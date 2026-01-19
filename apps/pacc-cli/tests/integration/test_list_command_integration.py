"""Integration tests for the PACC list command."""

import json
import tempfile
from pathlib import Path

import pytest

from pacc.cli import main


class TestListCommandIntegration:
    """Integration tests for list command functionality."""

    @pytest.fixture
    def temp_claude_dir(self):
        """Create temporary Claude configuration directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            yield claude_dir

    @pytest.fixture
    def sample_settings(self, temp_claude_dir):
        """Create sample settings.json file."""
        settings = {
            "hooks": [
                {
                    "name": "test-hook",
                    "path": "hooks/test-hook.json",
                    "events": ["file:created"],
                    "description": "Test file creation hook",
                    "installed_at": "2024-01-15T10:00:00Z",
                    "source": "local",
                }
            ],
            "mcps": [
                {
                    "name": "code-server",
                    "path": "mcps/code-server.py",
                    "command": "python mcps/code-server.py",
                    "description": "Code analysis server",
                    "installed_at": "2024-01-16T11:00:00Z",
                    "source": "github.com/example/repo",
                    "version": "1.0.0",
                }
            ],
            "agents": [
                {
                    "name": "reviewer",
                    "path": "agents/reviewer.md",
                    "model": "claude-3-sonnet",
                    "description": "Code review assistant",
                    "installed_at": "2024-01-14T09:00:00Z",
                }
            ],
            "commands": [
                {
                    "name": "/test",
                    "path": "commands/test.md",
                    "description": "Run tests",
                    "aliases": ["/t"],
                    "installed_at": "2024-01-17T15:00:00Z",
                }
            ],
        }

        settings_path = temp_claude_dir / "settings.json"
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

        return settings_path

    def test_list_command_basic(self, temp_claude_dir, sample_settings, monkeypatch, capsys):
        """Test basic list command functionality."""
        # Change to directory containing .claude
        monkeypatch.chdir(temp_claude_dir.parent)

        # Run list command
        import sys

        sys.argv = ["pacc", "list"]

        try:
            main()
        except SystemExit as e:
            assert e.code == 0

        captured = capsys.readouterr()

        # Check output contains expected extensions
        assert "test-hook" in captured.out
        assert "code-server" in captured.out
        assert "reviewer" in captured.out
        assert "/test" in captured.out

        # Check table headers
        assert "Name" in captured.out
        assert "Type" in captured.out
        assert "Description" in captured.out

    def test_list_command_json_format(self, temp_claude_dir, sample_settings, monkeypatch, capsys):
        """Test JSON output format."""
        monkeypatch.chdir(temp_claude_dir.parent)

        import sys

        sys.argv = ["pacc", "list", "--format", "json"]

        try:
            main()
        except SystemExit as e:
            assert e.code == 0

        captured = capsys.readouterr()

        # Parse JSON output
        data = json.loads(captured.out)
        assert "extensions" in data
        assert "count" in data

        # Verify extension data
        ext_names = [ext["name"] for ext in data["extensions"]]
        assert "test-hook" in ext_names
        assert "code-server" in ext_names
        assert "reviewer" in ext_names
        assert "/test" in ext_names

    def test_list_command_filter_by_type(
        self, temp_claude_dir, sample_settings, monkeypatch, capsys
    ):
        """Test filtering by extension type."""
        monkeypatch.chdir(temp_claude_dir.parent)

        import sys

        sys.argv = ["pacc", "list", "hooks"]

        try:
            main()
        except SystemExit as e:
            assert e.code == 0

        captured = capsys.readouterr()

        # Should only contain hooks
        assert "test-hook" in captured.out
        assert "code-server" not in captured.out
        assert "reviewer" not in captured.out
        assert "/test" not in captured.out

    def test_list_command_filter_pattern(
        self, temp_claude_dir, sample_settings, monkeypatch, capsys
    ):
        """Test filtering by name pattern."""
        monkeypatch.chdir(temp_claude_dir.parent)

        import sys

        sys.argv = ["pacc", "list", "--filter", "*-server"]

        try:
            main()
        except SystemExit as e:
            assert e.code == 0

        captured = capsys.readouterr()

        # Should only match code-server
        assert "code-server" in captured.out
        assert "test-hook" not in captured.out
        assert "reviewer" not in captured.out

    def test_list_command_search(self, temp_claude_dir, sample_settings, monkeypatch, capsys):
        """Test searching in descriptions."""
        monkeypatch.chdir(temp_claude_dir.parent)

        import sys

        sys.argv = ["pacc", "list", "--search", "code"]

        try:
            main()
        except SystemExit as e:
            assert e.code == 0

        captured = capsys.readouterr()

        # Should match items with "code" in description
        assert "code-server" in captured.out  # "Code analysis server"
        assert "reviewer" in captured.out  # "Code review assistant"
        assert "test-hook" not in captured.out
        assert "/test" not in captured.out

    def test_list_command_verbose(self, temp_claude_dir, sample_settings, monkeypatch, capsys):
        """Test verbose output."""
        monkeypatch.chdir(temp_claude_dir.parent)

        import sys

        sys.argv = ["pacc", "--verbose", "list"]

        try:
            main()
        except SystemExit as e:
            assert e.code == 0

        captured = capsys.readouterr()

        # Should show additional columns
        assert "Source" in captured.out
        assert "Installed" in captured.out

        # Should show metadata
        assert "local" in captured.out
        assert "github.com/example/repo" in captured.out
        assert "2024-01-" in captured.out

    def test_list_command_empty_config(self, temp_claude_dir, monkeypatch, capsys):
        """Test listing with empty configuration."""
        # Create empty settings.json
        settings_path = temp_claude_dir / "settings.json"
        with open(settings_path, "w") as f:
            json.dump({"hooks": [], "mcps": [], "agents": [], "commands": []}, f)

        monkeypatch.chdir(temp_claude_dir.parent)
        # Ensure we don't pick up user's home .claude directory
        monkeypatch.setenv("HOME", str(temp_claude_dir.parent))

        import sys

        sys.argv = ["pacc", "list", "--project"]

        try:
            main()
        except SystemExit as e:
            assert e.code == 0

        captured = capsys.readouterr()
        assert "No extensions installed" in captured.out

    def test_list_command_no_config(self, monkeypatch, capsys):
        """Test listing when no configuration exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.chdir(tmpdir)
            # Ensure we don't pick up user's home .claude directory
            monkeypatch.setenv("HOME", str(tmpdir))

            import sys

            sys.argv = ["pacc", "list", "--project"]

            try:
                main()
            except SystemExit as e:
                assert e.code == 0

            captured = capsys.readouterr()
            assert "No extensions installed" in captured.out
