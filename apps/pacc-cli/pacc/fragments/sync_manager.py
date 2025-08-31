"""Fragment Sync Manager for team synchronization of Claude Code memory fragments.

This module provides team synchronization capabilities for memory fragments
through pacc.json specifications and sync commands.
"""

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple, Set
import logging

from .storage_manager import FragmentStorageManager
from .installation_manager import FragmentInstallationManager
from .update_manager import FragmentUpdateManager
from .claude_md_manager import CLAUDEmdManager
from .version_tracker import FragmentVersionTracker
from ..core.project_config import ProjectConfigManager
from ..errors.exceptions import PACCError
from ..ui.components import MultiSelectList, SelectableItem

logger = logging.getLogger(__name__)


@dataclass
class FragmentSyncSpec:
    """Specification for a fragment in pacc.json."""
    name: str
    source: str
    version: Optional[str] = None
    required: bool = True
    collection: Optional[str] = None
    storage_type: str = "project"


@dataclass
class SyncConflict:
    """Represents a sync conflict."""
    fragment_name: str
    conflict_type: str  # 'version', 'modified', 'missing'
    local_version: Optional[str] = None
    remote_version: Optional[str] = None
    description: str = ""
    resolution_options: List[str] = field(default_factory=list)


@dataclass
class SyncResult:
    """Result of a fragment sync operation."""
    success: bool
    synced_count: int = 0
    added_count: int = 0
    updated_count: int = 0
    removed_count: int = 0
    conflict_count: int = 0
    conflicts: List[SyncConflict] = field(default_factory=list)
    changes_made: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False


