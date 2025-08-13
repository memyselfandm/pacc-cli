"""Core file utilities for PACC source management."""

import os
import pathlib
from typing import List, Set, Iterator, Optional, Union, Callable
from pathlib import Path
import fnmatch
import stat


class FilePathValidator:
    """Validates file paths for security and accessibility."""
    
    def __init__(self, allowed_extensions: Optional[Set[str]] = None):
        """Initialize validator with optional allowed extensions.
        
        Args:
            allowed_extensions: Set of allowed file extensions (with dots, e.g., {'.json', '.yaml'})
        """
        self.allowed_extensions = allowed_extensions or set()
    
    def is_valid_path(self, path: Union[str, Path]) -> bool:
        """Check if path is valid and safe to access.
        
        Args:
            path: Path to validate
            
        Returns:
            True if path is valid and safe
        """
        try:
            path_obj = Path(path).resolve()
            
            # Check if path exists
            if not path_obj.exists():
                return False
            
            # Check for directory traversal attempts
            if '..' in str(path):
                return False
            
            # Check if we can read the file/directory
            if not os.access(path_obj, os.R_OK):
                return False
            
            # Check file extension if restrictions are set
            if self.allowed_extensions and path_obj.is_file():
                if path_obj.suffix.lower() not in self.allowed_extensions:
                    return False
            
            return True
            
        except (OSError, ValueError, RuntimeError):
            return False
    
    def validate_extension(self, path: Union[str, Path], extensions: Set[str]) -> bool:
        """Validate file has one of the allowed extensions.
        
        Args:
            path: Path to check
            extensions: Set of allowed extensions (with dots)
            
        Returns:
            True if extension is allowed
        """
        path_obj = Path(path)
        return path_obj.suffix.lower() in extensions
    
    def is_safe_directory(self, path: Union[str, Path]) -> bool:
        """Check if directory is safe to scan.
        
        Args:
            path: Directory path to check
            
        Returns:
            True if directory is safe to scan
        """
        try:
            path_obj = Path(path).resolve()
            
            if not path_obj.exists() or not path_obj.is_dir():
                return False
            
            # Check permissions
            if not os.access(path_obj, os.R_OK | os.X_OK):
                return False
            
            # Avoid system directories on Unix-like systems
            system_dirs = {'/proc', '/sys', '/dev', '/etc'}
            if str(path_obj) in system_dirs:
                return False
            
            return True
            
        except (OSError, ValueError, RuntimeError):
            return False


class PathNormalizer:
    """Normalizes file paths for cross-platform compatibility."""
    
    @staticmethod
    def normalize(path: Union[str, Path]) -> Path:
        """Normalize path for current platform.
        
        Args:
            path: Path to normalize
            
        Returns:
            Normalized Path object
        """
        return Path(path).resolve()
    
    @staticmethod
    def to_posix(path: Union[str, Path]) -> str:
        """Convert path to POSIX format.
        
        Args:
            path: Path to convert
            
        Returns:
            POSIX-style path string
        """
        return Path(path).as_posix()
    
    @staticmethod
    def relative_to(path: Union[str, Path], base: Union[str, Path]) -> Path:
        """Get relative path from base.
        
        Args:
            path: Target path
            base: Base path
            
        Returns:
            Relative path
        """
        path_obj = Path(path).resolve()
        base_obj = Path(base).resolve()
        
        try:
            return path_obj.relative_to(base_obj)
        except ValueError:
            # Paths are not relative - return absolute path
            return path_obj
    
    @staticmethod
    def ensure_directory(path: Union[str, Path]) -> Path:
        """Ensure directory exists, create if necessary.
        
        Args:
            path: Directory path
            
        Returns:
            Path object for the directory
        """
        path_obj = Path(path)
        path_obj.mkdir(parents=True, exist_ok=True)
        return path_obj


