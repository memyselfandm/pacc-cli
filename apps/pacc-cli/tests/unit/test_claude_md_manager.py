"""Tests for CLAUDEmdManager."""

import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

from pacc.fragments.claude_md_manager import CLAUDEmdManager
from pacc.errors.exceptions import FileSystemError, ValidationError, SecurityError


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def manager(temp_dir):
    """Create a CLAUDEmdManager instance for testing."""
    return CLAUDEmdManager(project_root=temp_dir)

@pytest.fixture
def sample_claude_md(temp_dir):
    """Create a sample CLAUDE.md file."""
    claude_file = temp_dir / "CLAUDE.md"
    content = """# My Project

This is my project documentation.

<!-- PACC:config:START -->
Some configuration content
<!-- PACC:config:END -->

More documentation here.

<!-- PACC:hooks:START -->
Hook configuration
<!-- PACC:hooks:END -->

End of file.
"""
    claude_file.write_text(content, encoding='utf-8')
    return claude_file


class TestCLAUDEmdManager:
    """Test suite for CLAUDEmdManager."""
    pass


class TestInitialization:
    """Test CLAUDEmdManager initialization."""
    
    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        manager = CLAUDEmdManager()
        assert manager.project_root == Path.cwd().resolve()
        assert manager.backup_dir == manager.project_root / '.pacc' / 'backups'
        assert manager.backup_dir.exists()
    
    def test_init_with_custom_paths(self, temp_dir):
        """Test initialization with custom paths."""
        backup_dir = temp_dir / 'custom_backups'
        manager = CLAUDEmdManager(project_root=temp_dir, backup_dir=backup_dir)
        
        assert manager.project_root == temp_dir.resolve()
        # Handle macOS symlink resolution differences
        assert str(manager.backup_dir).endswith(str(backup_dir.name))
        assert manager.backup_dir.exists()


class TestPathMethods:
    """Test path-related methods."""
    
    def test_get_project_claude_md(self, manager, temp_dir):
        """Test getting project CLAUDE.md path."""
        result = manager.get_project_claude_md()
        assert result.name == 'CLAUDE.md'
        assert str(result).endswith('CLAUDE.md')
    
    def test_get_user_claude_md(self, manager):
        """Test getting user CLAUDE.md path."""
        expected = Path.home() / '.claude' / 'CLAUDE.md'
        assert manager.get_user_claude_md() == expected


class TestSectionValidation:
    """Test section name validation."""
    
    def test_valid_section_names(self, manager):
        """Test valid section names."""
        valid_names = [
            'config',
            'my-section',
            'my_section',
            'section.name',
            'Section123',
            'a',
            'A1-B2_C3.D4'
        ]
        
        for name in valid_names:
            # Should not raise
            manager._validate_section_name(name)
    
    def test_invalid_section_names(self, manager):
        """Test invalid section names."""
        invalid_names = [
            '',
            None,
            'section with spaces',
            'section/with/slashes',
            'section\\with\\backslashes',
            'section:with:colons',
            'section<with>brackets',
            'a' * 101,  # Too long
        ]
        
        for name in invalid_names:
            with pytest.raises(ValidationError):
                manager._validate_section_name(name)


