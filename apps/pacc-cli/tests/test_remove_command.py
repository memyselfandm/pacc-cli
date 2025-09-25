"""Tests for remove command functionality."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pacc.cli import PACCCli
from pacc.core.config_manager import ClaudeConfigManager


class TestRemoveCommand:
    """Test the remove command functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cli = PACCCli()
        self.config_manager = ClaudeConfigManager()

        # Create test configurations
        self.test_project_dir = Path(self.temp_dir) / "project"
        self.test_user_dir = Path(self.temp_dir) / "user" / ".claude"

        self.test_project_dir.mkdir(parents=True)
        self.test_user_dir.mkdir(parents=True)

        # Create test extensions configuration
        self.test_config = {
            "hooks": [
                {
                    "name": "test_hook_1",
                    "path": "hooks/test_hook_1.json",
                    "events": ["before_validate"],
                    "installed_at": "2024-01-01T10:00:00Z",
                },
                {
                    "name": "test_hook_2",
                    "path": "hooks/test_hook_2.json",
                    "events": ["after_install"],
                    "installed_at": "2024-01-02T10:00:00Z",
                },
            ],
            "mcps": [
                {
                    "name": "test_mcp",
                    "path": "mcps/test_mcp.py",
                    "command": "python test_mcp.py",
                    "args": [],
                    "installed_at": "2024-01-03T10:00:00Z",
                }
            ],
            "agents": [
                {
                    "name": "test_agent",
                    "path": "agents/test_agent.md",
                    "model": "claude-3-sonnet",
                    "description": "Test agent",
                    "installed_at": "2024-01-04T10:00:00Z",
                }
            ],
            "commands": [],
        }

        # Save test configurations to correct locations
        self.project_claude_dir = self.test_project_dir / ".claude"
        self.project_claude_dir.mkdir(exist_ok=True)

        self.project_config_path = self.project_claude_dir / "settings.json"
        self.user_config_path = self.test_user_dir / "settings.json"

        with open(self.project_config_path, "w") as f:
            json.dump(self.test_config, f)
        with open(self.user_config_path, "w") as f:
            json.dump(self.test_config, f)

        # Create actual extension files in correct locations
        for ext_type in ["hooks", "mcps", "agents"]:
            for config_dir in [self.project_claude_dir, self.test_user_dir]:
                ext_dir = config_dir / ext_type
                ext_dir.mkdir(exist_ok=True)

        # Create test hook files
        (self.project_claude_dir / "hooks" / "test_hook_1.json").write_text('{"test": "hook1"}')
        (self.project_claude_dir / "hooks" / "test_hook_2.json").write_text('{"test": "hook2"}')
        (self.test_user_dir / "hooks" / "test_hook_1.json").write_text('{"test": "hook1"}')
        (self.test_user_dir / "hooks" / "test_hook_2.json").write_text('{"test": "hook2"}')

        # Create test MCP files
        (self.project_claude_dir / "mcps" / "test_mcp.py").write_text('print("test mcp")')
        (self.test_user_dir / "mcps" / "test_mcp.py").write_text('print("test mcp")')

        # Create test agent files
        (self.project_claude_dir / "agents" / "test_agent.md").write_text("# Test Agent")
        (self.test_user_dir / "agents" / "test_agent.md").write_text("# Test Agent")

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _run_in_project_dir(self, func, *args, **kwargs):
        """Helper to run a function in the test project directory."""
        original_cwd = Path.cwd()
        import os

        os.chdir(self.test_project_dir)
        try:
            return func(*args, **kwargs)
        finally:
            os.chdir(original_cwd)

    def _run_in_user_dir(self, func, *args, **kwargs):
        """Helper to run a function in the test user directory."""
        original_cwd = Path.cwd()
        original_home = Path.home
        Path.home = lambda: self.test_user_dir.parent
        import os

        os.chdir(self.test_user_dir.parent)
        try:
            return func(*args, **kwargs)
        finally:
            os.chdir(original_cwd)
            Path.home = original_home

    def test_remove_extension_project_level(self):
        """Test removing extension from project level."""
        # Change directory BEFORE creating CLI instance
        original_cwd = Path.cwd()
        import os

        os.chdir(self.test_project_dir)

        try:
            # Create CLI instance AFTER changing directory
            cli = PACCCli()

            args = Mock()
            args.name = "test_hook_1"
            args.type = None
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = False
            args.force = False
            args.verbose = False

            result = cli.remove_command(args)

            assert result == 0

            # Verify extension was removed from configuration
            with open(self.project_config_path) as f:
                updated_config = json.load(f)

            hook_names = [h["name"] for h in updated_config["hooks"]]
            assert "test_hook_1" not in hook_names
            assert "test_hook_2" in hook_names

            # Verify file was removed
            assert not (self.project_claude_dir / "hooks" / "test_hook_1.json").exists()
            assert (self.project_claude_dir / "hooks" / "test_hook_2.json").exists()

        finally:
            os.chdir(original_cwd)

    def test_remove_extension_user_level(self):
        """Test removing extension from user level."""

        def _test_user_removal():
            cli = PACCCli()

            args = Mock()
            args.name = "test_mcp"
            args.type = "mcps"
            args.user = True
            args.project = False
            args.confirm = True
            args.dry_run = False
            args.force = False
            args.verbose = False

            result = cli.remove_command(args)

            assert result == 0

            # Verify extension was removed from configuration
            with open(self.user_config_path) as f:
                updated_config = json.load(f)

            assert len(updated_config["mcps"]) == 0

            # Verify file was removed
            assert not (self.test_user_dir / "mcps" / "test_mcp.py").exists()

        self._run_in_user_dir(_test_user_removal)

    def test_remove_extension_dry_run(self):
        """Test remove command with dry-run mode."""

        def _test_dry_run():
            cli = PACCCli()

            args = Mock()
            args.name = "test_hook_1"
            args.type = None
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = True
            args.force = False
            args.verbose = False

            result = cli.remove_command(args)

            assert result == 0

            # Verify extension was NOT removed from configuration (dry run)
            with open(self.project_config_path) as f:
                config = json.load(f)

            hook_names = [h["name"] for h in config["hooks"]]
            assert "test_hook_1" in hook_names

            # Verify file was NOT removed
            assert (self.project_claude_dir / "hooks" / "test_hook_1.json").exists()

        self._run_in_project_dir(_test_dry_run)

    def test_remove_extension_not_found(self):
        """Test removing non-existent extension."""
        original_cwd = Path.cwd
        Path.cwd = lambda: self.test_project_dir

        try:
            args = Mock()
            args.name = "nonexistent_extension"
            args.type = None
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = False
            args.force = False
            args.verbose = False

            result = self.cli.remove_command(args)

            assert result == 1  # Should fail

        finally:
            Path.cwd = original_cwd

    def test_remove_extension_multiple_scopes_without_specification(self):
        """Test removing extension when it exists in multiple scopes without specifying scope."""
        original_cwd = Path.cwd
        original_home = Path.home
        Path.cwd = lambda: self.test_project_dir
        Path.home = lambda: self.test_user_dir.parent

        try:
            args = Mock()
            args.name = "test_hook_1"
            args.type = None
            args.user = False  # Neither user nor project specified
            args.project = False
            args.confirm = True
            args.dry_run = False
            args.force = False
            args.verbose = False

            result = self.cli.remove_command(args)

            # Should default to project-level removal
            assert result == 0

            # Verify extension was removed from project config
            with open(self.project_config_path) as f:
                project_config = json.load(f)

            project_hook_names = [h["name"] for h in project_config["hooks"]]
            assert "test_hook_1" not in project_hook_names

            # Verify user config is unchanged
            with open(self.user_config_path) as f:
                user_config = json.load(f)

            user_hook_names = [h["name"] for h in user_config["hooks"]]
            assert "test_hook_1" in user_hook_names

        finally:
            Path.cwd = original_cwd
            Path.home = original_home

    def test_remove_extension_with_confirmation_prompt(self):
        """Test remove command with interactive confirmation."""
        original_cwd = Path.cwd
        Path.cwd = lambda: self.test_project_dir

        try:
            args = Mock()
            args.name = "test_hook_1"
            args.type = None
            args.user = False
            args.project = True
            args.confirm = False  # Require confirmation
            args.dry_run = False
            args.force = False
            args.verbose = False

            # Mock user input to confirm removal
            with patch("builtins.input", return_value="y"):
                result = self.cli.remove_command(args)

            assert result == 0

            # Verify extension was removed
            with open(self.project_config_path) as f:
                updated_config = json.load(f)

            hook_names = [h["name"] for h in updated_config["hooks"]]
            assert "test_hook_1" not in hook_names

        finally:
            Path.cwd = original_cwd

    def test_remove_extension_confirmation_cancelled(self):
        """Test remove command when user cancels confirmation."""
        original_cwd = Path.cwd
        Path.cwd = lambda: self.test_project_dir

        try:
            args = Mock()
            args.name = "test_hook_1"
            args.type = None
            args.user = False
            args.project = True
            args.confirm = False
            args.dry_run = False
            args.force = False
            args.verbose = False

            # Mock user input to cancel removal
            with patch("builtins.input", return_value="n"):
                result = self.cli.remove_command(args)

            assert result == 0  # Should succeed (user chose not to remove)

            # Verify extension was NOT removed
            with open(self.project_config_path) as f:
                config = json.load(f)

            hook_names = [h["name"] for h in config["hooks"]]
            assert "test_hook_1" in hook_names

        finally:
            Path.cwd = original_cwd

    def test_remove_extension_with_dependencies(self):
        """Test removing extension that has dependencies."""
        # Add dependent extension to config
        dependent_config = self.test_config.copy()
        dependent_config["hooks"].append(
            {
                "name": "dependent_hook",
                "path": "hooks/dependent_hook.json",
                "events": ["after_validate"],
                "dependencies": ["test_hook_1"],  # Depends on test_hook_1
                "installed_at": "2024-01-05T10:00:00Z",
            }
        )

        config_path = self.test_project_dir / "settings.json"
        with open(config_path, "w") as f:
            json.dump(dependent_config, f)

        original_cwd = Path.cwd
        Path.cwd = lambda: self.test_project_dir

        try:
            args = Mock()
            args.name = "test_hook_1"
            args.type = None
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = False
            args.force = False  # Don't force removal
            args.verbose = False

            result = self.cli.remove_command(args)

            # Should fail due to dependency
            assert result == 1

            # Verify extension was NOT removed due to dependency
            with open(config_path) as f:
                config = json.load(f)

            hook_names = [h["name"] for h in config["hooks"]]
            assert "test_hook_1" in hook_names

        finally:
            Path.cwd = original_cwd

    def test_remove_extension_force_with_dependencies(self):
        """Test force removing extension that has dependencies."""
        # Add dependent extension to config
        dependent_config = self.test_config.copy()
        dependent_config["hooks"].append(
            {
                "name": "dependent_hook",
                "path": "hooks/dependent_hook.json",
                "events": ["after_validate"],
                "dependencies": ["test_hook_1"],
                "installed_at": "2024-01-05T10:00:00Z",
            }
        )

        config_path = self.test_project_dir / "settings.json"
        with open(config_path, "w") as f:
            json.dump(dependent_config, f)

        original_cwd = Path.cwd
        Path.cwd = lambda: self.test_project_dir

        try:
            args = Mock()
            args.name = "test_hook_1"
            args.type = None
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = False
            args.force = True  # Force removal
            args.verbose = False

            result = self.cli.remove_command(args)

            assert result == 0

            # Verify extension was removed despite dependency
            with open(config_path) as f:
                config = json.load(f)

            hook_names = [h["name"] for h in config["hooks"]]
            assert "test_hook_1" not in hook_names
            assert "dependent_hook" in hook_names  # Dependent should remain

        finally:
            Path.cwd = original_cwd

    def test_remove_extension_configuration_backup_and_rollback(self):
        """Test that configuration is backed up and rolled back on failure."""
        original_cwd = Path.cwd
        Path.cwd = lambda: self.test_project_dir

        try:
            # Mock file deletion to fail
            original_unlink = Path.unlink

            def mock_unlink(self, *args, **kwargs):
                if "test_hook_1.json" in str(self):
                    raise OSError("Simulated file deletion failure")
                return original_unlink(self, *args, **kwargs)

            Path.unlink = mock_unlink

            args = Mock()
            args.name = "test_hook_1"
            args.type = None
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = False
            args.force = False
            args.verbose = False

            result = self.cli.remove_command(args)

            # Should fail due to file deletion error
            assert result == 1

            # Verify configuration was rolled back (hook still present)
            with open(self.project_config_path) as f:
                config = json.load(f)

            hook_names = [h["name"] for h in config["hooks"]]
            assert "test_hook_1" in hook_names

        finally:
            Path.cwd = original_cwd
            Path.unlink = original_unlink

    def test_remove_extension_type_specific_search(self):
        """Test removing extension with specific type specification."""
        original_cwd = Path.cwd
        Path.cwd = lambda: self.test_project_dir

        try:
            args = Mock()
            args.name = "test_mcp"
            args.type = "mcps"  # Specify type
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = False
            args.force = False
            args.verbose = False

            result = self.cli.remove_command(args)

            assert result == 0

            # Verify MCP was removed
            with open(self.project_config_path) as f:
                config = json.load(f)

            assert len(config["mcps"]) == 0

        finally:
            Path.cwd = original_cwd

    def test_remove_extension_wrong_type_specified(self):
        """Test removing extension with wrong type specification."""
        original_cwd = Path.cwd
        Path.cwd = lambda: self.test_project_dir

        try:
            args = Mock()
            args.name = "test_mcp"
            args.type = "hooks"  # Wrong type (should be mcps)
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = False
            args.force = False
            args.verbose = False

            result = self.cli.remove_command(args)

            # Should fail - extension not found in specified type
            assert result == 1

            # Verify MCP was NOT removed (still exists)
            with open(self.project_config_path) as f:
                config = json.load(f)

            assert len(config["mcps"]) == 1

        finally:
            Path.cwd = original_cwd

    def test_remove_extension_verbose_output(self):
        """Test remove command with verbose output."""
        original_cwd = Path.cwd
        Path.cwd = lambda: self.test_project_dir

        try:
            args = Mock()
            args.name = "test_hook_1"
            args.type = None
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = False
            args.force = False
            args.verbose = True

            # Capture output
            with patch("builtins.print") as mock_print:
                result = self.cli.remove_command(args)

            assert result == 0

            # Check that verbose information was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            verbose_output = "\n".join(print_calls)

            assert "test_hook_1" in verbose_output
            assert any("hook" in call.lower() for call in print_calls)

        finally:
            Path.cwd = original_cwd

    def test_remove_multiple_extensions_same_name_different_types(self):
        """Test handling when multiple extensions have same name but different types."""
        # Add extension with same name in different type
        config_with_duplicate_names = self.test_config.copy()
        config_with_duplicate_names["agents"].append(
            {
                "name": "test_hook_1",  # Same name as hook
                "path": "agents/test_hook_1.md",
                "model": "claude-3-sonnet",
                "description": "Agent with same name as hook",
                "installed_at": "2024-01-06T10:00:00Z",
            }
        )

        config_path = self.test_project_dir / "settings.json"
        with open(config_path, "w") as f:
            json.dump(config_with_duplicate_names, f)

        # Create agent file
        (self.test_project_dir / "agents" / "test_hook_1.md").write_text("# Agent with hook name")

        original_cwd = Path.cwd
        Path.cwd = lambda: self.test_project_dir

        try:
            # Remove without specifying type - should prompt user to choose
            args = Mock()
            args.name = "test_hook_1"
            args.type = None  # No type specified
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = False
            args.force = False
            args.verbose = False

            # Mock user selection to choose the hook (index 0)
            with patch("builtins.input", return_value="0"):
                result = self.cli.remove_command(args)

            assert result == 0

            # Verify hook was removed but agent with same name remains
            with open(config_path) as f:
                config = json.load(f)

            hook_names = [h["name"] for h in config["hooks"]]
            agent_names = [a["name"] for a in config["agents"]]

            assert "test_hook_1" not in hook_names  # Hook removed
            assert "test_hook_1" in agent_names  # Agent remains

        finally:
            Path.cwd = original_cwd


