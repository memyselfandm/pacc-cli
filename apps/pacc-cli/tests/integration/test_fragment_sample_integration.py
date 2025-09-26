"""Integration tests for Fragment workflows using deterministic sample fragments.

This module tests the complete fragment installation, update, and removal workflows
using sample fragment collections that install consistently every time.

Created for PACC-56: Fragment Integration Testing with Sample Fragments
"""

import json
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from pacc.errors.exceptions import PACCError
from pacc.fragments.claude_md_manager import CLAUDEmdManager
from pacc.fragments.installation_manager import FragmentInstallationManager
from pacc.fragments.storage_manager import FragmentStorageManager
from pacc.fragments.update_manager import FragmentUpdateManager
from pacc.validators.fragment_validator import FragmentValidator

from ..fixtures.sample_fragments import create_comprehensive_test_suite


class TestFragmentSampleIntegration:
    """Integration tests using deterministic sample fragments."""

    def setup_method(self):
        """Set up test environment with sample fragments."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_root = self.temp_dir / "test_project"
        self.project_root.mkdir()

        # Initialize managers
        self.installation_manager = FragmentInstallationManager(project_root=self.project_root)
        self.storage_manager = FragmentStorageManager(project_root=self.project_root)
        self.update_manager = FragmentUpdateManager(project_root=self.project_root)
        self.claude_md_manager = CLAUDEmdManager(project_root=self.project_root)
        self.validator = FragmentValidator()

        # Create test environment files
        self._setup_test_environment()

        # Create sample fragment collections
        self.sample_collections = create_comprehensive_test_suite(self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _setup_test_environment(self):
        """Create basic project files."""
        # Create CLAUDE.md
        claude_md = """# Test Project

This is a test project for fragment integration testing.

## Memory Fragments

Fragments will be installed here:
"""
        self.claude_md_path = self.project_root / "CLAUDE.md"
        self.claude_md_path.write_text(claude_md)

        # Create pacc.json
        pacc_config = {
            "name": "fragment-test-project",
            "version": "1.0.0",
            "description": "Project for testing fragment integration",
            "fragments": {},
        }
        self.pacc_json_path = self.project_root / "pacc.json"
        self.pacc_json_path.write_text(json.dumps(pacc_config, indent=2))

    def test_deterministic_collection_install_consistency(self):
        """Test that deterministic collection installs exactly the same way every time."""
        collection_path = self.sample_collections["deterministic"]

        # Install collection multiple times and verify identical results
        results = []
        for i in range(3):
            # Reset environment for each run
            if i > 0:
                self._reset_test_environment()

            result = self.installation_manager.install_from_source(
                str(collection_path), target_type="project", install_all=True
            )

            results.append(result)

            # Verify successful installation
            assert result.success, f"Installation {i + 1} failed: {result.error_message}"
            assert (
                result.installed_count == 6
            ), f"Expected 6 fragments, got {result.installed_count}"

        # Compare all results for consistency
        first_result = results[0]
        for i, result in enumerate(results[1:], 1):
            # Check that core metrics are identical
            assert result.success == first_result.success, f"Run {i + 1} success differs"
            assert (
                result.installed_count == first_result.installed_count
            ), f"Run {i + 1} count differs"
            assert (
                result.source_type == first_result.source_type
            ), f"Run {i + 1} source type differs"
            assert (
                result.target_type == first_result.target_type
            ), f"Run {i + 1} target type differs"

            # Check that installed fragments are identical
            assert len(result.installed_fragments) == len(
                first_result.installed_fragments
            ), f"Run {i + 1} has different fragment count"

            for fragment_name in first_result.installed_fragments:
                assert (
                    fragment_name in result.installed_fragments
                ), f"Run {i + 1} missing fragment: {fragment_name}"

                # Verify fragment metadata is identical
                first_meta = first_result.installed_fragments[fragment_name]
                current_meta = result.installed_fragments[fragment_name]

                # Check deterministic fields (excluding timestamps)
                assert first_meta.get("name") == current_meta.get("name")
                assert first_meta.get("type") == current_meta.get("type")
                assert first_meta.get("version") == current_meta.get("version")
                assert first_meta.get("complexity") == current_meta.get("complexity")

    def _reset_test_environment(self):
        """Reset the test environment to initial state."""
        # Remove existing fragments
        fragments_dir = self.project_root / ".claude" / "fragments"
        if fragments_dir.exists():
            shutil.rmtree(fragments_dir)

        # Reset CLAUDE.md
        claude_md = """# Test Project

This is a test project for fragment integration testing.

## Memory Fragments

