"""Tests for plugin repository management."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pacc.errors.exceptions import PACCError
from pacc.plugins.config import PluginConfigManager
from pacc.plugins.repository import (
    GitError,
    PluginInfo,
    PluginRepo,
    PluginRepositoryManager,
    RepositoryStructureError,
    UpdateResult,
)


@pytest.fixture
def temp_plugins_dir():
    """Create temporary plugins directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        plugins_dir = Path(temp_dir) / ".claude" / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        yield plugins_dir


@pytest.fixture
def mock_config_manager():
    """Mock configuration manager."""
    return Mock(spec=PluginConfigManager)


@pytest.fixture
def repo_manager(temp_plugins_dir, mock_config_manager):
    """Create repository manager with temp directory."""
    return PluginRepositoryManager(plugins_dir=temp_plugins_dir, config_manager=mock_config_manager)


@pytest.fixture
def sample_plugin_repo(temp_plugins_dir):
    """Create a sample plugin repository structure."""
    repo_dir = temp_plugins_dir / "repos" / "testuser" / "testplugin"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Create plugin.json
    plugin_dir = repo_dir / "test-plugin"
    plugin_dir.mkdir(exist_ok=True)

    plugin_json = {
        "name": "test-plugin",
        "version": "1.0.0",
        "description": "Test plugin",
        "author": {"name": "Test User"},
    }

    with open(plugin_dir / "plugin.json", "w") as f:
        json.dump(plugin_json, f, indent=2)

    # Create some commands and agents
    (plugin_dir / "commands").mkdir(exist_ok=True)
    (plugin_dir / "agents").mkdir(exist_ok=True)

    # Create a dummy command
    with open(plugin_dir / "commands" / "hello.md", "w") as f:
        f.write("""---
description: Test command
---

Hello $ARGUMENTS!
""")

    return repo_dir


