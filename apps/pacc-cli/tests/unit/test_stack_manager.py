"""Unit tests for pacc.stacks.manager module."""

import json
from pathlib import Path

import pytest
import yaml

from pacc.stacks.manager import (
    StackError,
    StackInfo,
    StackManifest,
    StackManager,
    StackResult,
    SyncResult,
)


class TestStackManifest:
    """Test StackManifest dataclass and parsing."""

    def test_from_dict_minimal(self):
        data = {"name": "test-stack", "version": "1.0.0"}
        manifest = StackManifest.from_dict(data)
        assert manifest.name == "test-stack"
        assert manifest.version == "1.0.0"
        assert manifest.mcp_servers == {}
        assert manifest.hooks == {}
        assert manifest.commands == []

    def test_from_dict_full(self):
        data = {
            "name": "full-stack",
            "version": "2.0.0",
            "description": "A full stack",
            "author": "tester",
            "mcp_servers": {"github": {"command": "npx", "args": ["-y", "server"]}},
            "hooks": {"PreToolUse": [{"matcher": "Bash"}]},
            "commands": [{"source": "./cmd.md", "name": "my-cmd"}],
            "agents": [{"source": "./agent.md", "name": "my-agent"}],
            "settings": {"model": "sonnet"},
            "fragments": [{"source": "./frag.md", "name": "my-frag"}],
        }
        manifest = StackManifest.from_dict(data)
        assert manifest.name == "full-stack"
        assert manifest.author == "tester"
        assert "github" in manifest.mcp_servers
        assert len(manifest.commands) == 1
        assert len(manifest.agents) == 1
        assert len(manifest.fragments) == 1

    def test_from_dict_missing_name(self):
        with pytest.raises(StackError, match="missing required field 'name'"):
            StackManifest.from_dict({"version": "1.0.0"})

    def test_from_dict_missing_version(self):
        with pytest.raises(StackError, match="missing required field 'version'"):
            StackManifest.from_dict({"name": "test"})

    def test_to_dict(self):
        manifest = StackManifest(
            name="test", version="1.0.0", description="desc", mcp_servers={"s": {"cmd": "x"}}
        )
        d = manifest.to_dict()
        assert d["name"] == "test"
        assert d["version"] == "1.0.0"
        assert d["description"] == "desc"
        assert "s" in d["mcp_servers"]

    def test_to_dict_omits_empty(self):
        manifest = StackManifest(name="minimal", version="1.0.0")
        d = manifest.to_dict()
        assert "hooks" not in d
        assert "commands" not in d
        assert "agents" not in d

    def test_roundtrip(self):
        data = {
            "name": "roundtrip",
            "version": "1.0.0",
            "description": "Test roundtrip",
            "mcp_servers": {"a": {"command": "test"}},
        }
        manifest = StackManifest.from_dict(data)
        result = manifest.to_dict()
        assert result["name"] == data["name"]
        assert result["mcp_servers"] == data["mcp_servers"]


class TestStackResult:
    """Test StackResult dataclass."""

    def test_success_result(self):
        result = StackResult(success=True, message="ok", stack_name="test")
        assert result.success is True
        assert result.changes == []

    def test_failure_result(self):
        result = StackResult(success=False, message="failed", warnings=["warn1"])
        assert result.success is False
        assert len(result.warnings) == 1


class TestStackInfo:
    """Test StackInfo dataclass."""

    def test_creation(self):
        info = StackInfo(
            name="test",
            version="1.0.0",
            description="desc",
            author="me",
            source="https://github.com/owner/repo",
            scope="project",
            commit="abc123",
            sha256="def456",
        )
        assert info.name == "test"
        assert info.scope == "project"


class TestSyncResult:
    """Test SyncResult dataclass."""

    def test_creation(self):
        result = SyncResult(success=True, message="ok", added=1, removed=0, updated=2, unchanged=3)
        assert result.added == 1
        assert result.updated == 2


