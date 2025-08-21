#!/usr/bin/env python3
"""Integration tests for the conversion system.

This module tests the complete conversion workflow including:
- Extension scanning and conversion
- Plugin generation and Git repository creation
- Push functionality with authentication
- Batch conversion workflows
- Integration with existing plugin install commands
- Error recovery and rollback scenarios
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock

# Import the conversion system components
from pacc.plugins.converter import (
    PluginConverter, 
    ExtensionToPluginConverter,
    ExtensionInfo,
    ConversionResult,
    convert_extensions_to_plugin
)
from pacc.plugins.repository import (
    PluginRepositoryManager,
    PluginRepo,
    UpdateResult,
    RepositoryValidationResult
)
from pacc.cli import PACCCli
from pacc.errors import PACCError, ValidationError


class ConversionIntegrationTestCase(unittest.TestCase):
    """Base test case for conversion integration tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(self._cleanup_temp_dir)
        
        # Create test directory structure
        self.test_project_dir = self.temp_dir / "test_project"
        self.test_project_dir.mkdir()
        
        self.claude_dir = self.test_project_dir / ".claude"
        self.claude_dir.mkdir()
        
        self.output_dir = self.temp_dir / "converted_plugins"
        self.output_dir.mkdir()
        
        # Initialize components
        self.converter = PluginConverter()
        self.cli_converter = ExtensionToPluginConverter(output_dir=self.output_dir)
        self.repo_manager = PluginRepositoryManager(plugins_dir=self.temp_dir / "plugins")
        
    def _cleanup_temp_dir(self):
        """Clean up temporary directory."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_hook(self, name: str, events: List[str] = None) -> Path:
        """Create a test hook file."""
        if events is None:
            events = ["PreToolUse", "PostToolUse"]
        
        hooks_dir = self.claude_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        
        hook_file = hooks_dir / f"{name}.json"
        hook_data = {
            "name": f"{name}_hook",
            "eventTypes": events,
            "commands": [f"echo 'Hook {name} triggered'"],
            "description": f"Test hook for {name}",
            "version": "1.0.0"
        }
        
        with open(hook_file, 'w') as f:
            json.dump(hook_data, f, indent=2)
        
        return hook_file
    
    def _create_test_agent(self, name: str, tools: List[str] = None) -> Path:
        """Create a test agent file."""
        if tools is None:
            tools = ["file_editor", "web_search"]
        
        agents_dir = self.claude_dir / "agents"
        agents_dir.mkdir(exist_ok=True)
        
        agent_file = agents_dir / f"{name}.md"
        agent_content = f"""---
name: {name}
description: Test agent for {name}
tools: {json.dumps(tools)}
---

# {name} Agent

This is a test agent for integration testing.

## Instructions

You are a specialized agent for {name} tasks.
"""
        
        with open(agent_file, 'w') as f:
            f.write(agent_content)
        
        return agent_file
    
    def _create_test_command(self, name: str, namespace: str = None) -> Path:
        """Create a test command file."""
        commands_dir = self.claude_dir / "commands"
        if namespace:
            commands_dir = commands_dir / namespace
        commands_dir.mkdir(parents=True, exist_ok=True)
        
        command_file = commands_dir / f"{name}.md"
        command_content = f"""# {name} Command

Custom command for {name} functionality.

## Usage

Use this command to perform {name} operations.

## Examples

