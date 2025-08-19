"""Tests for plugin convert and push CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from pacc.cli import PACCCli
from pacc.plugins.converter import ExtensionToPluginConverter, PluginPusher, ConversionResult, PluginMetadata


class TestPluginConvertCLI:
    """Test plugin convert CLI command."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PACCCli()
    
    @pytest.fixture
    def temp_extension(self):
        """Create a temporary extension file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            hook_data = {
                "name": "test-hook",
                "eventTypes": ["PreToolUse"],
                "commands": ["echo 'test'"]
            }
            json.dump(hook_data, f)
            yield Path(f.name)
            Path(f.name).unlink(missing_ok=True)
    
    def test_convert_command_basic(self, cli, temp_extension):
        """Test basic convert command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "plugins"
            
            # Mock the converter
            with patch('pacc.cli.ExtensionToPluginConverter') as mock_converter_class:
                mock_converter = Mock()
                mock_converter_class.return_value = mock_converter
                
                # Mock successful conversion
                mock_result = ConversionResult(
                    success=True,
                    plugin_name="test-plugin",
                    plugin_path=output_dir / "test-plugin",
                    components=["hooks"]
                )
                mock_converter.convert_extension.return_value = mock_result
                
                # Mock user input for name
                with patch('builtins.input', side_effect=['test-plugin', 'Test Author']):
                    args = Mock()
                    args.extension = str(temp_extension)
                    args.name = None
                    args.author = None
                    args.version = "1.0.0"
                    args.repo = None
                    args.batch = False
                    args.output = output_dir
                    args.overwrite = False
                    
                    result = cli.handle_plugin_convert(args)
                    
                    assert result == 0
                    mock_converter.convert_extension.assert_called_once()
    
    def test_convert_command_with_flags(self, cli, temp_extension):
        """Test convert command with all flags specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "plugins"
            
            with patch('pacc.cli.ExtensionToPluginConverter') as mock_converter_class:
                mock_converter = Mock()
                mock_converter_class.return_value = mock_converter
                
                mock_result = ConversionResult(
                    success=True,
                    plugin_name="my-plugin",
                    plugin_path=output_dir / "my-plugin",
                    components=["hooks"]
                )
                mock_converter.convert_extension.return_value = mock_result
                
                args = Mock()
                args.extension = str(temp_extension)
                args.name = "my-plugin"
                args.author = "My Author"
                args.version = "2.0.0"
                args.repo = None
                args.batch = False
                args.output = output_dir
                args.overwrite = True
                
                result = cli.handle_plugin_convert(args)
                
                assert result == 0
                
                # Verify converter was called with correct metadata
                call_args = mock_converter.convert_extension.call_args
                assert call_args[1]['plugin_name'] == "my-plugin"
                assert call_args[1]['overwrite'] is True
                
                metadata = call_args[1]['metadata']
                assert metadata.name == "my-plugin"
                assert metadata.author == "My Author"
                assert metadata.version == "2.0.0"
    
    def test_convert_command_with_repo_push(self, cli, temp_extension):
        """Test convert command with direct repository push."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "plugins"
            
            with patch('pacc.cli.ExtensionToPluginConverter') as mock_converter_class, \
                 patch('pacc.cli.PluginPusher') as mock_pusher_class:
                
                mock_converter = Mock()
                mock_converter_class.return_value = mock_converter
                
                mock_pusher = Mock()
                mock_pusher_class.return_value = mock_pusher
                mock_pusher.push_plugin.return_value = True
                
                mock_result = ConversionResult(
                    success=True,
                    plugin_name="test-plugin",
                    plugin_path=output_dir / "test-plugin",
                    components=["hooks"]
                )
                mock_converter.convert_extension.return_value = mock_result
                
                with patch('builtins.input', side_effect=['test-plugin', 'Test Author']):
                    args = Mock()
                    args.extension = str(temp_extension)
                    args.name = None
                    args.author = None
                    args.version = "1.0.0"
                    args.repo = "https://github.com/test/repo.git"
                    args.batch = False
                    args.output = output_dir
                    args.overwrite = False
                    
                    result = cli.handle_plugin_convert(args)
                    
                    assert result == 0
                    mock_pusher.push_plugin.assert_called_once_with(
                        output_dir / "test-plugin",
                        "https://github.com/test/repo.git"
                    )
    
    def test_convert_batch_mode(self, cli):
        """Test convert command in batch mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "extensions"
            source_dir.mkdir()
            output_dir = Path(tmpdir) / "plugins"
            
            # Create multiple extension files
            hook1 = source_dir / "hook1.json"
            hook1.write_text(json.dumps({"name": "hook1", "eventTypes": ["PreToolUse"]}))
            
            hook2 = source_dir / "hook2.json"
            hook2.write_text(json.dumps({"name": "hook2", "eventTypes": ["PostToolUse"]}))
            
            with patch('pacc.cli.ExtensionToPluginConverter') as mock_converter_class:
                mock_converter = Mock()
                mock_converter_class.return_value = mock_converter
                
                # Mock batch conversion results
                mock_results = [
                    ConversionResult(
                        success=True,
                        plugin_name="hook1-plugin",
                        plugin_path=output_dir / "hook1-plugin",
                        components=["hooks"]
                    ),
                    ConversionResult(
                        success=True,
                        plugin_name="hook2-plugin", 
                        plugin_path=output_dir / "hook2-plugin",
                        components=["hooks"]
                    )
                ]
                mock_converter.convert_directory.return_value = mock_results
                
                with patch('builtins.input', side_effect=['', 'Test Author']):
                    args = Mock()
                    args.extension = str(source_dir)
                    args.name = None
                    args.author = None
                    args.version = "1.0.0"
                    args.repo = None
                    args.batch = True
                    args.output = output_dir
                    args.overwrite = False
                    
                    result = cli.handle_plugin_convert(args)
                    
                    assert result == 0
                    mock_converter.convert_directory.assert_called_once()
    
    def test_convert_nonexistent_path(self, cli):
        """Test convert command with nonexistent extension path."""
        args = Mock()
        args.extension = "/nonexistent/path.json"
        
        result = cli.handle_plugin_convert(args)
        
        assert result == 1
    
    def test_convert_conversion_failure(self, cli, temp_extension):
        """Test convert command when conversion fails."""
        with patch('pacc.cli.ExtensionToPluginConverter') as mock_converter_class:
            mock_converter = Mock()
            mock_converter_class.return_value = mock_converter
            
            mock_result = ConversionResult(
                success=False,
                plugin_name="test-plugin",
                error_message="Conversion failed for testing"
            )
            mock_converter.convert_extension.return_value = mock_result
            
            with patch('builtins.input', side_effect=['test-plugin', 'Test Author']):
                args = Mock()
                args.extension = str(temp_extension)
                args.name = None
                args.author = None
                args.version = "1.0.0"
                args.repo = None
                args.batch = False
                args.output = None
                args.overwrite = False
                
                result = cli.handle_plugin_convert(args)
                
                assert result == 1


class TestPluginPushCLI:
    """Test plugin push CLI command."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PACCCli()
    
    @pytest.fixture
    def temp_plugin(self):
        """Create a temporary plugin directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "test-plugin"
            plugin_dir.mkdir()
            
            # Create plugin.json manifest
            manifest = {
                "name": "test-plugin",
                "version": "1.0.0",
                "description": "Test plugin",
                "components": ["hooks"]
            }
            (plugin_dir / "plugin.json").write_text(json.dumps(manifest))
            
            # Create hooks directory and file
            hooks_dir = plugin_dir / "hooks"
            hooks_dir.mkdir()
            hooks_data = {
                "hooks": [
                    {"name": "test", "eventTypes": ["PreToolUse"], "commands": ["echo test"]}
                ]
            }
            (hooks_dir / "hooks.json").write_text(json.dumps(hooks_data))
            
            yield plugin_dir
    
    def test_push_command_basic(self, cli, temp_plugin):
        """Test basic push command."""
        with patch('pacc.cli.PluginPusher') as mock_pusher_class, \
             patch.object(cli, '_confirm_action', return_value=True):
            
            mock_pusher = Mock()
            mock_pusher_class.return_value = mock_pusher
            mock_pusher.push_plugin.return_value = True
            
            args = Mock()
            args.plugin = str(temp_plugin)
            args.repo = "https://github.com/test/repo.git"
            args.private = False
            args.auth = "https"
            
            result = cli.handle_plugin_push(args)
            
            assert result == 0
            mock_pusher.push_plugin.assert_called_once_with(
                temp_plugin,
                "https://github.com/test/repo.git",
                private=False,
                auth_method="https"
            )
    
    def test_push_command_with_flags(self, cli, temp_plugin):
        """Test push command with private and SSH auth."""
        with patch('pacc.cli.PluginPusher') as mock_pusher_class, \
             patch.object(cli, '_confirm_action', return_value=True):
            
            mock_pusher = Mock()
            mock_pusher_class.return_value = mock_pusher
            mock_pusher.push_plugin.return_value = True
            
            args = Mock()
            args.plugin = str(temp_plugin)
            args.repo = "git@github.com:test/repo.git"
            args.private = True
            args.auth = "ssh"
            
            result = cli.handle_plugin_push(args)
            
            assert result == 0
            mock_pusher.push_plugin.assert_called_once_with(
                temp_plugin,
                "git@github.com:test/repo.git",
                private=True,
                auth_method="ssh"
            )
    
    def test_push_nonexistent_plugin(self, cli):
        """Test push command with nonexistent plugin path."""
        args = Mock()
        args.plugin = "/nonexistent/plugin"
        args.repo = "https://github.com/test/repo.git"
        
        result = cli.handle_plugin_push(args)
        
        assert result == 1
    
    def test_push_invalid_plugin_structure(self, cli):
        """Test push command with invalid plugin structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            invalid_plugin = Path(tmpdir) / "invalid-plugin"
            invalid_plugin.mkdir()
            # No plugin.json file
            
            args = Mock()
            args.plugin = str(invalid_plugin)
            args.repo = "https://github.com/test/repo.git"
            
            result = cli.handle_plugin_push(args)
            
            assert result == 1
    
    def test_push_cancelled_by_user(self, cli, temp_plugin):
        """Test push command cancelled by user."""
        with patch.object(cli, '_confirm_action', return_value=False):
            args = Mock()
            args.plugin = str(temp_plugin)
            args.repo = "https://github.com/test/repo.git"
            args.private = False
            args.auth = "https"
            
            result = cli.handle_plugin_push(args)
            
            assert result == 0  # Cancelled, but not an error
    
    def test_push_failure(self, cli, temp_plugin):
        """Test push command when push fails."""
        with patch('pacc.cli.PluginPusher') as mock_pusher_class, \
             patch.object(cli, '_confirm_action', return_value=True):
            
            mock_pusher = Mock()
            mock_pusher_class.return_value = mock_pusher
            mock_pusher.push_plugin.return_value = False
            
            args = Mock()
            args.plugin = str(temp_plugin)
            args.repo = "https://github.com/test/repo.git"
            args.private = False
            args.auth = "https"
            
            result = cli.handle_plugin_push(args)
            
            assert result == 1
    
    def test_push_file_instead_of_directory(self, cli):
        """Test push command with file instead of directory."""
        with tempfile.NamedTemporaryFile() as f:
            args = Mock()
            args.plugin = f.name
            args.repo = "https://github.com/test/repo.git"
            
            result = cli.handle_plugin_push(args)
            
            assert result == 1