class TestStackManagerValidation:
    """Test StackManager URL validation."""

    def test_validate_https_url(self):
        StackManager._validate_source("https://github.com/owner/repo")
        StackManager._validate_source("https://github.com/owner/repo.git")

    def test_validate_ssh_url(self):
        StackManager._validate_source("git@github.com:owner/repo.git")

    def test_validate_shorthand(self):
        StackManager._validate_source("owner/repo")

    def test_reject_shell_metacharacters(self):
        with pytest.raises(StackError, match="shell metacharacters"):
            StackManager._validate_source("https://evil.com/repo; rm -rf /")

    def test_reject_pipe(self):
        with pytest.raises(StackError, match="shell metacharacters"):
            StackManager._validate_source("https://evil.com/repo | cat /etc/passwd")

    def test_reject_backtick(self):
        with pytest.raises(StackError, match="shell metacharacters"):
            StackManager._validate_source("`whoami`")

    def test_reject_dollar(self):
        with pytest.raises(StackError, match="shell metacharacters"):
            StackManager._validate_source("$(whoami)")

    def test_reject_invalid_url(self):
        with pytest.raises(StackError, match="Invalid source URL"):
            StackManager._validate_source("not-a-valid-url-at-all!!!")

    def test_reject_newline_injection(self):
        with pytest.raises(StackError, match="shell metacharacters"):
            StackManager._validate_source("https://example.com/repo\nmalicious")


