"""Integration tests for fragment collection CLI commands."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pacc.cli import PACCCli


class TestFragmentCollectionCommands:
    """Test fragment collection CLI commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()

        # Change to temp directory for testing
        self.original_cwd = Path.cwd()
        import os

        os.chdir(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import os

        os.chdir(self.original_cwd)

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def create_test_collection(self, name: str = "test-collection") -> Path:
        """Create a test collection directory."""
        collection_dir = self.temp_dir / name
        collection_dir.mkdir(exist_ok=True)

        # Create pacc.json
        pacc_data = {
            "collection": {
                "name": name,
                "version": "1.0.0",
                "description": f"Test collection {name}",
                "author": "Test Author",
                "tags": ["test", "collection"],
                "files": ["fragment1", "fragment2"],
                "optional_files": ["optional-fragment"],
            }
        }
        (collection_dir / "pacc.json").write_text(json.dumps(pacc_data))

        # Create README.md
        readme_content = f"""# {name}

This is a test collection for testing purposes.

## Fragments

- fragment1: Basic fragment
- fragment2: Another fragment
- optional-fragment: Optional fragment
"""
        (collection_dir / "README.md").write_text(readme_content)

        # Create fragments
        (collection_dir / "fragment1.md").write_text("""---
title: Fragment 1
description: First test fragment
tags: [test, fragment1]
---

# Fragment 1

This is the first test fragment.
""")

        (collection_dir / "fragment2.md").write_text("""---
title: Fragment 2
description: Second test fragment
tags: [test, fragment2]
---

# Fragment 2

This is the second test fragment.
""")

        (collection_dir / "optional-fragment.md").write_text("""---
title: Optional Fragment
description: Optional test fragment
tags: [test, optional]
---

# Optional Fragment

This is an optional fragment.
""")

        return collection_dir

    def test_fragment_discover_basic(self):
        """Test basic fragment discover command."""
        # Create test collections
        self.create_test_collection("collection1")
        self.create_test_collection("collection2")

        # Test discover command
        with patch("sys.argv", ["pacc", "fragment", "discover", str(self.temp_dir)]):
            result = self.cli.main()

        assert result == 0

    def test_fragment_discover_with_metadata(self):
        """Test fragment discover command with metadata."""
        # Create test collection
        self.create_test_collection()

        # Test discover command with metadata
        with patch(
            "sys.argv", ["pacc", "fragment", "discover", str(self.temp_dir), "--show-metadata"]
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_discover_json_format(self):
        """Test fragment discover command with JSON format."""
        # Create test collection
        self.create_test_collection()

        # Test discover command with JSON format
        with patch(
            "sys.argv", ["pacc", "fragment", "discover", str(self.temp_dir), "--format", "json"]
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_discover_yaml_format(self):
        """Test fragment discover command with YAML format."""
        # Create test collection
        self.create_test_collection()

        # Test discover command with YAML format
        with patch(
            "sys.argv", ["pacc", "fragment", "discover", str(self.temp_dir), "--format", "yaml"]
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_discover_nonexistent_path(self):
        """Test fragment discover command with nonexistent path."""
        nonexistent_path = self.temp_dir / "nonexistent"

        with patch("sys.argv", ["pacc", "fragment", "discover", str(nonexistent_path)]):
            result = self.cli.main()

        assert result == 1

    def test_fragment_discover_no_collections(self):
        """Test fragment discover command when no collections found."""
        # Create empty directory
        empty_dir = self.temp_dir / "empty"
        empty_dir.mkdir()

        with patch("sys.argv", ["pacc", "fragment", "discover", str(empty_dir)]):
            result = self.cli.main()

        assert result == 0  # Should succeed but show no collections

    def test_fragment_collection_install_dry_run(self):
        """Test collection install command in dry-run mode."""
        # Create test collection
        collection_dir = self.create_test_collection()

        with patch(
            "sys.argv", ["pacc", "fragment", "install-collection", str(collection_dir), "--dry-run"]
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_install_selective_files(self):
        """Test collection install with selective files."""
        # Create test collection
        collection_dir = self.create_test_collection()

        with patch(
            "sys.argv",
            [
                "pacc",
                "fragment",
                "install-collection",
                str(collection_dir),
                "--files",
                "fragment1",
                "--dry-run",
            ],
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_install_include_optional(self):
        """Test collection install with optional files."""
        # Create test collection
        collection_dir = self.create_test_collection()

        with patch(
            "sys.argv",
            [
                "pacc",
                "fragment",
                "install-collection",
                str(collection_dir),
                "--include-optional",
                "--dry-run",
            ],
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_install_force(self):
        """Test collection install with force option."""
        # Create test collection
        collection_dir = self.create_test_collection()

        with patch(
            "sys.argv",
            ["pacc", "fragment", "install-collection", str(collection_dir), "--force", "--dry-run"],
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_install_user_storage(self):
        """Test collection install to user storage."""
        # Create test collection
        collection_dir = self.create_test_collection()

        with patch(
            "sys.argv",
            [
                "pacc",
                "fragment",
                "install-collection",
                str(collection_dir),
                "--storage-type",
                "user",
                "--dry-run",
            ],
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_install_no_dependencies(self):
        """Test collection install without dependency resolution."""
        # Create test collection
        collection_dir = self.create_test_collection()

        with patch(
            "sys.argv",
            [
                "pacc",
                "fragment",
                "install-collection",
                str(collection_dir),
                "--no-dependencies",
                "--dry-run",
            ],
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_install_no_verify(self):
        """Test collection install without integrity verification."""
        # Create test collection
        collection_dir = self.create_test_collection()

        with patch(
            "sys.argv",
            [
                "pacc",
                "fragment",
                "install-collection",
                str(collection_dir),
                "--no-verify",
                "--dry-run",
            ],
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_install_nonexistent_source(self):
        """Test collection install with nonexistent source."""
        nonexistent_path = self.temp_dir / "nonexistent"

        with patch("sys.argv", ["pacc", "fragment", "install-collection", str(nonexistent_path)]):
            result = self.cli.main()

        assert result == 1

    def test_fragment_collection_install_file_source(self):
        """Test collection install with file source (should fail)."""
        # Create a single file
        file_path = self.temp_dir / "test.md"
        file_path.write_text("# Test")

        with patch("sys.argv", ["pacc", "fragment", "install-collection", str(file_path)]):
            result = self.cli.main()

        assert result == 1

    def test_fragment_collection_status_no_collections(self):
        """Test collection status when no collections are installed."""
        with patch("sys.argv", ["pacc", "fragment", "collection-status"]):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_status_json_format(self):
        """Test collection status with JSON format."""
        with patch("sys.argv", ["pacc", "fragment", "collection-status", "--format", "json"]):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_status_yaml_format(self):
        """Test collection status with YAML format."""
        with patch("sys.argv", ["pacc", "fragment", "collection-status", "--format", "yaml"]):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_status_specific_collection(self):
        """Test collection status for specific collection."""
        with patch("sys.argv", ["pacc", "fragment", "collection-status", "nonexistent-collection"]):
            result = self.cli.main()

        assert result == 0  # Should succeed but show not installed

    def test_fragment_collection_status_filter_by_storage(self):
        """Test collection status filtered by storage type."""
        with patch(
            "sys.argv", ["pacc", "fragment", "collection-status", "--storage-type", "project"]
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_update_nonexistent(self):
        """Test collection update for nonexistent collection."""
        collection_dir = self.create_test_collection()

        with patch(
            "sys.argv",
            [
                "pacc",
                "fragment",
                "update-collection",
                "nonexistent-collection",
                str(collection_dir),
            ],
        ):
            result = self.cli.main()

        assert result == 1

    def test_fragment_collection_update_no_source(self):
        """Test collection update without source path."""
        with patch("sys.argv", ["pacc", "fragment", "update-collection", "test-collection"]):
            result = self.cli.main()

        assert result == 1

    def test_fragment_collection_update_dry_run(self):
        """Test collection update in dry-run mode."""
        # Create installed collection state
        pacc_json = self.temp_dir / "pacc.json"
        pacc_data = {
            "collections": {
                "test-collection": {
                    "version": "1.0.0",
                    "files": ["fragment1"],
                    "storage_type": "project",
                }
            }
        }
        pacc_json.write_text(json.dumps(pacc_data))

        # Create new version
        collection_dir = self.create_test_collection()

        with patch(
            "sys.argv",
            [
                "pacc",
                "fragment",
                "update-collection",
                "test-collection",
                str(collection_dir),
                "--dry-run",
            ],
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_remove_nonexistent(self):
        """Test collection remove for nonexistent collection."""
        with patch("sys.argv", ["pacc", "fragment", "remove-collection", "nonexistent-collection"]):
            result = self.cli.main()

        assert result == 1

    def test_fragment_collection_remove_force(self):
        """Test collection remove with force option."""
        # Create installed collection state
        pacc_json = self.temp_dir / "pacc.json"
        pacc_data = {
            "collections": {
                "test-collection": {
                    "version": "1.0.0",
                    "files": ["fragment1"],
                    "storage_type": "project",
                }
            }
        }
        pacc_json.write_text(json.dumps(pacc_data))

        with patch(
            "sys.argv", ["pacc", "fragment", "remove-collection", "test-collection", "--force"]
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_remove_with_dependencies(self):
        """Test collection remove with dependency removal."""
        # Create installed collection state
        pacc_json = self.temp_dir / "pacc.json"
        pacc_data = {
            "collections": {
                "test-collection": {
                    "version": "1.0.0",
                    "files": ["fragment1"],
                    "storage_type": "project",
                }
            }
        }
        pacc_json.write_text(json.dumps(pacc_data))

        with patch(
            "sys.argv",
            [
                "pacc",
                "fragment",
                "remove-collection",
                "test-collection",
                "--remove-dependencies",
                "--force",
            ],
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_collection_remove_user_storage(self):
        """Test collection remove from user storage."""
        # Create installed collection state
        pacc_json = self.temp_dir / "pacc.json"
        pacc_data = {
            "collections": {
                "test-collection": {
                    "version": "1.0.0",
                    "files": ["fragment1"],
                    "storage_type": "user",
                }
            }
        }
        pacc_json.write_text(json.dumps(pacc_data))

        with patch(
            "sys.argv",
            [
                "pacc",
                "fragment",
                "remove-collection",
                "test-collection",
                "--storage-type",
                "user",
                "--force",
            ],
        ):
            result = self.cli.main()

        assert result == 0

    def test_fragment_help_shows_collection_commands(self):
        """Test that fragment help shows collection commands."""
        with patch("sys.argv", ["pacc", "fragment"]):
            result = self.cli.main()

        assert result == 0
        # Should show collection commands in help


class TestFragmentCollectionErrorHandling:
    """Test error handling in fragment collection commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.cli = PACCCli()

        # Change to temp directory for testing
        self.original_cwd = Path.cwd()
        import os

        os.chdir(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import os

        os.chdir(self.original_cwd)

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_collection_manager_import_error(self):
        """Test handling of collection manager import error."""
        with patch(
            "pacc.fragments.collection_manager.FragmentCollectionManager",
            side_effect=ImportError("Module not found"),
        ):
            with patch("sys.argv", ["pacc", "fragment", "discover", str(self.temp_dir)]):
                result = self.cli.main()

            assert result == 1

    def test_collection_install_exception(self):
        """Test handling of exceptions during collection install."""
        # Create test collection
        collection_dir = self.temp_dir / "test-collection"
        collection_dir.mkdir()
        (collection_dir / "fragment1.md").write_text("# Fragment 1")
        (collection_dir / "fragment2.md").write_text("# Fragment 2")

        with patch(
            "pacc.fragments.collection_manager.FragmentCollectionManager.install_collection",
            side_effect=Exception("Installation failed"),
        ):
            with patch("sys.argv", ["pacc", "fragment", "install-collection", str(collection_dir)]):
                result = self.cli.main()

            assert result == 1

    def test_collection_status_exception(self):
        """Test handling of exceptions during collection status."""
        with patch(
            "pacc.fragments.collection_manager.FragmentCollectionManager.list_collections_with_metadata",
            side_effect=Exception("Status check failed"),
        ):
            with patch("sys.argv", ["pacc", "fragment", "collection-status"]):
                result = self.cli.main()

            assert result == 1

    def test_collection_update_exception(self):
        """Test handling of exceptions during collection update."""
        # Create installed collection state
        pacc_json = self.temp_dir / "pacc.json"
        pacc_data = {
            "collections": {
                "test-collection": {
                    "version": "1.0.0",
                    "files": ["fragment1"],
                    "storage_type": "project",
                }
            }
        }
        pacc_json.write_text(json.dumps(pacc_data))

        collection_dir = self.temp_dir / "test-collection"
        collection_dir.mkdir()
        (collection_dir / "fragment1.md").write_text("# Fragment 1")

        with patch(
            "pacc.fragments.collection_manager.FragmentCollectionManager.update_collection",
            side_effect=Exception("Update failed"),
        ):
            with patch(
                "sys.argv",
                ["pacc", "fragment", "update-collection", "test-collection", str(collection_dir)],
            ):
                result = self.cli.main()

            assert result == 1

    def test_collection_remove_exception(self):
        """Test handling of exceptions during collection removal."""
        # Create installed collection state
        pacc_json = self.temp_dir / "pacc.json"
        pacc_data = {
            "collections": {
                "test-collection": {
                    "version": "1.0.0",
                    "files": ["fragment1"],
                    "storage_type": "project",
                }
            }
        }
        pacc_json.write_text(json.dumps(pacc_data))

        with patch(
            "pacc.fragments.collection_manager.FragmentCollectionManager.remove_collection",
            side_effect=Exception("Removal failed"),
        ):
            with patch(
                "sys.argv", ["pacc", "fragment", "remove-collection", "test-collection", "--force"]
            ):
                result = self.cli.main()

            assert result == 1


if __name__ == "__main__":
    pytest.main([__file__])
