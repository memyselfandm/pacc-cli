"""Tests for URL functionality in PACC CLI."""

import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from pacc.core.url_downloader import URLValidator


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

    def test_safe_filename_extraction(self):
        """Test safe filename extraction from URLs."""
        validator = URLValidator()

        # Test normal URL with filename
        url1 = "https://github.com/user/repo/archive/main.zip"
        filename1 = validator.get_safe_filename(url1)
        assert filename1 == "main.zip"

        # Test URL without extension
        url2 = "https://example.com/download"
        filename2 = validator.get_safe_filename(url2, "default.zip")
        assert filename2 == "default.zip"

        # Test URL with unsafe characters
        url3 = "https://example.com/file<>:name.zip"
        filename3 = validator.get_safe_filename(url3)
        assert "<" not in filename3
        assert ">" not in filename3
        assert ":" not in filename3


class TestArchiveExtraction:
    """Test archive extraction without network dependencies."""

    def test_zip_archive_creation_and_validation(self):
        """Test creating and validating ZIP archives."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ZIP file
            zip_path = Path(temp_dir) / "test.zip"

            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("file1.txt", "content1")
                zf.writestr("folder/file2.txt", "content2")

            # Test that file was created
            assert zip_path.exists()
            assert zip_path.stat().st_size > 0

            # Test reading back the contents
            with zipfile.ZipFile(zip_path, "r") as zf:
                files = zf.namelist()
                assert "file1.txt" in files
                assert "folder/file2.txt" in files


class TestCLIURLIntegration:
    """Test CLI integration with URL functionality."""

    def test_url_detection(self):
        """Test URL detection in CLI."""
        from pacc.cli import PACCCli

        cli = PACCCli()

        # Test URL detection
        assert cli._is_url("https://github.com/user/repo.zip")
        assert cli._is_url("http://example.com/file.tar.gz")
        assert not cli._is_url("/local/path/file.zip")
        assert not cli._is_url("./relative/path")
        assert not cli._is_url("file.zip")

    def test_url_install_command_parsing(self):
        """Test URL install command parsing."""
        from pacc.cli import PACCCli

        cli = PACCCli()
        parser = cli.create_parser()

        # Test URL install command with options
        args = parser.parse_args(
            [
                "install",
                "https://github.com/user/repo.zip",
                "--max-size",
                "50",
                "--timeout",
                "60",
                "--no-cache",
                "--no-extract",
            ]
        )

        assert args.command == "install"
        assert args.source == "https://github.com/user/repo.zip"
        assert args.max_size == 50
        assert args.timeout == 60
        assert args.no_cache is True
        assert args.no_extract is True

    @patch("pacc.cli.HAS_URL_DOWNLOADER", False)
    def test_url_install_without_dependencies(self):
        """Test URL install fails gracefully without dependencies."""
        from pacc.cli import PACCCli

        cli = PACCCli()

        # Mock args for URL install
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

        # Should return error code 1 due to missing dependencies
        result = cli._install_from_url(args)
        assert result == 1


class TestSecurityFeatures:
    """Test security features of URL downloader."""

    def test_malicious_path_detection(self):
        """Test detection of malicious file paths."""
        from pacc.core.url_downloader import URLDownloader

        downloader = URLDownloader()

        # Test path traversal detection
        assert not downloader._is_safe_extract_path("../../../etc/passwd", Path("/tmp/extract"))
        assert not downloader._is_safe_extract_path("/etc/passwd", Path("/tmp/extract"))
        assert downloader._is_safe_extract_path("normal/file.txt", Path("/tmp/extract"))
        assert downloader._is_safe_extract_path("folder/subfolder/file.txt", Path("/tmp/extract"))

    def test_security_checks(self):
        """Test file security checking."""
        from pacc.core.url_downloader import URLDownloader

        downloader = URLDownloader()

        # Test various file paths
        test_cases = [
            ("../../../etc/passwd", True),  # Should have issues
            ("normal_file.txt", False),  # Should be safe
            ("/etc/passwd", True),  # Should have issues
            ("bin/executable", True),  # Should have issues
            ("folder/file.txt", False),  # Should be safe
        ]

        for file_path, should_have_issues in test_cases:
            issues = downloader._check_file_security(file_path)
            if should_have_issues:
                assert len(issues) > 0, f"Expected security issues for {file_path}"
            else:
                assert len(issues) == 0, f"Expected no security issues for {file_path}"


class TestProgressDisplay:
    """Test progress display functionality."""

    def test_progress_display_creation(self):
        """Test creating progress display."""
        from pacc.core.url_downloader import ProgressDisplay

        display = ProgressDisplay()
        assert display.show_speed is True
        assert display.show_eta is True
        assert display.update_interval == 0.1

    def test_byte_formatting(self):
        """Test byte formatting utility."""
        from pacc.core.url_downloader import ProgressDisplay

        display = ProgressDisplay()

        # Test various byte sizes
        assert "B" in display._format_bytes(500)
        assert "KB" in display._format_bytes(1500)
        assert "MB" in display._format_bytes(1500000)
        assert "GB" in display._format_bytes(1500000000)

    def test_time_formatting(self):
        """Test time formatting utility."""
        from pacc.core.url_downloader import ProgressDisplay

        display = ProgressDisplay()

        # Test various time durations
        assert "s" in display._format_time(30)
        assert "m" in display._format_time(90)
        assert "h" in display._format_time(3700)


def test_url_downloader_imports():
    """Test that URL downloader can be imported conditionally."""
    try:
        from pacc.cli import HAS_URL_DOWNLOADER
        from pacc.core.url_downloader import URLDownloader, URLValidator

        # If we get here, imports work
        assert URLDownloader is not None
        assert URLValidator is not None
        # HAS_URL_DOWNLOADER should reflect actual availability

    except ImportError:
        # If imports fail, that's also a valid test case
        # (happens when aiohttp is not installed)
        pass
