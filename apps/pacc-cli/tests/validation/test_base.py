"""Tests for validation base classes."""

import unittest
from pathlib import Path
import tempfile

from pacc.validation.base import ValidationResult, ValidationIssue, BaseValidator, CompositeValidator


class MockValidator(BaseValidator):
    """Mock validator for testing."""
    
    def validate_content(self, content: str, file_path=None) -> ValidationResult:
        """Mock validation that always passes."""
        result = ValidationResult(is_valid=True, file_path=file_path, validator_name=self.name)
        
        if "error" in content.lower():
            result.add_error("Mock error found", line_number=1, rule_id="MOCK_ERROR")
        
        if "warning" in content.lower():
            result.add_warning("Mock warning found", line_number=2, rule_id="MOCK_WARNING")
        
        return result
    
    def get_supported_extensions(self):
        """Return mock extensions."""
        return ['.mock', '.test']


class TestValidationIssue(unittest.TestCase):
    """Test cases for ValidationIssue."""
    
    def test_issue_creation(self):
        """Test creation of validation issue."""
        issue = ValidationIssue(
            severity='error',
            message='Test error',
            line_number=1,
            column_number=5,
            rule_id='TEST_RULE'
        )
        
        self.assertEqual(issue.severity, 'error')
        self.assertEqual(issue.message, 'Test error')
        self.assertEqual(issue.line_number, 1)
        self.assertEqual(issue.column_number, 5)
        self.assertEqual(issue.rule_id, 'TEST_RULE')
    
    def test_issue_string_representation(self):
        """Test string representation of validation issue."""
        issue = ValidationIssue(
            severity='error',
            message='Test error',
            line_number=1,
            column_number=5,
            rule_id='TEST_RULE'
        )
        
        str_repr = str(issue)
        self.assertIn('ERROR', str_repr)
        self.assertIn('Test error', str_repr)
        self.assertIn('line 1', str_repr)
        self.assertIn('col 5', str_repr)
        self.assertIn('[TEST_RULE]', str_repr)


class TestValidationResult(unittest.TestCase):
    """Test cases for ValidationResult."""
    
    def test_result_creation(self):
        """Test creation of validation result."""
        result = ValidationResult(is_valid=True)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.issues), 0)
        self.assertFalse(result.has_errors)
        self.assertFalse(result.has_warnings)
    
    def test_add_error(self):
        """Test adding error to result."""
        result = ValidationResult(is_valid=True)
        result.add_error("Test error", line_number=1, rule_id="TEST_ERROR")
        
        self.assertFalse(result.is_valid)  # Should become false when error added
        self.assertTrue(result.has_errors)
        self.assertEqual(result.error_count, 1)
        self.assertEqual(result.issues[0].severity, 'error')
    
    def test_add_warning(self):
        """Test adding warning to result."""
        result = ValidationResult(is_valid=True)
        result.add_warning("Test warning", line_number=2, rule_id="TEST_WARNING")
        
        self.assertTrue(result.is_valid)  # Should remain true for warnings
        self.assertTrue(result.has_warnings)
        self.assertEqual(result.warning_count, 1)
        self.assertEqual(result.issues[0].severity, 'warning')
    
    def test_add_info(self):
        """Test adding info to result."""
        result = ValidationResult(is_valid=True)
        result.add_info("Test info", rule_id="TEST_INFO")
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].severity, 'info')
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ValidationResult(is_valid=True, validator_name="TestValidator")
        result.add_error("Test error", line_number=1)
        result.add_warning("Test warning", line_number=2)
        
        result_dict = result.to_dict()
        
        self.assertIn('is_valid', result_dict)
        self.assertIn('validator_name', result_dict)
        self.assertIn('error_count', result_dict)
        self.assertIn('warning_count', result_dict)
        self.assertIn('issues', result_dict)
        
        self.assertEqual(result_dict['error_count'], 1)
        self.assertEqual(result_dict['warning_count'], 1)
        self.assertEqual(len(result_dict['issues']), 2)


