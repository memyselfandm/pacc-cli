"""Tests for team collaboration features in PACC."""

import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
from datetime import datetime

# Import test modules
from pacc.core.project_config import (
    PluginSpec, 
    PluginSyncManager, 
    PluginSyncResult,
    ConflictResolution,
    ConfigSource,
    ProjectConfigManager,
    ProjectConfigSchema
)
from pacc.plugins.config import PluginConfigManager


class TestPluginSpec:
    """Test PluginSpec functionality."""
    
    def test_from_string_simple(self):
        """Test creating PluginSpec from simple string."""
        spec = PluginSpec.from_string("owner/repo")
        assert spec.repository == "owner/repo"
        assert spec.version is None
        assert spec.get_version_specifier() == "latest"
    
    def test_from_string_with_version(self):
        """Test creating PluginSpec from string with version."""
        spec = PluginSpec.from_string("owner/repo@v1.2.3")
        assert spec.repository == "owner/repo"
        assert spec.version == "v1.2.3"
        assert spec.get_version_specifier() == "v1.2.3"
    
    def test_from_dict(self):
        """Test creating PluginSpec from dictionary."""
        data = {
            "repository": "owner/repo",
            "version": "main",
            "plugins": ["plugin1", "plugin2"],
            "metadata": {"description": "Test repo"}
        }
        spec = PluginSpec.from_dict(data)
        assert spec.repository == "owner/repo"
        assert spec.version == "main"
        assert spec.plugins == ["plugin1", "plugin2"]
        assert spec.metadata["description"] == "Test repo"
    
    def test_version_component_parsing(self):
        """Test version component parsing."""
        # Test commit SHA
        spec = PluginSpec("owner/repo", "abcd1234567890123456789012345678901234567890")
        components = spec.parse_version_components()
        assert components['type'] == 'commit'
        
        # Test tag
        spec = PluginSpec("owner/repo", "v1.2.3")
        components = spec.parse_version_components()
        assert components['type'] == 'tag'
        
        # Test branch
        spec = PluginSpec("owner/repo", "main")
        components = spec.parse_version_components()
        assert components['type'] == 'branch'
    
    def test_version_locking(self):
        """Test version locking detection."""
        # Dynamic refs should not be locked
        spec = PluginSpec("owner/repo", "latest")
        assert not spec.is_version_locked()
        
        spec = PluginSpec("owner/repo", "main")
        assert not spec.is_version_locked()
        
        # Specific versions should be locked
        spec = PluginSpec("owner/repo", "v1.2.3")
        assert spec.is_version_locked()
        
        spec = PluginSpec("owner/repo", "abcd1234")
        assert spec.is_version_locked()
    
    def test_git_ref_generation(self):
        """Test Git reference generation."""
        spec = PluginSpec("owner/repo", "v1.2.3")
        assert spec.get_git_ref() == "v1.2.3"
        
        spec = PluginSpec("owner/repo", "latest")
        assert spec.get_git_ref() == "HEAD"
        
        spec = PluginSpec("owner/repo", "main")
        assert spec.get_git_ref() == "main"


