"""End-to-end tests for complete plugin lifecycle workflows."""

import json
import yaml
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import tempfile

from pacc.core.project_config import ProjectConfigValidator
from pacc.plugins import (
    PluginRepositoryManager,
    PluginConfigManager,
    PluginConverter,
    EnvironmentManager
)
from pacc.cli import PaccCLI


class PerformanceTimer:
    """Helper class for tracking operation performance."""
    
    def __init__(self, operation_name):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
    
    @property
    def duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


@pytest.fixture
def mock_plugin_repo_structure(tmp_path):
    """Create a realistic mock plugin repository structure."""
    repo_dir = tmp_path / "test_plugin_repo"
    repo_dir.mkdir()
    
    # Create plugin manifest
    manifest = {
        "name": "test-productivity-plugins",
        "version": "1.0.0",
        "description": "A collection of productivity plugins for Claude Code",
        "author": "Test Author",
        "repository": "https://github.com/test/productivity-plugins",
        "plugins": [
            {
                "name": "quick-notes",
                "type": "agent",
                "path": "agents/quick-notes.md",
                "description": "Quick note-taking agent"
            },
            {
                "name": "project-analyzer", 
                "type": "agent",
                "path": "agents/project-analyzer.md",
                "description": "Analyzes project structure"
            },
            {
                "name": "git-helper",
                "type": "command",
                "path": "commands/git-helper.md", 
                "description": "Git workflow commands"
            },
            {
                "name": "dev-server",
                "type": "mcp",
                "path": "mcp/dev-server.yaml",
                "description": "Development server integration"
            },
            {
                "name": "file-watcher",
                "type": "hook",
                "path": "hooks/file-watcher.json",
                "description": "File change monitoring"
            }
        ]
    }
    
    manifest_file = repo_dir / "pacc-manifest.yaml"
    manifest_file.write_text(yaml.dump(manifest, default_flow_style=False))
    
    # Create plugin directories
    (repo_dir / "agents").mkdir()
    (repo_dir / "commands").mkdir()
    (repo_dir / "mcp").mkdir()
    (repo_dir / "hooks").mkdir()
    
    # Create agent plugins
    quick_notes_agent = """---
name: quick-notes
version: 1.0.0
description: Quick note-taking agent for capturing ideas and tasks
capabilities:
  - note_taking
  - task_management
  - quick_capture
---

# Quick Notes Agent

A specialized agent for rapid note-taking and task capture during development sessions.

## Features

- Instant note capture with automatic timestamping
- Task tracking and priority management
- Context-aware note organization
- Integration with project workflows

## Usage

Use this agent when you need to quickly capture ideas, make notes about code issues, or track development tasks without losing focus.

## Examples

- "Add a note about the performance issue in the user service"
- "Create a task to refactor the authentication module"
- "Capture this idea for the new feature architecture"
"""
    (repo_dir / "agents" / "quick-notes.md").write_text(quick_notes_agent)
    
    project_analyzer_agent = """---
name: project-analyzer
version: 1.0.0
description: Analyzes project structure and provides insights
capabilities:
  - code_analysis
  - architecture_review
  - dependency_analysis
  - metrics_calculation
---

# Project Analyzer Agent

An intelligent agent that analyzes project structure, dependencies, and code quality metrics.

## Features

- Dependency graph analysis
- Code complexity metrics
- Architecture pattern detection
- Performance bottleneck identification

## Usage

Use this agent to get insights about your project's structure, identify potential issues, and understand code relationships.

## Examples

- "Analyze the current project structure"
- "Show me the dependency relationships"
- "Find potential performance issues"
"""
    (repo_dir / "agents" / "project-analyzer.md").write_text(project_analyzer_agent)
    
    # Create command plugin
    git_helper_command = """# Git Helper Commands

Advanced Git workflow automation commands for Claude Code.

## Commands

### `git-flow-start`
Start a new feature branch with proper naming conventions.

```bash
git-flow-start feature/user-authentication
```

### `git-review-prep`
Prepare branch for code review with cleanup and validation.

```bash
git-review-prep --squash --lint --test
```

### `git-deploy-prep`
Prepare for deployment with version tagging and changelog.

```bash
git-deploy-prep --version 1.2.0 --environment production
```

## Usage Examples

```bash
# Start new feature development
git-flow-start feature/payment-integration

# Prepare for code review
git-review-prep --squash --lint

# Prepare for production deployment
git-deploy-prep --version 1.2.1 --environment production
```

## Configuration

Configure branch naming conventions and deployment targets in `.git-helper.yaml`.
"""
    (repo_dir / "commands" / "git-helper.md").write_text(git_helper_command)
    
    # Create MCP server plugin
    dev_server_mcp = {
        "name": "dev-server",
        "command": "python",
        "args": ["-m", "dev_server"],
        "env": {
            "SERVER_PORT": "8080",
            "DEBUG_MODE": "true",
            "LOG_LEVEL": "info"
        },
        "capabilities": [
            "server_management",
            "hot_reload",
            "log_streaming"
        ]
    }
    (repo_dir / "mcp" / "dev-server.yaml").write_text(yaml.dump(dev_server_mcp))
    
    # Create hook plugin
    file_watcher_hook = {
        "name": "file-watcher",
        "version": "1.0.0",
        "description": "Monitors file changes and triggers appropriate actions",
        "events": ["FileModified", "FileCreated", "FileDeleted"],
        "matchers": [
            {"pattern": "*.py", "action": "lint"},
            {"pattern": "*.js", "action": "format"},
            {"pattern": "*.md", "action": "validate"}
        ],
        "actions": {
            "lint": {
                "command": "pylint",
                "args": ["${file_path}"]
            },
            "format": {
                "command": "prettier",
                "args": ["--write", "${file_path}"]
            },
            "validate": {
                "command": "markdownlint",
                "args": ["${file_path}"]
            }
        }
    }
    (repo_dir / "hooks" / "file-watcher.json").write_text(json.dumps(file_watcher_hook, indent=2))
    
    return repo_dir


