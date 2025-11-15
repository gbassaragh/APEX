"""
Database connection and session management.

Uses NullPool for stateless operation (Azure Container Apps).
All sessions managed via FastAPI dependency injection.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from apex.config import config

# Create engine with NullPool for stateless/serverless patterns
# This works well for Azure Container Apps where connections shouldn't be pooled
engine = create_engine(
    config.database_url,
    poolclass=NullPool,  # Stateless pattern - no connection pooling
    echo=config.DEBUG,  # Log SQL in debug mode
    future=True,  # Use SQLAlchemy 2.0 style
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)