```
/{name} --help
```
"""
        
        with open(command_file, 'w') as f:
            f.write(command_content)
        
        return command_file
    
    def _create_test_mcp(self, name: str, command: str = None) -> Path:
        """Create a test MCP server configuration."""
        if command is None:
            command = f"python -m {name}_mcp"
        
        mcp_dir = self.claude_dir / "mcp"
        mcp_dir.mkdir(exist_ok=True)
        
        mcp_file = mcp_dir / f"{name}.json"
        mcp_data = {
            "mcpServers": {
                name: {
                    "command": command,
                    "args": [],
                    "env": {}
                }
            }
        }
        
        with open(mcp_file, 'w') as f:
            json.dump(mcp_data, f, indent=2)
        
        return mcp_file
    
    def _validate_plugin_structure(self, plugin_path: Path) -> bool:
        """Validate that a plugin has the expected structure."""
        if not plugin_path.exists() or not plugin_path.is_dir():
            return False
        
        # Check for plugin.json
        manifest_path = plugin_path / "plugin.json"
        if not manifest_path.exists():
            return False
        
        # Validate manifest content
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            required_fields = ["name", "version", "description"]
            if not all(field in manifest for field in required_fields):
                return False
        except (json.JSONDecodeError, IOError):
            return False
        
        return True


class TestEndToEndConversionWorkflow(ConversionIntegrationTestCase):
    """Test complete end-to-end conversion workflow."""
    
    def test_scan_convert_generate_workflow(self):
        """Test complete workflow: scan → convert → generate."""
        # Create test extensions
        hook_file = self._create_test_hook("test_hook")
        agent_file = self._create_test_agent("test_agent")
        command_file = self._create_test_command("test_command")
        mcp_file = self._create_test_mcp("test_mcp")
        
        # Step 1: Scan for extensions
        extensions = self.converter.scan_extensions(self.test_project_dir)
        
        self.assertGreater(len(extensions), 0, "Should discover extensions")
        extension_types = {ext.extension_type for ext in extensions}
        self.assertIn("hooks", extension_types)
        self.assertIn("agents", extension_types)
        self.assertIn("commands", extension_types)
        self.assertIn("mcp", extension_types)
        
        # Step 2: Convert to plugin
        result = self.converter.convert_to_plugin(
            extensions=extensions,
            plugin_name="test_integration_plugin",
            destination=self.output_dir,
            author_name="Test Author",
            description="Integration test plugin"
        )
        
        self.assertTrue(result.success, f"Conversion should succeed: {result.errors}")
        self.assertIsNotNone(result.plugin_path)
        self.assertGreater(len(result.converted_extensions), 0)
        
        # Step 3: Validate generated plugin structure
        plugin_path = result.plugin_path
        self.assertTrue(self._validate_plugin_structure(plugin_path))
        
        # Check component directories
        self.assertTrue((plugin_path / "hooks").exists())
        self.assertTrue((plugin_path / "agents").exists())
        self.assertTrue((plugin_path / "commands").exists())
        self.assertTrue((plugin_path / "mcp").exists())
        
        # Validate manifest content
        manifest_path = plugin_path / "plugin.json"
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        self.assertEqual(manifest["name"], "test_integration_plugin")
        self.assertEqual(manifest["author"]["name"], "Test Author")
        self.assertIn("components", manifest)
        
        # Validate conversion rate
        self.assertGreaterEqual(result.conversion_rate, 95.0, "Should achieve 95%+ conversion rate")
    
    def test_git_repository_integration(self):
        """Test Git repository creation and plugin push workflow."""
        # Create and convert a plugin
        self._create_test_hook("git_test_hook")
        self._create_test_agent("git_test_agent")
        
        extensions = self.converter.scan_extensions(self.test_project_dir)
        result = self.converter.convert_to_plugin(
            extensions=extensions,
            plugin_name="git_test_plugin",
            destination=self.output_dir
        )
        
        self.assertTrue(result.success)
        plugin_path = result.plugin_path
        
        # Create Git repository
        plugin_metadata = {"name": "git_test_plugin", "version": "1.0.0"}
        repo_created = self.repo_manager.create_plugin_repository(
            plugin_path, 
            plugin_metadata,
            init_git=True
        )
        
        self.assertTrue(repo_created, "Git repository should be created")
        self.assertTrue((plugin_path / ".git").exists())
        self.assertTrue((plugin_path / "README.md").exists())
        self.assertTrue((plugin_path / ".gitignore").exists())
        
        # Validate README content
        readme_content = (plugin_path / "README.md").read_text()
        self.assertIn("git_test_plugin", readme_content)
        self.assertIn("Installation", readme_content)
        self.assertIn("pacc plugin install", readme_content)
        
        # Commit plugin
        commit_success = self.repo_manager.commit_plugin(plugin_path)
        self.assertTrue(commit_success, "Initial commit should succeed")


class TestBatchConversion(ConversionIntegrationTestCase):
    """Test batch conversion of multiple extensions."""
    
    def test_batch_conversion_multiple_extensions(self):
        """Test converting multiple extensions in batch mode."""
        # Create multiple test extensions
        extensions_data = [
            ("hook1", "hooks"),
            ("hook2", "hooks"),
            ("agent1", "agents"),
            ("agent2", "agents"),
            ("cmd1", "commands"),
            ("cmd2", "commands"),
            ("mcp1", "mcp"),
            ("mcp2", "mcp")
        ]
        
        for name, ext_type in extensions_data:
            if ext_type == "hooks":
                self._create_test_hook(name)
            elif ext_type == "agents":
                self._create_test_agent(name)
            elif ext_type == "commands":
                self._create_test_command(name)
            elif ext_type == "mcp":
                self._create_test_mcp(name)
        
        # Perform batch conversion
        result = convert_extensions_to_plugin(
            source_directory=self.test_project_dir,
            plugin_name="batch_test_plugin",
            destination=self.output_dir,
            author_name="Batch Test Author"
        )
        
        self.assertTrue(result.success, f"Batch conversion should succeed: {result.errors}")
        self.assertGreaterEqual(len(result.converted_extensions), 6, "Should convert multiple extensions")
        
        # Validate all extension types are represented
        converted_types = {ext.extension_type for ext in result.converted_extensions}
        expected_types = {"hooks", "agents", "commands", "mcp"}
        self.assertTrue(expected_types.issubset(converted_types))
        
        # Validate conversion rate
        self.assertGreaterEqual(result.conversion_rate, 95.0)
    
    def test_cli_batch_conversion(self):
        """Test batch conversion through CLI interface."""
        # Create test extensions
        self._create_test_hook("cli_hook")
        self._create_test_agent("cli_agent")
        self._create_test_command("cli_command")
        
        # Test CLI batch conversion
        results = self.cli_converter.convert_directory(
            source_dir=self.test_project_dir,
            metadata_defaults={"author": "CLI Test Author", "version": "2.0.0"},
            overwrite=True
        )
        
        self.assertGreater(len(results), 0, "Should produce conversion results")
        success_count = sum(1 for r in results if r.success)
        self.assertGreater(success_count, 0, "Should have successful conversions")


class TestPluginCompatibility(ConversionIntegrationTestCase):
    """Test that converted plugins work with existing plugin install command."""
    
    def test_converted_plugin_install_compatibility(self):
        """Test that converted plugins can be installed via plugin install command."""
        # Create and convert a plugin
        self._create_test_hook("install_test_hook")
        self._create_test_agent("install_test_agent")
        
        result = convert_extensions_to_plugin(
            source_directory=self.test_project_dir,
            plugin_name="install_compatibility_plugin",
            destination=self.output_dir
        )
        
        self.assertTrue(result.success)
        plugin_path = result.plugin_path
        
        # Validate repository structure for plugin system
        validation_result = self.repo_manager.validate_repository_structure(plugin_path.parent)
        self.assertTrue(validation_result.is_valid, 
                       f"Converted plugin should be valid: {validation_result.error_message}")
        self.assertIn("install_compatibility_plugin", validation_result.plugins_found)
        
        # Test plugin discovery
        plugin_info = self.repo_manager.get_plugin_info(plugin_path.parent)
        self.assertIn("install_compatibility_plugin", plugin_info.plugins)
    
    @patch('subprocess.run')
    def test_converted_plugin_with_existing_install_flow(self, mock_run):
        """Test integration with existing plugin install workflow."""
        # Mock successful git operations
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        # Create and convert a plugin
        self._create_test_hook("flow_test_hook")
        
        result = convert_extensions_to_plugin(
            source_directory=self.test_project_dir,
            plugin_name="flow_test_plugin",
            destination=self.output_dir
        )
        
        self.assertTrue(result.success)
        
        # Simulate plugin repository structure
        repo_dir = self.temp_dir / "plugins" / "repos" / "test_owner" / "test_repo"
        repo_dir.mkdir(parents=True)
        shutil.copytree(result.plugin_path, repo_dir / "flow_test_plugin")
        
        # Test plugin discovery in repository context
        plugins = self.repo_manager._discover_plugins_in_repo(repo_dir)
        self.assertIn("flow_test_plugin", plugins)


class TestGitPushAuthentication(ConversionIntegrationTestCase):
    """Test Git push functionality with various authentication methods."""
    
    @patch('subprocess.run')
    def test_https_token_authentication(self, mock_run):
        """Test HTTPS push with token authentication."""
        # Mock successful git operations
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        # Create a test plugin
        plugin_path = self.output_dir / "https_test_plugin"
        plugin_path.mkdir()
        
        # Create minimal plugin structure
        (plugin_path / "plugin.json").write_text(json.dumps({
            "name": "https_test_plugin",
            "version": "1.0.0",
            "description": "Test plugin"
        }))
        
        # Create basic plugin structure to pass validation
        (plugin_path / "commands").mkdir()
        (plugin_path / "commands" / "test.md").write_text("# Test Command")
        
        # Initialize Git repository
        success = self.repo_manager.create_plugin_repository(
            plugin_path,
            {"name": "https_test_plugin"},
            init_git=True
        )
        self.assertTrue(success)
        
        # Manually create .git directory since we're mocking subprocess
        (plugin_path / ".git").mkdir()
        
        # Test HTTPS push with token
        auth = {"token": "test_token_123"}
        push_success = self.repo_manager.push_plugin(
            plugin_path,
            "https://github.com/test/repo.git",
            auth=auth
        )
        
        self.assertTrue(push_success)
        
        # Verify git commands were called correctly
        git_calls = [call for call in mock_run.call_args_list if call[0][0][0] == "git"]
        self.assertGreater(len(git_calls), 0, "Should make git calls")
    
    @patch('subprocess.run')
    def test_ssh_authentication(self, mock_run):
        """Test SSH push authentication."""
        # Mock successful git operations
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        # Create test plugin
        plugin_path = self.output_dir / "ssh_test_plugin"
        plugin_path.mkdir()
        (plugin_path / "plugin.json").write_text(json.dumps({
            "name": "ssh_test_plugin",
            "version": "1.0.0",
            "description": "SSH test plugin"
        }))
        
        # Create basic plugin structure to pass validation
        (plugin_path / "commands").mkdir()
        (plugin_path / "commands" / "test.md").write_text("# Test Command")
        
        # Initialize Git repository
        self.repo_manager.create_plugin_repository(
            plugin_path,
            {"name": "ssh_test_plugin"},
            init_git=True
        )
        
        # Manually create .git directory since we're mocking subprocess
        (plugin_path / ".git").mkdir()
        
        # Test SSH push (no auth dict needed for SSH)
        push_success = self.repo_manager.push_plugin(
            plugin_path,
            "git@github.com:test/repo.git"
        )
        
        self.assertTrue(push_success)
    
    @patch('subprocess.run')
    def test_authentication_error_handling(self, mock_run):
        """Test handling of authentication failures."""
        plugin_path = self.output_dir / "auth_fail_plugin"
        plugin_path.mkdir()
        (plugin_path / "plugin.json").write_text(json.dumps({
            "name": "auth_fail_plugin",
            "version": "1.0.0",
            "description": "Auth failure test"
        }))
        
        # Create basic plugin structure to pass validation
        (plugin_path / "commands").mkdir()
        (plugin_path / "commands" / "test.md").write_text("# Test Command")
        
        # Mock successful git init but failed push
        def mock_subprocess_run(*args, **kwargs):
            cmd = args[0]
            if cmd[0] == "git" and cmd[1] == "init":
                return Mock(returncode=0, stdout="", stderr="")
            elif cmd[0] == "git" and cmd[1] == "push":
                return Mock(returncode=1, stdout="", stderr="Authentication failed")
            else:
                return Mock(returncode=0, stdout="", stderr="")
        
        mock_run.side_effect = mock_subprocess_run
        
        self.repo_manager.create_plugin_repository(
            plugin_path,
            {"name": "auth_fail_plugin"},
            init_git=True
        )
        
        # Manually create .git directory since we're mocking subprocess
        (plugin_path / ".git").mkdir()
        
        # Push should fail gracefully
        push_success = self.repo_manager.push_plugin(
            plugin_path,
            "https://github.com/test/private-repo.git"
        )
        
        self.assertFalse(push_success, "Push should fail with authentication error")


class TestErrorRecoveryAndRollback(ConversionIntegrationTestCase):
    """Test error recovery and rollback scenarios."""
    
    def test_conversion_error_recovery(self):
        """Test recovery from conversion errors."""
        # Create a valid extension
        self._create_test_hook("valid_hook")
        
        # Create an invalid extension (corrupted JSON)
        invalid_hooks_dir = self.claude_dir / "hooks"
        invalid_hooks_dir.mkdir(exist_ok=True)
        invalid_hook_file = invalid_hooks_dir / "invalid_hook.json"
        invalid_hook_file.write_text("{ invalid json content")
        
        # Conversion should handle errors gracefully
        extensions = self.converter.scan_extensions(self.test_project_dir)
        
        # Should find valid extension and mark invalid one appropriately
        valid_extensions = [ext for ext in extensions if ext.is_valid]
        invalid_extensions = [ext for ext in extensions if not ext.is_valid]
        
        self.assertGreater(len(valid_extensions), 0, "Should find valid extensions")
        self.assertGreater(len(invalid_extensions), 0, "Should identify invalid extensions")
        
        # Conversion should succeed with valid extensions only
        result = self.converter.convert_to_plugin(
            extensions=valid_extensions,
            plugin_name="recovery_test_plugin",
            destination=self.output_dir
        )
        
        self.assertTrue(result.success)
        self.assertGreater(len(result.converted_extensions), 0)
        self.assertEqual(len(result.skipped_extensions), 0)  # No skipped since we filtered
    
    def test_git_rollback_functionality(self):
        """Test Git rollback capabilities."""
        # Create test repository
        test_repo = self.temp_dir / "test_rollback_repo"
        test_repo.mkdir()
        
        # Initialize git repository with subprocess (real git for rollback test)
        try:
            subprocess.run(["git", "init"], cwd=test_repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], 
                         cwd=test_repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], 
                         cwd=test_repo, check=True, capture_output=True)
            
            # Create initial commit
            test_file = test_repo / "initial.txt"
            test_file.write_text("Initial content")
            subprocess.run(["git", "add", "."], cwd=test_repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], 
                         cwd=test_repo, check=True, capture_output=True)
            
            # Get initial commit SHA
            initial_sha_result = subprocess.run(
                ["git", "log", "-1", "--format=%H"], 
                cwd=test_repo, 
                check=True, 
                capture_output=True, 
                text=True
            )
            initial_sha = initial_sha_result.stdout.strip()
            
            # Make another commit
            test_file.write_text("Modified content")
            subprocess.run(["git", "add", "."], cwd=test_repo, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Second commit"], 
                         cwd=test_repo, check=True, capture_output=True)
            
            # Test rollback to initial commit
            rollback_success = self.repo_manager.rollback_plugin(test_repo, initial_sha)
            self.assertTrue(rollback_success, "Rollback should succeed")
            
            # Verify content was rolled back
            self.assertEqual(test_file.read_text(), "Initial content")
            
        except subprocess.CalledProcessError:
            self.skipTest("Git not available for rollback test")
        except FileNotFoundError:
            self.skipTest("Git command not found")


class TestPerformanceTesting(ConversionIntegrationTestCase):
    """Test performance of conversion system."""
    
    def test_large_extension_conversion_performance(self):
        """Test conversion performance with large number of extensions."""
        import time
        
        # Create many test extensions
        num_extensions = 50
        
        start_time = time.time()
        
        for i in range(num_extensions // 4):
            self._create_test_hook(f"perf_hook_{i}")
            self._create_test_agent(f"perf_agent_{i}")
            self._create_test_command(f"perf_command_{i}")
            self._create_test_mcp(f"perf_mcp_{i}")
        
        # Scan extensions
        scan_start = time.time()
        extensions = self.converter.scan_extensions(self.test_project_dir)
        scan_time = time.time() - scan_start
        
        self.assertGreaterEqual(len(extensions), num_extensions * 0.9, 
                              "Should find most created extensions")
        
        # Convert extensions
        convert_start = time.time()
        result = self.converter.convert_to_plugin(
            extensions=extensions,
            plugin_name="performance_test_plugin",
            destination=self.output_dir
        )
        convert_time = time.time() - convert_start
        
        total_time = time.time() - start_time
        
        self.assertTrue(result.success, "Performance test conversion should succeed")
        
        # Performance benchmarks (adjust based on system capabilities)
        self.assertLess(scan_time, 5.0, "Scanning should complete within 5 seconds")
        self.assertLess(convert_time, 10.0, "Conversion should complete within 10 seconds")
        self.assertLess(total_time, 20.0, "Total workflow should complete within 20 seconds")
        
        # Conversion rate should remain high under load
        self.assertGreaterEqual(result.conversion_rate, 95.0)
    
    def test_batch_conversion_memory_usage(self):
        """Test memory efficiency during batch conversion."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create moderate number of extensions
        for i in range(20):
            self._create_test_hook(f"mem_hook_{i}")
            self._create_test_agent(f"mem_agent_{i}")
        
        # Perform conversion
        result = convert_extensions_to_plugin(
            source_directory=self.test_project_dir,
            plugin_name="memory_test_plugin",
            destination=self.output_dir
        )
        
        # Check final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        self.assertTrue(result.success)
        self.assertLess(memory_increase, 100, "Memory increase should be reasonable (<100MB)")