@pytest.fixture
def mock_claude_environment(tmp_path):
    """Create a mock Claude Code environment for testing."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    
    # Create settings.json
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
    
    # Create config.json
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
    
    return claude_dir


@pytest.mark.e2e
@pytest.mark.plugin_lifecycle
class TestCompletePluginLifecycle:
    """Test complete plugin lifecycle from discovery to removal."""
    
    def test_new_user_plugin_discovery_and_installation(
        self, 
        mock_plugin_repo_structure, 
        mock_claude_environment,
        tmp_path
    ):
        """Test complete workflow for new user discovering and installing plugins."""
        repo_dir = mock_plugin_repo_structure
        claude_dir = mock_claude_environment
        
        with patch('os.getcwd', return_value=str(tmp_path)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                # Step 1: User discovers available plugins
                repo_manager = PluginRepositoryManager()
                
                with PerformanceTimer("Plugin Discovery") as timer:
                    plugins = repo_manager.discover_plugins(repo_dir)
                
                # Should discover all plugins quickly
                assert timer.duration < 2.0, f"Plugin discovery took {timer.duration:.3f}s (should be < 2s)"
                assert len(plugins) == 5
                
                plugin_names = [p.name for p in plugins]
                assert "quick-notes" in plugin_names
                assert "project-analyzer" in plugin_names
                assert "git-helper" in plugin_names
                assert "dev-server" in plugin_names
                assert "file-watcher" in plugin_names
                
                # Step 2: User selects and installs specific plugins
                config_manager = PluginConfigManager(claude_dir)
                
                # Install agent plugin
                quick_notes_plugin = next(p for p in plugins if p.name == "quick-notes")
                
                with PerformanceTimer("Plugin Installation") as timer:
                    result = config_manager.install_plugin(quick_notes_plugin, repo_dir)
                
                # Should install quickly
                assert timer.duration < 1.0, f"Plugin installation took {timer.duration:.3f}s (should be < 1s)"
                assert result['success'] is True
                assert result['installed_count'] == 1
                
                # Step 3: Verify plugin is properly configured
                settings_path = claude_dir / "settings.json"
                settings_data = json.loads(settings_path.read_text())
                
                assert "quick-notes" in settings_data["agents"]
                assert settings_data["agents"]["quick-notes"]["path"] == str(repo_dir / "agents" / "quick-notes.md")
                
                # Step 4: Install multiple plugins at once
                remaining_plugins = [p for p in plugins if p.name != "quick-notes"]
                
                with PerformanceTimer("Batch Plugin Installation") as timer:
                    batch_result = config_manager.install_plugins(remaining_plugins, repo_dir)
                
                # Batch installation should be efficient
                assert timer.duration < 3.0, f"Batch installation took {timer.duration:.3f}s (should be < 3s)"
                assert batch_result['success'] is True
                assert batch_result['installed_count'] == 4
                
                # Step 5: Verify all plugins are configured
                updated_settings = json.loads(settings_path.read_text())
                assert len(updated_settings["agents"]) == 2  # quick-notes + project-analyzer
                assert len(updated_settings["commands"]) == 1  # git-helper
                assert len(updated_settings["mcp"]["servers"]) == 1  # dev-server
                assert len(updated_settings["hooks"]) == 1  # file-watcher
    
    def test_plugin_update_workflow(
        self,
        mock_plugin_repo_structure,
        mock_claude_environment,
        tmp_path
    ):
        """Test plugin update workflow with version management."""
        repo_dir = mock_plugin_repo_structure
        claude_dir = mock_claude_environment
        
        with patch('os.getcwd', return_value=str(tmp_path)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                # Setup: Install initial plugins
                repo_manager = PluginRepositoryManager()
                plugins = repo_manager.discover_plugins(repo_dir)
                config_manager = PluginConfigManager(claude_dir)
                config_manager.install_plugins(plugins, repo_dir)
                
                # Step 1: Simulate plugin updates in repository
                # Update the manifest with new versions
                manifest_file = repo_dir / "pacc-manifest.yaml"
                manifest_data = yaml.safe_load(manifest_file.read_text())
                manifest_data["version"] = "1.1.0"
                
                # Update specific plugin
                for plugin in manifest_data["plugins"]:
                    if plugin["name"] == "quick-notes":
                        plugin["version"] = "1.1.0"
                        plugin["description"] = "Enhanced quick note-taking agent with new features"
                
                manifest_file.write_text(yaml.dump(manifest_data, default_flow_style=False))
                
                # Update the actual plugin file
                quick_notes_file = repo_dir / "agents" / "quick-notes.md"
                updated_content = quick_notes_file.read_text().replace(
                    "version: 1.0.0",
                    "version: 1.1.0"
                ).replace(
                    "## Features",
                    "## New Features\n\n- Enhanced search capabilities\n- Better task organization\n\n## Features"
                )
                quick_notes_file.write_text(updated_content)
                
                # Step 2: Check for updates
                with PerformanceTimer("Update Check") as timer:
                    update_info = repo_manager.check_for_updates(repo_dir, claude_dir)
                
                assert timer.duration < 1.0, f"Update check took {timer.duration:.3f}s (should be < 1s)"
                assert len(update_info.updates_available) > 0
                
                # Step 3: Apply updates
                with PerformanceTimer("Update Application") as timer:
                    update_result = config_manager.update_plugins(update_info.updates_available, repo_dir)
                
                assert timer.duration < 2.0, f"Update application took {timer.duration:.3f}s (should be < 2s)"
                assert update_result['success'] is True
                assert update_result['updated_count'] > 0
                
                # Step 4: Verify updated configuration
                settings_path = claude_dir / "settings.json"
                settings_data = json.loads(settings_path.read_text())
                
                # Check that plugin still works and has updated content
                quick_notes_config = settings_data["agents"]["quick-notes"]
                assert quick_notes_config["path"] == str(repo_dir / "agents" / "quick-notes.md")
                
                # Verify the content was updated
                updated_plugin_content = (repo_dir / "agents" / "quick-notes.md").read_text()
                assert "version: 1.1.0" in updated_plugin_content
                assert "Enhanced search capabilities" in updated_plugin_content
    
    def test_plugin_conflict_resolution(
        self,
        mock_plugin_repo_structure,
        mock_claude_environment,
        tmp_path
    ):
        """Test handling of plugin conflicts and resolution strategies."""
        repo_dir = mock_plugin_repo_structure
        claude_dir = mock_claude_environment
        
        with patch('os.getcwd', return_value=str(tmp_path)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                # Setup: Install initial plugins
                repo_manager = PluginRepositoryManager()
                plugins = repo_manager.discover_plugins(repo_dir)
                config_manager = PluginConfigManager(claude_dir)
                config_manager.install_plugins(plugins, repo_dir)
                
                # Step 1: Create conflicting plugin
                conflicting_repo = tmp_path / "conflicting_repo"
                conflicting_repo.mkdir()
                
                # Create a plugin with same name but different implementation
                conflicting_manifest = {
                    "name": "conflicting-plugins",
                    "version": "1.0.0",
                    "plugins": [
                        {
                            "name": "quick-notes",  # Same name as existing plugin
                            "type": "agent",
                            "path": "agents/quick-notes.md",
                            "description": "Different quick notes implementation"
                        }
                    ]
                }
                
                (conflicting_repo / "pacc-manifest.yaml").write_text(
                    yaml.dump(conflicting_manifest, default_flow_style=False)
                )
                
                (conflicting_repo / "agents").mkdir()
                conflicting_plugin_content = """---
