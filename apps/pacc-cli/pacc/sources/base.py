"""Base classes for source handling."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Source:
    """Base class representing a source of extensions."""
    
    url: str
    source_type: str
    
    
class SourceHandler(ABC):
    """Abstract base class for handling different source types."""
    
    @abstractmethod
    def can_handle(self, source: str) -> bool:
        """Check if this handler can process the given source.
        
        Args:
            source: Source URL or path
            
        Returns:
            True if this handler can process the source
        """
        pass
    
    @abstractmethod
    def process_source(self, source: str, **kwargs) -> List:
        """Process the source and return available extensions.
        
        Args:
            source: Source URL or path
            **kwargs: Additional options (e.g., extension_type filter)
            
        Returns:
            List of Extension objects found in the source
        """
        pass
    
    @abstractmethod
    def get_source_info(self, source: str) -> Dict[str, Any]:
        """Get information about the source.
        
        Args:
            source: Source URL or path
            
        Returns:
            Dictionary with source metadata
        """
        pass