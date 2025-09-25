"""Unit tests for pacc.validators.utils module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from pacc.validators.utils import (
    ValidationRunner,
    validate_extension_directory,
)


class TestValidationRunner:
    """Test ValidationRunner class functionality."""

    def test_init_default(self):
        """Test ValidationRunner initialization with defaults."""
        runner = ValidationRunner()

        # Should have all validator types
        expected_types = {"hooks", "mcp", "agents", "commands"}
        assert set(runner.validators.keys()) == expected_types

    def test_validate_directory_no_filter(self, temp_dir):
        """Test directory validation without extension type filter."""
        runner = ValidationRunner()

        # Create test files for different extension types
        test_dir = temp_dir / "test_extensions"
        test_dir.mkdir()

        # Create hooks extension
        hooks_file = test_dir / "test.hooks.json"
        hooks_data = {"hooks": [{"event": "beforeInstall", "script": "echo 'before install'"}]}
        hooks_file.write_text(json.dumps(hooks_data))

        # Create MCP server config
        mcp_file = test_dir / "test.mcp.json"
        mcp_data = {"mcpServers": {"test-server": {"command": "python", "args": ["test.py"]}}}
        mcp_file.write_text(json.dumps(mcp_data))

        # Mock ExtensionDetector to return our files
        with patch("pacc.validators.utils.ExtensionDetector") as mock_detector:
            mock_detector.scan_directory.return_value = {"hooks": [hooks_file], "mcp": [mcp_file]}

            results = runner.validate_directory(test_dir)

        # Should have results for both types
        assert "hooks" in results
        assert "mcp" in results
        assert len(results) == 2

    def test_validate_directory_with_filter(self, temp_dir):
        """Test directory validation with extension type filter."""
        runner = ValidationRunner()

        test_dir = temp_dir / "test_extensions"
        test_dir.mkdir()

        # Create test files for different types
        hooks_file = test_dir / "test.hooks.json"
        hooks_data = {"hooks": [{"event": "beforeInstall", "script": "echo test"}]}
        hooks_file.write_text(json.dumps(hooks_data))

        mcp_file = test_dir / "test.mcp.json"
        mcp_data = {"mcpServers": {"test": {"command": "python", "args": ["test.py"]}}}
        mcp_file.write_text(json.dumps(mcp_data))

        # Mock ExtensionDetector
        with patch("pacc.validators.utils.ExtensionDetector") as mock_detector:
            mock_detector.scan_directory.return_value = {"hooks": [hooks_file], "mcp": [mcp_file]}

            # Test filtering by hooks only
            results = runner.validate_directory(test_dir, extension_type="hooks")

        # Should only have hooks results
        assert "hooks" in results
        assert "mcp" not in results
        assert len(results) == 1

    def test_validate_directory_filter_nonexistent_type(self, temp_dir):
        """Test directory validation with filter for non-existent extension type."""
        runner = ValidationRunner()

        test_dir = temp_dir / "test_extensions"
        test_dir.mkdir()

        # Mock ExtensionDetector to return some files
        with patch("pacc.validators.utils.ExtensionDetector") as mock_detector:
            mock_detector.scan_directory.return_value = {"hooks": [temp_dir / "test.hooks.json"]}

            # Filter for type that doesn't exist in directory
            results = runner.validate_directory(test_dir, extension_type="agents")

        # Should return empty results
        assert len(results) == 0

    def test_validate_directory_filter_invalid_type(self, temp_dir):
        """Test directory validation with invalid extension type filter."""
        runner = ValidationRunner()

        test_dir = temp_dir / "test_extensions"
        test_dir.mkdir()

        # Mock ExtensionDetector
        with patch("pacc.validators.utils.ExtensionDetector") as mock_detector:
            mock_detector.scan_directory.return_value = {"hooks": [temp_dir / "test.hooks.json"]}

            # Filter for completely invalid type
            results = runner.validate_directory(test_dir, extension_type="invalid")

        # Should return empty results (no error, just filtered out)
        assert len(results) == 0

    def test_validate_directory_preserves_original_behavior(self, temp_dir):
        """Test that filtering doesn't break the original behavior when no filter is applied."""
        runner = ValidationRunner()

        test_dir = temp_dir / "test_extensions"
        test_dir.mkdir()

        # Create multiple extension files
        files_by_type = {
            "hooks": [temp_dir / "test1.hooks.json", temp_dir / "test2.hooks.json"],
            "mcp": [temp_dir / "test.mcp.json"],
            "agents": [temp_dir / "test.agent.md"],
        }

        with patch("pacc.validators.utils.ExtensionDetector") as mock_detector:
            mock_detector.scan_directory.return_value = files_by_type

            # Test without filter (original behavior)
            results_no_filter = runner.validate_directory(test_dir)

            # Test with None filter (should be same as no filter)
            results_none_filter = runner.validate_directory(test_dir, extension_type=None)

        # Both should be identical
        assert results_no_filter.keys() == results_none_filter.keys()
        assert len(results_no_filter) == 3
        assert len(results_none_filter) == 3


