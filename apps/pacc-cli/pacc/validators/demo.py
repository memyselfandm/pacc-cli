"""Demonstration script for PACC validators."""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any

from .hooks import HooksValidator
from .mcp import MCPValidator
from .agents import AgentsValidator
from .commands import CommandsValidator


def create_sample_files() -> Dict[str, str]:
    """Create sample files for each extension type."""
    
    # Sample hook file
    sample_hook = {
        "name": "format-checker",
        "description": "Validates code formatting before tool use",
        "version": "1.0.0", 
        "eventTypes": ["PreToolUse"],
        "commands": [
            {
                "command": "ruff check {file_path}",
                "description": "Check code formatting",
                "timeout": 30
            }
        ],
        "matchers": [
            {
                "type": "regex",
                "pattern": ".*\\.(py|js|ts)$",
                "target": "file_path"
            }
        ],
        "enabled": True
    }
    
    # Sample MCP configuration
    sample_mcp = {
        "mcpServers": {
            "file-manager": {
                "command": "python",
                "args": ["-m", "file_manager_mcp"],
                "env": {
                    "LOG_LEVEL": "INFO"
                },
                "timeout": 60
            },
            "database-query": {
                "command": "/usr/local/bin/db-mcp-server",
                "args": ["--config", "/etc/db-config.json"],
                "cwd": "/var/lib/mcp",
                "restart": true
            }
        },
        "timeout": 120,
        "maxRetries": 3
    }
    
    # Sample agent file
    sample_agent = """---
name: code-reviewer
description: An AI agent that reviews code for best practices and potential issues
version: 2.1.0
author: PACC Team
tags: [code, review, quality]
tools: [file_reader, git, analyzer]
permissions: [read_files, tool_use]
parameters:
  language:
    type: choice
    description: Programming language to focus on
    choices: [python, javascript, typescript, go, rust]
    required: true
  style_guide:
    type: string
    description: Style guide to follow
    default: "pep8"
    required: false
examples:
  - input: "Review this Python function for performance issues"
    output: "I'll analyze the function for performance bottlenecks..."
  - command: "/review --language python --style_guide black"
    description: "Review code with Black style guide"
temperature: 0.3
max_tokens: 4000
---

# Code Reviewer Agent

This agent specializes in reviewing code for:

## Review Areas

- **Code Quality**: Identifies potential bugs and anti-patterns
- **Performance**: Suggests optimizations and efficiency improvements  
- **Security**: Flags potential security vulnerabilities
- **Style**: Ensures adherence to coding standards
- **Documentation**: Recommends documentation improvements

## Usage Instructions

1. Share the code you want reviewed
2. Specify the programming language
3. Optionally provide a style guide preference
4. Receive detailed feedback and suggestions

## Example Interactions

```python
def slow_function(data):
    result = []
    for item in data:
        if item not in result:
            result.append(item)
    return result
```

The agent would identify this as inefficient and suggest using a set for O(1) lookups.

## Capabilities

- Multi-language support
- Integration with popular linters and formatters
- Security vulnerability scanning
- Performance profiling suggestions
- Documentation quality assessment
"""
    
    # Sample command file
    sample_command = """---
name: deploy
description: Deploy the current project to specified environment
usage: /deploy [environment] [options]
category: deployment
aliases: [deploy-app, ship]
parameters:
  environment:
    type: choice
    description: Target deployment environment
    choices: [development, staging, production]
    required: true
  force:
    type: boolean
    description: Force deployment even if tests fail
    default: false
    required: false
  notify:
    type: boolean
    description: Send notifications on deployment completion
    default: true
    required: false
examples:
  - "/deploy staging"
  - "/deploy production --force --notify"
  - command: "/deploy development"
    description: "Deploy to development environment"
permissions: [execute_commands, network_access]
author: DevOps Team
version: 1.2.0
---

# Deploy Command

Deploy your application to the specified environment with comprehensive validation and rollback capabilities.

## Overview

The deploy command handles the complete deployment pipeline including:

- Pre-deployment validation
- Environment-specific configuration
- Database migrations  
- Service deployment
- Health checks
- Rollback on failure

## Usage

```bash
/deploy <environment> [options]
```

### Parameters

- `environment`: Target environment (development, staging, production)
- `--force`: Skip safety checks and force deployment
- `--notify`: Send completion notifications (default: true)

## Examples

### Basic Deployment
```
/deploy staging
```

### Production Deployment with Notifications
```
/deploy production --notify
```

### Force Deployment (Use with Caution)
```
/deploy staging --force
```

## Safety Features

- **Automated Testing**: Runs test suite before deployment
- **Environment Validation**: Verifies target environment health
- **Rollback Support**: Automatic rollback on deployment failure
- **Approval Gates**: Production deployments require confirmation

## Prerequisites

1. Valid deployment credentials
2. Target environment access
3. Required environment variables set
4. Database migration scripts (if applicable)

## Troubleshooting

If deployment fails:

1. Check the deployment logs
2. Verify environment connectivity
3. Ensure all required services are running
4. Contact DevOps team for production issues
"""
    
    # Create temporary files
    files = {}
    
    # Hook file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_hook, f, indent=2)
        files['hook'] = f.name
    
    # MCP file  
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mcp.json', delete=False) as f:
        json.dump(sample_mcp, f, indent=2)
        files['mcp'] = f.name
    
    # Agent file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(sample_agent)
        files['agent'] = f.name
    
    # Command file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(sample_command)
        files['command'] = f.name
    
    return files


