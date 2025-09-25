# PACC CLI Troubleshooting Guide

This comprehensive guide helps you diagnose and resolve common issues with PACC CLI.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Installation Issues](#installation-issues)
- [Command Execution Problems](#command-execution-problems)
- [Extension Installation Errors](#extension-installation-errors)
- [Validation Failures](#validation-failures)
- [Configuration Issues](#configuration-issues)
- [Permission and Access Problems](#permission-and-access-problems)
- [Platform-Specific Issues](#platform-specific-issues)
- [Performance Problems](#performance-problems)
- [Data and State Issues](#data-and-state-issues)
- [Integration Problems](#integration-problems)
- [Error Messages Reference](#error-messages-reference)
- [Debug Mode and Logging](#debug-mode-and-logging)
- [Getting Additional Help](#getting-additional-help)

## Quick Diagnostics

Run this diagnostic script to check your PACC installation:

```bash
#!/bin/bash
# pacc-diagnostic.sh

echo "PACC CLI Diagnostic Report"
echo "========================="
echo

# Check PACC installation
echo "1. PACC Installation:"
if command -v pacc &> /dev/null; then
    echo "   ✓ PACC found at: $(which pacc)"
    echo "   ✓ Version: $(pacc --version)"
else
    echo "   ✗ PACC not found in PATH"
fi
echo

# Check Python version
echo "2. Python Environment:"
echo "   Python: $(python --version 2>&1)"
echo "   Pip: $(pip --version)"
echo "   Location: $(which python)"
echo

# Check PACC module
echo "3. PACC Module:"
python -c "import pacc; print(f'   ✓ Module version: {pacc.__version__}')" 2>&1 || echo "   ✗ Module not found"
echo

# Check directories
echo "4. Claude Directories:"
[ -d "$HOME/.claude" ] && echo "   ✓ User config: ~/.claude/" || echo "   ✗ User config not found"
[ -d ".claude" ] && echo "   ✓ Project config: .claude/" || echo "   - No project config"
echo

# Check PATH
echo "5. PATH includes:"
echo "$PATH" | tr ':' '\n' | grep -E "(local/bin|\.local/bin|Scripts)" | sed 's/^/   /'
echo

# System info
echo "6. System Information:"
echo "   OS: $(uname -s)"
echo "   Architecture: $(uname -m)"
echo "   Shell: $SHELL"
```

## Installation Issues

### PACC Command Not Found

**Symptoms:**
```bash
$ pacc --version
bash: pacc: command not found
```

**Solutions:**

1. **Check if PACC is installed:**
```bash
pip show pacc-cli
# or
pip list | grep pacc-cli
```

2. **Ensure PATH includes pip's bin directory:**
```bash
# Find where pip installs scripts
python -m site --user-base

# Add to PATH (Linux/macOS)
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# Add to PATH (Windows)
# Add %APPDATA%\Python\Scripts to system PATH
```

3. **Use Python module directly:**
```bash
python -m pacc --version
```

4. **Reinstall with --user flag:**
```bash
pip uninstall pacc-cli
pip install --user pacc-cli
```

### Module Import Errors

**Symptoms:**
```python
ModuleNotFoundError: No module named 'pacc'
```

**Solutions:**

1. **Check Python environment:**
```bash
# Verify you're using the right Python
which python
python --version

# Check if PACC is installed for this Python
python -c "import sys; print(sys.path)"
python -m pip list | grep pacc
```

2. **Install in current environment:**
```bash
# Ensure pip is up to date
python -m pip install --upgrade pip

# Install PACC
python -m pip install pacc-cli
```

3. **Virtual environment issues:**
```bash
# Create fresh virtual environment
python -m venv pacc-env
source pacc-env/bin/activate  # Linux/macOS
# pacc-env\Scripts\activate     # Windows

pip install pacc-cli
```

### Dependency Conflicts

**Symptoms:**
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed
```

**Solutions:**

1. **Install in isolated environment:**
```bash
# Using pipx
pipx install pacc-cli

# Using uv
uv tool install pacc-cli
```

2. **Force reinstall:**
```bash
pip install --force-reinstall pacc-cli
```

3. **Install minimal dependencies:**
```bash
# Install without optional dependencies
pip install pacc-cli --no-deps
pip install PyYAML>=6.0  # Add required dependency manually
```

## Command Execution Problems

### Permission Denied Errors

**Symptoms:**
```bash
$ pacc install extension.json
PermissionError: [Errno 13] Permission denied: '/usr/local/lib/...'
```

**Solutions:**

1. **Use user installation:**
```bash
pacc install extension.json --user
```

2. **Check directory permissions:**
```bash
# Check permissions
ls -la ~/.claude/
ls -la .claude/

# Fix permissions if needed
chmod -R u+w ~/.claude/
```

3. **Run from writable directory:**
```bash
cd ~  # or another writable directory
pacc install /path/to/extension.json
```

### Command Timeout Issues

**Symptoms:**
```
TimeoutError: Command execution timed out
```

**Solutions:**

1. **Increase timeout:**
```bash
# Set environment variable
export PACC_TIMEOUT=300  # 5 minutes
pacc install large-extension/
```

2. **Process in smaller batches:**
```bash
# Instead of installing all at once
pacc install extensions/ --all

# Install individually
for ext in extensions/*; do
    pacc install "$ext"
done
```

## Extension Installation Errors

### Invalid Extension Format

**Symptoms:**
```
ValidationError: Invalid hook configuration: missing required field 'eventTypes'
```

**Solutions:**

1. **Check extension structure:**
```bash
# Validate before installing
pacc validate extension.json -v

# Check JSON syntax
python -m json.tool extension.json
```

2. **Fix common formatting issues:**
```json
// Bad - comments not allowed in JSON
{
  "name": "my-hook",
  // This comment will cause an error
  "eventTypes": ["PreToolUse"]
}

// Good - valid JSON
{
  "name": "my-hook",
  "eventTypes": ["PreToolUse"],
  "commands": ["echo 'Hello'"]
}
```

3. **Validate YAML frontmatter (agents):**
```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('agent.md').read().split('---')[1])"
```

### Path Resolution Errors

**Symptoms:**
```
FileNotFoundError: Extension file not found: ./extension.json
```

**Solutions:**

1. **Use absolute paths:**
```bash
pacc install /full/path/to/extension.json
```

2. **Check current directory:**
```bash
pwd
ls -la extension.json
```

3. **Handle spaces in paths:**
```bash
# Quote paths with spaces
pacc install "./My Extensions/hook.json"
```

### Duplicate Extension Errors

**Symptoms:**
```
ConflictError: Extension 'my-hook' already exists
```

**Solutions:**

1. **Force overwrite:**
```bash
pacc install extension.json --force
```

2. **Remove existing first:**
```bash
pacc remove my-hook
pacc install extension.json
```

3. **Check both scopes:**
```bash
pacc list --all | grep my-hook
pacc remove my-hook --user
pacc remove my-hook --project
```

## Validation Failures

### Schema Validation Errors

**Symptoms:**
```
ValidationError: Invalid schema for hook configuration
```

**Solutions:**

1. **Use strict validation for details:**
```bash
pacc validate extension.json --strict -v
```

2. **Check required fields:**

For hooks:
```json
{
  "name": "required",
  "eventTypes": ["required"],
  "commands": ["required"]
}
```

For MCP servers (.mcp.json):
```json
{
  "name": "required",
  "command": "required"
}
```

For agents (YAML frontmatter):
```yaml
---
name: required
description: required
tools:
  - name: required
---
```

### Command Safety Validation

**Symptoms:**
```
SecurityError: Potentially dangerous command detected
```

**Solutions:**

1. **Review command safety:**
```bash
# Dangerous commands are blocked
"rm -rf /"  # Blocked
"curl | bash"  # Blocked

# Safe alternatives
"echo 'Safe command'"
"python script.py"
```

2. **Use command arguments safely:**
```json
{
  "commands": [
    "prettier --write \"${file}\"",
    "eslint --fix \"${file}\""
  ]
}
```

## Configuration Issues

### Understanding Extension Types

**Important:** Not all extensions modify settings.json:

- **Configuration-based** (stored in settings.json):
  - Hooks: Require event and matcher configuration
  - MCP Servers: Require command and argument configuration

- **File-based** (no settings.json entry):
  - Agents: Stored in `.claude/agents/`, auto-discovered
  - Commands: Stored in `.claude/commands/`, auto-discovered

### Corrupted settings.json

**Symptoms:**
```
JSONDecodeError: Expecting value: line 1 column 1
```

**Solutions:**

1. **Restore from backup:**
```bash
# PACC creates automatic backups
ls ~/.claude/pacc/backups/
cp ~/.claude/pacc/backups/settings_20240315_120000.json ~/.claude/settings.json
```

2. **Validate and fix JSON:**
```bash
# Pretty-print and fix formatting
python -m json.tool ~/.claude/settings.json > settings_fixed.json
mv settings_fixed.json ~/.claude/settings.json
```

3. **Start fresh (only hooks and mcps needed):**
```bash
# Backup current
mv ~/.claude/settings.json ~/.claude/settings.json.bak

# Reinitialize with proper structure
echo '{"hooks": [], "mcps": []}' > ~/.claude/settings.json
```

### Configuration Not Loading

**Symptoms:**
```
Warning: Could not load configuration file
```

**Solutions:**

1. **Check file permissions:**
```bash
ls -la ~/.claude/pacc/config.json
chmod 644 ~/.claude/pacc/config.json
```

2. **Verify JSON syntax:**
```bash
python -m json.tool ~/.claude/pacc/config.json
```

3. **Reset configuration:**
```bash
rm ~/.claude/pacc/config.json
pacc config init
```

## Permission and Access Problems

### File System Permissions

**Symptoms:**
```
PermissionError: Cannot write to directory
```

**Solutions:**

1. **Check directory ownership:**
```bash
# Check ownership
ls -la ~/.claude/
ls -la .claude/

# Fix ownership
sudo chown -R $USER:$USER ~/.claude/
```

2. **Fix permissions:**
```bash
# Make directories writable
chmod -R u+w ~/.claude/
chmod -R u+w .claude/
```

3. **Use different scope:**
```bash
# If project fails, try user
pacc install extension.json --user
```

### Windows-Specific Permissions

**Symptoms:**
```
WindowsError: Access is denied
```

**Solutions:**

1. **Run as regular user (not admin):**
```powershell
# Don't use "Run as Administrator"
pacc install extension.json --user
```

2. **Check antivirus:**
- Add PACC to antivirus exceptions
- Temporarily disable real-time scanning

3. **Enable long path support:**
```powershell
# Run as Administrator
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

## Platform-Specific Issues

### macOS Issues

**Gatekeeper Blocking:**
```bash
# If macOS blocks execution
xattr -d com.apple.quarantine /path/to/pacc

# Or allow in System Preferences > Security & Privacy
```

**Python Version Issues:**
```bash
# Use Homebrew Python instead of system Python
brew install python@3.11
export PATH="/usr/local/opt/python@3.11/bin:$PATH"
```

### Windows Issues

**Path Separator Problems:**
```bash
# Use forward slashes or raw strings
pacc install "C:/Users/name/extension.json"
# or
pacc install r"C:\Users\name\extension.json"
```

**PowerShell Execution Policy:**
```powershell
# Check policy
Get-ExecutionPolicy

# Allow scripts (if needed)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Linux Issues

**Python Command Variations:**
```bash
# Some systems use python3
alias python=python3
alias pip=pip3

# Or use explicitly
python3 -m pacc --version
```

**SELinux Contexts:**
```bash
# If SELinux is blocking
sestatus  # Check if enabled

# Fix contexts
restorecon -Rv ~/.claude/
```

## Performance Problems

### Slow Validation

**Symptoms:**
- Validation takes more than a few seconds
- High CPU usage during validation

**Solutions:**

1. **Disable strict validation:**
```bash
# Use normal validation instead of strict
pacc validate extension.json
# Instead of: pacc validate extension.json --strict
```

2. **Validate specific files:**
```bash
# Instead of validating entire directory
pacc validate ./extensions/

# Validate specific files
pacc validate ./extensions/hook1.json
```

### Memory Issues

**Symptoms:**
```
MemoryError: Unable to allocate memory
```

**Solutions:**

1. **Process smaller batches:**
```bash
# Split large directories
find extensions/ -name "*.json" | head -10 | xargs -I {} pacc install {}
```

2. **Clear cache:**
```bash
rm -rf ~/.claude/pacc/cache/
```

## Data and State Issues

### Inconsistent State

**Symptoms:**
- Extensions appear installed but don't work
- List shows different results than actual files

**Solutions:**

1. **Rebuild extension registry:**
```bash
# Force rescan
pacc list --rebuild-cache
```

2. **Verify file system matches registry:**
```bash
# Check actual files
ls -la ~/.claude/hooks/
ls -la .claude/hooks/

# Compare with registry
pacc list --type hooks --json
```

3. **Clean and reinstall:**
```bash
# Remove all project extensions
rm -rf .claude/hooks/ .claude/agents/ .claude/commands/

# Reinstall from source
pacc install ./extension-source/ --all
```

### Backup and Recovery

**Create manual backup:**
```bash
# Backup all configurations
tar -czf claude-backup-$(date +%Y%m%d).tar.gz ~/.claude/ .claude/
```

**Restore from backup:**
```bash
# Restore configurations
tar -xzf claude-backup-20240315.tar.gz
```

## Integration Problems

### Claude Code Not Recognizing Extensions

**Symptoms:**
- Extensions installed but not working in Claude Code
- Commands not appearing

**Solutions:**

1. **Restart Claude Code:**
- Close and reopen Claude Code
- Extensions are loaded on startup

2. **Check installation location:**
```bash
# Verify correct directory
pacc info extension-name
# Should show correct path (.claude/ or ~/.claude/)
```

3. **Validate Claude Code settings:**
```bash
# Check settings.json is valid
python -m json.tool ~/.claude/settings.json
```

### Git Integration Issues

**Symptoms:**
- Git showing unexpected changes
- Merge conflicts in settings files

**Solutions:**

1. **Use proper .gitignore:**
```bash
# Add to .gitignore
echo ".claude/pacc/" >> .gitignore
echo ".claude/settings.local.json" >> .gitignore
echo ".claude/backups/" >> .gitignore
```

2. **Separate local and shared configs:**
```bash
# Shared configurations (commit these)
.claude/hooks/
.claude/agents/
.claude/commands/

# Local configurations (don't commit)
.claude/settings.local.json
.claude/pacc/
```

## Error Messages Reference

### Common Error Messages and Solutions

| Error | Meaning | Solution |
|-------|---------|----------|
| `FileNotFoundError` | Extension file doesn't exist | Check path and spelling |
| `PermissionError` | No write access | Use --user flag or check permissions |
| `ValidationError` | Extension format invalid | Run validate command for details |
| `ConflictError` | Extension already exists | Use --force to overwrite |
| `JSONDecodeError` | Invalid JSON syntax | Use json.tool to fix |
| `YAMLError` | Invalid YAML syntax | Check YAML formatting |
| `TimeoutError` | Operation took too long | Increase timeout or use smaller batches |
| `SecurityError` | Dangerous command detected | Review and fix commands |

## Debug Mode and Logging

### Enable Debug Output

```bash
# Set debug environment variable
export PACC_DEBUG=1
pacc install extension.json

# Or use verbose flag
pacc install extension.json -vvv
```

### Access Logs

```bash
# Default log location
cat ~/.claude/pacc/logs/pacc.log

# Follow logs in real-time
tail -f ~/.claude/pacc/logs/pacc.log
```

### Create Debug Report

```bash
#!/bin/bash
# Create comprehensive debug report

report_file="pacc-debug-$(date +%Y%m%d-%H%M%S).txt"

{
    echo "PACC Debug Report"
    echo "================="
    echo
    echo "Date: $(date)"
    echo "User: $USER"
    echo "Directory: $(pwd)"
    echo
    echo "PACC Version:"
    pacc --version
    echo
    echo "Python Environment:"
    python --version
    pip --version
    echo
    echo "Installed Extensions:"
    pacc list --all --json
    echo
    echo "Configuration:"
    cat ~/.claude/pacc/config.json 2>/dev/null || echo "No config file"
    echo
    echo "Recent Logs:"
    tail -n 50 ~/.claude/pacc/logs/pacc.log 2>/dev/null || echo "No logs found"
    echo
    echo "Environment Variables:"
    env | grep PACC
    echo
    echo "File System:"
    ls -la ~/.claude/ 2>/dev/null || echo "No user claude directory"
    ls -la .claude/ 2>/dev/null || echo "No project claude directory"
} > "$report_file"

echo "Debug report created: $report_file"
```

## Getting Additional Help

### Self-Help Resources

1. **Check documentation:**
   - [Installation Guide](installation_guide.md)
   - [Usage Documentation](usage_documentation.md)
   - [API Reference](api_reference.md)

2. **Search error messages:**
   ```bash
   # Search in PACC source
   grep -r "error message" ~/.local/lib/python*/site-packages/pacc/
   ```

3. **Test with examples:**
   ```bash
   # Use known-good examples
   pacc validate examples/simple-hook.json
   ```

### Community Support

1. **GitHub Issues:**
   - Search existing issues
   - Create detailed bug report
   - Include debug report

2. **Discussion Forums:**
   - Check FAQ section
   - Search before posting
   - Provide context and examples

### Bug Report Template

```markdown
## Bug Description
Brief description of the issue

## Environment
- PACC Version: (pacc --version)
- Python Version: (python --version)
- OS: (Windows/macOS/Linux)
- Installation Method: (pip/pipx/uv)

## Steps to Reproduce
1. Run command: `pacc install ...`
2. See error: ...

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Debug Output
\`\`\`
(paste verbose output here)
\`\`\`

## Additional Context
Any other relevant information
```

Remember: Most issues can be resolved by:
1. Checking the installation is correct
2. Validating extensions before installing
3. Using appropriate permissions/scope
4. Reading error messages carefully

---

**Version**: 1.0.0 | **Last Updated**: December 2024
