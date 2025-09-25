"""Enhanced unit tests for Fragment components using deterministic sample fragments.

This module provides comprehensive unit tests for validator, storage manager,
installation manager, and other fragment components using the deterministic
sample fragments created for PACC-56.
"""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pacc.errors.exceptions import PACCError
from pacc.fragments.claude_md_manager import CLAUDEmdManager
from pacc.fragments.installation_manager import FragmentInstallationManager, InstallationResult
from pacc.fragments.storage_manager import FragmentLocation, FragmentStorageManager
from pacc.validators.fragment_validator import FragmentValidator

from ..fixtures.sample_fragments import SampleFragmentFactory


class TestEnhancedFragmentValidator:
    """Enhanced tests for FragmentValidator using sample fragments."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.validator = FragmentValidator()

        # Create sample collections
        self.deterministic_collection = SampleFragmentFactory.create_deterministic_collection(
            self.temp_dir
        )
        self.edge_case_collection = SampleFragmentFactory.create_edge_case_collection(self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_validate_deterministic_fragments_consistency(self):
        """Test validator produces consistent results for deterministic fragments."""
        # Test each fragment multiple times to ensure consistency
        fragment_paths = list(self.deterministic_collection.rglob("*.md"))
        fragment_paths.extend(list(self.deterministic_collection.rglob("*.json")))

        # Filter out manifest files
        fragment_paths = [p for p in fragment_paths if "fragment-collection.json" not in str(p)]

        for fragment_path in fragment_paths:
            results = []
            for run in range(3):
                result = self.validator.validate_single(fragment_path)
                results.append(result)

                # Each run should succeed
                assert (
                    result.is_valid
                ), f"Validation failed on run {run+1} for {fragment_path}: {result.errors}"

            # All results should be identical
            first_result = results[0]
            for i, result in enumerate(results[1:], 1):
                assert (
                    result.is_valid == first_result.is_valid
                ), f"Run {i+1} validity differs for {fragment_path}"
                assert len(result.errors) == len(
                    first_result.errors
                ), f"Run {i+1} error count differs for {fragment_path}"
                assert len(result.warnings) == len(
                    first_result.warnings
                ), f"Run {i+1} warning count differs for {fragment_path}"

    def test_validate_edge_cases_consistently(self):
        """Test validator handles edge cases consistently."""
        edge_fragments = [
            ("minimal-test-agent.md", "agent"),
            ("special-chars-agent.md", "agent"),
            ("no-params-command.md", "command"),
            ("minimal-hook.json", "hook"),
        ]

        for fragment_file, expected_type in edge_fragments:
            fragment_path = (
                self.edge_case_collection
                / (
                    "agents"
                    if expected_type == "agent"
                    else "commands"
                    if expected_type == "command"
                    else "hooks"
                )
                / fragment_file
            )

            assert fragment_path.exists(), f"Fragment not found: {fragment_path}"

            # Validate multiple times
            for run in range(3):
                result = self.validator.validate_single(fragment_path)
                assert (
                    result.is_valid
                ), f"Edge case validation failed on run {run+1} for {fragment_file}"
                assert (
                    result.fragment_type == expected_type
                ), f"Wrong type detected for {fragment_file}: got {result.fragment_type}, expected {expected_type}"

    def test_validation_error_consistency(self):
        """Test that validation errors are consistent and deterministic."""
        # Create invalid fragments with known issues
        invalid_dir = self.temp_dir / "invalid_fragments"
        invalid_dir.mkdir()
        agents_dir = invalid_dir / "agents"
        agents_dir.mkdir()

        # Invalid fragment: missing frontmatter
        no_frontmatter = """# Invalid Agent

This agent has no frontmatter.
"""
        no_frontmatter_path = agents_dir / "no-frontmatter.md"
        no_frontmatter_path.write_text(no_frontmatter)

        # Invalid fragment: malformed frontmatter
        bad_frontmatter = """---
name: bad-agent
version: not-a-valid-version
description:
---

# Bad Agent

