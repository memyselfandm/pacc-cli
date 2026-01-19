#!/usr/bin/env python3
"""Integration tests for Git repository source handling."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pacc.cli import PACCCli
from pacc.sources.git import GitSourceHandler


class TestGitIntegration(unittest.TestCase):
    """Integration tests for Git source functionality."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)

        # Create a test git repository structure
        self.test_repo = Path(self.temp_dir) / "test-repo"
        self.test_repo.mkdir()

        # Initialize as git repository
        subprocess.run(["git", "init"], cwd=self.test_repo, capture_output=True, check=False)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=self.test_repo, check=False
        )
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_repo, check=False)

        # Create sample extensions
        self._create_sample_extensions()

        # Commit the extensions
        subprocess.run(["git", "add", "."], cwd=self.test_repo, capture_output=True, check=False)
        subprocess.run(
            ["git", "commit", "-m", "Add sample extensions"],
            cwd=self.test_repo,
            capture_output=True,
            check=False,
        )

    def _create_sample_extensions(self):
        """Create sample extensions in test repository."""
        # Create hooks
        hooks_dir = self.test_repo / "hooks"
        hooks_dir.mkdir()

        hook_config = {
            "name": "pre-tool-logger",
            "description": "Logs tool usage before execution",
            "events": ["PreToolUse"],
            "matchers": ["*"],
            "command": "echo 'Tool about to be used: $TOOL_NAME'",
        }
        (hooks_dir / "pre-tool-logger.json").write_text(json.dumps(hook_config, indent=2))

        # Create agents
        agents_dir = self.test_repo / "agents"
        agents_dir.mkdir()

        agent_content = """---
name: code-reviewer
description: Reviews code and suggests improvements
model: claude-3-sonnet
tools:
  - file_read
  - file_write
---

# Code Reviewer Agent

This agent reviews code and provides improvement suggestions.

## Instructions

Review the provided code for:
- Code quality and best practices
- Performance improvements
- Security considerations
- Documentation completeness
"""
        (agents_dir / "code-reviewer.md").write_text(agent_content)

        # Create commands
        commands_dir = self.test_repo / "commands"
        commands_dir.mkdir()

        command_content = """# Test Project Setup

Sets up a new test project with common testing utilities.

## Usage
/test-setup [project-name]

## Description
Creates a new testing project structure with:
- Test directory structure
- Sample test files
- Testing configuration

## Arguments
- project-name: Name of the project to create
"""
        (commands_dir / "test-setup.md").write_text(command_content)

        # Create MCP server
        mcp_dir = self.test_repo / "mcp"
        mcp_dir.mkdir()

        mcp_config = {
            "name": "file-watcher",
            "description": "Watches files for changes",
            "command": "python",
            "args": ["file_watcher.py"],
            "env": {"WATCH_DIR": "."},
        }
        (mcp_dir / "file-watcher.json").write_text(json.dumps(mcp_config, indent=2))

        # Create a simple MCP server script
        mcp_script = """#!/usr/bin/env python3
import sys
import json

def main():
    print(json.dumps({"name": "file-watcher", "version": "1.0.0"}))

if __name__ == "__main__":
    main()
"""
        (mcp_dir / "file_watcher.py").write_text(mcp_script)

        # Create repository metadata
        pacc_config = {
            "name": "test-extensions",
            "version": "1.0.0",
            "description": "Sample extensions for testing",
            "author": "Test Author",
            "extensions": {
                "hooks": ["hooks/pre-tool-logger.json"],
                "agents": ["agents/code-reviewer.md"],
                "commands": ["commands/test-setup.md"],
                "mcp": ["mcp/file-watcher.json"],
            },
        }
        (self.test_repo / "pacc.json").write_text(json.dumps(pacc_config, indent=2))

        # Create README
        readme_content = """# Test Extensions Repository

This repository contains sample extensions for PACC testing.

## Extensions Included

- **pre-tool-logger**: Hook that logs tool usage
- **code-reviewer**: Agent for code review
- **test-setup**: Command for project setup
- **file-watcher**: MCP server for file watching

## Installation

```bash
pacc install https://github.com/test/extensions.git
```
"""
        (self.test_repo / "README.md").write_text(readme_content)

    def test_git_source_detection(self):
        """Test that Git URLs are properly detected."""
        handler = GitSourceHandler()

        # Test various Git URL formats
        git_urls = [
            "https://github.com/owner/repo.git",
            "git@github.com:owner/repo.git",
            "https://gitlab.com/group/project.git",
            "https://bitbucket.org/workspace/repo.git",
        ]

        for url in git_urls:
            with self.subTest(url=url):
                self.assertTrue(handler.can_handle(url))

        # Test non-Git URLs
        non_git_urls = ["/local/path", "https://example.com/file.zip", "file:///path/to/file"]

        for url in non_git_urls:
            with self.subTest(url=url):
                self.assertFalse(handler.can_handle(url))

    @patch("subprocess.run")
    def test_git_clone_command_construction(self, mock_run):
        """Test that Git clone commands are constructed correctly."""
        from pacc.sources.git import GitCloner

        mock_run.return_value = Mock(returncode=0)
        cloner = GitCloner()

        # Test basic clone
        cloner.clone("https://github.com/test/repo.git")

        args = mock_run.call_args[0][0]
        self.assertIn("git", args)
        self.assertIn("clone", args)
        self.assertIn("https://github.com/test/repo.git", args)

    @patch("subprocess.run")
    def test_git_shallow_clone(self, mock_run):
        """Test shallow cloning for performance."""
        from pacc.sources.git import GitCloner

        mock_run.return_value = Mock(returncode=0)
        cloner = GitCloner()

        cloner.clone("https://github.com/test/large-repo.git", shallow=True)

        args = mock_run.call_args[0][0]
        self.assertIn("--depth", args)
        self.assertIn("1", args)

    @patch("subprocess.run")
    def test_git_branch_checkout(self, mock_run):
        """Test checking out specific branches."""
        from pacc.sources.git import GitCloner

        mock_run.return_value = Mock(returncode=0)
        cloner = GitCloner()

        cloner.clone("https://github.com/test/repo.git", branch="feature-branch")

        args = mock_run.call_args[0][0]
        self.assertIn("--branch", args)
        self.assertIn("feature-branch", args)

    def test_extension_scanning_from_git_repo(self):
        """Test scanning extensions from Git repository structure."""
        handler = GitSourceHandler()

        # Mock the cloner to return our test repository
        with patch("pacc.sources.git.GitCloner.clone") as mock_clone:
            mock_clone.return_value = self.test_repo

            # Scan for extensions
            repo_url = f"file://{self.test_repo}"
            extensions = handler.process_source(repo_url)

            # Should find all 4 extension types
            self.assertEqual(len(extensions), 4)

            extension_types = {ext.extension_type for ext in extensions}
            expected_types = {"hooks", "agents", "commands", "mcp"}
            self.assertEqual(extension_types, expected_types)

            # Verify specific extensions
            extension_names = {ext.name for ext in extensions}
            expected_names = {"pre-tool-logger", "code-reviewer", "test-setup", "file-watcher"}
            self.assertEqual(extension_names, expected_names)

    def test_git_repository_metadata_extraction(self):
        """Test extracting metadata from Git repository."""
        from pacc.sources.git import GitRepositorySource

        with patch("pacc.sources.git.GitCloner.clone") as mock_clone:
            mock_clone.return_value = self.test_repo

            source = GitRepositorySource(f"file://{self.test_repo}")
            metadata = source.get_repository_metadata()

            self.assertEqual(metadata["name"], "test-extensions")
            self.assertEqual(metadata["version"], "1.0.0")
            self.assertEqual(metadata["author"], "Test Author")
            self.assertIn("extensions", metadata)

    def test_git_subpath_handling(self):
        """Test handling repository subpaths."""
        handler = GitSourceHandler()

        with patch("pacc.sources.git.GitCloner.clone") as mock_clone:
            mock_clone.return_value = self.test_repo

            # Test scanning only hooks subdirectory
            url_with_path = f"file://{self.test_repo}/hooks"
            extensions = handler.process_source(url_with_path)

            # Should only find hooks
            self.assertEqual(len(extensions), 1)
            self.assertEqual(extensions[0].extension_type, "hooks")
            self.assertEqual(extensions[0].name, "pre-tool-logger")

    @patch("pacc.sources.git.GitCloner")
    def test_git_error_handling(self, mock_cloner_class):
        """Test error handling for Git operations."""
        # Mock clone failure
        mock_cloner = Mock()
        mock_cloner.clone.side_effect = subprocess.CalledProcessError(1, "git clone")
        mock_cloner_class.return_value = mock_cloner

        handler = GitSourceHandler()

        with self.assertRaises(Exception):
            handler.process_source("https://github.com/nonexistent/repo.git")

    def test_git_url_normalization(self):
        """Test Git URL normalization and validation."""
        from pacc.sources.git import GitUrlParser

        parser = GitUrlParser()

        test_cases = [
            ("https://github.com/owner/repo", "https://github.com/owner/repo.git"),
            ("https://github.com/owner/repo.git", "https://github.com/owner/repo.git"),
            ("git@github.com:owner/repo.git", "git@github.com:owner/repo.git"),
        ]

        for input_url, expected in test_cases:
            with self.subTest(input_url=input_url):
                normalized = parser.normalize(input_url)
                self.assertEqual(normalized, expected)

    def test_git_authentication_handling(self):
        """Test handling of Git authentication scenarios."""
        from pacc.sources.git import GitCloner

        cloner = GitCloner()

        # Test SSH URL detection (implies key-based auth)
        ssh_url = "git@github.com:private/repo.git"
        parsed_info = cloner._parse_auth_info(ssh_url)
        self.assertEqual(parsed_info["auth_type"], "ssh")

        # Test HTTPS URL (may require token)
        https_url = "https://github.com/private/repo.git"
        parsed_info = cloner._parse_auth_info(https_url)
        self.assertEqual(parsed_info["auth_type"], "https")


