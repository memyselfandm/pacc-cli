"""Marketplace integration foundation for PACC plugin ecosystem.

This module provides the foundation for integrating with plugin marketplaces,
including registry API clients, metadata caching, dependency resolution,
and support for both public and private registries.
"""

import json
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Union, NamedTuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from urllib.parse import urljoin, urlparse
import re


class RegistryType(Enum):
    """Types of plugin registries."""
    PUBLIC = "public"
    PRIVATE = "private"
    LOCAL = "local"


class PluginStatus(Enum):
    """Plugin status in marketplace."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    BETA = "beta"
    ALPHA = "alpha"


class DependencyConstraint(Enum):
    """Dependency version constraint types."""
    EXACT = "exact"          # ==1.0.0
    MINIMUM = "minimum"      # >=1.0.0
    MAXIMUM = "maximum"      # <=1.0.0
    COMPATIBLE = "compatible" # ^1.0.0 (semver compatible)
    RANGE = "range"          # >=1.0.0,<2.0.0


@dataclass
class SemanticVersion:
    """Semantic version representation following semver.org."""
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None
    
    @classmethod
    def parse(cls, version_str: str) -> "SemanticVersion":
        """Parse semantic version string."""
        # Strip 'v' prefix if present
        version_str = version_str.lstrip('v')
        
        # Regex for semver: major.minor.patch[-prerelease][+build]
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z\-\.]+))?(?:\+([0-9A-Za-z\-\.]+))?$'
        match = re.match(pattern, version_str)
        
        if not match:
            raise ValueError(f"Invalid semantic version: {version_str}")
        
        major, minor, patch, prerelease, build = match.groups()
        
        return cls(
            major=int(major),
            minor=int(minor),
            patch=int(patch),
            prerelease=prerelease,
            build=build
        )
    
    def __str__(self) -> str:
        """Convert to string representation."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version
    
    def __lt__(self, other: "SemanticVersion") -> bool:
        """Compare versions for sorting."""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        
        # Compare major.minor.patch
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        
        # Handle prerelease comparison
        if self.prerelease is None and other.prerelease is None:
            return False
        if self.prerelease is None:  # No prerelease > prerelease
            return False
        if other.prerelease is None:
            return True
        
        return self.prerelease < other.prerelease
    
    def __eq__(self, other: "SemanticVersion") -> bool:
        """Check version equality."""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        
        return (
            self.major == other.major and
            self.minor == other.minor and
            self.patch == other.patch and
            self.prerelease == other.prerelease
        )
    
    def __le__(self, other: "SemanticVersion") -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return self < other or self == other
    
    def __gt__(self, other: "SemanticVersion") -> bool:
        """Greater than comparison."""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return not (self <= other)
    
    def __ge__(self, other: "SemanticVersion") -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return not (self < other)
    
    def is_compatible_with(self, other: "SemanticVersion") -> bool:
        """Check if this version is compatible with other (this >= other and compatible)."""
        if self.major != other.major:
            return False
        if self.major == 0:
            # For 0.x.x, compatible means same minor version and this >= other
            return self.minor == other.minor and self >= other
        # For >=1.x.x, compatible means same major version and this >= other
        return self >= other


