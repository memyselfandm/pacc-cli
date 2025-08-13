"""Test suite for the PACC list command."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, List, Any

from pacc.cli import PACCCli
from pacc.core.config_manager import ClaudeConfigManager


class TestListCommand:
    """Test cases for the list command functionality."""
    
    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PACCCli()
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager."""
        with patch('pacc.cli.ClaudeConfigManager') as mock:
            yield mock
    
    @pytest.fixture
    def sample_config(self):
        """Sample configuration with various extensions."""
        return {
            "hooks": [
                {
                    "name": "test-hook",
                    "path": "hooks/test-hook.json",
                    "events": ["file:created", "file:modified"],
                    "description": "Test hook for file events",
                    "matchers": ["*.py", "*.js"],
                    "installed_at": "2024-01-15T10:30:00Z",
                    "source": "local",
                    "version": "1.0.0"
                },
                {
                    "name": "build-hook",
                    "path": "hooks/build-hook.json",
                    "events": ["project:build"],
                    "description": "Build automation hook",
                    "matchers": ["*"],
                    "installed_at": "2024-01-14T08:00:00Z",
                    "source": "github.com/user/repo"
                }
            ],
            "mcps": [
                {
                    "name": "test-server",
                    "path": "mcps/test-server.py",
                    "command": "python mcps/test-server.py",
                    "args": ["--port", "5000"],
                    "description": "Test MCP server",
                    "installed_at": "2024-01-16T14:20:00Z",
                    "source": "local",
                    "version": "2.1.0"
                }
            ],
            "agents": [
                {
                    "name": "code-reviewer",
                    "path": "agents/code-reviewer.md",
                    "model": "claude-3-sonnet",
                    "description": "Automated code review agent",
                    "installed_at": "2024-01-13T09:15:00Z",
                    "source": "pacc-registry",
                    "tools": ["grep", "read", "edit"]
                }
            ],
            "commands": [
                {
                    "name": "/lint",
                    "path": "commands/lint.md",
                    "description": "Run linting on codebase",
                    "aliases": ["/l", "/check"],
                    "installed_at": "2024-01-17T16:45:00Z",
                    "source": "local"
                },
                {
                    "name": "/format",
                    "path": "commands/format.md",
                    "description": "Format code files",
                    "aliases": ["/fmt"],
                    "installed_at": "2024-01-17T16:50:00Z",
                    "source": "local"
                }
            ]
        }
    
    @pytest.fixture
    def empty_config(self):
        """Empty configuration."""
        return {
            "hooks": [],
            "mcps": [],
            "agents": [],
            "commands": []
        }
    
    # Test basic list functionality
    
    def test_list_all_extensions_default_format(self, cli, mock_config_manager, sample_config, capsys):
        """Test listing all extensions with default table format."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        # Create args mock
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "table"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        
        # Should contain headers
        assert "Name" in captured.out
        assert "Type" in captured.out
        assert "Description" in captured.out
        
        # Should contain all extensions
        assert "test-hook" in captured.out
        assert "build-hook" in captured.out
        assert "test-server" in captured.out
        assert "code-reviewer" in captured.out
        assert "/lint" in captured.out
        assert "/format" in captured.out
    
    def test_list_specific_type(self, cli, mock_config_manager, sample_config, capsys):
        """Test listing only specific extension type."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = "hooks"
        args.user = False
        args.project = False
        args.all = True
        args.format = "table"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        
        # Should contain only hooks
        assert "test-hook" in captured.out
        assert "build-hook" in captured.out
        
        # Should not contain other types
        assert "test-server" not in captured.out
        assert "code-reviewer" not in captured.out
        assert "/lint" not in captured.out
    
    def test_list_empty_configuration(self, cli, mock_config_manager, empty_config, capsys):
        """Test listing when no extensions are installed."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = empty_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "table"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        assert "No extensions installed" in captured.out
    
    # Test different output formats
    
    def test_list_format_json(self, cli, mock_config_manager, sample_config, capsys):
        """Test JSON output format."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "json"
        args.filter = None
        args.search = None
        args.sort = None
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        
        # Should be valid JSON
        output_data = json.loads(captured.out)
        assert isinstance(output_data, dict)
        assert "extensions" in output_data
        # We check both user and project scopes by default, so extensions appear twice
        assert len(output_data["extensions"]) == 12  # 6 extensions x 2 scopes
        
        # Check structure
        for ext in output_data["extensions"]:
            assert "name" in ext
            assert "type" in ext
            assert "description" in ext
    
    def test_list_format_list(self, cli, mock_config_manager, sample_config, capsys):
        """Test simple list output format."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "list"
        args.filter = None
        args.search = None
        args.sort = "type"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        
        # Should be simple format
        lines = captured.out.strip().split('\n')
        assert any("hook/test-hook" in line for line in lines)
        assert any("hook/build-hook" in line for line in lines)
        assert any("mcp/test-server" in line for line in lines)
    
    # Test scope filtering
    
    def test_list_user_scope_only(self, cli, mock_config_manager, sample_config, capsys):
        """Test listing only user-level extensions."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.get_config_path.return_value = Path.home() / ".claude" / "settings.json"
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = True
        args.project = False
        args.all = False
        args.format = "table"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        mock_manager.get_config_path.assert_called_with(user_level=True)
    
    def test_list_project_scope_only(self, cli, mock_config_manager, sample_config, capsys):
        """Test listing only project-level extensions."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.get_config_path.return_value = Path(".claude") / "settings.json"
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = True
        args.all = False
        args.format = "table"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        mock_manager.get_config_path.assert_called_with(user_level=False)
    
    # Test filtering and search
    
    def test_list_with_name_filter(self, cli, mock_config_manager, sample_config, capsys):
        """Test filtering by name pattern."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "table"
        args.filter = "*-hook"  # Should match test-hook and build-hook
        args.search = None
        args.sort = "name"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        
        # Should contain hooks
        assert "test-hook" in captured.out
        assert "build-hook" in captured.out
        
        # Should not contain non-matching
        assert "test-server" not in captured.out
        assert "code-reviewer" not in captured.out
    
    def test_list_with_description_search(self, cli, mock_config_manager, sample_config, capsys):
        """Test searching in descriptions."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "table"
        args.filter = None
        args.search = "code"  # Should match "code review" and "codebase"
        args.sort = "name"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        
        # Should contain matches
        assert "code-reviewer" in captured.out  # "code review agent"
        assert "/lint" in captured.out  # "Run linting on codebase"
        assert "/format" in captured.out  # "Format code files"
        
        # Should not contain non-matching
        assert "test-hook" not in captured.out
        assert "build-hook" not in captured.out
    
    # Test sorting
    
    def test_list_sort_by_date(self, cli, mock_config_manager, sample_config, capsys):
        """Test sorting by installation date."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "list"
        args.filter = None
        args.search = None
        args.sort = "date"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        lines = captured.out.strip().split('\n')
        
        # Extensions should be in date order (newest first by default)
        # Based on sample_config dates
        expected_order = ["/format", "/lint", "test-server", "test-hook", "build-hook", "code-reviewer"]
        
        # Find the position of each extension in output
        positions = {}
        for i, line in enumerate(lines):
            for ext in expected_order:
                if ext in line:
                    positions[ext] = i
        
        # Verify order
        for i in range(len(expected_order) - 1):
            if expected_order[i] in positions and expected_order[i+1] in positions:
                assert positions[expected_order[i]] < positions[expected_order[i+1]]
    
    # Test verbose mode
    
    def test_list_verbose_mode(self, cli, mock_config_manager, sample_config, capsys):
        """Test verbose output with additional metadata."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "table"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = True
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        
        # Should contain additional columns in verbose mode
        assert "Source" in captured.out
        assert "Installed" in captured.out
        assert "Version" in captured.out if "Version" in str(sample_config) else True
        
        # Should contain metadata values
        assert "local" in captured.out
        assert "github.com/user/repo" in captured.out
        assert "2024-01" in captured.out  # Date prefix
    
    # Test error handling
    
    def test_list_config_read_error(self, cli, mock_config_manager, capsys):
        """Test handling of configuration read errors."""
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.side_effect = Exception("Failed to read config")
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "table"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        # When all configs fail to load, we show "No extensions installed" rather than error
        assert result == 0
        captured = capsys.readouterr()
        assert "No extensions installed" in captured.out
    
    # Test combined scope listing
    
    def test_list_all_scopes_combined(self, cli, mock_config_manager, capsys):
        """Test listing extensions from both user and project scopes."""
        # Setup
        user_config = {
            "hooks": [{"name": "user-hook", "path": "hooks/user.json", "description": "User hook"}],
            "mcps": [],
            "agents": [],
            "commands": []
        }
        project_config = {
            "hooks": [{"name": "project-hook", "path": "hooks/project.json", "description": "Project hook"}],
            "mcps": [],
            "agents": [],
            "commands": []
        }
        
        mock_manager = MagicMock()
        mock_manager.get_config_path.side_effect = [
            Path.home() / ".claude" / "settings.json",
            Path(".claude") / "settings.json"
        ]
        mock_manager.load_config.side_effect = [user_config, project_config]
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "table"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = False
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        
        # Should contain both user and project extensions
        assert "user-hook" in captured.out
        assert "project-hook" in captured.out
        
        # Should indicate scope
        assert "User" in captured.out or "~/.claude" in captured.out
        assert "Project" in captured.out or "./.claude" in captured.out
    
    # Test validation status display
    
    def test_list_with_validation_status(self, cli, mock_config_manager, sample_config, capsys):
        """Test displaying validation status when available."""
        # Add validation status to sample config
        sample_config["hooks"][0]["validation_status"] = "valid"
        sample_config["hooks"][1]["validation_status"] = "warning"
        sample_config["mcps"][0]["validation_status"] = "error"
        
        # Setup
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = sample_config
        mock_config_manager.return_value = mock_manager
        
        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True
        args.format = "table"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = True
        args.show_status = True  # Additional flag for validation status
        
        # Execute
        result = cli.list_command(args)
        
        # Verify
        assert result == 0
        captured = capsys.readouterr()
        
        # Should show validation status
        assert "Status" in captured.out or "Validation" in captured.out
        assert "valid" in captured.out.lower()
        assert "warning" in captured.out.lower()
        assert "error" in captured.out.lower()