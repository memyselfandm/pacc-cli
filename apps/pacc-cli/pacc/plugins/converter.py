"""Extension to Plugin Converter for PACC.

This module provides functionality to convert loose Claude Code extensions 
(hooks, agents, commands, MCP) found in .claude directories into structured
plugin format that can be managed by the plugin system.
"""

import json
import logging
import shutil
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set, Union

from ..core.file_utils import FilePathValidator, PathNormalizer
from ..validators.hooks import HooksValidator
from ..validators.agents import AgentsValidator
from ..validators.commands import CommandsValidator
from ..validators.mcp import MCPValidator
from ..errors.exceptions import PACCError, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class ExtensionInfo:
    """Information about a discovered extension."""
    
    path: Path
    extension_type: str
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = True


@dataclass
class ConversionResult:
    """Result of a plugin conversion operation."""
    
    success: bool
    plugin_path: Optional[Path] = None
    plugin_name: Optional[str] = None
    converted_extensions: List[ExtensionInfo] = field(default_factory=list)
    skipped_extensions: List[ExtensionInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def total_extensions(self) -> int:
        """Total number of extensions processed."""
        return len(self.converted_extensions) + len(self.skipped_extensions)
    
    @property
    def conversion_rate(self) -> float:
        """Percentage of extensions successfully converted."""
        if self.total_extensions == 0:
            return 0.0
        return (len(self.converted_extensions) / self.total_extensions) * 100
    
    @property
    def error_message(self) -> str:
        """Get a formatted error message from the errors list."""
        if not self.errors:
            return ""
        return "; ".join(self.errors)
    
    @property
    def components(self) -> List[str]:
        """Get list of component types from converted extensions."""
        component_types = set()
        for ext in self.converted_extensions:
            component_types.add(ext.extension_type)
        return sorted(list(component_types))


class PluginConverter:
    """Converts Claude Code extensions to plugin format.
    
    This class handles the conversion of loose extensions found in .claude
    directories into structured plugins that can be managed by the plugin system.
    """
    
    def __init__(self):
        """Initialize the plugin converter."""
        self.path_validator = FilePathValidator()
        self.hooks_validator = HooksValidator()
        self.agents_validator = AgentsValidator()
        self.commands_validator = CommandsValidator()
        self.mcp_validator = MCPValidator()
        
        self._reserved_names = {"claude", "system", "plugin", "pacc"}
    
    def scan_extensions(self, source_directory: Union[str, Path]) -> List[ExtensionInfo]:
        """Scan a directory for Claude Code extensions.
        
        Args:
            source_directory: Directory to scan for extensions
            
        Returns:
            List of discovered extensions
        """
        source_path = Path(source_directory)
        
        if not source_path.exists():
            logger.warning(f"Source directory does not exist: {source_path}")
            return []
        
        # Look for .claude directory
        claude_dir = source_path / ".claude"
        if not claude_dir.exists():
            logger.debug(f"No .claude directory found in {source_path}")
            return []
        
        extensions = []
        
        # Scan for different extension types
        extensions.extend(self._scan_hooks(claude_dir))
        extensions.extend(self._scan_agents(claude_dir))
        extensions.extend(self._scan_commands(claude_dir))
        extensions.extend(self._scan_mcp(claude_dir))
        
        logger.info(f"Found {len(extensions)} extensions in {source_path}")
        return extensions
    
    def convert_to_plugin(
        self,
        extensions: List[ExtensionInfo],
        plugin_name: str,
        destination: Union[str, Path],
        author_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> ConversionResult:
        """Convert extensions to a plugin.
        
        Args:
            extensions: List of extensions to convert
            plugin_name: Name for the plugin
            destination: Destination directory for the plugin
            author_name: Plugin author name
            description: Plugin description
            
        Returns:
            ConversionResult with conversion details
        """
        result = ConversionResult(success=False)
        
        # Validate plugin name
        if not self._validate_plugin_name(plugin_name):
            result.errors.append(f"Invalid plugin name: {plugin_name}")
            return result
        
        # Filter valid extensions
        valid_extensions = [ext for ext in extensions if ext.is_valid]
        if not valid_extensions:
            result.errors.append("No valid extensions provided for conversion")
            return result
        
        destination_path = Path(destination)
        plugin_path = destination_path / plugin_name
        
        try:
            # Create plugin directory structure
            if not self._create_plugin_structure(plugin_path, result):
                return result
            
            # Group extensions by type for conversion
            extensions_by_type = self._group_extensions_by_type(valid_extensions)
            
            # Convert each extension type
            total_converted = 0
            
            if "hooks" in extensions_by_type:
                total_converted += self._convert_hooks(
                    extensions_by_type["hooks"], plugin_path, result
                )
            
            if "agents" in extensions_by_type:
                total_converted += self._convert_agents(
                    extensions_by_type["agents"], plugin_path, result
                )
            
            if "commands" in extensions_by_type:
                total_converted += self._convert_commands(
                    extensions_by_type["commands"], plugin_path, result
                )
            
            if "mcp" in extensions_by_type:
                total_converted += self._convert_mcp(
                    extensions_by_type["mcp"], plugin_path, result
                )
            
            if total_converted == 0:
                result.errors.append("No extensions were successfully converted")
                return result
            
            # Generate plugin manifest
            manifest = self.generate_manifest(
                plugin_name=plugin_name,
                extensions_by_type=extensions_by_type,
                author_name=author_name,
                description=description
            )
            
            # Write manifest
            manifest_path = plugin_path / "plugin.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            
            result.success = True
            result.plugin_path = plugin_path
            result.plugin_name = plugin_name
            
            logger.info(f"Successfully converted {total_converted} extensions to plugin: {plugin_name}")
            return result
            
        except Exception as e:
            logger.error(f"Plugin conversion failed: {e}")
            result.errors.append(f"Conversion failed: {e}")
            return result
    
    def generate_manifest(
        self,
        plugin_name: str,
        extensions_by_type: Dict[str, List[ExtensionInfo]],
        author_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate plugin manifest from converted extensions.
        
        Args:
            plugin_name: Name of the plugin
            extensions_by_type: Extensions grouped by type
            author_name: Plugin author name
            description: Plugin description
            
        Returns:
            Plugin manifest dictionary
        """
        # Auto-generate description if not provided
        if not description:
            component_counts = []
            for ext_type, extensions in extensions_by_type.items():
                if extensions:
                    component_counts.append(f"{len(extensions)} {ext_type}")
            
            if component_counts:
                description = f"Converted from Claude Code extensions: {', '.join(component_counts)}"
            else:
                description = "Converted Claude Code plugin"
        
        # Count components
        components = {}
        total_converted = 0
        for ext_type, extensions in extensions_by_type.items():
            components[ext_type] = len(extensions)
            total_converted += len(extensions)
        
        manifest = {
            "name": plugin_name,
            "version": "1.0.0",
            "description": description,
            "author": {
                "name": author_name or "Unknown"
            },
            "components": components,
            "metadata": {
                "converted_from": "claude_extensions",
                "conversion_tool": "pacc",
                "total_extensions_converted": total_converted
            }
        }
        
        return manifest
    
    def _validate_plugin_name(self, name: str) -> bool:
        """Validate plugin name meets requirements."""
        if not name or not name.strip():
            return False
        
        name = name.strip()
        
        # Check length
        if len(name) > 100:
            return False
        
        # Check for reserved names
        if name.lower() in self._reserved_names:
            return False
        
        # Check for valid characters (alphanumeric, hyphens, underscores)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return False
        
        return True
    
    def _group_extensions_by_type(self, extensions: List[ExtensionInfo]) -> Dict[str, List[ExtensionInfo]]:
        """Group extensions by their type."""
        grouped = {}
        for ext in extensions:
            if ext.extension_type not in grouped:
                grouped[ext.extension_type] = []
            grouped[ext.extension_type].append(ext)
        return grouped
    
    def _create_plugin_structure(self, plugin_path: Path, result: ConversionResult) -> bool:
        """Create basic plugin directory structure."""
        try:
            plugin_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            result.errors.append(f"Failed to create plugin directory: {e}")
            return False
    
    def _scan_hooks(self, claude_dir: Path) -> List[ExtensionInfo]:
        """Scan for hook extensions."""
        hooks_dir = claude_dir / "hooks"
        if not hooks_dir.exists():
            return []
        
        extensions = []
        for hook_file in hooks_dir.glob("*.json"):
            try:
                validation_result = self.hooks_validator.validate_single(hook_file)
                
                ext_info = ExtensionInfo(
                    path=hook_file,
                    extension_type="hooks",
                    name=hook_file.stem,
                    metadata=validation_result.metadata,
                    validation_errors=validation_result.errors,
                    is_valid=validation_result.is_valid
                )
                extensions.append(ext_info)
                
            except Exception as e:
                logger.warning(f"Failed to validate hook {hook_file}: {e}")
        
        return extensions
    
    def _scan_agents(self, claude_dir: Path) -> List[ExtensionInfo]:
        """Scan for agent extensions."""
        agents_dir = claude_dir / "agents"
        if not agents_dir.exists():
            return []
        
        extensions = []
        for agent_file in agents_dir.rglob("*.md"):
            try:
                validation_result = self.agents_validator.validate_single(agent_file)
                
                ext_info = ExtensionInfo(
                    path=agent_file,
                    extension_type="agents",
                    name=agent_file.stem,
                    metadata=validation_result.metadata,
                    validation_errors=validation_result.errors,
                    is_valid=validation_result.is_valid
                )
                extensions.append(ext_info)
                
            except Exception as e:
                logger.warning(f"Failed to validate agent {agent_file}: {e}")
        
        return extensions
    
    def _scan_commands(self, claude_dir: Path) -> List[ExtensionInfo]:
        """Scan for command extensions."""
        commands_dir = claude_dir / "commands"
        if not commands_dir.exists():
            return []
        
        extensions = []
        for cmd_file in commands_dir.rglob("*.md"):
            try:
                validation_result = self.commands_validator.validate_single(cmd_file)
                
                ext_info = ExtensionInfo(
                    path=cmd_file,
                    extension_type="commands",
                    name=cmd_file.stem,
                    metadata=validation_result.metadata,
                    validation_errors=validation_result.errors,
                    is_valid=validation_result.is_valid
                )
                extensions.append(ext_info)
                
            except Exception as e:
                logger.warning(f"Failed to validate command {cmd_file}: {e}")
        
        return extensions
    
    def _scan_mcp(self, claude_dir: Path) -> List[ExtensionInfo]:
        """Scan for MCP extensions."""
        mcp_dir = claude_dir / "mcp"
        if not mcp_dir.exists():
            return []
        
        extensions = []
        for mcp_file in mcp_dir.glob("*.json"):
            try:
                validation_result = self.mcp_validator.validate_single(mcp_file)
                
                ext_info = ExtensionInfo(
                    path=mcp_file,
                    extension_type="mcp",
                    name=mcp_file.stem,
                    metadata=validation_result.metadata,
                    validation_errors=validation_result.errors,
                    is_valid=validation_result.is_valid
                )
                extensions.append(ext_info)
                
            except Exception as e:
                logger.warning(f"Failed to validate MCP {mcp_file}: {e}")
        
        return extensions
    
    def _convert_hooks(self, extensions: List[ExtensionInfo], plugin_path: Path, result: ConversionResult) -> int:
        """Convert hook extensions to plugin format."""
        hooks_dir = plugin_path / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        
        merged_hooks = {"hooks": []}
        converted_count = 0
        
        for ext in extensions:
            if not ext.is_valid:
                result.skipped_extensions.append(ext)
                result.warnings.append(f"Skipped invalid hook: {ext.name}")
                continue
            
            try:
                with open(ext.path, 'r', encoding='utf-8') as f:
                    hook_data = json.load(f)
                
                # Handle both single hook and hooks array formats
                if "hooks" in hook_data:
                    merged_hooks["hooks"].extend(hook_data["hooks"])
                else:
                    # Single hook format
                    merged_hooks["hooks"].append(hook_data)
                
                result.converted_extensions.append(ext)
                converted_count += 1
                
            except Exception as e:
                result.errors.append(f"Failed to convert hook {ext.name}: {e}")
                result.skipped_extensions.append(ext)
        
        # Write merged hooks file
        if merged_hooks["hooks"]:
            hooks_file = hooks_dir / "hooks.json"
            with open(hooks_file, 'w', encoding='utf-8') as f:
                json.dump(merged_hooks, f, indent=2, ensure_ascii=False)
        
        return converted_count
    
    def _convert_agents(self, extensions: List[ExtensionInfo], plugin_path: Path, result: ConversionResult) -> int:
        """Convert agent extensions to plugin format."""
        agents_dir = plugin_path / "agents"
        agents_dir.mkdir(exist_ok=True)
        
        converted_count = 0
        
        for ext in extensions:
            if not ext.is_valid:
                result.skipped_extensions.append(ext)
                result.warnings.append(f"Skipped invalid agent: {ext.name}")
                continue
            
            try:
                # Determine target filename and handle conflicts
                target_name = f"{ext.name}.md"
                target_path = agents_dir / target_name
                
                # Handle naming conflicts
                counter = 1
                while target_path.exists():
                    target_name = f"{ext.name}_{counter}.md"
                    target_path = agents_dir / target_name
                    counter += 1
                
                # Copy agent file with path conversion
                content = ext.path.read_text(encoding='utf-8')
                converted_content = self._convert_paths_to_plugin_relative(content)
                target_path.write_text(converted_content, encoding='utf-8')
                
                result.converted_extensions.append(ext)
                converted_count += 1
                
            except Exception as e:
                result.errors.append(f"Failed to convert agent {ext.name}: {e}")
                result.skipped_extensions.append(ext)
        
        return converted_count
    
    def _convert_commands(self, extensions: List[ExtensionInfo], plugin_path: Path, result: ConversionResult) -> int:
        """Convert command extensions to plugin format."""
        commands_dir = plugin_path / "commands"
        commands_dir.mkdir(exist_ok=True)
        
        converted_count = 0
        
        for ext in extensions:
            if not ext.is_valid:
                result.skipped_extensions.append(ext)
                result.warnings.append(f"Skipped invalid command: {ext.name}")
                continue
            
            try:
                # Preserve directory structure relative to commands directory
                claude_commands_dir = ext.path.parent
                while claude_commands_dir.name != "commands" and claude_commands_dir.parent != claude_commands_dir:
                    claude_commands_dir = claude_commands_dir.parent
                
                if claude_commands_dir.name == "commands":
                    rel_path = ext.path.relative_to(claude_commands_dir)
                else:
                    rel_path = ext.path.name
                
                target_path = commands_dir / rel_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy command file with path conversion
                content = ext.path.read_text(encoding='utf-8')
                converted_content = self._convert_paths_to_plugin_relative(content)
                target_path.write_text(converted_content, encoding='utf-8')
                
                result.converted_extensions.append(ext)
                converted_count += 1
                
            except Exception as e:
                result.errors.append(f"Failed to convert command {ext.name}: {e}")
                result.skipped_extensions.append(ext)
        
        return converted_count
    
    def _convert_mcp(self, extensions: List[ExtensionInfo], plugin_path: Path, result: ConversionResult) -> int:
        """Convert MCP extensions to plugin format."""
        mcp_dir = plugin_path / "mcp"
        mcp_dir.mkdir(exist_ok=True)
        
        merged_config = {"mcpServers": {}}
        converted_count = 0
        
        for ext in extensions:
            if not ext.is_valid:
                result.skipped_extensions.append(ext)
                result.warnings.append(f"Skipped invalid MCP config: {ext.name}")
                continue
            
            try:
                with open(ext.path, 'r', encoding='utf-8') as f:
                    mcp_data = json.load(f)
                
                # Merge MCP server configurations
                if "mcpServers" in mcp_data:
                    merged_config["mcpServers"].update(mcp_data["mcpServers"])
                
                result.converted_extensions.append(ext)
                converted_count += 1
                
            except Exception as e:
                result.errors.append(f"Failed to convert MCP config {ext.name}: {e}")
                result.skipped_extensions.append(ext)
        
        # Write merged MCP config
        if merged_config["mcpServers"]:
            config_file = mcp_dir / "config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(merged_config, f, indent=2, ensure_ascii=False)
        
        return converted_count
    
    def _convert_paths_to_plugin_relative(self, content: str) -> str:
        """Convert absolute .claude paths to plugin-relative paths."""
        import re
        
        # Replace .claude directory references with plugin root variable
        claude_pattern = r'(["\']?)([^"\']*/)\.claude(/[^"\']*?)(["\']?)'
        replacement = r'\1${CLAUDE_PLUGIN_ROOT}\3\4'
        
        return re.sub(claude_pattern, replacement, content)


# Convenience function for backward compatibility and ease of use
def convert_extensions_to_plugin(
    source_directory: Union[str, Path],
    plugin_name: str,
    destination: Union[str, Path],
    author_name: Optional[str] = None,
    description: Optional[str] = None
) -> ConversionResult:
    """Convert Claude Code extensions to a plugin.
    
    This is a convenience function that handles the full conversion workflow:
    1. Scan source directory for extensions
    2. Convert them to plugin format
    3. Generate manifest and plugin structure
    
    Args:
        source_directory: Directory containing .claude extensions
        plugin_name: Name for the new plugin
        destination: Where to create the plugin
        author_name: Plugin author name
        description: Plugin description
        
    Returns:
        ConversionResult with conversion details
    """
    converter = PluginConverter()
    
    # Scan for extensions
    extensions = converter.scan_extensions(source_directory)
    
    if not extensions:
        result = ConversionResult(success=False)
        result.errors.append(f"No convertible extensions found in {source_directory}")
        return result
    
    # Convert to plugin
    return converter.convert_to_plugin(
        extensions=extensions,
        plugin_name=plugin_name,
        destination=destination,
        author_name=author_name,
        description=description
    )


# For CLI compatibility, create additional classes
@dataclass
class PluginMetadata:
    """Metadata for a converted plugin."""
    
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    components: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary for plugin.json."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "components": self.components
        }


class ExtensionToPluginConverter:
    """CLI-compatible converter interface."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize converter."""
        self.output_dir = output_dir or Path.cwd()
        self.converter = PluginConverter()
    
    def convert_extension(
        self,
        source_path: Path,
        plugin_name: Optional[str] = None,
        metadata: Optional[PluginMetadata] = None,
        overwrite: bool = False
    ) -> ConversionResult:
        """Convert single extension."""
        # Use the main converter
        extensions = self.converter.scan_extensions(source_path.parent)
        if not extensions:
            result = ConversionResult(success=False)
            result.errors.append("No extensions found")
            return result
        
        # Filter for this specific extension
        target_extensions = [ext for ext in extensions if ext.path == source_path]
        if not target_extensions:
            result = ConversionResult(success=False)
            result.errors.append("Specified extension not found")
            return result
        
        if not plugin_name:
            plugin_name = target_extensions[0].name
        
        return self.converter.convert_to_plugin(
            extensions=target_extensions,
            plugin_name=plugin_name,
            destination=self.output_dir,
            author_name=metadata.author if metadata else None,
            description=metadata.description if metadata else None
        )
    
    def convert_directory(
        self,
        source_dir: Path,
        metadata_defaults: Optional[Dict[str, str]] = None,
        overwrite: bool = False
    ) -> List[ConversionResult]:
        """Convert all extensions in directory."""
        extensions = self.converter.scan_extensions(source_dir)
        results = []
        
        # Group by extension type and convert each as separate plugin
        by_type = self.converter._group_extensions_by_type(extensions)
        
        for ext_type, type_extensions in by_type.items():
            plugin_name = f"{source_dir.name}-{ext_type}"
            
            result = self.converter.convert_to_plugin(
                extensions=type_extensions,
                plugin_name=plugin_name,
                destination=self.output_dir,
                author_name=metadata_defaults.get("author") if metadata_defaults else None
            )
            results.append(result)
        
        return results


class PluginPusher:
    """Handles pushing plugins to Git repositories."""
    
    def push_plugin(
        self,
        plugin_path: Path,
        repo_url: str,
        private: bool = False,
        auth_method: str = "https"
    ) -> bool:
        """Push plugin to Git repository."""
        try:
            import subprocess
            import tempfile
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_repo = Path(temp_dir) / "plugin_repo"
                
                # Initialize Git repository
                subprocess.run(["git", "init"], cwd=temp_repo, check=True)
                
                # Copy plugin files
                shutil.copytree(plugin_path, temp_repo / plugin_path.name)
                
                # Add and commit
                subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
                subprocess.run([
                    "git", "commit", "-m", f"Initial commit: {plugin_path.name}"
                ], cwd=temp_repo, check=True)
                
                # Push to remote
                subprocess.run([
                    "git", "remote", "add", "origin", repo_url
                ], cwd=temp_repo, check=True)
                
                subprocess.run([
                    "git", "push", "-u", "origin", "main"
                ], cwd=temp_repo, check=True)
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to push plugin: {e}")
            return False