---
name: plugin-remove
description: Remove/uninstall a Claude Code plugin
argument-hint: <plugin_name> [--repo REPO] [--delete] [--keep-repo] [--dry-run]
allowed-tools: Bash(pacc:*)
---

# Remove Plugin

This command removes a Claude Code plugin from your enabled plugins and optionally deletes the repository files.

## Arguments
- **plugin_name**: Plugin to remove (format: repo/plugin or just plugin name)
- **--repo REPO**: Repository containing the plugin (owner/repo format)
- **--delete**: Delete repository files completely
- **--keep-repo**: Keep repository files, only disable plugin
- **--dry-run**: Show what would be removed without making changes

## Usage

!`if [ -n "$ARGUMENTS" ]; then pacc plugin remove $ARGUMENTS; else echo "Please specify plugin name (format: repo/plugin) or use --repo option"; pacc plugin list; fi`

The command will:
1. Disable the plugin (remove from enabledPlugins)
2. Optionally delete repository files (if --delete specified)
3. Show confirmation before making changes
