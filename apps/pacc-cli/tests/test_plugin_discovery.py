"""Tests for plugin discovery engine."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from pacc.plugins import DiscoveryPluginInfo as PluginInfo
from pacc.plugins import (
    PluginManifestParser,
    PluginMetadataExtractor,
    PluginScanner,
    RepositoryInfo,
    discover_plugins,
    extract_plugin_metadata,
    extract_template_variables,
    resolve_template_variables,
    validate_plugin_manifest,
)
from pacc.validation.base import ValidationResult


class TestPluginManifestParser:
    """Test plugin manifest parsing and validation."""

    def test_parse_valid_minimal_manifest(self, tmp_path):
        """Test parsing a minimal valid manifest."""
        manifest_data = {"name": "test-plugin"}
        manifest_path = tmp_path / "plugin.json"

        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        parser = PluginManifestParser()
        manifest, result = parser.parse_manifest(manifest_path)

        assert result.is_valid
        assert manifest["name"] == "test-plugin"
        assert result.warning_count >= 3  # Missing recommended fields

    def test_parse_valid_complete_manifest(self, tmp_path):
        """Test parsing a complete valid manifest."""
        manifest_data = {
            "name": "awesome-plugin",
            "version": "1.2.3",
            "description": "An awesome plugin for testing",
            "author": {
                "name": "Test Author",
                "email": "test@example.com",
                "url": "https://example.com",
            },
        }
        manifest_path = tmp_path / "plugin.json"

        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        parser = PluginManifestParser()
        manifest, result = parser.parse_manifest(manifest_path)

        assert result.is_valid
        assert manifest == manifest_data
        assert result.warning_count == 0

    def test_parse_invalid_json(self, tmp_path):
        """Test parsing invalid JSON."""
        manifest_path = tmp_path / "plugin.json"

        with open(manifest_path, "w") as f:
            f.write('{"name": "test", invalid json}')

        parser = PluginManifestParser()
        manifest, result = parser.parse_manifest(manifest_path)

        assert not result.is_valid
        assert result.has_errors
        assert "SYNTAX_ERROR" in [issue.rule_id for issue in result.issues]

    def test_parse_missing_required_field(self, tmp_path):
        """Test parsing manifest missing required name field."""
        manifest_data = {"version": "1.0.0"}
        manifest_path = tmp_path / "plugin.json"

        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f)

        parser = PluginManifestParser()
        manifest, result = parser.parse_manifest(manifest_path)

        assert not result.is_valid
        assert result.has_errors
        assert "MISSING_REQUIRED_FIELD" in [issue.rule_id for issue in result.issues]

    def test_validate_name_format(self, tmp_path):
        """Test validation of plugin name format."""
        invalid_names = [
            "",  # Empty
            "test plugin",  # Space
            "test@plugin",  # Special char
            "test.plugin",  # Dot
        ]

        parser = PluginManifestParser()

        for invalid_name in invalid_names:
            manifest_data = {"name": invalid_name}
            manifest_path = tmp_path / "plugin.json"

            with open(manifest_path, "w") as f:
                json.dump(manifest_data, f)

            manifest, result = parser.parse_manifest(manifest_path)
            assert not result.is_valid, f"Name '{invalid_name}' should be invalid"

    def test_validate_version_format(self, tmp_path):
        """Test validation of semantic version format."""
        invalid_versions = [
            "1.0",  # Missing patch
            "v1.0.0",  # Prefix
            "1.0.0.0",  # Too many parts
            "1.x.0",  # Non-numeric
        ]

        parser = PluginManifestParser()

        for invalid_version in invalid_versions:
            manifest_data = {"name": "test", "version": invalid_version}
            manifest_path = tmp_path / "plugin.json"

            with open(manifest_path, "w") as f:
                json.dump(manifest_data, f)

            manifest, result = parser.parse_manifest(manifest_path)
            assert not result.is_valid, f"Version '{invalid_version}' should be invalid"

    def test_validate_author_email(self, tmp_path):
        """Test validation of author email format."""
        invalid_emails = ["not-an-email", "@example.com", "test@", "test..test@example.com"]

        parser = PluginManifestParser()

        for invalid_email in invalid_emails:
            manifest_data = {"name": "test", "author": {"name": "Test", "email": invalid_email}}
            manifest_path = tmp_path / "plugin.json"

            with open(manifest_path, "w") as f:
                json.dump(manifest_data, f)

            manifest, result = parser.parse_manifest(manifest_path)
            assert not result.is_valid, f"Email '{invalid_email}' should be invalid"


class TestPluginMetadataExtractor:
    """Test metadata extraction from plugin components."""

    def test_extract_command_metadata_basic(self, tmp_path):
        """Test extracting basic command metadata."""
        command_content = """---