name: quick-notes
version: 2.0.0
description: Alternative quick notes implementation with different features
---

# Alternative Quick Notes Agent

This is a different implementation of quick notes functionality.
"""
                (conflicting_repo / "agents" / "quick-notes.md").write_text(conflicting_plugin_content)
                
                # Step 2: Attempt to install conflicting plugin
                conflicting_plugins = repo_manager.discover_plugins(conflicting_repo)
                
                with PerformanceTimer("Conflict Detection") as timer:
                    # This should detect the conflict
                    conflict_result = config_manager.install_plugins(
                        conflicting_plugins, 
                        conflicting_repo,
                        allow_conflicts=False
                    )
                
                assert timer.duration < 1.0, f"Conflict detection took {timer.duration:.3f}s (should be < 1s)"
                assert conflict_result['success'] is False
                assert 'conflicts' in conflict_result
                assert len(conflict_result['conflicts']) > 0
                
                # Step 3: Test conflict resolution with override
                with PerformanceTimer("Conflict Resolution") as timer:
                    override_result = config_manager.install_plugins(
                        conflicting_plugins,
                        conflicting_repo,
                        allow_conflicts=True,
                        conflict_strategy='override'
                    )
                
                assert timer.duration < 1.0, f"Conflict resolution took {timer.duration:.3f}s (should be < 1s)"
                assert override_result['success'] is True
                assert override_result['installed_count'] == 1
                
                # Step 4: Verify the plugin was replaced
                settings_path = claude_dir / "settings.json"
                settings_data = json.loads(settings_path.read_text())
                
                quick_notes_config = settings_data["agents"]["quick-notes"]
                assert quick_notes_config["path"] == str(conflicting_repo / "agents" / "quick-notes.md")
                
                # Verify the content is from the new plugin
                current_content = (conflicting_repo / "agents" / "quick-notes.md").read_text()
                assert "Alternative quick notes implementation" in current_content
    
    def test_plugin_removal_and_cleanup(
        self,
        mock_plugin_repo_structure,
        mock_claude_environment,
        tmp_path
    ):
        """Test complete plugin removal with proper cleanup."""
        repo_dir = mock_plugin_repo_structure
        claude_dir = mock_claude_environment
        
        with patch('os.getcwd', return_value=str(tmp_path)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                # Setup: Install all plugins
                repo_manager = PluginRepositoryManager()
                plugins = repo_manager.discover_plugins(repo_dir)
                config_manager = PluginConfigManager(claude_dir)
                config_manager.install_plugins(plugins, repo_dir)
                
                # Verify initial state
                settings_path = claude_dir / "settings.json"
                initial_settings = json.loads(settings_path.read_text())
                assert len(initial_settings["agents"]) == 2
                assert len(initial_settings["commands"]) == 1
                assert len(initial_settings["mcp"]["servers"]) == 1
                assert len(initial_settings["hooks"]) == 1
                
                # Step 1: Remove specific plugin
                with PerformanceTimer("Single Plugin Removal") as timer:
                    removal_result = config_manager.remove_plugin("quick-notes", plugin_type="agent")
                
                assert timer.duration < 0.5, f"Plugin removal took {timer.duration:.3f}s (should be < 0.5s)"
                assert removal_result['success'] is True
                assert removal_result['removed_count'] == 1
                
                # Verify plugin was removed
                updated_settings = json.loads(settings_path.read_text())
                assert len(updated_settings["agents"]) == 1
                assert "quick-notes" not in updated_settings["agents"]
                assert "project-analyzer" in updated_settings["agents"]
                
                # Step 2: Remove multiple plugins by type
                with PerformanceTimer("Batch Plugin Removal") as timer:
                    batch_removal = config_manager.remove_plugins_by_type("agent")
                
                assert timer.duration < 0.5, f"Batch removal took {timer.duration:.3f}s (should be < 0.5s)"
                assert batch_removal['success'] is True
                assert batch_removal['removed_count'] == 1  # project-analyzer
                
                # Verify agents section is empty
                final_settings = json.loads(settings_path.read_text())
                assert len(final_settings["agents"]) == 0
                
                # Step 3: Remove all remaining plugins
                with PerformanceTimer("Complete Cleanup") as timer:
                    cleanup_result = config_manager.remove_all_plugins()
                
                assert timer.duration < 1.0, f"Complete cleanup took {timer.duration:.3f}s (should be < 1s)"
                assert cleanup_result['success'] is True
                assert cleanup_result['removed_count'] >= 3  # commands, mcp, hooks
                
                # Verify complete cleanup
                clean_settings = json.loads(settings_path.read_text())
                assert len(clean_settings["agents"]) == 0
                assert len(clean_settings["commands"]) == 0
                assert len(clean_settings["mcp"]["servers"]) == 0
                assert len(clean_settings["hooks"]) == 0
    
    def test_plugin_environment_setup_workflow(
        self,
        mock_claude_environment,
        tmp_path
    ):
        """Test plugin environment setup and verification."""
        claude_dir = mock_claude_environment
        
        with patch('os.getcwd', return_value=str(tmp_path)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                # Step 1: Initialize environment manager
                env_manager = EnvironmentManager()
                
                # Step 2: Check initial environment status
                with PerformanceTimer("Environment Status Check") as timer:
                    initial_status = env_manager.get_status()
                
                assert timer.duration < 0.5, f"Status check took {timer.duration:.3f}s (should be < 0.5s)"
                assert initial_status.platform is not None
                assert initial_status.shell is not None
                
                # Step 3: Setup environment for plugin development
                with PerformanceTimer("Environment Setup") as timer:
                    setup_result = env_manager.setup_development_environment()
                
                assert timer.duration < 2.0, f"Environment setup took {timer.duration:.3f}s (should be < 2s)"
                assert setup_result.success is True
                
                # Step 4: Verify environment is properly configured
                with PerformanceTimer("Environment Verification") as timer:
                    verification_result = env_manager.verify_environment()
                
                assert timer.duration < 1.0, f"Environment verification took {timer.duration:.3f}s (should be < 1s)"
                assert verification_result.is_valid is True
                assert len(verification_result.issues) == 0
                
                # Step 5: Test environment reset
                with PerformanceTimer("Environment Reset") as timer:
                    reset_result = env_manager.reset_environment()
                
                assert timer.duration < 1.0, f"Environment reset took {timer.duration:.3f}s (should be < 1s)"
                assert reset_result.success is True


@pytest.mark.e2e
@pytest.mark.plugin_performance
class TestPluginPerformanceBenchmarks:
    """Performance benchmarks for plugin operations."""
    
    def test_large_repository_discovery_performance(self, tmp_path):
        """Test performance with large plugin repositories."""
        large_repo = tmp_path / "large_plugin_repo"
        large_repo.mkdir()
        
        # Create large manifest with many plugins
        plugins_list = []
        categories = ["agents", "commands", "mcp", "hooks"]
        
        # Create 100 plugins across categories
        for i in range(100):
            category = categories[i % len(categories)]
            extension = "md" if category in ["agents", "commands"] else ("yaml" if category == "mcp" else "json")
            
            plugins_list.append({
                "name": f"{category}-plugin-{i:03d}",
                "type": category.rstrip('s'),  # Remove 's' for singular type
                "path": f"{category}/{category}-plugin-{i:03d}.{extension}",
                "description": f"Test plugin {i} for {category}"
            })
        
        manifest = {
            "name": "large-plugin-collection",
            "version": "1.0.0",
            "description": "Large collection for performance testing",
            "plugins": plugins_list
        }
        
        (large_repo / "pacc-manifest.yaml").write_text(yaml.dump(manifest, default_flow_style=False))
        
        # Create directory structure and files
        for category in categories:
            (large_repo / category).mkdir()
            
            for i in range(25):  # 25 plugins per category
                plugin_index = (categories.index(category) * 25) + i
                filename = f"{category}-plugin-{plugin_index:03d}"
                
                if category in ["agents", "commands"]:
                    content = f"""---
