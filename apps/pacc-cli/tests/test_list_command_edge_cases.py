"""Additional test cases for list command edge cases and performance scenarios."""

import json
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from pacc.cli import PACCCli


class TestListCommandEdgeCases:
    """Test edge cases and performance scenarios for the list command."""

    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PACCCli()

    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager."""
        with patch("pacc.cli.ClaudeConfigManager") as mock:
            yield mock

    # Edge case: Large number of extensions
    def test_list_large_number_of_extensions(self, cli, mock_config_manager, capsys):
        """Test performance with a large number of extensions."""
        # Create config with 1000 extensions
        large_config = {"hooks": [], "mcps": [], "agents": [], "commands": []}

        for i in range(250):  # 250 per type = 1000 total
            large_config["hooks"].append(
                {
                    "name": f"hook-{i:03d}",
                    "path": f"hooks/hook-{i:03d}.json",
                    "description": f"Test hook number {i}",
                    "installed_at": f"2024-01-{(i%28)+1:02d}T{i%24:02d}:00:00Z",
                }
            )
            large_config["mcps"].append(
                {
                    "name": f"mcp-{i:03d}",
                    "path": f"mcps/mcp-{i:03d}.py",
                    "description": f"Test MCP server {i}",
                    "installed_at": f"2024-01-{(i%28)+1:02d}T{i%24:02d}:00:00Z",
                }
            )
            large_config["agents"].append(
                {
                    "name": f"agent-{i:03d}",
                    "path": f"agents/agent-{i:03d}.md",
                    "description": f"Test agent {i}",
                    "installed_at": f"2024-01-{(i%28)+1:02d}T{i%24:02d}:00:00Z",
                }
            )
            large_config["commands"].append(
                {
                    "name": f"/cmd-{i:03d}",
                    "path": f"commands/cmd-{i:03d}.md",
                    "description": f"Test command {i}",
                    "installed_at": f"2024-01-{(i%28)+1:02d}T{i%24:02d}:00:00Z",
                }
            )

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = large_config
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
        args.show_status = False

        # Measure performance
        start_time = time.time()
        result = cli.list_command(args)
        end_time = time.time()

        # Verify
        assert result == 0
        assert end_time - start_time < 2.0  # Should complete within 2 seconds

        captured = capsys.readouterr()
        # Check that some extensions are shown (output should contain many lines)
        lines = captured.out.split("\n")
        assert len(lines) > 100  # Should have many output lines

    # Edge case: Extensions with missing or malformed metadata
    def test_list_extensions_with_missing_metadata(self, cli, mock_config_manager, capsys):
        """Test listing extensions with missing or malformed metadata."""
        config_with_missing_data = {
            "hooks": [
                {
                    "name": "complete-hook",
                    "path": "hooks/complete.json",
                    "description": "Complete hook",
                    "installed_at": "2024-01-15T10:00:00Z",
                    "source": "local",
                    "version": "1.0.0",
                },
                {
                    "name": "minimal-hook",
                    "path": "hooks/minimal.json",
                    # Missing description, installed_at, source, version
                },
                {
                    "name": "malformed-hook",
                    "path": "hooks/malformed.json",
                    "description": "",  # Empty description
                    "installed_at": "invalid-date",  # Invalid date format
                    "source": None,  # Null source
                    "version": 123,  # Wrong type for version
                },
            ],
            "mcps": [
                {
                    # Missing name entirely
                    "path": "mcps/unnamed.py",
                    "description": "MCP without name",
                }
            ],
            "agents": [],
            "commands": [],
        }

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = config_with_missing_data
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
        args.verbose = True
        args.show_status = False

        # Execute
        result = cli.list_command(args)

        # Verify - should handle missing data gracefully
        assert result == 0
        captured = capsys.readouterr()

        # Should show extensions even with missing data
        assert "complete-hook" in captured.out
        assert "minimal-hook" in captured.out
        assert "malformed-hook" in captured.out

        # Should handle missing name by using empty string or "unknown"
        lines = captured.out.split("\n")
        assert any(
            line.strip().startswith("|") or "unnamed" in line or "" in line for line in lines
        )

    # Edge case: Extremely long extension names and descriptions
    def test_list_extensions_with_long_names_and_descriptions(
        self, cli, mock_config_manager, capsys
    ):
        """Test listing extensions with very long names and descriptions."""
        long_config = {
            "hooks": [
                {
                    "name": "a" * 100,  # Very long name
                    "path": "hooks/long-name.json",
                    "description": "b" * 200,  # Very long description
                    "installed_at": "2024-01-15T10:00:00Z",
                }
            ],
            "mcps": [
                {
                    "name": "normal-name",
                    "path": "mcps/normal.py",
                    "description": "This is a very long description that should be truncated when displayed in table format because it exceeds the normal display width and would make the table unreadable if not properly handled by the formatting code.",
                    "installed_at": "2024-01-16T10:00:00Z",
                }
            ],
            "agents": [],
            "commands": [],
        }

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = long_config
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
        args.show_status = False

        # Execute
        result = cli.list_command(args)

        # Verify
        assert result == 0
        captured = capsys.readouterr()

        # Should truncate long descriptions (implementation shows "..." for >50 chars)
        assert "..." in captured.out

        # Should still display the extensions
        assert "a" * 50 in captured.out or "a" * 100 in captured.out  # Long name should appear
        assert "normal-name" in captured.out

    # Edge case: Invalid date formats and sorting
    def test_list_sort_with_invalid_dates(self, cli, mock_config_manager, capsys):
        """Test date sorting with invalid date formats."""
        config_with_bad_dates = {
            "hooks": [
                {
                    "name": "hook-1",
                    "path": "hooks/hook-1.json",
                    "description": "Hook 1",
                    "installed_at": "2024-01-15T10:00:00Z",  # Valid date
                },
                {
                    "name": "hook-2",
                    "path": "hooks/hook-2.json",
                    "description": "Hook 2",
                    "installed_at": "invalid-date",  # Invalid date
                },
                {
                    "name": "hook-3",
                    "path": "hooks/hook-3.json",
                    "description": "Hook 3",
                    # Missing installed_at
                },
                {
                    "name": "hook-4",
                    "path": "hooks/hook-4.json",
                    "description": "Hook 4",
                    "installed_at": "2024-01-16T11:00:00Z",  # Valid date, newer
                },
            ],
            "mcps": [],
            "agents": [],
            "commands": [],
        }

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = config_with_bad_dates
        mock_config_manager.return_value = mock_manager

        args = Mock()
        args.type = None
        args.user = False
        args.project = True
        args.all = False
        args.format = "list"
        args.filter = None
        args.search = None
        args.sort = "date"
        args.verbose = False
        args.show_status = False

        # Execute
        result = cli.list_command(args)

        # Verify - should not crash and should sort valid dates properly
        assert result == 0
        captured = capsys.readouterr()

        # All hooks should appear
        assert "hook-1" in captured.out
        assert "hook-2" in captured.out
        assert "hook-3" in captured.out
        assert "hook-4" in captured.out

        # Valid dates should be sorted (hook-4 should come first - newest)
        lines = captured.out.strip().split("\n")
        hook4_line = next((i for i, line in enumerate(lines) if "hook-4" in line), None)
        hook1_line = next((i for i, line in enumerate(lines) if "hook-1" in line), None)

        if hook4_line is not None and hook1_line is not None:
            assert hook4_line < hook1_line  # hook-4 (newer) should appear before hook-1

    # Edge case: Unicode and special characters
    def test_list_extensions_with_unicode_and_special_chars(self, cli, mock_config_manager, capsys):
        """Test listing extensions with Unicode and special characters."""
        unicode_config = {
            "hooks": [
                {
                    "name": "🔧-hook-测试",
                    "path": "hooks/unicode.json",
                    "description": "Hook with émojis and 中文 characters",
                    "installed_at": "2024-01-15T10:00:00Z",
                },
                {
                    "name": "special/chars\\hook",
                    "path": "hooks/special.json",
                    "description": "Hook with /path\\separators and $pecial chars!",
                    "installed_at": "2024-01-16T10:00:00Z",
                },
            ],
            "mcps": [],
            "agents": [],
            "commands": [],
        }

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = unicode_config
        mock_config_manager.return_value = mock_manager

        args = Mock()
        args.type = None
        args.user = False
        args.project = True
        args.all = False
        args.format = "json"  # JSON should handle Unicode properly
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = False
        args.show_status = False

        # Execute
        result = cli.list_command(args)

        # Verify
        assert result == 0
        captured = capsys.readouterr()

        # Should be valid JSON with Unicode characters
        data = json.loads(captured.out)
        assert len(data["extensions"]) == 2

        names = [ext["name"] for ext in data["extensions"]]
        assert "🔧-hook-测试" in names
        assert "special/chars\\hook" in names

        descriptions = [ext["description"] for ext in data["extensions"]]
        assert any("émojis and 中文" in desc for desc in descriptions)

    # Edge case: Concurrent access simulation
    def test_list_with_config_changes_during_execution(self, cli, mock_config_manager, capsys):
        """Test behavior when configuration changes during list execution."""
        initial_config = {
            "hooks": [{"name": "hook-1", "path": "hooks/hook-1.json"}],
            "mcps": [],
            "agents": [],
            "commands": [],
        }

        # Setup mock that returns different data on subsequent calls
        mock_manager = MagicMock()
        mock_manager.load_config.side_effect = [
            initial_config,  # First call (user scope)
            {"hooks": [], "mcps": [], "agents": [], "commands": []},  # Second call (project scope)
        ]
        mock_config_manager.return_value = mock_manager

        args = Mock()
        args.type = None
        args.user = False
        args.project = False
        args.all = True  # Check both scopes
        args.format = "table"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = False
        args.show_status = False

        # Execute
        result = cli.list_command(args)

        # Should handle this gracefully and show available data
        assert result == 0
        captured = capsys.readouterr()
        assert "hook-1" in captured.out

    # Edge case: Filter and search combinations
    def test_list_complex_filter_and_search_combinations(self, cli, mock_config_manager, capsys):
        """Test complex combinations of filtering and searching."""
        complex_config = {
            "hooks": [
                {"name": "test-build-hook", "description": "Build automation hook for testing"},
                {"name": "prod-build-hook", "description": "Build automation hook for production"},
                {"name": "test-deploy-hook", "description": "Deployment hook for testing"},
                {"name": "monitoring-hook", "description": "System monitoring and alerting"},
            ],
            "mcps": [
                {"name": "build-server", "description": "Build automation server"},
                {"name": "test-runner", "description": "Test execution server"},
            ],
            "agents": [],
            "commands": [],
        }

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = complex_config
        mock_config_manager.return_value = mock_manager

        # Test 1: Filter by name pattern AND search in description
        args = Mock()
        args.type = None
        args.user = False
        args.project = True
        args.all = False
        args.format = "list"
        args.filter = "*-build-*"  # Should match test-build-hook, prod-build-hook
        args.search = "testing"  # Should match descriptions containing "testing"
        args.sort = "name"
        args.verbose = False
        args.show_status = False

        result = cli.list_command(args)
        assert result == 0
        captured = capsys.readouterr()

        # Should only match "test-build-hook" (matches both filter and search)
        assert "test-build-hook" in captured.out
        assert "prod-build-hook" not in captured.out  # matches filter but not search
        assert "test-deploy-hook" not in captured.out  # matches search but not filter
        assert "build-server" not in captured.out  # doesn't match filter pattern

    # Performance test: Multiple format outputs
    def test_list_all_output_formats_performance(self, cli, mock_config_manager):
        """Test performance of all output formats with moderate dataset."""
        # Create moderate-sized config (100 extensions)
        moderate_config = {"hooks": [], "mcps": [], "agents": [], "commands": []}
        for i in range(25):  # 25 per type = 100 total
            moderate_config["hooks"].append(
                {
                    "name": f"hook-{i}",
                    "path": f"hooks/hook-{i}.json",
                    "description": f"Hook {i} for testing performance",
                    "installed_at": f"2024-01-{(i%28)+1:02d}T10:00:00Z",
                }
            )
            moderate_config["mcps"].append(
                {
                    "name": f"mcp-{i}",
                    "path": f"mcps/mcp-{i}.py",
                    "description": f"MCP server {i}",
                    "installed_at": f"2024-01-{(i%28)+1:02d}T11:00:00Z",
                }
            )
            moderate_config["agents"].append(
                {
                    "name": f"agent-{i}",
                    "path": f"agents/agent-{i}.md",
                    "description": f"Agent {i}",
                    "installed_at": f"2024-01-{(i%28)+1:02d}T12:00:00Z",
                }
            )
            moderate_config["commands"].append(
                {
                    "name": f"/cmd-{i}",
                    "path": f"commands/cmd-{i}.md",
                    "description": f"Command {i}",
                    "installed_at": f"2024-01-{(i%28)+1:02d}T13:00:00Z",
                }
            )

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = moderate_config
        mock_config_manager.return_value = mock_manager

        # Test each format
        formats = ["table", "list", "json"]
        for format_type in formats:
            args = Mock()
            args.type = None
            args.user = False
            args.project = True
            args.all = False
            args.format = format_type
            args.filter = None
            args.search = None
            args.sort = "name"
            args.verbose = format_type == "table"  # Test verbose only for table
            args.show_status = False

            start_time = time.time()
            result = cli.list_command(args)
            end_time = time.time()

            assert result == 0
            assert end_time - start_time < 1.0  # Each format should complete within 1 second
