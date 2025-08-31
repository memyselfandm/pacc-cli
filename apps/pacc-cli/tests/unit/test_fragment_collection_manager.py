"""Unit tests for fragment collection manager."""

import pytest
import tempfile
import json
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from pacc.fragments.collection_manager import (
    FragmentCollectionManager,
    CollectionMetadata,
    CollectionMetadataParser,
    CollectionDependencyResolver,
    CollectionInstallOptions,
    CollectionInstallResult,
    CollectionUpdateInfo
)
from pacc.errors.exceptions import PACCError


class TestCollectionMetadata:
    """Test collection metadata functionality."""
    
    def test_metadata_creation(self):
        """Test creating collection metadata."""
        metadata = CollectionMetadata(
            name="test-collection",
            version="1.0.0",
            description="Test collection",
            author="Test Author",
            tags=["test", "collection"],
            dependencies=["other-collection"],
            files=["fragment1", "fragment2"]
        )
        
        assert metadata.name == "test-collection"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test collection"
        assert "test" in metadata.tags
        assert "other-collection" in metadata.dependencies
        assert len(metadata.files) == 2
    
    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = CollectionMetadata(
            name="test-collection",
            version="1.0.0",
            description="Test collection"
        )
        
        data = metadata.to_dict()
        
        assert data["name"] == "test-collection"
        assert data["version"] == "1.0.0"
        assert data["description"] == "Test collection"
        assert isinstance(data["tags"], list)
        assert isinstance(data["dependencies"], list)
    
    def test_metadata_from_dict(self):
        """Test creating metadata from dictionary."""
        data = {
            "name": "test-collection",
            "version": "2.0.0",
            "description": "Test description",
            "author": "Test Author",
            "tags": ["test"],
            "dependencies": ["dep1"],
            "files": ["file1", "file2"]
        }
        
        metadata = CollectionMetadata.from_dict(data)
        
        assert metadata.name == "test-collection"
        assert metadata.version == "2.0.0"
        assert metadata.description == "Test description"
        assert metadata.author == "Test Author"
        assert metadata.tags == ["test"]
        assert metadata.dependencies == ["dep1"]
        assert metadata.files == ["file1", "file2"]


class TestCollectionMetadataParser:
    """Test collection metadata parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.parser = CollectionMetadataParser()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_parse_pacc_json_metadata(self):
        """Test parsing metadata from pacc.json."""
        # Create test pacc.json
        pacc_json = self.temp_dir / "pacc.json"
        pacc_data = {
            "collection": {
                "name": "test-collection",
                "version": "1.0.0",
                "description": "Test collection",
                "author": "Test Author",
                "tags": ["test"],
                "dependencies": ["dep1"],
                "files": ["fragment1", "fragment2"]
            }
        }
        pacc_json.write_text(json.dumps(pacc_data))
        
        # Create test fragments
        (self.temp_dir / "fragment1.md").write_text("# Fragment 1")
        (self.temp_dir / "fragment2.md").write_text("# Fragment 2")
        
        # Parse metadata
        metadata = self.parser.parse_collection_metadata(self.temp_dir)
        
        assert metadata is not None
        assert metadata.name == "test-collection"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test collection"
        assert metadata.author == "Test Author"
        assert metadata.tags == ["test"]
        assert metadata.dependencies == ["dep1"]
        assert "fragment1" in metadata.files
        assert "fragment2" in metadata.files
        assert metadata.checksum is not None
    
    def test_parse_frontmatter_metadata(self):
        """Test parsing metadata from README.md frontmatter."""
        # Create README.md with frontmatter
        readme_content = """---
collection:
  name: test-collection
  version: 1.5.0
  description: Test collection from README
  author: README Author
  tags: [readme, test]
  dependencies: [readme-dep]
---

# Test Collection

