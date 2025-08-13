"""Fix suggestion engine for generating recovery actions."""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
import logging
import asyncio

from ..errors import PACCError, ValidationError, FileSystemError, ConfigurationError


logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of recovery actions."""
    FILE_OPERATION = "file_operation"
    CONFIGURATION_FIX = "configuration_fix"
    PERMISSION_FIX = "permission_fix"
    DEPENDENCY_INSTALL = "dependency_install"
    FORMAT_CONVERSION = "format_conversion"
    USER_INSTRUCTION = "user_instruction"
    SYSTEM_CHECK = "system_check"


@dataclass
class RecoveryAction:
    """Defines a specific recovery action that can be taken."""
    
    action_type: ActionType
    description: str
    auto_fixable: bool = False
    safe: bool = True
    instructions: List[str] = field(default_factory=list)
    command: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    execute_func: Optional[Callable] = None
    
    async def execute(self, context: Dict[str, Any] = None) -> bool:
        """Execute the recovery action.
        
        Args:
            context: Execution context with user data
            
        Returns:
            True if action executed successfully
        """
        if not self.auto_fixable:
            logger.warning("Cannot auto-execute non-auto-fixable action")
            return False
        
        try:
            if self.execute_func:
                # Custom execution function
                if asyncio.iscoroutinefunction(self.execute_func):
                    return await self.execute_func(context or {})
                else:
                    return self.execute_func(context or {})
            
            elif self.command:
                # Execute shell command
                return await self._execute_command(context or {})
            
            else:
                logger.warning("No execution method defined for action")
                return False
                
        except Exception as e:
            logger.error(f"Failed to execute recovery action: {e}")
            return False
    
    async def _execute_command(self, context: Dict[str, Any]) -> bool:
        """Execute shell command.
        
        Args:
            context: Execution context
            
        Returns:
            True if command executed successfully
        """
        import subprocess
        
        try:
            # Substitute parameters in command
            cmd = self.command
            for key, value in self.parameters.items():
                cmd = cmd.replace(f"{{{key}}}", str(value))
            
            # Substitute context variables
            for key, value in context.items():
                cmd = cmd.replace(f"{{{key}}}", str(value))
            
            logger.debug(f"Executing command: {cmd}")
            
            # Execute command
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.debug(f"Command executed successfully: {cmd}")
                return True
            else:
                logger.error(f"Command failed (exit {result.returncode}): {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {self.command}")
            return False
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return False


@dataclass
class FixSuggestion:
    """A suggestion for fixing an error."""
    
    title: str
    description: str
    confidence: float  # 0.0 to 1.0
    action: Optional[RecoveryAction] = None
    category: str = "general"
    priority: int = 1  # 1 = highest, 5 = lowest
    applicable_errors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        # Ensure confidence is within bounds
        self.confidence = max(0.0, min(1.0, self.confidence))


class SuggestionEngine:
    """Engine for generating fix suggestions based on errors."""
    
    def __init__(self):
        """Initialize suggestion engine."""
        self.suggestion_rules: List[Callable] = []
        self._register_builtin_rules()
    
    def _register_builtin_rules(self) -> None:
        """Register built-in suggestion rules."""
        self.suggestion_rules.extend([
            self._suggest_file_not_found_fixes,
            self._suggest_permission_fixes,
            self._suggest_validation_fixes,
            self._suggest_configuration_fixes,
            self._suggest_dependency_fixes,
            self._suggest_format_fixes,
            self._suggest_encoding_fixes,
            self._suggest_space_fixes,
            self._suggest_path_fixes,
            self._suggest_generic_fixes,
        ])
    
    async def analyze_error(
        self,
        error: Exception,
        file_path: Optional[Path] = None,
        operation: Optional[str] = None
    ) -> List[FixSuggestion]:
        """Analyze error and generate fix suggestions.
        
        Args:
            error: Exception to analyze
            file_path: Optional file path related to error
            operation: Optional operation that failed
            
        Returns:
            List of fix suggestions
        """
        suggestions = []
        
        # Run all suggestion rules
        for rule in self.suggestion_rules:
            try:
                rule_suggestions = await self._run_rule(rule, error, file_path, operation)
                suggestions.extend(rule_suggestions)
            except Exception as e:
                logger.warning(f"Suggestion rule failed: {e}")
        
        # Filter and sort suggestions
        suggestions = self._filter_suggestions(suggestions, error)
        suggestions = self._sort_suggestions(suggestions)
        
        logger.debug(f"Generated {len(suggestions)} suggestions for {type(error).__name__}")
        return suggestions
    
    async def _run_rule(
        self,
        rule: Callable,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Run a suggestion rule.
        
        Args:
            rule: Rule function to run
            error: Exception to analyze
            file_path: File path related to error
            operation: Operation that failed
            
        Returns:
            List of suggestions from rule
        """
        try:
            if asyncio.iscoroutinefunction(rule):
                return await rule(error, file_path, operation)
            else:
                return rule(error, file_path, operation)
        except Exception as e:
            logger.warning(f"Rule {rule.__name__} failed: {e}")
            return []
    
    def _filter_suggestions(
        self,
        suggestions: List[FixSuggestion],
        error: Exception
    ) -> List[FixSuggestion]:
        """Filter suggestions based on error type and applicability.
        
        Args:
            suggestions: List of suggestions to filter
            error: Exception being handled
            
        Returns:
            Filtered list of suggestions
        """
        error_type = type(error).__name__
        
        filtered = []
        for suggestion in suggestions:
            # Check if suggestion applies to this error type
            if suggestion.applicable_errors:
                if not any(
                    error_type == err_type or error_type.endswith(err_type)
                    for err_type in suggestion.applicable_errors
                ):
                    continue
            
            # Check confidence threshold
            if suggestion.confidence < 0.1:
                continue
            
            filtered.append(suggestion)
        
        # Remove duplicates based on title
        seen_titles = set()
        unique_suggestions = []
        for suggestion in filtered:
            if suggestion.title not in seen_titles:
                seen_titles.add(suggestion.title)
                unique_suggestions.append(suggestion)
        
        return unique_suggestions
    
    def _sort_suggestions(self, suggestions: List[FixSuggestion]) -> List[FixSuggestion]:
        """Sort suggestions by priority and confidence.
        
        Args:
            suggestions: List of suggestions to sort
            
        Returns:
            Sorted list of suggestions
        """
        return sorted(
            suggestions,
            key=lambda s: (s.priority, -s.confidence)
        )
    
    def _suggest_file_not_found_fixes(
        self,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Suggest fixes for file not found errors."""
        suggestions = []
        
        if not isinstance(error, (FileNotFoundError, FileSystemError)):
            return suggestions
        
        error_msg = str(error).lower()
        
        if file_path:
            parent_dir = file_path.parent
            filename = file_path.name
            
            # Suggest creating missing parent directories
            if not parent_dir.exists():
                suggestions.append(FixSuggestion(
                    title="Create missing directories",
                    description=f"Create parent directory: {parent_dir}",
                    confidence=0.8,
                    action=RecoveryAction(
                        action_type=ActionType.FILE_OPERATION,
                        description=f"Create directory {parent_dir}",
                        auto_fixable=True,
                        safe=True,
                        command=f"mkdir -p '{parent_dir}'",
                        execute_func=lambda ctx: self._create_directory(parent_dir)
                    ),
                    category="file_system",
                    priority=1,
                    applicable_errors=["FileNotFoundError", "FileSystemError"]
                ))
            
            # Suggest checking for similar filenames
            if parent_dir.exists():
                similar_files = self._find_similar_files(parent_dir, filename)
                if similar_files:
                    best_match = similar_files[0]
                    suggestions.append(FixSuggestion(
                        title=f"Use similar file: {best_match.name}",
                        description=f"Did you mean '{best_match.name}' instead of '{filename}'?",
                        confidence=0.6,
                        action=RecoveryAction(
                            action_type=ActionType.USER_INSTRUCTION,
                            description=f"Check if you meant to use '{best_match.name}'",
                            auto_fixable=False,
                            instructions=[
                                f"The file '{filename}' was not found",
                                f"Found similar file: '{best_match.name}'",
                                f"Check if this is the correct file to use"
                            ]
                        ),
                        category="file_system",
                        priority=2
                    ))
            
            # Suggest checking file permissions
            if file_path.exists():
                suggestions.append(FixSuggestion(
                    title="Check file permissions",
                    description="File exists but may not be readable",
                    confidence=0.7,
                    action=RecoveryAction(
                        action_type=ActionType.PERMISSION_FIX,
                        description=f"Fix permissions for {file_path}",
                        auto_fixable=True,
                        command=f"chmod 644 '{file_path}'",
                        execute_func=lambda ctx: self._fix_file_permissions(file_path)
                    ),
                    category="permissions",
                    priority=2,
                    applicable_errors=["PermissionError", "FileSystemError"]
                ))
        
        return suggestions
    
    def _suggest_permission_fixes(
        self,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Suggest fixes for permission errors."""
        suggestions = []
        
        if not isinstance(error, PermissionError):
            return suggestions
        
        if file_path:
            suggestions.append(FixSuggestion(
                title="Fix file permissions",
                description=f"Grant read/write permissions to {file_path}",
                confidence=0.9,
                action=RecoveryAction(
                    action_type=ActionType.PERMISSION_FIX,
                    description=f"Fix permissions for {file_path}",
                    auto_fixable=True,
                    command=f"chmod 644 '{file_path}'",
                    execute_func=lambda ctx: self._fix_file_permissions(file_path)
                ),
                category="permissions",
                priority=1,
                applicable_errors=["PermissionError"]
            ))
            
            # Suggest checking if running as admin/sudo
            suggestions.append(FixSuggestion(
                title="Run with elevated permissions",
                description="Try running the command with sudo/administrator privileges",
                confidence=0.6,
                action=RecoveryAction(
                    action_type=ActionType.USER_INSTRUCTION,
                    description="Run with elevated permissions",
                    auto_fixable=False,
                    instructions=[
                        "This operation requires elevated permissions",
                        "Try running with 'sudo' on Unix/Linux/macOS",
                        "Or run as Administrator on Windows"
                    ]
                ),
                category="permissions",
                priority=3
            ))
        
        return suggestions
    
    def _suggest_validation_fixes(
        self,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Suggest fixes for validation errors."""
        suggestions = []
        
        if not isinstance(error, ValidationError):
            return suggestions
        
        error_msg = str(error).lower()
        
        # JSON validation errors
        if "json" in error_msg:
            suggestions.append(FixSuggestion(
                title="Fix JSON syntax",
                description="Validate and fix JSON formatting",
                confidence=0.8,
                action=RecoveryAction(
                    action_type=ActionType.FORMAT_CONVERSION,
                    description="Validate JSON format",
                    auto_fixable=False,
                    instructions=[
                        "Check JSON syntax for missing commas, brackets, or quotes",
                        "Use a JSON validator tool to identify specific issues",
                        "Ensure all strings are properly quoted",
                        "Check for trailing commas (not allowed in JSON)"
                    ]
                ),
                category="validation",
                priority=1,
                applicable_errors=["ValidationError"]
            ))
        
        # YAML validation errors  
        if "yaml" in error_msg:
            suggestions.append(FixSuggestion(
                title="Fix YAML syntax",
                description="Validate and fix YAML formatting",
                confidence=0.8,
                action=RecoveryAction(
                    action_type=ActionType.FORMAT_CONVERSION,
                    description="Validate YAML format",
                    auto_fixable=False,
                    instructions=[
                        "Check YAML indentation (use spaces, not tabs)",
                        "Ensure proper key-value separator (:)",
                        "Check for special characters that need quoting",
                        "Validate list formatting with proper dashes"
                    ]
                ),
                category="validation",
                priority=1,
                applicable_errors=["ValidationError"]
            ))
        
        # Missing required fields
        if "required" in error_msg or "missing" in error_msg:
            suggestions.append(FixSuggestion(
                title="Add missing required fields",
                description="Add all required fields to the configuration",
                confidence=0.9,
                action=RecoveryAction(
                    action_type=ActionType.CONFIGURATION_FIX,
                    description="Add missing required fields",
                    auto_fixable=False,
                    instructions=[
                        "Review the error message for specific missing fields",
                        "Add the required fields with appropriate values",
                        "Check documentation for field requirements"
                    ]
                ),
                category="validation",
                priority=1,
                applicable_errors=["ValidationError"]
            ))
        
        return suggestions
    
    def _suggest_configuration_fixes(
        self,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Suggest fixes for configuration errors."""
        suggestions = []
        
        if not isinstance(error, ConfigurationError):
            return suggestions
        
        suggestions.append(FixSuggestion(
            title="Check configuration file",
            description="Verify configuration file exists and is valid",
            confidence=0.8,
            action=RecoveryAction(
                action_type=ActionType.CONFIGURATION_FIX,
                description="Validate configuration",
                auto_fixable=False,
                instructions=[
                    "Check that the configuration file exists",
                    "Verify the file format is correct (JSON/YAML)",
                    "Ensure all required configuration keys are present",
                    "Check for typos in configuration keys"
                ]
            ),
            category="configuration",
            priority=1,
            applicable_errors=["ConfigurationError"]
        ))
        
        return suggestions
    
    def _suggest_dependency_fixes(
        self,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Suggest fixes for dependency-related errors."""
        suggestions = []
        
        error_msg = str(error).lower()
        
        # Import/module errors
        if "import" in error_msg or "module" in error_msg:
            suggestions.append(FixSuggestion(
                title="Install missing dependencies",
                description="Install required Python packages",
                confidence=0.7,
                action=RecoveryAction(
                    action_type=ActionType.DEPENDENCY_INSTALL,
                    description="Install missing packages",
                    auto_fixable=False,
                    instructions=[
                        "Identify the missing package from the error message",
                        "Install using: pip install <package-name>",
                        "Or install from requirements.txt: pip install -r requirements.txt"
                    ]
                ),
                category="dependencies",
                priority=2
            ))
        
        return suggestions
    
    def _suggest_format_fixes(
        self,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Suggest fixes for format-related errors."""
        suggestions = []
        
        error_msg = str(error).lower()
        
        if "encoding" in error_msg or "utf" in error_msg:
            suggestions.append(FixSuggestion(
                title="Fix file encoding",
                description="Convert file to UTF-8 encoding",
                confidence=0.8,
                action=RecoveryAction(
                    action_type=ActionType.FORMAT_CONVERSION,
                    description="Convert to UTF-8 encoding",
                    auto_fixable=True,
                    execute_func=lambda ctx: self._fix_encoding(file_path) if file_path else False
                ),
                category="format",
                priority=2
            ))
        
        return suggestions
    
    def _suggest_encoding_fixes(
        self,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Suggest fixes for encoding errors."""
        suggestions = []
        
        if isinstance(error, UnicodeDecodeError):
            suggestions.append(FixSuggestion(
                title="Fix character encoding",
                description="Convert file to proper encoding (UTF-8)",
                confidence=0.9,
                action=RecoveryAction(
                    action_type=ActionType.FORMAT_CONVERSION,
                    description="Fix file encoding",
                    auto_fixable=True,
                    execute_func=lambda ctx: self._fix_encoding(file_path) if file_path else False
                ),
                category="encoding",
                priority=1,
                applicable_errors=["UnicodeDecodeError"]
            ))
        
        return suggestions
    
    def _suggest_space_fixes(
        self,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Suggest fixes for disk space errors."""
        suggestions = []
        
        error_msg = str(error).lower()
        
        if "space" in error_msg or "disk full" in error_msg:
            suggestions.append(FixSuggestion(
                title="Free up disk space",
                description="Clear temporary files and free disk space",
                confidence=0.8,
                action=RecoveryAction(
                    action_type=ActionType.SYSTEM_CHECK,
                    description="Free up disk space",
                    auto_fixable=False,
                    instructions=[
                        "Check available disk space: df -h",
                        "Clear temporary files and caches",
                        "Remove unnecessary files",
                        "Consider moving files to external storage"
                    ]
                ),
                category="system",
                priority=1
            ))
        
        return suggestions
    
    def _suggest_path_fixes(
        self,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Suggest fixes for path-related errors."""
        suggestions = []
        
        error_msg = str(error).lower()
        
        if file_path and ("path" in error_msg or "directory" in error_msg):
            # Check for path length issues
            if len(str(file_path)) > 255:
                suggestions.append(FixSuggestion(
                    title="Shorten file path",
                    description="File path is too long for the file system",
                    confidence=0.7,
                    action=RecoveryAction(
                        action_type=ActionType.USER_INSTRUCTION,
                        description="Reduce path length",
                        auto_fixable=False,
                        instructions=[
                            "Move files to a location with shorter path",
                            "Rename directories to use shorter names",
                            "Use symbolic links to shorten paths"
                        ]
                    ),
                    category="file_system",
                    priority=2
                ))
            
            # Check for special characters
            if any(char in str(file_path) for char in ['<', '>', ':', '"', '|', '?', '*']):
                suggestions.append(FixSuggestion(
                    title="Remove invalid characters from path",
                    description="Path contains characters not allowed by the file system",
                    confidence=0.8,
                    action=RecoveryAction(
                        action_type=ActionType.FILE_OPERATION,
                        description="Rename to remove invalid characters",
                        auto_fixable=False,
                        instructions=[
                            "Remove or replace these characters: < > : \" | ? *",
                            "Use underscores or dashes instead",
                            "Ensure path only contains valid characters"
                        ]
                    ),
                    category="file_system",
                    priority=2
                ))
        
        return suggestions
    
    def _suggest_generic_fixes(
        self,
        error: Exception,
        file_path: Optional[Path],
        operation: Optional[str]
    ) -> List[FixSuggestion]:
        """Suggest generic fixes that apply to most errors."""
        suggestions = []
        
        # Retry suggestion
        suggestions.append(FixSuggestion(
            title="Retry operation",
            description="The issue might be temporary - try again",
            confidence=0.3,
            action=RecoveryAction(
                action_type=ActionType.USER_INSTRUCTION,
                description="Retry the operation",
                auto_fixable=False,
                instructions=["Wait a moment and try the operation again"]
            ),
            category="generic",
            priority=4
        ))
        
        # Check logs suggestion
        suggestions.append(FixSuggestion(
            title="Check logs for more details",
            description="Review detailed logs for additional error information",
            confidence=0.2,
            action=RecoveryAction(
                action_type=ActionType.USER_INSTRUCTION,
                description="Review logs",
                auto_fixable=False,
                instructions=[
                    "Check the application logs for more details",
                    "Look for related error messages",
                    "Enable verbose logging if available"
                ]
            ),
            category="generic",
            priority=5
        ))
        
        return suggestions
    
    # Helper methods for executing fixes
    
    async def _create_directory(self, path: Path) -> bool:
        """Create directory safely."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {path}: {e}")
            return False
    
    async def _fix_file_permissions(self, path: Path) -> bool:
        """Fix file permissions."""
        try:
            import stat
            
            if path.is_file():
                # Make file readable and writable by owner
                path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            elif path.is_dir():
                # Make directory accessible
                path.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | 
                          stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            
            return True
        except Exception as e:
            logger.error(f"Failed to fix permissions for {path}: {e}")
            return False
    
    async def _fix_encoding(self, path: Path) -> bool:
        """Fix file encoding by converting to UTF-8."""
        try:
            import chardet
            
            # Detect current encoding
            with open(path, 'rb') as f:
                raw_data = f.read()
            
            detected = chardet.detect(raw_data)
            if not detected['encoding']:
                return False
            
            # Convert to UTF-8
            with open(path, 'r', encoding=detected['encoding']) as f:
                content = f.read()
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        except Exception as e:
            logger.error(f"Failed to fix encoding for {path}: {e}")
            return False
    
    def _find_similar_files(self, directory: Path, filename: str) -> List[Path]:
        """Find files with similar names in directory."""
        try:
            import difflib
            
            if not directory.exists():
                return []
            
            all_files = [f for f in directory.iterdir() if f.is_file()]
            file_names = [f.name for f in all_files]
            
            # Find close matches
            matches = difflib.get_close_matches(filename, file_names, n=3, cutoff=0.6)
            
            return [directory / match for match in matches]
            
        except Exception:
            return []