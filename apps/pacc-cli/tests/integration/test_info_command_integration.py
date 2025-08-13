"""Integration tests for PACC info command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from pacc.cli import main


class TestInfoCommandIntegration:
    """Integration tests for info command end-to-end scenarios."""

    @pytest.fixture
    def sample_hook_file(self, tmp_path):
        """Create a sample hook file for testing."""
        hook_data = {
            "name": "integration-test-hook",
            "description": "A hook for integration testing",
            "version": "2.0.0",
            "eventTypes": ["PreToolUse"],
            "commands": ["echo 'Integration test hook executed'"],
            "matchers": []
        }
        hook_file = tmp_path / "integration-hook.json"
        hook_file.write_text(json.dumps(hook_data, indent=2))
        return hook_file

    @pytest.fixture  
    def sample_agent_file(self, tmp_path):
        """Create a sample agent file for testing."""
        agent_content = """---
name: integration-agent
description: An agent for integration testing
version: 2.1.0
model: claude-3-haiku
tools: [web_search]
---

# Integration Test Agent

This agent is used for integration testing of the PACC info command.

## Capabilities

- Web search functionality
- Basic conversation handling
"""
        agent_file = tmp_path / "integration-agent.md"
        agent_file.write_text(agent_content)
        return agent_file

    def test_info_command_file_integration(self, sample_hook_file, capsys):
        """Test info command with real file integration."""
        # Test with minimal arguments
        with patch('sys.argv', ['pacc', 'info', str(sample_hook_file)]):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        
        # Check that key information is displayed
        assert "integration-test-hook" in captured.out
        assert "A hook for integration testing" in captured.out
        assert "2.0.0" in captured.out
        assert "hooks" in captured.out

    def test_info_command_verbose_integration(self, sample_hook_file, capsys):
        """Test info command with verbose flag integration."""
        with patch('sys.argv', ['pacc', 'info', str(sample_hook_file), '--verbose']):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        
        # Should show detailed information in verbose mode
        assert "Extension Details:" in captured.out
        assert "PreToolUse" in captured.out

    def test_info_command_json_integration(self, sample_agent_file, capsys):
        """Test info command with JSON output integration."""
        with patch('sys.argv', ['pacc', 'info', str(sample_agent_file), '--json']):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        
        # Should output valid JSON
        try:
            output_data = json.loads(captured.out)
            assert output_data["name"] == "integration-agent"
            assert output_data["type"] == "agents"
            assert output_data["version"] == "2.1.0"
        except json.JSONDecodeError:
            pytest.fail("Output was not valid JSON")

    def test_info_command_type_filter_integration(self, sample_agent_file, capsys):
        """Test info command with type filter integration."""
        with patch('sys.argv', ['pacc', 'info', str(sample_agent_file), '--type', 'agents', '--verbose']):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        
        assert "integration-agent" in captured.out
        assert "claude-3-haiku" in captured.out

    def test_info_command_nonexistent_file_integration(self, capsys):
        """Test info command with non-existent file integration."""
        with patch('sys.argv', ['pacc', 'info', '/nonexistent/path/file.json']):
            result = main()

        assert result == 1
        captured = capsys.readouterr()
        
        assert "does not exist" in captured.err

    def test_info_command_help_integration(self, capsys):
        """Test info command help output."""
        with patch('sys.argv', ['pacc', 'info', '--help']):
            with pytest.raises(SystemExit) as excinfo:
                main()
            
            # Help exits with code 0
            assert excinfo.value.code == 0

        captured = capsys.readouterr()
        
        # Should show help information
        assert "Display detailed information about extensions" in captured.out
        assert "--json" in captured.out
        assert "--show-related" in captured.out
        assert "--show-usage" in captured.out

    def test_info_command_with_usage_examples_integration(self, sample_hook_file, capsys):
        """Test info command with usage examples integration."""
        with patch('sys.argv', ['pacc', 'info', str(sample_hook_file), '--show-usage']):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        
        # Should show usage examples section
        assert "Usage Examples:" in captured.out
        assert "automatically triggered" in captured.out

    def test_info_command_with_troubleshooting_integration(self, sample_agent_file, capsys):
        """Test info command with troubleshooting information."""
        with patch('sys.argv', ['pacc', 'info', str(sample_agent_file), '--show-troubleshooting']):
            result = main()

        assert result == 0  
        captured = capsys.readouterr()
        
        # Should show troubleshooting section
        assert "Troubleshooting:" in captured.out