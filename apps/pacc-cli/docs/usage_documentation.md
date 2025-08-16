# PACC CLI Usage Documentation

This guide covers the complete usage of PACC CLI as a globally installed command-line tool for managing Claude Code extensions.

## Table of Contents

- [Overview](#overview)
- [Command Structure](#command-structure)
- [Global vs Project Scope](#global-vs-project-scope)
- [Core Commands](#core-commands)
  - [install](#install-command)
  - [validate](#validate-command)
  - [list](#list-command)
  - [remove](#remove-command)
  - [info](#info-command)
- [Command Options](#command-options)
- [Working with Different Extension Types](#working-with-different-extension-types)
- [Advanced Usage](#advanced-usage)
- [Configuration](#configuration)
- [Best Practices](#best-practices)

## Overview

PACC CLI is a package manager for Claude Code extensions, supporting:
- **Hooks**: Event-driven automation scripts
- **MCP Servers**: Model Context Protocol servers
- **Agents**: AI-powered assistants with tool access
- **Commands**: Slash commands for Claude Code

### Key Features

- **Dual Scope**: Install extensions globally (user-level) or per-project
- **Type Detection**: Automatically identifies extension types
- **Safe Operations**: Validates before modifying configurations
- **Interactive Mode**: Select specific extensions from multi-item sources
- **Dry Run**: Preview changes without applying them

## Command Structure

PACC follows a consistent command structure:

```bash
pacc <command> <source> [options]
```

- **command**: The action to perform (install, validate, list, etc.)
- **source**: File path, directory, or extension name
- **options**: Flags to modify behavior (--user, --project, --force, etc.)

### Getting Help

```bash
# General help
pacc --help
pacc -h

# Command-specific help
pacc install --help
pacc validate --help

# Version information
pacc --version
pacc -V
```

## Global vs Project Scope

PACC can install extensions at two levels:

### User-Level (Global)

- **Location**: `~/.claude/` directory
- **Scope**: Available across all projects
- **Use Case**: Personal tools, common utilities
- **Command**: `pacc install <source> --user`

### Project-Level

- **Location**: `.claude/` in project root
- **Scope**: Specific to current project
- **Use Case**: Project-specific tools, team configurations
- **Command**: `pacc install <source> --project`

### Default Behavior

```bash
# Default to project scope when in a project directory
cd my-project
pacc install ./hook.json  # Installs to .claude/

# Default to user scope when not in a project
cd ~
pacc install ./hook.json  # Installs to ~/.claude/

# Override with explicit flags
pacc install ./hook.json --user    # Always user-level
pacc install ./hook.json --project  # Always project-level
```

## Core Commands

### install Command

Installs Claude Code extensions from various sources.

```bash
# Basic installation
pacc install ./my-extension.json

# User-level installation
pacc install ./my-extension.json --user

# Project-level installation
pacc install ./my-extension.json --project

# Force overwrite existing
pacc install ./my-extension.json --force

# Preview without installing
pacc install ./my-extension.json --dry-run

# Interactive selection from directory
pacc install ./extensions/ --interactive

# Install all from directory
pacc install ./extensions/ --all
```

#### Installation Examples

```bash
# Install a single hook
pacc install ./format-hook.json --project

# Install MCP server globally
pacc install ./calculator-mcp/ --user

# Install multiple agents interactively
pacc install ./team-agents/ --interactive
# Shows: 
# [1] code-reviewer - Reviews code for best practices
# [2] test-writer - Generates unit tests
# [3] doc-generator - Creates documentation
# Select (e.g., 1,3 or all): 1,2

# Install command with validation
pacc install ./commands/deploy.md --dry-run
```

#### Extension Type Behaviors

Different extension types have different installation behaviors:

**Configuration-based extensions** (modify settings.json):
- **Hooks**: Require configuration entries for events and matchers
- **MCP Servers**: Require configuration for server commands and arguments

**File-based extensions** (no settings.json modification):
- **Agents**: Placed in `.claude/agents/` directory, auto-discovered by Claude Code
- **Commands**: Placed in `.claude/commands/` directory, auto-discovered by Claude Code

```bash
# Hook installation (updates settings.json)
$ pacc install ./my-hook.json --project
✓ Installed: my-hook (hooks)
✓ Updated .claude/settings.json

# Agent installation (file-based only)
$ pacc install ./my-agent.md --project
✓ Installed: my-agent (agents)
# Note: No settings.json update needed
```

### validate Command

Validates extensions without installing them.

```bash
# Auto-detect type and validate
pacc validate ./extension.json

# Validate with specific type
pacc validate ./extension.json --type hooks

# Strict validation (more thorough)
pacc validate ./extension.json --strict

# Validate entire directory
pacc validate ./extensions/

# Validate with detailed output
pacc validate ./extension.json -v
```

#### Validation Examples

```bash
# Validate hook structure
pacc validate ./pre-commit.json --type hooks
# ✓ Valid hook configuration
# ✓ Event types: PreToolUse
# ✓ Commands validated

# Validate MCP server
pacc validate ./weather-mcp/ --type mcp
# ✓ Valid MCP server configuration
# ✓ Executable found: weather-server
# ✓ Environment variables set

# Validate multiple agents
pacc validate ./agents/ --type agents
# ✓ Found 3 valid agents
# ✓ code-reviewer.md: Valid YAML frontmatter
# ✓ test-writer.md: Valid YAML frontmatter
# ✓ doc-generator.md: Valid YAML frontmatter
```

### list Command

Lists installed extensions.

```bash
# List all extensions
pacc list

# List user-level extensions
pacc list --user

# List project-level extensions
pacc list --project

# List specific type
pacc list --type hooks

# List with details
pacc list --detailed

# JSON output for scripting
pacc list --json
```

#### List Output Examples

```bash
$ pacc list
Project Extensions (.claude/):
  Hooks:
    ✓ format-hook - Auto-formats code before tool use
    ✓ test-hook - Runs tests before deployment
  
  Agents:
    ✓ code-reviewer - Reviews code for best practices
  
User Extensions (~/.claude/):
  MCP Servers:
    ✓ calculator - Basic math operations
    ✓ weather - Weather information service
  
  Commands:
    ✓ deploy - Deploy application
    ✓ test - Run test suite
```

### remove Command

Removes installed extensions.

```bash
# Remove by name
pacc remove format-hook

# Remove from specific scope
pacc remove calculator --user
pacc remove test-hook --project

# Remove with confirmation
pacc remove format-hook --confirm

# Force removal without confirmation
pacc remove format-hook --force
```

#### Removal Examples

```bash
# Remove project hook
$ pacc remove format-hook --project
? Remove format-hook from project? (y/N) y
✓ Removed format-hook from .claude/hooks/

# Remove user MCP server
$ pacc remove calculator --user
? Remove calculator MCP server from user config? (y/N) y
✓ Removed calculator from ~/.claude/.mcp.json
✓ Updated settings.json

# Remove agent (file-based, no settings.json update)
$ pacc remove code-reviewer --project
? Remove code-reviewer agent from project? (y/N) y
✓ Removed code-reviewer from .claude/agents/
```

### info Command

Shows detailed information about extensions.

```bash
# Show info for installed extension
pacc info format-hook

# Show info with specific scope
pacc info calculator --user

# Show info for file (not installed)
pacc info ./new-extension.json

# JSON output
pacc info format-hook --json
```

#### Info Output Example

```bash
$ pacc info format-hook
Extension: format-hook
Type: Hook
Scope: Project (.claude/)
Description: Auto-formats code before tool use

Event Types:
  - PreToolUse

Commands:
  - prettier --write {file}
  - eslint --fix {file}

Installation Date: 2024-12-15
Version: 1.0.0
Source: local file
```

## Command Options

### Global Options

Available for all commands:

```bash
-h, --help          Show help message
-V, --version       Show version number
-v, --verbose       Verbose output
-q, --quiet         Suppress non-error output
--no-color          Disable colored output
--config <file>     Use specific config file
```

### Scope Options

Control installation location:

```bash
--user              Install/operate at user level (~/.claude/)
--project           Install/operate at project level (.claude/)
--global            Alias for --user
--local             Alias for --project
```

### Installation Options

For `install` command:

```bash
--force             Overwrite existing extensions
--dry-run           Preview changes without applying
--interactive, -i   Interactive selection mode
--all               Install all items (skip selection)
--backup            Create backup before changes
--no-backup         Skip backup creation
```

### Validation Options

For `validate` command:

```bash
--type <type>       Specify extension type (hooks|mcp|agents|commands)
--strict            Enable strict validation
--fix               Attempt to fix issues (where possible)
```

### Output Options

Control output format:

```bash
--json              JSON output format
--yaml              YAML output format
--table             Table format (default for list)
--format <fmt>      Custom format string
```

## Working with Different Extension Types

### Hooks

Hooks are event-driven scripts that run on Claude Code events.

```bash
# Create a hook file
cat > format-hook.json << 'EOF'
{
  "name": "format-hook",
  "eventTypes": ["PreToolUse"],
  "commands": ["prettier --write {file}"],
  "description": "Format code before use"
}
EOF

# Validate and install
pacc validate format-hook.json --type hooks
pacc install format-hook.json --project

# List installed hooks
pacc list --type hooks
```

### MCP Servers

Model Context Protocol servers provide additional capabilities.

```bash
# Install from directory
pacc install ./calculator-mcp/ --user

# Validate server configuration
pacc validate ./calculator-mcp/.mcp.json --type mcp

# Check server status
pacc info calculator --user
```

### Agents

AI assistants with specialized capabilities.

```bash
# Install multiple agents
pacc install ./agents/ --interactive

# Validate agent metadata
pacc validate ./agents/code-reviewer.md --type agents

# List available agents
pacc list --type agents --detailed
```

### Commands

Slash commands for Claude Code.

```bash
# Install command
pacc install ./commands/deploy.md --project

# Validate command syntax
pacc validate ./commands/ --type commands

# View command info
pacc info deploy
```

## Advanced Usage

### Batch Operations

```bash
# Install multiple extensions
for file in ./extensions/*.json; do
  pacc install "$file" --project
done

# Validate all extensions in a directory
pacc validate ./extensions/ --strict

# Remove multiple extensions
pacc remove hook1 hook2 hook3 --force
```

### Scripting with PACC

```bash
#!/bin/bash
# Script to setup development environment

# Install required extensions
extensions=(
  "./hooks/format-hook.json"
  "./hooks/test-hook.json"
  "./agents/code-reviewer.md"
)

for ext in "${extensions[@]}"; do
  if pacc validate "$ext"; then
    pacc install "$ext" --project
  else
    echo "Skipping invalid extension: $ext"
  fi
done

# List installed
pacc list --json > installed-extensions.json
```

### Environment Variables

```bash
# Set default scope
export PACC_DEFAULT_SCOPE=user

# Set config location
export PACC_CONFIG_DIR=~/.config/pacc

# Enable debug output
export PACC_DEBUG=1

# Disable colors
export NO_COLOR=1
```

### Working with Git

```bash
# Add PACC to project
pacc init --project
echo ".claude/pacc/" >> .gitignore
echo ".claude/settings.local.json" >> .gitignore

# Commit shareable configurations
git add .claude/hooks/
git add .claude/agents/
git add .claude/commands/
git commit -m "Add Claude Code extensions"

# Clone and setup
git clone <repo>
cd <repo>
pacc install  # Reads pacc.json if present
```

## Configuration

### PACC Configuration File

Location: `~/.claude/pacc/config.json` or `.claude/pacc/config.json`

```json
{
  "defaultScope": "project",
  "autoBackup": true,
  "colorOutput": true,
  "validation": {
    "strict": false,
    "autoFix": false
  },
  "sources": {
    "trusted": ["https://github.com/org/extensions"]
  }
}
```

### Setting Defaults

```bash
# Set default scope
pacc config set defaultScope user

# Enable strict validation
pacc config set validation.strict true

# Add trusted source
pacc config add sources.trusted https://example.com/extensions
```

### Project Configuration

Create `pacc.json` in project root:

```json
{
  "name": "my-project",
  "extensions": {
    "hooks": ["format-hook", "test-hook"],
    "agents": ["code-reviewer"],
    "commands": ["deploy", "test"]
  },
  "requirements": {
    "pacc": ">=1.0.0"
  }
}
```

## Best Practices

### 1. Scope Selection

- **User-level**: Personal tools, utilities used across projects
- **Project-level**: Project-specific tools, team configurations

```bash
# Personal formatting preferences
pacc install ./my-format-hook.json --user

# Project-specific deployment
pacc install ./deploy-command.md --project
```

### 2. Version Control

```bash
# Track project extensions
git add .claude/hooks/ .claude/agents/ .claude/commands/

# Ignore local configurations
echo ".claude/pacc/" >> .gitignore
echo ".claude/settings.local.json" >> .gitignore
```

### 3. Validation First

Always validate before installing:

```bash
# Validate then install
pacc validate ./extension.json && pacc install ./extension.json
```

### 4. Use Dry Run

Preview changes before applying:

```bash
# Check what will be modified
pacc install ./extensions/ --dry-run
```

### 5. Regular Maintenance

```bash
# List all extensions
pacc list --all

# Check for issues
pacc validate --all --strict

# Clean up unused
pacc remove unused-extension --force
```

### 6. Team Workflows

```bash
# Create team configuration
cat > pacc.json << 'EOF'
{
  "name": "team-project",
  "extensions": {
    "hooks": ["lint-hook", "test-hook"],
    "agents": ["pr-reviewer", "doc-writer"]
  }
}
EOF

# Team members run
pacc install  # Installs all configured extensions
```

### 7. Security Considerations

- Always validate extensions from unknown sources
- Review commands and permissions before installing
- Use `--dry-run` to preview changes
- Keep backups of working configurations

```bash
# Validate unknown extension
pacc validate ./unknown-extension.json --strict

# Preview installation
pacc install ./unknown-extension.json --dry-run

# Install with backup
pacc install ./unknown-extension.json --backup
```

## Troubleshooting

### Common Issues

**Extension Not Found**:
```bash
# Check installation location
pacc list --all
# Verify scope
pacc info extension-name --user
pacc info extension-name --project
```

**Permission Errors**:
```bash
# Use appropriate scope
pacc install ./extension.json --user  # No admin needed
```

**Validation Failures**:
```bash
# Get detailed error information
pacc validate ./extension.json -v
# Try strict mode for more checks
pacc validate ./extension.json --strict
```

**Conflicts**:
```bash
# Force overwrite
pacc install ./extension.json --force
# Or remove first
pacc remove conflicting-extension
pacc install ./extension.json
```

## Next Steps

- Read the [Getting Started Guide](getting_started_guide.md) for tutorials
- See [Migration Guide](migration_guide.md) for moving from local to global
- Review [API Reference](api_reference.md) for detailed command documentation
- Check Extension Development guide to create your own (coming soon)

---

**Version**: 1.0.0 | **Last Updated**: December 2024