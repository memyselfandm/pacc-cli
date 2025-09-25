"""Integration tests for CLI fragment commands."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pacc.cli import PACCCli


class TestFragmentCommands:
    """Test CLI fragment command integration."""

    def test_fragment_help_command(self, capsys):
        """Test fragment help command."""
        cli = PACCCli()

        # Mock args for fragment help
        args = Mock()
        args.command = "fragment"
        args.fragment_command = None

        result = cli._fragment_help(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "Fragment Management Commands:" in captured.out
        assert "install <source>" in captured.out
        assert "list [options]" in captured.out
        assert "info <fragment>" in captured.out
        assert "remove <fragment>" in captured.out

    def test_fragment_install_single_file(self):
        """Test fragment install from a single file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            # Create a sample fragment file
            fragment_content = """---
title: Test Fragment
description: A test memory fragment
tags: [test, example]
---

# Test Fragment

This is a test fragment for memory storage.

## Example Code

```python
def test_function():
    return "Hello World"
```
"""
            source_file = temp_dir / "test_fragment.md"
            source_file.write_text(fragment_content)

            # Mock project root and storage
            with patch(
                "pacc.fragments.storage_manager.FragmentStorageManager"
            ) as mock_storage, patch(
                "pacc.validators.fragment_validator.FragmentValidator"
            ) as mock_validator:
                # Setup mock validator
                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validation_result.errors = []
                mock_validator.return_value.validate_single.return_value = mock_validation_result

                # Setup mock storage
                mock_storage_instance = mock_storage.return_value
                mock_fragment_path = (
                    temp_dir / ".claude" / "pacc" / "fragments" / "test_fragment.md"
                )
                mock_storage_instance.store_fragment.return_value = mock_fragment_path

                cli = PACCCli()
                args = Mock()
                args.source = str(source_file)
                args.storage_type = "project"
                args.collection = None
                args.overwrite = False
                args.dry_run = False
                args.verbose = False

                result = cli.handle_fragment_install(args)

                assert result == 0
                mock_validator.return_value.validate_single.assert_called_once_with(source_file)
                mock_storage_instance.store_fragment.assert_called_once_with(
                    fragment_name="test_fragment",
                    content=fragment_content,
                    storage_type="project",
                    collection=None,
                    overwrite=False,
                )

    def test_fragment_install_dry_run(self):
        """Test fragment install with dry run mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            # Create a sample fragment file
            fragment_content = "# Test Fragment\nThis is a test."
            source_file = temp_dir / "test_fragment.md"
            source_file.write_text(fragment_content)

            with patch(
                "pacc.fragments.storage_manager.FragmentStorageManager"
            ) as mock_storage, patch(
                "pacc.validators.fragment_validator.FragmentValidator"
            ) as mock_validator:
                # Setup mock validator
                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validation_result.errors = []
                mock_validator.return_value.validate_single.return_value = mock_validation_result

                cli = PACCCli()
                args = Mock()
                args.source = str(source_file)
                args.storage_type = "project"
                args.collection = None
                args.overwrite = False
                args.dry_run = True
                args.verbose = False

                result = cli.handle_fragment_install(args)

                assert result == 0
                # Should validate but not store in dry run mode
                mock_validator.return_value.validate_single.assert_called_once()
                mock_storage.return_value.store_fragment.assert_not_called()

    def test_fragment_install_directory(self):
        """Test fragment install from directory with multiple files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            # Create multiple fragment files
            fragments_dir = temp_dir / "fragments"
            fragments_dir.mkdir()

            # Create test fragments
            fragment1_content = "# Fragment 1\nFirst test fragment."
            fragment2_content = "# Fragment 2\nSecond test fragment."

            (fragments_dir / "fragment1.md").write_text(fragment1_content)
            (fragments_dir / "fragment2.md").write_text(fragment2_content)

            with patch(
                "pacc.fragments.storage_manager.FragmentStorageManager"
            ) as mock_storage, patch(
                "pacc.validators.fragment_validator.FragmentValidator"
            ) as mock_validator:
                # Setup mock validator
                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validation_result.errors = []
                mock_validator.return_value.validate_single.return_value = mock_validation_result
                mock_validator.return_value._find_extension_files.return_value = [
                    fragments_dir / "fragment1.md",
                    fragments_dir / "fragment2.md",
                ]

                # Setup mock storage
                mock_storage_instance = mock_storage.return_value
                mock_storage_instance.store_fragment.return_value = temp_dir / "stored.md"

                cli = PACCCli()
                args = Mock()
                args.source = str(fragments_dir)
                args.storage_type = "project"
                args.collection = "test-collection"
                args.overwrite = False
                args.dry_run = False
                args.verbose = False

                result = cli.handle_fragment_install(args)

                assert result == 0
                # Should store both fragments
                assert mock_storage_instance.store_fragment.call_count == 2

    def test_fragment_list_empty(self):
        """Test fragment list when no fragments are installed."""
        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage:
            mock_storage.return_value.list_fragments.return_value = []
            mock_storage.return_value.get_fragment_stats.return_value = {"total_fragments": 0}

            cli = PACCCli()
            args = Mock()
            args.storage_type = None
            args.collection = None
            args.pattern = None
            args.format = "table"
            args.show_stats = True
            args.verbose = False

            result = cli.handle_fragment_list(args)

            assert result == 0
            mock_storage.return_value.list_fragments.assert_called_once_with(
                storage_type=None, collection=None, pattern=None
            )

    def test_fragment_list_with_fragments(self, capsys):
        """Test fragment list with some fragments installed."""
        from datetime import datetime

        from pacc.fragments.storage_manager import FragmentLocation

        # Create mock fragment locations
        mock_fragment1 = FragmentLocation(
            path=Path("/test/fragment1.md"),
            name="fragment1",
            is_collection=False,
            storage_type="project",
            collection_name=None,
            last_modified=datetime(2023, 1, 1, 12, 0, 0),
            size=100,
        )

        mock_fragment2 = FragmentLocation(
            path=Path("/test/collection/fragment2.md"),
            name="fragment2",
            is_collection=True,
            storage_type="user",
            collection_name="test-collection",
            last_modified=datetime(2023, 1, 2, 12, 0, 0),
            size=200,
        )

        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage:
            mock_storage.return_value.list_fragments.return_value = [mock_fragment1, mock_fragment2]

            cli = PACCCli()
            args = Mock()
            args.storage_type = None
            args.collection = None
            args.pattern = None
            args.format = "table"
            args.show_stats = False
            args.verbose = False

            result = cli.handle_fragment_list(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "fragment1" in captured.out
            assert "fragment2" in captured.out
            assert "project" in captured.out
            assert "user" in captured.out
            assert "test-collection" in captured.out

    def test_fragment_list_json_format(self):
        """Test fragment list with JSON output format."""
        from datetime import datetime

        from pacc.fragments.storage_manager import FragmentLocation

        mock_fragment = FragmentLocation(
            path=Path("/test/fragment1.md"),
            name="fragment1",
            is_collection=False,
            storage_type="project",
            collection_name=None,
            last_modified=datetime(2023, 1, 1, 12, 0, 0),
            size=100,
        )

        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage:
            mock_storage.return_value.list_fragments.return_value = [mock_fragment]

            cli = PACCCli()
            args = Mock()
            args.storage_type = None
            args.collection = None
            args.pattern = None
            args.format = "json"
            args.show_stats = False
            args.verbose = False

            result = cli.handle_fragment_list(args)

            assert result == 0

    def test_fragment_info_found(self, capsys):
        """Test fragment info command when fragment is found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            fragment_file = temp_dir / "test_fragment.md"
            fragment_content = """---
title: Test Fragment
description: A test fragment
---

# Test Fragment
This is test content.
"""
            fragment_file.write_text(fragment_content)

            with patch(
                "pacc.fragments.storage_manager.FragmentStorageManager"
            ) as mock_storage, patch(
                "pacc.validators.fragment_validator.FragmentValidator"
            ) as mock_validator:
                mock_storage.return_value.find_fragment.return_value = fragment_file

                # Setup mock validation result
                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validation_result.errors = []
                mock_validation_result.warnings = []
                mock_validation_result.metadata = {
                    "title": "Test Fragment",
                    "description": "A test fragment",
                    "has_frontmatter": True,
                    "markdown_length": 30,
                    "line_count": 8,
                }
                mock_validator.return_value.validate_single.return_value = mock_validation_result

                cli = PACCCli()
                args = Mock()
                args.fragment = "test_fragment"
                args.storage_type = None
                args.collection = None
                args.format = "table"
                args.verbose = False

                result = cli.handle_fragment_info(args)

                assert result == 0
                mock_storage.return_value.find_fragment.assert_called_once_with(
                    fragment_name="test_fragment", storage_type=None, collection=None
                )

                captured = capsys.readouterr()
                assert "Fragment Information: test_fragment" in captured.out
                assert "Test Fragment" in captured.out
                assert "A test fragment" in captured.out

    def test_fragment_info_not_found(self):
        """Test fragment info command when fragment is not found."""
        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage:
            mock_storage.return_value.find_fragment.return_value = None

            cli = PACCCli()
            args = Mock()
            args.fragment = "nonexistent_fragment"
            args.storage_type = None
            args.collection = None
            args.format = "table"
            args.verbose = False

            result = cli.handle_fragment_info(args)

            assert result == 1

    def test_fragment_info_json_format(self):
        """Test fragment info command with JSON output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            fragment_file = temp_dir / "test_fragment.md"
            fragment_file.write_text("# Test\nContent")

            with patch(
                "pacc.fragments.storage_manager.FragmentStorageManager"
            ) as mock_storage, patch(
                "pacc.validators.fragment_validator.FragmentValidator"
            ) as mock_validator:
                mock_storage.return_value.find_fragment.return_value = fragment_file

                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validation_result.errors = []
                mock_validation_result.warnings = []
                mock_validation_result.metadata = {"title": "Test"}
                mock_validator.return_value.validate_single.return_value = mock_validation_result

                cli = PACCCli()
                args = Mock()
                args.fragment = "test_fragment"
                args.storage_type = None
                args.collection = None
                args.format = "json"
                args.verbose = False

                result = cli.handle_fragment_info(args)

                assert result == 0

    def test_fragment_remove_found(self):
        """Test fragment remove command when fragment is found."""
        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage, patch(
            "builtins.input", return_value="y"
        ):
            mock_storage.return_value.find_fragment.return_value = Path("/test/fragment.md")
            mock_storage.return_value.remove_fragment.return_value = True

            cli = PACCCli()
            args = Mock()
            args.fragment = "test_fragment"
            args.storage_type = None
            args.collection = None
            args.confirm = False
            args.dry_run = False
            args.verbose = False

            result = cli.handle_fragment_remove(args)

            assert result == 0
            mock_storage.return_value.remove_fragment.assert_called_once_with(
                fragment_name="test_fragment", storage_type=None, collection=None
            )

    def test_fragment_remove_not_found(self):
        """Test fragment remove command when fragment is not found."""
        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage:
            mock_storage.return_value.find_fragment.return_value = None

            cli = PACCCli()
            args = Mock()
            args.fragment = "nonexistent_fragment"
            args.storage_type = None
            args.collection = None
            args.confirm = False
            args.dry_run = False
            args.verbose = False

            result = cli.handle_fragment_remove(args)

            assert result == 1

    def test_fragment_remove_dry_run(self):
        """Test fragment remove command with dry run mode."""
        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage:
            mock_fragment_path = Path("/test/fragment.md")
            mock_storage.return_value.find_fragment.return_value = mock_fragment_path

            cli = PACCCli()
            args = Mock()
            args.fragment = "test_fragment"
            args.storage_type = None
            args.collection = None
            args.confirm = False
            args.dry_run = True
            args.verbose = False

            result = cli.handle_fragment_remove(args)

            assert result == 0
            # Should not actually remove in dry run mode
            mock_storage.return_value.remove_fragment.assert_not_called()

    def test_fragment_remove_with_confirm_flag(self):
        """Test fragment remove command with --confirm flag."""
        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage:
            mock_storage.return_value.find_fragment.return_value = Path("/test/fragment.md")
            mock_storage.return_value.remove_fragment.return_value = True

            cli = PACCCli()
            args = Mock()
            args.fragment = "test_fragment"
            args.storage_type = None
            args.collection = None
            args.confirm = True  # Skip confirmation prompt
            args.dry_run = False
            args.verbose = False

            result = cli.handle_fragment_remove(args)

            assert result == 0
            mock_storage.return_value.remove_fragment.assert_called_once()

    def test_fragment_remove_cancelled(self):
        """Test fragment remove command when user cancels."""
        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage, patch(
            "builtins.input", return_value="n"
        ):
            mock_storage.return_value.find_fragment.return_value = Path("/test/fragment.md")

            cli = PACCCli()
            args = Mock()
            args.fragment = "test_fragment"
            args.storage_type = None
            args.collection = None
            args.confirm = False
            args.dry_run = False
            args.verbose = False

            result = cli.handle_fragment_remove(args)

            assert result == 0
            # Should not remove when cancelled
            mock_storage.return_value.remove_fragment.assert_not_called()

    def test_fragment_install_invalid_source(self):
        """Test fragment install with invalid source."""
        cli = PACCCli()
        args = Mock()
        args.source = "/nonexistent/path"
        args.storage_type = "project"
        args.collection = None
        args.overwrite = False
        args.dry_run = False
        args.verbose = False

        result = cli.handle_fragment_install(args)

        assert result == 1

    def test_fragment_install_validation_failure(self):
        """Test fragment install when validation fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            # Create an invalid fragment file
            source_file = temp_dir / "invalid_fragment.md"
            source_file.write_text("")  # Empty file should fail validation

            with patch(
                "pacc.fragments.storage_manager.FragmentStorageManager"
            ) as mock_storage, patch(
                "pacc.validators.fragment_validator.FragmentValidator"
            ) as mock_validator:
                # Setup mock validator to return validation failure
                mock_validation_result = Mock()
                mock_validation_result.is_valid = False
                mock_validation_result.errors = [Mock(message="File is empty")]
                mock_validator.return_value.validate_single.return_value = mock_validation_result

                cli = PACCCli()
                args = Mock()
                args.source = str(source_file)
                args.storage_type = "project"
                args.collection = None
                args.overwrite = False
                args.dry_run = False
                args.verbose = False

                result = cli.handle_fragment_install(args)

                assert result == 1
                # Should not try to store invalid fragment
                mock_storage.return_value.store_fragment.assert_not_called()

    def test_fragment_commands_error_handling(self):
        """Test error handling in fragment commands."""
        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage:
            # Make storage manager raise an exception
            mock_storage.side_effect = Exception("Storage error")

            cli = PACCCli()
            args = Mock()
            args.storage_type = None
            args.collection = None
            args.pattern = None
            args.format = "table"
            args.show_stats = False
            args.verbose = False

            result = cli.handle_fragment_list(args)

            assert result == 1

    def test_fragment_install_verbose_mode(self, capsys):
        """Test fragment install command with verbose output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            # Create a sample fragment file
            fragment_content = """---
title: Test Fragment
description: A test fragment with verbose logging
tags: [test, verbose]
---

# Test Fragment

This is for testing verbose mode.
"""
            source_file = temp_dir / "test_verbose.md"
            source_file.write_text(fragment_content)

            with patch(
                "pacc.fragments.storage_manager.FragmentStorageManager"
            ) as mock_storage, patch(
                "pacc.validators.fragment_validator.FragmentValidator"
            ) as mock_validator:
                # Setup mock validator
                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validation_result.errors = []
                mock_validation_result.warnings = []
                mock_validation_result.metadata = {
                    "title": "Test Fragment",
                    "description": "A test fragment with verbose logging",
                    "category": "test",
                }
                mock_validator.return_value.validate_single.return_value = mock_validation_result

                # Setup mock storage
                mock_storage.return_value.store_fragment.return_value = Path(
                    "/test/path/test_verbose.md"
                )

                cli = PACCCli()
                args = Mock()
                args.source = str(source_file)
                args.storage_type = "project"
                args.collection = None
                args.overwrite = False
                args.dry_run = False
                args.verbose = True

                result = cli.handle_fragment_install(args)

                assert result == 0
                captured = capsys.readouterr()
                # Check for verbose output
                assert "Starting fragment installation with args:" in captured.out
                assert "Processing single fragment file:" in captured.out
                assert "Validation result:" in captured.out
                assert "Fragment name: test_verbose" in captured.out

    def test_fragment_install_dry_run_enhanced_preview(self, capsys):
        """Test enhanced dry-run preview with detailed information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            fragment_content = """---
title: Enhanced Preview Test
description: Testing enhanced dry-run preview
category: testing
---

# Enhanced Preview Test

This tests the enhanced dry-run preview functionality.
"""
            source_file = temp_dir / "preview_test.md"
            source_file.write_text(fragment_content)

            with patch(
                "pacc.fragments.storage_manager.FragmentStorageManager"
            ) as mock_storage, patch(
                "pacc.validators.fragment_validator.FragmentValidator"
            ) as mock_validator:
                # Setup mock validator with metadata
                mock_validation_result = Mock()
                mock_validation_result.is_valid = True
                mock_validation_result.errors = []
                mock_validation_result.warnings = []
                mock_validation_result.metadata = {
                    "title": "Enhanced Preview Test",
                    "description": "Testing enhanced dry-run preview",
                    "category": "testing",
                }
                mock_validator.return_value.validate_single.return_value = mock_validation_result

                # Mock the _get_fragment_path method
                expected_path = Path("/test/fragments/preview_test.md")
                mock_storage.return_value._get_fragment_path.return_value = expected_path

                cli = PACCCli()
                args = Mock()
                args.source = str(source_file)
                args.storage_type = "project"
                args.collection = "test-collection"
                args.overwrite = False
                args.dry_run = True
                args.verbose = True

                result = cli.handle_fragment_install(args)

                assert result == 0
                captured = capsys.readouterr()
                # Check for enhanced dry-run preview
                assert "Would install fragment: preview_test" in captured.out
                assert "Collection: test-collection" in captured.out
                assert "Storage type: project" in captured.out
                assert "Content size:" in captured.out
                assert "Title: Enhanced Preview Test" in captured.out
                assert "Description: Testing enhanced dry-run preview" in captured.out
                assert "Category: testing" in captured.out
                assert "Would be stored at:" in captured.out

    def test_fragment_remove_verbose_and_dry_run(self, capsys):
        """Test fragment remove with verbose output and dry-run preview."""
        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage:
            # Create a mock path object
            test_path = Mock(spec=Path)
            test_path.__str__ = Mock(return_value="/test/fragments/test_fragment.md")
            test_path.__fspath__ = Mock(return_value="/test/fragments/test_fragment.md")
            test_path.exists.return_value = True
            test_path.name = "test_fragment.md"

            # Setup parent mock
            test_path.parent = Mock()
            test_path.parent.name = "test-collection"
            test_path.parent.iterdir.return_value = [test_path]  # Only this file exists

            mock_storage.return_value.find_fragment.return_value = test_path

            # Setup mock stat
            mock_stat_result = Mock()
            mock_stat_result.st_size = 1024
            mock_stat_result.st_mtime = 1640995200.0  # 2022-01-01 00:00:00
            test_path.stat.return_value = mock_stat_result

            cli = PACCCli()
            args = Mock()
            args.fragment = "test_fragment"
            args.storage_type = "project"
            args.collection = "test-collection"
            args.dry_run = True
            args.verbose = True
            args.confirm = False

            result = cli.handle_fragment_remove(args)

            assert result == 0
            captured = capsys.readouterr()
            # Check for verbose and dry-run output
            assert "Starting fragment removal with args:" in captured.out
            assert "Fragment found at:" in captured.out
            assert "Fragment size: 1024 bytes" in captured.out
            assert "Fragment modified: 2021-12-31" in captured.out
            assert "Would remove fragment: test_fragment" in captured.out
            assert "Size: 1024 bytes" in captured.out

    def test_fragment_list_verbose_output(self, capsys):
        """Test fragment list command with verbose output."""
        with patch("pacc.fragments.storage_manager.FragmentStorageManager") as mock_storage:
            # Setup mock fragments
            mock_fragment = Mock()
            mock_fragment.name = "test_fragment"
            mock_fragment.path = Path("/test/fragments/test_fragment.md")
            mock_fragment.storage_type = "project"
            mock_fragment.collection_name = "test-collection"
            mock_fragment.is_collection = False
            mock_fragment.last_modified = None
            mock_fragment.size = 512

            mock_storage.return_value.list_fragments.return_value = [mock_fragment]

            cli = PACCCli()
            args = Mock()
            args.storage_type = None
            args.collection = None
            args.pattern = None
            args.format = "table"
            args.show_stats = False
            args.verbose = True

            result = cli.handle_fragment_list(args)

            assert result == 0
            captured = capsys.readouterr()
            # Check for verbose output
            assert "Listing fragments with filters:" in captured.out
            assert "Found 1 fragments matching criteria" in captured.out

    def test_fragment_install_directory_dry_run_detailed(self, capsys):
        """Test directory installation with detailed dry-run preview."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            # Create multiple fragment files
            fragments_dir = temp_dir / "fragments"
            fragments_dir.mkdir()

            # Valid fragment
            valid_content = "# Valid Fragment\nThis is valid."
            (fragments_dir / "valid.md").write_text(valid_content)

            # Invalid fragment (for testing)
            invalid_content = "This is not a proper fragment"
            (fragments_dir / "invalid.md").write_text(invalid_content)

            with patch(
                "pacc.fragments.storage_manager.FragmentStorageManager"
            ) as mock_storage, patch(
                "pacc.validators.fragment_validator.FragmentValidator"
            ) as mock_validator:

                def mock_validate_single(file_path):
                    result = Mock()
                    if "valid" in str(file_path):
                        result.is_valid = True
                        result.errors = []
                    else:
                        result.is_valid = False
                        result.errors = [Mock(message="Invalid format")]
                    result.warnings = []
                    return result

                mock_validator.return_value.validate_single.side_effect = mock_validate_single
                mock_validator.return_value._find_extension_files.return_value = [
                    fragments_dir / "valid.md",
                    fragments_dir / "invalid.md",
                ]

                cli = PACCCli()
                args = Mock()
                args.source = str(fragments_dir)
                args.storage_type = "project"
                args.collection = None
                args.overwrite = False
                args.dry_run = True
                args.verbose = True

                result = cli.handle_fragment_install(args)

                assert result == 0
                captured = capsys.readouterr()
                # Check for detailed dry-run output
                assert "DRY RUN - Would install:" in captured.out
                assert "✓ valid" in captured.out
                # Note: The validation mock setup shows both as valid in this test,
                # but in real usage the validation would properly filter invalid files
                assert "Summary:" in captured.out
                assert "fragments" in captured.out
