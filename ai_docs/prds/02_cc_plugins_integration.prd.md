# PRD: Integrating the Claude Code Plugin system with `pacc`

## Overview
As of 8/16/25 I've been made aware that Claude Code has an undocumented plugin system. A member of the CC discord generated some documentation of the plugin api from the CC source code.

That documentation is at:
@ai_docs/knowledge/claude-code-plugins-api-reference.md

This epic will cover a comprehensive integration of that plugin api into pacc-cli

## Key Features

### 1. Plugin Repository Management
- **Install plugins from Git repositories** using PACC's existing Git support
- **Automatic repository structure creation** at `~/.claude/plugins/repos/owner/repo/`
- **Repository tracking** via automated config.json management
- **Version control** with commit SHA tracking and rollback capabilities
- **Update management** with diff preview before pulling changes

### 2. Plugin Discovery & Search
- **Plugin marketplace** functionality (community registry)
- **Local plugin scanning** to discover unregistered plugins
- **Search by capability** (commands, agents, hooks)
- **Plugin metadata indexing** from plugin.json manifests
- **Dependency resolution** for plugins requiring other plugins

### 3. Plugin Conversion & Migration
- **Extension to plugin conversion** from existing installations
- **Automatic plugin structure generation** from loose files
- **Git repository initialization** and push for converted plugins
- **Metadata inference** from existing extension files
- **Batch conversion** for multiple extensions at once

### 4. Configuration Management
- **Automated config.json updates** when installing/removing plugins
- **Smart settings.json merging** for enabledPlugins section
- **Plugin enable/disable** without removal
- **Configuration backup** before modifications
- **Atomic operations** with rollback on failure

### 5. Plugin Development Support
- **Plugin scaffolding** commands to create new plugins
- **Plugin packaging** from existing commands/agents/hooks
- **Local plugin testing** before publishing
- **Plugin validation** during development
- **Template generation** for common plugin patterns

### 6. Team Collaboration
- **Project plugin configuration** via pacc.json
- **Team plugin synchronization** across developers
- **Plugin version pinning** for consistency
- **Private plugin registry** support for organizations
- **Plugin approval workflows** for enterprise teams

### 7. Enhanced CLI Commands
- `pacc plugin install owner/repo` - Install from Git repository
- `pacc plugin convert <extension>` - Convert existing extension to plugin
- `pacc plugin list` - List installed plugins with status
- `pacc plugin enable/disable <plugin>` - Toggle plugin activation
- `pacc plugin update <plugin>` - Update specific plugin
- `pacc plugin create` - Scaffold new plugin project
- `pacc plugin push <plugin> <repo>` - Push local plugin to Git
- `pacc plugin search <query>` - Search plugin marketplace

### 8. Slash Commands Integration
- `/plugin install <repo>` - Quick plugin installation
- `/plugin list` - Show installed plugins
- `/plugin convert` - Interactive conversion wizard
- `/plugin enable <name>` - Enable a plugin
- `/plugin disable <name>` - Disable a plugin
- `/plugin update` - Update all plugins
- `/plugin create` - Create new plugin interactively

### 9. Environment Management
- **Automatic ENABLE_PLUGINS=1** setting when any plugin is installed
- **Environment variable persistence** across sessions
- **Shell profile updates** for permanent configuration
- **Cross-platform env management** (Windows/Mac/Linux)
- **Smart detection** of existing ENABLE_PLUGINS setting

## Technical Design

### System Architecture

#### Core Design Principles
1. **Leverage Existing Infrastructure**: Build on PACC's existing Git integration, validators, and UI components
2. **Claude Code Compatibility**: Strict adherence to CC's plugin directory structure and configuration formats
3. **Zero Manual Configuration**: All plugin management should be automated, no manual JSON editing required
4. **Atomic Operations**: All configuration changes must be transactional with rollback capability
5. **Cross-Platform Support**: Consistent behavior across Windows, macOS, and Linux

#### Integration Architecture

