# ADR 003: Maturity-Aware LLM Orchestration

**Status**: Accepted

**Date**: 2025-01-20

**Deciders**: Development Team, Product Management

---

## Context

The APEX platform generates cost estimates for transmission and distribution projects at different levels of project maturity, formalized by the AACE (Association for the Advancement of Cost Engineering) classification system:

| AACE Class | Maturity Level | Expected Accuracy | Document Quality | Use Case |
|------------|---------------|-------------------|------------------|----------|
| **Class 5** | Concept Screening | -20% to +50% | Minimal (napkin sketches) | Portfolio prioritization |
| **Class 4** | Study/Feasibility | -15% to +30% | Preliminary (scope statements) | Go/no-go decisions |
| **Class 3** | Budget Authorization | -10% to +20% | Developed (engineering drawings) | Budget approval |
| **Class 2** | Control/Bid | -5% to +15% | Detailed (contractor bids) | Project execution |
| **Class 1** | Contractor Guarantee | -3% to +10% | Comprehensive (as-builts) | Regulatory filing |

Initial implementation used a single "one-size-fits-all" LLM prompt for all estimate types, causing:

1. **Quality Mismatch**: Class 5 estimates over-analyzed sparse data, wasting tokens/time
2. **Accuracy Issues**: Class 2 estimates under-analyzed detailed bids, missing critical assumptions
3. **Cost Inefficiency**: Same temperature (0.3) used for creative (Class 5) and deterministic (Class 1) tasks
4. **User Confusion**: Generic narratives didn't reflect estimate maturity level

We needed an orchestration pattern that:
- Adapts LLM behavior to estimate maturity level
- Optimizes token usage per AACE class requirements
- Provides class-appropriate output formatting
- Maintains consistency within each class

## Decision

**We will implement a maturity-aware LLM orchestrator that routes prompts, configures parameters, and formats outputs based on AACE class.**

### Architecture Components

1. **Class-Specific Personas**: Each AACE class has a tailored system prompt
   ```python
   AACE_PERSONAS = {
       AACEClass.CLASS_5: "You are a Conceptual Estimator...",
       AACEClass.CLASS_4: "You are a Feasibility Analyst...",
       AACEClass.CLASS_3: "You are a Budget Estimator...",
       AACEClass.CLASS_2: "You are an Auditor...",
       AACEClass.CLASS_1: "You are an Auditor...",
   }
   ```

2. **Temperature Scaling**: Higher uncertainty → higher temperature
   ```python
   AACE_TEMPERATURES = {
       AACEClass.CLASS_5: 0.7,  # Creative, exploratory
       AACEClass.CLASS_4: 0.3,  # Balanced analysis
       AACEClass.CLASS_3: 0.1,  # Deterministic extraction
       AACEClass.CLASS_2: 0.0,  # Precise validation
       AACEClass.CLASS_1: 0.0,  # Exact verification
   }
   ```

3. **Token Budget Allocation**: Match budget to document complexity
   - Class 5: 2K tokens (minimal input, creative output)
   - Class 4: 4K tokens (scope validation)
   - Class 3: 8K tokens (quantity extraction)
   - Class 2/1: 16K tokens (bid cross-checking)

4. **Routing Method**: Single orchestrator with class-based dispatch
   ```python
   async def validate_document(
       self,
       aace_class: AACEClass,
       document_type: str,
       structured_content: Dict[str, Any],
   ) -> Dict[str, Any]:
       persona = AACE_PERSONAS[aace_class]
       temperature = AACE_TEMPERATURES[aace_class]

       messages = [
           {"role": "system", "content": persona},
           {"role": "user", "content": self._build_prompt(aace_class, ...)}
       ]

       response = await self.client.chat.completions.create(
           model=self.deployment,
           messages=messages,
           temperature=temperature,
           max_tokens=4000,
       )
       return self._parse_response(response, aace_class)
   ```

### Persona Design Philosophy

**Class 5 (Conceptual Estimator)**:
- Encourage range-based thinking ("$5M-$15M corridor")
- Flag missing scope as expected, not deficiencies
- Output should match feasibility study tone

**Class 4 (Feasibility Analyst)**:
- Focus on scope gaps and document completeness
- Identify missing assumptions that affect feasibility
- Balance specificity with preliminary nature

**Class 3 (Budget Estimator)**:
- Extract quantities with precision
- Validate unit costs against industry norms
- Output suitable for budget authorization packages

**Class 2/1 (Auditor)**:
- Cross-check contractor bids for discrepancies
- Validate regulatory compliance (ISO-NE requirements)
- Output must withstand regulatory scrutiny

## Alternatives Considered

### Alternative 1: Separate LLM Clients per Class
**Rejected** because:
- High code duplication (5 client implementations)
- Difficult to maintain consistent error handling
- No shared token usage tracking
- Would require 5 separate Azure OpenAI deployments

**Advantages we're giving up**:
- Cleaner separation of concerns
- Independent scaling per class
- Easier A/B testing of persona effectiveness

