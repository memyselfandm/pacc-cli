"""Diagnostic and error analysis utilities for recovery operations."""

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import logging
import traceback

from ..errors import PACCError


logger = logging.getLogger(__name__)


@dataclass
class SystemInfo:
    """System information for diagnostics."""
    
    platform: str
    platform_version: str
    python_version: str
    python_executable: str
    architecture: str
    cpu_count: int
    memory_total: Optional[int] = None
    disk_free: Optional[int] = None
    environment_variables: Dict[str, str] = field(default_factory=dict)


@dataclass
class ErrorContext:
    """Context information for error analysis."""
    
    error_type: str
    error_message: str
    traceback: str
    file_path: Optional[str] = None
    operation: Optional[str] = None
    system_info: Optional[SystemInfo] = None
    timestamps: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticResult:
    """Result of diagnostic analysis."""
    
    issue_found: bool
    issue_type: str
    severity: str  # "low", "medium", "high", "critical"
    description: str
    recommendations: List[str] = field(default_factory=list)
    automated_fix_available: bool = False
    confidence: float = 0.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SystemDiagnostics:
    """System diagnostics and health checks."""
    
    def __init__(self):
        """Initialize system diagnostics."""
        self.cached_info: Optional[SystemInfo] = None
    
    def get_system_info(self, refresh: bool = False) -> SystemInfo:
        """Get comprehensive system information.
        
        Args:
            refresh: Whether to refresh cached information
            
        Returns:
            System information
        """
        if self.cached_info and not refresh:
            return self.cached_info
        
        # Basic platform info
        system_info = SystemInfo(
            platform=platform.system(),
            platform_version=platform.release(),
            python_version=sys.version,
            python_executable=sys.executable,
            architecture=platform.machine(),
            cpu_count=os.cpu_count() or 1
        )
        
        # Memory information
        try:
            if hasattr(os, 'sysconf') and hasattr(os, 'sysconf_names'):
                if 'SC_PAGE_SIZE' in os.sysconf_names and 'SC_PHYS_PAGES' in os.sysconf_names:
                    page_size = os.sysconf('SC_PAGE_SIZE')
                    phys_pages = os.sysconf('SC_PHYS_PAGES')
                    system_info.memory_total = page_size * phys_pages
        except (OSError, ValueError):
            pass
        
        # Disk space information
        try:
            disk_usage = shutil.disk_usage('/')
            system_info.disk_free = disk_usage.free
        except (OSError, ValueError):
            pass
        
        # Environment variables (filtered for security)
        safe_env_vars = [
            'PATH', 'PYTHON_PATH', 'HOME', 'USER', 'USERNAME',
            'SHELL', 'TERM', 'LANG', 'LC_ALL', 'TMPDIR', 'TMP'
        ]
        
        for var in safe_env_vars:
            if var in os.environ:
                system_info.environment_variables[var] = os.environ[var]
        
        self.cached_info = system_info
        return system_info
    
    def check_disk_space(self, path: Union[str, Path], min_free_mb: int = 100) -> DiagnosticResult:
        """Check available disk space.
        
        Args:
            path: Path to check disk space for
            min_free_mb: Minimum free space in MB
            
        Returns:
            Diagnostic result
        """
        try:
            path_obj = Path(path)
            
            # Find existing parent directory
            check_path = path_obj
            while not check_path.exists() and check_path.parent != check_path:
                check_path = check_path.parent
            
            disk_usage = shutil.disk_usage(check_path)
            free_mb = disk_usage.free / (1024 * 1024)
            
            if free_mb < min_free_mb:
                return DiagnosticResult(
                    issue_found=True,
                    issue_type="low_disk_space",
                    severity="high" if free_mb < 50 else "medium",
                    description=f"Low disk space: {free_mb:.1f}MB free (minimum: {min_free_mb}MB)",
                    recommendations=[
                        "Free up disk space by removing unnecessary files",
                        "Clear temporary files and caches",
                        "Consider moving files to external storage"
                    ],
                    confidence=0.9,
                    metadata={'free_mb': free_mb, 'min_required_mb': min_free_mb}
                )
            else:
                return DiagnosticResult(
                    issue_found=False,
                    issue_type="disk_space",
                    severity="low",
                    description=f"Sufficient disk space: {free_mb:.1f}MB free",
                    confidence=0.9,
                    metadata={'free_mb': free_mb}
                )
                
        except Exception as e:
            return DiagnosticResult(
                issue_found=True,
                issue_type="disk_check_failed",
                severity="medium",
                description=f"Could not check disk space: {e}",
                confidence=0.5
            )
    
    def check_permissions(self, path: Union[str, Path], operation: str = "read") -> DiagnosticResult:
        """Check file/directory permissions.
        
        Args:
            path: Path to check
            operation: Operation to check ("read", "write", "execute")
            
        Returns:
            Diagnostic result
        """
        try:
            path_obj = Path(path)
            
            # Check if path exists
            if not path_obj.exists():
                return DiagnosticResult(
                    issue_found=True,
                    issue_type="path_not_found",
                    severity="high",
                    description=f"Path does not exist: {path}",
                    recommendations=[
                        "Check if the path is correct",
                        "Create the missing file or directory",
                        "Verify the parent directory exists"
                    ],
                    confidence=0.9
                )
            
            # Check specific permissions
            issues = []
            
            if operation in ["read", "write"] and path_obj.is_file():
                if not os.access(path_obj, os.R_OK):
                    issues.append("File is not readable")
                if operation == "write" and not os.access(path_obj, os.W_OK):
                    issues.append("File is not writable")
            
            if operation in ["read", "write", "execute"] and path_obj.is_dir():
                if not os.access(path_obj, os.R_OK):
                    issues.append("Directory is not readable")
                if operation == "write" and not os.access(path_obj, os.W_OK):
                    issues.append("Directory is not writable")
                if not os.access(path_obj, os.X_OK):
                    issues.append("Directory is not accessible")
            
            if issues:
                return DiagnosticResult(
                    issue_found=True,
                    issue_type="permission_denied",
                    severity="medium",
                    description=f"Permission issues: {', '.join(issues)}",
                    recommendations=[
                        f"Check file permissions: ls -la '{path}'",
                        f"Fix permissions: chmod 644 '{path}' (for files) or chmod 755 '{path}' (for directories)",
                        "Run with appropriate user privileges"
                    ],
                    confidence=0.8,
                    metadata={'issues': issues, 'operation': operation}
                )
            else:
                return DiagnosticResult(
                    issue_found=False,
                    issue_type="permissions",
                    severity="low",
                    description=f"Permissions OK for {operation} operation",
                    confidence=0.9
                )
                
        except Exception as e:
            return DiagnosticResult(
                issue_found=True,
                issue_type="permission_check_failed",
                severity="medium",
                description=f"Could not check permissions: {e}",
                confidence=0.5
            )
    
    def check_python_environment(self) -> DiagnosticResult:
        """Check Python environment health.
        
        Returns:
            Diagnostic result
        """
        issues = []
        recommendations = []
        
        # Check Python version
        if sys.version_info < (3, 8):
            issues.append(f"Python version {sys.version_info.major}.{sys.version_info.minor} is too old")
            recommendations.append("Upgrade to Python 3.8 or later")
        
        # Check if we're in a virtual environment
        in_venv = (
            hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        )
        
        if not in_venv:
            issues.append("Not running in a virtual environment")
            recommendations.append("Consider using a virtual environment for better isolation")
        
        # Check for common required modules
        required_modules = ['json', 'pathlib', 'typing']
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            issues.append(f"Missing required modules: {', '.join(missing_modules)}")
            recommendations.append("Install missing modules or check Python installation")
        
        if issues:
            severity = "high" if any("version" in issue for issue in issues) else "medium"
            return DiagnosticResult(
                issue_found=True,
                issue_type="python_environment",
                severity=severity,
                description=f"Python environment issues: {'; '.join(issues)}",
                recommendations=recommendations,
                confidence=0.8,
                metadata={'python_version': sys.version, 'in_venv': in_venv}
            )
        else:
            return DiagnosticResult(
                issue_found=False,
                issue_type="python_environment",
                severity="low",
                description="Python environment is healthy",
                confidence=0.9,
                metadata={'python_version': sys.version, 'in_venv': in_venv}
            )
    
    def check_dependencies(self, required_packages: List[str] = None) -> DiagnosticResult:
        """Check if required packages are available.
        
        Args:
            required_packages: List of package names to check
            
        Returns:
            Diagnostic result
        """
        if not required_packages:
            required_packages = []
        
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            return DiagnosticResult(
                issue_found=True,
                issue_type="missing_dependencies",
                severity="medium",
                description=f"Missing required packages: {', '.join(missing_packages)}",
                recommendations=[
                    f"Install missing packages: pip install {' '.join(missing_packages)}",
                    "Check requirements.txt for complete dependency list",
                    "Ensure you're in the correct virtual environment"
                ],
                confidence=0.9,
                metadata={'missing_packages': missing_packages}
            )
        else:
            return DiagnosticResult(
                issue_found=False,
                issue_type="dependencies",
                severity="low",
                description="All required dependencies are available",
                confidence=0.9,
                metadata={'checked_packages': required_packages}
            )