name: {filename}
version: 1.0.0
description: Test plugin {plugin_index}
---

# Test Plugin {plugin_index}

This is test plugin number {plugin_index} for performance testing.
"""
                    (large_repo / category / f"{filename}.md").write_text(content)
                
                elif category == "mcp":
                    content = {
                        "name": filename,
                        "command": "python",
                        "args": ["-m", filename]
                    }
                    (large_repo / category / f"{filename}.yaml").write_text(yaml.dump(content))
                
                elif category == "hooks":
                    content = {
                        "name": filename,
                        "version": "1.0.0",
                        "events": ["PreToolUse"],
                        "description": f"Test hook {plugin_index}"
                    }
                    (large_repo / category / f"{filename}.json").write_text(json.dumps(content, indent=2))
        
        # Performance test
        repo_manager = PluginRepositoryManager()
        
        with PerformanceTimer("Large Repository Discovery") as timer:
            plugins = repo_manager.discover_plugins(large_repo)
        
        # Performance assertions
        assert timer.duration < 5.0, f"Large repo discovery took {timer.duration:.3f}s (should be < 5s)"
        assert len(plugins) == 100
        
        # Test discovery throughput
        throughput = len(plugins) / timer.duration
        assert throughput > 20, f"Discovery throughput: {throughput:.1f} plugins/s (should be > 20/s)"
        
        print(f"Discovered {len(plugins)} plugins in {timer.duration:.3f}s")
        print(f"Throughput: {throughput:.1f} plugins/second")
    
    def test_batch_installation_performance(
        self,
        mock_plugin_repo_structure,
        mock_claude_environment,
        tmp_path
    ):
        """Test performance of batch plugin installation."""
        repo_dir = mock_plugin_repo_structure
        claude_dir = mock_claude_environment
        
        with patch('os.getcwd', return_value=str(tmp_path)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                # Discover plugins
                repo_manager = PluginRepositoryManager()
                plugins = repo_manager.discover_plugins(repo_dir)
                config_manager = PluginConfigManager(claude_dir)
                
                # Performance test: Install all plugins at once
                with PerformanceTimer("Batch Installation") as timer:
                    result = config_manager.install_plugins(plugins, repo_dir)
                
                # Performance assertions
                assert timer.duration < 3.0, f"Batch installation took {timer.duration:.3f}s (should be < 3s)"
                assert result['success'] is True
                assert result['installed_count'] == len(plugins)
                
                # Test installation throughput
                throughput = len(plugins) / timer.duration
                assert throughput > 2, f"Installation throughput: {throughput:.1f} plugins/s (should be > 2/s)"
                
                print(f"Installed {len(plugins)} plugins in {timer.duration:.3f}s")
                print(f"Throughput: {throughput:.1f} plugins/second")
    
    def test_configuration_update_performance(
        self,
        mock_plugin_repo_structure,
        mock_claude_environment,
        tmp_path
    ):
        """Test performance of configuration updates."""
        repo_dir = mock_plugin_repo_structure
        claude_dir = mock_claude_environment
        
        with patch('os.getcwd', return_value=str(tmp_path)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                config_manager = PluginConfigManager(claude_dir)
                
                # Setup: Install some plugins first
                repo_manager = PluginRepositoryManager()
                plugins = repo_manager.discover_plugins(repo_dir)
                config_manager.install_plugins(plugins, repo_dir)
                
                # Performance test: Multiple configuration updates
                update_count = 20
                total_time = 0
                
                for i in range(update_count):
                    # Simulate configuration changes
                    test_plugin = {
                        "name": f"temp-plugin-{i}",
                        "type": "agent",
                        "path": f"/tmp/temp-{i}.md",
                        "description": f"Temporary plugin {i}"
                    }
                    
                    with PerformanceTimer(f"Config Update {i}") as timer:
                        # Add and remove plugin quickly
                        config_manager._update_settings_atomic(lambda s: s["agents"].update({
                            f"temp-plugin-{i}": {
                                "path": test_plugin["path"],
                                "enabled": True
                            }
                        }))
                        
                        config_manager._update_settings_atomic(lambda s: s["agents"].pop(f"temp-plugin-{i}", None))
                    
                    total_time += timer.duration
                
                # Performance assertions
                avg_time = total_time / update_count
                assert avg_time < 0.1, f"Average config update took {avg_time:.3f}s (should be < 0.1s)"
                assert total_time < 2.0, f"Total update time {total_time:.3f}s (should be < 2s)"
                
                throughput = update_count / total_time
                assert throughput > 10, f"Update throughput: {throughput:.1f} updates/s (should be > 10/s)"
                
                print(f"Performed {update_count} config updates in {total_time:.3f}s")
                print(f"Average time per update: {avg_time:.3f}s")
                print(f"Throughput: {throughput:.1f} updates/second")


@pytest.mark.e2e
@pytest.mark.stress_test
class TestPluginStressTests:
    """Stress tests for plugin system under load."""
    
    def test_concurrent_plugin_operations(
        self,
        mock_plugin_repo_structure,
        mock_claude_environment,
        tmp_path
    ):
        """Test concurrent plugin operations for thread safety."""
        import threading
        import concurrent.futures
        
        repo_dir = mock_plugin_repo_structure
        claude_dir = mock_claude_environment
        
        with patch('os.getcwd', return_value=str(tmp_path)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                config_manager = PluginConfigManager(claude_dir)
                repo_manager = PluginRepositoryManager()
                plugins = repo_manager.discover_plugins(repo_dir)
                
                # Test concurrent installation and removal
                def install_remove_cycle(thread_id):
                    """Install and remove plugins in a cycle."""
                    results = []
                    
                    for cycle in range(5):
                        try:
                            # Install plugins
                            install_result = config_manager.install_plugins(plugins, repo_dir)
                            results.append(('install', thread_id, cycle, install_result['success']))
                            
                            # Small delay
                            time.sleep(0.01)
                            
                            # Remove plugins
                            remove_result = config_manager.remove_all_plugins()
                            results.append(('remove', thread_id, cycle, remove_result['success']))
                            
                        except Exception as e:
                            results.append(('error', thread_id, cycle, str(e)))
                    
                    return results
                
                # Run concurrent operations
                with PerformanceTimer("Concurrent Operations") as timer:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                        futures = [
                            executor.submit(install_remove_cycle, thread_id) 
                            for thread_id in range(4)
                        ]
                        
                        all_results = []
                        for future in concurrent.futures.as_completed(futures):
                            all_results.extend(future.result())
                
                # Performance and correctness assertions
                assert timer.duration < 10.0, f"Concurrent operations took {timer.duration:.3f}s (should be < 10s)"
                
                # Verify no errors occurred
                errors = [r for r in all_results if r[0] == 'error']
                assert len(errors) == 0, f"Errors occurred during concurrent operations: {errors}"
                
                # Verify operations completed
                successful_ops = [r for r in all_results if r[0] in ['install', 'remove'] and r[3] is True]
                total_expected = 4 * 5 * 2  # 4 threads * 5 cycles * 2 operations
                assert len(successful_ops) == total_expected
                
                print(f"Completed {len(successful_ops)} concurrent operations in {timer.duration:.3f}s")
                print(f"Operations per second: {len(successful_ops) / timer.duration:.1f}")
    
    def test_memory_usage_under_load(
        self,
        mock_plugin_repo_structure,
        mock_claude_environment,
        tmp_path
    ):
        """Test memory usage during intensive plugin operations."""
        import psutil
        import gc
        
        repo_dir = mock_plugin_repo_structure
        claude_dir = mock_claude_environment
        
        with patch('os.getcwd', return_value=str(tmp_path)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                # Get initial memory usage
                process = psutil.Process(os.getpid())
                gc.collect()
                initial_memory = process.memory_info().rss
                
                config_manager = PluginConfigManager(claude_dir)
                repo_manager = PluginRepositoryManager()
                plugins = repo_manager.discover_plugins(repo_dir)
                
                max_memory_delta = 0
                
                # Perform many plugin operations
                for i in range(50):
                    # Install plugins
                    config_manager.install_plugins(plugins, repo_dir)
                    
                    # Check memory
                    current_memory = process.memory_info().rss
                    memory_delta = current_memory - initial_memory
                    max_memory_delta = max(max_memory_delta, memory_delta)
                    
                    # Remove plugins
                    config_manager.remove_all_plugins()
                    
                    # Periodic garbage collection
                    if i % 10 == 0:
                        gc.collect()
                
                # Final memory check
                gc.collect()
                final_memory = process.memory_info().rss
                final_delta = final_memory - initial_memory
                
                # Memory assertions
                max_memory_mb = max_memory_delta / 1024 / 1024
                final_memory_mb = final_delta / 1024 / 1024
                
                assert max_memory_mb < 50, f"Peak memory usage: {max_memory_mb:.1f}MB (should be < 50MB)"
                assert final_memory_mb < 10, f"Final memory delta: {final_memory_mb:.1f}MB (should be < 10MB)"
                
                print(f"Peak memory usage: {max_memory_mb:.1f}MB")
                print(f"Final memory delta: {final_memory_mb:.1f}MB")
    
    def test_error_recovery_under_stress(
        self,
        mock_plugin_repo_structure,
        mock_claude_environment,
        tmp_path
    ):
        """Test error recovery mechanisms under stress conditions."""
        repo_dir = mock_plugin_repo_structure
        claude_dir = mock_claude_environment
        
        with patch('os.getcwd', return_value=str(tmp_path)):
            with patch('pacc.core.project_config.ProjectConfigValidator._find_claude_dir', return_value=claude_dir):
                
                config_manager = PluginConfigManager(claude_dir)
                repo_manager = PluginRepositoryManager()
                plugins = repo_manager.discover_plugins(repo_dir)
                
                # Simulate various error conditions
                error_scenarios = [
                    "corrupted_settings",
                    "missing_plugin_files",
                    "invalid_json",
                    "permission_denied",
                    "disk_full_simulation"
                ]
                
                recovery_results = []
                
                for scenario in error_scenarios:
                    try:
                        with PerformanceTimer(f"Error Recovery: {scenario}") as timer:
                            if scenario == "corrupted_settings":
                                # Corrupt settings file temporarily
                                settings_path = claude_dir / "settings.json"
                                backup_content = settings_path.read_text()
                                settings_path.write_text("invalid json content")
                                
                                # Try to install plugins (should recover)
                                result = config_manager.install_plugins(plugins, repo_dir)
                                
                                # Restore for next test
                                settings_path.write_text(backup_content)
                            
                            elif scenario == "missing_plugin_files":
                                # Temporarily hide plugin files
                                temp_dir = repo_dir.parent / "temp_backup"
                                repo_dir.rename(temp_dir)
                                
                                # Try operation (should handle gracefully)
                                result = config_manager.install_plugins(plugins, repo_dir)
                                
                                # Restore files
                                temp_dir.rename(repo_dir)
                            
                            else:
                                # For other scenarios, just test normal operation
                                result = config_manager.install_plugins(plugins, repo_dir)
                                config_manager.remove_all_plugins()
                        
                        recovery_results.append({
                            'scenario': scenario,
                            'duration': timer.duration,
                            'success': True
                        })
                    
                    except Exception as e:
                        recovery_results.append({
                            'scenario': scenario,
                            'duration': timer.duration if 'timer' in locals() else 0,
                            'success': False,
                            'error': str(e)
                        })
                
                # Verify recovery performance and success
                successful_recoveries = [r for r in recovery_results if r['success']]
                assert len(successful_recoveries) >= len(error_scenarios) - 1, "Most scenarios should recover successfully"
                
                # Verify recovery is reasonably fast
                avg_recovery_time = sum(r['duration'] for r in successful_recoveries) / len(successful_recoveries)
                assert avg_recovery_time < 2.0, f"Average recovery time: {avg_recovery_time:.3f}s (should be < 2s)"
                
                print(f"Tested {len(error_scenarios)} error scenarios")
                print(f"Successful recoveries: {len(successful_recoveries)}")
                print(f"Average recovery time: {avg_recovery_time:.3f}s")