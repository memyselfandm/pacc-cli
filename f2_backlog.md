# Feature 5.2: Source Management - Implementation Backlog

## Feature Summary
The Source Management feature enables flexible handling of extension sources, supporting both single file inputs and directory-based multi-extension scenarios. It includes an interactive selection interface and comprehensive validation for each extension type (Hooks, MCP, Agents, Commands).

## Core Implementation Tasks

### 1. Source Input Handling
- [ ] Implement local file path acceptance
  - [ ] Create file path validator utility
  - [ ] Implement path normalization (resolve relative paths to absolute)
  - [ ] Add support for tilde expansion (~/)
  - [ ] Handle Windows vs Unix path separators
- [ ] Implement local directory path acceptance
  - [ ] Create directory scanner utility
  - [ ] Implement recursive directory traversal option
  - [ ] Add file filtering by extension type
  - [ ] Create directory structure analyzer
- [ ] Build source type detection logic
  - [ ] Auto-detect if path is file or directory
  - [ ] Identify extension type from file extension/content
  - [ ] Handle edge cases (symlinks, permissions)

### 2. Interactive Selection Interface
- [ ] Design selection UI components
  - [ ] Create multi-select list component
  - [ ] Implement keyboard navigation (arrow keys, space to select)
  - [ ] Add search/filter functionality
  - [ ] Include preview pane for selected items
- [ ] Implement selection workflow
  - [ ] Show discovered extensions with metadata
  - [ ] Allow individual item selection/deselection
  - [ ] Add "select all" / "deselect all" options
  - [ ] Implement selection persistence during navigation
- [ ] Create confirmation and summary screens
  - [ ] Display selected items with validation status
  - [ ] Show total count and breakdown by type
  - [ ] Add confirmation prompt before processing

### 3. Extension Type Validation

#### 3.1 Hooks Validation
- [ ] Implement JSON structure validator
  - [ ] Verify valid JSON syntax
  - [ ] Check required fields (name, version, events)
  - [ ] Validate JSON schema compliance
- [ ] Validate event types
  - [ ] Check against allowed event type list
  - [ ] Verify event handler structure
  - [ ] Validate event priority values
- [ ] Validate matchers
  - [ ] Check matcher syntax (regex, glob patterns)
  - [ ] Test matcher compilation
  - [ ] Validate matcher performance (avoid catastrophic backtracking)
- [ ] Create Hooks-specific error messages
  - [ ] Invalid JSON structure errors
  - [ ] Unknown event type errors
  - [ ] Matcher compilation errors

#### 3.2 MCP (Model Context Protocol) Validation
- [ ] Validate server configuration
  - [ ] Check required config fields (name, command, args)
  - [ ] Verify environment variable references
  - [ ] Validate port/socket configurations
- [ ] Validate executable paths
  - [ ] Check executable exists and is accessible
  - [ ] Verify execution permissions
  - [ ] Validate command arguments format
  - [ ] Test executable with --version flag
- [ ] Implement connection testing
  - [ ] Attempt server startup validation
  - [ ] Check for port conflicts
  - [ ] Validate server response format
- [ ] Create MCP-specific error messages
  - [ ] Executable not found errors
  - [ ] Permission denied errors
  - [ ] Configuration syntax errors

#### 3.3 Agents Validation
- [ ] Validate YAML frontmatter
  - [ ] Parse YAML header correctly
  - [ ] Check required fields (name, version, description)
  - [ ] Validate metadata schema
  - [ ] Handle YAML parsing errors gracefully
- [ ] Validate markdown content
  - [ ] Check for required sections (capabilities, instructions)
  - [ ] Validate markdown syntax
  - [ ] Ensure no broken internal links
  - [ ] Check code block syntax
- [ ] Implement content structure validation
  - [ ] Verify agent instruction clarity
  - [ ] Check for conflicting directives
  - [ ] Validate example usage sections
- [ ] Create Agents-specific error messages
  - [ ] Invalid YAML frontmatter errors
  - [ ] Missing required sections errors
  - [ ] Markdown syntax errors

#### 3.4 Commands Validation
- [ ] Validate markdown files
  - [ ] Check markdown syntax validity
  - [ ] Verify command documentation structure
  - [ ] Validate code examples
  - [ ] Check for required sections
- [ ] Validate naming conventions
  - [ ] Check file naming pattern compliance
  - [ ] Verify command name uniqueness
  - [ ] Validate command aliases
  - [ ] Check for reserved command names
