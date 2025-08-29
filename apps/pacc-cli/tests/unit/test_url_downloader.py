"""Tests for URL downloader functionality."""

import asyncio
import tempfile
import zipfile
import tarfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, AsyncMock
from urllib.parse import urlparse
import pytest

from pacc.core.url_downloader import (
    URLDownloader, 
    URLValidator, 
    DownloadProgress,
    DownloadSizeExceededException,
    SecurityScanFailedException,
    UnsupportedArchiveFormatException
)


class TestURLValidator:
    """Test URL validation functionality."""

    def test_valid_https_url(self):
        """Test validation of valid HTTPS URL."""
        validator = URLValidator()
        assert validator.is_valid_url("https://example.com/package.zip")
        assert validator.is_valid_url("https://github.com/user/repo/archive/main.zip")

    def test_valid_http_url(self):
        """Test validation of valid HTTP URL."""
        validator = URLValidator()
        assert validator.is_valid_url("http://example.com/package.tar.gz")

    def test_invalid_urls(self):
        """Test validation of invalid URLs."""
        validator = URLValidator()
        
        invalid_urls = [
            "",
            "not-a-url",
            "ftp://example.com/file.zip",  # Unsupported protocol
            "file:///local/path",  # Local file protocol
            "javascript:alert(1)",  # Security risk
            "data:text/html,<script>alert(1)</script>",  # Data URL
        ]
        
        for url in invalid_urls:
            assert not validator.is_valid_url(url), f"Should reject URL: {url}"

    def test_url_size_validation(self):
        """Test URL parameter size validation."""
        validator = URLValidator(max_url_length=50)
        
        short_url = "https://example.com/package.zip"
        long_url = "https://example.com/" + "a" * 100 + "/package.zip"
        
        assert validator.is_valid_url(short_url)
        assert not validator.is_valid_url(long_url)

    def test_blocked_domains(self):
        """Test blocked domain functionality."""
        blocked_domains = ["malicious.com", "spam.net"]
        validator = URLValidator(blocked_domains=blocked_domains)
        
        assert not validator.is_valid_url("https://malicious.com/package.zip")
        assert not validator.is_valid_url("https://spam.net/file.tar.gz")
        assert validator.is_valid_url("https://github.com/user/repo.zip")

    def test_allowed_domains_only(self):
        """Test allowed domains restriction."""
        allowed_domains = ["github.com", "gitlab.com"]
        validator = URLValidator(allowed_domains=allowed_domains)
        
        assert validator.is_valid_url("https://github.com/user/repo.zip")
        assert validator.is_valid_url("https://gitlab.com/user/project.tar.gz")
        assert not validator.is_valid_url("https://example.com/package.zip")


class TestDownloadProgress:
    """Test download progress tracking."""

    def test_progress_initialization(self):
        """Test progress tracker initialization."""
        progress = DownloadProgress()
        
        assert progress.downloaded_bytes == 0
        assert progress.total_bytes == 0
        assert progress.percentage == 0.0
        assert not progress.is_complete()

    def test_progress_updates(self):
        """Test progress updates."""
        progress = DownloadProgress()
        progress.set_total_size(1000)
        
        assert progress.total_bytes == 1000
        assert progress.percentage == 0.0
        
        progress.update_downloaded(250)
        assert progress.downloaded_bytes == 250
        assert progress.percentage == 25.0
        
        progress.update_downloaded(500)
        assert progress.downloaded_bytes == 500
        assert progress.percentage == 50.0

    def test_progress_completion(self):
        """Test progress completion detection."""
        progress = DownloadProgress()
        progress.set_total_size(1000)
        
        assert not progress.is_complete()
        
        progress.update_downloaded(1000)
        assert progress.is_complete()
        assert progress.percentage == 100.0