Fragments will be installed here:
"""
        self.claude_md_path.write_text(claude_md)

        # Reset pacc.json
        pacc_config = {
            "name": "fragment-test-project",
            "version": "1.0.0",
            "description": "Project for testing fragment integration",
            "fragments": {},
        }
        self.pacc_json_path.write_text(json.dumps(pacc_config, indent=2))

    def test_install_update_remove_workflow(self):
        """Test complete install -> update -> remove workflow with sample fragments."""
        collection_path = self.sample_collections["deterministic"]

        # 1. Install fragments
        install_result = self.installation_manager.install_from_source(
            str(collection_path), target_type="project", install_all=True
        )

        assert install_result.success, f"Installation failed: {install_result.error_message}"
        assert (
            install_result.installed_count == 6
        ), f"Expected 6 fragments, got {install_result.installed_count}"

        # Verify fragments are actually installed
        stored_fragments = self.storage_manager.list_installed_fragments()
        assert (
            len(stored_fragments) == 6
        ), f"Storage shows {len(stored_fragments)} fragments, expected 6"

        # 2. Update fragments (using versioned collection)
        versioned_collection_path = self.sample_collections["versioned"]

        # Install a specific versioned fragment
        v1_agent_path = versioned_collection_path / "agents" / "versioned-test-agent-v1.md"
        install_v1_result = self.installation_manager.install_from_source(
            str(v1_agent_path), target_type="project"
        )

        assert install_v1_result.success, "V1 agent installation failed"

        # Update to v1.1.0
        v11_agent_path = versioned_collection_path / "agents" / "versioned-test-agent-v11.md"
        update_result = self.update_manager.update_fragment(
            "versioned-test-agent", str(v11_agent_path)
        )

        assert update_result.success, f"Update failed: {update_result.error_message}"
        assert update_result.updated_fragments > 0, "No fragments were updated"

        # 3. Remove fragments
        # Remove the versioned agent
        remove_result = self.storage_manager.remove_fragment("versioned-test-agent")
        assert remove_result, "Failed to remove versioned-test-agent"

        # Remove some of the originally installed fragments
        fragments_to_remove = ["test-simple-agent", "test-simple-command"]
        for fragment_name in fragments_to_remove:
            remove_result = self.storage_manager.remove_fragment(fragment_name)
            assert remove_result, f"Failed to remove {fragment_name}"

        # Verify final state
        final_fragments = self.storage_manager.list_installed_fragments()
        expected_remaining = 6 - len(fragments_to_remove)  # Original 6 minus removed ones
        assert (
            len(final_fragments) == expected_remaining
        ), f"Expected {expected_remaining} fragments remaining, got {len(final_fragments)}"

        # Verify removed fragments are actually gone
        for removed_fragment in fragments_to_remove:
            assert removed_fragment not in [
                f["name"] for f in final_fragments
            ], f"{removed_fragment} still present after removal"

    def test_edge_case_fragments_consistency(self):
        """Test that edge case fragments install consistently."""
        collection_path = self.sample_collections["edge_cases"]

        # Test multiple installations for consistency
        for run in range(2):
            if run > 0:
                self._reset_test_environment()

            result = self.installation_manager.install_from_source(
                str(collection_path), target_type="project", install_all=True
            )

            assert result.success, f"Edge case installation run {run + 1} failed"
            assert result.installed_count == 4, f"Run {run + 1}: Expected 4 edge case fragments"

            # Verify specific edge cases were handled properly
            fragments = result.installed_fragments

            # Check minimal agent
            assert "minimal-test-agent" in fragments, "Minimal agent not installed"
            minimal_fragment = fragments["minimal-test-agent"]
            assert minimal_fragment["type"] == "agent"

            # Check special characters agent
            assert "special-chars-agent" in fragments, "Special chars agent not installed"
            special_fragment = fragments["special-chars-agent"]
            assert special_fragment["type"] == "agent"
            assert "special_characters" in special_fragment.get("metadata", {}).get(
                "test_metadata", {}
            )

            # Check no-params command
            assert "no-params-command" in fragments, "No-params command not installed"
            no_params_fragment = fragments["no-params-command"]
            assert no_params_fragment["type"] == "command"

            # Check minimal hook
            assert "minimal-hook" in fragments, "Minimal hook not installed"
            minimal_hook_fragment = fragments["minimal-hook"]
            assert minimal_hook_fragment["type"] == "hook"

    def test_dependency_resolution_workflow(self):
        """Test that dependency resolution works correctly with sample fragments."""
        collection_path = self.sample_collections["dependencies"]

        # Install collection with dependencies
        result = self.installation_manager.install_from_source(
            str(collection_path), target_type="project", install_all=True
        )

        assert result.success, f"Dependency installation failed: {result.error_message}"
        assert result.installed_count == 3, "Expected 3 fragments with dependencies"

        # Verify all fragments are installed
        fragments = result.installed_fragments
        expected_fragments = ["base-agent", "dependent-agent", "integrated-command"]

        for expected in expected_fragments:
            assert expected in fragments, f"Missing expected fragment: {expected}"

        # Verify dependency metadata is preserved
        base_fragment = fragments["base-agent"]
        assert base_fragment["metadata"].get("test_metadata", {}).get("dependency_level") == 0

        dependent_fragment = fragments["dependent-agent"]
        assert dependent_fragment["metadata"].get("test_metadata", {}).get("dependency_level") == 1
        assert "base-agent" in dependent_fragment["metadata"].get("dependencies", [])

        integrated_fragment = fragments["integrated-command"]
        assert integrated_fragment["metadata"].get("test_metadata", {}).get("dependency_level") == 2
        assert "base-agent" in integrated_fragment["metadata"].get("dependencies", [])
        assert "dependent-agent" in integrated_fragment["metadata"].get("dependencies", [])

        # Verify installation order was respected
        # (Installation manager should have resolved dependencies in correct order)
        stored_fragments = self.storage_manager.list_installed_fragments()
        assert len(stored_fragments) == 3, "Not all fragments were stored"

    def test_version_management_with_samples(self):
        """Test version management workflows using versioned sample fragments."""
        versioned_collection_path = self.sample_collections["versioned"]

        # Install v1.0.0 first
        v1_path = versioned_collection_path / "agents" / "versioned-test-agent-v1.md"
        v1_result = self.installation_manager.install_from_source(
            str(v1_path), target_type="project"
        )

        assert v1_result.success, "V1.0.0 installation failed"
        assert "versioned-test-agent" in v1_result.installed_fragments

        # Verify v1.0.0 is installed
        stored_fragments = self.storage_manager.list_installed_fragments()
        v1_fragment = next(
            (f for f in stored_fragments if f["name"] == "versioned-test-agent"), None
        )
        assert v1_fragment is not None, "V1 fragment not found in storage"
        assert v1_fragment["version"] == "1.0.0", f"Expected v1.0.0, got {v1_fragment['version']}"

        # Update to v1.1.0 (compatible update)
        v11_path = versioned_collection_path / "agents" / "versioned-test-agent-v11.md"
        v11_update = self.update_manager.update_fragment("versioned-test-agent", str(v11_path))

        assert v11_update.success, f"V1.1.0 update failed: {v11_update.error_message}"
        assert v11_update.updated_fragments > 0, "No fragments updated"

        # Verify v1.1.0 is now installed
        stored_fragments_after = self.storage_manager.list_installed_fragments()
        v11_fragment = next(
            (f for f in stored_fragments_after if f["name"] == "versioned-test-agent"), None
        )
        assert v11_fragment is not None, "V1.1.0 fragment not found after update"
        assert v11_fragment["version"] == "1.1.0", f"Expected v1.1.0, got {v11_fragment['version']}"

        # Update to v2.0.0 (breaking changes)
        v2_path = versioned_collection_path / "agents" / "versioned-test-agent-v2.md"
        v2_update = self.update_manager.update_fragment(
            "versioned-test-agent",
            str(v2_path),
            force=True,  # Required for breaking changes
        )

        assert v2_update.success, f"V2.0.0 update failed: {v2_update.error_message}"

        # Verify v2.0.0 is now installed
        final_fragments = self.storage_manager.list_installed_fragments()
        v2_fragment = next(
            (f for f in final_fragments if f["name"] == "versioned-test-agent"), None
        )
        assert v2_fragment is not None, "V2.0.0 fragment not found after update"
        assert v2_fragment["version"] == "2.0.0", f"Expected v2.0.0, got {v2_fragment['version']}"

        # Check that breaking changes metadata is preserved
        assert v2_fragment["metadata"].get("test_metadata", {}).get("breaking_changes") is True

    def test_comprehensive_validation_workflow(self):
        """Test that all sample fragments pass validation consistently."""
        # Test each collection separately
        for collection_name, collection_path in self.sample_collections.items():
            if collection_name == "master_index":
                continue  # Skip the index file

            # Validate each fragment in the collection
            if collection_path.is_dir():
                for fragment_path in collection_path.rglob("*.md"):
                    validation_result = self.validator.validate_single(fragment_path)
                    assert validation_result.is_valid, f"Validation failed for {fragment_path} in {collection_name}: {validation_result.errors}"

                for fragment_path in collection_path.rglob("*.json"):
                    if fragment_path.name != "fragment-collection.json":  # Skip manifest files
                        validation_result = self.validator.validate_single(fragment_path)
                        assert validation_result.is_valid, f"Validation failed for {fragment_path} in {collection_name}: {validation_result.errors}"

    def test_dry_run_consistency(self):
        """Test that dry run operations are consistent and don't modify the environment."""
        collection_path = self.sample_collections["deterministic"]

        # Capture initial state
        initial_claude_md = self.claude_md_path.read_text()
        initial_pacc_json = self.pacc_json_path.read_text()
        initial_fragments = self.storage_manager.list_installed_fragments()

        # Run dry-run installation
        dry_result = self.installation_manager.install_from_source(
            str(collection_path), target_type="project", install_all=True, dry_run=True
        )

        # Verify dry run shows what would be installed
        assert dry_result.success, f"Dry run failed: {dry_result.error_message}"
        assert dry_result.dry_run is True, "Result not marked as dry run"
        assert dry_result.installed_count == 6, "Dry run didn't detect all fragments"

        # Verify environment unchanged
        final_claude_md = self.claude_md_path.read_text()
        final_pacc_json = self.pacc_json_path.read_text()
        final_fragments = self.storage_manager.list_installed_fragments()

        assert initial_claude_md == final_claude_md, "CLAUDE.md was modified during dry run"
        assert initial_pacc_json == final_pacc_json, "pacc.json was modified during dry run"
        assert len(initial_fragments) == len(
            final_fragments
        ), "Fragment count changed during dry run"

    def test_performance_consistency(self):
        """Test that installation performance is consistent across runs."""
        collection_path = self.sample_collections["deterministic"]

        # Measure installation times across multiple runs
        install_times = []

        for run in range(3):
            if run > 0:
                self._reset_test_environment()

            start_time = time.time()

            result = self.installation_manager.install_from_source(
                str(collection_path), target_type="project", install_all=True
            )

            end_time = time.time()
            install_time = end_time - start_time
            install_times.append(install_time)

            assert result.success, f"Performance run {run + 1} failed"
            assert result.installed_count == 6, f"Performance run {run + 1} incomplete"

        # Verify performance is consistent (within reasonable bounds)
        avg_time = sum(install_times) / len(install_times)
        max_deviation = max(abs(t - avg_time) for t in install_times)

        # Allow up to 50% deviation (performance can vary in CI environments)
        allowed_deviation = avg_time * 0.5
        assert (
            max_deviation <= allowed_deviation
        ), f"Installation time inconsistent: times={install_times}, avg={avg_time:.3f}, max_dev={max_deviation:.3f}"

        # Verify all runs completed in reasonable time (< 10 seconds for test fragments)
        assert all(
            t < 10.0 for t in install_times
        ), f"Installation taking too long: {install_times}"

    def test_error_handling_consistency(self):
        """Test that error conditions are handled consistently."""
        # Test with non-existent collection
        non_existent_path = self.temp_dir / "does_not_exist"

        with pytest.raises(PACCError):
            self.installation_manager.install_from_source(
                str(non_existent_path), target_type="project"
            )

        # Test with invalid fragment (create a malformed one)
        invalid_collection_dir = self.temp_dir / "invalid_collection"
        invalid_collection_dir.mkdir()
        agents_dir = invalid_collection_dir / "agents"
        agents_dir.mkdir()

        # Create invalid fragment (missing frontmatter)
        invalid_agent = "# Invalid Agent\n\nThis agent has no frontmatter."
        (agents_dir / "invalid-agent.md").write_text(invalid_agent)

        # Attempt installation - should handle error gracefully
        result = self.installation_manager.install_from_source(
            str(invalid_collection_dir), target_type="project", install_all=True
        )

        # Should fail but with proper error handling
        assert not result.success, "Installation should have failed for invalid fragments"
        assert result.error_message, "Error message should be provided"
        assert result.installed_count == 0, "No fragments should have been installed"

    def test_concurrent_installation_safety(self):
        """Test that multiple installations don't interfere with each other."""
        # This tests basic safety - full concurrency testing would require threading
        collection_path = self.sample_collections["deterministic"]

        # Install once
        result1 = self.installation_manager.install_from_source(
            str(collection_path), target_type="project", install_all=True
        )

        assert result1.success, "First installation failed"

        # Install again (should handle existing fragments gracefully)
        result2 = self.installation_manager.install_from_source(
            str(collection_path), target_type="project", install_all=True
        )

        # Depending on implementation, this might succeed (update) or fail (already exists)
        # But it should handle it gracefully either way
        assert isinstance(result2.success, bool), "Second installation should return valid result"
        if not result2.success:
            assert result2.error_message, "Failed installation should provide error message"

        # Verify environment is still consistent
        final_fragments = self.storage_manager.list_installed_fragments()
        assert len(final_fragments) >= 6, "Fragments should still be installed"
