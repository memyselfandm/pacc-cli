"""Unit tests for pacc.errors.exceptions module."""

from pathlib import Path

import pytest

from pacc.errors.exceptions import (
    ConfigurationError,
    FileSystemError,
    NetworkError,
    PACCError,
    SecurityError,
    SourceError,
    ValidationError,
)


class TestPACCError:
    """Test base PACCError functionality."""

    def test_init_minimal(self):
        """Test PACCError initialization with minimal parameters."""
        error = PACCError("Test error message")

        assert error.message == "Test error message"
        assert error.error_code == "PACCERROR"  # Class name uppercase
        assert error.context == {}
        assert str(error) == "Test error message"

    def test_init_with_error_code(self):
        """Test PACCError initialization with custom error code."""
        error = PACCError("Test message", error_code="CUSTOM_ERROR")

        assert error.error_code == "CUSTOM_ERROR"

    def test_init_with_context(self):
        """Test PACCError initialization with context."""
        context = {"file": "test.json", "operation": "parse"}
        error = PACCError("Test message", context=context)

        assert error.context == context

    def test_init_full(self):
        """Test PACCError initialization with all parameters."""
        context = {"key": "value"}
        error = PACCError(message="Full test message", error_code="FULL_ERROR", context=context)

        assert error.message == "Full test message"
        assert error.error_code == "FULL_ERROR"
        assert error.context == context

    def test_str_representation(self):
        """Test string representation of PACCError."""
        error = PACCError("Error message")
        assert str(error) == "Error message"

    def test_to_dict(self):
        """Test conversion of PACCError to dictionary."""
        context = {"file": "test.json"}
        error = PACCError(message="Test error", error_code="TEST_ERROR", context=context)

        error_dict = error.to_dict()

        expected = {
            "type": "PACCError",
            "message": "Test error",
            "error_code": "TEST_ERROR",
            "context": {"file": "test.json"},
        }

        assert error_dict == expected

    def test_inheritance_from_exception(self):
        """Test that PACCError properly inherits from Exception."""
        error = PACCError("Test message")

        assert isinstance(error, Exception)
        assert isinstance(error, PACCError)

    def test_default_error_code_generation(self):
        """Test that default error code is generated from class name."""

        class CustomPACCError(PACCError):
            pass

        error = CustomPACCError("Test message")
        assert error.error_code == "CUSTOMPACCERROR"


class TestValidationError:
    """Test ValidationError functionality."""

    def test_init_minimal(self):
        """Test ValidationError initialization with minimal parameters."""
        error = ValidationError("Validation failed")

        assert error.message == "Validation failed"
        assert error.error_code == "VALIDATION_ERROR"
        assert error.file_path is None
        assert error.line_number is None
        assert error.validation_type is None

    def test_init_with_file_path(self):
        """Test ValidationError with file path."""
        file_path = Path("/test/file.json")
        error = ValidationError("Validation failed", file_path=file_path)

        assert error.file_path == file_path
        assert error.context["file_path"] == str(file_path)

    def test_init_with_line_number(self):
        """Test ValidationError with line number."""
        error = ValidationError("Syntax error", line_number=42)

        assert error.line_number == 42
        assert error.context["line_number"] == 42

    def test_init_with_validation_type(self):
        """Test ValidationError with validation type."""
        error = ValidationError("Schema error", validation_type="json_schema")

        assert error.validation_type == "json_schema"
        assert error.context["validation_type"] == "json_schema"

    def test_init_full(self):
        """Test ValidationError with all parameters."""
        file_path = Path("/test/file.json")
        error = ValidationError(
            message="JSON schema validation failed",
            file_path=file_path,
            line_number=15,
            validation_type="json_schema",
            additional_context="extra info",
        )

        assert error.message == "JSON schema validation failed"
        assert error.file_path == file_path
        assert error.line_number == 15
        assert error.validation_type == "json_schema"
        assert error.context["additional_context"] == "extra info"

    def test_context_merging(self):
        """Test that context is properly merged with specific fields."""
        file_path = Path("/test/file.json")
        error = ValidationError(
            message="Error", file_path=file_path, line_number=10, custom_field="custom_value"
        )

        expected_context = {
            "file_path": str(file_path),
            "line_number": 10,
            "custom_field": "custom_value",
        }

        assert error.context == expected_context


class TestFileSystemError:
    """Test FileSystemError functionality."""

    def test_init_minimal(self):
        """Test FileSystemError initialization with minimal parameters."""
        error = FileSystemError("File operation failed")

        assert error.message == "File operation failed"
        assert error.error_code == "FILESYSTEM_ERROR"
        assert error.file_path is None
        assert error.operation is None

    def test_init_with_file_path(self):
        """Test FileSystemError with file path."""
        file_path = Path("/test/file.txt")
        error = FileSystemError("Cannot read file", file_path=file_path)

        assert error.file_path == file_path
        assert error.context["file_path"] == str(file_path)

    def test_init_with_operation(self):
        """Test FileSystemError with operation."""
        error = FileSystemError("Operation failed", operation="copy")

        assert error.operation == "copy"
        assert error.context["operation"] == "copy"

    def test_init_full(self):
        """Test FileSystemError with all parameters."""
        file_path = Path("/test/file.txt")
        error = FileSystemError(
            message="Copy operation failed",
            file_path=file_path,
            operation="copy",
            permission_denied=True,
        )

        assert error.message == "Copy operation failed"
        assert error.file_path == file_path
        assert error.operation == "copy"
        assert error.context["permission_denied"] is True


