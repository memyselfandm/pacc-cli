"""Enhanced test fixtures and mocks for reliable fragment testing.

This module provides comprehensive mocking infrastructure for fragment testing,
ensuring deterministic and repeatable test behavior.

Created for PACC-56: Fragment Integration Testing with Sample Fragments
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from unittest.mock import Mock, patch

import pytest

from pacc.fragments.installation_manager import FragmentSource, InstallationResult
from pacc.fragments.storage_manager import FragmentLocation
from pacc.validators.fragment_validator import ValidationResult


@dataclass
class MockFragmentEnvironment:
    """Complete mock environment for fragment testing."""

    project_root: Path
    temp_dir: Path
    claude_md_path: Path
    pacc_json_path: Path
    fragments_dir: Path
    installed_fragments: Dict[str, Any] = field(default_factory=dict)
    mock_patches: List[Any] = field(default_factory=list)

    def __post_init__(self):
        """Initialize the mock environment."""
        self.setup_directory_structure()
        self.setup_project_files()

    def setup_directory_structure(self):
        """Create consistent directory structure."""
        self.project_root.mkdir(exist_ok=True)
        self.fragments_dir = self.project_root / ".claude" / "pacc" / "fragments"
        self.fragments_dir.mkdir(parents=True, exist_ok=True)

        # Create storage directories
        for fragment_type in ["agents", "commands", "hooks", "mcp"]:
            (self.fragments_dir / fragment_type).mkdir(exist_ok=True)

    def setup_project_files(self):
        """Create consistent project files."""
        # CLAUDE.md
        claude_content = """# Test Project

This is a deterministic test project for fragment testing.

## Memory Fragments

Fragments will be managed here consistently.
"""
        self.claude_md_path.write_text(claude_content)

        # pacc.json
        pacc_config = {
            "name": "deterministic-test-project",
            "version": "1.0.0",
            "description": "Consistent test project for fragment testing",
            "fragments": {},
            "test_metadata": {"created_for": "PACC-56", "deterministic": True},
        }
        self.pacc_json_path.write_text(json.dumps(pacc_config, indent=2, sort_keys=True))

    def add_mock_fragment(self, name: str, fragment_type: str, version: str = "1.0.0", **kwargs):
        """Add a mock fragment to the environment."""
        fragment_data = {
            "name": name,
            "type": fragment_type,
            "version": version,
            "location_type": "project",
            "installed_at": "2024-01-01T00:00:00Z",  # Fixed for determinism
            "metadata": {"test_fragment": True, "deterministic": True, **kwargs},
        }
        self.installed_fragments[name] = fragment_data

        # Create physical file
        content = self._generate_mock_fragment_content(name, fragment_type, version, **kwargs)
        file_extension = "md" if fragment_type in ["agent", "command"] else "json"
        fragment_file = self.fragments_dir / fragment_type / f"{name}.{file_extension}"
        fragment_file.write_text(content)

        return fragment_data

    def _generate_mock_fragment_content(
        self, name: str, fragment_type: str, version: str, **kwargs
    ):
        """Generate consistent mock fragment content."""
        if fragment_type in ["agent", "command"]:
            return f"""---
name: {name}
version: {version}
description: Mock {fragment_type} for deterministic testing
test_metadata:
  mock: true
  deterministic: true
  fragment_type: {fragment_type}
---

# Mock {fragment_type.title()}: {name}

This is a mock {fragment_type} created for deterministic testing.

## Purpose

This mock fragment provides consistent behavior for testing fragment operations.

## Test Properties

