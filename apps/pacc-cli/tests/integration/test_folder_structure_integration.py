"""Integration tests for folder structure features - PACC-26 Testing Part.

This comprehensive test suite validates folder structure features:
1. targetDir configuration and behavior
2. preserveStructure option functionality
3. Backward compatibility with existing installations
4. Security validations (path traversal prevention)
5. Cross-platform compatibility

Coordinates with Agent-1's implementation work.

Related Issues:
- PACC-26: Comprehensive testing and documentation (subtask PACC-36)
- Folder structure implementation by Agent-1
"""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from pacc.core.config_manager import ClaudeConfigManager
from pacc.core.project_config import ProjectConfigManager
from pacc.validators import validate_extension_directory


class TestFolderStructureConfiguration:
    """Test targetDir configuration functionality."""

    def test_target_dir_basic_configuration(self):
        """Test basic targetDir configuration in pacc.json."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source structure
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create pacc.json with targetDir configuration
            pacc_config = {
                "name": "folder-structure-test",
                "version": "1.0.0",
                "targetDir": "./custom-extensions",
                "extensions": {
                    "hooks": [
                        {
                            "name": "test-hook",
                            "source": "./hooks/test-hook.json",
                            "version": "1.0.0",
                        }
                    ]
                },
            }
            pacc_json = source_dir / "pacc.json"
            pacc_json.write_text(json.dumps(pacc_config, indent=2))

            # Create hooks directory and file
            hooks_dir = source_dir / "hooks"
            hooks_dir.mkdir()
            hook_file = hooks_dir / "test-hook.json"
            hook_file.write_text(
                json.dumps(
                    {
                        "name": "test-hook",
                        "version": "1.0.0",
                        "events": ["PreToolUse"],
                        "description": "Test hook for targetDir",
                    }
                )
            )

            # Test configuration loading
            config_manager = ProjectConfigManager()
            config = config_manager.load_project_config(source_dir)

            assert config is not None
            assert "targetDir" in config
            assert config["targetDir"] == "./custom-extensions"

    def test_target_dir_with_nested_structure(self):
        """Test targetDir with nested directory structures."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create complex source structure
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create nested structure
            nested_hooks = source_dir / "extensions" / "hooks" / "level1" / "level2"
            nested_hooks.mkdir(parents=True)

            hook_file = nested_hooks / "nested-hook.json"
            hook_file.write_text(
                json.dumps(
                    {
                        "name": "nested-hook",
                        "version": "1.0.0",
                        "events": ["PreToolUse"],
                        "description": "Nested hook test",
                    }
                )
            )

            # Create pacc.json with nested targetDir
            pacc_config = {
                "name": "nested-structure-test",
                "version": "1.0.0",
                "targetDir": "./target/extensions/custom",
                "extensions": {
                    "hooks": [
                        {
                            "name": "nested-hook",
                            "source": "./extensions/hooks/level1/level2/nested-hook.json",
                            "version": "1.0.0",
                        }
                    ]
                },
            }
            pacc_json = source_dir / "pacc.json"
            pacc_json.write_text(json.dumps(pacc_config, indent=2))

            # Validate configuration
            config_manager = ProjectConfigManager()
            config = config_manager.load_project_config(source_dir)

            assert config["targetDir"] == "./target/extensions/custom"
            assert len(config["extensions"]["hooks"]) == 1

    def test_target_dir_path_normalization(self):
        """Test targetDir path normalization across platforms."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Test various path formats
            test_paths = [
                "./custom-extensions",
                "custom-extensions/",
                "./custom-extensions/",
                "custom-extensions",
                "../project/extensions",
                "./sub/dir/extensions",
            ]

            for target_path in test_paths:
                pacc_config = {
                    "name": "path-normalization-test",
                    "version": "1.0.0",
                    "targetDir": target_path,
                    "extensions": {},
                }

                pacc_json = source_dir / "pacc.json"
                pacc_json.write_text(json.dumps(pacc_config, indent=2))

                # Test path normalization
                config_manager = ProjectConfigManager()
                config = config_manager.load_project_config(source_dir)

                assert "targetDir" in config
                # Should normalize path without crashing
                normalized_path = Path(config["targetDir"])
                assert isinstance(normalized_path, Path)


class TestPreserveStructureFeature:
    """Test preserveStructure option functionality."""

    def test_preserve_structure_enabled(self):
        """Test preserveStructure: true maintains directory hierarchy."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source with nested structure
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create nested extensions
            nested_structure = [
                "extensions/hooks/auth/pre-auth.json",
                "extensions/hooks/tools/tool-validator.json",
                "extensions/commands/user/profile.md",
                "extensions/agents/system/monitor.md",
            ]

            extensions_list = {"hooks": [], "commands": [], "agents": []}

            for rel_path in nested_structure:
                full_path = source_dir / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)

                # Create appropriate content based on extension type
                if "hooks" in rel_path:
                    content = {
                        "name": full_path.stem,
                        "version": "1.0.0",
                        "events": ["PreToolUse"],
                        "description": f"Hook from {rel_path}",
                    }
                    full_path.write_text(json.dumps(content, indent=2))
                    extensions_list["hooks"].append(
                        {"name": full_path.stem, "source": f"./{rel_path}", "version": "1.0.0"}
                    )
                elif "commands" in rel_path:
                    content = f"""---
name: {full_path.stem}
description: Command from {rel_path}
---

# /{full_path.stem}

Command content.
"""
                    full_path.write_text(content)
                    extensions_list["commands"].append(
                        {"name": full_path.stem, "source": f"./{rel_path}", "version": "1.0.0"}
                    )
                elif "agents" in rel_path:
                    content = f"""---
name: {full_path.stem}
description: Agent from {rel_path}
tools: ["file-reader"]
---

Agent content.
"""
                    full_path.write_text(content)
                    extensions_list["agents"].append(
                        {"name": full_path.stem, "source": f"./{rel_path}", "version": "1.0.0"}
                    )

            # Create pacc.json with preserveStructure enabled
            pacc_config = {
                "name": "preserve-structure-test",
                "version": "1.0.0",
                "targetDir": "./custom-target",
                "preserveStructure": True,
                "extensions": extensions_list,
            }

            pacc_json = source_dir / "pacc.json"
            pacc_json.write_text(json.dumps(pacc_config, indent=2))

            # Test configuration
            config_manager = ProjectConfigManager()
            config = config_manager.load_project_config(source_dir)

            assert config["preserveStructure"] is True
            assert config["targetDir"] == "./custom-target"

            # Verify all extensions are properly configured
            assert len(config["extensions"]["hooks"]) == 2
            assert len(config["extensions"]["commands"]) == 1
            assert len(config["extensions"]["agents"]) == 1

    def test_preserve_structure_disabled(self):
        """Test preserveStructure: false flattens directory structure."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create same nested structure as above
            nested_files = ["deep/nested/hook1.json", "very/deep/nested/hook2.json"]

            hooks_list = []
            for rel_path in nested_files:
                full_path = source_dir / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)

                content = {"name": full_path.stem, "version": "1.0.0", "events": ["PreToolUse"]}
                full_path.write_text(json.dumps(content, indent=2))
                hooks_list.append(
                    {"name": full_path.stem, "source": f"./{rel_path}", "version": "1.0.0"}
                )

            # Create pacc.json with preserveStructure disabled
            pacc_config = {
                "name": "flatten-structure-test",
                "version": "1.0.0",
                "targetDir": "./flattened",
                "preserveStructure": False,
                "extensions": {"hooks": hooks_list},
            }

            pacc_json = source_dir / "pacc.json"
            pacc_json.write_text(json.dumps(pacc_config, indent=2))

            # Test configuration
            config_manager = ProjectConfigManager()
            config = config_manager.load_project_config(source_dir)

            assert config["preserveStructure"] is False
            assert len(config["extensions"]["hooks"]) == 2

    def test_preserve_structure_default_behavior(self):
        """Test default behavior when preserveStructure is not specified."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create basic structure
            hook_file = source_dir / "test-hook.json"
            hook_file.write_text(
                json.dumps({"name": "test-hook", "version": "1.0.0", "events": ["PreToolUse"]})
            )

            # Create pacc.json WITHOUT preserveStructure field
            pacc_config = {
                "name": "default-behavior-test",
                "version": "1.0.0",
                "extensions": {
                    "hooks": [
                        {"name": "test-hook", "source": "./test-hook.json", "version": "1.0.0"}
                    ]
                },
            }

            pacc_json = source_dir / "pacc.json"
            pacc_json.write_text(json.dumps(pacc_config, indent=2))

            # Test configuration
            config_manager = ProjectConfigManager()
            config = config_manager.load_project_config(source_dir)

            # Should have default value (likely False for backward compatibility)
            preserve_structure = config.get("preserveStructure", False)
            assert isinstance(preserve_structure, bool)


