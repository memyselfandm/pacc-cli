#!/usr/bin/env python3
"""Test script for PACC slash commands integration."""

import json
import os
import subprocess
import sys
from pathlib import Path


def run_pacc_command(args, cwd=None):
    """Run a PACC CLI command and return the result."""
    try:
        # Use PYTHONPATH to ensure proper module resolution
        cmd = ["python", "-m", "pacc"] + args
        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        result = subprocess.run(
            cmd,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def test_json_output():
    """Test JSON output functionality."""
    print("🧪 Testing JSON output functionality...")

    # Test list command with JSON output (uses --format json)
    returncode, stdout, stderr = run_pacc_command(["list", "--format", "json"])

    if returncode != 0:
        print(f"  ❌ List command failed: {stderr}")
        return False

    try:
        result = json.loads(stdout)
        if not isinstance(result, dict):
            print(f"  ❌ JSON output is not a dictionary: {type(result)}")
            return False

        required_fields = ["success", "message"]
        for field in required_fields:
            if field not in result:
                print(f"  ❌ Missing required field in JSON output: {field}")
                return False

        print("  ✅ JSON output format valid")
        print(f"  📊 Result: {result.get('message', 'No message')}")
        return True

    except json.JSONDecodeError as e:
        print(f"  ❌ Invalid JSON output: {e}")
        print(f"  📄 Raw output: {stdout[:200]}...")
        return False


def test_command_help():
    """Test that commands provide proper help."""
    print("🧪 Testing command help functionality...")

    commands = ["install", "list", "remove", "info"]
    success_count = 0

    for cmd in commands:
        returncode, stdout, stderr = run_pacc_command([cmd, "--help"])

        if returncode != 0:
            print(f"  ❌ Help for {cmd} failed: {stderr}")
            continue

        # Check for JSON support (either --json flag or --format json)
        has_json_support = "--json" in stdout or "--format {table,list,json}" in stdout

        if has_json_support:
            print(f"  ✅ {cmd} command supports JSON output")
            success_count += 1
        else:
            print(f"  ⚠️  {cmd} command help doesn't mention JSON support")

    print(f"  📊 {success_count}/{len(commands)} commands have JSON support in help")
    return success_count == len(commands)


def test_slash_command_files():
    """Test that slash command files exist and have proper structure."""
    print("🧪 Testing slash command files...")

    commands_dir = Path(".claude/commands/pacc")
    expected_commands = ["install.md", "list.md", "info.md", "remove.md", "search.md", "update.md"]

    if not commands_dir.exists():
        print(f"  ❌ Commands directory doesn't exist: {commands_dir}")
        return False

    success_count = 0

    for cmd_file in expected_commands:
        cmd_path = commands_dir / cmd_file

        if not cmd_path.exists():
            print(f"  ❌ Command file missing: {cmd_file}")
            continue

        # Check file structure
        try:
            content = cmd_path.read_text()

            # Check for frontmatter
            if not content.startswith("---"):
                print(f"  ❌ {cmd_file}: Missing frontmatter")
                continue

            # Check for required frontmatter fields
            required_fields = ["allowed-tools", "argument-hint", "description"]
            missing_fields = []

            for field in required_fields:
                if f"{field}:" not in content:
                    missing_fields.append(field)

            if missing_fields:
                print(f"  ⚠️  {cmd_file}: Missing frontmatter fields: {missing_fields}")

            # Check for PACC command usage
            if "uv run pacc" not in content:
                print(f"  ❌ {cmd_file}: Doesn't use PACC CLI commands")
                continue

            print(f"  ✅ {cmd_file}: Valid structure")
            success_count += 1

        except Exception as e:
            print(f"  ❌ {cmd_file}: Error reading file: {e}")
            continue

    print(f"  📊 {success_count}/{len(expected_commands)} command files are valid")
    return success_count == len(expected_commands)


def test_integration():
    """Test end-to-end integration."""
    print("🧪 Testing end-to-end integration...")

    # Test that we can run the main PACC help
    returncode, stdout, stderr = run_pacc_command(["--help"])

    if returncode != 0:
        print(f"  ❌ PACC help failed: {stderr}")
        return False

    if "install" in stdout and "list" in stdout:
        print("  ✅ PACC CLI is functional")
    else:
        print("  ❌ PACC CLI help doesn't show expected commands")
        return False

    # Test JSON mode doesn't break regular commands
    returncode, stdout, stderr = run_pacc_command(["list", "--format", "json"])

    if returncode == 0:
        print("  ✅ JSON mode works without errors")
    else:
        print(f"  ⚠️  JSON mode had issues: {stderr}")

    return True


def main():
    """Run all tests."""
    print("🚀 Testing PACC Slash Commands Integration\n")

    # Change to the CLI directory
    cli_dir = Path(__file__).parent
    os.chdir(cli_dir)
    print(f"📁 Working directory: {cli_dir}\n")

    tests = [
        ("JSON Output Functionality", test_json_output),
        ("Command Help System", test_command_help),
        ("Slash Command Files", test_slash_command_files),
        ("End-to-End Integration", test_integration),
    ]

    passed_tests = 0
    total_tests = len(tests)

    for test_name, test_func in tests:
        print(f"{'='*50}")
        print(f"📋 {test_name}")
        print(f"{'='*50}")

        try:
            if test_func():
                print(f"✅ {test_name} - PASSED\n")
                passed_tests += 1
            else:
                print(f"❌ {test_name} - FAILED\n")
        except Exception as e:
            print(f"💥 {test_name} - ERROR: {e}\n")

    print(f"{'='*50}")
    print(f"📊 Test Results: {passed_tests}/{total_tests} tests passed")
    print(f"{'='*50}")

    if passed_tests == total_tests:
        print("🎉 All tests passed! PACC slash commands are ready!")
        return 0
    else:
        print(f"⚠️  {total_tests - passed_tests} test(s) failed. Please review the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
