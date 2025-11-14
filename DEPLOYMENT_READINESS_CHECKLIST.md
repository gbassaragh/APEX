# APEX Deployment Readiness Checklist

**Version:** 0.1.0
**Last Updated:** 2025-01-XX
**Status:** PRE-PRODUCTION - CRITICAL BLOCKERS REMAIN

---

## ✅ Completed Components

### Data Layer (Priority 1-2)
- [x] SQLAlchemy ORM models with GUID type decorator
- [x] Alembic migration framework configured
- [x] Repository pattern implementation
- [x] Session management with auto-commit/rollback
- [x] Pagination support for list queries
- [x] Multi-role RBAC via ProjectAccess table

### Business Logic (Priority 2-3)
- [x] Monte Carlo risk analysis engine (LHS, correlation, sensitivity)
- [x] AACE classification system
- [x] Cost database service architecture
- [x] Estimate generation orchestration framework
- [x] LLM orchestrator with maturity-aware routing

### API Layer (Priority 4)
- [x] FastAPI REST endpoints (projects, documents, estimates)
- [x] Request/response schema validation
- [x] Error handling with ErrorResponse schema
- [x] Pagination on all list endpoints
- [x] Role-based access control enforcement
- [x] Audit logging for all state changes
- [x] File upload security (size limits, MIME validation, filename sanitization)

### Security Hardening
- [x] Manager role enforcement on project PATCH/DELETE
- [x] Role_id validation in access grant operations
- [x] Path traversal prevention in filename handling
- [x] Control character and Unicode sanitization
- [x] File size limits (50 MB default)
- [x] MIME type validation for uploads
- [x] Windows device name prevention

---

## 🚨 CRITICAL BLOCKERS (Must Fix Before Production)

### 1. Authentication & Authorization (BLOCKER #1)
**Status:** ⛔ STUB IMPLEMENTATION - PRODUCTION UNSAFE

**Current State:**
- `dependencies.py:get_current_user()` returns hardcoded test user
- No Azure AD token validation
- No bearer token extraction from Authorization header

**Required Actions:**
- [ ] Implement Azure AD OAuth 2.0 token validation
- [ ] Extract and verify Bearer token from request headers
- [ ] Validate token signature with Azure AD public keys
- [ ] Extract user claims (aad_object_id, email, name)
- [ ] Load or create User entity from database
- [ ] Add token expiration checking
- [ ] Implement token refresh logic

**Reference:** See `PRIORITY_4_PLAN.md` Phase 1A for implementation details

**Risk Level:** 🔴 CRITICAL - System is completely open without this

---

### 2. Azure Service Integration (BLOCKER #2)
**Status:** ⛔ ALL STUBS - NO REAL FUNCTIONALITY

#### 2A. Azure Blob Storage
**Current State:**
- `blob_storage.py` contains stub implementation
- Upload/download operations are commented out
- No Managed Identity authentication configured

**Required Actions:**
- [ ] Implement `BlobStorageClient.upload_blob()` with Managed Identity
- [ ] Implement `BlobStorageClient.download_blob()` with retry logic
- [ ] Implement `BlobStorageClient.delete_blob()` with error handling
- [ ] Add dead letter queue for failed operations
- [ ] Configure private endpoint access only
- [ ] Test with real Azure Storage Account

#### 2B. Azure OpenAI
**Current State:**
- `llm/orchestrator.py` receives `client=None`
- No actual LLM calls being made
- Narrative/assumptions/exclusions are not generated

**Required Actions:**
- [ ] Initialize Azure OpenAI client with Managed Identity
- [ ] Implement token counting and truncation logic
- [ ] Implement retry logic for transient failures
- [ ] Add rate limiting to prevent quota exhaustion
- [ ] Test with actual GPT-4 model
- [ ] Validate output parsing and error handling

#### 2C. Azure AI Document Intelligence
**Current State:**
- `document_parser.py` does not call Azure DI API
- Validation results are hardcoded in `documents.py:158-164`
- No actual PDF/scanned document parsing

