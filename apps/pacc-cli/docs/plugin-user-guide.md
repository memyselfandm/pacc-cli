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

#### `pacc plugin info <plugin>`

Get detailed information about a specific plugin.

```bash
# Get plugin information
pacc plugin info plugin-name --repo owner/repo

# JSON output for scripting
pacc plugin info plugin-name --repo owner/repo --format json

# Table format (default)
pacc plugin info plugin-name --repo owner/repo --format table
```

**Information includes:**
- Plugin metadata (name, version, author, description)
- Installation status and enablement state
- Repository details (URL, commit SHA, last updated)
- Available components (commands, agents, hooks)
- File path location

#### `pacc plugin update <repo>`

Update a plugin repository to a new version or commit.

```bash
# Update repository to latest version
pacc plugin update owner/repo

# Update to specific version
pacc plugin update owner/repo --version v2.0.0

# Update to specific commit
pacc plugin update owner/repo --version abc1234

# Preview what would be updated (dry run)
pacc plugin update owner/repo --dry-run

# Update with automatic backup creation
pacc plugin update owner/repo --create-backup

# Force update without confirmation
pacc plugin update owner/repo --force
```

**Options:**
- `--version`: Target version, tag, branch, or commit SHA
- `--dry-run`: Preview what would be updated without making changes
- `--force`: Skip confirmation prompts
- `--create-backup`: Create backup before updating (recommended)
- `--verbose`: Show detailed update progress
- `--json`: Output results in JSON format

**Update Behavior:**
- Checks current repository state and target version
- Creates backup if requested (stored in `.claude/plugins/backups/`)
- Updates repository files to target version
- Preserves plugin enablement states
- Shows preview of changes before applying
- Supports rollback on failure

**Rollback Support:**
- Automatic rollback if update fails
- Manual rollback using backup directory
- Transaction-based updates for safety
- Preserves configuration state during rollback

**Examples:**
```bash
# Safe update with backup
pacc plugin update team/productivity-tools --create-backup --version v2.1.0

# Preview update changes
pacc plugin update team/ai-agents --dry-run --verbose

# Update multiple repositories
for repo in team/tools community/plugins; do
  pacc plugin update $repo --create-backup
done
```

#### `pacc plugin remove <plugin>`

Remove a plugin and optionally its repository files.

```bash
# Remove plugin only (keep repository if it has other plugins)
pacc plugin remove plugin-name --repo owner/repo

# Remove plugin and repository files (if no other plugins)
pacc plugin remove plugin-name --repo owner/repo --force

# Preview what would be removed (dry run)
pacc plugin remove plugin-name --repo owner/repo --dry-run

# Keep repository files but disable plugin
pacc plugin remove plugin-name --repo owner/repo --keep-files
```

**Options:**
- `--dry-run`: Preview what would be removed without making changes
- `--keep-files`: Disable plugin but keep repository files
- `--force`: Skip confirmation prompt
- `--repo`: Specify repository (required)

**Behavior:**
- Disables the plugin in Claude Code settings
- Removes plugin from repository configuration
- Optionally removes repository files if it's the last plugin
- Uses atomic transactions for safe operations

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
  "name": "my-project",
  "version": "1.0.0",
  "plugins": {
    "repositories": [
      "team/productivity-tools@v1.0.0",
      {
        "repository": "community/ai-agents",
        "version": "main",
        "plugins": ["code-reviewer", "documentation-helper"]
      }
    ],
    "required": ["code-reviewer", "formatter"],
    "optional": ["documentation-helper", "advanced-linter"]
  },
  "environments": {
    "development": {
      "plugins": {
        "repositories": ["team/dev-tools@latest"]
      }
    },
    "production": {
      "plugins": {
        "repositories": ["team/stable-tools@v2.0.0"]
      }
    }
  }
}
```

### Synchronization with `pacc plugin sync`

Team members can sync plugins using the sync command:

```bash
# Sync plugins for current project
pacc plugin sync

# Sync with specific environment
pacc plugin sync --environment development

# Preview changes without applying them
pacc plugin sync --dry-run

# Force sync without user confirmation
pacc plugin sync --force

# Verbose output for debugging
pacc plugin sync --verbose

