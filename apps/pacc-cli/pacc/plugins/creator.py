"""Plugin creation wizard and scaffolding system for Claude Code plugins.

This module provides comprehensive plugin creation functionality including:
- Interactive wizard for guided plugin creation
- Quick mode for rapid scaffolding
- Template system for all plugin types
- Manifest generation from existing files
- Git repository initialization
- Comprehensive validation and error handling
"""

import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Set
from datetime import datetime

from ..core.file_utils import FilePathValidator, PathNormalizer
from ..validation.base import ValidationResult
from ..errors.exceptions import PACCError, ValidationError


logger = logging.getLogger(__name__)


class CreationPluginType(Enum):
    """Supported plugin types for creation."""
    HOOKS = 'hooks'
    AGENTS = 'agents'
    COMMANDS = 'commands'
    MCP = 'mcp'


class CreationMode(Enum):
    """Plugin creation modes."""
    GUIDED = 'guided'  # Interactive wizard with all prompts
    QUICK = 'quick'    # Minimal prompts for rapid creation


@dataclass
class PluginTemplate:
    """Template definition for plugin scaffolding."""
    
    plugin_type: CreationPluginType
    files: Dict[str, str] = field(default_factory=dict)  # filename -> content template
    directories: Set[str] = field(default_factory=set)   # directory names to create
    manifest_template: Dict[str, Any] = field(default_factory=dict)
    
    def get_file_content(self, filename: str, metadata: Dict[str, Any]) -> str:
        """Get file content with metadata substitution.
        
        Args:
            filename: Name of the file
            metadata: Plugin metadata for substitution
            
        Returns:
            File content with substituted values
        """
        template = self.files.get(filename, '')
        return self._substitute_template_vars(template, metadata)
    
    def _substitute_template_vars(self, template: str, metadata: Dict[str, Any]) -> str:
        """Substitute template variables with metadata values.
        
        Args:
            template: Template string with {{variable}} placeholders
            metadata: Values to substitute
            
        Returns:
            Template with substituted values
        """
        # Simple template substitution for {{variable}} patterns
        def replace_var(match):
            var_name = match.group(1)
            return str(self._get_nested_value(metadata, var_name))
        
        return re.sub(r'\{\{([^}]+)\}\}', replace_var, template)
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """Get nested value from dictionary using dot notation.
        
        Args:
            data: Dictionary to search
            key_path: Dot-separated key path (e.g., 'author.name')
            
        Returns:
            Value at the specified path, or empty string if not found
        """
        keys = key_path.split('.')
        value = data
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return ''


@dataclass
class CreationResult:
    """Result of plugin creation operation."""
    
    success: bool
    plugin_path: Optional[Path] = None
    created_files: List[str] = field(default_factory=list)
    git_initialized: bool = False
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        result = {
            'success': self.success,
            'created_files': self.created_files,
            'git_initialized': self.git_initialized
        }
        
        if self.plugin_path:
            result['plugin_path'] = str(self.plugin_path)
        if self.error_message:
            result['error_message'] = self.error_message
        if self.warnings:
            result['warnings'] = self.warnings
            
        return result


