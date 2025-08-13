"""Base validation classes for PACC."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ValidationIssue:
    """Represents a validation issue found in a file."""
    
    severity: str  # 'error', 'warning', 'info'
    message: str
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    rule_id: Optional[str] = None
    context: Optional[str] = None
    
    def __str__(self) -> str:
        """Return string representation of validation issue."""
        location = ""
        if self.line_number is not None:
            location = f" (line {self.line_number}"
            if self.column_number is not None:
                location += f", col {self.column_number}"
            location += ")"
        
        rule_info = f" [{self.rule_id}]" if self.rule_id else ""
        
        return f"{self.severity.upper()}: {self.message}{location}{rule_info}"


@dataclass
class ValidationResult:
    """Result of validation operation."""
    
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    file_path: Optional[Path] = None
    validator_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_errors(self) -> bool:
        """Check if result has error-level issues."""
        return any(issue.severity == 'error' for issue in self.issues)
    
    @property
    def has_warnings(self) -> bool:
        """Check if result has warning-level issues."""
        return any(issue.severity == 'warning' for issue in self.issues)
    
    @property
    def error_count(self) -> int:
        """Get count of error-level issues."""
        return len([issue for issue in self.issues if issue.severity == 'error'])
    
    @property
    def warning_count(self) -> int:
        """Get count of warning-level issues."""
        return len([issue for issue in self.issues if issue.severity == 'warning'])
    
    def add_error(
        self, 
        message: str, 
        line_number: Optional[int] = None,
        column_number: Optional[int] = None,
        rule_id: Optional[str] = None,
        context: Optional[str] = None
    ) -> None:
        """Add an error-level issue.
        
        Args:
            message: Error message
            line_number: Line number where error occurred
            column_number: Column number where error occurred
            rule_id: ID of the validation rule that triggered
            context: Additional context about the error
        """
        issue = ValidationIssue(
            severity='error',
            message=message,
            line_number=line_number,
            column_number=column_number,
            rule_id=rule_id,
            context=context
        )
        self.issues.append(issue)
        self.is_valid = False
    
    def add_warning(
        self, 
        message: str, 
        line_number: Optional[int] = None,
        column_number: Optional[int] = None,
        rule_id: Optional[str] = None,
        context: Optional[str] = None
    ) -> None:
        """Add a warning-level issue.
        
        Args:
            message: Warning message
            line_number: Line number where warning occurred
            column_number: Column number where warning occurred
            rule_id: ID of the validation rule that triggered
            context: Additional context about the warning
        """
        issue = ValidationIssue(
            severity='warning',
            message=message,
            line_number=line_number,
            column_number=column_number,
            rule_id=rule_id,
            context=context
        )
        self.issues.append(issue)
    
    def add_info(
        self, 
        message: str, 
        line_number: Optional[int] = None,
        column_number: Optional[int] = None,
        rule_id: Optional[str] = None,
        context: Optional[str] = None
    ) -> None:
        """Add an info-level issue.
        
        Args:
            message: Info message
            line_number: Line number where info occurred
            column_number: Column number where info occurred
            rule_id: ID of the validation rule that triggered
            context: Additional context about the info
        """
        issue = ValidationIssue(
            severity='info',
            message=message,
            line_number=line_number,
            column_number=column_number,
            rule_id=rule_id,
            context=context
        )
        self.issues.append(issue)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert validation result to dictionary.
        
        Returns:
            Dictionary representation of validation result
        """
        return {
            'is_valid': self.is_valid,
            'file_path': str(self.file_path) if self.file_path else None,
            'validator_name': self.validator_name,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'issues': [
                {
                    'severity': issue.severity,
                    'message': issue.message,
                    'line_number': issue.line_number,
                    'column_number': issue.column_number,
                    'rule_id': issue.rule_id,
                    'context': issue.context,
                }
                for issue in self.issues
            ],
            'metadata': self.metadata,
        }