**Required Actions:**
- [ ] Implement `DocumentParser` with Azure DI client
- [ ] Implement async polling pattern (60s timeout, 2s interval)
- [ ] Add circuit breaker for service degradation
- [ ] Implement structured content extraction
- [ ] Test with real PDF, Word, and Excel documents
- [ ] Add error handling for unsupported formats

**Reference:** See `PRIORITY_4_PLAN.md` Phase 2 for document validation workflow

**Risk Level:** 🔴 CRITICAL - Core functionality non-operational

---

### 3. Document Validation Workflow (BLOCKER #3)
**Status:** ⛔ STUB - Returns hardcoded "passed" status

**Current State:**
```python
# documents.py:158-164
validation_result = {
    "status": "passed",
    "issues": [],
    "recommendations": ["Document appears complete for estimation"],
    ...
}
```

**Required Actions:**
- [ ] Integrate DocumentParser → Azure DI
- [ ] Integrate LLMOrchestrator → Azure OpenAI
- [ ] Implement completeness scoring algorithm
- [ ] Implement issue detection logic
- [ ] Add section extraction and validation
- [ ] Test with real project documents
- [ ] Add validation timeout handling

**Risk Level:** 🔴 CRITICAL - Users cannot validate documents

---

## ⚠️ HIGH PRIORITY (Pre-Production Requirements)

### 4. Soft Delete Pattern
**Status:** ⚠️ HARD DELETE - Data loss risk

**Current State:**
- Projects and documents use hard delete
- No recovery mechanism after deletion
- Cascading deletes may orphan audit logs

**Required Actions:**
- [ ] Add `deleted_at` column to Project, Document, Estimate tables
- [ ] Create Alembic migration for schema change
- [ ] Update repository delete methods to set deleted_at
- [ ] Add `is_deleted()` helper methods
- [ ] Filter deleted records from all queries
- [ ] Add admin endpoint to permanently purge old records
- [ ] Update audit logs to record soft deletes

**Reference:** Standard soft delete pattern - see Django/Rails implementations

**Risk Level:** 🟠 HIGH - Accidental data loss possible

---

### 5. Asynchronous Estimate Generation
**Status:** ⚠️ SYNCHRONOUS - 30s-5min blocking operations

**Current State:**
- `POST /estimates/generate` is synchronous
- User must wait for entire 14-step workflow
- No progress updates during processing
- Server timeout risk for complex projects

**Required Actions:**
- [ ] Implement background job pattern (Azure Functions or Service Bus)
- [ ] Add `EstimateStatus` enum (generating, completed, failed)
- [ ] Create status polling endpoint `GET /estimates/{id}/status`
- [ ] Add webhook notification support (optional)
- [ ] Implement job timeout handling (5 min max)
- [ ] Add progress percentage calculation
- [ ] Test with concurrent estimate requests

**Reference:** See Section 18.5 of specification for background job pattern

**Risk Level:** 🟠 HIGH - Poor UX, server timeout risk

---

### 6. Transaction Compensation
**Status:** ⚠️ NO COMPENSATION - Partial failure risk

**Current State:**
- Document upload: DB insert may succeed but blob upload fail (or vice versa)
- No rollback mechanism for cross-service transactions
- Orphaned database records or blob files possible

**Required Actions:**
- [ ] Implement two-phase commit saga pattern
- [ ] Upload to blob first, then commit DB record
- [ ] Add cleanup job for orphaned blobs
- [ ] Add DB cleanup for failed blob uploads
- [ ] Implement idempotency keys for retries
- [ ] Add transaction logging for debugging

**Reference:** See Gemini brainstorming plan "Two-Phase Commit Saga"

**Risk Level:** 🟠 HIGH - Data consistency issues

---

### 7. Export Functionality
**Status:** ⚠️ NOT IMPLEMENTED

**Current State:**
```python
# estimates.py:279-296
return JSONResponse(
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    content={"error": "CSV export not yet implemented"}
)
```

