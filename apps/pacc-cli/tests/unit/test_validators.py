"""Unit tests for pacc.validators.base module."""

import json
from pathlib import Path
from unittest.mock import patch, mock_open
import pytest

from pacc.validators.base import (
    ValidationError,
    ValidationResult, 
    BaseValidator
)


class TestValidationError:
    """Test ValidationError dataclass functionality."""
    
    def test_init_minimal(self):
        """Test ValidationError initialization with minimal parameters."""
        error = ValidationError(code="TEST_ERROR", message="Test message")
        
        assert error.code == "TEST_ERROR"
        assert error.message == "Test message"
        assert error.file_path is None
        assert error.line_number is None
        assert error.severity == "error"
        assert error.suggestion is None
    
    def test_init_full(self):
        """Test ValidationError initialization with all parameters."""
        error = ValidationError(
            code="TEST_ERROR",
            message="Test message",
            file_path="/test/file.json",
            line_number=42,
            severity="warning", 
            suggestion="Fix this issue"
        )
        
        assert error.code == "TEST_ERROR"
        assert error.message == "Test message"
        assert error.file_path == "/test/file.json"
        assert error.line_number == 42
        assert error.severity == "warning"
        assert error.suggestion == "Fix this issue"
    
    def test_str_minimal(self):
        """Test string representation with minimal information."""
        error = ValidationError(code="TEST_ERROR", message="Test message")
        
        result = str(error)
        assert "[ERROR] Test message" in result
        assert "file" not in result.lower()
    
    def test_str_with_file(self):
        """Test string representation with file path."""
        error = ValidationError(
            code="TEST_ERROR",
            message="Test message",
            file_path="/test/file.json"
        )
        
        result = str(error)
        assert "[ERROR] Test message in /test/file.json" in result
    
    def test_str_with_line_number(self):
        """Test string representation with line number."""
        error = ValidationError(
            code="TEST_ERROR",
            message="Test message",
            file_path="/test/file.json",
            line_number=42
        )
        
        result = str(error)
        assert "in /test/file.json at line 42" in result
    
    def test_str_with_suggestion(self):
        """Test string representation with suggestion."""
        error = ValidationError(
            code="TEST_ERROR",
            message="Test message",
            suggestion="Fix this issue"
        )
        
        result = str(error)
        assert "Suggestion: Fix this issue" in result
    
    def test_str_severity_cases(self):
        """Test string representation with different severity levels."""
        for severity in ["error", "warning", "info"]:
            error = ValidationError(
                code="TEST_ERROR",
                message="Test message",
                severity=severity
            )
            
            result = str(error)
            assert f"[{severity.upper()}]" in result


