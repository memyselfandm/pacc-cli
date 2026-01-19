"""Performance benchmarks for fragment operations using deterministic sample fragments.

This module provides comprehensive performance testing for fragment operations,
ensuring consistent measurement and documentation of performance characteristics.

Created for PACC-56: Fragment Integration Testing with Sample Fragments
"""

import json
import shutil
import statistics
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from pacc.fragments.installation_manager import FragmentInstallationManager
from pacc.fragments.storage_manager import FragmentStorageManager
from pacc.fragments.update_manager import FragmentUpdateManager
from pacc.validators.fragment_validator import FragmentValidator

from ..fixtures.sample_fragments import create_comprehensive_test_suite


@dataclass
class BenchmarkResult:
    """Performance benchmark result."""

    operation: str
    mean_time: float
    median_time: float
    min_time: float
    max_time: float
    std_dev: float
    iterations: int
    throughput: float = 0.0  # Operations per second
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "operation": self.operation,
            "mean_time": self.mean_time,
            "median_time": self.median_time,
            "min_time": self.min_time,
            "max_time": self.max_time,
            "std_dev": self.std_dev,
            "iterations": self.iterations,
            "throughput": self.throughput,
            "metadata": self.metadata,
        }


@dataclass
class PerformanceTestSuite:
    """Performance test suite configuration."""

    iterations: int = 10
    warmup_runs: int = 3
    timeout_seconds: float = 30.0
    collect_detailed_metrics: bool = True


