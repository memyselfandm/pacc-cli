"""Plugin-specific security validation and scanning for PACC."""

import re
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from pacc.security.security_measures import (
    SecurityIssue, ThreatLevel, InputSanitizer, PathTraversalProtector,
    FileContentScanner, SecurityPolicy
)
from pacc.errors.exceptions import SecurityError, ValidationError


class PluginSecurityLevel(Enum):
    """Security levels for plugin operations."""
    MINIMAL = "minimal"        # Basic validation only
    STANDARD = "standard"      # Default security level
    STRICT = "strict"          # Enhanced security scanning
    PARANOID = "paranoid"      # Maximum security validation


@dataclass
class PluginManifest:
    """Represents a plugin manifest with security metadata."""
    name: str
    version: str
    description: str
    plugin_type: str
    author: Optional[str] = None
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    file_operations: List[str] = field(default_factory=list)
    network_access: List[str] = field(default_factory=list)
    system_commands: List[str] = field(default_factory=list)
    security_level: PluginSecurityLevel = PluginSecurityLevel.STANDARD


@dataclass
class SecurityAuditEntry:
    """Represents a security audit log entry."""
    timestamp: str
    operation: str
    plugin_name: str
    security_level: PluginSecurityLevel
    issues: List[SecurityIssue]
    risk_score: int
    action_taken: str
    user_confirmed: bool = False


