# PACC - Package Manager for Claude Code
## Product Requirements Document

### 1. Executive Summary

**Product Name**: PACC (Package manager for Claude Code)  
**Version**: 1.0 MVP  
**Target Users**: Claude Code developers and teams  
**Purpose**: Simplify installation, management, and sharing of Claude Code extensions (hooks, MCP servers, agents, and slash commands)

PACC addresses the current friction in setting up and sharing Claude Code extensions by providing a familiar package manager experience similar to npm, pip, or brew. It automates the safe installation and configuration of Claude Code components while maintaining proper project isolation and team collaboration workflows.

### 2. Problem Statement

Currently, setting up Claude Code extensions requires:
- Manual file creation and placement in specific directories
- Manual editing of settings.json files
- Understanding of complex file structure and naming conventions
- Prone to configuration errors and security risks
- Difficult to share configurations across teams
- No standardized way to distribute and discover extensions

### 3. Product Goals

**Primary Goals:**
- Reduce Claude Code extension setup time from minutes to seconds
- Eliminate configuration errors through automation
- Enable easy sharing of extensions across teams and projects
- Provide a secure, validated installation process
- Create a standardized distribution format for Claude Code extensions

**Success Metrics:**
- 90% reduction in time to install and configure Claude Code extensions
- Zero manual settings.json editing required for standard installations
- 100% of installations maintain proper security boundaries
- Adoption by 50%+ of active Claude Code users within 6 months

### 4. User Stories

#### Primary User Stories

**As a developer, I want to:**
- Install a shared team hook with one command so I don't have to manually configure it
- Browse and select from multiple hooks in a repository without installing everything
- Initialize a new project with standard team configurations automatically
- Install extensions at user-level to use across all my projects
- Remove extensions cleanly without breaking my configuration

**As a team lead, I want to:**
- Define a standard set of extensions for my team in a configuration file
- Share extension configurations through version control
- Ensure team members use consistent tooling and hooks
- Control which extensions can be installed from external sources

**As an extension author, I want to:**
- Package my hook/agent/command for easy distribution
- Document installation requirements and usage clearly
- Provide multiple installation options (project vs user level)
- Version my extensions and provide upgrade paths

### 5. MVP Feature Specifications

#### 5.1 Core Installation System

**Feature**: Multi-type extension installation  
**Requirements**:
- Support for four extension types: hooks, mcp, agents, commands  
- Project-level installation (`.claude/` directory)
- User-level installation (`~/.claude/` directory)
- Automatic detection of extension type from source structure
- Safe modification of settings.json and related configuration files
- Automatic creation of necessary directory structures

**User Experience**:
```bash
# Install from local source
pacc hooks install ./my-hook-folder
pacc mcp install ./my-mcp-server --user
pacc agents install ./team-agents
pacc commands install ./custom-commands --project

# Interactive selection from multi-item sources
pacc hooks install ./multiple-hooks/
# Displays: "Found 3 hooks: formatter, linter, security. Select which to install:"
# User can select multiple via checkbox interface
```

#### 5.2 Source Management

**Feature**: Flexible source input handling  
**Requirements**:
- Accept local file paths for single extensions
- Accept local directory paths for multiple extensions
- Interactive selection interface for multi-item sources
- Validation of source structure and content
- Support for different packaging formats per extension type

**Source Structure Validation**:
- Hooks: Verify JSON structure, validate event types and matchers
- MCP: Validate server configuration and executable paths  
- Agents: Validate YAML frontmatter and markdown content
- Commands: Validate markdown files and naming conventions

#### 5.3 Interactive Selection Interface

**Feature**: Multi-extension source browsing  
**Requirements**:
- Display available extensions with descriptions
- Allow multiple selection via checkbox interface
- Show installation scope (project vs user) for each item
- Preview extension details before installation
- Confirm installation choices before execution

**User Interface Flow**:
1. Scan source directory for valid extensions
2. Display list with type, name, description, and compatibility
3. Allow user to select/deselect items
4. Show installation summary and conflicts
5. Confirm and execute installation