class TestConfigurationError:
    """Test ConfigurationError functionality."""

    def test_init_minimal(self):
        """Test ConfigurationError initialization with minimal parameters."""
        error = ConfigurationError("Configuration is invalid")

        assert error.message == "Configuration is invalid"
        assert error.error_code == "CONFIGURATION_ERROR"
        assert error.config_key is None
        assert error.config_file is None

    def test_init_with_config_key(self):
        """Test ConfigurationError with config key."""
        error = ConfigurationError("Invalid key", config_key="hooks.enabled")

        assert error.config_key == "hooks.enabled"
        assert error.context["config_key"] == "hooks.enabled"

    def test_init_with_config_file(self):
        """Test ConfigurationError with config file."""
        config_file = Path("/test/.claude/settings.json")
        error = ConfigurationError("Invalid config file", config_file=config_file)

        assert error.config_file == config_file
        assert error.context["config_file"] == str(config_file)

    def test_init_full(self):
        """Test ConfigurationError with all parameters."""
        config_file = Path("/test/.claude/settings.json")
        error = ConfigurationError(
            message="Invalid configuration value",
            config_key="mcp.servers.test",
            config_file=config_file,
            expected_type="string",
        )

        assert error.message == "Invalid configuration value"
        assert error.config_key == "mcp.servers.test"
        assert error.config_file == config_file
        assert error.context["expected_type"] == "string"


class TestSourceError:
    """Test SourceError functionality."""

    def test_init_minimal(self):
        """Test SourceError initialization with minimal parameters."""
        error = SourceError("Source processing failed")

        assert error.message == "Source processing failed"
        assert error.error_code == "SOURCE_ERROR"
        assert error.source_type is None
        assert error.source_path is None

    def test_init_with_source_type(self):
        """Test SourceError with source type."""
        error = SourceError("Git clone failed", source_type="git")

        assert error.source_type == "git"
        assert error.context["source_type"] == "git"

    def test_init_with_source_path(self):
        """Test SourceError with source path."""
        source_path = Path("/test/source")
        error = SourceError("Source not found", source_path=source_path)

        assert error.source_path == source_path
        assert error.context["source_path"] == str(source_path)

    def test_init_full(self):
        """Test SourceError with all parameters."""
        source_path = Path("/test/source")
        error = SourceError(
            message="Source validation failed",
            source_type="local",
            source_path=source_path,
            validation_failed=True,
        )

        assert error.message == "Source validation failed"
        assert error.source_type == "local"
        assert error.source_path == source_path
        assert error.context["validation_failed"] is True


class TestNetworkError:
    """Test NetworkError functionality."""

    def test_init_minimal(self):
        """Test NetworkError initialization with minimal parameters."""
        error = NetworkError("Network request failed")

        assert error.message == "Network request failed"
        assert error.error_code == "NETWORK_ERROR"
        assert error.url is None
        assert error.status_code is None

    def test_init_with_url(self):
        """Test NetworkError with URL."""
        error = NetworkError("Request failed", url="https://example.com")

        assert error.url == "https://example.com"
        assert error.context["url"] == "https://example.com"

    def test_init_with_status_code(self):
        """Test NetworkError with HTTP status code."""
        error = NetworkError("HTTP error", status_code=404)

        assert error.status_code == 404
        assert error.context["status_code"] == 404

    def test_init_full(self):
        """Test NetworkError with all parameters."""
        error = NetworkError(
            message="HTTP request failed",
            url="https://api.example.com/data",
            status_code=500,
            timeout=True,
        )

        assert error.message == "HTTP request failed"
        assert error.url == "https://api.example.com/data"
        assert error.status_code == 500
        assert error.context["timeout"] is True


class TestSecurityError:
    """Test SecurityError functionality."""

    def test_init_minimal(self):
        """Test SecurityError initialization with minimal parameters."""
        error = SecurityError("Security violation detected")

        assert error.message == "Security violation detected"
        assert error.error_code == "SECURITY_ERROR"
        assert error.security_check is None

    def test_init_with_security_check(self):
        """Test SecurityError with security check type."""
        error = SecurityError("Path traversal detected", security_check="path_traversal")

        assert error.security_check == "path_traversal"
        assert error.context["security_check"] == "path_traversal"

    def test_init_full(self):
        """Test SecurityError with all parameters."""
        error = SecurityError(
            message="Malicious file detected",
            security_check="file_scanner",
            threat_type="malware",
            risk_level="high",
        )

        assert error.message == "Malicious file detected"
        assert error.security_check == "file_scanner"
        assert error.context["threat_type"] == "malware"
        assert error.context["risk_level"] == "high"