class AdvancedCommandScanner:
    """Advanced security scanner for plugin commands."""
    
    def __init__(self):
        """Initialize the advanced command scanner."""
        self.dangerous_patterns = {
            # Command injection patterns
            'command_injection': [
                r'`[^`]*`',                    # Backtick command substitution
                r'\$\([^)]*\)',                # $(command) substitution
                r';\s*(rm|del|format)\s+',     # Chained dangerous commands
                r'\|\s*(rm|del|format)\s+',    # Piped dangerous commands
                r'&&\s*(rm|del|format)\s+',    # AND chained dangerous commands
                r'\|\|\s*(rm|del|format)\s+',  # OR chained dangerous commands
                r'eval\s*[\(\'"]\s*.*[\)\'"]\s*',  # eval with any brackets/quotes
                r'exec\s*[\(\'"]\s*.*[\)\'"]\s*',  # exec with any brackets/quotes
                r'system\s*\(',                # system() calls
                r'popen\s*\(',                 # popen() calls
                r'subprocess\.',               # subprocess module usage
            ],
            
            # Path traversal and directory manipulation
            'path_traversal': [
                r'\.\.[\\/]',                  # Path traversal attempts
                r'[\\/]\.\.[\\/]',             # Embedded path traversal
                r'%2e%2e',                     # URL encoded path traversal
                r'%252e%252e',                 # Double URL encoded
                r'\.\.%2f',                    # Mixed encoding
                r'\.\.%5c',                    # Mixed encoding (Windows)
            ],
            
            # Privilege escalation
            'privilege_escalation': [
                r'\bsudo\s+',                  # sudo commands
                r'\bsu\s+',                    # switch user
                r'\brunas\s+',                 # Windows runas
                r'\bchmod\s+[4-7][0-7][0-7]', # chmod with setuid/setgid
                r'\bchown\s+root',             # Change ownership to root
                r'\bumask\s+0[0-7][0-7]',      # Unsafe umask settings
                r'/etc/passwd',                # Password file access
                r'/etc/shadow',                # Shadow password file
                r'SUID|SGID',                  # SUID/SGID references
            ],
            
            # Dangerous file operations
            'dangerous_file_ops': [
                r'\brm\s+-[rf]*r[rf]*\s+/',    # rm -rf with root paths
                r'\bdel\s+/[fs]\s+',           # Windows del with force/subdirs
                r'\bformat\s+[cd]:\s*',        # Format drives
                r'\bfdisk\s+',                 # Disk partitioning
                r'\bmkfs[.\w]*\s+',            # Make filesystem (mkfs, mkfs.ext4, etc.)
                r'\bdd\s+if=.*of=',            # Disk duplication
                r'>/dev/null\s*2>&1',          # Silent operation hiding
                r'\bshred\s+',                 # Secure file deletion
                r'\bwipe\s+',                  # Secure wiping
            ],
            
            # Network operations and data exfiltration
            'network_operations': [
                r'\bcurl\s+.*\|\s*sh',         # Download and execute
                r'\bwget\s+.*\|\s*sh',         # Download and execute
                r'\bnc\s+-[le]',               # Netcat listeners
                r'\bnetcat\s+-[le]',           # Netcat listeners
                r'\btelnet\s+\d+\.\d+',        # Telnet connections
                r'\bftp\s+\d+\.\d+',           # FTP connections
                r'\bscp\s+.*@',                # SCP file transfers
                r'\brsync\s+.*@',              # Rsync transfers
                r'https?://[^\s]+\.(sh|py|exe|bat|ps1)', # Suspicious downloads
            ],
            
            # Data access and persistence
            'data_access': [
                r'/home/[^/]+/\.(ssh|gnupg|config)', # User sensitive dirs
                r'~[./](ssh|gnupg|config)',    # User sensitive dirs (tilde)
                r'\.bashrc|\.profile|\.zshrc', # Shell configuration
                r'crontab\s+-[er]',            # Cron job manipulation
                r'/etc/cron',                  # System cron access
                r'\.git/(config|hooks)',       # Git configuration
                r'\.env|\.config',             # Configuration files
                r'HISTFILE|HISTCONTROL',       # History manipulation
            ],
            
            # Encoding and obfuscation
            'obfuscation': [
                r'base64\s+-d',                # Base64 decoding
                r'echo\s+[A-Za-z0-9+/=]{20,}\s*\|\s*base64', # Base64 pipes
                r'python\s+-c\s*["\']',        # Python one-liners
                r'perl\s+-[pe]\s*["\']',       # Perl one-liners
                r'ruby\s+-e\s*["\']',          # Ruby one-liners
                r'node\s+-e\s*["\']',          # Node.js one-liners
                r'\\x[0-9a-fA-F]{2}',          # Hex encoding
                r'%[0-9a-fA-F]{2}',            # URL encoding
            ]
        }
        
        # Suspicious domains and IPs
        self.suspicious_domains = {
            'pastebin.com', 'hastebin.com', 'github.com/raw', 'gist.github.com',
            'bit.ly', 'tinyurl.com', 'short.link', 't.co', 'dropbox.com/s',
            'onedrive.live.com', 'drive.google.com', 'transfer.sh'
        }
        
        # Compile patterns for performance
        self._compiled_patterns = {}
        for category, patterns in self.dangerous_patterns.items():
            self._compiled_patterns[category] = [
                re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                for pattern in patterns
            ]
    
    def scan_command(self, command: str, context: str = "unknown") -> List[SecurityIssue]:
        """Scan a command for security threats.
        
        Args:
            command: Command string to scan
            context: Context where command is used
            
        Returns:
            List of security issues found
        """
        issues = []
        
        # Skip empty commands
        if not command or not command.strip():
            return issues
        
        # Scan against all pattern categories
        for category, compiled_patterns in self._compiled_patterns.items():
            for pattern in compiled_patterns:
                matches = list(pattern.finditer(command))
                for match in matches:
                    threat_level = self._get_threat_level_for_category(category)
                    
                    issues.append(SecurityIssue(
                        threat_level=threat_level,
                        issue_type=f"dangerous_{category}",
                        description=f"Detected {category.replace('_', ' ')}: {match.group().strip()}",
                        recommendation=self._get_recommendation_for_category(category),
                        line_number=None  # Commands are typically single-line
                    ))
        
        # Check for suspicious domains
        domain_issues = self._scan_for_suspicious_domains(command)
        issues.extend(domain_issues)
        
        # Check command length and complexity
        complexity_issues = self._analyze_command_complexity(command)
        issues.extend(complexity_issues)
        
        return issues
    
    def _get_threat_level_for_category(self, category: str) -> ThreatLevel:
        """Get threat level for a pattern category."""
        threat_levels = {
            'command_injection': ThreatLevel.CRITICAL,
            'privilege_escalation': ThreatLevel.CRITICAL,
            'dangerous_file_ops': ThreatLevel.HIGH,
            'path_traversal': ThreatLevel.HIGH,
            'network_operations': ThreatLevel.MEDIUM,
            'data_access': ThreatLevel.MEDIUM,
            'obfuscation': ThreatLevel.HIGH
        }
        return threat_levels.get(category, ThreatLevel.MEDIUM)
    
    def _get_recommendation_for_category(self, category: str) -> str:
        """Get security recommendation for a pattern category."""
        recommendations = {
            'command_injection': "Avoid command injection patterns. Use proper parameter validation and escaping.",
            'privilege_escalation': "Remove privilege escalation attempts. Plugins should not require elevated privileges.",
            'dangerous_file_ops': "Avoid destructive file operations. Use safe, scoped file access patterns.",
            'path_traversal': "Use validated, absolute paths within allowed directories only.",
            'network_operations': "Avoid downloading and executing remote code. Use secure, validated network access.",
            'data_access': "Limit access to user-specific data directories. Avoid system configuration files.",
            'obfuscation': "Remove obfuscated or encoded commands. Use clear, readable command syntax."
        }
        return recommendations.get(category, "Review command for potential security risks.")
    
    def _scan_for_suspicious_domains(self, command: str) -> List[SecurityIssue]:
        """Scan for suspicious domains in commands."""
        issues = []
        
        # Extract URLs and domains
        url_pattern = re.compile(
            r'https?://([a-zA-Z0-9.-]+\.?[a-zA-Z]{2,})', 
            re.IGNORECASE
        )
        
        for match in url_pattern.finditer(command):
            domain = match.group(1).lower()
            
            # Check against suspicious domains
            for suspicious in self.suspicious_domains:
                if suspicious in domain:
                    issues.append(SecurityIssue(
                        threat_level=ThreatLevel.MEDIUM,
                        issue_type="suspicious_domain",
                        description=f"Command accesses potentially suspicious domain: {domain}",
                        recommendation="Verify the legitimacy of external domains and their content."
                    ))
                    break
        
        return issues
    
    def _analyze_command_complexity(self, command: str) -> List[SecurityIssue]:
        """Analyze command complexity for potential security risks."""
        issues = []
        
        # Check command length
        if len(command) > 500:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.LOW,
                issue_type="complex_command",
                description=f"Command is very long ({len(command)} characters)",
                recommendation="Consider breaking complex commands into simpler, more auditable parts."
            ))
        
        # Check for multiple chained operations
        chain_count = command.count(';') + command.count('&&') + command.count('||')
        if chain_count > 3:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.MEDIUM,
                issue_type="complex_command_chain",
                description=f"Command contains many chained operations ({chain_count})",
                recommendation="Simplify command chains for better security auditing."
            ))
        
        # Check for deeply nested structures
        paren_depth = 0
        max_depth = 0
        for char in command:
            if char in '([{':
                paren_depth += 1
                max_depth = max(max_depth, paren_depth)
            elif char in ')]}':
                paren_depth = max(0, paren_depth - 1)
        
        if max_depth > 3:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.LOW,
                issue_type="complex_nesting",
                description=f"Command has deep nesting (depth: {max_depth})",
                recommendation="Reduce command complexity for better readability and security."
            ))
        
        return issues


