---
name: plugin-list
description: List installed Claude Code plugins with status
argument-hint: [--repo REPO] [--type TYPE] [--enabled] [--disabled] [--json]
allowed-tools: Bash(pacc:*)
---

# List Plugins

This command lists all installed Claude Code plugins and their status.

## Arguments
- **--repo REPO**: Show plugins from specific repository (owner/repo format)
- **--type TYPE**: Show only plugins of specified type (commands, agents, hooks)
- **--enabled**: Show only enabled plugins
- **--disabled**: Show only disabled plugins
- **--json**: Output in JSON format

## Usage

!`pacc plugin list $ARGUMENTS`