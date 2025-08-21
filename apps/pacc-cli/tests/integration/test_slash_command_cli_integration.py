"""Integration test for slash command and CLI integration.

This test validates that slash commands properly integrate with the PACC CLI
and that the output formatting is correct for Claude Code consumption.
"""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest


class TestSlashCommandCLIIntegration:
    """Test actual slash command integration with CLI execution."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.claude_dir = Path(self.temp_dir) / ".claude"
        self.plugins_dir = self.claude_dir / "plugins"
        
        # Create directory structure
        self.claude_dir.mkdir(parents=True)
        self.plugins_dir.mkdir(parents=True)
        
        # Create settings.json
        settings_path = self.claude_dir / "settings.json"
        settings_path.write_text(json.dumps({}))
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('pathlib.Path.home')
    def test_plugin_list_cli_output_format(self, mock_home):
        """Test that plugin list command outputs format that slash commands expect."""
        mock_home.return_value = Path(self.temp_dir)
        
        # Run the actual CLI command
        result = subprocess.run(
            ["python", "-m", "pacc", "plugin", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Should succeed even with no plugins
        assert result.returncode == 0, f"Plugin list failed: {result.stderr}"
        
        # Output should be readable and informative
        output = result.stdout
        assert len(output) > 0, "Should have some output"
        
        # Should not have Python errors or tracebacks
        assert "Traceback" not in result.stderr, f"Should not have Python errors: {result.stderr}"
        assert "Error" not in result.stderr, f"Unexpected error: {result.stderr}"
    
    @patch('pathlib.Path.home') 
    def test_plugin_env_status_cli_output(self, mock_home):
        """Test environment status CLI output format."""
        mock_home.return_value = Path(self.temp_dir)
        
        # Run environment status command
        result = subprocess.run(
            ["python", "-m", "pacc", "plugin", "env", "status"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Should succeed
        assert result.returncode == 0, f"Environment status failed: {result.stderr}"
        
        # Output should contain key information
        output = result.stdout
        assert "Platform:" in output, "Should show platform information"
        assert "Shell:" in output, "Should show shell information"
        assert "ENABLE_PLUGINS" in output, "Should show ENABLE_PLUGINS status"
        
        # Should have helpful formatting for user
        assert "ℹ" in output or "Info:" in output, "Should have informational indicators"
    
    @patch('pathlib.Path.home')
    def test_plugin_env_verify_cli_output(self, mock_home):
        """Test environment verify CLI output format."""
        mock_home.return_value = Path(self.temp_dir)
        
        # Run environment verify command
        result = subprocess.run(
            ["python", "-m", "pacc", "plugin", "env", "verify"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Return code will depend on environment state, both success/failure are valid
        assert result.returncode in [0, 1], f"Unexpected return code: {result.returncode}"
        
        # Should have clear output about verification status
        output = result.stdout
        assert len(output) > 0, "Should have verification output"
        
        # Should mention ENABLE_PLUGINS in some way
        output_combined = output + result.stderr
        assert "ENABLE_PLUGINS" in output_combined, "Should mention ENABLE_PLUGINS"
    
    def test_plugin_help_output_format(self):
        """Test that plugin help output is well-formatted."""
        
        # Test main plugin help
        result = subprocess.run(
            ["python", "-m", "pacc", "plugin", "--help"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"Plugin help failed: {result.stderr}"
        
        output = result.stdout
        # Should have standard help formatting
        assert "usage:" in output.lower(), "Should show usage information"
        assert "install" in output, "Should list install command"
        assert "list" in output, "Should list list command"
        assert "enable" in output, "Should list enable command"
        assert "env" in output, "Should list env command"
        
        # Test environment help specifically
        result = subprocess.run(
            ["python", "-m", "pacc", "plugin", "env", "--help"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        assert result.returncode == 0, f"Plugin env help failed: {result.stderr}"
        
        env_output = result.stdout
        assert "setup" in env_output, "Should list setup command"
        assert "status" in env_output, "Should list status command" 
        assert "verify" in env_output, "Should list verify command"
        assert "reset" in env_output, "Should list reset command"
    
    def test_invalid_plugin_command_error_handling(self):
        """Test error handling for invalid plugin commands."""
        
        # Test invalid subcommand
        result = subprocess.run(
            ["python", "-m", "pacc", "plugin", "invalid-command"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Should fail with proper error code
        assert result.returncode != 0, "Invalid command should fail"
        
        # Should have helpful error message
        error_output = result.stderr
        assert len(error_output) > 0, "Should have error output"
        
        # Should suggest valid commands or show help
        combined_output = result.stdout + result.stderr
        assert "help" in combined_output.lower() or "usage" in combined_output.lower(), \
            "Should suggest help or show usage"
    
    @patch('pathlib.Path.home')
    def test_plugin_install_error_handling(self, mock_home):
        """Test plugin install error handling for invalid URLs."""
        mock_home.return_value = Path(self.temp_dir)
        
        # Test with invalid repository URL
        result = subprocess.run(
            ["python", "-m", "pacc", "plugin", "install", "invalid-url"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Should fail appropriately
        assert result.returncode != 0, "Invalid URL should cause failure"
        
        # Should have informative error message
        error_output = result.stderr
        assert len(error_output) > 0, "Should have error message"
        
        # Error should be understandable (not just a traceback)
        assert "Traceback" not in error_output, "Should not show raw Python traceback"
    
    def test_cli_performance_requirements(self):
        """Test that CLI commands meet performance requirements."""
        import time
        
        # Test plugin list performance
        start_time = time.time()
        result = subprocess.run(
            ["python", "-m", "pacc", "plugin", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )
        list_time = time.time() - start_time
        
        assert result.returncode == 0, "Plugin list should succeed"
        assert list_time < 5.0, f"Plugin list took {list_time:.2f}s, expected < 5.0s"
        
        # Test environment status performance
        start_time = time.time()
        result = subprocess.run(
            ["python", "-m", "pacc", "plugin", "env", "status"],
            capture_output=True,
            text=True,
            timeout=30
        )
        status_time = time.time() - start_time
        
        assert result.returncode == 0, "Environment status should succeed"
        assert status_time < 3.0, f"Environment status took {status_time:.2f}s, expected < 3.0s"
        
        print(f"Performance: List={list_time:.2f}s, Status={status_time:.2f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])