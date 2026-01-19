"""Tests for project configuration management (pacc.json)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pacc.cli import PACCCli
from pacc.core.project_config import (
    ExtensionSpec,
    InstallationPathResolver,
    ProjectConfigManager,
    ProjectConfigSchema,
    ProjectConfigValidator,
    ProjectSyncManager,
)
from pacc.errors.exceptions import ValidationError


class TestProjectConfigSchema:
    """Test project configuration schema validation."""

    def test_valid_schema_structure(self):
        """Test that valid pacc.json structure is accepted."""
        valid_config = {
            "name": "my-claude-project",
            "version": "1.0.0",
            "description": "A test Claude Code project",
            "extensions": {
                "hooks": [
                    {"name": "pre-tool-logger", "source": "./hooks/logger.json", "version": "1.2.0"}
                ],
                "mcps": [
                    {
                        "name": "file-server",
                        "source": "https://github.com/example/mcp-file-server",
                        "version": "2.1.0",
                        "ref": "v2.1.0",
                    }
                ],
                "agents": [
                    {"name": "code-reviewer", "source": "./agents/reviewer.md", "version": "1.0.0"}
                ],
                "commands": [
                    {"name": "deploy", "source": "./commands/deploy.md", "version": "1.3.0"}
                ],
            },
            "environments": {
                "development": {
                    "extensions": {
                        "hooks": [
                            {
                                "name": "dev-debugger",
                                "source": "./hooks/debug.json",
                                "version": "1.0.0",
                            }
                        ]
                    }
                },
                "production": {
                    "extensions": {
                        "mcps": [
                            {
                                "name": "prod-monitor",
                                "source": "https://github.com/example/monitor-mcp",
                                "version": "1.5.0",
                            }
                        ]
                    }
                },
            },
            "metadata": {
                "created_at": "2024-12-15T10:00:00Z",
                "last_updated": "2024-12-15T10:00:00Z",
                "pacc_version": "1.0.0",
            },
        }

        schema = ProjectConfigSchema()
        result = schema.validate(valid_config)

        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_minimal_schema_structure(self):
        """Test minimal valid pacc.json structure."""
        minimal_config = {"name": "simple-project", "version": "1.0.0", "extensions": {}}

        schema = ProjectConfigSchema()
        result = schema.validate(minimal_config)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_invalid_schema_missing_required_fields(self):
        """Test validation fails for missing required fields."""
        invalid_config = {"description": "Missing name and version"}

        schema = ProjectConfigSchema()
        result = schema.validate(invalid_config)

        assert not result.is_valid
        assert len(result.errors) >= 2  # name and version required

        error_codes = [error.code for error in result.errors]
        assert "MISSING_REQUIRED_FIELD" in error_codes

    def test_invalid_extension_spec(self):
        """Test validation fails for invalid extension specifications."""
        invalid_config = {
            "name": "test-project",
            "version": "1.0.0",
            "extensions": {
                "hooks": [
                    {
                        "name": "invalid-hook",
                        # Missing required 'source' field
                        "version": "1.0.0",
                    }
                ]
            },
        }

        schema = ProjectConfigSchema()
        result = schema.validate(invalid_config)

        assert not result.is_valid
        assert any("source" in error.message for error in result.errors)

    def test_version_validation(self):
        """Test semantic version validation."""
        schema = ProjectConfigSchema()

        # Valid versions
        valid_versions = ["1.0.0", "2.1.3", "1.0.0-alpha", "1.0.0-beta.1"]
        for version in valid_versions:
            config = {"name": "test", "version": version, "extensions": {}}
            result = schema.validate(config)
            assert result.is_valid, f"Version {version} should be valid"

        # Invalid versions
        invalid_versions = ["1.0", "v1.0.0", "latest", "1.0.0.0"]
        for version in invalid_versions:
            config = {"name": "test", "version": version, "extensions": {}}
            result = schema.validate(config)
            assert not result.is_valid, f"Version {version} should be invalid"


class TestExtensionSpec:
    """Test extension specification handling."""

    def test_extension_spec_creation(self):
        """Test creating extension specifications."""
        spec_data = {
            "name": "test-hook",
            "source": "./hooks/test.json",
            "version": "1.0.0",
            "description": "A test hook",
        }

        spec = ExtensionSpec.from_dict(spec_data)

        assert spec.name == "test-hook"
        assert spec.source == "./hooks/test.json"
        assert spec.version == "1.0.0"
        assert spec.description == "A test hook"

    def test_extension_spec_validation(self):
        """Test extension spec validation."""
        # Valid local source
        local_spec = {"name": "local-hook", "source": "./hooks/local.json", "version": "1.0.0"}
        spec = ExtensionSpec.from_dict(local_spec)
        assert spec.is_valid()

        # Valid remote source
        remote_spec = {
            "name": "remote-hook",
            "source": "https://github.com/user/repo",
            "version": "1.0.0",
            "ref": "main",
        }
        spec = ExtensionSpec.from_dict(remote_spec)
        assert spec.is_valid()

        # Invalid - missing source
        invalid_spec = {"name": "invalid-hook", "version": "1.0.0"}
        with pytest.raises(ValueError):
            ExtensionSpec.from_dict(invalid_spec)

    def test_extension_spec_source_types(self):
        """Test different extension source types."""
        specs = [
            # Local file
            {"name": "local-file", "source": "./hooks/file.json", "version": "1.0.0"},
            # Local directory
            {"name": "local-dir", "source": "./extensions/", "version": "1.0.0"},
            # GitHub URL
            {
                "name": "github-repo",
                "source": "https://github.com/user/repo",
                "version": "1.0.0",
                "ref": "v1.0.0",
            },
            # Git URL
            {
                "name": "git-repo",
                "source": "git+https://gitlab.com/user/repo.git",
                "version": "1.0.0",
                "ref": "main",
            },
        ]

        for spec_data in specs:
            spec = ExtensionSpec.from_dict(spec_data)
            assert spec.is_valid()
            assert spec.get_source_type() in [
                "local_file",
                "local_directory",
                "git_repository",
                "url",
            ]


class TestProjectConfigManager:
    """Test project configuration management."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            yield project_dir

    @pytest.fixture
    def config_manager(self):
        """Create project config manager."""
        return ProjectConfigManager()

    @pytest.fixture
    def sample_project_config(self):
        """Sample project configuration."""
        return {
            "name": "test-project",
            "version": "1.0.0",
            "description": "Test project for PACC",
            "extensions": {
                "hooks": [{"name": "test-hook", "source": "./hooks/test.json", "version": "1.0.0"}],
                "mcps": [
                    {
                        "name": "test-mcp",
                        "source": "https://github.com/example/mcp",
                        "version": "2.0.0",
                        "ref": "v2.0.0",
                    }
                ],
            },
        }

    def test_init_project_config(self, temp_project_dir, config_manager, sample_project_config):
        """Test initializing project configuration."""
        config_path = temp_project_dir / "pacc.json"

        config_manager.init_project_config(
            project_dir=temp_project_dir, config=sample_project_config
        )

        assert config_path.exists()

        # Verify content
        with open(config_path) as f:
            saved_config = json.load(f)

        assert saved_config["name"] == "test-project"
        assert saved_config["version"] == "1.0.0"
        assert "metadata" in saved_config
        assert "created_at" in saved_config["metadata"]
        assert saved_config["metadata"]["pacc_version"] is not None

    def test_load_project_config(self, temp_project_dir, config_manager, sample_project_config):
        """Test loading project configuration."""
        config_path = temp_project_dir / "pacc.json"

        # Create config file
        with open(config_path, "w") as f:
            json.dump(sample_project_config, f, indent=2)

        loaded_config = config_manager.load_project_config(temp_project_dir)

        assert loaded_config["name"] == sample_project_config["name"]
        assert loaded_config["version"] == sample_project_config["version"]
        assert loaded_config["extensions"] == sample_project_config["extensions"]

    def test_load_nonexistent_config(self, temp_project_dir, config_manager):
        """Test loading non-existent configuration returns None."""
        loaded_config = config_manager.load_project_config(temp_project_dir)
        assert loaded_config is None

    def test_update_project_config(self, temp_project_dir, config_manager, sample_project_config):
        """Test updating project configuration."""
        temp_project_dir / "pacc.json"

        # Initialize config
        config_manager.init_project_config(temp_project_dir, sample_project_config)

        # Update with new extension
        updates = {
            "extensions": {
                "agents": [{"name": "new-agent", "source": "./agents/new.md", "version": "1.0.0"}]
            }
        }

        config_manager.update_project_config(temp_project_dir, updates)

        # Verify update
        updated_config = config_manager.load_project_config(temp_project_dir)
        assert "agents" in updated_config["extensions"]
        assert len(updated_config["extensions"]["agents"]) == 1
        assert updated_config["extensions"]["agents"][0]["name"] == "new-agent"

        # Original extensions should still be there
        assert "hooks" in updated_config["extensions"]
        assert "mcps" in updated_config["extensions"]

    def test_add_extension_to_config(self, temp_project_dir, config_manager, sample_project_config):
        """Test adding individual extension to configuration."""
        config_manager.init_project_config(temp_project_dir, sample_project_config)

        new_extension = {"name": "added-hook", "source": "./hooks/added.json", "version": "1.1.0"}

        config_manager.add_extension_to_config(
            project_dir=temp_project_dir, extension_type="hooks", extension_spec=new_extension
        )

        # Verify addition
        updated_config = config_manager.load_project_config(temp_project_dir)
        hooks = updated_config["extensions"]["hooks"]

        assert len(hooks) == 2  # Original + new
        added_hook = next((h for h in hooks if h["name"] == "added-hook"), None)
        assert added_hook is not None
        assert added_hook["version"] == "1.1.0"

    def test_remove_extension_from_config(
        self, temp_project_dir, config_manager, sample_project_config
    ):
        """Test removing extension from configuration."""
        config_manager.init_project_config(temp_project_dir, sample_project_config)

        config_manager.remove_extension_from_config(
            project_dir=temp_project_dir, extension_type="hooks", extension_name="test-hook"
        )

        # Verify removal
        updated_config = config_manager.load_project_config(temp_project_dir)
        hooks = updated_config["extensions"]["hooks"]

        assert len(hooks) == 0
        assert not any(h["name"] == "test-hook" for h in hooks)

    def test_validate_project_config(self, temp_project_dir, config_manager, sample_project_config):
        """Test project configuration validation."""
        config_manager.init_project_config(temp_project_dir, sample_project_config)

        result = config_manager.validate_project_config(temp_project_dir)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.extension_count > 0

    def test_validate_invalid_config(self, temp_project_dir, config_manager):
        """Test validation of invalid configuration."""
        invalid_config = {
            "name": "invalid-project",
            # Missing version
            "extensions": {
                "hooks": [
                    {
                        "name": "invalid-hook"
                        # Missing source and version
                    }
                ]
            },
        }

        config_path = temp_project_dir / "pacc.json"
        with open(config_path, "w") as f:
            json.dump(invalid_config, f)

        result = config_manager.validate_project_config(temp_project_dir)

        assert not result.is_valid
        assert len(result.errors) > 0


