"""Plugin configuration management with atomic operations and backup support."""

import json
import shutil
import tempfile
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, Set, Callable, ContextManager
import logging
from copy import deepcopy
from contextlib import contextmanager

from ..core.file_utils import FilePathValidator, PathNormalizer
from ..validation.base import ValidationResult, BaseValidator
from ..validation.formats import JSONValidator
from ..errors.exceptions import PACCError, ConfigurationError, ValidationError
from ..recovery.strategies import RecoveryStrategy, RecoveryContext, RecoveryResult, RecoveryMode, create_recovery_strategy


logger = logging.getLogger(__name__)


@dataclass
class BackupInfo:
    """Information about a configuration backup."""
    
    original_path: Path
    backup_path: Path
    timestamp: datetime
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """Return string representation of backup info."""
        return f"Backup of {self.original_path.name} at {self.timestamp.isoformat()}"


class AtomicFileWriter:
    """Provides atomic file write operations with automatic rollback."""
    
    def __init__(self, target_path: Path, create_backup: bool = True):
        """Initialize atomic file writer.
        
        Args:
            target_path: Path to the target file
            create_backup: Whether to create backup before writing
        """
        self.target_path = target_path
        self.create_backup = create_backup
        self.temp_path: Optional[Path] = None
        self.backup_path: Optional[Path] = None
        self._lock = threading.RLock()
    
    @contextmanager
    def write_context(self) -> ContextManager[Path]:
        """Context manager for atomic file writing.
        
        Yields:
            Path to temporary file to write to
            
        Example:
            with AtomicFileWriter(config_path).write_context() as temp_path:
                with open(temp_path, 'w') as f:
                    json.dump(config, f, indent=2)
        """
        with self._lock:
            try:
                # Create backup if requested and file exists
                if self.create_backup and self.target_path.exists():
                    self.backup_path = self._create_backup()
                
                # Create temporary file in same directory as target
                target_dir = self.target_path.parent
                target_dir.mkdir(parents=True, exist_ok=True)
                
                with tempfile.NamedTemporaryFile(
                    mode='w',
                    dir=target_dir,
                    prefix=f".{self.target_path.name}.",
                    suffix=".tmp",
                    delete=False,
                    encoding='utf-8'
                ) as temp_file:
                    self.temp_path = Path(temp_file.name)
                
                yield self.temp_path
                
                # Validate the temporary file was written
                if not self.temp_path.exists():
                    raise ConfigurationError("Temporary file was not created")
                
                # Atomic move to target location
                self._atomic_replace()
                
                # Clean up backup on success
                if self.backup_path and self.backup_path.exists():
                    self.backup_path.unlink()
                    self.backup_path = None
                
            except Exception as e:
                # Rollback on any failure
                self._rollback()
                raise ConfigurationError(f"Atomic write failed for {self.target_path}: {e}") from e
            finally:
                # Clean up temporary file
                if self.temp_path and self.temp_path.exists():
                    try:
                        self.temp_path.unlink()
                    except OSError:
                        logger.warning(f"Failed to clean up temporary file: {self.temp_path}")
                    self.temp_path = None
    
    def write_json(self, data: Dict[str, Any], indent: int = 2) -> None:
        """Write JSON data atomically.
        
        Args:
            data: JSON data to write
            indent: JSON indentation level
        """
        with self.write_context() as temp_path:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
    
    def _create_backup(self) -> Path:
        """Create backup of target file.
        
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.target_path.with_suffix(f".backup.{timestamp}")
        shutil.copy2(self.target_path, backup_path)
        logger.debug(f"Created backup: {backup_path}")
        return backup_path
    
    def _atomic_replace(self) -> None:
        """Atomically replace target file with temporary file."""
        if not self.temp_path:
            raise ConfigurationError("No temporary file to replace with")
        
        # On Windows, we need to remove the target first for atomic replacement
        import platform
        if platform.system() == "Windows" and self.target_path.exists():
            self.target_path.unlink()
        
        # Atomic move
        shutil.move(str(self.temp_path), str(self.target_path))
        logger.debug(f"Atomically replaced {self.target_path}")
    
    def _rollback(self) -> None:
        """Rollback changes by restoring backup."""
        if self.backup_path and self.backup_path.exists():
            try:
                if self.target_path.exists():
                    self.target_path.unlink()
                shutil.copy2(self.backup_path, self.target_path)
                logger.info(f"Rolled back changes to {self.target_path}")
            except OSError as e:
                logger.error(f"Failed to rollback {self.target_path}: {e}")


class ConfigBackup:
    """Manages configuration file backups with metadata and restoration."""
    
    def __init__(self, backup_dir: Optional[Path] = None):
        """Initialize config backup manager.
        
        Args:
            backup_dir: Directory to store backups (default: ~/.claude/backups)
        """
        if backup_dir is None:
            backup_dir = Path.home() / ".claude" / "backups"
        
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def create_backup(
        self, 
        config_path: Path, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> BackupInfo:
        """Create timestamped backup of configuration file.
        
        Args:
            config_path: Path to configuration file to backup
            metadata: Optional metadata to store with backup
            
        Returns:
            BackupInfo with backup details
        """
        if not config_path.exists():
            raise ConfigurationError(f"Cannot backup non-existent file: {config_path}")
        
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
        
        # Create backup filename
        original_name = config_path.name
        backup_name = f"{original_name}.{timestamp_str}.backup"
        backup_path = self.backup_dir / backup_name
        
        # Copy file to backup location
        shutil.copy2(config_path, backup_path)
        
        # Calculate checksum for integrity verification
        checksum = self._calculate_checksum(backup_path)
        
        # Create backup info
        backup_info = BackupInfo(
            original_path=config_path,
            backup_path=backup_path,
            timestamp=timestamp,
            checksum=checksum,
            metadata=metadata or {}
        )
        
        # Save backup metadata
        self._save_backup_metadata(backup_info)
        
        logger.info(f"Created backup: {backup_info}")
        return backup_info
    
    def restore_backup(self, backup_info: BackupInfo, verify_checksum: bool = True) -> bool:
        """Restore configuration from backup.
        
        Args:
            backup_info: Backup information
            verify_checksum: Whether to verify backup integrity
            
        Returns:
            True if restoration succeeded
        """
        if not backup_info.backup_path.exists():
            logger.error(f"Backup file not found: {backup_info.backup_path}")
            return False
        
        # Verify backup integrity
        if verify_checksum and backup_info.checksum:
            current_checksum = self._calculate_checksum(backup_info.backup_path)
            if current_checksum != backup_info.checksum:
                logger.error(f"Backup integrity check failed for {backup_info.backup_path}")
                return False
        
        try:
            # Ensure target directory exists
            backup_info.original_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Restore file
            shutil.copy2(backup_info.backup_path, backup_info.original_path)
            logger.info(f"Restored backup to {backup_info.original_path}")
            return True
            
        except OSError as e:
            logger.error(f"Failed to restore backup: {e}")
            return False
    
    def list_backups(self, config_path: Optional[Path] = None) -> List[BackupInfo]:
        """List available backups.
        
        Args:
            config_path: Optional filter for specific configuration file
            
        Returns:
            List of available backups
        """
        backups = []
        
        for backup_file in self.backup_dir.glob("*.backup"):
            metadata_file = backup_file.with_suffix(".backup.meta")
            if metadata_file.exists():
                try:
                    backup_info = self._load_backup_metadata(metadata_file)
                    if config_path is None or backup_info.original_path == config_path:
                        backups.append(backup_info)
                except Exception as e:
                    logger.warning(f"Failed to load backup metadata for {backup_file}: {e}")
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda b: b.timestamp, reverse=True)
        return backups
    
    def cleanup_old_backups(self, keep_count: int = 10, max_age_days: int = 30) -> int:
        """Clean up old backup files.
        
        Args:
            keep_count: Minimum number of backups to keep per file
            max_age_days: Maximum age in days for backups
            
        Returns:
            Number of backups removed
        """
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        removed_count = 0
        
        # Group backups by original file
        backups_by_file: Dict[Path, List[BackupInfo]] = {}
        for backup in self.list_backups():
            if backup.original_path not in backups_by_file:
                backups_by_file[backup.original_path] = []
            backups_by_file[backup.original_path].append(backup)
        
        # Clean up old backups for each file
        for original_path, file_backups in backups_by_file.items():
            # Sort by timestamp (newest first)
            file_backups.sort(key=lambda b: b.timestamp, reverse=True)
            
            # Keep the most recent backups
            to_keep = file_backups[:keep_count]
            candidates_for_removal = file_backups[keep_count:]
            
            # Remove backups older than cutoff date
            for backup in candidates_for_removal:
                if backup.timestamp < cutoff_date:
                    try:
                        if backup.backup_path.exists():
                            backup.backup_path.unlink()
                        
                        metadata_file = backup.backup_path.with_suffix(".backup.meta")
                        if metadata_file.exists():
                            metadata_file.unlink()
                        
                        removed_count += 1
                        logger.debug(f"Removed old backup: {backup.backup_path}")
                        
                    except OSError as e:
                        logger.warning(f"Failed to remove backup {backup.backup_path}: {e}")
        
        logger.info(f"Cleaned up {removed_count} old backups")
        return removed_count
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hexadecimal checksum string
        """
        import hashlib
        
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _save_backup_metadata(self, backup_info: BackupInfo) -> None:
        """Save backup metadata to companion file.
        
        Args:
            backup_info: Backup information to save
        """
        metadata_file = backup_info.backup_path.with_suffix(".backup.meta")
        
        metadata = {
            "original_path": str(backup_info.original_path),
            "backup_path": str(backup_info.backup_path),
            "timestamp": backup_info.timestamp.isoformat(),
            "checksum": backup_info.checksum,
            "metadata": backup_info.metadata
        }
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    def _load_backup_metadata(self, metadata_file: Path) -> BackupInfo:
        """Load backup metadata from file.
        
        Args:
            metadata_file: Path to metadata file
            
        Returns:
            BackupInfo object
        """
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        return BackupInfo(
            original_path=Path(metadata["original_path"]),
            backup_path=Path(metadata["backup_path"]),
            timestamp=datetime.fromisoformat(metadata["timestamp"]),
            checksum=metadata.get("checksum"),
            metadata=metadata.get("metadata", {})
        )


