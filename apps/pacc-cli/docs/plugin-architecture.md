# Plugin System Architecture

This document describes the technical architecture of PACC's Claude Code plugin management system, detailing component interactions, data flows, and implementation patterns.

## System Overview

The PACC plugin system provides comprehensive management for Claude Code plugins through a layered architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
├─────────────────────────────────────────────────────────────┤
│  Plugin Management Layer (Configuration + Repository)       │
├─────────────────────────────────────────────────────────────┤
│         Discovery & Validation Layer                       │
├─────────────────────────────────────────────────────────────┤
│            Core Infrastructure Layer                       │
├─────────────────────────────────────────────────────────────┤
│                Claude Code Integration                      │
└─────────────────────────────────────────────────────────────┘
```

## Core Architecture Principles

### 1. Atomic Operations
All configuration changes are atomic with automatic rollback on failure:
- Backup creation before modifications
- Temporary files for staging changes  
- Transactional multi-file updates
- Automatic cleanup on success/failure

### 2. Component Isolation
Each major component is independently testable and replaceable:
- Configuration management (config.json, settings.json)
- Repository management (Git operations, validation)
- Plugin discovery (scanning, metadata extraction)
- CLI interface (command parsing, user interaction)

### 3. Cross-Platform Compatibility
Consistent behavior across operating systems:
- Path normalization and validation
- File system operation abstractions
- Git command execution with proper timeouts
- Configuration file format standardization

### 4. Performance Optimization
Fast operations suitable for interactive use:
- Plugin discovery < 1 second for typical repositories
- Configuration updates < 500ms
- Bulk operations with transaction batching
- Lazy loading of plugin metadata

## Component Architecture

### Configuration Management (`pacc.plugins.config`)

**Primary Class**: `PluginConfigManager`

**Responsibilities**:
- Manage `~/.claude/plugins/config.json` (repository tracking)
- Manage `~/.claude/settings.json` enabledPlugins section
- Provide atomic configuration operations
- Handle backup/restore functionality
- Support team configuration synchronization

**Key Features**:
```python
class PluginConfigManager:
    # Core operations
    def add_repository(owner: str, repo: str) -> bool
    def remove_repository(owner: str, repo: str) -> bool
    def enable_plugin(repo: str, plugin_name: str) -> bool
    def disable_plugin(repo: str, plugin_name: str) -> bool
    
    # Advanced features
    def sync_team_config(pacc_config: dict) -> dict
    @contextmanager
    def transaction() -> ContextManager
    def backup_config(file_path: Path) -> BackupInfo
    def restore_config(backup_path: Path) -> bool
```

**Configuration File Formats**:

`config.json` structure:
```json
{
  "repositories": {
    "owner/repo": {
      "lastUpdated": "2025-08-18T10:30:00Z",
      "commitSha": "abc123def456...",
      "plugins": ["plugin1", "plugin2"],
      "url": "https://github.com/owner/repo"
    }
  }
}
```

`settings.json` integration:
```json
{
  "enabledPlugins": {
    "owner/repo": ["plugin1", "plugin2"]
  },
  // ... other Claude Code settings
}
```

### Repository Management (`pacc.plugins.repository`)

**Primary Class**: `PluginRepositoryManager`

**Responsibilities**:
- Git repository operations (clone, update, rollback)
- Repository structure validation
- Version tracking and conflict detection
- Plugin discovery coordination
- Integration with configuration management

**Key Features**:
```python
class PluginRepositoryManager:
    def clone_plugin(repo_url: str) -> PluginRepo
    def update_plugin(repo_path: Path) -> UpdateResult
    def rollback_plugin(repo_path: Path, commit_sha: str) -> bool
    def get_plugin_info(repo_path: Path) -> PluginInfo
    def validate_repository_structure(repo_path: Path) -> ValidationResult
```

**Git Integration**:
- Uses subprocess for Git commands with proper timeout handling
- Implements Claude Code's `git pull --ff-only` update strategy  
- Provides conflict detection and resolution options
- Supports both HTTPS and SSH repository URLs

**Repository Structure Validation**:
```python
def validate_repository_structure(repo_path: Path) -> ValidationResult:
    """Validates repository contains valid plugin structures:
    - At least one plugin.json file
    - Plugin directories with valid manifests
    - Component directories (commands/, agents/, hooks/)
    """
```

### Plugin Discovery (`pacc.plugins.discovery`)

**Primary Classes**: `PluginScanner`, `PluginManifestParser`, `PluginMetadataExtractor`

**Responsibilities**:
- Scan repositories for plugin structures
- Parse and validate plugin.json manifests
- Extract metadata from commands, agents, hooks
- Generate namespaced component identifiers
- Provide plugin information for selection

**Discovery Process**:
```
1. Repository Scan
   ├─ Find plugin.json files recursively
   ├─ Validate plugin directory structure
   └─ Create PluginInfo objects

