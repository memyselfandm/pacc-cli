#!/usr/bin/env python3
"""
Cross-platform testing procedures for PACC distribution.

This module provides comprehensive tests to ensure PACC works correctly
across Windows, macOS, and Linux platforms with different Python versions.
"""

import os
import sys
import platform
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pytest
import json
import time


class CrossPlatformTestSuite:
    """Comprehensive cross-platform testing procedures."""
    
    def __init__(self):
        self.platform_info = {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'python_version': sys.version,
            'python_implementation': platform.python_implementation()
        }
        self.test_results = []
        
    def detect_platform(self) -> str:
        """Detect the current platform."""
        system = platform.system().lower()
        if system == 'darwin':
            return 'macos'
        elif system == 'windows':
            return 'windows'
        elif system == 'linux':
            return 'linux'
        else:
            return 'unknown'
    
    def get_python_versions(self) -> List[str]:
        """Get available Python versions for testing."""
        versions = []
        base_versions = ['3.8', '3.9', '3.10', '3.11', '3.12']
        
        for version in base_versions:
            # Check if python version is available
            try:
                cmd = f'python{version}' if self.detect_platform() != 'windows' else f'py -{version}'
                result = subprocess.run([cmd, '--version'], 
                                     capture_output=True, text=True)
                if result.returncode == 0:
                    versions.append(version)
            except:
                pass
                
        return versions
    
    def test_path_handling(self) -> Dict[str, bool]:
        """Test path handling across platforms."""
        results = {}
        test_paths = {
            'simple': 'test/file.txt',
            'spaces': 'test folder/my file.txt',
            'unicode': 'test/файл_文件.txt',
            'special_chars': 'test/file@#$.txt',
            'deep_nesting': 'a/b/c/d/e/f/g/h/file.txt',
            'relative': '../test/file.txt',
            'absolute': os.path.abspath('test/file.txt'),
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            for name, path in test_paths.items():
                try:
                    # Create test path
                    full_path = Path(tmpdir) / path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text('test content')
                    
                    # Test reading
                    content = full_path.read_text()
                    
                    # Test path operations
                    assert full_path.exists()
                    assert full_path.is_file()
                    
                    results[f'path_{name}'] = True
                except Exception as e:
                    results[f'path_{name}'] = False
                    print(f"Path test '{name}' failed: {e}")
                    
        return results
    
    def test_file_permissions(self) -> Dict[str, bool]:
        """Test file permission handling."""
        results = {}
        
        if self.detect_platform() == 'windows':
            # Windows-specific permission tests
            results['permissions_windows'] = self._test_windows_permissions()
        else:
            # Unix-like permission tests
            results['permissions_unix'] = self._test_unix_permissions()
            
        return results
    
    def _test_windows_permissions(self) -> bool:
        """Test Windows-specific file permissions."""
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(b'test')
                tmp_path = tmp.name
            
            # Test read-only attribute
            subprocess.run(['attrib', '+R', tmp_path], check=True)
            
            # Verify read-only
            with pytest.raises(PermissionError):
                with open(tmp_path, 'w') as f:
                    f.write('should fail')
                    
            # Clean up
            subprocess.run(['attrib', '-R', tmp_path], check=True)
            os.unlink(tmp_path)
            return True
            
        except Exception as e:
            print(f"Windows permission test failed: {e}")
            return False
    
    def _test_unix_permissions(self) -> bool:
        """Test Unix-like file permissions."""
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(b'test')
                tmp_path = tmp.name
                
            # Test read-only
            os.chmod(tmp_path, 0o444)
            
            # Verify read-only
            with pytest.raises(PermissionError):
                with open(tmp_path, 'w') as f:
                    f.write('should fail')
                    
            # Clean up
            os.chmod(tmp_path, 0o644)
            os.unlink(tmp_path)
            return True
            
        except Exception as e:
            print(f"Unix permission test failed: {e}")
            return False
    
    def test_line_endings(self) -> Dict[str, bool]:
        """Test line ending handling across platforms."""
        results = {}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test different line endings
            endings = {
                'unix': b'line1\nline2\nline3',
                'windows': b'line1\r\nline2\r\nline3',
                'mixed': b'line1\nline2\r\nline3\r',
            }
            
            for name, content in endings.items():
                try:
                    file_path = Path(tmpdir) / f'{name}.txt'
                    
                    # Write binary content
                    with open(file_path, 'wb') as f:
                        f.write(content)
                    
                    # Read as text (should handle line endings)
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                    
                    # Should always get 3 lines regardless of endings
                    assert len(lines) == 3
                    results[f'line_ending_{name}'] = True
                    
                except Exception as e:
                    results[f'line_ending_{name}'] = False
                    print(f"Line ending test '{name}' failed: {e}")
                    
        return results
    
    def test_environment_variables(self) -> Dict[str, bool]:
        """Test environment variable handling."""
        results = {}
        
        # Test setting and reading environment variables
        test_vars = {
            'PACC_TEST_VAR': 'test_value',
            'PACC_PATH_VAR': '/test/path:/another/path',
            'PACC_UNICODE_VAR': 'тест_测试',
        }
        
        for var_name, var_value in test_vars.items():
            try:
                # Set variable
                os.environ[var_name] = var_value
                
                # Read it back
                read_value = os.environ.get(var_name)
                assert read_value == var_value
                
                # Test in subprocess
                if self.detect_platform() == 'windows':
                    cmd = f'echo %{var_name}%'
                else:
                    cmd = f'echo ${var_name}'
                    
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                results[f'env_{var_name}'] = True
                
                # Clean up
                del os.environ[var_name]
                
            except Exception as e:
                results[f'env_{var_name}'] = False
                print(f"Environment variable test '{var_name}' failed: {e}")
                
        return results
    
    def test_command_execution(self) -> Dict[str, bool]:
        """Test command execution across platforms."""
        results = {}
        
        # Platform-specific commands
        if self.detect_platform() == 'windows':
            commands = {
                'dir': ['cmd', '/c', 'dir'],
                'echo': ['cmd', '/c', 'echo', 'test'],
                'python': ['python', '--version'],
            }
        else:
            commands = {
                'ls': ['ls', '-la'],
                'echo': ['echo', 'test'],
                'python': ['python3', '--version'],
            }
            
        for name, cmd in commands.items():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                results[f'cmd_{name}'] = result.returncode == 0
            except Exception as e:
                results[f'cmd_{name}'] = False
                print(f"Command test '{name}' failed: {e}")
                
        return results
    
    def test_python_version_compatibility(self) -> Dict[str, bool]:
        """Test PACC with different Python versions."""
        results = {}
        available_versions = self.get_python_versions()
        
        for version in available_versions:
            try:
                # Create a test script that imports PACC
                test_script = '''
import sys
try:
    import pacc
    print(f"PACC imported successfully on Python {sys.version}")
    sys.exit(0)
except Exception as e:
    print(f"Failed to import PACC: {e}")
    sys.exit(1)
'''
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(test_script)
                    script_path = f.name
                
                # Run with specific Python version
                if self.detect_platform() == 'windows':
                    python_cmd = f'py -{version}'
                else:
                    python_cmd = f'python{version}'
                    
                result = subprocess.run([python_cmd, script_path], 
                                     capture_output=True, text=True)
                
                results[f'python_{version}'] = result.returncode == 0
                
                # Clean up
                os.unlink(script_path)
                
            except Exception as e:
                results[f'python_{version}'] = False
                print(f"Python {version} test failed: {e}")
                
        return results
    
    def run_all_tests(self) -> Dict[str, any]:
        """Run all cross-platform tests."""
        print(f"\n{'='*60}")
        print(f"Cross-Platform Test Suite - {self.platform_info['system']}")
        print(f"{'='*60}\n")
        
        all_results = {
            'platform_info': self.platform_info,
            'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'tests': {}
        }
        
        # Run each test category
        test_functions = [
            ('Path Handling', self.test_path_handling),
            ('File Permissions', self.test_file_permissions),
            ('Line Endings', self.test_line_endings),
            ('Environment Variables', self.test_environment_variables),
            ('Command Execution', self.test_command_execution),
            ('Python Compatibility', self.test_python_version_compatibility),
        ]
        
        for test_name, test_func in test_functions:
            print(f"\nRunning {test_name} tests...")
            try:
                results = test_func()
                all_results['tests'][test_name] = results
                
                # Print summary
                passed = sum(1 for v in results.values() if v)
                total = len(results)
                print(f"  {passed}/{total} tests passed")
                
            except Exception as e:
                print(f"  ERROR: {e}")
                all_results['tests'][test_name] = {'error': str(e)}
                
        return all_results


# Pytest test functions
@pytest.mark.cross_platform
class TestCrossPlatform:
    """Pytest wrapper for cross-platform tests."""
    
    def setup_method(self):
        """Set up test suite."""
        self.suite = CrossPlatformTestSuite()
    
    def test_platform_detection(self):
        """Test platform detection."""
        platform_name = self.suite.detect_platform()
        assert platform_name in ['windows', 'macos', 'linux', 'unknown']
        
    def test_python_version_detection(self):
        """Test Python version detection."""
        versions = self.suite.get_python_versions()
        assert len(versions) > 0, "No Python versions detected"
        assert sys.version.split()[0][:3] in versions
        
    @pytest.mark.parametrize("test_category", [
        'path_handling',
        'file_permissions', 
        'line_endings',
        'environment_variables',
        'command_execution'
    ])
    def test_category(self, test_category):
        """Test individual test categories."""
        test_method = getattr(self.suite, f'test_{test_category}')
        results = test_method()
        
        # At least some tests should pass
        passed = sum(1 for v in results.values() if v)
        assert passed > 0, f"No {test_category} tests passed"
        
    def test_full_suite(self):
        """Run the complete test suite."""
        results = self.suite.run_all_tests()
        
        # Save results
        results_file = Path('cross_platform_test_results.json')
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
            
        print(f"\nTest results saved to: {results_file}")
        
        # Basic assertions
        assert 'platform_info' in results
        assert 'tests' in results
        assert len(results['tests']) > 0


if __name__ == '__main__':
    # Run as standalone script
    suite = CrossPlatformTestSuite()
    results = suite.run_all_tests()
    
    # Print summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    
    total_tests = 0
    passed_tests = 0
    
    for category, tests in results['tests'].items():
        if isinstance(tests, dict) and 'error' not in tests:
            category_passed = sum(1 for v in tests.values() if v)
            category_total = len(tests)
            total_tests += category_total
            passed_tests += category_passed
            
            print(f"{category}: {category_passed}/{category_total} passed")
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    # Save detailed results
    with open('cross_platform_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)