"""Tests for plugin converter functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pacc.plugins.converter import (
    ConversionResult,
    ExtensionInfo,
    PluginConverter,
    convert_extensions_to_plugin,
)


class TestExtensionInfo:
    """Test ExtensionInfo dataclass."""

    def test_extension_info_creation(self):
        """Test creating ExtensionInfo object."""
        ext_info = ExtensionInfo(
            path=Path("/test/path.json"),
            extension_type="hooks",
            name="test_hook",
            metadata={"version": "1.0.0"},
            validation_errors=[],
            is_valid=True,
        )

        assert ext_info.path == Path("/test/path.json")
        assert ext_info.extension_type == "hooks"
        assert ext_info.name == "test_hook"
        assert ext_info.is_valid is True
        assert ext_info.metadata["version"] == "1.0.0"


class TestConversionResult:
    """Test ConversionResult dataclass."""

    def test_conversion_result_properties(self):
        """Test ConversionResult computed properties."""
        result = ConversionResult(success=True)

        # Test empty result
        assert result.total_extensions == 0
        assert result.conversion_rate == 0.0

        # Add some extensions
        ext1 = ExtensionInfo(Path("/test1"), "hooks", "test1")
        ext2 = ExtensionInfo(Path("/test2"), "agents", "test2")
        ext3 = ExtensionInfo(Path("/test3"), "commands", "test3")

        result.converted_extensions = [ext1, ext2]
        result.skipped_extensions = [ext3]

        assert result.total_extensions == 3
        assert abs(result.conversion_rate - 66.66666666666666) < 0.0001  # 2/3 * 100


class TestPluginConverter:
    """Test PluginConverter class."""

    @pytest.fixture
    def converter(self):
        """Create a PluginConverter instance for testing."""
        return PluginConverter()

    @pytest.fixture
    def temp_claude_dir(self):
        """Create a temporary .claude directory structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            claude_dir = tmpdir / ".claude"
            claude_dir.mkdir()

            # Create test extension directories
            (claude_dir / "hooks").mkdir()
            (claude_dir / "agents").mkdir()
            (claude_dir / "commands").mkdir()
            (claude_dir / "mcp").mkdir()

            yield claude_dir

    def test_plugin_name_validation(self, converter):
        """Test plugin name validation."""
        # Valid names
        assert converter._validate_plugin_name("my-plugin") is True
        assert converter._validate_plugin_name("my_plugin") is True
        assert converter._validate_plugin_name("plugin123") is True
        assert converter._validate_plugin_name("abc") is True

        # Invalid names
        assert converter._validate_plugin_name("") is False
        assert converter._validate_plugin_name("   ") is False
        assert converter._validate_plugin_name("my plugin") is False  # spaces
        assert converter._validate_plugin_name("my.plugin") is False  # dots
        assert converter._validate_plugin_name("my@plugin") is False  # special chars
        assert converter._validate_plugin_name("claude") is False  # reserved
        assert converter._validate_plugin_name("system") is False  # reserved
        assert converter._validate_plugin_name("a" * 101) is False  # too long

    def test_group_extensions_by_type(self, converter):
        """Test grouping extensions by type."""
        extensions = [
            ExtensionInfo(Path("/hook1.json"), "hooks", "hook1"),
            ExtensionInfo(Path("/hook2.json"), "hooks", "hook2"),
            ExtensionInfo(Path("/agent1.md"), "agents", "agent1"),
            ExtensionInfo(Path("/cmd1.md"), "commands", "cmd1"),
        ]

        grouped = converter._group_extensions_by_type(extensions)

        assert "hooks" in grouped
        assert "agents" in grouped
        assert "commands" in grouped
        assert len(grouped["hooks"]) == 2
        assert len(grouped["agents"]) == 1
        assert len(grouped["commands"]) == 1

    def test_scan_extensions_empty_directory(self, converter):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            extensions = converter.scan_extensions(tmpdir)
            assert extensions == []

    def test_scan_extensions_no_claude_dir(self, converter):
        """Test scanning directory without .claude subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files but no .claude directory
            (Path(tmpdir) / "test.txt").write_text("test")

            extensions = converter.scan_extensions(tmpdir)
            assert extensions == []

    def test_scan_extensions_with_hooks(self, converter, temp_claude_dir):
        """Test scanning directory with hook extensions."""
        # Create a test hook file
        hook_file = temp_claude_dir / "hooks" / "test_hook.json"
        hook_data = {"name": "test-hook", "eventTypes": ["PreToolUse"], "commands": ["echo 'test'"]}
        hook_file.write_text(json.dumps(hook_data))

        with patch.object(converter.hooks_validator, "validate_single") as mock_validate:
            mock_result = Mock()
            mock_result.is_valid = True
            mock_result.metadata = {"name": "test-hook"}
            mock_result.errors = []
            mock_validate.return_value = mock_result

            # Mock the _find_extension_files method
            with patch.object(converter.hooks_validator, "_find_extension_files") as mock_find:
                mock_find.return_value = [hook_file]

                extensions = converter.scan_extensions(temp_claude_dir.parent)

                assert len(extensions) == 1
                assert extensions[0].extension_type == "hooks"
                assert extensions[0].name == "test_hook"
                assert extensions[0].is_valid is True

    def test_convert_hooks_single_hook(self, converter):
        """Test converting a single hook extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir) / "test-plugin"
            plugin_path.mkdir(parents=True)
            (plugin_path / "hooks").mkdir()

            # Create test hook extension
            hook_data = {
                "name": "test-hook",
                "eventTypes": ["PreToolUse"],
                "commands": ["echo 'test'"],
            }

            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(hook_data, f)
                hook_path = Path(f.name)

            try:
                hook_ext = ExtensionInfo(
                    path=hook_path, extension_type="hooks", name="test_hook", is_valid=True
                )

                result = ConversionResult(success=False)
                converted = converter._convert_hooks([hook_ext], plugin_path, result)

                assert converted == 1
                assert len(result.converted_extensions) == 1
                assert len(result.errors) == 0

                # Check that hooks file was created
                hooks_file = plugin_path / "hooks" / "hooks.json"
                assert hooks_file.exists()

                # Check hooks file content
                with open(hooks_file) as f:
                    merged_hooks = json.load(f)

                assert "hooks" in merged_hooks
                assert len(merged_hooks["hooks"]) == 1
                assert merged_hooks["hooks"][0]["name"] == "test-hook"

            finally:
                hook_path.unlink()

    def test_convert_hooks_multiple_hooks(self, converter):
        """Test converting multiple hook extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir) / "test-plugin"
            plugin_path.mkdir(parents=True)
            (plugin_path / "hooks").mkdir()

            # Create multiple test hook extensions
            hook_data1 = {
                "name": "hook1",
                "eventTypes": ["PreToolUse"],
                "commands": ["echo 'test1'"],
            }
            hook_data2 = {
                "hooks": [
                    {
                        "name": "hook2a",
                        "eventTypes": ["PostToolUse"],
                        "commands": ["echo 'test2a'"],
                    },
                    {
                        "name": "hook2b",
                        "eventTypes": ["Notification"],
                        "commands": ["echo 'test2b'"],
                    },
                ]
            }

            hook_files = []
            try:
                # Create hook files
                for i, data in enumerate([hook_data1, hook_data2], 1):
                    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                        json.dump(data, f)
                        hook_files.append(Path(f.name))

                hook_exts = [
                    ExtensionInfo(hook_files[0], "hooks", "hook1", is_valid=True),
                    ExtensionInfo(hook_files[1], "hooks", "hook2", is_valid=True),
                ]

                result = ConversionResult(success=False)
                converted = converter._convert_hooks(hook_exts, plugin_path, result)

                assert converted == 2
                assert len(result.converted_extensions) == 2
                assert len(result.errors) == 0

                # Check that hooks file was created
                hooks_file = plugin_path / "hooks" / "hooks.json"
                assert hooks_file.exists()

                # Check hooks file content
                with open(hooks_file) as f:
                    merged_hooks = json.load(f)

                assert "hooks" in merged_hooks
                assert len(merged_hooks["hooks"]) == 3  # 1 + 2 hooks

            finally:
                for hook_file in hook_files:
                    hook_file.unlink()

    def test_convert_agents(self, converter):
        """Test converting agent extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir) / "test-plugin"
            plugin_path.mkdir(parents=True)
            (plugin_path / "agents").mkdir()

            # Create test agent file
            agent_content = """---
name: Test Agent
description: A test agent
tools: ["read_file", "write_file"]
---

# Test Agent

This is a test agent that does testing things.
"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(agent_content)
                agent_path = Path(f.name)

            try:
                agent_ext = ExtensionInfo(
                    path=agent_path, extension_type="agents", name="test_agent", is_valid=True
                )

                result = ConversionResult(success=False)
                converted = converter._convert_agents([agent_ext], plugin_path, result)

                assert converted == 1
                assert len(result.converted_extensions) == 1
                assert len(result.errors) == 0

                # Check that agent file was created
                agent_file = plugin_path / "agents" / "test_agent.md"
                assert agent_file.exists()

                # Check agent file content
                content = agent_file.read_text()
                assert "Test Agent" in content
                assert "test agent that does testing things" in content

            finally:
                agent_path.unlink()

    def test_convert_commands_preserves_structure(self, converter):
        """Test converting commands preserves directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir) / "test-plugin"
            plugin_path.mkdir(parents=True)
            (plugin_path / "commands").mkdir()

            # Create test command file with subdirectory structure
            source_path = (
                Path(tmpdir) / "source" / ".claude" / "commands" / "subdir" / "test_cmd.md"
            )
            source_path.parent.mkdir(parents=True)

            cmd_content = """---
name: Test Command
description: A test slash command
---

# Test Command

This is a test command.
"""
            source_path.write_text(cmd_content)

            cmd_ext = ExtensionInfo(
                path=source_path, extension_type="commands", name="test_cmd", is_valid=True
            )

            result = ConversionResult(success=False)
            converted = converter._convert_commands([cmd_ext], plugin_path, result)

            assert converted == 1
            assert len(result.converted_extensions) == 1
            assert len(result.errors) == 0

            # Check that command file was created with preserved structure
            cmd_file = plugin_path / "commands" / "subdir" / "test_cmd.md"
            assert cmd_file.exists()

            # Check command file content
            content = cmd_file.read_text()
            assert "Test Command" in content

    def test_convert_mcp_configs(self, converter):
        """Test converting MCP configurations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir) / "test-plugin"
            plugin_path.mkdir(parents=True)
            (plugin_path / "mcp").mkdir()

            # Create test MCP config
            mcp_data = {
                "mcpServers": {
                    "test-server": {
                        "command": "python",
                        "args": ["-m", "test_server"],
                        "env": {"TEST": "true"},
                    }
                }
            }

            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(mcp_data, f)
                mcp_path = Path(f.name)

            try:
                mcp_ext = ExtensionInfo(
                    path=mcp_path, extension_type="mcp", name="test_mcp", is_valid=True
                )

                result = ConversionResult(success=False)
                converted = converter._convert_mcp([mcp_ext], plugin_path, result)

                assert converted == 1
                assert len(result.converted_extensions) == 1
                assert len(result.errors) == 0

                # Check that MCP config file was created
                config_file = plugin_path / "mcp" / "config.json"
                assert config_file.exists()

                # Check MCP config content
                with open(config_file) as f:
                    merged_config = json.load(f)

                assert "mcpServers" in merged_config
                assert "test-server" in merged_config["mcpServers"]
                assert merged_config["mcpServers"]["test-server"]["command"] == "python"

            finally:
                mcp_path.unlink()

    def test_generate_manifest_basic(self, converter):
        """Test generating basic plugin manifest."""
        extensions_by_type = {
            "hooks": [
                ExtensionInfo(Path("/hook1.json"), "hooks", "hook1", is_valid=True),
                ExtensionInfo(Path("/hook2.json"), "hooks", "hook2", is_valid=True),
            ],
            "agents": [ExtensionInfo(Path("/agent1.md"), "agents", "agent1", is_valid=True)],
        }

        manifest = converter.generate_manifest(
            plugin_name="test-plugin",
            extensions_by_type=extensions_by_type,
            author_name="Test Author",
            description="Test plugin description",
        )

        assert manifest["name"] == "test-plugin"
        assert manifest["version"] == "1.0.0"
        assert manifest["description"] == "Test plugin description"
        assert manifest["author"]["name"] == "Test Author"
        assert manifest["components"]["hooks"] == 2
        assert manifest["components"]["agents"] == 1
        assert manifest["metadata"]["converted_from"] == "claude_extensions"
        assert manifest["metadata"]["conversion_tool"] == "pacc"
        assert manifest["metadata"]["total_extensions_converted"] == 3

    def test_generate_manifest_auto_description(self, converter):
        """Test generating manifest with automatic description."""
        extensions_by_type = {
            "commands": [
                ExtensionInfo(Path("/cmd1.md"), "commands", "cmd1", is_valid=True),
                ExtensionInfo(Path("/cmd2.md"), "commands", "cmd2", is_valid=True),
            ]
        }

        manifest = converter.generate_manifest(
            plugin_name="test-plugin",
            extensions_by_type=extensions_by_type,
            author_name="Test Author",
        )

        expected_desc = "Converted from Claude Code extensions: 2 commands"
        assert manifest["description"] == expected_desc

    def test_path_conversion(self, converter):
        """Test path conversion to plugin-relative format."""
        content = 'Run script at "/home/user/.claude/scripts/test.py"'

        converted = converter._convert_paths_to_plugin_relative(content)

        assert "${CLAUDE_PLUGIN_ROOT}" in converted
        assert "/scripts/test.py" in converted

    def test_convert_to_plugin_invalid_name(self, converter):
        """Test conversion with invalid plugin name."""
        result = converter.convert_to_plugin(
            extensions=[],
            plugin_name="invalid name",  # spaces not allowed
            destination="/tmp",
        )

        assert result.success is False
        assert len(result.errors) > 0
        assert "Invalid plugin name" in result.errors[0]

    def test_convert_to_plugin_empty_extensions(self, converter):
        """Test conversion with no extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = converter.convert_to_plugin(
                extensions=[], plugin_name="test-plugin", destination=tmpdir
            )

            assert result.success is False
            assert "No extensions were successfully converted" in result.errors

    def test_convert_to_plugin_full_workflow(self, converter):
        """Test complete conversion workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir)

            # Create test extensions
            hook_data = {"name": "test", "eventTypes": ["PreToolUse"], "commands": ["echo test"]}

            hook_file = destination / "test_hook.json"
            hook_file.write_text(json.dumps(hook_data))

            agent_content = "---\nname: Test\ndescription: Test agent\n---\n# Test"
            agent_file = destination / "test_agent.md"
            agent_file.write_text(agent_content)

            try:
                extensions = [
                    ExtensionInfo(hook_file, "hooks", "test_hook", is_valid=True),
                    ExtensionInfo(agent_file, "agents", "test_agent", is_valid=True),
                ]

                result = converter.convert_to_plugin(
                    extensions=extensions,
                    plugin_name="test-plugin",
                    destination=destination,
                    author_name="Test Author",
                    description="Test plugin",
                )

                assert result.success is True
                assert result.plugin_path == destination / "test-plugin"
                assert len(result.converted_extensions) == 2
                assert len(result.errors) == 0

                # Check plugin structure was created
                plugin_dir = destination / "test-plugin"
                assert plugin_dir.exists()
                assert (plugin_dir / "plugin.json").exists()
                assert (plugin_dir / "hooks").exists()
                assert (plugin_dir / "agents").exists()
                assert (plugin_dir / "hooks" / "hooks.json").exists()
                assert (plugin_dir / "agents" / "test_agent.md").exists()

                # Check manifest content
                with open(plugin_dir / "plugin.json") as f:
                    manifest = json.load(f)

                assert manifest["name"] == "test-plugin"
                assert manifest["description"] == "Test plugin"
                assert manifest["author"]["name"] == "Test Author"

            finally:
                hook_file.unlink(missing_ok=True)
                agent_file.unlink(missing_ok=True)


class TestConvertExtensionsToPlugin:
    """Test the convenience function for conversion."""

    def test_convert_extensions_to_plugin_no_extensions(self):
        """Test conversion when no extensions are found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = convert_extensions_to_plugin(
                source_directory=tmpdir, plugin_name="test-plugin", destination=tmpdir
            )

            assert result.success is False
            assert "No convertible extensions found" in result.errors

    @patch("pacc.plugins.converter.PluginConverter")
    def test_convert_extensions_to_plugin_success(self, mock_converter_class):
        """Test successful conversion using convenience function."""
        # Mock the converter
        mock_converter = Mock()
        mock_converter_class.return_value = mock_converter

        # Mock scan_extensions to return some extensions
        mock_extensions = [ExtensionInfo(Path("/test.json"), "hooks", "test", is_valid=True)]
        mock_converter.scan_extensions.return_value = mock_extensions

        # Mock convert_to_plugin to return success
        mock_result = ConversionResult(success=True)
        mock_converter.convert_to_plugin.return_value = mock_result

        result = convert_extensions_to_plugin(
            source_directory="/test/source",
            plugin_name="test-plugin",
            destination="/test/dest",
            author_name="Test Author",
            description="Test plugin",
        )

        assert result.success is True

        # Verify the converter was called correctly
        mock_converter.scan_extensions.assert_called_once_with("/test/source")
        mock_converter.convert_to_plugin.assert_called_once_with(
            extensions=mock_extensions,
            plugin_name="test-plugin",
            destination="/test/dest",
            author_name="Test Author",
            description="Test plugin",
        )


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def converter(self):
        """Create a PluginConverter instance for testing."""
        return PluginConverter()

    def test_scan_nonexistent_directory(self, converter):
        """Test scanning a directory that doesn't exist."""
        extensions = converter.scan_extensions("/nonexistent/directory")
        assert extensions == []

    def test_convert_invalid_extensions(self, converter):
        """Test converting extensions with validation errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir) / "test-plugin"
            plugin_path.mkdir(parents=True)
            (plugin_path / "hooks").mkdir()

            # Create invalid extension
            invalid_ext = ExtensionInfo(
                path=Path("/nonexistent.json"),
                extension_type="hooks",
                name="invalid",
                is_valid=False,
                validation_errors=["File not found"],
            )

            result = ConversionResult(success=False)
            converted = converter._convert_hooks([invalid_ext], plugin_path, result)

            assert converted == 0
            assert len(result.skipped_extensions) == 1
            assert len(result.warnings) > 0

    def test_file_permission_errors(self, converter):
        """Test handling file permission errors during conversion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir) / "test-plugin"
            plugin_path.mkdir(parents=True)

            # This should fail if we can't create the hooks directory
            with patch("pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")):
                result = converter._create_plugin_structure(
                    plugin_path, ConversionResult(success=False)
                )
                assert result is False

    def test_malformed_json_handling(self, converter):
        """Test handling malformed JSON in hook files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir) / "test-plugin"
            plugin_path.mkdir(parents=True)
            (plugin_path / "hooks").mkdir()

            # Create malformed JSON file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                f.write('{"invalid": json}')  # Missing quotes around 'json'
                malformed_path = Path(f.name)

            try:
                hook_ext = ExtensionInfo(
                    path=malformed_path,
                    extension_type="hooks",
                    name="malformed",
                    is_valid=True,  # Assume validation passed somehow
                )

                result = ConversionResult(success=False)
                converted = converter._convert_hooks([hook_ext], plugin_path, result)

                assert converted == 0
                assert len(result.errors) > 0
                assert len(result.skipped_extensions) == 1

            finally:
                malformed_path.unlink()

    def test_name_conflicts_resolution(self, converter):
        """Test resolution of naming conflicts during conversion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_path = Path(tmpdir) / "test-plugin"
            plugin_path.mkdir(parents=True)
            (plugin_path / "agents").mkdir()

            # Create existing file to cause conflict
            existing_file = plugin_path / "agents" / "test_agent.md"
            existing_file.write_text("existing content")

            # Create test agent file
            agent_content = "---\nname: Test\n---\n# New content"

            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(agent_content)
                agent_path = Path(f.name)

            try:
                agent_ext = ExtensionInfo(
                    path=agent_path, extension_type="agents", name="test_agent", is_valid=True
                )

                result = ConversionResult(success=False)
                converted = converter._convert_agents([agent_ext], plugin_path, result)

                assert converted == 1

                # Check that conflict was resolved with numbered suffix
                conflict_file = plugin_path / "agents" / "test_agent_1.md"
                assert conflict_file.exists()
                assert "New content" in conflict_file.read_text()

                # Original file should still exist
                assert existing_file.exists()
                assert "existing content" in existing_file.read_text()

            finally:
                agent_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__])
