"""
AACE International estimate classification service.

Classifies estimates into AACE Class 1-5 based on project maturity and deliverables.

AACE Classes:
- Class 5: Conceptual (±50%) - Capacity factored, parametric
- Class 4: Feasibility (±30%) - Equipment factored, parametric
- Class 3: Budget (±20%) - Semi-detailed, unit costs
- Class 2: Control (±15%) - Detailed, priced bill of quantities
- Class 1: Check Estimate (±10%) - Detailed, contractor bid check

Classification Logic:
- Uses weighted score: 60% engineering maturity + 40% document completeness
- Thresholds: ≥90% = Class 1, ≥70% = Class 2, ≥50% = Class 3, ≥30% = Class 4, <30% = Class 5
"""
from typing import Dict, List, Tuple, Any
from apex.models.enums import AACEClass
from apex.utils.errors import BusinessRuleViolation
import logging

logger = logging.getLogger(__name__)


class AACEClassifier:
    """
    Classifier for AACE International estimate classes.

    Uses engineering maturity percentage, deliverable completeness,
    and available documentation to determine appropriate classification.
    """

    def classify(
        self,
        engineering_maturity_pct: float,
        completeness_score: int,
        available_deliverables: List[str],
    ) -> Dict[str, Any]:
        """
        Classify estimate into AACE class.

        Args:
            engineering_maturity_pct: Engineering completion percentage (0-100)
            completeness_score: Document completeness score (0-100)
            available_deliverables: List of available document types

        Returns:
            Dict with aace_class, accuracy_range, justification, recommendations

        Raises:
            BusinessRuleViolation: If input values are out of valid range
        """
        # Validate input ranges
        if not (0 <= engineering_maturity_pct <= 100):
            raise BusinessRuleViolation(
                message=f"Engineering maturity must be 0-100, got {engineering_maturity_pct}",
                code="INVALID_ENGINEERING_MATURITY"
            )

        if not (0 <= completeness_score <= 100):
            raise BusinessRuleViolation(
                message=f"Completeness score must be 0-100, got {completeness_score}",
                code="INVALID_COMPLETENESS_SCORE"
            )

        logger.info(
            f"Classifying estimate: engineering={engineering_maturity_pct:.1f}%, "
            f"completeness={completeness_score}%, deliverables={len(available_deliverables)}"
        )

        # Determine class based on maturity and completeness
        aace_class, accuracy_range = self._determine_class(
            engineering_maturity_pct, completeness_score
        )

        # Generate justification
        justification = self._generate_justification(
            aace_class, engineering_maturity_pct, completeness_score, available_deliverables
        )

        # Generate recommendations for improvement
        recommendations = self._generate_recommendations(
            aace_class, engineering_maturity_pct, completeness_score, available_deliverables
        )

        logger.info(
            f"Classification complete: {aace_class.value} ({accuracy_range}), "
            f"{len(justification)} justifications, {len(recommendations)} recommendations"
        )

        return {
            "aace_class": aace_class,
            "accuracy_range": accuracy_range,
            "justification": justification,
            "recommendations": recommendations,
        }

    def _determine_class(
        self, engineering_maturity_pct: float, completeness_score: int
    ) -> Tuple[AACEClass, str]:
        """
        Determine AACE class based on maturity and completeness.

        Args:
            engineering_maturity_pct: Engineering completion (0-100)
            completeness_score: Document completeness (0-100)

        Returns:
            Tuple of (AACEClass, accuracy_range_string)
        """
        # Weighted score: 60% engineering maturity, 40% completeness
        weighted_score = (engineering_maturity_pct * 0.6) + (completeness_score * 0.4)

        # Classification thresholds
        if weighted_score >= 90:
            return AACEClass.CLASS_1, "±10%"
        elif weighted_score >= 70:
            return AACEClass.CLASS_2, "±15%"
        elif weighted_score >= 50:
            return AACEClass.CLASS_3, "±20%"
        elif weighted_score >= 30:
            return AACEClass.CLASS_4, "±30%"
        else:
            return AACEClass.CLASS_5, "±50%"

    def _generate_justification(
        self,
        aace_class: AACEClass,
        engineering_maturity_pct: float,
        completeness_score: int,
        available_deliverables: List[str],
    ) -> List[str]:
        """
        Generate justification for classification.

        Args:
            aace_class: Classified AACE class
            engineering_maturity_pct: Engineering completion
            completeness_score: Document completeness
            available_deliverables: Available document types

        Returns:
            List of justification statements
        """
        justification = []

        # Maturity justification
        if engineering_maturity_pct >= 90:
            justification.append(
                f"Engineering is {engineering_maturity_pct:.0f}% complete (detailed design)"
            )
        elif engineering_maturity_pct >= 70:
            justification.append(
                f"Engineering is {engineering_maturity_pct:.0f}% complete (design development)"
            )
        elif engineering_maturity_pct >= 50:
            justification.append(
                f"Engineering is {engineering_maturity_pct:.0f}% complete (preliminary design)"
            )
        elif engineering_maturity_pct >= 30:
            justification.append(
                f"Engineering is {engineering_maturity_pct:.0f}% complete (feasibility study)"
            )
        else:
            justification.append(
                f"Engineering is {engineering_maturity_pct:.0f}% complete (conceptual phase)"
            )

        # Completeness justification
        if completeness_score >= 90:
            justification.append(
                f"Documentation is {completeness_score}% complete with comprehensive deliverables"
            )
        elif completeness_score >= 70:
            justification.append(
                f"Documentation is {completeness_score}% complete with most key deliverables"
            )
        else:
            justification.append(
                f"Documentation is {completeness_score}% complete with limited deliverables"
            )

        # Deliverable-specific justifications
        key_docs = {"scope", "engineering", "schedule", "bid"}
        available_key = set(available_deliverables) & key_docs
        if available_key:
            justification.append(
                f"Available deliverables include: {', '.join(sorted(available_key))}"
            )

        # Class-specific context
        if aace_class == AACEClass.CLASS_1:
            justification.append("Suitable for contractor bid validation and final approval")
        elif aace_class == AACEClass.CLASS_2:
            justification.append("Suitable for project authorization and detailed control")
        elif aace_class == AACEClass.CLASS_3:
            justification.append("Suitable for budget approval and project planning")
        elif aace_class == AACEClass.CLASS_4:
            justification.append("Suitable for feasibility assessment and funding requests")
        else:  # CLASS_5
            justification.append("Suitable for conceptual planning and initial screening")

        return justification

    def _generate_recommendations(
        self,
        aace_class: AACEClass,
        engineering_maturity_pct: float,
        completeness_score: int,
        available_deliverables: List[str],
    ) -> List[str]:
        """
        Generate recommendations to improve estimate class.

        Args:
            aace_class: Current AACE class
            engineering_maturity_pct: Engineering completion
            completeness_score: Document completeness
            available_deliverables: Available document types

        Returns:
            List of actionable recommendations
        """
        recommendations = []

        # Already at highest class
        if aace_class == AACEClass.CLASS_1:
            recommendations.append("Estimate is at highest classification (Class 1)")
            return recommendations

        # Engineering maturity recommendations
        # MEDIUM FIX: Only recommend increase if below target, avoid negative gaps
        if aace_class in [AACEClass.CLASS_2, AACEClass.CLASS_3]:
            target = 90
        else:
            target = 70

        if engineering_maturity_pct < target:
            gap = target - engineering_maturity_pct
            recommendations.append(
                f"Increase engineering completion by {gap:.0f}% to improve classification"
            )

        # Documentation completeness recommendations
        if completeness_score < 90:
            recommendations.append("Complete missing sections in project documentation")

        # Missing deliverables
        key_docs = {"scope", "engineering", "schedule", "bid"}
        missing = key_docs - set(available_deliverables)
        if missing:
            recommendations.append(
                f"Obtain missing deliverables: {', '.join(sorted(missing))}"
            )

        # Class-specific recommendations
        if aace_class == AACEClass.CLASS_5:
            recommendations.append("Conduct preliminary engineering study to reach Class 4")
            recommendations.append("Develop equipment list and layout drawings")

        elif aace_class == AACEClass.CLASS_4:
            recommendations.append("Complete detailed engineering to 50%+ for Class 3")
            recommendations.append("Develop bill of quantities with unit costs")

        elif aace_class == AACEClass.CLASS_3:
            recommendations.append("Complete detailed engineering to 70%+ for Class 2")
            recommendations.append("Obtain vendor quotes for major equipment")

        elif aace_class == AACEClass.CLASS_2:
            recommendations.append("Complete final engineering and construction drawings for Class 1")
            recommendations.append("Obtain contractor bids for validation")

        return recommendations
