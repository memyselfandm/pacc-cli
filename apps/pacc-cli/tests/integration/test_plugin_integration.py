"""End-to-end integration tests for Claude Code plugin system.

This module tests complete workflows including:
- Install -> Discover -> Enable -> List workflows
- Multi-plugin repository handling
- Error scenarios and recovery
- Cross-component interactions
- Performance validation
- Configuration atomicity and rollback scenarios

These tests ensure all plugin components work together seamlessly.
"""

import json
import logging
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock, patch

import pytest

from pacc.cli import PACCCli
from pacc.errors.exceptions import ConfigurationError
from pacc.plugins.config import PluginConfigManager
from pacc.plugins.discovery import PluginScanner
from pacc.plugins.repository import PluginRepositoryManager

logger = logging.getLogger(__name__)


class TestPluginEndToEndWorkflows:
    """Test complete end-to-end plugin workflows."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.claude_dir = Path(self.temp_dir) / ".claude"
        self.plugins_dir = self.claude_dir / "plugins"
        self.repos_dir = self.plugins_dir / "repos"
        self.settings_path = self.claude_dir / "settings.json"
        self.config_path = self.plugins_dir / "config.json"

        # Create directory structure
        self.claude_dir.mkdir(parents=True, exist_ok=True)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.repos_dir.mkdir(parents=True, exist_ok=True)

        # Create minimal settings.json
        self.settings_path.write_text(json.dumps({}))

        # Initialize components
        self.config_manager = PluginConfigManager(
            plugins_dir=self.plugins_dir, settings_path=self.settings_path
        )
        self.repo_manager = PluginRepositoryManager(
            plugins_dir=self.plugins_dir, config_manager=self.config_manager
        )
        self.scanner = PluginScanner()

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_plugin_repo(self, owner: str, repo: str, plugins: List[Dict[str, Any]]) -> Path:
        """Create a test plugin repository structure.

        Args:
            owner: Repository owner
            repo: Repository name
            plugins: List of plugin configurations

        Returns:
            Path to created repository
        """
        repo_path = self.repos_dir / owner / repo
        repo_path.mkdir(parents=True, exist_ok=True)

        # Create .git directory to simulate git repo
        git_dir = repo_path / ".git"
        git_dir.mkdir(exist_ok=True)

        for plugin_config in plugins:
            plugin_name = plugin_config["name"]
            plugin_path = repo_path / plugin_name
            plugin_path.mkdir(exist_ok=True)

            # Create plugin.json manifest
            manifest = {
                "name": plugin_name,
                "version": plugin_config.get("version", "1.0.0"),
                "description": plugin_config.get("description", f"Test plugin {plugin_name}"),
                "author": {"name": "Test Author"},
            }

            manifest_path = plugin_path / "plugin.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))

            # Create components
            if plugin_config.get("commands"):
                commands_dir = plugin_path / "commands"
                commands_dir.mkdir(exist_ok=True)
                for cmd in plugin_config["commands"]:
                    cmd_path = commands_dir / f"{cmd}.md"
                    # Create parent directories for nested commands
                    cmd_path.parent.mkdir(parents=True, exist_ok=True)
                    cmd_content = f"""---
description: Test command {cmd}
---

This is a test command: {cmd}
"""
                    cmd_path.write_text(cmd_content)

            if plugin_config.get("agents"):
                agents_dir = plugin_path / "agents"
                agents_dir.mkdir(exist_ok=True)
                for agent in plugin_config["agents"]:
                    agent_path = agents_dir / f"{agent}.md"
                    # Create parent directories for nested agents
                    agent_path.parent.mkdir(parents=True, exist_ok=True)
                    agent_content = f"""---
name: {agent.title()} Agent
description: Test agent {agent}
tools: [Read, Write]
---

