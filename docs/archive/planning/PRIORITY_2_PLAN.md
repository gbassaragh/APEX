# APEX Phase 2 Priority 2+ Implementation Plan

## Services Layer - Core Business Logic

### Status: Priority 0 ✅ | Priority 1 ✅ | Priority 2+ 🔄

---

## Implementation Order

### Phase 2A: LLM Layer (Foundation for Estimate Generation)
1. **services/llm/prompts.py** - Prompt templates by AACE class
2. **services/llm/validators.py** - Response validation logic
3. **services/llm/orchestrator.py** - Maturity-aware routing engine

### Phase 2B: Analysis Services (Can be parallel)
4. **Review services/aace_classifier.py** - Enhance if needed
5. **Review services/risk_analysis.py** - Verify Iman-Conover implementation

### Phase 2C: Cost Engine
6. **services/cost_database.py** - CBS/WBS builder with temporary parent refs

### Phase 2D: Main Orchestration
7. **services/estimate_generator.py** - Full estimation workflow

---

## Service Specifications

### 1. services/llm/prompts.py

**Purpose**: AACE class-specific system and user prompt templates

**Key Components**:
```python
# Persona definitions by AACE class
PERSONAS = {
    AACEClass.CLASS_5: {
        "name": "Conceptual Estimator",
        "system_prompt": "...",
        "temperature": 0.7,
        "focus": "High-level budget ranges, parametric drivers"
    },
    AACEClass.CLASS_4: {
        "name": "Feasibility Analyst",
        "system_prompt": "...",
        "temperature": 0.3,
        "focus": "Scope validation, gap identification"
    },
    AACEClass.CLASS_3: {
        "name": "Budget Estimator",
        "system_prompt": "...",
        "temperature": 0.1,
        "focus": "Quantity extraction, detailed assumptions"
    },
    AACEClass.CLASS_2: {
        "name": "Control Estimator",
        "system_prompt": "...",
        "temperature": 0.0,
        "focus": "Contractor bid cross-checking"
    },
    AACEClass.CLASS_1: {
        "name": "Check Estimator / Auditor",
        "system_prompt": "...",
        "temperature": 0.0,
        "focus": "Bid vs drawings discrepancy detection"
    }
}

# Task-specific templates
def get_validation_prompt(aace_class: AACEClass, doc_type: str) -> str
def get_narrative_prompt(aace_class: AACEClass, estimate_context: Dict) -> str
def get_assumptions_prompt(aace_class: AACEClass, project_data: Dict) -> str
def get_exclusions_prompt(aace_class: AACEClass, project_data: Dict) -> str
```

**Dependencies**: None
**Integration**: Used by orchestrator.py

---

### 2. services/llm/validators.py

**Purpose**: Validate LLM responses for structure and content quality

**Key Methods**:
```python
def validate_narrative_response(response: str, min_length: int = 100) -> bool
def validate_assumptions_list(assumptions: List[str]) -> List[str]  # Returns cleaned list
def validate_exclusions_list(exclusions: List[str]) -> List[str]
def extract_json_from_response(response: str) -> Dict[str, Any]  # For structured outputs
def check_hallucination_markers(response: str) -> bool  # Detect "I don't know", etc.
```

**Dependencies**: None
**Integration**: Used by orchestrator.py

---

### 3. services/llm/orchestrator.py

**Purpose**: Maturity-aware LLM orchestration with AACE class routing

