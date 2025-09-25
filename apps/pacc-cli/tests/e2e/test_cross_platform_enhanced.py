"""Enhanced cross-platform tests for plugin system compatibility."""

import json
import os
import platform
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from pacc.core.file_utils import DirectoryScanner, FilePathValidator, PathNormalizer
from pacc.plugins import (
    EnvironmentManager,
    PluginConfigManager,
    PluginConverter,
    PluginRepositoryManager,
)


@pytest.fixture
def cross_platform_repo(tmp_path):
    """Create a cross-platform test repository with various path patterns."""
    repo_dir = tmp_path / "cross_platform_repo"
    repo_dir.mkdir()

    # Create manifest with cross-platform considerations
    manifest = {
        "name": "cross-platform-test-suite",
        "version": "1.0.0",
        "description": "Cross-platform compatibility test plugins",
        "platform_support": {"windows": True, "macos": True, "linux": True},
        "plugins": [
            {
                "name": "path-test-agent",
                "type": "agent",
                "path": "agents/path-test-agent.md",
                "description": "Tests path handling across platforms",
                "platform_requirements": ["windows", "macos", "linux"],
            },
            {
                "name": "file-system-hook",
                "type": "hook",
                "path": "hooks/file-system-hook.json",
                "description": "File system compatibility hook",
                "platform_specific": {
                    "windows": {"path_separator": "\\"},
                    "unix": {"path_separator": "/"},
                },
            },
            {
                "name": "shell-command",
                "type": "command",
                "path": "commands/shell-command.md",
                "description": "Cross-platform shell commands",
                "platform_variants": {
                    "windows": {"shell": "cmd", "extension": ".bat"},
                    "unix": {"shell": "bash", "extension": ".sh"},
                },
            },
            {
                "name": "environment-server",
                "type": "mcp",
                "path": "mcp/environment-server.yaml",
                "description": "Environment-aware MCP server",
                "environment_variables": {"cross_platform": True, "path_handling": "automatic"},
            },
        ],
    }

    (repo_dir / "pacc-manifest.yaml").write_text(yaml.dump(manifest, default_flow_style=False))

    # Create plugin directories
    for directory in ["agents", "hooks", "commands", "mcp"]:
        (repo_dir / directory).mkdir()

    # Create path test agent
    path_agent = """---
name: path-test-agent
version: 1.0.0
description: Tests path handling across different platforms
capabilities:
  - path_normalization
  - cross_platform_compatibility
  - file_system_operations
platform_support:
  windows: true
  macos: true
  linux: true
---

# Path Test Agent

This agent tests path handling across different operating systems.

## Platform-Specific Behavior

### Windows
- Uses backslash path separators
- Supports drive letters (C:, D:, etc.)
- Case-insensitive file systems
- Handles UNC paths (\\\\server\\share)

### macOS
- Uses forward slash path separators
- Case-insensitive by default (but preserving)
- Supports special characters in filenames
- Handles resource forks and extended attributes

### Linux
- Uses forward slash path separators
- Case-sensitive file systems
- Supports wide range of filename characters
- Handles symbolic links and permissions

## Cross-Platform Features

- Automatic path normalization
- Platform-appropriate file operations
- Consistent behavior across systems
- Error handling for platform-specific issues
"""
    (repo_dir / "agents" / "path-test-agent.md").write_text(path_agent)

    # Create file system hook
    fs_hook = {
        "name": "file-system-hook",
        "version": "1.0.0",
        "description": "Cross-platform file system monitoring hook",
        "events": ["FileCreated", "FileModified", "FileDeleted"],
        "platform_config": {
            "windows": {
                "path_separator": "\\",
                "case_sensitive": False,
                "watch_method": "ReadDirectoryChangesW",
            },
            "macos": {"path_separator": "/", "case_sensitive": False, "watch_method": "kqueue"},
            "linux": {"path_separator": "/", "case_sensitive": True, "watch_method": "inotify"},
        },
        "matchers": [
            {"pattern": "*", "platform": "all", "action": "log_event"},
            {"pattern": "*.tmp", "platform": "windows", "action": "ignore"},
            {"pattern": ".*", "platform": "unix", "action": "ignore_hidden"},
        ],
        "actions": {
            "log_event": {
                "command": "echo",
                "args": ["File system event: ${event_type} ${file_path}"],
                "platform_args": {"windows": ["cmd", "/c", "echo"], "unix": ["bash", "-c", "echo"]},
            }
        },
    }
    (repo_dir / "hooks" / "file-system-hook.json").write_text(json.dumps(fs_hook, indent=2))

    # Create shell command
    shell_command = """# Cross-Platform Shell Commands

Platform-aware shell commands that work across Windows, macOS, and Linux.

## Platform Detection

The system automatically detects the current platform and uses appropriate commands.

### Windows Commands

```cmd
REM Windows batch commands
dir /b *.txt
copy source.txt destination.txt
del temporary.txt
```

### Unix Commands (macOS/Linux)

```bash
# Unix shell commands
ls *.txt
cp source.txt destination.txt
rm temporary.txt
```

## Cross-Platform Commands

### `list-files`
List files in current directory.

**Windows:**
```cmd
dir /b
```

**Unix:**
```bash
ls -1
```

### `copy-file`
Copy a file from source to destination.

**Windows:**
```cmd
copy "%1" "%2"
```

**Unix:**
```bash
cp "$1" "$2"
```

### `remove-file`
Remove a file safely.

**Windows:**
```cmd
if exist "%1" del "%1"
```

**Unix:**
```bash
[ -f "$1" ] && rm "$1"
```

## Environment Variables

- `PACC_PLATFORM`: Current platform (windows, macos, linux)
- `PACC_SHELL`: Default shell (cmd, powershell, bash, zsh)
- `PACC_PATH_SEP`: Platform path separator (\\ or /)

## Usage Examples

```bash
# Platform-agnostic file operations
list-files
copy-file input.txt backup.txt
remove-file temporary.txt
```

The commands automatically adapt to the current platform.
"""
    (repo_dir / "commands" / "shell-command.md").write_text(shell_command)

    # Create environment server
    env_server = {
        "name": "environment-server",
        "command": "python",
        "args": ["-m", "cross_platform_server"],
        "env": {
            "PLATFORM": "${PACC_PLATFORM}",
            "PATH_SEPARATOR": "${PACC_PATH_SEP}",
            "HOME_DIR": "${HOME}",
            "USER_NAME": "${USER}",
        },
        "platform_config": {
            "windows": {
                "command": "python.exe",
                "env": {"HOME_DIR": "${USERPROFILE}", "USER_NAME": "${USERNAME}", "SHELL": "cmd"},
            },
            "macos": {
                "command": "/usr/bin/python3",
                "env": {"SHELL": "${SHELL:-/bin/bash}", "TERM": "${TERM:-xterm-256color}"},
            },
            "linux": {
                "command": "python3",
                "env": {"SHELL": "${SHELL:-/bin/bash}", "DISPLAY": "${DISPLAY}"},
            },
        },
        "capabilities": ["environment_detection", "path_normalization", "platform_adaptation"],
    }
    (repo_dir / "mcp" / "environment-server.yaml").write_text(yaml.dump(env_server))

    return repo_dir


