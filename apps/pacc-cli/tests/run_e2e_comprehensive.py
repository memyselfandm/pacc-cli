#!/usr/bin/env python3
"""Comprehensive E2E test runner for PACC plugin system."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil


class E2ETestRunner:
    """Comprehensive E2E test runner with performance monitoring."""

    def __init__(self, test_dir: Path):
        self.test_dir = test_dir
        self.results = {}
        self.start_time = None
        self.end_time = None
        self.system_info = self._get_system_info()

    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for test context."""
        return {
            "platform": os.name,
            "python_version": sys.version,
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / 1024 / 1024 / 1024,
            "pid": os.getpid(),
        }

    def run_test_suite(
        self,
        test_patterns: Optional[List[str]] = None,
        markers: Optional[List[str]] = None,
        parallel: bool = False,
        verbose: bool = False,
        generate_report: bool = True,
    ) -> Dict[str, Any]:
        """Run comprehensive E2E test suite."""
        self.start_time = time.time()

        print("🚀 PACC E2E Test Suite Starting")
        print("=" * 60)
        print(f"Platform: {self.system_info['platform']}")
        print(f"CPU Cores: {self.system_info['cpu_count']}")
        print(f"Memory: {self.system_info['memory_total_gb']:.1f}GB")
        print("=" * 60)

        # Define test suites
        test_suites = self._get_test_suites()

        # Filter test suites based on patterns
        if test_patterns:
            filtered_suites = {}
            for pattern in test_patterns:
                for suite_name, suite_config in test_suites.items():
                    if pattern.lower() in suite_name.lower():
                        filtered_suites[suite_name] = suite_config
            test_suites = filtered_suites

        # Run each test suite
        for suite_name, suite_config in test_suites.items():
            print(f"\n📋 Running Test Suite: {suite_name}")
            print("-" * 40)

            suite_results = self._run_test_suite(
                suite_name, suite_config, markers=markers, parallel=parallel, verbose=verbose
            )

            self.results[suite_name] = suite_results

            # Print suite summary
            self._print_suite_summary(suite_name, suite_results)

        self.end_time = time.time()

        # Generate comprehensive report
        if generate_report:
            self._generate_comprehensive_report()

        return self.results

    def _get_test_suites(self) -> Dict[str, Dict[str, Any]]:
        """Define E2E test suites."""
        return {
            "Plugin Lifecycle": {
                "path": "e2e/test_plugin_lifecycle.py",
                "markers": ["e2e", "plugin_lifecycle"],
                "description": "Complete plugin lifecycle workflows",
                "timeout": 300,  # 5 minutes
                "critical": True,
            },
            "Team Collaboration": {
                "path": "e2e/test_team_collaboration.py",
                "markers": ["e2e", "team_collaboration"],
                "description": "Multi-user team collaboration scenarios",
                "timeout": 600,  # 10 minutes
                "critical": True,
            },
            "CLI Performance": {
                "path": "e2e/test_plugin_cli_performance.py",
                "markers": ["e2e", "cli_performance"],
                "description": "CLI command performance benchmarks",
                "timeout": 300,  # 5 minutes
                "critical": True,
            },
            "Cross-Platform": {
                "path": "e2e/test_cross_platform_enhanced.py",
                "markers": ["e2e", "cross_platform"],
                "description": "Cross-platform compatibility testing",
                "timeout": 240,  # 4 minutes
                "critical": True,
            },
            "Plugin Benchmarks": {
                "path": "performance/test_plugin_benchmarks.py",
                "markers": ["performance", "plugin_benchmarks"],
                "description": "Comprehensive plugin performance benchmarks",
                "timeout": 480,  # 8 minutes
                "critical": False,
            },
            "Stress Tests": {
                "path": "e2e/test_plugin_lifecycle.py::TestPluginStressTests",
                "markers": ["e2e", "stress_test"],
                "description": "Plugin system stress and load testing",
                "timeout": 600,  # 10 minutes
                "critical": False,
            },
            "Memory Efficiency": {
                "path": "performance/test_plugin_benchmarks.py::TestPluginMemoryEfficiency",
                "markers": ["performance", "memory"],
                "description": "Memory usage and efficiency testing",
                "timeout": 240,  # 4 minutes
                "critical": False,
            },
        }

    def _run_test_suite(
        self,
        suite_name: str,
        suite_config: Dict[str, Any],
        markers: Optional[List[str]] = None,
        parallel: bool = False,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Run a specific test suite."""
        suite_start = time.time()

        # Build pytest command
        cmd = ["python", "-m", "pytest"]

        # Add test path
        test_path = self.test_dir / suite_config["path"]
        cmd.append(str(test_path))

        # Add markers
        suite_markers = suite_config.get("markers", [])
        if markers:
            suite_markers.extend(markers)

        if suite_markers:
            marker_expr = " and ".join(suite_markers)
            cmd.extend(["-m", marker_expr])

        # Add verbosity
        if verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")

        # Add parallel execution
        if parallel and psutil.cpu_count() > 1:
            cmd.extend(["-n", "auto"])

        # Add timeout
        if "timeout" in suite_config:
            cmd.extend(["--timeout", str(suite_config["timeout"])])

        # Add performance options
        cmd.extend(
            [
                "--tb=short",
                "--disable-warnings",
                f"--junit-xml={self.test_dir}/results/{suite_name.lower().replace(' ', '_')}_results.xml",
            ]
        )

        # Ensure results directory exists
        results_dir = self.test_dir / "results"
        results_dir.mkdir(exist_ok=True)

        # Run tests
        print(f"Executing: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.test_dir.parent,
                capture_output=True,
                text=True,
                timeout=suite_config.get("timeout", 300),
                check=False,
            )

            suite_end = time.time()
            suite_duration = suite_end - suite_start

            return {
                "duration": suite_duration,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
                "critical": suite_config.get("critical", False),
                "description": suite_config.get("description", ""),
                "timeout": suite_config.get("timeout"),
                "command": cmd,
            }

        except subprocess.TimeoutExpired:
            return {
                "duration": suite_config.get("timeout", 300),
                "return_code": -1,
                "stdout": "",
                "stderr": "Test suite timed out",
                "success": False,
                "critical": suite_config.get("critical", False),
                "description": suite_config.get("description", ""),
                "timeout": suite_config.get("timeout"),
                "timed_out": True,
            }

        except Exception as e:
            return {
                "duration": 0,
                "return_code": -2,
                "stdout": "",
                "stderr": str(e),
                "success": False,
                "critical": suite_config.get("critical", False),
                "description": suite_config.get("description", ""),
                "error": str(e),
            }

    def _print_suite_summary(self, suite_name: str, results: Dict[str, Any]):
        """Print summary for a test suite."""
        status = "✅ PASS" if results["success"] else "❌ FAIL"
        duration = results["duration"]

        print(f"{status} {suite_name} ({duration:.2f}s)")

        if not results["success"]:
            print(f"   Return code: {results['return_code']}")
            if results.get("timed_out"):
                print(f"   ⏰ Timed out after {results.get('timeout', 'N/A')}s")

            # Show error details
            if results["stderr"]:
                print(f"   Error: {results['stderr'][:200]}...")

        # Extract test counts from stdout if available
        stdout = results.get("stdout", "")
        if "passed" in stdout or "failed" in stdout:
            # Try to extract pytest summary
            lines = stdout.split("\n")
            for line in lines:
                if "passed" in line or "failed" in line or "error" in line:
                    if any(word in line for word in ["passed", "failed", "error", "skipped"]):
                        print(f"   📊 {line.strip()}")
                        break

    def _generate_comprehensive_report(self):
        """Generate comprehensive test report."""
        total_duration = self.end_time - self.start_time

        # Calculate summary statistics
        total_suites = len(self.results)
        successful_suites = sum(1 for r in self.results.values() if r["success"])
        failed_suites = total_suites - successful_suites
        critical_failures = sum(
            1 for r in self.results.values() if not r["success"] and r["critical"]
        )

        print("\n" + "=" * 80)
        print("🏁 COMPREHENSIVE E2E TEST REPORT")
        print("=" * 80)

        # Overall summary
        print("📊 SUMMARY")
        print(f"   Total Duration: {total_duration:.2f}s ({total_duration / 60:.1f}m)")
        print(f"   Test Suites: {total_suites}")
        print(f"   Successful: {successful_suites}")
        print(f"   Failed: {failed_suites}")
        print(f"   Critical Failures: {critical_failures}")

        # System performance
        current_memory = psutil.virtual_memory()
        print("\n🖥️  SYSTEM STATE")
        print(f"   CPU Usage: {psutil.cpu_percent()}%")
        print(f"   Memory Usage: {current_memory.percent:.1f}%")
        print(f"   Available Memory: {current_memory.available / 1024 / 1024 / 1024:.1f}GB")

        # Detailed results
        print("\n📋 DETAILED RESULTS")
        for suite_name, results in self.results.items():
            status_icon = "✅" if results["success"] else "❌"
            critical_marker = " [CRITICAL]" if results["critical"] else ""

            print(f"   {status_icon} {suite_name}{critical_marker}")
            print(f"      Duration: {results['duration']:.2f}s")
            print(f"      Description: {results['description']}")

            if not results["success"]:
                print(f"      ❌ Return Code: {results['return_code']}")
                if results.get("timed_out"):
                    print(f"      ⏰ Timed out after {results.get('timeout')}s")
                if results.get("error"):
                    print(f"      🔥 Error: {results['error']}")

        # Performance benchmarks summary
        print("\n⚡ PERFORMANCE HIGHLIGHTS")
        performance_suites = [
            name
            for name, results in self.results.items()
            if "performance" in name.lower() or "benchmark" in name.lower()
        ]

        if performance_suites:
            for suite_name in performance_suites:
                results = self.results[suite_name]
                if results["success"]:
                    print(f"   ✅ {suite_name}: {results['duration']:.2f}s")
                else:
                    print(f"   ❌ {suite_name}: FAILED")

        # Recommendations
        print("\n💡 RECOMMENDATIONS")

        if critical_failures > 0:
            print(f"   🚨 {critical_failures} critical test failures detected")
            print("      → Address critical failures before deployment")

        if failed_suites > 0:
            print(f"   ⚠️  {failed_suites} test suite(s) failed")
            print("      → Review test logs for detailed failure analysis")

        if total_duration > 600:  # 10 minutes
            print(f"   🐌 Test suite took {total_duration / 60:.1f} minutes")
            print("      → Consider parallel execution or test optimization")

        if current_memory.percent > 80:
            print(f"   🧠 High memory usage: {current_memory.percent:.1f}%")
            print("      → Monitor memory efficiency in plugin operations")

        # Final status
        print("\n🎯 FINAL STATUS")
        if critical_failures == 0 and failed_suites == 0:
            print("   🟢 ALL TESTS PASSED - Ready for deployment")
        elif critical_failures == 0:
            print("   🟡 NON-CRITICAL FAILURES - Deployment possible with caution")
        else:
            print("   🔴 CRITICAL FAILURES - Do not deploy")

        print("=" * 80)

        # Save detailed report
        self._save_json_report()

    def _save_json_report(self):
        """Save detailed JSON report."""
        report_data = {
            "summary": {
                "start_time": self.start_time,
                "end_time": self.end_time,
                "total_duration": self.end_time - self.start_time,
                "total_suites": len(self.results),
                "successful_suites": sum(1 for r in self.results.values() if r["success"]),
                "failed_suites": sum(1 for r in self.results.values() if not r["success"]),
                "critical_failures": sum(
                    1 for r in self.results.values() if not r["success"] and r["critical"]
                ),
            },
            "system_info": self.system_info,
            "results": self.results,
        }

        results_dir = self.test_dir / "results"
        results_dir.mkdir(exist_ok=True)

        timestamp = int(time.time())
        report_file = results_dir / f"e2e_comprehensive_report_{timestamp}.json"

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        print(f"\n📄 Detailed report saved: {report_file}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="PACC E2E Comprehensive Test Runner")

    parser.add_argument(
        "--test-dir", type=Path, default=Path(__file__).parent, help="Test directory path"
    )

    parser.add_argument(
        "--patterns",
        nargs="*",
        help="Test suite patterns to run (e.g., 'lifecycle', 'performance')",
    )

    parser.add_argument("--markers", nargs="*", help="Additional pytest markers to include")

    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")

    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    parser.add_argument(
        "--no-report", action="store_true", help="Skip comprehensive report generation"
    )

    args = parser.parse_args()

    # Initialize test runner
    runner = E2ETestRunner(args.test_dir)

    # Run test suite
    results = runner.run_test_suite(
        test_patterns=args.patterns,
        markers=args.markers,
        parallel=args.parallel,
        verbose=args.verbose,
        generate_report=not args.no_report,
    )

    # Determine exit code
    critical_failures = sum(1 for r in results.values() if not r["success"] and r["critical"])
    total_failures = sum(1 for r in results.values() if not r["success"])

    if critical_failures > 0:
        sys.exit(2)  # Critical failure
    elif total_failures > 0:
        sys.exit(1)  # Non-critical failure
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
