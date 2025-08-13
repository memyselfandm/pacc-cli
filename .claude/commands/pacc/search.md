---
allowed-tools: Bash(python:*), Bash(uv:*), Read
argument-hint: <query> [--type <type>]
description: Search for Claude Code extensions
---

## Searching for Extensions

I'll search for Claude Code extensions matching your query.

### 🔎 Searching for: $ARGUMENTS

Let me search through installed extensions:

!`cd /Users/m/ai-workspace/pacc/pacc-dev/apps/pacc-cli && python -m pacc list --search "$ARGUMENTS" --format json 2>&1`

Based on the search results, I'll show you:
- 🎯 Extensions matching your search query
- 📄 Descriptions and details for each match
- 💡 Installation status and location
- 🔗 Related extensions you might be interested in

You can install any of these extensions using `/pacc:install <extension-name>`!