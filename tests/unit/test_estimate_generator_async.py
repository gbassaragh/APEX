import asyncio
import threading
from decimal import Decimal
from uuid import uuid4

import pytest

from apex.database.repositories.audit_repository import AuditRepository
from apex.database.repositories.document_repository import DocumentRepository
from apex.database.repositories.estimate_repository import EstimateRepository
from apex.database.repositories.project_repository import ProjectRepository
from apex.models.database import Document
from apex.models.enums import ValidationStatus
from apex.services.aace_classifier import AACEClassifier
from apex.services.cost_database import CostDatabaseService
from apex.services.estimate_generator import EstimateGenerator
from tests.fixtures.azure_mocks import MockLLMOrchestrator


@pytest.mark.asyncio
async def test_monte_carlo_runs_in_thread(db_session, test_project, test_user):
    # Seed a validated document for project metrics
    doc = Document(
        id=uuid4(),
        project_id=test_project.id,
        document_type="engineering",
        blob_path="uploads/test-project/eng.pdf",
        validation_status=ValidationStatus.PASSED,
        completeness_score=80,
        created_by_id=test_user.id,
    )
    db_session.add(doc)
    db_session.commit()

    main_thread_name = threading.current_thread().name

    class RecordingRiskAnalyzer:
        def __init__(self, iterations: int, random_seed: int = 42):
            self.iterations = iterations
            self.random_seed = random_seed
            self.thread_seen = None

        def run_analysis(self, base_cost, risk_factors, correlation_matrix=None, confidence_levels=None):
            self.thread_seen = threading.current_thread().name
            return {
                "base_cost": base_cost,
                "mean_cost": base_cost,
                "std_dev": 0.0,
                "percentiles": {"p50": base_cost, "p80": base_cost, "p95": base_cost},
                "min_cost": base_cost,
                "max_cost": base_cost,
                "iterations": self.iterations,
                "risk_factors_applied": list(risk_factors.keys()),
                "sensitivities": {},
            }

    risk_analyzer = RecordingRiskAnalyzer(iterations=1000)
    estimate_generator = EstimateGenerator(
        project_repo=ProjectRepository(),
        document_repo=DocumentRepository(),
        estimate_repo=EstimateRepository(),
        audit_repo=AuditRepository(),
        llm_orchestrator=MockLLMOrchestrator(),
        risk_analyzer=risk_analyzer,
        aace_classifier=AACEClassifier(),
        cost_db_service=CostDatabaseService(),
    )

    estimate = await estimate_generator.generate_estimate(
        db=db_session,
        project_id=test_project.id,
        risk_factors_dto=[],
        confidence_level=0.8,
        monte_carlo_iterations=500,
        user=test_user,
    )

    assert estimate is not None
    assert risk_analyzer.thread_seen is not None
    assert risk_analyzer.thread_seen != main_thread_name
