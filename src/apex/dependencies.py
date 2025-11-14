"""
FastAPI dependency injection configuration.

CRITICAL: This module defines the session management pattern.
All database operations MUST use the get_db() dependency.
"""
from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session
import logging

from apex.database.connection import SessionLocal

logger = logging.getLogger(__name__)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions with proper transaction handling.

    CRITICAL PATTERN - DO NOT MODIFY WITHOUT REVIEW:
    - Opens a session at request start
    - Yields session for endpoint use
    - Commits BEFORE response is sent (allows error reporting)
    - Rolls back on error
    - Always closes the session

    This pattern ensures:
    1. One session per request
    2. Commit happens before response (errors can be reported to client)
    3. Automatic rollback on error
    4. No leaked connections

    Note: Endpoints should NOT call commit/rollback directly.
    The dependency manages the full transaction lifecycle.

    Yields:
        Database session for request scope
    """
    db = SessionLocal()
    try:
        yield db
        # Commit BEFORE response is sent so errors can be reported
        db.commit()
    except Exception as exc:
        logger.error("Database transaction failed: %s", exc)
        db.rollback()
        raise
    finally:
        db.close()


# Additional dependencies can be added here (current_user, permissions, etc.)