class TestStackManagerLocalOperations:
    """Test StackManager operations that don't require network."""

    @pytest.fixture
    def manager(self, temp_dir):
        return StackManager(project_dir=temp_dir)

    @pytest.fixture
    def stack_dir(self, temp_dir):
        """Create a local directory containing a valid stack.yaml."""
        d = temp_dir / "my-stack-source"
        d.mkdir()
        manifest = {
            "name": "test-stack",
            "version": "1.0.0",
            "description": "A test stack",
            "mcp_servers": {
                "test-server": {"command": "echo", "args": ["hello"]},
            },
            "settings": {"model": "sonnet"},
        }
        (d / "stack.yaml").write_text(yaml.safe_dump(manifest))
        return d

    def test_install_from_local_dir(self, manager, stack_dir, temp_dir):
        result = manager.install_stack(str(stack_dir), scope="project")
        assert result.success is True
        assert result.stack_name == "test-stack"
        assert len(result.changes) > 0

        # Verify settings were written
        settings_path = temp_dir / ".claude" / "settings.json"
        assert settings_path.exists()
        settings = json.loads(settings_path.read_text())
        assert "test-server" in settings.get("mcpServers", {})
        assert settings.get("model") == "sonnet"

    def test_install_dry_run(self, manager, stack_dir):
        result = manager.install_stack(str(stack_dir), dry_run=True)
        assert result.success is True
        assert "Dry run" in result.message
        assert len(result.changes) > 0

    def test_install_missing_manifest(self, manager, temp_dir):
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()
        result = manager.install_stack(str(empty_dir))
        assert result.success is False
        assert "stack.yaml" in result.message

    def test_list_stacks_empty(self, manager):
        stacks = manager.list_stacks()
        assert stacks == []

    def test_list_stacks_after_install(self, manager, stack_dir):
        manager.install_stack(str(stack_dir), scope="project")
        stacks = manager.list_stacks()
        assert len(stacks) == 1
        assert stacks[0].name == "test-stack"

    def test_info_stack_found(self, manager, stack_dir):
        manager.install_stack(str(stack_dir))
        info = manager.info_stack("test-stack")
        assert info is not None
        assert info.name == "test-stack"
        assert info.version == "1.0.0"

    def test_info_stack_not_found(self, manager):
        info = manager.info_stack("nonexistent")
        assert info is None

    def test_remove_stack(self, manager, stack_dir, temp_dir):
        manager.install_stack(str(stack_dir))
        result = manager.remove_stack("test-stack", scope="project")
        assert result.success is True
        assert len(result.changes) > 0

        # Verify MCP server removed from settings
        settings_path = temp_dir / ".claude" / "settings.json"
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
            assert "test-server" not in settings.get("mcpServers", {})

    def test_remove_nonexistent_stack(self, manager):
        result = manager.remove_stack("ghost", scope="project")
        assert result.success is False

    def test_remove_dry_run(self, manager, stack_dir):
        manager.install_stack(str(stack_dir))
        result = manager.remove_stack("test-stack", dry_run=True)
        assert result.success is True
        assert "Dry run" in result.message
        # Stack should still exist after dry run
        assert manager.info_stack("test-stack") is not None

    def test_sync_no_pacc_json(self, manager):
        result = manager.sync_stacks()
        assert result.success is True
        assert "nothing to sync" in result.message.lower()

    def test_sync_empty_stacks(self, manager, temp_dir):
        (temp_dir / "pacc.json").write_text('{"stacks": {}}')
        result = manager.sync_stacks()
        assert result.success is True

    def test_lockfile_created(self, manager, stack_dir, temp_dir):
        manager.install_stack(str(stack_dir))
        lock_path = temp_dir / "pacc.lock.yaml"
        assert lock_path.exists()
        lock_data = yaml.safe_load(lock_path.read_text())
        assert "stacks" in lock_data
        assert "test-stack" in lock_data["stacks"]
        assert "sha256" in lock_data["stacks"]["test-stack"]

    def test_lockfile_removed_on_uninstall(self, manager, stack_dir, temp_dir):
        manager.install_stack(str(stack_dir))
        manager.remove_stack("test-stack")
        lock_path = temp_dir / "pacc.lock.yaml"
        if lock_path.exists():
            lock_data = yaml.safe_load(lock_path.read_text())
            assert "test-stack" not in lock_data.get("stacks", {})

    def test_pacc_json_updated(self, manager, stack_dir, temp_dir):
        manager.install_stack(str(stack_dir))
        pacc_json = json.loads((temp_dir / "pacc.json").read_text())
        assert "test-stack" in pacc_json.get("stacks", {})

    def test_backup_created(self, manager, stack_dir, temp_dir):
        """Installing twice should create a backup of settings."""
        manager.install_stack(str(stack_dir))
        manager.install_stack(str(stack_dir))  # Second install triggers backup
        settings_dir = temp_dir / ".claude"
        backups = list(settings_dir.glob("settings.*.bak"))
        assert len(backups) >= 1


class TestStackManagerExport:
    """Test export functionality."""

    @pytest.fixture
    def manager(self, temp_dir):
        return StackManager(project_dir=temp_dir)

    def test_export_empty_config(self, manager, temp_dir):
        output = temp_dir / "exported"
        result = manager.export_stack("my-export", str(output))
        assert result.success is True
        assert (output / "stack.yaml").exists()
        assert (output / "README.md").exists()

    def test_export_with_mcp_servers(self, manager, temp_dir):
        # Set up settings with MCP servers
        settings_dir = temp_dir / ".claude"
        settings_dir.mkdir(parents=True)
        settings = {
            "mcpServers": {"github": {"command": "npx", "args": ["-y", "server"]}},
            "model": "sonnet",
        }
        (settings_dir / "settings.json").write_text(json.dumps(settings))

        output = temp_dir / "exported"
        result = manager.export_stack("my-export", str(output))
        assert result.success is True

        manifest = yaml.safe_load((output / "stack.yaml").read_text())
        assert "github" in manifest.get("mcp_servers", {})
        assert manifest.get("settings", {}).get("model") == "sonnet"

    def test_export_readme_generated(self, manager, temp_dir):
        output = temp_dir / "exported"
        manager.export_stack("my-export", str(output))
        readme = (output / "README.md").read_text()
        assert "my-export" in readme
        assert "pacc" in readme.lower()
