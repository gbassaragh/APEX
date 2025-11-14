"""
Base repository with common CRUD operations and pagination helpers.
"""
from typing import Generic, TypeVar, Type, List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from uuid import UUID

from apex.models.database import Base


ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository providing common CRUD operations.

    Repositories receive db: Session via dependency injection.
    They NEVER instantiate SessionLocal() directly.
    """

    def __init__(self, model: Type[ModelType]):
        """
        Initialize repository with model class.

        Args:
            model: SQLAlchemy model class
        """
        self.model = model

    def get(self, db: Session, id: UUID) -> Optional[ModelType]:
        """
        Get entity by ID.

        Args:
            db: Database session (injected)
            id: Entity UUID

        Returns:
            Entity or None if not found
        """
        return db.get(self.model, id)

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[ModelType], int]:
        """
        Get multiple entities with pagination.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filter conditions

        Returns:
            Tuple of (items, total_count)
        """
        query = select(self.model)

        # Apply filters if provided
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar()

        # Apply pagination
        query = query.offset(skip).limit(limit)
        items = db.execute(query).scalars().all()

        return items, total

    def create(self, db: Session, obj_in: Dict[str, Any]) -> ModelType:
        """
        Create new entity.

        Args:
            db: Database session
            obj_in: Dictionary of attributes

        Returns:
            Created entity
        """
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.flush()  # Generate ID without committing
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: ModelType, obj_in: Dict[str, Any]) -> ModelType:
        """
        Update existing entity.

        Args:
            db: Database session
            db_obj: Existing entity
            obj_in: Dictionary of attributes to update

        Returns:
            Updated entity
        """
        for key, value in obj_in.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)

        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: UUID) -> bool:
        """
        Delete entity by ID.

        Args:
            db: Database session
            id: Entity UUID

        Returns:
            True if deleted, False if not found
        """
        obj = db.get(self.model, id)
        if obj:
            db.delete(obj)
            db.flush()
            return True
        return False

    def paginate(
        self,
        db: Session,
        query,
        page: int,
        page_size: int,
    ) -> tuple[List[ModelType], int, bool, bool]:
        """
        Pagination helper for consistent pagination across repositories.

        Args:
            db: Database session
            query: SQLAlchemy query to paginate
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (items, total, has_next, has_prev)
        """
        # Ensure page is at least 1
        page = max(1, page)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = db.execute(count_query).scalar()

        # Calculate pagination metadata
        has_prev = page > 1
        has_next = (page * page_size) < total

        # Apply pagination
        offset = (page - 1) * page_size
        paginated_query = query.offset(offset).limit(page_size)
        items = db.execute(paginated_query).scalars().all()

        return items, total, has_next, has_prev
