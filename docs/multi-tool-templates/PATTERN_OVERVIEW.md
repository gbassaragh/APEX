# Multi-Tool AI-Enabled Estimating Platform - Pattern Overview

## Document Purpose

This document establishes the foundational architecture pattern for six AI-enabled estimating tools designed for utility transmission and distribution cost estimation. Each tool addresses a specific estimating workflow while sharing 85% of their core architecture, technology stack, and operational infrastructure.

---

## 1. Unified Problem Statement

### Business Challenge

Utility cost estimating teams face increasing pressure to deliver accurate, defensible estimates under tight regulatory scrutiny (ISO-NE compliance) while managing:

- **Manual Document Processing**: 100+ page engineering drawings, specifications, and bid packages processed manually
- **Inconsistent Estimation Methods**: Different estimators use different approaches, leading to wide variance in accuracy
- **Limited Risk Quantification**: Simplistic contingency percentages instead of statistical risk analysis
- **Compliance Burden**: 7-year audit trail requirements with limited tooling support
- **Knowledge Retention**: Senior estimators retiring with institutional knowledge
- **Scale Limitations**: ~30 estimators handling increasing project volume

### Technical Gap

Current state lacks:
- **AI-Powered Document Intelligence**: Automated extraction of quantities, specifications, and requirements from engineering documents
- **Standardized Risk Analysis**: Industrial-grade Monte Carlo simulation with proper correlation modeling
- **Intelligent Classification**: AACE Class 1-5 maturity determination based on document completeness
- **Audit-Ready Traceability**: Comprehensive logging of all AI-assisted decisions and assumptions
- **Enterprise Integration**: Seamless connectivity to cost databases, ERP systems, and project management platforms

### Opportunity

Build six purpose-built AI-enabled tools that:
1. **Automate repetitive extraction tasks** (60-80% time savings on document processing)
2. **Standardize estimation methodology** across all estimators
3. **Provide statistical confidence intervals** (P50/P80/P95) via proper risk modeling
4. **Maintain complete audit trails** for regulatory compliance
5. **Preserve institutional knowledge** through AI-embedded best practices
6. **Scale elastically** with project demand using cloud-native architecture

---

## 2. Vision Statement

### Business Vision

**Transform utility cost estimation from a manual, expert-dependent process into a scalable, AI-augmented discipline that delivers:**

- **Faster Turnaround**: 50% reduction in estimate cycle time through automated document processing
- **Higher Accuracy**: ±10% variance vs. actual costs (currently ±20-30% for Class 4-5 estimates)
- **Regulatory Confidence**: 100% audit-ready estimates with complete traceability
- **Knowledge Democratization**: Junior estimators produce senior-level quality through AI guidance
- **Risk Transparency**: Statistically valid confidence intervals for all estimates
- **Operational Excellence**: <1% error rate on quantity extraction from engineering documents

### Technical Vision

**Create a unified AI-enabled estimation platform built on:**

1. **Shared AI Core** (`estimating-ai-core` library):
   - Azure OpenAI GPT-4 orchestration with maturity-aware routing
   - Reusable prompt templates and safety guardrails
   - Token management and context window optimization
   - Centralized LLM observability and cost tracking

2. **Common Integration Layer** (`estimating-connectors` library):
   - Standardized cost database access patterns
   - Azure Blob Storage document management
   - Azure AD authentication and RBAC
   - Audit logging and compliance export

3. **Proven Architecture Pattern**:
   - FastAPI REST API (proven in APEX with 104/104 tests passing)
   - Repository pattern for data access
   - Azure-native services (SQL Database, Document Intelligence, Key Vault)
   - Zero-trust network architecture with Private Endpoints

4. **Consistent DevOps Practices**:
   - Infrastructure as Code (Bicep templates)
   - GitHub Actions CI/CD pipelines
   - Multi-environment strategy (dev, staging, production)
   - Automated testing gates (≥80% unit, ≥70% integration coverage)

### Success Metrics

**By End of Year 1**:
- All six tools deployed to production with ≥95% uptime
- ≥70% estimator adoption rate across tools
- ≥40% reduction in estimate preparation time
- Zero regulatory compliance violations related to AI usage
- ≥85% user satisfaction rating

**By End of Year 2**:
- Full ERP integration for cost data synchronization
- Shared web UI framework across all tools
- ≥90% estimator adoption with cross-tool workflows
- ≥50% reduction in estimate variance vs. actuals
- AI-generated narratives requiring <10% human editing

---

## 3. Common Architecture Baseline (85% Shared Pattern)