This is a test agent: {agent}
"""
                    agent_path.write_text(agent_content)

            if plugin_config.get("hooks"):
                hooks_dir = plugin_path / "hooks"
                hooks_dir.mkdir(exist_ok=True)
                hooks_path = hooks_dir / "hooks.json"
                hooks_content = {
                    "hooks": [
                        {
                            "type": "SessionStart",
                            "action": {
                                "command": f"echo 'Plugin {plugin_name} loaded'",
                                "timeout": 1000,
                            },
                        }
                    ]
                }
                hooks_path.write_text(json.dumps(hooks_content, indent=2))

        return repo_path

    def test_complete_install_discover_enable_list_workflow(self):
        """Test complete workflow: install -> discover -> enable -> list."""
        # Setup: Create test repository
        repo_path = self.create_test_plugin_repo(
            "testowner",
            "testrepo",
            [
                {
                    "name": "utility-plugin",
                    "commands": ["hello", "timestamp"],
                    "agents": ["helper"],
                    "hooks": True,
                },
                {"name": "dev-tools", "commands": ["lint", "test"], "version": "2.1.0"},
            ],
        )

        # Step 1: Mock repository installation (simulate git clone)
        with patch.object(self.repo_manager, "_get_current_commit_sha", return_value="abc123def"):
            # Manually add to config to simulate successful clone
            success = self.config_manager.add_repository(
                "testowner",
                "testrepo",
                {
                    "lastUpdated": "2025-08-18T10:00:00Z",
                    "commitSha": "abc123def",
                    "plugins": ["utility-plugin", "dev-tools"],
                    "url": "https://github.com/testowner/testrepo",
                },
            )
            assert success, "Failed to add repository to config"

            # Step 2: Discover plugins in repository
            repo_info = self.scanner.scan_repository(repo_path)
            assert repo_info.has_plugins, "No plugins discovered"
            assert (
                len(repo_info.plugins) == 2
            ), f"Expected 2 plugins, found {len(repo_info.plugins)}"

            plugin_names = [p.name for p in repo_info.valid_plugins]
            assert "utility-plugin" in plugin_names, "utility-plugin not found"
            assert "dev-tools" in plugin_names, "dev-tools not found"

            # Verify plugin components
            utility_plugin = next(p for p in repo_info.plugins if p.name == "utility-plugin")
            assert utility_plugin.has_components, "utility-plugin has no components"
            assert len(utility_plugin.components.get("commands", [])) == 2, "Expected 2 commands"
            assert len(utility_plugin.components.get("agents", [])) == 1, "Expected 1 agent"
            assert len(utility_plugin.components.get("hooks", [])) == 1, "Expected 1 hooks file"

            # Step 3: Enable plugins
            enable1_success = self.config_manager.enable_plugin(
                "testowner/testrepo", "utility-plugin"
            )
            assert enable1_success, "Failed to enable utility-plugin"

            enable2_success = self.config_manager.enable_plugin("testowner/testrepo", "dev-tools")
            assert enable2_success, "Failed to enable dev-tools"

            # Step 4: Verify configuration state
            # Check config.json
            config_data = json.loads(self.config_path.read_text())
            assert "repositories" in config_data, "repositories not found in config"
            assert "testowner/testrepo" in config_data["repositories"], "Repository not in config"

            repo_entry = config_data["repositories"]["testowner/testrepo"]
            assert repo_entry["commitSha"] == "abc123def", "Commit SHA mismatch"
            assert (
                "utility-plugin" in repo_entry["plugins"]
            ), "utility-plugin not in repo plugins list"
            assert "dev-tools" in repo_entry["plugins"], "dev-tools not in repo plugins list"

            # Check settings.json
            settings_data = json.loads(self.settings_path.read_text())
            assert "enabledPlugins" in settings_data, "enabledPlugins not found in settings"
            assert (
                "testowner/testrepo" in settings_data["enabledPlugins"]
            ), "Repository not in enabledPlugins"

            enabled_plugins = settings_data["enabledPlugins"]["testowner/testrepo"]
            assert "utility-plugin" in enabled_plugins, "utility-plugin not enabled"
            assert "dev-tools" in enabled_plugins, "dev-tools not enabled"

            # Step 5: Test namespaced component access
            namespaced = utility_plugin.get_namespaced_components()
            assert "commands" in namespaced, "Commands not in namespaced components"

            command_names = namespaced["commands"]
            expected_commands = ["utility-plugin:hello", "utility-plugin:timestamp"]
            for expected_cmd in expected_commands:
                assert expected_cmd in command_names, f"Expected command {expected_cmd} not found"

        logger.info("Complete install->discover->enable->list workflow test passed")

    def test_multi_plugin_repository_workflow(self):
        """Test handling repositories with multiple plugins."""
        # Create repository with 3 different plugin types
        repo_path = self.create_test_plugin_repo(
            "multiowner",
            "multirepo",
            [
                {"name": "commands-only", "commands": ["cmd1", "cmd2", "cmd3"]},
                {"name": "agents-only", "agents": ["agent1", "agent2"]},
                {"name": "hooks-only", "hooks": True},
            ],
        )

        with patch.object(self.repo_manager, "_get_current_commit_sha", return_value="multi123"):
            # Add repository
            success = self.config_manager.add_repository("multiowner", "multirepo")
            assert success, "Failed to add multi-plugin repository"

            # Discover all plugins
            repo_info = self.scanner.scan_repository(repo_path)
            assert (
                len(repo_info.valid_plugins) == 3
            ), f"Expected 3 plugins, found {len(repo_info.valid_plugins)}"

            # Enable only specific plugins (not all)
            enable_success = self.config_manager.enable_plugin(
                "multiowner/multirepo", "commands-only"
            )
            assert enable_success, "Failed to enable commands-only plugin"

            enable_success = self.config_manager.enable_plugin("multiowner/multirepo", "hooks-only")
            assert enable_success, "Failed to enable hooks-only plugin"

            # Verify only selected plugins are enabled
            settings_data = json.loads(self.settings_path.read_text())
            enabled = settings_data["enabledPlugins"]["multiowner/multirepo"]

            assert "commands-only" in enabled, "commands-only should be enabled"
            assert "hooks-only" in enabled, "hooks-only should be enabled"
            assert "agents-only" not in enabled, "agents-only should not be enabled"

            # Test selective disabling
            disable_success = self.config_manager.disable_plugin(
                "multiowner/multirepo", "commands-only"
            )
            assert disable_success, "Failed to disable commands-only plugin"

            # Verify state after disable
            settings_data = json.loads(self.settings_path.read_text())
            enabled = settings_data["enabledPlugins"]["multiowner/multirepo"]

            assert "commands-only" not in enabled, "commands-only should be disabled"
            assert "hooks-only" in enabled, "hooks-only should still be enabled"

        logger.info("Multi-plugin repository workflow test passed")

    def test_error_scenarios_and_recovery(self):
        """Test error scenarios and recovery mechanisms."""

        # Test 1: Invalid plugin manifest
        invalid_repo_path = self.repos_dir / "invalid" / "repo"
        invalid_repo_path.mkdir(parents=True)

        # Create plugin with invalid manifest
        plugin_path = invalid_repo_path / "broken-plugin"
        plugin_path.mkdir()

        # Invalid JSON in plugin.json
        manifest_path = plugin_path / "plugin.json"
        manifest_path.write_text('{"name": "test", invalid json}')

        repo_info = self.scanner.scan_repository(invalid_repo_path)
        assert len(repo_info.invalid_plugins) > 0, "Should have invalid plugins"
        assert len(repo_info.scan_errors) == 0, "Should not have scan errors for invalid manifest"

        broken_plugin = repo_info.invalid_plugins[0]
        assert not broken_plugin.is_valid, "Plugin should be marked as invalid"
        assert len(broken_plugin.errors) > 0, "Should have errors recorded"

        # Test 2: Configuration corruption recovery
        # Corrupt the config.json
        self.config_path.write_text("invalid json content")

        with pytest.raises(ConfigurationError, match="Invalid JSON"):
            self.config_manager._load_plugin_config()

        # Test 3: Atomic write failure simulation
        with patch(
            "pacc.plugins.config.AtomicFileWriter.write_json", side_effect=OSError("Disk full")
        ):
            success = self.config_manager.add_repository("test", "repo")
            assert not success, "Should fail when atomic write fails"

        # Test 4: Repository validation failure
        empty_repo_path = self.repos_dir / "empty" / "repo"
        empty_repo_path.mkdir(parents=True)

        validation_result = self.repo_manager.validate_repository_structure(empty_repo_path)
        assert not validation_result.is_valid, "Empty repository should be invalid"
        assert (
            "No plugins found" in validation_result.error_message
        ), "Should indicate no plugins found"

        logger.info("Error scenarios and recovery test passed")

    def test_cross_component_interactions(self):
        """Test interactions between different plugin components."""

        # Create repository with complex plugin structure
        repo_path = self.create_test_plugin_repo(
            "complex",
            "repo",
            [
                {
                    "name": "full-plugin",
                    "commands": ["main", "subdir/nested"],  # Test nested command
                    "agents": ["assistant", "tools/helper"],  # Test nested agent
                    "hooks": True,
                }
            ],
        )

        with patch.object(self.repo_manager, "_get_current_commit_sha", return_value="complex123"):
            # Add repository
            self.config_manager.add_repository("complex", "repo")

            # Test discovery with metadata extraction
            repo_info = self.scanner.scan_repository(repo_path)
            full_plugin = repo_info.plugins[0]

            # Verify metadata extraction worked
            assert "commands_metadata" in full_plugin.metadata, "Commands metadata not extracted"
            assert "agents_metadata" in full_plugin.metadata, "Agents metadata not extracted"
            assert "hooks_metadata" in full_plugin.metadata, "Hooks metadata not extracted"

            commands_meta = full_plugin.metadata["commands_metadata"]
            assert (
                len(commands_meta) == 2
            ), f"Expected 2 commands metadata, got {len(commands_meta)}"

            # Find nested command metadata
            nested_cmd = next((cmd for cmd in commands_meta if cmd["name"] == "nested"), None)
            assert nested_cmd is not None, "Nested command metadata not found"

            # Test namespacing for nested components
            namespaced = full_plugin.get_namespaced_components()
            command_names = namespaced["commands"]

            assert "full-plugin:main" in command_names, "Main command namespace incorrect"
            assert (
                "full-plugin:subdir:nested" in command_names
            ), "Nested command namespace incorrect"

            agent_names = namespaced["agents"]
            assert "full-plugin:assistant" in agent_names, "Agent namespace incorrect"
            assert "full-plugin:tools:helper" in agent_names, "Nested agent namespace incorrect"

            # Enable plugin and test configuration consistency
            self.config_manager.enable_plugin("complex/repo", "full-plugin")

            # Verify both config files are consistent
            config_data = json.loads(self.config_path.read_text())
            settings_data = json.loads(self.settings_path.read_text())

            assert "complex/repo" in config_data["repositories"], "Repository not in config"
            assert "complex/repo" in settings_data["enabledPlugins"], "Repository not in settings"
            assert (
                "full-plugin" in settings_data["enabledPlugins"]["complex/repo"]
            ), "Plugin not enabled"

        logger.info("Cross-component interactions test passed")

    def test_configuration_atomicity_and_rollback(self):
        """Test atomic configuration operations and rollback scenarios."""

        # Test atomic transaction success
        with self.config_manager.transaction():
            self.config_manager.add_repository("atomic", "test1")
            self.config_manager.add_repository("atomic", "test2")
            self.config_manager.enable_plugin("atomic/test1", "plugin1")
            self.config_manager.enable_plugin("atomic/test2", "plugin2")

        # Verify all changes were committed
        config_data = json.loads(self.config_path.read_text())
        settings_data = json.loads(self.settings_path.read_text())

        assert "atomic/test1" in config_data["repositories"], "test1 repo not added"
        assert "atomic/test2" in config_data["repositories"], "test2 repo not added"
        assert "atomic/test1" in settings_data["enabledPlugins"], "test1 plugins not enabled"
        assert "atomic/test2" in settings_data["enabledPlugins"], "test2 plugins not enabled"

        # Test atomic transaction rollback
        original_config = self.config_path.read_text()
        original_settings = self.settings_path.read_text()

        with pytest.raises(Exception):
            with self.config_manager.transaction():
                self.config_manager.add_repository("rollback", "test1")
                self.config_manager.enable_plugin("rollback/test1", "plugin1")
                # Simulate failure
                raise ValueError("Simulated failure")

        # Verify rollback occurred
        rolled_back_config = self.config_path.read_text()
        rolled_back_settings = self.settings_path.read_text()

        assert rolled_back_config == original_config, "Config was not rolled back"
        assert rolled_back_settings == original_settings, "Settings were not rolled back"

        config_data = json.loads(self.config_path.read_text())
        settings_data = json.loads(self.settings_path.read_text())

        assert "rollback/test1" not in config_data.get(
            "repositories", {}
        ), "Rolled back repo still present"
        assert "rollback/test1" not in settings_data.get(
            "enabledPlugins", {}
        ), "Rolled back settings still present"

        # Test backup and restore functionality
        backup_info = self.config_manager.backup_config(self.config_path)
        assert backup_info.backup_path.exists(), "Backup file was not created"

        # Modify config
        self.config_manager.add_repository("backup", "test")

        # Restore from backup
        restore_success = self.config_manager.restore_config(backup_info.backup_path)
        assert restore_success, "Failed to restore from backup"

        # Verify restoration
        config_data = json.loads(self.config_path.read_text())
        assert "backup/test" not in config_data.get("repositories", {}), "Backup restoration failed"

        logger.info("Configuration atomicity and rollback test passed")

    def test_performance_validation(self):
        """Test performance requirements are met."""

        # Create large repository with many plugins
        plugins_config = []
        for i in range(50):  # Create 50 plugins
            plugins_config.append(
                {
                    "name": f"perf-plugin-{i:02d}",
                    "commands": [f"cmd{j}" for j in range(5)],  # 5 commands each
                    "agents": [f"agent{j}" for j in range(2)],  # 2 agents each
                    "hooks": True if i % 3 == 0 else False,  # Every 3rd has hooks
                }
            )

        repo_path = self.create_test_plugin_repo("performance", "test", plugins_config)

        # Test discovery performance (should be < 1 second)
        start_time = time.time()
        repo_info = self.scanner.scan_repository(repo_path)
        discovery_time = time.time() - start_time

        assert discovery_time < 1.0, f"Discovery took {discovery_time:.2f}s, expected < 1.0s"
        assert (
            len(repo_info.valid_plugins) == 50
        ), f"Expected 50 plugins, found {len(repo_info.valid_plugins)}"

        # Test configuration update performance
        start_time = time.time()

        with patch.object(self.repo_manager, "_get_current_commit_sha", return_value="perf123"):
            success = self.config_manager.add_repository(
                "performance", "test", {"plugins": [f"perf-plugin-{i:02d}" for i in range(50)]}
            )

        config_time = time.time() - start_time
        assert success, "Failed to add performance test repository"
        assert config_time < 0.5, f"Config update took {config_time:.2f}s, expected < 0.5s"

        # Test bulk plugin enabling performance
        start_time = time.time()

        with self.config_manager.transaction():
            for i in range(10):  # Enable first 10 plugins
                success = self.config_manager.enable_plugin(
                    "performance/test", f"perf-plugin-{i:02d}"
                )
                assert success, f"Failed to enable plugin {i}"

        bulk_enable_time = time.time() - start_time
        assert bulk_enable_time < 1.0, f"Bulk enable took {bulk_enable_time:.2f}s, expected < 1.0s"

        # Verify all plugins were enabled correctly
        settings_data = json.loads(self.settings_path.read_text())
        enabled_plugins = settings_data["enabledPlugins"]["performance/test"]
        assert (
            len(enabled_plugins) == 10
        ), f"Expected 10 enabled plugins, found {len(enabled_plugins)}"

        logger.info(
            f"Performance validation passed - Discovery: {discovery_time:.3f}s, Config: {config_time:.3f}s, Bulk Enable: {bulk_enable_time:.3f}s"
        )


class TestPluginIntegrationWithCLI:
    """Test plugin integration with CLI commands."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.claude_dir = Path(self.temp_dir) / ".claude"
        self.plugins_dir = self.claude_dir / "plugins"
        self.claude_dir.mkdir(parents=True)

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("pathlib.Path.home")
    def test_cli_plugin_workflow_integration(self, mock_home):
        """Test CLI plugin commands work with underlying components."""
        mock_home.return_value = Path(self.temp_dir)

        # Create necessary directory structure and files
        plugins_dir = Path(self.temp_dir) / ".claude" / "plugins"
        settings_path = Path(self.temp_dir) / ".claude" / "settings.json"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps({}))

        cli = PACCCli()

        # Test plugin list when no plugins installed
        args = Mock()
        args.repo = None
        args.type = None
        args.enabled_only = False
        args.disabled_only = False
        args.format = "table"
        args.verbose = False

        result = cli.handle_plugin_list(args)
        assert result == 0, "Plugin list should succeed even when empty"

        # Test plugin enable/disable integration with real components but mocked enable/disable
        with patch(
            "pacc.plugins.config.PluginConfigManager.enable_plugin", return_value=True
        ) as mock_enable, patch(
            "pacc.plugins.config.PluginConfigManager.disable_plugin", return_value=True
        ) as mock_disable:
            # Test enable
            args = Mock()
            args.plugin = "test-plugin"
            args.repo = "owner/repo"

            result = cli.handle_plugin_enable(args)
            assert result == 0, "Plugin enable should succeed"
            mock_enable.assert_called_once_with("owner/repo", "test-plugin")

            # Test disable
            result = cli.handle_plugin_disable(args)
            assert result == 0, "Plugin disable should succeed"
            mock_disable.assert_called_once_with("owner/repo", "test-plugin")

    def test_cli_error_handling_integration(self):
        """Test CLI error handling integrates properly with plugin components."""
        cli = PACCCli()

        # Test invalid plugin identifier handling
        args = Mock()
        args.plugin = "invalid-format"
        args.repo = None

        result = cli.handle_plugin_enable(args)
        assert result == 1, "Should return error code for invalid plugin format"

        result = cli.handle_plugin_disable(args)
        assert result == 1, "Should return error code for invalid plugin format"

        # Test plugin install with invalid URL
        args = Mock()
        args.repo_url = "not-a-valid-url"
        args.dry_run = False
        args.update = False
        args.all = False
        args.type = None
        args.interactive = False
        args.enable = False
        args.verbose = False

        result = cli.handle_plugin_install(args)
        assert result == 1, "Should return error code for invalid repository URL"


