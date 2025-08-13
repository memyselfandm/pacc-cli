#!/usr/bin/env python3
"""PACC CLI - Package manager for Claude Code."""

import argparse
import asyncio
import sys
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
        """Create configuration entry for an extension."""
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
        elif extension.extension_type == "agents":
            config.update({
                "model": "claude-3-sonnet",  # Default model
                "description": extension.description or "Custom agent"
            })
        elif extension.extension_type == "commands":
            config.update({
                "description": extension.description or "Custom command",
                "aliases": []
            })
        
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