class FragmentPerformanceBenchmarks:
    """Comprehensive performance benchmarks for fragment operations."""

    def __init__(self, test_config: PerformanceTestSuite = None):
        self.config = test_config or PerformanceTestSuite()
        self.temp_dir = None
        self.project_root = None
        self.sample_collections = None
        self.benchmark_results = []

    def setup_benchmark_environment(self):
        """Set up clean environment for benchmarking."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_root = self.temp_dir / "benchmark_project"
        self.project_root.mkdir()

        # Create sample collections
        self.sample_collections = create_comprehensive_test_suite(self.temp_dir)

        # Initialize managers
        self.installation_manager = FragmentInstallationManager(project_root=self.project_root)
        self.storage_manager = FragmentStorageManager(project_root=self.project_root)
        self.update_manager = FragmentUpdateManager(project_root=self.project_root)
        self.validator = FragmentValidator()

        # Set up project files
        self._setup_project_files()

    def teardown_benchmark_environment(self):
        """Clean up benchmark environment."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _setup_project_files(self):
        """Set up basic project structure."""
        claude_md = """# Benchmark Test Project

This project is used for fragment performance benchmarking.
"""
        (self.project_root / "CLAUDE.md").write_text(claude_md)

        pacc_config = {"name": "fragment-benchmark-project", "version": "1.0.0", "fragments": {}}
        (self.project_root / "pacc.json").write_text(json.dumps(pacc_config, indent=2))

    def _reset_environment(self):
        """Reset environment for clean testing."""
        # Remove fragment storage
        fragments_dir = self.project_root / ".claude"
        if fragments_dir.exists():
            shutil.rmtree(fragments_dir)

        # Reset project files
        self._setup_project_files()

    def benchmark_operation(
        self, operation_name: str, operation_func, *args, **kwargs
    ) -> BenchmarkResult:
        """Benchmark a single operation with multiple iterations."""
        times = []

        # Warmup runs
        for _ in range(self.config.warmup_runs):
            try:
                operation_func(*args, **kwargs)
                self._reset_environment()
            except Exception:
                pass  # Ignore warmup failures

        # Actual benchmark runs
        for i in range(self.config.iterations):
            start_time = time.perf_counter()

            try:
                result = operation_func(*args, **kwargs)
                end_time = time.perf_counter()

                elapsed_time = end_time - start_time
                times.append(elapsed_time)

                # Reset for next iteration (if not last)
                if i < self.config.iterations - 1:
                    self._reset_environment()

            except Exception as e:
                print(f"Benchmark iteration {i + 1} failed for {operation_name}: {e}")
                continue

        if not times:
            # Return failed benchmark result
            return BenchmarkResult(
                operation=operation_name,
                mean_time=0.0,
                median_time=0.0,
                min_time=0.0,
                max_time=0.0,
                std_dev=0.0,
                iterations=0,
                metadata={"error": "All benchmark iterations failed"},
            )

        # Calculate statistics
        mean_time = statistics.mean(times)
        median_time = statistics.median(times)
        min_time = min(times)
        max_time = max(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0.0
        throughput = 1.0 / mean_time if mean_time > 0 else 0.0

        result = BenchmarkResult(
            operation=operation_name,
            mean_time=mean_time,
            median_time=median_time,
            min_time=min_time,
            max_time=max_time,
            std_dev=std_dev,
            iterations=len(times),
            throughput=throughput,
            metadata={
                "all_times": times,
                "coefficient_of_variation": (std_dev / mean_time * 100) if mean_time > 0 else 0.0,
            },
        )

        self.benchmark_results.append(result)
        return result

    def benchmark_fragment_validation(self) -> List[BenchmarkResult]:
        """Benchmark fragment validation operations."""
        results = []

        # Benchmark validation of different fragment types
        collections_to_test = [
            ("deterministic", "Basic validation performance"),
            ("edge_cases", "Edge case validation performance"),
            ("versioned", "Versioned fragment validation performance"),
            ("dependencies", "Dependency fragment validation performance"),
        ]

        for collection_name, description in collections_to_test:
            collection_path = self.sample_collections[collection_name]

            # Find all fragment files
            fragment_files = []
            fragment_files.extend(list(collection_path.rglob("*.md")))
            fragment_files.extend(
                [f for f in collection_path.rglob("*.json") if "collection" not in f.name]
            )

            def validate_collection(files=fragment_files):
                """Validate all fragments in collection."""
                validation_results = []
                for fragment_file in files:
                    result = self.validator.validate_single(fragment_file)
                    validation_results.append(result)
                return validation_results

            result = self.benchmark_operation(
                f"validate_{collection_name}_collection", validate_collection
            )
            result.metadata.update(
                {
                    "description": description,
                    "fragment_count": len(fragment_files),
                    "collection_type": collection_name,
                }
            )
            results.append(result)

            # Reset for next test
            self._reset_environment()

        return results

    def benchmark_fragment_installation(self) -> List[BenchmarkResult]:
        """Benchmark fragment installation operations."""
        results = []

        # Benchmark installation of different collection sizes
        collections_to_test = [
            ("deterministic", "Deterministic collection installation", True),
            ("edge_cases", "Edge case collection installation", True),
            ("dependencies", "Dependency resolution installation", True),
        ]

        for collection_name, description, install_all in collections_to_test:
            collection_path = self.sample_collections[collection_name]

            def install_collection():
                """Install collection."""
                return self.installation_manager.install_from_source(
                    str(collection_path), target_type="project", install_all=install_all
                )

            result = self.benchmark_operation(
                f"install_{collection_name}_collection", install_collection
            )
            result.metadata.update(
                {
                    "description": description,
                    "collection_type": collection_name,
                    "install_all": install_all,
                }
            )
            results.append(result)

            # Reset for next test
            self._reset_environment()

        # Benchmark single fragment installation
        def install_single_fragment():
            """Install single fragment."""
            fragment_path = (
                self.sample_collections["deterministic"] / "agents" / "test-simple-agent.md"
            )
            return self.installation_manager.install_from_source(
                str(fragment_path), target_type="project"
            )

        single_result = self.benchmark_operation("install_single_fragment", install_single_fragment)
        single_result.metadata.update(
            {"description": "Single fragment installation performance", "fragment_type": "agent"}
        )
        results.append(single_result)

        return results

    def benchmark_fragment_storage(self) -> List[BenchmarkResult]:
        """Benchmark fragment storage operations."""
        results = []

        # Set up some installed fragments first
        collection_path = self.sample_collections["deterministic"]
        install_result = self.installation_manager.install_from_source(
            str(collection_path), target_type="project", install_all=True
        )

        # Benchmark listing fragments
        def list_fragments():
            """List all installed fragments."""
            return self.storage_manager.list_installed_fragments()

        list_result = self.benchmark_operation("list_installed_fragments", list_fragments)
        list_result.metadata.update(
            {
                "description": "List installed fragments performance",
                "fragment_count": install_result.installed_count,
            }
        )
        results.append(list_result)

        # Benchmark retrieving individual fragments
        fragment_names = list(install_result.installed_fragments.keys())

        def retrieve_fragment(name):
            """Retrieve single fragment."""
            return self.storage_manager.get_fragment(name)

        if fragment_names:
            retrieve_result = self.benchmark_operation(
                "retrieve_single_fragment", retrieve_fragment, fragment_names[0]
            )
            retrieve_result.metadata.update(
                {
                    "description": "Single fragment retrieval performance",
                    "fragment_name": fragment_names[0],
                }
            )
            results.append(retrieve_result)

        # Benchmark removing fragments
        def remove_fragment(name):
            """Remove single fragment."""
            return self.storage_manager.remove_fragment(name)

        if len(fragment_names) > 1:
            remove_result = self.benchmark_operation(
                "remove_single_fragment", remove_fragment, fragment_names[1]
            )
            remove_result.metadata.update(
                {
                    "description": "Single fragment removal performance",
                    "fragment_name": fragment_names[1],
                }
            )
            results.append(remove_result)

        return results

    def benchmark_fragment_updates(self) -> List[BenchmarkResult]:
        """Benchmark fragment update operations."""
        results = []

        # Install versioned fragments first
        versioned_collection = self.sample_collections["versioned"]
        v1_path = versioned_collection / "agents" / "versioned-test-agent-v1.md"

        # Install v1.0.0
        self.installation_manager.install_from_source(str(v1_path), target_type="project")

        # Benchmark updating to v1.1.0
        v11_path = versioned_collection / "agents" / "versioned-test-agent-v11.md"

        def update_fragment():
            """Update fragment to newer version."""
            return self.update_manager.update_fragment("versioned-test-agent", str(v11_path))

        update_result = self.benchmark_operation("update_fragment_version", update_fragment)
        update_result.metadata.update(
            {
                "description": "Fragment version update performance",
                "from_version": "1.0.0",
                "to_version": "1.1.0",
            }
        )
        results.append(update_result)

        return results

    def run_comprehensive_benchmarks(self) -> Dict[str, List[BenchmarkResult]]:
        """Run all performance benchmarks."""
        try:
            self.setup_benchmark_environment()

            benchmark_suites = {
                "validation": self.benchmark_fragment_validation,
                "installation": self.benchmark_fragment_installation,
                "storage": self.benchmark_fragment_storage,
                "updates": self.benchmark_fragment_updates,
            }

            all_results = {}

            for suite_name, benchmark_func in benchmark_suites.items():
                print(f"Running {suite_name} benchmarks...")
                suite_results = benchmark_func()
                all_results[suite_name] = suite_results

                # Print summary
                print(f"  {suite_name.title()} Results:")
                for result in suite_results:
                    print(
                        f"    {result.operation}: {result.mean_time:.4f}s avg, {result.throughput:.2f} ops/sec"
                    )

            return all_results

        finally:
            self.teardown_benchmark_environment()

    def generate_performance_report(
        self, results: Dict[str, List[BenchmarkResult]]
    ) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        report = {
            "benchmark_info": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "iterations": self.config.iterations,
                "warmup_runs": self.config.warmup_runs,
                "timeout_seconds": self.config.timeout_seconds,
            },
            "summary": {
                "total_operations": sum(len(suite_results) for suite_results in results.values()),
                "total_benchmark_time": sum(
                    result.mean_time * result.iterations
                    for suite_results in results.values()
                    for result in suite_results
                ),
                "fastest_operation": None,
                "slowest_operation": None,
            },
            "detailed_results": {},
            "performance_analysis": {},
        }

        # Find fastest and slowest operations
        all_results = [result for suite_results in results.values() for result in suite_results]
        if all_results:
            fastest = min(all_results, key=lambda r: r.mean_time)
            slowest = max(all_results, key=lambda r: r.mean_time)

            report["summary"]["fastest_operation"] = {
                "operation": fastest.operation,
                "mean_time": fastest.mean_time,
                "throughput": fastest.throughput,
            }
            report["summary"]["slowest_operation"] = {
                "operation": slowest.operation,
                "mean_time": slowest.mean_time,
                "throughput": slowest.throughput,
            }

        # Add detailed results
        for suite_name, suite_results in results.items():
            report["detailed_results"][suite_name] = [result.to_dict() for result in suite_results]

        # Performance analysis
        report["performance_analysis"] = self._analyze_performance(results)

        return report

    def _analyze_performance(self, results: Dict[str, List[BenchmarkResult]]) -> Dict[str, Any]:
        """Analyze performance characteristics and identify patterns."""
        analysis = {"operation_categories": {}, "performance_patterns": [], "recommendations": []}

        # Categorize operations by performance
        all_results = [result for suite_results in results.values() for result in suite_results]

        if not all_results:
            return analysis

        mean_times = [result.mean_time for result in all_results]
        overall_mean = statistics.mean(mean_times)
        overall_std = statistics.stdev(mean_times) if len(mean_times) > 1 else 0.0

        # Categorize operations
        fast_threshold = overall_mean - overall_std
        slow_threshold = overall_mean + overall_std

        for result in all_results:
            if result.mean_time <= fast_threshold:
                category = "fast"
            elif result.mean_time >= slow_threshold:
                category = "slow"
            else:
                category = "medium"

            if category not in analysis["operation_categories"]:
                analysis["operation_categories"][category] = []

            analysis["operation_categories"][category].append(
                {
                    "operation": result.operation,
                    "mean_time": result.mean_time,
                    "throughput": result.throughput,
                }
            )

        # Identify patterns
        validation_results = results.get("validation", [])
        if validation_results:
            avg_validation_time = statistics.mean([r.mean_time for r in validation_results])
            analysis["performance_patterns"].append(
                f"Fragment validation averages {avg_validation_time:.4f}s per collection"
            )

        installation_results = results.get("installation", [])
        if installation_results:
            avg_installation_time = statistics.mean([r.mean_time for r in installation_results])
            analysis["performance_patterns"].append(
                f"Fragment installation averages {avg_installation_time:.4f}s per collection"
            )

        # Generate recommendations
        slow_operations = analysis["operation_categories"].get("slow", [])
        if slow_operations:
            analysis["recommendations"].append(
                f"Consider optimizing slow operations: {', '.join([op['operation'] for op in slow_operations])}"
            )

        # Check for high variance
        high_variance_ops = [
            result
            for result in all_results
            if result.metadata.get("coefficient_of_variation", 0) > 20
        ]
        if high_variance_ops:
            analysis["recommendations"].append(
                f"High variance detected in: {', '.join([op.operation for op in high_variance_ops])} - consider investigation"
            )

        return analysis