class FragmentSyncManager:
    """Manages team synchronization of Claude Code memory fragments."""
    
    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        """Initialize fragment sync manager.
        
        Args:
            project_root: Project root directory (defaults to current working directory)
        """
        self.project_root = Path(project_root or Path.cwd()).resolve()
        
        # Initialize component managers
        self.storage_manager = FragmentStorageManager(project_root=self.project_root)
        self.installation_manager = FragmentInstallationManager(project_root=self.project_root)
        self.update_manager = FragmentUpdateManager(project_root=self.project_root)
        self.claude_md_manager = CLAUDEmdManager(project_root=self.project_root)
        self.version_tracker = FragmentVersionTracker(project_root=self.project_root)
        self.config_manager = ProjectConfigManager()
        
        logger.info(f"Fragment sync manager initialized for project: {self.project_root}")
    
    def load_sync_specifications(self) -> List[FragmentSyncSpec]:
        """Load fragment sync specifications from pacc.json.
        
        Returns:
            List of fragment sync specifications
        """
        specs = []
        
        # Load pacc.json
        pacc_json_path = self.project_root / "pacc.json"
        if not pacc_json_path.exists():
            return specs
        
        try:
            config = json.loads(pacc_json_path.read_text(encoding='utf-8'))
            
            # Look for fragment specifications
            fragment_specs = config.get('fragmentSpecs', {})
            
            for name, spec_data in fragment_specs.items():
                spec = FragmentSyncSpec(
                    name=name,
                    source=spec_data.get('source', ''),
                    version=spec_data.get('version'),
                    required=spec_data.get('required', True),
                    collection=spec_data.get('collection'),
                    storage_type=spec_data.get('storageType', 'project')
                )
                specs.append(spec)
        
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"Failed to read pacc.json: {e}")
        
        return specs
    
    def save_sync_specifications(self, specs: List[FragmentSyncSpec]) -> None:
        """Save fragment sync specifications to pacc.json.
        
        Args:
            specs: List of fragment sync specifications
        """
        pacc_json_path = self.project_root / "pacc.json"
        
        # Load existing config
        if pacc_json_path.exists():
            try:
                config = json.loads(pacc_json_path.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                config = {}
        else:
            config = {}
        
        # Update fragment specifications
        config['fragmentSpecs'] = {}
        
        for spec in specs:
            spec_data = {
                'source': spec.source,
                'storageType': spec.storage_type
            }
            
            if spec.version:
                spec_data['version'] = spec.version
            if not spec.required:
                spec_data['required'] = False
            if spec.collection:
                spec_data['collection'] = spec.collection
            
            config['fragmentSpecs'][spec.name] = spec_data
        
        # Save config
        pacc_json_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    
    def detect_conflicts(
        self,
        specs: List[FragmentSyncSpec],
        installed_fragments: Dict[str, Any]
    ) -> List[SyncConflict]:
        """Detect conflicts between specs and installed fragments.
        
        Args:
            specs: Fragment specifications from pacc.json
            installed_fragments: Currently installed fragments
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        for spec in specs:
            if spec.name in installed_fragments:
                installed = installed_fragments[spec.name]
                
                # Check for version conflicts
                if spec.version and installed.get('version') != spec.version:
                    conflict = SyncConflict(
                        fragment_name=spec.name,
                        conflict_type='version',
                        local_version=installed.get('version'),
                        remote_version=spec.version,
                        description=f"Version mismatch: local={installed.get('version')}, spec={spec.version}",
                        resolution_options=['keep_local', 'use_spec', 'merge']
                    )
                    conflicts.append(conflict)
                
                # Check for source conflicts
                if installed.get('source_url') and installed['source_url'] != spec.source:
                    conflict = SyncConflict(
                        fragment_name=spec.name,
                        conflict_type='source',
                        description=f"Source mismatch: local={installed['source_url']}, spec={spec.source}",
                        resolution_options=['keep_local', 'use_spec']
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def sync_fragments(
        self,
        interactive: bool = True,
        force: bool = False,
        dry_run: bool = False,
        add_missing: bool = True,
        remove_extra: bool = False,
        update_existing: bool = True
    ) -> SyncResult:
        """Synchronize fragments based on pacc.json specifications.
        
        Args:
            interactive: Use interactive conflict resolution
            force: Force sync even with conflicts
            dry_run: Show what would be synced without making changes
            add_missing: Add fragments specified but not installed
            remove_extra: Remove installed fragments not in specs
            update_existing: Update existing fragments to spec versions
            
        Returns:
            Result of sync operation
        """
        result = SyncResult(
            success=False,
            dry_run=dry_run
        )
        
        try:
            # Load specifications
            specs = self.load_sync_specifications()
            if not specs:
                result.success = True
                result.changes_made.append("No fragment specifications found in pacc.json")
                return result
            
            # Get currently installed fragments
            installed_fragments = self._get_installed_fragments()
            
            # Detect conflicts
            conflicts = self.detect_conflicts(specs, installed_fragments)
            
            if conflicts and not force:
                if interactive:
                    # Resolve conflicts interactively
                    resolutions = self._resolve_conflicts_interactive(conflicts)
                    conflicts = [c for c in conflicts if c.fragment_name not in resolutions]
                else:
                    # Can't proceed with conflicts in non-interactive mode
                    result.conflicts = conflicts
                    result.conflict_count = len(conflicts)
                    result.errors.append(f"Found {len(conflicts)} conflicts - use --force to override")
                    return result
            
            # Process sync operations
            if dry_run:
                result = self._perform_dry_run_sync(result, specs, installed_fragments, add_missing, remove_extra, update_existing)
            else:
                result = self._perform_actual_sync(result, specs, installed_fragments, add_missing, remove_extra, update_existing)
            
            result.success = result.conflict_count == 0 and len(result.errors) == 0
            
        except Exception as e:
            logger.error(f"Fragment sync failed: {e}")
            result.errors.append(str(e))
        
        return result
    
    def _get_installed_fragments(self) -> Dict[str, Any]:
        """Get currently installed fragments from pacc.json.
        
        Returns:
            Dictionary of fragment names to metadata
        """
        pacc_json_path = self.project_root / "pacc.json"
        if not pacc_json_path.exists():
            return {}
        
        try:
            config = json.loads(pacc_json_path.read_text(encoding='utf-8'))
            return config.get('fragments', {})
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    
    def _resolve_conflicts_interactive(self, conflicts: List[SyncConflict]) -> Dict[str, str]:
        """Resolve conflicts interactively.
        
        Args:
            conflicts: List of conflicts to resolve
            
        Returns:
            Dictionary of fragment names to resolution choices
        """
        resolutions = {}
        
        for conflict in conflicts:
            print(f"\nConflict in fragment '{conflict.fragment_name}':")
            print(f"  {conflict.description}")
            print("\nOptions:")
            
            for i, option in enumerate(conflict.resolution_options, 1):
                print(f"  {i}. {option.replace('_', ' ').title()}")
            
            while True:
                try:
                    choice = input("\nChoose resolution (number): ").strip()
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(conflict.resolution_options):
                        resolutions[conflict.fragment_name] = conflict.resolution_options[choice_idx]
                        break
                    else:
                        print("Invalid choice, please try again")
                except (ValueError, KeyboardInterrupt):
                    print("Skipping conflict resolution")
                    break
        
        return resolutions
    
    def _perform_dry_run_sync(
        self,
        result: SyncResult,
        specs: List[FragmentSyncSpec],
        installed: Dict[str, Any],
        add_missing: bool,
        remove_extra: bool,
        update_existing: bool
    ) -> SyncResult:
        """Perform dry run sync to show what would change.
        
        Args:
            result: Result object to update
            specs: Fragment specifications
            installed: Installed fragments
            add_missing: Whether to add missing fragments
            remove_extra: Whether to remove extra fragments
            update_existing: Whether to update existing fragments
            
        Returns:
            Updated result object
        """
        spec_names = {spec.name for spec in specs}
        installed_names = set(installed.keys())
        
        # Fragments to add
        if add_missing:
            to_add = spec_names - installed_names
            for name in to_add:
                result.changes_made.append(f"Would add: {name}")
                result.added_count += 1
        
        # Fragments to remove
        if remove_extra:
            to_remove = installed_names - spec_names
            for name in to_remove:
                result.changes_made.append(f"Would remove: {name}")
                result.removed_count += 1
        
        # Fragments to update
        if update_existing:
            for spec in specs:
                if spec.name in installed:
                    if spec.version and installed[spec.name].get('version') != spec.version:
                        result.changes_made.append(f"Would update: {spec.name} to version {spec.version}")
                        result.updated_count += 1
        
        result.synced_count = result.added_count + result.updated_count
        return result
    
    def _perform_actual_sync(
        self,
        result: SyncResult,
        specs: List[FragmentSyncSpec],
        installed: Dict[str, Any],
        add_missing: bool,
        remove_extra: bool,
        update_existing: bool
    ) -> SyncResult:
        """Perform actual sync operations.
        
        Args:
            result: Result object to update
            specs: Fragment specifications
            installed: Installed fragments
            add_missing: Whether to add missing fragments
            remove_extra: Whether to remove extra fragments
            update_existing: Whether to update existing fragments
            
        Returns:
            Updated result object
        """
        spec_names = {spec.name for spec in specs}
        installed_names = set(installed.keys())
        spec_map = {spec.name: spec for spec in specs}
        logger.debug(f"Spec names: {spec_names}, Installed names: {installed_names}")
        
        # Add missing fragments
        if add_missing:
            to_add = spec_names - installed_names
            for name in to_add:
                spec = spec_map[name]
                try:
                    install_result = self.installation_manager.install_from_source(
                        source_input=spec.source,
                        target_type=spec.storage_type,
                        interactive=False,
                        install_all=True,
                        force=True,
                        dry_run=False
                    )
                    if install_result.success:
                        result.added_count += 1
                        result.changes_made.append(f"Added: {name}")
                    else:
                        result.errors.append(f"Failed to add {name}: {install_result.error_message}")
                except Exception as e:
                    result.errors.append(f"Failed to add {name}: {e}")
        
        # Remove extra fragments
        if remove_extra:
            to_remove = installed_names - spec_names
            logger.debug(f"Spec names: {spec_names}, Installed names: {installed_names}")
            logger.debug(f"Fragments to remove: {to_remove}")
            for name in to_remove:
                try:
                    # Remove from storage
                    locations = self.storage_manager.list_fragments()
                    for location in locations:
                        if location.name == name:
                            self.storage_manager.remove_fragment(
                                fragment_name=name,
                                storage_type=location.storage_type,
                                collection_name=location.collection_name
                            )
                            result.removed_count += 1
                            result.changes_made.append(f"Removed: {name}")
                            break
                except Exception as e:
                    result.errors.append(f"Failed to remove {name}: {e}")
        
        # Update existing fragments
        if update_existing:
            for spec in specs:
                if spec.name in installed:
                    if spec.version and installed[spec.name].get('version') != spec.version:
                        try:
                            # Re-install from source with specific version
                            install_result = self.installation_manager.install_from_source(
                                source_input=spec.source,
                                target_type=spec.storage_type,
                                interactive=False,
                                install_all=True,
                                force=True,
                                dry_run=False
                            )
                            if install_result.success:
                                result.updated_count += 1
                                result.changes_made.append(f"Updated: {spec.name} to version {spec.version}")
                            else:
                                result.errors.append(f"Failed to update {spec.name}: {install_result.error_message}")
                        except Exception as e:
                            result.errors.append(f"Failed to update {spec.name}: {e}")
        
        result.synced_count = result.added_count + result.updated_count
        return result
    
    def add_fragment_spec(
        self,
        name: str,
        source: str,
        version: Optional[str] = None,
        required: bool = True,
        collection: Optional[str] = None,
        storage_type: str = "project"
    ) -> None:
        """Add a fragment specification to pacc.json.
        
        Args:
            name: Fragment name
            source: Fragment source URL or path
            version: Optional version constraint
            required: Whether fragment is required
            collection: Optional collection name
            storage_type: Storage type (project or user)
        """
        specs = self.load_sync_specifications()
        
        # Check if already exists
        existing_spec = next((s for s in specs if s.name == name), None)
        
        if existing_spec:
            # Update existing spec
            existing_spec.source = source
            existing_spec.version = version
            existing_spec.required = required
            existing_spec.collection = collection
            existing_spec.storage_type = storage_type
        else:
            # Add new spec
            new_spec = FragmentSyncSpec(
                name=name,
                source=source,
                version=version,
                required=required,
                collection=collection,
                storage_type=storage_type
            )
            specs.append(new_spec)
        
        self.save_sync_specifications(specs)
    
    def remove_fragment_spec(self, name: str) -> bool:
        """Remove a fragment specification from pacc.json.
        
        Args:
            name: Fragment name to remove
            
        Returns:
            True if removed, False if not found
        """
        specs = self.load_sync_specifications()
        original_count = len(specs)
        
        specs = [s for s in specs if s.name != name]
        
        if len(specs) < original_count:
            self.save_sync_specifications(specs)
            return True
        
        return False