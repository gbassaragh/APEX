"""
Maturity-aware LLM orchestrator for APEX estimation platform.

CRITICAL: Routes prompts/tasks based on AACE class, manages token budgets,
and ensures audit trail compliance. NOT a flat client - intelligent routing.
"""
import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

try:
    import tiktoken
except ImportError:
    tiktoken = None
    logging.warning("tiktoken not installed - token counting will be approximate")

from openai import AsyncAzureOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from apex.azure.auth import get_azure_credential
from apex.config import config
from apex.models.database import Document, Project
from apex.models.enums import AACEClass
from apex.services.llm.prompts import (
    get_assumptions_prompt,
    get_exclusions_prompt,
    get_narrative_prompt,
    get_persona_config,
    get_validation_prompt,
)
from apex.services.llm.validators import (
    extract_json_from_response,
    validate_assumptions_list,
    validate_exclusions_list,
    validate_json_structure,
    validate_narrative_response,
)
from apex.utils.errors import BusinessRuleViolation

logger = logging.getLogger(__name__)


class LLMOrchestrator:
    """
    Maturity-aware LLM orchestration engine.

    Features:
    - AACE class-specific routing (different prompts/temperatures by maturity)
    - Token budget management with smart truncation
    - Response validation and hallucination detection
    - Retry logic for transient failures
    - Comprehensive audit logging

    Example:
        ```python
        orchestrator = LLMOrchestrator()
        narrative = await orchestrator.generate_narrative(
            aace_class=AACEClass.CLASS_3,
            project=project_orm,
            estimate_data={...},
            base_cost=Decimal("1000000.00"),
            risk_results={...}
        )
        ```
    """

    def __init__(self):
        """
        Initialize LLM orchestrator.

        Client initialization is deferred until first use (lazy pattern).
        """
        self._client: Optional[AsyncAzureOpenAI] = None
        self._encoder = None  # Initialized on first token counting call
        self.max_context_tokens = config.LLM_MAX_CONTEXT_TOKENS
        self.response_buffer_tokens = config.LLM_RESPONSE_BUFFER_TOKENS
        self.max_output_tokens = config.LLM_MAX_OUTPUT_TOKENS

    async def _get_client(self) -> AsyncAzureOpenAI:
        """
        Get or create Azure OpenAI client with Managed Identity.

        Lazy initialization pattern - client created on first use.

        Returns:
            AsyncAzureOpenAI client instance
        """
        if self._client is None:
            credential = await get_azure_credential()

            # Azure OpenAI requires azure_ad_token_provider for Managed Identity
            # CRITICAL FIX: Must await the async credential token retrieval
            async def token_provider():
                try:
                    token = await credential.get_token(
                        "https://cognitiveservices.azure.com/.default"
                    )
                    return token.token
                except Exception as exc:
                    logger.error(f"Failed to retrieve Azure AD token: {exc}")
                    raise

            self._client = AsyncAzureOpenAI(
                azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
                api_version=config.AZURE_OPENAI_API_VERSION,
                azure_ad_token_provider=token_provider,
            )

            logger.info(f"Initialized AsyncAzureOpenAI client for {config.AZURE_OPENAI_ENDPOINT}")

        return self._client

    def _get_encoder(self):
        """
        Get or create tiktoken encoder for GPT-4.

        Returns:
            tiktoken encoder or None if not available
        """
        if self._encoder is None and tiktoken is not None:
            self._encoder = tiktoken.encoding_for_model("gpt-4")
        return self._encoder

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text using tiktoken.

        If tiktoken unavailable, uses approximation (1 token ≈ 4 characters).

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        encoder = self._get_encoder()
        if encoder:
            return len(encoder.encode(text))
        else:
            # Fallback approximation when tiktoken not available
            return len(text) // 4

    def _prepare_messages(
        self,
        system_prompt: str,
        user_prompt: str,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, str]]:
        """
        Build message list with token management.

        Handles token budget, smart truncation, and message structure.

        Args:
            system_prompt: System/persona prompt
            user_prompt: User task prompt
            context_data: Optional structured data to include (will be JSON serialized)

        Returns:
            List of message dicts for OpenAI API
        """
        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Calculate base token usage
        base_tokens = self._estimate_tokens(system_prompt) + self._estimate_tokens(user_prompt)
        available_tokens = self.max_context_tokens - base_tokens - self.response_buffer_tokens

        # If context_data provided, serialize and check token budget
        if context_data:
            context_json = json.dumps(context_data, indent=2)
            context_tokens = self._estimate_tokens(context_json)

            if context_tokens > available_tokens:
                # Truncate context to fit budget
                logger.warning(
                    f"Context data exceeds token budget: {context_tokens} > {available_tokens}. "
                    "Applying smart truncation."
                )
                context_data = self._truncate_context(context_data, available_tokens)
                context_json = json.dumps(context_data, indent=2)

            # Append context to user prompt
            user_prompt = f"{user_prompt}\n\nContext Data:\n```json\n{context_json}\n```"

        messages.append({"role": "user", "content": user_prompt})

        total_tokens = self._estimate_tokens(system_prompt + user_prompt)
        logger.info(
            f"Prepared messages: ~{total_tokens} tokens (budget: {self.max_context_tokens})"
        )

        return messages

    def _truncate_context(
        self, context_data: Dict[str, Any], available_tokens: int
    ) -> Dict[str, Any]:
        """
        Smart truncation preserving priority data.

        Priority order (keep first, drop last):
        1. High-priority keys (scope, quantities, project_info)
        2. Medium-priority keys (tables, drawings)
        3. Low-priority keys (appendices, metadata)

        Args:
            context_data: Full context dictionary
            available_tokens: Token budget for context

        Returns:
            Truncated context dictionary
        """
        priority_keys = {
            "high": ["scope", "quantities", "project_info", "project_name", "voltage_level"],
            "medium": ["tables", "drawings", "cost_breakdown", "deliverables"],
            "low": ["appendices", "metadata", "notes", "references"],
        }

        truncated = {}

        # Start with high-priority keys
        for priority_level in ["high", "medium", "low"]:
            for key in priority_keys[priority_level]:
                if key in context_data:
                    truncated[key] = context_data[key]

                    # Check if we're approaching token limit
                    current_tokens = self._estimate_tokens(json.dumps(truncated, indent=2))
                    if current_tokens > available_tokens * 0.9:  # 90% threshold
                        logger.warning(
                            f"Truncation stopped at priority '{priority_level}'. "
                            f"Tokens: {current_tokens}/{available_tokens}"
                        )
                        return truncated

        # If still under budget, add remaining keys
        for key, value in context_data.items():
            if key not in truncated:
                truncated[key] = value

                current_tokens = self._estimate_tokens(json.dumps(truncated, indent=2))
                if current_tokens > available_tokens * 0.9:
                    # Remove last added key and stop
                    del truncated[key]
                    logger.warning(
                        f"Truncation complete. Final tokens: {current_tokens}/{available_tokens}"
                    )
                    return truncated

        return truncated

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),  # Retry on any exception
        reraise=True,
    )
    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """
        Call Azure OpenAI with retry logic.

        Args:
            messages: Message list for chat completion
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum response tokens

        Returns:
            LLM response content

        Raises:
            Exception: After 3 retries with exponential backoff
        """
        client = await self._get_client()

        response = await client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Extract response content
        if not response.choices or not response.choices[0].message:
            raise BusinessRuleViolation(
                message="LLM returned empty response", code="LLM_EMPTY_RESPONSE"
            )

        content = response.choices[0].message.content

        # Log token usage
        usage = response.usage
        if usage:
            logger.info(
                f"LLM call completed: {usage.prompt_tokens} prompt + "
                f"{usage.completion_tokens} completion = {usage.total_tokens} total tokens"
            )

        return content

    async def generate_narrative(
        self,
        aace_class: AACEClass,
        project: Project,
        base_cost: Decimal,
        risk_results: Dict[str, Any],
        line_item_summary: str,
    ) -> str:
        """
        Generate estimate narrative based on AACE class.

        Args:
            aace_class: AACE classification level
            project: Project ORM instance
            base_cost: Base estimate cost
            risk_results: Monte Carlo analysis results
            line_item_summary: Summary of cost breakdown structure

        Returns:
            Professional estimate narrative (500-1000 words)

        Raises:
            BusinessRuleViolation: If response validation fails
        """
        persona = get_persona_config(aace_class)
        user_prompt = get_narrative_prompt(
            aace_class=aace_class,
            project=project,
            base_cost=float(base_cost),
            risk_results=risk_results,
            line_item_summary=line_item_summary,
        )

        messages = self._prepare_messages(
            system_prompt=persona["system_prompt"],
            user_prompt=user_prompt,
        )

        logger.info(f"Generating narrative for {aace_class.value} estimate")

        response = await self._call_llm(
            messages=messages,
            temperature=persona["temperature"],
            max_tokens=self.max_output_tokens,
        )

        # Validate response
        if not validate_narrative_response(response, min_length=500):
            raise BusinessRuleViolation(
                message=f"LLM narrative failed validation for {aace_class.value}",
                code="NARRATIVE_VALIDATION_FAILED",
                details={"aace_class": aace_class.value, "response_length": len(response)},
            )

        logger.info(f"Narrative generated successfully: {len(response)} characters")
        return response

    async def generate_assumptions(
        self,
        aace_class: AACEClass,
        project: Project,
        documents: List[Document],
    ) -> List[str]:
        """
        Extract/generate assumptions from project data.

        Args:
            aace_class: AACE classification level
            project: Project ORM instance
            documents: List of project documents

        Returns:
            List of assumption strings (cleaned and validated)

        Raises:
            BusinessRuleViolation: If response extraction fails
        """
        persona = get_persona_config(aace_class)

        # Create document summary
        document_summary = "\n".join(
            [
                f"- {doc.document_type}: {doc.blob_path} (status: {doc.validation_status.value})"
                for doc in documents
            ]
        )

        user_prompt = get_assumptions_prompt(
            aace_class=aace_class,
            project=project,
            document_summary=document_summary,
        )

        messages = self._prepare_messages(
            system_prompt=persona["system_prompt"],
            user_prompt=user_prompt,
        )

        logger.info(f"Generating assumptions for {aace_class.value} estimate")

        response = await self._call_llm(
            messages=messages,
            temperature=persona["temperature"],
            max_tokens=self.max_output_tokens,
        )

        # Extract JSON from response
        try:
            data = extract_json_from_response(response)
        except ValueError as exc:
            raise BusinessRuleViolation(
                message=f"Failed to extract JSON from assumptions response: {exc}",
                code="ASSUMPTIONS_JSON_EXTRACTION_FAILED",
            )

        # Validate structure
        if not validate_json_structure(data, required_fields=["assumptions"]):
            raise BusinessRuleViolation(
                message="Assumptions response missing required 'assumptions' field",
                code="ASSUMPTIONS_INVALID_STRUCTURE",
            )

        # Clean and validate assumption list
        assumptions = validate_assumptions_list(data["assumptions"])

        logger.info(f"Generated {len(assumptions)} assumptions")
        return assumptions

    async def generate_exclusions(
        self,
        aace_class: AACEClass,
        project: Project,
        documents: List[Document],
    ) -> List[str]:
        """
        Identify scope exclusions.

        Args:
            aace_class: AACE classification level
            project: Project ORM instance
            documents: List of project documents

        Returns:
            List of exclusion strings (cleaned and validated)

        Raises:
            BusinessRuleViolation: If response extraction fails
        """
        persona = get_persona_config(aace_class)

        # Create document summary
        document_summary = "\n".join(
            [
                f"- {doc.document_type}: {doc.blob_path} (status: {doc.validation_status.value})"
                for doc in documents
            ]
        )

        user_prompt = get_exclusions_prompt(
            aace_class=aace_class,
            project=project,
            document_summary=document_summary,
        )

        messages = self._prepare_messages(
            system_prompt=persona["system_prompt"],
            user_prompt=user_prompt,
        )

        logger.info(f"Generating exclusions for {aace_class.value} estimate")

        response = await self._call_llm(
            messages=messages,
            temperature=persona["temperature"],
            max_tokens=self.max_output_tokens,
        )

        # Extract JSON from response
        try:
            data = extract_json_from_response(response)
        except ValueError as exc:
            raise BusinessRuleViolation(
                message=f"Failed to extract JSON from exclusions response: {exc}",
                code="EXCLUSIONS_JSON_EXTRACTION_FAILED",
            )

        # Validate structure
        if not validate_json_structure(data, required_fields=["exclusions"]):
            raise BusinessRuleViolation(
                message="Exclusions response missing required 'exclusions' field",
                code="EXCLUSIONS_INVALID_STRUCTURE",
            )

        # Clean and validate exclusion list
        exclusions = validate_exclusions_list(data["exclusions"])

        logger.info(f"Generated {len(exclusions)} exclusions")
        return exclusions

    async def validate_document(
        self,
        aace_class: AACEClass,
        document_type: str,
        structured_content: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        LLM-based document validation (completeness, contradictions).

        Args:
            aace_class: AACE classification level
            document_type: "scope", "engineering", "schedule", "bid"
            structured_content: Parsed document content from DocumentParser

        Returns:
            Validation result dict with:
                - completeness_score: int (0-100)
                - issues: List[str]
                - recommendations: List[str]
                - suitable_for_estimation: bool

        Raises:
            BusinessRuleViolation: If response extraction/validation fails
        """
        persona = get_persona_config(aace_class)
        user_prompt = get_validation_prompt(
            aace_class=aace_class,
            document_type=document_type,
            structured_content=structured_content,
        )

        messages = self._prepare_messages(
            system_prompt=persona["system_prompt"],
            user_prompt=user_prompt,
        )

        logger.info(f"Validating {document_type} document for {aace_class.value} estimate")

        response = await self._call_llm(
            messages=messages,
            temperature=persona["temperature"],
            max_tokens=self.max_output_tokens,
        )

        # Extract JSON from response
        try:
            data = extract_json_from_response(response)
        except ValueError as exc:
            raise BusinessRuleViolation(
                message=f"Failed to extract JSON from validation response: {exc}",
                code="VALIDATION_JSON_EXTRACTION_FAILED",
            )

        # Validate structure
        required_fields = [
            "completeness_score",
            "issues",
            "recommendations",
            "suitable_for_estimation",
        ]
        if not validate_json_structure(data, required_fields=required_fields):
            raise BusinessRuleViolation(
                message="Validation response missing required fields",
                code="VALIDATION_INVALID_STRUCTURE",
                details={"required": required_fields, "received": list(data.keys())},
            )

        # Validate completeness score range
        if not (0 <= data["completeness_score"] <= 100):
            raise BusinessRuleViolation(
                message=f"Invalid completeness score: {data['completeness_score']} (must be 0-100)",
                code="VALIDATION_INVALID_SCORE",
            )

        logger.info(
            f"Document validation complete: {data['completeness_score']}% complete, "
            f"{len(data['issues'])} issues, suitable={data['suitable_for_estimation']}"
        )

        return data

    async def close(self) -> None:
        """
        Close Azure OpenAI client.

        Should be called during application shutdown.
        """
        if self._client is not None:
            await self._client.close()
            logger.info("Closed AsyncAzureOpenAI client")
