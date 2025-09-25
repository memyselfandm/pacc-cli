# Plugin System User Guide

This guide covers how to use PACC's Claude Code plugin management system to install, manage, and use Claude Code plugins.

## Overview

The PACC plugin system provides comprehensive management for Claude Code plugins, which extend Claude Code functionality through Git-based repositories. Plugins can provide:

- **Commands**: Custom slash commands with markdown templates
- **Agents**: Specialized AI agents with specific tools and prompts
- **Hooks**: Event-driven extensions that execute on Claude Code events

## Environment Setup

Before using PACC's plugin management system, you need to configure your environment to enable Claude Code's plugin support.

### Automatic Environment Setup (Recommended)

PACC can automatically configure your environment when you install your first plugin:

```bash
# PACC will detect missing ENABLE_PLUGINS and offer to configure it
pacc plugin install https://github.com/owner/plugin-repo

# Or explicitly configure the environment
pacc env setup
```

When you install a plugin, PACC will:
1. Detect if `ENABLE_PLUGINS=1` is missing
2. Prompt you to configure it automatically
3. Update your shell profile for persistence
4. Verify the configuration works

### Manual Environment Setup

If you prefer manual configuration, set up the environment variable:

#### macOS/Linux (Bash)
```bash
# Add to ~/.bashrc
echo 'export ENABLE_PLUGINS=1' >> ~/.bashrc
source ~/.bashrc
```

#### macOS/Linux (Zsh)
```bash
# Add to ~/.zshrc
echo 'export ENABLE_PLUGINS=1' >> ~/.zshrc
source ~/.zshrc
```

#### Windows (PowerShell)
```powershell
# Set user environment variable
[Environment]::SetEnvironmentVariable("ENABLE_PLUGINS", "1", "User")
# Restart PowerShell to apply
```

#### Windows (Command Prompt)
```cmd
# Set user environment variable
setx ENABLE_PLUGINS 1
# Restart command prompt to apply
```

### Environment Verification

Check if your environment is correctly configured:

```bash
# Check environment variable
pacc env check

# Manual verification
echo $ENABLE_PLUGINS  # Should output: 1
```

### Cross-Platform Setup Instructions

#### Windows Subsystem for Linux (WSL)
```bash
# In WSL terminal
echo 'export ENABLE_PLUGINS=1' >> ~/.bashrc
source ~/.bashrc

# Verify in WSL
pacc env check
```

#### Docker/Container Environments
```dockerfile
# In Dockerfile
ENV ENABLE_PLUGINS=1

# Or in docker-compose.yml
environment:
  - ENABLE_PLUGINS=1
```

#### SSH/Remote Development
```bash
# Add to remote ~/.bashrc or ~/.zshrc
ssh user@remote 'echo "export ENABLE_PLUGINS=1" >> ~/.bashrc'

# Or copy local configuration
scp ~/.bashrc user@remote:~/
```

## Quick Start

### Prerequisites

1. Claude Code v1.0.81+ with plugin support
2. Git installed and configured
3. PACC CLI installed (`pip install pacc-cli`)
4. Environment configured (see Environment Setup above)

### Basic Workflow

1. **Verify environment** (first time):
   ```bash
   pacc env check
   # Should show: ✅ ENABLE_PLUGINS is configured
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

## Converting Extensions to Plugins

PACC provides powerful conversion tools to transform existing Claude Code extensions (hooks, agents, commands, MCP servers) into the structured plugin format. This enables you to share your extensions with the community or organize them into reusable plugins.

### Quick Conversion

Convert a single directory containing extensions:

```bash
# Convert extensions from a .claude directory
pacc plugin convert /path/to/project

# Convert with custom metadata
pacc plugin convert /path/to/project --name my-plugin --author "Your Name" --version 2.0.0

# Convert to specific output directory
pacc plugin convert /path/to/project --output ~/my-plugins
```

### Batch Conversion

Convert multiple extensions into separate plugins:

```bash
# Convert all extensions in a directory (creates separate plugins by type)
pacc plugin convert /path/to/project --batch

# Batch convert with custom output location
pacc plugin convert /path/to/project --batch --output ~/converted-plugins
```

### Direct Git Push

Convert and immediately push to a Git repository:

```bash
# Convert and push to GitHub
pacc plugin convert /path/to/project --repo https://github.com/username/my-plugin.git

