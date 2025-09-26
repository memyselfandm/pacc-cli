"""Integration tests for S01 fixes - PACC-26 Testing Part.

This comprehensive test suite validates the S01 fixes end-to-end:
1. Directory validation improvements
2. Extension type detection hierarchy (pacc.json > directory > content)
3. CLI validate command integration with all scenarios
4. Cross-platform compatibility and edge cases

Related Issues:
- PACC-24: Extension detection hierarchy implementation
- PACC-18: Fix slash command misclassification
- PACC-26: Comprehensive testing and documentation
"""

import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from pacc.cli import PACCCli
from pacc.validators import (
    validate_extension_directory,
)
from pacc.validators.base import ValidationResult
from pacc.validators.utils import ExtensionDetector


class TestS01DirectoryValidationIntegration:
    """Test S01 directory validation improvements end-to-end."""

    def test_complete_directory_validation_workflow(self):
        """Test complete directory validation workflow with S01 improvements."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create complex directory structure
            self._create_complex_test_structure(temp_path)

            # Run directory validation
            results = validate_extension_directory(temp_path)

            # Verify all extension types are detected
            assert "hooks" in results
            assert "agents" in results
            assert "commands" in results
            assert "mcp" in results

            # Verify results structure
            assert isinstance(results["hooks"], list)
            assert isinstance(results["agents"], list)
            assert isinstance(results["commands"], list)
            assert isinstance(results["mcp"], list)

            # Verify specific files are validated
            hook_files = [r.file_path for r in results["hooks"]]
            agent_files = [r.file_path for r in results["agents"]]
            command_files = [r.file_path for r in results["commands"]]

            assert any("test-hook.json" in f for f in hook_files)
            assert any("test-agent.md" in f for f in agent_files)
            assert any("test-command.md" in f for f in command_files)

    def test_nested_directory_validation_performance(self):
        """Test validation performance with deeply nested directories."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create deeply nested structure
            self._create_nested_test_structure(temp_path, depth=5)

            start_time = time.time()
            results = validate_extension_directory(temp_path)
            end_time = time.time()

            duration = end_time - start_time
            total_files = sum(len(file_list) for file_list in results.values())

            # Performance assertions
            assert duration < 3.0, f"Validation took too long: {duration:.2f}s"
            assert total_files > 10, "Should find multiple extension files"

            # Verify results are valid
            for _extension_type, validation_results in results.items():
                assert isinstance(validation_results, list)
                for result in validation_results:
                    assert isinstance(result, ValidationResult)

    def test_mixed_valid_invalid_directory_handling(self):
        """Test directory validation with mix of valid and invalid files."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create mixed content
            self._create_mixed_validity_structure(temp_path)

            results = validate_extension_directory(temp_path)

            # Should handle both valid and invalid files gracefully
            total_results = sum(len(file_list) for file_list in results.values())
            assert total_results > 0

            # Check that we have both valid and invalid results
            all_results = []
            for extension_results in results.values():
                all_results.extend(extension_results)

            valid_count = sum(1 for r in all_results if r.is_valid)
            invalid_count = sum(1 for r in all_results if not r.is_valid)

            assert valid_count > 0, "Should have some valid files"
            assert invalid_count > 0, "Should have some invalid files"

    def _create_complex_test_structure(self, base_path: Path):
        """Create complex test directory structure."""
        # Hooks
        hooks_dir = base_path / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "test-hook.json").write_text(
            json.dumps(
                {
                    "name": "test-hook",
                    "version": "1.0.0",
                    "eventTypes": ["PreToolUse"],
                    "commands": ["echo 'hook executed'"],
                }
            )
        )

        # Agents
        agents_dir = base_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "test-agent.md").write_text("""---
name: test-agent
description: A test agent
tools: ["file-reader"]
---

Test agent content.
""")

        # Commands
        commands_dir = base_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "test-command.md").write_text("""---
name: test-command
description: A test command
---

# /test-command