```
Claude Code Plugin System
├── Native Plugin Loader (CC)
│   ├── Reads: ~/.claude/plugins/config.json
│   ├── Loads: ~/.claude/plugins/repos/*/*
│   └── Enables: via settings.json
│
└── PACC Plugin Manager (New)
    ├── Repository Management
    │   ├── Git operations (clone/pull/push)
    │   ├── Version control (SHA tracking)
    │   └── Conflict resolution
    ├── Configuration Management
    │   ├── config.json manipulation
    │   ├── settings.json enabledPlugins
    │   └── pacc.json team configs
    └── Extension Services
        ├── Plugin conversion
        ├── Environment setup
        └── Slash commands
```

#### Data Flow

1. **Installation Flow**:
   ```
   User Command → Git Clone → Update config.json → Update settings.json → Notify CC
   ```

2. **Conversion Flow**:
   ```
   Scan Extensions → Generate Manifest → Create Structure → Init Git → Push Remote
   ```

3. **Team Sync Flow**:
   ```
   Read pacc.json → Compare Local → Clone Missing → Update Configs → Enable Plugins
   ```

### Key Technical Components

#### 1. Plugin Repository Manager
- **Purpose**: Handle all Git operations for plugin repositories
- **Key Responsibilities**:
  - Clone repositories to `~/.claude/plugins/repos/owner/repo/`
  - Track commits via SHA for version control
  - Execute `git pull --ff-only` matching CC's auto-update behavior
  - Handle merge conflicts and provide rollback options

#### 2. Configuration Manager
- **Purpose**: Manage CC's configuration files atomically
- **Key Files**:
  - `~/.claude/plugins/config.json` - Repository tracking
  - `~/.claude/settings.json` - Plugin enable/disable states
  - `./pacc.json` - Team plugin requirements
- **Safety Features**:
  - Backup before modification
  - Atomic writes with temp files
  - Validation before committing changes

#### 3. Plugin Converter
- **Purpose**: Transform existing extensions into shareable plugins
- **Conversion Mapping**:
  - `.claude/hooks.json` → `plugin/hooks/hooks.json`
  - `.claude/commands/*.md` → `plugin/commands/*.md`
  - `.claude/agents/*.md` → `plugin/agents/*.md`
- **Manifest Generation**: Auto-create plugin.json from metadata

#### 4. Environment Manager
- **Purpose**: Ensure ENABLE_PLUGINS=1 is set when needed
- **Strategies**:
  - Session-only: Export for current session
  - Persistent: Update shell profiles (.bashrc, .zshrc, etc.)
  - Windows: Set user/system environment variables
- **Smart Detection**: Check existing settings to avoid duplicates

### Directory Structure

```
~/.claude/
├── plugins/
│   ├── config.json                 # Managed by PACC
│   └── repos/                      # Managed by PACC
│       └── owner/
│           └── repo/
│               └── plugin-name/
│                   ├── plugin.json
│                   ├── commands/
│                   ├── agents/
│                   └── hooks/
├── settings.json                    # enabledPlugins managed by PACC
└── commands/
    └── plugin/                      # PACC slash commands
        ├── install.md
        ├── list.md
        └── convert.md
```

### Module Architecture

```
pacc/
├── cli.py                     # Main CLI with all commands including plugin commands
├── plugins/                   # New plugin subsystem
│   ├── __init__.py
│   ├── repository.py         # Git repository management
│   ├── discovery.py          # Plugin discovery engine
│   ├── config.py             # Plugin configuration management
│   ├── converter.py          # Extension to plugin converter
│   ├── environment.py        # Environment variable management
│   └── marketplace.py        # Marketplace integration (future)
```

**Implementation Note**: Plugin commands (`pacc plugin install`, `pacc plugin list`, etc.) will be implemented as additional subcommands in the existing `cli.py` file, following the same pattern as existing commands (install, list, remove, etc.).

### API Contracts

