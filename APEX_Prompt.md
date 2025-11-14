````markdown
# APEX – AI-Powered Estimation Expert  
**Final Development & Orchestration Specification (APEX_Prompt.md)**

---

## 0. Developer Contract (Non-Negotiable)

You are an AI coding assistant working under the supervision of a human lead engineer.

**You MUST:**

1. **Implement this specification exactly.**
   - Follow the **data model**, **service interfaces**, and **orchestration flows** as written.
   - Do **not** simplify, “toy-ify”, or replace any core component with a dummy implementation.

2. **Respect all “MUST / MUST NOT / PROHIBITED” rules.**
   - If any instruction here conflicts with your defaults or boilerplate, this spec wins.

3. **Do not introduce:**
   - Ad-hoc JSON blobs in place of normalized tables.
   - Inline secrets, static keys, or non-Managed Identity auth.
   - Random helper frameworks (Celery, Redis, etc.) not mentioned here.

4. **High-risk areas flagged for human review:**
   - Correlation implementation for Monte Carlo risk (`_apply_iman_conover`).
   - CBS hierarchy hand-off (temporary parent references → persisted GUIDs).

These areas **must** produce clear, testable code and are expected to be reviewed and validated by a human before production use.

When in doubt between a simpler “toy” shortcut and the more complex specification here, **choose the specification**.

---

## 1. Naming & Purpose

**Platform Name:**  
APEX – *AI-Powered Estimation Expert*

**Purpose:**  
Enterprise estimation platform for utility **transmission and distribution** projects. APEX automates:

- Intelligent document ingestion (complex PDFs, scanned docs, Word, Excel).
- AI-based document validation for completeness & contradictions.
- AACE-compliant estimate classification (Class 1–5) based on project maturity.
- Industrial-grade Monte Carlo risk analysis (with correlation and sensitivity).
- Relational, queryable cost breakdown (CBS/WBS), not JSON blobs.
- Full audit trail suitable for ISO-NE / regulatory submissions.

**Primary Users:**  
Utility cost estimating team (~30 estimators) plus managers/auditors.

---

## 2. Technology Stack & Dependencies

### 2.1 Core Platform

- **Language:** Python 3.11+
- **API Framework:** FastAPI
- **Database:** Azure SQL Database (SQLAlchemy + Alembic)
- **Object Storage:** Azure Blob Storage
- **LLM:** Azure OpenAI (GPT-4 family)
- **Document Parsing:** Azure AI Document Intelligence (formerly Form Recognizer)
- **Auth to Azure services:** Azure AD Managed Identity (MSI)
- **Runtime:** Azure Container Apps (backend) + Azure Functions (offload/document processing)
- **Observability:** Azure Application Insights (via opencensus-ext-azure)

### 2.2 Mandatory Python Packages (Conceptual List)

The project uses **pyproject.toml** as the single source of dependency truth. Root-level `requirements.txt` is **prohibited** as a primary dependency source.

Core / Web:

- `fastapi`
- `uvicorn[standard]`
- `pydantic`
- `pydantic-settings`
- `sqlalchemy`
- `alembic`
- `pyodbc`

Azure & LLM:

- `azure-identity`
- `azure-storage-blob`
- `azure-keyvault-secrets`
- `openai`  (Azure OpenAI SDK)
- `azure-ai-documentintelligence`  *(mandatory for PDF/scanned parsing)*

Risk & Data:

- `numpy`
- `scipy`              *(for qmc.LatinHypercube, distributions, etc.)*
- `statsmodels`        *(for correlation / rank correlations)*
- `SALib`              *(for sensitivity analysis, e.g., Sobol)*

Document Parsing (non-PDF):

- `openpyxl`           *(Excel)*
- `python-docx`        *(Word)*

Utilities & Testing:

- `python-multipart`
- `httpx`
- `pytest`
- `pytest-asyncio`
- `opencensus-ext-azure`
- `black`
- `isort`
- `flake8`
- `tenacity`           *(for retries)*
- (Optional) `tiktoken` *(token counting in LLM orchestrator)*

### 2.3 Prohibited & Replaced Packages

- **`mcerp` is prohibited.** It is outdated and incompatible with modern NumPy/SciPy.
- Correlation and sampling are implemented using:
  - `scipy.stats.qmc` (Latin Hypercube Sampling / quasi-random)
  - Custom Iman-Conover correlation using `numpy` and `scipy.stats`
  - `SALib` / `statsmodels` for sensitivity analysis and rank correlations.

- **`PyPDF2` is prohibited for text/table extraction.**  
  - It may be used **only** for simple PDF operations (e.g., splitting), not for extraction.
  - All text/table/layout extraction from PDFs **must** go through Azure AI Document Intelligence.

---

## 3. Project Structure

Generate **exactly** this structure (paths and names are binding):

