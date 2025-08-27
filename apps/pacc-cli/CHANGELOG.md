# Changelog

All notable changes to PACC (Package manager for Claude Code) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive PyPI publishing documentation and workflow
- Publishing automation scripts for streamlined releases
- Test PyPI integration for safe pre-release testing
- Credential management guide with security best practices
- GitHub Actions workflow for automated publishing
- Makefile targets for publishing workflow

### Changed
- Enhanced build scripts with publishing support
- Updated pyproject.toml with complete metadata

### Fixed
- CommandsValidator no longer incorrectly requires `name` field in frontmatter (PR #3)
- CommandsValidator now correctly treats frontmatter as optional
- AgentsValidator now expects `tools` as comma-separated string per Claude Code docs
- AgentsValidator removed invalid optional fields not in Claude Code specification
- Validators now properly warn about unknown fields instead of failing

### Security
- Secure credential storage recommendations
- Token rotation procedures and best practices

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

## [0.1.0] - 2023-12-XX - Initial Release

### Added
- Basic hook installation functionality
- Project-level installation support
- Simple validation system
- Initial CLI structure

---

## Version History Summary

- **1.0.0** - Production-ready release with comprehensive feature set
- **0.1.0** - Initial prototype release

[Unreleased]: https://github.com/anthropics/pacc/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/anthropics/pacc/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/anthropics/pacc/releases/tag/v0.1.0