class PluginManifestValidator:
    """Validates plugin manifests against security schema."""
    
    def __init__(self):
        """Initialize the manifest validator."""
        self.required_fields = {
            'name': str,
            'version': str, 
            'description': str,
            'plugin_type': str
        }
        
        self.optional_fields = {
            'author': str,
            'permissions': list,
            'dependencies': list,
            'file_operations': list,
            'network_access': list,
            'system_commands': list,
            'security_level': str
        }
        
        self.valid_plugin_types = {
            'hooks', 'mcp', 'agents', 'commands', 'themes', 'tools'
        }
        
        self.valid_permissions = {
            'file_read', 'file_write', 'file_execute',
            'network_http', 'network_https', 'network_ftp',
            'system_shell', 'system_env', 'system_process',
            'user_input', 'user_output', 'user_storage'
        }
    
    def validate_manifest(self, manifest_data: Dict[str, Any]) -> Tuple[bool, List[SecurityIssue]]:
        """Validate a plugin manifest.
        
        Args:
            manifest_data: Manifest data dictionary
            
        Returns:
            Tuple of (is_valid, issues_list)
        """
        issues = []
        
        # Validate required fields
        for field, expected_type in self.required_fields.items():
            if field not in manifest_data:
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.HIGH,
                    issue_type="missing_required_field",
                    description=f"Required field '{field}' is missing from manifest",
                    recommendation=f"Add '{field}' field to the plugin manifest."
                ))
            elif not isinstance(manifest_data[field], expected_type):
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="invalid_field_type",
                    description=f"Field '{field}' must be of type {expected_type.__name__}",
                    recommendation=f"Change '{field}' to {expected_type.__name__} type."
                ))
        
        # Validate optional fields
        for field, expected_type in self.optional_fields.items():
            if field in manifest_data:
                if not isinstance(manifest_data[field], expected_type):
                    issues.append(SecurityIssue(
                        threat_level=ThreatLevel.MEDIUM,
                        issue_type="invalid_field_type",
                        description=f"Field '{field}' must be of type {expected_type.__name__}",
                        recommendation=f"Change '{field}' to {expected_type.__name__} type."
                    ))
        
        # Validate specific field content
        if 'plugin_type' in manifest_data:
            plugin_type = manifest_data['plugin_type']
            if plugin_type not in self.valid_plugin_types:
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="invalid_plugin_type",
                    description=f"Unknown plugin type: {plugin_type}",
                    recommendation=f"Use one of: {', '.join(self.valid_plugin_types)}"
                ))
        
        # Validate permissions
        if 'permissions' in manifest_data:
            permission_issues = self._validate_permissions(manifest_data['permissions'])
            issues.extend(permission_issues)
        
        # Validate version format (only if it's a string)
        if 'version' in manifest_data:
            version = manifest_data['version']
            if isinstance(version, str):
                version_issues = self._validate_version(version)
                issues.extend(version_issues)
        
        # Validate name format (only if it's a string)
        if 'name' in manifest_data:
            name = manifest_data['name']
            if isinstance(name, str):
                name_issues = self._validate_name(name)
                issues.extend(name_issues)
        
        # Check for suspicious dependencies
        if 'dependencies' in manifest_data:
            dep_issues = self._validate_dependencies(manifest_data['dependencies'])
            issues.extend(dep_issues)
        
        is_valid = not any(issue.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL] 
                          for issue in issues)
        
        return is_valid, issues
    
    def _validate_permissions(self, permissions: List[str]) -> List[SecurityIssue]:
        """Validate permission declarations."""
        issues = []
        
        if not isinstance(permissions, list):
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.MEDIUM,
                issue_type="invalid_permissions_type",
                description="Permissions must be a list of permission strings",
                recommendation="Change permissions to a list format."
            ))
            return issues
        
        for permission in permissions:
            if not isinstance(permission, str):
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="invalid_permission_type",
                    description=f"Permission must be a string: {permission}",
                    recommendation="Use string values for permissions."
                ))
                continue
            
            if permission not in self.valid_permissions:
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="unknown_permission",
                    description=f"Unknown permission: {permission}",
                    recommendation=f"Use valid permissions: {', '.join(self.valid_permissions)}"
                ))
            
            # Check for dangerous permission combinations
            if permission == 'system_shell' and 'file_write' in permissions:
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.HIGH,
                    issue_type="dangerous_permission_combo",
                    description="Combination of system_shell and file_write permissions is high risk",
                    recommendation="Consider limiting to either shell OR file write access."
                ))
        
        return issues
    
    def _validate_version(self, version: str) -> List[SecurityIssue]:
        """Validate version format."""
        issues = []
        
        # Basic semantic versioning
        semver_pattern = r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?(?:\+[a-zA-Z0-9.-]+)?$'
        if not re.match(semver_pattern, version):
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.LOW,
                issue_type="invalid_version_format",
                description=f"Version '{version}' doesn't follow semantic versioning",
                recommendation="Use semantic versioning format: major.minor.patch"
            ))
        
        return issues
    
    def _validate_name(self, name: str) -> List[SecurityIssue]:
        """Validate plugin name."""
        issues = []
        
        # Check name format
        if not re.match(r'^[a-zA-Z0-9._-]+$', name):
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.MEDIUM,
                issue_type="invalid_name_format",
                description=f"Plugin name contains invalid characters: {name}",
                recommendation="Use only alphanumeric characters, dots, hyphens, and underscores."
            ))
        
        # Check for reserved names
        reserved_names = {
            'system', 'admin', 'root', 'claude', 'anthropic', 'config', 'settings'
        }
        if name.lower() in reserved_names:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.MEDIUM,
                issue_type="reserved_name",
                description=f"Plugin name '{name}' is reserved",
                recommendation="Choose a different, non-reserved name."
            ))
        
        return issues
    
    def _validate_dependencies(self, dependencies: List[str]) -> List[SecurityIssue]:
        """Validate plugin dependencies."""
        issues = []
        
        suspicious_packages = {
            'requests', 'urllib3', 'paramiko', 'fabric', 'ansible',
            'docker', 'kubernetes', 'boto3', 'azure', 'google-cloud'
        }
        
        for dep in dependencies:
            if not isinstance(dep, str):
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="invalid_dependency_type",
                    description=f"Dependency must be a string: {dep}",
                    recommendation="Use string values for dependencies."
                ))
                continue
            
            # Check for suspicious dependencies
            dep_name = dep.split('==')[0].split('>=')[0].split('<=')[0].lower()
            if dep_name in suspicious_packages:
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="suspicious_dependency",
                    description=f"Dependency '{dep_name}' provides network/system access capabilities",
                    recommendation="Verify the necessity of this dependency and its security implications."
                ))
        
        return issues


