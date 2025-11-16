"""
Unit tests for configuration management.

Tests Pydantic settings and Azure Managed Identity connection string construction.
"""
import pytest
from pydantic import ValidationError

from apex.config import Config


class TestConfigValidation:
    """Test configuration validation."""

    def test_config_requires_mandatory_fields(self, monkeypatch):
        """Test Config raises validation error for missing required fields."""
        # Clear all environment variables that would satisfy Config
        required_vars = [
            "AZURE_SQL_SERVER",
            "AZURE_SQL_DATABASE",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_DEPLOYMENT",
            "AZURE_DI_ENDPOINT",
            "AZURE_STORAGE_ACCOUNT",
            "AZURE_AD_TENANT_ID",
            "AZURE_AD_CLIENT_ID",
        ]
        for var in required_vars:
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(ValidationError) as exc_info:
            Config(
                _env_file=None,  # Prevent loading from .env
            )

        errors = exc_info.value.errors()
        required_fields = {error["loc"][0] for error in errors}

        # Check critical Azure fields are required
        assert "AZURE_SQL_SERVER" in required_fields
        assert "AZURE_SQL_DATABASE" in required_fields
        assert "AZURE_OPENAI_ENDPOINT" in required_fields
        assert "AZURE_OPENAI_DEPLOYMENT" in required_fields
        assert "AZURE_STORAGE_ACCOUNT" in required_fields

    def test_config_with_valid_minimal_settings(self):
        """Test Config with minimum required settings."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test.database.windows.net",
            AZURE_SQL_DATABASE="test_db",
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
        )

        assert config.AZURE_SQL_SERVER == "test.database.windows.net"
        assert config.AZURE_SQL_DATABASE == "test_db"
        assert config.AZURE_OPENAI_ENDPOINT == "https://test.openai.azure.com/"

    def test_config_default_values(self):
        """Test Config applies default values correctly."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test.database.windows.net",
            AZURE_SQL_DATABASE="test_db",
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
        )

        # Application defaults
        assert config.APP_NAME == "APEX"
        assert config.APP_VERSION == "0.1.0"
        assert config.ENVIRONMENT == "development"
        assert config.DEBUG is False

        # Azure defaults
        assert config.AZURE_SQL_DRIVER == "ODBC Driver 18 for SQL Server"
        assert config.AZURE_OPENAI_API_VERSION == "2024-02-15-preview"
        assert config.AZURE_STORAGE_CONTAINER_UPLOADS == "uploads"
        assert config.AZURE_STORAGE_CONTAINER_PROCESSED == "processed"

        # API defaults
        assert config.API_V1_PREFIX == "/api/v1"
        assert "http://localhost:3000" in config.CORS_ORIGINS

        # Monte Carlo defaults
        assert config.DEFAULT_MONTE_CARLO_ITERATIONS == 10000
        assert config.DEFAULT_CONFIDENCE_LEVEL == 0.80

        # Log level default
        assert config.LOG_LEVEL == "INFO"


class TestDatabaseURL:
    """Test database URL construction."""

    def test_database_url_managed_identity_format(self):
        """Test database_url property generates correct Managed Identity connection string."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test-server.database.windows.net",
            AZURE_SQL_DATABASE="apex_db",
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
        )

        url = config.database_url

        # Check critical components
        assert url.startswith("mssql+pyodbc://@")
        assert "test-server.database.windows.net" in url
        assert "apex_db" in url
        assert "Authentication=ActiveDirectoryMsi" in url
        assert "driver=ODBC+Driver+18+for+SQL+Server" in url

        # Should NOT contain username or password
        assert ":" not in url.split("@")[0].split("//")[1]  # No credentials before @

    def test_database_url_driver_url_encoding(self):
        """Test database URL properly encodes driver name."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test.database.windows.net",
            AZURE_SQL_DATABASE="test_db",
            AZURE_SQL_DRIVER="ODBC Driver 18 for SQL Server",  # Has spaces
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
        )

        url = config.database_url

        # Spaces should be replaced with '+'
        assert "driver=ODBC+Driver+18+for+SQL+Server" in url
        assert "driver=ODBC Driver 18 for SQL Server" not in url

    def test_database_url_custom_driver(self):
        """Test database URL with custom driver."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test.database.windows.net",
            AZURE_SQL_DATABASE="test_db",
            AZURE_SQL_DRIVER="ODBC Driver 17 for SQL Server",
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
        )

        url = config.database_url
        assert "driver=ODBC+Driver+17+for+SQL+Server" in url


class TestOptionalFields:
    """Test optional configuration fields."""

    def test_optional_key_vault_url(self):
        """Test AZURE_KEY_VAULT_URL is optional."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test.database.windows.net",
            AZURE_SQL_DATABASE="test_db",
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
        )

        assert config.AZURE_KEY_VAULT_URL is None

    def test_optional_app_insights_connection_string(self):
        """Test AZURE_APPINSIGHTS_CONNECTION_STRING is optional."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test.database.windows.net",
            AZURE_SQL_DATABASE="test_db",
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
        )

        assert config.AZURE_APPINSIGHTS_CONNECTION_STRING is None

    def test_optional_fields_can_be_set(self):
        """Test optional fields accept values when provided."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test.database.windows.net",
            AZURE_SQL_DATABASE="test_db",
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
            AZURE_KEY_VAULT_URL="https://test-kv.vault.azure.net/",
            AZURE_APPINSIGHTS_CONNECTION_STRING="InstrumentationKey=test-key",
        )

        assert config.AZURE_KEY_VAULT_URL == "https://test-kv.vault.azure.net/"
        assert config.AZURE_APPINSIGHTS_CONNECTION_STRING == "InstrumentationKey=test-key"