#### 5.4 Safe Configuration Management

**Feature**: Automated settings file updates  
**Requirements**:
- Backup existing settings before modification
- Validate settings.json syntax before and after changes
- Merge new configurations with existing ones intelligently
- Handle conflicts and duplicates gracefully
- Rollback capability on installation failures
- Respect existing user configurations and preferences

**Safety Mechanisms**:
- Create `.claude/pacc/backups/` with timestamped configuration snapshots
- Validate all JSON before writing
- Atomic updates (all changes succeed or all fail)
- Conflict detection and resolution prompts
- Dry-run mode for preview without changes

#### 5.5 Initialization System

**Feature**: Project and user-level initialization  
**Requirements**:
- `pacc init` command with scope selection
- Create necessary directory structures
- Generate basic configuration templates
- Set up gitignore patterns for project installations
- Initialize pacc working directory and metadata

**Command Signatures**:
```bash
pacc init                    # Initialize project-level (default)
pacc init --user            # Initialize user-level  
pacc init --project         # Explicitly project-level
```

**Initialization Actions**:
- Create `.claude/pacc/` working directory
- Generate initial `pacc.json` configuration file
- Update .gitignore to exclude `.claude/pacc/` and `.claude/settings.local.json`
- Create directory structure for all extension types
- Set up logging and metadata tracking

#### 5.6 Package Management Operations

**Feature**: Standard package manager verbs  
**Requirements**:
- Consistent command structure: `pacc <noun> <verb> <options>`
- Support for install, list, remove, update operations
- Detailed information display for installed packages
- Dependency tracking and conflict detection

**Command Structure**:
```bash
# Installation
pacc hooks install <source> [--user|--project] [--force] [--dry-run]
pacc mcp install <source> [options]
pacc agents install <source> [options]  
pacc commands install <source> [options]

# Listing
pacc hooks list [--user|--project|--all]
pacc mcp ls
pacc agents list --verbose
pacc commands list --format=table

# Removal
pacc hooks remove <name> [--user|--project]
pacc mcp remove <name> 
pacc agents remove <name> --confirm
pacc commands remove <name>

# Information
pacc hooks info <name>
pacc mcp info <name>
```

### 6. Technical Architecture

#### 6.1 Core Technology Stack

**Language**: Python 3.8+  
**Dependencies**: Minimal external dependencies
- `uv` for script execution and dependency management
- Standard library for JSON/YAML parsing, file operations
- `click` or `typer` for CLI interface (if needed beyond standard argparse)

**Script Execution**: All scripts executed via `uv run` for consistency and isolation

#### 6.2 Directory Structure and Data Management

**Working Directory**: `.claude/pacc/` (project) or `~/.claude/pacc/` (user)

```
.claude/pacc/
├── config.json                 # PACC configuration
├── installed.json              # Installation registry
├── backups/                    # Configuration backups
│   ├── settings_20241201_143022.json
│   └── hooks_20241201_143022.json
├── cache/                      # Downloaded packages (future)
├── logs/                       # Installation/operation logs
└── temp/                       # Temporary files during operations
```

**Configuration Files**:
- `config.json`: PACC settings, source repositories, preferences
- `installed.json`: Registry of installed packages with metadata
- Logs: Structured logs for debugging and audit trails

#### 6.3 Integration with Claude Code Settings

**Settings File Management**:
- Read existing `.claude/settings.json` and `~/.claude/settings.json`
- Parse and validate JSON structure
- Merge new configurations using deep merge strategy
- Maintain user preferences and existing configurations
- Update related files (MCP configurations, etc.)

**Git Integration**:
- Automatically update `.gitignore` for project installations
- Exclude `.claude/pacc/` and `.claude/settings.local.json`
- Preserve existing gitignore patterns
- Handle cases where gitignore doesn't exist

#### 6.4 Extension Type Handling

**Hooks**:
- Validate hook structure and event types
- Update settings.json hooks section
- Support for PreToolUse, PostToolUse, Notification, Stop events
- Validate matchers and command syntax

