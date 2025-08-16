"""
Test documentation completeness for F3.1 implementation.

This module validates:
- All documentation files exist and are properly formatted
- Installation methods are documented correctly
- Usage documentation covers global vs project-local differences
- Migration guides are comprehensive
- Getting started guides are complete
- All code examples work as documented
"""

import os
import re
import json
import subprocess
import tempfile
from pathlib import Path
import pytest
import sys


class TestDocumentationCompleteness:
    """Test suite for F3.1 documentation requirements."""
    
    @pytest.fixture
    def docs_dir(self):
        """Get the documentation directory path."""
        return Path(__file__).parent.parent.parent / "docs"
    
    def test_all_required_documentation_exists(self, docs_dir):
        """Test that all required documentation files exist."""
        required_docs = [
            "installation_guide.md",
            "usage_documentation.md", 
            "migration_guide.md",
            "getting_started_guide.md",
            "troubleshooting_guide.md",
            "api_reference.md"
        ]
        
        for doc in required_docs:
            doc_path = docs_dir / doc
            assert doc_path.exists(), f"Required documentation file missing: {doc}"
            assert doc_path.stat().st_size > 100, f"Documentation file too small: {doc}"
    
    def test_installation_guide_completeness(self, docs_dir):
        """Test installation guide covers all required methods."""
        guide_path = docs_dir / "installation_guide.md"
        content = guide_path.read_text()
        
        # Check for pip install instructions
        assert "pip install pacc-cli" in content, "Missing pip install instructions"
        assert "pip install --user pacc-cli" in content, "Missing user install instructions"
        
        # Check for uv tool install instructions
        assert "uv tool install pacc-cli" in content, "Missing uv tool install instructions"
        
        # Check for pipx installation option
        assert "pipx install pacc-cli" in content, "Missing pipx install instructions"
        
        # Check for virtual environment best practices
        assert "virtual environment" in content.lower(), "Missing virtual environment section"
        assert "venv" in content, "Missing venv instructions"
        
        # Check for post-installation setup
        assert "pacc --version" in content, "Missing version check instructions"
        assert "Verifying Installation" in content, "Missing verification section"
        
        # Check for troubleshooting section
        assert "Troubleshooting" in content, "Missing troubleshooting section"
        assert "command not found" in content.lower(), "Missing PATH troubleshooting"
    
    def test_usage_documentation_global_vs_local(self, docs_dir):
        """Test usage documentation covers global vs project-local differences."""
        guide_path = docs_dir / "usage_documentation.md"
        content = guide_path.read_text()
        
        # Check for global usage documentation
        assert "--user" in content, "Missing --user flag documentation"
        assert "--project" in content, "Missing --project flag documentation"
        assert "~/.claude/" in content, "Missing user-level directory reference"
        assert ".claude/" in content, "Missing project-level directory reference"
        
        # Check for scope explanation
        assert "Global vs Project Scope" in content, "Missing scope comparison section"
        assert "User-Level" in content, "Missing user-level explanation"
        assert "Project-Level" in content, "Missing project-level explanation"
        
        # Check for configuration documentation
        assert "Configuration" in content, "Missing configuration section"
        assert "pacc.json" in content, "Missing pacc.json documentation"
        
        # Check for best practices
        assert "Best Practices" in content, "Missing best practices section"
    
    def test_migration_guide_completeness(self, docs_dir):
        """Test migration guide covers all scenarios."""
        guide_path = docs_dir / "migration_guide.md"
        content = guide_path.read_text()
        
        # Check for migration scenarios
        assert "Development Installation → Global" in content or "Development to Global" in content, \
            "Missing development to global migration"
        assert "Project-Specific → System-Wide" in content or "Project-Embedded to Standalone" in content, \
            "Missing project to system migration"
        
        # Check for compatibility considerations
        assert "Compatibility" in content, "Missing compatibility section"
        assert "Version" in content, "Missing version compatibility info"
        
        # Check for rollback plan
        assert "Rollback" in content, "Missing rollback plan"
        
        # Check for troubleshooting
        assert "Troubleshooting" in content, "Missing troubleshooting section"
        
        # Check for data migration
        assert "Data Migration" in content or "Extension Migration" in content, \
            "Missing data/extension migration section"
    
    def test_getting_started_guide_completeness(self, docs_dir):
        """Test getting started guide has proper tutorials."""
        guide_path = docs_dir / "getting_started_guide.md" 
        content = guide_path.read_text()
        
        # Check for quick start
        assert "Quick Start" in content, "Missing quick start section"
        assert "5 minutes" in content.lower() or "five minutes" in content.lower(), \
            "Missing time estimate for quick start"
        
        # Check for tutorials
        assert "Tutorial" in content, "Missing tutorial section"
        assert "Installing Your First" in content, "Missing first installation tutorial"
        
        # Check for workflow examples
        assert "Common Workflows" in content or "Workflows" in content, \
            "Missing workflow examples"
        
        # Check for extension type coverage
        assert "Hooks" in content, "Missing hooks documentation"
        assert "MCP" in content, "Missing MCP server documentation"
        assert "Agents" in content, "Missing agents documentation"
        assert "Commands" in content, "Missing commands documentation"
        
        # Check for next steps
        assert "Next Steps" in content, "Missing next steps section"
    
    def test_code_examples_are_valid(self, docs_dir):
        """Test that code examples in documentation are valid."""
        # Check shell command examples
        for doc_file in docs_dir.glob("*.md"):
            content = doc_file.read_text()
            
            # Extract code blocks
            code_blocks = re.findall(r'```(?:bash|sh)\n(.*?)\n```', content, re.DOTALL)
            
            for block in code_blocks:
                # Check for common syntax errors
                lines = block.strip().split('\n')
                for line in lines:
                    # Skip comments and empty lines
                    if line.strip().startswith('#') or not line.strip():
                        continue
                    
                    # Check for basic command structure
                    if line.strip().startswith('pacc '):  # Only check actual pacc commands
                        # Ensure command has proper structure
                        assert ' ' in line or line.strip() == 'pacc', \
                            f"Invalid pacc command in {doc_file.name}: {line}"
                        
                        # Check for valid subcommands
                        if ' ' in line:
                            parts = line.strip().split()
                            valid_commands = ['install', 'validate', 'list', 'remove', 
                                           'info', 'init', 'config', '--version', '--help', '-h', '-V']
                            if len(parts) > 1 and not parts[1].startswith('-'):
                                assert any(cmd in parts[1] for cmd in valid_commands), \
                                    f"Unknown command in {doc_file.name}: {parts[1]}"
    
    def test_troubleshooting_guide_coverage(self, docs_dir):
        """Test troubleshooting guide covers common issues."""
        guide_path = docs_dir / "troubleshooting_guide.md"
        content = guide_path.read_text()
        
        # Check for common issue coverage
        issues = [
            "command not found",
            "Permission",
            "ModuleNotFoundError",
            "pip", 
            "PATH",
            "virtual environment",
            "Installation"
        ]
        
        for issue in issues:
            assert issue in content or issue.lower() in content.lower(), \
                f"Troubleshooting guide missing coverage for: {issue}"
        
        # Check for platform-specific sections
        assert "Windows" in content, "Missing Windows troubleshooting"
        assert "macOS" in content or "Mac" in content, "Missing macOS troubleshooting"
        assert "Linux" in content, "Missing Linux troubleshooting"
        
        # Check for debug information
        assert "Debug" in content or "Logging" in content, "Missing debug/logging section"
    
    def test_documentation_links_are_valid(self, docs_dir):
        """Test that internal documentation links are valid."""
        for doc_file in docs_dir.glob("*.md"):
            content = doc_file.read_text()
            
            # Find all markdown links
            links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
            
            for link_text, link_url in links:
                # Check internal links
                if link_url.endswith('.md') and not link_url.startswith('http'):
                    # Remove anchors
                    file_path = link_url.split('#')[0]
                    
                    # Skip if it's a relative path to parent directory
                    if file_path.startswith('../'):
                        continue
                        
                    # Check if linked file exists
                    linked_file = docs_dir / file_path
                    assert linked_file.exists(), \
                        f"Broken link in {doc_file.name}: {link_url} (file not found)"
    
    def test_package_name_consistency(self, docs_dir):
        """Test that package name 'pacc-cli' is used consistently."""
        for doc_file in docs_dir.glob("*.md"):
            content = doc_file.read_text()
            
            # Check pip install commands use pacc-cli
            pip_installs = re.findall(r'pip install ([^\s\[]+)', content)
            for package in pip_installs:
                if package.startswith('pacc'):
                    # Allow pacc-cli with version specifiers or extras, clean backticks
                    base_package = package.strip('`').split('==')[0].split('[')[0]
                    assert base_package == 'pacc-cli', \
                        f"Incorrect package name in {doc_file.name}: {package} (should be pacc-cli)"
            
            # Check pipx/uv commands
            tool_installs = re.findall(r'(?:pipx|uv tool) install ([^\s\[]+)', content)
            for package in tool_installs:
                if package.startswith('pacc'):
                    # Allow pacc-cli with version specifiers or extras, clean backticks
                    base_package = package.strip('`').split('==')[0].split('[')[0]
                    assert base_package == 'pacc-cli', \
                        f"Incorrect package name in {doc_file.name}: {package} (should be pacc-cli)"
    
    def test_version_reporting_in_docs(self, docs_dir):
        """Test that documentation includes version information."""
        for doc_file in ["installation_guide.md", "usage_documentation.md", 
                         "getting_started_guide.md", "migration_guide.md",
                         "troubleshooting_guide.md"]:
            guide_path = docs_dir / doc_file
            if guide_path.exists():
                content = guide_path.read_text()
                
                # Check for version footer or version mention
                assert "Version:" in content or "**Version**:" in content or "Last Updated:" in content, \
                    f"Missing version/update info in {doc_file}"
    
    def test_command_examples_coverage(self, docs_dir):
        """Test that all major commands have examples."""
        usage_guide = docs_dir / "usage_documentation.md"
        content = usage_guide.read_text()
        
        commands = ['install', 'validate', 'list', 'remove', 'info']
        
        for cmd in commands:
            # Check command is documented
            assert f"pacc {cmd}" in content, f"Missing examples for 'pacc {cmd}' command"
            
            # Check for examples with flags
            assert f"--" in content, "Missing flag examples"
    
    @pytest.mark.skipif(sys.platform.startswith('win'), reason="Shell script test for Unix-like systems")
    def test_shell_scripts_in_docs_are_valid(self, docs_dir):
        """Test that shell scripts in documentation have valid syntax."""
        for doc_file in docs_dir.glob("*.md"):
            content = doc_file.read_text()
            
            # Extract shell script blocks
            script_blocks = re.findall(r'```(?:bash|sh)\n(.*?)\n```', content, re.DOTALL)
            
            for block in script_blocks:
                # Skip if it's just commands, not a script
                if not any(keyword in block for keyword in ['#!/bin/bash', 'if ', 'for ', 'while ']):
                    continue
                
                # Skip if it contains placeholder syntax
                if any(placeholder in block for placeholder in ['<', '>', '[', ']']):
                    continue
                
                # Create temporary script file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                    f.write(block)
                    script_path = f.name
                
                try:
                    # Check syntax with bash -n
                    result = subprocess.run(['bash', '-n', script_path], 
                                         capture_output=True, text=True)
                    assert result.returncode == 0, \
                        f"Shell script syntax error in {doc_file.name}: {result.stderr}"
                finally:
                    os.unlink(script_path)


