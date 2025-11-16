"""
Cost lookup service for production cost database queries.

Replaces hardcoded values in CostDatabaseService with database-backed lookups plus
predictable fallbacks when data is missing.
"""
import logging
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from apex.models.database import CostCode

logger = logging.getLogger(__name__)


class CostLookupService:
    """Service for looking up cost data from database with fallbacks."""

    def get_cost_by_code(self, db: Session, code: str) -> Optional[CostCode]:
        """Look up cost code by code string."""
        query = select(CostCode).where(CostCode.code == code)
        return db.execute(query).scalar_one_or_none()

    def get_all_codes(self, db: Session) -> Dict[str, CostCode]:
        """Get all cost codes as a dict keyed by code."""
        codes = db.execute(select(CostCode)).scalars().all()
        return {cc.code: cc for cc in codes}

    def get_unit_cost(self, db: Session, cost_code: CostCode) -> Optional[Decimal]:
        """
        Determine unit cost from persisted values.

        Prefers explicit unit_cost_total, otherwise sums material/labor/other if present.
        """
        if cost_code is None:
            return None

        if cost_code.unit_cost_total is not None:
            return Decimal(cost_code.unit_cost_total)

        parts = [
            cost_code.unit_cost_material,
            cost_code.unit_cost_labor,
            cost_code.unit_cost_other,
        ]
        if any(part is not None for part in parts):
            total = sum(Decimal(part) for part in parts if part is not None)
            return total

        return None

    def estimate_tangent_tower_cost(
        self, db: Session, voltage_level: int, quantity: float
    ) -> Decimal:
        """Estimate tangent tower cost using DB data when available, else parametric fallback."""
        code = self._tower_code(voltage_level)
        cost_code = self.get_cost_by_code(db, code) if code else None
        unit_cost = self.get_unit_cost(db, cost_code)
        if unit_cost is None:
            return self._parametric_tower_estimate(voltage_level, quantity)
        return Decimal(str(quantity * float(unit_cost)))

    def fallback_unit_cost(self, description: str) -> Decimal:
        """
        Fallback heuristics for unit cost by description.

        Keeps deterministic values to avoid blocking workflows when data is missing.
        """
        desc = description.lower()
        if "tangent" in desc:
            return Decimal("75000.00")
        if "dead" in desc:
            return Decimal("95000.00")
        if "conductor" in desc:
            return Decimal("25.00")
        if "foundation" in desc:
            return Decimal("15000.00")
        if "clearing" in desc:
            return Decimal("10000.00")
        return Decimal("10000.00")

    def _tower_code(self, voltage_level: int) -> Optional[str]:
        """Map voltage to a canonical tangent tower code."""
        if voltage_level >= 345:
            return "26.01.01.345"
        if voltage_level >= 230:
            return "26.01.01.230"
        if voltage_level >= 115:
            return "26.01.01.115"
        if voltage_level >= 69:
            return "26.01.01.69"
        return None

    def _parametric_tower_estimate(self, voltage_level: int, quantity: float) -> Decimal:
        """Simple parametric tower estimate when no database value exists."""
        base_cost = 50000
        voltage_factor = max(voltage_level, 1) / 100
        unit_cost = base_cost * voltage_factor
        return Decimal(str(quantity * unit_cost))