### Alternative 2: Fine-Tuned Models per AACE Class
**Rejected** because:
- Requires 10K+ training examples per class (don't have data)
- High cost ($thousands for training, separate deployments)
- Maintenance burden (retrain on GPT-4 updates)
- No evidence that fine-tuning outperforms prompt engineering for this task

**Advantages we're giving up**:
- Potentially better class-specific performance
- Lower per-request token usage
- Less prompt engineering complexity

**When to revisit**: If APEX processes >10K estimates/year and has labeled training data.

### Alternative 3: Ensemble of Specialized Models
Use Claude for narratives, GPT-4 for extraction, Codex for quantity calculations.

**Rejected** because:
- Increases complexity (3 vendor integrations)
- Higher latency (sequential LLM calls)
- Difficult to debug (which model caused error?)
- Vendor lock-in to multiple providers

**Advantages we're giving up**:
- Best-in-class performance per task
- Reduced dependency on single vendor
- Ability to compare model outputs for quality

## Consequences

### Positive

1. **Quality Improvement**: Estimates match expected maturity level
   - Class 5 narratives acknowledge uncertainty appropriately
   - Class 2 narratives provide regulatory-grade detail

2. **Cost Optimization**: Token usage scaled to needs
   - Class 5: ~3K tokens/estimate (vs 8K with generic prompt)
   - Class 2: ~12K tokens/estimate (vs 8K under-analyzed)

3. **User Satisfaction**: Output tone matches user expectations
   - Portfolio managers get high-level summaries (Class 5)
   - Regulatory teams get audit-ready detail (Class 2)

4. **Maintainability**: Single orchestrator easier to monitor than 5 clients

### Negative

1. **Prompt Drift Risk**: 5 personas can diverge over time
   - **Mitigation**: Regression tests validate output structure per class
   - **Mitigation**: Quarterly persona review process

2. **Temperature Tuning Complexity**: Optimal temperature may vary per document type
   - **Mitigation**: Start with AACE-based defaults, collect user feedback
   - **Future**: Per-document-type temperature overrides if needed

3. **Testing Burden**: Must validate all 5 personas × 4 document types = 20 scenarios
   - **Mitigation**: Focus regression tests on critical paths (Class 2 bids, Class 4 scopes)

### Operational Considerations

1. **Monitoring**: Track LLM performance by AACE class
   ```python
   logger.info(
       "LLM orchestrator call",
       extra={
           "aace_class": aace_class.value,
           "document_type": document_type,
           "input_tokens": prompt_tokens,
           "output_tokens": completion_tokens,
           "duration_ms": duration,
       }
   )
   ```

2. **Prompt Version Control**: Store persona prompts in database or config
   - Enables A/B testing without code deployment
   - Audit trail for regulatory compliance
   - **Future Enhancement**: Migrate from hardcoded strings to `PromptTemplate` table

3. **Fallback Strategy**: If AACE class unknown, default to Class 3
   ```python
   aace_class = aace_class or AACEClass.CLASS_3  # Conservative default
   ```

4. **Token Limit Handling**: Truncate structured_content if exceeds budget
   ```python
   content_str = json.dumps(structured_content)
   token_count = count_tokens(content_str)

   if token_count > MAX_TOKENS[aace_class]:
       # Truncate tables, keep summaries
       structured_content = truncate_preserving_structure(structured_content, MAX_TOKENS[aace_class])
   ```

## Implementation Notes

### Persona Evolution

Personas should be updated based on:
- User feedback on estimate quality
- Regulatory audit findings
- Industry standard changes (AACE updates)

**Governance Process**:
1. Product Manager proposes persona change
2. Test on 10 historical estimates (offline evaluation)
3. Deploy to staging for beta user testing
4. Rollout to production with monitoring

### Temperature Rationale

**High Temperature (0.7)**: Class 5 Conceptual
- Encourages diverse assumption generation
- Comfortable with ambiguity
- Trade accuracy for creativity

**Medium Temperature (0.3)**: Class 4 Feasibility
- Balanced between analysis and creativity
- Can flag scope gaps without over-constraining

**Low Temperature (0.1)**: Class 3 Budget
- Deterministic quantity extraction
- Minimal hallucination risk
- Predictable output structure

**Zero Temperature (0.0)**: Class 2/1 Control/Guarantee
- Reproducible results for audits
- No creative interpretation
- Strict validation only

### Cross-Validation Strategy

For Class 2 estimates, run both Auditor (temp 0.0) and Budget Estimator (temp 0.1) personas:
- Compare assumptions/exclusions lists
- Flag discrepancies for human review
- **Future Enhancement**: Automatic consensus building

## Related Decisions

- **ADR 001**: Background Jobs (estimate generation runs asynchronously)
- **Future ADR**: If implementing PromptTemplate database table

## References

- `src/apex/services/llm/orchestrator.py`: Implementation
- AACE Cost Estimate Classification System: https://www.aacei.org/
- APEX_Prompt.md: Section 10 (LLM Integration Requirements)
- Azure OpenAI Best Practices: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/system-message
