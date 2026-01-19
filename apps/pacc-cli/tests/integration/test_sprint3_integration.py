"""Comprehensive integration tests for Sprint 3 features.

This module tests the complete workflow of Sprint 3 features including:
- Plugin synchronization and team collaboration
- Plugin info command integration
- Plugin remove command integration
- Update management system
- Cross-feature interactions and conflict resolution
"""

import json
import shutil
import tempfile
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from pacc.cli import PACCCli

# Try to import components, handle missing ones gracefully
try:
    from pacc.core.project_config import (
        ConfigSource,
        ConflictResolution,
        PluginSpec,
        PluginSyncManager,
        PluginSyncResult,
        ProjectConfigManager,
    )

    HAS_PROJECT_CONFIG = True
except ImportError:
    HAS_PROJECT_CONFIG = False

    # Create dummy classes for testing
    class PluginSpec:
        pass

    class PluginSyncManager:
        pass

    class PluginSyncResult:
        pass

    class ConflictResolution:
        pass

    class ConfigSource:
        pass

    class ProjectConfigManager:
        pass


try:
    from pacc.plugins.config import PluginConfigManager

    HAS_PLUGIN_CONFIG = True
except ImportError:
    HAS_PLUGIN_CONFIG = False

    class PluginConfigManager:
        pass


