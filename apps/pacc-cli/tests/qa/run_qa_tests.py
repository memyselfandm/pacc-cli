#!/usr/bin/env python3
"""
Master QA test runner for PACC distribution testing.

This script orchestrates all quality assurance tests to ensure PACC
is ready for distribution across all supported platforms and scenarios.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import QA test modules
from test_cross_platform import CrossPlatformTestSuite
from test_edge_cases import EdgeCaseTester
from test_package_managers import PackageManagerTester
from test_upgrade_uninstall import UpgradeUninstallTester


class QATestRunner:
    """Master QA test runner for comprehensive distribution testing."""

    def __init__(self):
        self.pacc_root = Path(__file__).parent.parent.parent
        self.results_dir = self.pacc_root / "qa_results"
        self.results_dir.mkdir(exist_ok=True)

        self.test_suites = {
            "cross_platform": CrossPlatformTestSuite(),
            "package_managers": PackageManagerTester(),
            "upgrade_uninstall": UpgradeUninstallTester(),
            "edge_cases": EdgeCaseTester(),
        }

    def run_unit_tests(self) -> Dict[str, Any]:
        """Run unit test suite."""
        print("\n" + "=" * 60)
        print("Running Unit Tests")
        print("=" * 60)

        result = {
            "suite": "unit_tests",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "passed": False,
            "details": {},
        }

        try:
            # Run pytest for unit tests
            cmd = [sys.executable, "-m", "pytest", "tests/unit/", "-v", "--tb=short"]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.pacc_root, check=False
            )

            result["return_code"] = proc.returncode
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
            result["passed"] = proc.returncode == 0

            if result["passed"]:
                print("✓ Unit tests passed")
            else:
                print("✗ Unit tests failed")
                print(proc.stdout)
                print(proc.stderr)

        except Exception as e:
            result["error"] = str(e)
            print(f"✗ Error running unit tests: {e}")

        return result

    def run_integration_tests(self) -> Dict[str, Any]:
        """Run integration test suite."""
        print("\n" + "=" * 60)
        print("Running Integration Tests")
        print("=" * 60)

        result = {
            "suite": "integration_tests",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "passed": False,
            "details": {},
        }

        try:
            # Run pytest for integration tests
            cmd = [sys.executable, "-m", "pytest", "tests/integration/", "-v", "--tb=short"]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.pacc_root, check=False
            )

            result["return_code"] = proc.returncode
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
            result["passed"] = proc.returncode == 0

            if result["passed"]:
                print("✓ Integration tests passed")
            else:
                print("✗ Integration tests failed")
                print(proc.stdout)
                print(proc.stderr)

        except Exception as e:
            result["error"] = str(e)
            print(f"✗ Error running integration tests: {e}")

        return result

    def run_e2e_tests(self) -> Dict[str, Any]:
        """Run end-to-end test suite."""
        print("\n" + "=" * 60)
        print("Running End-to-End Tests")
        print("=" * 60)

        result = {
            "suite": "e2e_tests",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "passed": False,
            "details": {},
        }

        try:
            # Run pytest for e2e tests
            cmd = [sys.executable, "-m", "pytest", "tests/e2e/", "-v", "--tb=short"]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.pacc_root, check=False
            )

            result["return_code"] = proc.returncode
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
            result["passed"] = proc.returncode == 0

            if result["passed"]:
                print("✓ End-to-end tests passed")
            else:
                print("✗ End-to-end tests failed")
                print(proc.stdout)
                print(proc.stderr)

        except Exception as e:
            result["error"] = str(e)
            print(f"✗ Error running e2e tests: {e}")

        return result

    def run_performance_tests(self) -> Dict[str, Any]:
        """Run performance test suite."""
        print("\n" + "=" * 60)
        print("Running Performance Tests")
        print("=" * 60)

        result = {
            "suite": "performance_tests",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "passed": False,
            "details": {},
        }

        try:
            # Run pytest for performance tests
            cmd = [sys.executable, "-m", "pytest", "tests/performance/", "-v", "--tb=short"]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.pacc_root, check=False
            )

            result["return_code"] = proc.returncode
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
            result["passed"] = proc.returncode == 0

            if result["passed"]:
                print("✓ Performance tests passed")
            else:
                print("✗ Performance tests failed")
                print(proc.stdout)
                print(proc.stderr)

        except Exception as e:
            result["error"] = str(e)
            print(f"✗ Error running performance tests: {e}")

        return result

    def run_qa_suite(self, suite_name: str) -> Dict[str, Any]:
        """Run a specific QA test suite."""
        if suite_name not in self.test_suites:
            raise ValueError(f"Unknown test suite: {suite_name}")

        print(f"\n{'=' * 60}")
        print(f"Running {suite_name.replace('_', ' ').title()} Tests")
        print("=" * 60)

        suite = self.test_suites[suite_name]

        try:
            results = suite.run_all_tests()

            # Calculate pass rate
            total_tests = 0
            passed_tests = 0

            for _category, test_results in results.get("tests", {}).items():
                if isinstance(test_results, dict) and "tests" in test_results:
                    tests = test_results["tests"]
                    for _test_name, test_result in tests.items():
                        if isinstance(test_result, bool):
                            total_tests += 1
                            if test_result:
                                passed_tests += 1

            results["summary"] = {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "pass_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "suite_passed": passed_tests == total_tests and total_tests > 0,
            }

            if results["summary"]["suite_passed"]:
                print(f"✓ {suite_name} tests passed ({passed_tests}/{total_tests})")
            else:
                print(f"✗ {suite_name} tests failed ({passed_tests}/{total_tests})")

            return results

        except Exception as e:
            print(f"✗ Error running {suite_name} tests: {e}")
            return {
                "suite": suite_name,
                "error": str(e),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            }

    def run_build_tests(self) -> Dict[str, Any]:
        """Test package building."""
        print("\n" + "=" * 60)
        print("Running Build Tests")
        print("=" * 60)

        result = {
            "suite": "build_tests",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "passed": False,
            "details": {},
        }

        try:
            # Clean previous builds
            import shutil

            for path in ["build", "dist", "*.egg-info"]:
                full_path = self.pacc_root / path
                if full_path.exists():
                    if full_path.is_dir():
                        shutil.rmtree(full_path)
                    else:
                        full_path.unlink()

            # Build package
            cmd = [sys.executable, "-m", "build"]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.pacc_root, check=False
            )

            result["build_return_code"] = proc.returncode
            result["build_stdout"] = proc.stdout
            result["build_stderr"] = proc.stderr

            if proc.returncode == 0:
                print("✓ Package build successful")

                # Check that dist files were created
                dist_dir = self.pacc_root / "dist"
                if dist_dir.exists():
                    wheel_files = list(dist_dir.glob("*.whl"))
                    tar_files = list(dist_dir.glob("*.tar.gz"))

                    result["wheel_created"] = len(wheel_files) > 0
                    result["sdist_created"] = len(tar_files) > 0
                    result["passed"] = result["wheel_created"] and result["sdist_created"]

                    if result["passed"]:
                        print("✓ Both wheel and source distribution created")
                    else:
                        print("✗ Missing distribution files")

                else:
                    result["passed"] = False
                    print("✗ No dist directory created")

            else:
                print("✗ Package build failed")
                print(proc.stdout)
                print(proc.stderr)

        except Exception as e:
            result["error"] = str(e)
            print(f"✗ Error during build tests: {e}")

        return result

    def generate_report(self, all_results: Dict[str, Any]) -> str:
        """Generate a comprehensive QA report."""
        report = []
        report.append("# PACC Quality Assurance Report")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Overall summary
        total_suites = len(all_results)
        passed_suites = sum(
            1
            for r in all_results.values()
            if r.get("passed") or r.get("summary", {}).get("suite_passed")
        )

        report.append("## Overall Summary")
        report.append(f"- **Total Test Suites**: {total_suites}")
        report.append(f"- **Passed Suites**: {passed_suites}")
        report.append(f"- **Success Rate**: {passed_suites / total_suites * 100:.1f}%")
        report.append("")

        # Individual suite results
        report.append("## Test Suite Results")
        report.append("")

        for suite_name, results in all_results.items():
            status = (
                "✓ PASS"
                if (results.get("passed") or results.get("summary", {}).get("suite_passed"))
                else "✗ FAIL"
            )
            report.append(f"### {suite_name.replace('_', ' ').title()} {status}")

            # Add summary if available
            if "summary" in results:
                summary = results["summary"]
                report.append(
                    f"- Tests: {summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)}"
                )
                report.append(f"- Pass Rate: {summary.get('pass_rate', 0) * 100:.1f}%")
            elif "return_code" in results:
                report.append(f"- Return Code: {results['return_code']}")

            if "error" in results:
                report.append(f"- Error: {results['error']}")

            report.append("")

        # Recommendations
        report.append("## Recommendations")

        if passed_suites == total_suites:
            report.append("✅ **All tests passed** - Package is ready for release")
        else:
            report.append("❌ **Some tests failed** - Address issues before release:")
            for suite_name, results in all_results.items():
                if not (results.get("passed") or results.get("summary", {}).get("suite_passed")):
                    report.append(f"- Fix issues in {suite_name}")

        report.append("")
        report.append("---")
        report.append("*Report generated by PACC QA Test Runner*")

        return "\n".join(report)

    def run_full_qa(self, suites: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run complete QA test suite."""
        print("\n" + "=" * 80)
        print("PACC COMPREHENSIVE QUALITY ASSURANCE TESTING")
        print("=" * 80)

        start_time = time.time()

        # Default to all suites if none specified
        if suites is None:
            suites = [
                "unit_tests",
                "integration_tests",
                "e2e_tests",
                "performance_tests",
                "cross_platform",
                "package_managers",
                "upgrade_uninstall",
                "edge_cases",
                "build_tests",
            ]

        all_results = {}

        # Run each test suite
        for suite_name in suites:
            try:
                if suite_name == "unit_tests":
                    results = self.run_unit_tests()
                elif suite_name == "integration_tests":
                    results = self.run_integration_tests()
                elif suite_name == "e2e_tests":
                    results = self.run_e2e_tests()
                elif suite_name == "performance_tests":
                    results = self.run_performance_tests()
                elif suite_name == "build_tests":
                    results = self.run_build_tests()
                elif suite_name in self.test_suites:
                    results = self.run_qa_suite(suite_name)
                else:
                    print(f"Warning: Unknown test suite '{suite_name}', skipping")
                    continue

                all_results[suite_name] = results

            except Exception as e:
                print(f"✗ Fatal error in {suite_name}: {e}")
                all_results[suite_name] = {
                    "suite": suite_name,
                    "fatal_error": str(e),
                    "passed": False,
                }

        # Generate and save report
        elapsed_time = time.time() - start_time

        # Save detailed results
        results_file = self.results_dir / f"qa_results_{int(time.time())}.json"
        with open(results_file, "w") as f:
            json.dump(all_results, f, indent=2, default=str)

        # Generate summary report
        report = self.generate_report(all_results)
        report_file = self.results_dir / f"qa_report_{int(time.time())}.md"
        with open(report_file, "w") as f:
            f.write(report)

        # Print final summary
        print("\n" + "=" * 80)
        print("QA TESTING COMPLETE")
        print("=" * 80)
        print(f"Total time: {elapsed_time:.1f} seconds")
        print(f"Results saved to: {results_file}")
        print(f"Report saved to: {report_file}")
        print("")
        print(report)

        return all_results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run PACC quality assurance tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available test suites:
  unit_tests          - Unit test suite
  integration_tests   - Integration test suite
  e2e_tests          - End-to-end test suite
  performance_tests   - Performance benchmarks
  cross_platform     - Cross-platform compatibility
  package_managers   - Package manager compatibility
  upgrade_uninstall  - Upgrade and uninstall procedures
  edge_cases         - Edge case scenarios
  build_tests        - Package building tests