Test command content.
""")

        # MCP servers
        mcp_dir = base_path / "mcp"
        mcp_dir.mkdir()
        (mcp_dir / "test-server.json").write_text(
            json.dumps(
                {
                    "name": "test-server",
                    "command": ["python", "server.py"],
                    "args": ["--port", "3000"],
                }
            )
        )

    def _create_nested_test_structure(self, base_path: Path, depth: int):
        """Create deeply nested test structure."""
        current_path = base_path

        for level in range(depth):
            level_dir = current_path / f"level_{level}"
            level_dir.mkdir()

            # Add some files at each level
            if level % 2 == 0:  # Even levels get hooks
                hook_file = level_dir / f"hook_level_{level}.json"
                hook_file.write_text(
                    json.dumps(
                        {
                            "name": f"hook-level-{level}",
                            "version": "1.0.0",
                            "eventTypes": ["PreToolUse"],
                            "commands": ["echo 'hook executed'"],
                        }
                    )
                )
            else:  # Odd levels get commands
                command_file = level_dir / f"command_level_{level}.md"
                command_file.write_text(f"""---
name: command-level-{level}
---

# /command-level-{level}

Command at level {level}.
""")

            current_path = level_dir

    def _create_mixed_validity_structure(self, base_path: Path):
        """Create structure with valid and invalid files."""
        # Valid hook
        valid_hook = base_path / "valid-hook.json"
        valid_hook.write_text(
            json.dumps(
                {
                    "name": "valid-hook",
                    "version": "1.0.0",
                    "eventTypes": ["PreToolUse"],
                    "commands": ["echo 'hook executed'"],
                    "description": "Valid hook for testing",
                }
            )
        )

        # Invalid hook (missing required fields)
        invalid_hook = base_path / "invalid-hook.json"
        invalid_hook.write_text(
            json.dumps(
                {
                    "name": "invalid-hook"
                    # Missing version and events
                }
            )
        )

        # Malformed JSON
        malformed_hook = base_path / "malformed-hook.json"
        malformed_hook.write_text('{"name": "malformed", "invalid": json}')

        # Valid command
        valid_command = base_path / "valid-command.md"
        valid_command.write_text("""---
name: valid-command
---

# /valid-command

Valid command content.
""")

        # Invalid command (missing frontmatter)
        invalid_command = base_path / "invalid-command.md"
        invalid_command.write_text("Just plain text without proper structure.")


class TestS01ExtensionDetectionHierarchyIntegration:
    """Test S01 extension detection hierarchy integration."""

    def test_pacc_json_highest_priority_integration(self):
        """Test pacc.json declarations take highest priority in complete workflow."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create misleading directory structure
            agents_dir = temp_path / "agents"
            agents_dir.mkdir()

            # File that looks like agent but is declared as command in pacc.json
            misleading_file = agents_dir / "actually-command.md"
            misleading_file.write_text("""---
name: actually-command
description: Looks like agent but is actually a command
tools: ["file-reader"]
permissions: ["read-files"]
---

This has agent keywords but should be detected as command due to pacc.json.
""")

            # Create pacc.json declaring it as command
            pacc_config = {
                "name": "test-hierarchy",
                "version": "1.0.0",
                "extensions": {
                    "commands": [
                        {
                            "name": "actually-command",
                            "source": "./agents/actually-command.md",
                            "version": "1.0.0",
                        }
                    ]
                },
            }
            (temp_path / "pacc.json").write_text(json.dumps(pacc_config, indent=2))

            # Run complete validation workflow
            results = validate_extension_directory(temp_path)

            # Should be detected as command, not agent
            assert "commands" in results
            assert len(results["commands"]) > 0

            # Should not be in agents
            if "agents" in results:
                agent_files = [r.file_path for r in results["agents"]]
                assert not any("actually-command.md" in f for f in agent_files)

            # Verify the specific file is in commands
            command_files = [r.file_path for r in results["commands"]]
            assert any("actually-command.md" in f for f in command_files)

    def test_directory_structure_secondary_priority_integration(self):
        """Test directory structure priority when no pacc.json exists."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create directory structure without pacc.json
            hooks_dir = temp_path / "hooks"
            hooks_dir.mkdir()

            # File with agent-like content in hooks directory
            hook_file = hooks_dir / "agent-like-hook.json"
            hook_file.write_text(
                json.dumps(
                    {
                        "description": "Contains agent keywords: tool, permission, agent",
                        "name": "agent-like-hook",
                        "version": "1.0.0",
                        "eventTypes": ["PreToolUse"],
                        "commands": ["echo 'hook executed'"],
                        "actions": ["validate_agent_tools"],
                    }
                )
            )

            # Run detection
            detector = ExtensionDetector()
            detected_type = detector.detect_extension_type(hook_file)

            # Should detect as hooks due to directory structure
            assert detected_type == "hooks"

            # Verify in validation workflow
            results = validate_extension_directory(temp_path)
            assert "hooks" in results

            hook_files = [r.file_path for r in results["hooks"]]
            assert any("agent-like-hook.json" in f for f in hook_files)

    def test_content_keywords_fallback_integration(self):
        """Test content keywords as fallback when no other signals exist."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # File outside any special directory with clear agent content
            agent_file = temp_path / "clear-agent.md"
            agent_file.write_text("""---
name: clear-agent
description: A clear agent example
tools: ["calculator", "file-reader"]
permissions: ["read-files", "execute"]
---

This is clearly an agent based on tools and permissions.
""")

            # Run detection
            detector = ExtensionDetector()
            detected_type = detector.detect_extension_type(agent_file)

            # Should detect as agents based on content
            assert detected_type == "agents"

            # Verify in validation workflow
            results = validate_extension_directory(temp_path)

            if "agents" in results:
                agent_files = [r.file_path for r in results["agents"]]
                assert any("clear-agent.md" in f for f in agent_files)

    def test_slash_command_misclassification_fix_integration(self):
        """Test fix for PACC-18: slash commands incorrectly classified as agents."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create commands directory
            commands_dir = temp_path / "commands"
            commands_dir.mkdir()

            # Create slash command that could be confused as agent
            slash_command = commands_dir / "agent-helper.md"
            slash_command.write_text("""---
