"""
Estimate generation and retrieval endpoints.

Handles full estimate orchestration workflow including:
- AACE classification
- Cost breakdown structure generation
- Monte Carlo risk analysis
- LLM narrative generation
"""
import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from apex.config import config
from apex.database.repositories.estimate_repository import EstimateRepository
from apex.database.repositories.job_repository import JobRepository
from apex.database.repositories.project_repository import ProjectRepository
from apex.dependencies import (
    get_current_user,
    get_db,
    get_estimate_repo,
    get_job_repo,
    get_project_repo,
)
from apex.models.database import User
from apex.models.schemas import (
    EstimateDetailResponse,
    EstimateGenerateRequest,
    EstimateLineItemResponse,
    EstimateResponse,
    JobStatusResponse,
    PaginatedResponse,
)
from apex.services.background_jobs import process_estimate_generation

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_estimate(
    request: EstimateGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    job_repo: JobRepository = Depends(get_job_repo),
):
    """
    Queue estimate generation as a background job.

    Use GET /jobs/{job_id} to poll status and retrieve results.
    """
    if not project_repo.check_user_access(db, current_user.id, request.project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {request.project_id}",
        )

    project = project_repo.get(db, request.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {request.project_id} not found",
        )

    job = job_repo.create_job(
        db=db,
        job_type="estimate_generation",
        user_id=current_user.id,
        project_id=request.project_id,
    )

    risk_factors_dto = [rf.model_dump() for rf in request.risk_factors]

    logger.info("Queued estimate generation job %s for project %s", job.id, request.project_id)
    if config.TESTING:
        # In test mode, run inline to avoid background task timing issues
        await process_estimate_generation(
            job.id,
            request.project_id,
            risk_factors_dto,
            request.confidence_level,
            request.monte_carlo_iterations,
            current_user.id,
        )
    else:
        asyncio.create_task(
            process_estimate_generation(
                job.id,
                request.project_id,
                risk_factors_dto,
                request.confidence_level,
                request.monte_carlo_iterations,
                current_user.id,
            )
        )

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


@router.get("/{estimate_id}", response_model=EstimateDetailResponse)
def get_estimate(
    estimate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    estimate_repo: EstimateRepository = Depends(get_estimate_repo),
):
    """
    Get estimate details with all related entities.

    Returns:
    - Estimate summary (base cost, risk-adjusted costs, AACE class)
    - Line items (full CBS/WBS hierarchy)
    - Assumptions
    - Exclusions
    - Risk factors

    Requires user to have access to the parent project.
    """
    # Get estimate with details
    estimate = estimate_repo.get_estimate_with_details(db, estimate_id)
    if not estimate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Estimate {estimate_id} not found",
        )

    # Check user access to project
    if not project_repo.check_user_access(db, current_user.id, estimate.project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {estimate.project_id}",
        )

    # Convert to response schema
    return EstimateDetailResponse(
        id=estimate.id,
        project_id=estimate.project_id,
        estimate_number=estimate.estimate_number,
        aace_class=estimate.aace_class,
        base_cost=estimate.base_cost,
        contingency_percentage=estimate.contingency_percentage,
        p50_cost=estimate.p50_cost,
        p80_cost=estimate.p80_cost,
        p95_cost=estimate.p95_cost,
        narrative=estimate.narrative,
        created_at=estimate.created_at,
        created_by_id=estimate.created_by_id,
        line_items=[
            EstimateLineItemResponse(
                id=item.id,
                parent_line_item_id=item.parent_line_item_id,
                cost_code_id=item.cost_code_id,
                description=item.description,
                quantity=item.quantity,
                unit_of_measure=item.unit_of_measure,
                unit_cost_total=item.unit_cost_total,
                total_cost=item.total_cost,
                wbs_code=item.wbs_code,
            )
            for item in estimate.line_items
        ],
        assumptions=[a.assumption_text for a in estimate.assumptions],
        exclusions=[e.exclusion_text for e in estimate.exclusions],
        risk_factors=[
            {
                "factor_name": rf.factor_name,
                "distribution": rf.distribution,
                "param_min": rf.param_min,
                "param_likely": rf.param_likely,
                "param_max": rf.param_max,
            }
            for rf in estimate.risk_factors
        ],
    )


@router.get("/projects/{project_id}/estimates", response_model=PaginatedResponse[EstimateResponse])
def list_project_estimates(
    project_id: UUID,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    estimate_repo: EstimateRepository = Depends(get_estimate_repo),
):
    """
    List estimates for a project with pagination.

    Returns summary information only (no line items, assumptions, etc.).
    Use GET /estimates/{estimate_id} for full details.

    Requires user to have access to the project.
    """
    # Check user access to project
    if not project_repo.check_user_access(db, current_user.id, project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {project_id}",
        )

    # Verify project exists
    project = project_repo.get(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Get paginated estimates
    items, total, has_next, has_prev = estimate_repo.get_paginated(
        db=db,
        project_id=project_id,
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
        has_prev=has_prev,
    )


@router.get("/{estimate_id}/export")
def export_estimate(
    estimate_id: UUID,
    format: str = Query("json", pattern="^(json)$", description="Export format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    estimate_repo: EstimateRepository = Depends(get_estimate_repo),
):
    """
    Export estimate in JSON format.

    Format:
    - json: Full estimate with all details including line items, assumptions, exclusions,
      and risk factors

    Future enhancements will include CSV and PDF export formats.

    Requires user to have access to the parent project.
    """
    # Get estimate with details
    estimate = estimate_repo.get_estimate_with_details(db, estimate_id)
    if not estimate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Estimate {estimate_id} not found",
        )

    # Check user access to project
    if not project_repo.check_user_access(db, current_user.id, estimate.project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {estimate.project_id}",
        )

    # Return full estimate as JSON (only format currently supported)
    return {
        "estimate": {
            "id": str(estimate.id),
            "project_id": str(estimate.project_id),
            "estimate_number": estimate.estimate_number,
            "aace_class": estimate.aace_class.value,
            "base_cost": float(estimate.base_cost),
            "contingency_percentage": estimate.contingency_percentage,
            "p50_cost": float(estimate.p50_cost) if estimate.p50_cost else None,
            "p80_cost": float(estimate.p80_cost) if estimate.p80_cost else None,
            "p95_cost": float(estimate.p95_cost) if estimate.p95_cost else None,
            "narrative": estimate.narrative,
            "created_at": estimate.created_at.isoformat(),
        },
        "line_items": [
            {
                "id": str(item.id),
                "parent_line_item_id": str(item.parent_line_item_id)
                if item.parent_line_item_id
                else None,
                "wbs_code": item.wbs_code,
                "description": item.description,
                "quantity": item.quantity,
                "unit_of_measure": item.unit_of_measure,
                "unit_cost_total": float(item.unit_cost_total),
                "total_cost": float(item.total_cost),
            }
            for item in estimate.line_items
        ],
        "assumptions": [a.assumption_text for a in estimate.assumptions],
        "exclusions": [e.exclusion_text for e in estimate.exclusions],
        "risk_factors": [
            {
                "factor_name": rf.factor_name,
                "distribution": rf.distribution,
                "param_min": rf.param_min,
                "param_likely": rf.param_likely,
                "param_max": rf.param_max,
            }
            for rf in estimate.risk_factors
        ],
    }
