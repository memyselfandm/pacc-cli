"""Unit tests for pacc.core.file_utils module."""

import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pacc.core.file_utils import DirectoryScanner, FileFilter, FilePathValidator, PathNormalizer


class TestFilePathValidator:
    """Test FilePathValidator class functionality."""

    def test_init_default(self):
        """Test FilePathValidator initialization with default values."""
        validator = FilePathValidator()
        assert validator.allowed_extensions == set()

    def test_init_with_extensions(self):
        """Test FilePathValidator initialization with allowed extensions."""
        extensions = {".json", ".yaml", ".md"}
        validator = FilePathValidator(allowed_extensions=extensions)
        assert validator.allowed_extensions == extensions

    def test_is_valid_path_existing_file(self, temp_dir):
        """Test validation of existing files."""
        validator = FilePathValidator()
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        assert validator.is_valid_path(test_file) is True
        assert validator.is_valid_path(str(test_file)) is True

    def test_is_valid_path_nonexistent_file(self, temp_dir):
        """Test validation of non-existent files."""
        validator = FilePathValidator()
        nonexistent_file = temp_dir / "nonexistent.txt"

        assert validator.is_valid_path(nonexistent_file) is False

    def test_is_valid_path_directory_traversal(self, temp_dir):
        """Test detection of directory traversal attempts."""
        validator = FilePathValidator()

        # Create a file outside temp_dir
        outside_file = temp_dir.parent / "outside.txt"
        outside_file.write_text("outside content")

        # Test various traversal patterns
        traversal_paths = ["../outside.txt", "subdir/../outside.txt", "./../../outside.txt"]

        for path in traversal_paths:
            assert validator.is_valid_path(path) is False

    def test_is_valid_path_permission_denied(self, temp_dir):
        """Test handling of permission denied errors."""
        validator = FilePathValidator()
        test_file = temp_dir / "no_access.txt"
        test_file.write_text("test content")

        with patch("os.access", return_value=False):
            assert validator.is_valid_path(test_file) is False

    def test_is_valid_path_with_extension_restrictions(self, temp_dir):
        """Test path validation with extension restrictions."""
        allowed_extensions = {".json", ".yaml"}
        validator = FilePathValidator(allowed_extensions=allowed_extensions)

        # Create test files
        json_file = temp_dir / "test.json"
        txt_file = temp_dir / "test.txt"
        json_file.write_text('{"test": true}')
        txt_file.write_text("test content")

        assert validator.is_valid_path(json_file) is True
        assert validator.is_valid_path(txt_file) is False

    def test_is_valid_path_directory_with_restrictions(self, temp_dir):
        """Test that directories pass validation even with extension restrictions."""
        allowed_extensions = {".json"}
        validator = FilePathValidator(allowed_extensions=allowed_extensions)

        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        assert validator.is_valid_path(test_dir) is True

    def test_is_valid_path_os_error(self, temp_dir):
        """Test handling of OS errors during validation."""
        validator = FilePathValidator()
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        with patch("pathlib.Path.resolve", side_effect=OSError("Test OS error")):
            assert validator.is_valid_path(test_file) is False

    def test_validate_extension_valid(self, temp_dir):
        """Test extension validation with valid extensions."""
        validator = FilePathValidator()
        test_file = temp_dir / "test.json"

        assert validator.validate_extension(test_file, {".json", ".yaml"}) is True
        assert validator.validate_extension(str(test_file), {".json", ".yaml"}) is True

    def test_validate_extension_invalid(self, temp_dir):
        """Test extension validation with invalid extensions."""
        validator = FilePathValidator()
        test_file = temp_dir / "test.txt"

        assert validator.validate_extension(test_file, {".json", ".yaml"}) is False

    def test_validate_extension_case_insensitive(self, temp_dir):
        """Test that extension validation is case insensitive."""
        validator = FilePathValidator()
        test_file = temp_dir / "test.JSON"

        assert validator.validate_extension(test_file, {".json"}) is True

    def test_is_safe_directory_valid(self, temp_dir):
        """Test validation of safe directories."""
        validator = FilePathValidator()
        test_dir = temp_dir / "safe_dir"
        test_dir.mkdir()

        assert validator.is_safe_directory(test_dir) is True

    def test_is_safe_directory_nonexistent(self, temp_dir):
        """Test validation of non-existent directories."""
        validator = FilePathValidator()
        nonexistent_dir = temp_dir / "nonexistent"

        assert validator.is_safe_directory(nonexistent_dir) is False

    def test_is_safe_directory_file_not_dir(self, temp_dir):
        """Test validation when path is file, not directory."""
        validator = FilePathValidator()
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        assert validator.is_safe_directory(test_file) is False

    def test_is_safe_directory_permission_denied(self, temp_dir):
        """Test handling of permission denied for directories."""
        validator = FilePathValidator()
        test_dir = temp_dir / "no_access"
        test_dir.mkdir()

        with patch("os.access", return_value=False):
            assert validator.is_safe_directory(test_dir) is False

    @pytest.mark.skipif(os.name == "nt", reason="Unix-specific system directory test")
    def test_is_safe_directory_system_dirs(self):
        """Test rejection of system directories on Unix systems."""
        validator = FilePathValidator()

        system_dirs = ["/proc", "/sys", "/dev", "/etc"]
        for sys_dir in system_dirs:
            assert validator.is_safe_directory(sys_dir) is False

    def test_is_safe_directory_os_error(self, temp_dir):
        """Test handling of OS errors in directory validation."""
        validator = FilePathValidator()
        test_dir = temp_dir / "test_dir"
        test_dir.mkdir()

        with patch("pathlib.Path.resolve", side_effect=OSError("Test OS error")):
            assert validator.is_safe_directory(test_dir) is False


