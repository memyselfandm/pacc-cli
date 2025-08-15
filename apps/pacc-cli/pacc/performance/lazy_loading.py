"""Lazy loading mechanisms for deferred computation and file operations."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, TypeVar, Union, Generic, Awaitable
import threading
import weakref
import logging

from ..core import DirectoryScanner, FileFilter, FilePathValidator


logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class LazyLoadConfig:
    """Configuration for lazy loading behavior."""
    
    batch_size: int = 100
    max_concurrent: int = 5
    timeout: Optional[float] = None
    prefetch_count: int = 10
    cache_results: bool = True
    background_loading: bool = True


class LazyLoadResult(Generic[T]):
    """Result of a lazy loading operation."""
    
    def __init__(
        self,
        loader_func: Callable[[], T],
        config: Optional[LazyLoadConfig] = None
    ):
        """Initialize lazy load result.
        
        Args:
            loader_func: Function to load the actual value
            config: Lazy loading configuration
        """
        self._loader_func = loader_func
        self._config = config or LazyLoadConfig()
        self._value: Optional[T] = None
        self._loaded = False
        self._loading = False
        self._error: Optional[Exception] = None
        self._lock = threading.Lock()
        self._load_event = threading.Event()
    
    @property
    def is_loaded(self) -> bool:
        """Check if value has been loaded."""
        return self._loaded
    
    @property
    def is_loading(self) -> bool:
        """Check if value is currently being loaded."""
        return self._loading
    
    @property
    def has_error(self) -> bool:
        """Check if loading resulted in an error."""
        return self._error is not None
    
    @property
    def error(self) -> Optional[Exception]:
        """Get loading error if any."""
        return self._error
    
    def get(self, timeout: Optional[float] = None) -> T:
        """Get the loaded value.
        
        Args:
            timeout: Maximum time to wait for loading
            
        Returns:
            Loaded value
            
        Raises:
            Exception: If loading failed
            TimeoutError: If loading timed out
        """
        # Check if already loaded
        if self._loaded:
            if self._error:
                raise self._error
            return self._value
        
        # Check if currently loading
        if self._loading:
            # Wait for loading to complete
            wait_timeout = timeout or self._config.timeout
            if self._load_event.wait(wait_timeout):
                if self._error:
                    raise self._error
                return self._value
            else:
                raise TimeoutError("Lazy loading timed out")
        
        # Load the value
        with self._lock:
            # Double-check after acquiring lock
            if self._loaded:
                if self._error:
                    raise self._error
                return self._value
            
            if self._loading:
                # Another thread is loading, wait for it
                self._lock.release()
                try:
                    wait_timeout = timeout or self._config.timeout
                    if self._load_event.wait(wait_timeout):
                        if self._error:
                            raise self._error
                        return self._value
                    else:
                        raise TimeoutError("Lazy loading timed out")
                finally:
                    self._lock.acquire()
            
            # Start loading
            self._loading = True
            
            try:
                logger.debug("Starting lazy loading")
                self._value = self._loader_func()
                self._loaded = True
                logger.debug("Lazy loading completed successfully")
                
            except Exception as e:
                self._error = e
                logger.error(f"Lazy loading failed: {e}")
                
            finally:
                self._loading = False
                self._load_event.set()
        
        if self._error:
            raise self._error
        
        return self._value
    
    def get_async(self) -> T:
        """Get value with potential async execution."""
        if asyncio.iscoroutinefunction(self._loader_func):
            # For async functions, we need to handle differently
            raise NotImplementedError("Use AsyncLazyLoader for async functions")
        
        return self.get()
    
    def invalidate(self) -> None:
        """Invalidate loaded value and reset state."""
        with self._lock:
            self._value = None
            self._loaded = False
            self._loading = False
            self._error = None
            self._load_event.clear()
        
        logger.debug("Lazy load result invalidated")


class LazyLoader:
    """Synchronous lazy loader for deferred computation."""
    
    def __init__(self, config: Optional[LazyLoadConfig] = None):
        """Initialize lazy loader.
        
        Args:
            config: Lazy loading configuration
        """
        self.config = config or LazyLoadConfig()
        self._cache: Dict[str, LazyLoadResult] = {}
        self._lock = threading.Lock()
    
    def create(
        self,
        loader_func: Callable[[], T],
        cache_key: Optional[str] = None
    ) -> LazyLoadResult[T]:
        """Create a lazy load result.
        
        Args:
            loader_func: Function to load the value
            cache_key: Optional key for caching the result
            
        Returns:
            Lazy load result
        """
        if cache_key and self.config.cache_results:
            with self._lock:
                if cache_key in self._cache:
                    return self._cache[cache_key]
                
                result = LazyLoadResult(loader_func, self.config)
                self._cache[cache_key] = result
                return result
        else:
            return LazyLoadResult(loader_func, self.config)
    
    def load_file(self, file_path: Union[str, Path]) -> LazyLoadResult[bytes]:
        """Create lazy loader for file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            Lazy load result for file content
        """
        path_obj = Path(file_path)
        cache_key = f"file:{path_obj.resolve()}" if self.config.cache_results else None
        
        def load_file_content() -> bytes:
            with open(path_obj, 'rb') as f:
                return f.read()
        
        return self.create(load_file_content, cache_key)
    
    def load_file_text(
        self,
        file_path: Union[str, Path],
        encoding: str = 'utf-8'
    ) -> LazyLoadResult[str]:
        """Create lazy loader for text file content.
        
        Args:
            file_path: Path to file
            encoding: Text encoding
            
        Returns:
            Lazy load result for text content
        """
        path_obj = Path(file_path)
        cache_key = f"text:{path_obj.resolve()}:{encoding}" if self.config.cache_results else None
        
        def load_text_content() -> str:
            with open(path_obj, 'r', encoding=encoding) as f:
                return f.read()
        
        return self.create(load_text_content, cache_key)
    
    def load_json(self, file_path: Union[str, Path]) -> LazyLoadResult[Any]:
        """Create lazy loader for JSON file.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Lazy load result for parsed JSON
        """
        import json
        
        path_obj = Path(file_path)
        cache_key = f"json:{path_obj.resolve()}" if self.config.cache_results else None
        
        def load_json_content() -> Any:
            with open(path_obj, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return self.create(load_json_content, cache_key)
    
    def compute(self, func: Callable[[], T], cache_key: Optional[str] = None) -> LazyLoadResult[T]:
        """Create lazy loader for computed value.
        
        Args:
            func: Function to compute value
            cache_key: Optional cache key
            
        Returns:
            Lazy load result for computed value
        """
        return self.create(func, cache_key)
    
    def clear_cache(self) -> None:
        """Clear all cached lazy load results."""
        with self._lock:
            self._cache.clear()
        logger.debug("Cleared lazy loader cache")
    
    def invalidate(self, cache_key: str) -> bool:
        """Invalidate specific cached result.
        
        Args:
            cache_key: Cache key to invalidate
            
        Returns:
            True if key was found and invalidated
        """
        with self._lock:
            if cache_key in self._cache:
                self._cache[cache_key].invalidate()
                del self._cache[cache_key]
                return True
            return False


class AsyncLazyLoader:
    """Asynchronous lazy loader for async operations."""
    
    def __init__(self, config: Optional[LazyLoadConfig] = None):
        """Initialize async lazy loader.
        
        Args:
            config: Lazy loading configuration
        """
        self.config = config or LazyLoadConfig()
        self._cache: Dict[str, asyncio.Future] = {}
        self._cache_lock = asyncio.Lock()
    
    async def create(
        self,
        loader_func: Callable[[], Union[T, Awaitable[T]]],
        cache_key: Optional[str] = None
    ) -> T:
        """Create async lazy load operation.
        
        Args:
            loader_func: Async function to load value
            cache_key: Optional cache key
            
        Returns:
            Loaded value
        """
        if cache_key and self.config.cache_results:
            async with self._cache_lock:
                if cache_key in self._cache:
                    return await self._cache[cache_key]
                
                # Create future for this computation
                future = asyncio.create_task(self._execute_loader(loader_func))
                self._cache[cache_key] = future
                return await future
        else:
            return await self._execute_loader(loader_func)
    
    async def _execute_loader(self, loader_func: Callable) -> T:
        """Execute loader function with timeout and error handling."""
        try:
            if asyncio.iscoroutinefunction(loader_func):
                if self.config.timeout:
                    return await asyncio.wait_for(loader_func(), self.config.timeout)
                else:
                    return await loader_func()
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                if self.config.timeout:
                    return await asyncio.wait_for(
                        loop.run_in_executor(None, loader_func),
                        self.config.timeout
                    )
                else:
                    return await loop.run_in_executor(None, loader_func)
                    
        except Exception as e:
            logger.error(f"Async lazy loading failed: {e}")
            raise
    
    async def load_file(self, file_path: Union[str, Path]) -> bytes:
        """Async load file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            File content as bytes
        """
        path_obj = Path(file_path)
        cache_key = f"file:{path_obj.resolve()}" if self.config.cache_results else None
        
        async def load_file_content() -> bytes:
            loop = asyncio.get_event_loop()
            with open(path_obj, 'rb') as f:
                return await loop.run_in_executor(None, f.read)
        
        return await self.create(load_file_content, cache_key)
    
    async def load_file_text(
        self,
        file_path: Union[str, Path],
        encoding: str = 'utf-8'
    ) -> str:
        """Async load text file content.
        
        Args:
            file_path: Path to file
            encoding: Text encoding
            
        Returns:
            Text content
        """
        path_obj = Path(file_path)
        cache_key = f"text:{path_obj.resolve()}:{encoding}" if self.config.cache_results else None
        
        async def load_text_content() -> str:
            loop = asyncio.get_event_loop()
            with open(path_obj, 'r', encoding=encoding) as f:
                return await loop.run_in_executor(None, f.read)
        
        return await self.create(load_text_content, cache_key)
    
    async def compute(
        self,
        func: Callable[[], Union[T, Awaitable[T]]],
        cache_key: Optional[str] = None
    ) -> T:
        """Async compute value.
        
        Args:
            func: Function or coroutine to compute value
            cache_key: Optional cache key
            
        Returns:
            Computed value
        """
        return await self.create(func, cache_key)
    
    async def clear_cache(self) -> None:
        """Clear all cached futures."""
        async with self._cache_lock:
            # Cancel all pending futures
            for future in self._cache.values():
                if not future.done():
                    future.cancel()
            
            self._cache.clear()
        
        logger.debug("Cleared async lazy loader cache")


class LazyIterator(Generic[T]):
    """Iterator that loads items lazily."""
    
    def __init__(
        self,
        items: List[Union[T, Callable[[], T]]],
        config: Optional[LazyLoadConfig] = None
    ):
        """Initialize lazy iterator.
        
        Args:
            items: List of items or loader functions
            config: Lazy loading configuration
        """
        self.items = items
        self.config = config or LazyLoadConfig()
        self._index = 0
        self._cache: Dict[int, T] = {}
        self._prefetch_task: Optional[asyncio.Task] = None
    
    def __iter__(self) -> Iterator[T]:
        """Return iterator."""
        return self
    
    def __next__(self) -> T:
        """Get next item."""
        if self._index >= len(self.items):
            raise StopIteration
        
        item = self._get_item(self._index)
        self._index += 1
        
        # Start prefetching if enabled
        if self.config.background_loading and self.config.prefetch_count > 0:
            self._start_prefetch()
        
        return item
    
    def __len__(self) -> int:
        """Get number of items."""
        return len(self.items)
    
    def _get_item(self, index: int) -> T:
        """Get item at index, loading if necessary."""
        if index in self._cache:
            return self._cache[index]
        
        item_or_loader = self.items[index]
        
        if callable(item_or_loader):
            # Item is a loader function
            try:
                loaded_item = item_or_loader()
                if self.config.cache_results:
                    self._cache[index] = loaded_item
                return loaded_item
            except Exception as e:
                logger.error(f"Failed to load item at index {index}: {e}")
                raise
        else:
            # Item is already loaded
            if self.config.cache_results:
                self._cache[index] = item_or_loader
            return item_or_loader
    
    def _start_prefetch(self) -> None:
        """Start prefetching next items in background."""
        if self._prefetch_task and not self._prefetch_task.done():
            return  # Already prefetching
        
        try:
            loop = asyncio.get_event_loop()
            self._prefetch_task = loop.create_task(self._prefetch_items())
        except RuntimeError:
            # No event loop, skip prefetching
            pass
    
    async def _prefetch_items(self) -> None:
        """Prefetch next items."""
        start_index = self._index
        end_index = min(start_index + self.config.prefetch_count, len(self.items))
        
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def prefetch_single(index: int) -> None:
            async with semaphore:
                if index not in self._cache:
                    try:
                        loop = asyncio.get_event_loop()
                        item = await loop.run_in_executor(None, self._get_item, index)
                        logger.debug(f"Prefetched item at index {index}")
                    except Exception as e:
                        logger.warning(f"Failed to prefetch item at index {index}: {e}")
        
        # Create prefetch tasks
        tasks = [prefetch_single(i) for i in range(start_index, end_index)]
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def peek(self, index: Optional[int] = None) -> T:
        """Peek at item without advancing iterator.
        
        Args:
            index: Index to peek at (default: current position)
            
        Returns:
            Item at index
        """
        peek_index = index if index is not None else self._index
        
        if peek_index >= len(self.items):
            raise IndexError("Index out of range")
        
        return self._get_item(peek_index)
    
    def skip(self, count: int = 1) -> None:
        """Skip ahead by count items.
        
        Args:
            count: Number of items to skip
        """
        self._index = min(self._index + count, len(self.items))
    
    def reset(self) -> None:
        """Reset iterator to beginning."""
        self._index = 0
        
        # Cancel prefetch task if running
        if self._prefetch_task and not self._prefetch_task.done():
            self._prefetch_task.cancel()


class LazyFileScanner:
    """Lazy file scanner that discovers files on-demand."""
    
    def __init__(
        self,
        scanner: Optional[DirectoryScanner] = None,
        config: Optional[LazyLoadConfig] = None
    ):
        """Initialize lazy file scanner.
        
        Args:
            scanner: Directory scanner to use
            config: Lazy loading configuration
        """
        self.scanner = scanner or DirectoryScanner()
        self.config = config or LazyLoadConfig()
        self._cached_scans: Dict[str, List[Path]] = {}
        self._lock = threading.Lock()
    
    def scan_lazy(
        self,
        directory: Union[str, Path],
        recursive: bool = True,
        file_filter: Optional[FileFilter] = None
    ) -> LazyIterator[Path]:
        """Create lazy iterator for directory scanning.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan recursively
            file_filter: Optional file filter
            
        Returns:
            Lazy iterator of file paths
        """
        dir_path = Path(directory)
        cache_key = f"{dir_path.resolve()}:{recursive}:{id(file_filter)}"
        
        # Check if we have cached results
        with self._lock:
            if cache_key in self._cached_scans:
                cached_files = self._cached_scans[cache_key]
                return LazyIterator([lambda f=f: f for f in cached_files], self.config)
        
        # Create lazy loaders for batched scanning
        def create_batch_loader(batch_start: int, batch_size: int) -> Callable[[], List[Path]]:
            def load_batch() -> List[Path]:
                logger.debug(f"Loading file batch {batch_start}-{batch_start + batch_size}")
                
                # Get all files (cached if available)
                with self._lock:
                    if cache_key in self._cached_scans:
                        all_files = self._cached_scans[cache_key]
                    else:
                        all_files = list(self.scanner.scan_directory(dir_path, recursive))
                        
                        if file_filter:
                            all_files = file_filter.filter_files(all_files)
                        
                        if self.config.cache_results:
                            self._cached_scans[cache_key] = all_files
                
                # Return batch
                batch_end = min(batch_start + batch_size, len(all_files))
                return all_files[batch_start:batch_end]
            
            return load_batch
        
        # First, do a quick scan to get total count
        try:
            # Quick scan to estimate file count
            sample_files = list(self.scanner.scan_directory(dir_path, recursive=False))
            if file_filter:
                sample_files = file_filter.filter_files(sample_files)
            
            # Estimate total based on sample
            if recursive and dir_path.is_dir():
                # Rough estimate: multiply by subdirectory count
                subdirs = sum(1 for p in dir_path.iterdir() if p.is_dir())
                estimated_total = len(sample_files) * max(1, subdirs)
            else:
                estimated_total = len(sample_files)
            
            # Create batch loaders
            batch_loaders = []
            for start in range(0, estimated_total, self.config.batch_size):
                loader = create_batch_loader(start, self.config.batch_size)
                batch_loaders.append(loader)
            
            return LazyIterator(batch_loaders, self.config)
            
        except Exception as e:
            logger.error(f"Failed to create lazy file scanner: {e}")
            # Fallback to immediate scanning
            files = list(self.scanner.scan_directory(dir_path, recursive))
            if file_filter:
                files = file_filter.filter_files(files)
            
            return LazyIterator(files, self.config)
    
    def find_files_lazy(
        self,
        directory: Union[str, Path],
        pattern: str,
        recursive: bool = True
    ) -> LazyIterator[Path]:
        """Create lazy iterator for finding files by pattern.
        
        Args:
            directory: Directory to search
            pattern: File pattern to match
            recursive: Whether to search recursively
            
        Returns:
            Lazy iterator of matching file paths
        """
        import fnmatch
        
        file_filter = FileFilter()
        file_filter.add_pattern_filter([pattern])
        
        return self.scan_lazy(directory, recursive, file_filter)
    
    def clear_cache(self) -> None:
        """Clear cached scan results."""
        with self._lock:
            self._cached_scans.clear()
        logger.debug("Cleared lazy file scanner cache")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_files = sum(len(files) for files in self._cached_scans.values())
            return {
                'cached_scans': len(self._cached_scans),
                'total_cached_files': total_files
            }