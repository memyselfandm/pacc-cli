"""Sample Fragment Collections for Deterministic Testing.

This module provides comprehensive sample fragment collections that install
consistently every time, ensuring reliable and repeatable test runs.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class FragmentTemplate:
    """Template for creating test fragments."""

    name: str
    content_type: str  # 'agent', 'command', 'hook', 'project_instruction'
    complexity: str = "medium"  # simple, medium, complex
    version: str = "1.0.0"
    description: str = None
    dependencies: List[str] = None
    install_behavior: str = "deterministic"  # deterministic, variable, conditional


class SampleFragmentFactory:
    """Factory for creating deterministic sample fragments."""

    @staticmethod
    def create_deterministic_collection(tmp_path: Path) -> Path:
        """Create a collection that installs consistently every time.

        This collection is designed to be completely deterministic:
        - Fixed content with no timestamps or random elements
        - Consistent file names and paths
        - Predictable dependency resolution
        - Deterministic validation behavior
        """
        collection_dir = tmp_path / "deterministic_fragments"
        collection_dir.mkdir()

        # Create agent fragments
        agents_dir = collection_dir / "agents"
        agents_dir.mkdir()

        # Simple agent fragment
        simple_agent = """---
name: test-simple-agent
version: 1.0.0
description: Simple deterministic test agent
test_metadata:
  complexity: simple
  deterministic: true
  install_order: 1
---

# Simple Test Agent

This is a simple test agent that provides consistent behavior for testing fragment installations.

## Purpose

This agent exists solely for testing fragment installation workflows. It has no external dependencies and minimal complexity to ensure deterministic behavior.

## Testing Notes

- Always installs the same way
- No dynamic content or timestamps
- Minimal validation complexity
- No external dependencies
"""
        (agents_dir / "test-simple-agent.md").write_text(simple_agent)

        # Medium complexity agent
        medium_agent = """---
name: test-medium-agent
version: 1.0.0
description: Medium complexity deterministic test agent
test_metadata:
  complexity: medium
  deterministic: true
  install_order: 2
  dependencies: []
---

# Medium Complexity Test Agent

This agent demonstrates medium complexity fragment behavior while maintaining deterministic installation.

## Features

- Structured content with multiple sections
- Consistent markdown formatting
- Predictable validation patterns
- Fixed configuration values

## Installation Behavior

This fragment is designed to:
1. Install consistently across all environments
2. Validate successfully every time
3. Generate the same installation metadata
4. Create identical file structures

## Test Configuration

```yaml
test_config:
  deterministic: true
  repeatable: true
  predictable: true
```

## Usage Instructions

This is a test fragment - it should not be used outside of testing contexts.
"""
        (agents_dir / "test-medium-agent.md").write_text(medium_agent)

        # Create command fragments
        commands_dir = collection_dir / "commands"
        commands_dir.mkdir()

        # Simple command fragment
        simple_command = """---
name: test-simple-command
version: 1.0.0
description: Simple deterministic test command
test_metadata:
  complexity: simple
  deterministic: true
  install_order: 3
---

# Simple Test Command

This command provides deterministic testing functionality.

## Command: /test-simple

A basic command that returns consistent output for testing.

### Implementation

```python
def execute_test_simple():
    return "Test command executed successfully - deterministic output"
```

### Parameters

- No parameters required
- Always returns the same result
- No side effects or external dependencies

### Expected Output

```
Test command executed successfully - deterministic output
```
"""
        (commands_dir / "test-simple-command.md").write_text(simple_command)

        # Complex command fragment
        complex_command = """---
name: test-complex-command
version: 1.0.0
description: Complex deterministic test command with validation patterns
test_metadata:
  complexity: complex
  deterministic: true
  install_order: 4
  validation_patterns:
    - frontmatter_required: true
    - implementation_section: true
    - parameter_documentation: true
---

# Complex Test Command

This command demonstrates complex fragment structure while maintaining deterministic behavior.

## Command: /test-complex

A comprehensive command that showcases various fragment features.

### Implementation

```python
import sys
from typing import Dict, List, Any

def execute_test_complex(
    mode: str = "default",
    verbose: bool = False,
    options: Dict[str, Any] = None
) -> Dict[str, Any]:
    \"\"\"Execute complex test command with predictable behavior.\"\"\"

    # Deterministic configuration
    base_config = {
        "version": "1.0.0",
        "timestamp": "2024-01-01T00:00:00Z",  # Fixed for determinism
        "environment": "test",
        "status": "success"
    }

    # Merge options deterministically
    if options:
        base_config.update(options)

    result = {
        "command": "test-complex",
        "mode": mode,
        "verbose": verbose,
        "config": base_config,
        "checksum": "abc123def456",  # Fixed for testing
        "execution_order": ["init", "process", "validate", "complete"]
    }

    return result
```

