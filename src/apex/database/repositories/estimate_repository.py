"""
Estimate repository with special handling for hierarchical line items.
"""
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select
from decimal import Decimal

from apex.database.repositories.base import BaseRepository
from apex.models.database import (
    Estimate,
    EstimateLineItem,
    EstimateAssumption,
    EstimateExclusion,
    EstimateRiskFactor,
)


class EstimateRepository(BaseRepository[Estimate]):
    """
    Repository for Estimate entity.

    Handles complex transaction for creating estimate with full hierarchy.
    """

    def __init__(self):
        super().__init__(Estimate)

    def create_estimate_with_hierarchy(
        self,
        db: Session,
        estimate: Estimate,
        line_items: List[EstimateLineItem],
        assumptions: List[EstimateAssumption],
        exclusions: List[EstimateExclusion],
        risk_factors: List[EstimateRiskFactor],
    ) -> Estimate:
        """
        Create complete estimate with all related entities in single transaction.

        This method handles the CBS hierarchy linking via wbs_code.

        Args:
            db: Database session
            estimate: Estimate ORM entity (not yet persisted)
            line_items: Flat list of line items with wbs_code and _temp_parent_ref
            assumptions: List of assumption entities
            exclusions: List of exclusion entities
            risk_factors: List of risk factor entities

        Returns:
            Persisted Estimate with all relationships and generated IDs
        """
        # Persist main estimate
        db.add(estimate)
        db.flush()  # Get estimate ID

        # Create line items and build wbs_code -> line_item mapping
        wbs_map: Dict[str, EstimateLineItem] = {}

        # First pass: Create all line items
        for item in line_items:
            item.estimate_id = estimate.id
            db.add(item)
            if item.wbs_code:
                wbs_map[item.wbs_code] = item

        db.flush()  # Generate line item IDs

        # Second pass: Link parent-child relationships using wbs_code
        # MEDIUM FIX (Codex): Fail fast if parent reference is invalid
        for item in line_items:
            parent_wbs = getattr(item, "_temp_parent_ref", None)
            if parent_wbs:
                parent = wbs_map.get(parent_wbs)
                if parent is None:
                    raise ValueError(
                        f"Unknown parent WBS code '{parent_wbs}' for line item: {item.description}. "
                        f"Available WBS codes: {sorted(wbs_map.keys())}"
                    )
                item.parent_line_item_id = parent.id

        # Add assumptions
        for assumption in assumptions:
            assumption.estimate_id = estimate.id
            db.add(assumption)

        # Add exclusions
        for exclusion in exclusions:
            exclusion.estimate_id = estimate.id
            db.add(exclusion)

        # Add risk factors
        for risk_factor in risk_factors:
            risk_factor.estimate_id = estimate.id
            db.add(risk_factor)

        db.flush()
        db.refresh(estimate)
        return estimate

    def get_estimate_with_details(self, db: Session, estimate_id: UUID) -> Optional[Estimate]:
        """
        Get estimate with all related entities eagerly loaded.

        HIGH FIX (Codex): Return Optional[Estimate] for proper type safety.

        Args:
            db: Database session
            estimate_id: Estimate UUID

        Returns:
            Estimate with relationships loaded, or None if not found
        """
        from sqlalchemy.orm import joinedload

        estimate = (
            db.query(Estimate)
            .options(
                joinedload(Estimate.line_items),
                joinedload(Estimate.assumptions),
                joinedload(Estimate.exclusions),
                joinedload(Estimate.risk_factors),
            )
            .filter(Estimate.id == estimate_id)
            .one_or_none()
        )
        return estimate

    def get_by_estimate_number(
        self,
        db: Session,
        estimate_number: str,
    ) -> Optional[Estimate]:
        """
        Get estimate by estimate number (unique identifier).

        Args:
            db: Database session
            estimate_number: Estimate number (e.g., "EST-2024-001")

        Returns:
            Estimate or None if not found
        """
        query = select(Estimate).where(Estimate.estimate_number == estimate_number)
        return db.execute(query).scalar_one_or_none()

    def get_by_project_id(
        self,
        db: Session,
        project_id: UUID,
        aace_class: Optional[str] = None,
    ) -> List[Estimate]:
        """
        Get all estimates for a project.

        Args:
            db: Database session
            project_id: Project UUID
            aace_class: Optional filter by AACE class

        Returns:
            List of estimates for the project
        """
        from apex.models.enums import AACEClass

        query = select(Estimate).where(Estimate.project_id == project_id)

        if aace_class:
            # Convert string to enum if needed
            if isinstance(aace_class, str):
                aace_class = AACEClass(aace_class)
            query = query.where(Estimate.aace_class == aace_class)

        # Order by creation date (newest first)
        query = query.order_by(Estimate.created_at.desc())

        return db.execute(query).scalars().all()

    def get_paginated(
        self,
        db: Session,
        project_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Estimate], int, bool, bool]:
        """
        Get paginated estimates for a project.

        Args:
            db: Database session
            project_id: Project UUID
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (items, total, has_next, has_prev)
        """
        query = (
            select(Estimate)
            .where(Estimate.project_id == project_id)
            .order_by(Estimate.created_at.desc())
        )

        return self.paginate(db, query, page, page_size)

    def get_line_items(
        self,
        db: Session,
        estimate_id: UUID,
        parent_only: bool = False,
    ) -> List[EstimateLineItem]:
        """
        Get line items for an estimate.

        Args:
            db: Database session
            estimate_id: Estimate UUID
            parent_only: If True, return only parent (summary) rows

        Returns:
            List of line items
        """
        query = select(EstimateLineItem).where(EstimateLineItem.estimate_id == estimate_id)

        if parent_only:
            # Parent rows have no parent_line_item_id
            query = query.where(EstimateLineItem.parent_line_item_id.is_(None))

        # Order by WBS code for hierarchical display
        query = query.order_by(EstimateLineItem.wbs_code)

        return db.execute(query).scalars().all()

    def get_line_item_hierarchy(
        self,
        db: Session,
        estimate_id: UUID,
    ) -> List[EstimateLineItem]:
        """
        Get line items with parent-child relationships loaded.

        Args:
            db: Database session
            estimate_id: Estimate UUID

        Returns:
            List of line items with children relationships loaded
        """
        from sqlalchemy.orm import joinedload

        query = (
            select(EstimateLineItem)
            .options(
                joinedload(EstimateLineItem.children),
                joinedload(EstimateLineItem.parent),
            )
            .where(EstimateLineItem.estimate_id == estimate_id)
            .order_by(EstimateLineItem.wbs_code)
        )

        return db.execute(query).scalars().unique().all()
