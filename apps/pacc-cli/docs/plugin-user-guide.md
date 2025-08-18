# Plugin System User Guide

This guide covers how to use PACC's Claude Code plugin management system to install, manage, and use Claude Code plugins.

## Overview

The PACC plugin system provides comprehensive management for Claude Code plugins, which extend Claude Code functionality through Git-based repositories. Plugins can provide:

- **Commands**: Custom slash commands with markdown templates
- **Agents**: Specialized AI agents with specific tools and prompts
- **Hooks**: Event-driven extensions that execute on Claude Code events

## Quick Start

### Prerequisites

1. Claude Code v1.0.81+ with plugin support
2. Git installed and configured
3. PACC CLI installed (`pip install pacc-cli`)

### Basic Workflow

1. **Enable plugins** (first time only):
   ```bash
   export ENABLE_PLUGINS=1
   # Add to your shell profile for persistence
   echo 'export ENABLE_PLUGINS=1' >> ~/.bashrc  # or ~/.zshrc
   ```

2. **Install a plugin repository**:
   ```bash
   pacc plugin install https://github.com/owner/plugin-repo
   ```

3. **List available plugins**:
   ```bash
   pacc plugin list
   ```

4. **Enable specific plugins**:
   ```bash
   pacc plugin enable owner/plugin-repo/plugin-name
   # or using separate arguments:
   pacc plugin enable plugin-name --repo owner/plugin-repo
   ```

5. **Restart Claude Code** to load the plugins

## Command Reference

### Installation Commands

#### `pacc plugin install <repo_url>`

Install plugins from a Git repository.

```bash
# Install from GitHub
pacc plugin install https://github.com/owner/repo
pacc plugin install git@github.com:owner/repo.git

# Install from other Git services
pacc plugin install https://gitlab.com/owner/repo
pacc plugin install https://bitbucket.org/owner/repo
```

**Options:**
- `--dry-run`: Preview what would be installed without making changes
- `--update`: Update repository if already installed
- `--enable`: Automatically enable all plugins after installation
- `--interactive`: Prompt to select which plugins to enable
- `--verbose`: Show detailed progress information

**Examples:**
```bash
# Dry run to preview
pacc plugin install https://github.com/example/tools --dry-run

# Install and enable automatically
pacc plugin install https://github.com/example/tools --enable

# Install with interactive selection
pacc plugin install https://github.com/example/multi-plugin --interactive
```

### Management Commands

#### `pacc plugin list`

List installed plugins and their status.

```bash
# List all plugins
pacc plugin list

# List plugins from specific repository
pacc plugin list --repo owner/repo

# List only enabled plugins
pacc plugin list --enabled-only

# List only disabled plugins
pacc plugin list --disabled-only

# List plugins by type
pacc plugin list --type commands
pacc plugin list --type agents
pacc plugin list --type hooks
```

**Output formats:**
- `--format table` (default): Formatted table
- `--format json`: JSON output for scripting
- `--format yaml`: YAML output

#### `pacc plugin enable <plugin>`

Enable a plugin to make it active in Claude Code.

```bash
# Enable using full identifier
pacc plugin enable owner/repo/plugin-name

# Enable using separate repo argument
pacc plugin enable plugin-name --repo owner/repo
```

#### `pacc plugin disable <plugin>`

Disable a plugin without uninstalling it.

```bash
# Disable using full identifier
pacc plugin disable owner/repo/plugin-name

# Disable using separate repo argument  
pacc plugin disable plugin-name --repo owner/repo
```

## Repository Structure

Plugin repositories must follow this structure:

```
repository-root/
├── plugin-name/
│   ├── plugin.json          # Plugin manifest (required)
│   ├── commands/            # Slash commands (optional)
│   │   ├── command1.md
│   │   └── subdir/
│   │       └── nested-cmd.md
│   ├── agents/              # AI agents (optional)
│   │   ├── agent1.md
│   │   └── specialized/
│   │       └── expert.md
│   └── hooks/               # Event hooks (optional)
│       └── hooks.json
└── another-plugin/
    ├── plugin.json
    └── commands/
        └── example.md
```

### Plugin Manifest (`plugin.json`)

Every plugin must have a `plugin.json` manifest file:

```json
{
  "name": "example-plugin",
  "version": "1.0.0",
  "description": "Example plugin for demonstration",
  "author": {
    "name": "Plugin Author",
    "email": "author@example.com",
    "url": "https://github.com/author"
  }
}
```

**Required fields:**
- `name`: Plugin identifier (alphanumeric, hyphens, underscores only)

**Recommended fields:**
- `version`: Semantic version (e.g., "1.2.3")
- `description`: Brief description of plugin functionality
- `author`: Author information with name (required), email, and URL

### Commands

Commands are markdown files with YAML frontmatter:

```markdown
---
description: Brief description of the command
argument-hint: "description of expected arguments"
allowed-tools: [Read, Write, Edit, Bash]
model: claude-3-opus
---

# Command Template

This is the prompt template for the command.

Use $ARGUMENTS to access user-provided arguments.
Use ${CLAUDE_PLUGIN_ROOT} to reference plugin directory.
```

**Frontmatter fields:**
- `description`: Command description (shown in help)
- `argument-hint`: Hint for command arguments
- `allowed-tools`: Tools the command can use (optional restriction)
- `model`: Preferred model for the command

**Template variables:**
- `$ARGUMENTS`: User-provided command arguments
- `${CLAUDE_PLUGIN_ROOT}`: Absolute path to plugin directory

