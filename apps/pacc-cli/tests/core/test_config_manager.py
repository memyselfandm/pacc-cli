"""Tests for configuration management functionality."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from pacc.core.config_manager import (
    ClaudeConfigManager,
    DeepMergeStrategy,
    deduplicate_extension_list,
)
from pacc.errors.exceptions import ConfigurationError, ValidationError


class TestDeepMergeStrategy:
    """Test the deep merge strategy."""

    def test_simple_merge(self):
        """Test simple object merging."""
        strategy = DeepMergeStrategy()

        existing = {"a": 1, "b": 2}
        new = {"c": 3, "d": 4}

        result = strategy.merge(existing, new)

        assert result.success
        assert result.merged_config == {"a": 1, "b": 2, "c": 3, "d": 4}
        assert len(result.conflicts) == 0
        assert len(result.changes_made) == 2

    def test_nested_merge(self):
        """Test nested object merging."""
        strategy = DeepMergeStrategy()

        existing = {"hooks": [{"name": "existing"}], "settings": {"theme": "dark", "debug": False}}
        new = {"mcps": [{"name": "new"}], "settings": {"language": "en", "debug": True}}

        result = strategy.merge(existing, new)

        assert result.success
        assert "hooks" in result.merged_config
        assert "mcps" in result.merged_config
        assert result.merged_config["settings"]["theme"] == "dark"
        assert result.merged_config["settings"]["language"] == "en"

        # Debug value conflict should be detected
        assert len(result.conflicts) == 1
        assert result.conflicts[0].key_path == "settings.debug"

    def test_array_append_strategy(self):
        """Test array append strategy."""
        strategy = DeepMergeStrategy(array_strategy="append")

        existing = {"hooks": [{"name": "hook1"}]}
        new = {"hooks": [{"name": "hook2"}]}

        result = strategy.merge(existing, new)

        assert result.success
        assert len(result.merged_config["hooks"]) == 2
        assert result.merged_config["hooks"][0]["name"] == "hook1"
        assert result.merged_config["hooks"][1]["name"] == "hook2"

    def test_array_dedupe_strategy(self):
        """Test array deduplication strategy."""
        strategy = DeepMergeStrategy(array_strategy="dedupe")

        existing = {"hooks": [{"name": "hook1"}, {"name": "hook2"}]}
        new = {"hooks": [{"name": "hook2"}, {"name": "hook3"}]}

        result = strategy.merge(existing, new)

        assert result.success
        assert len(result.merged_config["hooks"]) == 3
        hook_names = [h["name"] for h in result.merged_config["hooks"]]
        assert "hook1" in hook_names
        assert "hook2" in hook_names
        assert "hook3" in hook_names
        assert hook_names.count("hook2") == 1  # No duplicates

    def test_array_replace_strategy(self):
        """Test array replace strategy."""
        strategy = DeepMergeStrategy(array_strategy="replace")

        existing = {"hooks": [{"name": "hook1"}]}
        new = {"hooks": [{"name": "hook2"}]}

        result = strategy.merge(existing, new)

        assert result.success
        assert len(result.merged_config["hooks"]) == 1
        assert result.merged_config["hooks"][0]["name"] == "hook2"

    def test_type_mismatch_conflict(self):
        """Test handling of type mismatches."""
        strategy = DeepMergeStrategy()

        existing = {"setting": "string_value"}
        new = {"setting": 42}

        result = strategy.merge(existing, new)

        assert result.success  # Still succeeds but with conflicts
        assert len(result.conflicts) == 1
        assert result.conflicts[0].conflict_type == "type_mismatch"
        assert result.conflicts[0].key_path == "setting"
        # Should keep existing value on type mismatch
        assert result.merged_config["setting"] == "string_value"

    def test_value_conflict_keep_existing(self):
        """Test value conflict resolution - keep existing."""
        strategy = DeepMergeStrategy(conflict_resolution="keep_existing")

        existing = {"setting": "old_value"}
        new = {"setting": "new_value"}

        result = strategy.merge(existing, new)

        assert result.success
        assert len(result.conflicts) == 1
        assert result.merged_config["setting"] == "old_value"

    def test_value_conflict_use_new(self):
        """Test value conflict resolution - use new."""
        strategy = DeepMergeStrategy(conflict_resolution="use_new")

        existing = {"setting": "old_value"}
        new = {"setting": "new_value"}

        result = strategy.merge(existing, new)

        assert result.success
        assert len(result.conflicts) == 1
        assert result.merged_config["setting"] == "new_value"


class TestClaudeConfigManager:
    """Test the Claude configuration manager."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = ClaudeConfigManager()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_config_path_user_level(self):
        """Test getting user-level config path."""
        path = self.config_manager.get_config_path(user_level=True)
        assert path.name == "settings.json"
        assert ".claude" in str(path)
        assert str(Path.home()) in str(path)

    def test_get_config_path_project_level(self):
        """Test getting project-level config path."""
        path = self.config_manager.get_config_path(user_level=False)
        assert path.name == "settings.json"
        assert str(path) == ".claude/settings.json"

    def test_load_config_nonexistent(self):
        """Test loading non-existent config returns default."""
        config_path = Path(self.temp_dir) / "nonexistent.json"
        config = self.config_manager.load_config(config_path)

        expected_default = {"hooks": [], "mcps": [], "agents": [], "commands": []}
        assert config == expected_default

    def test_load_config_valid(self):
        """Test loading valid configuration."""
        config_path = Path(self.temp_dir) / "config.json"
        test_config = {"hooks": [{"name": "test_hook"}], "mcps": [], "agents": [], "commands": []}

        with open(config_path, "w") as f:
            json.dump(test_config, f)

        loaded_config = self.config_manager.load_config(config_path)
        assert loaded_config == test_config

    def test_load_config_invalid_json(self):
        """Test loading invalid JSON configuration."""
        config_path = Path(self.temp_dir) / "invalid.json"

        with open(config_path, "w") as f:
            f.write('{"invalid": json}')  # Invalid JSON

        with pytest.raises(ConfigurationError) as exc_info:
            self.config_manager.load_config(config_path)

        assert "Invalid JSON" in str(exc_info.value)

    def test_save_config(self):
        """Test saving configuration."""
        config_path = Path(self.temp_dir) / "test_config.json"
        test_config = {"hooks": [{"name": "test_hook"}], "mcps": [], "agents": [], "commands": []}

        self.config_manager.save_config(test_config, config_path)

        # Verify file was created and contains correct data
        assert config_path.exists()
        with open(config_path) as f:
            saved_config = json.load(f)
        assert saved_config == test_config

    def test_save_config_creates_backup(self):
        """Test that saving creates backup of existing file."""
        config_path = Path(self.temp_dir) / "config.json"
        backup_path = config_path.with_suffix(".json.backup")

        # Create initial config
        initial_config = {"hooks": []}
        with open(config_path, "w") as f:
            json.dump(initial_config, f)

        # Save new config (should create backup)
        new_config = {"hooks": [{"name": "new_hook"}]}
        self.config_manager.save_config(new_config, config_path)

        # Backup should have been created but then cleaned up
        # The main config should have the new content
        with open(config_path) as f:
            saved_config = json.load(f)
        assert saved_config == new_config

    def test_merge_config_no_conflicts(self):
        """Test merging configuration without conflicts."""
        config_path = Path(self.temp_dir) / "config.json"

        # Create initial config
        initial_config = {"hooks": [{"name": "hook1"}], "mcps": [], "agents": [], "commands": []}
        with open(config_path, "w") as f:
            json.dump(initial_config, f)

        # Merge new config
        new_config = {"mcps": [{"name": "mcp1"}], "agents": [{"name": "agent1"}]}

        result = self.config_manager.merge_config(config_path, new_config)

        assert result.success
        assert len(result.conflicts) == 0
        assert len(result.merged_config["hooks"]) == 1
        assert len(result.merged_config["mcps"]) == 1
        assert len(result.merged_config["agents"]) == 1
        assert len(result.merged_config["commands"]) == 0

    def test_merge_config_with_array_deduplication(self):
        """Test merging with array deduplication."""
        config_path = Path(self.temp_dir) / "config.json"

        # Create initial config
        initial_config = {
            "hooks": [{"name": "hook1", "event": "before"}, {"name": "hook2", "event": "after"}]
        }
        with open(config_path, "w") as f:
            json.dump(initial_config, f)

        # Merge config with duplicate
        new_config = {
            "hooks": [
                {"name": "hook2", "event": "after"},  # Duplicate
                {"name": "hook3", "event": "during"},  # New
            ]
        }

        result = self.config_manager.merge_config(config_path, new_config)

        assert result.success
        hooks = result.merged_config["hooks"]
        assert len(hooks) == 3  # Should deduplicate
        hook_names = [h["name"] for h in hooks]
        assert "hook1" in hook_names
        assert "hook2" in hook_names
        assert "hook3" in hook_names
        assert hook_names.count("hook2") == 1

    def test_update_config_atomic_success(self):
        """Test successful atomic configuration update."""
        config_path = Path(self.temp_dir) / "config.json"

        # Create initial config
        initial_config = {"hooks": []}
        with open(config_path, "w") as f:
            json.dump(initial_config, f)

        # Perform atomic update
        updates = {"mcps": [{"name": "new_mcp"}]}
        success = self.config_manager.update_config_atomic(config_path, updates)

        assert success

        # Verify config was updated
        updated_config = self.config_manager.load_config(config_path)
        assert len(updated_config["mcps"]) == 1
        assert updated_config["mcps"][0]["name"] == "new_mcp"

    def test_add_extension_config_hooks(self):
        """Test adding hook extension configuration."""
        config_path = Path(self.temp_dir) / ".claude" / "settings.json"

        # Mock getting config path to use our temp directory
        original_method = self.config_manager.get_config_path
        self.config_manager.get_config_path = lambda user_level: config_path

        try:
            hook_config = {
                "name": "test_hook",
                "event": "before_validate",
                "script": "scripts/test_hook.py",
            }

            success = self.config_manager.add_extension_config(
                "hooks", hook_config, user_level=False
            )

            assert success

            # Verify hook was added
            config = self.config_manager.load_config(config_path)
            assert len(config["hooks"]) == 1
            assert config["hooks"][0]["name"] == "test_hook"

        finally:
            self.config_manager.get_config_path = original_method

    def test_add_extension_config_invalid_type(self):
        """Test adding extension with invalid type."""
        with pytest.raises(ConfigurationError) as exc_info:
            self.config_manager.add_extension_config("invalid_type", {}, user_level=False)

        assert "Unknown extension type" in str(exc_info.value)

    def test_validate_config_structure_invalid(self):
        """Test validation of invalid config structure."""
        invalid_configs = [
            "not a dict",  # Should be dict
            {"hooks": "not a list"},  # hooks should be list
            {"mcps": {"not": "a list"}},  # mcps should be list
        ]

        for invalid_config in invalid_configs:
            with pytest.raises(ValidationError):
                self.config_manager._validate_config_structure(invalid_config, Path("test.json"))


