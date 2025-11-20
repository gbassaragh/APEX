"""
Integration tests for document upload and validation endpoints.

Tests the complete workflow:
1. Document upload to blob storage
2. Document parsing with Azure Document Intelligence
3. LLM validation
4. Database persistence
5. Audit logging
"""
from io import BytesIO
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from apex.models.database import AuditLog, Document, Project
from apex.models.enums import AACEClass, ProjectStatus, ValidationStatus


@pytest.mark.asyncio
class TestDocumentUpload:
    """Test document upload endpoint."""

    async def test_upload_pdf_document_success(
        self, client: AsyncClient, test_project, test_user, db_session
    ):
        """Test successful PDF document upload."""
        # Create test PDF content
        pdf_content = b"%PDF-1.4\n%Test PDF content\n%%EOF"

        files = {"file": ("test_scope.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {
            "project_id": str(test_project.id),
            "document_type": "scope",
        }

        response = await client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
        )

        assert response.status_code == 201
        result = response.json()

        # Verify response structure
        assert result["project_id"] == str(test_project.id)
        assert result["document_type"] == "scope"
        assert result["validation_status"] == "pending"
        assert "blob_path" in result
        assert result["blob_path"].startswith("uploads/")

        # Verify document in database
        document = db_session.execute(
            select(Document).where(Document.id == result["id"])
        ).scalar_one()

        assert document.project_id == test_project.id
        assert document.document_type == "scope"
        assert document.validation_status == ValidationStatus.PENDING
        assert document.created_by_id == test_user.id

        # Verify audit log created
        audit_log = db_session.execute(
            select(AuditLog).where(
                AuditLog.project_id == test_project.id, AuditLog.action == "document_uploaded"
            )
        ).scalar_one()

        assert audit_log.user_id == test_user.id
        assert audit_log.details["document_id"] == str(document.id)

    async def test_upload_document_sanitizes_filename(
        self, client: AsyncClient, test_project, db_session
    ):
        """Test filename sanitization (path traversal prevention)."""
        pdf_content = b"%PDF-1.4\n%Test\n%%EOF"

        # Try path traversal attack
        files = {"file": ("../../etc/passwd", BytesIO(pdf_content), "application/pdf")}
        data = {
            "project_id": str(test_project.id),
            "document_type": "scope",
        }

        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 201
        result = response.json()

        # Verify filename is sanitized (only basename preserved)
        assert "../../" not in result["blob_path"]
        assert "passwd" in result["blob_path"]  # Basename preserved

    async def test_upload_document_file_too_large(self, client: AsyncClient, test_project):
        """Test file size limit enforcement."""
        # Create file larger than MAX_UPLOAD_SIZE_MB (50 MB)
        large_content = b"X" * (51 * 1024 * 1024)  # 51 MB

        files = {"file": ("large.pdf", BytesIO(large_content), "application/pdf")}
        data = {
            "project_id": str(test_project.id),
            "document_type": "scope",
        }

        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 413  # Request Entity Too Large
        assert "exceeds maximum allowed size" in response.json()["detail"]

    async def test_upload_document_unsupported_mime_type(self, client: AsyncClient, test_project):
        """Test unsupported file type rejection."""
        exe_content = b"MZ\x90\x00"  # Fake .exe file

        files = {"file": ("malware.exe", BytesIO(exe_content), "application/x-msdownload")}
        data = {
            "project_id": str(test_project.id),
            "document_type": "scope",
        }

        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    async def test_upload_document_unauthorized_project_access(
        self, client: AsyncClient, test_user, db_session
    ):
        """Test upload to project without access is forbidden."""
        # Create project without user access
        unauthorized_project = Project(
            project_number="PROJ-UNAUTHORIZED",
            project_name="Unauthorized Project",
            status=ProjectStatus.DRAFT,
            created_by_id=test_user.id,
        )
        db_session.add(unauthorized_project)
        db_session.commit()

        pdf_content = b"%PDF-1.4\n%Test\n%%EOF"
        files = {"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")}
        data = {
            "project_id": str(unauthorized_project.id),
            "document_type": "scope",
        }

        response = await client.post("/api/v1/documents/upload", files=files, data=data)

        assert response.status_code == 403
        assert "does not have access" in response.json()["detail"]