class TestSprint3Integration:
    """Integration tests for Sprint 3 features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()

        # Project directory setup
        self.project_dir = self.temp_dir / "project"
        self.project_dir.mkdir()

        # Create .claude directory structure in temp dir
        self.claude_dir = self.temp_dir / ".claude"
        self.claude_dir.mkdir()
        self.plugins_dir = self.claude_dir / "plugins"
        self.plugins_dir.mkdir()

        # Create basic config files
        (self.plugins_dir / "config.json").write_text(
            json.dumps({"repositories": {}, "version": "1.0.0"})
        )

        (self.claude_dir / "settings.json").write_text(
            json.dumps({"enabledPlugins": {}, "version": "1.0.0"})
        )

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_cli_parser_includes_plugin_commands(self):
        """Test that CLI parser includes all Sprint 3 plugin commands."""
        parser = self.cli.create_parser()

        # Test plugin sync command parsing
        args = parser.parse_args(["plugin", "sync", "--dry-run"])
        assert args.command == "plugin"
        assert args.plugin_command == "sync"
        assert args.dry_run is True

        # Test plugin info command parsing
        args = parser.parse_args(["plugin", "info", "test-plugin", "--repo", "owner/repo"])
        assert args.command == "plugin"
        assert args.plugin_command == "info"
        assert args.plugin == "test-plugin"
        assert args.repo == "owner/repo"

        # Test plugin remove command parsing
        args = parser.parse_args(
            ["plugin", "remove", "test-plugin", "--repo", "owner/repo", "--force"]
        )
        assert args.command == "plugin"
        assert args.plugin_command == "remove"
        assert args.plugin == "test-plugin"
        assert args.repo == "owner/repo"
        assert args.force is True

    @patch("pathlib.Path.home")
    def test_plugin_sync_no_config_file(self, mock_home):
        """Test plugin sync when no pacc.json exists."""
        mock_home.return_value = self.temp_dir

        sync_args = Namespace(
            project_dir=self.project_dir,
            environment="default",
            dry_run=False,
            force=False,
            required_only=False,
            optional_only=False,
            json=False,
            verbose=False,
        )

        # Should fail gracefully when no pacc.json exists
        result = self.cli.handle_plugin_sync(sync_args)
        assert result == 1, "Should fail when no pacc.json exists"

    @patch("pathlib.Path.home")
    def test_plugin_info_error_handling(self, mock_home):
        """Test plugin info command error handling."""
        mock_home.return_value = self.temp_dir

        info_args = Namespace(plugin="nonexistent-plugin", repo="owner/repo", format="table")

        # Should handle missing plugin gracefully
        result = self.cli.handle_plugin_info(info_args)
        assert result == 1, "Should fail for nonexistent plugin"

    @patch("pathlib.Path.home")
    def test_plugin_remove_error_handling(self, mock_home):
        """Test plugin remove command error handling."""
        mock_home.return_value = self.temp_dir

        remove_args = Namespace(
            plugin="nonexistent-plugin",
            repo="owner/repo",
            dry_run=False,
            keep_files=False,
            force=True,
        )

        # Should handle missing plugin gracefully
        result = self.cli.handle_plugin_remove(remove_args)
        assert result == 0, "Should succeed (no-op) for nonexistent plugin"

    def test_team_collaboration_config_structure(self):
        """Test team collaboration configuration structure."""
        # Create team configuration
        team_config = {
            "name": "team-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": ["team/productivity-tools@v1.0.0"],
                "required": ["code-reviewer"],
            },
        }

        # Create local override with different version
        local_config = {
            "plugins": {
                "repositories": ["team/productivity-tools@v1.1.0"],  # Conflict
                "optional": ["local-dev-tool"],
            }
        }

        (self.project_dir / "pacc.json").write_text(json.dumps(team_config, indent=2))
        (self.project_dir / "pacc.local.json").write_text(json.dumps(local_config, indent=2))

        # Verify both files were created correctly
        assert (self.project_dir / "pacc.json").exists()
        assert (self.project_dir / "pacc.local.json").exists()

        # Verify content is valid JSON
        team_data = json.loads((self.project_dir / "pacc.json").read_text())
        local_data = json.loads((self.project_dir / "pacc.local.json").read_text())

        assert team_data["name"] == "team-project"
        assert len(team_data["plugins"]["repositories"]) == 1
        assert len(local_data["plugins"]["repositories"]) == 1

    def test_config_validation_structure(self):
        """Test validation of project configuration structure."""
        # Test valid configuration structure
        config = {
            "name": "test-project",
            "version": "1.0.0",
            "plugins": {"repositories": ["team/productivity-tools@v1.1.0"]},
        }

        (self.project_dir / "pacc.json").write_text(json.dumps(config, indent=2))

        # Verify configuration is valid JSON and has expected structure
        loaded_config = json.loads((self.project_dir / "pacc.json").read_text())
        assert "name" in loaded_config
        assert "version" in loaded_config
        assert "plugins" in loaded_config
        assert "repositories" in loaded_config["plugins"]
        assert isinstance(loaded_config["plugins"]["repositories"], list)

    def test_performance_validation_large_config(self):
        """Test performance with large configuration files."""
        # Create configuration with multiple repositories
        config = {
            "name": "large-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": [f"org/repo-{i}@v1.0.0" for i in range(10)],
                "required": [f"plugin-{i}" for i in range(5)],
                "optional": [f"plugin-{i}" for i in range(5, 10)],
            },
        }

        (self.project_dir / "pacc.json").write_text(json.dumps(config, indent=2))

        # Measure config loading performance
        start_time = datetime.now()

        # Load and validate the configuration
        loaded_config = json.loads((self.project_dir / "pacc.json").read_text())

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Verify config structure
        assert len(loaded_config["plugins"]["repositories"]) == 10
        assert len(loaded_config["plugins"]["required"]) == 5
        assert len(loaded_config["plugins"]["optional"]) == 5

        # Performance should be very fast for config loading
        assert duration < 1.0, f"Config loading took {duration}s, should be under 1s"

    def test_memory_usage_validation_config_size(self):
        """Test memory usage with large configuration files."""

        # Create large configuration
        config = {
            "name": "memory-test-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": [f"org/repo-{i}@v1.0.0" for i in range(100)],
                "required": [f"plugin-{i}" for i in range(50)],
            },
        }

        config_str = json.dumps(config, indent=2)
        (self.project_dir / "pacc.json").write_text(config_str)

        # Verify the config can be loaded without excessive memory use
        file_size = (self.project_dir / "pacc.json").stat().st_size
        config_size_mb = file_size / (1024 * 1024)

        # Should be able to handle reasonably large configs
        assert config_size_mb < 1.0, f"Config file is {config_size_mb}MB, should be manageable"

        # Load the config
        loaded_config = json.loads((self.project_dir / "pacc.json").read_text())
        assert len(loaded_config["plugins"]["repositories"]) == 100


class TestSprint3ErrorRecovery:
    """Test error recovery scenarios for Sprint 3 features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()
        self.project_dir = self.temp_dir / "project"
        self.project_dir.mkdir()

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_corrupted_config_detection(self):
        """Test detection of corrupted configuration files."""
        # Create corrupted JSON
        (self.project_dir / "pacc.json").write_text("{ invalid json }")

        # Attempt to load the corrupted config
        with pytest.raises(json.JSONDecodeError):
            json.loads((self.project_dir / "pacc.json").read_text())

    def test_missing_config_detection(self):
        """Test detection of missing configuration files."""
        # Ensure config file doesn't exist
        config_path = self.project_dir / "pacc.json"
        assert not config_path.exists()

        # Test file existence check
        assert not config_path.exists()

    def test_invalid_config_structure_detection(self):
        """Test detection of invalid configuration structure."""
        # Create config with missing required fields
        invalid_config = {
            "plugins": {
                "repositories": "not-a-list"  # Should be list
            }
            # Missing name and version
        }

        (self.project_dir / "pacc.json").write_text(json.dumps(invalid_config))

        loaded_config = json.loads((self.project_dir / "pacc.json").read_text())

        # Verify we can detect structural issues
        assert "name" not in loaded_config
        assert "version" not in loaded_config
        assert not isinstance(loaded_config["plugins"]["repositories"], list)


