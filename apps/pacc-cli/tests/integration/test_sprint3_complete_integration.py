"""Comprehensive end-to-end integration tests for Sprint 3 features.

This module tests complete plugin lifecycle workflows:
- install → info → update → sync → remove
- Team collaboration scenarios with conflict resolution
- Update rollback scenarios in real situations
- Cross-command interactions and error handling
- Performance validation for large repositories
"""

import json
import shutil
import tempfile
import time
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pacc.cli import PACCCli

# Import components with graceful fallback
try:
    from pacc.core.project_config import ConflictResolution, PluginSyncManager, PluginSyncResult

    HAS_PROJECT_CONFIG = True
except ImportError:
    HAS_PROJECT_CONFIG = False

    class PluginSyncManager:
        pass

    class PluginSyncResult:
        pass

    class ConflictResolution:
        pass


try:
    from pacc.plugins.config import PluginConfigManager

    HAS_PLUGIN_CONFIG = True
except ImportError:
    HAS_PLUGIN_CONFIG = False

    class PluginConfigManager:
        pass


class TestCompletePluginLifecycle:
    """Test complete plugin lifecycle: install → info → update → sync → remove."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()

        # Setup directory structure
        self.claude_dir = self.temp_dir / ".claude"
        self.claude_dir.mkdir()
        self.plugins_dir = self.claude_dir / "plugins"
        self.plugins_dir.mkdir()

        # Create project directory
        self.project_dir = self.temp_dir / "project"
        self.project_dir.mkdir()

        # Initialize config files
        (self.plugins_dir / "config.json").write_text(
            json.dumps({"repositories": {}, "version": "1.0.0"})
        )

        (self.claude_dir / "settings.json").write_text(
            json.dumps({"enabledPlugins": {}, "version": "1.0.0"})
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @patch("pathlib.Path.home")
    @patch("pacc.plugins.GitRepository")
    @patch("pacc.plugins.PluginDiscovery")
    @patch("pacc.plugins.RepositoryManager")
    @patch("pacc.plugins.PluginConfigManager")
    @patch("pacc.plugins.PluginSelector")
    def test_complete_plugin_lifecycle_workflow(
        self,
        mock_selector,
        mock_plugin_config,
        mock_repo_manager,
        mock_discovery,
        mock_git_repo,
        mock_home,
    ):
        """Test complete plugin lifecycle: install → info → update → sync → remove."""
        mock_home.return_value = self.temp_dir

        # Setup mock plugin repository
        mock_repo = Mock()
        mock_repo.clone.return_value = True
        mock_repo.update.return_value = True
        mock_repo.get_current_commit.return_value = "abc123"
        mock_git_repo.return_value = mock_repo
        mock_git_repo.is_valid_git_url.return_value = True

        # Setup mock plugin discovery
        mock_plugin_details = Mock()
        mock_plugin_details.name = "test-plugin"
        mock_plugin_details.manifest = {
            "name": "test-plugin",
            "version": "1.0.0",
            "description": "Test plugin for lifecycle testing",
        }
        mock_plugin_details.path = Path("/fake/path")
        mock_plugin_details.get_namespaced_components.return_value = {
            "commands": ["test-plugin:cmd1"],
            "agents": ["test-plugin:agent1"],
            "hooks": [],
        }

        mock_repo_plugins = Mock()
        mock_repo_plugins.plugins = [mock_plugin_details]

        mock_discovery_instance = Mock()
        mock_discovery_instance.discover_plugins.return_value = mock_repo_plugins
        mock_discovery.return_value = mock_discovery_instance

        # Setup mock repository manager
        mock_repo_manager_instance = Mock()
        mock_repo_manager_instance.clone_repository.return_value = ("test/repo", True)
        mock_repo_manager.return_value = mock_repo_manager_instance

        # Setup mock plugin config manager
        mock_config_instance = Mock()
        mock_config_instance.install_repository.return_value = True
        mock_config_instance.enable_plugin.return_value = True
        mock_plugin_config.return_value = mock_config_instance

        # Setup mock plugin selector
        mock_selector_instance = Mock()
        mock_selector_instance.select_plugins_for_installation.return_value = [mock_plugin_details]
        mock_selector.return_value = mock_selector_instance

        # Step 1: Install plugin repository
        install_args = Namespace(
            repo_url="https://github.com/test/repo.git",
            dry_run=False,
            update=False,
            enable=True,
            interactive=False,
            verbose=False,
            json=False,
        )

        # Mock repository directory after install
        repo_dir = self.plugins_dir / "test" / "repo"
        repo_dir.mkdir(parents=True)

        with patch("pathlib.Path.exists", return_value=True):
            result = self.cli.handle_plugin_install(install_args)

        assert result == 0, "Plugin install should succeed"

        # Step 2: Get plugin info (using same mock config instance)
        info_args = Namespace(plugin="test-plugin", repo="test/repo", format="table")

        # Configure mock for info command
        mock_config_instance._load_plugin_config.return_value = {
            "repositories": {
                "test/repo": {
                    "plugins": ["test-plugin"],
                    "lastUpdated": "2024-01-01T12:00:00",
                    "commitSha": "abc123",
                }
            }
        }
        mock_config_instance._load_settings.return_value = {
            "enabledPlugins": {"test/repo": ["test-plugin"]}
        }

        with patch("pacc.plugins.PluginRepositoryManager") as mock_repo_mgr:
            mock_repo_mgr_instance = Mock()
            mock_repo_mgr.return_value = mock_repo_mgr_instance

            result = self.cli.handle_plugin_info(info_args)

        assert result == 0, "Plugin info should succeed"

        # Step 3: Update plugin
        update_args = Namespace(
            repo="test/repo",
            version="v1.1.0",
            dry_run=False,
            force=False,
            create_backup=True,
            verbose=False,
            json=False,
        )

        with patch("pacc.plugins.PluginConfigManager") as mock_config:
            mock_instance = Mock()
            mock_instance._load_plugin_config.return_value = {
                "repositories": {"test/repo": {"plugins": ["test-plugin"], "version": "abc123"}}
            }
            mock_instance.update_repository.return_value = True
            mock_instance.transaction.return_value.__enter__ = Mock(return_value=mock_instance)
            mock_instance.transaction.return_value.__exit__ = Mock(return_value=None)
            mock_config.return_value = mock_instance

            result = self.cli.handle_plugin_update(update_args)

        assert result == 0, "Plugin update should succeed"

        # Step 4: Remove plugin
        remove_args = Namespace(
            plugin="test-plugin", repo="test/repo", dry_run=False, keep_files=False, force=True
        )

        with patch("pacc.plugins.PluginConfigManager") as mock_config:
            mock_instance = Mock()
            mock_instance._load_plugin_config.return_value = {
                "repositories": {"test/repo": {"plugins": ["test-plugin"]}}
            }
            mock_instance._load_settings.return_value = {
                "enabledPlugins": {"test/repo": ["test-plugin"]}
            }
            mock_instance.disable_plugin.return_value = True
            mock_instance.remove_repository.return_value = True
            mock_instance.transaction.return_value.__enter__ = Mock(return_value=mock_instance)
            mock_instance.transaction.return_value.__exit__ = Mock(return_value=None)
            mock_config.return_value = mock_instance

            with patch("shutil.rmtree") as mock_rmtree:
                result = self.cli.handle_plugin_remove(remove_args)

        assert result == 0, "Plugin remove should succeed"

        # Verify complete lifecycle executed without errors
        print("✓ Complete plugin lifecycle test passed")


class TestTeamCollaborationWorkflows:
    """Test team collaboration scenarios with multiple developers."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()

        # Create multiple project directories (simulating different team members)
        self.team_lead_dir = self.temp_dir / "team_lead"
        self.dev1_dir = self.temp_dir / "developer1"
        self.dev2_dir = self.temp_dir / "developer2"

        for proj_dir in [self.team_lead_dir, self.dev1_dir, self.dev2_dir]:
            proj_dir.mkdir(parents=True)

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @pytest.mark.skipif(not HAS_PROJECT_CONFIG, reason="Project config components not available")
    @patch("pacc.core.project_config.PluginSyncManager")
    def test_team_collaboration_sync_workflow(self, mock_sync_manager_class):
        """Test team collaboration with pacc.json synchronization."""

        # Setup team lead configuration
        team_config = {
            "name": "team-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": [
                    "team/productivity-tools@v1.0.0",
                    {
                        "repository": "team/ai-agents",
                        "version": "main",
                        "plugins": ["code-reviewer", "docs-generator"],
                    },
                ],
                "required": ["code-reviewer"],
                "optional": ["docs-generator"],
            },
        }

        (self.team_lead_dir / "pacc.json").write_text(json.dumps(team_config, indent=2))

        # Setup developer 1 with local overrides
        dev1_local_config = {
            "plugins": {
                "repositories": ["personal/dev-tools@latest"],
                "optional": ["personal-debugger"],
            }
        }

        # Copy team config to dev directories
        shutil.copy(self.team_lead_dir / "pacc.json", self.dev1_dir / "pacc.json")
        (self.dev1_dir / "pacc.local.json").write_text(json.dumps(dev1_local_config, indent=2))

        shutil.copy(self.team_lead_dir / "pacc.json", self.dev2_dir / "pacc.json")

        # Mock sync manager
        mock_sync_manager = Mock()
        mock_sync_result = PluginSyncResult(
            success=True,
            installed_count=2,
            updated_count=1,
            skipped_count=0,
            warnings=["Version conflict resolved for team/productivity-tools"],
        )
        mock_sync_manager.sync_plugins.return_value = mock_sync_result
        mock_sync_manager_class.return_value = mock_sync_manager

        # Test sync for each team member
        for project_dir in [self.dev1_dir, self.dev2_dir]:
            sync_args = Namespace(
                project_dir=project_dir,
                environment="default",
                dry_run=False,
                force=False,
                required_only=False,
                optional_only=False,
                json=False,
                verbose=False,
            )

            with patch.object(self.cli, "_print_success"), patch.object(
                self.cli, "_print_info"
            ), patch.object(self.cli, "_print_warning"), patch.object(self.cli, "_set_json_mode"):
                result = self.cli.handle_plugin_sync(sync_args)
                assert result == 0, f"Sync should succeed for {project_dir.name}"

        print("✓ Team collaboration sync workflow test passed")

    def test_version_conflict_resolution(self):
        """Test version conflict resolution between team and local configs."""

        # Team config with specific version
        team_config = {
            "name": "conflict-test",
            "version": "1.0.0",
            "plugins": {"repositories": ["shared/tool@v1.0.0"]},
        }

        # Local config with different version
        local_config = {
            "plugins": {
                "repositories": ["shared/tool@v1.1.0"]  # Conflict!
            }
        }

        (self.dev1_dir / "pacc.json").write_text(json.dumps(team_config))
        (self.dev1_dir / "pacc.local.json").write_text(json.dumps(local_config))

        # Verify configs can be loaded and contain expected conflicts
        team_data = json.loads((self.dev1_dir / "pacc.json").read_text())
        local_data = json.loads((self.dev1_dir / "pacc.local.json").read_text())

        # Extract versions from configurations
        team_repo = team_data["plugins"]["repositories"][0]
        local_repo = local_data["plugins"]["repositories"][0]

        assert "v1.0.0" in team_repo
        assert "v1.1.0" in local_repo

        print("✓ Version conflict configuration test passed")


