"""URL downloader for PACC remote package installation."""

import asyncio
import hashlib
import mimetypes
import os
import re
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any, Set
from urllib.parse import urlparse, urljoin
import logging

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

from ..errors import PACCError


logger = logging.getLogger(__name__)


class DownloadSizeExceededException(PACCError):
    """Raised when download size exceeds limits."""
    pass


class SecurityScanFailedException(PACCError):
    """Raised when security scan fails."""
    pass


class UnsupportedArchiveFormatException(PACCError):
    """Raised when archive format is not supported."""
    pass


class NetworkException(PACCError):
    """Raised when network operations fail."""
    pass


@dataclass
class DownloadProgress:
    """Tracks download progress."""
    
    downloaded_bytes: int = 0
    total_bytes: int = 0
    start_time: float = field(default_factory=lambda: 0.0)
    
    def set_total_size(self, total_bytes: int) -> None:
        """Set total download size."""
        self.total_bytes = total_bytes
    
    def update_downloaded(self, downloaded_bytes: int) -> None:
        """Update downloaded byte count."""
        self.downloaded_bytes = downloaded_bytes
    
    @property
    def percentage(self) -> float:
        """Get download percentage."""
        if self.total_bytes == 0:
            return 0.0
        return min(100.0, (self.downloaded_bytes / self.total_bytes) * 100.0)
    
    def is_complete(self) -> bool:
        """Check if download is complete."""
        return self.total_bytes > 0 and self.downloaded_bytes >= self.total_bytes
    
    @property
    def speed_bytes_per_second(self) -> float:
        """Calculate download speed in bytes per second."""
        import time
        if self.start_time == 0.0:
            self.start_time = time.time()
        
        elapsed = time.time() - self.start_time
        if elapsed <= 0:
            return 0.0
        
        return self.downloaded_bytes / elapsed


@dataclass
class DownloadResult:
    """Result of a download operation."""
    
    success: bool
    downloaded_path: Optional[Path] = None
    extracted_path: Optional[Path] = None
    url: Optional[str] = None
    file_size: int = 0
    content_type: Optional[str] = None
    from_cache: bool = False
    error_message: Optional[str] = None
    
    @property
    def final_path(self) -> Optional[Path]:
        """Get the final path (extracted if available, otherwise downloaded)."""
        return self.extracted_path or self.downloaded_path


