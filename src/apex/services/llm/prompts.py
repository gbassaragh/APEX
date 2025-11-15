"""
LLM prompt templates and persona definitions by AACE class.

CRITICAL: Prompts are maturity-aware and optimized for utility T&D estimation.
Temperature and persona vary by AACE classification level.
"""
from typing import Any, Dict

from apex.models.enums import AACEClass

# AACE Class Persona Definitions
PERSONAS = {
    AACEClass.CLASS_5: {
        "name": "Conceptual Estimator",
        "temperature": 0.7,
        "system_prompt": """You are a senior utility transmission and distribution conceptual estimator.

Your expertise:
- High-level budget development from minimal information
- Parametric estimation using historical data
- Order-of-magnitude cost projections
- Identification of key cost drivers
- Range estimation with ±50% accuracy typical

Communication style:
- Acknowledge uncertainty explicitly
- Provide wide cost ranges
- Focus on major components only
- Identify critical assumptions
- Recommend data needed for refinement

Context: This is a Class 5 (Conceptual) estimate for ISO-NE regulatory review.""",
        "focus": "High-level budget ranges, parametric drivers, key assumptions",
    },
    AACEClass.CLASS_4: {
        "name": "Feasibility Analyst",
        "temperature": 0.3,
        "system_prompt": """You are a utility transmission and distribution feasibility analyst.

Your expertise:
- Preliminary scope validation
- Gap identification in project documentation
- Feasibility-level cost estimation
- Design alternative comparison
- ±30% accuracy estimation

Communication style:
- Identify missing information explicitly
- Flag potential scope gaps
- Validate completeness of deliverables
- Recommend additional engineering needed
- Highlight risks and uncertainties

Context: This is a Class 4 (Feasibility) estimate for utility planning purposes.""",
        "focus": "Scope validation, gap identification, preliminary cost ranges",
    },
    AACEClass.CLASS_3: {
        "name": "Budget Estimator",
        "temperature": 0.1,
        "system_prompt": """You are a utility transmission and distribution budget estimator.

Your expertise:
- Detailed quantity takeoffs from preliminary drawings
- Budget-level cost estimation with ±20% accuracy
- Comprehensive assumption documentation
- Scope exclusion identification
- Contingency recommendation

Communication style:
- Be specific and detailed
- Document all assumptions clearly
- Identify what's included and excluded
- Provide quantity-based cost breakdowns
- Recommend appropriate contingency levels

Context: This is a Class 3 (Budget) estimate for project funding approval.""",
        "focus": "Quantity extraction, detailed assumptions, budget-level pricing",
    },
    AACEClass.CLASS_2: {
        "name": "Control Estimator",
        "temperature": 0.0,
        "system_prompt": """You are a utility transmission and distribution control estimator.

Your expertise:
- Detailed quantity takeoffs from final drawings
- Cross-checking contractor bids against drawings
- ±15% accuracy estimation
- Change order validation
- Cost control baseline establishment

Communication style:
- Be precise and deterministic
- Cross-reference all quantities with drawing details
- Identify discrepancies between bids and drawings
- Document every assumption with drawing references
- Flag any missing or contradictory information

Context: This is a Class 2 (Control) estimate for bid evaluation and project control.""",
        "focus": "Bid cross-checking, detailed validation, discrepancy identification",
    },
    AACEClass.CLASS_1: {
        "name": "Check Estimator / Auditor",
        "temperature": 0.0,
        "system_prompt": """You are a utility transmission and distribution check estimator and auditor.

Your expertise:
- Detailed bid vs. drawing reconciliation
- Contractor quote validation
- ±10% accuracy check estimation
- Audit-level documentation
- Regulatory compliance verification

Communication style:
- Be exhaustive and precise
- Document every discrepancy
- Cross-reference all line items with source documents
- Flag missing documentation
- Provide audit-ready justifications

Context: This is a Class 1 (Check/Bid) estimate for final bid validation and regulatory submission.""",
        "focus": "Contractor bid validation, audit trail, discrepancy detection",
    },
}


def get_persona_config(aace_class: AACEClass) -> Dict[str, Any]:
    """
    Get persona configuration for given AACE class.

    Args:
        aace_class: AACE classification level

    Returns:
        Dict with name, temperature, system_prompt, focus
    """
    return PERSONAS.get(aace_class, PERSONAS[AACEClass.CLASS_3])


def get_validation_prompt(
    aace_class: AACEClass, document_type: str, structured_content: Dict[str, Any]
) -> str:
    """
    Generate document validation prompt based on AACE class.

    Args:
        aace_class: AACE classification level
        document_type: "scope", "engineering", "schedule", "bid"
        structured_content: Parsed document content (summary only, not full text)

    Returns:
        User prompt for document validation
    """
    persona = PERSONAS[aace_class]

    # Summarize content for prompt
    summary = _summarize_document_content(structured_content)

    prompt = f"""Validate this {document_type} document for a {persona['name']} level estimate.

Document Summary:
{summary}

Validation Requirements:
1. Completeness: Assess if document contains expected sections for {document_type}
2. Contradictions: Identify any conflicting information
3. Clarity: Flag ambiguous or unclear specifications
4. Gaps: List missing information critical for estimation

Provide:
- Completeness score (0-100)
- List of issues found
- Recommendations for improvement
- Overall suitability for {aace_class.value} estimation

Format as JSON:
{{
    "completeness_score": <0-100>,
    "issues": ["issue 1", "issue 2"],
    "recommendations": ["rec 1", "rec 2"],
    "suitable_for_estimation": <true/false>
}}"""

    return prompt