#### Plugin Repository Manager
```python
class PluginRepositoryManager:
    def clone_plugin(repo_url: str, target_dir: Path) -> PluginRepo
    def update_plugin(repo_path: Path) -> UpdateResult
    def get_plugin_info(repo_path: Path) -> PluginInfo
    def rollback_plugin(repo_path: Path, commit_sha: str) -> bool
```

#### Configuration Manager
```python
class PluginConfigManager:
    def add_repository(owner: str, repo: str, metadata: dict) -> bool
    def remove_repository(owner: str, repo: str) -> bool
    def enable_plugin(repo: str, plugin_name: str) -> bool
    def disable_plugin(repo: str, plugin_name: str) -> bool
    def sync_team_config(pacc_config: dict) -> SyncResult
```

#### Plugin Converter
```python
class PluginConverter:
    def scan_extensions() -> List[Extension]
    def convert_to_plugin(extension: Extension, name: str) -> Plugin
    def generate_manifest(plugin_data: dict) -> dict
    def push_to_git(plugin: Plugin, repo_url: str) -> bool
```

### Integration Points

1. **Leverage Existing PACC Components**:
   - Use existing Git integration for repository management
   - Utilize existing UI components for interactive selection
   - Apply existing file utilities for cross-platform support
   - Extend existing CLI framework for plugin commands

2. **Adopt Claude Code Conventions**:
   - Follow plugin directory structure (~/.claude/plugins/)
   - Use plugin.json manifest format
   - Implement namespacing convention (plugin:subdir:name)
   - Support template variables (${CLAUDE_PLUGIN_ROOT}, $ARGUMENTS)

3. **Bridge the Gaps**:
   - Provide missing management commands that CC lacks
   - Enable team collaboration through pacc.json
   - Add conversion tools for existing extensions
   - Automate environment configuration

## Notes

### Critical Integration Insights

1. **Plugin System is Experimental**: Currently requires ENABLE_PLUGINS=1 environment variable. PACC should detect this and prompt users to enable if needed.

2. **No Built-in Management**: Claude Code has zero plugin management commands - this is PACC's primary value proposition for plugin users.

3. **Repository Structure**: Plugins live in `~/.claude/plugins/repos/owner/repo/` with potential multiple plugins per repository.

4. **Configuration Duality**:
   - `config.json` tracks repositories (not individual plugins)
   - `settings.json` enables specific plugins from those repositories
   - PACC must manage both files correctly

5. **Auto-update Behavior**: CC runs `git pull --ff-only` on startup for registered repos. PACC should respect this and handle conflicts gracefully.

6. **Component Types**:
   - Commands and Agents use Markdown with YAML frontmatter
   - Hooks use JSON configuration
   - All support nested directory structures with namespacing

7. **Security Concerns**:
   - No sandboxing for plugin execution
   - Hooks execute arbitrary shell commands
   - Plugins have full tool access
   - PACC's security scanning becomes critical

8. **Validation Requirements**:
   - Must validate plugin.json schema
   - Must check frontmatter in .md files
   - Must verify hook action commands
   - Should scan for dangerous patterns

9. **User Experience Improvements**:
   - PACC can provide the missing UI for plugin management
   - Interactive selection from multi-plugin repositories
   - Search and discovery features absent in CC
   - Version management and rollback capabilities