### Parameters

- `mode`: Operation mode (default: "default")
- `verbose`: Enable verbose output (default: false)
- `options`: Additional configuration dictionary

### Validation Rules

1. Command name must be "test-complex"
2. Version must be "1.0.0"
3. Must have implementation section
4. Must include parameter documentation
5. Must have deterministic output format

### Expected Output

```json
{
    "command": "test-complex",
    "mode": "default",
    "verbose": false,
    "config": {
        "version": "1.0.0",
        "timestamp": "2024-01-01T00:00:00Z",
        "environment": "test",
        "status": "success"
    },
    "checksum": "abc123def456",
    "execution_order": ["init", "process", "validate", "complete"]
}
```
"""
        (commands_dir / "test-complex-command.md").write_text(complex_command)

        # Create hook fragments
        hooks_dir = collection_dir / "hooks"
        hooks_dir.mkdir()

        # Deterministic hook
        deterministic_hook = {
            "name": "test-deterministic-hook",
            "version": "1.0.0",
            "description": "Deterministic test hook that installs consistently",
            "events": ["PreToolUse"],
            "test_metadata": {
                "complexity": "simple",
                "deterministic": True,
                "install_order": 5,
                "expected_behavior": "consistent",
            },
            "action": {
                "type": "log",
                "message": "Deterministic hook executed - consistent behavior",
                "timestamp": "fixed_for_testing",
            },
            "matchers": [{"pattern": "test-*", "behavior": "predictable"}],
        }
        (hooks_dir / "test-deterministic-hook.json").write_text(
            json.dumps(deterministic_hook, indent=2, sort_keys=True)
        )

        # Complex hook with deterministic behavior
        complex_hook = {
            "name": "test-complex-hook",
            "version": "1.0.0",
            "description": "Complex deterministic hook for comprehensive testing",
            "events": ["PreToolUse", "PostToolUse"],
            "test_metadata": {
                "complexity": "complex",
                "deterministic": True,
                "install_order": 6,
                "validation_requirements": [
                    "valid_events",
                    "consistent_matchers",
                    "deterministic_actions",
                ],
            },
            "matchers": [
                {"pattern": "test-*", "priority": 1, "behavior": "deterministic"},
                {"pattern": "fragment-*", "priority": 2, "behavior": "consistent"},
            ],
            "actions": {
                "pre_tool_use": {
                    "type": "validate",
                    "message": "Pre-hook validation - deterministic",
                    "checksum": "pre_abc123",
                },
                "post_tool_use": {
                    "type": "log",
                    "message": "Post-hook logging - consistent output",
                    "checksum": "post_def456",
                },
            },
            "configuration": {
                "timeout": 1000,
                "retries": 3,
                "deterministic_mode": True,
                "test_environment": True,
            },
        }
        (hooks_dir / "test-complex-hook.json").write_text(
            json.dumps(complex_hook, indent=2, sort_keys=True)
        )

        # Create collection manifest
        manifest = {
            "name": "deterministic-test-collection",
            "version": "1.0.0",
            "description": "Sample fragments that install consistently every time",
            "test_metadata": {
                "purpose": "integration_testing",
                "deterministic": True,
                "consistent_behavior": True,
                "created_for": "PACC-56",
            },
            "fragments": [
                {
                    "name": "test-simple-agent",
                    "type": "agent",
                    "path": "agents/test-simple-agent.md",
                    "install_order": 1,
                    "complexity": "simple",
                },
                {
                    "name": "test-medium-agent",
                    "type": "agent",
                    "path": "agents/test-medium-agent.md",
                    "install_order": 2,
                    "complexity": "medium",
                },
                {
                    "name": "test-simple-command",
                    "type": "command",
                    "path": "commands/test-simple-command.md",
                    "install_order": 3,
                    "complexity": "simple",
                },
                {
                    "name": "test-complex-command",
                    "type": "command",
                    "path": "commands/test-complex-command.md",
                    "install_order": 4,
                    "complexity": "complex",
                },
                {
                    "name": "test-deterministic-hook",
                    "type": "hook",
                    "path": "hooks/test-deterministic-hook.json",
                    "install_order": 5,
                    "complexity": "simple",
                },
                {
                    "name": "test-complex-hook",
                    "type": "hook",
                    "path": "hooks/test-complex-hook.json",
                    "install_order": 6,
                    "complexity": "complex",
                },
            ],
            "installation_characteristics": {
                "deterministic": True,
                "repeatable": True,
                "consistent_order": True,
                "no_random_elements": True,
                "fixed_timestamps": True,
                "predictable_validation": True,
            },
        }

        (collection_dir / "fragment-collection.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True)
        )

        return collection_dir

    @staticmethod
    def create_edge_case_collection(tmp_path: Path) -> Path:
        """Create fragments that test edge cases but with deterministic behavior."""
        collection_dir = tmp_path / "edge_case_fragments"
        collection_dir.mkdir()

        # Create agents directory
        agents_dir = collection_dir / "agents"
        agents_dir.mkdir()

        # Edge case: minimal valid agent
        minimal_agent = """---
