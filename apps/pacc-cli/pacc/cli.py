#!/usr/bin/env python3
"""PACC CLI - Package manager for Claude Code."""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

from . import __version__
from .validators import (
    ValidatorFactory, 
    ValidationResultFormatter,
    ExtensionDetector,
    ValidationRunner,
    validate_extension_file,
    validate_extension_directory
)
from .ui import MultiSelectList
from .errors import PACCError, ValidationError, SourceError
from .core.config_manager import ClaudeConfigManager
from .core.project_config import ProjectConfigManager, ProjectSyncManager
from .plugins import (
    PluginConfigManager,
    PluginRepositoryManager,
    RepositoryManager,
    PluginDiscovery,
    PluginSelector,
    GitRepository,
    ExtensionToPluginConverter,
    PluginPusher,
    PluginMetadata,
    EnvironmentManager,
    get_environment_manager
)
from .plugins.search import PluginSearchEngine, SearchPluginType, search_plugins, get_plugin_recommendations

# URL downloader imports (conditional for optional dependency)
try:
    from .core.url_downloader import URLDownloader, ProgressDisplay
    HAS_URL_DOWNLOADER = True
except ImportError:
    HAS_URL_DOWNLOADER = False
    URLDownloader = None
    ProgressDisplay = None


@dataclass
class Extension:
    """Represents a detected extension."""
    name: str
    file_path: Path
    extension_type: str
    description: Optional[str] = None


