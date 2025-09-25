"""Performance testing utilities for PACC E2E tests."""

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import psutil


@dataclass
class PerformanceMetrics:
    """Performance metrics for an operation."""

    operation_name: str
    duration: float
    memory_delta: int
    peak_memory: int
    throughput: Optional[float] = None
    checkpoints: List[Dict[str, Any]] = None

    @property
    def memory_delta_mb(self) -> float:
        """Memory delta in MB."""
        return self.memory_delta / 1024 / 1024

    @property
    def peak_memory_mb(self) -> float:
        """Peak memory in MB."""
        return self.peak_memory / 1024 / 1024


class PerformanceProfiler:
    """Advanced performance profiler for PACC operations."""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
        self.peak_memory = None
        self.process = psutil.Process(os.getpid())
        self.checkpoints = []
        self.custom_metrics = {}

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end()

    def start(self):
        """Start performance monitoring."""
        self.start_memory = self.process.memory_info().rss
        self.peak_memory = self.start_memory
        self.start_time = time.perf_counter()

    def end(self):
        """End performance monitoring."""
        self.end_time = time.perf_counter()
        self.end_memory = self.process.memory_info().rss

    def checkpoint(self, name: str, **custom_data):
        """Add a performance checkpoint."""
        if not self.start_time:
            raise RuntimeError("Profiler not started")

        current_time = time.perf_counter()
        current_memory = self.process.memory_info().rss
        self.peak_memory = max(self.peak_memory or 0, current_memory)

        checkpoint = {
            "name": name,
            "elapsed": current_time - self.start_time,
            "memory": current_memory,
            "memory_delta": current_memory - self.start_memory,
            "timestamp": current_time,
            **custom_data,
        }

        self.checkpoints.append(checkpoint)
        return checkpoint

    def add_metric(self, name: str, value: Any):
        """Add custom metric."""
        self.custom_metrics[name] = value

    @property
    def duration(self) -> float:
        """Get total duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    @property
    def memory_delta(self) -> int:
        """Get memory delta in bytes."""
        if self.start_memory and self.end_memory:
            return self.end_memory - self.start_memory
        return 0

    @property
    def peak_memory_delta(self) -> int:
        """Get peak memory delta in bytes."""
        if self.start_memory and self.peak_memory:
            return self.peak_memory - self.start_memory
        return 0

    def get_metrics(self, items_processed: Optional[int] = None) -> PerformanceMetrics:
        """Get performance metrics."""
        throughput = None
        if items_processed and self.duration > 0:
            throughput = items_processed / self.duration

        return PerformanceMetrics(
            operation_name=self.operation_name,
            duration=self.duration,
            memory_delta=self.memory_delta,
            peak_memory=self.peak_memory_delta,
            throughput=throughput,
            checkpoints=self.checkpoints.copy(),
        )

    def get_report(self) -> Dict[str, Any]:
        """Get detailed performance report."""
        return {
            "operation": self.operation_name,
            "duration": self.duration,
            "memory_delta": self.memory_delta,
            "memory_delta_mb": self.memory_delta / 1024 / 1024,
            "peak_memory_delta": self.peak_memory_delta,
            "peak_memory_mb": self.peak_memory_delta / 1024 / 1024,
            "checkpoints": self.checkpoints,
            "custom_metrics": self.custom_metrics,
        }


class MemoryMonitor:
    """Monitor memory usage patterns."""

    def __init__(self, sample_interval: float = 0.1):
        self.sample_interval = sample_interval
        self.process = psutil.Process(os.getpid())
        self.baseline_memory = None
        self.samples = []
        self.monitoring = False

    def start(self):
        """Start memory monitoring."""
        self.baseline_memory = self.process.memory_info().rss
        self.samples = []
        self.monitoring = True

    def stop(self):
        """Stop memory monitoring."""
        self.monitoring = False

    def sample(self, label: str = None):
        """Take a memory sample."""
        if not self.monitoring:
            return

        current_memory = self.process.memory_info().rss
        sample = {
            "timestamp": time.perf_counter(),
            "memory": current_memory,
            "delta": current_memory - (self.baseline_memory or 0),
            "label": label,
        }
        self.samples.append(sample)
        return sample

    @property
    def peak_memory_delta(self) -> int:
        """Get peak memory delta from baseline."""
        if not self.samples:
            return 0
        return max(sample["delta"] for sample in self.samples)

    @property
    def current_memory_delta(self) -> int:
        """Get current memory delta from baseline."""
        if not self.samples:
            return 0
        return self.samples[-1]["delta"]

    def get_memory_profile(self) -> Dict[str, Any]:
        """Get memory usage profile."""
        if not self.samples:
            return {}

        deltas = [sample["delta"] for sample in self.samples]

        return {
            "baseline_memory": self.baseline_memory,
            "peak_delta": max(deltas),
            "final_delta": deltas[-1],
            "average_delta": sum(deltas) / len(deltas),
            "samples_count": len(self.samples),
            "samples": self.samples,
        }


class BenchmarkReporter:
    """Generate benchmark reports."""

    def __init__(self):
        self.results = []

    def add_result(self, metrics: PerformanceMetrics):
        """Add benchmark result."""
        self.results.append(metrics)

    def generate_summary(self) -> Dict[str, Any]:
        """Generate benchmark summary."""
        if not self.results:
            return {}

        durations = [r.duration for r in self.results]
        memory_deltas = [r.memory_delta_mb for r in self.results]
        throughputs = [r.throughput for r in self.results if r.throughput]

        summary = {
            "total_operations": len(self.results),
            "duration": {
                "total": sum(durations),
                "average": sum(durations) / len(durations),
                "min": min(durations),
                "max": max(durations),
            },
            "memory": {
                "average_delta_mb": sum(memory_deltas) / len(memory_deltas),
                "peak_delta_mb": max(memory_deltas),
                "min_delta_mb": min(memory_deltas),
            },
        }

        if throughputs:
            summary["throughput"] = {
                "average": sum(throughputs) / len(throughputs),
                "peak": max(throughputs),
                "min": min(throughputs),
            }

        return summary

    def print_summary(self):
        """Print benchmark summary."""
        summary = self.generate_summary()

        print("\n" + "=" * 60)
        print("BENCHMARK SUMMARY")
        print("=" * 60)

        print(f"Operations: {summary['total_operations']}")
        print(f"Total time: {summary['duration']['total']:.3f}s")
        print(f"Average time: {summary['duration']['average']:.3f}s")
        print(f"Time range: {summary['duration']['min']:.3f}s - {summary['duration']['max']:.3f}s")

        print(f"Average memory: {summary['memory']['average_delta_mb']:.1f}MB")
        print(f"Peak memory: {summary['memory']['peak_delta_mb']:.1f}MB")

        if "throughput" in summary:
            print(f"Average throughput: {summary['throughput']['average']:.1f} ops/s")
            print(f"Peak throughput: {summary['throughput']['peak']:.1f} ops/s")

        print("=" * 60)


def assert_performance(
    metrics: PerformanceMetrics,
    max_duration: Optional[float] = None,
    max_memory_mb: Optional[float] = None,
    min_throughput: Optional[float] = None,
    max_peak_memory_mb: Optional[float] = None,
):
    """Assert performance requirements are met."""
    operation = metrics.operation_name

    if max_duration is not None:
        assert (
            metrics.duration <= max_duration
        ), f"{operation} took {metrics.duration:.3f}s (should be ≤ {max_duration}s)"

    if max_memory_mb is not None:
        assert (
            metrics.memory_delta_mb <= max_memory_mb
        ), f"{operation} used {metrics.memory_delta_mb:.1f}MB (should be ≤ {max_memory_mb}MB)"

    if max_peak_memory_mb is not None:
        assert (
            metrics.peak_memory_mb <= max_peak_memory_mb
        ), f"{operation} peak memory {metrics.peak_memory_mb:.1f}MB (should be ≤ {max_peak_memory_mb}MB)"

    if min_throughput is not None and metrics.throughput is not None:
        assert (
            metrics.throughput >= min_throughput
        ), f"{operation} throughput {metrics.throughput:.1f} (should be ≥ {min_throughput})"


def measure_throughput(operation: Callable, items: List[Any], batch_size: int = 1) -> float:
    """Measure throughput of an operation."""
    start_time = time.perf_counter()

    if batch_size == 1:
        for item in items:
            operation(item)
    else:
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            operation(batch)

    end_time = time.perf_counter()
    duration = end_time - start_time

    return len(items) / duration if duration > 0 else 0


@contextmanager
def performance_monitor(operation_name: str, items_count: Optional[int] = None):
    """Context manager for performance monitoring."""
    profiler = PerformanceProfiler(operation_name)

    try:
        profiler.start()
        yield profiler
    finally:
        profiler.end()
        metrics = profiler.get_metrics(items_count)

        # Print basic performance info
        print(f"{operation_name}: {metrics.duration:.3f}s", end="")
        if metrics.throughput:
            print(f", {metrics.throughput:.1f} items/s", end="")
        print(f", {metrics.memory_delta_mb:.1f}MB")


class PerformanceAssertion:
    """Performance assertion builder."""

    def __init__(self, metrics: PerformanceMetrics):
        self.metrics = metrics

    def duration_less_than(self, seconds: float):
        """Assert duration is less than specified seconds."""
        assert (
            self.metrics.duration < seconds
        ), f"{self.metrics.operation_name} took {self.metrics.duration:.3f}s (should be < {seconds}s)"
        return self

    def memory_less_than(self, mb: float):
        """Assert memory usage is less than specified MB."""
        assert (
            self.metrics.memory_delta_mb < mb
        ), f"{self.metrics.operation_name} used {self.metrics.memory_delta_mb:.1f}MB (should be < {mb}MB)"
        return self

    def throughput_greater_than(self, ops_per_sec: float):
        """Assert throughput is greater than specified ops/sec."""
        if self.metrics.throughput is None:
            raise ValueError("No throughput data available")
        assert (
            self.metrics.throughput > ops_per_sec
        ), f"{self.metrics.operation_name} throughput {self.metrics.throughput:.1f} (should be > {ops_per_sec})"
        return self

    def peak_memory_less_than(self, mb: float):
        """Assert peak memory is less than specified MB."""
        assert (
            self.metrics.peak_memory_mb < mb
        ), f"{self.metrics.operation_name} peak memory {self.metrics.peak_memory_mb:.1f}MB (should be < {mb}MB)"
        return self


def assert_that(metrics: PerformanceMetrics) -> PerformanceAssertion:
    """Create a performance assertion builder."""
    return PerformanceAssertion(metrics)
