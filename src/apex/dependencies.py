"""
FastAPI dependency injection configuration.

CRITICAL: This module defines the session management pattern.
All database operations MUST use the get_db() dependency.
"""
import logging
from typing import Generator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from apex.config import config
from apex.database.connection import SessionLocal

logger = logging.getLogger(__name__)

# ============================================================================
# Azure AD JWT Validation
# ============================================================================

# HTTPBearer security scheme for JWT token extraction
security = HTTPBearer(
    scheme_name="Azure AD Bearer Token",
    description="Azure AD OAuth 2.0 JWT token in Authorization header",
)

# JWKS Client (singleton) for JWT signature validation
# Caches public keys from Azure AD to avoid fetching on every request
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """
    Get or create JWKS client for JWT signature validation.

    Uses module-level singleton to avoid creating new client on every request.
    Client automatically caches keys and handles key rotation.

    Returns:
        PyJWKClient instance configured for Azure AD
    """
    global _jwks_client

    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            uri=config.azure_ad_jwks_uri,
            cache_keys=True,
            max_cached_keys=10,
            cache_jwk_set=True,
            lifespan=config.AZURE_AD_JWKS_CACHE_TTL,
        )
        logger.info(
            "Initialized JWKS client for Azure AD: %s",
            config.azure_ad_jwks_uri,
        )

    return _jwks_client


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


def get_job_repo():
    """Get JobRepository instance."""
    from apex.database.repositories.job_repository import JobRepository

    return JobRepository()


def get_audit_repo():
    """Get AuditRepository instance."""
    from apex.database.repositories.audit_repository import AuditRepository

    return AuditRepository()


# Service Dependencies


def get_llm_orchestrator():
    """
    Get LLMOrchestrator instance.

    LLMOrchestrator uses lazy initialization for Azure OpenAI client.
    Client is created on first use with Managed Identity authentication.

    Returns:
        LLMOrchestrator instance (client initialized on first LLM call)
    """
    from apex.services.llm.orchestrator import LLMOrchestrator

    # LLMOrchestrator handles its own Azure OpenAI client initialization
    # Uses AsyncAzureOpenAI with Managed Identity auth (lazy pattern)
    return LLMOrchestrator()


def get_risk_analyzer():
    """Get MonteCarloRiskAnalyzer instance."""
    from apex.config import config
    from apex.services.risk_analysis import MonteCarloRiskAnalyzer

    return MonteCarloRiskAnalyzer(iterations=config.DEFAULT_MONTE_CARLO_ITERATIONS, random_seed=42)


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


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Get current authenticated user from Azure AD JWT token.

    Validates JWT token from Authorization header and returns authenticated User entity.
    Implements Just-In-Time (JIT) user provisioning - creates User on first login.

    Process:
    1. Extract Bearer token from Authorization header
    2. Validate JWT signature using Azure AD public keys (JWKS)
    3. Verify token claims (issuer, audience, expiration)
    4. Extract user identity from claims (oid, email, name)
    5. Load or create User entity in database
    6. Return authenticated User

    Args:
        credentials: HTTP Bearer credentials from Authorization header
        db: Database session (dependency injected)

    Returns:
        User: Authenticated user entity from database

    Raises:
        HTTPException: 401 Unauthorized if token is invalid/expired/missing claims
        HTTPException: 500 Internal Server Error if user creation fails

    Security:
        - JWT signature validated against Azure AD public keys
        - Issuer claim validated (prevents token forgery)
        - Audience claim validated (prevents token reuse attacks)
        - Expiration claim validated (prevents replay attacks)
        - JWKS keys cached for performance (10-minute TTL)
        - User identified by aad_object_id (immutable, unique per AAD tenant)
    """
    from apex.models.database import User

    token = credentials.credentials

    try:
        # Get signing key from JWKS endpoint (cached)
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and validate JWT
        decoded = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=config.azure_ad_audience_value,
            issuer=config.azure_ad_issuer_url,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
                "require": ["exp", "iss", "aud", "oid"],  # Required claims
            },
        )

    except ExpiredSignatureError:
        logger.warning("JWT token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except InvalidTokenError as exc:
        logger.warning("Invalid JWT token: %s", str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    except Exception as exc:
        logger.error("JWT validation error: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user identity from token claims
    aad_object_id = decoded.get("oid")  # Azure AD object ID (required)
    email = decoded.get("email") or decoded.get("preferred_username")
    name = decoded.get("name")

    if not aad_object_id:
        logger.error("JWT token missing required 'oid' claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Load or create user (Just-In-Time provisioning)
    try:
        user = db.execute(
            select(User).where(User.aad_object_id == aad_object_id)
        ).scalar_one_or_none()

        if user is None:
            # Create new user on first login
            logger.info(
                "Creating new user via JIT provisioning: aad_object_id=%s, email=%s",
                aad_object_id,
                email,
            )
            user = User(
                aad_object_id=aad_object_id,
                email=email,
                name=name,
            )
            db.add(user)
            db.flush()  # Get ID without committing (commit handled by get_db())

        else:
            # Update user info if changed in Azure AD
            updated = False
            if email and user.email != email:
                logger.info(
                    "Updating user email: %s -> %s (aad_object_id=%s)",
                    user.email,
                    email,
                    aad_object_id,
                )
                user.email = email
                updated = True

            if name and user.name != name:
                logger.info(
                    "Updating user name: %s -> %s (aad_object_id=%s)",
                    user.name,
                    name,
                    aad_object_id,
                )
                user.name = name
                updated = True

            if updated:
                db.flush()

        logger.debug(
            "Authenticated user: id=%s, aad_object_id=%s, email=%s",
            user.id,
            user.aad_object_id,
            user.email,
        )

        return user

    except Exception as exc:
        logger.error(
            "Failed to load/create user for aad_object_id=%s: %s",
            aad_object_id,
            str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication",
        )
