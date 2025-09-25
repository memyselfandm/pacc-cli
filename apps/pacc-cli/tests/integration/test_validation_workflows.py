"""Integration tests for complete validation workflows."""

import json
from pathlib import Path
from unittest.mock import patch

from pacc.core.file_utils import DirectoryScanner, FileFilter, FilePathValidator
from pacc.validators.base import BaseValidator, ValidationResult


class TestValidationWorkflows:
    """Test complete validation workflows integrating multiple components."""

    def test_complete_directory_validation_workflow(self, sample_directory_structure):
        """Test complete workflow: scan → filter → validate → report."""
        # Setup components
        validator = FilePathValidator(allowed_extensions={".json", ".yaml", ".md"})
        scanner = DirectoryScanner(validator=validator)
        file_filter = FileFilter().add_extension_filter({".json", ".md"}).add_exclude_hidden()

        # Step 1: Scan directory
        discovered_files = list(scanner.scan_directory(sample_directory_structure, recursive=True))

        # Step 2: Filter files
        filtered_files = file_filter.filter_files(discovered_files)

        # Step 3: Group by extension type (simulated validation)
        json_files = [f for f in filtered_files if f.suffix == ".json"]
        md_files = [f for f in filtered_files if f.suffix == ".md"]

        # Verify workflow results
        assert len(discovered_files) > 0
        assert len(filtered_files) <= len(discovered_files)
        assert len(json_files) > 0
        assert len(md_files) > 0

        # All filtered files should have allowed extensions
        assert all(f.suffix in {".json", ".md"} for f in filtered_files)

        # No hidden files should be included
        assert all(not f.name.startswith(".") for f in filtered_files)

    def test_error_handling_workflow(self, temp_dir):
        """Test workflow error handling and recovery."""
        # Create test structure with problematic files
        test_dir = temp_dir / "error_test"
        test_dir.mkdir()

        # Valid file
        valid_file = test_dir / "valid.json"
        valid_file.write_text('{"name": "test", "version": "1.0.0"}')

        # Invalid JSON
        invalid_file = test_dir / "invalid.json"
        invalid_file.write_text('{"invalid": json, syntax}')

        # Inaccessible file (simulate permission error)
        restricted_file = test_dir / "restricted.json"
        restricted_file.write_text('{"restricted": true}')

        # Test workflow with error handling
        scanner = DirectoryScanner()
        discovered_files = list(scanner.scan_directory(test_dir, recursive=True))

        # Should discover all files despite later issues
        assert len(discovered_files) == 3

        # Test file access validation
        validator = FilePathValidator()
        accessible_files = []
        inaccessible_files = []

        for file_path in discovered_files:
            if validator.is_valid_path(file_path):
                accessible_files.append(file_path)
            else:
                inaccessible_files.append(file_path)

        # Most files should be accessible
        assert len(accessible_files) >= 2

    def test_large_directory_workflow(self, performance_directory):
        """Test workflow performance with large directory."""
        import time

        start_time = time.time()

        # Setup efficient scanning
        validator = FilePathValidator(allowed_extensions={".json", ".yaml", ".md"})
        scanner = DirectoryScanner(validator=validator)
        file_filter = (
            FileFilter()
            .add_extension_filter({".json", ".yaml", ".md"})
            .add_size_filter(0, 1024 * 1024)  # Max 1MB
            .add_exclude_hidden()
        )

        # Execute workflow
        discovered_files = list(scanner.scan_directory(performance_directory, recursive=True))
        filtered_files = file_filter.filter_files(discovered_files)

        end_time = time.time()
        duration = end_time - start_time

        # Verify performance and results
        assert len(discovered_files) > 1000  # Should find many files
        assert len(filtered_files) > 0  # Should have some matching files
        assert duration < 2.0  # Should complete within 2 seconds

    def test_cross_platform_path_workflow(self, temp_dir):
        """Test workflow with cross-platform path handling."""
        # Create files with various naming patterns
        test_files = [
            "normal_file.json",
            "file-with-dashes.yaml",
            "file_with_underscores.md",
            "file.with.dots.json",
            "file with spaces.yaml",
            "UPPERCASE.JSON",
            "MixedCase.Yaml",
        ]

        for filename in test_files:
            file_path = temp_dir / filename
            if filename.endswith(".json"):
                file_path.write_text('{"test": true}')
            elif filename.endswith(".yaml"):
                file_path.write_text("test: true")
            else:
                file_path.write_text("# Test file")

        # Test workflow handles all files correctly
        scanner = DirectoryScanner()
        file_filter = FileFilter().add_extension_filter({".json", ".yaml", ".md"})

        discovered_files = list(scanner.scan_directory(temp_dir, recursive=True))
        filtered_files = file_filter.filter_files(discovered_files)

        # Should handle all test files
        assert len(filtered_files) == len(test_files)

        # Test case-insensitive extension matching
        json_files = [f for f in filtered_files if f.suffix.lower() == ".json"]
        yaml_files = [f for f in filtered_files if f.suffix.lower() in {".yaml", ".yml"}]

        assert len(json_files) >= 2  # normal_file.json, UPPERCASE.JSON, etc.
        assert len(yaml_files) >= 2  # Various .yaml files


