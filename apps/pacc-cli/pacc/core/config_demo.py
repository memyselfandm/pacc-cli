#!/usr/bin/env python3
"""Demo script for the Claude configuration manager."""

import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

from .config_manager import ClaudeConfigManager, DeepMergeStrategy


def demo_config_merging():
    """Demonstrate configuration merging capabilities."""
    print("🔧 Claude Configuration Manager Demo")
    print("=" * 50)
    
    # Create a temporary directory for demo
    temp_dir = Path(tempfile.mkdtemp())
    config_path = temp_dir / "settings.json"
    
    try:
        # Initialize config manager
        config_manager = ClaudeConfigManager()
        
        print("\n1. Creating initial configuration...")
        initial_config = {
            "hooks": [
                {
                    "name": "pre_commit_hook",
                    "event": "before_commit",
                    "script": "scripts/pre_commit.py"
                }
            ],
            "mcps": [
                {
                    "name": "filesystem_mcp",
                    "command": "uv",
                    "args": ["run", "mcp-filesystem"]
                }
            ],
            "agents": [],
            "commands": [],
            "settings": {
                "theme": "dark",
                "auto_save": True,
                "debug_level": "info"
            }
        }
        
        config_manager.save_config(initial_config, config_path)
        print(f"✅ Initial config saved to {config_path}")
        print(f"   - {len(initial_config['hooks'])} hooks")
        print(f"   - {len(initial_config['mcps'])} MCP servers")
        
        print("\n2. Merging new extensions...")
        new_extensions = {
            "hooks": [
                {
                    "name": "post_commit_hook",
                    "event": "after_commit", 
                    "script": "scripts/post_commit.py"
                },
                {
                    "name": "pre_commit_hook",  # Duplicate (will be deduplicated)
                    "event": "before_commit",
                    "script": "scripts/pre_commit.py"
                }
            ],
            "agents": [
                {
                    "name": "code_reviewer",
                    "description": "Reviews code for best practices",
                    "model": "claude-3-opus"
                }
            ],
            "settings": {
                "auto_save": False,  # Conflict with existing
                "max_file_size": "10MB"  # New setting
            }
        }
        
        # Use automatic conflict resolution for demo
        merge_strategy = DeepMergeStrategy(
            array_strategy="dedupe",
            conflict_resolution="prompt"  # Would prompt in real usage
        )
        
        result = config_manager.merge_config(
            config_path, 
            new_extensions, 
            merge_strategy,
            resolve_conflicts=False  # Skip interactive resolution for demo
        )
        
        if result.success:
            print("✅ Merge completed successfully!")
            print(f"   - {len(result.changes_made)} changes made")
            print(f"   - {len(result.conflicts)} conflicts detected")
            
            if result.conflicts:
                print("\n   Conflicts found:")
                for conflict in result.conflicts:
                    print(f"     • {conflict.key_path}: {conflict.existing_value} → {conflict.new_value}")
            
            # Save the merged config (handling conflicts by keeping existing values)
            if result.merged_config:
                config_manager.save_config(result.merged_config, config_path)
                
                final_config = config_manager.load_config(config_path)
                print(f"\n   Final configuration:")
                print(f"     • {len(final_config['hooks'])} hooks")
                print(f"     • {len(final_config['mcps'])} MCP servers") 
                print(f"     • {len(final_config['agents'])} agents")
                print(f"     • {len(final_config['commands'])} commands")
        else:
            print("❌ Merge failed!")
            for warning in result.warnings:
                print(f"   Warning: {warning}")
        
        print("\n3. Testing atomic updates...")
        atomic_updates = {
            "commands": [
                {
                    "name": "build",
                    "description": "Build the project",
                    "command": "make build"
                }
            ]
        }
        
        success = config_manager.update_config_atomic(config_path, atomic_updates)
        if success:
            print("✅ Atomic update successful!")
            final_config = config_manager.load_config(config_path)
            print(f"   - Added {len(final_config['commands'])} command(s)")
        else:
            print("❌ Atomic update failed!")
        
        print("\n4. Testing extension-specific additions...")
        # Add a new MCP server
        mcp_config = {
            "name": "database_mcp",
            "command": "node",
            "args": ["dist/index.js"],
            "env": {"DATABASE_URL": "sqlite:///data.db"}
        }
        
        success = config_manager.add_extension_config(
            "mcps", mcp_config, user_level=False
        )
        
        # Mock the config path for this demo
        original_method = config_manager.get_config_path
        config_manager.get_config_path = lambda user_level: config_path
        
        try:
            success = config_manager.add_extension_config(
                "mcps", mcp_config, user_level=False
            )
            
            if success:
                print("✅ MCP server added successfully!")
                final_config = config_manager.load_config(config_path)
                print(f"   - Total MCP servers: {len(final_config['mcps'])}")
            else:
                print("❌ Failed to add MCP server!")
        finally:
            config_manager.get_config_path = original_method
        
        print("\n5. Final configuration preview:")
        final_config = config_manager.load_config(config_path)
        print(json.dumps(final_config, indent=2))
        
    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\n🧹 Cleaned up temporary directory: {temp_dir}")


def demo_deduplication():
    """Demonstrate extension list deduplication."""
    print("\n" + "=" * 50)
    print("🔄 Extension Deduplication Demo")
    print("=" * 50)
    
    from .config_manager import deduplicate_extension_list
    
    print("\n1. Testing hook deduplication...")
    hooks = [
        {"name": "pre_commit", "event": "before_commit", "version": "1.0"},
        {"name": "post_commit", "event": "after_commit", "version": "1.0"},
        {"name": "pre_commit", "event": "before_commit", "version": "2.0"},  # Duplicate
        {"name": "validation", "event": "before_validate", "version": "1.0"}
    ]
    
    deduplicated, duplicates = deduplicate_extension_list(hooks, "name")
    
    print(f"   Original: {len(hooks)} hooks")
    print(f"   Deduplicated: {len(deduplicated)} hooks")
    print(f"   Removed duplicates: {duplicates}")
    
    print("\n   Remaining hooks:")
    for hook in deduplicated:
        print(f"     • {hook['name']} (v{hook['version']})")
    
    print("\n2. Testing MCP server deduplication...")
    mcps = [
        {"name": "filesystem", "command": "mcp-filesystem"},
        {"name": "database", "command": "mcp-database"},
        {"name": "filesystem", "command": "mcp-filesystem-v2"},  # Duplicate name
    ]
    
    deduplicated, duplicates = deduplicate_extension_list(mcps, "name")
    
    print(f"   Original: {len(mcps)} MCP servers")
    print(f"   Deduplicated: {len(deduplicated)} MCP servers")
    print(f"   Removed duplicates: {duplicates}")


if __name__ == "__main__":
    demo_config_merging()
    demo_deduplication()
    print("\n🎉 Demo complete! The configuration manager is ready for production.")