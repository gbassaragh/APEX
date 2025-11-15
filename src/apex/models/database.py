"""
SQLAlchemy ORM models for APEX database schema.

CRITICAL: All analytical data must be in normalized tables, NOT JSON blobs.
JSON is only allowed for audit trails and validation results.
"""
import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects import mssql, postgresql
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import CHAR, TypeDecorator

from apex.models.enums import AACEClass, ProjectStatus, TerrainType, ValidationStatus

# Base class for all models
Base = declarative_base()


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.

    - Uses UNIQUEIDENTIFIER on SQL Server (mssql)
    - Uses UUID on Postgres (postgresql)
    - Uses CHAR(36) elsewhere (e.g., SQLite for tests)

    This ensures backend-agnostic UUID handling.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """Load the appropriate dialect-specific type."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID())
        if dialect.name == "mssql":
            return dialect.type_descriptor(mssql.UNIQUEIDENTIFIER())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        """Convert Python UUID to database format."""
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            # This validates that the value is a valid UUID representation
            value = uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        """Convert database value to Python UUID."""
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        # Handle cases where the driver returns bytes (e.g., mssql)
        if isinstance(value, bytes):
            return uuid.UUID(bytes_le=value)
        return uuid.UUID(value)


# User & Access Control Models


class User(Base):
    """
    Application user linked to Azure AD.

    Uses AAD Object ID for authentication correlation.
    """

    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    aad_object_id = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))

    # Relationships
    project_access = relationship("ProjectAccess", back_populates="user")


class AppRole(Base):
    """
    Application-level roles for RBAC.

    Typical roles: Estimator, Manager, Auditor
    """

    __tablename__ = "app_roles"

    id = Column(Integer, primary_key=True)
    role_name = Column(String(50), unique=True, nullable=False)


class ProjectAccess(Base):
    """
    Junction table for User-Project-Role access control.

    Implements application-level RBAC.
    AAD token alone is not sufficient for data access.
    """

    __tablename__ = "project_access"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    project_id = Column(GUID, ForeignKey("projects.id"), nullable=False)
    app_role_id = Column(Integer, ForeignKey("app_roles.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="project_access")
    project = relationship("Project", back_populates="access_control")
    app_role = relationship("AppRole")

    # Table constraints
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "project_id",
            "app_role_id",
            name="uq_project_access_user_project_role",
        ),
        Index("ix_project_access_user_project", "user_id", "project_id"),
    )


# Project & Document Models


class Project(Base):
    """
    Utility transmission/distribution project master record.

    Contains project-level parameters used for cost estimation.
    """

    __tablename__ = "projects"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_number = Column(String(50), unique=True, nullable=False, index=True)
    project_name = Column(String(255), nullable=False)

    # Project parameters
    voltage_level = Column(Integer)  # kV
    line_miles = Column(Float)
    terrain_type = Column(SAEnum(TerrainType))

    # Status tracking
    status = Column(SAEnum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False)

    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = Column(GUID, ForeignKey("users.id"), nullable=False)

    # Relationships
    documents = relationship("Document", back_populates="project")
    estimates = relationship("Estimate", back_populates="project")
    audit_logs = relationship("AuditLog", back_populates="project")
    access_control = relationship("ProjectAccess", back_populates="project")


class Document(Base):
    """
    Project document with validation status.

    Stores blob path only (not binary content).
    JSON validation_result allowed for audit/display purposes.
    """

    __tablename__ = "documents"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id"), nullable=False)
    document_type = Column(String(50), nullable=False)  # "scope", "engineering", "schedule", "bid"
    blob_path = Column(String(500), nullable=False)

    # Validation status
    validation_status = Column(
        SAEnum(ValidationStatus), default=ValidationStatus.PENDING, nullable=False
    )
    completeness_score = Column(Integer)  # 0–100

    # JSON acceptable here for audit/display, NOT analytical data
    validation_result = Column(JSON)

    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = Column(GUID, ForeignKey("users.id"), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="documents")


# Estimate & Cost Breakdown Models


class Estimate(Base):
    """
    Cost estimate master record with AACE classification.

    Contains cost summary and risk analysis results.
    Detailed cost breakdown in EstimateLineItem (relational, not JSON).
    """

    __tablename__ = "estimates"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id"), nullable=False)
    estimate_number = Column(String(50), unique=True, nullable=False, index=True)

    # AACE classification
    aace_class = Column(SAEnum(AACEClass), nullable=False)

    # Cost summary
    base_cost = Column(Numeric(15, 2), nullable=False)
    contingency_percentage = Column(Float)

    # Risk analysis results
    p50_cost = Column(Numeric(15, 2))
    p80_cost = Column(Numeric(15, 2))
    p95_cost = Column(Numeric(15, 2))
    risk_distribution_blob_path = Column(String(500))  # Path to Parquet/CSV with full distribution

    # LLM-generated content
    narrative = Column(Text)
    llm_model_version = Column(String(50))

    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = Column(GUID, ForeignKey("users.id"), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="estimates")
    line_items = relationship(
        "EstimateLineItem", back_populates="estimate", cascade="all, delete-orphan"
    )
    assumptions = relationship(
        "EstimateAssumption", back_populates="estimate", cascade="all, delete-orphan"
    )
    exclusions = relationship(
        "EstimateExclusion", back_populates="estimate", cascade="all, delete-orphan"
    )
    risk_factors = relationship(
        "EstimateRiskFactor", back_populates="estimate", cascade="all, delete-orphan"
    )
    audit_logs = relationship("AuditLog", back_populates="estimate")


class CostCode(Base):
    """
    Standard cost code master (e.g., RSMeans codes).

    Used for consistent cost item classification.
    """

    __tablename__ = "cost_codes"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "22.01.03"
    description = Column(String(255), nullable=False)
    unit_of_measure = Column(String(20))  # "EA", "LF", etc.
    source_database = Column(String(50), default="RSMeans")


class EstimateLineItem(Base):
    """
    Individual cost breakdown line item (CBS/WBS hierarchy).

    CRITICAL: Relational structure, NOT JSON.
    Supports parent-child hierarchy via parent_line_item_id.
    """

    __tablename__ = "estimate_line_items"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), nullable=False, index=True)
    cost_code_id = Column(GUID, ForeignKey("cost_codes.id"), nullable=True, index=True)

    # Hierarchy support
    parent_line_item_id = Column(
        GUID,
        ForeignKey("estimate_line_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    wbs_code = Column(String(50), index=True)  # For deterministic parent mapping

    # Line item details
    description = Column(String(500), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_of_measure = Column(String(20), nullable=False)

    # Cost breakdown
    unit_cost_material = Column(Numeric(15, 2))
    unit_cost_labor = Column(Numeric(15, 2))
    unit_cost_other = Column(Numeric(15, 2))
    unit_cost_total = Column(Numeric(15, 2), nullable=False)
    total_cost = Column(Numeric(15, 2), nullable=False)

    # Relationships
    estimate = relationship("Estimate", back_populates="line_items")
    cost_code = relationship("CostCode")
    parent = relationship(
        "EstimateLineItem",
        back_populates="children",
        remote_side=[id],  # Correct: use column attribute, not string
    )
    children = relationship(
        "EstimateLineItem",
        back_populates="parent",
        cascade="all, delete-orphan",  # Cascade deletes to children
    )


class EstimateAssumption(Base):
    """
    Estimate assumptions for transparency and audit trail.
    """

    __tablename__ = "estimate_assumptions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), nullable=False, index=True)
    assumption_text = Column(Text, nullable=False)
    category = Column(String(100))

    # Relationship
    estimate = relationship("Estimate", back_populates="assumptions")


class EstimateExclusion(Base):
    """
    Estimate exclusions for scope clarity.
    """

    __tablename__ = "estimate_exclusions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), nullable=False, index=True)
    exclusion_text = Column(Text, nullable=False)
    category = Column(String(100))

    # Relationship
    estimate = relationship("Estimate", back_populates="exclusions")


class EstimateRiskFactor(Base):
    """
    Risk factors for Monte Carlo analysis.

    CRITICAL: Relational structure, NOT JSON.
    Each factor stored separately for queryability.
    """

    __tablename__ = "estimate_risk_factors"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), nullable=False, index=True)

    factor_name = Column(String(255), nullable=False)
    distribution = Column(
        String(50), nullable=False
    )  # "triangular", "normal", "uniform", "lognormal", "pert"

    # Distribution parameters
    param_min = Column(Float)
    param_likely = Column(Float)
    param_max = Column(Float)
    param_mean = Column(Float)
    param_std_dev = Column(Float)

    # Relationship
    estimate = relationship("Estimate", back_populates="risk_factors")


# Audit Trail


class AuditLog(Base):
    """
    Comprehensive audit trail for regulatory compliance.

    Tracks all significant operations with user attribution.
    JSON details acceptable for audit purposes.
    """

    __tablename__ = "audit_logs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id"), index=True)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), index=True)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)

    action = Column(String(100), nullable=False)  # "created", "validated", "estimated", etc.
    details = Column(JSON)  # Arbitrary audit data (non-analytical)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # LLM usage tracking
    llm_model_version = Column(String(50))
    tokens_used = Column(Integer)

    # Relationships
    project = relationship("Project", back_populates="audit_logs")
    estimate = relationship("Estimate", back_populates="audit_logs")
