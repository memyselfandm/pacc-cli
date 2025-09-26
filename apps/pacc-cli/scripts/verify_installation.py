#!/usr/bin/env python3
"""Verify PACC installation and functionality."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_command(args):
    """Run a command and return result."""
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    return result


def verify_version():
    """Verify PACC version command works."""
    print("Checking PACC version...")
    result = run_command([sys.executable, "-m", "pacc", "--version"])

    if result.returncode == 0:
        print(f"✓ Version check passed: {result.stdout.strip()}")
        return True
    else:
        print(f"✗ Version check failed: {result.stderr}")
        return False


def verify_help():
    """Verify PACC help command works."""
    print("\nChecking PACC help...")
    result = run_command([sys.executable, "-m", "pacc", "--help"])

    if result.returncode == 0 and "PACC - Package manager for Claude Code" in result.stdout:
        print("✓ Help command works correctly")
        return True
    else:
        print("✗ Help command failed")
        return False


def verify_commands():
    """Verify all major commands are available."""
    print("\nChecking available commands...")
    commands = ["install", "validate", "list", "remove", "info", "init", "sync"]
    all_good = True

    for cmd in commands:
        result = run_command([sys.executable, "-m", "pacc", cmd, "--help"])
        if result.returncode == 0:
            print(f"✓ Command '{cmd}' is available")
        else:
            print(f"✗ Command '{cmd}' is not working properly")
            all_good = False

    return all_good


def verify_validation():
    """Verify validation functionality."""
    print("\nChecking validation functionality...")

    # Create a temporary valid hook file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        hook_data = {
            "name": "test-hook",
            "description": "Test hook",
            "version": "1.0.0",
            "events": [
                {
                    "type": "PreToolUse",
                    "matcher": {"tool": "Bash"},
                    "action": {"type": "Ask", "config": {"message": "Test message"}},
                }
            ],
        }
        json.dump(hook_data, f)
        temp_file = f.name

    try:
        result = run_command([sys.executable, "-m", "pacc", "validate", temp_file])

        if result.returncode == 0:
            print("✓ Validation works correctly")
            return True
        else:
            print("✗ Validation failed")
            if result.stderr:
                print(f"  Error: {result.stderr}")
            if result.stdout:
                print(f"  Output: {result.stdout}")
            return False
    finally:
        Path(temp_file).unlink(missing_ok=True)


def verify_json_output():
    """Verify JSON output mode."""
    print("\nChecking JSON output mode...")
    result = run_command([sys.executable, "-m", "pacc", "list", "--format", "json"])

    if result.returncode != 0:
        print("✗ List command failed")
        if result.stderr:
            print(f"  Error: {result.stderr}")
        return False

    try:
        data = json.loads(result.stdout)
        if "success" in data and isinstance(data["success"], bool):
            print("✓ JSON output mode works correctly")
            return True
        else:
            print("✗ JSON output is malformed")
            return False
    except json.JSONDecodeError:
        print(f"✗ Invalid JSON output: {result.stdout}")
        return False


def verify_entry_point():
    """Verify console script entry point."""
    print("\nChecking console script entry point...")

    # Try to run 'pacc' command directly
    try:
        result = run_command(["pacc", "--version"])

        if result.returncode == 0:
            print("✓ Console script 'pacc' is available in PATH")
            return True
        else:
            print("i Console script 'pacc' not found (this is OK if not installed via pip)")
            # This is not a failure - just informational
            return True
    except (FileNotFoundError, OSError):
        print("i Console script 'pacc' not found in PATH (expected if not installed)")
        # This is not a failure for development environments
        return True


def main():
    """Run all verification checks."""
    print("PACC Installation Verification")
    print("=" * 50)

    checks = [
        verify_version,
        verify_help,
        verify_commands,
        verify_validation,
        verify_json_output,
        verify_entry_point,
    ]

    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as e:
            print(f"✗ Check failed with error: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✓ All {total} checks passed! PACC is working correctly.")
        return 0
    else:
        print(f"✗ {passed}/{total} checks passed. Some functionality may not be working.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
