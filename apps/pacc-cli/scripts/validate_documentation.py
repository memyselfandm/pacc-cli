#!/usr/bin/env python3
"""
Documentation validation script for F3.1.

This script validates that all documentation requirements have been met:
- Installation documentation covers pip, uv, pipx
- Usage documentation covers global vs project usage
- Migration guides are comprehensive
- Getting started guides include tutorials
- All documentation is consistent and complete
"""

import os
import re
import sys
from pathlib import Path

def main():
    """Main validation function."""
    
    docs_dir = Path(__file__).parent.parent / "docs"
    if not docs_dir.exists():
        print(f"❌ Documentation directory not found: {docs_dir}")
        return False
    
    print("🔍 Validating F3.1 Documentation Requirements...")
    print()
    
    all_passed = True
    
    # 1. Check required files exist
    required_files = [
        "installation_guide.md",
        "usage_documentation.md", 
        "migration_guide.md",
        "getting_started_guide.md",
        "troubleshooting_guide.md"
    ]
    
    print("📁 Checking required documentation files...")
    for file in required_files:
        file_path = docs_dir / file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"   ✅ {file} ({size:,} bytes)")
        else:
            print(f"   ❌ {file} - MISSING")
            all_passed = False
    print()
    
    # 2. Validate installation guide
    print("🔧 Validating installation guide...")
    installation_guide = docs_dir / "installation_guide.md"
    if installation_guide.exists():
        content = installation_guide.read_text()
        
        checks = [
            ("pip install pacc-cli", "pip installation"),
            ("uv tool install pacc-cli", "uv installation"), 
            ("pipx install pacc-cli", "pipx installation"),
            ("virtual environment", "virtual environment coverage"),
            ("pacc --version", "verification commands"),
            ("Troubleshooting", "troubleshooting section")
        ]
        
        for pattern, description in checks:
            if pattern.lower() in content.lower():
                print(f"   ✅ {description}")
            else:
                print(f"   ❌ {description} - MISSING")
                all_passed = False
    print()
    
    # 3. Validate usage documentation
    print("📖 Validating usage documentation...")
    usage_doc = docs_dir / "usage_documentation.md"
    if usage_doc.exists():
        content = usage_doc.read_text()
        
        checks = [
            ("--user", "user flag documentation"),
            ("--project", "project flag documentation"),
            ("~/.claude/", "user-level directory"),
            (".claude/", "project-level directory"),
            ("Global vs Project Scope", "scope comparison"),
            ("Best Practices", "best practices section")
        ]
        
        for pattern, description in checks:
            if pattern in content:
                print(f"   ✅ {description}")
            else:
                print(f"   ❌ {description} - MISSING")
                all_passed = False
    print()
    
    # 4. Validate migration guide
    print("🔄 Validating migration guide...")
    migration_guide = docs_dir / "migration_guide.md"
    if migration_guide.exists():
        content = migration_guide.read_text()
        
        checks = [
            ("Development Installation → Global", "dev to global migration"),
            ("Rollback", "rollback procedures"),
            ("Compatibility", "compatibility considerations"),
            ("Migration Steps", "step-by-step instructions")
        ]
        
        for pattern, description in checks:
            if pattern in content:
                print(f"   ✅ {description}")
            else:
                print(f"   ❌ {description} - MISSING")
                all_passed = False
    print()
    
    # 5. Validate getting started guide
    print("🚀 Validating getting started guide...")
    getting_started = docs_dir / "getting_started_guide.md"
    if getting_started.exists():
        content = getting_started.read_text()
        
        checks = [
            ("Quick Start", "quick start section"),
            ("5 minutes", "time estimate"),
            ("Tutorial", "tutorial sections"),
            ("Hooks", "hooks coverage"),
            ("MCP", "MCP coverage"),
            ("Agents", "agents coverage"),
            ("Commands", "commands coverage"),
            ("Common Workflows", "workflow examples")
        ]
        
        for pattern, description in checks:
            if pattern in content:
                print(f"   ✅ {description}")
            else:
                print(f"   ❌ {description} - MISSING")
                all_passed = False
    print()
    
    # 6. Check package name consistency
    print("📦 Checking package name consistency...")
    inconsistent_files = []
    
    for doc_file in docs_dir.glob("*.md"):
        content = doc_file.read_text()
        
        # Find pip install commands that don't use pacc-cli
        pip_installs = re.findall(r'pip install ([^\s\[`]+)', content)
        for package in pip_installs:
            # Clean up the package name (remove backticks, version specs)
            clean_package = package.strip('`').split('==')[0].split('[')[0]
            if clean_package.startswith('pacc') and clean_package != 'pacc-cli':
                # Allow pacc-cli with version specifiers
                if not (package.startswith('pacc-cli') and ('==' in package or '[' in package)):
                    inconsistent_files.append((doc_file.name, package))
    
    if inconsistent_files:
        for file, package in inconsistent_files:
            print(f"   ❌ {file}: uses '{package}' instead of 'pacc-cli'")
        all_passed = False
    else:
        print("   ✅ All pip install commands use 'pacc-cli'")
    print()
    
    # 7. Check for broken internal links
    print("🔗 Checking internal links...")
    broken_links = []
    
    for doc_file in docs_dir.glob("*.md"):
        content = doc_file.read_text()
        
        # Find all markdown links
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
        
        for link_text, link_url in links:
            # Check internal links
            if link_url.endswith('.md') and not link_url.startswith('http'):
                # Remove anchors
                file_path = link_url.split('#')[0]
                
                # Skip relative paths to parent directory
                if file_path.startswith('../'):
                    continue
                    
                # Check if linked file exists
                linked_file = docs_dir / file_path
                if not linked_file.exists():
                    broken_links.append((doc_file.name, link_url))
    
    if broken_links:
        for file, link in broken_links:
            print(f"   ❌ {file}: broken link to '{link}'")
        all_passed = False
    else:
        print("   ✅ All internal links are valid")
    print()
    
    # Final result
    if all_passed:
        print("🎉 All F3.1 documentation requirements are met!")
        print()
        print("Summary:")
        print("✅ Installation documentation complete (pip, uv, pipx)")
        print("✅ Usage documentation covers global vs project usage")
        print("✅ Migration guides are comprehensive")
        print("✅ Getting started guides include tutorials")
        print("✅ Package naming is consistent")
        print("✅ Internal links are valid")
        return True
    else:
        print("❌ Some documentation requirements are not met")
        print("Please review the issues above and update the documentation")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)