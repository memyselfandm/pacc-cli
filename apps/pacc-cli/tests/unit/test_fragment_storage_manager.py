"""Tests for FragmentStorageManager."""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from pacc.errors.exceptions import PACCError
from pacc.fragments.storage_manager import FragmentStorageManager, GitIgnoreManager


class TestFragmentStorageManager:
    """Test cases for FragmentStorageManager."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def temp_user_home(self):
        """Create a temporary user home directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def storage_manager(self, temp_project, temp_user_home, monkeypatch):
        """Create FragmentStorageManager with temporary directories."""
        # Mock Path.home() to return temp directory
        monkeypatch.setattr(Path, "home", lambda: temp_user_home)

        # Initialize manager with temp project root
        manager = FragmentStorageManager(temp_project)
        return manager

    def test_initialization(self, storage_manager, temp_project, temp_user_home):
        """Test manager initialization."""
        assert storage_manager.project_root.resolve() == temp_project.resolve()
        assert storage_manager.project_storage == temp_project.resolve() / ".claude/pacc/fragments"
        # User storage is created from Path.home() which gets mocked, so we need to check the stem
        assert storage_manager.user_storage.parts[-3:] == (".claude", "pacc", "fragments")

        # Check that storage directories are created
        assert storage_manager.project_storage.exists()
        assert storage_manager.user_storage.exists()

    def test_store_and_load_fragment(self, storage_manager):
        """Test storing and loading fragments."""
        fragment_name = "test-fragment"
        content = "# Test Fragment\n\nThis is a test fragment."

        # Store fragment
        stored_path = storage_manager.store_fragment(fragment_name, content, "project")
        assert stored_path.exists()
        assert stored_path.name == "test-fragment.md"

        # Load fragment
        loaded_content = storage_manager.load_fragment(fragment_name, "project")
        assert loaded_content == content

    def test_store_fragment_with_collection(self, storage_manager):
        """Test storing fragments in collections."""
        fragment_name = "collection-fragment"
        content = "# Collection Fragment\n\nThis is in a collection."
        collection = "my-collection"

        # Store in collection
        stored_path = storage_manager.store_fragment(
            fragment_name, content, "project", collection=collection
        )

        expected_path = storage_manager.project_storage / collection / "collection-fragment.md"
        assert stored_path == expected_path
        assert stored_path.exists()

        # Verify collection directory was created
        collection_dir = storage_manager.project_storage / collection
        assert collection_dir.exists()
        assert collection_dir.is_dir()

    def test_store_fragment_user_storage(self, storage_manager):
        """Test storing fragments in user storage."""
        fragment_name = "user-fragment"
        content = "# User Fragment\n\nThis is a user fragment."

        # Store in user storage
        stored_path = storage_manager.store_fragment(fragment_name, content, "user")
        assert stored_path.exists()
        assert storage_manager.user_storage in stored_path.parents

    def test_store_fragment_overwrite(self, storage_manager):
        """Test fragment overwrite behavior."""
        fragment_name = "overwrite-test"
        original_content = "# Original Content"
        new_content = "# New Content"

        # Store original
        storage_manager.store_fragment(fragment_name, original_content, "project")

        # Try to store without overwrite (should fail)
        with pytest.raises(PACCError, match="Fragment already exists"):
            storage_manager.store_fragment(fragment_name, new_content, "project", overwrite=False)

        # Store with overwrite (should succeed)
        storage_manager.store_fragment(fragment_name, new_content, "project", overwrite=True)
        loaded_content = storage_manager.load_fragment(fragment_name, "project")
        assert loaded_content == new_content

    def test_find_fragment(self, storage_manager):
        """Test fragment finding functionality."""
        # Store fragments in different locations
        storage_manager.store_fragment("project-frag", "Project content", "project")
        storage_manager.store_fragment("user-frag", "User content", "user")
        storage_manager.store_fragment(
            "collection-frag", "Collection content", "project", collection="test-col"
        )

        # Find specific fragments
        project_path = storage_manager.find_fragment("project-frag", "project")
        assert project_path is not None
        assert "project-frag.md" in str(project_path)

        user_path = storage_manager.find_fragment("user-frag", "user")
        assert user_path is not None
        assert "user-frag.md" in str(user_path)

        collection_path = storage_manager.find_fragment("collection-frag", "project", "test-col")
        assert collection_path is not None
        assert "test-col" in str(collection_path)

        # Test searching both storages
        both_path = storage_manager.find_fragment("project-frag", None)
        assert both_path is not None

        # Test not found
        not_found = storage_manager.find_fragment("nonexistent")
        assert not_found is None

    def test_list_fragments(self, storage_manager):
        """Test fragment listing functionality."""
        # Store test fragments
        storage_manager.store_fragment("frag1", "Content 1", "project")
        storage_manager.store_fragment("frag2", "Content 2", "user")
        storage_manager.store_fragment(
            "col-frag", "Collection content", "project", collection="test-col"
        )

        # List all fragments
        all_fragments = storage_manager.list_fragments()
        assert len(all_fragments) == 3

        # List project fragments only
        project_fragments = storage_manager.list_fragments(storage_type="project")
        assert len(project_fragments) == 2

        # List user fragments only
        user_fragments = storage_manager.list_fragments(storage_type="user")
        assert len(user_fragments) == 1

        # List collection fragments
        collection_fragments = storage_manager.list_fragments(
            storage_type="project", collection="test-col"
        )
        assert len(collection_fragments) == 1
        assert collection_fragments[0].collection_name == "test-col"

    def test_list_fragments_with_pattern(self, storage_manager):
        """Test fragment listing with pattern matching."""
        # Store test fragments with different names
        storage_manager.store_fragment("test-alpha", "Content A", "project")
        storage_manager.store_fragment("test-beta", "Content B", "project")
        storage_manager.store_fragment("other-gamma", "Content C", "project")

        # List with pattern
        test_fragments = storage_manager.list_fragments(pattern="test-*")
        assert len(test_fragments) == 2

        # List with more specific pattern
        alpha_fragments = storage_manager.list_fragments(pattern="*-alpha")
        assert len(alpha_fragments) == 1

    def test_list_collections(self, storage_manager):
        """Test collection listing functionality."""
        # Store fragments in different collections
        storage_manager.store_fragment("frag1", "Content 1", "project", collection="col1")
        storage_manager.store_fragment("frag2", "Content 2", "project", collection="col1")
        storage_manager.store_fragment("frag3", "Content 3", "project", collection="col2")
        storage_manager.store_fragment("frag4", "Content 4", "user", collection="user-col")

        # List all collections
        collections = storage_manager.list_collections()
        assert "col1" in collections
        assert "col2" in collections
        assert "user-col" in collections

        # Check fragment counts
        assert len(collections["col1"]) == 2
        assert len(collections["col2"]) == 1
        assert len(collections["user-col"]) == 1

        # List project collections only
        project_collections = storage_manager.list_collections(storage_type="project")
        assert "col1" in project_collections
        assert "col2" in project_collections
        assert "user-col" not in project_collections

    def test_remove_fragment(self, storage_manager):
        """Test fragment removal."""
        fragment_name = "remove-test"
        storage_manager.store_fragment(fragment_name, "Content", "project")

        # Verify fragment exists
        assert storage_manager.find_fragment(fragment_name, "project") is not None

        # Remove fragment
        removed = storage_manager.remove_fragment(fragment_name, "project")
        assert removed is True

        # Verify fragment is gone
        assert storage_manager.find_fragment(fragment_name, "project") is None

        # Try to remove non-existent fragment
        not_removed = storage_manager.remove_fragment("nonexistent", "project")
        assert not_removed is False

    def test_remove_fragment_cleans_empty_collection(self, storage_manager):
        """Test that removing last fragment in collection cleans up directory."""
        collection = "temp-collection"
        fragment_name = "only-fragment"

        # Store fragment in collection
        storage_manager.store_fragment(fragment_name, "Content", "project", collection=collection)
        collection_path = storage_manager.project_storage / collection
        assert collection_path.exists()

        # Remove fragment
        storage_manager.remove_fragment(fragment_name, "project", collection)

        # Collection directory should be cleaned up
        assert not collection_path.exists()

    def test_create_and_remove_collection(self, storage_manager):
        """Test collection creation and removal."""
        collection_name = "test-collection"

        # Create collection
        collection_path = storage_manager.create_collection(collection_name, "project")
        assert collection_path.exists()
        assert collection_path.is_dir()

        # Remove empty collection
        removed = storage_manager.remove_collection(collection_name, "project")
        assert removed is True
        assert not collection_path.exists()

        # Create collection with fragments
        storage_manager.create_collection(collection_name, "project")
        storage_manager.store_fragment(
            "test-frag", "Content", "project", collection=collection_name
        )

        # Try to remove non-empty collection without force
        not_removed = storage_manager.remove_collection(collection_name, "project", force=False)
        assert not_removed is False
        assert collection_path.exists()

        # Remove with force
        removed = storage_manager.remove_collection(collection_name, "project", force=True)
        assert removed is True
        assert not collection_path.exists()

    def test_get_fragment_stats(self, storage_manager):
        """Test fragment statistics."""
        # Store test fragments
        storage_manager.store_fragment("proj1", "Project content 1", "project")
        storage_manager.store_fragment(
            "proj2", "Project content 2", "project", collection="proj-col"
        )
        storage_manager.store_fragment("user1", "User content 1", "user")

        stats = storage_manager.get_fragment_stats()

        assert stats["project_fragments"] == 2
        assert stats["user_fragments"] == 1
        assert stats["total_fragments"] == 3
        assert stats["collections"] == 1  # proj-col
        assert stats["total_size"] > 0
        assert "project" in stats["storage_paths"]
        assert "user" in stats["storage_paths"]

    def test_cleanup_empty_directories(self, storage_manager):
        """Test cleanup of empty directories."""
        # Create empty collection directories
        empty_col1 = storage_manager.project_storage / "empty1"
        empty_col2 = storage_manager.project_storage / "empty2"
        empty_col1.mkdir()
        empty_col2.mkdir()

        # Create non-empty collection
        non_empty = storage_manager.project_storage / "nonempty"
        non_empty.mkdir()
        (non_empty / "fragment.md").write_text("Content")

        # Run cleanup
        removed_count = storage_manager.cleanup_empty_directories("project")

        assert removed_count == 2
        assert not empty_col1.exists()
        assert not empty_col2.exists()
        assert non_empty.exists()

    def test_backup_fragments(self, storage_manager, temp_project):
        """Test fragment backup functionality."""
        # Store test fragments
        storage_manager.store_fragment("backup-test1", "Content 1", "project")
        storage_manager.store_fragment("backup-test2", "Content 2", "user")

        backup_dir = temp_project / "backups"
        backup_path = storage_manager.backup_fragments(backup_dir)

        assert backup_path.exists()
        assert backup_path.is_dir()
        assert "fragment_backup_" in backup_path.name

        # Check backup contents
        project_backup = backup_path / "project_fragments"
        user_backup = backup_path / "user_fragments"

        assert project_backup.exists()
        assert user_backup.exists()

        # Verify fragments are backed up
        assert (project_backup / "backup-test1.md").exists()
        assert (user_backup / "backup-test2.md").exists()

    def test_cross_platform_paths(self, storage_manager):
        """Test cross-platform path handling."""
        fragment_name = "cross-platform-test"
        content = "Cross platform content"

        # Store fragment
        stored_path = storage_manager.store_fragment(fragment_name, content, "project")

        # Verify path is properly normalized
        assert stored_path.is_absolute()
        assert stored_path.exists()

        # Test finding with different path separators
        found_path = storage_manager.find_fragment(fragment_name, "project")
        assert found_path == stored_path

    def test_fragment_location_metadata(self, storage_manager):
        """Test FragmentLocation metadata population."""
        fragment_name = "metadata-test"
        content = "# Metadata Test\n\nTest fragment for metadata."

        # Store fragment
        storage_manager.store_fragment(fragment_name, content, "project")

        # List fragments to get metadata
        fragments = storage_manager.list_fragments(storage_type="project")
        test_fragment = next(f for f in fragments if f.name == fragment_name)

        assert test_fragment.name == fragment_name
        assert test_fragment.storage_type == "project"
        assert test_fragment.is_collection is False
        assert test_fragment.collection_name is None
        assert test_fragment.last_modified is not None
        assert isinstance(test_fragment.last_modified, datetime)
        assert test_fragment.size is not None
        assert test_fragment.size > 0

    def test_load_nonexistent_fragment(self, storage_manager):
        """Test loading non-existent fragment raises error."""
        with pytest.raises(PACCError, match="Fragment not found"):
            storage_manager.load_fragment("nonexistent", "project")

    def test_fragment_extension_handling(self, storage_manager):
        """Test fragment extension handling."""
        # Store fragment without .md extension
        stored_path = storage_manager.store_fragment("no-extension", "Content", "project")
        assert stored_path.name == "no-extension.md"

        # Store fragment with .md extension
        stored_path = storage_manager.store_fragment("with-extension.md", "Content", "project")
        assert stored_path.name == "with-extension.md"

        # Find fragment without specifying extension
        found_path = storage_manager.find_fragment("no-extension", "project")
        assert found_path is not None

        # Find fragment with extension
        found_path = storage_manager.find_fragment("with-extension.md", "project")
        assert found_path is not None


