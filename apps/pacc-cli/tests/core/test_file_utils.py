"""Tests for core file utilities."""

import unittest
import tempfile
import os
from pathlib import Path

from pacc.core.file_utils import (
    FilePathValidator,
    PathNormalizer,
    DirectoryScanner,
    FileFilter
)


class TestFilePathValidator(unittest.TestCase):
    """Test cases for FilePathValidator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = FilePathValidator()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_file = Path(self.temp_dir) / "test.txt"
        self.temp_file.write_text("test content")
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.temp_file.exists():
            self.temp_file.unlink()
        os.rmdir(self.temp_dir)
    
    def test_valid_file_path(self):
        """Test validation of valid file path."""
        self.assertTrue(self.validator.is_valid_path(self.temp_file))
    
    def test_invalid_file_path(self):
        """Test validation of invalid file path."""
        invalid_path = Path(self.temp_dir) / "nonexistent.txt"
        self.assertFalse(self.validator.is_valid_path(invalid_path))
    
    def test_directory_traversal_detection(self):
        """Test detection of directory traversal attempts."""
        traversal_path = "../../../etc/passwd"
        self.assertFalse(self.validator.is_valid_path(traversal_path))
    
    def test_extension_validation(self):
        """Test file extension validation."""
        json_validator = FilePathValidator(allowed_extensions={'.json', '.txt'})
        self.assertTrue(json_validator.validate_extension(self.temp_file, {'.txt'}))
        self.assertFalse(json_validator.validate_extension(self.temp_file, {'.json'}))
    
    def test_safe_directory_check(self):
        """Test safe directory validation."""
        self.assertTrue(self.validator.is_safe_directory(self.temp_dir))
        self.assertFalse(self.validator.is_safe_directory("/nonexistent"))


class TestPathNormalizer(unittest.TestCase):
    """Test cases for PathNormalizer."""
    
    def test_normalize_path(self):
        """Test path normalization."""
        path = PathNormalizer.normalize("./test/../file.txt")
        self.assertIsInstance(path, Path)
    
    def test_to_posix(self):
        """Test conversion to POSIX format."""
        posix_path = PathNormalizer.to_posix("test/file.txt")
        self.assertEqual(posix_path, "test/file.txt")
    
    def test_relative_to(self):
        """Test relative path calculation."""
        base = Path("/home/user")
        target = Path("/home/user/projects/test")
        relative = PathNormalizer.relative_to(target, base)
        self.assertEqual(str(relative), "projects/test")


class TestDirectoryScanner(unittest.TestCase):
    """Test cases for DirectoryScanner."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.scanner = DirectoryScanner()
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test files
        (Path(self.temp_dir) / "test1.txt").write_text("content1")
        (Path(self.temp_dir) / "test2.json").write_text('{"test": true}')
        
        # Create subdirectory with file
        sub_dir = Path(self.temp_dir) / "subdir"
        sub_dir.mkdir()
        (sub_dir / "test3.yaml").write_text("test: value")
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_scan_directory_non_recursive(self):
        """Test non-recursive directory scanning."""
        files = list(self.scanner.scan_directory(self.temp_dir, recursive=False))
        file_names = [f.name for f in files]
        self.assertIn("test1.txt", file_names)
        self.assertIn("test2.json", file_names)
        self.assertNotIn("test3.yaml", file_names)  # Should not find subdirectory files
    
    def test_scan_directory_recursive(self):
        """Test recursive directory scanning."""
        files = list(self.scanner.scan_directory(self.temp_dir, recursive=True))
        file_names = [f.name for f in files]
        self.assertIn("test1.txt", file_names)
        self.assertIn("test2.json", file_names)
        self.assertIn("test3.yaml", file_names)  # Should find subdirectory files
    
    def test_find_files_by_extension(self):
        """Test finding files by extension."""
        json_files = self.scanner.find_files_by_extension(
            self.temp_dir, {'.json'}, recursive=True
        )
        self.assertEqual(len(json_files), 1)
        self.assertEqual(json_files[0].name, "test2.json")
    
    def test_get_directory_stats(self):
        """Test directory statistics."""
        stats = self.scanner.get_directory_stats(self.temp_dir)
        self.assertEqual(stats['total_files'], 3)
        self.assertIn('.txt', stats['extensions'])
        self.assertIn('.json', stats['extensions'])
        self.assertIn('.yaml', stats['extensions'])


class TestFileFilter(unittest.TestCase):
    """Test cases for FileFilter."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.filter = FileFilter()
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test files
        self.files = [
            Path(self.temp_dir) / "test1.txt",
            Path(self.temp_dir) / "test2.json", 
            Path(self.temp_dir) / "large.txt",
            Path(self.temp_dir) / ".hidden.txt"
        ]
        
        self.files[0].write_text("small content")
        self.files[1].write_text('{"test": true}')
        self.files[2].write_text("x" * 1000)  # Large file
        self.files[3].write_text("hidden content")
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_extension_filter(self):
        """Test extension filtering."""
        filtered = self.filter.add_extension_filter({'.txt'}).filter_files(self.files)
        txt_files = [f for f in filtered if f.suffix == '.txt']
        self.assertEqual(len(txt_files), 3)  # test1.txt, large.txt, .hidden.txt
    
    def test_pattern_filter(self):
        """Test pattern filtering."""
        filtered = self.filter.clear_filters().add_pattern_filter(['test*']).filter_files(self.files)
        test_files = [f for f in filtered if f.name.startswith('test')]
        self.assertEqual(len(test_files), 2)  # test1.txt, test2.json
    
    def test_size_filter(self):
        """Test size filtering."""
        filtered = self.filter.clear_filters().add_size_filter(min_size=500).filter_files(self.files)
        large_files = [f for f in filtered if f.stat().st_size >= 500]
        self.assertEqual(len(large_files), 1)  # large.txt
    
    def test_exclude_hidden_filter(self):
        """Test hidden file exclusion."""
        filtered = self.filter.clear_filters().add_exclude_hidden().filter_files(self.files)
        visible_files = [f for f in filtered if not f.name.startswith('.')]
        self.assertEqual(len(visible_files), 3)  # Excludes .hidden.txt
    
    def test_combined_filters(self):
        """Test combining multiple filters."""
        filtered = (self.filter.clear_filters()
                   .add_extension_filter({'.txt'})
                   .add_exclude_hidden()
                   .filter_files(self.files))
        result = [f for f in filtered if f.suffix == '.txt' and not f.name.startswith('.')]
        self.assertEqual(len(result), 2)  # test1.txt, large.txt


if __name__ == '__main__':
    unittest.main()