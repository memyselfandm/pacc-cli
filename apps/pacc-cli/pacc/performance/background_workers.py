"""Background worker system for async task processing."""

import asyncio
import queue
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import concurrent.futures
import logging
import weakref

from ..errors import PACCError


logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of background tasks."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Priority levels for tasks."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class TaskResult:
    """Result of a background task."""
    
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[Exception] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Get task duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if task is completed (success or failure)."""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]


@dataclass
class Task:
    """Background task definition."""
    
    task_id: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 0
    callback: Optional[Callable[[TaskResult], None]] = None
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: 'Task') -> bool:
        """Compare tasks for priority queue ordering."""
        # Higher priority value means higher priority
        if self.priority.value != other.priority.value:
            return self.priority.value > other.priority.value
        
        # For same priority, use creation time (FIFO)
        return self.created_at < other.created_at


class TaskQueue:
    """Priority queue for background tasks."""
    
    def __init__(self, max_size: Optional[int] = None):
        """Initialize task queue.
        
        Args:
            max_size: Maximum queue size (None for unlimited)
        """
        self.max_size = max_size
        self._queue = queue.PriorityQueue(maxsize=max_size or 0)
        self._task_count = 0
        self._lock = threading.Lock()
    
    def put(self, task: Task, block: bool = True, timeout: Optional[float] = None) -> bool:
        """Add task to queue.
        
        Args:
            task: Task to add
            block: Whether to block if queue is full
            timeout: Timeout for blocking operation
            
        Returns:
            True if task was added successfully
            
        Raises:
            queue.Full: If queue is full and block=False
        """
        try:
            # Use task count as secondary sort key to maintain order
            with self._lock:
                self._task_count += 1
                priority_item = (task, self._task_count)
            
            self._queue.put(priority_item, block=block, timeout=timeout)
            logger.debug(f"Added task {task.task_id} to queue (priority: {task.priority.name})")
            return True
            
        except queue.Full:
            if not block:
                raise
            return False
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Optional[Task]:
        """Get next task from queue.
        
        Args:
            block: Whether to block if queue is empty
            timeout: Timeout for blocking operation
            
        Returns:
            Next task or None if queue is empty and block=False
            
        Raises:
            queue.Empty: If queue is empty and block=False
        """
        try:
            priority_item = self._queue.get(block=block, timeout=timeout)
            task, _ = priority_item
            logger.debug(f"Retrieved task {task.task_id} from queue")
            return task
            
        except queue.Empty:
            if not block:
                raise
            return None
    
    def task_done(self) -> None:
        """Mark task as done."""
        self._queue.task_done()
    
    def join(self) -> None:
        """Wait for all tasks to complete."""
        self._queue.join()
    
    def qsize(self) -> int:
        """Get approximate queue size."""
        return self._queue.qsize()
    
    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
    
    def full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()


class BackgroundWorker:
    """Background worker that processes tasks from a queue."""
    
    def __init__(
        self,
        worker_id: str,
        task_queue: TaskQueue,
        result_callback: Optional[Callable[[TaskResult], None]] = None
    ):
        """Initialize background worker.
        
        Args:
            worker_id: Unique worker identifier
            task_queue: Task queue to process
            result_callback: Callback for task results
        """
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.result_callback = result_callback
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._current_task: Optional[Task] = None
        self._stats = {
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_execution_time': 0.0,
            'start_time': None
        }
    
    def start(self) -> None:
        """Start the worker thread."""
        if self._running:
            logger.warning(f"Worker {self.worker_id} is already running")
            return
        
        self._stop_event.clear()
        self._running = True
        self._stats['start_time'] = time.time()
        
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        
        logger.info(f"Started background worker {self.worker_id}")
    
    def stop(self, timeout: Optional[float] = None) -> bool:
        """Stop the worker thread.
        
        Args:
            timeout: Maximum time to wait for worker to stop
            
        Returns:
            True if worker stopped successfully
        """
        if not self._running:
            return True
        
        logger.info(f"Stopping background worker {self.worker_id}")
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout)
            
            if self._thread.is_alive():
                logger.warning(f"Worker {self.worker_id} did not stop within timeout")
                return False
        
        self._running = False
        logger.info(f"Stopped background worker {self.worker_id}")
        return True
    
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
    
    def get_current_task(self) -> Optional[Task]:
        """Get currently executing task."""
        return self._current_task
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        stats = self._stats.copy()
        
        if stats['start_time']:
            stats['uptime'] = time.time() - stats['start_time']
        
        total_tasks = stats['tasks_completed'] + stats['tasks_failed']
        if total_tasks > 0:
            stats['average_execution_time'] = stats['total_execution_time'] / total_tasks
            stats['success_rate'] = stats['tasks_completed'] / total_tasks
        else:
            stats['average_execution_time'] = 0.0
            stats['success_rate'] = 0.0
        
        return stats
    
    def _worker_loop(self) -> None:
        """Main worker loop."""
        logger.debug(f"Worker {self.worker_id} started processing tasks")
        
        while not self._stop_event.is_set():
            try:
                # Get next task (with timeout to allow checking stop event)
                task = self.task_queue.get(block=True, timeout=1.0)
                
                if task is None:
                    continue
                
                # Execute task
                result = self._execute_task(task)
                
                # Mark task as done
                self.task_queue.task_done()
                
                # Call result callback
                if self.result_callback:
                    try:
                        self.result_callback(result)
                    except Exception as e:
                        logger.error(f"Result callback failed: {e}")
                
                # Call task-specific callback
                if task.callback:
                    try:
                        task.callback(result)
                    except Exception as e:
                        logger.error(f"Task callback failed: {e}")
                
            except queue.Empty:
                # Timeout waiting for task, continue to check stop event
                continue
            except Exception as e:
                logger.error(f"Unexpected error in worker {self.worker_id}: {e}")
        
        logger.debug(f"Worker {self.worker_id} stopped processing tasks")
    
    def _execute_task(self, task: Task) -> TaskResult:
        """Execute a single task.
        
        Args:
            task: Task to execute
            
        Returns:
            Task result
        """
        self._current_task = task
        start_time = time.time()
        
        result = TaskResult(
            task_id=task.task_id,
            status=TaskStatus.RUNNING,
            start_time=start_time
        )
        
        logger.debug(f"Worker {self.worker_id} executing task {task.task_id}")
        
        try:
            # Execute the task function
            if task.timeout:
                # Use timeout for task execution
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(task.func, *task.args, **task.kwargs)
                    task_result = future.result(timeout=task.timeout)
            else:
                task_result = task.func(*task.args, **task.kwargs)
            
            # Task completed successfully
            result.status = TaskStatus.COMPLETED
            result.result = task_result
            result.end_time = time.time()
            
            # Update stats
            self._stats['tasks_completed'] += 1
            self._stats['total_execution_time'] += result.duration or 0
            
            logger.debug(f"Task {task.task_id} completed successfully in {result.duration:.3f}s")
            
        except concurrent.futures.TimeoutError:
            result.status = TaskStatus.FAILED
            result.error = TimeoutError(f"Task {task.task_id} timed out after {task.timeout}s")
            result.end_time = time.time()
            
            self._stats['tasks_failed'] += 1
            logger.warning(f"Task {task.task_id} timed out")
            
        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error = e
            result.end_time = time.time()
            
            self._stats['tasks_failed'] += 1
            logger.error(f"Task {task.task_id} failed: {e}")
            
            # Handle retries
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                logger.info(f"Retrying task {task.task_id} (attempt {task.retry_count}/{task.max_retries})")
                
                # Re-queue the task
                try:
                    self.task_queue.put(task, block=False)
                except queue.Full:
                    logger.warning(f"Could not retry task {task.task_id}: queue is full")
        
        finally:
            self._current_task = None
        
        return result


class WorkerPool:
    """Pool of background workers for parallel task processing."""
    
    def __init__(
        self,
        pool_name: str,
        num_workers: int = 4,
        max_queue_size: Optional[int] = None
    ):
        """Initialize worker pool.
        
        Args:
            pool_name: Name of the worker pool
            num_workers: Number of worker threads
            max_queue_size: Maximum queue size
        """
        self.pool_name = pool_name
        self.num_workers = num_workers
        self.task_queue = TaskQueue(max_queue_size)
        self.workers: List[BackgroundWorker] = []
        self.results: Dict[str, TaskResult] = {}
        self.result_callbacks: List[Callable[[TaskResult], None]] = []
        self._lock = threading.Lock()
        self._task_counter = 0
        self._running = False
    
    def start(self) -> None:
        """Start all workers in the pool."""
        if self._running:
            logger.warning(f"Worker pool {self.pool_name} is already running")
            return
        
        logger.info(f"Starting worker pool {self.pool_name} with {self.num_workers} workers")
        
        # Create and start workers
        for i in range(self.num_workers):
            worker_id = f"{self.pool_name}-worker-{i}"
            worker = BackgroundWorker(
                worker_id=worker_id,
                task_queue=self.task_queue,
                result_callback=self._handle_result
            )
            worker.start()
            self.workers.append(worker)
        
        self._running = True
        logger.info(f"Worker pool {self.pool_name} started successfully")
    
    def stop(self, timeout: Optional[float] = None) -> bool:
        """Stop all workers in the pool.
        
        Args:
            timeout: Maximum time to wait for workers to stop
            
        Returns:
            True if all workers stopped successfully
        """
        if not self._running:
            return True
        
        logger.info(f"Stopping worker pool {self.pool_name}")
        
        # Calculate per-worker timeout
        per_worker_timeout = timeout / len(self.workers) if timeout else None
        
        # Stop all workers
        all_stopped = True
        for worker in self.workers:
            if not worker.stop(per_worker_timeout):
                all_stopped = False
        
        # Wait for queue to empty
        try:
            if timeout:
                # Use remaining time for queue join
                remaining_timeout = timeout - (per_worker_timeout or 0) * len(self.workers)
                if remaining_timeout > 0:
                    # Create a timeout wrapper for join
                    def timeout_join():
                        self.task_queue.join()
                    
                    thread = threading.Thread(target=timeout_join)
                    thread.start()
                    thread.join(remaining_timeout)
                    
                    if thread.is_alive():
                        logger.warning("Task queue did not empty within timeout")
            else:
                self.task_queue.join()
        except Exception as e:
            logger.warning(f"Error waiting for task queue to empty: {e}")
        
        self.workers.clear()
        self._running = False
        
        if all_stopped:
            logger.info(f"Worker pool {self.pool_name} stopped successfully")
        else:
            logger.warning(f"Some workers in pool {self.pool_name} did not stop cleanly")
        
        return all_stopped
    
    def submit_task(
        self,
        func: Callable,
        *args,
        task_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: Optional[float] = None,
        max_retries: int = 0,
        callback: Optional[Callable[[TaskResult], None]] = None,
        **kwargs
    ) -> str:
        """Submit a task for execution.
        
        Args:
            func: Function to execute
            *args: Function arguments
            task_id: Optional task ID (generated if None)
            priority: Task priority
            timeout: Task timeout
            max_retries: Maximum retry attempts
            callback: Task completion callback
            **kwargs: Function keyword arguments
            
        Returns:
            Task ID
        """
        if not self._running:
            raise PACCError("Worker pool is not running")
        
        # Generate task ID if not provided
        if task_id is None:
            with self._lock:
                self._task_counter += 1
                task_id = f"{self.pool_name}-task-{self._task_counter}"
        
        # Create task
        task = Task(
            task_id=task_id,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=timeout,
            max_retries=max_retries,
            callback=callback
        )
        
        # Submit to queue
        try:
            self.task_queue.put(task, block=False)
            logger.debug(f"Submitted task {task_id} to pool {self.pool_name}")
            return task_id
            
        except queue.Full:
            raise PACCError(f"Worker pool {self.pool_name} queue is full")
    
    def get_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """Get result for a specific task.
        
        Args:
            task_id: Task ID
            timeout: Maximum time to wait for result
            
        Returns:
            Task result or None if not available
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                if task_id in self.results:
                    return self.results[task_id]
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return None
            
            # Wait a bit before checking again
            time.sleep(0.1)
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for all submitted tasks to complete.
        
        Args:
            timeout: Maximum time to wait
            
        Returns:
            True if all tasks completed within timeout
        """
        try:
            if timeout:
                # Use a separate thread for join with timeout
                def join_with_timeout():
                    self.task_queue.join()
                
                thread = threading.Thread(target=join_with_timeout)
                thread.start()
                thread.join(timeout)
                
                return not thread.is_alive()
            else:
                self.task_queue.join()
                return True
                
        except Exception as e:
            logger.error(f"Error waiting for task completion: {e}")
            return False
    
    def add_result_callback(self, callback: Callable[[TaskResult], None]) -> None:
        """Add a result callback for all tasks.
        
        Args:
            callback: Callback function
        """
        self.result_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics.
        
        Returns:
            Dictionary with pool statistics
        """
        worker_stats = [worker.get_stats() for worker in self.workers]
        
        total_completed = sum(stats['tasks_completed'] for stats in worker_stats)
        total_failed = sum(stats['tasks_failed'] for stats in worker_stats)
        total_tasks = total_completed + total_failed
        
        return {
            'pool_name': self.pool_name,
            'num_workers': len(self.workers),
            'running': self._running,
            'queue_size': self.task_queue.qsize(),
            'total_tasks_completed': total_completed,
            'total_tasks_failed': total_failed,
            'total_tasks': total_tasks,
            'success_rate': total_completed / total_tasks if total_tasks > 0 else 0.0,
            'worker_stats': worker_stats,
            'results_stored': len(self.results)
        }
    
    def clear_results(self, older_than: Optional[float] = None) -> int:
        """Clear stored results.
        
        Args:
            older_than: Only clear results older than this timestamp
            
        Returns:
            Number of results cleared
        """
        with self._lock:
            if older_than is None:
                count = len(self.results)
                self.results.clear()
                return count
            else:
                to_remove = []
                for task_id, result in self.results.items():
                    if result.end_time and result.end_time < older_than:
                        to_remove.append(task_id)
                
                for task_id in to_remove:
                    del self.results[task_id]
                
                return len(to_remove)
    
    def _handle_result(self, result: TaskResult) -> None:
        """Handle task result.
        
        Args:
            result: Task result
        """
        # Store result
        with self._lock:
            self.results[result.task_id] = result
        
        # Call result callbacks
        for callback in self.result_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Result callback failed: {e}")


