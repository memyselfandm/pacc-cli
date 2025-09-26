---
name: plugin-sync
description: Synchronize plugins from pacc.json team configuration
argument-hint: [--config FILE] [--dry-run] [--force] [--required-only] [--optional-only]
allowed-tools: Bash(pacc:*)
---

# Plugin Sync

This command synchronizes Claude Code plugins based on team configuration in pacc.json.

## Arguments
- **--config FILE**: Path to pacc.json configuration file (default: ./pacc.json)
- **--dry-run**: Show what would be synced without making changes
- **--force**: Force sync even if there are conflicts
- **--required-only**: Only install required plugins, skip optional ones
- **--optional-only**: Only install optional plugins, skip required ones

## Usage

!`pacc plugin sync $ARGUMENTS`

This will:
1. Read plugin requirements from pacc.json
2. Install missing required plugins
3. Update existing plugins to specified versions
4. Enable plugins as configured
5. Show summary of changes made

Great for keeping your team's plugin environment in sync!