@dataclass
class PluginDependency:
    """Represents a plugin dependency with version constraints."""
    name: str
    constraint_type: DependencyConstraint
    version: str
    optional: bool = False
    namespace: Optional[str] = None
    
    def __post_init__(self):
        """Validate dependency after initialization."""
        if self.constraint_type in [DependencyConstraint.EXACT, DependencyConstraint.MINIMUM, 
                                   DependencyConstraint.MAXIMUM, DependencyConstraint.COMPATIBLE]:
            try:
                SemanticVersion.parse(self.version)
            except ValueError:
                raise ValueError(f"Invalid semantic version for dependency {self.name}: {self.version}")
    
    @property
    def full_name(self) -> str:
        """Get full dependency name with namespace."""
        if self.namespace:
            return f"{self.namespace}:{self.name}"
        return self.name
    
    def is_satisfied_by(self, available_version: str) -> bool:
        """Check if an available version satisfies this dependency."""
        try:
            available = SemanticVersion.parse(available_version)
            # Only parse required version for non-range constraints
            if self.constraint_type != DependencyConstraint.RANGE:
                required = SemanticVersion.parse(self.version)
            else:
                required = None
        except ValueError:
            return False
        
        if self.constraint_type == DependencyConstraint.EXACT:
            return available == required
        elif self.constraint_type == DependencyConstraint.MINIMUM:
            return available >= required
        elif self.constraint_type == DependencyConstraint.MAXIMUM:
            return available <= required
        elif self.constraint_type == DependencyConstraint.COMPATIBLE:
            return available.is_compatible_with(required) and available >= required
        elif self.constraint_type == DependencyConstraint.RANGE:
            # Parse range format: ">=1.0.0,<2.0.0"
            parts = self.version.split(',')
            satisfies_all = True
            
            for part in parts:
                part = part.strip()
                if not part:  # Skip empty parts
                    continue
                    
                try:
                    if part.startswith('>='):
                        min_version = SemanticVersion.parse(part[2:].strip())
                        if available < min_version:
                            satisfies_all = False
                            break
                    elif part.startswith('<='):
                        max_version = SemanticVersion.parse(part[2:].strip())
                        if available > max_version:
                            satisfies_all = False
                            break
                    elif part.startswith('<'):
                        max_version = SemanticVersion.parse(part[1:].strip())
                        if available >= max_version:
                            satisfies_all = False
                            break
                    elif part.startswith('>'):
                        min_version = SemanticVersion.parse(part[1:].strip())
                        if available <= min_version:
                            satisfies_all = False
                            break
                except ValueError:
                    # Invalid version in constraint
                    return False
            
            return satisfies_all
        
        return False


@dataclass 
class PluginReview:
    """User review and rating for a plugin."""
    user_id: str
    rating: int  # 1-5 stars
    title: str
    content: str
    created_at: datetime
    helpful_count: int = 0
    version_reviewed: Optional[str] = None
    verified_user: bool = False
    
    def __post_init__(self):
        """Validate review data."""
        if not 1 <= self.rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data


@dataclass
class PluginVersion:
    """Represents a specific version of a plugin."""
    version: str
    released_at: datetime
    changelog: str = ""
    download_count: int = 0
    is_prerelease: bool = False
    is_yanked: bool = False
    yank_reason: Optional[str] = None
    dependencies: List[PluginDependency] = field(default_factory=list)
    minimum_pacc_version: Optional[str] = None
    platform_requirements: List[str] = field(default_factory=list)  # e.g., ["linux", "darwin", "win32"]
    
    def __post_init__(self):
        """Validate version data."""
        try:
            SemanticVersion.parse(self.version)
        except ValueError:
            raise ValueError(f"Invalid semantic version: {self.version}")
    
    @property
    def semantic_version(self) -> SemanticVersion:
        """Get semantic version object."""
        return SemanticVersion.parse(self.version)
    
    def is_compatible_with_platform(self, platform: str) -> bool:
        """Check if this version is compatible with a platform."""
        if not self.platform_requirements:
            return True  # No requirements means universal compatibility
        return platform in self.platform_requirements
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['released_at'] = self.released_at.isoformat()
        data['dependencies'] = [dep.__dict__ for dep in self.dependencies]
        return data