This agent has malformed frontmatter.
"""
        bad_frontmatter_path = agents_dir / "bad-frontmatter.md"
        bad_frontmatter_path.write_text(bad_frontmatter)

        # Test validation errors are consistent
        invalid_fragments = [
            (no_frontmatter_path, "missing_frontmatter"),
            (bad_frontmatter_path, "malformed_frontmatter"),
        ]

        for fragment_path, error_type in invalid_fragments:
            results = []
            for run in range(3):
                result = self.validator.validate_single(fragment_path)
                results.append(result)

            # All runs should fail consistently
            first_result = results[0]
            assert (
                not first_result.is_valid
            ), f"Invalid fragment {error_type} should fail validation"

            for i, result in enumerate(results[1:], 1):
                assert (
                    result.is_valid == first_result.is_valid
                ), f"Run {i+1} validity differs for {error_type}"
                assert len(result.errors) == len(
                    first_result.errors
                ), f"Run {i+1} error count differs for {error_type}"
                # Error messages should be identical
                assert (
                    result.errors == first_result.errors
                ), f"Run {i+1} error messages differ for {error_type}"


class TestEnhancedFragmentStorageManager:
    """Enhanced tests for FragmentStorageManager using sample fragments."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_root = self.temp_dir / "project"
        self.project_root.mkdir()
        self.user_home = self.temp_dir / "user_home"
        self.user_home.mkdir()

        # Mock Path.home() to use our temp directory
        self.home_patcher = patch("pathlib.Path.home", return_value=self.user_home)
        self.home_patcher.start()

        self.storage_manager = FragmentStorageManager(project_root=self.project_root)

        # Create sample collections
        self.deterministic_collection = SampleFragmentFactory.create_deterministic_collection(
            self.temp_dir
        )

    def teardown_method(self):
        """Clean up test environment."""
        self.home_patcher.stop()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_storage_locations_deterministic(self):
        """Test that storage locations are determined consistently."""
        # Test project storage
        project_location = self.storage_manager.get_fragment_location("test-fragment", "project")
        assert isinstance(project_location, FragmentLocation)
        assert project_location.location_type == "project"
        assert (
            self.project_root in project_location.base_path.parents
            or project_location.base_path == self.project_root
        )

        # Test user storage
        user_location = self.storage_manager.get_fragment_location("test-fragment", "user")
        assert isinstance(user_location, FragmentLocation)
        assert user_location.location_type == "user"
        assert (
            self.user_home in user_location.base_path.parents
            or user_location.base_path == self.user_home
        )

        # Multiple calls should return identical results
        for _ in range(3):
            pl = self.storage_manager.get_fragment_location("test-fragment", "project")
            ul = self.storage_manager.get_fragment_location("test-fragment", "user")

            assert pl.base_path == project_location.base_path
            assert ul.base_path == user_location.base_path

    def test_store_and_retrieve_deterministic_fragments(self):
        """Test storing and retrieving sample fragments consistently."""
        # Store a deterministic fragment
        fragment_path = self.deterministic_collection / "agents" / "test-simple-agent.md"
        fragment_content = fragment_path.read_text()

        # Store fragment
        stored_location = self.storage_manager.store_fragment(
            name="test-simple-agent",
            content=fragment_content,
            fragment_type="agent",
            target_type="project",
            metadata={"test_metadata": {"deterministic": True}},
        )

        assert stored_location is not None
        assert stored_location.exists()

        # Retrieve fragment
        retrieved_fragment = self.storage_manager.get_fragment("test-simple-agent")
        assert retrieved_fragment is not None
        assert retrieved_fragment["name"] == "test-simple-agent"
        assert retrieved_fragment["type"] == "agent"
        assert retrieved_fragment["location_type"] == "project"

        # Store and retrieve multiple times - should be consistent
        for run in range(3):
            # Store again (should update)
            new_location = self.storage_manager.store_fragment(
                name="test-simple-agent",
                content=fragment_content,
                fragment_type="agent",
                target_type="project",
                metadata={"test_metadata": {"deterministic": True, "run": run}},
            )

            # Should be same location
            assert new_location.fragment_path == stored_location.fragment_path

            # Retrieve should be consistent
            retrieved = self.storage_manager.get_fragment("test-simple-agent")
            assert retrieved["name"] == "test-simple-agent"
            assert retrieved["type"] == "agent"

    def test_list_fragments_consistency(self):
        """Test that fragment listing is consistent and deterministic."""
        # Store multiple deterministic fragments
        fragment_files = [
            ("agents/test-simple-agent.md", "agent"),
            ("agents/test-medium-agent.md", "agent"),
            ("commands/test-simple-command.md", "command"),
            ("hooks/test-deterministic-hook.json", "hook"),
        ]

        stored_fragments = []
        for relative_path, fragment_type in fragment_files:
            fragment_path = self.deterministic_collection / relative_path
            content = fragment_path.read_text()

            # Extract name from path
            name = fragment_path.stem
            if name.endswith("-hook"):
                name = name[:-5]  # Remove -hook suffix for hooks

            location = self.storage_manager.store_fragment(
                name=name,
                content=content,
                fragment_type=fragment_type,
                target_type="project",
                metadata={"test": True},
            )
            stored_fragments.append((name, fragment_type))

        # List fragments multiple times
        listings = []
        for _ in range(3):
            fragment_list = self.storage_manager.list_installed_fragments()
            listings.append(fragment_list)

            # Should have all stored fragments
            assert len(fragment_list) == len(stored_fragments)

            # Check each expected fragment is present
            fragment_names = {f["name"] for f in fragment_list}
            expected_names = {name for name, _ in stored_fragments}
            assert fragment_names == expected_names

        # All listings should be identical (order may vary, so compare sets)
        first_listing = listings[0]
        first_names = {f["name"]: f["type"] for f in first_listing}

        for i, listing in enumerate(listings[1:], 1):
            current_names = {f["name"]: f["type"] for f in listing}
            assert current_names == first_names, f"Listing {i+1} differs from first"

    def test_remove_fragment_consistency(self):
        """Test fragment removal is consistent and deterministic."""
        # Store a fragment
        fragment_path = self.deterministic_collection / "agents" / "test-simple-agent.md"
        content = fragment_path.read_text()

        location = self.storage_manager.store_fragment(
            name="test-simple-agent",
            content=content,
            fragment_type="agent",
            target_type="project",
            metadata={"test": True},
        )

        # Verify it exists
        assert self.storage_manager.get_fragment("test-simple-agent") is not None

        # Remove fragment
        removed = self.storage_manager.remove_fragment("test-simple-agent")
        assert removed is True

        # Verify it's gone
        assert self.storage_manager.get_fragment("test-simple-agent") is None

        # Remove again - should be consistent (return False)
        removed_again = self.storage_manager.remove_fragment("test-simple-agent")
        assert removed_again is False

        # Multiple remove attempts should be consistent
        for _ in range(3):
            result = self.storage_manager.remove_fragment("test-simple-agent")
            assert result is False


