"""Tests for PyPI package configuration and metadata."""

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent


class TestPackageMetadata:
    """Test package metadata configuration."""

    def test_pyproject_toml_exists(self):
        """Test that pyproject.toml exists in the project root."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml must exist in project root"

    def test_pyproject_toml_valid_syntax(self):
        """Test that pyproject.toml has valid TOML syntax."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        # Try to parse the TOML file
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("No TOML parser available")

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            assert isinstance(data, dict), "pyproject.toml must parse to a dictionary"

    def test_project_metadata_complete(self):
        """Test that all required project metadata is present."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("No TOML parser available")

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        # Check build system
        assert "build-system" in data, "build-system section must be defined"
        assert "requires" in data["build-system"], "build-system.requires must be defined"
        assert "build-backend" in data["build-system"], "build-system.build-backend must be defined"

        # Check project metadata
        assert "project" in data, "project section must be defined"
        project = data["project"]

        # Required fields
        assert "name" in project, "project.name must be defined"
        assert project["name"] == "pacc", "project name must be 'pacc'"

        assert (
            "version" in project or "dynamic" in project
        ), "project.version or dynamic version must be defined"
        assert "description" in project, "project.description must be defined"
        assert "authors" in project, "project.authors must be defined"
        assert "license" in project, "project.license must be defined"
        assert "requires-python" in project, "project.requires-python must be defined"

        # Check Python version requirement
        assert project["requires-python"] == ">=3.8", "Must support Python 3.8+"

        # Recommended fields
        assert "readme" in project, "project.readme should be defined"
        assert "keywords" in project, "project.keywords should be defined"
        assert "classifiers" in project, "project.classifiers should be defined"
        assert "urls" in project, "project.urls should be defined"

    def test_console_scripts_entry_point(self):
        """Test that console_scripts entry point is properly configured."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("No TOML parser available")

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        project = data.get("project", {})
        scripts = project.get("scripts", {})

        assert "pacc" in scripts, "pacc console script must be defined"
        assert scripts["pacc"] == "pacc.cli:main", "pacc script must point to pacc.cli:main"

    def test_dependencies_configuration(self):
        """Test that dependencies are properly configured."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("No TOML parser available")

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        project = data.get("project", {})

        # Core dependencies should be minimal
        dependencies = project.get("dependencies", [])
        assert isinstance(dependencies, list), "dependencies must be a list"
        # PACC should have minimal required dependencies
        assert len(dependencies) == 1, "PACC should have exactly one required dependency (PyYAML)"
        assert any(
            "PyYAML" in dep for dep in dependencies
        ), "PyYAML should be a required dependency"

        # Optional dependencies for advanced features
        optional_deps = project.get("optional-dependencies", {})
        assert "url" in optional_deps, "url optional dependency group should be defined"
        url_deps = optional_deps["url"]
        assert "aiohttp>=3.8.0" in url_deps, "aiohttp should be in url dependencies"
        assert "aiofiles>=0.8.0" in url_deps, "aiofiles should be in url dependencies"

        # Development dependencies
        assert "dev" in optional_deps, "dev optional dependency group should be defined"
        dev_deps = optional_deps["dev"]
        assert any("pytest" in dep for dep in dev_deps), "pytest should be in dev dependencies"
        assert any("mypy" in dep for dep in dev_deps), "mypy should be in dev dependencies"
        assert any("ruff" in dep for dep in dev_deps), "ruff should be in dev dependencies"

    def test_package_urls(self):
        """Test that project URLs are properly configured."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("No TOML parser available")

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        urls = data.get("project", {}).get("urls", {})

        # Required URLs
        assert (
            "Homepage" in urls or "Repository" in urls
        ), "Homepage or Repository URL must be defined"
        assert (
            "Issues" in urls or "Bug Tracker" in urls
        ), "Issues or Bug Tracker URL must be defined"
        assert "Documentation" in urls, "Documentation URL should be defined"

    def test_classifiers(self):
        """Test that appropriate PyPI classifiers are set."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("No TOML parser available")

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        classifiers = data.get("project", {}).get("classifiers", [])

        # Check for essential classifiers
        assert any(
            "Development Status" in c for c in classifiers
        ), "Development Status classifier required"
        assert any(
            "Intended Audience :: Developers" in c for c in classifiers
        ), "Target audience classifier required"
        assert any("License" in c for c in classifiers), "License classifier required"
        assert any(
            "Programming Language :: Python :: 3" in c for c in classifiers
        ), "Python 3 classifier required"
        assert any(
            "Programming Language :: Python :: 3.8" in c for c in classifiers
        ), "Python 3.8 classifier required"
        assert any("Operating System" in c for c in classifiers), "OS classifier required"
        assert any(
            "Topic :: Software Development" in c for c in classifiers
        ), "Topic classifier required"


class TestPackageStructure:
    """Test package structure and compatibility."""

    def test_version_accessible(self):
        """Test that version is accessible from the package."""
        # Import the package
        import pacc

        assert hasattr(pacc, "__version__"), "Package must have __version__ attribute"
        assert isinstance(pacc.__version__, str), "__version__ must be a string"
        assert pacc.__version__, "__version__ must not be empty"

        # Version should follow semantic versioning
        import re

        version_pattern = r"^\d+\.\d+\.\d+(?:[-+].+)?$"
        assert re.match(
            version_pattern, pacc.__version__
        ), f"Version {pacc.__version__} must follow semantic versioning"

    def test_init_files_present(self):
        """Test that all necessary __init__.py files are present."""
        required_init_files = [
            "pacc/__init__.py",
            "pacc/core/__init__.py",
            "pacc/ui/__init__.py",
            "pacc/validation/__init__.py",
            "pacc/validators/__init__.py",
            "pacc/selection/__init__.py",
            "pacc/packaging/__init__.py",
            "pacc/recovery/__init__.py",
            "pacc/performance/__init__.py",
            "pacc/errors/__init__.py",
            "pacc/sources/__init__.py",
        ]

        for init_file in required_init_files:
            init_path = PROJECT_ROOT / init_file
            assert init_path.exists(), f"{init_file} must exist for proper package structure"

    def test_entry_point_exists(self):
        """Test that the CLI entry point function exists and is callable."""
        from pacc.cli import main

        assert callable(main), "main function must be callable"

        # Check function signature
        import inspect

        sig = inspect.signature(main)
        assert len(sig.parameters) == 0, "main function should take no parameters"

        # Check return type annotation
        return_annotation = sig.return_annotation
        assert (
            return_annotation == int or return_annotation == inspect._empty
        ), "main function should return int or have no return annotation"


class TestPackageBuild:
    """Test that the package can be built successfully."""

    @pytest.mark.slow
    def test_package_builds_successfully(self):
        """Test that the package can be built using build tool."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        # Create a temporary directory for the build
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to build the package
            result = subprocess.run(
                [sys.executable, "-m", "build", "--outdir", tmpdir],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                # If build module not available, skip
                if "No module named build" in result.stderr:
                    pytest.skip("build module not available")

                pytest.fail(f"Package build failed: {result.stderr}")

            # Check that wheel and sdist were created
            tmpdir_path = Path(tmpdir)
            wheels = list(tmpdir_path.glob("*.whl"))
            sdists = list(tmpdir_path.glob("*.tar.gz"))

            assert len(wheels) == 1, "Exactly one wheel should be created"
            assert len(sdists) == 1, "Exactly one source distribution should be created"

            # Verify wheel name format
            wheel_name = wheels[0].name
            assert wheel_name.startswith("pacc-"), "Wheel name should start with 'pacc-'"
            assert "-py3-" in wheel_name, "Wheel should be pure Python 3"

    @pytest.mark.slow
    def test_package_installable_editable(self):
        """Test that the package can be installed in editable mode."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        # Create a temporary virtual environment
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_path = Path(tmpdir) / "venv"

            # Create virtual environment
            result = subprocess.run(
                [sys.executable, "-m", "venv", str(venv_path)],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                pytest.skip(f"Could not create virtual environment: {result.stderr}")

            # Get the python executable in the venv
            if sys.platform == "win32":
                venv_python = venv_path / "Scripts" / "python.exe"
            else:
                venv_python = venv_path / "bin" / "python"

            # Install package in editable mode
            result = subprocess.run(
                [str(venv_python), "-m", "pip", "install", "-e", str(PROJECT_ROOT)],
                capture_output=True,
                text=True,
                check=False,
            )

            assert result.returncode == 0, f"Editable install failed: {result.stderr}"

            # Test that pacc command is available
            if sys.platform == "win32":
                pacc_cmd = venv_path / "Scripts" / "pacc"
            else:
                pacc_cmd = venv_path / "bin" / "pacc"

            assert pacc_cmd.exists(), "pacc command should be installed"

            # Test that pacc command runs
            result = subprocess.run(
                [str(pacc_cmd), "--version"], capture_output=True, text=True, check=False
            )

            assert result.returncode == 0, f"pacc command failed: {result.stderr}"
            assert "1.0.0" in result.stdout, "Version should be displayed"


class TestDevelopmentWorkflow:
    """Test development and testing workflow configuration."""

    def test_development_dependencies_complete(self):
        """Test that all development dependencies are specified."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("No TOML parser available")

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        dev_deps = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])

        # Essential development tools
        required_tools = {
            "pytest": "Testing framework",
            "pytest-cov": "Coverage reporting",
            "pytest-asyncio": "Async test support",
            "mypy": "Type checking",
            "ruff": "Linting and formatting",
            "build": "Package building",
            "twine": "PyPI upload",
        }

        for tool, description in required_tools.items():
            assert any(
                tool in dep for dep in dev_deps
            ), f"{tool} ({description}) should be in dev dependencies"

    def test_tool_configurations(self):
        """Test that tool configurations are present in pyproject.toml."""
        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        if not pyproject_path.exists():
            pytest.skip("pyproject.toml not found")

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                pytest.skip("No TOML parser available")

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        tool = data.get("tool", {})

        # Ruff configuration
        assert "ruff" in tool, "Ruff configuration should be present"

        # Mypy configuration
        assert "mypy" in tool, "Mypy configuration should be present"

        # Coverage configuration
        assert "coverage" in tool, "Coverage configuration should be present"
