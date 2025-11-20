# ADR 002: GUID TypeDecorator for Cross-Database UUID Compatibility

**Status**: Accepted

**Date**: 2025-01-20

**Deciders**: Development Team

---

## Context

The APEX platform uses UUIDs (GUIDs) as primary keys for all entities to support:

1. **Distributed System Compatibility**: Pre-generated IDs for client-side optimistic UI updates
2. **Data Migration**: Merge data from multiple sources without ID conflicts
3. **Security**: Non-sequential IDs prevent enumeration attacks
4. **API Clarity**: Readable identifiers in URLs and logs

However, different database backends represent UUIDs differently:

| Database | Native Type | Storage Format | Example |
|----------|-------------|----------------|---------|
| **Azure SQL Server** | `UNIQUEIDENTIFIER` | 16-byte binary | `6F9619FF-8B86-D011-B42D-00C04FC964FF` |
| **PostgreSQL** | `UUID` | 16-byte binary | `a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11` |
| **SQLite** | No native type | 36-char string | `550e8400-e29b-41d4-a716-446655440000` |

This creates challenges:

1. **SQLAlchemy Type Inconsistency**: Default `UUID` type fails on SQL Server
2. **Migration Complexity**: Different Alembic migrations per database
3. **Test Environment Mismatch**: SQLite (testing) vs SQL Server (production) behavioral differences
4. **Application Logic Coupling**: Code shouldn't know which database it's using

## Decision

**We will use a custom SQLAlchemy `TypeDecorator` called `GUID` that abstracts UUID handling across all database backends.**

### Implementation

**File**: `src/apex/models/database.py`

```python
class GUID(TypeDecorator):
    """
    Platform-independent GUID type.

    Uses UNIQUEIDENTIFIER for MSSQL, UUID for PostgreSQL, CHAR(36) for SQLite.
    Stores as string internally, converts to UUID on retrieval.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'mssql':
            return dialect.type_descriptor(UNIQUEIDENTIFIER())
        elif dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'mssql':
            return str(value)
        elif dialect.name == 'postgresql':
            return value if isinstance(value, uuid.UUID) else uuid.UUID(value)
        else:
            return str(value) if isinstance(value, uuid.UUID) else value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value
```

### Usage in Models

All primary key and foreign key columns use `GUID` type:

```python
class Project(Base):
    __tablename__ = "projects"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    created_by_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
```

### Alembic Migration Pattern

Migrations automatically adapt based on database dialect:

```python
# Generated migration works across all databases
def upgrade():
    op.create_table('projects',
        sa.Column('id', apex.models.database.GUID(), nullable=False),
        sa.Column('created_by_id', apex.models.database.GUID(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
```

## Alternatives Considered

### Alternative 1: Database-Specific Migrations
**Rejected** because:
- Requires maintaining separate migration branches per database
- High maintenance burden (3x migration work)
- Error-prone (easy to miss updates across branches)
- Breaks "write once, deploy anywhere" principle

**Advantages we're giving up**:
- Slightly better performance (no type conversion overhead)
- Native database tooling compatibility (SQL Server Management Studio)

### Alternative 2: String Primary Keys Everywhere
**Rejected** because:
- 36-byte strings vs 16-byte UUIDs (2.25x storage overhead)
- Index size bloat (primary + foreign key indexes)
- No database-level type safety
- Application code must validate UUID format

**Advantages we're giving up**:
- No TypeDecorator complexity
- Works identically on all databases without conversion

### Alternative 3: Use PostgreSQL UUID Type Only
**Rejected** because:
- Locks us into PostgreSQL (Azure SQL Server requirement)
- Can't use SQL Server Managed Instance cost benefits
- Limits database choice for future scaling

## Consequences

### Positive

1. **Database Portability**: Single codebase works on SQL Server, PostgreSQL, SQLite
2. **Test Parity**: SQLite tests represent production behavior accurately
3. **Migration Simplicity**: One Alembic migration per schema change
4. **Type Safety**: Python code always works with `uuid.UUID` objects
5. **Production Flexibility**: Can switch databases without application changes

### Negative

1. **Conversion Overhead**: Minimal type conversion on every DB read/write
   - **Impact**: <1ms per operation, negligible for APEX workload
2. **SQL Server Query Quirks**: String comparison in binds requires `str(uuid)`
   - **Mitigation**: `process_bind_param` handles this automatically
3. **SQLite Limitations**: No native UUID indexes, uses string collation
   - **Mitigation**: Only affects local testing, not production

### Operational Considerations

1. **Raw SQL Queries**: When writing raw SQL, use parameter binding:
   ```python
   # Correct (TypeDecorator handles conversion)
   result = db.execute(
       text("SELECT * FROM projects WHERE id = :id"),
       {"id": project_id}  # project_id is uuid.UUID
   )

   # Incorrect (bypasses TypeDecorator)
   result = db.execute(
       text(f"SELECT * FROM projects WHERE id = '{project_id}'")
   )
   ```

2. **Database Administration**: SQL Server DBAs may see GUIDs as strings in some tools
   - Use CAST in queries: `CAST(id AS VARCHAR(36))` for readability

3. **Performance**: GUIDs have known index fragmentation issues
   - **Mitigation**: Acceptable for APEX entity counts (<100K projects)
   - **Future**: Consider sequential UUIDs (UUIDv7) if fragmentation observed

## Implementation Notes

### Null Handling

TypeDecorator returns `None` for NULL database values:
```python
project = db.get(Project, project_id)
if project is None:
    # Not found (expected behavior)
    pass
```

### Default Value Generation

Use `uuid.uuid4()` callable as default (not `uuid.uuid4`):
```python
# Correct (generates new UUID per row)
id = Column(GUID(), primary_key=True, default=uuid.uuid4)

# Incorrect (all rows get same UUID)
id = Column(GUID(), primary_key=True, default=uuid.uuid4())
```

### FastAPI Schema Integration

Pydantic models use `uuid.UUID` type for automatic validation:
```python
class ProjectResponse(BaseModel):
    id: UUID  # Automatically validates UUID format
    created_by_id: UUID

    class Config:
        from_attributes = True  # Enables ORM mode
```

### Testing Pattern

Tests can use string UUIDs for readability:
```python
from uuid import UUID

# Both work (TypeDecorator converts)
project_id = UUID("550e8400-e29b-41d4-a716-446655440000")
project_id = "550e8400-e29b-41d4-a716-446655440000"  # Converted to UUID

project = db.get(Project, project_id)
```

## Related Decisions

- **ADR 001**: Background Jobs (Job IDs use GUID type)
- **Future ADR**: If migrating to UUIDv7 for better index performance

## References

- SQLAlchemy TypeDecorator Documentation: https://docs.sqlalchemy.org/en/20/core/custom_types.html
- `src/apex/models/database.py`: GUID implementation
- APEX_Prompt.md: Section on GUID type requirements
- Azure SQL UNIQUEIDENTIFIER: https://learn.microsoft.com/en-us/sql/t-sql/data-types/uniqueidentifier-transact-sql
