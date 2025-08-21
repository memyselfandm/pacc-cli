"""Plugin search and discovery functionality for PACC."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Union
from dataclasses import dataclass, asdict
from enum import Enum

from .config import PluginConfigManager
from .discovery import PluginScanner, PluginInfo
from ..core.project_config import ProjectConfigManager


class SearchPluginType(Enum):
    """Supported plugin types for search."""
    COMMAND = "command"
    AGENT = "agent" 
    HOOK = "hook"
    MCP = "mcp"
    ALL = "all"


class SortBy(Enum):
    """Sort criteria for search results."""
    POPULARITY = "popularity"
    DATE = "date"
    NAME = "name"
    RELEVANCE = "relevance"


@dataclass
class SearchResult:
    """Represents a plugin search result."""
    name: str
    description: str
    plugin_type: SearchPluginType
    repository_url: str
    author: str
    version: str = "latest"
    popularity_score: int = 0
    last_updated: Optional[str] = None
    tags: List[str] = None
    installed: bool = False
    enabled: bool = False
    namespace: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    @property
    def full_name(self) -> str:
        """Get full plugin name including namespace."""
        if self.namespace:
            return f"{self.namespace}:{self.name}"
        return self.name
    
    def matches_query(self, query: str) -> bool:
        """Check if this result matches a search query."""
        if not query:
            return True
            
        query_lower = query.lower()
        return (
            query_lower in self.name.lower() or
            query_lower in self.description.lower() or
            query_lower in self.author.lower() or
            any(query_lower in tag.lower() for tag in self.tags if tag)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["plugin_type"] = self.plugin_type.value
        return result


@dataclass
class ProjectContext:
    """Context about the current project for recommendations."""
    project_type: Optional[str] = None
    languages: Set[str] = None
    frameworks: Set[str] = None
    has_tests: bool = False
    has_docs: bool = False
    
    def __post_init__(self):
        if self.languages is None:
            self.languages = set()
        if self.frameworks is None:
            self.frameworks = set()


class PluginRegistry:
    """Manages the community plugin registry."""
    
    def __init__(self, registry_path: Optional[Path] = None):
        """Initialize registry with optional custom path."""
        if registry_path is None:
            # Default to registry.json in same directory as this module
            registry_path = Path(__file__).parent / "registry.json"
        
        self.registry_path = registry_path
        self._registry_data: Optional[Dict[str, Any]] = None
        self._last_loaded: Optional[datetime] = None
    
    def _load_registry(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load registry data from file."""
        if not force_reload and self._registry_data is not None:
            return self._registry_data
        
        if not self.registry_path.exists():
            # Return empty registry if file doesn't exist
            return {"plugins": [], "version": "1.0", "last_updated": datetime.now().isoformat()}
        
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                self._registry_data = json.load(f)
                self._last_loaded = datetime.now()
                return self._registry_data
        except (json.JSONDecodeError, IOError) as e:
            # Return empty registry on error
            return {"plugins": [], "version": "1.0", "last_updated": datetime.now().isoformat()}
    
    def search_community_plugins(self, query: str = "", plugin_type: SearchPluginType = SearchPluginType.ALL) -> List[SearchResult]:
        """Search community plugins from registry."""
        registry = self._load_registry()
        results = []
        
        for plugin_data in registry.get("plugins", []):
            try:
                # Parse plugin type
                ptype = SearchPluginType(plugin_data.get("type", "command").lower())
                
                # Filter by type if specified
                if plugin_type != SearchPluginType.ALL and ptype != plugin_type:
                    continue
                
                result = SearchResult(
                    name=plugin_data.get("name", ""),
                    description=plugin_data.get("description", ""),
                    plugin_type=ptype,
                    repository_url=plugin_data.get("repository_url", ""),
                    author=plugin_data.get("author", ""),
                    version=plugin_data.get("version", "latest"),
                    popularity_score=plugin_data.get("popularity_score", 0),
                    last_updated=plugin_data.get("last_updated"),
                    tags=plugin_data.get("tags", []),
                    namespace=plugin_data.get("namespace")
                )
                
                # Check query match
                if result.matches_query(query):
                    results.append(result)
                    
            except (ValueError, KeyError) as e:
                # Skip invalid plugin entries
                continue
        
        return results
    
    def get_recommendations(self, project_context: ProjectContext, limit: int = 10) -> List[SearchResult]:
        """Get plugin recommendations based on project context."""
        registry = self._load_registry()
        results = []
        
        for plugin_data in registry.get("plugins", []):
            try:
                result = SearchResult(
                    name=plugin_data.get("name", ""),
                    description=plugin_data.get("description", ""),
                    plugin_type=SearchPluginType(plugin_data.get("type", "command").lower()),
                    repository_url=plugin_data.get("repository_url", ""),
                    author=plugin_data.get("author", ""),
                    version=plugin_data.get("version", "latest"),
                    popularity_score=plugin_data.get("popularity_score", 0),
                    last_updated=plugin_data.get("last_updated"),
                    tags=plugin_data.get("tags", []),
                    namespace=plugin_data.get("namespace")
                )
                
                # Calculate relevance score based on project context
                relevance_score = self._calculate_relevance(result, project_context)
                if relevance_score > 0:
                    result.popularity_score += relevance_score  # Boost popularity for sorting
                    results.append(result)
                    
            except (ValueError, KeyError):
                continue
        
        # Sort by popularity (which includes relevance boost) and limit
        results.sort(key=lambda r: r.popularity_score, reverse=True)
        return results[:limit]
    
    def _calculate_relevance(self, plugin: SearchResult, context: ProjectContext) -> int:
        """Calculate relevance score for a plugin given project context."""
        score = 0
        
        # Language-based recommendations
        for lang in context.languages:
            if any(lang.lower() in tag.lower() for tag in plugin.tags):
                score += 10
            if lang.lower() in plugin.description.lower():
                score += 5
        
        # Framework-based recommendations
        for framework in context.frameworks:
            if any(framework.lower() in tag.lower() for tag in plugin.tags):
                score += 8
            if framework.lower() in plugin.description.lower():
                score += 4
        
        # Project type recommendations
        if context.project_type:
            if any(context.project_type.lower() in tag.lower() for tag in plugin.tags):
                score += 15
            if context.project_type.lower() in plugin.description.lower():
                score += 8
        
        # Feature-based recommendations
        if context.has_tests and any("test" in tag.lower() for tag in plugin.tags):
            score += 5
        if context.has_docs and any("doc" in tag.lower() for tag in plugin.tags):
            score += 5
        
        return score