def demonstrate_validators():
    """Demonstrate all validators with sample files."""
    print("=== PACC Validators Demonstration ===\n")
    
    # Create sample files
    print("Creating sample extension files...")
    sample_files = create_sample_files()
    
    try:
        # Initialize validators
        hooks_validator = HooksValidator()
        mcp_validator = MCPValidator()
        agents_validator = AgentsValidator()
        commands_validator = CommandsValidator()
        
        validators = [
            ("Hooks", hooks_validator, sample_files['hook']),
            ("MCP", mcp_validator, sample_files['mcp']),
            ("Agents", agents_validator, sample_files['agent']),
            ("Commands", commands_validator, sample_files['command'])
        ]
        
        # Validate each file type
        for name, validator, file_path in validators:
            print(f"\n--- {name} Validator ---")
            print(f"Validating: {Path(file_path).name}")
            
            result = validator.validate_single(file_path)
            
            print(f"✓ Valid: {result.is_valid}")
            print(f"✓ Extension Type: {result.extension_type}")
            
            if result.errors:
                print(f"✗ Errors ({len(result.errors)}):")
                for error in result.errors:
                    print(f"  - {error.code}: {error.message}")
            
            if result.warnings:
                print(f"⚠ Warnings ({len(result.warnings)}):")
                for warning in result.warnings:
                    print(f"  - {warning.code}: {warning.message}")
            
            if result.metadata:
                print(f"📊 Metadata:")
                for key, value in result.metadata.items():
                    print(f"  - {key}: {value}")
        
        # Demonstrate batch validation
        print(f"\n--- Batch Validation ---")
        all_files = list(sample_files.values())
        
        print("Testing Hooks validator on all files:")
        results = hooks_validator.validate_batch(all_files)
        valid_hooks = [r for r in results if r.is_valid]
        print(f"Found {len(valid_hooks)} valid hooks out of {len(results)} files")
        
        # Demonstrate directory validation
        print(f"\n--- Directory Validation ---")
        temp_dir = Path(sample_files['hook']).parent
        print(f"Scanning directory: {temp_dir}")
        
        for name, validator, _ in validators:
            results = validator.validate_directory(temp_dir)
            valid_count = sum(1 for r in results if r.is_valid)
            print(f"{name}: {valid_count} valid extensions found")
    
    finally:
        # Clean up temporary files
        print(f"\nCleaning up temporary files...")
        for file_path in sample_files.values():
            Path(file_path).unlink(missing_ok=True)
    
    print(f"\n=== Demonstration Complete ===")


def demonstrate_error_handling():
    """Demonstrate error handling with invalid files."""
    print("\n=== Error Handling Demonstration ===\n")
    
    # Create files with various errors
    error_cases = {
        "invalid_json": '{"invalid": json syntax}',
        "missing_file": "nonexistent.json",
        "empty_file": "",
        "large_file": "x" * (11 * 1024 * 1024),  # 11MB file
        "binary_file": b"\x00\x01\x02\x03\xff\xfe\xfd"
    }
    
    hooks_validator = HooksValidator()
    
    for case_name, content in error_cases.items():
        print(f"--- {case_name} ---")
        
        if case_name == "missing_file":
            # Test with non-existent file
            result = hooks_validator.validate_single("nonexistent.json")
        elif case_name == "binary_file":
            # Test with binary content
            with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
                f.write(content)
                temp_file = f.name
            
            try:
                result = hooks_validator.validate_single(temp_file)
            finally:
                Path(temp_file).unlink(missing_ok=True)
        else:
            # Test with text content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(content)
                temp_file = f.name
            
            try:
                result = hooks_validator.validate_single(temp_file)
            finally:
                Path(temp_file).unlink(missing_ok=True)
        
        print(f"Valid: {result.is_valid}")
        if result.errors:
            print("Errors:")
            for error in result.errors:
                print(f"  - {error.code}: {error.message}")
        print()


if __name__ == "__main__":
    demonstrate_validators()
    demonstrate_error_handling()