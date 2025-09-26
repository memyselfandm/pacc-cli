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
    "GitCloner",
    "GitRepositorySource",
    # Git implementation
    "GitSourceHandler",
    "GitUrlParser",
    "Source",
    # Base classes
    "SourceHandler",
    "URLSource",
    # URL implementation
    "URLSourceHandler",
    "create_url_source_handler",
    "extract_filename_from_url",
    "is_url",
]
