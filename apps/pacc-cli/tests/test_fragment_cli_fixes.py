"""Tests for fragment PACCCli command fixes (PACC-60 and PACC-61)."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from pacc.cli import PACCCli


class TestFragmentInstallPACCCliFix:
    """Test that fragment install PACCCli properly uses FragmentInstallationManager (PACC-60)."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir) / "test_project"
        self.project_root.mkdir(parents=True)

        # Create test fragment
        self.test_fragment = self.project_root / "test_fragment.md"
        self.test_fragment.write_text("""---
title: "Test Memory Fragment"
description: "Fragment for testing PACCCli"
tags: ["test", "cli"]
category: "testing"
---

# Test Fragment

This is test content for the fragment.
""")

        # Create CLAUDE.md
        self.claude_md = self.project_root / "CLAUDE.md"
        self.claude_md.write_text("# Project Instructions\n\nOriginal content here.\n")

        # Create pacc.json
        self.pacc_json = self.project_root / "pacc.json"
        self.pacc_json.write_text('{"fragments": {}}\n')

    def teardown_method(self):
        """Clean up test environment."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("pacc.cli.PACCCli._print_success")
    @patch("pacc.cli.PACCCli._print_info")
    @patch("pacc.cli.PACCCli._print_error")
    def test_fragment_install_uses_installation_manager(self, mock_error, mock_info, mock_success):
        """Test that handle_fragment_install uses FragmentInstallationManager."""
        cli = PACCCli()

        # Mock args for fragment install
        args = MagicMock()
        args.source = str(self.test_fragment)
        args.storage_type = "project"
        args.collection = None
        args.overwrite = False
        args.dry_run = False
        args.verbose = False

        with patch("pacc.fragments.installation_manager.Path.cwd", return_value=self.project_root):
            # Run the install command
            result = cli.handle_fragment_install(args)

            # Should succeed
            assert result == 0, "Installation should succeed"

            # Check success message was printed
            mock_success.assert_called()
            success_calls = [str(call) for call in mock_success.call_args_list]
            assert any(
                "Installed" in str(call) for call in success_calls
            ), "Should print installation success message"

            # Verify CLAUDE.md was updated (actual file check)
            claude_content = self.claude_md.read_text()
            assert (
                "PACC:fragments:START" in claude_content or "test_fragment" in claude_content
            ), "CLAUDE.md should be updated with fragment reference"

    @patch("pacc.cli.PACCCli._print_info")
    def test_fragment_install_dry_run_mode(self, mock_info):
        """Test that dry-run mode shows what would be installed."""
        cli = PACCCli()

        args = MagicMock()
        args.source = str(self.test_fragment)
        args.storage_type = "project"
        args.collection = None
        args.overwrite = False
        args.dry_run = True
        args.verbose = False

        with patch("pacc.fragments.installation_manager.Path.cwd", return_value=self.project_root):
            result = cli.handle_fragment_install(args)

            # Should succeed
            assert result == 0, "Dry-run should succeed"

            # Check dry-run messages
            info_calls = [str(call) for call in mock_info.call_args_list]
            assert any(
                "DRY RUN" in str(call) for call in info_calls
            ), "Should indicate dry-run mode"
            assert any(
                "Would install" in str(call) for call in info_calls
            ), "Should show what would be installed"

            # CLAUDE.md should NOT be modified in dry-run
            claude_content = self.claude_md.read_text()
            assert (
                "test_fragment" not in claude_content
            ), "CLAUDE.md should not be modified in dry-run mode"

    @patch("pacc.cli.PACCCli._print_info")
    @patch("pacc.cli.PACCCli._print_success")
    def test_fragment_install_verbose_mode(self, mock_success, mock_info):
        """Test that verbose mode provides detailed output."""
        cli = PACCCli()

        args = MagicMock()
        args.source = str(self.test_fragment)
        args.storage_type = "project"
        args.collection = None
        args.overwrite = False
        args.dry_run = False
        args.verbose = True

        with patch("pacc.fragments.installation_manager.Path.cwd", return_value=self.project_root):
            result = cli.handle_fragment_install(args)

            assert result == 0, "Installation should succeed"

            # In verbose mode, should show fragment details
            info_calls = [str(call) for call in mock_info.call_args_list]
            # Should show reference path or location in verbose mode
            assert any(
                "Reference" in str(call) or "Location" in str(call) for call in info_calls
            ), "Verbose mode should show fragment details"

    @patch("pacc.cli.PACCCli._print_error")
    def test_fragment_install_handles_installation_failure(self, mock_error):
        """Test that installation failures are properly reported."""
        cli = PACCCli()

        # Use non-existent source
        args = MagicMock()
        args.source = "/non/existent/path/fragment.md"
        args.storage_type = "project"
        args.collection = None
        args.overwrite = False
        args.dry_run = False
        args.verbose = False

        result = cli.handle_fragment_install(args)

        # Should fail
        assert result == 1, "Should return error code for failed installation"

        # Should print error message
        mock_error.assert_called()
        error_calls = [str(call) for call in mock_error.call_args_list]
        assert any(
            "error" in str(call).lower() or "failed" in str(call).lower() for call in error_calls
        ), "Should print error message for failed installation"


class TestFragmentRemovePACCCliSecurity:
    """Test that fragment remove PACCCli is secure against path traversal (PACC-61)."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir) / "test_project"
        self.project_root.mkdir(parents=True)

        # Create fragment storage
        self.fragment_storage = self.project_root / ".claude" / "pacc" / "fragments"
        self.fragment_storage.mkdir(parents=True)

        # Create legitimate fragment
        self.legit_fragment = self.fragment_storage / "legit.md"
        self.legit_fragment.write_text("# Legitimate Fragment")

        # Create file outside storage (attack target)
        self.important_file = self.project_root / "important.md"
        self.important_file.write_text("# Important File - Should not be deletable")

    def teardown_method(self):
        """Clean up test environment."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    @patch("pacc.cli.PACCCli._print_error")
    @patch("builtins.input", return_value="y")  # Auto-confirm for testing
    def test_fragment_remove_blocks_path_traversal(self, mock_input, mock_error):
        """Test that path traversal attempts are blocked."""
        cli = PACCCli()

        # Try to remove file outside fragment storage
        args = MagicMock()
        args.fragment = "../../important"  # Path traversal attempt
        args.storage_type = None
        args.collection = None
        args.dry_run = False
        args.confirm = True  # Skip confirmation prompt
        args.verbose = False

        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            result = cli.handle_fragment_remove(args)

            # Should fail to find/remove
            assert result == 1, "Should fail to remove file via path traversal"

            # Important file should still exist
            assert (
                self.important_file.exists()
            ), "Important file should not be deleted via path traversal"

            # Should print error about not finding fragment
            mock_error.assert_called()
            error_calls = [str(call) for call in mock_error.call_args_list]
            assert any(
                "not found" in str(call).lower() or "failed" in str(call).lower()
                for call in error_calls
            ), "Should indicate fragment not found"

    @patch("pacc.cli.PACCCli._print_error")
    def test_fragment_remove_blocks_absolute_paths(self, mock_error):
        """Test that absolute paths are blocked."""
        cli = PACCCli()

        args = MagicMock()
        args.fragment = str(self.important_file)  # Absolute path
        args.storage_type = None
        args.collection = None
        args.dry_run = False
        args.confirm = True
        args.verbose = False

        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            result = cli.handle_fragment_remove(args)

            # Should fail
            assert result == 1, "Should fail to remove via absolute path"

            # File should still exist
            assert self.important_file.exists(), "File should not be deleted via absolute path"

    @patch("pacc.cli.PACCCli._print_success")
    @patch("builtins.input", return_value="y")
    def test_fragment_remove_allows_legitimate_removal(self, mock_input, mock_success):
        """Test that legitimate fragments can still be removed."""
        cli = PACCCli()

        args = MagicMock()
        args.fragment = "legit"  # Legitimate fragment name
        args.storage_type = None
        args.collection = None
        args.dry_run = False
        args.confirm = False  # Will use mock input
        args.verbose = False

        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            result = cli.handle_fragment_remove(args)

            # Should succeed
            assert result == 0, "Should successfully remove legitimate fragment"

            # Fragment should be deleted
            assert not self.legit_fragment.exists(), "Legitimate fragment should be deleted"

            # Should print success message
            mock_success.assert_called()

    @patch("pacc.cli.PACCCli._print_info")
    def test_fragment_remove_dry_run_safety(self, mock_info):
        """Test that dry-run mode doesn't delete anything."""
        cli = PACCCli()

        args = MagicMock()
        args.fragment = "legit"
        args.storage_type = None
        args.collection = None
        args.dry_run = True  # Dry-run mode
        args.confirm = True
        args.verbose = False

        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            result = cli.handle_fragment_remove(args)

            # Should succeed (dry-run)
            assert result == 0, "Dry-run should succeed"

            # Fragment should still exist
            assert self.legit_fragment.exists(), "Fragment should not be deleted in dry-run mode"

            # Should indicate what would be removed
            info_calls = [str(call) for call in mock_info.call_args_list]
            assert any(
                "Would remove" in str(call) for call in info_calls
            ), "Should indicate what would be removed"

    @patch("pacc.cli.PACCCli._print_error")
    def test_fragment_remove_with_slash_in_name(self, mock_error):
        """Test that fragment names with slashes are rejected."""
        cli = PACCCli()

        slash_attempts = [
            "subdir/fragment",
            "../fragment",
            "collection/../../../etc/passwd",
            "\\windows\\path",
        ]

        for attempt in slash_attempts:
            args = MagicMock()
            args.fragment = attempt
            args.storage_type = None
            args.collection = None
            args.dry_run = False
            args.confirm = True
            args.verbose = False

            with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
                result = cli.handle_fragment_remove(args)

                # Should fail
                assert result == 1, f"Should fail for fragment name with slashes: {attempt}"
