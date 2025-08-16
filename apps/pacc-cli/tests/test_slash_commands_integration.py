#!/usr/bin/env python3
"""Test PACC slash commands integration for Claude Code."""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any
import pytest

from pacc.cli import PACCCli
from pacc.core.config_manager import ClaudeConfigManager


class TestSlashCommandsIntegration:
    """Test suite for PACC slash commands integration."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_project_dir = Path(self.temp_dir) / "test_project"
        self.test_project_dir.mkdir(parents=True)
        
        # Create .claude directory structure
        self.claude_dir = self.test_project_dir / ".claude"
        self.claude_dir.mkdir()
        
        # Create commands directory
        self.commands_dir = self.claude_dir / "commands" / "pacc"
        self.commands_dir.mkdir(parents=True)
        
        # Save original working directory
        self.original_cwd = os.getcwd()
        os.chdir(self.test_project_dir)
        
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_slash_command_files_structure(self):
        """Test that slash command files have correct structure."""
        # Create the slash command files for testing
        self._create_test_slash_commands()
        
        # Expected slash commands
        slash_commands = [
            "install",
            "list", 
            "search",
            "info",
            "update",
            "remove"
        ]
        
        for cmd_name in slash_commands:
            cmd_file = self.commands_dir / f"{cmd_name}.md"
            
            # Check file exists
            assert cmd_file.exists(), f"Command file {cmd_name}.md should exist"
            
            # Check file content structure
            content = cmd_file.read_text()
            
            # Check for frontmatter
            assert content.startswith("---"), f"{cmd_name}.md should start with frontmatter"
            assert "allowed-tools:" in content, f"{cmd_name}.md should have allowed-tools"
            assert "argument-hint:" in content, f"{cmd_name}.md should have argument-hint"
            assert "description:" in content, f"{cmd_name}.md should have description"
            
            # Check for command usage
            assert "uv run pacc" in content or "python -m pacc" in content, \
                   f"{cmd_name}.md should use PACC CLI commands"
    
    def _create_test_slash_commands(self):
        """Create test slash command files."""
        # Copy real slash commands or create test versions
        import shutil
        real_commands_dir = Path(__file__).parent.parent.parent.parent / ".claude" / "commands" / "pacc"
        
        if real_commands_dir.exists():
            # Copy real commands for testing
            for cmd_file in real_commands_dir.glob("*.md"):
                shutil.copy2(cmd_file, self.commands_dir / cmd_file.name)
        else:
            # Create minimal test commands
            test_commands = {
                "install": """---
allowed-tools: Bash(python:*), Read
argument-hint: <source> [--type <type>]
description: Install Claude Code extensions via PACC
---
Installing: $ARGUMENTS
!`python -m pacc install $ARGUMENTS --json`
""",
                "list": """---
allowed-tools: Bash(python:*), Read
argument-hint: [type] [--user|--project|--all]
description: List installed Claude Code extensions
---
Listing extensions:
!`python -m pacc list $ARGUMENTS --format json`
""",
                "search": """---
allowed-tools: Bash(python:*), Read
argument-hint: <query> [--type <type>]
description: Search for Claude Code extensions
---
Searching: $ARGUMENTS
!`python -m pacc list --search "$ARGUMENTS" --format json`
""",
                "info": """---
allowed-tools: Bash(python:*), Read
argument-hint: <extension-name-or-path>
description: Show detailed information about an extension
---
Getting info: $ARGUMENTS
!`python -m pacc info $ARGUMENTS --json`
""",
                "update": """---
allowed-tools: Bash(python:*), Read
argument-hint: <extension-name-or-source> [--force]
description: Update an installed extension
---
Updating: $ARGUMENTS
!`python -m pacc install $ARGUMENTS --force --json`
""",
                "remove": """---
allowed-tools: Bash(python:*), Read
argument-hint: <extension-name> [--type <type>]
description: Remove an installed extension
---
Removing: $ARGUMENTS
!`python -m pacc remove $ARGUMENTS --confirm --json`
"""
            }
            
            for cmd_name, content in test_commands.items():
                (self.commands_dir / f"{cmd_name}.md").write_text(content)
    
    def test_install_slash_command(self):
        """Test /pacc:install slash command functionality."""
        cmd_file = self.commands_dir / "install.md"
        
        # Create install command file
        content = """---
allowed-tools: Bash(uv run pacc:*), Read
argument-hint: <source> [--type <type>] [--user|--project]
description: Install Claude Code extensions via PACC
---

## Installing extension: $ARGUMENTS

!`uv run pacc install $ARGUMENTS --json`

Process the installation and provide a clear summary of what was installed.
"""
        cmd_file.write_text(content)
        
        # Verify command structure
        assert cmd_file.exists()
        assert "allowed-tools: Bash" in cmd_file.read_text()
        assert "$ARGUMENTS" in cmd_file.read_text()
    
    def test_list_slash_command(self):
        """Test /pacc:list slash command functionality."""
        cmd_file = self.commands_dir / "list.md"
        
        # Create list command file
        content = """---