2. Manifest Processing
   ├─ Parse JSON with syntax validation
   ├─ Validate against schema (name, version, author)
   └─ Extract metadata for plugin management

3. Component Discovery
   ├─ Scan commands/ for .md files
   ├─ Scan agents/ for .md files
   ├─ Scan hooks/ for hooks.json files
   └─ Extract frontmatter and metadata

4. Namespace Generation
   ├─ Commands: plugin-name:subdir:command-name
   ├─ Agents: plugin-name:subdir:agent-name
   └─ Hooks: plugin-name:hook-file-name
```

**Metadata Extraction**:
```python
class PluginMetadataExtractor:
    def extract_command_metadata(command_path: Path) -> dict
    def extract_agent_metadata(agent_path: Path) -> dict
    def extract_hooks_metadata(hooks_path: Path) -> dict
```

Each extractor handles:
- YAML frontmatter parsing
- Template variable detection (`$ARGUMENTS`, `${CLAUDE_PLUGIN_ROOT}`)
- Error collection and validation
- Component-specific schema validation

### CLI Integration (`pacc.cli`)

**Plugin Commands**:
- `pacc plugin install <repo_url>` - Repository installation with discovery
- `pacc plugin list [--repo] [--type] [--enabled-only]` - Plugin listing
- `pacc plugin enable <plugin> [--repo]` - Plugin activation
- `pacc plugin disable <plugin> [--repo]` - Plugin deactivation

**Command Flow Example** (`plugin install`):
```
1. URL Validation
   ├─ Parse repository URL (GitHub, GitLab, etc.)
   ├─ Validate Git URL format
   └─ Extract owner/repo information

2. Repository Installation
   ├─ Clone repository to ~/.claude/plugins/repos/owner/repo/
   ├─ Validate repository structure
   └─ Add to config.json

3. Plugin Discovery
   ├─ Scan for plugins in repository
   ├─ Parse plugin manifests
   ├─ Extract component metadata
   └─ Generate selection options

4. Plugin Selection & Activation
   ├─ Display discovered plugins (--interactive)
   ├─ User selection or auto-enable (--enable)
   ├─ Update settings.json enabledPlugins
   └─ Confirm successful installation
```

## Data Flow Architecture

### Installation Flow

```
User Command → URL Validation → Git Clone → Structure Validation
     ↓
Plugin Discovery → Manifest Parsing → Component Extraction
     ↓  
User Selection → Configuration Update → Verification
     ↓
Success/Error Response
```

### Discovery Flow

```
Repository Path → Directory Scan → Plugin Detection
     ↓
Manifest Parsing → Schema Validation → Metadata Collection
     ↓
Component Scanning → Frontmatter Parsing → Namespace Generation
     ↓
PluginInfo Assembly → Validation Results → Selection Options
```

### Configuration Flow

```
Configuration Request → Backup Creation → Validation
     ↓
Atomic File Operations → Configuration Update → Verification
     ↓
Success: Cleanup Backups | Failure: Rollback → Result
```

## Integration with Claude Code

### File System Integration

**Plugin Directory Structure**:
```
~/.claude/plugins/
├── config.json                 # Managed by PACC
├── repos/                      # Git repositories
│   └── owner/
│       └── repo/
│           └── plugin-name/
│               ├── plugin.json
│               ├── commands/
│               ├── agents/
│               └── hooks/
└── backups/                    # Configuration backups
```

**Claude Code Integration Points**:
1. **Configuration Files**: PACC manages Claude Code's native config files
2. **Plugin Loading**: Claude Code loads plugins from PACC-managed directories
3. **Environment Variables**: PACC can set `ENABLE_PLUGINS=1` for activation
4. **Update Behavior**: PACC respects Claude Code's `git pull --ff-only` strategy

### Plugin Component Types

**Commands** (`.md` files with YAML frontmatter):
```markdown
---
description: Command description
allowed-tools: [Read, Write, Edit]
argument-hint: "usage hint"
model: claude-3-opus
---

Command template with $ARGUMENTS and ${CLAUDE_PLUGIN_ROOT}
```

**Agents** (`.md` files with agent-specific frontmatter):
```markdown
---
name: Agent Display Name
description: Agent purpose
tools: [Read, Write, Bash]
color: cyan
---