name: minimal-test-agent
version: 1.0.0
description: Minimal valid agent for edge case testing
---

# Minimal Agent

Minimal content.
"""
        (agents_dir / "minimal-test-agent.md").write_text(minimal_agent)

        # Edge case: agent with special characters (but deterministic)
        special_agent = """---
name: special-chars-agent
version: 1.0.0
description: "Agent with special characters: !@#$%^&*()_+-=[]{}|;:,.<>?"
test_metadata:
  special_characters: true
  deterministic: true
---

# Agent With Special Characters

This agent tests handling of special characters in a deterministic way.

## Special Content

- Symbols: !@#$%^&*()_+-=[]{}|;:,.<>?
- Unicode: αβγδε ∑∏∫√∞
- Quotes: "double" 'single' `backtick`
- Fixed for testing: always the same characters

## Deterministic Behavior

All special characters are fixed for consistent testing.
"""
        (agents_dir / "special-chars-agent.md").write_text(special_agent)

        # Create commands directory
        commands_dir = collection_dir / "commands"
        commands_dir.mkdir()

        # Edge case: command with no parameters
        no_params_command = """---
name: no-params-command
version: 1.0.0
description: Command with no parameters for edge case testing
---

# No Parameters Command

## Command: /no-params

A command that takes no parameters.

### Implementation

```python
def execute_no_params():
    return {"result": "success", "timestamp": "fixed_for_testing"}
```

### Expected Output

```json
{"result": "success", "timestamp": "fixed_for_testing"}
```
"""
        (commands_dir / "no-params-command.md").write_text(no_params_command)

        # Create hooks directory
        hooks_dir = collection_dir / "hooks"
        hooks_dir.mkdir()

        # Edge case: hook with minimal configuration
        minimal_hook = {
            "name": "minimal-hook",
            "version": "1.0.0",
            "description": "Minimal hook configuration",
            "events": ["PreToolUse"],
        }
        (hooks_dir / "minimal-hook.json").write_text(
            json.dumps(minimal_hook, indent=2, sort_keys=True)
        )

        # Collection manifest
        manifest = {
            "name": "edge-case-test-collection",
            "version": "1.0.0",
            "description": "Edge case fragments with deterministic behavior",
            "test_metadata": {
                "purpose": "edge_case_testing",
                "deterministic": True,
                "edge_cases": [
                    "minimal_content",
                    "special_characters",
                    "no_parameters",
                    "minimal_configuration",
                ],
            },
            "fragments": [
                {
                    "name": "minimal-test-agent",
                    "type": "agent",
                    "path": "agents/minimal-test-agent.md",
                    "edge_case": "minimal_content",
                },
                {
                    "name": "special-chars-agent",
                    "type": "agent",
                    "path": "agents/special-chars-agent.md",
                    "edge_case": "special_characters",
                },
                {
                    "name": "no-params-command",
                    "type": "command",
                    "path": "commands/no-params-command.md",
                    "edge_case": "no_parameters",
                },
                {
                    "name": "minimal-hook",
                    "type": "hook",
                    "path": "hooks/minimal-hook.json",
                    "edge_case": "minimal_configuration",
                },
            ],
        }

        (collection_dir / "fragment-collection.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True)
        )

        return collection_dir

    @staticmethod
    def create_versioned_collection(tmp_path: Path) -> Path:
        """Create fragments with version management features."""
        collection_dir = tmp_path / "versioned_fragments"
        collection_dir.mkdir()

        # Create agents directory
        agents_dir = collection_dir / "agents"
        agents_dir.mkdir()

        # Version 1.0.0 agent
        v1_agent = """---
