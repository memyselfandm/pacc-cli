"""Performance tests for the PACC list command."""

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from pacc.cli import PACCCli


class TestListCommandPerformance:
    """Performance tests for list command functionality."""

    @pytest.fixture
    def cli(self):
        """Create CLI instance for testing."""
        return PACCCli()

    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager."""
        with patch("pacc.cli.ClaudeConfigManager") as mock:
            yield mock

    def create_large_config(self, num_extensions_per_type=500):
        """Create configuration with many extensions for performance testing."""
        config = {"hooks": [], "mcps": [], "agents": [], "commands": []}

        for i in range(num_extensions_per_type):
            config["hooks"].append(
                {
                    "name": f"perf-hook-{i:04d}",
                    "path": f"hooks/perf-hook-{i:04d}.json",
                    "description": f"Performance test hook number {i} for benchmarking the list command with many extensions",
                    "events": ["file:created", "file:modified"] if i % 2 else ["project:build"],
                    "matchers": ["*.py", "*.js"] if i % 3 else ["*"],
                    "installed_at": f"2024-{(i%12)+1:02d}-{(i%28)+1:02d}T{i%24:02d}:{i%60:02d}:00Z",
                    "source": "local" if i % 3 == 0 else f"github.com/user/repo-{i}",
                    "version": f"{(i//100)+1}.{(i//10)%10}.{i%10}",
                }
            )

            config["mcps"].append(
                {
                    "name": f"perf-mcp-{i:04d}",
                    "path": f"mcps/perf-mcp-{i:04d}.py",
                    "command": f"python mcps/perf-mcp-{i:04d}.py",
                    "args": ["--port", str(5000 + i)],
                    "description": f"Performance test MCP server {i} for load testing the listing functionality",
                    "installed_at": f"2024-{(i%12)+1:02d}-{(i%28)+1:02d}T{i%24:02d}:{i%60:02d}:30Z",
                    "source": "local" if i % 2 == 0 else "pacc-registry",
                    "version": f"{(i//50)+1}.{(i//5)%10}.{i%5}",
                }
            )

            config["agents"].append(
                {
                    "name": f"perf-agent-{i:04d}",
                    "path": f"agents/perf-agent-{i:04d}.md",
                    "model": "claude-3-sonnet" if i % 2 else "claude-3-haiku",
                    "description": f"Performance test agent {i} for evaluating list command scalability with large datasets",
                    "tools": ["read", "edit", "grep"] if i % 2 else ["write", "search"],
                    "installed_at": f"2024-{(i%12)+1:02d}-{(i%28)+1:02d}T{i%24:02d}:{i%60:02d}:45Z",
                    "source": "pacc-registry" if i % 3 == 0 else "local",
                }
            )

            config["commands"].append(
                {
                    "name": f"/perf-cmd-{i:04d}",
                    "path": f"commands/perf-cmd-{i:04d}.md",
                    "description": f"Performance test command {i} for measuring list command efficiency",
                    "aliases": [f"/p{i}", f"/perf{i}"],
                    "installed_at": f"2024-{(i%12)+1:02d}-{(i%28)+1:02d}T{i%24:02d}:{i%60:02d}:15Z",
                    "source": "local",
                }
            )

        return config

    def test_list_performance_large_dataset_table_format(self, cli, mock_config_manager):
        """Test table format performance with large dataset."""
        large_config = self.create_large_config(100)  # 400 total extensions

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
        execution_time = end_time - start_time
        assert (
            execution_time < 1.0
        ), f"Table format took {execution_time:.3f}s, should be under 1.0s"

    def test_list_performance_large_dataset_json_format(self, cli, mock_config_manager):
        """Test JSON format performance with large dataset."""
        large_config = self.create_large_config(150)  # 600 total extensions

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = large_config
        mock_config_manager.return_value = mock_manager

        args = Mock()
        args.type = None
        args.user = False
        args.project = True
        args.all = False
        args.format = "json"
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
        execution_time = end_time - start_time
        assert execution_time < 0.5, f"JSON format took {execution_time:.3f}s, should be under 0.5s"

    def test_list_performance_filtering_large_dataset(self, cli, mock_config_manager):
        """Test filtering performance with large dataset."""
        large_config = self.create_large_config(200)  # 800 total extensions

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = large_config
        mock_config_manager.return_value = mock_manager

        args = Mock()
        args.type = None
        args.user = False
        args.project = True
        args.all = False
        args.format = "list"
        args.filter = "*-hook-*"  # Should match all hooks
        args.search = "Performance test"  # Should match all descriptions
        args.sort = "name"
        args.verbose = False
        args.show_status = False

        # Measure performance
        start_time = time.time()
        result = cli.list_command(args)
        end_time = time.time()

        # Verify
        assert result == 0
        execution_time = end_time - start_time
        assert execution_time < 1.0, f"Filtering took {execution_time:.3f}s, should be under 1.0s"

    def test_list_performance_date_sorting_large_dataset(self, cli, mock_config_manager):
        """Test date sorting performance with large dataset."""
        large_config = self.create_large_config(100)  # 400 total extensions

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = large_config
        mock_config_manager.return_value = mock_manager

        args = Mock()
        args.type = None
        args.user = False
        args.project = True
        args.all = False
        args.format = "list"
        args.filter = None
        args.search = None
        args.sort = "date"  # Most expensive sort operation
        args.verbose = False
        args.show_status = False

        # Measure performance
        start_time = time.time()
        result = cli.list_command(args)
        end_time = time.time()

        # Verify
        assert result == 0
        execution_time = end_time - start_time
        assert (
            execution_time < 1.0
        ), f"Date sorting took {execution_time:.3f}s, should be under 1.0s"

    def test_list_performance_verbose_mode_large_dataset(self, cli, mock_config_manager):
        """Test verbose mode performance with large dataset."""
        large_config = self.create_large_config(75)  # 300 total extensions

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
        args.verbose = True  # Show additional metadata
        args.show_status = False

        # Measure performance
        start_time = time.time()
        result = cli.list_command(args)
        end_time = time.time()

        # Verify
        assert result == 0
        execution_time = end_time - start_time
        assert (
            execution_time < 1.5
        ), f"Verbose mode took {execution_time:.3f}s, should be under 1.5s"

    def test_list_performance_memory_usage(self, cli, mock_config_manager):
        """Test that memory usage remains reasonable with large datasets."""
        import os

        import psutil

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        large_config = self.create_large_config(250)  # 1000 total extensions

        # Setup mock
        mock_manager = MagicMock()
        mock_manager.load_config.return_value = large_config
        mock_config_manager.return_value = mock_manager

        args = Mock()
        args.type = None
        args.user = False
        args.project = True
        args.all = False
        args.format = "json"
        args.filter = None
        args.search = None
        args.sort = "name"
        args.verbose = True
        args.show_status = False

        # Execute
        result = cli.list_command(args)

        # Check memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Verify
        assert result == 0
        assert (
            memory_increase < 50
        ), f"Memory increased by {memory_increase:.1f}MB, should be under 50MB"