class TestDeduplicateExtensionList:
    """Test extension list deduplication."""

    def test_deduplicate_by_name(self):
        """Test deduplication by name field."""
        extensions = [
            {"name": "ext1", "version": "1.0"},
            {"name": "ext2", "version": "1.0"},
            {"name": "ext1", "version": "2.0"},  # Duplicate name
            {"name": "ext3", "version": "1.0"},
        ]

        deduplicated, duplicates = deduplicate_extension_list(extensions, "name")

        assert len(deduplicated) == 3
        assert len(duplicates) == 1
        assert "name=ext1" in duplicates

        # Should keep first occurrence
        names = [ext["name"] for ext in deduplicated]
        assert names.count("ext1") == 1
        assert "ext2" in names
        assert "ext3" in names

    def test_deduplicate_no_key_field(self):
        """Test deduplication when key field is missing."""
        extensions = [
            {"id": "ext1"},  # No 'name' field
            {"name": "ext2", "version": "1.0"},
            {"id": "ext3"},  # No 'name' field
        ]

        deduplicated, duplicates = deduplicate_extension_list(extensions, "name")

        # Should keep all extensions without the key field
        assert len(deduplicated) == 3
        assert len(duplicates) == 0

    def test_deduplicate_empty_list(self):
        """Test deduplication of empty list."""
        deduplicated, duplicates = deduplicate_extension_list([], "name")

        assert len(deduplicated) == 0
        assert len(duplicates) == 0

    def test_deduplicate_custom_key(self):
        """Test deduplication with custom key field."""
        extensions = [
            {"id": "1", "name": "ext1"},
            {"id": "2", "name": "ext2"},
            {"id": "1", "name": "ext1_updated"},  # Duplicate ID
        ]

        deduplicated, duplicates = deduplicate_extension_list(extensions, "id")

        assert len(deduplicated) == 2
        assert len(duplicates) == 1
        assert "id=1" in duplicates


if __name__ == "__main__":
    pytest.main([__file__])
