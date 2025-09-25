"""Unit tests for extension type detection hierarchy (PACC-24).

This test suite validates that the detection logic follows the proper hierarchy:
1. pacc.json declarations (highest priority)
2. Directory structure (secondary signal)
3. Content keywords (fallback only)

This addresses the PACC-18 issue where slash commands were incorrectly classified as agents.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from pacc.validators.utils import ExtensionDetector


class TestExtensionDetectionHierarchy:
    """Test extension type detection hierarchy implementation."""

    def test_pacc_json_declarations_highest_priority(self):
        """Test that pacc.json declarations take highest priority over content keywords."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a file that looks like an agent by content
            agent_looking_file = temp_path / "helper.md"
            agent_looking_file.write_text("""---
name: helper-agent
description: A helper agent for tasks
---

This agent helps with tool usage and permissions.
""")

            # Create pacc.json that declares this file as a command
            pacc_json = temp_path / "pacc.json"
            pacc_config = {
                "name": "test-project",
                "version": "1.0.0",
                "extensions": {
                    "commands": [{"name": "helper", "source": "./helper.md", "version": "1.0.0"}]
                },
            }
            pacc_json.write_text(json.dumps(pacc_config, indent=2))

            # Mock ProjectConfigManager to return our config
            mock_config_manager = MagicMock()
            mock_config_manager.load_project_config.return_value = pacc_config

            with patch(
                "pacc.core.project_config.ProjectConfigManager", return_value=mock_config_manager
            ):
                detector = ExtensionDetector()
                detected_type = detector.detect_extension_type(
                    agent_looking_file, project_dir=temp_path
                )

            # Should detect as command despite agent-like content
            assert (
                detected_type == "commands"
            ), f"Expected 'commands' but got '{detected_type}'. pacc.json declarations should take highest priority."

    def test_directory_structure_secondary_priority(self):
        """Test that directory structure is used when no pacc.json declaration exists."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create commands directory structure
            commands_dir = temp_path / "commands"
            commands_dir.mkdir()

            # Create a file that could be confused as agent by content
            slash_command_file = commands_dir / "helper.md"
            slash_command_file.write_text("""# /helper

Helps users with agent-like functionality.

## Description

This command provides agent assistance but is actually a slash command.
Contains keywords: tool, permission, agent.
""")

            # No pacc.json file exists
            detector = ExtensionDetector()
            detected_type = detector.detect_extension_type(slash_command_file)

            # Should detect as command due to directory structure
            assert (
                detected_type == "commands"
            ), f"Expected 'commands' but got '{detected_type}'. Directory structure should be secondary priority."

    def test_content_keywords_fallback_only(self):
        """Test that content keywords are only used as final fallback."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file outside any special directory with clear agent content
            clear_agent_file = temp_path / "agent.md"
            clear_agent_file.write_text("""---
name: clear-agent
description: A clear agent example
tools: ["file-reader", "calculator"]
permissions: ["read-files", "execute"]
---

This is clearly an agent with tools and permissions.
""")

            # No pacc.json, no special directory
            detector = ExtensionDetector()
            detected_type = detector.detect_extension_type(clear_agent_file)

            # Should detect as agent based on content keywords (fallback)
            assert (
                detected_type == "agents"
            ), f"Expected 'agents' but got '{detected_type}'. Content keywords should be fallback method."

    def test_slash_command_misclassification_fix(self):
        """Test fix for PACC-18: slash commands incorrectly classified as agents."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create commands directory
            commands_dir = temp_path / "commands"
            commands_dir.mkdir()

            # Create slash command that might be confused as agent
            slash_command = commands_dir / "pacc-install.md"
            slash_command.write_text("""---
name: pacc-install
description: Install extensions using PACC CLI tool
---

# /pacc:install

Install Claude Code extensions with tool validation and permission checking.

## Usage
/pacc:install <source>

## Features
- Tool integration
- Permission validation
- Agent-like assistance