class LocalPluginIndex:
    """Manages indexing of locally installed plugins."""
    
    def __init__(self, config_manager: Optional[PluginConfigManager] = None):
        """Initialize with optional config manager."""
        self.config_manager = config_manager or PluginConfigManager()
        self.scanner = PluginScanner()
    
    def get_installed_plugins(self) -> List[SearchResult]:
        """Get all locally installed plugins."""
        results = []
        
        try:
            # Get installed plugins from config
            config = self.config_manager.load_config()
            enabled_plugins = self.config_manager.get_enabled_plugins()
            
            # Scan each repository
            for repo_key, repo_info in config.get("repositories", {}).items():
                repo_path = Path(repo_info.get("path", ""))
                if not repo_path.exists():
                    continue
                
                try:
                    # Discover plugins in this repository
                    plugins = self.scanner.scan_repository(repo_path)
                    
                    for plugin in plugins:
                        # Extract description from manifest
                        description = plugin.manifest.get("description", "") if plugin.manifest else ""
                        
                        # Extract namespace from plugin name (if it contains colons)
                        namespace = None
                        if ":" in plugin.name:
                            parts = plugin.name.split(":")
                            if len(parts) >= 2:
                                namespace = parts[0]
                        
                        # Convert to SearchResult
                        result = SearchResult(
                            name=plugin.name,
                            description=description,
                            plugin_type=self._plugin_type_from_components(plugin.components),
                            repository_url=repo_info.get("url", ""),
                            author=repo_info.get("owner", ""),
                            version=repo_info.get("current_commit", "")[:8] if repo_info.get("current_commit") else "unknown",
                            last_updated=repo_info.get("last_updated"),
                            installed=True,
                            enabled=plugin.name in enabled_plugins,
                            namespace=namespace
                        )
                        results.append(result)
                        
                except Exception:
                    # Skip repositories that can't be scanned
                    continue
                    
        except Exception:
            # Return empty list on any major error
            pass
        
        return results
    
    def _plugin_type_from_components(self, components: Dict[str, Any]) -> SearchPluginType:
        """Determine plugin type from its components."""
        # Components is a dict mapping component type to list of paths
        if components.get("hooks"):
            return SearchPluginType.HOOK
        elif components.get("mcps"):
            return SearchPluginType.MCP
        elif components.get("agents"):
            return SearchPluginType.AGENT
        elif components.get("commands"):
            return SearchPluginType.COMMAND
        else:
            return SearchPluginType.COMMAND  # Default


