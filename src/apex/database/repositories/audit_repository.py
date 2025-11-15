"""
Audit log repository with append-only operations.

CRITICAL: Audit logs are immutable for ISO-NE compliance.
No update() or delete() methods are exposed.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apex.database.repositories.base import BaseRepository
from apex.models.database import AuditLog


class AuditRepository(BaseRepository[AuditLog]):
    """
    Repository for AuditLog entity.

    Implements append-only pattern for regulatory compliance.
    Audit logs are immutable once created.
    """

    def __init__(self):
        super().__init__(AuditLog)

    # Override base methods to prevent mutations
    def update(self, *args, **kwargs):
        """
        Audit logs are immutable - update is prohibited.

        Raises:
            NotImplementedError: Always raises to prevent mutations
        """
        raise NotImplementedError("Audit logs are immutable - update operations are prohibited")

    def delete(self, *args, **kwargs):
        """
        Audit logs are immutable - delete is prohibited.

        Raises:
            NotImplementedError: Always raises to prevent mutations
        """
        raise NotImplementedError("Audit logs are immutable - delete operations are prohibited")

    def get_by_project_id(
        self,
        db: Session,
        project_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get all audit logs for a project.

        Args:
            db: Database session
            project_id: Project UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit logs for the project
        """
        query = (
            select(AuditLog)
            .where(AuditLog.project_id == project_id)
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )

        return db.execute(query).scalars().all()

    def get_by_estimate_id(
        self,
        db: Session,
        estimate_id: UUID,
    ) -> List[AuditLog]:
        """
        Get all audit logs for an estimate.

        Args:
            db: Database session
            estimate_id: Estimate UUID

        Returns:
            List of audit logs for the estimate
        """
        query = (
            select(AuditLog)
            .where(AuditLog.estimate_id == estimate_id)
            .order_by(AuditLog.timestamp.desc())
        )

        return db.execute(query).scalars().all()

    def get_by_user_id(
        self,
        db: Session,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get all audit logs for a user.

        Args:
            db: Database session
            user_id: User UUID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of audit logs for the user
        """
        query = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )

        return db.execute(query).scalars().all()

    def get_paginated(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 50,
        project_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        action: Optional[str] = None,
    ) -> tuple[List[AuditLog], int, bool, bool]:
        """
        Get paginated audit logs with optional filtering.

        Args:
            db: Database session
            page: Page number (1-indexed)
            page_size: Items per page
            project_id: Optional filter by project
            user_id: Optional filter by user
            action: Optional filter by action (e.g., "created", "validated", "estimated")

        Returns:
            Tuple of (items, total, has_next, has_prev)
        """
        query = select(AuditLog)

        # Apply filters
        if project_id:
            query = query.where(AuditLog.project_id == project_id)
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)

        # Order by timestamp (newest first)
        query = query.order_by(AuditLog.timestamp.desc())

        return self.paginate(db, query, page, page_size)

    def get_by_date_range(
        self,
        db: Session,
        start_date: datetime,
        end_date: datetime,
        project_id: Optional[UUID] = None,
    ) -> List[AuditLog]:
        """
        Get audit logs for compliance reporting within date range.

        Args:
            db: Database session
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            project_id: Optional filter by project

        Returns:
            List of audit logs within date range
        """
        query = select(AuditLog).where(
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date,
        )

        if project_id:
            query = query.where(AuditLog.project_id == project_id)

        # Order by timestamp (oldest first for reporting)
        query = query.order_by(AuditLog.timestamp.asc())

        return db.execute(query).scalars().all()
