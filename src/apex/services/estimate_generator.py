"""
Main estimation workflow orchestration service.

CRITICAL: Coordinates all estimation steps in correct order with full audit trail.
Single database transaction for entire estimate graph.
MUST check ProjectAccess before allowing estimate generation.

14-Step Workflow:
1. Load project & documents
2. Check user access (ProjectAccess table)
3. Derive completeness + maturity metrics
4. Classify AACE class
5. Compute base cost + line items
6. Build RiskFactor objects
7. Run Monte Carlo analysis
8. Compute contingency percentage
9. Generate narrative
10. Generate assumptions
11. Generate exclusions
12. Build Estimate + children ORM entities
13. Persist via repository (single transaction)
14. Create AuditLog entry
"""
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from apex.config import config
from apex.database.repositories.audit_repository import AuditRepository
from apex.database.repositories.document_repository import DocumentRepository
from apex.database.repositories.estimate_repository import EstimateRepository
from apex.database.repositories.project_repository import ProjectRepository
from apex.models.database import (
    CostCode,
    Document,
    Estimate,
    EstimateAssumption,
    EstimateExclusion,
    EstimateLineItem,
    EstimateRiskFactor,
    Project,
    User,
)
from apex.models.enums import AACEClass
from apex.services.aace_classifier import AACEClassifier
from apex.services.cost_database import CostDatabaseService
from apex.services.llm.orchestrator import LLMOrchestrator
from apex.services.risk_analysis import MonteCarloRiskAnalyzer, RiskFactor
from apex.utils.errors import BusinessRuleViolation

logger = logging.getLogger(__name__)