```text
apex/
├── src/
│   ├── apex/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app
│   │   ├── config.py               # Pydantic settings
│   │   ├── dependencies.py         # DI wiring, DB sessions, current_user, etc.
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py
│   │   │   │   ├── projects.py
│   │   │   │   ├── documents.py
│   │   │   │   ├── estimates.py
│   │   │   │   └── health.py
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── enums.py
│   │   │   ├── database.py         # SQLAlchemy ORM models
│   │   │   └── schemas.py          # Pydantic schemas/DTOs (incl. ErrorResponse, pagination)
│   │   │
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py       # engine + SessionLocal
│   │   │   ├── repositories/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py         # Optional: common CRUD + pagination helpers
│   │   │   │   ├── project_repository.py
│   │   │   │   ├── document_repository.py
│   │   │   │   ├── estimate_repository.py
│   │   │   │   └── audit_repository.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── llm/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── orchestrator.py  # Maturity-aware LLM orchestrator (NO toy client)
│   │   │   │   ├── prompts.py
│   │   │   │   └── validators.py
│   │   │   ├── document_parser.py   # Hybrid pipeline using Azure Document Intelligence
│   │   │   ├── cost_database.py     # CostDatabaseService
│   │   │   ├── risk_analysis.py     # Industrial-grade Monte Carlo engine
│   │   │   ├── aace_classifier.py
│   │   │   └── estimate_generator.py
│   │   │
│   │   ├── azure/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py             # Managed Identity helpers
│   │   │   ├── blob_storage.py     # Blob client abstractions
│   │   │   └── key_vault.py        # Key Vault integration (optional)
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── logging.py          # Structured logging to App Insights
│   │       ├── errors.py           # BusinessRuleViolation, etc.
│   │       ├── retry.py            # Azure retry decorators
│   │       └── middleware.py       # Request ID middleware, etc.
│   │
│   └── functions/
│       └── document_processor/
│           ├── __init__.py
│           ├── function_app.py     # Azure Function entrypoint (stub OK)
│           └── host.json
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── sample_project.pdf
│   │   ├── sample_scope.docx
│   │   └── azure_mocks.py
│   ├── unit/
│   │   ├── test_risk_analysis.py
│   │   ├── test_document_parser.py
│   │   ├── test_aace_classifier.py
│   │   └── test_cost_database_service.py
│   └── integration/
│       ├── test_api_projects.py
│       ├── test_api_documents.py
│       └── test_api_estimates.py
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── pyproject.toml              # Single source of dependency truth
├── .env.example
├── .gitignore
└── README.md
````

> **Reminder to AI:** Do **not** create a root `requirements.txt` as the primary dependency list. If you need a lock file, use `poetry.lock`, `pdm.lock`, or a generated `requirements.lock` from pyproject.

---

## 4. Relational Data Model (Non-Negotiable)

### 4.1 Enums (models/enums.py)

Implement (at minimum):

```python
from enum import Enum

class ProjectStatus(str, Enum):
    DRAFT = "draft"
    VALIDATING = "validating"
    VALIDATED = "validated"
    ESTIMATING = "estimating"
    COMPLETE = "complete"
    ARCHIVED = "archived"

class ValidationStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"

class AACEClass(str, Enum):
    CLASS_5 = "class_5"
    CLASS_4 = "class_4"
    CLASS_3 = "class_3"
    CLASS_2 = "class_2"
    CLASS_1 = "class_1"

class TerrainType(str, Enum):
    FLAT = "flat"
    ROLLING = "rolling"
    MOUNTAINOUS = "mountainous"
    URBAN = "urban"
    WETLAND = "wetland"
```

*(You may add descriptions as needed, but these identifiers and basic meaning must remain consistent.)*

### 4.2 GUID TypeDecorator (models/database.py)

Use a **backend-agnostic** GUID type that works with Azure SQL (mssql) and testing backends (e.g., SQLite, Postgres):

```python
import uuid
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects import mssql, postgresql

