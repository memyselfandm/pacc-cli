"""Advanced caching mechanisms for performance optimization."""

import asyncio
import hashlib
import pickle
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union
import weakref
import threading
import logging

from ..core import PathNormalizer


logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Entry in a cache with metadata."""
    
    value: T
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl
    
    def touch(self) -> None:
        """Update access information."""
        self.last_accessed = time.time()
        self.access_count += 1


class CacheStats:
    """Statistics for cache performance monitoring."""
    
    def __init__(self):
        """Initialize cache statistics."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.size = 0
        self.max_size = 0
        self.total_access_time = 0.0
        self._lock = threading.Lock()
    
    def record_hit(self, access_time: float = 0.0) -> None:
        """Record cache hit."""
        with self._lock:
            self.hits += 1
            self.total_access_time += access_time
    
    def record_miss(self, access_time: float = 0.0) -> None:
        """Record cache miss."""
        with self._lock:
            self.misses += 1
            self.total_access_time += access_time
    
    def record_eviction(self) -> None:
        """Record cache eviction."""
        with self._lock:
            self.evictions += 1
    
    def update_size(self, current_size: int, max_size: int) -> None:
        """Update size information."""
        with self._lock:
            self.size = current_size
            self.max_size = max_size
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        return 1.0 - self.hit_rate
    
    @property
    def average_access_time(self) -> float:
        """Calculate average access time."""
        total_accesses = self.hits + self.misses
        return self.total_access_time / total_accesses if total_accesses > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        with self._lock:
            return {
                'hits': self.hits,
                'misses': self.misses,
                'evictions': self.evictions,
                'size': self.size,
                'max_size': self.max_size,
                'hit_rate': self.hit_rate,
                'miss_rate': self.miss_rate,
                'average_access_time': self.average_access_time,
            }


