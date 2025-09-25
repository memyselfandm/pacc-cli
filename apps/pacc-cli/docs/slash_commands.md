# PACC Slash Commands Integration

This document describes the PACC slash commands integration for Claude Code, providing native extension management capabilities within coding sessions.

## Overview

PACC slash commands allow users to manage Claude Code extensions seamlessly without leaving their interactive Claude Code session. The implementation provides a complete set of namespaced commands under the `/pacc:*` namespace.

## Architecture

### Command Structure

```
.claude/commands/pacc/
├── pacc.md              # Main help command (/pacc)
├── install.md           # Installation command (/pacc:install)
├── list.md             # List extensions (/pacc:list)
├── info.md             # Extension information (/pacc:info)
├── remove.md           # Remove extensions (/pacc:remove)
├── search.md           # Search extensions (/pacc:search)
└── update.md           # Update extensions (/pacc:update)
```

### Integration Points

1. **CLI JSON Output**: All PACC CLI commands support structured JSON output for programmatic consumption
2. **Bash Tool Integration**: Slash commands use Claude Code's Bash tools to execute PACC CLI commands
3. **Argument Passing**: User arguments are passed through the `$ARGUMENTS` placeholder
4. **Result Processing**: JSON responses are parsed and formatted for user-friendly display

## Available Commands

### Core Commands

#### `/pacc:install <source> [options]`
Install Claude Code extensions from various sources.

**Sources Supported:**
- Local files/directories: `/pacc:install ./my-hook.json`
- HTTP URLs: `/pacc:install https://example.com/extension.zip`
- Git repositories: `/pacc:install https://github.com/user/extensions.git`

**Key Options:**
- `--type TYPE`: Specify extension type (hooks, mcps, agents, commands)
- `--user`: Install to user directory (`~/.claude/`)
- `--project`: Install to project directory (`./.claude/`) [default]
- `--force`: Overwrite existing extensions
- `--dry-run`: Preview installation without changes
- `--interactive`: Select specific extensions from multi-extension sources

#### `/pacc:list [type] [options]`
List installed extensions with filtering capabilities.

**Usage Examples:**
- `/pacc:list`: Show all extensions
- `/pacc:list hooks`: Show only hook extensions
- `/pacc:list --user`: Show user-level extensions only
- `/pacc:list --filter "git-*"`: Filter by name pattern
- `/pacc:list --search "database"`: Search in descriptions

#### `/pacc:info <name-or-path> [options]`
Display detailed extension information.

**Features:**
- Extension metadata and validation status
- Type-specific configuration details
- Usage examples and troubleshooting
- File information and installation details

**Options:**
- `--show-related`: Display related extensions
- `--show-usage`: Include usage examples
- `--show-troubleshooting`: Add troubleshooting guidance

#### `/pacc:remove <name> [options]`
Safely remove extensions with dependency checking.

**Safety Features:**
- Dependency validation before removal
- Atomic operations with rollback
- Confirmation prompts (skippable with `--confirm`)
- Backup creation before changes

### Discovery Commands

#### `/pacc:search <query> [options]`
Search for extensions (currently searches installed extensions).

**Current Functionality:**
- Search installed extensions by name/description
- Filter by extension type
- Preparation for future package registry integration

#### `/pacc:update [name] [options]`
Update extensions (currently provides manual workflows).

**Current Functionality:**
- Version checking guidance
- Update workflow instructions
- Preparation for automatic version management

### Main Help Command

#### `/pacc [subcommand]`
Comprehensive help and command overview.

**Features:**
- Overview of all PACC commands
- Extension type descriptions
- Installation scope explanations
- Quick start examples

## Implementation Details

### JSON Output Support

All CLI commands support structured JSON output:

```bash
# Direct CLI usage
uv run pacc list --format json
uv run pacc install source --json
uv run pacc info extension --json

# Slash command integration
!`uv run pacc list --format json`
!`uv run pacc install $ARGUMENTS --json`
```

### Command Result Structure

```json
{
  "success": true|false,
  "message": "Human readable message",
  "data": {
    "command_specific_data": "..."
  },
  "errors": ["error messages"],
  "warnings": ["warning messages"],
  "messages": [
    {"level": "info|success|warning|error", "message": "..."}
  ]
}
```

### Frontmatter Specification

Each slash command file includes standardized frontmatter:

```markdown
---
allowed-tools: Bash(uv run pacc command:*), Bash(cd *), Bash(pwd:*)
argument-hint: <source> [--option VALUE]
description: Brief command description
model: claude-3-5-sonnet-20241022
---
```

**Fields:**
- `allowed-tools`: Bash tools needed for command execution
- `argument-hint`: Argument syntax shown in Claude Code autocomplete
- `description`: Brief description for command listing
- `model`: Preferred model for command execution

### Security Considerations

1. **Tool Restrictions**: Commands are limited to specific Bash tool patterns
2. **Argument Validation**: All arguments are passed through PACC's validation system
3. **Path Safety**: File operations use PACC's secure path handling
4. **Atomic Operations**: All installation/removal operations are atomic with rollback

## Testing

### Test Coverage

The implementation includes comprehensive testing:

- **Unit Tests**: Individual component testing (18 tests)
- **Integration Tests**: End-to-end workflow testing
- **JSON Output Tests**: Structured output validation
- **File Structure Tests**: Command file validation
- **Error Handling Tests**: Graceful failure scenarios

### Running Tests

```bash
# Quick integration test
python test_slash_commands.py

# Comprehensive test suite
python -m pytest tests/test_slash_commands.py -v

# All PACC tests
make test
```

## Usage Examples

### Installing Extensions

```
# Install from GitHub repository
/pacc:install https://github.com/user/claude-extensions.git

# Install specific hook from local file
/pacc:install ./automation/git-hook.json --type hooks

# Interactive installation with preview
/pacc:install https://example.com/extensions.zip --interactive --dry-run
```

### Managing Extensions

```
# List all extensions with details
/pacc:list --all --format table

# Find database-related MCP servers
/pacc:search database --type mcps

# Get detailed extension information
/pacc:info my-extension --show-usage --show-troubleshooting

# Safely remove extension
/pacc:remove old-extension --dry-run
```

### Getting Help

```
# Main PACC overview
/pacc

# Command-specific help
/pacc:install --help
/pacc:list hooks --help
```

## Future Enhancements

### Package Registry Integration

- Central extension registry with thousands of community extensions
- Download counts, ratings, and compatibility information
- One-click installation with dependency resolution
- Automatic security scanning and validation

### Advanced Version Management

- Automatic update checking and installation
- Semantic versioning support with rollback capability
- Changelog display and breaking change warnings
- Batch updates with dependency management

### Enhanced Discovery

- Category-based browsing (Development Tools, Git Integration, etc.)
- Recommendation system based on project type
- Extension compatibility checking
- Community ratings and reviews

## Integration with Claude Code

The slash commands integrate seamlessly with Claude Code's existing features:

- **File References**: Support `@file` syntax in installation sources
- **Extended Thinking**: Commands can trigger extended reasoning when needed
- **Tool Permissions**: Respect Claude Code's tool permission system
- **Session Context**: Maintain context across command invocations
- **Error Handling**: Graceful error recovery with helpful suggestions

This implementation provides a solid foundation for PACC's evolution into a comprehensive extension management system while maintaining the simplicity and safety that Claude Code users expect.
