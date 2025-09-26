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

import re
import sys
from pathlib import Path


def _check_required_files(docs_dir: Path) -> bool:
    """Check that all required documentation files exist."""
    required_files = [
        "installation_guide.md",
        "usage_documentation.md",
        "migration_guide.md",
        "getting_started_guide.md",
        "troubleshooting_guide.md",
    ]

    print("📁 Checking required documentation files...")
    all_passed = True

    for file in required_files:
        file_path = docs_dir / file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"   ✅ {file} ({size:,} bytes)")
        else:
            print(f"   ❌ {file} - MISSING")
            all_passed = False

    print()
    return all_passed


def _validate_content_patterns(file_path: Path, checks: list, title: str) -> bool:
    """Validate that content contains required patterns."""
    print(f"{title}")

    if not file_path.exists():
        print(f"   ❌ File not found: {file_path.name}")
        print()
        return False

    content = file_path.read_text()
    all_passed = True

    for pattern, description in checks:
        # Case-insensitive search for certain patterns
        search_content = content.lower() if "install" in pattern.lower() else content
        search_pattern = pattern.lower() if "install" in pattern.lower() else pattern

        if search_pattern in search_content:
            print(f"   ✅ {description}")
        else:
            print(f"   ❌ {description} - MISSING")
            all_passed = False

    print()
    return all_passed


def _validate_installation_guide(docs_dir: Path) -> bool:
    """Validate installation guide content."""
    checks = [
        ("pip install pacc-cli", "pip installation"),
        ("uv tool install pacc-cli", "uv installation"),
        ("pipx install pacc-cli", "pipx installation"),
        ("virtual environment", "virtual environment coverage"),
        ("pacc --version", "verification commands"),
        ("Troubleshooting", "troubleshooting section"),
    ]

    return _validate_content_patterns(
        docs_dir / "installation_guide.md", checks, "🔧 Validating installation guide..."
    )


def _validate_usage_documentation(docs_dir: Path) -> bool:
    """Validate usage documentation content."""
    checks = [
        ("--user", "user flag documentation"),
        ("--project", "project flag documentation"),
        ("~/.claude/", "user-level directory"),
        (".claude/", "project-level directory"),
        ("Global vs Project Scope", "scope comparison"),
        ("Best Practices", "best practices section"),
    ]

    return _validate_content_patterns(
        docs_dir / "usage_documentation.md", checks, "📖 Validating usage documentation..."
    )


def _validate_migration_guide(docs_dir: Path) -> bool:
    """Validate migration guide content."""
    checks = [
        ("Development Installation → Global", "dev to global migration"),
        ("Rollback", "rollback procedures"),
        ("Compatibility", "compatibility considerations"),
        ("Migration Steps", "step-by-step instructions"),
    ]

    return _validate_content_patterns(
        docs_dir / "migration_guide.md", checks, "🔄 Validating migration guide..."
    )


def _validate_getting_started_guide(docs_dir: Path) -> bool:
    """Validate getting started guide content."""
    checks = [
        ("Quick Start", "quick start section"),
        ("5 minutes", "time estimate"),
        ("Tutorial", "tutorial sections"),
        ("Hooks", "hooks coverage"),
        ("MCP", "MCP coverage"),
        ("Agents", "agents coverage"),
        ("Commands", "commands coverage"),
        ("Common Workflows", "workflow examples"),
    ]

    return _validate_content_patterns(
        docs_dir / "getting_started_guide.md", checks, "🚀 Validating getting started guide..."
    )


def _check_package_name_consistency(docs_dir: Path) -> bool:
    """Check that all pip install commands use consistent package naming."""
    print("📦 Checking package name consistency...")
    inconsistent_files = []

    for doc_file in docs_dir.glob("*.md"):
        content = doc_file.read_text()
        pip_installs = re.findall(r"pip install ([^\s\[`]+)", content)

        for package in pip_installs:
            clean_package = package.strip("`").split("==")[0].split("[")[0]
            if clean_package.startswith("pacc") and clean_package != "pacc-cli":
                # Allow pacc-cli with version specifiers
                if not (package.startswith("pacc-cli") and ("==" in package or "[" in package)):
                    inconsistent_files.append((doc_file.name, package))

    if inconsistent_files:
        for file, package in inconsistent_files:
            print(f"   ❌ {file}: uses '{package}' instead of 'pacc-cli'")
        print()
        return False
    else:
        print("   ✅ All pip install commands use 'pacc-cli'")
        print()
        return True


def _check_internal_links(docs_dir: Path) -> bool:
    """Check for broken internal links in documentation."""
    print("🔗 Checking internal links...")
    broken_links = []

    for doc_file in docs_dir.glob("*.md"):
        content = doc_file.read_text()
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)

        for _link_text, link_url in links:
            if link_url.endswith(".md") and not link_url.startswith("http"):
                file_path = link_url.split("#")[0]

                if file_path.startswith("../"):
                    continue

                linked_file = docs_dir / file_path
                if not linked_file.exists():
                    broken_links.append((doc_file.name, link_url))

    if broken_links:
        for file, link in broken_links:
            print(f"   ❌ {file}: broken link to '{link}'")
        print()
        return False
    else:
        print("   ✅ All internal links are valid")
        print()
        return True


def _print_final_results(all_passed: bool) -> bool:
    """Print final validation results."""
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


def main():
    """Main validation function."""
    docs_dir = Path(__file__).parent.parent / "docs"
    if not docs_dir.exists():
        print(f"❌ Documentation directory not found: {docs_dir}")
        return False

    print("🔍 Validating F3.1 Documentation Requirements...")
    print()

    # Run all validation checks
    results = [
        _check_required_files(docs_dir),
        _validate_installation_guide(docs_dir),
        _validate_usage_documentation(docs_dir),
        _validate_migration_guide(docs_dir),
        _validate_getting_started_guide(docs_dir),
        _check_package_name_consistency(docs_dir),
        _check_internal_links(docs_dir),
    ]

    all_passed = all(results)
    return _print_final_results(all_passed)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
