"""Security tests for fragment management to prevent path traversal attacks."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pacc.core.file_utils import FilePathValidator
from pacc.fragments.storage_manager import FragmentStorageManager


class TestFragmentSecurityPrevention:
    """Test suite for path traversal and security vulnerabilities."""

    def setup_method(self):
        """Set up test environment."""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir) / "test_project"
        self.project_root.mkdir(parents=True)

        # Create fragment storage directories
        self.fragment_storage = self.project_root / ".claude" / "pacc" / "fragments"
        self.fragment_storage.mkdir(parents=True)

        # Create a legitimate fragment
        self.legit_fragment = self.fragment_storage / "legit_fragment.md"
        self.legit_fragment.write_text("# Legitimate Fragment\nContent here")

        # Create a file outside fragment storage (potential attack target)
        self.outside_file = self.project_root / "important.md"
        self.outside_file.write_text(
            "# Important File\nShould not be deletable via fragment commands"
        )

        # Create another outside file to test absolute path attacks
        self.temp_target = Path(self.temp_dir) / "target.md"
        self.temp_target.write_text("# Target File\nOutside project entirely")

    def teardown_method(self):
        """Clean up test environment."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_path_traversal_prevention_in_find_fragment(self):
        """Test that find_fragment prevents path traversal attacks."""
        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            storage_manager = FragmentStorageManager()

            # Test various path traversal attempts
            traversal_attempts = [
                "../../../important.md",  # Relative path traversal
                "../../important.md",  # Shorter traversal
                "../important.md",  # Single level traversal
                "/etc/passwd",  # Absolute path
                str(self.outside_file),  # Direct path to outside file
                str(self.temp_target),  # Path to temp target
                "subdir/../../../important.md",  # Traversal with subdir
                "collection/../../important.md",  # Traversal from collection
                "./../important.md",  # Dot prefix traversal
                "fragment/../../../etc/passwd",  # Complex traversal
            ]

            for attempt in traversal_attempts:
                result = storage_manager.find_fragment(attempt)
                assert result is None, f"Path traversal not blocked for: {attempt}"

    def test_fragment_remove_cannot_delete_outside_files(self):
        """Test that remove_fragment cannot delete files outside fragment storage."""
        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            storage_manager = FragmentStorageManager()

            # Ensure outside file exists
            assert self.outside_file.exists()

            # Try to remove file outside fragment storage
            success = storage_manager.remove_fragment("../../important")
            assert not success, "Should not be able to remove files outside fragment storage"

            # Verify file still exists
            assert self.outside_file.exists(), "Outside file should not be deleted"

    def test_fragment_remove_with_absolute_path_blocked(self):
        """Test that absolute paths are blocked in fragment removal."""
        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            storage_manager = FragmentStorageManager()

            # Try with absolute path
            success = storage_manager.remove_fragment(str(self.temp_target))
            assert not success, "Absolute paths should be blocked"

            # Verify target still exists
            assert self.temp_target.exists(), "Target file should not be deleted"

    def test_legitimate_fragment_operations_still_work(self):
        """Test that legitimate fragment operations are not affected."""
        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            storage_manager = FragmentStorageManager()

            # Find legitimate fragment
            found = storage_manager.find_fragment("legit_fragment")
            assert found is not None, "Should find legitimate fragment"
            # Compare resolved paths to handle symlink differences
            assert found.resolve() == self.legit_fragment.resolve()

            # Remove legitimate fragment
            success = storage_manager.remove_fragment("legit_fragment")
            assert success, "Should be able to remove legitimate fragment"
            assert not self.legit_fragment.exists(), "Fragment should be deleted"

    def test_path_validator_rejects_dangerous_paths(self):
        """Test that FilePathValidator properly rejects dangerous paths."""
        validator = FilePathValidator()

        # Test dangerous path patterns
        dangerous_paths = [
            "../etc/passwd",
            "../../secret.key",
            "/etc/shadow",
            "~/Documents/private.md",
            "/absolute/path/file.md",
            "normal/../../../etc/hosts",
        ]

        for path in dangerous_paths:
            assert not validator.is_valid_path(path), f"Should reject dangerous path: {path}"

    def test_collection_traversal_prevention(self):
        """Test that collection names cannot be used for traversal."""
        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            storage_manager = FragmentStorageManager()

            # Try to use collection parameter for traversal
            traversal_collections = [
                "../..",
                "../../..",
                "../collection",
                "/etc",
            ]

            for collection in traversal_collections:
                result = storage_manager.find_fragment(
                    "fragment", storage_type="project", collection=collection
                )
                # Should either return None or only find within proper storage
                if result:
                    assert (
                        self.fragment_storage in result.parents
                    ), f"Found fragment outside storage with collection: {collection}"

    def test_fragment_name_with_slashes_blocked(self):
        """Test that fragment names containing slashes are blocked."""
        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            storage_manager = FragmentStorageManager()

            slash_names = [
                "subdir/fragment",
                "collection/nested/fragment",
                "../fragment",
                "./hidden/fragment",
                "\\windows\\path\\fragment",  # Windows-style paths
            ]

            for name in slash_names:
                result = storage_manager.find_fragment(name)
                assert result is None, f"Should block fragment name with slashes: {name}"

    def test_symlink_traversal_prevention(self):
        """Test that symlinks cannot be used for traversal attacks."""
        # Create a symlink pointing outside fragment storage
        symlink_path = self.fragment_storage / "evil_link.md"

        try:
            symlink_path.symlink_to(self.outside_file)

            with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
                storage_manager = FragmentStorageManager()

                # Try to remove via symlink - should fail or only remove link
                storage_manager.remove_fragment("evil_link")

                # Original file should still exist
                assert self.outside_file.exists(), "Original file should not be deleted via symlink"

        except OSError:
            # Skip test if symlinks not supported (e.g., Windows without privileges)
            pytest.skip("Symlinks not supported on this system")
        finally:
            if symlink_path.exists() or symlink_path.is_symlink():
                symlink_path.unlink()

    def test_double_extension_attack_prevention(self):
        """Test that double extensions don't bypass validation."""
        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            storage_manager = FragmentStorageManager()

            # Create a file with double extension
            double_ext = self.fragment_storage / "fragment.md.md"
            double_ext.write_text("# Double Extension")

            # Should be findable with single .md
            found = storage_manager.find_fragment("fragment.md")
            assert (
                found == double_ext or found is None
            ), "Double extension handling should be consistent"

            # Clean up
            if double_ext.exists():
                double_ext.unlink()

    def test_null_byte_injection_prevention(self):
        """Test that null byte injection is prevented."""
        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            storage_manager = FragmentStorageManager()

            # Try null byte injection
            null_byte_attempts = [
                "fragment\x00.txt",
                "fragment.md\x00.exe",
                "legit_fragment\x00../../etc/passwd",
            ]

            for attempt in null_byte_attempts:
                try:
                    result = storage_manager.find_fragment(attempt)
                    # Should either handle safely or raise error
                    if result:
                        assert (
                            self.fragment_storage in result.parents
                        ), f"Null byte injection escaped storage: {attempt!r}"
                except (ValueError, TypeError):
                    # Expected - null bytes should cause errors
                    pass

    def test_case_sensitivity_attacks(self):
        """Test that case variations don't enable attacks."""
        with patch("pacc.fragments.storage_manager.Path.cwd", return_value=self.project_root):
            storage_manager = FragmentStorageManager()

            # Test case variations of traversal attempts
            case_variations = [
                "../Important.MD",
                "../IMPORTANT.md",
                "..\\Important.md",  # Windows-style with case variation
            ]

            for variation in case_variations:
                result = storage_manager.find_fragment(variation)
                assert result is None, f"Case variation should not enable traversal: {variation}"