### 3.1 Technology Stack (100% Identical)

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Language** | Python 3.11+ | Type hints, async/await, mature ecosystem |
| **API Framework** | FastAPI 0.104.0+ | OpenAPI docs, async support, proven in APEX |
| **Database** | Azure SQL Database (Business Critical) | ACID compliance, 7-year retention, zone redundancy |
| **ORM** | SQLAlchemy 2.0+ | Modern async patterns, platform-independent GUID handling |
| **Migrations** | Alembic | Declarative schema versioning |
| **Validation** | Pydantic 2.x | Type-safe DTOs, automatic OpenAPI schema generation |
| **AI Services** | Azure OpenAI (GPT-4) | Enterprise SLA, Private Endpoint support, content filtering |
| **Document Parsing** | Azure AI Document Intelligence | OCR + layout analysis, table extraction, async polling |
| **Storage** | Azure Blob Storage (ZRS) | Lifecycle management, Managed Identity auth |
| **Secrets** | Azure Key Vault | Hardware-backed encryption, automatic rotation |
| **Identity** | Azure AD + Managed Identity | Zero secrets in code, unified RBAC |
| **Observability** | Azure Application Insights | LLM token tracking, distributed tracing |
| **Compute** | Azure Container Apps | Serverless scaling, VNet injection, Private DNS |
| **Testing** | pytest + coverage.py | ≥80% unit coverage, ≥70% integration coverage |

### 3.2 Layered Architecture (85% Identical)

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                    │
│  • JWT authentication (Azure AD)                            │
│  • OpenAPI documentation (Swagger/ReDoc)                    │
│  • Request ID middleware                                     │
│  • Global exception handlers (BusinessRuleViolation, etc.)  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                          │
│  • Business logic orchestration                             │
│  • LLM calls via shared orchestrator                        │
│  • Document parsing coordination                            │
│  • Risk analysis (Monte Carlo)                              │
│  • [TOOL-SPECIFIC: Domain algorithms 15%]                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Repository Layer                         │
│  • Data access abstraction                                  │
│  • ProjectAccess authorization checks                       │
│  • Audit log creation                                       │
│  • Transaction management                                   │
│  • [TOOL-SPECIFIC: Domain entities 15%]                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                             │
│  • SQLAlchemy ORM models (GUID TypeDecorator)               │
│  • Alembic migrations                                       │
│  • NullPool for stateless Container Apps                    │
│  • [TOOL-SPECIFIC: Domain tables 20%]                       │
└─────────────────────────────────────────────────────────────┘
```

**Cross-Cutting Concerns (100% Shared)**:
- Azure integration helpers (`azure/` module)
- Utility functions (logging, retry decorators, error classes)
- Configuration management (Pydantic Settings)
- Dependency injection wiring

### 3.3 Shared Libraries (Reusable Components)

#### `estimating-ai-core` (Separate PyPI Package)
**Purpose**: Centralized AI orchestration and prompt management

**Components**:
- `LLMOrchestrator`: Maturity-aware routing (AACE Class 1-5)
- `PromptTemplateLibrary`: Reusable prompt templates with variable substitution
- `TokenManager`: Context window optimization, smart truncation
- `SafetyGuardrails`: Content filtering, PII detection, prompt sanitization
- `LLMObservabilityClient`: Token tracking, cost allocation, performance metrics

**Versioning**: Semantic versioning with 6-month major release cycle
**Testing**: ≥90% coverage with deterministic prompt fixtures

#### `estimating-connectors` (Separate PyPI Package)
**Purpose**: Standardized integration patterns

**Components**:
- `CostDatabaseClient`: Abstract interface for cost lookup services
- `DocumentStorageClient`: Azure Blob wrapper with lifecycle management
- `AuditExporter`: ISO-NE compliant export to CSV/Excel
- `ERPConnector`: [Future] Integration with enterprise systems

**Versioning**: Independent from `estimating-ai-core`, backward compatibility guaranteed
**Testing**: Integration tests against mock ERP/database endpoints

#### `estimating-security` (Separate PyPI Package)
**Purpose**: Unified authentication and authorization

**Components**:
- `AzureADAuthenticator`: JWT validation, token caching
- `ProjectAccessChecker`: RBAC with ProjectAccess table queries
- `ManagedIdentityHelper`: Azure service credential management
- `AuditLogger`: Structured logging for compliance

**Versioning**: Security patches within 48 hours of CVE disclosure
**Testing**: Penetration testing annually, automated security scans in CI/CD

### 3.4 Security Architecture (100% Identical)

#### Zero-Trust Network Design
```
Internet ─────> Azure Front Door (WAF)
                     │
                     ↓
            Azure Container Apps (VNet-injected)
                     │
          ┌──────────┼──────────┐
          ↓          ↓          ↓
    Private      Private    Private
    Endpoint     Endpoint   Endpoint
       │            │          │
    Azure SQL   Azure       Azure
    Database    OpenAI      Key Vault
