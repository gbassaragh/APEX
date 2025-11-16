"""
Pydantic schemas for API request/response DTOs.

Includes pagination, error responses, and domain models.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from apex.models.enums import AACEClass, ProjectStatus, TerrainType, ValidationStatus

# Generic type for pagination
T = TypeVar("T")


# Pagination Schemas


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated response wrapper.

    All list endpoints must use this schema.
    """

    items: List[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool

    model_config = {"from_attributes": True}


# Error Schemas


class ValidationError(BaseModel):
    """Validation error detail."""

    field: str
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """
    Standard error response schema.

    All non-2xx responses must adhere to this structure.
    """

    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    validation_errors: Optional[List[ValidationError]] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# User Schemas


class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user."""

    aad_object_id: str


class UserResponse(UserBase):
    """User response schema."""

    id: UUID
    aad_object_id: str

    model_config = {"from_attributes": True}


# Project Schemas


class ProjectBase(BaseModel):
    """Base project schema."""

    project_number: str
    project_name: str
    voltage_level: Optional[int] = Field(
        None, gt=0, description="Voltage level in kV (must be positive)"
    )
    line_miles: Optional[float] = Field(
        None, ge=0, description="Line length in miles (must be non-negative)"
    )
    terrain_type: Optional[TerrainType] = None


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project (all fields optional)."""

    project_name: Optional[str] = None
    voltage_level: Optional[int] = None
    line_miles: Optional[float] = None
    terrain_type: Optional[TerrainType] = None
    status: Optional[ProjectStatus] = None


class ProjectResponse(ProjectBase):
    """Project response schema."""

    id: UUID
    status: ProjectStatus
    created_at: datetime
    created_by_id: UUID

    model_config = {"from_attributes": True}


# Project Access Control Schemas


class ProjectAccessGrant(BaseModel):
    """Schema for granting project access."""

    user_id: UUID
    role_id: int = Field(..., ge=1, le=3, description="1=Estimator, 2=Manager, 3=Auditor")


class ProjectAccessRevoke(BaseModel):
    """Schema for revoking project access."""

    user_id: UUID
    role_id: Optional[int] = Field(
        None, ge=1, le=3, description="Specific role to revoke, or None for all roles"
    )


class ProjectAccessResponse(BaseModel):
    """Response schema for project access operations."""

    project_id: UUID
    user_id: UUID
    role_id: int
    granted: bool = True

    model_config = {"from_attributes": True}


# Document Schemas


class DocumentBase(BaseModel):
    """Base document schema."""

    document_type: str
    blob_path: str


class DocumentCreate(DocumentBase):
    """Schema for creating a document."""

    pass


class DocumentUploadResponse(BaseModel):
    """Response schema for document upload."""

    id: UUID
    project_id: UUID
    document_type: str
    blob_path: str
    validation_status: ValidationStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(DocumentBase):
    """Document response schema."""

    id: UUID
    project_id: UUID
    validation_status: ValidationStatus
    completeness_score: Optional[int] = Field(None, ge=0, le=100)
    validation_result: Optional[Dict[str, Any]] = None
    created_at: datetime
    created_by_id: UUID

    model_config = {"from_attributes": True}


class DocumentValidationResult(BaseModel):
    """Schema for document validation results."""

    document_id: UUID
    validation_status: ValidationStatus
    completeness_score: Optional[int] = Field(None, ge=0, le=100)
    issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    suitable_for_estimation: bool


# Estimate Schemas


class EstimateLineItemBase(BaseModel):
    """Base line item schema."""

    description: str
    quantity: float
    unit_of_measure: str
    unit_cost_total: Decimal
    total_cost: Decimal
    wbs_code: Optional[str] = None


class EstimateLineItemResponse(EstimateLineItemBase):
    """Line item response schema."""

    id: UUID
    parent_line_item_id: Optional[UUID] = None
    cost_code_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class RiskFactorInput(BaseModel):
    """Input schema for Monte Carlo risk factors."""

    name: str
    distribution: str  # "triangular", "normal", "uniform", "lognormal", "pert"
    min_value: Optional[float] = None
    most_likely: Optional[float] = None
    max_value: Optional[float] = None
    mean: Optional[float] = None
    std_dev: Optional[float] = None


class EstimateGenerateRequest(BaseModel):
    """Request schema for estimate generation."""

    project_id: UUID
    risk_factors: List[RiskFactorInput] = Field(default_factory=list)
    confidence_level: float = Field(default=0.80, ge=0.0, le=1.0)
    monte_carlo_iterations: int = Field(default=10000, ge=1000, le=100000)


class EstimateBase(BaseModel):
    """Base estimate schema."""

    estimate_number: str
    aace_class: AACEClass
    base_cost: Decimal
    contingency_percentage: Optional[float] = None


class EstimateResponse(EstimateBase):
    """Estimate response schema."""

    id: UUID
    project_id: UUID
    p50_cost: Optional[Decimal] = None
    p80_cost: Optional[Decimal] = None
    p95_cost: Optional[Decimal] = None
    narrative: Optional[str] = None
    created_at: datetime
    created_by_id: UUID

    model_config = {"from_attributes": True}


class EstimateDetailResponse(EstimateResponse):
    """Detailed estimate response with related entities."""

    line_items: List[EstimateLineItemResponse] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# AACE Classification Schemas


class AACEClassificationResult(BaseModel):
    """Result of AACE classification analysis."""

    aace_class: AACEClass
    accuracy_range: str  # e.g., "±20%"
    justification: List[str]
    recommendations: List[str]


# Monte Carlo Risk Analysis Schemas


class MonteCarloResult(BaseModel):
    """Result of Monte Carlo risk analysis."""

    base_cost: float
    mean_cost: float
    std_dev: float
    percentiles: Dict[str, float]  # e.g., {"p50": 100000, "p80": 120000}
    min_cost: float
    max_cost: float
    iterations: int
    risk_factors_applied: List[str]
    sensitivities: Dict[str, float]  # Factor name -> Spearman correlation


# Cost Database Schemas


class CostCodeResponse(BaseModel):
    """Cost code response schema."""

    id: UUID
    code: str
    description: str
    unit_of_measure: Optional[str] = None
    source_database: str

    model_config = {"from_attributes": True}


# Audit Log Schemas


class AuditLogResponse(BaseModel):
    """Audit log response schema."""

    id: UUID
    user_id: UUID
    action: str
    timestamp: datetime
    project_id: Optional[UUID] = None
    estimate_id: Optional[UUID] = None
    llm_model_version: Optional[str] = None
    tokens_used: Optional[int] = None

    model_config = {"from_attributes": True}


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
