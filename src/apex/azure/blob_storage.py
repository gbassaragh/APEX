"""
Azure Blob Storage client with async operations and Managed Identity auth.

CRITICAL: All operations are async and use retry decorator for resilience.
Dead letter queue support for failed document processing.
"""
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from azure.storage.blob.aio import BlobServiceClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError

from apex.config import config
from apex.azure.auth import get_azure_credential
from apex.utils.retry import azure_retry

logger = logging.getLogger(__name__)


class BlobStorageClient:
    """
    Async Azure Blob Storage client with Managed Identity authentication.

    Features:
    - Async operations for non-blocking I/O
    - Automatic retry with exponential backoff
    - Dead letter queue for failed documents
    - Container existence validation
    - Metadata support for audit trails

    Example:
        ```python
        blob_client = BlobStorageClient()
        await blob_client.upload_document(
            container="uploads",
            blob_name="project123/scope.pdf",
            data=pdf_bytes,
            metadata={"project_id": "abc-123", "document_type": "scope"}
        )
        ```
    """

    def __init__(self):
        """
        Initialize blob storage client.

        Client initialization is deferred until first operation to avoid
        blocking during application startup.
        """
        self._service_client: Optional[BlobServiceClient] = None
        self.account_url = f"https://{config.AZURE_STORAGE_ACCOUNT}.blob.core.windows.net"

    async def _get_service_client(self) -> BlobServiceClient:
        """
        Get or create blob service client with Managed Identity.

        Lazy initialization pattern - client created on first use.
        Credential is cached by auth module, so this is efficient.

        Returns:
            BlobServiceClient instance with async support
        """
        if self._service_client is None:
            credential = await get_azure_credential()
            self._service_client = BlobServiceClient(
                account_url=self.account_url,
                credential=credential
            )
            logger.info(f"Initialized BlobServiceClient for {self.account_url}")

        return self._service_client

    @azure_retry
    async def upload_document(
        self,
        container: str,
        blob_name: str,
        data: bytes,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        overwrite: bool = False
    ) -> str:
        """
        Upload document to blob storage with metadata.

        Args:
            container: Container name (e.g., "uploads", "processed")
            blob_name: Blob path (e.g., "project123/scope.pdf")
            data: Binary document content
            metadata: Optional metadata dictionary for audit trail
            content_type: MIME type (e.g., "application/pdf")
            overwrite: Allow overwriting existing blobs

        Returns:
            Full blob path: "container/blob_name"

        Raises:
            ResourceExistsError: If blob exists and overwrite=False
            azure.core.exceptions: Various Azure service errors (retried automatically)

        Example:
            ```python
            blob_path = await client.upload_document(
                container="uploads",
                blob_name="project123/scope.pdf",
                data=pdf_bytes,
                metadata={"project_id": "abc-123", "uploaded_by": "user@example.com"},
                content_type="application/pdf"
            )
            # blob_path = "uploads/project123/scope.pdf"
            ```
        """
        service_client = await self._get_service_client()

        # Get container client and ensure container exists
        container_client = service_client.get_container_client(container)
        await self._ensure_container_exists(container_client)

        # Upload blob with metadata
        blob_client = container_client.get_blob_client(blob_name)

        logger.info(f"Uploading blob: {container}/{blob_name} ({len(data)} bytes)")

        await blob_client.upload_blob(
            data=data,
            metadata=metadata,
            content_settings={
                "content_type": content_type
            } if content_type else None,
            overwrite=overwrite
        )

        blob_path = f"{container}/{blob_name}"
        logger.info(f"Successfully uploaded blob: {blob_path}")

        return blob_path

    @azure_retry
    async def download_document(
        self,
        container: str,
        blob_name: str
    ) -> bytes:
        """
        Download document from blob storage.

        Args:
            container: Container name
            blob_name: Blob path

        Returns:
            Binary document content

        Raises:
            ResourceNotFoundError: If blob doesn't exist
            azure.core.exceptions: Various Azure service errors (retried automatically)

        Example:
            ```python
            pdf_bytes = await client.download_document(
                container="uploads",
                blob_name="project123/scope.pdf"
            )
            ```
        """
        service_client = await self._get_service_client()
        blob_client = service_client.get_blob_client(container=container, blob=blob_name)

        logger.info(f"Downloading blob: {container}/{blob_name}")

        # Download blob to bytes
        stream = await blob_client.download_blob()
        data = await stream.readall()

        logger.info(f"Downloaded blob: {container}/{blob_name} ({len(data)} bytes)")

        return data

    @azure_retry
    async def delete_document(
        self,
        container: str,
        blob_name: str,
        missing_ok: bool = True
    ) -> bool:
        """
        Delete document from blob storage.

        Args:
            container: Container name
            blob_name: Blob path
            missing_ok: If True, don't raise error if blob doesn't exist

        Returns:
            True if deleted, False if not found (when missing_ok=True)

        Raises:
            ResourceNotFoundError: If blob doesn't exist and missing_ok=False
            azure.core.exceptions: Various Azure service errors (retried automatically)

        Example:
            ```python
            deleted = await client.delete_document(
                container="uploads",
                blob_name="project123/scope.pdf"
            )
            ```
        """
        service_client = await self._get_service_client()
        blob_client = service_client.get_blob_client(container=container, blob=blob_name)

        logger.info(f"Deleting blob: {container}/{blob_name}")

        try:
            await blob_client.delete_blob()
            logger.info(f"Deleted blob: {container}/{blob_name}")
            return True
        except ResourceNotFoundError:
            if missing_ok:
                logger.warning(f"Blob not found (missing_ok=True): {container}/{blob_name}")
                return False
            raise

    @azure_retry
    async def get_blob_metadata(
        self,
        container: str,
        blob_name: str
    ) -> Dict[str, str]:
        """
        Get blob metadata.

        Args:
            container: Container name
            blob_name: Blob path

        Returns:
            Metadata dictionary

        Raises:
            ResourceNotFoundError: If blob doesn't exist
            azure.core.exceptions: Various Azure service errors (retried automatically)

        Example:
            ```python
            metadata = await client.get_blob_metadata(
                container="uploads",
                blob_name="project123/scope.pdf"
            )
            # metadata = {"project_id": "abc-123", "document_type": "scope"}
            ```
        """
        service_client = await self._get_service_client()
        blob_client = service_client.get_blob_client(container=container, blob=blob_name)

        properties = await blob_client.get_blob_properties()
        return properties.metadata or {}

    @azure_retry
    async def move_to_dead_letter_queue(
        self,
        source_container: str,
        source_blob: str,
        error_details: Dict[str, Any]
    ) -> str:
        """
        Move failed document to dead letter queue with error metadata.

        Used for documents that fail processing after retry exhaustion.
        Preserves original blob and adds error context for investigation.

        Args:
            source_container: Original container name
            source_blob: Original blob path
            error_details: Error information (ALL fields preserved in metadata)

        Returns:
            DLQ blob path

        Example:
            ```python
            dlq_path = await client.move_to_dead_letter_queue(
                source_container="uploads",
                source_blob="project123/scope.pdf",
                error_details={
                    "error_type": "DocumentIntelligenceTimeout",
                    "error_message": "Analysis exceeded 60s timeout",
                    "timestamp": "2025-01-15T10:30:00Z",
                    "project_id": "abc-123",
                    "filename": "scope.pdf",
                    "operation": "document_parsing"
                }
            )
            ```

        Note:
            DLQ blob names include timestamp and UUID to prevent overwrites
            and preserve audit trail for multiple failure attempts.
        """
        # Download original blob
        data = await self.download_document(source_container, source_blob)

        # Get original metadata
        original_metadata = await self.get_blob_metadata(source_container, source_blob)

        # Build DLQ metadata preserving ALL error_details fields
        dlq_metadata = {
            **original_metadata,
            "dlq_source_container": source_container,
            "dlq_source_blob": source_blob,
        }

        # Add all error_details as dlq_ prefixed metadata (truncate values to Azure limit)
        for key, value in error_details.items():
            metadata_key = f"dlq_{key}"
            metadata_value = str(value)[:1024] if value is not None else ""
            dlq_metadata[metadata_key] = metadata_value

        # Create unique DLQ blob name with timestamp and UUID
        # Format: {container}/{original_path}_{timestamp}_{uuid}
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        blob_name_base = source_blob.replace('/', '-')  # Flatten nested paths
        dlq_blob_name = f"{source_container}/{blob_name_base}_{timestamp}_{unique_id}"

        # Upload to DLQ with combined metadata
        dlq_path = await self.upload_document(
            container=config.DLQ_CONTAINER,
            blob_name=dlq_blob_name,
            data=data,
            metadata=dlq_metadata,
            overwrite=False  # Never overwrite - preserve all failure attempts
        )

        logger.warning(
            f"Moved to DLQ: {source_container}/{source_blob} → {dlq_path}. "
            f"Error: {error_details.get('error_type')}"
        )

        return dlq_path

    async def _ensure_container_exists(self, container_client: ContainerClient) -> None:
        """
        Ensure container exists, create if necessary.

        Args:
            container_client: Container client instance

        Note:
            Container creation is idempotent - safe to call multiple times.
        """
        try:
            await container_client.create_container()
            logger.info(f"Created container: {container_client.container_name}")
        except ResourceExistsError:
            # Container already exists - this is fine
            pass

    async def close(self) -> None:
        """
        Close service client and release resources.

        Should be called during application shutdown.
        """
        if self._service_client is not None:
            await self._service_client.close()
            logger.info("Closed BlobServiceClient")
