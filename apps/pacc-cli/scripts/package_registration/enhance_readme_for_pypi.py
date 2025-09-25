#!/usr/bin/env python3
"""
Enhance README.md for PyPI presentation.

This script adds PyPI badges, improves formatting, and ensures the README
is optimized for display on the PyPI package page.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple


class ReadmeEnhancer:
    """Enhance README for PyPI presentation."""

    def __init__(self, package_name: str = "pacc"):
        """Initialize with package name."""
        self.package_name = package_name
        self.badges_added = False
        self.toc_added = False

    def generate_badges(self) -> str:
        """Generate PyPI badges for the package."""
        badges = f"""<!-- PyPI Badges -->
[![PyPI version](https://badge.fury.io/py/{self.package_name}.svg)](https://pypi.org/project/{self.package_name}/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/{self.package_name})](https://pypi.org/project/{self.package_name}/)
[![PyPI - License](https://img.shields.io/pypi/l/{self.package_name})](https://pypi.org/project/{self.package_name}/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/{self.package_name})](https://pypi.org/project/{self.package_name}/)
[![PyPI - Status](https://img.shields.io/pypi/status/{self.package_name})](https://pypi.org/project/{self.package_name}/)
"""
        return badges

    def generate_installation_section(self) -> str:
        """Generate optimized installation section."""
        return f"""## Installation

### From PyPI (Recommended)

```bash
pip install {self.package_name}
```

### From Source

```bash
git clone https://github.com/anthropics/{self.package_name}.git
cd {self.package_name}
pip install -e .
```

### With Optional Dependencies

```bash
# For URL support (Git and HTTP sources)
pip install {self.package_name}[url]

# For development
pip install {self.package_name}[dev]
```
"""

    def generate_quick_start(self) -> str:
        """Generate quick start section."""
        return f"""## Quick Start

### Install Your First Extension

```bash
# Install a local extension
{self.package_name} install ./my-extension.json

# Install from a directory with multiple extensions
{self.package_name} install ./extension-pack/ --interactive

# Install at user level (across all projects)
{self.package_name} install ./my-extension --user
```

### Validate Extensions

```bash
# Validate before installing
{self.package_name} validate ./extension-folder

# Validate specific type
{self.package_name} validate ./hooks-folder --type hooks
```

### Manage Extensions

```bash
# List installed extensions
{self.package_name} list

# Get info about an extension
{self.package_name} info my-extension

# Remove an extension
{self.package_name} remove my-extension
```
"""

    def enhance_readme(self, readme_content: str) -> Tuple[str, List[str]]:
        """
        Enhance README content for PyPI.

        Args:
            readme_content: Original README content

        Returns:
            Tuple of (enhanced_content, changes_made)
        """
        changes = []
        content = readme_content

        # Add badges if not present
        if "badge" not in content.lower() and "![" not in content[:500]:
            # Find the first line after the main heading
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("# ") and i + 1 < len(lines):
                    # Insert badges after the title
                    badges = self.generate_badges()
                    lines.insert(i + 1, "")
                    lines.insert(i + 2, badges)
                    content = "\n".join(lines)
                    changes.append("Added PyPI badges")
                    self.badges_added = True
                    break

        # Ensure proper installation section
        if "## installation" not in content.lower():
            # Add installation section after badges/description
            install_section = self.generate_installation_section()

            # Find a good place to insert
            lines = content.split("\n")
            inserted = False

            for i, line in enumerate(lines):
                if line.startswith("## ") and "feature" in line.lower():
                    # Insert before features
                    lines.insert(i, install_section)
                    content = "\n".join(lines)
                    changes.append("Added installation section")
                    inserted = True
                    break

            if not inserted:
                # Add at the end if no suitable place found
                content += "\n\n" + install_section
                changes.append("Added installation section at end")

        # Add quick start if missing
        if "## quick start" not in content.lower() and "## getting started" not in content.lower():
            quick_start = self.generate_quick_start()

            # Insert after installation
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "## installation" in line.lower():
                    # Find the next section
                    for j in range(i + 1, len(lines)):
                        if lines[j].startswith("## "):
                            lines.insert(j, quick_start)
                            content = "\n".join(lines)
                            changes.append("Added quick start section")
                            break
                    break

        # Improve formatting
        content = self._improve_formatting(content)
        if content != readme_content:
            changes.append("Improved formatting")

        # Add table of contents if complex
        if content.count("## ") > 5 and "[table of contents]" not in content.lower():
            toc = self._generate_toc(content)
            if toc:
                lines = content.split("\n")
                # Insert after badges
                for i, line in enumerate(lines):
                    if "badge" in line and i + 2 < len(lines):
                        lines.insert(i + 2, toc)
                        content = "\n".join(lines)
                        changes.append("Added table of contents")
                        self.toc_added = True
                        break

        return content, changes

    def _improve_formatting(self, content: str) -> str:
        """Improve README formatting for better rendering."""
        # Ensure consistent heading levels
        lines = content.split("\n")

        for i, line in enumerate(lines):
            # Fix heading spacing
            if re.match(r"^#+\s+\w", line):
                # Ensure single space after #
                lines[i] = re.sub(r"^(#+)\s+", r"\1 ", line)

            # Fix code block language hints
            if line.strip() == "```":
                # Check if previous line suggests a language
                if i > 0:
                    prev = lines[i - 1].lower()
                    if "bash" in prev or "shell" in prev or "command" in prev:
                        lines[i] = "```bash"
                    elif "python" in prev:
                        lines[i] = "```python"
                    elif "json" in prev:
                        lines[i] = "```json"

        content = "\n".join(lines)

        # Ensure proper line breaks around sections
        content = re.sub(r"\n(##\s+)", r"\n\n\1", content)
        content = re.sub(r"(```\n)\n+", r"\1", content)

        # Remove excessive blank lines
        content = re.sub(r"\n{3,}", "\n\n", content)

        return content

    def _generate_toc(self, content: str) -> Optional[str]:
        """Generate table of contents from headings."""
        lines = content.split("\n")
        toc_items = []

        for line in lines:
            if line.startswith("## ") and not line.startswith("## Table of Contents"):
                # Extract heading text
                heading = line[3:].strip()
                # Create anchor
                anchor = heading.lower().replace(" ", "-").replace("/", "-")
                anchor = re.sub(r"[^a-z0-9-]", "", anchor)
                toc_items.append(f"- [{heading}](#{anchor})")

        if len(toc_items) > 3:
            toc = "## Table of Contents\n\n"
            toc += "\n".join(toc_items)
            toc += "\n"
            return toc

        return None

    def add_pypi_specific_sections(self, content: str) -> str:
        """Add sections specifically useful for PyPI display."""
        sections_to_add = []

        # Add project links if missing
        if "## links" not in content.lower() and "## resources" not in content.lower():
            links_section = """## Links

- [GitHub Repository](https://github.com/anthropics/pacc)
- [Documentation](https://pacc.readthedocs.io)
- [Issue Tracker](https://github.com/anthropics/pacc/issues)
- [Changelog](https://github.com/anthropics/pacc/blob/main/CHANGELOG.md)
"""
            sections_to_add.append(links_section)

        # Add contributing section if missing
        if "## contribut" not in content.lower():
            contributing_section = """## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/anthropics/pacc.git
cd pacc

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

# Install in development mode
pip install -e .[dev]

# Run tests
pytest
```
"""
            sections_to_add.append(contributing_section)

        # Add license section if missing
        if "## license" not in content.lower():
            license_section = """## License

PACC is released under the MIT License. See the [LICENSE](LICENSE) file for details.
"""
            sections_to_add.append(license_section)

        # Append new sections
        if sections_to_add:
            content = content.rstrip() + "\n\n" + "\n\n".join(sections_to_add)

        return content

    def validate_readme(self, content: str) -> List[str]:
        """Validate README for PyPI compatibility."""
        issues = []

        # Check length
        if len(content) < 1000:
            issues.append("README seems too short - consider adding more details")

        if len(content) > 50000:
            issues.append("README very long - consider moving some content to docs")

        # Check for required sections
        required_sections = ["installation", "usage", "license"]
        content_lower = content.lower()

        for section in required_sections:
            if f"## {section}" not in content_lower and f"# {section}" not in content_lower:
                issues.append(f"Missing recommended section: {section}")

        # Check for broken markdown
        if content.count("```") % 2 != 0:
            issues.append("Unmatched code block markers (```)")

        if content.count("[") != content.count("]"):
            issues.append("Unmatched brackets - check markdown links")

        # Check for placeholder content
        placeholders = ["todo", "fixme", "xxx", "tbd"]
        for placeholder in placeholders:
            if placeholder in content_lower:
                issues.append(f"Found placeholder text: {placeholder}")

        return issues


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Enhance README.md for PyPI presentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s README.md
  %(prog)s README.md --output README_enhanced.md
  %(prog)s README.md --package-name my-package
  %(prog)s README.md --check-only
        """,
    )

    parser.add_argument("readme_path", type=Path, help="Path to README.md file")

    parser.add_argument("--output", type=Path, help="Output path (default: overwrite original)")

    parser.add_argument(
        "--package-name", default="pacc", help="Package name for badges (default: pacc)"
    )

    parser.add_argument(
        "--check-only", action="store_true", help="Only validate without making changes"
    )

    parser.add_argument(
        "--add-sections",
        action="store_true",
        help="Add PyPI-specific sections (links, contributing, license)",
    )

    args = parser.parse_args()

    if not args.readme_path.exists():
        print(f"❌ Error: File not found: {args.readme_path}")
        sys.exit(1)

    # Read current README
    content = args.readme_path.read_text(encoding="utf-8")
    enhancer = ReadmeEnhancer(args.package_name)

    if args.check_only:
        # Validate only
        issues = enhancer.validate_readme(content)

        print("📋 README Validation Report")
        print("=" * 50)

        if issues:
            print(f"\n⚠️  Issues found ({len(issues)}):")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("\n✅ No issues found!")

        print("\n📊 README Statistics:")
        print(f"  - Length: {len(content):,} characters")
        print(f"  - Lines: {content.count(chr(10)):,}")
        print(f"  - Sections: {content.count('## ')}")
        print(f"  - Code blocks: {content.count('```') // 2}")

    else:
        # Enhance README
        print("🔧 Enhancing README for PyPI...")

        enhanced_content, changes = enhancer.enhance_readme(content)

        if args.add_sections:
            enhanced_content = enhancer.add_pypi_specific_sections(enhanced_content)
            if enhanced_content != content:
                changes.append("Added PyPI-specific sections")

        # Validate enhanced version
        issues = enhancer.validate_readme(enhanced_content)

        if changes:
            print("\n✅ Enhancements made:")
            for change in changes:
                print(f"  - {change}")

            # Save enhanced version
            output_path = args.output or args.readme_path

            # Backup original if overwriting
            if not args.output and output_path == args.readme_path:
                backup_path = args.readme_path.with_suffix(".md.backup")
                backup_path.write_text(content, encoding="utf-8")
                print(f"\n💾 Original backed up to: {backup_path}")

            # Write enhanced version
            output_path.write_text(enhanced_content, encoding="utf-8")
            print(f"\n📝 Enhanced README saved to: {output_path}")

        else:
            print("\n✅ README already well-formatted for PyPI!")

        if issues:
            print("\n⚠️  Remaining issues to address:")
            for issue in issues:
                print(f"  - {issue}")

        # Show what was added
        if enhancer.badges_added:
            print("\n🏷️  PyPI badges added - your package will look professional!")

        if enhancer.toc_added:
            print("\n📑 Table of contents added for better navigation")

    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    main()