```

**Security Controls**:
- **Network**: All Azure services behind Private Endpoints, no public internet access
- **Identity**: Managed Identity for service-to-service, Azure AD JWT for user authentication
- **Data**: Transparent Data Encryption (TDE) for SQL, encryption at rest for Blob Storage
- **Transport**: TLS 1.2+ enforced for all connections
- **Secrets**: Zero secrets in code/config, all in Key Vault with hardware-backed encryption
- **Audit**: All operations logged to Application Insights + AuditLog table (7-year retention)

#### RBAC Model (Shared Schema)
```sql
-- Users table (synchronized with Azure AD)
CREATE TABLE User (
    user_id UNIQUEIDENTIFIER PRIMARY KEY,
    email NVARCHAR(255) NOT NULL UNIQUE,
    display_name NVARCHAR(255),
    is_active BIT DEFAULT 1
);

-- Application roles
CREATE TABLE AppRole (
    role_id UNIQUEIDENTIFIER PRIMARY KEY,
    role_name NVARCHAR(50) NOT NULL, -- Estimator, Manager, Auditor, Admin
    permissions NVARCHAR(MAX) -- JSON array of permission strings
);

-- Per-project access control
CREATE TABLE ProjectAccess (
    access_id UNIQUEIDENTIFIER PRIMARY KEY,
    user_id UNIQUEIDENTIFIER REFERENCES User(user_id),
    project_id UNIQUEIDENTIFIER REFERENCES Project(project_id),
    role_id UNIQUEIDENTIFIER REFERENCES AppRole(role_id),
    granted_at DATETIME2 DEFAULT GETUTCDATE(),
    granted_by UNIQUEIDENTIFIER REFERENCES User(user_id)
);
```

**Authorization Pattern** (enforced in all repositories):
```python
def check_project_access(db: Session, user_id: uuid.UUID, project_id: uuid.UUID, required_permission: str):
    """Verify user has required permission for project via ProjectAccess + AppRole."""
    access = db.query(ProjectAccess).filter(
        ProjectAccess.user_id == user_id,
        ProjectAccess.project_id == project_id
    ).join(AppRole).first()

    if not access:
        raise Forbidden(f"User {user_id} has no access to project {project_id}")

    permissions = json.loads(access.role.permissions)
    if required_permission not in permissions:
        raise Forbidden(f"User lacks permission: {required_permission}")
```

### 3.5 DevOps & Deployment (100% Identical)

#### Infrastructure as Code (Bicep Templates)
```
infra/
├── modules/
│   ├── container-app.bicep         # Azure Container Apps with VNet injection
│   ├── sql-database.bicep          # Azure SQL with Private Endpoint
│   ├── blob-storage.bicep          # Blob Storage with lifecycle policies
│   ├── openai.bicep                # Azure OpenAI with Private Endpoint
│   ├── key-vault.bicep             # Key Vault with access policies
│   └── vnet.bicep                  # VNet + subnets + Private DNS zones
├── main.bicep                      # Orchestrates all modules
└── parameters/
    ├── dev.bicepparam              # Development environment
    ├── staging.bicepparam          # Staging environment
    └── production.bicepparam       # Production environment (zone-redundant)
```

#### CI/CD Pipeline (GitHub Actions)
```yaml
# .github/workflows/ci-cd.yml (identical across all tools)
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: 3.11
      - name: Install dependencies
        run: pip install -e .
      - name: Run black
        run: black src/ tests/ --check --line-length 100
      - name: Run isort
        run: isort src/ tests/ --check-only --profile black
      - name: Run flake8
        run: flake8 src/ tests/
      - name: Run bandit (security)
        run: bandit -r src/ -ll
      - name: Run pytest
        run: pytest tests/ --cov=src --cov-report=xml --cov-fail-under=80

  deploy-dev:
    needs: lint-and-test
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    steps:
      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      - name: Deploy Infrastructure
        run: |
          az deployment group create \
            --resource-group ${{ secrets.DEV_RESOURCE_GROUP }} \
            --template-file infra/main.bicep \
            --parameters infra/parameters/dev.bicepparam
      - name: Deploy Container
        run: |
          az containerapp update \
            --name ${{ secrets.DEV_APP_NAME }} \
            --resource-group ${{ secrets.DEV_RESOURCE_GROUP }} \
            --image ${{ secrets.ACR_NAME }}.azurecr.io/${{ secrets.IMAGE_NAME }}:${{ github.sha }}

  deploy-production:
    needs: lint-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production
    steps:
      # Similar to deploy-dev but with production parameters + approval gate
