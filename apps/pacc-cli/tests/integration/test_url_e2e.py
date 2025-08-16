"""End-to-end tests for URL installation workflow."""

import tempfile
import zipfile
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import pytest

from pacc.cli import PACCCli
from pacc.sources.url import URLSourceHandler


class TestURLInstallationE2E:
    """End-to-end tests for URL installation workflow."""
    
    def create_test_extension_archive(self, file_paths_and_contents: dict) -> bytes:
        """Create a test archive with extension files.
        
        Args:
            file_paths_and_contents: Dict mapping file paths to their contents
            
        Returns:
            Bytes of the ZIP archive
        """
        import io
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            for file_path, content in file_paths_and_contents.items():
                zf.writestr(file_path, content)
        
        return zip_buffer.getvalue()
    
    def test_url_install_hooks_extension(self):
        """Test installing a hooks extension from URL."""
        # Create test hook content
        hook_content = {
            "name": "test_hook",
            "eventTypes": ["PreToolUse"],
            "commands": [
                {
                    "matchers": ["*"],
                    "command": "echo 'test hook'"
                }
            ]
        }
        
        # Create test archive
        archive_content = self.create_test_extension_archive({
            "test_hook.json": json.dumps(hook_content, indent=2),
            "README.md": "# Test Hook Extension\nA test hook for PACC."
        })
        
        # Mock the URL downloader
        with patch('pacc.core.url_downloader.aiohttp.ClientSession') as mock_session:
            # Setup mock response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {'content-length': str(len(archive_content))}
            
            # Mock chunked reading
            async def mock_iter_chunked(chunk_size):
                yield archive_content
            
            mock_response.content.iter_chunked = mock_iter_chunked
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)
            
            # Setup mock session
            mock_session_instance = AsyncMock()
            mock_session_instance.get = AsyncMock(return_value=mock_response)
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=None)
            
            mock_session.return_value = mock_session_instance
            
            # Test the installation
            cli = PACCCli()
            
            # Create a mock args object with all required attributes
            class MockArgs:
                source = "https://example.com/test_hook.zip"
                user = False
                project = True
                dry_run = True  # Use dry run to avoid actual file operations
                verbose = False
                max_size = 100
                timeout = 300
                no_cache = False
                no_extract = False
                type = None
                force = False
                interactive = False
                all = False
            
            args = MockArgs()
            
            # Should successfully route to URL install and process
            result = cli.install_command(args)
            
            # In dry-run mode, should return 0 (success)
            assert result == 0
    
    def test_url_source_handler_integration(self):
        """Test URL source handler integration with validators."""
        # Create test MCP server content
        mcp_content = {
            "name": "test_mcp",
            "command": "python test_server.py",
            "args": ["--port", "8080"]
        }
        
        # Test URL source handler
        handler = URLSourceHandler(show_progress=False)
        
        if not handler.available:
            pytest.skip("URL downloader not available")
        
        # Create a temporary directory that will exist during the test
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            extracted_path = temp_path / "extracted"
            extracted_path.mkdir()
            
            # Create mock MCP file
            mcp_dir = extracted_path / "mcp"
            mcp_dir.mkdir()
            mcp_file = mcp_dir / "test_server.json"
            mcp_file.write_text(json.dumps(mcp_content, indent=2))
            
            # Mock the asyncio.run to return our mock result
            with patch('pacc.sources.url.asyncio.run') as mock_asyncio_run:
                
                # Mock download result
                mock_result = MagicMock()
                mock_result.success = True
                mock_result.final_path = extracted_path  # Point to our real directory
                mock_result.error_message = None
                
                mock_asyncio_run.return_value = mock_result
                
                # Process the URL source
                extensions = handler.process_source(
                    "https://example.com/test_mcp.zip",
                    extension_type="mcp"
                )
                
                # Should find the MCP extension
                assert len(extensions) > 0
                assert extensions[0].extension_type == "mcp"
    
    def test_url_vs_git_routing(self):
        """Test that URL routing works correctly vs Git routing."""
        cli = PACCCli()
        
        # Test cases: URL should go to URL handler, Git should go to Git handler
        test_cases = [
            ("https://github.com/user/repo.zip", "url"),  # Direct download
            ("https://github.com/user/repo.tar.gz", "url"),  # Direct download
            ("https://example.com/package.zip", "url"),  # Direct download
            ("https://github.com/user/repo.git", "git"),  # Git repository
            ("https://github.com/user/repo", "git"),  # Git repository (no .git)
            ("git@github.com:user/repo.git", "git"),  # SSH Git
        ]
        
        for source_url, expected_type in test_cases:
            is_url = cli._is_url(source_url)
            is_git = cli._is_git_url(source_url)
            
            if expected_type == "url":
                assert is_url, f"URL {source_url} should be detected as URL"
                # Due to order in install_command, URL check comes first
                # so Git detection doesn't matter for routing
            elif expected_type == "git":
                # For Git URLs, they might also be detected as URLs
                # but the Git detection should work
                assert is_git, f"URL {source_url} should be detected as Git"
    
    def test_url_source_info_extraction(self):
        """Test URL source information extraction."""
        handler = URLSourceHandler()
        
        test_urls = [
            "https://github.com/user/repo/archive/main.zip",
            "https://gitlab.com/project/extension/archive/v1.0.zip", 
            "https://example.com/downloads/hook-pack.tar.gz",
            "https://files.example.com/script.py"
        ]
        
        for url in test_urls:
            info = handler.get_source_info(url)
            
            assert info["url"] == url
            assert info["source_type"] == "url"
            assert "hostname" in info
            assert "filename" in info
            
            # Check archive detection
            if any(ext in url for ext in ['.zip', '.tar.gz', '.tar.bz2']):
                assert info.get("likely_archive", False), f"Should detect {url} as archive"
            else:
                assert not info.get("likely_archive", True), f"Should not detect {url} as archive"
    
    def test_url_error_handling(self):
        """Test URL installation error handling."""
        cli = PACCCli()
        
        # Test with invalid URL
        class MockArgs:
            source = "not-a-valid-url"
            verbose = False
        
        result = cli.install_command(MockArgs())
        assert result == 1  # Should fail
        
        # Test with valid URL but no aiohttp
        with patch('pacc.cli.HAS_URL_DOWNLOADER', False):
            class MockArgs2:
                source = "https://example.com/test.zip"
                verbose = False
            
            result = cli.install_command(MockArgs2())
            assert result == 1  # Should fail gracefully
    
    def test_url_security_validation(self):
        """Test URL security validation."""
        handler = URLSourceHandler()
        
        if not handler.available:
            pytest.skip("URL downloader not available")
        
        # Test dangerous URLs
        dangerous_urls = [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
            "ftp://malicious.com/hack.zip"
        ]
        
        for url in dangerous_urls:
            assert not handler.validate_url(url), f"Should reject dangerous URL: {url}"
        
        # Test safe URLs
        safe_urls = [
            "https://github.com/user/repo.zip",
            "http://example.com/package.tar.gz",
            "https://files.example.com/extension.json"
        ]
        
        for url in safe_urls:
            assert handler.validate_url(url), f"Should accept safe URL: {url}"