class BaseValidator(ABC):
    """Base class for all validators."""
    
    def __init__(self, name: Optional[str] = None):
        """Initialize validator.
        
        Args:
            name: Optional name for the validator
        """
        self.name = name or self.__class__.__name__
        self.rules: Dict[str, bool] = {}
    
    @abstractmethod
    def validate_content(self, content: str, file_path: Optional[Path] = None) -> ValidationResult:
        """Validate file content.
        
        Args:
            content: File content to validate
            file_path: Optional path to the file being validated
            
        Returns:
            ValidationResult with any issues found
        """
        pass
    
    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a file.
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            ValidationResult with any issues found
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.validate_content(content, file_path)
        except UnicodeDecodeError:
            result = ValidationResult(is_valid=False, file_path=file_path, validator_name=self.name)
            result.add_error(f"File is not valid UTF-8 text", rule_id="ENCODING_ERROR")
            return result
        except OSError as e:
            result = ValidationResult(is_valid=False, file_path=file_path, validator_name=self.name)
            result.add_error(f"Cannot read file: {e}", rule_id="FILE_READ_ERROR")
            return result
    
    def enable_rule(self, rule_id: str) -> None:
        """Enable a validation rule.
        
        Args:
            rule_id: ID of the rule to enable
        """
        self.rules[rule_id] = True
    
    def disable_rule(self, rule_id: str) -> None:
        """Disable a validation rule.
        
        Args:
            rule_id: ID of the rule to disable
        """
        self.rules[rule_id] = False
    
    def is_rule_enabled(self, rule_id: str) -> bool:
        """Check if a validation rule is enabled.
        
        Args:
            rule_id: ID of the rule to check
            
        Returns:
            True if rule is enabled, False otherwise
        """
        return self.rules.get(rule_id, True)  # Default to enabled
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Get list of file extensions this validator supports.
        
        Returns:
            List of file extensions (with dots, e.g., ['.json', '.jsonc'])
        """
        pass
    
    def can_validate(self, file_path: Path) -> bool:
        """Check if this validator can validate the given file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if validator can handle this file type
        """
        return file_path.suffix.lower() in self.get_supported_extensions()


class CompositeValidator:
    """Validator that combines multiple validators."""
    
    def __init__(self, validators: List[BaseValidator]):
        """Initialize composite validator.
        
        Args:
            validators: List of validators to use
        """
        self.validators = validators
    
    def validate_file(self, file_path: Path) -> List[ValidationResult]:
        """Validate file with all applicable validators.
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            List of validation results from all applicable validators
        """
        results = []
        for validator in self.validators:
            if validator.can_validate(file_path):
                result = validator.validate_file(file_path)
                results.append(result)
        return results
    
    def validate_content(
        self, 
        content: str, 
        file_path: Optional[Path] = None,
        validator_types: Optional[List[str]] = None
    ) -> List[ValidationResult]:
        """Validate content with specified validators.
        
        Args:
            content: Content to validate
            file_path: Optional file path for context
            validator_types: Optional list of validator types to use
            
        Returns:
            List of validation results
        """
        results = []
        for validator in self.validators:
            # If specific validator types requested, filter by name
            if validator_types and validator.name not in validator_types:
                continue
            
            # If file path provided, check if validator can handle it
            if file_path and not validator.can_validate(file_path):
                continue
            
            result = validator.validate_content(content, file_path)
            results.append(result)
        
        return results
    
    def get_validator_by_name(self, name: str) -> Optional[BaseValidator]:
        """Get validator by name.
        
        Args:
            name: Name of the validator
            
        Returns:
            Validator instance or None if not found
        """
        for validator in self.validators:
            if validator.name == name:
                return validator
        return None
    
    def get_validators_for_file(self, file_path: Path) -> List[BaseValidator]:
        """Get all validators that can handle the given file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of applicable validators
        """
        return [v for v in self.validators if v.can_validate(file_path)]