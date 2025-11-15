"""
Project repository with access control queries.

CRITICAL: Access control methods enforce application-level RBAC.
Having an AAD token alone is NOT sufficient for project access.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apex.database.repositories.base import BaseRepository
from apex.models.database import AppRole, Project, ProjectAccess
from apex.models.enums import ProjectStatus


class ProjectRepository(BaseRepository[Project]):
    """
    Repository for Project entity.

    Implements project-specific queries and access control enforcement.
    """

    def __init__(self):
        super().__init__(Project)

    def get_by_project_number(self, db: Session, project_number: str) -> Optional[Project]:
        """
        Get project by project number (unique identifier).

        Args:
            db: Database session
            project_number: Project number (e.g., "TX-2024-001")

        Returns:
            Project or None if not found
        """
        query = select(Project).where(Project.project_number == project_number)
        return db.execute(query).scalar_one_or_none()

    def get_paginated(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[ProjectStatus] = None,
        user_id: Optional[UUID] = None,
    ) -> tuple[List[Project], int, bool, bool]:
        """
        Get paginated projects with optional filtering.

        HIGH FIX (Codex): Use DISTINCT when filtering by user_id to prevent
        duplicate projects when user has multiple roles.

        Args:
            db: Database session
            page: Page number (1-indexed)
            page_size: Items per page
            status: Filter by project status
            user_id: Filter by user access (only projects user can access)

        Returns:
            Tuple of (items, total, has_next, has_prev)
        """
        # Use DISTINCT when user filtering is applied
        if user_id:
            query = select(Project).distinct(Project.id)
        else:
            query = select(Project)

        # Apply status filter
        if status:
            query = query.where(Project.status == status)

        # Apply user access filter (join with ProjectAccess)
        if user_id:
            query = query.join(ProjectAccess, Project.id == ProjectAccess.project_id).where(
                ProjectAccess.user_id == user_id
            )

        # Order by creation date (newest first)
        query = query.order_by(Project.created_at.desc())

        return self.paginate(db, query, page, page_size)

    def check_user_access(
        self,
        db: Session,
        user_id: UUID,
        project_id: UUID,
    ) -> bool:
        """
        Check if user has access to project.

        CRITICAL: This method enforces application-level RBAC.
        Must be called before allowing any project operations.

        Args:
            db: Database session
            user_id: User UUID
            project_id: Project UUID

        Returns:
            True if user has access, False otherwise
        """
        query = select(ProjectAccess).where(
            ProjectAccess.user_id == user_id,
            ProjectAccess.project_id == project_id,
        )
        access = db.execute(query).scalar_one_or_none()
        return access is not None

    def check_user_has_role(
        self,
        db: Session,
        user_id: UUID,
        project_id: UUID,
        role_id: int,
    ) -> bool:
        """
        Check if user has specific role on project.

        Used for role-based access control (e.g., Manager-only operations).

        Args:
            db: Database session
            user_id: User UUID
            project_id: Project UUID
            role_id: AppRole ID to check for

        Returns:
            True if user has the specified role on this project, False otherwise
        """
        query = select(ProjectAccess).where(
            ProjectAccess.user_id == user_id,
            ProjectAccess.project_id == project_id,
            ProjectAccess.app_role_id == role_id,
        )
        access = db.execute(query).scalar_one_or_none()
        return access is not None

    def get_user_projects(
        self,
        db: Session,
        user_id: UUID,
        role: Optional[str] = None,
    ) -> List[Project]:
        """
        Get all projects user has access to.

        Args:
            db: Database session
            user_id: User UUID
            role: Optional filter by AppRole name (e.g., "Estimator", "Manager")

        Returns:
            List of projects user can access
        """
        query = (
            select(Project)
            .join(ProjectAccess, Project.id == ProjectAccess.project_id)
            .where(ProjectAccess.user_id == user_id)
        )

        # Filter by role if specified
        if role:
            query = query.join(AppRole, ProjectAccess.app_role_id == AppRole.id).where(
                AppRole.role_name == role
            )

        # Order by creation date (newest first)
        query = query.order_by(Project.created_at.desc())

        return db.execute(query).scalars().all()

    def grant_access(
        self,
        db: Session,
        user_id: UUID,
        project_id: UUID,
        role_id: int,
    ) -> ProjectAccess:
        """
        Grant user access to project with specific role.

        HIGH FIX (Codex): Include role_id in lookup to support multiple roles per user/project.
        Data model allows multiple roles via UniqueConstraint(user_id, project_id, app_role_id).

        Args:
            db: Database session
            user_id: User UUID
            project_id: Project UUID
            role_id: AppRole ID (1=Estimator, 2=Manager, 3=Auditor, etc.)

        Returns:
            Created or existing ProjectAccess entity
        """
        # Check if exact role already exists
        existing = (
            db.query(ProjectAccess)
            .filter(
                ProjectAccess.user_id == user_id,
                ProjectAccess.project_id == project_id,
                ProjectAccess.app_role_id == role_id,
            )
            .one_or_none()
        )

        if existing:
            # Exact role already exists
            return existing

        # Create new access (allows multiple roles per user/project)
        access = ProjectAccess(
            user_id=user_id,
            project_id=project_id,
            app_role_id=role_id,
        )
        db.add(access)
        db.flush()
        db.refresh(access)
        return access

    def revoke_access(
        self,
        db: Session,
        user_id: UUID,
        project_id: UUID,
        role_id: Optional[int] = None,
    ) -> bool:
        """
        Revoke user access to project.

        CRITICAL FIX (Codex): Handle multiple roles per user/project.
        If role_id is None, revokes ALL roles for the user/project.
        If role_id is specified, revokes only that specific role.

        Args:
            db: Database session
            user_id: User UUID
            project_id: Project UUID
            role_id: Optional AppRole ID (None = revoke all roles)

        Returns:
            True if any access was revoked, False if no access existed
        """
        query = db.query(ProjectAccess).filter(
            ProjectAccess.user_id == user_id,
            ProjectAccess.project_id == project_id,
        )

        # Filter by specific role if provided
        if role_id is not None:
            query = query.filter(ProjectAccess.app_role_id == role_id)

        # Delete all matching rows
        deleted_count = query.delete(synchronize_session=False)
        db.flush()

        return deleted_count > 0
