"""Plugin discovery and metadata extraction for Claude Code repositories."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Union

# Optional YAML support
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None

from ..errors.exceptions import PACCError, ValidationError
from ..validators import ValidatorFactory


logger = logging.getLogger(__name__)


@dataclass
class PluginInfo:
    """Information about a discovered plugin."""
    
    name: str
    type: str  # "hooks", "agents", "mcps", "commands"
    file_path: Path
    description: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """Return string representation."""
        desc = self.description or "No description"
        return f"{self.name} ({self.type}) - {desc}"


@dataclass 
class RepositoryPlugins:
    """Collection of plugins found in a repository."""
    
    repository: str
    plugins: List[PluginInfo] = field(default_factory=list)
    manifest: Optional[Dict[str, Any]] = None
    readme_content: Optional[str] = None
    
    def get_plugins_by_type(self, plugin_type: str) -> List[PluginInfo]:
        """Get plugins of specific type.
        
        Args:
            plugin_type: Type of plugins to get
            
        Returns:
            List of plugins of specified type
        """
        return [p for p in self.plugins if p.type == plugin_type]
    
    def get_plugin_by_name(self, name: str) -> Optional[PluginInfo]:
        """Get plugin by name.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin info or None if not found
        """
        for plugin in self.plugins:
            if plugin.name == name:
                return plugin
        return None


class PluginDiscovery:
    """Discovers and extracts metadata from Claude Code plugins in repositories."""
    
    # Standard plugin directory names
    PLUGIN_DIRS = {
        "hooks": ["hooks", "hook"],
        "agents": ["agents", "agent"], 
        "mcps": ["mcps", "mcp", "servers"],
        "commands": ["commands", "command", "slash-commands"]
    }
    
    # Plugin file extensions by type
    PLUGIN_EXTENSIONS = {
        "hooks": [".json"],
        "agents": [".md", ".yaml", ".yml"],
        "mcps": [".py", ".js", ".json", ".yaml", ".yml"],
        "commands": [".md"]
    }
    
    def __init__(self):
        """Initialize plugin discovery."""
        self.validator_factory = ValidatorFactory()
    
    def discover_plugins(self, repo_path: Path) -> RepositoryPlugins:
        """Discover all plugins in a repository.
        
        Args:
            repo_path: Path to repository root
            
        Returns:
            RepositoryPlugins with discovered plugins
        """
        if not repo_path.exists() or not repo_path.is_dir():
            raise PACCError(f"Repository path does not exist: {repo_path}")
        
        repo_name = f"{repo_path.parent.name}/{repo_path.name}" if repo_path.parent.name != "repos" else repo_path.name
        result = RepositoryPlugins(repository=repo_name)
        
        # Load repository manifest if present
        result.manifest = self._load_manifest(repo_path)
        
        # Load README content
        result.readme_content = self._load_readme(repo_path)
        
        # Discover plugins by scanning directories
        discovered_plugins = []
        
        # Check for explicit plugin directories
        for plugin_type, dir_names in self.PLUGIN_DIRS.items():
            for dir_name in dir_names:
                plugin_dir = repo_path / dir_name
                if plugin_dir.exists() and plugin_dir.is_dir():
                    plugins = self._discover_plugins_in_directory(plugin_dir, plugin_type)
                    discovered_plugins.extend(plugins)
        
        # Check root directory for loose plugin files
        root_plugins = self._discover_plugins_in_directory(repo_path, None, max_depth=1)
        discovered_plugins.extend(root_plugins)
        
        # If manifest specifies plugins, use that as authoritative source
        if result.manifest and "plugins" in result.manifest:
            manifest_plugins = self._load_plugins_from_manifest(repo_path, result.manifest)
            discovered_plugins.extend(manifest_plugins)
        
        # Remove duplicates and validate
        result.plugins = self._deduplicate_and_validate(discovered_plugins)
        
        logger.info(f"Discovered {len(result.plugins)} plugins in {repo_name}")
        return result
    
    def _discover_plugins_in_directory(
        self, 
        directory: Path, 
        expected_type: Optional[str] = None,
        max_depth: int = 3
    ) -> List[PluginInfo]:
        """Discover plugins in a specific directory.
        
        Args:
            directory: Directory to scan
            expected_type: Expected plugin type (None to auto-detect)
            max_depth: Maximum recursion depth
            
        Returns:
            List of discovered plugins
        """
        plugins = []
        
        if max_depth <= 0:
            return plugins
        
        try:
            for item in directory.iterdir():
                if item.is_file():
                    plugin = self._analyze_file_for_plugin(item, expected_type)
                    if plugin:
                        plugins.append(plugin)
                elif item.is_dir() and not item.name.startswith('.'):
                    # Recursively scan subdirectories
                    sub_plugins = self._discover_plugins_in_directory(
                        item, expected_type, max_depth - 1
                    )
                    plugins.extend(sub_plugins)
        
        except PermissionError:
            logger.warning(f"Permission denied accessing {directory}")
        except Exception as e:
            logger.warning(f"Error scanning directory {directory}: {e}")
        
        return plugins
    
    def _analyze_file_for_plugin(self, file_path: Path, expected_type: Optional[str] = None) -> Optional[PluginInfo]:
        """Analyze a file to determine if it's a plugin.
        
        Args:
            file_path: Path to file to analyze
            expected_type: Expected plugin type
            
        Returns:
            PluginInfo if file is a plugin, None otherwise
        """
        try:
            # Skip common non-plugin files
            if file_path.name.lower() in {'readme.md', 'license', 'changelog.md', '.gitignore'}:
                return None
            
            # Determine plugin type
            plugin_type = expected_type
            if not plugin_type:
                plugin_type = self._detect_plugin_type(file_path)
            
            if not plugin_type:
                return None
            
            # Validate using appropriate validator
            try:
                validator = self.validator_factory.create_validator(plugin_type)
                result = validator.validate_file(file_path)
                
                if not result.is_valid:
                    logger.debug(f"File {file_path} failed validation as {plugin_type}")
                    return None
                
                # Extract plugin metadata
                plugin_info = PluginInfo(
                    name=result.metadata.get("name", file_path.stem),
                    type=plugin_type,
                    file_path=file_path,
                    description=result.metadata.get("description"),
                    version=result.metadata.get("version"),
                    author=result.metadata.get("author"),
                    dependencies=result.metadata.get("dependencies", []),
                    metadata=result.metadata
                )
                
                return plugin_info
                
            except Exception as e:
                logger.debug(f"Validation failed for {file_path}: {e}")
                return None
                
        except Exception as e:
            logger.debug(f"Error analyzing file {file_path}: {e}")
            return None
    
    def _detect_plugin_type(self, file_path: Path) -> Optional[str]:
        """Detect plugin type from file path and extension.
        
        Args:
            file_path: Path to file
            
        Returns:
            Plugin type or None if not detected
        """
        file_ext = file_path.suffix.lower()
        
        # Check parent directory for type hints
        parent_name = file_path.parent.name.lower()
        for plugin_type, dir_names in self.PLUGIN_DIRS.items():
            if parent_name in dir_names:
                if file_ext in self.PLUGIN_EXTENSIONS.get(plugin_type, []):
                    return plugin_type
        
        # Check file extension patterns
        if file_ext == ".json":
            # Could be hook or MCP
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                
                # Check for hook patterns
                if any(key in content for key in ["events", "handlers", "matchers"]):
                    return "hooks"
                
                # Check for MCP patterns  
                if any(key in content for key in ["command", "args", "server"]):
                    return "mcps"
                    
            except Exception:
                pass
        
        elif file_ext in [".md"]:
            # Could be agent or command
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for agent frontmatter
                if content.startswith('---') and '---' in content[3:]:
                    return "agents"
                
                # Check for command patterns
                if any(pattern in content.lower() for pattern in ["slash command", "claude command", "/command"]):
                    return "commands"
                    
            except Exception:
                pass
        
        elif file_ext in [".py", ".js"]:
            # Likely MCP server
            return "mcps"
        
        elif file_ext in [".yaml", ".yml"] and HAS_YAML:
            # Could be agent or MCP
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = yaml.safe_load(f)
                
                if isinstance(content, dict):
                    # Check for agent patterns
                    if any(key in content for key in ["model", "system_prompt", "tools"]):
                        return "agents"
                    
                    # Check for MCP patterns
                    if any(key in content for key in ["command", "args", "server"]):
                        return "mcps"
                        
            except Exception:
                pass
        
        return None
    
    def _load_manifest(self, repo_path: Path) -> Optional[Dict[str, Any]]:
        """Load repository manifest file.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Manifest data or None if not found
        """
        # Try common manifest filenames
        manifest_files = [
            "claude-plugins.json",
            "plugins.json", 
            "manifest.json",
        ]
        
        if HAS_YAML:
            manifest_files.extend([
                "claude-plugins.yaml",
                "plugins.yaml",
                "manifest.yaml"
            ])
        
        for filename in manifest_files:
            manifest_path = repo_path / filename
            if manifest_path.exists():
                try:
                    if filename.endswith('.json'):
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    elif HAS_YAML and filename.endswith(('.yaml', '.yml')):
                        with open(manifest_path, 'r', encoding='utf-8') as f:
                            return yaml.safe_load(f)
                except Exception as e:
                    logger.warning(f"Failed to load manifest {manifest_path}: {e}")
        
        return None
    
    def _load_readme(self, repo_path: Path) -> Optional[str]:
        """Load README content from repository.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            README content or None if not found
        """
        readme_files = ["README.md", "readme.md", "README.txt", "readme.txt"]
        
        for filename in readme_files:
            readme_path = repo_path / filename
            if readme_path.exists():
                try:
                    with open(readme_path, 'r', encoding='utf-8') as f:
                        return f.read()
                except Exception as e:
                    logger.warning(f"Failed to load README {readme_path}: {e}")
        
        return None
    
    def _load_plugins_from_manifest(self, repo_path: Path, manifest: Dict[str, Any]) -> List[PluginInfo]:
        """Load plugins specified in manifest.
        
        Args:
            repo_path: Path to repository
            manifest: Manifest data
            
        Returns:
            List of plugins from manifest
        """
        plugins = []
        
        manifest_plugins = manifest.get("plugins", [])
        if isinstance(manifest_plugins, dict):
            # Handle dict format: {"type": ["plugin1", "plugin2"]}
            for plugin_type, plugin_list in manifest_plugins.items():
                if isinstance(plugin_list, list):
                    for plugin_name in plugin_list:
                        plugin_path = repo_path / plugin_name
                        if plugin_path.exists():
                            plugin = self._analyze_file_for_plugin(plugin_path, plugin_type)
                            if plugin:
                                plugins.append(plugin)
        
        elif isinstance(manifest_plugins, list):
            # Handle list format: [{"name": "plugin1", "type": "hooks", "path": "hooks/plugin1.json"}]
            for plugin_spec in manifest_plugins:
                if isinstance(plugin_spec, dict):
                    plugin_path = repo_path / plugin_spec.get("path", plugin_spec.get("name", ""))
                    if plugin_path.exists():
                        plugin = self._analyze_file_for_plugin(
                            plugin_path, 
                            plugin_spec.get("type")
                        )
                        if plugin:
                            # Override with manifest metadata
                            if "name" in plugin_spec:
                                plugin.name = plugin_spec["name"]
                            if "description" in plugin_spec:
                                plugin.description = plugin_spec["description"]
                            if "version" in plugin_spec:
                                plugin.version = plugin_spec["version"]
                            
                            plugins.append(plugin)
        
        return plugins
    
    def _deduplicate_and_validate(self, plugins: List[PluginInfo]) -> List[PluginInfo]:
        """Remove duplicates and validate plugins.
        
        Args:
            plugins: List of discovered plugins
            
        Returns:
            Deduplicated and validated plugin list
        """
        # Remove duplicates based on file path
        seen_paths: Set[Path] = set()
        unique_plugins = []
        
        for plugin in plugins:
            if plugin.file_path not in seen_paths:
                seen_paths.add(plugin.file_path)
                unique_plugins.append(plugin)
            else:
                logger.debug(f"Skipping duplicate plugin: {plugin.file_path}")
        
        # Additional validation
        valid_plugins = []
        for plugin in unique_plugins:
            try:
                # Ensure plugin file still exists
                if not plugin.file_path.exists():
                    logger.warning(f"Plugin file no longer exists: {plugin.file_path}")
                    continue
                
                # Validate plugin name
                if not plugin.name or not plugin.name.strip():
                    plugin.name = plugin.file_path.stem
                
                valid_plugins.append(plugin)
                
            except Exception as e:
                logger.warning(f"Plugin validation failed: {plugin.file_path} - {e}")
        
        return valid_plugins


class PluginSelector:
    """Handles interactive plugin selection from discovered plugins."""
    
    def __init__(self):
        """Initialize plugin selector."""
        pass
    
    def select_plugins_interactive(self, repo_plugins: RepositoryPlugins) -> List[PluginInfo]:
        """Interactively select plugins to install.
        
        Args:
            repo_plugins: Repository plugins to choose from
            
        Returns:
            List of selected plugins
        """
        if not repo_plugins.plugins:
            print("No plugins found in repository.")
            return []
        
        print(f"\nFound {len(repo_plugins.plugins)} plugin(s) in {repo_plugins.repository}:")
        
        # Group plugins by type
        by_type: Dict[str, List[PluginInfo]] = {}
        for plugin in repo_plugins.plugins:
            if plugin.type not in by_type:
                by_type[plugin.type] = []
            by_type[plugin.type].append(plugin)
        
        # Display plugins grouped by type
        plugin_index = 0
        index_to_plugin = {}
        
        for plugin_type, plugins in by_type.items():
            print(f"\n{plugin_type.upper()}:")
            for plugin in plugins:
                plugin_index += 1
                index_to_plugin[plugin_index] = plugin
                desc = plugin.description or "No description"
                print(f"  {plugin_index}. {plugin.name} - {desc}")
        
        # Get user selection
        print(f"\nSelect plugins to install:")
        print("  - Enter numbers separated by commas (e.g., 1,3,5)")
        print("  - Enter 'all' to install all plugins")
        print("  - Enter 'none' or press Enter to skip")
        
        while True:
            try:
                choice = input("Selection: ").strip()
                
                if not choice or choice.lower() == 'none':
                    return []
                
                if choice.lower() == 'all':
                    return repo_plugins.plugins
                
                # Parse individual selections
                selected_indices = []
                for part in choice.split(','):
                    try:
                        index = int(part.strip())
                        if index in index_to_plugin:
                            selected_indices.append(index)
                        else:
                            print(f"Invalid selection: {index}")
                            raise ValueError()
                    except ValueError:
                        print(f"Invalid input: {part}")
                        raise
                
                selected_plugins = [index_to_plugin[i] for i in selected_indices]
                
                # Confirm selection
                if selected_plugins:
                    print(f"\nSelected {len(selected_plugins)} plugin(s):")
                    for plugin in selected_plugins:
                        print(f"  - {plugin.name} ({plugin.type})")
                    
                    confirm = input("Continue with installation? [Y/n]: ").strip().lower()
                    if confirm in ('', 'y', 'yes'):
                        return selected_plugins
                    else:
                        print("Selection cancelled.")
                        return []
                else:
                    return []
                
            except (ValueError, KeyboardInterrupt):
                print("Invalid selection. Please try again.")
                continue
    
    def select_all_plugins(self, repo_plugins: RepositoryPlugins) -> List[PluginInfo]:
        """Select all plugins from repository.
        
        Args:
            repo_plugins: Repository plugins
            
        Returns:
            All plugins from repository
        """
        return repo_plugins.plugins
    
    def select_plugins_by_type(self, repo_plugins: RepositoryPlugins, plugin_type: str) -> List[PluginInfo]:
        """Select plugins of specific type.
        
        Args:
            repo_plugins: Repository plugins
            plugin_type: Type of plugins to select
            
        Returns:
            Plugins of specified type
        """
        return repo_plugins.get_plugins_by_type(plugin_type)
    
    def select_plugins_by_names(self, repo_plugins: RepositoryPlugins, names: List[str]) -> List[PluginInfo]:
        """Select plugins by names.
        
        Args:
            repo_plugins: Repository plugins
            names: List of plugin names to select
            
        Returns:
            Matching plugins
        """
        selected = []
        for name in names:
            plugin = repo_plugins.get_plugin_by_name(name)
            if plugin:
                selected.append(plugin)
            else:
                logger.warning(f"Plugin not found: {name}")
        
        return selected