---
name: plugin-install
description: Install a Claude Code plugin from Git repository
argument-hint: <repo_url> [--enable] [--all] [--type TYPE] [--interactive]
allowed-tools: Bash(pacc:*)
---

# Install Plugin

This command installs Claude Code plugins from a Git repository using PACC.

## Arguments
- **repo_url**: Git repository URL (e.g., owner/repo or full https://github.com/owner/repo.git)
- **--enable**: Automatically enable installed plugins
- **--all**: Install all plugins found in repository
- **--type TYPE**: Install only plugins of specified type (commands, agents, hooks)
- **--interactive**: Interactively select plugins to install

## Usage

!`if [ -n "$ARGUMENTS" ]; then pacc plugin install $ARGUMENTS; else echo "Please provide a repository URL to install from (e.g., owner/repo)"; fi`
