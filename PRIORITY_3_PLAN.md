# APEX Phase 3 Priority 3 Implementation Plan

## Repository Layer - Data Access Pattern

### Status: Priority 0 ✅ | Priority 1 ✅ | Priority 2+ ✅ | Priority 3 🔄

---

## Overview

Implement the **Repository Pattern** for clean separation between business logic (services) and data access. All database operations go through repositories, which provide:

- Clean CRUD operations
- Query abstraction
- Transaction management
- Pagination support
- Type safety with SQLAlchemy ORM

**Dependencies**: Priority 2+ services layer references these repositories and must be wired via dependency injection.

---

## Current Status

### Existing Files
- ✅ `database/repositories/base.py` (137 lines) - Base repository with common CRUD patterns
- ⚠️ `database/repositories/project_repository.py` (10 lines) - **STUB** - needs full implementation
- ⚠️ `database/repositories/document_repository.py` (10 lines) - **STUB** - needs full implementation
- ⚠️ `database/repositories/estimate_repository.py` (130 lines) - **PARTIAL** - has create_estimate_with_hierarchy, needs CRUD
- ⚠️ `database/repositories/audit_repository.py` (10 lines) - **STUB** - needs full implementation

### Referenced in Services
- `estimate_generator.py` uses all 4 repositories
- API layer will use repositories for all data access

---

## Implementation Order

### Phase 3A: Review Base Repository Pattern
1. **Review database/repositories/base.py** - Verify common CRUD + pagination helpers

### Phase 3B: Implement Core Repositories
2. **database/repositories/project_repository.py** - Project CRUD + access control
3. **database/repositories/document_repository.py** - Document CRUD + validation status queries
4. **database/repositories/audit_repository.py** - Audit log append-only operations

### Phase 3C: Enhance Estimate Repository
5. **database/repositories/estimate_repository.py** - Complete CRUD + CBS/WBS hierarchy transaction

---

## Repository Specifications

### 1. database/repositories/base.py (Review/Enhance)

**Current Implementation**: Common CRUD operations and pagination

**Expected Methods**:
```python
class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model

    def get_by_id(self, db: Session, id: UUID) -> Optional[T]
    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[T]
    def create(self, db: Session, obj: T) -> T
    def update(self, db: Session, id: UUID, updates: Dict[str, Any]) -> T
    def delete(self, db: Session, id: UUID) -> bool

    # Pagination helper
    def paginate(
        self,
        db: Session,
        query: Query,
        page: int,
        page_size: int
    ) -> Tuple[List[T], int, bool, bool]
```

**Review Focus**:
- ✅ Type safety with Generic[T]
- ✅ Proper transaction handling (no commits in base - let get_db() handle it)
- ✅ Pagination returns: (items, total, has_next, has_prev)
- ⚠️ Add common query filters (e.g., by_status, by_date_range)

---

### 2. database/repositories/project_repository.py (Implement)

**Purpose**: Project CRUD + access control queries

**Key Methods**:
```python
class ProjectRepository:
    def __init__(self):
        self.base = BaseRepository(Project)

    # Standard CRUD (delegate to base)
    def get_by_id(self, db: Session, project_id: UUID) -> Optional[Project]
    def get_by_project_number(self, db: Session, project_number: str) -> Optional[Project]
    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[Project]
    def create(self, db: Session, project: Project) -> Project
    def update(self, db: Session, project_id: UUID, updates: Dict[str, Any]) -> Project
    def delete(self, db: Session, project_id: UUID) -> bool

    # Pagination
    def get_paginated(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: Optional[ProjectStatus] = None,
        user_id: Optional[UUID] = None  # Filter by user access
    ) -> Tuple[List[Project], int, bool, bool]

    # Access control (CRITICAL)
    def check_user_access(
        self,
        db: Session,
        user_id: UUID,
        project_id: UUID
    ) -> bool:
        """Check if user has ProjectAccess for project."""
        # Query ProjectAccess table

    def get_user_projects(
        self,
        db: Session,
        user_id: UUID,
        role: Optional[str] = None  # Filter by AppRole
    ) -> List[Project]:
        """Get all projects user has access to."""
        # Join Project -> ProjectAccess -> filter by user_id

    def grant_access(
        self,
        db: Session,
        user_id: UUID,
        project_id: UUID,
        role_id: int  # AppRole.id
    ) -> ProjectAccess:
        """Grant user access to project with specific role."""

    def revoke_access(
        self,
        db: Session,
        user_id: UUID,
        project_id: UUID
    ) -> bool:
        """Revoke user access to project."""
```

