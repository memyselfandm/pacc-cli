---
name: pi
description: Quick alias for plugin install
argument-hint: <repo_url> [--enable] [--all] [--type TYPE] [--interactive]
allowed-tools: Bash(pacc:*)
---

# Plugin Install (Quick Alias)

Quick alias for `/plugin install` - installs Claude Code plugins from Git repositories.

## Usage

!`if [ -n "$ARGUMENTS" ]; then pacc plugin install $ARGUMENTS; else echo "Please provide a repository URL to install from (e.g., owner/repo)"; fi`