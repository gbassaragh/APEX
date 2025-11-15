"""
Retry decorators for Azure service calls with intelligent error handling.

CRITICAL: Distinguishes between transient errors (safe to retry) and
fatal errors (fail fast without retry).
"""
import asyncio
import functools
import logging

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
    ServiceRequestError,
    ServiceRequestTimeoutError,
    ServiceResponseError,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Transient errors - safe to retry
# These are temporary network/service issues that may resolve on retry
TRANSIENT_ERRORS = (
    ServiceRequestError,  # Network issues, connection failures
    ServiceRequestTimeoutError,  # Request timed out
    ServiceResponseError,  # HTTP 5xx errors from service
    HttpResponseError,  # Generic HTTP errors (includes 429 throttling, 503, etc.)
)

# Fatal errors - do NOT retry
# These indicate configuration or permission issues that won't resolve with retry
FATAL_ERRORS = (
    ClientAuthenticationError,  # Authentication failed - won't fix itself
    ResourceNotFoundError,  # Resource doesn't exist - won't appear on retry
    ResourceExistsError,  # Resource already exists - retry won't help
    ResourceModifiedError,  # ETag mismatch, optimistic concurrency failure
)


def azure_retry(func):
    """
    Intelligent retry decorator for Azure operations.

    Features:
    - Retries only transient errors (network, service failures)
    - Fails fast on fatal errors (auth, not-found)
    - Supports both async and sync functions
    - Exponential backoff: 2s, 4s, 8s (max 10s)
    - Logs retry attempts for debugging

    Usage:
        @azure_retry
        async def my_async_function():
            ...

        @azure_retry
        def my_sync_function():
            ...

    Raises:
        TRANSIENT_ERRORS: After 3 failed attempts
        FATAL_ERRORS: Immediately without retry
    """

    if asyncio.iscoroutinefunction(func):
        # Async function wrapper
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(TRANSIENT_ERRORS),
            reraise=True,
            before_sleep=lambda retry_state: logger.warning(
                f"Retrying {func.__name__} after {retry_state.outcome.exception()} "
                f"(attempt {retry_state.attempt_number}/3)"
            ),
        )
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except FATAL_ERRORS as e:
                # Log fatal error and fail immediately
                logger.error(
                    f"Fatal error in {func.__name__}: {e.__class__.__name__}: {e}. " "Not retrying."
                )
                raise

        return async_wrapper

    else:
        # Sync function wrapper
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(TRANSIENT_ERRORS),
            reraise=True,
            before_sleep=lambda retry_state: logger.warning(
                f"Retrying {func.__name__} after {retry_state.outcome.exception()} "
                f"(attempt {retry_state.attempt_number}/3)"
            ),
        )
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except FATAL_ERRORS as e:
                # Log fatal error and fail immediately
                logger.error(
                    f"Fatal error in {func.__name__}: {e.__class__.__name__}: {e}. " "Not retrying."
                )
                raise

        return sync_wrapper
