# Getting Started with PACC CLI

Welcome to PACC (Package manager for Claude Code)! This guide will walk you through your first steps with PACC, from installation to managing your first extensions.

## Table of Contents

- [Quick Start (5 minutes)](#quick-start-5-minutes)
- [Understanding Claude Code Extensions](#understanding-claude-code-extensions)
- [Tutorial 1: Installing Your First Hook](#tutorial-1-installing-your-first-hook)
- [Tutorial 2: Managing MCP Servers](#tutorial-2-managing-mcp-servers)
- [Tutorial 3: Working with Agents](#tutorial-3-working-with-agents)
- [Tutorial 4: Adding Custom Commands](#tutorial-4-adding-custom-commands)
- [Common Workflows](#common-workflows)
- [Best Practices](#best-practices)
- [Next Steps](#next-steps)

## Quick Start (5 minutes)

Get PACC up and running in just a few minutes:

### 1. Install PACC CLI

```bash
# Using pip (simplest)
pip install pacc-cli

# Or using pipx (recommended)
pipx install pacc-cli

# Verify installation
pacc --version
```

### 2. Setup Environment (Plugin Support)

If you plan to use plugins, configure your environment first:

```bash
# Check if environment is already configured
pacc env check

# If not configured, set it up automatically
pacc env setup

# Verify the setup worked
pacc env check
# Should show: ✅ ENABLE_PLUGINS is configured
```

**Manual setup (alternative)**:
```bash
# Add to your shell profile
echo 'export ENABLE_PLUGINS=1' >> ~/.bashrc  # or ~/.zshrc
source ~/.bashrc

# Verify
echo $ENABLE_PLUGINS  # Should output: 1
```

### 3. Create Your First Extension

Create a simple hook that formats code:

```bash
# Create a test hook
cat > format-hook.json << 'EOF'
{
  "name": "format-hook",
  "eventTypes": ["PreToolUse"],
  "matchers": [{"tool": "Write"}],
  "commands": ["echo 'Formatting code...'"],
  "description": "Simple formatting hook"
}
EOF
```

### 4. Validate and Install

```bash
# Validate the hook
pacc validate format-hook.json
# Output: ✓ Valid hook configuration

# Install to current project
pacc install format-hook.json --project

# Verify installation
pacc list
```

Congratulations! You've installed your first Claude Code extension with PACC.

## Understanding Claude Code Extensions

Before diving deeper, let's understand the four types of extensions PACC manages:

### 1. Hooks
- **Purpose**: Run commands on Claude Code events
- **Events**: PreToolUse, PostToolUse, Notification, Stop
- **Format**: JSON configuration files
- **Example**: Format code before writing, run tests after changes

### 2. MCP Servers
- **Purpose**: Extend Claude's capabilities with external tools
- **Format**: Executable programs with `.mcp.json` configuration
- **Example**: Calculator, weather service, database access

### 3. Agents
- **Purpose**: Specialized AI assistants with specific tools
- **Format**: Markdown files with YAML frontmatter
- **Example**: Code reviewer, test writer, documentation generator

### 4. Commands
- **Purpose**: Quick slash commands in Claude Code
- **Format**: Markdown files in commands directory
- **Example**: `/deploy`, `/test`, `/lint`

## Tutorial 1: Installing Your First Hook

Let's create a more sophisticated hook that runs code quality checks.

### Step 1: Create the Hook Configuration

```bash
# Create a quality check hook
cat > quality-check-hook.json << 'EOF'
{
  "name": "quality-check",
  "description": "Run quality checks before code modifications",
  "eventTypes": ["PreToolUse"],
  "matchers": [
    {
      "tool": "Write",
      "pathGlob": "**/*.{js,py,ts}"
    }
  ],
  "commands": [
    "echo '🔍 Running quality checks...'",
    "echo '✓ Syntax check passed'",
    "echo '✓ Style check passed'"
  ]
}
EOF
```

### Step 2: Understand the Structure

- **name**: Unique identifier for the hook
- **eventTypes**: When the hook runs
- **matchers**: Conditions for triggering (optional)
- **commands**: Shell commands to execute

### Step 3: Validate Before Installing

```bash
# Always validate first
pacc validate quality-check-hook.json --type hooks

# Get detailed validation output
pacc validate quality-check-hook.json -v
```

### Step 4: Install the Hook

```bash
# Preview what will happen
pacc install quality-check-hook.json --dry-run

# Install to current project
pacc install quality-check-hook.json --project

# Or install globally for all projects
pacc install quality-check-hook.json --user
```

### Step 5: Verify and Manage

```bash
# List installed hooks
pacc list --type hooks

# Get detailed information
pacc info quality-check

# Remove if needed
pacc remove quality-check --project
```

## Tutorial 2: Managing MCP Servers

MCP (Model Context Protocol) servers extend Claude's capabilities. Let's set up a calculator server.

### Step 1: Create MCP Server Structure

```bash
# Create directory for MCP server
mkdir calculator-mcp
cd calculator-mcp

# Create the executable (example)
cat > calculator-server.py << 'EOF'
#!/usr/bin/env python3
import sys
import json

# Simple calculator MCP server example
def calculate(operation, a, b):
    ops = {
        'add': a + b,
        'subtract': a - b,
        'multiply': a * b,
        'divide': a / b if b != 0 else 'Error: Division by zero'
    }
    return ops.get(operation, 'Unknown operation')

# MCP server implementation would go here
print("Calculator MCP Server v1.0")
EOF

chmod +x calculator-server.py
```

### Step 2: Create MCP Configuration

```bash
# Create .mcp.json configuration
cat > .mcp.json << 'EOF'
{
  "name": "calculator",
  "description": "Basic arithmetic operations",
  "command": "./calculator-server.py",
  "env": {
    "PYTHONUNBUFFERED": "1"
  },
  "settings": {
    "precision": 2,
    "mode": "basic"
  }
}
EOF

cd ..
```

### Step 3: Install the MCP Server

```bash
# Validate MCP configuration
pacc validate calculator-mcp --type mcp

# Install globally (recommended for MCP servers)
pacc install calculator-mcp --user

# Verify installation
pacc list --type mcp
```

### Step 4: Managing MCP Servers

```bash
# View MCP server details
pacc info calculator --user

# Update MCP server
pacc install calculator-mcp --user --force

# Remove MCP server
pacc remove calculator --user
```

## Tutorial 3: Working with Agents

Agents are AI assistants with specialized capabilities. Let's create a code review agent.

### Step 1: Create Agent File

```bash
# Create agents directory
mkdir -p my-agents

# Create code review agent
cat > my-agents/code-reviewer.md << 'EOF'
---
name: code-reviewer
description: Reviews code for best practices and potential issues
tools:
  - name: Read
    description: Read files to review code
  - name: Comment
    description: Add review comments
parameters:
  style_guide: "PEP8"
  severity: "medium"
---

# Code Reviewer Agent

I am a code review specialist that helps ensure code quality and best practices.

## Capabilities

- Review code for style compliance
- Identify potential bugs and issues
- Suggest improvements and optimizations
- Check for security vulnerabilities
- Ensure proper documentation

## Review Process

1. I analyze the code structure and patterns
2. Check against configured style guide
3. Look for common anti-patterns
4. Provide constructive feedback
5. Suggest specific improvements

Use me to maintain high code quality standards in your project!
EOF
```

### Step 2: Install the Agent

```bash
# Validate agent configuration
pacc validate my-agents/code-reviewer.md --type agents

# Install to project
pacc install my-agents/code-reviewer.md --project

# List installed agents
pacc list --type agents
```

### Step 3: Install Multiple Agents

```bash
# Create more agents
cat > my-agents/test-writer.md << 'EOF'
---
name: test-writer
description: Generates comprehensive unit tests
tools:
  - name: Read
    description: Read code to test
  - name: Write
    description: Write test files
---

# Test Writer Agent

I specialize in writing comprehensive unit tests for your code.
EOF

cat > my-agents/doc-generator.md << 'EOF'
---
name: doc-generator
description: Creates documentation from code
tools:
  - name: Read
    description: Read source files
  - name: Write
    description: Write documentation
---

# Documentation Generator

I create clear, comprehensive documentation for your code.
EOF

# Install all agents interactively
pacc install my-agents/ --interactive

# Select specific agents:
# [1] code-reviewer - Reviews code for best practices
# [2] test-writer - Generates comprehensive unit tests
# [3] doc-generator - Creates documentation from code
# Select (e.g., 1,3 or all): 1,2,3
```

## Tutorial 4: Adding Custom Commands

Commands provide quick shortcuts in Claude Code. Let's create some useful commands.

### Step 1: Create Commands Directory

```bash
# Create commands directory structure
mkdir -p my-commands

# Create deploy command
cat > my-commands/deploy.md << 'EOF'
# deploy

Deploy the application to production

## Usage
/deploy [environment] [--dry-run]

## Arguments
- environment: Target environment (staging, production)
- --dry-run: Preview deployment without executing

## Examples
/deploy staging
/deploy production --dry-run
EOF

# Create test command
cat > my-commands/test.md << 'EOF'
# test

Run project test suite

## Usage
/test [pattern] [--coverage]

## Arguments
- pattern: Test file pattern (optional)
- --coverage: Include coverage report

## Examples
/test
/test user_*.py --coverage
EOF
```

### Step 2: Install Commands

```bash
# Validate commands
pacc validate my-commands/ --type commands

# Install all commands
pacc install my-commands/ --project --all

# Or install interactively
pacc install my-commands/ --interactive
```

### Step 3: Manage Commands

```bash
# List installed commands
pacc list --type commands

# View command details
pacc info deploy

# Update command
pacc install my-commands/deploy.md --force
```

## Common Workflows

### Setting Up a New Project

```bash
#!/bin/bash
# setup-project.sh

# 1. Initialize project
mkdir new-project
cd new-project

# 2. Create standard extensions
mkdir -p .claude/{hooks,agents,commands}

# 3. Install common hooks
pacc install ~/standard-hooks/format-hook.json --project
pacc install ~/standard-hooks/test-hook.json --project

# 4. Install project-specific agents
pacc install ~/agents/code-reviewer.md --project

# 5. Create project configuration
cat > pacc.json << 'EOF'
{
  "name": "new-project",
  "extensions": {
    "hooks": ["format-hook", "test-hook"],
    "agents": ["code-reviewer"]
  }
}
EOF

# 6. Verify setup
pacc list --all
```

### Team Onboarding

```bash
# For new team members
git clone <project-repo>
cd <project>

# Install PACC if not already installed
pip install pacc-cli

# Install all project extensions
pacc install  # Reads pacc.json

# Verify installation
pacc list --project
```

### Daily Development Workflow

```bash
# Morning setup
cd my-project

# Check for extension updates
pacc list --all

# Add new hook for current feature
pacc install ./feature-hooks/validation-hook.json --project

# Work on feature...

# Before committing, validate all extensions
pacc validate .claude/ --strict

# Remove temporary extensions
pacc remove validation-hook --project
```

### Extension Development Workflow

```bash
# 1. Create extension
cat > my-hook.json << 'EOF'
{
  "name": "my-hook",
  "eventTypes": ["PreToolUse"],
  "commands": ["echo 'My custom hook'"]
}
EOF

# 2. Validate during development
pacc validate my-hook.json --strict

# 3. Test installation
pacc install my-hook.json --dry-run

# 4. Install and test
pacc install my-hook.json --project

# 5. Package for distribution
mkdir my-extensions
cp my-hook.json my-extensions/
echo "# My Extensions" > my-extensions/README.md

# 6. Share with team
git add my-extensions/
git commit -m "Add custom hook"
git push
```

## Best Practices

### 1. Always Validate First

```bash
# Good practice
pacc validate extension.json && pacc install extension.json

# Even better with strict validation
pacc validate extension.json --strict && pacc install extension.json
```

### 2. Use Appropriate Scopes

```bash
# Personal tools → User level
pacc install personal-formatter.json --user

# Project-specific → Project level
pacc install project-deployer.json --project

# Team shared → Version control + project level
git add .claude/hooks/team-hook.json
```

### 3. Document Your Extensions

```bash
# Create documentation for custom extensions
cat > extensions/README.md << 'EOF'
# Project Extensions

## Hooks
- format-hook: Runs prettier on JS/TS files
- test-hook: Runs unit tests before commits

## Agents
- code-reviewer: Reviews PRs for style and bugs

## Installation
\`\`\`bash
pacc install extensions/ --all --project
\`\`\`
EOF
```

### 4. Use Interactive Mode for Discovery

```bash
# When exploring new extension sets
pacc install ./community-extensions/ --interactive

# Review each option before installing
```

### 5. Regular Maintenance

```bash
# Weekly maintenance routine
# 1. List all extensions
pacc list --all > extensions-audit.txt

# 2. Validate all configurations
pacc validate .claude/ --strict
pacc validate ~/.claude/ --strict

# 3. Remove unused extensions
pacc remove unused-extension --force

# 4. Update documentation
echo "Last audit: $(date)" >> extensions-audit.txt
```

## Next Steps

### Learn More

1. **[Usage Documentation](usage_documentation.md)** - Comprehensive command reference
2. **[API Reference](api_reference.md)** - Detailed technical documentation
3. **Extension Development** - Create your own extensions (coming soon)

### Advanced Topics

1. **URL Installations** - Install from GitHub and other sources
2. **Custom Validators** - Add validation for your extensions
3. **Automation** - Integrate PACC into CI/CD pipelines

### Get Involved

1. **Share Extensions** - Contribute to the community repository
2. **Report Issues** - Help improve PACC
3. **Join Discussions** - Connect with other users

### Quick Reference Card

```bash
# Essential Commands
pacc --help                          # Show all commands
pacc install <source> [--user|--project]  # Install extension
pacc validate <source> [--strict]    # Validate extension
pacc list [--all]                    # List installed extensions
pacc remove <name> [--force]         # Remove extension
pacc info <name>                     # Show extension details

# Useful Options
--dry-run        # Preview without changes
--interactive    # Select from multiple items
--force          # Overwrite existing
--all            # Apply to all items
-v, --verbose    # Detailed output
```

Remember: PACC is designed to make your Claude Code experience more powerful and efficient. Start simple, experiment safely with `--dry-run`, and gradually build your perfect development environment!

---

**Happy Coding with PACC!** 🚀

**Version**: 1.0.0 | **Last Updated**: December 2024