class TestURLDownloader:
    """Test URL downloader functionality."""

    def setup_method(self):
        """Setup test method."""
        self.downloader = URLDownloader(
            max_file_size_mb=10,
            timeout_seconds=30
        )

    @pytest.mark.asyncio
    async def test_download_small_file(self):
        """Test downloading a small file."""
        mock_response_data = b"test file content"
        
        with patch('pacc.core.url_downloader.aiohttp.ClientSession') as mock_session_class:
            # Setup mock response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-length': str(len(mock_response_data))}
            
            # Mock the async iteration over chunks
            async def mock_iter_chunked(chunk_size):
                yield mock_response_data
            
            mock_response.content.iter_chunked = mock_iter_chunked
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Setup mock session
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            with tempfile.TemporaryDirectory() as temp_dir:
                dest_path = Path(temp_dir) / "downloaded_file.txt"
                url = "https://example.com/test.txt"
                
                result = await self.downloader.download_file(url, dest_path)
                
                assert result.success
                assert result.downloaded_path == dest_path
                assert dest_path.read_bytes() == mock_response_data

    @pytest.mark.asyncio
    async def test_download_size_limit_exceeded(self):
        """Test download fails when size limit is exceeded."""
        large_size = self.downloader.max_file_size_bytes + 1000000  # 1MB over limit
        
        with patch('pacc.core.url_downloader.aiohttp.ClientSession') as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-length': str(large_size)}
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Setup mock session
            mock_session = AsyncMock()
            mock_session.get.return_value = mock_response
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            with tempfile.TemporaryDirectory() as temp_dir:
                dest_path = Path(temp_dir) / "large_file.zip"
                url = "https://example.com/large.zip"
                
                with pytest.raises(DownloadSizeExceededException):
                    await self.downloader.download_file(url, dest_path)

    @pytest.mark.asyncio
    async def test_download_with_progress_callback(self):
        """Test download with progress callback."""
        mock_response_data = b"x" * 1000  # 1KB file
        progress_updates = []
        
        def progress_callback(progress: DownloadProgress):
            progress_updates.append(progress.percentage)
        
        with patch('pacc.core.url_downloader.aiohttp.ClientSession') as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-length': str(len(mock_response_data))}
            
            # Simulate chunked reading
            chunk_size = 250
            chunks = [mock_response_data[i:i+chunk_size] for i in range(0, len(mock_response_data), chunk_size)]
            
            # Mock the chunked content iteration
            async def mock_iter_chunked(chunk_size_arg):
                for chunk in chunks:
                    if chunk:  # Only yield non-empty chunks
                        yield chunk
            
            mock_response.content.iter_chunked = mock_iter_chunked
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Setup mock session
            mock_session = AsyncMock()
            mock_session.get.return_value = mock_response
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            with tempfile.TemporaryDirectory() as temp_dir:
                dest_path = Path(temp_dir) / "progress_test.txt"
                url = "https://example.com/test.txt"
                
                result = await self.downloader.download_file(
                    url, dest_path, progress_callback=progress_callback
                )
                
                assert result.success
                assert len(progress_updates) > 0
                assert progress_updates[-1] == 100.0  # Should reach 100%

    @pytest.mark.asyncio
    async def test_extract_zip_archive(self):
        """Test extracting ZIP archive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = Path(temp_dir) / "test.zip"
            extract_dir = Path(temp_dir) / "extracted"
            
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("file1.txt", "content1")
                zf.writestr("folder/file2.txt", "content2")
            
            result = await self.downloader.extract_archive(zip_path, extract_dir)
            
            assert result.success
            assert (extract_dir / "file1.txt").exists()
            assert (extract_dir / "folder" / "file2.txt").exists()
            assert (extract_dir / "file1.txt").read_text() == "content1"

    @pytest.mark.asyncio
    async def test_extract_tar_gz_archive(self):
        """Test extracting TAR.GZ archive."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test TAR.GZ file
            tar_path = Path(temp_dir) / "test.tar.gz"
            extract_dir = Path(temp_dir) / "extracted"
            
            with tarfile.open(tar_path, 'w:gz') as tf:
                # Create file in memory
                file1_data = b"content1"
                file1_info = tarfile.TarInfo(name="file1.txt")
                file1_info.size = len(file1_data)
                tf.addfile(file1_info, fileobj=tempfile.BytesIO(file1_data))
                
                file2_data = b"content2"
                file2_info = tarfile.TarInfo(name="folder/file2.txt")
                file2_info.size = len(file2_data)
                tf.addfile(file2_info, fileobj=tempfile.BytesIO(file2_data))
            
            result = await self.downloader.extract_archive(tar_path, extract_dir)
            
            assert result.success
            assert (extract_dir / "file1.txt").exists()
            assert (extract_dir / "folder" / "file2.txt").exists()

    @pytest.mark.asyncio
    async def test_extract_unsupported_format(self):
        """Test extraction fails for unsupported format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file with unsupported extension
            unknown_file = Path(temp_dir) / "test.unknown"
            unknown_file.write_text("not an archive")
            extract_dir = Path(temp_dir) / "extracted"
            
            with pytest.raises(UnsupportedArchiveFormatException):
                await self.downloader.extract_archive(unknown_file, extract_dir)

    @pytest.mark.asyncio
    async def test_security_scan_malicious_content(self):
        """Test security scanning detects malicious content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create ZIP with potentially malicious paths
            zip_path = Path(temp_dir) / "malicious.zip"
            
            with zipfile.ZipFile(zip_path, 'w') as zf:
                # Path traversal attempt
                zf.writestr("../../../etc/passwd", "malicious content")
                zf.writestr("good_file.txt", "safe content")
            
            # Security scan should detect malicious paths
            result = await self.downloader.scan_archive_security(zip_path)
            
            assert not result.is_safe
            assert "path traversal" in result.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_security_scan_safe_content(self):
        """Test security scanning passes safe content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create ZIP with safe content
            zip_path = Path(temp_dir) / "safe.zip"
            
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr("file1.txt", "safe content")
                zf.writestr("folder/file2.json", '{"safe": "data"}')
            
            result = await self.downloader.scan_archive_security(zip_path)
            
            assert result.is_safe
            assert len(result.warnings) == 0

    @pytest.mark.asyncio
    async def test_full_url_installation_workflow(self):
        """Test complete URL installation workflow."""
        # Create a test ZIP archive
        test_content = {
            "test_hook.json": '{"name": "test", "events": ["PreToolUse"]}',
            "README.md": "Test extension package"
        }
        
        mock_zip_data = self._create_mock_zip(test_content)
        
        with patch('pacc.core.url_downloader.aiohttp.ClientSession') as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-length': str(len(mock_zip_data))}
            
            # Mock the chunked content iteration
            async def mock_iter_chunked(chunk_size):
                yield mock_zip_data
            
            mock_response.content.iter_chunked = mock_iter_chunked
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Setup mock session
            mock_session = AsyncMock()
            mock_session.get.return_value = mock_response
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            with tempfile.TemporaryDirectory() as temp_dir:
                install_dir = Path(temp_dir) / "installed"
                url = "https://github.com/user/extension.zip"
                
                result = await self.downloader.install_from_url(
                    url, install_dir, extract_archives=True
                )
                
                assert result.success
                assert result.extracted_path.exists()
                assert (result.extracted_path / "test_hook.json").exists()
                assert (result.extracted_path / "README.md").exists()

    def _create_mock_zip(self, content_dict: dict) -> bytes:
        """Create mock ZIP file content."""
        import io
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            for filename, content in content_dict.items():
                zf.writestr(filename, content)
        
        return zip_buffer.getvalue()

    @pytest.mark.asyncio
    async def test_url_caching(self):
        """Test URL caching functionality."""
        cache_dir = Path(tempfile.mkdtemp()) / "cache"
        downloader = URLDownloader(cache_dir=cache_dir)
        
        mock_data = b"cached content"
        url = "https://example.com/cached.zip"
        
        with patch('pacc.core.url_downloader.aiohttp.ClientSession') as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-length': str(len(mock_data))}
            
            # Mock the chunked content iteration
            async def mock_iter_chunked(chunk_size):
                yield mock_data
            
            mock_response.content.iter_chunked = mock_iter_chunked
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Setup mock session
            mock_session = AsyncMock()
            mock_session.get.return_value = mock_response
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            with tempfile.TemporaryDirectory() as temp_dir:
                dest_path1 = Path(temp_dir) / "download1.zip"
                dest_path2 = Path(temp_dir) / "download2.zip"
                
                # First download - should hit network
                result1 = await downloader.download_file(url, dest_path1, use_cache=True)
                assert result1.success
                assert result1.from_cache is False
                
                # Second download - should use cache
                result2 = await downloader.download_file(url, dest_path2, use_cache=True)
                assert result2.success
                assert result2.from_cache is True
                
                # Both files should have same content
                assert dest_path1.read_bytes() == dest_path2.read_bytes()

    @pytest.mark.asyncio
    async def test_download_with_redirects(self):
        """Test downloading with HTTP redirects."""
        final_data = b"final content"
        
        with patch('pacc.core.url_downloader.aiohttp.ClientSession') as mock_session_class:
            # Setup redirect responses
            redirect_response = AsyncMock()
            redirect_response.status = 302
            redirect_response.headers = {'location': 'https://example.com/final.zip'}
            redirect_response.__aenter__ = AsyncMock(return_value=redirect_response)
            redirect_response.__aexit__ = AsyncMock(return_value=None)
            
            final_response = AsyncMock()
            final_response.status = 200
            final_response.headers = {'content-length': str(len(final_data))}
            
            # Mock the chunked content iteration
            async def mock_iter_chunked(chunk_size):
                yield final_data
            
            final_response.content.iter_chunked = mock_iter_chunked
            final_response.__aenter__ = AsyncMock(return_value=final_response)
            final_response.__aexit__ = AsyncMock(return_value=None)
            
            # Setup mock session
            mock_session = AsyncMock()
            mock_session.get.side_effect = [redirect_response, final_response]
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            
            mock_session_class.return_value = mock_session
            
            with tempfile.TemporaryDirectory() as temp_dir:
                dest_path = Path(temp_dir) / "redirected.zip"
                url = "https://example.com/redirect.zip"
                
                result = await self.downloader.download_file(url, dest_path, follow_redirects=True)
                
                assert result.success
                assert dest_path.read_bytes() == final_data