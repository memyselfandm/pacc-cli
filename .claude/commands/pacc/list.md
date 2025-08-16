---
allowed-tools: Bash(python:*), Bash(uv:*), Read
argument-hint: [type] [--user|--project|--all] [--filter <pattern>] [--search <query>]
description: List installed Claude Code extensions
---

## Listing Installed Extensions

I'll show you all installed Claude Code extensions.

### 📦 Fetching extension list...

!`cd /Users/m/ai-workspace/pacc/pacc-dev/apps/pacc-cli && python -m pacc list $ARGUMENTS --format json 2>&1`

Let me present the installed extensions in an organized format:

Based on the results, I'll show you:
- 📋 A summary of all installed extensions
- 🏷️ Extension types (hooks, MCP servers, agents, commands)
- 📍 Installation scope (user-level or project-level)
- 📝 Descriptions and metadata for each extension

You can use any of these extensions in your Claude Code session!