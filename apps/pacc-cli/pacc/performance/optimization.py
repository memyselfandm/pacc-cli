"""Performance optimization and profiling utilities."""

import asyncio
import cProfile
import functools
import gc
import io
import pstats
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
import threading
import psutil
import logging

from .caching import get_cache_manager
from .background_workers import get_worker_pool


logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""
    
    operation_name: str
    start_time: float
    end_time: float
    memory_before: int
    memory_after: int
    cpu_percent: float
    execution_count: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> float:
        """Get operation duration in seconds."""
        return self.end_time - self.start_time
    
    @property
    def memory_delta(self) -> int:
        """Get memory usage delta in bytes."""
        return self.memory_after - self.memory_before
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'operation_name': self.operation_name,
            'duration': self.duration,
            'memory_delta': self.memory_delta,
            'memory_before': self.memory_before,
            'memory_after': self.memory_after,
            'cpu_percent': self.cpu_percent,
            'execution_count': self.execution_count,
            'metadata': self.metadata
        }


@dataclass
class BenchmarkResult:
    """Result of a benchmark operation."""
    
    name: str
    iterations: int
    total_time: float
    average_time: float
    min_time: float
    max_time: float
    std_deviation: float
    ops_per_second: float
    memory_usage: Dict[str, int]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'name': self.name,
            'iterations': self.iterations,
            'total_time': self.total_time,
            'average_time': self.average_time,
            'min_time': self.min_time,
            'max_time': self.max_time,
            'std_deviation': self.std_deviation,
            'ops_per_second': self.ops_per_second,
            'memory_usage': self.memory_usage,
            'metadata': self.metadata
        }


