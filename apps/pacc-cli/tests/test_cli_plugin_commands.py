"""Integration tests for CLI plugin commands."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pacc.cli import PACCCli


class TestPluginCommands:
    """Test CLI plugin command integration."""
    
    def test_plugin_help_command(self, capsys):
        """Test plugin help command."""
        cli = PACCCli()
        
        # Mock args for plugin help
        args = Mock()
        args.command = "plugin"
        args.plugin_command = None
        
        result = cli._plugin_help(args)
        
        assert result == 0
        captured = capsys.readouterr()
        assert "pacc plugin: Manage Claude Code plugins" in captured.out
        assert "install <repo_url>" in captured.out
        assert "list" in captured.out
        assert "enable <plugin>" in captured.out
        assert "disable <plugin>" in captured.out
    
    def test_plugin_list_empty(self):
        """Test plugin list when no plugins are installed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock home directory to use temp directory
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.repo = None
                args.type = None
                args.enabled_only = False
                args.disabled_only = False
                args.format = "table"
                args.verbose = False
                
                result = cli.handle_plugin_list(args)
                
                assert result == 0
    
    def test_plugin_enable_invalid_format(self):
        """Test plugin enable with invalid plugin format."""
        cli = PACCCli()
        args = Mock()
        args.plugin = "invalid"  # No repo specified
        args.repo = None
        
        result = cli.handle_plugin_enable(args)
        
        assert result == 1
    
    def test_plugin_disable_invalid_format(self):
        """Test plugin disable with invalid plugin format."""
        cli = PACCCli()
        args = Mock()
        args.plugin = "invalid"  # No repo specified
        args.repo = None
        
        result = cli.handle_plugin_disable(args)
        
        assert result == 1
    
    def test_plugin_enable_with_repo_arg(self):
        """Test plugin enable with separate repo argument."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                
                # Mock the plugin config manager to return success
                with patch('pacc.plugins.PluginConfigManager') as mock_config:
                    mock_instance = Mock()
                    mock_instance.enable_plugin.return_value = True
                    mock_config.return_value = mock_instance
                    
                    result = cli.handle_plugin_enable(args)
                    
                    assert result == 0
                    mock_instance.enable_plugin.assert_called_once_with("owner/repo", "test-plugin")
    
    def test_plugin_disable_with_repo_arg(self):
        """Test plugin disable with separate repo argument."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                
                # Mock the plugin config manager to return success
                with patch('pacc.plugins.PluginConfigManager') as mock_config:
                    mock_instance = Mock()
                    mock_instance.disable_plugin.return_value = True
                    mock_config.return_value = mock_instance
                    
                    result = cli.handle_plugin_disable(args)
                    
                    assert result == 0
                    mock_instance.disable_plugin.assert_called_once_with("owner/repo", "test-plugin")
    
    def test_plugin_info_invalid_format(self):
        """Test plugin info with invalid plugin format."""
        cli = PACCCli()
        args = Mock()
        args.plugin = "invalid"  # No repo specified
        args.repo = None
        args.format = "table"
        
        result = cli.handle_plugin_info(args)
        
        assert result == 1
    
    def test_plugin_info_repo_not_found(self):
        """Test plugin info when repository not found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "owner/repo/test-plugin"
                args.repo = None
                args.format = "table"
                
                result = cli.handle_plugin_info(args)
                
                assert result == 1
    
    def test_plugin_info_success_json_format(self):
        """Test plugin info with JSON format output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.format = "json"
                
                # Mock the config manager to return plugin data
                with patch('pacc.plugins.PluginConfigManager') as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {
                            "owner/repo": {
                                "plugins": ["test-plugin"],
                                "lastUpdated": "2024-01-01T12:00:00",
                                "commitSha": "abc123def456",
                                "url": "https://github.com/owner/repo.git"
                            }
                        }
                    }
                    mock_instance._load_settings.return_value = {
                        "enabledPlugins": {
                            "owner/repo": ["test-plugin"]
                        }
                    }
                    mock_config.return_value = mock_instance
                    
                    # Mock repository manager
                    with patch('pacc.plugins.PluginRepositoryManager'):
                        # Mock discovery
                        with patch('pacc.plugins.PluginDiscovery'):
                            result = cli.handle_plugin_info(args)
                            
                            assert result == 0
    
    def test_plugin_remove_invalid_format(self):
        """Test plugin remove with invalid plugin format."""
        cli = PACCCli()
        args = Mock()
        args.plugin = "invalid"  # No repo specified
        args.repo = None
        
        result = cli.handle_plugin_remove(args)
        
        assert result == 1
    
    def test_plugin_remove_dry_run(self):
        """Test plugin remove in dry run mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.dry_run = True
                args.keep_files = False
                args.force = False
                
                # Mock the config manager
                with patch('pacc.plugins.PluginConfigManager') as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {
                            "owner/repo": {
                                "plugins": ["test-plugin"]
                            }
                        }
                    }
                    mock_instance._load_settings.return_value = {
                        "enabledPlugins": {
                            "owner/repo": ["test-plugin"]
                        }
                    }
                    mock_config.return_value = mock_instance
                    
                    result = cli.handle_plugin_remove(args)
                    
                    assert result == 0
    
    def test_plugin_remove_success_with_transaction(self):
        """Test plugin remove with successful transaction."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "test-plugin"
                args.repo = "owner/repo"
                args.dry_run = False
                args.keep_files = True  # Don't remove files for this test
                args.force = True  # Skip confirmation
                
                # Mock the config manager
                with patch('pacc.plugins.PluginConfigManager') as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {
                        "repositories": {
                            "owner/repo": {
                                "plugins": ["test-plugin"]
                            }
                        }
                    }
                    mock_instance._load_settings.return_value = {
                        "enabledPlugins": {
                            "owner/repo": ["test-plugin"]
                        }
                    }
                    mock_instance.disable_plugin.return_value = True
                    mock_instance.transaction.return_value.__enter__ = Mock(return_value=mock_instance)
                    mock_instance.transaction.return_value.__exit__ = Mock(return_value=None)
                    mock_config.return_value = mock_instance
                    
                    result = cli.handle_plugin_remove(args)
                    
                    assert result == 0
                    mock_instance.disable_plugin.assert_called_once_with("owner/repo", "test-plugin")
    
    def test_plugin_enable_slash_format(self):
        """Test plugin enable with owner/repo/plugin format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "owner/repo"  # This should be parsed as repo, not plugin
                args.repo = None
                
                # This should fail because it can't parse properly
                result = cli.handle_plugin_enable(args)
                
                assert result == 1
    
    def test_parse_plugin_identifier(self):
        """Test plugin identifier parsing."""
        cli = PACCCli()
        
        # Test repo/plugin format
        repo, plugin = cli._parse_plugin_identifier("owner/repo", None)
        assert repo == "owner"
        assert plugin == "repo"
        
        # Test separate args
        repo, plugin = cli._parse_plugin_identifier("plugin-name", "owner/repo")
        assert repo == "owner/repo"
        assert plugin == "plugin-name"
        
        # Test invalid format
        repo, plugin = cli._parse_plugin_identifier("just-plugin", None)
        assert repo is None
        assert plugin is None
    
    def test_plugin_install_invalid_url(self):
        """Test plugin install with invalid Git URL."""
        cli = PACCCli()
        args = Mock()
        args.repo_url = "not-a-url"
        args.dry_run = False
        args.update = False
        args.all = False
        args.type = None
        args.interactive = False
        args.enable = False
        args.verbose = False
        
        result = cli.handle_plugin_install(args)
        
        assert result == 1
    
    @patch('pacc.plugins.GitRepository.is_valid_git_url')
    def test_plugin_install_dry_run(self, mock_is_valid, capsys):
        """Test plugin install dry run mode."""
        mock_is_valid.return_value = True
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.repo_url = "https://github.com/owner/repo"
                args.dry_run = True
                args.update = False
                args.all = False
                args.type = None
                args.interactive = False
                args.enable = False
                args.verbose = False
                
                # Mock the repository manager and discovery
                with patch('pacc.plugins.RepositoryManager') as mock_repo_mgr, \
                     patch('pacc.plugins.PluginDiscovery') as mock_discovery, \
                     patch('pacc.plugins.PluginConfigManager') as mock_config:
                    
                    # Setup mocks
                    mock_repo_instance = Mock()
                    mock_repo_info = Mock()
                    mock_repo_info.owner = "owner"
                    mock_repo_info.repo = "repo"
                    mock_repo_info.commit_hash = "abc123"
                    mock_repo_instance.install_repository.return_value = (Path(temp_dir), mock_repo_info)
                    mock_repo_mgr.return_value = mock_repo_instance
                    
                    mock_discovery_instance = Mock()
                    mock_repo_plugins = Mock()
                    mock_repo_plugins.plugins = []
                    mock_discovery_instance.discover_plugins.return_value = mock_repo_plugins
                    mock_discovery.return_value = mock_discovery_instance
                    
                    result = cli.handle_plugin_install(args)
                    
                    assert result == 0
                    captured = capsys.readouterr()
                    assert "DRY RUN MODE" in captured.out


class TestPluginUpdateCommands:
    """Test CLI plugin update command functionality."""
    
    def test_plugin_update_no_plugins_installed(self):
        """Test plugin update when no plugins are installed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = None  # Update all plugins
                args.dry_run = False
                args.force = False
                args.show_diff = False
                
                # Mock config manager to return empty repositories
                with patch('pacc.plugins.PluginConfigManager') as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {"repositories": {}}
                    mock_config.return_value = mock_instance
                    
                    result = cli.handle_plugin_update(args)
                    
                    assert result == 0
    
    def test_plugin_update_specific_plugin_not_found(self):
        """Test updating specific plugin that doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "nonexistent/repo"
                args.dry_run = False
                args.force = False
                args.show_diff = False
                
                # Mock config manager
                with patch('pacc.plugins.PluginConfigManager') as mock_config:
                    mock_instance = Mock()
                    mock_instance._load_plugin_config.return_value = {"repositories": {}}
                    mock_config.return_value = mock_instance
                    
                    result = cli.handle_plugin_update(args)
                    
                    assert result == 1
    
    def test_plugin_update_invalid_format(self):
        """Test plugin update with invalid plugin format."""
        cli = PACCCli()
        args = Mock()
        args.plugin = "invalid-format"  # Missing slash
        args.dry_run = False
        args.force = False
        args.show_diff = False
        
        result = cli.handle_plugin_update(args)
        
        assert result == 1
    
    @patch('pacc.plugins.PluginRepositoryManager')
    @patch('pacc.plugins.PluginConfigManager')
    def test_plugin_update_single_plugin_success(self, mock_config, mock_repo_mgr):
        """Test successful single plugin update."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                # Setup repository directory
                repo_dir = Path(temp_dir) / ".claude" / "plugins" / "repos" / "owner" / "repo"
                repo_dir.mkdir(parents=True)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "owner/repo"
                args.dry_run = False
                args.force = False
                args.show_diff = False
                
                # Mock config manager
                mock_config_instance = Mock()
                mock_config_instance._load_plugin_config.return_value = {
                    "repositories": {"owner/repo": {"commitSha": "abc123"}}
                }
                mock_config.return_value = mock_config_instance
                
                # Mock repository manager
                mock_repo_instance = Mock()
                from pacc.plugins.repository import UpdateResult
                mock_update_result = UpdateResult(
                    success=True,
                    had_changes=True,
                    old_sha="abc123",
                    new_sha="def456",
                    message="Updated successfully"
                )
                mock_repo_instance._get_current_commit_sha.return_value = "abc123"
                mock_repo_instance._is_working_tree_clean.return_value = True
                mock_repo_instance.update_plugin.return_value = mock_update_result
                mock_repo_mgr.return_value = mock_repo_instance
                
                result = cli.handle_plugin_update(args)
                
                assert result == 0
                mock_repo_instance.update_plugin.assert_called_once()
    
    @patch('pacc.plugins.PluginRepositoryManager')
    @patch('pacc.plugins.PluginConfigManager')
    def test_plugin_update_all_plugins(self, mock_config, mock_repo_mgr):
        """Test updating all installed plugins."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                # Setup multiple repository directories
                repo1_dir = Path(temp_dir) / ".claude" / "plugins" / "repos" / "owner1" / "repo1"
                repo2_dir = Path(temp_dir) / ".claude" / "plugins" / "repos" / "owner2" / "repo2"
                repo1_dir.mkdir(parents=True)
                repo2_dir.mkdir(parents=True)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = None  # Update all
                args.dry_run = False
                args.force = False
                args.show_diff = False
                
                # Mock config manager with multiple repos
                mock_config_instance = Mock()
                mock_config_instance._load_plugin_config.return_value = {
                    "repositories": {
                        "owner1/repo1": {"commitSha": "abc123"},
                        "owner2/repo2": {"commitSha": "def456"}
                    }
                }
                mock_config.return_value = mock_config_instance
                
                # Mock repository manager
                mock_repo_instance = Mock()
                from pacc.plugins.repository import UpdateResult
                mock_update_result = UpdateResult(success=True, had_changes=False)
                mock_repo_instance.update_plugin.return_value = mock_update_result
                mock_repo_mgr.return_value = mock_repo_instance
                
                result = cli.handle_plugin_update(args)
                
                assert result == 0
                assert mock_repo_instance.update_plugin.call_count == 2
    
    @patch('pacc.plugins.PluginRepositoryManager')
    @patch('pacc.plugins.PluginConfigManager')
    def test_plugin_update_dry_run(self, mock_config, mock_repo_mgr, capsys):
        """Test plugin update dry run mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                # Setup repository directory
                repo_dir = Path(temp_dir) / ".claude" / "plugins" / "repos" / "owner" / "repo"
                repo_dir.mkdir(parents=True)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "owner/repo"
                args.dry_run = True
                args.force = False
                args.show_diff = False
                
                # Mock config manager
                mock_config_instance = Mock()
                mock_config_instance._load_plugin_config.return_value = {
                    "repositories": {"owner/repo": {"commitSha": "abc123"}}
                }
                mock_config.return_value = mock_config_instance
                
                # Mock repository manager with show preview functionality
                mock_repo_instance = Mock()
                mock_repo_instance._get_current_commit_sha.return_value = "abc123"
                mock_repo_mgr.return_value = mock_repo_instance
                
                # Mock CLI's _show_update_preview method to return success
                with patch.object(cli, '_show_update_preview') as mock_preview:
                    mock_preview.return_value = 0
                    
                    result = cli.handle_plugin_update(args)
                    
                    assert result == 0
                    mock_preview.assert_called_once()
    
    @patch('pacc.plugins.PluginRepositoryManager')
    @patch('pacc.plugins.PluginConfigManager')
    def test_plugin_update_with_conflicts(self, mock_config, mock_repo_mgr):
        """Test plugin update with merge conflicts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                # Setup repository directory
                repo_dir = Path(temp_dir) / ".claude" / "plugins" / "repos" / "owner" / "repo"
                repo_dir.mkdir(parents=True)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "owner/repo"
                args.dry_run = False
                args.force = False
                args.show_diff = False
                
                # Mock config manager
                mock_config_instance = Mock()
                mock_config_instance._load_plugin_config.return_value = {
                    "repositories": {"owner/repo": {"commitSha": "abc123"}}
                }
                mock_config.return_value = mock_config_instance
                
                # Mock repository manager with conflict
                mock_repo_instance = Mock()
                mock_repo_instance._get_current_commit_sha.return_value = "abc123"
                mock_repo_instance._is_working_tree_clean.return_value = False  # Dirty tree
                mock_repo_mgr.return_value = mock_repo_instance
                
                result = cli.handle_plugin_update(args)
                
                assert result == 1
    
    @patch('pacc.plugins.PluginRepositoryManager')
    @patch('pacc.plugins.PluginConfigManager')
    def test_plugin_update_force_mode(self, mock_config, mock_repo_mgr):
        """Test plugin update with force flag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                # Setup repository directory
                repo_dir = Path(temp_dir) / ".claude" / "plugins" / "repos" / "owner" / "repo"
                repo_dir.mkdir(parents=True)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "owner/repo"
                args.dry_run = False
                args.force = True  # Force update
                args.show_diff = False
                
                # Mock config manager
                mock_config_instance = Mock()
                mock_config_instance._load_plugin_config.return_value = {
                    "repositories": {"owner/repo": {"commitSha": "abc123"}}
                }
                mock_config.return_value = mock_config_instance
                
                # Mock repository manager
                mock_repo_instance = Mock()
                mock_repo_instance._get_current_commit_sha.return_value = "abc123"
                mock_repo_instance._is_working_tree_clean.return_value = False  # Dirty tree
                from pacc.plugins.repository import UpdateResult
                mock_update_result = UpdateResult(
                    success=False,
                    error_message="Update failed"
                )
                mock_repo_instance.update_plugin.return_value = mock_update_result
                mock_repo_instance.rollback_plugin.return_value = True  # Successful rollback
                mock_repo_mgr.return_value = mock_repo_instance
                
                result = cli.handle_plugin_update(args)
                
                # Should still fail but attempt rollback
                assert result == 1
                mock_repo_instance.rollback_plugin.assert_called_once_with(repo_dir, "abc123")
    
    @patch('pacc.plugins.PluginRepositoryManager')
    @patch('pacc.plugins.PluginConfigManager')
    @patch('subprocess.run')
    def test_plugin_update_show_diff(self, mock_subprocess, mock_config, mock_repo_mgr, capsys):
        """Test plugin update with diff display."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('pathlib.Path.home') as mock_home:
                mock_home.return_value = Path(temp_dir)
                
                # Setup repository directory
                repo_dir = Path(temp_dir) / ".claude" / "plugins" / "repos" / "owner" / "repo"
                repo_dir.mkdir(parents=True)
                
                cli = PACCCli()
                args = Mock()
                args.plugin = "owner/repo"
                args.dry_run = False
                args.force = False
                args.show_diff = True
                
                # Mock config manager
                mock_config_instance = Mock()
                mock_config_instance._load_plugin_config.return_value = {
                    "repositories": {"owner/repo": {"commitSha": "abc123"}}
                }
                mock_config.return_value = mock_config_instance
                
                # Mock repository manager
                mock_repo_instance = Mock()
                mock_repo_instance._get_current_commit_sha.return_value = "abc123"
                mock_repo_instance._is_working_tree_clean.return_value = True
                from pacc.plugins.repository import UpdateResult
                mock_update_result = UpdateResult(
                    success=True,
                    had_changes=True,
                    old_sha="abc123",
                    new_sha="def456"
                )
                mock_repo_instance.update_plugin.return_value = mock_update_result
                mock_repo_mgr.return_value = mock_repo_instance
                
                # Mock git diff command
                mock_subprocess.return_value = Mock(
                    returncode=0,
                    stdout=" file.py | 2 +-\n 1 file changed, 1 insertion(+), 1 deletion(-)"
                )
                
                result = cli.handle_plugin_update(args)
                
                assert result == 0
                mock_subprocess.assert_called()  # git diff should be called
    
    def test_plugin_update_error_handling(self):
        """Test plugin update with unexpected errors."""
        cli = PACCCli()
        args = Mock()
        args.plugin = "owner/repo"
        args.dry_run = False
        args.force = False
        args.show_diff = False
        
        # Mock an exception during update
        with patch('pacc.plugins.PluginRepositoryManager') as mock_repo_mgr:
            mock_repo_mgr.side_effect = Exception("Unexpected error")
            
            result = cli.handle_plugin_update(args)
            
            assert result == 1


if __name__ == "__main__":
    pytest.main([__file__])