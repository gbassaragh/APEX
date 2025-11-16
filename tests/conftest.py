"""
Pytest configuration and shared fixtures for APEX tests.

Provides:
- Test database (SQLite in-memory)
- Test HTTP client
- Mock Azure services
- Test user/project/document fixtures
"""
import os

# CRITICAL: Set test environment variables BEFORE any apex modules are imported
# This prevents Config validation errors during test collection
os.environ["TESTING"] = "true"  # Signal test mode to connection.py
os.environ.setdefault("AZURE_SQL_SERVER", "test-server.database.windows.net")
os.environ.setdefault("AZURE_SQL_DATABASE", "test-db")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test-openai.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT", "test-gpt4")
os.environ.setdefault("AZURE_DI_ENDPOINT", "https://test-di.cognitiveservices.azure.com/")
os.environ.setdefault("AZURE_STORAGE_ACCOUNT", "teststorageaccount")
os.environ.setdefault("AZURE_AD_TENANT_ID", "00000000-0000-0000-0000-000000000000")
os.environ.setdefault("AZURE_AD_CLIENT_ID", "00000000-0000-0000-0000-000000000000")

from typing import Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apex.dependencies import (
    get_blob_storage,
    get_current_user,
    get_db,
    get_document_parser,
    get_llm_orchestrator,
    security,
)
from apex.main import app
from apex.models.database import AppRole, Base, Document, Project, ProjectAccess, User
from apex.models.enums import ProjectStatus, ValidationStatus
from tests.fixtures.azure_mocks import (
    MockBlobStorageClient,
    MockDocumentParser,
    MockLLMOrchestrator,
)

# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def db_engine():
    """
    Create in-memory SQLite database engine for testing.

    Uses StaticPool to prevent connection issues with in-memory databases.
    Each test gets a fresh database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """
    Create database session for testing.

    Automatically rolls back transactions after each test.
    Seeds AppRole table with standard roles for all tests.
    """
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()

    # Seed AppRole table with standard roles for testing
    roles = [
        AppRole(id=1, role_name="Estimator"),
        AppRole(id=2, role_name="Manager"),
        AppRole(id=3, role_name="Auditor"),
    ]
    for role in roles:
        session.add(role)
    session.commit()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ============================================================================
# Mock Azure Services
# ============================================================================


@pytest.fixture(scope="function")
def mock_blob_storage():
    """Mock Azure Blob Storage client."""
    return MockBlobStorageClient()


@pytest.fixture(scope="function")
def mock_document_parser():
    """Mock Azure Document Intelligence parser."""
    return MockDocumentParser()


@pytest.fixture(scope="function")
def mock_llm_orchestrator():
    """Mock Azure OpenAI LLM orchestrator."""
    return MockLLMOrchestrator()


# ============================================================================
# FastAPI Test Client
# ============================================================================


@pytest_asyncio.fixture(scope="function")
async def client(
    db_session: Session,
    mock_blob_storage: MockBlobStorageClient,
    mock_document_parser: MockDocumentParser,
    mock_llm_orchestrator: MockLLMOrchestrator,
    test_user: User,
):
    """
    Create async HTTP client for testing FastAPI endpoints.

    Overrides dependencies to use test database and mock Azure services.
    """
    from httpx import ASGITransport, AsyncClient

    def override_get_db():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    def override_get_current_user():
        return test_user

    def override_security():
        # Return None - get_current_user will be overridden anyway
        return None

    def override_get_blob_storage():
        return mock_blob_storage

    def override_get_document_parser():
        return mock_document_parser

    def override_get_llm_orchestrator():
        return mock_llm_orchestrator

    # Override dependencies
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[security] = override_security
    app.dependency_overrides[get_blob_storage] = override_get_blob_storage
    app.dependency_overrides[get_document_parser] = override_get_document_parser
    app.dependency_overrides[get_llm_orchestrator] = override_get_llm_orchestrator

    # Pre-populate mock blob storage with test document content
    # This ensures validation tests can download documents
    from apex.config import config

    test_pdf = b"%PDF-1.4\n%Test document content\n%%EOF"
    # Upload test documents for various test scenarios
    test_blob_paths = [
        "uploads/test-project/test_scope.pdf",  # test_document fixture
        "uploads/test_bid.pdf",  # bid document test
    ]
    for blob_path in test_blob_paths:
        await mock_blob_storage.upload_document(
            container=config.AZURE_STORAGE_CONTAINER_UPLOADS,
            blob_name=blob_path,
            data=test_pdf,
            content_type="application/pdf",
        )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as ac:
        yield ac

    # Clear overrides
    app.dependency_overrides.clear()


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """Create test user."""
    user = User(
        aad_object_id=str(uuid4()),
        email="test.estimator@apex.com",
        name="Test Estimator",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_project(db_session: Session, test_user: User) -> Project:
    """Create test project with user access."""
    # Create project
    project = Project(
        project_number="PROJ-TEST-001",
        project_name="Test Transmission Line Project",
        voltage_level=345,
        line_miles=25.5,
        terrain_type="rolling",
        status=ProjectStatus.DRAFT,
        created_by_id=test_user.id,
    )
    db_session.add(project)
    db_session.flush()

    # Get Manager role (seeded by db_session fixture)
    # Project creator should have Manager role
    manager_role = db_session.query(AppRole).filter_by(role_name="Manager").first()

    # Grant user access to project
    access = ProjectAccess(
        user_id=test_user.id,
        project_id=project.id,
        app_role_id=manager_role.id,
    )
    db_session.add(access)
    db_session.commit()
    db_session.refresh(project)

    return project


@pytest.fixture(scope="function")
def test_document(db_session: Session, test_project: Project, test_user: User) -> Document:
    """Create test document."""
    document = Document(
        project_id=test_project.id,
        document_type="scope",
        blob_path="uploads/test-project/test_scope.pdf",
        validation_status=ValidationStatus.PENDING,
        created_by_id=test_user.id,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document
