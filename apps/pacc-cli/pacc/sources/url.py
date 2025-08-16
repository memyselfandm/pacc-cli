"""URL source handler for PACC installations."""

import asyncio
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from .base import SourceHandler, Source
from ..core.url_downloader import URLDownloader, ProgressDisplay
from ..validators import ExtensionDetector
from ..errors import SourceError


class URLSource(Source):
    """Represents a URL source for extensions."""
    
    def __init__(self, url: str, content_type: Optional[str] = None, file_size: int = 0):
        super().__init__(url=url, source_type="url")
        self.content_type = content_type
        self.file_size = file_size


class URLSourceHandler(SourceHandler):
    """Handler for URL-based extension sources."""
    
    def __init__(
        self,
        max_file_size_mb: int = 100,
        timeout_seconds: int = 300,
        cache_dir: Optional[Path] = None,
        show_progress: bool = True
    ):
        """Initialize URL source handler.
        
        Args:
            max_file_size_mb: Maximum download size in MB
            timeout_seconds: Download timeout in seconds
            cache_dir: Directory for caching downloads
            show_progress: Whether to show download progress
        """
        self.max_file_size_mb = max_file_size_mb
        self.timeout_seconds = timeout_seconds
        self.cache_dir = cache_dir
        self.show_progress = show_progress
        
        try:
            self.downloader = URLDownloader(
                max_file_size_mb=max_file_size_mb,
                timeout_seconds=timeout_seconds,
                cache_dir=cache_dir
            )
            self.available = True
        except ImportError:
            self.downloader = None
            self.available = False
    
    def can_handle(self, source: str) -> bool:
        """Check if this handler can process URLs.
        
        Args:
            source: Source URL or path
            
        Returns:
            True if source is a valid URL
        """
        if not self.available:
            return False
            
        try:
            parsed = urlparse(source)
            return parsed.scheme in ('http', 'https')
        except Exception:
            return False
    
    def process_source(
        self,
        source: str,
        extension_type: Optional[str] = None,
        extract_archives: bool = True,
        use_cache: bool = True,
        **kwargs
    ) -> List:
        """Process URL source and return available extensions.
        
        Args:
            source: URL to download from
            extension_type: Filter by specific extension type
            extract_archives: Whether to extract archive files
            use_cache: Whether to use cached downloads
            **kwargs: Additional options
            
        Returns:
            List of Extension objects found in the source
        """
        if not self.available:
            raise SourceError(
                "URL downloads require aiohttp. Install with: pip install aiohttp"
            )
        
        if not self.can_handle(source):
            raise SourceError(f"Invalid URL: {source}")
        
        # Setup progress display
        progress_display = None
        if self.show_progress:
            progress_display = ProgressDisplay()
        
        # Create temporary download directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Download and extract if needed
            result = asyncio.run(self.downloader.install_from_url(
                source,
                temp_path,
                extract_archives=extract_archives,
                progress_callback=progress_display.display_progress if progress_display else None
            ))
            
            if not result.success:
                raise SourceError(f"Download failed: {result.error_message}")
            
            # Use the extracted path if available, otherwise the downloaded file
            source_path = result.final_path
            
            if not source_path or not source_path.exists():
                raise SourceError("Downloaded content not found")
            
            # Detect extensions in the downloaded content
            extensions = []
            
            if source_path.is_file():
                ext_type = ExtensionDetector.detect_extension_type(source_path)
                if ext_type and (not extension_type or ext_type == extension_type):
                    from ..cli import Extension  # Import here to avoid circular imports
                    extension = Extension(
                        name=source_path.stem,
                        file_path=source_path,
                        extension_type=ext_type,
                        description=f"Downloaded from {source}"
                    )
                    extensions.append(extension)
            else:
                detected_files = ExtensionDetector.scan_directory(source_path)
                for ext_type, file_paths in detected_files.items():
                    if extension_type and ext_type != extension_type:
                        continue
                    
                    for file_path in file_paths:
                        from ..cli import Extension  # Import here to avoid circular imports
                        extension = Extension(
                            name=file_path.stem,
                            file_path=file_path,
                            extension_type=ext_type,
                            description=f"Downloaded from {source}"
                        )
                        extensions.append(extension)
            
            return extensions
    
    def get_source_info(self, source: str) -> Dict[str, Any]:
        """Get information about the URL source.
        
        Args:
            source: URL to get information about
            
        Returns:
            Dictionary with source metadata
        """
        if not self.available:
            return {
                "url": source,
                "available": False,
                "error": "aiohttp not available"
            }
        
        if not self.can_handle(source):
            return {
                "url": source,
                "available": False,
                "error": "Invalid URL"
            }
        
        # Basic URL parsing
        parsed = urlparse(source)
        
        info = {
            "url": source,
            "available": True,
            "source_type": "url",
            "scheme": parsed.scheme,
            "hostname": parsed.hostname,
            "path": parsed.path,
            "filename": Path(parsed.path).name if parsed.path else None,
            "max_file_size_mb": self.max_file_size_mb,
            "timeout_seconds": self.timeout_seconds,
            "caching_enabled": self.cache_dir is not None
        }
        
        # Try to detect file type from URL
        if info["filename"]:
            file_path = Path(info["filename"])
            file_suffixes = ''.join(file_path.suffixes).lower()
            
            # Check for archive formats (including multi-part extensions like .tar.gz)
            archive_extensions = {'.zip', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2'}
            is_archive = any(file_suffixes.endswith(ext) for ext in archive_extensions)
            
            info["likely_archive"] = is_archive
            if is_archive:
                info["archive_type"] = file_suffixes
            else:
                info["likely_archive"] = False
        
        return info
    
    def validate_url(self, url: str) -> bool:
        """Validate URL for safety and compliance.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid and safe
        """
        if not self.available:
            return False
        
        return self.downloader.validator.is_valid_url(url)
    
    async def download_async(
        self,
        source: str,
        destination: Path,
        extract_archives: bool = True,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Async download method for advanced use cases.
        
        Args:
            source: URL to download from
            destination: Path to save to
            extract_archives: Whether to extract archives
            progress_callback: Optional progress callback
            
        Returns:
            Download result information
        """
        if not self.available:
            raise SourceError("URL downloads require aiohttp")
        
        result = await self.downloader.install_from_url(
            source,
            destination,
            extract_archives=extract_archives,
            progress_callback=progress_callback
        )
        
        return {
            "success": result.success,
            "downloaded_path": result.downloaded_path,
            "extracted_path": result.extracted_path,
            "final_path": result.final_path,
            "url": result.url,
            "file_size": result.file_size,
            "content_type": result.content_type,
            "from_cache": result.from_cache,
            "error_message": result.error_message
        }


# Factory function for easy instantiation
def create_url_source_handler(**kwargs) -> URLSourceHandler:
    """Create URL source handler with default settings.
    
    Args:
        **kwargs: Configuration options for URLSourceHandler
        
    Returns:
        Configured URLSourceHandler instance
    """
    return URLSourceHandler(**kwargs)


# Utility functions
def is_url(source: str) -> bool:
    """Check if a source string is a URL.
    
    Args:
        source: Source string to check
        
    Returns:
        True if source appears to be a URL
    """
    try:
        parsed = urlparse(source)
        return parsed.scheme in ('http', 'https')
    except Exception:
        return False


def extract_filename_from_url(url: str, default: str = "download") -> str:
    """Extract filename from URL.
    
    Args:
        url: URL to extract filename from
        default: Default filename if extraction fails
        
    Returns:
        Extracted or default filename
    """
    try:
        parsed = urlparse(url)
        # Only process if it looks like a valid URL with a scheme
        if not parsed.scheme:
            return default
            
        path = Path(parsed.path)
        # Only return filename if path has a file extension or doesn't end with /
        if path.name and (path.suffix or not parsed.path.endswith('/')):
            return path.name
    except Exception:
        pass
    
    return default