"""Project configuration management for pacc.json files."""

import json
import re
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from urllib.parse import urlparse
import logging

from .file_utils import FilePathValidator, PathNormalizer
from ..validation.base import ValidationResult, BaseValidator
from ..validation.formats import JSONValidator
from ..errors.exceptions import (
    PACCError, 
    ConfigurationError, 
    ValidationError,
    ProjectConfigError
)
from .. import __version__ as pacc_version


logger = logging.getLogger(__name__)


@dataclass
class ProjectValidationError:
    """Validation error for project configuration."""
    
    code: str
    message: str
    severity: str = "error"
    context: Optional[str] = None
    line_number: Optional[int] = None
    
    def __str__(self) -> str:
        """Return string representation of error."""
        return f"{self.code}: {self.message}"


@dataclass
class ExtensionSpec:
    """Specification for an extension in pacc.json."""
    
    name: str
    source: str
    version: str
    description: Optional[str] = None
    ref: Optional[str] = None  # Git ref for remote sources
    environment: Optional[str] = None  # Environment restriction
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExtensionSpec':
        """Create ExtensionSpec from dictionary."""
        required_fields = ['name', 'source', 'version']
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing required field: {field_name}")
        
        return cls(
            name=data['name'],
            source=data['source'],
            version=data['version'],
            description=data.get('description'),
            ref=data.get('ref'),
            environment=data.get('environment'),
            dependencies=data.get('dependencies', []),
            metadata=data.get('metadata', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ExtensionSpec to dictionary."""
        result = {
            'name': self.name,
            'source': self.source,
            'version': self.version
        }
        
        if self.description:
            result['description'] = self.description
        if self.ref:
            result['ref'] = self.ref
        if self.environment:
            result['environment'] = self.environment
        if self.dependencies:
            result['dependencies'] = self.dependencies
        if self.metadata:
            result['metadata'] = self.metadata
        
        return result
    
    def is_valid(self) -> bool:
        """Check if extension specification is valid."""
        try:
            # Validate version format (basic semantic versioning)
            if not re.match(r'^\d+\.\d+\.\d+(-\w+(\.\d+)?)?$', self.version):
                return False
            
            # Validate source format
            source_type = self.get_source_type()
            if source_type == "unknown":
                return False
            
            return True
        except Exception:
            return False
    
    def get_source_type(self) -> str:
        """Determine the type of source."""
        if self.source.startswith(('http://', 'https://')):
            if 'github.com' in self.source or 'gitlab.com' in self.source:
                return "git_repository"
            return "url"
        elif self.source.startswith('git+'):
            return "git_repository"
        elif self.source.startswith('./') or self.source.startswith('../'):
            path = Path(self.source)
            if path.suffix in ['.json', '.yaml', '.md']:
                return "local_file"
            return "local_directory"
        else:
            # Assume local relative path
            path = Path(self.source)
            if path.suffix in ['.json', '.yaml', '.md']:
                return "local_file"
            return "local_directory"
    
    def is_local_source(self) -> bool:
        """Check if source is local."""
        return self.get_source_type() in ["local_file", "local_directory"]
    
    def resolve_source_path(self, project_dir: Path) -> Path:
        """Resolve source path relative to project directory."""
        if self.is_local_source():
            return project_dir / self.source
        else:
            raise ValueError(f"Cannot resolve remote source: {self.source}")


@dataclass
class PluginSpec:
    """Specification for a plugin repository in pacc.json."""
    
    repository: str  # owner/repo format
    version: Optional[str] = None  # Git ref (tag, branch, commit)
    plugins: List[str] = field(default_factory=list)  # Specific plugins to enable
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_string(cls, repo_string: str) -> 'PluginSpec':
        """Create PluginSpec from string format 'owner/repo@version'."""
        if '@' in repo_string:
            repository, version = repo_string.split('@', 1)
        else:
            repository, version = repo_string, None
        
        return cls(repository=repository, version=version)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginSpec':
        """Create PluginSpec from dictionary."""
        if 'repository' not in data:
            raise ValueError("Missing required field: repository")
        
        return cls(
            repository=data['repository'],
            version=data.get('version'),
            plugins=data.get('plugins', []),
            metadata=data.get('metadata', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert PluginSpec to dictionary."""
        result = {'repository': self.repository}
        
        if self.version:
            result['version'] = self.version
        if self.plugins:
            result['plugins'] = self.plugins
        if self.metadata:
            result['metadata'] = self.metadata
        
        return result
    
    def get_repo_key(self) -> str:
        """Get repository key in owner/repo format."""
        return self.repository
    
    def get_version_specifier(self) -> str:
        """Get version specifier (tag, branch, commit, or 'latest')."""
        return self.version or 'latest'
    
    def get_git_ref(self) -> str:
        """Get Git reference for checkout operations."""
        if not self.version:
            return 'HEAD'
        
        # Handle special cases
        if self.version in ['latest', 'main', 'master']:
            return self.version if self.version in ['main', 'master'] else 'HEAD'
        
        # For specific versions, return as-is
        return self.version
    
    def is_version_locked(self) -> bool:
        """Check if this is a locked version (specific commit/tag)."""
        if not self.version:
            return False
        
        # Consider it locked if it's not a branch name
        dynamic_refs = ['latest', 'main', 'master', 'develop', 'dev']
        return self.version not in dynamic_refs
    
    def parse_version_components(self) -> Dict[str, str]:
        """Parse version into components for advanced handling."""
        if not self.version:
            return {'type': 'default', 'ref': 'HEAD'}
        
        version = self.version.lower()
        
        # Check for commit SHA pattern (40 hex chars)
        if len(self.version) == 40 and all(c in '0123456789abcdef' for c in version):
            return {'type': 'commit', 'ref': self.version}
        
        # Check for short commit SHA pattern (7-8 hex chars)
        if 7 <= len(self.version) <= 8 and all(c in '0123456789abcdef' for c in version):
            return {'type': 'commit', 'ref': self.version}
        
        # Check for tag patterns (starts with v or has dots)
        if self.version.startswith('v') or '.' in self.version:
            return {'type': 'tag', 'ref': self.version}
        
        # Check for known branch names
        if version in ['main', 'master', 'develop', 'dev', 'latest']:
            return {'type': 'branch', 'ref': self.version if version != 'latest' else 'main'}
        
        # Default to branch
        return {'type': 'branch', 'ref': self.version}
    
    def is_valid(self) -> bool:
        """Check if plugin specification is valid."""
        # Validate repository format
        pattern = r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$'
        return bool(re.match(pattern, self.repository))


@dataclass
class PluginSyncResult:
    """Result of plugin synchronization."""
    
    success: bool
    installed_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_plugins: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigValidationResult:
    """Result of project configuration validation."""
    
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    extension_count: int = 0
    environment_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, code: str, message: str, context: Optional[str] = None):
        """Add validation error."""
        error = ProjectValidationError(
            code=code,
            message=message,
            severity="error",
            context=context
        )
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, code: str, message: str, context: Optional[str] = None):
        """Add validation warning."""
        warning = ProjectValidationError(
            code=code,
            message=message,
            severity="warning",
            context=context
        )
        self.warnings.append(warning)


