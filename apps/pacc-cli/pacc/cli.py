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
        self._print_info("List command not yet implemented")
        return 0

    def remove_command(self, args) -> int:
        """Handle the remove command.""" 
        self._print_info("Remove command not yet implemented")
        return 0

    def info_command(self, args) -> int:
        """Handle the info command."""
        self._print_info("Info command not yet implemented")
        return 0

    def _install_extension(self, extension, base_dir: Path, force: bool = False) -> None:
        """Install a single extension."""
        # This is a placeholder - actual installation logic would go here
        # For now, just create the directory structure
        ext_dir = base_dir / extension.extension_type
        ext_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy the extension file
        import shutil
        dest_path = ext_dir / extension.file_path.name
        
        if dest_path.exists() and not force:
            raise ValueError(f"Extension already exists: {dest_path}. Use --force to overwrite.")
        
        shutil.copy2(extension.file_path, dest_path)

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