class TestValidateExtensionDirectory:
    """Test validate_extension_directory function."""

    def test_validate_extension_directory_no_filter(self, temp_dir):
        """Test validate_extension_directory without filter."""
        test_dir = temp_dir / "test_extensions"
        test_dir.mkdir()

        # Mock the ValidationRunner
        with patch("pacc.validators.utils.ValidationRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.validate_directory.return_value = {"hooks": [], "mcp": []}

            results = validate_extension_directory(test_dir)

            # Should call ValidationRunner.validate_directory with no extension_type
            mock_runner.validate_directory.assert_called_once_with(test_dir, None)
            assert results == {"hooks": [], "mcp": []}

    def test_validate_extension_directory_with_filter(self, temp_dir):
        """Test validate_extension_directory with extension type filter."""
        test_dir = temp_dir / "test_extensions"
        test_dir.mkdir()

        with patch("pacc.validators.utils.ValidationRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.validate_directory.return_value = {"hooks": []}

            results = validate_extension_directory(test_dir, extension_type="hooks")

            # Should call ValidationRunner.validate_directory with extension_type
            mock_runner.validate_directory.assert_called_once_with(test_dir, "hooks")
            assert results == {"hooks": []}

    def test_validate_extension_directory_backward_compatibility(self, temp_dir):
        """Test that existing code calling without extension_type still works."""
        test_dir = temp_dir / "test_extensions"
        test_dir.mkdir()

        with patch("pacc.validators.utils.ValidationRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.validate_directory.return_value = {"hooks": [], "mcp": []}

            # This should work exactly as before (positional argument only)
            results = validate_extension_directory(test_dir)

            mock_runner.validate_directory.assert_called_once_with(test_dir, None)
            assert results == {"hooks": [], "mcp": []}

    def test_validate_extension_directory_pathlib_path(self, temp_dir):
        """Test validate_extension_directory accepts pathlib Path objects."""
        test_dir = temp_dir / "test_extensions"
        test_dir.mkdir()

        with patch("pacc.validators.utils.ValidationRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.validate_directory.return_value = {"hooks": []}

            # Test with pathlib Path
            results = validate_extension_directory(test_dir, extension_type="hooks")

            mock_runner.validate_directory.assert_called_once_with(test_dir, "hooks")
            assert results == {"hooks": []}

    def test_validate_extension_directory_string_path(self, temp_dir):
        """Test validate_extension_directory accepts string paths."""
        test_dir = temp_dir / "test_extensions"
        test_dir.mkdir()

        with patch("pacc.validators.utils.ValidationRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.validate_directory.return_value = {"mcp": []}

            # Test with string path
            results = validate_extension_directory(str(test_dir), extension_type="mcp")

            mock_runner.validate_directory.assert_called_once_with(str(test_dir), "mcp")
            assert results == {"mcp": []}


class TestValidationIntegrationWithFiltering:
    """Integration tests for validation with the new filtering capability."""

    def test_end_to_end_directory_validation_filtering(self, temp_dir):
        """Test complete directory validation workflow with filtering."""
        test_dir = temp_dir / "mixed_extensions"
        test_dir.mkdir()

        # Create test files
        hooks_file = test_dir / "deploy.hooks.json"
        hooks_file.write_text('{"hooks": [{"event": "beforeInstall", "script": "npm install"}]}')

        mcp_file = test_dir / "server.mcp.json"
        mcp_file.write_text(
            '{"mcpServers": {"fs": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"]}}}'
        )

        agents_file = test_dir / "test.agent.md"
        agents_file.write_text("---\nname: Test Agent\n---\nTest content")

        # Mock ExtensionDetector to control what files are found
        with patch("pacc.validators.utils.ExtensionDetector") as mock_detector:
            # Set up the mock to return our test files
            mock_detector.scan_directory.return_value = {
                "hooks": [hooks_file],
                "mcp": [mcp_file],
                "agents": [agents_file],
            }

            # Test filtering for hooks only
            hooks_results = validate_extension_directory(test_dir, extension_type="hooks")

            # Should only contain hooks results
            assert "hooks" in hooks_results
            assert "mcp" not in hooks_results
            assert "agents" not in hooks_results

            # Test filtering for MCP only
            mcp_results = validate_extension_directory(test_dir, extension_type="mcp")

            # Should only contain MCP results
            assert "mcp" in mcp_results
            assert "hooks" not in mcp_results
            assert "agents" not in mcp_results

            # Test no filtering (should get all types found)
            all_results = validate_extension_directory(test_dir)

            # Should contain all extension types present
            extension_types = set(all_results.keys())
            assert "hooks" in extension_types
            assert "mcp" in extension_types
            assert "agents" in extension_types

    def test_cli_integration_compatibility(self, temp_dir):
        """Test that the fix works with the CLI usage pattern."""
        # Simulate how the CLI calls the function
        test_dir = temp_dir / "cli_test"
        test_dir.mkdir()

        # Create a hooks file
        hooks_file = test_dir / "test.hooks.json"
        hooks_data = {"hooks": [{"event": "beforeInstall", "script": "echo test"}]}
        hooks_file.write_text(json.dumps(hooks_data))

        # This simulates the CLI call pattern: validate_extension_directory(source_path, args.type)
        extension_type = "hooks"  # This would be args.type in the CLI

        try:
            # This should not raise an exception (was the original bug)
            results = validate_extension_directory(test_dir, extension_type)

            # The function should execute successfully
            assert isinstance(results, dict)

            # If hooks files are found, they should be in the results
            if results:
                assert extension_type in results or len(results) == 0

        except TypeError as e:
            pytest.fail(f"CLI integration failed with TypeError: {e}")


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling for the new functionality."""

    def test_empty_extension_type_string(self, temp_dir):
        """Test behavior with empty string as extension_type."""
        test_dir = temp_dir / "empty_type_test"
        test_dir.mkdir()

        with patch("pacc.validators.utils.ExtensionDetector") as mock_detector:
            mock_detector.scan_directory.return_value = {"hooks": []}

            # Empty string should be treated as a filter (not None)
            results = validate_extension_directory(test_dir, extension_type="")

        # Should return empty results since "" is not a valid extension type
        assert len(results) == 0

    def test_none_extension_type_explicit(self, temp_dir):
        """Test explicit None as extension_type parameter."""
        test_dir = temp_dir / "none_type_test"
        test_dir.mkdir()

        with patch("pacc.validators.utils.ValidationRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner_class.return_value = mock_runner
            mock_runner.validate_directory.return_value = {"hooks": [], "mcp": []}

            # Explicit None should behave same as not providing the parameter
            results = validate_extension_directory(test_dir, extension_type=None)

            mock_runner.validate_directory.assert_called_once_with(test_dir, None)

    def test_case_sensitivity_extension_type(self, temp_dir):
        """Test that extension type filtering is case sensitive."""
        test_dir = temp_dir / "case_test"
        test_dir.mkdir()

        with patch("pacc.validators.utils.ExtensionDetector") as mock_detector:
            mock_detector.scan_directory.return_value = {"hooks": []}

            # Test with wrong case - should not match
            results = validate_extension_directory(test_dir, extension_type="HOOKS")

        # Should not match due to case sensitivity
        assert len(results) == 0
