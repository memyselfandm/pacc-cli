---
name: plugin-create
description: Create a new Claude Code plugin (interactive wizard)
argument-hint: [plugin_name] [--type TYPE] [--git-repo URL]
allowed-tools: Bash(pacc:*)
---

# Create New Plugin

This command launches an interactive wizard to create a new Claude Code plugin from scratch.

## Arguments
- **plugin_name**: Name for the new plugin (optional - will prompt if not provided)
- **--type TYPE**: Type of plugin to create (commands, agents, hooks, or mixed)
- **--git-repo URL**: Git repository URL to initialize and push to

## Usage

!`echo "Creating new plugin with interactive wizard..."; pacc plugin create --interactive $ARGUMENTS`

The wizard will help you:
1. Choose plugin name and basic metadata (author, description, version)
2. Select what types of components to include (commands, agents, hooks)
3. Generate template files and directory structure
4. Set up Git repository (optional)
5. Create initial commit and push (optional)