class TestFragmentInstallSecurity:
    """Test security aspects of fragment installation."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir) / "test_project"
        self.project_root.mkdir(parents=True)

        # Create CLAUDE.md file
        self.claude_md = self.project_root / "CLAUDE.md"
        self.claude_md.write_text("# Project Instructions\n\nOriginal content\n")

    def teardown_method(self):
        """Clean up test environment."""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_fragment_install_updates_claude_md(self):
        """Test that fragment installation properly updates CLAUDE.md."""
        from pacc.fragments.installation_manager import FragmentInstallationManager

        # Create a test fragment
        test_fragment = self.project_root / "test_fragment.md"
        test_fragment.write_text("""---
title: "Test Fragment"
description: "Test fragment for installation"
---

# Test Fragment Content
This is test content.
""")

        with patch("pacc.fragments.installation_manager.Path.cwd", return_value=self.project_root):
            manager = FragmentInstallationManager()

            # Install the fragment
            result = manager.install_from_source(
                source_input=str(test_fragment),
                target_type="project",
                interactive=False,
                install_all=True,
                force=False,
                dry_run=False,
            )

            assert result.success, f"Installation should succeed: {result.error_message}"
            assert result.installed_count == 1, "Should install one fragment"

            # Check that CLAUDE.md was updated
            claude_content = self.claude_md.read_text()
            assert "PACC:fragments:START" in claude_content, "Should add fragment markers"
            assert "test_fragment.md" in claude_content, "Should reference installed fragment"
            assert "Test Fragment" in claude_content, "Should include fragment title"

    def test_fragment_install_prevents_path_injection(self):
        """Test that fragment installation prevents path injection in CLAUDE.md."""
        from pacc.fragments.installation_manager import FragmentInstallationManager

        # Create a fragment with malicious name attempt
        malicious_fragment = self.project_root / "test.md"
        malicious_fragment.write_text("""---
title: "../../../etc/passwd"
description: "Attempted path injection"
---

Content
""")

        with patch("pacc.fragments.installation_manager.Path.cwd", return_value=self.project_root):
            manager = FragmentInstallationManager()

            # Install should succeed but sanitize the reference
            result = manager.install_from_source(
                source_input=str(malicious_fragment),
                target_type="project",
                interactive=False,
                install_all=True,
                force=False,
                dry_run=False,
            )

            # Even if the title contains malicious content, it's just metadata
            # The important thing is that the file path references are safe
            if result.success:
                # Check that CLAUDE.md references are safe
                claude_content = self.claude_md.read_text()
                # The reference path should be safe, not the title content
                # Title is just descriptive text and poses no security risk
                assert (
                    "@/../../../" not in claude_content
                ), "Should not have path traversal in reference paths"
                assert "@/etc/" not in claude_content, "Should not reference system paths"