@dataclass
class ProjectSyncResult:
    """Result of project synchronization."""
    
    success: bool
    installed_count: int = 0
    updated_count: int = 0
    failed_extensions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ProjectConfigSchema:
    """Validates project configuration schema."""
    
    def __init__(self):
        self.json_validator = JSONValidator()
        self.version_pattern = re.compile(r'^\d+\.\d+\.\d+(-\w+(\.\d+)?)?$')
    
    def validate(self, config: Dict[str, Any]) -> ConfigValidationResult:
        """Validate project configuration schema."""
        result = ConfigValidationResult(is_valid=True)
        
        # Validate required fields
        self._validate_required_fields(config, result)
        
        # Validate project metadata
        self._validate_project_metadata(config, result)
        
        # Validate extensions structure
        self._validate_extensions_structure(config, result)
        
        # Validate plugins structure (team collaboration)
        self._validate_plugins_structure(config, result)
        
        # Validate environments structure
        self._validate_environments_structure(config, result)
        
        # Count extensions for metadata
        result.extension_count = self._count_extensions(config)
        result.environment_count = len(config.get('environments', {}))
        
        return result
    
    def _validate_required_fields(self, config: Dict[str, Any], result: ConfigValidationResult):
        """Validate required fields in configuration."""
        required_fields = ['name', 'version']
        
        for field in required_fields:
            if field not in config:
                result.add_error(
                    "MISSING_REQUIRED_FIELD",
                    f"Missing required field: {field}"
                )
    
    def _validate_project_metadata(self, config: Dict[str, Any], result: ConfigValidationResult):
        """Validate project metadata fields."""
        # Validate project name
        if 'name' in config:
            name = config['name']
            if not isinstance(name, str) or not name.strip():
                result.add_error(
                    "INVALID_PROJECT_NAME",
                    "Project name must be a non-empty string"
                )
        
        # Validate version
        if 'version' in config:
            version = config['version']
            if not isinstance(version, str) or not self.version_pattern.match(version):
                result.add_error(
                    "INVALID_VERSION_FORMAT",
                    f"Invalid version format: {version}. Expected semantic version (e.g., 1.0.0)"
                )
        
        # Validate description (optional)
        if 'description' in config:
            description = config['description']
            if not isinstance(description, str):
                result.add_warning(
                    "INVALID_DESCRIPTION",
                    "Project description should be a string"
                )
    
    def _validate_extensions_structure(self, config: Dict[str, Any], result: ConfigValidationResult):
        """Validate extensions structure."""
        if 'extensions' not in config:
            result.add_warning(
                "NO_EXTENSIONS",
                "No extensions defined in project configuration"
            )
            return
        
        extensions = config['extensions']
        if not isinstance(extensions, dict):
            result.add_error(
                "INVALID_EXTENSIONS_STRUCTURE",
                "Extensions must be an object"
            )
            return
        
        valid_extension_types = ['hooks', 'mcps', 'agents', 'commands']
        
        for ext_type, ext_list in extensions.items():
            if ext_type not in valid_extension_types:
                result.add_warning(
                    "UNKNOWN_EXTENSION_TYPE",
                    f"Unknown extension type: {ext_type}"
                )
                continue
            
            if not isinstance(ext_list, list):
                result.add_error(
                    "INVALID_EXTENSION_LIST",
                    f"Extension type '{ext_type}' must be an array"
                )
                continue
            
            # Validate individual extension specs
            for i, ext_spec in enumerate(ext_list):
                self._validate_extension_spec(ext_spec, ext_type, i, result)
    
    def _validate_extension_spec(self, ext_spec: Dict[str, Any], ext_type: str, index: int, result: ConfigValidationResult):
        """Validate individual extension specification."""
        context = f"{ext_type}[{index}]"
        
        # Required fields for extension spec
        required_fields = ['name', 'source', 'version']
        for field in required_fields:
            if field not in ext_spec:
                result.add_error(
                    "MISSING_EXTENSION_FIELD",
                    f"Missing required field '{field}' in extension",
                    context
                )
        
        # Validate extension name
        if 'name' in ext_spec:
            name = ext_spec['name']
            if not isinstance(name, str) or not name.strip():
                result.add_error(
                    "INVALID_EXTENSION_NAME",
                    "Extension name must be a non-empty string",
                    context
                )
        
        # Validate source
        if 'source' in ext_spec:
            source = ext_spec['source']
            if not isinstance(source, str) or not source.strip():
                result.add_error(
                    "INVALID_EXTENSION_SOURCE",
                    "Extension source must be a non-empty string",
                    context
                )
        
        # Validate version
        if 'version' in ext_spec:
            version = ext_spec['version']
            if not isinstance(version, str) or not self.version_pattern.match(version):
                result.add_error(
                    "INVALID_EXTENSION_VERSION",
                    f"Invalid extension version format: {version}",
                    context
                )
    
    def _validate_plugins_structure(self, config: Dict[str, Any], result: ConfigValidationResult):
        """Validate plugins structure for team collaboration."""
        if 'plugins' not in config:
            return  # Plugins are optional
        
        plugins = config['plugins']
        if not isinstance(plugins, dict):
            result.add_error(
                "INVALID_PLUGINS_STRUCTURE",
                "Plugins must be an object"
            )
            return
        
        # Validate repositories list
        if 'repositories' in plugins:
            repositories = plugins['repositories']
            if not isinstance(repositories, list):
                result.add_error(
                    "INVALID_REPOSITORIES_STRUCTURE",
                    "Plugins repositories must be an array"
                )
            else:
                for i, repo in enumerate(repositories):
                    self._validate_repository_spec(repo, i, result)
        
        # Validate required plugins list
        if 'required' in plugins:
            required = plugins['required']
            if not isinstance(required, list):
                result.add_error(
                    "INVALID_REQUIRED_PLUGINS",
                    "Required plugins must be an array"
                )
            else:
                for i, plugin_name in enumerate(required):
                    if not isinstance(plugin_name, str) or not plugin_name.strip():
                        result.add_error(
                            "INVALID_REQUIRED_PLUGIN_NAME",
                            f"Required plugin name at index {i} must be a non-empty string"
                        )
        
        # Validate optional plugins list
        if 'optional' in plugins:
            optional = plugins['optional']
            if not isinstance(optional, list):
                result.add_error(
                    "INVALID_OPTIONAL_PLUGINS",
                    "Optional plugins must be an array"
                )
            else:
                for i, plugin_name in enumerate(optional):
                    if not isinstance(plugin_name, str) or not plugin_name.strip():
                        result.add_error(
                            "INVALID_OPTIONAL_PLUGIN_NAME",
                            f"Optional plugin name at index {i} must be a non-empty string"
                        )
    
    def _validate_repository_spec(self, repo_spec: Any, index: int, result: ConfigValidationResult):
        """Validate individual repository specification."""
        context = f"repositories[{index}]"
        
        if isinstance(repo_spec, str):
            # Simple string format: "owner/repo@version"
            if not self._validate_repository_string(repo_spec):
                result.add_error(
                    "INVALID_REPOSITORY_FORMAT",
                    f"Invalid repository format: {repo_spec}. Expected 'owner/repo' or 'owner/repo@version'",
                    context
                )
        elif isinstance(repo_spec, dict):
            # Object format with detailed configuration
            required_fields = ['repository']
            for field in required_fields:
                if field not in repo_spec:
                    result.add_error(
                        "MISSING_REPOSITORY_FIELD",
                        f"Missing required field '{field}' in repository specification",
                        context
                    )
            
            # Validate repository field
            if 'repository' in repo_spec:
                repo_name = repo_spec['repository']
                if not isinstance(repo_name, str) or not self._validate_repository_string(repo_name):
                    result.add_error(
                        "INVALID_REPOSITORY_NAME",
                        f"Invalid repository name: {repo_name}",
                        context
                    )
            
            # Validate optional version field
            if 'version' in repo_spec:
                version = repo_spec['version']
                if not isinstance(version, str) or not version.strip():
                    result.add_error(
                        "INVALID_REPOSITORY_VERSION",
                        "Repository version must be a non-empty string",
                        context
                    )
        else:
            result.add_error(
                "INVALID_REPOSITORY_TYPE",
                "Repository specification must be a string or object",
                context
            )
    
    def _validate_repository_string(self, repo_str: str) -> bool:
        """Validate repository string format."""
        # Pattern: owner/repo or owner/repo@version
        pattern = r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(@[a-zA-Z0-9_.-]+)?$'
        return bool(re.match(pattern, repo_str))

    def _validate_environments_structure(self, config: Dict[str, Any], result: ConfigValidationResult):
        """Validate environments structure."""
        if 'environments' not in config:
            return  # Environments are optional
        
        environments = config['environments']
        if not isinstance(environments, dict):
            result.add_error(
                "INVALID_ENVIRONMENTS_STRUCTURE",
                "Environments must be an object"
            )
            return
        
        for env_name, env_config in environments.items():
            if not isinstance(env_config, dict):
                result.add_error(
                    "INVALID_ENVIRONMENT_CONFIG",
                    f"Environment '{env_name}' configuration must be an object"
                )
                continue
            
            # Validate environment extensions if present
            if 'extensions' in env_config:
                # Recursively validate environment extensions
                env_validation_config = {'extensions': env_config['extensions']}
                self._validate_extensions_structure(env_validation_config, result)
            
            # Validate environment plugins if present
            if 'plugins' in env_config:
                # Recursively validate environment plugins
                env_validation_config = {'plugins': env_config['plugins']}
                self._validate_plugins_structure(env_validation_config, result)
    
    def _count_extensions(self, config: Dict[str, Any]) -> int:
        """Count total number of extensions in configuration."""
        count = 0
        extensions = config.get('extensions', {})
        
        for ext_list in extensions.values():
            if isinstance(ext_list, list):
                count += len(ext_list)
        
        # Count environment extensions
        environments = config.get('environments', {})
        for env_config in environments.values():
            if isinstance(env_config, dict) and 'extensions' in env_config:
                env_extensions = env_config['extensions']
                for ext_list in env_extensions.values():
                    if isinstance(ext_list, list):
                        count += len(ext_list)
        
        return count