10. **Extension Conversion Strategy**:
    - Map hooks.json → plugin/hooks/hooks.json
    - Map .claude/commands/* → plugin/commands/*
    - Map .claude/agents/* → plugin/agents/*
    - Auto-generate plugin.json from metadata
    - Preserve original extension functionality

11. **Environment Variable Handling**:
    - Check if ENABLE_PLUGINS is already set
    - Update shell profiles for persistence
    - Handle Windows/Mac/Linux differences
    - Provide clear user feedback about changes
    - Consider temporary vs permanent settings

12. **Future Considerations**:
    - Plugin marketplace/registry doesn't exist yet
    - Could build community-driven registry
    - Consider federation with other PACC instances
    - Think about plugin signing/verification

### Implementation Priorities

1. **High Priority (MVP)**:
   - Basic install/remove/list commands
   - Update management with diff preview
   - Team collaboration via pacc.json
   - Repository management with config.json
   - Settings.json enabledPlugins management

2. **Medium Priority**:
   - **Plugin conversion and management**:
     - Extension to plugin converter (new killer feature)
     - Plugin creation tools
     - Git push for converted plugins
   - **Automatic ENABLE_PLUGINS environment setup**
   - **Slash command integration**
   - Basic search/discovery functionality

3. **Low Priority (Future)**:
   - Comprehensive validation and security scanning
   - Marketplace integration
   - Dependency resolution
   - Plugin publishing workflow
   - Private registries

### Technical Challenges

1. **Atomic Operations**: Must ensure config.json and settings.json updates are atomic to prevent corruption.

2. **Git Conflicts**: Need to handle merge conflicts when CC's auto-update conflicts with manual updates.

3. **Plugin Discovery**: Must correctly identify all plugins within a repository (multiple plugin.json files).

4. **Backwards Compatibility**: Existing PACC users with manual command/agent installations need migration path.

5. **Cross-platform**: Plugin paths and Git operations must work on Windows/Mac/Linux.

### Success Metrics

- Time to install a plugin: <30 seconds
- Zero manual JSON editing required
- Team plugin sync success rate: >99%
- Extension conversion success rate: >95%
- Configuration rollback success: 100%
- User satisfaction with plugin management: >90%

## User Experience

### Installation Journey
1. User runs `pacc plugin install owner/repo`
2. PACC clones repo, discovers plugins, updates configs
3. User selects which plugins to enable (if multiple)
4. PACC sets ENABLE_PLUGINS=1 automatically
5. User restarts Claude Code with plugins ready

### Conversion Journey
1. User has existing custom commands/agents/hooks
2. Runs `pacc plugin convert my-extension --repo github.com/me/my-plugins`
3. PACC creates plugin structure, generates manifest
4. Pushes to Git repository automatically
5. User shares repo URL with team

### Team Collaboration Journey
1. Team lead adds plugins to pacc.json
2. Team members run `pacc plugin sync`
3. PACC installs missing plugins, updates existing ones
4. Everyone has consistent plugin environment
5. No manual configuration needed

## Risks and Mitigations

### Technical Risks
1. **CC Plugin API Changes**: Since it's experimental, APIs may change
   - *Mitigation*: Version detection and compatibility layers

2. **Configuration Corruption**: Malformed JSON could break CC
   - *Mitigation*: Validation, backups, atomic writes

3. **Git Conflicts**: Auto-updates might conflict with local changes
   - *Mitigation*: Conflict detection, manual resolution options

### User Experience Risks
1. **Complexity**: Plugin system adds new concepts
   - *Mitigation*: Clear documentation, intuitive commands

2. **Breaking Changes**: Updates might break workflows
   - *Mitigation*: Version pinning, rollback capability

## Dependencies

- Claude Code v1.0.81+ with plugin support
- Git installed and configured
- Python 3.8+ (existing PACC requirement)
- Network access for Git operations

## Timeline

- **Week 1-2**: Core plugin management (MVP)
- **Week 2-3**: Basic operations and team sync
- **Week 3-4**: Conversion system and environment setup
- **Week 4-5**: UI enhancements and discovery
- **Week 5-6**: Testing, documentation, and polish

## Open Questions

1. Should PACC maintain its own plugin registry/marketplace?
2. How to handle private Git repositories (auth)?
3. Should we support plugin dependencies?
4. How to handle plugin versioning conflicts in teams?
5. Should we add plugin sandboxing/security scanning?

## Appendix

### Related Documents
- [Claude Code Plugin API Reference](/ai_docs/knowledge/claude-code-plugins-api-reference.md)
- [Implementation Backlog](/02_cc_plugins_integration_backlog.md)
- [PACC MVP PRD](/ai_docs/prds/00_pacc_mvp_prd.md)
