# APEX Phase 4 Priority 4 Implementation Plan

## API Layer - FastAPI Endpoints

### Status: Priority 0 ✅ | Priority 1 ✅ | Priority 2+ ✅ | Priority 3 ✅ | Priority 4 🔄

---

## Overview

Implement **FastAPI REST API endpoints** that expose the APEX estimation platform to users. All endpoints use dependency injection for repositories/services, enforce access control, and return consistent response schemas.

**Dependencies**: Priority 3 repositories must be complete and tested before API implementation.

---

## Current Status

### Existing Files
- ✅ `api/v1/health.py` (45 lines) - Health check endpoints (live/ready)
- ✅ `api/v1/router.py` (21 lines) - Router aggregation stub
- ⚠️ `api/v1/__init__.py` (0 lines) - Empty placeholder
- ⚠️ `models/schemas.py` (partial) - Has ErrorResponse, PaginatedResponse, needs DTOs
- ❌ `api/v1/projects.py` - **MISSING** - Project CRUD endpoints
- ❌ `api/v1/documents.py` - **MISSING** - Document upload/validation endpoints
- ❌ `api/v1/estimates.py` - **MISSING** - Estimate generation/retrieval endpoints

### Referenced Services & Repositories
All services and repositories from Priority 2+ and Priority 3 are complete and ready for API integration.

---

## Implementation Order

### Phase 4A: Pydantic Schemas & DTOs (1-2 hours)
1. **Extend models/schemas.py** with request/response DTOs
2. Implement project, document, estimate schemas
3. Validation rules, field constraints, examples

### Phase 4B: Project Endpoints (2-3 hours)
4. **api/v1/projects.py** - Project CRUD with access control
5. Wire ProjectRepository via dependency injection
6. Enforce user access checks on all operations

### Phase 4C: Document Endpoints (2-3 hours)
7. **api/v1/documents.py** - Upload, validation, retrieval
8. Wire DocumentRepository and Azure Blob Storage
9. Async document parsing integration

### Phase 4D: Estimate Endpoints (3-4 hours)
10. **api/v1/estimates.py** - Generation, retrieval, export
11. Wire EstimateGenerator service (full orchestration)
12. Long-running estimate generation handling

### Phase 4E: Router Integration & Main App (1 hour)
13. Update **api/v1/router.py** to include all endpoint routers
14. Update **main.py** to mount v1 router
15. Verify middleware and error handling integration

### Total Estimated Time: 9-13 hours

---

## API Specifications

### Common Patterns

**Authentication & Authorization**:
- All endpoints receive `current_user: User` via dependency injection
- Access control enforced by checking `ProjectAccess` table
- AAD token validation handled by Azure AD middleware (future)

**Response Schemas**:
- Success: Pydantic model or `PaginatedResponse[T]`
- Error: `ErrorResponse` with request_id, timestamp, error_code
- All list endpoints use pagination (default page_size=20)

**Error Handling**:
- `BusinessRuleViolation` → 400 Bad Request
- `ValueError` (not found) → 404 Not Found
- Unhandled exceptions → 500 Internal Server Error
- All errors include X-Request-ID header

---

## 1. models/schemas.py (Extend)

**Current Status**: Has ErrorResponse, ValidationError, PaginatedResponse

**Add Request/Response DTOs**:

### Project Schemas
```python
class ProjectBase(BaseModel):
    project_number: str = Field(..., max_length=50, example="TX-2024-001")
    project_name: str = Field(..., max_length=255)
    voltage_level: Optional[int] = Field(None, ge=0, le=765, example=345)
    line_miles: Optional[float] = Field(None, ge=0, example=12.5)
    terrain_type: Optional[TerrainType] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    project_name: Optional[str] = Field(None, max_length=255)
    voltage_level: Optional[int] = Field(None, ge=0, le=765)
    line_miles: Optional[float] = Field(None, ge=0)
    terrain_type: Optional[TerrainType] = None
    status: Optional[ProjectStatus] = None

class ProjectResponse(ProjectBase):
    id: UUID
    status: ProjectStatus
    created_at: datetime
    created_by_id: UUID

    class Config:
        from_attributes = True
```

### Document Schemas
```python
class DocumentUploadResponse(BaseModel):
    id: UUID
    project_id: UUID
    document_type: str
    blob_path: str
    validation_status: ValidationStatus
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    document_type: str
    blob_path: str
    validation_status: ValidationStatus
    completeness_score: Optional[int] = None
    validation_result: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
```

