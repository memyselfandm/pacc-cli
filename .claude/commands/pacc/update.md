---
allowed-tools: Bash(python:*), Bash(uv:*), Read
argument-hint: <extension-name-or-source> [--force]
description: Update an installed extension
---

## Updating Extension

I'll help you update the specified Claude Code extension.

### 🔄 Updating: $ARGUMENTS

First, let me check the current installation:

!`cd /Users/m/ai-workspace/pacc/pacc-dev/apps/pacc-cli && python -m pacc info $ARGUMENTS --json 2>&1`

Now, let me update the extension by reinstalling it:

!`cd /Users/m/ai-workspace/pacc/pacc-dev/apps/pacc-cli && python -m pacc install $ARGUMENTS --force --json 2>&1`

Based on the update results, I'll show you:

- ✅ **Update Status**
  - Whether the update was successful
  - What changed in the new version
  - Any new features or fixes

- 📝 **Configuration Changes**
  - Any settings that were updated
  - New configuration options available
  - Backward compatibility notes

- ⚠️  **Important Notes**
  - Any manual steps required
  - Configuration migrations needed
  - Breaking changes to be aware of

The extension has been updated and is ready to use!