# JSON output for scripting
pacc plugin sync --json
```

**Configuration Discovery:**
The sync command looks for configuration files in this order:
1. `pacc.json` (team/project configuration)
2. `pacc.local.json` (local developer overrides)
3. Global user settings

**Sync Behavior:**
1. **Install missing repositories** specified in configuration
2. **Update existing repositories** to specified versions
3. **Enable required plugins** automatically
4. **Handle version conflicts** with intelligent resolution
5. **Report warnings and errors** for manual review
6. **Support rollback** if conflicts cannot be resolved

### Local Overrides

Create a `pacc.local.json` file for developer-specific overrides:

```json
{
  "plugins": {
    "repositories": ["personal/dev-utils@latest"],
    "optional": ["personal-debugger", "custom-formatter"]
  }
}
```

**Conflict Resolution:**
- Local configurations take precedence over team configurations
- Version conflicts are resolved by preferring local versions
- Warnings are shown for any conflicts that require attention

### Version Management

**Version Specifications:**
```json
{
  "plugins": {
    "repositories": [
      "team/tools@v1.0.0",           // Specific version tag
      "team/tools@main",             // Branch name
      "team/tools@abc1234",          // Commit SHA
      "team/tools@latest",           // Latest version
      "team/tools"                   // Defaults to latest
    ]
  }
}
```

**Version Locking:**
- Specific versions (tags/commits) are locked and won't auto-update
- Branch names and "latest" are dynamic and update during sync
- Use specific versions for production stability

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

#### "No pacc.json found" during sync
- Create a `pacc.json` file in your project root
- Use `pacc init` to create a basic configuration template
- Ensure you're running sync from the correct directory

#### "Version conflict detected" during sync
- Review conflicting versions in output
- Use `pacc.local.json` for local overrides
- Specify exact versions to avoid conflicts
- Use `--force` to apply team configuration

#### "Plugin info not available"
- Check that the plugin repository is still accessible
- Verify the plugin exists with `pacc plugin list`
- Use `--verbose` for detailed error information

#### "Failed to remove plugin files"
- Check filesystem permissions
- Ensure no processes are using plugin files
- Use `--keep-files` to disable without removing files
- Run with elevated permissions if necessary

#### "Transaction failed" during remove operation
- Check available disk space
- Verify configuration file permissions
- Use `--dry-run` to preview changes first
- Check for concurrent PACC operations

#### "Update failed" during plugin update
- Check Git repository connectivity
- Verify target version/commit exists
- Use `--dry-run` to preview changes first
- Check available disk space for backup creation
- Ensure no processes are using plugin files

#### "Rollback failed" after update failure
- Check backup directory exists and has correct permissions
- Verify source repository state before update
- Use manual rollback from backup directory
- Check for filesystem corruption or space issues

#### "Version not found" during update
- Verify the target version/tag/commit exists in repository
- Check network connectivity to repository
- Use `git ls-remote` to list available versions
- Try updating to `latest` or `main` branch first

### Team Collaboration Issues

#### "Sync conflicts between team members"
- Use consistent version specifications in `pacc.json`
- Create clear team guidelines for plugin updates
- Use local overrides (`pacc.local.json`) for personal preferences
- Communicate plugin changes through version control

#### "Different plugin versions across environments"
- Use environment-specific configurations
- Pin specific versions for production
- Document version requirements in project README
- Use automated sync in CI/CD pipelines

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

**Example Team Workflow:**
```bash
# Team lead: Set up project configuration
pacc init
# Edit pacc.json to define required plugins

# Team members: Join project and sync
git clone project-repo
cd project-repo
pacc plugin sync

# Developer: Check plugin status
pacc plugin list --enabled-only
pacc plugin info code-reviewer --repo team/tools

# Developer: Update existing plugin to new version
pacc plugin update team/tools --version v2.0.0 --create-backup --dry-run
pacc plugin update team/tools --version v2.0.0 --create-backup

# Developer: Remove unwanted plugin
pacc plugin remove old-formatter --repo team/tools --dry-run
pacc plugin remove old-formatter --repo team/tools

# Team: Update to new plugin versions
# Update pacc.json with new versions
pacc plugin sync --dry-run  # Preview changes
pacc plugin sync            # Apply updates
```

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