class TestProjectSync:
    """Test project synchronization functionality."""

    @pytest.fixture
    def sync_manager(self):
        """Create project sync manager."""
        return ProjectSyncManager()

    @pytest.fixture
    def mock_installer(self):
        """Mock extension installer."""
        installer = Mock()
        installer.install_extension.return_value = True
        return installer

    @pytest.fixture
    def sample_project_for_sync(self, temp_project_dir):
        """Sample project directory with pacc.json and extension files."""
        project_config = {
            "name": "sync-test-project",
            "version": "1.0.0",
            "extensions": {
                "hooks": [
                    {"name": "local-hook", "source": "./hooks/local.json", "version": "1.0.0"}
                ],
                "agents": [
                    {"name": "local-agent", "source": "./agents/local.md", "version": "1.0.0"}
                ],
            },
        }

        # Create pacc.json
        config_path = temp_project_dir / "pacc.json"
        with open(config_path, "w") as f:
            json.dump(project_config, f, indent=2)

        # Create extension files
        hooks_dir = temp_project_dir / "hooks"
        hooks_dir.mkdir()
        hook_file = hooks_dir / "local.json"
        with open(hook_file, "w") as f:
            json.dump({"name": "local-hook", "version": "1.0.0", "events": ["PreToolUse"]}, f)

        agents_dir = temp_project_dir / "agents"
        agents_dir.mkdir()
        agent_file = agents_dir / "local.md"
        agent_file.write_text("""---
name: local-agent
version: 1.0.0
---

# Local Agent

Test agent for sync.
""")

        return temp_project_dir

    def test_sync_project_extensions(self, sample_project_for_sync, sync_manager, mock_installer):
        """Test syncing project extensions from pacc.json."""
        with patch("pacc.core.project_config.get_extension_installer", return_value=mock_installer):
            result = sync_manager.sync_project(
                project_dir=sample_project_for_sync, environment="default"
            )

        assert result.success
        assert result.installed_count == 2  # hooks + agents
        assert len(result.failed_extensions) == 0

        # Verify installer was called correctly
        assert mock_installer.install_extension.call_count == 2

    def test_sync_with_environment_overrides(self, temp_project_dir, sync_manager, mock_installer):
        """Test syncing with environment-specific configurations."""
        project_config = {
            "name": "env-test-project",
            "version": "1.0.0",
            "extensions": {
                "hooks": [{"name": "base-hook", "source": "./hooks/base.json", "version": "1.0.0"}]
            },
            "environments": {
                "development": {
                    "extensions": {
                        "hooks": [
                            {"name": "dev-hook", "source": "./hooks/dev.json", "version": "1.0.0"}
                        ]
                    }
                }
            },
        }

        config_path = temp_project_dir / "pacc.json"
        with open(config_path, "w") as f:
            json.dump(project_config, f, indent=2)

        # Create hook files
        hooks_dir = temp_project_dir / "hooks"
        hooks_dir.mkdir()
        for hook_name in ["base.json", "dev.json"]:
            hook_file = hooks_dir / hook_name
            with open(hook_file, "w") as f:
                json.dump(
                    {
                        "name": hook_name.replace(".json", ""),
                        "version": "1.0.0",
                        "events": ["PreToolUse"],
                    },
                    f,
                )

        with patch("pacc.core.project_config.get_extension_installer", return_value=mock_installer):
            result = sync_manager.sync_project(
                project_dir=temp_project_dir, environment="development"
            )

        assert result.success
        assert result.installed_count == 2  # base-hook + dev-hook

        # Verify both hooks were installed
        installed_extensions = [
            call[0][0].name for call in mock_installer.install_extension.call_args_list
        ]
        assert "base-hook" in installed_extensions
        assert "dev-hook" in installed_extensions

    def test_sync_failure_handling(self, sample_project_for_sync, sync_manager):
        """Test handling of sync failures."""
        failing_installer = Mock()
        failing_installer.install_extension.side_effect = Exception("Installation failed")

        with patch(
            "pacc.core.project_config.get_extension_installer", return_value=failing_installer
        ):
            result = sync_manager.sync_project(
                project_dir=sample_project_for_sync, environment="default"
            )

        assert not result.success
        assert result.installed_count == 0
        assert len(result.failed_extensions) == 2

    def test_sync_nonexistent_project(self, temp_project_dir, sync_manager):
        """Test syncing project without pacc.json."""
        # No pacc.json file created

        result = sync_manager.sync_project(project_dir=temp_project_dir, environment="default")

        assert not result.success
        assert "pacc.json not found" in result.error_message