class TestPluginRepositoryManager:
    """Test cases for PluginRepositoryManager."""

    def test_init_creates_repos_directory(self, temp_plugins_dir, mock_config_manager):
        """Test initialization creates repos directory."""
        manager = PluginRepositoryManager(
            plugins_dir=temp_plugins_dir, config_manager=mock_config_manager
        )

        assert manager.repos_dir.exists()
        assert manager.repos_dir == temp_plugins_dir / "repos"

    @patch("pacc.plugins.repository.subprocess.run")
    def test_clone_plugin_success(self, mock_run, repo_manager, mock_config_manager):
        """Test successful plugin cloning."""
        # Mock git clone and git log commands
        mock_run.side_effect = [
            # git clone
            Mock(returncode=0, stdout="", stderr=""),
            # git log -1 --format=%H
            Mock(returncode=0, stdout="abc123def456\n", stderr=""),
        ]
        mock_config_manager.add_repository.return_value = True

        repo_url = "https://github.com/testuser/testplugin.git"
        target_dir = repo_manager.repos_dir / "testuser" / "testplugin"

        # Create fake plugin structure for validation
        target_dir.mkdir(parents=True, exist_ok=True)
        plugin_dir = target_dir / "test-plugin"
        plugin_dir.mkdir(exist_ok=True)

        plugin_json = {"name": "test-plugin", "version": "1.0.0"}

        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_json, f, indent=2)

        # Create some component directories
        (plugin_dir / "commands").mkdir(exist_ok=True)

        result = repo_manager.clone_plugin(repo_url, target_dir)

        assert isinstance(result, PluginRepo)
        assert result.owner == "testuser"
        assert result.repo == "testplugin"
        assert result.path == target_dir
        assert result.commit_sha == "abc123def456"

        # Check git clone was called
        clone_call = mock_run.call_args_list[0]
        assert "git" in clone_call[0][0]
        assert "clone" in clone_call[0][0]
        assert repo_url in clone_call[0][0]

    @patch("pacc.plugins.repository.subprocess.run")
    def test_clone_plugin_git_failure(self, mock_run, repo_manager):
        """Test clone failure due to git error."""
        mock_run.return_value = Mock(
            returncode=128, stdout="", stderr="fatal: repository not found"
        )

        repo_url = "https://github.com/invalid/repo.git"
        target_dir = repo_manager.repos_dir / "invalid" / "repo"

        with pytest.raises(GitError) as exc_info:
            repo_manager.clone_plugin(repo_url, target_dir)

        assert "Git clone failed" in str(exc_info.value)
        assert "fatal: repository not found" in str(exc_info.value)

    @patch("pacc.plugins.repository.subprocess.run")
    def test_update_plugin_success(self, mock_run, repo_manager, sample_plugin_repo):
        """Test successful plugin update."""
        # Mock git status and pull commands
        mock_run.side_effect = [
            # git status --porcelain
            Mock(returncode=0, stdout="", stderr=""),
            # git log -1 --format=%H (before pull)
            Mock(returncode=0, stdout="abc123\n", stderr=""),
            # git pull --ff-only
            Mock(returncode=0, stdout="Already up to date.\n", stderr=""),
            # git log -1 --format=%H (after pull)
            Mock(returncode=0, stdout="abc123\n", stderr=""),
        ]

        result = repo_manager.update_plugin(sample_plugin_repo)

        assert isinstance(result, UpdateResult)
        assert result.success is True
        assert result.had_changes is False
        assert result.old_sha == "abc123"
        assert result.new_sha == "abc123"
        assert "Already up to date" in result.message

    @patch("pacc.plugins.repository.subprocess.run")
    def test_update_plugin_with_changes(self, mock_run, repo_manager, sample_plugin_repo):
        """Test plugin update with actual changes."""
        mock_run.side_effect = [
            # git status --porcelain
            Mock(returncode=0, stdout="", stderr=""),
            # git log -1 --format=%H (before pull)
            Mock(returncode=0, stdout="abc123\n", stderr=""),
            # git pull --ff-only
            Mock(returncode=0, stdout="Updating abc123..def456\nFast-forward\n", stderr=""),
            # git log -1 --format=%H (after pull)
            Mock(returncode=0, stdout="def456\n", stderr=""),
        ]

        result = repo_manager.update_plugin(sample_plugin_repo)

        assert result.success is True
        assert result.had_changes is True
        assert result.old_sha == "abc123"
        assert result.new_sha == "def456"

    @patch("pacc.plugins.repository.subprocess.run")
    def test_update_plugin_dirty_working_tree(self, mock_run, repo_manager, sample_plugin_repo):
        """Test update fails with dirty working tree."""
        # git status --porcelain returns modified files
        mock_run.return_value = Mock(returncode=0, stdout=" M some-file.txt\n", stderr="")

        result = repo_manager.update_plugin(sample_plugin_repo)

        assert result.success is False
        assert "dirty working tree" in result.error_message.lower()

    @patch("pacc.plugins.repository.subprocess.run")
    def test_update_plugin_merge_conflict(self, mock_run, repo_manager, sample_plugin_repo):
        """Test update fails due to merge conflict."""
        mock_run.side_effect = [
            # git status --porcelain (clean)
            Mock(returncode=0, stdout="", stderr=""),
            # git log -1 --format=%H (before pull)
            Mock(returncode=0, stdout="abc123\n", stderr=""),
            # git pull --ff-only (fails)
            Mock(returncode=1, stdout="", stderr="fatal: Not possible to fast-forward"),
        ]

        result = repo_manager.update_plugin(sample_plugin_repo)

        assert result.success is False
        assert "merge conflict" in result.error_message.lower()

    @patch("pacc.plugins.repository.subprocess.run")
    def test_rollback_plugin_success(self, mock_run, repo_manager, sample_plugin_repo):
        """Test successful plugin rollback."""
        mock_run.side_effect = [
            # git rev-parse --verify
            Mock(returncode=0, stdout="", stderr=""),
            # git reset --hard
            Mock(returncode=0, stdout="", stderr=""),
        ]

        commit_sha = "abc123def456"
        result = repo_manager.rollback_plugin(sample_plugin_repo, commit_sha)

        assert result is True

        # Check both git commands were called
        assert len(mock_run.call_args_list) == 2

        # Check git rev-parse was called first
        verify_call = mock_run.call_args_list[0]
        assert "git" in verify_call[0][0]
        assert "rev-parse" in verify_call[0][0]
        assert "--verify" in verify_call[0][0]
        assert commit_sha in verify_call[0][0]

        # Check git reset was called second
        reset_call = mock_run.call_args_list[1]
        assert "git" in reset_call[0][0]
        assert "reset" in reset_call[0][0]
        assert "--hard" in reset_call[0][0]
        assert commit_sha in reset_call[0][0]

    @patch("pacc.plugins.repository.subprocess.run")
    def test_rollback_plugin_failure(self, mock_run, repo_manager, sample_plugin_repo):
        """Test rollback failure."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="fatal: invalid object name")

        result = repo_manager.rollback_plugin(sample_plugin_repo, "invalid_sha")

        assert result is False

    def test_get_plugin_info_success(self, repo_manager, sample_plugin_repo):
        """Test getting plugin information."""
        info = repo_manager.get_plugin_info(sample_plugin_repo)

        assert isinstance(info, PluginInfo)
        assert info.owner == "testuser"
        assert info.repo == "testplugin"
        assert len(info.plugins) == 1
        assert "test-plugin" in info.plugins

    def test_get_plugin_info_invalid_path(self, repo_manager, temp_plugins_dir):
        """Test get plugin info with invalid path."""
        invalid_path = temp_plugins_dir / "nonexistent"

        with pytest.raises(PACCError):
            repo_manager.get_plugin_info(invalid_path)

    def test_validate_repository_structure_valid(self, repo_manager, sample_plugin_repo):
        """Test validation of valid repository structure."""
        result = repo_manager.validate_repository_structure(sample_plugin_repo)

        assert result.is_valid is True
        assert len(result.plugins_found) == 1
        assert "test-plugin" in result.plugins_found

    def test_validate_repository_structure_no_plugins(self, repo_manager, temp_plugins_dir):
        """Test validation of repository with no plugins."""
        empty_repo = temp_plugins_dir / "repos" / "empty" / "repo"
        empty_repo.mkdir(parents=True, exist_ok=True)

        result = repo_manager.validate_repository_structure(empty_repo)

        assert result.is_valid is False
        assert len(result.plugins_found) == 0
        assert "no plugins found" in result.error_message.lower()

    def test_parse_repo_url_github_https(self, repo_manager):
        """Test parsing GitHub HTTPS URL."""
        url = "https://github.com/owner/repo.git"
        owner, repo = repo_manager._parse_repo_url(url)

        assert owner == "owner"
        assert repo == "repo"

    def test_parse_repo_url_github_ssh(self, repo_manager):
        """Test parsing GitHub SSH URL."""
        url = "git@github.com:owner/repo.git"
        owner, repo = repo_manager._parse_repo_url(url)

        assert owner == "owner"
        assert repo == "repo"

    def test_parse_repo_url_invalid(self, repo_manager):
        """Test parsing invalid URL."""
        with pytest.raises(ValueError):
            repo_manager._parse_repo_url("invalid-url")

    @patch("pacc.plugins.repository.subprocess.run")
    def test_get_current_commit_sha(self, mock_run, repo_manager, sample_plugin_repo):
        """Test getting current commit SHA."""
        mock_run.return_value = Mock(returncode=0, stdout="abc123def456\n", stderr="")

        sha = repo_manager._get_current_commit_sha(sample_plugin_repo)

        assert sha == "abc123def456"

    @patch("pacc.plugins.repository.subprocess.run")
    def test_is_working_tree_clean_true(self, mock_run, repo_manager, sample_plugin_repo):
        """Test checking clean working tree."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        is_clean = repo_manager._is_working_tree_clean(sample_plugin_repo)

        assert is_clean is True

    @patch("pacc.plugins.repository.subprocess.run")
    def test_is_working_tree_clean_false(self, mock_run, repo_manager, sample_plugin_repo):
        """Test checking dirty working tree."""
        mock_run.return_value = Mock(returncode=0, stdout=" M file.txt\n", stderr="")

        is_clean = repo_manager._is_working_tree_clean(sample_plugin_repo)

        assert is_clean is False

    def test_discover_plugins_in_repo(self, repo_manager, sample_plugin_repo):
        """Test discovering plugins in repository."""
        plugins = repo_manager._discover_plugins_in_repo(sample_plugin_repo)

        assert len(plugins) == 1
        assert "test-plugin" in plugins

    def test_discover_plugins_nested_structure(self, repo_manager, temp_plugins_dir):
        """Test discovering plugins in nested structure."""
        repo_dir = temp_plugins_dir / "repos" / "owner" / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)

        # Create nested plugin structure
        nested_plugin = repo_dir / "category" / "my-plugin"
        nested_plugin.mkdir(parents=True, exist_ok=True)

        plugin_json = {"name": "nested-plugin", "version": "1.0.0"}

        with open(nested_plugin / "plugin.json", "w") as f:
            json.dump(plugin_json, f)

        plugins = repo_manager._discover_plugins_in_repo(repo_dir)

        assert len(plugins) == 1
        assert "category/my-plugin" in plugins