class TestProjectConfigSchema:
    """Test project configuration schema validation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.schema = ProjectConfigSchema()
    
    def test_valid_plugins_configuration(self):
        """Test validation of valid plugins configuration."""
        config = {
            "name": "test-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": [
                    "owner/repo@v1.0.0",
                    {
                        "repository": "another/repo",
                        "version": "main"
                    }
                ],
                "required": ["plugin1", "plugin2"],
                "optional": ["plugin3"]
            }
        }
        
        result = self.schema.validate(config)
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_invalid_repository_format(self):
        """Test validation of invalid repository format."""
        config = {
            "name": "test-project", 
            "version": "1.0.0",
            "plugins": {
                "repositories": [
                    "invalid-repo-format",  # Missing owner/repo structure
                    42  # Wrong type
                ]
            }
        }
        
        result = self.schema.validate(config)
        assert not result.is_valid
        assert len(result.errors) >= 2
    
    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        config = {
            "plugins": {
                "repositories": ["owner/repo"]
            }
        }
        
        result = self.schema.validate(config)
        assert not result.is_valid
        # Should have errors for missing name and version
        error_codes = [error.code for error in result.errors]
        assert "MISSING_REQUIRED_FIELD" in error_codes
    
    def test_invalid_plugin_lists(self):
        """Test validation of invalid plugin lists."""
        config = {
            "name": "test-project",
            "version": "1.0.0", 
            "plugins": {
                "repositories": ["owner/repo"],
                "required": "not-a-list",  # Should be array
                "optional": [123, 456]     # Should be strings
            }
        }
        
        result = self.schema.validate(config)
        assert not result.is_valid
        error_codes = [error.code for error in result.errors]
        assert "INVALID_REQUIRED_PLUGINS" in error_codes
        assert "INVALID_OPTIONAL_PLUGIN_NAME" in error_codes


class TestConflictResolution:
    """Test conflict resolution functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sync_manager = PluginSyncManager()
    
    def test_version_conflict_detection(self):
        """Test detection of version conflicts."""
        sources = [
            ConfigSource(
                name="team",
                path=Path("/team/pacc.json"),
                config={
                    "plugins": {
                        "repositories": ["owner/repo@v1.0.0"]
                    }
                },
                priority=10
            ),
            ConfigSource(
                name="local",
                path=Path("/local/pacc.local.json"),
                config={
                    "plugins": {
                        "repositories": ["owner/repo@v1.1.0"]
                    }
                },
                priority=20,
                is_local=True
            )
        ]
        
        merged_config, conflicts = self.sync_manager._merge_plugin_configs(sources, None)
        
        assert len(conflicts) == 1
        assert "Version conflict for owner/repo" in conflicts[0]
        assert "v1.0.0" in conflicts[0]
        assert "v1.1.0" in conflicts[0]
    
    def test_semantic_version_comparison(self):
        """Test semantic version comparison."""
        # Test basic comparison
        result = self.sync_manager._compare_semantic_versions("1.2.3", "1.2.4")
        assert result == -1  # 1.2.3 < 1.2.4
        
        result = self.sync_manager._compare_semantic_versions("2.0.0", "1.9.9")
        assert result == 1   # 2.0.0 > 1.9.9
        
        result = self.sync_manager._compare_semantic_versions("1.0.0", "1.0.0")
        assert result == 0   # 1.0.0 == 1.0.0
        
        # Test with 'v' prefix
        result = self.sync_manager._compare_semantic_versions("v1.2.3", "1.2.4")
        assert result == -1
    
    def test_conflict_resolution_strategies(self):
        """Test different conflict resolution strategies."""
        # Test "local" strategy
        resolution = ConflictResolution(strategy="local")
        resolved = self.sync_manager._resolve_version_conflict(
            "owner/repo", "v1.0.0", "v1.1.0", "team", "local", resolution
        )
        assert resolved == "v1.1.0"  # Should prefer local
        
        # Test "team" strategy
        resolution = ConflictResolution(strategy="team")
        resolved = self.sync_manager._resolve_version_conflict(
            "owner/repo", "v1.0.0", "v1.1.0", "team", "local", resolution
        )
        assert resolved == "v1.0.0"  # Should prefer team
        
        # Test "merge" strategy (should prefer higher version)
        resolution = ConflictResolution(strategy="merge")
        resolved = self.sync_manager._resolve_version_conflict(
            "owner/repo", "v1.0.0", "v1.1.0", "team", "local", resolution
        )
        assert resolved == "v1.1.0"  # Should prefer higher version
    
    def test_preferred_version_selection(self):
        """Test preferred version selection heuristics."""
        # Local source should always win
        result = self.sync_manager._choose_preferred_version(
            "v1.0.0", "v1.1.0", "team", "local"
        )
        assert result == "v1.1.0"
        
        # Specific version should beat dynamic
        result = self.sync_manager._choose_preferred_version(
            "latest", "v1.2.3", "team", "global"
        )
        assert result == "v1.2.3"
        
        # Higher version should win
        result = self.sync_manager._choose_preferred_version(
            "v1.0.0", "v1.1.0", "team", "global"
        )
        assert result == "v1.1.0"