description: Test command
allowed-tools: [Read, Write]
argument-hint: "file path"
---

# Test Command

This is a test command that does $ARGUMENTS.
"""
        command_path = tmp_path / "test.md"
        with open(command_path, "w") as f:
            f.write(command_content)

        extractor = PluginMetadataExtractor()
        metadata = extractor.extract_command_metadata(command_path)

        assert metadata["type"] == "command"
        assert metadata["name"] == "test"
        assert metadata["description"] == "Test command"
        assert metadata["allowed_tools"] == ["Read", "Write"]
        assert metadata["argument_hint"] == "file path"
        assert "$ARGUMENTS" in metadata["template_variables"]
        assert len(metadata["errors"]) == 0

    def test_extract_command_metadata_no_frontmatter(self, tmp_path):
        """Test extracting metadata from command without frontmatter."""
        command_content = "# Simple Command\n\nDo something with $ARGUMENTS."
        command_path = tmp_path / "simple.md"
        with open(command_path, "w") as f:
            f.write(command_content)

        extractor = PluginMetadataExtractor()
        metadata = extractor.extract_command_metadata(command_path)

        assert metadata["type"] == "command"
        assert metadata["name"] == "simple"
        assert metadata["description"] is None
        assert metadata["body"] == command_content
        assert "$ARGUMENTS" in metadata["template_variables"]

    def test_extract_command_metadata_invalid_yaml(self, tmp_path):
        """Test extracting metadata with invalid YAML frontmatter."""
        command_content = """---
description: Test command
invalid: yaml: syntax
---

Command body"""
        command_path = tmp_path / "invalid.md"
        with open(command_path, "w") as f:
            f.write(command_content)

        extractor = PluginMetadataExtractor()
        metadata = extractor.extract_command_metadata(command_path)

        assert len(metadata["errors"]) > 0
        assert "Invalid YAML frontmatter" in metadata["errors"][0]

    def test_extract_agent_metadata_basic(self, tmp_path):
        """Test extracting basic agent metadata."""
        agent_content = """---
name: Test Agent
description: A test agent
tools: [Read, Write, Bash]
color: blue
---

