"""
Mock Azure services for testing.

Provides:
- MockBlobStorageClient - In-memory blob storage
- MockDocumentParser - Simulated Azure Document Intelligence
- MockLLMOrchestrator - Simulated Azure OpenAI
"""
import asyncio
from typing import Any, Dict, Optional

from apex.models.enums import AACEClass
from apex.utils.errors import BusinessRuleViolation

# ============================================================================
# Mock Blob Storage
# ============================================================================


class MockBlobStorageClient:
    """
    Mock Azure Blob Storage client for testing.

    Stores blobs in memory (not persistent across test runs).
    """

    def __init__(self):
        self._blobs: Dict[str, bytes] = {}  # {container/blob_name: content}
        self._metadata: Dict[str, Dict[str, str]] = {}
        self._upload_count = 0
        self._download_count = 0
        self._delete_count = 0

    async def upload_blob(
        self,
        container: str,
        blob_name: str,
        data: bytes,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload blob to mock storage."""
        key = f"{container}/{blob_name}"
        self._blobs[key] = data
        self._metadata[key] = metadata or {}
        self._upload_count += 1
        return key

    async def download_blob(self, container: str, blob_name: str) -> bytes:
        """Download blob from mock storage."""
        key = f"{container}/{blob_name}"
        if key not in self._blobs:
            raise Exception(f"Blob not found: {key}")
        self._download_count += 1
        return self._blobs[key]

    async def delete_blob(self, container: str, blob_name: str) -> None:
        """Delete blob from mock storage."""
        key = f"{container}/{blob_name}"
        if key in self._blobs:
            del self._blobs[key]
            del self._metadata[key]
        self._delete_count += 1

    async def move_to_dead_letter_queue(
        self,
        source_container: str,
        source_blob: str,
        error_details: Dict[str, Any],
    ) -> str:
        """Move blob to dead letter queue (mock)."""
        source_key = f"{source_container}/{source_blob}"
        dlq_key = f"dead-letter-queue/{source_blob}"

        if source_key in self._blobs:
            self._blobs[dlq_key] = self._blobs[source_key]
            self._metadata[dlq_key] = {**self._metadata.get(source_key, {}), **error_details}
            del self._blobs[source_key]
            del self._metadata[source_key]

        return dlq_key

    def blob_exists(self, container: str, blob_name: str) -> bool:
        """Check if blob exists."""
        key = f"{container}/{blob_name}"
        return key in self._blobs

    def get_stats(self) -> Dict[str, int]:
        """Get operation statistics."""
        return {
            "uploads": self._upload_count,
            "downloads": self._download_count,
            "deletes": self._delete_count,
            "blobs_stored": len(self._blobs),
        }

    async def close(self):
        """Close client (no-op for mock)."""
        pass


# ============================================================================
# Mock Document Parser
# ============================================================================


class MockDocumentParser:
    """
    Mock Azure Document Intelligence parser for testing.

    Allows configuring parse results and error conditions.
    """

    def __init__(self):
        self._parse_result: Optional[Dict[str, Any]] = None
        self._circuit_breaker_open = False
        self._timeout = False
        self._parse_count = 0

    def set_parse_result(self, result: Dict[str, Any]):
        """Set the structured content to return on next parse."""
        self._parse_result = result
        self._circuit_breaker_open = False
        self._timeout = False

    def set_circuit_breaker_open(self, is_open: bool):
        """Simulate circuit breaker state."""
        self._circuit_breaker_open = is_open

    def set_timeout(self, timeout: bool):
        """Simulate parsing timeout."""
        self._timeout = timeout

    async def parse_document(
        self, document_bytes: bytes, filename: str, blob_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parse document (mock implementation)."""
        self._parse_count += 1

        # Simulate circuit breaker open
        if self._circuit_breaker_open:
            raise BusinessRuleViolation(
                message="Azure Document Intelligence circuit breaker is OPEN",
                code="CIRCUIT_BREAKER_OPEN",
            )

        # Simulate timeout
        if self._timeout:
            await asyncio.sleep(0.1)  # Small delay to simulate timeout
            raise TimeoutError(f"Document parsing timeout for {filename}")

        # Return configured result or default
        if self._parse_result:
            return self._parse_result

        # Default parse result (minimal valid structure)
        return {
            "filename": filename,
            "pages": [
                {
                    "page_number": 1,
                    "width": 8.5,
                    "height": 11,
                    "unit": "inch",
                    "lines": [{"content": "Test document content", "polygon": None}],
                }
            ],
            "tables": [],
            "paragraphs": [{"content": "Test paragraph", "role": None}],
            "metadata": {
                "page_count": 1,
                "model_id": "prebuilt-layout",
                "api_version": "2024-02-15-preview",
            },
        }

    def get_stats(self) -> Dict[str, int]:
        """Get operation statistics."""
        return {
            "parse_count": self._parse_count,
        }

    async def close(self):
        """Close client (no-op for mock)."""
        pass


# ============================================================================
# Mock LLM Orchestrator
# ============================================================================


class MockLLMOrchestrator:
    """
    Mock Azure OpenAI LLM orchestrator for testing.

    Allows configuring validation results and error conditions.
    """

    def __init__(self):
        self._validation_result: Optional[Dict[str, Any]] = None
        self._error_message: Optional[str] = None
        self._validate_count = 0
        self.last_aace_class: Optional[AACEClass] = None
        self.last_document_type: Optional[str] = None

    def set_validation_result(self, result: Dict[str, Any]):
        """Set the validation result to return on next call."""
        self._validation_result = result
        self._error_message = None

    def set_error(self, message: str):
        """Simulate LLM validation error."""
        self._error_message = message
        self._validation_result = None

    async def validate_document(
        self,
        aace_class: AACEClass,
        document_type: str,
        structured_content: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate document (mock implementation)."""
        self._validate_count += 1
        self.last_aace_class = aace_class
        self.last_document_type = document_type

        # Simulate error
        if self._error_message:
            raise BusinessRuleViolation(message=self._error_message, code="LLM_VALIDATION_ERROR")

        # Return configured result or default
        if self._validation_result:
            return self._validation_result

        # Default validation result (document passes)
        return {
            "completeness_score": 75,
            "issues": [],
            "recommendations": ["Document appears suitable for estimation"],
            "suitable_for_estimation": True,
        }

    async def generate_narrative(
        self,
        aace_class: AACEClass,
        project: Any,
        base_cost: float,
        risk_results: Dict[str, Any],
        line_item_summary: Dict[str, Any],
    ) -> str:
        """Generate estimate narrative (mock implementation)."""
        return f"Test narrative for {project.project_name} with base cost ${base_cost:,.2f}"

    def get_stats(self) -> Dict[str, int]:
        """Get operation statistics."""
        return {
            "validate_count": self._validate_count,
        }

    async def close(self):
        """Close client (no-op for mock)."""
        pass
