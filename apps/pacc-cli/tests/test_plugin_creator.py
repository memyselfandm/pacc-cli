"""Comprehensive tests for plugin creation functionality."""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from dataclasses import dataclass

from pacc.plugins.creator import (
    PluginCreator,
    PluginTemplate,
    CreationPluginType,
    CreationMode,
    CreationResult,
    TemplateEngine,
    GitInitializer,
    MetadataCollector
)
from pacc.errors.exceptions import PACCError, ValidationError


class TestCreationPluginType:
    """Test plugin type enumeration."""
    
    def test_plugin_types_exist(self):
        """Test that all required plugin types are defined."""
        assert hasattr(CreationPluginType, 'HOOKS')
        assert hasattr(CreationPluginType, 'AGENTS')
        assert hasattr(CreationPluginType, 'COMMANDS')
        assert hasattr(CreationPluginType, 'MCP')
        
    def test_plugin_type_values(self):
        """Test plugin type string values."""
        assert CreationPluginType.HOOKS.value == 'hooks'
        assert CreationPluginType.AGENTS.value == 'agents'
        assert CreationPluginType.COMMANDS.value == 'commands'
        assert CreationPluginType.MCP.value == 'mcp'


class TestCreationMode:
    """Test creation mode enumeration."""
    
    def test_creation_modes_exist(self):
        """Test that all creation modes are defined."""
        assert hasattr(CreationMode, 'GUIDED')
        assert hasattr(CreationMode, 'QUICK')
        
    def test_creation_mode_values(self):
        """Test creation mode string values."""
        assert CreationMode.GUIDED.value == 'guided'
        assert CreationMode.QUICK.value == 'quick'


class TestMetadataCollector:
    """Test metadata collection for plugin creation."""
    
    def test_collect_basic_metadata_guided(self):
        """Test collecting basic metadata in guided mode."""
        collector = MetadataCollector()
        
        with patch('builtins.input', side_effect=[
            'my-awesome-plugin',
            '1.0.0',
            'An awesome plugin for testing',
            'Test Author',
            'test@example.com',
            'https://github.com/testuser'
        ]):
            metadata = collector.collect_basic_metadata(CreationMode.GUIDED)
            
        assert metadata['name'] == 'my-awesome-plugin'
        assert metadata['version'] == '1.0.0'
        assert metadata['description'] == 'An awesome plugin for testing'
        assert metadata['author']['name'] == 'Test Author'
        assert metadata['author']['email'] == 'test@example.com'
        assert metadata['author']['url'] == 'https://github.com/testuser'
    
    def test_collect_basic_metadata_quick(self):
        """Test collecting basic metadata in quick mode."""
        collector = MetadataCollector()
        
        with patch('builtins.input', side_effect=['my-plugin']):
            metadata = collector.collect_basic_metadata(CreationMode.QUICK)
            
        assert metadata['name'] == 'my-plugin'
        assert metadata['version'] == '1.0.0'  # Default
        assert 'description' not in metadata
    
    def test_validate_plugin_name(self):
        """Test plugin name validation."""
        collector = MetadataCollector()
        
        # Valid names
        assert collector._validate_name('my-plugin') is True
        assert collector._validate_name('MyPlugin123') is True
        assert collector._validate_name('test_plugin') is True
        
        # Invalid names
        assert collector._validate_name('') is False
        assert collector._validate_name('my plugin') is False  # spaces
        assert collector._validate_name('plugin@test') is False  # special chars
        assert collector._validate_name('123plugin') is True  # numbers allowed
    
    def test_collect_with_retries_on_invalid_name(self):
        """Test retry logic for invalid plugin names."""
        collector = MetadataCollector()
        
        with patch('builtins.input', side_effect=[
            'invalid name',  # First attempt - invalid
            'my-valid-plugin'  # Second attempt - valid
        ]):
            metadata = collector.collect_basic_metadata(CreationMode.QUICK)
            
        assert metadata['name'] == 'my-valid-plugin'
    
    def test_collect_with_predefined_name(self):
        """Test collecting metadata with predefined name."""
        collector = MetadataCollector()
        
        # No input should be needed for name when it's predefined
        metadata = collector.collect_basic_metadata(CreationMode.QUICK, name='predefined-plugin')
        
        assert metadata['name'] == 'predefined-plugin'
        assert metadata['version'] == '1.0.0'