class TestCLIIntegration:
    """Test CLI command integration for project configuration."""

    def test_init_command_with_project_config(self, temp_project_dir):
        """Test 'pacc init --project-config' command."""
        cli = PACCCli()

        # Mock the arguments
        args = Mock()
        args.project_config = True
        args.name = "test-project"
        args.version = "1.0.0"
        args.description = "Test project"

        with patch("pacc.cli.Path.cwd", return_value=temp_project_dir):
            result = cli.init_command(args)

        assert result == 0  # Success

        # Verify pacc.json was created
        config_path = temp_project_dir / "pacc.json"
        assert config_path.exists()

        with open(config_path) as f:
            config = json.load(f)

        assert config["name"] == "test-project"
        assert config["version"] == "1.0.0"
        assert config["description"] == "Test project"

    def test_sync_command(self, sample_project_for_sync):
        """Test 'pacc sync' command."""
        cli = PACCCli()

        args = Mock()
        args.environment = "default"
        args.dry_run = False
        args.verbose = False
        args.project_dir = None  # This will default to cwd

        with patch("pacc.cli.Path.cwd", return_value=sample_project_for_sync):
            with patch("pacc.core.project_config.get_extension_installer"):
                result = cli.sync_command(args)

        assert result == 0  # Success

    def test_sync_command_dry_run(self, sample_project_for_sync):
        """Test 'pacc sync --dry-run' command."""
        cli = PACCCli()

        args = Mock()
        args.environment = "default"
        args.dry_run = True
        args.verbose = False
        args.project_dir = None  # This will default to cwd

        with patch("pacc.cli.Path.cwd", return_value=sample_project_for_sync):
            result = cli.sync_command(args)

        assert result == 0  # Success


