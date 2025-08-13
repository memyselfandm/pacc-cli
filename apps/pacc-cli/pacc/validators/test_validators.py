"""Comprehensive test cases for PACC validators."""

import json
import tempfile
import yaml
from pathlib import Path
from typing import Dict, Any

from .base import ValidationResult
from .hooks import HooksValidator
from .mcp import MCPValidator
from .agents import AgentsValidator  
from .commands import CommandsValidator


class ValidatorTestSuite:
    """Test suite for all PACC validators with comprehensive edge cases."""
    
    def __init__(self):
        """Initialize test suite."""
        self.hooks_validator = HooksValidator()
        self.mcp_validator = MCPValidator()
        self.agents_validator = AgentsValidator()
        self.commands_validator = CommandsValidator()
        
        self.test_results = {
            "hooks": [],
            "mcp": [],
            "agents": [],
            "commands": []
        }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all validator tests and return results."""
        print("Running PACC Validator Test Suite...")
        
        # Test each validator
        self._test_hooks_validator()
        self._test_mcp_validator()
        self._test_agents_validator()
        self._test_commands_validator()
        
        # Generate summary
        summary = self._generate_test_summary()
        return summary
    
    def _test_hooks_validator(self) -> None:
        """Test hooks validator with various scenarios."""
        print("  Testing Hooks Validator...")
        
        # Test cases for hooks
        test_cases = [
            # Valid hook
            {
                "name": "valid_hook",
                "data": {
                    "name": "test-hook",
                    "description": "A test hook for validation",
                    "eventTypes": ["PreToolUse"],
                    "commands": ["echo 'Hello World'"],
                    "version": "1.0.0"
                },
                "should_pass": True
            },
            # Hook with matchers
            {
                "name": "hook_with_matchers",
                "data": {
                    "name": "matcher-hook",
                    "description": "Hook with matchers",
                    "eventTypes": ["PostToolUse"],
                    "commands": [{"command": "echo 'test'", "description": "Test command"}],
                    "matchers": [
                        {"type": "exact", "pattern": "test"},
                        {"type": "regex", "pattern": "test.*"}
                    ]
                },
                "should_pass": True
            },
            # Invalid JSON structure
            {
                "name": "invalid_json",
                "data": "invalid json content",
                "should_pass": False,
                "is_json": False
            },
            # Missing required fields
            {
                "name": "missing_fields",
                "data": {
                    "name": "incomplete-hook"
                    # Missing eventTypes and commands
                },
                "should_pass": False
            },
            # Invalid event types
            {
                "name": "invalid_event_types",
                "data": {
                    "name": "bad-events",
                    "description": "Hook with invalid events",
                    "eventTypes": ["InvalidEvent"],
                    "commands": ["echo test"]
                },
                "should_pass": False
            },
            # Dangerous command
            {
                "name": "dangerous_command",
                "data": {
                    "name": "dangerous-hook",
                    "description": "Hook with dangerous command",
                    "eventTypes": ["PreToolUse"],
                    "commands": ["rm -rf /"]
                },
                "should_pass": True,  # Should pass validation but have warnings
                "expect_warnings": True
            },
            # Invalid regex in matcher
            {
                "name": "invalid_regex_matcher",
                "data": {
                    "name": "bad-regex",
                    "description": "Hook with invalid regex",
                    "eventTypes": ["PreToolUse"],
                    "commands": ["echo test"],
                    "matchers": [{"type": "regex", "pattern": "[invalid"}]
                },
                "should_pass": False
            }
        ]
        
        for test_case in test_cases:
            result = self._run_single_test("hooks", test_case)
            self.test_results["hooks"].append(result)
    
    def _test_mcp_validator(self) -> None:
        """Test MCP validator with various scenarios."""
        print("  Testing MCP Validator...")
        
        test_cases = [
            # Valid MCP configuration
            {
                "name": "valid_mcp",
                "data": {
                    "mcpServers": {
                        "test-server": {
                            "command": "python",
                            "args": ["-m", "test_server"],
                            "env": {"TEST_VAR": "value"}
                        }
                    }
                },
                "should_pass": True
            },
            # MCP with multiple servers
            {
                "name": "multiple_servers",
                "data": {
                    "mcpServers": {
                        "server1": {
                            "command": "node",
                            "args": ["server1.js"]
                        },
                        "server2": {
                            "command": "python",
                            "args": ["-m", "server2"],
                            "timeout": 30
                        }
                    },
                    "timeout": 60,
                    "maxRetries": 3
                },
                "should_pass": True
            },
            # Missing mcpServers
            {
                "name": "missing_servers",
                "data": {
                    "someOtherField": "value"
                },
                "should_pass": False
            },
            # Invalid server config
            {
                "name": "invalid_server_config",
                "data": {
                    "mcpServers": {
                        "bad-server": "not an object"
                    }
                },
                "should_pass": False
            },
            # Missing command
            {
                "name": "missing_command",
                "data": {
                    "mcpServers": {
                        "incomplete-server": {
                            "args": ["some", "args"]
                        }
                    }
                },
                "should_pass": False
            },
            # Invalid timeout
            {
                "name": "invalid_timeout",
                "data": {
                    "mcpServers": {
                        "server": {
                            "command": "python",
                            "timeout": -5
                        }
                    }
                },
                "should_pass": False
            },
            # Command with shell characters (should warn)
            {
                "name": "shell_command",
                "data": {
                    "mcpServers": {
                        "shell-server": {
                            "command": "python -m server && echo done"
                        }
                    }
                },
                "should_pass": True,
                "expect_warnings": True
            }
        ]
        
        for test_case in test_cases:
            result = self._run_single_test("mcp", test_case)
            self.test_results["mcp"].append(result)
    
    def _test_agents_validator(self) -> None:
        """Test agents validator with various scenarios."""
        print("  Testing Agents Validator...")
        
        test_cases = [
            # Valid agent
            {
                "name": "valid_agent",
                "data": """---
