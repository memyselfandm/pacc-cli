"""Error handling infrastructure for PACC."""

from .exceptions import (
    PACCError,
    ValidationError,
    FileSystemError,
    ConfigurationError,
    SourceError,
    NetworkError,
    SecurityError,
)
from .reporting import ErrorReporter, ErrorContext

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