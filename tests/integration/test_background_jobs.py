from typing import Callable

import pytest
from sqlalchemy.orm import sessionmaker

from apex.database.repositories.job_repository import JobRepository
from apex.models.enums import ValidationStatus
from apex.services import background_jobs
from apex.services.background_jobs import process_document_validation, process_estimate_generation


def _bind_session_factory(db_session) -> Callable:
    """Create a SessionLocal factory bound to the test engine."""
    bind = db_session.get_bind()
    return sessionmaker(bind=bind, autocommit=False, autoflush=False, future=True)


@pytest.mark.asyncio
async def test_document_validation_background_job_completes(
    db_session,
    test_document,
    mock_blob_storage,
    mock_document_parser,
    mock_llm_orchestrator,
    monkeypatch,
):
    # Ensure mocks are used inside background worker
    monkeypatch.setattr(background_jobs, "SessionLocal", _bind_session_factory(db_session))
    monkeypatch.setattr(background_jobs, "BlobStorageClient", lambda: mock_blob_storage)
    monkeypatch.setattr(background_jobs, "DocumentParser", lambda: mock_document_parser)
    monkeypatch.setattr(background_jobs, "LLMOrchestrator", lambda: mock_llm_orchestrator)

    from apex.config import config

    await mock_blob_storage.upload_document(
        container=config.AZURE_STORAGE_CONTAINER_UPLOADS,
        blob_name=test_document.blob_path,
        data=b"pdf-bytes",
        content_type="application/pdf",
    )

    job_repo = JobRepository()
    job = job_repo.create_job(
        db=db_session,
        job_type="document_validation",
        user_id=test_document.created_by_id,
        document_id=test_document.id,
        project_id=test_document.project_id,
    )
    db_session.commit()

    await process_document_validation(job.id, test_document.id, test_document.created_by_id)
    db_session.expire_all()
    job = job_repo.get(db_session, job.id)

    assert job is not None
    assert job.status == "completed"
    assert job.result_data["document_id"] == str(test_document.id)
    assert job.result_data["validation_status"].upper() in ("PENDING", "PASSED", "MANUAL_REVIEW")


@pytest.mark.asyncio
async def test_estimate_generation_background_job_completes(
    db_session,
    test_project,
    test_document,
    mock_blob_storage,
    mock_llm_orchestrator,
    monkeypatch,
):
    # Make document appear validated for completeness heuristics
    test_document.validation_status = ValidationStatus.PASSED
    test_document.completeness_score = 80
    db_session.commit()

    # Fast risk analyzer to avoid heavy Monte Carlo during tests
    class FastRiskAnalyzer:
        def __init__(self, iterations: int, random_seed: int = 42):
            self.iterations = iterations
            self.random_seed = random_seed

        def run_analysis(
            self, base_cost, risk_factors, correlation_matrix=None, confidence_levels=None
        ):
            return {
                "base_cost": base_cost,
                "mean_cost": base_cost * 1.05,
                "std_dev": 0.0,
                "percentiles": {"p50": base_cost, "p80": base_cost * 1.1, "p95": base_cost * 1.2},
                "min_cost": base_cost,
                "max_cost": base_cost * 1.2,
                "iterations": self.iterations,
                "risk_factors_applied": [],
                "sensitivities": {},
            }

    # Ensure mocks are used inside background worker
    monkeypatch.setattr(background_jobs, "SessionLocal", _bind_session_factory(db_session))
    monkeypatch.setattr(background_jobs, "BlobStorageClient", lambda: mock_blob_storage)
    monkeypatch.setattr(background_jobs, "LLMOrchestrator", lambda: mock_llm_orchestrator)
    monkeypatch.setattr(background_jobs, "MonteCarloRiskAnalyzer", FastRiskAnalyzer)

    job_repo = JobRepository()
    job = job_repo.create_job(
        db=db_session,
        job_type="estimate_generation",
        user_id=test_document.created_by_id,
        project_id=test_project.id,
    )
    db_session.commit()

    await process_estimate_generation(
        job.id,
        test_project.id,
        [],
        0.8,
        1000,
        test_document.created_by_id,
    )

    db_session.expire_all()
    job = job_repo.get(db_session, job.id)

    assert job is not None
    assert job.status == "completed"
    assert job.result_data["project_id"] == str(test_project.id)
    assert "estimate_id" in job.result_data