@dataclass
class CommandResult:
    """Represents the result of a CLI command execution."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "message": self.message
        }
        
        if self.data is not None:
            result["data"] = self.data
        if self.errors:
            result["errors"] = self.errors
        if self.warnings:
            result["warnings"] = self.warnings
            
        return result


class PACCCli:
    """Main CLI class for PACC operations."""
    
    def __init__(self):
        self._messages = []  # Store messages for JSON output
        self._json_output = False
        
    def create_parser(self) -> argparse.ArgumentParser:
        """Create the main argument parser."""
        parser = argparse.ArgumentParser(
            prog="pacc",
            description="PACC - Package manager for Claude Code",
            epilog="For more help on a specific command, use: pacc <command> --help"
        )
        
        parser.add_argument(
            "--version", 
            action="version", 
            version=f"pacc {__version__}"
        )
        
        parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Enable verbose output"
        )
        
        parser.add_argument(
            "--no-color",
            action="store_true", 
            help="Disable colored output"
        )
        
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output in JSON format for programmatic consumption"
        )
        
        # Add subcommands
        subparsers = parser.add_subparsers(
            dest="command", 
            help="Available commands",
            metavar="<command>"
        )
        
        # Install command
        self._add_install_parser(subparsers)
        
        # List command
        self._add_list_parser(subparsers)
        
        # Remove command
        self._add_remove_parser(subparsers)
        
        # Info command
        self._add_info_parser(subparsers)
        
        # Validate command
        self._add_validate_parser(subparsers)
        
        # Init command
        self._add_init_parser(subparsers)
        
        # Sync command
        self._add_sync_parser(subparsers)
        
        # Plugin command
        self._add_plugin_parser(subparsers)
        
        return parser
    
    def _add_install_parser(self, subparsers) -> None:
        """Add the install command parser."""
        install_parser = subparsers.add_parser(
            "install",
            help="Install Claude Code extensions",
            description="Install hooks, MCP servers, agents, or commands from local sources or URLs"
        )
        
        install_parser.add_argument(
            "source",
            help="Path to extension file/directory or URL to install from"
        )
        
        install_parser.add_argument(
            "--type", "-t",
            choices=ValidatorFactory.get_supported_types(),
            help="Specify extension type (auto-detected if not provided)"
        )
        
        # Installation scope
        scope_group = install_parser.add_mutually_exclusive_group()
        scope_group.add_argument(
            "--user",
            action="store_true",
            help="Install to user directory (~/.claude/)"
        )
        scope_group.add_argument(
            "--project", 
            action="store_true",
            help="Install to project directory (./.claude/) [default]"
        )
        
        # Installation options
        install_parser.add_argument(
            "--force",
            action="store_true",
            help="Force installation, overwriting existing files"
        )
        
        install_parser.add_argument(
            "--dry-run", "-n",
            action="store_true",
            help="Show what would be installed without making changes"
        )
        
        install_parser.add_argument(
            "--interactive", "-i",
            action="store_true",
            help="Use interactive selection for multi-item sources"
        )
        
        install_parser.add_argument(
            "--all",
            action="store_true",
            help="Install all valid extensions found in source"
        )
        
        # URL-specific options
        install_parser.add_argument(
            "--no-extract",
            action="store_true",
            help="Don't extract archives when installing from URLs"
        )
        
        install_parser.add_argument(
            "--max-size",
            type=int,
            default=100,
            help="Maximum download size in MB (default: 100)"
        )
        
        install_parser.add_argument(
            "--timeout",
            type=int,
            default=300,
            help="Download timeout in seconds (default: 300)"
        )
        
        install_parser.add_argument(
            "--no-cache",
            action="store_true",
            help="Disable download caching"
        )
        
        install_parser.add_argument(
            "--json",
            action="store_true",
            help="Output installation results in JSON format"
        )
        
        install_parser.set_defaults(func=self.install_command)
    
    def _add_list_parser(self, subparsers) -> None:
        """Add the list command parser."""
        list_parser = subparsers.add_parser(
            "list",
            aliases=["ls"],
            help="List installed extensions",
            description="List installed Claude Code extensions"
        )
        
        list_parser.add_argument(
            "type",
            nargs="?",
            choices=ValidatorFactory.get_supported_types(),
            help="Extension type to list (lists all if not specified)"
        )
        
        list_parser.add_argument(
            "--user",
            action="store_true",
            help="List user-level extensions only"
        )
        
        list_parser.add_argument(
            "--project",
            action="store_true", 
            help="List project-level extensions only"
        )
        
        list_parser.add_argument(
            "--all", "-a",
            action="store_true",
            help="List both user and project extensions [default]"
        )
        
        list_parser.add_argument(
            "--format",
            choices=["table", "list", "json"],
            default="table",
            help="Output format"
        )
        
        # Add filtering and search options
        list_parser.add_argument(
            "--filter", "-f",
            help="Filter by name pattern (supports wildcards)"
        )
        
        list_parser.add_argument(
            "--search", "-s",
            help="Search in descriptions"
        )
        
        list_parser.add_argument(
            "--sort",
            choices=["name", "type", "date"],
            default="name",
            help="Sort order for results"
        )
        
        list_parser.add_argument(
            "--show-status",
            action="store_true",
            help="Show validation status (with --verbose)"
        )
        
        list_parser.set_defaults(func=self.list_command)
    
    def _add_remove_parser(self, subparsers) -> None:
        """Add the remove command parser."""
        remove_parser = subparsers.add_parser(
            "remove",
            aliases=["rm"],
            help="Remove installed extensions",
            description="Remove Claude Code extensions"
        )
        
        remove_parser.add_argument(
            "name",
            help="Name of extension to remove"
        )
        
        remove_parser.add_argument(
            "--type", "-t",
            choices=ValidatorFactory.get_supported_types(),
            help="Extension type (auto-detected if not provided)"
        )
        
        # Scope options
        scope_group = remove_parser.add_mutually_exclusive_group()
        scope_group.add_argument(
            "--user",
            action="store_true",
            help="Remove from user directory (~/.claude/)"
        )
        scope_group.add_argument(
            "--project",
            action="store_true",
            help="Remove from project directory (./.claude/) [default]"
        )
        
        # Removal options
        remove_parser.add_argument(
            "--confirm", "-y",
            action="store_true",
            help="Skip confirmation prompt"
        )
        
        remove_parser.add_argument(
            "--dry-run", "-n",
            action="store_true",
            help="Show what would be removed without making changes"
        )
        
        remove_parser.add_argument(
            "--force",
            action="store_true",
            help="Force removal even if dependencies exist"
        )
        
        remove_parser.add_argument(
            "--json",
            action="store_true",
            help="Output removal results in JSON format"
        )
        
        remove_parser.set_defaults(func=self.remove_command)
    
    def _add_info_parser(self, subparsers) -> None:
        """Add the info command parser."""
        info_parser = subparsers.add_parser(
            "info",
            help="Show extension information",
            description="Display detailed information about extensions"
        )
        
        info_parser.add_argument(
            "source",
            help="Path to extension or name of installed extension"
        )
        
        info_parser.add_argument(
            "--type", "-t",
            choices=ValidatorFactory.get_supported_types(),
            help="Extension type (auto-detected if not provided)"
        )
        
        info_parser.add_argument(
            "--json",
            action="store_true",
            help="Output information in JSON format"
        )
        
        info_parser.add_argument(
            "--show-related",
            action="store_true",
            help="Show related extensions and suggestions"
        )
        
        info_parser.add_argument(
            "--show-usage",
            action="store_true", 
            help="Show usage examples where available"
        )
        
        info_parser.add_argument(
            "--show-troubleshooting",
            action="store_true",
            help="Include troubleshooting information"
        )
        
        info_parser.add_argument(
            "--verbose", "-v",
            action="store_true",
            help="Show detailed information and metadata"
        )
        
        info_parser.set_defaults(func=self.info_command)
    
    def _add_validate_parser(self, subparsers) -> None:
        """Add the validate command parser."""
        validate_parser = subparsers.add_parser(
            "validate",
            help="Validate extensions without installing",
            description="Validate Claude Code extensions for correctness"
        )
        
        validate_parser.add_argument(
            "source",
            help="Path to extension file or directory to validate"
        )
        
        validate_parser.add_argument(
            "--type", "-t",
            choices=ValidatorFactory.get_supported_types(),
            help="Extension type (auto-detected if not provided)"
        )
        
        validate_parser.add_argument(
            "--strict",
            action="store_true",
            help="Use strict validation (treat warnings as errors)"
        )
        
        validate_parser.set_defaults(func=self.validate_command)
    
    def _add_init_parser(self, subparsers) -> None:
        """Add the init command parser."""
        init_parser = subparsers.add_parser(
            "init",
            help="Initialize PACC configuration",
            description="Initialize project or user-level PACC configuration"
        )
        
        # Scope options
        scope_group = init_parser.add_mutually_exclusive_group()
        scope_group.add_argument(
            "--user",
            action="store_true",
            help="Initialize user-level configuration (~/.claude/)"
        )
        scope_group.add_argument(
            "--project",
            action="store_true",
            help="Initialize project-level configuration (./.claude/) [default]"
        )
        
        # Project configuration options
        init_parser.add_argument(
            "--project-config",
            action="store_true",
            help="Initialize project configuration file (pacc.json)"
        )
        
        init_parser.add_argument(
            "--name",
            help="Project name (required with --project-config)"
        )
        
        init_parser.add_argument(
            "--version",
            default="1.0.0",
            help="Project version (default: 1.0.0)"
        )
        
        init_parser.add_argument(
            "--description",
            help="Project description"
        )
        
        init_parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing configuration files"
        )
        
        init_parser.set_defaults(func=self.init_command)
    
    def _add_sync_parser(self, subparsers) -> None:
        """Add the sync command parser."""
        sync_parser = subparsers.add_parser(
            "sync",
            help="Synchronize project extensions",
            description="Install extensions from project configuration (pacc.json)"
        )
        
        sync_parser.add_argument(
            "--environment", "-e",
            default="default",
            help="Environment to sync (default: default)"
        )
        
        sync_parser.add_argument(
            "--dry-run", "-n",
            action="store_true",
            help="Show what would be installed without making changes"
        )
        
        sync_parser.add_argument(
            "--force",
            action="store_true",
            help="Force installation, overwriting existing extensions"
        )
        
        sync_parser.add_argument(
            "--project-dir",
            type=Path,
            help="Project directory (default: current directory)"
        )
        
        sync_parser.set_defaults(func=self.sync_command)

    def _add_plugin_parser(self, subparsers) -> None:
        """Add the plugin command parser."""
        plugin_parser = subparsers.add_parser(
            "plugin",
            help="Manage Claude Code plugins",
            description="Install, list, enable, and disable Claude Code plugins from Git repositories"
        )
        
        plugin_subparsers = plugin_parser.add_subparsers(
            dest="plugin_command",
            help="Plugin commands",
            metavar="<plugin_command>"
        )
        
        # Plugin install command
        install_plugin_parser = plugin_subparsers.add_parser(
            "install",
            help="Install plugins from Git repository",
            description="Clone Git repository and install discovered Claude Code plugins"
        )
        
        install_plugin_parser.add_argument(
            "repo_url",
            help="Git repository URL (e.g., https://github.com/owner/repo)"
        )
        
        install_plugin_parser.add_argument(
            "--enable",
            action="store_true",
            help="Automatically enable installed plugins"
        )
        
        install_plugin_parser.add_argument(
            "--all",
            action="store_true",
            help="Install all plugins found in repository"
        )
        
        install_plugin_parser.add_argument(
            "--type", "-t",
            choices=["hooks", "agents", "mcps", "commands"],
            help="Install only plugins of specified type"
        )
        
        install_plugin_parser.add_argument(
            "--update",
            action="store_true", 
            help="Update repository if it already exists"
        )
        
        install_plugin_parser.add_argument(
            "--interactive", "-i",
            action="store_true",
            help="Interactively select plugins to install"
        )
        
        install_plugin_parser.add_argument(
            "--dry-run", "-n",
            action="store_true",
            help="Show what would be installed without making changes"
        )
        
        install_plugin_parser.set_defaults(func=self.handle_plugin_install)
        
        # Plugin list command
        list_plugin_parser = plugin_subparsers.add_parser(
            "list",
            aliases=["ls"],
            help="List installed plugins",
            description="List installed plugins and their status"
        )
        
        list_plugin_parser.add_argument(
            "--repo",
            help="Show plugins from specific repository (owner/repo format)"
        )
        
        list_plugin_parser.add_argument(
            "--type", "-t",
            choices=["hooks", "agents", "mcps", "commands"],
            help="Show only plugins of specified type"
        )
        
        list_plugin_parser.add_argument(
            "--enabled-only",
            action="store_true",
            help="Show only enabled plugins"
        )
        
        list_plugin_parser.add_argument(
            "--disabled-only", 
            action="store_true",
            help="Show only disabled plugins"
        )
        
        list_plugin_parser.add_argument(
            "--format",
            choices=["table", "list", "json"],
            default="table",
            help="Output format"
        )
        
        list_plugin_parser.set_defaults(func=self.handle_plugin_list)
        
        # Plugin enable command
        enable_plugin_parser = plugin_subparsers.add_parser(
            "enable",
            help="Enable a specific plugin",
            description="Enable a plugin by adding it to enabledPlugins in settings.json"
        )
        
        enable_plugin_parser.add_argument(
            "plugin",
            help="Plugin to enable (format: repo/plugin or just plugin name)"
        )
        
        enable_plugin_parser.add_argument(
            "--repo",
            help="Repository containing the plugin (owner/repo format)"
        )
        
        enable_plugin_parser.set_defaults(func=self.handle_plugin_enable)
        
        # Plugin disable command  
        disable_plugin_parser = plugin_subparsers.add_parser(
            "disable",
            help="Disable a specific plugin",
            description="Disable a plugin by removing it from enabledPlugins in settings.json"
        )
        
        disable_plugin_parser.add_argument(
            "plugin",
            help="Plugin to disable (format: repo/plugin or just plugin name)"
        )
        
        disable_plugin_parser.add_argument(
            "--repo", 
            help="Repository containing the plugin (owner/repo format)"
        )
        
        disable_plugin_parser.set_defaults(func=self.handle_plugin_disable)
        
        # Plugin update command
        update_plugin_parser = plugin_subparsers.add_parser(
            "update",
            help="Update plugins from Git repositories",
            description="Update plugins by pulling latest changes from Git repositories"
        )
        
        update_plugin_parser.add_argument(
            "plugin",
            nargs="?",
            help="Specific plugin to update (format: owner/repo or repo/plugin). If not specified, updates all plugins."
        )
        
        update_plugin_parser.add_argument(
            "--dry-run", "-n",
            action="store_true",
            help="Show what would be updated without making changes"
        )
        
        update_plugin_parser.add_argument(
            "--force", "-f",
            action="store_true",
            help="Force update even if there are conflicts (performs git reset --hard)"
        )
        
        update_plugin_parser.add_argument(
            "--show-diff",
            action="store_true", 
            help="Show diff of changes when updating"
        )
        
        update_plugin_parser.set_defaults(func=self.handle_plugin_update)
        
        # Plugin sync command
        sync_plugin_parser = plugin_subparsers.add_parser(
            "sync",
            help="Synchronize plugins from pacc.json configuration",
            description="Sync team plugins by reading pacc.json configuration and installing/updating required plugins"
        )
        
        sync_plugin_parser.add_argument(
            "--project-dir",
            type=Path,
            default=Path.cwd(),
            help="Project directory containing pacc.json (default: current directory)"
        )
        
        sync_plugin_parser.add_argument(
            "--environment", "-e",
            default="default",
            help="Environment to sync (default: default)"
        )
        
        sync_plugin_parser.add_argument(
            "--dry-run", "-n",
            action="store_true",
            help="Show what would be synced without making changes"
        )
        
        sync_plugin_parser.add_argument(
            "--force", "-f",
            action="store_true",
            help="Force sync even if there are conflicts"
        )
        
        sync_plugin_parser.add_argument(
            "--required-only",
            action="store_true",
            help="Only install required plugins, skip optional ones"
        )
        
        sync_plugin_parser.add_argument(
            "--optional-only",
            action="store_true",
            help="Only install optional plugins, skip required ones"
        )
        
        sync_plugin_parser.set_defaults(func=self.handle_plugin_sync)
        
        # Plugin info command
        info_plugin_parser = plugin_subparsers.add_parser(
            "info",
            help="Show detailed plugin information",
            description="Display detailed metadata, components, and status of a plugin"
        )
        
        info_plugin_parser.add_argument(
            "plugin",
            help="Plugin to show info for (format: repo/plugin or just plugin name)"
        )
        
        info_plugin_parser.add_argument(
            "--repo",
            help="Repository containing the plugin (owner/repo format)"
        )
        
        info_plugin_parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Output format"
        )
        
        info_plugin_parser.set_defaults(func=self.handle_plugin_info)
        
        # Plugin remove command
        remove_plugin_parser = plugin_subparsers.add_parser(
            "remove",
            aliases=["rm"],
            help="Remove/uninstall a plugin",
            description="Remove plugin from enabled plugins and optionally delete repository files"
        )
        
        remove_plugin_parser.add_argument(
            "plugin",
            help="Plugin to remove (format: repo/plugin or just plugin name)"
        )
        
        remove_plugin_parser.add_argument(
            "--repo",
            help="Repository containing the plugin (owner/repo format)"
        )
        
        remove_plugin_parser.add_argument(
            "--force", "-f",
            action="store_true",
            help="Skip confirmation prompts"
        )
        
        remove_plugin_parser.add_argument(
            "--keep-files",
            action="store_true",
            help="Remove from settings but keep repository files"
        )
        
        remove_plugin_parser.add_argument(
            "--dry-run", "-n",
            action="store_true",
            help="Show what would be removed without making changes"
        )
        
        remove_plugin_parser.set_defaults(func=self.handle_plugin_remove)
        
        # Plugin convert command
        convert_plugin_parser = plugin_subparsers.add_parser(
            "convert",
            help="Convert extensions to plugin format",
            description="Convert Claude Code extensions (hooks, agents, MCPs, commands) to plugin format"
        )
        
        convert_plugin_parser.add_argument(
            "extension",
            help="Path to extension file or directory to convert"
        )
        
        convert_plugin_parser.add_argument(
            "--name",
            help="Plugin name (auto-generated if not provided)"
        )
        
        convert_plugin_parser.add_argument(
            "--version",
            default="1.0.0",
            help="Plugin version (default: 1.0.0)"
        )
        
        convert_plugin_parser.add_argument(
            "--author",
            help="Plugin author information"
        )
        
        convert_plugin_parser.add_argument(
            "--repo",
            help="Git repository URL for direct push after conversion"
        )
        
        convert_plugin_parser.add_argument(
            "--local",
            action="store_true",
            default=True,
            help="Local-only conversion (default behavior)"
        )
        
        convert_plugin_parser.add_argument(
            "--batch",
            action="store_true",
            help="Convert all extensions in directory"
        )
        
        convert_plugin_parser.add_argument(
            "--output", "-o",
            type=Path,
            help="Output directory for converted plugins"
        )
        
        convert_plugin_parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing plugin directories"
        )
        
        convert_plugin_parser.set_defaults(func=self.handle_plugin_convert)
        
        # Plugin push command
        push_plugin_parser = plugin_subparsers.add_parser(
            "push",
            help="Push local plugin to Git repository",
            description="Push a local plugin directory to a Git repository"
        )
        
        push_plugin_parser.add_argument(
            "plugin",
            help="Path to local plugin directory"
        )
        
        push_plugin_parser.add_argument(
            "repo",
            help="Git repository URL (e.g., https://github.com/owner/repo)"
        )
        
        push_plugin_parser.add_argument(
            "--private",
            action="store_true",
            help="Repository is private (affects auth handling)"
        )
        
        push_plugin_parser.add_argument(
            "--auth",
            choices=["https", "ssh"],
            default="https",
            help="Authentication method (default: https)"
        )
        
        push_plugin_parser.set_defaults(func=self.handle_plugin_push)
        
        # Plugin search command
        search_plugin_parser = plugin_subparsers.add_parser(
            "search",
            help="Search for available plugins",
            description="Search community plugins and locally installed plugins"
        )
        
        search_plugin_parser.add_argument(
            "query",
            nargs="?",
            help="Search query (optional - shows all plugins if omitted)"
        )
        
        search_plugin_parser.add_argument(
            "--type", "-t",
            choices=["all", "command", "agent", "hook", "mcp"],
            default="all",
            help="Filter by plugin type (default: all)"
        )
        
        search_plugin_parser.add_argument(
            "--sort", "-s",
            choices=["relevance", "popularity", "date", "name"],
            default="relevance",
            help="Sort results by criteria (default: relevance)"
        )
        
        search_plugin_parser.add_argument(
            "--installed-only",
            action="store_true",
            help="Only show locally installed plugins"
        )
        
        search_plugin_parser.add_argument(
            "--exclude-installed",
            action="store_true",
            help="Exclude locally installed plugins from results"
        )
        
        search_plugin_parser.add_argument(
            "--recommendations",
            action="store_true",
            help="Show recommendations based on current project"
        )
        
        search_plugin_parser.add_argument(
            "--limit", "-l",
            type=int,
            default=20,
            help="Maximum number of results to show (default: 20)"
        )
        
        search_plugin_parser.set_defaults(func=self.handle_plugin_search)
        
        # Plugin create command
        create_plugin_parser = plugin_subparsers.add_parser(
            "create",
            help="Create new Claude Code plugin",
            description="Interactive wizard for creating new Claude Code plugins with templates"
        )
        
        create_plugin_parser.add_argument(
            "name",
            nargs="?",
            help="Plugin name (will prompt if not provided)"
        )
        
        create_plugin_parser.add_argument(
            "--type", "-t",
            choices=["hooks", "agents", "commands", "mcp"],
            help="Plugin type (will prompt if not provided)"
        )
        
        create_plugin_parser.add_argument(
            "--output-dir", "-o",
            type=str,
            default=".",
            help="Output directory for the plugin (default: current directory)"
        )
        
        create_plugin_parser.add_argument(
            "--mode", "-m",
            choices=["guided", "quick"],
            default="guided",
            help="Creation mode: guided (full wizard) or quick (minimal prompts) (default: guided)"
        )
        
        create_plugin_parser.add_argument(
            "--init-git",
            action="store_true",
            help="Initialize Git repository (will prompt in guided mode if not specified)"
        )
        
        create_plugin_parser.add_argument(
            "--no-git",
            action="store_true",
            help="Skip Git initialization"
        )
        
        create_plugin_parser.set_defaults(func=self.handle_plugin_create)
        
        # Plugin environment commands
        env_plugin_parser = plugin_subparsers.add_parser(
            "env",
            help="Manage Claude Code plugin environment",
            description="Configure environment variables for Claude Code plugin support"
        )
        
        env_subparsers = env_plugin_parser.add_subparsers(
            dest="env_command",
            help="Environment commands",
            metavar="<env_command>"
        )
        
        # Environment setup command
        setup_env_parser = env_subparsers.add_parser(
            "setup",
            help="Configure environment for plugins",
            description="Automatically configure ENABLE_PLUGINS environment variable"
        )
        setup_env_parser.add_argument(
            "--force",
            action="store_true",
            help="Force setup even if already configured"
        )
        setup_env_parser.set_defaults(func=self.handle_plugin_env_setup)
        
        # Environment status command
        status_env_parser = env_subparsers.add_parser(
            "status",
            help="Show environment status", 
            description="Display current environment configuration status"
        )
        status_env_parser.set_defaults(func=self.handle_plugin_env_status)
        
        # Environment verify command
        verify_env_parser = env_subparsers.add_parser(
            "verify",
            help="Verify environment configuration",
            description="Test if environment is properly configured for plugins"
        )
        verify_env_parser.set_defaults(func=self.handle_plugin_env_verify)
        
        # Environment reset command
        reset_env_parser = env_subparsers.add_parser(
            "reset",
            help="Reset environment configuration", 
            description="Remove PACC environment modifications"
        )
        reset_env_parser.add_argument(
            "--confirm",
            action="store_true",
            help="Skip confirmation prompt"
        )
        reset_env_parser.set_defaults(func=self.handle_plugin_env_reset)
        
        env_plugin_parser.set_defaults(func=self._plugin_env_help)
        
        plugin_parser.set_defaults(func=self._plugin_help)

    def install_command(self, args) -> int:
        """Handle the install command."""
        # Set JSON mode if requested
        self._set_json_mode(getattr(args, 'json', False))
        
        try:
            # Check source type and handle accordingly
            # Check for direct download URLs first (before Git URLs)
            if self._is_url(args.source):
                return self._install_from_url(args)
            elif self._is_git_url(args.source):
                return self._install_from_git(args)
            else:
                return self._install_from_local_path(args)
                
        except Exception as e:
            if self._json_output:
                result = CommandResult(
                    success=False,
                    message=f"Installation failed: {e}",
                    errors=[str(e)]
                )
                self._output_json_result(result)
            else:
                self._print_error(f"Installation failed: {e}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()
            return 1

    def _is_url(self, source: str) -> bool:
        """Check if source is a URL."""
        try:
            parsed = urlparse(source)
            return parsed.scheme in ('http', 'https')
        except Exception:
            return False
    
    def _is_git_url(self, source: str) -> bool:
        """Check if source is a Git repository URL."""
        try:
            from .sources.git import GitUrlParser
            parser = GitUrlParser()
            return parser.validate(source)
        except Exception:
            return False

    def _install_from_url(self, args) -> int:
        """Install from URL source."""
        if not HAS_URL_DOWNLOADER:
            self._print_error("URL downloads require additional dependencies.")
            self._print_error("Install with: pip install aiohttp")
            return 1
        
        # Determine installation scope
        if args.user:
            install_scope = "user"
            base_dir = Path.home() / ".claude"
        else:
            install_scope = "project"
            base_dir = Path.cwd() / ".claude"
        
        self._print_info(f"Installing from URL: {args.source}")
        self._print_info(f"Installation scope: {install_scope}")
        
        if args.dry_run:
            self._print_info("DRY RUN MODE - No changes will be made")
            return 0
        
        # Setup URL downloader
        cache_dir = base_dir / "cache" if not args.no_cache else None
        downloader = URLDownloader(
            max_file_size_mb=args.max_size,
            timeout_seconds=args.timeout,
            cache_dir=cache_dir
        )
        
        # Setup progress display
        progress_display = ProgressDisplay()
        
        # Create temporary download directory
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Download and extract if needed
            result = asyncio.run(downloader.install_from_url(
                args.source,
                temp_path,
                extract_archives=not args.no_extract,
                progress_callback=progress_display.display_progress
            ))
            
            if not result.success:
                self._print_error(f"Download failed: {result.error_message}")
                return 1
            
            self._print_success(f"Downloaded successfully")
            
            # Use the extracted path if available, otherwise the downloaded file
            source_path = result.final_path
            
            if not source_path or not source_path.exists():
                self._print_error("Downloaded content not found")
                return 1
            
            # Process the downloaded content as a local installation
            args.source = str(source_path)
            return self._install_from_local_path(args)

    def _install_from_git(self, args) -> int:
        """Install from Git repository source."""
        # Determine installation scope
        if args.user:
            install_scope = "user"
            base_dir = Path.home() / ".claude"
        else:
            install_scope = "project"
            base_dir = Path.cwd() / ".claude"
        
        self._print_info(f"Installing from Git repository: {args.source}")
        self._print_info(f"Installation scope: {install_scope}")
        
        if args.dry_run:
            self._print_info("DRY RUN MODE - No changes will be made")
        
        try:
            from .sources.git import GitSourceHandler
            handler = GitSourceHandler()
            
            # Process the Git repository and get extensions
            extensions = handler.process_source(
                args.source, 
                extension_type=args.type
            )
            
            if not extensions:
                self._print_error("No valid extensions found in Git repository")
                return 1
            
            # Convert to Extension objects (they should already be Extension objects)
            # Filter by type if specified
            if args.type:
                extensions = [ext for ext in extensions if ext.extension_type == args.type]
                if not extensions:
                    self._print_error(f"No {args.type} extensions found in repository")
                    return 1
            
            # Handle selection (similar to local installation)
            selected_extensions = []
            if len(extensions) == 1:
                selected_extensions = extensions
            elif args.all:
                selected_extensions = extensions
            elif args.interactive or (not args.all and len(extensions) > 1):
                # Use simplified interactive selection
                print(f"Found {len(extensions)} extensions in Git repository:")
                for i, ext in enumerate(extensions, 1):
                    desc = ext.description or "No description"
                    print(f"  {i}. {ext.name} ({ext.extension_type}) - {desc}")
                
                if args.interactive:
                    while True:
                        try:
                            choices = input("Select extensions (e.g., 1,3 or 'all' or 'none'): ").strip()
                            if choices.lower() == 'none':
                                selected_extensions = []
                                break
                            elif choices.lower() == 'all':
                                selected_extensions = extensions
                                break
                            else:
                                indices = [int(x.strip()) - 1 for x in choices.split(',')]
                                selected_extensions = [extensions[i] for i in indices if 0 <= i < len(extensions)]
                                break
                        except (ValueError, IndexError):
                            print("Invalid selection. Please try again.")
                            continue
                else:
                    selected_extensions = extensions
                    
                if not selected_extensions:
                    self._print_info("No extensions selected for installation")
                    return 0
            else:
                # Default: install all if multiple found
                selected_extensions = extensions
                self._print_info(f"Found {len(extensions)} extensions, installing all")
            
            # Validate selected extensions
            validation_errors = []
            for ext in selected_extensions:
                result = validate_extension_file(ext.file_path, ext.extension_type)
                
                if not result.is_valid:
                    validation_errors.append((ext, result))
                    continue
                
                if args.verbose:
                    formatted = ValidationResultFormatter.format_result(result, verbose=True)
                    self._print_info(f"Validation result:\n{formatted}")
            
            if validation_errors:
                self._print_error("Validation failed for some extensions:")
                for ext, result in validation_errors:
                    formatted = ValidationResultFormatter.format_result(result)
                    self._print_error(formatted)
                
                if not args.force:
                    self._print_error("Use --force to install despite validation errors")
                    return 1
            
            # Perform installation
            success_count = 0
            for ext in selected_extensions:
                try:
                    if args.dry_run:
                        self._print_info(f"Would install: {ext.name} ({ext.extension_type})")
                    else:
                        self._install_extension(ext, base_dir, args.force)
                        self._print_success(f"Installed: {ext.name} ({ext.extension_type})")
                    success_count += 1
                except Exception as e:
                    self._print_error(f"Failed to install {ext.name}: {e}")
                    if not args.force:
                        return 1
            
            if args.dry_run:
                self._print_info(f"Would install {success_count} extension(s) from Git repository")
            else:
                self._print_success(f"Successfully installed {success_count} extension(s) from Git repository")
            
            return 0
            
        except Exception as e:
            self._print_error(f"Git installation failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1

    def _install_from_local_path(self, args) -> int:
        """Install from local file/directory path."""
        source_path = Path(args.source).resolve()
        
        # Validate source path
        if not source_path.exists():
            self._print_error(f"Source path does not exist: {source_path}")
            return 1
        
        # Determine installation scope
        if args.user:
            install_scope = "user"
            base_dir = Path.home() / ".claude"
        else:
            install_scope = "project"
            base_dir = Path.cwd() / ".claude"
        
        self._print_info(f"Installing from: {source_path}")
        self._print_info(f"Installation scope: {install_scope}")
        
        if args.dry_run:
            self._print_info("DRY RUN MODE - No changes will be made")
        
        # Detect extensions
        if source_path.is_file():
            ext_type = ExtensionDetector.detect_extension_type(source_path)
            if not ext_type:
                self._print_error(f"No valid extensions detected in: {source_path}")
                return 1
            extension = Extension(
                name=source_path.stem,
                file_path=source_path,
                extension_type=ext_type,
                description=None
            )
            extensions = [extension]
        else:
            detected_files = ExtensionDetector.scan_directory(source_path)
            extensions = []
            for ext_type, file_paths in detected_files.items():
                for file_path in file_paths:
                    extension = Extension(
                        name=file_path.stem,
                        file_path=file_path,
                        extension_type=ext_type,
                        description=None
                    )
                    extensions.append(extension)
            
            if not extensions:
                self._print_error(f"No valid extensions found in: {source_path}")
                return 1
        
        # Filter by type if specified
        if args.type:
            extensions = [ext for ext in extensions if ext.extension_type == args.type]
            if not extensions:
                self._print_error(f"No {args.type} extensions found in source")
                return 1
        
        # Handle selection
        selected_extensions = []
        if len(extensions) == 1:
            selected_extensions = extensions
        elif args.all:
            selected_extensions = extensions
        elif args.interactive or (not args.all and len(extensions) > 1):
            # Use simplified interactive selection for now
            print(f"Found {len(extensions)} extensions:")
            for i, ext in enumerate(extensions, 1):
                print(f"  {i}. {ext.name} ({ext.extension_type})")
            
            if args.interactive:
                while True:
                    try:
                        choices = input("Select extensions (e.g., 1,3 or 'all' or 'none'): ").strip()
                        if choices.lower() == 'none':
                            selected_extensions = []
                            break
                        elif choices.lower() == 'all':
                            selected_extensions = extensions
                            break
                        else:
                            indices = [int(x.strip()) - 1 for x in choices.split(',')]
                            selected_extensions = [extensions[i] for i in indices if 0 <= i < len(extensions)]
                            break
                    except (ValueError, IndexError):
                        print("Invalid selection. Please try again.")
                        continue
            else:
                selected_extensions = extensions
                
            if not selected_extensions:
                self._print_info("No extensions selected for installation")
                return 0
        else:
            # Default: install all if multiple found
            selected_extensions = extensions
            self._print_info(f"Found {len(extensions)} extensions, installing all")
        
        # Validate selected extensions
        validation_errors = []
        for ext in selected_extensions:
            result = validate_extension_file(ext.file_path, ext.extension_type)
            
            if not result.is_valid:
                validation_errors.append((ext, result))
                continue
            
            if args.verbose:
                formatted = ValidationResultFormatter.format_result(result, verbose=True)
                self._print_info(f"Validation result:\n{formatted}")
        
        if validation_errors:
            self._print_error("Validation failed for some extensions:")
            for ext, result in validation_errors:
                formatted = ValidationResultFormatter.format_result(result)
                self._print_error(formatted)
            
            if not args.force:
                self._print_error("Use --force to install despite validation errors")
                return 1
        
        # Perform installation
        success_count = 0
        for ext in selected_extensions:
            try:
                if args.dry_run:
                    self._print_info(f"Would install: {ext.name} ({ext.extension_type})")
                else:
                    self._install_extension(ext, base_dir, args.force)
                    self._print_success(f"Installed: {ext.name} ({ext.extension_type})")
                success_count += 1
            except Exception as e:
                self._print_error(f"Failed to install {ext.name}: {e}")
                if not args.force:
                    return 1
        
        if self._json_output:
            result = CommandResult(
                success=True,
                message=f"{'Would install' if args.dry_run else 'Successfully installed'} {success_count} extension(s)",
                data={
                    "installed_count": success_count,
                    "dry_run": args.dry_run,
                    "extensions": [
                        {
                            "name": ext.name,
                            "type": ext.extension_type,
                            "description": ext.description,
                            "file_path": str(ext.file_path)
                        }
                        for ext in selected_extensions
                    ]
                }
            )
            self._output_json_result(result)
        else:
            if args.dry_run:
                self._print_info(f"Would install {success_count} extension(s)")
            else:
                self._print_success(f"Successfully installed {success_count} extension(s)")
        
        return 0

    def validate_command(self, args) -> int:
        """Handle the validate command."""
        try:
            source_path = Path(args.source).resolve()
            
            if not source_path.exists():
                self._print_error(f"Source path does not exist: {source_path}")
                return 1
            
            # Run validation
            if source_path.is_file():
                result = validate_extension_file(source_path, args.type)
                results = [result] if result else []
            else:
                results = validate_extension_directory(source_path, args.type)
            
            if not results:
                self._print_error("No valid extensions found to validate")
                return 1
            
            # Format and display results
            formatter = ValidationResultFormatter()
            output = formatter.format_batch_results(results, show_summary=True)
            print(output)
            
            # Check for errors
            error_count = sum(len(r.errors) for r in results)
            warning_count = sum(len(r.warnings) for r in results)
            
            if error_count > 0:
                return 1
            elif args.strict and warning_count > 0:
                self._print_error("Validation failed in strict mode due to warnings")
                return 1
            
            return 0
            
        except Exception as e:
            self._print_error(f"Validation failed: {e}")
            return 1

    def init_command(self, args) -> int:
        """Handle the init command."""
        try:
            if args.project_config:
                return self._init_project_config(args)
            else:
                return self._init_pacc_directories(args)
                
        except Exception as e:
            self._print_error(f"Initialization failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def _init_project_config(self, args) -> int:
        """Initialize project configuration file (pacc.json)."""
        project_dir = Path.cwd()
        config_path = project_dir / "pacc.json"
        
        # Check if project name is provided
        if not args.name:
            self._print_error("Project name is required when using --project-config")
            self._print_error("Use: pacc init --project-config --name <project-name>")
            return 1
        
        # Check if config already exists
        if config_path.exists() and not args.force:
            self._print_error(f"Project configuration already exists: {config_path}")
            self._print_error("Use --force to overwrite existing configuration")
            return 1
        
        # Create project configuration
        config = {
            "name": args.name,
            "version": args.version,
            "extensions": {}
        }
        
        if args.description:
            config["description"] = args.description
        
        # Initialize project config
        config_manager = ProjectConfigManager()
        config_manager.init_project_config(project_dir, config)
        
        self._print_success(f"Initialized project configuration: {config_path}")
        self._print_info(f"Project: {args.name} v{args.version}")
        
        # Suggest next steps
        self._print_info("\nNext steps:")
        self._print_info("  1. Add extensions to pacc.json")
        self._print_info("  2. Run 'pacc sync' to install extensions")
        
        return 0
    
    def _init_pacc_directories(self, args) -> int:
        """Initialize PACC directories and basic configuration."""
        # Determine scope
        if args.user:
            base_dir = Path.home() / ".claude"
            scope_name = "user"
        else:
            base_dir = Path.cwd() / ".claude"
            scope_name = "project"
        
        self._print_info(f"Initializing {scope_name}-level PACC configuration")
        self._print_info(f"Directory: {base_dir}")
        
        # Create directories
        extension_dirs = ["hooks", "mcps", "agents", "commands"]
        for ext_dir in extension_dirs:
            dir_path = base_dir / ext_dir
            dir_path.mkdir(parents=True, exist_ok=True)
            self._print_info(f"Created directory: {dir_path}")
        
        # Create basic settings.json if it doesn't exist
        settings_path = base_dir / "settings.json"
        if not settings_path.exists() or args.force:
            config_manager = ClaudeConfigManager()
            default_config = config_manager._get_default_config()
            config_manager.save_config(default_config, settings_path)
            self._print_success(f"Created configuration: {settings_path}")
        else:
            self._print_info(f"Configuration already exists: {settings_path}")
        
        self._print_success(f"Successfully initialized {scope_name}-level PACC configuration")
        return 0
    
    def sync_command(self, args) -> int:
        """Handle the sync command."""
        try:
            # Determine project directory
            project_dir = args.project_dir if args.project_dir else Path.cwd()
            
            self._print_info(f"Synchronizing project extensions from: {project_dir}")
            self._print_info(f"Environment: {args.environment}")
            
            if args.dry_run:
                self._print_info("DRY RUN MODE - No changes will be made")
            
            # Check if pacc.json exists
            config_path = project_dir / "pacc.json"
            if not config_path.exists():
                self._print_error(f"No pacc.json found in {project_dir}")
                self._print_error("Initialize with: pacc init --project-config --name <project-name>")
                return 1
            
            # Validate project configuration first
            config_manager = ProjectConfigManager()
            validation_result = config_manager.validate_project_config(project_dir)
            
            if not validation_result.is_valid:
                self._print_error("Project configuration validation failed:")
                for error in validation_result.errors:
                    self._print_error(f"  {error.code}: {error.message}")
                return 1
            
            if validation_result.warnings and args.verbose:
                self._print_warning("Project configuration warnings:")
                for warning in validation_result.warnings:
                    self._print_warning(f"  {warning.code}: {warning.message}")
            
            # Perform synchronization
            sync_manager = ProjectSyncManager()
            sync_result = sync_manager.sync_project(
                project_dir=project_dir,
                environment=args.environment,
                dry_run=args.dry_run
            )
            
            # Report results
            if sync_result.success:
                if args.dry_run:
                    self._print_success(f"Would install {sync_result.installed_count} extensions")
                else:
                    self._print_success(f"Successfully installed {sync_result.installed_count} extensions")
                
                if sync_result.updated_count > 0:
                    self._print_info(f"Updated {sync_result.updated_count} existing extensions")
                
                if sync_result.warnings:
                    self._print_warning("Warnings during sync:")
                    for warning in sync_result.warnings:
                        self._print_warning(f"  {warning}")
                
                return 0
            else:
                self._print_error(f"Synchronization failed: {sync_result.error_message}")
                
                if sync_result.failed_extensions:
                    self._print_error("Failed extensions:")
                    for failed_ext in sync_result.failed_extensions:
                        self._print_error(f"  {failed_ext}")
                
                return 1
                
        except Exception as e:
            self._print_error(f"Sync failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1

    def list_command(self, args) -> int:
        """Handle the list command."""
        # Set JSON mode if requested or if format is json
        self._set_json_mode(getattr(args, 'json', False) or args.format == 'json')
        
        try:
            from fnmatch import fnmatch
            from datetime import datetime, timezone
            import json
            
            # Determine which scopes to list
            scopes_to_check = []
            if args.user:
                scopes_to_check.append(("user", True))
            elif args.project:
                scopes_to_check.append(("project", False))
            else:  # Default to all scopes
                scopes_to_check.append(("user", True))
                scopes_to_check.append(("project", False))
            
            # Collect all extensions from requested scopes
            all_extensions = []
            config_manager = ClaudeConfigManager()
            
            for scope_name, is_user_level in scopes_to_check:
                try:
                    config_path = config_manager.get_config_path(user_level=is_user_level)
                    config = config_manager.load_config(config_path)
                    
                    # Extract extensions with metadata
                    for ext_type in ["hooks", "mcps", "agents", "commands"]:
                        if args.type and ext_type != args.type:
                            continue
                            
                        for ext in config.get(ext_type, []):
                            # Add extension type and scope info
                            ext_data = ext.copy()
                            ext_data["type"] = ext_type.rstrip("s")  # Remove plural 's'
                            ext_data["scope"] = scope_name
                            ext_data["scope_path"] = str(config_path.parent)
                            all_extensions.append(ext_data)
                            
                except Exception as e:
                    if args.verbose:
                        self._print_warning(f"Failed to load {scope_name} config: {e}")
                    continue
            
            if not all_extensions:
                if self._json_output:
                    result = CommandResult(
                        success=True,
                        message="No extensions installed",
                        data={"extensions": [], "count": 0}
                    )
                    self._output_json_result(result)
                else:
                    self._print_info("No extensions installed")
                return 0
            
            # Apply filters
            filtered_extensions = all_extensions
            
            # Filter by name pattern
            if args.filter:
                filtered_extensions = [
                    ext for ext in filtered_extensions
                    if fnmatch(ext.get("name", ""), args.filter)
                ]
            
            # Search in descriptions
            if args.search:
                search_lower = args.search.lower()
                filtered_extensions = [
                    ext for ext in filtered_extensions
                    if search_lower in ext.get("description", "").lower()
                ]
            
            if not filtered_extensions:
                self._print_info("No extensions match the criteria")
                return 0
            
            # Sort extensions
            if args.sort == "name":
                filtered_extensions.sort(key=lambda x: x.get("name", "").lower())
            elif args.sort == "type":
                filtered_extensions.sort(key=lambda x: (x.get("type", ""), x.get("name", "").lower()))
            elif args.sort == "date":
                # Sort by installation date (newest first)
                def get_date(ext):
                    date_str = ext.get("installed_at", "")
                    if date_str:
                        try:
                            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        except:
                            pass
                    # Use timezone-aware min datetime to match parsed dates
                    return datetime.min.replace(tzinfo=timezone.utc)
                filtered_extensions.sort(key=get_date, reverse=True)
            
            # Format and display output
            if self._json_output:
                result = CommandResult(
                    success=True,
                    message=f"Found {len(filtered_extensions)} extension(s)",
                    data={
                        "extensions": filtered_extensions,
                        "count": len(filtered_extensions),
                        "filter_applied": bool(args.filter or args.search),
                        "scope": "user" if args.user else "project" if args.project else "all"
                    }
                )
                self._output_json_result(result)
                
            elif args.format == "list":
                # Simple list format
                for ext in filtered_extensions:
                    name = ext.get("name", "unknown")
                    ext_type = ext.get("type", "unknown")
                    desc = ext.get("description", "")
                    scope = ext.get("scope", "")
                    
                    line = f"{ext_type}/{name}"
                    if desc:
                        line += f" - {desc}"
                    if len(scopes_to_check) > 1:  # Show scope when listing multiple
                        line += f" [{scope}]"
                    print(line)
                    
            else:  # table format
                self._print_extensions_table(filtered_extensions, args.verbose, args.show_status, len(scopes_to_check) > 1)
            
            return 0
            
        except Exception as e:
            self._print_error(f"Failed to list extensions: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def _print_extensions_table(self, extensions, verbose=False, show_status=False, show_scope=False):
        """Print extensions in a formatted table."""
        if not extensions:
            return
        
        # Define columns
        headers = ["Name", "Type", "Description"]
        if show_scope:
            headers.append("Scope")
        if verbose:
            headers.extend(["Source", "Installed"])
            if any("version" in ext for ext in extensions):
                headers.append("Version")
        if verbose and show_status and any("validation_status" in ext for ext in extensions):
            headers.append("Status")
        
        # Calculate column widths
        col_widths = [len(h) for h in headers]
        rows = []
        
        for ext in extensions:
            row = [
                ext.get("name", ""),
                ext.get("type", ""),
                ext.get("description", "")[:50] + "..." if len(ext.get("description", "")) > 50 else ext.get("description", "")
            ]
            
            if show_scope:
                row.append(ext.get("scope", ""))
                
            if verbose:
                row.append(ext.get("source", "unknown"))
                
                # Format installation date
                date_str = ext.get("installed_at", "")
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        row.append(dt.strftime("%Y-%m-%d %H:%M"))
                    except:
                        row.append(date_str)
                else:
                    row.append("unknown")
                
                if any("version" in ext for ext in extensions):
                    row.append(ext.get("version", "-"))
                    
            if verbose and show_status and any("validation_status" in ext for ext in extensions):
                status = ext.get("validation_status", "unknown")
                # Add color/symbol based on status
                if status == "valid":
                    row.append("✓ valid")
                elif status == "warning":
                    row.append("⚠ warning")
                elif status == "error":
                    row.append("✗ error")
                else:
                    row.append(status)
            
            rows.append(row)
            
            # Update column widths
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))
        
        # Print header
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        print(header_line)
        print("-" * len(header_line))
        
        # Print rows
        for row in rows:
            print(" | ".join(str(val).ljust(w) for val, w in zip(row, col_widths)))

    def remove_command(self, args) -> int:
        """Handle the remove command."""
        # Set JSON mode if requested
        self._set_json_mode(getattr(args, 'json', False))
        
        try:
            # Determine removal scope
            if args.user:
                remove_scope = "user"
                is_user_level = True
                base_dir = Path.home() / ".claude"
            else:
                remove_scope = "project"
                is_user_level = False
                base_dir = Path.cwd() / ".claude"
            
            self._print_info(f"Removing extension: {args.name}")
            self._print_info(f"Removal scope: {remove_scope}")
            
            if args.dry_run:
                self._print_info("DRY RUN MODE - No changes will be made")
            
            # Get configuration path and load config
            config_manager = ClaudeConfigManager()
            config_path = config_manager.get_config_path(user_level=is_user_level)
            
            if not config_path.exists():
                self._print_error(f"No configuration found at {remove_scope} level")
                return 1
            
            config = config_manager.load_config(config_path)
            
            # Find extension to remove
            extension_info = self._find_extension_to_remove(args.name, args.type, config)
            
            if not extension_info:
                self._print_error(f"Extension '{args.name}' not found")
                if args.type:
                    self._print_error(f"No {args.type} extension named '{args.name}' found")
                else:
                    self._print_error(f"No extension named '{args.name}' found in any type")
                return 1
            
            extension_type, extension_config, extension_index = extension_info
            
            # Check for dependencies unless force is specified
            if not args.force:
                dependencies = self._find_extension_dependencies(args.name, config)
                if dependencies:
                    self._print_error(f"Cannot remove '{args.name}' - it has dependencies:")
                    for dep in dependencies:
                        dep_type = self._get_extension_type_from_config(dep, config)
                        self._print_error(f"  - {dep['name']} ({dep_type})")
                    self._print_error("Use --force to remove anyway")
                    return 1
            
            # Show extension details
            if args.verbose:
                self._print_extension_details(extension_config, extension_type)
            
            # Confirmation prompt
            if not args.confirm and not args.dry_run:
                if not self._confirm_removal(extension_config, extension_type):
                    self._print_info("Removal cancelled")
                    return 0
            
            if args.dry_run:
                self._print_info(f"Would remove: {args.name} ({extension_type})")
                extension_path = base_dir / extension_config.get('path', '')
                if extension_path.exists():
                    self._print_info(f"Would delete file: {extension_path}")
                return 0
            
            # Perform atomic removal
            success = self._remove_extension_atomic(
                extension_config, extension_type, extension_index, 
                config, config_path, base_dir, args.verbose
            )
            
            if success:
                if self._json_output:
                    result = CommandResult(
                        success=True,
                        message=f"Successfully removed: {args.name} ({extension_type})",
                        data={
                            "removed_extension": {
                                "name": args.name,
                                "type": extension_type,
                                "scope": remove_scope
                            }
                        }
                    )
                    self._output_json_result(result)
                else:
                    self._print_success(f"Successfully removed: {args.name} ({extension_type})")
                return 0
            else:
                if self._json_output:
                    result = CommandResult(
                        success=False,
                        message=f"Failed to remove: {args.name}",
                        errors=[f"Extension removal failed: {args.name}"]
                    )
                    self._output_json_result(result)
                else:
                    self._print_error(f"Failed to remove: {args.name}")
                return 1
                
        except Exception as e:
            self._print_error(f"Removal failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1

    def info_command(self, args) -> int:
        """Handle the info command."""
        try:
            source = args.source
            
            # Determine if source is a file path or installed extension name
            source_path = Path(source)
            
            if source_path.exists():
                # Source is a file path - validate and extract info
                return self._handle_info_for_file(source_path, args)
            elif source_path.is_absolute() or "/" in source or "\\" in source:
                # Source looks like a file path but doesn't exist
                self._print_error(f"File does not exist: {source_path}")
                return 1
            else:
                # Source might be an installed extension name
                return self._handle_info_for_installed(source, args)
                
        except Exception as e:
            self._print_error(f"Failed to get extension info: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1

    def _handle_info_for_file(self, file_path: Path, args) -> int:
        """Handle info command for file path."""
        # Validate the extension file
        result = validate_extension_file(file_path, args.type)
        
        if not result:
            self._print_error(f"No valid extension found at: {file_path}")
            return 1
        
        # Extract additional file information
        file_info = self._get_file_info(file_path)
        
        # Create comprehensive info object
        extension_info = {
            "name": result.metadata.get("name", file_path.stem),
            "description": result.metadata.get("description", "No description available"),
            "version": result.metadata.get("version", "Unknown"),
            "type": result.extension_type,
            "file_path": str(file_path),
            "file_size": file_info.get("size", 0),
            "last_modified": file_info.get("modified", "Unknown"),
            "validation": {
                "is_valid": result.is_valid,
                "errors": [{"code": err.code, "message": err.message, "line": err.line_number} 
                          for err in result.errors],
                "warnings": [{"code": warn.code, "message": warn.message, "line": warn.line_number} 
                           for warn in result.warnings]
            },
            "metadata": result.metadata
        }
        
        # Display the information
        if getattr(args, 'json', False):
            return self._display_info_json(extension_info)
        else:
            return self._display_info_formatted(extension_info, args)
    
    def _handle_info_for_installed(self, extension_name: str, args) -> int:
        """Handle info command for installed extension name."""
        config_manager = ClaudeConfigManager()
        
        # Search in both user and project configs
        for is_user_level in [False, True]:  # Project first, then user
            try:
                config_path = config_manager.get_config_path(user_level=is_user_level)
                config = config_manager.load_config(config_path)
                
                # Search through all extension types
                for ext_type in ["hooks", "mcps", "agents", "commands"]:
                    if args.type and ext_type != args.type:
                        continue
                        
                    for ext_config in config.get(ext_type, []):
                        if ext_config.get("name") == extension_name:
                            # Found the extension
                            extension_info = self._build_installed_extension_info(
                                ext_config, ext_type, config_path.parent, is_user_level
                            )
                            
                            if getattr(args, 'json', False):
                                return self._display_info_json(extension_info)
                            else:
                                return self._display_info_formatted(extension_info, args)
                                
            except Exception as e:
                if args.verbose:
                    self._print_warning(f"Failed to load {'user' if is_user_level else 'project'} config: {e}")
                continue
        
        # Extension not found
        self._print_error(f"Extension '{extension_name}' not found in installed extensions")
        return 1
    
    def _get_file_info(self, file_path: Path) -> dict:
        """Get file system information about an extension file."""
        try:
            stat = file_path.stat()
            from datetime import datetime
            
            return {
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "permissions": oct(stat.st_mode)[-3:]
            }
        except Exception:
            return {"size": 0, "modified": "Unknown", "permissions": "Unknown"}
    
    def _build_installed_extension_info(self, ext_config: dict, ext_type: str, 
                                      config_dir: Path, is_user_level: bool) -> dict:
        """Build comprehensive info object for installed extension."""
        extension_info = {
            "name": ext_config.get("name", "Unknown"),
            "description": ext_config.get("description", "No description available"),
            "version": ext_config.get("version", "Unknown"),
            "type": ext_type.rstrip("s"),  # Remove plural 's'
            "scope": "user" if is_user_level else "project",
            "config_path": str(config_dir / "settings.json"),
            "installation": {
                "installed_at": ext_config.get("installed_at", "Unknown"),
                "source": ext_config.get("source", "Unknown"),
                "validation_status": ext_config.get("validation_status", "Unknown")
            },
            "configuration": ext_config
        }
        
        # Add file information if path exists
        if "path" in ext_config:
            ext_file_path = config_dir / ext_config["path"]
            if ext_file_path.exists():
                file_info = self._get_file_info(ext_file_path)
                extension_info["file_info"] = {
                    "path": str(ext_file_path),
                    "size": file_info.get("size", 0),
                    "last_modified": file_info.get("modified", "Unknown")
                }
                
                # Re-validate the file if it exists
                try:
                    result = validate_extension_file(ext_file_path, ext_type.rstrip("s"))
                    if result:
                        extension_info["validation"] = {
                            "is_valid": result.is_valid,
                            "errors": [{"code": err.code, "message": err.message, "line": err.line_number} 
                                     for err in result.errors],
                            "warnings": [{"code": warn.code, "message": warn.message, "line": warn.line_number} 
                                       for warn in result.warnings]
                        }
                        extension_info["current_metadata"] = result.metadata
                except Exception:
                    pass  # Validation failed, but that's okay for info display
        
        return extension_info
    
    def _display_info_json(self, extension_info: dict) -> int:
        """Display extension information in JSON format."""
        import json
        print(json.dumps(extension_info, indent=2, ensure_ascii=False))
        return 0
    
    def _display_info_formatted(self, extension_info: dict, args) -> int:
        """Display extension information in formatted text."""
        name = extension_info.get("name", "Unknown")
        description = extension_info.get("description", "No description")
        version = extension_info.get("version", "Unknown")
        ext_type = extension_info.get("type", "Unknown")
        
        # Header section
        print(f"\n{'='*60}")
        print(f"📦 {name}")
        print(f"{'='*60}")
        print(f"Type:        {ext_type}")
        print(f"Version:     {version}")
        print(f"Description: {description}")
        
        # Installation info for installed extensions
        if "installation" in extension_info:
            install_info = extension_info["installation"]
            scope = extension_info.get("scope", "unknown")
            print(f"\n🔧 Installation Info:")
            print(f"Scope:        {scope}")
            print(f"Installed:    {install_info.get('installed_at', 'Unknown')}")
            print(f"Source:       {install_info.get('source', 'Unknown')}")
            print(f"Status:       {self._format_validation_status(install_info.get('validation_status', 'Unknown'))}")
        
        # File information
        if "file_path" in extension_info:
            print(f"\n📁 File Info:")
            print(f"Path:         {extension_info['file_path']}")
            print(f"Size:         {self._format_file_size(extension_info.get('file_size', 0))}")
            print(f"Modified:     {extension_info.get('last_modified', 'Unknown')}")
        elif "file_info" in extension_info:
            file_info = extension_info["file_info"]
            print(f"\n📁 File Info:")
            print(f"Path:         {file_info['path']}")
            print(f"Size:         {self._format_file_size(file_info.get('size', 0))}")
            print(f"Modified:     {file_info.get('last_modified', 'Unknown')}")
        
        # Validation results
        if "validation" in extension_info:
            validation = extension_info["validation"]
            print(f"\n✅ Validation Results:")
            print(f"Valid:        {'✓ Yes' if validation['is_valid'] else '✗ No'}")
            
            if validation.get("errors"):
                print(f"Errors:       {len(validation['errors'])}")
                if args.verbose:
                    for error in validation["errors"]:
                        line_info = f" (line {error['line']})" if error.get('line') else ""
                        print(f"  ✗ {error['code']}: {error['message']}{line_info}")
            
            if validation.get("warnings"):
                print(f"Warnings:     {len(validation['warnings'])}")
                if args.verbose:
                    for warning in validation["warnings"]:
                        line_info = f" (line {warning['line']})" if warning.get('line') else ""
                        print(f"  ⚠ {warning['code']}: {warning['message']}{line_info}")
        
        # Type-specific metadata
        metadata = extension_info.get("metadata") or extension_info.get("current_metadata", {})
        if metadata and args.verbose:
            print(f"\n🔍 Extension Details:")
            self._display_type_specific_info(ext_type, metadata)
        
        # Configuration details for installed extensions
        if "configuration" in extension_info and args.verbose:
            config = extension_info["configuration"]
            print(f"\n⚙️ Configuration:")
            for key, value in config.items():
                if key not in ["name", "description", "version"]:
                    print(f"  {key}: {value}")
        
        # Related extensions and suggestions
        if getattr(args, 'show_related', False):
            self._show_related_extensions(extension_info, args)
        
        # Usage examples
        if getattr(args, 'show_usage', False):
            self._show_usage_examples(extension_info)
        
        # Troubleshooting info
        if getattr(args, 'show_troubleshooting', False):
            self._show_troubleshooting_info(extension_info)
        
        print()  # Final newline
        return 0
    
    def _format_validation_status(self, status: str) -> str:
        """Format validation status with appropriate symbols."""
        status_symbols = {
            "valid": "✓ Valid",
            "warning": "⚠ Warning", 
            "error": "✗ Error",
            "unknown": "? Unknown"
        }
        return status_symbols.get(status.lower(), f"? {status}")
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    
    def _display_type_specific_info(self, ext_type: str, metadata: dict) -> None:
        """Display type-specific information based on extension type."""
        if ext_type == "hooks":
            if "event_types" in metadata:
                print(f"  Event Types:  {', '.join(metadata['event_types'])}")
            if "command_count" in metadata:
                print(f"  Commands:     {metadata['command_count']}")
            if "has_matchers" in metadata:
                print(f"  Has Matchers: {'Yes' if metadata['has_matchers'] else 'No'}")
        
        elif ext_type == "agents":
            if "model" in metadata:
                print(f"  Model:        {metadata['model']}")
            if "tools" in metadata:
                print(f"  Tools:        {', '.join(metadata['tools'])}")
            if "system_prompt" in metadata:
                prompt_preview = metadata["system_prompt"][:50] + "..." if len(metadata.get("system_prompt", "")) > 50 else metadata.get("system_prompt", "")
                print(f"  System Prompt: {prompt_preview}")
        
        elif ext_type == "mcps":
            if "command" in metadata:
                print(f"  Command:      {metadata['command']}")
            if "args" in metadata:
                print(f"  Arguments:    {metadata['args']}")
        
        elif ext_type == "commands":
            if "aliases" in metadata:
                print(f"  Aliases:      {', '.join(metadata['aliases'])}")
    
    def _show_related_extensions(self, extension_info: dict, args) -> None:
        """Show related extensions and suggestions."""
        ext_type = extension_info.get("type", "")
        name = extension_info.get("name", "")
        
        print(f"\n🔗 Related Extensions:")
        
        # Find related extensions by type
        config_manager = ClaudeConfigManager()
        related_extensions = []
        
        for is_user_level in [False, True]:
            try:
                config_path = config_manager.get_config_path(user_level=is_user_level)
                config = config_manager.load_config(config_path)
                
                # Get extensions of the same type
                extensions = config.get(f"{ext_type}s", [])
                for ext in extensions:
                    if ext.get("name") != name:  # Exclude the current extension
                        related_extensions.append({
                            "name": ext.get("name", "Unknown"),
                            "description": ext.get("description", "No description"),
                            "scope": "user" if is_user_level else "project"
                        })
                        
            except Exception:
                continue
        
        if related_extensions:
            for ext in related_extensions[:5]:  # Show max 5 related
                scope_info = f" [{ext['scope']}]" if len(related_extensions) > 1 else ""
                print(f"  • {ext['name']}{scope_info} - {ext['description']}")
        else:
            print(f"  No other {ext_type} extensions found")
    
    def _show_usage_examples(self, extension_info: dict) -> None:
        """Show usage examples where available."""
        ext_type = extension_info.get("type", "")
        name = extension_info.get("name", "")
        
        print(f"\n💡 Usage Examples:")
        
        if ext_type == "hooks":
            print(f"  # Hook '{name}' will be automatically triggered on configured events")
            print(f"  # No manual invocation required")
        elif ext_type == "agents":
            print(f"  # Use agent '{name}' in Claude Code:")
            print(f"  @{name} <your request>")
        elif ext_type == "commands":
            print(f"  # Use command '{name}' in Claude Code:")
            print(f"  /{name} <arguments>")
        elif ext_type == "mcps":
            print(f"  # MCP server '{name}' provides tools/resources")
            print(f"  # Available automatically when Claude Code starts")
        else:
            print(f"  Usage examples not available for {ext_type} extensions")
    
    def _show_troubleshooting_info(self, extension_info: dict) -> None:
        """Show troubleshooting information."""
        print(f"\n🔧 Troubleshooting:")
        
        validation = extension_info.get("validation", {})
        if not validation.get("is_valid", True):
            print(f"  Extension has validation errors:")
            for error in validation.get("errors", []):
                print(f"    • Fix: {error['message']}")
        else:
            print(f"  • Extension appears to be correctly configured")
            print(f"  • Check Claude Code logs if extension isn't working")
            print(f"  • Verify extension is enabled in settings")
        
        # Type-specific troubleshooting
        ext_type = extension_info.get("type", "")
        if ext_type == "hooks":
            print(f"  • Ensure hook events match your use case")
            print(f"  • Check that matchers are correctly configured")
        elif ext_type == "mcps":
            print(f"  • Verify MCP server executable is available")
            print(f"  • Check server logs for connection issues")

    def _install_extension(self, extension, base_dir: Path, force: bool = False) -> None:
        """Install a single extension with configuration management."""
        import shutil
        import json
        from pathlib import Path
        
        # Create extension type directory
        ext_dir = base_dir / extension.extension_type
        ext_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy the extension file
        dest_path = ext_dir / extension.file_path.name
        
        if dest_path.exists() and not force:
            raise ValueError(f"Extension already exists: {dest_path}. Use --force to overwrite.")
        
        shutil.copy2(extension.file_path, dest_path)
        
        # Only update settings.json for hooks and mcps
        # Agents and commands are file-based and don't need configuration entries
        if extension.extension_type in ["hooks", "mcps"]:
            # Update configuration using the JSON merger
            config_manager = ClaudeConfigManager()
            config_path = base_dir / "settings.json"
            
            # Load extension metadata for configuration
            extension_config = self._create_extension_config(extension, dest_path)
            
            # Add to configuration
            from pathlib import Path
            home_claude_dir = Path.home() / '.claude'
            is_user_level = base_dir.resolve() == home_claude_dir.resolve()
            success = config_manager.add_extension_config(
                extension.extension_type, 
                extension_config,
                user_level=is_user_level
            )
            
            if not success:
                # Rollback file copy if config update failed
                if dest_path.exists():
                    dest_path.unlink()
                raise ValueError(f"Failed to update configuration for {extension.name}")
    
    def _create_extension_config(self, extension, dest_path: Path) -> Dict[str, Any]:
        """Create configuration entry for an extension.
        
        Note: Only hooks and MCPs need configuration entries.
        Agents and commands are file-based and don't require settings.json entries.
        """
        config = {
            "name": extension.name,
            "path": str(dest_path.relative_to(dest_path.parent.parent))
        }
        
        # Add type-specific configuration
        if extension.extension_type == "hooks":
            config.update({
                "events": ["*"],  # Default to all events
                "matchers": ["*"]  # Default to all matchers
            })
        elif extension.extension_type == "mcps":
            config.update({
                "command": f"python {dest_path.name}",
                "args": []
            })
        # Agents and commands don't need configuration entries
        # They are discovered by Claude Code from their directories
        
        return config
    
    def _find_extension_to_remove(
        self, 
        name: str, 
        extension_type: Optional[str], 
        config: Dict[str, Any]
    ) -> Optional[Tuple[str, Dict[str, Any], int]]:
        """Find extension to remove in configuration.
        
        Args:
            name: Name of extension to find
            extension_type: Specific type to search in (optional)
            config: Configuration dictionary
            
        Returns:
            Tuple of (extension_type, extension_config, index) or None if not found
        """
        matching_extensions = []
        
        # Search in specified type or all types
        search_types = [extension_type] if extension_type else ["hooks", "mcps", "agents", "commands"]
        
        for ext_type in search_types:
            if ext_type in config:
                for idx, ext_config in enumerate(config[ext_type]):
                    if ext_config.get("name") == name:
                        matching_extensions.append((ext_type, ext_config, idx))
        
        if not matching_extensions:
            return None
        
        if len(matching_extensions) == 1:
            return matching_extensions[0]
        
        # Multiple extensions with same name - prompt user to choose
        return self._prompt_extension_selection(matching_extensions)
    
    def _prompt_extension_selection(
        self, 
        matching_extensions: List[Tuple[str, Dict[str, Any], int]]
    ) -> Optional[Tuple[str, Dict[str, Any], int]]:
        """Prompt user to select which extension to remove when multiple matches exist.
        
        Args:
            matching_extensions: List of matching (type, config, index) tuples
            
        Returns:
            Selected extension tuple or None if cancelled
        """
        print(f"\nFound {len(matching_extensions)} extensions with that name:")
        for i, (ext_type, ext_config, _) in enumerate(matching_extensions):
            path = ext_config.get('path', 'unknown')
            desc = ext_config.get('description', 'No description')
            print(f"  {i}. {ext_type}: {path} - {desc}")
        
        while True:
            try:
                choice = input("Select extension to remove (number, or 'cancel'): ").strip()
                if choice.lower() in ('cancel', 'c', 'n', 'no'):
                    return None
                
                idx = int(choice)
                if 0 <= idx < len(matching_extensions):
                    return matching_extensions[idx]
                else:
                    print(f"Invalid selection. Please choose 0-{len(matching_extensions)-1}")
            except (ValueError, KeyboardInterrupt):
                print("Invalid input. Please enter a number or 'cancel'")
                continue
    
    def _find_extension_dependencies(self, extension_name: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find extensions that depend on the given extension.
        
        Args:
            extension_name: Name of extension to check dependencies for
            config: Configuration dictionary
            
        Returns:
            List of extension configurations that depend on the extension
        """
        dependencies = []
        
        for ext_type in ["hooks", "mcps", "agents", "commands"]:
            if ext_type in config:
                for ext_config in config[ext_type]:
                    ext_deps = ext_config.get("dependencies", [])
                    if extension_name in ext_deps:
                        dependencies.append(ext_config)
        
        return dependencies
    
    def _get_extension_type_from_config(self, extension_config: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Get the type of an extension from the configuration.
        
        Args:
            extension_config: Extension configuration to find type for
            config: Full configuration dictionary
            
        Returns:
            Extension type string
        """
        for ext_type in ["hooks", "mcps", "agents", "commands"]:
            if ext_type in config:
                for ext in config[ext_type]:
                    if ext == extension_config:
                        return ext_type
        return "unknown"
    
    def _print_extension_details(self, extension_config: Dict[str, Any], extension_type: str) -> None:
        """Print detailed information about an extension.
        
        Args:
            extension_config: Extension configuration
            extension_type: Type of extension
        """
        print(f"\nExtension Details:")
        print(f"  Name: {extension_config.get('name', 'Unknown')}")
        print(f"  Type: {extension_type}")
        print(f"  Path: {extension_config.get('path', 'Unknown')}")
        
        if 'description' in extension_config:
            print(f"  Description: {extension_config['description']}")
        
        if 'installed_at' in extension_config:
            print(f"  Installed: {extension_config['installed_at']}")
        
        # Type-specific details
        if extension_type == "hooks" and 'events' in extension_config:
            print(f"  Events: {', '.join(extension_config['events'])}")
        elif extension_type == "mcps" and 'command' in extension_config:
            print(f"  Command: {extension_config['command']}")
        elif extension_type == "agents" and 'model' in extension_config:
            print(f"  Model: {extension_config['model']}")
        
        if 'dependencies' in extension_config:
            print(f"  Dependencies: {', '.join(extension_config['dependencies'])}")
        
        print()
    
    def _confirm_removal(self, extension_config: Dict[str, Any], extension_type: str) -> bool:
        """Prompt user to confirm extension removal.
        
        Args:
            extension_config: Extension configuration
            extension_type: Type of extension
            
        Returns:
            True if user confirms removal, False otherwise
        """
        name = extension_config.get('name', 'Unknown')
        path = extension_config.get('path', 'Unknown')
        
        print(f"\n⚠️  Confirm Removal")
        print(f"Extension: {name} ({extension_type})")
        print(f"File: {path}")
        
        if 'description' in extension_config:
            print(f"Description: {extension_config['description']}")
        
        while True:
            try:
                response = input("Remove this extension? [y/N]: ").strip().lower()
                if response in ('y', 'yes'):
                    return True
                elif response in ('n', 'no', ''):
                    return False
                else:
                    print("Please enter 'y' for yes or 'n' for no")
            except KeyboardInterrupt:
                print("\nOperation cancelled")
                return False
    
    def _remove_extension_atomic(
        self,
        extension_config: Dict[str, Any],
        extension_type: str,
        extension_index: int,
        config: Dict[str, Any],
        config_path: Path,
        base_dir: Path,
        verbose: bool = False
    ) -> bool:
        """Atomically remove extension with rollback on failure.
        
        Args:
            extension_config: Extension configuration to remove
            extension_type: Type of extension
            extension_index: Index of extension in config array
            config: Full configuration
            config_path: Path to configuration file
            base_dir: Base directory for extensions
            
        Returns:
            True if removal succeeded, False otherwise
        """
        import shutil
        
        # Create backup of configuration
        backup_config = None
        backup_path = None
        
        try:
            # Backup configuration
            config_manager = ClaudeConfigManager()
            backup_path = config_manager._create_backup(config_path)
            backup_config = config.copy()
            
            # Remove from configuration
            if extension_type in config and extension_index < len(config[extension_type]):
                config[extension_type].pop(extension_index)
            
            # Save updated configuration
            config_manager.save_config(config, config_path, create_backup=False)
            
            # Remove extension file if it exists
            extension_file_path = None
            if 'path' in extension_config:
                extension_file_path = base_dir / extension_config['path']
                if extension_file_path.exists():
                    extension_file_path.unlink()
                    if verbose:
                        self._print_info(f"Deleted file: {extension_file_path}")
            
            # Clean up empty directories
            if extension_file_path and extension_file_path.parent != base_dir:
                try:
                    extension_file_path.parent.rmdir()  # Only removes if empty
                    if verbose:
                        self._print_info(f"Removed empty directory: {extension_file_path.parent}")
                except OSError:
                    pass  # Directory not empty or other issue - that's OK
            
            return True
            
        except Exception as e:
            self._print_error(f"Removal failed, attempting rollback: {e}")
            
            # Attempt rollback
            try:
                if backup_config:
                    # Restore configuration
                    config_manager.save_config(backup_config, config_path, create_backup=False)
                    
                    # Restore file if we have backup and it was deleted
                    if extension_file_path and backup_path and backup_path.exists():
                        # This is simplified - in reality we'd need file-level backups
                        pass
                    
                    self._print_info("Configuration rolled back successfully")
                
            except Exception as rollback_error:
                self._print_error(f"Rollback failed: {rollback_error}")
            
            return False
            
        finally:
            # Clean up backup file
            if backup_path and backup_path.exists():
                try:
                    backup_path.unlink()
                except OSError:
                    pass
    
    def _remove_extension_config(
        self,
        extension_type: str,
        extension_name: str,
        user_level: bool = False
    ) -> bool:
        """Remove extension configuration from Claude settings.
        
        Args:
            extension_type: Type of extension ('hooks', 'mcps', 'agents', 'commands')  
            extension_name: Name of extension to remove
            user_level: Whether to remove from user-level or project-level config
            
        Returns:
            True if extension was removed successfully
        """
        config_manager = ClaudeConfigManager()
        config_path = config_manager.get_config_path(user_level)
        
        if not config_path.exists():
            return False
        
        config = config_manager.load_config(config_path)
        
        # Find and remove extension
        if extension_type in config:
            original_count = len(config[extension_type])
            config[extension_type] = [
                ext for ext in config[extension_type] 
                if ext.get("name") != extension_name
            ]
            
            if len(config[extension_type]) < original_count:
                # Extension was found and removed
                try:
                    config_manager.save_config(config, config_path)
                    return True
                except Exception as e:
                    self._print_error(f"Failed to save configuration: {e}")
                    return False
        
        return False

    def _format_extension_for_selection(self, ext) -> str:
        """Format extension for selection UI."""
        return f"{ext.name} ({ext.extension_type}) - {ext.description or 'No description'}"

    def _print_info(self, message: str) -> None:
        """Print info message."""
        if self._json_output:
            self._messages.append({"level": "info", "message": message})
        else:
            print(f"ℹ {message}")

    def _print_success(self, message: str) -> None:
        """Print success message."""
        if self._json_output:
            self._messages.append({"level": "success", "message": message})
        else:
            print(f"✓ {message}")

    def _print_error(self, message: str) -> None:
        """Print error message."""
        if self._json_output:
            self._messages.append({"level": "error", "message": message})
        else:
            print(f"✗ {message}", file=sys.stderr)

    def _print_warning(self, message: str) -> None:
        """Print warning message."""
        if self._json_output:
            self._messages.append({"level": "warning", "message": message})
        else:
            print(f"⚠ {message}", file=sys.stderr)
    
    def _output_json_result(self, result: CommandResult) -> None:
        """Output command result in JSON format."""
        import json
        result_dict = result.to_dict()
        
        # Add collected messages if any
        if self._messages:
            result_dict["messages"] = self._messages
            
        print(json.dumps(result_dict, indent=2, ensure_ascii=False))
    
    def _set_json_mode(self, enabled: bool) -> None:
        """Enable or disable JSON output mode."""
        self._json_output = enabled
        self._messages = []
    
    def _plugin_help(self, args) -> int:
        """Show plugin command help when no subcommand is specified."""
        print("pacc plugin: Manage Claude Code plugins\n")
        print("Available commands:")
        print("  install <repo_url>     Install plugins from Git repository")
        print("  list                   List installed plugins with status")
        print("  enable <plugin>        Enable a specific plugin")
        print("  disable <plugin>       Disable a specific plugin")
        print("  update [plugin]        Update plugins from Git repositories")
        print("  remove <plugin>        Remove/uninstall a plugin")
        print("  info <plugin>          Show detailed plugin information")
        print("  sync                   Synchronize plugins from pacc.json")
        print("  convert <extension>    Convert extension to plugin format")
        print("  push <plugin> <repo>   Push local plugin to Git repository")
        print("\nUse 'pacc plugin <command> --help' for more information on a command.")
        return 0
    
    def handle_plugin_install(self, args) -> int:
        """Handle plugin install command."""
        try:
            self._print_info(f"Installing plugins from repository: {args.repo_url}")
            
            if args.dry_run:
                self._print_info("DRY RUN MODE - No changes will be made")
            
            # Validate Git URL
            if not GitRepository.is_valid_git_url(args.repo_url):
                self._print_error(f"Invalid Git repository URL: {args.repo_url}")
                return 1
            
            # Initialize plugin managers
            plugins_dir = Path.home() / ".claude" / "plugins"
            repo_manager = RepositoryManager(plugins_dir)
            plugin_config = PluginConfigManager(plugins_dir=plugins_dir)
            discovery = PluginDiscovery()
            selector = PluginSelector()
            
            # Clone or update repository
            with self._progress_indicator("Cloning repository"):
                repo_path, repo_info = repo_manager.install_repository(
                    args.repo_url, 
                    update_if_exists=args.update
                )
            
            self._print_success(f"Repository cloned: {repo_info.owner}/{repo_info.repo}")
            
            # Discover plugins
            with self._progress_indicator("Discovering plugins"):
                repo_plugins = discovery.discover_plugins(repo_path)
            
            if not repo_plugins.plugins:
                self._print_warning("No plugins found in repository")
                return 0
            
            self._print_info(f"Found {len(repo_plugins.plugins)} plugin(s)")
            
            # Select plugins to install
            if args.all:
                selected_plugins = selector.select_all_plugins(repo_plugins)
            elif args.type:
                selected_plugins = selector.select_plugins_by_type(repo_plugins, args.type)
            elif args.interactive:
                selected_plugins = selector.select_plugins_interactive(repo_plugins)
            else:
                # Default: show plugins and ask for confirmation
                self._display_discovered_plugins(repo_plugins)
                if self._confirm_plugin_installation(repo_plugins):
                    selected_plugins = repo_plugins.plugins
                else:
                    self._print_info("Installation cancelled")
                    return 0
            
            if not selected_plugins:
                self._print_info("No plugins selected for installation")
                return 0
            
            # Install selected plugins
            success_count = 0
            repo_key = f"{repo_info.owner}/{repo_info.repo}"
            
            if not args.dry_run:
                # Add repository to config
                plugin_config.add_repository(
                    repo_info.owner, 
                    repo_info.repo,
                    metadata={
                        "url": args.repo_url,
                        "commit": repo_info.commit_hash,
                        "plugins": [p.name for p in selected_plugins]
                    }
                )
            
            for plugin in selected_plugins:
                try:
                    if args.dry_run:
                        self._print_info(f"Would install: {plugin.name} ({plugin.type})")
                    else:
                        # Plugin files are already in the repository directory
                        # Just need to enable them if requested
                        if args.enable:
                            plugin_config.enable_plugin(repo_key, plugin.name)
                            self._print_success(f"Installed and enabled: {plugin.name} ({plugin.type})")
                        else:
                            self._print_success(f"Installed: {plugin.name} ({plugin.type})")
                    
                    success_count += 1
                    
                except Exception as e:
                    self._print_error(f"Failed to install {plugin.name}: {e}")
                    
            # Summary
            if args.dry_run:
                self._print_info(f"Would install {success_count} plugin(s)")
            else:
                self._print_success(f"Successfully installed {success_count} plugin(s)")
                if args.enable:
                    self._print_info("Plugins have been enabled automatically")
                else:
                    self._print_info("Use 'pacc plugin enable <plugin>' to enable plugins")
            
            return 0
            
        except Exception as e:
            self._print_error(f"Plugin installation failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def handle_plugin_list(self, args) -> int:
        """Handle plugin list command."""
        try:
            # Initialize plugin managers
            plugins_dir = Path.home() / ".claude" / "plugins"
            plugin_config = PluginConfigManager(plugins_dir=plugins_dir)
            repo_manager = RepositoryManager(plugins_dir)
            discovery = PluginDiscovery()
            
            # Load plugin configuration
            config = plugin_config._load_plugin_config()
            settings = plugin_config._load_settings()
            enabled_plugins = settings.get("enabledPlugins", {})
            
            # Collect plugin information
            all_plugins = []
            
            for repo_key, repo_data in config.get("repositories", {}).items():
                # Skip if filtering by specific repo
                if args.repo and args.repo != repo_key:
                    continue
                
                owner, repo = repo_key.split("/", 1)
                repo_path = repo_manager.get_repository_path(owner, repo)
                
                if not repo_path or not repo_path.exists():
                    # Repository not found locally
                    for plugin_name in repo_data.get("plugins", []):
                        plugin_info = {
                            "name": plugin_name,
                            "repository": repo_key,
                            "type": "unknown",
                            "enabled": plugin_name in enabled_plugins.get(repo_key, []),
                            "status": "missing",
                            "description": "Repository not found locally"
                        }
                        all_plugins.append(plugin_info)
                    continue
                
                # Discover plugins in repository
                try:
                    repo_plugins = discovery.discover_plugins(repo_path)
                    
                    for plugin in repo_plugins.plugins:
                        # Skip if filtering by type
                        if args.type and plugin.type != args.type:
                            continue
                        
                        is_enabled = plugin.name in enabled_plugins.get(repo_key, [])
                        
                        # Skip if filtering by enabled/disabled status
                        if args.enabled_only and not is_enabled:
                            continue
                        if args.disabled_only and is_enabled:
                            continue
                        
                        plugin_info = {
                            "name": plugin.name,
                            "repository": repo_key,
                            "type": plugin.type,
                            "enabled": is_enabled,
                            "status": "installed",
                            "description": plugin.description or "No description",
                            "version": plugin.version,
                            "file_path": str(plugin.file_path)
                        }
                        all_plugins.append(plugin_info)
                        
                except Exception as e:
                    self._print_warning(f"Failed to scan repository {repo_key}: {e}")
            
            if not all_plugins:
                self._print_info("No plugins found")
                return 0
            
            # Display results
            if args.format == "json":
                import json
                result = {
                    "plugins": all_plugins,
                    "count": len(all_plugins)
                }
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif args.format == "list":
                for plugin in all_plugins:
                    status = "✓" if plugin["enabled"] else "✗"
                    print(f"{status} {plugin['repository']}/{plugin['name']} ({plugin['type']}) - {plugin['description']}")
            else:
                # Table format
                self._display_plugins_table(all_plugins)
            
            return 0
            
        except Exception as e:
            self._print_error(f"Failed to list plugins: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def handle_plugin_enable(self, args) -> int:
        """Handle plugin enable command."""
        try:
            # Parse plugin identifier
            repo_key, plugin_name = self._parse_plugin_identifier(args.plugin, args.repo)
            if not repo_key or not plugin_name:
                self._print_error("Please specify plugin in format 'repo/plugin' or use --repo option")
                return 1
            
            # Initialize plugin config
            plugins_dir = Path.home() / ".claude" / "plugins"
            plugin_config = PluginConfigManager(plugins_dir=plugins_dir)
            
            # Enable plugin
            if plugin_config.enable_plugin(repo_key, plugin_name):
                self._print_success(f"Enabled plugin: {repo_key}/{plugin_name}")
                return 0
            else:
                self._print_error(f"Failed to enable plugin: {repo_key}/{plugin_name}")
                return 1
                
        except Exception as e:
            self._print_error(f"Failed to enable plugin: {e}")
            return 1
    
    def handle_plugin_disable(self, args) -> int:
        """Handle plugin disable command."""
        try:
            # Parse plugin identifier
            repo_key, plugin_name = self._parse_plugin_identifier(args.plugin, args.repo)
            if not repo_key or not plugin_name:
                self._print_error("Please specify plugin in format 'repo/plugin' or use --repo option")
                return 1
            
            # Initialize plugin config
            plugins_dir = Path.home() / ".claude" / "plugins"
            plugin_config = PluginConfigManager(plugins_dir=plugins_dir)
            
            # Disable plugin
            if plugin_config.disable_plugin(repo_key, plugin_name):
                self._print_success(f"Disabled plugin: {repo_key}/{plugin_name}")
                return 0
            else:
                self._print_error(f"Failed to disable plugin: {repo_key}/{plugin_name}")
                return 1
                
        except Exception as e:
            self._print_error(f"Failed to disable plugin: {e}")
            return 1
    
    def handle_plugin_info(self, args) -> int:
        """Handle plugin info command."""
        try:
            # Parse plugin identifier
            repo_key, plugin_name = self._parse_plugin_identifier(args.plugin, args.repo)
            if not repo_key or not plugin_name:
                self._print_error("Please specify plugin in format 'repo/plugin' or use --repo option")
                return 1
            
            # Initialize managers
            plugins_dir = Path.home() / ".claude" / "plugins"
            plugin_config = PluginConfigManager(plugins_dir=plugins_dir)
            repo_manager = PluginRepositoryManager(plugins_dir=plugins_dir)
            discovery = PluginDiscovery()
            
            # Load configuration
            config = plugin_config._load_plugin_config()
            settings = plugin_config._load_settings()
            enabled_plugins = settings.get("enabledPlugins", {})
            
            # Check if repository exists in config
            repositories = config.get("repositories", {})
            if repo_key not in repositories:
                self._print_error(f"Repository '{repo_key}' not found. Use 'pacc plugin list' to see available plugins.")
                return 1
            
            repo_info = repositories[repo_key]
            
            # Check if plugin exists in repository
            repo_plugins = repo_info.get("plugins", [])
            if plugin_name not in repo_plugins:
                self._print_error(f"Plugin '{plugin_name}' not found in repository '{repo_key}'")
                self._print_info(f"Available plugins in {repo_key}: {', '.join(repo_plugins)}")
                return 1
            
            # Get repository path
            owner, repo = repo_key.split("/", 1)
            repo_path = plugins_dir / "repos" / owner / repo
            
            # Check installation status
            is_enabled = plugin_name in enabled_plugins.get(repo_key, [])
            is_installed = repo_path.exists()
            
            # Basic plugin info
            plugin_info = {
                "name": plugin_name,
                "repository": repo_key,
                "enabled": is_enabled,
                "installed": is_installed,
                "last_updated": repo_info.get("lastUpdated"),
                "commit_sha": repo_info.get("commitSha"),
                "repository_url": repo_info.get("url")
            }
            
            # If installed, get detailed information
            if is_installed:
                try:
                    # Discover plugin details in repository
                    repo_plugins = discovery.discover_plugins(repo_path)
                    
                    # Find the specific plugin
                    plugin_details = None
                    for plugin in repo_plugins.plugins:
                        if plugin.name == plugin_name:
                            plugin_details = plugin
                            break
                    
                    if plugin_details:
                        plugin_info.update({
                            "type": getattr(plugin_details, 'type', 'unknown'),
                            "description": plugin_details.manifest.get("description", "No description"),
                            "version": plugin_details.manifest.get("version", "unknown"),
                            "author": plugin_details.manifest.get("author", "unknown"),
                            "file_path": str(plugin_details.path),
                            "components": self._get_plugin_components_info(plugin_details),
                            "manifest": plugin_details.manifest
                        })
                    else:
                        plugin_info.update({
                            "type": "unknown",
                            "description": "Plugin metadata not available",
                            "version": "unknown",
                            "author": "unknown"
                        })
                        
                except Exception as e:
                    self._print_warning(f"Failed to scan plugin details: {e}")
                    plugin_info.update({
                        "type": "unknown",
                        "description": f"Error reading plugin: {e}",
                        "version": "unknown",
                        "author": "unknown"
                    })
            else:
                plugin_info.update({
                    "type": "unknown",
                    "description": "Repository not found locally",
                    "version": "unknown",
                    "author": "unknown",
                    "status": "missing"
                })
            
            # Display results
            if args.format == "json":
                import json
                print(json.dumps(plugin_info, indent=2, ensure_ascii=False, default=str))
            else:
                self._display_plugin_info_table(plugin_info)
            
            return 0
            
        except Exception as e:
            self._print_error(f"Failed to get plugin info: {e}")
            return 1
    
    def handle_plugin_remove(self, args) -> int:
        """Handle plugin remove command."""
        try:
            # Parse plugin identifier
            repo_key, plugin_name = self._parse_plugin_identifier(args.plugin, args.repo)
            if not repo_key or not plugin_name:
                self._print_error("Please specify plugin in format 'repo/plugin' or use --repo option")
                return 1
            
            # Initialize managers
            plugins_dir = Path.home() / ".claude" / "plugins"
            plugin_config = PluginConfigManager(plugins_dir=plugins_dir)
            repo_manager = PluginRepositoryManager(plugins_dir=plugins_dir)
            
            # Load configuration
            config = plugin_config._load_plugin_config()
            settings = plugin_config._load_settings()
            enabled_plugins = settings.get("enabledPlugins", {})
            
            # Check if repository exists in config
            repositories = config.get("repositories", {})
            if repo_key not in repositories:
                self._print_warning(f"Repository '{repo_key}' not found in configuration")
            
            # Check if plugin is enabled
            is_enabled = plugin_name in enabled_plugins.get(repo_key, [])
            
            # Get repository path
            owner, repo = repo_key.split("/", 1)
            repo_path = plugins_dir / "repos" / owner / repo
            repo_exists = repo_path.exists()
            
            # Dry run mode
            if args.dry_run:
                self._print_info("DRY RUN MODE - No changes will be made")
                if is_enabled:
                    self._print_info(f"Would disable plugin: {repo_key}/{plugin_name}")
                if repo_exists and not args.keep_files:
                    repo_plugins = repositories.get(repo_key, {}).get("plugins", [])
                    if len(repo_plugins) <= 1:
                        self._print_info(f"Would remove repository: {repo_path}")
                    else:
                        self._print_info(f"Would keep repository (has other plugins): {repo_path}")
                if repo_key in repositories:
                    self._print_info(f"Would remove from config: {repo_key}")
                return 0
            
            # Confirmation prompt
            if not args.force:
                self._print_info(f"Plugin: {repo_key}/{plugin_name}")
                self._print_info(f"Enabled: {'Yes' if is_enabled else 'No'}")
                self._print_info(f"Repository exists: {'Yes' if repo_exists else 'No'}")
                
                if not args.keep_files and repo_exists:
                    repo_plugins = repositories.get(repo_key, {}).get("plugins", [])
                    if len(repo_plugins) <= 1:
                        self._print_warning(f"This will delete the entire repository: {repo_path}")
                    else:
                        self._print_info(f"Repository will be kept (has {len(repo_plugins)} plugins)")
                
                confirm = input("Continue with removal? [y/N]: ").lower().strip()
                if confirm not in ('y', 'yes'):
                    self._print_info("Removal cancelled")
                    return 0
            
            # Atomic removal using transaction
            try:
                with plugin_config.transaction():
                    removal_success = True
                    
                    # Step 1: Disable plugin if enabled
                    if is_enabled:
                        if plugin_config.disable_plugin(repo_key, plugin_name):
                            self._print_success(f"Disabled plugin: {repo_key}/{plugin_name}")
                        else:
                            self._print_error(f"Failed to disable plugin: {repo_key}/{plugin_name}")
                            removal_success = False
                    
                    # Step 2: Remove repository files if requested and safe
                    if not args.keep_files and repo_exists and removal_success:
                        repo_plugins = repositories.get(repo_key, {}).get("plugins", [])
                        
                        # Only remove repository if this is the only plugin or if forced
                        if len(repo_plugins) <= 1:
                            try:
                                import shutil
                                shutil.rmtree(repo_path)
                                self._print_success(f"Removed repository: {repo_path}")
                            except OSError as e:
                                self._print_error(f"Failed to remove repository files: {e}")
                                removal_success = False
                        else:
                            self._print_info(f"Repository kept (contains {len(repo_plugins)} plugins)")
                    
                    # Step 3: Remove from config if repository is empty or doesn't exist
                    if removal_success and repo_key in repositories:
                        repo_plugins = repositories.get(repo_key, {}).get("plugins", [])
                        if len(repo_plugins) <= 1 or not repo_exists:
                            if plugin_config.remove_repository(owner, repo):
                                self._print_success(f"Removed repository from config: {repo_key}")
                            else:
                                self._print_error(f"Failed to remove repository from config: {repo_key}")
                                removal_success = False
                    
                    if not removal_success:
                        raise Exception("Plugin removal failed, rolling back changes")
                
                self._print_success(f"Successfully removed plugin: {repo_key}/{plugin_name}")
                return 0
                
            except Exception as e:
                self._print_error(f"Failed to remove plugin (changes rolled back): {e}")
                return 1
            
        except Exception as e:
            self._print_error(f"Failed to remove plugin: {e}")
            return 1
    
    def handle_plugin_update(self, args) -> int:
        """Handle plugin update command."""
        try:
            plugins_dir = Path.home() / ".claude" / "plugins"
            repo_manager = PluginRepositoryManager(plugins_dir=plugins_dir)
            plugin_config = PluginConfigManager(plugins_dir=plugins_dir)
            
            # If specific plugin specified, update only that one
            if args.plugin:
                return self._update_single_plugin(args, repo_manager, plugin_config)
            else:
                return self._update_all_plugins(args, repo_manager, plugin_config)
                
        except Exception as e:
            self._print_error(f"Failed to update plugins: {e}")
            return 1
    
    def _update_single_plugin(self, args, repo_manager: PluginRepositoryManager, plugin_config: PluginConfigManager) -> int:
        """Update a single plugin repository."""
        plugin_spec = args.plugin
        
        # Parse plugin specification - could be owner/repo or repo/plugin format
        if "/" in plugin_spec:
            parts = plugin_spec.split("/")
            if len(parts) == 2:
                # Assume owner/repo format for now
                owner, repo = parts
                repo_key = f"{owner}/{repo}"
            else:
                self._print_error(f"Invalid plugin specification: {plugin_spec}")
                return 1
        else:
            self._print_error("Plugin specification must be in 'owner/repo' format")
            return 1
        
        # Check if repository exists in config
        config_data = plugin_config._load_plugin_config()
        repositories = config_data.get("repositories", {})
        
        if repo_key not in repositories:
            self._print_error(f"Repository not found: {repo_key}")
            self._print_info("Use 'pacc plugin list' to see installed repositories")
            return 1
        
        # Get repository path
        plugins_dir = Path.home() / ".claude" / "plugins"
        repo_path = plugins_dir / "repos" / owner / repo
        if not repo_path.exists():
            self._print_error(f"Repository directory not found: {repo_path}")
            return 1
        
        return self._perform_plugin_update(repo_key, repo_path, args, repo_manager, plugin_config)
    
    def _update_all_plugins(self, args, repo_manager: PluginRepositoryManager, plugin_config: PluginConfigManager) -> int:
        """Update all installed plugin repositories."""
        config_data = plugin_config._load_plugin_config()
        repositories = config_data.get("repositories", {})
        
        if not repositories:
            self._print_info("No plugin repositories found to update")
            return 0
        
        self._print_info(f"Updating {len(repositories)} plugin repositories...")
        
        total_updated = 0
        total_errors = 0
        
        for repo_key in repositories:
            try:
                # Parse owner/repo from key
                owner, repo = repo_key.split("/", 1)
                repo_path = repo_manager.repos_dir / owner / repo
                
                if not repo_path.exists():
                    self._print_warning(f"Repository directory not found: {repo_path}")
                    total_errors += 1
                    continue
                
                result = self._perform_plugin_update(repo_key, repo_path, args, repo_manager, plugin_config)
                if result == 0:
                    total_updated += 1
                else:
                    total_errors += 1
                    
            except Exception as e:
                self._print_error(f"Failed to update {repo_key}: {e}")
                total_errors += 1
        
        # Summary
        self._print_info(f"\nUpdate complete: {total_updated} updated, {total_errors} errors")
        return 0 if total_errors == 0 else 1
    
    def _perform_plugin_update(self, repo_key: str, repo_path: Path, args, repo_manager: PluginRepositoryManager, plugin_config: PluginConfigManager) -> int:
        """Perform the actual update for a repository."""
        self._print_info(f"Updating {repo_key}...")
        
        try:
            # Get current status before update
            old_sha = None
            try:
                old_sha = repo_manager._get_current_commit_sha(repo_path)
            except Exception as e:
                self._print_warning(f"Could not get current commit SHA: {e}")
            
            # Check for uncommitted changes if not forcing
            if not args.force and not repo_manager._is_working_tree_clean(repo_path):
                self._print_error(f"Repository {repo_key} has uncommitted changes. Use --force to override or commit your changes.")
                return 1
            
            # Dry run - show what would be updated
            if args.dry_run:
                return self._show_update_preview(repo_key, repo_path, repo_manager, old_sha)
            
            # Perform actual update
            update_result = repo_manager.update_plugin(repo_path)
            
            if not update_result.success:
                self._print_error(f"Update failed for {repo_key}: {update_result.error_message}")
                
                # Attempt automatic rollback if we have old SHA
                if old_sha and args.force:
                    self._print_info(f"Attempting rollback to {old_sha[:8]}...")
                    if repo_manager.rollback_plugin(repo_path, old_sha):
                        self._print_success(f"Rolled back {repo_key} to previous state")
                    else:
                        self._print_error(f"Rollback failed for {repo_key}")
                
                return 1
            
            # Update successful
            if update_result.had_changes:
                self._print_success(f"Updated {repo_key}: {update_result.old_sha[:8]} → {update_result.new_sha[:8]}")
                
                # Show diff if requested
                if args.show_diff and update_result.old_sha and update_result.new_sha:
                    self._show_commit_diff(repo_path, update_result.old_sha, update_result.new_sha)
                
                # Update config with new commit SHA
                try:
                    metadata = plugin_config._load_plugin_config().get("repositories", {}).get(repo_key, {})
                    metadata["commitSha"] = update_result.new_sha
                    metadata["lastUpdated"] = datetime.now().isoformat()
                    plugin_config.add_repository(*repo_key.split("/", 1), metadata)
                except Exception as e:
                    self._print_warning(f"Failed to update config metadata: {e}")
                    
            else:
                self._print_info(f"{repo_key} is already up to date")
            
            return 0
            
        except Exception as e:
            self._print_error(f"Unexpected error updating {repo_key}: {e}")
            return 1
    
    def _show_update_preview(self, repo_key: str, repo_path: Path, repo_manager: PluginRepositoryManager, old_sha: Optional[str]) -> int:
        """Show preview of what would be updated."""
        try:
            # Fetch remote changes without merging
            import subprocess
            result = subprocess.run(
                ["git", "fetch", "--dry-run"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                self._print_error(f"Failed to fetch remote for {repo_key}: {result.stderr}")
                return 1
            
            # Get remote HEAD SHA
            result = subprocess.run(
                ["git", "rev-parse", "origin/HEAD"],
                cwd=repo_path,
                capture_output=True, 
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                # Try origin/main or origin/master
                for branch in ["origin/main", "origin/master"]:
                    result = subprocess.run(
                        ["git", "rev-parse", branch],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0:
                        break
                else:
                    self._print_error(f"Could not determine remote HEAD for {repo_key}")
                    return 1
            
            remote_sha = result.stdout.strip()
            
            if old_sha == remote_sha:
                self._print_info(f"{repo_key} is already up to date")
                return 0
            
            # Show commits behind
            if old_sha:
                result = subprocess.run(
                    ["git", "rev-list", "--count", f"{old_sha}..{remote_sha}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    commits_behind = result.stdout.strip()
                    self._print_info(f"{repo_key} is {commits_behind} commits behind remote")
                
                # Show commit log
                result = subprocess.run(
                    ["git", "log", "--oneline", f"{old_sha}..{remote_sha}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    self._print_info(f"Recent changes in {repo_key}:")
                    for line in result.stdout.strip().split('\n'):
                        self._print_info(f"  • {line}")
            else:
                self._print_info(f"{repo_key} would be updated to {remote_sha[:8]}")
            
            return 0
            
        except Exception as e:
            self._print_error(f"Failed to show preview for {repo_key}: {e}")
            return 1
    
    def _show_commit_diff(self, repo_path: Path, old_sha: str, new_sha: str) -> None:
        """Show diff between two commits."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "diff", "--stat", f"{old_sha}..{new_sha}"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                self._print_info("Changes:")
                for line in result.stdout.strip().split('\n'):
                    self._print_info(f"  {line}")
            else:
                self._print_info("No file changes detected")
                
        except Exception as e:
            self._print_warning(f"Could not show diff: {e}")

    def handle_plugin_sync(self, args) -> int:
        """Handle plugin sync command for team collaboration."""
        try:
            from .core.project_config import PluginSyncManager
            
            # Initialize sync manager
            sync_manager = PluginSyncManager()
            
            # Check if pacc.json exists
            project_dir = args.project_dir
            config_path = project_dir / "pacc.json"
            
            if not config_path.exists():
                self._print_error(f"No pacc.json found in {project_dir}")
                self._print_info("Initialize a project configuration with 'pacc init' or create pacc.json manually")
                return 1
            
            # Set output mode
            self._set_json_mode(getattr(args, 'json', False))
            
            # Show what we're syncing
            if args.dry_run:
                self._print_info(f"🔍 Dry-run: Checking plugin synchronization for {project_dir}")
            else:
                self._print_info(f"🔄 Synchronizing plugins from {config_path}")
            
            if args.environment != "default":
                self._print_info(f"Environment: {args.environment}")
            
            # Perform sync
            result = sync_manager.sync_plugins(
                project_dir=project_dir,
                environment=args.environment,
                dry_run=args.dry_run
            )
            
            # Process filtering options
            if args.required_only or args.optional_only:
                # This would need additional logic in sync_manager
                # For now, just warn the user
                if args.required_only:
                    self._print_warning("--required-only filtering not yet implemented")
                if args.optional_only:
                    self._print_warning("--optional-only filtering not yet implemented")
            
            # Display results
            if result.success:
                self._print_success("✅ Plugin synchronization completed successfully")
                
                if result.installed_count > 0:
                    self._print_info(f"📦 Installed: {result.installed_count} plugins")
                
                if result.updated_count > 0:
                    self._print_info(f"🔄 Updated: {result.updated_count} plugins")
                
                if result.skipped_count > 0:
                    self._print_info(f"⏭️  Skipped: {result.skipped_count} plugins (already up to date)")
                
                if not result.installed_count and not result.updated_count:
                    self._print_info("💡 All plugins are already synchronized")
            
            else:
                self._print_error("❌ Plugin synchronization failed")
                if result.error_message:
                    self._print_error(f"Error: {result.error_message}")
            
            # Show warnings
            for warning in result.warnings:
                self._print_warning(warning)
            
            # Show failed plugins
            if result.failed_plugins:
                self._print_error(f"Failed to sync {len(result.failed_plugins)} plugins:")
                for plugin in result.failed_plugins:
                    self._print_error(f"  • {plugin}")
            
            # JSON output
            if self._json_output:
                command_result = CommandResult(
                    success=result.success,
                    message="Plugin sync completed" if result.success else "Plugin sync failed",
                    data={
                        "installed_count": result.installed_count,
                        "updated_count": result.updated_count,
                        "skipped_count": result.skipped_count,
                        "failed_plugins": result.failed_plugins,
                        "environment": args.environment,
                        "dry_run": args.dry_run
                    },
                    warnings=result.warnings if result.warnings else None
                )
                print(json.dumps(command_result.to_dict(), indent=2))
            
            return 0 if result.success else 1
            
        except Exception as e:
            self._print_error(f"Sync failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def handle_plugin_convert(self, args) -> int:
        """Handle plugin convert command."""
        try:
            source_path = Path(args.extension)
            
            # Validate source path
            if not source_path.exists():
                self._print_error(f"Extension path does not exist: {source_path}")
                return 1
            
            # Initialize converter
            output_dir = args.output or Path.cwd() / "converted_plugins"
            converter = ExtensionToPluginConverter(output_dir=output_dir)
            
            # Interactive prompts for missing metadata
            plugin_name = args.name
            if not plugin_name:
                plugin_name = input(f"Enter plugin name (leave empty for auto-generation): ").strip()
                if not plugin_name:
                    plugin_name = None  # Let converter auto-generate
            
            author = args.author
            if not author:
                author = input("Enter plugin author (optional): ").strip() or ""
            
            # Create metadata
            metadata = PluginMetadata(
                name=plugin_name or "temp",  # Will be updated by converter if auto-generated
                version=args.version,
                author=author
            )
            
            self._print_info(f"Converting extension: {source_path}")
            
            if args.batch:
                # Batch conversion
                self._print_info("Running batch conversion...")
                metadata_defaults = {
                    "version": args.version,
                    "author": author
                }
                
                results = converter.convert_directory(
                    source_path,
                    metadata_defaults=metadata_defaults,
                    overwrite=args.overwrite
                )
                
                # Display results
                success_count = sum(1 for r in results if r.success)
                self._print_info(f"Batch conversion completed: {success_count}/{len(results)} successful")
                
                for result in results:
                    if result.success:
                        self._print_success(f"✓ {result.plugin_name} -> {result.plugin_path}")
                    else:
                        self._print_error(f"✗ {result.plugin_name}: {result.error_message}")
                
                # Handle direct push to repo if specified
                if args.repo and success_count > 0:
                    self._print_info(f"Pushing successful conversions to {args.repo}")
                    pusher = PluginPusher()
                    
                    push_success = 0
                    for result in results:
                        if result.success and result.plugin_path:
                            if pusher.push_plugin(result.plugin_path, args.repo):
                                push_success += 1
                                self._print_success(f"Pushed {result.plugin_name} to repository")
                            else:
                                self._print_error(f"Failed to push {result.plugin_name}")
                    
                    self._print_info(f"Successfully pushed {push_success}/{success_count} plugins")
                
                return 0 if success_count > 0 else 1
                
            else:
                # Single conversion
                result = converter.convert_extension(
                    source_path,
                    plugin_name,
                    metadata,
                    args.overwrite
                )
                
                if result.success:
                    self._print_success(f"Successfully converted to plugin: {result.plugin_name}")
                    self._print_info(f"Plugin location: {result.plugin_path}")
                    self._print_info(f"Components: {', '.join(result.components)}")
                    
                    # Handle direct push to repo if specified
                    if args.repo:
                        self._print_info(f"Pushing plugin to {args.repo}")
                        pusher = PluginPusher()
                        
                        if pusher.push_plugin(result.plugin_path, args.repo):
                            self._print_success(f"Successfully pushed to repository: {args.repo}")
                        else:
                            self._print_error("Failed to push to repository")
                            return 1
                    
                    return 0
                else:
                    self._print_error(f"Conversion failed: {result.error_message}")
                    return 1
                    
        except KeyboardInterrupt:
            self._print_info("Conversion cancelled by user")
            return 1
        except Exception as e:
            self._print_error(f"Conversion failed: {e}")
            return 1
    
    def handle_plugin_push(self, args) -> int:
        """Handle plugin push command."""
        try:
            plugin_path = Path(args.plugin)
            
            # Validate plugin path
            if not plugin_path.exists():
                self._print_error(f"Plugin path does not exist: {plugin_path}")
                return 1
            
            if not plugin_path.is_dir():
                self._print_error(f"Plugin path must be a directory: {plugin_path}")
                return 1
            
            # Validate plugin structure
            manifest_path = plugin_path / "plugin.json"
            if not manifest_path.exists():
                self._print_error(f"No plugin.json found in {plugin_path}")
                self._print_info("This doesn't appear to be a valid plugin directory")
                return 1
            
            # Preview what will be pushed
            self._print_info(f"Preparing to push plugin: {plugin_path.name}")
            self._print_info(f"Target repository: {args.repo}")
            self._print_info(f"Authentication method: {args.auth}")
            
            # Confirm push
            if not self._confirm_action(f"Push plugin {plugin_path.name} to {args.repo}?"):
                self._print_info("Push cancelled")
                return 0
            
            # Initialize pusher and push
            pusher = PluginPusher()
            
            with self._progress_indicator("Pushing plugin to repository"):
                success = pusher.push_plugin(
                    plugin_path,
                    args.repo,
                    private=args.private,
                    auth_method=args.auth
                )
            
            if success:
                self._print_success(f"Successfully pushed {plugin_path.name} to {args.repo}")
                self._print_info(f"Repository URL: {args.repo}")
                return 0
            else:
                self._print_error("Failed to push plugin to repository")
                self._print_info("Check your Git credentials and repository permissions")
                return 1
                
        except KeyboardInterrupt:
            self._print_info("Push cancelled by user")
            return 1
        except Exception as e:
            self._print_error(f"Push failed: {e}")
            return 1
    
    def handle_plugin_search(self, args) -> int:
        """Handle plugin search command."""
        try:
            # Handle recommendations mode
            if args.recommendations:
                return self._handle_search_recommendations(args)
            
            # Set up search parameters
            query = args.query or ""
            plugin_type = args.type
            sort_by = args.sort
            
            # Handle conflicting flags
            if args.installed_only and args.exclude_installed:
                self._print_error("Cannot use --installed-only and --exclude-installed together")
                return 1
            
            include_installed = not args.exclude_installed
            installed_only = args.installed_only
            
            self._print_info(f"Searching plugins{f' for \"{query}\"' if query else ''}...")
            
            # Perform search
            results = search_plugins(
                query=query,
                plugin_type=plugin_type,
                sort_by=sort_by,
                include_installed=include_installed,
                installed_only=installed_only
            )
            
            # Apply limit
            if args.limit > 0:
                results = results[:args.limit]
            
            # Display results
            if not results:
                if installed_only:
                    self._print_info("No installed plugins found matching your criteria.")
                    self._print_info("Use 'pacc plugin install <repo>' to install plugins.")
                else:
                    self._print_info("No plugins found matching your criteria.")
                    if query:
                        self._print_info("Try a different search term or use --type to filter by plugin type.")
                return 0
            
            self._display_search_results(results, query)
            
            # Show helpful info
            installed_count = sum(1 for r in results if r.get("installed", False))
            total_count = len(results)
            
            if installed_count > 0:
                self._print_info(f"\nShowing {total_count} plugins ({installed_count} installed)")
            else:
                self._print_info(f"\nShowing {total_count} plugins")
            
            if not installed_only and total_count > 0:
                self._print_info("Use 'pacc plugin install <repo>' to install a plugin")
                self._print_info("Use 'pacc plugin search --installed-only' to see only installed plugins")
            
            return 0
            
        except KeyboardInterrupt:
            self._print_info("Search cancelled by user")
            return 1
        except Exception as e:
            self._print_error(f"Search failed: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    def handle_plugin_create(self, args) -> int:
        """Handle plugin create command."""
        try:
            from .plugins.creator import (
                PluginCreator,
                CreationPluginType,
                CreationMode
            )
            
            # Determine output directory
            output_dir = Path(args.output_dir).resolve()
            if not output_dir.exists():
                self._print_error(f"Output directory does not exist: {output_dir}")
                return 1
            
            # Map CLI arguments to creator parameters
            plugin_type = None
            if args.type:
                type_map = {
                    'hooks': CreationPluginType.HOOKS,
                    'agents': CreationPluginType.AGENTS,
                    'commands': CreationPluginType.COMMANDS,
                    'mcp': CreationPluginType.MCP
                }
                plugin_type = type_map[args.type]
            
            creation_mode = CreationMode.GUIDED if args.mode == 'guided' else CreationMode.QUICK
            
            # Determine Git initialization preference
            init_git = None
            if args.init_git:
                init_git = True
            elif args.no_git:
                init_git = False
            # If neither flag is set, let the creator decide based on mode
            
            # Create the plugin
            creator = PluginCreator()
            self._print_info("🚀 Starting plugin creation wizard...")
            
            if creation_mode == CreationMode.GUIDED:
                self._print_info("📋 Guided mode: comprehensive plugin setup")
            else:
                self._print_info("⚡ Quick mode: minimal configuration")
            
            result = creator.create_plugin(
                name=args.name,
                plugin_type=plugin_type,
                output_dir=output_dir,
                mode=creation_mode,
                init_git=init_git
            )
            
            if result.success:
                self._print_success(f"✅ Plugin created successfully!")
                self._print_info(f"📁 Location: {result.plugin_path}")
                
                if result.created_files:
                    self._print_info("📝 Created files:")
                    for file_name in result.created_files:
                        self._print_info(f"   • {file_name}")
                
                if result.git_initialized:
                    self._print_info("🔧 Git repository initialized")
                
                if result.warnings:
                    self._print_info("⚠️  Warnings:")
                    for warning in result.warnings:
                        self._print_warning(f"   • {warning}")
                
                self._print_info("")
                self._print_info("🎯 Next steps:")
                self._print_info("   1. Edit the plugin files to implement your functionality")
                self._print_info("   2. Test your plugin locally")
                if result.git_initialized:
                    self._print_info("   3. Commit your changes: git add . && git commit -m 'Initial plugin structure'")
                    self._print_info("   4. Push to a Git repository for sharing")
                else:
                    self._print_info("   3. Initialize Git if you want to share: git init")
                
                return 0
            else:
                self._print_error(f"❌ Plugin creation failed: {result.error_message}")
                return 1
                
        except KeyboardInterrupt:
            self._print_info("Plugin creation cancelled by user")
            return 1
        except Exception as e:
            self._print_error(f"Plugin creation failed: {e}")
            if hasattr(args, 'verbose') and args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    
    def _handle_search_recommendations(self, args) -> int:
        """Handle search recommendations mode."""
        try:
            self._print_info("Getting plugin recommendations for your project...")
            
            results = get_plugin_recommendations(limit=args.limit)
            
            if not results:
                self._print_info("No recommendations found for your project.")
                self._print_info("This might be because:")
                self._print_info("  • Your project type is not recognized")
                self._print_info("  • No matching plugins are available")
                self._print_info("Use 'pacc plugin search' to browse all available plugins.")
                return 0
            
            print()
            print("🎯 Recommended plugins for your project:")
            print()
            
            self._display_search_results(results, "", show_relevance=True)
            
            self._print_info(f"\nShowing {len(results)} recommendations")
            self._print_info("Use 'pacc plugin install <repo>' to install a recommended plugin")
            
            return 0
            
        except Exception as e:
            self._print_error(f"Failed to get recommendations: {e}")
            return 1
    
    def _display_search_results(self, results: List[Dict[str, Any]], query: str = "", show_relevance: bool = False) -> None:
        """Display search results in a formatted table."""
        if not results:
            return
        
        # Prepare table data
        headers = ["Name", "Type", "Description", "Author", "Status"]
        if show_relevance:
            headers.append("Match")
        
        rows = []
        for result in results:
            name = result.get("name", "")
            namespace = result.get("namespace")
            if namespace:
                name = f"{namespace}:{name}"
            
            plugin_type = result.get("plugin_type", "").upper()
            description = result.get("description", "")
            author = result.get("author", "")
            
            # Status indicator
            status_parts = []
            if result.get("installed", False):
                if result.get("enabled", False):
                    status_parts.append("✅ Enabled")
                else:
                    status_parts.append("📦 Installed")
            else:
                status_parts.append("🌐 Available")
            
            status = " ".join(status_parts)
            
            # Truncate long descriptions
            if len(description) > 60:
                description = description[:57] + "..."
            
            row = [name, plugin_type, description, author, status]
            
            if show_relevance:
                popularity = result.get("popularity_score", 0)
                row.append(f"{popularity}")
            
            rows.append(row)
        
        # Print table
        self._print_table(headers, rows)
        
        # Add search tips if query was provided
        if query and not show_relevance:
            print()
            self._print_info(f"💡 Tips:")
            self._print_info(f"  • Use --type to filter by plugin type (command, agent, hook, mcp)")
            self._print_info(f"  • Use --sort to change sort order (popularity, date, name)")
            self._print_info(f"  • Use --recommendations to get suggestions for your project")
    
    def _print_table(self, headers: List[str], rows: List[List[str]]) -> None:
        """Print a formatted table."""
        if not rows:
            return
        
        # Calculate column widths
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Print header
        header_row = " | ".join(header.ljust(col_widths[i]) for i, header in enumerate(headers))
        print(header_row)
        print("-" * len(header_row))
        
        # Print rows
        for row in rows:
            row_str = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
            print(row_str)
    
    def _plugin_env_help(self, args) -> int:
        """Show plugin environment help."""
        self._print_info("Available environment commands:")
        self._print_info("  setup  - Configure environment for Claude Code plugins")
        self._print_info("  status - Show current environment configuration")
        self._print_info("  verify - Verify environment is properly configured")
        self._print_info("  reset  - Remove PACC environment modifications")
        self._print_info("")
        self._print_info("Use 'pacc plugin env <command> --help' for more information")
        return 0
    
    def handle_plugin_env_setup(self, args) -> int:
        """Handle plugin environment setup command."""
        try:
            env_manager = get_environment_manager()
            
            self._print_info("Setting up environment for Claude Code plugins...")
            self._print_info(f"Platform: {env_manager.platform.value}")
            self._print_info(f"Shell: {env_manager.shell.value}")
            
            # Setup environment
            success, message, warnings = env_manager.setup_environment(force=args.force)
            
            if success:
                self._print_success(message)
                if warnings:
                    for warning in warnings:
                        self._print_warning(warning)
                return 0
            else:
                self._print_error(message)
                if warnings:
                    for warning in warnings:
                        self._print_warning(warning)
                return 1
                
        except Exception as e:
            self._print_error(f"Environment setup failed: {e}")
            return 1
    
    def handle_plugin_env_status(self, args) -> int:
        """Handle plugin environment status command."""
        try:
            env_manager = get_environment_manager()
            status = env_manager.get_environment_status()
            
            self._print_info("Environment Status:")
            self._print_info(f"  Platform: {status.platform.value}")
            self._print_info(f"  Shell: {status.shell.value}")
            self._print_info(f"  ENABLE_PLUGINS set: {status.enable_plugins_set}")
            
            if status.enable_plugins_set:
                self._print_info(f"  ENABLE_PLUGINS value: {status.enable_plugins_value}")
            
            if status.config_file:
                self._print_info(f"  Configuration file: {status.config_file}")
                self._print_info(f"  File writable: {status.writable}")
                if status.backup_exists:
                    self._print_info(f"  Backup exists: Yes")
            
            if status.containerized:
                self._print_info(f"  Containerized: Yes")
            
            if status.conflicts:
                self._print_warning("Conflicts detected:")
                for conflict in status.conflicts:
                    self._print_warning(f"  - {conflict}")
            
            # Overall status
            if status.enable_plugins_set and status.enable_plugins_value == env_manager.ENABLE_PLUGINS_VALUE:
                self._print_success("Environment is configured for Claude Code plugins")
            else:
                self._print_warning("Environment may need configuration")
                self._print_info("Run 'pacc plugin env setup' to configure automatically")
            
            return 0
            
        except Exception as e:
            self._print_error(f"Failed to get environment status: {e}")
            return 1
    
    def handle_plugin_env_verify(self, args) -> int:
        """Handle plugin environment verify command."""
        try:
            env_manager = get_environment_manager()
            
            self._print_info("Verifying environment configuration...")
            
            success, message, details = env_manager.verify_environment()
            
            if success:
                self._print_success(message)
                self._print_info("Environment verification details:")
                for key, value in details.items():
                    if value is not None:
                        self._print_info(f"  {key}: {value}")
                return 0
            else:
                self._print_error(message)
                self._print_info("Environment verification details:")
                for key, value in details.items():
                    if value is not None:
                        self._print_info(f"  {key}: {value}")
                self._print_info("")
                self._print_info("Run 'pacc plugin env setup' to configure the environment")
                return 1
                
        except Exception as e:
            self._print_error(f"Environment verification failed: {e}")
            return 1
    
    def handle_plugin_env_reset(self, args) -> int:
        """Handle plugin environment reset command."""
        try:
            env_manager = get_environment_manager()
            
            # Confirm reset unless --confirm flag is used
            if not args.confirm:
                if not self._confirm_action("Reset environment configuration (remove PACC modifications)?"):
                    self._print_info("Reset cancelled")
                    return 0
            
            self._print_info("Resetting environment configuration...")
            
            success, message, warnings = env_manager.reset_environment()
            
            if success:
                self._print_success(message)
                if warnings:
                    for warning in warnings:
                        self._print_warning(warning)
                return 0
            else:
                self._print_error(message)
                if warnings:
                    for warning in warnings:
                        self._print_warning(warning)
                return 1
                
        except Exception as e:
            self._print_error(f"Environment reset failed: {e}")
            return 1
    
    def _parse_plugin_identifier(self, plugin_arg: str, repo_arg: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """Parse plugin identifier from arguments.
        
        Args:
            plugin_arg: Plugin argument (could be 'plugin' or 'repo/plugin')
            repo_arg: Optional repository argument
            
        Returns:
            Tuple of (repo_key, plugin_name) or (None, None) if invalid
        """
        if "/" in plugin_arg:
            # Format: repo/plugin
            parts = plugin_arg.split("/", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
        elif repo_arg:
            # Separate repo and plugin args
            return repo_arg, plugin_arg
        
        return None, None
    
    def _display_discovered_plugins(self, repo_plugins) -> None:
        """Display discovered plugins for user review."""
        print(f"\nFound {len(repo_plugins.plugins)} plugin(s) in {repo_plugins.repository}:")
        
        # Group by type
        by_type = {}
        for plugin in repo_plugins.plugins:
            if plugin.type not in by_type:
                by_type[plugin.type] = []
            by_type[plugin.type].append(plugin)
        
        for plugin_type, plugins in by_type.items():
            print(f"\n{plugin_type.upper()}:")
            for plugin in plugins:
                desc = plugin.description or "No description"
                print(f"  • {plugin.name} - {desc}")
    
    def _confirm_plugin_installation(self, repo_plugins) -> bool:
        """Confirm plugin installation with user."""
        try:
            response = input(f"\nInstall all {len(repo_plugins.plugins)} plugin(s)? [Y/n]: ").strip().lower()
            return response in ('', 'y', 'yes')
        except KeyboardInterrupt:
            return False
    
    def _display_plugins_table(self, plugins: List[Dict[str, Any]]) -> None:
        """Display plugins in table format."""
        if not plugins:
            return
        
        # Calculate column widths
        headers = ["Status", "Repository", "Plugin", "Type", "Description"]
        col_widths = [len(h) for h in headers]
        
        rows = []
        for plugin in plugins:
            status = "✓ Enabled" if plugin["enabled"] else "✗ Disabled"
            row = [
                status,
                plugin["repository"],
                plugin["name"],
                plugin["type"],
                plugin["description"][:50] + "..." if len(plugin["description"]) > 50 else plugin["description"]
            ]
            rows.append(row)
            
            # Update column widths
            for i, val in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(val)))
        
        # Print header
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        print(header_line)
        print("-" * len(header_line))
        
        # Print rows
        for row in rows:
            print(" | ".join(str(val).ljust(w) for val, w in zip(row, col_widths)))
    
    def _progress_indicator(self, message: str):
        """Simple progress indicator context manager."""
        from contextlib import contextmanager
        
        @contextmanager
        def indicator():
            print(f"{message}...", end="", flush=True)
            try:
                yield
                print(" ✓")
            except Exception:
                print(" ✗")
                raise
        
        return indicator()
    
    def _get_plugin_components_info(self, plugin_details) -> dict:
        """Get information about plugin components.
        
        Args:
            plugin_details: PluginInfo object from discovery
            
        Returns:
            Dict with component counts and details
        """
        components_info = {
            "commands": [],
            "agents": [],
            "hooks": [],
            "total_count": 0
        }
        
        try:
            # Get namespaced components
            namespaced = plugin_details.get_namespaced_components()
            
            for comp_type, comp_list in namespaced.items():
                components_info[comp_type] = comp_list
                components_info["total_count"] += len(comp_list)
            
            return components_info
            
        except Exception as e:
            self._print_warning(f"Failed to analyze plugin components: {e}")
            return components_info
    
    def _display_plugin_info_table(self, plugin_info: dict) -> None:
        """Display plugin information in table format.
        
        Args:
            plugin_info: Plugin information dictionary
        """
        # Plugin header
        print(f"\nPlugin: {plugin_info['name']}")
        print("=" * (len(plugin_info['name']) + 8))
        
        # Basic information
        print(f"Repository: {plugin_info['repository']}")
        print(f"Enabled: {'✓ Yes' if plugin_info['enabled'] else '✗ No'}")
        print(f"Installed: {'✓ Yes' if plugin_info['installed'] else '✗ No'}")
        
        if plugin_info.get('description'):
            print(f"Description: {plugin_info['description']}")
        
        if plugin_info.get('version'):
            print(f"Version: {plugin_info['version']}")
        
        if plugin_info.get('author'):
            print(f"Author: {plugin_info['author']}")
        
        # Repository information
        if plugin_info.get('repository_url'):
            print(f"Repository URL: {plugin_info['repository_url']}")
        
        if plugin_info.get('last_updated'):
            print(f"Last Updated: {plugin_info['last_updated']}")
        
        if plugin_info.get('commit_sha'):
            print(f"Commit SHA: {plugin_info['commit_sha'][:8]}...")
        
        if plugin_info.get('file_path'):
            print(f"Location: {plugin_info['file_path']}")
        
        # Components information
        if plugin_info.get('components'):
            components = plugin_info['components']
            total_components = components.get('total_count', 0)
            
            if total_components > 0:
                print(f"\nComponents ({total_components} total):")
                
                if components.get('commands'):
                    print(f"  Commands ({len(components['commands'])}):")
                    for cmd in components['commands']:
                        print(f"    - {cmd}")
                
                if components.get('agents'):
                    print(f"  Agents ({len(components['agents'])}):")
                    for agent in components['agents']:
                        print(f"    - {agent}")
                
                if components.get('hooks'):
                    print(f"  Hooks ({len(components['hooks'])}):")
                    for hook in components['hooks']:
                        print(f"    - {hook}")
            else:
                print("\nComponents: None found")
        
        # Status information
        if plugin_info.get('status'):
            print(f"\nStatus: {plugin_info['status']}")
    
    def _confirm_action(self, message: str) -> bool:
        """Prompt user for confirmation.
        
        Args:
            message: Confirmation message to display
            
        Returns:
            True if user confirms, False otherwise
        """
        try:
            response = input(f"{message} [y/N]: ").strip().lower()
            return response in ('y', 'yes')
        except (KeyboardInterrupt, EOFError):
            return False
    
    def _progress_indicator(self, message: str):
        """Context manager for progress indication.
        
        Args:
            message: Progress message to display
            
        Returns:
            Context manager for progress indication
        """
        from contextlib import contextmanager
        
        @contextmanager
        def progress():
            print(f"⏳ {message}...")
            try:
                yield
            finally:
                pass  # Could add completion message here
        
        return progress()


def main() -> int:
    """Main CLI entry point."""
    cli = PACCCli()
    parser = cli.create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def cli_main() -> None:
    """CLI entry point."""
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    cli_main()