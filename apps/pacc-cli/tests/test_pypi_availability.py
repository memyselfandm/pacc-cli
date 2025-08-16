#!/usr/bin/env python3
"""
Test PyPI package name availability checker.
"""

import sys
import pytest
from pathlib import Path


class TestPyPIAvailability:
    """Test suite for PyPI availability checking."""
    
    def test_availability_script_exists(self):
        """Test that the availability checker script exists."""
        script_path = Path(__file__).parent.parent / "scripts" / "package_registration" / "check_pypi_availability.py"
        assert script_path.exists(), "PyPI availability checker script must exist"
    
    def test_script_imports(self):
        """Test that the script can be imported."""
        scripts_dir = Path(__file__).parent.parent / "scripts" / "package_registration"
        sys.path.insert(0, str(scripts_dir))
        
        try:
            import check_pypi_availability
            
            # Check required functions exist
            assert hasattr(check_pypi_availability, 'check_pypi_name')
            assert hasattr(check_pypi_availability, 'check_similar_names')
            assert hasattr(check_pypi_availability, 'main')
        finally:
            sys.path.pop(0)
    
    def test_known_package_check(self):
        """Test checking a known package (should exist)."""
        scripts_dir = Path(__file__).parent.parent / "scripts" / "package_registration"
        sys.path.insert(0, str(scripts_dir))
        
        try:
            import check_pypi_availability
            
            # Check a well-known package
            result = check_pypi_availability.check_pypi_name("requests")
            
            assert result.get("available") is False
            assert result.get("exists") is True
            assert "current_version" in result
            assert "url" in result
        finally:
            sys.path.pop(0)
    
    def test_unique_package_check(self):
        """Test checking a unique package name (should not exist)."""
        scripts_dir = Path(__file__).parent.parent / "scripts" / "package_registration"
        sys.path.insert(0, str(scripts_dir))
        
        try:
            import check_pypi_availability
            
            # Check a very unique package name
            result = check_pypi_availability.check_pypi_name("this-is-a-very-unique-package-name-123456789")
            
            assert result.get("available") is True
            assert result.get("exists") is False
        finally:
            sys.path.pop(0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])