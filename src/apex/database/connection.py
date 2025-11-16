"""
Database connection and session management.

Uses NullPool for stateless operation (Azure Container Apps).
All sessions managed via FastAPI dependency injection.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from apex.config import config


def _create_engine():
    """
    Create database engine with environment-specific configuration.

    For testing environments, uses SQLite in-memory database.
    For production, uses configured Azure SQL with Managed Identity.
    """
    # Check if we're in test mode (TESTING env var or pytest running)
    is_testing = os.environ.get("TESTING", "").lower() in ("1", "true", "yes")

    if is_testing:
        # Use SQLite for testing (same as conftest.py does)
        return create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=config.DEBUG,
            future=True,
        )

    # Production: Use configured database URL
    # This will fail if pyodbc/ODBC driver not installed, which is expected
    return create_engine(
        config.database_url,
        poolclass=NullPool,  # Stateless pattern - no connection pooling
        echo=config.DEBUG,  # Log SQL in debug mode
        future=True,  # Use SQLAlchemy 2.0 style
    )


# Create engine (test-aware)
engine = _create_engine()

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)