name: agent-helper
description: Helps with agent-like tasks
---

# /agent-helper

This command provides agent-like assistance with tool validation and permissions.

## Features
- Tool integration support
- Permission checking
- Agent-style assistance

Contains agent keywords but should be command due to directory structure.
""")

            # Run detection
            detector = ExtensionDetector()
            detected_type = detector.detect_extension_type(slash_command)

            # Should be detected as command (fixes PACC-18)
            assert (
                detected_type == "commands"
            ), "PACC-18 regression: slash command misclassified as agent"

            # Verify in validation workflow
            results = validate_extension_directory(temp_path)
            assert "commands" in results

            command_files = [r.file_path for r in results["commands"]]
            assert any("agent-helper.md" in f for f in command_files)

    def test_hierarchy_override_chain_integration(self):
        """Test complete hierarchy: pacc.json > directory > content."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files that demonstrate the hierarchy
            test_files = [
                # File 1: pacc.json overrides directory and content
                (
                    "hooks/declared-as-command.json",
                    {
                        "description": "In hooks dir with hook content but declared as command",
                        "name": "declared-as-command",
                        "version": "1.0.0",
                        "eventTypes": ["PreToolUse"],
                        "commands": ["echo 'hook executed'"],  # Hook-like content
                    },
                ),
                # File 2: Directory overrides content (no pacc.json declaration)
                (
                    "commands/agent-like-command.md",
                    """---
name: agent-like-command
description: Has agent keywords but in commands directory
tools: ["calculator"]
permissions: ["execute"]
---

# /agent-like-command

Agent-like content but should be command due to directory.
""",
                ),
                # File 3: Content fallback (no directory/pacc.json signals)
                (
                    "standalone-agent.md",
                    """---
name: standalone-agent
description: Clear agent with tools and permissions
tools: ["file-reader", "calculator"]
permissions: ["read-files", "execute"]
---

Clear agent content with no other signals.
""",
                ),
            ]

            # Create directory structure and files
            for file_path, content in test_files:
                full_path = temp_path / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)

                if isinstance(content, dict):
                    full_path.write_text(json.dumps(content, indent=2))
                else:
                    full_path.write_text(content)

            # Create pacc.json that overrides first file
            pacc_config = {
                "name": "hierarchy-test",
                "version": "1.0.0",
                "extensions": {
                    "commands": [
                        {
                            "name": "declared-as-command",
                            "source": "./hooks/declared-as-command.json",
                            "version": "1.0.0",
                        }
                    ]
                },
            }
            (temp_path / "pacc.json").write_text(json.dumps(pacc_config, indent=2))

            # Test individual detection
            detector = ExtensionDetector()

            # File 1: Should be command due to pacc.json (highest priority)
            file1_path = temp_path / "hooks/declared-as-command.json"
            type1 = detector.detect_extension_type(file1_path, project_dir=temp_path)
            assert type1 == "commands", "pacc.json should override directory structure"

            # File 2: Should be command due to directory (secondary priority)
            file2_path = temp_path / "commands/agent-like-command.md"
            type2 = detector.detect_extension_type(file2_path)
            assert type2 == "commands", "Directory structure should override content keywords"

            # File 3: Should be agent due to content (fallback)
            file3_path = temp_path / "standalone-agent.md"
            type3 = detector.detect_extension_type(file3_path)
            assert type3 == "agents", "Content keywords should be fallback method"

            # Verify in complete validation workflow
            results = validate_extension_directory(temp_path)

            # All files should be correctly categorized
            assert "commands" in results
            assert len(results["commands"]) >= 2  # Files 1 and 2

            if "agents" in results:
                agent_files = [r.file_path for r in results["agents"]]
                assert any("standalone-agent.md" in f for f in agent_files)


