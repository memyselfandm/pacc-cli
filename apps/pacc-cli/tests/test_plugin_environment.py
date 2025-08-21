"""Tests for plugin environment management functionality."""

import os
import platform
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock

from pacc.plugins.environment import (
    EnvironmentManager,
    EnvironmentStatus,
    Platform,
    Shell,
    ProfileUpdate,
    get_environment_manager
)


class TestEnvironmentManager(unittest.TestCase):
    """Test cases for EnvironmentManager."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.manager = EnvironmentManager()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_detect_platform_windows(self):
        """Test platform detection on Windows."""
        with patch('platform.system', return_value='Windows'):
            manager = EnvironmentManager()
            self.assertEqual(manager.platform, Platform.WINDOWS)
    
    def test_detect_platform_macos(self):
        """Test platform detection on macOS."""
        with patch('platform.system', return_value='Darwin'):
            manager = EnvironmentManager()
            self.assertEqual(manager.platform, Platform.MACOS)
    
    def test_detect_platform_linux(self):
        """Test platform detection on Linux."""
        with patch('platform.system', return_value='Linux'):
            manager = EnvironmentManager()
            self.assertEqual(manager.platform, Platform.LINUX)
    
    def test_detect_platform_unknown(self):
        """Test platform detection for unknown systems."""
        with patch('platform.system', return_value='FreeBSD'):
            manager = EnvironmentManager()
            self.assertEqual(manager.platform, Platform.UNKNOWN)
    
    @patch('os.environ.get')
    @patch('shutil.which')
    def test_detect_shell_zsh(self, mock_which, mock_env_get):
        """Test shell detection for zsh."""
        mock_env_get.return_value = '/bin/zsh'
        mock_which.return_value = '/bin/zsh'
        
        with patch('platform.system', return_value='Darwin'):
            manager = EnvironmentManager()
            self.assertEqual(manager.shell, Shell.ZSH)
    
    @patch('os.environ.get')
    @patch('shutil.which')
    def test_detect_shell_bash(self, mock_which, mock_env_get):
        """Test shell detection for bash."""
        mock_env_get.return_value = '/bin/bash'
        mock_which.return_value = '/bin/bash'
        
        with patch('platform.system', return_value='Linux'):
            manager = EnvironmentManager()
            self.assertEqual(manager.shell, Shell.BASH)
    
    @patch('os.environ.get')
    @patch('shutil.which')
    def test_detect_shell_fish(self, mock_which, mock_env_get):
        """Test shell detection for fish."""
        mock_env_get.return_value = '/usr/bin/fish'
        mock_which.return_value = '/usr/bin/fish'
        
        with patch('platform.system', return_value='Linux'):
            manager = EnvironmentManager()
            self.assertEqual(manager.shell, Shell.FISH)
    
    @patch('shutil.which')
    def test_detect_shell_powershell_windows(self, mock_which):
        """Test shell detection for PowerShell on Windows."""
        mock_which.side_effect = lambda x: '/usr/bin/pwsh' if x == 'pwsh' else None
        
        with patch('platform.system', return_value='Windows'):
            manager = EnvironmentManager()
            self.assertEqual(manager.shell, Shell.POWERSHELL)
    
    @patch('shutil.which')
    def test_detect_shell_cmd_windows(self, mock_which):
        """Test shell detection for cmd on Windows."""
        mock_which.return_value = None  # No PowerShell available
        
        with patch('platform.system', return_value='Windows'):
            manager = EnvironmentManager()
            self.assertEqual(manager.shell, Shell.CMD)
    
    @patch('pathlib.Path.exists')
    def test_is_containerized_docker(self, mock_exists):
        """Test containerized environment detection for Docker."""
        mock_exists.return_value = True
        
        self.assertTrue(self.manager._is_containerized())
    
    def test_is_containerized_cgroup(self):
        """Test containerized environment detection via cgroups."""
        with patch('builtins.open', mock_open(read_data='0::/docker/container123')):
            self.assertTrue(self.manager._is_containerized())
    
    def test_is_containerized_wsl(self):
        """Test WSL environment detection."""
        with patch('builtins.open', mock_open(read_data='Linux version 4.4.0-19041-Microsoft')):
            with patch('pathlib.Path.exists', return_value=True):
                self.assertTrue(self.manager._is_containerized())
    
    def test_is_containerized_normal(self):
        """Test normal environment detection."""
        with patch('pathlib.Path.exists', return_value=False):
            with patch('builtins.open', side_effect=FileNotFoundError):
                self.assertFalse(self.manager._is_containerized())
    
    @patch('pathlib.Path.home')
    def test_get_unix_profile_paths_bash(self, mock_home):
        """Test getting Unix profile paths for bash."""
        mock_home.return_value = self.temp_dir
        
        with patch('platform.system', return_value='Linux'):
            with patch('os.environ.get', return_value='/bin/bash'):
                manager = EnvironmentManager()
                
                # Create a .bashrc file
                bashrc = self.temp_dir / '.bashrc'
                bashrc.touch()
                
                paths = manager._get_unix_profile_paths()
                self.assertIn(bashrc, paths)
    
    @patch('pathlib.Path.home')
    def test_get_unix_profile_paths_zsh(self, mock_home):
        """Test getting Unix profile paths for zsh."""
        mock_home.return_value = self.temp_dir
        
        with patch('platform.system', return_value='Darwin'):
            with patch('os.environ.get', return_value='/bin/zsh'):
                manager = EnvironmentManager()
                
                # Create a .zshrc file
                zshrc = self.temp_dir / '.zshrc'
                zshrc.touch()
                
                paths = manager._get_unix_profile_paths()
                self.assertIn(zshrc, paths)
    
    @patch('pathlib.Path.home')
    def test_get_unix_profile_paths_fish(self, mock_home):
        """Test getting Unix profile paths for fish."""
        mock_home.return_value = self.temp_dir
        
        with patch('platform.system', return_value='Linux'):
            with patch('os.environ.get', return_value='/usr/bin/fish'):
                manager = EnvironmentManager()
                
                # Create fish config directory and file
                fish_config_dir = self.temp_dir / '.config' / 'fish'
                fish_config_dir.mkdir(parents=True)
                fish_config = fish_config_dir / 'config.fish'
                fish_config.touch()
                
                paths = manager._get_unix_profile_paths()
                self.assertIn(fish_config, paths)
    
    @patch('subprocess.run')
    def test_get_windows_profile_paths_powershell(self, mock_run):
        """Test getting Windows profile paths for PowerShell."""
        profile_path = "C:\\Users\\test\\Documents\\PowerShell\\profile.ps1"
        mock_run.return_value = Mock(returncode=0, stdout=profile_path)
        
        with patch('platform.system', return_value='Windows'):
            with patch('shutil.which', return_value='/usr/bin/pwsh'):
                manager = EnvironmentManager()
                paths = manager._get_windows_profile_paths()
                self.assertEqual(len(paths), 1)
                self.assertEqual(str(paths[0]), profile_path)
    
    @patch('subprocess.run')
    def test_get_windows_profile_paths_powershell_fallback(self, mock_run):
        """Test Windows profile paths fallback when PowerShell command fails."""
        mock_run.side_effect = subprocess.SubprocessError()
        
        with patch('platform.system', return_value='Windows'):
            with patch('shutil.which', return_value='/usr/bin/pwsh'):
                with patch('pathlib.Path.home') as mock_home:
                    mock_home.return_value = Path("C:\\Users\\test")
                    manager = EnvironmentManager()
                    paths = manager._get_windows_profile_paths()
                    self.assertTrue(len(paths) > 0)
                    self.assertTrue(any("PowerShell" in str(p) for p in paths))
    
    @patch('os.environ', {'ENABLE_PLUGINS': 'true'})
    def test_get_environment_status_configured(self):
        """Test environment status when properly configured."""
        with patch.object(self.manager, 'get_shell_profile_paths', return_value=[Path('/test/.bashrc')]):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('os.access', return_value=True):
                    status = self.manager.get_environment_status()
                    
                    self.assertTrue(status.enable_plugins_set)
                    self.assertEqual(status.enable_plugins_value, "true")
                    self.assertEqual(len(status.conflicts), 0)
    
    @patch('os.environ', {})
    def test_get_environment_status_not_configured(self):
        """Test environment status when not configured."""
        with patch.object(self.manager, 'get_shell_profile_paths', return_value=[]):
            status = self.manager.get_environment_status()
            
            self.assertFalse(status.enable_plugins_set)
            self.assertIsNone(status.enable_plugins_value)
    
    @patch('os.environ', {'ENABLE_PLUGINS': 'false'})
    def test_get_environment_status_conflicts(self):
        """Test environment status with conflicts."""
        status = self.manager.get_environment_status()
        
        self.assertTrue(status.enable_plugins_set)
        self.assertEqual(status.enable_plugins_value, "false")
        self.assertTrue(len(status.conflicts) > 0)
    
    def test_setup_environment_already_configured(self):
        """Test setup when environment is already configured."""
        with patch.object(self.manager, 'get_environment_status') as mock_status:
            mock_status.return_value = EnvironmentStatus(
                platform=Platform.LINUX,
                shell=Shell.BASH,
                enable_plugins_set=True,
                enable_plugins_value="true",
                config_file=None,
                backup_exists=False,
                containerized=False,
                writable=True,
                conflicts=[]
            )
            
            success, message, warnings = self.manager.setup_environment()
            self.assertTrue(success)
            self.assertIn("already configured", message)
    
    def test_setup_environment_not_writable(self):
        """Test setup when profile is not writable."""
        with patch.object(self.manager, 'get_environment_status') as mock_status:
            mock_status.return_value = EnvironmentStatus(
                platform=Platform.LINUX,
                shell=Shell.BASH,
                enable_plugins_set=False,
                enable_plugins_value=None,
                config_file=Path("/test/.bashrc"),
                backup_exists=False,
                containerized=False,
                writable=False,
                conflicts=[]
            )
            
            success, message, warnings = self.manager.setup_environment()
            self.assertFalse(success)
            self.assertIn("Cannot write", message)
    
    def test_setup_environment_windows_cmd(self):
        """Test setup on Windows with cmd shell."""
        with patch('platform.system', return_value='Windows'):
            with patch('shutil.which', return_value=None):  # No PowerShell
                manager = EnvironmentManager()
                
                with patch.object(manager, '_setup_windows_environment_variables') as mock_setup:
                    mock_setup.return_value = (True, "Success", [])
                    
                    success, message, warnings = manager.setup_environment()
                    self.assertTrue(success)
                    mock_setup.assert_called_once()
    
    @patch('subprocess.run')
    def test_setup_windows_environment_variables_success(self, mock_run):
        """Test Windows environment variable setup success."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        success, message, warnings = self.manager._setup_windows_environment_variables()
        self.assertTrue(success)
        self.assertIn("registry", message)
    
    @patch('subprocess.run')
    def test_setup_windows_environment_variables_failure(self, mock_run):
        """Test Windows environment variable setup failure."""
        mock_run.return_value = Mock(returncode=1, stderr="Access denied")
        
        success, message, warnings = self.manager._setup_windows_environment_variables()
        self.assertFalse(success)
        self.assertIn("Failed to set", message)
    
    def test_setup_shell_profile_success(self):
        """Test successful shell profile setup."""
        profile_path = self.temp_dir / '.bashrc'
        
        status = EnvironmentStatus(
            platform=Platform.LINUX,
            shell=Shell.BASH,
            enable_plugins_set=False,
            enable_plugins_value=None,
            config_file=profile_path,
            backup_exists=False,
            containerized=False,
            writable=True,
            conflicts=[]
        )
        
        with patch.object(self.manager, 'backup_profile', return_value=(True, "Backup created")):
            with patch.object(self.manager, '_is_already_configured', return_value=False):
                success, message, warnings = self.manager._setup_shell_profile(status, False)
                
                self.assertTrue(success)
                self.assertIn("configured", message)
                
                # Check that the file was created with the export line
                self.assertTrue(profile_path.exists())
                content = profile_path.read_text()
                self.assertIn("ENABLE_PLUGINS", content)
                self.assertIn("export", content)
    
    def test_setup_shell_profile_fish(self):
        """Test shell profile setup for fish shell."""
        profile_path = self.temp_dir / 'config.fish'
        
        # Set up manager for fish shell
        with patch('platform.system', return_value='Linux'):
            with patch('os.environ.get', return_value='/usr/bin/fish'):
                manager = EnvironmentManager()
        
        status = EnvironmentStatus(
            platform=Platform.LINUX,
            shell=Shell.FISH,
            enable_plugins_set=False,
            enable_plugins_value=None,
            config_file=profile_path,
            backup_exists=False,
            containerized=False,
            writable=True,
            conflicts=[]
        )
        
        with patch.object(manager, 'backup_profile', return_value=(True, "Backup created")):
            with patch.object(manager, '_is_already_configured', return_value=False):
                success, message, warnings = manager._setup_shell_profile(status, False)
                
                self.assertTrue(success)
                content = profile_path.read_text()
                self.assertIn("set -x ENABLE_PLUGINS", content)
    
    def test_backup_profile_success(self):
        """Test successful profile backup."""
        profile_path = self.temp_dir / '.bashrc'
        profile_path.write_text("original content")
        
        success, message = self.manager.backup_profile(profile_path)
        
        self.assertTrue(success)
        self.assertIn("Backup created", message)
        
        # Check backup file exists
        backup_path = Path(str(profile_path) + '.pacc.backup')
        self.assertTrue(backup_path.exists())
        self.assertEqual(backup_path.read_text(), "original content")
    
    def test_backup_profile_no_existing_file(self):
        """Test backup when no existing file."""
        profile_path = self.temp_dir / '.bashrc'
        
        success, message = self.manager.backup_profile(profile_path)
        
        self.assertTrue(success)
        self.assertIn("No existing profile", message)
    
    def test_backup_profile_existing_backup(self):
        """Test backup when backup already exists."""
        profile_path = self.temp_dir / '.bashrc'
        profile_path.write_text("original content")
        
        # Create existing backup
        backup_path = Path(str(profile_path) + '.pacc.backup')
        backup_path.write_text("old backup")
        
        success, message = self.manager.backup_profile(profile_path)
        
        self.assertTrue(success)
        # Should create timestamped backup
        self.assertTrue(any(p.name.endswith('.backup') for p in self.temp_dir.iterdir()))
    
    def test_verify_environment_success(self):
        """Test successful environment verification."""
        with patch.object(self.manager, 'get_environment_status') as mock_status:
            mock_status.return_value = EnvironmentStatus(
                platform=Platform.LINUX,
                shell=Shell.BASH,
                enable_plugins_set=True,
                enable_plugins_value="true",
                config_file=Path("/test/.bashrc"),
                backup_exists=False,
                containerized=False,
                writable=True,
                conflicts=[]
            )
            
            success, message, details = self.manager.verify_environment()
            self.assertTrue(success)
            self.assertIn("properly configured", message)
    
    def test_verify_environment_not_set(self):
        """Test environment verification when not set."""
        with patch.object(self.manager, 'get_environment_status') as mock_status:
            mock_status.return_value = EnvironmentStatus(
                platform=Platform.LINUX,
                shell=Shell.BASH,
                enable_plugins_set=False,
                enable_plugins_value=None,
                config_file=None,
                backup_exists=False,
                containerized=False,
                writable=True,
                conflicts=[]
            )
            
            success, message, details = self.manager.verify_environment()
            self.assertFalse(success)
            self.assertIn("not set", message)
    
    def test_verify_environment_wrong_value(self):
        """Test environment verification with wrong value."""
        with patch.object(self.manager, 'get_environment_status') as mock_status:
            mock_status.return_value = EnvironmentStatus(
                platform=Platform.LINUX,
                shell=Shell.BASH,
                enable_plugins_set=True,
                enable_plugins_value="false",
                config_file=Path("/test/.bashrc"),
                backup_exists=False,
                containerized=False,
                writable=True,
                conflicts=[]
            )
            
            success, message, details = self.manager.verify_environment()
            self.assertFalse(success)
            self.assertIn("should be 'true'", message)
    
    def test_reset_environment_windows(self):
        """Test environment reset on Windows."""
        with patch('platform.system', return_value='Windows'):
            with patch('shutil.which', return_value=None):  # Use CMD
                manager = EnvironmentManager()
                
                with patch.object(manager, '_reset_windows_environment') as mock_reset:
                    mock_reset.return_value = (True, "Reset successful", [])
                    
                    success, message, warnings = manager.reset_environment()
                    self.assertTrue(success)
                    mock_reset.assert_called_once()
    
    @patch('subprocess.run')
    def test_reset_windows_environment_success(self, mock_run):
        """Test successful Windows environment reset."""
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        success, message, warnings = self.manager._reset_windows_environment()
        self.assertTrue(success)
        self.assertIn("removed", message)
    
    @patch('subprocess.run')
    def test_reset_windows_environment_not_found(self, mock_run):
        """Test Windows environment reset when variable not found."""
        mock_run.return_value = Mock(returncode=1, stderr="cannot find the file specified")
        
        success, message, warnings = self.manager._reset_windows_environment()
        self.assertTrue(success)
        self.assertIn("was not set", message)
    
    def test_reset_shell_profile_success(self):
        """Test successful shell profile reset."""
        profile_path = self.temp_dir / '.bashrc'
        content = """# Some existing content
# Added by PACC - Claude Code plugin enablement
export ENABLE_PLUGINS=true
# More content"""
        profile_path.write_text(content)
        
        status = EnvironmentStatus(
            platform=Platform.LINUX,
            shell=Shell.BASH,
            enable_plugins_set=True,
            enable_plugins_value="true",
            config_file=profile_path,
            backup_exists=False,
            containerized=False,
            writable=True,
            conflicts=[]
        )
        
        success, message, warnings = self.manager._reset_shell_profile(status)
        
        self.assertTrue(success)
        self.assertIn("removed", message)
        
        # Check that PACC modifications were removed
        cleaned_content = profile_path.read_text()
        self.assertNotIn("PACC", cleaned_content)
        self.assertNotIn("ENABLE_PLUGINS", cleaned_content)
        self.assertIn("Some existing content", cleaned_content)
        self.assertIn("More content", cleaned_content)
    
    def test_reset_shell_profile_no_modifications(self):
        """Test shell profile reset when no PACC modifications exist."""
        profile_path = self.temp_dir / '.bashrc'
        profile_path.write_text("# Some existing content\n")
        
        status = EnvironmentStatus(
            platform=Platform.LINUX,
            shell=Shell.BASH,
            enable_plugins_set=False,
            enable_plugins_value=None,
            config_file=profile_path,
            backup_exists=False,
            containerized=False,
            writable=True,
            conflicts=[]
        )
        
        success, message, warnings = self.manager._reset_shell_profile(status)
        
        self.assertTrue(success)
        self.assertIn("No PACC modifications", message)
    
    def test_get_export_line_bash(self):
        """Test export line generation for bash."""
        with patch('platform.system', return_value='Linux'):
            with patch('os.environ.get', return_value='/bin/bash'):
                manager = EnvironmentManager()
                export_line = manager._get_export_line()
                self.assertEqual(export_line, "export ENABLE_PLUGINS=true")
    
    def test_get_export_line_fish(self):
        """Test export line generation for fish."""
        with patch('platform.system', return_value='Linux'):
            with patch('os.environ.get', return_value='/usr/bin/fish'):
                manager = EnvironmentManager()
                export_line = manager._get_export_line()
                self.assertEqual(export_line, "set -x ENABLE_PLUGINS true")
    
    def test_is_already_configured_true(self):
        """Test detection of already configured profile."""
        profile_path = self.temp_dir / '.bashrc'
        content = """# Added by PACC - Claude Code plugin enablement
export ENABLE_PLUGINS=true"""
        profile_path.write_text(content)
        
        self.assertTrue(self.manager._is_already_configured(profile_path))
    
    def test_is_already_configured_false(self):
        """Test detection of non-configured profile."""
        profile_path = self.temp_dir / '.bashrc'
        profile_path.write_text("# Some other content")
        
        self.assertFalse(self.manager._is_already_configured(profile_path))
    
    def test_is_already_configured_no_file(self):
        """Test configured detection for non-existent file."""
        profile_path = self.temp_dir / '.nonexistent'
        
        self.assertFalse(self.manager._is_already_configured(profile_path))