class TestReferenceResolution:
    """Test @reference path resolution."""
    
    def test_resolve_absolute_path(self, manager, temp_dir):
        """Test resolving absolute paths."""
        ref_file = temp_dir / 'reference.md'
        ref_file.write_text("Reference content", encoding='utf-8')
        
        base_file = temp_dir / 'CLAUDE.md'
        resolved = manager._resolve_reference_path(str(ref_file), base_file)
        
        assert resolved == ref_file.resolve()
    
    def test_resolve_home_path(self, manager, temp_dir):
        """Test resolving home directory paths."""
        base_file = temp_dir / 'CLAUDE.md'
        
        with patch('pathlib.Path.home') as mock_home:
            mock_home.return_value = temp_dir
            ref_file = temp_dir / 'test.md'
            ref_file.write_text("Test content", encoding='utf-8')
            
            resolved = manager._resolve_reference_path('~/test.md', base_file)
            assert resolved == ref_file.resolve()
    
    def test_resolve_relative_path(self, manager, temp_dir):
        """Test resolving relative paths."""
        subdir = temp_dir / 'subdir'
        subdir.mkdir()
        ref_file = subdir / 'reference.md'
        ref_file.write_text("Reference content", encoding='utf-8')
        
        base_file = temp_dir / 'CLAUDE.md'
        resolved = manager._resolve_reference_path('subdir/reference.md', base_file)
        
        assert resolved == ref_file.resolve()
    
    def test_resolve_invalid_path(self, manager, temp_dir):
        """Test resolving invalid paths."""
        base_file = temp_dir / 'CLAUDE.md'
        
        with pytest.raises(ValidationError):
            manager._resolve_reference_path('nonexistent/file.md', base_file)
    
    def test_resolve_traversal_attempt(self, manager, temp_dir):
        """Test security check for directory traversal."""
        base_file = temp_dir / 'CLAUDE.md'
        
        with pytest.raises((SecurityError, ValidationError)):
            manager._resolve_reference_path('../../etc/passwd', base_file)


class TestFileOperations:
    """Test basic file operations."""
    
    def test_read_existing_file(self, manager, sample_claude_md):
        """Test reading an existing file."""
        content = manager.read_file_content(sample_claude_md)
        assert 'My Project' in content
        assert 'PACC:config:START' in content
    
    def test_read_nonexistent_file(self, manager, temp_dir):
        """Test reading a non-existent file."""
        nonexistent = temp_dir / 'nonexistent.md'
        content = manager.read_file_content(nonexistent)
        assert content == ""
    
    def test_read_file_with_unicode(self, manager, temp_dir):
        """Test reading file with unicode content."""
        unicode_file = temp_dir / 'unicode.md'
        unicode_content = "# Project 🚀\n\nThis has émojis and spëcial chars."
        unicode_file.write_text(unicode_content, encoding='utf-8')
        
        content = manager.read_file_content(unicode_file)
        assert content == unicode_content


class TestSectionOperations:
    """Test section management operations."""
    
    def test_get_existing_section(self, manager, sample_claude_md):
        """Test getting content of existing section."""
        content = manager.get_section_content(sample_claude_md, 'config')
        assert content == "Some configuration content"
    
    def test_get_nonexistent_section(self, manager, sample_claude_md):
        """Test getting content of non-existent section."""
        content = manager.get_section_content(sample_claude_md, 'nonexistent')
        assert content is None
    
    def test_list_sections(self, manager, sample_claude_md):
        """Test listing all sections in a file."""
        sections = manager.list_sections(sample_claude_md)
        assert set(sections) == {'config', 'hooks'}
    
    def test_list_sections_empty_file(self, manager, temp_dir):
        """Test listing sections in empty file."""
        empty_file = temp_dir / 'empty.md'
        empty_file.write_text("", encoding='utf-8')
        
        sections = manager.list_sections(empty_file)
        assert sections == []
    
    def test_update_existing_section(self, manager, sample_claude_md):
        """Test updating an existing section."""
        new_content = "Updated configuration content"
        result = manager.update_section(sample_claude_md, 'config', new_content)
        
        assert result is True
        updated_content = manager.get_section_content(sample_claude_md, 'config')
        assert updated_content == new_content
    
    def test_update_section_no_change(self, manager, sample_claude_md):
        """Test updating section with same content."""
        original_content = manager.get_section_content(sample_claude_md, 'config')
        result = manager.update_section(sample_claude_md, 'config', original_content)
        
        assert result is False  # No changes made
    
    def test_create_new_section(self, manager, sample_claude_md):
        """Test creating a new section."""
        new_content = "New section content"
        result = manager.update_section(sample_claude_md, 'newsection', new_content)
        
        assert result is True
        sections = manager.list_sections(sample_claude_md)
        assert 'newsection' in sections
        
        content = manager.get_section_content(sample_claude_md, 'newsection')
        assert content == new_content
    
    def test_create_section_in_new_file(self, manager, temp_dir):
        """Test creating section in a new file."""
        new_file = temp_dir / 'newfile.md'
        new_content = "First section content"
        
        result = manager.update_section(new_file, 'first', new_content)
        
        assert result is True
        assert new_file.exists()
        
        content = manager.get_section_content(new_file, 'first')
        assert content == new_content
    
    def test_remove_existing_section(self, manager, sample_claude_md):
        """Test removing an existing section."""
        result = manager.remove_section(sample_claude_md, 'config')
        
        assert result is True
        sections = manager.list_sections(sample_claude_md)
        assert 'config' not in sections
        assert 'hooks' in sections  # Other sections remain
    
    def test_remove_nonexistent_section(self, manager, sample_claude_md):
        """Test removing a non-existent section."""
        result = manager.remove_section(sample_claude_md, 'nonexistent')
        assert result is False
    
    def test_remove_section_from_nonexistent_file(self, manager, temp_dir):
        """Test removing section from non-existent file."""
        nonexistent = temp_dir / 'nonexistent.md'
        result = manager.remove_section(nonexistent, 'anysection')
        assert result is False