class MetadataCollector:
    """Collects plugin metadata through interactive prompts."""
    
    def collect_basic_metadata(self, mode: CreationMode, name: Optional[str] = None) -> Dict[str, Any]:
        """Collect basic plugin metadata.
        
        Args:
            mode: Creation mode (guided or quick)
            name: Optional pre-specified name
            
        Returns:
            Dictionary of collected metadata
        """
        metadata = {}
        
        # Plugin name (required for all modes)
        if name:
            metadata['name'] = name
        else:
            metadata['name'] = self._prompt_for_name()
        
        if mode == CreationMode.GUIDED:
            # Comprehensive metadata collection
            metadata['version'] = self._prompt_for_version()
            metadata['description'] = self._prompt_for_description()
            metadata['author'] = self._collect_author_info()
        else:
            # Quick mode - minimal metadata
            metadata['version'] = '1.0.0'  # Default version
        
        return metadata
    
    def _prompt_for_name(self) -> str:
        """Prompt for plugin name with validation."""
        while True:
            name = input("Enter plugin name: ").strip()
            if self._validate_name(name):
                return name
            print("❌ Invalid name. Use only letters, numbers, hyphens, and underscores.")
    
    def _prompt_for_version(self) -> str:
        """Prompt for plugin version."""
        version = input("Enter version (default: 1.0.0): ").strip()
        return version if version else '1.0.0'
    
    def _prompt_for_description(self) -> str:
        """Prompt for plugin description."""
        description = input("Enter description (optional): ").strip()
        return description if description else None
    
    def _collect_author_info(self) -> Dict[str, str]:
        """Collect author information."""
        author = {}
        
        name = input("Author name: ").strip()
        if name:
            author['name'] = name
        
        email = input("Author email (optional): ").strip()
        if email:
            author['email'] = email
            
        url = input("Author URL (optional): ").strip()
        if url:
            author['url'] = url
        
        return author if author else None
    
    def _validate_name(self, name: str) -> bool:
        """Validate plugin name format.
        
        Args:
            name: Plugin name to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not name:
            return False
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))


class TemplateEngine:
    """Template engine for generating plugin scaffolds."""
    
    def get_template(self, plugin_type: CreationPluginType) -> PluginTemplate:
        """Get template for specified plugin type.
        
        Args:
            plugin_type: Type of plugin to create template for
            
        Returns:
            PluginTemplate instance for the specified type
        """
        templates = {
            CreationPluginType.HOOKS: self._create_hooks_template(),
            CreationPluginType.AGENTS: self._create_agents_template(),
            CreationPluginType.COMMANDS: self._create_commands_template(),
            CreationPluginType.MCP: self._create_mcp_template()
        }
        
        return templates[plugin_type]
    
    def render_template(self, template: PluginTemplate, metadata: Dict[str, Any]) -> Dict[str, str]:
        """Render template with metadata to produce file contents.
        
        Args:
            template: Template to render
            metadata: Metadata for substitution
            
        Returns:
            Dictionary mapping filenames to rendered content
        """
        rendered_files = {}
        
        # Render plugin.json manifest
        manifest = template.manifest_template.copy()
        manifest.update(metadata)
        
        # Remove None values
        manifest = {k: v for k, v in manifest.items() if v is not None}
        
        rendered_files['plugin.json'] = json.dumps(manifest, indent=2)
        
        # Render other template files
        for filename, content_template in template.files.items():
            if filename != 'plugin.json':  # Already handled above
                rendered_files[filename] = template.get_file_content(filename, metadata)
        
        return rendered_files
    
    def _create_hooks_template(self) -> PluginTemplate:
        """Create template for hooks plugin."""
        return PluginTemplate(
            plugin_type=CreationPluginType.HOOKS,
            directories={'hooks'},
            files={
                'hooks/example-hook.json': self._get_example_hook_content(),
                '.gitignore': self._get_gitignore_content(),
                'README.md': self._get_readme_template('hooks')
            },
            manifest_template={
                'name': '',
                'version': '1.0.0',
                'description': '',
                'author': {},
                'components': {
                    'hooks': ['example-hook.json']
                }
            }
        )
    
    def _create_agents_template(self) -> PluginTemplate:
        """Create template for agents plugin."""
        return PluginTemplate(
            plugin_type=CreationPluginType.AGENTS,
            directories={'agents'},
            files={
                'agents/example-agent.md': self._get_example_agent_content(),
                '.gitignore': self._get_gitignore_content(),
                'README.md': self._get_readme_template('agents')
            },
            manifest_template={
                'name': '',
                'version': '1.0.0',
                'description': '',
                'author': {},
                'components': {
                    'agents': ['example-agent.md']
                }
            }
        )
    
    def _create_commands_template(self) -> PluginTemplate:
        """Create template for commands plugin."""
        return PluginTemplate(
            plugin_type=CreationPluginType.COMMANDS,
            directories={'commands'},
            files={
                'commands/example-command.md': self._get_example_command_content(),
                '.gitignore': self._get_gitignore_content(),
                'README.md': self._get_readme_template('commands')
            },
            manifest_template={
                'name': '',
                'version': '1.0.0',
                'description': '',
                'author': {},
                'components': {
                    'commands': ['example-command.md']
                }
            }
        )
    
    def _create_mcp_template(self) -> PluginTemplate:
        """Create template for MCP servers plugin."""
        return PluginTemplate(
            plugin_type=CreationPluginType.MCP,
            directories={'servers'},
            files={
                'mcp.json': self._get_example_mcp_content(),
                'servers/example-server.py': self._get_example_server_content(),
                '.gitignore': self._get_gitignore_content(),
                'README.md': self._get_readme_template('mcp')
            },
            manifest_template={
                'name': '',
                'version': '1.0.0',
                'description': '',
                'author': {},
                'components': {
                    'mcp': ['mcp.json']
                }
            }
        )
    
    def _get_example_hook_content(self) -> str:
        """Get example hook content."""
        return json.dumps({
            "event": "PreToolUse",
            "matcher": {
                "toolName": "*"
            },
            "command": {
                "type": "bash",
                "command": "echo 'Hook triggered for tool: ${toolName}'"
            },
            "description": "Example hook that logs when any tool is about to be used"
        }, indent=2)
    
    def _get_example_agent_content(self) -> str:
        """Get example agent content."""
        return '''# Example Agent

---
name: example-agent
description: An example agent for demonstration
parameters:
  - name: task
    type: string
    description: The task to help with
    required: true
---

## Agent Instructions

This is an example agent that demonstrates the basic structure.

### What I can help with:
- Example task 1
- Example task 2
- Example task 3

### Usage:
Describe your task and I'll help you complete it step by step.
'''
    
    def _get_example_command_content(self) -> str:
        """Get example command content."""
        return '''# Example Command

Description: An example command that demonstrates basic functionality

## Usage

```
/example-command [options]
```

## Options

- `--help`: Show this help message
- `--version`: Show version information

## Examples

```
/example-command --help
/example-command --version
```

## Implementation

This command demonstrates:
1. Basic command structure
2. Help text formatting
3. Option handling
'''
    
    def _get_example_mcp_content(self) -> str:
        """Get example MCP server configuration."""
        return json.dumps({
            "servers": {
                "example-server": {
                    "command": "python",
                    "args": ["servers/example-server.py"],
                    "description": "Example MCP server for demonstration"
                }
            }
        }, indent=2)
    
    def _get_example_server_content(self) -> str:
        """Get example MCP server implementation."""
        return '''#!/usr/bin/env python3
"""Example MCP server implementation."""

import json
import sys
from typing import Dict, Any


class ExampleMCPServer:
    """Example MCP server that provides basic functionality."""
    
    def __init__(self):
        self.tools = {
            "example_tool": {
                "description": "An example tool that echoes input",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Message to echo"
                        }
                    },
                    "required": ["message"]
                }
            }
        }
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP request."""
        method = request.get("method", "")
        
        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": name,
                        "description": tool["description"],
                        "inputSchema": tool["parameters"]
                    }
                    for name, tool in self.tools.items()
                ]
            }
        elif method == "tools/call":
            return self._handle_tool_call(request.get("params", {}))
        else:
            return {"error": f"Unknown method: {method}"}
    
    def _handle_tool_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool call."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        if tool_name == "example_tool":
            message = arguments.get("message", "")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Echo: {message}"
                    }
                ]
            }
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    def run(self):
        """Run the MCP server."""
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                response = self.handle_request(request)
                print(json.dumps(response))
                sys.stdout.flush()
            except Exception as e:
                error_response = {"error": str(e)}
                print(json.dumps(error_response))
                sys.stdout.flush()