### Estimate Schemas
```python
class RiskFactorInput(BaseModel):
    name: str = Field(..., max_length=255)
    distribution: str = Field(..., regex="^(triangular|normal|uniform|lognormal|pert)$")
    min_value: Optional[float] = None
    most_likely: Optional[float] = None
    max_value: Optional[float] = None
    mean: Optional[float] = None
    std_dev: Optional[float] = None

class EstimateGenerateRequest(BaseModel):
    project_id: UUID
    risk_factors: List[RiskFactorInput] = []
    confidence_level: float = Field(0.80, ge=0.01, le=0.99)
    monte_carlo_iterations: int = Field(10000, ge=1000, le=100000)

class EstimateResponse(BaseModel):
    id: UUID
    project_id: UUID
    estimate_number: str
    aace_class: AACEClass
    base_cost: Decimal
    contingency_percentage: Optional[float]
    p50_cost: Optional[Decimal]
    p80_cost: Optional[Decimal]
    p95_cost: Optional[Decimal]
    narrative: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {Decimal: str}
```

---

## 2. api/v1/projects.py (Implement)

**Purpose**: Project CRUD operations with access control enforcement

**Key Endpoints**:
```python
POST   /projects                     # Create new project
GET    /projects                     # List projects (paginated, user-scoped)
GET    /projects/{project_id}        # Get project details
PATCH  /projects/{project_id}        # Update project
DELETE /projects/{project_id}        # Delete project (soft delete recommended)

POST   /projects/{project_id}/access # Grant user access
DELETE /projects/{project_id}/access # Revoke user access
```

**Critical Requirements**:
- MUST call `project_repo.check_user_access()` before allowing operations
- List endpoint MUST filter by `current_user.id` (user sees only their projects)
- Access control endpoints require "Manager" or "Admin" role
- All mutations create audit log entries

**Dependencies**:
```python
def get_project_repo() -> ProjectRepository:
    return ProjectRepository()

def get_audit_repo() -> AuditRepository:
    return AuditRepository()

def get_current_user(db: Session = Depends(get_db)) -> User:
    # TODO: Parse AAD token, lookup user in database
    # For now, return stub user for testing
    pass
```

**Example Endpoint**:
```python
@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
):
    """
    Create new project and grant creator access with Estimator role.
    """
    # Create project
    project_data = project_in.model_dump()
    project_data["created_by_id"] = current_user.id
    project = project_repo.create(db, project_data)

    # Grant creator access (Estimator role = 1)
    project_repo.grant_access(db, current_user.id, project.id, role_id=1)

    # Create audit log
    audit_repo.create(db, {
        "project_id": project.id,
        "user_id": current_user.id,
        "action": "created",
        "details": {"project_number": project.project_number},
    })

    return project
```

---

## 3. api/v1/documents.py (Implement)

**Purpose**: Document upload, parsing, validation, and retrieval

**Key Endpoints**:
```python
POST   /documents/upload                  # Upload document to blob storage
POST   /documents/{document_id}/validate  # Trigger LLM validation
GET    /documents/{document_id}           # Get document details
GET    /projects/{project_id}/documents   # List project documents (paginated)
DELETE /documents/{document_id}           # Delete document
```

**Critical Requirements**:
- Upload must save to Azure Blob Storage
- Return blob_path in database, not binary content
- Validation triggers async LLM orchestrator
- Access control: user must have access to parent project
- Support multipart/form-data for file uploads

**Dependencies**:
```python
def get_document_repo() -> DocumentRepository:
    return DocumentRepository()

def get_blob_storage() -> BlobStorageClient:
    # From apex.azure.blob_storage
    return BlobStorageClient()

def get_llm_orchestrator() -> LLMOrchestrator:
    # From apex.services.llm.orchestrator
    return LLMOrchestrator()
```

**Upload Flow**:
1. Receive multipart file upload
2. Save to Azure Blob Storage (`container: uploads, path: {project_id}/{timestamp}_{filename}`)
3. Create Document entity with blob_path, validation_status=PENDING
4. Return DocumentUploadResponse
5. (Future) Trigger async document parsing via Azure Function

**Validation Flow**:
1. Load document from blob storage
2. Call DocumentParser to extract structured content
3. Call LLMOrchestrator.validate_document()
4. Update Document entity with validation_result, completeness_score
5. Return updated DocumentResponse

---

## 4. api/v1/estimates.py (Implement)

**Purpose**: Estimate generation orchestration and retrieval