class TestReferenceProcessing:
    """Test @reference directive processing."""
    
    def test_resolve_single_reference(self, manager, temp_dir):
        """Test resolving a single @reference."""
        # Create reference file
        ref_file = temp_dir / 'ref.md'
        ref_file.write_text("Referenced content", encoding='utf-8')
        
        # Create content with reference
        base_file = temp_dir / 'CLAUDE.md'
        content = f"@{ref_file}\n\nOther content"
        
        resolved = manager.resolve_references(content, base_file)
        
        assert "Referenced content" in resolved
        assert f"Reference: {ref_file}" in resolved
        assert "Other content" in resolved
    
    def test_resolve_multiple_references(self, manager, temp_dir):
        """Test resolving multiple @references."""
        # Create reference files
        ref1 = temp_dir / 'ref1.md'
        ref1.write_text("First reference", encoding='utf-8')
        
        ref2 = temp_dir / 'ref2.md'
        ref2.write_text("Second reference", encoding='utf-8')
        
        base_file = temp_dir / 'CLAUDE.md'
        content = f"@{ref1}\n\nMiddle content\n\n@{ref2}"
        
        resolved = manager.resolve_references(content, base_file)
        
        assert "First reference" in resolved
        assert "Second reference" in resolved
        assert "Middle content" in resolved
    
    def test_resolve_reference_with_description(self, manager, temp_dir):
        """Test resolving @reference with description."""
        ref_file = temp_dir / 'ref.md'
        ref_file.write_text("Referenced content", encoding='utf-8')
        
        base_file = temp_dir / 'CLAUDE.md'
        content = f"@{ref_file} This is a description"
        
        resolved = manager.resolve_references(content, base_file)
        
        assert "Referenced content" in resolved
        assert "This is a description" in resolved
    
    def test_resolve_nonexistent_reference(self, manager, temp_dir):
        """Test resolving non-existent @reference."""
        base_file = temp_dir / 'CLAUDE.md'
        content = "@nonexistent/file.md"
        
        resolved = manager.resolve_references(content, base_file)
        
        assert "Reference not found or empty" in resolved or "Reference error" in resolved
    
    def test_update_section_with_references(self, manager, temp_dir):
        """Test updating section with @reference resolution."""
        # Create reference file
        ref_file = temp_dir / 'config.md'
        ref_file.write_text("Config from reference", encoding='utf-8')
        
        claude_file = temp_dir / 'CLAUDE.md'
        content = f"@{ref_file}\n\nAdditional config"
        
        result = manager.update_section_with_references(claude_file, 'config', content)
        
        assert result is True
        
        # Check that reference was resolved
        section_content = manager.get_section_content(claude_file, 'config')
        assert "Config from reference" in section_content
        assert "Additional config" in section_content
        assert f"Reference: {ref_file}" in section_content


