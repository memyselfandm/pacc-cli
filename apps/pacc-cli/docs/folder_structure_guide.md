# PACC Folder Structure Configuration Guide

## Overview

PACC 1.0 introduces advanced folder structure configuration through `targetDir` and `preserveStructure` options in `pacc.json`. This guide explains how to customize extension installation paths, preserve directory hierarchies, and migrate from default installations.

## Configuration Options

### targetDir

Specifies a custom installation directory for extensions within the Claude Code configuration folder.

```json
{
  "name": "custom-project",
  "version": "1.0.0", 
  "extensions": {
    "commands": [
      {
        "name": "deploy",
        "source": "./commands/deploy.md",
        "version": "1.0.0",
        "targetDir": "deployment-tools"
      }
    ]
  }
}
```

**Installation Path:** `.claude/commands/deployment-tools/deploy.md`

### preserveStructure

Controls whether the source directory structure is preserved during installation.

```json
{
  "name": "structured-project",
  "version": "1.0.0",
  "extensions": {
    "commands": [
      {
        "name": "build-tools",
        "source": "./src/commands/build/",
        "version": "1.0.0", 
        "preserveStructure": true
      }
    ]
  }
}
```

**Source Structure:**
```
src/commands/build/
├── docker/
│   ├── build.md
│   └── deploy.md
└── npm/
    ├── install.md
    └── test.md
```

**Installation Result:**
```
.claude/commands/build-tools/
├── docker/
│   ├── build.md
│   └── deploy.md
└── npm/
    ├── install.md
    └── test.md
```

## Configuration Scenarios

### 1. Custom Organization

```json
{
  "name": "organized-workspace",
  "version": "1.0.0",
  "extensions": {
    "commands": [
      {
        "name": "frontend-tools", 
        "source": "./commands/frontend/",
        "version": "1.0.0",
        "targetDir": "development/frontend"
      },
      {
        "name": "backend-tools",
        "source": "./commands/backend/",
        "version": "1.0.0", 
        "targetDir": "development/backend"
      }
    ],
    "hooks": [
      {
        "name": "ci-hooks",
        "source": "./automation/ci-cd/",
        "version": "1.0.0",
        "targetDir": "automation",
        "preserveStructure": true
      }
    ]
  }
}
```

**Result:**
```
.claude/
├── commands/
│   └── development/
│       ├── frontend/
│       │   └── [frontend tools]
│       └── backend/
│           └── [backend tools]
└── hooks/
    └── automation/
        └── [CI/CD structure preserved]
```

### 2. Team-Based Organization

```json
{
  "name": "team-extensions",
  "version": "1.0.0",
  "extensions": {
    "agents": [
      {
        "name": "devops-agent",
        "source": "./agents/devops.md", 
        "version": "1.0.0",
        "targetDir": "teams/devops"
      },
      {
        "name": "qa-agent",
        "source": "./agents/qa.md",
        "version": "1.0.0",
        "targetDir": "teams/qa"
      }
    ]
  }
}
```

### 3. Environment-Specific Configuration

```json
{
  "name": "multi-env-project",
  "version": "1.0.0",
  "extensions": {
    "commands": [
      {
        "name": "staging-commands",
        "source": "./commands/staging/",
        "version": "1.0.0",
        "targetDir": "environments/staging",
        "preserveStructure": true,
        "environment": "staging"
      },
      {
        "name": "production-commands", 
        "source": "./commands/production/",
        "version": "1.0.0",
        "targetDir": "environments/production",
        "preserveStructure": true,
        "environment": "production"
      }
    ]
  }
}
```

## Installation Behavior

### Default Installation (No Configuration)

```bash
# Without targetDir or preserveStructure
pacc install ./my-command.md --project
```

**Result:** `.claude/commands/my-command.md`

### Custom Target Directory

```json
{
  "targetDir": "custom-tools"
}
```

**Result:** `.claude/commands/custom-tools/my-command.md`

### Preserved Structure

```json
{
  "preserveStructure": true
}
```

**Source:** `./commands/utils/helper.md`
**Result:** `.claude/commands/utils/helper.md`

### Combined Configuration

```json
{
  "targetDir": "tools", 
  "preserveStructure": true
}
```

**Source:** `./src/commands/build/docker.md`
**Result:** `.claude/commands/tools/src/commands/build/docker.md`

## Migration from Default Installations

### Pre-1.0 Installation Structure

Before PACC 1.0, extensions were installed directly:

```
.claude/
├── commands/
│   ├── deploy.md
│   ├── build.md
│   └── test.md
├── hooks/
│   ├── pre-commit.json
│   └── post-deploy.json
└── agents/
    └── helper.md
```

### Migration Steps

1. **Assess Current Structure**
   ```bash
   # List current extensions
   pacc list --all
   
   # Check installation paths
   ls -la .claude/commands/
   ls -la .claude/hooks/
   ```