name: test-agent
description: A test agent for validation
version: 1.0.0
tools: [search, calculator]
---

# Test Agent

This is a test agent that demonstrates proper formatting.

## Usage

The agent helps with testing validation logic.
""",
                "should_pass": True,
                "is_yaml_md": True
            },
            # Agent with parameters
            {
                "name": "agent_with_parameters",
                "data": """---
name: parameterized-agent
description: Agent with parameters
parameters:
  query:
    type: string
    description: Search query
    required: true
  limit:
    type: integer
    description: Result limit
    default: 10
examples:
  - input: "search for cats"
    output: "Found 5 cat results"
---

# Parameterized Agent

This agent accepts parameters.
""",
                "should_pass": True,
                "is_yaml_md": True
            },
            # Missing frontmatter
            {
                "name": "missing_frontmatter",
                "data": """# Agent Without Frontmatter

This agent is missing YAML frontmatter.
""",
                "should_pass": False,
                "is_yaml_md": True
            },
            # Invalid YAML
            {
                "name": "invalid_yaml",
                "data": """---
name: bad-yaml
description: Agent with invalid YAML
invalid: [unclosed list
---

# Agent content
""",
                "should_pass": False,
                "is_yaml_md": True
            },
            # Missing required fields
            {
                "name": "missing_required_fields",
                "data": """---
name: incomplete-agent
# Missing description
---

# Incomplete Agent
""",
                "should_pass": False,
                "is_yaml_md": True
            },
            # Invalid permissions
            {
                "name": "invalid_permissions",
                "data": """---
name: bad-permissions
description: Agent with invalid permissions
permissions: [invalid_permission, read_files]
---

# Agent with bad permissions
""",
                "should_pass": False,
                "is_yaml_md": True
            },
            # Invalid temperature
            {
                "name": "invalid_temperature",
                "data": """---
name: bad-temp-agent
description: Agent with invalid temperature
temperature: 2.0
---

# Agent with bad temperature
""",
                "should_pass": False,
                "is_yaml_md": True
            }
        ]
        
        for test_case in test_cases:
            result = self._run_single_test("agents", test_case)
            self.test_results["agents"].append(result)
    
    def _test_commands_validator(self) -> None:
        """Test commands validator with various scenarios."""
        print("  Testing Commands Validator...")
        
        test_cases = [
            # Valid command with frontmatter
            {
                "name": "valid_command_frontmatter",
                "data": """---
name: test-cmd
description: A test command
usage: /test-cmd [options]
examples:
  - /test-cmd --help
  - /test-cmd --verbose
parameters:
  verbose:
    type: boolean
    description: Enable verbose output
    required: false
---

# Test Command

This is a test slash command.

## Usage

Use `/test-cmd` to run the test.
""",
                "should_pass": True,
                "is_yaml_md": True
            },
            # Valid simple command
            {
                "name": "valid_simple_command",
                "data": """# /test-simple

A simple test command without frontmatter.

Usage: `/test-simple`

This command demonstrates the simple format.
""",
                "should_pass": True,
                "is_yaml_md": True
            },
            # Command with invalid name
            {
                "name": "invalid_command_name",
                "data": """---
name: 123-invalid
description: Command with invalid name
---

# Invalid Command
""",
                "should_pass": False,
                "is_yaml_md": True
            },
            # Reserved command name
            {
                "name": "reserved_name",
                "data": """---
name: help
description: Using reserved name
---

# Reserved Name Command
""",
                "should_pass": False,
                "is_yaml_md": True
            },
            # Missing required fields
            {
                "name": "missing_description",
                "data": """---
name: no-desc
# Missing description
---

# Command without description
""",
                "should_pass": False,
                "is_yaml_md": True
            },
            # Invalid parameter type
            {
                "name": "invalid_param_type",
                "data": """---
name: bad-param
description: Command with invalid parameter type
parameters:
  bad_param:
    type: invalid_type
    description: Bad parameter
---

# Command with bad parameter
""",
                "should_pass": False,
                "is_yaml_md": True
            },
            # Choice parameter without choices
            {
                "name": "choice_without_options",
                "data": """---
name: choice-cmd
description: Choice command without options
parameters:
  mode:
    type: choice
    description: Operation mode
---

# Choice command
""",
                "should_pass": False,
                "is_yaml_md": True
            }
        ]
        
        for test_case in test_cases:
            result = self._run_single_test("commands", test_case)
            self.test_results["commands"].append(result)
    
    def _run_single_test(self, validator_type: str, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single test case."""
        test_name = test_case["name"]
        data = test_case["data"]
        should_pass = test_case["should_pass"]
        expect_warnings = test_case.get("expect_warnings", False)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            if test_case.get("is_yaml_md", False):
                # For markdown files
                f.name = f.name.replace('.json', '.md')
                f.write(data)
            elif test_case.get("is_json", True):
                # For JSON files
                json.dump(data, f, indent=2)
            else:
                # For raw content
                f.write(data)
            
            temp_file = f.name
        
        try:
            # Get appropriate validator
            if validator_type == "hooks":
                validator = self.hooks_validator
            elif validator_type == "mcp":
                validator = self.mcp_validator
            elif validator_type == "agents":
                validator = self.agents_validator
            elif validator_type == "commands":
                validator = self.commands_validator
            else:
                raise ValueError(f"Unknown validator type: {validator_type}")
            
            # Run validation
            result = validator.validate_single(temp_file)
            
            # Check if result matches expectation
            test_passed = False
            if should_pass:
                test_passed = result.is_valid
                if expect_warnings:
                    test_passed = test_passed and len(result.warnings) > 0
            else:
                test_passed = not result.is_valid
            
            return {
                "name": test_name,
                "passed": test_passed,
                "validator_result": result,
                "expected_pass": should_pass,
                "expected_warnings": expect_warnings,
                "error_count": len(result.errors),
                "warning_count": len(result.warnings)
            }
            
        finally:
            # Clean up
            Path(temp_file).unlink(missing_ok=True)
    
    def _generate_test_summary(self) -> Dict[str, Any]:
        """Generate a summary of all test results."""
        summary = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "by_validator": {}
        }
        
        for validator_type, results in self.test_results.items():
            validator_summary = {
                "total": len(results),
                "passed": sum(1 for r in results if r["passed"]),
                "failed": sum(1 for r in results if not r["passed"]),
                "tests": results
            }
            
            summary["by_validator"][validator_type] = validator_summary
            summary["total_tests"] += validator_summary["total"]
            summary["passed_tests"] += validator_summary["passed"]
            summary["failed_tests"] += validator_summary["failed"]
        
        return summary
    
    def print_test_results(self, summary: Dict[str, Any]) -> None:
        """Print formatted test results."""
        print(f"\n=== PACC Validator Test Results ===")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Success Rate: {summary['passed_tests']/summary['total_tests']*100:.1f}%")
        
        for validator_type, results in summary["by_validator"].items():
            print(f"\n{validator_type.upper()} Validator:")
            print(f"  Passed: {results['passed']}/{results['total']}")
            
            # Show failed tests
            failed_tests = [t for t in results["tests"] if not t["passed"]]
            if failed_tests:
                print(f"  Failed tests:")
                for test in failed_tests:
                    print(f"    - {test['name']}")
                    if test["validator_result"].errors:
                        for error in test["validator_result"].errors[:2]:  # Show first 2 errors
                            print(f"      Error: {error.message}")


def run_validator_tests():
    """Main function to run all validator tests."""
    test_suite = ValidatorTestSuite()
    summary = test_suite.run_all_tests()
    test_suite.print_test_results(summary)
    return summary


if __name__ == "__main__":
    run_validator_tests()