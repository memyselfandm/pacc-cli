#!/usr/bin/env python3
"""
Prepare for PyPI package registration.

This script helps prepare all necessary files and documentation for registering
a package on PyPI, including checking requirements and generating templates.
"""
import argparse
import json
import os
import sys
import tomllib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


class PyPIRegistrationPrep:
    """Prepare package for PyPI registration."""
    
    def __init__(self, project_path: Path):
        """Initialize with project path."""
        self.project_path = Path(project_path).resolve()
        self.pyproject_path = self.project_path / "pyproject.toml"
        self.readme_path = self.project_path / "README.md"
        self.license_path = self.project_path / "LICENSE"
        self.package_data: Dict[str, Any] = {}
        
    def check_prerequisites(self) -> Dict[str, Any]:
        """Check if all prerequisites for PyPI registration are met."""
        checks = {
            "has_pyproject": self.pyproject_path.exists(),
            "has_readme": self.readme_path.exists(),
            "has_license": self.license_path.exists(),
            "has_build_system": False,
            "has_project_metadata": False,
            "has_version": False,
            "has_description": False,
            "has_authors": False,
            "has_classifiers": False,
            "issues": []
        }
        
        if checks["has_pyproject"]:
            try:
                with open(self.pyproject_path, 'rb') as f:
                    self.package_data = tomllib.load(f)
                
                # Check build system
                if "build-system" in self.package_data:
                    checks["has_build_system"] = True
                else:
                    checks["issues"].append("Missing [build-system] section in pyproject.toml")
                
                # Check project metadata
                if "project" in self.package_data:
                    checks["has_project_metadata"] = True
                    project = self.package_data["project"]
                    
                    # Check required fields
                    if "version" in project:
                        checks["has_version"] = True
                    else:
                        checks["issues"].append("Missing version in [project] section")
                    
                    if "description" in project:
                        checks["has_description"] = True
                    else:
                        checks["issues"].append("Missing description in [project] section")
                    
                    if "authors" in project:
                        checks["has_authors"] = True
                    else:
                        checks["issues"].append("Missing authors in [project] section")
                    
                    if "classifiers" in project:
                        checks["has_classifiers"] = True
                    else:
                        checks["issues"].append("Missing classifiers in [project] section")
                else:
                    checks["issues"].append("Missing [project] section in pyproject.toml")
                    
            except Exception as e:
                checks["issues"].append(f"Error reading pyproject.toml: {str(e)}")
        else:
            checks["issues"].append("pyproject.toml not found")
        
        if not checks["has_readme"]:
            checks["issues"].append("README.md not found")
            
        if not checks["has_license"]:
            checks["issues"].append("LICENSE file not found")
        
        checks["ready_for_registration"] = len(checks["issues"]) == 0
        
        return checks
    
    def generate_registration_docs(self, output_dir: Path) -> Dict[str, Path]:
        """Generate documentation for the registration process."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        docs = {}
        
        # Generate PyPI registration guide
        guide_path = output_dir / "PYPI_REGISTRATION_GUIDE.md"
        guide_content = self._generate_registration_guide()
        guide_path.write_text(guide_content)
        docs["registration_guide"] = guide_path
        
        # Generate package checklist
        checklist_path = output_dir / "PYPI_CHECKLIST.md"
        checklist_content = self._generate_checklist()
        checklist_path.write_text(checklist_content)
        docs["checklist"] = checklist_path
        
        # Generate test installation script
        test_script_path = output_dir / "test_pypi_installation.sh"
        test_script_content = self._generate_test_script()
        test_script_path.write_text(test_script_content)
        test_script_path.chmod(0o755)
        docs["test_script"] = test_script_path
        
        # Generate package metadata summary
        metadata_path = output_dir / "package_metadata.json"
        metadata_content = self._extract_package_metadata()
        metadata_path.write_text(json.dumps(metadata_content, indent=2))
        docs["metadata"] = metadata_path
        
        return docs
    
    def _generate_registration_guide(self) -> str:
        """Generate a comprehensive PyPI registration guide."""
        package_name = self.package_data.get("project", {}).get("name", "your-package")
        
        return f"""# PyPI Registration Guide for {package_name}

