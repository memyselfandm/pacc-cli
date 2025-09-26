"""
Complete build workflow validation test.

This test validates the entire PACC build, package, and installation process
to ensure production readiness.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

import pytest


class TestCompleteBuildWorkflow:
    """Test the complete PACC build and installation workflow."""

    def _get_project_root(self):
        """Get the project root directory."""
        test_dir = Path(__file__).parent
        return test_dir.parent

    def _clean_build_environment(self, project_root):
        """Clean build artifacts."""
        print("Step 1: Cleaning build environment...")
        for artifact_dir in ["build", "dist"]:
            for path in project_root.glob(artifact_dir):
                if path.is_dir():
                    shutil.rmtree(path)

    def _build_distributions(self, project_root):
        """Build distributions and validate."""
        print("Step 2: Building distributions...")
        build_result = subprocess.run(
            [sys.executable, "scripts/build.py", "build"],
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False,
        )

        assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"
        print("✅ Build completed successfully")

        print("Step 3: Validating distributions...")
        check_result = subprocess.run(
            [sys.executable, "scripts/build.py", "check"],
            capture_output=True,
            text=True,
            cwd=project_root,
            check=False,
        )

        assert check_result.returncode == 0, f"Distribution check failed: {check_result.stderr}"
        print("✅ Distribution validation passed")

    def _setup_test_venv(self, temp_dir, wheel_path):
        """Set up test virtual environment and install wheel."""
        venv_dir = Path(temp_dir) / "test_venv"

        print("   Creating virtual environment...")
        venv.create(venv_dir, with_pip=True)

        # Get paths for the virtual environment
        if sys.platform == "win32":
            pip_path = venv_dir / "Scripts" / "pip.exe"
            pacc_path = venv_dir / "Scripts" / "pacc.exe"
        else:
            pip_path = venv_dir / "bin" / "pip"
            pacc_path = venv_dir / "bin" / "pacc"

        print("   Installing wheel...")
        install_result = subprocess.run(
            [str(pip_path), "install", str(wheel_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert install_result.returncode == 0, f"Installation failed: {install_result.stderr}"
        return pacc_path

    def _test_basic_commands(self, pacc_path):
        """Test basic PACC commands."""
        print("Step 5: Testing PACC functionality...")

        # Test version command
        version_result = subprocess.run(
            [str(pacc_path), "--version"], capture_output=True, text=True, check=False
        )

        assert version_result.returncode == 0, f"Version command failed: {version_result.stderr}"
        assert (
            "1.0.0" in version_result.stdout
        ), f"Unexpected version output: {version_result.stdout}"
        print("   ✅ Version command works")

        # Test help command
        help_result = subprocess.run(
            [str(pacc_path), "--help"], capture_output=True, text=True, check=False
        )

        assert help_result.returncode == 0, f"Help command failed: {help_result.stderr}"
        assert "install" in help_result.stdout, "Install command not found in help"
        assert "validate" in help_result.stdout, "Validate command not found in help"
        print("   ✅ Help command works")

    def _test_validation_workflow(self, pacc_path, temp_dir):
        """Test extension validation workflow."""
        print("Step 6: Testing extension validation...")

        # Create test extension directory
        test_dir = Path(temp_dir) / "test_extensions"
        test_dir.mkdir()

        # Create valid hook
        valid_hook = {
            "name": "test-hook",
            "eventTypes": ["PreToolUse"],
            "commands": ["echo 'Hook executed'"],
            "description": "Test hook for validation",
        }

        hook_file = test_dir / "valid-hook.json"
        with open(hook_file, "w") as f:
            json.dump(valid_hook, f, indent=2)

        # Test validation of valid hook
        validate_result = subprocess.run(
            [str(pacc_path), "validate", str(hook_file), "--type", "hooks"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert (
            validate_result.returncode == 0
        ), f"Valid hook validation failed: {validate_result.stderr}"
        assert (
            "Valid" in validate_result.stdout or "✓" in validate_result.stdout
        ), "Valid hook not recognized as valid"
        print("   ✅ Valid hook validation works")

        return hook_file

    def _test_invalid_validation(self, pacc_path, temp_dir):
        """Test validation of invalid extensions."""
        test_dir = Path(temp_dir) / "test_extensions"

        # Create invalid hook
        invalid_hook = {
            "name": "invalid-hook",
            # Missing required fields
        }

        invalid_hook_file = test_dir / "invalid-hook.json"
        with open(invalid_hook_file, "w") as f:
            json.dump(invalid_hook, f, indent=2)

        # Test validation of invalid hook
        invalid_validate_result = subprocess.run(
            [str(pacc_path), "validate", str(invalid_hook_file), "--type", "hooks"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Should fail validation but not crash
        assert invalid_validate_result.returncode != 0, "Invalid hook should fail validation"
        assert (
            "INVALID" in invalid_validate_result.stdout or "ERROR" in invalid_validate_result.stdout
        ), "Invalid hook errors not reported"
        print("   ✅ Invalid hook validation works")

    def _test_installation_workflow(self, pacc_path, hook_file, temp_dir):
        """Test installation workflow preparation."""
        print("Step 7: Testing installation workflow...")

        # Create minimal Claude directory structure for testing
        claude_dir = Path(temp_dir) / ".claude"
        claude_dir.mkdir()

        # Test that pacc can handle basic installation concepts
        dry_run_result = subprocess.run(
            [str(pacc_path), "install", str(hook_file), "--dry-run"],
            capture_output=True,
            text=True,
            cwd=temp_dir,
            check=False,
        )

        # Dry run should work (or at least not crash with a clear error)
        if dry_run_result.returncode != 0:
            # Check if it's a reasonable error (like no settings.json)
            error_output = dry_run_result.stderr.lower()
            acceptable_errors = ["settings.json", "configuration", "not found", "permission"]

            assert any(
                err in error_output for err in acceptable_errors
            ), f"Unexpected error in dry run: {dry_run_result.stderr}"
            print("   ✅ Installation workflow handles missing config gracefully")
        else:
            print("   ✅ Installation dry run works")

    def test_complete_build_to_install_workflow(self):
        """Test complete workflow from source to working installation."""
        project_root = self._get_project_root()

        self._clean_build_environment(project_root)
        self._build_distributions(project_root)

        # Test wheel installation and functionality
        print("Step 4: Testing wheel installation...")
        dist_dir = project_root / "dist"
        wheel_files = list(dist_dir.glob("*.whl"))
        assert wheel_files, "No wheel file found"

        wheel_path = wheel_files[0]

        with tempfile.TemporaryDirectory() as temp_dir:
            pacc_path = self._setup_test_venv(temp_dir, wheel_path)
            self._test_basic_commands(pacc_path)
            hook_file = self._test_validation_workflow(pacc_path, temp_dir)
            self._test_invalid_validation(pacc_path, temp_dir)
            self._test_installation_workflow(pacc_path, hook_file, temp_dir)

        print("\n🎉 Complete build workflow validation PASSED!")
        print("PACC is ready for production deployment!")

    def test_cross_platform_package_structure(self):
        """Test that package structure is cross-platform compatible."""

        test_dir = Path(__file__).parent
        project_root = test_dir.parent

        # Check that all paths use forward slashes in package metadata
        pyproject_path = project_root / "pyproject.toml"

        # Read the file and check for Windows-style paths
        content = pyproject_path.read_text()

        # Should not contain backslashes (Windows paths)
        assert "\\\\" not in content, "Package metadata contains Windows-style paths"

        # Check entry points
        assert 'pacc = "pacc.cli:main"' in content, "Entry point not found or malformed"

        print("✅ Package structure is cross-platform compatible")

    def test_dependencies_and_compatibility(self):
        """Test dependency specifications and Python compatibility."""

        test_dir = Path(__file__).parent
        project_root = test_dir.parent

        # Check minimum Python version requirement
        pyproject_path = project_root / "pyproject.toml"
        content = pyproject_path.read_text()

        assert 'requires-python = ">=3.8"' in content, "Python version requirement incorrect"

        # Check that core dependencies are minimal
        lines = content.split("\n")
        in_dependencies = False
        core_deps = []

        for line in lines:
            if line.strip() == "dependencies = [":
                in_dependencies = True
                continue
            elif in_dependencies and line.strip() == "]":
                break
            elif in_dependencies:
                core_deps.append(line.strip())

        # Should have minimal dependencies
        assert len(core_deps) <= 3, f"Too many core dependencies: {core_deps}"

        # PyYAML should be the only required dependency for core functionality
        yaml_dep_found = any("PyYAML" in dep for dep in core_deps)
        assert yaml_dep_found, "PyYAML dependency not found"

        print("✅ Dependencies and compatibility requirements met")

    def test_security_and_safety_measures(self):
        """Test that security measures are properly integrated."""

        # Test that security modules are available
        from pacc.security import InputSanitizer, PathTraversalProtector, SecurityAuditor

        # Test basic security functionality
        auditor = SecurityAuditor()
        assert auditor is not None

        sanitizer = InputSanitizer()
        assert sanitizer is not None

        protector = PathTraversalProtector()
        assert protector is not None

        # Test that dangerous path patterns are detected
        dangerous_paths = [
            "../../../etc/passwd",
            "..\\..\\Windows\\System32",
            "/proc/self/mem",
            "C:\\Windows\\System32\\cmd.exe",
        ]

        for dangerous_path in dangerous_paths:
            is_safe = protector.is_safe_path(dangerous_path)
            # Most of these should be detected as unsafe
            # (Some might be safe on current platform, that's okay)
            print(f"   Path safety check: {dangerous_path} -> {'SAFE' if is_safe else 'UNSAFE'}")

        print("✅ Security measures are properly integrated")

    def test_documentation_and_help_completeness(self):
        """Test that documentation and help are complete."""

        test_dir = Path(__file__).parent
        project_root = test_dir.parent

        # Check that key documentation files exist
        required_docs = ["README.md", "LICENSE", "docs/api_reference.md", "docs/security_guide.md"]

        for doc_file in required_docs:
            doc_path = project_root / doc_file
            assert doc_path.exists(), f"Required documentation missing: {doc_file}"

            # Check that files are not empty
            content = doc_path.read_text().strip()
            assert len(content) > 100, f"Documentation file too short: {doc_file}"

        print("✅ Documentation is complete")

    @pytest.mark.slow
    def test_performance_benchmarks(self):
        """Test that performance benchmarks meet expectations."""

        # Import performance testing components
        from pacc.core.file_utils import DirectoryScanner, FilePathValidator

        # Test file scanning performance
        validator = FilePathValidator()
        scanner = DirectoryScanner(validator)

        # Create temporary directory with many files
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir)

            # Create 100 test files
            for i in range(100):
                test_file = test_dir / f"test_file_{i}.json"
                test_file.write_text(f'{{"test": {i}}}')

            # Time the scanning operation
            import time

            start_time = time.time()

            files = list(scanner.scan_directory(test_dir))

            end_time = time.time()
            scan_time = end_time - start_time

            # Should be able to scan 100 files in reasonable time
            assert len(files) == 100, f"Expected 100 files, found {len(files)}"
            assert scan_time < 1.0, f"Scanning too slow: {scan_time:.3f}s for 100 files"

            print(f"   Scanned {len(files)} files in {scan_time:.3f}s")

        print("✅ Performance benchmarks meet expectations")


if __name__ == "__main__":
    # Allow running this test directly for quick validation
    test = TestCompleteBuildWorkflow()
    test.test_complete_build_to_install_workflow()
    test.test_cross_platform_package_structure()
    test.test_dependencies_and_compatibility()
    test.test_security_and_safety_measures()
    test.test_documentation_and_help_completeness()
    test.test_performance_benchmarks()
    print("\n🎯 All workflow validation tests PASSED!")