# Integration and error chaining tests
class TestErrorChaining:
    """Test error chaining and exception handling patterns."""

    def test_error_chaining_with_cause(self):
        """Test chaining errors with __cause__."""
        try:
            raise ValueError("Original error")
        except ValueError as e:
            chained_error = ValidationError("Validation failed due to value error")
            chained_error.__cause__ = e

            assert chained_error.__cause__ is e
            assert isinstance(chained_error.__cause__, ValueError)

    def test_error_hierarchy(self):
        """Test that all custom errors inherit from PACCError."""
        errors = [
            ValidationError("test"),
            FileSystemError("test"),
            ConfigurationError("test"),
            SourceError("test"),
            NetworkError("test"),
            SecurityError("test"),
        ]

        for error in errors:
            assert isinstance(error, PACCError)
            assert isinstance(error, Exception)

    def test_error_serialization_consistency(self):
        """Test that all errors can be serialized to dict consistently."""
        errors = [
            PACCError("base error"),
            ValidationError("validation error", line_number=10),
            FileSystemError("fs error", operation="read"),
            ConfigurationError("config error", config_key="test"),
            SourceError("source error", source_type="git"),
            NetworkError("network error", status_code=404),
            SecurityError("security error", security_check="auth"),
        ]

        for error in errors:
            error_dict = error.to_dict()

            # All errors should have these base fields
            assert "type" in error_dict
            assert "message" in error_dict
            assert "error_code" in error_dict
            assert "context" in error_dict

            # Type should match class name
            assert error_dict["type"] == error.__class__.__name__

            # Context should be a dictionary
            assert isinstance(error_dict["context"], dict)


# Edge cases and error conditions
class TestErrorEdgeCases:
    """Test edge cases and unusual error conditions."""

    def test_empty_message(self):
        """Test error with empty message."""
        error = PACCError("")
        assert error.message == ""
        assert str(error) == ""

    def test_none_context_values(self):
        """Test error with None values in context."""
        error = PACCError("test", context={"key": None})
        assert error.context["key"] is None

        error_dict = error.to_dict()
        assert error_dict["context"]["key"] is None

    def test_large_context(self):
        """Test error with large context dictionary."""
        large_context = {f"key_{i}": f"value_{i}" for i in range(1000)}
        error = PACCError("test", context=large_context)

        assert len(error.context) == 1000
        assert error.context["key_500"] == "value_500"

    def test_unicode_message(self):
        """Test error with unicode characters in message."""
        unicode_message = "Error: ñòñ-ASCII characters 中文 🚀"
        error = PACCError(unicode_message)

        assert error.message == unicode_message
        assert str(error) == unicode_message

    def test_special_characters_in_paths(self):
        """Test errors with special characters in file paths."""
        special_path = Path("/test/file with spaces & symbols!@#$.json")
        error = ValidationError("test", file_path=special_path)

        assert error.context["file_path"] == str(special_path)

    def test_very_long_message(self):
        """Test error with very long message."""
        long_message = "Error: " + "x" * 10000
        error = PACCError(long_message)

        assert len(error.message) == 10007  # "Error: " + 10000 x's
        assert error.message.endswith("x" * 100)  # Check it ends with x's

    def test_nested_context_structures(self):
        """Test error with nested dictionaries in context."""
        nested_context = {
            "level1": {"level2": {"level3": ["item1", "item2", "item3"]}},
            "simple": "value",
        }

        error = PACCError("test", context=nested_context)
        assert error.context["level1"]["level2"]["level3"] == ["item1", "item2", "item3"]

        # Should be serializable
        error_dict = error.to_dict()
        assert error_dict["context"]["level1"]["level2"]["level3"] == ["item1", "item2", "item3"]


# Performance and memory tests
@pytest.mark.performance
class TestErrorPerformance:
    """Test error handling performance."""

    def test_error_creation_performance(self):
        """Test that error creation is reasonably fast."""
        import time

        start_time = time.time()

        # Create 1000 errors
        for i in range(1000):
            error = ValidationError(f"Error {i}", line_number=i)

        end_time = time.time()
        duration = end_time - start_time

        # Should create 1000 errors in under 100ms
        assert duration < 0.1

    def test_error_serialization_performance(self):
        """Test that error serialization is reasonably fast."""
        import time

        # Create error with moderately large context
        context = {f"key_{i}": f"value_{i}" for i in range(100)}
        error = PACCError("test error", context=context)

        start_time = time.time()

        # Serialize 1000 times
        for _ in range(1000):
            error_dict = error.to_dict()

        end_time = time.time()
        duration = end_time - start_time

        # Should serialize 1000 times in under 100ms
        assert duration < 0.1
