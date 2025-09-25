"""Performance benchmarks for PACC source management components."""

import json
import os
import time
from pathlib import Path

import psutil
import pytest

from pacc.core.file_utils import DirectoryScanner, FileFilter, FilePathValidator, PathNormalizer
from pacc.security.security_measures import InputSanitizer, SecurityAuditor
from pacc.validators.base import BaseValidator, ValidationResult


class PerformanceProfiler:
    """Simple performance profiler for benchmarking."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
        self.process = psutil.Process(os.getpid())

    def start(self):
        """Start profiling."""
        self.start_memory = self.process.memory_info().rss
        self.start_time = time.perf_counter()

    def end(self):
        """End profiling."""
        self.end_time = time.perf_counter()
        self.end_memory = self.process.memory_info().rss

    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def memory_delta(self) -> int:
        """Get memory delta in bytes."""
        if self.start_memory and self.end_memory:
            return self.end_memory - self.start_memory
        return 0


@pytest.fixture
def large_test_dataset(tmp_path) -> Path:
    """Create large test dataset for performance testing."""
    dataset_dir = tmp_path / "large_dataset"
    dataset_dir.mkdir()

    # Create directory structure with many files
    categories = ["hooks", "mcp", "agents", "commands"]
    files_per_category = 1000

    for category in categories:
        category_dir = dataset_dir / category
        category_dir.mkdir()

        for i in range(files_per_category):
            if category == "hooks":
                file_path = category_dir / f"hook_{i:04d}.json"
                content = {
                    "name": f"hook-{i}",
                    "version": "1.0.0",
                    "description": f"Hook number {i} for testing performance",
                    "events": ["PreToolUse", "PostToolUse"],
                    "matchers": [{"pattern": f"*{i}*"}],
                }
                file_path.write_text(json.dumps(content, indent=2))

            elif category == "mcp":
                file_path = category_dir / f"server_{i:04d}.yaml"
                content = f"""name: server-{i}
command: python
args:
  - -m
  - server_{i}
env:
  SERVER_ID: "{i}"
  DEBUG: "false"
"""
                file_path.write_text(content)

            elif category == "agents":
                file_path = category_dir / f"agent_{i:04d}.md"
                content = f"""---
name: agent-{i}
version: 1.0.0
description: Agent number {i} for performance testing
capabilities:
  - data_processing
  - analysis
---

# Agent {i}

This is agent number {i} created for performance testing.

## Capabilities

- Process data efficiently
- Analyze patterns
- Generate insights

## Instructions

Use this agent for performance testing scenarios.
"""
                file_path.write_text(content)

            elif category == "commands":
                file_path = category_dir / f"command_{i:04d}.md"
                content = f"""# Command {i}

Performance testing command number {i}.

## Usage

```bash
command-{i} --input data --output results
```

## Parameters

- `--input`: Input data file
- `--output`: Output results file
- `--verbose`: Enable verbose output

## Examples

