# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**APEX (AI-Powered Estimation Expert)** is an enterprise estimation platform for utility transmission and distribution projects. The system automates cost estimation through intelligent document parsing, AI-based validation, AACE-compliant classification, and industrial-grade Monte Carlo risk analysis.

**Primary Users**: Utility cost estimating teams (~30 estimators) plus managers/auditors
**Regulatory Context**: ISO-NE / regulatory compliance required for all estimates

## Technology Stack

- **Language**: Python 3.11+
- **API Framework**: FastAPI with async support
- **Database**: Azure SQL Database (SQLAlchemy 2.0+ with Alembic migrations)
- **Storage**: Azure Blob Storage (Managed Identity auth only)
- **LLM**: Azure OpenAI (GPT-4 family)
- **Document Parsing**: Azure AI Document Intelligence (mandatory for PDFs)
- **Runtime**: Azure Container Apps + Azure Functions
- **Observability**: Azure Application Insights (opencensus-ext-azure)

## Project Structure

```
apex/
├── src/apex/
│   ├── main.py                    # FastAPI application
│   ├── config.py                  # Pydantic settings (env-based)
│   ├── dependencies.py            # DI wiring, DB sessions
│   ├── api/v1/                    # API routers (projects, documents, estimates, health)
│   ├── models/
│   │   ├── enums.py              # ProjectStatus, ValidationStatus, AACEClass, TerrainType
│   │   ├── database.py           # SQLAlchemy ORM models with GUID type
│   │   └── schemas.py            # Pydantic DTOs, ErrorResponse, PaginatedResponse
│   ├── database/
│   │   ├── connection.py         # Engine with NullPool for stateless operation
│   │   └── repositories/         # Repository pattern (project, document, estimate, audit)
│   ├── services/
│   │   ├── llm/
│   │   │   └── orchestrator.py   # Maturity-aware LLM with AACE class routing
│   │   ├── document_parser.py    # Azure DI wrapper (async polling pattern)
│   │   ├── risk_analysis.py      # Monte Carlo engine (LHS, Iman-Conover, Spearman)
│   │   ├── aace_classifier.py    # AACE Class 1-5 determination
│   │   ├── cost_database.py      # Cost breakdown structure (CBS/WBS) builder
│   │   └── estimate_generator.py # Main orchestration service
│   ├── azure/                     # Managed Identity helpers, blob storage, key vault
│   └── utils/                     # logging, errors, retry, middleware
├── tests/
│   ├── fixtures/azure_mocks.py   # Mock Azure services for testing
│   ├── unit/                     # Service-level tests (risk, parser, classifier)
│   └── integration/              # API endpoint tests
├── alembic/                      # Database migrations
└── pyproject.toml               # Single source of dependency truth (NO requirements.txt)
```

## Core Architecture Principles

### Data Model
- **GUID Type Decorator**: Backend-agnostic UUID handling (mssql UNIQUEIDENTIFIER, postgres UUID, sqlite CHAR(36))
- **Relational First**: All analytical data (costs, quantities, risk factors) must be normalized tables, NOT JSON blobs
- **JSON Allowed Only For**: Audit trails (`AuditLog.details`), validation results (`Document.validation_result`)
- **Hierarchical Line Items**: `EstimateLineItem` uses `parent_line_item_id` + `wbs_code` for CBS/WBS hierarchy

### Session Management Pattern (CRITICAL)
```python
# dependencies.py - DO NOT DEVIATE FROM THIS PATTERN
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Auto-commit on success
    except Exception:
        db.rollback()  # Auto-rollback on error
        raise
    finally:
        db.close()
```
**Rule**: Repositories/services NEVER instantiate `SessionLocal()` directly - always receive `db: Session` via dependency injection.

### Security Requirements
- **Zero Trust**: All Azure services behind private endpoints, VNet-injected Container Apps
- **Managed Identity Only**: No hardcoded secrets, API keys, or connection strings with credentials
- **Application RBAC**: Check `User` + `ProjectAccess` + `AppRole` - AAD token alone is insufficient
- **ISO Compliance**: All operations must maintain audit trail in `AuditLog` table

## Key Service Components

### 1. LLM Orchestrator (`services/llm/orchestrator.py`)
**Maturity-Aware Design**: Routes prompts/tasks based on AACE class (not a flat client)