name: versioned-test-agent
version: 1.0.0
description: Test agent for version management (v1.0.0)
test_metadata:
  version_series: "1.x"
  deterministic: true
  changelog:
    - "1.0.0: Initial version for testing"
---

# Versioned Test Agent (v1.0.0)

This agent demonstrates version management in fragments.

## Version Features

- Version: 1.0.0
- Initial implementation
- Basic functionality
- Deterministic behavior

## Version History

- 1.0.0: Initial version for testing
"""
        (agents_dir / "versioned-test-agent-v1.md").write_text(v1_agent)

        # Version 1.1.0 agent
        v11_agent = """---
name: versioned-test-agent
version: 1.1.0
description: Test agent for version management (v1.1.0)
test_metadata:
  version_series: "1.x"
  deterministic: true
  changelog:
    - "1.0.0: Initial version for testing"
    - "1.1.0: Added enhanced features"
---

# Versioned Test Agent (v1.1.0)

This agent demonstrates version management with enhancements.

## Version Features

- Version: 1.1.0
- Enhanced implementation
- Additional functionality
- Backward compatible
- Deterministic behavior

## Enhancements in v1.1.0

- Improved error handling
- Enhanced documentation
- Better test coverage

## Version History

- 1.0.0: Initial version for testing
- 1.1.0: Added enhanced features
"""
        (agents_dir / "versioned-test-agent-v11.md").write_text(v11_agent)

        # Version 2.0.0 agent
        v2_agent = """---
name: versioned-test-agent
version: 2.0.0
description: Test agent for version management (v2.0.0)
test_metadata:
  version_series: "2.x"
  deterministic: true
  breaking_changes: true
  changelog:
    - "1.0.0: Initial version for testing"
    - "1.1.0: Added enhanced features"
    - "2.0.0: Major rewrite with breaking changes"
---

# Versioned Test Agent (v2.0.0)

This agent demonstrates major version changes.

## Version Features

- Version: 2.0.0
- Complete rewrite
- Breaking changes
- New architecture
- Deterministic behavior

## Breaking Changes in v2.0.0

- Changed API interface
- New configuration format
- Updated dependencies
- Modified behavior patterns

## Version History

- 1.0.0: Initial version for testing
- 1.1.0: Added enhanced features
- 2.0.0: Major rewrite with breaking changes
"""
        (agents_dir / "versioned-test-agent-v2.md").write_text(v2_agent)

        # Collection manifest
        manifest = {
            "name": "versioned-test-collection",
            "version": "2.0.0",
            "description": "Fragments demonstrating version management",
            "test_metadata": {
                "purpose": "version_testing",
                "deterministic": True,
                "versions_included": ["1.0.0", "1.1.0", "2.0.0"],
                "breaking_changes": True,
            },
            "fragments": [
                {
                    "name": "versioned-test-agent",
                    "type": "agent",
                    "versions": [
                        {
                            "version": "1.0.0",
                            "path": "agents/versioned-test-agent-v1.md",
                            "status": "stable",
                        },
                        {
                            "version": "1.1.0",
                            "path": "agents/versioned-test-agent-v11.md",
                            "status": "stable",
                        },
                        {
                            "version": "2.0.0",
                            "path": "agents/versioned-test-agent-v2.md",
                            "status": "latest",
                            "breaking_changes": True,
                        },
                    ],
                }
            ],
            "version_management": {
                "strategy": "semantic_versioning",
                "backward_compatibility": "within_major",
                "breaking_changes_policy": "major_version_only",
            },
        }

        (collection_dir / "fragment-collection.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True)
        )

        return collection_dir

    @staticmethod
    def create_dependency_collection(tmp_path: Path) -> Path:
        """Create fragments that test dependency resolution."""
        collection_dir = tmp_path / "dependency_fragments"
        collection_dir.mkdir()

        # Create agents directory
        agents_dir = collection_dir / "agents"
        agents_dir.mkdir()

        # Base agent (no dependencies)
        base_agent = """---
name: base-agent
version: 1.0.0
description: Base agent with no dependencies
test_metadata:
  dependency_level: 0
  deterministic: true
---

# Base Agent

This agent has no dependencies and can be installed independently.

## Features

- Self-contained functionality
- No external dependencies
- Deterministic installation
- Provides base services
"""
        (agents_dir / "base-agent.md").write_text(base_agent)

        # Dependent agent
        dependent_agent = """---
name: dependent-agent
version: 1.0.0
description: Agent that depends on base-agent
dependencies:
  - base-agent