**Required Actions:**
- [ ] Implement CSV export with hierarchical line items
- [ ] Implement PDF export (pyppeteer or ReportLab)
- [ ] Add export templates
- [ ] Add export format validation
- [ ] Test with large estimates (>1000 line items)
- [ ] Add export caching for repeated requests

**Risk Level:** 🟡 MEDIUM - Functional gap, workaround available (JSON export works)

---

## 🔒 Security Requirements

### 8. Network Security
**Status:** ⚠️ REQUIRES INFRASTRUCTURE CONFIGURATION

**Required Actions:**
- [ ] Configure Azure VNet for Container Apps
- [ ] Enable private endpoints for all Azure services:
  - [ ] Azure SQL Database
  - [ ] Azure Blob Storage
  - [ ] Azure OpenAI
  - [ ] Azure AI Document Intelligence
- [ ] Disable public network access on all PaaS services
- [ ] Configure Network Security Groups (NSGs)
- [ ] Test connectivity via private endpoints only
- [ ] Add WAF (Web Application Firewall) for API Gateway

**Reference:** See specification Section 6 for zero-trust architecture

**Risk Level:** 🔴 CRITICAL - Security compliance requirement

---

### 9. Secrets Management
**Status:** ⚠️ ENVIRONMENT VARIABLES ONLY

**Required Actions:**
- [ ] Migrate all secrets to Azure Key Vault
- [ ] Configure Managed Identity access to Key Vault
- [ ] Remove secrets from .env files
- [ ] Add secret rotation policy
- [ ] Implement secret caching with TTL
- [ ] Add secret access audit logging

**Risk Level:** 🟠 HIGH - Security best practice

---

### 10. Rate Limiting & DoS Protection
**Status:** ⚠️ BASIC LIMITS ONLY

**Current Protections:**
- [x] File size limit (50 MB)
- [x] MIME type validation
- [x] Pagination page size limit (100 max)

**Missing Protections:**
- [ ] API rate limiting (requests/minute per user)
- [ ] Concurrent request limits
- [ ] IP-based throttling
- [ ] Request size limits for JSON payloads
- [ ] Timeout enforcement on all endpoints
- [ ] Circuit breaker for downstream services

**Risk Level:** 🟡 MEDIUM - Abuse vector exists

---

## 📊 Testing Requirements

### 11. Integration Testing
**Status:** ⚠️ INCOMPLETE

**Completed:**
- [x] Unit tests for risk analysis engine
- [x] Unit tests for AACE classifier
- [x] Repository layer tests
- [x] API endpoint smoke tests (mocked)

**Missing:**
- [ ] End-to-end tests with real Azure services
- [ ] Document upload → validation → estimate workflow test
- [ ] Multi-user concurrent access tests
- [ ] Role-based access control tests
- [ ] Error handling and rollback tests
- [ ] Performance tests under load

**Risk Level:** 🟠 HIGH - Unknown production behavior

---

### 12. Load Testing
**Status:** ⛔ NOT STARTED

**Required Actions:**
- [ ] Define performance baselines:
  - [ ] Document upload: <5s for 10MB file
  - [ ] Document validation: <2min for complex PDF
  - [ ] Estimate generation: <5min for 1000 line items
  - [ ] List endpoints: <500ms for 100 items
- [ ] Test concurrent users (10, 50, 100)
- [ ] Test database connection pool under load
- [ ] Test LLM rate limits and queue behavior
- [ ] Identify bottlenecks and optimize

**Risk Level:** 🟡 MEDIUM - Scalability unknown

---

## 🚀 DevOps & Deployment

### 13. Infrastructure as Code
**Status:** ⛔ NOT STARTED

**Required Actions:**
- [ ] Create Bicep/Terraform templates for:
  - [ ] Azure Container Apps environment
  - [ ] Azure SQL Database
  - [ ] Azure Storage Account
  - [ ] Azure OpenAI resource
  - [ ] Azure AI Document Intelligence
  - [ ] VNet and private endpoints
  - [ ] Application Insights
  - [ ] Log Analytics workspace
