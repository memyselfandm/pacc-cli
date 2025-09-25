"""Mock utilities for PACC E2E tests."""

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock, patch


class MockGitRepository:
    """Mock Git repository for testing."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.commits = []
        self.branches = ["main"]
        self.current_branch = "main"
        self.remotes = {"origin": "https://github.com/test/repo.git"}
        self.is_dirty = False

    def clone(self, url: str, target_path: Path) -> bool:
        """Mock git clone operation."""
        target_path.mkdir(parents=True, exist_ok=True)
        (target_path / ".git").mkdir(exist_ok=True)
        return True

    def pull(self) -> bool:
        """Mock git pull operation."""
        return True

    def push(self, branch: str = None) -> bool:
        """Mock git push operation."""
        return True

    def add(self, files: List[str]) -> bool:
        """Mock git add operation."""
        return True

    def commit(self, message: str) -> str:
        """Mock git commit operation."""
        commit_hash = f"abc123{len(self.commits)}"
        self.commits.append(
            {"hash": commit_hash, "message": message, "timestamp": "2024-01-01T00:00:00Z"}
        )
        return commit_hash

    def checkout(self, branch: str) -> bool:
        """Mock git checkout operation."""
        if branch not in self.branches:
            self.branches.append(branch)
        self.current_branch = branch
        return True

    def status(self) -> Dict[str, Any]:
        """Mock git status operation."""
        return {
            "branch": self.current_branch,
            "dirty": self.is_dirty,
            "staged": [],
            "unstaged": [],
            "untracked": [],
        }

    def log(self, count: int = 10) -> List[Dict[str, Any]]:
        """Mock git log operation."""
        return self.commits[-count:] if self.commits else []


class MockFileSystem:
    """Mock file system for testing."""

    def __init__(self):
        self.files = {}
        self.directories = set()
        self.access_errors = set()
        self.permission_errors = set()

    def add_file(self, path: str, content: str = ""):
        """Add a mock file."""
        self.files[path] = content
        # Add parent directories
        parent = str(Path(path).parent)
        while parent != str(Path(parent).parent):
            self.directories.add(parent)
            parent = str(Path(parent).parent)

    def add_directory(self, path: str):
        """Add a mock directory."""
        self.directories.add(path)

    def add_access_error(self, path: str):
        """Add a path that should raise access errors."""
        self.access_errors.add(path)

    def add_permission_error(self, path: str):
        """Add a path that should raise permission errors."""
        self.permission_errors.add(path)

    def exists(self, path: str) -> bool:
        """Mock path existence check."""
        if path in self.access_errors:
            raise OSError(f"Access denied: {path}")
        return path in self.files or path in self.directories

    def is_file(self, path: str) -> bool:
        """Mock file check."""
        return path in self.files

    def is_dir(self, path: str) -> bool:
        """Mock directory check."""
        return path in self.directories

    def read_text(self, path: str) -> str:
        """Mock file reading."""
        if path in self.permission_errors:
            raise PermissionError(f"Permission denied: {path}")
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        return self.files[path]

    def write_text(self, path: str, content: str):
        """Mock file writing."""
        if path in self.permission_errors:
            raise PermissionError(f"Permission denied: {path}")
        self.files[path] = content

    def listdir(self, path: str) -> List[str]:
        """Mock directory listing."""
        if path not in self.directories:
            raise FileNotFoundError(f"Directory not found: {path}")

        items = []
        for file_path in self.files:
            if str(Path(file_path).parent) == path:
                items.append(Path(file_path).name)

        for dir_path in self.directories:
            if str(Path(dir_path).parent) == path:
                items.append(Path(dir_path).name)

        return items


class MockEnvironment:
    """Mock environment for testing."""

    def __init__(self):
        self.env_vars = dict(os.environ)
        self.platform = "linux"
        self.shell = "bash"
        self.home_dir = "/home/test"
        self.temp_dir = "/tmp"

    def set_platform(self, platform: str):
        """Set the mock platform."""
        self.platform = platform
        if platform == "windows":
            self.shell = "cmd"
            self.home_dir = "C:\\Users\\test"
            self.temp_dir = "C:\\temp"
        elif platform == "macos":
            self.shell = "zsh"
            self.home_dir = "/Users/test"

    def set_env(self, key: str, value: str):
        """Set environment variable."""
        self.env_vars[key] = value

    def get_env(self, key: str, default: str = None) -> str:
        """Get environment variable."""
        return self.env_vars.get(key, default)

    def get_platform(self) -> str:
        """Get platform."""
        return self.platform

    def get_shell(self) -> str:
        """Get shell."""
        return self.shell


class MockClaudeEnvironment:
    """Mock Claude Code environment."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.claude_dir = base_path / ".claude"
        self.settings = {}
        self.config = {}
        self.plugins_enabled = True
        self.backup_count = 0

    def setup(self):
        """Setup mock Claude environment."""
        self.claude_dir.mkdir(parents=True, exist_ok=True)

        self.settings = {
            "modelId": "claude-3-5-sonnet-20241022",
            "maxTokens": 8192,
            "temperature": 0,
            "systemPrompt": "",
            "plugins": {},
            "hooks": {},
            "agents": {},
            "commands": {},
            "mcp": {"servers": {}},
            "mock": True,
        }

        self.config = {
            "version": "1.0.0",
            "mock": True,
            "extensions": {"hooks": {}, "agents": {}, "commands": {}, "mcp": {"servers": {}}},
        }

        self.save_settings()
        self.save_config()

    def save_settings(self):
        """Save settings to file."""
        (self.claude_dir / "settings.json").write_text(json.dumps(self.settings, indent=2))

    def save_config(self):
        """Save config to file."""
        (self.claude_dir / "config.json").write_text(json.dumps(self.config, indent=2))

    def add_plugin(self, plugin_type: str, plugin_name: str, plugin_path: str):
        """Add a plugin to the environment."""
        if plugin_type == "mcp":
            self.settings["mcp"]["servers"][plugin_name] = {
                "command": "python",
                "args": ["-m", plugin_name],
            }
        else:
            self.settings[plugin_type][plugin_name] = {"path": plugin_path, "enabled": True}
        self.save_settings()

    def remove_plugin(self, plugin_type: str, plugin_name: str):
        """Remove a plugin from the environment."""
        if plugin_type == "mcp":
            self.settings["mcp"]["servers"].pop(plugin_name, None)
        else:
            self.settings[plugin_type].pop(plugin_name, None)
        self.save_settings()

    def create_backup(self) -> str:
        """Create a backup."""
        self.backup_count += 1
        backup_id = f"backup_{self.backup_count}"
        backup_dir = self.claude_dir / "backups" / backup_id
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Copy current settings
        import shutil

        shutil.copy2(self.claude_dir / "settings.json", backup_dir / "settings.json")
        shutil.copy2(self.claude_dir / "config.json", backup_dir / "config.json")

        return backup_id

    def restore_backup(self, backup_id: str):
        """Restore from backup."""
        backup_dir = self.claude_dir / "backups" / backup_id
        if backup_dir.exists():
            import shutil

            shutil.copy2(backup_dir / "settings.json", self.claude_dir / "settings.json")
            shutil.copy2(backup_dir / "config.json", self.claude_dir / "config.json")

            # Reload settings and config
            self.settings = json.loads((self.claude_dir / "settings.json").read_text())
            self.config = json.loads((self.claude_dir / "config.json").read_text())


