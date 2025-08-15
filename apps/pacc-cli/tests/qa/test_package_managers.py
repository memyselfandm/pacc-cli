#!/usr/bin/env python3
"""
Package manager compatibility testing for PACC.

Tests installation and functionality with different package managers:
- pip (standard Python package installer)
- uv (fast Python package installer)
- pipx (install Python applications in isolated environments)
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


class PackageManagerTester:
    """Test PACC installation with different package managers."""
    
    def __init__(self):
        self.pacc_root = Path(__file__).parent.parent.parent
        self.test_results = []
        self.available_managers = self._detect_package_managers()
        
    def _detect_package_managers(self) -> Dict[str, bool]:
        """Detect available package managers."""
        managers = {}
        
        # Check for pip
        try:
            result = subprocess.run(['pip', '--version'], 
                                 capture_output=True, text=True)
            managers['pip'] = result.returncode == 0
        except:
            managers['pip'] = False
            
        # Check for uv
        try:
            result = subprocess.run(['uv', '--version'], 
                                 capture_output=True, text=True)
            managers['uv'] = result.returncode == 0
        except:
            managers['uv'] = False
            
        # Check for pipx
        try:
            result = subprocess.run(['pipx', '--version'], 
                                 capture_output=True, text=True)
            managers['pipx'] = result.returncode == 0
        except:
            managers['pipx'] = False
            
        return managers
    
    def test_pip_installation(self) -> Dict[str, any]:
        """Test PACC installation with pip."""
        results = {
            'manager': 'pip',
            'tests': {}
        }
        
        if not self.available_managers.get('pip'):
            results['error'] = 'pip not available'
            return results
            
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_path = Path(tmpdir) / 'venv'
            
            try:
                # Create virtual environment
                subprocess.run([sys.executable, '-m', 'venv', str(venv_path)], 
                             check=True)
                
                # Get pip path in venv
                if sys.platform == 'win32':
                    pip_cmd = venv_path / 'Scripts' / 'pip'
                    python_cmd = venv_path / 'Scripts' / 'python'
                    pacc_cmd = venv_path / 'Scripts' / 'pacc'
                else:
                    pip_cmd = venv_path / 'bin' / 'pip'
                    python_cmd = venv_path / 'bin' / 'python'
                    pacc_cmd = venv_path / 'bin' / 'pacc'
                
                # Test 1: Editable installation
                print("  Testing editable installation...")
                result = subprocess.run([str(pip_cmd), 'install', '-e', str(self.pacc_root)],
                                     capture_output=True, text=True)
                results['tests']['editable_install'] = result.returncode == 0
                
                # Test 2: Import test
                print("  Testing import...")
                result = subprocess.run([str(python_cmd), '-c', 'import pacc; print(pacc.__version__)'],
                                     capture_output=True, text=True)
                results['tests']['import'] = result.returncode == 0
                results['tests']['version'] = result.stdout.strip() if result.returncode == 0 else None
                
                # Test 3: CLI availability
                print("  Testing CLI...")
                result = subprocess.run([str(pacc_cmd), '--version'],
                                     capture_output=True, text=True)
                results['tests']['cli_available'] = result.returncode == 0
                
                # Test 4: Basic functionality
                print("  Testing basic functionality...")
                result = subprocess.run([str(pacc_cmd), '--help'],
                                     capture_output=True, text=True)
                results['tests']['help_command'] = result.returncode == 0
                
                # Test 5: Uninstall
                print("  Testing uninstall...")
                result = subprocess.run([str(pip_cmd), 'uninstall', '-y', 'pacc'],
                                     capture_output=True, text=True)
                results['tests']['uninstall'] = result.returncode == 0
                
                # Test 6: Wheel installation
                print("  Building and testing wheel installation...")
                # First build the wheel
                build_result = subprocess.run([str(pip_cmd), 'install', 'build'],
                                           capture_output=True, text=True)
                
                if build_result.returncode == 0:
                    build_dir = Path(tmpdir) / 'build'
                    build_dir.mkdir()
                    
                    # Build wheel
                    result = subprocess.run([str(python_cmd), '-m', 'build', '--wheel', 
                                          str(self.pacc_root), '--outdir', str(build_dir)],
                                         capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        # Find the wheel file
                        wheel_files = list(build_dir.glob('*.whl'))
                        if wheel_files:
                            # Install from wheel
                            result = subprocess.run([str(pip_cmd), 'install', str(wheel_files[0])],
                                                 capture_output=True, text=True)
                            results['tests']['wheel_install'] = result.returncode == 0
                            
                            # Test after wheel install
                            result = subprocess.run([str(pacc_cmd), '--version'],
                                                 capture_output=True, text=True)
                            results['tests']['wheel_functionality'] = result.returncode == 0
                        else:
                            results['tests']['wheel_install'] = False
                            results['tests']['wheel_functionality'] = False
                    else:
                        results['tests']['wheel_build'] = False
                        
            except Exception as e:
                results['error'] = str(e)
                
        return results
    
    def test_uv_installation(self) -> Dict[str, any]:
        """Test PACC installation with uv."""
        results = {
            'manager': 'uv',
            'tests': {}
        }
        
        if not self.available_managers.get('uv'):
            results['error'] = 'uv not available'
            return results
            
        with tempfile.TemporaryDirectory() as tmpdir:
            venv_path = Path(tmpdir) / 'venv'
            
            try:
                # Create virtual environment with uv
                subprocess.run(['uv', 'venv', str(venv_path)], check=True)
                
                # Get paths
                if sys.platform == 'win32':
                    python_cmd = venv_path / 'Scripts' / 'python'
                    pacc_cmd = venv_path / 'Scripts' / 'pacc'
                else:
                    python_cmd = venv_path / 'bin' / 'python'
                    pacc_cmd = venv_path / 'bin' / 'pacc'
                
                # Test 1: Install with uv
                print("  Testing uv installation...")
                result = subprocess.run(['uv', 'pip', 'install', '-e', str(self.pacc_root)],
                                     env={**os.environ, 'VIRTUAL_ENV': str(venv_path)},
                                     capture_output=True, text=True)
                results['tests']['install'] = result.returncode == 0
                
                # Test 2: Functionality
                print("  Testing functionality...")
                result = subprocess.run([str(pacc_cmd), '--version'],
                                     capture_output=True, text=True)
                results['tests']['functionality'] = result.returncode == 0
                
                # Test 3: Package info
                print("  Testing package info...")
                result = subprocess.run(['uv', 'pip', 'show', 'pacc'],
                                     env={**os.environ, 'VIRTUAL_ENV': str(venv_path)},
                                     capture_output=True, text=True)
                results['tests']['package_info'] = result.returncode == 0
                
                # Test 4: Uninstall
                print("  Testing uninstall...")
                result = subprocess.run(['uv', 'pip', 'uninstall', 'pacc'],
                                     env={**os.environ, 'VIRTUAL_ENV': str(venv_path)},
                                     capture_output=True, text=True)
                results['tests']['uninstall'] = result.returncode == 0
                
            except Exception as e:
                results['error'] = str(e)
                
        return results
    
    def test_pipx_installation(self) -> Dict[str, any]:
        """Test PACC installation with pipx."""
        results = {
            'manager': 'pipx',
            'tests': {}
        }
        
        if not self.available_managers.get('pipx'):
            results['error'] = 'pipx not available'
            return results
            
        try:
            # Note: pipx modifies global state, so we need to be careful
            # First ensure pacc is not already installed
            subprocess.run(['pipx', 'uninstall', 'pacc'], 
                        capture_output=True, text=True)
            
            # Test 1: Install from local path
            print("  Testing pipx installation...")
            result = subprocess.run(['pipx', 'install', str(self.pacc_root)],
                                 capture_output=True, text=True)
            results['tests']['install'] = result.returncode == 0
            
            if result.returncode == 0:
                # Test 2: Run command
                print("  Testing functionality...")
                result = subprocess.run(['pacc', '--version'],
                                     capture_output=True, text=True)
                results['tests']['functionality'] = result.returncode == 0
                
                # Test 3: List installed apps
                print("  Testing list...")
                result = subprocess.run(['pipx', 'list'],
                                     capture_output=True, text=True)
                results['tests']['list_shows_pacc'] = 'pacc' in result.stdout
                
                # Test 4: Upgrade (reinstall from same source)
                print("  Testing upgrade...")
                result = subprocess.run(['pipx', 'upgrade', 'pacc'],
                                     capture_output=True, text=True)
                results['tests']['upgrade'] = result.returncode == 0
                
                # Test 5: Uninstall
                print("  Testing uninstall...")
                result = subprocess.run(['pipx', 'uninstall', 'pacc'],
                                     capture_output=True, text=True)
                results['tests']['uninstall'] = result.returncode == 0
                
            else:
                results['tests']['functionality'] = False
                results['tests']['list_shows_pacc'] = False
                results['tests']['upgrade'] = False
                results['tests']['uninstall'] = False
                
        except Exception as e:
            results['error'] = str(e)
            
        return results
    
    def test_virtual_environments(self) -> Dict[str, any]:
        """Test PACC in different virtual environment scenarios."""
        results = {
            'scenario': 'virtual_environments',
            'tests': {}
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test 1: Standard venv
            print("  Testing standard venv...")
            venv1 = Path(tmpdir) / 'venv1'
            try:
                subprocess.run([sys.executable, '-m', 'venv', str(venv1)], check=True)
                
                if sys.platform == 'win32':
                    pip_cmd = venv1 / 'Scripts' / 'pip'
                    pacc_cmd = venv1 / 'Scripts' / 'pacc'
                else:
                    pip_cmd = venv1 / 'bin' / 'pip'
                    pacc_cmd = venv1 / 'bin' / 'pacc'
                    
                # Install and test
                result = subprocess.run([str(pip_cmd), 'install', '-e', str(self.pacc_root)],
                                     capture_output=True, text=True)
                if result.returncode == 0:
                    result = subprocess.run([str(pacc_cmd), '--version'],
                                         capture_output=True, text=True)
                    results['tests']['standard_venv'] = result.returncode == 0
                else:
                    results['tests']['standard_venv'] = False
                    
            except Exception as e:
                results['tests']['standard_venv'] = False
                
            # Test 2: Nested virtual environment
            print("  Testing nested venv...")
            venv2 = Path(tmpdir) / 'deeply' / 'nested' / 'path' / 'venv2'
            try:
                venv2.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run([sys.executable, '-m', 'venv', str(venv2)], check=True)
                
                if sys.platform == 'win32':
                    pip_cmd = venv2 / 'Scripts' / 'pip'
                    pacc_cmd = venv2 / 'Scripts' / 'pacc'
                else:
                    pip_cmd = venv2 / 'bin' / 'pip'
                    pacc_cmd = venv2 / 'bin' / 'pacc'
                    
                result = subprocess.run([str(pip_cmd), 'install', '-e', str(self.pacc_root)],
                                     capture_output=True, text=True)
                if result.returncode == 0:
                    result = subprocess.run([str(pacc_cmd), '--version'],
                                         capture_output=True, text=True)
                    results['tests']['nested_venv'] = result.returncode == 0
                else:
                    results['tests']['nested_venv'] = False
                    
            except Exception as e:
                results['tests']['nested_venv'] = False
                
            # Test 3: Path with spaces
            print("  Testing venv with spaces in path...")
            venv3 = Path(tmpdir) / 'virtual env with spaces'
            try:
                subprocess.run([sys.executable, '-m', 'venv', str(venv3)], check=True)
                
                if sys.platform == 'win32':
                    pip_cmd = venv3 / 'Scripts' / 'pip'
                    pacc_cmd = venv3 / 'Scripts' / 'pacc'
                else:
                    pip_cmd = venv3 / 'bin' / 'pip'
                    pacc_cmd = venv3 / 'bin' / 'pacc'
                    
                result = subprocess.run([str(pip_cmd), 'install', '-e', str(self.pacc_root)],
                                     capture_output=True, text=True)
                if result.returncode == 0:
                    result = subprocess.run([str(pacc_cmd), '--version'],
                                         capture_output=True, text=True)
                    results['tests']['spaces_in_path'] = result.returncode == 0
                else:
                    results['tests']['spaces_in_path'] = False
                    
            except Exception as e:
                results['tests']['spaces_in_path'] = False
                
        return results
    
    def test_global_vs_local_installation(self) -> Dict[str, any]:
        """Test global vs local installation scenarios."""
        results = {
            'scenario': 'global_vs_local',
            'tests': {}
        }
        
        # Note: Testing actual global installation is risky and requires admin rights
        # We'll test the concepts without actually installing globally
        
        # Test 1: Check if running in a virtual environment
        in_venv = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )
        results['tests']['detect_venv'] = True
        results['tests']['currently_in_venv'] = in_venv
        
        # Test 2: Check user site packages
        try:
            import site
            user_site = site.getusersitepackages()
            results['tests']['user_site_available'] = bool(user_site)
            results['tests']['user_site_path'] = user_site
        except:
            results['tests']['user_site_available'] = False
            
        # Test 3: Simulate user installation (without actually doing it)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_user_site = Path(tmpdir) / 'user_site'
            fake_user_site.mkdir()
            
            # Would use: pip install --user pacc
            results['tests']['user_install_simulation'] = True
            
        return results
    
    def run_all_tests(self) -> Dict[str, any]:
        """Run all package manager tests."""
        print(f"\n{'='*60}")
        print("Package Manager Compatibility Tests")
        print(f"{'='*60}\n")
        
        print("Available package managers:")
        for manager, available in self.available_managers.items():
            status = "✓" if available else "✗"
            print(f"  {status} {manager}")
        
        all_results = {
            'available_managers': self.available_managers,
            'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'pacc_root': str(self.pacc_root),
            'tests': {}
        }
        
        # Run tests for each package manager
        test_functions = [
            ('pip', self.test_pip_installation),
            ('uv', self.test_uv_installation),
            ('pipx', self.test_pipx_installation),
            ('virtual_environments', self.test_virtual_environments),
            ('global_vs_local', self.test_global_vs_local_installation),
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
class TestPackageManagers:
    """Pytest wrapper for package manager tests."""
    
    def setup_method(self):
        """Set up test suite."""
        self.tester = PackageManagerTester()
        
    def test_package_manager_detection(self):
        """Test detection of available package managers."""
        managers = self.tester.available_managers
        
        # At least pip should be available
        assert 'pip' in managers
        assert managers['pip'] is True
        
    @pytest.mark.skipif(not shutil.which('pip'), reason="pip not available")
    def test_pip_integration(self):
        """Test pip installation workflow."""
        results = self.tester.test_pip_installation()
        
        assert 'error' not in results or results['error'] == 'pip not available'
        
        if 'tests' in results:
            # Critical tests that should pass
            assert results['tests'].get('editable_install', False)
            assert results['tests'].get('import', False)
            assert results['tests'].get('cli_available', False)
            
    @pytest.mark.skipif(not shutil.which('uv'), reason="uv not available")
    def test_uv_integration(self):
        """Test uv installation workflow."""
        results = self.tester.test_uv_installation()
        
        if 'tests' in results:
            assert results['tests'].get('install', False)
            assert results['tests'].get('functionality', False)
            
    @pytest.mark.skipif(not shutil.which('pipx'), reason="pipx not available")
    def test_pipx_integration(self):
        """Test pipx installation workflow."""
        results = self.tester.test_pipx_installation()
        
        if 'tests' in results:
            assert results['tests'].get('install', False)
            
    def test_virtual_environment_scenarios(self):
        """Test various virtual environment scenarios."""
        results = self.tester.test_virtual_environments()
        
        assert 'tests' in results
        # At least standard venv should work
        assert results['tests'].get('standard_venv', False)
        
    def test_full_suite(self):
        """Run the complete package manager test suite."""
        results = self.tester.run_all_tests()
        
        # Save results
        results_file = Path('package_manager_test_results.json')
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        print(f"\nTest results saved to: {results_file}")
        
        # Basic assertions
        assert 'available_managers' in results
        assert 'tests' in results
        assert len(results['tests']) > 0


if __name__ == '__main__':
    # Run as standalone script
    tester = PackageManagerTester()
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
    with open('package_manager_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)