class ProjectConfigManager:
    """Manages project configuration files (pacc.json)."""
    
    def __init__(self):
        self.file_validator = FilePathValidator(allowed_extensions={'.json'})
        self.path_normalizer = PathNormalizer()
        self.schema = ProjectConfigSchema()
    
    def init_project_config(self, project_dir: Path, config: Dict[str, Any]) -> None:
        """Initialize project configuration file."""
        config_path = self._get_config_path(project_dir)
        
        # Add metadata
        if 'metadata' not in config:
            config['metadata'] = {}
        
        config['metadata'].update({
            'created_at': datetime.now(timezone.utc).isoformat(),
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'pacc_version': pacc_version
        })
        
        # Validate configuration
        validation_result = self.schema.validate(config)
        if not validation_result.is_valid:
            errors = [str(error) for error in validation_result.errors]
            raise ConfigurationError(f"Invalid project configuration: {'; '.join(errors)}")
        
        # Ensure project directory exists
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Write configuration file
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Initialized project configuration: {config_path}")
    
    def load_project_config(self, project_dir: Path) -> Optional[Dict[str, Any]]:
        """Load project configuration from pacc.json."""
        config_path = self._get_config_path(project_dir)
        
        if not config_path.exists():
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            logger.debug(f"Loaded project configuration: {config_path}")
            return config
            
        except (json.JSONDecodeError, OSError) as e:
            raise ConfigurationError(f"Failed to load project configuration from {config_path}: {e}")
    
    def save_project_config(self, project_dir: Path, config: Dict[str, Any]) -> None:
        """Save project configuration to pacc.json."""
        config_path = self._get_config_path(project_dir)
        
        # Update metadata
        if 'metadata' not in config:
            config['metadata'] = {}
        
        config['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat()
        
        # Validate configuration
        validation_result = self.schema.validate(config)
        if not validation_result.is_valid:
            errors = [str(error) for error in validation_result.errors]
            raise ConfigurationError(f"Invalid project configuration: {'; '.join(errors)}")
        
        # Create backup if file exists
        if config_path.exists():
            backup_path = config_path.with_suffix('.json.backup')
            shutil.copy2(config_path, backup_path)
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved project configuration: {config_path}")
            
        except OSError as e:
            raise ConfigurationError(f"Failed to save project configuration to {config_path}: {e}")
    
    def update_project_config(self, project_dir: Path, updates: Dict[str, Any]) -> None:
        """Update project configuration with new values."""
        config = self.load_project_config(project_dir)
        if config is None:
            raise ConfigurationError(f"No project configuration found in {project_dir}")
        
        # Deep merge updates into existing config
        self._deep_merge(config, updates)
        
        # Save updated configuration
        self.save_project_config(project_dir, config)
    
    def add_extension_to_config(self, project_dir: Path, extension_type: str, extension_spec: Dict[str, Any]) -> None:
        """Add extension specification to project configuration."""
        config = self.load_project_config(project_dir)
        if config is None:
            raise ConfigurationError(f"No project configuration found in {project_dir}")
        
        # Ensure extensions section exists
        if 'extensions' not in config:
            config['extensions'] = {}
        
        if extension_type not in config['extensions']:
            config['extensions'][extension_type] = []
        
        # Check for duplicates
        existing_names = {ext['name'] for ext in config['extensions'][extension_type]}
        if extension_spec['name'] in existing_names:
            raise ConfigurationError(f"Extension '{extension_spec['name']}' already exists in {extension_type}")
        
        # Add extension
        config['extensions'][extension_type].append(extension_spec)
        
        # Save updated configuration
        self.save_project_config(project_dir, config)
        
        logger.info(f"Added {extension_type} extension '{extension_spec['name']}' to project configuration")
    
    def remove_extension_from_config(self, project_dir: Path, extension_type: str, extension_name: str) -> bool:
        """Remove extension specification from project configuration."""
        config = self.load_project_config(project_dir)
        if config is None:
            raise ConfigurationError(f"No project configuration found in {project_dir}")
        
        # Check if extension exists
        if 'extensions' not in config or extension_type not in config['extensions']:
            return False
        
        extensions = config['extensions'][extension_type]
        original_count = len(extensions)
        
        # Remove extension with matching name
        config['extensions'][extension_type] = [
            ext for ext in extensions 
            if ext.get('name') != extension_name
        ]
        
        if len(config['extensions'][extension_type]) == original_count:
            return False  # Extension not found
        
        # Save updated configuration
        self.save_project_config(project_dir, config)
        
        logger.info(f"Removed {extension_type} extension '{extension_name}' from project configuration")
        return True
    
    def validate_project_config(self, project_dir: Path) -> ConfigValidationResult:
        """Validate project configuration."""
        config = self.load_project_config(project_dir)
        if config is None:
            result = ConfigValidationResult(is_valid=False)
            result.add_error("NO_CONFIG_FILE", "No pacc.json file found in project directory")
            return result
        
        return self.schema.validate(config)
    
    def get_extensions_for_environment(self, config: Dict[str, Any], environment: str = "default") -> Dict[str, List[Dict[str, Any]]]:
        """Get merged extensions for specific environment."""
        # Start with base extensions
        base_extensions = config.get('extensions', {})
        merged_extensions = {}
        
        # Deep copy base extensions
        for ext_type, ext_list in base_extensions.items():
            merged_extensions[ext_type] = [ext.copy() for ext in ext_list]
        
        # Apply environment-specific extensions
        if environment != "default" and 'environments' in config:
            env_config = config['environments'].get(environment, {})
            env_extensions = env_config.get('extensions', {})
            
            for ext_type, ext_list in env_extensions.items():
                if ext_type not in merged_extensions:
                    merged_extensions[ext_type] = []
                
                # Add environment extensions (avoiding duplicates by name)
                existing_names = {ext['name'] for ext in merged_extensions[ext_type]}
                for ext in ext_list:
                    if ext['name'] not in existing_names:
                        merged_extensions[ext_type].append(ext.copy())
        
        return merged_extensions
    
    def _get_config_path(self, project_dir: Path) -> Path:
        """Get path to project configuration file."""
        return project_dir / "pacc.json"
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Deep merge source dictionary into target dictionary."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


class ProjectSyncManager:
    """Manages synchronization of project extensions from pacc.json."""
    
    def __init__(self):
        self.config_manager = ProjectConfigManager()
    
    def sync_project(self, project_dir: Path, environment: str = "default", dry_run: bool = False) -> ProjectSyncResult:
        """Synchronize project extensions based on pacc.json configuration."""
        result = ProjectSyncResult(success=True)
        
        try:
            # Load project configuration
            config = self.config_manager.load_project_config(project_dir)
            if config is None:
                result.success = False
                result.error_message = f"pacc.json not found in {project_dir}"
                return result
            
            # Get extensions for environment
            extensions = self.config_manager.get_extensions_for_environment(config, environment)
            
            # Install each extension
            installer = get_extension_installer()
            
            for ext_type, ext_list in extensions.items():
                for ext_spec_dict in ext_list:
                    try:
                        ext_spec = ExtensionSpec.from_dict(ext_spec_dict)
                        
                        if dry_run:
                            logger.info(f"Would install {ext_type}: {ext_spec.name} from {ext_spec.source}")
                        else:
                            success = installer.install_extension(ext_spec, ext_type, project_dir)
                            
                            if success:
                                result.installed_count += 1
                                logger.info(f"Installed {ext_type}: {ext_spec.name}")
                            else:
                                result.failed_extensions.append(f"{ext_type}/{ext_spec.name}")
                                result.warnings.append(f"Failed to install {ext_type}: {ext_spec.name}")
                    
                    except Exception as e:
                        result.failed_extensions.append(f"{ext_type}/{ext_spec_dict.get('name', 'unknown')}")
                        result.warnings.append(f"Failed to install {ext_type}: {e}")
            
            # Check if any installations failed
            if result.failed_extensions:
                result.success = False
                result.error_message = f"Failed to install {len(result.failed_extensions)} extensions"
            
            logger.info(f"Project sync completed: {result.installed_count} installed, {len(result.failed_extensions)} failed")
            
        except Exception as e:
            result.success = False
            result.error_message = f"Project sync failed: {e}"
            logger.error(f"Project sync error: {e}")
        
        return result


@dataclass 
class ConflictResolution:
    """Configuration for resolving conflicts between multiple pacc.json files."""
    
    strategy: str = "merge"  # "merge", "local", "team", "prompt"
    prefer_local_versions: bool = False
    allow_version_downgrades: bool = False
    merge_required_and_optional: bool = True
    conflict_plugins: List[str] = field(default_factory=list)
    
    def should_prompt_user(self) -> bool:
        """Check if user interaction is required."""
        return self.strategy == "prompt" or bool(self.conflict_plugins)


@dataclass
class ConfigSource:
    """Represents a source of configuration (team, local, environment)."""
    
    name: str
    path: Path
    config: Dict[str, Any]
    priority: int = 0  # Higher number = higher priority
    is_local: bool = False
    
    def get_plugins_config(self) -> Dict[str, Any]:
        """Get plugins configuration from this source."""
        return self.config.get('plugins', {})


class PluginSyncManager:
    """Manages synchronization of plugins for team collaboration."""
    
    def __init__(self):
        self.config_manager = ProjectConfigManager()
        
    def sync_plugins(self, project_dir: Path, environment: str = "default", dry_run: bool = False) -> PluginSyncResult:
        """Synchronize plugins based on pacc.json configuration."""
        result = PluginSyncResult(success=True)
        
        try:
            # Load project configuration
            config = self.config_manager.load_project_config(project_dir)
            if config is None:
                result.success = False
                result.error_message = f"pacc.json not found in {project_dir}"
                return result
            
            # Get plugins configuration
            plugins_config = self._get_plugins_for_environment(config, environment)
            if not plugins_config:
                result.success = True
                result.error_message = "No plugins configuration found"
                return result
            
            # Parse repository specifications
            repositories = self._parse_repository_specs(plugins_config.get('repositories', []))
            required_plugins = set(plugins_config.get('required', []))
            optional_plugins = set(plugins_config.get('optional', []))
            
            # Get plugin manager for operations
            plugin_manager = self._get_plugin_manager()
            
            # Get currently installed plugins
            installed_plugins = self._get_installed_plugins(plugin_manager)
            
            # Process each repository
            for repo_spec in repositories:
                try:
                    sync_result = self._sync_repository(
                        repo_spec, required_plugins, optional_plugins, 
                        installed_plugins, plugin_manager, dry_run
                    )
                    
                    result.installed_count += sync_result.get('installed', 0)
                    result.updated_count += sync_result.get('updated', 0)
                    result.skipped_count += sync_result.get('skipped', 0)
                    
                    if sync_result.get('failed'):
                        result.failed_plugins.extend(sync_result['failed'])
                    
                except Exception as e:
                    error_msg = f"Failed to sync repository {repo_spec.repository}: {e}"
                    result.failed_plugins.append(repo_spec.repository)
                    result.warnings.append(error_msg)
                    logger.error(error_msg)
            
            # Check for missing required plugins
            missing_required = self._check_missing_required_plugins(
                required_plugins, installed_plugins, repositories
            )
            if missing_required:
                result.warnings.extend([
                    f"Required plugin not found: {plugin}" for plugin in missing_required
                ])
            
            # Set final result status
            if result.failed_plugins or missing_required:
                result.success = False
                result.error_message = f"Failed to sync {len(result.failed_plugins)} plugins"
            
            logger.info(
                f"Plugin sync completed: {result.installed_count} installed, "
                f"{result.updated_count} updated, {result.skipped_count} skipped, "
                f"{len(result.failed_plugins)} failed"
            )
            
        except Exception as e:
            result.success = False
            result.error_message = f"Plugin sync failed: {e}"
            logger.error(f"Plugin sync error: {e}")
        
        return result
    
    def _get_plugins_for_environment(self, config: Dict[str, Any], environment: str) -> Dict[str, Any]:
        """Get merged plugins configuration for specific environment."""
        base_plugins = config.get('plugins', {})
        
        if environment == "default" or 'environments' not in config:
            return base_plugins
        
        # Merge with environment-specific plugins
        env_config = config.get('environments', {}).get(environment, {})
        env_plugins = env_config.get('plugins', {})
        
        # Deep merge plugins configurations
        merged = base_plugins.copy()
        
        # Merge repositories
        if 'repositories' in env_plugins:
            base_repos = merged.get('repositories', [])
            env_repos = env_plugins['repositories']
            merged['repositories'] = base_repos + env_repos
        
        # Merge required/optional lists
        for plugin_type in ['required', 'optional']:
            if plugin_type in env_plugins:
                base_list = set(merged.get(plugin_type, []))
                env_list = set(env_plugins[plugin_type])
                merged[plugin_type] = list(base_list.union(env_list))
        
        return merged
    
    def _parse_repository_specs(self, repositories: List[Union[str, Dict[str, Any]]]) -> List[PluginSpec]:
        """Parse repository specifications from configuration."""
        specs = []
        
        for repo_data in repositories:
            try:
                if isinstance(repo_data, str):
                    spec = PluginSpec.from_string(repo_data)
                elif isinstance(repo_data, dict):
                    spec = PluginSpec.from_dict(repo_data)
                else:
                    logger.warning(f"Invalid repository specification: {repo_data}")
                    continue
                
                if spec.is_valid():
                    specs.append(spec)
                else:
                    logger.warning(f"Invalid repository format: {spec.repository}")
            
            except Exception as e:
                logger.error(f"Failed to parse repository specification: {e}")
        
        return specs
    
    def _sync_repository(
        self, 
        repo_spec: PluginSpec, 
        required_plugins: Set[str], 
        optional_plugins: Set[str],
        installed_plugins: Dict[str, Any],
        plugin_manager: Any,
        dry_run: bool
    ) -> Dict[str, Any]:
        """Sync a single repository with differential updates."""
        result = {
            'installed': 0,
            'updated': 0,
            'skipped': 0,
            'failed': []
        }
        
        repo_key = repo_spec.get_repo_key()
        
        # Check if repository is already installed
        if repo_key in installed_plugins:
            # Get repository path for version checking
            owner, repo = repo_key.split("/", 1)
            repo_path = Path.home() / ".claude" / "plugins" / "repos" / owner / repo
            
            if repo_path.exists():
                # Resolve target version to commit SHA for accurate comparison
                target_commit = self._resolve_version_to_commit(repo_spec, repo_path)
                current_commit = self._get_current_commit(repo_path)
                
                if target_commit and current_commit and target_commit != current_commit:
                    if dry_run:
                        logger.info(f"Would update repository {repo_key} to {repo_spec.get_version_specifier()} ({target_commit[:8]})")
                    else:
                        # Perform version-locked update
                        if self._checkout_version(repo_spec, repo_path):
                            # Update metadata with resolved commit
                            success = plugin_manager.update_repository(repo_key, target_commit)
                            if success:
                                result['updated'] += 1
                                logger.info(f"Updated repository {repo_key} to {repo_spec.get_version_specifier()}")
                            else:
                                result['failed'].append(repo_key)
                        else:
                            result['failed'].append(repo_key)
                            logger.error(f"Failed to checkout version {repo_spec.get_version_specifier()} for {repo_key}")
                else:
                    result['skipped'] += 1
                    logger.debug(f"Repository {repo_key} already at target version")
            else:
                # Repository directory missing, treat as new installation
                logger.warning(f"Repository {repo_key} config exists but directory missing, reinstalling")
                if dry_run:
                    logger.info(f"Would reinstall repository {repo_key}@{repo_spec.get_version_specifier()}")
                else:
                    success = plugin_manager.install_repository(repo_spec)
                    if success:
                        result['installed'] += 1
                        logger.info(f"Reinstalled repository {repo_key}")
                    else:
                        result['failed'].append(repo_key)
        else:
            # Install new repository
            if dry_run:
                logger.info(f"Would install repository {repo_key}@{repo_spec.get_version_specifier()}")
            else:
                success = plugin_manager.install_repository(repo_spec)
                if success:
                    # After installation, checkout the specific version if needed
                    if repo_spec.version and repo_spec.is_version_locked():
                        owner, repo = repo_key.split("/", 1)
                        repo_path = Path.home() / ".claude" / "plugins" / "repos" / owner / repo
                        if repo_path.exists():
                            self._checkout_version(repo_spec, repo_path)
                    
                    result['installed'] += 1
                    logger.info(f"Installed repository {repo_key}")
                else:
                    result['failed'].append(repo_key)
        
        # Handle specific plugin enablement within repository
        if repo_spec.plugins:
            for plugin_name in repo_spec.plugins:
                if plugin_name in required_plugins or plugin_name in optional_plugins:
                    if dry_run:
                        logger.info(f"Would enable plugin {plugin_name} in {repo_key}")
                    else:
                        plugin_manager.enable_plugin(repo_key, plugin_name)
        
        return result
    
    def _needs_update(self, current_version: str, target_version: str) -> bool:
        """Check if repository needs to be updated."""
        if target_version in ['latest', 'main', 'master']:
            return True  # Always update for latest/main/master
        
        return current_version != target_version
    
    def _resolve_version_to_commit(self, repo_spec: PluginSpec, repo_path: Path) -> Optional[str]:
        """Resolve version specifier to actual commit SHA."""
        try:
            import subprocess
            
            version_info = repo_spec.parse_version_components()
            ref = version_info['ref']
            
            # Fetch latest from remote to ensure we have all refs
            subprocess.run(
                ["git", "fetch", "--quiet"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                timeout=60
            )
            
            # Resolve reference to commit SHA
            if version_info['type'] == 'commit':
                # Verify commit exists
                result = subprocess.run(
                    ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.stdout.strip() if result.returncode == 0 else None
            
            elif version_info['type'] == 'tag':
                # Resolve tag to commit
                result = subprocess.run(
                    ["git", "rev-parse", f"refs/tags/{ref}^{{commit}}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return result.stdout.strip()
                
                # Try without refs/tags prefix
                result = subprocess.run(
                    ["git", "rev-parse", f"{ref}^{{commit}}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.stdout.strip() if result.returncode == 0 else None
            
            elif version_info['type'] == 'branch':
                # Resolve branch to commit (prefer remote)
                remote_ref = f"origin/{ref}"
                result = subprocess.run(
                    ["git", "rev-parse", f"{remote_ref}^{{commit}}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return result.stdout.strip()
                
                # Fallback to local branch
                result = subprocess.run(
                    ["git", "rev-parse", f"{ref}^{{commit}}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.stdout.strip() if result.returncode == 0 else None
            
            else:
                # Default case
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.stdout.strip() if result.returncode == 0 else None
        
        except Exception as e:
            logger.error(f"Failed to resolve version {repo_spec.version} for {repo_spec.repository}: {e}")
            return None
    
    def _checkout_version(self, repo_spec: PluginSpec, repo_path: Path) -> bool:
        """Checkout specific version in repository."""
        try:
            import subprocess
            
            version_info = repo_spec.parse_version_components()
            ref = version_info['ref']
            
            logger.info(f"Checking out {version_info['type']} '{ref}' in {repo_spec.repository}")
            
            # For commits and tags, checkout directly
            if version_info['type'] in ['commit', 'tag']:
                result = subprocess.run(
                    ["git", "checkout", "--quiet", ref],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    logger.info(f"Successfully checked out {version_info['type']} {ref}")
                    return True
                else:
                    logger.error(f"Failed to checkout {ref}: {result.stderr}")
                    return False
            
            # For branches, checkout and potentially track remote
            elif version_info['type'] == 'branch':
                # Try to checkout remote branch first
                remote_ref = f"origin/{ref}"
                result = subprocess.run(
                    ["git", "checkout", "--quiet", "-B", ref, remote_ref],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    logger.info(f"Successfully checked out branch {ref} from remote")
                    return True
                
                # Fallback to local branch
                result = subprocess.run(
                    ["git", "checkout", "--quiet", ref],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    logger.info(f"Successfully checked out local branch {ref}")
                    return True
                else:
                    logger.error(f"Failed to checkout branch {ref}: {result.stderr}")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to checkout version for {repo_spec.repository}: {e}")
            return False
    
    def _get_current_commit(self, repo_path: Path) -> Optional[str]:
        """Get current commit SHA of repository."""
        try:
            import subprocess
            
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.warning(f"Failed to get current commit for {repo_path}: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get current commit for {repo_path}: {e}")
            return None
    
    def _get_installed_plugins(self, plugin_manager: Any) -> Dict[str, Any]:
        """Get currently installed plugins."""
        try:
            return plugin_manager.list_installed_repositories()
        except Exception as e:
            logger.error(f"Failed to get installed plugins: {e}")
            return {}
    
    def _check_missing_required_plugins(
        self, 
        required_plugins: Set[str], 
        installed_plugins: Dict[str, Any],
        repositories: List[PluginSpec]
    ) -> List[str]:
        """Check for missing required plugins."""
        # Get all available plugins from repositories
        available_plugins = set()
        for repo_spec in repositories:
            available_plugins.update(repo_spec.plugins)
        
        # Find missing required plugins
        missing = []
        for plugin in required_plugins:
            if plugin not in available_plugins:
                missing.append(plugin)
        
        return missing
    
    def _get_plugin_manager(self):
        """Get plugin manager instance."""
        # Import here to avoid circular imports
        from ..plugins.config import PluginConfigManager
        return PluginConfigManager()
    
    def sync_plugins_with_conflict_resolution(
        self, 
        project_dir: Path, 
        environment: str = "default", 
        dry_run: bool = False,
        conflict_resolution: Optional[ConflictResolution] = None
    ) -> PluginSyncResult:
        """Synchronize plugins with advanced conflict resolution."""
        try:
            # Discover all configuration sources
            config_sources = self._discover_config_sources(project_dir, environment)
            
            if not config_sources:
                result = PluginSyncResult(success=False)
                result.error_message = "No configuration sources found"
                return result
            
            # Merge configurations with conflict detection
            merged_config, conflicts = self._merge_plugin_configs(config_sources, conflict_resolution)
            
            # Handle conflicts if any
            if conflicts and conflict_resolution and conflict_resolution.should_prompt_user():
                # This would show interactive conflict resolution UI
                # For now, log conflicts
                for conflict in conflicts:
                    logger.warning(f"Configuration conflict: {conflict}")
            
            # Use merged configuration for sync
            return self._sync_with_merged_config(
                project_dir, merged_config, environment, dry_run
            )
            
        except Exception as e:
            result = PluginSyncResult(success=False)
            result.error_message = f"Sync with conflict resolution failed: {e}"
            logger.error(f"Sync error: {e}")
            return result
    
    def _discover_config_sources(self, project_dir: Path, environment: str) -> List[ConfigSource]:
        """Discover all available configuration sources."""
        sources = []
        
        # Team configuration (pacc.json in project root)
        team_config_path = project_dir / "pacc.json"
        if team_config_path.exists():
            try:
                team_config = self.config_manager.load_project_config(project_dir)
                if team_config:
                    sources.append(ConfigSource(
                        name="team",
                        path=team_config_path,
                        config=team_config,
                        priority=10,
                        is_local=False
                    ))
            except Exception as e:
                logger.warning(f"Failed to load team config: {e}")
        
        # Local configuration (pacc.local.json)
        local_config_path = project_dir / "pacc.local.json"
        if local_config_path.exists():
            try:
                with open(local_config_path, 'r', encoding='utf-8') as f:
                    local_config = json.load(f)
                sources.append(ConfigSource(
                    name="local",
                    path=local_config_path,
                    config=local_config,
                    priority=20,  # Local takes precedence
                    is_local=True
                ))
            except Exception as e:
                logger.warning(f"Failed to load local config: {e}")
        
        # Global user configuration (optional)
        global_config_path = Path.home() / ".claude" / "pacc.json"
        if global_config_path.exists():
            try:
                with open(global_config_path, 'r', encoding='utf-8') as f:
                    global_config = json.load(f)
                sources.append(ConfigSource(
                    name="global",
                    path=global_config_path,
                    config=global_config,
                    priority=5,  # Lowest priority
                    is_local=False
                ))
            except Exception as e:
                logger.warning(f"Failed to load global config: {e}")
        
        # Sort by priority (lower numbers processed first)
        sources.sort(key=lambda s: s.priority)
        
        return sources
    
    def _merge_plugin_configs(
        self, 
        sources: List[ConfigSource], 
        conflict_resolution: Optional[ConflictResolution]
    ) -> Tuple[Dict[str, Any], List[str]]:
        """Merge plugin configurations from multiple sources."""
        merged = {
            'repositories': [],
            'required': [],
            'optional': []
        }
        conflicts = []
        repo_versions = {}  # Track version conflicts
        
        for source in sources:
            plugins_config = source.get_plugins_config()
            
            # Merge repositories
            for repo in plugins_config.get('repositories', []):
                repo_spec = self._parse_single_repository(repo)
                if repo_spec:
                    repo_key = repo_spec.get_repo_key()
                    
                    # Check for version conflicts
                    if repo_key in repo_versions:
                        existing_version = repo_versions[repo_key]['version']
                        new_version = repo_spec.get_version_specifier()
                        
                        if existing_version != new_version:
                            conflict_msg = (
                                f"Version conflict for {repo_key}: "
                                f"{repo_versions[repo_key]['source']} wants {existing_version}, "
                                f"{source.name} wants {new_version}"
                            )
                            conflicts.append(conflict_msg)
                            
                            # Resolve conflict
                            resolved_version = self._resolve_version_conflict(
                                repo_key, existing_version, new_version, 
                                repo_versions[repo_key]['source'], source.name,
                                conflict_resolution
                            )
                            
                            if resolved_version:
                                repo_spec.version = resolved_version
                                repo_versions[repo_key] = {
                                    'version': resolved_version,
                                    'source': f"resolved({source.name})"
                                }
                    else:
                        repo_versions[repo_key] = {
                            'version': repo_spec.get_version_specifier(),
                            'source': source.name
                        }
                    
                    # Add to merged repositories (replace if exists)
                    existing_repo_index = None
                    for i, existing_repo in enumerate(merged['repositories']):
                        if existing_repo.get_repo_key() == repo_key:
                            existing_repo_index = i
                            break
                    
                    if existing_repo_index is not None:
                        merged['repositories'][existing_repo_index] = repo_spec
                    else:
                        merged['repositories'].append(repo_spec)
            
            # Merge required/optional lists (union)
            for list_type in ['required', 'optional']:
                current_list = set(merged[list_type])
                source_list = set(plugins_config.get(list_type, []))
                merged[list_type] = list(current_list.union(source_list))
        
        return merged, conflicts
    
    def _parse_single_repository(self, repo_data: Union[str, Dict[str, Any]]) -> Optional[PluginSpec]:
        """Parse a single repository specification."""
        try:
            if isinstance(repo_data, str):
                return PluginSpec.from_string(repo_data)
            elif isinstance(repo_data, dict):
                return PluginSpec.from_dict(repo_data)
            else:
                logger.warning(f"Invalid repository specification: {repo_data}")
                return None
        except Exception as e:
            logger.error(f"Failed to parse repository: {e}")
            return None
    
    def _resolve_version_conflict(
        self, 
        repo_key: str,
        version1: str, 
        version2: str,
        source1: str,
        source2: str,
        conflict_resolution: Optional[ConflictResolution]
    ) -> Optional[str]:
        """Resolve version conflict between two sources."""
        if not conflict_resolution:
            # Default: prefer higher version or local source
            return self._choose_preferred_version(version1, version2, source1, source2)
        
        if conflict_resolution.strategy == "local" and source2 == "local":
            return version2
        elif conflict_resolution.strategy == "team" and source1 == "team":
            return version1
        elif conflict_resolution.strategy == "merge":
            # Intelligent merge: prefer higher version unless downgrades allowed
            return self._choose_preferred_version(
                version1, version2, source1, source2,
                allow_downgrades=conflict_resolution.allow_version_downgrades
            )
        elif conflict_resolution.strategy == "prompt":
            # Mark for user interaction
            conflict_resolution.conflict_plugins.append(
                f"{repo_key}: {source1}@{version1} vs {source2}@{version2}"
            )
            return version1  # Temporary choice
        
        return version1
    
    def _choose_preferred_version(
        self, 
        version1: str, 
        version2: str, 
        source1: str, 
        source2: str,
        allow_downgrades: bool = False
    ) -> str:
        """Choose preferred version using heuristics."""
        # Prefer local configurations
        if source2 == "local":
            return version2
        if source1 == "local":
            return version1
        
        # Prefer specific versions over dynamic ones
        dynamic_refs = ['latest', 'main', 'master', 'develop']
        v1_is_dynamic = version1 in dynamic_refs
        v2_is_dynamic = version2 in dynamic_refs
        
        if v1_is_dynamic and not v2_is_dynamic:
            return version2
        if v2_is_dynamic and not v1_is_dynamic:
            return version1
        
        # Try semantic version comparison
        try:
            if self._compare_semantic_versions(version1, version2) > 0:
                return version1
            else:
                return version2
        except:
            # Fallback: prefer second version (more recent source)
            return version2
    
    def _compare_semantic_versions(self, v1: str, v2: str) -> int:
        """Compare semantic versions. Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
        def parse_version(v):
            # Remove 'v' prefix if present
            v = v.lstrip('v')
            # Split by dots and convert to integers
            parts = []
            for part in v.split('.'):
                try:
                    parts.append(int(part.split('-')[0]))  # Handle pre-release versions
                except ValueError:
                    parts.append(0)
            return parts
        
        parts1 = parse_version(v1)
        parts2 = parse_version(v2)
        
        # Pad with zeros to same length
        max_len = max(len(parts1), len(parts2))
        parts1.extend([0] * (max_len - len(parts1)))
        parts2.extend([0] * (max_len - len(parts2)))
        
        for p1, p2 in zip(parts1, parts2):
            if p1 > p2:
                return 1
            elif p1 < p2:
                return -1
        
        return 0
    
    def _sync_with_merged_config(
        self, 
        project_dir: Path, 
        merged_config: Dict[str, Any], 
        environment: str, 
        dry_run: bool
    ) -> PluginSyncResult:
        """Perform sync using merged configuration."""
        result = PluginSyncResult(success=True)
        
        try:
            # Convert merged config to the format expected by sync_plugins
            repositories = merged_config.get('repositories', [])
            required_plugins = set(merged_config.get('required', []))
            optional_plugins = set(merged_config.get('optional', []))
            
            # Get plugin manager for operations
            plugin_manager = self._get_plugin_manager()
            
            # Get currently installed plugins
            installed_plugins = self._get_installed_plugins(plugin_manager)
            
            # Process each repository
            for repo_spec in repositories:
                try:
                    sync_result = self._sync_repository(
                        repo_spec, required_plugins, optional_plugins, 
                        installed_plugins, plugin_manager, dry_run
                    )
                    
                    result.installed_count += sync_result.get('installed', 0)
                    result.updated_count += sync_result.get('updated', 0)
                    result.skipped_count += sync_result.get('skipped', 0)
                    
                    if sync_result.get('failed'):
                        result.failed_plugins.extend(sync_result['failed'])
                
                except Exception as e:
                    error_msg = f"Failed to sync repository {repo_spec.repository}: {e}"
                    result.failed_plugins.append(repo_spec.repository)
                    result.warnings.append(error_msg)
                    logger.error(error_msg)
            
            # Set final result status
            if result.failed_plugins:
                result.success = False
                result.error_message = f"Failed to sync {len(result.failed_plugins)} plugins"
            
            logger.info(
                f"Plugin sync completed: {result.installed_count} installed, "
                f"{result.updated_count} updated, {result.skipped_count} skipped, "
                f"{len(result.failed_plugins)} failed"
            )
            
        except Exception as e:
            result.success = False
            result.error_message = f"Merged config sync failed: {e}"
            logger.error(f"Sync error: {e}")
        
        return result


class ProjectConfigValidator:
    """Validates project configuration for dependencies and compatibility."""
    
    def __init__(self):
        self.schema = ProjectConfigSchema()
    
    def validate_dependencies(self, config: Dict[str, Any]) -> ConfigValidationResult:
        """Validate extension dependencies within project."""
        result = ConfigValidationResult(is_valid=True)
        
        # Build set of all extension names
        all_extensions = set()
        extensions = config.get('extensions', {})
        
        for ext_list in extensions.values():
            for ext in ext_list:
                all_extensions.add(ext.get('name', ''))
        
        # Check dependencies
        for ext_type, ext_list in extensions.items():
            for ext in ext_list:
                dependencies = ext.get('dependencies', [])
                for dep in dependencies:
                    if dep not in all_extensions:
                        result.add_error(
                            "MISSING_DEPENDENCY",
                            f"Extension '{ext.get('name', '')}' depends on '{dep}' which is not defined in project",
                            f"{ext_type}/{ext.get('name', '')}"
                        )
        
        return result
    
    def validate_compatibility(self, config: Dict[str, Any], current_pacc_version: str) -> ConfigValidationResult:
        """Validate version compatibility."""
        result = ConfigValidationResult(is_valid=True)
        
        extensions = config.get('extensions', {})
        
        for ext_type, ext_list in extensions.items():
            for ext in ext_list:
                min_version = ext.get('min_pacc_version')
                if min_version and self._compare_versions(current_pacc_version, min_version) < 0:
                    result.add_error(
                        "VERSION_INCOMPATIBLE",
                        f"Extension '{ext.get('name', '')}' requires PACC version {min_version}, current: {current_pacc_version}",
                        f"{ext_type}/{ext.get('name', '')}"
                    )
        
        return result
    
    def validate_duplicates(self, config: Dict[str, Any]) -> ConfigValidationResult:
        """Validate for duplicate extension names."""
        result = ConfigValidationResult(is_valid=True)
        
        all_names = {}  # name -> (type, count)
        extensions = config.get('extensions', {})
        
        for ext_type, ext_list in extensions.items():
            for ext in ext_list:
                name = ext.get('name', '')
                if name in all_names:
                    all_names[name][1] += 1
                else:
                    all_names[name] = [ext_type, 1]
        
        # Report duplicates
        for name, (ext_type, count) in all_names.items():
            if count > 1:
                result.add_error(
                    "DUPLICATE_EXTENSION",
                    f"Extension name '{name}' is used {count} times in project configuration",
                    ext_type
                )
        
        return result
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """Compare two semantic versions. Returns -1, 0, or 1."""
        def parse_version(v):
            parts = v.split('-')[0].split('.')
            return [int(x) for x in parts]
        
        v1_parts = parse_version(version1)
        v2_parts = parse_version(version2)
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1_part = v1_parts[i] if i < len(v1_parts) else 0
            v2_part = v2_parts[i] if i < len(v2_parts) else 0
            
            if v1_part < v2_part:
                return -1
            elif v1_part > v2_part:
                return 1
        
        return 0


def get_extension_installer():
    """Get extension installer instance."""
    # This would normally return the actual installer
    # For now, return a mock that always succeeds
    class MockInstaller:
        def install_extension(self, ext_spec: ExtensionSpec, ext_type: str, project_dir: Path) -> bool:
            return True
    
    return MockInstaller()


# Exception classes
class ProjectConfigError(PACCError):
    """Base exception for project configuration errors."""
    pass