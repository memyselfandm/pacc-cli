"""Error handling infrastructure for PACC."""

from .exceptions import (
    PACCError,
    ValidationError,
    FileSystemError,
    ConfigurationError,
    SourceError,
)
from .reporting import ErrorReporter, ErrorContext

__all__ = [
    "PACCError",
    "ValidationError", 
    "FileSystemError",
    "ConfigurationError",
    "SourceError",
    "ErrorReporter",
    "ErrorContext",
]