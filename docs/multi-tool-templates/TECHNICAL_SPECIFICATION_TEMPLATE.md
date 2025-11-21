# [TOOL NAME] - Technical Specification

> **FILL-OUT INSTRUCTIONS**:
> - This template provides comprehensive structure for documenting implementation details
> - Replace all `[PLACEHOLDER]` text with actual values
> - Keep sections marked `[SHARED PATTERN]` identical to proven APEX implementation
> - Sections marked `[TOOL-SPECIFIC]` require domain customization
> - Example text in gray boxes shows what good content looks like
> - Delete these instructions and example boxes when complete

---

## Document Control

| Property | Value |
|----------|-------|
| **Tool Name** | [Full name, e.g., "APEX - AI-Powered Estimation Expert"] |
| **Tool Code** | [Short code, e.g., "APEX", "SUBSTATION", "INTERCONNECT"] |
| **Version** | [Semantic version, e.g., "1.0.0"] |
| **Status** | [MVP, Development, Production] |
| **Owner** | [Product owner name] |
| **Tech Lead** | [Lead developer name] |
| **Last Updated** | [YYYY-MM-DD] |
| **Production Readiness Score** | [X/100 - Update after IT review] |

---

## 1. Project Overview

### 1.1 Executive Summary

**[TOOL-SPECIFIC - 2-3 paragraphs describing business purpose]**

<details>
<summary>Example (APEX)</summary>

> APEX (AI-Powered Estimation Expert) automates cost estimation for utility transmission and distribution projects. The system processes engineering drawings, specifications, and historical bid data to generate AACE-compliant estimates with statistical confidence intervals (P50/P80/P95) through Monte Carlo risk analysis.
>
> Primary users are 15 internal utility cost estimators who handle 300+ estimates annually. The tool reduces estimate preparation time by 40% while improving accuracy from ±20-30% variance to ±10% through AI-powered document intelligence and standardized risk modeling.
>
> Regulatory compliance (ISO-NE) requires complete audit trails for all estimates with 7-year retention. APEX maintains comprehensive audit logs of all AI-assisted decisions and assumptions, providing 100% defensible estimates for regulatory review.
</details>

**[Your tool - fill in similar content]**:
> [Tool name] solves [business problem] for [user population]. The system [key capabilities and workflow].
>
> Primary users are [number] [role description] who [current process description]. The tool [key value proposition with metrics].
>
> Regulatory/business requirements include [compliance needs]. [Tool name] addresses these through [compliance approach].

### 1.2 Problem Statement

**Current State Pain Points**:
- [Pain point 1: e.g., Manual document processing takes 8-12 hours per project]
- [Pain point 2: e.g., Inconsistent estimation methods across 30 estimators]
- [Pain point 3: e.g., Limited risk quantification capabilities]
- [Pain point 4: e.g., Compliance burden with inadequate audit tooling]

**Proposed Solution**:
- [Solution 1: e.g., AI-powered document parsing reduces processing to <30 seconds]
- [Solution 2: e.g., Standardized LLM-based validation ensures consistency]
- [Solution 3: e.g., Industrial-grade Monte Carlo provides statistical confidence]
- [Solution 4: e.g., Automatic audit logging for all AI decisions]

**Success Metrics** (12 months post-launch):
- [Metric 1: e.g., 40% reduction in estimate preparation time]
- [Metric 2: e.g., ±10% cost variance vs. actuals (down from ±20-30%)]
- [Metric 3: e.g., 70% user adoption rate]
- [Metric 4: e.g., Zero regulatory compliance violations]

### 1.3 Scope

**In Scope for MVP**:
- ✅ [Feature 1: e.g., Document upload and Azure DI parsing]
- ✅ [Feature 2: e.g., AI-based document validation]
- ✅ [Feature 3: e.g., AACE classification determination]
- ✅ [Feature 4: e.g., Monte Carlo risk analysis (10K iterations)]
- ✅ [Feature 5: e.g., Estimate export to Excel]

**Out of Scope for MVP** (future phases):
- ❌ [Feature A: e.g., Web UI (API-only for MVP)]
- ❌ [Feature B: e.g., ERP integration for cost data sync]
- ❌ [Feature C: e.g., Multi-estimator collaboration workflows]
- ❌ [Feature D: e.g., Mobile app for field data collection]

**Phase 2 Roadmap** (6-12 months):
- [Phase 2 Feature 1]
- [Phase 2 Feature 2]

---

## 2. User Personas and Workflows

### 2.1 User Personas

#### Persona 1: [Primary User Role]

**[TOOL-SPECIFIC - Define your primary users]**

<details>
<summary>Example (APEX - Transmission Estimator)</summary>

**Role**: Senior Transmission Cost Estimator
**Background**: 10+ years utility experience, Excel power user, limited Python/AI knowledge
**Goals**:
- Generate accurate Class 3-4 estimates in <8 hours (currently 12-16 hours)
- Maintain defensible assumptions for regulatory review
- Leverage historical bid data for unit cost validation

**Pain Points**:
- Manual quantity extraction from 100+ page engineering drawings
- Difficulty quantifying risk with simple contingency percentages
- Time-consuming cross-checking of cost codes and unit prices

**Technical Comfort**: Medium (Excel VBA, SQL queries, no coding experience)
**APEX Workflow**: Upload drawings → Review AI-extracted quantities → Adjust assumptions → Export estimate
</details>

[Your tool]:
**Role**: [Job title]
**Background**: [Experience, technical skills, domain expertise]
**Goals**:
- [Goal 1]
- [Goal 2]
- [Goal 3]

**Pain Points**:
- [Pain 1]
- [Pain 2]
- [Pain 3]

**Technical Comfort**: [Low/Medium/High - describe skill level]
**Tool Workflow**: [Step-by-step workflow]

#### Persona 2: [Secondary User Role]

[Repeat above structure for Manager/Auditor/Admin roles]

### 2.2 Core Workflows

#### Workflow 1: [Primary Workflow Name]

**[TOOL-SPECIFIC - Document main user journey]**

