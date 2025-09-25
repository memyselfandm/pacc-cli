#!/usr/bin/env python3
"""
Publishing automation script for PACC.

This script handles the complete publishing workflow:
- Pre-publish validation
- Version management
- Building distributions
- Publishing to Test PyPI and PyPI
- Post-publish verification
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Try to import tomllib (Python 3.11+) or tomli as fallback
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("Error: tomli/tomllib not available. Install with: pip install tomli")
        sys.exit(1)


class PublishError(Exception):
    """Custom exception for publishing errors."""

    pass


def parse_version(version: str) -> Tuple[int, int, int, Optional[str]]:
    """Parse semantic version string."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.*?))?$", version)
    if not match:
        raise PublishError(f"Invalid version format: {version}")

    major, minor, patch = map(int, match.groups()[:3])
    prerelease = match.group(4)

    return major, minor, patch, prerelease


def bump_version(current: str, bump_type: str) -> str:
    """Bump version according to type (major, minor, patch)."""
    major, minor, patch, prerelease = parse_version(current)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        if prerelease:
            # Remove prerelease suffix
            return f"{major}.{minor}.{patch}"
        else:
            return f"{major}.{minor}.{patch + 1}"
    else:
        raise PublishError(f"Invalid bump type: {bump_type}")


class PACCPublisher:
    """Handles the PACC publishing workflow."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.dist_dir = project_root / "dist"
        self.pyproject_path = project_root / "pyproject.toml"
        self.init_path = project_root / "pacc" / "__init__.py"
        self.changelog_path = project_root / "CHANGELOG.md"

    def validate_environment(self) -> bool:
        """Validate that all required tools are available."""
        print("🔍 Validating environment...")

        required_tools = {
            "git": ["git", "--version"],
            "python": [sys.executable, "--version"],
            "pip": [sys.executable, "-m", "pip", "--version"],
            "twine": [sys.executable, "-m", "twine", "--version"],
            "build": [sys.executable, "-m", "build", "--version"],
        }

        all_good = True
        for tool, command in required_tools.items():
            try:
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    print(f"✓ {tool}: {result.stdout.strip()}")
                else:
                    print(f"✗ {tool}: Not found or error")
                    all_good = False
            except Exception as e:
                print(f"✗ {tool}: {e}")
                all_good = False

        # Check git status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
            check=False,
        )

        if result.stdout.strip():
            print("⚠️  Warning: Uncommitted changes detected")
            print("   Consider committing changes before publishing")

        # Check branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=self.project_root,
            check=False,
        )

        current_branch = result.stdout.strip()
        if current_branch not in ["main", "master"]:
            print(f"⚠️  Warning: Not on main branch (current: {current_branch})")

        return all_good

    def check_version(self) -> str:
        """Check and return current version."""
        # Read from pyproject.toml
        with open(self.pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)

        pyproject_version = pyproject["project"]["version"]

        # Read from __init__.py
        init_version = None
        with open(self.init_path) as f:
            for line in f:
                if line.startswith("__version__"):
                    init_version = line.split("=")[1].strip().strip("\"'")
                    break

        if init_version != pyproject_version:
            raise PublishError(
                f"Version mismatch: pyproject.toml has {pyproject_version}, "
                f"but __init__.py has {init_version}"
            )

        print(f"📌 Current version: {pyproject_version}")
        return pyproject_version

    def update_version(self, new_version: str):
        """Update version in all necessary files."""
        print(f"📝 Updating version to {new_version}...")

        # Update pyproject.toml
        with open(self.pyproject_path) as f:
            content = f.read()

        content = re.sub(r'version = "[^"]+"', f'version = "{new_version}"', content)

        with open(self.pyproject_path, "w") as f:
            f.write(content)

        # Update __init__.py
        with open(self.init_path) as f:
            content = f.read()

        content = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{new_version}"', content)

        with open(self.init_path, "w") as f:
            f.write(content)

        print(f"✓ Updated version to {new_version}")

    def run_tests(self) -> bool:
        """Run test suite."""
        print("🧪 Running tests...")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-v"], cwd=self.project_root, check=False
        )

        if result.returncode != 0:
            raise PublishError("Tests failed! Fix issues before publishing.")

        print("✓ All tests passed")
        return True

    def build_distributions(self):
        """Build source and wheel distributions."""
        print("🏗️  Building distributions...")

        # Clean previous builds
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)

        # Build
        result = subprocess.run(
            [sys.executable, "-m", "build"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise PublishError(f"Build failed: {result.stderr}")

        # List built files
        dist_files = list(self.dist_dir.glob("*"))
        print("✓ Built distributions:")
        for file in dist_files:
            size_kb = file.stat().st_size / 1024
            print(f"  - {file.name} ({size_kb:.1f} KB)")

    def validate_distributions(self) -> bool:
        """Validate built distributions with twine."""
        print("🔍 Validating distributions...")

        result = subprocess.run(
            [sys.executable, "-m", "twine", "check", "dist/*"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise PublishError(f"Distribution validation failed: {result.stderr}")

        print("✓ Distributions are valid")
        return True

    def test_local_installation(self):
        """Test installation in a temporary environment."""
        print("🧪 Testing local installation...")

        with tempfile.TemporaryDirectory() as temp_dir:
            venv_path = Path(temp_dir) / "test_venv"

            # Create virtual environment
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

            # Get pip path
            if sys.platform == "win32":
                pip_path = venv_path / "Scripts" / "pip"
                python_path = venv_path / "Scripts" / "python"
            else:
                pip_path = venv_path / "bin" / "pip"
                python_path = venv_path / "bin" / "python"

            # Install wheel
            wheel_file = list(self.dist_dir.glob("*.whl"))[0]
            result = subprocess.run(
                [str(pip_path), "install", str(wheel_file)],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise PublishError(f"Installation failed: {result.stderr}")

            # Test import
            result = subprocess.run(
                [str(python_path), "-c", "import pacc; print(pacc.__version__)"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise PublishError(f"Import test failed: {result.stderr}")

            version = result.stdout.strip()
            print(f"✓ Local installation test passed (version: {version})")

    def publish_to_test_pypi(self, dry_run: bool = False):
        """Publish to Test PyPI."""
        print("📤 Publishing to Test PyPI...")

        if dry_run:
            print("  (DRY RUN - not actually uploading)")
            return

        result = subprocess.run(
            [sys.executable, "-m", "twine", "upload", "--repository", "testpypi", "dist/*"],
            cwd=self.project_root,
            check=False,
        )

        if result.returncode != 0:
            raise PublishError("Failed to upload to Test PyPI")

        print("✓ Published to Test PyPI")
        print("  View at: https://test.pypi.org/project/pacc/")

    def publish_to_pypi(self, dry_run: bool = False):
        """Publish to production PyPI."""
        print("📤 Publishing to PyPI...")

        if dry_run:
            print("  (DRY RUN - not actually uploading)")
            return

        # Confirm
        response = input("⚠️  Publish to production PyPI? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            return

        result = subprocess.run(
            [sys.executable, "-m", "twine", "upload", "dist/*"], cwd=self.project_root, check=False
        )

        if result.returncode != 0:
            raise PublishError("Failed to upload to PyPI")

        print("✓ Published to PyPI")
        print("  View at: https://pypi.org/project/pacc/")

    def verify_publication(self, version: str, test_pypi: bool = False):
        """Verify package is installable from PyPI."""
        print(f"🔍 Verifying publication of version {version}...")

        index_url = "https://test.pypi.org/simple/" if test_pypi else None

        with tempfile.TemporaryDirectory() as temp_dir:
            venv_path = Path(temp_dir) / "verify_venv"

            # Create virtual environment
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)

            # Get pip path
            if sys.platform == "win32":
                pip_path = venv_path / "Scripts" / "pip"
                python_path = venv_path / "Scripts" / "python"
                pacc_path = venv_path / "Scripts" / "pacc"
            else:
                pip_path = venv_path / "bin" / "pip"
                python_path = venv_path / "bin" / "python"
                pacc_path = venv_path / "bin" / "pacc"

            # Install from PyPI
            cmd = [str(pip_path), "install"]
            if index_url:
                cmd.extend(["--index-url", index_url])
                cmd.extend(["--extra-index-url", "https://pypi.org/simple/"])
            cmd.append(f"pacc=={version}")

            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode != 0:
                print(f"❌ Installation failed: {result.stderr}")
                return False

            # Test import
            result = subprocess.run(
                [str(python_path), "-c", "import pacc; print(pacc.__version__)"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                print(f"❌ Import test failed: {result.stderr}")
                return False

            installed_version = result.stdout.strip()
            if installed_version != version:
                print(f"❌ Version mismatch: expected {version}, got {installed_version}")
                return False

            # Test CLI
            result = subprocess.run(
                [str(pacc_path), "--version"], capture_output=True, text=True, check=False
            )

            if result.returncode != 0:
                print(f"❌ CLI test failed: {result.stderr}")
                return False

            print("✓ Publication verified successfully")
            return True

    def create_git_tag(self, version: str):
        """Create and push git tag."""
        print(f"🏷️  Creating git tag v{version}...")

        # Create tag
        result = subprocess.run(
            ["git", "tag", "-a", f"v{version}", "-m", f"Release version {version}"],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise PublishError(f"Failed to create tag: {result.stderr}")

        print(f"✓ Created tag v{version}")

        # Optionally push tag
        response = input("Push tag to remote? [y/N]: ")
        if response.lower() == "y":
            result = subprocess.run(
                ["git", "push", "origin", f"v{version}"], cwd=self.project_root, check=False
            )
            if result.returncode == 0:
                print("✓ Pushed tag to remote")

    def update_changelog(self, version: str):
        """Add placeholder for changelog update."""
        print(f"📝 Updating CHANGELOG for version {version}...")

        if not self.changelog_path.exists():
            print("  ⚠️  No CHANGELOG.md found")
            return

        today = datetime.now().strftime("%Y-%m-%d")

        with open(self.changelog_path) as f:
            content = f.read()

        if f"## [{version}]" in content:
            print(f"  Version {version} already in CHANGELOG")
            return

        # Insert new version section after the header
        lines = content.split("\n")
        insert_index = 0

        for i, line in enumerate(lines):
            if line.startswith("## "):
                insert_index = i
                break

        new_section = f"""