2. **Create Migration Configuration**
   ```json
   {
     "name": "migrated-project",
     "version": "1.0.0",
     "extensions": {
       "commands": [
         {
           "name": "deploy",
           "source": ".claude/commands/deploy.md",
           "version": "1.0.0",
           "targetDir": "legacy"
         }
       ]
     }
   }
   ```

3. **Backup Current Extensions**
   ```bash
   # Create backup
   cp -r .claude .claude.backup
   ```

4. **Reinstall with New Structure**
   ```bash
   # Remove old installations
   pacc remove deploy build test --force
   
   # Install with new configuration  
   pacc sync
   ```

### Migration Example

**Before (Pre-1.0):**
```
.claude/commands/
├── deploy.md
├── build.md
└── test.md
```

**After (1.0 with targetDir):**
```
.claude/commands/
└── project-tools/
    ├── deploy.md
    ├── build.md
    └── test.md
```

**Migration Configuration:**
```json
{
  "name": "project-migration",
  "version": "1.0.0",
  "extensions": {
    "commands": [
      {
        "name": "project-commands",
        "source": "./commands/",
        "version": "1.0.0",
        "targetDir": "project-tools",
        "preserveStructure": false
      }
    ]
  }
}
```

## Best Practices

### 1. Consistent Naming Conventions

```json
{
  "extensions": {
    "commands": [
      {
        "targetDir": "project-tools",      // kebab-case
        "name": "deployment-commands"      // consistent naming
      }
    ]
  }
}
```

### 2. Logical Grouping

```json
{
  "extensions": {
    "commands": [
      {
        "targetDir": "development",
        "name": "dev-tools"
      },
      {
        "targetDir": "deployment", 
        "name": "deploy-tools"
      },
      {
        "targetDir": "testing",
        "name": "test-tools"
      }
    ]
  }
}
```

### 3. Preserve Structure for Complex Extensions

```json
{
  "extensions": {
    "commands": [
      {
        "name": "multi-component-tool",
        "source": "./complex-commands/",
        "preserveStructure": true,    // Keep internal organization
        "targetDir": "tools/complex"  // But organize at top level
      }
    ]
  }
}
```

### 4. Environment-Specific Organization

```json
{
  "extensions": {
    "hooks": [
      {
        "name": "dev-hooks",
        "targetDir": "environments/development",
        "environment": "development"
      },
      {
        "name": "prod-hooks", 
        "targetDir": "environments/production",
        "environment": "production"
      }
    ]
  }
}
```

## Security Considerations

### Path Validation

PACC validates `targetDir` paths to prevent security issues:

```json
{
  "targetDir": "../../../etc"  // ❌ REJECTED - Path traversal
}
```

```json
{
  "targetDir": "tools/secure"  // ✅ ACCEPTED - Safe relative path
}
```

### Allowed Patterns

- ✅ `"tools"`
- ✅ `"project/commands"`
- ✅ `"teams/devops"`
- ❌ `"../outside"`
- ❌ `"/absolute/path"`
- ❌ `"~/home/path"`

### Claude Code Directory Boundaries

`targetDir` is restricted to within the Claude Code configuration directory:

```
.claude/                    # Configuration root
├── commands/
│   └── [targetDir]/       # Custom directories allowed here
├── hooks/
│   └── [targetDir]/       # Custom directories allowed here
└── agents/
    └── [targetDir]/       # Custom directories allowed here
```

## Command Line Interface

### Installation with Structure

```bash
# Install with default structure
pacc install ./commands/ --project

# Install preserving source structure  
pacc install ./commands/ --project --preserve-structure

# Install to custom directory
pacc install ./commands/ --project --target-dir "tools"
```

### Validation

```bash
# Validate folder structure configuration
pacc validate ./pacc.json

# Check for path traversal issues
pacc validate ./pacc.json --strict
```

## Troubleshooting

### Common Issues

1. **Path Not Found**
   ```bash
   Error: Target directory 'nonexistent/path' could not be created
   ```
   **Solution:** Ensure parent directories exist or use valid paths

2. **Permission Denied**
   ```bash
   Error: Permission denied creating directory '.claude/commands/tools'
   ```
   **Solution:** Check file permissions for `.claude` directory

3. **Path Traversal Blocked**
   ```bash
   Error: Invalid targetDir '../outside' - path traversal not allowed
   ```
   **Solution:** Use relative paths within Claude Code directory

### Debug Information

```bash
# Show installation paths
pacc list --verbose

# Validate configuration
pacc validate ./pacc.json --strict

# Check directory structure
pacc info <extension-name>
```

## Related Commands

- [`pacc sync`](./usage_documentation.md#sync-command) - Apply folder structure configuration
- [`pacc install`](./usage_documentation.md#install-command) - Install with custom structure
- [`pacc validate`](./validation_guide.md) - Validate configuration

## See Also

- [Extension Type Detection Guide](./extension_detection_guide.md)
- [Migration Guide](./migration_guide.md) 
- [Project Configuration Reference](./api_reference.md#project-configuration)