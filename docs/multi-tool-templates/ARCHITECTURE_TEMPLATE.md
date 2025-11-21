# [TOOL NAME] - Architecture Specification

> **INSTRUCTIONS FOR TOOL MAINTAINERS**:
> - Replace `[TOOL NAME]` with your tool's name (e.g., "APEX", "Substation Estimator")
> - Fill in all `[PLACEHOLDER]` sections with tool-specific details
> - Keep all sections marked `[SHARED PATTERN - DO NOT MODIFY]` identical to this template
> - Sections marked `[TOOL-SPECIFIC]` should be customized for your domain
> - Delete these instructions and the example text when complete

---

## Document Purpose

This document describes the software architecture for **[TOOL NAME]**, an AI-enabled cost estimating tool for **[DOMAIN: e.g., transmission/distribution, substation, renewable interconnection]** projects. This tool follows the multi-tool estimation platform pattern with 85% shared architecture and 15% domain-specific customization.

**Target Audience**: Enterprise architects, platform owners, security teams, development teams

**Related Documents**:
- **PATTERN_OVERVIEW.md**: Unified vision and common baseline across all six tools
- **TECHNICAL_SPECIFICATION.md**: Detailed implementation requirements for this specific tool
- **DEPLOYMENT_OPERATIONS_GUIDE.md**: Production deployment and operational procedures

---

## 1. System Context

### 1.1 Business Purpose