**Key Class**:
```python
class LLMOrchestrator:
    def __init__(self, config: Config):
        self.config = config
        self.client = None  # Azure OpenAI client
        self.encoder = tiktoken.encoding_for_model("gpt-4")
        self.max_context_tokens = config.LLM_MAX_CONTEXT_TOKENS
        self.response_buffer_tokens = config.LLM_RESPONSE_BUFFER_TOKENS

    async def _get_client(self) -> AsyncAzureOpenAI:
        """Lazy initialization of Azure OpenAI client"""

    async def generate_narrative(
        self,
        aace_class: AACEClass,
        project: Project,
        estimate_data: Dict[str, Any],
        base_cost: Decimal,
        risk_results: Dict[str, Any]
    ) -> str:
        """Generate estimate narrative based on AACE class"""

    async def generate_assumptions(
        self,
        aace_class: AACEClass,
        project: Project,
        documents: List[Document]
    ) -> List[str]:
        """Extract/generate assumptions from project data"""

    async def generate_exclusions(
        self,
        aace_class: AACEClass,
        project: Project,
        documents: List[Document]
    ) -> List[str]:
        """Identify scope exclusions"""

    async def validate_document(
        self,
        aace_class: AACEClass,
        document_type: str,
        structured_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """LLM-based document validation (completeness, contradictions)"""

    def _prepare_messages(
        self,
        system_prompt: str,
        user_prompt: str,
        context_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Build message list with token management"""

    def _truncate_context(
        self,
        context_data: Dict[str, Any],
        available_tokens: int
    ) -> Dict[str, Any]:
        """Smart truncation preserving priority data"""

    def _estimate_tokens(self, text: str) -> int:
        """Token counting using tiktoken"""
```

**Dependencies**:
- azure.auth (get_azure_credential)
- llm/prompts.py
- llm/validators.py
- openai SDK (AsyncAzureOpenAI)
- tiktoken

**Integration**:
- Called by estimate_generator.py
- Uses AACE class from aace_classifier.py

**Critical Notes**:
- MUST use tiktoken for accurate token counting
- Token budget: max_context - response_buffer
- Smart truncation: preserve scope/quantities, drop appendices
- Audit trail: log model version, tokens used → AuditLog

---

### 4. services/aace_classifier.py (Review/Enhance)

**Check List**:
- ✅ Takes engineering maturity %, completeness score, deliverables
- ✅ Returns AACEClass enum, accuracy range, justification, recommendations
- ✅ Uses maturity thresholds (e.g., >90% = Class 1, 60-90% = Class 2, etc.)
- ⚠️ Verify decision logic matches AACE standards
- ⚠️ Ensure recommendations are actionable

**Expected Signature**:
```python
class AACEClassifier:
    def classify(
        self,
        engineering_maturity_percent: float,
        scope_completeness_percent: float,
        available_deliverables: List[str]
    ) -> Dict[str, Any]:
        """
        Returns:
        {
            "aace_class": AACEClass.CLASS_3,
            "accuracy_range": "±20%",
            "justification": [
                "Engineering 65% complete",
                "Preliminary drawings available",
                "No bid data yet"
            ],
            "recommendations": [
                "Complete preliminary design for Class 2",
                "Obtain contractor quotes to improve accuracy"
            ]
        }
        """
```

---

### 5. services/risk_analysis.py (Review/Enhance)

**Check List**:
- ✅ Latin Hypercube Sampling (scipy.stats.qmc)
- ✅ Multiple distributions (triangular, normal, uniform, lognormal, PERT)
- ⚠️ Iman-Conover correlation implementation (HIGH-RISK - must validate)
- ✅ Spearman rank correlations for sensitivity
- ⚠️ Verify NO mcerp usage (prohibited)
- ⚠️ Deterministic seed support for testing

**Expected Signature**:
```python
class MonteCarloRiskAnalyzer:
    def run_analysis(
        self,
        base_cost: float,
        risk_factors: Dict[str, RiskFactor],
        correlation_matrix: Optional[np.ndarray] = None,
        confidence_levels: List[float] = [0.50, 0.80, 0.95],
        iterations: int = 10000,
        random_seed: int = 42
    ) -> Dict[str, Any]:
        """
        Returns:
        {
            "base_cost": 1000000.0,
            "mean_cost": 1150000.0,
            "std_dev": 85000.0,
            "percentiles": {"p50": 1140000, "p80": 1220000, "p95": 1310000},
            "min_cost": 980000.0,
            "max_cost": 1450000.0,
            "iterations": 10000,
            "risk_factors_applied": ["labor_escalation", "material_volatility"],
            "sensitivities": {
                "labor_escalation": 0.62,  # Spearman correlation
                "material_volatility": 0.41
            }
        }
        """
```

