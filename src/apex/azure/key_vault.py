"""
Azure Key Vault client wrapper (optional).

CRITICAL: This is a synchronous client. For async operations, create async version.
"""
from typing import Optional
from azure.keyvault.secrets import SecretClient
from apex.config import config
from apex.azure.auth import get_azure_credential_sync
from apex.utils.retry import azure_retry


class KeyVaultClient:
    """
    Synchronous wrapper for Azure Key Vault operations.

    Used for retrieving secrets if needed (e.g., third-party API keys).
    Not required for Azure service authentication (uses Managed Identity).

    Note: Uses synchronous credential getter since this class is not async.
          For async operations, create KeyVaultClientAsync variant.
    """

    def __init__(self):
        """Initialize Key Vault client with Managed Identity."""
        if not config.AZURE_KEY_VAULT_URL:
            raise ValueError("AZURE_KEY_VAULT_URL not configured")

        # Use sync credential getter (not async)
        credential = get_azure_credential_sync()
        self.client = SecretClient(vault_url=config.AZURE_KEY_VAULT_URL, credential=credential)

    @azure_retry
    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Retrieve secret from Key Vault.

        Args:
            secret_name: Name of the secret

        Returns:
            Secret value or None if not found
        """
        try:
            secret = self.client.get_secret(secret_name)
            return secret.value
        except Exception:
            return None
