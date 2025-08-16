"""PACC sources module for handling different extension sources."""

from .base import SourceHandler, Source
from .git import GitSourceHandler, GitRepositorySource, GitUrlParser, GitCloner
from .url import URLSourceHandler, URLSource, create_url_source_handler, is_url, extract_filename_from_url

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