## Prerequisites

Before registering on PyPI, ensure you have:
1. A PyPI account (register at https://pypi.org/account/register/)
2. Two-factor authentication enabled (recommended)
3. API token generated (https://pypi.org/manage/account/)

## Step-by-Step Registration Process

### 1. Test on TestPyPI First

TestPyPI is a separate instance for testing:

```bash
# Install build tools
pip install --upgrade build twine

# Build the package
python -m build

# Upload to TestPyPI
python -m twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --no-deps {package_name}
```

### 2. Prepare for Production PyPI

1. **Verify Package Name Availability**
   ```bash
   python scripts/package_registration/check_pypi_availability.py {package_name}
   ```

2. **Review Package Metadata**
   - Ensure version number follows semantic versioning
   - Check description is clear and concise
   - Verify all URLs are correct
   - Confirm license is properly specified

3. **Test Package Locally**
   ```bash
   # Install in development mode
   pip install -e .
   
   # Run tests
   pytest
   
   # Test command-line interface
   {package_name} --help
   ```

### 3. Upload to PyPI

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build fresh distribution
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

### 4. Post-Registration Steps

1. **Verify Installation**
   ```bash
   # Create fresh virtual environment
   python -m venv test_env
   source test_env/bin/activate  # On Windows: test_env\\Scripts\\activate
   
   # Install from PyPI
   pip install {package_name}
   
   # Test functionality
   {package_name} --version
   ```

2. **Update Documentation**
   - Add PyPI badges to README
   - Update installation instructions
   - Add link to PyPI page

3. **Configure Automated Releases**
   - Set up GitHub Actions for automatic PyPI uploads
   - Use trusted publishing (recommended)

## API Token Configuration

### Creating a .pypirc file

Create `~/.pypirc` with the following content:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = <your-pypi-token>

[testpypi]
username = __token__
password = <your-testpypi-token>
```

**Security Note**: Set appropriate permissions:
```bash
chmod 600 ~/.pypirc
```

## Troubleshooting Common Issues

### Package Name Already Taken
- Run the availability checker to find alternatives
- Consider namespacing (e.g., `myorg-{package_name}`)

### Version Already Exists
- PyPI doesn't allow re-uploading the same version
- Increment version number in pyproject.toml
- Delete local dist/ folder and rebuild

### Missing Metadata
- Ensure all required fields in pyproject.toml are filled
- Validate with: `python -m build --sdist`

### Authentication Errors
- Verify API token is correct
- Ensure token has upload permissions
- Check if using __token__ as username

## Best Practices

1. **Always test on TestPyPI first**
2. **Use semantic versioning** (MAJOR.MINOR.PATCH)
3. **Include comprehensive README** with examples
4. **Add badges** for version, downloads, and build status
5. **Set up automated testing** before each release
6. **Tag releases in Git** matching PyPI versions
7. **Use trusted publishing** with GitHub Actions

## Additional Resources

- [PyPI Publishing Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- [Semantic Versioning](https://semver.org/)
- [Python Packaging User Guide](https://packaging.python.org/)
- [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)

---
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    def _generate_checklist(self) -> str:
        """Generate a pre-registration checklist."""
        checks = self.check_prerequisites()
        package_name = self.package_data.get("project", {}).get("name", "your-package")
        
        checklist_items = [
            ("Project Structure", [
                ("pyproject.toml exists", checks["has_pyproject"]),
                ("README.md exists", checks["has_readme"]),
                ("LICENSE file exists", checks["has_license"]),
            ]),
            ("Package Metadata", [
                ("[build-system] configured", checks["has_build_system"]),
                ("[project] section complete", checks["has_project_metadata"]),
                ("Version specified", checks["has_version"]),
                ("Description provided", checks["has_description"]),
                ("Authors listed", checks["has_authors"]),
                ("Classifiers added", checks["has_classifiers"]),
            ]),
            ("Code Quality", [
                ("All tests passing", None),
                ("Code formatted (ruff/black)", None),
                ("Type hints added (mypy)", None),
                ("Documentation complete", None),
            ]),
            ("PyPI Preparation", [
                ("PyPI account created", None),
                ("2FA enabled", None),
                ("API token generated", None),
                ("Package name available", None),
            ]),
            ("Distribution", [
                ("Build tools installed", None),
                ("Test build successful", None),
                ("TestPyPI upload tested", None),
                ("Installation tested", None),
            ])
        ]
        
        content = f"""# PyPI Registration Checklist for {package_name}

## Pre-Registration Checklist

"""
        for section, items in checklist_items:
            content += f"### {section}\n\n"
            for item, status in items:
                if status is None:
                    checkbox = "- [ ]"
                elif status:
                    checkbox = "- [x]"
                else:
                    checkbox = "- [ ] ❌"
                content += f"{checkbox} {item}\n"
            content += "\n"
        
        if checks["issues"]:
            content += "## Issues to Resolve\n\n"
            for issue in checks["issues"]:
                content += f"- ⚠️  {issue}\n"
            content += "\n"
        
        content += f"""## Registration Status

**Ready for Registration**: {'✅ Yes' if checks['ready_for_registration'] else '❌ No - resolve issues above'}

## Commands to Run

```bash
# 1. Check package name availability
python scripts/package_registration/check_pypi_availability.py {package_name}

# 2. Build the package
python -m build

# 3. Check the built package
twine check dist/*

# 4. Upload to TestPyPI
twine upload --repository testpypi dist/*

# 5. Test installation
pip install --index-url https://test.pypi.org/simple/ {package_name}

# 6. Upload to PyPI (when ready)
twine upload dist/*
```

---
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        return content
    
    def _generate_test_script(self) -> str:
        """Generate a test installation script."""
        package_name = self.package_data.get("project", {}).get("name", "your-package")
        
        return f"""#!/bin/bash
# Test installation script for {package_name}

set -e  # Exit on error

echo "🧪 Testing PyPI installation for {package_name}"
echo "============================================="

# Create temporary directory
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv test_env
source test_env/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Test installation from TestPyPI
echo "🔍 Testing installation from TestPyPI..."
if pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ {package_name}; then
    echo "✅ TestPyPI installation successful"
    
    # Test basic functionality
    echo "🏃 Testing basic functionality..."
    {package_name} --version
    {package_name} --help
    
    # Run basic import test
    echo "🐍 Testing Python import..."
    python -c "import {package_name.replace('-', '_')}; print('✅ Import successful')"
    
else
    echo "❌ TestPyPI installation failed"
fi

# Test installation from PyPI (if available)
echo ""
echo "🔍 Testing installation from PyPI..."
pip uninstall -y {package_name} || true
if pip install {package_name}; then
    echo "✅ PyPI installation successful"
    {package_name} --version
else
    echo "ℹ️  Package not yet available on PyPI"
fi

# Cleanup
deactivate
cd -
rm -rf $TEMP_DIR

echo ""
echo "🎉 Testing complete!"
"""
    
    def _extract_package_metadata(self) -> Dict[str, Any]:
        """Extract package metadata for review."""
        if not self.package_data:
            return {"error": "No package data available"}
        
        project = self.package_data.get("project", {})
        
        metadata = {
            "name": project.get("name", "Unknown"),
            "version": project.get("version", "Unknown"),
            "description": project.get("description", ""),
            "authors": project.get("authors", []),
            "maintainers": project.get("maintainers", []),
            "license": project.get("license", {}),
            "keywords": project.get("keywords", []),
            "classifiers": project.get("classifiers", []),
            "urls": project.get("urls", {}),
            "dependencies": project.get("dependencies", []),
            "requires-python": project.get("requires-python", ""),
            "readme": project.get("readme", ""),
            "scripts": project.get("scripts", {}),
            "entry-points": project.get("entry-points", {}),
            "optional-dependencies": project.get("optional-dependencies", {}),
            "build-system": self.package_data.get("build-system", {}),
            "extracted_at": datetime.now().isoformat()
        }
        
        return metadata
    
    def generate_badges(self) -> str:
        """Generate README badges for PyPI."""
        package_name = self.package_data.get("project", {}).get("name", "your-package")
        
        return f"""<!-- PyPI Badges -->
[![PyPI version](https://badge.fury.io/py/{package_name}.svg)](https://badge.fury.io/py/{package_name})
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/{package_name})](https://pypi.org/project/{package_name}/)
[![PyPI - License](https://img.shields.io/pypi/l/{package_name})](https://pypi.org/project/{package_name}/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/{package_name})](https://pypi.org/project/{package_name}/)
[![PyPI - Status](https://img.shields.io/pypi/status/{package_name})](https://pypi.org/project/{package_name}/)
"""


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Prepare package for PyPI registration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s .
  %(prog)s /path/to/project
  %(prog)s --check-only
  %(prog)s --output-dir ./pypi-prep
        """
    )
    
    parser.add_argument(
        'project_path',
        nargs='?',
        default='.',
        help='Path to project directory (default: current directory)'
    )
    
    parser.add_argument(
        '--check-only',
        action='store_true',
        help='Only check prerequisites without generating docs'
    )
    
    parser.add_argument(
        '--output-dir',
        default='./package_registration',
        help='Directory for generated documentation (default: ./package_registration)'
    )
    
    parser.add_argument(
        '--badges',
        action='store_true',
        help='Generate PyPI badges for README'
    )
    
    args = parser.parse_args()
    
    # Initialize prep tool
    prep = PyPIRegistrationPrep(args.project_path)
    
    # Check prerequisites
    print(f"📋 Checking PyPI registration prerequisites for: {prep.project_path}")
    print("=" * 60)
    
    checks = prep.check_prerequisites()
    
    # Display check results
    print(f"✓ pyproject.toml: {'✅' if checks['has_pyproject'] else '❌'}")
    print(f"✓ README.md: {'✅' if checks['has_readme'] else '❌'}")
    print(f"✓ LICENSE: {'✅' if checks['has_license'] else '❌'}")
    print(f"✓ Build system: {'✅' if checks['has_build_system'] else '❌'}")
    print(f"✓ Package metadata: {'✅' if checks['has_project_metadata'] else '❌'}")
    
    if checks['issues']:
        print("\n⚠️  Issues found:")
        for issue in checks['issues']:
            print(f"  - {issue}")
    
    print(f"\n📊 Ready for registration: {'✅ Yes' if checks['ready_for_registration'] else '❌ No'}")
    
    if args.badges:
        print("\n📛 PyPI Badges for README:")
        print("-" * 60)
        print(prep.generate_badges())
    
    if not args.check_only:
        print(f"\n📝 Generating registration documentation...")
        output_dir = Path(args.output_dir)
        docs = prep.generate_registration_docs(output_dir)
        
        print(f"\n✅ Generated files in {output_dir}:")
        for doc_type, path in docs.items():
            print(f"  - {path.name}")
        
        print(f"\n📖 Next steps:")
        print(f"  1. Review the registration guide: {docs['registration_guide']}")
        print(f"  2. Complete the checklist: {docs['checklist']}")
        print(f"  3. Run the test script: {docs['test_script']}")
    
    # Exit with appropriate code
    sys.exit(0 if checks['ready_for_registration'] else 1)


if __name__ == '__main__':
    main()