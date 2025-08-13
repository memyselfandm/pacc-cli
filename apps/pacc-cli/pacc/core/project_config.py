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