**Critical Notes**:
- Iman-Conover MUST be validated against @RISK or similar tool before production
- _transform_samples() must correctly implement all distribution types
- All numpy operations must use deterministic seed

---

### 6. services/cost_database.py (NEW)

**Purpose**: Compute base cost and build CBS/WBS hierarchy with temporary parent refs

**Key Class**:
```python
class CostDatabaseService:
    def __init__(self, db: Session):
        self.db = db

    def compute_base_cost(
        self,
        project: Project,
        documents: List[Document],
        cost_code_map: Dict[str, CostCode]
    ) -> Tuple[Decimal, List[EstimateLineItem]]:
        """
        Main entry point.

        Returns:
            (base_cost, line_items)

        where line_items is flat list with:
        - wbs_code set (e.g., "10", "10-100", "10-110")
        - _temp_parent_ref attribute for parent linking
        - parent_line_item_id still None (linked in repository)
        """

    def _extract_quantities(
        self,
        project: Project,
        documents: List[Document]
    ) -> Dict[str, Any]:
        """
        Extract quantity takeoffs from parsed documents.

        For MVP: Simple extraction from structured document data
        For Production: LLM-assisted quantity extraction
        """

    def _map_to_cost_items(
        self,
        project: Project,
        quantities: Dict[str, Any],
        cost_code_map: Dict[str, CostCode]
    ) -> List[Dict[str, Any]]:
        """Map quantities to cost codes (e.g., RSMeans)"""

    def _lookup_unit_costs(
        self,
        cost_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Look up unit costs from cost database.

        For MVP: Hardcoded sample costs
        For Production: RSMeans API integration or database lookup
        """

    def _apply_adjustments(
        self,
        project: Project,
        cost_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply location factors, market conditions, escalation.

        Based on:
        - project.terrain_type (multiplier)
        - project.voltage_level (complexity factor)
        - Geographic location (if available)
        """

    def _build_cbs_hierarchy(
        self,
        cost_items: List[Dict[str, Any]]
    ) -> Tuple[Decimal, List[EstimateLineItem]]:
        """
        Build Cost Breakdown Structure with parent/child relationships.

        Process:
        1. Group items by WBS code prefix
        2. Create summary rows (parents) with totals
        3. Create detail rows (children) with quantities
        4. Set wbs_code on all items
        5. Set _temp_parent_ref on children (not parent_line_item_id yet)
        6. Return total cost + flat list of EstimateLineItem entities

        Example hierarchy:
        - "10: Transmission Line" (parent, summary)
          - "10-100: Tangent Structures" (child, detail)
          - "10-200: Dead-End Structures" (child, detail)
        - "20: Conductor & Hardware" (parent, summary)
          - "20-100: ACSR Conductor" (child, detail)
        """
```

**Dependencies**:
- database.connection (Session)
- models.database (Project, Document, EstimateLineItem, CostCode)
- Decimal for cost calculations

**Integration**:
- Called by estimate_generator.py
- Uses parsed documents from document_parser.py

**Critical Notes**:
- All costs MUST use Decimal, not float
- Parent GUID linking happens in repository, not here
- Temporary parent reference pattern: `line_item._temp_parent_ref = "10"` for child "10-100"
- WBS codes must be deterministic for parent mapping

---

### 7. services/estimate_generator.py (NEW)

**Purpose**: Main orchestration service coordinating all estimation steps

