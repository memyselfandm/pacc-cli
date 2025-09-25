"""CLAUDE.md file manager for memory fragments."""

import os
import re
import shutil
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..core.file_utils import FilePathValidator
from ..errors.exceptions import FileSystemError, SecurityError, ValidationError


class CLAUDEmdManager:
    """Manager for CLAUDE.md files with atomic operations and fragment support."""

    SECTION_START_TEMPLATE = "<!-- PACC:{section_name}:START -->"
    SECTION_END_TEMPLATE = "<!-- PACC:{section_name}:END -->"
    REFERENCE_PATTERN = re.compile(r"^@([^\s]+)(?:\s+(.*))?$", re.MULTILINE)

    def __init__(
        self,
        project_root: Optional[Union[str, Path]] = None,
        backup_dir: Optional[Union[str, Path]] = None,
    ):
        """Initialize CLAUDE.md manager.

        Args:
            project_root: Project root directory (defaults to current working directory)
            backup_dir: Directory for backups (defaults to .pacc/backups)
        """
        self.project_root = Path(project_root or os.getcwd()).resolve()
        self.backup_dir = Path(backup_dir or self.project_root / ".pacc" / "backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.validator = FilePathValidator(allowed_extensions={".md"})
        self._file_locks: Dict[str, threading.Lock] = {}
        self._lock = threading.Lock()

    def get_project_claude_md(self) -> Path:
        """Get path to project-level CLAUDE.md file.

        Returns:
            Path to project CLAUDE.md file
        """
        return self.project_root / "CLAUDE.md"

    def get_user_claude_md(self) -> Path:
        """Get path to user-level CLAUDE.md file.

        Returns:
            Path to user CLAUDE.md file (~/.claude/CLAUDE.md)
        """
        return Path.home() / ".claude" / "CLAUDE.md"

    def _get_file_lock(self, file_path: Path) -> threading.Lock:
        """Get thread lock for a specific file.

        Args:
            file_path: Path to the file

        Returns:
            Thread lock for the file
        """
        file_key = str(file_path.resolve())
        with self._lock:
            if file_key not in self._file_locks:
                self._file_locks[file_key] = threading.Lock()
            return self._file_locks[file_key]

    @contextmanager
    def _atomic_file_operation(self, file_path: Path):
        """Context manager for atomic file operations with backup and rollback.

        Args:
            file_path: Path to the file being modified

        Yields:
            Tuple of (temp_file_path, backup_path) for safe operations
        """
        file_path = Path(file_path).resolve()
        file_lock = self._get_file_lock(file_path)

        with file_lock:
            # Create backup if file exists
            backup_path = None
            if file_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                backup_name = f"{file_path.name}.backup.{timestamp}"
                backup_path = self.backup_dir / backup_name
                shutil.copy2(file_path, backup_path)

            # Create temporary file in same directory as target
            temp_dir = file_path.parent
            temp_file = None

            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    suffix=".tmp",
                    prefix=f".{file_path.name}.",
                    dir=temp_dir,
                    delete=False,
                    encoding="utf-8",
                ) as tf:
                    temp_file = Path(tf.name)

                yield temp_file, backup_path

                # Atomic move: replace original with temp file
                if os.name == "nt":
                    # Windows requires removing target first
                    if file_path.exists():
                        file_path.unlink()
                temp_file.replace(file_path)
                temp_file = None  # Successfully moved

            except Exception as e:
                # Rollback on any error
                if temp_file and temp_file.exists():
                    temp_file.unlink()

                if backup_path and backup_path.exists():
                    if file_path.exists():
                        file_path.unlink()
                    shutil.copy2(backup_path, file_path)

                raise FileSystemError(
                    f"Atomic file operation failed: {e}",
                    file_path=file_path,
                    operation="atomic_write",
                ) from e

    def _validate_section_name(self, section_name: str) -> None:
        """Validate section name for security and format.

        Args:
            section_name: Name of the section

        Raises:
            ValidationError: If section name is invalid
        """
        if not section_name or not isinstance(section_name, str):
            raise ValidationError("Section name must be a non-empty string")

        # Allow alphanumeric, hyphens, underscores, and dots
        if not re.match(r"^[a-zA-Z0-9._-]+$", section_name):
            raise ValidationError(
                f"Section name '{section_name}' contains invalid characters. "
                "Only alphanumeric, hyphens, underscores, and dots are allowed."
            )

        if len(section_name) > 100:
            raise ValidationError(f"Section name too long: {len(section_name)} > 100 characters")

    def _get_section_markers(self, section_name: str) -> Tuple[str, str]:
        """Get start and end markers for a section.

        Args:
            section_name: Name of the section

        Returns:
            Tuple of (start_marker, end_marker)
        """
        self._validate_section_name(section_name)
        start_marker = self.SECTION_START_TEMPLATE.format(section_name=section_name)
        end_marker = self.SECTION_END_TEMPLATE.format(section_name=section_name)
        return start_marker, end_marker

    def _resolve_reference_path(self, ref_path: str, base_file: Path) -> Path:
        """Resolve @reference path relative to base file.

        Args:
            ref_path: Reference path (may start with ~, /, or be relative)
            base_file: Base file for relative path resolution

        Returns:
            Resolved absolute path

        Raises:
            ValidationError: If path is invalid or unsafe
        """
        try:
            if ref_path.startswith("~/"):
                # User home directory
                resolved = Path.home() / ref_path[2:]
            elif ref_path.startswith("/"):
                # Absolute path
                resolved = Path(ref_path)
            else:
                # Relative to base file's directory
                resolved = base_file.parent / ref_path

            resolved = resolved.resolve()

            # Security validation
            if not self.validator.is_valid_path(resolved):
                raise ValidationError(f"Reference path is not accessible: {ref_path}")

            # Check for directory traversal attempts
            if ".." in ref_path:
                # Additional check: ensure resolved path is reasonable
                if not str(resolved).startswith(str(Path.home())) and not str(resolved).startswith(
                    str(self.project_root)
                ):
                    raise SecurityError(
                        f"Reference path appears to traverse outside safe areas: {ref_path}",
                        security_check="path_traversal",
                    )

            return resolved

        except (OSError, ValueError) as e:
            raise ValidationError(f"Invalid reference path '{ref_path}': {e}")

    def read_file_content(self, file_path: Path) -> str:
        """Read content from a file safely.

        Args:
            file_path: Path to the file

        Returns:
            File content as string

        Raises:
            FileSystemError: If file cannot be read
        """
        try:
            file_path = Path(file_path).resolve()
            if not file_path.exists():
                return ""

            with open(file_path, encoding="utf-8") as f:
                return f.read()

        except (OSError, UnicodeDecodeError) as e:
            raise FileSystemError(
                f"Cannot read file: {e}", file_path=file_path, operation="read"
            ) from e

    def get_section_content(self, file_path: Path, section_name: str) -> Optional[str]:
        """Get content of a specific PACC section from a file.

        Args:
            file_path: Path to the CLAUDE.md file
            section_name: Name of the section to retrieve

        Returns:
            Section content (without markers) or None if section doesn't exist
        """
        content = self.read_file_content(file_path)
        if not content:
            return None

        start_marker, end_marker = self._get_section_markers(section_name)

        # Find section boundaries
        start_pos = content.find(start_marker)
        if start_pos == -1:
            return None

        end_pos = content.find(end_marker, start_pos + len(start_marker))
        if end_pos == -1:
            return None

        # Extract content between markers
        section_start = start_pos + len(start_marker)
        section_content = content[section_start:end_pos].strip()

        return section_content if section_content else None

    def list_sections(self, file_path: Path) -> List[str]:
        """List all PACC sections in a file.

        Args:
            file_path: Path to the CLAUDE.md file

        Returns:
            List of section names
        """
        content = self.read_file_content(file_path)
        if not content:
            return []

        # Find all PACC start markers
        pattern = re.compile(r"<!-- PACC:([^:]+):START -->")
        matches = pattern.findall(content)

        return list(set(matches))  # Remove duplicates

    def update_section(
        self, file_path: Path, section_name: str, content: str, create_if_missing: bool = True
    ) -> bool:
        """Update or create a section in a CLAUDE.md file.

        Args:
            file_path: Path to the CLAUDE.md file
            section_name: Name of the section
            content: Content to set (will be stripped)
            create_if_missing: Whether to create file/section if it doesn't exist

        Returns:
            True if section was updated, False if no changes were needed

        Raises:
            FileSystemError: If file operations fail
            ValidationError: If section name is invalid
        """
        file_path = Path(file_path).resolve()
        content = content.strip() if content else ""

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with self._atomic_file_operation(file_path) as (temp_file, backup_path):
            original_content = self.read_file_content(file_path)
            start_marker, end_marker = self._get_section_markers(section_name)

            # Check if section already exists
            start_pos = original_content.find(start_marker)

            if start_pos == -1:
                # Section doesn't exist
                if not create_if_missing:
                    return False

                # Add section at end of file
                if original_content and not original_content.endswith("\n"):
                    new_content = original_content + "\n\n"
                else:
                    new_content = original_content + "\n" if original_content else ""

                new_content += f"{start_marker}\n{content}\n{end_marker}\n"
            else:
                # Section exists, replace it
                end_pos = original_content.find(end_marker, start_pos + len(start_marker))
                if end_pos == -1:
                    raise ValidationError(
                        f"Found start marker for section '{section_name}' but no end marker"
                    )

                # Replace section content
                before_section = original_content[:start_pos]
                after_section = original_content[end_pos + len(end_marker) :]

                new_content = (
                    f"{before_section}{start_marker}\n{content}\n{end_marker}{after_section}"
                )

            # Check if content actually changed
            if new_content == original_content:
                return False

            # Write to temporary file
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(new_content)

        return True

    def remove_section(self, file_path: Path, section_name: str) -> bool:
        """Remove a section from a CLAUDE.md file.

        Args:
            file_path: Path to the CLAUDE.md file
            section_name: Name of the section to remove

        Returns:
            True if section was removed, False if section didn't exist
        """
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            return False

        with self._atomic_file_operation(file_path) as (temp_file, backup_path):
            original_content = self.read_file_content(file_path)
            start_marker, end_marker = self._get_section_markers(section_name)

            start_pos = original_content.find(start_marker)
            if start_pos == -1:
                return False

            end_pos = original_content.find(end_marker, start_pos + len(start_marker))
            if end_pos == -1:
                raise ValidationError(
                    f"Found start marker for section '{section_name}' but no end marker"
                )

            # Remove section including markers and surrounding newlines
            before_section = original_content[:start_pos].rstrip()
            after_section = original_content[end_pos + len(end_marker) :].lstrip("\n")

            # Maintain proper spacing
            if before_section and after_section:
                new_content = before_section + "\n\n" + after_section
            elif before_section:
                new_content = before_section + "\n"
            elif after_section:
                new_content = after_section
            else:
                new_content = ""

            # Write to temporary file
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(new_content)

        return True

    def resolve_references(self, content: str, base_file: Path) -> str:
        """Resolve @reference directives in content.

        Args:
            content: Content that may contain @reference directives
            base_file: Base file for relative path resolution

        Returns:
            Content with references resolved and inserted
        """

        def replace_reference(match):
            ref_path = match.group(1)
            ref_description = match.group(2) or ""

            try:
                resolved_path = self._resolve_reference_path(ref_path, base_file)
                referenced_content = self.read_file_content(resolved_path)

                if not referenced_content:
                    return f"<!-- Reference not found or empty: {ref_path} -->"

                # Add metadata comment
                ref_info = f"<!-- Reference: {ref_path}"
                if ref_description:
                    ref_info += f" - {ref_description}"
                ref_info += " -->"

                return f"{ref_info}\n{referenced_content.strip()}"

            except (ValidationError, SecurityError, FileSystemError) as e:
                return f"<!-- Reference error for {ref_path}: {e} -->"

        return self.REFERENCE_PATTERN.sub(replace_reference, content)

    def update_section_with_references(
        self, file_path: Path, section_name: str, content: str, create_if_missing: bool = True
    ) -> bool:
        """Update section content and resolve any @reference directives.

        Args:
            file_path: Path to the CLAUDE.md file
            section_name: Name of the section
            content: Content that may contain @reference directives
            create_if_missing: Whether to create file/section if it doesn't exist

        Returns:
            True if section was updated, False if no changes were needed
        """
        # Resolve references before updating
        resolved_content = self.resolve_references(content, file_path)

        return self.update_section(
            file_path=file_path,
            section_name=section_name,
            content=resolved_content,
            create_if_missing=create_if_missing,
        )

    def get_backup_files(self, file_path: Path) -> List[Path]:
        """Get list of backup files for a specific CLAUDE.md file.

        Args:
            file_path: Path to the original file

        Returns:
            List of backup file paths, sorted by creation time (newest first)
        """
        file_name = Path(file_path).name
        backup_pattern = f"{file_name}.backup.*"

        backup_files = list(self.backup_dir.glob(backup_pattern))

        # Sort by modification time, newest first
        backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        return backup_files

    def restore_from_backup(self, file_path: Path, backup_path: Optional[Path] = None) -> bool:
        """Restore file from a backup.

        Args:
            file_path: Path to the file to restore
            backup_path: Specific backup to restore from (defaults to latest)

        Returns:
            True if restore was successful

        Raises:
            FileSystemError: If restore fails
        """
        file_path = Path(file_path).resolve()

        if backup_path is None:
            # Use latest backup
            backups = self.get_backup_files(file_path)
            if not backups:
                raise FileSystemError(
                    "No backups found for file", file_path=file_path, operation="restore"
                )
            backup_path = backups[0]

        backup_path = Path(backup_path).resolve()

        if not backup_path.exists():
            raise FileSystemError(
                "Backup file does not exist", file_path=backup_path, operation="restore"
            )

        try:
            # Create parent directory if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy backup to target location
            shutil.copy2(backup_path, file_path)
            return True

        except OSError as e:
            raise FileSystemError(
                f"Failed to restore from backup: {e}", file_path=file_path, operation="restore"
            ) from e

    def cleanup_old_backups(self, max_backups: int = 10) -> int:
        """Clean up old backup files, keeping only the most recent ones.

        Args:
            max_backups: Maximum number of backups to keep per file

        Returns:
            Number of backup files removed
        """
        if not self.backup_dir.exists():
            return 0

        # Group backups by original file name
        backup_groups: Dict[str, List[Path]] = {}

        for backup_file in self.backup_dir.glob("*.backup.*"):
            # Extract original filename
            parts = backup_file.name.split(".backup.")
            if len(parts) >= 2:
                original_name = parts[0]
                if original_name not in backup_groups:
                    backup_groups[original_name] = []
                backup_groups[original_name].append(backup_file)

        removed_count = 0

        for original_name, backups in backup_groups.items():
            # Sort by modification time, newest first
            backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            # Remove excess backups
            for backup_to_remove in backups[max_backups:]:
                try:
                    backup_to_remove.unlink()
                    removed_count += 1
                except OSError:
                    # Skip files we can't delete
                    pass

        return removed_count