@dataclass
class SecurityScanResult:
    """Result of a security scan."""
    
    is_safe: bool
    warnings: List[str] = field(default_factory=list)
    blocked_files: List[str] = field(default_factory=list)
    suspicious_patterns: List[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Result of archive extraction."""
    
    success: bool
    extracted_path: Optional[Path] = None
    extracted_files: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


class URLValidator:
    """Validates URLs for safety and compliance."""
    
    ALLOWED_SCHEMES = {'http', 'https'}
    DANGEROUS_PATTERNS = [
        r'javascript:',
        r'data:',
        r'vbscript:',
        r'file:',
        r'ftp:',
    ]
    
    def __init__(
        self,
        max_url_length: int = 2048,
        allowed_domains: Optional[List[str]] = None,
        blocked_domains: Optional[List[str]] = None
    ):
        """Initialize URL validator.
        
        Args:
            max_url_length: Maximum allowed URL length
            allowed_domains: List of allowed domains (if set, only these are allowed)
            blocked_domains: List of blocked domains
        """
        self.max_url_length = max_url_length
        self.allowed_domains = set(allowed_domains or [])
        self.blocked_domains = set(blocked_domains or [])
    
    def is_valid_url(self, url: str) -> bool:
        """Validate URL for safety and compliance.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid and safe
        """
        if not url or len(url) > self.max_url_length:
            return False
        
        # Check for dangerous patterns
        url_lower = url.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, url_lower):
                return False
        
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        
        # Check scheme
        if parsed.scheme not in self.ALLOWED_SCHEMES:
            return False
        
        # Check domain restrictions
        if parsed.hostname:
            hostname = parsed.hostname.lower()
            
            # Check blocked domains
            if self.blocked_domains and hostname in self.blocked_domains:
                return False
            
            # Check allowed domains (if set)
            if self.allowed_domains and hostname not in self.allowed_domains:
                return False
        
        return True
    
    def get_safe_filename(self, url: str, default_name: str = "download") -> str:
        """Extract safe filename from URL.
        
        Args:
            url: URL to extract filename from
            default_name: Default filename if none can be extracted
            
        Returns:
            Safe filename
        """
        try:
            parsed = urlparse(url)
            path = Path(parsed.path)
            
            if path.name and path.suffix:
                # Sanitize filename
                safe_name = re.sub(r'[<>:"/\\|?*]', '_', path.name)
                return safe_name[:100]  # Limit length
            
        except Exception:
            pass
        
        return default_name


class URLDownloader:
    """Downloads and processes files from URLs."""
    
    SUPPORTED_ARCHIVE_EXTENSIONS = {'.zip', '.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2'}
    CHUNK_SIZE = 8192  # 8KB chunks for streaming
    MAX_REDIRECTS = 10
    
    def __init__(
        self,
        max_file_size_mb: int = 100,
        timeout_seconds: int = 300,
        cache_dir: Optional[Path] = None,
        user_agent: str = "PACC/1.0"
    ):
        """Initialize URL downloader.
        
        Args:
            max_file_size_mb: Maximum file size in MB
            timeout_seconds: Request timeout in seconds
            cache_dir: Directory for caching downloads
            user_agent: User agent string for requests
        """
        if not HAS_AIOHTTP:
            raise ImportError("aiohttp is required for URL downloads. Install with: pip install aiohttp")
        
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.timeout_seconds = timeout_seconds
        self.cache_dir = cache_dir
        self.user_agent = user_agent
        self.validator = URLValidator()
        
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def download_file(
        self,
        url: str,
        destination: Path,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None,
        use_cache: bool = False,
        follow_redirects: bool = True
    ) -> DownloadResult:
        """Download file from URL.
        
        Args:
            url: URL to download from
            destination: Path to save file
            progress_callback: Optional progress callback function
            use_cache: Whether to use cached downloads
            follow_redirects: Whether to follow HTTP redirects
            
        Returns:
            Download result
        """
        if not self.validator.is_valid_url(url):
            return DownloadResult(
                success=False,
                url=url,
                error_message=f"Invalid or unsafe URL: {url}"
            )
        
        # Check cache first
        if use_cache and self.cache_dir:
            cached_path = await self._get_cached_file(url)
            if cached_path and cached_path.exists():
                # Copy from cache to destination
                import shutil
                shutil.copy2(cached_path, destination)
                
                return DownloadResult(
                    success=True,
                    downloaded_path=destination,
                    url=url,
                    file_size=destination.stat().st_size,
                    from_cache=True
                )
        
        # Ensure destination directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            headers = {'User-Agent': self.user_agent}
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                redirect_count = 0
                current_url = url
                
                while redirect_count < self.MAX_REDIRECTS:
                    response = await session.get(current_url)
                    async with response:
                        # Handle redirects
                        if response.status in (301, 302, 303, 307, 308) and follow_redirects:
                            redirect_url = response.headers.get('location')
                            if redirect_url:
                                current_url = urljoin(current_url, redirect_url)
                                redirect_count += 1
                                continue
                        
                        # Check response status
                        if response.status != 200:
                            return DownloadResult(
                                success=False,
                                url=url,
                                error_message=f"HTTP {response.status}: {response.reason}"
                            )
                        
                        # Check content length
                        content_length = response.headers.get('content-length')
                        if content_length:
                            size = int(content_length)
                            if size > self.max_file_size_bytes:
                                raise DownloadSizeExceededException(
                                    f"File size {size} exceeds limit {self.max_file_size_bytes}"
                                )
                        
                        # Setup progress tracking
                        progress = DownloadProgress()
                        if content_length:
                            progress.set_total_size(int(content_length))
                        
                        # Download file
                        downloaded_bytes = 0
                        
                        with open(destination, 'wb') as f:
                            async for chunk in response.content.iter_chunked(self.CHUNK_SIZE):
                                if not chunk:
                                    break
                                
                                f.write(chunk)
                                downloaded_bytes += len(chunk)
                                
                                # Check size limit during download
                                if downloaded_bytes > self.max_file_size_bytes:
                                    destination.unlink(missing_ok=True)
                                    raise DownloadSizeExceededException(
                                        f"Download size {downloaded_bytes} exceeds limit"
                                    )
                                
                                # Update progress
                                progress.update_downloaded(downloaded_bytes)
                                if progress_callback:
                                    progress_callback(progress)
                        
                        # Cache file if enabled
                        if use_cache and self.cache_dir:
                            await self._cache_file(url, destination)
                        
                        content_type = response.headers.get('content-type', 'application/octet-stream')
                        
                        return DownloadResult(
                            success=True,
                            downloaded_path=destination,
                            url=url,
                            file_size=downloaded_bytes,
                            content_type=content_type,
                            from_cache=False
                        )
                
                # Too many redirects
                return DownloadResult(
                    success=False,
                    url=url,
                    error_message=f"Too many redirects (>{self.MAX_REDIRECTS})"
                )
                
        except DownloadSizeExceededException:
            raise
        except asyncio.TimeoutError:
            return DownloadResult(
                success=False,
                url=url,
                error_message="Download timeout"
            )
        except Exception as e:
            return DownloadResult(
                success=False,
                url=url,
                error_message=f"Download failed: {str(e)}"
            )
    
    async def extract_archive(
        self,
        archive_path: Path,
        extract_dir: Path,
        security_scan: bool = True
    ) -> ExtractionResult:
        """Extract archive file.
        
        Args:
            archive_path: Path to archive file
            extract_dir: Directory to extract to
            security_scan: Whether to perform security scan
            
        Returns:
            Extraction result
        """
        if not archive_path.exists():
            return ExtractionResult(
                success=False,
                error_message=f"Archive file not found: {archive_path}"
            )
        
        # Check supported format
        archive_suffix = ''.join(archive_path.suffixes).lower()
        if archive_suffix not in self.SUPPORTED_ARCHIVE_EXTENSIONS:
            raise UnsupportedArchiveFormatException(
                f"Unsupported archive format: {archive_suffix}"
            )
        
        # Security scan
        if security_scan:
            scan_result = await self.scan_archive_security(archive_path)
            if not scan_result.is_safe:
                raise SecurityScanFailedException(
                    f"Security scan failed: {', '.join(scan_result.warnings)}"
                )
        
        extract_dir.mkdir(parents=True, exist_ok=True)
        extracted_files = []
        
        try:
            if archive_suffix in {'.zip'}:
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    # Extract all files
                    for member in zf.namelist():
                        # Additional security check for each member
                        if self._is_safe_extract_path(member, extract_dir):
                            zf.extract(member, extract_dir)
                            extracted_files.append(member)
            
            elif archive_suffix in {'.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2'}:
                mode = 'r'
                if archive_suffix in {'.tar.gz', '.tgz'}:
                    mode = 'r:gz'
                elif archive_suffix in {'.tar.bz2', '.tbz2'}:
                    mode = 'r:bz2'
                
                with tarfile.open(archive_path, mode) as tf:
                    for member in tf.getmembers():
                        if self._is_safe_extract_path(member.name, extract_dir):
                            tf.extract(member, extract_dir)
                            extracted_files.append(member.name)
            
            return ExtractionResult(
                success=True,
                extracted_path=extract_dir,
                extracted_files=extracted_files
            )
            
        except Exception as e:
            return ExtractionResult(
                success=False,
                error_message=f"Extraction failed: {str(e)}"
            )
    
    async def scan_archive_security(self, archive_path: Path) -> SecurityScanResult:
        """Perform security scan on archive.
        
        Args:
            archive_path: Path to archive file
            
        Returns:
            Security scan result
        """
        warnings = []
        blocked_files = []
        suspicious_patterns = []
        
        try:
            archive_suffix = ''.join(archive_path.suffixes).lower()
            
            if archive_suffix == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    for member in zf.namelist():
                        issues = self._check_file_security(member)
                        warnings.extend(issues)
                        if issues:
                            blocked_files.append(member)
            
            elif archive_suffix in {'.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2'}:
                mode = 'r'
                if archive_suffix in {'.tar.gz', '.tgz'}:
                    mode = 'r:gz'
                elif archive_suffix in {'.tar.bz2', '.tbz2'}:
                    mode = 'r:bz2'
                
                with tarfile.open(archive_path, mode) as tf:
                    for member in tf.getmembers():
                        issues = self._check_file_security(member.name)
                        warnings.extend(issues)
                        if issues:
                            blocked_files.append(member.name)
            
            is_safe = len(warnings) == 0
            
            return SecurityScanResult(
                is_safe=is_safe,
                warnings=warnings,
                blocked_files=blocked_files,
                suspicious_patterns=suspicious_patterns
            )
            
        except Exception as e:
            return SecurityScanResult(
                is_safe=False,
                warnings=[f"Security scan failed: {str(e)}"]
            )
    
    async def install_from_url(
        self,
        url: str,
        install_dir: Path,
        extract_archives: bool = True,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> DownloadResult:
        """Complete URL installation workflow.
        
        Args:
            url: URL to download and install from
            install_dir: Directory to install to
            extract_archives: Whether to extract archive files
            progress_callback: Optional progress callback
            
        Returns:
            Download result with extraction information
        """
        install_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate safe filename
        filename = self.validator.get_safe_filename(url, "download")
        temp_download = install_dir / filename
        
        # Download file
        result = await self.download_file(url, temp_download, progress_callback)
        
        if not result.success:
            return result
        
        # Extract if it's an archive and extraction is enabled
        if extract_archives and self._is_archive_file(temp_download):
            extract_dir = install_dir / temp_download.stem
            extract_result = await self.extract_archive(temp_download, extract_dir)
            
            if extract_result.success:
                result.extracted_path = extract_result.extracted_path
                # Remove the downloaded archive after successful extraction
                temp_download.unlink(missing_ok=True)
            else:
                result.error_message = extract_result.error_message
                result.success = False
        
        return result
    
    def _is_archive_file(self, file_path: Path) -> bool:
        """Check if file is a supported archive format."""
        suffix = ''.join(file_path.suffixes).lower()
        return suffix in self.SUPPORTED_ARCHIVE_EXTENSIONS
    
    def _is_safe_extract_path(self, member_path: str, extract_dir: Path) -> bool:
        """Check if extraction path is safe (no path traversal)."""
        # Resolve the full path and check it's within extract_dir
        try:
            full_path = (extract_dir / member_path).resolve()
            return str(full_path).startswith(str(extract_dir.resolve()))
        except Exception:
            return False
    
    def _check_file_security(self, file_path: str) -> List[str]:
        """Check file for security issues."""
        issues = []
        
        # Check for path traversal
        if '..' in file_path or file_path.startswith('/'):
            issues.append(f"Path traversal attempt in: {file_path}")
        
        # Check for suspicious file names
        suspicious_names = {
            'passwd', 'shadow', 'hosts', 'sudoers',
            '.ssh', '.bash_history', '.bashrc'
        }
        
        file_name = Path(file_path).name.lower()
        if file_name in suspicious_names:
            issues.append(f"Suspicious file name: {file_path}")
        
        # Check for executable files in dangerous locations
        if file_path.startswith(('bin/', 'sbin/', 'usr/bin/', 'usr/sbin/')):
            issues.append(f"Executable in system directory: {file_path}")
        
        return issues
    
    async def _get_cached_file(self, url: str) -> Optional[Path]:
        """Get cached file for URL if it exists."""
        if not self.cache_dir:
            return None
        
        # Create cache key from URL
        cache_key = hashlib.sha256(url.encode()).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.cache"
        
        if cache_path.exists():
            return cache_path
        
        return None
    
    async def _cache_file(self, url: str, file_path: Path) -> None:
        """Cache downloaded file."""
        if not self.cache_dir:
            return
        
        cache_key = hashlib.sha256(url.encode()).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.cache"
        
        try:
            import shutil
            shutil.copy2(file_path, cache_path)
        except Exception as e:
            logger.warning(f"Failed to cache file: {e}")


class ProgressDisplay:
    """Display progress for downloads."""
    
    def __init__(self, show_speed: bool = True, show_eta: bool = True):
        """Initialize progress display.
        
        Args:
            show_speed: Whether to show download speed
            show_eta: Whether to show estimated time remaining
        """
        self.show_speed = show_speed
        self.show_eta = show_eta
        self.last_update = 0.0
        self.update_interval = 0.1  # Update every 100ms
    
    def display_progress(self, progress: DownloadProgress) -> None:
        """Display download progress.
        
        Args:
            progress: Progress information
        """
        import time
        
        # Throttle updates
        now = time.time()
        if now - self.last_update < self.update_interval and not progress.is_complete():
            return
        self.last_update = now
        
        # Create progress bar
        bar_width = 40
        filled_width = int(bar_width * progress.percentage / 100)
        bar = '█' * filled_width + '░' * (bar_width - filled_width)
        
        # Format size
        downloaded = self._format_bytes(progress.downloaded_bytes)
        total = self._format_bytes(progress.total_bytes) if progress.total_bytes > 0 else "Unknown"
        
        # Build status line
        status_parts = [
            f"\rProgress: [{bar}] {progress.percentage:.1f}%",
            f"({downloaded}/{total})"
        ]
        
        if self.show_speed and progress.speed_bytes_per_second > 0:
            speed = self._format_bytes(progress.speed_bytes_per_second) + "/s"
            status_parts.append(f"Speed: {speed}")
        
        if self.show_eta and progress.speed_bytes_per_second > 0 and progress.total_bytes > 0:
            remaining_bytes = progress.total_bytes - progress.downloaded_bytes
            eta_seconds = remaining_bytes / progress.speed_bytes_per_second
            eta = self._format_time(eta_seconds)
            status_parts.append(f"ETA: {eta}")
        
        status_line = " | ".join(status_parts)
        print(status_line, end='', flush=True)
        
        if progress.is_complete():
            print()  # New line when complete
    
    def _format_bytes(self, bytes_value: float) -> str:
        """Format bytes in human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} TB"
    
    def _format_time(self, seconds: float) -> str:
        """Format time in human readable format."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes:.0f}m {seconds:.0f}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}h {minutes:.0f}m"