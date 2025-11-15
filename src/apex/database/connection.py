"""
Database connection and session management.

Uses NullPool for stateless operation (Azure Container Apps).
All sessions managed via FastAPI dependency injection.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from apex.config import config


# Lazy initialization for testing
_engine = None
_session_factory = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        if config is None:
            raise RuntimeError("Config not initialized. Cannot create database engine.")
        _engine = create_engine(
            config.database_url,
            poolclass=NullPool,  # Stateless pattern - no connection pooling
            echo=config.DEBUG,   # Log SQL in debug mode
            future=True,         # Use SQLAlchemy 2.0 style
        )
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
            future=True,
        )
    return _session_factory


# For backward compatibility, export as module-level variables
# These will be lazily initialized when accessed
def _get_engine_compat():
    return get_engine()


def _get_session_local_compat():
    return get_session_factory()


# Only create engine/session if not in test mode
if config is not None:
    engine = get_engine()
    SessionLocal = get_session_factory()
else:
    # During tests, these will need to be mocked or created with test config
    engine = None  # type: ignore
    SessionLocal = None  # type: ignore