@dataclass
class PluginMetadata:
    """Complete metadata for a plugin in the marketplace."""
    name: str
    namespace: Optional[str]
    description: str
    author: str
    author_email: Optional[str] = None
    homepage_url: Optional[str] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None
    license: str = "Unknown"
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    plugin_type: str = "command"  # command, agent, hook, mcp
    status: PluginStatus = PluginStatus.ACTIVE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    total_downloads: int = 0
    average_rating: float = 0.0
    review_count: int = 0
    versions: List[PluginVersion] = field(default_factory=list)
    reviews: List[PluginReview] = field(default_factory=list)
    
    @property
    def full_name(self) -> str:
        """Get full plugin name with namespace."""
        if self.namespace:
            return f"{self.namespace}:{self.name}"
        return self.name
    
    @property
    def latest_version(self) -> Optional[PluginVersion]:
        """Get the latest non-prerelease version."""
        if not self.versions:
            return None
        
        # Filter out prerelease and yanked versions
        stable_versions = [
            v for v in self.versions 
            if not v.is_prerelease and not v.is_yanked
        ]
        
        if not stable_versions:
            return None
        
        # Sort by semantic version and return latest
        stable_versions.sort(key=lambda v: v.semantic_version, reverse=True)
        return stable_versions[0]
    
    def get_version(self, version_str: str) -> Optional[PluginVersion]:
        """Get a specific version of the plugin."""
        for version in self.versions:
            if version.version == version_str:
                return version
        return None
    
    def calculate_rating_stats(self):
        """Calculate average rating and review count from reviews."""
        if not self.reviews:
            self.average_rating = 0.0
            self.review_count = 0
            return
        
        total_rating = sum(review.rating for review in self.reviews)
        self.average_rating = total_rating / len(self.reviews)
        self.review_count = len(self.reviews)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['status'] = self.status.value
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        data['versions'] = [v.to_dict() for v in self.versions]
        data['reviews'] = [r.to_dict() for r in self.reviews]
        return data


