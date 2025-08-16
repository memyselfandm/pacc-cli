#!/usr/bin/env python3
"""
Test suite for local installation and command availability.

These tests verify that PACC can be installed locally and that
the command-line interface works correctly after installation.
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
import pytest


class TestLocalInstallation:
    """Test local installation scenarios."""
    
    @pytest.fixture
    def wheel_file(self):
        """Get the built wheel file."""
        project_root = Path(__file__).parent.parent
        dist_dir = project_root / "dist"
        
        if not dist_dir.exists():
            pytest.skip("No dist directory found. Run 'make build' first.")
        
        wheel_files = list(dist_dir.glob("*.whl"))
        if not wheel_files:
            pytest.skip("No wheel file found. Run 'make build' first.")
        
        return wheel_files[0]
    
    def test_pip_install_wheel(self, wheel_file, tmp_path):
        """Test installing PACC via pip from wheel."""
        # Create virtual environment
        venv_dir = tmp_path / "test_venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True
        )
        
        # Get pip path
        if sys.platform == "win32":
            pip_path = venv_dir / "Scripts" / "pip"
        else:
            pip_path = venv_dir / "bin" / "pip"
        
        # Install wheel
        result = subprocess.run(
            [str(pip_path), "install", str(wheel_file)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Installation failed: {result.stderr}"
        assert "Successfully installed pacc" in result.stdout
    
    def test_editable_install(self, tmp_path):
        """Test editable installation for development."""
        project_root = Path(__file__).parent.parent
        
        # Create virtual environment
        venv_dir = tmp_path / "test_venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True
        )
        
        # Get pip path
        if sys.platform == "win32":
            pip_path = venv_dir / "Scripts" / "pip"
        else:
            pip_path = venv_dir / "bin" / "pip"
        
        # Install in editable mode
        result = subprocess.run(
            [str(pip_path), "install", "-e", str(project_root)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0, f"Editable install failed: {result.stderr}"
    
    def test_command_entry_point(self, wheel_file, tmp_path):
        """Test that pacc command is available after installation."""
        # Create and setup virtual environment
        venv_dir = tmp_path / "test_venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True
        )
        
        if sys.platform == "win32":
            pip_path = venv_dir / "Scripts" / "pip"
            pacc_path = venv_dir / "Scripts" / "pacc"
        else:
            pip_path = venv_dir / "bin" / "pip"
            pacc_path = venv_dir / "bin" / "pacc"
        
        # Install
        subprocess.run(
            [str(pip_path), "install", str(wheel_file)],
            check=True
        )
        
        # Check command exists
        assert pacc_path.exists(), "pacc command not found"
        
        # Test command execution
        result = subprocess.run(
            [str(pacc_path), "--version"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "1.0.0" in result.stdout
    
    def test_import_after_install(self, wheel_file, tmp_path):
        """Test importing PACC modules after installation."""
        # Setup virtual environment
        venv_dir = tmp_path / "test_venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True
        )
        
        if sys.platform == "win32":
            pip_path = venv_dir / "Scripts" / "pip"
            python_path = venv_dir / "Scripts" / "python"
        else:
            pip_path = venv_dir / "bin" / "pip"
            python_path = venv_dir / "bin" / "python"
        
        # Install
        subprocess.run(
            [str(pip_path), "install", str(wheel_file)],
            check=True
        )
        
        # Test imports
        test_imports = [
            "import pacc",
            "from pacc import __version__",
            "from pacc.cli import main",
            "from pacc.validators import HooksValidator",
            "from pacc.core import file_utils",
        ]
        
        for import_stmt in test_imports:
            result = subprocess.run(
                [str(python_path), "-c", import_stmt],
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0, f"Import failed: {import_stmt}\n{result.stderr}"
    
    def test_help_commands(self, wheel_file, tmp_path):
        """Test that help commands work correctly."""
        # Setup
        venv_dir = tmp_path / "test_venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True
        )
        
        if sys.platform == "win32":
            pip_path = venv_dir / "Scripts" / "pip"
            pacc_path = venv_dir / "Scripts" / "pacc"
        else:
            pip_path = venv_dir / "bin" / "pip"
            pacc_path = venv_dir / "bin" / "pacc"
        
        # Install
        subprocess.run(
            [str(pip_path), "install", str(wheel_file)],
            check=True
        )
        
        # Test various help commands
        help_commands = [
            ["--help"],
            ["install", "--help"],
            ["validate", "--help"],
            ["list", "--help"],
        ]
        
        for cmd in help_commands:
            result = subprocess.run(
                [str(pacc_path)] + cmd,
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0, f"Help command failed: {' '.join(cmd)}"
            assert "usage:" in result.stdout.lower()
    
    def test_uninstall_cleanup(self, wheel_file, tmp_path):
        """Test that uninstallation removes all files."""
        # Setup
        venv_dir = tmp_path / "test_venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True
        )
        
        if sys.platform == "win32":
            pip_path = venv_dir / "Scripts" / "pip"
            pacc_path = venv_dir / "Scripts" / "pacc"
        else:
            pip_path = venv_dir / "bin" / "pip"
            pacc_path = venv_dir / "bin" / "pacc"
        
        # Install
        subprocess.run(
            [str(pip_path), "install", str(wheel_file)],
            check=True
        )
        
        # Verify installed
        assert pacc_path.exists()
        
        # Uninstall
        result = subprocess.run(
            [str(pip_path), "uninstall", "-y", "pacc"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert not pacc_path.exists(), "pacc command still exists after uninstall"


class TestPackageValidation:
    """Test package structure and metadata validation."""
    
    def test_package_version_consistency(self):
        """Test version is consistent across all files."""
        project_root = Path(__file__).parent.parent
        
        # Read version from __init__.py
        init_file = project_root / "pacc" / "__init__.py"
        init_version = None
        
        with open(init_file, "r") as f:
            for line in f:
                if line.startswith("__version__"):
                    init_version = line.split("=")[1].strip().strip('"\'')
                    break
        
        assert init_version == "1.0.0", f"Expected version 1.0.0, got {init_version}"
        
        # Check it's accessible via import
        import pacc
        assert pacc.__version__ == init_version
    
    def test_all_modules_importable(self):
        """Test that all package modules can be imported."""
        import pacc
        import pacc.cli
        import pacc.core
        import pacc.ui
        import pacc.validators
        import pacc.validation
        import pacc.errors
        import pacc.selection
        import pacc.packaging
        import pacc.recovery
        import pacc.performance
        
        # Verify submodules
        from pacc.core import file_utils
        from pacc.validators import HooksValidator, MCPValidator
        from pacc.ui import components
        from pacc.errors import exceptions
    
    def test_entry_point_callable(self):
        """Test that the CLI entry point is callable."""
        from pacc.cli import main
        
        # Should be callable
        assert callable(main)
        
        # Test with --help (should exit with SystemExit)
        with pytest.raises(SystemExit) as exc_info:
            sys.argv = ["pacc", "--help"]
            main()
        
        # Help should exit with code 0
        assert exc_info.value.code == 0