class BaseCache(ABC, Generic[T]):
    """Base class for cache implementations."""
    
    def __init__(self, max_size: int = 1000):
        """Initialize base cache.
        
        Args:
            max_size: Maximum number of entries
        """
        self.max_size = max_size
        self._data: Dict[str, CacheEntry[T]] = {}
        self._lock = threading.RLock()
        self.stats = CacheStats()
    
    @abstractmethod
    def _evict(self) -> None:
        """Evict entries according to cache policy."""
        pass
    
    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        start_time = time.time()
        
        with self._lock:
            if key in self._data:
                entry = self._data[key]
                
                # Check if expired
                if entry.is_expired:
                    del self._data[key]
                    self.stats.record_miss(time.time() - start_time)
                    return default
                
                # Update access info
                entry.touch()
                self.stats.record_hit(time.time() - start_time)
                return entry.value
            
            self.stats.record_miss(time.time() - start_time)
            return default
    
    def put(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """Put value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        with self._lock:
            current_time = time.time()
            
            # Create cache entry
            entry = CacheEntry(
                value=value,
                created_at=current_time,
                last_accessed=current_time,
                ttl=ttl
            )
            
            self._data[key] = entry
            
            # Evict if necessary
            if len(self._data) > self.max_size:
                self._evict()
            
            self.stats.update_size(len(self._data), self.max_size)
    
    def remove(self, key: str) -> bool:
        """Remove entry from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key was found and removed
        """
        with self._lock:
            if key in self._data:
                del self._data[key]
                self.stats.update_size(len(self._data), self.max_size)
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._data.clear()
            self.stats.update_size(0, self.max_size)
    
    def contains(self, key: str) -> bool:
        """Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is not expired
        """
        with self._lock:
            if key in self._data:
                entry = self._data[key]
                if entry.is_expired:
                    del self._data[key]
                    return False
                return True
            return False
    
    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._data)
    
    def keys(self) -> List[str]:
        """Get all cache keys."""
        with self._lock:
            return list(self._data.keys())
    
    def cleanup_expired(self) -> int:
        """Remove expired entries.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self._data.items():
                if entry.is_expired:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._data[key]
            
            if expired_keys:
                self.stats.update_size(len(self._data), self.max_size)
            
            return len(expired_keys)


class LRUCache(BaseCache[T]):
    """Least Recently Used cache implementation."""
    
    def __init__(self, max_size: int = 1000):
        """Initialize LRU cache."""
        super().__init__(max_size)
        self._access_order: OrderedDict[str, bool] = OrderedDict()
    
    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """Get value and update LRU order."""
        result = super().get(key, default)
        
        if result is not None:
            with self._lock:
                # Move to end (most recently used)
                if key in self._access_order:
                    self._access_order.move_to_end(key)
        
        return result
    
    def put(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """Put value and update LRU order."""
        super().put(key, value, ttl)
        
        with self._lock:
            # Update access order
            if key in self._access_order:
                self._access_order.move_to_end(key)
            else:
                self._access_order[key] = True
    
    def _evict(self) -> None:
        """Evict least recently used entries."""
        while len(self._data) > self.max_size:
            # Remove least recently used
            if self._access_order:
                lru_key = next(iter(self._access_order))
                del self._data[lru_key]
                del self._access_order[lru_key]
                self.stats.record_eviction()
            else:
                break
    
    def remove(self, key: str) -> bool:
        """Remove entry and update LRU order."""
        result = super().remove(key)
        
        if result:
            with self._lock:
                self._access_order.pop(key, None)
        
        return result
    
    def clear(self) -> None:
        """Clear cache and LRU order."""
        super().clear()
        with self._lock:
            self._access_order.clear()


class TTLCache(BaseCache[T]):
    """Time-To-Live cache implementation."""
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 3600.0):
        """Initialize TTL cache.
        
        Args:
            max_size: Maximum number of entries
            default_ttl: Default time to live in seconds
        """
        super().__init__(max_size)
        self.default_ttl = default_ttl
        self._cleanup_interval = 60.0  # Clean up expired entries every minute
        self._last_cleanup = time.time()
    
    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """Get value and perform cleanup if needed."""
        # Periodic cleanup
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            self.cleanup_expired()
            self._last_cleanup = current_time
        
        return super().get(key, default)
    
    def put(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """Put value with TTL."""
        if ttl is None:
            ttl = self.default_ttl
        
        super().put(key, value, ttl)
    
    def _evict(self) -> None:
        """Evict expired entries first, then oldest."""
        # First, remove expired entries
        expired_count = self.cleanup_expired()
        
        # If still over capacity, remove oldest entries
        if len(self._data) > self.max_size:
            # Sort by creation time and remove oldest
            sorted_items = sorted(
                self._data.items(),
                key=lambda x: x[1].created_at
            )
            
            to_remove = len(self._data) - self.max_size
            for key, _ in sorted_items[:to_remove]:
                del self._data[key]
                self.stats.record_eviction()


class WeakRefCache(BaseCache[T]):
    """Cache using weak references to prevent memory leaks."""
    
    def __init__(self, max_size: int = 1000):
        """Initialize weak reference cache."""
        super().__init__(max_size)
        self._weak_refs: Dict[str, weakref.ref] = {}
    
    def put(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """Put value with weak reference."""
        def cleanup_callback(ref):
            # Remove from cache when object is garbage collected
            with self._lock:
                if key in self._weak_refs and self._weak_refs[key] is ref:
                    del self._weak_refs[key]
                    self._data.pop(key, None)
        
        # Only cache objects that can be weakly referenced
        try:
            weak_ref = weakref.ref(value, cleanup_callback)
            super().put(key, value, ttl)
            
            with self._lock:
                self._weak_refs[key] = weak_ref
                
        except TypeError:
            # Object can't be weakly referenced, use normal caching
            super().put(key, value, ttl)
    
    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """Get value and check weak reference."""
        with self._lock:
            if key in self._weak_refs:
                weak_ref = self._weak_refs[key]
                obj = weak_ref()
                
                if obj is None:
                    # Object was garbage collected
                    del self._weak_refs[key]
                    self._data.pop(key, None)
                    return default
        
        return super().get(key, default)
    
    def _evict(self) -> None:
        """Evict entries with garbage collected objects first."""
        # Clean up garbage collected objects
        with self._lock:
            dead_keys = []
            for key, weak_ref in self._weak_refs.items():
                if weak_ref() is None:
                    dead_keys.append(key)
            
            for key in dead_keys:
                del self._weak_refs[key]
                self._data.pop(key, None)
                self.stats.record_eviction()
        
        # If still over capacity, use TTL-like eviction
        if len(self._data) > self.max_size:
            sorted_items = sorted(
                self._data.items(),
                key=lambda x: x[1].last_accessed
            )
            
            to_remove = len(self._data) - self.max_size
            for key, _ in sorted_items[:to_remove]:
                self._data.pop(key, None)
                self._weak_refs.pop(key, None)
                self.stats.record_eviction()


class AsyncCache:
    """Asynchronous cache for async operations."""
    
    def __init__(self, cache: BaseCache[T]):
        """Initialize async cache wrapper.
        
        Args:
            cache: Underlying cache implementation
        """
        self.cache = cache
        self._async_lock = asyncio.Lock()
    
    async def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """Async get operation."""
        # Cache operations are usually fast, so we run in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.cache.get, key, default)
    
    async def put(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """Async put operation."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.cache.put, key, value, ttl)
    
    async def remove(self, key: str) -> bool:
        """Async remove operation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.cache.remove, key)
    
    async def contains(self, key: str) -> bool:
        """Async contains operation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.cache.contains, key)
    
    async def clear(self) -> None:
        """Async clear operation."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.cache.clear)
    
    async def get_or_compute(
        self,
        key: str,
        compute_func: Callable[[], T],
        ttl: Optional[float] = None
    ) -> T:
        """Get value or compute if not in cache.
        
        Args:
            key: Cache key
            compute_func: Function to compute value if not cached
            ttl: Time to live for computed value
            
        Returns:
            Cached or computed value
        """
        # Check cache first
        value = await self.get(key)
        if value is not None:
            return value
        
        # Compute value
        if asyncio.iscoroutinefunction(compute_func):
            computed_value = await compute_func()
        else:
            loop = asyncio.get_event_loop()
            computed_value = await loop.run_in_executor(None, compute_func)
        
        # Cache the computed value
        await self.put(key, computed_value, ttl)
        
        return computed_value


class CacheManager:
    """Manager for multiple cache instances with different policies."""
    
    def __init__(self):
        """Initialize cache manager."""
        self._caches: Dict[str, BaseCache] = {}
        self._default_cache = LRUCache(max_size=1000)
        self._lock = threading.Lock()
    
    def create_cache(
        self,
        name: str,
        cache_type: str = "lru",
        max_size: int = 1000,
        **kwargs
    ) -> BaseCache:
        """Create and register a new cache.
        
        Args:
            name: Cache name
            cache_type: Type of cache ("lru", "ttl", "weakref")
            max_size: Maximum cache size
            **kwargs: Additional cache-specific arguments
            
        Returns:
            Created cache instance
        """
        with self._lock:
            if cache_type == "lru":
                cache = LRUCache(max_size=max_size)
            elif cache_type == "ttl":
                default_ttl = kwargs.get('default_ttl', 3600.0)
                cache = TTLCache(max_size=max_size, default_ttl=default_ttl)
            elif cache_type == "weakref":
                cache = WeakRefCache(max_size=max_size)
            else:
                raise ValueError(f"Unknown cache type: {cache_type}")
            
            self._caches[name] = cache
            logger.debug(f"Created {cache_type} cache '{name}' with max_size={max_size}")
            
            return cache
    
    def get_cache(self, name: str) -> Optional[BaseCache]:
        """Get cache by name.
        
        Args:
            name: Cache name
            
        Returns:
            Cache instance or None if not found
        """
        with self._lock:
            return self._caches.get(name)
    
    def get_or_create_cache(
        self,
        name: str,
        cache_type: str = "lru",
        **kwargs
    ) -> BaseCache:
        """Get existing cache or create new one.
        
        Args:
            name: Cache name
            cache_type: Cache type for creation
            **kwargs: Cache creation arguments
            
        Returns:
            Cache instance
        """
        cache = self.get_cache(name)
        if cache is None:
            cache = self.create_cache(name, cache_type, **kwargs)
        return cache
    
    def remove_cache(self, name: str) -> bool:
        """Remove cache by name.
        
        Args:
            name: Cache name
            
        Returns:
            True if cache was found and removed
        """
        with self._lock:
            if name in self._caches:
                del self._caches[name]
                logger.debug(f"Removed cache '{name}'")
                return True
            return False
    
    def clear_all(self) -> None:
        """Clear all caches."""
        with self._lock:
            for cache in self._caches.values():
                cache.clear()
            logger.debug("Cleared all caches")
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all caches.
        
        Returns:
            Dictionary mapping cache names to stats
        """
        with self._lock:
            stats = {}
            for name, cache in self._caches.items():
                stats[name] = cache.stats.to_dict()
            return stats
    
    def cleanup_expired(self) -> Dict[str, int]:
        """Clean up expired entries in all caches.
        
        Returns:
            Dictionary mapping cache names to cleanup counts
        """
        with self._lock:
            cleanup_counts = {}
            for name, cache in self._caches.items():
                if hasattr(cache, 'cleanup_expired'):
                    count = cache.cleanup_expired()
                    cleanup_counts[name] = count
                    if count > 0:
                        logger.debug(f"Cleaned up {count} expired entries from cache '{name}'")
            return cleanup_counts
    
    def cache(
        self,
        cache_name: str = "default",
        key_func: Optional[Callable] = None,
        ttl: Optional[float] = None
    ):
        """Decorator for caching function results.
        
        Args:
            cache_name: Name of cache to use
            key_func: Function to generate cache key
            ttl: Time to live for cached values
            
        Returns:
            Decorator function
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Get or create cache
                cache = self.get_or_create_cache(cache_name)
                
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    key_parts = [func.__name__]
                    key_parts.extend(str(arg) for arg in args)
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                    cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()
                
                # Check cache
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Compute and cache result
                result = func(*args, **kwargs)
                cache.put(cache_key, result, ttl)
                
                return result
            
            return wrapper
        return decorator
    
    def async_cache(
        self,
        cache_name: str = "default",
        key_func: Optional[Callable] = None,
        ttl: Optional[float] = None
    ):
        """Decorator for caching async function results.
        
        Args:
            cache_name: Name of cache to use
            key_func: Function to generate cache key
            ttl: Time to live for cached values
            
        Returns:
            Async decorator function
        """
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Get or create cache
                cache = self.get_or_create_cache(cache_name)
                async_cache = AsyncCache(cache)
                
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Default key generation
                    key_parts = [func.__name__]
                    key_parts.extend(str(arg) for arg in args)
                    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                    cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()
                
                # Use get_or_compute for async operations
                return await async_cache.get_or_compute(
                    cache_key,
                    lambda: func(*args, **kwargs),
                    ttl
                )
            
            return wrapper
        return decorator


# Global cache manager instance
_cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """Get global cache manager instance."""
    return _cache_manager


def cache(cache_name: str = "default", **kwargs):
    """Decorator for caching function results using global cache manager."""
    return _cache_manager.cache(cache_name, **kwargs)


def async_cache(cache_name: str = "default", **kwargs):
    """Decorator for caching async function results using global cache manager."""
    return _cache_manager.async_cache(cache_name, **kwargs)