```bash
# Basic usage
command-{i} --input test.json --output results.json

# Verbose mode
command-{i} --input test.json --output results.json --verbose
```
"""
                file_path.write_text(content)

    return dataset_dir


@pytest.mark.performance
class TestFileUtilsPerformance:
    """Performance tests for file utilities."""

    def test_file_path_validator_performance(self, large_test_dataset):
        """Test FilePathValidator performance with large dataset."""
        validator = FilePathValidator(allowed_extensions={".json", ".yaml", ".md"})

        # Collect all files
        all_files = list(large_test_dataset.rglob("*"))
        file_paths = [f for f in all_files if f.is_file()]

        profiler = PerformanceProfiler()
        profiler.start()

        # Validate all files
        valid_count = 0
        for file_path in file_paths:
            if validator.is_valid_path(file_path):
                valid_count += 1

        profiler.end()

        # Performance assertions
        assert profiler.duration < 2.0  # Should complete in under 2 seconds
        assert len(file_paths) == 4000  # Should find all test files
        assert valid_count > 3900  # Most files should be valid

        # Calculate throughput
        throughput = len(file_paths) / profiler.duration
        assert throughput > 2000  # At least 2000 files/second

        print(f"Validated {len(file_paths)} files in {profiler.duration:.3f}s")
        print(f"Throughput: {throughput:.0f} files/second")
        print(f"Memory delta: {profiler.memory_delta / 1024 / 1024:.1f} MB")

    def test_directory_scanner_performance(self, large_test_dataset):
        """Test DirectoryScanner performance with large dataset."""
        scanner = DirectoryScanner()

        profiler = PerformanceProfiler()
        profiler.start()

        # Scan directory recursively
        discovered_files = list(scanner.scan_directory(large_test_dataset, recursive=True))

        profiler.end()

        # Performance assertions
        assert profiler.duration < 1.0  # Should complete in under 1 second
        assert len(discovered_files) == 4000  # Should find all files

        # Calculate throughput
        throughput = len(discovered_files) / profiler.duration
        assert throughput > 4000  # At least 4000 files/second

        print(f"Scanned {len(discovered_files)} files in {profiler.duration:.3f}s")
        print(f"Throughput: {throughput:.0f} files/second")

    def test_file_filter_performance(self, large_test_dataset):
        """Test FileFilter performance with large dataset."""
        scanner = DirectoryScanner()
        all_files = list(scanner.scan_directory(large_test_dataset, recursive=True))

        # Create complex filter
        file_filter = (
            FileFilter()
            .add_extension_filter({".json", ".yaml", ".md"})
            .add_size_filter(100, 100 * 1024)  # 100 bytes to 100KB
            .add_exclude_hidden()
        )

        profiler = PerformanceProfiler()
        profiler.start()

        # Apply filters
        filtered_files = file_filter.filter_files(all_files)

        profiler.end()

        # Performance assertions
        assert profiler.duration < 0.5  # Should complete in under 0.5 seconds
        assert len(filtered_files) > 3000  # Should match most files

        # Calculate throughput
        throughput = len(all_files) / profiler.duration
        assert throughput > 8000  # At least 8000 files/second

        print(f"Filtered {len(all_files)} files in {profiler.duration:.3f}s")
        print(f"Result: {len(filtered_files)} files passed filters")
        print(f"Throughput: {throughput:.0f} files/second")

    def test_path_normalizer_performance(self, large_test_dataset):
        """Test PathNormalizer performance with many paths."""
        scanner = DirectoryScanner()
        all_files = list(scanner.scan_directory(large_test_dataset, recursive=True))

        profiler = PerformanceProfiler()
        profiler.start()

        # Normalize all paths
        normalized_paths = []
        for file_path in all_files:
            normalized = PathNormalizer.normalize(file_path)
            posix_path = PathNormalizer.to_posix(file_path)
            normalized_paths.append((normalized, posix_path))

        profiler.end()

        # Performance assertions
        assert profiler.duration < 1.0  # Should complete in under 1 second
        assert len(normalized_paths) == len(all_files)

        # Calculate throughput
        throughput = len(all_files) / profiler.duration
        assert throughput > 4000  # At least 4000 paths/second

        print(f"Normalized {len(all_files)} paths in {profiler.duration:.3f}s")
        print(f"Throughput: {throughput:.0f} paths/second")


@pytest.mark.performance
class TestValidationPerformance:
    """Performance tests for validation components."""

    def create_mock_validator(self):
        """Create mock validator for performance testing."""

        class PerformanceValidator(BaseValidator):
            def get_extension_type(self):
                return "performance"

            def validate_single(self, file_path):
                result = ValidationResult(
                    is_valid=True,
                    file_path=str(file_path),
                    extension_type=self.get_extension_type(),
                )

                # Basic validation
                access_error = self._validate_file_accessibility(file_path)
                if access_error:
                    result.add_error(access_error.code, access_error.message)
                    return result

                # Simple content validation
                try:
                    content = file_path.read_text()
                    if len(content) > 100000:  # 100KB limit
                        result.add_warning("LARGE_FILE", "File is quite large")

                    if len(content) == 0:
                        result.add_error("EMPTY_FILE", "File is empty")

                except Exception as e:
                    result.add_error("READ_ERROR", f"Cannot read file: {e}")

                return result

            def _find_extension_files(self, directory):
                return list(directory.rglob("*"))

        return PerformanceValidator()

    def test_single_file_validation_performance(self, large_test_dataset):
        """Test single file validation performance."""
        validator = self.create_mock_validator()

        # Get sample of files
        all_files = list(large_test_dataset.rglob("*.json"))[:100]

        profiler = PerformanceProfiler()
        profiler.start()

        # Validate files individually
        results = []
        for file_path in all_files:
            result = validator.validate_single(file_path)
            results.append(result)

        profiler.end()

        # Performance assertions
        assert profiler.duration < 0.5  # Should complete in under 0.5 seconds
        assert len(results) == len(all_files)

        # Calculate throughput
        throughput = len(all_files) / profiler.duration
        assert throughput > 200  # At least 200 validations/second

        print(f"Validated {len(all_files)} files in {profiler.duration:.3f}s")
        print(f"Throughput: {throughput:.0f} validations/second")

    def test_batch_validation_performance(self, large_test_dataset):
        """Test batch validation performance."""
        validator = self.create_mock_validator()

        # Get larger sample
        all_files = list(large_test_dataset.rglob("*.json"))[:500]

        profiler = PerformanceProfiler()
        profiler.start()

        # Batch validate
        results = validator.validate_batch(all_files)

        profiler.end()

        # Performance assertions
        assert profiler.duration < 2.0  # Should complete in under 2 seconds
        assert len(results) == len(all_files)

        # Calculate throughput
        throughput = len(all_files) / profiler.duration
        assert throughput > 250  # At least 250 validations/second

        print(f"Batch validated {len(all_files)} files in {profiler.duration:.3f}s")
        print(f"Throughput: {throughput:.0f} validations/second")

    def test_directory_validation_performance(self, large_test_dataset):
        """Test directory validation performance."""
        validator = self.create_mock_validator()

        # Test on hooks directory (1000 files)
        hooks_dir = large_test_dataset / "hooks"

        profiler = PerformanceProfiler()
        profiler.start()

        # Validate entire directory
        results = validator.validate_directory(hooks_dir)

        profiler.end()

        # Performance assertions
        assert profiler.duration < 5.0  # Should complete in under 5 seconds
        assert len(results) == 1000  # Should validate all hook files

        # Calculate throughput
        throughput = len(results) / profiler.duration
        assert throughput > 200  # At least 200 validations/second

        print(f"Directory validated {len(results)} files in {profiler.duration:.3f}s")
        print(f"Throughput: {throughput:.0f} validations/second")


@pytest.mark.performance
class TestSecurityPerformance:
    """Performance tests for security components."""

    def test_input_sanitizer_performance(self):
        """Test InputSanitizer performance with large content."""
        sanitizer = InputSanitizer()

        # Create large content with various patterns
        content_parts = []
        for i in range(1000):
            content_parts.append(f"Normal content line {i}")
            if i % 100 == 0:
                content_parts.append("import os  # Suspicious pattern")
            if i % 200 == 0:
                content_parts.append("eval(user_input)  # Another suspicious pattern")

        large_content = "\n".join(content_parts)

        profiler = PerformanceProfiler()
        profiler.start()

        # Scan content for threats
        issues = sanitizer.scan_for_threats(large_content, "test_content")

        profiler.end()

        # Performance assertions
        assert profiler.duration < 1.0  # Should complete in under 1 second
        assert len(issues) > 0  # Should find suspicious patterns

        # Calculate throughput
        throughput = len(large_content) / profiler.duration
        assert throughput > 100000  # At least 100KB/second

        print(f"Scanned {len(large_content)} chars in {profiler.duration:.3f}s")
        print(f"Found {len(issues)} issues")
        print(f"Throughput: {throughput/1024:.0f} KB/second")

    def test_security_auditor_performance(self, large_test_dataset):
        """Test SecurityAuditor performance with many files."""
        auditor = SecurityAuditor()

        # Test on a subset of files to avoid very long test times
        sample_files = list(large_test_dataset.rglob("*.json"))[:100]

        profiler = PerformanceProfiler()
        profiler.start()

        # Audit each file
        audit_results = []
        for file_path in sample_files:
            result = auditor.audit_file(file_path, "performance_test")
            audit_results.append(result)

        profiler.end()

        # Performance assertions
        assert profiler.duration < 5.0  # Should complete in under 5 seconds
        assert len(audit_results) == len(sample_files)

        # Calculate throughput
        throughput = len(sample_files) / profiler.duration
        assert throughput > 20  # At least 20 audits/second

        print(f"Audited {len(sample_files)} files in {profiler.duration:.3f}s")
        print(f"Throughput: {throughput:.0f} audits/second")

    def test_directory_audit_performance(self, tmp_path):
        """Test directory audit performance."""
        auditor = SecurityAuditor()

        # Create smaller test directory for focused performance test
        test_dir = tmp_path / "audit_test"
        test_dir.mkdir()

        # Create 50 test files
        for i in range(50):
            file_path = test_dir / f"test_{i:02d}.json"
            content = {"name": f"test-{i}", "version": "1.0.0", "data": f"Test data for file {i}"}
            file_path.write_text(json.dumps(content))

        profiler = PerformanceProfiler()
        profiler.start()

        # Audit entire directory
        result = auditor.audit_directory(test_dir, recursive=True)

        profiler.end()

        # Performance assertions
        assert profiler.duration < 3.0  # Should complete in under 3 seconds
        assert result["summary"]["total_files"] == 50

        # Calculate throughput
        throughput = result["summary"]["total_files"] / profiler.duration
        assert throughput > 15  # At least 15 files/second for full audit

        print(
            f"Directory audit: {result['summary']['total_files']} files in {profiler.duration:.3f}s"
        )
        print(f"Throughput: {throughput:.0f} files/second")


@pytest.mark.performance
class TestMemoryPerformance:
    """Test memory usage patterns and optimization."""

    def test_memory_usage_large_directory(self, large_test_dataset):
        """Test memory usage when processing large directories."""
        import gc

        scanner = DirectoryScanner()

        # Force garbage collection before starting
        gc.collect()
        initial_memory = psutil.Process(os.getpid()).memory_info().rss

        # Process large directory
        all_files = list(scanner.scan_directory(large_test_dataset, recursive=True))

        # Check memory after processing
        after_scan_memory = psutil.Process(os.getpid()).memory_info().rss
        memory_delta = after_scan_memory - initial_memory

        # Memory assertions
        assert len(all_files) == 4000  # Should find all files
        assert memory_delta < 100 * 1024 * 1024  # Should use less than 100MB

        # Test memory cleanup
        del all_files
        gc.collect()

        final_memory = psutil.Process(os.getpid()).memory_info().rss
        cleanup_delta = after_scan_memory - final_memory

        print(f"Processed {len(all_files) if 'all_files' in locals() else 4000} files")
        print(f"Memory delta: {memory_delta / 1024 / 1024:.1f} MB")
        print(f"Memory cleanup: {cleanup_delta / 1024 / 1024:.1f} MB")

    def test_memory_efficient_batch_processing(self, large_test_dataset):
        """Test memory-efficient batch processing of large datasets."""
        scanner = DirectoryScanner()
        validator = FilePathValidator()

        # Process in batches to test memory efficiency
        batch_size = 100
        processed_count = 0
        max_memory_delta = 0

        initial_memory = psutil.Process(os.getpid()).memory_info().rss

        for file_path in scanner.scan_directory(large_test_dataset, recursive=True):
            # Process individual file
            is_valid = validator.is_valid_path(file_path)
            processed_count += 1

            # Check memory every batch
            if processed_count % batch_size == 0:
                current_memory = psutil.Process(os.getpid()).memory_info().rss
                memory_delta = current_memory - initial_memory
                max_memory_delta = max(max_memory_delta, memory_delta)

        # Memory assertions
        assert processed_count == 4000  # Should process all files
        assert max_memory_delta < 50 * 1024 * 1024  # Should use less than 50MB

        print(f"Processed {processed_count} files in batches of {batch_size}")
        print(f"Max memory delta: {max_memory_delta / 1024 / 1024:.1f} MB")


@pytest.mark.performance
class TestScalabilityBenchmarks:
    """Test scalability with increasing dataset sizes."""

    def test_scaling_file_count(self, tmp_path):
        """Test performance scaling with increasing file count."""
        scanner = DirectoryScanner()
        validator = FilePathValidator()

        file_counts = [100, 500, 1000, 2000]
        results = []

        for file_count in file_counts:
            # Create test dataset of specified size
            test_dir = tmp_path / f"scale_test_{file_count}"
            test_dir.mkdir()

            for i in range(file_count):
                file_path = test_dir / f"file_{i:04d}.json"
                content = {"id": i, "data": f"test data {i}"}
                file_path.write_text(json.dumps(content))

            # Time the scanning operation
            start_time = time.perf_counter()
            files = list(scanner.scan_directory(test_dir, recursive=True))
            scan_time = time.perf_counter() - start_time

            # Time the validation operation
            start_time = time.perf_counter()
            valid_count = sum(1 for f in files if validator.is_valid_path(f))
            validate_time = time.perf_counter() - start_time

            results.append(
                {
                    "file_count": file_count,
                    "scan_time": scan_time,
                    "validate_time": validate_time,
                    "total_time": scan_time + validate_time,
                    "scan_throughput": file_count / scan_time,
                    "validate_throughput": file_count / validate_time,
                }
            )

        # Analyze scaling behavior
        for result in results:
            print(
                f"Files: {result['file_count']}, "
                f"Scan: {result['scan_time']:.3f}s ({result['scan_throughput']:.0f}/s), "
                f"Validate: {result['validate_time']:.3f}s ({result['validate_throughput']:.0f}/s)"
            )

        # Performance assertions
        for result in results:
            assert result["scan_throughput"] > 1000  # At least 1000 files/second
            assert result["validate_throughput"] > 1000  # At least 1000 validations/second

    def test_scaling_file_size(self, tmp_path):
        """Test performance scaling with increasing file sizes."""
        validator = FilePathValidator()

        file_sizes = [1024, 10 * 1024, 100 * 1024, 1024 * 1024]  # 1KB, 10KB, 100KB, 1MB
        results = []

        for file_size in file_sizes:
            # Create test file of specified size
            test_file = tmp_path / f"large_file_{file_size}.json"

            # Create JSON content of approximately the target size
            content = {
                "metadata": {"size": file_size},
                "data": "x" * (file_size - 100),  # Approximate content size
            }
            test_file.write_text(json.dumps(content))

            # Time the validation operation
            start_time = time.perf_counter()
            is_valid = validator.is_valid_path(test_file)
            validate_time = time.perf_counter() - start_time

            actual_size = test_file.stat().st_size

            results.append(
                {
                    "target_size": file_size,
                    "actual_size": actual_size,
                    "validate_time": validate_time,
                    "throughput_mbps": (actual_size / 1024 / 1024) / validate_time,
                }
            )

        # Analyze scaling behavior
        for result in results:
            print(
                f"Size: {result['actual_size']/1024:.0f}KB, "
                f"Time: {result['validate_time']:.3f}s, "
                f"Throughput: {result['throughput_mbps']:.1f} MB/s"
            )

        # Performance assertions
        for result in results:
            # Should maintain reasonable throughput even for large files
            if result["actual_size"] > 100 * 1024:  # For files > 100KB
                assert result["throughput_mbps"] > 10  # At least 10 MB/s


# Performance test configuration
@pytest.fixture(autouse=True, scope="session")
def performance_test_setup():
    """Setup for performance tests."""
    print("\n" + "=" * 80)
    print("PACC Performance Benchmark Suite")
    print("=" * 80)

    # System information
    print(f"Python version: {os.sys.version}")
    print(f"Platform: {os.name}")
    print(f"CPU count: {psutil.cpu_count()}")
    print(f"Memory: {psutil.virtual_memory().total / 1024 / 1024 / 1024:.1f} GB")
    print("=" * 80)


# Performance summary
@pytest.fixture(autouse=True, scope="session")
def performance_summary():
    """Print performance summary after tests."""
    yield

    print("\n" + "=" * 80)
    print("Performance Benchmark Summary")
    print("=" * 80)
    print("All performance benchmarks completed.")
    print("Check individual test outputs for detailed metrics.")
    print("=" * 80)
