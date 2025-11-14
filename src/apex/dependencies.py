"""
FastAPI dependency injection configuration.

CRITICAL: This module defines the session management pattern.
All database operations MUST use the get_db() dependency.
"""
from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session
import logging

from apex.database.connection import SessionLocal

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions with proper transaction handling.

    CRITICAL PATTERN - DO NOT MODIFY WITHOUT REVIEW:
    - Opens a session at request start
    - Yields session for endpoint use
    - Commits BEFORE response is sent (allows error reporting)
    - Rolls back on error
    - Always closes the session

    This pattern ensures:
    1. One session per request
    2. Commit happens before response (errors can be reported to client)
    3. Automatic rollback on error
    4. No leaked connections

    Note: Endpoints should NOT call commit/rollback directly.
    The dependency manages the full transaction lifecycle.

    Yields:
        Database session for request scope
    """
    db = SessionLocal()
    try:
        yield db
        # Commit BEFORE response is sent so errors can be reported
        db.commit()
    except Exception as exc:
        logger.error("Database transaction failed: %s", exc)
        db.rollback()
        raise
    finally:
        db.close()


# Repository Dependencies


def get_project_repo():
    """Get ProjectRepository instance."""
    from apex.database.repositories.project_repository import ProjectRepository

    return ProjectRepository()


def get_document_repo():
    """Get DocumentRepository instance."""
    from apex.database.repositories.document_repository import DocumentRepository

    return DocumentRepository()


def get_estimate_repo():
    """Get EstimateRepository instance."""
    from apex.database.repositories.estimate_repository import EstimateRepository

    return EstimateRepository()


def get_audit_repo():
    """Get AuditRepository instance."""
    from apex.database.repositories.audit_repository import AuditRepository

    return AuditRepository()


# Service Dependencies


def get_llm_orchestrator():
    """Get LLMOrchestrator instance."""
    from apex.services.llm.orchestrator import LLMOrchestrator
    from apex.config import config

    # TODO: Initialize with actual Azure OpenAI client when ready
    return LLMOrchestrator(config=config, client=None, logger=logger)


def get_risk_analyzer():
    """Get MonteCarloRiskAnalyzer instance."""
    from apex.services.risk_analysis import MonteCarloRiskAnalyzer
    from apex.config import config

    return MonteCarloRiskAnalyzer(
        iterations=config.DEFAULT_MONTE_CARLO_ITERATIONS, random_seed=42
    )


def get_aace_classifier():
    """Get AACEClassifier instance."""
    from apex.services.aace_classifier import AACEClassifier

    return AACEClassifier()


def get_cost_db_service():
    """Get CostDatabaseService instance."""
    from apex.services.cost_database import CostDatabaseService

    return CostDatabaseService()


def get_document_parser():
    """Get DocumentParser instance."""
    from apex.services.document_parser import DocumentParser

    # TODO: Initialize with actual Azure Document Intelligence client when ready
    return DocumentParser()


def get_estimate_generator(
    project_repo=Depends(get_project_repo),
    document_repo=Depends(get_document_repo),
    estimate_repo=Depends(get_estimate_repo),
    audit_repo=Depends(get_audit_repo),
    llm_orchestrator=Depends(get_llm_orchestrator),
    risk_analyzer=Depends(get_risk_analyzer),
    aace_classifier=Depends(get_aace_classifier),
    cost_db_service=Depends(get_cost_db_service),
):
    """
    Get EstimateGenerator instance with all dependencies wired.

    This is the main orchestration service that coordinates:
    - Project and document loading
    - AACE classification
    - Cost computation
    - Monte Carlo risk analysis
    - LLM narrative generation
    - Full estimate persistence
    """
    from apex.services.estimate_generator import EstimateGenerator

    return EstimateGenerator(
        project_repo=project_repo,
        document_repo=document_repo,
        estimate_repo=estimate_repo,
        audit_repo=audit_repo,
        llm_orchestrator=llm_orchestrator,
        risk_analyzer=risk_analyzer,
        aace_classifier=aace_classifier,
        cost_db_service=cost_db_service,
    )


# Azure Service Dependencies


def get_blob_storage():
    """Get BlobStorageClient instance."""
    from apex.azure.blob_storage import BlobStorageClient

    # TODO: Initialize with actual Managed Identity credentials when ready
    return BlobStorageClient()


# Authentication & Authorization Dependencies


def get_current_user(db: Session = Depends(get_db)):
    """
    Get current authenticated user from request context.

    TODO: Implement actual Azure AD token validation:
    1. Extract Bearer token from Authorization header
    2. Validate token with Azure AD
    3. Extract user claims (aad_object_id, email)
    4. Load or create User entity from database
    5. Return User entity

    For now, this returns a stub user for development/testing.
    DO NOT deploy to production without implementing actual auth.
    """
    from apex.models.database import User
    import uuid

    # STUB: Return test user for development
    # This is a placeholder until Azure AD integration is implemented
    logger.warning("Using stub user - implement Azure AD auth before production")

    # Check if test user exists, create if not
    test_user = (
        db.query(User)
        .filter(User.email == "test@example.com")
        .one_or_none()
    )

    if not test_user:
        test_user = User(
            id=uuid.uuid4(),
            aad_object_id="00000000-0000-0000-0000-000000000000",
            email="test@example.com",
            name="Test User",
        )
        db.add(test_user)
        db.flush()

    return test_user
