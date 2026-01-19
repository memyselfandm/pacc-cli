---
name: plugin-disable
description: Disable a specific Claude Code plugin
argument-hint: <plugin_name> [--repo REPO]
allowed-tools: Bash(pacc:*)
---

# Disable Plugin

This command disables a Claude Code plugin by removing it from the enabledPlugins section in your settings.json.

## Arguments
- **plugin_name**: Plugin to disable (format: repo/plugin or just plugin name)
- **--repo REPO**: Repository containing the plugin (owner/repo format)

## Usage

!`if [ -n "$ARGUMENTS" ]; then pacc plugin disable $ARGUMENTS; else echo "Please specify plugin name (format: repo/plugin) or use --repo option"; pacc plugin list --enabled; fi`
