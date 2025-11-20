import pytest

from apex.models.enums import ValidationStatus
from apex.services import background_jobs
from tests.integration.test_background_jobs import _bind_session_factory


@pytest.mark.asyncio
async def test_document_validation_endpoint_returns_job(
    client,
    db_session,
    test_document,
    mock_blob_storage,
    mock_document_parser,
    mock_llm_orchestrator,
    monkeypatch,
):
    # Ensure background worker uses test DB/mocks
    monkeypatch.setattr(background_jobs, "SessionLocal", _bind_session_factory(db_session))
    monkeypatch.setattr(background_jobs, "BlobStorageClient", lambda: mock_blob_storage)
    monkeypatch.setattr(background_jobs, "DocumentParser", lambda: mock_document_parser)
    monkeypatch.setattr(background_jobs, "LLMOrchestrator", lambda: mock_llm_orchestrator)

    # Seed blob content for download
    from apex.config import config

    await mock_blob_storage.upload_document(
        container=config.AZURE_STORAGE_CONTAINER_UPLOADS,
        blob_name=test_document.blob_path,
        data=b"pdf-bytes",
        content_type="application/pdf",
    )

    resp = await client.post(f"/api/v1/documents/{test_document.id}/validate")
    assert resp.status_code == 202
    job_id = resp.json()["id"]

    # With TESTING=true, the endpoint runs the job inline
    status_resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert status_resp.status_code == 200
    payload = status_resp.json()
    assert payload.get("status") == "completed"
    assert payload["result_data"]["document_id"] == str(test_document.id)
    assert payload["result_data"]["validation_status"].upper() in (
        "PENDING",
        "PASSED",
        "MANUAL_REVIEW",
    )


@pytest.mark.asyncio
async def test_estimate_generation_endpoint_returns_job(
    client,
    db_session,
    test_project,
    test_document,
    mock_blob_storage,
    mock_llm_orchestrator,
    monkeypatch,
):
    monkeypatch.setattr(background_jobs, "SessionLocal", _bind_session_factory(db_session))
    monkeypatch.setattr(background_jobs, "BlobStorageClient", lambda: mock_blob_storage)
    monkeypatch.setattr(background_jobs, "LLMOrchestrator", lambda: mock_llm_orchestrator)

    class FastRiskAnalyzer:
        """Fast stub to avoid heavy Monte Carlo during integration tests."""

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
                "percentiles": {
                    "p50": base_cost,
                    "p80": base_cost * 1.1,
                    "p95": base_cost * 1.2,
                },
                "min_cost": base_cost,
                "max_cost": base_cost * 1.2,
                "iterations": self.iterations,
                "risk_factors_applied": [],
                "sensitivities": {},
            }

    monkeypatch.setattr(background_jobs, "MonteCarloRiskAnalyzer", FastRiskAnalyzer)

    test_document.validation_status = ValidationStatus.PASSED
    test_document.completeness_score = 80
    db_session.commit()

    payload = {
        "project_id": str(test_project.id),
        "risk_factors": [],
        "confidence_level": 0.8,
        "monte_carlo_iterations": 1000,
    }
    resp = await client.post("/api/v1/estimates/generate", json=payload)
    assert resp.status_code == 202
    job_id = resp.json()["id"]

    # With TESTING=true, the endpoint runs the job inline
    status_resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert status_resp.status_code == 200
    payload = status_resp.json()
    assert payload["status"] == "completed"
    assert payload["result_data"]["project_id"] == str(test_project.id)
    assert "estimate_id" in payload["result_data"]