class TestPathNormalizer:
    """Test PathNormalizer class functionality."""

    def test_normalize_basic_path(self, temp_dir):
        """Test basic path normalization."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test")

        normalized = PathNormalizer.normalize(test_file)
        assert normalized.is_absolute()
        assert normalized.exists()

    def test_normalize_relative_path(self, temp_dir):
        """Test normalization of relative paths."""
        with patch("pathlib.Path.cwd", return_value=temp_dir):
            relative_path = "./test.txt"
            normalized = PathNormalizer.normalize(relative_path)
            assert normalized.is_absolute()

    def test_normalize_string_path(self, temp_dir):
        """Test normalization of string paths."""
        test_path = str(temp_dir / "test.txt")
        normalized = PathNormalizer.normalize(test_path)
        assert isinstance(normalized, Path)

    def test_to_posix_unix_path(self):
        """Test conversion to POSIX format from Unix path."""
        unix_path = "/home/user/file.txt"
        posix_path = PathNormalizer.to_posix(unix_path)
        assert posix_path == "/home/user/file.txt"

    def test_to_posix_windows_path(self):
        """Test conversion to POSIX format from Windows path."""
        windows_path = r"C:\Users\user\file.txt"
        posix_path = PathNormalizer.to_posix(windows_path)
        # Should convert backslashes to forward slashes
        assert "/" in posix_path
        assert "\\" not in posix_path

    def test_relative_to_valid_base(self, temp_dir):
        """Test relative path calculation with valid base."""
        base_dir = temp_dir / "base"
        target_file = base_dir / "subdir" / "file.txt"
        base_dir.mkdir()
        (base_dir / "subdir").mkdir()
        target_file.write_text("test")

        relative = PathNormalizer.relative_to(target_file, base_dir)
        assert str(relative) == "subdir/file.txt" or str(relative) == "subdir\\file.txt"

    def test_relative_to_invalid_base(self, temp_dir):
        """Test relative path calculation with invalid base."""
        target_file = temp_dir / "file.txt"
        unrelated_dir = temp_dir / "unrelated"
        target_file.write_text("test")
        unrelated_dir.mkdir()

        # When paths are not relative, should return absolute path
        result = PathNormalizer.relative_to(target_file, unrelated_dir)
        assert result.is_absolute()

    def test_ensure_directory_new(self, temp_dir):
        """Test ensuring a new directory exists."""
        new_dir = temp_dir / "new" / "nested" / "dir"

        result = PathNormalizer.ensure_directory(new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()
        assert result == new_dir

    def test_ensure_directory_existing(self, temp_dir):
        """Test ensuring an existing directory exists."""
        existing_dir = temp_dir / "existing"
        existing_dir.mkdir()

        result = PathNormalizer.ensure_directory(existing_dir)
        assert existing_dir.exists()
        assert result == existing_dir


class TestDirectoryScanner:
    """Test DirectoryScanner class functionality."""

    def test_init_default(self):
        """Test DirectoryScanner initialization with default validator."""
        scanner = DirectoryScanner()
        assert isinstance(scanner.validator, FilePathValidator)

    def test_init_with_validator(self):
        """Test DirectoryScanner initialization with custom validator."""
        custom_validator = FilePathValidator(allowed_extensions={".json"})
        scanner = DirectoryScanner(validator=custom_validator)
        assert scanner.validator is custom_validator

    def test_scan_directory_non_recursive(self, sample_directory_structure):
        """Test non-recursive directory scanning."""
        scanner = DirectoryScanner()

        files = list(scanner.scan_directory(sample_directory_structure, recursive=False))
        file_names = [f.name for f in files]

        # Should only find files in root directory
        assert "large_file.txt" in file_names
        # Should not find files in subdirectories
        assert "sample_hook.json" not in file_names

    def test_scan_directory_recursive(self, sample_directory_structure):
        """Test recursive directory scanning."""
        scanner = DirectoryScanner()

        files = list(scanner.scan_directory(sample_directory_structure, recursive=True))
        file_names = [f.name for f in files]

        # Should find files in subdirectories
        assert "sample_hook.json" in file_names
        assert "server.yaml" in file_names
        assert "test_agent.md" in file_names
        assert "file.txt" in file_names  # from nested/deep/

    def test_scan_directory_max_depth(self, sample_directory_structure):
        """Test directory scanning with max depth limit."""
        scanner = DirectoryScanner()

        # Create deeper nesting
        deep_dir = sample_directory_structure / "level1" / "level2" / "level3"
        deep_dir.mkdir(parents=True)
        deep_file = deep_dir / "deep.txt"
        deep_file.write_text("deep content")

        # Scan with depth limit
        files = list(
            scanner.scan_directory(sample_directory_structure, recursive=True, max_depth=2)
        )
        file_paths = [str(f) for f in files]

        # Should not find files deeper than max_depth
        assert not any("level3" in path for path in file_paths)

    def test_scan_directory_unsafe_directory(self, temp_dir):
        """Test scanning of unsafe directories."""
        scanner = DirectoryScanner()

        # Mock unsafe directory
        with patch.object(scanner.validator, "is_safe_directory", return_value=False):
            files = list(scanner.scan_directory(temp_dir))
            assert len(files) == 0

    def test_scan_directory_permission_error(self, sample_directory_structure):
        """Test handling of permission errors during scanning."""
        scanner = DirectoryScanner()

        with patch("pathlib.Path.glob", side_effect=PermissionError("Permission denied")):
            files = list(scanner.scan_directory(sample_directory_structure))
            # Should handle gracefully and return empty list
            assert len(files) == 0

    def test_find_files_by_extension(self, sample_directory_structure):
        """Test finding files by extension."""
        scanner = DirectoryScanner()

        json_files = scanner.find_files_by_extension(
            sample_directory_structure, {".json"}, recursive=True
        )

        assert len(json_files) >= 1
        assert all(f.suffix == ".json" for f in json_files)
        assert any(f.name == "sample_hook.json" for f in json_files)

    def test_find_files_by_extension_non_recursive(self, sample_directory_structure):
        """Test finding files by extension non-recursively."""
        scanner = DirectoryScanner()

        # Create a JSON file in root
        root_json = sample_directory_structure / "root.json"
        root_json.write_text('{"root": true}')

        json_files = scanner.find_files_by_extension(
            sample_directory_structure, {".json"}, recursive=False
        )

        file_names = [f.name for f in json_files]
        assert "root.json" in file_names
        assert "sample_hook.json" not in file_names  # Should not find in subdirs

    def test_find_files_multiple_extensions(self, sample_directory_structure):
        """Test finding files with multiple extensions."""
        scanner = DirectoryScanner()

        files = scanner.find_files_by_extension(
            sample_directory_structure, {".json", ".yaml", ".md"}, recursive=True
        )

        extensions = {f.suffix for f in files}
        assert ".json" in extensions
        assert ".yaml" in extensions
        assert ".md" in extensions

    def test_get_directory_stats(self, sample_directory_structure):
        """Test getting directory statistics."""
        scanner = DirectoryScanner()

        stats = scanner.get_directory_stats(sample_directory_structure)

        assert isinstance(stats, dict)
        assert "total_files" in stats
        assert "total_directories" in stats
        assert "total_size" in stats
        assert "extensions" in stats

        assert stats["total_files"] > 0
        assert stats["total_size"] > 0
        assert len(stats["extensions"]) > 0

    def test_get_directory_stats_unsafe_directory(self, temp_dir):
        """Test getting stats for unsafe directory."""
        scanner = DirectoryScanner()

        with patch.object(scanner.validator, "is_safe_directory", return_value=False):
            stats = scanner.get_directory_stats(temp_dir)

            assert stats["total_files"] == 0
            assert stats["total_directories"] == 0
            assert stats["total_size"] == 0
            assert len(stats["extensions"]) == 0

    def test_get_directory_stats_permission_error(self, sample_directory_structure):
        """Test handling of permission errors in stats collection."""
        scanner = DirectoryScanner()

        with patch.object(
            scanner, "scan_directory", side_effect=PermissionError("Permission denied")
        ):
            stats = scanner.get_directory_stats(sample_directory_structure)

            # Should handle gracefully
            assert isinstance(stats, dict)
            assert stats["total_files"] == 0


class TestFileFilter:
    """Test FileFilter class functionality."""

    def test_init(self):
        """Test FileFilter initialization."""
        file_filter = FileFilter()
        assert file_filter.filters == []

    def test_add_extension_filter(self, temp_dir):
        """Test adding extension filter."""
        file_filter = FileFilter()
        file_filter.add_extension_filter({".json", ".yaml"})

        assert len(file_filter.filters) == 1

        # Test the filter works
        json_file = temp_dir / "test.json"
        txt_file = temp_dir / "test.txt"

        assert file_filter.filters[0](json_file) is True
        assert file_filter.filters[0](txt_file) is False

    def test_add_pattern_filter(self, temp_dir):
        """Test adding pattern filter."""
        file_filter = FileFilter()
        file_filter.add_pattern_filter(["test_*", "*.tmp"])

        assert len(file_filter.filters) == 1

        # Test the filter works
        matching_file1 = temp_dir / "test_file.txt"
        matching_file2 = temp_dir / "data.tmp"
        non_matching_file = temp_dir / "regular.txt"

        assert file_filter.filters[0](matching_file1) is True
        assert file_filter.filters[0](matching_file2) is True
        assert file_filter.filters[0](non_matching_file) is False

    def test_add_size_filter(self, temp_dir):
        """Test adding size filter."""
        file_filter = FileFilter()
        file_filter.add_size_filter(min_size=100, max_size=1000)

        assert len(file_filter.filters) == 1

        # Create test files with different sizes
        small_file = temp_dir / "small.txt"
        medium_file = temp_dir / "medium.txt"
        large_file = temp_dir / "large.txt"

        small_file.write_text("x" * 50)  # 50 bytes
        medium_file.write_text("x" * 500)  # 500 bytes
        large_file.write_text("x" * 2000)  # 2000 bytes

        assert file_filter.filters[0](small_file) is False  # Too small
        assert file_filter.filters[0](medium_file) is True  # Just right
        assert file_filter.filters[0](large_file) is False  # Too large

    def test_add_size_filter_no_max(self, temp_dir):
        """Test adding size filter without maximum."""
        file_filter = FileFilter()
        file_filter.add_size_filter(min_size=100)

        large_file = temp_dir / "large.txt"
        large_file.write_text("x" * 2000)

        assert file_filter.filters[0](large_file) is True

    def test_add_size_filter_os_error(self, temp_dir):
        """Test size filter handling OS errors."""
        file_filter = FileFilter()
        file_filter.add_size_filter(min_size=100)

        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        with patch("pathlib.Path.stat", side_effect=OSError("Test error")):
            assert file_filter.filters[0](test_file) is False

    def test_add_exclude_hidden_unix(self, temp_dir):
        """Test excluding hidden files on Unix-like systems."""
        file_filter = FileFilter()
        file_filter.add_exclude_hidden()

        visible_file = temp_dir / "visible.txt"
        hidden_file = temp_dir / ".hidden.txt"

        assert file_filter.filters[0](visible_file) is True
        assert file_filter.filters[0](hidden_file) is False

    @pytest.mark.skipif(os.name != "nt", reason="Windows-specific test")
    def test_add_exclude_hidden_windows(self, temp_dir):
        """Test excluding hidden files on Windows."""
        file_filter = FileFilter()
        file_filter.add_exclude_hidden()

        test_file = temp_dir / "test.txt"
        test_file.write_text("test")

        # Mock Windows hidden attribute
        mock_stat = MagicMock()
        mock_stat.st_file_attributes = stat.FILE_ATTRIBUTE_HIDDEN

        with patch("pathlib.Path.stat", return_value=mock_stat):
            assert file_filter.filters[0](test_file) is False

    def test_filter_files_no_filters(self, temp_dir):
        """Test filtering files with no filters applied."""
        file_filter = FileFilter()

        files = [temp_dir / "file1.txt", temp_dir / "file2.json", temp_dir / "file3.yaml"]

        filtered = file_filter.filter_files(files)
        assert filtered == files

    def test_filter_files_with_filters(self, temp_dir):
        """Test filtering files with multiple filters."""
        file_filter = FileFilter()
        file_filter.add_extension_filter({".json", ".yaml"})
        file_filter.add_pattern_filter(["test_*"])

        files = [
            temp_dir / "test_file.json",  # Matches both filters
            temp_dir / "test_file.txt",  # Matches pattern but not extension
            temp_dir / "other_file.json",  # Matches extension but not pattern
            temp_dir / "other_file.txt",  # Matches neither filter
        ]

        filtered = file_filter.filter_files(files)

        assert len(filtered) == 1
        assert filtered[0].name == "test_file.json"

    def test_clear_filters(self, temp_dir):
        """Test clearing all filters."""
        file_filter = FileFilter()
        file_filter.add_extension_filter({".json"})
        file_filter.add_pattern_filter(["test_*"])

        assert len(file_filter.filters) == 2

        result = file_filter.clear_filters()

        assert len(file_filter.filters) == 0
        assert result is file_filter  # Test method chaining

    def test_method_chaining(self, temp_dir):
        """Test that filter methods support chaining."""
        file_filter = FileFilter()

        result = (
            file_filter.add_extension_filter({".json"})
            .add_pattern_filter(["test_*"])
            .add_size_filter(100, 1000)
            .add_exclude_hidden()
        )

        assert result is file_filter
        assert len(file_filter.filters) == 4


# Integration tests for file utilities
class TestFileUtilsIntegration:
    """Integration tests for file utilities working together."""

    def test_validator_and_scanner_integration(self, sample_directory_structure):
        """Test FilePathValidator and DirectoryScanner working together."""
        # Create validator that only allows JSON files
        validator = FilePathValidator(allowed_extensions={".json"})
        scanner = DirectoryScanner(validator=validator)

        files = list(scanner.scan_directory(sample_directory_structure, recursive=True))

        # Should only find JSON files
        assert all(f.suffix == ".json" for f in files)
        assert any(f.name == "sample_hook.json" for f in files)

    def test_scanner_and_filter_integration(self, sample_directory_structure):
        """Test DirectoryScanner and FileFilter working together."""
        scanner = DirectoryScanner()
        file_filter = FileFilter()
        file_filter.add_extension_filter({".json", ".md"})
        file_filter.add_exclude_hidden()

        all_files = list(scanner.scan_directory(sample_directory_structure, recursive=True))
        filtered_files = file_filter.filter_files(all_files)

        # Should only have JSON and MD files, no hidden files
        assert all(f.suffix in {".json", ".md"} for f in filtered_files)
        assert all(not f.name.startswith(".") for f in filtered_files)

    def test_full_pipeline_integration(self, sample_directory_structure):
        """Test complete file processing pipeline."""
        # Setup components
        validator = FilePathValidator(allowed_extensions={".json", ".yaml", ".md"})
        scanner = DirectoryScanner(validator=validator)
        file_filter = FileFilter().add_extension_filter({".json", ".md"}).add_exclude_hidden()

        # Process directory
        all_files = list(scanner.scan_directory(sample_directory_structure, recursive=True))
        filtered_files = file_filter.filter_files(all_files)
        normalized_paths = [PathNormalizer.normalize(f) for f in filtered_files]

        # Verify results
        assert len(filtered_files) > 0
        assert all(f.suffix in {".json", ".md"} for f in filtered_files)
        assert all(p.is_absolute() for p in normalized_paths)


# Performance tests
@pytest.mark.performance
class TestFileUtilsPerformance:
    """Performance tests for file utilities."""

    def test_scanner_performance_large_directory(self, performance_directory):
        """Test scanner performance with large directory."""
        import time

        scanner = DirectoryScanner()

        start_time = time.time()
        files = list(scanner.scan_directory(performance_directory, recursive=True))
        end_time = time.time()

        duration = end_time - start_time
        files_per_second = len(files) / duration if duration > 0 else float("inf")

        # Should process at least 1000 files per second
        assert files_per_second > 1000
        assert len(files) > 1000  # Should find the test files we created

    def test_filter_performance_large_file_list(self, performance_directory):
        """Test file filter performance with large file list."""
        import time

        scanner = DirectoryScanner()
        all_files = list(scanner.scan_directory(performance_directory, recursive=True))

        file_filter = (
            FileFilter()
            .add_extension_filter({".json", ".yaml"})
            .add_size_filter(0, 10000)
            .add_exclude_hidden()
        )

        start_time = time.time()
        filtered_files = file_filter.filter_files(all_files)
        end_time = time.time()

        duration = end_time - start_time

        # Should filter files quickly (under 100ms for 1000+ files)
        assert duration < 0.1
        assert len(filtered_files) > 0