You are a test agent that helps with testing.
"""
        agent_path = tmp_path / "test-agent.md"
        with open(agent_path, "w") as f:
            f.write(agent_content)

        extractor = PluginMetadataExtractor()
        metadata = extractor.extract_agent_metadata(agent_path)

        assert metadata["type"] == "agent"
        assert metadata["name"] == "test-agent"
        assert metadata["display_name"] == "Test Agent"
        assert metadata["description"] == "A test agent"
        assert metadata["tools"] == ["Read", "Write", "Bash"]
        assert metadata["color"] == "blue"
        assert len(metadata["errors"]) == 0

    def test_extract_hooks_metadata_basic(self, tmp_path):
        """Test extracting basic hooks metadata."""
        hooks_data = {
            "hooks": [
                {
                    "type": "PreToolUse",
                    "matcher": {"toolName": "Bash"},
                    "action": {"command": "echo 'Running command'"},
                    "description": "Log bash commands",
                }
            ]
        }
        hooks_path = tmp_path / "hooks.json"
        with open(hooks_path, "w") as f:
            json.dump(hooks_data, f)

        extractor = PluginMetadataExtractor()
        metadata = extractor.extract_hooks_metadata(hooks_path)

        assert metadata["type"] == "hooks"
        assert len(metadata["hooks"]) == 1
        assert metadata["hooks"][0]["type"] == "PreToolUse"
        assert metadata["hooks"][0]["matcher"]["toolName"] == "Bash"
        assert len(metadata["errors"]) == 0

    def test_extract_hooks_metadata_invalid_structure(self, tmp_path):
        """Test extracting hooks metadata with invalid structure."""
        hooks_data = {"invalid": "structure"}
        hooks_path = tmp_path / "hooks.json"
        with open(hooks_path, "w") as f:
            json.dump(hooks_data, f)

        extractor = PluginMetadataExtractor()
        metadata = extractor.extract_hooks_metadata(hooks_path)

        assert len(metadata["errors"]) > 0
        assert "missing 'hooks' array" in metadata["errors"][0]


class TestPluginScanner:
    """Test plugin scanning functionality."""

    def create_test_plugin(self, plugin_dir: Path, name: str = "test-plugin"):
        """Helper to create a test plugin structure."""
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest = {"name": name, "version": "1.0.0", "description": f"Test plugin {name}"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(manifest, f)

        # Create commands
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir(exist_ok=True)

        command_content = """---
description: Test command
---

Test command for $ARGUMENTS.
"""
        with open(commands_dir / "test.md", "w") as f:
            f.write(command_content)

        # Create agents
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir(exist_ok=True)

        agent_content = """---
name: Test Agent
description: Test agent
---