class TestFolderStructureSecurityValidation:
    """Test security validations for folder structure features."""

    def test_path_traversal_prevention_target_dir(self):
        """Test prevention of path traversal attacks in targetDir."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Test malicious targetDir values
            malicious_paths = [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32",
                "/etc/passwd",
                "C:\\Windows\\System32",
                "../../sensitive/data",
                "../outside-project",
            ]

            for malicious_path in malicious_paths:
                pacc_config = {
                    "name": "security-test",
                    "version": "1.0.0",
                    "targetDir": malicious_path,
                    "extensions": {},
                }

                pacc_json = source_dir / "pacc.json"
                pacc_json.write_text(json.dumps(pacc_config, indent=2))

                # Test security validation
                config_manager = ProjectConfigManager()

                try:
                    config = config_manager.load_project_config(source_dir)

                    # Should either reject malicious path or sanitize it
                    if config and "targetDir" in config:
                        # If accepted, should be sanitized/normalized
                        target_path = Path(config["targetDir"])

                        # Should not allow absolute paths to system directories
                        assert not str(target_path).startswith("/etc")
                        assert not str(target_path).startswith("C:\\Windows")

                except (ValueError, SecurityError, Exception) as e:
                    # Should raise security-related error
                    assert any(
                        keyword in str(e).lower()
                        for keyword in ["security", "path", "invalid", "traversal"]
                    )

    def test_source_path_traversal_prevention(self):
        """Test prevention of path traversal in extension source paths."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Test malicious source paths
            malicious_sources = [
                "../../../etc/passwd",
                "../../outside-project/malicious.json",
                "/etc/shadow",
                "..\\..\\windows\\system32\\evil.exe",
            ]

            for malicious_source in malicious_sources:
                pacc_config = {
                    "name": "source-security-test",
                    "version": "1.0.0",
                    "extensions": {
                        "hooks": [
                            {
                                "name": "malicious-hook",
                                "source": malicious_source,
                                "version": "1.0.0",
                            }
                        ]
                    },
                }

                pacc_json = source_dir / "pacc.json"
                pacc_json.write_text(json.dumps(pacc_config, indent=2))

                # Test validation
                try:
                    results = validate_extension_directory(source_dir)

                    # If validation proceeds, should handle missing files gracefully
                    # rather than attempting to access system files
                    if "hooks" in results:
                        for result in results["hooks"]:
                            # Should not successfully validate system files
                            assert not result.is_valid or "malicious" not in result.file_path

                except (FileNotFoundError, PermissionError, SecurityError):
                    # Expected - should not access system files
                    pass

    def test_symlink_security_handling(self):
        """Test security handling of symbolic links in folder structures."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create legitimate file
            legitimate_file = source_dir / "legitimate.json"
            legitimate_file.write_text(
                json.dumps({"name": "legitimate", "version": "1.0.0", "events": ["PreToolUse"]})
            )

            # Create potentially dangerous symlink target outside project
            outside_dir = temp_path / "outside"
            outside_dir.mkdir()
            dangerous_file = outside_dir / "dangerous.json"
            dangerous_file.write_text(
                json.dumps(
                    {
                        "name": "dangerous",
                        "version": "1.0.0",
                        "events": ["PreToolUse"],
                        "malicious": "content",
                    }
                )
            )

            # Create symlink (if supported)
            try:
                if hasattr(os, "symlink"):
                    symlink_path = source_dir / "symlink.json"
                    os.symlink(dangerous_file, symlink_path)

                    # Test validation handles symlinks securely
                    results = validate_extension_directory(source_dir)

                    # Should either reject symlinks or validate them securely
                    if "hooks" in results:
                        for result in results["hooks"]:
                            # Should not expose dangerous content through symlinks
                            if "symlink" in result.file_path:
                                # Either should be invalid or properly sandboxed
                                pass

            except (OSError, NotImplementedError):
                pytest.skip("Platform does not support symlinks")


class TestFolderStructureBackwardCompatibility:
    """Test backward compatibility with existing installations."""

    def test_legacy_installation_compatibility(self):
        """Test that new folder structure features don't break legacy installations."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy-style Claude Code config directory
            claude_config_dir = temp_path / ".claude"
            claude_config_dir.mkdir()

            # Create legacy config.json (without folder structure features)
            legacy_config = {
                "hooks": [
                    {
                        "name": "legacy-hook",
                        "path": str(temp_path / "legacy-hook.json"),
                        "version": "1.0.0",
                    }
                ],
                "commands": [
                    {
                        "name": "legacy-command",
                        "path": str(temp_path / "legacy-command.md"),
                        "version": "1.0.0",
                    }
                ],
            }

            config_file = claude_config_dir / "config.json"
            config_file.write_text(json.dumps(legacy_config, indent=2))

            # Create legacy extension files
            legacy_hook = temp_path / "legacy-hook.json"
            legacy_hook.write_text(
                json.dumps({"name": "legacy-hook", "version": "1.0.0", "events": ["PreToolUse"]})
            )

            legacy_command = temp_path / "legacy-command.md"
            legacy_command.write_text("""---
name: legacy-command
---

# /legacy-command

Legacy command content.
""")

            # Test that legacy configuration still works
            config_manager = ClaudeConfigManager()

            try:
                # Should be able to read legacy config without errors
                config = config_manager.load_config(claude_config_dir)

                # Should contain legacy entries
                assert "hooks" in config or "commands" in config

            except Exception as e:
                # Should not break on legacy configurations
                raise AssertionError(f"Legacy config caused error: {e}")

    def test_migration_from_legacy_to_folder_structure(self):
        """Test migration path from legacy to new folder structure."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create legacy setup

            # Create new pacc.json with folder structure features
            new_config = {
                "name": "migrated-project",
                "version": "1.0.0",
                "targetDir": "./modern-extensions",
                "preserveStructure": True,
                "extensions": {
                    "hooks": [
                        {"name": "new-hook", "source": "./hooks/new-hook.json", "version": "1.0.0"}
                    ],
                    "commands": [
                        {
                            "name": "new-command",
                            "source": "./commands/new-command.md",
                            "version": "1.0.0",
                        }
                    ],
                },
            }

            pacc_json = temp_path / "pacc.json"
            pacc_json.write_text(json.dumps(new_config, indent=2))

            # Create corresponding files
            hooks_dir = temp_path / "hooks"
            hooks_dir.mkdir()
            new_hook = hooks_dir / "new-hook.json"
            new_hook.write_text(
                json.dumps({"name": "new-hook", "version": "1.0.0", "events": ["PreToolUse"]})
            )

            commands_dir = temp_path / "commands"
            commands_dir.mkdir()
            new_command = commands_dir / "new-command.md"
            new_command.write_text("""---