class TestGitIgnoreManager:
    """Test cases for GitIgnoreManager."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def gitignore_manager(self, temp_project):
        """Create GitIgnoreManager with temporary directory."""
        return GitIgnoreManager(temp_project)

    def test_ensure_fragment_entries_new_gitignore(self, gitignore_manager, temp_project):
        """Test adding entries to new .gitignore."""
        fragment_paths = [".claude/pacc/fragments/"]

        modified = gitignore_manager.ensure_fragment_entries(fragment_paths)
        assert modified is True

        gitignore_path = temp_project / ".gitignore"
        assert gitignore_path.exists()

        content = gitignore_path.read_text()
        assert ".claude/pacc/fragments/" in content
        assert "# PACC Fragment Storage" in content

    def test_ensure_fragment_entries_existing_gitignore(self, gitignore_manager, temp_project):
        """Test adding entries to existing .gitignore."""
        gitignore_path = temp_project / ".gitignore"
        gitignore_path.write_text("# Existing content\n*.pyc\n")

        fragment_paths = [".claude/pacc/fragments/"]

        modified = gitignore_manager.ensure_fragment_entries(fragment_paths)
        assert modified is True

        content = gitignore_path.read_text()
        assert "*.pyc" in content  # Original content preserved
        assert ".claude/pacc/fragments/" in content
        assert "# PACC Fragment Storage" in content

    def test_ensure_fragment_entries_already_present(self, gitignore_manager, temp_project):
        """Test adding entries that are already present."""
        gitignore_path = temp_project / ".gitignore"
        gitignore_path.write_text(".claude/pacc/fragments/\n")

        fragment_paths = [".claude/pacc/fragments/"]

        modified = gitignore_manager.ensure_fragment_entries(fragment_paths)
        assert modified is False

    def test_remove_fragment_entries(self, gitignore_manager, temp_project):
        """Test removing fragment entries from .gitignore."""
        gitignore_path = temp_project / ".gitignore"
        gitignore_path.write_text("*.pyc\n.claude/pacc/fragments/\n*.tmp\n")

        fragment_paths = [".claude/pacc/fragments/"]

        modified = gitignore_manager.remove_fragment_entries(fragment_paths)
        assert modified is True

        content = gitignore_path.read_text()
        assert "*.pyc" in content
        assert "*.tmp" in content
        assert ".claude/pacc/fragments/" not in content

    def test_remove_fragment_entries_not_present(self, gitignore_manager, temp_project):
        """Test removing entries that aren't present."""
        gitignore_path = temp_project / ".gitignore"
        gitignore_path.write_text("*.pyc\n")

        fragment_paths = [".claude/pacc/fragments/"]

        modified = gitignore_manager.remove_fragment_entries(fragment_paths)
        assert modified is False

    def test_cross_platform_paths_in_gitignore(self, gitignore_manager, temp_project):
        """Test that paths are normalized for git (forward slashes)."""
        # Test with Windows-style path
        fragment_paths = [".claude\\pacc\\fragments\\"]

        modified = gitignore_manager.ensure_fragment_entries(fragment_paths)
        assert modified is True

        gitignore_path = temp_project / ".gitignore"
        content = gitignore_path.read_text()
        # Should be normalized to forward slashes
        assert ".claude/pacc/fragments/" in content
        assert ".claude\\pacc\\fragments\\" not in content


