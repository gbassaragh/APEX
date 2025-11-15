"""
Document upload, validation, and retrieval endpoints.

Handles document upload to Azure Blob Storage and AI-powered validation.
"""
from typing import Optional
from uuid import UUID
from datetime import datetime
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    Query,
    status,
)
from sqlalchemy.orm import Session

from apex.dependencies import (
    get_db,
    get_current_user,
    get_project_repo,
    get_document_repo,
    get_audit_repo,
    get_blob_storage,
    get_llm_orchestrator,
    get_document_parser,
)
from apex.database.repositories.project_repository import ProjectRepository
from apex.database.repositories.document_repository import DocumentRepository
from apex.database.repositories.audit_repository import AuditRepository
from apex.azure.blob_storage import BlobStorageClient
from apex.services.llm.orchestrator import LLMOrchestrator
from apex.services.document_parser import DocumentParser
from apex.models.database import User
from apex.models.schemas import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentValidationResult,
    PaginatedResponse,
)
from apex.models.enums import ValidationStatus, AACEClass
from apex.config import config
from apex.utils.errors import BusinessRuleViolation

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
    safe_name = re.sub(r'[\x00-\x1F\u200E\u200F\u202A-\u202E]', '', safe_name)

    # Replace unsafe characters with underscore
    # Azure blob names cannot contain: \ / : * ? " < > |
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', safe_name)

    # Remove leading/trailing whitespace and dots (Azure constraint)
    safe_name = safe_name.strip('. \t\n\r')

    # Prevent Windows device names
    device_names = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
                    'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4',
                    'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
    name_without_ext = safe_name.rsplit('.', 1)[0].upper()
    if name_without_ext in device_names:
        safe_name = f"file_{safe_name}"

    # Enforce max length (preserve extension if possible)
    if len(safe_name) > max_length:
        parts = safe_name.rsplit('.', 1)
        if len(parts) == 2:
            # Has extension - preserve it
            name, ext = parts
            max_name_len = max_length - len(ext) - 1
            safe_name = f"{name[:max_name_len]}.{ext}"
        else:
            # No extension
            safe_name = safe_name[:max_length]

    # Final safety check - if empty after sanitization, use default
    if not safe_name or safe_name == '.':
        safe_name = "uploaded_file"

    return safe_name


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
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
    project = project_repo.get_by_id(db, project_id)
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Allowed types: {', '.join(config.ALLOWED_MIME_TYPES)}",
        )

    # Validate file size (read and check before processing)
    file_content = await file.read()
    if len(file_content) > config.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({len(file_content) / 1024 / 1024:.2f} MB) exceeds maximum allowed size of {config.MAX_UPLOAD_SIZE_MB} MB",
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


