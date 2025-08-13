"""End-to-end tests for complete user journeys and cross-platform compatibility."""

import json
import yaml
import os
import platform
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from pacc.core.file_utils import FilePathValidator, DirectoryScanner, FileFilter, PathNormalizer
from pacc.validators.base import ValidationResult
from pacc.errors.exceptions import ValidationError, FileSystemError, SecurityError


@pytest.mark.e2e
class TestCompleteUserJourneys:
    """Test complete user journeys from start to finish."""
    
    def test_new_user_first_time_setup(self, temp_dir):
        """Test complete journey for a new user setting up PACC for the first time."""
        # Simulate new user's project directory
        project_dir = temp_dir / "my_new_project"
        project_dir.mkdir()
        
        # User creates a .claude directory structure
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir()
        
        # User wants to validate some existing extension files they found online
        extensions_dir = project_dir / "downloaded_extensions"
        extensions_dir.mkdir()
        
        # Create various extension files (as if downloaded from different sources)
        # Hook file
        hook_file = extensions_dir / "useful_hook.json"
        hook_file.write_text(json.dumps({
            "name": "useful-hook",
            "version": "1.0.0",
            "description": "A useful hook for development",
            "events": ["PreToolUse", "PostToolUse"],
            "matchers": [{"pattern": "*.py"}]
        }, indent=2))
        
        # MCP server config
        mcp_file = extensions_dir / "ai_server.yaml"
        mcp_file.write_text(yaml.dump({
            "name": "ai-server",
            "command": "python",
            "args": ["-m", "ai_server"],
            "env": {"API_KEY": "${AI_API_KEY}"}
        }))
        
        # Agent file
        agent_file = extensions_dir / "code_reviewer.md"
        agent_file.write_text("""---
name: code-reviewer
version: 1.0.0
description: An agent that reviews code for best practices
capabilities:
  - code_analysis
  - best_practices
  - security_review
---

# Code Reviewer Agent

This agent specializes in reviewing code for best practices and security issues.

## Instructions

When reviewing code:
1. Check for security vulnerabilities
2. Verify best practices are followed
3. Suggest improvements
4. Flag potential issues

## Examples

Use this agent when you need thorough code review.
""")
        
        # Command file
        command_file = extensions_dir / "deploy_command.md"
        command_file.write_text("""# Deploy Command

Automates deployment process for applications.

## Usage

```bash
deploy --environment production --confirm
```

## Parameters

- `--environment`: Target environment (development, staging, production)
- `--confirm`: Skip confirmation prompts
- `--dry-run`: Show what would be deployed without executing

## Examples

```bash
# Deploy to staging
deploy --environment staging

# Production deployment with confirmation
deploy --environment production --confirm
```
""")
        
        # Step 1: User scans downloaded extensions
        scanner = DirectoryScanner()
        discovered_files = list(scanner.scan_directory(extensions_dir, recursive=True))
        
        # Should discover all extension files
        assert len(discovered_files) == 4
        file_names = [f.name for f in discovered_files]
        assert "useful_hook.json" in file_names
        assert "ai_server.yaml" in file_names
        assert "code_reviewer.md" in file_names
        assert "deploy_command.md" in file_names
        
        # Step 2: User filters by extension type
        file_filter = FileFilter()
        
        # User wants to validate JSON hooks first
        json_filter = FileFilter().add_extension_filter({'.json'})
        json_files = json_filter.filter_files(discovered_files)
        assert len(json_files) == 1
        assert json_files[0].name == "useful_hook.json"
        
        # User validates YAML configs
        yaml_filter = FileFilter().add_extension_filter({'.yaml', '.yml'})
        yaml_files = yaml_filter.filter_files(discovered_files)
        assert len(yaml_files) == 1
        assert yaml_files[0].name == "ai_server.yaml"
        
        # User validates markdown files (agents and commands)
        md_filter = FileFilter().add_extension_filter({'.md'})
        md_files = md_filter.filter_files(discovered_files)
        assert len(md_files) == 2
        
        # Step 3: User validates file paths and accessibility
        validator = FilePathValidator()
        for file_path in discovered_files:
            assert validator.is_valid_path(file_path)
        
        # Step 4: User organizes files by type for installation
        extension_types = {
            'hooks': json_files,
            'mcp': yaml_files,
            'agents': [f for f in md_files if 'agent' in f.name or 'reviewer' in f.name],
            'commands': [f for f in md_files if 'command' in f.name]
        }
        
        assert len(extension_types['hooks']) == 1
        assert len(extension_types['mcp']) == 1
        assert len(extension_types['agents']) == 1
        assert len(extension_types['commands']) == 1
        
        # Step 5: User normalizes paths for cross-platform compatibility
        normalized_paths = {}
        for ext_type, files in extension_types.items():
            normalized_paths[ext_type] = [PathNormalizer.normalize(f) for f in files]
        
        # All paths should be absolute and normalized
        for ext_type, paths in normalized_paths.items():
            for path in paths:
                assert path.is_absolute()
                assert path.exists()
    
    def test_power_user_batch_processing(self, temp_dir):
        """Test power user batch processing large sets of extensions."""
        # Create large set of extensions
        extensions_root = temp_dir / "extension_library"
        extensions_root.mkdir()
        
        # Create multiple categories with many files
        categories = {
            'productivity_hooks': 15,
            'development_tools': 20,
            'ai_agents': 25,
            'utility_commands': 30
        }
        
        total_files = 0
        for category, count in categories.items():
            category_dir = extensions_root / category
            category_dir.mkdir()
            
            for i in range(count):
                if 'hooks' in category:
                    file_path = category_dir / f"hook_{i:02d}.json"
                    file_path.write_text(json.dumps({
                        "name": f"hook-{i}",
                        "version": "1.0.0",
                        "events": ["PreToolUse"],
                        "description": f"Hook number {i}"
                    }))
                elif 'tools' in category:
                    file_path = category_dir / f"tool_{i:02d}.yaml"
                    file_path.write_text(yaml.dump({
                        "name": f"tool-{i}",
                        "command": "python",
                        "args": [f"-m", f"tool_{i}"]
                    }))
                elif 'agents' in category:
                    file_path = category_dir / f"agent_{i:02d}.md"
                    file_path.write_text(f"""---
name: agent-{i}
version: 1.0.0
description: Agent number {i}
---

# Agent {i}

This is agent number {i}.
""")
                elif 'commands' in category:
                    file_path = category_dir / f"command_{i:02d}.md"
                    file_path.write_text(f"""# Command {i}

This is command number {i}.

## Usage

```bash
command-{i} --help
```
""")
                total_files += 1
        
        # Power user workflow: batch process everything
        import time
        start_time = time.time()
        
        # Step 1: High-performance scanning
        scanner = DirectoryScanner()
        all_files = list(scanner.scan_directory(extensions_root, recursive=True))
        
        # Step 2: Parallel filtering by type
        filters = {
            'hooks': FileFilter().add_extension_filter({'.json'}),
            'mcp': FileFilter().add_extension_filter({'.yaml', '.yml'}),
            'agents': FileFilter().add_extension_filter({'.md'}).add_pattern_filter(['agent_*']),
            'commands': FileFilter().add_extension_filter({'.md'}).add_pattern_filter(['command_*'])
        }
        
        filtered_results = {}
        for ext_type, file_filter in filters.items():
            filtered_results[ext_type] = file_filter.filter_files(all_files)
        
        # Step 3: Batch validation
        validator = FilePathValidator()
        validation_results = {}
        
        for ext_type, files in filtered_results.items():
            valid_files = []
            invalid_files = []
            
            for file_path in files:
                if validator.is_valid_path(file_path):
                    valid_files.append(file_path)
                else:
                    invalid_files.append(file_path)
            
            validation_results[ext_type] = {
                'valid': valid_files,
                'invalid': invalid_files,
                'total': len(files)
            }
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify performance and results
        assert len(all_files) == total_files
        assert processing_time < 5.0  # Should process 90 files in under 5 seconds
        
        # Verify categorization
        assert len(filtered_results['hooks']) == 15
        assert len(filtered_results['mcp']) == 20
        assert len(filtered_results['agents']) == 25
        assert len(filtered_results['commands']) == 30
        
        # All files should be valid
        for ext_type, results in validation_results.items():
            assert len(results['invalid']) == 0
            assert len(results['valid']) == results['total']
    
    def test_error_correction_workflow(self, temp_dir):
        """Test user workflow for finding and correcting validation errors."""
        # Create directory with problematic extensions
        problem_dir = temp_dir / "problematic_extensions"
        problem_dir.mkdir()
        
        # Create files with various issues
        issues = [
            # Missing required fields
            ("incomplete_hook.json", {"name": "incomplete", "version": "1.0.0"}),
            
            # Invalid JSON syntax
            ("syntax_error.json", '{"name": "broken", "version": 1.0.0, "events": [}'),
            
            # Wrong field types
            ("type_error.json", {"name": "wrong-types", "version": 1.0, "events": "not-a-list"}),
            
            # Valid file for comparison
            ("good_hook.json", {
                "name": "good-hook",
                "version": "1.0.0", 
                "events": ["PreToolUse"],
                "description": "A good hook"
            }),
        ]
        
        for filename, content in issues:
            file_path = problem_dir / filename
            if isinstance(content, dict):
                file_path.write_text(json.dumps(content, indent=2))
            else:
                file_path.write_text(content)
        
        # Step 1: User discovers validation issues
        class DiagnosticValidator:
            def __init__(self):
                self.file_validator = FilePathValidator()
            
            def validate_hook_file(self, file_path):
                result = {
                    'file_path': str(file_path),
                    'is_valid': True,
                    'errors': [],
                    'warnings': [],
                    'suggestions': []
                }
                
                # Check file accessibility
                if not self.file_validator.is_valid_path(file_path):
                    result['is_valid'] = False
                    result['errors'].append("File is not accessible")
                    return result
                
                try:
                    # Read and parse JSON
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    
                    # Check required fields
                    required_fields = ['name', 'version', 'events']
                    for field in required_fields:
                        if field not in data:
                            result['is_valid'] = False
                            result['errors'].append(f"Missing required field: {field}")
                            result['suggestions'].append(f"Add '{field}' field to hook configuration")
                    
                    # Check field types
                    if 'events' in data and not isinstance(data['events'], list):
                        result['is_valid'] = False
                        result['errors'].append("Events field must be a list")
                        result['suggestions'].append("Change events to array format: [\"EventName\"]")
                    
                    if 'version' in data and not isinstance(data['version'], str):
                        result['is_valid'] = False
                        result['errors'].append("Version must be a string")
                        result['suggestions'].append("Use string format: \"1.0.0\"")
                    
                    # Check optional but recommended fields
                    if 'description' not in data:
                        result['warnings'].append("Description field is recommended")
                        result['suggestions'].append("Add description for better documentation")
                
                except json.JSONDecodeError as e:
                    result['is_valid'] = False
                    result['errors'].append(f"Invalid JSON syntax: {e.msg} at line {e.lineno}")
                    result['suggestions'].append("Fix JSON syntax errors")
                
                except Exception as e:
                    result['is_valid'] = False
                    result['errors'].append(f"Validation error: {str(e)}")
                
                return result
        
        diagnostic = DiagnosticValidator()
        
        # Step 2: User runs validation on all files
        scanner = DirectoryScanner()
        json_files = list(scanner.scan_directory(problem_dir, recursive=True))
        json_files = [f for f in json_files if f.suffix == '.json']
        
        validation_report = []
        for file_path in json_files:
            result = diagnostic.validate_hook_file(file_path)
            validation_report.append(result)
        
        # Step 3: User analyzes validation report
        valid_files = [r for r in validation_report if r['is_valid']]
        invalid_files = [r for r in validation_report if not r['is_valid']]
        files_with_warnings = [r for r in validation_report if r['warnings']]
        
        # Verify expected results
        assert len(validation_report) == 4
        assert len(valid_files) == 1  # Only good_hook.json should be valid
        assert len(invalid_files) == 3  # Three problematic files
        assert len(files_with_warnings) >= 1  # At least one file with warnings
        
        # Step 4: User fixes issues based on suggestions
        # Find specific error types
        syntax_errors = [r for r in invalid_files if any("syntax" in error.lower() for error in r['errors'])]
        missing_field_errors = [r for r in invalid_files if any("missing" in error.lower() for error in r['errors'])]
        type_errors = [r for r in invalid_files if any("must be" in error.lower() for error in r['errors'])]
        
        assert len(syntax_errors) >= 1
        assert len(missing_field_errors) >= 1
        assert len(type_errors) >= 1
        
        # Verify suggestions are helpful
        all_suggestions = []
        for result in validation_report:
            all_suggestions.extend(result['suggestions'])
        
        suggestion_text = " ".join(all_suggestions).lower()
        assert "fix json syntax" in suggestion_text
        assert "add" in suggestion_text  # Should suggest adding missing fields
        assert "array format" in suggestion_text or "list" in suggestion_text


