"""Security measures and hardening for PACC source management."""

import os
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Set, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum

from pacc.errors.exceptions import SecurityError, ValidationError


class ThreatLevel(Enum):
    """Threat level enumeration for security issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityIssue:
    """Represents a security issue found during scanning."""
    threat_level: ThreatLevel
    issue_type: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    recommendation: Optional[str] = None
    cve_references: Optional[List[str]] = None


class PathTraversalProtector:
    """Protects against path traversal attacks."""
    
    def __init__(self, allowed_base_paths: Optional[List[Path]] = None):
        """Initialize path traversal protector.
        
        Args:
            allowed_base_paths: List of base paths that are allowed for access
        """
        self.allowed_base_paths = allowed_base_paths or []
        self.dangerous_patterns = [
            '..',
            '..\\',
            '../',
            '..\\',
            '%2e%2e',
            '%2e%2e%2f',
            '%2e%2e%5c',
            '....\\\\',
            '....///',
        ]
    
    def is_safe_path(self, path: Union[str, Path], base_path: Optional[Path] = None) -> bool:
        """Check if a path is safe from traversal attacks.
        
        Args:
            path: Path to check
            base_path: Optional base path to restrict access to
            
        Returns:
            True if path is safe, False otherwise
        """
        try:
            path_str = str(path)
            
            # Check for dangerous patterns
            for pattern in self.dangerous_patterns:
                if pattern in path_str.lower():
                    return False
            
            # Resolve and check actual path
            resolved_path = Path(path).resolve()
            
            # If base path is provided, ensure resolved path is within it
            if base_path:
                base_resolved = Path(base_path).resolve()
                try:
                    resolved_path.relative_to(base_resolved)
                except ValueError:
                    return False
            
            # Check against allowed base paths
            if self.allowed_base_paths:
                for allowed_base in self.allowed_base_paths:
                    try:
                        resolved_path.relative_to(allowed_base.resolve())
                        return True
                    except ValueError:
                        continue
                return False
            
            return True
            
        except (OSError, ValueError, RuntimeError):
            return False
    
    def sanitize_path(self, path: Union[str, Path]) -> Path:
        """Sanitize a path by removing dangerous components.
        
        Args:
            path: Path to sanitize
            
        Returns:
            Sanitized path
            
        Raises:
            SecurityError: If path cannot be safely sanitized
        """
        try:
            # Convert to Path object
            path_obj = Path(path)
            
            # Check if already safe
            if self.is_safe_path(path_obj):
                return path_obj.resolve()
            
            # Remove dangerous components
            parts = []
            for part in path_obj.parts:
                # Skip dangerous parts
                if part in ['..', '.']:
                    continue
                # Decode any URL encoding
                clean_part = part.replace('%2e', '.').replace('%2f', '/').replace('%5c', '\\')
                if clean_part not in ['..', '.']:
                    parts.append(part)
            
            if not parts:
                raise SecurityError(
                    "Path cannot be safely sanitized",
                    security_check="path_sanitization"
                )
            
            sanitized = Path(*parts)
            
            # Final safety check
            if not self.is_safe_path(sanitized):
                raise SecurityError(
                    f"Path remains unsafe after sanitization: {sanitized}",
                    security_check="path_sanitization"
                )
            
            return sanitized.resolve()
            
        except Exception as e:
            raise SecurityError(
                f"Failed to sanitize path: {str(e)}",
                security_check="path_sanitization"
            ) from e


class InputSanitizer:
    """Sanitizes various types of input to prevent injection attacks."""
    
    def __init__(self):
        """Initialize input sanitizer."""
        # Patterns for detecting potentially malicious content
        self.suspicious_patterns = {
            'code_injection': [
                r'import\s+os',
                r'import\s+subprocess',
                r'import\s+sys',
                r'__import__',
                r'eval\s*\(',
                r'exec\s*\(',
                r'compile\s*\(',
                r'globals\s*\(',
                r'locals\s*\(',
                r'vars\s*\(',
                r'dir\s*\(',
                r'getattr\s*\(',
                r'setattr\s*\(',
                r'hasattr\s*\(',
                r'delattr\s*\(',
            ],
            'command_injection': [
                r';\s*rm\s+',
                r';\s*del\s+',
                r';\s*format\s+',
                r';\s*shutdown\s+',
                r';\s*reboot\s+',
                r'&\s*rm\s+',
                r'\|\s*rm\s+',
                r'`.*`',
                r'\$\(.*\)',
                r'nc\s+-',
                r'netcat\s+-',
                r'curl\s+.*\|\s*sh',
                r'wget\s+.*\|\s*sh',
            ],
            'file_operations': [
                r'open\s*\(',
                r'file\s*\(',
                r'with\s+open',
                r'\.read\s*\(',
                r'\.write\s*\(',
                r'\.delete\s*\(',
                r'\.remove\s*\(',
                r'\.unlink\s*\(',
                r'\.rmdir\s*\(',
                r'\.mkdir\s*\(',
            ],
            'network_operations': [
                r'socket\s*\(',
                r'urllib\.',
                r'requests\.',
                r'http\.',
                r'ftp\.',
                r'telnet\.',
                r'ssh\.',
            ]
        }
        
        # Maximum safe lengths for various input types
        self.max_lengths = {
            'filename': 255,
            'description': 1000,
            'version': 50,
            'name': 100,
            'command': 500,
            'url': 2000,
        }
    
    def scan_for_threats(self, content: str, content_type: str = "general") -> List[SecurityIssue]:
        """Scan content for security threats.
        
        Args:
            content: Content to scan
            content_type: Type of content being scanned
            
        Returns:
            List of security issues found
        """
        issues = []
        
        try:
            # Check content length
            max_length = self.max_lengths.get(content_type, 10000)
            if len(content) > max_length:
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="excessive_length",
                    description=f"Content exceeds maximum safe length ({len(content)} > {max_length})",
                    recommendation="Reduce content length or split into smaller parts"
                ))
            
            # Scan for suspicious patterns
            for category, patterns in self.suspicious_patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        line_number = content[:match.start()].count('\n') + 1
                        
                        threat_level = ThreatLevel.HIGH
                        if category == 'file_operations':
                            threat_level = ThreatLevel.MEDIUM
                        elif category == 'network_operations':
                            threat_level = ThreatLevel.MEDIUM
                        
                        issues.append(SecurityIssue(
                            threat_level=threat_level,
                            issue_type=f"suspicious_{category}",
                            description=f"Potentially dangerous {category.replace('_', ' ')}: {match.group()}",
                            line_number=line_number,
                            recommendation=f"Review and validate {category.replace('_', ' ')} usage"
                        ))
            
            # Check for encoded content that might hide malicious code
            if self._has_suspicious_encoding(content):
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.HIGH,
                    issue_type="suspicious_encoding",
                    description="Content contains suspicious encoding that might hide malicious code",
                    recommendation="Decode and verify all encoded content"
                ))
            
        except Exception as e:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.LOW,
                issue_type="scan_error",
                description=f"Error during security scan: {str(e)}",
                recommendation="Manual review recommended"
            ))
        
        return issues
    
    def _has_suspicious_encoding(self, content: str) -> bool:
        """Check if content has suspicious encoding patterns."""
        suspicious_encodings = [
            r'\\x[0-9a-fA-F]{2}',  # Hex encoding
            r'\\u[0-9a-fA-F]{4}',  # Unicode encoding
            r'%[0-9a-fA-F]{2}',    # URL encoding
            r'&#\d+;',             # HTML entity encoding
            r'&[a-zA-Z]+;',        # HTML named entities
            r'\\[0-7]{3}',         # Octal encoding
        ]
        
        encoded_count = 0
        for pattern in suspicious_encodings:
            matches = re.findall(pattern, content)
            encoded_count += len(matches)
        
        # If more than 10% of the content appears to be encoded, it's suspicious
        if len(content) > 0:
            encoded_ratio = encoded_count / len(content)
            return encoded_ratio > 0.1
        
        return False
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename for safe usage.
        
        Args:
            filename: Filename to sanitize
            
        Returns:
            Sanitized filename
            
        Raises:
            SecurityError: If filename cannot be safely sanitized
        """
        if not filename or not filename.strip():
            raise SecurityError(
                "Empty filename not allowed",
                security_check="filename_sanitization"
            )
        
        # Remove dangerous characters
        dangerous_chars = r'[<>:"/\\|?*\x00-\x1f]'
        sanitized = re.sub(dangerous_chars, '_', filename)
        
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        
        # Check for reserved names (Windows)
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        
        name_without_ext = sanitized.split('.')[0].upper()
        if name_without_ext in reserved_names:
            sanitized = f"safe_{sanitized}"
        
        # Ensure reasonable length
        if len(sanitized) > self.max_lengths['filename']:
            name, ext = os.path.splitext(sanitized)
            max_name_len = self.max_lengths['filename'] - len(ext)
            sanitized = name[:max_name_len] + ext
        
        if not sanitized:
            raise SecurityError(
                "Filename cannot be safely sanitized",
                security_check="filename_sanitization"
            )
        
        return sanitized