<details>
<summary>Example (APEX - Generate Estimate)</summary>

**Actor**: Transmission Estimator
**Trigger**: New project request from Engineering
**Preconditions**: Engineering drawings and specifications available

**Steps**:
1. **Create Project** (API: `POST /api/v1/projects`)
   - Input: Project name, location, voltage class
   - Output: `project_id` for subsequent operations

2. **Upload Documents** (API: `POST /api/v1/documents`)
   - Input: PDF drawings, Excel quantity sheets, Word specifications
   - Processing: Azure Blob Storage upload → Azure Document Intelligence parsing (async)
   - Output: Parsed tables, text blocks, metadata

3. **Validate Documents** (API: `POST /api/v1/documents/{id}/validate`)
   - AI Check: LLM reviews completeness, consistency, conflicts
   - Output: `ValidationStatus` (VALID/INVALID) + gap list

4. **Generate Estimate** (API: `POST /api/v1/estimates`)
   - AACE Classification: Analyze maturity + completeness → Class 1-5
   - Quantity Extraction: LLM extracts counts, lengths, types from drawings
   - Cost Computation: Apply unit costs from cost database → Base cost
   - Risk Analysis: Monte Carlo simulation (10K iterations) → P50/P80/P95
   - Narrative Generation: LLM creates assumptions, exclusions, risks text
   - Output: Complete `Estimate` with line items, risk factors, narrative

5. **Review and Adjust** (API: `PATCH /api/v1/estimates/{id}/line-items`)
   - Estimator reviews AI-extracted quantities
   - Manually adjusts quantities, unit costs, risk distributions
   - Re-runs Monte Carlo if risk factors change

6. **Export Estimate** (API: `GET /api/v1/estimates/{id}/export`)
   - Output: Excel workbook with summary, line items, risk chart

**Success Criteria**:
- Estimate generated in <60 seconds
- ≥90% quantity extraction accuracy (manual validation)
- P80 cost within ±15% of final bid (historical validation)

**Error Handling**:
- Invalid document → Return validation errors, block estimate generation
- Monte Carlo timeout → Fall back to deterministic base cost, notify user
- LLM API failure → Retry 3x with exponential backoff, escalate if persistent
</details>

[Your tool - document 2-3 core workflows]:
**Actor**: [User role]
**Trigger**: [What initiates this workflow]
**Preconditions**: [Required state]

**Steps**:
1. [Step 1 with API endpoint]
2. [Step 2 with API endpoint]
3. [...]

**Success Criteria**:
- [Criterion 1]
- [Criterion 2]

**Error Handling**:
- [Error scenario 1] → [Recovery approach]
- [Error scenario 2] → [Recovery approach]

---

## 3. System Architecture

### 3.1 Component Diagram

```
[SHARED PATTERN - Customize component names only]

┌────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                          │
│  [FUTURE: Web UI - React + TypeScript]                         │
│  [MVP: Direct API access via Postman/Swagger UI]               │
└────────────────────────────────────────────────────────────────┘
                            │ HTTPS (JWT Bearer token)
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                       API Layer (FastAPI)                      │
│ ────────────────────────────────────────────────────────────── │
│  Routers (src/{tool}/api/v1/):                                 │
│    • health.py           - Liveness/readiness probes           │
│    • projects.py         - Project CRUD                        │
│    • documents.py        - Upload, parse, validate             │
│    • [domain].py         - [TOOL-SPECIFIC endpoints]           │
│                                                                 │
│  Middleware:                                                    │
│    • JWTAuthMiddleware   - Azure AD validation                 │
│    • RequestIDMiddleware - X-Request-ID injection              │
│                                                                 │
│  Dependencies (src/{tool}/dependencies.py):                    │
│    • get_db()            - Session with auto-commit/rollback   │
│    • get_current_user()  - JWT → User object                   │
└────────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                      Service Layer                             │
│ ────────────────────────────────────────────────────────────── │
│  Shared Services (via libraries):                              │
│    • LLMOrchestrator     - estimating-ai-core                  │
│    • DocumentParser      - Azure DI async wrapper              │
│                                                                 │
│  [TOOL-SPECIFIC Services]:                                     │
│    • [service_1]         - [Purpose]                           │
│    • [service_2]         - [Purpose]                           │
│                                                                 │
│  Example (APEX):                                               │
│    • aace_classifier.py      - Maturity + completeness scoring │
│    • cost_database.py        - CBS/WBS builder                 │
│    • risk_analysis.py        - Monte Carlo engine              │
│    • estimate_generator.py   - Orchestration                   │
└────────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                    Repository Layer                            │
│ ────────────────────────────────────────────────────────────── │
│    • ProjectRepository   - Project CRUD + access checks        │
│    • DocumentRepository  - Document CRUD + blob mgmt           │
│    • [Domain]Repository  - [TOOL-SPECIFIC entities]            │
│    • AuditRepository     - Audit log creation                  │
└────────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌────────────────────────────────────────────────────────────────┐
│                        Data Layer                              │
│ ────────────────────────────────────────────────────────────── │
│  Azure SQL Database (Business Critical, Zone-Redundant):       │
│    • Common: User, AppRole, ProjectAccess, Project, Document   │
│    • [TOOL-SPECIFIC]: [List domain tables]                     │
│    • AuditLog (7-year retention)                               │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 API Endpoints [TOOL-SPECIFIC]

#### Health Endpoints [SHARED PATTERN - DO NOT MODIFY]

```yaml
GET /health/live:
  summary: "Kubernetes liveness probe"
  responses:
    200:
      description: "Service is running"
      content:
        application/json:
          schema:
            type: object
            properties:
              status: { type: string, example: "healthy" }

GET /health/ready:
  summary: "Kubernetes readiness probe"
  description: "Checks database connectivity, Azure services availability"
  responses:
    200:
      description: "Service is ready to accept traffic"
      content:
        application/json:
          schema:
            type: object
            properties:
              status: { type: string, example: "ready" }
              checks:
                type: object
                properties:
                  database: { type: string, example: "ok" }
                  blob_storage: { type: string, example: "ok" }
                  azure_openai: { type: string, example: "ok" }
    503:
      description: "Service not ready (dependencies unavailable)"
