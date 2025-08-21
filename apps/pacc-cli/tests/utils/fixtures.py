"""Test fixtures and factories for PACC E2E tests."""

import json
import yaml
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import time


@dataclass
class PluginTemplate:
    """Template for creating test plugins."""
    name: str
    type: str
    size: str = "medium"  # small, medium, large
    version: str = "1.0.0"
    description: str = None
    capabilities: List[str] = None
    platform_support: Dict[str, bool] = None


class PluginRepositoryFactory:
    """Factory for creating test plugin repositories."""
    
    @staticmethod
    def create_minimal_repo(tmp_path: Path, plugin_count: int = 5) -> Path:
        """Create a minimal plugin repository."""
        repo_dir = tmp_path / "minimal_repo"
        repo_dir.mkdir()
        
        plugins_list = []
        categories = ["agents", "commands", "hooks", "mcp"]
        
        for i in range(plugin_count):
            category = categories[i % len(categories)]
            plugin_name = f"test-{category}-{i:02d}"
            extension = "md" if category in ["agents", "commands"] else ("yaml" if category == "mcp" else "json")
            
            plugins_list.append({
                "name": plugin_name,
                "type": category.rstrip('s'),
                "path": f"{category}/{plugin_name}.{extension}",
                "description": f"Test plugin {i} for {category}",
                "version": "1.0.0"
            })
            
            # Create directory
            (repo_dir / category).mkdir(exist_ok=True)
            
            # Create plugin file
            if category in ["agents", "commands"]:
                content = f"""---
name: {plugin_name}
version: 1.0.0
description: Test plugin {i} for {category}
---

# Test Plugin {i}

This is a test plugin for E2E testing.
"""
                (repo_dir / category / f"{plugin_name}.{extension}").write_text(content)
            
            elif category == "mcp":
                content = {
                    "name": plugin_name,
                    "command": "python",
                    "args": ["-m", f"test_{i}"]
                }
                (repo_dir / category / f"{plugin_name}.{extension}").write_text(yaml.dump(content))
            
            elif category == "hooks":
                content = {
                    "name": plugin_name,
                    "version": "1.0.0",
                    "events": ["PreToolUse"],
                    "description": f"Test hook {i}"
                }
                (repo_dir / category / f"{plugin_name}.{extension}").write_text(json.dumps(content, indent=2))
        
        # Create manifest
        manifest = {
            "name": "minimal-test-repo",
            "version": "1.0.0",
            "description": f"Minimal test repository with {plugin_count} plugins",
            "plugins": plugins_list
        }
        
        (repo_dir / "pacc-manifest.yaml").write_text(yaml.dump(manifest, default_flow_style=False))
        
        return repo_dir
    
    @staticmethod
    def create_sized_repo(
        tmp_path: Path, 
        small_count: int = 10,
        medium_count: int = 10, 
        large_count: int = 5
    ) -> Path:
        """Create a repository with plugins of different sizes."""
        repo_dir = tmp_path / "sized_repo"
        repo_dir.mkdir()
        
        plugins_list = []
        plugin_configs = [
            ("small", small_count, 1),
            ("medium", medium_count, 3),
            ("large", large_count, 8)
        ]
        
        total_plugins = 0
        
        for size, count, multiplier in plugin_configs:
            for i in range(count):
                category = ["agents", "commands", "hooks", "mcp"][total_plugins % 4]
                plugin_name = f"{size}-{category}-{i:02d}"
                extension = "md" if category in ["agents", "commands"] else ("yaml" if category == "mcp" else "json")
                
                plugins_list.append({
                    "name": plugin_name,
                    "type": category.rstrip('s'),
                    "path": f"{category}/{plugin_name}.{extension}",
                    "description": f"{size.title()} test plugin {i} for {category}",
                    "version": "1.0.0",
                    "size": size
                })
                
                # Create directory
                (repo_dir / category).mkdir(exist_ok=True)
                
                # Create plugin file with size-appropriate content
                if category in ["agents", "commands"]:
                    content = f"""---
name: {plugin_name}
version: 1.0.0
description: {size.title()} test plugin {i} for {category}
size: {size}
---

# {size.title()} Test Plugin {i}

{'This is a comprehensive plugin with extensive documentation. ' * multiplier}

## Features

{'- Feature implementation with detailed description\\n' * (3 * multiplier)}

## Usage

{'```bash\\n# Example usage\\ncommand --option value\\n```\\n\\n' * multiplier}
"""
                    (repo_dir / category / f"{plugin_name}.{extension}").write_text(content)
                
                elif category == "mcp":
                    content = {
                        "name": plugin_name,
                        "command": "python",
                        "args": ["-m", f"test_{i}"],
                        "capabilities": ["testing"] * multiplier,
                        "size": size
                    }
                    (repo_dir / category / f"{plugin_name}.{extension}").write_text(yaml.dump(content))
                
                elif category == "hooks":
                    content = {
                        "name": plugin_name,
                        "version": "1.0.0",
                        "events": ["PreToolUse"] * multiplier,
                        "description": f"{size.title()} test hook {i}",
                        "matchers": [{"pattern": f"*{j}*"} for j in range(multiplier)],
                        "size": size
                    }
                    (repo_dir / category / f"{plugin_name}.{extension}").write_text(json.dumps(content, indent=2))
                
                total_plugins += 1
        
        # Create manifest
        manifest = {
            "name": "sized-test-repo",
            "version": "1.0.0", 
            "description": f"Test repository with {total_plugins} plugins of various sizes",
            "size_distribution": {
                "small": small_count,
                "medium": medium_count,
                "large": large_count
            },
            "plugins": plugins_list
        }
        
        (repo_dir / "pacc-manifest.yaml").write_text(yaml.dump(manifest, default_flow_style=False))
        
        return repo_dir
    
    @staticmethod
    def create_versioned_repo(tmp_path: Path, versions: List[str] = None) -> Path:
        """Create a repository with multiple plugin versions."""
        if versions is None:
            versions = ["1.0.0", "1.1.0", "2.0.0"]
        
        repo_dir = tmp_path / "versioned_repo"
        repo_dir.mkdir()
        
        plugins_list = []
        
        for i, version in enumerate(versions):
            plugin_name = f"versioned-agent-{i:02d}"
            plugins_list.append({
                "name": plugin_name,
                "type": "agent",
                "path": f"agents/{plugin_name}.md",
                "description": f"Versioned test plugin {i} (v{version})",
                "version": version
            })
            
            # Create directory
            (repo_dir / "agents").mkdir(exist_ok=True)
            
            # Create plugin file
            content = f"""---
name: {plugin_name}
version: {version}
description: Versioned test plugin {i} (v{version})
changelog:
  - "{version}: Test version for E2E testing"
---

# Versioned Test Plugin {i}

**Version: {version}**

This plugin tests version management functionality.

## Version History

- {version}: Current version for testing
"""
            (repo_dir / "agents" / f"{plugin_name}.md").write_text(content)
        
        # Create manifest
        manifest = {
            "name": "versioned-test-repo",
            "version": versions[-1],  # Use latest version
            "description": f"Test repository with versioned plugins",
            "versions": versions,
            "plugins": plugins_list
        }
        
        (repo_dir / "pacc-manifest.yaml").write_text(yaml.dump(manifest, default_flow_style=False))
        
        return repo_dir


