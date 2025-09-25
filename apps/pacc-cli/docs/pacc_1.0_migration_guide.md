# PACC 1.0 Migration Guide

## Overview

PACC 1.0 introduces significant improvements to extension management, validation, and project configuration. This guide helps existing users migrate from pre-1.0 versions to take advantage of new features while maintaining compatibility with existing workflows.

## What's New in PACC 1.0

### Major Features

1. **Enhanced Validation System**
   - Improved validation command with detailed output
   - Strict mode for production environments
   - Better error reporting and suggestions

2. **Folder Structure Configuration**
   - Custom installation directories via `targetDir`
   - Structure preservation with `preserveStructure`
   - Organized extension management

3. **Hierarchical Type Detection**
   - pacc.json declarations take highest priority
   - Directory structure as secondary signal
   - Content keywords as fallback only
   - Fixes slash command misclassification (PACC-18)

4. **Project Configuration (`pacc.json`)**
   - Explicit extension declarations
   - Version locking and dependency management
   - Team collaboration features

### Breaking Changes

1. **Type Detection Hierarchy**
   - pacc.json declarations now override all other detection methods
   - Directory structure has increased importance
   - Content-only detection is now fallback only

2. **Validation Command Improvements**
   - Enhanced output format
   - New `--strict` mode
   - Better error categorization

3. **Configuration File Structure**
   - New `pacc.json` format
   - Extended `ExtensionSpec` with folder options

## Migration Steps

### Step 1: Assessment

First, assess your current PACC installation and extensions:

```bash
# Check current PACC version
pacc --version

# List all installed extensions
pacc list --all

# Check validation status
pacc validate .claude/
```

### Step 2: Backup Current Configuration

Create a backup of your existing configuration:

```bash
# Backup Claude Code directory
cp -r ~/.claude ~/.claude.backup

# For project-level installations
cp -r ./.claude ./.claude.backup
```

### Step 3: Install PACC 1.0

```bash
# Upgrade PACC
pip install --upgrade pacc-cli

# Verify installation
pacc --version  # Should show 1.0.0+
```

### Step 4: Create pacc.json Configuration

Generate a `pacc.json` file for explicit extension management:

```json
{
  "name": "my-project",
  "version": "1.0.0",
  "description": "Migrated from pre-1.0 PACC configuration",
  "extensions": {
    "commands": [
      {
        "name": "deploy",
        "source": ".claude/commands/deploy.md",
        "version": "1.0.0"
      }
    ],
    "hooks": [
      {
        "name": "pre-commit",
        "source": ".claude/hooks/pre-commit.json",
        "version": "1.0.0"
      }
    ],
    "agents": [
      {
        "name": "helper",
        "source": ".claude/agents/helper.md",
        "version": "1.0.0"
      }
    ]
  }
}
```

### Step 5: Validate Migration

```bash
# Validate new configuration
pacc validate ./pacc.json

# Test extension detection
pacc validate .claude/ --strict

# Verify all extensions are recognized
pacc list --all
```

## Specific Migration Scenarios

### Scenario 1: Basic Extension Collection

**Pre-1.0 Structure:**
```
.claude/
├── commands/
│   ├── deploy.md
│   └── build.md
├── hooks/
│   └── pre-commit.json
└── agents/
    └── helper.md
```

**Migration Actions:**
1. Extensions already in correct directories ✅
2. Create `pacc.json` to declare extensions explicitly
3. No file moves required

**New pacc.json:**
```json
{
  "name": "basic-extensions",
  "version": "1.0.0",
  "extensions": {
    "commands": [
      {"name": "deploy", "source": ".claude/commands/deploy.md", "version": "1.0.0"},
      {"name": "build", "source": ".claude/commands/build.md", "version": "1.0.0"}
    ],
    "hooks": [
      {"name": "pre-commit", "source": ".claude/hooks/pre-commit.json", "version": "1.0.0"}
    ],
    "agents": [
      {"name": "helper", "source": ".claude/agents/helper.md", "version": "1.0.0"}
    ]
  }
}
```

