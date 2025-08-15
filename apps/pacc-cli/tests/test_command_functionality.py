"""Test command functionality after installation."""

import subprocess
import sys
import json
import tempfile
import shutil
from pathlib import Path
import pytest


class TestCommandFunctionality:
    """Test all major CLI commands work correctly."""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    @pytest.fixture
    def sample_hook_file(self, temp_project_dir):
        """Create a sample hook file for testing."""
        hook_content = {
            "name": "test-hook",
            "description": "Test hook for validation",
            "version": "1.0.0",
            "events": [
                {
                    "type": "PreToolUse",
                    "matcher": {"tool": "Bash"},
                    "action": {
                        "type": "Ask",
                        "config": {
                            "message": "About to run bash command: {{tool.command}}"
                        }
                    }
                }
            ]
        }
        
        hook_file = temp_project_dir / "test-hook.json"
        with open(hook_file, "w") as f:
            json.dump(hook_content, f, indent=2)
            
        return hook_file
        
    def run_pacc_command(self, args, cwd=None):
        """Helper to run pacc commands."""
        pacc_dir = Path(__file__).parent.parent
        if cwd is None:
            cwd = pacc_dir
            
        result = subprocess.run(
            [sys.executable, "-m", "pacc"] + args,
            cwd=cwd,
            capture_output=True,
            text=True
        )
        return result
        
    def test_help_command(self):
        """Test help command displays properly."""
        result = self.run_pacc_command(["--help"])
        
        assert result.returncode == 0
        assert "PACC - Package manager for Claude Code" in result.stdout
        assert "<command>" in result.stdout  # The metavar for commands
        assert "install" in result.stdout
        assert "validate" in result.stdout
        assert "list" in result.stdout
        
    def test_install_help(self):
        """Test install command help."""
        result = self.run_pacc_command(["install", "--help"])
        
        assert result.returncode == 0
        assert "Install Claude Code extensions" in result.stdout
        assert "--user" in result.stdout
        assert "--project" in result.stdout
        assert "--dry-run" in result.stdout
        
    def test_validate_help(self):
        """Test validate command help."""
        result = self.run_pacc_command(["validate", "--help"])
        
        assert result.returncode == 0
        assert "Validate extension files" in result.stdout
        assert "--type" in result.stdout
        assert "--strict" in result.stdout
        
    def test_list_help(self):
        """Test list command help."""
        result = self.run_pacc_command(["list", "--help"])
        
        assert result.returncode == 0
        assert "List installed extensions" in result.stdout
        assert "--user" in result.stdout
        assert "--project" in result.stdout
        assert "--format" in result.stdout
        
    def test_validate_command_functionality(self, sample_hook_file):
        """Test validate command works correctly."""
        result = self.run_pacc_command(["validate", str(sample_hook_file)])
        
        assert result.returncode == 0
        assert "Validation passed" in result.stdout or "✓" in result.stdout
        
    def test_validate_invalid_file(self, temp_project_dir):
        """Test validate command with invalid file."""
        invalid_file = temp_project_dir / "invalid.json"
        with open(invalid_file, "w") as f:
            f.write("{ invalid json")
            
        result = self.run_pacc_command(["validate", str(invalid_file)])
        
        assert result.returncode == 1
        assert "error" in result.stdout.lower() or "error" in result.stderr.lower()
        
    def test_list_command_empty(self, temp_project_dir):
        """Test list command when no extensions are installed."""
        result = self.run_pacc_command(["list"], cwd=temp_project_dir)
        
        assert result.returncode == 0
        assert "No extensions installed" in result.stdout
        
    def test_list_command_json_format(self, temp_project_dir):
        """Test list command with JSON output."""
        # Use --format json instead of --json
        result = self.run_pacc_command(["list", "--format", "json"], cwd=temp_project_dir)
        
        assert result.returncode == 0
        
        # Should output valid JSON
        try:
            data = json.loads(result.stdout)
            assert "success" in data
            assert data["success"] is True
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {result.stdout}")
            
    def test_command_error_handling(self):
        """Test error handling for non-existent files."""
        result = self.run_pacc_command(["validate", "/non/existent/file.json"])
        
        assert result.returncode == 1
        assert "error" in result.stdout.lower() or "error" in result.stderr.lower()
        
    def test_verbose_mode(self, sample_hook_file):
        """Test verbose mode provides additional output."""
        # Normal run
        result_normal = self.run_pacc_command(["validate", str(sample_hook_file)])
        
        # Verbose run
        result_verbose = self.run_pacc_command(["validate", str(sample_hook_file), "--verbose"])
        
        assert result_normal.returncode == 0
        assert result_verbose.returncode == 0
        
        # Verbose should have more output
        assert len(result_verbose.stdout) >= len(result_normal.stdout)
        
    def test_dry_run_mode(self, sample_hook_file, temp_project_dir):
        """Test dry-run mode doesn't make changes."""
        # Try to install with dry-run
        result = self.run_pacc_command(
            ["install", str(sample_hook_file), "--project", "--dry-run"],
            cwd=temp_project_dir
        )
        
        # Command should succeed
        assert result.returncode == 0
        assert "dry-run" in result.stdout.lower() or "would" in result.stdout.lower()
        
        # No .claude directory should be created
        claude_dir = temp_project_dir / ".claude"
        assert not claude_dir.exists()
        
    def test_json_output_consistency(self):
        """Test JSON output is consistent across commands."""
        # Test list command with JSON format
        result = self.run_pacc_command(["list", "--format", "json"])
        
        assert result.returncode == 0
        
        try:
            data = json.loads(result.stdout)
            # Standard JSON response should have these fields
            assert "success" in data
            assert "message" in data
            assert isinstance(data["success"], bool)
            assert isinstance(data["message"], str)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {result.stdout}")
            
    def test_no_color_mode(self, sample_hook_file):
        """Test no-color mode removes ANSI escape codes."""
        # Run with color (default)
        result_color = self.run_pacc_command(["validate", str(sample_hook_file)])
        
        # Run without color
        result_no_color = self.run_pacc_command(["validate", str(sample_hook_file), "--no-color"])
        
        assert result_color.returncode == 0
        assert result_no_color.returncode == 0
        
        # No color output shouldn't have ANSI escape codes
        assert "\033[" not in result_no_color.stdout
        assert "\x1b[" not in result_no_color.stdout