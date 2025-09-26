"""Plugin configuration management for Claude Code integration."""

from .config import AtomicFileWriter, ConfigBackup, PluginConfigManager
from .converter import (
    ConversionResult,
    ExtensionInfo,
    ExtensionToPluginConverter,
    PluginConverter,
    PluginMetadata,
    PluginPusher,
    convert_extensions_to_plugin,
)
from .creator import (
    CreationMode,
    CreationPluginType,
    CreationResult,
    GitInitializer,
    MetadataCollector,
    PluginCreator,
    PluginTemplate,
    TemplateEngine,
)
from .discovery import PluginInfo as DiscoveryPluginInfo
from .discovery import (
    PluginManifestParser,
    PluginMetadataExtractor,
    PluginScanner,
    RepositoryInfo,
    discover_plugins,
    extract_plugin_metadata,
    extract_template_variables,
    resolve_template_variables,
    validate_plugin_manifest,
)

# For backward compatibility, import old classes as stubs
from .discovery_old import PluginDiscovery, PluginSelector, RepositoryPlugins
from .environment import (
    EnvironmentManager,
    EnvironmentStatus,
    Platform,
    ProfileUpdate,
    Shell,
    get_environment_manager,
)
from .marketplace import (
    DependencyConstraint,
    DependencyResolver,
    MarketplaceClient,
    MetadataCache,
    PluginDependency,
    PluginStatus,
    PluginVersion,
    RegistryConfig,
    RegistryType,
    SemanticVersion,
    create_marketplace_client,
    get_plugin_info,
    resolve_plugin_dependencies,
    search_marketplace,
)
from .marketplace import PluginMetadata as MarketplaceMetadata
from .repository import (
    GitError,
    PluginRepo,
    PluginRepositoryManager,
    RepositoryStructureError,
    RepositoryValidationResult,
    UpdateResult,
)
from .repository import PluginInfo as RepoPluginInfo
from .sandbox import PluginSandbox, SandboxConfig, SandboxLevel, SandboxManager, SandboxResult

# Search functionality
from .search import (
    LocalPluginIndex,
    PluginRegistry,
    PluginSearchEngine,
    SearchPluginType,
    SearchResult,
    SortBy,
    get_plugin_recommendations,
    search_plugins,
)

# Sprint 7 features - Security & Marketplace
from .security import (
    AdvancedCommandScanner,
    PermissionAnalyzer,
    PluginManifest,
    PluginManifestValidator,
    PluginSecurityLevel,
    PluginSecurityManager,
    SecurityAuditEntry,
    SecurityAuditLogger,
)
from .security_integration import (
    SecurityValidatorMixin,
    convert_security_issues_to_validation_errors,
    create_security_enhanced_validator,
    enhance_validation_with_security,
    validate_plugin_in_sandbox,
)

# Create aliases for CLI compatibility
RepositoryManager = PluginRepositoryManager
GitRepository = PluginRepo


__all__ = [
    "AdvancedCommandScanner",
    "AtomicFileWriter",
    "ConfigBackup",
    "ConversionResult",
    "CreationMode",
    "CreationPluginType",
    "CreationResult",
    "DependencyConstraint",
    "DependencyResolver",
    "DiscoveryPluginInfo",
    # Environment management
    "EnvironmentManager",
    "EnvironmentStatus",
    "ExtensionInfo",
    "ExtensionToPluginConverter",
    "GitError",
    "GitInitializer",
    "GitRepository",  # Alias
    "LocalPluginIndex",
    # Sprint 7 - Marketplace
    "MarketplaceClient",
    "MarketplaceMetadata",
    "MetadataCache",
    "MetadataCollector",
    "PermissionAnalyzer",
    "Platform",
    "PluginConfigManager",
    # Conversion functionality
    "PluginConverter",
    # Plugin creation
    "PluginCreator",
    "PluginDependency",
    # Backward compatibility
    "PluginDiscovery",
    "PluginManifest",
    "PluginManifestParser",
    "PluginManifestValidator",
    "PluginMetadata",
    "PluginMetadataExtractor",
    "PluginPusher",
    "PluginRegistry",
    "PluginRepo",
    "PluginRepositoryManager",
    "PluginSandbox",
    "PluginScanner",
    # Search functionality
    "PluginSearchEngine",
    "PluginSecurityLevel",
    # Sprint 7 - Security & Sandbox
    "PluginSecurityManager",
    "PluginSelector",
    "PluginStatus",
    "PluginTemplate",
    "PluginVersion",
    "ProfileUpdate",
    "RegistryConfig",
    "RegistryType",
    "RepoPluginInfo",
    "RepositoryInfo",
    "RepositoryManager",  # Alias
    "RepositoryPlugins",
    "RepositoryStructureError",
    "RepositoryValidationResult",
    "SandboxConfig",
    "SandboxLevel",
    "SandboxManager",
    "SandboxResult",
    "SearchPluginType",
    "SearchResult",
    "SecurityAuditEntry",
    "SecurityAuditLogger",
    "SecurityValidatorMixin",
    "SemanticVersion",
    "Shell",
    "SortBy",
    "TemplateEngine",
    "UpdateResult",
    "convert_extensions_to_plugin",
    # Sprint 7 - Security Integration
    "convert_security_issues_to_validation_errors",
    "create_marketplace_client",
    "create_security_enhanced_validator",
    "discover_plugins",
    "enhance_validation_with_security",
    "extract_plugin_metadata",
    "extract_template_variables",
    "get_environment_manager",
    "get_plugin_info",
    "get_plugin_recommendations",
    "resolve_plugin_dependencies",
    "resolve_template_variables",
    "search_marketplace",
    "search_plugins",
    "validate_plugin_in_sandbox",
    "validate_plugin_manifest",
]
