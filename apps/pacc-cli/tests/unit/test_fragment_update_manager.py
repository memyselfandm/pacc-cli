"""Unit tests for Fragment Update Manager."""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from pacc.fragments.update_manager import FragmentUpdateInfo, FragmentUpdateManager


class TestFragmentUpdateManager:
    """Test suite for FragmentUpdateManager."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory with pacc.json."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Create pacc.json with test fragment
        pacc_json = {
            "fragments": {
                "test_fragment": {
                    "title": "Test Fragment",
                    "description": "A test fragment",
                    "reference_path": ".claude/pacc/fragments/test_fragment.md",
                    "storage_type": "project",
                    "installed_at": datetime.now().isoformat(),
                    "source_url": "https://github.com/test/repo.git",
                    "version": "abc12345",
                }
            }
        }

        pacc_json_path = project_dir / "pacc.json"
        pacc_json_path.write_text(json.dumps(pacc_json, indent=2))

        # Create fragment storage directory
        fragment_dir = project_dir / ".claude/pacc/fragments"
        fragment_dir.mkdir(parents=True)

        # Create test fragment file
        fragment_file = fragment_dir / "test_fragment.md"
        fragment_file.write_text("# Test Fragment\n\nContent here")

        return project_dir

    def test_init(self, temp_project):
        """Test update manager initialization."""
        manager = FragmentUpdateManager(project_root=temp_project)
        assert manager.project_root == temp_project
        assert manager.storage_manager is not None
        assert manager.installation_manager is not None
        assert manager.claude_md_manager is not None

    def test_check_for_updates_no_pacc_json(self, tmp_path):
        """Test checking updates when pacc.json doesn't exist."""
        manager = FragmentUpdateManager(project_root=tmp_path)
        updates = manager.check_for_updates()
        assert updates == {}

    def test_check_for_updates_with_fragments(self, temp_project):
        """Test checking for updates with installed fragments."""
        manager = FragmentUpdateManager(project_root=temp_project)

        # Mock the Git check
        with patch.object(manager, "_check_git_update") as mock_check:
            mock_check.return_value = FragmentUpdateInfo(
                name="test_fragment",
                current_version="abc12345",
                latest_version="def67890",
                has_update=True,
                source_url="https://github.com/test/repo.git",
            )

            updates = manager.check_for_updates()

        assert "test_fragment" in updates
        assert updates["test_fragment"].has_update is True
        assert updates["test_fragment"].latest_version == "def67890"

    def test_check_for_updates_filter_by_name(self, temp_project):
        """Test checking updates for specific fragments."""
        manager = FragmentUpdateManager(project_root=temp_project)

        with patch.object(manager, "_check_git_update"):
            updates = manager.check_for_updates(fragment_names=["other_fragment"])

        assert "test_fragment" not in updates

    def test_check_for_updates_filter_by_storage_type(self, temp_project):
        """Test checking updates filtered by storage type."""
        manager = FragmentUpdateManager(project_root=temp_project)

        with patch.object(manager, "_check_git_update") as mock_check:
            mock_check.return_value = FragmentUpdateInfo(
                name="test_fragment",
                current_version="abc12345",
                latest_version="abc12345",
                has_update=False,
                source_url="https://github.com/test/repo.git",
            )

            # Should find project fragments
            updates = manager.check_for_updates(storage_type="project")
            assert "test_fragment" in updates

            # Should not find user fragments
            updates = manager.check_for_updates(storage_type="user")
            assert "test_fragment" not in updates

    @patch("subprocess.run")
    def test_check_git_update(self, mock_run, temp_project):
        """Test checking for Git updates."""
        manager = FragmentUpdateManager(project_root=temp_project)

        # Mock git clone and rev-parse commands
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git clone
            Mock(returncode=0, stdout="def67890\n", stderr=""),  # git rev-parse
        ]

        update_info = FragmentUpdateInfo(
            name="test_fragment",
            current_version="abc12345",
            latest_version=None,
            has_update=False,
            source_url="https://github.com/test/repo.git",
        )

        metadata = {"version": "abc12345"}
        result = manager._check_git_update(update_info, metadata)

        assert result.latest_version == "def67890"
        assert result.has_update is True

    def test_update_fragments_dry_run(self, temp_project):
        """Test dry run update."""
        manager = FragmentUpdateManager(project_root=temp_project)

        # Mock check_for_updates to return an update
        with patch.object(manager, "check_for_updates") as mock_check:
            mock_check.return_value = {
                "test_fragment": FragmentUpdateInfo(
                    name="test_fragment",
                    current_version="abc12345",
                    latest_version="def67890",
                    has_update=True,
                    source_url="https://github.com/test/repo.git",
                )
            }

            result = manager.update_fragments(dry_run=True)

        assert result.dry_run is True
        assert result.updated_count == 1
        assert "Would update test_fragment" in result.changes_made[0]

        # Verify pacc.json wasn't modified
        pacc_json_path = temp_project / "pacc.json"
        config = json.loads(pacc_json_path.read_text())
        assert config["fragments"]["test_fragment"]["version"] == "abc12345"

    def test_update_fragments_no_updates(self, temp_project):
        """Test update when no updates are available."""
        manager = FragmentUpdateManager(project_root=temp_project)

        with patch.object(manager, "check_for_updates") as mock_check:
            mock_check.return_value = {
                "test_fragment": FragmentUpdateInfo(
                    name="test_fragment",
                    current_version="abc12345",
                    latest_version="abc12345",
                    has_update=False,
                    source_url="https://github.com/test/repo.git",
                )
            }

            result = manager.update_fragments()

        assert result.success is True
        assert result.updated_count == 0
        assert "No updates available" in result.changes_made[0]

    def test_create_update_backup(self, temp_project):
        """Test creating backup before updates."""
        manager = FragmentUpdateManager(project_root=temp_project)

        # Create CLAUDE.md file
        claude_md = temp_project / "CLAUDE.md"
        claude_md.write_text("# Test CLAUDE.md")

        backup = manager._create_update_backup()

        assert backup["claude_md"] == "# Test CLAUDE.md"
        assert backup["pacc_json"] is not None
        assert "timestamp" in backup

    def test_rollback_updates(self, temp_project):
        """Test rolling back failed updates."""
        manager = FragmentUpdateManager(project_root=temp_project)

        # Create backup state
        original_pacc = (temp_project / "pacc.json").read_text()
        backup = {"claude_md": "# Original CLAUDE.md", "pacc_json": original_pacc, "fragments": {}}

        # Modify pacc.json
        pacc_json_path = temp_project / "pacc.json"
        config = json.loads(pacc_json_path.read_text())
        config["fragments"]["test_fragment"]["version"] = "modified"
        pacc_json_path.write_text(json.dumps(config))

        # Rollback
        manager._rollback_updates(backup)

        # Verify rollback
        restored_config = json.loads(pacc_json_path.read_text())
        assert restored_config["fragments"]["test_fragment"]["version"] == "abc12345"

    def test_update_fragment_versions(self, temp_project):
        """Test updating fragment versions in pacc.json."""
        manager = FragmentUpdateManager(project_root=temp_project)

        updates = {
            "test_fragment": FragmentUpdateInfo(
                name="test_fragment",
                current_version="abc12345",
                latest_version="def67890",
                has_update=True,
                source_url="https://github.com/test/repo.git",
            )
        }

        manager._update_fragment_versions(updates)

        # Verify pacc.json was updated
        pacc_json_path = temp_project / "pacc.json"
        config = json.loads(pacc_json_path.read_text())
        assert config["fragments"]["test_fragment"]["version"] == "def67890"
        assert "updated_at" in config["fragments"]["test_fragment"]
