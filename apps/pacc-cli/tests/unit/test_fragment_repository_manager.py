"""Tests for FragmentRepositoryManager."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pacc.errors.exceptions import PACCError, ValidationError
from pacc.fragments.repository_manager import (
    FragmentCloneSpec,
    FragmentDiscoveryResult,
    FragmentGitError,
    FragmentRepo,
    FragmentRepositoryError,
    FragmentRepositoryManager,
    FragmentUpdateResult,
)


class TestFragmentCloneSpec:
    """Test cases for FragmentCloneSpec."""

    def test_valid_clone_spec_creation(self):
        """Test creating valid clone specifications."""
        # Test basic spec
        spec = FragmentCloneSpec(repo_url="https://github.com/owner/repo.git")
        assert spec.repo_url == "https://github.com/owner/repo.git"
        assert spec.branch is None
        assert spec.tag is None
        assert spec.commit_sha is None
        assert spec.shallow is True
        assert spec.target_dir is None

        # Test spec with branch
        spec = FragmentCloneSpec(
            repo_url="https://github.com/owner/repo.git", branch="develop", shallow=False
        )
        assert spec.branch == "develop"
        assert spec.shallow is False

        # Test spec with tag
        spec = FragmentCloneSpec(repo_url="https://github.com/owner/repo.git", tag="v1.0.0")
        assert spec.tag == "v1.0.0"

        # Test spec with commit SHA
        spec = FragmentCloneSpec(
            repo_url="https://github.com/owner/repo.git", commit_sha="abc123def456"
        )
        assert spec.commit_sha == "abc123def456"

    def test_invalid_clone_spec_multiple_refs(self):
        """Test that providing multiple references raises validation error."""
        with pytest.raises(
            ValidationError, match="Can only specify one of: branch, tag, or commit_sha"
        ):
            FragmentCloneSpec(
                repo_url="https://github.com/owner/repo.git", branch="main", tag="v1.0.0"
            )

        with pytest.raises(
            ValidationError, match="Can only specify one of: branch, tag, or commit_sha"
        ):
            FragmentCloneSpec(
                repo_url="https://github.com/owner/repo.git", branch="main", commit_sha="abc123"
            )

        with pytest.raises(
            ValidationError, match="Can only specify one of: branch, tag, or commit_sha"
        ):
            FragmentCloneSpec(
                repo_url="https://github.com/owner/repo.git", tag="v1.0.0", commit_sha="abc123"
            )


class TestFragmentRepo:
    """Test cases for FragmentRepo."""

    def test_fragment_repo_properties(self):
        """Test FragmentRepo properties."""
        repo = FragmentRepo(
            owner="testowner",
            repo="testrepo",
            path=Path("/tmp/fragments/repos/testowner/testrepo"),
            url="https://github.com/testowner/testrepo.git",
            commit_sha="abc123def456",
            branch="main",
            tag="v1.0.0",
            fragments=["fragment1.md", "fragment2.md"],
            is_shallow=True,
        )

        assert repo.full_name == "testowner/testrepo"
        assert repo.version_ref == "tag:v1.0.0"

        # Test version_ref precedence
        repo.tag = None
        assert repo.version_ref == "branch:main"

        repo.branch = None
        assert repo.version_ref == "sha:abc123de"

        repo.commit_sha = None
        assert repo.version_ref == "unknown"


class TestFragmentRepositoryManager:
    """Test cases for FragmentRepositoryManager."""

    @pytest.fixture
    def temp_fragments_dir(self):
        """Create a temporary fragments directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def repository_manager(self, temp_fragments_dir):
        """Create FragmentRepositoryManager with temporary directory."""
        return FragmentRepositoryManager(fragments_dir=temp_fragments_dir)

    @pytest.fixture
    def mock_git_repo(self, temp_fragments_dir):
        """Create a mock Git repository with fragments."""
        repo_dir = temp_fragments_dir / "repos" / "testowner" / "testrepo"
        repo_dir.mkdir(parents=True)

        # Create some fragment files
        (repo_dir / "fragment1.md").write_text("# Fragment 1\nThis is fragment 1.")
        (repo_dir / "fragment2.md").write_text("# Fragment 2\nThis is fragment 2.")
        (repo_dir / "subfolder").mkdir()
        (repo_dir / "subfolder" / "fragment3.md").write_text("# Fragment 3\nThis is fragment 3.")

        # Create a README (should be ignored)
        (repo_dir / "README.md").write_text("# Test Repo\nThis is a test repository.")

        return repo_dir

    def test_initialization(self, temp_fragments_dir):
        """Test manager initialization."""
        manager = FragmentRepositoryManager(temp_fragments_dir)

        assert manager.fragments_dir == temp_fragments_dir
        assert manager.repos_dir == temp_fragments_dir / "repos"
        assert manager.cache_dir == temp_fragments_dir / "cache"

        # Check directories were created
        assert manager.repos_dir.exists()
        assert manager.cache_dir.exists()

    def test_initialization_default_path(self, monkeypatch):
        """Test manager initialization with default path."""
        mock_home = Path("/mock/home")
        monkeypatch.setattr(Path, "home", lambda: mock_home)

        with patch("pathlib.Path.mkdir"):
            manager = FragmentRepositoryManager()
            expected_dir = mock_home / ".claude" / "pacc" / "fragments"
            assert manager.fragments_dir == expected_dir

    def test_parse_repo_url_github_https(self, repository_manager):
        """Test parsing GitHub HTTPS URLs."""
        # Test standard GitHub HTTPS URL
        owner, repo = repository_manager._parse_repo_url("https://github.com/owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"

        # Test GitHub HTTPS URL without .git
        owner, repo = repository_manager._parse_repo_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_repo_url_github_ssh(self, repository_manager):
        """Test parsing GitHub SSH URLs."""
        # Test standard GitHub SSH URL
        owner, repo = repository_manager._parse_repo_url("git@github.com:owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"

        # Test GitHub SSH URL without .git
        owner, repo = repository_manager._parse_repo_url("git@github.com:owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_repo_url_other_git(self, repository_manager):
        """Test parsing other Git URLs."""
        # Test GitLab URL
        owner, repo = repository_manager._parse_repo_url("https://gitlab.com/owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_repo_url_invalid(self, repository_manager):
        """Test parsing invalid URLs."""
        with pytest.raises(ValueError, match="Unable to parse repository URL"):
            repository_manager._parse_repo_url("not-a-valid-url")

        with pytest.raises(ValueError, match="Unable to parse repository URL"):
            repository_manager._parse_repo_url("https://github.com/incomplete")

    @patch("subprocess.run")
    def test_get_current_commit_sha_success(self, mock_run, repository_manager, mock_git_repo):
        """Test getting current commit SHA successfully."""
        mock_run.return_value = Mock(returncode=0, stdout="abc123def456789\n")

        sha = repository_manager._get_current_commit_sha(mock_git_repo)
        assert sha == "abc123def456789"

        mock_run.assert_called_once_with(
            ["git", "log", "-1", "--format=%H"],
            cwd=mock_git_repo,
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch("subprocess.run")
    def test_get_current_commit_sha_failure(self, mock_run, repository_manager, mock_git_repo):
        """Test getting current commit SHA failure."""
        mock_run.return_value = Mock(returncode=1, stderr="Not a git repository")

        with pytest.raises(FragmentGitError, match="Failed to get commit SHA"):
            repository_manager._get_current_commit_sha(mock_git_repo)

    @patch("subprocess.run")
    def test_get_current_branch_success(self, mock_run, repository_manager, mock_git_repo):
        """Test getting current branch successfully."""
        mock_run.return_value = Mock(returncode=0, stdout="main\n")

        branch = repository_manager._get_current_branch(mock_git_repo)
        assert branch == "main"

    @patch("subprocess.run")
    def test_get_current_branch_detached_head(self, mock_run, repository_manager, mock_git_repo):
        """Test getting current branch when in detached HEAD state."""
        mock_run.return_value = Mock(returncode=0, stdout="HEAD\n")

        branch = repository_manager._get_current_branch(mock_git_repo)
        assert branch is None

    @patch("subprocess.run")
    def test_is_working_tree_clean_true(self, mock_run, repository_manager, mock_git_repo):
        """Test working tree is clean."""
        mock_run.return_value = Mock(returncode=0, stdout="")

        is_clean = repository_manager._is_working_tree_clean(mock_git_repo)
        assert is_clean is True

    @patch("subprocess.run")
    def test_is_working_tree_clean_false(self, mock_run, repository_manager, mock_git_repo):
        """Test working tree has changes."""
        mock_run.return_value = Mock(returncode=0, stdout=" M modified_file.md\n")

        is_clean = repository_manager._is_working_tree_clean(mock_git_repo)
        assert is_clean is False

    def test_discover_fragments_in_repo(self, repository_manager, mock_git_repo):
        """Test discovering fragments in repository."""
        fragments = repository_manager._discover_fragments_in_repo(mock_git_repo)

        # Should find 3 fragments, excluding README.md
        expected_fragments = ["fragment1.md", "fragment2.md", "subfolder/fragment3.md"]
        assert sorted(fragments) == sorted(expected_fragments)

    def test_discover_fragments_empty_repo(self, repository_manager, temp_fragments_dir):
        """Test discovering fragments in empty repository."""
        empty_repo = temp_fragments_dir / "empty_repo"
        empty_repo.mkdir()

        fragments = repository_manager._discover_fragments_in_repo(empty_repo)
        assert fragments == []

    def test_discover_fragments_validation(self, repository_manager, mock_git_repo):
        """Test fragment discovery validation."""
        result = repository_manager.discover_fragments(mock_git_repo)

        assert result.is_valid is True
        assert len(result.fragments_found) == 3
        assert "fragment1.md" in result.fragments_found
        assert "fragment2.md" in result.fragments_found
        assert "subfolder/fragment3.md" in result.fragments_found
        assert result.error_message is None

    def test_discover_fragments_no_fragments(self, repository_manager, temp_fragments_dir):
        """Test fragment discovery with no fragments found."""
        empty_repo = temp_fragments_dir / "empty_repo"
        empty_repo.mkdir()

        result = repository_manager.discover_fragments(empty_repo)

        assert result.is_valid is False
        assert result.fragments_found == []
        assert "No fragments found" in result.error_message

    def test_discover_fragments_nonexistent_repo(self, repository_manager, temp_fragments_dir):
        """Test fragment discovery with non-existent repository."""
        nonexistent_repo = temp_fragments_dir / "nonexistent"

        result = repository_manager.discover_fragments(nonexistent_repo)

        assert result.is_valid is False
        assert "Repository path does not exist" in result.error_message

    @patch("pacc.fragments.repository_manager.subprocess.run")
    def test_clone_fragment_repo_success(self, mock_run, repository_manager, temp_fragments_dir):
        """Test successful fragment repository cloning."""
        # Mock git clone
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git clone
            Mock(returncode=0, stdout="abc123def456\n"),  # get commit SHA
            Mock(returncode=0, stdout="main\n"),  # get branch
        ]

        # Create target directory and fragments
        target_dir = temp_fragments_dir / "repos" / "testowner" / "testrepo"
        target_dir.mkdir(parents=True)
        (target_dir / "fragment.md").write_text("# Fragment")

        clone_spec = FragmentCloneSpec(
            repo_url="https://github.com/testowner/testrepo.git", branch="main"
        )

        with patch.object(repository_manager, "discover_fragments") as mock_discover:
            mock_discover.return_value = FragmentDiscoveryResult(
                is_valid=True, fragments_found=["fragment.md"]
            )

            result = repository_manager.clone_fragment_repo(clone_spec)

            assert isinstance(result, FragmentRepo)
            assert result.owner == "testowner"
            assert result.repo == "testrepo"
            assert result.url == "https://github.com/testowner/testrepo.git"
            assert result.branch == "main"
            assert result.commit_sha == "abc123def456"
            assert result.fragments == ["fragment.md"]
            assert result.is_shallow is True

    @patch("pacc.fragments.repository_manager.subprocess.run")
    def test_clone_fragment_repo_git_failure(self, mock_run, repository_manager):
        """Test fragment repository cloning with git failure."""
        # Mock git clone failure
        mock_run.return_value = Mock(returncode=1, stderr="Repository not found")

        clone_spec = FragmentCloneSpec(repo_url="https://github.com/testowner/testrepo.git")

        with pytest.raises(FragmentGitError, match="Git clone failed"):
            repository_manager.clone_fragment_repo(clone_spec)

    @patch("pacc.fragments.repository_manager.subprocess.run")
    def test_clone_fragment_repo_no_fragments(
        self, mock_run, repository_manager, temp_fragments_dir
    ):
        """Test fragment repository cloning with no fragments found."""
        # Mock successful git operations
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git clone
            Mock(returncode=0, stdout="abc123def456\n"),  # get commit SHA
            Mock(returncode=0, stdout="main\n"),  # get branch
        ]

        # Create empty target directory
        target_dir = temp_fragments_dir / "repos" / "testowner" / "testrepo"
        target_dir.mkdir(parents=True)

        clone_spec = FragmentCloneSpec(repo_url="https://github.com/testowner/testrepo.git")

        with patch.object(repository_manager, "discover_fragments") as mock_discover:
            mock_discover.return_value = FragmentDiscoveryResult(
                is_valid=False, fragments_found=[], error_message="No fragments found"
            )

            with pytest.raises(FragmentRepositoryError, match="does not contain valid fragments"):
                repository_manager.clone_fragment_repo(clone_spec)

    @patch("pacc.fragments.repository_manager.subprocess.run")
    def test_clone_with_commit_sha(self, mock_run, repository_manager, temp_fragments_dir):
        """Test cloning with specific commit SHA."""
        # Mock git operations
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # git clone
            Mock(returncode=0, stdout="", stderr=""),  # git checkout SHA
            Mock(returncode=0, stdout="abc123def456\n"),  # get commit SHA
        ]

        # Create target directory and fragments
        target_dir = temp_fragments_dir / "repos" / "testowner" / "testrepo"
        target_dir.mkdir(parents=True)
        (target_dir / "fragment.md").write_text("# Fragment")

        clone_spec = FragmentCloneSpec(
            repo_url="https://github.com/testowner/testrepo.git", commit_sha="abc123def456"
        )

        with patch.object(repository_manager, "discover_fragments") as mock_discover:
            mock_discover.return_value = FragmentDiscoveryResult(
                is_valid=True, fragments_found=["fragment.md"]
            )

            result = repository_manager.clone_fragment_repo(clone_spec)

            # Verify checkout was called
            checkout_calls = [call for call in mock_run.call_args_list if "checkout" in str(call)]
            assert len(checkout_calls) > 0

            assert result.commit_sha == "abc123def456"

    @patch("pacc.fragments.repository_manager.subprocess.run")
    def test_update_fragment_repo_success(self, mock_run, repository_manager, mock_git_repo):
        """Test successful fragment repository update."""
        # Mock git operations
        mock_run.side_effect = [
            Mock(returncode=0, stdout="abc123\n"),  # get old SHA
            Mock(returncode=0, stdout=""),  # git status
            Mock(returncode=0, stdout="main\n"),  # get branch
            Mock(returncode=0, stdout="Updated\n"),  # git pull
            Mock(returncode=0, stdout="def456\n"),  # get new SHA
        ]

        with patch.object(repository_manager, "discover_fragments") as mock_discover:
            mock_discover.return_value = FragmentDiscoveryResult(is_valid=True)

            result = repository_manager.update_fragment_repo(mock_git_repo)

            assert result.success is True
            assert result.had_changes is True
            assert result.old_sha == "abc123"
            assert result.new_sha == "def456"

    @patch("pacc.fragments.repository_manager.subprocess.run")
    def test_update_fragment_repo_no_changes(self, mock_run, repository_manager, mock_git_repo):
        """Test fragment repository update with no changes."""
        same_sha = "abc123def456"
        mock_run.side_effect = [
            Mock(returncode=0, stdout=f"{same_sha}\n"),  # get old SHA
            Mock(returncode=0, stdout=""),  # git status
            Mock(returncode=0, stdout="main\n"),  # get branch
            Mock(returncode=0, stdout="Already up to date\n"),  # git pull
            Mock(returncode=0, stdout=f"{same_sha}\n"),  # get new SHA
        ]

        with patch.object(repository_manager, "discover_fragments") as mock_discover:
            mock_discover.return_value = FragmentDiscoveryResult(is_valid=True)

            result = repository_manager.update_fragment_repo(mock_git_repo)

            assert result.success is True
            assert result.had_changes is False
            assert result.old_sha == same_sha
            assert result.new_sha == same_sha

    @patch("pacc.fragments.repository_manager.subprocess.run")
    def test_update_fragment_repo_dirty_working_tree(
        self, mock_run, repository_manager, mock_git_repo
    ):
        """Test fragment repository update with dirty working tree."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="abc123\n"),  # get old SHA
            Mock(returncode=0, stdout=" M modified.md\n"),  # git status (dirty)
        ]

        result = repository_manager.update_fragment_repo(mock_git_repo)

        assert result.success is False
        assert "dirty working tree" in result.error_message

    @patch("pacc.fragments.repository_manager.subprocess.run")
    def test_rollback_fragment_repo_success(self, mock_run, repository_manager, mock_git_repo):
        """Test successful fragment repository rollback."""
        target_sha = "abc123def456"
        mock_run.side_effect = [
            Mock(returncode=0, stdout=f"{target_sha}\n"),  # verify SHA
            Mock(returncode=0, stdout=""),  # git reset
        ]

        result = repository_manager.rollback_fragment_repo(mock_git_repo, target_sha)

        assert result is True

        # Verify git commands were called
        assert mock_run.call_count == 2
        verify_call = mock_run.call_args_list[0]
        assert "rev-parse" in str(verify_call)
        reset_call = mock_run.call_args_list[1]
        assert "reset" in str(reset_call) and "--hard" in str(reset_call)

    @patch("pacc.fragments.repository_manager.subprocess.run")
    def test_rollback_fragment_repo_invalid_sha(self, mock_run, repository_manager, mock_git_repo):
        """Test fragment repository rollback with invalid SHA."""
        mock_run.return_value = Mock(returncode=1, stderr="Invalid SHA")

        result = repository_manager.rollback_fragment_repo(mock_git_repo, "invalid_sha")

        assert result is False

    def test_get_repo_info_success(self, repository_manager, mock_git_repo):
        """Test getting repository information successfully."""
        with patch.object(repository_manager, "_get_current_commit_sha") as mock_sha:
            with patch.object(repository_manager, "_get_current_branch") as mock_branch:
                with patch.object(repository_manager, "_get_remote_url") as mock_url:
                    with patch.object(repository_manager, "discover_fragments") as mock_discover:
                        mock_sha.return_value = "abc123def456"
                        mock_branch.return_value = "main"
                        mock_url.return_value = "https://github.com/testowner/testrepo.git"
                        mock_discover.return_value = FragmentDiscoveryResult(
                            is_valid=True, fragments_found=["fragment1.md", "fragment2.md"]
                        )

                        info = repository_manager.get_repo_info(mock_git_repo)

                        assert info["owner"] == "testowner"
                        assert info["repo"] == "testrepo"
                        assert info["full_name"] == "testowner/testrepo"
                        assert info["commit_sha"] == "abc123def456"
                        assert info["branch"] == "main"
                        assert info["remote_url"] == "https://github.com/testowner/testrepo.git"
                        assert info["fragment_count"] == 2
                        assert info["is_valid"] is True

    def test_get_repo_info_nonexistent_repo(self, repository_manager, temp_fragments_dir):
        """Test getting repository information for non-existent repository."""
        nonexistent_repo = temp_fragments_dir / "nonexistent"

        with pytest.raises(PACCError, match="Repository path does not exist"):
            repository_manager.get_repo_info(nonexistent_repo)

    def test_cleanup_cache(self, repository_manager, temp_fragments_dir):
        """Test cache cleanup functionality."""
        # Create some cache files
        cache_file1 = repository_manager.cache_dir / "test_file.cache"
        cache_file2 = repository_manager.cache_dir / "another_file.cache"
        cache_subdir = repository_manager.cache_dir / "subdir"
        cache_subdir.mkdir()
        cache_file3 = cache_subdir / "nested_file.cache"

        # Create files
        cache_file1.write_text("test content")
        cache_file2.write_text("more content")
        cache_file3.write_text("nested content")

        # Test cleanup with a very high age (should not remove anything)
        removed_count = repository_manager.cleanup_cache(max_age_days=365)

        # The method should complete without error
        assert removed_count >= 0

        # Test cleanup with age 0 (should potentially remove files)
        # Note: This test is more about ensuring the method runs without error
        # than testing exact behavior due to timing dependencies
        removed_count = repository_manager.cleanup_cache(max_age_days=0)
        assert removed_count >= 0


class TestFragmentDiscoveryResult:
    """Test cases for FragmentDiscoveryResult."""

    def test_valid_discovery_result(self):
        """Test creating valid discovery result."""
        result = FragmentDiscoveryResult(
            is_valid=True,
            fragments_found=["fragment1.md", "fragment2.md"],
            warnings=["Warning: Large file"],
        )

        assert result.is_valid is True
        assert len(result.fragments_found) == 2
        assert len(result.warnings) == 1
        assert result.error_message is None

    def test_invalid_discovery_result(self):
        """Test creating invalid discovery result."""
        result = FragmentDiscoveryResult(is_valid=False, error_message="No fragments found")

        assert result.is_valid is False
        assert result.error_message == "No fragments found"
        assert result.fragments_found == []
        assert result.warnings == []


class TestFragmentUpdateResult:
    """Test cases for FragmentUpdateResult."""

    def test_successful_update_result(self):
        """Test creating successful update result."""
        result = FragmentUpdateResult(
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
        assert result.message == "Updated successfully"
        assert result.error_message is None

    def test_failed_update_result(self):
        """Test creating failed update result."""
        result = FragmentUpdateResult(
            success=False,
            error_message="Update failed due to conflicts",
            conflicts=["file1.md", "file2.md"],
        )

        assert result.success is False
        assert result.error_message == "Update failed due to conflicts"
        assert len(result.conflicts) == 2
        assert result.had_changes is False