if __name__ == "__main__":
    server = ExampleMCPServer()
    server.run()
'''
    
    def _get_gitignore_content(self) -> str:
        """Get .gitignore content for plugins."""
        return '''# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment variables
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Temporary files
tmp/
temp/
'''
    
    def _get_readme_template(self, plugin_type: str) -> str:
        """Get README template for plugin type."""
        return f'''# {{{{name}}}}

{{{{description}}}}

## Installation

```bash
pacc plugin install <repository-url>
```

## Plugin Type

This is a **{plugin_type}** plugin for Claude Code.

## Components

This plugin includes:

- Example {plugin_type[:-1] if plugin_type.endswith('s') else plugin_type}

## Usage

[Add usage instructions here]

## Configuration

[Add configuration details here]

## Contributing

[Add contribution guidelines here]

## License

[Add license information here]
'''


class GitInitializer:
    """Handles Git repository initialization for plugins."""
    
    def init_repository(self, plugin_path: Path) -> bool:
        """Initialize Git repository in plugin directory.
        
        Args:
            plugin_path: Path to plugin directory
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ['git', 'init'],
                cwd=plugin_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            logger.warning("Failed to initialize Git repository")
            return False
    
    def create_gitignore(self, plugin_path: Path) -> None:
        """Create .gitignore file if it doesn't exist.
        
        Args:
            plugin_path: Path to plugin directory
        """
        gitignore_path = plugin_path / '.gitignore'
        if not gitignore_path.exists():
            template_engine = TemplateEngine()
            gitignore_content = template_engine._get_gitignore_content()
            gitignore_path.write_text(gitignore_content)


class PluginCreator:
    """Main plugin creation wizard and scaffolding system."""
    
    def __init__(self):
        self.metadata_collector = MetadataCollector()
        self.template_engine = TemplateEngine()
        self.git_initializer = GitInitializer()
    
    def create_plugin(
        self,
        name: Optional[str] = None,
        plugin_type: Optional[CreationPluginType] = None,
        output_dir: Path = Path.cwd(),
        mode: CreationMode = CreationMode.GUIDED,
        init_git: Optional[bool] = None
    ) -> CreationResult:
        """Create a new plugin with interactive wizard.
        
        Args:
            name: Optional pre-specified plugin name
            plugin_type: Optional pre-specified plugin type
            output_dir: Directory to create plugin in
            mode: Creation mode (guided or quick)
            init_git: Whether to initialize Git repository
            
        Returns:
            CreationResult with operation status and details
        """
        try:
            # Collect plugin type if not specified
            if plugin_type is None:
                plugin_type = self._prompt_for_plugin_type()
            
            # Collect metadata
            metadata = self.metadata_collector.collect_basic_metadata(mode, name=name)
            
            # Check if plugin directory already exists
            plugin_path = output_dir / metadata['name']
            if plugin_path.exists():
                return CreationResult(
                    success=False,
                    error_message=f"Plugin directory '{metadata['name']}' already exists"
                )
            
            # Get template and render files
            template = self.template_engine.get_template(plugin_type)
            rendered_files = self.template_engine.render_template(template, metadata)
            
            # Create plugin scaffold
            created_plugin_path = self._create_scaffold(template, metadata, output_dir)
            
            # Write rendered files
            created_files = []
            for filename, content in rendered_files.items():
                file_path = created_plugin_path / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
                created_files.append(filename)
            
            # Initialize Git repository if requested
            git_initialized = False
            if init_git is None and mode == CreationMode.GUIDED:
                git_response = input("Initialize Git repository? (y/N): ").strip().lower()
                init_git = git_response in ['y', 'yes']
            elif init_git is None:
                init_git = False
            
            if init_git:
                git_initialized = self.git_initializer.init_repository(created_plugin_path)
                if not git_initialized:
                    logger.warning("Failed to initialize Git repository")
            
            return CreationResult(
                success=True,
                plugin_path=created_plugin_path,
                created_files=created_files,
                git_initialized=git_initialized
            )
            
        except Exception as e:
            logger.error(f"Plugin creation failed: {e}")
            return CreationResult(
                success=False,
                error_message=str(e)
            )
    
    def generate_manifest_from_files(self, plugin_path: Path) -> Dict[str, Any]:
        """Generate plugin manifest from existing plugin files.
        
        Args:
            plugin_path: Path to existing plugin directory
            
        Returns:
            Generated manifest dictionary
        """
        manifest = {
            'name': plugin_path.name,
            'version': '1.0.0',
            'components': {}
        }
        
        # Scan for different component types
        component_types = ['hooks', 'agents', 'commands']
        
        for comp_type in component_types:
            comp_dir = plugin_path / comp_type
            if comp_dir.exists() and comp_dir.is_dir():
                files = []
                for file_path in comp_dir.rglob('*'):
                    if file_path.is_file() and not file_path.name.startswith('.'):
                        rel_path = file_path.relative_to(comp_dir)
                        files.append(str(rel_path))
                
                if files:
                    manifest['components'][comp_type] = files
        
        # Check for MCP configuration
        mcp_config = plugin_path / 'mcp.json'
        if mcp_config.exists():
            manifest['components']['mcp'] = ['mcp.json']
        
        return manifest
    
    def _prompt_for_plugin_type(self) -> CreationPluginType:
        """Prompt user to select plugin type.
        
        Returns:
            Selected PluginType
        """
        print("Select plugin type:")
        print("1. Hooks - Event-driven automation")
        print("2. Agents - AI assistants with specific expertise")
        print("3. Commands - Custom slash commands")
        print("4. MCP - Model Context Protocol servers")
        
        while True:
            choice = input("Enter choice (1-4): ").strip()
            type_map = {
                '1': CreationPluginType.HOOKS,
                '2': CreationPluginType.AGENTS,
                '3': CreationPluginType.COMMANDS,
                '4': CreationPluginType.MCP,
                'hooks': CreationPluginType.HOOKS,
                'agents': CreationPluginType.AGENTS,
                'commands': CreationPluginType.COMMANDS,
                'mcp': CreationPluginType.MCP
            }
            
            if choice in type_map:
                return type_map[choice]
            
            print("❌ Invalid choice. Please select 1-4 or type the name.")
    
    def _create_scaffold(
        self,
        template: PluginTemplate,
        metadata: Dict[str, Any],
        output_dir: Path
    ) -> Path:
        """Create plugin directory scaffold.
        
        Args:
            template: Plugin template
            metadata: Plugin metadata
            output_dir: Output directory
            
        Returns:
            Path to created plugin directory
        """
        plugin_path = output_dir / metadata['name']
        plugin_path.mkdir(parents=True, exist_ok=True)
        
        # Create directories specified in template
        for directory in template.directories:
            (plugin_path / directory).mkdir(exist_ok=True)
        
        return plugin_path