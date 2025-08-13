"""Custom exception classes for PACC."""

from typing import Optional, Dict, Any
from pathlib import Path


class PACCError(Exception):
    """Base exception for all PACC errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize PACC error.
        
        Args:
            message: Human-readable error message
            error_code: Optional error code for programmatic handling
            context: Optional context information
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.context = context or {}
    
    def __str__(self) -> str:
        """Return string representation of error."""
        return self.message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation.
        
        Returns:
            Dictionary with error details
        """
        return {
            'type': self.__class__.__name__,
            'message': self.message,
            'error_code': self.error_code,
            'context': self.context,
        }


class ValidationError(PACCError):
    """Error raised when validation fails."""
    
    def __init__(
        self, 
        message: str, 
        file_path: Optional[Path] = None,
        line_number: Optional[int] = None,
        validation_type: Optional[str] = None,
        **kwargs
    ):
        """Initialize validation error.
        
        Args:
            message: Error message
            file_path: Path to file that failed validation
            line_number: Line number where validation failed
            validation_type: Type of validation that failed
            **kwargs: Additional context
        """
        context = kwargs.copy()
        if file_path:
            context['file_path'] = str(file_path)
        if line_number:
            context['line_number'] = line_number
        if validation_type:
            context['validation_type'] = validation_type
            
        super().__init__(message, error_code='VALIDATION_ERROR', context=context)
        self.file_path = file_path
        self.line_number = line_number
        self.validation_type = validation_type


class FileSystemError(PACCError):
    """Error raised for file system operations."""
    
    def __init__(
        self, 
        message: str, 
        file_path: Optional[Path] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        """Initialize file system error.
        
        Args:
            message: Error message
            file_path: Path that caused the error
            operation: Operation that failed
            **kwargs: Additional context
        """
        context = kwargs.copy()
        if file_path:
            context['file_path'] = str(file_path)
        if operation:
            context['operation'] = operation
            
        super().__init__(message, error_code='FILESYSTEM_ERROR', context=context)
        self.file_path = file_path
        self.operation = operation


class ConfigurationError(PACCError):
    """Error raised for configuration issues."""
    
    def __init__(
        self, 
        message: str, 
        config_key: Optional[str] = None,
        config_file: Optional[Path] = None,
        **kwargs
    ):
        """Initialize configuration error.
        
        Args:
            message: Error message
            config_key: Configuration key that caused the error
            config_file: Configuration file with the error
            **kwargs: Additional context
        """
        context = kwargs.copy()
        if config_key:
            context['config_key'] = config_key
        if config_file:
            context['config_file'] = str(config_file)
            
        super().__init__(message, error_code='CONFIGURATION_ERROR', context=context)
        self.config_key = config_key
        self.config_file = config_file


class SourceError(PACCError):
    """Error raised for source management operations."""
    
    def __init__(
        self, 
        message: str, 
        source_type: Optional[str] = None,
        source_path: Optional[Path] = None,
        **kwargs
    ):
        """Initialize source error.
        
        Args:
            message: Error message
            source_type: Type of source (local, git, etc.)
            source_path: Path to source
            **kwargs: Additional context
        """
        context = kwargs.copy()
        if source_type:
            context['source_type'] = source_type
        if source_path:
            context['source_path'] = str(source_path)
            
        super().__init__(message, error_code='SOURCE_ERROR', context=context)
        self.source_type = source_type
        self.source_path = source_path


class NetworkError(PACCError):
    """Error raised for network operations."""
    
    def __init__(
        self, 
        message: str, 
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ):
        """Initialize network error.
        
        Args:
            message: Error message
            url: URL that caused the error
            status_code: HTTP status code if applicable
            **kwargs: Additional context
        """
        context = kwargs.copy()
        if url:
            context['url'] = url
        if status_code:
            context['status_code'] = status_code
            
        super().__init__(message, error_code='NETWORK_ERROR', context=context)
        self.url = url
        self.status_code = status_code


class SecurityError(PACCError):
    """Error raised for security violations."""
    
    def __init__(
        self, 
        message: str, 
        security_check: Optional[str] = None,
        **kwargs
    ):
        """Initialize security error.
        
        Args:
            message: Error message
            security_check: Type of security check that failed
            **kwargs: Additional context
        """
        context = kwargs.copy()
        if security_check:
            context['security_check'] = security_check
            
        super().__init__(message, error_code='SECURITY_ERROR', context=context)
        self.security_check = security_check


class ProjectConfigError(PACCError):
    """Error raised for project configuration issues."""
    
    def __init__(
        self, 
        message: str, 
        project_dir: Optional[Path] = None,
        config_section: Optional[str] = None,
        **kwargs
    ):
        """Initialize project configuration error.
        
        Args:
            message: Error message
            project_dir: Project directory where error occurred
            config_section: Section of config that caused error
            **kwargs: Additional context
        """
        context = kwargs.copy()
        if project_dir:
            context['project_dir'] = str(project_dir)
        if config_section:
            context['config_section'] = config_section
            
        super().__init__(message, error_code='PROJECT_CONFIG_ERROR', context=context)
        self.project_dir = project_dir
        self.config_section = config_section