```

**Quality Gates** (enforced in pipeline):
- ✅ Black formatting (100 char line length)
- ✅ isort import sorting (black profile)
- ✅ flake8 linting (PEP 8 compliance)
- ✅ bandit security scanning (no HIGH/CRITICAL issues)
- ✅ pytest with ≥80% unit coverage, ≥70% integration coverage
- ✅ Alembic migration check (no uncommitted schema changes)

#### Environment Strategy
| Environment | Purpose | Database Tier | Scaling | Cost |
|-------------|---------|---------------|---------|------|
| **Development** | Developer testing, integration testing | Basic (2 vCores) | Manual 0-1 replicas | ~$200/mo |
| **Staging** | Pre-production validation, UAT | General Purpose (4 vCores) | Auto 1-3 replicas | ~$800/mo |
| **Production** | Live estimating operations | Business Critical (8 vCores, zone-redundant) | Auto 2-10 replicas | ~$2500/mo |

### 3.6 Observability (100% Identical)

#### Azure Application Insights Integration
```python
# src/{tool_name}/utils/logging.py (shared pattern)
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer

class ObservabilityClient:
    """Unified observability for all tools."""

    def __init__(self, connection_string: str, service_name: str):
        self.service_name = service_name

        # Structured logging to Application Insights
        self.logger = logging.getLogger(service_name)
        self.logger.addHandler(AzureLogHandler(connection_string=connection_string))
        self.logger.setLevel(logging.INFO)

        # Distributed tracing (10% sampling in prod)
        self.tracer = Tracer(
            exporter=AzureExporter(connection_string=connection_string),
            sampler=ProbabilitySampler(0.1)
        )

    def log_llm_call(self, model: str, tokens_in: int, tokens_out: int,
                     operation: str, project_id: str, duration_ms: int):
        """Log LLM usage for cost tracking and performance monitoring."""
        self.logger.info(
            "LLM_CALL",
            extra={
                "custom_dimensions": {
                    "service": self.service_name,
                    "model": model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "operation": operation,
                    "project_id": project_id,
                    "duration_ms": duration_ms,
                    "cost_usd": self._calculate_cost(model, tokens_in, tokens_out)
                }
            }
        )
```

**Monitored Metrics** (dashboards shared across all tools):
- LLM token usage by operation type (cost allocation)
- API endpoint response times (P50/P95/P99)
- Database query performance (slow query alerts)
- Document parsing duration (by page count)
- Monte Carlo iteration times (for capacity planning)
- Error rates by endpoint and exception type
- Active user sessions and concurrent requests

**Alerts** (configured identically across tools):
- Error rate >1% for 5 minutes → Page on-call engineer
- API P95 latency >2 seconds → Slack notification
- LLM token cost >$500/day → Email budget owner
- Failed authentication rate >5% → Security team escalation
- Database CPU >80% for 10 minutes → Auto-scale trigger

### 3.7 Tool-Specific Customization (15% Variable)

Each tool customizes these areas while maintaining the 85% shared baseline:

#### Domain-Specific Data Models (15-20% of schema)
```python
# Example: APEX has EstimateLineItem with WBS hierarchy
# Another tool might have BidComparison with vendor analysis
class ToolSpecificEntity(Base):
    """Extend common Project/Document/User models with domain entities."""
    __tablename__ = "tool_specific_table"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID, ForeignKey("project.project_id"))  # Common FK
    # ... tool-specific columns
```

#### Custom Cost Codes and Hierarchies
- **APEX**: WBS codes for transmission/distribution (10-xxx, 20-xxx, etc.)
- **Tool 2**: Different code structure for substation work
- **Tool 3**: Renewable interconnection cost codes

#### AACE Classification Logic (Tool-Specific Algorithms)
- Different maturity metrics per tool type
- Custom completeness scoring formulas
- Domain-specific document requirements

#### Risk Factor Definitions
- **APEX**: Terrain type, structure complexity, conductor type
- **Tool 2**: Equipment lead time, labor availability
- **Tool 3**: Permitting risk, environmental factors

#### LLM Prompt Templates (Domain-Specific)
```python
# estimating-ai-core provides base templates
# Each tool overrides with domain vocabulary

