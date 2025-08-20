"""Basic sandboxing concepts for plugin validation and execution."""

import os
import tempfile
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from pacc.security.security_measures import SecurityIssue, ThreatLevel
from pacc.errors.exceptions import SecurityError


class SandboxLevel(Enum):
    """Sandbox isolation levels."""
    NONE = "none"              # No sandboxing
    BASIC = "basic"            # Basic file system isolation
    RESTRICTED = "restricted"  # File system + network restrictions
    STRICT = "strict"          # Maximum isolation


@dataclass
class SandboxConfig:
    """Configuration for sandbox environment."""
    level: SandboxLevel = SandboxLevel.BASIC
    allowed_paths: List[Path] = None
    blocked_paths: List[Path] = None
    max_execution_time: int = 30  # seconds
    max_memory_mb: int = 512
    allow_network: bool = False
    allow_subprocess: bool = False
    environment_vars: Dict[str, str] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.allowed_paths is None:
            self.allowed_paths = []
        if self.blocked_paths is None:
            self.blocked_paths = []
        if self.environment_vars is None:
            self.environment_vars = {}


@dataclass
class SandboxResult:
    """Result of sandbox execution."""
    success: bool
    return_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0
    memory_used_mb: float = 0.0
    security_violations: List[SecurityIssue] = None
    
    def __post_init__(self):
        """Initialize default values."""
        if self.security_violations is None:
            self.security_violations = []


