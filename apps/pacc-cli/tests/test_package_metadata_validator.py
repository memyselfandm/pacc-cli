"""
Tests for package metadata validation functionality.
"""

import sys
from pathlib import Path

# Add the scripts directory to the path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "package_registration"))

from validate_package_metadata import (
    PackageMetadataValidator,
    check_description_quality,
    check_version_format,
    validate_classifiers,
    validate_pyproject_metadata,
)


class TestPackageMetadataValidator:
    """Test the PackageMetadataValidator class."""

    def test_validate_complete_metadata(self):
        """Test validation of complete, valid metadata."""
        validator = PackageMetadataValidator()

        metadata = {
            "name": "pacc",
            "version": "1.0.0",
            "description": "Package manager for Claude Code - simplify installation",
            "authors": [{"name": "PACC Team", "email": "pacc@example.com"}],
            "license": {"text": "MIT"},
            "readme": "README.md",
            "requires-python": ">=3.8",
            "keywords": ["package", "manager", "claude"],
            "classifiers": [
                "Development Status :: 4 - Beta",
                "Intended Audience :: Developers",
                "License :: OSI Approved :: MIT License",
                "Programming Language :: Python :: 3",
                "Programming Language :: Python :: 3.8",
            ],
            "urls": {
                "Homepage": "https://github.com/example/pacc",
                "Repository": "https://github.com/example/pacc",
            },
        }

        result = validator.validate_metadata(metadata)

        assert result["valid"] is True
        assert result["score"] >= 90  # Should have high score
        assert len(result["errors"]) == 0
        assert len(result["warnings"]) == 0

    def test_validate_minimal_metadata(self):
        """Test validation of minimal required metadata."""
        validator = PackageMetadataValidator()

        metadata = {
            "name": "pacc",
            "version": "0.1.0",
        }

        result = validator.validate_metadata(metadata)

        assert result["valid"] is False  # Missing required fields
        assert "description" in str(result["errors"])
        assert result["score"] < 50

    def test_validate_version_formats(self):
        """Test version format validation."""
        validator = PackageMetadataValidator()

        # Valid versions
        valid_versions = [
            "1.0.0",
            "0.1.0",
            "2.3.4",
            "1.0.0a1",
            "1.0.0b2",
            "1.0.0rc1",
            "1.0.0.post1",
            "1.0.0.dev0",
        ]

        for version in valid_versions:
            assert validator.check_version_format(version) is True

        # Invalid versions
        invalid_versions = ["1", "1.0", "v1.0.0", "1.0.0-beta", "latest", ""]

        for version in invalid_versions:
            assert validator.check_version_format(version) is False

    def test_validate_description_quality(self):
        """Test description quality checks."""
        validator = PackageMetadataValidator()

        # Good descriptions
        good_desc = "Package manager for Claude Code - simplify installation and management"
        result = validator.check_description_quality(good_desc)
        assert result["quality"] == "good"
        assert result["score"] >= 80

        # Too short
        short_desc = "Package manager"
        result = validator.check_description_quality(short_desc)
        assert result["quality"] in ["poor", "fair"]
        assert "too short" in result["suggestions"][0].lower()

        # Too long
        long_desc = "This is " + "a very long description " * 20
        result = validator.check_description_quality(long_desc)
        assert "too long" in result["suggestions"][0].lower()

    def test_validate_classifiers(self):
        """Test PyPI classifier validation."""
        validator = PackageMetadataValidator()

        # Valid classifiers
        valid_classifiers = [
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python :: 3",
        ]

        result = validator.validate_classifiers(valid_classifiers)
        assert result["valid"] is True
        assert len(result["invalid"]) == 0

        # Invalid classifiers
        invalid_classifiers = [
            "Development Status :: 7 - Awesome",  # Not a real status
            "License :: My Custom License",  # Not standard
            "Programming Language :: Python :: 2.5",  # Outdated
        ]

        result = validator.validate_classifiers(invalid_classifiers)
        assert result["valid"] is False
        assert len(result["invalid"]) > 0
        assert len(result["suggestions"]) > 0

    def test_check_urls(self):
        """Test URL validation and checking."""
        validator = PackageMetadataValidator()

        urls = {
            "Homepage": "https://github.com/example/pacc",
            "Documentation": "https://pacc.readthedocs.io",
            "Repository": "https://github.com/example/pacc.git",
            "Changelog": "https://github.com/example/pacc/blob/main/CHANGELOG.md",
        }

        result = validator.check_urls(urls)

        assert result["valid"] is True
        assert "Homepage" in result["checked"]
        assert len(result["issues"]) == 0

    def test_suggest_improvements(self):
        """Test improvement suggestions for metadata."""
        validator = PackageMetadataValidator()

        # Minimal metadata
        metadata = {"name": "pacc", "version": "1.0.0", "description": "Package manager"}

        suggestions = validator.suggest_improvements(metadata)

        assert len(suggestions) > 0
        assert any("authors" in s.lower() for s in suggestions)
        assert any("license" in s.lower() for s in suggestions)
        assert any("keywords" in s.lower() for s in suggestions)
        assert any("classifiers" in s.lower() for s in suggestions)

    def test_generate_metadata_report(self):
        """Test metadata quality report generation."""
        validator = PackageMetadataValidator()

        metadata = {
            "name": "pacc",
            "version": "1.0.0",
            "description": "Package manager for Claude Code",
            "authors": [{"name": "PACC Team"}],
            "keywords": ["package", "manager"],
            "classifiers": [
                "Development Status :: 4 - Beta",
                "Programming Language :: Python :: 3",
            ],
        }

        report = validator.generate_report(metadata)

        assert "name" in report
        assert "score" in report
        assert "validation" in report
        assert "improvements" in report
        assert report["score"] > 0
        assert report["score"] <= 100


