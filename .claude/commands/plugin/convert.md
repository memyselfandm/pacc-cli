---
name: plugin-convert
description: Convert Claude Code extensions to plugin format (interactive wizard)
argument-hint: [extension_name] [--output-dir DIR] [--git-repo URL] [--push]
allowed-tools: Bash(pacc:*)
---

# Convert Extension to Plugin

This command launches an interactive wizard to convert your existing Claude Code extensions (hooks, agents, commands, MCPs) into the new plugin format.

## Arguments
- **extension_name**: Name of extension to convert (optional - will scan if not provided)
- **--output-dir DIR**: Output directory for converted plugins
- **--git-repo URL**: Git repository URL to push converted plugin to
- **--push**: Automatically push to Git repository after conversion

## Usage

!`pacc plugin convert --interactive $ARGUMENTS`

This will:
1. Scan for existing extensions in your .claude directory
2. Let you select which ones to convert  
3. Help you choose plugin name and metadata
4. Convert extensions to plugin format
5. Optionally push to Git repository for sharing