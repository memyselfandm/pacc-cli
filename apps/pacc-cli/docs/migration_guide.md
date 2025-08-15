# PACC CLI Migration Guide

This guide helps you migrate from a local/development installation of PACC to a global installation, and covers various migration scenarios.

## Table of Contents

- [Overview](#overview)
- [Migration Scenarios](#migration-scenarios)
- [Pre-Migration Checklist](#pre-migration-checklist)
- [Migration Steps](#migration-steps)
  - [From Local Development to Global](#from-local-development-to-global)
  - [From Project-Embedded to Standalone](#from-project-embedded-to-standalone)
  - [From Python Script to CLI Tool](#from-python-script-to-cli-tool)
- [Data Migration](#data-migration)
- [Configuration Migration](#configuration-migration)
- [Extension Migration](#extension-migration)
- [Compatibility Considerations](#compatibility-considerations)
- [Rollback Plan](#rollback-plan)
- [Post-Migration Verification](#post-migration-verification)
- [Troubleshooting](#troubleshooting)

## Overview

Migration to global PACC CLI installation provides several benefits:

- **System-wide availability**: Use `pacc` command from any directory
- **Consistent environment**: Same version across all projects
- **Easier updates**: Single command to update globally
- **Better isolation**: No interference with project dependencies
- **Team consistency**: Everyone uses the same tool version

## Migration Scenarios

### Scenario 1: Development Installation → Global Installation

You've been using PACC from the cloned repository:
```bash
cd pacc/apps/pacc-cli
python -m pacc install ./extension.json
```

Want to use it globally:
```bash
pacc install ./extension.json
```

### Scenario 2: Project-Specific → System-Wide

You've installed PACC in project virtual environments:
```bash
cd my-project
source venv/bin/activate
pip install pacc-cli
```

Want a single global installation:
```bash
pip install pacc-cli  # or pipx/uv
```

### Scenario 3: Script Usage → CLI Usage

You've been running PACC as a Python script:
```bash
python /path/to/pacc/main.py install ./extension.json
```

Want to use as a proper CLI:
```bash
pacc install ./extension.json
```

## Pre-Migration Checklist

Before migrating, ensure you have:

- [ ] Python 3.8 or higher installed
- [ ] Administrative access (if needed for global install)
- [ ] List of all installed extensions
- [ ] Backup of configurations
- [ ] Understanding of current setup

### Gather Current Information

```bash
# 1. Check current PACC location and version
which pacc  # or where pacc on Windows
python -c "import pacc; print(pacc.__version__, pacc.__file__)"

# 2. List all installed extensions
# From your local installation:
python -m pacc list --all > current-extensions.txt

# 3. Backup configurations
cp -r ~/.claude ~/.claude.backup
# For each project:
cp -r .claude .claude.backup

# 4. Note custom configurations
cat ~/.claude/pacc/config.json  # If exists
```

## Migration Steps

### From Local Development to Global

#### Step 1: Install Global PACC CLI

Choose your preferred method:

```bash
# Option A: Using pip
pip install pacc-cli

# Option B: Using pipx (recommended)
pipx install pacc-cli

# Option C: Using uv
uv tool install pacc-cli
```

#### Step 2: Verify Global Installation

```bash
# Check version
pacc --version

# Verify it's using global installation
which pacc  # Should show global location

# Test basic functionality
pacc --help
```

#### Step 3: Migrate Configurations

```bash
# Copy user configurations if they exist
if [ -d "$HOME/.claude/pacc" ]; then
    echo "User configuration already exists"
else
    # Copy from development location
    cp -r /path/to/dev/pacc/.claude/pacc ~/.claude/
fi
```

#### Step 4: Reinstall Extensions

```bash
# For each extension in current-extensions.txt
# Reinstall using global PACC

# User-level extensions
pacc install ./saved-extensions/calculator-mcp --user
pacc install ./saved-extensions/format-hook.json --user

# For each project
cd my-project
pacc install ./saved-extensions/project-hook.json --project
```

#### Step 5: Remove Local Installation

```bash
# Deactivate virtual environment if active
deactivate

# Remove development directory (optional)
# rm -rf /path/to/local/pacc

# Or keep for development
# Just remove from PATH
```

### From Project-Embedded to Standalone

#### Step 1: List All Project Installations

```bash
# Find all projects with PACC
find ~/projects -name "pacc" -type d | grep site-packages

# Or search for .claude directories
find ~/projects -name ".claude" -type d
```

#### Step 2: Document Extensions Per Project

For each project:
```bash
cd project-directory
source venv/bin/activate
python -m pacc list > project-extensions.txt
deactivate
```

#### Step 3: Install Global PACC

```bash
# Install globally
pipx install pacc-cli

# Verify
pacc --version
```

#### Step 4: Migrate Each Project

```bash
#!/bin/bash
# Migration script for all projects

projects=(
    ~/projects/project1
    ~/projects/project2
    ~/projects/project3
)

for project in "${projects[@]}"; do
    echo "Migrating $project"
    cd "$project"
    
    # Reinstall project extensions with global PACC
    if [ -f project-extensions.txt ]; then
        # Parse and reinstall extensions
        pacc install ./extensions/ --project
    fi
done
```

#### Step 5: Update Project Documentation

Update your project README files:

```markdown
## Setup

This project uses PACC CLI for Claude Code extensions.

### Install PACC CLI (one-time)
\`\`\`bash
pip install pacc-cli
# or
pipx install pacc-cli
\`\`\`

### Install Project Extensions
\`\`\`bash
pacc install
\`\`\`
```

### From Python Script to CLI Tool

#### Step 1: Document Current Usage

```bash
# Create wrapper script to capture current usage
cat > pacc-old.sh << 'EOF'
#!/bin/bash
python /path/to/pacc/main.py "$@"
EOF

chmod +x pacc-old.sh
```

#### Step 2: Install CLI Version

```bash
# Install global CLI
pip install pacc-cli

# Test parallel operation
pacc --version  # New
./pacc-old.sh --version  # Old
```

#### Step 3: Migrate Workflows

Update all scripts and documentation:

```bash
# Find all references to old usage
grep -r "python.*pacc.*main.py" .

# Update scripts
sed -i 's|python /path/to/pacc/main.py|pacc|g' *.sh

# Update documentation
sed -i 's|python -m pacc|pacc|g' *.md
```

#### Step 4: Verify Compatibility

```bash
# Test each command with new CLI
pacc validate ./test-extension.json
pacc install ./test-extension.json --dry-run
pacc list
```

## Data Migration

### Extension Registry Migration

```bash
# Export from old installation
python -m pacc list --json > extensions-backup.json

# Import to new installation
# Parse JSON and reinstall each extension
python << 'EOF'
import json
import subprocess

with open('extensions-backup.json') as f:
    extensions = json.load(f)

for ext in extensions.get('project', []):
    cmd = ['pacc', 'install', ext['source'], '--project']
    subprocess.run(cmd)

for ext in extensions.get('user', []):
    cmd = ['pacc', 'install', ext['source'], '--user']
    subprocess.run(cmd)
EOF
```

### Configuration Migration

```bash
# Backup existing configuration
cp ~/.claude/pacc/config.json config-backup.json

# Merge configurations if needed
python << 'EOF'
import json

# Load old config
with open('config-backup.json') as f:
    old_config = json.load(f)

# Apply to new installation
import subprocess
for key, value in old_config.items():
    cmd = ['pacc', 'config', 'set', key, str(value)]
    subprocess.run(cmd)
EOF
```

## Extension Migration

### Batch Migration Script

Create a migration script for all extensions:

```bash
#!/bin/bash
# migrate-extensions.sh

echo "Starting PACC extension migration..."

# User-level extensions
user_extensions=(
    "$HOME/saved-extensions/calculator-mcp"
    "$HOME/saved-extensions/weather-mcp"
    "$HOME/saved-extensions/format-hook.json"
)

echo "Migrating user-level extensions..."
for ext in "${user_extensions[@]}"; do
    if [ -e "$ext" ]; then
        echo "Installing $ext"
        pacc install "$ext" --user
    else
        echo "Warning: $ext not found"
    fi
done

# Project-level extensions
if [ -d ".claude" ]; then
    echo "Migrating project-level extensions..."
    for ext in .claude/hooks/*.json; do
        [ -e "$ext" ] || continue
        pacc install "$ext" --project
    done
fi

echo "Migration complete!"
```

### Handling Extension Conflicts

```bash
# Check for conflicts before migration
pacc list --all > new-extensions.txt
diff current-extensions.txt new-extensions.txt

# Resolve conflicts
pacc remove conflicting-extension --force
pacc install ./correct-extension.json
```

## Compatibility Considerations

### Version Compatibility

```bash
# Check version compatibility
python << 'EOF'
import json

# Old version
old_version = "0.9.0"  # Example

# New version  
new_version = "1.0.0"

# Check if major version changed
old_major = int(old_version.split('.')[0])
new_major = int(new_version.split('.')[0])

if old_major != new_major:
    print("Warning: Major version change detected")
    print("Review breaking changes in release notes")
EOF
```

### Path Differences

Update any hardcoded paths:

```bash
# Old paths
/home/user/dev/pacc/apps/pacc-cli/

# New paths (global installation)
~/.local/lib/python3.x/site-packages/pacc/
~/.local/bin/pacc
```

### Configuration Format Changes

Check for configuration format changes:

```bash
# Validate old configurations with new version
pacc validate ~/.claude/pacc/config.json

# Update if needed
pacc config migrate  # If such command exists
```

## Rollback Plan

### Preparation

Before migration, create a rollback script:

```bash
#!/bin/bash
# rollback-pacc.sh

echo "Rolling back PACC migration..."

# Restore configurations
cp -r ~/.claude.backup ~/.claude

# Uninstall global PACC
pip uninstall pacc-cli -y

# Restore local installation instructions
echo "To restore local installation:"
echo "1. cd /path/to/local/pacc"
echo "2. pip install -e ."

# List what needs manual restoration
echo "Manual steps needed:"
echo "- Reinstall project virtual environments"
echo "- Update PATH if needed"
echo "- Restore any custom scripts"
```

### Rollback Steps

If migration fails:

```bash
# 1. Run rollback script
./rollback-pacc.sh

# 2. Restore project configurations
for project in ~/projects/*; do
    [ -d "$project/.claude.backup" ] && \
        cp -r "$project/.claude.backup" "$project/.claude"
done

# 3. Reinstall local version
cd /path/to/local/pacc
pip install -e .

# 4. Verify rollback
python -m pacc --version
```

## Post-Migration Verification

### Comprehensive Testing

```bash
#!/bin/bash
# verify-migration.sh

echo "Verifying PACC migration..."

# 1. Check installation
if ! command -v pacc &> /dev/null; then
    echo "ERROR: pacc command not found"
    exit 1
fi

# 2. Version check
pacc --version || exit 1

# 3. Test basic commands
pacc --help > /dev/null || exit 1

# 4. Test validation
echo '{"name":"test","eventTypes":["PreToolUse"],"commands":["echo test"]}' > test.json
pacc validate test.json || exit 1
rm test.json

# 5. List extensions
pacc list --all || exit 1

# 6. Check configurations
if [ -f ~/.claude/pacc/config.json ]; then
    echo "✓ User configuration exists"
fi

echo "✓ Migration verification complete!"
```

### Performance Comparison

```bash
# Time command execution
time pacc list --all

# Compare with old installation if available
time python -m pacc list --all

# Check resource usage
/usr/bin/time -v pacc validate ./large-directory/
```

## Troubleshooting

### Common Migration Issues

#### Issue: Command Not Found

```bash
# Solution 1: Update PATH
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# Solution 2: Use full path
~/.local/bin/pacc --version

# Solution 3: Reinstall with --user
pip install --user pacc-cli
```

#### Issue: Permission Errors

```bash
# Solution 1: Use user installation
pip install --user pacc-cli

# Solution 2: Use virtual environment
python -m venv pacc-env
source pacc-env/bin/activate
pip install pacc-cli

# Solution 3: Use pipx/uv
pipx install pacc-cli
```

#### Issue: Missing Extensions

```bash
# List missing extensions
diff <(cat current-extensions.txt | sort) <(pacc list --all | sort)

# Reinstall missing extensions
while read ext; do
    pacc install "$ext"
done < missing-extensions.txt
```

#### Issue: Configuration Conflicts

```bash
# Backup conflicting config
mv ~/.claude/pacc/config.json ~/.claude/pacc/config.json.old

# Start fresh
pacc init --user

# Manually merge important settings
pacc config set defaultScope project
pacc config set validation.strict true
```

### Getting Help

If you encounter issues:

1. Check the error message carefully
2. Run with verbose mode: `pacc -v <command>`
3. Check logs: `~/.claude/pacc/logs/`
4. Review this guide's rollback section
5. Consult the [Troubleshooting Guide](troubleshooting_guide.md)

## Summary

Migrating to global PACC CLI installation provides a better development experience. Key points:

- **Plan carefully**: Document current state before migrating
- **Test thoroughly**: Verify each step works correctly
- **Have a rollback plan**: Be prepared to revert if needed
- **Update documentation**: Ensure team knows about the change
- **Maintain compatibility**: Check version differences

After successful migration, you'll have a more maintainable and consistent PACC setup across all your projects.

---

**Version**: 1.0.0 | **Last Updated**: December 2024