**Dependencies**:
- models.database (Project, ProjectAccess, User, AppRole)
- models.enums (ProjectStatus)
- BaseRepository

**Critical Notes**:
- MUST implement `check_user_access()` - used by estimate_generator
- Access control queries must join ProjectAccess table
- Never bypass access checks

---

### 3. database/repositories/document_repository.py (Implement)

**Purpose**: Document CRUD + project-specific queries

**Key Methods**:
```python
class DocumentRepository:
    def __init__(self):
        self.base = BaseRepository(Document)

    # Standard CRUD
    def get_by_id(self, db: Session, document_id: UUID) -> Optional[Document]
    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[Document]
    def create(self, db: Session, document: Document) -> Document
    def update(self, db: Session, document_id: UUID, updates: Dict[str, Any]) -> Document
    def delete(self, db: Session, document_id: UUID) -> bool

    # Project-specific queries (REQUIRED by estimate_generator)
    def get_by_project_id(
        self,
        db: Session,
        project_id: UUID,
        document_type: Optional[str] = None,
        validation_status: Optional[ValidationStatus] = None
    ) -> List[Document]:
        """Get all documents for a project (with optional filters)."""

    # Pagination
    def get_paginated(
        self,
        db: Session,
        project_id: UUID,
        page: int = 1,
        page_size: int = 20,
        document_type: Optional[str] = None
    ) -> Tuple[List[Document], int, bool, bool]

    # Validation status queries
    def get_validated_documents(
        self,
        db: Session,
        project_id: UUID
    ) -> List[Document]:
        """Get only validated documents (completeness_score >= 70)."""

    def update_validation_result(
        self,
        db: Session,
        document_id: UUID,
        validation_result: Dict[str, Any],
        completeness_score: int,
        validation_status: ValidationStatus
    ) -> Document:
        """Update document validation result (from LLM validation)."""
```

**Dependencies**:
- models.database (Document, Project)
- models.enums (ValidationStatus)
- BaseRepository

**Critical Notes**:
- `get_by_project_id()` is called by estimate_generator - REQUIRED
- Validation result is JSON (acceptable per spec for audit data)
- Filter by validation_status for quality gate checks

---

### 4. database/repositories/audit_repository.py (Implement)

**Purpose**: Audit log append-only operations

**Key Methods**:
```python
class AuditRepository:
    def __init__(self):
        self.base = BaseRepository(AuditLog)

    # Append-only operations
    def create(self, db: Session, audit_log: AuditLog) -> AuditLog:
        """Create audit log entry (append-only, no updates/deletes)."""

    # Query operations
    def get_by_id(self, db: Session, audit_id: UUID) -> Optional[AuditLog]

    def get_by_project_id(
        self,
        db: Session,
        project_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get all audit logs for a project."""

    def get_by_estimate_id(
        self,
        db: Session,
        estimate_id: UUID
    ) -> List[AuditLog]:
        """Get all audit logs for an estimate."""

    def get_by_user_id(
        self,
        db: Session,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get all audit logs for a user."""

    # Pagination
    def get_paginated(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 50,
        project_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        action: Optional[str] = None
    ) -> Tuple[List[AuditLog], int, bool, bool]

    # Compliance reporting
    def get_by_date_range(
        self,
        db: Session,
        start_date: datetime,
        end_date: datetime,
        project_id: Optional[UUID] = None
    ) -> List[AuditLog]:
        """Get audit logs for compliance reporting."""
```

**Dependencies**:
- models.database (AuditLog)
- BaseRepository

**Critical Notes**:
- **Append-only**: No update() or delete() methods (immutable audit trail)
- ISO-NE compliance requires comprehensive audit trail
- Log all estimate generation steps (used by estimate_generator)

---

### 5. database/repositories/estimate_repository.py (Enhance)

**Current Status**: Has `create_estimate_with_hierarchy()` implementation (130 lines)