```

#### Project Endpoints [SHARED PATTERN]

```yaml
POST /api/v1/projects:
  summary: "Create new project"
  security:
    - AzureAD_JWT: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          required: [project_name]
          properties:
            project_name: { type: string, minLength: 3, maxLength: 255 }
            project_description: { type: string }
            [TOOL-SPECIFIC fields]: { type: string }
  responses:
    201:
      description: "Project created successfully"
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Project'
    400:
      description: "Validation error"
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
    401:
      description: "Unauthorized (invalid JWT)"

GET /api/v1/projects:
  summary: "List projects accessible to current user"
  security:
    - AzureAD_JWT: []
  parameters:
    - name: page
      in: query
      schema: { type: integer, default: 1 }
    - name: page_size
      in: query
      schema: { type: integer, default: 20, maximum: 100 }
  responses:
    200:
      description: "Paginated list of projects"
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/PaginatedProjects'
```

#### [TOOL-SPECIFIC Endpoints]

**[Document your domain-specific API endpoints]**

<details>
<summary>Example (APEX - Estimate Endpoints)</summary>

```yaml
POST /api/v1/estimates:
  summary: "Generate estimate for project"
  description: "Orchestrates AACE classification, cost computation, Monte Carlo analysis, narrative generation"
  security:
    - AzureAD_JWT: []
  requestBody:
    required: true
    content:
      application/json:
        schema:
          type: object
          required: [project_id]
          properties:
            project_id:
              type: string
              format: uuid
            monte_carlo_iterations:
              type: integer
              default: 10000
              minimum: 1000
              maximum: 100000
  responses:
    201:
      description: "Estimate generated successfully"
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/Estimate'
    400:
      description: "Validation error (e.g., no validated documents)"
    403:
      description: "User lacks permission estimate:create for project"
    422:
      description: "Business rule violation (e.g., incomplete documents)"

GET /api/v1/estimates/{estimate_id}/export:
  summary: "Export estimate to Excel"
  security:
    - AzureAD_JWT: []
  parameters:
    - name: estimate_id
      in: path
      required: true
      schema: { type: string, format: uuid }
  responses:
    200:
      description: "Excel workbook with estimate details"
      content:
        application/vnd.openxmlformats-officedocument.spreadsheetml.sheet:
          schema:
            type: string
            format: binary
```
</details>

[Your tool - list 5-10 core endpoints with similar detail]

### 3.3 Data Models [TOOL-SPECIFIC]

#### Common Models [SHARED PATTERN - DO NOT MODIFY]

```python
# src/{tool}/models/database.py

from sqlalchemy.orm import DeclarativeBase, mapped_column
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "user"

    user_id = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    email = mapped_column(String(255), nullable=False, unique=True)
    display_name = mapped_column(String(255))
    is_active = mapped_column(Boolean, default=True)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Project(Base):
    __tablename__ = "project"

    project_id = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    project_name = mapped_column(String(255), nullable=False)
    project_description = mapped_column(Text)
    status = mapped_column(String(50), nullable=False, default="DRAFT")
    created_by = mapped_column(GUID, ForeignKey("user.user_id"), nullable=False)
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # [TOOL-SPECIFIC: Add domain fields here]
    # Example: voltage_class = mapped_column(String(20))
```

#### [TOOL-SPECIFIC Models]

**[Document your domain entities with SQLAlchemy ORM definitions]**

<details>
<summary>Example (APEX - Estimate Model)</summary>

```python
from apex.models.enums import AACEClass
from decimal import Decimal

class Estimate(Base):
    __tablename__ = "estimate"

    estimate_id = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    project_id = mapped_column(GUID, ForeignKey("project.project_id"), nullable=False)
    aace_class = mapped_column(String(10), nullable=False)  # CLASS_1 to CLASS_5
    base_cost_usd = mapped_column(Numeric(18, 2), nullable=False)
    p50_cost_usd = mapped_column(Numeric(18, 2))  # Monte Carlo median
    p80_cost_usd = mapped_column(Numeric(18, 2))  # 80th percentile
    p95_cost_usd = mapped_column(Numeric(18, 2))  # 95th percentile
    assumptions_narrative = mapped_column(Text)   # LLM-generated
    created_at = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="estimates")
    line_items = relationship("EstimateLineItem", back_populates="estimate", cascade="all, delete-orphan")
    risk_factors = relationship("RiskFactor", back_populates="estimate", cascade="all, delete-orphan")

class EstimateLineItem(Base):
    __tablename__ = "estimate_line_item"

    line_item_id = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    estimate_id = mapped_column(GUID, ForeignKey("estimate.estimate_id"), nullable=False)
    parent_line_item_id = mapped_column(GUID, ForeignKey("estimate_line_item.line_item_id"))
    wbs_code = mapped_column(String(20), nullable=False)  # e.g., "10-100-050"
    description = mapped_column(String(500))
    quantity = mapped_column(Numeric(18, 4))
    unit = mapped_column(String(20))
    unit_cost_usd = mapped_column(Numeric(18, 2))
    total_cost_usd = mapped_column(Numeric(18, 2))

    # Relationships
    estimate = relationship("Estimate", back_populates="line_items")
    parent = relationship("EstimateLineItem", remote_side=[line_item_id], back_populates="children")
    children = relationship("EstimateLineItem", back_populates="parent")
```
</details>

[Your tool - define 3-5 core domain models]:

```python
class [Entity1](Base):
    __tablename__ = "[table_name]"

    [primary_key] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    # [Define columns with types, constraints]
    # [Define relationships]
```

### 3.4 Pydantic Schemas [TOOL-SPECIFIC]

**[Define request/response DTOs for API validation]**

<details>
<summary>Example (APEX - Estimate Schemas)</summary>

```python
# src/apex/models/schemas.py

from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime
import uuid