class FileContentScanner:
    """Scans file content for security threats."""
    
    def __init__(self, max_file_size: int = 50 * 1024 * 1024):  # 50MB default
        """Initialize file content scanner.
        
        Args:
            max_file_size: Maximum file size to scan in bytes
        """
        self.max_file_size = max_file_size
        self.input_sanitizer = InputSanitizer()
        
        # File type specific scanners
        self.binary_signatures = {
            # Executable file signatures
            b'\x4d\x5a': 'PE executable (Windows)',
            b'\x7f\x45\x4c\x46': 'ELF executable (Linux)',
            b'\xfe\xed\xfa\xce': 'Mach-O executable (macOS)',
            b'\xfe\xed\xfa\xcf': 'Mach-O executable (macOS 64-bit)',
            b'\xca\xfe\xba\xbe': 'Java class file',
            b'\x50\x4b\x03\x04': 'ZIP archive',
            b'\x1f\x8b\x08': 'GZIP archive',
            b'\x42\x5a\x68': 'BZIP2 archive',
        }
    
    def scan_file(self, file_path: Path) -> List[SecurityIssue]:
        """Scan a file for security threats.
        
        Args:
            file_path: Path to file to scan
            
        Returns:
            List of security issues found
        """
        issues = []
        
        try:
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="file_too_large",
                    description=f"File exceeds maximum safe size ({file_size} > {self.max_file_size})",
                    file_path=str(file_path),
                    recommendation="Review file necessity and reduce size if possible"
                ))
                return issues  # Don't scan oversized files
            
            # Check for binary signatures
            with open(file_path, 'rb') as f:
                header = f.read(16)
            
            for signature, file_type in self.binary_signatures.items():
                if header.startswith(signature):
                    issues.append(SecurityIssue(
                        threat_level=ThreatLevel.HIGH,
                        issue_type="binary_executable",
                        description=f"File appears to be a binary executable: {file_type}",
                        file_path=str(file_path),
                        recommendation="Binary executables should not be included in extension packages"
                    ))
                    return issues  # Don't scan binary files further
            
            # Try to read as text and scan content
            try:
                content = file_path.read_text(encoding='utf-8')
                content_issues = self.input_sanitizer.scan_for_threats(content, "file_content")
                
                for issue in content_issues:
                    issue.file_path = str(file_path)
                    issues.append(issue)
            
            except UnicodeDecodeError:
                # File contains binary data
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="binary_content",
                    description="File contains binary data but has text extension",
                    file_path=str(file_path),
                    recommendation="Verify file format matches extension"
                ))
        
        except Exception as e:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.LOW,
                issue_type="scan_error",
                description=f"Error scanning file: {str(e)}",
                file_path=str(file_path),
                recommendation="Manual review recommended"
            ))
        
        return issues
    
    def calculate_file_hash(self, file_path: Path, algorithm: str = "sha256") -> str:
        """Calculate hash of file content for integrity verification.
        
        Args:
            file_path: Path to file
            algorithm: Hash algorithm to use
            
        Returns:
            Hexadecimal hash string
        """
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()


