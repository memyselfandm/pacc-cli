"""Pytest configuration and shared fixtures for PACC tests."""

import os
import tempfile
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List, Generator
import pytest
from unittest.mock import MagicMock, patch

# Import modules to test
from pacc.core.file_utils import FilePathValidator, PathNormalizer, DirectoryScanner, FileFilter
from pacc.errors.exceptions import PACCError, ValidationError as PACCValidationError
from pacc.validators.base import BaseValidator, ValidationResult, ValidationError


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_directory_structure(temp_dir: Path) -> Path:
    """Create a sample directory structure for testing."""
    # Create directory structure
    (temp_dir / "hooks").mkdir()
    (temp_dir / "mcp").mkdir()
    (temp_dir / "agents").mkdir()
    (temp_dir / "commands").mkdir()
    (temp_dir / "nested" / "deep").mkdir(parents=True)
    (temp_dir / ".hidden").mkdir()
    
    # Create sample files
    files_to_create = [
        ("hooks/sample_hook.json", {"name": "test-hook", "version": "1.0.0", "events": ["PreToolUse"]}),
        ("hooks/invalid_hook.json", "invalid json content"),
        ("mcp/server.yaml", {"name": "test-server", "command": "python", "args": ["-m", "test"]}),
        ("agents/test_agent.md", "# Test Agent\n\n---\nname: test-agent\nversion: 1.0.0\n---\n\nThis is a test agent."),
        ("commands/test_command.md", "# Test Command\n\nThis is a test command."),
        ("nested/deep/file.txt", "deep file content"),
        (".hidden/hidden_file.txt", "hidden content"),
        ("large_file.txt", "x" * 1000),  # 1KB file
    ]
    
    for file_path, content in files_to_create:
        file_full_path = temp_dir / file_path
        if isinstance(content, dict):
            with open(file_full_path, 'w') as f:
                json.dump(content, f, indent=2)
        else:
            with open(file_full_path, 'w') as f:
                f.write(content)
    
    return temp_dir


@pytest.fixture
def sample_json_files(temp_dir: Path) -> List[Path]:
    """Create sample JSON files for testing."""
    files = []
    
    # Valid JSON hook
    valid_hook = temp_dir / "valid_hook.json"
    with open(valid_hook, 'w') as f:
        json.dump({
            "name": "test-hook",
            "version": "1.0.0",
            "events": ["PreToolUse", "PostToolUse"],
            "matchers": [{"pattern": "*.py"}]
        }, f, indent=2)
    files.append(valid_hook)
    
    # Invalid JSON
    invalid_json = temp_dir / "invalid.json"
    with open(invalid_json, 'w') as f:
        f.write('{"invalid": json, syntax}')
    files.append(invalid_json)
    
    # Empty JSON
    empty_json = temp_dir / "empty.json"
    with open(empty_json, 'w') as f:
        f.write('{}')
    files.append(empty_json)
    
    return files


@pytest.fixture
def sample_yaml_files(temp_dir: Path) -> List[Path]:
    """Create sample YAML files for testing."""
    files = []
    
    # Valid YAML MCP config
    valid_mcp = temp_dir / "valid_mcp.yaml"
    with open(valid_mcp, 'w') as f:
        yaml.dump({
            "name": "test-mcp-server",
            "command": "python",
            "args": ["-m", "test_server"],
            "env": {"TEST_ENV": "true"}
        }, f)
    files.append(valid_mcp)
    
    # Invalid YAML
    invalid_yaml = temp_dir / "invalid.yaml"
    with open(invalid_yaml, 'w') as f:
        f.write('invalid: yaml: syntax: [unclosed')
    files.append(invalid_yaml)
    
    return files


@pytest.fixture
def sample_markdown_files(temp_dir: Path) -> List[Path]:
    """Create sample Markdown files for testing."""
    files = []
    
    # Valid agent markdown with YAML frontmatter
    valid_agent = temp_dir / "valid_agent.md"
    with open(valid_agent, 'w') as f:
        f.write("""---
name: test-agent
version: 1.0.0
description: A test agent for validation
capabilities:
  - text_processing
  - data_analysis
---

# Test Agent

This is a test agent with proper structure.

## Capabilities

- Process text data
- Analyze patterns

## Instructions

Use this agent for testing validation workflows.
""")
    files.append(valid_agent)
    
    # Valid command markdown
    valid_command = temp_dir / "valid_command.md"
    with open(valid_command, 'w') as f:
        f.write("""# Test Command

A test command for validation.

## Usage

```bash
test-command --option value
```

## Parameters

- `--option`: Test option parameter

## Examples

```bash
test-command --option "example"
```
""")
    files.append(valid_command)
    
    # Invalid markdown (no proper structure)
    invalid_md = temp_dir / "invalid.md"
    with open(invalid_md, 'w') as f:
        f.write("Just some text without proper structure")
    files.append(invalid_md)
    
    return files


@pytest.fixture
def file_path_validator() -> FilePathValidator:
    """Create a FilePathValidator instance for testing."""
    return FilePathValidator()


@pytest.fixture
def restricted_validator() -> FilePathValidator:
    """Create a FilePathValidator with extension restrictions."""
    return FilePathValidator(allowed_extensions={'.json', '.yaml', '.md'})


@pytest.fixture
def path_normalizer() -> PathNormalizer:
    """Create a PathNormalizer instance for testing."""
    return PathNormalizer()


@pytest.fixture
def directory_scanner() -> DirectoryScanner:
    """Create a DirectoryScanner instance for testing."""
    return DirectoryScanner()


@pytest.fixture
def file_filter() -> FileFilter:
    """Create a FileFilter instance for testing."""
    return FileFilter()