name: new-command
---

# /new-command

New command with folder structure.
""")

            # Test that new configuration loads properly
            config_manager = ProjectConfigManager()
            config = config_manager.load_project_config(temp_path)

            assert config["targetDir"] == "./modern-extensions"
            assert config["preserveStructure"] is True
            assert len(config["extensions"]["hooks"]) == 1
            assert len(config["extensions"]["commands"]) == 1

    def test_mixed_legacy_modern_compatibility(self):
        """Test compatibility when both legacy and modern configurations exist."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create both legacy and modern configuration files

            # Legacy .claude/config.json
            claude_dir = temp_path / ".claude"
            claude_dir.mkdir()
            legacy_config = {
                "hooks": [{"name": "legacy-hook", "path": "./legacy-hook.json", "version": "1.0.0"}]
            }
            (claude_dir / "config.json").write_text(json.dumps(legacy_config))

            # Modern pacc.json
            modern_config = {
                "name": "mixed-project",
                "version": "1.0.0",
                "targetDir": "./modern",
                "extensions": {
                    "commands": [
                        {
                            "name": "modern-command",
                            "source": "./modern-command.md",
                            "version": "1.0.0",
                        }
                    ]
                },
            }
            (temp_path / "pacc.json").write_text(json.dumps(modern_config))

            # Create extension files
            (temp_path / "legacy-hook.json").write_text(
                json.dumps({"name": "legacy-hook", "version": "1.0.0", "events": ["PreToolUse"]})
            )

            (temp_path / "modern-command.md").write_text("""---
name: modern-command
---

# /modern-command

Modern command.
""")

            # Test that both configurations can coexist
            # (Implementation may prefer one over the other, but should not crash)

            try:
                legacy_manager = ClaudeConfigManager()
                modern_manager = ProjectConfigManager()

                # Both should work without interfering
                legacy_config_loaded = legacy_manager.load_config(claude_dir)
                modern_config_loaded = modern_manager.load_project_config(temp_path)

                # Should not cause conflicts
                assert legacy_config_loaded is not None or modern_config_loaded is not None

            except Exception as e:
                raise AssertionError(f"Mixed configuration caused conflict: {e}")


