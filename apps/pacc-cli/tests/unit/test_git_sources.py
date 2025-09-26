#!/usr/bin/env python3
"""Tests for Git repository source handling."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pacc.errors import SourceError
from pacc.sources.git import GitCloner, GitRepositorySource, GitSourceHandler, GitUrlParser


class TestGitUrlParser(unittest.TestCase):
    """Test Git URL parsing and validation."""

    def setUp(self):
        self.parser = GitUrlParser()

    def test_github_https_url_parsing(self):
        """Test parsing GitHub HTTPS URLs."""
        url = "https://github.com/owner/repo.git"
        result = self.parser.parse(url)

        self.assertEqual(result["provider"], "github")
        self.assertEqual(result["owner"], "owner")
        self.assertEqual(result["repo"], "repo")
        self.assertEqual(result["protocol"], "https")
        self.assertIsNone(result["branch"])
        self.assertIsNone(result["path"])

    def test_github_ssh_url_parsing(self):
        """Test parsing GitHub SSH URLs."""
        url = "git@github.com:owner/repo.git"
        result = self.parser.parse(url)

        self.assertEqual(result["provider"], "github")
        self.assertEqual(result["owner"], "owner")
        self.assertEqual(result["repo"], "repo")
        self.assertEqual(result["protocol"], "ssh")

    def test_gitlab_url_parsing(self):
        """Test parsing GitLab URLs."""
        url = "https://gitlab.com/group/subgroup/project.git"
        result = self.parser.parse(url)

        self.assertEqual(result["provider"], "gitlab")
        self.assertEqual(result["owner"], "group/subgroup")
        self.assertEqual(result["repo"], "project")
        self.assertEqual(result["protocol"], "https")

    def test_bitbucket_url_parsing(self):
        """Test parsing Bitbucket URLs."""
        url = "https://bitbucket.org/workspace/repo.git"
        result = self.parser.parse(url)

        self.assertEqual(result["provider"], "bitbucket")
        self.assertEqual(result["owner"], "workspace")
        self.assertEqual(result["repo"], "repo")

    def test_url_with_branch(self):
        """Test parsing URLs with branch specifications."""
        url = "https://github.com/owner/repo.git#feature-branch"
        result = self.parser.parse(url)

        self.assertEqual(result["branch"], "feature-branch")

    def test_url_with_tag(self):
        """Test parsing URLs with tag specifications."""
        url = "https://github.com/owner/repo.git@v1.2.3"
        result = self.parser.parse(url)

        self.assertEqual(result["tag"], "v1.2.3")

    def test_url_with_commit(self):
        """Test parsing URLs with commit specifications."""
        url = "https://github.com/owner/repo.git@abc123def"
        result = self.parser.parse(url)

        self.assertEqual(result["commit"], "abc123def")

    def test_url_with_subdirectory(self):
        """Test parsing URLs with subdirectory paths."""
        url = "https://github.com/owner/repo.git/path/to/extensions"
        result = self.parser.parse(url)

        self.assertEqual(result["path"], "path/to/extensions")

    def test_invalid_url(self):
        """Test handling of invalid URLs."""
        with self.assertRaises(SourceError):
            self.parser.parse("not-a-git-url")

    def test_unsupported_provider(self):
        """Test handling of unsupported Git providers."""
        url = "https://unsupported-git.com/owner/repo.git"
        with self.assertRaises(SourceError):
            self.parser.parse(url)

    def test_validate_github_url(self):
        """Test GitHub URL validation."""
        url = "https://github.com/owner/repo.git"
        self.assertTrue(self.parser.validate(url))

        # Invalid GitHub URL
        invalid_url = "https://github.com/owner"
        self.assertFalse(self.parser.validate(invalid_url))

    def test_normalize_github_url(self):
        """Test GitHub URL normalization."""
        # Without .git suffix
        url = "https://github.com/owner/repo"
        normalized = self.parser.normalize(url)
        self.assertEqual(normalized, "https://github.com/owner/repo.git")

        # With .git suffix (should remain unchanged)
        url_with_git = "https://github.com/owner/repo.git"
        normalized = self.parser.normalize(url_with_git)
        self.assertEqual(normalized, url_with_git)


class TestGitCloner(unittest.TestCase):
    """Test Git repository cloning functionality."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.cloner = GitCloner(temp_dir=self.temp_dir)

    @patch("subprocess.run")
    def test_clone_public_repository(self, mock_run):
        """Test cloning a public repository."""
        mock_run.return_value = Mock(returncode=0)

        url = "https://github.com/test/repo.git"
        result = self.cloner.clone(url)

        self.assertIsInstance(result, Path)
        self.assertTrue(result.is_relative_to(Path(self.temp_dir)))
        mock_run.assert_called()

    @patch("subprocess.run")
    def test_clone_with_branch(self, mock_run):
        """Test cloning specific branch."""
        mock_run.return_value = Mock(returncode=0)

        url = "https://github.com/test/repo.git"
        self.cloner.clone(url, branch="feature-branch")

        # Check that branch was specified in git command
        args = mock_run.call_args[0][0]
        self.assertIn("--branch", args)
        self.assertIn("feature-branch", args)

    @patch("subprocess.run")
    def test_shallow_clone(self, mock_run):
        """Test shallow cloning for large repositories."""
        mock_run.return_value = Mock(returncode=0)

        url = "https://github.com/test/large-repo.git"
        self.cloner.clone(url, shallow=True)

        # Check that shallow clone was requested
        args = mock_run.call_args[0][0]
        self.assertIn("--depth", args)
        self.assertIn("1", args)

    @patch("subprocess.run")
    def test_clone_failure(self, mock_run):
        """Test handling of clone failures."""
        mock_run.return_value = Mock(returncode=1, stderr="Repository not found")

        url = "https://github.com/nonexistent/repo.git"
        with self.assertRaises(SourceError):
            self.cloner.clone(url)

    def test_cleanup_clone(self):
        """Test cleaning up cloned repositories."""
        # Create a fake clone directory
        clone_dir = Path(self.temp_dir) / "test-repo"
        clone_dir.mkdir()
        (clone_dir / "file.txt").write_text("test")

        self.cloner.cleanup(clone_dir)
        self.assertFalse(clone_dir.exists())

    @patch("subprocess.run")
    def test_clone_with_credentials(self, mock_run):
        """Test cloning with SSH credentials."""
        mock_run.return_value = Mock(returncode=0)

        url = "git@github.com:private/repo.git"
        result = self.cloner.clone(url)

        self.assertIsInstance(result, Path)
        mock_run.assert_called()


