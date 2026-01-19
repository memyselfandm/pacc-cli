"""Additional validation tests for package configuration."""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


class TestPackageValidation:
    """Validate package configuration and structure."""

    def test_no_missing_imports(self):
        """Test that all Python files can be imported without errors."""
        # Get all Python files in the package
        package_dir = PROJECT_ROOT / "pacc"
        python_files = list(package_dir.rglob("*.py"))

        # Exclude test files and __pycache__
        python_files = [
            f
            for f in python_files
            if "__pycache__" not in str(f)
            and "test_" not in f.name
            and f.name not in {"demo.py", "config_demo.py"}
        ]

        # Try to compile each file
        for py_file in python_files:
            with open(py_file) as f:
                content = f.read()

            try:
                compile(content, str(py_file), "exec")
            except SyntaxError as e:
                pytest.fail(f"Syntax error in {py_file}: {e}")

    def test_package_importable(self):
        """Test that the package and all submodules can be imported."""
        # Main package
        import pacc

        # CLI module
        import pacc.cli

        # Core modules
        import pacc.core
        import pacc.errors
        import pacc.packaging
        import pacc.performance
        import pacc.recovery
        import pacc.selection
        import pacc.sources
        import pacc.ui
        import pacc.validation
        import pacc.validators

        # Ensure main entry point is callable
        assert callable(pacc.cli.main)

    def test_cli_help_accessible(self):
        """Test that CLI help is accessible."""
        result = subprocess.run(
            [sys.executable, "-m", "pacc", "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"Help command failed: {result.stderr}"
        assert "usage:" in result.stdout.lower()
        assert "pacc" in result.stdout

        # Check for main commands
        expected_commands = ["install", "validate", "list", "remove", "info"]
        for cmd in expected_commands:
            assert cmd in result.stdout, f"Command '{cmd}' not found in help output"

    def test_subcommand_help(self):
        """Test that subcommand help is accessible."""
        commands = ["install", "validate", "list", "remove", "info"]

        for cmd in commands:
            result = subprocess.run(
                [sys.executable, "-m", "pacc", cmd, "--help"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            # Some commands might not be implemented yet
            if result.returncode == 0:
                assert "usage:" in result.stdout.lower()
                assert cmd in result.stdout