class TestDataClasses:
    """Test plugin repository data classes."""

    def test_plugin_repo_creation(self):
        """Test PluginRepo creation."""
        path = Path("/path/to/repo")
        repo = PluginRepo(
            owner="testowner",
            repo="testrepo",
            path=path,
            url="https://github.com/testowner/testrepo.git",
        )

        assert repo.owner == "testowner"
        assert repo.repo == "testrepo"
        assert repo.path == path
        assert repo.full_name == "testowner/testrepo"

    def test_update_result_success(self):
        """Test UpdateResult for successful update."""
        result = UpdateResult(
            success=True,
            had_changes=True,
            old_sha="abc123",
            new_sha="def456",
            message="Updated successfully",
        )

        assert result.success is True
        assert result.had_changes is True
        assert result.old_sha == "abc123"
        assert result.new_sha == "def456"

    def test_plugin_info_creation(self):
        """Test PluginInfo creation."""
        info = PluginInfo(
            owner="owner", repo="repo", plugins=["plugin1", "plugin2"], path=Path("/path")
        )

        assert info.owner == "owner"
        assert info.repo == "repo"
        assert len(info.plugins) == 2
        assert "plugin1" in info.plugins


class TestPluginUpdateWorkflows:
    """Test comprehensive update workflows and edge cases."""

    @patch("pacc.plugins.repository.subprocess.run")
    def test_update_detection_behind_commits(self, mock_run, repo_manager, sample_plugin_repo):
        """Test detection of commits behind remote."""
        mock_run.side_effect = [
            # git fetch --dry-run
            Mock(returncode=0, stdout="", stderr=""),
            # git rev-parse origin/HEAD
            Mock(returncode=0, stdout="def456\n", stderr=""),
            # Current commit
            Mock(returncode=0, stdout="abc123\n", stderr=""),
            # git rev-list --count
            Mock(returncode=0, stdout="3\n", stderr=""),
            # git log --oneline
            Mock(
                returncode=0,
                stdout="def456 Fix bug\n789abc Add feature\n321def Update docs\n",
                stderr="",
            ),
        ]

        # This would be called by the CLI's _show_update_preview method
        # which uses the repo manager's methods

        # Test that we can get current commit SHA
        current_sha = repo_manager._get_current_commit_sha(sample_plugin_repo)
        assert current_sha  # Should return a SHA

    @patch("pacc.plugins.repository.subprocess.run")
    def test_update_with_force_rollback(self, mock_run, repo_manager, sample_plugin_repo):
        """Test force update with automatic rollback on failure."""
        mock_run.side_effect = [
            # git status --porcelain (dirty tree)
            Mock(returncode=0, stdout=" M some-file.txt\n", stderr=""),
            # git log -1 --format=%H (get old SHA)
            Mock(returncode=0, stdout="abc123\n", stderr=""),
            # git pull --ff-only (fails)
            Mock(returncode=1, stdout="", stderr="fatal: merge conflict"),
            # git rev-parse --verify (for rollback)
            Mock(returncode=0, stdout="", stderr=""),
            # git reset --hard (rollback)
            Mock(returncode=0, stdout="", stderr=""),
        ]

        # Test normal update with dirty tree fails
        result = repo_manager.update_plugin(sample_plugin_repo)
        assert result.success is False
        assert "dirty working tree" in result.error_message.lower()

        # Test rollback functionality
        rollback_result = repo_manager.rollback_plugin(sample_plugin_repo, "abc123")
        assert rollback_result is True

    @patch("pacc.plugins.repository.subprocess.run")
    def test_update_validation_after_pull(self, mock_run, repo_manager, sample_plugin_repo):
        """Test repository validation after successful update."""
        mock_run.side_effect = [
            # git status --porcelain
            Mock(returncode=0, stdout="", stderr=""),
            # git log -1 --format=%H (before)
            Mock(returncode=0, stdout="abc123\n", stderr=""),
            # git pull --ff-only
            Mock(returncode=0, stdout="Updating abc123..def456\n", stderr=""),
            # git log -1 --format=%H (after)
            Mock(returncode=0, stdout="def456\n", stderr=""),
        ]

        result = repo_manager.update_plugin(sample_plugin_repo)

        assert result.success is True
        assert result.had_changes is True
        assert result.old_sha == "abc123"
        assert result.new_sha == "def456"

        # Verify the repository is still valid after update
        validation_result = repo_manager.validate_repository_structure(sample_plugin_repo)
        assert validation_result.is_valid is True

    @patch("pacc.plugins.repository.subprocess.run")
    def test_update_timeout_handling(self, mock_run, repo_manager, sample_plugin_repo):
        """Test handling of git command timeouts during update."""
        # Simulate timeout on git pull
        mock_run.side_effect = [
            # git status --porcelain
            Mock(returncode=0, stdout="", stderr=""),
            # git log -1 --format=%H
            Mock(returncode=0, stdout="abc123\n", stderr=""),
            # git pull --ff-only (timeout)
            subprocess.TimeoutExpired("git", 120),
        ]

        result = repo_manager.update_plugin(sample_plugin_repo)

        assert result.success is False
        assert "timed out" in result.error_message.lower()

    def test_update_nonexistent_repository(self, repo_manager, temp_plugins_dir):
        """Test update attempt on non-existent repository."""
        nonexistent_path = temp_plugins_dir / "repos" / "missing" / "repo"

        result = repo_manager.update_plugin(nonexistent_path)

        assert result.success is False
        assert "does not exist" in result.error_message

    @patch("pacc.plugins.repository.subprocess.run")
    def test_update_no_remote_configured(self, mock_run, repo_manager, sample_plugin_repo):
        """Test update when no remote is configured."""
        mock_run.side_effect = [
            # git status --porcelain
            Mock(returncode=0, stdout="", stderr=""),
            # git log -1 --format=%H
            Mock(returncode=0, stdout="abc123\n", stderr=""),
            # git pull --ff-only (no remote)
            Mock(returncode=1, stdout="", stderr="fatal: no remote repository"),
        ]

        result = repo_manager.update_plugin(sample_plugin_repo)

        assert result.success is False
        assert "no remote repository" in result.error_message

    @patch("pacc.plugins.repository.subprocess.run")
    def test_rollback_invalid_commit(self, mock_run, repo_manager, sample_plugin_repo):
        """Test rollback with invalid commit SHA."""
        mock_run.return_value = Mock(
            returncode=1, stdout="", stderr="fatal: invalid object name 'invalid_sha'"
        )

        result = repo_manager.rollback_plugin(sample_plugin_repo, "invalid_sha")

        assert result is False

    @patch("pacc.plugins.repository.subprocess.run")
    def test_get_commit_sha_git_error(self, mock_run, repo_manager, sample_plugin_repo):
        """Test getting commit SHA with git error."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="fatal: not a git repository")

        with pytest.raises(GitError):
            repo_manager._get_current_commit_sha(sample_plugin_repo)

    def test_repository_validation_missing_plugin_json(self, repo_manager, temp_plugins_dir):
        """Test repository validation with missing plugin.json files."""
        repo_dir = temp_plugins_dir / "repos" / "test" / "incomplete"
        repo_dir.mkdir(parents=True)

        # Create plugin directory but no plugin.json
        plugin_dir = repo_dir / "incomplete-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "commands").mkdir()

        # Create command file
        with open(plugin_dir / "commands" / "test.md", "w") as f:
            f.write("---\ndescription: Test\n---\nTest command")

        result = repo_manager.validate_repository_structure(repo_dir)

        # Should still be valid but with warnings
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("missing plugin.json" in warning for warning in result.warnings)

    def test_repository_validation_malformed_plugin_json(self, repo_manager, temp_plugins_dir):
        """Test repository validation with malformed plugin.json."""
        repo_dir = temp_plugins_dir / "repos" / "test" / "malformed"
        repo_dir.mkdir(parents=True)

        plugin_dir = repo_dir / "bad-plugin"
        plugin_dir.mkdir()

        # Create malformed plugin.json
        with open(plugin_dir / "plugin.json", "w") as f:
            f.write("{ invalid json }")

        (plugin_dir / "commands").mkdir()

        result = repo_manager.validate_repository_structure(repo_dir)

        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("invalid plugin.json" in warning for warning in result.warnings)


class TestErrorHandling:
    """Test error handling in repository management."""

    def test_git_error_creation(self):
        """Test GitError exception."""
        error = GitError("Git command failed", "CLONE_FAILED", {"repo": "test"})

        assert "Git command failed" in str(error)
        assert error.error_code == "CLONE_FAILED"
        assert error.context["repo"] == "test"

    def test_repository_structure_error(self):
        """Test RepositoryStructureError exception."""
        error = RepositoryStructureError("Invalid structure")

        assert "Invalid structure" in str(error)
        assert error.error_code == "REPOSITORYSTRUCTUREERROR"


class TestGitConversionIntegration:
    """Test Git conversion and repository creation functionality."""

    @pytest.fixture
    def sample_plugin_structure(self, temp_plugins_dir):
        """Create a sample plugin structure for conversion testing."""
        plugin_dir = temp_plugins_dir / "converted-plugin"
        plugin_dir.mkdir(parents=True)

        # Create plugin.json
        plugin_json = {
            "name": "converted-plugin",
            "version": "1.0.0",
            "description": "A converted plugin from existing extensions",
            "author": {
                "name": "Test Author",
                "email": "test@example.com",
                "url": "https://example.com",
            },
        }

        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_json, f, indent=2)

        # Create commands directory with sample commands
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir()

        # Create a few sample commands
        with open(commands_dir / "hello.md", "w") as f:
            f.write("""---
