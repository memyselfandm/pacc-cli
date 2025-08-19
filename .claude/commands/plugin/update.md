---
name: plugin-update
description: Update Claude Code plugins from Git repositories
argument-hint: [plugin_name] [--show-diff] [--force] [--dry-run]
allowed-tools: Bash(pacc:*)
---

# Update Plugin

This command updates Claude Code plugins by pulling the latest changes from their Git repositories.

## Arguments
- **plugin_name**: Specific plugin to update (owner/repo format), or leave empty to update all
- **--show-diff**: Show diff before updating
- **--force**: Force update even if there are conflicts
- **--dry-run**: Show what would be updated without making changes

## Usage

!`pacc plugin update $ARGUMENTS`