@router.post("/{document_id}/validate", response_model=DocumentValidationResult)
async def validate_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    document_repo: DocumentRepository = Depends(get_document_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    blob_storage: BlobStorageClient = Depends(get_blob_storage),
    document_parser: DocumentParser = Depends(get_document_parser),
    llm_orchestrator: LLMOrchestrator = Depends(get_llm_orchestrator),
):
    """
    Trigger AI-powered document validation.

    Workflow:
    1. Load document from blob storage
    2. Parse document using Azure Document Intelligence
    3. Validate using LLM orchestrator
    4. Update document with validation results

    This is a synchronous operation that may take 30s-2min depending on document size.
    """
    # Get document
    document = document_repo.get_by_id(db, document_id)
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

    try:
        # Load document from blob storage
        document_bytes = await blob_storage.download_document(
            container=config.AZURE_STORAGE_CONTAINER_UPLOADS,
            blob_name=document.blob_path,
        )

        # Step 1: Parse document using DocumentParser (Azure Document Intelligence)
        try:
            structured_content = await document_parser.parse_document(
                document_bytes=document_bytes,
                filename=Path(document.blob_path).name,
                blob_path=f"{config.AZURE_STORAGE_CONTAINER_UPLOADS}/{document.blob_path}",
            )

            # Save parsed content immediately (even if validation fails later)
            document_repo.update_validation_result(
                db=db,
                document_id=document_id,
                validation_result={"parsed_content": structured_content},
                completeness_score=None,
                validation_status=ValidationStatus.PENDING,
            )

        except BusinessRuleViolation as circuit_error:
            # Circuit breaker open - service temporarily unavailable
            if circuit_error.code == "CIRCUIT_BREAKER_OPEN":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Document parsing service temporarily unavailable: {circuit_error.message}",
                )
            elif circuit_error.code == "UNSUPPORTED_FORMAT":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=circuit_error.message,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Document parsing failed: {circuit_error.message}",
                )

        except TimeoutError as timeout_error:
            # Document Intelligence timeout
            logger.error(f"Document parsing timeout for {document_id}: {timeout_error}")
            document_repo.update_validation_result(
                db=db,
                document_id=document_id,
                validation_result={"error": "Parsing timeout", "details": str(timeout_error)},
                completeness_score=0,
                validation_status=ValidationStatus.FAILED,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document parsing timeout: {str(timeout_error)}",
            )

        except Exception as parse_error:
            # Other parsing errors (DLQ handled internally by DocumentParser)
            logger.error(f"Document parsing error for {document_id}: {parse_error}", exc_info=True)
            document_repo.update_validation_result(
                db=db,
                document_id=document_id,
                validation_result={"error": "Parsing failed", "details": str(parse_error)},
                completeness_score=0,
                validation_status=ValidationStatus.FAILED,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document parsing failed: {str(parse_error)}",
            )

        # Step 2: Determine AACE class for LLM routing
        # For document validation (pre-estimation), use conservative class assumption:
        # - Bid documents: CLASS_2 (Control estimate - auditor persona)
        # - Other documents: CLASS_4 (Feasibility - checking completeness for scope/engineering/schedule)
        aace_class = AACEClass.CLASS_2 if document.document_type == "bid" else AACEClass.CLASS_4

        # Step 3: Validate with LLM orchestrator
        try:
            llm_validation = await llm_orchestrator.validate_document(
                aace_class=aace_class,
                document_type=document.document_type,
                structured_content=structured_content,
            )

            # Extract validation results
            completeness_score = llm_validation.get("completeness_score", 0)
            issues = llm_validation.get("issues", [])
            recommendations = llm_validation.get("recommendations", [])
            suitable_for_estimation = llm_validation.get("suitable_for_estimation", False)

            # Determine validation status
            if suitable_for_estimation and completeness_score >= 70:
                validation_status = ValidationStatus.PASSED
            elif completeness_score >= 50:
                validation_status = ValidationStatus.MANUAL_REVIEW
            else:
                validation_status = ValidationStatus.FAILED

            # Build complete validation result (includes parsed content + LLM validation)
            validation_result = {
                "parsed_content": structured_content,
                "llm_validation": llm_validation,
                "aace_class_used": aace_class.value,
            }

        except BusinessRuleViolation as llm_error:
            # LLM validation failed (hallucination detection, response extraction failure)
            logger.error(f"LLM validation error for {document_id}: {llm_error}")
            validation_status = ValidationStatus.MANUAL_REVIEW
            validation_result = {
                "parsed_content": structured_content,
                "llm_error": llm_error.message,
                "aace_class_used": aace_class.value,
            }
            completeness_score = None
            issues = [f"LLM validation failed: {llm_error.message}"]
            recommendations = ["Manual review required due to LLM validation failure"]
            suitable_for_estimation = False

        except Exception as llm_error:
            # Unexpected LLM errors
            logger.error(f"Unexpected LLM error for {document_id}: {llm_error}", exc_info=True)
            validation_status = ValidationStatus.MANUAL_REVIEW
            validation_result = {
                "parsed_content": structured_content,
                "llm_error": str(llm_error),
                "aace_class_used": aace_class.value,
            }
            completeness_score = None
            issues = [f"LLM validation error: {str(llm_error)}"]
            recommendations = ["Manual review required due to LLM error"]
            suitable_for_estimation = False

        # Update document with validation results
        updated_document = document_repo.update_validation_result(
            db=db,
            document_id=document_id,
            validation_result=validation_result,
            completeness_score=completeness_score,
            validation_status=validation_status,
        )

        # Create audit log
        audit_repo.create(
            db,
            {
                "project_id": document.project_id,
                "user_id": current_user.id,
                "action": "document_validated",
                "details": {
                    "document_id": str(document_id),
                    "validation_status": validation_status.value,
                    "completeness_score": completeness_score,
                },
            },
        )

        return DocumentValidationResult(
            document_id=document_id,
            validation_status=updated_document.validation_status,
            completeness_score=updated_document.completeness_score,
            issues=validation_result.get("issues", []),
            recommendations=validation_result.get("recommendations", []),
            suitable_for_estimation=suitable_for_estimation,
        )

    except Exception as exc:
        # Update document to FAILED status
        document_repo.update_validation_result(
            db=db,
            document_id=document_id,
            validation_result={"error": str(exc)},
            completeness_score=0,
            validation_status=ValidationStatus.FAILED,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document validation failed: {str(exc)}",
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
    document = document_repo.get_by_id(db, document_id)
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
    project = project_repo.get_by_id(db, project_id)
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
    document = document_repo.get_by_id(db, document_id)
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
