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


if __name__ == "__main__":
    pytest.main([__file__])