class TestValidationResult:
    """Test ValidationResult dataclass functionality."""
    
    def test_init_minimal(self):
        """Test ValidationResult initialization with minimal parameters."""
        result = ValidationResult(is_valid=True)
        
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.file_path is None
        assert result.extension_type is None
        assert result.metadata == {}
    
    def test_init_full(self):
        """Test ValidationResult initialization with all parameters."""
        errors = [ValidationError(code="ERR1", message="Error 1")]
        warnings = [ValidationError(code="WARN1", message="Warning 1", severity="warning")]
        metadata = {"test": "value"}
        
        result = ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            file_path="/test/file.json",
            extension_type="hooks",
            metadata=metadata
        )
        
        assert result.is_valid is False
        assert result.errors == errors
        assert result.warnings == warnings
        assert result.file_path == "/test/file.json"
        assert result.extension_type == "hooks"
        assert result.metadata == metadata
    
    def test_add_error(self):
        """Test adding an error to validation result."""
        result = ValidationResult(is_valid=True, file_path="/test/file.json")
        
        result.add_error(
            code="TEST_ERROR",
            message="Test error message",
            line_number=10,
            suggestion="Fix this"
        )
        
        assert result.is_valid is False  # Should become invalid
        assert len(result.errors) == 1
        
        error = result.errors[0]
        assert error.code == "TEST_ERROR"
        assert error.message == "Test error message"
        assert error.file_path == "/test/file.json"
        assert error.line_number == 10
        assert error.severity == "error"
        assert error.suggestion == "Fix this"
    
    def test_add_error_override_file_path(self):
        """Test adding error with explicit file path override."""
        result = ValidationResult(is_valid=True, file_path="/default/file.json")
        
        result.add_error(
            code="TEST_ERROR",
            message="Test error",
            file_path="/override/file.json"
        )
        
        error = result.errors[0]
        assert error.file_path == "/override/file.json"
    
    def test_add_warning(self):
        """Test adding a warning to validation result."""
        result = ValidationResult(is_valid=True)
        
        result.add_warning(
            code="TEST_WARNING",
            message="Test warning message",
            suggestion="Consider fixing"
        )
        
        assert result.is_valid is True  # Should remain valid
        assert len(result.warnings) == 1
        
        warning = result.warnings[0]
        assert warning.code == "TEST_WARNING"
        assert warning.message == "Test warning message"
        assert warning.severity == "warning"
        assert warning.suggestion == "Consider fixing"
    
    def test_add_info(self):
        """Test adding an info message to validation result."""
        result = ValidationResult(is_valid=True)
        
        result.add_info(
            code="TEST_INFO",
            message="Test info message"
        )
        
        assert result.is_valid is True  # Should remain valid
        assert len(result.warnings) == 1  # Info goes into warnings list
        
        info = result.warnings[0]
        assert info.code == "TEST_INFO"
        assert info.message == "Test info message"
        assert info.severity == "info"
    
    def test_all_issues_property(self):
        """Test all_issues property combines errors and warnings."""
        result = ValidationResult(is_valid=True)
        
        result.add_error("ERR1", "Error 1")
        result.add_warning("WARN1", "Warning 1")
        result.add_info("INFO1", "Info 1")
        
        all_issues = result.all_issues
        assert len(all_issues) == 3
        
        # Check that we have all types
        severities = {issue.severity for issue in all_issues}
        assert severities == {"error", "warning", "info"}
    
    def test_merge_results(self):
        """Test merging two validation results."""
        result1 = ValidationResult(is_valid=True, metadata={"key1": "value1"})
        result1.add_warning("WARN1", "Warning 1")
        
        result2 = ValidationResult(is_valid=False, metadata={"key2": "value2"})
        result2.add_error("ERR1", "Error 1")
        result2.add_warning("WARN2", "Warning 2")
        
        result1.merge(result2)
        
        assert result1.is_valid is False  # Should become invalid due to errors
        assert len(result1.errors) == 1
        assert len(result1.warnings) == 2
        assert result1.metadata == {"key1": "value1", "key2": "value2"}
    
    def test_merge_valid_results(self):
        """Test merging two valid results stays valid."""
        result1 = ValidationResult(is_valid=True)
        result1.add_warning("WARN1", "Warning 1")
        
        result2 = ValidationResult(is_valid=True)
        result2.add_warning("WARN2", "Warning 2")
        
        result1.merge(result2)
        
        assert result1.is_valid is True  # Should remain valid
        assert len(result1.warnings) == 2