test_metadata:
  dependency_level: 1
  deterministic: true
  requires: ["base-agent"]
---

# Dependent Agent

This agent depends on the base-agent for functionality.

## Dependencies

- base-agent: Required for core functionality

## Features

- Extends base-agent capabilities
- Deterministic dependency resolution
- Predictable installation order
"""
        (agents_dir / "dependent-agent.md").write_text(dependent_agent)

        # Create commands directory
        commands_dir = collection_dir / "commands"
        commands_dir.mkdir()

        # Command that uses agents
        integrated_command = """---
name: integrated-command
version: 1.0.0
description: Command that integrates with agents
dependencies:
  - base-agent
  - dependent-agent
test_metadata:
  dependency_level: 2
  deterministic: true
  integration_type: "agent_command"
---

# Integrated Command

## Command: /integrated

This command integrates with agent functionality.

### Dependencies

- base-agent: Provides core services
- dependent-agent: Provides extended functionality

### Implementation

```python
def execute_integrated():
    # Uses deterministic agent integration
    return {
        "status": "success",
        "agents_used": ["base-agent", "dependent-agent"],
        "timestamp": "fixed_for_testing"
    }
```
"""
        (commands_dir / "integrated-command.md").write_text(integrated_command)

        # Collection manifest with dependency resolution
        manifest = {
            "name": "dependency-test-collection",
            "version": "1.0.0",
            "description": "Fragments demonstrating dependency resolution",
            "test_metadata": {
                "purpose": "dependency_testing",
                "deterministic": True,
                "dependency_graph": "linear",
                "resolution_strategy": "topological_sort",
            },
            "fragments": [
                {
                    "name": "base-agent",
                    "type": "agent",
                    "path": "agents/base-agent.md",
                    "dependencies": [],
                    "dependency_level": 0,
                },
                {
                    "name": "dependent-agent",
                    "type": "agent",
                    "path": "agents/dependent-agent.md",
                    "dependencies": ["base-agent"],
                    "dependency_level": 1,
                },
                {
                    "name": "integrated-command",
                    "type": "command",
                    "path": "commands/integrated-command.md",
                    "dependencies": ["base-agent", "dependent-agent"],
                    "dependency_level": 2,
                },
            ],
            "dependency_resolution": {
                "strategy": "strict_order",
                "allow_circular": False,
                "deterministic": True,
                "install_order": ["base-agent", "dependent-agent", "integrated-command"],
            },
        }

        (collection_dir / "fragment-collection.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True)
        )

        return collection_dir


def create_comprehensive_test_suite(tmp_path: Path) -> Dict[str, Path]:
    """Create a comprehensive suite of sample fragment collections.

    Returns:
        Dictionary mapping collection names to their paths
    """
    collections = {}

    # Create each type of collection
    collections["deterministic"] = SampleFragmentFactory.create_deterministic_collection(tmp_path)
    collections["edge_cases"] = SampleFragmentFactory.create_edge_case_collection(tmp_path)
    collections["versioned"] = SampleFragmentFactory.create_versioned_collection(tmp_path)
    collections["dependencies"] = SampleFragmentFactory.create_dependency_collection(tmp_path)

    # Create master index
    master_index = {
        "name": "comprehensive-fragment-test-suite",
        "version": "1.0.0",
        "description": "Complete suite of sample fragments for testing",
        "created_for": "PACC-56",
        "collections": [
            {
                "name": "deterministic",
                "path": str(collections["deterministic"]),
                "purpose": "Basic deterministic installation testing",
                "fragment_count": 6,
            },
            {
                "name": "edge_cases",
                "path": str(collections["edge_cases"]),
                "purpose": "Edge case and boundary testing",
                "fragment_count": 4,
            },
            {
                "name": "versioned",
                "path": str(collections["versioned"]),
                "purpose": "Version management and upgrade testing",
                "fragment_count": 3,
            },
            {
                "name": "dependencies",
                "path": str(collections["dependencies"]),
                "purpose": "Dependency resolution and ordering testing",
                "fragment_count": 3,
            },
        ],
        "total_fragments": 16,
        "test_characteristics": {
            "deterministic": True,
            "repeatable": True,
            "comprehensive_coverage": True,
            "edge_case_testing": True,
            "version_testing": True,
            "dependency_testing": True,
        },
    }

    master_index_path = tmp_path / "fragment_test_suite_index.json"
    master_index_path.write_text(json.dumps(master_index, indent=2, sort_keys=True))

    collections["master_index"] = master_index_path

    return collections