class DirectoryScanner:
    """Scans directories for files matching criteria."""
    
    def __init__(self, validator: Optional[FilePathValidator] = None):
        """Initialize scanner with optional validator.
        
        Args:
            validator: File path validator to use
        """
        self.validator = validator or FilePathValidator()
    
    def scan_directory(
        self, 
        directory: Union[str, Path], 
        recursive: bool = True,
        max_depth: Optional[int] = None
    ) -> Iterator[Path]:
        """Scan directory for files.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan recursively
            max_depth: Maximum depth for recursive scanning
            
        Yields:
            Path objects for found files
        """
        dir_path = Path(directory)
        
        if not self.validator.is_safe_directory(dir_path):
            return
        
        try:
            if recursive:
                pattern = "**/*" if max_depth is None else "/".join(["*"] * (max_depth + 1))
                for path in dir_path.glob(pattern):
                    if path.is_file() and self.validator.is_valid_path(path):
                        yield path
            else:
                for path in dir_path.iterdir():
                    if path.is_file() and self.validator.is_valid_path(path):
                        yield path
                        
        except (OSError, PermissionError):
            # Skip directories we can't access
            pass
    
    def find_files_by_extension(
        self, 
        directory: Union[str, Path], 
        extensions: Set[str],
        recursive: bool = True
    ) -> List[Path]:
        """Find files with specific extensions.
        
        Args:
            directory: Directory to search
            extensions: Set of extensions to match (with dots)
            recursive: Whether to search recursively
            
        Returns:
            List of matching file paths
        """
        files = []
        for file_path in self.scan_directory(directory, recursive):
            if file_path.suffix.lower() in extensions:
                files.append(file_path)
        return files
    
    def get_directory_stats(self, directory: Union[str, Path]) -> dict:
        """Get statistics about directory contents.
        
        Args:
            directory: Directory to analyze
            
        Returns:
            Dictionary with directory statistics
        """
        dir_path = Path(directory)
        stats = {
            'total_files': 0,
            'total_directories': 0,
            'total_size': 0,
            'extensions': set(),
        }
        
        if not self.validator.is_safe_directory(dir_path):
            return stats
        
        try:
            for path in self.scan_directory(dir_path, recursive=True):
                if path.is_file():
                    stats['total_files'] += 1
                    stats['total_size'] += path.stat().st_size
                    if path.suffix:
                        stats['extensions'].add(path.suffix.lower())
                elif path.is_dir():
                    stats['total_directories'] += 1
                    
        except (OSError, PermissionError):
            pass
        
        return stats


class FileFilter:
    """Filters files based on various criteria."""
    
    def __init__(self):
        """Initialize file filter."""
        self.filters: List[Callable[[Path], bool]] = []
    
    def add_extension_filter(self, extensions: Set[str]) -> 'FileFilter':
        """Add extension filter.
        
        Args:
            extensions: Set of allowed extensions (with dots)
            
        Returns:
            Self for method chaining
        """
        def extension_filter(path: Path) -> bool:
            return path.suffix.lower() in extensions
        
        self.filters.append(extension_filter)
        return self
    
    def add_pattern_filter(self, patterns: List[str]) -> 'FileFilter':
        """Add filename pattern filter.
        
        Args:
            patterns: List of fnmatch patterns
            
        Returns:
            Self for method chaining
        """
        def pattern_filter(path: Path) -> bool:
            return any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns)
        
        self.filters.append(pattern_filter)
        return self
    
    def add_size_filter(self, min_size: int = 0, max_size: Optional[int] = None) -> 'FileFilter':
        """Add file size filter.
        
        Args:
            min_size: Minimum file size in bytes
            max_size: Maximum file size in bytes (None for no limit)
            
        Returns:
            Self for method chaining
        """
        def size_filter(path: Path) -> bool:
            try:
                size = path.stat().st_size
                if size < min_size:
                    return False
                if max_size is not None and size > max_size:
                    return False
                return True
            except OSError:
                return False
        
        self.filters.append(size_filter)
        return self
    
    def add_exclude_hidden(self) -> 'FileFilter':
        """Add filter to exclude hidden files.
        
        Returns:
            Self for method chaining
        """
        def hidden_filter(path: Path) -> bool:
            # Check if file/directory name starts with dot
            if path.name.startswith('.'):
                return False
            
            # On Windows, check hidden attribute
            if os.name == 'nt':
                try:
                    attrs = path.stat().st_file_attributes
                    return not (attrs & stat.FILE_ATTRIBUTE_HIDDEN)
                except (AttributeError, OSError):
                    pass
            
            return True
        
        self.filters.append(hidden_filter)
        return self
    
    def filter_files(self, files: List[Path]) -> List[Path]:
        """Apply all filters to file list.
        
        Args:
            files: List of file paths to filter
            
        Returns:
            Filtered list of file paths
        """
        if not self.filters:
            return files
        
        filtered = []
        for file_path in files:
            if all(filter_func(file_path) for filter_func in self.filters):
                filtered.append(file_path)
        
        return filtered
    
    def clear_filters(self) -> 'FileFilter':
        """Clear all filters.
        
        Returns:
            Self for method chaining
        """
        self.filters.clear()
        return self