class TeamWorkspaceFactory:
    """Factory for creating team workspaces."""
    
    @staticmethod
    def create_team_workspace(
        tmp_path: Path, 
        member_names: List[str],
        shared_plugins: Optional[List[str]] = None
    ) -> Dict[str, Path]:
        """Create a team workspace with multiple member directories."""
        team_workspace = tmp_path / "team_workspace" 
        team_workspace.mkdir()
        
        member_workspaces = {}
        
        for member_name in member_names:
            member_dir = team_workspace / f"{member_name}_workspace"
            member_dir.mkdir()
            
            # Create Claude environment for each member
            claude_dir = member_dir / ".claude"
            claude_dir.mkdir()
            
            # Individual settings
            settings = {
                "modelId": "claude-3-5-sonnet-20241022",
                "maxTokens": 8192,
                "temperature": 0,
                "systemPrompt": f"Team member: {member_name}",
                "plugins": {},
                "hooks": {},
                "agents": {},
                "commands": {},
                "mcp": {"servers": {}},
                "team": {
                    "member_name": member_name,
                    "workspace": str(member_dir)
                }
            }
            
            # Add shared plugins if specified
            if shared_plugins:
                for plugin_name in shared_plugins:
                    settings["agents"][plugin_name] = {
                        "path": f"/shared/plugins/{plugin_name}.md",
                        "enabled": True,
                        "shared": True
                    }
            
            (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))
            
            # Individual config
            config = {
                "version": "1.0.0",
                "team_member": member_name,
                "extensions": {
                    "hooks": {},
                    "agents": {},
                    "commands": {},
                    "mcp": {"servers": {}}
                }
            }
            (claude_dir / "config.json").write_text(json.dumps(config, indent=2))
            
            member_workspaces[member_name] = member_dir
        
        return member_workspaces
    
    @staticmethod
    def create_shared_repo(tmp_path: Path, team_plugins: List[Dict[str, Any]]) -> Path:
        """Create a shared team plugin repository."""
        shared_repo = tmp_path / "shared_team_repo"
        shared_repo.mkdir()
        
        # Create team manifest with role-based access
        manifest = {
            "name": "team-shared-plugins",
            "version": "1.0.0",
            "description": "Shared plugins for team collaboration",
            "team_config": {
                "collaboration": True,
                "sync_enabled": True,
                "conflict_resolution": "team_lead_approval"
            },
            "plugins": team_plugins
        }
        
        # Create plugin directories and files
        for plugin in team_plugins:
            category = plugin["type"] + "s"  # Convert to plural
            category_dir = shared_repo / category
            category_dir.mkdir(exist_ok=True)
            
            plugin_name = plugin["name"]
            extension = "md" if category in ["agents", "commands"] else ("yaml" if category == "mcp" else "json")
            
            if category in ["agents", "commands"]:
                content = f"""---
name: {plugin_name}
version: {plugin.get('version', '1.0.0')}
description: {plugin.get('description', f'Team plugin {plugin_name}')}
team_config:
  shared: true
  collaboration: true
---

# Team Plugin: {plugin_name}

{plugin.get('description', f'Team collaboration plugin {plugin_name}')}

## Team Usage

This plugin is shared across the development team.
"""
                (category_dir / f"{plugin_name}.{extension}").write_text(content)
            
            elif category == "mcp":
                content = {
                    "name": plugin_name,
                    "command": "python",
                    "args": ["-m", plugin_name.replace("-", "_")],
                    "team_config": {
                        "shared": True,
                        "collaboration": True
                    }
                }
                (category_dir / f"{plugin_name}.{extension}").write_text(yaml.dump(content))
            
            elif category == "hooks":
                content = {
                    "name": plugin_name,
                    "version": plugin.get("version", "1.0.0"),
                    "events": ["PreToolUse"],
                    "description": plugin.get("description", f"Team hook {plugin_name}"),
                    "team_config": {
                        "shared": True,
                        "collaboration": True
                    }
                }
                (category_dir / f"{plugin_name}.{extension}").write_text(json.dumps(content, indent=2))
        
        (shared_repo / "pacc-manifest.yaml").write_text(yaml.dump(manifest, default_flow_style=False))
        
        return shared_repo


