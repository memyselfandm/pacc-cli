"""Tests for plugin sync CLI command."""

import json
import shutil
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pacc.cli import PACCCli
from pacc.core.project_config import PluginSyncResult


class TestPluginSyncCLI:
    """Test plugin sync CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = PACCCli()
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_plugin_sync_command_parsing(self):
        """Test that plugin sync command is properly parsed."""
        parser = self.cli.create_parser()

        # Test basic sync command
        args = parser.parse_args(["plugin", "sync"])
        assert args.command == "plugin"
        assert args.plugin_command == "sync"
        assert args.project_dir == Path.cwd()
        assert args.environment == "default"
        assert not args.dry_run
        assert not args.force

        # Test with options
        args = parser.parse_args(
            [
                "plugin",
                "sync",
                "--project-dir",
                str(self.temp_dir),
                "--environment",
                "production",
                "--dry-run",
                "--force",
                "--required-only",
            ]
        )
        assert args.project_dir == self.temp_dir
        assert args.environment == "production"
        assert args.dry_run
        assert args.force
        assert args.required_only

    @patch("pacc.core.project_config.PluginSyncManager")
    def test_handle_plugin_sync_success(self, mock_sync_manager_class):
        """Test successful plugin sync handling."""
        # Mock the sync manager
        mock_sync_manager = Mock()
        mock_sync_result = PluginSyncResult(
            success=True, installed_count=2, updated_count=1, skipped_count=1
        )
        mock_sync_manager.sync_plugins.return_value = mock_sync_result
        mock_sync_manager_class.return_value = mock_sync_manager

        # Create test config
        (self.temp_dir / "pacc.json").write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "version": "1.0.0",
                    "plugins": {"repositories": ["owner/repo@v1.0.0"]},
                }
            )
        )

        # Create args
        args = Namespace(
            project_dir=self.temp_dir,
            environment="default",
            dry_run=False,
            force=False,
            required_only=False,
            optional_only=False,
            json=False,
            verbose=False,
        )

        # Mock print methods
        with patch.object(self.cli, "_print_success") as mock_success, patch.object(
            self.cli, "_print_info"
        ) as mock_info, patch.object(self.cli, "_set_json_mode"):
            result = self.cli.handle_plugin_sync(args)

            assert result == 0  # Success exit code
            mock_sync_manager.sync_plugins.assert_called_once_with(
                project_dir=self.temp_dir, environment="default", dry_run=False
            )
            mock_success.assert_called_once()
            # Should show counts for installed/updated/skipped
            assert mock_info.call_count >= 3

    @patch("pacc.core.project_config.PluginSyncManager")
    def test_handle_plugin_sync_failure(self, mock_sync_manager_class):
        """Test plugin sync failure handling."""
        # Mock the sync manager to return failure
        mock_sync_manager = Mock()
        mock_sync_result = PluginSyncResult(
            success=False,
            failed_plugins=["owner/repo"],
            warnings=["Failed to install owner/repo"],
            error_message="Sync failed",
        )
        mock_sync_manager.sync_plugins.return_value = mock_sync_result
        mock_sync_manager_class.return_value = mock_sync_manager

        # Create test config
        (self.temp_dir / "pacc.json").write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "version": "1.0.0",
                    "plugins": {"repositories": ["owner/repo@v1.0.0"]},
                }
            )
        )

        args = Namespace(
            project_dir=self.temp_dir,
            environment="default",
            dry_run=False,
            force=False,
            required_only=False,
            optional_only=False,
            json=False,
            verbose=False,
        )

        # Mock print methods
        with patch.object(self.cli, "_print_error") as mock_error, patch.object(
            self.cli, "_print_warning"
        ) as mock_warning, patch.object(self.cli, "_set_json_mode"):
            result = self.cli.handle_plugin_sync(args)

            assert result == 1  # Failure exit code
            mock_error.assert_called()
            mock_warning.assert_called()

    def test_handle_plugin_sync_no_config(self):
        """Test handling when no pacc.json exists."""
        args = Namespace(
            project_dir=self.temp_dir,
            environment="default",
            dry_run=False,
            force=False,
            required_only=False,
            optional_only=False,
            json=False,
            verbose=False,
        )

        with patch.object(self.cli, "_print_error") as mock_error, patch.object(
            self.cli, "_print_info"
        ) as mock_info, patch.object(self.cli, "_set_json_mode"):
            result = self.cli.handle_plugin_sync(args)

            assert result == 1  # Failure exit code
            mock_error.assert_called_once()
            mock_info.assert_called_once()

            # Check error message mentions pacc.json
            error_call = mock_error.call_args[0][0]
            assert "pacc.json" in error_call

    @patch("pacc.core.project_config.PluginSyncManager")
    def test_handle_plugin_sync_dry_run(self, mock_sync_manager_class):
        """Test dry-run mode messaging."""
        mock_sync_manager = Mock()
        mock_sync_result = PluginSyncResult(
            success=True, installed_count=0, updated_count=0, skipped_count=2
        )
        mock_sync_manager.sync_plugins.return_value = mock_sync_result
        mock_sync_manager_class.return_value = mock_sync_manager

        (self.temp_dir / "pacc.json").write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "version": "1.0.0",
                    "plugins": {"repositories": ["owner/repo@v1.0.0"]},
                }
            )
        )

        args = Namespace(
            project_dir=self.temp_dir,
            environment="default",
            dry_run=True,  # Dry run mode
            force=False,
            required_only=False,
            optional_only=False,
            json=False,
            verbose=False,
        )

        with patch.object(self.cli, "_print_info") as mock_info, patch.object(
            self.cli, "_print_success"
        ), patch.object(self.cli, "_set_json_mode"):
            result = self.cli.handle_plugin_sync(args)

            assert result == 0
            # Should pass dry_run=True to sync manager
            mock_sync_manager.sync_plugins.assert_called_with(
                project_dir=self.temp_dir, environment="default", dry_run=True
            )

            # Should show dry-run in output
            info_calls = [call[0][0] for call in mock_info.call_args_list]
            dry_run_mentioned = any(
                "dry-run" in call.lower() or "dry run" in call.lower() for call in info_calls
            )
            assert dry_run_mentioned

    @patch("pacc.core.project_config.PluginSyncManager")
    def test_handle_plugin_sync_json_output(self, mock_sync_manager_class):
        """Test JSON output mode."""
        mock_sync_manager = Mock()
        mock_sync_result = PluginSyncResult(
            success=True, installed_count=1, updated_count=1, skipped_count=0
        )
        mock_sync_manager.sync_plugins.return_value = mock_sync_result
        mock_sync_manager_class.return_value = mock_sync_manager

        (self.temp_dir / "pacc.json").write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "version": "1.0.0",
                    "plugins": {"repositories": ["owner/repo@v1.0.0"]},
                }
            )
        )

        args = Namespace(
            project_dir=self.temp_dir,
            environment="default",
            dry_run=False,
            force=False,
            required_only=False,
            optional_only=False,
            json=True,  # JSON output mode
            verbose=False,
        )

        with patch("builtins.print") as mock_print, patch.object(
            self.cli, "_set_json_mode"
        ), patch.object(self.cli, "_print_success"), patch.object(self.cli, "_print_info"):
            # Set JSON mode
            self.cli._json_output = True

            result = self.cli.handle_plugin_sync(args)

            assert result == 0

            # Should have printed JSON output
            mock_print.assert_called()
            json_output = mock_print.call_args[0][0]

            # Parse and validate JSON
            output_data = json.loads(json_output)
            assert output_data["success"] is True
            assert "data" in output_data
            assert output_data["data"]["installed_count"] == 1
            assert output_data["data"]["updated_count"] == 1
            assert output_data["data"]["environment"] == "default"

    def test_filtering_options_warning(self):
        """Test that filtering options show warnings (not yet implemented)."""
        (self.temp_dir / "pacc.json").write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "version": "1.0.0",
                    "plugins": {"repositories": ["owner/repo@v1.0.0"]},
                }
            )
        )

        args = Namespace(
            project_dir=self.temp_dir,
            environment="default",
            dry_run=False,
            force=False,
            required_only=True,  # Should trigger warning
            optional_only=False,
            json=False,
            verbose=False,
        )

        with patch(
            "pacc.core.project_config.PluginSyncManager"
        ) as mock_sync_manager_class, patch.object(
            self.cli, "_print_warning"
        ) as mock_warning, patch.object(self.cli, "_print_success"), patch.object(
            self.cli, "_print_info"
        ), patch.object(self.cli, "_set_json_mode"):
            # Mock successful sync
            mock_sync_manager = Mock()
            mock_sync_result = PluginSyncResult(success=True)
            mock_sync_manager.sync_plugins.return_value = mock_sync_result
            mock_sync_manager_class.return_value = mock_sync_manager

            result = self.cli.handle_plugin_sync(args)

            assert result == 0
            # Should warn about unimplemented filtering
            mock_warning.assert_called()
            warning_msg = mock_warning.call_args[0][0]
            assert "required-only" in warning_msg

    @patch("pacc.core.project_config.PluginSyncManager")
    def test_handle_plugin_sync_with_environment(self, mock_sync_manager_class):
        """Test sync with specific environment."""
        mock_sync_manager = Mock()
        mock_sync_result = PluginSyncResult(success=True)
        mock_sync_manager.sync_plugins.return_value = mock_sync_result
        mock_sync_manager_class.return_value = mock_sync_manager

        (self.temp_dir / "pacc.json").write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "version": "1.0.0",
                    "plugins": {"repositories": ["owner/repo@v1.0.0"]},
                    "environments": {
                        "production": {"plugins": {"repositories": ["prod/repo@v2.0.0"]}}
                    },
                }
            )
        )

        args = Namespace(
            project_dir=self.temp_dir,
            environment="production",  # Specific environment
            dry_run=False,
            force=False,
            required_only=False,
            optional_only=False,
            json=False,
            verbose=False,
        )

        with patch.object(self.cli, "_print_info") as mock_info, patch.object(
            self.cli, "_print_success"
        ), patch.object(self.cli, "_set_json_mode"):
            result = self.cli.handle_plugin_sync(args)

            assert result == 0
            # Should pass environment to sync manager
            mock_sync_manager.sync_plugins.assert_called_with(
                project_dir=self.temp_dir, environment="production", dry_run=False
            )

            # Should mention environment in output
            info_calls = [call[0][0] for call in mock_info.call_args_list]
            env_mentioned = any("production" in call for call in info_calls)
            assert env_mentioned

    @patch("pacc.core.project_config.PluginSyncManager")
    def test_handle_plugin_sync_with_warnings(self, mock_sync_manager_class):
        """Test handling of sync warnings."""
        mock_sync_manager = Mock()
        mock_sync_result = PluginSyncResult(
            success=True, warnings=["Plugin foo is deprecated", "Version conflict resolved"]
        )
        mock_sync_manager.sync_plugins.return_value = mock_sync_result
        mock_sync_manager_class.return_value = mock_sync_manager

        (self.temp_dir / "pacc.json").write_text(
            json.dumps(
                {
                    "name": "test-project",
                    "version": "1.0.0",
                    "plugins": {"repositories": ["owner/repo@v1.0.0"]},
                }
            )
        )

        args = Namespace(
            project_dir=self.temp_dir,
            environment="default",
            dry_run=False,
            force=False,
            required_only=False,
            optional_only=False,
            json=False,
            verbose=False,
        )

        with patch.object(self.cli, "_print_warning") as mock_warning, patch.object(
            self.cli, "_print_success"
        ), patch.object(self.cli, "_print_info"), patch.object(self.cli, "_set_json_mode"):
            result = self.cli.handle_plugin_sync(args)

            assert result == 0
            # Should print all warnings
            assert mock_warning.call_count == 2

            warning_calls = [call[0][0] for call in mock_warning.call_args_list]
            assert "Plugin foo is deprecated" in warning_calls
            assert "Version conflict resolved" in warning_calls


class TestPluginSyncCLIIntegration:
    """Integration tests for plugin sync CLI."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    @patch("pacc.core.project_config.PluginSyncManager._get_plugin_manager")
    def test_end_to_end_sync_flow(self, mock_get_manager):
        """Test complete end-to-end sync flow through CLI."""
        # Mock plugin manager
        mock_manager = Mock()
        mock_manager.list_installed_repositories.return_value = {}
        mock_manager.install_repository.return_value = True
        mock_manager.enable_plugin.return_value = True
        mock_get_manager.return_value = mock_manager

        # Create realistic pacc.json
        config = {
            "name": "my-project",
            "version": "1.0.0",
            "description": "Test project for plugin sync",
            "plugins": {
                "repositories": [
                    "team/productivity-hooks@v1.2.0",
                    {
                        "repository": "community/ai-agents",
                        "version": "main",
                        "plugins": ["code-reviewer", "documentation-helper"],
                    },
                ],
                "required": ["code-reviewer"],
                "optional": ["documentation-helper"],
            },
        }

        (self.temp_dir / "pacc.json").write_text(json.dumps(config, indent=2))

        # Run CLI command programmatically
        cli = PACCCli()
        parser = cli.create_parser()
        args = parser.parse_args(["plugin", "sync", "--project-dir", str(self.temp_dir)])

        # Capture output
        with patch("builtins.print") as mock_print:
            result = cli.handle_plugin_sync(args)

        assert result == 0

        # Verify plugin manager was called correctly
        assert mock_manager.install_repository.call_count >= 1

        # Check that success message was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        success_printed = any("success" in call.lower() for call in print_calls)
        assert success_printed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