# Convert with metadata and push
pacc plugin convert /path/to/project \
  --name my-awesome-plugin \
  --author "Your Name" \
  --repo https://github.com/username/my-awesome-plugin.git
```

### Push Existing Plugins

Push a local plugin directory to Git:

```bash
# Push plugin to repository
pacc plugin push /path/to/plugin https://github.com/username/plugin-repo.git

# Push with specific authentication method
pacc plugin push /path/to/plugin https://github.com/username/plugin-repo.git --auth ssh

# Push private repository
pacc plugin push /path/to/plugin https://github.com/username/private-plugin.git --private
```

### Conversion Options

#### `pacc plugin convert <extension_path>`

Convert Claude Code extensions to plugin format.

**Arguments:**
- `extension_path`: Path to extension file or directory containing `.claude` folder

**Options:**
- `--name`: Plugin name (auto-generated from directory if not specified)
- `--version`: Plugin version (default: 1.0.0)
- `--author`: Plugin author information
- `--output, -o`: Output directory for converted plugins
- `--batch`: Convert all extensions in directory as separate plugins
- `--repo`: Git repository URL for direct push after conversion
- `--overwrite`: Overwrite existing plugin directories

**Examples:**

```bash
# Basic conversion with interactive prompts
pacc plugin convert ~/my-project

# Full specification
pacc plugin convert ~/my-project \
  --name productivity-tools \
  --version 1.2.0 \
  --author "Development Team <team@company.com>" \
  --output ~/plugins

# Batch conversion of multiple extensions
pacc plugin convert ~/large-project --batch --output ~/converted-plugins

# Convert and push in one step
pacc plugin convert ~/my-project --repo https://github.com/team/tools.git
```

#### `pacc plugin push <plugin_path> <repo_url>`

Push a local plugin to a Git repository.

**Arguments:**
- `plugin_path`: Path to local plugin directory
- `repo_url`: Git repository URL (HTTPS or SSH)

**Options:**
- `--private`: Repository is private (affects auth handling)
- `--auth`: Authentication method (`https` or `ssh`, default: https)

**Examples:**

```bash
# Push to GitHub with HTTPS
pacc plugin push ~/plugins/my-plugin https://github.com/username/my-plugin.git

# Push to private repository with SSH
pacc plugin push ~/plugins/secret-plugin git@github.com:username/secret-plugin.git --auth ssh

# Push to GitLab
pacc plugin push ~/plugins/my-plugin https://gitlab.com/username/my-plugin.git
```

### Conversion Process

The conversion process performs these steps:

1. **Scan**: Discovers all Claude Code extensions in the source directory
2. **Validate**: Checks each extension for proper format and structure
3. **Convert**: Transforms extensions into plugin format:
   - **Hooks**: Merges multiple hook files into `hooks/hooks.json`
   - **Agents**: Copies agent files to `agents/` directory
   - **Commands**: Preserves directory structure in `commands/`
   - **MCP**: Merges server configurations into `mcp/config.json`
4. **Generate**: Creates `plugin.json` manifest with metadata
5. **Package**: Creates complete plugin directory structure

### Generated Plugin Structure

Converted plugins follow the standard structure:

```
converted-plugin/
├── plugin.json              # Generated manifest
├── README.md               # Auto-generated documentation
├── .gitignore             # Git ignore file
├── hooks/                 # Converted hooks (if any)
│   └── hooks.json
├── agents/                # Converted agents (if any)
│   ├── agent1.md
│   └── agent2.md
├── commands/              # Converted commands (if any)
│   ├── cmd1.md
│   └── subdir/
│       └── cmd2.md
└── mcp/                   # Converted MCP servers (if any)
    └── config.json
