"""Tests for the PACC info command functionality."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pacc.cli import PACCCli
from pacc.core.config_manager import ClaudeConfigManager
from pacc.validators import ValidationResult


class TestInfoCommand:
    """Test cases for the info command."""

    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PACCCli()

    def _create_mock_args(self, source, **overrides):
        """Create mock args with default values."""
        args = Mock()
        args.source = source
        args.type = None
        args.json = False
        args.verbose = False
        args.show_related = False
        args.show_usage = False
        args.show_troubleshooting = False

        # Apply any overrides
        for key, value in overrides.items():
            setattr(args, key, value)

        return args

    @pytest.fixture
    def sample_hook_file(self, tmp_path):
        """Create a sample hook file for testing."""
        hook_data = {
            "name": "test-hook",
            "description": "A test hook for demonstration",
            "version": "1.0.0",
            "eventTypes": ["PreToolUse", "PostToolUse"],
            "commands": ["echo 'Hook executed'"],
            "matchers": [{"type": "exact", "pattern": "test-command"}],
        }
        hook_file = tmp_path / "test-hook.json"
        hook_file.write_text(json.dumps(hook_data, indent=2))
        return hook_file

    @pytest.fixture
    def sample_agent_file(self, tmp_path):
        """Create a sample agent file for testing."""
        agent_content = """---
name: test-agent
description: A test agent for demonstration
version: 1.0.0
model: claude-3-sonnet
tools: [search, calculator]
system_prompt: You are a helpful test agent.
---

# Test Agent