class EstimateCreate(BaseModel):
    """Request schema for creating estimate."""
    project_id: uuid.UUID = Field(..., description="Project to estimate")
    monte_carlo_iterations: int = Field(10000, ge=1000, le=100000, description="Number of Monte Carlo simulations")

class EstimateLineItemResponse(BaseModel):
    """Response schema for estimate line item."""
    line_item_id: uuid.UUID
    wbs_code: str
    description: str | None
    quantity: Decimal | None
    unit: str | None
    unit_cost_usd: Decimal | None
    total_cost_usd: Decimal | None
    children: list["EstimateLineItemResponse"] = []

    model_config = ConfigDict(from_attributes=True)

class EstimateResponse(BaseModel):
    """Response schema for complete estimate."""
    estimate_id: uuid.UUID
    project_id: uuid.UUID
    aace_class: str
    base_cost_usd: Decimal
    p50_cost_usd: Decimal | None
    p80_cost_usd: Decimal | None
    p95_cost_usd: Decimal | None
    assumptions_narrative: str | None
    created_at: datetime
    line_items: list[EstimateLineItemResponse]

    model_config = ConfigDict(from_attributes=True)
```
</details>

[Your tool - define request/response schemas for core endpoints]

---

## 4. AI Integration

### 4.1 LLM Usage Patterns [TOOL-SPECIFIC]

**Azure OpenAI Configuration**:
- **Model**: GPT-4 (128K context window)
- **Deployment**: [deployment-name, e.g., "gpt-4-turbo-2024-04-09"]
- **Endpoint**: [Azure OpenAI endpoint URL from Key Vault]
- **Authentication**: Managed Identity (DefaultAzureCredential)
- **Content Filtering**: Enabled (Hate, Violence, Self-Harm detection)

**LLM Operations** [TOOL-SPECIFIC - Define your AI use cases]:

<details>
<summary>Example (APEX)</summary>

| Operation | Prompt Template | AACE Class | Temperature | Max Tokens | Cost/Call |
|-----------|-----------------|------------|-------------|------------|-----------|
| **Document Validation** | `document_validation` | All | 0.3 | 2000 | ~$0.15 |
| **Quantity Extraction** | `quantity_extraction` | 3-5 | 0.1 | 4000 | ~$0.30 |
| **Risk Narrative** | `risk_narrative` | All | 0.7 | 3000 | ~$0.25 |
| **Assumptions Generation** | `assumptions_narrative` | 1-2 | 0.1 | 3000 | ~$0.25 |

**Total LLM Cost per Estimate**: ~$0.95 (based on GPT-4 Turbo pricing $10/1M input, $30/1M output)
</details>

[Your tool - list AI operations with details]:

| Operation | Prompt Template | Context | Temperature | Max Tokens | Cost/Call |
|-----------|-----------------|---------|-------------|------------|-----------|
| [Op 1] | [template_name] | [When used] | [0.0-1.0] | [tokens] | [$X.XX] |
| [Op 2] | [template_name] | [When used] | [0.0-1.0] | [tokens] | [$X.XX] |

### 4.2 Prompt Engineering [TOOL-SPECIFIC]

**[Document 2-3 critical prompts with full text]**

<details>
<summary>Example (APEX - Quantity Extraction Prompt)</summary>

```python
QUANTITY_EXTRACTION_PROMPT = """
You are a utility transmission cost estimator with 20+ years of experience. Your task is to extract quantities from engineering drawings for a {voltage_class} transmission line project.

**Input Documents**:
{document_summaries}

**Extract the following quantities**:
1. Structure counts by type:
   - Tangent structures (straight-line support)
   - Deadend structures (terminal points, line angles >30°)
   - Angle structures (line angles 3-30°)
   - Specialty structures (river crossings, railroad crossings)

2. Conductor lengths by type:
   - Specify ACSR size (e.g., 795 ACSR, 954 ACSR)
   - Account for sag and span assumptions
   - Note if documents provide explicit conductor footage or if estimated from structure count

3. Foundation types and counts:
   - Drilled shaft foundations (depth and diameter)
   - Direct embed foundations
   - Rock anchor foundations

**Output Format** (JSON):
```json
{{
  "structures": [
    {{"type": "tangent", "count": 45, "confidence": "high", "source": "Drawing Sheet 5"}},
    {{"type": "deadend", "count": 8, "confidence": "medium", "source": "Inferred from line angles in Drawing Sheet 3"}}
  ],
  "conductors": [
    {{"type": "795_ACSR", "length_feet": 15000, "confidence": "high", "source": "Bill of Materials Sheet 12"}}
  ],
  "foundations": [
    {{"type": "drilled_shaft", "diameter_inches": 48, "depth_feet": 25, "count": 40, "confidence": "high"}}
  ],
  "gaps": [
    "Conductor sag assumptions not specified - used 3% industry standard",
    "Foundation soil conditions not provided - assumed Class B per region"
  ]
}}
```

**Critical Instructions**:
- ONLY extract quantities explicitly stated or clearly inferable from drawings
- Mark confidence as "high" (explicit), "medium" (inferable), or "low" (assumed)
- Always cite source (drawing sheet number, table, or note)
- Flag all gaps, assumptions, and ambiguities in "gaps" array
- If conflicting information exists, list all values with sources and flag as conflict
"""
```
</details>

[Your tool - provide 2-3 critical prompt templates]:

```
[PROMPT_NAME] = """
[Full prompt text with variable substitution markers like {variable_name}]
"""
```

### 4.3 Token Management [SHARED PATTERN]

**Context Window Strategy**:
- **Total Budget**: 128K tokens (GPT-4 Turbo)
- **Reserved for Response**: 4K tokens
- **Available for Prompt**: 124K tokens

**Truncation Logic** (when content exceeds budget):
```python
from estimating_ai_core import TokenManager
import tiktoken

token_manager = TokenManager(model="gpt-4", max_tokens=124000)

