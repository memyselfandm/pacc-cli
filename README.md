<p align="center">
  <img src="https://img.shields.io/pypi/v/pacc-cli?style=flat-square&color=6366f1" alt="PyPI version">
  <img src="https://img.shields.io/pypi/pyversions/pacc-cli?style=flat-square" alt="Python versions">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/claude%20code-ready-6366f1?style=flat-square" alt="Claude Code Ready">
</p>

<h1 align="center">pacc</h1>
<h3 align="center">Ansible for Claude Code</h3>

<p align="center">
One CLI to install, configure, and sync your entire Claude Code environment.<br>
Stacks, plugins, fragments, extensions, and more — managed, versioned, and reproducible.
</p>

---

## The Problem

Setting up Claude Code from scratch is painful. MCP servers, hooks, commands, agents, settings, memory fragments — scattered across config files, shared via Slack snippets, and broken by the next teammate who "just changed one thing."

**PACC fixes this.** Package your entire Claude Code environment into shareable **stacks**, sync across machines in seconds, and onboard new developers in under a minute.

## Quick Start

```bash
# Install
pip install pacc-cli

# Install a stack (bundles MCP servers + hooks + commands + settings)
pacc stack install https://github.com/your-org/claude-fullstack

# Sync your project's Claude Code environment
pacc sync

# Check everything is healthy
pacc doctor
```

That's it. Zero to fully-configured in 30 seconds.

## Core Concepts

### Stacks — Your Entire Environment in One Command

A **stack** is a Git repo with a `stack.yaml` manifest that bundles everything Claude Code needs:

```yaml
# stack.yaml
name: fullstack-dev
version: "1.0.0"
description: "Full-stack development environment"

mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"

hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: "command"
          command: "echo 'Logging bash usage'"

commands:
  - source: "./commands/review.md"
    name: "code-review"

agents:
  - source: "./agents/reviewer.md"
    name: "reviewer"

settings:
  model: "sonnet"

fragments:
  - source: "./fragments/style-guide.md"
    name: "style-guide"
```

```bash
pacc stack install https://github.com/your-org/fullstack-stack
pacc stack list
pacc stack sync          # Idempotent — run it 100 times, same result
pacc stack export mystack ./output   # Export your current config as a stack
```

### Plugins — Full Ecosystem with Git Integration

```bash
pacc plugin install https://github.com/owner/claude-plugin
pacc plugin list --enabled
pacc plugin update
pacc plugin create          # Interactive wizard
pacc plugin search "code review"
```

### Memory Fragments — Persistent Context That Survives Sessions

```bash
pacc fragment install ./style-guide.md
pacc fragment list
pacc fragment sync          # Team-wide knowledge bases
```

### Doctor — Built-in Diagnostics

```bash
pacc doctor                 # Run all checks
pacc doctor --fix           # Auto-fix what can be fixed
pacc doctor --verbose       # Detailed output
```

Checks include: Claude Code installation, config file validity, MCP server health, plugin integrity, fragment references, environment variables, permissions, and more.

### Team Sync — Reproducible Environments

Share your environment via `pacc.json`:

```json
{
  "stacks": {
    "github.com/your-org/fullstack-stack": {
      "version": "v2.1.0",
      "scope": "project"
    }
  },
  "plugins": {
    "github.com/owner/code-review-plugin": {
      "version": "v1.0.0",
      "enabled": ["reviewer"]
    }
  },
  "fragments": {
    "style-guide": {
      "source": "./fragments/style-guide.md",
      "storage_type": "project"
    }
  }
}
```

```bash
# New developer joins the team:
git clone your-project && cd your-project
pacc sync                   # Everything installed. Done.
```

Version-locked via `pacc.lock.yaml` for reproducible builds:

```yaml
# pacc.lock.yaml (auto-generated)
stacks:
  fullstack-stack:
    source: "https://github.com/your-org/fullstack-stack"
    commit: "a1b2c3d4e5f6..."
    sha256: "abc123..."
    locked_at: "2026-03-30T12:00:00Z"
```

