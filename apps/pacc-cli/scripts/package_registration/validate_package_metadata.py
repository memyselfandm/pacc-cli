#!/usr/bin/env python3
"""
Validate package metadata for PyPI compliance and quality.

This script validates pyproject.toml metadata to ensure it meets PyPI requirements
and follows best practices for package discoverability.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import tomllib

# Known valid PyPI classifiers (subset of most common ones)
VALID_CLASSIFIERS = [
    # Development Status
    "Development Status :: 1 - Planning",
    "Development Status :: 2 - Pre-Alpha",
    "Development Status :: 3 - Alpha",
    "Development Status :: 4 - Beta",
    "Development Status :: 5 - Production/Stable",
    "Development Status :: 6 - Mature",
    "Development Status :: 7 - Inactive",
    # Intended Audience
    "Intended Audience :: Developers",
    "Intended Audience :: End Users/Desktop",
    "Intended Audience :: System Administrators",
    "Intended Audience :: Science/Research",
    # License
    "License :: OSI Approved :: MIT License",
    "License :: OSI Approved :: Apache Software License",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    "License :: OSI Approved :: BSD License",
    # Programming Language
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3 :: Only",
    # Topic
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: Software Development :: Build Tools",
    "Topic :: System :: Software Distribution",
    "Topic :: Utilities",
    # Operating System
    "Operating System :: OS Independent",
    "Operating System :: POSIX",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: MacOS",
    # Environment
    "Environment :: Console",
    "Environment :: Web Environment",
    # Typing
    "Typing :: Typed",
]


class PackageMetadataValidator:
    """Validate package metadata for PyPI compliance."""

    def __init__(self):
        """Initialize the validator."""
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.suggestions: List[str] = []

    def validate_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate package metadata comprehensively.

        Args:
            metadata: Package metadata dictionary from pyproject.toml

        Returns:
            Validation results with score and recommendations
        """
        self.errors = []
        self.warnings = []
        self.suggestions = []

        score = 100  # Start with perfect score

        # Required fields
        required_fields = ["name", "version"]
        for field in required_fields:
            if field not in metadata:
                self.errors.append(f"Missing required field: {field}")
                score -= 20

        # Highly recommended fields
        recommended_fields = ["description", "authors", "license", "readme"]
        for field in recommended_fields:
            if field not in metadata:
                self.warnings.append(f"Missing recommended field: {field}")
                score -= 5

        # Validate specific fields
        if "name" in metadata:
            if not self._validate_package_name(metadata["name"]):
                score -= 10

        if "version" in metadata:
            if not self.check_version_format(metadata["version"]):
                self.errors.append(f"Invalid version format: {metadata['version']}")
                score -= 15

        if "description" in metadata:
            desc_result = self.check_description_quality(metadata["description"])
            if desc_result["quality"] == "poor":
                score -= 10
            elif desc_result["quality"] == "fair":
                score -= 5
            self.suggestions.extend(desc_result["suggestions"])

        if "keywords" in metadata:
            self._validate_keywords(metadata["keywords"])
        else:
            self.suggestions.append("Add keywords to improve discoverability")
            score -= 5

        if "classifiers" in metadata:
            classifiers_result = self.validate_classifiers(metadata["classifiers"])
            if not classifiers_result["valid"]:
                score -= 10
            if classifiers_result["suggestions"]:
                self.suggestions.extend(classifiers_result["suggestions"])
        else:
            self.suggestions.append("Add classifiers to categorize your package")
            score -= 10

        if "urls" in metadata:
            urls_result = self.check_urls(metadata["urls"])
            if not urls_result["valid"]:
                score -= 5

        # Check for Python version requirement
        if "requires-python" not in metadata:
            self.warnings.append("No Python version requirement specified")
            score -= 5

        # Ensure score doesn't go below 0
        score = max(0, score)

        return {
            "valid": len(self.errors) == 0,
            "score": score,
            "errors": self.errors,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "metadata_coverage": self._calculate_coverage(metadata),
        }

    def _validate_package_name(self, name: str) -> bool:
        """Validate package name according to PEP 508."""
        # Package names should be lowercase with hyphens or underscores
        pattern = r"^[a-z0-9]+(?:[_-][a-z0-9]+)*$"

        if not re.match(pattern, name):
            self.errors.append(
                f"Invalid package name '{name}'. Use lowercase letters, "
                "numbers, hyphens, and underscores only."
            )
            return False

        if len(name) < 2:
            self.errors.append("Package name too short (minimum 2 characters)")
            return False

        if len(name) > 50:
            self.warnings.append("Package name very long (>50 characters)")

        return True

    def check_version_format(self, version: str) -> bool:
        """Check if version follows PEP 440."""
        # Simplified PEP 440 regex
        pattern = r"^(\d+!)?\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$"
        return bool(re.match(pattern, version))

    def check_description_quality(self, description: str) -> Dict[str, Any]:
        """Check description quality and provide suggestions."""
        suggestions = []
        quality = "good"
        score = 100

        # Length check
        if len(description) < 10:
            quality = "poor"
            score = 30
            suggestions.append("Description too short - aim for at least 50 characters")
        elif len(description) < 50:
            quality = "fair"
            score = 60
            suggestions.append("Consider expanding description for better clarity")
        elif len(description) > 200:
            suggestions.append("Description quite long - consider making it more concise")
            score = 80

        # Content quality checks
        if description.lower() == description:
            suggestions.append("Consider proper capitalization in description")
            score -= 10

        if not description.endswith("."):
            suggestions.append("Consider ending description with a period")
            score -= 5

        # Check for meaningful content
        generic_words = ["package", "library", "module", "python"]
        if all(
            word not in description.lower() for word in ["manager", "tool", "framework", "utility"]
        ):
            if sum(1 for word in generic_words if word in description.lower()) >= 2:
                suggestions.append(
                    "Description seems generic - be more specific about functionality"
                )
                score -= 10

        return {
            "quality": quality if score >= 80 else ("fair" if score >= 50 else "poor"),
            "score": max(0, score),
            "suggestions": suggestions,
        }

    def _validate_keywords(self, keywords: List[str]) -> None:
        """Validate keywords list."""
        if len(keywords) == 0:
            self.warnings.append("No keywords specified")
        elif len(keywords) > 10:
            self.warnings.append("Too many keywords (>10) - focus on most relevant ones")

        for keyword in keywords:
            if len(keyword) > 30:
                self.warnings.append(f"Keyword '{keyword}' is too long")
            if " " in keyword:
                self.warnings.append(f"Keyword '{keyword}' contains spaces - use hyphens instead")

    def validate_classifiers(self, classifiers: List[str]) -> Dict[str, Any]:
        """Validate PyPI classifiers."""
        invalid = []
        suggestions = []

        for classifier in classifiers:
            if classifier not in VALID_CLASSIFIERS:
                # Check if it's a partial match
                partial_matches = [c for c in VALID_CLASSIFIERS if classifier.lower() in c.lower()]
                if partial_matches:
                    invalid.append(classifier)
                    suggestions.append(f"Did you mean: {partial_matches[0]}?")
                else:
                    invalid.append(classifier)

        # Check for recommended classifiers
        has_status = any(c.startswith("Development Status ::") for c in classifiers)
        has_audience = any(c.startswith("Intended Audience ::") for c in classifiers)
        has_license = any(c.startswith("License ::") for c in classifiers)
        has_python = any(c.startswith("Programming Language :: Python") for c in classifiers)

        if not has_status:
            suggestions.append("Add a Development Status classifier")
        if not has_audience:
            suggestions.append("Add an Intended Audience classifier")
        if not has_license:
            suggestions.append("Add a License classifier")
        if not has_python:
            suggestions.append("Add Programming Language :: Python classifiers")

        return {"valid": len(invalid) == 0, "invalid": invalid, "suggestions": suggestions}

    def check_urls(self, urls: Dict[str, str]) -> Dict[str, Any]:
        """Check project URLs."""
        issues = []
        checked = []

        # Recommended URL types
        recommended = ["Homepage", "Repository", "Documentation", "Bug Tracker"]

        for url_type in recommended:
            if url_type not in urls:
                self.suggestions.append(f"Consider adding {url_type} URL")

        for url_type, url in urls.items():
            checked.append(url_type)

            # Basic URL validation
            if not url.startswith(("http://", "https://")):
                issues.append(f"{url_type} URL should start with http:// or https://")

            # Check for common patterns
            if "github.com" in url and url.endswith(".git"):
                self.suggestions.append(
                    f"Remove .git from {url_type} URL for better web compatibility"
                )

        return {"valid": len(issues) == 0, "checked": checked, "issues": issues}

    def _calculate_coverage(self, metadata: Dict[str, Any]) -> float:
        """Calculate metadata completeness percentage."""
        all_fields = [
            "name",
            "version",
            "description",
            "readme",
            "requires-python",
            "license",
            "authors",
            "maintainers",
            "keywords",
            "classifiers",
            "urls",
            "dependencies",
            "optional-dependencies",
            "scripts",
        ]

        present_fields = sum(1 for field in all_fields if metadata.get(field))
        return (present_fields / len(all_fields)) * 100

    def suggest_improvements(self, metadata: Dict[str, Any]) -> List[str]:
        """Generate improvement suggestions for metadata."""
        suggestions = []

        # Check for missing beneficial fields
        if "authors" not in metadata:
            suggestions.append("Add package authors with name and email")

        if "license" not in metadata:
            suggestions.append("Specify a license (e.g., MIT, Apache-2.0, GPL-3.0)")

        if "urls" not in metadata:
            suggestions.append("Add project URLs (Homepage, Repository, etc.)")
        elif "Homepage" not in metadata.get("urls", {}):
            suggestions.append("Add a Homepage URL")

        if "keywords" not in metadata or len(metadata.get("keywords", [])) < 3:
            suggestions.append("Add more keywords (3-7 recommended) for better discoverability")

        if "classifiers" not in metadata or len(metadata.get("classifiers", [])) < 5:
            suggestions.append("Add more classifiers to better categorize your package")

        if "readme" not in metadata:
            suggestions.append("Specify a README file")

        if "requires-python" not in metadata:
            suggestions.append("Specify minimum Python version requirement")

        return suggestions

    def generate_report(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a comprehensive metadata quality report."""
        validation_result = self.validate_metadata(metadata)
        improvements = self.suggest_improvements(metadata)

        return {
            "name": metadata.get("name", "Unknown"),
            "version": metadata.get("version", "Unknown"),
            "score": validation_result["score"],
            "grade": self._score_to_grade(validation_result["score"]),
            "validation": validation_result,
            "improvements": improvements,
            "metadata_coverage": validation_result["metadata_coverage"],
            "report_generated": datetime.now().isoformat(),
        }

    def _score_to_grade(self, score: int) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"


def validate_pyproject_file(pyproject_path: Path) -> Dict[str, Any]:
    """Validate a pyproject.toml file."""
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        if "project" not in data:
            return {
                "valid": False,
                "score": 0,
                "errors": ["No [project] section found in pyproject.toml"],
                "warnings": [],
                "suggestions": ["Add [project] section with package metadata"],
            }

        validator = PackageMetadataValidator()
        return validator.generate_report(data["project"])

    except Exception as e:
        return {
            "valid": False,
            "score": 0,
            "errors": [f"Error reading pyproject.toml: {e!s}"],
            "warnings": [],
            "suggestions": [],
        }


def validate_pyproject_metadata(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate pyproject.toml metadata structure."""
    issues = []

    if "project" not in data:
        issues.append("Missing [project] section")
        return False, issues

    project = data["project"]

    # Check required fields
    if "name" not in project:
        issues.append("Missing required field: name")
    if "version" not in project:
        issues.append("Missing required field: version")

    return len(issues) == 0, issues


def check_version_format(version: str) -> bool:
    """Check if version string follows PEP 440."""
    pattern = r"^(\d+!)?\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$"
    return bool(re.match(pattern, version))


def check_description_quality(description: str) -> Tuple[str, int]:
    """Check description quality and return rating."""
    if len(description) < 10:
        return "poor", 20
    elif len(description) < 50:
        return "fair", 60
    elif len(description) > 200:
        return "good", 80
    else:
        return "good", 90


def validate_classifiers(classifiers: List[str]) -> Tuple[bool, List[str], List[str]]:
    """Validate PyPI classifiers."""
    invalid = []
    suggestions = []

    for classifier in classifiers:
        if classifier not in VALID_CLASSIFIERS:
            invalid.append(classifier)
            # Find similar valid classifier
            for valid in VALID_CLASSIFIERS:
                if classifier.lower() in valid.lower():
                    suggestions.append(f"Use '{valid}' instead of '{classifier}'")
                    break

    return len(invalid) == 0, invalid, suggestions


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate package metadata for PyPI compliance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s pyproject.toml
  %(prog)s --json pyproject.toml
  %(prog)s --suggestions pyproject.toml
        """,
    )

    parser.add_argument("pyproject_path", type=Path, help="Path to pyproject.toml file")

    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    parser.add_argument("--suggestions", action="store_true", help="Show improvement suggestions")

    parser.add_argument(
        "--strict", action="store_true", help="Use strict validation (warnings become errors)"
    )

    args = parser.parse_args()

    if not args.pyproject_path.exists():
        print(f"❌ Error: File not found: {args.pyproject_path}")
        sys.exit(1)

    # Validate the file
    result = validate_pyproject_file(args.pyproject_path)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Display results
        print("\n📋 Package Metadata Validation Report")
        print("=" * 50)
        print(f"Package: {result.get('name', 'Unknown')}")
        print(f"Version: {result.get('version', 'Unknown')}")
        print(f"Score: {result.get('score', 0)}/100 (Grade: {result.get('grade', 'F')})")
        print(f"Metadata Coverage: {result.get('metadata_coverage', 0):.1f}%")

        validation = result.get("validation", {})

        if validation.get("errors"):
            print(f"\n❌ Errors ({len(validation['errors'])}):")
            for error in validation["errors"]:
                print(f"  - {error}")

        if validation.get("warnings"):
            print(f"\n⚠️  Warnings ({len(validation['warnings'])}):")
            for warning in validation["warnings"]:
                print(f"  - {warning}")

        if args.suggestions or validation.get("suggestions"):
            suggestions = validation.get("suggestions", []) + result.get("improvements", [])
            if suggestions:
                print(f"\n💡 Suggestions ({len(suggestions)}):")
                for suggestion in suggestions:
                    print(f"  - {suggestion}")

        print("\n" + "=" * 50)

        if result.get("score", 0) >= 80:
            print("✅ Package metadata is in good shape for PyPI!")
        elif result.get("score", 0) >= 60:
            print("⚠️  Package metadata needs some improvements")
        else:
            print("❌ Package metadata needs significant improvements")

    # Exit code based on validation result
    sys.exit(0 if result.get("valid", False) else 1)


if __name__ == "__main__":
    main()