| AACE Class | Persona | Temperature | Use Case |
|------------|---------|-------------|----------|
| CLASS_5 | Conceptual Estimator | 0.7 | High-level budget ranges |
| CLASS_4 | Feasibility Analyst | 0.3 | Scope validation, gap identification |
| CLASS_3 | Budget Estimator | 0.1 | Quantity extraction, detailed assumptions |
| CLASS_2/1 | Auditor | 0.0 | Contractor bid cross-checking |

**Token Management**: Use tiktoken for counting, implement smart truncation (128K context, 4K response buffer)

### 2. Document Parser (`services/document_parser.py`)
**Azure Document Intelligence Integration** (async polling pattern):
- PDFs/scanned docs → **MUST** use Azure AI Document Intelligence
- Excel → `openpyxl`, Word → `python-docx`
- **PROHIBITED**: PyPDF2 for text/table extraction (simple operations only)

**Pattern**:
```python
async def analyze_document(document_bytes: bytes) -> Dict[str, Any]:
    poller = client.begin_analyze_document(model_id="prebuilt-layout", document=document_bytes)
    # Async polling with timeout (default 60s, 2s interval)
    result = await poll_with_timeout(poller)
    return extract_structured_content(result)  # Pages, tables, paragraphs
```

### 3. Monte Carlo Risk Analyzer (`services/risk_analysis.py`)
**Industrial-Grade Requirements** (toy implementations prohibited):
- **Sampling**: Latin Hypercube Sampling via `scipy.stats.qmc`
- **Distributions**: Triangular, normal, uniform, lognormal, PERT
- **Correlation**: Iman-Conover method (⚠️ HIGH-RISK - requires human validation)
- **Sensitivity**: Spearman rank correlations or SALib

**PROHIBITED**: `mcerp` package (outdated, NumPy incompatible)

**Critical Functions Requiring Human Review**:
- `_apply_iman_conover()` - Must validate against @RISK or similar before production
- `_transform_samples()` - Verify distribution transformations with known test cases

### 4. Cost Database Service (`services/cost_database.py`)
**Goal**: Project + documents → (base_cost, EstimateLineItem entities)

**Key Method**:
```python
def compute_base_cost(
    db: Session, project: Project, documents: List[Document], cost_code_map: Dict[str, CostCode]
) -> Tuple[Decimal, List[EstimateLineItem]]:
    # Returns: (total_cost, flat_list_of_line_items)
    # Line items have wbs_code + _temp_parent_ref (linking deferred to repository transaction)
```

**CBS Hierarchy Pattern**:
- Parent items: "10: Transmission Line" (summary rows)
- Child items: "10-100: Tangent Structures" (detail rows)
- Use `wbs_code` for deterministic parent mapping
- Actual GUID linking (`parent_line_item_id`) happens in `EstimateRepository.create_estimate_with_hierarchy()`

### 5. Estimate Generator (`services/estimate_generator.py`)
**Main Orchestration Flow**:
1. Load project & documents
2. Check user access (`ProjectAccess` table)
3. Classify AACE class (maturity + completeness)
4. Compute base cost + line items (`CostDatabaseService`)
5. Run Monte Carlo analysis → P50/P80/P95 costs
6. Generate narrative/assumptions/exclusions via LLM
7. Persist entire estimate graph in single transaction
8. Create audit log entry

## Development Commands

### Environment Setup
```bash
# Dependencies managed via pyproject.toml only
pip install -e .  # or use poetry/pdm if preferred

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Code quality
black src/ tests/ --line-length 100
isort src/ tests/ --profile black
flake8 src/ tests/
```

### Testing
```bash
# Unit tests (deterministic, mocked Azure services)
pytest tests/unit/test_risk_analysis.py -v
pytest tests/unit/test_document_parser.py -v
pytest tests/unit/test_cost_database_service.py -v

# Integration tests (API endpoints with test DB)
pytest tests/integration/ -v

# All tests with coverage
pytest tests/ --cov=apex --cov-report=term-missing
```