# Prioritize content by importance
content_chunks = [
    {"text": system_prompt, "priority": 1, "required": True},
    {"text": user_instructions, "priority": 1, "required": True},
    {"text": document_metadata, "priority": 2, "required": False},
    {"text": document_content_page_1, "priority": 3, "required": False},
    {"text": document_content_page_2, "priority": 4, "required": False},
    # ... additional pages with decreasing priority
]

# Smart truncation: Keep required + highest priority chunks
final_prompt = token_manager.build_prompt(content_chunks)
```

### 4.4 Safety and Compliance [SHARED PATTERN - DO NOT MODIFY]

**Content Filtering**: Enabled via Azure OpenAI (mandatory, cannot disable)
- Hate speech detection
- Violence/graphic content detection
- Self-harm detection
- Sexual content detection (not relevant for estimation, but enforced)

**PII Scrubbing** (before LLM calls):
```python
from estimating_security import PIIScrubber

scrubber = PIIScrubber()
sanitized_text = scrubber.remove_pii(
    text=document_content,
    patterns=["SSN", "PHONE", "EMAIL", "CREDIT_CARD"]
)
```

**Prompt Injection Detection**:
```python
from estimating_security import PromptInjectionDetector

detector = PromptInjectionDetector()
if detector.is_malicious(user_input):
    raise BusinessRuleViolation("Potentially malicious input detected")
```

**Audit Logging** (NO prompt content, only metadata):
```python
audit_logger.log(
    user_id=user_id,
    action="llm.generate",
    resource_type="Estimate",
    resource_id=estimate_id,
    details={
        "model": "gpt-4-turbo",
        "operation": "quantity_extraction",
        "tokens_in": 1500,
        "tokens_out": 800,
        "duration_ms": 2300,
        "cost_usd": 0.089
        # NOTE: NO prompt or response content logged
    }
)
```

---

## 5. Service Layer Design [TOOL-SPECIFIC]

### 5.1 Service Overview

**[List your domain services and their responsibilities]**

<details>
<summary>Example (APEX)</summary>

| Service | Responsibility | Dependencies |
|---------|---------------|--------------|
| **LLMOrchestrator** | AI call coordination, maturity-aware routing | estimating-ai-core, Azure OpenAI |
| **DocumentParser** | Azure DI async wrapper, table extraction | Azure Document Intelligence |
| **AACEClassifier** | Maturity + completeness scoring → Class 1-5 | LLMOrchestrator, DocumentRepository |
| **CostDatabaseService** | CBS/WBS builder, cost code lookup | CostCode definitions, LLMOrchestrator |
| **RiskAnalysisService** | Monte Carlo engine (LHS, Iman-Conover) | scipy, numpy |
| **EstimateGenerator** | Main orchestration service | All of the above |
</details>

[Your tool]:

| Service | Responsibility | Dependencies |
|---------|---------------|--------------|
| [Service 1] | [Purpose] | [Dependencies] |
| [Service 2] | [Purpose] | [Dependencies] |

### 5.2 Key Service Implementation [TOOL-SPECIFIC]

**[Provide implementation details for 1-2 critical services]**

<details>
<summary>Example (APEX - EstimateGenerator Service)</summary>

```python
# src/apex/services/estimate_generator.py

from apex.services.llm.orchestrator import LLMOrchestrator
from apex.services.aace_classifier import AACEClassifier
from apex.services.cost_database import CostDatabaseService
from apex.services.risk_analysis import RiskAnalysisService
from apex.database.repositories import EstimateRepository, ProjectRepository, DocumentRepository
from apex.models.database import Estimate, EstimateLineItem
from sqlalchemy.orm import Session
import uuid

class EstimateGeneratorService:
    """Orchestrates estimate generation workflow."""

    def __init__(
        self,
        db: Session,
        llm_orchestrator: LLMOrchestrator,
        aace_classifier: AACEClassifier,
        cost_service: CostDatabaseService,
        risk_service: RiskAnalysisService
    ):
        self.db = db
        self.llm = llm_orchestrator
        self.aace = aace_classifier
        self.cost = cost_service
        self.risk = risk_service

        self.estimate_repo = EstimateRepository(db)
        self.project_repo = ProjectRepository(db)
        self.document_repo = DocumentRepository(db)

    async def generate_estimate(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        monte_carlo_iterations: int = 10000
    ) -> Estimate:
        """
        Generate complete estimate for project.

        Workflow:
        1. Load project and documents
        2. Check user access
        3. Classify AACE class
        4. Compute base cost + line items
        5. Run Monte Carlo analysis
        6. Generate narrative/assumptions
        7. Persist estimate
        8. Create audit log

        Args:
            project_id: Project to estimate
            user_id: User requesting estimate
            monte_carlo_iterations: Number of Monte Carlo simulations

        Returns:
            Complete Estimate with line items, risk factors, narrative

        Raises:
            Forbidden: User lacks permission
            BusinessRuleViolation: No validated documents
        """

        # Step 1: Load project
        project = self.project_repo.get_with_access_check(project_id, user_id, "estimate:create")

        # Step 2: Load validated documents
        documents = self.document_repo.get_by_project(project_id, status="VALID")
        if not documents:
            raise BusinessRuleViolation("No validated documents available for estimation")

        # Step 3: Classify AACE class
        aace_class = await self.aace.determine_class(project, documents)

        # Step 4: Compute base cost + line items
        base_cost, line_items = await self.cost.compute_base_cost(project, documents)

        # Step 5: Run Monte Carlo analysis
        risk_factors = await self.cost.extract_risk_factors(line_items)
        monte_carlo_result = await self.risk.run_simulation(
            line_items=line_items,
            risk_factors=risk_factors,
            iterations=monte_carlo_iterations
        )

        # Step 6: Generate narrative
        narrative = await self.llm.generate(
            prompt=self._build_narrative_prompt(project, aace_class, line_items, risk_factors),
            aace_class=aace_class,
            max_tokens=3000
        )

        # Step 7: Persist estimate (atomic transaction)
        estimate = Estimate(
            project_id=project_id,
            aace_class=aace_class.value,
            base_cost_usd=base_cost,
            p50_cost_usd=monte_carlo_result.p50,
            p80_cost_usd=monte_carlo_result.p80,
            p95_cost_usd=monte_carlo_result.p95,
            assumptions_narrative=narrative
        )

        estimate = self.estimate_repo.create_estimate_with_hierarchy(
            estimate=estimate,
            line_items=line_items,
            risk_factors=risk_factors
        )

        # Step 8: Audit log
        audit_logger.log(
            user_id=user_id,
            action="estimate.generated",
            resource_type="Estimate",
            resource_id=estimate.estimate_id,
            details={
                "aace_class": aace_class.value,
                "base_cost_usd": float(base_cost),
                "monte_carlo_iterations": monte_carlo_iterations
            }
        )

        return estimate