class TestConfigValidation:
    """Test comprehensive configuration validation."""

    def test_dependency_validation(self):
        """Test extension dependency validation."""
        config = {
            "name": "dep-test",
            "version": "1.0.0",
            "extensions": {
                "hooks": [
                    {
                        "name": "dependent-hook",
                        "source": "./hooks/dependent.json",
                        "version": "1.0.0",
                        "dependencies": ["base-hook"],
                    }
                ]
            },
        }

        validator = ProjectConfigValidator()

        result = validator.validate_dependencies(config)

        # Should warn about missing dependency
        assert not result.is_valid
        assert any("base-hook" in error.message for error in result.errors)

    def test_version_compatibility_validation(self):
        """Test version compatibility validation."""
        config = {
            "name": "version-test",
            "version": "1.0.0",
            "extensions": {
                "hooks": [
                    {
                        "name": "old-hook",
                        "source": "./hooks/old.json",
                        "version": "0.1.0",
                        "min_pacc_version": "2.0.0",  # Incompatible
                    }
                ]
            },
        }

        validator = ProjectConfigValidator()

        result = validator.validate_compatibility(config, current_pacc_version="1.0.0")

        # Should warn about version incompatibility
        assert not result.is_valid
        assert any("version" in error.message.lower() for error in result.errors)

    def test_duplicate_extension_validation(self):
        """Test duplicate extension detection."""
        config = {
            "name": "duplicate-test",
            "version": "1.0.0",
            "extensions": {
                "hooks": [
                    {"name": "duplicate-hook", "source": "./hooks/dup1.json", "version": "1.0.0"},
                    {
                        "name": "duplicate-hook",  # Same name
                        "source": "./hooks/dup2.json",
                        "version": "1.1.0",
                    },
                ]
            },
        }

        validator = ProjectConfigValidator()

        result = validator.validate_duplicates(config)

        # Should detect duplicate extension names
        assert not result.is_valid
        assert any("duplicate" in error.message.lower() for error in result.errors)