This is a test agent implementation.
"""
        agent_file = tmp_path / "test-agent.md"
        agent_file.write_text(agent_content)
        return agent_file

    @pytest.fixture
    def mock_installed_config(self):
        """Mock configuration with installed extensions."""
        return {
            "hooks": [
                {
                    "name": "installed-hook",
                    "path": "hooks/installed-hook.json",
                    "description": "An installed hook",
                    "version": "1.2.0",
                    "installed_at": "2024-08-13T10:30:00Z",
                    "source": "local-file",
                    "validation_status": "valid",
                }
            ],
            "agents": [
                {
                    "name": "installed-agent",
                    "path": "agents/installed-agent.md",
                    "description": "An installed agent",
                    "version": "2.0.0",
                    "model": "claude-3-opus",
                    "installed_at": "2024-08-13T11:15:00Z",
                    "source": "github",
                    "validation_status": "warning",
                }
            ],
            "mcps": [],
            "commands": [],
        }

    def test_info_command_file_path(self, cli, sample_hook_file, capsys):
        """Test info command with file path."""
        # Mock the validation result
        mock_result = ValidationResult(
            is_valid=True,
            file_path=str(sample_hook_file),
            extension_type="hooks",
            metadata={
                "name": "test-hook",
                "description": "A test hook for demonstration",
                "version": "1.0.0",
                "event_types": ["PreToolUse", "PostToolUse"],
                "has_matchers": True,
                "command_count": 1,
            },
        )

        with patch("pacc.cli.validate_extension_file", return_value=mock_result):
            # Create mock args
            args = self._create_mock_args(str(sample_hook_file), verbose=True)

            # Run info command
            result = cli.info_command(args)

        assert result == 0
        captured = capsys.readouterr()

        # Check that key information is displayed
        assert "test-hook" in captured.out
        assert "A test hook for demonstration" in captured.out
        assert "1.0.0" in captured.out
        assert "PreToolUse" in captured.out
        assert "PostToolUse" in captured.out
        assert "hooks" in captured.out

    def test_info_command_installed_extension(self, cli, mock_installed_config, capsys):
        """Test info command with installed extension name."""
        with patch.object(
            ClaudeConfigManager, "load_config", return_value=mock_installed_config
        ), patch.object(
            ClaudeConfigManager, "get_config_path", return_value=Path("/fake/.claude/settings.json")
        ):
            args = self._create_mock_args("installed-hook", verbose=True)

            result = cli.info_command(args)

        assert result == 0
        captured = capsys.readouterr()

        # Check that installed extension information is displayed
        assert "installed-hook" in captured.out
        assert "An installed hook" in captured.out
        assert "1.2.0" in captured.out
        assert "2024-08-13" in captured.out
        assert "local-file" in captured.out
        assert "valid" in captured.out

    def test_info_command_json_output(self, cli, sample_hook_file):
        """Test info command with JSON output format."""
        mock_result = ValidationResult(
            is_valid=True,
            file_path=str(sample_hook_file),
            extension_type="hooks",
            metadata={
                "name": "test-hook",
                "description": "A test hook for demonstration",
                "version": "1.0.0",
                "event_types": ["PreToolUse", "PostToolUse"],
                "has_matchers": True,
                "command_count": 1,
            },
        )

        with patch("pacc.validators.validate_extension_file", return_value=mock_result), patch(
            "sys.stdout"
        ) as mock_stdout:
            args = self._create_mock_args(str(sample_hook_file), json=True)

            result = cli.info_command(args)

        assert result == 0
        # Verify JSON output was attempted
        mock_stdout.write.assert_called()

    def test_info_command_validation_errors(self, cli, sample_hook_file, capsys):
        """Test info command when validation has errors."""
        mock_result = ValidationResult(
            is_valid=False,
            file_path=str(sample_hook_file),
            extension_type="hooks",
            metadata={},  # Empty metadata for invalid file
        )
        mock_result.add_error("INVALID_JSON", "Invalid JSON syntax at line 5")
        mock_result.add_warning("DEPRECATED_FIELD", "Field 'oldField' is deprecated")

        # Ensure is_valid is False after adding errors
        assert mock_result.is_valid == False
        assert len(mock_result.errors) > 0

        with patch("pacc.cli.validate_extension_file", return_value=mock_result):
            args = self._create_mock_args(str(sample_hook_file), verbose=True)

            result = cli.info_command(args)

        assert result == 0  # Info should still work even with validation errors
        captured = capsys.readouterr()

        # Check that validation errors are displayed
        assert "✗ No" in captured.out  # Should show "Valid: ✗ No"
        assert "INVALID_JSON" in captured.out
        assert "Invalid JSON syntax" in captured.out
        assert "DEPRECATED_FIELD" in captured.out

    def test_info_command_nonexistent_file(self, cli, capsys):
        """Test info command with non-existent file."""
        args = self._create_mock_args("/nonexistent/file.json")

        result = cli.info_command(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err

    def test_info_command_nonexistent_installed_extension(self, cli, mock_installed_config, capsys):
        """Test info command with non-existent installed extension."""
        with patch.object(
            ClaudeConfigManager, "load_config", return_value=mock_installed_config
        ), patch.object(
            ClaudeConfigManager, "get_config_path", return_value=Path("/fake/.claude/settings.json")
        ):
            args = self._create_mock_args("nonexistent-extension")

            result = cli.info_command(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_info_command_with_type_filter(self, cli, sample_agent_file):
        """Test info command with type filter."""
        mock_result = ValidationResult(
            is_valid=True,
            file_path=str(sample_agent_file),
            extension_type="agents",
            metadata={
                "name": "test-agent",
                "description": "A test agent for demonstration",
                "version": "1.0.0",
                "model": "claude-3-sonnet",
                "tools": ["search", "calculator"],
            },
        )

        with patch("pacc.cli.validate_extension_file", return_value=mock_result):
            args = self._create_mock_args(str(sample_agent_file), type="agents")

            result = cli.info_command(args)

        assert result == 0

    def test_info_command_verbose_mode(self, cli, sample_hook_file, capsys):
        """Test info command in verbose mode shows additional details."""
        mock_result = ValidationResult(
            is_valid=True,
            file_path=str(sample_hook_file),
            extension_type="hooks",
            metadata={
                "name": "test-hook",
                "description": "A test hook for demonstration",
                "version": "1.0.0",
                "event_types": ["PreToolUse", "PostToolUse"],
                "has_matchers": True,
                "command_count": 1,
                "file_size": 1024,
                "last_modified": "2024-08-13T10:00:00Z",
            },
        )

        with patch("pacc.cli.validate_extension_file", return_value=mock_result):
            args = self._create_mock_args(str(sample_hook_file), verbose=True)

            result = cli.info_command(args)

        assert result == 0
        captured = capsys.readouterr()

        # In verbose mode, should show additional technical details
        assert "Size:" in captured.out or "file_size" in captured.out.lower()

    def test_info_command_suggests_related_extensions(self, cli, mock_installed_config, capsys):
        """Test that info command suggests related extensions."""
        # Add related extensions to the mock config
        config_with_related = {
            **mock_installed_config,
            "hooks": [
                {
                    "name": "related-hook-1",
                    "description": "Related hook for testing",
                    "path": "hooks/related-hook-1.json",
                },
                {
                    "name": "related-hook-2",
                    "description": "Another related hook for testing",
                    "path": "hooks/related-hook-2.json",
                },
            ],
        }

        with patch.object(
            ClaudeConfigManager, "load_config", return_value=config_with_related
        ), patch.object(
            ClaudeConfigManager, "get_config_path", return_value=Path("/fake/.claude/settings.json")
        ):
            args = self._create_mock_args("related-hook-1", show_related=True)

            result = cli.info_command(args)

        assert result == 0
        captured = capsys.readouterr()

        # Should suggest other similar extensions
        assert "Related Extensions" in captured.out or "related" in captured.out.lower()