### Agents

Agents are markdown files defining specialized AI assistants:

```markdown
---
name: Display Name
description: When to use this agent
tools: [Read, Write, Edit, Grep, Bash]
color: cyan
model: claude-3-opus
---

You are a specialized agent for [specific purpose].

Your role includes:
1. [Primary responsibility]
2. [Secondary responsibility]
3. [Additional capabilities]

Always [specific instruction for behavior].
```

**Frontmatter fields:**
- `name`: Display name for the agent
- `description`: When to use this agent
- `tools`: Tools available to the agent
- `color`: Terminal color (optional)
- `model`: Preferred model (optional)

### Hooks

Hooks are JSON files defining event-driven behavior:

```json
{
  "hooks": [
    {
      "type": "SessionStart",
      "action": {
        "command": "echo 'Plugin loaded!'",
        "timeout": 1000
      }
    },
    {
      "type": "PreToolUse",
      "matcher": {
        "toolName": "Bash",
        "argumentPattern": "rm -rf"
      },
      "action": {
        "command": "echo 'WARNING: Dangerous command detected!'",
        "timeout": 2000
      }
    }
  ]
}
```

**Hook types:**
- `SessionStart`: Triggered when Claude Code starts
- `SessionEnd`: Triggered when Claude Code ends
- `PreToolUse`: Before tool execution
- `PostToolUse`: After tool execution
- `UserPromptSubmit`: When user submits a prompt
- `Notification`: System notifications

## Team Collaboration

### Project Configuration

Create a `pacc.json` file in your project root to define team plugin requirements:

```json
{
  "plugins": {
    "team/utilities": ["formatter", "linter", "docs-generator"],
    "team/agents": ["code-reviewer", "security-scanner"],
    "community/tools": ["git-hooks"]
  }
}
```

### Synchronization

Team members can sync plugins using:

```bash
# In project directory with pacc.json
pacc plugin sync
```

This will:
1. Install any missing plugin repositories
2. Enable the specified plugins
3. Update existing repositories
4. Report any conflicts or errors

## Advanced Usage

### Environment Variables

- `ENABLE_PLUGINS=1`: Required to enable plugin system in Claude Code
- `CLAUDE_PLUGIN_ROOT`: Set by Claude Code, points to plugin directory

### Configuration Files

PACC manages these configuration files:

- `~/.claude/plugins/config.json`: Repository tracking and metadata
- `~/.claude/settings.json`: Plugin enable/disable states (enabledPlugins section)
- `./pacc.json`: Project-specific plugin requirements

### Plugin Namespacing

Plugin components use namespaced identifiers to avoid conflicts:

- Commands: `plugin-name:command-name` or `plugin-name:subdir:command-name`
- Agents: `plugin-name:agent-name` or `plugin-name:subdir:agent-name`
- Hooks: `plugin-name:hook-file-name`

## Troubleshooting

### Common Issues

#### "ENABLE_PLUGINS not set"
```bash
export ENABLE_PLUGINS=1
# Add to shell profile for persistence
```

#### "No plugins found in repository"
- Verify repository has proper plugin structure
- Ensure `plugin.json` files exist in plugin directories
- Check that directories contain commands/, agents/, or hooks/

#### "Plugin not found"
- Use `pacc plugin list` to see available plugins
- Verify plugin name spelling and repository
- Ensure repository was installed successfully

#### "Permission denied" during installation
- Check Git repository permissions
- Verify SSH keys for private repositories
- Use HTTPS URLs for public repositories

### Debug Mode

Use verbose mode for detailed information:

```bash
pacc plugin install https://github.com/owner/repo --verbose
pacc plugin list --verbose
```

### Configuration Validation

Check configuration integrity:

```bash
# List all plugins with detailed status
pacc plugin list --format json

# Validate repository structure
pacc plugin install https://github.com/owner/repo --dry-run
```

## Best Practices

### Plugin Development

1. **Use semantic versioning** in plugin.json
2. **Provide clear descriptions** for commands and agents
3. **Test hooks carefully** - they execute on every event
4. **Keep plugins focused** - single responsibility per plugin
5. **Document template variables** in command bodies
6. **Use appropriate timeouts** for hook actions

### Repository Management

1. **Organize plugins logically** in separate directories
2. **Use consistent naming** across plugins
3. **Include examples** in plugin descriptions
4. **Version control** plugin.json changes
5. **Test on multiple platforms** before publishing

### Team Workflow

1. **Define plugin requirements** in pacc.json
2. **Document custom plugins** for team members
3. **Use version pinning** for stable environments
4. **Regular sync** to keep plugins updated
5. **Review plugin changes** before team adoption

## Security Considerations

### Plugin Safety

- **Review plugin code** before installation from untrusted sources
- **Check hook commands** - they execute arbitrary shell commands
- **Use private repositories** for sensitive internal plugins
- **Limit tool access** in command frontmatter when possible
- **Monitor plugin activity** in verbose mode

### Repository Access

- **Use HTTPS URLs** for public repositories
- **Configure SSH keys** properly for private repositories
- **Verify repository ownership** before installation
- **Keep Git credentials secure**

## Support

For issues and questions:

- **Integration Issues**: Check integration test results
- **Performance Problems**: Use `--verbose` mode for diagnosis
- **Configuration Errors**: Verify JSON syntax in config files
- **Plugin Development**: Refer to plugin manifest schema

The plugin system is designed to be robust with automatic backup, rollback, and atomic operations to ensure your Claude Code configuration remains stable.