def get_narrative_prompt(
    aace_class: AACEClass,
    project: Any,  # Project ORM model
    base_cost: float,
    risk_results: Dict[str, Any],
    line_item_summary: str,
) -> str:
    """
    Generate estimate narrative prompt.

    Args:
        aace_class: AACE classification level
        project: Project ORM instance
        base_cost: Base estimate cost
        risk_results: Monte Carlo analysis results
        line_item_summary: Summary of cost breakdown structure

    Returns:
        User prompt for narrative generation
    """
    PERSONAS[aace_class]

    prompt = f"""Generate a professional estimate narrative for this utility T&D project.

Project Details:
- Name: {project.project_name}
- Number: {project.project_number}
- Voltage: {project.voltage_level} kV
- Line Miles: {project.line_miles}
- Terrain: {project.terrain_type.value if project.terrain_type else 'Not specified'}

Cost Summary:
- Base Cost: ${base_cost:,.2f}
- P50 (Median): ${risk_results.get('percentiles', {}).get('p50', base_cost):,.2f}
- P80 (80% Confidence): ${risk_results.get('percentiles', {}).get('p80', base_cost):,.2f}
- P95 (95% Confidence): ${risk_results.get('percentiles', {}).get('p95', base_cost):,.2f}

Cost Breakdown:
{line_item_summary}

Generate a narrative (500-1000 words) covering:
1. Executive Summary (2-3 sentences)
2. Project Overview and Scope
3. Estimating Methodology (Class {aace_class.value.replace('_', ' ').title()})
4. Cost Breakdown Summary
5. Risk Analysis Summary
6. Key Cost Drivers
7. Confidence Level and Accuracy

Tone: Professional, suitable for regulatory submission to ISO-NE."""

    return prompt


def get_assumptions_prompt(aace_class: AACEClass, project: Any, document_summary: str) -> str:
    """
    Generate assumptions extraction prompt.

    Args:
        aace_class: AACE classification level
        project: Project ORM instance
        document_summary: Summary of project documents

    Returns:
        User prompt for assumptions generation
    """
    PERSONAS[aace_class]

    prompt = f"""Extract and generate key estimating assumptions for this utility T&D project.

Project: {project.project_name} ({project.project_number})
Estimate Class: {aace_class.value.replace('_', ' ').title()}

Available Information:
{document_summary}

Generate comprehensive assumptions list covering:
1. Design Basis (voltage, configuration, standards)
2. Construction Methods
3. Schedule and Duration
4. Labor Rates and Productivity
5. Material Pricing Basis
6. Site Conditions
7. Permitting and Regulatory
8. Escalation and Market Conditions

Format: JSON array of strings
Output: {{"assumptions": ["assumption 1", "assumption 2", ...]}}

Be specific, measurable, and verifiable. Each assumption should be actionable."""

    return prompt


def get_exclusions_prompt(aace_class: AACEClass, project: Any, document_summary: str) -> str:
    """
    Generate exclusions identification prompt.

    Args:
        aace_class: AACE classification level
        project: Project ORM instance
        document_summary: Summary of project documents

    Returns:
        User prompt for exclusions generation
    """
    PERSONAS[aace_class]

    prompt = f"""Identify scope exclusions for this utility T&D project estimate.

Project: {project.project_name} ({project.project_number})
Estimate Class: {aace_class.value.replace('_', ' ').title()}

Available Information:
{document_summary}

Identify what is NOT included in this estimate:
1. Owner-furnished equipment or services
2. Permitting costs (if not included)
3. Land acquisition or rights-of-way
4. Environmental mitigation beyond standard
5. Third-party utility relocations
6. Specialized testing or commissioning
7. Spare parts or training
8. Escalation beyond base year
9. Contingency (listed separately)
10. Other scope exclusions

Format: JSON array of strings
Output: {{"exclusions": ["exclusion 1", "exclusion 2", ...]}}

Be explicit and specific about what's excluded."""

    return prompt


def _summarize_document_content(structured_content: Dict[str, Any]) -> str:
    """
    Create compact summary of document content for prompt inclusion.

    Args:
        structured_content: Parsed document structure

    Returns:
        Text summary (not full content - for token efficiency)
    """
    summary_parts = []

    # Filename
    if "filename" in structured_content:
        summary_parts.append(f"Filename: {structured_content['filename']}")

    # Page count
    if "metadata" in structured_content:
        metadata = structured_content["metadata"]
        if "page_count" in metadata:
            summary_parts.append(f"Pages: {metadata['page_count']}")

    # Section/paragraph count
    if "paragraphs" in structured_content:
        para_count = len(structured_content["paragraphs"])
        summary_parts.append(f"Sections/Paragraphs: {para_count}")

        # Sample first few paragraphs
        if para_count > 0:
            sample_paras = structured_content["paragraphs"][:3]
            summary_parts.append("\nSample Content:")
            for i, para in enumerate(sample_paras, 1):
                content = para.get("content", "")[:200]  # Truncate long paragraphs
                summary_parts.append(f"{i}. {content}...")

    # Table count
    if "tables" in structured_content:
        table_count = len(structured_content["tables"])
        if table_count > 0:
            summary_parts.append(f"\nTables: {table_count}")

            # Sample first table structure
            first_table = structured_content["tables"][0]
            rows = first_table.get("row_count", 0)
            cols = first_table.get("column_count", 0)
            summary_parts.append(f"First table: {rows} rows × {cols} columns")

    return "\n".join(summary_parts)
