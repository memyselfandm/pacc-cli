#!/usr/bin/env python3
"""
Build automation script for PACC.

This script handles:
- Building source and wheel distributions
- Validating build outputs
- Testing local installation
- Managing build artifacts
"""

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

# Try to import tomllib (Python 3.11+) or tomli as fallback
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("Error: tomli/tomllib not available. Install with: pip install tomli")
        sys.exit(1)


class BuildError(Exception):
    """Custom exception for build errors."""

    pass


class PACCBuilder:
    """Build automation for PACC package."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.dist_dir = project_root / "dist"
        self.build_dir = project_root / "build"

    def clean(self):
        """Clean build artifacts."""
        print("🧹 Cleaning build artifacts...")

        # Remove directories
        for dir_path in [self.dist_dir, self.build_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                print(f"   Removed {dir_path}")

        # Remove egg-info
        for egg_info in self.project_root.glob("*.egg-info"):
            shutil.rmtree(egg_info)
            print(f"   Removed {egg_info}")

        # Remove __pycache__
        for cache_dir in self.project_root.rglob("__pycache__"):
            shutil.rmtree(cache_dir)

        print("✅ Clean complete")

    def install_build_deps(self):
        """Install build dependencies."""
        print("📦 Installing build dependencies...")

        deps = ["build", "twine", "wheel", "setuptools>=68.0"]

        for dep in deps:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", dep],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise BuildError(f"Failed to install {dep}: {result.stderr}")

        print("✅ Build dependencies installed")

    def check_requirements(self):
        """Check that all requirements are met for building."""
        print("🔍 Checking build requirements...")

        # Check Python version

        # Check required files
        required_files = [
            "pyproject.toml",
            "setup.py",
            "README.md",
            "LICENSE",
            "MANIFEST.in",
            "pacc/__init__.py",
            "pacc/cli.py",
        ]

        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                raise BuildError(f"Required file missing: {file_path}")

        # Check version in __init__.py matches pyproject.toml
        self._validate_version_consistency()

        print("✅ All requirements met")

    def _validate_version_consistency(self):
        """Ensure version is consistent across files."""
        # Read version from pyproject.toml
        with open(self.project_root / "pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)

        pyproject_version = pyproject["project"]["version"]

        # Read version from __init__.py
        init_file = self.project_root / "pacc" / "__init__.py"
        init_version = None

        with open(init_file) as f:
            for line in f:
                if line.startswith("__version__"):
                    # Extract version string
                    init_version = line.split("=")[1].strip().strip("\"'")
                    break

        if init_version != pyproject_version:
            raise BuildError(
                f"Version mismatch: pyproject.toml has {pyproject_version}, "
                f"but __init__.py has {init_version}"
            )

    def build_sdist(self) -> Path:
        """Build source distribution."""
        print("🏗️  Building source distribution...")

        result = subprocess.run(
            [sys.executable, "-m", "build", "--sdist", str(self.project_root)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise BuildError(f"Failed to build sdist: {result.stderr}")

        # Find the generated file
        sdist_files = list(self.dist_dir.glob("*.tar.gz"))
        if not sdist_files:
            raise BuildError("No sdist file generated")

        sdist_path = sdist_files[0]
        print(f"✅ Built source distribution: {sdist_path.name}")

        # Validate contents
        self._validate_sdist(sdist_path)

        return sdist_path

    def build_wheel(self) -> Path:
        """Build wheel distribution."""
        print("🏗️  Building wheel distribution...")

        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", str(self.project_root)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise BuildError(f"Failed to build wheel: {result.stderr}")

        # Find the generated file
        wheel_files = list(self.dist_dir.glob("*.whl"))
        if not wheel_files:
            raise BuildError("No wheel file generated")

        wheel_path = wheel_files[0]
        print(f"✅ Built wheel distribution: {wheel_path.name}")

        # Validate contents
        self._validate_wheel(wheel_path)

        return wheel_path

    def _validate_sdist(self, sdist_path: Path):
        """Validate source distribution contents."""
        print("   Validating sdist contents...")

        with tarfile.open(sdist_path, "r:gz") as tar:
            members = tar.getnames()

            # Check for required files
            required_patterns = [
                "pyproject.toml",
                "setup.py",
                "README.md",
                "LICENSE",
                "pacc/__init__.py",
                "pacc/cli.py",
                "pacc/py.typed",
            ]

            for pattern in required_patterns:
                if not any(pattern in member for member in members):
                    raise BuildError(f"Required file missing from sdist: {pattern}")

            # Check no test files included
            if any("tests/" in member for member in members):
                raise BuildError("Test files should not be in sdist")

            # Check no cache files
            if any("__pycache__" in member for member in members):
                raise BuildError("Cache files found in sdist")

    def _validate_wheel(self, wheel_path: Path):
        """Validate wheel distribution contents."""
        print("   Validating wheel contents...")

        with zipfile.ZipFile(wheel_path, "r") as zip_ref:
            filenames = zip_ref.namelist()

            # Check for required files
            required_patterns = [
                "pacc/__init__.py",
                "pacc/cli.py",
                "pacc/py.typed",
                ".dist-info/METADATA",
                ".dist-info/WHEEL",
                ".dist-info/entry_points.txt",
            ]

            for pattern in required_patterns:
                if not any(pattern in f for f in filenames):
                    raise BuildError(f"Required file missing from wheel: {pattern}")

            # Validate metadata
            metadata_files = [f for f in filenames if f.endswith("METADATA")]
            if metadata_files:
                with zip_ref.open(metadata_files[0]) as f:
                    metadata = f.read().decode("utf-8")

                    # Check basic metadata fields
                    if "Name: pacc" not in metadata:
                        raise BuildError("Package name not found in metadata")

                    if "Version:" not in metadata:
                        raise BuildError("Version not found in metadata")

    def test_wheel_installation(self, wheel_path: Path) -> bool:
        """Test installing wheel in isolated environment."""
        print("🧪 Testing wheel installation...")

        with tempfile.TemporaryDirectory() as temp_dir:
            venv_dir = Path(temp_dir) / "test_venv"

            # Create virtual environment
            subprocess.run(
                [sys.executable, "-m", "venv", str(venv_dir)], check=True, capture_output=True
            )

            # Get paths for venv
            if sys.platform == "win32":
                pip_path = venv_dir / "Scripts" / "pip"
                python_path = venv_dir / "Scripts" / "python"
                pacc_path = venv_dir / "Scripts" / "pacc"
            else:
                pip_path = venv_dir / "bin" / "pip"
                python_path = venv_dir / "bin" / "python"
                pacc_path = venv_dir / "bin" / "pacc"

            # Install wheel
            print("   Installing wheel in test environment...")
            result = subprocess.run(
                [str(pip_path), "install", str(wheel_path)],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise BuildError(f"Installation failed: {result.stderr}")

            # Test import
            print("   Testing import...")
            result = subprocess.run(
                [str(python_path), "-c", "import pacc; print(pacc.__version__)"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise BuildError(f"Import test failed: {result.stderr}")

            version = result.stdout.strip()
            print(f"   Version: {version}")

            # Test command
            print("   Testing pacc command...")
            result = subprocess.run(
                [str(pacc_path), "--version"], capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                raise BuildError(f"Command test failed: {result.stderr}")

            # Test basic functionality
            print("   Testing basic functionality...")
            result = subprocess.run(
                [str(pacc_path), "--help"], capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                raise BuildError(f"Help command failed: {result.stderr}")

            if "install" not in result.stdout:
                raise BuildError("Install command not found in help output")

            print("✅ Installation test passed")
            return True

    def build_all(self, skip_tests: bool = False):
        """Build both distributions and optionally test."""
        print("🚀 Building PACC distributions...")
        print(f"   Project root: {self.project_root}")
        print()

        # Check requirements
        self.check_requirements()
        print()

        # Build distributions
        sdist_path = self.build_sdist()
        wheel_path = self.build_wheel()
        print()

        # Test installation
        if not skip_tests:
            self.test_wheel_installation(wheel_path)
            print()

        # Summary
        print("📊 Build Summary:")
        print(f"   Source distribution: {sdist_path.name}")
        print(f"   Wheel distribution: {wheel_path.name}")
        print(f"   Size (sdist): {sdist_path.stat().st_size / 1024:.1f} KB")
        print(f"   Size (wheel): {wheel_path.stat().st_size / 1024:.1f} KB")
        print()
        print("✅ Build complete! Distributions are in ./dist/")

    def check_distribution(self, dist_path: Path):
        """Check a distribution file with twine."""
        print(f"🔍 Checking distribution: {dist_path.name}")

        result = subprocess.run(
            [sys.executable, "-m", "twine", "check", str(dist_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            print(f"❌ Distribution check failed: {result.stderr}")
            return False

        print("✅ Distribution check passed")
        return True


def _create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(description="Build automation for PACC package")

    parser.add_argument(
        "action",
        choices=["build", "clean", "test", "check", "install-deps"],
        help="Action to perform",
    )

    parser.add_argument("--skip-tests", action="store_true", help="Skip installation tests")

    parser.add_argument(
        "--dist-type",
        choices=["sdist", "wheel", "both"],
        default="both",
        help="Distribution type to build",
    )

    return parser


def _handle_build_action(builder: PACCBuilder, args) -> None:
    """Handle the build action based on distribution type."""
    if args.dist_type == "both":
        builder.build_all(skip_tests=args.skip_tests)
    elif args.dist_type == "sdist":
        builder.clean()
        builder.check_requirements()
        sdist = builder.build_sdist()
        print(f"✅ Built: {sdist.name}")
    elif args.dist_type == "wheel":
        builder.clean()
        builder.check_requirements()
        wheel = builder.build_wheel()
        print(f"✅ Built: {wheel.name}")


def _handle_test_action(builder: PACCBuilder) -> None:
    """Handle the test action for wheel installation."""
    wheel_files = list(builder.dist_dir.glob("*.whl"))
    if not wheel_files:
        print("❌ No wheel file found. Run 'build' first.")
        sys.exit(1)

    builder.test_wheel_installation(wheel_files[0])


def _handle_check_action(builder: PACCBuilder) -> None:
    """Handle the check action for distribution validation."""
    if not builder.dist_dir.exists():
        print("❌ No dist directory found. Run 'build' first.")
        sys.exit(1)

    dist_files = list(builder.dist_dir.glob("*.tar.gz"))
    dist_files.extend(list(builder.dist_dir.glob("*.whl")))

    if not dist_files:
        print("❌ No distribution files found.")
        sys.exit(1)

    all_passed = True
    for dist_file in dist_files:
        if not builder.check_distribution(dist_file):
            all_passed = False

    if not all_passed:
        sys.exit(1)


def _execute_action(builder: PACCBuilder, args) -> None:
    """Execute the specified action."""
    if args.action == "clean":
        builder.clean()
    elif args.action == "install-deps":
        builder.install_build_deps()
    elif args.action == "build":
        _handle_build_action(builder, args)
    elif args.action == "test":
        _handle_test_action(builder)
    elif args.action == "check":
        _handle_check_action(builder)


def main():
    """Main entry point for build script."""
    parser = _create_argument_parser()
    args = parser.parse_args()

    # Find project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    # Create builder
    builder = PACCBuilder(project_root)

    try:
        _execute_action(builder, args)
    except BuildError as e:
        print(f"❌ Build error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Build interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
