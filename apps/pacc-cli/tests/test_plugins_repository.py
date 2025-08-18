"""Tests for plugin repository management."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, call
import pytest

from pacc.plugins.repository import (
    PluginRepositoryManager, 
    PluginRepo, 
    UpdateResult,
    PluginInfo,
    GitError,
    RepositoryStructureError
)
from pacc.plugins.config import PluginConfigManager
from pacc.errors.exceptions import PACCError, ConfigurationError


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
    return PluginRepositoryManager(
        plugins_dir=temp_plugins_dir,
        config_manager=mock_config_manager
    )


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
        "author": {"name": "Test User"}
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
            plugins_dir=temp_plugins_dir,
            config_manager=mock_config_manager
        )
        
        assert manager.repos_dir.exists()
        assert manager.repos_dir == temp_plugins_dir / "repos"
    
    @patch('pacc.plugins.repository.subprocess.run')
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
        
        plugin_json = {
            "name": "test-plugin",
            "version": "1.0.0"
        }
        
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
    
    @patch('pacc.plugins.repository.subprocess.run')
    def test_clone_plugin_git_failure(self, mock_run, repo_manager):
        """Test clone failure due to git error."""
        mock_run.return_value = Mock(
            returncode=128, 
            stdout="", 
            stderr="fatal: repository not found"
        )
        
        repo_url = "https://github.com/invalid/repo.git"
        target_dir = repo_manager.repos_dir / "invalid" / "repo"
        
        with pytest.raises(GitError) as exc_info:
            repo_manager.clone_plugin(repo_url, target_dir)
        
        assert "Git clone failed" in str(exc_info.value)
        assert "fatal: repository not found" in str(exc_info.value)
    
    @patch('pacc.plugins.repository.subprocess.run')
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
    
    @patch('pacc.plugins.repository.subprocess.run')
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
    
    @patch('pacc.plugins.repository.subprocess.run')
    def test_update_plugin_dirty_working_tree(self, mock_run, repo_manager, sample_plugin_repo):
        """Test update fails with dirty working tree."""
        # git status --porcelain returns modified files
        mock_run.return_value = Mock(returncode=0, stdout=" M some-file.txt\n", stderr="")
        
        result = repo_manager.update_plugin(sample_plugin_repo)
        
        assert result.success is False
        assert "dirty working tree" in result.error_message.lower()
    
    @patch('pacc.plugins.repository.subprocess.run')
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
    
    @patch('pacc.plugins.repository.subprocess.run')
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
    
    @patch('pacc.plugins.repository.subprocess.run')
    def test_rollback_plugin_failure(self, mock_run, repo_manager, sample_plugin_repo):
        """Test rollback failure."""
        mock_run.return_value = Mock(
            returncode=1, 
            stdout="", 
            stderr="fatal: invalid object name"
        )
        
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
    
    @patch('pacc.plugins.repository.subprocess.run')
    def test_get_current_commit_sha(self, mock_run, repo_manager, sample_plugin_repo):
        """Test getting current commit SHA."""
        mock_run.return_value = Mock(returncode=0, stdout="abc123def456\n", stderr="")
        
        sha = repo_manager._get_current_commit_sha(sample_plugin_repo)
        
        assert sha == "abc123def456"
    
    @patch('pacc.plugins.repository.subprocess.run')
    def test_is_working_tree_clean_true(self, mock_run, repo_manager, sample_plugin_repo):
        """Test checking clean working tree."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        is_clean = repo_manager._is_working_tree_clean(sample_plugin_repo)
        
        assert is_clean is True
    
    @patch('pacc.plugins.repository.subprocess.run')
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
        
        plugin_json = {
            "name": "nested-plugin",
            "version": "1.0.0"
        }
        
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
            url="https://github.com/testowner/testrepo.git"
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
            message="Updated successfully"
        )
        
        assert result.success is True
        assert result.had_changes is True
        assert result.old_sha == "abc123"
        assert result.new_sha == "def456"
    
    def test_plugin_info_creation(self):
        """Test PluginInfo creation."""
        info = PluginInfo(
            owner="owner",
            repo="repo",
            plugins=["plugin1", "plugin2"],
            path=Path("/path")
        )
        
        assert info.owner == "owner"
        assert info.repo == "repo"
        assert len(info.plugins) == 2
        assert "plugin1" in info.plugins


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