This command helps users with extension installation.
""")

            detector = ExtensionDetector()
            detected_type = detector.detect_extension_type(slash_command)

            # Should be detected as command, not agent (fixes PACC-18)
            assert (
                detected_type == "commands"
            ), f"PACC-18 regression: Expected 'commands' but got '{detected_type}'. Slash commands should not be misclassified as agents."

    def test_pacc_json_overrides_directory_structure(self):
        """Test that pacc.json declarations override directory structure signals."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create agents directory
            agents_dir = temp_path / "agents"
            agents_dir.mkdir()

            # Create file in agents directory
            file_in_agents = agents_dir / "actual-command.md"
            file_in_agents.write_text("""# /actual-command

This is actually a command but placed in agents directory.
""")

            # Create pacc.json that correctly declares this as a command
            pacc_json = temp_path / "pacc.json"
            pacc_config = {
                "name": "test-project",
                "version": "1.0.0",
                "extensions": {
                    "commands": [
                        {
                            "name": "actual-command",
                            "source": "./agents/actual-command.md",
                            "version": "1.0.0",
                        }
                    ]
                },
            }
            pacc_json.write_text(json.dumps(pacc_config, indent=2))

            # Mock ProjectConfigManager
            mock_config_manager = MagicMock()
            mock_config_manager.load_project_config.return_value = pacc_config

            with patch(
                "pacc.core.project_config.ProjectConfigManager", return_value=mock_config_manager
            ):
                detector = ExtensionDetector()
                detected_type = detector.detect_extension_type(
                    file_in_agents, project_dir=temp_path
                )

            # Should detect as command despite being in agents directory
            assert (
                detected_type == "commands"
            ), f"Expected 'commands' but got '{detected_type}'. pacc.json should override directory structure."

    def test_directory_structure_overrides_content_keywords(self):
        """Test that directory structure overrides content-based detection."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create hooks directory
            hooks_dir = temp_path / "hooks"
            hooks_dir.mkdir()

            # Create file with agent-like content but in hooks directory
            hook_file = hooks_dir / "agent-like.json"
            hook_file.write_text("""{
  "description": "This has agent keywords: tool, permission, agent assistance",
  "hooks": [
    {
      "event": "PreToolUse",
      "action": "validate_agent_permissions"
    }
  ]
}""")

            detector = ExtensionDetector()
            detected_type = detector.detect_extension_type(hook_file)

            # Should detect as hooks due to directory structure, not agent due to content
            assert (
                detected_type == "hooks"
            ), f"Expected 'hooks' but got '{detected_type}'. Directory structure should override content keywords."

    def test_ambiguous_case_with_fallback_logic(self):
        """Test fallback logic handles ambiguous cases gracefully."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file with mixed signals
            ambiguous_file = temp_path / "mixed.md"
            ambiguous_file.write_text("""---
description: Contains both agent and command keywords
---

This file has agent, tool, permission keywords.
But also has command, usage, slash patterns.

Could be either type - ambiguous case.
""")

            detector = ExtensionDetector()
            detected_type = detector.detect_extension_type(ambiguous_file)

            # Should return one of the valid types or None, but not crash
            assert detected_type in [
                None,
                "agents",
                "commands",
            ], f"Ambiguous detection returned unexpected type: '{detected_type}'"

    def test_no_detection_signals_returns_none(self):
        """Test that files with no detection signals return None."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create file with no clear signals
            unknown_file = temp_path / "readme.txt"
            unknown_file.write_text(
                "This is just a regular text file with no extension-specific content."
            )

            detector = ExtensionDetector()
            detected_type = detector.detect_extension_type(unknown_file)

            assert (
                detected_type is None
            ), f"Expected None for unknown file type, but got '{detected_type}'"

    def test_multiple_extensions_in_pacc_json(self):
        """Test handling multiple extensions declared in pacc.json."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create multiple files
            agent_file = temp_path / "agent.md"
            agent_file.write_text("Agent content")

            command_file = temp_path / "command.md"
            command_file.write_text("Command content")

            # Create pacc.json with multiple extensions
            pacc_json = temp_path / "pacc.json"
            pacc_config = {
                "name": "multi-extension-project",
                "version": "1.0.0",
                "extensions": {
                    "agents": [{"name": "agent", "source": "./agent.md", "version": "1.0.0"}],
                    "commands": [{"name": "command", "source": "./command.md", "version": "1.0.0"}],
                },
            }
            pacc_json.write_text(json.dumps(pacc_config, indent=2))

            # Mock ProjectConfigManager
            mock_config_manager = MagicMock()
            mock_config_manager.load_project_config.return_value = pacc_config

            with patch(
                "pacc.core.project_config.ProjectConfigManager", return_value=mock_config_manager
            ):
                detector = ExtensionDetector()

                agent_type = detector.detect_extension_type(agent_file, project_dir=temp_path)
                command_type = detector.detect_extension_type(command_file, project_dir=temp_path)

            assert (
                agent_type == "agents"
            ), f"Agent file should be detected as 'agents', got '{agent_type}'"
            assert (
                command_type == "commands"
            ), f"Command file should be detected as 'commands', got '{command_type}'"

    def test_project_config_integration(self):
        """Test integration with ProjectConfigManager for pacc.json awareness."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test file
            test_file = temp_path / "test-extension.md"
            test_file.write_text("Test content")

            # Test with real ProjectConfigManager (no pacc.json)
            detector = ExtensionDetector()
            result = detector.detect_extension_type(test_file, project_dir=temp_path)

            # Should handle missing pacc.json gracefully
            assert result is None or result in [
                "agents",
                "commands",
                "hooks",
                "mcp",
            ], f"Unexpected detection result: '{result}'"

    def test_backwards_compatibility(self):
        """Test that existing code without project_dir parameter still works."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create commands directory structure (old detection method)
            commands_dir = temp_path / "commands"
            commands_dir.mkdir()

            command_file = commands_dir / "test.md"
            command_file.write_text("# /test\nSlash command content")

            # Test old signature (without project_dir)
            detector = ExtensionDetector()
            detected_type = detector.detect_extension_type(command_file)

            # Should still work with directory structure detection
            assert (
                detected_type == "commands"
            ), f"Backwards compatibility failed: expected 'commands', got '{detected_type}'"