class PermissionAnalyzer:
    """Analyzes file system permissions and access patterns."""
    
    def __init__(self, allowed_base_paths: Optional[List[Path]] = None):
        """Initialize permission analyzer.
        
        Args:
            allowed_base_paths: Base paths where plugins are allowed to operate
        """
        self.allowed_base_paths = allowed_base_paths or []
        self.restricted_paths = {
            Path('/etc'), Path('/bin'), Path('/sbin'), Path('/usr/bin'),
            Path('/usr/sbin'), Path('/var/log'), Path('/var/run'),
            Path.home() / '.ssh', Path.home() / '.gnupg'
        }
    
    def analyze_file_access(self, file_path: Path, operation: str) -> List[SecurityIssue]:
        """Analyze file access for security implications.
        
        Args:
            file_path: Path to file being accessed
            operation: Type of operation (read, write, execute, delete)
            
        Returns:
            List of security issues
        """
        issues = []
        
        try:
            resolved_path = file_path.resolve()
            
            # Check against restricted paths
            for restricted in self.restricted_paths:
                try:
                    resolved_path.relative_to(restricted)
                    issues.append(SecurityIssue(
                        threat_level=ThreatLevel.HIGH,
                        issue_type="restricted_path_access",
                        description=f"Attempted {operation} access to restricted path: {resolved_path}",
                        recommendation="Limit file operations to allowed plugin directories."
                    ))
                    break
                except ValueError:
                    continue
            
            # Check if path is within allowed base paths
            if self.allowed_base_paths:
                is_allowed = False
                for base_path in self.allowed_base_paths:
                    try:
                        resolved_path.relative_to(base_path.resolve())
                        is_allowed = True
                        break
                    except ValueError:
                        continue
                
                if not is_allowed:
                    issues.append(SecurityIssue(
                        threat_level=ThreatLevel.MEDIUM,
                        issue_type="unauthorized_path_access",
                        description=f"File access outside allowed directories: {resolved_path}",
                        recommendation="Restrict file operations to authorized plugin directories."
                    ))
            
            # Analyze operation type
            if operation == 'execute':
                issues.extend(self._analyze_execution_risk(resolved_path))
            elif operation in ['write', 'delete']:
                issues.extend(self._analyze_modification_risk(resolved_path))
        
        except Exception as e:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.LOW,
                issue_type="permission_analysis_error",
                description=f"Error analyzing file permissions: {e}",
                recommendation="Manual review of file access patterns recommended."
            ))
        
        return issues
    
    def _analyze_execution_risk(self, file_path: Path) -> List[SecurityIssue]:
        """Analyze execution risk for a file."""
        issues = []
        
        # Check file extension
        risky_extensions = {'.exe', '.bat', '.cmd', '.ps1', '.sh', '.com', '.scr'}
        if file_path.suffix.lower() in risky_extensions:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.HIGH,
                issue_type="risky_executable",
                description=f"Execution of potentially dangerous file type: {file_path.suffix}",
                recommendation="Avoid executing binary files or scripts from plugin packages."
            ))
        
        return issues
    
    def _analyze_modification_risk(self, file_path: Path) -> List[SecurityIssue]:
        """Analyze modification risk for a file."""
        issues = []
        
        # Check for system configuration files
        config_patterns = [
            r'\.config$', r'\.conf$', r'\.ini$', r'\.cfg$',
            r'config\.', r'settings\.', r'\.env$'
        ]
        
        for pattern in config_patterns:
            if re.search(pattern, file_path.name, re.IGNORECASE):
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="config_file_modification",
                    description=f"Modification of configuration file: {file_path.name}",
                    recommendation="Verify that configuration changes are safe and necessary."
                ))
                break
        
        return issues