class ErrorAnalyzer:
    """Analyzer for extracting insights from errors and exceptions."""
    
    def __init__(self):
        """Initialize error analyzer."""
        self.pattern_rules = [
            self._analyze_file_not_found,
            self._analyze_permission_error,
            self._analyze_import_error,
            self._analyze_syntax_error,
            self._analyze_encoding_error,
            self._analyze_json_error,
            self._analyze_network_error,
            self._analyze_memory_error,
            self._analyze_timeout_error,
        ]
    
    def analyze_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorContext:
        """Analyze error and extract context information.
        
        Args:
            error: Exception to analyze
            context: Additional context information
            
        Returns:
            Error context with analysis
        """
        context = context or {}
        
        error_context = ErrorContext(
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc(),
            file_path=context.get('file_path'),
            operation=context.get('operation'),
            system_info=SystemDiagnostics().get_system_info()
        )
        
        # Add timestamps
        import time
        error_context.timestamps['analyzed_at'] = time.time()
        
        # Extract additional metadata from error
        error_context.metadata.update(self._extract_error_metadata(error))
        
        # Add context metadata
        error_context.metadata.update(context)
        
        return error_context
    
    def categorize_error(self, error: Exception) -> Tuple[str, float]:
        """Categorize error and assess severity.
        
        Args:
            error: Exception to categorize
            
        Returns:
            Tuple of (category, severity_score)
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # File system errors
        if isinstance(error, (FileNotFoundError, FileExistsError, IsADirectoryError, NotADirectoryError)):
            return "file_system", 0.6
        
        if isinstance(error, PermissionError):
            return "permissions", 0.7
        
        # Validation errors
        if "json" in error_msg or "yaml" in error_msg or "invalid" in error_msg:
            return "validation", 0.5
        
        # Network errors
        if "connection" in error_msg or "network" in error_msg or "timeout" in error_msg:
            return "network", 0.4
        
        # Memory errors
        if isinstance(error, MemoryError) or "memory" in error_msg:
            return "memory", 0.9
        
        # Import/dependency errors
        if isinstance(error, ImportError) or isinstance(error, ModuleNotFoundError):
            return "dependencies", 0.6
        
        # Syntax errors
        if isinstance(error, SyntaxError):
            return "syntax", 0.8
        
        # Encoding errors
        if isinstance(error, UnicodeError):
            return "encoding", 0.5
        
        # Default category
        return "unknown", 0.3
    
    def get_error_patterns(self, error: Exception) -> List[DiagnosticResult]:
        """Get diagnostic results based on error patterns.
        
        Args:
            error: Exception to analyze
            
        Returns:
            List of diagnostic results
        """
        results = []
        
        for rule in self.pattern_rules:
            try:
                result = rule(error)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f"Error analysis rule failed: {e}")
        
        return results
    
    def _extract_error_metadata(self, error: Exception) -> Dict[str, Any]:
        """Extract metadata from exception object.
        
        Args:
            error: Exception to extract metadata from
            
        Returns:
            Dictionary of metadata
        """
        metadata = {}
        
        # Standard exception attributes
        if hasattr(error, 'errno'):
            metadata['errno'] = error.errno
        
        if hasattr(error, 'strerror'):
            metadata['strerror'] = error.strerror
        
        if hasattr(error, 'filename'):
            metadata['filename'] = error.filename
        
        # For custom PACC errors
        if isinstance(error, PACCError):
            metadata.update(error.context)
        
        return metadata
    
    # Pattern analysis rules
    
    def _analyze_file_not_found(self, error: Exception) -> Optional[DiagnosticResult]:
        """Analyze file not found errors."""
        if not isinstance(error, FileNotFoundError):
            return None
        
        filename = getattr(error, 'filename', None)
        
        recommendations = [
            "Check if the file path is correct",
            "Verify the file exists at the specified location"
        ]
        
        if filename:
            file_path = Path(filename)
            parent_dir = file_path.parent
            
            if not parent_dir.exists():
                recommendations.insert(0, f"Create missing directory: {parent_dir}")
            
            # Check for similar files
            if parent_dir.exists():
                similar_files = self._find_similar_files(parent_dir, file_path.name)
                if similar_files:
                    recommendations.append(f"Similar files found: {', '.join(f.name for f in similar_files[:3])}")
        
        return DiagnosticResult(
            issue_found=True,
            issue_type="file_not_found",
            severity="medium",
            description=f"File not found: {filename or 'unknown'}",
            recommendations=recommendations,
            confidence=0.9,
            metadata={'filename': filename}
        )
    
    def _analyze_permission_error(self, error: Exception) -> Optional[DiagnosticResult]:
        """Analyze permission errors."""
        if not isinstance(error, PermissionError):
            return None
        
        filename = getattr(error, 'filename', None)
        
        return DiagnosticResult(
            issue_found=True,
            issue_type="permission_denied",
            severity="medium",
            description=f"Permission denied: {filename or 'unknown file'}",
            recommendations=[
                "Check file permissions and ownership",
                "Run with appropriate user privileges",
                f"Try: chmod 644 '{filename}'" if filename else "Fix file permissions"
            ],
            confidence=0.9,
            metadata={'filename': filename}
        )
    
    def _analyze_import_error(self, error: Exception) -> Optional[DiagnosticResult]:
        """Analyze import errors."""
        if not isinstance(error, (ImportError, ModuleNotFoundError)):
            return None
        
        module_name = getattr(error, 'name', None) or str(error).split("'")[1] if "'" in str(error) else None
        
        recommendations = [
            "Install the missing package",
            "Check if you're in the correct virtual environment"
        ]
        
        if module_name:
            recommendations.insert(0, f"Install package: pip install {module_name}")
        
        return DiagnosticResult(
            issue_found=True,
            issue_type="missing_dependency",
            severity="medium",
            description=f"Missing module: {module_name or 'unknown'}",
            recommendations=recommendations,
            confidence=0.9,
            metadata={'module_name': module_name}
        )
    
    def _analyze_syntax_error(self, error: Exception) -> Optional[DiagnosticResult]:
        """Analyze syntax errors."""
        if not isinstance(error, SyntaxError):
            return None
        
        return DiagnosticResult(
            issue_found=True,
            issue_type="syntax_error",
            severity="high",
            description=f"Syntax error: {error.msg or str(error)}",
            recommendations=[
                "Check file syntax and formatting",
                "Look for missing brackets, quotes, or commas",
                "Validate with appropriate syntax checker"
            ],
            confidence=0.9,
            metadata={'line_number': error.lineno, 'filename': error.filename}
        )
    
    def _analyze_encoding_error(self, error: Exception) -> Optional[DiagnosticResult]:
        """Analyze encoding errors."""
        if not isinstance(error, UnicodeError):
            return None
        
        return DiagnosticResult(
            issue_found=True,
            issue_type="encoding_error",
            severity="medium",
            description=f"Encoding error: {type(error).__name__}",
            recommendations=[
                "Convert file to UTF-8 encoding",
                "Specify correct encoding when opening file",
                "Use encoding detection tools"
            ],
            confidence=0.8
        )
    
    def _analyze_json_error(self, error: Exception) -> Optional[DiagnosticResult]:
        """Analyze JSON errors."""
        error_msg = str(error).lower()
        
        if "json" not in error_msg:
            return None
        
        return DiagnosticResult(
            issue_found=True,
            issue_type="json_format_error",
            severity="medium",
            description=f"JSON format error: {error}",
            recommendations=[
                "Validate JSON syntax",
                "Check for missing commas or brackets",
                "Remove trailing commas",
                "Ensure all strings are quoted"
            ],
            confidence=0.8
        )
    
    def _analyze_network_error(self, error: Exception) -> Optional[DiagnosticResult]:
        """Analyze network-related errors."""
        error_msg = str(error).lower()
        
        if not any(keyword in error_msg for keyword in ['connection', 'network', 'timeout', 'refused']):
            return None
        
        severity = "high" if "refused" in error_msg else "medium"
        
        return DiagnosticResult(
            issue_found=True,
            issue_type="network_error",
            severity=severity,
            description=f"Network error: {error}",
            recommendations=[
                "Check internet connection",
                "Verify server is accessible",
                "Check firewall settings",
                "Try again after a short delay"
            ],
            confidence=0.7
        )
    
    def _analyze_memory_error(self, error: Exception) -> Optional[DiagnosticResult]:
        """Analyze memory errors."""
        if not isinstance(error, MemoryError):
            return None
        
        return DiagnosticResult(
            issue_found=True,
            issue_type="memory_error",
            severity="high",
            description="Out of memory",
            recommendations=[
                "Close other applications to free memory",
                "Process smaller chunks of data",
                "Increase virtual memory",
                "Consider using a machine with more RAM"
            ],
            confidence=0.9
        )
    
    def _analyze_timeout_error(self, error: Exception) -> Optional[DiagnosticResult]:
        """Analyze timeout errors."""
        error_msg = str(error).lower()
        
        if "timeout" not in error_msg:
            return None
        
        return DiagnosticResult(
            issue_found=True,
            issue_type="timeout_error",
            severity="medium",
            description=f"Timeout error: {error}",
            recommendations=[
                "Increase timeout value",
                "Check if operation is taking too long",
                "Verify network connectivity",
                "Try breaking operation into smaller steps"
            ],
            confidence=0.8
        )
    
    def _find_similar_files(self, directory: Path, filename: str, max_results: int = 3) -> List[Path]:
        """Find files with similar names."""
        try:
            import difflib
            
            if not directory.exists():
                return []
            
            all_files = [f for f in directory.iterdir() if f.is_file()]
            file_names = [f.name for f in all_files]
            
            matches = difflib.get_close_matches(filename, file_names, n=max_results, cutoff=0.6)
            return [directory / match for match in matches]
            
        except Exception:
            return []


class DiagnosticEngine:
    """Main diagnostic engine that coordinates analysis and recommendations."""
    
    def __init__(self):
        """Initialize diagnostic engine."""
        self.system_diagnostics = SystemDiagnostics()
        self.error_analyzer = ErrorAnalyzer()
    
    def run_full_diagnostics(
        self,
        error: Optional[Exception] = None,
        file_path: Optional[Union[str, Path]] = None,
        operation: Optional[str] = None
    ) -> List[DiagnosticResult]:
        """Run comprehensive diagnostics.
        
        Args:
            error: Optional error to analyze
            file_path: Optional file path for context
            operation: Optional operation name
            
        Returns:
            List of diagnostic results
        """
        results = []
        
        # System health checks
        results.append(self.system_diagnostics.check_python_environment())
        
        if file_path:
            results.append(self.system_diagnostics.check_disk_space(file_path))
            results.append(self.system_diagnostics.check_permissions(file_path, "read"))
        
        # Error-specific analysis
        if error:
            error_patterns = self.error_analyzer.get_error_patterns(error)
            results.extend(error_patterns)
        
        # Filter out non-issues for cleaner output
        return [r for r in results if r.issue_found or r.severity != "low"]
    
    def get_recovery_recommendations(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Get prioritized recovery recommendations.
        
        Args:
            error: Exception to analyze
            context: Additional context
            
        Returns:
            List of recovery recommendations
        """
        context = context or {}
        
        # Run diagnostics
        results = self.run_full_diagnostics(
            error=error,
            file_path=context.get('file_path'),
            operation=context.get('operation')
        )
        
        # Collect all recommendations
        all_recommendations = []
        for result in results:
            all_recommendations.extend(result.recommendations)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in all_recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)
        
        return unique_recommendations
    
    def assess_error_severity(self, error: Exception) -> Tuple[str, float]:
        """Assess error severity and category.
        
        Args:
            error: Exception to assess
            
        Returns:
            Tuple of (category, severity_score)
        """
        return self.error_analyzer.categorize_error(error)
    
    def generate_diagnostic_report(
        self,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive diagnostic report.
        
        Args:
            error: Optional error to analyze
            context: Additional context
            
        Returns:
            Diagnostic report dictionary
        """
        context = context or {}
        
        report = {
            'timestamp': time.time(),
            'system_info': self.system_diagnostics.get_system_info().to_dict() if hasattr(self.system_diagnostics.get_system_info(), 'to_dict') else self.system_diagnostics.get_system_info(),
            'diagnostics': [],
            'error_analysis': None,
            'recommendations': [],
            'severity_assessment': None
        }
        
        # Convert dataclass to dict for system_info
        import dataclasses
        report['system_info'] = dataclasses.asdict(self.system_diagnostics.get_system_info())
        
        # Run diagnostics
        diagnostic_results = self.run_full_diagnostics(
            error=error,
            file_path=context.get('file_path'),
            operation=context.get('operation')
        )
        
        report['diagnostics'] = [dataclasses.asdict(result) for result in diagnostic_results]
        
        # Error analysis
        if error:
            error_context = self.error_analyzer.analyze_error(error, context)
            report['error_analysis'] = dataclasses.asdict(error_context)
            
            category, severity = self.assess_error_severity(error)
            report['severity_assessment'] = {
                'category': category,
                'severity_score': severity
            }
        
        # Recommendations
        report['recommendations'] = self.get_recovery_recommendations(error, context) if error else []
        
        return report


# Import time for report generation
import time