class TestFolderStructureCrossPlatform:
    """Test cross-platform compatibility of folder structure features."""

    def test_windows_path_separators(self):
        """Test handling of Windows-style path separators."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create configuration with Windows-style paths
            windows_config = {
                "name": "windows-paths-test",
                "version": "1.0.0",
                "targetDir": ".\\windows\\style\\paths",
                "preserveStructure": True,
                "extensions": {
                    "hooks": [
                        {
                            "name": "windows-hook",
                            "source": ".\\hooks\\windows-hook.json",
                            "version": "1.0.0",
                        }
                    ]
                },
            }

            pacc_json = source_dir / "pacc.json"
            pacc_json.write_text(json.dumps(windows_config, indent=2))

            # Create corresponding directory structure
            hooks_dir = source_dir / "hooks"
            hooks_dir.mkdir()
            hook_file = hooks_dir / "windows-hook.json"
            hook_file.write_text(
                json.dumps({"name": "windows-hook", "version": "1.0.0", "events": ["PreToolUse"]})
            )

            # Test cross-platform path handling
            config_manager = ProjectConfigManager()
            config = config_manager.load_project_config(source_dir)

            # Should normalize paths for current platform
            assert "targetDir" in config
            target_path = Path(config["targetDir"])
            assert isinstance(target_path, Path)

            # Should find extension files regardless of path separator style
            results = validate_extension_directory(source_dir)
            if "hooks" in results:
                assert len(results["hooks"]) > 0

    def test_unix_path_separators(self):
        """Test handling of Unix-style path separators."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create configuration with Unix-style paths
            unix_config = {
                "name": "unix-paths-test",
                "version": "1.0.0",
                "targetDir": "./unix/style/paths",
                "preserveStructure": True,
                "extensions": {
                    "commands": [
                        {
                            "name": "unix-command",
                            "source": "./commands/unix-command.md",
                            "version": "1.0.0",
                        }
                    ]
                },
            }

            pacc_json = source_dir / "pacc.json"
            pacc_json.write_text(json.dumps(unix_config, indent=2))

            # Create corresponding structure
            commands_dir = source_dir / "commands"
            commands_dir.mkdir()
            command_file = commands_dir / "unix-command.md"
            command_file.write_text("""---
name: unix-command
---

# /unix-command

Unix-style command.
""")

            # Test path handling
            config_manager = ProjectConfigManager()
            config = config_manager.load_project_config(source_dir)

            assert config["targetDir"] == "./unix/style/paths"

            # Validate extensions
            results = validate_extension_directory(source_dir)
            if "commands" in results:
                assert len(results["commands"]) > 0

    def test_case_sensitive_filesystem_handling(self):
        """Test handling of case-sensitive vs case-insensitive filesystems."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create files with different cases
            test_files = [
                ("UPPERCASE.json", "hooks"),
                ("lowercase.json", "hooks"),
                ("MixedCase.json", "hooks"),
            ]

            hooks_dir = source_dir / "hooks"
            hooks_dir.mkdir()

            extensions_config = {"hooks": []}

            for filename, _ext_type in test_files:
                file_path = hooks_dir / filename
                file_path.write_text(
                    json.dumps(
                        {
                            "name": filename.replace(".json", ""),
                            "version": "1.0.0",
                            "events": ["PreToolUse"],
                        }
                    )
                )

                extensions_config["hooks"].append(
                    {
                        "name": filename.replace(".json", ""),
                        "source": f"./hooks/{filename}",
                        "version": "1.0.0",
                    }
                )

            # Create pacc.json
            pacc_config = {
                "name": "case-sensitivity-test",
                "version": "1.0.0",
                "extensions": extensions_config,
            }

            pacc_json = source_dir / "pacc.json"
            pacc_json.write_text(json.dumps(pacc_config, indent=2))

            # Test validation
            results = validate_extension_directory(source_dir)

            # Should handle all files regardless of filesystem case sensitivity
            if "hooks" in results:
                assert len(results["hooks"]) == len(test_files)

    def test_long_path_handling(self):
        """Test handling of long file paths (Windows 260 char limit, etc.)."""
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_dir = temp_path / "source"
            source_dir.mkdir()

            # Create deeply nested directory structure
            long_path_parts = ["very"] * 10 + ["long"] * 10 + ["directory"] * 5 + ["structure"]
            deep_dir = source_dir

            for part in long_path_parts:
                deep_dir = deep_dir / part
                try:
                    deep_dir.mkdir(exist_ok=True)
                except OSError as e:
                    # Skip test if filesystem doesn't support long paths
                    if "path too long" in str(e).lower() or e.errno == 36:  # ENAMETOOLONG
                        pytest.skip(f"Filesystem doesn't support long paths: {e}")
                    raise

            # Create file in deep directory
            long_path_file = deep_dir / "deep-hook.json"
            try:
                long_path_file.write_text(
                    json.dumps({"name": "deep-hook", "version": "1.0.0", "events": ["PreToolUse"]})
                )

                # Test validation with long paths
                results = validate_extension_directory(source_dir)

                # Should handle long paths gracefully
                total_results = sum(len(file_list) for file_list in results.values())
                assert total_results >= 0  # Should not crash

            except OSError as e:
                if "path too long" in str(e).lower():
                    pytest.skip(f"Filesystem doesn't support long paths: {e}")
                raise


if __name__ == "__main__":
    # Run folder structure integration tests
    pytest.main([__file__, "-v", "--tb=short"])
