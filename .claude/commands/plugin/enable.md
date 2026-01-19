---
name: plugin-enable
description: Enable a specific Claude Code plugin
argument-hint: <plugin_name> [--repo REPO]
allowed-tools: Bash(pacc:*)
---

# Enable Plugin

This command enables a Claude Code plugin by adding it to the enabledPlugins section in your settings.json.

## Arguments
- **plugin_name**: Plugin to enable (format: repo/plugin or just plugin name)
- **--repo REPO**: Repository containing the plugin (owner/repo format)

## Usage

!`if [ -n "$ARGUMENTS" ]; then pacc plugin enable $ARGUMENTS; else echo "Please specify plugin name (format: repo/plugin) or use --repo option"; pacc plugin list --disabled; fi`