class EstimateGenerator:
    """
    Main orchestration service coordinating all estimation steps.

    Responsibilities:
    - Access control validation
    - Service coordination
    - Transaction management
    - Audit logging
    - Error handling and rollback

    Example:
        ```python
        generator = EstimateGenerator(
            project_repo=project_repo,
            document_repo=document_repo,
            estimate_repo=estimate_repo,
            audit_repo=audit_repo,
            llm_orchestrator=llm_orch,
            risk_analyzer=risk_analyzer,
            aace_classifier=aace_classifier,
            cost_db_service=cost_db_service,
        )

        estimate = await generator.generate_estimate(
            db=db,
            project_id=project_uuid,
            risk_factors_dto=[{...}],
            confidence_level=0.80,
            monte_carlo_iterations=10000,
            user=current_user,
        )
        ```
    """

    def __init__(
        self,
        project_repo: ProjectRepository,
        document_repo: DocumentRepository,
        estimate_repo: EstimateRepository,
        audit_repo: AuditRepository,
        llm_orchestrator: LLMOrchestrator,
        risk_analyzer: MonteCarloRiskAnalyzer,
        aace_classifier: AACEClassifier,
        cost_db_service: CostDatabaseService,
    ):
        """
        Initialize estimate generator with all required dependencies.

        Args:
            project_repo: Project data access
            document_repo: Document data access
            estimate_repo: Estimate data access
            audit_repo: Audit log data access
            llm_orchestrator: LLM coordination service
            risk_analyzer: Monte Carlo risk analysis service
            aace_classifier: AACE classification service
            cost_db_service: Cost database and CBS/WBS service
        """
        self.project_repo = project_repo
        self.document_repo = document_repo
        self.estimate_repo = estimate_repo
        self.audit_repo = audit_repo
        self.llm_orchestrator = llm_orchestrator
        self.risk_analyzer = risk_analyzer
        self.aace_classifier = aace_classifier
        self.cost_db_service = cost_db_service

    async def generate_estimate(
        self,
        db: Session,
        project_id: UUID,
        risk_factors_dto: List[Dict[str, Any]],
        confidence_level: float,
        monte_carlo_iterations: int,
        user: User,
    ) -> Estimate:
        """
        Orchestrate full estimate generation workflow.

        14-Step Process:
        1. Load project & documents
        2. Check user access
        3. Derive completeness + maturity
        4. Classify AACE class
        5. Compute base cost + line items
        6. Build RiskFactor objects
        7. Run Monte Carlo analysis
        8. Compute contingency percentage
        9. Generate narrative
        10. Generate assumptions
        11. Generate exclusions
        12. Build Estimate + children entities
        13. Persist via repository
        14. Create audit log

        Args:
            db: Database session
            project_id: Project UUID
            risk_factors_dto: List of risk factor definitions
            confidence_level: Target confidence level (e.g., 0.80 for P80)
            monte_carlo_iterations: Number of MC iterations
            user: Current user

        Returns:
            Persisted Estimate entity with full hierarchy

        Raises:
            BusinessRuleViolation: Access denied, validation failures, etc.
        """
        logger.info(f"Starting estimate generation for project {project_id} by user {user.email}")

        start_time = datetime.utcnow()

        # STEP 1: Load project & documents
        project = self.project_repo.get(db, project_id)
        if not project:
            raise BusinessRuleViolation(
                message=f"Project not found: {project_id}", code="PROJECT_NOT_FOUND"
            )

        documents = self.document_repo.get_by_project_id(db, project_id)

        logger.info(f"Loaded project {project.project_number}: {len(documents)} documents")

        # STEP 2: Check user access
        has_access = self.project_repo.check_user_access(db, user.id, project_id)
        if not has_access:
            raise BusinessRuleViolation(
                message=f"User {user.email} does not have access to project {project_id}",
                code="ACCESS_DENIED",
            )

        # STEP 3: Derive completeness + maturity metrics
        completeness_score, engineering_maturity = self._derive_project_metrics(project, documents)

        logger.info(
            f"Project metrics: completeness={completeness_score}%, "
            f"engineering_maturity={engineering_maturity}%"
        )

        # STEP 4: Classify AACE class
        classification_result = self.aace_classifier.classify(
            engineering_maturity_pct=engineering_maturity,
            completeness_score=completeness_score,
            available_deliverables=[doc.document_type for doc in documents],
        )

        aace_class: AACEClass = classification_result["aace_class"]
        accuracy_range: str = classification_result["accuracy_range"]

        logger.info(
            f"AACE classification: {aace_class.value} ({accuracy_range}), "
            f"{len(classification_result['justification'])} justifications"
        )

        # STEP 5: Compute base cost + line items
        # Get available cost codes (simplified for MVP - production would query database)
        cost_code_map = self._get_cost_code_map(db)

        base_cost, line_items = self.cost_db_service.compute_base_cost(
            db=db,
            project=project,
            documents=documents,
            cost_code_map=cost_code_map,
        )

        logger.info(f"Base cost computed: ${base_cost:,.2f} with {len(line_items)} line items")

        # STEP 6: Build RiskFactor objects from DTO
        risk_factors = self._build_risk_factors(risk_factors_dto)

        # STEP 7: Run Monte Carlo analysis
        self.risk_analyzer.iterations = monte_carlo_iterations
        risk_results = await asyncio.to_thread(
            self.risk_analyzer.run_analysis,
            base_cost=float(base_cost),
            risk_factors=risk_factors,
            correlation_matrix=None,  # MVP: no correlation (production would extract from DTO)
            confidence_levels=[0.50, confidence_level, 0.95],
        )

        pct = int(confidence_level * 100)
        p50 = risk_results["percentiles"]["p50"]
        target = risk_results["percentiles"][f"p{pct}"]
        logger.info(f"Monte Carlo analysis complete: P50=${p50:,.2f}, P{pct}=${target:,.2f}")

        # STEP 8: Compute contingency percentage
        target_cost = Decimal(str(risk_results["percentiles"][f"p{int(confidence_level * 100)}"]))
        contingency_pct = (
            float((target_cost - base_cost) / base_cost * 100) if base_cost > 0 else 0.0
        )

        logger.info(f"Contingency percentage: {contingency_pct:.2f}%")

        # STEP 9: Generate narrative (LLM)
        line_item_summary = self._create_line_item_summary(line_items)

        narrative = await self.llm_orchestrator.generate_narrative(
            aace_class=aace_class,
            project=project,
            base_cost=base_cost,
            risk_results=risk_results,
            line_item_summary=line_item_summary,
        )

        logger.info(f"Narrative generated: {len(narrative)} characters")

        # STEP 10: Generate assumptions (LLM)
        assumptions_list = await self.llm_orchestrator.generate_assumptions(
            aace_class=aace_class,
            project=project,
            documents=documents,
        )

        logger.info(f"Generated {len(assumptions_list)} assumptions")

        # STEP 11: Generate exclusions (LLM)
        exclusions_list = await self.llm_orchestrator.generate_exclusions(
            aace_class=aace_class,
            project=project,
            documents=documents,
        )

        logger.info(f"Generated {len(exclusions_list)} exclusions")

        # STEP 12: Build Estimate + children ORM entities
        estimate = self._build_estimate_entity(
            project=project,
            aace_class=aace_class,
            base_cost=base_cost,
            contingency_pct=contingency_pct,
            confidence_level=confidence_level,
            risk_results=risk_results,
            narrative=narrative,
            user=user,
        )

        # Build assumption entities
        assumption_entities = [
            EstimateAssumption(
                assumption_text=text,
                category="General",  # MVP: simple category (production would use LLM to categorize)
            )
            for text in assumptions_list
        ]

        # Build exclusion entities
        exclusion_entities = [
            EstimateExclusion(
                exclusion_text=text,
                category="General",
            )
            for text in exclusions_list
        ]

        # Build risk factor entities
        # Persist all distribution parameters for complete audit trail
        risk_factor_entities = []
        for factor in risk_factors.values():
            risk_factor_entity = EstimateRiskFactor(
                factor_name=factor.name,
                distribution=factor.distribution,
            )

            # Set distribution-specific parameters
            if factor.min_value is not None:
                risk_factor_entity.param_min = factor.min_value
            if factor.most_likely is not None:
                risk_factor_entity.param_likely = factor.most_likely
            if factor.max_value is not None:
                risk_factor_entity.param_max = factor.max_value
            if factor.mean is not None:
                risk_factor_entity.param_mean = factor.mean
            if factor.std_dev is not None:
                risk_factor_entity.param_std_dev = factor.std_dev

            risk_factor_entities.append(risk_factor_entity)

        logger.info(
            f"Built estimate entity with {len(line_items)} line items, "
            f"{len(assumption_entities)} assumptions, {len(exclusion_entities)} exclusions, "
            f"{len(risk_factor_entities)} risk factors"
        )

        # STEP 13: Persist via repository (single transaction)
        persisted_estimate = self.estimate_repo.create_estimate_with_hierarchy(
            db=db,
            estimate=estimate,
            line_items=line_items,
            assumptions=assumption_entities,
            exclusions=exclusion_entities,
            risk_factors=risk_factor_entities,
        )

        logger.info(f"Estimate persisted: {persisted_estimate.estimate_number}")

        # STEP 14: Create audit log
        duration_seconds = (datetime.utcnow() - start_time).total_seconds()

        audit_log_data = {
            "project_id": project_id,
            "estimate_id": persisted_estimate.id,
            "user_id": user.id,
            "action": "estimate_generated",
            "details": {
                "aace_class": aace_class.value,
                "base_cost": float(base_cost),
                "p50_cost": risk_results["percentiles"]["p50"],
                "p80_cost": risk_results["percentiles"].get("p80"),
                "p95_cost": risk_results["percentiles"]["p95"],
                "contingency_pct": contingency_pct,
                "line_item_count": len(line_items),
                "duration_seconds": duration_seconds,
            },
            "llm_model_version": config.AZURE_OPENAI_DEPLOYMENT,
        }

        self.audit_repo.create(db, audit_log_data)

        logger.info(
            f"Estimate generation complete: {persisted_estimate.estimate_number} "
            f"in {duration_seconds:.1f}s"
        )

        return persisted_estimate

    def _derive_project_metrics(
        self,
        project: Project,
        documents: List[Document],
    ) -> tuple[int, float]:
        """
        Derive completeness and engineering maturity metrics.

        Args:
            project: Project instance
            documents: List of documents

        Returns:
            Tuple of (completeness_score, engineering_maturity_pct)
        """
        # MVP: Simple heuristic based on document count and validation status
        # Production: Aggregate from document.validation_result completeness scores

        # Completeness: based on validated documents
        total_docs = len(documents)
        if total_docs == 0:
            completeness_score = 0
        else:
            validated_docs = sum(
                1 for doc in documents if doc.completeness_score and doc.completeness_score >= 70
            )
            completeness_score = int((validated_docs / total_docs) * 100)

        # Engineering maturity: heuristic based on project status and document types
        has_engineering = any(doc.document_type == "engineering" for doc in documents)
        has_bid = any(doc.document_type == "bid" for doc in documents)

        if has_bid and has_engineering:
            engineering_maturity = 95.0  # Near final
        elif has_engineering:
            engineering_maturity = 65.0  # Preliminary design
        elif any(doc.document_type == "scope" for doc in documents):
            engineering_maturity = 30.0  # Feasibility
        else:
            engineering_maturity = 10.0  # Conceptual

        return completeness_score, engineering_maturity

    def _get_cost_code_map(self, db: Session) -> Dict[str, CostCode]:
        """
        Get available cost codes.

        Args:
            db: Database session

        Returns:
            Dictionary of cost code ID -> CostCode entity

        Note: Uses CostLookupService to build map; returns empty dict if none exist.
        """
        from apex.services.cost_lookup import CostLookupService

        lookup = CostLookupService()
        return lookup.get_all_codes(db)

    def _build_risk_factors(
        self,
        risk_factors_dto: List[Dict[str, Any]],
    ) -> Dict[str, RiskFactor]:
        """
        Convert risk factor DTOs to RiskFactor dataclasses.

        Args:
            risk_factors_dto: List of risk factor dictionaries from API

        Returns:
            Dictionary of factor name -> RiskFactor

        Raises:
            BusinessRuleViolation: If DTO is invalid
        """
        risk_factors = {}

        for dto in risk_factors_dto:
            try:
                factor = RiskFactor(
                    name=dto["name"],
                    distribution=dto["distribution"],
                    min_value=dto.get("min_value"),
                    most_likely=dto.get("most_likely"),
                    max_value=dto.get("max_value"),
                    mean=dto.get("mean"),
                    std_dev=dto.get("std_dev"),
                )
                risk_factors[factor.name] = factor
            except (KeyError, TypeError) as exc:
                raise BusinessRuleViolation(
                    message=f"Invalid risk factor DTO: {exc}",
                    code="INVALID_RISK_FACTOR_DTO",
                    details={"dto": dto},
                )

        logger.info(f"Built {len(risk_factors)} RiskFactor objects from DTOs")

        return risk_factors

    def _create_line_item_summary(
        self,
        line_items: List[EstimateLineItem],
    ) -> str:
        """
        Create summary of line items for LLM prompt.

        Args:
            line_items: List of EstimateLineItem entities

        Returns:
            Formatted summary string
        """
        # Group by parent (items with no _temp_parent_ref are parents)
        parents = [
            item
            for item in line_items
            if not hasattr(item, "_temp_parent_ref") or item._temp_parent_ref is None
        ]

        summary_lines = []
        for parent in parents:
            summary_lines.append(
                f"- {parent.wbs_code}: {parent.description} = ${parent.total_cost:,.2f}"
            )

        return "\n".join(summary_lines)

    def _build_estimate_entity(
        self,
        project: Project,
        aace_class: AACEClass,
        base_cost: Decimal,
        contingency_pct: float,
        confidence_level: float,
        risk_results: Dict[str, Any],
        narrative: str,
        user: User,
    ) -> Estimate:
        """
        Build Estimate ORM entity.

        Args:
            project: Project instance
            aace_class: AACE classification
            base_cost: Base cost
            contingency_pct: Contingency percentage
            confidence_level: Target confidence level (e.g., 0.80 for P80)
            risk_results: Monte Carlo results
            narrative: Generated narrative
            user: Current user

        Returns:
            Estimate entity (not yet persisted)
        """
        # Generate estimate number (MVP: simple incrementing)
        # Production: Get next number from sequence or database
        estimate_number = (
            f"{project.project_number}-EST-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )

        # HIGH FIX: Store actual confidence level percentile, not just P80
        # Map confidence_level to appropriate percentile
        target_percentile_key = f"p{int(confidence_level * 100)}"
        target_percentile_cost = risk_results["percentiles"].get(
            target_percentile_key, risk_results["percentiles"]["p50"]  # Fallback to median
        )

        estimate = Estimate(
            project_id=project.id,
            estimate_number=estimate_number,
            aace_class=aace_class,
            base_cost=base_cost,
            contingency_percentage=contingency_pct,
            p50_cost=Decimal(str(risk_results["percentiles"]["p50"])),
            p80_cost=Decimal(str(target_percentile_cost)),  # Use actual target percentile
            p95_cost=Decimal(str(risk_results["percentiles"]["p95"])),
            # risk_distribution_blob_path would be set if we save full distribution to Blob
            narrative=narrative,
            llm_model_version=config.AZURE_OPENAI_DEPLOYMENT,
            created_by_id=user.id,
        )

        return estimate
