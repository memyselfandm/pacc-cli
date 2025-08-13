#!/usr/bin/env python3
"""PACC CLI - Package manager for Claude Code."""

import argparse
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

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


@dataclass
class Extension:
    """Represents a detected extension."""
    name: str
    file_path: Path
    extension_type: str
    description: Optional[str] = None


class PACCCli:
    """Main CLI class for PACC operations."""
    
    def __init__(self):
        pass
        
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
        
        return parser
    
    def _add_install_parser(self, subparsers) -> None:
        """Add the install command parser."""
        install_parser = subparsers.add_parser(
            "install",
            help="Install Claude Code extensions",
            description="Install hooks, MCP servers, agents, or commands from local sources"
        )
        
        install_parser.add_argument(
            "source",
            help="Path to extension file or directory to install"
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
        
        remove_parser.add_argument(
            "--user",
            action="store_true",
            help="Remove from user directory"
        )
        
        remove_parser.add_argument(
            "--project",
            action="store_true",
            help="Remove from project directory"
        )
        
        remove_parser.add_argument(
            "--confirm", "-y",
            action="store_true",
            help="Skip confirmation prompt"
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

    def install_command(self, args) -> int:
        """Handle the install command."""
        try:
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
            
            if args.dry_run:
                self._print_info(f"Would install {success_count} extension(s)")
            else:
                self._print_success(f"Successfully installed {success_count} extension(s)")
            
            return 0
            
        except Exception as e:
            self._print_error(f"Installation failed: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1

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

    def list_command(self, args) -> int:
        """Handle the list command."""
        try:
            from fnmatch import fnmatch
            from datetime import datetime
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
                    return datetime.min
                filtered_extensions.sort(key=get_date, reverse=True)
            
            # Format and display output
            if args.format == "json":
                output = {
                    "extensions": filtered_extensions,
                    "count": len(filtered_extensions)
                }
                print(json.dumps(output, indent=2))
                
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
        self._print_info("Remove command not yet implemented")
        return 0

    def info_command(self, args) -> int:
        """Handle the info command."""
        self._print_info("Info command not yet implemented")
        return 0

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

    def _format_extension_for_selection(self, ext) -> str:
        """Format extension for selection UI."""
        return f"{ext.name} ({ext.extension_type}) - {ext.description or 'No description'}"

    def _print_info(self, message: str) -> None:
        """Print info message."""
        print(f"ℹ {message}")

    def _print_success(self, message: str) -> None:
        """Print success message."""
        print(f"✓ {message}")

    def _print_error(self, message: str) -> None:
        """Print error message."""
        print(f"✗ {message}", file=sys.stderr)

    def _print_warning(self, message: str) -> None:
        """Print warning message."""
        print(f"⚠ {message}", file=sys.stderr)


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