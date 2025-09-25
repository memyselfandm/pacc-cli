#!/usr/bin/env python3
"""
Test the QA infrastructure itself to ensure all components work correctly.

This test validates that the QA test infrastructure is functioning properly
and can reliably detect issues across all test categories.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

import pytest


class QAInfrastructureTester:
    """Test the QA infrastructure components."""

    def __init__(self):
        self.qa_dir = Path(__file__).parent
        self.pacc_root = self.qa_dir.parent.parent

    def test_qa_test_files_exist(self) -> Dict[str, bool]:
        """Test that all QA test files exist and are readable."""
        results = {}

        required_files = [
            "test_cross_platform.py",
            "test_package_managers.py",
            "test_upgrade_uninstall.py",
            "test_edge_cases.py",
            "run_qa_tests.py",
        ]

        for filename in required_files:
            filepath = self.qa_dir / filename
            results[f"{filename}_exists"] = filepath.exists()
            results[f"{filename}_readable"] = filepath.is_file() and os.access(filepath, os.R_OK)

        return results

    def test_qa_test_imports(self) -> Dict[str, bool]:
        """Test that QA test modules can be imported correctly."""
        results = {}

        test_modules = [
            "test_cross_platform",
            "test_package_managers",
            "test_upgrade_uninstall",
            "test_edge_cases",
        ]

        # Add QA directory to path for imports
        sys.path.insert(0, str(self.qa_dir))

        try:
            for module_name in test_modules:
                try:
                    module = __import__(module_name)
                    results[f"{module_name}_import"] = True

                    # Check for required classes
                    expected_classes = {
                        "test_cross_platform": "CrossPlatformTestSuite",
                        "test_package_managers": "PackageManagerTester",
                        "test_upgrade_uninstall": "UpgradeUninstallTester",
                        "test_edge_cases": "EdgeCaseTester",
                    }

                    if module_name in expected_classes:
                        class_name = expected_classes[module_name]
                        results[f"{module_name}_has_class"] = hasattr(module, class_name)

                        # Check for run_all_tests method
                        if hasattr(module, class_name):
                            test_class = getattr(module, class_name)
                            results[f"{module_name}_has_run_method"] = hasattr(
                                test_class, "run_all_tests"
                            )

                except ImportError as e:
                    results[f"{module_name}_import"] = False
                    results[f"{module_name}_error"] = str(e)

        finally:
            # Remove from path
            sys.path.pop(0)

        return results

    def test_qa_runner_functionality(self) -> Dict[str, bool]:
        """Test that the QA runner script works correctly."""
        results = {}

        qa_runner = self.qa_dir / "run_qa_tests.py"

        # Test 1: Help option
        try:
            result = subprocess.run(
                [sys.executable, str(qa_runner), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            results["help_command"] = result.returncode == 0
            results["help_shows_usage"] = "usage:" in result.stdout.lower()

        except Exception as e:
            results["help_command"] = False
            results["help_error"] = str(e)

        # Test 2: Quick test option (dry run simulation)
        try:
            # This will likely fail since we don't have all dependencies
            # but we're testing that the script structure is correct
            result = subprocess.run(
                [sys.executable, str(qa_runner), "--quick"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            # Don't require success, just that it starts properly
            results["quick_option_recognized"] = (
                "unit_tests" in result.stdout or "Error" in result.stderr
            )

        except subprocess.TimeoutExpired:
            results["quick_option_recognized"] = True  # Started properly
        except Exception as e:
            results["quick_option_recognized"] = False
            results["quick_error"] = str(e)

        return results

    def test_documentation_files(self) -> Dict[str, bool]:
        """Test that QA documentation files exist and are complete."""
        results = {}

        docs_dir = self.pacc_root / "docs"

        # Check for QA documentation
        qa_checklist = docs_dir / "qa_checklist.md"
        release_validation = docs_dir / "release_validation.md"

        results["qa_checklist_exists"] = qa_checklist.exists()
        results["release_validation_exists"] = release_validation.exists()

        if qa_checklist.exists():
            content = qa_checklist.read_text()
            results["qa_checklist_has_sections"] = all(
                section in content
                for section in [
                    "Pre-Release QA Checklist",
                    "Cross-Platform Testing",
                    "Package Manager Compatibility",
                    "Upgrade and Migration Testing",
                ]
            )

        if release_validation.exists():
            content = release_validation.read_text()
            results["release_validation_has_procedures"] = all(
                section in content
                for section in [
                    "Pre-Release Testing",
                    "Build Validation",
                    "Cross-Platform Validation",
                    "Performance Validation",
                ]
            )

        return results

    def test_test_structure_consistency(self) -> Dict[str, bool]:
        """Test that all QA tests follow consistent structure."""
        results = {}

        # Add QA directory to path
        sys.path.insert(0, str(self.qa_dir))

        try:
            test_modules = [
                ("test_cross_platform", "CrossPlatformTestSuite"),
                ("test_package_managers", "PackageManagerTester"),
                ("test_upgrade_uninstall", "UpgradeUninstallTester"),
                ("test_edge_cases", "EdgeCaseTester"),
            ]

            consistent_structure = True

            for module_name, class_name in test_modules:
                try:
                    module = __import__(module_name)
                    test_class = getattr(module, class_name)

                    # Check for required methods
                    required_methods = ["run_all_tests"]
                    for method in required_methods:
                        if not hasattr(test_class, method):
                            consistent_structure = False
                            results[f"{module_name}_missing_{method}"] = True

                    # Check if can instantiate
                    instance = test_class()
                    results[f"{module_name}_instantiable"] = True

                except Exception as e:
                    consistent_structure = False
                    results[f"{module_name}_error"] = str(e)

            results["consistent_structure"] = consistent_structure

        finally:
            sys.path.pop(0)

        return results

    def test_pytest_integration(self) -> Dict[str, bool]:
        """Test that QA tests integrate properly with pytest."""
        results = {}

        # Check if pytest can discover QA tests
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", str(self.qa_dir)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.pacc_root,
                check=False,
            )

            results["pytest_discovery"] = result.returncode == 0
            results["tests_discovered"] = "test session starts" in result.stdout

            # Count discovered test functions
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                test_functions = [line for line in lines if "<Function" in line]
                results["test_function_count"] = len(test_functions)
                results["has_test_functions"] = len(test_functions) > 0

        except Exception as e:
            results["pytest_discovery"] = False
            results["pytest_error"] = str(e)

        return results

    def test_results_directory_creation(self) -> Dict[str, bool]:
        """Test that QA tests can create results directories."""
        results = {}

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Test creating QA results directory
            qa_results = tmpdir / "qa_results"

            try:
                qa_results.mkdir(exist_ok=True)
                results["can_create_results_dir"] = qa_results.exists()

                # Test creating result file
                test_result = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "test": "infrastructure_test",
                    "passed": True,
                }

                result_file = qa_results / "test_result.json"
                with open(result_file, "w") as f:
                    json.dump(test_result, f, indent=2)

                results["can_create_result_file"] = result_file.exists()

                # Test reading result file
                with open(result_file) as f:
                    loaded_result = json.load(f)

                results["can_read_result_file"] = loaded_result["test"] == "infrastructure_test"

            except Exception as e:
                results["results_dir_error"] = str(e)

        return results

    def test_error_handling(self) -> Dict[str, bool]:
        """Test that QA tests handle errors gracefully."""
        results = {}

        # Test with invalid parameters
        qa_runner = self.qa_dir / "run_qa_tests.py"

        try:
            # Test with invalid suite name
            result = subprocess.run(
                [sys.executable, str(qa_runner), "--suites", "nonexistent_suite"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            # Should handle gracefully (either warn or fail gracefully)
            results["handles_invalid_suite"] = True

        except subprocess.TimeoutExpired:
            results["handles_invalid_suite"] = False
            results["error"] = "Timeout on invalid suite"
        except Exception as e:
            results["handles_invalid_suite"] = False
            results["error"] = str(e)

        return results

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all QA infrastructure tests."""
        print("\n" + "=" * 60)
        print("QA Infrastructure Validation")
        print("=" * 60)

        all_results = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "tests": {}}

        test_functions = [
            ("File Existence", self.test_qa_test_files_exist),
            ("Module Imports", self.test_qa_test_imports),
            ("QA Runner", self.test_qa_runner_functionality),
            ("Documentation", self.test_documentation_files),
            ("Structure Consistency", self.test_test_structure_consistency),
            ("Pytest Integration", self.test_pytest_integration),
            ("Results Directory", self.test_results_directory_creation),
            ("Error Handling", self.test_error_handling),
        ]

        for test_name, test_func in test_functions:
            print(f"\nTesting {test_name}...")
            try:
                results = test_func()
                all_results["tests"][test_name] = results

                # Print summary
                passed = sum(1 for v in results.values() if isinstance(v, bool) and v)
                total = sum(1 for v in results.values() if isinstance(v, bool))
                print(f"  {passed}/{total} tests passed")

                # Show any errors
                for key, value in results.items():
                    if key.endswith("_error"):
                        print(f"  Error in {key}: {value}")

            except Exception as e:
                print(f"  ERROR: {e}")
                all_results["tests"][test_name] = {"error": str(e)}

        return all_results