class TestAtomicOperations:
    """Test atomic file operations and rollback."""
    
    def test_atomic_operation_success(self, manager, temp_dir):
        """Test successful atomic operation."""
        test_file = temp_dir / 'test.md'
        original_content = "Original content"
        test_file.write_text(original_content, encoding='utf-8')
        
        new_content = "Updated content"
        manager.update_section(test_file, 'testsection', new_content)
        
        # File should be updated
        content = manager.read_file_content(test_file)
        assert 'testsection' in content
        assert new_content in content
        
        # Should have backup
        backups = manager.get_backup_files(test_file)
        assert len(backups) >= 1
    
    def test_atomic_operation_rollback(self, manager, temp_dir):
        """Test rollback on failed atomic operation."""
        test_file = temp_dir / 'test.md'
        original_content = "Original content"
        test_file.write_text(original_content, encoding='utf-8')
        
        # Mock a failure during temp file write (not backup creation)
        original_open = open
        def mock_open_selective(*args, **kwargs):
            # Only fail for temp files (those with .tmp in the name)
            if len(args) > 0 and '.tmp' in str(args[0]) and 'w' in str(args[1] if len(args) > 1 else kwargs.get('mode', '')):
                raise OSError("Simulated disk full")
            return original_open(*args, **kwargs)
        
        with patch('builtins.open', side_effect=mock_open_selective):
            with pytest.raises(FileSystemError):
                manager.update_section(test_file, 'testsection', "New content")
        
        # Original file should be intact
        content = manager.read_file_content(test_file)
        assert content == original_content
    
    def test_backup_creation(self, manager, temp_dir):
        """Test backup file creation."""
        test_file = temp_dir / 'test.md'
        test_file.write_text("Original content", encoding='utf-8')
        
        # Perform multiple updates
        manager.update_section(test_file, 'section1', "Content 1")
        manager.update_section(test_file, 'section2', "Content 2")
        
        backups = manager.get_backup_files(test_file)
        assert len(backups) >= 2
        
        # Backups should be sorted by newest first
        for i in range(len(backups) - 1):
            assert backups[i].stat().st_mtime >= backups[i + 1].stat().st_mtime
    
    def test_restore_from_backup(self, manager, temp_dir):
        """Test restoring from backup."""
        test_file = temp_dir / 'test.md'
        original_content = "Original content"
        test_file.write_text(original_content, encoding='utf-8')
        
        # Make changes
        manager.update_section(test_file, 'testsection', "Modified content")
        
        # Restore from backup
        result = manager.restore_from_backup(test_file)
        assert result is True
        
        # File should be restored
        content = manager.read_file_content(test_file)
        assert content == original_content
    
    def test_restore_from_specific_backup(self, manager, temp_dir):
        """Test restoring from a specific backup."""
        test_file = temp_dir / 'test.md'
        test_file.write_text("Version 1", encoding='utf-8')
        
        # Make multiple changes
        manager.update_section(test_file, 'section', "Version 2")
        backups_after_v2 = manager.get_backup_files(test_file)
        
        manager.update_section(test_file, 'section', "Version 3")
        
        # Restore from specific backup (Version 1)
        v1_backup = backups_after_v2[0]  # Most recent backup after v2 = v1 content
        result = manager.restore_from_backup(test_file, v1_backup)
        assert result is True
        
        content = manager.read_file_content(test_file)
        assert "Version 1" in content
    
    def test_cleanup_old_backups(self, manager, temp_dir):
        """Test cleaning up old backup files."""
        test_file = temp_dir / 'test.md'
        test_file.write_text("Content", encoding='utf-8')
        
        # Create many backups
        for i in range(15):
            manager.update_section(test_file, 'section', f"Content {i}")
            time.sleep(0.01)  # Ensure different timestamps
        
        # Clean up, keeping only 5
        removed = manager.cleanup_old_backups(max_backups=5)
        assert removed >= 10
        
        # Should have only 5 backups left
        remaining_backups = manager.get_backup_files(test_file)
        assert len(remaining_backups) <= 5