@pytest.mark.asyncio
class TestDocumentValidation:
    """Test document validation endpoint."""

    async def test_validate_document_success(
        self,
        client: AsyncClient,
        test_document,
        mock_document_parser,
        mock_llm_orchestrator,
        db_session,
    ):
        """Test successful document validation workflow with async job pattern."""
        # Configure mocks
        mock_document_parser.set_parse_result(
            {
                "filename": "test.pdf",
                "pages": [{"page_number": 1, "lines": [{"content": "Test scope document"}]}],
                "tables": [],
                "paragraphs": [{"content": "Complete project scope"}],
                "metadata": {"page_count": 1},
            }
        )

        mock_llm_orchestrator.set_validation_result(
            {
                "completeness_score": 85,
                "issues": [],
                "recommendations": ["Document is complete"],
                "suitable_for_estimation": True,
            }
        )

        # NEW: Endpoint returns 202 Accepted with job_id
        response = await client.post(f"/api/v1/documents/{test_document.id}/validate")

        assert response.status_code == 202  # Accepted, job queued
        result = response.json()

        # Verify job created
        assert "id" in result  # job_id
        assert result["job_type"] == "document_validation"
        assert result["status"] == "pending"

        job_id = result["id"]

        # In test mode (config.TESTING=True), job runs inline, so check completion
        job_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200
        job_result = job_response.json()

        # Verify job completed successfully
        assert job_result["status"] == "completed"
        assert job_result["result_data"]["document_id"] == str(test_document.id)
        assert job_result["result_data"]["validation_status"] == "passed"
        assert job_result["result_data"]["completeness_score"] == 85
        assert job_result["result_data"]["suitable_for_estimation"] is True

        # Verify document updated in database
        db_session.refresh(test_document)
        assert test_document.validation_status == ValidationStatus.PASSED
        assert test_document.completeness_score == 85

    async def test_validate_document_circuit_breaker_open(
        self, client: AsyncClient, test_document, mock_document_parser, db_session
    ):
        """Test circuit breaker open causes job failure."""
        # Simulate circuit breaker open
        mock_document_parser.set_circuit_breaker_open(True)

        # Job creation succeeds (202), but execution fails
        response = await client.post(f"/api/v1/documents/{test_document.id}/validate")

        assert response.status_code == 202  # Accepted
        result = response.json()
        job_id = result["id"]

        # In test mode, job runs inline and should fail
        job_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200
        job_result = job_response.json()

        # Verify job failed due to circuit breaker
        assert job_result["status"] == "failed"
        assert (
            "temporarily unavailable" in job_result["error_message"].lower()
            or "circuit" in job_result["error_message"].lower()
        )

        # Verify document marked as FAILED
        db_session.refresh(test_document)
        assert test_document.validation_status == ValidationStatus.FAILED

    async def test_validate_document_parsing_timeout(
        self, client: AsyncClient, test_document, mock_document_parser, db_session
    ):
        """Test parsing timeout causes job failure."""
        # Simulate timeout
        mock_document_parser.set_timeout(True)

        # Job creation succeeds (202), but execution fails
        response = await client.post(f"/api/v1/documents/{test_document.id}/validate")

        assert response.status_code == 202  # Accepted
        result = response.json()
        job_id = result["id"]

        # In test mode, job runs inline and should fail
        job_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200
        job_result = job_response.json()

        # Verify job failed due to timeout
        assert job_result["status"] == "failed"
        assert (
            "timeout" in job_result["error_message"].lower()
            or "timed out" in job_result["error_message"].lower()
        )

        # Verify document marked as FAILED
        db_session.refresh(test_document)
        assert test_document.validation_status == ValidationStatus.FAILED

    async def test_validate_document_llm_error_manual_review(
        self,
        client: AsyncClient,
        test_document,
        mock_document_parser,
        mock_llm_orchestrator,
        db_session,
    ):
        """Test LLM validation error triggers MANUAL_REVIEW status in async job."""
        # Document parsing succeeds
        mock_document_parser.set_parse_result(
            {
                "filename": "test.pdf",
                "pages": [{"page_number": 1}],
                "tables": [],
                "paragraphs": [],
                "metadata": {"page_count": 1},
            }
        )

        # LLM validation fails
        mock_llm_orchestrator.set_error("Hallucination detected")

        # Job creation succeeds (202), parsing succeeds, but LLM fails gracefully
        response = await client.post(f"/api/v1/documents/{test_document.id}/validate")

        assert response.status_code == 202  # Accepted
        result = response.json()
        job_id = result["id"]

        # In test mode, job runs inline and completes (with MANUAL_REVIEW status)
        job_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200
        job_result = job_response.json()

        # Verify job completed (not failed) but document needs manual review
        assert job_result["status"] == "completed"
        assert job_result["result_data"]["validation_status"] == "manual_review"
        assert job_result["result_data"]["suitable_for_estimation"] is False

        # Verify parsed content was saved and document marked for manual review
        db_session.refresh(test_document)
        assert test_document.validation_status == ValidationStatus.MANUAL_REVIEW
        assert "parsed_content" in test_document.validation_result
        assert (
            "llm_error" in test_document.validation_result
            or "llm_validation" in test_document.validation_result
        )

    async def test_validate_document_bid_uses_class2(
        self, client: AsyncClient, test_project, test_user, db_session, mock_llm_orchestrator
    ):
        """Test bid documents use AACE CLASS_2 (auditor persona) in async job."""
        # Create bid document
        bid_document = Document(
            project_id=test_project.id,
            document_type="bid",
            blob_path="uploads/test_bid.pdf",
            validation_status=ValidationStatus.PENDING,
            created_by_id=test_user.id,
        )
        db_session.add(bid_document)
        db_session.commit()

        # Trigger validation job
        response = await client.post(f"/api/v1/documents/{bid_document.id}/validate")

        assert response.status_code == 202  # Accepted
        result = response.json()
        job_id = result["id"]

        # Wait for job completion (inline in test mode)
        job_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200

        # Verify LLM was called with CLASS_2 (bid documents use auditor persona)
        assert mock_llm_orchestrator.last_aace_class == AACEClass.CLASS_2

    async def test_validate_document_scope_uses_class4(
        self, client: AsyncClient, test_document, mock_llm_orchestrator
    ):
        """Test scope documents use AACE CLASS_4 (feasibility persona) in async job."""
        # Trigger validation job
        response = await client.post(f"/api/v1/documents/{test_document.id}/validate")

        assert response.status_code == 202  # Accepted
        result = response.json()
        job_id = result["id"]

        # Wait for job completion (inline in test mode)
        job_response = await client.get(f"/api/v1/jobs/{job_id}")
        assert job_response.status_code == 200

        # Verify LLM was called with CLASS_4 (scope documents use feasibility persona)
        assert mock_llm_orchestrator.last_aace_class == AACEClass.CLASS_4