class TestPluginSyncManager:
    """Test plugin synchronization manager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.sync_manager = PluginSyncManager()
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_config_source_discovery(self):
        """Test discovery of configuration sources."""
        # Create test configuration files
        (self.temp_dir / "pacc.json").write_text(json.dumps({
            "name": "test-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": ["team/repo@v1.0.0"]
            }
        }))
        
        (self.temp_dir / "pacc.local.json").write_text(json.dumps({
            "plugins": {
                "repositories": ["local/repo@v1.1.0"]
            }
        }))
        
        sources = self.sync_manager._discover_config_sources(self.temp_dir, "default")
        
        assert len(sources) >= 2
        source_names = [s.name for s in sources]
        assert "team" in source_names
        assert "local" in source_names
        
        # Local should have higher priority
        local_source = next(s for s in sources if s.name == "local")
        team_source = next(s for s in sources if s.name == "team")
        assert local_source.priority > team_source.priority
    
    @patch('pacc.core.project_config.PluginSyncManager._get_plugin_manager')
    def test_plugin_sync_dry_run(self, mock_get_manager):
        """Test plugin sync in dry-run mode."""
        # Mock plugin manager
        mock_manager = Mock()
        mock_manager.list_installed_repositories.return_value = {}
        mock_get_manager.return_value = mock_manager
        
        # Create test config
        (self.temp_dir / "pacc.json").write_text(json.dumps({
            "name": "test-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": ["owner/repo@v1.0.0"],
                "required": ["plugin1"]
            }
        }))
        
        result = self.sync_manager.sync_plugins(
            project_dir=self.temp_dir,
            dry_run=True
        )
        
        assert result.success
        # In dry-run, should not actually install anything
        assert mock_manager.install_repository.call_count == 0
    
    @patch('pacc.core.project_config.PluginSyncManager._get_plugin_manager')
    @patch('pacc.core.project_config.PluginSyncManager._resolve_version_to_commit')
    def test_differential_sync(self, mock_resolve_version, mock_get_manager):
        """Test differential sync behavior."""
        # Mock plugin manager
        mock_manager = Mock()
        mock_manager.list_installed_repositories.return_value = {
            "owner/repo": {"version": "abc123"}  # Already installed
        }
        mock_get_manager.return_value = mock_manager
        
        # Mock version resolution
        mock_resolve_version.return_value = "def456"  # Different commit
        
        # Mock _get_current_commit to return different commit
        with patch.object(self.sync_manager, '_get_current_commit', return_value="abc123"):
            # Mock successful checkout
            with patch.object(self.sync_manager, '_checkout_version', return_value=True):
                # Create test config
                (self.temp_dir / "pacc.json").write_text(json.dumps({
                    "name": "test-project",
                    "version": "1.0.0",
                    "plugins": {
                        "repositories": ["owner/repo@v1.1.0"]
                    }
                }))
                
                result = self.sync_manager.sync_plugins(project_dir=self.temp_dir)
                
                # Should detect difference and update
                assert result.updated_count > 0 or result.installed_count > 0
    
    def test_repository_spec_parsing(self):
        """Test parsing of repository specifications."""
        # Test string format
        spec = self.sync_manager._parse_single_repository("owner/repo@v1.0.0")
        assert spec.repository == "owner/repo"
        assert spec.version == "v1.0.0"
        
        # Test dict format
        spec = self.sync_manager._parse_single_repository({
            "repository": "owner/repo",
            "version": "main",
            "plugins": ["plugin1"]
        })
        assert spec.repository == "owner/repo"
        assert spec.version == "main"
        assert "plugin1" in spec.plugins
        
        # Test invalid format
        spec = self.sync_manager._parse_single_repository(123)
        assert spec is None


class TestPluginConfigManager:
    """Test plugin configuration manager integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config_manager = PluginConfigManager(
            plugins_dir=self.temp_dir / "plugins",
            settings_path=self.temp_dir / "settings.json"
        )
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_repository_installation(self):
        """Test repository installation."""
        spec = PluginSpec("owner/repo", "v1.0.0", ["plugin1"])
        
        success = self.config_manager.install_repository(spec)
        
        assert success
        
        # Check that repository was added to config
        repositories = self.config_manager.list_installed_repositories()
        assert "owner/repo" in repositories
        assert repositories["owner/repo"]["version"] == "v1.0.0"
    
    def test_repository_update(self):
        """Test repository update."""
        # First install
        spec = PluginSpec("owner/repo", "v1.0.0")
        self.config_manager.install_repository(spec)
        
        # Then update
        success = self.config_manager.update_repository("owner/repo", "v1.1.0")
        
        assert success
        
        # Check updated version
        repositories = self.config_manager.list_installed_repositories()
        assert repositories["owner/repo"]["version"] == "v1.1.0"
    
    def test_plugin_enablement(self):
        """Test plugin enable/disable functionality."""
        # Install repository first
        spec = PluginSpec("owner/repo", "v1.0.0", ["plugin1"])
        self.config_manager.install_repository(spec)
        
        # Enable plugin
        success = self.config_manager.enable_plugin("owner/repo", "plugin1")
        assert success
        
        # Check settings
        settings = self.config_manager._load_settings()
        assert "enabledPlugins" in settings
        assert "owner/repo" in settings["enabledPlugins"]
        assert "plugin1" in settings["enabledPlugins"]["owner/repo"]
        
        # Disable plugin
        success = self.config_manager.disable_plugin("owner/repo", "plugin1")
        assert success
        
        # Check settings updated
        settings = self.config_manager._load_settings()
        assert "owner/repo" not in settings.get("enabledPlugins", {})