class TestThreadSafety:
    """Test thread safety of operations."""
    
    def test_concurrent_section_updates(self, manager, temp_dir):
        """Test concurrent updates to different sections."""
        test_file = temp_dir / 'test.md'
        test_file.write_text("Initial content", encoding='utf-8')
        
        results = []
        exceptions = []
        
        def update_section(section_name, content):
            try:
                result = manager.update_section(test_file, section_name, content)
                results.append((section_name, result))
            except Exception as e:
                exceptions.append((section_name, e))
        
        # Create multiple threads updating different sections
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=update_section,
                args=(f'section{i}', f'Content {i}')
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        assert len(results) == 10
        
        # Verify all sections were created
        sections = manager.list_sections(test_file)
        expected_sections = {f'section{i}' for i in range(10)}
        assert set(sections) == expected_sections
    
    def test_concurrent_same_section_updates(self, manager, temp_dir):
        """Test concurrent updates to the same section."""
        test_file = temp_dir / 'test.md'
        test_file.write_text("Initial content", encoding='utf-8')
        
        results = []
        exceptions = []
        
        def update_same_section(thread_id):
            try:
                result = manager.update_section(
                    test_file, 
                    'shared_section', 
                    f'Content from thread {thread_id}'
                )
                results.append((thread_id, result))
            except Exception as e:
                exceptions.append((thread_id, e))
        
        # Create multiple threads updating the same section
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_same_section, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should have no exceptions due to proper locking
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        
        # Section should exist and have content from one of the threads
        content = manager.get_section_content(test_file, 'shared_section')
        assert content is not None
        assert 'Content from thread' in content


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_malformed_section_markers(self, manager, temp_dir):
        """Test handling of malformed section markers."""
        test_file = temp_dir / 'malformed.md'
        malformed_content = """
# Test

<!-- PACC:config:START -->
Some content
<!-- Missing end marker -->

More content
"""
        test_file.write_text(malformed_content, encoding='utf-8')
        
        with pytest.raises((ValidationError, FileSystemError), match="no end marker"):
            manager.update_section(test_file, 'config', "New content")
    
    def test_empty_section_content(self, manager, temp_dir):
        """Test handling empty section content."""
        test_file = temp_dir / 'test.md'
        
        # Create section with empty content
        result = manager.update_section(test_file, 'empty', "")
        assert result is True
        
        # Should be able to retrieve empty content (returns empty string or None)
        content = manager.get_section_content(test_file, 'empty')
        assert content == "" or content is None
    
    def test_section_with_only_whitespace(self, manager, temp_dir):
        """Test handling section with only whitespace."""
        test_file = temp_dir / 'test.md'
        
        # Create section with whitespace
        result = manager.update_section(test_file, 'whitespace', "   \n  \t  \n   ")
        assert result is True
        
        # Should be stripped to empty (returns empty string or None)
        content = manager.get_section_content(test_file, 'whitespace')
        assert content == "" or content is None
    
    def test_very_large_section_content(self, manager, temp_dir):
        """Test handling very large section content."""
        test_file = temp_dir / 'test.md'
        
        # Create large content (1MB)
        large_content = "A" * 1024 * 1024
        
        result = manager.update_section(test_file, 'large', large_content)
        assert result is True
        
        retrieved_content = manager.get_section_content(test_file, 'large')
        assert retrieved_content == large_content
    
    def test_special_characters_in_content(self, manager, temp_dir):
        """Test handling special characters in content."""
        test_file = temp_dir / 'test.md'
        
        special_content = """
Special chars: !@#$%^&*()
Unicode: 🚀 émoji and spëcial
HTML: <div>content</div>
XML: <?xml version="1.0"?>
Markdown: **bold** *italic* `code`
<!-- Comments -->
"""
        
        result = manager.update_section(test_file, 'special', special_content)
        assert result is True
        
        retrieved_content = manager.get_section_content(test_file, 'special')
        assert retrieved_content.strip() == special_content.strip()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])