---
name: pd
description: Quick alias for plugin disable
argument-hint: <plugin_name> [--repo REPO]
allowed-tools: Bash(pacc:*)
---

# Plugin Disable (Quick Alias)

Quick alias for `/plugin disable` - disables a Claude Code plugin.

## Usage

!`if [ -n "$ARGUMENTS" ]; then pacc plugin disable $ARGUMENTS; else echo "Please specify plugin name (format: repo/plugin) or use --repo option"; pacc plugin list --enabled; fi`
