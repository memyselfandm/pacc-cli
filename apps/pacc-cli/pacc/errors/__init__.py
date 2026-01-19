"""Error handling infrastructure for PACC."""

from .exceptions import (
    ConfigurationError,
    FileSystemError,
    NetworkError,
    PACCError,
    SecurityError,
    SourceError,
    ValidationError,
)
from .reporting import ErrorContext, ErrorReporter

__all__ = [
    "ConfigurationError",
    "ErrorContext",
    "ErrorReporter",
    "FileSystemError",
    "NetworkError",
    "PACCError",
    "SecurityError",
    "SourceError",
    "ValidationError",
]
