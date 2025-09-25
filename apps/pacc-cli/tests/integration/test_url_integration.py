"""Integration tests for URL-based installation."""

import argparse
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pacc.cli import PACCCli


class TestURLInstallationIntegration:
    """Test complete URL installation workflows."""

    def test_url_detection_and_routing(self):
        """Test that URLs are properly detected and routed."""
        cli = PACCCli()

        # Test URL detection
        assert cli._is_url("https://github.com/user/repo.zip")
        assert cli._is_url("http://example.com/package.tar.gz")
        assert not cli._is_url("./local/file.zip")
        assert not cli._is_url("/absolute/path/file.zip")

    def test_local_path_fallback(self):
        """Test that local paths still work with updated install command."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a simple test hook file
            hook_file = Path(temp_dir) / "test_hook.json"
            hook_content = {
                "name": "test_hook",
                "eventTypes": ["PreToolUse"],
                "commands": [{"matchers": ["*"], "command": "echo 'test'"}],
            }

            import json

            hook_file.write_text(json.dumps(hook_content, indent=2))

            cli = PACCCli()

            # Mock args for local install
            class MockArgs:
                source = str(hook_file)
                type = None
                user = False
                project = True
                force = False
                dry_run = True
                interactive = False
                all = False
                verbose = False
                no_extract = False
                max_size = 100
                timeout = 300
                no_cache = False

            args = MockArgs()

            # Should successfully process local file
            result = cli._install_from_local_path(args)
            assert result == 0  # Success

    def test_dry_run_url_install(self):
        """Test URL install in dry-run mode."""
        cli = PACCCli()

        class MockArgs:
            source = "https://github.com/user/repo.zip"
            user = False
            project = True
            dry_run = True
            verbose = False
            max_size = 100
            timeout = 300
            no_cache = False
            no_extract = False

        args = MockArgs()

        # With URL downloader available, dry-run should succeed
        with patch("pacc.cli.HAS_URL_DOWNLOADER", True):
            result = cli._install_from_url(args)
            assert result == 0  # Should succeed in dry-run mode

    def test_url_install_without_dependencies(self):
        """Test URL install fails gracefully without aiohttp."""
        cli = PACCCli()

        class MockArgs:
            source = "https://github.com/user/repo.zip"
            user = False
            project = True
            dry_run = False
            verbose = False
            max_size = 100
            timeout = 300
            no_cache = False
            no_extract = False

        args = MockArgs()

        # Without URL downloader, should fail gracefully
        with patch("pacc.cli.HAS_URL_DOWNLOADER", False):
            result = cli._install_from_url(args)
            assert result == 1  # Should fail gracefully

    def test_command_line_parsing(self):
        """Test complete command line parsing for URL installs."""
        cli = PACCCli()
        parser = cli.create_parser()

        # Test minimal URL install
        args = parser.parse_args(["install", "https://example.com/package.zip"])
        assert args.command == "install"
        assert args.source == "https://example.com/package.zip"
        assert args.max_size == 100  # Default
        assert args.timeout == 300  # Default
        assert args.no_cache is False  # Default
        assert args.no_extract is False  # Default

        # Test URL install with all options
        args = parser.parse_args(
            [
                "--verbose",  # Global option comes before command
                "install",
                "https://github.com/user/repo.tar.gz",
                "--user",
                "--force",
                "--max-size",
                "50",
                "--timeout",
                "120",
                "--no-cache",
                "--no-extract",
                "--dry-run",
            ]
        )

        assert args.source == "https://github.com/user/repo.tar.gz"
        assert args.user is True
        assert args.force is True
        assert args.max_size == 50
        assert args.timeout == 120
        assert args.no_cache is True
        assert args.no_extract is True
        assert args.dry_run is True

    def test_install_command_routing(self):
        """Test that install command properly routes URLs vs local paths."""
        cli = PACCCli()

        # Mock the actual installation methods
        with patch.object(cli, "_install_from_url") as mock_url_install, patch.object(
            cli, "_install_from_local_path"
        ) as mock_local_install:
            mock_url_install.return_value = 0
            mock_local_install.return_value = 0

            # Test URL routing
            class URLArgs:
                source = "https://github.com/user/repo.zip"
                verbose = False

            cli.install_command(URLArgs())
            mock_url_install.assert_called_once()
            mock_local_install.assert_not_called()

            # Reset mocks
            mock_url_install.reset_mock()
            mock_local_install.reset_mock()

            # Test local path routing
            class LocalArgs:
                source = "/local/path/file.zip"
                verbose = False

            cli.install_command(LocalArgs())
            mock_local_install.assert_called_once()
            mock_url_install.assert_not_called()

    def test_url_download_workflow_structure(self):
        """Test the URL download workflow structure without complex mocking."""
        cli = PACCCli()

        # Test that the method exists and has the right structure
        assert hasattr(cli, "_install_from_url")
        assert callable(cli._install_from_url)

        # Test that the method fails gracefully without dependencies
        with patch("pacc.cli.HAS_URL_DOWNLOADER", False):

            class MockArgs:
                source = "https://github.com/user/repo.zip"
                user = False
                project = True
                dry_run = False
                verbose = False
                max_size = 100
                timeout = 300
                no_cache = False
                no_extract = False

            args = MockArgs()
            result = cli._install_from_url(args)

            # Should fail gracefully with proper error message
            assert result == 1

    def test_error_handling(self):
        """Test error handling in URL installation."""
        cli = PACCCli()

        # Test with malformed URL
        class BadURLArgs:
            source = "not-a-valid-url"

        result = cli.install_command(BadURLArgs())
        # Should route to local path handler, which should fail
        assert result == 1

    def test_security_considerations(self):
        """Test that security features are properly integrated."""
        from pacc.core.url_downloader import URLValidator

        # Test that dangerous URLs are rejected
        validator = URLValidator()

        dangerous_urls = [
            "javascript:alert(1)",
            "data:text/html,<script>",
            "file:///etc/passwd",
            "ftp://example.com/file.zip",
        ]

        for url in dangerous_urls:
            assert not validator.is_valid_url(url), f"Should reject dangerous URL: {url}"

        # Test that safe URLs are accepted
        safe_urls = [
            "https://github.com/user/repo.zip",
            "http://example.com/package.tar.gz",
            "https://gitlab.com/project/archive.zip",
        ]

        for url in safe_urls:
            assert validator.is_valid_url(url), f"Should accept safe URL: {url}"


class TestFeatureCompleteness:
    """Test that Feature F1.2 requirements are met."""

    def test_url_download_functionality(self):
        """Test that URL download functionality is available."""
        try:
            from pacc.core.url_downloader import URLDownloader

            # Test that URLDownloader can be instantiated
            downloader = URLDownloader()
            assert downloader is not None
            assert hasattr(downloader, "download_file")
            assert hasattr(downloader, "extract_archive")
            assert hasattr(downloader, "install_from_url")
        except ImportError:
            # If aiohttp is not available, that's expected
            pytest.skip("aiohttp not available for URL downloads")

    def test_archive_format_support(self):
        """Test that various archive formats are supported."""
        from pacc.core.url_downloader import URLDownloader

        downloader = URLDownloader()
        supported_extensions = downloader.SUPPORTED_ARCHIVE_EXTENSIONS

        # Check that required formats are supported
        required_formats = {".zip", ".tar.gz", ".tar.bz2"}
        for fmt in required_formats:
            assert fmt in supported_extensions, f"Required format {fmt} not supported"

    def test_security_scanning(self):
        """Test that security scanning is implemented."""
        from pacc.core.url_downloader import URLDownloader

        downloader = URLDownloader()

        # Test that security methods exist
        assert hasattr(downloader, "scan_archive_security")
        assert hasattr(downloader, "_check_file_security")
        assert hasattr(downloader, "_is_safe_extract_path")

    def test_progress_indicators(self):
        """Test that progress indicators are available."""
        from pacc.core.url_downloader import DownloadProgress, ProgressDisplay

        # Test progress tracking
        progress = DownloadProgress()
        assert hasattr(progress, "percentage")
        assert hasattr(progress, "is_complete")

        # Test progress display
        display = ProgressDisplay()
        assert hasattr(display, "display_progress")

    def test_cli_integration(self):
        """Test that CLI integration is complete."""
        from pacc.cli import PACCCli

        cli = PACCCli()
        parser = cli.create_parser()

        # Get help text for the install command specifically
        subparsers_actions = [
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        ]

        if subparsers_actions:
            subparsers_action = subparsers_actions[0]
            install_parser = subparsers_action.choices.get("install")
            if install_parser:
                install_help = install_parser.format_help()

                assert "--no-extract" in install_help
                assert "--max-size" in install_help
                assert "--timeout" in install_help
                assert "--no-cache" in install_help
                assert "URL" in install_help or "url" in install_help

    def test_url_metadata_tracking(self):
        """Test that URL metadata can be tracked."""
        from pacc.core.url_downloader import DownloadResult

        # Test that download results contain URL metadata
        result = DownloadResult(
            success=True,
            url="https://example.com/package.zip",
            file_size=1024,
            content_type="application/zip",
            from_cache=False,
        )

        assert result.url == "https://example.com/package.zip"
        assert result.file_size == 1024
        assert result.content_type == "application/zip"
        assert result.from_cache is False
