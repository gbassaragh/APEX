"""
Project CRUD endpoints with access control enforcement.

All project operations enforce application-level RBAC via ProjectAccess table.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from apex.database.repositories.audit_repository import AuditRepository
from apex.database.repositories.project_repository import ProjectRepository
from apex.dependencies import get_audit_repo, get_current_user, get_db, get_project_repo
from apex.models.database import User
from apex.models.enums import AppRoleType, ProjectStatus
from apex.models.schemas import (
    PaginatedResponse,
    ProjectAccessGrant,
    ProjectAccessResponse,
    ProjectAccessRevoke,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """
    Create new project and grant creator access with Estimator role.

    The creator is automatically granted Estimator role (role_id=1) on the new project.
    """
    # Check for duplicate project number
    existing = project_repo.get_by_project_number(db, project_in.project_number)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project number '{project_in.project_number}' already exists",
        )

    # Create project
    project_data = project_in.model_dump()
    project_data["created_by_id"] = current_user.id
    project = project_repo.create(db, project_data)

    # Grant creator access with Estimator role
    project_repo.grant_access(db, current_user.id, project.id, role_id=AppRoleType.ESTIMATOR.value)

    # Create audit log
    audit_repo.create(
        db,
        {
            "project_id": project.id,
            "user_id": current_user.id,
            "action": "project_created",
            "details": {
                "project_number": project.project_number,
                "project_name": project.project_name,
            },
        },
    )

    return project


@router.get("", response_model=PaginatedResponse[ProjectResponse])
def list_projects(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[ProjectStatus] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """
    List projects accessible to current user with pagination.

    Only returns projects where the user has access (via ProjectAccess table).
    """
    items, total, has_next, has_prev = project_repo.get_paginated(
        db,
        page=page,
        page_size=page_size,
        status=status_filter,
        user_id=current_user.id,  # Filter by user access
    )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
        has_prev=has_prev,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    """
    Get project details.

    Requires user to have access to the project.
    """
    # Get project
    project = project_repo.get(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Check user access
    if not project_repo.check_user_access(db, current_user.id, project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {project_id}",
        )

    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: UUID,
    project_update: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """
    Update project details.

    Requires user to have Manager role on the project.
    """
    # Check user has Manager role (not just access)
    if not project_repo.check_user_has_role(
        db, current_user.id, project_id, AppRoleType.MANAGER.value
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User must have Manager role to update project {project_id}",
        )

    # Get project
    project = project_repo.get(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Update project
    update_data = project_update.model_dump(exclude_unset=True)
    updated_project = project_repo.update(db, project_id, update_data)

    # Create audit log
    audit_repo.create(
        db,
        {
            "project_id": project_id,
            "user_id": current_user.id,
            "action": "project_updated",
            "details": {"updates": update_data},
        },
    )

    return updated_project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """
    Delete project.

    Requires user to have Manager role on the project.
    NOTE: This is a hard delete. Consider implementing soft delete for production.
    """
    # Check user has Manager role (not just access)
    if not project_repo.check_user_has_role(
        db, current_user.id, project_id, AppRoleType.MANAGER.value
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User must have Manager role to delete project {project_id}",
        )

    # Get project to verify it exists
    project = project_repo.get(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Create audit log before deletion
    audit_repo.create(
        db,
        {
            "project_id": project_id,
            "user_id": current_user.id,
            "action": "project_deleted",
            "details": {
                "project_number": project.project_number,
                "project_name": project.project_name,
            },
        },
    )

    # Delete project
    project_repo.delete(db, project_id)

    return None


@router.post("/{project_id}/access", response_model=ProjectAccessResponse)
def grant_project_access(
    project_id: UUID,
    access_grant: ProjectAccessGrant,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """
    Grant user access to project with specific role.

    Requires current user to have Manager role on the project.
    """
    # Check current user has Manager role on project
    if not project_repo.check_user_has_role(
        db, current_user.id, project_id, AppRoleType.MANAGER.value
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User must have Manager role to grant access to project {project_id}",
        )

    # Verify project exists
    project = project_repo.get(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Validate role_id against AppRoleType enum
    try:
        AppRoleType(access_grant.role_id)
    except ValueError:
        valid_roles = [r.value for r in AppRoleType]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role_id: {access_grant.role_id}. Must be one of: {valid_roles}",
        )

    # Grant access
    project_repo.grant_access(db, access_grant.user_id, project_id, access_grant.role_id)

    # Create audit log
    audit_repo.create(
        db,
        {
            "project_id": project_id,
            "user_id": current_user.id,
            "action": "access_granted",
            "details": {
                "granted_to_user_id": str(access_grant.user_id),
                "role_id": access_grant.role_id,
            },
        },
    )

    return ProjectAccessResponse(
        project_id=project_id,
        user_id=access_grant.user_id,
        role_id=access_grant.role_id,
        granted=True,
    )


@router.delete("/{project_id}/access", status_code=status.HTTP_204_NO_CONTENT)
def revoke_project_access(
    project_id: UUID,
    access_revoke: ProjectAccessRevoke,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """
    Revoke user access to project.

    If role_id is specified, revokes only that specific role.
    If role_id is None, revokes all roles for the user on this project.

    Requires current user to have Manager role on the project.
    """
    # Check current user has Manager role on project
    if not project_repo.check_user_has_role(
        db, current_user.id, project_id, AppRoleType.MANAGER.value
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User must have Manager role to revoke access to project {project_id}",
        )

    # Verify project exists
    project = project_repo.get(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Revoke access
    revoked = project_repo.revoke_access(
        db, access_revoke.user_id, project_id, access_revoke.role_id
    )

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching access found to revoke",
        )

    # Create audit log
    audit_repo.create(
        db,
        {
            "project_id": project_id,
            "user_id": current_user.id,
            "action": "access_revoked",
            "details": {
                "revoked_from_user_id": str(access_revoke.user_id),
                "role_id": access_revoke.role_id,
            },
        },
    )

    return None