description: Say hello to someone
parameters:
  - name: target
    description: Who to greet
---

Hello $ARGUMENTS!
""")

        # Create nested command
        nested_dir = commands_dir / "utils"
        nested_dir.mkdir()
        with open(nested_dir / "debug.md", "w") as f:
            f.write("""---
description: Debug utility command
---

Debug mode activated!
""")

        # Create agents directory with sample agents
        agents_dir = plugin_dir / "agents"
        agents_dir.mkdir()

        with open(agents_dir / "helper.md", "w") as f:
            f.write("""---
name: Helper Agent
description: Helpful assistant
version: 1.0
---

I'm here to help!
""")

        # Create hooks directory with hooks.json
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir()

        hooks_data = {
            "onFileChange": {
                "description": "Runs when files change",
                "action": "echo 'File changed: $FILE'",
            },
            "onStartup": {"description": "Runs on startup", "action": "echo 'Plugin started'"},
        }

        with open(hooks_dir / "hooks.json", "w") as f:
            json.dump(hooks_data, f, indent=2)

        return plugin_dir

    @patch("pacc.plugins.repository.subprocess.run")
    def test_create_plugin_repository_success(
        self, mock_run, repo_manager, sample_plugin_structure
    ):
        """Test successful plugin repository creation."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Read plugin metadata
        with open(sample_plugin_structure / "plugin.json") as f:
            plugin_metadata = json.load(f)

        result = repo_manager.create_plugin_repository(
            sample_plugin_structure, plugin_metadata, init_git=True
        )

        assert result is True

        # Check that README.md was created
        readme_path = sample_plugin_structure / "README.md"
        assert readme_path.exists()

        # Check that .gitignore was created
        gitignore_path = sample_plugin_structure / ".gitignore"
        assert gitignore_path.exists()

        # Verify git init was called
        mock_run.assert_called_once()
        git_call = mock_run.call_args_list[0]
        assert "git" in git_call[0][0]
        assert "init" in git_call[0][0]

    def test_create_plugin_repository_without_git(self, repo_manager, sample_plugin_structure):
        """Test plugin repository creation without Git initialization."""
        # Read plugin metadata
        with open(sample_plugin_structure / "plugin.json") as f:
            plugin_metadata = json.load(f)

        result = repo_manager.create_plugin_repository(
            sample_plugin_structure, plugin_metadata, init_git=False
        )

        assert result is True

        # Check that files were still created
        readme_path = sample_plugin_structure / "README.md"
        assert readme_path.exists()

        gitignore_path = sample_plugin_structure / ".gitignore"
        assert gitignore_path.exists()

    @patch("pacc.plugins.repository.subprocess.run")
    def test_create_plugin_repository_git_failure(
        self, mock_run, repo_manager, sample_plugin_structure
    ):
        """Test plugin repository creation with Git init failure."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="fatal: not a valid directory")

        with open(sample_plugin_structure / "plugin.json") as f:
            plugin_metadata = json.load(f)

        from pacc.plugins.repository import GitError

        with pytest.raises(GitError) as exc_info:
            repo_manager.create_plugin_repository(
                sample_plugin_structure, plugin_metadata, init_git=True
            )

        assert "Failed to initialize Git repository" in str(exc_info.value)

    def test_create_plugin_repository_invalid_structure(self, repo_manager, temp_plugins_dir):
        """Test plugin repository creation with invalid plugin structure."""
        invalid_dir = temp_plugins_dir / "invalid-plugin"
        invalid_dir.mkdir()

        # Create empty plugin.json without required fields
        with open(invalid_dir / "plugin.json", "w") as f:
            json.dump({}, f)

        from pacc.errors.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            repo_manager.create_plugin_repository(invalid_dir, {}, init_git=False)

        assert "Invalid plugin structure" in str(exc_info.value)

    def test_generate_readme_comprehensive(self, repo_manager, sample_plugin_structure):
        """Test comprehensive README generation from plugin metadata."""
        plugin_metadata = {
            "name": "awesome-plugin",
            "version": "2.1.0",
            "description": "An awesome plugin for Claude Code",
            "author": {
                "name": "Jane Developer",
                "email": "jane@dev.com",
                "url": "https://janedev.com",
            },
        }

        readme_content = repo_manager.generate_readme(plugin_metadata, sample_plugin_structure)

        # Check title and basic info
        assert "# awesome-plugin" in readme_content
        assert "An awesome plugin for Claude Code" in readme_content
        assert "**Version:** 2.1.0" in readme_content

        # Check author information
        assert "**Author:** Jane Developer <jane@dev.com>" in readme_content
        assert "[Website](https://janedev.com)" in readme_content

        # Check components section
        assert "## Components" in readme_content
        assert "**Commands:** 2 custom commands" in readme_content
        assert "- `hello`" in readme_content
        assert "- `utils/debug`" in readme_content

        assert "**Agents:** 1 specialized agents" in readme_content
        assert "- `helper`" in readme_content

        assert "**Hooks:** 2 event hooks" in readme_content
        assert "- `onFileChange`" in readme_content
        assert "- `onStartup`" in readme_content

        # Check installation and usage sections
        assert "## Installation" in readme_content
        assert "pacc plugin install" in readme_content
        assert "## Usage" in readme_content
        assert "### Commands" in readme_content
        assert "### Agents" in readme_content
        assert "### Hooks" in readme_content

        # Check requirements
        assert "## Requirements" in readme_content
        assert "Claude Code v1.0.81" in readme_content
        assert "ENABLE_PLUGINS=1" in readme_content

    def test_generate_readme_minimal_metadata(self, repo_manager, temp_plugins_dir):
        """Test README generation with minimal plugin metadata."""
        # Create minimal plugin structure
        plugin_dir = temp_plugins_dir / "minimal-plugin"
        plugin_dir.mkdir()

        # Create empty plugin.json with just name
        plugin_json = {"name": "minimal-plugin"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_json, f)

        readme_content = repo_manager.generate_readme(plugin_json, plugin_dir)

        assert "# minimal-plugin" in readme_content
        assert "A Claude Code plugin" in readme_content  # Default description
        assert "**Version:** 1.0.0" in readme_content  # Default version
        assert "No components detected" in readme_content

    def test_generate_readme_no_author(self, repo_manager, temp_plugins_dir):
        """Test README generation without author information."""
        plugin_dir = temp_plugins_dir / "no-author-plugin"
        plugin_dir.mkdir()

        plugin_json = {"name": "no-author-plugin", "description": "Plugin without author"}

        readme_content = repo_manager.generate_readme(plugin_json, plugin_dir)

        assert "# no-author-plugin" in readme_content
        assert "Plugin without author" in readme_content
        # Should not contain author section
        assert "**Author:**" not in readme_content

    def test_create_gitignore_content(self, repo_manager):
        """Test .gitignore content generation."""
        gitignore_content = repo_manager.create_gitignore()

        # Check for common patterns
        assert ".DS_Store" in gitignore_content
        assert "__pycache__/" in gitignore_content
        assert "*.log" in gitignore_content
        assert ".env" in gitignore_content
        assert "node_modules/" in gitignore_content
        assert ".claude/local/" in gitignore_content

        # Check structure
        assert "# OS-specific files" in gitignore_content
        assert "# Python" in gitignore_content
        assert "# Claude Code specific" in gitignore_content

    @patch("pacc.plugins.repository.subprocess.run")
    def test_commit_plugin_success(self, mock_run, repo_manager, sample_plugin_structure):
        """Test successful plugin commit."""
        # Mock git commands
        mock_run.side_effect = [
            # git add .
            Mock(returncode=0, stdout="", stderr=""),
            # git commit -m
            Mock(returncode=0, stdout="[main abc123] Initial commit\n", stderr=""),
        ]

        # Create .git directory to simulate initialized repo
        git_dir = sample_plugin_structure / ".git"
        git_dir.mkdir()

        result = repo_manager.commit_plugin(sample_plugin_structure)

        assert result is True

        # Check git commands were called
        assert len(mock_run.call_args_list) == 2

        # Check git add was called first
        add_call = mock_run.call_args_list[0]
        assert "git" in add_call[0][0]
        assert "add" in add_call[0][0]
        assert "." in add_call[0][0]

        # Check git commit was called with auto-generated message
        commit_call = mock_run.call_args_list[1]
        assert "git" in commit_call[0][0]
        assert "commit" in commit_call[0][0]
        assert "-m" in commit_call[0][0]
        # Check commit message contains plugin name
        commit_message = commit_call[0][0][-1]
        assert "converted-plugin" in commit_message
        assert "PACC plugin converter" in commit_message

    @patch("pacc.plugins.repository.subprocess.run")
    def test_commit_plugin_custom_message(self, mock_run, repo_manager, sample_plugin_structure):
        """Test plugin commit with custom message."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git add
            Mock(returncode=0, stdout="", stderr=""),  # git commit
        ]

        git_dir = sample_plugin_structure / ".git"
        git_dir.mkdir()

        custom_message = "Custom commit message for testing"
        result = repo_manager.commit_plugin(sample_plugin_structure, custom_message)

        assert result is True

        # Check custom message was used
        commit_call = mock_run.call_args_list[1]
        assert custom_message in commit_call[0][0]

    @patch("pacc.plugins.repository.subprocess.run")
    def test_commit_plugin_nothing_to_commit(self, mock_run, repo_manager, sample_plugin_structure):
        """Test commit when there are no changes."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git add
            Mock(
                returncode=1, stdout="nothing to commit, working tree clean", stderr=""
            ),  # git commit
        ]

        git_dir = sample_plugin_structure / ".git"
        git_dir.mkdir()

        result = repo_manager.commit_plugin(sample_plugin_structure)

        # Should still return True when nothing to commit
        assert result is True

    def test_commit_plugin_not_git_repo(self, repo_manager, sample_plugin_structure):
        """Test commit failure when directory is not a Git repository."""
        # No .git directory exists
        result = repo_manager.commit_plugin(sample_plugin_structure)

        assert result is False

    @patch("pacc.plugins.repository.subprocess.run")
    def test_push_plugin_success(self, mock_run, repo_manager, sample_plugin_structure):
        """Test successful plugin push to remote repository."""
        mock_run.side_effect = [
            # git remote get-url origin (doesn't exist)
            Mock(returncode=1, stdout="", stderr=""),
            # git remote add origin
            Mock(returncode=0, stdout="", stderr=""),
            # git push -u origin main
            Mock(returncode=0, stdout="To github.com:user/repo.git\n", stderr=""),
        ]

        git_dir = sample_plugin_structure / ".git"
        git_dir.mkdir()

        repo_url = "https://github.com/user/repo.git"
        result = repo_manager.push_plugin(sample_plugin_structure, repo_url)

        assert result is True

        # Check commands were called in order
        assert len(mock_run.call_args_list) == 3

        # Check remote add was called
        remote_add_call = mock_run.call_args_list[1]
        assert "git" in remote_add_call[0][0]
        assert "remote" in remote_add_call[0][0]
        assert "add" in remote_add_call[0][0]
        assert "origin" in remote_add_call[0][0]
        assert repo_url in remote_add_call[0][0]

        # Check push was called
        push_call = mock_run.call_args_list[2]
        assert "git" in push_call[0][0]
        assert "push" in push_call[0][0]
        assert "-u" in push_call[0][0]
        assert "origin" in push_call[0][0]
        assert "main" in push_call[0][0]

    @patch("pacc.plugins.repository.subprocess.run")
    def test_push_plugin_update_existing_remote(
        self, mock_run, repo_manager, sample_plugin_structure
    ):
        """Test push with existing remote origin."""
        mock_run.side_effect = [
            # git remote get-url origin (exists)
            Mock(returncode=0, stdout="https://old-url.git\n", stderr=""),
            # git remote set-url origin
            Mock(returncode=0, stdout="", stderr=""),
            # git push -u origin main
            Mock(returncode=0, stdout="", stderr=""),
        ]

        git_dir = sample_plugin_structure / ".git"
        git_dir.mkdir()

        repo_url = "https://github.com/user/repo.git"
        result = repo_manager.push_plugin(sample_plugin_structure, repo_url)

        assert result is True

        # Check remote set-url was called
        remote_seturl_call = mock_run.call_args_list[1]
        assert "set-url" in remote_seturl_call[0][0]

    @patch("pacc.plugins.repository.subprocess.run")
    def test_push_plugin_authentication_failure(
        self, mock_run, repo_manager, sample_plugin_structure
    ):
        """Test push failure due to authentication error."""
        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr=""),  # git remote get-url
            Mock(returncode=0, stdout="", stderr=""),  # git remote add
            Mock(returncode=1, stdout="", stderr="remote: authentication failed"),  # git push
        ]

        git_dir = sample_plugin_structure / ".git"
        git_dir.mkdir()

        repo_url = "https://github.com/user/private-repo.git"
        result = repo_manager.push_plugin(sample_plugin_structure, repo_url)

        assert result is False

    @patch("pacc.plugins.repository.subprocess.run")
    def test_push_plugin_repository_not_found(
        self, mock_run, repo_manager, sample_plugin_structure
    ):
        """Test push failure when repository doesn't exist."""
        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr=""),  # git remote get-url
            Mock(returncode=0, stdout="", stderr=""),  # git remote add
            Mock(returncode=1, stdout="", stderr="remote: repository not found"),  # git push
        ]

        git_dir = sample_plugin_structure / ".git"
        git_dir.mkdir()

        repo_url = "https://github.com/user/nonexistent.git"
        result = repo_manager.push_plugin(sample_plugin_structure, repo_url)

        assert result is False

    def test_push_plugin_custom_branch(self, repo_manager, sample_plugin_structure):
        """Test push to custom branch."""
        with patch("pacc.plugins.repository.subprocess.run") as mock_run:
            mock_run.side_effect = [
                Mock(returncode=1, stdout="", stderr=""),  # git remote get-url
                Mock(returncode=0, stdout="", stderr=""),  # git remote add
                Mock(returncode=0, stdout="", stderr=""),  # git push
            ]

            git_dir = sample_plugin_structure / ".git"
            git_dir.mkdir()

            repo_url = "https://github.com/user/repo.git"
            result = repo_manager.push_plugin(sample_plugin_structure, repo_url, branch="develop")

            assert result is True

            # Check develop branch was used
            push_call = mock_run.call_args_list[2]
            assert "develop" in push_call[0][0]

    def test_validate_plugin_structure_valid(self, repo_manager, sample_plugin_structure):
        """Test validation of valid plugin structure."""
        result = repo_manager._validate_plugin_structure(sample_plugin_structure)

        assert result is True

    def test_validate_plugin_structure_missing_json(self, repo_manager, temp_plugins_dir):
        """Test validation with missing plugin.json."""
        invalid_dir = temp_plugins_dir / "invalid"
        invalid_dir.mkdir()

        result = repo_manager._validate_plugin_structure(invalid_dir)

        assert result is False

    def test_validate_plugin_structure_invalid_json(self, repo_manager, temp_plugins_dir):
        """Test validation with invalid plugin.json."""
        invalid_dir = temp_plugins_dir / "invalid"
        invalid_dir.mkdir()

        # Create malformed JSON
        with open(invalid_dir / "plugin.json", "w") as f:
            f.write("{ invalid json content }")

        result = repo_manager._validate_plugin_structure(invalid_dir)

        assert result is False

    def test_analyze_plugin_components_comprehensive(self, repo_manager, sample_plugin_structure):
        """Test comprehensive plugin component analysis."""
        components = repo_manager._analyze_plugin_components(sample_plugin_structure)

        assert len(components["commands"]) == 2
        assert "hello" in components["commands"]
        assert "utils/debug" in components["commands"]

        assert len(components["agents"]) == 1
        assert "helper" in components["agents"]

        assert len(components["hooks"]) == 2
        assert "onFileChange" in components["hooks"]
        assert "onStartup" in components["hooks"]

    def test_analyze_plugin_components_empty(self, repo_manager, temp_plugins_dir):
        """Test component analysis with empty plugin."""
        empty_dir = temp_plugins_dir / "empty"
        empty_dir.mkdir()

        components = repo_manager._analyze_plugin_components(empty_dir)

        assert len(components["commands"]) == 0
        assert len(components["agents"]) == 0
        assert len(components["hooks"]) == 0

    def test_prepare_authenticated_url_github_token(self, repo_manager):
        """Test URL preparation with GitHub token."""
        url = "https://github.com/user/repo.git"
        auth = {"token": "ghp_1234567890"}

        result = repo_manager._prepare_authenticated_url(url, auth)

        assert result == "https://ghp_1234567890@github.com/user/repo.git"

    def test_prepare_authenticated_url_gitlab_token(self, repo_manager):
        """Test URL preparation with GitLab token."""
        url = "https://gitlab.com/user/repo.git"
        auth = {"token": "glpat_1234567890"}

        result = repo_manager._prepare_authenticated_url(url, auth)

        assert result == "https://oauth2:glpat_1234567890@gitlab.com/user/repo.git"

    def test_prepare_authenticated_url_bitbucket_token(self, repo_manager):
        """Test URL preparation with Bitbucket token."""
        url = "https://bitbucket.org/user/repo.git"
        auth = {"token": "app_password_123"}

        result = repo_manager._prepare_authenticated_url(url, auth)

        assert result == "https://x-token-auth:app_password_123@bitbucket.org/user/repo.git"

    def test_prepare_authenticated_url_username_password(self, repo_manager):
        """Test URL preparation with username and password."""
        url = "https://github.com/user/repo.git"
        auth = {"username": "testuser", "password": "testpass"}

        result = repo_manager._prepare_authenticated_url(url, auth)

        assert result == "https://testuser:testpass@github.com/user/repo.git"

    def test_prepare_authenticated_url_ssh(self, repo_manager):
        """Test URL preparation with SSH (should return unchanged)."""
        url = "git@github.com:user/repo.git"
        auth = {"token": "should_be_ignored"}

        result = repo_manager._prepare_authenticated_url(url, auth)

        # SSH URLs should be returned unchanged
        assert result == url

    def test_prepare_authenticated_url_no_auth(self, repo_manager):
        """Test URL preparation without authentication."""
        url = "https://github.com/user/repo.git"

        result = repo_manager._prepare_authenticated_url(url, None)

        assert result == url