**Key Class**:
```python
class EstimateGenerator:
    def __init__(
        self,
        project_repo: ProjectRepository,
        document_repo: DocumentRepository,
        estimate_repo: EstimateRepository,
        audit_repo: AuditRepository,
        llm_orchestrator: LLMOrchestrator,
        risk_analyzer: MonteCarloRiskAnalyzer,
        aace_classifier: AACEClassifier,
        cost_db_service: CostDatabaseService
    ):
        # Dependency injection of all required services

    async def generate_estimate(
        self,
        db: Session,
        project_id: UUID,
        risk_factors_dto: List[Dict[str, Any]],
        confidence_level: float,
        monte_carlo_iterations: int,
        user: User
    ) -> Estimate:
        """
        Full estimation workflow:

        1. Load project & documents (with access check)
        2. Derive completeness + maturity metrics
        3. Classify AACE class (AACEClassifier)
        4. Compute base cost + line items (CostDatabaseService)
        5. Build RiskFactor objects from DTO
        6. Run Monte Carlo analysis (MonteCarloRiskAnalyzer)
        7. Compute contingency % from P_target vs base
        8. Generate narrative (LLMOrchestrator)
        9. Generate assumptions (LLMOrchestrator)
        10. Generate exclusions (LLMOrchestrator)
        11. Build Estimate + children ORM entities
        12. Persist via repository (single transaction)
        13. Create AuditLog entry
        14. Return Estimate

        Raises:
            BusinessRuleViolation: Access denied, validation failures
            Various Azure/LLM exceptions
        """
```

**Dependencies**:
- All repositories (project, document, estimate, audit)
- All services (llm_orchestrator, risk_analyzer, aace_classifier, cost_db_service)
- models.database (Estimate, EstimateLineItem, EstimateAssumption, etc.)

**Integration**:
- Called by API endpoint (api/v1/estimates.py)
- Orchestrates all other services
- Uses database session from get_db() dependency

**Critical Notes**:
- MUST check ProjectAccess before allowing estimate generation
- Single database transaction for entire estimate graph
- Proper error handling with rollback
- Comprehensive audit logging
- Convert risk_factors_dto to RiskFactor dataclasses

---

## Implementation Strategy

### Phase 2A: LLM Layer (2-3 hours)
- Implement prompts.py with all persona definitions
- Implement validators.py with response validation
- Implement orchestrator.py with token management

### Phase 2B: Analysis Review (1 hour)
- Review aace_classifier.py for completeness
- Review risk_analysis.py for Iman-Conover correctness
- Add tests for deterministic behavior

### Phase 2C: Cost Engine (2-3 hours)
- Implement cost_database.py with CBS/WBS builder
- Create sample cost code data for testing
- Implement temporary parent reference pattern

### Phase 2D: Main Orchestration (2-3 hours)
- Implement estimate_generator.py
- Wire up all dependencies
- Create integration tests

### Total Estimated Time: 7-10 hours of focused implementation

---

## Validation Strategy

1. **Unit Tests**: Each service independently with mocks
2. **Integration Tests**: End-to-end estimate generation with test data
3. **Gemini Review**: Comprehensive code review for completeness
4. **Codex Review**: Technical validation for correctness
5. **Manual Review**: Human validation of Iman-Conover and token management

---

## Risk Areas Requiring Human Review

1. **Iman-Conover Correlation** (risk_analysis.py)
   - Validate against @RISK or similar tool
   - Test with known correlation matrices
   - Verify marginal preservation

2. **Token Management** (llm/orchestrator.py)
   - Verify truncation doesn't lose critical data
   - Test with large documents approaching limits
   - Validate tiktoken accuracy

3. **CBS Hierarchy Linking** (estimate_generator.py + repository)
   - Test parent GUID assignment in transaction
   - Verify deterministic WBS code matching
   - Ensure referential integrity

---

## Success Criteria

- ✅ All services implement specified interfaces
- ✅ All async operations use proper patterns
- ✅ All database operations use Decimal for costs
- ✅ No JSON blobs for analytical data
- ✅ Comprehensive error handling
- ✅ Full audit trail support
- ✅ Token management within limits
- ✅ Deterministic risk analysis (with seed)
- ✅ Pass Gemini + Codex reviews
- ✅ Integration tests demonstrate end-to-end flow