```

### Auto-Generated Documentation

Converted plugins include comprehensive documentation:

- **README.md**: Complete usage guide with installation instructions
- **Component inventory**: Lists all commands, agents, and hooks
- **Installation examples**: Ready-to-use pacc commands
- **Usage examples**: Sample invocations for each component

### Conversion Best Practices

1. **Review before converting**: Ensure extensions work correctly
2. **Use descriptive names**: Choose clear, searchable plugin names
3. **Add version information**: Start with semantic versioning (1.0.0)
4. **Include author details**: Provide contact information
5. **Test conversions**: Verify converted plugins install correctly
6. **Document custom features**: Add specific usage notes to generated README

### Conversion Troubleshooting

#### "No extensions found"
- Verify the source directory contains a `.claude` folder
- Check that extensions are in the correct subdirectories (`hooks/`, `agents/`, etc.)
- Use `--verbose` flag for detailed scanning information

#### "Validation errors during conversion"
- Review extension files for syntax errors
- Ensure hook files use valid JSON format
- Check agent markdown files have proper YAML frontmatter
- Verify command files are valid markdown

#### "Plugin name conflicts"
- Use `--name` option to specify a unique plugin name
- Check existing plugins with `pacc plugin list`
- Use namespace prefixes (e.g., `company-toolname`)

#### "Git push authentication failed"
- Configure Git credentials properly
- Use SSH keys for SSH URLs
- Use personal access tokens for HTTPS to private repositories
- Verify repository permissions and existence

#### "Conversion rate below 95%"
- Check validation errors in output
- Fix invalid extension files before conversion
- Some extensions may be intentionally skipped (corrupted files)

### Integration with Plugin System

Converted plugins work seamlessly with the existing plugin system:

```bash
# Convert extensions
pacc plugin convert ~/my-project --name my-tools

# Push to GitHub
pacc plugin push ~/converted-plugins/my-tools https://github.com/username/my-tools.git

# Install from repository (different machine/team member)
pacc plugin install https://github.com/username/my-tools

# Enable the plugin
pacc plugin enable my-tools --repo username/my-tools
```

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

### Environment Issues

#### "ENABLE_PLUGINS not set"

**Problem**: Claude Code cannot load plugins because the environment variable is missing.

**Solutions**:
```bash
# Quick fix (temporary)
export ENABLE_PLUGINS=1

# Permanent fix (run PACC setup)
pacc env setup

# Manual permanent fix
echo 'export ENABLE_PLUGINS=1' >> ~/.bashrc  # or ~/.zshrc
source ~/.bashrc
```

**Verification**:
```bash
pacc env check
echo $ENABLE_PLUGINS  # Should output: 1
```

#### "Environment variable not persisting"

**Problem**: `ENABLE_PLUGINS=1` works in current session but disappears after restart.

**Cause**: Variable not added to shell profile

**Solutions**:
```bash
# Identify your shell
echo $SHELL

# For Bash users
echo 'export ENABLE_PLUGINS=1' >> ~/.bashrc
echo 'export ENABLE_PLUGINS=1' >> ~/.bash_profile

# For Zsh users
echo 'export ENABLE_PLUGINS=1' >> ~/.zshrc

# For Fish users
echo 'set -gx ENABLE_PLUGINS 1' >> ~/.config/fish/config.fish

# Test persistence
# Close terminal, reopen, then:
echo $ENABLE_PLUGINS
```

#### "Shell profile conflicts"

**Problem**: Multiple shell profiles causing conflicts or overrides.

**Symptoms**: Variable sometimes works, sometimes doesn't.

**Solution**:
```bash
# Check which profiles exist
ls -la ~/.*rc ~/.*profile

# Check which profiles are sourced
echo "Checking shell startup files..."
grep -r "ENABLE_PLUGINS" ~/.bashrc ~/.zshrc ~/.bash_profile ~/.profile 2>/dev/null

# Clean up duplicates - remove from all but one primary file
# For Bash: use ~/.bashrc
# For Zsh: use ~/.zshrc

# Verify single source
pacc env check --verbose
```

#### "Permission denied when updating shell profile"

**Problem**: Cannot write to shell profile files.

**Cause**: File permissions or ownership issues.

**Solution**:
```bash
# Check file ownership
ls -la ~/.bashrc ~/.zshrc

# Fix ownership if needed
chown $USER:$USER ~/.bashrc ~/.zshrc

# Fix permissions
chmod 644 ~/.bashrc ~/.zshrc

# Retry setup
pacc env setup
```

#### "Windows environment variable not working"

**Problem**: Set `ENABLE_PLUGINS=1` on Windows but Claude Code doesn't see it.

**Solutions**:

**For PowerShell**:
```powershell
# Set user environment variable
[Environment]::SetEnvironmentVariable("ENABLE_PLUGINS", "1", "User")