**Review & Add Missing Methods**:
```python
class EstimateRepository:
    def __init__(self):
        self.base = BaseRepository(Estimate)

    # Standard CRUD
    def get_by_id(self, db: Session, estimate_id: UUID) -> Optional[Estimate]:
        """Get estimate with all relationships loaded (line_items, assumptions, etc.)."""
        # Use joinedload for relationships

    def get_by_estimate_number(
        self,
        db: Session,
        estimate_number: str
    ) -> Optional[Estimate]:
        """Get estimate by estimate number."""

    def get_by_project_id(
        self,
        db: Session,
        project_id: UUID,
        aace_class: Optional[AACEClass] = None
    ) -> List[Estimate]:
        """Get all estimates for a project."""

    def get_paginated(
        self,
        db: Session,
        project_id: UUID,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Estimate], int, bool, bool]

    # Complex transaction (ALREADY IMPLEMENTED - REVIEW)
    def create_estimate_with_hierarchy(
        self,
        db: Session,
        estimate: Estimate,
        line_items: List[EstimateLineItem],
        assumptions: List[EstimateAssumption],
        exclusions: List[EstimateExclusion],
        risk_factors: List[EstimateRiskFactor]
    ) -> Estimate:
        """
        Create estimate with full hierarchy in single transaction.

        CRITICAL:
        1. Persist estimate first to get estimate.id
        2. Link line item parent GUIDs using wbs_code + _temp_parent_ref
        3. Persist line_items, assumptions, exclusions, risk_factors
        4. Return persisted estimate with all relationships

        This is called by estimate_generator - MUST work correctly.
        """
        # Current implementation needs review

    # Line item queries
    def get_line_items(
        self,
        db: Session,
        estimate_id: UUID,
        parent_only: bool = False
    ) -> List[EstimateLineItem]:
        """Get line items (optionally filter to parent rows only)."""

    def get_line_item_hierarchy(
        self,
        db: Session,
        estimate_id: UUID
    ) -> List[EstimateLineItem]:
        """Get line items with parent-child relationships loaded."""
```

**Dependencies**:
- models.database (Estimate, EstimateLineItem, EstimateAssumption, EstimateExclusion, EstimateRiskFactor)
- models.enums (AACEClass)
- BaseRepository

**Critical Notes**:
- **`create_estimate_with_hierarchy()` is HIGH-RISK** - must handle:
  - Parent GUID linking using `_temp_parent_ref` + `wbs_code`
  - Single transaction for all entities
  - Proper foreign key ordering (estimate → children)
- CBS/WBS parent linking logic must be deterministic and correct
- Review existing implementation before adding CRUD methods

---

## Implementation Strategy

### Phase 3A: Review Base (30 minutes)
- Review base.py for completeness
- Add any missing pagination/query helpers
- Verify transaction handling patterns

### Phase 3B: Implement Repositories (3-4 hours)
- Implement project_repository.py (access control critical)
- Implement document_repository.py (project queries)
- Implement audit_repository.py (append-only)

### Phase 3C: Enhance Estimate Repository (1-2 hours)
- Review create_estimate_with_hierarchy() for parent linking
- Add standard CRUD methods
- Add line item queries

### Total Estimated Time: 5-7 hours

---

## Testing Strategy

1. **Unit Tests**: Each repository with SQLite in-memory database
2. **Transaction Tests**: Verify rollback behavior on errors
3. **Pagination Tests**: Edge cases (empty results, single page, etc.)
4. **Access Control Tests**: User permissions (critical for security)
5. **Hierarchy Tests**: CBS/WBS parent linking correctness

---

## Success Criteria

- ✅ All repositories implement required methods
- ✅ No direct Session commits (transaction management via get_db())
- ✅ Pagination returns consistent schema
- ✅ Access control enforced at repository level
- ✅ Parent GUID linking works correctly in create_estimate_with_hierarchy()
- ✅ Unit tests cover all CRUD operations
- ✅ Integration with estimate_generator validated

---

## Risk Areas Requiring Validation

1. **CBS/WBS Parent Linking** (estimate_repository.py)
   - Must correctly map `_temp_parent_ref` → `parent_line_item_id` GUIDs
   - Test with multi-level hierarchy (parents + children + grandchildren if needed)
   - Verify deterministic ordering (parents before children)

2. **Access Control** (project_repository.py)
   - `check_user_access()` must be bulletproof
   - Never bypass ProjectAccess table
   - Test with multiple users + roles

3. **Transaction Safety** (all repositories)
   - No commits in repository methods
   - Proper exception propagation for rollback
   - Test rollback scenarios

---

## Next Phase After Priority 3

**Priority 4: API Layer** - FastAPI endpoints using repositories:
- `api/v1/projects.py` - Project CRUD + access control endpoints
- `api/v1/documents.py` - Document upload, validation, retrieval
- `api/v1/estimates.py` - Estimate generation, retrieval, export

---

**End of Priority 3 Plan**