- Deterministic: Always behaves the same way
- Reliable: No random elements or external dependencies
- Consistent: Same input produces same output
"""
        else:  # hook, mcp
            content = {
                "name": name,
                "version": version,
                "description": f"Mock {fragment_type} for deterministic testing",
                "test_metadata": {
                    "mock": True,
                    "deterministic": True,
                    "fragment_type": fragment_type,
                },
            }

            if fragment_type == "hook":
                content["events"] = ["PreToolUse", "PostToolUse"]
                content["action"] = {
                    "type": "log",
                    "message": f"Mock hook {name} executed - deterministic",
                    "timestamp": "fixed_for_testing",
                }
            elif fragment_type == "mcp":
                content["command"] = "python"
                content["args"] = ["-m", f"mock_{name.replace('-', '_')}"]

            return json.dumps(content, indent=2, sort_keys=True)

    def cleanup(self):
        """Clean up the mock environment."""
        for patch in self.mock_patches:
            patch.stop()


class MockFragmentValidator:
    """Mock validator that provides deterministic validation results."""

    def __init__(self, always_valid: bool = True, deterministic_errors: bool = True):
        self.always_valid = always_valid
        self.deterministic_errors = deterministic_errors
        self._validation_cache = {}  # Cache for consistent results

    def validate_single(self, fragment_path: Union[str, Path]) -> ValidationResult:
        """Provide consistent validation results."""
        path_str = str(fragment_path)

        # Return cached result for consistency
        if path_str in self._validation_cache:
            return self._validation_cache[path_str]

        # Create deterministic result
        if self.always_valid:
            result = ValidationResult(
                is_valid=True,
                fragment_type=self._detect_fragment_type(fragment_path),
                fragment_name=Path(fragment_path).stem,
                errors=[],
                warnings=[],
            )
        else:
            # Deterministic errors based on filename patterns
            errors = []
            if "invalid" in path_str:
                errors.append("Mock validation error: invalid pattern detected")
            if "malformed" in path_str:
                errors.append("Mock validation error: malformed structure")

            result = ValidationResult(
                is_valid=len(errors) == 0,
                fragment_type=self._detect_fragment_type(fragment_path),
                fragment_name=Path(fragment_path).stem,
                errors=errors,
                warnings=[],
            )

        # Cache for consistency
        self._validation_cache[path_str] = result
        return result

    def _detect_fragment_type(self, fragment_path: Union[str, Path]) -> str:
        """Detect fragment type from path."""
        path = Path(fragment_path)
        parent_name = path.parent.name

        if parent_name in ["agents", "commands", "hooks", "mcp"]:
            return parent_name.rstrip("s")  # Remove plural

        # Fallback detection
        if path.suffix == ".md":
            return "agent"  # Default for .md files
        elif path.suffix == ".json":
            return "hook"  # Default for .json files
        else:
            return "unknown"


class MockFragmentStorageManager:
    """Mock storage manager with deterministic behavior."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path("/mock/project")
        self.stored_fragments = {}
        self.storage_locations = {}

    def store_fragment(
        self,
        name: str,
        content: str,
        fragment_type: str,
        target_type: str = "project",
        metadata: Optional[Dict] = None,
    ) -> FragmentLocation:
        """Store fragment with deterministic behavior."""
        location = FragmentLocation(
            fragment_name=name,
            fragment_type=fragment_type,
            location_type=target_type,
            base_path=self.project_root / ".claude" / "pacc" / "fragments",
            fragment_path=self.project_root
            / ".claude"
            / "pacc"
            / "fragments"
            / fragment_type
            / f"{name}.{'md' if fragment_type in ['agent', 'command'] else 'json'}",
        )

        # Store fragment data
        self.stored_fragments[name] = {
            "name": name,
            "type": fragment_type,
            "content": content,
            "location_type": target_type,
            "metadata": metadata or {},
            "stored_at": "2024-01-01T00:00:00Z",  # Fixed for determinism
        }

        self.storage_locations[name] = location
        return location

    def get_fragment(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve fragment with consistent results."""
        return self.stored_fragments.get(name)

    def list_installed_fragments(self) -> List[Dict[str, Any]]:
        """List fragments with consistent ordering."""
        fragments = list(self.stored_fragments.values())
        # Sort by name for deterministic ordering
        return sorted(fragments, key=lambda f: f["name"])

    def remove_fragment(self, name: str) -> bool:
        """Remove fragment with consistent behavior."""
        if name in self.stored_fragments:
            del self.stored_fragments[name]
            if name in self.storage_locations:
                del self.storage_locations[name]
            return True
        return False

    def get_fragment_location(self, name: str, location_type: str = "project") -> FragmentLocation:
        """Get fragment location with deterministic paths."""
        if name in self.storage_locations:
            return self.storage_locations[name]

        # Create deterministic location
        return FragmentLocation(
            fragment_name=name,
            fragment_type="agent",  # Default
            location_type=location_type,
            base_path=self.project_root / ".claude" / "pacc" / "fragments",
            fragment_path=self.project_root
            / ".claude"
            / "pacc"
            / "fragments"
            / "agent"
            / f"{name}.md",
        )


class MockFragmentInstallationManager:
    """Mock installation manager with deterministic results."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path("/mock/project")
        self.mock_storage = MockFragmentStorageManager(project_root)
        self.installed_collections = {}

    def install_from_source(
        self,
        source_input: str,
        target_type: str = "project",
        interactive: bool = False,
        install_all: bool = False,
        force: bool = False,
        dry_run: bool = False,
    ) -> InstallationResult:
        """Provide deterministic installation results."""
        source_path = Path(source_input)

        # Generate consistent results based on source
        if not source_path.exists() and "nonexistent" not in source_input:
            # Mock source resolution for consistent testing
            pass

        # Determine what would be installed
        mock_fragments = self._generate_mock_installation_result(source_input, target_type)

        result = InstallationResult(
            success=True,
            installed_count=len(mock_fragments),
            source_type="collection" if source_path.is_dir() else "local",
            target_type=target_type,
            installed_fragments=mock_fragments,
            validation_warnings=[],
            error_message="",
            dry_run=dry_run,
            changes_made=[f"Installed {name}" for name in mock_fragments.keys()]
            if not dry_run
            else [],
        )

        # If not dry run, actually "install" to mock storage
        if not dry_run:
            for name, fragment_data in mock_fragments.items():
                self.mock_storage.store_fragment(
                    name=name,
                    content=f"Mock content for {name}",
                    fragment_type=fragment_data["type"],
                    target_type=target_type,
                    metadata=fragment_data.get("metadata", {}),
                )

        return result

    def _generate_mock_installation_result(
        self, source_input: str, target_type: str
    ) -> Dict[str, Dict[str, Any]]:
        """Generate consistent mock installation results."""
        source_path = Path(source_input)

        # Base fragments for deterministic collections
        if "deterministic" in source_input:
            return {
                "test-simple-agent": {"type": "agent", "version": "1.0.0", "complexity": "simple"},
                "test-medium-agent": {"type": "agent", "version": "1.0.0", "complexity": "medium"},
                "test-simple-command": {
                    "type": "command",
                    "version": "1.0.0",
                    "complexity": "simple",
                },
                "test-complex-command": {
                    "type": "command",
                    "version": "1.0.0",
                    "complexity": "complex",
                },
                "test-deterministic-hook": {
                    "type": "hook",
                    "version": "1.0.0",
                    "complexity": "simple",
                },
                "test-complex-hook": {"type": "hook", "version": "1.0.0", "complexity": "complex"},
            }
        elif "edge_case" in source_input:
            return {
                "minimal-test-agent": {
                    "type": "agent",
                    "version": "1.0.0",
                    "edge_case": "minimal_content",
                },
                "special-chars-agent": {
                    "type": "agent",
                    "version": "1.0.0",
                    "edge_case": "special_characters",
                },
                "no-params-command": {
                    "type": "command",
                    "version": "1.0.0",
                    "edge_case": "no_parameters",
                },
                "minimal-hook": {
                    "type": "hook",
                    "version": "1.0.0",
                    "edge_case": "minimal_configuration",
                },
            }
        elif "dependency" in source_input:
            return {
                "base-agent": {"type": "agent", "version": "1.0.0", "dependency_level": 0},
                "dependent-agent": {"type": "agent", "version": "1.0.0", "dependency_level": 1},
                "integrated-command": {
                    "type": "command",
                    "version": "1.0.0",
                    "dependency_level": 2,
                },
            }
        else:
            # Single fragment
            fragment_name = source_path.stem
            fragment_type = "agent" if source_path.suffix == ".md" else "hook"
            return {fragment_name: {"type": fragment_type, "version": "1.0.0"}}

    def resolve_source(self, source_input: str) -> FragmentSource:
        """Provide deterministic source resolution."""
        source_path = Path(source_input)

        if source_path.is_dir() or "collection" in source_input:
            return FragmentSource(
                source_type="collection",
                location=source_input,
                is_remote=False,
                is_collection=True,
                fragments=[],  # Would be populated in real implementation
                metadata={"test": "deterministic"},
            )
        else:
            return FragmentSource(
                source_type="local",
                location=source_input,
                is_remote=False,
                is_collection=False,
                fragments=[Path(source_input)],
                metadata={"test": "deterministic"},
            )


class ReliableTestFixtures:
    """Factory for creating reliable, deterministic test fixtures."""

    @staticmethod
    def create_mock_environment(temp_dir: Path) -> MockFragmentEnvironment:
        """Create a complete mock environment for testing."""
        project_root = temp_dir / "mock_project"
        project_root.mkdir()

        environment = MockFragmentEnvironment(
            project_root=project_root,
            temp_dir=temp_dir,
            claude_md_path=project_root / "CLAUDE.md",
            pacc_json_path=project_root / "pacc.json",
            fragments_dir=project_root / ".claude" / "pacc" / "fragments",
        )

        return environment

    @staticmethod
    def create_consistent_mocks() -> Dict[str, Mock]:
        """Create consistent mock objects for testing."""
        # Mock time functions for deterministic timestamps
        mock_time = Mock()
        mock_time.time.return_value = 1704067200.0  # Fixed timestamp: 2024-01-01 00:00:00 UTC
        mock_time.strftime.return_value = "2024-01-01T00:00:00Z"

        # Mock datetime for consistent date handling
        mock_datetime = Mock()
        mock_datetime.now.return_value = datetime(2024, 1, 1, 0, 0, 0)
        mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 0, 0, 0)

        # Mock UUID for consistent identifiers
        mock_uuid = Mock()
        mock_uuid.uuid4.return_value = Mock()
        mock_uuid.uuid4.return_value.hex = "deterministic_test_uuid_123456789"

        return {"time": mock_time, "datetime": mock_datetime, "uuid": mock_uuid}

    @staticmethod
    def patch_for_determinism():
        """Return context managers for deterministic patching."""
        return [
            patch("time.time", return_value=1704067200.0),
            patch("time.strftime", return_value="2024-01-01T00:00:00Z"),
            patch("datetime.datetime.now", return_value=datetime(2024, 1, 1, 0, 0, 0)),
            patch("datetime.datetime.utcnow", return_value=datetime(2024, 1, 1, 0, 0, 0)),
        ]


