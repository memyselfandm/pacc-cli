"""PACC sources module for handling different extension sources."""

from .base import Source, SourceHandler
from .git import GitCloner, GitRepositorySource, GitSourceHandler, GitUrlParser
from .url import (
    URLSource,
    URLSourceHandler,
    create_url_source_handler,
    extract_filename_from_url,
    is_url,
)

__all__ = [
    # Base classes
    "SourceHandler",
    "Source",
    # Git implementation
    "GitSourceHandler",
    "GitRepositorySource",
    "GitUrlParser",
    "GitCloner",
    # URL implementation
    "URLSourceHandler",
    "URLSource",
    "create_url_source_handler",
    "is_url",
    "extract_filename_from_url",
]
