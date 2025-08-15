"""Persistence components for selection workflow caching and history."""

import asyncio
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
import logging

from ..core import PathNormalizer
from .types import SelectionContext, SelectionResult


logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Entry in the selection cache."""
    
    key: str
    result: SelectionResult
    timestamp: float
    context_hash: str
    ttl: Optional[float] = None  # Time to live in seconds
    access_count: int = 0
    last_access: float = 0.0
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl
    
    def touch(self) -> None:
        """Update access information."""
        self.access_count += 1
        self.last_access = time.time()


@dataclass 
class HistoryEntry:
    """Entry in the selection history."""
    
    timestamp: float
    source_paths: List[str]
    context: Dict[str, Any]
    result: Dict[str, Any]
    session_id: Optional[str] = None
    user_notes: Optional[str] = None
    
    @classmethod
    def from_selection(
        cls,
        source_paths: List[Union[str, Path]],
        context: SelectionContext,
        result: SelectionResult,
        session_id: Optional[str] = None
    ) -> 'HistoryEntry':
        """Create history entry from selection data."""
        return cls(
            timestamp=time.time(),
            source_paths=[str(p) for p in source_paths],
            context=cls._serialize_context(context),
            result=cls._serialize_result(result),
            session_id=session_id
        )
    
    @staticmethod
    def _serialize_context(context: SelectionContext) -> Dict[str, Any]:
        """Serialize selection context for storage."""
        # Convert context to dict, handling non-serializable fields
        context_dict = asdict(context)
        
        # Remove non-serializable validators
        context_dict.pop('validators', None)
        
        # Convert enums to strings
        if 'mode' in context_dict:
            context_dict['mode'] = context_dict['mode'].value
        if 'strategy' in context_dict:
            context_dict['strategy'] = context_dict['strategy'].value
        
        # Convert sets to lists
        if 'extensions' in context_dict and context_dict['extensions']:
            context_dict['extensions'] = list(context_dict['extensions'])
        
        return context_dict
    
    @staticmethod
    def _serialize_result(result: SelectionResult) -> Dict[str, Any]:
        """Serialize selection result for storage."""
        # Convert result to dict, handling Path objects
        result_dict = asdict(result)
        
        # Convert Path objects to strings
        if 'selected_files' in result_dict:
            result_dict['selected_files'] = [str(p) for p in result_dict['selected_files']]
        
        # Simplify validation results for storage
        if 'validation_results' in result_dict:
            simplified_results = []
            for vr in result_dict['validation_results']:
                simplified = {
                    'is_valid': vr.get('is_valid', False),
                    'error_count': len(vr.get('errors', [])),
                    'warning_count': len(vr.get('warnings', [])),
                    'file_path': vr.get('file_path'),
                    'extension_type': vr.get('extension_type')
                }
                simplified_results.append(simplified)
            result_dict['validation_results'] = simplified_results
        
        # Convert exceptions to strings
        if 'errors' in result_dict:
            result_dict['errors'] = [str(e) for e in result_dict['errors']]
        
        return result_dict


class SelectionCache:
    """Cache for selection results to improve performance."""
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_entries: int = 1000,
        default_ttl: Optional[float] = 3600  # 1 hour
    ):
        """Initialize selection cache.
        
        Args:
            cache_dir: Directory to store cache files
            max_entries: Maximum number of cache entries
            default_ttl: Default time-to-live for cache entries in seconds
        """
        self.cache_dir = cache_dir or Path.home() / '.claude' / 'pacc' / 'cache'
        self.max_entries = max_entries
        self.default_ttl = default_ttl
        
        # In-memory cache for fast access
        self._memory_cache: Dict[str, CacheEntry] = {}
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing cache
        asyncio.create_task(self._load_cache())
    
    def generate_key(
        self,
        source_paths: List[Union[str, Path]],
        context: SelectionContext
    ) -> str:
        """Generate cache key for selection parameters.
        
        Args:
            source_paths: Source paths for selection
            context: Selection context
            
        Returns:
            Cache key string
        """
        # Normalize paths for consistent keys
        normalized_paths = [
            PathNormalizer.to_posix(path) for path in source_paths
        ]
        normalized_paths.sort()  # Ensure consistent ordering
        
        # Create context hash (excluding non-deterministic fields)
        context_data = {
            'mode': context.mode.value,
            'strategy': context.strategy.value,
            'extensions': sorted(context.extensions) if context.extensions else None,
            'patterns': sorted(context.patterns) if context.patterns else None,
            'size_limits': context.size_limits,
            'exclude_hidden': context.exclude_hidden,
            'max_selections': context.max_selections,
        }
        
        # Combine paths and context for hashing
        key_data = {
            'paths': normalized_paths,
            'context': context_data,
            'version': '1.0'  # Cache version for invalidation
        }
        
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_json.encode()).hexdigest()[:16]
    
    async def get(self, key: str) -> Optional[SelectionResult]:
        """Get cached selection result.
        
        Args:
            key: Cache key
            
        Returns:
            Cached selection result or None if not found/expired
        """
        # Check memory cache first
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            
            if entry.is_expired:
                await self._remove_entry(key)
                return None
            
            entry.touch()
            logger.debug(f"Cache hit for key {key}")
            return entry.result
        
        # Check disk cache
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                entry = self._deserialize_entry(data)
                if entry and not entry.is_expired:
                    entry.touch()
                    self._memory_cache[key] = entry
                    logger.debug(f"Cache hit from disk for key {key}")
                    return entry.result
                else:
                    # Remove expired entry
                    cache_file.unlink(missing_ok=True)
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to load cache entry {key}: {e}")
                cache_file.unlink(missing_ok=True)
        
        logger.debug(f"Cache miss for key {key}")
        return None
    
    async def set(
        self,
        key: str,
        result: SelectionResult,
        ttl: Optional[float] = None
    ) -> None:
        """Store selection result in cache.
        
        Args:
            key: Cache key
            result: Selection result to cache
            ttl: Time-to-live override
        """
        # Don't cache results with errors or user cancellations
        if not result.success or result.user_cancelled:
            logger.debug(f"Not caching failed/cancelled result for key {key}")
            return
        
        # Create cache entry
        entry = CacheEntry(
            key=key,
            result=result,
            timestamp=time.time(),
            context_hash=key,  # Using key as context hash for simplicity
            ttl=ttl or self.default_ttl
        )
        
        # Store in memory cache
        self._memory_cache[key] = entry
        
        # Store to disk asynchronously
        asyncio.create_task(self._write_cache_entry(key, entry))
        
        # Cleanup if we exceed max entries
        if len(self._memory_cache) > self.max_entries:
            await self._cleanup_cache()
        
        logger.debug(f"Cached result for key {key}")
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        self._memory_cache.clear()
        
        # Remove cache files
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink(missing_ok=True)
        
        logger.info("Cache cleared")
    
    async def cleanup_expired(self) -> int:
        """Remove expired cache entries.
        
        Returns:
            Number of entries removed
        """
        removed_count = 0
        expired_keys = []
        
        # Find expired entries in memory
        for key, entry in self._memory_cache.items():
            if entry.is_expired:
                expired_keys.append(key)
        
        # Remove expired entries
        for key in expired_keys:
            await self._remove_entry(key)
            removed_count += 1
        
        # Check disk cache for expired entries
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                entry = self._deserialize_entry(data)
                if entry and entry.is_expired:
                    cache_file.unlink(missing_ok=True)
                    removed_count += 1
                    
            except (json.JSONDecodeError, KeyError, ValueError):
                # Remove corrupted files
                cache_file.unlink(missing_ok=True)
                removed_count += 1
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} expired cache entries")
        
        return removed_count
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        memory_entries = len(self._memory_cache)
        disk_entries = len(list(self.cache_dir.glob("*.json")))
        
        total_access_count = sum(entry.access_count for entry in self._memory_cache.values())
        total_size = sum(
            f.stat().st_size for f in self.cache_dir.glob("*.json") if f.exists()
        )
        
        return {
            'memory_entries': memory_entries,
            'disk_entries': disk_entries,
            'total_access_count': total_access_count,
            'total_size_bytes': total_size,
            'cache_dir': str(self.cache_dir),
            'max_entries': self.max_entries,
            'default_ttl': self.default_ttl,
        }
    
    async def _load_cache(self) -> None:
        """Load cache entries from disk."""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                    
                    entry = self._deserialize_entry(data)
                    if entry and not entry.is_expired:
                        key = cache_file.stem
                        self._memory_cache[key] = entry
                    else:
                        # Remove expired entry
                        cache_file.unlink(missing_ok=True)
                        
                except (json.JSONDecodeError, KeyError, ValueError):
                    # Remove corrupted files
                    cache_file.unlink(missing_ok=True)
                    
            logger.debug(f"Loaded {len(self._memory_cache)} cache entries")
            
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
    
    async def _write_cache_entry(self, key: str, entry: CacheEntry) -> None:
        """Write cache entry to disk."""
        try:
            cache_file = self.cache_dir / f"{key}.json"
            data = self._serialize_entry(entry)
            
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to write cache entry {key}: {e}")
    
    async def _remove_entry(self, key: str) -> None:
        """Remove cache entry from memory and disk."""
        # Remove from memory
        self._memory_cache.pop(key, None)
        
        # Remove from disk
        cache_file = self.cache_dir / f"{key}.json"
        cache_file.unlink(missing_ok=True)
    
    async def _cleanup_cache(self) -> None:
        """Clean up cache when it exceeds max entries."""
        if len(self._memory_cache) <= self.max_entries:
            return
        
        # Sort entries by last access time (LRU)
        sorted_entries = sorted(
            self._memory_cache.items(),
            key=lambda x: x[1].last_access or x[1].timestamp
        )
        
        # Remove oldest entries
        entries_to_remove = len(self._memory_cache) - self.max_entries + 10
        for key, _ in sorted_entries[:entries_to_remove]:
            await self._remove_entry(key)
        
        logger.debug(f"Cleaned up {entries_to_remove} cache entries")
    
    def _serialize_entry(self, entry: CacheEntry) -> Dict[str, Any]:
        """Serialize cache entry for storage."""
        return {
            'key': entry.key,
            'timestamp': entry.timestamp,
            'context_hash': entry.context_hash,
            'ttl': entry.ttl,
            'access_count': entry.access_count,
            'last_access': entry.last_access,
            'result': {
                'success': entry.result.success,
                'selected_files': [str(p) for p in entry.result.selected_files],
                'metadata': entry.result.metadata,
                'warnings': entry.result.warnings,
                'user_cancelled': entry.result.user_cancelled,
                'cached_result': entry.result.cached_result,
                # Skip validation_results and errors for cache storage
            }
        }
    
    def _deserialize_entry(self, data: Dict[str, Any]) -> Optional[CacheEntry]:
        """Deserialize cache entry from storage."""
        try:
            result_data = data['result']
            result = SelectionResult(
                success=result_data['success'],
                selected_files=[Path(p) for p in result_data['selected_files']],
                metadata=result_data.get('metadata', {}),
                warnings=result_data.get('warnings', []),
                user_cancelled=result_data.get('user_cancelled', False),
                cached_result=result_data.get('cached_result', False),
            )
            
            return CacheEntry(
                key=data['key'],
                result=result,
                timestamp=data['timestamp'],
                context_hash=data['context_hash'],
                ttl=data.get('ttl'),
                access_count=data.get('access_count', 0),
                last_access=data.get('last_access', 0.0),
            )
            
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to deserialize cache entry: {e}")
            return None


class SelectionHistory:
    """History tracker for selection operations."""
    
    def __init__(
        self,
        history_dir: Optional[Path] = None,
        max_entries: int = 10000
    ):
        """Initialize selection history.
        
        Args:
            history_dir: Directory to store history files
            max_entries: Maximum number of history entries
        """
        self.history_dir = history_dir or Path.home() / '.claude' / 'pacc' / 'history'
        self.max_entries = max_entries
        
        # Ensure history directory exists
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        # History file (JSON lines format)
        self.history_file = self.history_dir / 'selections.jsonl'
    
    async def add_selection(
        self,
        source_paths: List[Union[str, Path]],
        context: SelectionContext,
        result: SelectionResult,
        session_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> None:
        """Add selection to history.
        
        Args:
            source_paths: Source paths that were selected from
            context: Selection context
            result: Selection result
            session_id: Optional session identifier
            notes: Optional user notes
        """
        entry = HistoryEntry.from_selection(source_paths, context, result, session_id)
        entry.user_notes = notes
        
        # Append to history file
        try:
            with open(self.history_file, 'a') as f:
                json.dump(asdict(entry), f)
                f.write('\\n')
            
            logger.debug(f"Added selection to history: {len(result.selected_files)} files")
            
        except Exception as e:
            logger.error(f"Failed to write history entry: {e}")
        
        # Clean up if we exceed max entries
        await self._cleanup_history()
    
    async def get_recent_selections(
        self,
        limit: int = 10,
        session_id: Optional[str] = None
    ) -> List[HistoryEntry]:
        """Get recent selection history entries.
        
        Args:
            limit: Maximum number of entries to return
            session_id: Filter by session ID if provided
            
        Returns:
            List of recent history entries
        """
        entries = []
        
        if not self.history_file.exists():
            return entries
        
        try:
            # Read entries in reverse order (most recent first)
            with open(self.history_file, 'r') as f:
                lines = f.readlines()
            
            for line in reversed(lines):
                if len(entries) >= limit:
                    break
                
                try:
                    data = json.loads(line.strip())
                    entry = HistoryEntry(**data)
                    
                    # Filter by session ID if provided
                    if session_id is None or entry.session_id == session_id:
                        entries.append(entry)
                        
                except (json.JSONDecodeError, TypeError):
                    continue
            
        except Exception as e:
            logger.error(f"Failed to read history: {e}")
        
        return entries
    
    async def search_history(
        self,
        query: str,
        limit: int = 50
    ) -> List[HistoryEntry]:
        """Search history entries.
        
        Args:
            query: Search query (matches paths and notes)
            limit: Maximum number of results
            
        Returns:
            List of matching history entries
        """
        entries = []
        query_lower = query.lower()
        
        if not self.history_file.exists():
            return entries
        
        try:
            with open(self.history_file, 'r') as f:
                for line in f:
                    if len(entries) >= limit:
                        break
                    
                    try:
                        data = json.loads(line.strip())
                        entry = HistoryEntry(**data)
                        
                        # Search in paths and notes
                        searchable_text = ' '.join(entry.source_paths)
                        if entry.user_notes:
                            searchable_text += ' ' + entry.user_notes
                        
                        if query_lower in searchable_text.lower():
                            entries.append(entry)
                            
                    except (json.JSONDecodeError, TypeError):
                        continue
                        
        except Exception as e:
            logger.error(f"Failed to search history: {e}")
        
        # Return most recent matches first
        return list(reversed(entries))
    
    async def clear_history(self, before_timestamp: Optional[float] = None) -> int:
        """Clear history entries.
        
        Args:
            before_timestamp: Only clear entries before this timestamp
            
        Returns:
            Number of entries removed
        """
        if not self.history_file.exists():
            return 0
        
        removed_count = 0
        
        if before_timestamp is None:
            # Clear all history
            self.history_file.unlink()
            return -1  # Unknown count
        
        try:
            # Read existing entries
            entries = []
            with open(self.history_file, 'r') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        entry = HistoryEntry(**data)
                        
                        if entry.timestamp >= before_timestamp:
                            entries.append(entry)
                        else:
                            removed_count += 1
                            
                    except (json.JSONDecodeError, TypeError):
                        removed_count += 1  # Count corrupted entries as removed
            
            # Write back remaining entries
            with open(self.history_file, 'w') as f:
                for entry in entries:
                    json.dump(asdict(entry), f)
                    f.write('\\n')
            
            logger.info(f"Cleared {removed_count} history entries")
            
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
        
        return removed_count
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get history statistics.
        
        Returns:
            Dictionary with history statistics
        """
        total_entries = 0
        oldest_timestamp = None
        newest_timestamp = None
        file_size = 0
        
        if self.history_file.exists():
            try:
                file_size = self.history_file.stat().st_size
                
                with open(self.history_file, 'r') as f:
                    for line in f:
                        try:
                            data = json.loads(line.strip())
                            total_entries += 1
                            
                            timestamp = data.get('timestamp', 0)
                            if oldest_timestamp is None or timestamp < oldest_timestamp:
                                oldest_timestamp = timestamp
                            if newest_timestamp is None or timestamp > newest_timestamp:
                                newest_timestamp = timestamp
                                
                        except (json.JSONDecodeError, TypeError):
                            continue
                            
            except Exception as e:
                logger.error(f"Failed to get history stats: {e}")
        
        return {
            'total_entries': total_entries,
            'oldest_timestamp': oldest_timestamp,
            'newest_timestamp': newest_timestamp,
            'file_size_bytes': file_size,
            'history_file': str(self.history_file),
            'max_entries': self.max_entries,
        }
    
    async def _cleanup_history(self) -> None:
        """Clean up history when it exceeds max entries."""
        if not self.history_file.exists():
            return
        
        try:
            # Count current entries
            entry_count = 0
            with open(self.history_file, 'r') as f:
                for _ in f:
                    entry_count += 1
            
            if entry_count <= self.max_entries:
                return
            
            # Keep only the most recent entries
            entries_to_keep = []
            with open(self.history_file, 'r') as f:
                lines = f.readlines()
            
            # Keep the last max_entries lines
            keep_count = min(self.max_entries, len(lines))
            entries_to_keep = lines[-keep_count:]
            
            # Write back the kept entries
            with open(self.history_file, 'w') as f:
                f.writelines(entries_to_keep)
            
            removed_count = entry_count - keep_count
            logger.debug(f"Cleaned up {removed_count} old history entries")
            
        except Exception as e:
            logger.error(f"Failed to cleanup history: {e}")