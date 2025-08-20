"""Plugin discovery engine for Claude Code plugins.

This module provides comprehensive plugin discovery functionality for multi-plugin
repositories following Claude Code plugin conventions.
"""

import json
import logging
import time
import yaml
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Union, Tuple
import re

from ..core.file_utils import FilePathValidator, PathNormalizer
from ..validation.base import ValidationResult, BaseValidator
from ..validation.formats import JSONValidator
from ..errors.exceptions import PACCError, ValidationError


logger = logging.getLogger(__name__)


@dataclass 
class PluginInfo:
    """Information about a discovered plugin."""
    
    name: str
    path: Path
    manifest: Dict[str, Any]
    components: Dict[str, List[Path]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    validation_result: Optional[ValidationResult] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        """Check if plugin is valid."""
        return len(self.errors) == 0 and (
            self.validation_result is None or self.validation_result.is_valid
        )
    
    @property
    def has_components(self) -> bool:
        """Check if plugin has any components."""
        return any(
            self.components.get(comp_type, []) 
            for comp_type in ['commands', 'agents', 'hooks']
        )
    
    def get_namespaced_components(self, plugin_root: Optional[Path] = None) -> Dict[str, List[str]]:
        """Get components with proper Claude Code namespacing.
        
        Returns namespaced component names following plugin:subdir:name convention.
        
        Args:
            plugin_root: Optional plugin root path for template resolution
            
        Returns:
            Dict mapping component types to namespaced names
        """
        namespaced = {}
        
        for comp_type, comp_paths in self.components.items():
            namespaced[comp_type] = []
            
            for comp_path in comp_paths:
                # Calculate relative path from plugin root
                try:
                    if comp_type == 'hooks':
                        # Hooks use the file name without extension 
                        namespaced_name = f"{self.name}:{comp_path.stem}"
                    else:
                        # Commands and agents use directory structure
                        rel_path = comp_path.relative_to(self.path / comp_type)
                        
                        # Build namespace: plugin:subdir:name
                        path_parts = list(rel_path.parts[:-1])  # Exclude filename
                        name_part = rel_path.stem  # Filename without extension
                        
                        if path_parts:
                            subdir = ':'.join(path_parts)
                            namespaced_name = f"{self.name}:{subdir}:{name_part}"
                        else:
                            namespaced_name = f"{self.name}:{name_part}"
                    
                    namespaced[comp_type].append(namespaced_name)
                
                except (ValueError, OSError) as e:
                    logger.warning(f"Failed to create namespace for {comp_path}: {e}")
                    # Fallback to simple name
                    namespaced_name = f"{self.name}:{comp_path.stem}"
                    namespaced[comp_type].append(namespaced_name)
        
        return namespaced


@dataclass
class RepositoryInfo:
    """Information about a plugin repository."""
    
    path: Path
    plugins: List[PluginInfo] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    scan_errors: List[str] = field(default_factory=list)
    
    @property
    def valid_plugins(self) -> List[PluginInfo]:
        """Get list of valid plugins in repository."""
        return [p for p in self.plugins if p.is_valid]
    
    @property
    def invalid_plugins(self) -> List[PluginInfo]:
        """Get list of invalid plugins in repository."""
        return [p for p in self.plugins if not p.is_valid]
    
    @property  
    def plugin_count(self) -> int:
        """Get total number of plugins."""
        return len(self.plugins)
    
    @property
    def has_plugins(self) -> bool:
        """Check if repository has any plugins."""
        return len(self.plugins) > 0


class PluginManifestParser:
    """Parser and validator for plugin.json manifest files."""
    
    def __init__(self):
        """Initialize manifest parser."""
        self.json_validator = JSONValidator()
        self._schema = self._get_manifest_schema()
    
    def parse_manifest(self, manifest_path: Path) -> Tuple[Dict[str, Any], ValidationResult]:
        """Parse and validate plugin manifest file.
        
        Args:
            manifest_path: Path to plugin.json file
            
        Returns:
            Tuple of (parsed_manifest, validation_result)
        """
        result = ValidationResult(
            is_valid=True,
            file_path=manifest_path,
            validator_name="PluginManifestParser"
        )
        
        try:
            # Read and parse JSON
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validate JSON syntax
            json_result = self.json_validator.validate_content(content, manifest_path)
            if not json_result.is_valid:
                result.is_valid = False
                result.issues.extend(json_result.issues)
                return {}, result
            
            manifest = json.loads(content)
            
            # Validate manifest schema
            schema_result = self._validate_schema(manifest, manifest_path)
            if not schema_result.is_valid:
                result.is_valid = False
                result.issues.extend(schema_result.issues)
                return manifest, result
            
            # Additional validation rules
            self._validate_manifest_rules(manifest, result)
            
            logger.debug(f"Successfully parsed manifest: {manifest_path}")
            return manifest, result
            
        except json.JSONDecodeError as e:
            result.is_valid = False
            result.add_error(
                f"Invalid JSON syntax: {e}",
                line_number=getattr(e, 'lineno', None),
                column_number=getattr(e, 'colno', None),
                rule_id="SYNTAX_ERROR"
            )
            return {}, result
            
        except OSError as e:
            result.is_valid = False
            result.add_error(f"Cannot read manifest file: {e}", rule_id="FILE_READ_ERROR")
            return {}, result
    
    def validate_manifest_content(self, content: str, file_path: Optional[Path] = None) -> ValidationResult:
        """Validate manifest content string.
        
        Args:
            content: Manifest content to validate
            file_path: Optional file path for context
            
        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(
            is_valid=True,
            file_path=file_path,
            validator_name="PluginManifestParser"
        )
        
        try:
            manifest = json.loads(content)
            schema_result = self._validate_schema(manifest, file_path)
            if not schema_result.is_valid:
                result.is_valid = False
                result.issues.extend(schema_result.issues)
            else:
                self._validate_manifest_rules(manifest, result)
                
        except json.JSONDecodeError as e:
            result.is_valid = False
            result.add_error(
                f"Invalid JSON syntax: {e}",
                line_number=getattr(e, 'lineno', None),
                column_number=getattr(e, 'colno', None),
                rule_id="SYNTAX_ERROR"
            )
        
        return result
    
    def _get_manifest_schema(self) -> Dict[str, Any]:
        """Get the plugin manifest JSON schema.
        
        Returns:
            JSON schema for plugin.json validation
        """
        return {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9_-]+$",
                    "minLength": 1,
                    "maxLength": 100
                },
                "version": {
                    "type": "string",
                    "pattern": r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$"
                },
                "description": {
                    "type": "string",
                    "maxLength": 500
                },
                "author": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string", "maxLength": 100},
                        "email": {"type": "string", "format": "email"},
                        "url": {"type": "string", "format": "uri"}
                    },
                    "additionalProperties": False
                }
            },
            "additionalProperties": True  # Allow extension fields
        }
    
    def _validate_schema(self, manifest: Dict[str, Any], file_path: Optional[Path]) -> ValidationResult:
        """Validate manifest against schema.
        
        Args:
            manifest: Parsed manifest data
            file_path: Optional file path for context
            
        Returns:
            ValidationResult with schema validation details
        """
        result = ValidationResult(
            is_valid=True,
            file_path=file_path,
            validator_name="PluginManifestParser"
        )
        
        # Required fields validation
        if "name" not in manifest:
            result.add_error("Missing required field: name", rule_id="MISSING_REQUIRED_FIELD")
        elif not isinstance(manifest["name"], str):
            result.add_error("Field 'name' must be a string", rule_id="INVALID_FIELD_TYPE")
        elif not manifest["name"].strip():
            result.add_error("Field 'name' cannot be empty", rule_id="EMPTY_REQUIRED_FIELD")
        elif not re.match(r"^[a-zA-Z0-9_-]+$", manifest["name"]):
            result.add_error(
                "Field 'name' can only contain letters, numbers, hyphens, and underscores",
                rule_id="INVALID_NAME_FORMAT"
            )
        
        # Version validation
        if "version" in manifest:
            if not isinstance(manifest["version"], str):
                result.add_error("Field 'version' must be a string", rule_id="INVALID_FIELD_TYPE")
            elif not re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$", manifest["version"]):
                result.add_error(
                    "Field 'version' must follow semantic versioning (e.g., '1.2.3')",
                    rule_id="INVALID_VERSION_FORMAT"
                )
        
        # Description validation
        if "description" in manifest:
            if not isinstance(manifest["description"], str):
                result.add_error("Field 'description' must be a string", rule_id="INVALID_FIELD_TYPE")
            elif len(manifest["description"]) > 500:
                result.add_error("Field 'description' cannot exceed 500 characters", rule_id="FIELD_TOO_LONG")
        
        # Author validation
        if "author" in manifest:
            if not isinstance(manifest["author"], dict):
                result.add_error("Field 'author' must be an object", rule_id="INVALID_FIELD_TYPE")
            else:
                author = manifest["author"]
                if "name" not in author:
                    result.add_error("Author object missing required field: name", rule_id="MISSING_REQUIRED_FIELD")
                elif not isinstance(author["name"], str):
                    result.add_error("Author 'name' must be a string", rule_id="INVALID_FIELD_TYPE")
                elif not author["name"].strip():
                    result.add_error("Author 'name' cannot be empty", rule_id="EMPTY_REQUIRED_FIELD")
                
                # Email validation (basic)
                if "email" in author:
                    if not isinstance(author["email"], str):
                        result.add_error("Author 'email' must be a string", rule_id="INVALID_FIELD_TYPE")
                    elif not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$", author["email"]) or ".." in author["email"]:
                        result.add_error("Author 'email' must be a valid email address", rule_id="INVALID_EMAIL_FORMAT")
                
                # URL validation (basic)
                if "url" in author:
                    if not isinstance(author["url"], str):
                        result.add_error("Author 'url' must be a string", rule_id="INVALID_FIELD_TYPE")
                    elif not re.match(r"^https?://", author["url"]):
                        result.add_error("Author 'url' must be a valid HTTP/HTTPS URL", rule_id="INVALID_URL_FORMAT")
        
        return result
    
    def _validate_manifest_rules(self, manifest: Dict[str, Any], result: ValidationResult) -> None:
        """Apply additional validation rules to manifest.
        
        Args:
            manifest: Parsed manifest data
            result: ValidationResult to update with issues
        """
        # Check for recommended fields
        if "description" not in manifest:
            result.add_warning("Missing recommended field: description", rule_id="MISSING_RECOMMENDED_FIELD")
        
        if "version" not in manifest:
            result.add_warning("Missing recommended field: version", rule_id="MISSING_RECOMMENDED_FIELD")
        
        if "author" not in manifest:
            result.add_warning("Missing recommended field: author", rule_id="MISSING_RECOMMENDED_FIELD")
        
        # Check for reasonable name length
        if len(manifest.get("name", "")) > 50:
            result.add_warning("Plugin name is quite long, consider shortening for better UX", rule_id="LONG_NAME")
        
        # Check for non-standard fields (info only)
        standard_fields = {"name", "version", "description", "author"}
        extra_fields = set(manifest.keys()) - standard_fields
        if extra_fields:
            result.add_info(f"Plugin includes non-standard fields: {', '.join(extra_fields)}", rule_id="EXTRA_FIELDS")


class PluginMetadataExtractor:
    """Extracts metadata from plugin components (commands, agents, hooks)."""
    
    def __init__(self):
        """Initialize metadata extractor."""
        self.yaml_parser = yaml.SafeLoader
        
    def extract_command_metadata(self, command_path: Path) -> Dict[str, Any]:
        """Extract metadata from a command markdown file.
        
        Args:
            command_path: Path to command .md file
            
        Returns:
            Dictionary with command metadata
        """
        metadata = {
            "type": "command",
            "name": command_path.stem,
            "path": command_path,
            "description": None,
            "allowed_tools": [],
            "argument_hint": None,
            "model": None,
            "body": "",
            "errors": []
        }
        
        try:
            with open(command_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse YAML frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1])
                        metadata.update({
                            "description": frontmatter.get("description"),
                            "allowed_tools": frontmatter.get("allowed-tools", []),
                            "argument_hint": frontmatter.get("argument-hint"),
                            "model": frontmatter.get("model")
                        })
                        metadata["body"] = parts[2].strip()
                    except yaml.YAMLError as e:
                        metadata["errors"].append(f"Invalid YAML frontmatter: {e}")
                        metadata["body"] = content
                else:
                    metadata["body"] = content
            else:
                metadata["body"] = content
            
            # Detect template variables
            template_vars = []
            if "$ARGUMENTS" in content:
                template_vars.append("$ARGUMENTS")
            if "${CLAUDE_PLUGIN_ROOT}" in content:
                template_vars.append("${CLAUDE_PLUGIN_ROOT}")
            metadata["template_variables"] = template_vars
            
        except OSError as e:
            metadata["errors"].append(f"Cannot read command file: {e}")
        
        return metadata
    
    def extract_agent_metadata(self, agent_path: Path) -> Dict[str, Any]:
        """Extract metadata from an agent markdown file.
        
        Args:
            agent_path: Path to agent .md file
            
        Returns:
            Dictionary with agent metadata
        """
        metadata = {
            "type": "agent",
            "name": agent_path.stem,
            "path": agent_path,
            "display_name": None,
            "description": None,
            "tools": [],
            "color": None,
            "model": None,
            "body": "",
            "errors": []
        }
        
        try:
            with open(agent_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse YAML frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    try:
                        frontmatter = yaml.safe_load(parts[1])
                        metadata.update({
                            "display_name": frontmatter.get("name"),
                            "description": frontmatter.get("description"),
                            "tools": frontmatter.get("tools", []),
                            "color": frontmatter.get("color"),
                            "model": frontmatter.get("model")
                        })
                        metadata["body"] = parts[2].strip()
                    except yaml.YAMLError as e:
                        metadata["errors"].append(f"Invalid YAML frontmatter: {e}")
                        metadata["body"] = content
                else:
                    metadata["body"] = content
            else:
                metadata["body"] = content
                
        except OSError as e:
            metadata["errors"].append(f"Cannot read agent file: {e}")
        
        return metadata
    
    def extract_hooks_metadata(self, hooks_path: Path) -> Dict[str, Any]:
        """Extract metadata from a hooks.json file.
        
        Args:
            hooks_path: Path to hooks.json file
            
        Returns:
            Dictionary with hooks metadata
        """
        metadata = {
            "type": "hooks",
            "name": hooks_path.stem,
            "path": hooks_path,
            "hooks": [],
            "errors": []
        }
        
        try:
            with open(hooks_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            hooks_data = json.loads(content)
            
            if "hooks" in hooks_data and isinstance(hooks_data["hooks"], list):
                for hook in hooks_data["hooks"]:
                    hook_info = {
                        "type": hook.get("type"),
                        "matcher": hook.get("matcher", {}),
                        "action": hook.get("action", {}),
                        "description": hook.get("description")
                    }
                    metadata["hooks"].append(hook_info)
            else:
                metadata["errors"].append("Invalid hooks.json structure: missing 'hooks' array")
                
        except json.JSONDecodeError as e:
            metadata["errors"].append(f"Invalid JSON in hooks file: {e}")
        except OSError as e:
            metadata["errors"].append(f"Cannot read hooks file: {e}")
        
        return metadata


class PluginScanner:
    """Scans directories to discover Claude Code plugins."""
    
    def __init__(self):
        """Initialize plugin scanner."""
        self.manifest_parser = PluginManifestParser()
        self.metadata_extractor = PluginMetadataExtractor()
        self.path_validator = FilePathValidator()
        self._scan_cache = {}  # Cache for repository scans
        self._cache_timestamp = {}  # Track cache freshness
        
    def scan_repository(self, repo_path: Path, use_cache: bool = True) -> RepositoryInfo:
        """Scan repository for plugins.
        
        Args:
            repo_path: Path to plugin repository
            use_cache: Whether to use cached results
            
        Returns:
            RepositoryInfo with discovered plugins
        """
        repo_key = str(repo_path.resolve())
        
        # Check cache first
        if use_cache and repo_key in self._scan_cache:
            try:
                # Check if repository has been modified since cache
                repo_mtime = repo_path.stat().st_mtime
                cache_time = self._cache_timestamp.get(repo_key, 0)
                
                if repo_mtime <= cache_time:
                    logger.debug(f"Using cached scan results for {repo_path}")
                    return self._scan_cache[repo_key]
            except OSError:
                # If we can't stat the repo, invalidate cache
                pass
        
        repo_info = RepositoryInfo(path=repo_path)
        
        try:
            if not repo_path.exists():
                repo_info.scan_errors.append(f"Repository path does not exist: {repo_path}")
                return repo_info
            
            if not repo_path.is_dir():
                repo_info.scan_errors.append(f"Repository path is not a directory: {repo_path}")
                return repo_info
            
            # Look for plugin directories (containing plugin.json)
            plugin_dirs = self._find_plugin_directories(repo_path)
            
            logger.debug(f"Found {len(plugin_dirs)} potential plugin directories in {repo_path}")
            
            for plugin_dir in plugin_dirs:
                try:
                    plugin_info = self._scan_plugin_directory(plugin_dir)
                    if plugin_info:
                        repo_info.plugins.append(plugin_info)
                        logger.debug(f"Successfully scanned plugin: {plugin_info.name}")
                except Exception as e:
                    error_msg = f"Failed to scan plugin directory {plugin_dir}: {e}. Check if the directory is accessible and contains valid plugin files."
                    repo_info.scan_errors.append(error_msg)
                    logger.error(error_msg)
            
            # Add repository metadata
            repo_info.metadata = {
                "scanned_at": str(Path.cwd()),
                "plugin_count": len(repo_info.plugins),
                "valid_plugins": len(repo_info.valid_plugins),
                "invalid_plugins": len(repo_info.invalid_plugins)
            }
            
        except Exception as e:
            error_msg = f"Failed to scan repository {repo_path}: {e}"
            repo_info.scan_errors.append(error_msg)
            logger.error(error_msg)
        
        # Cache the results if scan was successful
        if use_cache and not repo_info.scan_errors:
            self._scan_cache[repo_key] = repo_info
            self._cache_timestamp[repo_key] = time.time()
            logger.debug(f"Cached scan results for {repo_path}")
        
        return repo_info
    
    def _find_plugin_directories(self, repo_path: Path) -> List[Path]:
        """Find directories containing plugin.json files.
        
        Optimized to avoid deep recursion and use limited depth search.
        
        Args:
            repo_path: Repository root path
            
        Returns:
            List of plugin directory paths
        """
        plugin_dirs = []
        MAX_DEPTH = 3  # Limit search depth for performance
        
        # Search for plugin.json files with limited recursion
        try:
            # First check common plugin locations
            common_locations = [
                repo_path,  # Root level
                repo_path / "plugins",  # Common plugins dir
                repo_path / "src" / "plugins",  # Src structure
            ]
            
            for location in common_locations:
                if location.exists() and location.is_dir():
                    manifest_path = location / "plugin.json"
                    if manifest_path.exists():
                        if self.path_validator.is_valid_path(location):
                            plugin_dirs.append(location)
                            logger.debug(f"Found plugin manifest: {manifest_path}")
            
            # Then do limited recursive search if no plugins found in common locations
            if not plugin_dirs:
                def _search_with_depth(path: Path, current_depth: int = 0):
                    if current_depth >= MAX_DEPTH:
                        return
                    
                    try:
                        for item in path.iterdir():
                            if item.is_dir() and not item.name.startswith('.'):
                                manifest_path = item / "plugin.json"
                                if manifest_path.exists():
                                    if self.path_validator.is_valid_path(item):
                                        plugin_dirs.append(item)
                                        logger.debug(f"Found plugin manifest: {manifest_path}")
                                else:
                                    # Recurse into subdirectory
                                    _search_with_depth(item, current_depth + 1)
                    except (OSError, PermissionError):
                        # Skip directories we can't access
                        pass
                
                _search_with_depth(repo_path)
                
        except OSError as e:
            logger.error(f"Error searching for plugin directories in {repo_path}: {e}. Check repository permissions and disk space.")
        
        return plugin_dirs
    
    def _scan_plugin_directory(self, plugin_dir: Path) -> Optional[PluginInfo]:
        """Scan a single plugin directory.
        
        Args:
            plugin_dir: Path to plugin directory
            
        Returns:
            PluginInfo or None if not a valid plugin
        """
        manifest_path = plugin_dir / "plugin.json"
        
        if not manifest_path.exists():
            logger.warning(f"No plugin.json found in {plugin_dir}")
            return None
        
        # Parse manifest
        manifest, validation_result = self.manifest_parser.parse_manifest(manifest_path)
        
        if not validation_result.is_valid:
            logger.warning(f"Invalid plugin manifest in {plugin_dir}: {validation_result.error_count} errors")
        
        # Create plugin info
        plugin_info = PluginInfo(
            name=manifest.get("name", plugin_dir.name),
            path=plugin_dir,
            manifest=manifest,
            validation_result=validation_result
        )
        
        # Collect validation errors
        if validation_result.has_errors:
            plugin_info.errors.extend([
                f"{issue.message}" for issue in validation_result.issues 
                if issue.severity == 'error'
            ])
        
        if validation_result.has_warnings:
            plugin_info.warnings.extend([
                f"{issue.message}" for issue in validation_result.issues 
                if issue.severity == 'warning'
            ])
        
        # Discover components with metadata extraction
        self._discover_plugin_components(plugin_info, extract_metadata=True)
        
        return plugin_info
    
    def _discover_plugin_components(self, plugin_info: PluginInfo, extract_metadata: bool = False) -> None:
        """Discover plugin components (commands, agents, hooks).
        
        Optimized to only extract metadata when needed and batch file operations.
        
        Args:
            plugin_info: PluginInfo to update with component information
            extract_metadata: Whether to extract detailed metadata (slower)
        """
        plugin_path = plugin_info.path
        
        # Define component types and their extensions
        component_types = {
            "commands": ("commands", "*.md"),
            "agents": ("agents", "*.md"), 
            "hooks": ("hooks", "*.json"),
            "mcp": ("mcp", "*.json")
        }
        
        # Batch discover all components
        for comp_type, (dirname, pattern) in component_types.items():
            comp_dir = plugin_path / dirname
            if comp_dir.exists() and comp_dir.is_dir():
                try:
                    # Use glob instead of rglob for better performance (limit to immediate children)
                    component_files = []
                    
                    # Check immediate directory
                    direct_files = list(comp_dir.glob(pattern))
                    component_files.extend(direct_files)
                    
                    # Only check one level deep for performance
                    for subdir in comp_dir.iterdir():
                        if subdir.is_dir() and not subdir.name.startswith('.'):
                            try:
                                subdir_files = list(subdir.glob(pattern))
                                component_files.extend(subdir_files)
                            except (OSError, PermissionError):
                                # Skip inaccessible subdirectories
                                continue
                    
                    if component_files:
                        plugin_info.components[comp_type] = component_files
                        logger.debug(f"Found {len(component_files)} {comp_type} in {comp_dir}")
                        
                        # Only extract metadata if specifically requested
                        if extract_metadata:
                            self._extract_component_metadata(plugin_info, comp_type, component_files)
                
                except (OSError, PermissionError) as e:
                    error_msg = f"Error accessing {comp_type} directory {comp_dir}: {e}"
                    plugin_info.warnings.append(error_msg)
                    logger.warning(error_msg)
    
    def _extract_component_metadata(self, plugin_info: PluginInfo, comp_type: str, files: List[Path]) -> None:
        """Extract metadata for component files (called separately for performance).
        
        Args:
            plugin_info: Plugin info to update
            comp_type: Component type (commands, agents, etc.)
            files: List of component files
        """
        metadata_key = f"{comp_type}_metadata"
        if metadata_key not in plugin_info.metadata:
            plugin_info.metadata[metadata_key] = []
        
        for file_path in files:
            try:
                if comp_type == "commands":
                    metadata = self.metadata_extractor.extract_command_metadata(file_path)
                elif comp_type == "agents":
                    metadata = self.metadata_extractor.extract_agent_metadata(file_path)
                elif comp_type in ["hooks", "mcp"]:
                    metadata = self.metadata_extractor.extract_hooks_metadata(file_path)
                else:
                    continue
                
                if metadata.get("errors"):
                    plugin_info.errors.extend(metadata["errors"])
                
                plugin_info.metadata[metadata_key].append(metadata)
                
            except Exception as e:
                error_msg = f"Failed to extract {comp_type} metadata from {file_path}: {e}. Check if the file format is valid and readable."
                plugin_info.errors.append(error_msg)
                logger.error(error_msg)


# Template variable resolution functions
def resolve_template_variables(
    content: str, 
    plugin_root: Optional[Path] = None,
    arguments: Optional[str] = None
) -> str:
    """Resolve template variables in plugin content.
    
    Args:
        content: Content with template variables
        plugin_root: Plugin root directory path
        arguments: Arguments to substitute for $ARGUMENTS
        
    Returns:
        Content with template variables resolved
    """
    resolved = content
    
    # Resolve ${CLAUDE_PLUGIN_ROOT}
    if plugin_root and "${CLAUDE_PLUGIN_ROOT}" in resolved:
        resolved = resolved.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
    
    # Resolve $ARGUMENTS 
    if arguments and "$ARGUMENTS" in resolved:
        resolved = resolved.replace("$ARGUMENTS", arguments)
    
    return resolved


def extract_template_variables(content: str) -> List[str]:
    """Extract template variables from content.
    
    Args:
        content: Content to scan for template variables
        
    Returns:
        List of template variables found
    """
    variables = []
    
    # Find ${CLAUDE_PLUGIN_ROOT}
    if "${CLAUDE_PLUGIN_ROOT}" in content:
        variables.append("${CLAUDE_PLUGIN_ROOT}")
    
    # Find $ARGUMENTS
    if "$ARGUMENTS" in content:
        variables.append("$ARGUMENTS")
    
    return variables


# Main discovery functions
def discover_plugins(repo_path: Union[str, Path]) -> RepositoryInfo:
    """Discover all plugins in a repository.
    
    Args:
        repo_path: Path to plugin repository
        
    Returns:
        RepositoryInfo with discovered plugins
    """
    scanner = PluginScanner()
    return scanner.scan_repository(Path(repo_path))


def validate_plugin_manifest(manifest_path: Union[str, Path]) -> ValidationResult:
    """Validate a plugin.json manifest file.
    
    Args:
        manifest_path: Path to plugin.json file
        
    Returns:
        ValidationResult with validation details
    """
    parser = PluginManifestParser()
    _, result = parser.parse_manifest(Path(manifest_path))
    return result


def extract_plugin_metadata(plugin_path: Union[str, Path]) -> Optional[PluginInfo]:
    """Extract complete metadata for a plugin.
    
    Args:
        plugin_path: Path to plugin directory
        
    Returns:
        PluginInfo with complete metadata or None if invalid
    """
    scanner = PluginScanner()
    return scanner._scan_plugin_directory(Path(plugin_path))