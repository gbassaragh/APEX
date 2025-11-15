"""
Document repository with project-specific queries.

Handles document CRUD operations and validation status management.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apex.database.repositories.base import BaseRepository
from apex.models.database import Document
from apex.models.enums import ValidationStatus


class DocumentRepository(BaseRepository[Document]):
    """
    Repository for Document entity.

    Implements document-specific queries including project filtering
    and validation status management.
    """

    def __init__(self):
        super().__init__(Document)

    def get_by_project_id(
        self,
        db: Session,
        project_id: UUID,
        document_type: Optional[str] = None,
        validation_status: Optional[ValidationStatus] = None,
    ) -> List[Document]:
        """
        Get all documents for a project with optional filters.

        REQUIRED by estimate_generator service.

        Args:
            db: Database session
            project_id: Project UUID
            document_type: Optional filter by type ("scope", "engineering", "schedule", "bid")
            validation_status: Optional filter by validation status

        Returns:
            List of documents matching criteria
        """
        query = select(Document).where(Document.project_id == project_id)

        # Apply document type filter
        if document_type:
            query = query.where(Document.document_type == document_type)

        # Apply validation status filter
        if validation_status:
            query = query.where(Document.validation_status == validation_status)

        # Order by creation date (oldest first for processing order)
        query = query.order_by(Document.created_at.asc())

        return db.execute(query).scalars().all()

    def get_paginated(
        self,
        db: Session,
        project_id: UUID,
        page: int = 1,
        page_size: int = 20,
        document_type: Optional[str] = None,
    ) -> tuple[List[Document], int, bool, bool]:
        """
        Get paginated documents for a project.

        Args:
            db: Database session
            project_id: Project UUID
            page: Page number (1-indexed)
            page_size: Items per page
            document_type: Optional filter by document type

        Returns:
            Tuple of (items, total, has_next, has_prev)
        """
        query = select(Document).where(Document.project_id == project_id)

        # Apply document type filter
        if document_type:
            query = query.where(Document.document_type == document_type)

        # Order by creation date (newest first)
        query = query.order_by(Document.created_at.desc())

        return self.paginate(db, query, page, page_size)

    def get_validated_documents(
        self,
        db: Session,
        project_id: UUID,
    ) -> List[Document]:
        """
        Get only validated documents for a project.

        Documents are considered validated if:
        - validation_status = PASSED
        - completeness_score >= 70

        Args:
            db: Database session
            project_id: Project UUID

        Returns:
            List of validated documents
        """
        query = (
            select(Document)
            .where(
                Document.project_id == project_id,
                Document.validation_status == ValidationStatus.PASSED,
                Document.completeness_score >= 70,
            )
            .order_by(Document.created_at.asc())
        )

        return db.execute(query).scalars().all()

    def update_validation_result(
        self,
        db: Session,
        document_id: UUID,
        validation_result: Dict[str, Any],
        completeness_score: int,
        validation_status: ValidationStatus,
    ) -> Document:
        """
        Update document validation result from LLM validation.

        LOW FIX (Codex): Use proper exception for not found case.

        Args:
            db: Database session
            document_id: Document UUID
            validation_result: JSON validation result from LLM orchestrator
            completeness_score: Completeness score (0-100)
            validation_status: Validation status enum value

        Returns:
            Updated document entity

        Raises:
            ValueError: If document not found (API layer should catch and return 404)
        """
        document = db.get(Document, document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        # Update validation fields
        document.validation_result = validation_result
        document.completeness_score = completeness_score
        document.validation_status = validation_status

        db.add(document)
        db.flush()
        db.refresh(document)
        return document
