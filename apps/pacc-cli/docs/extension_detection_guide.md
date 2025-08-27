# Extension Type Detection Guide

## Overview

PACC uses a hierarchical detection system to identify extension types automatically. This guide explains the detection priorities, common scenarios, and how to troubleshoot type detection issues. Understanding this system helps prevent misclassification and ensures extensions are handled correctly.

## Detection Hierarchy

PACC follows a three-tier detection approach:

1. **pacc.json declarations** (Highest Priority)
2. **Directory structure** (Secondary Signal)  
3. **Content keywords** (Fallback Only)

### Priority 1: pacc.json Declarations

When a `pacc.json` file exists, explicit declarations take absolute priority over all other detection methods.

```json
{
  "name": "my-project",
  "version": "1.0.0",
  "extensions": {
    "commands": [
      {
        "name": "helper",
        "source": "./agents/helper.md",  // File is in agents/ directory
        "version": "1.0.0"
      }
    ]
  }
}
```

**Result:** `./agents/helper.md` is detected as a **command**, not an agent, because pacc.json declares it as such.

### Priority 2: Directory Structure

When no pacc.json declaration exists, directory structure provides type hints:

```
project/
├── hooks/          # Files here detected as hooks
│   └── pre-commit.json
├── commands/       # Files here detected as commands  
│   └── deploy.md
├── agents/         # Files here detected as agents
│   └── helper.md
└── mcp/           # Files here detected as mcp
    └── server.json
```

### Priority 3: Content Keywords

As a final fallback, PACC analyzes file content for type-specific keywords:

- **Hooks:** `"hooks"`, `"event"`, `"PreToolUse"`, `"PostToolUse"`
- **MCP:** `"mcpServers"`, `"command"`, `"args"`, `"env"`
- **Agents:** `"tools"`, `"permissions"`, YAML frontmatter
- **Commands:** `"#/"`, `"## Usage"`, `"## Parameters"`

## Detection Examples

### Example 1: pacc.json Override

**File:** `./agents/slash-command.md`
```markdown
---
name: deployment-helper
description: Helps with deployments using agent-like assistance  
---

# Deployment Helper

This tool provides agent capabilities for deployment tasks.
Uses tools and permissions like agents do.
```

**pacc.json:**
```json
{
  "extensions": {
    "commands": [
      {
        "name": "deployment-helper",
        "source": "./agents/slash-command.md",
        "version": "1.0.0"
      }
    ]
  }
}
```

**Detection Result:** `commands` (pacc.json overrides directory structure and content)

### Example 2: Directory Structure Detection

**File:** `./commands/helper-tool.md`
```markdown
This file helps users with agent-like functionality.
Contains keywords: tool, permission, agent assistance.
```

**No pacc.json exists**

**Detection Result:** `commands` (directory structure overrides content keywords)

### Example 3: Content Keyword Fallback

**File:** `./random-location/clear-agent.md`
```markdown
---
name: file-organizer
description: Organizes files based on patterns
tools: ["file-reader", "file-writer"]
permissions: ["read-files", "write-files"]
---

# File Organizer Agent

This agent analyzes files and organizes them...
```

**No pacc.json, no special directory structure**

**Detection Result:** `agents` (content keywords used as fallback)

## Common Detection Issues

### Issue 1: Slash Commands Detected as Agents (PACC-18)

**Problem:**
```markdown
---
name: pacc-install  
description: Install extensions using PACC CLI tool
---

# /pacc:install

Install Claude Code extensions with tool validation and permission checking.

Contains keywords: tool, permission, agent-like assistance
```

**Without proper hierarchy, this could be detected as an agent.**

**Solution - Use Directory Structure:**
```
commands/
└── pacc-install.md    # Directory structure ensures correct detection
```

**Or Use pacc.json:**
```json
{
  "extensions": {
    "commands": [
      {
        "name": "pacc-install",
        "source": "./pacc-install.md",
        "version": "1.0.0"
      }
    ]
  }
}
```

### Issue 2: Ambiguous Content

**Problem:**
```markdown
This file contains both agent and command keywords.
Has agent, tool, permission references.
But also has command, usage, slash patterns.
```

**Solution - Explicit Declaration:**
```json
{
  "extensions": {
    "agents": [
      {
        "name": "ambiguous-file",
        "source": "./ambiguous-file.md",
        "version": "1.0.0"
      }
    ]
  }
}
```

### Issue 3: Non-Standard File Names

**Problem:**
```
custom-automation.json    # Could be hook, but unusual name
my-special-server.conf    # Could be MCP, but unusual extension
```

**Solution - Force Type Detection:**
```bash
# Override detection with explicit type
pacc validate ./custom-automation.json --type hooks
pacc validate ./my-special-server.conf --type mcp
```

## Detection Algorithms

### Hooks Detection

**File Extensions:** `.json`

**Directory Indicators:** `hooks/`, `automation/`

**Content Keywords:**
- `"hooks"` array present
- `"event"` field with valid event types
- `"PreToolUse"`, `"PostToolUse"`, etc.

**Example Pattern:**
```json
{
  "name": "example-hook",
  "hooks": [                    // ← Key indicator
    {
      "event": "PreToolUse",    // ← Event type
      "command": "npm test"
    }
  ]
}
```