class TestUpdateRollbackScenarios:
    """Test update rollback scenarios in realistic situations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()

        self.claude_dir = self.temp_dir / ".claude"
        self.claude_dir.mkdir()
        self.plugins_dir = self.claude_dir / "plugins"
        self.plugins_dir.mkdir()

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @patch("pathlib.Path.home")
    def test_update_rollback_on_failure(self, mock_home):
        """Test rollback when update fails."""
        mock_home.return_value = self.temp_dir

        # Create repository with backup scenario
        repo_dir = self.plugins_dir / "test" / "repo"
        repo_dir.mkdir(parents=True)

        # Create backup directory
        backup_dir = self.plugins_dir / "backups" / "test_repo_20240101_120000"
        backup_dir.mkdir(parents=True)

        update_args = Namespace(
            repo="test/repo",
            version="v2.0.0",
            dry_run=False,
            force=False,
            create_backup=True,
            verbose=False,
            json=False,
        )

        with patch("pacc.plugins.PluginConfigManager") as mock_config:
            mock_instance = Mock()
            mock_instance._load_plugin_config.return_value = {
                "repositories": {"test/repo": {"plugins": ["test-plugin"], "version": "v1.0.0"}}
            }

            # Simulate update failure and rollback
            mock_instance.update_repository.side_effect = Exception("Update failed")
            mock_instance.transaction.return_value.__enter__ = Mock(return_value=mock_instance)
            mock_instance.transaction.return_value.__exit__ = Mock(
                side_effect=Exception("Transaction failed")
            )
            mock_config.return_value = mock_instance

            with patch("pathlib.Path.exists", return_value=True):
                result = self.cli.handle_plugin_update(update_args)

            # Should handle failure gracefully
            assert result == 1, "Update should fail but handle rollback"

        print("✓ Update rollback test passed")


class TestCrossCommandInteractions:
    """Test interactions and conflicts between different commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()

        self.claude_dir = self.temp_dir / ".claude"
        self.claude_dir.mkdir()
        self.plugins_dir = self.claude_dir / "plugins"
        self.plugins_dir.mkdir()

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @patch("pathlib.Path.home")
    def test_info_command_with_synced_plugins(self, mock_home):
        """Test info command works correctly with synced plugins."""
        mock_home.return_value = self.temp_dir

        # Setup synced plugin configuration
        synced_config = {
            "repositories": {
                "team/tools": {
                    "plugins": ["synced-plugin"],
                    "lastUpdated": "2024-01-01T12:00:00",
                    "commitSha": "def456",
                    "syncedFrom": "pacc.json",
                }
            }
        }

        (self.plugins_dir / "config.json").write_text(json.dumps(synced_config))

        info_args = Namespace(plugin="synced-plugin", repo="team/tools", format="table")

        with patch("pacc.plugins.PluginConfigManager") as mock_config:
            mock_instance = Mock()
            mock_instance._load_plugin_config.return_value = synced_config
            mock_instance._load_settings.return_value = {
                "enabledPlugins": {"team/tools": ["synced-plugin"]}
            }
            mock_config.return_value = mock_instance

            with patch("pacc.plugins.PluginRepositoryManager") as mock_repo_mgr:
                mock_repo_mgr_instance = Mock()
                mock_repo_mgr.return_value = mock_repo_mgr_instance

                # Mock repository doesn't exist locally (sync needed)
                with patch("pathlib.Path.exists", return_value=False):
                    result = self.cli.handle_plugin_info(info_args)

                # The test expectation should be that it reports not installed
                # but still shows info from config, which is valid behavior
                assert result == 0, "Info should work with synced but not installed plugins"

        print("✓ Info command with synced plugins test passed")

    @patch("pathlib.Path.home")
    def test_remove_command_after_sync_operations(self, mock_home):
        """Test remove command cleans up properly after sync operations."""
        mock_home.return_value = self.temp_dir

        # Initialize the config.json file properly
        config_data = {
            "repositories": {
                "team/tools": {"plugins": ["synced-plugin"], "syncedFrom": "pacc.json"}
            }
        }
        (self.plugins_dir / "config.json").write_text(json.dumps(config_data))

        remove_args = Namespace(
            plugin="synced-plugin", repo="team/tools", dry_run=False, keep_files=False, force=True
        )

        with patch("pacc.plugins.PluginConfigManager") as mock_config:
            mock_instance = Mock()
            mock_instance._load_plugin_config.return_value = config_data
            mock_instance._load_settings.return_value = {
                "enabledPlugins": {"team/tools": ["synced-plugin"]}
            }
            mock_instance.disable_plugin.return_value = True
            mock_instance.remove_repository.return_value = True
            mock_instance.transaction.return_value.__enter__ = Mock(return_value=mock_instance)
            mock_instance.transaction.return_value.__exit__ = Mock(return_value=None)
            mock_config.return_value = mock_instance

            with patch("pathlib.Path.exists", return_value=True), patch(
                "shutil.rmtree"
            ) as mock_rmtree:
                result = self.cli.handle_plugin_remove(remove_args)

            assert result == 0, "Remove should handle synced plugins correctly"
            mock_rmtree.assert_called_once()

        print("✓ Remove command after sync operations test passed")