```
</details>

[Your tool - provide implementation skeleton for 1-2 core services]

---

## 6. Repository Layer [SHARED PATTERN]

### 6.1 Repository Pattern

**All repositories follow this pattern** [DO NOT MODIFY]:

```python
from sqlalchemy.orm import Session
from apex.models.database import Project
from apex.utils.errors import Forbidden, NotFound
import uuid

class ProjectRepository:
    """Data access for Project entity with authorization checks."""

    def __init__(self, db: Session):
        self.db = db  # NEVER create SessionLocal() directly

    def create(self, project: Project, user_id: uuid.UUID) -> Project:
        """Create project and grant creator full access."""
        self.db.add(project)
        self.db.flush()  # Get project_id for ProjectAccess

        # Grant creator Estimator role
        access = ProjectAccess(
            user_id=user_id,
            project_id=project.project_id,
            role_id=self._get_role_id("Estimator"),
            granted_by=user_id
        )
        self.db.add(access)
        # Commit handled by get_db() dependency
        return project

    def get_with_access_check(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        required_permission: str
    ) -> Project:
        """Get project if user has required permission."""
        project = self.db.query(Project).filter(Project.project_id == project_id).first()
        if not project:
            raise NotFound(f"Project {project_id} not found")

        # Check ProjectAccess
        access = self.db.query(ProjectAccess).filter(
            ProjectAccess.user_id == user_id,
            ProjectAccess.project_id == project_id
        ).join(AppRole).first()

        if not access:
            raise Forbidden(f"User {user_id} has no access to project {project_id}")

        permissions = json.loads(access.role.permissions)
        if required_permission not in permissions:
            raise Forbidden(f"User lacks permission: {required_permission}")

        return project
```

### 6.2 [TOOL-SPECIFIC Repositories]

**[List your domain repositories and unique methods]**

Example (APEX):
- `EstimateRepository.create_estimate_with_hierarchy()` - Atomic persist of estimate + line items + risk factors with parent/child linking
- `RiskFactorRepository.get_by_estimate()` - Fetch all risk factors for Monte Carlo re-run

[Your tool]:
- `[Repository].[method_name]()` - [Description]

---

## 7. Testing Strategy

### 7.1 Test Coverage Requirements [SHARED PATTERN - DO NOT MODIFY]

| Test Type | Coverage Target | Purpose |
|-----------|-----------------|---------|
| **Unit Tests** | ≥80% | Isolate service/repository logic, mock dependencies |
| **Integration Tests** | ≥70% | API endpoints with real DB (in-memory SQLite for speed) |
| **Azure Service Mocks** | 100% of Azure calls | Avoid hitting live services in tests |
| **Regression Tests** | All bug fixes | Prevent re-occurrence of fixed issues |

### 7.2 Test Structure [SHARED PATTERN]

```
tests/
├── fixtures/
│   ├── azure_mocks.py          # Mock Azure clients (OpenAI, Blob, Document Intelligence)
│   ├── database_fixtures.py    # SQLAlchemy test DB setup
│   └── sample_data.py          # Reusable test data (projects, documents, users)
│
├── unit/
│   ├── test_[service_1].py     # [TOOL-SPECIFIC service tests]
│   ├── test_[service_2].py
│   └── test_risk_analysis.py   # Example: Deterministic Monte Carlo tests with seed=42
│
└── integration/
    ├── test_projects_api.py    # Project CRUD endpoints
    ├── test_documents_api.py   # Document upload, parsing, validation
    └── test_[domain]_api.py    # [TOOL-SPECIFIC endpoint tests]
```

### 7.3 Sample Test Cases [TOOL-SPECIFIC]

**[Provide 2-3 example test cases]**

<details>
<summary>Example (APEX - Risk Analysis Test)</summary>

```python
# tests/unit/test_risk_analysis.py

import pytest
from apex.services.risk_analysis import RiskAnalysisService, TriangularDistribution
from decimal import Decimal

def test_monte_carlo_triangular_distribution_deterministic():
    """Test Monte Carlo with known triangular distribution (deterministic seed)."""
    service = RiskAnalysisService()

    # Define simple triangular distribution: min=100, mode=150, max=200
    dist = TriangularDistribution(
        line_item_id="test-item",
        parameter="total_cost",
        min_value=Decimal("100.00"),
        mode_value=Decimal("150.00"),
        max_value=Decimal("200.00")
    )

    result = service.run_simulation(
        line_items=[],  # Not needed for this test
        risk_factors=[dist],
        iterations=10000,
        random_seed=42  # Deterministic for repeatability
    )

    # Expected values for triangular(100, 150, 200):
    # Mean ≈ (100 + 150 + 200) / 3 = 150
    # P50 ≈ 147-153 (median slightly left of mode for triangular)
    # P80 ≈ 175
    # P95 ≈ 190

    assert 145 <= result.p50 <= 155, f"P50 {result.p50} outside expected range"
    assert 170 <= result.p80 <= 180, f"P80 {result.p80} outside expected range"
    assert 185 <= result.p95 <= 195, f"P95 {result.p95} outside expected range"

