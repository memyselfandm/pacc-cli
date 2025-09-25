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
    "PACCError",
    "ValidationError",
    "FileSystemError",
    "ConfigurationError",
    "SourceError",
    "NetworkError",
    "SecurityError",
    "ErrorReporter",
    "ErrorContext",
]