- [ ] Implement command metadata validation
  - [ ] Verify command signature format
  - [ ] Check parameter documentation
  - [ ] Validate return value documentation
- [ ] Create Commands-specific error messages
  - [ ] Invalid naming convention errors
  - [ ] Missing documentation errors
  - [ ] Duplicate command name errors

### 4. Packaging Format Support
- [ ] Implement format detection
  - [ ] Auto-detect packaging format from file structure
  - [ ] Support explicit format specification
  - [ ] Handle mixed format directories
- [ ] Support single-file formats
  - [ ] JSON for Hooks
  - [ ] YAML for MCP configs
  - [ ] Markdown for Agents and Commands
- [ ] Support multi-file formats
  - [ ] Directory-based Hooks with manifest
  - [ ] MCP packages with dependencies
  - [ ] Agent bundles with resources
  - [ ] Command collections with shared utilities
- [ ] Implement format converters
  - [ ] Convert between supported formats
  - [ ] Preserve metadata during conversion
  - [ ] Handle format-specific features

### 5. Error Handling
- [ ] Implement comprehensive error types
  - [ ] FileNotFoundError for missing sources
  - [ ] PermissionError for access issues
  - [ ] ValidationError for content issues
  - [ ] FormatError for unsupported formats
- [ ] Create error recovery mechanisms
  - [ ] Suggest fixes for common errors
  - [ ] Allow partial processing on errors
  - [ ] Implement retry logic for transient errors
- [ ] Build error reporting system
  - [ ] Aggregate errors by type
  - [ ] Create detailed error logs
  - [ ] Generate user-friendly error summaries
- [ ] Implement error UI
  - [ ] Show inline validation errors
  - [ ] Create error summary dialog
  - [ ] Add "fix and retry" options

### 6. User Experience Flow
- [ ] Design onboarding flow
  - [ ] Create source selection wizard
  - [ ] Add helpful tooltips and examples
  - [ ] Implement progress indicators
- [ ] Optimize performance
  - [ ] Implement lazy loading for large directories
  - [ ] Add caching for validation results
  - [ ] Create background validation workers
- [ ] Add convenience features
  - [ ] Recent sources history
  - [ ] Drag-and-drop file support
  - [ ] Batch operations support
  - [ ] Quick actions menu

## Test Cases

### Unit Tests
- [ ] Test file path validation
  - [ ] Valid absolute paths
  - [ ] Valid relative paths
  - [ ] Invalid paths (non-existent, no permissions)
  - [ ] Edge cases (symlinks, network paths)
- [ ] Test directory scanning
  - [ ] Empty directories
  - [ ] Nested directories
  - [ ] Large directories (1000+ files)
  - [ ] Mixed content directories
- [ ] Test validation logic for each extension type
  - [ ] Valid extension files
  - [ ] Invalid extension files
  - [ ] Edge case content
  - [ ] Malformed content

### Integration Tests
- [ ] Test full source import workflow
  - [ ] Single file import
  - [ ] Directory import with selection
  - [ ] Mixed extension type import
  - [ ] Error recovery scenarios
- [ ] Test interactive selection interface
  - [ ] Keyboard navigation
  - [ ] Mouse interactions
  - [ ] Search and filter
  - [ ] Large list performance
- [ ] Test validation pipeline
  - [ ] Sequential validation
  - [ ] Parallel validation
  - [ ] Validation with dependencies
  - [ ] Cascading validation errors

### End-to-End Tests
- [ ] Test complete user journeys
  - [ ] First-time user importing extensions
  - [ ] Power user batch importing
  - [ ] Error correction workflow
  - [ ] Format conversion workflow
- [ ] Test cross-platform compatibility
  - [ ] Windows path handling
  - [ ] macOS specific features
  - [ ] Linux file permissions
  - [ ] Network file systems

## Performance Requirements
- [ ] Directory scanning < 100ms for 1000 files
- [ ] Validation < 50ms per extension
- [ ] Interactive UI responsive < 16ms
- [ ] Memory usage < 100MB for large imports

## Security Considerations
- [ ] Implement path traversal protection
- [ ] Validate file size limits
- [ ] Scan for malicious patterns
- [ ] Implement sandboxed validation
- [ ] Add user permission checks

## Documentation Tasks
- [ ] Create source format specifications
- [ ] Write validation rule documentation
- [ ] Create troubleshooting guide
- [ ] Add example extensions for each type
- [ ] Document best practices