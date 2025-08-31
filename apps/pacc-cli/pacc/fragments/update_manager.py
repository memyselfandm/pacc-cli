"""Fragment Update Manager for Claude Code memory fragments.

This module provides update detection and application for installed memory fragments,
supporting version comparison through Git commits and safe update mechanisms.
"""

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple
import logging
import subprocess

from .storage_manager import FragmentStorageManager, FragmentLocation
from .installation_manager import FragmentInstallationManager
from .claude_md_manager import CLAUDEmdManager
from ..validators.fragment_validator import FragmentValidator
from ..sources.git import GitSourceHandler, GitRepositorySource
from ..sources.url import URLSourceHandler, URLSource, is_url
from ..errors.exceptions import PACCError, ValidationError
from ..core.file_utils import FilePathValidator

logger = logging.getLogger(__name__)


@dataclass
class FragmentUpdateInfo:
    """Information about a fragment update."""
    name: str
    current_version: Optional[str]  # Git SHA or date
    latest_version: Optional[str]   # Git SHA or date
    has_update: bool
    source_url: Optional[str]
    changes: List[str] = field(default_factory=list)
    conflict: bool = False
    error: Optional[str] = None


@dataclass
class UpdateResult:
    """Result of a fragment update operation."""
    success: bool
    updated_count: int = 0
    skipped_count: int = 0
    conflict_count: int = 0
    error_count: int = 0
    updates: Dict[str, FragmentUpdateInfo] = field(default_factory=dict)
    dry_run: bool = False
    changes_made: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class FragmentUpdateManager:
    """Manages updates for installed Claude Code memory fragments."""
    
    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        """Initialize fragment update manager.
        
        Args:
            project_root: Project root directory (defaults to current working directory)
        """
        self.project_root = Path(project_root or Path.cwd()).resolve()
        
        # Initialize component managers
        self.storage_manager = FragmentStorageManager(project_root=self.project_root)
        self.installation_manager = FragmentInstallationManager(project_root=self.project_root)
        self.claude_md_manager = CLAUDEmdManager(project_root=self.project_root)
        self.validator = FragmentValidator()
        
        # Path validator
        self.path_validator = FilePathValidator(allowed_extensions={'.md', '.txt'})
        
        logger.info(f"Fragment update manager initialized for project: {self.project_root}")
    
    def check_for_updates(
        self,
        fragment_names: Optional[List[str]] = None,
        storage_type: Optional[str] = None
    ) -> Dict[str, FragmentUpdateInfo]:
        """Check for available updates for installed fragments.
        
        Args:
            fragment_names: Specific fragments to check (None = all)
            storage_type: Filter by storage type ('project' or 'user')
            
        Returns:
            Dictionary of fragment names to update information
        """
        updates = {}
        
        # Load pacc.json to get fragment metadata
        pacc_json_path = self.project_root / "pacc.json"
        if not pacc_json_path.exists():
            logger.warning("No pacc.json found - no fragments to update")
            return updates
        
        try:
            config = json.loads(pacc_json_path.read_text(encoding='utf-8'))
            fragments = config.get('fragments', {})
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to read pacc.json: {e}")
            return updates
        
        # Filter fragments based on parameters
        for name, metadata in fragments.items():
            # Skip if specific names requested and this isn't one
            if fragment_names and name not in fragment_names:
                continue
            
            # Skip if storage type filter doesn't match
            if storage_type and metadata.get('storage_type') != storage_type:
                continue
            
            # Check for updates for this fragment
            update_info = self._check_fragment_update(name, metadata)
            updates[name] = update_info
        
        return updates
    
    def _check_fragment_update(self, name: str, metadata: Dict[str, Any]) -> FragmentUpdateInfo:
        """Check if a specific fragment has updates available.
        
        Args:
            name: Fragment name
            metadata: Fragment metadata from pacc.json
            
        Returns:
            Fragment update information
        """
        update_info = FragmentUpdateInfo(
            name=name,
            current_version=metadata.get('version'),
            latest_version=None,
            has_update=False,
            source_url=metadata.get('source_url')
        )
        
        # If no source URL stored, we can't check for updates
        if not update_info.source_url:
            update_info.error = "No source URL tracked - cannot check for updates"
            return update_info
        
        try:
            # Check if it's a Git source
            if update_info.source_url.endswith('.git') or 'github.com' in update_info.source_url:
                update_info = self._check_git_update(update_info, metadata)
            else:
                # For URL sources, check modification time or content hash
                update_info = self._check_url_update(update_info, metadata)
        except Exception as e:
            logger.error(f"Failed to check updates for {name}: {e}")
            update_info.error = str(e)
        
        return update_info
    
    def _check_git_update(self, update_info: FragmentUpdateInfo, metadata: Dict[str, Any]) -> FragmentUpdateInfo:
        """Check for updates from a Git repository source.
        
        Args:
            update_info: Update information to populate
            metadata: Fragment metadata
            
        Returns:
            Updated fragment update information
        """
        try:
            # Clone repo to temp directory to check latest version
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Clone the repository
                result = subprocess.run(
                    ['git', 'clone', '--depth', '1', update_info.source_url, str(temp_path)],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode != 0:
                    update_info.error = f"Failed to clone repository: {result.stderr}"
                    return update_info
                
                # Get latest commit SHA
                result = subprocess.run(
                    ['git', 'rev-parse', 'HEAD'],
                    cwd=temp_path,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    latest_sha = result.stdout.strip()
                    update_info.latest_version = latest_sha[:8]  # Short SHA
                    
                    # Compare with current version
                    current_sha = metadata.get('version', '')
                    if current_sha and current_sha != latest_sha[:8]:
                        update_info.has_update = True
                        
                        # Try to get commit messages between versions
                        if current_sha:
                            update_info.changes = self._get_git_changes(temp_path, current_sha, latest_sha)
        
        except Exception as e:
            update_info.error = f"Git check failed: {e}"
        
        return update_info
    
    def _check_url_update(self, update_info: FragmentUpdateInfo, metadata: Dict[str, Any]) -> FragmentUpdateInfo:
        """Check for updates from a URL source.
        
        Args:
            update_info: Update information to populate
            metadata: Fragment metadata
            
        Returns:
            Updated fragment update information
        """
        # For URL sources, we'll compare content hashes
        # This is a simplified implementation
        update_info.error = "URL update checking not yet implemented"
        return update_info
    
    def _get_git_changes(self, repo_path: Path, old_sha: str, new_sha: str) -> List[str]:
        """Get list of changes between two Git commits.
        
        Args:
            repo_path: Path to Git repository
            old_sha: Old commit SHA
            new_sha: New commit SHA
            
        Returns:
            List of change descriptions
        """
        changes = []
        
        try:
            # Get commit messages between versions
            result = subprocess.run(
                ['git', 'log', '--oneline', f'{old_sha}..{new_sha}'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        changes.append(line)
        except Exception as e:
            logger.warning(f"Could not get git changes: {e}")
        
        return changes
    
    def update_fragments(
        self,
        fragment_names: Optional[List[str]] = None,
        force: bool = False,
        dry_run: bool = False,
        merge_strategy: str = "safe"
    ) -> UpdateResult:
        """Update installed fragments to their latest versions.
        
        Args:
            fragment_names: Specific fragments to update (None = all with updates)
            force: Force update even with conflicts
            dry_run: Show what would be updated without making changes
            merge_strategy: How to handle CLAUDE.md updates ('safe', 'overwrite', 'merge')
            
        Returns:
            Result of update operation
        """
        result = UpdateResult(
            success=False,
            dry_run=dry_run
        )
        
        try:
            # Check for updates
            updates = self.check_for_updates(fragment_names)
            
            # Filter to only fragments with updates
            fragments_to_update = {
                name: info for name, info in updates.items()
                if info.has_update and not info.error
            }
            
            if not fragments_to_update:
                result.success = True
                result.changes_made.append("No updates available")
                return result
            
            # Create backup before updates
            backup_state = self._create_update_backup()
            
            try:
                # Process each update
                for name, update_info in fragments_to_update.items():
                    if dry_run:
                        result.changes_made.append(f"Would update {name}: {update_info.current_version} -> {update_info.latest_version}")
                        result.updated_count += 1
                    else:
                        success = self._apply_fragment_update(name, update_info, force, merge_strategy)
                        if success:
                            result.updated_count += 1
                            result.changes_made.append(f"Updated {name} to {update_info.latest_version}")
                        else:
                            result.error_count += 1
                            result.errors.append(f"Failed to update {name}")
                    
                    result.updates[name] = update_info
                
                result.success = result.error_count == 0
                
                if not dry_run and result.success:
                    # Update pacc.json with new versions
                    self._update_fragment_versions(result.updates)
                
            except Exception as e:
                # Rollback on failure
                if not dry_run:
                    self._rollback_updates(backup_state)
                raise e
                
        except Exception as e:
            logger.error(f"Fragment update failed: {e}")
            result.errors.append(str(e))
        
        return result
    
    def _create_update_backup(self) -> Dict[str, Any]:
        """Create backup state before updates.
        
        Returns:
            Backup state dictionary
        """
        backup = {
            "timestamp": datetime.now().isoformat(),
            "claude_md": None,
            "pacc_json": None,
            "fragments": {}
        }
        
        # Backup CLAUDE.md
        claude_md_path = self.project_root / "CLAUDE.md"
        if claude_md_path.exists():
            backup["claude_md"] = claude_md_path.read_text(encoding='utf-8')
        
        # Backup pacc.json
        pacc_json_path = self.project_root / "pacc.json"
        if pacc_json_path.exists():
            backup["pacc_json"] = pacc_json_path.read_text(encoding='utf-8')
        
        # Backup fragment files
        for location in self.storage_manager.list_fragments():
            if location.path.exists():
                backup["fragments"][str(location.path)] = location.path.read_text(encoding='utf-8')
        
        return backup
    
    def _apply_fragment_update(
        self,
        name: str,
        update_info: FragmentUpdateInfo,
        force: bool,
        merge_strategy: str
    ) -> bool:
        """Apply update to a specific fragment.
        
        Args:
            name: Fragment name
            update_info: Update information
            force: Force update even with conflicts
            merge_strategy: How to handle CLAUDE.md updates
            
        Returns:
            True if update successful
        """
        try:
            # Re-install fragment from source with latest version
            result = self.installation_manager.install_from_source(
                source_input=update_info.source_url,
                target_type="project",  # Maintain same storage type
                interactive=False,
                install_all=True,
                force=force,
                dry_run=False
            )
            
            return result.success
            
        except Exception as e:
            logger.error(f"Failed to apply update for {name}: {e}")
            return False
    
    def _update_fragment_versions(self, updates: Dict[str, FragmentUpdateInfo]) -> None:
        """Update fragment versions in pacc.json.
        
        Args:
            updates: Dictionary of fragment updates
        """
        pacc_json_path = self.project_root / "pacc.json"
        
        try:
            config = json.loads(pacc_json_path.read_text(encoding='utf-8'))
            fragments = config.get('fragments', {})
            
            for name, update_info in updates.items():
                if name in fragments and update_info.latest_version:
                    fragments[name]['version'] = update_info.latest_version
                    fragments[name]['updated_at'] = datetime.now().isoformat()
            
            pacc_json_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
            
        except Exception as e:
            logger.error(f"Failed to update pacc.json versions: {e}")
    
    def _rollback_updates(self, backup_state: Dict[str, Any]) -> None:
        """Rollback updates using backup state.
        
        Args:
            backup_state: Backup state to restore
        """
        try:
            # Restore CLAUDE.md
            if backup_state["claude_md"]:
                claude_md_path = self.project_root / "CLAUDE.md"
                claude_md_path.write_text(backup_state["claude_md"], encoding='utf-8')
            
            # Restore pacc.json
            if backup_state["pacc_json"]:
                pacc_json_path = self.project_root / "pacc.json"
                pacc_json_path.write_text(backup_state["pacc_json"], encoding='utf-8')
            
            # Restore fragment files
            for path_str, content in backup_state["fragments"].items():
                Path(path_str).write_text(content, encoding='utf-8')
                
        except Exception as e:
            logger.error(f"Rollback failed: {e}")