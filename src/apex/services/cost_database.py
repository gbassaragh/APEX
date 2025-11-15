"""
Cost Database Service for computing base costs and CBS/WBS hierarchy.

CRITICAL: Returns RELATIONAL EstimateLineItem entities, NOT JSON blobs.
All costs use Decimal for precision. Parent linking is deferred to repository transaction.

CBS/WBS Hierarchy:
- Parent items: "10: Transmission Line" (summary with rolled-up totals)
- Child items: "10-100: Tangent Structures" (detail with quantities)
- Uses wbs_code for deterministic mapping
- Sets _temp_parent_ref attribute (e.g., "10" for child "10-100")
- EstimateRepository persists parent_line_item_id GUIDs in transaction
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from apex.models.database import CostCode, Document, EstimateLineItem, Project
from apex.models.enums import TerrainType

logger = logging.getLogger(__name__)


class CostDatabaseService:
    """
    Computes base (pre-contingency) cost and builds CBS/WBS hierarchy.

    Workflow:
    1. Extract quantities from parsed documents
    2. Map quantities to cost codes (e.g., RSMeans)
    3. Look up unit costs (MVP: sample costs; production: database/API)
    4. Apply adjustments (terrain, voltage, location factors)
    5. Build CBS hierarchy with parent/child relationships
    6. Return base cost + flat list of EstimateLineItem entities
    """

    def __init__(self):
        """
        Initialize cost database service.

        Note: Database session is passed to methods, not stored in __init__.
        This follows the stateless service pattern for Azure Container Apps.
        """
        pass

    def compute_base_cost(
        self,
        db: Session,
        project: Project,
        documents: List[Document],
        cost_code_map: Dict[str, CostCode],
    ) -> Tuple[Decimal, List[EstimateLineItem]]:
        """
        Main entry point for base cost computation.

        Args:
            db: SQLAlchemy database session (for future cost code lookups)
            project: Project ORM instance
            documents: List of validated documents
            cost_code_map: Dictionary of cost code ID -> CostCode entity

        Returns:
            Tuple of (total_base_cost, line_item_entities)

        Line items have:
        - wbs_code set (e.g., "10", "10-100")
        - _temp_parent_ref attribute for parent linking (not parent_line_item_id)
        - estimate_id still None (set by repository)

        Raises:
            BusinessRuleViolation: If quantity extraction fails or data is invalid
        """
        logger.info(
            f"Computing base cost for project {project.project_number}: "
            f"{len(documents)} documents, {len(cost_code_map)} cost codes available"
        )

        # Extract quantities from documents
        quantities = self._extract_quantities(project, documents)

        # Map quantities to cost codes
        cost_items = self._map_to_cost_items(project, quantities, cost_code_map)

        # Look up unit costs
        cost_items_with_units = self._lookup_unit_costs(cost_items)

        # Apply project-specific adjustments
        adjusted_items = self._apply_adjustments(project, cost_items_with_units)

        # Build CBS hierarchy
        total_cost, line_item_entities = self._build_cbs_hierarchy(adjusted_items)

        logger.info(
            f"Base cost computation complete: ${total_cost:,.2f}, "
            f"{len(line_item_entities)} line items"
        )

        return total_cost, line_item_entities

    def _extract_quantities(
        self,
        project: Project,
        documents: List[Document],
    ) -> Dict[str, Any]:
        """
        Extract quantity takeoffs from parsed documents.

        For MVP: Simple parametric estimation based on project attributes.
        For Production: LLM-assisted extraction from structured document content.

        Args:
            project: Project ORM instance
            documents: List of documents

        Returns:
            Dictionary of quantity data by component type

        Note: This is MVP implementation using parametric estimation.
        """
        logger.info(f"Extracting quantities for {project.project_name}")

        # MVP: Parametric estimation based on project attributes
        # Production would parse document.validation_result JSON for quantities

        quantities = {}

        # Transmission line quantities (voltage level drives structure type)
        if project.voltage_level and project.line_miles:
            # Tangent structures (standard supports)
            # Rule of thumb: 1 structure per 600-800 feet (varies by voltage)
            if project.voltage_level >= 345:
                structures_per_mile = 5  # Larger spans for higher voltage
            elif project.voltage_level >= 115:
                structures_per_mile = 7
            else:
                structures_per_mile = 10

            quantities["tangent_structures"] = {
                "quantity": project.line_miles * structures_per_mile,
                "unit": "EA",
                "description": f"{project.voltage_level}kV Tangent Structures",
            }

            # Dead-end structures (angle points, typically 5-10% of total)
            quantities["dead_end_structures"] = {
                "quantity": project.line_miles * structures_per_mile * 0.08,
                "unit": "EA",
                "description": f"{project.voltage_level}kV Dead-End Structures",
            }

            # Conductor (3 phases + ground wire)
            quantities["conductor"] = {
                "quantity": project.line_miles * 5280 * 4,  # 4 wires (3 phase + ground)
                "unit": "LF",
                "description": f"ACSR Conductor for {project.voltage_level}kV",
            }

            # Foundation (1 per structure, varies by terrain)
            total_structures = (
                quantities["tangent_structures"]["quantity"]
                + quantities["dead_end_structures"]["quantity"]
            )
            quantities["foundations"] = {
                "quantity": total_structures,
                "unit": "EA",
                "description": "Drilled Pier Foundations",
            }

            # Right-of-way clearing (width varies by voltage)
            if project.voltage_level >= 345:
                row_width_ft = 200
            elif project.voltage_level >= 115:
                row_width_ft = 150
            else:
                row_width_ft = 100

            quantities["row_clearing"] = {
                "quantity": project.line_miles * row_width_ft / 43560,  # Convert to acres
                "unit": "AC",
                "description": f"Right-of-Way Clearing ({row_width_ft}' width)",
            }

        logger.info(f"Extracted {len(quantities)} quantity items parametrically")

        return quantities

    def _map_to_cost_items(
        self,
        project: Project,
        quantities: Dict[str, Any],
        cost_code_map: Dict[str, CostCode],
    ) -> List[Dict[str, Any]]:
        """
        Map quantities to cost codes.

        Args:
            project: Project instance
            quantities: Extracted quantities
            cost_code_map: Available cost codes

        Returns:
            List of cost items with quantity and cost code reference
        """
        logger.info(f"Mapping {len(quantities)} quantities to cost codes")

        cost_items = []

        # MVP: Simple mapping (production would use intelligent matching)
        # Cost code examples: "10-100" = Tangent Structures, "10-200" = Dead-End Structures

        for key, qty_data in quantities.items():
            # Simplified cost code lookup (production would query CostCode table)
            cost_code_id = None

            # Try to find matching cost code from map (simplified for MVP)
            if "tangent" in key.lower():
                cost_code_id = "10-100"  # Placeholder - would lookup in cost_code_map
            elif "dead_end" in key.lower() or "dead-end" in key.lower():
                cost_code_id = "10-200"
            elif "conductor" in key.lower():
                cost_code_id = "20-100"
            elif "foundation" in key.lower():
                cost_code_id = "10-300"
            elif "clearing" in key.lower():
                cost_code_id = "30-100"

            cost_items.append(
                {
                    "component_key": key,
                    "cost_code_id": cost_code_id,
                    "description": qty_data["description"],
                    "quantity": qty_data["quantity"],
                    "unit_of_measure": qty_data["unit"],
                }
            )

        logger.info(f"Mapped to {len(cost_items)} cost items")

        return cost_items

    def _lookup_unit_costs(
        self,
        cost_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Look up unit costs from cost database.

        For MVP: Hardcoded sample costs
        For Production: Query RSMeans database/API or internal cost database

        Args:
            cost_items: Cost items from mapping

        Returns:
            Cost items with unit costs added
        """
        logger.info(f"Looking up unit costs for {len(cost_items)} items")

        # MVP: Sample unit costs (production would query database)
        sample_unit_costs = {
            "10-100": {
                "material": Decimal("15000"),
                "labor": Decimal("8000"),
                "other": Decimal("2000"),
            },  # Tangent structure
            "10-200": {
                "material": Decimal("22000"),
                "labor": Decimal("12000"),
                "other": Decimal("3000"),
            },  # Dead-end structure
            "10-300": {
                "material": Decimal("3000"),
                "labor": Decimal("4000"),
                "other": Decimal("500"),
            },  # Foundation
            "20-100": {
                "material": Decimal("1.50"),
                "labor": Decimal("0.75"),
                "other": Decimal("0.25"),
            },  # Conductor per LF
            "30-100": {
                "material": Decimal("500"),
                "labor": Decimal("1000"),
                "other": Decimal("200"),
            },  # ROW clearing per acre
        }

        for item in cost_items:
            cost_code_id = item.get("cost_code_id")

            if cost_code_id and cost_code_id in sample_unit_costs:
                unit_cost = sample_unit_costs[cost_code_id]
                item["unit_cost_material"] = unit_cost["material"]
                item["unit_cost_labor"] = unit_cost["labor"]
                item["unit_cost_other"] = unit_cost["other"]
                item["unit_cost_total"] = (
                    unit_cost["material"] + unit_cost["labor"] + unit_cost["other"]
                )
            else:
                # Fallback for unknown cost codes
                logger.warning(
                    f"No unit cost found for cost code {cost_code_id}, using placeholder"
                )
                item["unit_cost_material"] = Decimal("1000")
                item["unit_cost_labor"] = Decimal("500")
                item["unit_cost_other"] = Decimal("100")
                item["unit_cost_total"] = Decimal("1600")

        logger.info("Unit cost lookup complete")

        return cost_items

    def _apply_adjustments(
        self,
        project: Project,
        cost_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Apply project-specific adjustments.

        Adjustments based on:
        - Terrain type (multiplier for difficulty)
        - Voltage level (complexity factor)
        - Geographic location (if available)

        Args:
            project: Project instance
            cost_items: Cost items with unit costs

        Returns:
            Cost items with adjusted unit costs
        """
        logger.info(
            f"Applying adjustments for terrain={project.terrain_type}, voltage={project.voltage_level}kV"
        )

        # Terrain difficulty multipliers
        terrain_multipliers = {
            TerrainType.FLAT: Decimal("1.0"),
            TerrainType.ROLLING: Decimal("1.1"),
            TerrainType.MOUNTAINOUS: Decimal("1.35"),
            TerrainType.URBAN: Decimal("1.25"),
            TerrainType.WETLAND: Decimal("1.2"),
        }

        terrain_factor = terrain_multipliers.get(project.terrain_type, Decimal("1.0"))

        # Voltage complexity factor (higher voltage = more complex)
        if project.voltage_level and project.voltage_level >= 345:
            voltage_factor = Decimal("1.15")
        elif project.voltage_level and project.voltage_level >= 230:
            voltage_factor = Decimal("1.10")
        elif project.voltage_level and project.voltage_level >= 115:
            voltage_factor = Decimal("1.05")
        else:
            voltage_factor = Decimal("1.0")

        # Combined adjustment factor
        combined_factor = terrain_factor * voltage_factor

        logger.info(
            f"Adjustment factors: terrain={terrain_factor}, voltage={voltage_factor}, "
            f"combined={combined_factor}"
        )

        # Apply factor to unit costs
        for item in cost_items:
            item["unit_cost_material"] *= combined_factor
            item["unit_cost_labor"] *= combined_factor
            item["unit_cost_other"] *= combined_factor
            item["unit_cost_total"] *= combined_factor

        return cost_items

    def _build_cbs_hierarchy(
        self,
        cost_items: List[Dict[str, Any]],
    ) -> Tuple[Decimal, List[EstimateLineItem]]:
        """
        Build Cost Breakdown Structure with parent/child relationships.

        Process:
        1. Group items by WBS code prefix (first two digits)
        2. Create summary parent rows with rolled-up totals
        3. Create detail child rows with quantities
        4. Set wbs_code on all items
        5. Set _temp_parent_ref on children (not parent_line_item_id - that's for repository)
        6. Return total cost + flat list of EstimateLineItem entities

        Example hierarchy:
        - "10: Transmission Structures" (parent, summary, quantity=0)
          - "10-100: Tangent Structures" (child, detail, quantity=N)
          - "10-200: Dead-End Structures" (child, detail, quantity=M)
        - "20: Conductor & Hardware" (parent, summary, quantity=0)
          - "20-100: ACSR Conductor" (child, detail, quantity=X)

        Args:
            cost_items: Adjusted cost items

        Returns:
            Tuple of (total_cost, line_item_entities)
        """
        logger.info(f"Building CBS hierarchy from {len(cost_items)} cost items")

        # Group by WBS prefix
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for item in cost_items:
            cost_code = item.get("cost_code_id", "99-999")
            prefix = cost_code.split("-")[0] if "-" in cost_code else "99"

            if prefix not in grouped:
                grouped[prefix] = []
            grouped[prefix].append(item)

        # Define parent categories
        parent_descriptions = {
            "10": "Transmission Structures",
            "20": "Conductor & Hardware",
            "30": "Right-of-Way & Site Work",
            "40": "Substation Equipment",
            "50": "Protection & Control",
            "99": "Miscellaneous",
        }

        line_items: List[EstimateLineItem] = []
        total_cost = Decimal("0")

        # Build hierarchy
        for prefix in sorted(grouped.keys()):
            children = grouped[prefix]

            # Calculate parent total
            parent_total = sum(
                Decimal(str(child["quantity"])) * child["unit_cost_total"] for child in children
            )

            total_cost += parent_total

            # Create parent summary row
            parent = EstimateLineItem(
                wbs_code=prefix,
                description=f"{prefix}: {parent_descriptions.get(prefix, 'Other')}",
                quantity=Decimal("0"),  # Summary row - no quantity
                unit_of_measure="LS",  # Lump sum
                unit_cost_material=Decimal("0"),
                unit_cost_labor=Decimal("0"),
                unit_cost_other=Decimal("0"),
                unit_cost_total=Decimal("0"),  # Will be rolled up from children
                total_cost=parent_total,
            )
            parent._temp_parent_ref = None  # Top-level item
            line_items.append(parent)

            # Create child detail rows
            for child_data in children:
                quantity = Decimal(str(child_data["quantity"]))
                unit_total = child_data["unit_cost_total"]
                child_total = quantity * unit_total

                child = EstimateLineItem(
                    wbs_code=child_data.get("cost_code_id", f"{prefix}-999"),
                    description=child_data["description"],
                    quantity=quantity,
                    unit_of_measure=child_data["unit_of_measure"],
                    unit_cost_material=child_data["unit_cost_material"],
                    unit_cost_labor=child_data["unit_cost_labor"],
                    unit_cost_other=child_data["unit_cost_other"],
                    unit_cost_total=unit_total,
                    total_cost=child_total,
                )

                # Set temporary parent reference (not GUID - that's set in repository)
                child._temp_parent_ref = prefix  # Links to parent's wbs_code
                line_items.append(child)

        logger.info(
            f"CBS hierarchy built: {len(line_items)} total line items "
            f"({len(grouped)} parents, {len(cost_items)} children), "
            f"total cost = ${total_cost:,.2f}"
        )

        return total_cost, line_items