This is a test collection.
"""
        (self.temp_dir / "README.md").write_text(readme_content)
        (self.temp_dir / "fragment1.md").write_text("# Fragment 1")
        
        # Parse metadata
        metadata = self.parser.parse_collection_metadata(self.temp_dir)
        
        assert metadata is not None
        assert metadata.name == "test-collection"
        assert metadata.version == "1.5.0"
        assert metadata.description == "Test collection from README"
        assert metadata.author == "README Author"
        assert "readme" in metadata.tags
        assert "test" in metadata.tags
        assert "readme-dep" in metadata.dependencies
    
    def test_parse_minimal_metadata(self):
        """Test parsing when no explicit metadata exists."""
        # Create fragments without metadata
        (self.temp_dir / "fragment1.md").write_text("# Fragment 1")
        (self.temp_dir / "fragment2.md").write_text("# Fragment 2")
        
        # Parse metadata
        metadata = self.parser.parse_collection_metadata(self.temp_dir)
        
        assert metadata is not None
        assert metadata.name == self.temp_dir.name
        assert metadata.version == "1.0.0"
        assert len(metadata.files) == 2
        assert "fragment1" in metadata.files
        assert "fragment2" in metadata.files
        assert metadata.checksum is not None
    
    def test_calculate_checksum(self):
        """Test checksum calculation."""
        # Create test fragments
        (self.temp_dir / "fragment1.md").write_text("# Fragment 1\nContent 1")
        (self.temp_dir / "fragment2.md").write_text("# Fragment 2\nContent 2")
        
        # Calculate checksum
        files = ["fragment1", "fragment2"]
        checksum1 = self.parser._calculate_collection_checksum(self.temp_dir, files)
        
        # Should be consistent
        checksum2 = self.parser._calculate_collection_checksum(self.temp_dir, files)
        assert checksum1 == checksum2
        
        # Should change if content changes
        (self.temp_dir / "fragment1.md").write_text("# Fragment 1\nModified content")
        checksum3 = self.parser._calculate_collection_checksum(self.temp_dir, files)
        assert checksum1 != checksum3


class TestCollectionDependencyResolver:
    """Test collection dependency resolver."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.storage_manager = Mock()
        self.resolver = CollectionDependencyResolver(self.storage_manager)
    
    def test_resolve_no_dependencies(self):
        """Test resolving metadata with no dependencies."""
        metadata = CollectionMetadata(name="test", version="1.0.0")
        
        resolved = self.resolver.resolve_dependencies(metadata)
        
        assert resolved == []
    
    def test_resolve_missing_dependencies(self):
        """Test resolving metadata with missing dependencies."""
        metadata = CollectionMetadata(
            name="test",
            version="1.0.0",
            dependencies=["missing-dep"]
        )
        
        # Mock storage manager to return empty collections
        self.storage_manager.list_collections.return_value = {}
        
        resolved = self.resolver.resolve_dependencies(metadata)
        
        assert "missing-dep" in resolved
    
    def test_resolve_existing_dependencies(self):
        """Test resolving metadata with existing dependencies."""
        metadata = CollectionMetadata(
            name="test",
            version="1.0.0",
            dependencies=["existing-dep"]
        )
        
        # Mock storage manager to return existing collection
        self.storage_manager.list_collections.return_value = {
            "existing-dep": ["fragment1"]
        }
        
        resolved = self.resolver.resolve_dependencies(metadata)
        
        assert resolved == []
    
    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""
        # This is a simplified test - full circular dependency detection
        # would require more complex setup
        metadata = CollectionMetadata(
            name="test",
            version="1.0.0",
            dependencies=["test"]  # Depends on itself
        )
        
        with pytest.raises(PACCError, match="Circular dependency"):
            self.resolver.resolve_dependencies(metadata)


class TestCollectionInstallOptions:
    """Test collection install options."""
    
    def test_default_options(self):
        """Test default install options."""
        options = CollectionInstallOptions()
        
        assert options.selected_files is None
        assert options.include_optional is False
        assert options.force_overwrite is False
        assert options.storage_type == "project"
        assert options.verify_integrity is True
        assert options.resolve_dependencies is True
        assert options.dry_run is False
    
    def test_custom_options(self):
        """Test custom install options."""
        options = CollectionInstallOptions(
            selected_files=["file1", "file2"],
            include_optional=True,
            force_overwrite=True,
            storage_type="user",
            verify_integrity=False,
            resolve_dependencies=False,
            dry_run=True
        )
        
        assert options.selected_files == ["file1", "file2"]
        assert options.include_optional is True
        assert options.force_overwrite is True
        assert options.storage_type == "user"
        assert options.verify_integrity is False
        assert options.resolve_dependencies is False
        assert options.dry_run is True


