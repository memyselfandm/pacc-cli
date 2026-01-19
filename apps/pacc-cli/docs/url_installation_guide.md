# URL-Based Installation Guide

## Overview

PACC supports installing Claude Code extensions directly from URLs, making it easy to install packages from GitHub, GitLab, or any web server hosting extension archives.

## Quick Start

### Basic URL Installation

```bash
# Install from a GitHub release
pacc install https://github.com/user/extension/archive/main.zip

# Install from any HTTP/HTTPS URL
pacc install https://example.com/my-extension.tar.gz
```

### Installation Options

```bash
# Install to user directory instead of project
pacc install https://github.com/user/extension.zip --user

# Preview what would be installed (dry run)
pacc install https://github.com/user/extension.zip --dry-run

# Force installation even with validation warnings
pacc install https://github.com/user/extension.zip --force

# Don't extract archives (keep as single file)
pacc install https://github.com/user/extension.zip --no-extract
```

### URL-Specific Options

```bash
# Set maximum download size (in MB)
pacc install https://example.com/large-extension.zip --max-size 200

# Set download timeout (in seconds)
pacc install https://example.com/slow-server.zip --timeout 600

# Disable download caching
pacc install https://example.com/extension.zip --no-cache
```

## Supported Archive Formats

PACC can automatically extract the following archive formats:

- **ZIP** (`.zip`)
- **TAR** (`.tar`)
- **GZIP compressed TAR** (`.tar.gz`, `.tgz`)
- **BZIP2 compressed TAR** (`.tar.bz2`, `.tbz2`)

## Security Features

### URL Validation

PACC validates URLs for safety:

- Only HTTP and HTTPS protocols are allowed
- Dangerous protocols (javascript:, data:, file:) are blocked
- URL length limits prevent abuse
- Domain filtering can be configured

### Archive Security Scanning

Downloaded archives are automatically scanned for:

- **Path traversal attacks** (`../../../etc/passwd`)
- **Absolute paths** (`/etc/passwd`)
- **Suspicious file names** (system files, hidden files)
- **Executable files in system directories**

### Size Limits

- Default maximum download size: 100 MB
- Configurable via `--max-size` option
- Downloads are checked during transfer to prevent resource exhaustion

## Examples

### Installing from GitHub

```bash
# Install from main branch
pacc install https://github.com/user/claude-hooks/archive/main.zip

# Install from specific release
pacc install https://github.com/user/claude-agent/releases/download/v1.0.0/agent.zip

# Install from GitLab
pacc install https://gitlab.com/user/project/-/archive/main/project-main.tar.gz
```

### Installing with Custom Options

```bash
# Large extension with custom timeout
pacc install https://example.com/large-extension.zip \
  --max-size 500 \
  --timeout 900 \
  --user

# Multiple extensions with interactive selection
pacc install https://github.com/team/extensions/archive/main.zip \
  --interactive

# Preview installation
pacc install https://github.com/user/extension.zip \
  --dry-run \
  --verbose
```

### Installing Specific Extension Types

```bash
# Install only hooks from a multi-extension archive
pacc install https://github.com/user/mixed-extensions.zip --type hooks

# Install only agents
pacc install https://github.com/user/ai-agents.zip --type agents
```

## Caching

URL downloads are cached by default to improve performance:

- Cache location: `.claude/cache/` (project) or `~/.claude/cache/` (user)
- Cache key based on URL hash
- Automatic cache reuse for identical URLs
- Disable with `--no-cache` option

### Cache Management

```bash
# Install without using cache
pacc install https://example.com/extension.zip --no-cache

# Cache location
ls .claude/cache/  # Project-level cache
ls ~/.claude/cache/  # User-level cache
```

## Error Handling

### Common Issues

**Missing Dependencies:**
```
URL downloads require additional dependencies.
Install with: pip install aiohttp
```

**Download Too Large:**
```
Download failed: File size 157286400 exceeds limit 104857600
```
*Solution: Increase limit with `--max-size 200`*

**Download Timeout:**
```
Download failed: Download timeout
```
*Solution: Increase timeout with `--timeout 600`*

**Security Scan Failed:**
```
Download failed: Security scan failed: Path traversal attempt in: ../../../etc/passwd
```
*Solution: Contact extension author to fix security issues*

### Validation Errors

URL installations use the same validation as local installations:

```bash
# Show validation details
pacc install https://example.com/extension.zip --verbose

# Force installation despite warnings
pacc install https://example.com/extension.zip --force
```

## Advanced Usage

### Domain Restrictions

For security, you can configure PACC to only allow specific domains:

```python
# In your configuration (future feature)
{
  "url_sources": {
    "allowed_domains": ["github.com", "gitlab.com", "your-company.com"],
    "blocked_domains": ["suspicious.com"]
  }
}
```

### Custom Download Locations

```bash
# Download to specific project
cd /path/to/my-project
pacc install https://github.com/user/extension.zip --project

# Download to user directory from anywhere
pacc install https://github.com/user/extension.zip --user
```

### Batch Installation

Install multiple URLs in sequence:

```bash
# Install multiple extensions
pacc install https://github.com/user/hooks.zip
pacc install https://github.com/user/agents.zip
pacc install https://github.com/user/commands.zip
```

## Best Practices

### For Extension Authors

1. **Use stable URLs** for releases
2. **Provide checksums** for verification (future feature)
3. **Follow PACC packaging standards**
4. **Test with `--dry-run` before publishing**
5. **Keep archives under 100 MB when possible**

### For Extension Users

1. **Always preview with `--dry-run` first**
2. **Use `--verbose` to see what's being installed**
3. **Verify extension sources before installation**
4. **Use `--user` for personal extensions**
5. **Use `--project` for team-shared extensions**

### Security Guidelines

1. **Only install from trusted sources**
2. **Review validation output carefully**
3. **Use domain restrictions in enterprise environments**
4. **Keep PACC updated for latest security features**
5. **Report suspicious extensions to the community**

## Troubleshooting

### Network Issues

```bash
# Increase timeout for slow connections
pacc install https://example.com/extension.zip --timeout 900

# Check if URL is accessible
curl -I https://example.com/extension.zip
```

### Archive Issues

```bash
# Don't extract if having extraction problems
pacc install https://example.com/extension.zip --no-extract

# Check archive contents manually
curl -L https://example.com/extension.zip -o temp.zip
unzip -l temp.zip
```

### Permission Issues

```bash
# Install to user directory if project directory is read-only
pacc install https://example.com/extension.zip --user

# Check directory permissions
ls -la .claude/
```

## Integration with Existing Workflows

URL installation works seamlessly with existing PACC commands:

```bash
# Install from URL then list
pacc install https://github.com/user/extension.zip
pacc list

# Get info about installed extension
pacc info extension-name

# Remove URL-installed extension
pacc remove extension-name
```

The source URL is tracked in the extension metadata for future reference and updates.