@pytest.mark.asyncio
class TestDocumentRetrieval:
    """Test document retrieval endpoints."""

    async def test_get_document_success(self, client: AsyncClient, test_document):
        """Test retrieving document by ID."""
        response = await client.get(f"/api/v1/documents/{test_document.id}")

        assert response.status_code == 200
        result = response.json()

        assert result["id"] == str(test_document.id)
        assert result["document_type"] == test_document.document_type

    async def test_get_document_not_found(self, client: AsyncClient):
        """Test 404 for non-existent document."""
        fake_id = uuid4()
        response = await client.get(f"/api/v1/documents/{fake_id}")

        assert response.status_code == 404

    async def test_list_project_documents(
        self, client: AsyncClient, test_project, test_user, db_session
    ):
        """Test listing documents for a project with pagination."""
        # Create multiple documents
        for i in range(5):
            doc = Document(
                project_id=test_project.id,
                document_type="scope" if i % 2 == 0 else "engineering",
                blob_path=f"uploads/test_{i}.pdf",
                validation_status=ValidationStatus.PENDING,
                created_by_id=test_user.id,
            )
            db_session.add(doc)
        db_session.commit()

        response = await client.get(
            f"/api/v1/documents/projects/{test_project.id}/documents",
            params={"page": 1, "page_size": 3},
        )

        assert response.status_code == 200
        result = response.json()

        assert result["total"] == 5
        assert len(result["items"]) == 3
        assert result["page"] == 1
        assert result["page_size"] == 3
        assert result["has_next"] is True
        assert result["has_prev"] is False

    async def test_list_project_documents_filter_by_type(
        self, client: AsyncClient, test_project, test_user, db_session
    ):
        """Test filtering documents by type."""
        # Create mixed document types
        for doc_type in ["scope", "engineering", "scope", "schedule"]:
            doc = Document(
                project_id=test_project.id,
                document_type=doc_type,
                blob_path=f"uploads/{doc_type}.pdf",
                validation_status=ValidationStatus.PENDING,
                created_by_id=test_user.id,
            )
            db_session.add(doc)
        db_session.commit()

        response = await client.get(
            f"/api/v1/documents/projects/{test_project.id}/documents",
            params={"document_type": "scope"},
        )

        assert response.status_code == 200
        result = response.json()

        assert result["total"] == 2
        assert all(item["document_type"] == "scope" for item in result["items"])


@pytest.mark.asyncio
class TestDocumentDeletion:
    """Test document deletion endpoint."""

    async def test_delete_document_success(self, client: AsyncClient, test_document, db_session):
        """Test successful document deletion."""
        document_id = test_document.id

        response = await client.delete(f"/api/v1/documents/{document_id}")

        assert response.status_code == 204

        # Verify document deleted from database
        deleted = db_session.execute(
            select(Document).where(Document.id == document_id)
        ).scalar_one_or_none()

        assert deleted is None

    async def test_delete_document_creates_audit_log(
        self, client: AsyncClient, test_document, test_project, test_user, db_session
    ):
        """Test audit log created on deletion."""
        await client.delete(f"/api/v1/documents/{test_document.id}")

        # Verify audit log
        audit = db_session.execute(
            select(AuditLog).where(
                AuditLog.project_id == test_project.id, AuditLog.action == "document_deleted"
            )
        ).scalar_one()

        assert audit.user_id == test_user.id