@dataclass
class RegistryConfig:
    """Configuration for a plugin registry."""
    name: str
    url: str
    registry_type: RegistryType
    enabled: bool = True
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 30
    cache_ttl: int = 3600  # 1 hour default
    verify_ssl: bool = True
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate registry configuration."""
        # Validate URL
        parsed = urlparse(self.url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid registry URL: {self.url}")
        
        # Ensure URL ends with /
        if not self.url.endswith('/'):
            self.url += '/'
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        headers = self.custom_headers.copy()
        
        if self.api_key:
            headers['Authorization'] = f"Bearer {self.api_key}"
        elif self.username and self.password:
            import base64
            credentials = f"{self.username}:{self.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers['Authorization'] = f"Basic {encoded}"
        
        return headers
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['registry_type'] = self.registry_type.value
        # Don't serialize sensitive information
        if 'password' in data:
            data['password'] = None
        if 'api_key' in data:
            data['api_key'] = None
        return data


class CacheEntry(NamedTuple):
    """Cache entry with timestamp and data."""
    timestamp: float
    data: Any
    etag: Optional[str] = None
    registry_name: Optional[str] = None
    endpoint: Optional[str] = None


class MetadataCache:
    """Cache system for plugin metadata with TTL support."""
    
    def __init__(self, cache_dir: Optional[Path] = None, default_ttl: int = 3600):
        """Initialize cache with optional directory and TTL."""
        if cache_dir is None:
            cache_dir = Path.home() / ".claude" / "pacc" / "cache" / "marketplace"
        
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        self._memory_cache: Dict[str, CacheEntry] = {}
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, registry_name: str, endpoint: str, params: Optional[Dict] = None) -> str:
        """Generate cache key for request."""
        key_data = f"{registry_name}:{endpoint}"
        if params:
            # Sort params for consistent key generation
            param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            key_data += f"?{param_str}"
        
        # Use hash for long keys
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cache_file(self, cache_key: str) -> Path:
        """Get cache file path for key."""
        return self.cache_dir / f"{cache_key}.json"
    
    def get(self, registry_name: str, endpoint: str, params: Optional[Dict] = None, ttl: Optional[int] = None) -> Optional[Any]:
        """Get cached data if not expired."""
        cache_key = self._get_cache_key(registry_name, endpoint, params)
        ttl = ttl or self.default_ttl
        current_time = time.time()
        
        # Check memory cache first
        if cache_key in self._memory_cache:
            entry = self._memory_cache[cache_key]
            if current_time - entry.timestamp < ttl:
                return entry.data
            else:
                del self._memory_cache[cache_key]
        
        # Check disk cache
        cache_file = self._get_cache_file(cache_key)
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                
                timestamp = cached_data.get('timestamp', 0)
                if current_time - timestamp < ttl:
                    data = cached_data.get('data')
                    etag = cached_data.get('etag')
                    
                    # Update memory cache
                    self._memory_cache[cache_key] = CacheEntry(timestamp, data, etag, registry_name, endpoint)
                    return data
                else:
                    # Expired, remove file
                    try:
                        cache_file.unlink()
                    except FileNotFoundError:
                        pass
            except (json.JSONDecodeError, IOError):
                # Corrupted cache file, remove it
                if cache_file.exists():
                    cache_file.unlink()
        
        return None
    
    def set(self, registry_name: str, endpoint: str, data: Any, params: Optional[Dict] = None, etag: Optional[str] = None):
        """Cache data with timestamp."""
        cache_key = self._get_cache_key(registry_name, endpoint, params)
        timestamp = time.time()
        
        # Update memory cache
        self._memory_cache[cache_key] = CacheEntry(timestamp, data, etag, registry_name, endpoint)
        
        # Update disk cache
        cache_file = self._get_cache_file(cache_key)
        cache_data = {
            'timestamp': timestamp,
            'data': data,
            'etag': etag
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
        except IOError:
            # Ignore cache write failures
            pass
    
    def invalidate(self, registry_name: str, endpoint: str = "", params: Optional[Dict] = None):
        """Invalidate cached data."""
        if endpoint:
            # Invalidate specific endpoint
            cache_key = self._get_cache_key(registry_name, endpoint, params)
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
            
            cache_file = self._get_cache_file(cache_key)
            if cache_file.exists():
                cache_file.unlink()
        else:
            # Invalidate all entries for registry
            keys_to_remove = []
            
            for key, entry in list(self._memory_cache.items()):
                if entry.registry_name == registry_name:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._memory_cache[key]
            
            # Remove corresponding disk cache files
            for key in keys_to_remove:
                cache_file = self._get_cache_file(key)
                try:
                    cache_file.unlink()
                except FileNotFoundError:
                    pass
    
    def clear_expired(self, ttl: Optional[int] = None):
        """Clear all expired cache entries."""
        ttl = ttl or self.default_ttl
        current_time = time.time()
        
        # Clear memory cache
        keys_to_remove = [
            key for key, entry in self._memory_cache.items()
            if current_time - entry.timestamp >= ttl
        ]
        for key in keys_to_remove:
            del self._memory_cache[key]
        
        # Clear disk cache
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                
                timestamp = cached_data.get('timestamp', 0)
                if current_time - timestamp >= ttl:
                    cache_file.unlink()
            except (json.JSONDecodeError, IOError):
                # Remove corrupted files
                cache_file.unlink()


class DependencyResolver:
    """Resolves plugin dependencies and checks for conflicts."""
    
    def __init__(self, marketplace_client: "MarketplaceClient"):
        """Initialize with marketplace client for dependency lookup."""
        self.client = marketplace_client
    
    def resolve_dependencies(
        self,
        plugin_name: str,
        version: str,
        installed_plugins: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Resolve dependencies for a plugin.
        
        Returns:
            Dict with 'success', 'dependencies', 'conflicts', and 'messages' keys
        """
        installed_plugins = installed_plugins or {}
        result = {
            'success': True,
            'dependencies': [],
            'conflicts': [],
            'messages': []
        }
        
        try:
            # Get plugin metadata
            metadata = self.client.get_plugin_metadata(plugin_name)
            if not metadata:
                result['success'] = False
                result['messages'].append(f"Plugin {plugin_name} not found in marketplace")
                return result
            
            # Get specific version
            plugin_version = metadata.get_version(version)
            if not plugin_version:
                result['success'] = False
                result['messages'].append(f"Version {version} not found for plugin {plugin_name}")
                return result
            
            # Check each dependency
            for dependency in plugin_version.dependencies:
                dep_result = self._resolve_single_dependency(dependency, installed_plugins)
                
                if dep_result['status'] == 'satisfied':
                    result['messages'].append(f"Dependency {dependency.full_name} already satisfied")
                elif dep_result['status'] == 'installable':
                    result['dependencies'].append({
                        'name': dependency.full_name,
                        'version': dep_result['version'],
                        'constraint': dependency.version,
                        'optional': dependency.optional
                    })
                    result['messages'].append(f"Will install {dependency.full_name} {dep_result['version']}")
                else:
                    conflict = {
                        'dependency': dependency.full_name,
                        'required': dependency.version,
                        'installed': dep_result.get('installed_version'),
                        'reason': dep_result.get('reason', 'Unknown conflict')
                    }
                    result['conflicts'].append(conflict)
                    
                    if not dependency.optional:
                        result['success'] = False
                    
                    result['messages'].append(
                        f"Conflict with {dependency.full_name}: {conflict['reason']}"
                    )
        
        except Exception as e:
            result['success'] = False
            result['messages'].append(f"Error resolving dependencies: {str(e)}")
        
        return result
    
    def _resolve_single_dependency(
        self,
        dependency: PluginDependency,
        installed_plugins: Dict[str, str]
    ) -> Dict[str, Any]:
        """Resolve a single dependency."""
        
        # Check if already installed
        if dependency.full_name in installed_plugins:
            installed_version = installed_plugins[dependency.full_name]
            if dependency.is_satisfied_by(installed_version):
                return {'status': 'satisfied', 'installed_version': installed_version}
            else:
                return {
                    'status': 'conflict',
                    'installed_version': installed_version,
                    'reason': f"Installed version {installed_version} doesn't satisfy constraint {dependency.version}"
                }
        
        # Find compatible version in marketplace
        try:
            metadata = self.client.get_plugin_metadata(dependency.full_name)
            if not metadata:
                return {'status': 'not_found', 'reason': f"Plugin {dependency.full_name} not found"}
            
            # Find latest compatible version
            compatible_versions = []
            for version in metadata.versions:
                if not version.is_yanked and dependency.is_satisfied_by(version.version):
                    compatible_versions.append(version)
            
            if not compatible_versions:
                return {
                    'status': 'no_compatible_version',
                    'reason': f"No compatible version found for constraint {dependency.version}"
                }
            
            # Sort and pick latest compatible version
            compatible_versions.sort(key=lambda v: v.semantic_version, reverse=True)
            latest_compatible = compatible_versions[0]
            
            return {'status': 'installable', 'version': latest_compatible.version}
            
        except Exception as e:
            return {'status': 'error', 'reason': f"Error checking dependency: {str(e)}"}
    
    def check_circular_dependencies(
        self,
        plugin_name: str,
        version: str,
        dependency_chain: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """Check for circular dependencies."""
        dependency_chain = dependency_chain or set()
        
        if plugin_name in dependency_chain:
            return {
                'has_circular': True,
                'chain': list(dependency_chain) + [plugin_name],
                'message': f"Circular dependency detected: {' -> '.join(dependency_chain)} -> {plugin_name}"
            }
        
        try:
            metadata = self.client.get_plugin_metadata(plugin_name)
            if not metadata:
                return {'has_circular': False, 'message': f"Plugin {plugin_name} not found"}
            
            plugin_version = metadata.get_version(version)
            if not plugin_version:
                return {'has_circular': False, 'message': f"Version {version} not found"}
            
            # Check each dependency recursively
            new_chain = dependency_chain | {plugin_name}
            for dependency in plugin_version.dependencies:
                if not dependency.optional:  # Only check required dependencies
                    dep_metadata = self.client.get_plugin_metadata(dependency.full_name)
                    if dep_metadata and dep_metadata.latest_version:
                        circular_check = self.check_circular_dependencies(
                            dependency.full_name,
                            dep_metadata.latest_version.version,
                            new_chain
                        )
                        if circular_check['has_circular']:
                            return circular_check
            
            return {'has_circular': False, 'message': 'No circular dependencies found'}
            
        except Exception as e:
            return {'has_circular': False, 'message': f"Error checking circular dependencies: {str(e)}"}


class MarketplaceClient:
    """Client for interacting with plugin marketplaces/registries."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize marketplace client."""
        if config_path is None:
            config_path = Path.home() / ".claude" / "pacc" / "marketplace.json"
        
        self.config_path = config_path
        self.registries: Dict[str, RegistryConfig] = {}
        self.cache = MetadataCache()
        self.dependency_resolver = DependencyResolver(self)
        
        # Load configuration
        self._load_config()
    
    def _load_config(self):
        """Load marketplace configuration."""
        if not self.config_path.exists():
            # Create default configuration with public registry
            self._create_default_config()
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            for name, registry_data in config_data.get('registries', {}).items():
                try:
                    registry_type = RegistryType(registry_data.get('registry_type', 'public'))
                    registry = RegistryConfig(
                        name=name,
                        url=registry_data['url'],
                        registry_type=registry_type,
                        enabled=registry_data.get('enabled', True),
                        timeout=registry_data.get('timeout', 30),
                        cache_ttl=registry_data.get('cache_ttl', 3600),
                        verify_ssl=registry_data.get('verify_ssl', True),
                        custom_headers=registry_data.get('custom_headers', {})
                    )
                    self.registries[name] = registry
                except (ValueError, KeyError) as e:
                    # Skip invalid registry configurations
                    continue
                    
        except (json.JSONDecodeError, IOError):
            # Create default config on error
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default marketplace configuration."""
        # For MVP, we'll use the local registry.json as the "marketplace"
        default_registry = RegistryConfig(
            name="community",
            url="https://api.claude-code.dev/plugins/",  # Future API endpoint
            registry_type=RegistryType.PUBLIC,
            enabled=True
        )
        
        self.registries["community"] = default_registry
        self._save_config()
    
    def _save_config(self):
        """Save marketplace configuration."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config_data = {
            'version': '1.0',
            'registries': {
                name: registry.to_dict()
                for name, registry in self.registries.items()
            }
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2)
        except IOError:
            # Ignore save failures for now
            pass
    
    def add_registry(self, registry: RegistryConfig) -> bool:
        """Add a new registry configuration."""
        try:
            self.registries[registry.name] = registry
            self._save_config()
            return True
        except Exception:
            return False
    
    def remove_registry(self, name: str) -> bool:
        """Remove a registry configuration."""
        if name in self.registries:
            del self.registries[name]
            self.cache.invalidate(name)
            self._save_config()
            return True
        return False
    
    def get_plugin_metadata(self, plugin_name: str, registry_name: Optional[str] = None) -> Optional[PluginMetadata]:
        """Get plugin metadata from marketplace."""
        # For MVP foundation, return mock data based on existing registry.json
        # In full implementation, this would make HTTP requests to registry APIs
        
        registries_to_search = [registry_name] if registry_name else list(self.registries.keys())
        
        for reg_name in registries_to_search:
            if reg_name not in self.registries or not self.registries[reg_name].enabled:
                continue
            
            # Check cache first
            cached = self.cache.get(reg_name, f"plugins/{plugin_name}")
            if cached:
                return self._dict_to_plugin_metadata(cached)
            
            # For MVP, simulate API call by checking local registry.json
            metadata = self._mock_get_plugin_metadata(plugin_name, reg_name)
            if metadata:
                # Cache the result
                self.cache.set(reg_name, f"plugins/{plugin_name}", metadata.to_dict())
                return metadata
        
        return None
    
    def _mock_get_plugin_metadata(self, plugin_name: str, registry_name: str) -> Optional[PluginMetadata]:
        """Mock implementation using local registry.json for MVP."""
        # This would be replaced with actual HTTP API calls in production
        registry_file = Path(__file__).parent / "registry.json"
        
        if not registry_file.exists():
            return None
        
        try:
            with open(registry_file, 'r', encoding='utf-8') as f:
                registry_data = json.load(f)
            
            for plugin_data in registry_data.get('plugins', []):
                if plugin_data.get('name') == plugin_name:
                    # Convert registry data to PluginMetadata
                    return self._registry_to_plugin_metadata(plugin_data)
                    
        except (json.JSONDecodeError, IOError):
            pass
        
        return None
    
    def _registry_to_plugin_metadata(self, plugin_data: Dict[str, Any]) -> PluginMetadata:
        """Convert registry data to PluginMetadata."""
        # Create mock version data
        version_str = plugin_data.get('version', '1.0.0')
        mock_version = PluginVersion(
            version=version_str,
            released_at=datetime.fromisoformat(plugin_data.get('last_updated', '2025-01-01T00:00:00Z').replace('Z', '+00:00')),
            changelog=f"Version {version_str}",
            download_count=plugin_data.get('popularity_score', 0) * 10,  # Mock download count
            dependencies=[]  # Would be parsed from actual plugin metadata
        )
        
        return PluginMetadata(
            name=plugin_data.get('name', ''),
            namespace=plugin_data.get('namespace'),
            description=plugin_data.get('description', ''),
            author=plugin_data.get('author', ''),
            repository_url=plugin_data.get('repository_url', ''),
            tags=plugin_data.get('tags', []),
            plugin_type=plugin_data.get('type', 'command'),
            status=PluginStatus.ACTIVE,
            total_downloads=plugin_data.get('popularity_score', 0) * 10,
            average_rating=4.2,  # Mock rating
            review_count=plugin_data.get('popularity_score', 0) // 10,
            versions=[mock_version]
        )
    
    def _dict_to_plugin_metadata(self, data: Dict[str, Any]) -> PluginMetadata:
        """Convert dictionary back to PluginMetadata."""
        # Parse versions
        versions = []
        for version_data in data.get('versions', []):
            dependencies = []
            for dep_data in version_data.get('dependencies', []):
                dep = PluginDependency(
                    name=dep_data['name'],
                    constraint_type=DependencyConstraint(dep_data['constraint_type']),
                    version=dep_data['version'],
                    optional=dep_data.get('optional', False),
                    namespace=dep_data.get('namespace')
                )
                dependencies.append(dep)
            
            version = PluginVersion(
                version=version_data['version'],
                released_at=datetime.fromisoformat(version_data['released_at']),
                changelog=version_data.get('changelog', ''),
                download_count=version_data.get('download_count', 0),
                is_prerelease=version_data.get('is_prerelease', False),
                is_yanked=version_data.get('is_yanked', False),
                dependencies=dependencies
            )
            versions.append(version)
        
        # Parse reviews
        reviews = []
        for review_data in data.get('reviews', []):
            review = PluginReview(
                user_id=review_data['user_id'],
                rating=review_data['rating'],
                title=review_data['title'],
                content=review_data['content'],
                created_at=datetime.fromisoformat(review_data['created_at']),
                helpful_count=review_data.get('helpful_count', 0),
                version_reviewed=review_data.get('version_reviewed'),
                verified_user=review_data.get('verified_user', False)
            )
            reviews.append(review)
        
        return PluginMetadata(
            name=data['name'],
            namespace=data.get('namespace'),
            description=data['description'],
            author=data['author'],
            author_email=data.get('author_email'),
            homepage_url=data.get('homepage_url'),
            repository_url=data.get('repository_url'),
            documentation_url=data.get('documentation_url'),
            license=data.get('license', 'Unknown'),
            tags=data.get('tags', []),
            categories=data.get('categories', []),
            plugin_type=data.get('plugin_type', 'command'),
            status=PluginStatus(data.get('status', 'active')),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else None,
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else None,
            total_downloads=data.get('total_downloads', 0),
            average_rating=data.get('average_rating', 0.0),
            review_count=data.get('review_count', 0),
            versions=versions,
            reviews=reviews
        )
    
    def search_plugins(
        self,
        query: str = "",
        plugin_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[PluginMetadata]:
        """Search plugins across all enabled registries."""
        results = []
        
        for registry_name, registry in self.registries.items():
            if not registry.enabled:
                continue
            
            # Check cache
            cache_params = {
                'query': query,
                'type': plugin_type,
                'tags': ','.join(tags) if tags else '',
                'limit': limit,
                'offset': offset
            }
            cached = self.cache.get(registry_name, "search", cache_params, ttl=1800)  # 30 min cache
            
            if cached:
                for plugin_data in cached:
                    results.append(self._dict_to_plugin_metadata(plugin_data))
            else:
                # For MVP, use mock search
                search_results = self._mock_search_plugins(query, plugin_type, tags, limit, offset)
                # Cache results
                self.cache.set(registry_name, "search", [p.to_dict() for p in search_results], cache_params)
                results.extend(search_results)
        
        # Remove duplicates and sort by relevance
        unique_results = {}
        for plugin in results:
            if plugin.full_name not in unique_results:
                unique_results[plugin.full_name] = plugin
        
        return list(unique_results.values())[:limit]
    
    def _mock_search_plugins(
        self,
        query: str,
        plugin_type: Optional[str],
        tags: Optional[List[str]],
        limit: int,
        offset: int
    ) -> List[PluginMetadata]:
        """Mock search implementation for MVP."""
        registry_file = Path(__file__).parent / "registry.json"
        results = []
        
        if not registry_file.exists():
            return results
        
        try:
            with open(registry_file, 'r', encoding='utf-8') as f:
                registry_data = json.load(f)
            
            for plugin_data in registry_data.get('plugins', []):
                # Filter by type
                if plugin_type and plugin_data.get('type') != plugin_type:
                    continue
                
                # Filter by tags
                if tags:
                    plugin_tags = plugin_data.get('tags', [])
                    if not any(tag in plugin_tags for tag in tags):
                        continue
                
                # Filter by query
                if query:
                    query_lower = query.lower()
                    searchable_text = ' '.join([
                        plugin_data.get('name', ''),
                        plugin_data.get('description', ''),
                        plugin_data.get('author', ''),
                        ' '.join(plugin_data.get('tags', []))
                    ]).lower()
                    
                    if query_lower not in searchable_text:
                        continue
                
                # Convert to metadata
                metadata = self._registry_to_plugin_metadata(plugin_data)
                results.append(metadata)
                
        except (json.JSONDecodeError, IOError):
            pass
        
        # Apply pagination
        return results[offset:offset + limit]
    
    def get_plugin_versions(self, plugin_name: str) -> List[PluginVersion]:
        """Get all versions of a plugin."""
        metadata = self.get_plugin_metadata(plugin_name)
        return metadata.versions if metadata else []
    
    def invalidate_cache(self, registry_name: Optional[str] = None):
        """Invalidate marketplace cache."""
        if registry_name:
            self.cache.invalidate(registry_name)
        else:
            for reg_name in self.registries.keys():
                self.cache.invalidate(reg_name)


# Utility functions for CLI integration
def create_marketplace_client(config_path: Optional[Path] = None) -> MarketplaceClient:
    """Create a marketplace client instance."""
    return MarketplaceClient(config_path)


def get_plugin_info(plugin_name: str, registry_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get plugin information as dictionary for CLI."""
    client = create_marketplace_client()
    metadata = client.get_plugin_metadata(plugin_name, registry_name)
    return metadata.to_dict() if metadata else None


def search_marketplace(
    query: str = "",
    plugin_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Search marketplace plugins for CLI."""
    client = create_marketplace_client()
    results = client.search_plugins(query, plugin_type, tags, limit)
    return [plugin.to_dict() for plugin in results]


def resolve_plugin_dependencies(
    plugin_name: str,
    version: str,
    installed_plugins: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Resolve plugin dependencies for CLI."""
    client = create_marketplace_client()
    return client.dependency_resolver.resolve_dependencies(plugin_name, version, installed_plugins)