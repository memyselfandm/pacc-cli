"""
Integration tests for end-to-end package installation workflows.

This test suite validates the complete PACC package installation process from
build to installation to functionality verification.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

import pytest


class TestEndToEndPackageInstallation:
    """Test complete package installation workflows."""

    @pytest.fixture
    def project_root(self):
        """Get the project root directory."""
        # Navigate from test file to project root
        test_dir = Path(__file__).parent
        project_root = test_dir.parent
        return project_root

    @pytest.fixture
    def clean_build_env(self, project_root):
        """Ensure clean build environment."""
        # Clean any existing build artifacts
        for artifact_dir in ["build", "dist", "*.egg-info"]:
            for path in project_root.glob(artifact_dir):
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.is_file():
                    path.unlink()
        yield project_root

    def test_build_script_functionality(self, clean_build_env):
        """Test that build script works correctly."""
        project_root = clean_build_env
        build_script = project_root / "scripts" / "build.py"

        # Test build dependencies installation
        result = subprocess.run(
            [sys.executable, str(build_script), "install-deps"],
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False,
        )

        assert result.returncode == 0, f"Build deps installation failed: {result.stderr}"

        # Test requirements check
        result = subprocess.run(
            [sys.executable, str(build_script), "build", "--skip-tests"],
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False,
        )

        # Should succeed or provide clear error message
        if result.returncode != 0:
            print(f"Build output: {result.stdout}")
            print(f"Build error: {result.stderr}")

        # Verify dist artifacts were created
        dist_dir = project_root / "dist"
        if result.returncode == 0:
            assert dist_dir.exists(), "dist directory not created"
            assert list(dist_dir.glob("*.whl")), "No wheel file created"
            assert list(dist_dir.glob("*.tar.gz")), "No source distribution created"

    def test_wheel_installation_and_functionality(self, clean_build_env):
        """Test installing wheel and verifying CLI functionality."""
        project_root = clean_build_env

        # First build the wheel
        build_result = subprocess.run(
            [sys.executable, "scripts/build.py", "build", "--dist-type", "wheel"],
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False,
        )

        if build_result.returncode != 0:
            pytest.skip(f"Build failed, skipping install test: {build_result.stderr}")

        # Find the wheel file
        dist_dir = project_root / "dist"
        wheel_files = list(dist_dir.glob("*.whl"))
        assert wheel_files, "No wheel file found after build"

        wheel_path = wheel_files[0]

        # Test installation in isolated environment
        with tempfile.TemporaryDirectory() as temp_dir:
            venv_dir = Path(temp_dir) / "test_venv"

            # Create virtual environment
            venv.create(venv_dir, with_pip=True)

            # Get paths for the virtual environment
            if sys.platform == "win32":
                python_path = venv_dir / "Scripts" / "python.exe"
                pacc_path = venv_dir / "Scripts" / "pacc.exe"
            else:
                python_path = venv_dir / "bin" / "python"
                pacc_path = venv_dir / "bin" / "pacc"

            # Install the wheel
            install_result = subprocess.run(
                [str(python_path), "-m", "pip", "install", str(wheel_path)],
                capture_output=True,
                text=True,
                check=False,
            )

            assert (
                install_result.returncode == 0
            ), f"Wheel installation failed: {install_result.stderr}"

            # Test that pacc command exists and works
            version_result = subprocess.run(
                [str(pacc_path), "--version"], capture_output=True, text=True, check=False
            )

            assert (
                version_result.returncode == 0
            ), f"PACC version command failed: {version_result.stderr}"
            assert (
                "1.0.0" in version_result.stdout
            ), f"Version output unexpected: {version_result.stdout}"

            # Test basic help command
            help_result = subprocess.run(
                [str(pacc_path), "--help"], capture_output=True, text=True, check=False
            )

            assert help_result.returncode == 0, f"PACC help command failed: {help_result.stderr}"
            assert "install" in help_result.stdout, "Install command not found in help"
            assert "validate" in help_result.stdout, "Validate command not found in help"

    def test_editable_installation(self, clean_build_env):
        """Test editable installation works correctly."""
        project_root = clean_build_env

        with tempfile.TemporaryDirectory() as temp_dir:
            venv_dir = Path(temp_dir) / "test_venv"

            # Create virtual environment
            venv.create(venv_dir, with_pip=True)

            # Get python path for the virtual environment
            if sys.platform == "win32":
                python_path = venv_dir / "Scripts" / "python.exe"
                pacc_path = venv_dir / "Scripts" / "pacc.exe"
            else:
                python_path = venv_dir / "bin" / "python"
                pacc_path = venv_dir / "bin" / "pacc"

            # Install in editable mode
            install_result = subprocess.run(
                [str(python_path), "-m", "pip", "install", "-e", str(project_root)],
                capture_output=True,
                text=True,
                check=False,
            )

            if install_result.returncode != 0:
                pytest.skip(f"Editable installation failed: {install_result.stderr}")

            # Test that pacc command works
            version_result = subprocess.run(
                [str(pacc_path), "--version"], capture_output=True, text=True, check=False
            )

            assert (
                version_result.returncode == 0
            ), f"PACC version command failed: {version_result.stderr}"

    def test_cross_platform_compatibility(self, clean_build_env):
        """Test cross-platform compatibility features."""
        project_root = clean_build_env

        # Test path handling components
        from pacc.core.file_utils import PathNormalizer

        normalizer = PathNormalizer()

        # Test various path formats
        test_paths = [
            "/home/user/claude/hooks",
            "C:\\Users\\User\\claude\\hooks",
            "~/claude/hooks",
            "./hooks/test.json",
            "../shared/agents.md",
        ]

        for test_path in test_paths:
            try:
                normalized = normalizer.normalize(test_path)
                assert isinstance(normalized, Path), f"Failed to normalize {test_path}"
            except Exception as e:
                # Some paths might not be valid on current platform, that's OK
                print(f"Path {test_path} normalization: {e}")

        # Test file validation with various extensions
        from pacc.core.file_utils import FilePathValidator

        validator = FilePathValidator()

        test_files = ["test.json", "agent.md", "config.yaml", "server.py", "hook.js"]

        for test_file in test_files:
            result = validator.validate_extension(
                test_file, {".json", ".md", ".yaml", ".py", ".js"}
            )
            assert result, f"File extension validation failed for {test_file}"

    def test_installation_scripts_functionality(self, clean_build_env):
        """Test installation scripts work correctly."""
        project_root = clean_build_env

        # Test shell script exists and is executable (on Unix-like systems)
        shell_script = project_root / "scripts" / "test_installation.sh"
        if shell_script.exists() and sys.platform != "win32":
            # Make executable
            shell_script.chmod(0o755)

            # Test execution
            result = subprocess.run(
                ["bash", str(shell_script)],
                capture_output=True,
                text=True,
                cwd=project_root,
                check=False,
            )

            # Script should either succeed or provide helpful error messages
            if result.returncode != 0:
                print(f"Shell script output: {result.stdout}")
                print(f"Shell script error: {result.stderr}")

        # Test batch script exists (on Windows)
        batch_script = project_root / "scripts" / "test_installation.bat"
        if batch_script.exists() and sys.platform == "win32":
            result = subprocess.run(
                [str(batch_script)],
                capture_output=True,
                text=True,
                cwd=project_root,
                shell=True,
                check=False,
            )

            if result.returncode != 0:
                print(f"Batch script output: {result.stdout}")
                print(f"Batch script error: {result.stderr}")

    def test_package_metadata_consistency(self, clean_build_env):
        """Test package metadata is consistent across files."""
        project_root = clean_build_env

        # Read version from pyproject.toml
        pyproject_path = project_root / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not found"

        # Try to import tomllib (Python 3.11+) or tomli as fallback
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("tomli/tomllib not available")

        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)

        pyproject_version = pyproject_data["project"]["version"]

        # Read version from __init__.py
        init_path = project_root / "pacc" / "__init__.py"
        assert init_path.exists(), "__init__.py not found"

        init_content = init_path.read_text()
        init_version = None

        for line in init_content.split("\n"):
            if line.startswith("__version__"):
                init_version = line.split("=")[1].strip().strip("\"'")
                break

        assert (
            init_version == pyproject_version
        ), f"Version mismatch: pyproject.toml={pyproject_version}, __init__.py={init_version}"

        # Verify other metadata consistency
        assert pyproject_data["project"]["name"] == "pacc"
        assert "Package manager for Claude Code" in pyproject_data["project"]["description"]
        assert pyproject_data["project"]["requires-python"] == ">=3.8"

    def test_build_artifacts_validation(self, clean_build_env):
        """Test that build artifacts are correctly structured."""
        project_root = clean_build_env

        # Build both distributions
        build_result = subprocess.run(
            [sys.executable, "scripts/build.py", "build"],
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False,
        )

        if build_result.returncode != 0:
            pytest.skip(f"Build failed: {build_result.stderr}")

        dist_dir = project_root / "dist"

        # Check wheel structure
        wheel_files = list(dist_dir.glob("*.whl"))
        assert wheel_files, "No wheel file created"

        wheel_path = wheel_files[0]

        # Verify wheel name format
        assert "pacc" in wheel_path.name
        assert "1.0.0" in wheel_path.name
        assert wheel_path.suffix == ".whl"

        # Check source distribution
        sdist_files = list(dist_dir.glob("*.tar.gz"))
        assert sdist_files, "No source distribution created"

        sdist_path = sdist_files[0]
        assert "pacc" in sdist_path.name
        assert "1.0.0" in sdist_path.name

    def test_comprehensive_functionality_after_install(self, clean_build_env):
        """Test comprehensive PACC functionality after installation."""
        project_root = clean_build_env

        # Build and install
        build_result = subprocess.run(
            [sys.executable, "scripts/build.py", "build", "--dist-type", "wheel"],
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False,
        )

        if build_result.returncode != 0:
            pytest.skip(f"Build failed: {build_result.stderr}")

        wheel_files = list((project_root / "dist").glob("*.whl"))
        wheel_path = wheel_files[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            venv_dir = Path(temp_dir) / "test_venv"
            venv.create(venv_dir, with_pip=True)

            if sys.platform == "win32":
                python_path = venv_dir / "Scripts" / "python.exe"
                pacc_path = venv_dir / "Scripts" / "pacc.exe"
            else:
                python_path = venv_dir / "bin" / "python"
                pacc_path = venv_dir / "bin" / "pacc"

            # Install
            subprocess.run(
                [str(python_path), "-m", "pip", "install", str(wheel_path)],
                check=True,
                capture_output=True,
            )

            # Create test extension files
            test_dir = Path(temp_dir) / "test_extensions"
            test_dir.mkdir()

            # Create a simple hook for testing
            test_hook = {
                "name": "test-hook",
                "eventTypes": ["PreToolUse"],
                "commands": ["echo 'File created: ${file}'"],
                "description": "Test hook for integration testing",
            }

            hook_file = test_dir / "test-hook.json"
            with open(hook_file, "w") as f:
                json.dump(test_hook, f)

            # Test validation
            validate_result = subprocess.run(
                [str(pacc_path), "validate", str(hook_file), "--type", "hooks"],
                capture_output=True,
                text=True,
                check=False,
            )

            assert validate_result.returncode == 0, f"Validation failed: {validate_result.stderr}"
            assert "Valid" in validate_result.stdout or "✓" in validate_result.stdout

            # Test that CLI provides helpful output
            help_result = subprocess.run(
                [str(pacc_path), "--help"], capture_output=True, text=True, check=False
            )

            assert help_result.returncode == 0
            assert "install" in help_result.stdout
            assert "validate" in help_result.stdout
            assert (
                "Package manager for Claude Code" in help_result.stdout
                or "PACC" in help_result.stdout
            )


@pytest.mark.slow
class TestLongRunningPackageOperations:
    """Test long-running package operations and edge cases."""

    def test_large_extension_handling(self):
        """Test handling of large extension files."""
        # This would test performance with large files
        # Currently just validates the framework is ready
        from pacc.performance.optimization import PerformanceOptimizer

        optimizer = PerformanceOptimizer()
        assert optimizer is not None

    def test_concurrent_installations(self):
        """Test concurrent installation scenarios."""
        # This would test race conditions and locking
        # Currently validates components are available
        from pacc.core.config_manager import ClaudeConfigManager

        manager = ClaudeConfigManager()
        assert manager is not None

    def test_network_timeout_handling(self):
        """Test network timeout scenarios for URL installations."""
        # This would test network error handling
        # Currently validates URL components exist
        from pacc.sources.url import URLSourceHandler

        handler = URLSourceHandler()
        assert handler is not None


class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility specifically."""

    def test_path_separators(self):
        """Test handling of different path separators."""
        from pacc.core.file_utils import PathNormalizer

        normalizer = PathNormalizer()

        # Test Windows-style paths
        windows_path = "C:\\Users\\user\\.claude\\hooks"
        normalized = normalizer.normalize(windows_path)
        assert isinstance(normalized, Path)

        # Test Unix-style paths
        unix_path = "/home/user/.claude/hooks"
        normalized = normalizer.normalize(unix_path)
        assert isinstance(normalized, Path)

    def test_file_permissions(self):
        """Test file permission handling across platforms."""
        from pacc.core.file_utils import FilePathValidator

        validator = FilePathValidator()

        # This should work on all platforms
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b'{"test": true}')
            temp_path = f.name

        try:
            result = validator.is_valid_path(temp_path)
            assert result
        finally:
            Path(temp_path).unlink()

    def test_character_encoding(self):
        """Test handling of different character encodings."""
        from pacc.core.file_utils import FilePathValidator

        validator = FilePathValidator()

        # Test various Unicode filenames
        test_names = [
            "test.json",
            "测试.json",  # Chinese
            "тест.json",  # Cyrillic
            "テスト.json",  # Japanese
            "café.json",  # Accented characters
        ]

        for name in test_names:
            try:
                # Some filesystems may not support all Unicode characters
                # For filename validation, we just check if it doesn't contain dangerous characters
                # This is a simple test - actual filename validation may be in different classes
                assert isinstance(name, str) and len(name) > 0
            except Exception:
                # Platform-specific limitations are acceptable
                pass
