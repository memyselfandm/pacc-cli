# Changelog

All notable changes to PACC (Package manager for Claude Code) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2025-09-01

**Major release introducing Claude Code Memory Fragments**

### Added
- **Memory Fragments System** (PACC-39)
  - Install context fragments from files, directories, or Git repositories
  - Automatic CLAUDE.md integration with managed sections
  - Project-level and user-level fragment storage
  - Fragment collections for organizing related content
  - Version tracking for Git-sourced fragments
  - Team synchronization via pacc.json configuration

- **Fragment CLI Commands**
  - `pacc fragment install` - Install fragments from various sources
  - `pacc fragment list` - List installed fragments with filtering
  - `pacc fragment info` - Display fragment details and metadata
  - `pacc fragment remove` - Remove fragments with CLAUDE.md cleanup
  - `pacc fragment update` - Update fragments from their sources
  - `pacc fragment sync` - Sync team fragments from pacc.json
  - `pacc fragment discover` - Discover fragments in repositories
  - `pacc fragment collection *` - Collection management commands

- **Fragment Validation**
  - YAML frontmatter parsing and validation
  - Metadata extraction (title, description, tags, category, author)
  - Content validation for markdown format

- **Documentation**
  - Comprehensive Fragment User Guide (`docs/fragment_user_guide.md`)
  - Updated README with fragment commands and architecture

### Fixed
- **PACC-61 (Critical)**: Path traversal vulnerability in fragment remove command
  - Input sanitization rejects path separators and traversal sequences
  - Boundary validation ensures operations stay within fragment storage
  - Multiple validation layers for defense in depth
- **PACC-60**: Fragment install now properly updates CLAUDE.md references
  - CLI uses FragmentInstallationManager for complete workflow
  - Atomic operations with rollback on failure

### Security
- Path traversal protection for all fragment operations
- Symlink attack prevention
- Null byte injection protection
- Collection traversal prevention
- 13 dedicated security tests covering attack vectors

## [1.0.0] - 2025-08-25

**Production-ready release with complete plugin ecosystem**

### Added
- **Complete Plugin Management System** (Sprints 1-7)
  - Install plugins from Git repositories (HTTPS and SSH)
  - List, enable, disable, and remove installed plugins
  - Update plugins with rollback capability
  - Plugin information display with metadata

- **Team Collaboration Features**
  - `pacc.json` project configuration for plugin requirements
  - Team synchronization with differential updates
  - Version locking to prevent conflicts
  - Cross-platform environment setup (ENABLE_PLUGINS)

- **Plugin Development Tools**
  - Interactive plugin creation wizard with templates
  - Extension-to-plugin converter (95% success rate)
  - Plugin publishing to Git repositories
  - Support for all 4 Claude Code extension types

- **Plugin Discovery & Search**
  - Community plugin registry with 15+ example plugins
  - Search by name, type, tags, and popularity
  - Project-specific plugin recommendations
  - Marketplace foundation for future expansion

- **Security Enhancements**
  - Advanced threat detection (170+ dangerous patterns)
  - 4-level sandbox isolation system
  - Command injection and path traversal protection
  - Comprehensive security audit logging
  - Permission analysis for file operations

- **Claude Code Integration**
  - Native slash commands (/plugin, /pi, /pl, /pe, /pd, /pu)
  - Automatic environment configuration
  - Cross-platform shell detection
  - Settings.json and config.json management

- **Performance Optimizations**
  - Plugin discovery at >4,000 files/second
  - Installation in <30 seconds typical
  - Validation in <50ms per extension
  - Memory-efficient operations with profiling

### Changed
- Enhanced CLI with 15+ new plugin-specific commands
- Improved error messages with recovery suggestions
- Updated documentation with plugin user guide
- Restructured codebase to support plugin architecture

### Fixed
- CommandsValidator no longer incorrectly requires `name` field in frontmatter
- CommandsValidator now correctly treats frontmatter as optional
- AgentsValidator now expects `tools` as comma-separated string per Claude Code docs
- AgentsValidator removed invalid optional fields not in Claude Code specification
- Validators now properly warn about unknown fields instead of failing
- `pacc info` now handles directories correctly like `pacc validate` does

### Security
- Comprehensive validation before any file operations
- Atomic configuration updates with rollback
- Secure Git operations with SSH key support
- Protection against malicious plugin code

## [0.1.0] - 2025-08-16 (Beta)

**Initial beta release of PACC - Package manager for Claude Code**

### Added
- Core installation system supporting all Claude Code extension types
- Multi-type extension support (hooks, MCP servers, agents, commands)
- Interactive selection interface for browsing and installing extensions
- Comprehensive validation system for all extension types
- Safe configuration management with atomic operations
- Source management for local files and directories
- URL download functionality for Git and HTTP sources
- Performance optimizations with caching and lazy loading
- Error recovery system with intelligent retry mechanisms
- Security hardening against path traversal and injection attacks
- Comprehensive test suite with >80% coverage
- Full documentation including API reference and security guide

### Changed
- Migrated from prototype to production-ready architecture
- Improved error messages and user feedback
- Enhanced validation with type-specific rules

### Fixed
- Cross-platform compatibility issues
- Configuration merge conflicts
- Path handling edge cases

---

## Version History Summary

- **1.1.0** - Memory Fragments release with CLAUDE.md integration
- **1.0.0** - Production-ready release with complete plugin ecosystem
- **0.1.0** - Initial beta release

[Unreleased]: https://github.com/memyselfandm/pacc-cli/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/memyselfandm/pacc-cli/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/memyselfandm/pacc-cli/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/memyselfandm/pacc-cli/releases/tag/v0.1.0
