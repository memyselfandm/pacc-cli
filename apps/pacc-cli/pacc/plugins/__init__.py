"""Plugin configuration management for Claude Code integration."""

from .config import PluginConfigManager, ConfigBackup, AtomicFileWriter
from .repository import (
    PluginRepositoryManager,
    PluginRepo,
    UpdateResult,
    PluginInfo as RepoPluginInfo,
    RepositoryValidationResult,
    GitError,
    RepositoryStructureError
)
from .discovery import (
    PluginInfo as DiscoveryPluginInfo, 
    RepositoryInfo, 
    PluginScanner, 
    PluginManifestParser, 
    PluginMetadataExtractor,
    discover_plugins,
    validate_plugin_manifest,
    extract_plugin_metadata,
    resolve_template_variables,
    extract_template_variables
)
from .converter import (
    PluginConverter,
    ExtensionToPluginConverter,
    PluginPusher,
    ConversionResult,
    PluginMetadata,
    ExtensionInfo,
    convert_extensions_to_plugin
)
from .environment import (
    EnvironmentManager,
    EnvironmentStatus,
    Platform,
    Shell,
    ProfileUpdate,
    get_environment_manager
)
from .creator import (
    PluginCreator,
    PluginTemplate,
    CreationPluginType,
    CreationMode,
    CreationResult,
    TemplateEngine,
    GitInitializer,
    MetadataCollector
)

# Create aliases for CLI compatibility
RepositoryManager = PluginRepositoryManager
GitRepository = PluginRepo

# For backward compatibility, import old classes as stubs
from .discovery_old import PluginDiscovery, RepositoryPlugins, PluginSelector

# Search functionality
from .search import (
    PluginSearchEngine,
    PluginRegistry,
    LocalPluginIndex,
    SearchResult,
    SearchPluginType,
    SortBy,
    search_plugins,
    get_plugin_recommendations
)

__all__ = [
    "PluginConfigManager",
    "ConfigBackup", 
    "AtomicFileWriter",
    "PluginRepositoryManager",
    "RepositoryManager",  # Alias
    "GitRepository",      # Alias
    "PluginRepo",
    "UpdateResult",
    "RepoPluginInfo",
    "RepositoryValidationResult",
    "GitError",
    "RepositoryStructureError",
    "DiscoveryPluginInfo",
    "RepositoryInfo",
    "PluginScanner",
    "PluginManifestParser",
    "PluginMetadataExtractor",
    "discover_plugins",
    "validate_plugin_manifest", 
    "extract_plugin_metadata",
    "resolve_template_variables",
    "extract_template_variables",
    # Conversion functionality
    "PluginConverter",
    "ExtensionToPluginConverter",
    "PluginPusher",
    "ConversionResult",
    "PluginMetadata",
    "ExtensionInfo",
    "convert_extensions_to_plugin",
    # Environment management
    "EnvironmentManager",
    "EnvironmentStatus",
    "Platform",
    "Shell", 
    "ProfileUpdate",
    "get_environment_manager",
    # Backward compatibility
    "PluginDiscovery",
    "RepositoryPlugins", 
    "PluginSelector",
    # Search functionality
    "PluginSearchEngine",
    "PluginRegistry",
    "LocalPluginIndex", 
    "SearchResult",
    "SearchPluginType",
    "SortBy",
    "search_plugins",
    "get_plugin_recommendations",
    # Plugin creation
    "PluginCreator",
    "PluginTemplate",
    "CreationPluginType",
    "CreationMode",
    "CreationResult",
    "TemplateEngine",
    "GitInitializer",
    "MetadataCollector"
]