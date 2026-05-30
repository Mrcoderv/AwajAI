"""Shared application exceptions.

These classes keep API and service error handling consistent across the project.
"""


class AppError(Exception):
    """Base exception for predictable application errors."""


class ValidationError(AppError):
    """Raised when incoming data is missing or invalid."""


class NotFoundError(AppError):
    """Raised when a requested record cannot be found."""


class ServiceError(AppError):
    """Raised when an unexpected data-access or service failure occurs."""
