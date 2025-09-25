"""Comprehensive tests for plugin configuration management system."""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

from pacc.errors.exceptions import ConfigurationError
from pacc.plugins.config import AtomicFileWriter, ConfigBackup, PluginConfigManager


class TestAtomicFileWriter:
    """Test atomic file write operations."""

    def test_atomic_write_json_success(self, tmp_path):
        """Test successful atomic JSON write."""
        target_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42}

        writer = AtomicFileWriter(target_file)
        writer.write_json(test_data)

        # Verify file exists and contains correct data
        assert target_file.exists()
        with open(target_file) as f:
            loaded_data = json.load(f)
        assert loaded_data == test_data

    def test_atomic_write_context_success(self, tmp_path):
        """Test successful atomic write using context manager."""
        target_file = tmp_path / "test.json"
        test_data = {"context": "manager", "test": True}

        writer = AtomicFileWriter(target_file)

        with writer.write_context() as temp_path:
            with open(temp_path, "w") as f:
                json.dump(test_data, f, indent=2)

        # Verify final file
        assert target_file.exists()
        with open(target_file) as f:
            loaded_data = json.load(f)
        assert loaded_data == test_data

    def test_atomic_write_with_backup(self, tmp_path):
        """Test atomic write creates backup of existing file."""
        target_file = tmp_path / "existing.json"

        # Create existing file
        original_data = {"original": "data"}
        with open(target_file, "w") as f:
            json.dump(original_data, f)

        # Overwrite with new data
        new_data = {"new": "data"}
        writer = AtomicFileWriter(target_file, create_backup=True)
        writer.write_json(new_data)

        # Verify new data is in target file
        with open(target_file) as f:
            loaded_data = json.load(f)
        assert loaded_data == new_data

        # Backup should have been cleaned up on success
        backup_files = list(tmp_path.glob("*.backup.*"))
        assert len(backup_files) == 0

    def test_atomic_write_rollback_on_failure(self, tmp_path):
        """Test rollback occurs when write fails."""
        target_file = tmp_path / "test.json"

        # Create existing file
        original_data = {"original": "content"}
        with open(target_file, "w") as f:
            json.dump(original_data, f)

        writer = AtomicFileWriter(target_file, create_backup=True)

        # Simulate failure during write
        with pytest.raises(ConfigurationError):
            with writer.write_context() as temp_path:
                # Write invalid content that will cause issues
                with open(temp_path, "w") as f:
                    f.write("invalid json content")
                # Simulate failure by removing temp file
                temp_path.unlink()

        # Original file should still exist with original content
        assert target_file.exists()
        with open(target_file) as f:
            loaded_data = json.load(f)
        assert loaded_data == original_data

    def test_atomic_write_no_backup_option(self, tmp_path):
        """Test atomic write without backup creation."""
        target_file = tmp_path / "test.json"

        # Create existing file
        with open(target_file, "w") as f:
            json.dump({"existing": "data"}, f)

        # Write without backup
        writer = AtomicFileWriter(target_file, create_backup=False)
        writer.write_json({"new": "data"})

        # No backup files should exist
        backup_files = list(tmp_path.glob("*.backup*"))
        assert len(backup_files) == 0