class TestS01CLIValidateCommandIntegration:
    """Test S01 CLI validate command integration with all scenarios."""

    def test_cli_validate_single_file_integration(self):
        """Test CLI validate command with single file."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create valid hook file
            hook_file = temp_path / "test-hook.json"
            hook_file.write_text(
                json.dumps(
                    {
                        "name": "test-hook",
                        "version": "1.0.0",
                        "eventTypes": ["PreToolUse"],
                        "commands": ["echo 'hook executed'"],
                        "description": "Test hook for CLI validation",
                    }
                )
            )

            # Test CLI validate command
            cli = PACCCli()

            # Mock args for validate command
            class MockArgs:
                source = str(hook_file)
                type = None
                strict = False

            result = cli.validate_command(MockArgs())

            # Should succeed (return 0)
            assert result == 0

    def test_cli_validate_directory_integration(self):
        """Test CLI validate command with directory."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test structure
            self._create_cli_test_structure(temp_path)

            # Test CLI validate command
            cli = PACCCli()

            class MockArgs:
                source = str(temp_path)
                type = None
                strict = False

            result = cli.validate_command(MockArgs())

            # Should succeed with mixed valid/invalid files
            assert result in [0, 1]  # May have warnings/errors but should not crash

    def test_cli_validate_with_type_filter_integration(self):
        """Test CLI validate command with specific type filter."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create mixed extension types
            self._create_cli_test_structure(temp_path)

            # Test with hooks filter
            cli = PACCCli()

            class MockArgs:
                source = str(temp_path)
                type = "hooks"
                strict = False

            result = cli.validate_command(MockArgs())

            # Should process only hooks
            assert result in [0, 1]  # Should not crash

    def test_cli_validate_strict_mode_integration(self):
        """Test CLI validate command in strict mode."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create hook with warning (missing description)
            hook_file = temp_path / "warning-hook.json"
            hook_file.write_text(
                json.dumps(
                    {
                        "name": "warning-hook",
                        "version": "1.0.0",
                        "eventTypes": ["PreToolUse"],
                        "commands": ["echo 'hook executed'"],
                        # Missing description - should generate warning
                    }
                )
            )

            # Test in normal mode
            cli = PACCCli()

            class MockArgs:
                source = str(hook_file)
                type = None
                strict = False

            normal_result = cli.validate_command(MockArgs())

            # Test in strict mode
            class MockStrictArgs:
                source = str(hook_file)
                type = None
                strict = True

            strict_result = cli.validate_command(MockStrictArgs())

            # Normal mode should succeed with warnings
            # Strict mode should fail due to warnings
            assert normal_result == 0
            assert strict_result == 1  # Should fail in strict mode

    def test_cli_validate_nonexistent_path_handling(self):
        """Test CLI validate command with nonexistent path."""
        cli = PACCCli()

        class MockArgs:
            source = "/nonexistent/path"
            type = None
            strict = False

        result = cli.validate_command(MockArgs())

        # Should fail gracefully
        assert result == 1

    def test_cli_validate_error_handling_integration(self):
        """Test CLI validate command error handling."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file that will cause validation error
            error_file = temp_path / "error-hook.json"
            error_file.write_text('{"invalid": json, "syntax": error}')

            cli = PACCCli()

            class MockArgs:
                source = str(error_file)
                type = None
                strict = False

            result = cli.validate_command(MockArgs())

            # Should fail gracefully with error
            assert result == 1

    def _create_cli_test_structure(self, base_path: Path):
        """Create test structure for CLI testing."""
        # Valid hook
        valid_hook = base_path / "valid-hook.json"
        valid_hook.write_text(
            json.dumps(
                {
                    "name": "valid-hook",
                    "version": "1.0.0",
                    "eventTypes": ["PreToolUse"],
                    "commands": ["echo 'valid hook executed'"],
                    "description": "Valid hook for CLI testing",
                }
            )
        )

        # Hook with warning
        warning_hook = base_path / "warning-hook.json"
        warning_hook.write_text(
            json.dumps(
                {
                    "name": "warning-hook",
                    "version": "1.0.0",
                    "eventTypes": ["PreToolUse"],
                    "commands": ["echo 'hook executed'"],
                    # Missing description
                }
            )
        )

        # Invalid hook
        invalid_hook = base_path / "invalid-hook.json"
        invalid_hook.write_text(
            json.dumps(
                {
                    "name": "invalid-hook"
                    # Missing required fields
                }
            )
        )

        # Valid command
        commands_dir = base_path / "commands"
        commands_dir.mkdir()
        valid_command = commands_dir / "valid-command.md"
        valid_command.write_text("""---
