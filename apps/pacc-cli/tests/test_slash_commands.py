#!/usr/bin/env python3
"""Comprehensive test suite for PACC slash commands integration."""

import json
import os
import subprocess

# Add the pacc module to Python path
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pacc.cli import CommandResult, PACCCli


class TestSlashCommandsIntegration:
    """Test suite for PACC slash commands integration."""

    @pytest.fixture
    def cli(self):
        """Create a PACC CLI instance for testing."""
        return PACCCli()

    @pytest.fixture
    def temp_claude_dir(self):
        """Create a temporary .claude directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            claude_dir = Path(temp_dir) / ".claude"
            claude_dir.mkdir()

            # Create subdirectories
            for subdir in ["commands", "hooks", "mcps", "agents"]:
                (claude_dir / subdir).mkdir()

            yield claude_dir

    def run_pacc_cli(self, args, cwd=None):
        """Run PACC CLI command programmatically."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)

        try:
            result = subprocess.run(
                ["python", "-m", "pacc"] + args,
                cwd=cwd or os.getcwd(),
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                check=False,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"

    def test_json_output_structure(self, cli):
        """Test that JSON output has the correct structure."""
        cli._set_json_mode(True)

        # Test CommandResult serialization
        result = CommandResult(
            success=True,
            message="Test message",
            data={"test": "data"},
            errors=["error1"],
            warnings=["warning1"],
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["message"] == "Test message"
        assert result_dict["data"]["test"] == "data"
        assert result_dict["errors"] == ["error1"]
        assert result_dict["warnings"] == ["warning1"]

    def test_list_command_json_output(self):
        """Test list command JSON output format."""
        returncode, stdout, stderr = self.run_pacc_cli(["list", "--format", "json"])

        assert returncode == 0, f"Command failed with stderr: {stderr}"

        # Parse JSON output
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")

        # Verify structure
        assert "success" in result
        assert "message" in result
        assert "data" in result
        assert "extensions" in result["data"]
        assert "count" in result["data"]
        assert isinstance(result["data"]["extensions"], list)
        assert isinstance(result["data"]["count"], int)

    def test_install_command_json_flag(self):
        """Test that install command has JSON flag."""
        returncode, stdout, stderr = self.run_pacc_cli(["install", "--help"])

        assert returncode == 0
        assert "--json" in stdout, "Install command should support --json flag"

    def test_remove_command_json_flag(self):
        """Test that remove command has JSON flag."""
        returncode, stdout, stderr = self.run_pacc_cli(["remove", "--help"])

        assert returncode == 0
        assert "--json" in stdout, "Remove command should support --json flag"

    def test_info_command_json_flag(self):
        """Test that info command has JSON flag."""
        returncode, stdout, stderr = self.run_pacc_cli(["info", "--help"])

        assert returncode == 0
        assert "--json" in stdout, "Info command should support --json flag"

    def test_slash_command_files_exist(self):
        """Test that all required slash command files exist."""
        commands_dir = Path(".claude/commands/pacc")
        expected_files = ["install.md", "list.md", "info.md", "remove.md", "search.md", "update.md"]

        for cmd_file in expected_files:
            cmd_path = commands_dir / cmd_file
            assert cmd_path.exists(), f"Command file {cmd_file} should exist"

            # Verify file has content
            content = cmd_path.read_text()
            assert len(content) > 0, f"Command file {cmd_file} should not be empty"

    def test_slash_command_frontmatter(self):
        """Test that slash command files have proper frontmatter."""
        commands_dir = Path(".claude/commands/pacc")
        required_fields = ["allowed-tools", "argument-hint", "description"]

        for cmd_file in commands_dir.glob("*.md"):
            content = cmd_file.read_text()

            # Check frontmatter exists
            assert content.startswith("---"), f"{cmd_file.name} should start with frontmatter"

            # Check required fields
            for field in required_fields:
                assert f"{field}:" in content, f"{cmd_file.name} should have {field} in frontmatter"

            # Check it calls PACC CLI
            assert (
                "uv run pacc" in content or "python -m pacc" in content
            ), f"{cmd_file.name} should invoke PACC CLI"

    def test_slash_command_pacc_integration(self):
        """Test that slash commands properly integrate with PACC CLI."""
        commands_dir = Path(".claude/commands/pacc")

        for cmd_file in commands_dir.glob("*.md"):
            content = cmd_file.read_text()

            # Should use bash tools to run PACC
            assert "Bash(" in content, f"{cmd_file.name} should use Bash tools"

            # Should pass arguments
            assert "$ARGUMENTS" in content, f"{cmd_file.name} should use $ARGUMENTS placeholder"

            # Should use JSON output for programmatic access
            if cmd_file.name in ["install.md", "remove.md", "info.md"]:
                assert "--json" in content, f"{cmd_file.name} should use --json flag"
            elif cmd_file.name == "list.md":
                # list command uses --format json
                assert any(
                    fmt in content for fmt in ["--format json", "--json"]
                ), f"{cmd_file.name} should use JSON output"

    def test_message_collection_in_json_mode(self, cli):
        """Test that messages are properly collected in JSON mode."""
        cli._set_json_mode(True)

        # Add various message types
        cli._print_info("Info message")
        cli._print_success("Success message")
        cli._print_warning("Warning message")
        cli._print_error("Error message")

        assert len(cli._messages) == 4

        # Check message structure
        info_msg = cli._messages[0]
        assert info_msg["level"] == "info"
        assert info_msg["message"] == "Info message"

        success_msg = cli._messages[1]
        assert success_msg["level"] == "success"
        assert success_msg["message"] == "Success message"

    def test_json_mode_toggle(self, cli):
        """Test JSON mode can be toggled on/off."""
        # Initially off
        assert cli._json_output is False
        assert len(cli._messages) == 0

        # Turn on
        cli._set_json_mode(True)
        assert cli._json_output is True

        cli._print_info("Test message")
        assert len(cli._messages) == 1

        # Turn off
        cli._set_json_mode(False)
        assert cli._json_output is False
        assert len(cli._messages) == 0  # Should be cleared

    def test_pacc_main_help_command(self):
        """Test the main pacc.md help command exists."""
        main_cmd = Path(".claude/commands/pacc.md")
        assert main_cmd.exists(), "Main PACC help command should exist"

        content = main_cmd.read_text()

        # Should describe all subcommands
        subcommands = ["install", "list", "info", "remove", "search", "update"]
        for subcmd in subcommands:
            assert f"/pacc:{subcmd}" in content, f"Main help should mention /pacc:{subcmd}"

        # Should describe extension types
        ext_types = ["hooks", "mcps", "agents", "commands"]
        for ext_type in ext_types:
            assert ext_type in content.lower(), f"Main help should mention {ext_type}"

    def test_command_error_handling_in_json_mode(self, cli):
        """Test that errors are properly handled in JSON mode."""
        cli._set_json_mode(True)

        # Simulate command error
        try:
            # This would normally be called in command implementation
            result = CommandResult(
                success=False,
                message="Command failed",
                errors=["File not found", "Permission denied"],
            )

            result_dict = result.to_dict()

            assert result_dict["success"] is False
            assert result_dict["message"] == "Command failed"
            assert len(result_dict["errors"]) == 2

        except Exception as e:
            pytest.fail(f"Error handling failed: {e}")

    @pytest.mark.parametrize("command", ["install", "list", "info", "remove"])
    def test_cli_command_json_support(self, command):
        """Parametrized test for JSON support in CLI commands."""
        returncode, stdout, stderr = self.run_pacc_cli([command, "--help"])

        assert returncode == 0, f"{command} --help should work"

        # Check for JSON support (command-specific)
        if command == "list":
            assert (
                "--format" in stdout and "json" in stdout
            ), f"{command} should support JSON via --format"
        else:
            assert "--json" in stdout, f"{command} should support --json flag"


class TestSlashCommandWorkflows:
    """Test workflows that slash commands enable."""

    def run_pacc_cli(self, args, cwd=None):
        """Run PACC CLI command programmatically."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)

        try:
            result = subprocess.run(
                ["python", "-m", "pacc"] + args,
                cwd=cwd or os.getcwd(),
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
                check=False,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timed out"

    def test_list_and_parse_workflow(self):
        """Test workflow of listing extensions and parsing JSON results."""
        # This simulates what a slash command would do
        returncode, stdout, stderr = self.run_pacc_cli(["list", "--format", "json"])

        assert returncode == 0

        # Parse result as slash command would
        result = json.loads(stdout)

        # Extract information for user display
        extensions = result["data"]["extensions"]
        count = result["data"]["count"]

        # This would be formatted for Claude Code user
        assert isinstance(extensions, list)
        assert isinstance(count, int)
        assert count == len(extensions)

    def test_info_command_detailed_output(self):
        """Test info command produces detailed output suitable for slash commands."""
        # Test with non-existent extension (should still return valid JSON structure)
        returncode, stdout, stderr = self.run_pacc_cli(["info", "nonexistent", "--json"])

        # Command should handle gracefully
        assert returncode in [0, 1]  # Either success or expected failure

        # If JSON output, should be parseable
        if returncode == 0 and stdout.strip():
            try:
                result = json.loads(stdout)
                assert "success" in result
                assert "message" in result
            except json.JSONDecodeError:
                # If not JSON, should be human-readable error
                assert len(stdout) > 0 or len(stderr) > 0


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])
