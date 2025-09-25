# PACC Validation Guide

## Overview

The `pacc validate` command provides comprehensive validation of Claude Code extensions without installing them. This guide covers all validation features, use cases, and best practices for ensuring extension quality before deployment.

## Command Syntax

```bash
pacc validate <source> [options]
```

### Parameters

- **`<source>`**: Path to extension file or directory to validate
- **`[options]`**: Optional flags to modify validation behavior

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--type` | `-t` | Specify extension type (`hooks`, `mcp`, `agents`, `commands`) |
| `--strict` | | Enable strict validation (treat warnings as errors) |

## Basic Usage

### Validate Single File

```bash
# Auto-detect extension type and validate
pacc validate ./my-hook.json

# Specify type explicitly
pacc validate ./my-hook.json --type hooks

# Example output:
# ✓ VALID: ./my-hook.json
# Type: hooks
#
# Validation Summary:
#   Valid: 1/1
#   Errors: 0
#   Warnings: 0
```

### Validate Directory

```bash
# Validate all extensions in directory
pacc validate ./extensions/

# Validate specific type in directory
pacc validate ./extensions/ --type commands

# Example output:
# ✓ VALID: ./extensions/deploy.md
# Type: commands
#
# ✓ VALID: ./extensions/build.md
# Type: commands
#
# ✗ INVALID: ./extensions/broken.md
# Type: commands
#
# Errors (2):
#   • MISSING_TITLE: Command file must have a title starting with '#'
#   • INVALID_SYNTAX: Invalid markdown syntax at line 15
#
# Validation Summary:
#   Valid: 2/3
#   Errors: 2
#   Warnings: 0
```

## Extension Type-Specific Validation

### Hooks Validation

```bash
# Validate hook configuration
pacc validate ./pre-commit-hook.json --type hooks

# Common validations:
# - JSON structure correctness
# - Required fields (name, description, hooks)
# - Valid event types (PreToolUse, PostToolUse, etc.)
# - Command safety and security
# - Environment variable usage
```

**Example Hook File:**
```json
{
  "name": "pre-commit-hook",
  "description": "Runs checks before tool execution",
  "hooks": [
    {
      "event": "PreToolUse",
      "command": "npm run lint"
    }
  ]
}
```

### MCP Server Validation

```bash
# Validate MCP server configuration
pacc validate ./mcp-server.json --type mcp

# Common validations:
# - Server configuration structure
# - Executable path verification
# - Environment variables
# - Port and connection settings
# - Security constraints
```

**Example MCP Server File:**
```json
{
  "mcpServers": {
    "database": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-postgres"],
      "env": {
        "DATABASE_URL": "postgresql://localhost/mydb"
      }
    }
  }
}
```

### Agents Validation

```bash
# Validate agent configuration
pacc validate ./my-agent.md --type agents

# Common validations:
# - YAML frontmatter structure
# - Required metadata (name, description)
# - Tool declarations
# - Permission specifications
# - Content format and completeness
```

**Example Agent File:**
```markdown
---
name: file-organizer
description: Organizes files based on content and patterns
tools: ["file-reader", "file-writer"]
permissions: ["read-files", "write-files"]
---

# File Organizer Agent

This agent helps organize files by analyzing their content...
```

### Commands Validation

```bash
# Validate slash command
pacc validate ./deploy-command.md --type commands

# Common validations:
# - Markdown structure
# - Required title format
# - Usage documentation
# - Parameter descriptions
# - Example completeness
```

**Example Command File:**
```markdown
# /deploy

Deploy application to production environment.

## Usage
/deploy <target> [--dry-run]

## Parameters
- `target`: Deployment target (staging, production)
- `--dry-run`: Preview changes without executing

## Examples
/deploy production
/deploy staging --dry-run
```

## Advanced Validation Features

### Strict Mode

Enable strict validation to treat warnings as errors:

```bash
# Strict validation - warnings will cause failure
pacc validate ./extensions/ --strict

# Use case: CI/CD pipelines where high quality is required
# Example in GitHub Actions:
# - name: Validate Extensions
#   run: pacc validate ./src/extensions/ --strict
```

### Type Detection Override

Force validation with specific type when auto-detection fails:

```bash
# Force validation as hooks even if file doesn't match patterns
pacc validate ./custom-automation.json --type hooks

# Useful for:
# - Non-standard file names
# - Custom extension formats
# - Development and testing
```

## Common Validation Scenarios

### Development Workflow

```bash
# 1. Validate during development
pacc validate ./my-extension.json
# Fix any errors reported

