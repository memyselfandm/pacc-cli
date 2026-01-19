# Memory Fragments User Guide

Memory fragments are reusable context snippets that provide Claude Code with project-specific instructions, workflows, and guidelines. PACC manages fragments by storing them in organized locations and automatically updating your `CLAUDE.md` file with references.

## Overview

Fragments solve the problem of providing Claude with consistent, reusable context across sessions. Instead of repeating instructions, you can install fragments that are automatically loaded when Claude starts working on your project.

### Key Features

- **Organized Storage**: Fragments are stored in `.claude/pacc/fragments/` (project) or `~/.claude/pacc/fragments/` (user)
- **Automatic CLAUDE.md Integration**: Installed fragments are automatically referenced in your CLAUDE.md
- **Version Tracking**: Track fragment sources for easy updates
- **Team Synchronization**: Share fragments via `pacc.json` project configuration
- **Collection Support**: Organize related fragments into collections

## Quick Start

### Install a Fragment

```bash
# Install from a local file
pacc fragment install ./my-workflow.md

# Install from a Git repository
pacc fragment install https://github.com/user/fragments-repo.git

# Install to user-level (available across all projects)
pacc fragment install ./coding-standards.md --storage-type user

# Preview what would be installed (dry run)
pacc fragment install ./fragment.md --dry-run
```

### List Installed Fragments

```bash
# List all fragments
pacc fragment list

# List with detailed statistics
pacc fragment list --show-stats

# Filter by storage location
pacc fragment list --storage-type project

# Output as JSON
pacc fragment list --format json
```

### View Fragment Details

```bash
# Show fragment information
pacc fragment info my-workflow

# Show with JSON output
pacc fragment info my-workflow --format json
```

### Remove a Fragment

```bash
# Remove a fragment (will prompt for confirmation)
pacc fragment remove my-workflow

# Remove without confirmation
pacc fragment remove my-workflow --confirm

# Preview removal (dry run)
pacc fragment remove my-workflow --dry-run
```

### Update Fragments

```bash
# Check for updates
pacc fragment update --check

# Update all fragments
pacc fragment update

# Update specific fragments
pacc fragment update my-workflow coding-standards

# Force update (overwrite local changes)
pacc fragment update --force
```

## Fragment Format

Fragments are Markdown files with optional YAML frontmatter for metadata:

```markdown
---
title: "My Workflow Guide"
description: "Guidelines for working on this project"
tags: ["workflow", "guidelines"]
category: "development"
author: "Team Name"
version: "1.0.0"
---

# My Workflow Guide

Your fragment content goes here. This content will be available
to Claude Code when working on your project.

## Section 1

Instructions, guidelines, or context...

## Section 2

More content...
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `title` | No | Human-readable title for the fragment |
| `description` | No | Brief description of the fragment's purpose |
| `tags` | No | List of tags for categorization |
| `category` | No | Category for organization |
| `author` | No | Author or team name |
| `version` | No | Version string for tracking |

If no frontmatter is provided, PACC will use the filename as the fragment identifier.

## Storage Locations

### Project-Level Storage

Project fragments are stored in `.claude/pacc/fragments/` within your project directory. These fragments are:
- Specific to the current project
- Tracked in version control (if desired)
- Referenced in the project's `CLAUDE.md`

```bash
pacc fragment install ./fragment.md --storage-type project
```

### User-Level Storage

User fragments are stored in `~/.claude/pacc/fragments/` and are:
- Available across all projects
- Personal to the current user
- Referenced in `~/.claude/CLAUDE.md`

```bash
pacc fragment install ./fragment.md --storage-type user
```

## Collections

Collections allow you to organize related fragments into subdirectories:

```bash
# Install to a collection
pacc fragment install ./api-guide.md --collection api-docs

# List fragments in a collection
pacc fragment list --collection api-docs

# Remove from a collection
pacc fragment remove api-guide --collection api-docs
```

### Collection Commands

```bash
# Install an entire collection from a repository
pacc fragment collection install https://github.com/user/fragment-collection.git

# Update a collection
pacc fragment collection update my-collection

# Check collection status
pacc fragment collection status my-collection

# Remove a collection
pacc fragment collection remove my-collection
```

## CLAUDE.md Integration

When you install a fragment, PACC automatically updates your `CLAUDE.md` file with a reference:

```markdown
<!-- PACC:fragments:START -->
@.claude/pacc/fragments/my-workflow.md - My Workflow Guide
@.claude/pacc/fragments/coding-standards.md - Coding Standards
<!-- PACC:fragments:END -->
```

The markers (`PACC:fragments:START` and `PACC:fragments:END`) define a managed section that PACC updates automatically. Content outside this section is preserved.

## Team Synchronization

Share fragments with your team using `pacc.json`:

```json
{
  "fragments": {
    "coding-standards": {
      "source": "https://github.com/team/fragments.git",
      "path": "coding-standards.md",
      "version": "1.0.0"
    },
    "api-guide": {
      "source": "https://github.com/team/fragments.git",
      "path": "api-guide.md"
    }
  }
}
```

Then team members can sync fragments:

```bash
# Sync fragments from pacc.json
pacc fragment sync

# Check sync status
pacc fragment sync --check
```

## Discovering Fragments

Find fragments in repositories:

```bash
# Discover fragments in a Git repository
pacc fragment discover https://github.com/user/repo.git

# Discover in a local directory
pacc fragment discover ./my-fragments/
```

## Command Reference

| Command | Description |
|---------|-------------|
| `pacc fragment install <source>` | Install fragments from file, directory, or URL |
| `pacc fragment list` | List installed fragments |
| `pacc fragment info <name>` | Show fragment details |
| `pacc fragment remove <name>` | Remove a fragment |
| `pacc fragment update [names...]` | Update installed fragments |
| `pacc fragment sync` | Sync fragments from pacc.json |
| `pacc fragment discover <source>` | Discover fragments in a source |
| `pacc fragment collection install <source>` | Install a fragment collection |
| `pacc fragment collection update <name>` | Update a collection |
| `pacc fragment collection status <name>` | Check collection status |
| `pacc fragment collection remove <name>` | Remove a collection |

### Common Options

| Option | Short | Description |
|--------|-------|-------------|
| `--storage-type` | `-s` | Storage location: `project` or `user` |
| `--collection` | `-c` | Collection name for organization |
| `--dry-run` | `-n` | Preview changes without applying |
| `--verbose` | `-v` | Enable detailed output |
| `--format` | | Output format: `table`, `list`, or `json` |

## Security

PACC includes robust security measures for fragment management:

- **Path Traversal Protection**: Fragment names cannot contain path separators or traversal sequences
- **Boundary Validation**: All operations are restricted to designated storage directories
- **Input Sanitization**: All user input is validated before file operations

For more details, see the [Security Guide](security_guide.md).

## Troubleshooting

### Fragment not appearing in CLAUDE.md

Ensure you're using `pacc fragment install` (not copying files manually). The installation process updates CLAUDE.md automatically.

### Permission denied errors

Check that you have write access to:
- `.claude/pacc/fragments/` (project storage)
- `~/.claude/pacc/fragments/` (user storage)
- The `CLAUDE.md` file being updated

### Fragment updates not working

Fragments installed from Git repositories track their source. Local file installations cannot be auto-updated. Reinstall with the `--overwrite` flag if needed.

### Collection not found

Verify the collection exists:
```bash
pacc fragment list --collection my-collection
```

If empty, the collection may not have been created. Install fragments with the `--collection` flag to create it.
