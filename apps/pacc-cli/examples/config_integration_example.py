#!/usr/bin/env python3
"""Example showing integration of config manager with validation system."""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any

# Import our new config manager
from pacc.core.config_manager import ClaudeConfigManager, DeepMergeStrategy

# Import existing validation components
from pacc.validators.hooks import HooksValidator
from pacc.validators.mcp import MCPValidator
from pacc.validators.agents import AgentsValidator
from pacc.validators.commands import CommandsValidator


def validate_and_install_extension():
    """Example of validating an extension and updating config."""
    print("🔧 Extension Validation & Configuration Example")
    print("=" * 60)
    
    # Create temp environment
    temp_dir = Path(tempfile.mkdtemp())
    config_path = temp_dir / "settings.json"
    
    try:
        # Initialize config manager
        config_manager = ClaudeConfigManager()
        
        print("\n1. Creating test hook extension...")
        # Create a test hook file
        hook_file = temp_dir / "test_hook.json"
        hook_content = {
            "name": "code_formatter",
            "description": "Formats code before commits",
            "event": "before_commit",
            "script": "scripts/format_code.py",
            "matchers": ["*.py", "*.js"],
            "config": {
                "style": "black",
                "line_length": 88
            }
        }
        
        with open(hook_file, 'w') as f:
            json.dump(hook_content, f, indent=2)
        
        print(f"✅ Created hook file: {hook_file}")
        
        print("\n2. Validating hook extension...")
        # Validate the hook using existing validator
        hook_validator = HooksValidator()
        validation_result = hook_validator.validate_file(hook_file)
        
        if validation_result.is_valid:
            print(f"✅ Hook validation passed!")
            print(f"   - No errors found")
            if validation_result.warnings:
                print(f"   - {len(validation_result.warnings)} warnings")
        else:
            print(f"❌ Hook validation failed!")
            for error in validation_result.errors:
                print(f"   - Error: {error}")
            return  # Don't install invalid extension
        
        print("\n3. Adding validated extension to configuration...")
        # Since validation passed, add to config
        success = config_manager.add_extension_config(
            "hooks", 
            hook_content,
            user_level=False
        )
        
        # Mock the config path for this example
        original_method = config_manager.get_config_path
        config_manager.get_config_path = lambda user_level: config_path
        
        try:
            success = config_manager.add_extension_config(
                "hooks",
                hook_content,
                user_level=False
            )
            
            if success:
                print("✅ Extension added to configuration!")
            else:
                print("❌ Failed to add extension to configuration!")
                return
        finally:
            config_manager.get_config_path = original_method
        
        print("\n4. Testing bulk configuration update...")
        # Simulate installing multiple extensions at once
        bulk_config = {
            "mcps": [
                {
                    "name": "filesystem_server",
                    "command": "uv",
                    "args": ["run", "mcp-filesystem"],
                    "env": {"ALLOWED_DIRS": "/workspace"}
                }
            ],
            "agents": [
                {
                    "name": "code_reviewer",
                    "description": "AI code reviewer",
                    "model": "claude-3-opus",
                    "system_prompt": "You are a helpful code reviewer."
                }
            ],
            "commands": [
                {
                    "name": "test",
                    "description": "Run project tests",
                    "command": "pytest tests/"
                }
            ]
        }
        
        # Use merge strategy that deduplicates arrays
        merge_strategy = DeepMergeStrategy(
            array_strategy="dedupe",
            conflict_resolution="keep_existing"
        )
        
        # Mock config path again
        config_manager.get_config_path = lambda user_level: config_path
        
        try:
            # Perform bulk merge
            merge_result = config_manager.merge_config(
                config_path,
                bulk_config,
                merge_strategy,
                resolve_conflicts=False  # Auto-resolve for example
            )
            
            if merge_result.success:
                print("✅ Bulk configuration merge successful!")
                print(f"   - {len(merge_result.changes_made)} changes made")
                if merge_result.conflicts:
                    print(f"   - {len(merge_result.conflicts)} conflicts (auto-resolved)")
                
                # Save the merged config
                config_manager.save_config(merge_result.merged_config, config_path)
                
            else:
                print("❌ Bulk configuration merge failed!")
                for warning in merge_result.warnings:
                    print(f"   - {warning}")
        finally:
            config_manager.get_config_path = original_method
        
        print("\n5. Final configuration summary...")
        final_config = config_manager.load_config(config_path)
        
        print(f"📊 Configuration statistics:")
        print(f"   • Hooks: {len(final_config.get('hooks', []))}")
        print(f"   • MCP Servers: {len(final_config.get('mcps', []))}")
        print(f"   • Agents: {len(final_config.get('agents', []))}")
        print(f"   • Commands: {len(final_config.get('commands', []))}")
        
        print(f"\n📁 Final configuration:")
        print(json.dumps(final_config, indent=2))
        
        print("\n6. Demonstrating validation integration...")
        # Show how each validator can be used with the config
        validators = {
            'hooks': HooksValidator(),
            'mcps': MCPValidator(),
            'agents': AgentsValidator(),
            'commands': CommandsValidator()
        }
        
        print("\n   Validator compatibility check:")
        for ext_type, validator in validators.items():
            extensions = final_config.get(ext_type, [])
            print(f"   • {ext_type}: {len(extensions)} extensions")
            
            # Check if validator supports the extensions we have
            supported_extensions = validator.get_supported_extensions()
            print(f"     - Validator supports: {', '.join(supported_extensions)}")
        
    except Exception as e:
        print(f"❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\n🧹 Cleaned up temporary directory")


def demonstrate_conflict_resolution():
    """Show how conflict resolution works."""
    print("\n" + "=" * 60)
    print("⚔️ Conflict Resolution Demo")
    print("=" * 60)
    
    temp_dir = Path(tempfile.mkdtemp())
    config_path = temp_dir / "settings.json"
    
    try:
        config_manager = ClaudeConfigManager()
        
        # Create initial config with some settings
        initial_config = {
            "hooks": [{"name": "formatter", "script": "format.py"}],
            "settings": {
                "auto_save": True,
                "theme": "dark",
                "debug": False
            }
        }
        
        config_manager.save_config(initial_config, config_path)
        print("✅ Created initial configuration")
        
        # Try to merge conflicting config
        conflicting_config = {
            "hooks": [{"name": "formatter", "script": "new_format.py"}],  # Different script
            "settings": {
                "auto_save": False,  # Conflict!
                "theme": "light",    # Conflict!
                "max_files": 100     # New setting
            }
        }
        
        print("\n🔍 Detecting conflicts...")
        merge_result = config_manager.merge_config(
            config_path,
            conflicting_config,
            resolve_conflicts=False  # Don't prompt for demo
        )
        
        print(f"Found {len(merge_result.conflicts)} conflicts:")
        for conflict in merge_result.conflicts:
            print(f"   • {conflict.key_path}: {conflict.existing_value} vs {conflict.new_value}")
        
        print("\n📋 Conflict types detected:")
        conflict_types = set(c.conflict_type for c in merge_result.conflicts)
        for conflict_type in conflict_types:
            count = len([c for c in merge_result.conflicts if c.conflict_type == conflict_type])
            print(f"   • {conflict_type}: {count} conflicts")
        
    finally:
        import shutil
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