class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.sync_manager = PluginSyncManager()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    @patch('pacc.core.project_config.PluginSyncManager._get_plugin_manager')
    def test_complete_team_sync_workflow(self, mock_get_manager):
        """Test complete team synchronization workflow."""
        # Mock plugin manager
        mock_manager = Mock()
        mock_manager.list_installed_repositories.return_value = {}
        mock_manager.install_repository.return_value = True
        mock_manager.enable_plugin.return_value = True
        mock_get_manager.return_value = mock_manager
        
        # Create team configuration
        team_config = {
            "name": "team-project",
            "version": "1.0.0",
            "plugins": {
                "repositories": [
                    "team/hooks@v1.0.0",
                    {
                        "repository": "team/agents",
                        "version": "main",
                        "plugins": ["agent1", "agent2"]
                    }
                ],
                "required": ["agent1"],
                "optional": ["agent2"]
            }
        }
        
        (self.temp_dir / "pacc.json").write_text(json.dumps(team_config))
        
        # Create local override
        local_config = {
            "plugins": {
                "repositories": ["local/dev-tools@latest"],
                "optional": ["dev-plugin"]
            }
        }
        
        (self.temp_dir / "pacc.local.json").write_text(json.dumps(local_config))
        
        # Perform sync with conflict resolution
        conflict_resolution = ConflictResolution(strategy="merge")
        result = self.sync_manager.sync_plugins_with_conflict_resolution(
            project_dir=self.temp_dir,
            conflict_resolution=conflict_resolution
        )
        
        assert result.success
        
        # Should have installed repositories from both team and local configs
        assert mock_manager.install_repository.call_count >= 2
        
        # Should have enabled required plugins
        assert mock_manager.enable_plugin.called
    
    def test_version_locking_workflow(self):
        """Test version locking and specific commit checkout."""
        # This would require actual Git operations in full implementation
        # For now, test the version resolution logic
        
        spec = PluginSpec("owner/repo", "v1.2.3")
        assert spec.is_version_locked()
        
        version_info = spec.parse_version_components()
        assert version_info['type'] == 'tag'
        assert version_info['ref'] == 'v1.2.3'
        
        git_ref = spec.get_git_ref()
        assert git_ref == "v1.2.3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])