**MCP Servers**:
- Handle `.mcp.json` file creation/updates
- Validate server configurations and executable paths
- Support for both project and user MCP installations
- Manage server lifecycle and dependencies

**Agents**:
- Validate YAML frontmatter and markdown content
- Place files in correct agents directory
- Validate tool permissions and descriptions
- Handle name conflicts between user and project agents

**Commands**:
- Validate markdown format and naming conventions
- Support namespacing through directory structures
- Handle argument placeholders and syntax
- Maintain command registry for conflict detection

### 7. User Experience Design

#### 7.1 Command Line Interface

**Design Principles**:
- Familiar package manager patterns (npm, pip, brew)
- Consistent verb-noun structure
- Helpful error messages and guidance
- Progressive disclosure of complexity
- Sensible defaults for common operations

**Help System**:
```bash
pacc --help                    # Global help
pacc hooks --help              # Noun-specific help
pacc hooks install --help      # Command-specific help
```

**Output Formatting**:
- Colored output for status indicators (success/warning/error)
- Progress indicators for long operations
- Structured output options (JSON, table, list)
- Verbose mode for detailed operation logs

#### 7.2 Interactive Features

**Selection Interface**:
- Checkbox-style multi-selection for batch operations
- Arrow key navigation
- Search/filter capability for large lists
- Preview pane showing extension details
- Keyboard shortcuts for common actions

**Confirmation Prompts**:
- Clear summary of planned changes
- Risk indicators for potentially dangerous operations
- Option to preview changes without execution
- Ability to modify selections before confirmation

#### 7.3 Error Handling and Recovery

**Error Categories**:
- Validation errors: Clear description of what's invalid and how to fix
- Permission errors: Guidance on resolving access issues
- Conflict errors: Options for resolution (overwrite, skip, rename)
- System errors: Recovery suggestions and support information

**Recovery Mechanisms**:
- Automatic rollback on failed installations
- Manual rollback commands for user-initiated recovery
- Repair commands to fix corrupted installations
- Diagnostic commands to identify and resolve issues

### 8. Security and Safety Considerations

#### 8.1 Installation Safety

**Validation Requirements**:
- Syntax validation for all configuration files
- Schema validation for extension metadata
- Security scanning of hook commands (basic patterns)
- Path validation to prevent directory traversal
- Permission validation for MCP servers and hooks

**User Consent**:
- Clear disclosure of what will be installed and where
- Warning for potentially dangerous operations (file system access, network access)
- Confirmation required for overwriting existing configurations
- Option to review all changes before execution

#### 8.2 Execution Security

**Isolation**:
- No execution of arbitrary code during installation
- Validation-only approach for package contents
- Clear separation between pacc operations and installed extension execution
- Audit trail of all installation and configuration changes

**Permission Model**:
- Respect existing Claude Code permission settings
- Never override user-defined security restrictions
- Provide warnings when installing extensions that require elevated permissions
- Support for organization-level policy enforcement (future)

### 9. Post-MVP Roadmap

#### 9.1 Phase 2: Remote Sources and Web Integration

**URL Source Support**:
- Install directly from GitHub URLs, gists, and other web sources
- Support for version pinning and update notifications
- Checksum verification for downloaded packages
- Cached downloads for offline usage

**Repository Management**:
- Add/remove public extension repositories
- Search and browse available extensions
- Automatic updates for installed packages
- Version management and dependency resolution

#### 9.2 Phase 3: Configuration as Code

**pacc.json Project Configuration**:
- Declarative configuration file in project root
- `pacc install` reads pacc.json and installs all listed extensions
- Version locking and team synchronization
- Environment-specific configurations (dev, staging, prod)

**Team Collaboration**:
- Shared team extension repositories
- Organization-wide extension policies
- Automated setup for new team members
- Integration with CI/CD for consistent environments

#### 9.3 Phase 4: Advanced Features

**PACC Slash Commands**:
- Native Claude Code integration via slash commands
- In-session package management without leaving Claude Code
- Real-time installation status and feedback
- Integration with Claude Code's permission system