class PluginConfigManager:
    """Main configuration management class for Claude Code plugins."""
    
    def __init__(
        self,
        plugins_dir: Optional[Path] = None,
        settings_path: Optional[Path] = None,
        backup_manager: Optional[ConfigBackup] = None
    ):
        """Initialize plugin configuration manager.
        
        Args:
            plugins_dir: Directory containing plugin repositories (default: ~/.claude/plugins)
            settings_path: Path to Claude settings.json (default: ~/.claude/settings.json)
            backup_manager: Backup manager instance
        """
        if plugins_dir is None:
            plugins_dir = Path.home() / ".claude" / "plugins"
        if settings_path is None:
            settings_path = Path.home() / ".claude" / "settings.json"
        
        self.plugins_dir = plugins_dir
        self.settings_path = settings_path
        self.config_path = plugins_dir / "config.json"
        self.repos_dir = plugins_dir / "repos"
        
        self.backup_manager = backup_manager or ConfigBackup()
        self.json_validator = JSONValidator()
        self._lock = threading.RLock()
        
        # Configuration caching for performance
        self._config_cache = {}
        self._config_mtime = {}
        self._settings_cache = None
        self._settings_mtime = 0
        
        # Ensure directories exist
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.repos_dir.mkdir(parents=True, exist_ok=True)
    
    def add_repository(
        self, 
        owner: str, 
        repo: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add repository to config.json.
        
        Args:
            owner: Repository owner
            repo: Repository name
            metadata: Optional repository metadata
            
        Returns:
            True if repository was added successfully
        """
        with self._lock:
            try:
                # Load existing config
                config = self._load_plugin_config()
                
                # Create repository entry
                repo_key = f"{owner}/{repo}"
                repo_entry = metadata or {}
                
                # Add standard fields if not present
                if "lastUpdated" not in repo_entry:
                    repo_entry["lastUpdated"] = datetime.now().isoformat()
                if "plugins" not in repo_entry:
                    repo_entry["plugins"] = []
                
                # Add to config
                if "repositories" not in config:
                    config["repositories"] = {}
                
                config["repositories"][repo_key] = repo_entry
                
                # Save config atomically
                return self._save_plugin_config(config)
                
            except Exception as e:
                logger.error(f"Failed to add repository {owner}/{repo}: {e}")
                return False
    
    def remove_repository(self, owner: str, repo: str) -> bool:
        """Remove repository from config.json.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            True if repository was removed successfully
        """
        with self._lock:
            try:
                # Load existing config
                config = self._load_plugin_config()
                
                repo_key = f"{owner}/{repo}"
                
                if "repositories" in config and repo_key in config["repositories"]:
                    # Create backup before modification
                    backup_info = self.backup_config(self.config_path)
                    
                    # Remove repository
                    del config["repositories"][repo_key]
                    
                    # Save config atomically
                    if self._save_plugin_config(config):
                        logger.info(f"Repository {repo_key} removed successfully")
                        return True
                    else:
                        # Rollback on save failure
                        self.restore_config(backup_info.backup_path)
                        return False
                else:
                    logger.warning(f"Repository {repo_key} not found in config")
                    return True  # Already removed
                
            except Exception as e:
                logger.error(f"Failed to remove repository {owner}/{repo}: {e}")
                return False
    
    def enable_plugin(self, repo: str, plugin_name: str) -> bool:
        """Add plugin to enabledPlugins in settings.json.
        
        Args:
            repo: Repository key (owner/repo format)
            plugin_name: Name of plugin to enable
            
        Returns:
            True if plugin was enabled successfully
        """
        with self._lock:
            try:
                # Load settings
                settings = self._load_settings()
                
                # Initialize enabledPlugins if not present
                if "enabledPlugins" not in settings:
                    settings["enabledPlugins"] = {}
                
                # Add plugin to repository's enabled list
                if repo not in settings["enabledPlugins"]:
                    settings["enabledPlugins"][repo] = []
                
                if plugin_name not in settings["enabledPlugins"][repo]:
                    settings["enabledPlugins"][repo].append(plugin_name)
                    
                    # Save settings atomically
                    return self._save_settings(settings)
                else:
                    logger.info(f"Plugin {plugin_name} already enabled for {repo}")
                    return True
                
            except Exception as e:
                logger.error(f"Failed to enable plugin {plugin_name} for {repo}: {e}")
                return False
    
    def disable_plugin(self, repo: str, plugin_name: str) -> bool:
        """Remove plugin from enabledPlugins in settings.json.
        
        Args:
            repo: Repository key (owner/repo format)
            plugin_name: Name of plugin to disable
            
        Returns:
            True if plugin was disabled successfully
        """
        with self._lock:
            try:
                # Load settings
                settings = self._load_settings()
                
                if ("enabledPlugins" in settings and 
                    repo in settings["enabledPlugins"] and 
                    plugin_name in settings["enabledPlugins"][repo]):
                    
                    # Create backup before modification
                    backup_info = self.backup_config(self.settings_path)
                    
                    # Remove plugin
                    settings["enabledPlugins"][repo].remove(plugin_name)
                    
                    # Clean up empty repository entries
                    if not settings["enabledPlugins"][repo]:
                        del settings["enabledPlugins"][repo]
                    
                    # Save settings atomically
                    if self._save_settings(settings):
                        logger.info(f"Plugin {plugin_name} disabled for {repo}")
                        return True
                    else:
                        # Rollback on save failure
                        self.restore_config(backup_info.backup_path)
                        return False
                else:
                    logger.warning(f"Plugin {plugin_name} not enabled for {repo}")
                    return True  # Already disabled
                
            except Exception as e:
                logger.error(f"Failed to disable plugin {plugin_name} for {repo}: {e}")
                return False
    
    def install_repository(self, plugin_spec) -> bool:
        """Install a plugin repository from specification.
        
        Args:
            plugin_spec: PluginSpec object with repository details
            
        Returns:
            True if installation succeeded
        """
        try:
            repo_key = plugin_spec.get_repo_key()
            owner, repo = repo_key.split("/", 1)
            
            # Create repository metadata
            metadata = {
                "version": plugin_spec.get_version_specifier(),
                "lastUpdated": datetime.now().isoformat(),
                "plugins": plugin_spec.plugins.copy() if plugin_spec.plugins else []
            }
            
            # Add metadata from spec if present
            if plugin_spec.metadata:
                metadata.update(plugin_spec.metadata)
            
            # Add repository to config
            success = self.add_repository(owner, repo, metadata)
            
            if success:
                # Enable any specified plugins
                for plugin_name in plugin_spec.plugins:
                    self.enable_plugin(repo_key, plugin_name)
                
                logger.info(f"Installed repository: {repo_key}@{plugin_spec.get_version_specifier()}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to install repository {plugin_spec.repository}: {e}")
            return False
    
    def update_repository(self, repo_key: str, target_version: str) -> bool:
        """Update a repository to a specific version.
        
        Args:
            repo_key: Repository key in owner/repo format
            target_version: Target version to update to
            
        Returns:
            True if update succeeded
        """
        with self._lock:
            try:
                # Load current config
                config = self._load_plugin_config()
                
                if repo_key not in config.get("repositories", {}):
                    logger.error(f"Repository not found: {repo_key}")
                    return False
                
                # Update repository metadata
                repo_data = config["repositories"][repo_key]
                repo_data["version"] = target_version
                repo_data["lastUpdated"] = datetime.now().isoformat()
                
                # Save updated config
                success = self._save_plugin_config(config)
                
                if success:
                    logger.info(f"Updated repository {repo_key} to version {target_version}")
                
                return success
                
            except Exception as e:
                logger.error(f"Failed to update repository {repo_key}: {e}")
                return False
    
    def list_installed_repositories(self) -> Dict[str, Any]:
        """List all installed repositories with their metadata.
        
        Returns:
            Dictionary mapping repo_key to repository metadata
        """
        try:
            config = self._load_plugin_config()
            return config.get("repositories", {})
        except Exception as e:
            logger.error(f"Failed to list installed repositories: {e}")
            return {}
    
    def get_repository_info(self, repo_key: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific repository.
        
        Args:
            repo_key: Repository key in owner/repo format
            
        Returns:
            Repository metadata or None if not found
        """
        try:
            repositories = self.list_installed_repositories()
            return repositories.get(repo_key)
        except Exception as e:
            logger.error(f"Failed to get repository info for {repo_key}: {e}")
            return None
    
    def sync_team_config(self, pacc_config: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronize team configuration.
        
        Args:
            pacc_config: PACC team configuration
            
        Returns:
            Sync result with details
        """
        result = {
            "success": False,
            "installed_count": 0,
            "updated_count": 0,
            "failed_count": 0,
            "errors": [],
            "warnings": []
        }
        
        with self._lock:
            try:
                # Extract plugin requirements from team config
                plugins = pacc_config.get("plugins", {})
                
                for repo_key, plugin_list in plugins.items():
                    try:
                        # Parse owner/repo
                        if "/" not in repo_key:
                            result["errors"].append(f"Invalid repository format: {repo_key}")
                            result["failed_count"] += 1
                            continue
                        
                        owner, repo = repo_key.split("/", 1)
                        
                        # Add repository if not present
                        current_config = self._load_plugin_config()
                        if repo_key not in current_config.get("repositories", {}):
                            if self.add_repository(owner, repo):
                                result["installed_count"] += 1
                            else:
                                result["errors"].append(f"Failed to add repository: {repo_key}")
                                result["failed_count"] += 1
                                continue
                        else:
                            result["updated_count"] += 1
                        
                        # Enable specified plugins
                        for plugin_name in plugin_list:
                            if not self.enable_plugin(repo_key, plugin_name):
                                result["warnings"].append(f"Failed to enable plugin: {plugin_name}")
                    
                    except Exception as e:
                        result["errors"].append(f"Error processing {repo_key}: {e}")
                        result["failed_count"] += 1
                
                # Set success if no errors
                result["success"] = len(result["errors"]) == 0
                
            except Exception as e:
                result["errors"].append(f"Team config sync failed: {e}")
        
        return result
    
    def backup_config(self, file_path: Path) -> BackupInfo:
        """Create timestamped backup of configuration file.
        
        Args:
            file_path: Path to configuration file
            
        Returns:
            BackupInfo with backup details
        """
        return self.backup_manager.create_backup(file_path)
    
    def restore_config(self, backup_path: Path) -> bool:
        """Restore configuration from backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if restoration succeeded
        """
        # Find backup info
        for backup_info in self.backup_manager.list_backups():
            if backup_info.backup_path == backup_path:
                return self.backup_manager.restore_backup(backup_info)
        
        # If backup info not found, try direct restoration
        logger.warning(f"Backup metadata not found for {backup_path}, attempting direct restore")
        
        # Determine original path from backup filename
        # Backup files are named like: config.json.20241201_143022_123.backup
        backup_name = backup_path.name
        if ".backup" in backup_name:
            original_name = backup_name.split(".backup")[0]
            # Remove timestamp part
            parts = original_name.split(".")
            if len(parts) >= 3 and parts[-2].replace("_", "").isdigit():
                original_name = ".".join(parts[:-2]) + "." + parts[-1]
            
            # Determine target path based on filename
            if original_name == "config.json":
                target_path = self.config_path
            elif original_name == "settings.json":
                target_path = self.settings_path
            else:
                logger.error(f"Cannot determine target path for backup: {backup_path}")
                return False
            
            try:
                shutil.copy2(backup_path, target_path)
                logger.info(f"Restored {target_path} from {backup_path}")
                return True
            except OSError as e:
                logger.error(f"Failed to restore {target_path}: {e}")
                return False
        
        logger.error(f"Invalid backup filename format: {backup_path}")
        return False
    
    def validate_config(self, config_data: Dict[str, Any]) -> ValidationResult:
        """Validate configuration structure.
        
        Args:
            config_data: Configuration data to validate
            
        Returns:
            ValidationResult with validation details
        """
        # For now, just validate JSON structure
        # Can be extended with schema validation
        
        if not isinstance(config_data, dict):
            result = ValidationResult(
                is_valid=False,
                file_path=None,
                validator_name="PluginConfigValidator",
                metadata={}
            )
            result.add_error("Configuration must be a JSON object", rule_id="INVALID_TYPE")
            return result
        
        return ValidationResult(
            is_valid=True,
            file_path=None,
            validator_name="PluginConfigValidator",
            metadata={"structure": "valid"}
        )
    
    @contextmanager
    def transaction(self):
        """Context manager for multi-file configuration transactions.
        
        Example:
            with config_manager.transaction():
                config_manager.add_repository("owner", "repo")
                config_manager.enable_plugin("owner/repo", "plugin1")
        """
        # Create backups before transaction
        backups = []
        
        try:
            # Backup all relevant config files
            for config_file in [self.config_path, self.settings_path]:
                if config_file.exists():
                    backup_info = self.backup_config(config_file)
                    backups.append(backup_info)
            
            yield self
            
            # Transaction completed successfully - clean up backups
            for backup_info in backups:
                try:
                    if backup_info.backup_path.exists():
                        backup_info.backup_path.unlink()
                    metadata_file = backup_info.backup_path.with_suffix(".backup.meta")
                    if metadata_file.exists():
                        metadata_file.unlink()
                except OSError as e:
                    logger.warning(f"Failed to clean up backup: {e}")
                    
        except Exception as e:
            # Transaction failed - restore all backups
            logger.error(f"Transaction failed, rolling back: {e}")
            
            for backup_info in backups:
                if not self.backup_manager.restore_backup(backup_info, verify_checksum=False):
                    logger.error(f"Failed to rollback {backup_info.original_path}")
            
            raise
    
    def _load_plugin_config(self) -> Dict[str, Any]:
        """Load plugin configuration from config.json with caching.
        
        Returns:
            Plugin configuration dictionary
        """
        config_key = str(self.config_path)
        
        if not self.config_path.exists():
            return {"repositories": {}}
        
        try:
            # Check cache first
            current_mtime = self.config_path.stat().st_mtime
            if (config_key in self._config_cache and 
                self._config_mtime.get(config_key, 0) >= current_mtime):
                logger.debug(f"Using cached config for {self.config_path}")
                return deepcopy(self._config_cache[config_key])
            
            # Load from file
            with open(self.config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validate JSON
            validation_result = self.json_validator.validate_content(content, self.config_path)
            if not validation_result.is_valid:
                raise ConfigurationError(f"Invalid JSON in {self.config_path}")
            
            config = json.loads(content)
            
            # Ensure basic structure
            if "repositories" not in config:
                config["repositories"] = {}
            
            # Update cache
            self._config_cache[config_key] = deepcopy(config)
            self._config_mtime[config_key] = current_mtime
            logger.debug(f"Cached config for {self.config_path}")
            
            return config
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in {self.config_path}: {e}")
        except OSError as e:
            raise ConfigurationError(f"Cannot read {self.config_path}: {e}")
    
    def _save_plugin_config(self, config: Dict[str, Any]) -> bool:
        """Save plugin configuration to config.json atomically.
        
        Args:
            config: Configuration to save
            
        Returns:
            True if save succeeded
        """
        try:
            # Validate configuration
            validation_result = self.validate_config(config)
            if not validation_result.is_valid:
                logger.error(f"Invalid configuration: {validation_result.errors}")
                return False
            
            # Write atomically
            writer = AtomicFileWriter(self.config_path, create_backup=True)
            writer.write_json(config, indent=2)
            
            # Invalidate cache
            config_key = str(self.config_path)
            if config_key in self._config_cache:
                del self._config_cache[config_key]
                del self._config_mtime[config_key]
            
            logger.debug(f"Saved plugin configuration to {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save plugin configuration: {e}")
            return False
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load Claude settings from settings.json with caching.
        
        Returns:
            Settings dictionary
        """
        if not self.settings_path.exists():
            return {}
        
        try:
            # Check cache first
            current_mtime = self.settings_path.stat().st_mtime
            if (self._settings_cache is not None and 
                self._settings_mtime >= current_mtime):
                logger.debug(f"Using cached settings for {self.settings_path}")
                return deepcopy(self._settings_cache)
            
            # Load from file
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validate JSON
            validation_result = self.json_validator.validate_content(content, self.settings_path)
            if not validation_result.is_valid:
                raise ConfigurationError(f"Invalid JSON in {self.settings_path}")
            
            settings = json.loads(content)
            
            # Update cache
            self._settings_cache = deepcopy(settings)
            self._settings_mtime = current_mtime
            logger.debug(f"Cached settings for {self.settings_path}")
            
            return settings
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in {self.settings_path}: {e}")
        except OSError as e:
            raise ConfigurationError(f"Cannot read {self.settings_path}: {e}")
    
    def _save_settings(self, settings: Dict[str, Any]) -> bool:
        """Save Claude settings to settings.json atomically.
        
        Args:
            settings: Settings to save
            
        Returns:
            True if save succeeded
        """
        try:
            # Write atomically
            writer = AtomicFileWriter(self.settings_path, create_backup=True)
            writer.write_json(settings, indent=2)
            
            # Invalidate cache
            self._settings_cache = None
            self._settings_mtime = 0
            
            logger.debug(f"Saved settings to {self.settings_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False