"""
Azure authentication module with Managed Identity support.

CRITICAL: Async-safe credential caching using asyncio.Lock.
Prevents blocking the FastAPI event loop during initialization.
"""
import asyncio
import logging
from typing import Optional
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)

# Module-level credential cache (async-safe)
_credential: Optional[DefaultAzureCredential] = None
_credential_lock = asyncio.Lock()
_init_complete = False  # Flag to avoid lock overhead after initialization


async def get_azure_credential() -> DefaultAzureCredential:
    """
    Get or create Azure Managed Identity credential (async-safe singleton).

    Uses asyncio.Lock for event-loop-safe initialization.
    Double-check pattern avoids lock overhead after first initialization.

    Credential hierarchy (DefaultAzureCredential attempts in order):
    1. EnvironmentCredential - for local development with env vars
    2. ManagedIdentityCredential - for Azure deployments (production)
    3. AzureCliCredential - for local dev with Azure CLI login
    4. Visual Studio Code Credential - for VS Code Azure extension

    Returns:
        DefaultAzureCredential instance (cached after first call)

    Raises:
        azure.identity.CredentialUnavailableError: If no credential source is available

    Example:
        ```python
        from apex.azure.auth import get_azure_credential

        credential = await get_azure_credential()
        blob_client = BlobServiceClient(account_url=..., credential=credential)
        ```

    Note:
        This function MUST be called with await in async context.
        Do NOT use threading.Lock version in FastAPI async endpoints.
    """
    global _credential, _init_complete

    # Fast path - credential already initialized (no lock needed)
    if _init_complete:
        return _credential

    # Slow path - async-safe initialization with lock
    async with _credential_lock:
        # Double-check: another coroutine may have initialized while we waited
        if _credential is None:
            logger.info("Initializing Azure DefaultAzureCredential (async, first access)")
            try:
                # Use async DefaultAzureCredential to avoid blocking event loop
                _credential = DefaultAzureCredential()
                _init_complete = True
                logger.info(
                    "Azure credential initialized successfully. "
                    "Credential will be cached for subsequent requests."
                )
            except Exception as e:
                logger.error(
                    f"Failed to initialize Azure credential: {e}. "
                    "Ensure Managed Identity is enabled or Azure CLI is authenticated."
                )
                raise

    return _credential


async def reset_credential() -> None:
    """
    Reset cached credential (primarily for testing).

    CAUTION: This will force re-initialization on next get_azure_credential() call.
    Use only in test scenarios or when credential needs to be refreshed.

    Must be called with await in async context.
    """
    global _credential, _init_complete

    async with _credential_lock:
        if _credential is not None:
            logger.warning("Resetting cached Azure credential")
            if hasattr(_credential, 'close'):
                await _credential.close()  # Clean up async resources
            _credential = None
            _init_complete = False


# Synchronous version for non-async contexts (e.g., script initialization)
# WARNING: This will block. Use only during application startup, not in request handlers.
def get_azure_credential_sync() -> DefaultAzureCredential:
    """
    Synchronous credential getter for startup/initialization.

    WARNING: This blocks the thread. Do NOT use in async request handlers.
    Use get_azure_credential() (async version) in FastAPI endpoints.

    Only use this during application startup or in synchronous scripts.
    """
    from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential

    logger.warning(
        "Using synchronous credential initialization. "
        "This will block. Prefer async get_azure_credential() in request handlers."
    )
    return SyncDefaultAzureCredential()
