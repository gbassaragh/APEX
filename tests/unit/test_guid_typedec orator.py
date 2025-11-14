"""
Unit tests for GUID TypeDecorator cross-database compatibility.

Tests ensure GUID type works correctly across:
- Azure SQL Server (mssql)
- PostgreSQL
- SQLite (for testing)
"""
import uuid
import pytest
from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.pool import StaticPool

from apex.models.database import GUID


# Test models
Base = declarative_base()


class TestModel(Base):
    """Test model with GUID primary key."""
    __tablename__ = "test_table"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(100))


@pytest.fixture
def sqlite_engine():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


class TestGUIDTypeDecorator:
    """Test GUID TypeDecorator behavior."""

    def test_guid_generation_default(self, sqlite_engine):
        """Test automatic UUID generation via default."""
        with Session(sqlite_engine) as session:
            test_obj = TestModel(name="test1")
            session.add(test_obj)
            session.commit()

            assert test_obj.id is not None
            assert isinstance(test_obj.id, uuid.UUID)

    def test_guid_explicit_assignment(self, sqlite_engine):
        """Test explicit UUID assignment."""
        test_uuid = uuid.uuid4()

        with Session(sqlite_engine) as session:
            test_obj = TestModel(id=test_uuid, name="test2")
            session.add(test_obj)
            session.commit()

            assert test_obj.id == test_uuid

    def test_guid_query_by_id(self, sqlite_engine):
        """Test querying by GUID."""
        test_uuid = uuid.uuid4()

        with Session(sqlite_engine) as session:
            # Create
            test_obj = TestModel(id=test_uuid, name="test3")
            session.add(test_obj)
            session.commit()

            # Query
            result = session.query(TestModel).filter(TestModel.id == test_uuid).first()
            assert result is not None
            assert result.id == test_uuid
            assert result.name == "test3"

    def test_guid_string_conversion(self, sqlite_engine):
        """Test GUID handles string input correctly."""
        test_uuid = uuid.uuid4()
        test_uuid_str = str(test_uuid)

        with Session(sqlite_engine) as session:
            # Assign as string
            test_obj = TestModel(id=test_uuid_str, name="test4")
            session.add(test_obj)
            session.commit()

            # Should be converted to UUID
            assert isinstance(test_obj.id, uuid.UUID)
            assert test_obj.id == test_uuid

    def test_guid_null_handling(self, sqlite_engine):
        """Test GUID handles None values correctly."""
        # Create model without required ID should fail
        with Session(sqlite_engine) as session:
            test_obj = TestModel(name="test5")
            # Default should provide UUID
            assert test_obj.id is not None

    def test_guid_persistence_and_retrieval(self, sqlite_engine):
        """Test GUID survives round-trip to database."""
        test_uuid = uuid.uuid4()

        with Session(sqlite_engine) as session:
            test_obj = TestModel(id=test_uuid, name="persistence_test")
            session.add(test_obj)
            session.commit()
            object_id = test_obj.id

        # New session
        with Session(sqlite_engine) as session:
            result = session.query(TestModel).filter(TestModel.id == object_id).first()
            assert result is not None
            assert result.id == test_uuid
            assert isinstance(result.id, uuid.UUID)

    def test_guid_dialect_detection_sqlite(self):
        """Test GUID uses CHAR(36) for SQLite."""
        from sqlalchemy.dialects import sqlite

        dialect = sqlite.dialect()
        guid_type = GUID()
        impl = guid_type.load_dialect_impl(dialect)

        # Should be CHAR type for SQLite
        assert impl.length == 36

    def test_guid_process_bind_param_uuid(self):
        """Test GUID bind parameter processing with UUID input."""
        guid_type = GUID()
        test_uuid = uuid.uuid4()

        result = guid_type.process_bind_param(test_uuid, None)
        assert result == str(test_uuid)

    def test_guid_process_bind_param_string(self):
        """Test GUID bind parameter processing with string input."""
        guid_type = GUID()
        test_uuid = uuid.uuid4()

        result = guid_type.process_bind_param(str(test_uuid), None)
        assert result == str(test_uuid)

    def test_guid_process_bind_param_none(self):
        """Test GUID bind parameter processing with None."""
        guid_type = GUID()

        result = guid_type.process_bind_param(None, None)
        assert result is None

    def test_guid_process_result_value_string(self):
        """Test GUID result value processing with string from database."""
        guid_type = GUID()
        test_uuid = uuid.uuid4()

        result = guid_type.process_result_value(str(test_uuid), None)
        assert isinstance(result, uuid.UUID)
        assert result == test_uuid

    def test_guid_process_result_value_uuid(self):
        """Test GUID result value processing with UUID from database."""
        guid_type = GUID()
        test_uuid = uuid.uuid4()

        result = guid_type.process_result_value(test_uuid, None)
        assert isinstance(result, uuid.UUID)
        assert result == test_uuid

    def test_guid_process_result_value_none(self):
        """Test GUID result value processing with None."""
        guid_type = GUID()

        result = guid_type.process_result_value(None, None)
        assert result is None


class TestGUIDDialectSpecific:
    """Test GUID behavior across different database dialects."""

    def test_guid_mssql_dialect(self):
        """Test GUID uses UNIQUEIDENTIFIER for SQL Server."""
        from sqlalchemy.dialects import mssql

        dialect = mssql.dialect()
        guid_type = GUID()
        impl = guid_type.load_dialect_impl(dialect)

        # Should be UNIQUEIDENTIFIER for mssql
        assert impl.__class__.__name__ == "UNIQUEIDENTIFIER"

    def test_guid_postgresql_dialect(self):
        """Test GUID uses UUID for PostgreSQL."""
        from sqlalchemy.dialects import postgresql

        dialect = postgresql.dialect()
        guid_type = GUID()
        impl = guid_type.load_dialect_impl(dialect)

        # Should be UUID for postgresql
        assert impl.__class__.__name__ == "UUID"

    def test_guid_cache_ok(self):
        """Test GUID type is cache-safe."""
        guid_type = GUID()
        assert guid_type.cache_ok is True