### Running Locally
```bash
# Set environment variables (see .env.example)
export AZURE_SQL_SERVER="..."
export AZURE_OPENAI_ENDPOINT="..."
# ... etc

# Development server
uvicorn apex.main:app --reload --host 0.0.0.0 --port 8000

# Health checks
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

## Critical Implementation Rules

### Database & ORM
1. **GUID Type**: Always use custom `GUID` TypeDecorator for all UUIDs (Azure SQL, Postgres, SQLite compatible)
2. **NullPool**: Use for stateless Azure Container Apps (`poolclass=NullPool`)
3. **Session Hygiene**: Always inject `db: Session` via `get_db()` dependency
4. **Migrations**: All schema changes via Alembic (no direct SQL DDL in production)

### API Layer
1. **Pagination**: All list endpoints return `PaginatedResponse[T]`
2. **Error Schema**: All non-2xx responses use `ErrorResponse` model
3. **Request IDs**: `RequestIDMiddleware` adds X-Request-ID header to all responses
4. **Exception Handling**: Global handlers for `BusinessRuleViolation` (400) and `Exception` (500)

### Azure Integration
1. **Retry Pattern**: Use `@azure_retry` decorator (3 attempts, exponential backoff 2-10s)
2. **Managed Identity**: All Azure clients use `DefaultAzureCredential()` - no secrets
3. **Blob Paths**: Store paths only in DB, never binary content
4. **App Insights**: Log all LLM calls (model, tokens, action, identifiers)

### Prohibited Practices
- ❌ Root-level `requirements.txt` as primary dependency source
- ❌ `mcerp` package for Monte Carlo
- ❌ PyPDF2 for text/table extraction (Azure DI mandatory)
- ❌ JSON blobs for analytical data (costs, quantities, risk factors)
- ❌ Hardcoded secrets, API keys, or credentials
- ❌ Toy/stub implementations for core services
- ❌ Direct instantiation of `SessionLocal()` outside `get_db()`

## Testing Patterns

### Azure Service Mocking
```python
# tests/fixtures/azure_mocks.py
class MockDocumentIntelligenceClient:
    def begin_analyze_document(self, model_id, document):
        # Return mock poller with deterministic results
        pass

class MockBlobServiceClient:
    def get_blob_client(self, container, blob):
        # Return mock blob client
        pass
```

### Risk Analysis Tests
- Use deterministic seeds (`random_seed=42`)
- Validate against known distributions
- Test Iman-Conover correlation preservation
- Verify Spearman sensitivity calculations

### API Integration Tests
- Mock Azure services (Document Intelligence, Blob, OpenAI)
- Use in-memory SQLite for test database
- Test full request/response cycle
- Validate pagination, error schemas, auth checks

## Common Pitfalls

1. **CBS Hierarchy**: Don't try to persist parent GUIDs immediately - use `wbs_code` + `_temp_parent_ref`, link in repository transaction
2. **Monte Carlo Correlation**: Iman-Conover is complex - implement conservatively, flag for human review
3. **Token Management**: Always check context window limits before LLM calls (128K - 4K buffer)
4. **Session Management**: Never commit/rollback manually in services - let `get_db()` handle it
5. **Document Parsing**: Azure DI is async with polling - implement proper timeout handling

## Configuration

Environment variables (via `pydantic-settings`):
- `AZURE_SQL_SERVER`, `AZURE_SQL_DATABASE` - Database connection
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` - LLM access
- `AZURE_STORAGE_ACCOUNT` - Blob storage
- `AZURE_APPINSIGHTS_CONNECTION_STRING` - Observability
- `DEFAULT_MONTE_CARLO_ITERATIONS=10000` - Risk analysis config
- `LOG_LEVEL=INFO` - Logging verbosity

Database URL pattern (Managed Identity):
```
mssql+pyodbc://@{server}/{database}?driver=ODBC+Driver+18+for+SQL+Server&Authentication=ActiveDirectoryMsi
```

## Future Enhancements (Not MVP)

These are documented in Section 18 of the specification but should NOT be implemented initially:
- Concurrency control for estimate generation (EstimateStatus enum)
- Redis caching for cost lookups
- Token-bucket rate limiting for LLM calls
- Custom telemetry metrics (estimate duration, parse time)
- Background job queue pattern (Azure Service Bus + Functions)

---

**Reference**: See `APEX_Prompt.md` for complete specification details and implementation requirements.