@pytest.fixture
def mock_fragment_environment(tmp_path):
    """Pytest fixture for mock fragment environment."""
    environment = ReliableTestFixtures.create_mock_environment(tmp_path)
    yield environment
    environment.cleanup()


@pytest.fixture
def deterministic_patches():
    """Pytest fixture for deterministic patching."""
    patches = ReliableTestFixtures.patch_for_determinism()

    # Start all patches
    started_patches = []
    for p in patches:
        started_patches.append(p.start())

    yield started_patches

    # Stop all patches
    for p in patches:
        p.stop()


@pytest.fixture
def mock_fragment_components():
    """Pytest fixture providing mock fragment components."""
    return {
        "validator": MockFragmentValidator(always_valid=True),
        "storage": MockFragmentStorageManager(),
        "installation": MockFragmentInstallationManager(),
        "consistent_mocks": ReliableTestFixtures.create_consistent_mocks(),
    }


def create_deterministic_test_data() -> Dict[str, Any]:
    """Create deterministic test data for consistent testing."""
    return {
        "test_fragments": {
            "simple_agent": {
                "name": "test-simple-agent",
                "type": "agent",
                "version": "1.0.0",
                "content": """---
name: test-simple-agent
version: 1.0.0
description: Simple test agent
---

# Simple Test Agent

Deterministic test agent for consistent testing.
""",
                "metadata": {"complexity": "simple", "deterministic": True},
            },
            "simple_command": {
                "name": "test-simple-command",
                "type": "command",
                "version": "1.0.0",
                "content": """---
name: test-simple-command
version: 1.0.0
description: Simple test command
---

# Simple Test Command

## Command: /test-simple

Deterministic test command for consistent testing.
""",
                "metadata": {"complexity": "simple", "deterministic": True},
            },
            "simple_hook": {
                "name": "test-simple-hook",
                "type": "hook",
                "version": "1.0.0",
                "content": json.dumps(
                    {
                        "name": "test-simple-hook",
                        "version": "1.0.0",
                        "description": "Simple test hook",
                        "events": ["PreToolUse"],
                        "action": {"type": "log", "message": "Test hook executed - deterministic"},
                    },
                    indent=2,
                    sort_keys=True,
                ),
                "metadata": {"complexity": "simple", "deterministic": True},
            },
        },
        "test_collections": {
            "basic": ["test-simple-agent", "test-simple-command", "test-simple-hook"],
            "agents_only": ["test-simple-agent"],
            "commands_only": ["test-simple-command"],
            "hooks_only": ["test-simple-hook"],
        },
        "expected_results": {
            "basic_collection_install": {
                "success": True,
                "fragment_count": 3,
                "types": {"agent": 1, "command": 1, "hook": 1},
            }
        },
    }
