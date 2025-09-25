"""Test scripts for verifying PACC installation."""

import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

import pytest


class TestInstallationScripts:
    """Test PACC installation in different scenarios."""

    @pytest.fixture
    def pacc_source_dir(self):
        """Get the PACC source directory."""
        return Path(__file__).parent.parent

    @pytest.fixture
    def temp_venv_dir(self):
        """Create a temporary virtual environment."""
        temp_dir = tempfile.mkdtemp()
        venv_dir = Path(temp_dir) / "test_venv"
        yield venv_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    def create_venv(self, venv_dir):
        """Create a virtual environment."""
        venv.create(venv_dir, with_pip=True)

        # Get the Python executable in the venv
        if sys.platform == "win32":
            python_exe = venv_dir / "Scripts" / "python.exe"
            pip_exe = venv_dir / "Scripts" / "pip.exe"
        else:
            python_exe = venv_dir / "bin" / "python"
            pip_exe = venv_dir / "bin" / "pip"

        return python_exe, pip_exe

    @pytest.mark.slow
    def test_editable_installation(self, pacc_source_dir, temp_venv_dir):
        """Test editable installation of PACC."""
        # Create virtual environment
        python_exe, pip_exe = self.create_venv(temp_venv_dir)

        # Install in editable mode
        result = subprocess.run(
            [str(pip_exe), "install", "-e", str(pacc_source_dir)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify pacc command is available
        result = subprocess.run(
            [str(python_exe), "-m", "pacc", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "pacc" in result.stdout

        # Verify it's truly editable by checking if changes are reflected
        # This is verified by the presence of .egg-link file
        if sys.platform == "win32":
            site_packages = temp_venv_dir / "Lib" / "site-packages"
        else:
            # Find site-packages directory
            result = subprocess.run(
                [str(python_exe), "-c", "import site; print(site.getsitepackages()[0])"],
                capture_output=True,
                text=True,
                check=False,
            )
            site_packages = Path(result.stdout.strip())

        egg_link = site_packages / "pacc.egg-link"
        assert egg_link.exists(), "Editable installation not detected"

    @pytest.mark.slow
    def test_wheel_installation(self, pacc_source_dir, temp_venv_dir):
        """Test wheel installation of PACC."""
        # Create virtual environment
        python_exe, pip_exe = self.create_venv(temp_venv_dir)

        # Build wheel
        dist_dir = pacc_source_dir / "dist"

        # Install build tools
        subprocess.run([str(pip_exe), "install", "build"], capture_output=True, check=False)

        # Build the wheel
        result = subprocess.run(
            [str(python_exe), "-m", "build", "--wheel", str(pacc_source_dir)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"Build failed: {result.stderr}"

        # Find the built wheel
        wheel_files = list(dist_dir.glob("*.whl"))
        assert len(wheel_files) > 0, "No wheel file found"

        wheel_file = wheel_files[0]

        # Install the wheel
        result = subprocess.run(
            [str(pip_exe), "install", str(wheel_file)], capture_output=True, text=True, check=False
        )

        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify pacc command works
        result = subprocess.run(
            [str(python_exe), "-m", "pacc", "--help"], capture_output=True, text=True, check=False
        )

        assert result.returncode == 0
        assert "PACC - Package manager for Claude Code" in result.stdout

    def test_direct_script_execution(self, pacc_source_dir):
        """Test running PACC directly without installation."""
        # Run directly using python -m from source
        result = subprocess.run(
            [sys.executable, "-m", "pacc", "--version"],
            cwd=pacc_source_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "pacc" in result.stdout

    def test_console_script_entry_point(self, pacc_source_dir, temp_venv_dir):
        """Test console_scripts entry point after installation."""
        # Create virtual environment
        python_exe, pip_exe = self.create_venv(temp_venv_dir)

        # Install in editable mode
        subprocess.run(
            [str(pip_exe), "install", "-e", str(pacc_source_dir)], capture_output=True, check=False
        )

        # Check if pacc command is available as console script
        if sys.platform == "win32":
            pacc_exe = temp_venv_dir / "Scripts" / "pacc.exe"
        else:
            pacc_exe = temp_venv_dir / "bin" / "pacc"

        assert pacc_exe.exists(), f"Console script not found at {pacc_exe}"

        # Run the console script
        result = subprocess.run(
            [str(pacc_exe), "--version"], capture_output=True, text=True, check=False
        )

        assert result.returncode == 0
        assert "pacc" in result.stdout

    def test_cross_platform_compatibility(self, pacc_source_dir):
        """Test basic cross-platform compatibility."""
        # Test path handling
        result = subprocess.run(
            [sys.executable, "-m", "pacc", "validate", "non_existent_file.json"],
            cwd=pacc_source_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        # Should fail gracefully on all platforms
        assert result.returncode == 1

        # Error message should use proper path separators
        if sys.platform == "win32":
            # Windows paths might use backslashes
            assert "\\" in result.stdout or "/" in result.stdout
        else:
            # Unix paths use forward slashes
            assert "/" in result.stdout

    def test_python_version_compatibility(self, pacc_source_dir):
        """Test Python version requirements."""
        # Get current Python version
        import sys

        current_version = sys.version_info

        # PACC requires Python 3.8+
        assert current_version >= (3, 8), "Test suite requires Python 3.8+"

        # Verify version check in code
        result = subprocess.run(
            [sys.executable, "-c", "import pacc; print('OK')"],
            cwd=pacc_source_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "OK" in result.stdout
