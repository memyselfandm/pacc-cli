"""Integration layer between security module and existing validators."""

from pathlib import Path
from typing import List, Optional, Dict, Any

from pacc.validators.base import ValidationResult, ValidationError
from pacc.plugins.security import (
    PluginSecurityManager, 
    PluginSecurityLevel,
    SecurityIssue,
    ThreatLevel
)
from pacc.plugins.sandbox import SandboxManager


def convert_security_issues_to_validation_errors(
    security_issues: List[SecurityIssue], 
    file_path: Optional[str] = None
) -> List[ValidationError]:
    """Convert security issues to validation errors."""
    validation_errors = []
    
    for issue in security_issues:
        # Map threat levels to validation severities
        severity_map = {
            ThreatLevel.LOW: "info",
            ThreatLevel.MEDIUM: "warning", 
            ThreatLevel.HIGH: "error",
            ThreatLevel.CRITICAL: "error"
        }
        
        validation_error = ValidationError(
            code=f"SECURITY_{issue.issue_type.upper()}",
            message=issue.description,
            file_path=issue.file_path or file_path,
            line_number=issue.line_number,
            severity=severity_map.get(issue.threat_level, "warning"),
            suggestion=issue.recommendation
        )
        validation_errors.append(validation_error)
    
    return validation_errors


def enhance_validation_with_security(
    result: ValidationResult,
    plugin_path: Path,
    plugin_type: str,
    security_level: PluginSecurityLevel = PluginSecurityLevel.STANDARD
) -> ValidationResult:
    """Enhance existing validation result with security analysis."""
    security_manager = PluginSecurityManager(security_level=security_level)
    
    try:
        # Run security validation
        is_safe, security_issues = security_manager.validate_plugin_security(
            plugin_path, plugin_type, security_level
        )
        
        # Convert security issues to validation errors
        security_errors = convert_security_issues_to_validation_errors(
            security_issues, str(plugin_path)
        )
        
        # Add security errors to the result
        for error in security_errors:
            if error.severity == "error":
                result.errors.append(error)
                result.is_valid = False
            else:
                result.warnings.append(error)
        
        # Add security metadata
        result.metadata['security_scan'] = {
            'is_safe': is_safe,
            'security_level': security_level.value,
            'total_issues': len(security_issues),
            'critical_issues': sum(1 for i in security_issues if i.threat_level == ThreatLevel.CRITICAL),
            'high_issues': sum(1 for i in security_issues if i.threat_level == ThreatLevel.HIGH),
            'medium_issues': sum(1 for i in security_issues if i.threat_level == ThreatLevel.MEDIUM),
            'low_issues': sum(1 for i in security_issues if i.threat_level == ThreatLevel.LOW)
        }
        
    except Exception as e:
        # Add error about security validation failure
        result.add_error(
            "SECURITY_VALIDATION_FAILED",
            f"Security validation encountered an error: {str(e)}",
            suggestion="Manual security review recommended"
        )
    
    return result


def validate_plugin_in_sandbox(
    plugin_path: Path,
    plugin_type: str
) -> ValidationResult:
    """Validate plugin using sandbox analysis."""
    result = ValidationResult(
        is_valid=True,
        file_path=str(plugin_path),
        extension_type=plugin_type
    )
    
    try:
        sandbox_manager = SandboxManager()
        is_safe, security_issues = sandbox_manager.validate_plugin_in_sandbox(
            plugin_path, plugin_type
        )
        
        # Convert security issues to validation errors
        validation_errors = convert_security_issues_to_validation_errors(
            security_issues, str(plugin_path)
        )
        
        # Add to result
        for error in validation_errors:
            if error.severity == "error":
                result.errors.append(error)
                result.is_valid = False
            else:
                result.warnings.append(error)
        
        # Add sandbox metadata
        result.metadata['sandbox_validation'] = {
            'is_safe': is_safe,
            'total_issues': len(security_issues),
            'sandbox_compatible': is_safe
        }
        
    except Exception as e:
        result.add_error(
            "SANDBOX_VALIDATION_FAILED",
            f"Sandbox validation encountered an error: {str(e)}",
            suggestion="Manual sandbox compatibility review recommended"
        )
    
    return result


class SecurityValidatorMixin:
    """Mixin class to add security validation to existing validators."""
    
    def __init__(self, *args, **kwargs):
        # Extract security-specific kwargs before calling super
        self.security_level = kwargs.pop('security_level', PluginSecurityLevel.STANDARD)
        self.enable_sandbox = kwargs.pop('enable_sandbox', False)
        super().__init__(*args, **kwargs)
    
    def validate_with_security(self, file_path: Path, plugin_type: str) -> ValidationResult:
        """Validate with integrated security checks."""
        # First run the base validation
        if hasattr(self, 'validate_single'):
            result = self.validate_single(file_path)
        else:
            result = ValidationResult(
                is_valid=True,
                file_path=str(file_path),
                extension_type=plugin_type
            )
        
        # Add security validation
        result = enhance_validation_with_security(
            result, file_path, plugin_type, self.security_level
        )
        
        # Add sandbox validation if enabled
        if self.enable_sandbox:
            sandbox_result = validate_plugin_in_sandbox(file_path, plugin_type)
            result.merge(sandbox_result)
        
        return result


def create_security_enhanced_validator(
    base_validator_class, 
    security_level: PluginSecurityLevel = PluginSecurityLevel.STANDARD,
    enable_sandbox: bool = False
):
    """Create a security-enhanced version of an existing validator class."""
    
    class SecurityEnhancedValidator(SecurityValidatorMixin, base_validator_class):
        def __init__(self, *args, **kwargs):
            # Set defaults that will be extracted by SecurityValidatorMixin
            if 'security_level' not in kwargs:
                kwargs['security_level'] = security_level
            if 'enable_sandbox' not in kwargs:
                kwargs['enable_sandbox'] = enable_sandbox
            super().__init__(*args, **kwargs)
        
        def validate_single(self, file_path):
            # Get the base validation result
            result = super().validate_single(file_path)
            
            # Enhance with security
            plugin_type = self.get_extension_type()
            result = enhance_validation_with_security(
                result, Path(file_path), plugin_type, self.security_level
            )
            
            # Add sandbox validation if enabled
            if self.enable_sandbox:
                sandbox_result = validate_plugin_in_sandbox(Path(file_path), plugin_type)
                result.merge(sandbox_result)
            
            return result
    
    return SecurityEnhancedValidator