class TestValidationPipeline:
    """Test validation pipeline with mock validators."""

    def create_mock_hook_validator(self):
        """Create a mock hook validator for testing."""

        class MockHookValidator(BaseValidator):
            def get_extension_type(self):
                return "hooks"

            def validate_single(self, file_path):
                result = ValidationResult(
                    is_valid=True,
                    file_path=str(file_path),
                    extension_type=self.get_extension_type(),
                )

                # Simulate validation logic
                try:
                    with open(file_path) as f:
                        data = json.load(f)

                    # Check required fields
                    required_fields = ["name", "version", "events"]
                    for field in required_fields:
                        if field not in data:
                            result.add_error(
                                "MISSING_FIELD",
                                f"Missing required field: {field}",
                                suggestion=f"Add '{field}' to hook configuration",
                            )

                    # Check events format
                    if "events" in data and not isinstance(data["events"], list):
                        result.add_error(
                            "INVALID_EVENTS",
                            "Events must be a list",
                            suggestion="Change events to array format",
                        )

                    # Add warning for missing description
                    if "description" not in data:
                        result.add_warning(
                            "MISSING_DESCRIPTION",
                            "Hook description is recommended",
                            suggestion="Add description field for better documentation",
                        )

                except json.JSONDecodeError as e:
                    result.add_error(
                        "INVALID_JSON",
                        f"Invalid JSON syntax: {e.msg}",
                        line_number=e.lineno,
                        suggestion="Fix JSON syntax errors",
                    )
                except Exception as e:
                    result.add_error(
                        "VALIDATION_ERROR",
                        f"Validation failed: {e!s}",
                        suggestion="Check file format and content",
                    )

                return result

            def _find_extension_files(self, directory):
                return list(directory.glob("**/*.json"))

        return MockHookValidator()

    def test_hook_validation_pipeline(self, temp_dir):
        """Test complete hook validation pipeline."""
        hook_validator = self.create_mock_hook_validator()

        # Create test hook files
        hooks_dir = temp_dir / "hooks"
        hooks_dir.mkdir()

        # Valid hook
        valid_hook = hooks_dir / "valid_hook.json"
        valid_hook.write_text(
            json.dumps(
                {
                    "name": "test-hook",
                    "version": "1.0.0",
                    "events": ["PreToolUse"],
                    "description": "A test hook",
                },
                indent=2,
            )
        )

        # Hook missing required field
        incomplete_hook = hooks_dir / "incomplete_hook.json"
        incomplete_hook.write_text(
            json.dumps(
                {
                    "name": "incomplete-hook",
                    "version": "1.0.0",
                    # Missing 'events' field
                },
                indent=2,
            )
        )

        # Hook with warning (missing description)
        warning_hook = hooks_dir / "warning_hook.json"
        warning_hook.write_text(
            json.dumps(
                {
                    "name": "warning-hook",
                    "version": "1.0.0",
                    "events": ["PostToolUse"],
                    # Missing 'description' field - should generate warning
                },
                indent=2,
            )
        )

        # Invalid JSON
        invalid_hook = hooks_dir / "invalid_hook.json"
        invalid_hook.write_text('{"name": "invalid", "version": 1.0.0, "events": [}')

        # Run validation pipeline
        results = hook_validator.validate_directory(hooks_dir)

        # Analyze results
        valid_results = [r for r in results if r.is_valid]
        invalid_results = [r for r in results if not r.is_valid]
        results_with_warnings = [r for r in results if r.warnings]

        # Verify expectations
        assert len(results) == 4  # Should validate all 4 files
        assert len(valid_results) == 2  # valid_hook and warning_hook should be valid
        assert len(invalid_results) == 2  # incomplete_hook and invalid_hook should be invalid
        assert len(results_with_warnings) >= 1  # warning_hook should have warnings

        # Check specific error types
        error_codes = []
        for result in invalid_results:
            error_codes.extend([error.code for error in result.errors])

        assert "MISSING_FIELD" in error_codes
        assert "INVALID_JSON" in error_codes

    def test_validation_pipeline_with_filtering(self, temp_dir):
        """Test validation pipeline with pre-filtering."""
        hook_validator = self.create_mock_hook_validator()

        # Create mixed file types
        test_dir = temp_dir / "mixed"
        test_dir.mkdir()

        # Hook file (should be validated)
        hook_file = test_dir / "hook.json"
        hook_file.write_text(
            json.dumps({"name": "test-hook", "version": "1.0.0", "events": ["PreToolUse"]})
        )

        # Non-JSON file (should be ignored)
        text_file = test_dir / "readme.txt"
        text_file.write_text("This is a text file")

        # JSON file that's not a hook (should be validated but may fail)
        data_file = test_dir / "data.json"
        data_file.write_text(json.dumps({"data": "value"}))

        # Use file filter to pre-filter
        scanner = DirectoryScanner()
        file_filter = FileFilter().add_extension_filter({".json"})

        discovered_files = list(scanner.scan_directory(test_dir, recursive=True))
        json_files = file_filter.filter_files(discovered_files)

        # Validate only JSON files
        results = hook_validator.validate_batch(json_files)

        # Should only validate JSON files
        assert len(results) == 2  # hook.json and data.json
        assert all(Path(r.file_path).suffix == ".json" for r in results)

        # hook.json should be valid, data.json should have errors
        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = sum(1 for r in results if not r.is_valid)

        assert valid_count >= 1  # At least the proper hook should be valid
        assert invalid_count >= 1  # data.json should fail hook validation

    def test_batch_validation_error_isolation(self, temp_dir):
        """Test that errors in one file don't affect validation of others."""
        hook_validator = self.create_mock_hook_validator()

        # Create files with various issues
        test_dir = temp_dir / "batch_test"
        test_dir.mkdir()

        files_data = [
            ("good1.json", {"name": "good1", "version": "1.0.0", "events": ["PreToolUse"]}),
            ("good2.json", {"name": "good2", "version": "1.0.0", "events": ["PostToolUse"]}),
            ("bad1.json", '{"invalid": json}'),  # Invalid JSON
            ("bad2.json", {"name": "bad2"}),  # Missing required fields
            ("good3.json", {"name": "good3", "version": "1.0.0", "events": ["Notification"]}),
        ]

        file_paths = []
        for filename, content in files_data:
            file_path = test_dir / filename
            if isinstance(content, dict):
                file_path.write_text(json.dumps(content, indent=2))
            else:
                file_path.write_text(content)
            file_paths.append(file_path)

        # Validate batch
        results = hook_validator.validate_batch(file_paths)

        # Check that good files are still validated correctly despite bad files
        assert len(results) == 5

        good_results = [r for r in results if "good" in r.file_path]
        bad_results = [r for r in results if "bad" in r.file_path]

        assert len(good_results) == 3
        assert len(bad_results) == 2

        # All good files should be valid
        assert all(r.is_valid for r in good_results)

        # All bad files should be invalid
        assert all(not r.is_valid for r in bad_results)


