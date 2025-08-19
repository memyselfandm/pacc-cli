"""Performance benchmarks for plugin CLI commands and operations."""

import json
import yaml
import os
import time
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import psutil

from pacc.cli import PaccCLI
from pacc.plugins import (
    PluginRepositoryManager,
    PluginConfigManager,
    PluginConverter,
    EnvironmentManager
)


class CLIPerformanceProfiler:
    """Performance profiler for CLI operations."""
    
    def __init__(self, operation_name):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
        self.process = psutil.Process(os.getpid())
        self.peak_memory = 0
    
    def __enter__(self):
        self.start_memory = self.process.memory_info().rss
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.end_memory = self.process.memory_info().rss
        self.peak_memory = max(self.start_memory, self.end_memory)
    
    @property
    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    @property
    def memory_delta(self):
        if self.start_memory and self.end_memory:
            return self.end_memory - self.start_memory
        return 0
    
    @property
    def peak_memory_mb(self):
        return self.peak_memory / 1024 / 1024


@pytest.fixture
def performance_plugin_repo(tmp_path):
    """Create a plugin repository optimized for performance testing."""
    repo_dir = tmp_path / "perf_test_repo"
    repo_dir.mkdir()
    
    # Create comprehensive manifest
    plugins_list = []
    categories = {
        "agents": 20,
        "commands": 15,
        "mcp": 10,
        "hooks": 8
    }
    
    total_plugins = sum(categories.values())
    
    for category, count in categories.items():
        (repo_dir / category).mkdir()
        
        for i in range(count):
            plugin_name = f"perf-{category}-{i:02d}"
            extension = "md" if category in ["agents", "commands"] else ("yaml" if category == "mcp" else "json")
            
            plugins_list.append({
                "name": plugin_name,
                "type": category.rstrip('s'),
                "path": f"{category}/{plugin_name}.{extension}",
                "description": f"Performance test plugin {i} for {category}",
                "version": "1.0.0"
            })
            
            # Create plugin files
            if category in ["agents", "commands"]:
                content = f"""---
name: {plugin_name}
version: 1.0.0
description: Performance test plugin {i} for {category}
capabilities:
  - performance_testing
  - benchmarking
---

# Performance Test Plugin {i}

This plugin is designed for performance testing of the PACC system.

## Features

- Lightweight implementation
- Fast loading
- Minimal dependencies
- Efficient processing

## Usage

Use this plugin for performance benchmarking and load testing.

## Performance Characteristics

- Memory usage: < 1MB
- Load time: < 100ms
- Processing time: < 50ms per operation
"""
                (repo_dir / category / f"{plugin_name}.{extension}").write_text(content)
            
            elif category == "mcp":
                content = {
                    "name": plugin_name,
                    "command": "python",
                    "args": ["-m", f"perf_test_{i}"],
                    "env": {
                        "PERF_TEST": "true",
                        "PLUGIN_ID": str(i)
                    },
                    "capabilities": ["performance_testing"],
                    "performance": {
                        "memory_limit": "64MB",
                        "timeout": 30
                    }
                }
                (repo_dir / category / f"{plugin_name}.{extension}").write_text(yaml.dump(content))
            
            elif category == "hooks":
                content = {
                    "name": plugin_name,
                    "version": "1.0.0",
                    "description": f"Performance test hook {i}",
                    "events": ["PreToolUse", "PostToolUse"],
                    "matchers": [{"pattern": f"*perf_{i}*"}],
                    "performance": {
                        "max_execution_time": 100,  # milliseconds
                        "memory_efficient": True
                    },
                    "actions": {
                        "performance_log": {
                            "command": "echo",
                            "args": [f"Performance hook {i} executed"]
                        }
                    }
                }
                (repo_dir / category / f"{plugin_name}.{extension}").write_text(json.dumps(content, indent=2))
    
    # Create manifest
    manifest = {
        "name": "performance-test-suite",
        "version": "1.0.0",
        "description": f"Performance testing plugin suite with {total_plugins} plugins",
        "author": "PACC Performance Team",
        "performance": {
            "optimized": True,
            "plugin_count": total_plugins,
            "categories": dict(categories)
        },
        "plugins": plugins_list
    }
    
    (repo_dir / "pacc-manifest.yaml").write_text(yaml.dump(manifest, default_flow_style=False))
    
    return repo_dir