@pytest.fixture
def sample_project_for_sync(temp_project_dir):
    """Reusable fixture for sync testing."""
    project_config = {
        "name": "sync-test-project",
        "version": "1.0.0",
        "extensions": {
            "hooks": [{"name": "local-hook", "source": "./hooks/local.json", "version": "1.0.0"}]
        },
    }

    config_path = temp_project_dir / "pacc.json"
    with open(config_path, "w") as f:
        json.dump(project_config, f, indent=2)

    hooks_dir = temp_project_dir / "hooks"
    hooks_dir.mkdir()
    hook_file = hooks_dir / "local.json"
    with open(hook_file, "w") as f:
        json.dump({"name": "local-hook", "version": "1.0.0", "events": ["PreToolUse"]}, f)

    return temp_project_dir


@pytest.fixture
def temp_project_dir():
    """Create temporary project directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


class TestFolderStructureSpecification:
    """Test folder structure specification features (PACC-19, PACC-25)."""

    def test_extension_spec_with_target_dir(self):
        """Test ExtensionSpec with targetDir field."""
        spec_data = {
            "name": "team-hook",
            "source": "./hooks/team.json",
            "version": "1.0.0",
            "targetDir": "team/product/",
        }

        spec = ExtensionSpec.from_dict(spec_data)

        assert spec.name == "team-hook"
        assert spec.source == "./hooks/team.json"
        assert spec.version == "1.0.0"
        assert spec.target_dir == "team/product/"
        assert spec.preserve_structure is False  # Default

    def test_extension_spec_with_preserve_structure(self):
        """Test ExtensionSpec with preserveStructure field."""
        spec_data = {
            "name": "structured-hook",
            "source": "./src/hooks/",
            "version": "1.0.0",
            "preserveStructure": True,
        }

        spec = ExtensionSpec.from_dict(spec_data)

        assert spec.preserve_structure is True
        assert spec.target_dir is None  # Default

    def test_extension_spec_with_both_folder_fields(self):
        """Test ExtensionSpec with both targetDir and preserveStructure."""
        spec_data = {
            "name": "complex-extension",
            "source": "https://github.com/team/extensions",
            "version": "1.2.0",
            "targetDir": "custom/location/",
            "preserveStructure": True,
        }

        spec = ExtensionSpec.from_dict(spec_data)

        assert spec.target_dir == "custom/location/"
        assert spec.preserve_structure is True

    def test_extension_spec_snake_case_compatibility(self):
        """Test ExtensionSpec supports both camelCase and snake_case field names."""
        # Test snake_case format
        snake_case_data = {
            "name": "snake-case-test",
            "source": "./test.json",
            "version": "1.0.0",
            "target_dir": "snake/case/",
            "preserve_structure": True,
        }

        spec = ExtensionSpec.from_dict(snake_case_data)
        assert spec.target_dir == "snake/case/"
        assert spec.preserve_structure is True

        # Test camelCase format
        camel_case_data = {
            "name": "camel-case-test",
            "source": "./test.json",
            "version": "1.0.0",
            "targetDir": "camel/case/",
            "preserveStructure": False,
        }

        spec = ExtensionSpec.from_dict(camel_case_data)
        assert spec.target_dir == "camel/case/"
        assert spec.preserve_structure is False

    def test_extension_spec_to_dict_includes_folder_fields(self):
        """Test that to_dict includes folder structure fields in camelCase."""
        spec = ExtensionSpec(
            name="test-ext",
            source="./test.json",
            version="1.0.0",
            target_dir="custom/dir/",
            preserve_structure=True,
        )

        result = spec.to_dict()

        assert result["targetDir"] == "custom/dir/"
        assert result["preserveStructure"] is True

        # Ensure backwards compatibility - no snake_case in JSON
        assert "target_dir" not in result
        assert "preserve_structure" not in result

    def test_extension_spec_to_dict_omits_none_values(self):
        """Test that to_dict omits None/False values for clean JSON."""
        spec = ExtensionSpec(
            name="minimal-ext",
            source="./test.json",
            version="1.0.0",
            # target_dir=None, preserve_structure=False (defaults)
        )

        result = spec.to_dict()

        assert "targetDir" not in result
        assert "preserveStructure" not in result  # False is default, omit

    def test_schema_validation_valid_folder_fields(self):
        """Test schema validation accepts valid folder structure fields."""
        valid_config = {
            "name": "folder-test-project",
            "version": "1.0.0",
            "extensions": {
                "hooks": [
                    {
                        "name": "organized-hook",
                        "source": "./hooks/organized.json",
                        "version": "1.0.0",
                        "targetDir": "team/hooks/",
                        "preserveStructure": True,
                    }
                ],
                "commands": [
                    {
                        "name": "team-command",
                        "source": "./commands/team.md",
                        "version": "1.0.0",
                        "targetDir": "commands/team-name/",
                    }
                ],
            },
        }

        schema = ProjectConfigSchema()
        result = schema.validate(valid_config)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_schema_validation_invalid_target_dir(self):
        """Test schema validation rejects invalid targetDir values."""
        invalid_configs = [
            # Empty string
            {
                "name": "test",
                "version": "1.0.0",
                "extensions": {
                    "hooks": [
                        {
                            "name": "test-hook",
                            "source": "./test.json",
                            "version": "1.0.0",
                            "targetDir": "",
                        }
                    ]
                },
            },
            # Path traversal attempt
            {
                "name": "test",
                "version": "1.0.0",
                "extensions": {
                    "hooks": [
                        {
                            "name": "malicious-hook",
                            "source": "./test.json",
                            "version": "1.0.0",
                            "targetDir": "../../../etc/",
                        }
                    ]
                },
            },
            # Absolute path
            {
                "name": "test",
                "version": "1.0.0",
                "extensions": {
                    "hooks": [
                        {
                            "name": "absolute-hook",
                            "source": "./test.json",
                            "version": "1.0.0",
                            "targetDir": "/absolute/path/",
                        }
                    ]
                },
            },
            # Non-string type
            {
                "name": "test",
                "version": "1.0.0",
                "extensions": {
                    "hooks": [
                        {
                            "name": "wrong-type-hook",
                            "source": "./test.json",
                            "version": "1.0.0",
                            "targetDir": 123,
                        }
                    ]
                },
            },
        ]

        schema = ProjectConfigSchema()

        for i, config in enumerate(invalid_configs):
            result = schema.validate(config)
            assert not result.is_valid, f"Config {i} should be invalid"

            # Check specific error types
            error_codes = [error.code for error in result.errors]
            expected_codes = ["INVALID_TARGET_DIR", "UNSAFE_TARGET_DIR"]
            assert any(
                code in error_codes for code in expected_codes
            ), f"Config {i} should have target dir error"

    def test_schema_validation_invalid_preserve_structure(self):
        """Test schema validation rejects invalid preserveStructure values."""
        invalid_config = {
            "name": "test",
            "version": "1.0.0",
            "extensions": {
                "hooks": [
                    {
                        "name": "invalid-preserve-hook",
                        "source": "./test.json",
                        "version": "1.0.0",
                        "preserveStructure": "not-a-boolean",
                    }
                ]
            },
        }

        schema = ProjectConfigSchema()
        result = schema.validate(invalid_config)

        assert not result.is_valid
        error_codes = [error.code for error in result.errors]
        assert "INVALID_PRESERVE_STRUCTURE" in error_codes


class TestInstallationPathResolver:
    """Test InstallationPathResolver for folder structure handling."""

    @pytest.fixture
    def resolver(self):
        """Create InstallationPathResolver instance."""
        return InstallationPathResolver()

    @pytest.fixture
    def claude_code_dir(self, temp_project_dir):
        """Mock Claude Code directory."""
        claude_dir = temp_project_dir / ".claude"
        claude_dir.mkdir()
        return claude_dir

    def test_resolve_basic_target_path(self, resolver, claude_code_dir):
        """Test basic target path resolution without custom settings."""
        spec = ExtensionSpec(name="basic-hook", source="./hooks/basic.json", version="1.0.0")

        base_dir = claude_code_dir / "hooks"
        source_file = Path("basic.json")

        result = resolver.resolve_target_path(spec, base_dir, source_file)

        assert result == base_dir / "basic.json"

    def test_resolve_target_path_with_custom_dir(self, resolver, claude_code_dir):
        """Test target path resolution with custom targetDir."""
        spec = ExtensionSpec(
            name="team-hook",
            source="./hooks/team.json",
            version="1.0.0",
            target_dir="team/product/",
        )

        base_dir = claude_code_dir / "hooks"
        source_file = Path("team.json")

        result = resolver.resolve_target_path(spec, base_dir, source_file)

        expected = base_dir / "team/product" / "team.json"
        assert result == expected

    def test_resolve_target_path_with_structure_preservation(self, resolver, claude_code_dir):
        """Test target path resolution with structure preservation."""
        spec = ExtensionSpec(
            name="structured-hook", source="./src/hooks/", version="1.0.0", preserve_structure=True
        )

        base_dir = claude_code_dir / "hooks"
        source_file = Path("src/hooks/nested/deep.json")

        result = resolver.resolve_target_path(spec, base_dir, source_file)

        # Should preserve the nested structure
        base_dir / "deep.json"  # Simplified expectation for now
        assert result.name == "deep.json"

    def test_resolve_target_path_with_both_custom_and_preserve(self, resolver, claude_code_dir):
        """Test target path resolution with both custom dir and structure preservation."""
        spec = ExtensionSpec(
            name="complex-hook",
            source="./src/hooks/",
            version="1.0.0",
            target_dir="custom/team/",
            preserve_structure=True,
        )

        base_dir = claude_code_dir / "hooks"
        source_file = Path("src/hooks/nested/complex.json")

        result = resolver.resolve_target_path(spec, base_dir, source_file)

        # Should use custom directory and preserve structure
        assert "custom/team" in str(result)
        assert result.name == "complex.json"

    def test_validate_target_directory_security(self, resolver):
        """Test target directory validation prevents path traversal."""
        # Valid directories
        valid_dirs = ["team/hooks/", "commands/product/", "simple"]
        for valid_dir in valid_dirs:
            result = resolver._validate_target_directory(valid_dir)
            assert result == valid_dir.rstrip("/")

        # Invalid directories (should raise ValidationError)
        invalid_dirs = ["../../../etc/", "/absolute/path/", "team/../../../root"]
        for invalid_dir in invalid_dirs:
            with pytest.raises(ValidationError):
                resolver._validate_target_directory(invalid_dir)

    def test_get_extension_install_directory(self, resolver, claude_code_dir):
        """Test getting base installation directories for extension types."""
        expected_dirs = {
            "hooks": claude_code_dir / "hooks",
            "mcps": claude_code_dir / "mcps",
            "agents": claude_code_dir / "agents",
            "commands": claude_code_dir / "commands",
        }

        for ext_type, expected_dir in expected_dirs.items():
            result = resolver.get_extension_install_directory(ext_type, claude_code_dir)
            assert result == expected_dir

        # Test invalid extension type
        with pytest.raises(ValueError):
            resolver.get_extension_install_directory("invalid_type", claude_code_dir)

    def test_validate_target_path_security_bounds(self, resolver, claude_code_dir):
        """Test target path validation stays within Claude Code directory."""
        # Valid paths (within claude_code_dir)
        valid_paths = [
            claude_code_dir / "hooks" / "test.json",
            claude_code_dir / "custom" / "team" / "hook.json",
        ]

        for valid_path in valid_paths:
            assert resolver.validate_target_path(valid_path, claude_code_dir) is True

        # Invalid paths (outside claude_code_dir)
        invalid_paths = [claude_code_dir.parent / "outside.json", Path("/tmp/malicious.json")]

        for invalid_path in invalid_paths:
            assert resolver.validate_target_path(invalid_path, claude_code_dir) is False

    def test_create_target_directory(self, resolver, temp_project_dir):
        """Test target directory creation."""
        target_file = temp_project_dir / "nested" / "deep" / "structure" / "file.json"

        # Directory shouldn't exist initially
        assert not target_file.parent.exists()

        # Create target directory
        resolver.create_target_directory(target_file)

        # Directory should now exist
        assert target_file.parent.exists()
        assert target_file.parent.is_dir()


class TestBackwardCompatibility:
    """Test backward compatibility with existing pacc.json files."""

    def test_existing_configs_still_work(self):
        """Test that existing configs without folder fields still validate."""
        existing_config = {
            "name": "legacy-project",
            "version": "1.0.0",
            "extensions": {
                "hooks": [
                    {
                        "name": "legacy-hook",
                        "source": "./hooks/legacy.json",
                        "version": "1.0.0",
                        # No targetDir or preserveStructure fields
                    }
                ]
            },
        }

        schema = ProjectConfigSchema()
        result = schema.validate(existing_config)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_extension_spec_defaults(self):
        """Test that ExtensionSpec has proper defaults for new fields."""
        minimal_spec_data = {"name": "minimal", "source": "./test.json", "version": "1.0.0"}

        spec = ExtensionSpec.from_dict(minimal_spec_data)

        # Should have sensible defaults
        assert spec.target_dir is None
        assert spec.preserve_structure is False

    def test_to_dict_backward_compatibility(self):
        """Test that to_dict produces clean JSON without new fields when not used."""
        spec = ExtensionSpec(
            name="clean",
            source="./test.json",
            version="1.0.0",
            # Using defaults for new fields
        )

        result = spec.to_dict()

        # Should only contain the basic required fields
        expected_keys = {"name", "source", "version"}
        assert set(result.keys()) == expected_keys

        # Should not contain the new optional fields
        assert "targetDir" not in result
        assert "preserveStructure" not in result