class SecurityPolicy:
    """Manages security policies and enforcement."""
    
    def __init__(self):
        """Initialize security policy."""
        self.policies = {
            'max_file_size': 50 * 1024 * 1024,  # 50MB
            'allowed_extensions': {'.json', '.yaml', '.yml', '.md', '.txt'},
            'blocked_extensions': {'.exe', '.bat', '.sh', '.ps1', '.com', '.scr', '.dll'},
            'max_content_length': 1024 * 1024,  # 1MB for text content
            'require_hash_verification': False,
            'allow_binary_content': False,
            'max_archive_extraction_size': 100 * 1024 * 1024,  # 100MB
            'scan_archived_content': True,
        }
        
        self.enforcement_levels = {
            ThreatLevel.LOW: 'log',      # Log but allow
            ThreatLevel.MEDIUM: 'warn',  # Warn but allow with confirmation
            ThreatLevel.HIGH: 'block',   # Block by default
            ThreatLevel.CRITICAL: 'block'  # Always block
        }
    
    def set_policy(self, policy_name: str, value) -> None:
        """Set a security policy value.
        
        Args:
            policy_name: Name of policy to set
            value: Value to set
        """
        if policy_name not in self.policies:
            raise ValueError(f"Unknown policy: {policy_name}")
        
        self.policies[policy_name] = value
    
    def get_policy(self, policy_name: str):
        """Get a security policy value.
        
        Args:
            policy_name: Name of policy to get
            
        Returns:
            Policy value
        """
        return self.policies.get(policy_name)
    
    def enforce_policy(self, issues: List[SecurityIssue]) -> Tuple[List[SecurityIssue], List[SecurityIssue]]:
        """Enforce security policies on found issues.
        
        Args:
            issues: List of security issues
            
        Returns:
            Tuple of (blocking_issues, warning_issues)
        """
        blocking_issues = []
        warning_issues = []
        
        for issue in issues:
            enforcement = self.enforcement_levels.get(issue.threat_level, 'block')
            
            if enforcement == 'block':
                blocking_issues.append(issue)
            elif enforcement == 'warn':
                warning_issues.append(issue)
            # 'log' level issues are neither blocking nor warning
        
        return blocking_issues, warning_issues
    
    def is_extension_allowed(self, extension: str) -> bool:
        """Check if file extension is allowed by policy.
        
        Args:
            extension: File extension to check
            
        Returns:
            True if extension is allowed
        """
        extension = extension.lower()
        
        # Check blocked extensions first
        if extension in self.policies['blocked_extensions']:
            return False
        
        # Check allowed extensions
        allowed = self.policies['allowed_extensions']
        if allowed and extension not in allowed:
            return False
        
        return True