class TestFragmentCollectionManager:
    """Test fragment collection manager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.collection_manager = FragmentCollectionManager(project_root=self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_manager_initialization(self):
        """Test collection manager initialization."""
        assert self.collection_manager.project_root == self.temp_dir
        assert self.collection_manager.storage_manager is not None
        assert self.collection_manager.metadata_parser is not None
        assert self.collection_manager.dependency_resolver is not None
    
    def create_test_collection(self, name: str = "test-collection") -> Path:
        """Create a test collection directory."""
        collection_dir = self.temp_dir / name
        collection_dir.mkdir()
        
        # Create pacc.json
        pacc_data = {
            "collection": {
                "name": name,
                "version": "1.0.0",
                "description": f"Test collection {name}",
                "files": ["fragment1", "fragment2"]
            }
        }
        (collection_dir / "pacc.json").write_text(json.dumps(pacc_data))
        
        # Create fragments
        (collection_dir / "fragment1.md").write_text("# Fragment 1")
        (collection_dir / "fragment2.md").write_text("# Fragment 2")
        
        return collection_dir
    
    def test_discover_collections(self):
        """Test discovering collections in directories."""
        # Create test collections
        collection1 = self.create_test_collection("collection1")
        collection2 = self.create_test_collection("collection2")
        
        # Discover collections
        collections = self.collection_manager.discover_collections([self.temp_dir])
        
        assert len(collections) == 2
        collection_names = [metadata.name for _, metadata in collections]
        assert "collection1" in collection_names
        assert "collection2" in collection_names
    
    def test_install_collection_dry_run(self):
        """Test collection installation in dry-run mode."""
        # Create test collection
        collection_dir = self.create_test_collection()
        
        # Install in dry-run mode
        options = CollectionInstallOptions(dry_run=True)
        result = self.collection_manager.install_collection(collection_dir, options)
        
        assert result.success is True
        assert result.collection_name == "test-collection"
        assert len(result.installed_files) == 2
        assert "fragment1" in result.installed_files
        assert "fragment2" in result.installed_files
        assert any("Would install" in change for change in result.changes_made)
    
    @patch('pacc.fragments.collection_manager.FragmentStorageManager')
    def test_install_collection_actual(self, mock_storage_class):
        """Test actual collection installation."""
        # Mock storage manager
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        mock_storage.store_fragment.return_value = Path("/fake/path")
        
        # Create test collection
        collection_dir = self.create_test_collection()
        
        # Install collection
        options = CollectionInstallOptions(dry_run=False)
        
        # Mock other managers
        with patch.object(self.collection_manager, 'version_tracker'), \
             patch.object(self.collection_manager, '_create_collection_backup', return_value={}), \
             patch.object(self.collection_manager, '_track_collection_installation'):
            
            result = self.collection_manager.install_collection(collection_dir, options)
        
        assert result.success is True
        assert result.collection_name == "test-collection"
        assert len(result.installed_files) == 2
        
        # Verify storage manager was called
        assert mock_storage.store_fragment.call_count == 2
    
    def test_install_collection_selective_files(self):
        """Test collection installation with selective files."""
        # Create test collection
        collection_dir = self.create_test_collection()
        
        # Install only one file
        options = CollectionInstallOptions(
            selected_files=["fragment1"],
            dry_run=True
        )
        result = self.collection_manager.install_collection(collection_dir, options)
        
        assert result.success is True
        assert len(result.installed_files) == 1
        assert "fragment1" in result.installed_files
        assert "fragment2" not in result.installed_files
    
    def test_install_collection_with_dependencies(self):
        """Test collection installation with dependencies."""
        # Create collection with dependencies
        collection_dir = self.temp_dir / "dependent-collection"
        collection_dir.mkdir()
        
        pacc_data = {
            "collection": {
                "name": "dependent-collection",
                "version": "1.0.0",
                "dependencies": ["missing-dep"],
                "files": ["fragment1"]
            }
        }
        (collection_dir / "pacc.json").write_text(json.dumps(pacc_data))
        (collection_dir / "fragment1.md").write_text("# Fragment 1")
        
        # Mock dependency resolver
        with patch.object(self.collection_manager.dependency_resolver, 'resolve_dependencies') as mock_resolve:
            mock_resolve.return_value = ["missing-dep"]
            
            options = CollectionInstallOptions(dry_run=True)
            result = self.collection_manager.install_collection(collection_dir, options)
        
        assert result.success is True
        assert "missing-dep" in result.dependencies_resolved
        assert any("Missing dependencies" in warning for warning in result.warnings)
    
    def test_verify_collection_integrity(self):
        """Test collection integrity verification."""
        # Create test collection
        collection_dir = self.create_test_collection()
        
        # Parse metadata to get checksum
        metadata = self.collection_manager.metadata_parser.parse_collection_metadata(collection_dir)
        
        # Verify integrity
        is_valid = self.collection_manager._verify_collection_integrity(collection_dir, metadata)
        assert is_valid is True
        
        # Modify a file and verify integrity fails
        (collection_dir / "fragment1.md").write_text("# Modified Fragment 1")
        is_valid = self.collection_manager._verify_collection_integrity(collection_dir, metadata)
        assert is_valid is False
    
    def test_get_collection_status_not_installed(self):
        """Test getting status of non-installed collection."""
        status = self.collection_manager.get_collection_status("non-existent")
        
        assert status["name"] == "non-existent"
        assert status["installed"] is False
        assert status["version"] is None
    
    def test_get_collection_status_installed(self):
        """Test getting status of installed collection."""
        # Create pacc.json with collection tracking
        pacc_json = self.temp_dir / "pacc.json"
        pacc_data = {
            "collections": {
                "test-collection": {
                    "version": "1.0.0",
                    "files": ["fragment1", "fragment2"],
                    "storage_type": "project",
                    "installed_at": "2023-01-01T00:00:00"
                }
            }
        }
        pacc_json.write_text(json.dumps(pacc_data))
        
        # Mock storage manager to return fragments
        with patch.object(self.collection_manager.storage_manager, 'list_fragments') as mock_list:
            mock_list.return_value = [
                Mock(name="fragment1"),
                Mock(name="fragment2")
            ]
            
            status = self.collection_manager.get_collection_status("test-collection")
        
        assert status["name"] == "test-collection"
        assert status["installed"] is True
        assert status["version"] == "1.0.0"
        assert status["storage_type"] == "project"
        assert status["files_count"] == 2
        assert status["integrity_valid"] is True  # No missing files
        assert len(status["missing_files"]) == 0
        assert len(status["extra_files"]) == 0
    
    def test_list_collections_with_metadata(self):
        """Test listing collections with metadata."""
        # Create pacc.json with collections
        pacc_json = self.temp_dir / "pacc.json"
        pacc_data = {
            "collections": {
                "collection1": {
                    "version": "1.0.0",
                    "description": "First collection",
                    "storage_type": "project"
                },
                "collection2": {
                    "version": "2.0.0",
                    "description": "Second collection",
                    "storage_type": "user"
                }
            }
        }
        pacc_json.write_text(json.dumps(pacc_data))
        
        # List all collections
        collections = self.collection_manager.list_collections_with_metadata()
        
        assert len(collections) == 2
        collection_names = [name for name, _ in collections]
        assert "collection1" in collection_names
        assert "collection2" in collection_names
        
        # Filter by storage type
        collections_project = self.collection_manager.list_collections_with_metadata("project")
        assert len(collections_project) == 1
        assert collections_project[0][0] == "collection1"
    
    def test_remove_collection(self):
        """Test collection removal."""
        # Mock storage manager
        with patch.object(self.collection_manager.storage_manager, 'remove_collection') as mock_remove, \
             patch.object(self.collection_manager, '_untrack_collection_installation') as mock_untrack:
            
            mock_remove.return_value = True
            
            success = self.collection_manager.remove_collection("test-collection")
        
        assert success is True
        mock_remove.assert_called_once_with("test-collection", "project", force=True)
        mock_untrack.assert_called_once_with("test-collection")
    
    def test_update_collection(self):
        """Test collection update."""
        # Create initial collection state
        pacc_json = self.temp_dir / "pacc.json"
        pacc_data = {
            "collections": {
                "test-collection": {
                    "version": "1.0.0",
                    "files": ["fragment1"],
                    "storage_type": "project"
                }
            }
        }
        pacc_json.write_text(json.dumps(pacc_data))
        
        # Create new version of collection
        new_collection_dir = self.temp_dir / "new-collection"
        new_collection_dir.mkdir()
        
        new_pacc_data = {
            "collection": {
                "name": "test-collection",
                "version": "2.0.0",
                "files": ["fragment1", "fragment2"]
            }
        }
        (new_collection_dir / "pacc.json").write_text(json.dumps(new_pacc_data))
        (new_collection_dir / "fragment1.md").write_text("# Updated Fragment 1")
        (new_collection_dir / "fragment2.md").write_text("# New Fragment 2")
        
        # Mock storage manager and install method
        with patch.object(self.collection_manager.storage_manager, 'list_collections') as mock_list, \
             patch.object(self.collection_manager, 'install_collection') as mock_install:
            
            mock_list.return_value = {"test-collection": ["fragment1"]}
            mock_install.return_value = CollectionInstallResult(
                success=True,
                collection_name="test-collection",
                installed_files=["fragment1", "fragment2"]
            )
            
            options = CollectionInstallOptions(dry_run=True)
            result = self.collection_manager.update_collection("test-collection", new_collection_dir, options)
        
        assert result.success is True
        assert result.collection_name == "test-collection"
        assert len(result.installed_files) == 2


if __name__ == "__main__":
    pytest.main([__file__])