### MCP Server Detection

**File Extensions:** `.json`

**Directory Indicators:** `mcp/`, `servers/`

**Content Keywords:**
- `"mcpServers"` object present
- Server configuration with `"command"` and `"args"`

**Example Pattern:**
```json
{
  "mcpServers": {             // ← Key indicator
    "database": {
      "command": "npx",       // ← Command field
      "args": ["@mcp/server"] // ← Args array
    }
  }
}
```

### Agents Detection

**File Extensions:** `.md`

**Directory Indicators:** `agents/`, `assistants/`

**Content Keywords:**
- YAML frontmatter with `tools` or `permissions`
- `"tools"` array
- `"permissions"` array

**Example Pattern:**
```markdown
---
name: example-agent
tools: ["file-reader"]        // ← Tools array
permissions: ["read-files"]   // ← Permissions array  
---
```

### Commands Detection

**File Extensions:** `.md`

**Directory Indicators:** `commands/`, `slash-commands/`

**Content Keywords:**
- Headers starting with `#/` (slash command syntax)
- `## Usage` or `## Parameters` sections
- Command documentation patterns

**Example Pattern:**
```markdown
# /example                   // ← Slash command header

## Usage                     // ← Usage section
/example <param>

## Parameters               // ← Parameters section
```

## Best Practices

### 1. Use Explicit Declarations

For production projects, always use pacc.json declarations:

```json
{
  "name": "production-project",
  "version": "1.0.0",
  "extensions": {
    "commands": [
      {"name": "deploy", "source": "./deploy.md", "version": "1.0.0"}
    ],
    "hooks": [
      {"name": "ci-hook", "source": "./ci.json", "version": "1.0.0"}
    ]
  }
}
```

### 2. Organize by Directory Structure

Structure projects to support automatic detection:

```
project/
├── pacc.json              # Explicit declarations
├── hooks/                 # Auto-detected as hooks
├── commands/              # Auto-detected as commands
├── agents/                # Auto-detected as agents
└── mcp/                   # Auto-detected as mcp
```

### 3. Use Consistent Naming

Follow naming conventions that aid detection:

```
hooks/
├── pre-commit-hook.json   # Clear hook naming
└── post-deploy-hook.json

commands/
├── build-command.md       # Clear command naming  
└── deploy-command.md

agents/
├── file-agent.md          # Clear agent naming
└── helper-agent.md
```

### 4. Validate Detection Results

Always validate that detection works correctly:

```bash
# Test detection without installation
pacc validate ./my-extension.md

# Check detected type
pacc validate ./my-extension.md --type commands  # Override if needed
```

## Troubleshooting Detection

### Debug Detection Issues

```bash
# Check what type PACC detects
pacc validate ./extension.md

# Override detection for testing
pacc validate ./extension.md --type hooks

# Validate entire directory structure
pacc validate ./project/ --strict
```

### Common Solutions

1. **Wrong Type Detected**
   - Add explicit pacc.json declaration
   - Move file to appropriate directory
   - Use `--type` flag to override

2. **No Type Detected**
   - Add content keywords
   - Use standard file extensions (.json, .md)
   - Place in conventional directory structure

3. **Ambiguous Detection**
   - Create pacc.json with explicit declarations
   - Remove conflicting keywords from content
   - Use directory structure as tiebreaker

## Detection API

### Programmatic Detection

```python
from pacc.validators.utils import ExtensionDetector

detector = ExtensionDetector()

# Detect with all hierarchy levels
detected_type = detector.detect_extension_type(
    file_path="./my-extension.md",
    project_dir="./my-project"    # Look for pacc.json here
)

# Detect without pacc.json (legacy mode)
detected_type = detector.detect_extension_type("./my-extension.md")
```

### Detection Results

```python
# Possible return values:
# - "hooks"
# - "mcp" 
# - "agents"
# - "commands"
# - None (if no type detected)
```

## Migration from Pre-1.0

### Old Detection (Pre-1.0)

- Relied primarily on file content
- Directory structure had limited influence
- No pacc.json support
- Prone to misclassification

### New Detection (1.0+)

- Hierarchical approach with clear priorities
- pacc.json declarations take precedence
- Directory structure as strong signal
- Content keywords only as fallback

### Migration Steps

1. **Test Current Detection:**
   ```bash
   pacc validate ./extensions/
   ```

2. **Create pacc.json for Clarity:**
   ```json
   {
     "name": "migrated-project",
     "version": "1.0.0", 
     "extensions": {
       "commands": [
         {"name": "cmd1", "source": "./cmd1.md", "version": "1.0.0"}
       ]
     }
   }
   ```

3. **Reorganize Directory Structure:**
   ```bash
   mkdir -p hooks commands agents mcp
   mv *.json hooks/
   mv *.md commands/
   ```

## Related Documentation

- [Validation Guide](./validation_guide.md) - Test detection results
- [Folder Structure Guide](./folder_structure_guide.md) - Directory organization
- [Migration Guide](./migration_guide.md) - Upgrade from pre-1.0
- [API Reference](./api_reference.md) - Detection API details