class TestTemplateEngine:
    """Test template engine for generating plugin files."""
    
    def test_get_template_for_hooks(self):
        """Test getting template for hooks plugin."""
        engine = TemplateEngine()
        template = engine.get_template(CreationPluginType.HOOKS)
        
        assert isinstance(template, PluginTemplate)
        assert template.plugin_type == CreationPluginType.HOOKS
        assert 'hooks' in template.directories
        assert '.gitignore' in template.files
        
    def test_get_template_for_agents(self):
        """Test getting template for agents plugin."""
        engine = TemplateEngine()
        template = engine.get_template(CreationPluginType.AGENTS)
        
        assert isinstance(template, PluginTemplate)
        assert template.plugin_type == CreationPluginType.AGENTS
        assert 'agents' in template.directories
        
    def test_get_template_for_commands(self):
        """Test getting template for commands plugin."""
        engine = TemplateEngine()
        template = engine.get_template(CreationPluginType.COMMANDS)
        
        assert isinstance(template, PluginTemplate)
        assert template.plugin_type == CreationPluginType.COMMANDS
        assert 'commands' in template.directories
        
    def test_get_template_for_mcp(self):
        """Test getting template for MCP servers plugin."""
        engine = TemplateEngine()
        template = engine.get_template(CreationPluginType.MCP)
        
        assert isinstance(template, PluginTemplate)
        assert template.plugin_type == CreationPluginType.MCP
        assert 'mcp.json' in template.files
    
    def test_render_template_with_metadata(self):
        """Test rendering template with metadata substitution."""
        engine = TemplateEngine()
        template = engine.get_template(CreationPluginType.HOOKS)
        
        metadata = {
            'name': 'test-plugin',
            'version': '1.0.0',
            'description': 'Test plugin',
            'author': {'name': 'Test Author'}
        }
        
        rendered = engine.render_template(template, metadata)
        
        # Check that metadata was substituted
        manifest_content = rendered['plugin.json']
        manifest = json.loads(manifest_content)
        assert manifest['name'] == 'test-plugin'
        assert manifest['version'] == '1.0.0'
        assert manifest['description'] == 'Test plugin'


class TestGitInitializer:
    """Test Git repository initialization."""
    
    def test_init_git_repo_success(self, tmp_path):
        """Test successful Git repository initialization."""
        initializer = GitInitializer()
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            result = initializer.init_repository(tmp_path)
            
        assert result is True
        mock_run.assert_called_once()
        
    def test_init_git_repo_failure(self, tmp_path):
        """Test Git initialization failure handling."""
        initializer = GitInitializer()
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")
            result = initializer.init_repository(tmp_path)
            
        assert result is False
    
    def test_create_gitignore(self, tmp_path):
        """Test .gitignore file creation."""
        initializer = GitInitializer()
        initializer.create_gitignore(tmp_path)
        
        gitignore_path = tmp_path / '.gitignore'
        assert gitignore_path.exists()
        
        content = gitignore_path.read_text()
        assert '__pycache__/' in content
        assert '*.py[cod]' in content  # More comprehensive than *.pyc
        assert '.env' in content


