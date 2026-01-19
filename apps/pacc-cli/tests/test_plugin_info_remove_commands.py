"""Comprehensive tests for plugin info and remove commands."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pacc.cli import PACCCli


class TestPluginInfoCommand:
    """Test plugin info command functionality."""

    def test_info_command_with_detailed_plugin_data(self):
        """Test info command with full plugin metadata."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.format = "json"

                # Mock plugin discovery with detailed data
                mock_plugin_details = Mock()
                mock_plugin_details.name = "test-plugin"
                mock_plugin_details.manifest = {
                    "description": "A test plugin",
                    "version": "1.0.0",
                    "author": "Test Author",
                }
                mock_plugin_details.path = Path("/fake/path")
                mock_plugin_details.get_namespaced_components.return_value = {
                    "commands": ["test-plugin:cmd1", "test-plugin:cmd2"],
                    "agents": ["test-plugin:agent1"],
                    "hooks": [],
                }

                mock_repo_plugins = Mock()
                mock_repo_plugins.plugins = [mock_plugin_details]

                with patch("pacc.plugins.PluginConfigManager") as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {
                            "owner/repo": {
                                "plugins": ["test-plugin"],
                                "lastUpdated": "2024-01-01T12:00:00",
                                "commitSha": "abc123def456",
                                "url": "https://github.com/owner/repo.git",
                            }
                        }
                    }
                    mock_instance._load_settings.return_value = {
                        "enabledPlugins": {"owner/repo": ["test-plugin"]}
                    }
                    mock_config.return_value = mock_instance

                    with patch("pacc.plugins.PluginDiscovery") as mock_discovery:
                        mock_discovery_instance = Mock()
                        mock_discovery_instance.discover_plugins.return_value = mock_repo_plugins
                        mock_discovery.return_value = mock_discovery_instance

                        # Mock repository path exists
                        with patch("pathlib.Path.exists", return_value=True):
                            result = cli.handle_plugin_info(args)

                            assert result == 0

    def test_info_command_table_format_output(self, capsys):
        """Test info command with table format output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.format = "table"

                with patch("pacc.plugins.PluginConfigManager") as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {
                            "owner/repo": {
                                "plugins": ["test-plugin"],
                                "lastUpdated": "2024-01-01T12:00:00",
                                "commitSha": "abc123def456",
                                "url": "https://github.com/owner/repo.git",
                            }
                        }
                    }
                    mock_instance._load_settings.return_value = {
                        "enabledPlugins": {"owner/repo": ["test-plugin"]}
                    }
                    mock_config.return_value = mock_instance

                    # Mock repository path doesn't exist (not installed)
                    with patch("pathlib.Path.exists", return_value=False):
                        result = cli.handle_plugin_info(args)

                        assert result == 0
                        captured = capsys.readouterr()
                        assert "Plugin: test-plugin" in captured.out
                        assert "Repository: owner/repo" in captured.out
                        assert "Enabled: ✓ Yes" in captured.out
                        assert "Installed: ✗ No" in captured.out

    def test_info_command_plugin_not_in_repo(self):
        """Test info command when plugin not found in repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                cli = PACCCli()
                args = Mock()
                args.plugin = "nonexistent-plugin"
                args.repo = "owner/repo"
                args.format = "table"

                with patch("pacc.plugins.PluginConfigManager") as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {
                            "owner/repo": {
                                "plugins": ["other-plugin"],  # Different plugin
                                "lastUpdated": "2024-01-01T12:00:00",
                            }
                        }
                    }
                    mock_instance._load_settings.return_value = {"enabledPlugins": {}}
                    mock_config.return_value = mock_instance

                    result = cli.handle_plugin_info(args)

                    assert result == 1

    def test_info_command_discovery_error(self):
        """Test info command when plugin discovery fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.format = "json"

                with patch("pacc.plugins.PluginConfigManager") as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {
                            "owner/repo": {
                                "plugins": ["test-plugin"],
                                "lastUpdated": "2024-01-01T12:00:00",
                            }
                        }
                    }
                    mock_instance._load_settings.return_value = {"enabledPlugins": {}}
                    mock_config.return_value = mock_instance

                    with patch("pacc.plugins.PluginDiscovery") as mock_discovery:
                        mock_discovery_instance = Mock()
                        mock_discovery_instance.discover_plugins.side_effect = Exception(
                            "Discovery failed"
                        )
                        mock_discovery.return_value = mock_discovery_instance

                        # Mock repository exists
                        with patch("pathlib.Path.exists", return_value=True):
                            result = cli.handle_plugin_info(args)

                            assert result == 0  # Should still succeed with warning


class TestPluginRemoveCommand:
    """Test plugin remove command functionality."""

    def test_remove_command_with_confirmation_cancelled(self):
        """Test remove command when user cancels confirmation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.dry_run = False
                args.keep_files = False
                args.force = False

                with patch("pacc.plugins.PluginConfigManager") as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {"owner/repo": {"plugins": ["test-plugin"]}}
                    }
                    mock_instance._load_settings.return_value = {
                        "enabledPlugins": {"owner/repo": ["test-plugin"]}
                    }
                    mock_config.return_value = mock_instance

                    # Mock repository exists
                    with patch("pathlib.Path.exists", return_value=True):
                        # Mock user input to cancel
                        with patch("builtins.input", return_value="n"):
                            result = cli.handle_plugin_remove(args)

                            assert result == 0  # Success but cancelled

    def test_remove_command_repository_not_in_config(self):
        """Test remove command when repository not in configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.dry_run = False
                args.keep_files = False
                args.force = True  # Skip confirmation

                with patch("pacc.plugins.PluginConfigManager") as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {}  # Empty - repo not found
                    }
                    mock_instance._load_settings.return_value = {"enabledPlugins": {}}
                    mock_instance.transaction.return_value.__enter__ = Mock(
                        return_value=mock_instance
                    )
                    mock_instance.transaction.return_value.__exit__ = Mock(return_value=None)
                    mock_config.return_value = mock_instance

                    # Mock repository doesn't exist
                    with patch("pathlib.Path.exists", return_value=False):
                        result = cli.handle_plugin_remove(args)

                        assert result == 0  # Should succeed

    def test_remove_command_with_file_removal(self):
        """Test remove command that removes repository files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.dry_run = False
                args.keep_files = False  # Remove files
                args.force = True  # Skip confirmation

                with patch("pacc.plugins.PluginConfigManager") as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {
                            "owner/repo": {
                                "plugins": ["test-plugin"]  # Only plugin in repo
                            }
                        }
                    }
                    mock_instance._load_settings.return_value = {
                        "enabledPlugins": {"owner/repo": ["test-plugin"]}
                    }
                    mock_instance.disable_plugin.return_value = True
                    mock_instance.remove_repository.return_value = True
                    mock_instance.transaction.return_value.__enter__ = Mock(
                        return_value=mock_instance
                    )
                    mock_instance.transaction.return_value.__exit__ = Mock(return_value=None)
                    mock_config.return_value = mock_instance

                    # Mock repository exists
                    with patch("pathlib.Path.exists", return_value=True):
                        # Mock shutil.rmtree
                        with patch("shutil.rmtree") as mock_rmtree:
                            result = cli.handle_plugin_remove(args)

                            assert result == 0
                            mock_rmtree.assert_called_once()
                            mock_instance.disable_plugin.assert_called_once_with(
                                "owner/repo", "test-plugin"
                            )
                            mock_instance.remove_repository.assert_called_once_with("owner", "repo")

    def test_remove_command_keep_repo_with_multiple_plugins(self):
        """Test remove command that keeps repository with multiple plugins."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.dry_run = False
                args.keep_files = False
                args.force = True

                with patch("pacc.plugins.PluginConfigManager") as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {
                            "owner/repo": {
                                "plugins": ["test-plugin", "another-plugin"]  # Multiple plugins
                            }
                        }
                    }
                    mock_instance._load_settings.return_value = {
                        "enabledPlugins": {"owner/repo": ["test-plugin"]}
                    }
                    mock_instance.disable_plugin.return_value = True
                    mock_instance.transaction.return_value.__enter__ = Mock(
                        return_value=mock_instance
                    )
                    mock_instance.transaction.return_value.__exit__ = Mock(return_value=None)
                    mock_config.return_value = mock_instance

                    # Mock repository exists
                    with patch("pathlib.Path.exists", return_value=True):
                        result = cli.handle_plugin_remove(args)

                        assert result == 0
                        mock_instance.disable_plugin.assert_called_once_with(
                            "owner/repo", "test-plugin"
                        )
                        # Should not call remove_repository since there are other plugins
                        mock_instance.remove_repository.assert_not_called()

    def test_remove_command_transaction_failure(self):
        """Test remove command when transaction fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path(temp_dir)

                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.dry_run = False
                args.keep_files = True
                args.force = True

                with patch("pacc.plugins.PluginConfigManager") as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {"owner/repo": {"plugins": ["test-plugin"]}}
                    }
                    mock_instance._load_settings.return_value = {
                        "enabledPlugins": {"owner/repo": ["test-plugin"]}
                    }
                    mock_instance.disable_plugin.return_value = False  # Failure
                    mock_instance.transaction.return_value.__enter__ = Mock(
                        return_value=mock_instance
                    )
                    mock_instance.transaction.return_value.__exit__ = Mock(
                        side_effect=Exception("Transaction failed")
                    )
                    mock_config.return_value = mock_instance

                    result = cli.handle_plugin_remove(args)

                    assert result == 1  # Should fail


