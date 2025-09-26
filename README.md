# `pacc`: Package Manager for Claude Code

## Overview
`pacc` is a comprehensive Python CLI tool for managing Claude Code extensions and plugins.

`pacc` can manage:
- **Plugins** (NEW): Full plugin ecosystem with Git integration
- Hooks
- Slash Commands
- (Sub-)Agents
- MCP Servers

at the global level (~/.claude) or project level (`<project-root>/.claude`).

### Key Features
1. **Plugin Management**: Install, update, and manage Claude Code plugins from Git repositories
2. **Extension Installation**: Install extensions from source files or folders
3. **Safe Configuration**: Atomic config file modifications with rollback support
4. **Team Collaboration**: Share plugin configurations via `pacc.json`
5. **Plugin Development**: Create, convert, and publish plugins
6. **Security**: Comprehensive validation and threat detection

## Installation
### Prerequisites
- Python 3.8 or higher
- Git (for plugin management)
- Claude Code with ENABLE_PLUGINS=1 environment variable

### Installation
```bash
# Install from PyPI (recommended)
pip install pacc-cli

# Or install with pipx for isolated environment
pipx install pacc-cli

# For development (from source)
git clone https://github.com/memyselfandm/pacc-cli.git
cd pacc-cli/apps/pacc-cli
pip install -e .
```

## Plugin Management (NEW)

### Core Plugin Commands
```bash
# Install a plugin from Git repository
pacc plugin install https://github.com/owner/plugin-repo
pacc plugin install git@github.com:owner/plugin-repo.git

# List installed plugins
pacc plugin list
pacc plugin list --enabled  # Show only enabled plugins

# Get plugin information
pacc plugin info plugin-name

# Enable/disable plugins
pacc plugin enable plugin-name
pacc plugin disable plugin-name

# Update plugins
pacc plugin update  # Update all plugins
pacc plugin update plugin-name  # Update specific plugin

# Remove plugins
pacc plugin remove plugin-name
```

### Team Collaboration
```bash
# Sync plugins from pacc.json
pacc plugin sync

# Example pacc.json:
{
  "plugins": {
    "github.com/owner/repo": {
      "version": "v1.0.0",
      "enabled": ["plugin1", "plugin2"]
    }
  }
}
```

### Plugin Development
```bash
# Create a new plugin interactively
pacc plugin create

# Convert existing extensions to plugins
pacc plugin convert my-hook.json
pacc plugin convert ./extensions-folder

# Push local plugin to Git
pacc plugin push my-plugin https://github.com/myuser/my-plugin
```

### Plugin Discovery
```bash
# Search for plugins
pacc plugin search "code review"
pacc plugin search --type command
pacc plugin search --sort popularity
```

### Environment Setup
```bash
# Set up ENABLE_PLUGINS environment variable
pacc plugin env setup

# Check environment status
pacc plugin env status

# Reset environment
pacc plugin env reset
```

## Extension Management (Original Features)

### Basic Usage
```bash
# Install extensions from a source file or folder
pacc install ./my-hook.json --project
pacc install ./my-mcp-server --user
pacc install ./team-agents.md --project
pacc install ./custom-commands.md --project

# Validate extensions before installing
pacc validate ./extension-folder --type hooks

# Interactive selection from multi-item sources
pacc install ./multiple-extensions/ --interactive
```

### Source Folder Setup
Organize your extensions in a folder structure:
```
extensions/
├── hooks/
│   ├── pre-commit.json
│   └── post-tool.json
├── agents/
│   ├── code-reviewer.md
│   └── test-writer.md
├── commands/
│   └── git-utils.md
└── mcp/
    └── server-config.json
```

## Slash Commands Integration

PACC provides Claude Code slash commands for quick access:
- `/plugin install <repo>` - Quick plugin installation
- `/plugin list` or `/pl` - List installed plugins
- `/plugin info <name>` or `/pi` - Plugin information
- `/plugin enable <name>` - Enable a plugin
- `/plugin disable <name>` - Disable a plugin
- `/plugin update` - Update plugins
- `/plugin create` - Create new plugin
- `/plugin search <query>` - Search for plugins

## Security Features

PACC includes comprehensive security measures:
- **Validation**: All plugins and extensions are validated before installation
- **Threat Detection**: 170+ dangerous patterns detected
- **Sandboxing**: 4 levels of plugin isolation
- **Path Protection**: Prevention of path traversal attacks
- **Command Scanning**: Detection of malicious commands

## Development

### Running Tests
```bash
# Run all tests
make test

# Run with coverage
make coverage

# Run performance benchmarks
make benchmark

# Run security tests
make security
```

### Project Structure
```
pacc/
├── apps/pacc-cli/          # Main CLI application
│   ├── pacc/               # Core package modules
│   │   ├── core/           # File utilities, path handling
│   │   ├── plugins/        # Plugin management system
│   │   ├── validators/     # Extension validators
│   │   └── ...
│   └── tests/              # Comprehensive test suite
└── ai_docs/                # Documentation and PRDs
```

## Contributing
Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to PACC.

## License
MIT License - see [LICENSE](LICENSE) for details.

## Support
- Report issues: [GitHub Issues](https://github.com/yourusername/pacc/issues)
- Documentation: [Full Documentation](https://docs.pacc.dev)
- Discord: [Join our community](https://discord.gg/pacc)
