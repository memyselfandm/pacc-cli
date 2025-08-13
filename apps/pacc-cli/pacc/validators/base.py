"""Base validator classes and validation result types."""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


@dataclass
class ValidationError:
    """Represents a validation error with detailed information."""
    
    code: str
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    severity: str = "error"  # error, warning, info
    suggestion: Optional[str] = None
    
    def __str__(self) -> str:
        """Human-readable error message."""
        location = ""
        if self.file_path:
            location = f"in {self.file_path}"
            if self.line_number:
                location += f" at line {self.line_number}"
        
        result = f"[{self.severity.upper()}] {self.message}"
        if location:
            result += f" {location}"
        if self.suggestion:
            result += f"\nSuggestion: {self.suggestion}"
        
        return result


@dataclass
class ValidationResult:
    """Represents the result of a validation operation."""
    
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    file_path: Optional[str] = None
    extension_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, code: str, message: str, file_path: Optional[str] = None,
                  line_number: Optional[int] = None, suggestion: Optional[str] = None) -> None:
        """Add an error to the validation result."""
        self.errors.append(ValidationError(
            code=code, 
            message=message,
            file_path=file_path or self.file_path,
            line_number=line_number,
            severity="error",
            suggestion=suggestion
        ))
        self.is_valid = False
    
    def add_warning(self, code: str, message: str, file_path: Optional[str] = None,
                    line_number: Optional[int] = None, suggestion: Optional[str] = None) -> None:
        """Add a warning to the validation result."""
        self.warnings.append(ValidationError(
            code=code,
            message=message, 
            file_path=file_path or self.file_path,
            line_number=line_number,
            severity="warning",
            suggestion=suggestion
        ))
    
    def add_info(self, code: str, message: str, file_path: Optional[str] = None,
                 line_number: Optional[int] = None, suggestion: Optional[str] = None) -> None:
        """Add an info message to the validation result."""
        self.warnings.append(ValidationError(
            code=code,
            message=message,
            file_path=file_path or self.file_path, 
            line_number=line_number,
            severity="info",
            suggestion=suggestion
        ))
    
    @property
    def all_issues(self) -> List[ValidationError]:
        """Get all errors and warnings combined."""
        return self.errors + self.warnings
    
    def merge(self, other: 'ValidationResult') -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if other.errors:
            self.is_valid = False
        self.metadata.update(other.metadata)