class TestCLIIntegration:
    """Test CLI integration and interactive features."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PACCCli()
    
    def test_interactive_prompts(self, cli):
        """Test interactive prompts for missing metadata."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            hook_data = {"name": "test", "eventTypes": ["PreToolUse"]}
            json.dump(hook_data, f)
            temp_file = Path(f.name)
        
        try:
            with patch('pacc.cli.ExtensionToPluginConverter') as mock_converter_class:
                mock_converter = Mock()
                mock_converter_class.return_value = mock_converter
                
                mock_result = ConversionResult(
                    success=True,
                    plugin_name="interactive-test",
                    plugin_path=Path("/tmp/interactive-test"),
                    components=["hooks"]
                )
                mock_converter.convert_extension.return_value = mock_result
                
                # Test interactive input handling
                with patch('builtins.input', side_effect=['interactive-test', 'Interactive Author']):
                    args = Mock()
                    args.extension = str(temp_file)
                    args.name = None  # Trigger prompt
                    args.author = None  # Trigger prompt
                    args.version = "1.0.0"
                    args.repo = None
                    args.batch = False
                    args.output = None
                    args.overwrite = False
                    
                    result = cli.handle_plugin_convert(args)
                    
                    assert result == 0
                    
                    # Verify metadata was created with prompted values
                    call_args = mock_converter.convert_extension.call_args
                    metadata = call_args[1]['metadata']
                    assert metadata.name == "interactive-test"
                    assert metadata.author == "Interactive Author"
        finally:
            temp_file.unlink(missing_ok=True)
    
    def test_keyboard_interrupt_handling(self, cli):
        """Test graceful handling of keyboard interrupts."""
        with tempfile.NamedTemporaryFile() as f:
            with patch('pacc.cli.ExtensionToPluginConverter', side_effect=KeyboardInterrupt):
                args = Mock()
                args.extension = f.name
                
                result = cli.handle_plugin_convert(args)
                
                assert result == 1
    
    def test_error_reporting(self, cli):
        """Test error reporting and user feedback."""
        with tempfile.NamedTemporaryFile() as f:
            with patch('pacc.cli.ExtensionToPluginConverter', side_effect=Exception("Test error")):
                args = Mock()
                args.extension = f.name
                
                result = cli.handle_plugin_convert(args)
                
                assert result == 1


if __name__ == "__main__":
    pytest.main([__file__])