**[TOOL-SPECIFIC - Replace with your tool's purpose]**

Example (APEX):
> APEX (AI-Powered Estimation Expert) automates cost estimation for utility transmission and distribution projects. The system processes engineering drawings, specifications, and historical bid data to generate AACE-compliant estimates with statistical confidence intervals (P50/P80/P95) through Monte Carlo risk analysis.

**Primary Users**: [Number] internal estimators + [Number] managers/auditors
**Regulatory Context**: ISO-NE compliance required for all estimates (7-year audit retention)
**Key Workflows**:
- [Workflow 1: e.g., Document upload and validation]
- [Workflow 2: e.g., Estimate generation with risk analysis]
- [Workflow 3: e.g., Manager review and approval]

### 1.2 System Context Diagram

```
[SHARED PATTERN - Customize component labels only]

┌─────────────────────────────────────────────────────────────────────────┐
│                          External Actors                                 │
└─────────────────────────────────────────────────────────────────────────┘
    │                          │                        │
    │ [User Role 1]            │ [User Role 2]         │ [User Role 3]
    │ (e.g., Estimators)       │ (e.g., Managers)      │ (e.g., Auditors)
    │                          │                        │
    ↓                          ↓                        ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      Azure Front Door (WAF)                              │
│  • DDoS protection                                                       │
│  • TLS termination                                                       │
│  • [SHARED PATTERN - DO NOT MODIFY]                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                   [TOOL NAME] API (Container Apps)                       │
│  • FastAPI REST API                                                      │
│  • Azure AD JWT authentication                                           │
│  • VNet-injected, no public internet access                              │
│  • [SHARED PATTERN with tool-specific endpoints]                        │
└─────────────────────────────────────────────────────────────────────────┘
         │              │               │                │
         ↓              ↓               ↓                ↓
    ┌────────┐    ┌──────────┐   ┌──────────┐    ┌──────────────┐
    │ Azure  │    │  Azure   │   │  Azure   │    │    Azure     │
    │  SQL   │    │ OpenAI   │   │   Blob   │    │  Document    │
    │Database│    │  (GPT-4) │   │ Storage  │    │ Intelligence │
    │        │    │          │   │          │    │              │
    │Private │    │ Private  │   │ Private  │    │   Private    │
    │Endpoint│    │ Endpoint │   │ Endpoint │    │   Endpoint   │
    └────────┘    └──────────┘   └──────────┘    └──────────────┘
                       ↓
                 ┌──────────┐
                 │  Azure   │
                 │   Key    │
                 │  Vault   │
                 │ Private  │
                 │ Endpoint │
                 └──────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      External Integrations                               │
│  • [TOOL-SPECIFIC: List integrations]                                   │
│    - Cost Database (REST API via Private Endpoint)                      │
│    - ERP System (future, via estimating-connectors library)             │
│    - Document Repository (Azure Blob Storage)                           │
└─────────────────────────────────────────────────────────────────────────┘
```

**Trust Boundaries**:
- 🔴 **Internet → Azure Front Door**: Public internet, WAF-protected
- 🟡 **Azure Front Door → Container Apps**: Internal Azure network, TLS-encrypted
- 🟢 **Container Apps → Azure Services**: Private Endpoints only, Managed Identity auth
- ⚫ **Container Apps → External Integrations**: [TOOL-SPECIFIC: Define trust level]

### 1.3 AI Pipeline Overview

```
[SHARED PATTERN - Customize operation names only]

User Request (REST API)
         │
         ↓
┌──────────────────────────────────────────┐
│     Document Upload & Storage            │
│  • Azure Blob Storage                    │
│  • Virus scanning (future)               │
│  • Metadata extraction                   │
└──────────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│   Document Parsing (Azure DI)            │
│  • OCR + layout analysis                 │
│  • Table extraction                      │
│  • Async polling pattern                 │
│  • [SHARED PATTERN - DO NOT MODIFY]     │
└──────────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│  AI Validation (Azure OpenAI GPT-4)      │
│  • Prompt: [TOOL-SPECIFIC validation]    │
│  • Via estimating-ai-core orchestrator   │
│  • Temperature: [0.1-0.7 based on AACE]  │
│  • Content filtering enabled             │
└──────────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│  [TOOL-SPECIFIC AI Operations]           │
│  • [Operation 1: e.g., Quantity extract] │
│  • [Operation 2: e.g., Cost computation] │
│  • [Operation 3: e.g., Risk analysis]    │
│  • Via LLMOrchestrator (shared library)  │
└──────────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│  Narrative Generation (GPT-4)            │
│  • Assumptions, exclusions, risks        │
│  • Maturity-aware tone/detail level      │
│  • [SHARED PATTERN - DO NOT MODIFY]     │
└──────────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│   Result Persistence & Audit Logging     │
│  • Azure SQL Database                    │
│  • AuditLog table (7-year retention)     │
│  • [SHARED PATTERN - DO NOT MODIFY]     │
└──────────────────────────────────────────┘
         │
         ↓
    API Response (JSON)
```

**AI Safety Controls** [SHARED PATTERN - DO NOT MODIFY]:
- Content filtering: Hate/Violence/Self-Harm detection enabled
- Prompt injection detection: Via `estimating-security` library
- PII scrubbing: Remove SSNs, phone numbers, addresses before LLM calls
- Token limits: 128K context window, 4K response buffer
- Audit logging: All LLM calls logged (model, tokens, operation) - NO prompt content

---

## 2. Logical Architecture

### 2.1 Layered Architecture

```
[SHARED PATTERN - 85% identical across all tools]

┌──────────────────────────────────────────────────────────────────────────┐
│                          API Layer (FastAPI)                             │
│ ────────────────────────────────────────────────────────────────────── │
│  src/{tool_name}/api/v1/                                                 │
│    • health.py           - Liveness/readiness probes                     │
│    • projects.py         - Project CRUD operations                       │
│    • documents.py        - Document upload, parsing, validation          │
│    • [TOOL-SPECIFIC].py  - Domain-specific endpoints                     │
│    • users.py            - User management (admin only)                  │
│                                                                           │
│  Middleware:                                                              │
│    • RequestIDMiddleware - X-Request-ID header injection                 │
│    • JWTAuthMiddleware   - Azure AD token validation                     │
│    • CORSMiddleware      - [If web UI exists]                            │
│                                                                           │
│  Exception Handlers:                                                      │
│    • BusinessRuleViolation → 400 with ErrorResponse schema               │
│    • Forbidden → 403 with detail message                                 │
│    • Exception → 500 with generic error (no stack trace leak)            │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                          Service Layer                                   │
│ ────────────────────────────────────────────────────────────────────── │
│  src/{tool_name}/services/                                               │
│    • llm/orchestrator.py     - Via estimating-ai-core library            │
│    • document_parser.py      - Azure Document Intelligence wrapper       │
│    • [TOOL-SPECIFIC services] - Domain business logic                    │
│                                                                           │
│  Example (APEX):                                                          │
│    • aace_classifier.py      - AACE Class 1-5 determination              │
│    • cost_database.py        - CBS/WBS hierarchy builder                 │
│    • risk_analysis.py        - Monte Carlo engine                        │
│    • estimate_generator.py   - Main orchestration service                │
│                                                                           │
│  [TOOL-SPECIFIC: List your domain services here]                         │
│    • [service_1].py          - [Purpose]                                 │
│    • [service_2].py          - [Purpose]                                 │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                        Repository Layer                                  │
│ ────────────────────────────────────────────────────────────────────── │
│  src/{tool_name}/database/repositories/                                  │
│    • project_repository.py   - Project CRUD + ProjectAccess checks       │
│    • document_repository.py  - Document CRUD + blob path management      │
│    • [TOOL-SPECIFIC].py      - Domain entity repositories                │
│    • audit_repository.py     - AuditLog creation                         │
│                                                                           │
│  Pattern (all repositories):                                             │
│    class XRepository:                                                     │
│        def __init__(self, db: Session):  # Injected, never create own    │
│            self.db = db                                                   │
│                                                                           │
│        def create(self, entity: X) -> X:                                 │
│            # Insert with audit logging                                    │
│                                                                           │
│        def get_with_access_check(self, id: UUID, user_id: UUID) -> X:    │
│            # Verify ProjectAccess before returning                        │
└──────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                          Data Layer                                      │
│ ────────────────────────────────────────────────────────────────────── │
│  src/{tool_name}/models/database.py - SQLAlchemy ORM models             │
│  alembic/versions/*.py               - Database migrations               │
│                                                                           │
│  Common Tables (all tools):                                              │
│    • User                - Azure AD synchronized user profiles           │
│    • AppRole             - Application roles (Estimator, Manager, etc.)  │
│    • ProjectAccess       - Per-project RBAC junction table               │
│    • Project             - Top-level project entity                      │
│    • Document            - Uploaded documents with blob storage paths    │
│    • AuditLog            - All operations logged for 7-year retention    │
│                                                                           │
│  [TOOL-SPECIFIC Tables: List your domain entities]                       │
│    • [Entity1]           - [Purpose, example: EstimateLineItem]          │
│    • [Entity2]           - [Purpose, example: RiskFactor]                │
│    • [Entity3]           - [Purpose]                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Cross-Cutting Concerns

```
[SHARED PATTERN - 100% identical across all tools]

┌──────────────────────────────────────────────────────────────────────────┐
│                    src/{tool_name}/azure/                                │
│  • blob_storage.py       - BlobServiceClient wrapper with Managed ID     │
│  • key_vault.py          - SecretClient wrapper for config loading       │
│  • managed_identity.py   - DefaultAzureCredential helper                 │
│  • document_intelligence.py - DocumentIntelligenceClient async wrapper   │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                    src/{tool_name}/utils/                                │
│  • logging.py            - Structured logging to Application Insights    │
│  • errors.py             - Custom exception classes                      │
│  • retry.py              - @azure_retry decorator (exp backoff 2-10s)    │
│  • middleware.py         - RequestIDMiddleware, JWTAuthMiddleware        │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                    src/{tool_name}/config.py                             │
│  • Pydantic Settings with environment variable loading                   │
│  • Secrets loaded from Azure Key Vault at startup                        │
│  • [SHARED PATTERN - DO NOT MODIFY structure]                           │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                    src/{tool_name}/dependencies.py                       │
│  • get_db() - Database session with auto-commit/rollback                 │
│  • get_current_user() - Azure AD JWT validation                          │
│  • [SHARED PATTERN - DO NOT MODIFY session management]                  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Shared Library Integration Points

#### `estimating-ai-core` Library
**Version**: [Specify version, e.g., v1.0.0]
**Installation**: `pip install estimating-ai-core==1.0.0`

**Usage Pattern**:
```python
from estimating_ai_core import LLMOrchestrator, PromptTemplate, TokenManager

# Initialize in dependency injection
orchestrator = LLMOrchestrator(
    azure_openai_endpoint=config.AZURE_OPENAI_ENDPOINT,
    deployment_name=config.AZURE_OPENAI_DEPLOYMENT,
    credential=DefaultAzureCredential()
)

# Use maturity-aware routing
response = await orchestrator.generate(
    prompt=PromptTemplate.format("quantity_extraction", variables={...}),
    aace_class=AACEClass.CLASS_3,  # Auto-selects temperature + system prompt
    max_tokens=4000
)
```

**[TOOL-SPECIFIC: List which shared prompts you use]**
- `document_validation` - Checks completeness and consistency
- `[custom_prompt_1]` - [Purpose]
- `[custom_prompt_2]` - [Purpose]

#### `estimating-connectors` Library
**Version**: [Specify version, e.g., v0.5.0]
**Installation**: `pip install estimating-connectors==0.5.0`

**Usage Pattern**:
```python
from estimating_connectors import CostDatabaseClient, AuditExporter

# Initialize cost database client
cost_client = CostDatabaseClient(
    base_url=config.COST_DATABASE_URL,
    credential=DefaultAzureCredential()
)

# Lookup cost codes
cost_data = await cost_client.get_cost_by_code(
    cost_code="[TOOL-SPECIFIC code format]",
    region="Northeast",
    year=2025
)
```

**[TOOL-SPECIFIC: List which connectors you use]**
- `CostDatabaseClient` - For [specific cost lookup needs]
- `AuditExporter` - For ISO-NE compliance exports
- `[future connector]` - [When ERP integration is needed]

#### `estimating-security` Library
**Version**: [Specify version, e.g., v1.0.0]
**Installation**: `pip install estimating-security==1.0.0`

**Usage Pattern** [SHARED PATTERN - DO NOT MODIFY]:
```python
from estimating_security import AzureADAuthenticator, ProjectAccessChecker, AuditLogger

# JWT validation (used in dependencies.py)
authenticator = AzureADAuthenticator(tenant_id=config.AZURE_TENANT_ID)
user = await authenticator.validate_token(token)

# RBAC check (used in all repositories)
access_checker = ProjectAccessChecker(db)
access_checker.require_permission(user_id, project_id, "estimate:create")

# Audit logging (used in all services)
audit_logger = AuditLogger(db)
await audit_logger.log(
    user_id=user_id,
    action="[TOOL-SPECIFIC action verb]",
    resource_type="Project",
    resource_id=project_id,
    details={"key": "value"}  # JSON blob, avoid PII
)
```

### 2.4 Customization Points (15% Variable)

**[TOOL-SPECIFIC: Document where your tool diverges from shared pattern]**

#### Domain-Specific Services
```
[List your custom services and their purpose]

Example (APEX):
- aace_classifier.py: Determines AACE Class 1-5 based on document completeness
- cost_database.py: Builds CBS/WBS hierarchy from parsed quantities
- risk_analysis.py: Monte Carlo simulation with Latin Hypercube Sampling

[Your tool]:
- [service_1].py: [Purpose]
- [service_2].py: [Purpose]
```

#### Custom Data Models
```
[List your domain entities beyond common Project/Document/User]

Example (APEX):
- Estimate: Top-level cost estimate with P50/P80/P95
- EstimateLineItem: WBS hierarchy with parent/child relationships
- RiskFactor: Distributions for Monte Carlo (triangular, normal, etc.)
- CostCode: Utility cost code definitions

[Your tool]:
- [Entity1]: [Purpose, relationships]
- [Entity2]: [Purpose, relationships]
```

#### Custom Prompts
```
[List your tool-specific LLM prompts]

Example (APEX):
- quantity_extraction: Extract structure counts, conductor lengths from drawings
- risk_narrative: Generate risk assumptions and exclusions text

[Your tool]:
- [prompt_1]: [Purpose, expected output]
- [prompt_2]: [Purpose, expected output]
```

---

## 3. Technology Stack

### 3.1 Core Technologies [SHARED PATTERN - 100% Identical]

| Layer | Technology | Version | Rationale |
|-------|------------|---------|-----------|
| **Language** | Python | 3.11+ | Type hints, async/await, mature ecosystem |
| **API Framework** | FastAPI | 0.104.0+ | OpenAPI docs, async support, Pydantic integration |
| **Database** | Azure SQL Database | Business Critical | ACID, 7-year retention, zone-redundant HA |
| **ORM** | SQLAlchemy | 2.0+ | Modern async patterns, platform-independent GUID |
| **Migrations** | Alembic | Latest | Declarative schema versioning |
| **Validation** | Pydantic | 2.x | Type-safe DTOs, auto OpenAPI schema generation |
| **Testing** | pytest | Latest | Fixtures, parametrize, coverage integration |
| **Code Quality** | black, isort, flake8 | Latest | PEP 8 enforcement, consistent formatting |
| **Security Scan** | bandit | Latest | Static analysis for common vulnerabilities |

### 3.2 Azure Services [SHARED PATTERN - 100% Identical]

| Service | SKU | Purpose | Private Endpoint |
|---------|-----|---------|------------------|
| **Container Apps** | Consumption plan | Serverless API hosting, auto-scale 0-10 | N/A (VNet-injected) |
| **SQL Database** | Business Critical (8 vCores) | Relational data with 7-year retention | ✅ Required |
| **Blob Storage** | Standard ZRS | Document storage with lifecycle mgmt | ✅ Required |
| **Azure OpenAI** | Standard (GPT-4) | LLM inference for AI operations | ✅ Required |
| **Document Intelligence** | Standard | OCR + table extraction from PDFs | ✅ Required |
| **Key Vault** | Standard | Secrets management with rotation | ✅ Required |
| **Application Insights** | Standard | Observability, LLM token tracking | No (data sent via instrumentation key) |
| **Virtual Network** | Standard | Private networking, NSG rules | N/A (infrastructure) |
| **Front Door** | Standard | WAF, DDoS protection, TLS termination | No (edge service) |

**Cost Estimate** [Update with your tool's projected costs]:
- Development: ~$200/month
- Staging: ~$800/month
- Production: ~$2500/month (Business Critical SQL + zone-redundant storage)

### 3.3 Technology Trade-offs

#### Why FastAPI over Flask/Django?
- ✅ **Async-native**: Essential for LLM calls, document parsing (long-running operations)
- ✅ **Auto OpenAPI docs**: Swagger UI + ReDoc generated automatically
- ✅ **Pydantic integration**: Type-safe request/response validation
- ✅ **Performance**: 3-5x faster than Flask for I/O-bound workloads
- ❌ **Learning curve**: Requires understanding async/await patterns

#### Why Azure SQL over PostgreSQL/Cosmos DB?
- ✅ **ACID compliance**: Critical for financial data (cost estimates)
- ✅ **Mature ecosystem**: Enterprise backup, point-in-time restore
- ✅ **Query performance**: Complex joins for WBS hierarchies, audit queries
- ✅ **Business Critical tier**: Zone-redundant HA, 99.995% SLA
- ❌ **Cost**: More expensive than Cosmos DB serverless for low-volume scenarios

#### Why Azure OpenAI over OpenAI Platform?
- ✅ **Private Endpoint support**: Zero public internet exposure
- ✅ **Enterprise SLA**: 99.9% uptime guarantee
- ✅ **Data residency**: Prompts/completions stay in Azure region
- ✅ **Content filtering**: Mandatory safety guardrails enabled
- ❌ **Model lag**: New models arrive 3-6 months after OpenAI Platform

#### Why Shared Libraries over Monorepo?
- ✅ **Independent versioning**: Tools can upgrade at different cadences
- ✅ **Security patching**: Critical fixes deployed without full tool rebuild
- ✅ **Team autonomy**: Tool teams own their release cycles
- ❌ **Coordination overhead**: Breaking changes require multi-repo synchronization

---

## 4. Security Architecture

### 4.1 Network Security [SHARED PATTERN - DO NOT MODIFY]

```
Internet
   │
   ↓ (HTTPS only, TLS 1.2+)
┌──────────────────────┐
│ Azure Front Door     │
│ • WAF (OWASP Top 10) │
│ • DDoS protection    │
│ • Rate limiting      │
└──────────────────────┘
   │
   ↓ (Internal Azure network)
┌──────────────────────────────────────────┐
│         Virtual Network (10.0.0.0/16)    │
│  ┌────────────────────────────────────┐  │
│  │ Container Apps Subnet             │  │
│  │ • [TOOL NAME] API instances       │  │
│  │ • No public IP assignment         │  │
│  │ • NSG: Allow HTTPS from Front Door│  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ Private Endpoint Subnet           │  │
│  │ • SQL Database (10.0.1.4)         │  │
│  │ • Blob Storage (10.0.1.5)         │  │
│  │ • Azure OpenAI (10.0.1.6)         │  │
│  │ • Document Intelligence (10.0.1.7)│  │
│  │ • Key Vault (10.0.1.8)            │  │
│  └────────────────────────────────────┘  │
│                                          │
│  Private DNS Zones:                      │
│  • privatelink.database.windows.net      │
│  • privatelink.blob.core.windows.net     │
│  • privatelink.openai.azure.com          │
│  • privatelink.vaultcore.azure.net       │
└──────────────────────────────────────────┘
```

**Security Controls**:
- All Azure services accessible ONLY via Private Endpoints (no public internet)
- Network Security Groups (NSGs) enforce least-privilege access
- Azure Front Door WAF blocks SQL injection, XSS, and OWASP Top 10 attacks
- TLS 1.2+ enforced for all connections (TLS 1.0/1.1 disabled)

### 4.2 Identity and Access Management [SHARED PATTERN - DO NOT MODIFY]

#### Authentication Flow
```
1. User → Azure AD login → JWT access token (aud: api://[app-id])
2. User → API request with Bearer token in Authorization header
3. API → JWTAuthMiddleware validates token signature, expiry, audience
4. API → Extract user_id from token claims (oid or sub)
5. API → Load User from database (synchronized from Azure AD)
6. API → Proceed to authorization check
```

#### Authorization Flow
```
1. API endpoint requires permission (e.g., "estimate:create")
2. Repository → Query ProjectAccess table:
   SELECT pa.* FROM ProjectAccess pa
   JOIN AppRole ar ON pa.role_id = ar.role_id
   WHERE pa.user_id = :user_id AND pa.project_id = :project_id
3. Repository → Parse ar.permissions JSON array
4. Repository → Check if required permission in array
5. If FOUND → Proceed with operation
   If NOT FOUND → Raise Forbidden exception (HTTP 403)
```

#### Role Definitions [TOOL-SPECIFIC: Customize role names/permissions]

Example (APEX):
| Role | Permissions | Typical Users |
|------|-------------|---------------|
| **Estimator** | `project:read`, `project:create`, `document:upload`, `estimate:create` | All estimators |
| **Manager** | All Estimator + `estimate:approve`, `project:archive` | Cost estimation managers |
| **Auditor** | `project:read`, `estimate:read`, `audit:export` | Compliance team |
| **Admin** | All permissions | IT administrators |

[Your tool - update this table]:
| Role | Permissions | Typical Users |
|------|-------------|---------------|
| **[Role 1]** | `[perm1]`, `[perm2]` | [User type] |
| **[Role 2]** | `[perm1]`, `[perm2]` | [User type] |

### 4.3 Data Protection [SHARED PATTERN - DO NOT MODIFY]

| Data Type | At Rest | In Transit | Retention | PII Handling |
|-----------|---------|------------|-----------|--------------|
| **SQL Database** | TDE (AES-256) | TLS 1.2+ | 7 years (ISO-NE) | Email only, no SSN/phone |
| **Blob Storage** | Microsoft-managed key | HTTPS only | 90 days → Archive tier | None (engineering docs) |
| **Key Vault Secrets** | HSM-backed | HTTPS only | 90-day rotation | API keys, connection strings |
| **LLM Prompts** | NOT persisted | HTTPS to Private Endpoint | 90 days (Azure OpenAI logs) | PII scrubbed before LLM call |
| **Application Insights** | Microsoft-managed | HTTPS only | 90 days | No PII, token counts only |

**PII Scrubbing Pattern** [SHARED PATTERN - DO NOT MODIFY]:
```python
from estimating_security import PIIScrubber

scrubber = PIIScrubber()

# Before sending to LLM
sanitized_text = scrubber.remove_pii(
    text=document_content,
    patterns=["SSN", "PHONE", "EMAIL", "ADDRESS"]
)

# LLM call with sanitized input
response = await orchestrator.generate(prompt=sanitized_text, ...)
```

### 4.4 Audit Logging [SHARED PATTERN - DO NOT MODIFY]

All operations logged to `AuditLog` table with 7-year retention (ISO-NE compliance):

```sql
CREATE TABLE AuditLog (
    audit_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL REFERENCES [User](user_id),
    action NVARCHAR(100) NOT NULL,           -- [TOOL-SPECIFIC action verbs]
    resource_type NVARCHAR(50) NOT NULL,     -- Project, Document, Estimate, etc.
    resource_id UNIQUEIDENTIFIER,            -- FK to resource
    timestamp DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    details NVARCHAR(MAX),                   -- JSON blob, avoid PII
    request_id NVARCHAR(50),                 -- X-Request-ID for correlation
    ip_address NVARCHAR(45)                  -- IPv4/IPv6 address
);

CREATE INDEX IX_AuditLog_UserId_Timestamp ON AuditLog(user_id, timestamp);
CREATE INDEX IX_AuditLog_ResourceType_ResourceId ON AuditLog(resource_type, resource_id);
```

**[TOOL-SPECIFIC: Define your action verbs]**

Example (APEX):
- `project.created`, `project.updated`, `project.archived`
- `document.uploaded`, `document.validated`, `document.parsed`
- `estimate.generated`, `estimate.approved`, `estimate.exported`

[Your tool]:
- `[resource].[action]` - [Description]
- `[resource].[action]` - [Description]

---

## 5. Data Architecture

### 5.1 Common Schema (All Tools)

```sql
-- [SHARED PATTERN - DO NOT MODIFY these tables]

-- User management
CREATE TABLE [User] (
    user_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    email NVARCHAR(255) NOT NULL UNIQUE,
    display_name NVARCHAR(255),
    is_active BIT DEFAULT 1,
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE()
);

-- Application roles
CREATE TABLE AppRole (
    role_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    role_name NVARCHAR(50) NOT NULL UNIQUE,
    permissions NVARCHAR(MAX) NOT NULL,  -- JSON array of permission strings
    created_at DATETIME2 DEFAULT GETUTCDATE()
);

-- Per-project access control
CREATE TABLE ProjectAccess (
    access_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL REFERENCES [User](user_id) ON DELETE CASCADE,
    project_id UNIQUEIDENTIFIER NOT NULL REFERENCES Project(project_id) ON DELETE CASCADE,
    role_id UNIQUEIDENTIFIER NOT NULL REFERENCES AppRole(role_id),
    granted_at DATETIME2 DEFAULT GETUTCDATE(),
    granted_by UNIQUEIDENTIFIER REFERENCES [User](user_id),
    CONSTRAINT UQ_ProjectAccess_UserProject UNIQUE (user_id, project_id)
);

-- Top-level project
CREATE TABLE Project (
    project_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    project_name NVARCHAR(255) NOT NULL,
    project_description NVARCHAR(MAX),
    status NVARCHAR(50) NOT NULL DEFAULT 'DRAFT',  -- [TOOL-SPECIFIC enum values]
    created_by UNIQUEIDENTIFIER NOT NULL REFERENCES [User](user_id),
    created_at DATETIME2 DEFAULT GETUTCDATE(),
    updated_at DATETIME2 DEFAULT GETUTCDATE()
);

-- Uploaded documents
CREATE TABLE Document (
    document_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    project_id UNIQUEIDENTIFIER NOT NULL REFERENCES Project(project_id) ON DELETE CASCADE,
    document_name NVARCHAR(255) NOT NULL,
    document_type NVARCHAR(50) NOT NULL,  -- [TOOL-SPECIFIC: PDF, EXCEL, WORD, etc.]
    blob_path NVARCHAR(1024) NOT NULL,    -- Azure Blob Storage URI
    file_size_bytes BIGINT NOT NULL,
    validation_status NVARCHAR(50) DEFAULT 'PENDING',  -- PENDING, VALID, INVALID
    validation_result NVARCHAR(MAX),      -- JSON blob with validation details
    uploaded_by UNIQUEIDENTIFIER NOT NULL REFERENCES [User](user_id),
    uploaded_at DATETIME2 DEFAULT GETUTCDATE()
);

-- Audit trail (7-year retention for ISO-NE compliance)
CREATE TABLE AuditLog (
    audit_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    user_id UNIQUEIDENTIFIER NOT NULL REFERENCES [User](user_id),
    action NVARCHAR(100) NOT NULL,
    resource_type NVARCHAR(50) NOT NULL,
    resource_id UNIQUEIDENTIFIER,
    timestamp DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    details NVARCHAR(MAX),                -- JSON blob
    request_id NVARCHAR(50),
    ip_address NVARCHAR(45)
);
```

### 5.2 Tool-Specific Schema

**[TOOL-SPECIFIC: Define your domain entities]**

Example (APEX):
```sql
-- Cost estimates
CREATE TABLE Estimate (
    estimate_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    project_id UNIQUEIDENTIFIER NOT NULL REFERENCES Project(project_id),
    aace_class NVARCHAR(10) NOT NULL,     -- CLASS_1 to CLASS_5
    base_cost_usd DECIMAL(18, 2) NOT NULL,
    p50_cost_usd DECIMAL(18, 2),          -- Monte Carlo median
    p80_cost_usd DECIMAL(18, 2),          -- 80th percentile
    p95_cost_usd DECIMAL(18, 2),          -- 95th percentile
    assumptions_narrative NVARCHAR(MAX),  -- LLM-generated
    created_at DATETIME2 DEFAULT GETUTCDATE()
);

-- WBS line items
CREATE TABLE EstimateLineItem (
    line_item_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    estimate_id UNIQUEIDENTIFIER NOT NULL REFERENCES Estimate(estimate_id),
    parent_line_item_id UNIQUEIDENTIFIER REFERENCES EstimateLineItem(line_item_id),
    wbs_code NVARCHAR(20) NOT NULL,       -- e.g., "10-100-050"
    description NVARCHAR(500),
    quantity DECIMAL(18, 4),
    unit NVARCHAR(20),
    unit_cost_usd DECIMAL(18, 2),
    total_cost_usd DECIMAL(18, 2)
);
```

[Your tool - create similar DDL]:
```sql
-- [Table 1]
CREATE TABLE [Entity1] (
    [primary_key] UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    -- [Define columns with types, constraints, foreign keys]
);

-- [Table 2]
CREATE TABLE [Entity2] (
    [primary_key] UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    -- [Define columns]
);
```

### 5.3 GUID Handling Pattern [SHARED PATTERN - DO NOT MODIFY]

**Problem**: Azure SQL uses `UNIQUEIDENTIFIER`, PostgreSQL uses `UUID`, SQLite uses `CHAR(36)`

**Solution**: Custom `GUID` TypeDecorator in `models/database.py`

```python
from sqlalchemy import TypeDecorator, CHAR
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.dialects.postgresql import UUID
import uuid

class GUID(TypeDecorator):
    """Platform-independent GUID type."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mssql":
            return dialect.type_descriptor(UNIQUEIDENTIFIER)
        elif dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "mssql" or dialect.name == "postgresql":
            return value
        else:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value

# Usage in all models
from sqlalchemy.orm import mapped_column

class Project(Base):
    __tablename__ = "project"
    project_id = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
```

---

## 6. Operational Design

### 6.1 Deployment Architecture [SHARED PATTERN - DO NOT MODIFY]

**Environment Strategy**:
| Environment | Branch | Deployment Trigger | Approvals | Database |
|-------------|--------|-------------------|-----------|----------|
| **Development** | `develop` | Push to develop | None | Shared test DB |
| **Staging** | `main` (pre-prod tag) | Manual via GitHub Actions | Tech Lead | Staging DB (prod-like) |
| **Production** | `main` (release tag) | Manual via GitHub Actions | Product Owner + IT | Production DB (HA) |

**Infrastructure as Code** (Bicep templates in `infra/` directory):
```
infra/
├── main.bicep                  # Orchestrates all modules
├── modules/
│   ├── container-app.bicep     # Container Apps with VNet injection
│   ├── sql-database.bicep      # Azure SQL with Private Endpoint
│   ├── blob-storage.bicep      # Blob Storage with lifecycle policies
│   ├── openai.bicep            # Azure OpenAI with Private Endpoint
│   ├── key-vault.bicep         # Key Vault with access policies
│   └── vnet.bicep              # VNet + Private DNS zones
└── parameters/
    ├── dev.bicepparam          # Development parameters
    ├── staging.bicepparam      # Staging parameters
    └── production.bicepparam   # Production parameters
```

**Deployment Process** (30-step checklist in `DEPLOYMENT_OPERATIONS_GUIDE.md`):
1. Pre-deployment validation (lint, test, security scan)
2. Infrastructure deployment (Bicep)
3. Database migration (Alembic)
4. Container image build and push to ACR
5. Container App update with new image
6. Smoke tests (health endpoints, auth flow)
7. Post-deployment validation

### 6.2 Observability [SHARED PATTERN - DO NOT MODIFY]

#### Azure Application Insights Dashboards

**API Performance Dashboard**:
- P50/P95/P99 response times by endpoint
- Request volume by hour
- Error rate by endpoint and exception type
- Dependency call duration (SQL, Blob, OpenAI)

**LLM Usage Dashboard**:
- Token consumption by operation type (cost allocation)
- LLM call duration and success rate
- Prompt token count distribution
- Cost per estimate calculation

**Custom Metrics** [TOOL-SPECIFIC: Define domain metrics]:

Example (APEX):
```python
from opencensus.stats import measure, view

# Define custom metrics
estimate_generation_duration = measure.MeasureFloat(
    "estimate_generation_duration_ms",
    "Time to generate complete estimate",
    "ms"
)

monte_carlo_iterations = measure.MeasureInt(
    "monte_carlo_iterations",
    "Number of Monte Carlo iterations performed",
    "iterations"
)
```

[Your tool - define custom metrics]:
- `[metric_1]` - [Description, unit]
- `[metric_2]` - [Description, unit]

#### Alerting Rules [SHARED PATTERN with tool-specific thresholds]

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| API Error Rate | >1% for 5 minutes | High | Page on-call engineer |
| API P95 Latency | >2 seconds for 10 minutes | Medium | Slack notification |
| LLM Token Cost | >$500/day | Medium | Email budget owner |
| Database CPU | >80% for 10 minutes | High | Auto-scale + notify |
| Failed Auth Rate | >5% for 5 minutes | Critical | Security team escalation |

**[TOOL-SPECIFIC: Add domain-specific alerts]**

Example (APEX):
- Monte Carlo timeout (>60 seconds) → Investigate complexity
- Document parsing failure rate >10% → Check Azure DI service health

[Your tool]:
- `[Alert condition]` → `[Action]`

### 6.3 Disaster Recovery [SHARED PATTERN - DO NOT MODIFY]

**Recovery Objectives**:
- **RTO** (Recovery Time Objective): 4 hours
- **RPO** (Recovery Point Objective): 1 hour

**Backup Strategy**:
| Resource | Backup Frequency | Retention | Recovery Method |
|----------|------------------|-----------|-----------------|
| **Azure SQL** | Automated (hourly) | 35 days point-in-time | Azure Portal restore |
| **Blob Storage** | Geo-redundant (ZRS) | Lifecycle policy (90d→Archive) | Azure Portal copy |
| **Key Vault** | Automated | 90 days soft-delete | Azure CLI recovery |
| **Infrastructure** | Git-tracked Bicep | Indefinite | Redeploy from `main` |

**Runbook**: See `DEPLOYMENT_OPERATIONS_GUIDE.md` Section 6: Disaster Recovery Procedures

---

## 7. Non-Functional Requirements

### 7.1 Performance [TOOL-SPECIFIC: Define your SLAs]

Example (APEX):
| Operation | Target | Measurement |
|-----------|--------|-------------|
| **Document upload** | <5 seconds for 10MB PDF | P95 response time |
| **Document parsing** | <30 seconds for 50-page PDF | Async job completion |
| **Estimate generation** | <60 seconds for typical project | End-to-end API call |
| **Monte Carlo (10K iterations)** | <15 seconds | Service layer timing |
| **API health check** | <100ms | Liveness probe |

[Your tool - define performance targets]:
| Operation | Target | Measurement |
|-----------|--------|-------------|
| **[Operation 1]** | [Target time] | [Metric] |
| **[Operation 2]** | [Target time] | [Metric] |

### 7.2 Scalability [SHARED PATTERN with tool-specific thresholds]

**Scaling Strategy**:
- **Horizontal Scaling**: Container Apps auto-scale 0-10 replicas based on CPU/memory
- **Database Scaling**: Manual vertical scaling (8→16 vCores) if needed
- **Storage Scaling**: Automatic (Azure Blob scales to petabytes)

**Capacity Planning** [TOOL-SPECIFIC: Define your expected load]:

Example (APEX):
- **Users**: 30 estimators (peak 15 concurrent)
- **Projects**: 200 active projects, 500 annual
- **Documents**: 2000 documents/year, 50-200 pages each
- **Estimates**: 300 estimates/year

[Your tool]:
- **Users**: [Number] estimators (peak [Number] concurrent)
- **Projects**: [Volume]
- **Documents**: [Volume and characteristics]
- **[Domain entities]**: [Volume]

### 7.3 Reliability [SHARED PATTERN - DO NOT MODIFY]

**SLA**: 99.9% uptime (8.7 hours downtime/year allowed)

**High Availability**:
- Container Apps: Multi-replica deployment (min 2 in production)
- Azure SQL: Business Critical tier with zone-redundant HA
- Blob Storage: Zone-redundant storage (ZRS)
- Azure OpenAI: Enterprise SLA with automatic failover

**Error Handling Pattern** [SHARED PATTERN - DO NOT MODIFY]:
```python
from apex.utils.retry import azure_retry
from apex.utils.errors import BusinessRuleViolation

@azure_retry(max_attempts=3, backoff_seconds=2)
async def call_azure_service():
    """Retry with exponential backoff for transient failures."""
    # Service call with automatic retry

def validate_business_rule(condition: bool, message: str):
    """Raise BusinessRuleViolation for user errors (no retry)."""
    if not condition:
        raise BusinessRuleViolation(message)  # Returns HTTP 400
```

### 7.4 Maintainability [SHARED PATTERN - DO NOT MODIFY]

**Code Quality Standards**:
- ✅ Black formatting (100 char line length)
- ✅ isort import sorting (black profile)
- ✅ flake8 PEP 8 linting
- ✅ bandit security scanning
- ✅ ≥80% unit test coverage
- ✅ ≥70% integration test coverage

**Documentation Requirements**:
- All public functions have Google-style docstrings
- Complex algorithms have inline comments explaining approach
- README.md provides 5-minute quick start
- CLAUDE.md provides AI assistant context
- DEPLOYMENT_OPERATIONS_GUIDE.md has complete runbook

---

## 8. References

**Related Documents**:
- **PATTERN_OVERVIEW.md**: Multi-tool vision and common baseline
- **TECHNICAL_SPECIFICATION.md**: Detailed implementation requirements for this tool
- **DEPLOYMENT_OPERATIONS_GUIDE.md**: Production deployment and operational procedures
- **IT_INTEGRATION_REVIEW_SUMMARY.md**: Enterprise architecture review and readiness score

**Shared Library Documentation**:
- `estimating-ai-core`: [Link to docs]
- `estimating-connectors`: [Link to docs]
- `estimating-security`: [Link to docs]

**Azure Documentation**:
- [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Azure Private Link](https://learn.microsoft.com/en-us/azure/private-link/)

---

**Document Version**: 1.0
**Last Updated**: [YYYY-MM-DD]
**Maintained By**: [Tool Team Name]
**Review Cycle**: Quarterly