class TestURLInstallationFeatures:
    """Test specific URL installation features."""
    
    def test_archive_format_support(self):
        """Test that various archive formats are supported."""
        from pacc.core.url_downloader import URLDownloader
        
        downloader = URLDownloader()
        supported_formats = downloader.SUPPORTED_ARCHIVE_EXTENSIONS
        
        required_formats = {'.zip', '.tar.gz', '.tar.bz2', '.tar', '.tgz', '.tbz2'}
        
        for fmt in required_formats:
            assert fmt in supported_formats, f"Format {fmt} should be supported"
    
    def test_progress_display_functionality(self):
        """Test progress display features."""
        from pacc.core.url_downloader import ProgressDisplay, DownloadProgress
        
        # Test progress calculation
        progress = DownloadProgress()
        progress.set_total_size(1000)
        progress.update_downloaded(250)
        
        assert progress.percentage == 25.0
        assert not progress.is_complete()
        
        progress.update_downloaded(1000)
        assert progress.percentage == 100.0
        assert progress.is_complete()
        
        # Test progress display
        display = ProgressDisplay(show_speed=True, show_eta=True)
        assert display.show_speed
        assert display.show_eta
        
        # Test formatting utilities
        assert "KB" in display._format_bytes(1500)
        assert "MB" in display._format_bytes(1500000)
        assert "s" in display._format_time(30)
    
    def test_url_caching_configuration(self):
        """Test URL caching configuration."""
        from pacc.sources.url import URLSourceHandler
        
        # Test with caching enabled
        cache_dir = Path("/tmp/pacc_test_cache")
        handler = URLSourceHandler(cache_dir=cache_dir)
        
        if handler.available:
            assert handler.cache_dir == cache_dir
            assert handler.downloader.cache_dir == cache_dir
        
        # Test with caching disabled
        handler_no_cache = URLSourceHandler(cache_dir=None)
        
        if handler_no_cache.available:
            assert handler_no_cache.cache_dir is None
            assert handler_no_cache.downloader.cache_dir is None


@pytest.mark.skipif(
    not URLSourceHandler().available,
    reason="aiohttp not available for URL downloads"
)
class TestURLInstallationWithDependencies:
    """Tests that require URL downloader dependencies."""
    
    def test_url_handler_availability(self):
        """Test URL handler availability with dependencies."""
        handler = URLSourceHandler()
        
        assert handler.available
        assert handler.downloader is not None
        assert handler.can_handle("https://example.com/test.zip")
    
    def test_url_downloader_configuration(self):
        """Test URL downloader configuration options."""
        handler = URLSourceHandler(
            max_file_size_mb=50,
            timeout_seconds=120,
            show_progress=False
        )
        
        assert handler.max_file_size_mb == 50
        assert handler.timeout_seconds == 120
        assert not handler.show_progress
        
        # Check that downloader is configured correctly
        assert handler.downloader.max_file_size_bytes == 50 * 1024 * 1024
        assert handler.downloader.timeout_seconds == 120