class PerformanceMonitor:
    """Monitor for tracking performance metrics."""
    
    def __init__(self):
        """Initialize performance monitor."""
        self.metrics: List[PerformanceMetrics] = []
        self._lock = threading.Lock()
        self._enabled = True
    
    def enable(self) -> None:
        """Enable performance monitoring."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable performance monitoring."""
        self._enabled = False
    
    def record_operation(
        self,
        operation_name: str,
        duration: float,
        memory_delta: int = 0,
        cpu_percent: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record performance metrics for an operation.
        
        Args:
            operation_name: Name of the operation
            duration: Duration in seconds
            memory_delta: Memory usage change in bytes
            cpu_percent: CPU usage percentage
            metadata: Additional metadata
        """
        if not self._enabled:
            return
        
        current_time = time.time()
        memory_before = psutil.Process().memory_info().rss - memory_delta
        memory_after = psutil.Process().memory_info().rss
        
        metrics = PerformanceMetrics(
            operation_name=operation_name,
            start_time=current_time - duration,
            end_time=current_time,
            memory_before=memory_before,
            memory_after=memory_after,
            cpu_percent=cpu_percent,
            metadata=metadata or {}
        )
        
        with self._lock:
            self.metrics.append(metrics)
    
    def get_metrics(
        self,
        operation_name: Optional[str] = None,
        since: Optional[float] = None
    ) -> List[PerformanceMetrics]:
        """Get recorded metrics.
        
        Args:
            operation_name: Filter by operation name
            since: Only return metrics since this timestamp
            
        Returns:
            List of performance metrics
        """
        with self._lock:
            filtered_metrics = self.metrics.copy()
        
        if operation_name:
            filtered_metrics = [m for m in filtered_metrics if m.operation_name == operation_name]
        
        if since:
            filtered_metrics = [m for m in filtered_metrics if m.start_time >= since]
        
        return filtered_metrics
    
    def get_summary(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """Get performance summary.
        
        Args:
            operation_name: Filter by operation name
            
        Returns:
            Performance summary
        """
        metrics = self.get_metrics(operation_name)
        
        if not metrics:
            return {'operation_count': 0}
        
        durations = [m.duration for m in metrics]
        memory_deltas = [m.memory_delta for m in metrics]
        
        return {
            'operation_count': len(metrics),
            'total_duration': sum(durations),
            'average_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'total_memory_delta': sum(memory_deltas),
            'average_memory_delta': sum(memory_deltas) / len(memory_deltas),
            'operations_by_name': self._group_by_operation(metrics)
        }
    
    def clear_metrics(self, older_than: Optional[float] = None) -> int:
        """Clear recorded metrics.
        
        Args:
            older_than: Only clear metrics older than this timestamp
            
        Returns:
            Number of metrics cleared
        """
        with self._lock:
            if older_than is None:
                count = len(self.metrics)
                self.metrics.clear()
                return count
            else:
                old_count = len(self.metrics)
                self.metrics = [m for m in self.metrics if m.start_time >= older_than]
                return old_count - len(self.metrics)
    
    def _group_by_operation(self, metrics: List[PerformanceMetrics]) -> Dict[str, Dict[str, Any]]:
        """Group metrics by operation name."""
        grouped: Dict[str, List[PerformanceMetrics]] = {}
        
        for metric in metrics:
            if metric.operation_name not in grouped:
                grouped[metric.operation_name] = []
            grouped[metric.operation_name].append(metric)
        
        result = {}
        for op_name, op_metrics in grouped.items():
            durations = [m.duration for m in op_metrics]
            result[op_name] = {
                'count': len(op_metrics),
                'total_duration': sum(durations),
                'average_duration': sum(durations) / len(durations),
                'min_duration': min(durations),
                'max_duration': max(durations)
            }
        
        return result


class ProfileManager:
    """Manager for code profiling operations."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize profile manager.
        
        Args:
            output_dir: Directory to save profile results
        """
        self.output_dir = output_dir or Path.cwd() / 'profiles'
        self.output_dir.mkdir(exist_ok=True)
        self._profiles: Dict[str, cProfile.Profile] = {}
        self._lock = threading.Lock()
    
    def start_profile(self, profile_name: str) -> None:
        """Start a new profiling session.
        
        Args:
            profile_name: Name of the profiling session
        """
        with self._lock:
            if profile_name in self._profiles:
                logger.warning(f"Profile {profile_name} is already running")
                return
            
            profiler = cProfile.Profile()
            profiler.enable()
            self._profiles[profile_name] = profiler
            
            logger.debug(f"Started profiling session: {profile_name}")
    
    def stop_profile(self, profile_name: str) -> Optional[str]:
        """Stop profiling session and save results.
        
        Args:
            profile_name: Name of the profiling session
            
        Returns:
            Path to saved profile file
        """
        with self._lock:
            if profile_name not in self._profiles:
                logger.warning(f"Profile {profile_name} is not running")
                return None
            
            profiler = self._profiles.pop(profile_name)
            profiler.disable()
        
        # Save profile results
        timestamp = int(time.time())
        profile_file = self.output_dir / f"{profile_name}_{timestamp}.prof"
        
        profiler.dump_stats(str(profile_file))
        logger.info(f"Saved profile results to {profile_file}")
        
        return str(profile_file)
    
    def get_profile_stats(
        self,
        profile_name: str,
        sort_by: str = 'cumulative',
        limit: int = 20
    ) -> str:
        """Get formatted statistics for a running profile.
        
        Args:
            profile_name: Name of the profiling session
            sort_by: Sort criteria for statistics
            limit: Number of entries to include
            
        Returns:
            Formatted statistics string
        """
        with self._lock:
            if profile_name not in self._profiles:
                return f"Profile {profile_name} is not running"
            
            profiler = self._profiles[profile_name]
        
        # Create string buffer for stats
        stats_buffer = io.StringIO()
        
        # Temporarily disable profiler to get stats
        profiler.disable()
        try:
            stats = pstats.Stats(profiler, stream=stats_buffer)
            stats.sort_stats(sort_by)
            stats.print_stats(limit)
        finally:
            profiler.enable()
        
        return stats_buffer.getvalue()
    
    def profile_function(
        self,
        func: Callable,
        profile_name: Optional[str] = None,
        save_results: bool = True
    ):
        """Decorator for profiling individual functions.
        
        Args:
            func: Function to profile
            profile_name: Name for the profile (defaults to function name)
            save_results: Whether to save profile results
            
        Returns:
            Decorated function
        """
        profile_name = profile_name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self.start_profile(profile_name)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                if save_results:
                    self.stop_profile(profile_name)
                else:
                    with self._lock:
                        if profile_name in self._profiles:
                            self._profiles[profile_name].disable()
                            del self._profiles[profile_name]
            
        return wrapper
    
    def cleanup_old_profiles(self, max_age_days: int = 7) -> int:
        """Clean up old profile files.
        
        Args:
            max_age_days: Maximum age of profile files to keep
            
        Returns:
            Number of files removed
        """
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        removed_count = 0
        
        for profile_file in self.output_dir.glob("*.prof"):
            try:
                if profile_file.stat().st_mtime < cutoff_time:
                    profile_file.unlink()
                    removed_count += 1
            except OSError as e:
                logger.warning(f"Failed to remove old profile file {profile_file}: {e}")
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old profile files")
        
        return removed_count


class BenchmarkRunner:
    """Runner for performance benchmarks."""
    
    def __init__(self, warmup_iterations: int = 3):
        """Initialize benchmark runner.
        
        Args:
            warmup_iterations: Number of warmup iterations before measurement
        """
        self.warmup_iterations = warmup_iterations
        self.results: List[BenchmarkResult] = []
    
    def benchmark(
        self,
        func: Callable,
        iterations: int = 100,
        name: Optional[str] = None,
        setup: Optional[Callable] = None,
        teardown: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> BenchmarkResult:
        """Benchmark a function.
        
        Args:
            func: Function to benchmark
            iterations: Number of iterations to run
            name: Name for the benchmark
            setup: Setup function to run before each iteration
            teardown: Teardown function to run after each iteration
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Benchmark result
        """
        name = name or func.__name__
        
        logger.info(f"Starting benchmark: {name} ({iterations} iterations)")
        
        # Force garbage collection before benchmark
        gc.collect()
        
        # Warmup runs
        for _ in range(self.warmup_iterations):
            if setup:
                setup()
            try:
                func(*args, **kwargs)
            finally:
                if teardown:
                    teardown()
        
        # Measurement runs
        times = []
        memory_before = psutil.Process().memory_info().rss
        
        for _ in range(iterations):
            if setup:
                setup()
            
            start_time = time.perf_counter()
            try:
                func(*args, **kwargs)
            finally:
                end_time = time.perf_counter()
                times.append(end_time - start_time)
                
                if teardown:
                    teardown()
        
        memory_after = psutil.Process().memory_info().rss
        
        # Calculate statistics
        total_time = sum(times)
        average_time = total_time / len(times)
        min_time = min(times)
        max_time = max(times)
        
        # Calculate standard deviation
        variance = sum((t - average_time) ** 2 for t in times) / len(times)
        std_deviation = variance ** 0.5
        
        ops_per_second = 1.0 / average_time if average_time > 0 else 0.0
        
        result = BenchmarkResult(
            name=name,
            iterations=iterations,
            total_time=total_time,
            average_time=average_time,
            min_time=min_time,
            max_time=max_time,
            std_deviation=std_deviation,
            ops_per_second=ops_per_second,
            memory_usage={
                'before': memory_before,
                'after': memory_after,
                'delta': memory_after - memory_before
            }
        )
        
        self.results.append(result)
        
        logger.info(
            f"Benchmark {name} completed: "
            f"{average_time:.6f}s avg, {ops_per_second:.1f} ops/sec"
        )
        
        return result
    
    def compare_functions(
        self,
        functions: List[Callable],
        iterations: int = 100,
        names: Optional[List[str]] = None,
        *args,
        **kwargs
    ) -> List[BenchmarkResult]:
        """Compare multiple functions.
        
        Args:
            functions: List of functions to compare
            iterations: Number of iterations per function
            names: Optional names for functions
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            List of benchmark results
        """
        if names is None:
            names = [f.__name__ for f in functions]
        
        results = []
        for func, name in zip(functions, names):
            result = self.benchmark(func, iterations, name, *args, **kwargs)
            results.append(result)
        
        # Sort by average time (fastest first)
        results.sort(key=lambda r: r.average_time)
        
        # Log comparison
        logger.info("Benchmark comparison results (fastest first):")
        for i, result in enumerate(results):
            logger.info(
                f"  {i+1}. {result.name}: {result.average_time:.6f}s "
                f"({result.ops_per_second:.1f} ops/sec)"
            )
        
        return results
    
    def get_results(self) -> List[BenchmarkResult]:
        """Get all benchmark results."""
        return self.results.copy()
    
    def clear_results(self) -> None:
        """Clear all benchmark results."""
        self.results.clear()


class PerformanceOptimizer:
    """Main performance optimization coordinator."""
    
    def __init__(self):
        """Initialize performance optimizer."""
        self.monitor = PerformanceMonitor()
        self.profiler = ProfileManager()
        self.benchmark_runner = BenchmarkRunner()
        self.cache_manager = get_cache_manager()
        self._optimizations_applied: List[str] = []
    
    def optimize_for_large_files(self) -> None:
        """Apply optimizations for handling large files."""
        optimizations = []
        
        # Create file processing cache
        self.cache_manager.create_cache(
            "file_processing",
            cache_type="lru",
            max_size=500
        )
        optimizations.append("file_processing_cache")
        
        # Create validation cache with TTL
        self.cache_manager.create_cache(
            "validation_results",
            cache_type="ttl",
            max_size=1000,
            default_ttl=3600  # 1 hour
        )
        optimizations.append("validation_cache")
        
        # Start background worker pool for file operations
        file_pool = get_worker_pool("file_operations", num_workers=4)
        optimizations.append("file_worker_pool")
        
        self._optimizations_applied.extend(optimizations)
        logger.info(f"Applied large file optimizations: {', '.join(optimizations)}")
    
    def optimize_for_memory(self) -> None:
        """Apply memory usage optimizations."""
        optimizations = []
        
        # Use weak reference cache for temporary objects
        self.cache_manager.create_cache(
            "temporary_objects",
            cache_type="weakref",
            max_size=200
        )
        optimizations.append("weakref_cache")
        
        # Force garbage collection
        gc.collect()
        optimizations.append("garbage_collection")
        
        # Create smaller caches
        for cache_name in ["selection_cache", "metadata_cache"]:
            cache = self.cache_manager.get_cache(cache_name)
            if cache and hasattr(cache, 'max_size') and cache.max_size > 100:
                # Reduce cache size
                cache.max_size = 100
                optimizations.append(f"reduced_{cache_name}_size")
        
        self._optimizations_applied.extend(optimizations)
        logger.info(f"Applied memory optimizations: {', '.join(optimizations)}")
    
    def optimize_for_speed(self) -> None:
        """Apply speed optimizations."""
        optimizations = []
        
        # Increase worker pool sizes
        for pool_name in ["validation", "processing", "conversion"]:
            try:
                pool = get_worker_pool(pool_name, num_workers=8, auto_start=False)
                if not pool.is_running():
                    pool.start()
                optimizations.append(f"{pool_name}_worker_pool")
            except Exception as e:
                logger.warning(f"Failed to optimize {pool_name} pool: {e}")
        
        # Create aggressive caching
        self.cache_manager.create_cache(
            "speed_cache",
            cache_type="lru",
            max_size=2000
        )
        optimizations.append("speed_cache")
        
        self._optimizations_applied.extend(optimizations)
        logger.info(f"Applied speed optimizations: {', '.join(optimizations)}")
    
    def auto_optimize(self, workload_type: str = "balanced") -> None:
        """Automatically apply optimizations based on workload type.
        
        Args:
            workload_type: Type of workload ("memory", "speed", "large_files", "balanced")
        """
        logger.info(f"Auto-optimizing for {workload_type} workload")
        
        if workload_type == "memory":
            self.optimize_for_memory()
        elif workload_type == "speed":
            self.optimize_for_speed()
        elif workload_type == "large_files":
            self.optimize_for_large_files()
        elif workload_type == "balanced":
            # Apply balanced optimizations
            self.optimize_for_large_files()
            
            # Add some speed optimizations
            self.cache_manager.create_cache(
                "balanced_cache",
                cache_type="lru",
                max_size=1000
            )
            
            # Moderate worker pools
            get_worker_pool("balanced_processing", num_workers=4)
            
            self._optimizations_applied.append("balanced_optimization")
        else:
            logger.warning(f"Unknown workload type: {workload_type}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report.
        
        Returns:
            Performance report dictionary
        """
        # Get system information
        process = psutil.Process()
        memory_info = process.memory_info()
        
        report = {
            'timestamp': time.time(),
            'system_stats': {
                'cpu_percent': psutil.cpu_percent(),
                'memory_rss': memory_info.rss,
                'memory_vms': memory_info.vms,
                'memory_percent': process.memory_percent(),
                'num_threads': process.num_threads(),
            },
            'performance_metrics': self.monitor.get_summary(),
            'cache_stats': self.cache_manager.get_stats(),
            'benchmark_results': [r.to_dict() for r in self.benchmark_runner.get_results()],
            'optimizations_applied': self._optimizations_applied.copy(),
        }
        
        # Add worker pool stats if available
        try:
            from .background_workers import _worker_pools
            report['worker_pool_stats'] = {
                name: pool.get_stats() for name, pool in _worker_pools.items()
            }
        except ImportError:
            pass
        
        return report
    
    def monitor_function(
        self,
        operation_name: Optional[str] = None,
        profile: bool = False
    ):
        """Decorator for monitoring function performance.
        
        Args:
            operation_name: Name for the operation (defaults to function name)
            profile: Whether to profile the function
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            op_name = operation_name or func.__name__
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Start profiling if requested
                if profile:
                    self.profiler.start_profile(op_name)
                
                # Monitor performance
                start_time = time.perf_counter()
                memory_before = psutil.Process().memory_info().rss
                
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    memory_after = psutil.Process().memory_info().rss
                    
                    # Record metrics
                    duration = end_time - start_time
                    memory_delta = memory_after - memory_before
                    
                    self.monitor.record_operation(
                        op_name,
                        duration,
                        memory_delta,
                        metadata={'args_count': len(args), 'kwargs_count': len(kwargs)}
                    )
                    
                    # Stop profiling if enabled
                    if profile:
                        self.profiler.stop_profile(op_name)
            
            return wrapper
        return decorator


# Global performance optimizer instance
_performance_optimizer = PerformanceOptimizer()


def get_performance_optimizer() -> PerformanceOptimizer:
    """Get global performance optimizer instance."""
    return _performance_optimizer


def monitor_performance(operation_name: Optional[str] = None, profile: bool = False):
    """Decorator for monitoring function performance."""
    return _performance_optimizer.monitor_function(operation_name, profile)