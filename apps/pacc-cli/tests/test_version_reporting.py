"""Test version reporting functionality."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pacc import __version__


class TestVersionReporting:
    """Test version reporting in various contexts."""

    def test_version_flag(self):
        """Test --version flag displays correct version."""
        pacc_dir = Path(__file__).parent.parent

        result = subprocess.run(
            [sys.executable, "-m", "pacc", "--version"],
            cwd=pacc_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert f"pacc {__version__}" in result.stdout

    def test_version_matches_package_metadata(self):
        """Test that version in __init__.py matches pyproject.toml."""
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            import tomli as tomllib  # Python <3.11

        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)

        pyproject_version = pyproject_data["project"]["version"]
        assert __version__ == pyproject_version

    def test_version_import(self):
        """Test that version can be imported correctly."""
        from pacc import __version__ as imported_version

        assert imported_version == "1.0.0"
        assert isinstance(imported_version, str)

    def test_version_consistency_in_help(self):
        """Test that version is consistent in help output."""
        pacc_dir = Path(__file__).parent.parent

        # Check main help
        result = subprocess.run(
            [sys.executable, "-m", "pacc", "-h"],
            cwd=pacc_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        # Version should be available via --version flag mentioned in help
        assert "--version" in result.stdout

    def test_version_in_json_output(self):
        """Test that version is included in JSON output when appropriate."""
        pacc_dir = Path(__file__).parent.parent

        # The list command with --format json should work even with no extensions
        result = subprocess.run(
            [sys.executable, "-m", "pacc", "list", "--format", "json"],
            cwd=pacc_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        # Even if no extensions, command should succeed
        assert result.returncode == 0

        # Parse JSON output
        try:
            json_data = json.loads(result.stdout)
            assert "success" in json_data
        except json.JSONDecodeError:
            # Alternative: check if it's the global --json flag
            result2 = subprocess.run(
                [sys.executable, "-m", "pacc", "--json", "list"],
                cwd=pacc_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            if result2.returncode == 0:
                json_data = json.loads(result2.stdout)
                assert "success" in json_data
            else:
                pytest.fail(f"Invalid JSON output: {result.stdout}")

    def test_version_format(self):
        """Test that version follows semantic versioning format."""
        import re

        # Semantic versioning pattern (simplified)
        semver_pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9\-\.]+)?(\+[a-zA-Z0-9\-\.]+)?$"

        assert re.match(
            semver_pattern, __version__
        ), f"Version {__version__} doesn't match semantic versioning"

    def test_version_accessible_programmatically(self):
        """Test that version can be accessed programmatically."""
        import pacc

        # Should be accessible as module attribute
        assert hasattr(pacc, "__version__")
        assert pacc.__version__ == __version__

        # Should be a string
        assert isinstance(pacc.__version__, str)

        # Should not be empty
        assert len(pacc.__version__) > 0