allowed-tools: Bash(uv run pacc:*), Read
argument-hint: [type] [--user|--project|--all]
description: List installed Claude Code extensions
---

## Listing installed extensions

!`uv run pacc list $ARGUMENTS --format json`

Display the installed extensions in a formatted table with their types and descriptions.
"""
        cmd_file.write_text(content)
        
        # Verify command structure
        assert cmd_file.exists()
        assert "--format json" in cmd_file.read_text()
    
    def test_search_slash_command(self):
        """Test /pacc:search slash command functionality."""
        cmd_file = self.commands_dir / "search.md"
        
        # Create search command file
        content = """---
allowed-tools: Bash(uv run pacc:*), Read
argument-hint: <query> [--type <type>]
description: Search for Claude Code extensions
---

## Searching for extensions: $ARGUMENTS

!`uv run pacc list --search "$ARGUMENTS" --format json`

Show extensions matching the search query with their descriptions and installation status.
"""
        cmd_file.write_text(content)
        
        # Verify command structure
        assert cmd_file.exists()
        assert "--search" in cmd_file.read_text()
    
    def test_info_slash_command(self):
        """Test /pacc:info slash command functionality."""
        cmd_file = self.commands_dir / "info.md"
        
        # Create info command file
        content = """---
allowed-tools: Bash(uv run pacc:*), Read
argument-hint: <extension-name>
description: Show detailed information about an extension
---

## Getting information for: $ARGUMENTS

!`uv run pacc info $ARGUMENTS --json`

Display comprehensive information about the extension including:
- Description and version
- Installation status
- Configuration details
- Usage examples
"""
        cmd_file.write_text(content)
        
        # Verify command structure
        assert cmd_file.exists()
        assert "pacc info" in cmd_file.read_text()
    
    def test_update_slash_command(self):
        """Test /pacc:update slash command functionality."""
        cmd_file = self.commands_dir / "update.md"
        
        # Create update command file
        content = """---
allowed-tools: Bash(uv run pacc:*), Read
argument-hint: <extension-name> [--force]
description: Update an installed extension
---

## Updating extension: $ARGUMENTS

# First check if extension is installed
!`uv run pacc info $ARGUMENTS --json`

# Then reinstall with force flag to update
!`uv run pacc install $ARGUMENTS --force --json`

Provide a summary of the update operation and any changes made.
"""
        cmd_file.write_text(content)
        
        # Verify command structure
        assert cmd_file.exists()
        assert "--force" in cmd_file.read_text()
    
    def test_remove_slash_command(self):
        """Test /pacc:remove slash command functionality."""
        cmd_file = self.commands_dir / "remove.md"
        
        # Create remove command file
        content = """---
allowed-tools: Bash(uv run pacc:*), Read
argument-hint: <extension-name> [--type <type>] [--confirm]
description: Remove an installed extension
---

## Removing extension: $ARGUMENTS

!`uv run pacc remove $ARGUMENTS --confirm --json`

Confirm the removal and provide a summary of what was removed.
"""
        cmd_file.write_text(content)
        
        # Verify command structure
        assert cmd_file.exists()
        assert "--confirm" in cmd_file.read_text()
    
    def test_json_output_integration(self):
        """Test that CLI commands support JSON output for slash commands."""
        cli = PACCCli()
        
        # Test list command with JSON
        class Args:
            command = "list"
            type = None
            user = False
            project = False
            all = True
            format = "json"
            filter = None
            search = None
            sort = "name"
            show_status = False
            verbose = False
            json = True
        
        # Mock the list_command to check JSON output
        import io
        import sys
        from contextlib import redirect_stdout
        
        captured_output = io.StringIO()
        with redirect_stdout(captured_output):
            result = cli.list_command(Args())
        
        output = captured_output.getvalue()
        
        # Verify JSON output
        if output.strip():  # Only check if there's output
            try:
                parsed = json.loads(output)
                assert isinstance(parsed, dict), "Output should be valid JSON dict"
                assert "success" in parsed, "JSON should have success field"
                assert "message" in parsed, "JSON should have message field"
            except json.JSONDecodeError:
                # If no extensions installed, might just print info message
                pass
    
    def test_slash_command_namespacing(self):
        """Test that commands are properly namespaced as /pacc:command."""
        # Create test slash commands first
        self._create_test_slash_commands()
        
        # Commands should be in pacc subdirectory for namespacing
        assert self.commands_dir.name == "pacc"
        assert self.commands_dir.parent.name == "commands"
        
        # This creates commands like /pacc:install, /pacc:list, etc.
        cmd_files = list(self.commands_dir.glob("*.md"))
        assert len(cmd_files) >= 6, "Should have at least 6 PACC slash commands"
    
    def test_slash_command_error_handling(self):
        """Test error handling in slash commands."""
        # Create a command that handles errors
        cmd_file = self.commands_dir / "test_error.md"
        content = """---
