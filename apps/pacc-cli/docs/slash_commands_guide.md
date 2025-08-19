# PACC Slash Commands Guide

This guide explains how to use PACC slash commands within Claude Code for seamless extension management.

## Overview

PACC provides native Claude Code integration through slash commands, allowing you to manage extensions directly within your coding session without switching to the terminal.

## Available Commands

All PACC commands are namespaced under `/pacc:` to avoid conflicts with other tools.

### Extension Management Commands

#### `/pacc:install`

Install Claude Code extensions from various sources.

**Syntax:**
```
/pacc:install <source> [--type <type>] [--user|--project] [--force] [--all]
```

**Examples:**
```
/pacc:install https://github.com/user/extension.git
/pacc:install ./local/extension.json --type hooks
/pacc:install path/to/directory --all
```

### Plugin Management Commands

#### `/plugin:install`

Install plugins from Git repositories with automatic environment setup.

**Syntax:**
```
/plugin:install <repo_url> [--enable] [--interactive] [--dry-run]
```

**Examples:**
```
/plugin:install https://github.com/owner/plugin-repo
/plugin:install https://github.com/team/tools --enable
/plugin:install https://github.com/multi/plugins --interactive
```

**Features:**
- Automatic ENABLE_PLUGINS=1 configuration
- Repository cloning and management
- Plugin discovery and selection
- Environment verification

#### `/plugin:list`

List installed plugins with status and repository information.

**Syntax:**
```
/plugin:list [--repo <owner/repo>] [--enabled-only] [--disabled-only] [--format <format>]
```

**Examples:**
```
/plugin:list
/plugin:list --repo team/tools
/plugin:list --enabled-only --format json
/plugin:list --type commands
```

**Output includes:**
- Plugin name and description
- Repository source
- Enable/disable status
- Available components (commands, agents, hooks)

#### `/plugin:enable`

Enable a plugin to make it active in Claude Code.

**Syntax:**
```
/plugin:enable <plugin-name> --repo <owner/repo>
```

**Examples:**
```
/plugin:enable code-reviewer --repo team/tools
/plugin:enable documentation-helper --repo community/plugins
```

#### `/plugin:disable`

Disable a plugin without removing it.

**Syntax:**
```
/plugin:disable <plugin-name> --repo <owner/repo>
```

**Examples:**
```
/plugin:disable old-formatter --repo team/tools
/plugin:disable experimental-feature --repo personal/experiments
```

#### `/plugin:info`

Get detailed information about a specific plugin.

**Syntax:**
```
/plugin:info <plugin-name> --repo <owner/repo> [--format <format>]
```

**Examples:**
```
/plugin:info code-reviewer --repo team/tools
/plugin:info ai-assistant --repo community/agents --format json
```

**Information includes:**
- Plugin metadata (version, author, description)
- Installation status and enablement state
- Repository details (URL, commit SHA, last updated)
- Available components with descriptions
- Usage examples

#### `/plugin:update`

Update a plugin repository to the latest version.

**Syntax:**
```
/plugin:update <owner/repo> [--version <version>] [--dry-run] [--create-backup]
```

**Examples:**
```
/plugin:update team/tools
/plugin:update community/plugins --version v2.0.0
/plugin:update personal/experiments --dry-run
```

**Features:**
- Version-specific updates (tags, branches, commits)
- Automatic backup creation
- Rollback on failure
- Preview changes before applying

#### `/plugin:remove`

Remove a plugin and optionally its repository.

**Syntax:**
```
/plugin:remove <plugin-name> --repo <owner/repo> [--keep-files] [--dry-run]
```

**Examples:**
```
/plugin:remove old-tool --repo team/deprecated
/plugin:remove test-plugin --repo personal/experiments --keep-files
```

#### `/plugin:convert`

Convert existing Claude Code extensions to plugin format.

**Syntax:**
```
/plugin:convert <extension-path> [--name <name>] [--repo <repo-url>] [--batch]
```

**Examples:**
```
/plugin:convert ~/my-project
/plugin:convert ~/extensions --name my-tools --repo https://github.com/me/tools.git
/plugin:convert ~/large-project --batch
```

**Features:**
- Automatic plugin structure generation
- Metadata inference from existing extensions
- Direct push to Git repositories
- Batch conversion for multiple extensions

#### `/plugin:sync`

Synchronize plugins according to team configuration.

**Syntax:**
```
/plugin:sync [--environment <env>] [--dry-run] [--force]
```

**Examples:**
```
/plugin:sync
/plugin:sync --environment development
/plugin:sync --dry-run
```

**Features:**
- Reads pacc.json for team requirements
- Installs missing plugins
- Updates existing plugins to specified versions
- Environment-specific configurations

### Environment Management Commands

#### `/env:setup`

Configure environment for plugin support.

**Syntax:**
```
/env:setup [--shell <shell>] [--global] [--force]
```

**Examples:**
```
/env:setup
/env:setup --shell zsh
/env:setup --global --force
```

