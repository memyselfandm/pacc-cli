---
allowed-tools: Bash(python:*), Bash(uv:*), Read
argument-hint: <extension-name> [--type <type>] [--user|--project] [--force]
description: Remove an installed extension
---

## Removing Extension

I'll help you remove the specified Claude Code extension.

### 🗑️ Preparing to remove: $ARGUMENTS

First, let me check what will be removed:

!`cd /Users/m/ai-workspace/pacc/pacc-dev/apps/pacc-cli && python -m pacc info $ARGUMENTS --json 2>&1`

Now, removing the extension:

!`cd /Users/m/ai-workspace/pacc/pacc-dev/apps/pacc-cli && python -m pacc remove $ARGUMENTS --confirm --json 2>&1`

Based on the removal results:

- ✅ **Removal Summary**
  - Extension successfully removed
  - Configuration cleaned up
  - Associated files deleted

- 📁 **Cleanup Details**
  - Files that were removed
  - Configuration entries cleared
  - Any remaining artifacts

- 💡 **Next Steps**
  - The extension has been completely removed
  - You can reinstall it later if needed using `/pacc:install`
  - Any dependent extensions may need reconfiguration

The extension has been successfully removed from your Claude Code setup!