class TestCLIIntegration(ConversionIntegrationTestCase):
    """Test CLI integration for conversion commands."""
    
    def test_plugin_convert_command_integration(self):
        """Test plugin convert command through CLI interface."""
        # Create test extension
        hook_file = self._create_test_hook("cli_integration_hook")
        
        # Simulate CLI args (use batch mode since passing directory)
        from argparse import Namespace
        args = Namespace(
            extension=str(self.test_project_dir),
            name="cli_integration_plugin",
            version="1.0.0",
            author="CLI Integration Test",
            repo=None,
            local=True,
            batch=True,
            output=self.output_dir,
            overwrite=True
        )
        
        # Test CLI handler (mock interactive inputs)
        cli = PACCCli()
        
        with patch('builtins.input', return_value=''):  # Mock empty inputs for auto-generation
            result_code = cli.handle_plugin_convert(args)
        
        self.assertEqual(result_code, 0, "CLI convert command should succeed")
        
        # Verify plugin was created
        plugin_files = list(self.output_dir.glob("*/plugin.json"))
        self.assertGreater(len(plugin_files), 0, "Should create plugin")
    
    def test_plugin_push_command_integration(self):
        """Test plugin push command through CLI interface."""
        # Create test plugin
        plugin_path = self.output_dir / "push_test_plugin"
        plugin_path.mkdir()
        
        (plugin_path / "plugin.json").write_text(json.dumps({
            "name": "push_test_plugin", 
            "version": "1.0.0",
            "description": "Push test plugin"
        }))
        
        # Simulate CLI args
        from argparse import Namespace
        args = Namespace(
            plugin=str(plugin_path),
            repo="https://github.com/test/push-test.git",
            private=False,
            auth="https"
        )
        
        # Test CLI handler with mocked operations
        cli = PACCCli()
        
        with patch.object(cli, '_confirm_action', return_value=True), \
             patch('pacc.plugins.converter.PluginPusher.push_plugin', return_value=True):
            result_code = cli.handle_plugin_push(args)
        
        self.assertEqual(result_code, 0, "CLI push command should succeed")


if __name__ == '__main__':
    # Set up test environment
    import logging
    logging.basicConfig(level=logging.WARNING)  # Reduce log noise during tests
    
    # Run integration tests
    unittest.main(verbosity=2)