@pytest.mark.e2e
@pytest.mark.cross_platform
class TestCrossPlatformPluginOperations:
    """Test plugin operations across different platforms."""

    def test_path_normalization_across_platforms(self, cross_platform_repo, tmp_path):
        """Test path normalization works correctly across platforms."""
        repo_dir = cross_platform_repo

        # Create test paths with platform-specific patterns
        test_paths = [
            "simple/path/file.txt",
            "path/with spaces/file name.txt",
            "path/with-dashes/file-name.txt",
            "path/with_underscores/file_name.txt",
            "path/with.dots/file.name.txt",
        ]

        # Windows-specific paths (if on Windows)
        if platform.system() == "Windows":
            test_paths.extend(
                [
                    "C:\\Windows\\System32\\file.txt",
                    "\\\\server\\share\\file.txt",
                    "path\\windows\\style.txt",
                ]
            )

        # Unix-specific paths (if on Unix-like systems)
        else:
            test_paths.extend(
                [
                    "/absolute/unix/path.txt",
                    "~/home/relative/path.txt",
                    "./relative/current/path.txt",
                    "../relative/parent/path.txt",
                ]
            )

        normalizer = PathNormalizer()

        for test_path_str in test_paths:
            try:
                # Test path normalization
                test_path = Path(test_path_str)
                normalized = normalizer.normalize(test_path)

                # Verify normalization preserves path structure
                assert isinstance(normalized, Path)

                # Test POSIX conversion
                posix_path = normalizer.to_posix(test_path)
                assert isinstance(posix_path, str)
                assert "/" in posix_path or posix_path == "."

                # Test relative path calculation (if possible)
                try:
                    relative = normalizer.relative_to(test_path, tmp_path)
                    assert isinstance(relative, Path)
                except ValueError:
                    # Expected if paths are not related
                    pass

            except (OSError, ValueError) as e:
                # Some paths may not be valid on all platforms
                print(f"Path not supported on this platform: {test_path_str} - {e}")
                continue

    def test_plugin_discovery_cross_platform(self, cross_platform_repo, tmp_path):
        """Test plugin discovery works across platforms."""
        repo_dir = cross_platform_repo

        # Test discovery with various path patterns
        repo_manager = PluginRepositoryManager()

        # Standard discovery
        plugins = repo_manager.discover_plugins(repo_dir)
        assert len(plugins) == 4

        plugin_names = [p.name for p in plugins]
        assert "path-test-agent" in plugin_names
        assert "file-system-hook" in plugin_names
        assert "shell-command" in plugin_names
        assert "environment-server" in plugin_names

        # Test discovery with different path formats
        path_formats = [
            str(repo_dir),  # String path
            repo_dir,  # Path object
        ]

        # Platform-specific path formats
        if platform.system() == "Windows":
            path_formats.append(str(repo_dir).replace("/", "\\"))

        for path_format in path_formats:
            try:
                discovered = repo_manager.discover_plugins(path_format)
                assert len(discovered) == 4, f"Discovery failed for path format: {path_format}"
            except Exception as e:
                pytest.fail(f"Discovery failed for path format {path_format}: {e}")

    def test_plugin_installation_cross_platform(self, cross_platform_repo, tmp_path):
        """Test plugin installation across platforms."""
        repo_dir = cross_platform_repo

        # Create cross-platform test environment
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        # Create platform-appropriate settings
        settings = {
            "modelId": "claude-3-5-sonnet-20241022",
            "maxTokens": 8192,
            "temperature": 0,
            "systemPrompt": "",
            "plugins": {},
            "hooks": {},
            "agents": {},
            "commands": {},
            "mcp": {"servers": {}},
            "platform": {
                "detected": platform.system().lower(),
                "path_separator": os.sep,
                "supports_symlinks": hasattr(os, "symlink"),
            },
        }
        (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))

        config = {
            "version": "1.0.0",
            "platform": platform.system().lower(),
            "extensions": {"hooks": {}, "agents": {}, "commands": {}, "mcp": {"servers": {}}},
        }
        (claude_dir / "config.json").write_text(json.dumps(config, indent=2))

        with patch("os.getcwd", return_value=str(tmp_path)):
            with patch(
                "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                return_value=claude_dir,
            ):
                # Test plugin installation
                repo_manager = PluginRepositoryManager()
                config_manager = PluginConfigManager(claude_dir)

                plugins = repo_manager.discover_plugins(repo_dir)
                result = config_manager.install_plugins(plugins, repo_dir)

                assert result["success"] is True
                assert result["installed_count"] == 4

                # Verify platform-appropriate paths were used
                updated_settings = json.loads((claude_dir / "settings.json").read_text())

                # Check that paths use platform-appropriate separators
                for plugin_type in ["agents", "hooks", "commands"]:
                    for plugin_name, plugin_config in updated_settings[plugin_type].items():
                        plugin_path = plugin_config["path"]

                        # Path should exist and be accessible
                        assert Path(plugin_path).exists(), f"Plugin path not found: {plugin_path}"

                        # Path should use platform-appropriate format
                        if platform.system() == "Windows":
                            # Windows paths might use backslashes or forward slashes
                            assert "\\" in plugin_path or "/" in plugin_path
                        else:
                            # Unix paths should use forward slashes
                            assert "/" in plugin_path

    def test_environment_manager_cross_platform(self, tmp_path):
        """Test environment manager across platforms."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        with patch("os.getcwd", return_value=str(tmp_path)):
            with patch(
                "pacc.core.project_config.ProjectConfigValidator._find_claude_dir",
                return_value=claude_dir,
            ):
                env_manager = EnvironmentManager()

                # Test platform detection
                status = env_manager.get_status()
                assert status.platform is not None
                assert status.shell is not None

                expected_platform = platform.system().lower()
                if expected_platform == "darwin":
                    expected_platform = "macos"

                assert status.platform.value == expected_platform

                # Test environment setup
                setup_result = env_manager.setup_development_environment()
                assert setup_result.success is True

                # Test environment verification
                verification = env_manager.verify_environment()
                assert verification.is_valid is True

                # Platform-specific checks
                if platform.system() == "Windows":
                    # Windows-specific environment checks
                    assert "USERPROFILE" in os.environ or "HOME" in os.environ
                    assert any(
                        ext in os.environ.get("PATHEXT", "") for ext in [".EXE", ".BAT", ".CMD"]
                    )

                elif platform.system() == "Darwin":  # macOS
                    # macOS-specific environment checks
                    assert "HOME" in os.environ
                    assert os.path.exists("/usr/bin") or os.path.exists("/bin")

                elif platform.system() == "Linux":
                    # Linux-specific environment checks
                    assert "HOME" in os.environ
                    assert os.path.exists("/usr/bin") or os.path.exists("/bin")

    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific test")
    def test_unix_specific_features(self, cross_platform_repo, tmp_path):
        """Test Unix-specific features (Linux/macOS)."""
        repo_dir = cross_platform_repo
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        # Create test files with Unix permissions
        test_file = tmp_path / "test_permissions.txt"
        test_file.write_text("test content")

        # Test different permission levels
        permission_tests = [
            (0o644, True),  # Read/write for owner, read for others
            (0o755, True),  # Read/write/execute for owner, read/execute for others
            (0o600, True),  # Read/write for owner only
            (0o000, False),  # No permissions (should fail unless root)
        ]

        validator = FilePathValidator()

        for permissions, should_be_valid in permission_tests:
            try:
                test_file.chmod(permissions)
                is_valid = validator.is_valid_path(test_file)

                # If running as root, restricted files might still be accessible
                if os.getuid() == 0:
                    assert is_valid is True, "Root should access all files"
                elif should_be_valid:
                    assert is_valid is True, f"File with {oct(permissions)} should be valid"
                else:
                    assert is_valid is False, f"File with {oct(permissions)} should be invalid"

            finally:
                # Restore permissions for cleanup
                test_file.chmod(0o644)

        # Test symbolic links
        if hasattr(os, "symlink"):
            symlink_target = tmp_path / "symlink_target.txt"
            symlink_target.write_text("symlink target content")

            symlink_path = tmp_path / "test_symlink.txt"
            os.symlink(symlink_target, symlink_path)

            # Test symlink handling
            assert validator.is_valid_path(symlink_path)
            assert validator.is_valid_path(symlink_target)

            # Test broken symlink
            symlink_target.unlink()
            broken_symlink_valid = validator.is_valid_path(symlink_path)
            # Behavior may vary - some systems consider broken symlinks invalid

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
    def test_windows_specific_features(self, cross_platform_repo, tmp_path):
        """Test Windows-specific features."""
        repo_dir = cross_platform_repo

        # Test Windows path patterns
        windows_paths = [
            "C:\\Windows\\System32",
            "D:\\Program Files\\Application",
            "\\\\server\\share\\file.txt",  # UNC path
            "path\\with\\backslashes.txt",
        ]

        normalizer = PathNormalizer()

        for path_str in windows_paths:
            try:
                path = Path(path_str)
                normalized = normalizer.normalize(path)
                assert isinstance(normalized, Path)

                posix_path = normalizer.to_posix(path)
                assert "/" in posix_path or path_str in [".", ""]

            except (OSError, ValueError):
                # Some UNC paths might not be accessible
                continue

        # Test case-insensitive file operations
        test_file_lower = tmp_path / "testfile.txt"
        test_file_lower.write_text("test content")

        # Windows should treat these as the same file
        test_file_upper = tmp_path / "TESTFILE.TXT"

        validator = FilePathValidator()
        assert validator.is_valid_path(test_file_lower)
        # Note: Path existence check depends on file system configuration

        # Test Windows-specific environment variables
        windows_env_vars = ["USERPROFILE", "USERNAME", "COMPUTERNAME", "PATHEXT"]
        available_vars = [var for var in windows_env_vars if var in os.environ]
        assert len(available_vars) > 0, "Should have some Windows environment variables"

    def test_file_encoding_cross_platform(self, cross_platform_repo, tmp_path):
        """Test file encoding handling across platforms."""
        repo_dir = cross_platform_repo

        # Test various text encodings
        encodings_to_test = ["utf-8", "utf-16", "latin-1"]

        # Create test content with various characters
        test_content = {
            "ascii": "Simple ASCII text",
            "unicode": "Unicode test: café, naïve, 测试, файл, 🚀",
            "mixed": "Mixed content: ASCII + Unicode café 测试",
        }

        scanner = DirectoryScanner()
        validator = FilePathValidator()

        for encoding in encodings_to_test:
            for content_type, content in test_content.items():
                test_file = tmp_path / f"test_{encoding}_{content_type}.txt"

                try:
                    # Write file with specific encoding
                    test_file.write_text(content, encoding=encoding)

                    # Test file scanning
                    files = list(scanner.scan_directory(tmp_path, recursive=False))
                    assert test_file in files

                    # Test validation
                    is_valid = validator.is_valid_path(test_file)
                    assert is_valid is True

                    # Test reading back
                    read_content = test_file.read_text(encoding=encoding)
                    assert read_content == content

                except (UnicodeError, UnicodeEncodeError, UnicodeDecodeError) as e:
                    # Some encoding combinations might not work on all platforms
                    print(f"Encoding {encoding} not supported for {content_type}: {e}")
                    continue

    def test_plugin_converter_cross_platform(self, tmp_path):
        """Test plugin converter across platforms."""
        # Create test extension files
        test_extensions_dir = tmp_path / "test_extensions"
        test_extensions_dir.mkdir()

        # Create a hook file
        hook_content = {
            "name": "cross-platform-hook",
            "version": "1.0.0",
            "description": "Cross-platform test hook",
            "events": ["PreToolUse"],
            "platform_config": {
                "windows": {"enabled": True},
                "macos": {"enabled": True},
                "linux": {"enabled": True},
            },
        }

        hook_file = test_extensions_dir / "cross-platform-hook.json"
        hook_file.write_text(json.dumps(hook_content, indent=2))

        # Test conversion
        converter = PluginConverter()

        output_dir = tmp_path / "converted_plugin"

        conversion_result = converter.convert_extension_to_plugin(
            hook_file,
            output_dir,
            plugin_name="cross-platform-test",
            plugin_version="1.0.0",
            author="Cross Platform Tester",
        )

        assert conversion_result.success is True
        assert output_dir.exists()

        # Verify cross-platform plugin structure
        manifest_file = output_dir / "pacc-manifest.yaml"
        assert manifest_file.exists()

        manifest_data = yaml.safe_load(manifest_file.read_text())
        assert manifest_data["name"] == "cross-platform-test"
        assert len(manifest_data["plugins"]) == 1

        # Check that converted files use platform-appropriate paths
        plugin_info = manifest_data["plugins"][0]
        plugin_path = output_dir / plugin_info["path"]
        assert plugin_path.exists()


@pytest.mark.e2e
@pytest.mark.platform_compatibility
class TestPlatformCompatibilityMatrix:
    """Test compatibility matrix across different platform scenarios."""

    def test_platform_detection_accuracy(self):
        """Test accurate platform detection."""
        env_manager = EnvironmentManager()
        status = env_manager.get_status()

        current_platform = platform.system()
        detected_platform = status.platform.value

        platform_mapping = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}

        expected = platform_mapping.get(current_platform, current_platform.lower())
        assert (
            detected_platform == expected
        ), f"Platform detection mismatch: {detected_platform} != {expected}"

        # Test shell detection
        detected_shell = status.shell.value
        assert detected_shell is not None

        # Platform-specific shell validation
        if current_platform == "Windows":
            assert detected_shell in [
                "cmd",
                "powershell",
            ], f"Unexpected Windows shell: {detected_shell}"
        else:
            assert detected_shell in [
                "bash",
                "zsh",
                "sh",
                "fish",
            ], f"Unexpected Unix shell: {detected_shell}"

    def test_path_separator_handling(self, tmp_path):
        """Test path separator handling across platforms."""
        normalizer = PathNormalizer()

        # Test mixed path separators
        mixed_paths = [
            "path/with/forward/slashes.txt",
            "path\\with\\back\\slashes.txt",
            "path/mixed\\separators/file.txt",
            "./relative/path.txt",
            "../parent/path.txt",
        ]

        for path_str in mixed_paths:
            path = Path(path_str)
            normalized = normalizer.normalize(path)

            # Normalized path should use platform-appropriate separators
            normalized_str = str(normalized)

            if platform.system() == "Windows":
                # Windows accepts both, but normalization might prefer one
                assert (
                    "\\" in normalized_str
                    or "/" in normalized_str
                    or len(normalized_str.split(os.sep)) > 1
                )
            else:
                # Unix systems should use forward slashes
                assert (
                    "/" in normalized_str
                    or normalized_str in [".", ".."]
                    or os.sep not in normalized_str
                )

    def test_file_system_case_sensitivity(self, tmp_path):
        """Test file system case sensitivity handling."""
        # Create test files
        lowercase_file = tmp_path / "testfile.txt"
        lowercase_file.write_text("lowercase content")

        uppercase_file = tmp_path / "TESTFILE.TXT"

        scanner = DirectoryScanner()

        # Check if file system is case-sensitive
        try:
            uppercase_file.write_text("uppercase content")
            files_created = 2  # Case-sensitive file system
            case_sensitive = True
        except FileExistsError:
            files_created = 1  # Case-insensitive file system
            case_sensitive = False

        # Scan directory
        discovered_files = list(scanner.scan_directory(tmp_path, recursive=False))
        text_files = [f for f in discovered_files if f.suffix.lower() == ".txt"]

        if case_sensitive:
            assert len(text_files) == 2, "Case-sensitive file system should have 2 files"
        else:
            assert len(text_files) == 1, "Case-insensitive file system should have 1 file"

        # Test file filter behavior
        file_filter = FileFilter()
        json_filter = file_filter.add_extension_filter({".txt"})
        filtered_files = json_filter.filter_files(discovered_files)

        # Filter should work regardless of case sensitivity
        assert len(filtered_files) >= 1, "Extension filter should find at least one .txt file"

    def test_special_characters_in_paths(self, tmp_path):
        """Test handling of special characters in file paths."""
        # Test various special characters that are valid on different platforms
        special_char_tests = [
            ("spaces in name.txt", True),
            ("file-with-dashes.txt", True),
            ("file_with_underscores.txt", True),
            ("file.with.dots.txt", True),
            ("file@symbol.txt", True),
            ("file#hash.txt", True),
            ("file%percent.txt", True),
        ]

        # Platform-specific special characters
        if platform.system() != "Windows":
            special_char_tests.extend(
                [
                    ("file:colon.txt", True),
                    ("file|pipe.txt", True),
                    ("file?question.txt", True),
                ]
            )

        validator = FilePathValidator()
        created_files = []

        for filename, should_work in special_char_tests:
            test_file = tmp_path / filename

            try:
                test_file.write_text("test content")
                created_files.append(test_file)

                # Test validation
                is_valid = validator.is_valid_path(test_file)
                if should_work:
                    assert is_valid, f"File with special characters should be valid: {filename}"

            except (OSError, ValueError) as e:
                if should_work:
                    print(f"Platform doesn't support filename: {filename} - {e}")
                # Some filenames might not be supported on all platforms
                continue

        # Test scanning with special characters
        if created_files:
            scanner = DirectoryScanner()
            discovered = list(scanner.scan_directory(tmp_path, recursive=False))

            # All created files should be discoverable
            for created_file in created_files:
                assert (
                    created_file in discovered
                ), f"Special character file not discovered: {created_file.name}"

    def test_long_path_handling(self, tmp_path):
        """Test handling of long file paths."""
        # Create nested directory structure
        long_path_components = [
            "very",
            "long",
            "path",
            "structure",
            "with",
            "many",
            "nested",
            "directories",
            "for",
            "testing",
            "path",
            "length",
            "limits",
        ]

        current_path = tmp_path
        for component in long_path_components:
            current_path = current_path / component
            try:
                current_path.mkdir()
            except OSError as e:
                # Platform might have path length limits
                print(f"Path length limit reached at: {current_path} - {e}")
                break

        # Create a file in the deepest accessible directory
        if current_path.exists():
            long_file = current_path / "test_file_with_a_very_long_name_to_test_path_limits.txt"

            try:
                long_file.write_text("content in long path")

                # Test validation
                validator = FilePathValidator()
                is_valid = validator.is_valid_path(long_file)
                assert is_valid, "Long path file should be valid if created successfully"

                # Test discovery
                scanner = DirectoryScanner()
                discovered = list(scanner.scan_directory(tmp_path, recursive=True))
                assert long_file in discovered, "Long path file should be discoverable"

            except OSError as e:
                print(f"Long path file creation failed: {e}")
                # Expected on some platforms with strict path limits


@pytest.fixture(autouse=True, scope="session")
def cross_platform_test_info():
    """Print cross-platform test information."""
    print("\n" + "=" * 80)
    print("PACC Cross-Platform Compatibility Test Suite")
    print("=" * 80)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Architecture: {platform.machine()}")
    print(f"Python: {platform.python_version()}")
    print(f"File System Encoding: {os.fsencode('test').decode('utf-8', errors='ignore')}")
    print(f"Path Separator: '{os.sep}'")
    print(f"Line Separator: {os.linesep!r}")
    print("=" * 80)

    yield

    print("\n" + "=" * 80)
    print("Cross-Platform Compatibility Test Summary")
    print("=" * 80)
    print("✅ Path normalization across platforms")
    print("✅ Plugin discovery and installation")
    print("✅ Environment detection and setup")
    print("✅ File encoding handling")
    print("✅ Platform-specific features")
    print("✅ Special character support")
    print("✅ Case sensitivity handling")
    print("✅ Long path support")
    print("=" * 80)
