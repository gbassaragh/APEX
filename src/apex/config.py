"""
Configuration module using pydantic-settings for environment-based configuration.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class Config(BaseSettings):
    """
    Application configuration loaded from environment variables.

    All Azure services use Managed Identity authentication.
    No hardcoded secrets or API keys allowed.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "APEX"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"  # "development", "staging", "production"
    DEBUG: bool = False

    # Azure SQL
    AZURE_SQL_SERVER: str
    AZURE_SQL_DATABASE: str
    AZURE_SQL_DRIVER: str = "ODBC Driver 18 for SQL Server"

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_DEPLOYMENT: str
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Azure Document Intelligence (REQUIRED)
    AZURE_DI_ENDPOINT: str  # CRITICAL: Required for document parsing operations

    # Storage
    AZURE_STORAGE_ACCOUNT: str
    AZURE_STORAGE_CONTAINER_UPLOADS: str = "uploads"
    AZURE_STORAGE_CONTAINER_PROCESSED: str = "processed"

    # Key Vault (optional)
    AZURE_KEY_VAULT_URL: Optional[str] = None

    # API
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # App Insights
    AZURE_APPINSIGHTS_CONNECTION_STRING: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    # Monte Carlo defaults
    DEFAULT_MONTE_CARLO_ITERATIONS: int = 10000
    DEFAULT_CONFIDENCE_LEVEL: float = 0.80

    # Azure Document Intelligence Configuration
    AZURE_DI_TIMEOUT: int = 60  # Maximum polling time in seconds
    AZURE_DI_POLL_INTERVAL: int = 2  # Polling interval in seconds
    AZURE_DI_CIRCUIT_BREAKER_THRESHOLD: int = 5  # Failures before circuit opens
    AZURE_DI_CIRCUIT_BREAKER_TIMEOUT: int = 60  # Seconds before retry

    # LLM Configuration
    LLM_MAX_CONTEXT_TOKENS: int = 128000  # GPT-4 context window
    LLM_RESPONSE_BUFFER_TOKENS: int = 4000  # Reserve for response
    LLM_MAX_OUTPUT_TOKENS: int = 4000  # Limit LLM output length

    # LLM Temperature per AACE Class
    LLM_TEMPERATURE_CLASS_5: float = 0.7  # Conceptual - more creative
    LLM_TEMPERATURE_CLASS_4: float = 0.3  # Feasibility - moderate creativity
    LLM_TEMPERATURE_CLASS_3: float = 0.1  # Budget - low creativity
    LLM_TEMPERATURE_CLASS_2: float = 0.0  # Control - deterministic
    LLM_TEMPERATURE_CLASS_1: float = 0.0  # Bid/Check - deterministic

    # Resource Limits (DoS Protection)
    PARSER_MAX_CONCURRENT: int = 5  # Max concurrent parsing operations
    PARSER_MAX_MEMORY_MB: int = 512  # Max memory per document
    PARSER_TIMEOUT_SECONDS: int = 30  # Timeout per document parse

    # Cache Configuration
    # WARNING: "memory" backend is process-local and NOT shared across Uvicorn workers.
    # For production with multiple workers, use Redis or disable caching.
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600  # 1 hour default TTL
    CACHE_BACKEND: str = "memory"  # "memory" (dev only) or "redis" (production)

    # Dead Letter Queue
    DLQ_CONTAINER: str = "dead-letter-queue"

    # Document Upload Limits (DoS Protection)
    MAX_UPLOAD_SIZE_MB: int = 50  # Maximum file size in megabytes
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
        "application/msword",  # .doc
        "application/vnd.ms-excel",  # .xls
        "image/png",
        "image/jpeg",
        "image/tiff",  # Scanned documents
    ]

    @property
    def max_upload_size_bytes(self) -> int:
        """Convert MB to bytes for FastAPI File validation."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def database_url(self) -> str:
        """
        Construct Azure SQL connection string with Managed Identity authentication.

        Returns:
            Connection string for SQLAlchemy with MSI auth
        """
        return (
            f"mssql+pyodbc://@{self.AZURE_SQL_SERVER}/"
            f"{self.AZURE_SQL_DATABASE}"
            f"?driver={self.AZURE_SQL_DRIVER.replace(' ', '+')}"
            f"&Authentication=ActiveDirectoryMsi"
        )


# Global config instance
config = Config()