class PluginSearchEngine:
    """Main search engine combining registry and local index."""
    
    def __init__(self, registry_path: Optional[Path] = None, config_manager: Optional[PluginConfigManager] = None):
        """Initialize search engine."""
        self.registry = PluginRegistry(registry_path)
        self.local_index = LocalPluginIndex(config_manager)
        
    def search(
        self,
        query: str = "",
        plugin_type: SearchPluginType = SearchPluginType.ALL,
        sort_by: SortBy = SortBy.RELEVANCE,
        include_installed: bool = True,
        installed_only: bool = False
    ) -> List[SearchResult]:
        """
        Perform a comprehensive plugin search.
        
        Args:
            query: Search query string
            plugin_type: Filter by plugin type
            sort_by: Sort criteria
            include_installed: Include locally installed plugins
            installed_only: Only return installed plugins
        
        Returns:
            List of search results
        """
        results = []
        
        # Get installed plugins if requested
        if include_installed or installed_only:
            installed = self.local_index.get_installed_plugins()
            
            # Filter installed plugins
            for plugin in installed:
                if plugin_type == SearchPluginType.ALL or plugin.plugin_type == plugin_type:
                    if plugin.matches_query(query):
                        results.append(plugin)
        
        # Get community plugins if not installed-only
        if not installed_only:
            community = self.registry.search_community_plugins(query, plugin_type)
            
            # Mark which ones are installed
            installed_names = {p.full_name for p in results}
            for plugin in community:
                if plugin.full_name not in installed_names:
                    results.append(plugin)
                else:
                    # Update installed plugin with community info
                    for installed in results:
                        if installed.full_name == plugin.full_name:
                            installed.popularity_score = plugin.popularity_score
                            installed.tags = plugin.tags
                            break
        
        # Sort results
        results = self._sort_results(results, sort_by)
        
        return results
    
    def get_recommendations(self, limit: int = 10) -> List[SearchResult]:
        """Get plugin recommendations based on current project."""
        context = self._analyze_project_context()
        return self.registry.get_recommendations(context, limit)
    
    def _sort_results(self, results: List[SearchResult], sort_by: SortBy) -> List[SearchResult]:
        """Sort search results by specified criteria."""
        if sort_by == SortBy.NAME:
            return sorted(results, key=lambda r: r.name.lower())
        elif sort_by == SortBy.POPULARITY:
            return sorted(results, key=lambda r: r.popularity_score, reverse=True)
        elif sort_by == SortBy.DATE:
            # Sort by last_updated, putting None values at the end
            return sorted(
                results,
                key=lambda r: r.last_updated or "0000-00-00",
                reverse=True
            )
        else:  # RELEVANCE (default)
            # For relevance, prefer installed plugins, then popularity
            return sorted(
                results,
                key=lambda r: (r.installed, r.popularity_score),
                reverse=True
            )
    
    def _analyze_project_context(self) -> ProjectContext:
        """Analyze current project to provide context for recommendations."""
        context = ProjectContext()
        
        try:
            # Try to detect project characteristics
            cwd = Path.cwd()
            
            # Check for common files to determine project type and languages
            if (cwd / "package.json").exists():
                context.languages.add("javascript")
                context.project_type = "web"
            
            if (cwd / "requirements.txt").exists() or (cwd / "pyproject.toml").exists():
                context.languages.add("python")
                if not context.project_type:
                    context.project_type = "python"
            
            if (cwd / "Cargo.toml").exists():
                context.languages.add("rust")
                context.project_type = "rust"
            
            if (cwd / "go.mod").exists():
                context.languages.add("go")
                context.project_type = "go"
            
            # Check for testing frameworks
            if any((cwd / f).exists() for f in ["tests", "test", "__tests__", "spec"]):
                context.has_tests = True
            
            # Check for documentation
            if any((cwd / f).exists() for f in ["docs", "documentation", "README.md"]):
                context.has_docs = True
                
        except Exception:
            # Return basic context on any error
            pass
        
        return context


# Convenience functions for CLI usage
def search_plugins(
    query: str = "",
    plugin_type: str = "all",
    sort_by: str = "relevance",
    include_installed: bool = True,
    installed_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Convenience function for CLI to search plugins.
    
    Returns results as dictionaries for easy JSON serialization.
    """
    try:
        ptype = SearchPluginType(plugin_type.lower())
    except ValueError:
        ptype = SearchPluginType.ALL
    
    try:
        sort_criteria = SortBy(sort_by.lower())
    except ValueError:
        sort_criteria = SortBy.RELEVANCE
    
    engine = PluginSearchEngine()
    results = engine.search(
        query=query,
        plugin_type=ptype,
        sort_by=sort_criteria,
        include_installed=include_installed,
        installed_only=installed_only
    )
    
    return [result.to_dict() for result in results]


def get_plugin_recommendations(limit: int = 10) -> List[Dict[str, Any]]:
    """Get plugin recommendations for current project."""
    engine = PluginSearchEngine()
    results = engine.get_recommendations(limit)
    return [result.to_dict() for result in results]