You are a test agent.
"""
        with open(agents_dir / "test.md", "w") as f:
            f.write(agent_content)

        # Create hooks
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)

        hooks_data = {
            "hooks": [{"type": "SessionStart", "action": {"command": "echo 'Plugin loaded'"}}]
        }
        with open(hooks_dir / "hooks.json", "w") as f:
            json.dump(hooks_data, f)

    def test_scan_single_plugin_repository(self, tmp_path):
        """Test scanning repository with single plugin."""
        plugin_dir = tmp_path / "my-plugin"
        self.create_test_plugin(plugin_dir)

        scanner = PluginScanner()
        repo_info = scanner.scan_repository(tmp_path)

        assert repo_info.plugin_count == 1
        assert len(repo_info.valid_plugins) == 1
        assert len(repo_info.invalid_plugins) == 0
        assert len(repo_info.scan_errors) == 0

        plugin = repo_info.plugins[0]
        assert plugin.name == "test-plugin"
        assert plugin.is_valid
        assert plugin.has_components
        assert "commands" in plugin.components
        assert "agents" in plugin.components
        assert "hooks" in plugin.components

    def test_scan_multi_plugin_repository(self, tmp_path):
        """Test scanning repository with multiple plugins."""
        # Create multiple plugins
        self.create_test_plugin(tmp_path / "plugin1", "plugin-one")
        self.create_test_plugin(tmp_path / "plugin2", "plugin-two")
        self.create_test_plugin(tmp_path / "subdir" / "plugin3", "plugin-three")

        scanner = PluginScanner()
        repo_info = scanner.scan_repository(tmp_path)

        assert repo_info.plugin_count == 3
        assert len(repo_info.valid_plugins) == 3

        plugin_names = [p.name for p in repo_info.plugins]
        assert "plugin-one" in plugin_names
        assert "plugin-two" in plugin_names
        assert "plugin-three" in plugin_names

    def test_scan_repository_with_invalid_plugin(self, tmp_path):
        """Test scanning repository with invalid plugin."""
        plugin_dir = tmp_path / "invalid-plugin"
        plugin_dir.mkdir()

        # Create invalid manifest (missing name)
        manifest = {"version": "1.0.0"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(manifest, f)

        scanner = PluginScanner()
        repo_info = scanner.scan_repository(tmp_path)

        assert repo_info.plugin_count == 1
        assert len(repo_info.valid_plugins) == 0
        assert len(repo_info.invalid_plugins) == 1

        plugin = repo_info.plugins[0]
        assert not plugin.is_valid
        assert len(plugin.errors) > 0

    def test_scan_nonexistent_repository(self, tmp_path):
        """Test scanning nonexistent repository."""
        nonexistent_path = tmp_path / "does-not-exist"

        scanner = PluginScanner()
        repo_info = scanner.scan_repository(nonexistent_path)

        assert repo_info.plugin_count == 0
        assert len(repo_info.scan_errors) > 0
        assert "does not exist" in repo_info.scan_errors[0]

    def test_scan_file_instead_of_directory(self, tmp_path):
        """Test scanning a file instead of directory."""
        file_path = tmp_path / "not-a-dir.txt"
        file_path.write_text("not a directory")

        scanner = PluginScanner()
        repo_info = scanner.scan_repository(file_path)

        assert repo_info.plugin_count == 0
        assert len(repo_info.scan_errors) > 0
        assert "not a directory" in repo_info.scan_errors[0]


class TestPluginInfo:
    """Test PluginInfo functionality."""

    def test_plugin_info_validation_status(self):
        """Test plugin validation status properties."""
        plugin = PluginInfo(name="test", path=Path("/test"), manifest={"name": "test"})

        # Initially valid
        assert plugin.is_valid

        # Add error makes invalid
        plugin.errors.append("Test error")
        assert not plugin.is_valid

        # Clear errors
        plugin.errors.clear()
        assert plugin.is_valid

    def test_plugin_info_namespaced_components(self, tmp_path):
        """Test namespaced component generation."""
        plugin_dir = tmp_path / "test-plugin"
        plugin_dir.mkdir()

        # Create nested command structure
        (plugin_dir / "commands" / "utils").mkdir(parents=True)
        (plugin_dir / "commands" / "test.md").touch()
        (plugin_dir / "commands" / "utils" / "helper.md").touch()

        plugin = PluginInfo(
            name="test-plugin",
            path=plugin_dir,
            manifest={"name": "test-plugin"},
            components={
                "commands": [
                    plugin_dir / "commands" / "test.md",
                    plugin_dir / "commands" / "utils" / "helper.md",
                ]
            },
        )

        namespaced = plugin.get_namespaced_components()

        assert "commands" in namespaced
        assert "test-plugin:test" in namespaced["commands"]
        assert "test-plugin:utils:helper" in namespaced["commands"]


class TestTemplateVariables:
    """Test template variable functionality."""

    def test_extract_template_variables(self):
        """Test extracting template variables from content."""
        content = """
        Use $ARGUMENTS for user input.
        Plugin root is ${CLAUDE_PLUGIN_ROOT}.
        Regular $vars should be ignored.
        """

        variables = extract_template_variables(content)

        assert "$ARGUMENTS" in variables
        assert "${CLAUDE_PLUGIN_ROOT}" in variables
        assert len(variables) == 2

    def test_resolve_template_variables(self):
        """Test resolving template variables."""
        content = "Plugin at ${CLAUDE_PLUGIN_ROOT} processes $ARGUMENTS"
        plugin_root = Path("/test/plugin")
        arguments = "test input"

        resolved = resolve_template_variables(content, plugin_root, arguments)

        assert "${CLAUDE_PLUGIN_ROOT}" not in resolved
        assert "$ARGUMENTS" not in resolved
        assert "/test/plugin" in resolved
        assert "test input" in resolved

    def test_resolve_partial_variables(self):
        """Test resolving only some template variables."""
        content = "Plugin at ${CLAUDE_PLUGIN_ROOT} processes $ARGUMENTS"

        # Only resolve plugin root
        resolved = resolve_template_variables(content, Path("/test"), None)
        assert "/test" in resolved
        assert "$ARGUMENTS" in resolved  # Still present


class TestMainFunctions:
    """Test main discovery functions."""

    def test_discover_plugins_function(self, tmp_path):
        """Test discover_plugins function."""
        # Create test plugin
        plugin_dir = tmp_path / "test-plugin"
        plugin_dir.mkdir()

        manifest = {"name": "test-plugin", "version": "1.0.0"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(manifest, f)

        repo_info = discover_plugins(tmp_path)

        assert isinstance(repo_info, RepositoryInfo)
        assert repo_info.plugin_count == 1
        assert repo_info.plugins[0].name == "test-plugin"

    def test_validate_plugin_manifest_function(self, tmp_path):
        """Test validate_plugin_manifest function."""
        manifest_path = tmp_path / "plugin.json"
        manifest = {"name": "test-plugin"}

        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        result = validate_plugin_manifest(manifest_path)

        assert isinstance(result, ValidationResult)
        assert result.is_valid

    def test_extract_plugin_metadata_function(self, tmp_path):
        """Test extract_plugin_metadata function."""
        plugin_dir = tmp_path / "test-plugin"
        plugin_dir.mkdir()

        manifest = {"name": "test-plugin"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(manifest, f)

        plugin_info = extract_plugin_metadata(plugin_dir)

        assert isinstance(plugin_info, PluginInfo)
        assert plugin_info.name == "test-plugin"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_plugin_with_no_components(self, tmp_path):
        """Test plugin with only manifest, no components."""
        plugin_dir = tmp_path / "minimal-plugin"
        plugin_dir.mkdir()

        manifest = {"name": "minimal-plugin"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(manifest, f)

        scanner = PluginScanner()
        repo_info = scanner.scan_repository(tmp_path)

        assert repo_info.plugin_count == 1
        plugin = repo_info.plugins[0]
        assert not plugin.has_components
        assert len(plugin.components) == 0

    def test_plugin_with_empty_directories(self, tmp_path):
        """Test plugin with empty component directories."""
        plugin_dir = tmp_path / "empty-dirs-plugin"
        plugin_dir.mkdir()

        manifest = {"name": "empty-dirs"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(manifest, f)

        # Create empty directories
        (plugin_dir / "commands").mkdir()
        (plugin_dir / "agents").mkdir()
        (plugin_dir / "hooks").mkdir()

        scanner = PluginScanner()
        plugin_info = scanner._scan_plugin_directory(plugin_dir)

        assert plugin_info is not None
        assert not plugin_info.has_components
        # Empty directories shouldn't add empty component lists
        assert len(plugin_info.components.get("commands", [])) == 0

    def test_malformed_component_files(self, tmp_path):
        """Test handling of malformed component files."""
        plugin_dir = tmp_path / "malformed-plugin"
        plugin_dir.mkdir()

        manifest = {"name": "malformed"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(manifest, f)

        # Create malformed hooks file
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir()
        with open(hooks_dir / "hooks.json", "w") as f:
            f.write("invalid json{")

        scanner = PluginScanner()
        plugin_info = scanner._scan_plugin_directory(plugin_dir)

        assert plugin_info is not None
        assert len(plugin_info.errors) > 0
        assert not plugin_info.is_valid

    def test_permission_denied_access(self, tmp_path):
        """Test handling permission denied errors."""
        plugin_dir = tmp_path / "restricted-plugin"
        plugin_dir.mkdir()

        manifest = {"name": "restricted"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(manifest, f)

        # Mock permission error during component discovery
        with patch("pathlib.Path.rglob") as mock_rglob:
            mock_rglob.side_effect = OSError("Permission denied")

            scanner = PluginScanner()
            plugin_info = scanner._scan_plugin_directory(plugin_dir)

            assert plugin_info is not None
            # Should still create plugin info even if component discovery fails


if __name__ == "__main__":
    pytest.main([__file__])