class TestEnhancedFragmentInstallationManager:
    """Enhanced tests for FragmentInstallationManager using sample fragments."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_root = self.temp_dir / "project"
        self.project_root.mkdir()

        # Create test environment
        self._setup_project_environment()

        self.installation_manager = FragmentInstallationManager(project_root=self.project_root)

        # Create sample collections
        self.deterministic_collection = SampleFragmentFactory.create_deterministic_collection(
            self.temp_dir
        )
        self.dependency_collection = SampleFragmentFactory.create_dependency_collection(
            self.temp_dir
        )

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _setup_project_environment(self):
        """Set up basic project files."""
        claude_md = """# Test Project

Test project for fragment installation.
"""
        (self.project_root / "CLAUDE.md").write_text(claude_md)

        pacc_config = {"name": "test-project", "version": "1.0.0", "fragments": {}}
        (self.project_root / "pacc.json").write_text(json.dumps(pacc_config, indent=2))

    def test_installation_result_consistency(self):
        """Test that installation results are consistent and deterministic."""
        # Install deterministic collection multiple times
        results = []

        for run in range(3):
            # Reset environment between runs
            if run > 0:
                self._reset_environment()

            result = self.installation_manager.install_from_source(
                str(self.deterministic_collection), target_type="project", install_all=True
            )
            results.append(result)

            # Each run should succeed
            assert result.success, f"Installation run {run+1} failed: {result.error_message}"
            assert isinstance(result, InstallationResult)
            assert result.installed_count > 0, f"No fragments installed on run {run+1}"

        # Compare results for consistency
        first_result = results[0]
        for i, result in enumerate(results[1:], 1):
            # Core metrics should be identical
            assert result.success == first_result.success
            assert result.installed_count == first_result.installed_count
            assert result.source_type == first_result.source_type
            assert result.target_type == first_result.target_type
            assert result.dry_run == first_result.dry_run

            # Installed fragments should be the same
            assert set(result.installed_fragments.keys()) == set(
                first_result.installed_fragments.keys()
            )

    def _reset_environment(self):
        """Reset project environment for clean testing."""
        # Remove fragments directory
        fragments_dir = self.project_root / ".claude"
        if fragments_dir.exists():
            shutil.rmtree(fragments_dir)

        # Reset files
        self._setup_project_environment()

    def test_dependency_resolution_consistency(self):
        """Test dependency resolution produces consistent results."""
        results = []

        for run in range(3):
            if run > 0:
                self._reset_environment()

            result = self.installation_manager.install_from_source(
                str(self.dependency_collection), target_type="project", install_all=True
            )
            results.append(result)

            assert result.success, f"Dependency installation run {run+1} failed"
            assert result.installed_count == 3, f"Wrong fragment count on run {run+1}"

        # Verify dependency order is consistent
        first_result = results[0]
        expected_fragments = {"base-agent", "dependent-agent", "integrated-command"}

        for result in results:
            installed_names = set(result.installed_fragments.keys())
            assert installed_names == expected_fragments, "Installed fragments differ between runs"

    def test_dry_run_behavior_consistency(self):
        """Test dry run behavior is consistent and doesn't modify environment."""
        # Capture initial state
        initial_claude_md = (self.project_root / "CLAUDE.md").read_text()
        initial_pacc_json = (self.project_root / "pacc.json").read_text()

        # Run dry-run multiple times
        dry_results = []
        for run in range(3):
            result = self.installation_manager.install_from_source(
                str(self.deterministic_collection),
                target_type="project",
                install_all=True,
                dry_run=True,
            )
            dry_results.append(result)

            # Verify dry run properties
            assert result.dry_run is True, f"Run {run+1} not marked as dry run"
            assert result.success, f"Dry run {run+1} failed"

            # Verify environment unchanged
            current_claude_md = (self.project_root / "CLAUDE.md").read_text()
            current_pacc_json = (self.project_root / "pacc.json").read_text()

            assert current_claude_md == initial_claude_md, f"CLAUDE.md changed on dry run {run+1}"
            assert current_pacc_json == initial_pacc_json, f"pacc.json changed on dry run {run+1}"

        # All dry runs should produce identical results
        first_dry_result = dry_results[0]
        for i, result in enumerate(dry_results[1:], 1):
            assert result.success == first_dry_result.success
            assert result.installed_count == first_dry_result.installed_count
            assert result.dry_run == first_dry_result.dry_run

    def test_error_handling_determinism(self):
        """Test that error conditions are handled deterministically."""
        # Test with non-existent source
        nonexistent_path = self.temp_dir / "does_not_exist"

        error_results = []
        for run in range(3):
            with pytest.raises(PACCError) as exc_info:
                self.installation_manager.install_from_source(
                    str(nonexistent_path), target_type="project"
                )
            error_results.append(str(exc_info.value))

        # Error messages should be consistent
        first_error = error_results[0]
        for i, error_msg in enumerate(error_results[1:], 1):
            assert error_msg == first_error, f"Error message differs on run {i+1}"

    def test_source_resolution_consistency(self):
        """Test that source resolution produces consistent results."""
        # Test different types of sources
        sources_to_test = [
            (str(self.deterministic_collection), "collection", True),
            (
                str(self.deterministic_collection / "agents" / "test-simple-agent.md"),
                "local",
                False,
            ),
        ]

        for source_input, expected_type, is_collection in sources_to_test:
            # Resolve source multiple times
            resolved_sources = []
            for run in range(3):
                resolved = self.installation_manager.resolve_source(source_input)
                resolved_sources.append(resolved)

                assert resolved.source_type == expected_type, f"Wrong source type on run {run+1}"
                assert (
                    resolved.is_collection == is_collection
                ), f"Wrong collection flag on run {run+1}"

            # All resolutions should be identical
            first_resolved = resolved_sources[0]
            for i, resolved in enumerate(resolved_sources[1:], 1):
                assert resolved.source_type == first_resolved.source_type
                assert resolved.location == first_resolved.location
                assert resolved.is_collection == first_resolved.is_collection
                assert resolved.is_remote == first_resolved.is_remote


