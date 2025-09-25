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

# For backward compatibility, import old classes as stubs
from .discovery_old import PluginDiscovery, PluginSelector, RepositoryPlugins

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

__all__ = [
    "PluginConfigManager",
    "ConfigBackup",
    "AtomicFileWriter",
    "PluginRepositoryManager",
    "RepositoryManager",  # Alias
    "GitRepository",  # Alias
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
    "MetadataCollector",
    # Sprint 7 - Security & Sandbox
    "PluginSecurityManager",
    "PluginSecurityLevel",
    "AdvancedCommandScanner",
    "PluginManifestValidator",
    "PermissionAnalyzer",
    "SecurityAuditLogger",
    "PluginManifest",
    "SecurityAuditEntry",
    "PluginSandbox",
    "SandboxManager",
    "SandboxConfig",
    "SandboxLevel",
    "SandboxResult",
    # Sprint 7 - Marketplace
    "MarketplaceClient",
    "MarketplaceMetadata",
    "PluginVersion",
    "PluginDependency",
    "SemanticVersion",
    "RegistryConfig",
    "RegistryType",
    "PluginStatus",
    "DependencyConstraint",
    "MetadataCache",
    "DependencyResolver",
    "create_marketplace_client",
    "get_plugin_info",
    "search_marketplace",
    "resolve_plugin_dependencies",
    # Sprint 7 - Security Integration
    "convert_security_issues_to_validation_errors",
    "enhance_validation_with_security",
    "validate_plugin_in_sandbox",
    "SecurityValidatorMixin",
    "create_security_enhanced_validator",
]