class TestGitCLIIntegration(unittest.TestCase):
    """Test Git source integration with CLI commands."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.cli = PACCCli()

    @patch("pacc.sources.git.GitCloner.clone")
    def test_install_from_git_url(self, mock_clone):
        """Test installing extensions from Git URL via CLI."""
        # Create mock repository
        repo_dir = Path(self.temp_dir) / "mock-repo"
        repo_dir.mkdir()

        # Create a test hook
        hooks_dir = repo_dir / "hooks"
        hooks_dir.mkdir()
        hook_config = {"name": "test-hook", "events": ["PreToolUse"]}
        (hooks_dir / "test-hook.json").write_text(json.dumps(hook_config))

        mock_clone.return_value = repo_dir

        # Mock CLI arguments
        args = Mock()
        args.source = "https://github.com/test/extensions.git"
        args.type = None
        args.user = False
        args.project = True
        args.force = False
        args.dry_run = True
        args.interactive = False
        args.all = True
        args.verbose = False

        # Should successfully process Git URL
        result = self.cli.install_command(args)
        self.assertEqual(result, 0)

    @patch("pacc.sources.git.GitCloner.clone")
    def test_validate_git_source(self, mock_clone):
        """Test validating extensions from Git repository."""
        # Create mock repository with invalid extension
        repo_dir = Path(self.temp_dir) / "mock-repo"
        repo_dir.mkdir()

        hooks_dir = repo_dir / "hooks"
        hooks_dir.mkdir()
        # Invalid hook (missing required fields)
        (hooks_dir / "invalid-hook.json").write_text('{"name": "invalid"}')

        mock_clone.return_value = repo_dir

        args = Mock()
        args.source = "https://github.com/test/extensions.git"
        args.type = None
        args.strict = False

        # Should detect validation errors
        result = self.cli.validate_command(args)
        # May return 1 due to validation errors, but shouldn't crash
        self.assertIn(result, [0, 1])

    def test_git_url_in_info_command(self):
        """Test handling Git URLs in info command."""
        args = Mock()
        args.source = "https://github.com/test/extensions.git"
        args.type = None
        args.json = False
        args.verbose = False

        # Should handle Git URLs gracefully (may fail but shouldn't crash)
        try:
            result = self.cli.info_command(args)
            self.assertIsInstance(result, int)
        except Exception as e:
            # Expected for non-existent URLs, but should be handled gracefully
            self.assertIsInstance(e, (FileNotFoundError, OSError))


if __name__ == "__main__":
    unittest.main()