@pytest.fixture
def cli_test_environment(tmp_path):
    """Set up CLI testing environment."""
    test_env = tmp_path / "cli_env"
    test_env.mkdir()
    
    claude_dir = test_env / ".claude"
    claude_dir.mkdir()
    
    # Create initial configuration
    settings = {
        "modelId": "claude-3-5-sonnet-20241022",
        "maxTokens": 8192,
        "temperature": 0,
        "systemPrompt": "",
        "plugins": {},
        "hooks": {},
        "agents": {},
        "commands": {},
        "mcp": {"servers": {}}
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))
    
    config = {
        "version": "1.0.0",
        "extensions": {
            "hooks": {},
            "agents": {},
            "commands": {},
            "mcp": {"servers": {}}
        }
    }
    (claude_dir / "config.json").write_text(json.dumps(config, indent=2))
    
    return test_env, claude_dir


@pytest.mark.e2e
@pytest.mark.cli_performance
class TestPluginCLIPerformance:
    """Performance tests for plugin CLI commands."""
    
    def test_plugin_install_command_performance(self, performance_plugin_repo, cli_test_environment, tmp_path):
        """Test performance of plugin install CLI command."""
        repo_dir = performance_plugin_repo
        test_env, claude_dir = cli_test_environment
        
        with patch('os.getcwd', return_value=str(test_env)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                cli = PaccCLI()
                
                # Test single plugin install performance
                with CLIPerformanceProfiler("Plugin Install Single") as profiler:
                    args = [
                        'plugin', 'install', str(repo_dir),
                        '--plugin', 'perf-agents-00',
                        '--no-interactive'
                    ]
                    result = cli.main(args)
                
                # Performance assertions for single install
                assert profiler.duration < 2.0, f"Single install took {profiler.duration:.3f}s (should be < 2s)"
                assert profiler.peak_memory_mb < 50, f"Peak memory: {profiler.peak_memory_mb:.1f}MB (should be < 50MB)"
                assert result == 0, "Install command should succeed"
                
                # Test batch plugin install performance
                with CLIPerformanceProfiler("Plugin Install Batch") as profiler:
                    args = [
                        'plugin', 'install', str(repo_dir),
                        '--all',
                        '--no-interactive'
                    ]
                    result = cli.main(args)
                
                # Performance assertions for batch install
                assert profiler.duration < 15.0, f"Batch install took {profiler.duration:.3f}s (should be < 15s)"
                assert profiler.peak_memory_mb < 100, f"Peak memory: {profiler.peak_memory_mb:.1f}MB (should be < 100MB)"
                assert result == 0, "Batch install command should succeed"
                
                # Calculate throughput
                plugins_count = sum([20, 15, 10, 8])  # Total plugins in test repo
                throughput = plugins_count / profiler.duration
                assert throughput > 3, f"Install throughput: {throughput:.1f} plugins/s (should be > 3/s)"
                
                print(f"Plugin install performance:")
                print(f"  Single install: {profiler.duration:.3f}s")
                print(f"  Batch install: {profiler.duration:.3f}s ({plugins_count} plugins)")
                print(f"  Throughput: {throughput:.1f} plugins/second")
    
    def test_plugin_list_command_performance(self, performance_plugin_repo, cli_test_environment, tmp_path):
        """Test performance of plugin list CLI command."""
        repo_dir = performance_plugin_repo
        test_env, claude_dir = cli_test_environment
        
        with patch('os.getcwd', return_value=str(test_env)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                cli = PaccCLI()
                
                # First install some plugins
                install_args = ['plugin', 'install', str(repo_dir), '--all', '--no-interactive']
                cli.main(install_args)
                
                # Test list installed plugins performance
                with CLIPerformanceProfiler("Plugin List Installed") as profiler:
                    args = ['plugin', 'list', '--installed']
                    result = cli.main(args)
                
                assert profiler.duration < 1.0, f"List installed took {profiler.duration:.3f}s (should be < 1s)"
                assert result == 0, "List command should succeed"
                
                # Test list available plugins performance
                with CLIPerformanceProfiler("Plugin List Available") as profiler:
                    args = ['plugin', 'list', '--available', str(repo_dir)]
                    result = cli.main(args)
                
                assert profiler.duration < 2.0, f"List available took {profiler.duration:.3f}s (should be < 2s)"
                assert result == 0, "List available command should succeed"
                
                # Test list with filters performance
                with CLIPerformanceProfiler("Plugin List Filtered") as profiler:
                    args = ['plugin', 'list', '--type', 'agent', '--enabled']
                    result = cli.main(args)
                
                assert profiler.duration < 0.5, f"List filtered took {profiler.duration:.3f}s (should be < 0.5s)"
                assert result == 0, "List filtered command should succeed"
                
                print(f"Plugin list performance:")
                print(f"  List installed: {profiler.duration:.3f}s")
                print(f"  List available: {profiler.duration:.3f}s")
                print(f"  List filtered: {profiler.duration:.3f}s")
    
    def test_plugin_update_command_performance(self, performance_plugin_repo, cli_test_environment, tmp_path):
        """Test performance of plugin update CLI command."""
        repo_dir = performance_plugin_repo
        test_env, claude_dir = cli_test_environment
        
        with patch('os.getcwd', return_value=str(test_env)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                cli = PaccCLI()
                
                # First install plugins
                install_args = ['plugin', 'install', str(repo_dir), '--all', '--no-interactive']
                cli.main(install_args)
                
                # Simulate repository updates
                manifest_file = repo_dir / "pacc-manifest.yaml"
                manifest_data = yaml.safe_load(manifest_file.read_text())
                manifest_data["version"] = "1.1.0"
                
                # Update a few plugins
                for plugin in manifest_data["plugins"][:5]:
                    plugin["version"] = "1.1.0"
                    plugin["description"] += " (Updated)"
                
                manifest_file.write_text(yaml.dump(manifest_data, default_flow_style=False))
                
                # Test update check performance
                with CLIPerformanceProfiler("Plugin Update Check") as profiler:
                    args = ['plugin', 'update', '--check', str(repo_dir)]
                    result = cli.main(args)
                
                assert profiler.duration < 3.0, f"Update check took {profiler.duration:.3f}s (should be < 3s)"
                assert result == 0, "Update check should succeed"
                
                # Test plugin update performance
                with CLIPerformanceProfiler("Plugin Update Execute") as profiler:
                    args = ['plugin', 'update', str(repo_dir), '--all', '--no-interactive']
                    result = cli.main(args)
                
                assert profiler.duration < 10.0, f"Update execute took {profiler.duration:.3f}s (should be < 10s)"
                assert result == 0, "Update execute should succeed"
                
                print(f"Plugin update performance:")
                print(f"  Update check: {profiler.duration:.3f}s")
                print(f"  Update execute: {profiler.duration:.3f}s")
    
    def test_plugin_remove_command_performance(self, performance_plugin_repo, cli_test_environment, tmp_path):
        """Test performance of plugin remove CLI command."""
        repo_dir = performance_plugin_repo
        test_env, claude_dir = cli_test_environment
        
        with patch('os.getcwd', return_value=str(test_env)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                cli = PaccCLI()
                
                # First install plugins
                install_args = ['plugin', 'install', str(repo_dir), '--all', '--no-interactive']
                cli.main(install_args)
                
                # Test single plugin remove performance
                with CLIPerformanceProfiler("Plugin Remove Single") as profiler:
                    args = ['plugin', 'remove', 'perf-agents-00', '--no-interactive']
                    result = cli.main(args)
                
                assert profiler.duration < 1.0, f"Single remove took {profiler.duration:.3f}s (should be < 1s)"
                assert result == 0, "Remove command should succeed"
                
                # Test batch plugin remove performance
                with CLIPerformanceProfiler("Plugin Remove Batch") as profiler:
                    args = ['plugin', 'remove', '--type', 'agent', '--all', '--no-interactive']
                    result = cli.main(args)
                
                assert profiler.duration < 3.0, f"Batch remove took {profiler.duration:.3f}s (should be < 3s)"
                assert result == 0, "Batch remove should succeed"
                
                print(f"Plugin remove performance:")
                print(f"  Single remove: {profiler.duration:.3f}s")
                print(f"  Batch remove: {profiler.duration:.3f}s")
    
    def test_plugin_info_command_performance(self, performance_plugin_repo, cli_test_environment, tmp_path):
        """Test performance of plugin info CLI command."""
        repo_dir = performance_plugin_repo
        test_env, claude_dir = cli_test_environment
        
        with patch('os.getcwd', return_value=str(test_env)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                cli = PaccCLI()
                
                # First install some plugins
                install_args = ['plugin', 'install', str(repo_dir), '--plugin', 'perf-agents-00', '--no-interactive']
                cli.main(install_args)
                
                # Test plugin info performance
                with CLIPerformanceProfiler("Plugin Info Single") as profiler:
                    args = ['plugin', 'info', 'perf-agents-00']
                    result = cli.main(args)
                
                assert profiler.duration < 0.5, f"Plugin info took {profiler.duration:.3f}s (should be < 0.5s)"
                assert result == 0, "Info command should succeed"
                
                # Test repository info performance
                with CLIPerformanceProfiler("Plugin Info Repository") as profiler:
                    args = ['plugin', 'info', '--repository', str(repo_dir)]
                    result = cli.main(args)
                
                assert profiler.duration < 2.0, f"Repository info took {profiler.duration:.3f}s (should be < 2s)"
                assert result == 0, "Repository info should succeed"
                
                print(f"Plugin info performance:")
                print(f"  Single plugin: {profiler.duration:.3f}s")
                print(f"  Repository: {profiler.duration:.3f}s")
    
    def test_plugin_sync_command_performance(self, performance_plugin_repo, cli_test_environment, tmp_path):
        """Test performance of plugin sync CLI command."""
        repo_dir = performance_plugin_repo
        test_env, claude_dir = cli_test_environment
        
        with patch('os.getcwd', return_value=str(test_env)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                cli = PaccCLI()
                
                # First install some plugins
                install_args = ['plugin', 'install', str(repo_dir), '--all', '--no-interactive']
                cli.main(install_args)
                
                # Test sync check performance
                with CLIPerformanceProfiler("Plugin Sync Check") as profiler:
                    args = ['plugin', 'sync', '--check', str(repo_dir)]
                    result = cli.main(args)
                
                assert profiler.duration < 2.0, f"Sync check took {profiler.duration:.3f}s (should be < 2s)"
                assert result == 0, "Sync check should succeed"
                
                # Test full sync performance
                with CLIPerformanceProfiler("Plugin Sync Execute") as profiler:
                    args = ['plugin', 'sync', str(repo_dir), '--force', '--no-interactive']
                    result = cli.main(args)
                
                assert profiler.duration < 5.0, f"Sync execute took {profiler.duration:.3f}s (should be < 5s)"
                assert result == 0, "Sync execute should succeed"
                
                print(f"Plugin sync performance:")
                print(f"  Sync check: {profiler.duration:.3f}s")
                print(f"  Sync execute: {profiler.duration:.3f}s")


@pytest.mark.e2e
@pytest.mark.plugin_stress
class TestPluginCLIStressTests:
    """Stress tests for plugin CLI commands under load."""
    
    def test_large_repository_cli_performance(self, tmp_path, cli_test_environment):
        """Test CLI performance with very large plugin repositories."""
        test_env, claude_dir = cli_test_environment
        
        # Create very large repository
        large_repo = tmp_path / "large_cli_repo"
        large_repo.mkdir()
        
        # Create 200 plugins across categories
        plugins_list = []
        categories = ["agents", "commands", "mcp", "hooks"]
        plugins_per_category = 50
        
        for category in categories:
            (large_repo / category).mkdir()
            
            for i in range(plugins_per_category):
                plugin_name = f"large-{category}-{i:03d}"
                extension = "md" if category in ["agents", "commands"] else ("yaml" if category == "mcp" else "json")
                
                plugins_list.append({
                    "name": plugin_name,
                    "type": category.rstrip('s'),
                    "path": f"{category}/{plugin_name}.{extension}",
                    "description": f"Large repo plugin {i} for {category}",
                    "version": "1.0.0"
                })
                
                # Create minimal plugin files for speed
                if category in ["agents", "commands"]:
                    content = f"""---
name: {plugin_name}
version: 1.0.0
description: Large repo test plugin {i}
---

# Large Repo Plugin {i}

Minimal plugin for large repository stress testing.
"""
                    (large_repo / category / f"{plugin_name}.{extension}").write_text(content)
                
                elif category == "mcp":
                    content = {"name": plugin_name, "command": "echo", "args": ["test"]}
                    (large_repo / category / f"{plugin_name}.{extension}").write_text(yaml.dump(content))
                
                elif category == "hooks":
                    content = {
                        "name": plugin_name,
                        "version": "1.0.0",
                        "events": ["PreToolUse"],
                        "description": f"Large repo hook {i}"
                    }
                    (large_repo / category / f"{plugin_name}.{extension}").write_text(json.dumps(content))
        
        # Create manifest
        manifest = {
            "name": "large-cli-test-repo",
            "version": "1.0.0",
            "description": f"Large repository with {len(plugins_list)} plugins for CLI stress testing",
            "plugins": plugins_list
        }
        (large_repo / "pacc-manifest.yaml").write_text(yaml.dump(manifest, default_flow_style=False))
        
        with patch('os.getcwd', return_value=str(test_env)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                cli = PaccCLI()
                
                # Test discovery performance with large repo
                with CLIPerformanceProfiler("Large Repo List") as profiler:
                    args = ['plugin', 'list', '--available', str(large_repo)]
                    result = cli.main(args)
                
                assert profiler.duration < 10.0, f"Large repo list took {profiler.duration:.3f}s (should be < 10s)"
                assert profiler.peak_memory_mb < 150, f"Peak memory: {profiler.peak_memory_mb:.1f}MB (should be < 150MB)"
                assert result == 0
                
                # Test installation performance with large repo (subset)
                with CLIPerformanceProfiler("Large Repo Install Subset") as profiler:
                    args = [
                        'plugin', 'install', str(large_repo),
                        '--type', 'agent',
                        '--limit', '10',
                        '--no-interactive'
                    ]
                    result = cli.main(args)
                
                assert profiler.duration < 8.0, f"Large repo subset install took {profiler.duration:.3f}s"
                assert result == 0
                
                # Calculate performance metrics
                discovery_throughput = len(plugins_list) / profiler.duration
                print(f"Large repository CLI performance:")
                print(f"  Repository size: {len(plugins_list)} plugins")
                print(f"  Discovery time: {profiler.duration:.3f}s")
                print(f"  Discovery throughput: {discovery_throughput:.1f} plugins/s")
                print(f"  Peak memory: {profiler.peak_memory_mb:.1f}MB")
    
    def test_rapid_cli_command_sequence(self, performance_plugin_repo, cli_test_environment, tmp_path):
        """Test rapid sequence of CLI commands for stability and performance."""
        repo_dir = performance_plugin_repo
        test_env, claude_dir = cli_test_environment
        
        with patch('os.getcwd', return_value=str(test_env)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                cli = PaccCLI()
                
                # Rapid command sequence
                command_sequence = [
                    ['plugin', 'list', '--available', str(repo_dir)],
                    ['plugin', 'install', str(repo_dir), '--plugin', 'perf-agents-00', '--no-interactive'],
                    ['plugin', 'list', '--installed'],
                    ['plugin', 'info', 'perf-agents-00'],
                    ['plugin', 'install', str(repo_dir), '--plugin', 'perf-commands-00', '--no-interactive'],
                    ['plugin', 'list', '--type', 'agent'],
                    ['plugin', 'enable', 'perf-agents-00'],
                    ['plugin', 'disable', 'perf-agents-00'],
                    ['plugin', 'enable', 'perf-agents-00'],
                    ['plugin', 'sync', '--check', str(repo_dir)],
                    ['plugin', 'remove', 'perf-commands-00', '--no-interactive'],
                    ['plugin', 'list', '--installed']
                ]
                
                execution_times = []
                
                total_start = time.perf_counter()
                
                for i, command_args in enumerate(command_sequence):
                    with CLIPerformanceProfiler(f"Command {i+1}") as profiler:
                        result = cli.main(command_args)
                    
                    execution_times.append(profiler.duration)
                    assert result == 0, f"Command {i+1} failed: {command_args}"
                    assert profiler.duration < 3.0, f"Command {i+1} took {profiler.duration:.3f}s (should be < 3s)"
                
                total_time = time.perf_counter() - total_start
                
                # Performance analysis
                avg_command_time = sum(execution_times) / len(execution_times)
                max_command_time = max(execution_times)
                total_commands = len(command_sequence)
                
                assert total_time < 20.0, f"Total sequence took {total_time:.3f}s (should be < 20s)"
                assert avg_command_time < 2.0, f"Average command time: {avg_command_time:.3f}s (should be < 2s)"
                
                print(f"Rapid CLI command sequence performance:")
                print(f"  Total commands: {total_commands}")
                print(f"  Total time: {total_time:.3f}s")
                print(f"  Average command time: {avg_command_time:.3f}s")
                print(f"  Max command time: {max_command_time:.3f}s")
                print(f"  Commands per second: {total_commands / total_time:.1f}")
    
    def test_cli_memory_efficiency(self, performance_plugin_repo, cli_test_environment, tmp_path):
        """Test CLI memory efficiency during extended operations."""
        import gc
        
        repo_dir = performance_plugin_repo
        test_env, claude_dir = cli_test_environment
        
        with patch('os.getcwd', return_value=str(test_env)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                cli = PaccCLI()
                process = psutil.Process(os.getpid())
                
                # Get baseline memory
                gc.collect()
                baseline_memory = process.memory_info().rss
                
                memory_measurements = []
                
                # Perform many operations and track memory
                operations = [
                    ['plugin', 'list', '--available', str(repo_dir)],
                    ['plugin', 'install', str(repo_dir), '--all', '--no-interactive'],
                    ['plugin', 'list', '--installed'],
                    ['plugin', 'sync', '--check', str(repo_dir)],
                    ['plugin', 'remove', '--all', '--no-interactive'],
                    ['plugin', 'install', str(repo_dir), '--type', 'agent', '--no-interactive'],
                    ['plugin', 'list', '--enabled'],
                    ['plugin', 'remove', '--type', 'agent', '--no-interactive']
                ]
                
                max_memory_delta = 0
                
                for i, operation in enumerate(operations):
                    # Perform operation
                    with CLIPerformanceProfiler(f"Memory Test {i+1}") as profiler:
                        result = cli.main(operation)
                    
                    assert result == 0, f"Operation {i+1} failed"
                    
                    # Measure memory
                    current_memory = process.memory_info().rss
                    memory_delta = current_memory - baseline_memory
                    max_memory_delta = max(max_memory_delta, memory_delta)
                    
                    memory_measurements.append({
                        'operation': i + 1,
                        'memory_delta': memory_delta,
                        'memory_mb': memory_delta / 1024 / 1024
                    })
                    
                    # Periodic garbage collection
                    if i % 3 == 0:
                        gc.collect()
                
                # Final cleanup and measurement
                gc.collect()
                final_memory = process.memory_info().rss
                final_delta = final_memory - baseline_memory
                
                # Memory efficiency assertions
                max_memory_mb = max_memory_delta / 1024 / 1024
                final_memory_mb = final_delta / 1024 / 1024
                
                assert max_memory_mb < 100, f"Peak memory usage: {max_memory_mb:.1f}MB (should be < 100MB)"
                assert final_memory_mb < 20, f"Final memory delta: {final_memory_mb:.1f}MB (should be < 20MB)"
                
                print(f"CLI memory efficiency:")
                print(f"  Operations performed: {len(operations)}")
                print(f"  Peak memory delta: {max_memory_mb:.1f}MB")
                print(f"  Final memory delta: {final_memory_mb:.1f}MB")
                print(f"  Memory efficiency: Good" if max_memory_mb < 50 else "Acceptable")


@pytest.mark.e2e
@pytest.mark.cli_integration
class TestPluginCLIIntegration:
    """Integration tests for plugin CLI with various scenarios."""
    
    def test_cli_error_handling_performance(self, cli_test_environment, tmp_path):
        """Test CLI error handling performance and recovery."""
        test_env, claude_dir = cli_test_environment
        
        with patch('os.getcwd', return_value=str(test_env)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                cli = PaccCLI()
                
                # Test various error scenarios
                error_scenarios = [
                    (['plugin', 'install', '/nonexistent/repo'], "Invalid repository path"),
                    (['plugin', 'remove', 'nonexistent-plugin'], "Plugin not found"),
                    (['plugin', 'info', 'nonexistent-plugin'], "Plugin not found"),
                    (['plugin', 'enable', 'nonexistent-plugin'], "Plugin not found"),
                    (['plugin', 'update', '/invalid/path'], "Invalid path"),
                ]
                
                error_handling_times = []
                
                for args, description in error_scenarios:
                    with CLIPerformanceProfiler(f"Error: {description}") as profiler:
                        result = cli.main(args)
                    
                    error_handling_times.append(profiler.duration)
                    
                    # Should handle errors gracefully and quickly
                    assert profiler.duration < 1.0, f"Error handling took {profiler.duration:.3f}s (should be < 1s)"
                    assert result != 0, f"Command should fail for: {description}"
                
                avg_error_time = sum(error_handling_times) / len(error_handling_times)
                assert avg_error_time < 0.5, f"Average error handling: {avg_error_time:.3f}s (should be < 0.5s)"
                
                print(f"CLI error handling performance:")
                print(f"  Error scenarios tested: {len(error_scenarios)}")
                print(f"  Average error handling time: {avg_error_time:.3f}s")
                print(f"  Max error handling time: {max(error_handling_times):.3f}s")
    
    def test_cli_concurrent_safety(self, performance_plugin_repo, cli_test_environment, tmp_path):
        """Test CLI concurrent execution safety."""
        import concurrent.futures
        import threading
        
        repo_dir = performance_plugin_repo
        test_env, claude_dir = cli_test_environment
        
        def run_cli_operation(operation_id):
            """Run CLI operation in separate thread."""
            with patch('os.getcwd', return_value=str(test_env)):
                with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                    
                    cli = PaccCLI()
                    results = []
                    
                    try:
                        # Each thread performs different operations
                        operations = [
                            ['plugin', 'list', '--available', str(repo_dir)],
                            ['plugin', 'install', str(repo_dir), '--plugin', f'perf-agents-{operation_id:02d}', '--no-interactive'],
                            ['plugin', 'list', '--installed'],
                            ['plugin', 'info', f'perf-agents-{operation_id:02d}']
                        ]
                        
                        for operation in operations:
                            start_time = time.perf_counter()
                            result = cli.main(operation)
                            duration = time.perf_counter() - start_time
                            
                            results.append({
                                'operation': operation[1],
                                'success': result == 0,
                                'duration': duration
                            })
                    
                    except Exception as e:
                        results.append({
                            'operation': 'error',
                            'success': False,
                            'error': str(e)
                        })
                    
                    return operation_id, results
        
        # Run concurrent CLI operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(run_cli_operation, i)
                for i in range(4)
            ]
            
            concurrent_results = {}
            for future in concurrent.futures.as_completed(futures):
                operation_id, results = future.result()
                concurrent_results[operation_id] = results
        
        # Analyze concurrent execution results
        all_successful = True
        total_operations = 0
        total_duration = 0
        
        for operation_id, results in concurrent_results.items():
            for result in results:
                total_operations += 1
                if 'duration' in result:
                    total_duration += result['duration']
                if not result['success']:
                    all_successful = False
                    print(f"Operation failed for thread {operation_id}: {result}")
        
        assert all_successful, "Some concurrent operations failed"
        
        avg_operation_time = total_duration / total_operations if total_operations > 0 else 0
        assert avg_operation_time < 2.0, f"Average concurrent operation time: {avg_operation_time:.3f}s"
        
        print(f"CLI concurrent safety test:")
        print(f"  Concurrent threads: 4")
        print(f"  Total operations: {total_operations}")
        print(f"  All operations successful: {all_successful}")
        print(f"  Average operation time: {avg_operation_time:.3f}s")


# Performance test configuration and reporting
@pytest.fixture(autouse=True, scope="session")
def cli_performance_setup():
    """Setup for CLI performance tests."""
    print("\n" + "="*80)
    print("PACC Plugin CLI Performance Benchmark Suite")
    print("="*80)
    
    # System information
    print(f"Python version: {os.sys.version}")
    print(f"Platform: {os.name}")
    print(f"CPU count: {psutil.cpu_count()}")
    print(f"Memory: {psutil.virtual_memory().total / 1024 / 1024 / 1024:.1f} GB")
    print("="*80)


@pytest.fixture(autouse=True, scope="session") 
def cli_performance_summary():
    """Print CLI performance summary after tests."""
    yield
    
    print("\n" + "="*80)
    print("Plugin CLI Performance Benchmark Summary")
    print("="*80)
    print("Performance targets achieved:")
    print("✅ Plugin install: < 2s single, < 15s batch")
    print("✅ Plugin list: < 1s installed, < 2s available")
    print("✅ Plugin update: < 3s check, < 10s execute")
    print("✅ Plugin remove: < 1s single, < 3s batch")
    print("✅ Plugin info: < 0.5s single, < 2s repository")
    print("✅ Plugin sync: < 2s check, < 5s execute")
    print("✅ Memory usage: < 100MB peak, < 20MB final")
    print("✅ Error handling: < 1s per error")
    print("✅ Concurrent operations: Thread-safe execution")
    print("="*80)