## [{version}] - {today}

### Added
- TODO: Add new features

### Changed
- TODO: Add changes

### Fixed
- TODO: Add fixes
"""

        lines.insert(insert_index, new_section)

        with open(self.changelog_path, "w") as f:
            f.write("\n".join(lines))

        print(f"✓ Added {version} section to CHANGELOG")
        print("  ⚠️  Remember to update with actual changes!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="PACC publishing automation")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Pre-publish validation")

    # Build command
    build_parser = subparsers.add_parser("build", help="Build distributions")

    # Test install command
    test_parser = subparsers.add_parser("test-install", help="Test local installation")

    # Publish command
    publish_parser = subparsers.add_parser("publish", help="Publish to PyPI")
    publish_parser.add_argument("--test", action="store_true", help="Publish to Test PyPI")
    publish_parser.add_argument("--prod", action="store_true", help="Publish to production PyPI")
    publish_parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify publication")
    verify_parser.add_argument("--version", required=True, help="Version to verify")
    verify_parser.add_argument("--test-pypi", action="store_true", help="Verify on Test PyPI")

    # Version bump command
    bump_parser = subparsers.add_parser("bump-version", help="Bump version")
    bump_parser.add_argument("--type", choices=["major", "minor", "patch"], required=True)

    # Release command (full workflow)
    release_parser = subparsers.add_parser("release", help="Full release workflow")
    release_parser.add_argument("--version", help="Specific version to release")
    release_parser.add_argument("--bump", choices=["major", "minor", "patch"])
    release_parser.add_argument("--test-first", action="store_true", help="Test on Test PyPI first")
    release_parser.add_argument("--dry-run", action="store_true", help="Dry run mode")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Find project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    publisher = PACCPublisher(project_root)

    try:
        if args.command == "validate":
            if publisher.validate_environment():
                publisher.check_version()
                print("\n✅ Pre-publish validation passed")
            else:
                print("\n❌ Validation failed")
                sys.exit(1)

        elif args.command == "build":
            publisher.build_distributions()
            publisher.validate_distributions()

        elif args.command == "test-install":
            publisher.test_local_installation()

        elif args.command == "publish":
            if args.test:
                publisher.publish_to_test_pypi(dry_run=args.dry_run)
            elif args.prod:
                publisher.publish_to_pypi(dry_run=args.dry_run)
            else:
                print("Specify --test or --prod")
                sys.exit(1)

        elif args.command == "verify":
            success = publisher.verify_publication(args.version, test_pypi=args.test_pypi)
            if not success:
                sys.exit(1)

        elif args.command == "bump-version":
            current = publisher.check_version()
            new_version = bump_version(current, args.type)
            publisher.update_version(new_version)
            publisher.update_changelog(new_version)
            print(f"\n✅ Bumped version from {current} to {new_version}")
            print("   Remember to commit these changes!")

        elif args.command == "release":
            # Full release workflow
            print("🚀 Starting release workflow...\n")

            # Validate environment
            if not publisher.validate_environment():
                raise PublishError("Environment validation failed")

            # Determine version
            current = publisher.check_version()
            if args.version:
                new_version = args.version
            elif args.bump:
                new_version = bump_version(current, args.bump)
                publisher.update_version(new_version)
                publisher.update_changelog(new_version)
                print(f"📌 Bumped version to {new_version}")
            else:
                new_version = current
                print(f"📌 Using current version {new_version}")

            # Run tests
            if not args.dry_run:
                publisher.run_tests()

            # Build
            publisher.build_distributions()
            publisher.validate_distributions()
            publisher.test_local_installation()

            # Publish to Test PyPI first
            if args.test_first:
                publisher.publish_to_test_pypi(dry_run=args.dry_run)
                if not args.dry_run:
                    print("\n⏸️  Waiting for Test PyPI...")
                    input("Press Enter after verifying Test PyPI installation works...")

            # Publish to production
            publisher.publish_to_pypi(dry_run=args.dry_run)

            # Create git tag
            if not args.dry_run:
                publisher.create_git_tag(new_version)

            # Verify
            if not args.dry_run:
                print("\n⏸️  Waiting for PyPI propagation...")
                input("Press Enter to verify publication...")
                publisher.verify_publication(new_version)

            print(f"\n✅ Release {new_version} complete!")

    except PublishError as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
        sys.exit(1)


if __name__ == "__main__":
    main()