def test_monte_carlo_latin_hypercube_sampling():
    """Verify LHS produces better convergence than naive random sampling."""
    service = RiskAnalysisService()

    dist = TriangularDistribution(
        line_item_id="test-item",
        parameter="total_cost",
        min_value=Decimal("1000"),
        mode_value=Decimal("1500"),
        max_value=Decimal("2000")
    )

    # Run with LHS
    result_lhs = service.run_simulation([],  [dist], iterations=1000, random_seed=42, use_lhs=True)

    # Run with naive random
    result_random = service.run_simulation([], [dist], iterations=1000, random_seed=42, use_lhs=False)

    # LHS should have lower variance in repeated runs (better stratification)
    # This is a simplified check - real validation would compare multiple runs
    assert result_lhs.p50 is not None
    assert result_random.p50 is not None
```
</details>

[Your tool - provide 2-3 representative test cases]

---

## 8. Deployment and Operations

### 8.1 Infrastructure as Code [SHARED PATTERN - DO NOT MODIFY]

**Bicep Template Structure**:
```
infra/
├── main.bicep                  # Orchestrator (imports all modules)
├── modules/
│   ├── container-app.bicep     # Azure Container Apps
│   ├── sql-database.bicep      # Azure SQL Database
│   ├── blob-storage.bicep      # Azure Blob Storage
│   ├── openai.bicep            # Azure OpenAI
│   ├── document-intelligence.bicep # Azure AI Document Intelligence
│   ├── key-vault.bicep         # Azure Key Vault
│   └── vnet.bicep              # Virtual Network + Private Endpoints
└── parameters/
    ├── dev.bicepparam          # Development environment
    ├── staging.bicepparam      # Staging environment
    └── production.bicepparam   # Production environment
```

**Deployment Command**:
```bash
# Deploy to development
az deployment group create \
  --resource-group rg-[tool-name]-dev \
  --template-file infra/main.bicep \
  --parameters infra/parameters/dev.bicepparam

# Deploy to production (with approval)
az deployment group create \
  --resource-group rg-[tool-name]-prod \
  --template-file infra/main.bicep \
  --parameters infra/parameters/production.bicepparam
```

### 8.2 CI/CD Pipeline [SHARED PATTERN - DO NOT MODIFY]

**GitHub Actions Workflow** (`.github/workflows/ci-cd.yml`):

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: '3.11'
  AZURE_RESOURCE_GROUP_DEV: 'rg-[tool-name]-dev'
  AZURE_RESOURCE_GROUP_PROD: 'rg-[tool-name]-prod'

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: pip install -e .

      - name: Run black
        run: black src/ tests/ --check --line-length 100

      - name: Run isort
        run: isort src/ tests/ --check-only --profile black

      - name: Run flake8
        run: flake8 src/ tests/

      - name: Run bandit (security scan)
        run: bandit -r src/ -ll -f txt

      - name: Run pytest
        run: |
          pytest tests/ \
            --cov=src \
            --cov-report=xml \
            --cov-report=term-missing \
            --cov-fail-under=80

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3

  deploy-dev:
    needs: lint-and-test
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS_DEV }}

      - name: Deploy Infrastructure
        run: |
          az deployment group create \
            --resource-group ${{ env.AZURE_RESOURCE_GROUP_DEV }} \
            --template-file infra/main.bicep \
            --parameters infra/parameters/dev.bicepparam

      - name: Build and Push Docker Image
        run: |
          docker build -t ${{ secrets.ACR_NAME }}.azurecr.io/[tool-name]:${{ github.sha }} .
          az acr login --name ${{ secrets.ACR_NAME }}
          docker push ${{ secrets.ACR_NAME }}.azurecr.io/[tool-name]:${{ github.sha }}

      - name: Update Container App
        run: |
          az containerapp update \
            --name ca-[tool-name]-dev \
            --resource-group ${{ env.AZURE_RESOURCE_GROUP_DEV }} \
            --image ${{ secrets.ACR_NAME }}.azurecr.io/[tool-name]:${{ github.sha }}

  deploy-production:
    needs: lint-and-test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval
    steps:
      # Similar to deploy-dev but with production parameters
```

### 8.3 Monitoring and Alerts [TOOL-SPECIFIC]

**Application Insights Queries** [Define your key monitoring queries]:

<details>
<summary>Example (APEX)</summary>

```kusto
// LLM Cost by Operation Type (last 7 days)
customMetrics
| where timestamp > ago(7d)
| where name == "LLM_CALL"
| extend operation = tostring(customDimensions.operation)
| extend cost_usd = todouble(customDimensions.cost_usd)
| summarize TotalCost = sum(cost_usd), CallCount = count() by operation
| order by TotalCost desc

// Estimate Generation Performance (P95 latency)
requests
| where timestamp > ago(24h)
| where name == "POST /api/v1/estimates"
| summarize P95_Duration_ms = percentile(duration, 95) by bin(timestamp, 1h)
| render timechart

// Failed Document Validation Rate
customEvents
| where timestamp > ago(7d)
| where name == "document.validation_complete"
| extend status = tostring(customDimensions.validation_status)
| summarize Total = count(), Failed = countif(status == "INVALID") by bin(timestamp, 1d)
| extend FailureRate = (Failed * 100.0) / Total
| render timechart
```
</details>

[Your tool - define 3-5 key monitoring queries]

### 8.4 Runbook [SHARED PATTERN]

See **`DEPLOYMENT_OPERATIONS_GUIDE.md`** for complete 30-step deployment checklist and operational procedures, including:

- Pre-deployment validation
- Database migration procedures
- Blue-green deployment process
- Smoke testing checklist
- Rollback procedures
- Disaster recovery runbook
- Common troubleshooting scenarios

---

## 9. Security and Compliance

### 9.1 Threat Model [TOOL-SPECIFIC]