class BaseValidator(ABC):
    """Base class for all extension validators."""
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024):  # 10MB default
        """Initialize validator with optional configuration."""
        self.max_file_size = max_file_size
    
    @abstractmethod
    def get_extension_type(self) -> str:
        """Return the extension type this validator handles."""
        pass
    
    @abstractmethod
    def validate_single(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate a single extension file."""
        pass
    
    def validate_batch(self, file_paths: List[Union[str, Path]]) -> List[ValidationResult]:
        """Validate multiple extension files."""
        results = []
        for file_path in file_paths:
            try:
                result = self.validate_single(file_path)
                results.append(result)
            except Exception as e:
                result = ValidationResult(
                    is_valid=False,
                    file_path=str(file_path),
                    extension_type=self.get_extension_type()
                )
                result.add_error(
                    "VALIDATION_EXCEPTION",
                    f"Unexpected error during validation: {str(e)}",
                    suggestion="Check file format and accessibility"
                )
                results.append(result)
        return results
    
    def validate_directory(self, directory_path: Union[str, Path]) -> List[ValidationResult]:
        """Validate all valid extension files in a directory."""
        directory = Path(directory_path)
        if not directory.exists():
            result = ValidationResult(
                is_valid=False,
                file_path=str(directory),
                extension_type=self.get_extension_type()
            )
            result.add_error(
                "DIRECTORY_NOT_FOUND",
                f"Directory does not exist: {directory}",
                suggestion="Check the directory path"
            )
            return [result]
        
        if not directory.is_dir():
            result = ValidationResult(
                is_valid=False,
                file_path=str(directory),
                extension_type=self.get_extension_type()
            )
            result.add_error(
                "NOT_A_DIRECTORY",
                f"Path is not a directory: {directory}",
                suggestion="Provide a directory path"
            )
            return [result]
        
        # Find valid extension files
        extension_files = self._find_extension_files(directory)
        if not extension_files:
            result = ValidationResult(
                is_valid=False,
                file_path=str(directory),
                extension_type=self.get_extension_type()
            )
            result.add_error(
                "NO_EXTENSIONS_FOUND",
                f"No {self.get_extension_type()} extensions found in directory",
                suggestion=f"Check that the directory contains valid {self.get_extension_type()} files"
            )
            return [result]
        
        return self.validate_batch(extension_files)
    
    @abstractmethod
    def _find_extension_files(self, directory: Path) -> List[Path]:
        """Find extension files of this type in the given directory."""
        pass
    
    def _validate_file_accessibility(self, file_path: Path) -> Optional[ValidationError]:
        """Validate that a file can be accessed and is not too large."""
        if not file_path.exists():
            return ValidationError(
                code="FILE_NOT_FOUND",
                message=f"File does not exist: {file_path}",
                file_path=str(file_path),
                suggestion="Check the file path"
            )
        
        if not file_path.is_file():
            return ValidationError(
                code="NOT_A_FILE",
                message=f"Path is not a file: {file_path}",
                file_path=str(file_path),
                suggestion="Provide a file path, not a directory"
            )
        
        try:
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                return ValidationError(
                    code="FILE_TOO_LARGE",
                    message=f"File too large: {file_size} bytes (max: {self.max_file_size})",
                    file_path=str(file_path),
                    suggestion="Reduce file size or increase max_file_size limit"
                )
        except OSError as e:
            return ValidationError(
                code="FILE_ACCESS_ERROR",
                message=f"Cannot access file: {e}",
                file_path=str(file_path),
                suggestion="Check file permissions and availability"
            )
        
        return None
    
    def _validate_json_syntax(self, file_path: Path) -> tuple[Optional[ValidationError], Optional[Dict[str, Any]]]:
        """Validate JSON syntax and return parsed data."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return None, data
        except json.JSONDecodeError as e:
            return ValidationError(
                code="INVALID_JSON",
                message=f"Invalid JSON syntax: {e.msg}",
                file_path=str(file_path),
                line_number=e.lineno,
                suggestion="Fix JSON syntax errors"
            ), None
        except UnicodeDecodeError as e:
            return ValidationError(
                code="ENCODING_ERROR",
                message=f"File encoding error: {e}",
                file_path=str(file_path),
                suggestion="Ensure file is saved with UTF-8 encoding"
            ), None
        except Exception as e:
            return ValidationError(
                code="FILE_READ_ERROR",
                message=f"Cannot read file: {e}",
                file_path=str(file_path),
                suggestion="Check file permissions and format"
            ), None
    
    def _validate_required_fields(self, data: Dict[str, Any], required_fields: List[str], 
                                  file_path: str) -> List[ValidationError]:
        """Validate that required fields are present in data."""
        errors = []
        for field in required_fields:
            if field not in data:
                errors.append(ValidationError(
                    code="MISSING_REQUIRED_FIELD",
                    message=f"Missing required field: '{field}'",
                    file_path=file_path,
                    suggestion=f"Add the '{field}' field to the configuration"
                ))
            elif data[field] is None:
                errors.append(ValidationError(
                    code="NULL_REQUIRED_FIELD",
                    message=f"Required field '{field}' cannot be null",
                    file_path=file_path,
                    suggestion=f"Provide a value for the '{field}' field"
                ))
        return errors
    
    def _validate_field_type(self, data: Dict[str, Any], field: str, expected_type: type,
                           file_path: str, required: bool = True) -> Optional[ValidationError]:
        """Validate that a field has the expected type."""
        if field not in data:
            if required:
                return ValidationError(
                    code="MISSING_REQUIRED_FIELD",
                    message=f"Missing required field: '{field}'",
                    file_path=file_path,
                    suggestion=f"Add the '{field}' field to the configuration"
                )
            return None
        
        value = data[field]
        if value is None and not required:
            return None
        
        if not isinstance(value, expected_type):
            return ValidationError(
                code="INVALID_FIELD_TYPE",
                message=f"Field '{field}' must be of type {expected_type.__name__}, got {type(value).__name__}",
                file_path=file_path,
                suggestion=f"Change '{field}' to a {expected_type.__name__} value"
            )
        
        return None