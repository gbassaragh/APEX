"""
Integration tests for project management endpoints.

Tests:
- Project creation
- Project listing with pagination
- Project retrieval
- Access control enforcement
"""
import pytest
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy import select

from apex.models.database import Project, ProjectAccess, AppRole, AuditLog
from apex.models.enums import ProjectStatus


@pytest.mark.asyncio
class TestProjectCreation:
    """Test project creation endpoint."""

    async def test_create_project_success(self, client: AsyncClient, test_user, db_session):
        """Test successful project creation."""
        project_data = {
            "project_number": "PROJ-INT-001",
            "project_name": "Integration Test Project",
            "voltage_level": 230,
            "line_miles": 15.5,
            "terrain_type": "flat",
        }

        response = await client.post("/api/v1/projects/", json=project_data)

        assert response.status_code == 201
        result = response.json()

        assert result["project_number"] == "PROJ-INT-001"
        assert result["project_name"] == "Integration Test Project"
        assert result["voltage_level"] == 230
        assert result["status"] == "draft"

        # Verify project in database
        project = db_session.execute(
            select(Project).where(Project.id == result["id"])
        ).scalar_one()

        assert project.created_by_id == test_user.id

        # Verify creator has Manager access
        access = db_session.execute(
            select(ProjectAccess)
            .join(AppRole)
            .where(
                ProjectAccess.project_id == project.id,
                ProjectAccess.user_id == test_user.id,
                AppRole.role_name == "Manager"
            )
        ).scalar_one_or_none()

        assert access is not None

        # Verify audit log
        audit = db_session.execute(
            select(AuditLog).where(
                AuditLog.project_id == project.id,
                AuditLog.action == "project_created"
            )
        ).scalar_one()

        assert audit.user_id == test_user.id

    async def test_create_project_duplicate_number(self, client: AsyncClient, test_project):
        """Test duplicate project number rejection."""
        project_data = {
            "project_number": test_project.project_number,  # Duplicate
            "project_name": "Duplicate Project",
            "voltage_level": 115,
        }

        response = await client.post("/api/v1/projects/", json=project_data)

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    async def test_create_project_invalid_voltage(self, client: AsyncClient):
        """Test validation of voltage level."""
        project_data = {
            "project_number": "PROJ-BAD-001",
            "project_name": "Invalid Voltage Project",
            "voltage_level": -115,  # Invalid
        }

        response = await client.post("/api/v1/projects/", json=project_data)

        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
class TestProjectRetrieval:
    """Test project retrieval endpoints."""

    async def test_get_project_success(self, client: AsyncClient, test_project):
        """Test retrieving project by ID."""
        response = await client.get(f"/api/v1/projects/{test_project.id}")

        assert response.status_code == 200
        result = response.json()

        assert result["id"] == str(test_project.id)
        assert result["project_number"] == test_project.project_number

    async def test_get_project_not_found(self, client: AsyncClient):
        """Test 404 for non-existent project."""
        fake_id = uuid4()
        response = await client.get(f"/api/v1/projects/{fake_id}")

        assert response.status_code == 404

    async def test_get_project_unauthorized_access(self, client: AsyncClient, test_user, db_session):
        """Test access control prevents unauthorized access."""
        # Create project without granting access to test_user
        unauthorized_project = Project(
            project_number="PROJ-UNAUTH-001",
            project_name="Unauthorized Project",
            status=ProjectStatus.DRAFT,
            created_by_id=test_user.id,
        )
        db_session.add(unauthorized_project)
        db_session.commit()

        response = await client.get(f"/api/v1/projects/{unauthorized_project.id}")

        assert response.status_code == 403
        assert "does not have access" in response.json()["detail"]

    async def test_list_projects_pagination(self, client: AsyncClient, test_user, db_session):
        """Test project listing with pagination."""
        # Create multiple projects with access
        estimator_role = db_session.query(AppRole).filter_by(role_name="Estimator").first()

        for i in range(5):
            project = Project(
                project_number=f"PROJ-LIST-{i:03d}",
                project_name=f"Test Project {i}",
                status=ProjectStatus.DRAFT,
                created_by_id=test_user.id,
            )
            db_session.add(project)
            db_session.flush()

            access = ProjectAccess(
                user_id=test_user.id,
                project_id=project.id,
                app_role_id=estimator_role.id,
            )
            db_session.add(access)

        db_session.commit()

        response = await client.get("/api/v1/projects/", params={"page": 1, "page_size": 3})

        assert response.status_code == 200
        result = response.json()

        assert result["total"] >= 5  # At least our 5 + test_project
        assert len(result["items"]) == 3
        assert result["page"] == 1
        assert result["page_size"] == 3
        assert result["has_next"] is True


@pytest.mark.asyncio
class TestProjectUpdate:
    """Test project update endpoint."""

    async def test_update_project_success(self, client: AsyncClient, test_project):
        """Test successful project update."""
        update_data = {
            "project_name": "Updated Project Name",
            "status": "validated",
        }

        response = await client.patch(f"/api/v1/projects/{test_project.id}", json=update_data)

        assert response.status_code == 200
        result = response.json()

        assert result["project_name"] == "Updated Project Name"
        assert result["status"] == "validated"

    async def test_update_project_requires_manager_role(
        self, client: AsyncClient, test_project, test_user, db_session
    ):
        """Test only Manager role can update project status."""
        # Downgrade user to Estimator role
        estimator_role = db_session.query(AppRole).filter_by(role_name="Estimator").first()
        access = db_session.execute(
            select(ProjectAccess).where(
                ProjectAccess.project_id == test_project.id,
                ProjectAccess.user_id == test_user.id
            )
        ).scalar_one()
        access.app_role_id = estimator_role.id
        db_session.commit()

        update_data = {"status": "complete"}

        response = await client.patch(f"/api/v1/projects/{test_project.id}", json=update_data)

        # Should fail - estimators cannot change status
        assert response.status_code == 403


@pytest.mark.asyncio
class TestProjectDeletion:
    """Test project deletion endpoint (soft delete)."""

    async def test_delete_project_soft_delete(self, client: AsyncClient, test_project, db_session):
        """Test project soft delete (archive)."""
        project_id = test_project.id

        response = await client.delete(f"/api/v1/projects/{project_id}")

        assert response.status_code == 204

        # Verify project is archived, not deleted
        db_session.refresh(test_project)
        assert test_project.status == ProjectStatus.ARCHIVED
