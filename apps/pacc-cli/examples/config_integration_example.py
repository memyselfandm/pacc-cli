#!/usr/bin/env python3
"""Example showing integration of config manager with validation system."""

import json
import shutil
import tempfile
import traceback
from pathlib import Path

# Import our new config manager
from pacc.core.config_manager import ClaudeConfigManager, DeepMergeStrategy
from pacc.validators.agents import AgentsValidator
from pacc.validators.commands import CommandsValidator

# Import existing validation components
from pacc.validators.hooks import HooksValidator
from pacc.validators.mcp import MCPValidator


def _create_test_hook(temp_dir: Path) -> tuple[Path, dict]:
    """Create a test hook file for the example."""
    hook_file = temp_dir / "test_hook.json"
    hook_content = {
        "name": "code_formatter",
        "description": "Formats code before commits",
        "event": "before_commit",
        "script": "scripts/format_code.py",
        "matchers": ["*.py", "*.js"],
        "config": {"style": "black", "line_length": 88},
    }

    with open(hook_file, "w") as f:
        json.dump(hook_content, f, indent=2)

    return hook_file, hook_content


def _validate_hook_extension(hook_file: Path) -> bool:
    """Validate the hook extension and return success status."""
    hook_validator = HooksValidator()
    validation_result = hook_validator.validate_file(hook_file)

    if validation_result.is_valid:
        print("✅ Hook validation passed!")
        print("   - No errors found")
        if validation_result.warnings:
            print(f"   - {len(validation_result.warnings)} warnings")
        return True
    else:
        print("❌ Hook validation failed!")
        for error in validation_result.errors:
            print(f"   - Error: {error}")
        return False


def _add_extension_to_config(config_manager, hook_content: dict, config_path: Path) -> bool:
    """Add validated extension to configuration."""
    original_method = config_manager.get_config_path
    config_manager.get_config_path = lambda _: config_path

    try:
        success = config_manager.add_extension_config("hooks", hook_content, user_level=False)
        if success:
            print("✅ Extension added to configuration!")
        else:
            print("❌ Failed to add extension to configuration!")
        return success
    finally:
        config_manager.get_config_path = original_method


def _create_bulk_config() -> dict:
    """Create bulk configuration for testing."""
    return {
        "mcps": [
            {
                "name": "filesystem_server",
                "command": "uv",
                "args": ["run", "mcp-filesystem"],
                "env": {"ALLOWED_DIRS": "/workspace"},
            }
        ],
        "agents": [
            {
                "name": "code_reviewer",
                "description": "AI code reviewer",
                "model": "claude-3-opus",
                "system_prompt": "You are a helpful code reviewer.",
            }
        ],
        "commands": [
            {"name": "test", "description": "Run project tests", "command": "pytest tests/"}
        ],
    }


def _perform_bulk_merge(config_manager, config_path: Path, bulk_config: dict) -> bool:
    """Perform bulk configuration merge."""
    merge_strategy = DeepMergeStrategy(array_strategy="dedupe", conflict_resolution="keep_existing")

    original_method = config_manager.get_config_path
    config_manager.get_config_path = lambda _: config_path

    try:
        merge_result = config_manager.merge_config(
            config_path,
            bulk_config,
            merge_strategy,
            resolve_conflicts=False,
        )

        if merge_result.success:
            print("✅ Bulk configuration merge successful!")
            print(f"   - {len(merge_result.changes_made)} changes made")
            if merge_result.conflicts:
                print(f"   - {len(merge_result.conflicts)} conflicts (auto-resolved)")

            config_manager.save_config(merge_result.merged_config, config_path)
            return True
        else:
            print("❌ Bulk configuration merge failed!")
            for warning in merge_result.warnings:
                print(f"   - {warning}")
            return False
    finally:
        config_manager.get_config_path = original_method


def _show_config_summary(config_manager, config_path: Path) -> dict:
    """Show final configuration summary."""
    final_config = config_manager.load_config(config_path)

    print("📊 Configuration statistics:")
    print(f"   • Hooks: {len(final_config.get('hooks', []))}")
    print(f"   • MCP Servers: {len(final_config.get('mcps', []))}")
    print(f"   • Agents: {len(final_config.get('agents', []))}")
    print(f"   • Commands: {len(final_config.get('commands', []))}")

    print("\n📁 Final configuration:")
    print(json.dumps(final_config, indent=2))

    return final_config