class TestErrorRecoveryWorkflows:
    """Test error recovery and graceful degradation in workflows."""

    def test_partial_directory_access_failure(self, temp_dir):
        """Test workflow when some directories are inaccessible."""
        # Create test structure
        accessible_dir = temp_dir / "accessible"
        accessible_dir.mkdir()
        (accessible_dir / "file1.json").write_text('{"test": 1}')

        restricted_dir = temp_dir / "restricted"
        restricted_dir.mkdir()
        (restricted_dir / "file2.json").write_text('{"test": 2}')

        # Mock permission error for restricted directory
        original_glob = Path.glob

        def mock_glob(self, pattern):
            if "restricted" in str(self):
                raise PermissionError("Permission denied")
            return original_glob(self, pattern)

        scanner = DirectoryScanner()

        with patch.object(Path, "glob", mock_glob):
            # Should handle permission error gracefully
            discovered_files = list(scanner.scan_directory(temp_dir, recursive=True))

            # Should still find files in accessible directory
            file_names = [f.name for f in discovered_files]
            assert "file1.json" in file_names

    def test_validation_with_corrupted_files(self, temp_dir):
        """Test validation workflow with corrupted files."""
        # Create test files
        test_dir = temp_dir / "corruption_test"
        test_dir.mkdir()

        # Normal file
        normal_file = test_dir / "normal.json"
        normal_file.write_text('{"normal": true}')

        # Truncated file (simulated corruption)
        truncated_file = test_dir / "truncated.json"
        truncated_file.write_text('{"truncated":')  # Incomplete JSON

        # Binary file with .json extension
        binary_file = test_dir / "binary.json"
        binary_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")

        # Create a validator that handles these gracefully
        class RobustValidator(BaseValidator):
            def get_extension_type(self):
                return "robust"

            def validate_single(self, file_path):
                result = ValidationResult(
                    is_valid=True,
                    file_path=str(file_path),
                    extension_type=self.get_extension_type(),
                )

                try:
                    # Try to read as text first
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()

                    # Try to parse as JSON
                    try:
                        data = json.loads(content)
                        result.metadata["content_type"] = "json"
                        result.metadata["keys"] = (
                            list(data.keys()) if isinstance(data, dict) else []
                        )
                    except json.JSONDecodeError as e:
                        result.add_error(
                            "JSON_PARSE_ERROR",
                            f"Failed to parse JSON: {e.msg}",
                            line_number=getattr(e, "lineno", None),
                            suggestion="Check JSON syntax",
                        )
                        result.metadata["content_type"] = "text"

                except UnicodeDecodeError:
                    result.add_error(
                        "ENCODING_ERROR",
                        "File contains binary data or unsupported encoding",
                        suggestion="Ensure file is valid text with UTF-8 encoding",
                    )
                    result.metadata["content_type"] = "binary"

                except Exception as e:
                    result.add_error(
                        "UNEXPECTED_ERROR",
                        f"Unexpected error: {e!s}",
                        suggestion="Check file accessibility and format",
                    )

                return result

            def _find_extension_files(self, directory):
                return list(directory.glob("*.json"))

        validator = RobustValidator()
        results = validator.validate_directory(test_dir)

        # Should validate all files despite corruption
        assert len(results) == 3

        # Categorize results
        valid_results = [r for r in results if r.is_valid]
        invalid_results = [r for r in results if not r.is_valid]

        # Normal file should be valid
        assert any("normal.json" in r.file_path for r in valid_results)

        # Corrupted files should be invalid but handled gracefully
        assert len(invalid_results) >= 2

        # Check that appropriate error codes are generated
        error_codes = []
        for result in invalid_results:
            error_codes.extend([error.code for error in result.errors])

        assert "JSON_PARSE_ERROR" in error_codes or "ENCODING_ERROR" in error_codes

    def test_workflow_memory_management(self, performance_directory):
        """Test that workflows handle large datasets without memory issues."""
        import gc
        import os

        import psutil

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Process large directory multiple times
        scanner = DirectoryScanner()
        file_filter = FileFilter().add_extension_filter({".txt", ".json", ".yaml"})

        for iteration in range(5):
            discovered_files = list(scanner.scan_directory(performance_directory, recursive=True))
            filtered_files = file_filter.filter_files(discovered_files)

            # Process files in batches to avoid memory buildup
            batch_size = 100
            for i in range(0, len(filtered_files), batch_size):
                batch = filtered_files[i : i + batch_size]
                # Simulate processing batch
                processed_count = len(batch)

            # Force garbage collection
            gc.collect()

        # Check memory usage hasn't grown excessively
        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory

        # Memory growth should be reasonable (less than 50MB)
        assert memory_growth < 50 * 1024 * 1024  # 50MB threshold