class TestGitConversionWorkflows:
    """Test complete conversion workflows end-to-end."""

    @patch("pacc.plugins.repository.subprocess.run")
    def test_complete_conversion_workflow(self, mock_run, repo_manager, temp_plugins_dir):
        """Test complete plugin conversion workflow from start to finish."""
        # Create plugin structure
        plugin_dir = temp_plugins_dir / "workflow-plugin"
        plugin_dir.mkdir()

        plugin_metadata = {
            "name": "workflow-plugin",
            "version": "1.0.0",
            "description": "Complete workflow test plugin",
            "author": {"name": "Test Developer"},
        }

        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_metadata, f, indent=2)

        # Add some components
        (plugin_dir / "commands").mkdir()
        with open(plugin_dir / "commands" / "test.md", "w") as f:
            f.write("---\ndescription: Test command\n---\nTest content")

        # Mock all Git operations
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git init
            Mock(returncode=0, stdout="", stderr=""),  # git add .
            Mock(returncode=0, stdout="", stderr=""),  # git commit
            Mock(returncode=1, stdout="", stderr=""),  # git remote get-url (doesn't exist)
            Mock(returncode=0, stdout="", stderr=""),  # git remote add
            Mock(returncode=0, stdout="", stderr=""),  # git push
        ]

        # 1. Create repository
        create_result = repo_manager.create_plugin_repository(plugin_dir, plugin_metadata)
        assert create_result is True

        # Manually create .git directory since we're mocking git init
        (plugin_dir / ".git").mkdir()

        # 2. Commit plugin
        commit_result = repo_manager.commit_plugin(plugin_dir)
        assert commit_result is True

        # 3. Push to remote (Git directory already exists from step 2)
        push_result = repo_manager.push_plugin(
            plugin_dir, "https://github.com/user/workflow-plugin.git"
        )
        assert push_result is True

        # Verify all files were created
        assert (plugin_dir / "README.md").exists()
        assert (plugin_dir / ".gitignore").exists()

        # Check README content
        with open(plugin_dir / "README.md") as f:
            readme_content = f.read()
            assert "workflow-plugin" in readme_content
            assert "Complete workflow test plugin" in readme_content
            assert "Test Developer" in readme_content

    @patch("pacc.plugins.repository.subprocess.run")
    def test_conversion_with_authentication(self, mock_run, repo_manager, temp_plugins_dir):
        """Test conversion workflow with authentication."""
        plugin_dir = temp_plugins_dir / "auth-plugin"
        plugin_dir.mkdir()

        plugin_metadata = {"name": "auth-plugin", "version": "1.0.0"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_metadata, f)

        (plugin_dir / "commands").mkdir()
        git_dir = plugin_dir / ".git"
        git_dir.mkdir()

        mock_run.side_effect = [
            Mock(returncode=1, stdout="", stderr=""),  # git remote get-url
            Mock(returncode=0, stdout="", stderr=""),  # git remote add
            Mock(returncode=0, stdout="", stderr=""),  # git push
        ]

        auth = {"token": "private_token_123"}
        result = repo_manager.push_plugin(
            plugin_dir, "https://github.com/user/private-repo.git", auth=auth
        )

        assert result is True

        # Check that authenticated URL was used
        remote_add_call = mock_run.call_args_list[1]
        authenticated_url = remote_add_call[0][0][-1]
        assert "private_token_123@github.com" in authenticated_url

    def test_conversion_error_recovery(self, repo_manager, temp_plugins_dir):
        """Test error recovery during conversion process."""
        # Create invalid plugin directory
        invalid_dir = temp_plugins_dir / "invalid-plugin"
        invalid_dir.mkdir()

        # Missing plugin.json should cause validation error
        from pacc.errors.exceptions import ValidationError

        with pytest.raises(ValidationError):
            repo_manager.create_plugin_repository(invalid_dir, {}, init_git=False)

        # Directory should still exist for recovery
        assert invalid_dir.exists()

    @patch("pacc.plugins.repository.subprocess.run")
    def test_conversion_timeout_handling(self, mock_run, repo_manager, temp_plugins_dir):
        """Test handling of timeouts during conversion."""
        plugin_dir = temp_plugins_dir / "timeout-plugin"
        plugin_dir.mkdir()

        plugin_metadata = {"name": "timeout-plugin"}
        with open(plugin_dir / "plugin.json", "w") as f:
            json.dump(plugin_metadata, f)

        # Simulate timeout on git operations
        mock_run.side_effect = subprocess.TimeoutExpired("git", 30)

        from pacc.plugins.repository import GitError

        with pytest.raises(GitError) as exc_info:
            repo_manager.create_plugin_repository(plugin_dir, plugin_metadata)

        assert "timed out" in str(exc_info.value).lower()
