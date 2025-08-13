# PACC Validators

This module provides comprehensive validation for Claude Code extension files including hooks, MCP servers, agents, and slash commands. The validators ensure that extensions follow proper formatting, contain required fields, and adhere to security best practices.

## Overview

The PACC validators module implements Wave 2 of the Source Management feature, providing extension-specific validation for all four Claude Code extension types:

- **Hooks**: JSON configuration files for event-driven automation
- **MCP**: Model Context Protocol server configurations  
- **Agents**: YAML frontmatter + markdown files for AI agents
- **Commands**: Markdown files defining slash commands

## Quick Start

```python
from pacc.validators import validate_extension_file, ValidationRunner

# Validate a single file (auto-detects extension type)
result = validate_extension_file("my-hook.json")
print(f"Valid: {result.is_valid}")

# Validate all extensions in a directory
runner = ValidationRunner()
results = runner.validate_directory("./extensions")
```

## Architecture

### Base Classes

#### `BaseValidator`
Abstract base class for all extension validators providing:
- File accessibility validation
- JSON syntax validation  
- Common field validation utilities
- Batch and directory validation support

#### `ValidationResult`
Container for validation outcomes including:
- Validity status (`is_valid`)
- Error and warning lists
- Extension metadata
- File path information

#### `ValidationError`
Detailed error information with:
- Error code for programmatic handling
- Human-readable message
- Optional line numbers and suggestions
- Severity levels (error, warning, info)

### Extension-Specific Validators

#### `HooksValidator`
Validates Claude Code hook files:

**Supported Features:**
- JSON structure validation
- Event type validation (`PreToolUse`, `PostToolUse`, `Notification`, `Stop`)
- Command syntax and security checks
- Matcher validation (exact, regex, prefix, suffix, contains)
- Version format validation

**Example Hook:**
```json
{
  "name": "format-checker",
  "description": "Validates code formatting",
  "eventTypes": ["PreToolUse"],
  "commands": ["ruff check {file_path}"],
  "matchers": [{
    "type": "regex",
    "pattern": ".*\\.(py|js)$"
  }]
}
```

**Validation Rules:**
- Name must be alphanumeric with hyphens/underscores
- At least one valid event type required
- Commands checked for security issues
- Regex patterns validated for syntax
- Reserved names generate warnings

#### `MCPValidator`
Validates Model Context Protocol server configurations:

**Supported Features:**
- Server configuration validation
- Executable path verification
- Environment variable validation
- Timeout and retry settings
- Optional connection testing

**Example MCP Configuration:**
```json
{
  "mcpServers": {
    "file-manager": {
      "command": "python",
      "args": ["-m", "file_manager_mcp"],
      "env": {"LOG_LEVEL": "INFO"},
      "timeout": 60
    }
  }
}
```

**Validation Rules:**
- `mcpServers` object required
- Each server must have `command` field
- Executable paths checked for existence
- Environment variables must be strings
- Timeouts must be positive numbers

#### `AgentsValidator`
Validates AI agent definition files:

**Supported Features:**
- YAML frontmatter parsing
- Required field validation (name, description)
- Tool and permission validation
- Parameter schema validation
- Markdown content analysis

**Example Agent:**
```markdown
---
name: code-reviewer
description: Reviews code for best practices
tools: [file_reader, analyzer]
permissions: [read_files]
parameters:
  language:
    type: choice
    choices: [python, javascript]
    required: true
---

# Code Reviewer Agent

This agent specializes in code review...
```

**Validation Rules:**
- YAML frontmatter required with name and description
- Valid permission types enforced
- Parameter types must be supported
- Temperature between 0 and 1
- Semantic versioning for version field

#### `CommandsValidator`
Validates slash command definition files:

**Supported Features:**
- YAML frontmatter or simple markdown formats
- Command name validation
- Parameter schema validation
- Usage pattern validation
- Alias and permission validation

**Example Command:**
```markdown
---
name: deploy
description: Deploy to specified environment
usage: /deploy [environment]
parameters:
  environment:
    type: choice
    choices: [dev, staging, prod]
    required: true
---

# Deploy Command

Deploy your application...
```

**Validation Rules:**
- Command names must start with letter
- Reserved names (help, exit, etc.) forbidden
- Parameter types validated
- Choice parameters require choices array
- Usage patterns should start with /

## Utility Classes

### `ValidatorFactory`
Factory for creating validator instances:

```python
from pacc.validators import ValidatorFactory

# Get specific validator
hooks_validator = ValidatorFactory.get_validator("hooks")

# Get all validators
all_validators = ValidatorFactory.get_all_validators()
```

### `ValidationRunner`
High-level interface for validation operations:

```python
from pacc.validators import ValidationRunner

runner = ValidationRunner()

# Validate single file with auto-detection
result = runner.validate_file("extension.json")

# Validate directory
results_by_type = runner.validate_directory("./extensions")

# Validate mixed file types
results = runner.validate_mixed_files(["hook.json", "agent.md"])
```

### `ExtensionDetector`
Automatic extension type detection:

```python
from pacc.validators import ExtensionDetector

# Detect single file type
ext_type = ExtensionDetector.detect_extension_type("my-file.json")

# Scan directory and categorize files
files_by_type = ExtensionDetector.scan_directory("./extensions")
```

### `ValidationResultFormatter`
Format validation results for display:

```python
from pacc.validators import ValidationResultFormatter

# Format as text
text_output = ValidationResultFormatter.format_result(result, verbose=True)

# Format as JSON
json_output = ValidationResultFormatter.format_as_json(results)
```

## Error Handling

The validators provide comprehensive error reporting with specific error codes:

### Common Error Codes

**File Access:**
- `FILE_NOT_FOUND`: File doesn't exist
- `FILE_TOO_LARGE`: Exceeds size limit
- `ENCODING_ERROR`: UTF-8 encoding issues

**Format Errors:**
- `INVALID_JSON`: JSON syntax errors
- `INVALID_YAML`: YAML parsing errors
- `MALFORMED_FRONTMATTER`: Missing closing ---

**Content Validation:**
- `MISSING_REQUIRED_FIELD`: Required field absent
- `INVALID_FIELD_TYPE`: Wrong data type
- `RESERVED_NAME`: Using reserved identifier

**Security Warnings:**
- `POTENTIAL_SHELL_INJECTION`: Dangerous command patterns
- `DANGEROUS_COMMAND`: Potentially destructive operations
- `COMMAND_NOT_IN_PATH`: Executable not found

## Performance Considerations

### Large File Handling
- Default 10MB file size limit
- Configurable via `max_file_size` parameter
- Streaming validation for large directories

### Batch Operations
- Parallel validation support planned
- Memory-efficient directory scanning
- Progress reporting for long operations

### Caching
- Pre-compiled regex patterns
- Reusable validator instances
- Metadata caching for repeated validations

## Testing

Comprehensive test suite included:

```bash
# Run all validator tests
python -m pacc.validators.test_validators

# Run demonstration
python -m pacc.validators.demo
```

### Test Coverage
- Valid extension examples
- Invalid format handling
- Edge cases and error conditions
- Performance with large files
- Security vulnerability detection

## Integration Examples

### CLI Integration
```python
from pacc.validators import create_validation_report

def validate_command(file_path):
    result = validate_extension_file(file_path)
    report = create_validation_report(result, output_format="text", verbose=True)
    print(report)
```

### Pre-commit Hook
```python
from pacc.validators import ValidationRunner

def pre_commit_validation():
    runner = ValidationRunner()
    results = runner.validate_directory(".")
    
    has_errors = any(
        any(not r.is_valid for r in file_results)
        for file_results in results.values()
    )
    
    if has_errors:
        print("Validation failed - fix errors before committing")
        return False
    
    return True
```

### IDE Integration
```python
from pacc.validators import validate_extension_file

def get_diagnostics(file_path):
    result = validate_extension_file(file_path)
    
    diagnostics = []
    for error in result.all_issues:
        diagnostics.append({
            "line": error.line_number or 1,
            "message": error.message,
            "severity": error.severity,
            "code": error.code
        })
    
    return diagnostics
```

## Configuration

Validators accept configuration parameters:

```python
# Custom file size limit
validator = HooksValidator(max_file_size=50 * 1024 * 1024)  # 50MB

# Enable MCP connection testing
mcp_validator = MCPValidator(enable_connection_testing=True)

# Configure all validators
runner = ValidationRunner(
    max_file_size=20 * 1024 * 1024,
    enable_connection_testing=False
)
```

## Future Enhancements

### Planned Features
- Async validation for large directories
- Custom validation rules via plugins
- Integration with Claude Code settings validation
- Real-time validation during editing
- Validation rule documentation generation

### Extension Points
The validator architecture supports:
- Custom validator implementations
- Additional extension types
- Configurable validation rules
- Custom error formatters
- Integration with external tools

## Contributing

When adding new validators or enhancing existing ones:

1. Inherit from `BaseValidator`
2. Implement required abstract methods
3. Add comprehensive error codes and messages
4. Include security validation where applicable
5. Add test cases covering edge cases
6. Update factory registration
7. Document validation rules and examples

For detailed implementation examples, see the existing validator implementations in this module.