class TestEnvironmentVariables:
    """Test environment variable loading."""

    def test_config_case_sensitivity(self):
        """Test configuration keys are case-sensitive."""
        import os

        # Set environment variable
        os.environ["AZURE_SQL_SERVER"] = "env-test-server.database.windows.net"
        os.environ["AZURE_SQL_DATABASE"] = "env_test_db"
        os.environ["AZURE_OPENAI_ENDPOINT"] = "https://env-test.openai.azure.com/"
        os.environ["AZURE_OPENAI_DEPLOYMENT"] = "env-gpt-4"
        os.environ["AZURE_STORAGE_ACCOUNT"] = "envteststorage"

        try:
            config = Config(_env_file=None)

            assert config.AZURE_SQL_SERVER == "env-test-server.database.windows.net"
            assert config.AZURE_SQL_DATABASE == "env_test_db"

        finally:
            # Cleanup
            del os.environ["AZURE_SQL_SERVER"]
            del os.environ["AZURE_SQL_DATABASE"]
            del os.environ["AZURE_OPENAI_ENDPOINT"]
            del os.environ["AZURE_OPENAI_DEPLOYMENT"]
            del os.environ["AZURE_STORAGE_ACCOUNT"]

    def test_config_cors_origins_list_parsing(self):
        """Test CORS_ORIGINS parses as list."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test.database.windows.net",
            AZURE_SQL_DATABASE="test_db",
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
        )

        assert isinstance(config.CORS_ORIGINS, list)
        assert len(config.CORS_ORIGINS) >= 2


class TestSecurityValidation:
    """Test security-related configuration validation."""

    def test_no_hardcoded_secrets_in_defaults(self):
        """Test Config has no hardcoded secrets in default values."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test.database.windows.net",
            AZURE_SQL_DATABASE="test_db",
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
        )

        # Database URL should use Managed Identity (no password/key)
        db_url = config.database_url
        assert "password" not in db_url.lower()
        assert "pwd" not in db_url.lower()
        assert "secret" not in db_url.lower()
        assert "key=" not in db_url.lower()

        # Should use Managed Identity authentication
        assert "ActiveDirectoryMsi" in db_url

    def test_managed_identity_authentication_only(self):
        """Test database connection uses Managed Identity exclusively."""
        config = Config(
            _env_file=None,
            AZURE_SQL_SERVER="test.database.windows.net",
            AZURE_SQL_DATABASE="test_db",
            AZURE_OPENAI_ENDPOINT="https://test.openai.azure.com/",
            AZURE_OPENAI_DEPLOYMENT="gpt-4",
            AZURE_STORAGE_ACCOUNT="teststorageaccount",
        )

        db_url = config.database_url

        # Should have MSI authentication
        assert "Authentication=ActiveDirectoryMsi" in db_url

        # Should NOT have credentials
        assert "@" in db_url  # Has @ separator
        # But no credentials before @
        protocol_and_auth = db_url.split("//")[1].split("@")[0]
        assert protocol_and_auth == ""  # Empty = no username:password