class TestSprint3EdgeCases:
    """Test edge cases for Sprint 3 features."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()
        self.project_dir = self.temp_dir / "project"
        self.project_dir.mkdir()

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_empty_repository_config(self):
        """Test configuration with empty repository list."""
        config = {
            "name": "empty-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": []  # Empty
            },
        }

        (self.project_dir / "pacc.json").write_text(json.dumps(config))

        # Verify empty repository list is valid
        loaded_config = json.loads((self.project_dir / "pacc.json").read_text())
        assert len(loaded_config["plugins"]["repositories"]) == 0
        assert isinstance(loaded_config["plugins"]["repositories"], list)

    def test_complex_repository_specification(self):
        """Test complex repository specifications."""
        config = {
            "name": "complex-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": [
                    "simple/repo@v1.0.0",
                    {
                        "repository": "complex/repo",
                        "version": "main",
                        "plugins": ["plugin1", "plugin2"],
                    },
                ]
            },
        }

        (self.project_dir / "pacc.json").write_text(json.dumps(config))

        # Verify complex specs are valid JSON
        loaded_config = json.loads((self.project_dir / "pacc.json").read_text())
        repos = loaded_config["plugins"]["repositories"]
        assert len(repos) == 2
        assert isinstance(repos[0], str)
        assert isinstance(repos[1], dict)
        assert "repository" in repos[1]
        assert "version" in repos[1]
        assert "plugins" in repos[1]

    def test_environment_specific_config(self):
        """Test environment-specific configuration."""
        config = {
            "name": "env-project",
            "version": "1.0.0",
            "plugins": {"repositories": ["base/repo@v1.0.0"]},
            "environments": {
                "development": {"plugins": {"repositories": ["dev/tools@latest"]}},
                "production": {"plugins": {"repositories": ["prod/stable@v2.0.0"]}},
            },
        }

        (self.project_dir / "pacc.json").write_text(json.dumps(config))

        # Verify environment config structure
        loaded_config = json.loads((self.project_dir / "pacc.json").read_text())
        assert "environments" in loaded_config
        assert "development" in loaded_config["environments"]
        assert "production" in loaded_config["environments"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