class SecurityAuditor:
    """Performs comprehensive security audits of PACC operations."""
    
    def __init__(self):
        """Initialize security auditor."""
        self.path_protector = PathTraversalProtector()
        self.content_scanner = FileContentScanner()
        self.policy = SecurityPolicy()
        
        # Audit log
        self.audit_log = []
    
    def audit_file(self, file_path: Path, context: str = "general") -> Dict:
        """Perform comprehensive security audit of a file.
        
        Args:
            file_path: Path to file to audit
            context: Context of the audit
            
        Returns:
            Audit result dictionary
        """
        audit_result = {
            'file_path': str(file_path),
            'context': context,
            'timestamp': self._get_timestamp(),
            'issues': [],
            'is_safe': True,
            'risk_score': 0,
            'recommendations': []
        }
        
        try:
            # Check path safety
            if not self.path_protector.is_safe_path(file_path):
                audit_result['issues'].append(SecurityIssue(
                    threat_level=ThreatLevel.HIGH,
                    issue_type="unsafe_path",
                    description="File path appears unsafe (possible path traversal)",
                    file_path=str(file_path),
                    recommendation="Use only safe, validated file paths"
                ))
            
            # Check extension policy
            if not self.policy.is_extension_allowed(file_path.suffix):
                audit_result['issues'].append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="disallowed_extension",
                    description=f"File extension '{file_path.suffix}' is not allowed by policy",
                    file_path=str(file_path),
                    recommendation="Use only allowed file extensions"
                ))
            
            # Scan file content
            if file_path.exists():
                content_issues = self.content_scanner.scan_file(file_path)
                audit_result['issues'].extend(content_issues)
            
            # Calculate risk score
            audit_result['risk_score'] = self._calculate_risk_score(audit_result['issues'])
            
            # Determine if file is safe
            blocking_issues, warning_issues = self.policy.enforce_policy(audit_result['issues'])
            audit_result['is_safe'] = len(blocking_issues) == 0
            
            # Generate recommendations
            audit_result['recommendations'] = self._generate_recommendations(audit_result['issues'])
            
            # Log audit
            self.audit_log.append(audit_result)
        
        except Exception as e:
            audit_result['issues'].append(SecurityIssue(
                threat_level=ThreatLevel.LOW,
                issue_type="audit_error",
                description=f"Error during security audit: {str(e)}",
                recommendation="Manual security review recommended"
            ))
            audit_result['is_safe'] = False
        
        return audit_result
    
    def audit_directory(self, directory_path: Path, recursive: bool = True) -> Dict:
        """Perform security audit of an entire directory.
        
        Args:
            directory_path: Path to directory to audit
            recursive: Whether to audit recursively
            
        Returns:
            Directory audit result
        """
        audit_result = {
            'directory_path': str(directory_path),
            'timestamp': self._get_timestamp(),
            'file_audits': [],
            'summary': {
                'total_files': 0,
                'safe_files': 0,
                'unsafe_files': 0,
                'total_issues': 0,
                'max_risk_score': 0,
            },
            'is_safe': True
        }
        
        try:
            # Find files to audit
            if recursive:
                files = directory_path.rglob('*')
            else:
                files = directory_path.iterdir()
            
            files = [f for f in files if f.is_file()]
            
            # Audit each file
            for file_path in files:
                file_audit = self.audit_file(file_path, context="directory_scan")
                audit_result['file_audits'].append(file_audit)
                
                # Update summary
                audit_result['summary']['total_files'] += 1
                if file_audit['is_safe']:
                    audit_result['summary']['safe_files'] += 1
                else:
                    audit_result['summary']['unsafe_files'] += 1
                
                audit_result['summary']['total_issues'] += len(file_audit['issues'])
                audit_result['summary']['max_risk_score'] = max(
                    audit_result['summary']['max_risk_score'],
                    file_audit['risk_score']
                )
            
            # Determine overall safety
            audit_result['is_safe'] = audit_result['summary']['unsafe_files'] == 0
        
        except Exception as e:
            audit_result['is_safe'] = False
            audit_result['error'] = str(e)
        
        return audit_result
    
    def _calculate_risk_score(self, issues: List[SecurityIssue]) -> int:
        """Calculate numeric risk score from security issues.
        
        Args:
            issues: List of security issues
            
        Returns:
            Risk score (0-100)
        """
        score = 0
        
        for issue in issues:
            if issue.threat_level == ThreatLevel.LOW:
                score += 5
            elif issue.threat_level == ThreatLevel.MEDIUM:
                score += 15
            elif issue.threat_level == ThreatLevel.HIGH:
                score += 30
            elif issue.threat_level == ThreatLevel.CRITICAL:
                score += 50
        
        return min(score, 100)  # Cap at 100
    
    def _generate_recommendations(self, issues: List[SecurityIssue]) -> List[str]:
        """Generate security recommendations from issues.
        
        Args:
            issues: List of security issues
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        for issue in issues:
            if issue.recommendation and issue.recommendation not in recommendations:
                recommendations.append(issue.recommendation)
        
        # Add general recommendations based on issue types
        issue_types = {issue.issue_type for issue in issues}
        
        if any('injection' in issue_type for issue_type in issue_types):
            recommendations.append("Review all user inputs for injection vulnerabilities")
        
        if any('encoding' in issue_type for issue_type in issue_types):
            recommendations.append("Verify all encoded content is legitimate")
        
        if any('binary' in issue_type for issue_type in issue_types):
            recommendations.append("Remove binary files from extension packages")
        
        return recommendations
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for audit logging."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def export_audit_log(self, file_path: Path) -> None:
        """Export audit log to file.
        
        Args:
            file_path: Path to export file
        """
        import json
        
        # Convert SecurityIssue objects to dictionaries
        exportable_log = []
        for entry in self.audit_log:
            export_entry = entry.copy()
            export_entry['issues'] = [
                {
                    'threat_level': issue.threat_level.value,
                    'issue_type': issue.issue_type,
                    'description': issue.description,
                    'file_path': issue.file_path,
                    'line_number': issue.line_number,
                    'recommendation': issue.recommendation,
                    'cve_references': issue.cve_references,
                }
                for issue in entry['issues']
            ]
            exportable_log.append(export_entry)
        
        with open(file_path, 'w') as f:
            json.dump(exportable_log, f, indent=2)