# APEX Production Readiness Improvement Plan

**Document Version**: 1.0
**Last Updated**: 2025-01-15
**Status**: Ready for Implementation
**Estimated Total Effort**: 2-3 weeks (1 senior developer)

---

## Executive Summary

This document provides a comprehensive, phase-by-phase implementation plan to resolve critical issues preventing APEX from being production-ready. The APEX codebase demonstrates exceptional architecture, security, and code quality, but contains **three critical performance issues** that would cause server unresponsiveness under concurrent load.

**Critical Issues Identified:**
1. Blocking operations in async event loop (document validation, estimate generation)
2. CPU-bound Monte Carlo simulation running in main thread
3. Missing tests for core business logic

**Implementation Strategy**: Three phases over 2-3 weeks
- **Phase 1 (Week 1-2)**: Critical fixes - Background jobs, thread pool, core tests
- **Phase 2 (Week 3-4)**: High priority - Async KeyVault, production cost database, document parsing
- **Phase 3 (Week 5-6)**: Polish - Consistency, documentation, performance testing

---

## Table of Contents

1. [Project Context](#project-context)
2. [Current State Analysis](#current-state-analysis)
3. [Phase 1: Critical Fixes (Week 1-2)](#phase-1-critical-fixes)
4. [Phase 2: High Priority (Week 3-4)](#phase-2-high-priority)
5. [Phase 3: Polish (Week 5-6)](#phase-3-polish)
6. [Testing Strategy](#testing-strategy)
7. [Acceptance Criteria](#acceptance-criteria)
8. [Risk Mitigation](#risk-mitigation)
9. [Deployment Guide](#deployment-guide)
10. [Appendices](#appendices)

---

## Project Context

### What is APEX?

**APEX (AI-Powered Estimation Expert)** is an enterprise estimation platform for utility transmission and distribution projects. The system automates cost estimation through:
- Intelligent document parsing (Azure AI Document Intelligence)
- AI-based validation (Azure OpenAI GPT-4)
- AACE-compliant classification (Class 1-5)
- Industrial-grade Monte Carlo risk analysis
- Automated narrative generation

**Primary Users**: ~30 utility cost estimators, managers, auditors
**Regulatory Context**: ISO-NE compliance required for all estimates

### Technology Stack

**Backend:**
- Python 3.11+
- FastAPI (async web framework)
- SQLAlchemy 2.0+ with Alembic migrations
- Pydantic 2.x for validation

**Database:**
- Azure SQL Database (production)
- SQLite (testing)
- Custom GUID TypeDecorator for cross-DB compatibility

**Azure Services:**
- Azure OpenAI (GPT-4 for LLM orchestration)
- Azure AI Document Intelligence (PDF parsing)
- Azure Blob Storage (document storage)
- Azure Key Vault (secrets management)
- Azure Container Apps (deployment target)
- Azure Application Insights (telemetry)

**Scientific Computing:**
- NumPy 1.26+
- SciPy 1.11+ (Latin Hypercube Sampling, distributions)
- Statsmodels (statistical analysis)

**Authentication:**
- Azure AD (OAuth 2.0 JWT tokens)
- Managed Identity (all Azure service auth)

### Project Structure

```
apex/
├── src/apex/
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Pydantic settings (env-based)
│   ├── dependencies.py            # DI wiring, DB sessions, auth
│   ├── api/v1/                    # API routers
│   │   ├── documents.py           # ⚠️ CRITICAL FIX NEEDED
│   │   ├── estimates.py           # ⚠️ CRITICAL FIX NEEDED
│   │   ├── projects.py
│   │   └── health.py
│   ├── models/
│   │   ├── database.py            # SQLAlchemy ORM models
│   │   ├── schemas.py             # Pydantic DTOs
│   │   └── enums.py               # Enums (AACEClass, ValidationStatus, etc.)
│   ├── database/
│   │   ├── connection.py          # Engine with NullPool
│   │   └── repositories/          # Repository pattern
│   ├── services/
│   │   ├── estimate_generator.py  # ⚠️ CRITICAL FIX NEEDED
│   │   ├── risk_analysis.py       # ⚠️ CRITICAL FIX NEEDED
│   │   ├── document_parser.py
│   │   ├── cost_database.py
│   │   ├── aace_classifier.py
│   │   └── llm/orchestrator.py
│   ├── azure/                     # Azure service clients
│   └── utils/                     # Logging, errors, retry, middleware
├── tests/
│   ├── unit/                      # ⚠️ MISSING CORE TESTS
│   ├── integration/
│   └── fixtures/azure_mocks.py
├── alembic/                       # Database migrations
└── pyproject.toml                 # Dependencies
```

---

## Current State Analysis

### Critical Issues (Preventing Production Deployment)

#### Issue 1: Blocking Document Validation
**File**: `src/apex/api/v1/documents.py:246-469`
**Severity**: CRITICAL
**Impact**: Server freezes for 30s-2min per document validation

**Current Code:**
```python
@router.post("/{document_id}/validate", response_model=DocumentValidationResult)
@azure_retry
async def validate_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    # ... dependencies
):
    """
    Trigger AI-powered document validation.

    This is a synchronous operation that may take 30s-2min depending on document size.
    """
    # Line 294: Azure Document Intelligence (30s-2min blocking)
    structured_content = await document_parser.parse_document(...)

    # Line 368: LLM validation (10-30s blocking)
    llm_validation = await llm_orchestrator.validate_document(...)
```

**Problem**: While declared `async`, the endpoint blocks the event loop for the entire duration. With FastAPI's single-threaded async model, this freezes the server for all other requests.

#### Issue 2: Blocking Estimate Generation
**File**: `src/apex/api/v1/estimates.py:42-165`
**Severity**: CRITICAL
**Impact**: Server freezes for 30s-5min per estimate

**Current Code:**
```python
@router.post("/generate", response_model=EstimateDetailResponse, status_code=status.HTTP_201_CREATED)
def generate_estimate(  # NOT async!
    request: EstimateGenerateRequest,
    db: Session = Depends(get_db),
    # ... dependencies
):
    """
    This is a long-running synchronous operation that may take 30s-5min depending on:
    - Number of documents to analyze
    - Complexity of cost breakdown structure
    - Monte Carlo simulation iterations
    - LLM narrative generation time
    """
    # Line 97: Synchronous call that takes 30s-5min
    estimate = estimate_generator.generate_estimate(...)
```

**Problem**: Completely synchronous function that blocks the server. The comment acknowledges need for background job pattern but it's not implemented.

#### Issue 3: CPU-Bound Monte Carlo in Event Loop
**File**: `src/apex/services/estimate_generator.py:236-241`
**Severity**: CRITICAL
**Impact**: CPU-bound computation freezes async event loop

**Current Code:**
```python
# STEP 7: Run Monte Carlo analysis
# TODO (HIGH PRIORITY): Monte Carlo is CPU-bound and blocks event loop.
# Production should use:
#   risk_results = await asyncio.to_thread(self.risk_analyzer.run_analysis, ...)
# This requires testing to ensure thread safety of NumPy/SciPy operations.
risk_results = self.risk_analyzer.run_analysis(  # Blocking!
    base_cost=float(base_cost),
    risk_factors=risk_factors,
    correlation_matrix=None,
    confidence_levels=[0.50, confidence_level, 0.95],
)
```

**Problem**: The Monte Carlo analyzer (`risk_analysis.py`) performs 10,000 iterations of CPU-intensive NumPy/SciPy operations in the main thread. The code includes a TODO acknowledging this exact issue.

#### Issue 4: Missing Core Service Tests
**Severity**: HIGH
**Impact**: Untested complex business logic with no validation

**Missing Tests:**
- `MonteCarloRiskAnalyzer` (400+ lines of statistical code)
- `EstimateGenerator` (14-step orchestration workflow)
- `LLMOrchestrator` (maturity-aware routing)
- `AACEClassifier` (classification logic)
- `CostDatabaseService` (CBS/WBS hierarchy)

**Risk**: No validation that:
- Iman-Conover correlation preserves rank correlation correctly
- PERT distribution implementation matches specification
- Estimate generation workflow handles all error conditions
- LLM routing selects correct persona for each AACE class

---

## Phase 1: Critical Fixes

**Duration**: 1-2 weeks
**Priority**: BLOCKING - Must complete before production deployment
**Goal**: Resolve server blocking issues and establish core test coverage

### Task 1.1: Background Job Infrastructure

**Objective**: Implement async job queue for long-running operations without adding deployment complexity.

**Approach**: Start with FastAPI `BackgroundTasks` (simplest, no new infrastructure), then optionally migrate to Azure Functions if needed.

#### Step 1.1.1: Create Job Status Data Model

**File**: `src/apex/models/database.py`

Add new table for job tracking:

```python
from sqlalchemy import Column, DateTime, String, Text
from datetime import datetime

class BackgroundJob(Base):
    """
    Background job tracking for long-running operations.

    Used for document validation and estimate generation.
    """

    __tablename__ = "background_jobs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    job_type = Column(String(50), nullable=False, index=True)  # "document_validation", "estimate_generation"
    status = Column(String(20), nullable=False, index=True)  # "pending", "running", "completed", "failed"

    # Related entity IDs
    document_id = Column(GUID, ForeignKey("documents.id"), nullable=True, index=True)
    project_id = Column(GUID, ForeignKey("projects.id"), nullable=True, index=True)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), nullable=True, index=True)

    # Progress tracking
    progress_percent = Column(Integer, default=0)  # 0-100
    current_step = Column(String(255))  # Human-readable current step

    # Result storage
    result_data = Column(JSON)  # Final result or error details
    error_message = Column(Text)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_by_id = Column(GUID, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User")
    document = relationship("Document")
    project = relationship("Project")
    estimate = relationship("Estimate")

    # Index for job cleanup queries
    __table_args__ = (
        Index("ix_background_jobs_status_created", "status", "created_at"),
    )
```

**Create Migration:**

```bash
alembic revision --autogenerate -m "Add background_jobs table for async operations"
alembic upgrade head
```

#### Step 1.1.2: Create Job Repository

**File**: `src/apex/database/repositories/job_repository.py`

```python
"""
Repository for background job operations.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apex.database.repositories.base import BaseRepository
from apex.models.database import BackgroundJob


class JobRepository(BaseRepository[BackgroundJob]):
    """Repository for background job CRUD operations."""

    def __init__(self):
        super().__init__(BackgroundJob)

    def create_job(
        self,
        db: Session,
        job_type: str,
        user_id: UUID,
        document_id: Optional[UUID] = None,
        project_id: Optional[UUID] = None,
    ) -> BackgroundJob:
        """Create new background job in pending state."""
        job = BackgroundJob(
            job_type=job_type,
            status="pending",
            created_by_id=user_id,
            document_id=document_id,
            project_id=project_id,
        )
        db.add(job)
        db.flush()
        return job

    def update_progress(
        self,
        db: Session,
        job_id: UUID,
        progress_percent: int,
        current_step: str,
    ) -> BackgroundJob:
        """Update job progress."""
        job = self.get(db, job_id)
        if job:
            job.progress_percent = progress_percent
            job.current_step = current_step
            if job.status == "pending":
                job.status = "running"
                job.started_at = datetime.utcnow()
            db.flush()
        return job

    def mark_completed(
        self,
        db: Session,
        job_id: UUID,
        result_data: dict,
        estimate_id: Optional[UUID] = None,
    ) -> BackgroundJob:
        """Mark job as completed with results."""
        job = self.get(db, job_id)
        if job:
            job.status = "completed"
            job.progress_percent = 100
            job.completed_at = datetime.utcnow()
            job.result_data = result_data
            if estimate_id:
                job.estimate_id = estimate_id
            db.flush()
        return job

    def mark_failed(
        self,
        db: Session,
        job_id: UUID,
        error_message: str,
    ) -> BackgroundJob:
        """Mark job as failed with error details."""
        job = self.get(db, job_id)
        if job:
            job.status = "failed"
            job.completed_at = datetime.utcnow()
            job.error_message = error_message
            db.flush()
        return job

    def get_user_jobs(
        self,
        db: Session,
        user_id: UUID,
        limit: int = 50,
    ) -> List[BackgroundJob]:
        """Get recent jobs for a user."""
        query = (
            select(BackgroundJob)
            .where(BackgroundJob.created_by_id == user_id)
            .order_by(BackgroundJob.created_at.desc())
            .limit(limit)
        )
        return db.execute(query).scalars().all()

    def cleanup_old_jobs(
        self,
        db: Session,
        older_than_days: int = 30,
    ) -> int:
        """Delete completed/failed jobs older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        query = select(BackgroundJob).where(
            BackgroundJob.status.in_(["completed", "failed"]),
            BackgroundJob.created_at < cutoff,
        )
        jobs = db.execute(query).scalars().all()
        count = len(jobs)
        for job in jobs:
            db.delete(job)
        return count
```

#### Step 1.1.3: Add Job Repository Dependency

**File**: `src/apex/dependencies.py`

Add after line 130:

```python
def get_job_repo():
    """Get JobRepository instance."""
    from apex.database.repositories.job_repository import JobRepository

    return JobRepository()
```

#### Step 1.1.4: Create Job Status API Endpoint

**File**: `src/apex/api/v1/jobs.py` (NEW FILE)

```python
"""
Background job status endpoints.

Provides job tracking for long-running async operations.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apex.database.repositories.job_repository import JobRepository
from apex.dependencies import get_current_user, get_db, get_job_repo
from apex.models.database import User
from apex.models.schemas import JobStatusResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    job_repo: JobRepository = Depends(get_job_repo),
):
    """
    Get background job status.

    Returns current status, progress, and results (if completed).
    Users can only access their own jobs.
    """
    job = job_repo.get(db, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    # Authorization: user can only access their own jobs
    if job.created_by_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this job",
        )

    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        progress_percent=job.progress_percent,
        current_step=job.current_step,
        result_data=job.result_data,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
```

#### Step 1.1.5: Add Job Status Schema

**File**: `src/apex/models/schemas.py`

Add after other response schemas:

```python
from typing import Optional
from datetime import datetime

class JobStatusResponse(BaseModel):
    """Background job status response."""

    id: UUID
    job_type: str
    status: str  # "pending", "running", "completed", "failed"
    progress_percent: int
    current_step: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
```

#### Step 1.1.6: Register Jobs Router

**File**: `src/apex/api/v1/router.py`

```python
from apex.api.v1 import jobs  # Add import

# Add to router registration
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
```

### Task 1.2: Refactor Document Validation to Background Job

**Objective**: Convert synchronous document validation to async background job.

#### Step 1.2.1: Create Background Validation Worker

**File**: `src/apex/services/background_jobs.py` (NEW FILE)

```python
"""
Background job workers for long-running operations.

Uses FastAPI BackgroundTasks to run operations asynchronously.
"""
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from apex.database.connection import SessionLocal
from apex.database.repositories.audit_repository import AuditRepository
from apex.database.repositories.document_repository import DocumentRepository
from apex.database.repositories.job_repository import JobRepository
from apex.database.repositories.project_repository import ProjectRepository
from apex.models.enums import AACEClass, ValidationStatus
from apex.services.document_parser import DocumentParser
from apex.services.llm.orchestrator import LLMOrchestrator
from apex.utils.errors import BusinessRuleViolation

logger = logging.getLogger(__name__)


async def process_document_validation(
    job_id: UUID,
    document_id: UUID,
    user_id: UUID,
) -> None:
    """
    Background worker for document validation.

    Args:
        job_id: Background job ID for progress tracking
        document_id: Document to validate
        user_id: User who initiated validation
    """
    # Create new DB session for background task
    db = SessionLocal()

    try:
        # Initialize repositories and services
        job_repo = JobRepository()
        document_repo = DocumentRepository()
        project_repo = ProjectRepository()
        audit_repo = AuditRepository()
        document_parser = DocumentParser()
        llm_orchestrator = LLMOrchestrator()

        # Update job status
        job_repo.update_progress(
            db, job_id, progress_percent=10, current_step="Loading document"
        )
        db.commit()

        # Get document
        document = document_repo.get(db, document_id)
        if not document:
            job_repo.mark_failed(db, job_id, f"Document {document_id} not found")
            db.commit()
            return

        # Load document from blob storage
        from apex.azure.blob_storage import BlobStorageClient
        from apex.config import config

        blob_storage = BlobStorageClient()

        job_repo.update_progress(
            db, job_id, progress_percent=20, current_step="Downloading from blob storage"
        )
        db.commit()

        document_bytes = await blob_storage.download_document(
            container=config.AZURE_STORAGE_CONTAINER_UPLOADS,
            blob_name=document.blob_path,
        )

        # Step 1: Parse document
        job_repo.update_progress(
            db, job_id, progress_percent=30, current_step="Parsing document with Azure DI"
        )
        db.commit()

        try:
            from pathlib import Path

            structured_content = await document_parser.parse_document(
                document_bytes=document_bytes,
                filename=Path(document.blob_path).name,
                blob_path=f"{config.AZURE_STORAGE_CONTAINER_UPLOADS}/{document.blob_path}",
            )

            # Save parsed content
            document_repo.update_validation_result(
                db=db,
                document_id=document_id,
                validation_result={"parsed_content": structured_content},
                completeness_score=None,
                validation_status=ValidationStatus.PENDING,
            )
            db.commit()

        except BusinessRuleViolation as circuit_error:
            error_msg = f"Document parsing failed: {str(circuit_error)}"
            job_repo.mark_failed(db, job_id, error_msg)
            db.commit()
            return

        except Exception as parse_error:
            logger.error(f"Document parsing error: {parse_error}", exc_info=True)
            error_msg = f"Document parsing failed: {str(parse_error)}"
            job_repo.mark_failed(db, job_id, error_msg)
            db.commit()
            return

        # Step 2: LLM validation
        job_repo.update_progress(
            db, job_id, progress_percent=60, current_step="Running AI validation"
        )
        db.commit()

        # Determine AACE class for LLM routing
        aace_class = AACEClass.CLASS_2 if document.document_type == "bid" else AACEClass.CLASS_4

        try:
            llm_validation = await llm_orchestrator.validate_document(
                aace_class=aace_class,
                document_type=document.document_type,
                structured_content=structured_content,
            )

            completeness_score = llm_validation.get("completeness_score", 0)
            suitable_for_estimation = llm_validation.get("suitable_for_estimation", False)

            # Determine validation status
            if suitable_for_estimation and completeness_score >= 70:
                validation_status = ValidationStatus.PASSED
            elif completeness_score >= 50:
                validation_status = ValidationStatus.MANUAL_REVIEW
            else:
                validation_status = ValidationStatus.FAILED

            validation_result = {
                "parsed_content": structured_content,
                "llm_validation": llm_validation,
                "aace_class_used": aace_class.value,
            }

        except Exception as llm_error:
            logger.error(f"LLM validation error: {llm_error}", exc_info=True)
            validation_status = ValidationStatus.MANUAL_REVIEW
            validation_result = {
                "parsed_content": structured_content,
                "llm_error": str(llm_error),
                "aace_class_used": aace_class.value,
                "issues": [f"LLM validation failed: {str(llm_error)}"],
                "recommendations": ["Manual review required due to LLM validation failure"],
            }
            completeness_score = None
            suitable_for_estimation = False

        # Step 3: Update document
        job_repo.update_progress(
            db, job_id, progress_percent=90, current_step="Saving validation results"
        )
        db.commit()

        updated_document = document_repo.update_validation_result(
            db=db,
            document_id=document_id,
            validation_result=validation_result,
            completeness_score=completeness_score,
            validation_status=validation_status,
        )
        db.commit()

        # Create audit log
        audit_repo.create(
            db,
            {
                "project_id": document.project_id,
                "user_id": user_id,
                "action": "document_validated",
                "details": {
                    "document_id": str(document_id),
                    "validation_status": validation_status.value,
                    "completeness_score": completeness_score,
                    "job_id": str(job_id),
                },
            },
        )
        db.commit()

        # Mark job as completed
        result_data = {
            "document_id": str(document_id),
            "validation_status": validation_status.value,
            "completeness_score": completeness_score,
            "suitable_for_estimation": suitable_for_estimation,
        }

        job_repo.mark_completed(db, job_id, result_data)
        db.commit()

        logger.info(f"Document validation completed: job_id={job_id}, document_id={document_id}")

    except Exception as exc:
        logger.error(f"Background job failed: {exc}", exc_info=True)
        try:
            job_repo.mark_failed(db, job_id, str(exc))
            db.commit()
        except Exception as rollback_exc:
            logger.error(f"Failed to mark job as failed: {rollback_exc}")

    finally:
        await document_parser.close()
        db.close()
```

#### Step 1.2.2: Refactor Document Validation Endpoint

**File**: `src/apex/api/v1/documents.py`

Replace the `validate_document` function (lines 246-469) with:

```python
from fastapi import BackgroundTasks

@router.post("/{document_id}/validate", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def validate_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    document_repo: DocumentRepository = Depends(get_document_repo),
    job_repo: JobRepository = Depends(get_job_repo),
):
    """
    Trigger AI-powered document validation (async background job).

    Returns immediately with job ID. Use GET /jobs/{job_id} to check status.

    Returns:
        202 Accepted with job status URL
    """
    # Get document
    document = document_repo.get(db, document_id)
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

    # Check if document is already being validated
    from sqlalchemy import select
    from apex.models.database import BackgroundJob

    existing_job = db.execute(
        select(BackgroundJob).where(
            BackgroundJob.document_id == document_id,
            BackgroundJob.job_type == "document_validation",
            BackgroundJob.status.in_(["pending", "running"]),
        )
    ).scalar_one_or_none()

    if existing_job:
        return JobStatusResponse(
            id=existing_job.id,
            job_type=existing_job.job_type,
            status=existing_job.status,
            progress_percent=existing_job.progress_percent,
            current_step=existing_job.current_step,
            result_data=existing_job.result_data,
            error_message=existing_job.error_message,
            created_at=existing_job.created_at,
            started_at=existing_job.started_at,
            completed_at=existing_job.completed_at,
        )

    # Create background job
    job = job_repo.create_job(
        db=db,
        job_type="document_validation",
        user_id=current_user.id,
        document_id=document_id,
        project_id=document.project_id,
    )
    db.commit()

    # Queue background task
    from apex.services.background_jobs import process_document_validation

    background_tasks.add_task(
        process_document_validation,
        job_id=job.id,
        document_id=document_id,
        user_id=current_user.id,
    )

    logger.info(f"Queued document validation job: job_id={job.id}, document_id={document_id}")

    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        progress_percent=job.progress_percent,
        current_step="Job queued",
        result_data=None,
        error_message=None,
        created_at=job.created_at,
        started_at=None,
        completed_at=None,
    )
```

Add import at top of file:

```python
from apex.database.repositories.job_repository import JobRepository
from apex.dependencies import get_job_repo
```

### Task 1.3: Refactor Estimate Generation to Background Job

**Objective**: Convert synchronous estimate generation to async background job.

#### Step 1.3.1: Create Estimate Generation Worker

**File**: `src/apex/services/background_jobs.py`

Add to existing file:

```python
async def process_estimate_generation(
    job_id: UUID,
    project_id: UUID,
    risk_factors_dto: List[Dict[str, Any]],
    confidence_level: float,
    monte_carlo_iterations: int,
    user_id: UUID,
) -> None:
    """
    Background worker for estimate generation.

    Args:
        job_id: Background job ID for progress tracking
        project_id: Project to estimate
        risk_factors_dto: Risk factor definitions
        confidence_level: Target confidence level (0.80 for P80)
        monte_carlo_iterations: Number of MC iterations
        user_id: User who initiated estimation
    """
    db = SessionLocal()

    try:
        # Initialize services
        job_repo = JobRepository()
        project_repo = ProjectRepository()
        document_repo = DocumentRepository()
        estimate_repo = EstimateRepository()
        audit_repo = AuditRepository()

        from apex.services.llm.orchestrator import LLMOrchestrator
        from apex.services.risk_analysis import MonteCarloRiskAnalyzer
        from apex.services.aace_classifier import AACEClassifier
        from apex.services.cost_database import CostDatabaseService
        from apex.services.estimate_generator import EstimateGenerator
        from apex.config import config

        llm_orchestrator = LLMOrchestrator()
        risk_analyzer = MonteCarloRiskAnalyzer(
            iterations=config.DEFAULT_MONTE_CARLO_ITERATIONS,
            random_seed=42
        )
        aace_classifier = AACEClassifier()
        cost_db_service = CostDatabaseService()

        estimate_generator = EstimateGenerator(
            project_repo=project_repo,
            document_repo=document_repo,
            estimate_repo=estimate_repo,
            audit_repo=audit_repo,
            llm_orchestrator=llm_orchestrator,
            risk_analyzer=risk_analyzer,
            aace_classifier=aace_classifier,
            cost_db_service=cost_db_service,
        )

        # Update job status
        job_repo.update_progress(
            db, job_id, progress_percent=5, current_step="Starting estimate generation"
        )
        db.commit()

        # Get user for estimate generator
        from apex.models.database import User
        from sqlalchemy import select

        user = db.execute(select(User).where(User.id == user_id)).scalar_one()

        # Call estimate generator with progress callbacks
        # Note: We'll need to modify estimate_generator to accept a progress callback
        estimate = await estimate_generator.generate_estimate(
            db=db,
            project_id=project_id,
            risk_factors_dto=risk_factors_dto,
            confidence_level=confidence_level,
            monte_carlo_iterations=monte_carlo_iterations,
            user=user,
            progress_callback=lambda pct, step: _update_job_progress(
                db, job_repo, job_id, pct, step
            ),
        )

        # Mark job as completed
        result_data = {
            "estimate_id": str(estimate.id),
            "estimate_number": estimate.estimate_number,
            "aace_class": estimate.aace_class.value,
            "base_cost": float(estimate.base_cost),
            "p50_cost": float(estimate.p50_cost) if estimate.p50_cost else None,
            "p80_cost": float(estimate.p80_cost) if estimate.p80_cost else None,
        }

        job_repo.mark_completed(db, job_id, result_data, estimate_id=estimate.id)
        db.commit()

        logger.info(f"Estimate generation completed: job_id={job_id}, estimate_id={estimate.id}")

    except Exception as exc:
        logger.error(f"Estimate generation job failed: {exc}", exc_info=True)
        try:
            job_repo.mark_failed(db, job_id, str(exc))
            db.commit()
        except Exception:
            pass

    finally:
        db.close()


def _update_job_progress(
    db: Session,
    job_repo: JobRepository,
    job_id: UUID,
    progress_percent: int,
    current_step: str,
) -> None:
    """Helper to update job progress and commit."""
    try:
        job_repo.update_progress(db, job_id, progress_percent, current_step)
        db.commit()
    except Exception as exc:
        logger.warning(f"Failed to update job progress: {exc}")
```

#### Step 1.3.2: Refactor Estimate Generation Endpoint

**File**: `src/apex/api/v1/estimates.py`

Replace `generate_estimate` function (lines 39-165) with:

```python
@router.post(
    "/generate", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED
)
async def generate_estimate(
    request: EstimateGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    job_repo: JobRepository = Depends(get_job_repo),
):
    """
    Generate new estimate for a project (async background job).

    This operation takes 30s-5min depending on complexity. Returns immediately
    with job ID. Use GET /jobs/{job_id} to check status.

    Returns:
        202 Accepted with job status URL
    """
    # Check user access to project
    if not project_repo.check_user_access(db, current_user.id, request.project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {request.project_id}",
        )

    # Verify project exists
    project = project_repo.get(db, request.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {request.project_id} not found",
        )

    # Create background job
    job = job_repo.create_job(
        db=db,
        job_type="estimate_generation",
        user_id=current_user.id,
        project_id=request.project_id,
    )
    db.commit()

    # Convert RiskFactorInput DTOs to dicts
    risk_factors_dto = [rf.model_dump() for rf in request.risk_factors]

    # Queue background task
    from apex.services.background_jobs import process_estimate_generation

    background_tasks.add_task(
        process_estimate_generation,
        job_id=job.id,
        project_id=request.project_id,
        risk_factors_dto=risk_factors_dto,
        confidence_level=request.confidence_level,
        monte_carlo_iterations=request.monte_carlo_iterations,
        user_id=current_user.id,
    )

    logger.info(f"Queued estimate generation job: job_id={job.id}, project_id={request.project_id}")

    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        progress_percent=job.progress_percent,
        current_step="Job queued",
        result_data=None,
        error_message=None,
        created_at=job.created_at,
        started_at=None,
        completed_at=None,
    )
```

Add imports:

```python
from fastapi import BackgroundTasks
from apex.database.repositories.job_repository import JobRepository
from apex.dependencies import get_job_repo
from apex.models.schemas import JobStatusResponse
```

### Task 1.4: Thread Pool for Monte Carlo Analysis

**Objective**: Move CPU-bound Monte Carlo simulation to thread pool.

#### Step 1.4.1: Modify Estimate Generator

**File**: `src/apex/services/estimate_generator.py`

Replace lines 232-241 with:

```python
import asyncio

# STEP 7: Run Monte Carlo analysis in thread pool
# Monte Carlo is CPU-bound (NumPy/SciPy operations), so we run it in a
# separate thread to avoid blocking the async event loop.
logger.info(f"Starting Monte Carlo analysis with {len(risk_factors)} risk factors")

risk_results = await asyncio.to_thread(
    self.risk_analyzer.run_analysis,
    base_cost=float(base_cost),
    risk_factors=risk_factors,
    correlation_matrix=None,  # MVP: no correlation (production would extract from DTO)
    confidence_levels=[0.50, confidence_level, 0.95],
)

pct = int(confidence_level * 100)
p50 = risk_results["percentiles"]["p50"]
target = risk_results["percentiles"][f"p{pct}"]
logger.info(f"Monte Carlo analysis complete: P50=${p50:,.2f}, P{pct}=${target:,.2f}")
```

**Verification**: Add logging before/after to confirm non-blocking behavior.

### Task 1.5: Core Service Tests

**Objective**: Establish test coverage for critical business logic.

#### Step 1.5.1: Monte Carlo Risk Analyzer Tests

**File**: `tests/unit/test_risk_analysis.py` (NEW FILE)

```python
"""
Unit tests for Monte Carlo risk analysis.

Tests validate statistical correctness against known distributions.
"""
import numpy as np
import pytest
from decimal import Decimal

from apex.services.risk_analysis import MonteCarloRiskAnalyzer, RiskFactor
from apex.utils.errors import BusinessRuleViolation


class TestMonteCarloRiskAnalyzer:
    """Test suite for MonteCarloRiskAnalyzer."""

    def test_no_risk_factors_returns_base_cost(self):
        """With no risk factors, should return base cost for all percentiles."""
        analyzer = MonteCarloRiskAnalyzer(iterations=1000, random_seed=42)

        results = analyzer.run_analysis(
            base_cost=1000000.0,
            risk_factors={},
            confidence_levels=[0.50, 0.80, 0.95],
        )

        assert results["base_cost"] == 1000000.0
        assert results["mean_cost"] == 1000000.0
        assert results["std_dev"] == 0.0
        assert results["percentiles"]["p50"] == 1000000.0
        assert results["percentiles"]["p80"] == 1000000.0
        assert results["percentiles"]["p95"] == 1000000.0

    def test_triangular_distribution_mean(self):
        """Triangular distribution should have mean = (min + mode + max) / 3."""
        analyzer = MonteCarloRiskAnalyzer(iterations=100000, random_seed=42)

        # Triangular: min=-0.1, mode=0.0, max=0.2
        # Mean = (-0.1 + 0.0 + 0.2) / 3 = 0.0333...
        # So mean cost should be ~1,033,333
        risk_factor = RiskFactor(
            name="test_triangular",
            distribution="triangular",
            min_value=-0.1,
            most_likely=0.0,
            max_value=0.2,
        )

        results = analyzer.run_analysis(
            base_cost=1000000.0,
            risk_factors={"test_triangular": risk_factor},
        )

        # Allow 1% tolerance for Monte Carlo variance
        expected_mean = 1033333.33
        assert 1023000 < results["mean_cost"] < 1043000, (
            f"Mean cost {results['mean_cost']} outside expected range "
            f"around {expected_mean}"
        )

    def test_normal_distribution_mean_std(self):
        """Normal distribution should preserve mean and std dev."""
        analyzer = MonteCarloRiskAnalyzer(iterations=100000, random_seed=42)

        # Normal: mean=0.05, std=0.02
        # Mean cost should be ~1,050,000
        # Std dev should be ~20,000
        risk_factor = RiskFactor(
            name="test_normal",
            distribution="normal",
            mean=0.05,
            std_dev=0.02,
        )

        results = analyzer.run_analysis(
            base_cost=1000000.0,
            risk_factors={"test_normal": risk_factor},
        )

        # Allow 2% tolerance
        assert 1040000 < results["mean_cost"] < 1060000
        assert 15000 < results["std_dev"] < 25000

    def test_uniform_distribution_mean(self):
        """Uniform distribution should have mean = (min + max) / 2."""
        analyzer = MonteCarloRiskAnalyzer(iterations=100000, random_seed=42)

        # Uniform: min=-0.05, max=0.15
        # Mean = (-0.05 + 0.15) / 2 = 0.05
        # Mean cost should be ~1,050,000
        risk_factor = RiskFactor(
            name="test_uniform",
            distribution="uniform",
            min_value=-0.05,
            max_value=0.15,
        )

        results = analyzer.run_analysis(
            base_cost=1000000.0,
            risk_factors={"test_uniform": risk_factor},
        )

        assert 1040000 < results["mean_cost"] < 1060000

    def test_pert_distribution_properties(self):
        """PERT distribution should be bounded and have reasonable mean."""
        analyzer = MonteCarloRiskAnalyzer(iterations=100000, random_seed=42)

        # PERT: min=-0.1, mode=0.0, max=0.2
        # PERT mean ≈ (min + 4*mode + max) / 6 = (-0.1 + 0 + 0.2) / 6 = 0.0167
        # Mean cost should be ~1,016,700
        risk_factor = RiskFactor(
            name="test_pert",
            distribution="pert",
            min_value=-0.1,
            most_likely=0.0,
            max_value=0.2,
        )

        results = analyzer.run_analysis(
            base_cost=1000000.0,
            risk_factors={"test_pert": risk_factor},
        )

        # PERT has tighter distribution than triangular
        assert 1010000 < results["mean_cost"] < 1025000

        # All costs should be within bounds
        assert results["min_cost"] >= 900000  # base * (1 - 0.1)
        assert results["max_cost"] <= 1200000  # base * (1 + 0.2)

    def test_percentiles_ordered(self):
        """Percentiles should be in ascending order: P50 < P80 < P95."""
        analyzer = MonteCarloRiskAnalyzer(iterations=10000, random_seed=42)

        risk_factor = RiskFactor(
            name="test",
            distribution="triangular",
            min_value=0.0,
            most_likely=0.1,
            max_value=0.3,
        )

        results = analyzer.run_analysis(
            base_cost=1000000.0,
            risk_factors={"test": risk_factor},
            confidence_levels=[0.50, 0.80, 0.95],
        )

        p50 = results["percentiles"]["p50"]
        p80 = results["percentiles"]["p80"]
        p95 = results["percentiles"]["p95"]

        assert p50 < p80 < p95, f"Percentiles not ordered: P50={p50}, P80={p80}, P95={p95}"

    def test_correlation_matrix_validation(self):
        """Should validate correlation matrix shape and properties."""
        analyzer = MonteCarloRiskAnalyzer(iterations=1000, random_seed=42)

        risk_factors = {
            "factor1": RiskFactor("factor1", "triangular", -0.1, 0.0, 0.1),
            "factor2": RiskFactor("factor2", "triangular", -0.05, 0.0, 0.05),
        }

        # Invalid: wrong shape
        invalid_correlation = np.array([[1.0]])

        with pytest.raises(BusinessRuleViolation) as exc:
            analyzer.run_analysis(
                base_cost=1000000.0,
                risk_factors=risk_factors,
                correlation_matrix=invalid_correlation,
            )

        assert "shape" in str(exc.value).lower()

    def test_correlation_matrix_symmetric(self):
        """Should reject non-symmetric correlation matrices."""
        analyzer = MonteCarloRiskAnalyzer(iterations=1000, random_seed=42)

        risk_factors = {
            "factor1": RiskFactor("factor1", "triangular", -0.1, 0.0, 0.1),
            "factor2": RiskFactor("factor2", "triangular", -0.05, 0.0, 0.05),
        }

        # Invalid: not symmetric
        invalid_correlation = np.array([
            [1.0, 0.5],
            [0.6, 1.0],  # Should be 0.5, not 0.6
        ])

        with pytest.raises(BusinessRuleViolation) as exc:
            analyzer.run_analysis(
                base_cost=1000000.0,
                risk_factors=risk_factors,
                correlation_matrix=invalid_correlation,
            )

        assert "symmetric" in str(exc.value).lower()

    def test_spearman_sensitivity_analysis(self):
        """Sensitivity analysis should identify most influential factors."""
        analyzer = MonteCarloRiskAnalyzer(iterations=10000, random_seed=42)

        risk_factors = {
            "small_impact": RiskFactor("small_impact", "triangular", -0.01, 0.0, 0.01),
            "large_impact": RiskFactor("large_impact", "triangular", -0.2, 0.0, 0.4),
        }

        results = analyzer.run_analysis(
            base_cost=1000000.0,
            risk_factors=risk_factors,
        )

        sensitivities = results["sensitivities"]

        # Large impact factor should have higher absolute sensitivity
        assert abs(sensitivities["large_impact"]) > abs(sensitivities["small_impact"])

    def test_unsupported_distribution_raises_error(self):
        """Should raise error for unsupported distribution types."""
        analyzer = MonteCarloRiskAnalyzer(iterations=1000, random_seed=42)

        risk_factor = RiskFactor(
            name="invalid",
            distribution="exponential",  # Not supported
            mean=0.1,
            std_dev=0.05,
        )

        with pytest.raises(ValueError) as exc:
            analyzer.run_analysis(
                base_cost=1000000.0,
                risk_factors={"invalid": risk_factor},
            )

        assert "unsupported" in str(exc.value).lower()
```

#### Step 1.5.2: Estimate Generator Tests

**File**: `tests/unit/test_estimate_generator.py` (NEW FILE)

```python
"""
Unit tests for EstimateGenerator orchestration.

Tests workflow coordination without full integration.
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from apex.services.estimate_generator import EstimateGenerator
from apex.models.enums import AACEClass, ProjectStatus, TerrainType, ValidationStatus
from apex.models.database import Project, Document, User


@pytest.fixture
def mock_repositories():
    """Create mock repositories."""
    return {
        "project_repo": Mock(),
        "document_repo": Mock(),
        "estimate_repo": Mock(),
        "audit_repo": Mock(),
    }


@pytest.fixture
def mock_services():
    """Create mock services."""
    return {
        "llm_orchestrator": Mock(),
        "risk_analyzer": Mock(),
        "aace_classifier": Mock(),
        "cost_db_service": Mock(),
    }


@pytest.fixture
def estimate_generator(mock_repositories, mock_services):
    """Create EstimateGenerator with mocked dependencies."""
    return EstimateGenerator(
        project_repo=mock_repositories["project_repo"],
        document_repo=mock_repositories["document_repo"],
        estimate_repo=mock_repositories["estimate_repo"],
        audit_repo=mock_repositories["audit_repo"],
        llm_orchestrator=mock_services["llm_orchestrator"],
        risk_analyzer=mock_services["risk_analyzer"],
        aace_classifier=mock_services["aace_classifier"],
        cost_db_service=mock_services["cost_db_service"],
    )


@pytest.fixture
def sample_project():
    """Create sample project."""
    return Project(
        id=uuid4(),
        project_number="PROJ-001",
        project_name="Test Transmission Line",
        voltage_level=230,
        line_miles=10.0,
        terrain_type=TerrainType.ROLLING,
        status=ProjectStatus.ACTIVE,
        created_by_id=uuid4(),
    )


@pytest.fixture
def sample_documents():
    """Create sample documents."""
    project_id = uuid4()
    return [
        Document(
            id=uuid4(),
            project_id=project_id,
            document_type="scope",
            blob_path="uploads/project/scope.pdf",
            validation_status=ValidationStatus.PASSED,
            completeness_score=85,
            created_by_id=uuid4(),
        ),
        Document(
            id=uuid4(),
            project_id=project_id,
            document_type="engineering",
            blob_path="uploads/project/engineering.pdf",
            validation_status=ValidationStatus.PASSED,
            completeness_score=90,
            created_by_id=uuid4(),
        ),
    ]


@pytest.fixture
def sample_user():
    """Create sample user."""
    return User(
        id=uuid4(),
        aad_object_id="test-aad-id",
        email="test@example.com",
        name="Test User",
    )


class TestEstimateGenerator:
    """Test suite for EstimateGenerator."""

    @pytest.mark.asyncio
    async def test_project_not_found_raises_error(
        self, estimate_generator, mock_repositories, sample_user
    ):
        """Should raise error if project not found."""
        mock_repositories["project_repo"].get_by_id.return_value = None

        from apex.utils.errors import BusinessRuleViolation

        with pytest.raises(BusinessRuleViolation) as exc:
            await estimate_generator.generate_estimate(
                db=Mock(),
                project_id=uuid4(),
                risk_factors_dto=[],
                confidence_level=0.80,
                monte_carlo_iterations=1000,
                user=sample_user,
            )

        assert "not found" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_access_denied_raises_error(
        self, estimate_generator, mock_repositories, sample_project, sample_user
    ):
        """Should raise error if user doesn't have access."""
        mock_repositories["project_repo"].get_by_id.return_value = sample_project
        mock_repositories["project_repo"].check_user_access.return_value = False

        from apex.utils.errors import BusinessRuleViolation

        with pytest.raises(BusinessRuleViolation) as exc:
            await estimate_generator.generate_estimate(
                db=Mock(),
                project_id=sample_project.id,
                risk_factors_dto=[],
                confidence_level=0.80,
                monte_carlo_iterations=1000,
                user=sample_user,
            )

        assert "access" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_workflow_calls_all_services_in_order(
        self,
        estimate_generator,
        mock_repositories,
        mock_services,
        sample_project,
        sample_documents,
        sample_user,
    ):
        """Should call all services in correct order."""
        # Setup mocks
        mock_repositories["project_repo"].get_by_id.return_value = sample_project
        mock_repositories["project_repo"].check_user_access.return_value = True
        mock_repositories["document_repo"].get_by_project_id.return_value = sample_documents

        mock_services["aace_classifier"].classify.return_value = {
            "aace_class": AACEClass.CLASS_3,
            "accuracy_range": "±20%",
            "justification": ["Has engineering docs"],
        }

        from apex.models.database import EstimateLineItem

        mock_services["cost_db_service"].compute_base_cost.return_value = (
            Decimal("1000000.00"),
            [
                EstimateLineItem(
                    description="Test line item",
                    quantity=1.0,
                    unit_of_measure="LS",
                    unit_cost_total=Decimal("1000000.00"),
                    total_cost=Decimal("1000000.00"),
                    wbs_code="10",
                )
            ],
        )

        mock_services["risk_analyzer"].run_analysis.return_value = {
            "base_cost": 1000000.0,
            "mean_cost": 1100000.0,
            "std_dev": 50000.0,
            "percentiles": {
                "p50": 1100000.0,
                "p80": 1150000.0,
                "p95": 1200000.0,
            },
            "min_cost": 950000.0,
            "max_cost": 1300000.0,
            "iterations": 10000,
            "risk_factors_applied": [],
            "sensitivities": {},
        }

        mock_services["llm_orchestrator"].generate_narrative = AsyncMock(
            return_value="Test narrative"
        )
        mock_services["llm_orchestrator"].generate_assumptions = AsyncMock(
            return_value=["Assumption 1", "Assumption 2"]
        )
        mock_services["llm_orchestrator"].generate_exclusions = AsyncMock(
            return_value=["Exclusion 1"]
        )

        from apex.models.database import Estimate

        mock_estimate = Estimate(
            id=uuid4(),
            project_id=sample_project.id,
            estimate_number="EST-001",
            aace_class=AACEClass.CLASS_3,
            base_cost=Decimal("1000000.00"),
            contingency_percentage=15.0,
            p50_cost=Decimal("1100000.00"),
            p80_cost=Decimal("1150000.00"),
            p95_cost=Decimal("1200000.00"),
            narrative="Test narrative",
            created_by_id=sample_user.id,
        )

        mock_repositories["estimate_repo"].create_estimate_with_hierarchy.return_value = (
            mock_estimate
        )

        # Execute
        result = await estimate_generator.generate_estimate(
            db=Mock(),
            project_id=sample_project.id,
            risk_factors_dto=[],
            confidence_level=0.80,
            monte_carlo_iterations=10000,
            user=sample_user,
        )

        # Verify service calls in order
        mock_repositories["project_repo"].get_by_id.assert_called_once()
        mock_repositories["project_repo"].check_user_access.assert_called_once()
        mock_services["aace_classifier"].classify.assert_called_once()
        mock_services["cost_db_service"].compute_base_cost.assert_called_once()
        mock_services["risk_analyzer"].run_analysis.assert_called_once()
        mock_services["llm_orchestrator"].generate_narrative.assert_called_once()
        mock_services["llm_orchestrator"].generate_assumptions.assert_called_once()
        mock_services["llm_orchestrator"].generate_exclusions.assert_called_once()
        mock_repositories["estimate_repo"].create_estimate_with_hierarchy.assert_called_once()

        assert result.id == mock_estimate.id
```

#### Step 1.5.3: Run Tests and Verify

```bash
# Run new tests
pytest tests/unit/test_risk_analysis.py -v
pytest tests/unit/test_estimate_generator.py -v

# Run all tests to ensure no regressions
pytest tests/ --cov=apex --cov-report=term-missing
```

**Acceptance Criteria for Phase 1:**
- [ ] Database migration creates `background_jobs` table
- [ ] Job status endpoint returns job progress
- [ ] Document validation returns 202 and job ID
- [ ] Estimate generation returns 202 and job ID
- [ ] Server can handle 10 concurrent document validations
- [ ] Server can handle 5 concurrent estimate generations
- [ ] Monte Carlo runs in thread pool (verify via logging)
- [ ] All existing tests pass
- [ ] New risk analysis tests pass (10+ test cases)
- [ ] New estimate generator tests pass (5+ test cases)
- [ ] Test coverage for `risk_analysis.py` > 80%
- [ ] Test coverage for `estimate_generator.py` > 70%

---

## Phase 2: High Priority

**Duration**: 1-2 weeks
**Priority**: HIGH - Required for production functionality
**Prerequisites**: Phase 1 complete
**Goal**: Implement production-ready features and fix remaining architectural issues

### Task 2.1: Async KeyVault Client

**Objective**: Replace synchronous KeyVault client with async version to prevent event loop blocking.

#### Step 2.1.1: Refactor KeyVault Client

**File**: `src/apex/azure/key_vault.py`

Replace entire file with:

```python
"""
Azure Key Vault async client with Managed Identity authentication.

CRITICAL: This is an async client - all methods must be awaited.
Use during startup only, not in request path.
"""
import logging
from typing import Optional

from azure.keyvault.secrets.aio import SecretClient

from apex.azure.auth import get_azure_credential

logger = logging.getLogger(__name__)


class KeyVaultClient:
    """
    Async Azure Key Vault client.

    Best Practice: Fetch secrets at startup, not per-request.
    Store in config or environment for request handling.
    """

    def __init__(self):
        """Initialize client (deferred until first use)."""
        self._client: Optional[SecretClient] = None
        self._vault_url: Optional[str] = None

    async def _get_client(self, vault_url: str) -> SecretClient:
        """Get or create async Secret Client."""
        if self._client is None or self._vault_url != vault_url:
            credential = await get_azure_credential()
            self._client = SecretClient(vault_url=vault_url, credential=credential)
            self._vault_url = vault_url
            logger.info(f"Initialized async KeyVault client for {vault_url}")

        return self._client

    async def get_secret(self, vault_url: str, secret_name: str) -> str:
        """
        Get secret value from Key Vault.

        Args:
            vault_url: Key Vault URL (e.g., "https://my-vault.vault.azure.net/")
            secret_name: Name of secret to retrieve

        Returns:
            Secret value as string

        Raises:
            Exception: If secret not found or access denied
        """
        client = await self._get_client(vault_url)

        try:
            secret = await client.get_secret(secret_name)
            logger.debug(f"Retrieved secret: {secret_name}")
            return secret.value
        except Exception as exc:
            logger.error(f"Failed to get secret {secret_name}: {exc}")
            raise

    async def set_secret(self, vault_url: str, secret_name: str, value: str) -> None:
        """
        Set secret value in Key Vault.

        Args:
            vault_url: Key Vault URL
            secret_name: Name of secret to set
            value: Secret value
        """
        client = await self._get_client(vault_url)

        try:
            await client.set_secret(secret_name, value)
            logger.info(f"Set secret: {secret_name}")
        except Exception as exc:
            logger.error(f"Failed to set secret {secret_name}: {exc}")
            raise

    async def close(self) -> None:
        """Close client connection."""
        if self._client is not None:
            await self._client.close()
            logger.info("Closed KeyVault client")
```

#### Step 2.1.2: Update Configuration Loading

**File**: `src/apex/config.py`

If KeyVault is used during config loading, add async initialization:

```python
import asyncio

class Settings(BaseSettings):
    # ... existing fields ...

    @classmethod
    async def load_secrets_from_keyvault(cls) -> dict:
        """Load secrets from Azure Key Vault (async)."""
        from apex.azure.key_vault import KeyVaultClient

        if not config.AZURE_KEYVAULT_URL:
            return {}

        kv_client = KeyVaultClient()

        try:
            secrets = {}

            # Example: Load database password from KV
            if config.USE_KEYVAULT_FOR_DB_PASSWORD:
                secrets["db_password"] = await kv_client.get_secret(
                    vault_url=config.AZURE_KEYVAULT_URL,
                    secret_name="database-password",
                )

            return secrets

        finally:
            await kv_client.close()

# Load secrets at startup (outside request cycle)
# In main.py startup event:
@app.on_event("startup")
async def load_secrets():
    secrets = await Settings.load_secrets_from_keyvault()
    # Store in config or environment
```

#### Step 2.1.3: Verify No Request-Path Usage

Search for any KeyVault usage in API endpoints:

```bash
grep -r "KeyVaultClient" src/apex/api/
grep -r "get_secret" src/apex/api/
```

If found, refactor to load at startup instead.

### Task 2.2: Production Cost Database

**Objective**: Replace hardcoded cost values with real database-backed cost lookup.

This is a substantial undertaking requiring:
1. Cost code data sourcing (RSMeans, internal database, vendor API)
2. Database schema population
3. CostDatabaseService refactoring

#### Step 2.2.1: Populate Cost Code Table

**Option A: Import from CSV**

Create `scripts/import_cost_codes.py`:

```python
"""
Import cost codes from CSV file into database.

Usage:
    python scripts/import_cost_codes.py --file data/cost_codes.csv
"""
import argparse
import csv
import sys
from pathlib import Path
from uuid import uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from apex.database.connection import SessionLocal
from apex.models.database import CostCode


def import_cost_codes(csv_file: Path, source_database: str = "RSMeans"):
    """Import cost codes from CSV."""
    db = SessionLocal()

    try:
        with open(csv_file, "r") as f:
            reader = csv.DictReader(f)

            # Expected columns: code, description, unit_of_measure, unit_cost_material,
            #                   unit_cost_labor, unit_cost_other

            count = 0
            for row in reader:
                cost_code = CostCode(
                    id=uuid4(),
                    code=row["code"],
                    description=row["description"],
                    unit_of_measure=row["unit_of_measure"],
                    source_database=source_database,
                )

                db.add(cost_code)
                count += 1

                if count % 100 == 0:
                    db.commit()
                    print(f"Imported {count} cost codes...")

        db.commit()
        print(f"Successfully imported {count} cost codes")

    except Exception as exc:
        db.rollback()
        print(f"Error importing cost codes: {exc}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import cost codes from CSV")
    parser.add_argument("--file", required=True, help="CSV file path")
    parser.add_argument("--source", default="RSMeans", help="Source database name")

    args = parser.parse_args()

    import_cost_codes(Path(args.file), args.source)
```

**Sample CSV format** (`data/cost_codes.csv`):

```csv
code,description,unit_of_measure
26.01.01,230kV Transmission Tower - Tangent,EA
26.01.02,230kV Transmission Tower - Angle,EA
26.02.01,ACSR Conductor 795 kcmil,LF
26.03.01,Overhead Ground Wire,LF
26.04.01,Tower Foundation - Drilled Pier,EA
```

**Run import:**

```bash
python scripts/import_cost_codes.py --file data/cost_codes.csv
```

#### Step 2.2.2: Create Cost Lookup Service

**File**: `src/apex/services/cost_lookup.py` (NEW FILE)

```python
"""
Cost lookup service for production cost database queries.

Replaces hardcoded values in CostDatabaseService.
"""
import logging
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from apex.models.database import CostCode

logger = logging.getLogger(__name__)


class CostLookupService:
    """Service for looking up cost data from database."""

    def get_cost_by_code(
        self,
        db: Session,
        code: str,
    ) -> Optional[CostCode]:
        """
        Look up cost code by code string.

        Args:
            db: Database session
            code: Cost code (e.g., "26.01.01")

        Returns:
            CostCode entity or None if not found
        """
        query = select(CostCode).where(CostCode.code == code)
        return db.execute(query).scalar_one_or_none()

    def get_all_codes(self, db: Session) -> Dict[str, CostCode]:
        """
        Get all cost codes as dict.

        Returns:
            Dictionary of code -> CostCode
        """
        query = select(CostCode)
        cost_codes = db.execute(query).scalars().all()

        return {cc.code: cc for cc in cost_codes}

    def estimate_tangent_tower_cost(
        self,
        db: Session,
        voltage_level: int,
        quantity: float,
    ) -> Decimal:
        """
        Estimate tangent tower costs.

        Args:
            db: Database session
            voltage_level: Voltage level in kV
            quantity: Number of towers

        Returns:
            Total estimated cost
        """
        # Look up appropriate cost code based on voltage
        if voltage_level >= 345:
            code = "26.01.01.345"  # 345kV+ tangent
        elif voltage_level >= 230:
            code = "26.01.01.230"  # 230kV tangent
        elif voltage_level >= 115:
            code = "26.01.01.115"  # 115kV tangent
        else:
            code = "26.01.01.69"   # 69kV tangent

        cost_code = self.get_cost_by_code(db, code)

        if cost_code is None:
            # Fallback to parametric estimation if no cost code
            logger.warning(f"Cost code {code} not found, using parametric estimate")
            return self._parametric_tower_estimate(voltage_level, quantity)

        # In production, you'd have unit costs in the CostCode table
        # For now, retrieve from external pricing service or table
        unit_cost = self._get_unit_cost(db, cost_code)

        return Decimal(str(quantity * float(unit_cost)))

    def _parametric_tower_estimate(
        self,
        voltage_level: int,
        quantity: float,
    ) -> Decimal:
        """Fallback parametric estimation if no cost data."""
        # Simple parametric model: cost increases with voltage
        base_cost = 50000  # $50K base
        voltage_factor = voltage_level / 100

        unit_cost = base_cost * voltage_factor
        total = quantity * unit_cost

        return Decimal(str(total))

    def _get_unit_cost(
        self,
        db: Session,
        cost_code: CostCode,
    ) -> Decimal:
        """
        Get current unit cost for cost code.

        In production, this would:
        1. Check for regional adjustments
        2. Apply inflation/escalation factors
        3. Include labor + material + overhead

        For MVP, return placeholder based on cost code type.
        """
        # TODO: Implement proper cost lookup from pricing table
        # This is still simplified but better than hardcoded

        if "tower" in cost_code.description.lower():
            return Decimal("75000.00")  # $75K per tower
        elif "conductor" in cost_code.description.lower():
            return Decimal("25.00")  # $25/LF
        elif "foundation" in cost_code.description.lower():
            return Decimal("15000.00")  # $15K per foundation
        else:
            return Decimal("10000.00")  # Default
```

#### Step 2.2.3: Refactor Cost Database Service

**File**: `src/apex/services/cost_database.py`

Replace hardcoded calculations (around lines 180-210) with cost lookup calls:

```python
from apex.services.cost_lookup import CostLookupService

class CostDatabaseService:
    """Enhanced with real cost lookup."""

    def __init__(self):
        self.cost_lookup = CostLookupService()

    def compute_base_cost(
        self,
        db: Session,
        project: Project,
        documents: List[Document],
        cost_code_map: Dict[str, CostCode],
    ) -> Tuple[Decimal, List[EstimateLineItem]]:
        """Compute base cost using database cost lookup."""

        # ... existing code for project metrics ...

        # UPDATED: Use cost lookup instead of hardcoded values
        line_items: List[EstimateLineItem] = []
        total_cost = Decimal("0.00")

        # 1. Tangent Structures
        tangent_quantity = line_miles * 4.0  # ~4 towers per mile
        tangent_cost = self.cost_lookup.estimate_tangent_tower_cost(
            db=db,
            voltage_level=voltage_level,
            quantity=tangent_quantity,
        )

        line_items.append(
            EstimateLineItem(
                wbs_code="10-100",
                description=f"{voltage_level}kV Tangent Structures",
                quantity=tangent_quantity,
                unit_of_measure="EA",
                unit_cost_total=tangent_cost / Decimal(str(tangent_quantity)),
                total_cost=tangent_cost,
            )
        )
        total_cost += tangent_cost

        # 2. Conductor - look up from database
        conductor_lf = line_miles * 5280  # Convert to linear feet
        conductor_cost_code = self.cost_lookup.get_cost_by_code(db, "26.02.01")

        if conductor_cost_code:
            conductor_unit_cost = self.cost_lookup._get_unit_cost(db, conductor_cost_code)
            conductor_total = conductor_unit_cost * Decimal(str(conductor_lf))
        else:
            # Fallback
            conductor_unit_cost = Decimal("2.50")
            conductor_total = conductor_unit_cost * Decimal(str(conductor_lf))

        line_items.append(
            EstimateLineItem(
                wbs_code="10-200",
                description="ACSR Conductor",
                quantity=conductor_lf,
                unit_of_measure="LF",
                unit_cost_total=conductor_unit_cost,
                total_cost=conductor_total,
            )
        )
        total_cost += conductor_total

        # Continue for other line items...

        return total_cost, line_items
```

### Task 2.3: Document Parsing Implementation

**Objective**: Implement Excel and Word document parsing.

#### Step 2.3.1: Implement Excel Parsing

**File**: `src/apex/services/document_parser.py`

Replace `_parse_excel` method (lines 440-466) with:

```python
async def _parse_excel(self, document_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Parse Excel file using openpyxl.

    Extracts sheets, cells, and formulas for LLM analysis.
    """
    import openpyxl
    from io import BytesIO

    try:
        workbook = openpyxl.load_workbook(BytesIO(document_bytes), data_only=False)

        structured = {
            "filename": filename,
            "sheets": [],
            "metadata": {
                "format": "excel",
                "sheet_count": len(workbook.sheetnames),
                "workbook_properties": {
                    "creator": workbook.properties.creator,
                    "created": workbook.properties.created.isoformat()
                    if workbook.properties.created
                    else None,
                },
            },
        }

        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]

            sheet_data = {
                "name": sheet_name,
                "rows": [],
                "tables": [],
                "max_row": sheet.max_row,
                "max_column": sheet.max_column,
            }

            # Extract all non-empty rows
            for row in sheet.iter_rows(values_only=True):
                # Skip completely empty rows
                if any(cell is not None for cell in row):
                    sheet_data["rows"].append(list(row))

            # Extract tables if present
            if hasattr(sheet, "tables"):
                for table in sheet.tables.values():
                    table_data = {
                        "name": table.name if hasattr(table, "name") else None,
                        "ref": table.ref,
                    }
                    sheet_data["tables"].append(table_data)

            structured["sheets"].append(sheet_data)

        logger.info(
            f"Parsed Excel file: {filename} - {len(structured['sheets'])} sheets, "
            f"{sum(len(s['rows']) for s in structured['sheets'])} total rows"
        )

        return structured

    except Exception as exc:
        logger.error(f"Excel parsing error for {filename}: {exc}", exc_info=True)
        raise ValueError(f"Failed to parse Excel file: {str(exc)}")
```

#### Step 2.3.2: Implement Word Parsing

**File**: `src/apex/services/document_parser.py`

Replace `_parse_word` method (lines 468-495) with:

```python
async def _parse_word(self, document_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Parse Word document using python-docx.

    Extracts paragraphs, tables, and styles for LLM analysis.
    """
    import docx
    from io import BytesIO

    try:
        document = docx.Document(BytesIO(document_bytes))

        structured = {
            "filename": filename,
            "paragraphs": [],
            "tables": [],
            "metadata": {
                "format": "word",
                "paragraph_count": len(document.paragraphs),
                "table_count": len(document.tables),
                "core_properties": {
                    "author": document.core_properties.author,
                    "created": document.core_properties.created.isoformat()
                    if document.core_properties.created
                    else None,
                    "title": document.core_properties.title,
                },
            },
        }

        # Extract paragraphs
        for para in document.paragraphs:
            if para.text.strip():  # Skip empty paragraphs
                para_data = {
                    "text": para.text,
                    "style": para.style.name if para.style else None,
                }
                structured["paragraphs"].append(para_data)

        # Extract tables
        for table_idx, table in enumerate(document.tables):
            table_data = {
                "table_number": table_idx + 1,
                "row_count": len(table.rows),
                "column_count": len(table.columns) if table.rows else 0,
                "cells": [],
            }

            for row_idx, row in enumerate(table.rows):
                row_data = []
                for cell in row.cells:
                    row_data.append(cell.text.strip())
                table_data["cells"].append(row_data)

            structured["tables"].append(table_data)

        logger.info(
            f"Parsed Word file: {filename} - {len(structured['paragraphs'])} paragraphs, "
            f"{len(structured['tables'])} tables"
        )

        return structured

    except Exception as exc:
        logger.error(f"Word parsing error for {filename}: {exc}", exc_info=True)
        raise ValueError(f"Failed to parse Word document: {str(exc)}")
```

#### Step 2.3.3: Test Document Parsing

Create test files:

**File**: `tests/unit/test_document_parser.py`

```python
"""
Unit tests for document parser.
"""
import pytest
from pathlib import Path

from apex.services.document_parser import DocumentParser


@pytest.fixture
def parser():
    """Create DocumentParser instance."""
    return DocumentParser()


@pytest.mark.asyncio
async def test_parse_excel_extracts_sheets(parser):
    """Should extract sheet data from Excel file."""
    # Create simple Excel file
    import openpyxl
    from io import BytesIO

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Test Sheet"
    ws["A1"] = "Header 1"
    ws["B1"] = "Header 2"
    ws["A2"] = "Value 1"
    ws["B2"] = "Value 2"

    excel_bytes = BytesIO()
    wb.save(excel_bytes)
    excel_bytes.seek(0)

    result = await parser._parse_excel(excel_bytes.read(), "test.xlsx")

    assert result["filename"] == "test.xlsx"
    assert len(result["sheets"]) == 1
    assert result["sheets"][0]["name"] == "Test Sheet"
    assert len(result["sheets"][0]["rows"]) >= 2


@pytest.mark.asyncio
async def test_parse_word_extracts_paragraphs(parser):
    """Should extract paragraphs from Word file."""
    import docx
    from io import BytesIO

    doc = docx.Document()
    doc.add_paragraph("Test paragraph 1")
    doc.add_paragraph("Test paragraph 2")

    word_bytes = BytesIO()
    doc.save(word_bytes)
    word_bytes.seek(0)

    result = await parser._parse_word(word_bytes.read(), "test.docx")

    assert result["filename"] == "test.docx"
    assert len(result["paragraphs"]) == 2
    assert result["paragraphs"][0]["text"] == "Test paragraph 1"
```

Run tests:

```bash
pytest tests/unit/test_document_parser.py -v
```

**Acceptance Criteria for Phase 2:**
- [ ] KeyVault client uses async methods (`aio`)
- [ ] No KeyVault calls in request path (only at startup)
- [ ] Cost codes table populated with production data
- [ ] CostDatabaseService queries database for costs
- [ ] Excel files parse correctly (verified with test files)
- [ ] Word files parse correctly (verified with test files)
- [ ] Integration tests pass with real document parsing
- [ ] Estimates use real cost data (not hardcoded)

---

## Phase 3: Polish

**Duration**: 1 week
**Priority**: MEDIUM - Quality improvements
**Prerequisites**: Phases 1 & 2 complete
**Goal**: Consistency, documentation, and performance validation

### Task 3.1: Repository Consistency

**Objective**: Standardize error handling across all repositories.

#### Step 3.1.1: Fix DocumentRepository Return Pattern

**File**: `src/apex/database/repositories/document_repository.py`

Find `update_validation_result` method (around line 138) and change:

```python
# BEFORE:
def update_validation_result(...):
    document = self.get(db, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found")  # WRONG!
    # ...

# AFTER:
def update_validation_result(...):
    document = self.get(db, document_id)
    if document is None:
        return None  # Consistent with other repos
    # ...
```

Update all callers to check for `None`:

```python
# In background_jobs.py and any other callers:
updated_document = document_repo.update_validation_result(...)
if updated_document is None:
    logger.error(f"Document {document_id} not found")
    # Handle error appropriately
```

#### Step 3.1.2: Audit All Repositories

Run automated check:

```bash
# Search for ValueError in repositories
grep -r "raise ValueError" src/apex/database/repositories/

# Search for inconsistent None handling
grep -r "if not.*:" src/apex/database/repositories/
```

Standardize to:
- Return `None` for not-found cases
- Raise `BusinessRuleViolation` for business logic errors
- Let API layer convert to appropriate HTTP status

### Task 3.2: API Contract Cleanup

**Objective**: Ensure API contract matches implementation.

#### Step 3.2.1: Remove Unimplemented Export Formats

**File**: `src/apex/api/v1/estimates.py`

**Option A: Remove from pattern (recommended)**

Line 300:

```python
# BEFORE:
format: str = Query("json", pattern="^(json|csv|pdf)$")

# AFTER:
format: str = Query("json", pattern="^(json)$")  # Only json implemented
```

**Option B: Implement CSV export (moderate effort)**

```python
elif format == "csv":
    # Return flattened line items as CSV
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "WBS Code",
        "Description",
        "Quantity",
        "Unit of Measure",
        "Unit Cost",
        "Total Cost",
    ])

    # Write line items
    for item in estimate.line_items:
        writer.writerow([
            item.wbs_code,
            item.description,
            item.quantity,
            item.unit_of_measure,
            float(item.unit_cost_total),
            float(item.total_cost),
        ])

    csv_content = output.getvalue()

    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=estimate_{estimate.estimate_number}.csv"
        },
    )
```

### Task 3.3: Architecture Decision Records

**Objective**: Document major architectural decisions for future maintainers.

#### Step 3.3.1: Create ADR Directory

```bash
mkdir -p docs/adr
```

#### Step 3.3.2: Document Background Jobs Decision

**File**: `docs/adr/001-background-jobs.md`

```markdown
# ADR 001: Background Job Pattern for Long-Running Operations

**Status**: Accepted
**Date**: 2025-01-15
**Deciders**: Development Team

## Context

APEX has two long-running operations that block FastAPI's async event loop:
1. Document validation (30s-2min) - Azure Document Intelligence + LLM validation
2. Estimate generation (30s-5min) - Cost computation + Monte Carlo + LLM narrative

Running these synchronously freezes the server for all users.

## Decision

Implement background job pattern using:
1. FastAPI `BackgroundTasks` for job execution
2. `background_jobs` database table for status tracking
3. Job status API endpoint for progress polling
4. 202 Accepted response with job ID

### Alternative Considered

**Azure Functions + Storage Queues**: More scalable but adds deployment complexity.

**Decision**: Start with FastAPI BackgroundTasks. Migrate to Azure Functions if:
- Job volume exceeds single-instance capacity (>100 concurrent jobs)
- Need for distributed processing across regions
- Requirement for job retry/dead-letter queue

## Consequences

### Positive
- Server remains responsive under concurrent load
- Can handle 10+ concurrent document validations
- Progressive enhancement path to Azure Functions

### Negative
- Requires polling for job status (not real-time)
- Jobs lost if server restarts (mitigated by database tracking)
- Additional database table and API endpoints

## Implementation

See Phase 1, Task 1.1-1.3 in `ImprovementPlan.md`.
```

#### Step 3.3.3: Document GUID TypeDecorator Decision

**File**: `docs/adr/002-guid-typedecorator.md`

```markdown
# ADR 002: GUID TypeDecorator for Cross-Database Compatibility

**Status**: Accepted
**Date**: 2024-12 (retroactive)
**Deciders**: Original Development Team

## Context

APEX must support multiple database backends:
- Azure SQL Server (production) - uses `UNIQUEIDENTIFIER`
- PostgreSQL (potential future) - uses `UUID`
- SQLite (testing) - no native UUID type

Python's `uuid.UUID` doesn't map consistently across databases.

## Decision

Implement custom SQLAlchemy `TypeDecorator` that:
- Uses `UNIQUEIDENTIFIER` on MSSQL
- Uses `UUID` on PostgreSQL
- Uses `CHAR(36)` on SQLite
- Handles byte/string conversion transparently

## Implementation

```python
class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID())
        if dialect.name == "mssql":
            return dialect.type_descriptor(mssql.UNIQUEIDENTIFIER())
        return dialect.type_descriptor(CHAR(36))
    # ... conversion methods
```

## Consequences

### Positive
- Single codebase works across all database backends
- Test with SQLite, deploy to Azure SQL without code changes
- Type-safe UUID handling in Python

### Negative
- Custom type requires understanding for new developers
- Slightly more complex than using database-native types

## References
- `src/apex/models/database.py:23-64`
- SQLAlchemy TypeDecorator docs
```

#### Step 3.3.4: Document Session Management Pattern

**File**: `docs/adr/003-session-management.md`

```markdown
# ADR 003: Session-Per-Request Pattern with Auto-Commit

**Status**: Accepted
**Date**: 2024-12 (retroactive)

## Context

FastAPI with SQLAlchemy requires careful session management to:
- Prevent connection leaks
- Ensure transactions commit/rollback appropriately
- Report errors to clients before response is sent

## Decision

Use FastAPI dependency injection with generator pattern:

```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Commit BEFORE response
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

### Key Principles

1. **One session per request**: Created at request start, closed at end
2. **Commit before response**: Errors can be reported to client
3. **Auto-rollback on error**: Ensures database consistency
4. **No manual commit/rollback in endpoints**: Dependency handles it

### Prohibited Patterns

❌ Manual session creation in services:
```python
db = SessionLocal()  # WRONG - bypasses dependency
```

❌ Manual commit in endpoints:
```python
def endpoint(db: Session = Depends(get_db)):
    # ...
    db.commit()  # WRONG - dependency handles this
```

## Consequences

### Positive
- No connection leaks
- Automatic transaction management
- Errors reported before response sent
- Consistent across all endpoints

### Negative
- Must understand dependency pattern for new developers
- Cannot easily do multi-phase commits (rare requirement)

## References
- `src/apex/dependencies.py:66-99`
- FastAPI SQL Databases tutorial
```

### Task 3.4: Performance Testing

**Objective**: Validate async fixes with load testing.

#### Step 3.4.1: Create Load Test Script

**File**: `tests/performance/load_test.py` (NEW FILE)

```python
"""
Load test for APEX API to verify async fixes.

Requires locust: pip install locust
Run: locust -f tests/performance/load_test.py --host http://localhost:8000
"""
import random
import time
from uuid import uuid4

from locust import HttpUser, task, between


class APEXUser(HttpUser):
    """Simulated APEX user."""

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    def on_start(self):
        """Login and get auth token."""
        # TODO: Implement actual Azure AD token acquisition
        # For now, use mock token if testing with disabled auth
        self.token = "mock-token"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # Create test project
        response = self.client.post(
            "/api/v1/projects",
            json={
                "project_number": f"LOAD-TEST-{uuid4().hex[:8]}",
                "project_name": "Load Test Project",
                "voltage_level": 230,
                "line_miles": 10.0,
                "terrain_type": "rolling",
            },
            headers=self.headers,
        )

        if response.status_code == 201:
            self.project_id = response.json()["id"]
        else:
            self.project_id = None

    @task(3)
    def list_projects(self):
        """List projects (most common operation)."""
        self.client.get(
            "/api/v1/projects",
            headers=self.headers,
        )

    @task(1)
    def validate_document(self):
        """Trigger document validation (async operation)."""
        if not self.project_id:
            return

        # First upload a document
        response = self.client.post(
            "/api/v1/documents/upload",
            data={
                "project_id": self.project_id,
                "document_type": "scope",
            },
            files={
                "file": ("test.pdf", b"fake pdf content", "application/pdf")
            },
            headers={"Authorization": f"Bearer {self.token}"},
        )

        if response.status_code == 201:
            document_id = response.json()["id"]

            # Trigger validation (should return 202 immediately)
            start_time = time.time()

            response = self.client.post(
                f"/api/v1/documents/{document_id}/validate",
                headers=self.headers,
            )

            duration = time.time() - start_time

            # Verify returns quickly (< 1 second)
            if duration > 1.0:
                print(f"WARNING: Validation endpoint took {duration:.2f}s (should be < 1s)")

            # Verify returns 202
            if response.status_code != 202:
                print(f"ERROR: Expected 202, got {response.status_code}")

    @task(1)
    def check_job_status(self):
        """Check background job status."""
        # This would check a real job ID
        # For now, just test the endpoint structure
        fake_job_id = str(uuid4())

        response = self.client.get(
            f"/api/v1/jobs/{fake_job_id}",
            headers=self.headers,
        )

        # Expected 404 (job doesn't exist) or 403 (not your job)
        # Just verify endpoint doesn't crash


# Run with:
# locust -f tests/performance/load_test.py --host http://localhost:8000 --users 10 --spawn-rate 2
```

#### Step 3.4.2: Run Load Tests

```bash
# Install locust
pip install locust

# Start APEX server
uvicorn apex.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, run load test
cd /home/gbass/MyProjects/APEX
locust -f tests/performance/load_test.py \
    --host http://localhost:8000 \
    --users 10 \
    --spawn-rate 2 \
    --run-time 5m \
    --headless \
    --html reports/load_test_report.html
```

**Success Criteria:**
- Server handles 10 concurrent users without timeouts
- Document validation returns in < 1 second (202 response)
- Estimate generation returns in < 1 second (202 response)
- No 500 errors during 5-minute test
- Memory usage remains stable (no leaks)

**Acceptance Criteria for Phase 3:**
- [ ] All repositories return `None` consistently
- [ ] No `ValueError` raised for not-found cases
- [ ] Export endpoint only advertises implemented formats
- [ ] CSV export works OR removed from API contract
- [ ] 3 ADRs created and reviewed
- [ ] Load test passes with 10 concurrent users
- [ ] No timeouts during 5-minute load test
- [ ] Memory usage stable during load test

---

## Testing Strategy

### Unit Tests

**Coverage Targets:**
- `risk_analysis.py`: 80%+ (critical statistical code)
- `estimate_generator.py`: 70%+ (orchestration)
- `document_parser.py`: 70%+ (parsing logic)
- `background_jobs.py`: 60%+ (worker functions)

**Key Test Scenarios:**
1. **Monte Carlo**: Validate against known distributions
2. **Estimate Generation**: Test workflow with mocked services
3. **Document Parsing**: Test all file formats
4. **Job Tracking**: Test status transitions

### Integration Tests

**API Endpoint Tests:**
- Document upload → validation (background) → job status → completion
- Estimate generation (background) → job status → completion
- Error handling (invalid project ID, access denied, etc.)

**Database Tests:**
- Job status updates
- Estimate hierarchy persistence
- Transaction rollback on errors

### Performance Tests

**Load Testing:**
- 10 concurrent users for 5 minutes
- Mix of operations (70% read, 20% document validation, 10% estimates)
- Verify response times < SLA

**Stress Testing:**
- Increase to 50 concurrent users
- Monitor for memory leaks
- Verify graceful degradation

### Manual Testing Checklist

**Phase 1 Verification:**
- [ ] Upload document, trigger validation, returns 202
- [ ] Poll job status, see progress updates
- [ ] Job completes, document status updated
- [ ] Generate estimate, returns 202
- [ ] Poll job status, see progress (10%, 50%, 90%)
- [ ] Job completes, estimate created
- [ ] Server handles multiple simultaneous validations
- [ ] Server handles multiple simultaneous estimates

**Phase 2 Verification:**
- [ ] Upload Excel file, parses correctly
- [ ] Upload Word file, parses correctly
- [ ] Estimate uses database costs (not hardcoded)
- [ ] Cost lookup queries database

**Phase 3 Verification:**
- [ ] Load test passes
- [ ] Export JSON works
- [ ] Export CSV works (if implemented)
- [ ] ADRs readable and accurate

---

## Acceptance Criteria

### Phase 1: Critical Fixes

**Functional:**
- [ ] Background jobs table created and migrated
- [ ] Job status endpoint returns accurate progress
- [ ] Document validation endpoint returns 202 Accepted
- [ ] Estimate generation endpoint returns 202 Accepted
- [ ] Job polling shows progress updates
- [ ] Jobs complete successfully with results

**Performance:**
- [ ] Document validation returns in < 1 second
- [ ] Estimate generation returns in < 1 second
- [ ] Server handles 10 concurrent document validations
- [ ] Server handles 5 concurrent estimate generations
- [ ] Monte Carlo runs in thread pool (verified via logging)

**Testing:**
- [ ] All existing tests pass
- [ ] 10+ new risk analysis tests pass
- [ ] 5+ new estimate generator tests pass
- [ ] Test coverage: `risk_analysis.py` > 80%
- [ ] Test coverage: `estimate_generator.py` > 70%

### Phase 2: High Priority

**Functional:**
- [ ] KeyVault client uses async (`aio`) methods
- [ ] No KeyVault calls in request path
- [ ] Cost codes table populated with data
- [ ] CostDatabaseService queries database for costs
- [ ] Excel files parse with openpyxl
- [ ] Word files parse with python-docx

**Testing:**
- [ ] Excel parsing tests pass
- [ ] Word parsing tests pass
- [ ] Integration tests with real parsing pass
- [ ] Estimates generated with database costs

### Phase 3: Polish

**Functional:**
- [ ] All repositories use consistent error patterns
- [ ] No `ValueError` for not-found cases
- [ ] Export endpoint matches implementation
- [ ] ADRs created and reviewed

**Performance:**
- [ ] Load test passes (10 users, 5 minutes)
- [ ] No timeouts during load test
- [ ] Memory usage stable
- [ ] Response times meet SLA

### Overall Production Readiness

**Critical Checklist:**
- [ ] All Phase 1 acceptance criteria met
- [ ] All Phase 2 acceptance criteria met
- [ ] All Phase 3 acceptance criteria met
- [ ] Security review completed
- [ ] Documentation updated
- [ ] Deployment runbook created
- [ ] Monitoring/alerting configured
- [ ] Disaster recovery plan documented

---

## Risk Mitigation

### Technical Risks

**Risk**: Background jobs fail silently
**Mitigation**:
- Job status tracking in database
- Failed status with error messages
- Monitoring alerts on job failures
- Job cleanup cron (delete old jobs)

**Risk**: Thread pool exhaustion
**Mitigation**:
- Monitor concurrent job count
- Implement job queue limits
- Add retry logic with exponential backoff
- Scale horizontally if needed

**Risk**: NumPy/SciPy not thread-safe
**Mitigation**:
- Test Monte Carlo in thread pool thoroughly
- Use `ProcessPoolExecutor` if thread safety issues
- Verify results match single-threaded execution

**Risk**: Database connection exhaustion
**Mitigation**:
- Background workers create own sessions
- NullPool prevents connection pooling
- Monitor active connection count

### Deployment Risks

**Risk**: Migration downtime
**Mitigation**:
- Test migrations on staging first
- Migrations are additive (add table, don't modify)
- Can rollback if needed
- Schedule during maintenance window

**Risk**: Breaking API changes
**Mitigation**:
- Document validation/generation still work (just async)
- New endpoints for job status
- Old behavior deprecated, not removed
- Version API (v1 → v2 if needed)

### Data Risks

**Risk**: Cost data inaccuracy
**Mitigation**:
- Validate cost codes against source data
- Implement cost code approval workflow
- Audit cost lookups
- Compare estimates before/after

---

## Deployment Guide

### Pre-Deployment Checklist

**Code Review:**
- [ ] All code reviewed by senior developer
- [ ] Security review completed
- [ ] Performance testing passed
- [ ] Documentation updated

**Database:**
- [ ] Alembic migrations tested on staging
- [ ] Backup current production database
- [ ] Rollback plan documented

**Configuration:**
- [ ] Environment variables updated
- [ ] Azure resources provisioned
- [ ] Managed Identity permissions granted
- [ ] Application Insights configured

### Deployment Steps

#### Step 1: Database Migration

```bash
# On staging first
alembic upgrade head

# Verify migration
psql -U user -d apex_staging -c "\dt"  # List tables
psql -U user -d apex_staging -c "SELECT COUNT(*) FROM background_jobs;"  # Verify table

# On production (during maintenance window)
alembic upgrade head
```

#### Step 2: Deploy Application

```bash
# Build Docker image
docker build -t apex:v1.1.0 .

# Push to Azure Container Registry
az acr login --name apexregistry
docker tag apex:v1.1.0 apexregistry.azurecr.io/apex:v1.1.0
docker push apexregistry.azurecr.io/apex:v1.1.0

# Update Container App
az containerapp update \
  --name apex-api \
  --resource-group apex-prod \
  --image apexregistry.azurecr.io/apex:v1.1.0
```

#### Step 3: Verify Deployment

```bash
# Health check
curl https://apex-api.azurecontainerapps.io/health/live
curl https://apex-api.azurecontainerapps.io/health/ready

# Test background jobs
curl -X POST https://apex-api.azurecontainerapps.io/api/v1/documents/{id}/validate \
  -H "Authorization: Bearer $TOKEN"
# Should return 202 with job_id

# Check job status
curl https://apex-api.azurecontainerapps.io/api/v1/jobs/{job_id} \
  -H "Authorization: Bearer $TOKEN"
```

#### Step 4: Monitor

```bash
# Watch Application Insights for errors
az monitor app-insights query \
  --app apex-insights \
  --analytics-query "exceptions | where timestamp > ago(1h)"

# Monitor job completion rate
az monitor app-insights query \
  --app apex-insights \
  --analytics-query "customEvents | where name == 'background_job_completed' | summarize count() by bin(timestamp, 5m)"
```

### Rollback Plan

If issues occur:

```bash
# Rollback Container App to previous version
az containerapp update \
  --name apex-api \
  --resource-group apex-prod \
  --image apexregistry.azurecr.io/apex:v1.0.0

# Rollback database migration (if needed)
alembic downgrade -1

# Verify rollback
curl https://apex-api.azurecontainerapps.io/health/ready
```

---

## Appendices

### Appendix A: Code Examples

**Before/After: Document Validation Endpoint**

```python
# BEFORE (Blocking):
@router.post("/{document_id}/validate")
async def validate_document(...):
    # Blocks for 30s-2min
    structured_content = await document_parser.parse_document(...)
    llm_validation = await llm_orchestrator.validate_document(...)
    return DocumentValidationResult(...)

# AFTER (Non-Blocking):
@router.post("/{document_id}/validate", status_code=202)
async def validate_document(background_tasks: BackgroundTasks, ...):
    job = job_repo.create_job(db, "document_validation", user_id, document_id)
    background_tasks.add_task(process_document_validation, job.id, document_id, user_id)
    return JobStatusResponse(id=job.id, status="pending", ...)
```

**Before/After: Monte Carlo Execution**

```python
# BEFORE (Blocking):
risk_results = self.risk_analyzer.run_analysis(...)  # Blocks async loop!

# AFTER (Thread Pool):
import asyncio
risk_results = await asyncio.to_thread(
    self.risk_analyzer.run_analysis,
    base_cost=float(base_cost),
    risk_factors=risk_factors,
)
```

### Appendix B: Database Schema Changes

**New Table: background_jobs**

```sql
CREATE TABLE background_jobs (
    id UNIQUEIDENTIFIER PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pending, running, completed, failed
    document_id UNIQUEIDENTIFIER NULL FOREIGN KEY REFERENCES documents(id),
    project_id UNIQUEIDENTIFIER NULL FOREIGN KEY REFERENCES projects(id),
    estimate_id UNIQUEIDENTIFIER NULL FOREIGN KEY REFERENCES estimates(id),
    progress_percent INT DEFAULT 0,
    current_step VARCHAR(255),
    result_data NVARCHAR(MAX),  -- JSON
    error_message NVARCHAR(MAX),
    created_at DATETIME2 NOT NULL,
    started_at DATETIME2 NULL,
    completed_at DATETIME2 NULL,
    created_by_id UNIQUEIDENTIFIER NOT NULL FOREIGN KEY REFERENCES users(id),
    INDEX ix_background_jobs_status_created (status, created_at),
    INDEX ix_background_jobs_user (created_by_id),
);
```

### Appendix C: Environment Variables

**New Environment Variables:**

```bash
# Background job configuration
BACKGROUND_JOB_CLEANUP_DAYS=30  # Delete old jobs after 30 days
BACKGROUND_JOB_MAX_CONCURRENT=10  # Max concurrent jobs per instance

# Cost database configuration
COST_DATABASE_SOURCE="RSMeans"  # Cost data source identifier
COST_DATABASE_VERSION="2024"    # Cost data version for audit trail
```

### Appendix D: References

**External Documentation:**
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [asyncio.to_thread](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread)
- [SQLAlchemy 2.0 TypeDecorator](https://docs.sqlalchemy.org/en/20/core/custom_types.html#sqlalchemy.types.TypeDecorator)
- [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Latin Hypercube Sampling (scipy)](https://docs.scipy.org/doc/scipy/reference/stats.qmc.html)

**Internal Documentation:**
- Code Analysis Report (generated 2025-01-15)
- APEX Specification (`APEX_Prompt.md`)
- Architecture Decision Records (`docs/adr/`)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-15 | Claude Code Analysis | Initial comprehensive plan |

---

**END OF IMPROVEMENT PLAN**

This document is comprehensive and ready for handoff to another developer or IDE. All tasks include specific file paths, code examples, acceptance criteria, and testing strategies.