class TestConfigBackup:
    """Test configuration backup management."""

    def test_create_backup_success(self, tmp_path):
        """Test successful backup creation."""
        config_file = tmp_path / "config.json"
        config_data = {"test": "data", "timestamp": "2024-01-01"}

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        backup_manager = ConfigBackup(tmp_path / "backups")
        backup_info = backup_manager.create_backup(config_file)

        # Verify backup info
        assert backup_info.original_path == config_file
        assert backup_info.backup_path.exists()
        assert backup_info.checksum is not None
        assert isinstance(backup_info.timestamp, datetime)

        # Verify backup content
        with open(backup_info.backup_path) as f:
            backup_data = json.load(f)
        assert backup_data == config_data

        # Verify metadata file exists
        metadata_file = backup_info.backup_path.with_suffix(".backup.meta")
        assert metadata_file.exists()

    def test_create_backup_with_metadata(self, tmp_path):
        """Test backup creation with custom metadata."""
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump({"data": "test"}, f)

        custom_metadata = {"user": "test", "reason": "before_update"}

        backup_manager = ConfigBackup(tmp_path / "backups")
        backup_info = backup_manager.create_backup(config_file, custom_metadata)

        assert backup_info.metadata == custom_metadata

    def test_restore_backup_success(self, tmp_path):
        """Test successful backup restoration."""
        config_file = tmp_path / "config.json"
        original_data = {"original": "content"}

        # Create original file and backup
        with open(config_file, "w") as f:
            json.dump(original_data, f)

        backup_manager = ConfigBackup(tmp_path / "backups")
        backup_info = backup_manager.create_backup(config_file)

        # Modify original file
        modified_data = {"modified": "content"}
        with open(config_file, "w") as f:
            json.dump(modified_data, f)

        # Restore backup
        success = backup_manager.restore_backup(backup_info)
        assert success

        # Verify restoration
        with open(config_file) as f:
            restored_data = json.load(f)
        assert restored_data == original_data

    def test_restore_backup_checksum_verification(self, tmp_path):
        """Test backup restoration with checksum verification."""
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump({"test": "data"}, f)

        backup_manager = ConfigBackup(tmp_path / "backups")
        backup_info = backup_manager.create_backup(config_file)

        # Corrupt the backup file
        with open(backup_info.backup_path, "w") as f:
            f.write("corrupted content")

        # Restoration should fail due to checksum mismatch
        success = backup_manager.restore_backup(backup_info, verify_checksum=True)
        assert not success

    def test_list_backups(self, tmp_path):
        """Test listing available backups."""
        config_file1 = tmp_path / "config1.json"
        config_file2 = tmp_path / "config2.json"

        with open(config_file1, "w") as f:
            json.dump({"file": "1"}, f)
        with open(config_file2, "w") as f:
            json.dump({"file": "2"}, f)

        backup_manager = ConfigBackup(tmp_path / "backups")

        # Create multiple backups
        backup1 = backup_manager.create_backup(config_file1)
        backup2 = backup_manager.create_backup(config_file2)
        backup3 = backup_manager.create_backup(config_file1)  # Second backup of file1

        # List all backups
        all_backups = backup_manager.list_backups()
        assert len(all_backups) == 3

        # List backups for specific file
        file1_backups = backup_manager.list_backups(config_file1)
        assert len(file1_backups) == 2

        file2_backups = backup_manager.list_backups(config_file2)
        assert len(file2_backups) == 1

    def test_cleanup_old_backups(self, tmp_path):
        """Test cleanup of old backup files."""
        config_file = tmp_path / "config.json"
        with open(config_file, "w") as f:
            json.dump({"test": "data"}, f)

        backup_manager = ConfigBackup(tmp_path / "backups")

        # Create multiple backups (simulating different timestamps)
        backups = []
        for i in range(5):
            backup_info = backup_manager.create_backup(config_file)
            backups.append(backup_info)

            # Simulate older timestamps by modifying metadata
            metadata_file = backup_info.backup_path.with_suffix(".backup.meta")
            with open(metadata_file) as f:
                metadata = json.load(f)

            # Make older backups by subtracting days
            from datetime import timedelta

            old_timestamp = datetime.now() - timedelta(days=(i * 10))
            metadata["timestamp"] = old_timestamp.isoformat()

            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)

        # Cleanup should remove old backups
        removed_count = backup_manager.cleanup_old_backups(keep_count=2, max_age_days=15)

        # Should have removed some backups
        assert removed_count > 0

        # Should have at most 2 backups remaining
        remaining_backups = backup_manager.list_backups(config_file)
        assert len(remaining_backups) <= 2