**[Identify threats specific to your tool's data and workflows]**

<details>
<summary>Example (APEX)</summary>

| Threat | Attack Vector | Mitigation | Residual Risk |
|--------|---------------|------------|---------------|
| **Unauthorized Estimate Access** | JWT token theft, session hijacking | Azure AD JWT + ProjectAccess checks, token expiry | LOW |
| **Cost Data Exfiltration** | Blob Storage public exposure | Private Endpoints only, no public access | LOW |
| **LLM Prompt Injection** | Malicious text in uploaded documents | Prompt injection detection, content filtering | MEDIUM |
| **Bid Data Leakage to LLM Provider** | Azure OpenAI logs retention | Private Endpoint, 90-day log retention, no prompt logging | LOW |
| **SQL Injection** | Malicious input to API endpoints | SQLAlchemy ORM (no raw SQL), Pydantic validation | LOW |
</details>

[Your tool]:

| Threat | Attack Vector | Mitigation | Residual Risk |
|--------|---------------|------------|---------------|
| [Threat 1] | [How it could occur] | [Controls in place] | [LOW/MEDIUM/HIGH] |
| [Threat 2] | [How it could occur] | [Controls in place] | [LOW/MEDIUM/HIGH] |

### 9.2 Compliance Requirements [TOOL-SPECIFIC]

**[Document regulatory and industry compliance needs]**

Example (APEX):
- **ISO-NE Compliance**: 7-year audit trail for all estimates
- **NERC CIP**: Critical infrastructure protection (if applicable)
- **SOX**: Financial data integrity (cost estimates used for budget forecasting)

[Your tool]:
- **[Regulation 1]**: [Requirement and implementation]
- **[Regulation 2]**: [Requirement and implementation]

### 9.3 Data Classification [TOOL-SPECIFIC]

**[Classify data sensitivity levels]**

Example (APEX):
| Data Type | Classification | Rationale | Protection |
|-----------|----------------|-----------|------------|
| Cost Estimates | HIGHLY SENSITIVE | Competitive advantage, bid data | Private Endpoints, TDE, RBAC |
| Engineering Drawings | INTERNAL USE | Proprietary utility designs | Blob Storage encryption, access logs |
| User Emails | PII | Personal identifiable information | TDE, limited retention |
| LLM Prompts | CONFIDENTIAL | May contain cost/bid data | NOT persisted, 90-day Azure logs |

[Your tool]:
| Data Type | Classification | Rationale | Protection |
|-----------|----------------|-----------|------------|
| [Data 1] | [Level] | [Why sensitive] | [Controls] |
| [Data 2] | [Level] | [Why sensitive] | [Controls] |

---

## 10. Roadmap and Future Enhancements

### 10.1 Phase 2 Features (6-12 months)

**[TOOL-SPECIFIC - Define next phase of functionality]**

Example (APEX):
- **Web UI**: React + TypeScript frontend with estimator dashboard
- **ERP Integration**: Sync cost codes and unit prices from enterprise ERP system
- **Collaborative Workflows**: Multi-estimator review and approval processes
- **Advanced Risk Models**: Correlation matrices for complex project dependencies
- **Predictive Analytics**: ML model for estimate accuracy prediction based on historical data

[Your tool]:
- **[Feature 1]**: [Description and business value]
- **[Feature 2]**: [Description and business value]

### 10.2 Technical Debt and Known Issues

**[Document technical debt items for future refactoring]**

Example (APEX):
- **Monte Carlo Performance**: Current 10K iterations take ~15s; investigate GPU acceleration for 100K+ iterations
- **Document Parser Scalability**: Azure DI polling pattern inefficient for >200 page documents; consider batch processing
- **Cost Code Sync**: Manual CSV import from cost database; needs automated ETL pipeline

[Your tool]:
- **[Debt Item 1]**: [Description, impact, proposed solution]
- **[Debt Item 2]**: [Description, impact, proposed solution]

### 10.3 Shared Library Evolution

**Dependencies on Shared Libraries**:
- **estimating-ai-core**: Currently v1.0.0, expect v2.0.0 in Q3 2025 with multi-model support (GPT-4, Claude, Gemini)
- **estimating-connectors**: Currently v0.5.0, v1.0.0 blocked on ERP vendor API access
- **estimating-security**: v1.0.0 stable, security patches as needed

**Upgrade Strategy**:
- Minor versions: Recommended upgrade within 3 months
- Major versions: Required upgrade within 6 months with migration guide
- Security patches: Mandatory within 2 weeks

---

## 11. Appendices

### Appendix A: Glossary [TOOL-SPECIFIC]

**[Define domain-specific terms]**

Example (APEX):
- **AACE**: Association for the Advancement of Cost Engineering (industry standard for estimate classification)
- **CBS**: Cost Breakdown Structure (hierarchical decomposition of project costs)
- **LHS**: Latin Hypercube Sampling (stratified sampling method for Monte Carlo)
- **WBS**: Work Breakdown Structure (hierarchical decomposition of project scope)
- **P50/P80/P95**: Percentile cost values from Monte Carlo (50th, 80th, 95th percentile)

[Your tool - define 10-15 key terms]

### Appendix B: API Reference

**Full API documentation available at**: `http://localhost:8000/docs` (Swagger UI when running locally)

### Appendix C: Database Schema Diagram

[Include ERD showing all tables and relationships]

### Appendix D: Cost Estimation

**Development Costs** (one-time):
- [Initial development: $X]
- [Infrastructure setup: $X]
- [Testing and QA: $X]

**Operational Costs** (monthly):
| Resource | SKU | Estimated Cost |
|----------|-----|----------------|
| Container Apps (dev) | Consumption | ~$50 |
| Azure SQL (dev) | Basic (2 vCore) | ~$150 |
| Blob Storage (dev) | Standard ZRS | ~$10 |
| Azure OpenAI (shared) | Standard GPT-4 | ~$200 (allocated across tools) |
| **Total Development** | | **~$410/month** |
| Container Apps (prod) | Consumption (auto-scale) | ~$300 |
| Azure SQL (prod) | Business Critical (8 vCore) | ~$2000 |
| Blob Storage (prod) | Standard ZRS | ~$50 |
| **Total Production** | | **~$2550/month** |

---

**Document Version**: 1.0
**Last Updated**: [YYYY-MM-DD]
**Maintained By**: [Tool Team Name]
**Next Review**: [Quarterly date]
**Production Readiness Score**: [After IT review]