# Verify it's set
[Environment]::GetEnvironmentVariable("ENABLE_PLUGINS", "User")

# Restart PowerShell and verify
$env:ENABLE_PLUGINS
```

**For Command Prompt**:
```cmd
setx ENABLE_PLUGINS 1
# Restart cmd and verify
echo %ENABLE_PLUGINS%
```

**For WSL**:
```bash
# WSL needs its own configuration
echo 'export ENABLE_PLUGINS=1' >> ~/.bashrc
source ~/.bashrc
echo $ENABLE_PLUGINS
```

#### "Docker/Container environment issues"

**Problem**: Plugins not working in containerized development.

**Solution**:
```dockerfile
# In Dockerfile
ENV ENABLE_PLUGINS=1

# In docker-compose.yml
services:
  app:
    environment:
      - ENABLE_PLUGINS=1
    # or
    env_file:
      - .env  # where .env contains ENABLE_PLUGINS=1
```

**Verification in container**:
```bash
docker exec -it container_name bash
echo $ENABLE_PLUGINS
pacc env check
```

#### "SSH/Remote development environment issues"

**Problem**: Local environment works but remote doesn't have plugins enabled.

**Solution**:
```bash
# Configure remote environment
ssh user@remote 'echo "export ENABLE_PLUGINS=1" >> ~/.bashrc'

# Or copy your configuration
scp ~/.bashrc user@remote:~/

# Verify on remote
ssh user@remote 'echo $ENABLE_PLUGINS'

# Use SSH config for automatic setup
echo "SendEnv ENABLE_PLUGINS" >> ~/.ssh/config
```

#### "IDE/Editor terminal environment issues"

**Problem**: Plugins work in regular terminal but not in IDE terminal.

**Cause**: IDE may not inherit shell environment variables.

**Solutions**:

**VS Code**:
```json
// In settings.json
{
  "terminal.integrated.env.osx": {
    "ENABLE_PLUGINS": "1"
  },
  "terminal.integrated.env.linux": {
    "ENABLE_PLUGINS": "1"
  },
  "terminal.integrated.env.windows": {
    "ENABLE_PLUGINS": "1"
  }
}
```

**IntelliJ/PyCharm**:
- Settings → Build, Execution, Deployment → Console → Environment Variables
- Add: `ENABLE_PLUGINS=1`

**General solution**:
```bash
# Restart IDE after setting environment variable
# Or launch IDE from terminal with environment
ENABLE_PLUGINS=1 code .
ENABLE_PLUGINS=1 pycharm .
```

### Plugin Loading Issues

#### "Plugin verification failed"

**Problem**: Plugins fail to load with verification errors.

**Diagnosis**:
```bash
# Check plugin configuration
pacc plugin list --verbose

# Verify plugin structure
pacc plugin info plugin-name --repo owner/repo --verbose

# Check Claude Code plugin directory
ls -la ~/.claude/plugins/repos/

# Verify configuration files
cat ~/.claude/plugins/config.json
cat ~/.claude/settings.json | grep -A 10 "enabledPlugins"
```

**Solutions**:
```bash
# Reinstall problematic plugin
pacc plugin remove plugin-name --repo owner/repo
pacc plugin install https://github.com/owner/repo --enable

# Reset plugin configuration
pacc env reset  # If this command exists
# Or manually:
mv ~/.claude/plugins/config.json ~/.claude/plugins/config.json.backup
pacc plugin install https://github.com/owner/repo
```

#### "Plugin directory permissions"

**Problem**: Cannot write to plugin directory.

**Solution**:
```bash
# Check permissions
ls -la ~/.claude/plugins/

# Fix permissions
chmod -R 755 ~/.claude/plugins/
chown -R $USER:$USER ~/.claude/plugins/

# Recreate if needed
rm -rf ~/.claude/plugins/
mkdir -p ~/.claude/plugins/repos/
```

### Team Environment Issues

#### "Inconsistent environment across team members"

**Problem**: Some team members have plugins working, others don't.

**Solution**: Create team setup script:

```bash
#!/bin/bash
# team-setup.sh

echo "Setting up PACC environment for team..."

# Check if PACC is installed
if ! command -v pacc &> /dev/null; then
    echo "Installing PACC CLI..."
    pip install pacc-cli