## All Commands

### Core
| Command | Description |
|---------|-------------|
| `pacc install <source>` | Install extensions from files, directories, or URLs |
| `pacc list` | List installed extensions |
| `pacc remove <name>` | Remove extensions |
| `pacc info <name>` | Show extension details |
| `pacc validate <source>` | Validate without installing |
| `pacc init` | Initialize PACC configuration |
| `pacc sync` | Sync from pacc.json (idempotent) |
| `pacc doctor` | Run diagnostics with optional `--fix` |

### Stacks
| Command | Description |
|---------|-------------|
| `pacc stack install <repo>` | Install a stack from a Git repository |
| `pacc stack list` | List installed stacks |
| `pacc stack info <name>` | Show stack details |
| `pacc stack remove <name>` | Remove a stack and all its components |
| `pacc stack sync` | Sync all stacks to desired state |
| `pacc stack export <name> <dir>` | Export current config as a reusable stack |

### Plugins
| Command | Description |
|---------|-------------|
| `pacc plugin install <repo>` | Install from Git repository |
| `pacc plugin list` | List installed plugins |
| `pacc plugin enable/disable <name>` | Toggle plugins |
| `pacc plugin update [name]` | Update plugins |
| `pacc plugin remove <name>` | Uninstall |
| `pacc plugin create` | Interactive creation wizard |
| `pacc plugin search <query>` | Search community plugins |
| `pacc plugin sync` | Sync from pacc.json |
| `pacc plugin convert <source>` | Convert extensions to plugins |
| `pacc plugin push <name> <repo>` | Publish to Git |
| `pacc plugin env setup` | Configure ENABLE_PLUGINS |

### Fragments
| Command | Description |
|---------|-------------|
| `pacc fragment install <source>` | Install memory fragments |
| `pacc fragment list` | List fragments |
| `pacc fragment remove <name>` | Remove with CLAUDE.md cleanup |
| `pacc fragment update` | Update from sources |
| `pacc fragment sync` | Team synchronization |
| `pacc fragment discover <repo>` | Find fragments in repos |
| `pacc fragment collection install` | Install fragment collections |

## Security

PACC takes security seriously:

- **170+ threat patterns** detected during installation
- **4-level sandbox isolation** for plugin execution
- **SHA-256 verification** of stack and plugin contents
- **Path traversal protection** with symlink and null-byte detection
- **Command injection prevention** on all inputs
- **Lockfile pinning** for reproducible, tamper-evident environments
- **Timestamped backups** before every config modification
- **Dry-run mode** on all mutating operations

## Safety Guarantees

Every operation in PACC is:
- **Idempotent** — run `pacc sync` any number of times, it always converges
- **Reversible** — timestamped backups before every modification
- **Previewable** — `--dry-run` on every mutating command
- **Clean** — removed stacks/plugins leave zero orphaned artifacts

## Installation

```bash
# PyPI (recommended)
pip install pacc-cli

# pipx (isolated)
pipx install pacc-cli

# From source
git clone https://github.com/memyselfandm/pacc-cli.git
cd pacc-cli/apps/pacc-cli
pip install -e .
```

**Requirements:** Python 3.8+, Git

## Claude Code Slash Commands

PACC registers as a Claude Code slash command provider:

```
/plugin install <repo>    /pl (list)    /pi (info)
/plugin enable <name>     /pe           /pd (disable)
/plugin update            /pu           /plugin create
```

## Development

```bash
make test          # Run test suite (>80% coverage)
make benchmark     # Performance benchmarks
make security      # Security test suite
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
<b>pacc</b> — stop copy-pasting configs. Start shipping.<br>
<a href="https://github.com/memyselfandm/pacc-cli">GitHub</a> ·
<a href="https://pypi.org/project/pacc-cli/">PyPI</a> ·
<a href="https://memyselfandm.github.io/pacc-cli/">Documentation</a>
</p>
