"""
Estimate generation and retrieval endpoints.

Handles full estimate orchestration workflow including:
- AACE classification
- Cost breakdown structure generation
- Monte Carlo risk analysis
- LLM narrative generation
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from apex.database.repositories.audit_repository import AuditRepository
from apex.database.repositories.estimate_repository import EstimateRepository
from apex.database.repositories.project_repository import ProjectRepository
from apex.dependencies import (
    get_audit_repo,
    get_current_user,
    get_db,
    get_estimate_generator,
    get_estimate_repo,
    get_project_repo,
)
from apex.models.database import User
from apex.models.schemas import (
    EstimateDetailResponse,
    EstimateGenerateRequest,
    EstimateLineItemResponse,
    EstimateResponse,
    PaginatedResponse,
)
from apex.services.estimate_generator import EstimateGenerator

router = APIRouter()


@router.post(
    "/generate", response_model=EstimateDetailResponse, status_code=status.HTTP_201_CREATED
)
def generate_estimate(
    request: EstimateGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    estimate_repo: EstimateRepository = Depends(get_estimate_repo),
    estimate_generator: EstimateGenerator = Depends(get_estimate_generator),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """
    Generate new estimate for a project.

    This is a long-running synchronous operation that may take 30s-5min depending on:
    - Number of documents to analyze
    - Complexity of cost breakdown structure
    - Monte Carlo simulation iterations
    - LLM narrative generation time

    Workflow:
    1. Load project & documents
    2. Check user access (ProjectAccess table)
    3. Derive completeness + maturity → AACEClassifier.classify()
    4. CostDatabaseService.compute_base_cost() → (base_cost, line_items)
    5. Build RiskFactor objects, run Monte Carlo → risk_results
    6. Compute contingency percentage from P_target vs base
    7. Call LLMOrchestrator to generate narrative, assumptions, exclusions
    8. Build ORM entities (Estimate, EstimateRiskFactor, EstimateAssumption, EstimateExclusion)
    9. Call estimate_repo.create_estimate_with_hierarchy() to persist in one transaction
    10. Create AuditLog
    11. Return Estimate entity with full details

    NOTE: This is currently synchronous. Future enhancement will use background job pattern
    with polling endpoint for status.
    """
    # Check user access to project
    if not project_repo.check_user_access(db, current_user.id, request.project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to project {request.project_id}",
        )

    # Verify project exists
    project = project_repo.get_by_id(db, request.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {request.project_id} not found",
        )

    # Convert RiskFactorInput DTOs to internal RiskFactor objects
    risk_factors_dto = [rf.model_dump() for rf in request.risk_factors]

    try:
        # Call main orchestration service
        # This executes the full 14-step workflow
        estimate = estimate_generator.generate_estimate(
            db=db,
            project_id=request.project_id,
            risk_factors_dto=risk_factors_dto,
            confidence_level=request.confidence_level,
            monte_carlo_iterations=request.monte_carlo_iterations,
            user=current_user,
        )

        # Load estimate with all details for response
        estimate_with_details = estimate_repo.get_estimate_with_details(db, estimate.id)

        # Convert to response schema
        return EstimateDetailResponse(
            id=estimate_with_details.id,
            project_id=estimate_with_details.project_id,
            estimate_number=estimate_with_details.estimate_number,
            aace_class=estimate_with_details.aace_class,
            base_cost=estimate_with_details.base_cost,
            contingency_percentage=estimate_with_details.contingency_percentage,
            p50_cost=estimate_with_details.p50_cost,
            p80_cost=estimate_with_details.p80_cost,
            p95_cost=estimate_with_details.p95_cost,
            narrative=estimate_with_details.narrative,
            created_at=estimate_with_details.created_at,
            created_by_id=estimate_with_details.created_by_id,
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
                for item in estimate_with_details.line_items
            ],
            assumptions=[a.assumption_text for a in estimate_with_details.assumptions],
            exclusions=[e.exclusion_text for e in estimate_with_details.exclusions],
            risk_factors=[
                {
                    "factor_name": rf.factor_name,
                    "distribution": rf.distribution,
                    "param_min": rf.param_min,
                    "param_likely": rf.param_likely,
                    "param_max": rf.param_max,
                }
                for rf in estimate_with_details.risk_factors
            ],
        )

    except Exception as exc:
        # Log failure and raise
        audit_repo.create(
            db,
            {
                "project_id": request.project_id,
                "user_id": current_user.id,
                "action": "estimate_generation_failed",
                "details": {"error": str(exc)},
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Estimate generation failed: {str(exc)}",
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
    project = project_repo.get_by_id(db, project_id)
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
    format: str = Query("json", pattern="^(json|csv|pdf)$", description="Export format"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    estimate_repo: EstimateRepository = Depends(get_estimate_repo),
):
    """
    Export estimate in various formats.

    Formats:
    - json: Full estimate with all details (default)
    - csv: Flattened line items with cost breakdown
    - pdf: Professional estimate report (future enhancement)

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

    if format == "json":
        # Return full estimate as JSON
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

    elif format == "csv":
        # Return flattened line items as CSV
        # TODO: Implement CSV generation with proper headers
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="CSV export not yet implemented",
        )

    elif format == "pdf":
        # Return professional PDF report
        # TODO: Implement PDF generation
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="PDF export not yet implemented",
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format: {format}. Must be one of: json, csv, pdf",
        )