class TestValidationFunctions:
    """Test standalone validation functions."""

    def test_validate_pyproject_metadata(self):
        """Test pyproject.toml metadata validation."""
        # Valid metadata
        valid_data = {
            "project": {"name": "pacc", "version": "1.0.0", "description": "Test package"}
        }

        is_valid, issues = validate_pyproject_metadata(valid_data)
        assert is_valid is True
        assert len(issues) == 0

        # Invalid metadata
        invalid_data = {
            "project": {
                "name": "pacc"
                # Missing version
            }
        }

        is_valid, issues = validate_pyproject_metadata(invalid_data)
        assert is_valid is False
        assert len(issues) > 0
        assert any("version" in issue for issue in issues)

    def test_check_version_format_function(self):
        """Test version format checking function."""
        assert check_version_format("1.0.0") is True
        assert check_version_format("1.0.0a1") is True
        assert check_version_format("1.0.0.post1") is True
        assert check_version_format("v1.0.0") is False
        assert check_version_format("1.0") is False

    def test_check_description_quality_function(self):
        """Test description quality checking function."""
        # Good description
        quality, score = check_description_quality(
            "A comprehensive package manager for Claude Code extensions"
        )
        assert quality == "good"
        assert score >= 80

        # Poor description
        quality, score = check_description_quality("pacc")
        assert quality == "poor"
        assert score < 50

    def test_validate_classifiers_function(self):
        """Test classifier validation function."""
        # Valid classifiers
        valid = ["Development Status :: 3 - Alpha", "License :: OSI Approved :: MIT License"]

        is_valid, invalid, suggestions = validate_classifiers(valid)
        assert is_valid is True
        assert len(invalid) == 0

        # Invalid classifiers
        invalid_list = ["Invalid :: Classifier"]
        is_valid, invalid, suggestions = validate_classifiers(invalid_list)
        assert is_valid is False
        assert len(invalid) == 1
        assert len(suggestions) > 0


class TestCLIIntegration:
    """Test command-line interface integration."""

    def test_validate_pyproject_file(self, tmp_path):
        """Test validating an actual pyproject.toml file."""
        # Create test pyproject.toml
        pyproject_content = """
[project]
name = "test-package"
version = "1.0.0"
description = "A test package for validation"
authors = [{name = "Test Author", email = "test@example.com"}]
license = {text = "MIT"}
readme = "README.md"
requires-python = ">=3.8"
keywords = ["test", "package"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Programming Language :: Python :: 3"
]

[project.urls]
Homepage = "https://example.com"
"""

        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)

        # Import after file creation
        from validate_package_metadata import validate_pyproject_file

        result = validate_pyproject_file(pyproject_path)

        assert result["valid"] is True
        assert result["score"] >= 80
        assert len(result["errors"]) == 0
