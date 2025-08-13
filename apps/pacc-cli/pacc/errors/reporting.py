"""Error reporting and context management for PACC."""

import sys
import traceback
from typing import Optional, Dict, Any, List, TextIO
from dataclasses import dataclass, field
from pathlib import Path
import json
from datetime import datetime

from .exceptions import PACCError


@dataclass
class ErrorContext:
    """Context information for error reporting."""
    
    operation: str
    file_path: Optional[Path] = None
    command: Optional[str] = None
    user_input: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary.
        
        Returns:
            Dictionary representation of context
        """
        return {
            'operation': self.operation,
            'file_path': str(self.file_path) if self.file_path else None,
            'command': self.command,
            'user_input': self.user_input,
            'environment': self.environment,
            'timestamp': self.timestamp.isoformat(),
        }


class ErrorReporter:
    """Reports and logs errors with context."""
    
    def __init__(
        self, 
        output: Optional[TextIO] = None,
        verbose: bool = False,
        log_file: Optional[Path] = None
    ):
        """Initialize error reporter.
        
        Args:
            output: Output stream for error messages (defaults to stderr)
            verbose: Whether to include detailed error information
            log_file: Optional file to log errors to
        """
        self.output = output or sys.stderr
        self.verbose = verbose
        self.log_file = log_file
        self.error_history: List[Dict[str, Any]] = []
    
    def report_error(
        self, 
        error: Exception, 
        context: Optional[ErrorContext] = None,
        show_traceback: bool = False
    ) -> None:
        """Report an error with optional context.
        
        Args:
            error: The error to report
            context: Optional error context
            show_traceback: Whether to show full traceback
        """
        error_data = self._prepare_error_data(error, context)
        self.error_history.append(error_data)
        
        # Display error to user
        self._display_error(error, context, show_traceback)
        
        # Log to file if configured
        if self.log_file:
            self._log_to_file(error_data)
    
    def _prepare_error_data(
        self, 
        error: Exception, 
        context: Optional[ErrorContext]
    ) -> Dict[str, Any]:
        """Prepare error data for logging and storage.
        
        Args:
            error: The error that occurred
            context: Optional error context
            
        Returns:
            Dictionary with error information
        """
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'error_type': error.__class__.__name__,
            'message': str(error),
            'traceback': traceback.format_exc() if self.verbose else None,
        }
        
        # Add PACC-specific error information
        if isinstance(error, PACCError):
            error_data.update(error.to_dict())
        
        # Add context information
        if context:
            error_data['context'] = context.to_dict()
        
        return error_data
    
    def _display_error(
        self, 
        error: Exception, 
        context: Optional[ErrorContext],
        show_traceback: bool
    ) -> None:
        """Display error message to user.
        
        Args:
            error: The error to display
            context: Optional error context
            show_traceback: Whether to show traceback
        """
        # Basic error message
        self.output.write(f"Error: {error}\n")
        
        # Add context if available
        if context and context.file_path:
            self.output.write(f"File: {context.file_path}\n")
        
        if context and context.operation:
            self.output.write(f"Operation: {context.operation}\n")
        
        # Show PACC-specific error details
        if isinstance(error, PACCError):
            if error.error_code:
                self.output.write(f"Error Code: {error.error_code}\n")
            
            if self.verbose and error.context:
                self.output.write("Context:\n")
                for key, value in error.context.items():
                    self.output.write(f"  {key}: {value}\n")
        
        # Show traceback if requested or in verbose mode
        if show_traceback or self.verbose:
            self.output.write("\nTraceback:\n")
            traceback.print_exc(file=self.output)
        
        self.output.write("\n")
        self.output.flush()
    
    def _log_to_file(self, error_data: Dict[str, Any]) -> None:
        """Log error data to file.
        
        Args:
            error_data: Error information to log
        """
        if not self.log_file:
            return
        
        try:
            # Ensure log directory exists
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Append error data as JSON line
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(error_data) + '\n')
                
        except (OSError, IOError):
            # If we can't log to file, just continue
            pass
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all reported errors.
        
        Returns:
            Dictionary with error statistics and recent errors
        """
        if not self.error_history:
            return {'total_errors': 0, 'recent_errors': []}
        
        error_types = {}
        for error in self.error_history:
            error_type = error.get('error_type', 'Unknown')
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        return {
            'total_errors': len(self.error_history),
            'error_types': error_types,
            'recent_errors': self.error_history[-5:],  # Last 5 errors
        }
    
    def clear_history(self) -> None:
        """Clear error history."""
        self.error_history.clear()
    
    def report_validation_error(
        self, 
        message: str, 
        file_path: Optional[Path] = None,
        line_number: Optional[int] = None,
        validation_type: Optional[str] = None
    ) -> None:
        """Report a validation error with convenience method.
        
        Args:
            message: Error message
            file_path: File that failed validation
            line_number: Line number where validation failed
            validation_type: Type of validation that failed
        """
        from .exceptions import ValidationError
        
        error = ValidationError(
            message=message,
            file_path=file_path,
            line_number=line_number,
            validation_type=validation_type
        )
        
        context = ErrorContext(
            operation='validation',
            file_path=file_path
        )
        
        self.report_error(error, context)
    
    def report_filesystem_error(
        self, 
        message: str, 
        file_path: Optional[Path] = None,
        operation: Optional[str] = None
    ) -> None:
        """Report a filesystem error with convenience method.
        
        Args:
            message: Error message
            file_path: File path that caused the error
            operation: Operation that failed
        """
        from .exceptions import FileSystemError
        
        error = FileSystemError(
            message=message,
            file_path=file_path,
            operation=operation
        )
        
        context = ErrorContext(
            operation=operation or 'filesystem',
            file_path=file_path
        )
        
        self.report_error(error, context)