System prompt for the specialized agent
```

**Hooks** (`hooks.json` with event definitions):
```json
{
  "hooks": [
    {
      "type": "PreToolUse|PostToolUse|SessionStart|SessionEnd|UserPromptSubmit|Notification",
      "matcher": { "toolName": "Bash", "argumentPattern": "pattern" },
      "action": { "command": "echo 'hook triggered'", "timeout": 1000 }
    }
  ]
}
```

## Error Handling & Recovery

### Error Categories

1. **Configuration Errors**:
   - Invalid JSON syntax in config files
   - Schema validation failures
   - File permission issues
   - Atomic operation failures

2. **Repository Errors**:
   - Git operation failures (clone, pull, reset)
   - Invalid repository URLs
   - Network connectivity issues
   - Repository structure violations

3. **Plugin Errors**:
   - Invalid plugin.json manifests
   - Missing required components
   - YAML frontmatter syntax errors
   - Namespace conflicts

4. **System Errors**:
   - Disk space limitations
   - File system permissions
   - Process timeout issues
   - Dependency unavailability

### Recovery Strategies

**Automatic Recovery**:
- Configuration backup/restore on failures
- Atomic operations with rollback
- Retry mechanisms for transient failures
- Graceful degradation for partial failures

**User-Initiated Recovery**:
- Manual backup restoration commands
- Repository re-cloning options
- Configuration validation tools
- Repair utilities for corrupted state

## Performance Characteristics

### Benchmarks

Based on integration test results:

- **Plugin Discovery**: < 1 second for 50+ plugins
- **Configuration Updates**: < 500ms for typical operations  
- **Repository Cloning**: Network-dependent, with 5-minute timeout
- **Bulk Operations**: < 1 second for 10+ plugin enable/disable

### Optimization Strategies

1. **Lazy Loading**: Plugin metadata loaded only when needed
2. **Caching**: Repository information cached between operations
3. **Parallel Operations**: Independent operations run concurrently  
4. **Efficient Scanning**: Optimized directory traversal patterns
5. **Incremental Updates**: Only update changed configurations

### Memory Usage

- **Base Memory**: ~10MB for core components
- **Per Plugin**: ~1KB metadata per plugin
- **Repository Cache**: ~100KB per repository
- **Peak Usage**: ~50MB during large repository operations

## Security Model

### Trust Boundaries

1. **Local System**: PACC runs with user permissions
2. **Configuration Files**: Protected by file system permissions
3. **Git Repositories**: Public/private repository access via Git
4. **Plugin Execution**: Plugins run with full Claude Code permissions

### Security Features

**Input Validation**:
- URL validation for repository sources
- JSON schema validation for configurations
- Path traversal protection
- Command injection prevention

**Atomic Operations**:
- Configuration changes are atomic
- Backup creation before modifications
- Rollback capabilities on failures
- Temporary file cleanup

**Plugin Safety**:
- Repository structure validation
- Manifest schema enforcement  
- Component syntax checking
- Hook command validation (basic)

### Security Considerations

**Plugin Trust**:
- Plugins execute with full tool access
- Hook commands run arbitrary shell commands
- No plugin sandboxing currently implemented
- User must trust plugin sources

**Recommendations**:
- Review plugin code before installation
- Use trusted plugin sources
- Monitor plugin behavior in verbose mode
- Regular backup of plugin configurations

## Testing Architecture

### Test Categories

1. **Unit Tests**: Individual component testing
   - Configuration management operations
   - Repository validation logic
   - Plugin discovery mechanisms
   - CLI command parsing

2. **Integration Tests**: Component interaction testing
   - End-to-end workflow validation
   - Cross-component communication
   - Error scenario handling
   - Performance validation

3. **End-to-End Tests**: Complete user journey testing
   - Installation workflows
   - Team synchronization
   - Configuration management
   - Recovery scenarios

### Test Infrastructure

**Mock Strategies**:
- Git operation mocking for offline testing
- File system mocking for cross-platform testing
- Network operation mocking for reliability
- Time-based mocking for consistent behavior

**Test Data Management**:
- Temporary directory creation/cleanup
- Mock plugin repository generation
- Configuration file templates
- Test isolation between runs

## Extension Points

### Plugin Types

Current support:
- **Commands**: Markdown with YAML frontmatter
- **Agents**: Markdown with agent frontmatter  
- **Hooks**: JSON event definitions

Future extensibility:
- **Templates**: Project scaffolding templates
- **Themes**: Claude Code appearance customization
- **Integrations**: External tool connections
- **Workflows**: Multi-step automation

### Configuration Extensions

**Team Configuration** (`pacc.json`):
```json
{
  "plugins": {
    "owner/repo": ["plugin1", "plugin2"]
  },
  "settings": {
    "auto_update": true,
    "version_pinning": false
  }
}
```

**Plugin Dependencies** (future):
```json
{
  "dependencies": {
    "required": ["owner/base-plugin"],
    "optional": ["owner/helper-plugin"],
    "conflicts": ["owner/incompatible-plugin"]
  }
}
```

### API Extensions

Future API enhancements:
- Plugin marketplace integration
- Dependency resolution system
- Version management and rollback
- Plugin signing and verification
- Remote configuration management

This architecture provides a solid foundation for current plugin management needs while maintaining extensibility for future enhancements.