**Key Endpoints**:
```python
POST   /estimates/generate               # Generate new estimate (long-running)
GET    /estimates/{estimate_id}          # Get estimate with details
GET    /projects/{project_id}/estimates  # List project estimates (paginated)
GET    /estimates/{estimate_id}/export   # Export estimate (JSON/CSV/PDF)
```

**Critical Requirements**:
- Generation is long-running (30s - 5min depending on complexity)
- MUST call EstimateGenerator.generate_estimate() (14-step workflow)
- Access control: user must have access to parent project
- Return estimate immediately, not wait for completion
- Future enhancement: background job + polling endpoint

**Dependencies**:
```python
def get_estimate_repo() -> EstimateRepository:
    return EstimateRepository()

def get_estimate_generator() -> EstimateGenerator:
    # Full service with all dependencies
    return EstimateGenerator(
        project_repo=get_project_repo(),
        document_repo=get_document_repo(),
        estimate_repo=get_estimate_repo(),
        audit_repo=get_audit_repo(),
        llm_orchestrator=get_llm_orchestrator(),
        risk_analyzer=get_risk_analyzer(),
        aace_classifier=get_aace_classifier(),
        cost_db_service=get_cost_db_service(),
    )
```

**Generation Flow**:
1. Validate request (project exists, user has access)
2. Call EstimateGenerator.generate_estimate()
   - Load project & documents
   - Classify AACE class
   - Compute base cost + CBS hierarchy
   - Run Monte Carlo analysis
   - Generate narrative/assumptions/exclusions via LLM
   - Persist estimate with full hierarchy
3. Return EstimateResponse
4. Client can poll GET /estimates/{estimate_id} for status

**Export Endpoint**:
- JSON: Full estimate with line items, assumptions, exclusions, risk factors
- CSV: Flattened line items with cost breakdown
- PDF: Professional estimate report (future enhancement)

---

## 5. api/v1/router.py (Update)

**Current Status**: Stub that includes only health router

**Update to Include All Routers**:
```python
from fastapi import APIRouter
from apex.api.v1 import health, projects, documents, estimates

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(estimates.router, prefix="/estimates", tags=["estimates"])
```

---

## 6. main.py (Update)

**Current Status**: Basic FastAPI app with health checks

**Updates Required**:
1. Mount v1 router at `/api/v1`
2. Add CORS middleware configuration
3. Ensure RequestIDMiddleware is active
4. Verify global exception handlers are registered

**No changes needed** if these are already in place from Priority 0-1.

---

## Testing Strategy

### Unit Tests (api/v1/)
- Mock repositories to test endpoint logic
- Verify request validation (Pydantic)
- Test response serialization
- Access control enforcement

### Integration Tests (tests/integration/)
- Full request/response cycle with test database
- Test pagination parameters
- Error response schemas
- Multipart file upload (documents)

### Manual Testing
```bash
# Start development server
uvicorn apex.main:app --reload

# Test health checks
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready

# Test API endpoints
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"project_number": "TEST-001", "project_name": "Test Project"}'

curl http://localhost:8000/api/v1/projects
```

---

## Success Criteria

- ✅ All endpoints return correct status codes (200, 201, 400, 404, 500)
- ✅ All responses match Pydantic schemas
- ✅ Access control enforced on all project-scoped operations
- ✅ Pagination works correctly on all list endpoints
- ✅ Error responses include request_id and follow ErrorResponse schema
- ✅ File upload works with Azure Blob Storage
- ✅ Estimate generation completes successfully (14-step workflow)
- ✅ Audit logs created for all mutations
- ✅ FastAPI OpenAPI docs auto-generated at /docs

---

## Risk Areas Requiring Validation

1. **Access Control Enforcement** (CRITICAL)
   - MUST check user access before allowing operations
   - Test with multiple users and roles
   - Verify users cannot access projects they don't have rights to

2. **Long-Running Estimate Generation**
   - Current implementation is synchronous (blocking)
   - May timeout on complex projects (>30s)
   - Future enhancement: background job pattern with polling

3. **File Upload Handling**
   - Multipart form data parsing
   - Large file handling (streaming)
   - Blob storage error handling

4. **Transaction Safety**
   - get_db() dependency handles commit/rollback
   - Ensure no manual commits in endpoint handlers
   - Test rollback on errors

---

## Next Phase After Priority 4

**Priority 5: Deployment & Infrastructure**
- Alembic migrations for database schema
- Azure Container Apps deployment configuration
- Environment variable management (Azure Key Vault)
- CI/CD pipeline (GitHub Actions)
- Monitoring and alerting (Application Insights)

---

**End of Priority 4 Plan**
