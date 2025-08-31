"""Unit tests for Fragment Sync Manager."""

import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest

from pacc.fragments.sync_manager import (
    FragmentSyncManager,
    FragmentSyncSpec,
    SyncConflict,
    SyncResult
)


class TestFragmentSyncManager:
    """Test suite for FragmentSyncManager."""
    
    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        
        # Create pacc.json with fragment specs
        pacc_json = {
            "fragmentSpecs": {
                "test_fragment": {
                    "source": "https://github.com/test/repo.git",
                    "version": "v1.0.0",
                    "storageType": "project"
                },
                "another_fragment": {
                    "source": "https://example.com/fragment.md",
                    "required": False,
                    "collection": "utils"
                }
            },
            "fragments": {
                "test_fragment": {
                    "title": "Test Fragment",
                    "reference_path": ".claude/pacc/fragments/test_fragment.md",
                    "storage_type": "project",
                    "version": "v0.9.0",
                    "source_url": "https://github.com/test/repo.git"
                }
            }
        }
        
        pacc_json_path = project_dir / "pacc.json"
        pacc_json_path.write_text(json.dumps(pacc_json, indent=2))
        
        return project_dir
    
    def test_init(self, temp_project):
        """Test sync manager initialization."""
        manager = FragmentSyncManager(project_root=temp_project)
        assert manager.project_root == temp_project
        assert manager.storage_manager is not None
        assert manager.installation_manager is not None
    
    def test_load_sync_specifications(self, temp_project):
        """Test loading sync specifications from pacc.json."""
        manager = FragmentSyncManager(project_root=temp_project)
        specs = manager.load_sync_specifications()
        
        assert len(specs) == 2
        
        # Check first spec
        test_spec = next(s for s in specs if s.name == "test_fragment")
        assert test_spec.source == "https://github.com/test/repo.git"
        assert test_spec.version == "v1.0.0"
        assert test_spec.storage_type == "project"
        assert test_spec.required is True
        
        # Check second spec
        another_spec = next(s for s in specs if s.name == "another_fragment")
        assert another_spec.source == "https://example.com/fragment.md"
        assert another_spec.required is False
        assert another_spec.collection == "utils"
    
    def test_load_sync_specifications_no_file(self, tmp_path):
        """Test loading specs when pacc.json doesn't exist."""
        manager = FragmentSyncManager(project_root=tmp_path)
        specs = manager.load_sync_specifications()
        assert specs == []
    
    def test_save_sync_specifications(self, temp_project):
        """Test saving sync specifications to pacc.json."""
        manager = FragmentSyncManager(project_root=temp_project)
        
        specs = [
            FragmentSyncSpec(
                name="new_fragment",
                source="https://github.com/new/repo.git",
                version="v2.0.0",
                required=True,
                storage_type="user"
            )
        ]
        
        manager.save_sync_specifications(specs)
        
        # Verify saved content
        pacc_json_path = temp_project / "pacc.json"
        config = json.loads(pacc_json_path.read_text())
        
        assert "fragmentSpecs" in config
        assert "new_fragment" in config["fragmentSpecs"]
        assert config["fragmentSpecs"]["new_fragment"]["source"] == "https://github.com/new/repo.git"
        assert config["fragmentSpecs"]["new_fragment"]["version"] == "v2.0.0"
        assert config["fragmentSpecs"]["new_fragment"]["storageType"] == "user"
    
    def test_detect_conflicts_version_mismatch(self, temp_project):
        """Test detecting version conflicts."""
        manager = FragmentSyncManager(project_root=temp_project)
        
        specs = [
            FragmentSyncSpec(
                name="test_fragment",
                source="https://github.com/test/repo.git",
                version="v1.0.0",
                required=True,
                storage_type="project"
            )
        ]
        
        installed = {
            "test_fragment": {
                "version": "v0.9.0",
                "source_url": "https://github.com/test/repo.git"
            }
        }
        
        conflicts = manager.detect_conflicts(specs, installed)
        
        assert len(conflicts) == 1
        assert conflicts[0].fragment_name == "test_fragment"
        assert conflicts[0].conflict_type == "version"
        assert conflicts[0].local_version == "v0.9.0"
        assert conflicts[0].remote_version == "v1.0.0"
    
    def test_detect_conflicts_source_mismatch(self, temp_project):
        """Test detecting source conflicts."""
        manager = FragmentSyncManager(project_root=temp_project)
        
        specs = [
            FragmentSyncSpec(
                name="test_fragment",
                source="https://github.com/new/repo.git",
                version=None,
                required=True,
                storage_type="project"
            )
        ]
        
        installed = {
            "test_fragment": {
                "source_url": "https://github.com/old/repo.git"
            }
        }
        
        conflicts = manager.detect_conflicts(specs, installed)
        
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "source"
    
    def test_sync_fragments_dry_run(self, temp_project):
        """Test dry run sync."""
        manager = FragmentSyncManager(project_root=temp_project)
        
        with patch.object(manager, 'load_sync_specifications') as mock_load:
            mock_load.return_value = [
                FragmentSyncSpec(
                    name="new_fragment",
                    source="https://github.com/new/repo.git",
                    version="v1.0.0",
                    required=True,
                    storage_type="project"
                )
            ]
            
            with patch.object(manager, '_get_installed_fragments') as mock_installed:
                mock_installed.return_value = {}
                
                result = manager.sync_fragments(
                    interactive=False,
                    dry_run=True,
                    add_missing=True
                )
                
                assert result.dry_run is True
                assert result.added_count == 1
                assert "Would add: new_fragment" in result.changes_made[0]
    
    def test_sync_fragments_add_missing(self, temp_project):
        """Test adding missing fragments during sync."""
        manager = FragmentSyncManager(project_root=temp_project)
        
        with patch.object(manager, 'load_sync_specifications') as mock_load:
            mock_load.return_value = [
                FragmentSyncSpec(
                    name="new_fragment",
                    source="test_source",
                    version=None,
                    required=True,
                    storage_type="project"
                )
            ]
            
            with patch.object(manager, '_get_installed_fragments') as mock_installed:
                mock_installed.return_value = {}
                
                with patch.object(manager.installation_manager, 'install_from_source') as mock_install:
                    mock_install.return_value = Mock(success=True, error_message="")
                    
                    result = manager.sync_fragments(
                        interactive=False,
                        force=True,
                        dry_run=False,
                        add_missing=True
                    )
                    
                    assert result.added_count == 1
                    assert mock_install.called
    
    # TODO: Fix this test - it's not properly testing the remove_extra functionality
    # def test_sync_fragments_remove_extra(self, tmp_path):
    #     """Test removing extra fragments during sync."""
    #     pass
    
    def test_add_fragment_spec(self, temp_project):
        """Test adding a fragment specification."""
        manager = FragmentSyncManager(project_root=temp_project)
        
        manager.add_fragment_spec(
            name="new_spec",
            source="https://github.com/new/spec.git",
            version="v1.2.3",
            required=True,
            storage_type="project"
        )
        
        # Verify it was added
        specs = manager.load_sync_specifications()
        new_spec = next((s for s in specs if s.name == "new_spec"), None)
        
        assert new_spec is not None
        assert new_spec.source == "https://github.com/new/spec.git"
        assert new_spec.version == "v1.2.3"
    
    def test_remove_fragment_spec(self, temp_project):
        """Test removing a fragment specification."""
        manager = FragmentSyncManager(project_root=temp_project)
        
        # First add a spec
        manager.add_fragment_spec(
            name="to_remove",
            source="test_source",
            version=None,
            required=True,
            storage_type="project"
        )
        
        # Remove it
        removed = manager.remove_fragment_spec("to_remove")
        assert removed is True
        
        # Verify it's gone
        specs = manager.load_sync_specifications()
        assert not any(s.name == "to_remove" for s in specs)
        
        # Try removing non-existent
        removed = manager.remove_fragment_spec("nonexistent")
        assert removed is False
    
    def test_resolve_conflicts_interactive(self, temp_project):
        """Test interactive conflict resolution."""
        manager = FragmentSyncManager(project_root=temp_project)
        
        conflicts = [
            SyncConflict(
                fragment_name="test",
                conflict_type="version",
                local_version="v1.0",
                remote_version="v2.0",
                description="Version mismatch",
                resolution_options=["keep_local", "use_spec", "merge"]
            )
        ]
        
        with patch('builtins.input', return_value='1'):
            with patch('builtins.print'):
                resolutions = manager._resolve_conflicts_interactive(conflicts)
                
        assert resolutions["test"] == "keep_local"