class TestBaseValidator(unittest.TestCase):
    """Test cases for BaseValidator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = MockValidator()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = Path(self.temp_dir) / "test.mock"
        self.temp_file.write_text("test content with error and warning")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_file.exists():
            self.temp_file.unlink()
        import os
        os.rmdir(self.temp_dir)
    
    def test_validate_content(self):
        """Test content validation."""
        result = self.validator.validate_content("normal content")
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.issues), 0)
        
        result = self.validator.validate_content("content with error")
        self.assertFalse(result.is_valid)
        self.assertTrue(result.has_errors)
    
    def test_validate_file(self):
        """Test file validation."""
        result = self.validator.validate_file(self.temp_file)
        self.assertFalse(result.is_valid)  # File contains "error" and "warning"
        self.assertTrue(result.has_errors)
        self.assertTrue(result.has_warnings)
        self.assertEqual(result.file_path, self.temp_file)
    
    def test_rule_management(self):
        """Test validation rule management."""
        self.assertTrue(self.validator.is_rule_enabled("DEFAULT_RULE"))
        
        self.validator.disable_rule("TEST_RULE")
        self.assertFalse(self.validator.is_rule_enabled("TEST_RULE"))
        
        self.validator.enable_rule("TEST_RULE")
        self.assertTrue(self.validator.is_rule_enabled("TEST_RULE"))
    
    def test_can_validate(self):
        """Test file type validation."""
        mock_file = Path("test.mock")
        unsupported_file = Path("test.unsupported")
        
        self.assertTrue(self.validator.can_validate(mock_file))
        self.assertFalse(self.validator.can_validate(unsupported_file))
    
    def test_validate_nonexistent_file(self):
        """Test validation of nonexistent file."""
        nonexistent = Path(self.temp_dir) / "nonexistent.mock"
        result = self.validator.validate_file(nonexistent)
        
        self.assertFalse(result.is_valid)
        self.assertTrue(result.has_errors)
        self.assertIn("Cannot read file", result.issues[0].message)


class TestCompositeValidator(unittest.TestCase):
    """Test cases for CompositeValidator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator1 = MockValidator("Validator1")
        self.validator2 = MockValidator("Validator2")
        self.composite = CompositeValidator([self.validator1, self.validator2])
        
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = Path(self.temp_dir) / "test.mock"
        self.temp_file.write_text("test content")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_file.exists():
            self.temp_file.unlink()
        import os
        os.rmdir(self.temp_dir)
    
    def test_validate_file_with_multiple_validators(self):
        """Test file validation with multiple validators."""
        results = self.composite.validate_file(self.temp_file)
        
        # Both validators should run since they both support .mock files
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].validator_name, "Validator1")
        self.assertEqual(results[1].validator_name, "Validator2")
    
    def test_validate_content_with_specific_validators(self):
        """Test content validation with specific validator types."""
        results = self.composite.validate_content(
            "test content", 
            validator_types=["Validator1"]
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].validator_name, "Validator1")
    
    def test_get_validator_by_name(self):
        """Test getting validator by name."""
        validator = self.composite.get_validator_by_name("Validator1")
        self.assertIsNotNone(validator)
        self.assertEqual(validator.name, "Validator1")
        
        validator = self.composite.get_validator_by_name("NonExistent")
        self.assertIsNone(validator)
    
    def test_get_validators_for_file(self):
        """Test getting applicable validators for file."""
        validators = self.composite.get_validators_for_file(self.temp_file)
        self.assertEqual(len(validators), 2)  # Both support .mock extension
        
        unsupported_file = Path("test.unsupported")
        validators = self.composite.get_validators_for_file(unsupported_file)
        self.assertEqual(len(validators), 0)  # Neither supports .unsupported


if __name__ == '__main__':
    unittest.main()