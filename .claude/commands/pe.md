---
name: pe
description: Quick alias for plugin enable
argument-hint: <plugin_name> [--repo REPO]
allowed-tools: Bash(pacc:*)
---

# Plugin Enable (Quick Alias)

Quick alias for `/plugin enable` - enables a Claude Code plugin.

## Usage

!`if [ -n "$ARGUMENTS" ]; then pacc plugin enable $ARGUMENTS; else echo "Please specify plugin name (format: repo/plugin) or use --repo option"; pacc plugin list --disabled; fi`
