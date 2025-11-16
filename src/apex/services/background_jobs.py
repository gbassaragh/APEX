"""
Background job workers for long-running operations.

Uses FastAPI BackgroundTasks to run operations asynchronously without blocking the main
event loop for expensive document validation and estimate generation.
"""
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select

from apex.azure.blob_storage import BlobStorageClient
from apex.config import config
from apex.database.connection import SessionLocal
from apex.database.repositories.audit_repository import AuditRepository
from apex.database.repositories.document_repository import DocumentRepository
from apex.database.repositories.estimate_repository import EstimateRepository
from apex.database.repositories.job_repository import JobRepository
from apex.database.repositories.project_repository import ProjectRepository
from apex.models.database import User
from apex.models.enums import AACEClass, ValidationStatus
from apex.services.aace_classifier import AACEClassifier
from apex.services.cost_database import CostDatabaseService
from apex.services.document_parser import DocumentParser
from apex.services.estimate_generator import EstimateGenerator
from apex.services.llm.orchestrator import LLMOrchestrator
from apex.services.risk_analysis import MonteCarloRiskAnalyzer
from apex.utils.errors import BusinessRuleViolation

logger = logging.getLogger(__name__)


async def process_document_validation(
    job_id: UUID,
    document_id: UUID,
    user_id: UUID,
) -> None:
    """Background worker for document validation."""
    db = SessionLocal()

    try:
        job_repo = JobRepository()
        document_repo = DocumentRepository()
        project_repo = ProjectRepository()
        audit_repo = AuditRepository()
        blob_storage = BlobStorageClient()
        document_parser = DocumentParser()
        llm_orchestrator = LLMOrchestrator()

        job_repo.update_progress(db, job_id, progress_percent=10, current_step="Loading document")
        db.commit()

        document = document_repo.get(db, document_id)
        if not document:
            job_repo.mark_failed(db, job_id, f"Document {document_id} not found")
            db.commit()
            return

        # Access check: ensure user can reach project
        access = project_repo.check_user_access(db, user_id, document.project_id)
        if not access:
            job_repo.mark_failed(db, job_id, "Access denied for this document/project")
            db.commit()
            return

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
            db, job_id, progress_percent=35, current_step="Parsing document with Azure DI"
        )
        db.commit()

        try:
            structured_content = await document_parser.parse_document(
                document_bytes=document_bytes,
                filename=Path(document.blob_path).name,
                blob_path=f"{config.AZURE_STORAGE_CONTAINER_UPLOADS}/{document.blob_path}",
            )

            document_repo.update_validation_result(
                db=db,
                document_id=document_id,
                validation_result={"parsed_content": structured_content},
                completeness_score=0,
                validation_status=ValidationStatus.PENDING,
            )
            db.commit()
        except BusinessRuleViolation as circuit_error:
            job_repo.mark_failed(db, job_id, f"Document parsing failed: {str(circuit_error)}")
            document_repo.update_validation_result(
                db=db,
                document_id=document_id,
                validation_result={"error": str(circuit_error)},
                completeness_score=0,
                validation_status=ValidationStatus.FAILED,
            )
            db.commit()
            return
        except Exception as parse_error:
            logger.error(f"Document parsing error: {parse_error}", exc_info=True)
            job_repo.mark_failed(db, job_id, f"Document parsing failed: {str(parse_error)}")
            document_repo.update_validation_result(
                db=db,
                document_id=document_id,
                validation_result={"error": str(parse_error)},
                completeness_score=0,
                validation_status=ValidationStatus.FAILED,
            )
            db.commit()
            return

        # Step 2: LLM validation
        job_repo.update_progress(
            db, job_id, progress_percent=55, current_step="Running LLM validation"
        )
        db.commit()

        aace_class = AACEClass.CLASS_2 if document.document_type == "bid" else AACEClass.CLASS_4

        try:
            llm_validation = await llm_orchestrator.validate_document(
                aace_class=aace_class,
                document_type=document.document_type,
                structured_content=structured_content,
            )
            completeness_score = llm_validation.get("completeness_score", 0)
            suitable_for_estimation = llm_validation.get("suitable_for_estimation", False)

            if suitable_for_estimation and completeness_score >= 70:
                validation_status = ValidationStatus.PASSED
            elif completeness_score >= 50:
                validation_status = ValidationStatus.MANUAL_REVIEW
            else:
                validation_status = ValidationStatus.FAILED

            validation_result: Dict[str, Any] = {
                "parsed_content": structured_content,
                "llm_validation": llm_validation,
                "aace_class_used": aace_class.value,
            }
        except Exception as llm_error:
            logger.error(f"LLM validation error for {document_id}: {llm_error}", exc_info=True)
            completeness_score = 0
            suitable_for_estimation = False
            validation_status = ValidationStatus.MANUAL_REVIEW
            validation_result = {
                "parsed_content": structured_content,
                "llm_error": str(llm_error),
                "aace_class_used": aace_class.value,
                "issues": [f"LLM validation failed: {str(llm_error)}"],
                "recommendations": ["Manual review required due to LLM validation failure"],
            }

        updated_document = document_repo.update_validation_result(
            db=db,
            document_id=document_id,
            validation_result=validation_result,
            completeness_score=completeness_score,
            validation_status=validation_status,
        )
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
                },
            },
        )
        job_repo.mark_completed(
            db,
            job_id,
            result_data={
                "document_id": str(document_id),
                "validation_status": updated_document.validation_status.value,
                "completeness_score": updated_document.completeness_score,
                "suitable_for_estimation": suitable_for_estimation,
            },
        )
        db.commit()
        logger.info("Document validation job completed: %s", job_id)
    except Exception as exc:
        logger.error(f"Document validation job failed: {exc}", exc_info=True)
        try:
            job_repo.mark_failed(db, job_id, str(exc))
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


