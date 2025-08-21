"""Hooks validator for Claude Code hook extensions."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from .base import BaseValidator, ValidationResult

# Import advanced security scanning capabilities
try:
    from pacc.plugins.security import AdvancedCommandScanner, ThreatLevel
    ADVANCED_SECURITY_AVAILABLE = True
except ImportError:
    ADVANCED_SECURITY_AVAILABLE = False


class HooksValidator(BaseValidator):
    """Validator for Claude Code hook extensions."""
    
    # Valid hook event types according to Claude Code specification
    VALID_EVENT_TYPES = {
        "PreToolUse",
        "PostToolUse", 
        "Notification",
        "Stop"
    }
    
    # Valid matcher types for hooks
    VALID_MATCHER_TYPES = {
        "exact",
        "regex",
        "prefix", 
        "suffix",
        "contains"
    }
    
    def __init__(self, max_file_size: int = 10 * 1024 * 1024):
        """Initialize hooks validator."""
        super().__init__(max_file_size)
        
        # Initialize advanced security scanner if available
        if ADVANCED_SECURITY_AVAILABLE:
            self._security_scanner = AdvancedCommandScanner()
        else:
            self._security_scanner = None
        
        # Pre-compile regex patterns for performance (fallback)
        self._command_validation_patterns = {
            "shell_injection": re.compile(r'[;&|`$(){}[\]\\]'),
            "path_traversal": re.compile(r'\.\./|\.\.\\'),
            "dangerous_commands": re.compile(r'\b(rm|del|format|fdisk|mkfs|dd)\b', re.IGNORECASE)
        }
    
    def get_extension_type(self) -> str:
        """Return the extension type this validator handles."""
        return "hooks"
    
    def validate_single(self, file_path: Union[str, Path]) -> ValidationResult:
        """Validate a single hook file."""
        file_path = Path(file_path)
        result = ValidationResult(
            is_valid=True,
            file_path=str(file_path),
            extension_type=self.get_extension_type()
        )
        
        # Check file accessibility
        access_error = self._validate_file_accessibility(file_path)
        if access_error:
            result.add_error(
                access_error.code,
                access_error.message,
                suggestion=access_error.suggestion
            )
            return result
        
        # Validate JSON syntax
        json_error, hook_data = self._validate_json_syntax(file_path)
        if json_error:
            result.add_error(
                json_error.code,
                json_error.message,
                line_number=json_error.line_number,
                suggestion=json_error.suggestion
            )
            return result
        
        # Validate hook structure
        self._validate_hook_structure(hook_data, result)
        
        # Extract metadata for successful validations
        if result.is_valid and hook_data:
            result.metadata = {
                "name": hook_data.get("name", ""),
                "description": hook_data.get("description", ""),
                "event_types": hook_data.get("eventTypes", []),
                "version": hook_data.get("version", "1.0.0"),
                "has_matchers": bool(hook_data.get("matchers", [])),
                "command_count": len(hook_data.get("commands", []))
            }
        
        return result
    
    def _find_extension_files(self, directory: Path) -> List[Path]:
        """Find hook files in the given directory."""
        hook_files = []
        
        # Look for .json files that could be hooks
        for json_file in directory.rglob("*.json"):
            # Quick check if this might be a hook file
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    content = f.read(1024)  # Read first 1KB
                    if any(event in content for event in self.VALID_EVENT_TYPES):
                        hook_files.append(json_file)
            except Exception:
                # If we can't read it, let the full validation handle the error
                hook_files.append(json_file)
        
        return hook_files
    
    def _validate_hook_structure(self, hook_data: Dict[str, Any], result: ValidationResult) -> None:
        """Validate the overall structure of a hook."""
        file_path = result.file_path
        
        # Check that data is a dictionary
        if not isinstance(hook_data, dict):
            result.add_error(
                "INVALID_HOOK_FORMAT",
                "Hook must be a JSON object",
                suggestion="Ensure the root element is a JSON object {}"
            )
            return
        
        # Validate required fields
        required_fields = ["name", "eventTypes", "commands"]
        for field in required_fields:
            error = self._validate_field_type(hook_data, field, str if field == "name" else list, file_path)
            if error:
                result.add_error(error.code, error.message, suggestion=error.suggestion)
        
        # Validate optional fields
        optional_fields = {
            "description": str,
            "version": str,
            "enabled": bool,
            "matchers": list
        }
        
        for field, expected_type in optional_fields.items():
            error = self._validate_field_type(hook_data, field, expected_type, file_path, required=False)
            if error:
                result.add_error(error.code, error.message, suggestion=error.suggestion)
        
        # Skip detailed validation if required fields are missing
        if not all(field in hook_data for field in required_fields):
            return
        
        # Validate name format
        self._validate_hook_name(hook_data.get("name", ""), result)
        
        # Validate event types
        self._validate_event_types(hook_data.get("eventTypes", []), result)
        
        # Validate commands
        self._validate_commands(hook_data.get("commands", []), result)
        
        # Validate matchers if present
        if "matchers" in hook_data:
            self._validate_matchers(hook_data["matchers"], result)
        
        # Validate version format if present
        if "version" in hook_data:
            self._validate_version(hook_data["version"], result)
    
    def _validate_hook_name(self, name: str, result: ValidationResult) -> None:
        """Validate hook name format."""
        if not name:
            result.add_error(
                "EMPTY_HOOK_NAME",
                "Hook name cannot be empty",
                suggestion="Provide a descriptive name for the hook"
            )
            return
        
        # Check name format (alphanumeric, hyphens, underscores)
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            result.add_error(
                "INVALID_HOOK_NAME_FORMAT",
                f"Hook name '{name}' contains invalid characters",
                suggestion="Use only alphanumeric characters, hyphens, and underscores"
            )
        
        # Check name length
        if len(name) > 100:
            result.add_error(
                "HOOK_NAME_TOO_LONG",
                f"Hook name is too long ({len(name)} characters, max 100)",
                suggestion="Use a shorter, more concise name"
            )
        
        # Check for reserved names
        reserved_names = {"system", "default", "internal", "claude", "anthropic"}
        if name.lower() in reserved_names:
            result.add_warning(
                "RESERVED_HOOK_NAME",
                f"Hook name '{name}' is reserved and may cause conflicts",
                suggestion="Consider using a different name"
            )
    
    def _validate_event_types(self, event_types: List[str], result: ValidationResult) -> None:
        """Validate hook event types."""
        if not isinstance(event_types, list):
            result.add_error(
                "INVALID_EVENT_TYPES_FORMAT",
                "eventTypes must be an array",
                suggestion="Change eventTypes to an array of event type strings"
            )
            return
        
        if not event_types:
            result.add_error(
                "NO_EVENT_TYPES",
                "Hook must specify at least one event type",
                suggestion=f"Add one or more event types: {', '.join(self.VALID_EVENT_TYPES)}"
            )
            return
        
        invalid_types = []
        for event_type in event_types:
            if not isinstance(event_type, str):
                result.add_error(
                    "INVALID_EVENT_TYPE_FORMAT",
                    f"Event type must be a string, got {type(event_type).__name__}",
                    suggestion="Ensure all event types are strings"
                )
            elif event_type not in self.VALID_EVENT_TYPES:
                invalid_types.append(event_type)
        
        if invalid_types:
            result.add_error(
                "INVALID_EVENT_TYPES",
                f"Invalid event types: {', '.join(invalid_types)}",
                suggestion=f"Valid event types are: {', '.join(self.VALID_EVENT_TYPES)}"
            )
        
        # Check for duplicates
        if len(event_types) != len(set(event_types)):
            result.add_warning(
                "DUPLICATE_EVENT_TYPES",
                "Duplicate event types found",
                suggestion="Remove duplicate event types"
            )
    
    def _validate_commands(self, commands: List[Any], result: ValidationResult) -> None:
        """Validate hook commands."""
        if not isinstance(commands, list):
            result.add_error(
                "INVALID_COMMANDS_FORMAT",
                "commands must be an array",
                suggestion="Change commands to an array of command objects or strings"
            )
            return
        
        if not commands:
            result.add_error(
                "NO_COMMANDS",
                "Hook must specify at least one command",
                suggestion="Add one or more commands to execute"
            )
            return
        
        for i, command in enumerate(commands):
            self._validate_single_command(command, i, result)
    
    def _validate_single_command(self, command: Any, index: int, result: ValidationResult) -> None:
        """Validate a single command in the commands array."""
        command_prefix = f"Command {index + 1}"
        
        # Commands can be strings or objects
        if isinstance(command, str):
            self._validate_command_string(command, command_prefix, result)
        elif isinstance(command, dict):
            self._validate_command_object(command, command_prefix, result)
        else:
            result.add_error(
                "INVALID_COMMAND_TYPE",
                f"{command_prefix}: Command must be a string or object",
                suggestion="Use either a command string or a command object with 'command' field"
            )
    
    def _validate_command_string(self, command: str, prefix: str, result: ValidationResult) -> None:
        """Validate a command string."""
        if not command.strip():
            result.add_error(
                "EMPTY_COMMAND",
                f"{prefix}: Command cannot be empty",
                suggestion="Provide a valid command to execute"
            )
            return
        
        self._validate_command_security(command, prefix, result)
    
    def _validate_command_object(self, command: Dict[str, Any], prefix: str, result: ValidationResult) -> None:
        """Validate a command object."""
        # Required field: command
        if "command" not in command:
            result.add_error(
                "MISSING_COMMAND_FIELD",
                f"{prefix}: Command object must have 'command' field",
                suggestion="Add a 'command' field with the command to execute"
            )
            return
        
        command_str = command["command"]
        if not isinstance(command_str, str):
            result.add_error(
                "INVALID_COMMAND_FIELD_TYPE",
                f"{prefix}: 'command' field must be a string",
                suggestion="Change the 'command' field to a string value"
            )
            return
        
        self._validate_command_string(command_str, prefix, result)
        
        # Validate optional fields
        optional_fields = {
            "description": str,
            "timeout": (int, float),
            "workingDirectory": str,
            "environment": dict,
            "condition": str
        }
        
        for field, expected_type in optional_fields.items():
            if field in command:
                value = command[field]
                if not isinstance(value, expected_type):
                    result.add_error(
                        "INVALID_COMMAND_FIELD_TYPE",
                        f"{prefix}: '{field}' must be of type {expected_type.__name__ if not isinstance(expected_type, tuple) else ' or '.join(t.__name__ for t in expected_type)}",
                        suggestion=f"Change '{field}' to the correct type"
                    )
        
        # Validate timeout value
        if "timeout" in command:
            timeout = command["timeout"]
            if isinstance(timeout, (int, float)) and timeout <= 0:
                result.add_error(
                    "INVALID_TIMEOUT_VALUE",
                    f"{prefix}: timeout must be positive",
                    suggestion="Use a positive number for timeout in seconds"
                )
    
    def _validate_command_security(self, command: str, prefix: str, result: ValidationResult) -> None:
        """Validate command for comprehensive security issues."""
        # Use advanced security scanner if available
        if self._security_scanner:
            try:
                security_issues = self._security_scanner.scan_command(command, context=prefix)
                
                for issue in security_issues:
                    # Convert security issue to validation result format
                    if issue.threat_level == ThreatLevel.CRITICAL:
                        result.add_error(
                            f"CRITICAL_SECURITY_RISK",
                            f"{prefix}: {issue.description}",
                            suggestion=issue.recommendation
                        )
                    elif issue.threat_level == ThreatLevel.HIGH:
                        result.add_error(
                            f"HIGH_SECURITY_RISK",
                            f"{prefix}: {issue.description}",
                            suggestion=issue.recommendation
                        )
                    elif issue.threat_level == ThreatLevel.MEDIUM:
                        result.add_warning(
                            f"MEDIUM_SECURITY_RISK",
                            f"{prefix}: {issue.description}",
                            suggestion=issue.recommendation
                        )
                    else:  # LOW
                        result.add_warning(
                            f"LOW_SECURITY_RISK",
                            f"{prefix}: {issue.description}",
                            suggestion=issue.recommendation
                        )
                
                # If we found critical or high-risk issues, we're done
                if any(issue.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH] 
                       for issue in security_issues):
                    return
                
            except Exception as e:
                # Fall back to basic validation if advanced scanning fails
                result.add_warning(
                    "SECURITY_SCAN_ERROR",
                    f"{prefix}: Advanced security scan failed: {e}",
                    suggestion="Manual security review recommended"
                )
        
        # Fallback to basic security validation
        self._validate_command_security_basic(command, prefix, result)
    
    def _validate_command_security_basic(self, command: str, prefix: str, result: ValidationResult) -> None:
        """Basic security validation fallback."""
        # Check for shell injection patterns
        if self._command_validation_patterns["shell_injection"].search(command):
            result.add_warning(
                "POTENTIAL_SHELL_INJECTION",
                f"{prefix}: Command contains potentially dangerous characters",
                suggestion="Review command for shell injection vulnerabilities"
            )
        
        # Check for path traversal
        if self._command_validation_patterns["path_traversal"].search(command):
            result.add_warning(
                "POTENTIAL_PATH_TRAVERSAL",
                f"{prefix}: Command contains path traversal patterns",
                suggestion="Avoid using '../' in commands"
            )
        
        # Check for dangerous commands
        if self._command_validation_patterns["dangerous_commands"].search(command):
            result.add_warning(
                "DANGEROUS_COMMAND",
                f"{prefix}: Command contains potentially destructive operations",
                suggestion="Review command for data safety"
            )
        
        # Check command length
        if len(command) > 1000:
            result.add_warning(
                "LONG_COMMAND",
                f"{prefix}: Command is very long ({len(command)} characters)",
                suggestion="Consider breaking into multiple commands or using a script file"
            )
    
    def _validate_matchers(self, matchers: List[Any], result: ValidationResult) -> None:
        """Validate hook matchers."""
        if not isinstance(matchers, list):
            result.add_error(
                "INVALID_MATCHERS_FORMAT",
                "matchers must be an array",
                suggestion="Change matchers to an array of matcher objects"
            )
            return
        
        for i, matcher in enumerate(matchers):
            self._validate_single_matcher(matcher, i, result)
    
    def _validate_single_matcher(self, matcher: Any, index: int, result: ValidationResult) -> None:
        """Validate a single matcher object."""
        matcher_prefix = f"Matcher {index + 1}"
        
        if not isinstance(matcher, dict):
            result.add_error(
                "INVALID_MATCHER_TYPE",
                f"{matcher_prefix}: Matcher must be an object",
                suggestion="Use a matcher object with 'type' and 'pattern' fields"
            )
            return
        
        # Required fields
        required_fields = ["type", "pattern"]
        for field in required_fields:
            if field not in matcher:
                result.add_error(
                    "MISSING_MATCHER_FIELD",
                    f"{matcher_prefix}: Missing required field '{field}'",
                    suggestion=f"Add '{field}' field to the matcher"
                )
        
        if not all(field in matcher for field in required_fields):
            return
        
        # Validate matcher type
        matcher_type = matcher["type"]
        if not isinstance(matcher_type, str):
            result.add_error(
                "INVALID_MATCHER_TYPE_FORMAT",
                f"{matcher_prefix}: 'type' must be a string",
                suggestion="Set 'type' to a string value"
            )
        elif matcher_type not in self.VALID_MATCHER_TYPES:
            result.add_error(
                "INVALID_MATCHER_TYPE_VALUE",
                f"{matcher_prefix}: Invalid matcher type '{matcher_type}'",
                suggestion=f"Valid matcher types are: {', '.join(self.VALID_MATCHER_TYPES)}"
            )
        
        # Validate pattern
        pattern = matcher["pattern"]
        if not isinstance(pattern, str):
            result.add_error(
                "INVALID_MATCHER_PATTERN_TYPE",
                f"{matcher_prefix}: 'pattern' must be a string",
                suggestion="Set 'pattern' to a string value"
            )
        elif not pattern:
            result.add_error(
                "EMPTY_MATCHER_PATTERN",
                f"{matcher_prefix}: 'pattern' cannot be empty",
                suggestion="Provide a pattern to match against"
            )
        elif matcher_type == "regex":
            # Validate regex pattern
            try:
                re.compile(pattern)
            except re.error as e:
                result.add_error(
                    "INVALID_REGEX_PATTERN",
                    f"{matcher_prefix}: Invalid regex pattern: {e}",
                    suggestion="Fix the regex pattern syntax"
                )
        
        # Validate optional fields
        if "target" in matcher:
            target = matcher["target"]
            if not isinstance(target, str):
                result.add_error(
                    "INVALID_MATCHER_TARGET_TYPE",
                    f"{matcher_prefix}: 'target' must be a string",
                    suggestion="Set 'target' to a string value"
                )
            # Note: target validation would depend on Claude Code's specification
            # for what targets are valid
        
        if "caseSensitive" in matcher:
            case_sensitive = matcher["caseSensitive"]
            if not isinstance(case_sensitive, bool):
                result.add_error(
                    "INVALID_MATCHER_CASE_SENSITIVE_TYPE",
                    f"{matcher_prefix}: 'caseSensitive' must be a boolean",
                    suggestion="Set 'caseSensitive' to true or false"
                )
    
    def _validate_version(self, version: str, result: ValidationResult) -> None:
        """Validate version format (basic semantic versioning)."""
        if not isinstance(version, str):
            result.add_error(
                "INVALID_VERSION_TYPE",
                "version must be a string",
                suggestion="Set version to a string value like '1.0.0'"
            )
            return
        
        # Basic semantic versioning check
        semver_pattern = r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?(?:\+[a-zA-Z0-9.-]+)?$'
        if not re.match(semver_pattern, version):
            result.add_warning(
                "INVALID_VERSION_FORMAT",
                f"Version '{version}' does not follow semantic versioning",
                suggestion="Use semantic versioning format like '1.0.0'"
            )