# 2. Validate before committing
pacc validate ./src/extensions/ --strict
# Ensure all extensions pass strict validation

# 3. Validate in CI pipeline
pacc validate ./extensions/ --strict
# Automated quality gates
```

### Team Collaboration

```bash
# Validate shared extension repository
git clone https://github.com/team/extensions.git
cd extensions
pacc validate ./ --strict

# Validate specific developer's extensions
pacc validate ./contributors/john/ --type commands

# Validate before merging PR
pacc validate ./src/ --strict
```

### Directory Structure Validation

```bash
# Validate extensions with proper directory structure
my-project/
├── hooks/
│   ├── pre-commit.json     # Auto-detected as hooks
│   └── post-deploy.json    # Auto-detected as hooks
├── commands/
│   ├── deploy.md           # Auto-detected as commands
│   └── build.md            # Auto-detected as commands
└── agents/
    └── helper.md           # Auto-detected as agents

# Validate entire project
pacc validate ./my-project/
```

## Error Handling and Troubleshooting

### Common Error Types

| Error Code | Description | Solution |
|------------|-------------|----------|
| `INVALID_JSON` | Malformed JSON syntax | Use JSON validator to fix syntax |
| `MISSING_FIELD` | Required field missing | Add missing field to configuration |
| `INVALID_EVENT` | Unknown hook event type | Use valid event type (PreToolUse, PostToolUse) |
| `UNSAFE_COMMAND` | Potentially dangerous command | Review command for security issues |
| `FILE_NOT_FOUND` | Referenced file missing | Ensure file exists at specified path |
| `INVALID_MARKDOWN` | Malformed markdown | Fix markdown syntax errors |

### Validation Failures

```bash
# Example validation failure
pacc validate ./broken-hook.json

# Output:
# ✗ INVALID: ./broken-hook.json
# Type: hooks
#
# Errors (3):
#   • INVALID_JSON: Unexpected token at line 15, column 4
#   • MISSING_FIELD: Required field 'description' is missing
#   • UNSAFE_COMMAND: Command 'rm -rf /' contains dangerous operations
#
# Warnings (1):
#   • DEPRECATED_FIELD: Field 'version' is deprecated, use 'schemaVersion'
```

### Debug Information

Use verbose output for detailed information:

```bash
# Enable verbose output (when available)
pacc validate ./extension.json -v

# Check specific validation rules
pacc validate ./extension.json --type hooks
```

## Integration Examples

### GitHub Actions

```yaml
name: Validate Extensions
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install PACC
        run: pip install pacc-cli
      - name: Validate Extensions
        run: pacc validate ./src/extensions/ --strict
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Validating extensions..."
if ! pacc validate ./src/extensions/ --strict; then
    echo "Extension validation failed. Commit aborted."
    exit 1
fi
echo "Extensions validated successfully."
```

### Makefile Integration

```makefile
.PHONY: validate test

validate:
	pacc validate ./src/extensions/ --strict

test: validate
	pytest tests/

ci: validate test
	echo "All checks passed"
```

## Best Practices

### 1. Regular Validation

- Validate extensions during development
- Run validation before committing changes
- Include validation in CI/CD pipelines

### 2. Use Strict Mode in Production

```bash
# Development - allow warnings
pacc validate ./extensions/

# Production/CI - no warnings allowed
pacc validate ./extensions/ --strict
```

### 3. Type-Specific Directories

Organize extensions by type for automatic detection:

```
project/
├── hooks/          # Auto-detected as hooks
├── mcp/           # Auto-detected as mcp
├── agents/        # Auto-detected as agents
└── commands/      # Auto-detected as commands
```

### 4. Validation in Development Workflow

```bash
# Before starting work
pacc validate ./my-extension.json

# After making changes
pacc validate ./my-extension.json --strict

# Before pushing
pacc validate ./src/extensions/ --strict
```

### 5. Team Standards

- Establish validation requirements for your team
- Use strict mode for shared extensions
- Document validation requirements in README
- Include validation in code review process

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All validations passed |
| `1` | Validation errors found |
| `1` | Strict mode enabled and warnings found |

## Related Commands

- [`pacc install`](./usage_documentation.md#install-command) - Install validated extensions
- [`pacc list`](./usage_documentation.md#list-command) - List installed extensions
- [`pacc info`](./usage_documentation.md#info-command) - View extension details

## See Also

- [Extension Type Detection Guide](./extension_detection_guide.md)
- [Folder Structure Configuration](./folder_structure_guide.md)
- [Migration Guide](./migration_guide.md)
- [API Reference](./api_reference.md)
