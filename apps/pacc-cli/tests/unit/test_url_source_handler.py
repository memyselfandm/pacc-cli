"""Tests for URL source handler."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from pacc.errors import SourceError
from pacc.sources.url import URLSource, URLSourceHandler, extract_filename_from_url, is_url


class TestURLSourceHandler:
    """Test URL source handler functionality."""

    def setup_method(self):
        """Setup test method."""
        self.handler = URLSourceHandler(show_progress=False)

    def test_can_handle_valid_urls(self):
        """Test URL detection."""
        assert self.handler.can_handle("https://github.com/user/repo.zip")
        assert self.handler.can_handle("http://example.com/package.tar.gz")
        assert not self.handler.can_handle("/local/path/file.zip")
        assert not self.handler.can_handle("./relative/path")
        assert not self.handler.can_handle("file.zip")

    def test_get_source_info(self):
        """Test getting source information."""
        url = "https://github.com/user/repo/archive/main.zip"
        info = self.handler.get_source_info(url)

        assert info["url"] == url
        assert info["source_type"] == "url"
        assert info["scheme"] == "https"
        assert info["hostname"] == "github.com"
        assert info["filename"] == "main.zip"
        assert info["likely_archive"] is True
        assert info["archive_type"] == ".zip"

    def test_source_info_non_archive(self):
        """Test source info for non-archive files."""
        url = "https://example.com/script.py"
        info = self.handler.get_source_info(url)

        assert info["filename"] == "script.py"
        assert info["likely_archive"] is False

    def test_validate_url(self):
        """Test URL validation."""
        if self.handler.available:
            assert self.handler.validate_url("https://github.com/user/repo.zip")
            assert not self.handler.validate_url("javascript:alert(1)")
            assert not self.handler.validate_url("file:///etc/passwd")

    @pytest.mark.asyncio
    async def test_download_async(self):
        """Test async download functionality."""
        if not self.handler.available:
            pytest.skip("URL downloader not available")

        mock_result = {
            "success": True,
            "downloaded_path": Path("/tmp/test.zip"),
            "extracted_path": None,
            "final_path": Path("/tmp/test.zip"),
            "url": "https://example.com/test.zip",
            "file_size": 1024,
            "content_type": "application/zip",
            "from_cache": False,
            "error_message": None,
        }

        with patch.object(
            self.handler.downloader,
            "install_from_url",
            return_value=AsyncMock(
                success=True,
                downloaded_path=Path("/tmp/test.zip"),
                extracted_path=None,
                final_path=Path("/tmp/test.zip"),
                url="https://example.com/test.zip",
                file_size=1024,
                content_type="application/zip",
                from_cache=False,
                error_message=None,
            ),
        ):
            result = await self.handler.download_async(
                "https://example.com/test.zip", Path("/tmp"), extract_archives=True
            )

            assert result["success"] is True
            assert result["url"] == "https://example.com/test.zip"
            assert result["file_size"] == 1024

    def test_process_source_unavailable(self):
        """Test process_source when downloader is unavailable."""
        handler = URLSourceHandler()
        handler.available = False

        with pytest.raises(SourceError, match="URL downloads require aiohttp"):
            handler.process_source("https://example.com/test.zip")

    def test_process_source_invalid_url(self):
        """Test process_source with invalid URL."""
        with pytest.raises(SourceError, match="Invalid URL"):
            self.handler.process_source("not-a-url")


class TestURLSource:
    """Test URL source representation."""

    def test_url_source_creation(self):
        """Test creating URL source."""
        source = URLSource(
            url="https://example.com/package.zip", content_type="application/zip", file_size=1024
        )

        assert source.url == "https://example.com/package.zip"
        assert source.source_type == "url"
        assert source.content_type == "application/zip"
        assert source.file_size == 1024


class TestUtilityFunctions:
    """Test utility functions."""

    def test_is_url_function(self):
        """Test is_url utility function."""
        assert is_url("https://github.com/user/repo.zip")
        assert is_url("http://example.com/file.tar.gz")
        assert not is_url("/local/path/file.zip")
        assert not is_url("./relative/path")
        assert not is_url("file.zip")
        assert not is_url("")

    def test_extract_filename_from_url(self):
        """Test filename extraction from URL."""
        assert (
            extract_filename_from_url("https://github.com/user/repo/archive/main.zip") == "main.zip"
        )
        assert extract_filename_from_url("https://example.com/package.tar.gz") == "package.tar.gz"
        assert extract_filename_from_url("https://example.com/") == "download"
        assert extract_filename_from_url("https://example.com/path/") == "download"
        assert extract_filename_from_url("invalid-url") == "download"
        assert extract_filename_from_url("https://example.com/script.py") == "script.py"


class TestURLSourceHandlerCreation:
    """Test URL source handler creation and configuration."""

    def test_handler_with_custom_settings(self):
        """Test creating handler with custom settings."""
        cache_dir = Path("/tmp/test_cache")
        handler = URLSourceHandler(
            max_file_size_mb=50, timeout_seconds=60, cache_dir=cache_dir, show_progress=False
        )

        assert handler.max_file_size_mb == 50
        assert handler.timeout_seconds == 60
        assert handler.cache_dir == cache_dir
        assert handler.show_progress is False

    def test_factory_function(self):
        """Test factory function for creating handlers."""
        from pacc.sources.url import create_url_source_handler

        handler = create_url_source_handler(max_file_size_mb=25, timeout_seconds=120)

        assert isinstance(handler, URLSourceHandler)
        assert handler.max_file_size_mb == 25
        assert handler.timeout_seconds == 120


class TestURLSourceHandlerIntegration:
    """Test URL source handler integration with existing systems."""

    def test_handler_available_property(self):
        """Test availability property."""
        handler = URLSourceHandler()

        # Should be available if aiohttp is installed
        # If not available, that's also a valid test case
        assert isinstance(handler.available, bool)

        if handler.available:
            assert handler.downloader is not None
        else:
            assert handler.downloader is None

    def test_handler_with_missing_dependencies(self):
        """Test handler behavior with missing dependencies."""
        with patch("pacc.sources.url.URLDownloader", side_effect=ImportError("aiohttp not found")):
            handler = URLSourceHandler()

            assert not handler.available
            assert handler.downloader is None
            assert not handler.can_handle("https://example.com/test.zip")

    def test_source_info_when_unavailable(self):
        """Test getting source info when handler is unavailable."""
        handler = URLSourceHandler()
        handler.available = False

        info = handler.get_source_info("https://example.com/test.zip")

        assert info["available"] is False
        assert "error" in info
        assert "aiohttp" in info["error"]


class TestErrorHandling:
    """Test error handling in URL source handler."""

    def test_invalid_url_handling(self):
        """Test handling of invalid URLs."""
        handler = URLSourceHandler()

        invalid_urls = ["", "not-a-url", "javascript:alert(1)", "file:///etc/passwd"]

        for url in invalid_urls:
            assert not handler.can_handle(url)

            info = handler.get_source_info(url)
            if handler.available:
                assert info["available"] is False
                assert "error" in info

    def test_source_error_propagation(self):
        """Test that SourceError is properly raised."""
        handler = URLSourceHandler()

        with pytest.raises(SourceError):
            handler.process_source("invalid-url")


@pytest.mark.integration
class TestURLSourceHandlerIntegrationWithDownloader:
    """Integration tests with the actual URL downloader."""

    def test_handler_uses_downloader_correctly(self):
        """Test that handler correctly uses the URL downloader."""
        handler = URLSourceHandler(show_progress=False)

        if not handler.available:
            pytest.skip("URL downloader not available")

        # Test that the handler has the expected configuration
        assert handler.downloader.max_file_size_bytes == 100 * 1024 * 1024  # 100MB
        assert handler.downloader.timeout_seconds == 300
        assert handler.downloader.cache_dir is None  # Default

    def test_handler_with_cache_configuration(self):
        """Test handler with cache configuration."""
        cache_dir = Path("/tmp/test_cache")
        handler = URLSourceHandler(cache_dir=cache_dir, show_progress=False)

        if not handler.available:
            pytest.skip("URL downloader not available")

        assert handler.downloader.cache_dir == cache_dir
