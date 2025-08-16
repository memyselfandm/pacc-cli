"""Utility functions for PACC validators."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

from .base import ValidationResult, BaseValidator
from .hooks import HooksValidator
from .mcp import MCPValidator
from .agents import AgentsValidator
from .commands import CommandsValidator


class ValidatorFactory:
    """Factory class for creating and managing validators."""
    
    _validators = {
        "hooks": HooksValidator,
        "mcp": MCPValidator,
        "agents": AgentsValidator,
        "commands": CommandsValidator
    }
    
    @classmethod
    def get_validator(cls, extension_type: str, **kwargs) -> BaseValidator:
        """Get a validator instance for the specified extension type."""
        if extension_type not in cls._validators:
            raise ValueError(f"Unknown extension type: {extension_type}. "
                           f"Available types: {', '.join(cls._validators.keys())}")
        
        validator_class = cls._validators[extension_type]
        return validator_class(**kwargs)
    
    @classmethod
    def get_all_validators(cls, **kwargs) -> Dict[str, BaseValidator]:
        """Get all available validators."""
        return {
            ext_type: validator_class(**kwargs)
            for ext_type, validator_class in cls._validators.items()
        }
    
    @classmethod
    def get_supported_types(cls) -> List[str]:
        """Get list of supported extension types."""
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
                           show_summary: bool = True) -> str:
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
            lines.append(ValidationResultFormatter.format_result(result))
        
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
    """Utility to detect extension types from files and directories."""
    
    @staticmethod
    def detect_extension_type(file_path: Union[str, Path]) -> Optional[str]:
        """Detect the extension type of a file."""
        file_path = Path(file_path)
        
        if not file_path.exists() or not file_path.is_file():
            return None
        
        # Check file extension and name patterns
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()
        
        # MCP files
        if name.endswith('.mcp.json') or name == 'mcp.json':
            return "mcp"
        
        # Check content for file type detection
        try:
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
                if content.startswith("---") and ("name:" in content or "description:" in content):
                    # Has YAML frontmatter, check content type
                    if any(word in content.lower() for word in ["agent", "tool", "permission"]):
                        return "agents"
                    elif any(word in content.lower() for word in ["command", "usage:", "/", "slash"]):
                        return "commands"
                elif "/" in content and ("command" in content.lower() or "usage" in content.lower()):
                    return "commands"
                    
        except Exception:
            # If we can't read the file, try to guess from name/location
            pass
        
        # Fallback based on directory structure
        parts = file_path.parts
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
    def scan_directory(directory_path: Union[str, Path]) -> Dict[str, List[Path]]:
        """Scan a directory and categorize files by extension type."""
        directory = Path(directory_path)
        
        if not directory.exists() or not directory.is_dir():
            return {}
        
        extensions_by_type = {
            "hooks": [],
            "mcp": [], 
            "agents": [],
            "commands": []
        }
        
        # Get all relevant files
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                ext_type = ExtensionDetector.detect_extension_type(file_path)
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
    
    def validate_directory(self, directory_path: Union[str, Path]) -> Dict[str, List[ValidationResult]]:
        """Validate all extensions in a directory, organized by type."""
        extensions_by_type = ExtensionDetector.scan_directory(directory_path)
        results_by_type = {}
        
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


def validate_extension_directory(directory_path: Union[str, Path]) -> Dict[str, List[ValidationResult]]:
    """Validate all extensions in a directory."""
    runner = ValidationRunner()
    return runner.validate_directory(directory_path)