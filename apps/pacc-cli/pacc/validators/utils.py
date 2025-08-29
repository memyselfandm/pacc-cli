"""Utility functions for PACC validators."""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

from .base import ValidationResult, BaseValidator


def parse_claude_frontmatter(yaml_content: str) -> Optional[Dict[str, Any]]:
    """Parse Claude Code frontmatter with lenient handling for unquoted brackets.
    
    Claude Code's frontmatter parser is more lenient than strict YAML.
    It allows unquoted square brackets in values like:
    - argument-hint: [--team <name>] [--project <name>]
    - argument-hint: [message]
    
    This function preprocesses the YAML to handle these cases before parsing.
    
    Args:
        yaml_content: The YAML frontmatter content to parse
        
    Returns:
        Parsed frontmatter as a dictionary, or None if parsing fails
    """
    if not yaml_content or not yaml_content.strip():
        return {}
    
    # Process line by line to handle problematic patterns
    lines = yaml_content.split('\n')
    processed_lines = []
    
    for line in lines:
        # Check if line has a key-value pair
        if ':' in line:
            # Split only on first colon to preserve values with colons
            parts = line.split(':', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                
                # Special handling for argument-hint field which should always be a string
                if key == 'argument-hint' and value.startswith('['):
                    # Claude Code treats this as a string, not a YAML list
                    # Always quote it to preserve as string
                    if not (value.startswith('"[') or value.startswith("'[")):
                        value = f'"{value}"'
                        line = f"{parts[0]}: {value}"
                # Check if value starts with [ and contains spaces (problematic for YAML)
                elif value and value.startswith('[') and ' ' in value:
                    # Check if it's not already a valid YAML list
                    if not (value.startswith('["') or value.startswith("['") or value == '[]'):
                        # This is likely Claude Code style brackets, auto-quote it
                        value = f'"{value}"'
                        line = f"{parts[0]}: {value}"
        
        processed_lines.append(line)
    
    processed_yaml = '\n'.join(processed_lines)
    
    try:
        result = yaml.safe_load(processed_yaml)
        
        # Post-process to ensure argument-hint is always a string
        if result and 'argument-hint' in result:
            hint = result['argument-hint']
            if isinstance(hint, list):
                # Convert list back to Claude Code format string
                if len(hint) == 1:
                    result['argument-hint'] = f"[{hint[0]}]"
                else:
                    result['argument-hint'] = str(hint)
        
        return result
    except yaml.YAMLError:
        # If it still fails, return None to let the validator handle the error
        return None


class ValidatorFactory:
    """Factory class for creating and managing validators."""
    
    _validators = None
    
    @classmethod
    def _initialize_validators(cls):
        """Initialize validators with late import to avoid circular dependencies."""
        if cls._validators is None:
            from .hooks import HooksValidator
            from .mcp import MCPValidator
            from .agents import AgentsValidator
            from .commands import CommandsValidator
            
            cls._validators = {
                "hooks": HooksValidator,
                "mcp": MCPValidator,
                "agents": AgentsValidator,
                "commands": CommandsValidator
            }
    
    @classmethod
    def get_validator(cls, extension_type: str, **kwargs) -> BaseValidator:
        """Get a validator instance for the specified extension type."""
        cls._initialize_validators()
        
        if extension_type not in cls._validators:
            raise ValueError(f"Unknown extension type: {extension_type}. "
                           f"Available types: {', '.join(cls._validators.keys())}")
        
        validator_class = cls._validators[extension_type]
        return validator_class(**kwargs)
    
    @classmethod
    def get_all_validators(cls, **kwargs) -> Dict[str, BaseValidator]:
        """Get all available validators."""
        cls._initialize_validators()
        
        return {
            ext_type: validator_class(**kwargs)
            for ext_type, validator_class in cls._validators.items()
        }
    
    @classmethod
    def get_supported_types(cls) -> List[str]:
        """Get list of supported extension types."""
        cls._initialize_validators()
        return list(cls._validators.keys())


class ValidationResultFormatter:
    """Formatter for validation results."""
    
    @staticmethod
    def format_result(result: ValidationResult, verbose: bool = False) -> str:
        """Format a single validation result as text."""
        lines = []
        
        # Header
        status = "✓ VALID" if result.is_valid else "✗ INVALID"
        lines.append(f"{status}: {result.file_path}")
        
        if result.extension_type:
            lines.append(f"Type: {result.extension_type}")
        
        # Errors
        if result.errors:
            lines.append(f"\nErrors ({len(result.errors)}):")
            for error in result.errors:
                lines.append(f"  • {error.code}: {error.message}")
                if verbose and error.suggestion:
                    lines.append(f"    Suggestion: {error.suggestion}")
        
        # Warnings
        if result.warnings:
            lines.append(f"\nWarnings ({len(result.warnings)}):")
            for warning in result.warnings:
                lines.append(f"  • {warning.code}: {warning.message}")
                if verbose and warning.suggestion:
                    lines.append(f"    Suggestion: {warning.suggestion}")
        
        # Metadata
        if verbose and result.metadata:
            lines.append(f"\nMetadata:")
            for key, value in result.metadata.items():
                lines.append(f"  {key}: {value}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_batch_results(results: List[ValidationResult], 
                           show_summary: bool = True,
                           verbose: bool = False) -> str:
        """Format multiple validation results."""
        lines = []
        
        if show_summary:
            valid_count = sum(1 for r in results if r.is_valid)
            total_count = len(results)
            error_count = sum(len(r.errors) for r in results)
            warning_count = sum(len(r.warnings) for r in results)
            
            lines.append(f"Validation Summary:")
            lines.append(f"  Valid: {valid_count}/{total_count}")
            lines.append(f"  Errors: {error_count}")
            lines.append(f"  Warnings: {warning_count}")
            lines.append("")
        
        # Individual results
        for i, result in enumerate(results):
            if i > 0:
                lines.append("")
            lines.append(ValidationResultFormatter.format_result(result, verbose=verbose))
        
        return "\n".join(lines)
    
    @staticmethod
    def format_as_json(result: Union[ValidationResult, List[ValidationResult]]) -> Dict[str, Any]:
        """Format validation result(s) as JSON-serializable dictionary."""
        if isinstance(result, list):
            return {
                "results": [ValidationResultFormatter._result_to_dict(r) for r in result],
                "summary": {
                    "total": len(result),
                    "valid": sum(1 for r in result if r.is_valid),
                    "invalid": sum(1 for r in result if not r.is_valid),
                    "total_errors": sum(len(r.errors) for r in result),
                    "total_warnings": sum(len(r.warnings) for r in result)
                }
            }
        else:
            return ValidationResultFormatter._result_to_dict(result)
    
    @staticmethod
    def _result_to_dict(result: ValidationResult) -> Dict[str, Any]:
        """Convert a ValidationResult to a dictionary."""
        return {
            "is_valid": result.is_valid,
            "file_path": result.file_path,
            "extension_type": result.extension_type,
            "errors": [
                {
                    "code": e.code,
                    "message": e.message,
                    "line_number": e.line_number,
                    "severity": e.severity,
                    "suggestion": e.suggestion
                }
                for e in result.errors
            ],
            "warnings": [
                {
                    "code": w.code,
                    "message": w.message,
                    "line_number": w.line_number,
                    "severity": w.severity,
                    "suggestion": w.suggestion
                }
                for w in result.warnings
            ],
            "metadata": result.metadata
        }


class ExtensionDetector:
    """Utility to detect extension types from files and directories.
    
    Uses hierarchical detection approach:
    1. pacc.json declarations (highest priority)
    2. Directory structure (secondary signal) 
    3. Content keywords (fallback only)
    """
    
    @staticmethod
    def detect_extension_type(file_path: Union[str, Path], project_dir: Optional[Union[str, Path]] = None) -> Optional[str]:
        """Detect the extension type of a file using hierarchical approach.
        
        Args:
            file_path: Path to the file to analyze
            project_dir: Optional project directory to look for pacc.json (highest priority)
                        If not provided, will try to detect from file_path location
            
        Returns:
            Extension type string ('hooks', 'mcp', 'agents', 'commands') or None if unknown
        """
        file_path = Path(file_path)
        
        if not file_path.exists() or not file_path.is_file():
            return None
        
        # Step 1: Check pacc.json declarations (highest priority)
        pacc_json_type = ExtensionDetector._check_pacc_json_declaration(file_path, project_dir)
        if pacc_json_type:
            return pacc_json_type
        
        # Step 2: Check directory structure (secondary signal)
        directory_type = ExtensionDetector._check_directory_structure(file_path)
        if directory_type:
            return directory_type
        
        # Step 3: Check content keywords (fallback only)
        content_type = ExtensionDetector._check_content_keywords(file_path)
        if content_type:
            return content_type
        
        return None
    
    @staticmethod
    def _check_pacc_json_declaration(file_path: Path, project_dir: Optional[Union[str, Path]]) -> Optional[str]:
        """Check if file is declared in pacc.json with specific type."""
        if project_dir is None:
            # Try to find project directory by looking for pacc.json in parent directories
            current_dir = file_path.parent
            while current_dir != current_dir.parent:  # Stop at filesystem root
                if (current_dir / "pacc.json").exists():
                    project_dir = current_dir
                    break
                current_dir = current_dir.parent
            
            if project_dir is None:
                return None
        
        project_dir = Path(project_dir)
        pacc_json_path = project_dir / "pacc.json"
        
        if not pacc_json_path.exists():
            return None
        
        try:
            # Import here to avoid circular imports
            from ..core.project_config import ProjectConfigManager
            
            config_manager = ProjectConfigManager()
            config = config_manager.load_project_config(project_dir)
            
            if not config or 'extensions' not in config:
                return None
            
            # Convert file path to relative path from project directory
            try:
                relative_path = file_path.relative_to(project_dir)
                relative_str = str(relative_path)
                
                # Also try with "./" prefix as used in pacc.json
                relative_with_prefix = f"./{relative_str}"
                
            except ValueError:
                # File is not within project directory
                relative_str = str(file_path)
                relative_with_prefix = relative_str
            
            # Check each extension type
            extensions = config.get('extensions', {})
            for ext_type, ext_list in extensions.items():
                if not isinstance(ext_list, list):
                    continue
                    
                for ext_spec in ext_list:
                    if not isinstance(ext_spec, dict) or 'source' not in ext_spec:
                        continue
                    
                    source = ext_spec['source']
                    
                    # Handle various source path formats
                    if source in [relative_str, relative_with_prefix, str(file_path), file_path.name]:
                        return ext_type
                        
                    # Handle source paths with different normalization
                    source_path = Path(source)
                    if source_path.name == file_path.name:
                        # Also check if the relative paths match when normalized
                        if source.startswith('./'):
                            source_normalized = Path(source[2:])
                        else:
                            source_normalized = source_path
                            
                        if str(source_normalized) == relative_str:
                            return ext_type
                            
        except Exception as e:
            # Log error but don't fail detection
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error checking pacc.json declarations: {e}")
        
        return None
    
    @staticmethod
    def _check_directory_structure(file_path: Path) -> Optional[str]:
        """Check directory structure for extension type hints."""
        parts = file_path.parts
        
        # Check for standard directory names in the path
        if any(part in ["commands", "cmd"] for part in parts):
            return "commands"
        elif any(part in ["agents", "agent"] for part in parts):
            return "agents"
        elif any(part in ["hooks", "hook"] for part in parts):
            return "hooks"
        elif any(part in ["mcp", "servers"] for part in parts):
            return "mcp"
        
        return None
    
    @staticmethod
    def _check_content_keywords(file_path: Path) -> Optional[str]:
        """Check file content for extension type keywords (fallback only)."""
        try:
            suffix = file_path.suffix.lower()
            name = file_path.name.lower()
            
            # MCP files by name pattern
            if name.endswith('.mcp.json') or name == 'mcp.json':
                return "mcp"
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(1024)  # Read first 1KB
                
            # Hooks (JSON files with hook patterns)
            if suffix == '.json':
                if any(event in content for event in ["PreToolUse", "PostToolUse", "Notification", "Stop"]):
                    return "hooks"
                elif "mcpServers" in content:
                    return "mcp"
            
            # Agents and Commands (Markdown files)  
            elif suffix == '.md':
                content_lower = content.lower()
                
                # Check for slash command patterns first (more specific)
                if content.startswith("# /") or "/:" in content or "slash command" in content_lower:
                    return "commands"
                
                # Check for frontmatter
                if content.startswith("---"):
                    frontmatter_end = content.find("---", 3)
                    if frontmatter_end != -1:
                        frontmatter = content[:frontmatter_end + 3]
                        frontmatter_lower = frontmatter.lower()
                        body = content[frontmatter_end + 3:]
                        body_lower = body.lower()
                        
                        # Strong indicators for commands (slash commands)
                        if any(pattern in content_lower for pattern in [
                            "# /", "usage:", "/:", "slash command", "command usage"
                        ]):
                            return "commands"
                        
                        # Strong indicators for agents 
                        if any(pattern in frontmatter_lower for pattern in [
                            "tools:", "permissions:", "enabled:"
                        ]) or any(pattern in body_lower for pattern in [
                            "this agent", "agent helps", "agent should"
                        ]):
                            return "agents"
                
                # General content analysis (weaker signals)
                if any(word in content_lower for word in ["usage:", "## usage", "# usage"]):
                    return "commands"
                elif any(word in content_lower for word in ["tool", "permission", "agent"]):
                    # This is the old logic that caused PACC-18 - now it's fallback only
                    # Only return "agents" if we have strong agent indicators
                    if any(strong_indicator in content_lower for strong_indicator in [
                        "this agent", "agent helps", "agent should", "agent provides"
                    ]):
                        return "agents"
                    # If it just has generic "tool" or "permission" keywords, it might be a command
                    return None  # Let other detection methods handle this
                    
        except Exception:
            # If we can't read the file, return None
            pass
        
        return None
    
    @staticmethod
    def scan_directory(directory_path: Union[str, Path], project_dir: Optional[Union[str, Path]] = None) -> Dict[str, List[Path]]:
        """Scan a directory and categorize files by extension type.
        
        Args:
            directory_path: Directory to scan for extensions
            project_dir: Optional project directory for pacc.json detection context
                        If None, will use directory_path as the project directory
        """
        directory = Path(directory_path)
        
        if not directory.exists() or not directory.is_dir():
            return {}
        
        # Use directory_path as project_dir if not specified
        if project_dir is None:
            project_dir = directory
        
        extensions_by_type = {
            "hooks": [],
            "mcp": [], 
            "agents": [],
            "commands": []
        }
        
        # Get all relevant files
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                ext_type = ExtensionDetector.detect_extension_type(file_path, project_dir=project_dir)
                if ext_type:
                    extensions_by_type[ext_type].append(file_path)
        
        return extensions_by_type


class ValidationRunner:
    """High-level interface for running validations."""
    
    def __init__(self, **validator_kwargs):
        """Initialize with optional validator configuration."""
        self.validator_kwargs = validator_kwargs
        self.validators = ValidatorFactory.get_all_validators(**validator_kwargs)
    
    def validate_file(self, file_path: Union[str, Path], 
                      extension_type: Optional[str] = None) -> ValidationResult:
        """Validate a single file, auto-detecting type if not specified."""
        file_path = Path(file_path)
        
        if extension_type is None:
            extension_type = ExtensionDetector.detect_extension_type(file_path)
            
        if extension_type is None:
            result = ValidationResult(is_valid=False, file_path=str(file_path))
            result.add_error(
                "UNKNOWN_EXTENSION_TYPE",
                f"Could not determine extension type for file: {file_path}",
                suggestion="Ensure file follows naming conventions or specify extension type explicitly"
            )
            return result
        
        if extension_type not in self.validators:
            result = ValidationResult(is_valid=False, file_path=str(file_path))
            result.add_error(
                "UNSUPPORTED_EXTENSION_TYPE",
                f"Unsupported extension type: {extension_type}",
                suggestion=f"Supported types: {', '.join(self.validators.keys())}"
            )
            return result
        
        validator = self.validators[extension_type]
        return validator.validate_single(file_path)
    
    def validate_directory(self, directory_path: Union[str, Path], 
                          extension_type: Optional[str] = None) -> Dict[str, List[ValidationResult]]:
        """Validate extensions in a directory, optionally filtered by type.
        
        Args:
            directory_path: Path to directory to validate
            extension_type: Optional extension type to filter by. If provided, only
                          validates extensions of this type.
        
        Returns:
            Dict mapping extension types to their validation results
        """
        extensions_by_type = ExtensionDetector.scan_directory(directory_path, project_dir=directory_path)
        results_by_type = {}
        
        # Filter by extension type if specified
        if extension_type is not None:
            if extension_type in extensions_by_type:
                extensions_by_type = {extension_type: extensions_by_type[extension_type]}
            else:
                extensions_by_type = {}
        
        for ext_type, file_paths in extensions_by_type.items():
            if file_paths:
                validator = self.validators[ext_type]
                results_by_type[ext_type] = validator.validate_batch(file_paths)
        
        return results_by_type
    
    def validate_mixed_files(self, file_paths: List[Union[str, Path]]) -> List[ValidationResult]:
        """Validate a list of files with mixed extension types."""
        results = []
        
        for file_path in file_paths:
            result = self.validate_file(file_path)
            results.append(result)
        
        return results


def create_validation_report(results: Union[ValidationResult, List[ValidationResult], 
                                         Dict[str, List[ValidationResult]]],
                           output_format: str = "text",
                           verbose: bool = False) -> str:
    """Create a formatted validation report."""
    
    if output_format == "json":
        import json
        return json.dumps(ValidationResultFormatter.format_as_json(results), indent=2)
    
    elif output_format == "text":
        if isinstance(results, dict):
            # Directory validation results
            lines = ["=== PACC Extension Validation Report ===\n"]
            
            total_files = sum(len(file_results) for file_results in results.values())
            total_valid = sum(sum(1 for r in file_results if r.is_valid) 
                            for file_results in results.values())
            
            lines.append(f"Summary: {total_valid}/{total_files} files valid\n")
            
            for ext_type, file_results in results.items():
                if file_results:
                    valid_count = sum(1 for r in file_results if r.is_valid)
                    lines.append(f"--- {ext_type.upper()} Extensions ({valid_count}/{len(file_results)} valid) ---")
                    lines.append(ValidationResultFormatter.format_batch_results(file_results, show_summary=False))
                    lines.append("")
            
            return "\n".join(lines)
        
        elif isinstance(results, list):
            return ValidationResultFormatter.format_batch_results(results, show_summary=True)
        
        else:
            return ValidationResultFormatter.format_result(results, verbose=verbose)
    
    else:
        raise ValueError(f"Unsupported output format: {output_format}")


# Convenience functions for common use cases
def validate_extension_file(file_path: Union[str, Path], 
                          extension_type: Optional[str] = None) -> ValidationResult:
    """Validate a single extension file."""
    runner = ValidationRunner()
    return runner.validate_file(file_path, extension_type)


def validate_extension_directory(directory_path: Union[str, Path], 
                                extension_type: Optional[str] = None) -> Dict[str, List[ValidationResult]]:
    """Validate extensions in a directory, optionally filtered by type.
    
    Args:
        directory_path: Path to directory containing extensions to validate
        extension_type: Optional extension type to filter by ('hooks', 'mcp', 'agents', 'commands').
                       If None, validates all extension types found in the directory.
    
    Returns:
        Dict mapping extension types to their validation results. When extension_type
        is specified, returns only that type (if found) or empty dict.
    """
    runner = ValidationRunner()
    return runner.validate_directory(directory_path, extension_type)