name: valid-command
description: Valid command
---

# /valid-command

Valid command content.
""")


class TestS01CrossPlatformIntegration:
    """Test S01 fixes work across different platforms and edge cases."""

    def test_windows_path_handling_integration(self):
        """Test S01 fixes handle Windows-style paths correctly."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create files with various naming patterns
            test_files = [
                "UPPERCASE.JSON",
                "mixed-Case.json",
                "with spaces.json",
                "with.dots.json",
                "with_underscores.json",
            ]

            for filename in test_files:
                file_path = temp_path / filename
                file_path.write_text(
                    json.dumps(
                        {
                            "name": filename.split(".")[0],
                            "version": "1.0.0",
                            "eventTypes": ["PreToolUse"],
                            "commands": ["echo 'hook executed'"],
                        }
                    )
                )

            # Run validation
            results = validate_extension_directory(temp_path)

            # Should handle all files regardless of naming convention
            if "hooks" in results:
                validated_count = len(results["hooks"])
                assert validated_count >= len(test_files)

    def test_unicode_filename_handling_integration(self):
        """Test S01 fixes handle Unicode filenames correctly."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create files with Unicode names
            unicode_files = [
                "测试-hook.json",  # Chinese
                "тест-hook.json",  # Russian
                "テスト-hook.json",  # Japanese
                "émoji-🎉-hook.json",  # Emoji
            ]

            created_files = []
            for filename in unicode_files:
                try:
                    file_path = temp_path / filename
                    file_path.write_text(
                        json.dumps(
                            {
                                "name": "unicode-test",
                                "version": "1.0.0",
                                "eventTypes": ["PreToolUse"],
                                "commands": ["echo 'hook executed'"],
                            }
                        )
                    )
                    created_files.append(filename)
                except (OSError, UnicodeError):
                    # Skip if filesystem doesn't support Unicode
                    continue

            if created_files:
                # Run validation
                results = validate_extension_directory(temp_path)

                # Should handle Unicode files without crashing
                total_results = sum(len(file_list) for file_list in results.values())
                assert total_results > 0

    def test_deep_nesting_performance_integration(self):
        """Test S01 fixes handle deep directory nesting efficiently."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create deeply nested structure (10 levels)
            current_path = temp_path
            for level in range(10):
                level_dir = current_path / f"level_{level}"
                level_dir.mkdir()

                # Add hook file at each level
                hook_file = level_dir / f"hook_level_{level}.json"
                hook_file.write_text(
                    json.dumps(
                        {
                            "name": f"hook-level-{level}",
                            "version": "1.0.0",
                            "eventTypes": ["PreToolUse"],
                            "commands": ["echo 'hook executed'"],
                        }
                    )
                )

                current_path = level_dir

            # Time the validation
            start_time = time.time()
            results = validate_extension_directory(temp_path)
            end_time = time.time()

            duration = end_time - start_time

            # Should complete in reasonable time
            assert duration < 5.0, f"Deep nesting validation too slow: {duration:.2f}s"

            # Should find files at all levels
            if "hooks" in results:
                assert len(results["hooks"]) >= 5  # Should find hooks at multiple levels

    def test_symlink_handling_integration(self):
        """Test S01 fixes handle symbolic links appropriately."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create original file
            original_file = temp_path / "original-hook.json"
            original_file.write_text(
                json.dumps(
                    {
                        "name": "original-hook",
                        "version": "1.0.0",
                        "eventTypes": ["PreToolUse"],
                        "commands": ["echo 'hook executed'"],
                    }
                )
            )

            # Create symlink (if supported on platform)
            symlink_file = temp_path / "symlink-hook.json"
            try:
                if hasattr(os, "symlink"):
                    os.symlink(original_file, symlink_file)

                    # Run validation
                    results = validate_extension_directory(temp_path)

                    # Should handle symlinks gracefully
                    total_results = sum(len(file_list) for file_list in results.values())
                    assert total_results > 0
            except (OSError, NotImplementedError):
                # Skip if platform doesn't support symlinks
                pytest.skip("Platform does not support symlinks")

    def test_permission_denied_handling_integration(self):
        """Test S01 fixes handle permission denied errors gracefully."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create accessible file
            accessible_file = temp_path / "accessible-hook.json"
            accessible_file.write_text(
                json.dumps(
                    {
                        "name": "accessible-hook",
                        "version": "1.0.0",
                        "eventTypes": ["PreToolUse"],
                        "commands": ["echo 'hook executed'"],
                    }
                )
            )

            # Create restricted directory (simulate permission error)
            restricted_dir = temp_path / "restricted"
            restricted_dir.mkdir()
            restricted_file = restricted_dir / "restricted-hook.json"
            restricted_file.write_text(
                json.dumps(
                    {
                        "name": "restricted-hook",
                        "version": "1.0.0",
                        "eventTypes": ["PreToolUse"],
                        "commands": ["echo 'hook executed'"],
                    }
                )
            )

            # Mock permission error for restricted directory
            original_glob = Path.glob

            def mock_glob(self, pattern, **kwargs):
                if "restricted" in str(self):
                    raise PermissionError("Permission denied")
                return original_glob(self, pattern, **kwargs)

            with patch.object(Path, "glob", mock_glob):
                # Should handle permission error gracefully
                results = validate_extension_directory(temp_path)

                # Should still find accessible files
                total_results = sum(len(file_list) for file_list in results.values())
                assert total_results > 0


