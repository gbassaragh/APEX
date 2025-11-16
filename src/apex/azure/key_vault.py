"""
Azure Key Vault async client with Managed Identity authentication.

CRITICAL: This is an async client—always await methods. Intended for startup-time secret
loading, not per-request calls.
"""
import logging
from typing import Optional

from azure.keyvault.secrets.aio import SecretClient

from apex.azure.auth import get_azure_credential

logger = logging.getLogger(__name__)


class KeyVaultClient:
    """
    Async Azure Key Vault client.

    Best practice: fetch secrets at startup and cache them in process config/env.
    """

    def __init__(self):
        self._client: Optional[SecretClient] = None
        self._vault_url: Optional[str] = None

    async def _get_client(self, vault_url: str) -> SecretClient:
        """Get or create an async SecretClient instance."""
        if self._client is None or self._vault_url != vault_url:
            credential = await get_azure_credential()
            self._client = SecretClient(vault_url=vault_url, credential=credential)
            self._vault_url = vault_url
            logger.info("Initialized async KeyVault client for %s", vault_url)

        return self._client

    async def get_secret(self, vault_url: str, secret_name: str) -> str:
        """Retrieve a secret value."""
        client = await self._get_client(vault_url)
        secret = await client.get_secret(secret_name)
        logger.debug("Retrieved secret: %s", secret_name)
        return secret.value

    async def set_secret(self, vault_url: str, secret_name: str, value: str) -> None:
        """Set a secret value."""
        client = await self._get_client(vault_url)
        await client.set_secret(secret_name, value)
        logger.info("Set secret: %s", secret_name)

    async def close(self) -> None:
        """Close underlying client."""
        if self._client is not None:
            await self._client.close()
            logger.info("Closed KeyVault client")
