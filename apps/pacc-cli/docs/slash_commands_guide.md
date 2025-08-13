# PACC Slash Commands Guide

This guide explains how to use PACC slash commands within Claude Code for seamless extension management.

## Overview

PACC provides native Claude Code integration through slash commands, allowing you to manage extensions directly within your coding session without switching to the terminal.

## Available Commands

All PACC commands are namespaced under `/pacc:` to avoid conflicts with other tools.

### `/pacc:install`

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
- [Extension Development Guide](./extension_development.md)