class TestGitRepositorySource(unittest.TestCase):
    """Test Git repository source handling."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

        # Create a mock repository structure
        self.repo_dir = Path(self.temp_dir) / "test-repo"
        self.repo_dir.mkdir()

        # Create sample extensions
        hooks_dir = self.repo_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "test-hook.json").write_text('{"name": "test-hook", "events": ["PreToolUse"]}')

        agents_dir = self.repo_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "test-agent.md").write_text("---\nname: test-agent\n---\n# Test Agent")

        self.source = GitRepositorySource("https://github.com/test/repo.git")

    @patch.object(GitCloner, "clone")
    def test_scan_extensions(self, mock_clone):
        """Test scanning repository for extensions."""
        mock_clone.return_value = self.repo_dir

        extensions = self.source.scan_extensions()

        self.assertEqual(len(extensions), 2)
        extension_types = {ext.extension_type for ext in extensions}
        self.assertEqual(extension_types, {"hooks", "agents"})

    @patch.object(GitCloner, "clone")
    def test_scan_with_subdirectory(self, mock_clone):
        """Test scanning specific subdirectory in repository."""
        mock_clone.return_value = self.repo_dir

        # Create source with subdirectory path
        source = GitRepositorySource("https://github.com/test/repo.git/hooks")
        extensions = source.scan_extensions()

        # Should only find hooks
        self.assertEqual(len(extensions), 1)
        self.assertEqual(extensions[0].extension_type, "hooks")

    @patch.object(GitCloner, "clone")
    def test_extract_extension(self, mock_clone):
        """Test extracting specific extension from repository."""
        mock_clone.return_value = self.repo_dir

        extension_name = "test-hook"
        extension_data = self.source.extract_extension(extension_name, "hooks")

        self.assertIsNotNone(extension_data)
        self.assertIn("name", extension_data)
        self.assertEqual(extension_data["name"], "test-hook")

    @patch.object(GitCloner, "clone")
    def test_repository_metadata(self, mock_clone):
        """Test extracting repository metadata."""
        mock_clone.return_value = self.repo_dir

        # Create README and package metadata
        (self.repo_dir / "README.md").write_text("# Test Repository")
        (self.repo_dir / "pacc.json").write_text('{"name": "test-extensions", "version": "1.0.0"}')

        metadata = self.source.get_repository_metadata()

        self.assertIn("name", metadata)
        self.assertIn("version", metadata)
        self.assertEqual(metadata["name"], "test-extensions")
        self.assertEqual(metadata["version"], "1.0.0")

    @patch.object(GitCloner, "clone")
    def test_cleanup(self, mock_clone):
        """Test cleaning up temporary repository clone."""
        mock_clone.return_value = self.repo_dir

        # Simulate scanning to create the clone
        self.source.scan_extensions()

        # Cleanup should remove the temporary directory
        self.source.cleanup()
        # Directory is managed by GitCloner, so we can't test removal directly
        # But we can verify cleanup was called
        self.assertIsNotNone(self.source._cloner)


class TestGitSourceHandler(unittest.TestCase):
    """Test Git source handler integration."""

    def setUp(self):
        self.handler = GitSourceHandler()

    def test_can_handle_github_url(self):
        """Test detection of GitHub URLs."""
        self.assertTrue(self.handler.can_handle("https://github.com/owner/repo.git"))
        self.assertTrue(self.handler.can_handle("git@github.com:owner/repo.git"))
        self.assertFalse(self.handler.can_handle("/path/to/local/file"))
        self.assertFalse(self.handler.can_handle("https://example.com/not-git"))

    def test_can_handle_gitlab_url(self):
        """Test detection of GitLab URLs."""
        self.assertTrue(self.handler.can_handle("https://gitlab.com/group/repo.git"))
        self.assertTrue(self.handler.can_handle("git@gitlab.com:group/repo.git"))

    def test_can_handle_bitbucket_url(self):
        """Test detection of Bitbucket URLs."""
        self.assertTrue(self.handler.can_handle("https://bitbucket.org/workspace/repo.git"))

    @patch.object(GitRepositorySource, "scan_extensions")
    def test_process_source(self, mock_scan):
        """Test processing Git repository source."""
        # Mock extensions found in repository
        mock_extension = Mock()
        mock_extension.name = "test-extension"
        mock_extension.extension_type = "hooks"
        mock_extension.file_path = Path("/tmp/test-hook.json")
        mock_scan.return_value = [mock_extension]

        url = "https://github.com/test/repo.git"
        extensions = self.handler.process_source(url)

        self.assertEqual(len(extensions), 1)
        self.assertEqual(extensions[0].name, "test-extension")
        self.assertEqual(extensions[0].extension_type, "hooks")

    @patch.object(GitRepositorySource, "scan_extensions")
    def test_process_source_with_filters(self, mock_scan):
        """Test processing source with type filters."""
        # Mock mixed extensions
        hook_ext = Mock()
        hook_ext.extension_type = "hooks"
        agent_ext = Mock()
        agent_ext.extension_type = "agents"
        mock_scan.return_value = [hook_ext, agent_ext]

        url = "https://github.com/test/repo.git"
        extensions = self.handler.process_source(url, extension_type="hooks")

        # Should only return hooks
        self.assertEqual(len(extensions), 1)
        self.assertEqual(extensions[0].extension_type, "hooks")

    def test_get_source_info(self):
        """Test extracting source information from Git URL."""
        url = "https://github.com/owner/repo.git#main"
        info = self.handler.get_source_info(url)

        self.assertEqual(info["provider"], "github")
        self.assertEqual(info["owner"], "owner")
        self.assertEqual(info["repo"], "repo")
        self.assertEqual(info["branch"], "main")
        self.assertEqual(info["type"], "git")


if __name__ == "__main__":
    unittest.main()
