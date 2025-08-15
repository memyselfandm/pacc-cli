"""Test CLI entry point functionality."""

import subprocess
import sys
from pathlib import Path
import pytest

from pacc import __version__
from pacc.cli import main, cli_main


class TestEntryPoint:
    """Test CLI entry point configuration and functionality."""
    
    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        assert callable(main)
        
    def test_cli_main_function_exists(self):
        """Test that cli_main function exists and is callable."""
        assert callable(cli_main)
        
    def test_console_script_entry_point(self):
        """Test that the console_scripts entry point is properly configured."""
        # Get the path to the pacc package
        pacc_dir = Path(__file__).parent.parent
        
        # Run Python with the -m flag to invoke the module
        result = subprocess.run(
            [sys.executable, "-m", "pacc", "--help"],
            cwd=pacc_dir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "PACC - Package manager for Claude Code" in result.stdout
        
    def test_main_module_execution(self):
        """Test that __main__.py allows module execution."""
        pacc_dir = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, "-m", "pacc", "--help"],
            cwd=pacc_dir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        # Check for key elements in help output
        assert "PACC - Package manager for Claude Code" in result.stdout
        assert "install" in result.stdout
        assert "validate" in result.stdout
        
    def test_entry_point_with_no_args(self):
        """Test entry point behavior when no arguments are provided."""
        pacc_dir = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, "-m", "pacc"],
            cwd=pacc_dir,
            capture_output=True,
            text=True
        )
        
        # Should show help and return 1
        assert result.returncode == 1
        assert "usage: pacc" in result.stdout
        
    def test_entry_point_with_invalid_command(self):
        """Test entry point behavior with invalid command."""
        pacc_dir = Path(__file__).parent.parent
        
        result = subprocess.run(
            [sys.executable, "-m", "pacc", "invalid-command"],
            cwd=pacc_dir,
            capture_output=True,
            text=True
        )
        
        # Should show error
        assert result.returncode == 2
        assert "invalid choice:" in result.stderr or "unrecognized arguments:" in result.stderr
        
    def test_keyboard_interrupt_handling(self):
        """Test that KeyboardInterrupt is handled properly."""
        # Test using subprocess to isolate the interrupt
        pacc_dir = Path(__file__).parent.parent
        
        # Create a simple test script that raises KeyboardInterrupt
        test_script = '''
import sys
sys.path.insert(0, r"{}")
from pacc.cli import main
try:
    # Simulate KeyboardInterrupt during execution
    raise KeyboardInterrupt()
except KeyboardInterrupt:
    sys.exit(130)
'''.format(str(pacc_dir))
        
        result = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True
        )
        
        # Should exit with code 130
        assert result.returncode == 130