class TestPluginConfigManager:
    """Test main plugin configuration manager."""

    @pytest.fixture
    def config_manager(self, tmp_path):
        """Create configured plugin config manager for testing."""
        plugins_dir = tmp_path / "plugins"
        settings_path = tmp_path / "settings.json"

        return PluginConfigManager(plugins_dir=plugins_dir, settings_path=settings_path)

    def test_add_repository_success(self, config_manager):
        """Test successful repository addition."""
        success = config_manager.add_repository("owner", "repo")
        assert success

        # Verify config file was created and contains repository
        config = config_manager._load_plugin_config()
        assert "repositories" in config
        assert "owner/repo" in config["repositories"]

        repo_entry = config["repositories"]["owner/repo"]
        assert "lastUpdated" in repo_entry
        assert "plugins" in repo_entry

    def test_add_repository_with_metadata(self, config_manager):
        """Test repository addition with custom metadata."""
        metadata = {
            "commitSha": "abc123",
            "plugins": ["plugin1", "plugin2"],
            "description": "Test repository",
        }

        success = config_manager.add_repository("owner", "repo", metadata)
        assert success

        config = config_manager._load_plugin_config()
        repo_entry = config["repositories"]["owner/repo"]

        assert repo_entry["commitSha"] == "abc123"
        assert repo_entry["plugins"] == ["plugin1", "plugin2"]
        assert repo_entry["description"] == "Test repository"
        assert "lastUpdated" in repo_entry  # Should be added automatically

    def test_remove_repository_success(self, config_manager):
        """Test successful repository removal."""
        # Add repository first
        config_manager.add_repository("owner", "repo")

        # Remove it
        success = config_manager.remove_repository("owner", "repo")
        assert success

        # Verify removal
        config = config_manager._load_plugin_config()
        assert "owner/repo" not in config.get("repositories", {})

    def test_remove_nonexistent_repository(self, config_manager):
        """Test removing non-existent repository."""
        success = config_manager.remove_repository("owner", "nonexistent")
        assert success  # Should succeed (already removed)

    def test_enable_plugin_success(self, config_manager):
        """Test successful plugin enablement."""
        success = config_manager.enable_plugin("owner/repo", "plugin1")
        assert success

        # Verify settings
        settings = config_manager._load_settings()
        assert "enabledPlugins" in settings
        assert "owner/repo" in settings["enabledPlugins"]
        assert "plugin1" in settings["enabledPlugins"]["owner/repo"]

    def test_enable_plugin_duplicate(self, config_manager):
        """Test enabling already enabled plugin."""
        # Enable plugin first time
        config_manager.enable_plugin("owner/repo", "plugin1")

        # Enable again - should succeed without duplicating
        success = config_manager.enable_plugin("owner/repo", "plugin1")
        assert success

        settings = config_manager._load_settings()
        plugin_list = settings["enabledPlugins"]["owner/repo"]
        assert plugin_list.count("plugin1") == 1

    def test_disable_plugin_success(self, config_manager):
        """Test successful plugin disabling."""
        # Enable plugin first
        config_manager.enable_plugin("owner/repo", "plugin1")
        config_manager.enable_plugin("owner/repo", "plugin2")

        # Disable one plugin
        success = config_manager.disable_plugin("owner/repo", "plugin1")
        assert success

        # Verify only plugin2 remains enabled
        settings = config_manager._load_settings()
        enabled_plugins = settings["enabledPlugins"]["owner/repo"]
        assert "plugin1" not in enabled_plugins
        assert "plugin2" in enabled_plugins

    def test_disable_last_plugin_cleans_repo_entry(self, config_manager):
        """Test disabling last plugin removes repository entry."""
        # Enable single plugin
        config_manager.enable_plugin("owner/repo", "plugin1")

        # Disable it
        success = config_manager.disable_plugin("owner/repo", "plugin1")
        assert success

        # Repository entry should be removed
        settings = config_manager._load_settings()
        assert "owner/repo" not in settings.get("enabledPlugins", {})

    def test_disable_nonexistent_plugin(self, config_manager):
        """Test disabling non-existent plugin."""
        success = config_manager.disable_plugin("owner/repo", "nonexistent")
        assert success  # Should succeed (already disabled)

    def test_sync_team_config_success(self, config_manager):
        """Test successful team configuration sync."""
        team_config = {
            "plugins": {"owner1/repo1": ["plugin1", "plugin2"], "owner2/repo2": ["plugin3"]}
        }

        result = config_manager.sync_team_config(team_config)

        assert result["success"]
        assert result["installed_count"] == 2  # Two repositories
        assert len(result["errors"]) == 0

        # Verify repositories were added
        config = config_manager._load_plugin_config()
        assert "owner1/repo1" in config["repositories"]
        assert "owner2/repo2" in config["repositories"]

        # Verify plugins were enabled
        settings = config_manager._load_settings()
        enabled = settings["enabledPlugins"]
        assert enabled["owner1/repo1"] == ["plugin1", "plugin2"]
        assert enabled["owner2/repo2"] == ["plugin3"]

    def test_sync_team_config_invalid_repo_format(self, config_manager):
        """Test team config sync with invalid repository format."""
        team_config = {"plugins": {"invalid-format": ["plugin1"], "owner/repo": ["plugin2"]}}

        result = config_manager.sync_team_config(team_config)

        assert not result["success"]
        assert result["failed_count"] == 1
        assert result["installed_count"] == 1  # Valid repo should still be processed
        assert len(result["errors"]) == 1
        assert "Invalid repository format" in result["errors"][0]

    def test_backup_and_restore_config(self, config_manager):
        """Test configuration backup and restoration."""
        # Add some configuration
        config_manager.add_repository("owner", "repo")
        config_manager.enable_plugin("owner/repo", "plugin1")

        # Create backup
        backup_info = config_manager.backup_config(config_manager.config_path)
        assert backup_info.backup_path.exists()

        # Modify configuration
        config_manager.remove_repository("owner", "repo")

        # Restore from backup
        success = config_manager.restore_config(backup_info.backup_path)
        assert success

        # Verify restoration
        config = config_manager._load_plugin_config()
        assert "owner/repo" in config["repositories"]

    def test_validate_config_valid(self, config_manager):
        """Test validation of valid configuration."""
        valid_config = {
            "repositories": {
                "owner/repo": {"lastUpdated": "2024-01-01T12:00:00", "plugins": ["plugin1"]}
            }
        }

        result = config_manager.validate_config(valid_config)
        assert result.is_valid
        assert result.error_count == 0

    def test_validate_config_invalid(self, config_manager):
        """Test validation of invalid configuration."""
        invalid_config = "not a dict"

        result = config_manager.validate_config(invalid_config)
        assert not result.is_valid
        assert result.error_count > 0
        assert any(
            "JSON object" in issue.message for issue in result.issues if issue.severity == "error"
        )

    def test_transaction_success(self, config_manager):
        """Test successful transaction."""
        with config_manager.transaction():
            config_manager.add_repository("owner", "repo")
            config_manager.enable_plugin("owner/repo", "plugin1")

        # Verify all changes were applied
        config = config_manager._load_plugin_config()
        assert "owner/repo" in config["repositories"]

        settings = config_manager._load_settings()
        assert "plugin1" in settings["enabledPlugins"]["owner/repo"]

    def test_transaction_rollback_on_failure(self, config_manager):
        """Test transaction rollback on failure."""
        # Create initial state
        config_manager.add_repository("existing", "repo")

        original_config = config_manager._load_plugin_config()

        # Transaction that fails
        with pytest.raises(Exception):
            with config_manager.transaction():
                config_manager.add_repository("new", "repo")

                # Simulate failure
                raise Exception("Simulated failure")

        # Configuration should be rolled back
        current_config = config_manager._load_plugin_config()
        assert current_config == original_config
        assert "new/repo" not in current_config["repositories"]

    def test_concurrent_access_thread_safety(self, config_manager):
        """Test thread safety of concurrent configuration access."""
        import threading
        import time

        results = []
        errors = []

        def add_repository(owner, repo):
            try:
                time.sleep(0.01)  # Small delay to increase chance of race conditions
                success = config_manager.add_repository(owner, repo)
                results.append(success)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=add_repository, args=(f"owner{i}", f"repo{i}"))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All operations should succeed
        assert len(errors) == 0
        assert all(results)

        # All repositories should be present
        config = config_manager._load_plugin_config()
        for i in range(10):
            assert f"owner{i}/repo{i}" in config["repositories"]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_config_manager_with_readonly_directory(self, tmp_path):
        """Test behavior with read-only directories."""
        plugins_dir = tmp_path / "readonly_plugins"
        plugins_dir.mkdir()

        # Make directory read-only (platform-specific)
        import stat

        plugins_dir.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        try:
            # Should raise an exception during initialization due to permission error
            with pytest.raises(PermissionError):
                config_manager = PluginConfigManager(plugins_dir=plugins_dir)

        finally:
            # Restore write permissions for cleanup
            plugins_dir.chmod(stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

    def test_corrupted_config_file_handling(self, tmp_path):
        """Test handling of corrupted configuration files."""
        config_file = tmp_path / "plugins" / "config.json"
        config_file.parent.mkdir(parents=True)

        # Create corrupted JSON file
        with open(config_file, "w") as f:
            f.write('{"invalid": json content}')

        config_manager = PluginConfigManager(plugins_dir=config_file.parent)

        # Should handle corrupted file gracefully
        with pytest.raises(ConfigurationError):
            config_manager._load_plugin_config()

    def test_disk_full_simulation(self, tmp_path):
        """Test behavior when disk is full (simulated)."""
        config_manager = PluginConfigManager(plugins_dir=tmp_path / "plugins")

        # Mock open to simulate disk full
        original_open = open

        def mock_open(*args, **kwargs):
            if "w" in str(args[1]) if len(args) > 1 else kwargs.get("mode", ""):
                raise OSError("No space left on device")
            return original_open(*args, **kwargs)

        with patch("builtins.open", side_effect=mock_open):
            success = config_manager.add_repository("owner", "repo")
            assert not success

    def test_large_configuration_performance(self, tmp_path):
        """Test performance with large configuration."""
        config_manager = PluginConfigManager(
            plugins_dir=tmp_path / "plugins", settings_path=tmp_path / "settings.json"
        )
        # Add many repositories
        for i in range(100):
            success = config_manager.add_repository(f"owner{i}", f"repo{i}")
            assert success

        # Enable many plugins
        for i in range(100):
            for j in range(5):
                success = config_manager.enable_plugin(f"owner{i}/repo{i}", f"plugin{j}")
                assert success

        # Operations should still be fast
        import time

        start_time = time.time()

        config = config_manager._load_plugin_config()
        settings = config_manager._load_settings()

        end_time = time.time()

        # Should complete in reasonable time (less than 1 second)
        assert end_time - start_time < 1.0

        # Verify large configuration is intact
        assert len(config["repositories"]) == 100
        assert len(settings["enabledPlugins"]) == 100


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
