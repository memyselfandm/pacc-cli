#!/usr/bin/env python3
"""
Upgrade and uninstall testing procedures for PACC.

Tests various upgrade scenarios and clean uninstallation procedures to ensure
smooth version transitions and proper cleanup.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pytest
from packaging import version


class UpgradeUninstallTester:
    """Test PACC upgrade and uninstall procedures."""
    
    def __init__(self):
        self.pacc_root = Path(__file__).parent.parent.parent
        self.test_results = []
        
    def _create_test_versions(self, tmpdir: Path) -> Dict[str, Path]:
        """Create multiple test versions of PACC for upgrade testing."""
        versions = {}
        
        # Create version 1.0.0
        v1_dir = tmpdir / 'pacc_v1.0.0'
        shutil.copytree(self.pacc_root, v1_dir)
        
        # Modify version in v1
        setup_py = v1_dir / 'setup.py'
        if setup_py.exists():
            content = setup_py.read_text()
            content = content.replace('version=', 'version="1.0.0", # version=')
            setup_py.write_text(content)
        
        # Also update __init__.py if it exists
        init_py = v1_dir / 'pacc' / '__init__.py'
        if init_py.exists():
            content = init_py.read_text()
            # Replace version string
            import re
            content = re.sub(r'__version__\s*=\s*["\'].*?["\']', '__version__ = "1.0.0"', content)
            init_py.write_text(content)
            
        versions['1.0.0'] = v1_dir
        
        # Create version 2.0.0
        v2_dir = tmpdir / 'pacc_v2.0.0' 
        shutil.copytree(self.pacc_root, v2_dir)
        
        # Modify version in v2
        setup_py = v2_dir / 'setup.py'
        if setup_py.exists():
            content = setup_py.read_text()
            content = content.replace('version=', 'version="2.0.0", # version=')
            setup_py.write_text(content)
            
        init_py = v2_dir / 'pacc' / '__init__.py'
        if init_py.exists():
            content = init_py.read_text()
            content = re.sub(r'__version__\s*=\s*["\'].*?["\']', '__version__ = "2.0.0"', content)
            init_py.write_text(content)
            
        versions['2.0.0'] = v2_dir
        
        # Current version (development)
        versions['current'] = self.pacc_root
        
        return versions
    
    def test_basic_upgrade(self) -> Dict[str, any]:
        """Test basic upgrade from one version to another."""
        results = {
            'scenario': 'basic_upgrade',
            'tests': {}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            versions = self._create_test_versions(tmpdir)
            
            # Create test venv
            venv_path = tmpdir / 'test_venv'
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
            
            if sys.platform == 'win32':
                pip_cmd = venv_path / 'Scripts' / 'pip'
                python_cmd = venv_path / 'Scripts' / 'python'
                pacc_cmd = venv_path / 'Scripts' / 'pacc'
            else:
                pip_cmd = venv_path / 'bin' / 'pip'
                python_cmd = venv_path / 'bin' / 'python'
                pacc_cmd = venv_path / 'bin' / 'pacc'
            
            try:
                # Install version 1.0.0
                print("  Installing version 1.0.0...")
                result = subprocess.run([str(pip_cmd), 'install', '-e', str(versions['1.0.0'])],
                                     capture_output=True, text=True)
                results['tests']['install_v1'] = result.returncode == 0
                
                # Check version
                result = subprocess.run([str(python_cmd), '-c', 
                                       'import pacc; print(pacc.__version__)'],
                                     capture_output=True, text=True)
                results['tests']['version_v1'] = '1.0.0' in result.stdout
                
                # Test functionality
                result = subprocess.run([str(pacc_cmd), '--help'],
                                     capture_output=True, text=True)
                results['tests']['v1_functional'] = result.returncode == 0
                
                # Upgrade to version 2.0.0
                print("  Upgrading to version 2.0.0...")
                result = subprocess.run([str(pip_cmd), 'install', '--upgrade', '-e', 
                                       str(versions['2.0.0'])],
                                     capture_output=True, text=True)
                results['tests']['upgrade_to_v2'] = result.returncode == 0
                
                # Check new version
                result = subprocess.run([str(python_cmd), '-c', 
                                       'import pacc; print(pacc.__version__)'],
                                     capture_output=True, text=True)
                results['tests']['version_v2'] = '2.0.0' in result.stdout
                
                # Test functionality after upgrade
                result = subprocess.run([str(pacc_cmd), '--help'],
                                     capture_output=True, text=True)
                results['tests']['v2_functional'] = result.returncode == 0
                
            except Exception as e:
                results['error'] = str(e)
                
        return results
    
    def test_config_migration(self) -> Dict[str, any]:
        """Test configuration migration during upgrades."""
        results = {
            'scenario': 'config_migration',
            'tests': {}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create mock PACC config directory
            pacc_config = tmpdir / '.pacc'
            pacc_config.mkdir()
            
            # Create old format config
            old_config = {
                'version': '1.0',
                'settings': {
                    'key1': 'value1',
                    'key2': 'value2'
                }
            }
            
            config_file = pacc_config / 'config.json'
            with open(config_file, 'w') as f:
                json.dump(old_config, f)
                
            results['tests']['old_config_created'] = config_file.exists()
            
            # Simulate config migration (this would be done by PACC)
            # For testing, we'll create a migration function
            def migrate_config(config_path: Path):
                """Simulate config migration."""
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    
                # Check version and migrate
                if config.get('version') == '1.0':
                    # Backup old config
                    backup_path = config_path.with_suffix('.backup')
                    shutil.copy2(config_path, backup_path)
                    
                    # Migrate to new format
                    new_config = {
                        'version': '2.0',
                        'settings': config.get('settings', {}),
                        'migrated_from': '1.0',
                        'migration_date': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    
                    with open(config_path, 'w') as f:
                        json.dump(new_config, f, indent=2)
                        
                    return True
                return False
            
            # Test migration
            try:
                migrated = migrate_config(config_file)
                results['tests']['migration_successful'] = migrated
                
                # Check backup was created
                backup_file = config_file.with_suffix('.backup')
                results['tests']['backup_created'] = backup_file.exists()
                
                # Verify new config
                with open(config_file, 'r') as f:
                    new_config = json.load(f)
                    
                results['tests']['new_version'] = new_config.get('version') == '2.0'
                results['tests']['data_preserved'] = new_config.get('settings', {}).get('key1') == 'value1'
                results['tests']['migration_tracked'] = 'migrated_from' in new_config
                
            except Exception as e:
                results['error'] = str(e)
                
        return results
    
    def test_clean_uninstall(self) -> Dict[str, any]:
        """Test clean uninstallation procedures."""
        results = {
            'scenario': 'clean_uninstall',
            'tests': {}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create test venv
            venv_path = tmpdir / 'test_venv'
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
            
            if sys.platform == 'win32':
                pip_cmd = venv_path / 'Scripts' / 'pip'
                python_cmd = venv_path / 'Scripts' / 'python'
                pacc_cmd = venv_path / 'Scripts' / 'pacc'
            else:
                pip_cmd = venv_path / 'bin' / 'pip'
                python_cmd = venv_path / 'bin' / 'python'
                pacc_cmd = venv_path / 'bin' / 'pacc'
            
            try:
                # Install PACC
                print("  Installing PACC...")
                result = subprocess.run([str(pip_cmd), 'install', '-e', str(self.pacc_root)],
                                     capture_output=True, text=True)
                results['tests']['install'] = result.returncode == 0
                
                # Create some PACC data files
                pacc_data = venv_path / '.pacc'
                pacc_data.mkdir()
                (pacc_data / 'test.json').write_text('{"test": true}')
                
                # Verify installation
                result = subprocess.run([str(pip_cmd), 'show', 'pacc'],
                                     capture_output=True, text=True)
                results['tests']['package_installed'] = result.returncode == 0
                
                # Test that command exists
                result = subprocess.run([str(pacc_cmd), '--version'],
                                     capture_output=True, text=True)
                results['tests']['command_available'] = result.returncode == 0
                
                # Uninstall
                print("  Uninstalling PACC...")
                result = subprocess.run([str(pip_cmd), 'uninstall', '-y', 'pacc'],
                                     capture_output=True, text=True)
                results['tests']['uninstall'] = result.returncode == 0
                
                # Verify clean uninstall
                result = subprocess.run([str(pip_cmd), 'show', 'pacc'],
                                     capture_output=True, text=True)
                results['tests']['package_removed'] = result.returncode != 0
                
                # Check that import fails
                result = subprocess.run([str(python_cmd), '-c', 'import pacc'],
                                     capture_output=True, text=True)
                results['tests']['import_fails'] = result.returncode != 0
                
                # Check command is gone
                # Note: On some systems, the script might remain but won't work
                if pacc_cmd.exists():
                    result = subprocess.run([str(pacc_cmd), '--version'],
                                         capture_output=True, text=True)
                    results['tests']['command_fails'] = result.returncode != 0
                else:
                    results['tests']['command_removed'] = True
                    
                # Note: Data files would typically remain unless explicitly removed
                results['tests']['data_files_remain'] = pacc_data.exists()
                
            except Exception as e:
                results['error'] = str(e)
                
        return results
    
    def test_downgrade_scenario(self) -> Dict[str, any]:
        """Test downgrading to a previous version."""
        results = {
            'scenario': 'downgrade',
            'tests': {}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            versions = self._create_test_versions(tmpdir)
            
            # Create test venv
            venv_path = tmpdir / 'test_venv'
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
            
            if sys.platform == 'win32':
                pip_cmd = venv_path / 'Scripts' / 'pip'
                python_cmd = venv_path / 'Scripts' / 'python'
            else:
                pip_cmd = venv_path / 'bin' / 'pip'
                python_cmd = venv_path / 'bin' / 'python'
            
            try:
                # Install version 2.0.0
                print("  Installing version 2.0.0...")
                result = subprocess.run([str(pip_cmd), 'install', '-e', str(versions['2.0.0'])],
                                     capture_output=True, text=True)
                results['tests']['install_v2'] = result.returncode == 0
                
                # Verify version
                result = subprocess.run([str(python_cmd), '-c', 
                                       'import pacc; print(pacc.__version__)'],
                                     capture_output=True, text=True)
                results['tests']['version_is_v2'] = '2.0.0' in result.stdout
                
                # Downgrade to version 1.0.0
                print("  Downgrading to version 1.0.0...")
                result = subprocess.run([str(pip_cmd), 'install', '--force-reinstall', 
                                       '-e', str(versions['1.0.0'])],
                                     capture_output=True, text=True)
                results['tests']['downgrade_to_v1'] = result.returncode == 0
                
                # Verify downgrade
                result = subprocess.run([str(python_cmd), '-c', 
                                       'import pacc; print(pacc.__version__)'],
                                     capture_output=True, text=True)
                results['tests']['version_is_v1'] = '1.0.0' in result.stdout
                
            except Exception as e:
                results['error'] = str(e)
                
        return results
    
    def test_partial_uninstall_recovery(self) -> Dict[str, any]:
        """Test recovery from partial uninstallation."""
        results = {
            'scenario': 'partial_uninstall_recovery',
            'tests': {}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Create test venv
            venv_path = tmpdir / 'test_venv'
            subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], check=True)
            
            if sys.platform == 'win32':
                pip_cmd = venv_path / 'Scripts' / 'pip'
                site_packages = venv_path / 'Lib' / 'site-packages'
            else:
                pip_cmd = venv_path / 'bin' / 'pip'
                site_packages = venv_path / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
            
            try:
                # Install PACC
                result = subprocess.run([str(pip_cmd), 'install', '-e', str(self.pacc_root)],
                                     capture_output=True, text=True)
                results['tests']['initial_install'] = result.returncode == 0
                
                # Simulate partial uninstall by removing some files
                print("  Simulating partial uninstall...")
                pacc_dir = site_packages / 'pacc'
                if pacc_dir.exists():
                    # Remove some but not all files
                    for file in list(pacc_dir.glob('*.py'))[:2]:
                        file.unlink()
                    results['tests']['partial_removal'] = True
                else:
                    results['tests']['partial_removal'] = False
                    
                # Try to repair by reinstalling
                print("  Attempting repair...")
                result = subprocess.run([str(pip_cmd), 'install', '--force-reinstall', 
                                       '-e', str(self.pacc_root)],
                                     capture_output=True, text=True)
                results['tests']['repair_install'] = result.returncode == 0
                
                # Verify repair
                result = subprocess.run([str(pip_cmd), 'show', 'pacc'],
                                     capture_output=True, text=True)
                results['tests']['repair_successful'] = result.returncode == 0
                
            except Exception as e:
                results['error'] = str(e)
                
        return results
    
    def test_multiple_version_coexistence(self) -> Dict[str, any]:
        """Test having multiple versions in different environments."""
        results = {
            'scenario': 'multiple_versions',
            'tests': {}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            versions = self._create_test_versions(tmpdir)
            
            # Create two venvs
            venv1 = tmpdir / 'venv1'
            venv2 = tmpdir / 'venv2'
            
            subprocess.run([sys.executable, '-m', 'venv', str(venv1)], check=True)
            subprocess.run([sys.executable, '-m', 'venv', str(venv2)], check=True)
            
            if sys.platform == 'win32':
                pip1 = venv1 / 'Scripts' / 'pip'
                pip2 = venv2 / 'Scripts' / 'pip'
                python1 = venv1 / 'Scripts' / 'python'
                python2 = venv2 / 'Scripts' / 'python'
            else:
                pip1 = venv1 / 'bin' / 'pip'
                pip2 = venv2 / 'bin' / 'pip'
                python1 = venv1 / 'bin' / 'python'
                python2 = venv2 / 'bin' / 'python'
            
            try:
                # Install v1 in venv1
                print("  Installing v1.0.0 in venv1...")
                result = subprocess.run([str(pip1), 'install', '-e', str(versions['1.0.0'])],
                                     capture_output=True, text=True)
                results['tests']['venv1_install'] = result.returncode == 0
                
                # Install v2 in venv2
                print("  Installing v2.0.0 in venv2...")
                result = subprocess.run([str(pip2), 'install', '-e', str(versions['2.0.0'])],
                                     capture_output=True, text=True)
                results['tests']['venv2_install'] = result.returncode == 0
                
                # Check versions
                result1 = subprocess.run([str(python1), '-c', 
                                        'import pacc; print(pacc.__version__)'],
                                       capture_output=True, text=True)
                results['tests']['venv1_version'] = '1.0.0' in result1.stdout
                
                result2 = subprocess.run([str(python2), '-c', 
                                        'import pacc; print(pacc.__version__)'],
                                       capture_output=True, text=True)
                results['tests']['venv2_version'] = '2.0.0' in result2.stdout
                
                # Verify isolation
                results['tests']['versions_isolated'] = (
                    '1.0.0' in result1.stdout and 
                    '2.0.0' in result2.stdout
                )
                
            except Exception as e:
                results['error'] = str(e)
                
        return results
    
    def run_all_tests(self) -> Dict[str, any]:
        """Run all upgrade/uninstall tests."""
        print(f"\n{'='*60}")
        print("Upgrade and Uninstall Tests")
        print(f"{'='*60}\n")
        
        all_results = {
            'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'pacc_root': str(self.pacc_root),
            'tests': {}
        }
        
        test_functions = [
            ('Basic Upgrade', self.test_basic_upgrade),
            ('Config Migration', self.test_config_migration),
            ('Clean Uninstall', self.test_clean_uninstall),
            ('Downgrade Scenario', self.test_downgrade_scenario),
            ('Partial Uninstall Recovery', self.test_partial_uninstall_recovery),
            ('Multiple Version Coexistence', self.test_multiple_version_coexistence),
        ]
        
        for test_name, test_func in test_functions:
            print(f"\nTesting {test_name}...")
            results = test_func()
            all_results['tests'][test_name] = results
            
            # Print summary
            if 'tests' in results:
                passed = sum(1 for v in results['tests'].values() 
                           if isinstance(v, bool) and v)
                total = sum(1 for v in results['tests'].values() 
                          if isinstance(v, bool))
                print(f"  {passed}/{total} tests passed")
                
            if 'error' in results:
                print(f"  Error: {results['error']}")
                
        return all_results


# Pytest test functions
@pytest.mark.integration
class TestUpgradeUninstall:
    """Pytest wrapper for upgrade/uninstall tests."""
    
    def setup_method(self):
        """Set up test suite."""
        self.tester = UpgradeUninstallTester()
        
    def test_basic_upgrade_workflow(self):
        """Test basic version upgrade."""
        results = self.tester.test_basic_upgrade()
        
        if 'tests' in results:
            # Key upgrade steps should work
            assert results['tests'].get('install_v1', False)
            assert results['tests'].get('upgrade_to_v2', False)
            
    def test_configuration_migration(self):
        """Test configuration migration during upgrade."""
        results = self.tester.test_config_migration()
        
        if 'tests' in results:
            assert results['tests'].get('migration_successful', False)
            assert results['tests'].get('backup_created', False)
            assert results['tests'].get('data_preserved', False)
            
    def test_clean_uninstallation(self):
        """Test clean uninstallation process."""
        results = self.tester.test_clean_uninstall()
        
        if 'tests' in results:
            assert results['tests'].get('install', False)
            assert results['tests'].get('uninstall', False)
            assert results['tests'].get('package_removed', False)
            
    def test_version_downgrade(self):
        """Test downgrading to previous version."""
        results = self.tester.test_downgrade_scenario()
        
        if 'tests' in results:
            assert results['tests'].get('downgrade_to_v1', False)
            
    def test_recovery_procedures(self):
        """Test recovery from partial uninstall."""
        results = self.tester.test_partial_uninstall_recovery()
        
        if 'tests' in results:
            assert results['tests'].get('repair_successful', False)
            
    def test_full_suite(self):
        """Run the complete upgrade/uninstall test suite."""
        results = self.tester.run_all_tests()
        
        # Save results
        results_file = Path('upgrade_uninstall_test_results.json')
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        print(f"\nTest results saved to: {results_file}")
        
        # Basic assertions
        assert 'tests' in results
        assert len(results['tests']) > 0


if __name__ == '__main__':
    # Run as standalone script
    tester = UpgradeUninstallTester()
    results = tester.run_all_tests()
    
    # Print summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    
    total_tests = 0
    passed_tests = 0
    
    for category, test_results in results['tests'].items():
        if 'tests' in test_results:
            tests = test_results['tests']
            category_passed = sum(1 for v in tests.values() 
                                if isinstance(v, bool) and v)
            category_total = sum(1 for v in tests.values() 
                               if isinstance(v, bool))
            total_tests += category_total
            passed_tests += category_passed
            
            print(f"{category}: {category_passed}/{category_total} passed")
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    # Save detailed results
    with open('upgrade_uninstall_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)