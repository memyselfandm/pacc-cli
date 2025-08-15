# PACC CLI Installation Guide

This comprehensive guide covers all installation methods for PACC CLI (Package manager for Claude Code). Choose the installation method that best fits your workflow.

> **Note**: The package is published as `pacc-cli` on PyPI since `pacc` was already taken.

## Table of Contents

- [Quick Start](#quick-start)
- [System Requirements](#system-requirements)
- [Installation Methods](#installation-methods)
  - [Using pip (Recommended)](#using-pip-recommended)
  - [Using uv](#using-uv)
  - [Using pipx](#using-pipx)
  - [Development Installation](#development-installation)
- [Virtual Environment Best Practices](#virtual-environment-best-practices)
- [Post-Installation Setup](#post-installation-setup)
- [Verifying Installation](#verifying-installation)
- [Troubleshooting](#troubleshooting)
- [Updating PACC CLI](#updating-pacc-cli)
- [Uninstalling](#uninstalling)

## Quick Start

For most users, the simplest installation method is:

```bash
# Install globally with pip
pip install pacc-cli

# Or install in user space
pip install --user pacc-cli

# Verify installation
pacc --version
```

## System Requirements

- **Python**: 3.8 or higher
- **Operating System**: Windows, macOS, or Linux
- **Memory**: 50MB minimum
- **Storage**: 10MB for installation
- **Dependencies**: PyYAML (automatically installed)

### Checking Your Python Version

```bash
python --version
# or
python3 --version
```

If you need to install or update Python, visit [python.org](https://www.python.org/downloads/).

## Installation Methods

### Using pip (Recommended)

pip is the standard Python package installer and works on all platforms.

#### Global Installation

```bash
# Install globally (requires admin/root privileges)
pip install pacc-cli

# On some systems, you may need to use pip3
pip3 install pacc-cli
```

#### User Installation

Installing in user space doesn't require admin privileges:

```bash
# Install for current user only
pip install --user pacc-cli

# Add user bin directory to PATH if needed
# Linux/macOS: Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.local/bin:$PATH"

# Windows: Add %APPDATA%\Python\Scripts to PATH
```

#### Installing with Optional Dependencies

```bash
# Install with URL support for remote installations
pip install pacc-cli[url]

# Install with all development dependencies
pip install pacc-cli[dev]

# Install with all extras
pip install pacc-cli[url,dev]
```

### Using uv

[uv](https://github.com/astral-sh/uv) is a fast Python package installer written in Rust.

#### Installing uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

#### Installing PACC CLI with uv

```bash
# Install as a tool (recommended)
uv tool install pacc-cli

# This automatically:
# - Creates an isolated environment
# - Installs pacc-cli
# - Makes the 'pacc' command available globally

# Install with extras
uv tool install pacc-cli[url]

# Verify installation
pacc --version
```

#### Benefits of uv tool install

- **Isolated environment**: No conflicts with other packages
- **Automatic PATH management**: Command available immediately
- **Easy updates**: `uv tool upgrade pacc-cli`
- **Clean uninstall**: `uv tool uninstall pacc-cli`

### Using pipx

[pipx](https://pypa.github.io/pipx/) installs Python applications in isolated environments.

#### Installing pipx

```bash
# Using pip
python -m pip install --user pipx
python -m pipx ensurepath

# macOS with Homebrew
brew install pipx
pipx ensurepath

# Windows with Scoop
scoop install pipx
pipx ensurepath
```

#### Installing PACC CLI with pipx

```bash
# Install pacc-cli
pipx install pacc-cli

# Install with optional dependencies
pipx install pacc-cli[url]

# The 'pacc' command is now available globally
pacc --version
```

#### Benefits of pipx

- **Isolation**: Each tool gets its own virtual environment
- **No dependency conflicts**: Tools can't interfere with each other
- **Easy management**: `pipx list`, `pipx upgrade`, `pipx uninstall`
- **Automatic PATH handling**: Commands available immediately

### Development Installation

For contributing to PACC or testing the latest changes:

```bash
# Clone the repository
git clone https://github.com/your-org/pacc.git
cd pacc/apps/pacc-cli

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install in editable mode with all dependencies
pip install -e ".[dev,url]"

# Run tests to verify
pytest
```

## Virtual Environment Best Practices

### Why Use Virtual Environments?

- **Dependency isolation**: Avoid conflicts between projects
- **Reproducible environments**: Consistent behavior across systems
- **Easy cleanup**: Delete the environment to remove everything
- **Version management**: Different projects can use different versions

### Creating a Virtual Environment

```bash
# Create virtual environment
python -m venv pacc-env

# Activate virtual environment
# Linux/macOS
source pacc-env/bin/activate

# Windows
pacc-env\Scripts\activate

# Install PACC CLI
pip install pacc-cli

# When done, deactivate
deactivate
```

### Using venv with PACC Projects

```bash
# Create project-specific environment
cd my-claude-project
python -m venv .venv
source .venv/bin/activate

# Install PACC CLI for this project
pip install pacc-cli

# Install project extensions
pacc install ./extensions/ --project
```

## Post-Installation Setup

### Configuring Your Shell

#### Bash/Zsh (Linux/macOS)

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# Add user bin to PATH if using --user installation
export PATH="$HOME/.local/bin:$PATH"

# Optional: Add PACC completions (if available)
# eval "$(pacc completions bash)"  # For bash
# eval "$(pacc completions zsh)"   # For zsh

# Optional: Set default PACC behavior
export PACC_DEFAULT_SCOPE="project"  # or "user"
```

#### PowerShell (Windows)

Add to your PowerShell profile:

```powershell
# Add user Scripts to PATH
$env:Path += ";$env:APPDATA\Python\Scripts"

# Optional: Set default PACC behavior
$env:PACC_DEFAULT_SCOPE = "project"
```

### Initial Configuration

```bash
# Check PACC installation
pacc --version

# View available commands
pacc --help

# Set up user-level Claude configuration (optional)
pacc init --user

# Set up project-level configuration
cd your-project
pacc init --project
```

## Verifying Installation

### Basic Verification

```bash
# Check version
pacc --version
# Expected output: pacc version 1.0.0

# Check help
pacc --help
# Should display all available commands

# Check Python integration
python -c "import pacc; print(pacc.__version__)"
# Should print version number
```

### Functional Test

Create a simple test to verify PACC works correctly:

```bash
# Create test hook
cat > test-hook.json << 'EOF'
{
  "name": "test-hook",
  "eventTypes": ["PreToolUse"],
  "commands": ["echo 'PACC is working!'"],
  "description": "Test hook for verification"
}
EOF

# Validate the hook
pacc validate test-hook.json --type hooks
# Expected: ✓ Validation successful

# Test installation (dry run)
pacc install test-hook.json --dry-run
# Should show what would be installed

# Clean up
rm test-hook.json
```

## Troubleshooting

### Common Installation Issues

#### Command Not Found

**Problem**: `bash: pacc: command not found`

**Solutions**:

1. **Check PATH**:
   ```bash
   # Find where pacc is installed
   pip show pacc-cli | grep Location
   
   # Add to PATH if needed
   export PATH="$PATH:/path/to/pacc/bin"
   ```

2. **Use python -m**:
   ```bash
   python -m pacc --version
   ```

3. **Reinstall with --user**:
   ```bash
   pip uninstall pacc-cli
   pip install --user pacc-cli
   ```

#### Permission Denied

**Problem**: `Permission denied` during installation

**Solutions**:

1. **Use --user flag**:
   ```bash
   pip install --user pacc-cli
   ```

2. **Use virtual environment**:
   ```bash
   python -m venv pacc-env
   source pacc-env/bin/activate
   pip install pacc-cli
   ```

3. **Use pipx or uv**:
   ```bash
   pipx install pacc-cli
   # or
   uv tool install pacc-cli
   ```

#### Python Version Error

**Problem**: `ERROR: pacc-cli requires Python >=3.8`

**Solution**: Update Python to 3.8 or higher:
```bash
# Check current version
python --version

# Install Python 3.8+ from python.org
# Or use your system package manager
```

#### Missing Dependencies

**Problem**: `ModuleNotFoundError: No module named 'yaml'`

**Solution**: Reinstall with dependencies:
```bash
pip install --upgrade pacc-cli
# or force reinstall
pip install --force-reinstall pacc-cli
```

### Platform-Specific Issues

#### Windows

- **Long Path Support**: Enable long path support in Windows 10/11
- **Execution Policy**: May need to adjust PowerShell execution policy
- **Antivirus**: Some antivirus software may flag Python scripts

#### macOS

- **System Python**: Avoid using system Python, install via Homebrew
- **PATH Priority**: Ensure Homebrew Python is first in PATH
- **Gatekeeper**: May need to allow execution in Security settings

#### Linux

- **Python Versions**: Some distros have python3 instead of python
- **Package Conflicts**: Use virtual environments to avoid conflicts
- **SELinux**: May need to adjust contexts for some operations

## Updating PACC CLI

### Updating with pip

```bash
# Update to latest version
pip install --upgrade pacc-cli

# Update to specific version
pip install pacc-cli==1.2.0

# Check current version
pacc --version
```

### Updating with uv

```bash
# Update to latest version
uv tool upgrade pacc-cli

# Reinstall specific version
uv tool uninstall pacc-cli
uv tool install pacc-cli==1.2.0
```

### Updating with pipx

```bash
# Update to latest version
pipx upgrade pacc-cli

# Force reinstall
pipx reinstall pacc-cli

# Install specific version
pipx install pacc-cli==1.2.0 --force
```

## Uninstalling

### Uninstalling with pip

```bash
# Uninstall pacc-cli
pip uninstall pacc-cli

# Remove user configuration (optional)
rm -rf ~/.claude/pacc/
```

### Uninstalling with uv

```bash
# Remove pacc-cli
uv tool uninstall pacc-cli
```

### Uninstalling with pipx

```bash
# Remove pacc-cli
pipx uninstall pacc-cli
```

### Complete Cleanup

To completely remove PACC CLI and all configurations:

```bash
# 1. Uninstall package
pip uninstall pacc-cli  # or use pipx/uv

# 2. Remove user configuration
rm -rf ~/.claude/pacc/

# 3. Remove any project configurations
# In each project directory:
rm -rf .claude/pacc/

# 4. Remove from PATH if manually added
# Edit ~/.bashrc, ~/.zshrc, or PowerShell profile
```

## Next Steps

Now that PACC CLI is installed:

1. **Read the Getting Started Guide**: Learn basic usage patterns
2. **Explore Available Commands**: Run `pacc --help`
3. **Install Your First Extension**: Follow the tutorials
4. **Join the Community**: Share feedback and get help

For more information:
- [Getting Started Guide](getting_started_guide.md)
- [Usage Documentation](usage_documentation.md)
- [API Reference](api_reference.md)
- [Troubleshooting Guide](troubleshooting_guide.md)

---

**Version**: 1.0.0 | **Last Updated**: December 2024