def _demonstrate_validators(final_config: dict) -> None:
    """Demonstrate validation integration."""
    validators = {
        "hooks": HooksValidator(),
        "mcps": MCPValidator(),
        "agents": AgentsValidator(),
        "commands": CommandsValidator(),
    }

    print("\n   Validator compatibility check:")
    for ext_type, validator in validators.items():
        extensions = final_config.get(ext_type, [])
        print(f"   • {ext_type}: {len(extensions)} extensions")

        supported_extensions = validator.get_supported_extensions()
        print(f"     - Validator supports: {', '.join(supported_extensions)}")


def validate_and_install_extension():
    """Example of validating an extension and updating config."""
    print("🔧 Extension Validation & Configuration Example")
    print("=" * 60)

    temp_dir = Path(tempfile.mkdtemp())
    config_path = temp_dir / "settings.json"

    try:
        config_manager = ClaudeConfigManager()

        print("\n1. Creating test hook extension...")
        hook_file, hook_content = _create_test_hook(temp_dir)
        print(f"✅ Created hook file: {hook_file}")

        print("\n2. Validating hook extension...")
        if not _validate_hook_extension(hook_file):
            return

        print("\n3. Adding validated extension to configuration...")
        if not _add_extension_to_config(config_manager, hook_content, config_path):
            return

        print("\n4. Testing bulk configuration update...")
        bulk_config = _create_bulk_config()
        if not _perform_bulk_merge(config_manager, config_path, bulk_config):
            return

        print("\n5. Final configuration summary...")
        final_config = _show_config_summary(config_manager, config_path)

        print("\n6. Demonstrating validation integration...")
        _demonstrate_validators(final_config)

    except Exception as e:
        print(f"❌ Example failed: {e}")
        traceback.print_exc()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("\n🧹 Cleaned up temporary directory")


def _create_initial_config(config_manager, config_path: Path) -> None:
    """Create initial configuration for conflict demo."""
    initial_config = {
        "hooks": [{"name": "formatter", "script": "format.py"}],
        "settings": {"auto_save": True, "theme": "dark", "debug": False},
    }
    config_manager.save_config(initial_config, config_path)
    print("✅ Created initial configuration")


def _create_conflicting_config() -> dict:
    """Create conflicting configuration for demo."""
    return {
        "hooks": [{"name": "formatter", "script": "new_format.py"}],
        "settings": {
            "auto_save": False,
            "theme": "light",
            "max_files": 100,
        },
    }


def _analyze_conflicts(merge_result) -> None:
    """Analyze and display conflict information."""
    print(f"Found {len(merge_result.conflicts)} conflicts:")
    for conflict in merge_result.conflicts:
        print(f"   • {conflict.key_path}: {conflict.existing_value} vs {conflict.new_value}")

    print("\n📋 Conflict types detected:")
    conflict_types = {c.conflict_type for c in merge_result.conflicts}
    for conflict_type in conflict_types:
        count = len([c for c in merge_result.conflicts if c.conflict_type == conflict_type])
        print(f"   • {conflict_type}: {count} conflicts")


def demonstrate_conflict_resolution():
    """Show how conflict resolution works."""
    print("\n" + "=" * 60)
    print("⚔️ Conflict Resolution Demo")
    print("=" * 60)

    temp_dir = Path(tempfile.mkdtemp())
    config_path = temp_dir / "settings.json"

    try:
        config_manager = ClaudeConfigManager()

        _create_initial_config(config_manager, config_path)

        conflicting_config = _create_conflicting_config()

        print("\n🔍 Detecting conflicts...")
        merge_result = config_manager.merge_config(
            config_path,
            conflicting_config,
            resolve_conflicts=False,
        )

        _analyze_conflicts(merge_result)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    validate_and_install_extension()
    demonstrate_conflict_resolution()
    print("\n🎉 Integration example complete!")
    print("\nKey takeaways:")
    print("• Validation happens before configuration updates")
    print("• Config manager handles complex merging with conflict detection")
    print("• Array deduplication prevents duplicate extensions")
    print("• Atomic operations ensure configuration integrity")
    print("• Interactive conflict resolution (when enabled) guides users")