class TestFragmentStorageIntegration:
    """Integration tests for fragment storage system."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def temp_user_home(self):
        """Create a temporary user home directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def storage_manager(self, temp_project, temp_user_home, monkeypatch):
        """Create FragmentStorageManager with temporary directories."""
        monkeypatch.setattr(Path, "home", lambda: temp_user_home)
        return FragmentStorageManager(temp_project)

    def test_complete_fragment_lifecycle(self, storage_manager, temp_project):
        """Test complete fragment lifecycle from creation to removal."""
        # 1. Store fragments in different locations and collections
        storage_manager.store_fragment("project-main", "Main project fragment", "project")
        storage_manager.store_fragment("user-main", "Main user fragment", "user")
        storage_manager.store_fragment(
            "collection-item", "Collection fragment", "project", collection="docs"
        )

        # 2. Verify gitignore was updated for project fragments
        gitignore_path = temp_project / ".gitignore"
        assert gitignore_path.exists()
        gitignore_content = gitignore_path.read_text()
        assert ".claude/pacc/fragments/" in gitignore_content

        # 3. List and verify all fragments
        all_fragments = storage_manager.list_fragments()
        assert len(all_fragments) == 3

        fragment_names = {f.name for f in all_fragments}
        assert fragment_names == {"project-main", "user-main", "collection-item"}

        # 4. Verify collections
        collections = storage_manager.list_collections()
        assert "docs" in collections
        assert "collection-item" in collections["docs"]

        # 5. Test fragment search and loading
        found_project = storage_manager.find_fragment("project-main")
        assert found_project is not None
        loaded_content = storage_manager.load_fragment("project-main")
        assert loaded_content == "Main project fragment"

        # 6. Create backup
        backup_path = storage_manager.backup_fragments(temp_project / "backup")
        assert backup_path.exists()
        assert (backup_path / "project_fragments" / "project-main.md").exists()
        assert (backup_path / "project_fragments" / "docs" / "collection-item.md").exists()
        assert (backup_path / "user_fragments" / "user-main.md").exists()

        # 7. Get statistics
        stats = storage_manager.get_fragment_stats()
        assert stats["total_fragments"] == 3
        assert stats["project_fragments"] == 2
        assert stats["user_fragments"] == 1
        assert stats["collections"] == 1

        # 8. Remove fragments and verify cleanup
        removed = storage_manager.remove_fragment("collection-item", collection="docs")
        assert removed is True

        # Collection directory should be cleaned up
        docs_dir = storage_manager.project_storage / "docs"
        assert not docs_dir.exists()

        # 9. Final verification
        remaining_fragments = storage_manager.list_fragments()
        assert len(remaining_fragments) == 2

        remaining_names = {f.name for f in remaining_fragments}
        assert remaining_names == {"project-main", "user-main"}

    def test_error_handling_and_recovery(self, storage_manager):
        """Test error handling in various scenarios."""
        # Test storing to read-only location (simulated)
        fragment_name = "error-test"
        content = "Error test content"

        # Store valid fragment first
        storage_manager.store_fragment(fragment_name, content, "project")

        # Test duplicate storage without overwrite
        with pytest.raises(PACCError, match="Fragment already exists"):
            storage_manager.store_fragment(fragment_name, content, "project", overwrite=False)

        # Test loading non-existent fragment
        with pytest.raises(PACCError, match="Fragment not found"):
            storage_manager.load_fragment("nonexistent-fragment", "project")

        # Test operations on invalid storage types
        fragments = storage_manager.list_fragments(storage_type="invalid")
        assert len(fragments) == 0
