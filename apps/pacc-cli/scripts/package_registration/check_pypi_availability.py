#!/usr/bin/env python3
"""
Check if a package name is available on PyPI and Test PyPI.

This script helps verify that your chosen package name is available
before attempting to publish.
"""

import sys
import json
import urllib.request
import urllib.error
from typing import Dict, Optional


def check_pypi_name(package_name: str, test_pypi: bool = False) -> Dict[str, any]:
    """
    Check if a package name is available on PyPI.
    
    Args:
        package_name: The package name to check
        test_pypi: Check Test PyPI instead of production PyPI
        
    Returns:
        Dictionary with availability information
    """
    base_url = "https://test.pypi.org" if test_pypi else "https://pypi.org"
    api_url = f"{base_url}/pypi/{package_name}/json"
    
    try:
        with urllib.request.urlopen(api_url) as response:
            data = json.loads(response.read())
            return {
                "available": False,
                "exists": True,
                "current_version": data["info"]["version"],
                "author": data["info"]["author"],
                "summary": data["info"]["summary"],
                "url": f"{base_url}/project/{package_name}/"
            }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {
                "available": True,
                "exists": False,
                "message": f"'{package_name}' is available on {'Test ' if test_pypi else ''}PyPI!"
            }
        else:
            return {
                "available": None,
                "error": f"HTTP Error {e.code}: {e.reason}"
            }
    except Exception as e:
        return {
            "available": None,
            "error": f"Error checking package: {str(e)}"
        }


def check_similar_names(package_name: str) -> list:
    """
    Check for similar package names that might cause confusion.
    
    This is a simple check - for production use, consider using
    the PyPI search API or warehouse API.
    """
    similar = []
    
    # Common variations to check
    variations = [
        package_name.replace("-", "_"),
        package_name.replace("_", "-"),
        package_name.lower(),
        package_name.upper(),
        package_name.capitalize(),
    ]
    
    # Remove duplicates
    variations = list(set(variations)) 
    variations.remove(package_name)  # Don't check the original
    
    for variant in variations:
        if variant != package_name:
            result = check_pypi_name(variant)
            if result.get("exists"):
                similar.append({
                    "name": variant,
                    "version": result.get("current_version"),
                    "url": result.get("url")
                })
    
    return similar


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python check_pypi_availability.py <package-name>")
        print("\nExample:")
        print("  python check_pypi_availability.py my-awesome-package")
        sys.exit(1)
    
    package_name = sys.argv[1]
    
    print(f"🔍 Checking availability of '{package_name}'...\n")
    
    # Check production PyPI
    print("📦 Production PyPI:")
    pypi_result = check_pypi_name(package_name)
    
    if pypi_result.get("available") is True:
        print(f"  ✅ {pypi_result['message']}")
    elif pypi_result.get("available") is False:
        print(f"  ❌ Package already exists!")
        print(f"     Version: {pypi_result['current_version']}")
        print(f"     Author: {pypi_result['author']}")
        print(f"     URL: {pypi_result['url']}")
    else:
        print(f"  ⚠️  {pypi_result.get('error', 'Unknown error')}")
    
    # Check Test PyPI
    print("\n🧪 Test PyPI:")
    test_result = check_pypi_name(package_name, test_pypi=True)
    
    if test_result.get("available") is True:
        print(f"  ✅ {test_result['message']}")
    elif test_result.get("available") is False:
        print(f"  ❌ Package already exists on Test PyPI!")
        print(f"     Version: {test_result['current_version']}")
        print(f"     URL: {test_result['url']}")
    else:
        print(f"  ⚠️  {test_result.get('error', 'Unknown error')}")
    
    # Check for similar names
    print("\n🔍 Checking for similar package names...")
    similar = check_similar_names(package_name)
    
    if similar:
        print("  ⚠️  Found similar packages that might cause confusion:")
        for pkg in similar:
            print(f"     - {pkg['name']} (v{pkg['version']})")
            print(f"       {pkg['url']}")
    else:
        print("  ✅ No confusingly similar package names found")
    
    # Summary
    print("\n📊 Summary:")
    if pypi_result.get("available") and test_result.get("available"):
        print(f"  ✅ '{package_name}' is available on both PyPI and Test PyPI!")
        print("  🎉 You can proceed with this package name.")
    elif not pypi_result.get("available"):
        print(f"  ❌ '{package_name}' is already taken on PyPI.")
        print("  💡 Consider choosing a different name or namespace.")
    else:
        print(f"  ⚠️  Unable to fully verify availability.")
        print("  💡 Check manually before proceeding.")
    
    # Exit code
    if pypi_result.get("available") is True:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()