"""Test sample fragment creation to verify the infrastructure works."""

import shutil
import tempfile
from pathlib import Path

from tests.fixtures.sample_fragments import SampleFragmentFactory, create_comprehensive_test_suite


class TestSampleFragmentCreation:
    """Test that sample fragment infrastructure works correctly."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_create_deterministic_collection(self):
        """Test creating deterministic collection works."""
        collection = SampleFragmentFactory.create_deterministic_collection(self.temp_dir)

        # Verify collection exists
        assert collection.exists()
        assert collection.is_dir()

        # Verify structure
        assert (collection / "agents").exists()
        assert (collection / "commands").exists()
        assert (collection / "hooks").exists()
        assert (collection / "fragment-collection.json").exists()

        # Verify specific fragments exist
        assert (collection / "agents" / "test-simple-agent.md").exists()
        assert (collection / "agents" / "test-medium-agent.md").exists()
        assert (collection / "commands" / "test-simple-command.md").exists()
        assert (collection / "commands" / "test-complex-command.md").exists()
        assert (collection / "hooks" / "test-deterministic-hook.json").exists()
        assert (collection / "hooks" / "test-complex-hook.json").exists()

    def test_create_comprehensive_suite(self):
        """Test creating comprehensive test suite works."""
        collections = create_comprehensive_test_suite(self.temp_dir)

        # Verify all expected collections
        expected_collections = [
            "deterministic",
            "edge_cases",
            "versioned",
            "dependencies",
            "master_index",
        ]
        for collection_name in expected_collections:
            assert collection_name in collections
            if collection_name != "master_index":
                assert collections[collection_name].exists()
                assert collections[collection_name].is_dir()

    def test_fragment_content_consistency(self):
        """Test that fragment content is deterministic."""
        collection1_dir = self.temp_dir / "collection1"
        collection1_dir.mkdir()
        collection2_dir = self.temp_dir / "collection2"
        collection2_dir.mkdir()

        collection1 = SampleFragmentFactory.create_deterministic_collection(collection1_dir)
        collection2 = SampleFragmentFactory.create_deterministic_collection(collection2_dir)

        # Compare fragment contents
        fragment1 = (collection1 / "agents" / "test-simple-agent.md").read_text()
        fragment2 = (collection2 / "agents" / "test-simple-agent.md").read_text()

        assert fragment1 == fragment2, "Fragment content should be identical across creations"

    def test_edge_case_collection(self):
        """Test edge case collection creation."""
        collection = SampleFragmentFactory.create_edge_case_collection(self.temp_dir)

        # Verify edge case fragments
        assert (collection / "agents" / "minimal-test-agent.md").exists()
        assert (collection / "agents" / "special-chars-agent.md").exists()
        assert (collection / "commands" / "no-params-command.md").exists()
        assert (collection / "hooks" / "minimal-hook.json").exists()

    def test_versioned_collection(self):
        """Test versioned collection creation."""
        collection = SampleFragmentFactory.create_versioned_collection(self.temp_dir)

        # Verify versioned fragments
        assert (collection / "agents" / "versioned-test-agent-v1.md").exists()
        assert (collection / "agents" / "versioned-test-agent-v11.md").exists()
        assert (collection / "agents" / "versioned-test-agent-v2.md").exists()

    def test_dependency_collection(self):
        """Test dependency collection creation."""
        collection = SampleFragmentFactory.create_dependency_collection(self.temp_dir)

        # Verify dependency fragments
        assert (collection / "agents" / "base-agent.md").exists()
        assert (collection / "agents" / "dependent-agent.md").exists()
        assert (collection / "commands" / "integrated-command.md").exists()