class TestPluginCreator:
    """Test main plugin creator functionality."""
    
    def test_create_plugin_guided_mode(self, tmp_path):
        """Test creating plugin in guided mode."""
        creator = PluginCreator()
        
        with patch('builtins.input', side_effect=[
            'hooks',  # Plugin type
            'test-plugin',  # Name
            '1.0.0',  # Version
            'Test plugin',  # Description
            'Test Author',  # Author name
            'test@example.com',  # Author email
            '',  # Author URL (empty)
            'y'  # Initialize git
        ]):
            result = creator.create_plugin(
                output_dir=tmp_path,
                mode=CreationMode.GUIDED
            )
        
        assert result.success is True
        assert result.plugin_path.exists()
        assert (result.plugin_path / 'plugin.json').exists()
        assert (result.plugin_path / 'hooks').exists()
        assert (result.plugin_path / '.gitignore').exists()
    
    def test_create_plugin_quick_mode(self, tmp_path):
        """Test creating plugin in quick mode."""
        creator = PluginCreator()
        
        with patch('builtins.input', side_effect=[
            'agents',  # Plugin type
            'quick-plugin'  # Name
        ]):
            result = creator.create_plugin(
                output_dir=tmp_path,
                mode=CreationMode.QUICK
            )
        
        assert result.success is True
        assert result.plugin_path.exists()
        assert (result.plugin_path / 'plugin.json').exists()
        assert (result.plugin_path / 'agents').exists()
    
    def test_create_plugin_with_name_parameter(self, tmp_path):
        """Test creating plugin with pre-specified name."""
        creator = PluginCreator()
        
        with patch('builtins.input', side_effect=['3']):  # Commands type (option 3)
            result = creator.create_plugin(
                name='preset-plugin',
                output_dir=tmp_path,
                mode=CreationMode.QUICK
            )
        
        if not result.success:
            print(f"Creation failed: {result.error_message}")
        assert result.success is True
        assert result.plugin_path.name == 'preset-plugin'
    
    def test_create_plugin_with_type_parameter(self, tmp_path):
        """Test creating plugin with pre-specified type."""
        creator = PluginCreator()
        
        with patch('builtins.input', side_effect=['mcp-plugin']):  # Just name
            result = creator.create_plugin(
                plugin_type=CreationPluginType.MCP,
                output_dir=tmp_path,
                mode=CreationMode.QUICK
            )
        
        assert result.success is True
        assert (result.plugin_path / 'mcp.json').exists()
    
    def test_create_plugin_directory_exists_error(self, tmp_path):
        """Test error when plugin directory already exists."""
        creator = PluginCreator()
        existing_dir = tmp_path / 'existing-plugin'
        existing_dir.mkdir()
        
        with patch('builtins.input', side_effect=[
            'hooks',
            'existing-plugin'
        ]):
            result = creator.create_plugin(
                output_dir=tmp_path,
                mode=CreationMode.QUICK
            )
        
        assert result.success is False
        assert 'already exists' in result.error_message
    
    def test_generate_manifest_from_existing_files(self, tmp_path):
        """Test generating manifest from existing plugin files."""
        creator = PluginCreator()
        
        # Create existing plugin structure
        plugin_dir = tmp_path / 'existing-plugin'
        plugin_dir.mkdir()
        
        # Create hooks
        hooks_dir = plugin_dir / 'hooks'
        hooks_dir.mkdir()
        (hooks_dir / 'test-hook.json').write_text('{"event": "PreToolUse"}')
        
        # Create agents
        agents_dir = plugin_dir / 'agents'
        agents_dir.mkdir()
        (agents_dir / 'test-agent.md').write_text('# Test Agent\n---\nname: test\n---')
        
        manifest = creator.generate_manifest_from_files(plugin_dir)
        
        assert 'hooks' in manifest['components']
        assert 'agents' in manifest['components']
        assert len(manifest['components']['hooks']) == 1
        assert len(manifest['components']['agents']) == 1
    
    def test_scaffold_generation_creates_directories(self, tmp_path):
        """Test that scaffold generation creates proper directory structure."""
        creator = PluginCreator()
        template_engine = TemplateEngine()
        
        template = template_engine.get_template(CreationPluginType.HOOKS)
        metadata = {'name': 'test-plugin', 'version': '1.0.0'}
        
        plugin_path = creator._create_scaffold(
            template=template,
            metadata=metadata,
            output_dir=tmp_path
        )
        
        assert plugin_path.exists()
        assert (plugin_path / 'hooks').exists()
        # Note: _create_scaffold only creates directories, not files
        assert plugin_path.name == 'test-plugin'