class ClaudeEnvironmentFactory:
    """Factory for creating Claude Code environments."""
    
    @staticmethod
    def create_basic_environment(tmp_path: Path) -> Path:
        """Create a basic Claude environment."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        
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
        
        return claude_dir
    
    @staticmethod
    def create_configured_environment(
        tmp_path: Path,
        installed_plugins: Dict[str, List[str]] = None
    ) -> Path:
        """Create a Claude environment with pre-installed plugins."""
        claude_dir = ClaudeEnvironmentFactory.create_basic_environment(tmp_path)
        
        if installed_plugins:
            settings_file = claude_dir / "settings.json"
            settings = json.loads(settings_file.read_text())
            
            for plugin_type, plugin_names in installed_plugins.items():
                for plugin_name in plugin_names:
                    settings[plugin_type][plugin_name] = {
                        "path": f"/test/plugins/{plugin_name}.{'md' if plugin_type in ['agents', 'commands'] else 'json' if plugin_type == 'hooks' else 'yaml'}",
                        "enabled": True
                    }
            
            settings_file.write_text(json.dumps(settings, indent=2))
        
        return claude_dir
    
    @staticmethod
    def create_performance_environment(tmp_path: Path) -> Path:
        """Create a Claude environment optimized for performance testing."""
        claude_dir = ClaudeEnvironmentFactory.create_basic_environment(tmp_path)
        
        # Add performance-specific settings
        settings_file = claude_dir / "settings.json"
        settings = json.loads(settings_file.read_text())
        settings.update({
            "performance": {
                "mode": "testing",
                "enable_metrics": True,
                "cache_plugins": True
            },
            "benchmark": {
                "start_time": time.time(),
                "test_mode": True
            }
        })
        settings_file.write_text(json.dumps(settings, indent=2))
        
        return claude_dir


def create_test_plugin(
    plugin_type: str,
    name: str,
    size: str = "medium",
    version: str = "1.0.0",
    **kwargs
) -> Dict[str, Any]:
    """Create a test plugin configuration."""
    base_plugin = {
        "name": name,
        "type": plugin_type,
        "version": version,
        "description": f"Test {plugin_type} plugin: {name}",
        **kwargs
    }
    
    # Add size-specific attributes
    if size == "small":
        base_plugin["complexity"] = "low"
        base_plugin["load_time"] = "fast"
    elif size == "large":
        base_plugin["complexity"] = "high"
        base_plugin["load_time"] = "slower"
        base_plugin["features"] = ["advanced", "comprehensive", "detailed"]
    
    return base_plugin


def create_test_manifest(
    name: str,
    plugins: List[Dict[str, Any]],
    version: str = "1.0.0",
    **kwargs
) -> Dict[str, Any]:
    """Create a test manifest configuration."""
    return {
        "name": name,
        "version": version,
        "description": f"Test manifest: {name}",
        "plugins": plugins,
        "test_config": {
            "created_at": time.time(),
            "test_mode": True
        },
        **kwargs
    }