**Features:**
- Automatic ENABLE_PLUGINS=1 configuration
- Shell profile detection and updates
- Cross-platform support (Windows/macOS/Linux)
- Verification of configuration

#### `/env:check`

Verify environment configuration for plugins.

**Syntax:**
```
/env:check [--verbose] [--debug]
```

**Examples:**
```
/env:check
/env:check --verbose
/env:check --debug
```

**Verification includes:**
- ENABLE_PLUGINS environment variable
- Shell profile configuration
- Plugin directory structure
- Claude Code plugin support

### `/pacc:list`

List all installed Claude Code extensions.

**Syntax:**
```
/pacc:list [type] [--user|--project|--all] [--filter <pattern>] [--search <query>]
```

**Examples:**
```
/pacc:list
/pacc:list hooks --user
/pacc:list --search "git"
/pacc:list --filter "*.test"
```

### `/pacc:search`

Search for extensions by name or description.

**Syntax:**
```
/pacc:search <query> [--type <type>]
```

**Examples:**
```
/pacc:search "python"
/pacc:search "formatter" --type hooks
```

### `/pacc:info`

Get detailed information about an extension.

**Syntax:**
```
/pacc:info <extension-name-or-path> [--show-related] [--show-usage]
```

**Examples:**
```
/pacc:info my-hook
/pacc:info ./path/to/extension.json --show-usage
```

### `/pacc:update`

Update an installed extension to the latest version.

**Syntax:**
```
/pacc:update <extension-name-or-source> [--force]
```

**Examples:**
```
/pacc:update my-extension
/pacc:update https://github.com/user/extension.git --force
```

### `/pacc:remove`

Remove an installed extension.

**Syntax:**
```
/pacc:remove <extension-name> [--type <type>] [--user|--project] [--force]
```

**Examples:**
```
/pacc:remove old-extension
/pacc:remove test-hook --type hooks --user
```

## Features

### JSON Output Mode

All PACC slash commands use JSON output mode for structured responses that Claude Code can parse and present beautifully. This ensures:
- Clear success/failure indicators
- Detailed error messages
- Progress tracking for long operations
- Structured data for Claude to format

### Interactive Feedback

Claude Code provides interactive feedback for all operations:
- ✅ Success confirmations
- ❌ Error explanations
- 📊 Progress updates
- 💡 Helpful suggestions

### Safety Features

PACC slash commands include built-in safety:
- Confirmation prompts for destructive operations
- Automatic backups before modifications
- Validation of all extensions before installation
- Clear warnings for potential issues

## Integration with Claude Code

### Permissions

PACC slash commands require appropriate permissions in Claude Code:
- `Bash` tool permission for executing PACC CLI
- `Read` tool permission for file operations
- File system access for installation/removal

### Workflow Integration

PACC slash commands integrate seamlessly with Claude Code workflows:

1. **Discovery**: Use `/pacc:search` to find extensions
2. **Information**: Use `/pacc:info` to learn about extensions
3. **Installation**: Use `/pacc:install` to add extensions
4. **Management**: Use `/pacc:list` and `/pacc:remove` to manage
5. **Updates**: Use `/pacc:update` to keep extensions current

### Error Handling

When errors occur, PACC slash commands provide:
- Clear error messages
- Suggested fixes
- Rollback information
- Next steps to resolve issues

## Best Practices

1. **Always review before installing**: Use `/pacc:info` to understand what an extension does
2. **Use appropriate scope**: Install user-level for personal use, project-level for team sharing
3. **Regular updates**: Periodically run `/pacc:update` to get latest features and fixes
4. **Clean installations**: Remove unused extensions with `/pacc:remove` to keep your setup clean

## Technical Details

### Command Structure

Each PACC slash command is implemented as a Markdown file with:
- **Frontmatter**: Metadata including tools, arguments, and description
- **Bash execution**: Calls to PACC CLI with JSON output
- **Result formatting**: Claude-friendly presentation of results

### JSON Communication

PACC CLI provides `--json` flag for all commands, returning:
```json
{
  "success": true,
  "message": "Operation completed",
  "data": {
    // Command-specific data
  },
  "errors": [],
  "warnings": []
}
```

### Extension Types

PACC supports four extension types:
- **hooks**: Event-driven automation scripts
- **mcps**: MCP (Model Context Protocol) servers
- **agents**: Custom AI subagents
- **commands**: Additional slash commands

## Troubleshooting

### Command not found

If `/pacc:` commands aren't available:
1. Ensure `.claude/commands/pacc/` directory exists
2. Verify command files have `.md` extension
3. Restart Claude Code session

### Permission errors

If commands fail with permission errors:
1. Check Claude Code tool permissions
2. Ensure PACC CLI is installed and accessible
3. Verify file system permissions

### Installation failures

If installations fail:
1. Use `/pacc:info` to validate the extension first
2. Check network connectivity for URLs
3. Ensure sufficient disk space
4. Review error messages for specific issues

## See Also

- [PACC CLI Documentation](../README.md)
- [Claude Code Slash Commands](https://docs.anthropic.com/claude-code/slash-commands)
- Extension Development Guide (coming soon)