APEX_PROMPTS = {
    "quantity_extraction": """
    You are a utility transmission estimator. Extract quantities from this engineering drawing.

    Focus on:
    - Structure counts (tangent, deadend, angle)
    - Conductor lengths by type (795 ACSR, 954 ACSR)
    - Foundation types (drilled shaft, direct embed)
    ...
    """,
    # Other tool would have different focus areas
}
```

---

## 4. Six Tools Overview

### Tool Roadmap (Phased Deployment)

| Tool | Domain | Primary Users | Phase | Status | Shared % |
|------|--------|---------------|-------|--------|----------|
| **APEX** | Transmission/Distribution Estimates | 15 estimators | ✅ **MVP Complete** | Production (95/100 readiness) | 85% |
| **Tool 2** | Substation Cost Estimating | 8 estimators | 🔄 **Phase 1** | Development | 90% |
| **Tool 3** | Renewable Interconnection Studies | 5 estimators | 📋 **Phase 2** | Planning | 85% |
| **Tool 4** | Bid Comparison & Analysis | 12 estimators + managers | 📋 **Phase 2** | Planning | 80% |
| **Tool 5** | Project Budget Tracking | 30 estimators + auditors | 📋 **Phase 3** | Concept | 75% |
| **Tool 6** | Cost Database Management | Admins + senior estimators | 📋 **Phase 3** | Concept | 70% |

### Shared Component Dependencies
```
APEX (MVP Complete) ──┐
                       ├──> estimating-ai-core v1.0.0 (LLM orchestration)
Tool 2 (Development) ─┤
                       ├──> estimating-connectors v0.5.0 (integrations)
Tool 3 (Planning) ─────┤
                       └──> estimating-security v1.0.0 (auth/audit)
```

**Versioning Strategy**:
- Major version bumps require all tools to upgrade within 6 months
- Minor versions are backward compatible, recommended upgrade within 3 months
- Security patches are mandatory within 2 weeks of release

---

## 5. Success Criteria for Pattern Adoption

### Technical Adoption Metrics
- ✅ All six tools use identical Bicep templates (only parameter variations)
- ✅ All six tools achieve ≥80% unit test coverage, ≥70% integration coverage
- ✅ All six tools deployed via GitHub Actions with same CI/CD pipeline structure
- ✅ Zero production incidents related to shared library bugs
- ✅ Mean time to deploy new tool from template: <4 weeks

### Business Adoption Metrics
- ✅ ≥70% estimator adoption rate across all tools by end of Year 1
- ✅ ≥40% reduction in estimate preparation time vs. pre-AI baseline
- ✅ Zero regulatory compliance violations related to AI usage
- ✅ ≥85% user satisfaction rating (quarterly surveys)
- ✅ Cost per estimate <$50 (Azure + labor amortized)

### Operational Metrics
- ✅ 99.9% uptime SLA across all production tools
- ✅ <2 second P95 API response time for all endpoints
- ✅ <$5000/month total Azure spend across all tools (excl. SQL data storage)
- ✅ LLM token cost <$0.50 per estimate on average
- ✅ Zero security incidents (unauthorized access, data leaks)

---

## 6. Governance and Maintenance

### Shared Library Ownership
- **Product Owner**: [Business Owner Name]
- **Technical Lead**: [Lead Developer Name]
- **Architecture Review**: Quarterly review with IT enterprise architects

### Change Management Process
1. **Proposal**: GitHub issue with RFC template in `estimating-ai-core` repo
2. **Impact Assessment**: Review by all six tool maintainers
3. **Approval Gate**: Requires 4/6 tool leads to approve breaking changes
4. **Communication**: 30-day notice for major version bumps
5. **Migration Support**: Shared library maintainers provide upgrade guides

### Documentation Standards
- All shared libraries maintain comprehensive API documentation (Sphinx)
- Each tool maintains CLAUDE.md with tool-specific implementation notes
- Architecture Decision Records (ADRs) for all major pattern changes
- Quarterly architecture review presentations to IT leadership

---

## Next Steps

1. **For New Tool Development**: Use this Pattern Overview + Architecture Template + Technical Specification Template
2. **For IT Review**: Proceed to Leadership-Facing Materials (Executive Summary, Architecture Narrative)
3. **For Development Teams**: Reference Developer-Facing Artifacts (README template, CONTRIBUTING guidelines)

---

**Document Version**: 1.0
**Last Updated**: 2025-01-20
**Maintained By**: APEX Development Team
**Review Cycle**: Quarterly