class TestPluginHelperMethods:
    """Test plugin command helper methods."""

    def test_get_plugin_components_info(self):
        """Test _get_plugin_components_info helper method."""
        cli = PACCCli()

        # Mock plugin details
        mock_plugin = Mock()
        mock_plugin.get_namespaced_components.return_value = {
            "commands": ["plugin:cmd1", "plugin:cmd2"],
            "agents": ["plugin:agent1"],
            "hooks": [],
        }

        result = cli._get_plugin_components_info(mock_plugin)

        assert result["commands"] == ["plugin:cmd1", "plugin:cmd2"]
        assert result["agents"] == ["plugin:agent1"]
        assert result["hooks"] == []
        assert result["total_count"] == 3

    def test_get_plugin_components_info_error(self):
        """Test _get_plugin_components_info with error."""
        cli = PACCCli()

        # Mock plugin details that raises exception
        mock_plugin = Mock()
        mock_plugin.get_namespaced_components.side_effect = Exception("Component error")

        result = cli._get_plugin_components_info(mock_plugin)

        assert result["commands"] == []
        assert result["agents"] == []
        assert result["hooks"] == []
        assert result["total_count"] == 0

    def test_display_plugin_info_table(self, capsys):
        """Test _display_plugin_info_table helper method."""
        cli = PACCCli()

        plugin_info = {
            "name": "test-plugin",
            "repository": "owner/repo",
            "enabled": True,
            "installed": True,
            "description": "A test plugin",
            "version": "1.0.0",
            "author": "Test Author",
            "repository_url": "https://github.com/owner/repo.git",
            "last_updated": "2024-01-01T12:00:00",
            "commit_sha": "abc123def456789",
            "file_path": "/path/to/plugin",
            "components": {
                "commands": ["test-plugin:cmd1"],
                "agents": ["test-plugin:agent1"],
                "hooks": [],
                "total_count": 2,
            },
        }

        cli._display_plugin_info_table(plugin_info)

        captured = capsys.readouterr()
        assert "Plugin: test-plugin" in captured.out
        assert "Repository: owner/repo" in captured.out
        assert "Enabled: ✓ Yes" in captured.out
        assert "Installed: ✓ Yes" in captured.out
        assert "Description: A test plugin" in captured.out
        assert "Version: 1.0.0" in captured.out
        assert "Author: Test Author" in captured.out
        assert "Components (2 total):" in captured.out
        assert "Commands (1):" in captured.out
        assert "test-plugin:cmd1" in captured.out
        assert "Agents (1):" in captured.out
        assert "test-plugin:agent1" in captured.out

    def test_display_plugin_info_table_minimal(self, capsys):
        """Test _display_plugin_info_table with minimal info."""
        cli = PACCCli()

        plugin_info = {
            "name": "minimal-plugin",
            "repository": "owner/repo",
            "enabled": False,
            "installed": False,
        }

        cli._display_plugin_info_table(plugin_info)

        captured = capsys.readouterr()
        assert "Plugin: minimal-plugin" in captured.out
        assert "Repository: owner/repo" in captured.out
        assert "Enabled: ✗ No" in captured.out
        assert "Installed: ✗ No" in captured.out
