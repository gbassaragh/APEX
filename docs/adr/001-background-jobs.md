# ADR 001: Background Job Pattern for Long-Running Operations

**Status**: Accepted

**Date**: 2025-01-20

**Deciders**: Development Team

---

## Context

The APEX estimation platform requires long-running operations that cannot block HTTP request/response cycles:

1. **Document Validation**: Azure Document Intelligence parsing (20-60 seconds for large PDFs)
2. **Estimate Generation**: Full orchestration workflow (30-90 seconds including LLM calls, Monte Carlo analysis)

Initial implementation used synchronous processing, causing:
- HTTP timeout issues (>30s requests)
- Poor user experience (blocked UI waiting for responses)
- Resource contention (async event loop blocked by CPU-bound operations)

We needed a pattern that:
- Returns immediate 202 Accepted responses
- Processes work asynchronously without blocking
- Provides status polling mechanism
- Works within Azure Container Apps constraints
- Maintains transactional integrity

## Decision

**We will use FastAPI's native async background job pattern with database-backed job tracking.**

### Architecture Components

1. **Job Entity**: `Job` database table tracks background operation state
   - `job_type`: "document_validation" | "estimate_generation"
   - `status`: "pending" | "running" | "completed" | "failed"
   - `progress_percent`: 0-100 for UI progress bars
   - `current_step`: Human-readable status for UI
   - `result_data`: JSON with operation results
   - `error_message`: Failure diagnostics

2. **API Pattern**: POST endpoints return `JobStatusResponse` with 202 Accepted
   ```python
   @router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
   async def generate_estimate(...):
       job = job_repo.create_job(db, job_type="estimate_generation", ...)
       asyncio.create_task(process_estimate_generation(job.id, ...))
       return JobStatusResponse(id=job.id, status="pending", ...)
   ```

3. **Worker Functions**: `background_jobs.py` contains async worker functions
   - Own database session management (`SessionLocal()`)
   - Progress updates via `job_repo.update_progress()`
   - Error handling with `job_repo.mark_failed()`
   - Transaction management with try/except/finally

4. **Polling Mechanism**: `GET /jobs/{job_id}` endpoint for status checks
   - Returns current job state
   - Includes `result_data` when completed
   - Client polls every 2-5 seconds

### Test Mode Override

For integration testing, synchronous execution via `config.TESTING` flag:
```python
if config.TESTING:
    await process_estimate_generation(...)  # Inline execution
else:
    asyncio.create_task(process_estimate_generation(...))  # Background
```

This ensures:
- Tests don't have race conditions
- Failures are caught immediately
- Test execution is deterministic

## Alternatives Considered

### Alternative 1: Azure Functions (Queue-Triggered)
**Rejected** because:
- Additional infrastructure complexity (Storage Queues, separate Function Apps)
- Increased latency (queue polling overhead ~1-5s)
- Higher cost (separate compute tier)
- More complex deployment (two services instead of one)
- Would still need `Job` table for status tracking

**Advantages we're giving up**:
- Automatic retry with dead-letter queue
- Better isolation (function crashes don't affect API)
- Horizontal scaling per queue partition

**When to revisit**: If job volume exceeds 1000/hour or job failures cause API instability.

### Alternative 2: Celery + Redis
**Rejected** because:
- Heavyweight dependency (Celery, Redis, monitoring)
- Azure Container Apps don't include managed Redis
- Would need Azure Cache for Redis (additional cost)
- Overkill for 2 job types with predictable duration

**Advantages we're giving up**:
- Task prioritization and routing
- Distributed task execution
- Rich monitoring/admin UI

**When to revisit**: If job types exceed 5 or need complex routing logic.

### Alternative 3: Synchronous with Streaming Responses
**Rejected** because:
- HTTP streaming requires persistent connections
- Container Apps can still timeout (max 240s)
- Client complexity (SSE or WebSocket handling)
- No benefit over polling for 30-90s jobs

## Consequences

### Positive

1. **Simplicity**: Single codebase, no additional infrastructure
2. **Fast Development**: Native FastAPI patterns, minimal boilerplate
3. **Cost-Effective**: No additional Azure services required
4. **Testability**: `TESTING` flag enables deterministic tests
5. **Transparency**: `Job` table provides full audit trail

### Negative

1. **No Automatic Retry**: Worker crashes lose in-flight jobs
   - **Mitigation**: Monitor job stuck in "running" state >5 minutes
2. **Limited Scalability**: All jobs run on Container App instances
   - **Mitigation**: Acceptable for <100 concurrent jobs
3. **Memory Pressure**: Large jobs (Monte Carlo with 100K iterations) run in-process
   - **Mitigation**: Container Apps have 2GB RAM, sufficient for MVP
4. **No Prioritization**: FIFO processing only
   - **Mitigation**: Acceptable with <10 users

### Operational Considerations

1. **Monitoring**: Use Application Insights to track:
   - Job duration (avg/p95/p99)
   - Failure rate by job_type
   - Jobs stuck in "running" state

2. **Cleanup**: Implement periodic job for old completed/failed jobs:
   ```sql
   DELETE FROM jobs
   WHERE status IN ('completed', 'failed')
   AND completed_at < DATEADD(day, -30, GETUTCDATE())
   ```

3. **Graceful Shutdown**: Container Apps SIGTERM handling:
   - Mark running jobs as "failed" with "container_restart" error
   - Users can retry via UI

## Implementation Notes

### Session Management Pattern

**CRITICAL**: Background workers must create their own database session:
```python
async def process_document_validation(job_id: UUID, ...):
    db = SessionLocal()  # Own session, NOT dependency injection
    try:
        # ... work ...
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

This avoids:
- Session lifecycle issues (FastAPI request session closed before job starts)
- Transaction conflicts (job transaction independent of API transaction)

### Progress Update Strategy

Update progress at major milestones, not continuously:
```python
job_repo.update_progress(db, job_id, 10, "Loading document")
job_repo.update_progress(db, job_id, 35, "Parsing with Azure DI")
job_repo.update_progress(db, job_id, 55, "Running LLM validation")
job_repo.update_progress(db, job_id, 90, "Saving results")
```

Frequent updates (every second) create database contention.

### Error Message Guidelines

Include enough detail for support team debugging:
```python
job_repo.mark_failed(
    db, job_id,
    f"Document parsing failed: {str(error)}. Check Document Intelligence service status."
)
```

Avoid exposing internal details to end users (sanitize in UI layer).

## Related Decisions

- **ADR 002**: GUID TypeDecorator (job IDs use UUID primary keys)
- **Future ADR**: When to migrate to Azure Functions (threshold criteria)

## References

- ImprovementPlan.md: Phase 1 implementation details
- `src/apex/services/background_jobs.py`: Worker implementation
- `src/apex/database/repositories/job_repository.py`: Job CRUD operations
- `src/apex/api/v1/estimates.py`: API endpoint example (POST /generate)