class TestBaseValidator:
    """Test BaseValidator abstract base class."""
    
    def test_init_default(self):
        """Test BaseValidator initialization with defaults."""
        class TestValidator(BaseValidator):
            def get_extension_type(self):
                return "test"
            
            def validate_single(self, file_path):
                return ValidationResult(is_valid=True)
            
            def _find_extension_files(self, directory):
                return []
        
        validator = TestValidator()
        assert validator.max_file_size == 10 * 1024 * 1024  # 10MB
    
    def test_init_custom_size(self):
        """Test BaseValidator initialization with custom max file size."""
        class TestValidator(BaseValidator):
            def get_extension_type(self):
                return "test"
            
            def validate_single(self, file_path):
                return ValidationResult(is_valid=True)
            
            def _find_extension_files(self, directory):
                return []
        
        validator = TestValidator(max_file_size=1024)
        assert validator.max_file_size == 1024
    
    def test_validate_batch_success(self, temp_dir, mock_validator):
        """Test successful batch validation."""
        # Create test files
        file1 = temp_dir / "file1.test"
        file2 = temp_dir / "file2.test"
        file1.write_text("content1")
        file2.write_text("content2")
        
        results = mock_validator.validate_batch([file1, file2])
        
        assert len(results) == 2
        assert all(result.is_valid for result in results)
        assert all(result.extension_type == "test" for result in results)
    
    def test_validate_batch_with_exception(self, temp_dir, mock_validator):
        """Test batch validation handling exceptions."""
        # Create test file
        test_file = temp_dir / "test.file"
        test_file.write_text("content")
        
        # Mock validate_single to raise exception
        with patch.object(mock_validator, 'validate_single', side_effect=Exception("Test error")):
            results = mock_validator.validate_batch([test_file])
        
        assert len(results) == 1
        result = results[0]
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].code == "VALIDATION_EXCEPTION"
        assert "Test error" in result.errors[0].message
    
    def test_validate_directory_not_exists(self, temp_dir, mock_validator):
        """Test directory validation when directory doesn't exist."""
        nonexistent = temp_dir / "nonexistent"
        
        results = mock_validator.validate_directory(nonexistent)
        
        assert len(results) == 1
        result = results[0]
        assert result.is_valid is False
        assert result.errors[0].code == "DIRECTORY_NOT_FOUND"
    
    def test_validate_directory_not_a_directory(self, temp_dir, mock_validator):
        """Test directory validation when path is not a directory."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        
        results = mock_validator.validate_directory(test_file)
        
        assert len(results) == 1
        result = results[0]
        assert result.is_valid is False
        assert result.errors[0].code == "NOT_A_DIRECTORY"
    
    def test_validate_directory_no_extensions(self, temp_dir, mock_validator):
        """Test directory validation when no extensions found."""
        # Create directory with no test files
        test_dir = temp_dir / "empty"
        test_dir.mkdir()
        
        results = mock_validator.validate_directory(test_dir)
        
        assert len(results) == 1
        result = results[0]
        assert result.is_valid is False
        assert result.errors[0].code == "NO_EXTENSIONS_FOUND"
    
    def test_validate_directory_success(self, temp_dir, mock_validator):
        """Test successful directory validation."""
        # Create test files
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()
        (test_dir / "file1.test").write_text("content1")
        (test_dir / "file2.test").write_text("content2")
        
        # Mock _find_extension_files to return our test files
        test_files = [test_dir / "file1.test", test_dir / "file2.test"]
        with patch.object(mock_validator, '_find_extension_files', return_value=test_files):
            results = mock_validator.validate_directory(test_dir)
        
        assert len(results) == 2
        assert all(result.is_valid for result in results)
    
    def test_validate_file_accessibility_not_exists(self, temp_dir, mock_validator):
        """Test file accessibility validation for non-existent file."""
        nonexistent = temp_dir / "nonexistent.txt"
        
        error = mock_validator._validate_file_accessibility(nonexistent)
        
        assert error is not None
        assert error.code == "FILE_NOT_FOUND"
    
    def test_validate_file_accessibility_not_a_file(self, temp_dir, mock_validator):
        """Test file accessibility validation for directory."""
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()
        
        error = mock_validator._validate_file_accessibility(test_dir)
        
        assert error is not None
        assert error.code == "NOT_A_FILE"
    
    def test_validate_file_accessibility_too_large(self, temp_dir, mock_validator):
        """Test file accessibility validation for oversized file."""
        large_file = temp_dir / "large.txt"
        large_file.write_text("x" * (mock_validator.max_file_size + 1))
        
        error = mock_validator._validate_file_accessibility(large_file)
        
        assert error is not None
        assert error.code == "FILE_TOO_LARGE"
    
    def test_validate_file_accessibility_os_error(self, temp_dir, mock_validator):
        """Test file accessibility validation with OS error."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        
        with patch('pathlib.Path.stat', side_effect=OSError("Test OS error")):
            error = mock_validator._validate_file_accessibility(test_file)
        
        assert error is not None
        assert error.code == "FILE_ACCESS_ERROR"
    
    def test_validate_file_accessibility_success(self, temp_dir, mock_validator):
        """Test successful file accessibility validation."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        
        error = mock_validator._validate_file_accessibility(test_file)
        
        assert error is None
    
    def test_validate_json_syntax_valid(self, temp_dir, mock_validator):
        """Test JSON syntax validation with valid JSON."""
        json_file = temp_dir / "valid.json"
        test_data = {"name": "test", "version": "1.0.0"}
        
        with open(json_file, 'w') as f:
            json.dump(test_data, f)
        
        error, data = mock_validator._validate_json_syntax(json_file)
        
        assert error is None
        assert data == test_data
    
    def test_validate_json_syntax_invalid(self, temp_dir, mock_validator):
        """Test JSON syntax validation with invalid JSON."""
        json_file = temp_dir / "invalid.json"
        json_file.write_text('{"invalid": json, syntax}')
        
        error, data = mock_validator._validate_json_syntax(json_file)
        
        assert error is not None
        assert error.code == "INVALID_JSON"
        assert data is None
    
    def test_validate_json_syntax_encoding_error(self, temp_dir, mock_validator):
        """Test JSON syntax validation with encoding error."""
        json_file = temp_dir / "encoding_error.json"
        json_file.write_text("test")
        
        with patch('builtins.open', side_effect=UnicodeDecodeError('utf-8', b'', 0, 1, "invalid")):
            error, data = mock_validator._validate_json_syntax(json_file)
        
        assert error is not None
        assert error.code == "ENCODING_ERROR"
        assert data is None
    
    def test_validate_json_syntax_file_read_error(self, temp_dir, mock_validator):
        """Test JSON syntax validation with file read error."""
        json_file = temp_dir / "test.json"
        json_file.write_text('{"test": true}')
        
        with patch('builtins.open', side_effect=Exception("File read error")):
            error, data = mock_validator._validate_json_syntax(json_file)
        
        assert error is not None
        assert error.code == "FILE_READ_ERROR"
        assert data is None
    
    def test_validate_required_fields_all_present(self, mock_validator):
        """Test required fields validation when all fields are present."""
        data = {"name": "test", "version": "1.0.0", "description": "test desc"}
        required = ["name", "version", "description"]
        
        errors = mock_validator._validate_required_fields(data, required, "/test/file.json")
        
        assert len(errors) == 0
    
    def test_validate_required_fields_missing(self, mock_validator):
        """Test required fields validation with missing fields."""
        data = {"name": "test"}
        required = ["name", "version", "description"]
        
        errors = mock_validator._validate_required_fields(data, required, "/test/file.json")
        
        assert len(errors) == 2
        missing_fields = {error.message for error in errors}
        assert any("version" in msg for msg in missing_fields)
        assert any("description" in msg for msg in missing_fields)
        assert all(error.code == "MISSING_REQUIRED_FIELD" for error in errors)
    
    def test_validate_required_fields_null_values(self, mock_validator):
        """Test required fields validation with null values."""
        data = {"name": "test", "version": None, "description": "test"}
        required = ["name", "version", "description"]
        
        errors = mock_validator._validate_required_fields(data, required, "/test/file.json")
        
        assert len(errors) == 1
        assert errors[0].code == "NULL_REQUIRED_FIELD"
        assert "version" in errors[0].message
    
    def test_validate_field_type_valid(self, mock_validator):
        """Test field type validation with correct type."""
        data = {"name": "test", "version": "1.0.0", "count": 42}
        
        # Test string field
        error = mock_validator._validate_field_type(data, "name", str, "/test/file.json")
        assert error is None
        
        # Test int field
        error = mock_validator._validate_field_type(data, "count", int, "/test/file.json")
        assert error is None
    
    def test_validate_field_type_invalid(self, mock_validator):
        """Test field type validation with incorrect type."""
        data = {"name": "test", "count": "not_a_number"}
        
        error = mock_validator._validate_field_type(data, "count", int, "/test/file.json")
        
        assert error is not None
        assert error.code == "INVALID_FIELD_TYPE"
        assert "int" in error.message
        assert "str" in error.message
    
    def test_validate_field_type_missing_required(self, mock_validator):
        """Test field type validation with missing required field."""
        data = {"name": "test"}
        
        error = mock_validator._validate_field_type(data, "version", str, "/test/file.json", required=True)
        
        assert error is not None
        assert error.code == "MISSING_REQUIRED_FIELD"
    
    def test_validate_field_type_missing_optional(self, mock_validator):
        """Test field type validation with missing optional field."""
        data = {"name": "test"}
        
        error = mock_validator._validate_field_type(data, "description", str, "/test/file.json", required=False)
        
        assert error is None
    
    def test_validate_field_type_null_optional(self, mock_validator):
        """Test field type validation with null optional field."""
        data = {"name": "test", "description": None}
        
        error = mock_validator._validate_field_type(data, "description", str, "/test/file.json", required=False)
        
        assert error is None


# Integration tests for validation components
class TestValidationIntegration:
    """Integration tests for validation components working together."""
    
    def test_complete_validation_flow(self, temp_dir):
        """Test complete validation flow with errors and warnings."""
        class TestValidator(BaseValidator):
            def get_extension_type(self):
                return "test"
            
            def validate_single(self, file_path):
                result = ValidationResult(
                    is_valid=True,
                    file_path=str(file_path),
                    extension_type=self.get_extension_type()
                )
                
                # Add a warning for demonstration
                result.add_warning(
                    "TEST_WARNING",
                    "This is a test warning",
                    suggestion="Consider updating the file"
                )
                
                return result
            
            def _find_extension_files(self, directory):
                return list(directory.glob("*.test"))
        
        # Create test files
        test_dir = temp_dir / "test_validation"
        test_dir.mkdir()
        (test_dir / "file1.test").write_text("content1")
        (test_dir / "file2.test").write_text("content2")
        
        validator = TestValidator()
        results = validator.validate_directory(test_dir)
        
        assert len(results) == 2
        assert all(result.is_valid for result in results)
        assert all(len(result.warnings) == 1 for result in results)
        assert all(result.extension_type == "test" for result in results)
    
    def test_error_accumulation(self, temp_dir):
        """Test that errors accumulate correctly across validations."""
        class ErrorValidator(BaseValidator):
            def get_extension_type(self):
                return "error"
            
            def validate_single(self, file_path):
                result = ValidationResult(
                    is_valid=True,
                    file_path=str(file_path),
                    extension_type=self.get_extension_type()
                )
                
                # Add different types of issues based on filename
                if "error" in file_path.name:
                    result.add_error("CRITICAL_ERROR", "This file has critical errors")
                if "warning" in file_path.name:
                    result.add_warning("MINOR_WARNING", "This file has warnings")
                if "info" in file_path.name:
                    result.add_info("INFO_MESSAGE", "This file has info messages")
                
                return result
            
            def _find_extension_files(self, directory):
                return list(directory.glob("*.error"))
        
        # Create test files
        test_dir = temp_dir / "error_test"
        test_dir.mkdir()
        (test_dir / "error_file.error").write_text("content")
        (test_dir / "warning_file.error").write_text("content")
        (test_dir / "info_file.error").write_text("content")
        (test_dir / "normal_file.error").write_text("content")
        
        validator = ErrorValidator()
        results = validator.validate_directory(test_dir)
        
        # Count different types of issues
        total_errors = sum(len(result.errors) for result in results)
        total_warnings = sum(len(result.warnings) for result in results)
        
        assert total_errors == 1  # Only error_file should have errors
        assert total_warnings == 2  # warning_file and info_file should have warnings
        
        # Check validity
        valid_results = [r for r in results if r.is_valid]
        invalid_results = [r for r in results if not r.is_valid]
        
        assert len(valid_results) == 3  # 3 files without errors
        assert len(invalid_results) == 1  # 1 file with errors


# Edge case and error handling tests
class TestValidationEdgeCases:
    """Test edge cases and error handling in validation."""
    
    def test_empty_validation_result(self):
        """Test behavior of empty validation result."""
        result = ValidationResult(is_valid=True)
        
        assert len(result.all_issues) == 0
        assert result.is_valid is True
        
        # Merging with empty result should not change anything
        other = ValidationResult(is_valid=True)
        result.merge(other)
        
        assert result.is_valid is True
        assert len(result.all_issues) == 0
    
    def test_validation_error_edge_cases(self):
        """Test ValidationError with edge case inputs."""
        # Test with empty strings
        error = ValidationError(code="", message="")
        assert error.code == ""
        assert error.message == ""
        
        # Test with very long messages
        long_message = "x" * 1000
        error = ValidationError(code="LONG", message=long_message)
        assert len(error.message) == 1000
        assert long_message in str(error)
    
    def test_validation_result_edge_cases(self):
        """Test ValidationResult with edge case inputs."""
        # Test with many errors
        result = ValidationResult(is_valid=True)
        for i in range(100):
            result.add_error(f"ERROR_{i}", f"Error message {i}")
        
        assert len(result.errors) == 100
        assert result.is_valid is False
        assert len(result.all_issues) == 100