async def process_estimate_generation(
    job_id: UUID,
    project_id: UUID,
    risk_factors_dto: List[Dict[str, Any]],
    confidence_level: float,
    monte_carlo_iterations: int,
    user_id: UUID,
) -> None:
    """Background worker for estimate generation."""
    db = SessionLocal()

    try:
        job_repo = JobRepository()
        project_repo = ProjectRepository()
        document_repo = DocumentRepository()
        estimate_repo = EstimateRepository()
        audit_repo = AuditRepository()

        # Initialize services
        risk_analyzer = MonteCarloRiskAnalyzer(iterations=monte_carlo_iterations, random_seed=42)
        llm_orchestrator = LLMOrchestrator()
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

        job_repo.update_progress(db, job_id, progress_percent=10, current_step="Preparing estimate job")
        db.commit()

        project = project_repo.get(db, project_id)
        if not project:
            job_repo.mark_failed(db, job_id, f"Project {project_id} not found")
            db.commit()
            return

        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not user:
            job_repo.mark_failed(db, job_id, "User not found for estimate generation")
            db.commit()
            return

        job_repo.update_progress(db, job_id, progress_percent=25, current_step="Running estimate generator")
        db.commit()

        estimate = await estimate_generator.generate_estimate(
            db=db,
            project_id=project_id,
            risk_factors_dto=risk_factors_dto,
            confidence_level=confidence_level,
            monte_carlo_iterations=monte_carlo_iterations,
            user=user,
        )

        job_repo.update_progress(db, job_id, progress_percent=90, current_step="Loading estimate details")
        db.commit()

        estimate_with_details = estimate_repo.get_estimate_with_details(db, estimate.id)
        job_repo.mark_completed(
            db,
            job_id,
            result_data={
                "estimate_id": str(estimate.id),
                "project_id": str(project_id),
                "estimate_number": estimate.estimate_number,
                "aace_class": estimate.aace_class.value,
                "base_cost": float(estimate.base_cost),
                "p50_cost": float(estimate.p50_cost) if estimate.p50_cost else None,
                "p80_cost": float(estimate.p80_cost) if estimate.p80_cost else None,
                "p95_cost": float(estimate.p95_cost) if estimate.p95_cost else None,
            },
            estimate_id=estimate.id,
        )
        db.commit()
        logger.info("Estimate generation job completed: %s", job_id)
    except Exception as exc:
        logger.error(f"Estimate generation job failed: {exc}", exc_info=True)
        try:
            job_repo.mark_failed(db, job_id, str(exc))
            db.commit()
        except Exception:
            pass
    finally:
        db.close()