class SecurityAuditLogger:
    """Logs security audit events and maintains audit trails."""
    
    def __init__(self, log_file: Optional[Path] = None):
        """Initialize security audit logger.
        
        Args:
            log_file: Path to audit log file
        """
        self.log_file = log_file
        self.audit_entries: List[SecurityAuditEntry] = []
        
        # Set up logging
        self.logger = logging.getLogger('pacc.security')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_security_event(self, 
                          operation: str,
                          plugin_name: str,
                          issues: List[SecurityIssue],
                          action_taken: str,
                          security_level: PluginSecurityLevel = PluginSecurityLevel.STANDARD,
                          user_confirmed: bool = False) -> None:
        """Log a security audit event.
        
        Args:
            operation: Operation being performed
            plugin_name: Name of plugin being processed
            issues: Security issues found
            action_taken: Action taken based on security findings
            security_level: Security level used for validation
            user_confirmed: Whether user confirmed risky operations
        """
        # Calculate risk score
        risk_score = sum(self._get_risk_value(issue.threat_level) for issue in issues)
        
        # Create audit entry
        entry = SecurityAuditEntry(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            plugin_name=plugin_name,
            security_level=security_level,
            issues=issues,
            risk_score=risk_score,
            action_taken=action_taken,
            user_confirmed=user_confirmed
        )
        
        self.audit_entries.append(entry)
        
        # Log to standard logger
        if issues:
            level = logging.WARNING if risk_score > 50 else logging.INFO
            self.logger.log(level, 
                f"Security audit for {plugin_name}: {len(issues)} issues found, "
                f"risk score: {risk_score}, action: {action_taken}")
        
        # Write to audit file if configured
        if self.log_file:
            self._write_audit_entry(entry)
    
    def _get_risk_value(self, threat_level: ThreatLevel) -> int:
        """Get numeric risk value for threat level."""
        values = {
            ThreatLevel.LOW: 10,
            ThreatLevel.MEDIUM: 25,
            ThreatLevel.HIGH: 50,
            ThreatLevel.CRITICAL: 100
        }
        return values.get(threat_level, 25)
    
    def _write_audit_entry(self, entry: SecurityAuditEntry) -> None:
        """Write audit entry to log file."""
        try:
            if not self.log_file.parent.exists():
                self.log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to JSON-serializable format
            entry_dict = {
                'timestamp': entry.timestamp,
                'operation': entry.operation,
                'plugin_name': entry.plugin_name,
                'security_level': entry.security_level.value,
                'risk_score': entry.risk_score,
                'action_taken': entry.action_taken,
                'user_confirmed': entry.user_confirmed,
                'issues': [
                    {
                        'threat_level': issue.threat_level.value,
                        'issue_type': issue.issue_type,
                        'description': issue.description,
                        'recommendation': issue.recommendation,
                        'file_path': issue.file_path,
                        'line_number': issue.line_number
                    }
                    for issue in entry.issues
                ]
            }
            
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry_dict) + '\n')
        
        except Exception as e:
            self.logger.error(f"Failed to write audit entry: {e}")
    
    def get_audit_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get audit summary for the last N days.
        
        Args:
            days: Number of days to include in summary
            
        Returns:
            Audit summary dictionary
        """
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        recent_entries = [
            entry for entry in self.audit_entries
            if datetime.fromisoformat(entry.timestamp).timestamp() > cutoff
        ]
        
        return {
            'total_audits': len(recent_entries),
            'high_risk_audits': len([e for e in recent_entries if e.risk_score > 75]),
            'blocked_operations': len([e for e in recent_entries if 'blocked' in e.action_taken]),
            'user_confirmations': len([e for e in recent_entries if e.user_confirmed]),
            'average_risk_score': sum(e.risk_score for e in recent_entries) / len(recent_entries) if recent_entries else 0,
            'most_common_issues': self._get_most_common_issues(recent_entries)
        }
    
    def _get_most_common_issues(self, entries: List[SecurityAuditEntry]) -> Dict[str, int]:
        """Get most common security issues from audit entries."""
        issue_counts = {}
        
        for entry in entries:
            for issue in entry.issues:
                issue_type = issue.issue_type
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        # Sort by frequency and return top 10
        sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_issues[:10])


class PluginSecurityManager:
    """Main security manager for plugin operations."""
    
    def __init__(self, 
                 security_level: PluginSecurityLevel = PluginSecurityLevel.STANDARD,
                 audit_log_path: Optional[Path] = None):
        """Initialize plugin security manager.
        
        Args:
            security_level: Default security level for operations
            audit_log_path: Path to security audit log file
        """
        self.security_level = security_level
        
        # Initialize components
        self.command_scanner = AdvancedCommandScanner()
        self.manifest_validator = PluginManifestValidator()
        self.permission_analyzer = PermissionAnalyzer()
        self.audit_logger = SecurityAuditLogger(audit_log_path)
        
        # Legacy security components
        self.input_sanitizer = InputSanitizer()
        self.path_protector = PathTraversalProtector()
        self.content_scanner = FileContentScanner()
    
    def validate_plugin_security(self, 
                                plugin_path: Path,
                                plugin_type: str,
                                security_level: Optional[PluginSecurityLevel] = None) -> Tuple[bool, List[SecurityIssue]]:
        """Comprehensive security validation of a plugin.
        
        Args:
            plugin_path: Path to plugin files
            plugin_type: Type of plugin (hooks, mcp, agents, commands)
            security_level: Security level to use for validation
            
        Returns:
            Tuple of (is_safe, issues_list)
        """
        level = security_level or self.security_level
        all_issues = []
        
        try:
            # 1. Path safety validation
            if not self.path_protector.is_safe_path(plugin_path):
                all_issues.append(SecurityIssue(
                    threat_level=ThreatLevel.HIGH,
                    issue_type="unsafe_plugin_path",
                    description=f"Plugin path is unsafe: {plugin_path}",
                    recommendation="Use safe, validated plugin paths."
                ))
            
            # 2. Manifest validation (if present)
            manifest_path = plugin_path / 'manifest.json'
            if manifest_path.exists():
                manifest_issues = self._validate_plugin_manifest(manifest_path)
                all_issues.extend(manifest_issues)
            
            # 3. Content security scanning
            if plugin_path.is_file():
                content_issues = self.content_scanner.scan_file(plugin_path)
                all_issues.extend(content_issues)
            elif plugin_path.is_dir():
                for file_path in plugin_path.rglob('*'):
                    if file_path.is_file():
                        content_issues = self.content_scanner.scan_file(file_path)
                        all_issues.extend(content_issues)
            
            # 4. Plugin-type specific validation
            type_specific_issues = self._validate_by_plugin_type(plugin_path, plugin_type)
            all_issues.extend(type_specific_issues)
            
            # 5. Permission analysis
            permission_issues = self._analyze_plugin_permissions(plugin_path)
            all_issues.extend(permission_issues)
            
            # Determine if plugin is safe based on security level
            is_safe = self._evaluate_safety(all_issues, level)
            
            # Log security audit
            action = "approved" if is_safe else "blocked"
            self.audit_logger.log_security_event(
                operation="plugin_validation",
                plugin_name=plugin_path.name,
                issues=all_issues,
                action_taken=action,
                security_level=level
            )
            
            return is_safe, all_issues
        
        except Exception as e:
            error_issue = SecurityIssue(
                threat_level=ThreatLevel.MEDIUM,
                issue_type="validation_error",
                description=f"Error during security validation: {e}",
                recommendation="Manual security review recommended."
            )
            all_issues.append(error_issue)
            
            self.audit_logger.log_security_event(
                operation="plugin_validation",
                plugin_name=plugin_path.name,
                issues=all_issues,
                action_taken="error",
                security_level=level
            )
            
            return False, all_issues
    
    def _validate_plugin_manifest(self, manifest_path: Path) -> List[SecurityIssue]:
        """Validate plugin manifest file."""
        issues = []
        
        try:
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)
            
            is_valid, manifest_issues = self.manifest_validator.validate_manifest(manifest_data)
            issues.extend(manifest_issues)
        
        except json.JSONDecodeError as e:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.MEDIUM,
                issue_type="invalid_manifest_json",
                description=f"Manifest JSON is invalid: {e}",
                recommendation="Fix JSON syntax errors in manifest file."
            ))
        except Exception as e:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.LOW,
                issue_type="manifest_read_error",
                description=f"Error reading manifest: {e}",
                recommendation="Ensure manifest file is readable."
            ))
        
        return issues
    
    def _validate_by_plugin_type(self, plugin_path: Path, plugin_type: str) -> List[SecurityIssue]:
        """Perform plugin-type specific security validation."""
        issues = []
        
        if plugin_type == 'hooks':
            issues.extend(self._validate_hooks_security(plugin_path))
        elif plugin_type == 'mcp':
            issues.extend(self._validate_mcp_security(plugin_path))
        elif plugin_type == 'agents':
            issues.extend(self._validate_agents_security(plugin_path))
        elif plugin_type == 'commands':
            issues.extend(self._validate_commands_security(plugin_path))
        
        return issues
    
    def _validate_hooks_security(self, plugin_path: Path) -> List[SecurityIssue]:
        """Validate hooks-specific security concerns."""
        issues = []
        
        # Find and scan hook JSON files
        if plugin_path.is_file() and plugin_path.suffix == '.json':
            hook_files = [plugin_path]
        else:
            hook_files = list(plugin_path.rglob('*.json'))
        
        for hook_file in hook_files:
            try:
                with open(hook_file, 'r') as f:
                    hook_data = json.load(f)
                
                # Scan commands for security issues
                commands = hook_data.get('commands', [])
                for i, command in enumerate(commands):
                    command_str = command if isinstance(command, str) else command.get('command', '')
                    if command_str:
                        command_issues = self.command_scanner.scan_command(
                            command_str, f"hook command {i+1}"
                        )
                        issues.extend(command_issues)
            
            except Exception as e:
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.LOW,
                    issue_type="hook_scan_error",
                    description=f"Error scanning hook file {hook_file}: {e}",
                    recommendation="Manual review of hook file recommended."
                ))
        
        return issues
    
    def _validate_mcp_security(self, plugin_path: Path) -> List[SecurityIssue]:
        """Validate MCP-specific security concerns."""
        issues = []
        
        # Check for executable files
        if plugin_path.is_dir():
            for file_path in plugin_path.rglob('*'):
                if file_path.is_file() and file_path.stat().st_mode & 0o111:
                    issues.append(SecurityIssue(
                        threat_level=ThreatLevel.MEDIUM,
                        issue_type="mcp_executable_file",
                        description=f"MCP plugin contains executable file: {file_path.name}",
                        recommendation="Review executable files for security implications."
                    ))
        
        return issues
    
    def _validate_agents_security(self, plugin_path: Path) -> List[SecurityIssue]:
        """Validate agents-specific security concerns."""
        issues = []
        
        # Scan markdown files for embedded scripts
        if plugin_path.is_file() and plugin_path.suffix == '.md':
            md_files = [plugin_path]
        else:
            md_files = list(plugin_path.rglob('*.md'))
        
        for md_file in md_files:
            try:
                content = md_file.read_text()
                
                # Look for code blocks that might contain dangerous commands
                code_block_pattern = r'```(?:bash|sh|shell|python|js|javascript)\n(.*?)\n```'
                for match in re.finditer(code_block_pattern, content, re.DOTALL | re.IGNORECASE):
                    code_content = match.group(1)
                    code_issues = self.command_scanner.scan_command(
                        code_content, "agent code block"
                    )
                    issues.extend(code_issues)
            
            except Exception as e:
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.LOW,
                    issue_type="agent_scan_error",
                    description=f"Error scanning agent file {md_file}: {e}",
                    recommendation="Manual review of agent file recommended."
                ))
        
        return issues
    
    def _validate_commands_security(self, plugin_path: Path) -> List[SecurityIssue]:
        """Validate commands-specific security concerns."""
        issues = []
        
        # Similar to agents, scan markdown files for command definitions
        if plugin_path.is_file() and plugin_path.suffix == '.md':
            cmd_files = [plugin_path]
        else:
            cmd_files = list(plugin_path.rglob('*.md'))
        
        for cmd_file in cmd_files:
            try:
                content = cmd_file.read_text()
                
                # Look for command definitions or examples
                content_issues = self.input_sanitizer.scan_for_threats(content, "command_file")
                issues.extend(content_issues)
            
            except Exception as e:
                issues.append(SecurityIssue(
                    threat_level=ThreatLevel.LOW,
                    issue_type="command_scan_error", 
                    description=f"Error scanning command file {cmd_file}: {e}",
                    recommendation="Manual review of command file recommended."
                ))
        
        return issues
    
    def _analyze_plugin_permissions(self, plugin_path: Path) -> List[SecurityIssue]:
        """Analyze plugin file system permissions."""
        issues = []
        
        # Analyze plugin directory structure
        if plugin_path.is_dir():
            for file_path in plugin_path.rglob('*'):
                if file_path.is_file():
                    perm_issues = self.permission_analyzer.analyze_file_access(
                        file_path, "read"
                    )
                    issues.extend(perm_issues)
        else:
            perm_issues = self.permission_analyzer.analyze_file_access(
                plugin_path, "read"
            )
            issues.extend(perm_issues)
        
        return issues
    
    def _evaluate_safety(self, issues: List[SecurityIssue], security_level: PluginSecurityLevel) -> bool:
        """Evaluate if plugin is safe based on security level and issues found."""
        # Count issues by threat level
        critical_count = sum(1 for issue in issues if issue.threat_level == ThreatLevel.CRITICAL)
        high_count = sum(1 for issue in issues if issue.threat_level == ThreatLevel.HIGH)
        medium_count = sum(1 for issue in issues if issue.threat_level == ThreatLevel.MEDIUM)
        
        # Security level determines tolerance
        if security_level == PluginSecurityLevel.MINIMAL:
            return critical_count == 0
        elif security_level == PluginSecurityLevel.STANDARD:
            return critical_count == 0 and high_count <= 1
        elif security_level == PluginSecurityLevel.STRICT:
            return critical_count == 0 and high_count == 0 and medium_count <= 2
        elif security_level == PluginSecurityLevel.PARANOID:
            return critical_count == 0 and high_count == 0 and medium_count == 0
        
        return False