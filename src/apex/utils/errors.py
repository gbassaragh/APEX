"""
Custom exception classes for business logic violations.
"""


class BusinessRuleViolation(Exception):
    """
    Exception raised when a business rule is violated.

    Used for validation errors, access violations, and other business logic failures.
    Automatically converted to 400 Bad Request by global exception handler.
    """

    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        """
        Initialize business rule violation.

        Args:
            message: Human-readable error message
            code: Optional error code for client handling
            details: Optional additional error context
        """
        super().__init__(message)
        self.code = code
        self.details = details or {}