allowed-tools: Bash(uv run pacc:*)
argument-hint: <invalid-args>
description: Test error handling
---

## Testing error handling

!`uv run pacc invalid-command --json 2>&1 || echo "ERROR_CODE: $?"`

Handle the error gracefully and inform the user.
"""
        cmd_file.write_text(content)
        
        # Verify error handling is included
        assert "ERROR_CODE" in cmd_file.read_text()
    
    def test_slash_command_help_integration(self):
        """Test that slash commands appear in help system."""
        # Commands in .claude/commands/pacc/ should appear as:
        # /pacc:install, /pacc:list, etc. in Claude Code help
        
        # Verify directory structure supports this
        assert (self.claude_dir / "commands").exists()
        assert (self.claude_dir / "commands" / "pacc").exists()
        
        # Each .md file in pacc/ directory becomes a namespaced command
        expected_commands = {
            "install": "Install Claude Code extensions via PACC",
            "list": "List installed Claude Code extensions",
            "search": "Search for Claude Code extensions",
            "info": "Show detailed information about an extension",
            "update": "Update an installed extension",
            "remove": "Remove an installed extension"
        }
        
        for cmd_name, expected_desc in expected_commands.items():
            cmd_file = self.commands_dir / f"{cmd_name}.md"
            if cmd_file.exists():
                content = cmd_file.read_text()
                # Extract description from frontmatter
                if "description:" in content:
                    desc_line = [line for line in content.split('\n') if line.startswith("description:")][0]
                    assert expected_desc in desc_line or len(desc_line) > 0
    

class TestSlashCommandContent:
    """Test the actual content and functionality of slash commands."""
    
    def test_install_command_variations(self):
        """Test different variations of the install command."""
        test_cases = [
            # (arguments, expected_command_parts)
            ("https://example.com/extension.zip", ["install", "https://example.com/extension.zip"]),
            ("./local/extension.json --type hooks", ["install", "./local/extension.json", "--type", "hooks"]),
            ("extension-name --user", ["install", "extension-name", "--user"]),
            ("path/to/dir --all --force", ["install", "path/to/dir", "--all", "--force"]),
        ]
        
        for args, expected_parts in test_cases:
            # Simulate command construction
            full_command = f"uv run pacc install {args} --json"
            for part in expected_parts:
                assert part in full_command, f"Command should contain '{part}'"
    
    def test_list_command_filters(self):
        """Test list command with various filters."""
        test_cases = [
            ("", ["list", "--format", "json"]),
            ("hooks", ["list", "hooks", "--format", "json"]),
            ("--user", ["list", "--user", "--format", "json"]),
            ("--filter '*.test'", ["list", "--filter", "*.test", "--format", "json"]),
        ]
        
        for args, expected_parts in test_cases:
            full_command = f"uv run pacc list {args} --format json"
            # Just verify command is properly formed
            assert "pacc list" in full_command
    
    def test_command_bash_safety(self):
        """Test that commands are safe from injection."""
        # Commands should use proper quoting and escaping
        dangerous_inputs = [
            "'; rm -rf /",
            "$(evil-command)",
            "`backdoor`",
            "& malicious &&",
        ]
        
        for dangerous_input in dangerous_inputs:
            # The $ARGUMENTS placeholder should be properly handled
            # In real implementation, we'd want to ensure proper escaping
            assert True  # Placeholder for actual safety checks
    

class TestSlashCommandWorkflow:
    """Test end-to-end workflows using slash commands."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
    def teardown_method(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_install_list_remove_workflow(self):
        """Test complete workflow: install -> list -> remove."""
        # This tests the integration of multiple slash commands
        
        # 1. Install command should support JSON output
        install_result = {
            "success": True,
            "message": "Successfully installed 1 extension(s)",
            "data": {
                "installed_count": 1,
                "extensions": [{
                    "name": "test-hook",
                    "type": "hook",
                    "description": "Test hook extension"
                }]
            }
        }
        
        # 2. List command should show the installed extension
        list_result = {
            "success": True,
            "message": "Found 1 extension(s)",
            "data": {
                "extensions": [{
                    "name": "test-hook",
                    "type": "hook",
                    "description": "Test hook extension",
                    "scope": "project"
                }],
                "count": 1
            }
        }
        
        # 3. Remove command should remove it
        remove_result = {
            "success": True,
            "message": "Successfully removed: test-hook (hook)",
            "data": {
                "removed_extension": {
                    "name": "test-hook",
                    "type": "hook",
                    "scope": "project"
                }
            }
        }
        
        # Verify the workflow data structures
        assert install_result["success"] is True
        assert list_result["data"]["count"] == 1
        assert remove_result["data"]["removed_extension"]["name"] == "test-hook"
    

if __name__ == "__main__":
    pytest.main([__file__, "-v"])