@contextmanager
def patch_claude_environment(claude_dir: Path):
    """Context manager to patch Claude environment detection."""
    with patch("pacc.core.project_config.ProjectConfigValidator._find_claude_dir") as mock_find:
        mock_find.return_value = claude_dir
        yield mock_find


@contextmanager
def patch_git_operations():
    """Context manager to patch Git operations."""
    with patch("pacc.plugins.repository.git") as mock_git:
        mock_repo = MockGitRepository(Path("/mock/repo"))

        mock_git.Repo.clone_from.return_value = mock_repo
        mock_git.Repo.return_value = mock_repo

        yield mock_repo


@contextmanager
def patch_file_system(mock_fs: MockFileSystem):
    """Context manager to patch file system operations."""
    with patch("pathlib.Path.exists") as mock_exists, patch(
        "pathlib.Path.is_file"
    ) as mock_is_file, patch("pathlib.Path.is_dir") as mock_is_dir, patch(
        "pathlib.Path.read_text"
    ) as mock_read, patch("pathlib.Path.write_text") as mock_write:
        mock_exists.side_effect = lambda self: mock_fs.exists(str(self))
        mock_is_file.side_effect = lambda self: mock_fs.is_file(str(self))
        mock_is_dir.side_effect = lambda self: mock_fs.is_dir(str(self))
        mock_read.side_effect = lambda self, **kwargs: mock_fs.read_text(str(self))
        mock_write.side_effect = lambda self, content, **kwargs: mock_fs.write_text(
            str(self), content
        )

        yield mock_fs