### Scenario 2: Mixed Location Extensions

**Pre-1.0 Structure:**
```
project/
├── my-commands/
│   ├── deploy.md      # Command in non-standard location
│   └── build.md       # Command in non-standard location
├── automation/
│   └── hooks.json     # Hook in non-standard location
└── .claude/
    └── agents/
        └── helper.md  # Agent in standard location
```

**Migration Actions:**

**Option A: Move to Standard Locations**
```bash
# Move to standard directories
mkdir -p .claude/commands .claude/hooks
mv my-commands/*.md .claude/commands/
mv automation/hooks.json .claude/hooks/
```

**Option B: Use pacc.json Declarations (Recommended)**
```json
{
  "name": "mixed-location-project",
  "version": "1.0.0",
  "extensions": {
    "commands": [
      {"name": "deploy", "source": "./my-commands/deploy.md", "version": "1.0.0"},
      {"name": "build", "source": "./my-commands/build.md", "version": "1.0.0"}
    ],
    "hooks": [
      {"name": "automation-hooks", "source": "./automation/hooks.json", "version": "1.0.0"}
    ],
    "agents": [
      {"name": "helper", "source": ".claude/agents/helper.md", "version": "1.0.0"}
    ]
  }
}
```

### Scenario 3: Misclassified Extensions (PACC-18 Fix)

**Pre-1.0 Issue:**
Slash commands were sometimes detected as agents due to content keywords.

**File:** `helper.md`
```markdown
---
name: deployment-helper
description: Helps with deployments using tool integration
---

# /deploy

Deploy applications with tool validation and permission checking.
```

**Pre-1.0 Detection:** `agents` (incorrect due to tool/permission keywords)

**Migration Solution:**
```json
{
  "extensions": {
    "commands": [
      {
        "name": "deployment-helper",
        "source": "./helper.md",
        "version": "1.0.0"
      }
    ]
  }
}
```

**1.0 Detection:** `commands` (correct via pacc.json declaration)

### Scenario 4: Custom Organization Migration

Migrate to organized folder structure using new 1.0 features:

**Pre-1.0 Structure:**
```
.claude/
├── commands/
│   ├── frontend-deploy.md
│   ├── backend-deploy.md
│   ├── frontend-build.md
│   └── backend-build.md
```

**1.0 Migration with Custom Organization:**
```json
{
  "name": "organized-project",
  "version": "1.0.0",
  "extensions": {
    "commands": [
      {
        "name": "frontend-tools",
        "source": ".claude/commands/frontend-*.md",
        "version": "1.0.0",
        "targetDir": "frontend",
        "preserveStructure": true
      },
      {
        "name": "backend-tools",
        "source": ".claude/commands/backend-*.md",
        "version": "1.0.0",
        "targetDir": "backend",
        "preserveStructure": true
      }
    ]
  }
}
```

**Result Structure:**
```
.claude/commands/
├── frontend/
│   ├── frontend-deploy.md
│   └── frontend-build.md
└── backend/
    ├── backend-deploy.md
    └── backend-build.md
```

## Configuration Changes

### ExtensionSpec Updates

New fields available in `pacc.json`:

```json
{
  "name": "extension-name",
  "source": "./path/to/extension",
  "version": "1.0.0",
  "description": "Optional description",        // NEW
  "ref": "main",                              // NEW - Git reference
  "environment": "production",                // NEW - Environment restriction
  "dependencies": ["other-extension"],        // NEW - Dependencies
  "metadata": {"key": "value"},              // NEW - Custom metadata
  "targetDir": "custom/path",                 // NEW - Custom installation directory
  "preserveStructure": true                   // NEW - Preserve source structure
}
```

### Validation Enhancements

New validation options:

```bash
# Pre-1.0 validation
pacc validate ./extension.json

# 1.0 enhanced validation
pacc validate ./extension.json --strict     # Treat warnings as errors
pacc validate ./directory/ --type commands  # Override type detection
```

## Team Collaboration Improvements

### Version Locking

