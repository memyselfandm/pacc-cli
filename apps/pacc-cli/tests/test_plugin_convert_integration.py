"""Integration tests for plugin conversion CLI workflow."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pacc.cli import PACCCli


class TestPluginConvertIntegration:
    """Test the complete plugin conversion workflow."""
    
    def test_convert_workflow_mock(self):
        """Test the complete convert workflow with mocked components."""
        cli = PACCCli()
        
        # Create a temporary hook file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            hook_data = {
                "name": "test-hook",
                "eventTypes": ["PreToolUse"],
                "commands": ["echo 'test'"]
            }
            json.dump(hook_data, f)
            hook_file = Path(f.name)
        
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                # Mock the converter to avoid validator dependencies
                with patch('pacc.cli.ExtensionToPluginConverter') as mock_converter_class:
                    mock_converter = Mock()
                    mock_converter_class.return_value = mock_converter
                    
                    from pacc.plugins.converter import ConversionResult
                    mock_result = ConversionResult(
                        success=True,
                        plugin_name="test-plugin",
                        plugin_path=Path(output_dir) / "test-plugin",
                        components=["hooks"]
                    )
                    mock_converter.convert_extension.return_value = mock_result
                    
                    # Mock user input
                    with patch('builtins.input', side_effect=['test-plugin', 'Test Author']):
                        args = Mock()
                        args.extension = str(hook_file)
                        args.name = None
                        args.author = None
                        args.version = "1.0.0"
                        args.repo = None
                        args.batch = False
                        args.output = Path(output_dir)
                        args.overwrite = False
                        
                        result = cli.handle_plugin_convert(args)
                        
                        # Should succeed
                        assert result == 0
                        
                        # Verify converter was called
                        mock_converter.convert_extension.assert_called_once()
                        
                        # Check that metadata was created correctly
                        call_args = mock_converter.convert_extension.call_args
                        metadata = call_args[1]['metadata']
                        assert metadata.name == "test-plugin"
                        assert metadata.author == "Test Author"
                        assert metadata.version == "1.0.0"
                        
        finally:
            hook_file.unlink(missing_ok=True)
    
    def test_plugin_help_includes_new_commands(self):
        """Test that plugin help includes the new convert and push commands."""
        cli = PACCCli()
        
        # Test that the help method includes new commands
        with patch('builtins.print') as mock_print:
            args = Mock()
            result = cli._plugin_help(args)
            
            assert result == 0
            
            # Check that print was called with the right content
            print_calls = [call[0][0] for call in mock_print.call_args_list]
            help_text = ' '.join(print_calls)
            
            assert 'convert <extension>' in help_text
            assert 'push <plugin> <repo>' in help_text
            assert 'Convert extension to plugin format' in help_text
            assert 'Push local plugin to Git repository' in help_text
    
    def test_convert_with_repo_push_mock(self):
        """Test convert with direct repository push."""
        cli = PACCCli()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            hook_data = {"name": "test", "eventTypes": ["PreToolUse"]}
            json.dump(hook_data, f)
            hook_file = Path(f.name)
        
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                with patch('pacc.cli.ExtensionToPluginConverter') as mock_converter_class, \
                     patch('pacc.cli.PluginPusher') as mock_pusher_class:
                    
                    # Mock converter
                    mock_converter = Mock()
                    mock_converter_class.return_value = mock_converter
                    
                    from pacc.plugins.converter import ConversionResult
                    mock_result = ConversionResult(
                        success=True,
                        plugin_name="test-plugin",
                        plugin_path=Path(output_dir) / "test-plugin",
                        components=["hooks"]
                    )
                    mock_converter.convert_extension.return_value = mock_result
                    
                    # Mock pusher
                    mock_pusher = Mock()
                    mock_pusher_class.return_value = mock_pusher
                    mock_pusher.push_plugin.return_value = True
                    
                    with patch('builtins.input', side_effect=['test-plugin', 'Test Author']):
                        args = Mock()
                        args.extension = str(hook_file)
                        args.name = None
                        args.author = None
                        args.version = "1.0.0"
                        args.repo = "https://github.com/test/repo.git"
                        args.batch = False
                        args.output = Path(output_dir)
                        args.overwrite = False
                        
                        result = cli.handle_plugin_convert(args)
                        
                        assert result == 0
                        
                        # Verify both converter and pusher were called
                        mock_converter.convert_extension.assert_called_once()
                        mock_pusher.push_plugin.assert_called_once_with(
                            Path(output_dir) / "test-plugin",
                            "https://github.com/test/repo.git"
                        )
                        
        finally:
            hook_file.unlink(missing_ok=True)
    
    def test_push_command_mock(self):
        """Test the push command workflow."""
        cli = PACCCli()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a mock plugin directory
            plugin_dir = Path(temp_dir) / "test-plugin"
            plugin_dir.mkdir()
            
            # Create plugin.json
            manifest = {
                "name": "test-plugin",
                "version": "1.0.0",
                "description": "Test plugin",
                "components": ["hooks"]
            }
            (plugin_dir / "plugin.json").write_text(json.dumps(manifest))
            
            with patch('pacc.cli.PluginPusher') as mock_pusher_class, \
                 patch.object(cli, '_confirm_action', return_value=True):
                
                mock_pusher = Mock()
                mock_pusher_class.return_value = mock_pusher
                mock_pusher.push_plugin.return_value = True
                
                args = Mock()
                args.plugin = str(plugin_dir)
                args.repo = "https://github.com/test/repo.git"
                args.private = False
                args.auth = "https"
                
                result = cli.handle_plugin_push(args)
                
                assert result == 0
                
                # Verify pusher was called with correct arguments
                mock_pusher.push_plugin.assert_called_once_with(
                    plugin_dir,
                    "https://github.com/test/repo.git",
                    private=False,
                    auth_method="https"
                )


if __name__ == "__main__":
    pytest.main([__file__])