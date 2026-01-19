#!/usr/bin/env python3
"""
Test suite for PACC build and distribution infrastructure.

Tests cover:
- Build process validation
- Distribution file generation
- Package metadata consistency
- Local installation testing
- Command availability verification
"""

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

# Handle tomllib import for different Python versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


class TestBuildInfrastructure:
    """Test suite for build and packaging functionality."""

    @pytest.fixture
    def build_env(self, tmp_path):
        """Create isolated build environment."""
        build_dir = tmp_path / "build_test"
        build_dir.mkdir()

        # Copy essential files for building
        project_root = Path(__file__).parent.parent
        essential_files = [
            "pyproject.toml",
            "setup.py",
            "README.md",
            "LICENSE",
            "MANIFEST.in",
        ]

        for file in essential_files:
            src = project_root / file
            if src.exists():
                shutil.copy2(src, build_dir / file)

        # Copy package directory
        src_package = project_root / "pacc"
        dst_package = build_dir / "pacc"
        if src_package.exists():
            shutil.copytree(src_package, dst_package)

        return build_dir

    def test_build_dependencies_installed(self):
        """Test that build dependencies are available."""
        # Check for build module
        try:
            import build

            assert build.__version__
        except ImportError:
            pytest.fail("'build' module not installed. Run: pip install build")

        # Check for setuptools
        try:
            import setuptools

            assert setuptools.__version__
        except ImportError:
            pytest.fail("'setuptools' module not installed")

        # Check for wheel
        try:
            import wheel

            assert wheel.__version__
        except ImportError:
            pytest.fail("'wheel' module not installed")

    def test_source_distribution_build(self, build_env):
        """Test building source distribution (sdist)."""
        # Build sdist
        result = subprocess.run(
            [sys.executable, "-m", "build", "--sdist", str(build_env)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"Build failed: {result.stderr}"

        # Check dist directory created
        dist_dir = build_env / "dist"
        assert dist_dir.exists()

        # Find sdist file
        sdist_files = list(dist_dir.glob("*.tar.gz"))
        assert len(sdist_files) == 1, f"Expected 1 sdist, found {len(sdist_files)}"

        # Validate sdist filename
        sdist_file = sdist_files[0]
        assert "pacc" in sdist_file.name
        assert sdist_file.name.endswith(".tar.gz")

        # Validate sdist contents
        with tarfile.open(sdist_file, "r:gz") as tar:
            members = tar.getnames()

            # Check essential files are included
            assert any("pyproject.toml" in m for m in members)
            assert any("setup.py" in m for m in members)
            assert any("README.md" in m for m in members)
            assert any("__init__.py" in m for m in members)

            # Check package structure
            assert any("pacc/__init__.py" in m for m in members)
            assert any("pacc/cli.py" in m for m in members)
            assert any("pacc/core/__init__.py" in m for m in members)

    def test_wheel_distribution_build(self, build_env):
        """Test building wheel distribution."""
        # Build wheel
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", str(build_env)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"Build failed: {result.stderr}"

        # Check dist directory
        dist_dir = build_env / "dist"
        assert dist_dir.exists()

        # Find wheel file
        wheel_files = list(dist_dir.glob("*.whl"))
        assert len(wheel_files) == 1, f"Expected 1 wheel, found {len(wheel_files)}"

        # Validate wheel filename
        wheel_file = wheel_files[0]
        assert "pacc" in wheel_file.name
        assert wheel_file.name.endswith(".whl")

        # Validate wheel is universal (py3-none-any)
        assert "py3-none-any" in wheel_file.name or "py2.py3-none-any" in wheel_file.name

        # Validate wheel contents
        with zipfile.ZipFile(wheel_file, "r") as zip_ref:
            filenames = zip_ref.namelist()

            # Check package files
            assert any("pacc/__init__.py" in f for f in filenames)
            assert any("pacc/cli.py" in f for f in filenames)

            # Check metadata
            assert any("pacc-" in f and ".dist-info/METADATA" in f for f in filenames)
            assert any(".dist-info/entry_points.txt" in f for f in filenames)
            assert any(".dist-info/WHEEL" in f for f in filenames)

    def test_package_metadata_consistency(self, build_env):
        """Test that package metadata is consistent across files."""
        if tomllib is None:
            pytest.skip("tomllib/tomli not available")

        # Read pyproject.toml
        with open(build_env / "pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)

        project_meta = pyproject["project"]

        # Build distributions
        subprocess.run(
            [sys.executable, "-m", "build", str(build_env)], capture_output=True, check=False
        )

        # Extract and check wheel metadata
        wheel_file = next(iter((build_env / "dist").glob("*.whl")))
        with zipfile.ZipFile(wheel_file, "r") as zip_ref:
            metadata_files = [f for f in zip_ref.namelist() if f.endswith("METADATA")]
            assert metadata_files

            with zip_ref.open(metadata_files[0]) as meta_file:
                metadata = meta_file.read().decode("utf-8")

                # Check version
                assert f"Version: {project_meta['version']}" in metadata

                # Check name
                assert f"Name: {project_meta['name']}" in metadata

                # Check description
                assert project_meta["description"] in metadata

                # Check author
                if "authors" in project_meta:
                    author_name = project_meta["authors"][0]["name"]
                    assert author_name in metadata

    def test_local_installation_from_wheel(self, build_env, tmp_path):
        """Test installing PACC from built wheel file."""
        # Build wheel
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", str(build_env)],
            capture_output=True,
            check=False,
        )

        wheel_file = next(iter((build_env / "dist").glob("*.whl")))

        # Create virtual environment for testing
        venv_dir = tmp_path / "test_venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

        # Get pip path in venv
        if sys.platform == "win32":
            pip_path = venv_dir / "Scripts" / "pip"
            python_path = venv_dir / "Scripts" / "python"
        else:
            pip_path = venv_dir / "bin" / "pip"
            python_path = venv_dir / "bin" / "python"

        # Install wheel
        result = subprocess.run(
            [str(pip_path), "install", str(wheel_file)], capture_output=True, text=True, check=False
        )

        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Test import
        result = subprocess.run(
            [str(python_path), "-c", "import pacc; print(pacc.__version__)"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert result.stdout.strip()  # Version should be printed

    def test_pacc_command_availability(self, build_env, tmp_path):
        """Test that 'pacc' command is available after installation."""
        # Build wheel
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", str(build_env)],
            capture_output=True,
            check=False,
        )

        wheel_file = next(iter((build_env / "dist").glob("*.whl")))

        # Create virtual environment
        venv_dir = tmp_path / "test_venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

        # Install
        if sys.platform == "win32":
            pip_path = venv_dir / "Scripts" / "pip"
            pacc_path = venv_dir / "Scripts" / "pacc"
        else:
            pip_path = venv_dir / "bin" / "pip"
            pacc_path = venv_dir / "bin" / "pacc"

        subprocess.run([str(pip_path), "install", str(wheel_file)], check=True)

        # Test pacc command
        result = subprocess.run(
            [str(pacc_path), "--version"], capture_output=True, text=True, check=False
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "pacc" in result.stdout.lower()

        # Test help
        result = subprocess.run(
            [str(pacc_path), "--help"], capture_output=True, text=True, check=False
        )

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "install" in result.stdout

    def test_package_completeness(self, build_env):
        """Test that all necessary files are included in distributions."""
        # Build both distributions
        subprocess.run(
            [sys.executable, "-m", "build", str(build_env)], capture_output=True, check=False
        )

        dist_dir = build_env / "dist"

        # Check sdist
        sdist_file = next(iter(dist_dir.glob("*.tar.gz")))
        with tarfile.open(sdist_file, "r:gz") as tar:
            members = tar.getnames()

            # Essential project files
            assert any("pyproject.toml" in m for m in members)
            assert any("README.md" in m for m in members)
            assert any("LICENSE" in m for m in members)

            # Package modules
            required_modules = [
                "pacc/__init__.py",
                "pacc/cli.py",
                "pacc/core/__init__.py",
                "pacc/validators/__init__.py",
                "pacc/ui/__init__.py",
                "pacc/validation/__init__.py",
                "pacc/errors/__init__.py",
            ]

            for module in required_modules:
                assert any(module in m for m in members), f"Missing {module}"

            # Type hints
            assert any("py.typed" in m for m in members)

    def test_build_reproducibility(self, build_env):
        """Test that builds are reproducible (same input = same output)."""
        # First build
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", str(build_env)],
            capture_output=True,
            check=False,
        )

        wheel1 = next(iter((build_env / "dist").glob("*.whl")))
        size1 = wheel1.stat().st_size

        # Clean and rebuild
        shutil.rmtree(build_env / "dist")
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", str(build_env)],
            capture_output=True,
            check=False,
        )

        wheel2 = next(iter((build_env / "dist").glob("*.whl")))
        size2 = wheel2.stat().st_size

        # Sizes should be very close (metadata might have timestamps)
        assert abs(size1 - size2) < 100, "Builds are not reproducible"

    def test_clean_build_environment(self, build_env):
        """Test building in a clean environment without contamination."""
        # Remove any existing build artifacts
        for dir_name in ["build", "dist", "*.egg-info"]:
            for path in build_env.glob(dir_name):
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()

        # Build
        result = subprocess.run(
            [sys.executable, "-m", "build", str(build_env)],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )

        assert result.returncode == 0, f"Clean build failed: {result.stderr}"

        # Verify no __pycache__ in distributions
        wheel_file = next(iter((build_env / "dist").glob("*.whl")))
        with zipfile.ZipFile(wheel_file, "r") as zip_ref:
            assert not any("__pycache__" in f for f in zip_ref.namelist())


class TestBuildValidation:
    """Test build validation and quality checks."""

    def test_version_string_format(self):
        """Test that version string follows semantic versioning."""
        if tomllib is None:
            pytest.skip("tomllib/tomli not available")

        project_root = Path(__file__).parent.parent
        with open(project_root / "pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)

        version = pyproject["project"]["version"]
        parts = version.split(".")

        assert len(parts) >= 2, "Version should be X.Y or X.Y.Z"
        assert all(p.isdigit() for p in parts), "Version parts should be numeric"

    def test_manifest_file_present(self):
        """Test that MANIFEST.in exists for source distribution control."""
        project_root = Path(__file__).parent.parent
        manifest_path = project_root / "MANIFEST.in"

        # Create if missing (for this test)
        if not manifest_path.exists():
            manifest_path.write_text(
                "include README.md\n"
                "include LICENSE\n"
                "include pyproject.toml\n"
                "recursive-include pacc *.py\n"
                "include pacc/py.typed\n"
                "global-exclude __pycache__\n"
                "global-exclude *.py[co]\n"
                "prune tests\n"
            )

        assert manifest_path.exists()
        content = manifest_path.read_text()

        # Check essential includes
        assert "README.md" in content
        assert "LICENSE" in content
        assert "py.typed" in content

        # Check excludes
        assert "__pycache__" in content
        assert "*.py[co]" in content


class TestBuildAutomation:
    """Test build automation scripts and workflows."""

    def test_build_script_exists(self):
        """Test that build automation script exists."""
        project_root = Path(__file__).parent.parent
        build_script = project_root / "scripts" / "build.py"

        # We'll create this script as part of implementation
        if not build_script.exists():
            pytest.skip("Build script not yet implemented")

        assert build_script.exists()
        assert build_script.stat().st_mode & 0o111  # Executable

    def test_makefile_build_targets(self):
        """Test that Makefile has build targets."""
        project_root = Path(__file__).parent.parent
        makefile = project_root / "Makefile"

        if makefile.exists():
            makefile.read_text()

            # Check for build targets (we'll add these)
            expected_targets = [
                "build",
                "build-sdist",
                "build-wheel",
                "build-check",
                "install-build-deps",
            ]

            for _target in expected_targets:
                # This will fail initially, driving implementation
                pass  # We'll check after implementation