fi

# Setup environment
echo "Configuring environment..."
pacc env setup

# Install team plugins
echo "Installing team plugins..."
if [ -f "pacc.json" ]; then
    pacc plugin sync
else
    echo "No pacc.json found. Please create one with team plugin requirements."
fi

# Verify setup
echo "Verifying setup..."
pacc env check
pacc plugin list

echo "Team setup complete!"
```

#### "Environment variable conflicts in CI/CD"

**Problem**: CI/CD pipeline can't access or set `ENABLE_PLUGINS`.

**Solution**:
```yaml
# GitHub Actions
env:
  ENABLE_PLUGINS: 1

# GitLab CI
variables:
  ENABLE_PLUGINS: 1

# Jenkins
environment {
  ENABLE_PLUGINS = '1'
}

# Docker-based CI
docker run -e ENABLE_PLUGINS=1 ...
```

### Advanced Troubleshooting

#### "Environment check shows conflicting information"

**Problem**: `pacc env check` shows different results than manual checks.

**Diagnosis**:
```bash
# Compare different methods
echo "Manual check: $ENABLE_PLUGINS"
pacc env check --verbose
env | grep ENABLE_PLUGINS
printenv ENABLE_PLUGINS

# Check shell initialization
bash -c 'echo $ENABLE_PLUGINS'
zsh -c 'echo $ENABLE_PLUGINS'
```

#### "Multiple shell environments causing issues"

**Problem**: Different behavior in different shells or terminals.

**Solution**:
```bash
# Standardize across shells
# Create ~/.profile with common settings
echo 'export ENABLE_PLUGINS=1' >> ~/.profile

# Ensure shells source ~/.profile
echo 'source ~/.profile' >> ~/.bashrc
echo 'source ~/.profile' >> ~/.zshrc

# Test all shells
bash -c 'echo "Bash: $ENABLE_PLUGINS"'
zsh -c 'echo "Zsh: $ENABLE_PLUGINS"'
```

### Environment Diagnostic Commands

```bash
# Comprehensive environment diagnosis
pacc env check --verbose --debug

# Manual diagnostic checklist
echo "=== Environment Diagnostic ==="
echo "Shell: $SHELL"
echo "User: $USER"
echo "Home: $HOME"
echo "ENABLE_PLUGINS: $ENABLE_PLUGINS"
echo "Claude plugins dir: ~/.claude/plugins/"
ls -la ~/.claude/plugins/ 2>/dev/null || echo "No plugins directory"
echo "PACC version:"
pacc --version
echo "=== End Diagnostic ==="
```

### Common Issues

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

### Environment Management

1. **Standardize team environment setup**:
   ```bash
   # Create team-setup.sh script
   #!/bin/bash
   echo "Setting up team environment..."
   pacc env setup
   pacc plugin sync
   pacc env check
   ```

2. **Document environment requirements**:
   ```markdown
   # Team Environment Setup

   ## Prerequisites
   - Claude Code v1.0.81+
   - PACC CLI installed
   - Git configured

   ## Setup
   ```bash
   ./team-setup.sh
   pacc env check
   ```
   ```

3. **Use consistent shell configuration**:
   - Standardize on Bash or Zsh across team
   - Document which shell profile to use (.bashrc vs .zshrc)
   - Include environment setup in onboarding checklist

4. **CI/CD environment consistency**:
   ```yaml
   # .github/workflows/main.yml
   env:
     ENABLE_PLUGINS: 1

   jobs:
     test:
       steps:
         - name: Setup PACC
           run: |
             pip install pacc-cli
             pacc env check
   ```

5. **Cross-platform considerations**:
   - Test setup scripts on Windows, macOS, and Linux
   - Document platform-specific requirements
   - Use Docker for consistent environments when possible

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

### Development vs Production Environment Management

1. **Separate environment configurations**:
   ```json
   {
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

2. **Environment-specific setup**:
   ```bash
   # Development environment
   pacc plugin sync --environment development

   # Production environment
   pacc plugin sync --environment production
   ```

3. **Security considerations for shared environments**:
   - Use private repositories for internal plugins
   - Review plugin code before installation
   - Monitor plugin activity in production
   - Use specific version pins for production stability

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
