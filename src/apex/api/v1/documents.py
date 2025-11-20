"""
Document upload, validation, and retrieval endpoints.

Handles document upload to Azure Blob Storage and AI-powered validation.
"""
import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from apex.azure.blob_storage import BlobStorageClient
from apex.config import config
from apex.database.repositories.audit_repository import AuditRepository
from apex.database.repositories.document_repository import DocumentRepository
from apex.database.repositories.job_repository import JobRepository
from apex.database.repositories.project_repository import ProjectRepository
from apex.dependencies import (
    get_audit_repo,
    get_blob_storage,
    get_current_user,
    get_db,
    get_document_repo,
    get_job_repo,
    get_project_repo,
)
from apex.models.database import User
from apex.models.enums import ValidationStatus
from apex.models.schemas import (
    DocumentResponse,
    DocumentUploadResponse,
    JobStatusResponse,
    PaginatedResponse,
)
from apex.services.background_jobs import process_document_validation
from apex.utils.retry import azure_retry

logger = logging.getLogger(__name__)
router = APIRouter()


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitize filename to prevent path traversal, control characters, and Azure naming issues.

    Rules:
    - Extract basename only (no path components)
    - Remove/replace control characters and Unicode RTL markers
    - Replace unsafe characters with underscore
    - Enforce maximum length
    - Prevent Windows device names (CON, PRN, AUX, etc.)

    Args:
        filename: Original filename from upload
        max_length: Maximum allowed filename length

    Returns:
        Sanitized filename safe for Azure Blob Storage
    """
    # Extract basename only (prevents path traversal)
    safe_name = Path(filename).name

    # Remove control characters (0x00-0x1F) and Unicode RTL markers (0x200E, 0x200F, 0x202A-0x202E)
    safe_name = re.sub(r"[\x00-\x1F\u200E\u200F\u202A-\u202E]", "", safe_name)

    # Replace unsafe characters with underscore
    # Azure blob names cannot contain: \ / : * ? " < > |
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", safe_name)

    # Remove leading/trailing whitespace and dots (Azure constraint)
    safe_name = safe_name.strip(". \t\n\r")

    # Prevent Windows device names
    device_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }
    name_without_ext = safe_name.rsplit(".", 1)[0].upper()
    if name_without_ext in device_names:
        safe_name = f"file_{safe_name}"

    # Enforce max length (preserve extension if possible)
    if len(safe_name) > max_length:
        parts = safe_name.rsplit(".", 1)
        if len(parts) == 2:
            # Has extension - preserve it
            name, ext = parts
            max_name_len = max_length - len(ext) - 1
            safe_name = f"{name[:max_name_len]}.{ext}"
        else:
            # No extension
            safe_name = safe_name[:max_length]

    # Final safety check - if empty after sanitization, use default
    if not safe_name or safe_name == ".":
        safe_name = "uploaded_file"

    return safe_name


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
@azure_retry
async def upload_document(
    project_id: UUID = Form(..., description="Project UUID to associate document with"),
    document_type: str = Form(..., description="Document type: scope, engineering, schedule, bid"),
    file: UploadFile = File(..., description="Document file to upload"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    document_repo: DocumentRepository = Depends(get_document_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    blob_storage: BlobStorageClient = Depends(get_blob_storage),
):
    """
    Upload document to Azure Blob Storage and create database entry.

    Files are uploaded to: {container}/uploads/{project_id}/{timestamp}_{filename}

    After upload, document is in PENDING validation status.
    Call POST /documents/{document_id}/validate to trigger AI validation.
    """
    # Check user access to project
    if not project_repo.check_user_access(db, current_user.id, project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {project_id}",
        )

    # Verify project exists
    project = project_repo.get(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Validate document type
    valid_types = ["scope", "engineering", "schedule", "bid"]
    if document_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type. Must be one of: {', '.join(valid_types)}",
        )

    # Validate MIME type
    if file.content_type not in config.ALLOWED_MIME_TYPES:
        allowed_types = ", ".join(config.ALLOWED_MIME_TYPES)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed types: {allowed_types}",
        )

    # Validate file size (read and check before processing)
    file_content = await file.read()
    if len(file_content) > config.max_upload_size_bytes:
        file_size_mb = len(file_content) / 1024 / 1024
        max_size_mb = config.MAX_UPLOAD_SIZE_MB
        msg = f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed size of {max_size_mb} MB"
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=msg,
        )

    # Sanitize filename with comprehensive security checks
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_filename = sanitize_filename(file.filename)
    blob_name = f"uploads/{project_id}/{timestamp}_{safe_filename}"

    try:
        # Upload to blob storage
        await blob_storage.upload_document(
            container=config.AZURE_STORAGE_CONTAINER_UPLOADS,
            blob_name=blob_name,
            data=file_content,
            content_type=file.content_type,
        )

        # Create document database entry
        document_data = {
            "project_id": project_id,
            "document_type": document_type,
            "blob_path": blob_name,
            "validation_status": ValidationStatus.PENDING,
            "created_by_id": current_user.id,
        }
        document = document_repo.create(db, document_data)

        # Create audit log
        audit_repo.create(
            db,
            {
                "project_id": project_id,
                "user_id": current_user.id,
                "action": "document_uploaded",
                "details": {
                    "document_id": str(document.id),
                    "document_type": document_type,
                    "filename": file.filename,
                    "blob_path": blob_name,
                },
            },
        )

        return DocumentUploadResponse(
            id=document.id,
            project_id=document.project_id,
            document_type=document.document_type,
            blob_path=document.blob_path,
            validation_status=document.validation_status,
            created_at=document.created_at,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(exc)}",
        )


@router.post(
    "/{document_id}/validate",
    response_model=JobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@azure_retry
async def validate_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    document_repo: DocumentRepository = Depends(get_document_repo),
    job_repo: JobRepository = Depends(get_job_repo),
):
    """
    Queue AI-powered document validation as a background job.

    Use GET /jobs/{job_id} to poll status.
    """
    document = document_repo.get(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Check user access to project
    if not project_repo.check_user_access(db, current_user.id, document.project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {document.project_id}",
        )

    job = job_repo.create_job(
        db=db,
        job_type="document_validation",
        user_id=current_user.id,
        document_id=document_id,
        project_id=document.project_id,
    )

    logger.info("Queued document validation job %s for document %s", job.id, document_id)
    if config.TESTING:
        # In test mode, run inline to avoid background task timing issues
        await process_document_validation(job.id, document_id, current_user.id)
    else:
        asyncio.create_task(process_document_validation(job.id, document_id, current_user.id))

    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        progress_percent=job.progress_percent,
        current_step="Job queued",
        result_data=None,
        error_message=None,
        created_at=job.created_at,
        started_at=None,
        completed_at=None,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    document_repo: DocumentRepository = Depends(get_document_repo),
):
    """
    Get document details including validation results.

    Requires user to have access to the parent project.
    """
    # Get document
    document = document_repo.get(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Check user access to project
    if not project_repo.check_user_access(db, current_user.id, document.project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {document.project_id}",
        )

    return document


@router.get("/projects/{project_id}/documents", response_model=PaginatedResponse[DocumentResponse])
def list_project_documents(
    project_id: UUID,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    document_repo: DocumentRepository = Depends(get_document_repo),
):
    """
    List documents for a project with pagination.

    Requires user to have access to the project.
    """
    # Check user access to project
    if not project_repo.check_user_access(db, current_user.id, project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {project_id}",
        )

    # Verify project exists
    project = project_repo.get(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Get paginated documents
    items, total, has_next, has_prev = document_repo.get_paginated(
        db=db,
        project_id=project_id,
        page=page,
        page_size=page_size,
        document_type=document_type,
    )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
        has_prev=has_prev,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
@azure_retry
async def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    document_repo: DocumentRepository = Depends(get_document_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    blob_storage: BlobStorageClient = Depends(get_blob_storage),
):
    """
    Delete document from database and blob storage.

    Requires user to have access to the parent project.
    """
    # Get document
    document = document_repo.get(db, document_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )

    # Check user access to project
    if not project_repo.check_user_access(db, current_user.id, document.project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {document.project_id}",
        )

    # Create audit log before deletion
    audit_repo.create(
        db,
        {
            "project_id": document.project_id,
            "user_id": current_user.id,
            "action": "document_deleted",
            "details": {
                "document_id": str(document_id),
                "document_type": document.document_type,
                "blob_path": document.blob_path,
            },
        },
    )

    # Delete from blob storage
    try:
        await blob_storage.delete_document(
            container=config.AZURE_STORAGE_CONTAINER_UPLOADS,
            blob_name=document.blob_path,
        )
    except Exception as blob_error:
        # Log but don't fail - document might already be deleted from blob
        logger.warning(f"Blob deletion failed for {document.blob_path}: {blob_error}")

    # Delete from database
    document_repo.delete(db, document_id)

    return None
