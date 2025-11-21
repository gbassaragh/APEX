# APEX Technical Specification
**Implementation Guide for Developers**

---

## Document Purpose

This document provides detailed technical specifications for implementing, testing, and deploying APEX. It complements the [Architecture Document](ARCHITECTURE.md) with code-level details, configuration requirements, and operational procedures.

**Audience:** Software developers, DevOps engineers, QA testers

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Code Structure & Conventions](#code-structure--conventions)
3. [Configuration Management](#configuration-management)
4. [Database Schema & Migrations](#database-schema--migrations)
5. [API Design Patterns](#api-design-patterns)
6. [Service Layer Implementation](#service-layer-implementation)
7. [Testing Strategy](#testing-strategy)
8. [Deployment Procedures](#deployment-procedures)
9. [Operational Runbooks](#operational-runbooks)
10. [Troubleshooting Guide](#troubleshooting-guide)

---

## Development Environment Setup

### Prerequisites

**Required Software:**
- Python 3.11 or 3.12
- Git
- Azure CLI (`az`)
- ODBC Driver 18 for SQL Server (for local database connections)
- Docker Desktop (optional, for local container testing)

### Local Setup

```bash
# Clone repository
git clone https://github.com/your-org/APEX.git
cd APEX

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Verify installation
python -c "import apex; print(apex.__name__)"
pytest --version
```

### Environment Configuration

**Create `.env` file** (never commit this file):
```bash
# Copy from template
cp .env.example .env

# Edit with your Azure credentials
# Minimum required for local development:
AZURE_SQL_SERVER=your-dev-server.database.windows.net
AZURE_SQL_DATABASE=apex_dev
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_DI_ENDPOINT=https://your-region.api.cognitive.microsoft.com/
AZURE_STORAGE_ACCOUNT=yourdevstorageacct

# Optional for local testing:
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=DEBUG
```

### Azure Authentication (Local)

**Option 1: Azure CLI (Recommended for Development)**
```bash
az login
az account set --subscription "Your Subscription Name"

# Verify Managed Identity emulation works
az account get-access-token --resource https://database.windows.net/
```

**Option 2: Service Principal (CI/CD)**
```bash
# Set environment variables (CI/CD only)
export AZURE_CLIENT_ID=xxx
export AZURE_CLIENT_SECRET=xxx
export AZURE_TENANT_ID=xxx
```

### Database Setup (Local)

**Option 1: Azure SQL Database (Recommended)**
```bash
# Provision dev database in Azure
az sql db create \
  --resource-group rg-apex-dev \
  --server sql-apex-dev \
  --name apex_dev \
  --service-objective Basic

# Run migrations
alembic upgrade head
```

**Option 2: Local SQLite (Testing Only)**
```python
# In tests, use SQLite in-memory database
# See tests/unit/test_*.py for examples
engine = create_engine("sqlite:///:memory:")
```

---

## Code Structure & Conventions

### Project Layout (Binding)

```
apex/
├── src/apex/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entrypoint
│   ├── config.py                  # Pydantic Settings
│   ├── dependencies.py            # Dependency injection
│   │
│   ├── api/v1/                    # API layer
│   │   ├── projects.py            # /api/v1/projects endpoints
│   │   ├── documents.py           # /api/v1/documents endpoints
│   │   ├── estimates.py           # /api/v1/estimates endpoints
│   │   └── health.py              # /api/v1/health endpoints
│   │
│   ├── models/                    # Data models
│   │   ├── enums.py               # Status enums
│   │   ├── database.py            # SQLAlchemy ORM
│   │   └── schemas.py             # Pydantic DTOs
│   │
│   ├── database/                  # Data access
│   │   ├── connection.py          # SQLAlchemy engine
│   │   └── repositories/          # Repository pattern
│   │       ├── project_repository.py
│   │       ├── document_repository.py
│   │       ├── estimate_repository.py
│   │       └── audit_repository.py
│   │
│   ├── services/                  # Business logic
│   │   ├── llm/                   # LLM orchestration
│   │   │   ├── orchestrator.py
│   │   │   ├── prompts.py
│   │   │   └── validators.py
│   │   ├── document_parser.py
│   │   ├── risk_analysis.py
│   │   ├── aace_classifier.py
│   │   ├── cost_database.py
│   │   └── estimate_generator.py
│   │
│   ├── azure/                     # Azure integrations
│   │   ├── auth.py
│   │   ├── blob_storage.py
│   │   └── key_vault.py
│   │
│   └── utils/                     # Utilities
│       ├── logging.py
│       ├── errors.py
│       ├── retry.py
│       └── middleware.py
│
├── tests/
│   ├── fixtures/                  # Test fixtures
│   ├── unit/                      # Unit tests
│   └── integration/               # Integration tests
│
├── alembic/                       # Database migrations
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
│
├── docs/                          # Documentation
├── pyproject.toml                 # Dependencies (SINGLE SOURCE)
├── alembic.ini                    # Alembic config
├── .env.example                   # Environment template
└── README.md
```

**Rules:**
- ❌ **NO** `requirements.txt` as primary source (use `pyproject.toml`)
- ✅ All Python files must have module docstrings
- ✅ All public functions must have docstrings (Google style)
- ✅ Type hints required for all function signatures

### Naming Conventions

**Files & Modules:**
- Snake_case: `document_parser.py`, `estimate_repository.py`
- No abbreviations: `document_parser.py` not `doc_parser.py`

**Classes:**
- PascalCase: `EstimateGenerator`, `ProjectRepository`
- Suffix for pattern: `*Repository`, `*Service`, `*Middleware`

**Functions & Variables:**
- snake_case: `generate_estimate()`, `project_id`
- Descriptive names: `calculate_p80_cost()` not `calc_p80()`

**Constants:**
- UPPER_SNAKE_CASE: `DEFAULT_MONTE_CARLO_ITERATIONS`

**Database Tables:**
- Plural snake_case: `projects`, `estimate_line_items`

**Enums:**
- Class: PascalCase (`ProjectStatus`)
- Values: UPPER_SNAKE_CASE (`DRAFT`, `COMPLETE`)

### Code Quality Standards

**Formatting (Enforced in CI):**
```bash
# Black (line length 100)
black src/ tests/ --line-length 100 --check

# isort (imports)
isort src/ tests/ --profile black --check

# flake8 (linting)
flake8 src/ tests/ --max-line-length 100
```

**Type Checking (Recommended):**
```bash
mypy src/apex --strict
```

**Security Scanning:**
```bash
# Dependency vulnerabilities
pip-audit

# Secret scanning
trufflehog --regex --entropy=False .
```

---

## Configuration Management

### Pydantic Settings Pattern

**File:** `src/apex/config.py`

```python
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    """Environment-based configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )

    # Required fields
    AZURE_SQL_SERVER: str
    AZURE_SQL_DATABASE: str
    AZURE_OPENAI_ENDPOINT: str
    # ...

    # Optional fields with defaults
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    @property
    def database_url(self) -> str:
        """Construct Managed Identity connection string."""
        return (
            f"mssql+pyodbc://@{self.AZURE_SQL_SERVER}/"
            f"{self.AZURE_SQL_DATABASE}"
            f"?driver={self.AZURE_SQL_DRIVER.replace(' ', '+')}"
            f"&Authentication=ActiveDirectoryMsi"
        )

# Global instance (lazy for testing)
config = Config() if "pytest" not in sys.modules else None
```

### Environment Variables

**Required (All Environments):**
```bash
AZURE_SQL_SERVER=xxx.database.windows.net
AZURE_SQL_DATABASE=apex_prod
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_DI_ENDPOINT=https://xxx.cognitiveservices.azure.com/
AZURE_STORAGE_ACCOUNT=xxxstorageacct
```

**Optional (Environment-Specific):**
```bash
# Development
ENVIRONMENT=development
DEBUG=True
LOG_LEVEL=DEBUG

# UAT
ENVIRONMENT=uat
DEBUG=False
LOG_LEVEL=INFO

# Production
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=WARNING
AZURE_APPINSIGHTS_CONNECTION_STRING=InstrumentationKey=xxx
```

### Secrets Management

**Managed Identity (Production):**
- All Azure service connections use `DefaultAzureCredential()`
- No secrets in environment variables or Key Vault

**Key Vault (Optional, for Non-Azure Secrets):**
```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

client = SecretClient(
    vault_url="https://kv-apex-prod.vault.azure.net",
    credential=DefaultAzureCredential()
)

secret = client.get_secret("external-api-key")
```

**Local Development (`.env` file):**
- Use Azure CLI authentication (`az login`)
- `.env` file for configuration, not secrets

---

## Database Schema & Migrations

### Alembic Configuration

**File:** `alembic.ini`
```ini
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname  # Overridden by env.py

[loggers]
keys = root,sqlalchemy,alembic

[logger_alembic]
level = INFO
handlers =
qualname = alembic
```

**File:** `alembic/env.py`
```python
from apex.config import config
from apex.models.database import Base

# Use config.database_url for connection
target_metadata = Base.metadata
```

### Creating Migrations

**Auto-generate migration:**
```bash
# After modifying ORM models in models/database.py
alembic revision --autogenerate -m "Add estimate risk factors table"

# Review generated migration in alembic/versions/
# Edit if needed (Alembic can't detect everything)

# Apply migration
alembic upgrade head
```

**Manual migration example:**
```python
"""Add estimate risk factors table

Revision ID: abc123
Revises: def456
Create Date: 2024-11-21 10:00:00
"""
from alembic import op
import sqlalchemy as sa
from apex.models.database import GUID

def upgrade():
    op.create_table(
        'risk_factors',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('estimate_id', GUID(), nullable=False),
        sa.Column('factor_name', sa.String(100), nullable=False),
        sa.Column('distribution_type', sa.String(50)),
        # ...
    )

def downgrade():
    op.drop_table('risk_factors')
```

### Schema Conventions

**Primary Keys:**
- Always `id GUID` (use GUID TypeDecorator)
- Default: `uuid.uuid4` in Python

**Foreign Keys:**
- Pattern: `{table_name}_id` (e.g., `project_id`, `estimate_id`)
- Always indexed
- ON DELETE behavior: CASCADE for child records, RESTRICT for critical references

**Timestamps:**
- `created_at DATETIME2 DEFAULT GETUTCDATE()` (SQL Server)
- `updated_at DATETIME2` (trigger or ORM event)

**Enums:**
- Use SQLAlchemy `Enum` type with Python `str` enums
- Example: `status = Column(Enum(ProjectStatus))`

**JSON Columns:**
- ✅ **Allowed:** Audit trails (`AuditLog.details`), validation results
- ❌ **Prohibited:** Cost data, quantities, analytical data

---

## API Design Patterns

### FastAPI Best Practices

**Endpoint Structure:**
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from apex.dependencies import get_db, get_current_user
from apex.models.schemas import ProjectResponse, ProjectCreate, PaginatedResponse
from apex.models.database import User

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get(
    "/",
    response_model=PaginatedResponse[ProjectResponse],
    summary="List all projects",
    description="Returns paginated list of projects accessible by current user"
)
async def list_projects(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List projects with pagination."""
    # Implementation
    pass
```

### Error Handling

**Custom exceptions:**
```python
# utils/errors.py
class BusinessRuleViolation(Exception):
    """Raised when business rule is violated."""
    pass

# API handler
@app.exception_handler(BusinessRuleViolation)
async def business_rule_handler(request: Request, exc: BusinessRuleViolation):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "type": "business_rule_violation"}
    )
```

**Error Response Schema:**
```python
class ErrorResponse(BaseModel):
    error: str
    type: str
    request_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
```

### Pagination

**Standard pattern:**
```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

# In repository
def list_projects(self, page: int, page_size: int) -> Tuple[List[Project], int]:
    offset = (page - 1) * page_size
    query = self.db.query(Project).filter(...)

    total = query.count()
    items = query.offset(offset).limit(page_size).all()

    return items, total
```

### Authentication & Authorization

**Dependency injection pattern:**
```python
# dependencies.py
async def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
) -> User:
    """Extract user from AAD token and verify in database."""
    # 1. Validate JWT token with Azure AD
    # 2. Extract AAD object ID
    # 3. Lookup User in database
    # 4. Return User object or raise 401
    pass

async def require_project_access(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Verify user has access to project."""
    access = db.query(ProjectAccess).filter_by(
        user_id=current_user.id,
        project_id=project_id
    ).first()

    if not access:
        raise HTTPException(403, "Insufficient permissions")

    return access
```

---

## Service Layer Implementation

### Repository Pattern

**Base repository:**
```python
# database/repositories/base.py
class BaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, model_class, id: UUID) -> Optional[Any]:
        return self.db.query(model_class).filter_by(id=id).first()

    def list_all(self, model_class, filters: dict) -> List[Any]:
        query = self.db.query(model_class)
        for key, value in filters.items():
            query = query.filter(getattr(model_class, key) == value)
        return query.all()

    # Pagination, sorting, etc.
```

**Concrete repository:**
```python
# database/repositories/project_repository.py
class ProjectRepository(BaseRepository):
    def create_project(self, data: ProjectCreate, user_id: UUID) -> Project:
        project = Project(
            id=uuid.uuid4(),
            name=data.name,
            project_number=data.project_number,
            created_by_user_id=user_id,
            status=ProjectStatus.DRAFT
        )
        self.db.add(project)
        self.db.flush()  # Get ID without committing
        return project

    def get_user_projects(self, user_id: UUID) -> List[Project]:
        return (
            self.db.query(Project)
            .join(ProjectAccess)
            .filter(ProjectAccess.user_id == user_id)
            .all()
        )
```

### Service Layer

**Purpose:** Orchestrate business logic, coordinate multiple repositories.

```python
# services/estimate_generator.py
class EstimateGeneratorService:
    def __init__(
        self,
        db: Session,
        llm_orchestrator: LLMOrchestrator,
        document_parser: DocumentParserService,
        risk_analyzer: RiskAnalysisService,
        cost_db_service: CostDatabaseService,
    ):
        self.db = db
        self.llm = llm_orchestrator
        # ...

    async def generate_estimate(
        self,
        project_id: UUID,
        user_id: UUID
    ) -> Estimate:
        """Main orchestration flow for estimate generation."""
        # 1. Load project and documents
        project = self.project_repo.get_by_id(project_id)
        documents = self.document_repo.get_by_project(project_id)

        # 2. Classify AACE maturity
        aace_class = self.classifier.classify(project, documents)

        # 3. Build cost database
        base_cost, line_items = self.cost_db.compute_base_cost(
            project, documents
        )

        # 4. Run risk analysis
        risk_result = self.risk_analyzer.run_monte_carlo(
            base_cost, line_items
        )

        # 5. Generate narrative
        narrative = await self.llm.generate_narrative(
            aace_class, project, line_items
        )

        # 6. Persist estimate (single transaction)
        estimate = self.estimate_repo.create_estimate_with_hierarchy(
            project_id, aace_class, base_cost, risk_result, narrative, line_items
        )

        # 7. Audit log
        self.audit_repo.log_action(
            entity_type="Estimate",
            entity_id=estimate.id,
            action="GENERATE",
            user_id=user_id
        )

        return estimate
```

### Async Patterns

**For I/O-bound operations (LLM calls, Azure API calls):**
```python
async def analyze_document_async(self, document_bytes: bytes) -> Dict:
    """Async document analysis with Azure Document Intelligence."""
    poller = self.di_client.begin_analyze_document(
        model_id="prebuilt-layout",
        document=document_bytes
    )

    # Poll asynchronously
    result = await self._poll_with_timeout(poller, timeout=60)
    return self._extract_structured_content(result)

async def _poll_with_timeout(self, poller, timeout: int) -> Any:
    """Async polling with timeout."""
    import asyncio
    start_time = time.time()
    while not poller.done():
        if time.time() - start_time > timeout:
            raise TimeoutError("Document analysis timed out")
        await asyncio.sleep(2)  # Poll every 2 seconds
    return poller.result()
```

**For CPU-bound operations (Monte Carlo):**
```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

async def run_monte_carlo_async(self, params: Dict) -> Dict:
    """Run Monte Carlo in separate process to avoid blocking."""
    loop = asyncio.get_event_loop()
    with ProcessPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor,
            self._run_monte_carlo_sync,
            params
        )
    return result

def _run_monte_carlo_sync(self, params: Dict) -> Dict:
    """Synchronous Monte Carlo execution (CPU-bound)."""
    # NumPy/SciPy heavy lifting here
    pass
```

---

## Testing Strategy

### Test Structure

```
tests/
├── fixtures/
│   ├── __init__.py
│   ├── azure_mocks.py         # Mock Azure services
│   └── sample_data.py         # Sample documents, projects
│
├── unit/
│   ├── test_config.py         # Config validation
│   ├── test_enums.py          # Enum serialization
│   ├── test_guid_typedecorator.py
│   ├── test_session_management.py
│   ├── test_risk_analysis.py  # Monte Carlo tests (CRITICAL)
│   ├── test_document_parser.py
│   └── test_cost_database.py
│
└── integration/
    ├── test_api_projects.py   # Project CRUD APIs
    ├── test_api_documents.py  # Document upload/download
    └── test_api_estimates.py  # End-to-end estimate generation
```

### Unit Testing Best Practices

**Test structure:**
```python
import pytest
from apex.services.risk_analysis import RiskAnalysisService

class TestMonteCarloSimulation:
    """Test suite for Monte Carlo risk analysis."""

    def test_triangular_distribution(self):
        """Test Monte Carlo with triangular distribution."""
        service = RiskAnalysisService()
        result = service.run_simulation(
            base_cost=1000000,
            distribution='triangular',
            params={'min': 900000, 'mode': 1000000, 'max': 1200000},
            iterations=10000,
            random_seed=42  # Deterministic for testing
        )

        # Verify statistical properties
        assert 900000 <= result.p50 <= 1200000
        assert result.p50 < result.p80 < result.p95
        # Allow 5% tolerance for statistical variation
        assert 980000 <= result.p50 <= 1020000

    def test_correlation_preservation(self):
        """Test Iman-Conover correlation preservation."""
        # CRITICAL TEST: Validate against @RISK or Crystal Ball
        service = RiskAnalysisService()
        correlation_matrix = [[1.0, 0.7], [0.7, 1.0]]

        result = service.apply_correlation(
            samples=[[...], [...]],
            correlation_matrix=correlation_matrix
        )

        # Verify correlation is preserved (within tolerance)
        actual_corr = np.corrcoef(result)
        np.testing.assert_allclose(
            actual_corr, correlation_matrix, atol=0.05
        )
```

**Mocking Azure services:**
```python
# tests/fixtures/azure_mocks.py
class MockDocumentIntelligenceClient:
    def begin_analyze_document(self, model_id, document):
        return MockPoller(result={
            "pages": [...],
            "tables": [...],
        })

@pytest.fixture
def mock_di_client(monkeypatch):
    client = MockDocumentIntelligenceClient()
    monkeypatch.setattr(
        "apex.services.document_parser.DocumentIntelligenceClient",
        lambda *args, **kwargs: client
    )
    return client
```

### Integration Testing

**API endpoint test:**
```python
from fastapi.testclient import TestClient
from apex.main import app

client = TestClient(app)

def test_create_project_endpoint():
    """Test POST /api/v1/projects."""
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Test Project",
            "project_number": "P-2024-001"
        },
        headers={"Authorization": "Bearer fake-token-for-testing"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert "id" in data
```

### Test Coverage Goals

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| **Utils** (config, errors, logging) | 100% | High |
| **Models** (enums, GUID, schemas) | 100% | High |
| **Repositories** | 80% | High |
| **Services** (risk, parser, LLM) | 70% | **CRITICAL** |
| **API Endpoints** | 60% | Medium |

**Run coverage:**
```bash
pytest tests/ --cov=apex --cov-report=html --cov-report=term
open htmlcov/index.html  # View detailed report
```

---

## Deployment Procedures

### Container Build

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install ODBC Driver for SQL Server
RUN apt-get update && apt-get install -y \
    curl apt-transport-https gnupg unixodbc-dev && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql18

# Copy dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy application code
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Non-root user
RUN useradd -m -u 1000 apex && chown -R apex:apex /app
USER apex

EXPOSE 8000

CMD ["uvicorn", "apex.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build and push:**
```bash
# Build container
docker build -t acr.azurecr.io/apex:$(git rev-parse --short HEAD) .

# Test locally
docker run -p 8000:8000 --env-file .env acr.azurecr.io/apex:latest

# Push to Azure Container Registry
az acr login --name acr
docker push acr.azurecr.io/apex:$(git rev-parse --short HEAD)
```

### Azure Container Apps Deployment

**Infrastructure as Code (Bicep):**
```bicep
resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: 'ca-apex-prod'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
      }
      secrets: []  // No secrets, use Managed Identity
    }
    template: {
      containers: [{
        name: 'apex-api'
        image: 'acr.azurecr.io/apex:${imageTag}'
        resources: {
          cpu: json('2.0')
          memory: '4Gi'
        }
        env: [
          { name: 'AZURE_SQL_SERVER', value: sqlServer.properties.fullyQualifiedDomainName }
          { name: 'AZURE_SQL_DATABASE', value: 'apex_prod' }
          { name: 'AZURE_OPENAI_ENDPOINT', value: openai.properties.endpoint }
          // ...
        ]
      }]
      scale: {
        minReplicas: 2
        maxReplicas: 10
        rules: [{
          name: 'http-rule'
          http: {
            metadata: {
              concurrentRequests: '50'
            }
          }
        }]
      }
    }
  }
}
```

**Deploy via Azure CLI:**
```bash
az containerapp update \
  --name ca-apex-prod \
  --resource-group rg-apex-prod \
  --image acr.azurecr.io/apex:v1.0.0 \
  --set-env-vars \
    AZURE_SQL_SERVER=sql-apex-prod.database.windows.net \
    AZURE_SQL_DATABASE=apex_prod \
    # ...
```

### Database Migration Strategy

**Pre-deployment:**
```bash
# Run migrations in separate job (before app deployment)
az containerapp job create \
  --name job-apex-migrate \
  --resource-group rg-apex-prod \
  --image acr.azurecr.io/apex:v1.0.0 \
  --command "/bin/sh" "-c" "alembic upgrade head" \
  --replica-timeout 600 \
  --trigger-type Manual

# Execute migration job
az containerapp job start --name job-apex-migrate --resource-group rg-apex-prod
```

**Blue/Green Deployment:**
1. Deploy new version to "green" environment
2. Run migrations (forward compatible with blue)
3. Switch traffic to green
4. Decommission blue after validation

---

## Operational Runbooks

### Health Checks

**Liveness probe:** `/health/live`
- Returns 200 if app is running (no dependencies checked)

**Readiness probe:** `/health/ready`
- Returns 200 if app can serve traffic
- Checks: Database connection, Azure OpenAI reachable

**Implementation:**
```python
@router.get("/health/live")
async def liveness():
    return {"status": "ok"}

@router.get("/health/ready")
async def readiness(db: Session = Depends(get_db)):
    try:
        # Check database
        db.execute("SELECT 1")

        # Check Azure OpenAI
        # (lightweight call, or use cached status)

        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(503, f"Not ready: {str(e)}")
```

### Monitoring Queries (Application Insights)

**API performance:**
```kusto
requests
| where timestamp > ago(1h)
| summarize
    RequestCount = count(),
    AvgDuration = avg(duration),
    P50 = percentile(duration, 50),
    P95 = percentile(duration, 95),
    P99 = percentile(duration, 99)
  by operation_Name
| order by P95 desc
```

**Error rate:**
```kusto
requests
| where timestamp > ago(1h)
| summarize
    TotalRequests = count(),
    FailedRequests = countif(success == false)
| extend ErrorRate = 100.0 * FailedRequests / TotalRequests
```

**LLM token usage:**
```kusto
traces
| where message contains "LLM_TOKEN_USAGE"
| extend tokens = toint(customDimensions.tokens)
| summarize TotalTokens = sum(tokens) by bin(timestamp, 1h)
```

### Backup & Restore

**Database backup:**
```bash
# Automated backups (7-35 days retention)
az sql db show \
  --resource-group rg-apex-prod \
  --server sql-apex-prod \
  --name apex_prod \
  --query earliestRestoreDate

# Manual backup
az sql db export \
  --resource-group rg-apex-prod \
  --server sql-apex-prod \
  --name apex_prod \
  --storage-key-type StorageAccessKey \
  --storage-key $STORAGE_KEY \
  --storage-uri https://stapexprod.blob.core.windows.net/backups/apex_$(date +%Y%m%d).bacpac
```

**Blob storage backup:**
- Enabled versioning + soft delete (7 days)
- Lifecycle policy: Move to cool storage after 90 days

**Restore procedure:**
```bash
# Point-in-time restore (within RPO)
az sql db restore \
  --resource-group rg-apex-prod \
  --server sql-apex-prod \
  --name apex_prod \
  --dest-name apex_prod_restored \
  --time "2024-11-21T10:00:00Z"
```

### Incident Response

**Severity Levels:**
- **P0 (Critical):** Service down, data loss
- **P1 (High):** Degraded performance, partial outage
- **P2 (Medium):** Non-critical feature broken
- **P3 (Low):** Cosmetic issue, workaround available

**Escalation:**
1. On-call developer (15 min response for P0/P1)
2. Technical lead (30 min for P0)
3. Business owner (1 hour for P0)

---

## Troubleshooting Guide

### Common Issues

**1. "Authentication failed" (SQL Database)**

**Symptom:** `Login failed for user 'NT AUTHORITY\ANONYMOUS LOGON'`

**Cause:** Managed Identity not configured or not granted access

**Solution:**
```bash
# Grant Container App Managed Identity access to SQL
az sql server ad-admin set \
  --resource-group rg-apex-prod \
  --server-name sql-apex-prod \
  --display-name ca-apex-prod \
  --object-id $(az containerapp show --name ca-apex-prod --resource-group rg-apex-prod --query identity.principalId -o tsv)

# Or use SQL commands:
# CREATE USER [ca-apex-prod] FROM EXTERNAL PROVIDER;
# ALTER ROLE db_datareader ADD MEMBER [ca-apex-prod];
# ALTER ROLE db_datawriter ADD MEMBER [ca-apex-prod];
```

**2. "Azure OpenAI rate limit exceeded"**

**Symptom:** HTTP 429 errors in logs

**Cause:** TPM (tokens per minute) quota exceeded

**Solution:**
- Implement exponential backoff retry (already in `utils/retry.py`)
- Request quota increase from Azure support
- Optimize prompts to reduce token usage

**3. "Document parsing timeout"**

**Symptom:** `TimeoutError: Document analysis timed out`

**Cause:** Large/complex documents exceed 60s timeout

**Solution:**
```python
# Increase timeout in config.py
AZURE_DI_TIMEOUT: int = 120  # 2 minutes for large documents

# Or implement async queue pattern (future enhancement)
```

**4. "Monte Carlo execution takes too long"**

**Symptom:** API response > 60 seconds

**Cause:** Too many line items or iterations

**Solution:**
- Reduce iterations for simple estimates (5,000 instead of 10,000)
- Run Monte Carlo in background job (Azure Function)
- Cache results for similar estimates

### Debug Mode

**Enable verbose logging:**
```bash
# Set environment variable
LOG_LEVEL=DEBUG

# Or in code
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Query slow endpoints:**
```kusto
requests
| where timestamp > ago(1h)
| where duration > 5000  // > 5 seconds
| project timestamp, operation_Name, duration, resultCode, cloud_RoleName
| order by duration desc
```

### Performance Profiling

**Profile Python code:**
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run expensive function
result = run_monte_carlo(...)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

**Database query profiling:**
```python
# Enable SQLAlchemy echo
engine = create_engine(config.database_url, echo=True)

# Use EXPLAIN ANALYZE in SQL Server
# Query Plan in Azure Portal
```

---

## Appendix

### Useful Commands Cheat Sheet

```bash
# Development
pip install -e .                    # Install in editable mode
pytest tests/ -v                    # Run tests verbose
black src/ tests/                   # Format code
alembic upgrade head                # Run migrations
uvicorn apex.main:app --reload     # Start dev server

# Database
alembic revision --autogenerate -m "description"
alembic upgrade +1                  # Migrate one version forward
alembic downgrade -1                # Rollback one version
alembic history                     # Show migration history

# Azure CLI
az login
az account set --subscription "Sub Name"
az containerapp list --resource-group rg-apex-prod -o table
az sql db list --resource-group rg-apex-prod --server sql-apex-prod -o table

# Docker
docker build -t apex:local .
docker run -p 8000:8000 --env-file .env apex:local
docker logs <container_id> -f      # Follow logs

# Git
git log --oneline --graph           # Visual commit history
git diff origin/main                # Compare with main branch
```

### External References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Azure Container Apps Docs](https://learn.microsoft.com/azure/container-apps/)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

---

**Document Maintenance:**
- Review after each sprint/release
- Update for new Azure service integrations
- Add troubleshooting cases as they occur

*This technical specification is the authoritative implementation guide for APEX developers.*