class PluginSandbox:
    """Basic sandbox for plugin validation and limited execution."""
    
    def __init__(self, config: SandboxConfig):
        """Initialize plugin sandbox.
        
        Args:
            config: Sandbox configuration
        """
        self.config = config
        self.temp_dir = None
        self.restricted_paths = self._get_restricted_paths()
    
    def _get_restricted_paths(self) -> List[Path]:
        """Get list of system paths that should be restricted."""
        system_paths = [
            Path('/etc'),
            Path('/bin'),
            Path('/sbin'),
            Path('/usr/bin'),
            Path('/usr/sbin'),
            Path('/var'),
            Path('/sys'),
            Path('/proc'),
            Path('/dev'),
            Path('/root'),
        ]
        
        # Add Windows system paths
        if os.name == 'nt':
            system_paths.extend([
                Path('C:/Windows'),
                Path('C:/Program Files'),
                Path('C:/Program Files (x86)'),
                Path('C:/Users/All Users'),
            ])
        
        return system_paths + (self.config.blocked_paths or [])
    
    def create_sandbox_environment(self, plugin_path: Path) -> Path:
        """Create isolated sandbox environment.
        
        Args:
            plugin_path: Path to plugin to sandbox
            
        Returns:
            Path to sandbox directory
            
        Raises:
            SecurityError: If sandbox creation fails
        """
        try:
            # Create temporary sandbox directory
            self.temp_dir = Path(tempfile.mkdtemp(prefix='pacc_sandbox_'))
            
            # Copy plugin files to sandbox
            sandbox_plugin_path = self.temp_dir / 'plugin'
            if plugin_path.is_file():
                sandbox_plugin_path.mkdir(parents=True)
                shutil.copy2(plugin_path, sandbox_plugin_path / plugin_path.name)
            else:
                shutil.copytree(plugin_path, sandbox_plugin_path)
            
            # Set restrictive permissions
            self._set_sandbox_permissions(self.temp_dir)
            
            return sandbox_plugin_path
            
        except Exception as e:
            self._cleanup()
            raise SecurityError(
                f"Failed to create sandbox environment: {e}",
                security_check="sandbox_creation"
            )
    
    def _set_sandbox_permissions(self, sandbox_dir: Path) -> None:
        """Set restrictive permissions on sandbox directory."""
        try:
            if os.name != 'nt':  # Unix-like systems
                # Make directory readable/writable only by owner
                os.chmod(sandbox_dir, 0o700)
                
                # Set permissions on all files in sandbox
                for root, dirs, files in os.walk(sandbox_dir):
                    for d in dirs:
                        os.chmod(Path(root) / d, 0o700)
                    for f in files:
                        os.chmod(Path(root) / f, 0o600)
        except Exception as e:
            # Non-critical error, continue with warnings
            pass
    
    def validate_file_access(self, file_path: Path) -> List[SecurityIssue]:
        """Validate if file access is allowed in sandbox.
        
        Args:
            file_path: Path to file being accessed
            
        Returns:
            List of security issues
        """
        issues = []
        
        try:
            resolved_path = file_path.resolve()
            
            # Check against restricted system paths
            for restricted in self.restricted_paths:
                try:
                    resolved_path.relative_to(restricted)
                    issues.append(SecurityIssue(
                        threat_level=ThreatLevel.HIGH,
                        issue_type="sandbox_violation_system_path",
                        description=f"Attempted access to restricted system path: {resolved_path}",
                        recommendation="Limit file access to plugin directory and allowed paths only."
                    ))
                    return issues
                except ValueError:
                    continue
            
            # Check against explicitly allowed paths
            if self.config.allowed_paths:
                is_allowed = False
                for allowed in self.config.allowed_paths:
                    try:
                        resolved_path.relative_to(allowed.resolve())
                        is_allowed = True
                        break
                    except ValueError:
                        continue
                
                if not is_allowed:
                    # If we have a sandbox temp dir, allow access within it
                    if self.temp_dir:
                        try:
                            resolved_path.relative_to(self.temp_dir)
                            is_allowed = True
                        except ValueError:
                            pass
                    
                    if not is_allowed:
                        issues.append(SecurityIssue(
                            threat_level=ThreatLevel.MEDIUM,
                            issue_type="sandbox_violation_unauthorized_path",
                            description=f"File access outside allowed paths: {resolved_path}",
                            recommendation="Restrict file operations to authorized directories."
                        ))
        
        except Exception as e:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.LOW,
                issue_type="sandbox_validation_error",
                description=f"Error validating file access: {e}",
                recommendation="Manual review of file access patterns recommended."
            ))
        
        return issues
    
    def execute_command_safely(self, command: str, working_dir: Optional[Path] = None) -> SandboxResult:
        """Execute command in sandbox with restrictions.
        
        Args:
            command: Command to execute
            working_dir: Working directory for command
            
        Returns:
            Sandbox execution result
        """
        result = SandboxResult(success=False)
        
        # Basic security validation
        if self._is_command_dangerous(command):
            result.security_violations.append(SecurityIssue(
                threat_level=ThreatLevel.CRITICAL,
                issue_type="dangerous_command_execution",
                description=f"Attempted execution of dangerous command: {command}",
                recommendation="Remove dangerous command patterns from plugin."
            ))
            return result
        
        try:
            # Set up environment
            env = self._create_restricted_environment()
            
            # Set working directory
            if working_dir is None and self.temp_dir:
                working_dir = self.temp_dir
            
            # Execute with restrictions
            import time
            start_time = time.time()
            
            # Note: This is a basic implementation
            # In production, you'd want more sophisticated sandboxing
            # using containers, chroot, or system-specific mechanisms
            
            if self.config.level == SandboxLevel.NONE:
                # No sandboxing - just execute
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=working_dir,
                    env=env,
                    text=True
                )
            else:
                # Basic sandboxing - limited environment
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=working_dir,
                    env=env,
                    text=True
                )
            
            # Wait with timeout
            try:
                stdout, stderr = process.communicate(timeout=self.config.max_execution_time)
                result.return_code = process.returncode
                result.stdout = stdout
                result.stderr = stderr
                result.success = process.returncode == 0
            except subprocess.TimeoutExpired:
                process.kill()
                result.stderr = f"Command timed out after {self.config.max_execution_time} seconds"
                result.security_violations.append(SecurityIssue(
                    threat_level=ThreatLevel.MEDIUM,
                    issue_type="execution_timeout",
                    description="Command execution exceeded time limit",
                    recommendation="Reduce command complexity or increase timeout limit."
                ))
            
            result.execution_time = time.time() - start_time
            
        except Exception as e:
            result.stderr = str(e)
            result.security_violations.append(SecurityIssue(
                threat_level=ThreatLevel.MEDIUM,
                issue_type="execution_error",
                description=f"Error executing command: {e}",
                recommendation="Review command syntax and permissions."
            ))
        
        return result
    
    def _is_command_dangerous(self, command: str) -> bool:
        """Check if command contains dangerous patterns."""
        dangerous_patterns = [
            'rm -rf /',
            'del /f /s /q',
            'format ',
            'fdisk',
            'mkfs',
            'dd if=',
            'sudo ',
            'su ',
            '> /dev/',
            'chmod 777',
            'chown root',
        ]
        
        command_lower = command.lower()
        return any(pattern in command_lower for pattern in dangerous_patterns)
    
    def _create_restricted_environment(self) -> Dict[str, str]:
        """Create restricted environment variables."""
        # Start with minimal environment
        restricted_env = {
            'PATH': '/usr/bin:/bin',  # Limited PATH
            'HOME': str(self.temp_dir) if self.temp_dir else '/tmp',
            'TMPDIR': str(self.temp_dir) if self.temp_dir else '/tmp',
            'USER': 'sandbox',
            'SHELL': '/bin/sh'
        }
        
        # Add user-specified environment variables
        restricted_env.update(self.config.environment_vars)
        
        # Remove potentially dangerous variables
        dangerous_vars = [
            'LD_PRELOAD', 'LD_LIBRARY_PATH', 'PYTHONPATH',
            'PERL5LIB', 'RUBYLIB', 'NODE_PATH'
        ]
        
        for var in dangerous_vars:
            restricted_env.pop(var, None)
        
        return restricted_env
    
    def analyze_sandbox_violations(self, plugin_path: Path) -> List[SecurityIssue]:
        """Analyze plugin for potential sandbox violations.
        
        Args:
            plugin_path: Path to plugin to analyze
            
        Returns:
            List of potential security issues
        """
        issues = []
        
        try:
            # Analyze file access patterns
            if plugin_path.is_file():
                files_to_check = [plugin_path]
            else:
                files_to_check = list(plugin_path.rglob('*'))
                files_to_check = [f for f in files_to_check if f.is_file()]
            
            for file_path in files_to_check:
                # Check file access
                access_issues = self.validate_file_access(file_path)
                issues.extend(access_issues)
                
                # Analyze file content for sandbox-breaking patterns
                try:
                    if file_path.suffix in ['.py', '.js', '.sh', '.bat', '.ps1']:
                        content_issues = self._analyze_file_content(file_path)
                        issues.extend(content_issues)
                except Exception:
                    # Skip files that can't be read
                    pass
        
        except Exception as e:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.LOW,
                issue_type="sandbox_analysis_error",
                description=f"Error analyzing sandbox violations: {e}",
                recommendation="Manual review of plugin recommended."
            ))
        
        return issues
    
    def _analyze_file_content(self, file_path: Path) -> List[SecurityIssue]:
        """Analyze file content for sandbox-breaking patterns."""
        issues = []
        
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            # Look for sandbox escape patterns
            escape_patterns = [
                (r'os\.system\s*\(', "Direct system command execution"),
                (r'subprocess\.(call|run|Popen)', "Subprocess execution"),
                (r'exec\s*\(', "Dynamic code execution"),
                (r'eval\s*\(', "Dynamic code evaluation"),
                (r'import\s+ctypes', "Native code access"),
                (r'__import__\s*\(', "Dynamic imports"),
                (r'open\s*\([^)]*["\'][/\\]', "Absolute path file access"),
                (r'chroot|chdir', "Directory manipulation"),
                (r'setuid|setgid', "Privilege manipulation"),
                (r'socket\.|urllib\.|requests\.', "Network access"),
            ]
            
            for pattern, description in escape_patterns:
                import re
                if re.search(pattern, content, re.IGNORECASE):
                    issues.append(SecurityIssue(
                        threat_level=ThreatLevel.MEDIUM,
                        issue_type="potential_sandbox_escape",
                        description=f"Potential sandbox escape: {description}",
                        file_path=str(file_path),
                        recommendation="Review code for sandbox compliance."
                    ))
        
        except Exception:
            # Skip files that can't be analyzed
            pass
        
        return issues
    
    def cleanup(self) -> None:
        """Clean up sandbox environment."""
        self._cleanup()
    
    def _cleanup(self) -> None:
        """Internal cleanup method."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
            except Exception:
                # Best effort cleanup
                pass
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()


class SandboxManager:
    """Manages sandbox environments for different plugin types."""
    
    def __init__(self):
        """Initialize sandbox manager."""
        self.default_configs = {
            'hooks': SandboxConfig(
                level=SandboxLevel.RESTRICTED,
                allow_network=False,
                allow_subprocess=True,  # Hooks often need subprocess
                max_execution_time=10
            ),
            'mcp': SandboxConfig(
                level=SandboxLevel.BASIC,
                allow_network=True,   # MCP servers often need network
                allow_subprocess=True,
                max_execution_time=30
            ),
            'agents': SandboxConfig(
                level=SandboxLevel.BASIC,
                allow_network=False,
                allow_subprocess=False,
                max_execution_time=5
            ),
            'commands': SandboxConfig(
                level=SandboxLevel.BASIC,
                allow_network=False,
                allow_subprocess=False,
                max_execution_time=5
            )
        }
    
    def create_sandbox(self, 
                      plugin_type: str, 
                      config: Optional[SandboxConfig] = None) -> PluginSandbox:
        """Create sandbox for specific plugin type.
        
        Args:
            plugin_type: Type of plugin (hooks, mcp, agents, commands)
            config: Optional custom configuration
            
        Returns:
            Configured plugin sandbox
        """
        if config is None:
            config = self.default_configs.get(plugin_type, SandboxConfig())
        
        return PluginSandbox(config)
    
    def validate_plugin_in_sandbox(self, 
                                  plugin_path: Path, 
                                  plugin_type: str) -> Tuple[bool, List[SecurityIssue]]:
        """Validate plugin in appropriate sandbox.
        
        Args:
            plugin_path: Path to plugin
            plugin_type: Type of plugin
            
        Returns:
            Tuple of (is_safe, issues_list)
        """
        issues = []
        
        try:
            with self.create_sandbox(plugin_type) as sandbox:
                # Analyze for sandbox violations
                sandbox_issues = sandbox.analyze_sandbox_violations(plugin_path)
                issues.extend(sandbox_issues)
                
                # Create sandbox environment for testing
                sandbox_plugin_path = sandbox.create_sandbox_environment(plugin_path)
                
                # Validate file access patterns
                for file_path in sandbox_plugin_path.rglob('*'):
                    if file_path.is_file():
                        access_issues = sandbox.validate_file_access(file_path)
                        issues.extend(access_issues)
                
                # Determine safety based on issue severity
                critical_issues = [i for i in issues if i.threat_level == ThreatLevel.CRITICAL]
                high_issues = [i for i in issues if i.threat_level == ThreatLevel.HIGH]
                
                is_safe = len(critical_issues) == 0 and len(high_issues) <= 1
                
                return is_safe, issues
        
        except Exception as e:
            issues.append(SecurityIssue(
                threat_level=ThreatLevel.MEDIUM,
                issue_type="sandbox_validation_error",
                description=f"Error during sandbox validation: {e}",
                recommendation="Manual security review recommended."
            ))
            return False, issues