**Enhanced Safety and Validation**:
- Code scanning for security vulnerabilities
- Digital signatures for trusted extension authors
- Sandboxed installation testing
- Automated testing of installed extensions

**Status Line Integration**:
- Live status indicator for package management operations
- Quick access to commonly used extensions
- Visual feedback for installation status and conflicts
- Integration with Claude Code's notification system

#### 9.4 Phase 5: Ecosystem Development

**Extension Marketplace**:
- Curated extension directory
- User ratings and reviews
- Usage statistics and analytics
- Featured extensions and recommendations

**Developer Tools**:
- Extension scaffolding and templates
- Testing framework for extensions
- Documentation generation
- Publishing and distribution tools

### 10. Success Metrics and KPIs

#### 10.1 Adoption Metrics
- Number of active users (monthly/weekly)
- Number of extensions installed through pacc
- Percentage of Claude Code users adopting pacc
- Growth in community-contributed extensions

#### 10.2 Quality Metrics
- Installation success rate (target: >99%)
- Configuration error rate (target: <1%)
- User satisfaction scores
- Time to successful installation (target: <30 seconds)

#### 10.3 Ecosystem Health
- Number of available extensions
- Number of active extension authors
- Community contribution rates
- Documentation completeness and quality

### 11. Documentation Requirements

#### 11.1 User Documentation

**Installation and Setup Guide**:
- Installation instructions for different operating systems
- Initial configuration and setup process
- Integration with existing Claude Code installations
- Troubleshooting common installation issues

**User Guide**:
- Complete command reference with examples
- Common workflows and use cases
- Best practices for project vs user installations
- Team collaboration patterns

**Extension Management Guide**:
- How to find and evaluate extensions
- Installation and removal procedures
- Conflict resolution and troubleshooting
- Security considerations for extension installation

#### 11.2 Developer Documentation

**Extension Packaging Guide**:
- Directory structure requirements for each extension type
- Metadata and configuration file formats
- Testing and validation procedures
- Packaging best practices and conventions

**Source Repository Setup**:
- How to structure a source repository for pacc
- Multi-extension repository organization
- Versioning and release management
- Documentation requirements for extensions

**Integration Guide**:
- How pacc integrates with Claude Code settings
- Configuration file formats and validation
- Extension lifecycle and management
- API reference for programmatic usage

#### 11.3 Specification Documents

**pacc.json Schema**:
- Complete schema definition for project configuration
- Field descriptions and validation rules
- Examples for different project types
- Version migration guides

**Extension Metadata Schema**:
- Required and optional metadata fields
- Validation rules and constraints
- Compatibility indicators and requirements
- Security and permission declarations

### 12. Implementation Considerations

#### 12.1 Development Approach

**Iterative Development**:
- Start with hooks as the primary extension type (most complex validation)
- Add extension types incrementally (commands, agents, mcp)
- Build robust error handling and recovery early
- Test extensively with real Claude Code installations

**Testing Strategy**:
- Unit tests for all validation and configuration logic
- Integration tests with actual Claude Code installations
- End-to-end tests for complete installation workflows
- Security testing for validation bypass attempts

#### 12.2 Distribution and Packaging

**Installation Method**:
- Distribute as a single Python script with uv integration
- Support for both direct download and package manager installation
- Self-updating capability for future releases
- Compatibility with different Python environments

**Version Management**:
- Semantic versioning for pacc itself
- Backward compatibility for configuration formats
- Migration tools for breaking changes
- Clear upgrade paths and documentation

#### 12.3 Community and Ecosystem

**Open Source Strategy**:
- Open source from day one to encourage community contribution
- Clear contribution guidelines and code of conduct
- Regular community feedback sessions and feature requests
- Integration with Anthropic's developer community programs

**Extension Quality**:
- Community-driven extension validation and testing
- Template repositories for different extension types
- Best practices documentation and examples
- Automated quality checks and recommendations

This PRD provides a comprehensive foundation for implementing PACC as a robust, secure, and user-friendly package manager for Claude Code extensions. The focus on safety, familiar UX patterns, and extensibility positions it to become an essential tool in the Claude Code ecosystem.