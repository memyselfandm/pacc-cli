"""Test version accessibility and consistency."""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


def test_version_import():
    """Test that version can be imported from the package."""
    import pacc

    assert hasattr(pacc, "__version__")
    assert pacc.__version__ == "1.0.0"


def test_version_cli_flag():
    """Test that --version flag works in CLI."""
    result = subprocess.run(
        [sys.executable, "-m", "pacc", "--version"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    # Check return code
    assert result.returncode == 0, f"Version command failed: {result.stderr}"

    # Check output contains version
    assert "1.0.0" in result.stdout, f"Version not in output: {result.stdout}"


def test_version_consistency():
    """Test that version is consistent across all locations."""
    # Import version from package
    import pacc

    package_version = pacc.__version__

    # Read version from pyproject.toml
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            pytest.skip("No TOML parser available")

    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    pyproject_version = data["project"]["version"]

    # Ensure they match
    assert (
        package_version == pyproject_version
    ), f"Version mismatch: package={package_version}, pyproject.toml={pyproject_version}"


def test_version_format():
    """Test that version follows semantic versioning."""
    import re

    import pacc

    # Semantic versioning pattern
    semver_pattern = r"^(\d+)\.(\d+)\.(\d+)(?:[-+][\w\.]+)?$"

    match = re.match(semver_pattern, pacc.__version__)
    assert match, f"Version {pacc.__version__} does not follow semantic versioning"

    # Extract major, minor, patch
    major, minor, patch = match.groups()[:3]
    assert int(major) >= 0
    assert int(minor) >= 0
    assert int(patch) >= 0