```json
{
  "name": "team-project",
  "version": "1.0.0",
  "extensions": {
    "commands": [
      {
        "name": "shared-deploy",
        "source": "https://github.com/team/extensions.git",
        "version": "2.1.0",                    // Lock specific version
        "ref": "v2.1.0"                       // Lock Git reference
      }
    ]
  }
}
```

### Environment-Specific Extensions

```json
{
  "extensions": {
    "hooks": [
      {
        "name": "dev-hooks",
        "source": "./dev-hooks.json",
        "version": "1.0.0",
        "environment": "development"           // Only install in dev
      },
      {
        "name": "prod-hooks",
        "source": "./prod-hooks.json",
        "version": "1.0.0",
        "environment": "production"            // Only install in prod
      }
    ]
  }
}
```

## Common Migration Issues

### Issue 1: Type Detection Changes

**Problem:** Extensions detected differently than pre-1.0

**Solution:** Create explicit pacc.json declarations
```json
{
  "extensions": {
    "commands": [
      {"name": "my-extension", "source": "./my-extension.md", "version": "1.0.0"}
    ]
  }
}
```

### Issue 2: Validation Failures

**Problem:** New strict validation reveals issues

**Solution:** Fix validation errors or use non-strict mode initially
```bash
# Identify issues
pacc validate ./ --strict

# Fix issues, then use strict mode
pacc validate ./ --strict
```

### Issue 3: Path Resolution Changes

**Problem:** Relative paths resolve differently

**Solution:** Use absolute paths or project-relative paths
```json
{
  "extensions": {
    "commands": [
      {"name": "cmd", "source": "./commands/cmd.md", "version": "1.0.0"}
    ]
  }
}
```

## Testing Migration

### Validation Checklist

1. **Extension Detection**
   ```bash
   pacc validate ./pacc.json
   pacc validate .claude/ --strict
   ```

2. **Installation Testing**
   ```bash
   # Test in clean environment
   cp -r .claude .claude.test
   rm -rf .claude
   pacc sync  # Reinstall from pacc.json
   ```

3. **Functionality Testing**
   - Test each extension works correctly
   - Verify Claude Code integration
   - Check command execution

### Rollback Plan

If migration issues occur:

```bash
# Restore backup
rm -rf .claude
mv .claude.backup .claude

# Reinstall pre-1.0 version if needed
pip install pacc-cli==0.9.0  # Replace with last working version
```

## Best Practices Post-Migration

### 1. Use pacc.json for All Projects

```json
{
  "name": "project-name",
  "version": "1.0.0",
  "extensions": {
    // Explicit declarations
  }
}
```

### 2. Organize Extensions by Type

```
project/
├── pacc.json
├── extensions/
│   ├── hooks/
│   ├── commands/
│   ├── agents/
│   └── mcp/
└── .claude/           # Installation target
```

### 3. Use Strict Validation

```bash
# In CI/CD pipelines
pacc validate ./ --strict

# Before deployment
pacc validate ./pacc.json --strict
```

### 4. Version Control pacc.json

```gitignore
# .gitignore
.claude/          # Don't commit installed extensions
!pacc.json        # Do commit configuration
```

## Getting Help

### Documentation

- [Validation Guide](./validation_guide.md)
- [Folder Structure Guide](./folder_structure_guide.md)
- [Extension Detection Guide](./extension_detection_guide.md)
- [API Reference](./api_reference.md)

### Troubleshooting

```bash
# Check PACC version
pacc --version

# Validate configuration
pacc validate ./pacc.json --strict

# Debug extension detection
pacc validate ./extension.md --type commands
```

### Community Support

- GitHub Issues: Report bugs and migration problems
- Documentation: Comprehensive guides and examples
- Examples: Sample configurations and migrations

## Migration Success Criteria

Your migration is successful when:

1. ✅ All extensions validate without errors
2. ✅ Extensions are detected correctly
3. ✅ pacc.json configuration is working
4. ✅ Team members can sync successfully
5. ✅ CI/CD pipelines pass validation
6. ✅ Claude Code integration works as expected

Congratulations on successfully migrating to PACC 1.0! 🎉
