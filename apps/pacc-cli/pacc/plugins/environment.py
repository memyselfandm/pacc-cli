"""Environment management for Claude Code plugin configuration.

This module handles automatic ENABLE_PLUGINS configuration across platforms,
ensuring Claude Code can load plugins without manual environment setup.
"""

import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum


class Platform(Enum):
    """Supported platforms."""
    WINDOWS = "windows"
    MACOS = "macos" 
    LINUX = "linux"
    UNKNOWN = "unknown"


class Shell(Enum):
    """Supported shells."""
    BASH = "bash"
    ZSH = "zsh"
    FISH = "fish"
    POWERSHELL = "powershell"
    CMD = "cmd"
    UNKNOWN = "unknown"


@dataclass
class EnvironmentStatus:
    """Current environment configuration status."""
    platform: Platform
    shell: Shell
    enable_plugins_set: bool
    enable_plugins_value: Optional[str]
    config_file: Optional[Path]
    backup_exists: bool
    containerized: bool
    writable: bool
    conflicts: List[str]


@dataclass
class ProfileUpdate:
    """Represents a shell profile update operation."""
    file_path: Path
    backup_path: Path
    content_to_add: str
    exists_before: bool
    needs_creation: bool


class EnvironmentManager:
    """Manages environment configuration for Claude Code plugins."""
    
    ENABLE_PLUGINS_VAR = "ENABLE_PLUGINS"
    ENABLE_PLUGINS_VALUE = "true"
    PACC_COMMENT = "# Added by PACC - Claude Code plugin enablement"
    BACKUP_SUFFIX = ".pacc.backup"
    
    def __init__(self):
        self.platform = self.detect_platform()
        self.shell = self.detect_shell()
        self._home_dir = Path.home()
        
    def detect_platform(self) -> Platform:
        """Detect the current operating system platform."""
        system = platform.system().lower()
        
        if system == "windows":
            return Platform.WINDOWS
        elif system == "darwin":
            return Platform.MACOS
        elif system == "linux":
            return Platform.LINUX
        else:
            return Platform.UNKNOWN
    
    def detect_shell(self) -> Shell:
        """Detect the current shell environment."""
        # Check for containerized environments first
        if self._is_containerized():
            # In containers, often bash is default
            if shutil.which("bash"):
                return Shell.BASH
        
        # Check SHELL environment variable (Unix/Linux/macOS)
        if self.platform != Platform.WINDOWS:
            shell_path = os.environ.get("SHELL", "")
            if shell_path:
                shell_name = Path(shell_path).name.lower()
                if "zsh" in shell_name:
                    return Shell.ZSH
                elif "bash" in shell_name:
                    return Shell.BASH
                elif "fish" in shell_name:
                    return Shell.FISH
        
        # Windows detection
        if self.platform == Platform.WINDOWS:
            # Check if PowerShell is available and preferred
            if shutil.which("pwsh") or shutil.which("powershell"):
                return Shell.POWERSHELL
            else:
                return Shell.CMD
        
        # Fallback detection by checking available shells
        for shell in [Shell.ZSH, Shell.BASH, Shell.FISH]:
            if shutil.which(shell.value):
                return shell
        
        return Shell.UNKNOWN
    
    def _is_containerized(self) -> bool:
        """Check if running in a containerized environment."""
        # Check for Docker
        if Path("/.dockerenv").exists():
            return True
        
        # Check for other container indicators
        try:
            with open("/proc/1/cgroup", "r") as f:
                cgroup_content = f.read()
                if "docker" in cgroup_content or "containerd" in cgroup_content:
                    return True
        except (FileNotFoundError, PermissionError):
            pass
        
        # WSL detection
        if Path("/proc/version").exists():
            try:
                with open("/proc/version", "r") as f:
                    if "microsoft" in f.read().lower():
                        return True
            except (FileNotFoundError, PermissionError):
                pass
        
        return False
    
    def get_shell_profile_paths(self) -> List[Path]:
        """Get potential shell profile file paths for the current shell."""
        if self.platform == Platform.WINDOWS:
            return self._get_windows_profile_paths()
        else:
            return self._get_unix_profile_paths()
    
    def _get_unix_profile_paths(self) -> List[Path]:
        """Get Unix/Linux/macOS shell profile paths."""
        paths = []
        
        if self.shell == Shell.BASH:
            # Bash profiles in order of preference
            candidates = [
                self._home_dir / ".bashrc",
                self._home_dir / ".bash_profile", 
                self._home_dir / ".profile"
            ]
        elif self.shell == Shell.ZSH:
            # Zsh profiles
            candidates = [
                self._home_dir / ".zshrc",
                self._home_dir / ".zprofile",
                self._home_dir / ".profile"
            ]
        elif self.shell == Shell.FISH:
            # Fish config
            candidates = [
                self._home_dir / ".config" / "fish" / "config.fish"
            ]
        else:
            # Generic fallback
            candidates = [
                self._home_dir / ".profile",
                self._home_dir / ".bashrc"
            ]
        
        # Return existing files first, then potential creation targets
        existing = [p for p in candidates if p.exists()]
        if existing:
            return existing
        
        # If no existing files, return the primary candidate for creation
        return [candidates[0]] if candidates else []
    
    def _get_windows_profile_paths(self) -> List[Path]:
        """Get Windows profile paths."""
        if self.shell == Shell.POWERSHELL:
            # PowerShell profile locations
            try:
                # Try to get PowerShell profile path
                result = subprocess.run(
                    ["powershell", "-Command", "$PROFILE"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    profile_path = Path(result.stdout.strip())
                    return [profile_path]
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
            
            # Fallback to common PowerShell profile locations
            documents = Path.home() / "Documents"
            candidates = [
                documents / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
                documents / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
            ]
        else:
            # For CMD, we'll use environment variables (handled separately)
            candidates = []
        
        return candidates
    
    def get_environment_status(self) -> EnvironmentStatus:
        """Get current environment configuration status."""
        enable_plugins_set = self.ENABLE_PLUGINS_VAR in os.environ
        enable_plugins_value = os.environ.get(self.ENABLE_PLUGINS_VAR)
        
        profile_paths = self.get_shell_profile_paths()
        config_file = profile_paths[0] if profile_paths else None
        
        backup_exists = False
        if config_file:
            backup_path = Path(str(config_file) + self.BACKUP_SUFFIX)
            backup_exists = backup_path.exists()
        
        # Check if profile is writable
        writable = True
        if config_file:
            try:
                # Test if we can write to the directory
                config_file.parent.mkdir(parents=True, exist_ok=True)
                if config_file.exists():
                    writable = os.access(config_file, os.W_OK)
                else:
                    writable = os.access(config_file.parent, os.W_OK)
            except (PermissionError, OSError):
                writable = False
        
        # Check for conflicts
        conflicts = []
        if enable_plugins_set and enable_plugins_value != self.ENABLE_PLUGINS_VALUE:
            conflicts.append(f"ENABLE_PLUGINS is set to '{enable_plugins_value}' instead of '{self.ENABLE_PLUGINS_VALUE}'")
        
        return EnvironmentStatus(
            platform=self.platform,
            shell=self.shell,
            enable_plugins_set=enable_plugins_set,
            enable_plugins_value=enable_plugins_value,
            config_file=config_file,
            backup_exists=backup_exists,
            containerized=self._is_containerized(),
            writable=writable,
            conflicts=conflicts
        )
    
    def setup_environment(self, force: bool = False) -> Tuple[bool, str, List[str]]:
        """Configure environment for Claude Code plugins.
        
        Args:
            force: Force setup even if already configured
            
        Returns:
            Tuple of (success, message, warnings)
        """
        status = self.get_environment_status()
        warnings = []
        
        # Check if already configured
        if status.enable_plugins_set and not force:
            if status.enable_plugins_value == self.ENABLE_PLUGINS_VALUE:
                return True, "Environment already configured for Claude Code plugins", []
            else:
                warnings.append(f"ENABLE_PLUGINS is set to '{status.enable_plugins_value}' instead of '{self.ENABLE_PLUGINS_VALUE}'")
        
        # Check permissions
        if not status.writable:
            return False, f"Cannot write to shell profile: {status.config_file}", warnings
        
        # Handle different platforms
        if self.platform == Platform.WINDOWS and self.shell == Shell.CMD:
            return self._setup_windows_environment_variables()
        else:
            return self._setup_shell_profile(status, force)
    
    def _setup_shell_profile(self, status: EnvironmentStatus, force: bool) -> Tuple[bool, str, List[str]]:
        """Setup environment via shell profile modification."""
        if not status.config_file:
            return False, f"No suitable shell profile found for {self.shell.value}", []
        
        try:
            # Create backup
            backup_result = self.backup_profile(status.config_file)
            if not backup_result[0]:
                return False, f"Failed to create backup: {backup_result[1]}", []
            
            # Check if already configured
            if not force and self._is_already_configured(status.config_file):
                return True, "Environment already configured in shell profile", []
            
            # Add environment variable
            export_line = self._get_export_line()
            
            # Read existing content
            content = ""
            if status.config_file.exists():
                content = status.config_file.read_text(encoding='utf-8')
            
            # Add our configuration if not present
            if self.PACC_COMMENT not in content:
                if content and not content.endswith('\n'):
                    content += '\n'
                content += f'\n{self.PACC_COMMENT}\n{export_line}\n'
                
                # Ensure parent directory exists
                status.config_file.parent.mkdir(parents=True, exist_ok=True)
                
                # Write updated content
                status.config_file.write_text(content, encoding='utf-8')
            
            return True, f"Environment configured in {status.config_file}", []
            
        except Exception as e:
            return False, f"Failed to setup environment: {str(e)}", []
    
    def _setup_windows_environment_variables(self) -> Tuple[bool, str, List[str]]:
        """Setup environment variables on Windows via registry."""
        try:
            # Use setx command to set user environment variable
            result = subprocess.run([
                "setx", 
                self.ENABLE_PLUGINS_VAR, 
                self.ENABLE_PLUGINS_VALUE
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return True, "Environment variable set via Windows registry", [
                    "You may need to restart your terminal for changes to take effect"
                ]
            else:
                return False, f"Failed to set environment variable: {result.stderr}", []
                
        except Exception as e:
            return False, f"Failed to set Windows environment variable: {str(e)}", []
    
    def _get_export_line(self) -> str:
        """Get the appropriate export line for the current shell."""
        if self.shell == Shell.FISH:
            return f"set -x {self.ENABLE_PLUGINS_VAR} {self.ENABLE_PLUGINS_VALUE}"
        else:
            return f"export {self.ENABLE_PLUGINS_VAR}={self.ENABLE_PLUGINS_VALUE}"
    
    def _is_already_configured(self, profile_path: Path) -> bool:
        """Check if the profile is already configured with ENABLE_PLUGINS."""
        if not profile_path.exists():
            return False
        
        try:
            content = profile_path.read_text(encoding='utf-8')
            return (self.ENABLE_PLUGINS_VAR in content and 
                    self.PACC_COMMENT in content)
        except Exception:
            return False
    
    def backup_profile(self, profile_path: Path) -> Tuple[bool, str]:
        """Create a backup of the shell profile.
        
        Args:
            profile_path: Path to the profile file
            
        Returns:
            Tuple of (success, message)
        """
        if not profile_path.exists():
            return True, "No existing profile to backup"
        
        try:
            backup_path = Path(str(profile_path) + self.BACKUP_SUFFIX)
            
            # Add timestamp if backup already exists
            if backup_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = Path(f"{profile_path}.{timestamp}.backup")
            
            # Copy the file
            import shutil as sh
            sh.copy2(profile_path, backup_path)
            
            return True, f"Backup created at {backup_path}"
            
        except Exception as e:
            return False, f"Failed to create backup: {str(e)}"
    
    def verify_environment(self) -> Tuple[bool, str, Dict[str, any]]:
        """Verify that the environment is properly configured.
        
        Returns:
            Tuple of (success, message, details)
        """
        status = self.get_environment_status()
        details = {
            "platform": status.platform.value,
            "shell": status.shell.value,
            "enable_plugins_set": status.enable_plugins_set,
            "enable_plugins_value": status.enable_plugins_value,
            "config_file": str(status.config_file) if status.config_file else None,
            "containerized": status.containerized,
            "conflicts": status.conflicts
        }
        
        if not status.enable_plugins_set:
            return False, "ENABLE_PLUGINS environment variable is not set", details
        
        if status.enable_plugins_value != self.ENABLE_PLUGINS_VALUE:
            return False, f"ENABLE_PLUGINS is set to '{status.enable_plugins_value}' but should be '{self.ENABLE_PLUGINS_VALUE}'", details
        
        if status.conflicts:
            return False, f"Environment conflicts detected: {'; '.join(status.conflicts)}", details
        
        return True, "Environment is properly configured for Claude Code plugins", details
    
    def reset_environment(self) -> Tuple[bool, str, List[str]]:
        """Remove PACC environment modifications.
        
        Returns:
            Tuple of (success, message, warnings)
        """
        status = self.get_environment_status()
        warnings = []
        
        if self.platform == Platform.WINDOWS and self.shell == Shell.CMD:
            return self._reset_windows_environment()
        else:
            return self._reset_shell_profile(status)
    
    def _reset_shell_profile(self, status: EnvironmentStatus) -> Tuple[bool, str, List[str]]:
        """Reset shell profile by removing PACC modifications."""
        if not status.config_file or not status.config_file.exists():
            return True, "No shell profile to reset", []
        
        try:
            content = status.config_file.read_text(encoding='utf-8')
            
            # Check if our modifications are present
            if self.PACC_COMMENT not in content:
                return True, "No PACC modifications found in shell profile", []
            
            # Remove PACC modifications
            lines = content.split('\n')
            filtered_lines = []
            skip_next = False
            
            for line in lines:
                if self.PACC_COMMENT in line:
                    skip_next = True
                    continue
                elif skip_next and (self.ENABLE_PLUGINS_VAR in line):
                    skip_next = False
                    continue
                else:
                    skip_next = False
                    filtered_lines.append(line)
            
            # Write cleaned content
            cleaned_content = '\n'.join(filtered_lines)
            status.config_file.write_text(cleaned_content, encoding='utf-8')
            
            return True, f"PACC modifications removed from {status.config_file}", []
            
        except Exception as e:
            return False, f"Failed to reset shell profile: {str(e)}", []
    
    def _reset_windows_environment(self) -> Tuple[bool, str, List[str]]:
        """Reset Windows environment variables."""
        try:
            # Remove the environment variable
            result = subprocess.run([
                "reg", "delete", 
                "HKCU\\Environment", 
                "/v", self.ENABLE_PLUGINS_VAR, 
                "/f"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return True, "Environment variable removed from Windows registry", [
                    "You may need to restart your terminal for changes to take effect"
                ]
            else:
                # Variable might not exist, which is fine
                if "cannot find" in result.stderr.lower():
                    return True, "Environment variable was not set", []
                return False, f"Failed to remove environment variable: {result.stderr}", []
                
        except Exception as e:
            return False, f"Failed to reset Windows environment: {str(e)}", []


def get_environment_manager() -> EnvironmentManager:
    """Get a configured environment manager instance."""
    return EnvironmentManager()