Examples:
  %(prog)s                                    # Run all tests
  %(prog)s --suites cross_platform            # Run only cross-platform tests
  %(prog)s --suites unit_tests build_tests    # Run specific test suites
  %(prog)s --quick                            # Run quick test subset
""",
    )

    parser.add_argument("--suites", nargs="+", help="Specific test suites to run")

    parser.add_argument(
        "--quick", action="store_true", help="Run quick test subset (unit, integration, build)"
    )

    parser.add_argument(
        "--cross-platform", action="store_true", help="Run only cross-platform tests"
    )

    parser.add_argument(
        "--package-managers", action="store_true", help="Run only package manager tests"
    )

    parser.add_argument("--edge-cases", action="store_true", help="Run only edge case tests")

    parser.add_argument("--upgrade", action="store_true", help="Run only upgrade/uninstall tests")

    args = parser.parse_args()

    runner = QATestRunner()

    # Determine which suites to run
    suites = None
    if args.quick:
        suites = ["unit_tests", "integration_tests", "build_tests"]
    elif args.cross_platform:
        suites = ["cross_platform"]
    elif args.package_managers:
        suites = ["package_managers"]
    elif args.edge_cases:
        suites = ["edge_cases"]
    elif args.upgrade:
        suites = ["upgrade_uninstall"]
    elif args.suites:
        suites = args.suites

    try:
        results = runner.run_full_qa(suites)

        # Exit with appropriate code
        all_passed = all(
            r.get("passed") or r.get("summary", {}).get("suite_passed", False)
            for r in results.values()
        )

        sys.exit(0 if all_passed else 1)

    except KeyboardInterrupt:
        print("\nQA testing interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Fatal error during QA testing: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
