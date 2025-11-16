import asyncio
from typing import Callable

import pytest
from sqlalchemy.orm import sessionmaker

from apex.database.repositories.job_repository import JobRepository
from apex.models.enums import ValidationStatus
from apex.services import background_jobs


def _bind_session_factory(db_session) -> Callable:
    """Create a SessionLocal factory bound to the test engine."""
    bind = db_session.get_bind()
    return sessionmaker(bind=bind, autocommit=False, autoflush=False, future=True)


@pytest.mark.asyncio
async def test_document_validation_background_job_completes(
    client,
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

    resp = await client.post(f"/documents/{test_document.id}/validate")
    assert resp.status_code == 202
    job_id = resp.json()["id"]

    job_repo = JobRepository()
    job = None
    for _ in range(20):
        job = job_repo.get(db_session, job_id)
        if job and job.status in ("completed", "failed"):
            break
        await asyncio.sleep(0.05)

    assert job is not None, "Job record should exist"
    assert job.status == "completed"
    assert job.result_data["document_id"] == str(test_document.id)
    assert job.result_data["validation_status"] in ("PENDING", "PASSED", "MANUAL_REVIEW")


@pytest.mark.asyncio
async def test_estimate_generation_background_job_completes(
    client,
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

        def run_analysis(self, base_cost, risk_factors, correlation_matrix=None, confidence_levels=None):
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

    payload = {
        "project_id": str(test_project.id),
        "risk_factors": [],
        "confidence_level": 0.8,
        "monte_carlo_iterations": 1000,
    }
    resp = await client.post("/estimates/generate", json=payload)
    assert resp.status_code == 202
    job_id = resp.json()["id"]

    job_repo = JobRepository()
    job = None
    for _ in range(30):
        job = job_repo.get(db_session, job_id)
        if job and job.status in ("completed", "failed"):
            break
        await asyncio.sleep(0.05)
        db_session.expire_all()

    assert job is not None, "Job record should exist"
    assert job.status == "completed"
    assert job.result_data["project_id"] == str(test_project.id)
    assert "estimate_id" in job.result_data