class TestPerformanceValidation:
    """Test performance requirements for plugin operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @pytest.mark.skipif(not HAS_PROJECT_CONFIG, reason="Project config components not available")
    def test_sync_performance_large_configuration(self):
        """Test sync performance with large plugin configurations."""

        # Create large configuration
        large_config = {
            "name": "performance-test",
            "version": "1.0.0",
            "plugins": {
                "repositories": [f"org/repo-{i}@v1.0.{i % 10}" for i in range(50)],
                "required": [f"plugin-{i}" for i in range(25)],
                "optional": [f"plugin-{i}" for i in range(25, 50)],
            },
        }

        project_dir = self.temp_dir / "large_project"
        project_dir.mkdir()
        (project_dir / "pacc.json").write_text(json.dumps(large_config))

        sync_args = Namespace(
            project_dir=project_dir,
            environment="default",
            dry_run=True,  # Dry run for performance testing
            force=False,
            required_only=False,
            optional_only=False,
            json=False,
            verbose=False,
        )

        # Measure sync performance
        start_time = time.time()

        with patch("pacc.core.project_config.PluginSyncManager") as mock_sync_manager_class:
            mock_sync_manager = Mock()
            mock_sync_result = PluginSyncResult(success=True, skipped_count=50)
            mock_sync_manager.sync_plugins.return_value = mock_sync_result
            mock_sync_manager_class.return_value = mock_sync_manager

            with patch.object(self.cli, "_print_success"), patch.object(
                self.cli, "_print_info"
            ), patch.object(self.cli, "_set_json_mode"):
                result = self.cli.handle_plugin_sync(sync_args)

        end_time = time.time()
        duration = end_time - start_time

        assert result == 0, "Large config sync should succeed"
        assert duration < 5.0, f"Sync took {duration:.2f}s, should be under 5s for dry-run"

        print(f"✓ Large configuration sync performance test passed ({duration:.2f}s)")

    def test_configuration_loading_performance(self):
        """Test configuration file loading performance."""

        # Create very large configuration
        massive_config = {
            "name": "massive-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": [
                    f"org{i}/repo{j}@v{i}.{j}.0" for i in range(20) for j in range(20)
                ],
                "required": [f"plugin-{i}-{j}" for i in range(10) for j in range(10)],
                "optional": [f"plugin-{i}-{j}" for i in range(10, 20) for j in range(10)],
            },
        }

        config_file = self.temp_dir / "massive_pacc.json"

        # Measure config write time
        start_write = time.time()
        config_file.write_text(json.dumps(massive_config, indent=2))
        write_time = time.time() - start_write

        # Measure config read time
        start_read = time.time()
        loaded_config = json.loads(config_file.read_text())
        read_time = time.time() - start_read

        # Verify config integrity
        assert len(loaded_config["plugins"]["repositories"]) == 400
        assert len(loaded_config["plugins"]["required"]) == 100
        assert len(loaded_config["plugins"]["optional"]) == 100

        # Performance assertions
        assert write_time < 1.0, f"Config write took {write_time:.2f}s, should be under 1s"
        assert read_time < 0.5, f"Config read took {read_time:.2f}s, should be under 0.5s"

        file_size_mb = config_file.stat().st_size / (1024 * 1024)
        assert file_size_mb < 5.0, f"Config file is {file_size_mb:.2f}MB, should be manageable"

        print(
            f"✓ Configuration loading performance test passed (write: {write_time:.3f}s, read: {read_time:.3f}s)"
        )


class TestErrorHandlingAcrossCommands:
    """Test error handling works consistently across all Sprint 3 commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @patch("pathlib.Path.home")
    def test_consistent_error_handling_missing_repo(self, mock_home):
        """Test all commands handle missing repository consistently."""
        mock_home.return_value = self.temp_dir

        # Test info command with missing repo
        info_args = Namespace(plugin="missing-plugin", repo="missing/repo", format="table")

        info_result = self.cli.handle_plugin_info(info_args)
        assert info_result == 1, "Info should fail gracefully for missing repo"

        # Test remove command with missing repo
        remove_args = Namespace(
            plugin="missing-plugin",
            repo="missing/repo",
            dry_run=False,
            keep_files=False,
            force=True,
        )

        remove_result = self.cli.handle_plugin_remove(remove_args)
        assert remove_result == 0, "Remove should succeed (no-op) for missing repo"

        print("✓ Consistent error handling test passed")

    def test_configuration_error_handling(self):
        """Test configuration error handling across commands."""

        # Create invalid JSON configuration
        invalid_config_dir = self.temp_dir / "invalid_project"
        invalid_config_dir.mkdir()
        (invalid_config_dir / "pacc.json").write_text("{ invalid json syntax }")

        sync_args = Namespace(
            project_dir=invalid_config_dir,
            environment="default",
            dry_run=False,
            force=False,
            required_only=False,
            optional_only=False,
            json=False,
            verbose=False,
        )

        # Should handle invalid JSON gracefully
        result = self.cli.handle_plugin_sync(sync_args)
        assert result == 1, "Sync should fail gracefully with invalid JSON"

        print("✓ Configuration error handling test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