@pytest.mark.cross_platform
class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility across different operating systems."""
    
    def test_path_handling_across_platforms(self, temp_dir):
        """Test path handling works correctly across different platforms."""
        # Create test files with various path patterns
        test_cases = [
            "simple_file.json",
            "file-with-dashes.yaml",
            "file_with_underscores.md",
            "file.with.dots.txt",
        ]
        
        if platform.system() != "Windows":
            # Unix-like systems can handle these
            test_cases.extend([
                "file with spaces.json",
                "file:with:colons.yaml",
                "file|with|pipes.md"
            ])
        
        created_files = []
        for filename in test_cases:
            file_path = temp_dir / filename
            file_path.write_text("test content")
            created_files.append(file_path)
        
        # Test path normalization across platforms
        normalizer = PathNormalizer()
        
        for file_path in created_files:
            # Test normalization
            normalized = normalizer.normalize(file_path)
            assert normalized.exists()
            assert normalized.is_absolute()
            
            # Test POSIX conversion
            posix_path = normalizer.to_posix(file_path)
            assert isinstance(posix_path, str)
            assert "/" in posix_path or len(posix_path.split("/")) > 1
        
        # Test relative path calculation
        for file_path in created_files[:3]:  # Test subset to avoid too many combinations
            relative = normalizer.relative_to(file_path, temp_dir)
            # Should either be relative or absolute (if not related)
            assert isinstance(relative, Path)
    
    def test_file_scanning_cross_platform(self, temp_dir):
        """Test file scanning works across platforms with different file systems."""
        # Create test directory structure
        subdir_cases = [
            "simple_dir",
            "dir-with-dashes", 
            "dir_with_underscores",
        ]
        
        if platform.system() != "Windows":
            subdir_cases.append("dir with spaces")
        
        created_dirs = []
        for dirname in subdir_cases:
            dir_path = temp_dir / dirname
            dir_path.mkdir()
            created_dirs.append(dir_path)
            
            # Create files in each directory
            (dir_path / "test.json").write_text('{"test": true}')
            (dir_path / "test.yaml").write_text('test: true')
            (dir_path / "test.md").write_text('# Test')
        
        # Test scanning
        scanner = DirectoryScanner()
        discovered_files = list(scanner.scan_directory(temp_dir, recursive=True))
        
        # Should find all created files
        expected_file_count = len(created_dirs) * 3  # 3 files per directory
        assert len(discovered_files) >= expected_file_count
        
        # Test that all platform-specific directories were scanned
        discovered_dirs = {f.parent.name for f in discovered_files}
        for expected_dir in subdir_cases:
            assert expected_dir in discovered_dirs
    
    @pytest.mark.skipif(platform.system() == "Windows", reason="Unix-specific permissions test")
    def test_unix_permissions_handling(self, temp_dir):
        """Test handling of Unix-style file permissions."""
        # Create files with different permissions
        readable_file = temp_dir / "readable.json"
        readable_file.write_text('{"readable": true}')
        
        # Create temporarily inaccessible file
        restricted_file = temp_dir / "restricted.json"
        restricted_file.write_text('{"restricted": true}')
        
        try:
            # Remove read permissions
            restricted_file.chmod(0o000)
            
            # Test validation
            validator = FilePathValidator()
            
            assert validator.is_valid_path(readable_file)
            # Restricted file should fail validation due to permissions
            # Note: This might pass if running as root
            restricted_valid = validator.is_valid_path(restricted_file)
            
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)
            
            # If not running as root, should have failed validation
            if os.getuid() != 0:
                assert not restricted_valid
        
        finally:
            # Ensure permissions are restored for cleanup
            try:
                restricted_file.chmod(0o644)
            except:
                pass
    
    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows-specific test")
    def test_windows_specific_handling(self, temp_dir):
        """Test Windows-specific file handling."""
        # Test Windows path patterns
        test_cases = [
            "normal_file.json",
            "UPPERCASE.JSON",
            "MixedCase.Yaml",
            "file.with.multiple.dots.json"
        ]
        
        for filename in test_cases:
            file_path = temp_dir / filename
            file_path.write_text("test content")
        
        # Test case-insensitive extension matching
        scanner = DirectoryScanner()
        discovered_files = list(scanner.scan_directory(temp_dir, recursive=True))
        
        file_filter = FileFilter().add_extension_filter({'.json'})
        json_files = file_filter.filter_files(discovered_files)
        
        # Should match both .json and .JSON files
        json_names = [f.name for f in json_files]
        assert "normal_file.json" in json_names
        assert "UPPERCASE.JSON" in json_names
        assert "file.with.multiple.dots.json" in json_names
    
    def test_unicode_filename_support(self, temp_dir):
        """Test support for Unicode filenames across platforms."""
        # Unicode test cases (some may not work on all file systems)
        unicode_cases = [
            "café.json",  # Accented characters
            "测试.yaml",  # Chinese characters
            "файл.md",   # Cyrillic characters
            "🚀rocket.json",  # Emoji (may not work on all systems)
        ]
        
        created_files = []
        for filename in unicode_cases:
            try:
                file_path = temp_dir / filename
                file_path.write_text("unicode test content")
                created_files.append(file_path)
            except (UnicodeError, OSError):
                # Some file systems don't support certain Unicode characters
                continue
        
        if created_files:
            # Test that Unicode files can be processed
            scanner = DirectoryScanner()
            discovered_files = list(scanner.scan_directory(temp_dir, recursive=True))
            
            unicode_files = [f for f in discovered_files if f in created_files]
            assert len(unicode_files) > 0
            
            # Test path normalization with Unicode
            normalizer = PathNormalizer()
            for file_path in unicode_files:
                normalized = normalizer.normalize(file_path)
                assert normalized.exists()


@pytest.mark.security
class TestSecurityWorkflows:
    """Test security-related workflows and protections."""
    
    def test_path_traversal_protection(self, temp_dir):
        """Test protection against path traversal attacks."""
        # Create test structure
        secure_dir = temp_dir / "secure_area"
        secure_dir.mkdir()
        secure_file = secure_dir / "secure.json"
        secure_file.write_text('{"secure": true}')
        
        # Create file outside secure area
        outside_file = temp_dir / "outside.json"
        outside_file.write_text('{"outside": true}')
        
        # Test various path traversal attempts
        traversal_attempts = [
            "../outside.json",
            "../../outside.json",
            "./../../outside.json",
            "subdir/../outside.json",
            "subdir/../../outside.json",
        ]
        
        validator = FilePathValidator()
        
        # All traversal attempts should fail validation
        for attempt in traversal_attempts:
            traversal_path = secure_dir / attempt
            try:
                # Even if the path resolves, it should be rejected
                is_valid = validator.is_valid_path(traversal_path)
                assert not is_valid, f"Path traversal attempt should be rejected: {attempt}"
            except (ValueError, OSError):
                # Path traversal should be caught and rejected
                pass
    
    def test_malicious_file_detection(self, temp_dir):
        """Test detection of potentially malicious files."""
        # Create files that might be problematic
        test_cases = [
            # Extremely large file
            ("huge_file.json", "x" * (20 * 1024 * 1024)),  # 20MB file
            
            # File with suspicious content patterns
            ("suspicious.json", '{"eval": "import os; os.system(\\"rm -rf /\\")", "data": "normal"}'),
            
            # Binary file with text extension
            ("binary.json", b"\x00\x01\x02\x03\xFF\xFE\xFD\xFC"),
            
            # File with very long lines
            ("long_line.json", '{"data": "' + "x" * 100000 + '"}'),
        ]
        
        created_files = []
        for filename, content in test_cases:
            file_path = temp_dir / filename
            if isinstance(content, bytes):
                file_path.write_bytes(content)
            else:
                file_path.write_text(content)
            created_files.append(file_path)
        
        # Create security-aware validator
        class SecurityValidator:
            def __init__(self, max_file_size=10*1024*1024):  # 10MB limit
                self.max_file_size = max_file_size
                self.suspicious_patterns = [
                    "import os",
                    "eval",
                    "exec",
                    "subprocess",
                    "__import__",
                    "rm -rf",
                    "del /",
                ]
            
            def scan_file_security(self, file_path):
                issues = []
                
                try:
                    # Check file size
                    file_size = file_path.stat().st_size
                    if file_size > self.max_file_size:
                        issues.append(f"File too large: {file_size} bytes")
                    
                    # Try to read as text
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        
                        # Check for suspicious patterns
                        for pattern in self.suspicious_patterns:
                            if pattern in content:
                                issues.append(f"Suspicious pattern detected: {pattern}")
                        
                        # Check line length
                        for i, line in enumerate(content.split('\n'), 1):
                            if len(line) > 10000:  # Very long line
                                issues.append(f"Extremely long line at line {i}")
                                break
                    
                    except UnicodeDecodeError:
                        issues.append("Binary content in text file")
                    
                except Exception as e:
                    issues.append(f"Security scan error: {str(e)}")
                
                return issues
        
        security_validator = SecurityValidator()
        
        # Scan all test files
        security_reports = []
        for file_path in created_files:
            issues = security_validator.scan_file_security(file_path)
            security_reports.append({
                'file': file_path.name,
                'issues': issues,
                'is_safe': len(issues) == 0
            })
        
        # Verify security issues are detected
        unsafe_files = [r for r in security_reports if not r['is_safe']]
        assert len(unsafe_files) == len(test_cases)  # All test files should be flagged
        
        # Check specific detections
        issue_types = []
        for report in security_reports:
            issue_types.extend(report['issues'])
        
        issue_text = " ".join(issue_types).lower()
        assert "too large" in issue_text
        assert "suspicious pattern" in issue_text or "suspicious" in issue_text
        assert "binary content" in issue_text
        assert "long line" in issue_text
    
    def test_safe_file_handling(self, temp_dir):
        """Test that safe file handling practices are followed."""
        # Create test files with various characteristics
        safe_files_dir = temp_dir / "safe_files"
        safe_files_dir.mkdir()
        
        # Normal, safe files
        safe_cases = [
            ("normal.json", {"name": "test", "version": "1.0.0"}),
            ("config.yaml", {"server": "localhost", "port": 8080}),
            ("agent.md", "# Test Agent\n\nThis is a test agent."),
        ]
        
        for filename, content in safe_cases:
            file_path = safe_files_dir / filename
            if isinstance(content, dict):
                if filename.endswith('.json'):
                    file_path.write_text(json.dumps(content, indent=2))
                else:
                    file_path.write_text(yaml.dump(content))
            else:
                file_path.write_text(content)
        
        # Test safe processing pipeline
        class SafeProcessor:
            def __init__(self):
                self.file_validator = FilePathValidator()
                self.scanner = DirectoryScanner()
            
            def process_safely(self, directory):
                results = {
                    'processed': [],
                    'skipped': [],
                    'errors': []
                }
                
                try:
                    # Step 1: Validate directory safety
                    if not self.file_validator.is_safe_directory(directory):
                        results['errors'].append("Directory is not safe to process")
                        return results
                    
                    # Step 2: Scan with safety checks
                    for file_path in self.scanner.scan_directory(directory, recursive=True):
                        try:
                            # Validate each file
                            if not self.file_validator.is_valid_path(file_path):
                                results['skipped'].append(str(file_path))
                                continue
                            
                            # Additional safety checks
                            file_size = file_path.stat().st_size
                            if file_size > 1024 * 1024:  # 1MB limit
                                results['skipped'].append(f"{file_path} (too large)")
                                continue
                            
                            # Process file safely
                            with open(file_path, 'r', encoding='utf-8') as f:
                                # Read with size limit
                                content = f.read(1024 * 1024)  # Max 1MB
                            
                            results['processed'].append({
                                'path': str(file_path),
                                'size': file_size,
                                'type': file_path.suffix
                            })
                        
                        except Exception as e:
                            results['errors'].append(f"Error processing {file_path}: {str(e)}")
                
                except Exception as e:
                    results['errors'].append(f"Processing error: {str(e)}")
                
                return results
        
        processor = SafeProcessor()
        results = processor.process_safely(safe_files_dir)
        
        # Verify safe processing
        assert len(results['processed']) == 3  # All safe files should be processed
        assert len(results['skipped']) == 0    # No files should be skipped
        assert len(results['errors']) == 0     # No errors should occur
        
        # Verify file information is captured
        processed_types = {item['type'] for item in results['processed']}
        assert '.json' in processed_types
        assert '.yaml' in processed_types
        assert '.md' in processed_types