@pytest.fixture
def validation_result() -> ValidationResult:
    """Create a ValidationResult instance for testing."""
    return ValidationResult(is_valid=True, file_path="/test/file.json", extension_type="hooks")


@pytest.fixture
def sample_validation_errors() -> List[ValidationError]:
    """Create sample validation errors for testing."""
    return [
        ValidationError(
            code="TEST_ERROR_1",
            message="Test error message 1",
            file_path="/test/file1.json",
            line_number=5,
            severity="error",
            suggestion="Fix the error"
        ),
        ValidationError(
            code="TEST_WARNING_1", 
            message="Test warning message 1",
            file_path="/test/file2.json",
            severity="warning",
            suggestion="Consider fixing this warning"
        ),
    ]


@pytest.fixture
def mock_validator() -> BaseValidator:
    """Create a mock validator for testing."""
    class MockValidator(BaseValidator):
        def get_extension_type(self) -> str:
            return "test"
        
        def validate_single(self, file_path) -> ValidationResult:
            result = ValidationResult(is_valid=True, file_path=str(file_path), extension_type="test")
            return result
        
        def _find_extension_files(self, directory: Path) -> List[Path]:
            return list(directory.glob("*.test"))
    
    return MockValidator()


@pytest.fixture
def security_test_paths(temp_dir: Path) -> Dict[str, Path]:
    """Create paths for security testing (path traversal, etc.)."""
    # Create some files for security testing
    safe_file = temp_dir / "safe_file.txt"
    safe_file.write_text("safe content")
    
    # Create a file outside temp directory for traversal testing
    parent_dir = temp_dir.parent
    outside_file = parent_dir / "outside_file.txt"
    outside_file.write_text("outside content")
    
    return {
        "safe_file": safe_file,
        "outside_file": outside_file,
        "temp_dir": temp_dir,
        "parent_dir": parent_dir,
        "traversal_path": "../outside_file.txt",
        "absolute_traversal": str(outside_file),
    }


@pytest.fixture
def large_file(temp_dir: Path) -> Path:
    """Create a large file for size testing."""
    large_file = temp_dir / "large_file.txt"
    # Create a 2MB file
    with open(large_file, 'w') as f:
        f.write('x' * (2 * 1024 * 1024))
    return large_file


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Automatically cleanup any temporary files created during tests."""
    yield
    # Cleanup happens automatically via tempfile module


@pytest.fixture
def mock_os_functions():
    """Mock OS functions for testing error conditions."""
    return {
        'access': patch('os.access'),
        'stat': patch('os.stat'),
        'listdir': patch('os.listdir'),
        'path_exists': patch('pathlib.Path.exists'),
        'path_is_file': patch('pathlib.Path.is_file'),
        'path_is_dir': patch('pathlib.Path.is_dir'),
    }


# Performance testing fixtures
@pytest.fixture
def performance_directory(temp_dir: Path) -> Path:
    """Create a directory with many files for performance testing."""
    perf_dir = temp_dir / "performance_test"
    perf_dir.mkdir()
    
    # Create 1000 small files
    for i in range(1000):
        file_path = perf_dir / f"file_{i:04d}.txt"
        file_path.write_text(f"content for file {i}")
    
    # Create some different extension files
    for ext in ['.json', '.yaml', '.md', '.py']:
        for i in range(100):
            file_path = perf_dir / f"file_{i:04d}{ext}"
            file_path.write_text(f"content for {ext} file {i}")
    
    return perf_dir


# Cross-platform testing fixtures
@pytest.fixture
def cross_platform_paths(temp_dir: Path) -> Dict[str, str]:
    """Create paths for cross-platform testing."""
    return {
        'windows_style': r'C:\Users\test\file.txt',
        'unix_style': '/home/test/file.txt',
        'mixed_separators': r'C:\Users/test\file.txt',
        'tilde_path': '~/test/file.txt',
        'relative_path': './test/file.txt',
        'double_slash': '//network/path/file.txt',
        'unicode_path': 'test/ñòñ-àscii/file.txt',
    }


# Error simulation fixtures
@pytest.fixture
def error_simulation():
    """Fixture to simulate various error conditions."""
    class ErrorSimulator:
        @staticmethod
        def permission_error():
            return PermissionError("Permission denied")
        
        @staticmethod
        def file_not_found_error():
            return FileNotFoundError("File not found")
        
        @staticmethod
        def os_error():
            return OSError("OS error")
        
        @staticmethod
        def unicode_decode_error():
            return UnicodeDecodeError('utf-8', b'', 0, 1, "invalid start byte")
    
    return ErrorSimulator()


# Utility functions for tests
def create_test_file(path: Path, content: str = "test content"):
    """Helper function to create test files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_test_json(path: Path, data: Dict[str, Any]):
    """Helper function to create test JSON files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    return path


def create_test_yaml(path: Path, data: Dict[str, Any]):
    """Helper function to create test YAML files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        yaml.dump(data, f)
    return path


# Test data constants
VALID_HOOK_DATA = {
    "name": "test-hook",
    "version": "1.0.0",
    "events": ["PreToolUse", "PostToolUse"],
    "matchers": [{"pattern": "*.py"}]
}

VALID_MCP_DATA = {
    "name": "test-mcp-server",
    "command": "python",
    "args": ["-m", "test_server"],
    "env": {"TEST_ENV": "true"}
}

VALID_AGENT_FRONTMATTER = {
    "name": "test-agent",
    "version": "1.0.0",
    "description": "A test agent",
    "capabilities": ["text_processing"]
}

# Mark slow tests
slow = pytest.mark.slow
unit = pytest.mark.unit
integration = pytest.mark.integration
e2e = pytest.mark.e2e
security = pytest.mark.security
cross_platform = pytest.mark.cross_platform
performance = pytest.mark.performance