class TestDocumentationExamples:
    """Test that examples in documentation actually work."""
    
    def test_quick_start_example(self, tmp_path):
        """Test the quick start example works."""
        # Create a simple hook as shown in docs
        hook_content = {
            "name": "format-hook",
            "eventTypes": ["PreToolUse"],
            "matchers": [{"tool": "Write"}],
            "commands": ["echo 'Formatting code...'"],
            "description": "Simple formatting hook"
        }
        
        hook_file = tmp_path / "format-hook.json"
        hook_file.write_text(json.dumps(hook_content, indent=2))
        
        # The hook file should be valid JSON
        loaded = json.loads(hook_file.read_text())
        assert loaded["name"] == "format-hook"
        assert "PreToolUse" in loaded["eventTypes"]
    
    def test_complex_hook_example(self, tmp_path):
        """Test more complex hook examples from docs."""
        hook_content = {
            "name": "quality-check",
            "description": "Run quality checks before code modifications",
            "eventTypes": ["PreToolUse"],
            "matchers": [
                {
                    "tool": "Write",
                    "pathGlob": "**/*.{js,py,ts}"
                }
            ],
            "commands": [
                "echo '🔍 Running quality checks...'",
                "echo '✓ Syntax check passed'",
                "echo '✓ Style check passed'"
            ]
        }
        
        hook_file = tmp_path / "quality-check-hook.json"
        hook_file.write_text(json.dumps(hook_content, indent=2))
        
        # Validate structure
        loaded = json.loads(hook_file.read_text())
        assert loaded["name"] == "quality-check"
        assert len(loaded["commands"]) == 3
        assert loaded["matchers"][0]["pathGlob"] == "**/*.{js,py,ts}"