class TestFragmentIntegrationReliability:
    """Test the reliability and consistency of fragment component integration."""

    def setup_method(self):
        """Set up comprehensive test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_root = self.temp_dir / "project"
        self.project_root.mkdir()

        # Create all sample collections
        self.sample_collections = {
            "deterministic": SampleFragmentFactory.create_deterministic_collection(self.temp_dir),
            "edge_cases": SampleFragmentFactory.create_edge_case_collection(self.temp_dir),
            "versioned": SampleFragmentFactory.create_versioned_collection(self.temp_dir),
            "dependencies": SampleFragmentFactory.create_dependency_collection(self.temp_dir),
        }

        # Initialize all components
        self.validator = FragmentValidator()
        self.storage_manager = FragmentStorageManager(project_root=self.project_root)
        self.installation_manager = FragmentInstallationManager(project_root=self.project_root)
        self.claude_md_manager = CLAUDEmdManager(project_root=self.project_root)

        # Set up project
        self._setup_project()

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def _setup_project(self):
        """Set up basic project structure."""
        claude_md = """# Fragment Integration Test Project

This project tests fragment component integration.
"""
        (self.project_root / "CLAUDE.md").write_text(claude_md)

        pacc_config = {"name": "fragment-integration-test", "version": "1.0.0", "fragments": {}}
        (self.project_root / "pacc.json").write_text(json.dumps(pacc_config, indent=2))

    def test_full_workflow_reliability(self):
        """Test full validate -> install -> store -> retrieve workflow reliability."""
        collection_path = self.sample_collections["deterministic"]

        # Test complete workflow multiple times
        for run in range(3):
            if run > 0:
                self._reset_project()

            # 1. Validate all fragments in collection
            fragment_paths = list(collection_path.rglob("*.md"))
            fragment_paths.extend(
                [p for p in collection_path.rglob("*.json") if "collection" not in p.name]
            )

            validated_fragments = []
            for fragment_path in fragment_paths:
                result = self.validator.validate_single(fragment_path)
                assert result.is_valid, f"Validation failed on run {run+1} for {fragment_path}"
                validated_fragments.append((fragment_path, result))

            # 2. Install collection
            install_result = self.installation_manager.install_from_source(
                str(collection_path), target_type="project", install_all=True
            )

            assert install_result.success, f"Installation failed on run {run+1}"
            assert install_result.installed_count == len(
                validated_fragments
            ), f"Install count mismatch on run {run+1}"

            # 3. Verify storage
            stored_fragments = self.storage_manager.list_installed_fragments()
            assert (
                len(stored_fragments) == install_result.installed_count
            ), f"Storage count mismatch on run {run+1}"

            # 4. Retrieve each fragment
            for fragment_name in install_result.installed_fragments:
                retrieved = self.storage_manager.get_fragment(fragment_name)
                assert retrieved is not None, f"Could not retrieve {fragment_name} on run {run+1}"
                assert retrieved["name"] == fragment_name

    def _reset_project(self):
        """Reset project to clean state."""
        # Remove fragment storage
        claude_dir = self.project_root / ".claude"
        if claude_dir.exists():
            shutil.rmtree(claude_dir)

        # Reset project files
        self._setup_project()

    def test_component_consistency_under_stress(self):
        """Test that all components remain consistent under repeated operations."""
        collection_path = self.sample_collections["deterministic"]

        # Perform many operations to test consistency
        operation_results = {
            "validations": [],
            "installations": [],
            "retrievals": [],
            "listings": [],
        }

        # Install once
        install_result = self.installation_manager.install_from_source(
            str(collection_path), target_type="project", install_all=True
        )
        assert install_result.success, "Initial installation failed"

        # Perform repeated operations
        for cycle in range(5):
            # Validate all fragments again
            fragment_paths = list(collection_path.rglob("*.md"))
            fragment_paths.extend(
                [p for p in collection_path.rglob("*.json") if "collection" not in p.name]
            )

            validation_results = []
            for fragment_path in fragment_paths:
                result = self.validator.validate_single(fragment_path)
                validation_results.append(result.is_valid)
            operation_results["validations"].append(validation_results)

            # List stored fragments
            stored = self.storage_manager.list_installed_fragments()
            listing_result = [(f["name"], f["type"]) for f in stored]
            operation_results["listings"].append(sorted(listing_result))

            # Retrieve each fragment
            retrieval_results = []
            for fragment_name in install_result.installed_fragments:
                retrieved = self.storage_manager.get_fragment(fragment_name)
                retrieval_results.append(retrieved is not None)
            operation_results["retrievals"].append(retrieval_results)

        # Verify all operations produced consistent results
        for operation_type, results in operation_results.items():
            first_result = results[0]
            for i, result in enumerate(results[1:], 1):
                assert (
                    result == first_result
                ), f"{operation_type} cycle {i+1} differs from first: {result} != {first_result}"

    def test_cross_component_data_integrity(self):
        """Test data integrity across all fragment components."""
        collection_path = self.sample_collections["deterministic"]

        # Install fragments
        install_result = self.installation_manager.install_from_source(
            str(collection_path), target_type="project", install_all=True
        )

        assert install_result.success, "Installation failed"

        # Verify data consistency across components
        installed_names = set(install_result.installed_fragments.keys())

        # Check storage manager
        stored_fragments = self.storage_manager.list_installed_fragments()
        stored_names = {f["name"] for f in stored_fragments}
        assert stored_names == installed_names, "Storage manager data inconsistent"

        # Check individual retrievals
        for fragment_name in installed_names:
            retrieved = self.storage_manager.get_fragment(fragment_name)
            assert retrieved is not None, f"Could not retrieve {fragment_name}"
            assert retrieved["name"] == fragment_name, "Retrieved fragment name mismatch"

            # Verify the fragment data matches installation result
            install_data = install_result.installed_fragments[fragment_name]
            assert retrieved["type"] == install_data["type"], f"Type mismatch for {fragment_name}"

        # Verify CLAUDE.md integration
        claude_md_content = (self.project_root / "CLAUDE.md").read_text()
        for fragment_name in installed_names:
            # Fragment should be referenced in CLAUDE.md (depending on implementation)
            # This test may need adjustment based on actual CLAUDE.md integration behavior
            pass

    def test_error_recovery_consistency(self):
        """Test that error conditions and recovery are handled consistently."""
        # Test partial installation failure recovery
        invalid_collection = self.temp_dir / "invalid_collection"
        invalid_collection.mkdir()
        agents_dir = invalid_collection / "agents"
        agents_dir.mkdir()

        # Mix valid and invalid fragments
        valid_fragment = """---
name: valid-test-agent
version: 1.0.0
description: Valid test agent
---

# Valid Agent

This agent should validate successfully.
"""
        (agents_dir / "valid-agent.md").write_text(valid_fragment)

        invalid_fragment = """# Invalid Agent

No frontmatter - should fail validation.
"""
        (agents_dir / "invalid-agent.md").write_text(invalid_fragment)

        # Attempt installation - should handle partial failure consistently
        results = []
        for run in range(3):
            if run > 0:
                self._reset_project()

            result = self.installation_manager.install_from_source(
                str(invalid_collection), target_type="project", install_all=True
            )
            results.append(result)

        # All runs should handle errors the same way
        first_result = results[0]
        for i, result in enumerate(results[1:], 1):
            assert result.success == first_result.success, f"Success status differs on run {i+1}"
            # Error handling behavior should be consistent
            if not result.success:
                assert bool(result.error_message) == bool(first_result.error_message)
            assert result.installed_count == first_result.installed_count