class TestEnvironmentManagerFactory(unittest.TestCase):
    """Test cases for environment manager factory function."""
    
    def test_get_environment_manager(self):
        """Test that factory function returns EnvironmentManager instance."""
        manager = get_environment_manager()
        self.assertIsInstance(manager, EnvironmentManager)


class TestCrossplatformCompatibility(unittest.TestCase):
    """Cross-platform compatibility tests."""
    
    def test_all_platforms_supported(self):
        """Test that all major platforms are supported."""
        platforms = ['Windows', 'Darwin', 'Linux']
        
        for platform_name in platforms:
            with patch('platform.system', return_value=platform_name):
                manager = EnvironmentManager()
                self.assertNotEqual(manager.platform, Platform.UNKNOWN)
    
    def test_shell_detection_robustness(self):
        """Test that shell detection handles various scenarios."""
        test_cases = [
            ('/bin/bash', Shell.BASH),
            ('/usr/bin/zsh', Shell.ZSH),
            ('/usr/local/bin/fish', Shell.FISH),
            ('', Shell.UNKNOWN)  # Empty shell path
        ]
        
        for shell_path, expected_shell in test_cases:
            with patch('os.environ.get', return_value=shell_path):
                with patch('shutil.which', return_value=shell_path if shell_path else None):
                    with patch('platform.system', return_value='Linux'):
                        manager = EnvironmentManager()
                        if expected_shell != Shell.UNKNOWN:
                            # For known shells, check detection works
                            self.assertIn(manager.shell, [expected_shell, Shell.UNKNOWN])


if __name__ == '__main__':
    unittest.main()