class TestPluginDependencyResolution:
    """Test plugin dependency and conflict resolution."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.claude_dir = Path(self.temp_dir) / ".claude"
        self.plugins_dir = self.claude_dir / "plugins"
        self.settings_path = self.claude_dir / "settings.json"

        self.claude_dir.mkdir(parents=True)
        self.plugins_dir.mkdir(parents=True)
        self.settings_path.write_text(json.dumps({}))

        self.config_manager = PluginConfigManager(
            plugins_dir=self.plugins_dir, settings_path=self.settings_path
        )

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_team_config_synchronization(self):
        """Test team configuration synchronization functionality."""

        # Create a team configuration
        team_config = {
            "plugins": {
                "team/utilities": ["formatter", "linter"],
                "team/agents": ["code-reviewer", "documentation-helper"],
                "external/tools": ["git-hooks"],
            }
        }

        # Test sync
        sync_result = self.config_manager.sync_team_config(team_config)

        assert sync_result["success"], f"Team sync failed: {sync_result['errors']}"
        assert (
            sync_result["installed_count"] == 3
        ), f"Expected 3 repos installed, got {sync_result['installed_count']}"
        assert (
            sync_result["failed_count"] == 0
        ), f"Expected no failures, got {sync_result['failed_count']}"

        # Verify configuration was updated
        config_data = json.loads((self.plugins_dir / "config.json").read_text())
        settings_data = json.loads(self.settings_path.read_text())

        expected_repos = ["team/utilities", "team/agents", "external/tools"]
        for repo in expected_repos:
            assert repo in config_data["repositories"], f"Repository {repo} not in config"
            assert (
                repo in settings_data["enabledPlugins"]
            ), f"Repository {repo} not in enabledPlugins"

        # Verify specific plugins are enabled
        assert (
            "formatter" in settings_data["enabledPlugins"]["team/utilities"]
        ), "formatter not enabled"
        assert "linter" in settings_data["enabledPlugins"]["team/utilities"], "linter not enabled"
        assert (
            "code-reviewer" in settings_data["enabledPlugins"]["team/agents"]
        ), "code-reviewer not enabled"
        assert (
            "git-hooks" in settings_data["enabledPlugins"]["external/tools"]
        ), "git-hooks not enabled"

        logger.info("Team configuration synchronization test passed")

    def test_plugin_conflict_detection(self):
        """Test detection and handling of plugin name conflicts."""

        # Add two repositories with conflicting plugin names
        success1 = self.config_manager.add_repository("repo1", "test", {"plugins": ["shared-name"]})
        success2 = self.config_manager.add_repository("repo2", "test", {"plugins": ["shared-name"]})

        assert success1, "Failed to add first repository"
        assert success2, "Failed to add second repository"

        # Enable plugins from both repositories
        enable1 = self.config_manager.enable_plugin("repo1/test", "shared-name")
        enable2 = self.config_manager.enable_plugin("repo2/test", "shared-name")

        assert enable1, "Failed to enable plugin from repo1"
        assert enable2, "Failed to enable plugin from repo2"

        # Verify both are enabled (Claude Code should handle namespacing)
        settings_data = json.loads(self.settings_path.read_text())

        assert (
            "shared-name" in settings_data["enabledPlugins"]["repo1/test"]
        ), "Plugin from repo1 not enabled"
        assert (
            "shared-name" in settings_data["enabledPlugins"]["repo2/test"]
        ), "Plugin from repo2 not enabled"

        logger.info("Plugin conflict detection test passed")


if __name__ == "__main__":
    # Configure logging for tests
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    pytest.main([__file__, "-v"])
