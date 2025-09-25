# PACC Package Installation Guide

This guide covers the installation options and packaging status for PACC (Package manager for Claude Code).

## Installation Options

### Option 1: Install from Wheel (Recommended)

1. **Build the wheel**:
   ```bash
   cd apps/pacc-cli/
   python scripts/build.py build --dist-type wheel
   ```

2. **Install the wheel**:
   ```bash
   pip install dist/pacc-1.0.0-py3-none-any.whl
   ```

3. **Verify installation**:
   ```bash
   pacc --version
   pacc --help
   ```

### Option 2: Editable Installation (Development)

For development work, install in editable mode:

```bash
cd apps/pacc-cli/
pip install -e .
```

This allows you to modify the source code and see changes immediately.

### Option 3: Install from Source Distribution

1. **Build source distribution**:
   ```bash
   python scripts/build.py build --dist-type sdist
   ```

2. **Install from source**:
   ```bash
   pip install dist/pacc-1.0.0.tar.gz
   ```

## Build Process and Scripts

### Build Script Usage

The `scripts/build.py` script provides comprehensive build automation:

```bash
# Install build dependencies
python scripts/build.py install-deps

# Build both wheel and source distributions
python scripts/build.py build

# Build only wheel
python scripts/build.py build --dist-type wheel

# Build only source distribution
python scripts/build.py build --dist-type sdist

# Check distributions with twine
python scripts/build.py check

# Test wheel installation
python scripts/build.py test
```

### Makefile Integration

Use the Makefile for common development tasks:

```bash
# Build all distributions
make build

# Build and test locally
make build-local

# Run comprehensive test suite
make test

# Check code quality
make quality

# Clean build artifacts
make clean
```

## Package Structure and Compatibility

### Cross-Platform Compatibility

PACC is designed to work across:
- **Windows** (Python 3.8+)
- **macOS** (Python 3.8+)
- **Linux** (Python 3.8+)

The package structure ensures compatibility through:
- POSIX-style paths in metadata
- Cross-platform file handling
- Universal wheel format (`py3-none-any`)

### Dependencies

**Core Dependencies (Required)**:
- `PyYAML>=6.0` - YAML parsing for agents and commands

**Optional Dependencies**:
- `url` extras: `aiohttp>=3.8.0`, `aiofiles>=0.8.0` - For URL installations
- `dev` extras: `pytest`, `mypy`, `ruff`, etc. - For development

**Install with optional dependencies**:
```bash
# Install with URL support
pip install pacc-cli[url]

# Install with all development tools
pip install pacc-cli[dev]
```

## Installation Validation

### Verify Installation

After installation, verify PACC is working correctly:

```bash
# Check version
pacc --version

# View available commands
pacc --help

# Test validation functionality
echo '{"name": "test", "eventTypes": ["PreToolUse"], "commands": ["echo test"]}' > test-hook.json
pacc validate test-hook.json --type hooks
```

### Test Extension Workflow

Create a minimal test to verify functionality:

```bash
# Create test directory
mkdir test-pacc-install
cd test-pacc-install

# Create a simple hook
cat > simple-hook.json << 'EOF'
{
  "name": "simple-hook",
  "eventTypes": ["PreToolUse"],
  "commands": ["echo 'Hook executed successfully'"],
  "description": "Simple test hook"
}
EOF

# Validate the hook
pacc validate simple-hook.json --type hooks

# Test dry-run installation (safe)
pacc install simple-hook.json --dry-run
```

## Troubleshooting Installation

### Common Issues

**Python Version Error**:
```
ERROR: This package requires Python >=3.8
```
**Solution**: Upgrade to Python 3.8 or higher.

**Permission Errors**:
```
ERROR: Could not install packages due to an EnvironmentError
```
**Solution**: Use `--user` flag or virtual environment:
```bash
pip install --user pacc-cli
# OR
python -m venv pacc-env
source pacc-env/bin/activate  # Linux/macOS
# pacc-env\Scripts\activate  # Windows
pip install pacc-cli
```

**Missing Dependencies**:
```
ModuleNotFoundError: No module named 'yaml'
```
**Solution**: Install with all dependencies:
```bash
pip install pacc-cli[dev]
```

### Build Issues

**Missing Build Tools**:
```
ERROR: Failed building wheel for pacc
```
**Solution**: Install build dependencies:
```bash
python scripts/build.py install-deps
```

**TOML Parsing Errors**:
```
ModuleNotFoundError: No module named 'tomli'
```
**Solution**: Install tomli for Python < 3.11:
```bash
pip install tomli
```

## Production Deployment

### System Requirements

- **Python**: 3.8 or higher
- **Memory**: 50MB minimum for basic operations
- **Storage**: 10MB for package installation
- **Network**: Optional (for URL-based installations)

### Performance Characteristics

- **File Scanning**: >4,000 files/second
- **Validation**: <50ms per extension
- **Installation**: <5 seconds for typical extensions
- **Memory Usage**: <20MB during operations

### Security Considerations

PACC includes comprehensive security measures:
- Path traversal protection
- Command injection prevention
- File content scanning
- Sandboxed validation
- Input sanitization

## Support and Documentation

### Documentation Structure

```
docs/
├── api_reference.md      # Complete API documentation
├── security_guide.md     # Security best practices
├── package_installation_guide.md  # This guide
└── slash_commands_guide.md        # Claude Code integration
```

### Getting Help

1. **Check documentation**: Review the comprehensive guides in `docs/`
2. **Run with verbose output**: Use `-v` flag for detailed information
3. **Check logs**: PACC maintains operation logs for debugging
4. **Review test examples**: See `tests/` directory for usage patterns

### Version Information

- **Current Version**: 1.0.0
- **Minimum Python**: 3.8
- **Package Format**: Universal wheel
- **Status**: Production ready

---

**Next Steps**: After installation, see the [API Reference](api_reference.md) for detailed usage instructions and the [Security Guide](security_guide.md) for best practices.
