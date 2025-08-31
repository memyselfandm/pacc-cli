"""Unit tests for Fragment Version Tracker."""

import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest

from pacc.fragments.version_tracker import FragmentVersionTracker, FragmentVersion


class TestFragmentVersionTracker:
    """Test suite for FragmentVersionTracker."""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        return project_dir
    
    def test_init(self, temp_project):
        """Test version tracker initialization."""
        tracker = FragmentVersionTracker(project_root=temp_project)
        assert tracker.project_root == temp_project
        assert tracker.version_file == temp_project / ".pacc/fragment_versions.json"
        assert tracker.versions == {}
    
    def test_load_versions_no_file(self, temp_project):
        """Test loading versions when file doesn't exist."""
        tracker = FragmentVersionTracker(project_root=temp_project)
        versions = tracker._load_versions()
        assert versions == {}
    
    def test_load_versions_with_file(self, temp_project):
        """Test loading versions from existing file."""
        # Create version file
        version_file = temp_project / ".pacc/fragment_versions.json"
        version_file.parent.mkdir(parents=True)
        
        version_data = {
            "test_fragment": {
                "version_id": "abc12345",
                "source_type": "git",
                "timestamp": datetime.now().isoformat(),
                "source_url": "https://github.com/test/repo.git",
                "commit_message": "Initial commit",
                "author": "Test Author"
            }
        }
        version_file.write_text(json.dumps(version_data))
        
        tracker = FragmentVersionTracker(project_root=temp_project)
        
        assert "test_fragment" in tracker.versions
        assert tracker.versions["test_fragment"].version_id == "abc12345"
        assert tracker.versions["test_fragment"].source_type == "git"
    
    def test_save_versions(self, temp_project):
        """Test saving versions to file."""
        tracker = FragmentVersionTracker(project_root=temp_project)
        
        # Add a version
        version = FragmentVersion(
            version_id="def67890",
            source_type="url",
            timestamp=datetime.now(),
            source_url="https://example.com/fragment.md"
        )
        tracker.versions["new_fragment"] = version
        
        # Save
        tracker._save_versions()
        
        # Verify file was created
        version_file = temp_project / ".pacc/fragment_versions.json"
        assert version_file.exists()
        
        # Load and verify content
        data = json.loads(version_file.read_text())
        assert "new_fragment" in data
        assert data["new_fragment"]["version_id"] == "def67890"
    
    @patch('subprocess.run')
    def test_track_installation_git(self, mock_run, temp_project):
        """Test tracking Git source installation."""
        tracker = FragmentVersionTracker(project_root=temp_project)
        
        # Create test fragment
        fragment_path = temp_project / "test_fragment.md"
        fragment_path.write_text("# Test Fragment")
        
        # Mock git commands
        mock_run.side_effect = [
            Mock(returncode=0, stdout="abc123456789\n"),  # git rev-parse HEAD
            Mock(returncode=0, stdout="Initial commit\n"),  # git log -1 --pretty=%s
            Mock(returncode=0, stdout="Test Author\n")  # git log -1 --pretty=%an
        ]
        
        version = tracker.track_installation(
            "test_fragment",
            "https://github.com/test/repo.git",
            "git",
            fragment_path
        )
        
        assert version.version_id == "abc12345"  # Short SHA
        assert version.source_type == "git"
        assert version.commit_message == "Initial commit"
        assert version.author == "Test Author"
        assert "test_fragment" in tracker.versions
    
    def test_track_installation_url(self, temp_project):
        """Test tracking URL source installation."""
        tracker = FragmentVersionTracker(project_root=temp_project)
        
        # Create test fragment
        fragment_path = temp_project / "test_fragment.md"
        fragment_path.write_text("# Test Fragment")
        
        version = tracker.track_installation(
            "test_fragment",
            "https://example.com/fragment.md",
            "url",
            fragment_path
        )
        
        assert len(version.version_id) == 8  # Short hash
        assert version.source_type == "url"
        assert version.source_url == "https://example.com/fragment.md"
        assert "test_fragment" in tracker.versions
    
    def test_calculate_content_hash(self, temp_project):
        """Test content hash calculation."""
        tracker = FragmentVersionTracker(project_root=temp_project)
        
        # Create test file
        test_file = temp_project / "test.txt"
        test_file.write_text("Test content")
        
        hash_id = tracker._calculate_content_hash(test_file)
        
        assert len(hash_id) == 8
        assert hash_id.isalnum()
    
    def test_get_version(self, temp_project):
        """Test getting version information."""
        tracker = FragmentVersionTracker(project_root=temp_project)
        
        # Add a version
        version = FragmentVersion(
            version_id="abc12345",
            source_type="git",
            timestamp=datetime.now()
        )
        tracker.versions["test_fragment"] = version
        
        # Get existing version
        retrieved = tracker.get_version("test_fragment")
        assert retrieved == version
        
        # Get non-existent version
        assert tracker.get_version("nonexistent") is None
    
    def test_has_update(self, temp_project):
        """Test checking for updates."""
        tracker = FragmentVersionTracker(project_root=temp_project)
        
        # Add a version
        version = FragmentVersion(
            version_id="abc12345",
            source_type="git",
            timestamp=datetime.now()
        )
        tracker.versions["test_fragment"] = version
        
        # Check with same version
        assert tracker.has_update("test_fragment", "abc12345") is False
        
        # Check with different version
        assert tracker.has_update("test_fragment", "def67890") is True
        
        # Check non-existent fragment
        assert tracker.has_update("nonexistent", "any") is False
    
    def test_update_version(self, temp_project):
        """Test updating version information."""
        tracker = FragmentVersionTracker(project_root=temp_project)
        
        # Add initial version
        old_version = FragmentVersion(
            version_id="abc12345",
            source_type="git",
            timestamp=datetime.now()
        )
        tracker.versions["test_fragment"] = old_version
        
        # Update version
        new_version = FragmentVersion(
            version_id="def67890",
            source_type="git",
            timestamp=datetime.now()
        )
        tracker.update_version("test_fragment", new_version)
        
        assert tracker.versions["test_fragment"].version_id == "def67890"
    
    def test_remove_version(self, temp_project):
        """Test removing version tracking."""
        tracker = FragmentVersionTracker(project_root=temp_project)
        
        # Add a version
        version = FragmentVersion(
            version_id="abc12345",
            source_type="git",
            timestamp=datetime.now()
        )
        tracker.versions["test_fragment"] = version
        
        # Remove it
        tracker.remove_version("test_fragment")
        
        assert "test_fragment" not in tracker.versions
        
        # Remove non-existent (should not error)
        tracker.remove_version("nonexistent")
    
    def test_fragment_version_to_dict(self):
        """Test FragmentVersion to_dict method."""
        version = FragmentVersion(
            version_id="abc12345",
            source_type="git",
            timestamp=datetime.now(),
            source_url="https://github.com/test/repo.git",
            commit_message="Test commit",
            author="Test Author"
        )
        
        data = version.to_dict()
        
        assert data["version_id"] == "abc12345"
        assert data["source_type"] == "git"
        assert "timestamp" in data
        assert data["source_url"] == "https://github.com/test/repo.git"
        assert data["commit_message"] == "Test commit"
        assert data["author"] == "Test Author"
    
    def test_fragment_version_from_dict(self):
        """Test FragmentVersion from_dict method."""
        data = {
            "version_id": "abc12345",
            "source_type": "git",
            "timestamp": datetime.now().isoformat(),
            "source_url": "https://github.com/test/repo.git",
            "commit_message": "Test commit",
            "author": "Test Author"
        }
        
        version = FragmentVersion.from_dict(data)
        
        assert version.version_id == "abc12345"
        assert version.source_type == "git"
        assert isinstance(version.timestamp, datetime)
        assert version.source_url == "https://github.com/test/repo.git"
        assert version.commit_message == "Test commit"
        assert version.author == "Test Author"