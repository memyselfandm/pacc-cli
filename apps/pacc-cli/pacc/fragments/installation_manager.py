"""Fragment Installation Manager for Claude Code memory fragments.

This module provides the main installation workflow for memory fragments,
supporting installation from Git repositories, local paths, and collections.
"""

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple
import logging

from .claude_md_manager import CLAUDEmdManager
from .storage_manager import FragmentStorageManager
from ..validators.fragment_validator import FragmentValidator
from ..core.config_manager import ClaudeConfigManager
from ..sources.base import SourceHandler, Source
from ..sources.git import GitSourceHandler, GitRepositorySource
from ..sources.url import URLSourceHandler, URLSource, is_url
from ..ui.components import MultiSelectList, SelectableItem
from ..errors.exceptions import PACCError, ValidationError, FileSystemError
from ..core.file_utils import FilePathValidator


logger = logging.getLogger(__name__)


@dataclass
class FragmentSource:
    """Represents a source of memory fragments."""
    source_type: str  # 'git', 'url', 'local', 'collection'
    location: str
    is_remote: bool = False
    is_collection: bool = False
    fragments: List[Path] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstallationResult:
    """Result of a fragment installation operation."""
    success: bool
    installed_count: int = 0
    source_type: str = ""
    target_type: str = ""
    installed_fragments: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    validation_warnings: List[str] = field(default_factory=list)
    error_message: str = ""
    dry_run: bool = False
    changes_made: List[str] = field(default_factory=list)