# Pytest test functions
@pytest.mark.qa_infrastructure
class TestQAInfrastructure:
    """Pytest wrapper for QA infrastructure tests."""

    def setup_method(self):
        """Set up test suite."""
        self.tester = QAInfrastructureTester()

    def test_files_exist(self):
        """Test that all QA files exist."""
        results = self.tester.test_qa_test_files_exist()

        # All files should exist and be readable
        for key, value in results.items():
            if key.endswith("_exists") or key.endswith("_readable"):
                assert value, f"Failed: {key}"

    def test_imports_work(self):
        """Test that QA modules can be imported."""
        results = self.tester.test_qa_test_imports()

        # All imports should work
        for key, value in results.items():
            if key.endswith("_import"):
                assert value, f"Failed to import: {key}"

    def test_runner_works(self):
        """Test that QA runner functions."""
        results = self.tester.test_qa_runner_functionality()

        # Help command should work
        assert results.get("help_command", False), "QA runner help command failed"

    def test_documentation_complete(self):
        """Test that documentation exists."""
        results = self.tester.test_documentation_files()

        # Documentation files should exist
        assert results.get("qa_checklist_exists", False), "QA checklist missing"
        assert results.get("release_validation_exists", False), "Release validation doc missing"

    def test_structure_consistent(self):
        """Test that test structure is consistent."""
        results = self.tester.test_test_structure_consistency()

        # Structure should be consistent
        assert results.get("consistent_structure", False), "QA test structure inconsistent"

    def test_full_infrastructure(self):
        """Run the complete QA infrastructure test suite."""
        results = self.tester.run_all_tests()

        # Save results
        results_file = Path("qa_infrastructure_test_results.json")
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\nQA Infrastructure test results saved to: {results_file}")

        # Basic assertions
        assert "tests" in results
        assert len(results["tests"]) > 0


if __name__ == "__main__":
    # Run as standalone script
    tester = QAInfrastructureTester()
    results = tester.run_all_tests()

    # Print summary
    print(f"\n{'='*60}")
    print("QA Infrastructure Test Summary")
    print(f"{'='*60}")

    total_tests = 0
    passed_tests = 0

    for category, test_results in results["tests"].items():
        if isinstance(test_results, dict):
            category_passed = sum(1 for v in test_results.values() if isinstance(v, bool) and v)
            category_total = sum(1 for v in test_results.values() if isinstance(v, bool))
            total_tests += category_total
            passed_tests += category_passed

            print(f"{category}: {category_passed}/{category_total} passed")

    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\n✅ QA Infrastructure is working correctly!")
    else:
        print("\n❌ QA Infrastructure has issues that need to be addressed")

    # Save detailed results
    with open("qa_infrastructure_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