- [ ] Implement CI/CD pipeline (GitHub Actions or Azure DevOps)
- [ ] Add environment-specific configurations (dev, staging, prod)
- [ ] Add deployment rollback capability

**Risk Level:** 🟠 HIGH - Manual deployment error risk

---

### 14. Observability
**Status:** ⚠️ PARTIAL - App Insights configured but incomplete

**Completed:**
- [x] Application Insights connection string in config
- [x] Audit logging to database

**Missing:**
- [ ] Custom metrics for:
  - [ ] Estimate generation duration
  - [ ] Document parse success/failure rate
  - [ ] LLM token usage per request
  - [ ] API endpoint latency percentiles
- [ ] Distributed tracing for multi-service calls
- [ ] Alert rules for:
  - [ ] High error rate (>5% 5xx responses)
  - [ ] Slow response times (>5s P95)
  - [ ] Failed estimate generations
  - [ ] Azure service quota approaching limits
- [ ] Dashboard for real-time monitoring
- [ ] Log aggregation and retention policy

**Risk Level:** 🟡 MEDIUM - Operational blind spots

---

### 15. Database Migrations
**Status:** ⚠️ MANUAL EXECUTION REQUIRED

**Completed:**
- [x] Alembic framework configured
- [x] Initial migration created

**Missing:**
- [ ] Automated migration execution in deployment pipeline
- [ ] Migration rollback procedures
- [ ] Migration testing in staging environment
- [ ] Data migration scripts for soft delete transition
- [ ] Backup and restore procedures

**Risk Level:** 🟡 MEDIUM - Manual error risk

---

## 📋 Pre-Deployment Validation

### Phase 1: Development Environment
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Code coverage >80% for critical paths
- [ ] No security vulnerabilities in dependencies
- [ ] Linting and formatting checks pass

### Phase 2: Staging Environment
- [ ] Successful deployment to staging
- [ ] Azure AD authentication working
- [ ] All Azure services integrated and tested
- [ ] Document upload → validation → estimate workflow end-to-end test
- [ ] Performance benchmarks meet requirements
- [ ] Security scan passed (OWASP ZAP or similar)

### Phase 3: Production Readiness
- [ ] All CRITICAL blockers resolved
- [ ] All HIGH priority items resolved or documented exceptions
- [ ] Infrastructure as Code reviewed and approved
- [ ] Deployment runbook created and tested
- [ ] Rollback plan documented and tested
- [ ] Monitoring and alerting configured
- [ ] On-call rotation established
- [ ] User documentation complete
- [ ] Training materials prepared

---

## 📝 Sign-Off Required

### Technical Lead Approval
- [ ] Architecture review complete
- [ ] Security review complete
- [ ] Code review complete
- [ ] Performance validation complete

### Business Owner Approval
- [ ] Functional requirements met
- [ ] User acceptance testing complete
- [ ] Risk assessment reviewed
- [ ] Go-live plan approved

---

## 🔗 Reference Documents

- `APEX_Prompt.md` - Full technical specification
- `PRIORITY_4_PLAN.md` - API implementation plan
- `GEMINI_AZURE_INTEGRATION_PLAN.md` - Azure service integration roadmap
- `CODEX_SECURITY_FINDINGS.md` - Security review results

---

## 📊 Current Status Summary

**Overall Readiness:** 🔴 **NOT READY FOR PRODUCTION**

**Blockers Remaining:** 3 CRITICAL, 4 HIGH priority

**Estimated Work:** 28-40 days (per Azure integration plan)

**Next Steps:**
1. Begin Phase 1: Azure Service Integration (5-7 days)
2. Implement Phase 2: Document Validation Workflow (8-10 days)
3. Complete Phase 3: Production Hardening (10-15 days)
4. Execute Phase 4: Testing & Deployment (5-8 days)

**Target Production Date:** TBD after critical blockers resolved
