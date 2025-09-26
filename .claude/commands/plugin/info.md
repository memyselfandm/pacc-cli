---
name: plugin-info
description: Show detailed information about a Claude Code plugin
argument-hint: <plugin_name> [--repo REPO] [--json]
allowed-tools: Bash(pacc:*)
---

# Plugin Info

This command shows detailed information about a specific Claude Code plugin including metadata, components, and status.

## Arguments
- **plugin_name**: Plugin to show info for (format: repo/plugin or just plugin name)
- **--repo REPO**: Repository containing the plugin (owner/repo format)
- **--json**: Output in JSON format

## Usage

!`if [ -n "$ARGUMENTS" ]; then pacc plugin info $ARGUMENTS; else echo "Please specify plugin name (format: repo/plugin) or use --repo option"; pacc plugin list; fi`