class GUID(TypeDecorator):
    """
    Platform-independent GUID type.

    - Uses UNIQUEIDENTIFIER on SQL Server.
    - Uses UUID on Postgres.
    - Uses CHAR(36) elsewhere (e.g., SQLite for tests).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID())
        if dialect.name == "mssql":
            return dialect.type_descriptor(mssql.UNIQUEIDENTIFIER())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
```

All primary/foreign key UUIDs **must** use this `GUID` type.

### 4.3 ORM Models (models/database.py)

Only the critical subset is shown; implement all as specified:

#### User & Access Control

```python
from sqlalchemy import Column, String, Integer, DateTime, Enum as SAEnum, ForeignKey, JSON, Float, Numeric, Text
from sqlalchemy.orm import relationship
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    aad_object_id = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))

    project_access = relationship("ProjectAccess", back_populates="user")


class AppRole(Base):
    __tablename__ = "app_roles"

    id = Column(Integer, primary_key=True)
    role_name = Column(String(50), unique=True, nullable=False)  # "Estimator", "Manager", "Auditor"


class ProjectAccess(Base):
    __tablename__ = "project_access"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    project_id = Column(GUID, ForeignKey("projects.id"), nullable=False)
    app_role_id = Column(Integer, ForeignKey("app_roles.id"), nullable=False)

    user = relationship("User", back_populates="project_access")
    project = relationship("Project", back_populates="access_control")
    app_role = relationship("AppRole")
```

#### Project & Document

```python
class Project(Base):
    __tablename__ = "projects"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_number = Column(String(50), unique=True, nullable=False, index=True)
    project_name = Column(String(255), nullable=False)

    voltage_level = Column(Integer)
    line_miles = Column(Float)
    terrain_type = Column(SAEnum(TerrainType))

    status = Column(SAEnum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = Column(GUID, ForeignKey("users.id"), nullable=False)

    documents = relationship("Document", back_populates="project")
    estimates = relationship("Estimate", back_populates="project")
    audit_logs = relationship("AuditLog", back_populates="project")
    access_control = relationship("ProjectAccess", back_populates="project")


class Document(Base):
    __tablename__ = "documents"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id"), nullable=False)
    document_type = Column(String(50), nullable=False)  # "scope", "engineering", "schedule", "bid"
    blob_path = Column(String(500), nullable=False)

    validation_status = Column(SAEnum(ValidationStatus), default=ValidationStatus.PENDING, nullable=False)
    completeness_score = Column(Integer)  # 0–100

    # JSON is acceptable here for audit/display, NOT for analytical cost breakdowns
    validation_result = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = Column(GUID, ForeignKey("users.id"), nullable=False)

    project = relationship("Project", back_populates="documents")
```

#### Estimate & Cost Breakdown

```python
class Estimate(Base):
    __tablename__ = "estimates"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id"), nullable=False)
    estimate_number = Column(String(50), unique=True, nullable=False)

    aace_class = Column(SAEnum(AACEClass), nullable=False)

    # Cost Summary
    base_cost = Column(Numeric(15, 2), nullable=False)
    contingency_percentage = Column(Float)

    # Risk Summary
    p50_cost = Column(Numeric(15, 2))
    p80_cost = Column(Numeric(15, 2))
    p95_cost = Column(Numeric(15, 2))
    risk_distribution_blob_path = Column(String(500))  # Path to Parquet/CSV with full distribution

    # LLM-generated content
    narrative = Column(Text)
    llm_model_version = Column(String(50))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_id = Column(GUID, ForeignKey("users.id"), nullable=False)

    project = relationship("Project", back_populates="estimates")

    # Relational children
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
```

```python
class CostCode(Base):
    __tablename__ = "cost_codes"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "22.01.03"
    description = Column(String(255), nullable=False)
    unit_of_measure = Column(String(20))  # "EA", "LF", etc.
    source_database = Column(String(50), default="RSMeans")
```

```python
class EstimateLineItem(Base):
    __tablename__ = "estimate_line_items"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), nullable=False, index=True)
    cost_code_id = Column(GUID, ForeignKey("cost_codes.id"), nullable=True, index=True)

    parent_line_item_id = Column(GUID, ForeignKey("estimate_line_items.id"), nullable=True, index=True)

    # Optional WBS/CBS code used for deterministic parent mapping
    wbs_code = Column(String(50), index=True)

    description = Column(String(500), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_of_measure = Column(String(20), nullable=False)

    unit_cost_material = Column(Numeric(15, 2))
    unit_cost_labor = Column(Numeric(15, 2))
    unit_cost_other = Column(Numeric(15, 2))
    unit_cost_total = Column(Numeric(15, 2), nullable=False)
    total_cost = Column(Numeric(15, 2), nullable=False)

    estimate = relationship("Estimate", back_populates="line_items")
    cost_code = relationship("CostCode")

    parent = relationship(
        "EstimateLineItem",
        back_populates="children",
        remote_side="EstimateLineItem.id",
    )
    children = relationship("EstimateLineItem", back_populates="parent")
```

```python
class EstimateAssumption(Base):
    __tablename__ = "estimate_assumptions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), nullable=False, index=True)
    assumption_text = Column(Text, nullable=False)
    category = Column(String(100))

    estimate = relationship("Estimate", back_populates="assumptions")


class EstimateExclusion(Base):
    __tablename__ = "estimate_exclusions"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), nullable=False, index=True)
    exclusion_text = Column(Text, nullable=False)
    category = Column(String(100))

    estimate = relationship("Estimate", back_populates="exclusions")


class EstimateRiskFactor(Base):
    __tablename__ = "estimate_risk_factors"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), nullable=False, index=True)

    factor_name = Column(String(255), nullable=False)
    distribution = Column(String(50), nullable=False)  # "triangular", "lognormal", "pert", etc.
    param_min = Column(Float)
    param_likely = Column(Float)
    param_max = Column(Float)
    # Additional parameters (mean, std) can be added as needed.

    estimate = relationship("Estimate", back_populates="risk_factors")
```

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("projects.id"), index=True)
    estimate_id = Column(GUID, ForeignKey("estimates.id"), index=True)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)

    action = Column(String(100), nullable=False)  # "created", "validated", "estimated", etc.
    details = Column(JSON)  # Arbitrary audit data (non-analytical)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    llm_model_version = Column(String(50))
    tokens_used = Column(Integer)

    project = relationship("Project", back_populates="audit_logs")
    estimate = relationship("Estimate", back_populates="audit_logs")
```

> **Rule:** All analytical / aggregatable data (costs, quantities, risk factors) must live in normalized tables. JSON is allowed only where explicitly stated for audit or display.

---

## 5. Configuration, DB Engine & Session Management

### 5.1 Config (config.py)

Implement `Config` via `pydantic-settings`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "APEX"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # "development", "staging", "production"
    DEBUG: bool = False

    # Azure SQL
    AZURE_SQL_SERVER: str
    AZURE_SQL_DATABASE: str
    AZURE_SQL_DRIVER: str = "ODBC Driver 18 for SQL Server"

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_DEPLOYMENT: str
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Storage
    AZURE_STORAGE_ACCOUNT: str
    AZURE_STORAGE_CONTAINER_UPLOADS: str = "uploads"
    AZURE_STORAGE_CONTAINER_PROCESSED: str = "processed"

    # Key Vault (optional)
    AZURE_KEY_VAULT_URL: Optional[str] = None

    # API
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # App Insights
    AZURE_APPINSIGHTS_CONNECTION_STRING: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    # Monte Carlo defaults
    DEFAULT_MONTE_CARLO_ITERATIONS: int = 10000
    DEFAULT_CONFIDENCE_LEVEL: float = 0.80

    @property
    def database_url(self) -> str:
        return (
            f"mssql+pyodbc://@{self.AZURE_SQL_SERVER}/"
            f"{self.AZURE_SQL_DATABASE}"
            f"?driver={self.AZURE_SQL_DRIVER.replace(' ', '+')}"
            f"&Authentication=ActiveDirectoryMsi"
        )

config = Config()
```

### 5.2 DB Engine & Pooling (database/connection.py)

Recommend **stateless / NullPool** for Azure Container Apps:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from apex.config import config

engine = create_engine(
    config.database_url,
    poolclass=NullPool,      # Stateless pattern works well for serverless / ACA
    echo=config.DEBUG,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)
```

> You may introduce a `QueuePool` variant later if you have stable, long-lived processes and clear pooling requirements.

### 5.3 Session Management & FastAPI Dependency (dependencies.py)

**CRITICAL PATTERN** – do not improvise:

```python
from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session
import logging

from apex.database.connection import SessionLocal

logger = logging.getLogger(__name__)

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for DB sessions with proper transaction handling.

    - Opens a session at request start.
    - Commits on successful completion.
    - Rolls back on error.
    - Always closes the session.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as exc:
        logger.error("Database transaction failed: %s", exc)
        db.rollback()
        raise
    finally:
        db.close()
```

> **Rule:** Repositories and services **must not** instantiate `SessionLocal()` directly. They always receive `db: Session` injected from `get_db`.

---

## 6. Security & Network Architecture (Non-Negotiable High-Level Requirements)

These points are architectural **requirements**; code should assume this environment:

* **Zero-Trust Network:**
  All PaaS services (Azure SQL, Blob, OpenAI, Document Intelligence) must have **public network access disabled** and be reachable only via private endpoints.

* **Private Endpoints:**
  Azure Container Apps communicate with:

  * Azure SQL Database
  * Azure Blob Storage
  * Azure OpenAI
  * Azure AI Document Intelligence
    exclusively via **Private Link**.

* **VNet Injection:**
  The Container Apps environment is VNet injected and reachable only inside the VNet (no public exposure except via controlled entry points/API gateway).

* **Managed Identity:**
  All Azure service access (SQL, Storage, Key Vault, OpenAI, Document Intelligence) uses **Managed Identity**. No hardcoded secrets.

* **Application-Level RBAC:**

  * API endpoints must check `User` + `ProjectAccess` + `AppRole` for authorization.
  * Having an AAD token is **not** sufficient to access project data.

* **Compliance:**
  Azure resource group uses an ISO-aligned policy initiative (e.g., ISO/IEC 27001) to enforce encryption, logging, and access control.

---

## 7. LLM Orchestrator (services/llm/orchestrator.py)

The old “flat client” is **prohibited**. Implement a **maturity-aware** orchestrator that selects prompts and tasks based on target AACE class.

### 7.1 Core Responsibilities

* Route LLM calls for:

  * Document validation
  * Structured extraction (when using LLM augmentation)
  * Estimate narrative generation
  * Assumptions & exclusions generation

* Select appropriate:

  * System prompt (persona)
  * User prompt template
  * Temperature and other parameters

* Manage:

  * Token budgeting / truncation
  * Retry logic for transient errors
  * Logging token usage to `AuditLog`

### 7.2 Persona / Task Matrix (Conceptual)

| AACE Class | Persona (System)          | Primary Tasks                                                            | Temp |
| ---------- | ------------------------- | ------------------------------------------------------------------------ | ---- |
| CLASS_5    | Conceptual Estimator      | High-level budget ranges, parametric drivers, key assumptions            | 0.7  |
| CLASS_4    | Feasibility Analyst       | Validate preliminary scope, identify missing sections & gaps             | 0.3  |
| CLASS_3    | Budget Estimator          | Extract quantities, detailed assumptions/exclusions, budget-level detail | 0.1  |
| CLASS_2/1  | Auditor / Check Estimator | Cross-check contractor/Bid vs drawings, flag discrepancies               | 0.0  |

### 7.3 Token Management (Example)

```python
import json
from typing import Dict, Any, Tuple

import tiktoken  # Optional but recommended

class LLMOrchestrator:
    def __init__(self, config: Config, client, logger):
        self.config = config
        self.client = client  # Azure OpenAI client
        self.logger = logger
        self.encoder = tiktoken.encoding_for_model("gpt-4")
        self.max_context_tokens = 128000
        self.response_buffer_tokens = 4000

    def _prepare_doc_payload(
        self,
        system_prompt: str,
        user_prompt: str,
        structured_doc: Dict[str, Any],
    ) -> Tuple[str, bool]:
        """
        Ensures we don't exceed model context window.
        Returns (doc_json, was_truncated).
        """
        base_tokens = len(self.encoder.encode(system_prompt + user_prompt))
        available = self.max_context_tokens - base_tokens - self.response_buffer_tokens

        doc_str = json.dumps(structured_doc)
        doc_tokens = len(self.encoder.encode(doc_str))

        if doc_tokens <= available:
            return doc_str, False

        # TODO (for AI): Implement smart truncation by priority sections.
        truncated_str = self._smart_truncate(structured_doc, available)
        return truncated_str, True

    def _smart_truncate(self, structured_doc: Dict[str, Any], token_budget: int) -> str:
        """
        AI Assistants: implement a simple but deterministic truncation strategy:
        e.g., keep high-priority sections (scope/quantities), drop appendices.
        """
        # Minimal placeholder – must be improved by AI according to actual schema
        subset = {k: structured_doc.get(k) for k in list(structured_doc.keys())[:5]}
        return json.dumps(subset)
```

> LLM calls themselves can use `tenacity`-based retry patterns and optional client-side rate limiting (see Section 18 for advanced options).

---

## 8. Document Parsing Service (services/document_parser.py)

### 8.1 Rules

* **PDFs & scanned docs:** must use Azure AI Document Intelligence.
* `.xlsx` → `openpyxl`; `.docx` → `python-docx`.
* No use of PyPDF2 for data extraction.

### 8.2 Azure Document Intelligence Wrapper (Async Pattern)

```python
from typing import Dict, Any
import asyncio
import logging

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential  # or MSI-based bearer (see azure/auth.py)
from azure.core.exceptions import AzureError

from apex.utils.retry import azure_retry

logger = logging.getLogger(__name__)

class DocumentIntelligenceWrapper:
    """
    Wraps Azure Document Intelligence with proper polling and timeouts.
    """

    def __init__(self, client: DocumentIntelligenceClient, max_wait_seconds: int = 60, poll_interval: int = 2):
        self.client = client
        self.max_wait_seconds = max_wait_seconds
        self.poll_interval = poll_interval

    @azure_retry
    async def analyze_document(
        self,
        document_bytes: bytes,
        model_id: str = "prebuilt-layout",
    ) -> Dict[str, Any]:
        """
        Asynchronous polling pattern for long-running analysis operations.
        """

        poller = self.client.begin_analyze_document(
            model_id=model_id,
            document=document_bytes,
        )

        elapsed = 0
        while not poller.done() and elapsed < self.max_wait_seconds:
            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

        if not poller.done():
            poller.cancel()
            raise TimeoutError(f"Document analysis exceeded {self.max_wait_seconds} seconds")

        result = poller.result()
        return self._extract_structured_content(result)

    def _extract_structured_content(self, result) -> Dict[str, Any]:
        """
        Convert Azure DI result into a normalized internal structure.
        AI must:
        - Extract pages, paragraphs, headings, tables.
        - Preserve table row/column structure.
        """
        # Implement a clear, deterministic structure here.
        raise NotImplementedError("Implement DI result to internal structure mapping.")
```

### 8.3 DocumentParser Service

Implement a higher-level `DocumentParser` that:

* Dispatches based on file type.
* Calls Azure DI for PDF.
* Returns structured JSON that downstream LLM calls use for validation, not raw PDF text.

---

## 9. Industrial-Grade Monte Carlo Risk Analysis (services/risk_analysis.py)

**Toy implementations are prohibited.** Implement:

* Latin Hypercube Sampling (LHS).
* Multiple distributions (triangular, normal, uniform, lognormal, PERT).
* Optional correlation matrix using Iman-Conover.
* Sensitivity metrics (e.g., Spearman rank correlations or SALib).

### 9.1 Data Structures

```python
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np

@dataclass
class RiskFactor:
    name: str
    distribution: str           # "triangular", "normal", "uniform", "lognormal", "pert"
    min_value: float
    most_likely: Optional[float] = None
    max_value: Optional[float] = None
    mean: Optional[float] = None
    std_dev: Optional[float] = None
```

### 9.2 Core Engine Skeleton

```python
from scipy.stats import qmc, norm, triang, lognorm
from scipy.stats import rankdata

class MonteCarloRiskAnalyzer:
    """
    Monte Carlo simulation with:
    - Latin Hypercube Sampling
    - Optional Iman-Conover correlation
    - Sensitivity analysis (e.g., Spearman rank correlation)
    """

    def __init__(self, iterations: int = 10000, random_seed: int = 42):
        self.iterations = iterations
        self.random_seed = random_seed

    def run_analysis(
        self,
        base_cost: float,
        risk_factors: Dict[str, RiskFactor],
        correlation_matrix: Optional[np.ndarray] = None,
        confidence_levels: List[float] = [0.50, 0.80, 0.95],
    ) -> Dict[str, any]:
        np.random.seed(self.random_seed)

        factor_names = list(risk_factors.keys())
        n_vars = len(factor_names)
        sampler = qmc.LatinHypercube(d=n_vars, seed=self.random_seed)
        lhs_samples = sampler.random(self.iterations)  # (iterations, n_vars)

        # Transform samples to desired distributions
        transformed = np.zeros_like(lhs_samples)
        for j, name in enumerate(factor_names):
            factor = risk_factors[name]
            transformed[:, j] = self._transform_samples(lhs_samples[:, j], factor)

        # Apply correlation if matrix provided
        if correlation_matrix is not None:
            transformed = self._apply_iman_conover(transformed, correlation_matrix)

        # Compute total multipliers and costs
        total_multipliers = 1.0 + transformed.sum(axis=1)
        risk_adjusted_costs = base_cost * total_multipliers

        # Compute percentiles
        percentiles = {}
        for level in confidence_levels:
            value = float(np.percentile(risk_adjusted_costs, level * 100))
            percentiles[f"p{int(level * 100)}"] = round(value, 2)

        mean_cost = float(np.mean(risk_adjusted_costs))
        std_dev = float(np.std(risk_adjusted_costs))

        # Sensitivity (Spearman rank correlation)
        sensitivities = self._compute_spearman_sensitivity(transformed, risk_adjusted_costs, factor_names)

        return {
            "base_cost": base_cost,
            "mean_cost": round(mean_cost, 2),
            "std_dev": round(std_dev, 2),
            "percentiles": percentiles,
            "min_cost": round(float(np.min(risk_adjusted_costs)), 2),
            "max_cost": round(float(np.max(risk_adjusted_costs)), 2),
            "iterations": self.iterations,
            "risk_factors_applied": factor_names,
            "sensitivities": sensitivities,   # For Tornado charts
        }

    def _transform_samples(self, u: np.ndarray, factor: RiskFactor) -> np.ndarray:
        """
        Transform uniform [0,1] samples into appropriate distribution deltas (e.g., cost multipliers).
        AI must implement triangular, normal, uniform, lognormal, and PERT behavior.
        """
        # Placeholder; must be implemented according to factor.distribution
        raise NotImplementedError

    def _apply_iman_conover(self, samples: np.ndarray, correlation_matrix: np.ndarray) -> np.ndarray:
        """
        Apply Iman-Conover to induce correlation while preserving marginals.

        HIGH-RISK FUNCTION: This implementation MUST be reviewed by a human
        and validated against known cases from a trusted tool (e.g., @RISK)
        before being used in production.
        """
        n_samples, n_vars = samples.shape

        # 1. Rank-transform original samples
        ranked = np.apply_along_axis(rankdata, 0, samples)

        # 2. Generate correlated normal scores
        L = np.linalg.cholesky(correlation_matrix)
        normals = norm.ppf((ranked - 0.5) / n_samples)
        correlated = normals @ L.T

        # 3. Rank correlated normals
        correlated_ranks = np.apply_along_axis(rankdata, 0, correlated)

        # 4. Map correlated ranks back onto sorted original samples
        result = np.zeros_like(samples)
        for j in range(n_vars):
            order = np.argsort(correlated_ranks[:, j])
            sorted_original = np.sort(samples[:, j])
            result[:, j] = sorted_original[order]

        return result

    def _compute_spearman_sensitivity(
        self,
        factor_samples: np.ndarray,
        total_costs: np.ndarray,
        factor_names: List[str],
    ) -> Dict[str, float]:
        """
        Compute Spearman rank correlation coefficients between each factor
        and total cost to indicate relative influence.
        """
        sensitivities: Dict[str, float] = {}
        for j, name in enumerate(factor_names):
            x = rankdata(factor_samples[:, j])
            y = rankdata(total_costs)
            corr = np.corrcoef(x, y)[0, 1]
            sensitivities[name] = round(float(corr), 4)
        return sensitivities
```

> **Human review requirement:** `_apply_iman_conover` and `_transform_samples` must be validated against known cases before production use.

---

## 10. AACE Classifier (services/aace_classifier.py)

Implement `AACEClassifier` as previously specified:

* Uses engineering maturity %, completeness, and available deliverables to assign `AACEClass`.
* Returns:

  * `aace_class`
  * `accuracy_range`
  * `justification` (list of strings)
  * `recommendations` (list of actions to improve class)

---

## 11. Cost Database Service (services/cost_database.py)

**Goal:** Take project + parsed docs + cost code data → compute:

* `base_cost` (Decimal)
* A **flat list of `EstimateLineItem` entities** with correct WBS and parent/child semantics.

### 11.1 Class Signature

```python
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from apex.models.database import (
    Project,
    Document,
    EstimateLineItem,
    CostCode,
)
from apex.utils.errors import BusinessRuleViolation

class CostDatabaseService:
    """
    Computes base (pre-contingency) cost and builds RELATIONAL EstimateLineItem entities.
    """

    def compute_base_cost(
        self,
        db: Session,
        project: Project,
        documents: List[Document],
        cost_code_map: Dict[str, CostCode],
    ) -> Tuple[Decimal, List[EstimateLineItem]]:
        """
        Returns:
            base_cost: Total pre-contingency cost.
            line_items: Flat list of EstimateLineItem instances with:
                        - estimate_id not set yet
                        - parent_line_item_id still None (parent linking deferred)
                        - optional _temp_parent_ref and wbs_code fields set
        """
        quantities = self._extract_quantities(project, documents)
        cost_items = self._map_to_cost_items(project, quantities, cost_code_map)
        cost_items_with_units = self._lookup_unit_costs(db, cost_items)
        adjusted_items = self._apply_adjustments(project, cost_items_with_units)
        total_cost, line_item_entities = self._build_cbs_hierarchy(adjusted_items)
        return total_cost, line_item_entities

    # Internal methods (must exist, even if MVP versions are simple but real):
    def _extract_quantities(self, project, documents): ...
    def _map_to_cost_items(self, project, quantities, cost_code_map): ...
    def _lookup_unit_costs(self, db, cost_items): ...
    def _apply_adjustments(self, project, cost_items_with_units): ...
    def _build_cbs_hierarchy(self, cost_items): ...
```

### 11.2 `_build_cbs_hierarchy` Requirements

* Creates:

  * Parent/summary rows (e.g., “10: Transmission Line”) as `EstimateLineItem`.
  * Child rows (e.g., “10-100: Tangent Structures”) as `EstimateLineItem`.

* Uses a **deterministic key**, typically `wbs_code`, to relate children to parents.

* Sets:

  * `line_item.wbs_code` (e.g., "10", "10-100")
  * Temporary parent references, e.g., `line_item._temp_parent_ref = "10"` for "10-100".

* Returns:

  * `total_cost` as `Decimal`.
  * `line_items` as a flat list of `EstimateLineItem` (no nested JSON).

The **actual linking to persisted GUIDs** (parent_line_item_id) is done in the `EstimateRepository` transaction (see below).

---

## 12. Estimate Generation Orchestration (services/estimate_generator.py)

### 12.1 Dependencies & Class

```python
from uuid import UUID
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from apex.database.repositories.project_repository import ProjectRepository
from apex.database.repositories.document_repository import DocumentRepository
from apex.database.repositories.estimate_repository import EstimateRepository
from apex.database.repositories.audit_repository import AuditRepository

from apex.models.database import User, Estimate, EstimateRiskFactor, EstimateAssumption, EstimateExclusion
from apex.services.llm.orchestrator import LLMOrchestrator
from apex.services.risk_analysis import MonteCarloRiskAnalyzer, RiskFactor
from apex.services.aace_classifier import AACEClassifier
from apex.services.cost_database import CostDatabaseService
from apex.utils.errors import BusinessRuleViolation

class EstimateGenerator:
    def __init__(
        self,
        project_repo: ProjectRepository,
        document_repo: DocumentRepository,
        estimate_repo: EstimateRepository,
        audit_repo: AuditRepository,
        llm_orchestrator: LLMOrchestrator,
        risk_analyzer: MonteCarloRiskAnalyzer,
        aace_classifier: AACEClassifier,
        cost_db_service: CostDatabaseService,
    ) -> None:
        self.project_repo = project_repo
        self.document_repo = document_repo
        self.estimate_repo = estimate_repo
        self.audit_repo = audit_repo
        self.llm_orchestrator = llm_orchestrator
        self.risk_analyzer = risk_analyzer
        self.aace_classifier = aace_classifier
        self.cost_db_service = cost_db_service

    def generate_estimate(
        self,
        db: Session,
        project_id: UUID,
        risk_factors_dto: List[Dict[str, Any]],
        confidence_level: float,
        monte_carlo_iterations: int,
        user: User,
    ) -> Estimate:
        """
        Orchestrates full estimate generation:

        1. Load project & documents.
        2. Check user access (ProjectAccess table).
        3. Derive completeness + maturity → AACEClassifier.classify().
        4. CostDatabaseService.compute_base_cost(...) → (base_cost, line_items).
        5. Build RiskFactor objects, run Monte Carlo → risk_results.
        6. Compute contingency percentage from P_target vs base.
        7. Call LLMOrchestrator to generate narrative, assumptions, exclusions.
        8. Build ORM entities:
           - Estimate
           - EstimateRiskFactor entries
           - EstimateAssumption entries
           - EstimateExclusion entries
        9. Call estimate_repo.create_estimate_with_hierarchy(...) to persist:
           - Estimate + line_items + assumptions + exclusions + risk_factors in one transaction.
        10. Create AuditLog.
        11. Return Estimate entity.
        """
        # Implementation left to AI under these constraints.
        raise NotImplementedError
```

---

## 13. API Layer & Pagination

### 13.1 Common Schemas (models/schemas.py)

#### Pagination

```python
from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel
from datetime import datetime

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
```

All list endpoints (e.g., `GET /projects`, `GET /projects/{project_id}/estimates`) **must** use `PaginatedResponse[T]`.

#### Error Response

```python
class ValidationError(BaseModel):
    field: str
    message: str
    code: Optional[str] = None

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    validation_errors: Optional[List[ValidationError]] = None
    request_id: Optional[str] = None
    timestamp: datetime
```

All non-2xx responses must adhere to this schema.

### 13.2 Error & Request ID Middleware (utils/middleware.py, utils/errors.py, main.py)

**BusinessRuleViolation:**

```python
class BusinessRuleViolation(Exception):
    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details
```

**Request ID middleware (utils/middleware.py):**

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

**Global exception handlers (main.py):**

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
import traceback

from apex.models.schemas import ErrorResponse
from apex.utils.errors import BusinessRuleViolation
from apex.config import config

logger = logging.getLogger(__name__)

@app.exception_handler(BusinessRuleViolation)
async def business_rule_handler(request: Request, exc: BusinessRuleViolation):
    request_id = getattr(request.state, "request_id", None)
    payload = ErrorResponse(
        error_code=exc.code or "BUSINESS_RULE_VIOLATION",
        message=str(exc),
        details=exc.details,
        request_id=request_id,
        timestamp=datetime.utcnow(),
    )
    return JSONResponse(status_code=400, content=payload.model_dump())


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error("Unhandled exception: %s", traceback.format_exc())
    message = "An unexpected error occurred"
    if config.DEBUG:
        message = str(exc)
    payload = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message=message,
        details=None,
        request_id=request_id,
        timestamp=datetime.utcnow(),
    )
    return JSONResponse(status_code=500, content=payload.model_dump())
```

### 13.3 Health Endpoints (api/v1/health.py)

Implement minimal but meaningful health checks:

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from apex.dependencies import get_db

router = APIRouter()

@router.get("/health/live")
async def liveness_check():
    return {"status": "alive", "timestamp": datetime.utcnow()}

@router.get("/health/ready")
async def readiness_check(db: Session = Depends(get_db)):
    checks = {"database": "unknown", "blob_storage": "unknown"}
    issues = []

    # Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        checks["database"] = "unhealthy"
        issues.append(f"Database: {exc}")

    # Blob storage check (stub; real implementation calls azure/blob_storage.py)
    try:
        # e.g., BlobStorageClient().check_container("uploads")
        checks["blob_storage"] = "healthy"
    except Exception as exc:
        checks["blob_storage"] = "unhealthy"
        issues.append(f"Blob Storage: {exc}")

    all_healthy = all(v == "healthy" for v in checks.values())
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return (
        {
            "status": "ready" if all_healthy else "degraded",
            "checks": checks,
            "issues": issues or None,
            "timestamp": datetime.utcnow(),
        },
        status_code,
    )
```

---

## 14. Logging & Retry (utils/logging.py, utils/retry.py)

### 14.1 Logging

* Use standard `logging` module.
* Integrate with Application Insights via `opencensus-ext-azure`.
* At minimum, log:

  * All LLM calls (model, tokens, action, project/estimate identifiers).
  * All BusinessRuleViolation errors.
  * All unhandled exceptions.

### 14.2 Azure Retry Decorator (utils/retry.py)

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from azure.core.exceptions import AzureError, ServiceRequestError

azure_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((AzureError, ServiceRequestError)),
    reraise=True,
)
```

Use `@azure_retry` for Azure OpenAI calls, Document Intelligence calls, and Blob operations.

---

## 15. Testing Guidelines

* Unit tests:

  * Risk engine with deterministic seeds.
  * Document parser with mocked Azure DI responses.
  * CostDatabaseService with controlled quantities and cost codes.
  * AACEClassifier for various maturity/completeness combinations.

* Integration tests:

  * `POST /projects` / `GET /projects`.
  * `POST /documents/upload` / `POST /documents/{id}/validate`.
  * `POST /estimates/generate` with mocked LLM + DI + cost data.

* Azure mocks should live in `tests/fixtures/azure_mocks.py` and simulate:

  * `DocumentIntelligenceClient.begin_analyze_document` poller.
  * Managed Identity credentials.
  * Azure OpenAI client responses.

---

## 16. pyproject.toml & Build System

### 16.1 Build System (Mandatory)

Your `pyproject.toml` must define:

```toml
[build-system]
requires = ["setuptools >= 61.0", "wheel"]
build-backend = "setuptools.build_meta"
```

### 16.2 Project Metadata (Skeleton)

```toml
[project]
name = "apex"
version = "0.1.0"
description = "APEX – AI-Powered Estimation Expert for utility T&D projects"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.104.0,<1.0.0",
    "uvicorn[standard]>=0.24.0,<1.0.0",
    "pydantic>=2.5.0,<3.0.0",
    "pydantic-settings>=2.1.0,<3.0.0",
    "sqlalchemy>=2.0.0,<3.0.0",
    "alembic>=1.13.0,<2.0.0",
    "pyodbc>=5.0.0,<6.0.0",
    "azure-identity>=1.15.0,<2.0.0",
    "azure-storage-blob>=12.19.0,<13.0.0",
    "azure-keyvault-secrets>=4.7.0,<5.0.0",
    "openai>=1.3.0,<2.0.0",
    "azure-ai-documentintelligence>=1.0.0,<2.0.0",
    "numpy>=1.26.0,<2.0.0",
    "scipy>=1.11.0,<2.0.0",
    "statsmodels>=0.14.0,<1.0.0",
    "SALib>=1.4.7,<2.0.0",
    "openpyxl>=3.1.0,<4.0.0",
    "python-docx>=1.1.0,<2.0.0",
    "python-multipart>=0.0.6,<1.0.0",
    "httpx>=0.25.0,<1.0.0",
    "pytest>=7.4.0,<8.0.0",
    "pytest-asyncio>=0.21.0,<1.0.0",
    "opencensus-ext-azure>=1.1.0,<2.0.0",
    "black>=23.0.0,<24.0.0",
    "isort>=5.12.0,<6.0.0",
    "flake8>=6.0.0,<7.0.0",
    "tenacity>=8.2.0,<9.0.0",
    "tiktoken>=0.5.0,<1.0.0",
]

[tool.black]
line-length = 100

[tool.isort]
profile = "black"
```

> A separate lock file (poetry.lock / pdm.lock / requirements.lock) should be generated for reproducible builds. Docker and CI should install from the lock file, not from naked version ranges.

---

## 17. How to Use This Prompt in an AI IDE

1. **Save this file as** `APEX_Prompt.md` in your repository root.
2. In your AI IDE (Cursor, Windsurf, Copilot, etc.), instruct:

> “Build the APEX backend according to `APEX_Prompt.md`. The relational data model, security mandates, and core services (Document Parsing, Risk Analysis, LLM Orchestrator, Cost Database, Estimate Generator) are **non-negotiable**. Implement all mandatory sections first. Treat Section 18 as future/optional enhancements.”

3. Implement in this order:

   1. `config.py`, `database/connection.py`, `models/database.py`, `models/enums.py`, `models/schemas.py`
   2. `utils/logging.py`, `utils/errors.py`, `utils/retry.py`, `utils/middleware.py`
   3. `services/llm/orchestrator.py`, `services/document_parser.py`, `services/risk_analysis.py`, `services/aace_classifier.py`, `services/cost_database.py`, `services/estimate_generator.py`
   4. API routers (`api/v1/*.py`) & `main.py`
   5. Tests & mocks

---

## 18. Future / Optional Enhancements (Not Required for MVP)

The following patterns are **recommended** but **not required** in the initial implementation. They should be implemented only after the core system is stable.

### 18.1 Concurrency Control for Estimate Generation

* Introduce `EstimateStatus` enum and `status` column on `Estimate` (`generating`, `completed`, `failed`).
* In `EstimateGenerator`, enforce “one active generation per project” by:

  * Checking for a recent `status = generating` estimate for that `project_id`.
  * If found, raising `BusinessRuleViolation("Estimate generation already in progress...")`.
  * Creating a placeholder `Estimate` with `status = generating` and updating to `completed` / `failed` after processing.

### 18.2 Caching for Cost Lookups

* Use a shared cache (e.g., Redis via Azure Cache for Redis) for expensive, deterministic lookups (e.g., RSMeans unit costs by cost_code + region + year).
* Keys should be based on **stable, low-cardinality attributes** (like `cost_code`, `location_factor_region`, `year`), not raw cost item lists.
* Caching must be an optimization only; the system must be correct without it.

### 18.3 Advanced Rate Limiting for LLM Calls

* Implement a **token-bucket** or sliding-window rate limiter in the LLM client to smooth out usage and avoid hitting Azure limits.
* Coordinate with Azure OpenAI quotas; the limiter is best-effort, not a guarantee.
* Ensure blocking waits are done in a way that does not starve the event loop (e.g., run blocking LLM calls in threadpools).

### 18.4 Metrics & Custom Telemetry

* Define custom metrics for:

  * Estimate generation duration.
  * LLM call latency.
  * Document parse duration.
* Send time series to Application Insights using opencensus or Azure Monitor.
* Use those metrics to monitor performance and capacity planning.

### 18.5 Background Job / Queue Pattern

* Introduce a `BackgroundJob` model and `JobStatus` enum for long-running tasks (bulk parsing, multi-project risk analysis).
* Use Azure Service Bus + Azure Functions to offload heavy tasks from the API.
* Expose endpoints to:

  * Enqueue jobs.
  * Poll job status.
  * Retrieve job results.

---

**End of APEX_Prompt.md**

This specification is intentionally strict. Any AI-generated code should treat this document as the single source of truth for the APEX backend architecture and behavior.

```
```