class TestCreationResult:
    """Test creation result data structure."""
    
    def test_successful_creation_result(self, tmp_path):
        """Test successful creation result."""
        plugin_path = tmp_path / 'test-plugin'
        result = CreationResult(
            success=True,
            plugin_path=plugin_path,
            created_files=['plugin.json', 'hooks/test.json'],
            git_initialized=True
        )
        
        assert result.success is True
        assert result.plugin_path == plugin_path
        assert len(result.created_files) == 2
        assert result.git_initialized is True
        assert result.error_message is None
    
    def test_failed_creation_result(self):
        """Test failed creation result."""
        result = CreationResult(
            success=False,
            error_message="Plugin directory already exists"
        )
        
        assert result.success is False
        assert result.error_message == "Plugin directory already exists"
        assert result.plugin_path is None
        assert result.created_files == []
    
    def test_to_dict_conversion(self, tmp_path):
        """Test converting result to dictionary."""
        plugin_path = tmp_path / 'test-plugin'
        result = CreationResult(
            success=True,
            plugin_path=plugin_path,
            created_files=['plugin.json'],
            git_initialized=False
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['success'] is True
        assert result_dict['plugin_path'] == str(plugin_path)
        assert result_dict['created_files'] == ['plugin.json']
        assert result_dict['git_initialized'] is False


class TestIntegrationScenarios:
    """Test integration scenarios and edge cases."""
    
    def test_full_guided_workflow_hooks_plugin(self, tmp_path):
        """Test complete guided workflow for hooks plugin."""
        creator = PluginCreator()
        
        with patch('builtins.input', side_effect=[
            'hooks',
            'my-hooks-plugin',
            '2.1.0',
            'A comprehensive hooks plugin for testing',
            'Jane Developer',
            'jane@dev.com',
            'https://github.com/jane',
            'y'  # Initialize git
        ]):
            with patch('subprocess.run') as mock_git:
                mock_git.return_value.returncode = 0
                result = creator.create_plugin(
                    output_dir=tmp_path,
                    mode=CreationMode.GUIDED
                )
        
        # Verify result
        assert result.success is True
        assert result.git_initialized is True
        
        # Verify directory structure
        plugin_path = result.plugin_path
        assert plugin_path.exists()
        assert (plugin_path / 'plugin.json').exists()
        assert (plugin_path / 'hooks').is_dir()
        assert (plugin_path / '.gitignore').exists()
        
        # Verify manifest content
        with open(plugin_path / 'plugin.json') as f:
            manifest = json.load(f)
        
        assert manifest['name'] == 'my-hooks-plugin'
        assert manifest['version'] == '2.1.0'
        assert manifest['description'] == 'A comprehensive hooks plugin for testing'
        assert manifest['author']['name'] == 'Jane Developer'
        assert manifest['author']['email'] == 'jane@dev.com'
        assert manifest['author']['url'] == 'https://github.com/jane'
    
    def test_quick_workflow_all_plugin_types(self, tmp_path):
        """Test quick workflow for all plugin types."""
        creator = PluginCreator()
        
        plugin_types = [CreationPluginType.HOOKS, CreationPluginType.AGENTS, CreationPluginType.COMMANDS, CreationPluginType.MCP]
        
        for i, plugin_type in enumerate(plugin_types):
            plugin_name = f'test-{plugin_type.value}-{i}'
            
            result = creator.create_plugin(
                name=plugin_name,
                plugin_type=plugin_type,
                output_dir=tmp_path,
                mode=CreationMode.QUICK
            )
            
            assert result.success is True
            assert result.plugin_path.name == plugin_name
            
            # Check type-specific directory/file exists
            if plugin_type == CreationPluginType.MCP:
                assert (result.plugin_path / 'mcp.json').exists()
            else:
                assert (result.plugin_path / plugin_type.value).is_dir()