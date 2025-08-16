"""Configuration management for Claude Code settings.json files."""

import json
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, Set, Callable
import logging
from copy import deepcopy

from .file_utils import FilePathValidator, PathNormalizer
from ..validation.base import ValidationResult, BaseValidator
from ..validation.formats import JSONValidator
from ..errors.exceptions import PACCError, ConfigurationError, ValidationError
from ..ui.components import MultiSelectList, SelectableItem
from ..recovery.strategies import RecoveryStrategy, RecoveryContext, RecoveryResult, RecoveryMode, create_recovery_strategy


logger = logging.getLogger(__name__)


@dataclass
class ConflictInfo:
    """Information about a configuration conflict."""
    
    key_path: str
    existing_value: Any
    new_value: Any
    conflict_type: str  # 'value_mismatch', 'type_mismatch', 'array_overlap'
    context: Optional[str] = None
    
    def __str__(self) -> str:
        """Return string representation of conflict."""
        return f"{self.conflict_type} at {self.key_path}: {self.existing_value} vs {self.new_value}"


@dataclass
class MergeResult:
    """Result of a configuration merge operation."""
    
    success: bool
    merged_config: Optional[Dict[str, Any]] = None
    conflicts: List[ConflictInfo] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    changes_made: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_conflicts(self) -> bool:
        """Check if merge result has conflicts."""
        return len(self.conflicts) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if merge result has warnings."""
        return len(self.warnings) > 0


class MergeStrategy(ABC):
    """Base class for configuration merge strategies."""
    
    @abstractmethod
    def merge(
        self, 
        existing_config: Dict[str, Any], 
        new_config: Dict[str, Any],
        key_path: str = ""
    ) -> MergeResult:
        """Merge two configuration objects.
        
        Args:
            existing_config: Existing configuration
            new_config: New configuration to merge in
            key_path: Current key path for tracking conflicts
            
        Returns:
            MergeResult with merged config and any conflicts
        """
        pass


class DeepMergeStrategy(MergeStrategy):
    """Deep merge strategy that recursively merges nested objects."""
    
    def __init__(
        self,
        array_strategy: str = "append",  # 'append', 'replace', 'dedupe'
        conflict_resolution: str = "prompt"  # 'prompt', 'keep_existing', 'use_new'
    ):
        """Initialize deep merge strategy.
        
        Args:
            array_strategy: How to handle array merging
            conflict_resolution: How to resolve value conflicts
        """
        self.array_strategy = array_strategy
        self.conflict_resolution = conflict_resolution
    
    def merge(
        self, 
        existing_config: Dict[str, Any], 
        new_config: Dict[str, Any],
        key_path: str = ""
    ) -> MergeResult:
        """Perform deep merge of configurations."""
        result = MergeResult(success=True)
        result.merged_config = deepcopy(existing_config)
        
        try:
            self._merge_recursive(
                result.merged_config,
                new_config,
                result,
                key_path
            )
        except Exception as e:
            result.success = False
            result.warnings.append(f"Merge failed: {e}")
            result.merged_config = existing_config
        
        return result
    
    def _merge_recursive(
        self, 
        target: Dict[str, Any], 
        source: Dict[str, Any], 
        result: MergeResult,
        key_path: str
    ) -> None:
        """Recursively merge source into target."""
        for key, value in source.items():
            current_path = f"{key_path}.{key}" if key_path else key
            
            if key not in target:
                # New key - just add it
                target[key] = deepcopy(value)
                result.changes_made.append(f"Added {current_path}")
                continue
            
            existing_value = target[key]
            
            # Handle type mismatches
            if type(existing_value) != type(value):
                conflict = ConflictInfo(
                    key_path=current_path,
                    existing_value=existing_value,
                    new_value=value,
                    conflict_type="type_mismatch",
                    context=f"Existing type: {type(existing_value).__name__}, new type: {type(value).__name__}"
                )
                result.conflicts.append(conflict)
                
                # For now, keep existing value on type mismatch
                result.warnings.append(f"Type mismatch at {current_path}, keeping existing value")
                continue
            
            # Handle different value types
            if isinstance(value, dict) and isinstance(existing_value, dict):
                # Recursive merge for nested objects
                self._merge_recursive(existing_value, value, result, current_path)
            
            elif isinstance(value, list) and isinstance(existing_value, list):
                # Handle array merging
                merged_array = self._merge_arrays(existing_value, value, current_path, result)
                target[key] = merged_array
            
            elif existing_value != value:
                # Value conflict - different primitive values
                conflict = ConflictInfo(
                    key_path=current_path,
                    existing_value=existing_value,
                    new_value=value,
                    conflict_type="value_mismatch"
                )
                result.conflicts.append(conflict)
                
                # Apply conflict resolution strategy
                if self.conflict_resolution == "use_new":
                    target[key] = deepcopy(value)
                    result.changes_made.append(f"Updated {current_path} (used new value)")
                elif self.conflict_resolution == "keep_existing":
                    # Keep existing value (no change)
                    result.warnings.append(f"Kept existing value at {current_path}")
                # For 'prompt', conflicts will be handled by the caller
    
    def _merge_arrays(
        self, 
        existing_array: List[Any], 
        new_array: List[Any], 
        key_path: str,
        result: MergeResult
    ) -> List[Any]:
        """Merge two arrays based on strategy."""
        if self.array_strategy == "replace":
            result.changes_made.append(f"Replaced array at {key_path}")
            return deepcopy(new_array)
        
        elif self.array_strategy == "append":
            merged = existing_array + new_array
            result.changes_made.append(f"Appended to array at {key_path}")
            return merged
        
        elif self.array_strategy == "dedupe":
            # Combine arrays and remove duplicates
            merged = existing_array.copy()
            added_count = 0
            
            for item in new_array:
                if item not in merged:
                    merged.append(item)
                    added_count += 1
            
            if added_count > 0:
                result.changes_made.append(f"Added {added_count} unique items to array at {key_path}")
            
            return merged
        
        else:
            # Default to append
            return existing_array + new_array


class ClaudeConfigManager:
    """Manages Claude Code configuration files with safe merging and validation."""
    
    def __init__(
        self,
        recovery_strategy: Optional[RecoveryStrategy] = None,
        validator: Optional[BaseValidator] = None
    ):
        """Initialize configuration manager.
        
        Args:
            recovery_strategy: Strategy for error recovery
            validator: JSON validator for configuration files
        """
        self.file_validator = FilePathValidator(allowed_extensions={'.json'})
        self.path_normalizer = PathNormalizer()
        self.recovery_strategy = recovery_strategy or create_recovery_strategy(
            RecoveryMode.INTERACTIVE
        )
        self.json_validator = validator or JSONValidator()
    
    def get_config_path(self, user_level: bool = False) -> Path:
        """Get path to Claude configuration file.
        
        Args:
            user_level: If True, get user-level config (~/.claude/settings.json)
                       If False, get project-level config (.claude/settings.json)
        
        Returns:
            Path to configuration file
        """
        if user_level:
            # User-level configuration
            home_dir = Path.home()
            config_dir = home_dir / ".claude"
        else:
            # Project-level configuration
            config_dir = Path(".claude")
        
        return config_dir / "settings.json"
    
    def ensure_config_directory(self, config_path: Path) -> None:
        """Ensure configuration directory exists.
        
        Args:
            config_path: Path to configuration file
        """
        config_dir = config_path.parent
        self.path_normalizer.ensure_directory(config_dir)
    
    def load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration dictionary
            
        Raises:
            ConfigurationError: If file cannot be loaded or is invalid
        """
        if not config_path.exists():
            logger.debug(f"Configuration file does not exist: {config_path}")
            return self._get_default_config()
        
        if not self.file_validator.is_valid_path(config_path):
            raise ConfigurationError(f"Invalid configuration file path: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validate JSON syntax
            validation_result = self.json_validator.validate_content(content, config_path)
            if not validation_result.is_valid:
                errors = [str(issue) for issue in validation_result.issues]
                raise ConfigurationError(f"Invalid JSON in {config_path}: {'; '.join(errors)}")
            
            config = json.loads(content)
            
            # Validate configuration structure
            self._validate_config_structure(config, config_path)
            
            return config
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in {config_path}: {e}")
        except OSError as e:
            raise ConfigurationError(f"Cannot read configuration file {config_path}: {e}")
    
    def save_config(
        self, 
        config: Dict[str, Any], 
        config_path: Path,
        create_backup: bool = True
    ) -> None:
        """Save configuration to file with backup.
        
        Args:
            config: Configuration to save
            config_path: Path to save configuration
            create_backup: Whether to create backup before saving
            
        Raises:
            ConfigurationError: If configuration cannot be saved
        """
        # Validate configuration before saving
        self._validate_config_structure(config, config_path)
        
        # Ensure directory exists
        self.ensure_config_directory(config_path)
        
        # Create backup if requested
        backup_path = None
        if create_backup and config_path.exists():
            backup_path = self._create_backup(config_path)
        
        try:
            # Write configuration
            config_json = json.dumps(config, indent=2, ensure_ascii=False)
            
            # Validate JSON before writing
            json.loads(config_json)  # Quick validation
            
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(config_json)
            
            logger.info(f"Configuration saved to {config_path}")
            
        except Exception as e:
            # Restore backup if save failed
            if backup_path and backup_path.exists():
                try:
                    shutil.copy2(backup_path, config_path)
                    logger.info(f"Restored backup after save failure")
                except OSError:
                    logger.error(f"Failed to restore backup after save failure")
            
            raise ConfigurationError(f"Failed to save configuration to {config_path}: {e}")
    
    def merge_config(
        self, 
        config_path: Path, 
        new_config: Dict[str, Any],
        merge_strategy: Optional[MergeStrategy] = None,
        resolve_conflicts: bool = True
    ) -> MergeResult:
        """Merge new configuration into existing configuration.
        
        Args:
            config_path: Path to existing configuration file
            new_config: New configuration to merge
            merge_strategy: Strategy to use for merging
            resolve_conflicts: Whether to prompt user for conflict resolution
            
        Returns:
            MergeResult with merged configuration and conflicts
        """
        logger.debug(f"Merging configuration into {config_path}")
        
        # Load existing configuration
        existing_config = self.load_config(config_path)
        
        # Use default merge strategy if none provided
        if merge_strategy is None:
            conflict_resolution = "prompt" if resolve_conflicts else "keep_existing"
            merge_strategy = DeepMergeStrategy(
                array_strategy="dedupe",
                conflict_resolution=conflict_resolution
            )
        
        # Perform merge
        merge_result = merge_strategy.merge(existing_config, new_config)
        
        if not merge_result.success:
            return merge_result
        
        # Handle conflicts if any
        if merge_result.has_conflicts and resolve_conflicts:
            resolved_config = self._resolve_conflicts(
                merge_result.merged_config,
                merge_result.conflicts
            )
            if resolved_config is not None:
                merge_result.merged_config = resolved_config
                merge_result.conflicts.clear()  # Conflicts were resolved
            else:
                # User cancelled conflict resolution
                merge_result.success = False
                merge_result.warnings.append("Configuration merge cancelled by user")
        
        return merge_result
    
    def update_config_atomic(
        self,
        config_path: Path,
        updates: Dict[str, Any],
        merge_strategy: Optional[MergeStrategy] = None
    ) -> bool:
        """Atomically update configuration with rollback on failure.
        
        Args:
            config_path: Path to configuration file
            updates: Configuration updates to apply
            merge_strategy: Strategy for merging updates
            
        Returns:
            True if update succeeded, False otherwise
        """
        backup_path = None
        
        try:
            # Create backup if file exists
            if config_path.exists():
                backup_path = self._create_backup(config_path)
            
            # Perform merge
            merge_result = self.merge_config(config_path, updates, merge_strategy)
            
            if not merge_result.success:
                logger.error(f"Configuration merge failed: {merge_result.warnings}")
                return False
            
            # Save merged configuration
            self.save_config(merge_result.merged_config, config_path, create_backup=False)
            
            logger.info(f"Configuration updated successfully: {len(merge_result.changes_made)} changes")
            return True
            
        except Exception as e:
            logger.error(f"Atomic configuration update failed: {e}")
            
            # Attempt to restore backup
            if backup_path and backup_path.exists():
                try:
                    shutil.copy2(backup_path, config_path)
                    logger.info(f"Configuration restored from backup")
                except OSError as restore_error:
                    logger.error(f"Failed to restore backup: {restore_error}")
            
            return False
        
        finally:
            # Clean up backup file
            if backup_path and backup_path.exists():
                try:
                    backup_path.unlink()
                except OSError:
                    logger.warning(f"Failed to remove backup file: {backup_path}")
    
    def add_extension_config(
        self,
        extension_type: str,
        extension_config: Dict[str, Any],
        user_level: bool = False
    ) -> bool:
        """Add extension configuration to Claude settings.
        
        Note: Only hooks and MCPs require settings.json entries.
        Agents and commands are file-based and discovered automatically.
        
        Args:
            extension_type: Type of extension ('hooks', 'mcps')
            extension_config: Configuration for the extension
            user_level: Whether to update user-level or project-level config
            
        Returns:
            True if extension was added successfully
        """
        config_path = self.get_config_path(user_level)
        
        # Prepare update based on extension type
        if extension_type == "hooks":
            updates = {"hooks": [extension_config]}
        elif extension_type == "mcps":
            updates = {"mcps": [extension_config]}
        elif extension_type in ["agents", "commands"]:
            # Agents and commands don't go in settings.json
            # They are discovered from their directories
            raise ConfigurationError(
                f"Extension type '{extension_type}' is file-based and doesn't require settings.json entries. "
                f"Simply place the file in the appropriate directory."
            )
        else:
            raise ConfigurationError(f"Unknown extension type: {extension_type}")
        
        # Use dedupe strategy for arrays to avoid duplicates
        merge_strategy = DeepMergeStrategy(
            array_strategy="dedupe",
            conflict_resolution="prompt"
        )
        
        return self.update_config_atomic(config_path, updates, merge_strategy)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default Claude configuration structure.
        
        Note: Only hooks and MCPs are stored in settings.json.
        Agents and commands are file-based.
        """
        return {
            "hooks": [],
            "mcps": []
        }
    
    def _validate_config_structure(self, config: Dict[str, Any], config_path: Path) -> None:
        """Validate Claude configuration structure.
        
        Args:
            config: Configuration to validate
            config_path: Path to configuration file for error reporting
            
        Raises:
            ValidationError: If configuration structure is invalid
        """
        if not isinstance(config, dict):
            raise ValidationError(f"Configuration must be a JSON object in {config_path}")
        
        # Check for required extension arrays (only hooks and mcps)
        for key in ["hooks", "mcps"]:
            if key in config and not isinstance(config[key], list):
                raise ValidationError(f"'{key}' must be an array in {config_path}")
        
        # Additional validation could be added here for specific extension schemas
    
    def _create_backup(self, config_path: Path) -> Path:
        """Create backup of configuration file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Path to backup file
        """
        backup_path = config_path.with_suffix('.json.backup')
        shutil.copy2(config_path, backup_path)
        logger.debug(f"Created backup: {backup_path}")
        return backup_path
    
    def _resolve_conflicts(
        self, 
        merged_config: Dict[str, Any], 
        conflicts: List[ConflictInfo]
    ) -> Optional[Dict[str, Any]]:
        """Interactively resolve configuration conflicts.
        
        Args:
            merged_config: Configuration with conflicts
            conflicts: List of conflicts to resolve
            
        Returns:
            Resolved configuration or None if cancelled
        """
        if not conflicts:
            return merged_config
        
        print(f"\n🔧 Configuration conflicts detected:")
        print(f"Found {len(conflicts)} conflicts that need resolution.\n")
        
        resolved_config = deepcopy(merged_config)
        
        for i, conflict in enumerate(conflicts, 1):
            print(f"Conflict {i}/{len(conflicts)}: {conflict.conflict_type}")
            print(f"Key: {conflict.key_path}")
            print(f"Existing: {conflict.existing_value}")
            print(f"New:      {conflict.new_value}")
            if conflict.context:
                print(f"Context:  {conflict.context}")
            
            # Create selection items
            items = [
                SelectableItem(
                    id="keep_existing",
                    display_text="Keep existing value",
                    description=f"Keep: {conflict.existing_value}",
                    metadata={"value": conflict.existing_value}
                ),
                SelectableItem(
                    id="use_new",
                    display_text="Use new value",
                    description=f"Use: {conflict.new_value}",
                    metadata={"value": conflict.new_value}
                )
            ]
            
            # Show interactive selection
            selector = MultiSelectList(
                items=items,
                title=f"Resolve conflict at {conflict.key_path}:",
                allow_multiple=False
            )
            
            selected = selector.run()
            
            if not selected:
                print("❌ Conflict resolution cancelled.")
                return None
            
            choice = selected[0]
            chosen_value = choice.metadata["value"]
            
            # Apply choice to resolved config
            self._set_nested_value(resolved_config, conflict.key_path, chosen_value)
            
            print(f"✅ Resolved: Using {choice.display_text.lower()}\n")
        
        print(f"🎉 All conflicts resolved!")
        return resolved_config
    
    def _set_nested_value(self, config: Dict[str, Any], key_path: str, value: Any) -> None:
        """Set a nested value in configuration using dot notation.
        
        Args:
            config: Configuration dictionary
            key_path: Dot-separated key path (e.g., "mcps.0.name")
            value: Value to set
        """
        keys = key_path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key.isdigit():
                # Array index
                idx = int(key)
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return  # Invalid path
            else:
                # Object key
                if key not in current:
                    current[key] = {}
                current = current[key]
        
        # Set final value
        final_key = keys[-1]
        if final_key.isdigit():
            idx = int(final_key)
            if isinstance(current, list) and 0 <= idx < len(current):
                current[idx] = value
        else:
            current[final_key] = value


def deduplicate_extension_list(
    extensions: List[Dict[str, Any]], 
    key_field: str = "name"
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Deduplicate list of extensions based on a key field.
    
    Args:
        extensions: List of extension configurations
        key_field: Field to use for deduplication (default: "name")
        
    Returns:
        Tuple of (deduplicated_list, list_of_duplicates_removed)
    """
    seen = set()
    deduplicated = []
    duplicates = []
    
    for ext in extensions:
        if key_field in ext:
            key_value = ext[key_field]
            if key_value not in seen:
                seen.add(key_value)
                deduplicated.append(ext)
            else:
                duplicates.append(f"{key_field}={key_value}")
        else:
            # Keep extensions without the key field
            deduplicated.append(ext)
    
    return deduplicated, duplicates