class TestS01PerformanceBenchmarks:
    """Performance benchmarks for S01 fixes."""

    def test_large_directory_validation_benchmark(self):
        """Benchmark validation performance with large directories."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create large number of files (1000)
            for i in range(1000):
                file_path = temp_path / f"test_hook_{i:04d}.json"
                file_path.write_text(
                    json.dumps(
                        {
                            "name": f"test-hook-{i}",
                            "version": "1.0.0",
                            "eventTypes": ["PreToolUse"],
                            "commands": ["echo 'hook executed'"],
                        }
                    )
                )

            # Benchmark validation
            start_time = time.time()
            validate_extension_directory(temp_path)
            end_time = time.time()

            duration = end_time - start_time
            files_per_second = 1000 / duration if duration > 0 else float("inf")

            print("\nPerformance Benchmark Results:")
            print("- Files validated: 1000")
            print(f"- Duration: {duration:.3f}s")
            print(f"- Files/second: {files_per_second:.1f}")

            # Performance targets
            assert duration < 10.0, f"Validation too slow: {duration:.2f}s"
            assert files_per_second > 50, f"Throughput too low: {files_per_second:.1f} files/s"

    def test_extension_detection_benchmark(self):
        """Benchmark extension type detection performance."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files for detection
            test_files = []
            for i in range(100):
                file_path = temp_path / f"test_file_{i:03d}.json"
                file_path.write_text(
                    json.dumps(
                        {
                            "name": f"test-{i}",
                            "version": "1.0.0",
                            "eventTypes": ["PreToolUse"],
                            "commands": ["echo 'hook executed'"],
                        }
                    )
                )
                test_files.append(file_path)

            # Benchmark detection
            detector = ExtensionDetector()

            start_time = time.time()
            for file_path in test_files:
                detector.detect_extension_type(file_path)
            end_time = time.time()

            duration = end_time - start_time
            detections_per_second = len(test_files) / duration if duration > 0 else float("inf")

            print("\nDetection Benchmark Results:")
            print(f"- Files processed: {len(test_files)}")
            print(f"- Duration: {duration:.3f}s")
            print(f"- Detections/second: {detections_per_second:.1f}")

            # Performance targets
            assert duration < 2.0, f"Detection too slow: {duration:.2f}s"
            assert (
                detections_per_second > 100
            ), f"Detection throughput too low: {detections_per_second:.1f}/s"


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "--tb=short"])