# Global worker pool registry
_worker_pools: Dict[str, WorkerPool] = {}
_pools_lock = threading.Lock()


def get_worker_pool(
    pool_name: str,
    num_workers: int = 4,
    max_queue_size: Optional[int] = None,
    auto_start: bool = True
) -> WorkerPool:
    """Get or create a worker pool.
    
    Args:
        pool_name: Pool name
        num_workers: Number of workers
        max_queue_size: Maximum queue size
        auto_start: Whether to auto-start the pool
        
    Returns:
        Worker pool instance
    """
    with _pools_lock:
        if pool_name not in _worker_pools:
            pool = WorkerPool(pool_name, num_workers, max_queue_size)
            _worker_pools[pool_name] = pool
            
            if auto_start:
                pool.start()
        
        return _worker_pools[pool_name]


def shutdown_all_pools(timeout: Optional[float] = None) -> None:
    """Shutdown all worker pools.
    
    Args:
        timeout: Maximum time to wait for shutdown
    """
    with _pools_lock:
        pools = list(_worker_pools.values())
        _worker_pools.clear()
    
    logger.info(f"Shutting down {len(pools)} worker pools")
    
    # Calculate per-pool timeout
    per_pool_timeout = timeout / len(pools) if timeout and pools else None
    
    for pool in pools:
        pool.stop(per_pool_timeout)
    
    logger.info("All worker pools shut down")