# Test functions for pytest integration
class TestFragmentPerformanceBenchmarks:
    """Test class for pytest integration of performance benchmarks."""

    def test_validation_performance_benchmarks(self):
        """Test validation performance is within acceptable limits."""
        benchmarks = FragmentPerformanceBenchmarks(
            PerformanceTestSuite(iterations=5, warmup_runs=1)
        )

        try:
            benchmarks.setup_benchmark_environment()
            validation_results = benchmarks.benchmark_fragment_validation()

            # Performance assertions
            for result in validation_results:
                assert result.iterations > 0, f"No successful iterations for {result.operation}"
                assert result.mean_time > 0, f"Invalid timing for {result.operation}"
                assert (
                    result.mean_time < 10.0
                ), f"Validation too slow: {result.operation} took {result.mean_time}s"

                # Consistency check
                cv = result.metadata.get("coefficient_of_variation", 0)
                assert (
                    cv < 50
                ), f"High variance in {result.operation}: {cv}% coefficient of variation"

        finally:
            benchmarks.teardown_benchmark_environment()

    def test_installation_performance_benchmarks(self):
        """Test installation performance is within acceptable limits."""
        benchmarks = FragmentPerformanceBenchmarks(
            PerformanceTestSuite(iterations=5, warmup_runs=1)
        )

        try:
            benchmarks.setup_benchmark_environment()
            installation_results = benchmarks.benchmark_fragment_installation()

            # Performance assertions
            for result in installation_results:
                assert result.iterations > 0, f"No successful iterations for {result.operation}"
                assert result.mean_time > 0, f"Invalid timing for {result.operation}"
                assert (
                    result.mean_time < 30.0
                ), f"Installation too slow: {result.operation} took {result.mean_time}s"

                # Throughput check
                assert (
                    result.throughput > 0.01
                ), f"Very low throughput for {result.operation}: {result.throughput} ops/sec"

        finally:
            benchmarks.teardown_benchmark_environment()

    def test_comprehensive_performance_suite(self):
        """Test the complete performance benchmark suite."""
        benchmarks = FragmentPerformanceBenchmarks(
            PerformanceTestSuite(iterations=3, warmup_runs=1)
        )

        all_results = benchmarks.run_comprehensive_benchmarks()

        # Verify we got results from all benchmark suites
        expected_suites = ["validation", "installation", "storage", "updates"]
        for suite in expected_suites:
            assert suite in all_results, f"Missing benchmark suite: {suite}"
            assert len(all_results[suite]) > 0, f"No results from {suite} suite"

        # Generate and verify report
        report = benchmarks.generate_performance_report(all_results)

        assert "benchmark_info" in report
        assert "summary" in report
        assert "detailed_results" in report
        assert "performance_analysis" in report

        # Verify report completeness
        assert report["summary"]["total_operations"] > 0
        assert report["summary"]["fastest_operation"] is not None
        assert report["summary"]["slowest_operation"] is not None


if __name__ == "__main__":
    """Run performance benchmarks standalone."""
    print("Running Fragment Performance Benchmarks...")

    benchmarks = FragmentPerformanceBenchmarks(PerformanceTestSuite(iterations=10, warmup_runs=3))

    all_results = benchmarks.run_comprehensive_benchmarks()
    report = benchmarks.generate_performance_report(all_results)

    # Save report to file
    report_file = Path("fragment_performance_report.json")
    report_file.write_text(json.dumps(report, indent=2, sort_keys=True))

    print(f"\nPerformance report saved to: {report_file}")
    print("\nSummary:")
    print(f"  Total operations: {report['summary']['total_operations']}")
    print(
        f"  Fastest: {report['summary']['fastest_operation']['operation']} - {report['summary']['fastest_operation']['mean_time']:.4f}s"
    )
    print(
        f"  Slowest: {report['summary']['slowest_operation']['operation']} - {report['summary']['slowest_operation']['mean_time']:.4f}s"
    )