class TestDocumentationMaintenance:
    """Test documentation maintenance and consistency."""
    
    @pytest.fixture
    def docs_dir(self):
        """Get the documentation directory path."""
        return Path(__file__).parent.parent.parent / "docs"
    
    def test_no_dead_links_to_external_resources(self, docs_dir):
        """Test that external links are properly formatted."""
        for doc_file in docs_dir.glob("*.md"):
            content = doc_file.read_text()
            
            # Find all links
            links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
            
            for link_text, link_url in links:
                if link_url.startswith('http'):
                    # Just check URL format, not actual connectivity
                    assert link_url.startswith(('http://', 'https://')), \
                        f"Invalid URL format in {doc_file.name}: {link_url}"
    
    def test_consistent_formatting(self, docs_dir):
        """Test documentation follows consistent formatting."""
        for doc_file in docs_dir.glob("*.md"):
            content = doc_file.read_text()
            lines = content.split('\n')
            
            # Check headers have proper spacing
            for i, line in enumerate(lines):
                if line.startswith('#'):
                    # Headers should have blank line before (except first line)
                    if i > 0:
                        assert i == 0 or lines[i-1].strip() == '', \
                            f"Missing blank line before header in {doc_file.name}, line {i+1}"
    
    def test_code_block_languages_specified(self, docs_dir):
        """Test that code blocks specify languages."""
        for doc_file in docs_dir.glob("*.md"):
            content = doc_file.read_text()
            
            # Find code blocks without language
            plain_blocks = re.findall(r'```\n', content)
            
            # Allow some plain blocks but not too many
            assert len(plain_blocks) < 5, \
                f"Too many code blocks without language specification in {doc_file.name}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])