class FragmentInstallationManager:
    """Manages installation of Claude Code memory fragments."""
    
    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        """Initialize fragment installation manager.
        
        Args:
            project_root: Project root directory (defaults to current working directory)
        """
        self.project_root = Path(project_root or Path.cwd()).resolve()
        
        # Initialize component managers
        self.claude_md_manager = CLAUDEmdManager(project_root=self.project_root)
        self.storage_manager = FragmentStorageManager(project_root=self.project_root)
        self.validator = FragmentValidator()
        
        # Initialize path validator
        self.path_validator = FilePathValidator(allowed_extensions={'.md', '.txt'})
        
        # Configuration manager for pacc.json updates
        self.config_manager = ClaudeConfigManager()
        
        logger.info(f"Fragment installation manager initialized for project: {self.project_root}")

    def resolve_source(self, source_input: str) -> FragmentSource:
        """Resolve source input to a FragmentSource object.
        
        Args:
            source_input: Source input (URL, path, etc.)
            
        Returns:
            FragmentSource object with resolved information
            
        Raises:
            PACCError: If source cannot be resolved or accessed
        """
        # Check if it's a URL (HTTP/HTTPS)
        if is_url(source_input):
            if source_input.endswith('.git') or 'github.com' in source_input or 'gitlab.com' in source_input:
                # Git repository URL
                return FragmentSource(
                    source_type="git",
                    location=source_input,
                    is_remote=True
                )
            else:
                # Direct URL download
                return FragmentSource(
                    source_type="url",
                    location=source_input,
                    is_remote=True
                )
        
        # Check if it's a local path
        source_path = Path(source_input).resolve()
        if not source_path.exists():
            raise PACCError(f"Source not found: {source_input}")
        
        if source_path.is_file():
            # Single fragment file
            if not self.path_validator.is_valid_path(source_path):
                raise PACCError(f"Invalid fragment file: {source_input}")
            
            return FragmentSource(
                source_type="local",
                location=str(source_path),
                is_remote=False,
                fragments=[source_path]
            )
        
        elif source_path.is_dir():
            # Directory - could be a collection
            fragments = self._discover_fragments_in_directory(source_path)
            if not fragments:
                raise PACCError(f"No fragments found in directory: {source_input}")
            
            is_collection = len(fragments) > 1
            
            return FragmentSource(
                source_type="collection" if is_collection else "local",
                location=str(source_path),
                is_remote=False,
                is_collection=is_collection,
                fragments=fragments
            )
        
        else:
            raise PACCError(f"Invalid source type: {source_input}")

    def _discover_fragments_in_directory(self, directory: Path) -> List[Path]:
        """Discover fragment files in a directory.
        
        Args:
            directory: Directory to search
            
        Returns:
            List of fragment file paths
        """
        fragment_files = []
        
        # Look for markdown files (potential fragments)
        for md_file in directory.rglob("*.md"):
            if self.path_validator.is_valid_path(md_file):
                try:
                    # Quick validation check to see if it's a proper fragment
                    validation_result = self.validator.validate_single(md_file)
                    if validation_result.is_valid or not validation_result.errors:
                        fragment_files.append(md_file)
                except Exception as e:
                    logger.warning(f"Could not validate potential fragment {md_file}: {e}")
                    # Include it anyway, let full validation handle it later
                    fragment_files.append(md_file)
        
        return fragment_files

    def install_from_source(
        self,
        source_input: str,
        target_type: str = "project",
        interactive: bool = False,
        install_all: bool = False,
        force: bool = False,
        dry_run: bool = False
    ) -> InstallationResult:
        """Install fragments from a source.
        
        Args:
            source_input: Source input (URL, path, etc.)
            target_type: Installation target ('project' or 'user')
            interactive: Use interactive selection for collections
            install_all: Install all fragments found (non-interactive)
            force: Force installation, overwrite existing fragments
            dry_run: Show what would be installed without making changes
            
        Returns:
            InstallationResult with operation details
        """
        result = InstallationResult(
            success=False,
            target_type=target_type,
            dry_run=dry_run
        )
        
        try:
            # Resolve source
            source = self.resolve_source(source_input)
            result.source_type = source.source_type
            
            logger.info(f"Installing fragments from {source.source_type} source: {source.location}")
            
            # Handle remote sources (Git/URL)
            if source.is_remote:
                temp_fragments = self._fetch_remote_source(source)
            else:
                temp_fragments = source.fragments
            
            # Select fragments to install
            fragments_to_install = self._select_fragments_for_installation(
                temp_fragments, interactive, install_all
            )
            
            if not fragments_to_install:
                result.success = True
                result.installed_count = 0
                return result
            
            # Validate selected fragments
            validation_results = self._validate_fragments(fragments_to_install, force)
            result.validation_warnings.extend(validation_results.get('warnings', []))
            
            if validation_results.get('errors') and not force:
                result.error_message = f"Validation errors found: {validation_results['errors']}"
                return result
            
            # Perform installation (or dry-run)
            if dry_run:
                result = self._perform_dry_run_installation(result, fragments_to_install, target_type)
            else:
                result = self._perform_actual_installation(result, fragments_to_install, target_type, force)
            
            return result
            
        except Exception as e:
            logger.error(f"Fragment installation failed: {e}")
            result.error_message = str(e)
            return result

    def _fetch_remote_source(self, source: FragmentSource) -> List[Path]:
        """Fetch fragments from remote source (Git/URL).
        
        Args:
            source: Remote fragment source
            
        Returns:
            List of local fragment paths after fetching
            
        Raises:
            PACCError: If remote fetch fails
        """
        if source.source_type == "git":
            return self._fetch_git_source(source)
        elif source.source_type == "url":
            return self._fetch_url_source(source)
        else:
            raise PACCError(f"Unsupported remote source type: {source.source_type}")

    def _fetch_git_source(self, source: FragmentSource) -> List[Path]:
        """Fetch fragments from Git repository.
        
        Args:
            source: Git fragment source
            
        Returns:
            List of local fragment paths after cloning
        """
        from ..sources.git import GitCloner
        
        temp_dir = Path(tempfile.mkdtemp(prefix="pacc_git_"))
        try:
            cloner = GitCloner()
            repo_path = cloner.clone(source.location, temp_dir)
            
            # Discover fragments in cloned repository
            fragments = self._discover_fragments_in_directory(repo_path)
            if not fragments:
                raise PACCError(f"No fragments found in Git repository: {source.location}")
            
            return fragments
            
        except Exception as e:
            # Clean up temp directory on error
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise PACCError(f"Failed to fetch Git repository: {e}") from e

    def _fetch_url_source(self, source: FragmentSource) -> List[Path]:
        """Fetch fragments from URL.
        
        Args:
            source: URL fragment source
            
        Returns:
            List of local fragment paths after downloading
        """
        from ..sources.url import create_url_source_handler
        
        temp_dir = Path(tempfile.mkdtemp(prefix="pacc_url_"))
        try:
            handler = create_url_source_handler()
            downloaded_path = handler.download(source.location, temp_dir)
            
            if downloaded_path.is_file():
                # Single file download
                return [downloaded_path] if self.path_validator.is_valid_path(downloaded_path) else []
            else:
                # Directory/archive download
                return self._discover_fragments_in_directory(downloaded_path)
                
        except Exception as e:
            # Clean up temp directory on error
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise PACCError(f"Failed to fetch URL: {e}") from e

    def _select_fragments_for_installation(
        self, 
        fragments: List[Path], 
        interactive: bool, 
        install_all: bool
    ) -> List[Path]:
        """Select fragments for installation based on user preferences.
        
        Args:
            fragments: Available fragment files
            interactive: Use interactive selection
            install_all: Install all fragments
            
        Returns:
            List of selected fragment files
        """
        if not fragments:
            return []
        
        if len(fragments) == 1:
            # Single fragment - always install
            return fragments
        
        if install_all:
            # Install all fragments
            return fragments
        
        if interactive:
            # Interactive selection
            items = []
            for fragment in fragments:
                # Get fragment metadata for display
                try:
                    validation_result = self.validator.validate_single(fragment)
                    title = validation_result.metadata.get('title', fragment.stem)
                    description = validation_result.metadata.get('description', '')
                except Exception:
                    title = fragment.stem
                    description = ''
                
                items.append(SelectableItem(
                    value=fragment,
                    display_text=title,
                    description=description
                ))
            
            selector = MultiSelectList(
                items=items,
                title="Select fragments to install",
                min_selections=0
            )
            
            selected_indices = selector.show()
            return [fragments[i] for i in selected_indices]
        else:
            # Default: install all if multiple found
            return fragments

    def _validate_fragments(self, fragments: List[Path], force: bool) -> Dict[str, List[str]]:
        """Validate fragments before installation.
        
        Args:
            fragments: Fragment files to validate
            force: Whether to force installation despite errors
            
        Returns:
            Dictionary with 'errors' and 'warnings' lists
        """
        errors = []
        warnings = []
        
        for fragment in fragments:
            try:
                result = self.validator.validate_single(fragment)
                
                if result.errors:
                    errors.extend([f"{fragment.name}: {error}" for error in result.errors])
                
                if result.warnings:
                    warnings.extend([f"{fragment.name}: {warning}" for warning in result.warnings])
                    
            except Exception as e:
                errors.append(f"{fragment.name}: Validation failed - {e}")
        
        return {'errors': errors, 'warnings': warnings}

    def _perform_dry_run_installation(
        self, 
        result: InstallationResult, 
        fragments: List[Path], 
        target_type: str
    ) -> InstallationResult:
        """Perform dry-run installation (show what would be installed).
        
        Args:
            result: Installation result to update
            fragments: Fragments to install
            target_type: Installation target type
            
        Returns:
            Updated installation result
        """
        result.success = True
        result.installed_count = len(fragments)
        
        for fragment in fragments:
            fragment_name = fragment.stem
            
            # Get fragment metadata
            try:
                validation_result = self.validator.validate_single(fragment)
                metadata = validation_result.metadata or {}
            except Exception:
                metadata = {}
            
            # Generate reference path
            if target_type == "user":
                ref_path = f"~/.claude/pacc/fragments/{fragment_name}.md"
            else:
                ref_path = f".claude/pacc/fragments/{fragment_name}.md"
            
            result.installed_fragments[fragment_name] = {
                "title": metadata.get('title', ''),
                "description": metadata.get('description', ''),
                "tags": metadata.get('tags', []),
                "reference_path": ref_path,
                "storage_type": target_type,
                "would_install": True
            }
            
            result.changes_made.append(f"Would install fragment: {fragment_name}")
        
        return result

    def _perform_actual_installation(
        self, 
        result: InstallationResult, 
        fragments: List[Path], 
        target_type: str,
        force: bool
    ) -> InstallationResult:
        """Perform actual fragment installation.
        
        Args:
            result: Installation result to update
            fragments: Fragments to install
            target_type: Installation target type
            force: Force overwrite existing fragments
            
        Returns:
            Updated installation result
        """
        installed_fragments = []
        
        try:
            # Create backup of current state for rollback
            backup_state = self._create_installation_backup(target_type)
            
            # Install fragments atomically
            for fragment in fragments:
                fragment_info = self._install_single_fragment(fragment, target_type, force)
                installed_fragments.append(fragment_info)
                result.installed_fragments[fragment_info['name']] = fragment_info
                result.changes_made.append(f"Installed fragment: {fragment_info['name']}")
            
            # Update CLAUDE.md with fragment references
            self._update_claude_md_with_fragments(installed_fragments, target_type)
            result.changes_made.append("Updated CLAUDE.md with fragment references")
            
            # Update pacc.json to track installed fragments
            self._update_pacc_json_with_fragments(installed_fragments, target_type)
            result.changes_made.append("Updated pacc.json with fragment tracking")
            
            result.success = True
            result.installed_count = len(installed_fragments)
            
            logger.info(f"Successfully installed {len(installed_fragments)} fragments")
            
        except Exception as e:
            logger.error(f"Installation failed, performing rollback: {e}")
            
            # Rollback on failure
            try:
                self._rollback_installation(backup_state, installed_fragments)
                result.changes_made.append("Rolled back changes due to installation failure")
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
                result.changes_made.append(f"Rollback failed: {rollback_error}")
            
            result.error_message = f"Installation failed: {e}"
            result.success = False
        
        return result

    def _install_single_fragment(self, fragment: Path, target_type: str, force: bool) -> Dict[str, Any]:
        """Install a single fragment to storage.
        
        Args:
            fragment: Fragment file to install
            target_type: Installation target type
            force: Force overwrite existing fragments
            
        Returns:
            Fragment information dictionary
            
        Raises:
            PACCError: If installation fails
        """
        fragment_name = fragment.stem
        content = fragment.read_text(encoding='utf-8')
        
        # Get fragment metadata
        try:
            validation_result = self.validator.validate_single(fragment)
            metadata = validation_result.metadata or {}
        except Exception as e:
            if not force:
                raise PACCError(f"Fragment validation failed: {e}")
            metadata = {}
        
        # Store fragment in appropriate location
        try:
            stored_path = self.storage_manager.store_fragment(
                fragment_name=fragment_name,
                content=content,
                storage_type=target_type,
                overwrite=force
            )
        except PACCError as e:
            if "already exists" in str(e) and not force:
                raise PACCError(f"Fragment '{fragment_name}' already exists. Use --force to overwrite.")
            raise
        
        # Generate reference path relative to project/user root
        if target_type == "user":
            ref_path = f"~/.claude/pacc/fragments/{fragment_name}.md"
        else:
            project_relative = stored_path.relative_to(self.project_root)
            ref_path = str(project_relative).replace('\\', '/')
        
        return {
            "name": fragment_name,
            "title": metadata.get('title', ''),
            "description": metadata.get('description', ''),
            "tags": metadata.get('tags', []),
            "category": metadata.get('category', ''),
            "author": metadata.get('author', ''),
            "reference_path": ref_path,
            "storage_type": target_type,
            "storage_path": str(stored_path),
            "installed_at": datetime.now().isoformat()
        }

    def _update_claude_md_with_fragments(self, fragments: List[Dict[str, Any]], target_type: str) -> None:
        """Update CLAUDE.md file with fragment references.
        
        Args:
            fragments: List of installed fragment info dictionaries
            target_type: Installation target type
        """
        if target_type == "user":
            claude_md_path = self.claude_md_manager.get_user_claude_md()
        else:
            claude_md_path = self.claude_md_manager.get_project_claude_md()
        
        # Get existing fragment section content
        existing_content = self.claude_md_manager.get_section_content(claude_md_path, "fragments") or ""
        
        # Build new references
        new_references = []
        for fragment in fragments:
            ref_line = f"@{fragment['reference_path']}"
            if fragment.get('title'):
                ref_line += f" - {fragment['title']}"
            new_references.append(ref_line)
        
        # Combine with existing content (avoid duplicates)
        existing_lines = [line.strip() for line in existing_content.split('\n') if line.strip()]
        all_references = []
        
        # Add existing references first
        for line in existing_lines:
            if line.startswith('@') and line not in [ref for ref in new_references]:
                all_references.append(line)
        
        # Add new references
        all_references.extend(new_references)
        
        # Update section with combined references
        if all_references:
            section_content = '\n'.join(all_references)
            self.claude_md_manager.update_section(
                file_path=claude_md_path,
                section_name="fragments",
                content=section_content,
                create_if_missing=True
            )

    def _update_pacc_json_with_fragments(self, fragments: List[Dict[str, Any]], target_type: str) -> None:
        """Update pacc.json to track installed fragments.
        
        Args:
            fragments: List of installed fragment info dictionaries
            target_type: Installation target type
        """
        pacc_json_path = self.project_root / "pacc.json"
        
        # Load or create pacc.json
        if pacc_json_path.exists():
            try:
                config = json.loads(pacc_json_path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                config = {}
        else:
            config = {}
        
        # Ensure fragments section exists
        if "fragments" not in config:
            config["fragments"] = {}
        
        # Add fragment entries
        for fragment in fragments:
            config["fragments"][fragment["name"]] = {
                "title": fragment.get("title", ""),
                "description": fragment.get("description", ""),
                "tags": fragment.get("tags", []),
                "category": fragment.get("category", ""),
                "author": fragment.get("author", ""),
                "reference_path": fragment["reference_path"],
                "storage_type": fragment["storage_type"],
                "installed_at": fragment["installed_at"]
            }
        
        # Write updated config
        pacc_json_path.write_text(json.dumps(config, indent=2), encoding='utf-8')

    def _create_installation_backup(self, target_type: str) -> Dict[str, Any]:
        """Create backup state for rollback purposes.
        
        Args:
            target_type: Installation target type
            
        Returns:
            Backup state dictionary
        """
        backup_state = {
            "target_type": target_type,
            "claude_md_backup": None,
            "pacc_json_backup": None,
            "storage_backup": None
        }
        
        # Backup CLAUDE.md
        if target_type == "user":
            claude_md_path = self.claude_md_manager.get_user_claude_md()
        else:
            claude_md_path = self.claude_md_manager.get_project_claude_md()
        
        if claude_md_path.exists():
            backup_state["claude_md_backup"] = claude_md_path.read_text(encoding='utf-8')
        
        # Backup pacc.json
        pacc_json_path = self.project_root / "pacc.json"
        if pacc_json_path.exists():
            backup_state["pacc_json_backup"] = pacc_json_path.read_text(encoding='utf-8')
        
        return backup_state

    def _rollback_installation(self, backup_state: Dict[str, Any], installed_fragments: List[Dict[str, Any]]) -> None:
        """Rollback installation changes.
        
        Args:
            backup_state: Backup state from before installation
            installed_fragments: List of fragments that were installed
        """
        target_type = backup_state["target_type"]
        
        # Remove installed fragment files
        for fragment in installed_fragments:
            try:
                storage_path = Path(fragment["storage_path"])
                if storage_path.exists():
                    storage_path.unlink()
            except Exception as e:
                logger.warning(f"Could not remove fragment file during rollback: {e}")
        
        # Restore CLAUDE.md
        if backup_state["claude_md_backup"] is not None:
            if target_type == "user":
                claude_md_path = self.claude_md_manager.get_user_claude_md()
            else:
                claude_md_path = self.claude_md_manager.get_project_claude_md()
            
            try:
                claude_md_path.write_text(backup_state["claude_md_backup"], encoding='utf-8')
            except Exception as e:
                logger.warning(f"Could not restore CLAUDE.md during rollback: {e}")
        
        # Restore pacc.json
        if backup_state["pacc_json_backup"] is not None:
            pacc_json_path = self.project_root / "pacc.json"
            try:
                pacc_json_path.write_text(backup_state["pacc_json_backup"], encoding='utf-8')
            except Exception as e:
                logger.warning(f"Could not restore pacc.json during rollback: {e}")