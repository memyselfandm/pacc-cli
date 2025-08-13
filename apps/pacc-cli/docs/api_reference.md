# PACC API Reference

This document provides comprehensive API documentation for all public interfaces in PACC (Package manager for Claude Code).

## Table of Contents

1. [Core Utilities](#core-utilities)
2. [Validation Framework](#validation-framework)
3. [Error Handling](#error-handling)
4. [Security Components](#security-components)
5. [Usage Examples](#usage-examples)
6. [Extension Points](#extension-points)

## Core Utilities

### FilePathValidator

Validates file paths for security and accessibility.

#### Constructor

```python
FilePathValidator(allowed_extensions: Optional[Set[str]] = None)
```

**Parameters:**
- `allowed_extensions` (Optional[Set[str]]): Set of allowed file extensions (with dots, e.g., {'.json', '.yaml'})

#### Methods

##### is_valid_path

```python
is_valid_path(path: Union[str, Path]) -> bool
```

Check if path is valid and safe to access.

**Parameters:**
- `path` (Union[str, Path]): Path to validate

**Returns:**
- `bool`: True if path is valid and safe

**Example:**
```python
validator = FilePathValidator()
if validator.is_valid_path("/path/to/file.json"):
    # Safe to process
    pass
```

##### validate_extension

```python
validate_extension(path: Union[str, Path], extensions: Set[str]) -> bool
```

Validate file has one of the allowed extensions.

**Parameters:**
- `path` (Union[str, Path]): Path to check
- `extensions` (Set[str]): Set of allowed extensions (with dots)

**Returns:**
- `bool`: True if extension is allowed

##### is_safe_directory

```python
is_safe_directory(path: Union[str, Path]) -> bool
```

Check if directory is safe to scan.

**Parameters:**
- `path` (Union[str, Path]): Directory path to check

**Returns:**
- `bool`: True if directory is safe to scan

### PathNormalizer

Normalizes file paths for cross-platform compatibility.

#### Methods

##### normalize (static)

```python
@staticmethod
normalize(path: Union[str, Path]) -> Path
```

Normalize path for current platform.

**Parameters:**
- `path` (Union[str, Path]): Path to normalize

**Returns:**
- `Path`: Normalized Path object

**Example:**
```python
normalized = PathNormalizer.normalize("./relative/path")
print(normalized)  # Absolute path
```

##### to_posix (static)

```python
@staticmethod
to_posix(path: Union[str, Path]) -> str
```

Convert path to POSIX format.

**Parameters:**
- `path` (Union[str, Path]): Path to convert

**Returns:**
- `str`: POSIX-style path string

##### relative_to (static)

```python
@staticmethod
relative_to(path: Union[str, Path], base: Union[str, Path]) -> Path
```

Get relative path from base.

**Parameters:**
- `path` (Union[str, Path]): Target path
- `base` (Union[str, Path]): Base path

**Returns:**
- `Path`: Relative path

##### ensure_directory (static)

```python
@staticmethod
ensure_directory(path: Union[str, Path]) -> Path
```

Ensure directory exists, create if necessary.

**Parameters:**
- `path` (Union[str, Path]): Directory path

**Returns:**
- `Path`: Path object for the directory

### DirectoryScanner

Scans directories for files matching criteria.

#### Constructor

```python
DirectoryScanner(validator: Optional[FilePathValidator] = None)
```

**Parameters:**
- `validator` (Optional[FilePathValidator]): File path validator to use

#### Methods

##### scan_directory

```python
scan_directory(
    directory: Union[str, Path], 
    recursive: bool = True,
    max_depth: Optional[int] = None
) -> Iterator[Path]
```

Scan directory for files.

**Parameters:**
- `directory` (Union[str, Path]): Directory to scan
- `recursive` (bool): Whether to scan recursively
- `max_depth` (Optional[int]): Maximum depth for recursive scanning

**Yields:**
- `Path`: Path objects for found files

**Example:**
```python
scanner = DirectoryScanner()
for file_path in scanner.scan_directory("/extensions", recursive=True):
    print(f"Found: {file_path}")
```

##### find_files_by_extension

```python
find_files_by_extension(
    directory: Union[str, Path], 
    extensions: Set[str],
    recursive: bool = True
) -> List[Path]
```

Find files with specific extensions.

**Parameters:**
- `directory` (Union[str, Path]): Directory to search
- `extensions` (Set[str]): Set of extensions to match (with dots)
- `recursive` (bool): Whether to search recursively

**Returns:**
- `List[Path]`: List of matching file paths

##### get_directory_stats

```python
get_directory_stats(directory: Union[str, Path]) -> dict
```

Get statistics about directory contents.

**Parameters:**
- `directory` (Union[str, Path]): Directory to analyze

**Returns:**
- `dict`: Dictionary with directory statistics

**Response Format:**
```python
{
    'total_files': int,
    'total_directories': int,
    'total_size': int,  # bytes
    'extensions': set,  # set of found extensions
}
```

### FileFilter

Filters files based on various criteria.

#### Constructor

```python
FileFilter()
```

#### Methods

##### add_extension_filter

```python
add_extension_filter(extensions: Set[str]) -> 'FileFilter'
```

Add extension filter.

**Parameters:**
- `extensions` (Set[str]): Set of allowed extensions (with dots)

**Returns:**
- `FileFilter`: Self for method chaining

##### add_pattern_filter

```python
add_pattern_filter(patterns: List[str]) -> 'FileFilter'
```

Add filename pattern filter.

**Parameters:**
- `patterns` (List[str]): List of fnmatch patterns

**Returns:**
- `FileFilter`: Self for method chaining

##### add_size_filter

```python
add_size_filter(min_size: int = 0, max_size: Optional[int] = None) -> 'FileFilter'
```

Add file size filter.

**Parameters:**
- `min_size` (int): Minimum file size in bytes
- `max_size` (Optional[int]): Maximum file size in bytes (None for no limit)

**Returns:**
- `FileFilter`: Self for method chaining

##### add_exclude_hidden

```python
add_exclude_hidden() -> 'FileFilter'
```

Add filter to exclude hidden files.

**Returns:**
- `FileFilter`: Self for method chaining

##### filter_files

```python
filter_files(files: List[Path]) -> List[Path]
```

Apply all filters to file list.

**Parameters:**
- `files` (List[Path]): List of file paths to filter

**Returns:**
- `List[Path]`: Filtered list of file paths

##### clear_filters

```python
clear_filters() -> 'FileFilter'
```

Clear all filters.

**Returns:**
- `FileFilter`: Self for method chaining

**Example:**
```python
file_filter = (FileFilter()
              .add_extension_filter({'.json', '.yaml'})
              .add_size_filter(0, 1024*1024)  # Max 1MB
              .add_exclude_hidden())

filtered_files = file_filter.filter_files(all_files)
```

## Validation Framework

### ValidationError (dataclass)

Represents a validation error with detailed information.

#### Fields

```python
@dataclass
class ValidationError:
    code: str
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    severity: str = "error"  # error, warning, info
    suggestion: Optional[str] = None
```

#### Methods

##### __str__

```python
__str__() -> str
```

Human-readable error message.

**Returns:**
- `str`: Formatted error message

### ValidationResult (dataclass)

Represents the result of a validation operation.

#### Fields

```python
@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    file_path: Optional[str] = None
    extension_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### Methods

##### add_error

```python
add_error(
    code: str, 
    message: str, 
    file_path: Optional[str] = None,
    line_number: Optional[int] = None, 
    suggestion: Optional[str] = None
) -> None
```

Add an error to the validation result.

**Parameters:**
- `code` (str): Error code
- `message` (str): Error message
- `file_path` (Optional[str]): Path to file with error
- `line_number` (Optional[int]): Line number where error occurred
- `suggestion` (Optional[str]): Suggestion for fixing the error

##### add_warning

```python
add_warning(
    code: str, 
    message: str, 
    file_path: Optional[str] = None,
    line_number: Optional[int] = None, 
    suggestion: Optional[str] = None
) -> None
```

Add a warning to the validation result.

##### add_info

```python
add_info(
    code: str, 
    message: str, 
    file_path: Optional[str] = None,
    line_number: Optional[int] = None, 
    suggestion: Optional[str] = None
) -> None
```

Add an info message to the validation result.

##### merge

```python
merge(other: 'ValidationResult') -> None
```

Merge another validation result into this one.

**Parameters:**
- `other` (ValidationResult): Another validation result to merge

#### Properties

##### all_issues

```python
@property
all_issues() -> List[ValidationError]
```

Get all errors and warnings combined.

**Returns:**
- `List[ValidationError]`: Combined list of all issues

### BaseValidator (ABC)

Base class for all extension validators.

#### Constructor

```python
BaseValidator(max_file_size: int = 10 * 1024 * 1024)  # 10MB default
```

**Parameters:**
- `max_file_size` (int): Maximum file size to process in bytes

#### Abstract Methods

##### get_extension_type

```python
@abstractmethod
get_extension_type() -> str
```

Return the extension type this validator handles.

**Returns:**
- `str`: Extension type name

##### validate_single

```python
@abstractmethod
validate_single(file_path: Union[str, Path]) -> ValidationResult
```

Validate a single extension file.

**Parameters:**
- `file_path` (Union[str, Path]): Path to file to validate

**Returns:**
- `ValidationResult`: Validation result

#### Concrete Methods

##### validate_batch

```python
validate_batch(file_paths: List[Union[str, Path]]) -> List[ValidationResult]
```

Validate multiple extension files.

**Parameters:**
- `file_paths` (List[Union[str, Path]]): List of file paths to validate

**Returns:**
- `List[ValidationResult]`: List of validation results

##### validate_directory

```python
validate_directory(directory_path: Union[str, Path]) -> List[ValidationResult]
```

Validate all valid extension files in a directory.

**Parameters:**
- `directory_path` (Union[str, Path]): Directory to validate

**Returns:**
- `List[ValidationResult]`: List of validation results

#### Protected Methods

##### _validate_file_accessibility

```python
_validate_file_accessibility(file_path: Path) -> Optional[ValidationError]
```

Validate that a file can be accessed and is not too large.

##### _validate_json_syntax

```python
_validate_json_syntax(file_path: Path) -> tuple[Optional[ValidationError], Optional[Dict[str, Any]]]
```

Validate JSON syntax and return parsed data.

##### _validate_required_fields

```python
_validate_required_fields(
    data: Dict[str, Any], 
    required_fields: List[str], 
    file_path: str
) -> List[ValidationError]
```

Validate that required fields are present in data.

##### _validate_field_type

```python
_validate_field_type(
    data: Dict[str, Any], 
    field: str, 
    expected_type: type,
    file_path: str, 
    required: bool = True
) -> Optional[ValidationError]
```

Validate that a field has the expected type.

## Error Handling

### Exception Hierarchy

```
Exception
└── PACCError
    ├── ValidationError
    ├── FileSystemError
    ├── ConfigurationError
    ├── SourceError
    ├── NetworkError
    └── SecurityError
```

### PACCError

Base exception for all PACC errors.

#### Constructor

```python
PACCError(
    message: str, 
    error_code: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
)
```

**Parameters:**
- `message` (str): Human-readable error message
- `error_code` (Optional[str]): Optional error code for programmatic handling
- `context` (Optional[Dict[str, Any]]): Optional context information

#### Methods

##### to_dict

```python
to_dict() -> Dict[str, Any]
```

Convert error to dictionary representation.

**Returns:**
- `Dict[str, Any]`: Dictionary with error details

**Example:**
```python
try:
    risky_operation()
except PACCError as e:
    error_dict = e.to_dict()
    log_error(error_dict)
```

### ValidationError (Exception)

Error raised when validation fails.

#### Constructor

```python
ValidationError(
    message: str, 
    file_path: Optional[Path] = None,
    line_number: Optional[int] = None,
    validation_type: Optional[str] = None,
    **kwargs
)
```

### FileSystemError

Error raised for file system operations.

#### Constructor

```python
FileSystemError(
    message: str, 
    file_path: Optional[Path] = None,
    operation: Optional[str] = None,
    **kwargs
)
```

### SecurityError

Error raised for security violations.

#### Constructor

```python
SecurityError(
    message: str, 
    security_check: Optional[str] = None,
    **kwargs
)
```

## Security Components

### PathTraversalProtector

Protects against path traversal attacks.

#### Constructor

```python
PathTraversalProtector(allowed_base_paths: Optional[List[Path]] = None)
```

**Parameters:**
- `allowed_base_paths` (Optional[List[Path]]): List of base paths that are allowed for access

#### Methods

##### is_safe_path

```python
is_safe_path(path: Union[str, Path], base_path: Optional[Path] = None) -> bool
```

Check if a path is safe from traversal attacks.

##### sanitize_path

```python
sanitize_path(path: Union[str, Path]) -> Path
```

Sanitize a path by removing dangerous components.

### InputSanitizer

Sanitizes various types of input to prevent injection attacks.

#### Methods

##### scan_for_threats

```python
scan_for_threats(content: str, content_type: str = "general") -> List[SecurityIssue]
```

Scan content for security threats.

##### sanitize_filename

```python
sanitize_filename(filename: str) -> str
```

Sanitize a filename for safe usage.

### SecurityAuditor

Performs comprehensive security audits of PACC operations.

#### Methods

##### audit_file

```python
audit_file(file_path: Path, context: str = "general") -> Dict
```

Perform comprehensive security audit of a file.

##### audit_directory

```python
audit_directory(directory_path: Path, recursive: bool = True) -> Dict
```

Perform security audit of an entire directory.

## Usage Examples

### Basic File Validation

```python
from pacc.core.file_utils import FilePathValidator, DirectoryScanner
from pacc.validators.base import ValidationResult

# Set up validator and scanner
validator = FilePathValidator(allowed_extensions={'.json', '.yaml'})
scanner = DirectoryScanner(validator)

# Scan directory for files
for file_path in scanner.scan_directory("/extensions"):
    if validator.is_valid_path(file_path):
        print(f"Valid file: {file_path}")
```

### Custom Validator Implementation

```python
from pacc.validators.base import BaseValidator, ValidationResult

class CustomHookValidator(BaseValidator):
    def get_extension_type(self) -> str:
        return "hooks"
    
    def validate_single(self, file_path) -> ValidationResult:
        result = ValidationResult(
            is_valid=True,
            file_path=str(file_path),
            extension_type=self.get_extension_type()
        )
        
        # Custom validation logic
        error = self._validate_file_accessibility(file_path)
        if error:
            result.add_error(error.code, error.message)
            return result
        
        # Parse and validate JSON
        json_error, data = self._validate_json_syntax(file_path)
        if json_error:
            result.add_error(json_error.code, json_error.message)
            return result
        
        # Validate required fields
        required_fields = ['name', 'version', 'events']
        field_errors = self._validate_required_fields(data, required_fields, str(file_path))
        for error in field_errors:
            result.add_error(error.code, error.message)
        
        return result
    
    def _find_extension_files(self, directory: Path) -> List[Path]:
        return list(directory.glob("**/*.json"))

# Use custom validator
validator = CustomHookValidator()
results = validator.validate_directory("/hooks")

for result in results:
    if not result.is_valid:
        print(f"Validation failed for {result.file_path}")
        for error in result.errors:
            print(f"  Error: {error.message}")
```

### Secure File Processing

```python
from pacc.security.security_measures import SecurityAuditor, PathTraversalProtector

# Set up security components
auditor = SecurityAuditor()
path_protector = PathTraversalProtector()

def secure_process_file(file_path: str, base_dir: Path):
    # Validate path safety
    if not path_protector.is_safe_path(file_path, base_dir):
        raise SecurityError("Unsafe file path detected")
    
    # Perform security audit
    audit_result = auditor.audit_file(Path(file_path))
    
    if not audit_result['is_safe']:
        print(f"Security issues found in {file_path}:")
        for issue in audit_result['issues']:
            print(f"  {issue.threat_level.value}: {issue.description}")
        return False
    
    # Safe to process
    return True
```

### Advanced File Filtering

```python
from pacc.core.file_utils import DirectoryScanner, FileFilter

# Create sophisticated filter
file_filter = (FileFilter()
              .add_extension_filter({'.json', '.yaml', '.md'})
              .add_size_filter(100, 5*1024*1024)  # 100 bytes to 5MB
              .add_pattern_filter(['*hook*', '*agent*'])
              .add_exclude_hidden())

# Scan and filter
scanner = DirectoryScanner()
all_files = list(scanner.scan_directory("/extensions", recursive=True))
filtered_files = file_filter.filter_files(all_files)

print(f"Found {len(all_files)} files, filtered to {len(filtered_files)}")
```

## Extension Points

### Creating Custom Validators

To create a custom validator, extend `BaseValidator`:

```python
class MyCustomValidator(BaseValidator):
    def get_extension_type(self) -> str:
        return "my_extension_type"
    
    def validate_single(self, file_path) -> ValidationResult:
        # Implement validation logic
        pass
    
    def _find_extension_files(self, directory: Path) -> List[Path]:
        # Implement file discovery logic
        pass
```

### Custom Security Policies

```python
from pacc.security.security_measures import SecurityPolicy

# Create custom policy
policy = SecurityPolicy()
policy.set_policy('max_file_size', 100 * 1024 * 1024)  # 100MB
policy.set_policy('allowed_extensions', {'.json', '.yaml', '.md', '.txt'})

# Use in security auditor
auditor = SecurityAuditor()
auditor.policy = policy
```

### Custom File Filters

```python
from pacc.core.file_utils import FileFilter

class CustomFileFilter(FileFilter):
    def add_custom_criterion(self, criterion_func):
        """Add custom filtering criterion."""
        self.filters.append(criterion_func)
        return self

# Usage
def is_recent_file(file_path):
    import time
    return time.time() - file_path.stat().st_mtime < 86400  # Last 24 hours

custom_filter = (CustomFileFilter()
                .add_extension_filter({'.json'})
                .add_custom_criterion(is_recent_file))
```

## Error Codes Reference

### Validation Error Codes

| Code | Description | Severity |
|------|-------------|----------|
| `MISSING_REQUIRED_FIELD` | Required field missing from configuration | Error |
| `INVALID_FIELD_TYPE` | Field has incorrect data type | Error |
| `INVALID_JSON` | JSON syntax error | Error |
| `FILE_NOT_FOUND` | File does not exist | Error |
| `FILE_TOO_LARGE` | File exceeds size limit | Warning |
| `MISSING_DESCRIPTION` | Recommended description field missing | Warning |

### Security Error Codes

| Code | Description | Threat Level |
|------|-------------|--------------|
| `PATH_TRAVERSAL` | Path traversal attempt detected | High |
| `CODE_INJECTION` | Potential code injection found | High |
| `BINARY_EXECUTABLE` | Binary executable file detected | High |
| `SUSPICIOUS_ENCODING` | Suspicious content encoding found | Medium |
| `FILE_TOO_LARGE` | File exceeds security size limit | Medium |

---

**Document Version**: 1.0  
**Last Updated**: 2024-08-12  
**API Compatibility**: PACC v0.1.0+

For questions about the API or suggestions for improvements, please open an issue in the PACC repository.