@contextmanager
def patch_environment(mock_env: MockEnvironment):
    """Context manager to patch environment detection."""
    with patch("os.environ", mock_env.env_vars), patch("platform.system") as mock_platform, patch(
        "os.name", mock_env.platform
    ):
        mock_platform.return_value = mock_env.platform.title()
        yield mock_env


class MockPluginRepository:
    """Mock plugin repository for testing."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.plugins = []
        self.manifest = {}
        self.version = "1.0.0"
        self.is_valid = True
        self.discovery_delay = 0  # Simulate discovery time

    def add_plugin(self, plugin_data: Dict[str, Any]):
        """Add a plugin to the mock repository."""
        self.plugins.append(plugin_data)

    def set_manifest(self, manifest_data: Dict[str, Any]):
        """Set the repository manifest."""
        self.manifest = manifest_data

    def set_discovery_delay(self, delay: float):
        """Set artificial delay for discovery operations."""
        self.discovery_delay = delay

    def discover_plugins(self) -> List[Dict[str, Any]]:
        """Mock plugin discovery."""
        if self.discovery_delay > 0:
            import time

            time.sleep(self.discovery_delay)

        if not self.is_valid:
            raise ValueError("Invalid repository")

        return self.plugins.copy()

    def get_manifest(self) -> Dict[str, Any]:
        """Get repository manifest."""
        return self.manifest.copy()

    def simulate_update(self, plugin_name: str, new_version: str):
        """Simulate plugin update."""
        for plugin in self.plugins:
            if plugin["name"] == plugin_name:
                plugin["version"] = new_version
                plugin["description"] += " (Updated)"

    def simulate_corruption(self):
        """Simulate repository corruption."""
        self.is_valid = False

    def restore(self):
        """Restore repository from corruption."""
        self.is_valid = True


class MockPerformanceEnvironment:
    """Mock environment for performance testing."""

    def __init__(self):
        self.cpu_count = 4
        self.memory_total = 8 * 1024 * 1024 * 1024  # 8GB
        self.memory_available = 6 * 1024 * 1024 * 1024  # 6GB
        self.memory_used = 2 * 1024 * 1024 * 1024  # 2GB
        self.load_average = 0.5
        self.io_counters = {"read_bytes": 1000000, "write_bytes": 500000}

    def get_cpu_count(self) -> int:
        """Get CPU count."""
        return self.cpu_count

    def get_memory_info(self) -> Dict[str, int]:
        """Get memory information."""
        return {
            "total": self.memory_total,
            "available": self.memory_available,
            "used": self.memory_used,
            "percent": (self.memory_used / self.memory_total) * 100,
        }

    def get_load_average(self) -> float:
        """Get system load average."""
        return self.load_average

    def simulate_load(self, load_factor: float):
        """Simulate system load."""
        self.load_average = load_factor
        self.memory_used = int(self.memory_total * (0.2 + load_factor * 0.6))


@contextmanager
def mock_performance_environment():
    """Context manager for mocking performance environment."""
    mock_env = MockPerformanceEnvironment()

    with patch("psutil.cpu_count") as mock_cpu, patch(
        "psutil.virtual_memory"
    ) as mock_memory, patch("psutil.getloadavg") as mock_load:
        mock_cpu.return_value = mock_env.get_cpu_count()
        mock_memory.return_value = Mock(**mock_env.get_memory_info())
        mock_load.return_value = (mock_env.get_load_average(), 0, 0)

        yield mock_env