class TestRemoveCommandDependencyChecking:
    """Test dependency checking functionality for remove command."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cli = PACCCli()
        self.test_dir = Path(self.temp_dir) / "test_project"
        self.test_dir.mkdir(parents=True)

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_dependencies_simple(self):
        """Test finding simple dependencies."""
        config = {
            "hooks": [
                {"name": "base_hook", "path": "hooks/base.json"},
                {"name": "dependent_hook", "path": "hooks/dep.json", "dependencies": ["base_hook"]},
            ],
            "mcps": [],
            "agents": [],
            "commands": [],
        }

        config_path = self.test_dir / "settings.json"
        with open(config_path, "w") as f:
            json.dump(config, f)

        dependencies = self.cli._find_extension_dependencies("base_hook", config)

        assert len(dependencies) == 1
        assert dependencies[0]["name"] == "dependent_hook"

    def test_find_dependencies_multiple(self):
        """Test finding multiple dependencies."""
        config = {
            "hooks": [
                {"name": "base_hook", "path": "hooks/base.json"},
                {"name": "dep1", "path": "hooks/dep1.json", "dependencies": ["base_hook"]},
                {"name": "dep2", "path": "hooks/dep2.json", "dependencies": ["base_hook", "other"]},
                {"name": "independent", "path": "hooks/indep.json"},
            ],
            "mcps": [{"name": "mcp_dep", "path": "mcps/mcp.py", "dependencies": ["base_hook"]}],
            "agents": [],
            "commands": [],
        }

        dependencies = self.cli._find_extension_dependencies("base_hook", config)

        assert len(dependencies) == 3
        dep_names = [d["name"] for d in dependencies]
        assert "dep1" in dep_names
        assert "dep2" in dep_names
        assert "mcp_dep" in dep_names
        assert "independent" not in dep_names

    def test_find_dependencies_none(self):
        """Test finding no dependencies."""
        config = {
            "hooks": [
                {"name": "hook1", "path": "hooks/hook1.json"},
                {"name": "hook2", "path": "hooks/hook2.json", "dependencies": ["other_hook"]},
            ],
            "mcps": [],
            "agents": [],
            "commands": [],
        }

        dependencies = self.cli._find_extension_dependencies("hook1", config)

        assert len(dependencies) == 0

    def test_find_dependencies_cross_type(self):
        """Test finding dependencies across different extension types."""
        config = {
            "hooks": [{"name": "base_extension", "path": "hooks/base.json"}],
            "mcps": [{"name": "mcp1", "path": "mcps/mcp1.py", "dependencies": ["base_extension"]}],
            "agents": [
                {"name": "agent1", "path": "agents/agent1.md", "dependencies": ["base_extension"]}
            ],
            "commands": [
                {"name": "cmd1", "path": "commands/cmd1.md", "dependencies": ["base_extension"]}
            ],
        }

        dependencies = self.cli._find_extension_dependencies("base_extension", config)

        assert len(dependencies) == 3
        dep_names = [d["name"] for d in dependencies]
        assert "mcp1" in dep_names
        assert "agent1" in dep_names
        assert "cmd1" in dep_names


class TestRemoveCommandIntegration:
    """Integration tests for remove command with real file operations."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_project = Path(self.temp_dir) / "test_project"
        self.test_project.mkdir()

        # Create .claude directory and config
        self.claude_dir = self.test_project / ".claude"
        self.claude_dir.mkdir()

        # Create extension directories
        for ext_type in ["hooks", "mcps", "agents", "commands"]:
            (self.claude_dir / ext_type).mkdir()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_to_end_removal_workflow(self):
        """Test complete end-to-end removal workflow."""
        # Create test extension files
        hook_file = self.claude_dir / "hooks" / "test_hook.json"
        hook_file.write_text('{"event": "before_validate", "script": "test.py"}')

        mcp_file = self.claude_dir / "mcps" / "test_mcp.py"
        mcp_file.write_text('print("Hello from test MCP")')

        # Create configuration
        config = {
            "hooks": [
                {
                    "name": "test_hook",
                    "path": "hooks/test_hook.json",
                    "events": ["before_validate"],
                    "installed_at": "2024-01-01T10:00:00Z",
                }
            ],
            "mcps": [
                {
                    "name": "test_mcp",
                    "path": "mcps/test_mcp.py",
                    "command": "python test_mcp.py",
                    "installed_at": "2024-01-02T10:00:00Z",
                }
            ],
            "agents": [],
            "commands": [],
        }

        config_file = self.claude_dir / "settings.json"
        with open(config_file, "w") as f:
            json.dump(config, f)

        # Change to test project directory
        original_cwd = Path.cwd()
        import os

        os.chdir(self.test_project)

        try:
            cli = PACCCli()

            # Remove hook extension
            args = Mock()
            args.name = "test_hook"
            args.type = None
            args.user = False
            args.project = True
            args.confirm = True
            args.dry_run = False
            args.force = False
            args.verbose = False

            result = cli.remove_command(args)

            assert result == 0

            # Verify hook was removed
            assert not hook_file.exists()

            # Verify configuration was updated
            with open(config_file) as f:
                updated_config = json.load(f)

            assert len(updated_config["hooks"]) == 0
            assert len(updated_config["mcps"]) == 1  # MCP should remain

            # Verify MCP file still exists
            assert mcp_file.exists()

        finally:
            os.chdir(original_cwd)
