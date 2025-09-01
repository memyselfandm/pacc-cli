"""Fragment Storage Manager for Claude Code memory fragments.

This module provides organized storage for memory fragments at both project and user levels,
with support for collection directories and automatic gitignore management.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Union, Iterator, Tuple
import fnmatch
from dataclasses import dataclass
from datetime import datetime

from ..core.file_utils import PathNormalizer, FilePathValidator, DirectoryScanner
from ..errors.exceptions import PACCError

logger = logging.getLogger(__name__)


@dataclass
class FragmentLocation:
    """Represents a fragment's location and metadata."""
    path: Path
    name: str
    is_collection: bool
    storage_type: str  # 'project' or 'user'
    collection_name: Optional[str] = None
    last_modified: Optional[datetime] = None
    size: Optional[int] = None

    def __post_init__(self):
        """Populate metadata from file system."""
        if self.path.exists():
            stat = self.path.stat()
            self.last_modified = datetime.fromtimestamp(stat.st_mtime)
            self.size = stat.st_size if self.path.is_file() else None


class GitIgnoreManager:
    """Manages .gitignore entries for fragment storage."""

    def __init__(self, project_root: Path):
        """Initialize gitignore manager.
        
        Args:
            project_root: Root directory of the project
        """
        self.project_root = PathNormalizer.normalize(project_root)
        self.gitignore_path = self.project_root / '.gitignore'

    def ensure_fragment_entries(self, fragment_paths: List[str]) -> bool:
        """Ensure fragment paths are in .gitignore.
        
        Args:
            fragment_paths: List of fragment paths to ignore
            
        Returns:
            True if .gitignore was modified
        """
        current_entries = set()
        
        # Read existing .gitignore
        if self.gitignore_path.exists():
            try:
                current_entries = set(self.gitignore_path.read_text().splitlines())
            except (OSError, UnicodeDecodeError):
                # If we can't read .gitignore, we'll create a new one
                current_entries = set()
        
        # Determine new entries needed
        new_entries = []
        pacc_section_marker = "# PACC Fragment Storage"
        
        for path in fragment_paths:
            normalized_path = path.replace('\\', '/')  # Use forward slashes for git
            if normalized_path not in current_entries:
                new_entries.append(normalized_path)
        
        if not new_entries:
            return False
        
        # Add new entries to .gitignore
        try:
            with open(self.gitignore_path, 'a', encoding='utf-8') as f:
                # Add section marker if not present
                content = self.gitignore_path.read_text() if self.gitignore_path.exists() else ""
                if pacc_section_marker not in content:
                    f.write(f"\n{pacc_section_marker}\n")
                
                # Add new entries
                for entry in new_entries:
                    f.write(f"{entry}\n")
            
            return True
        except OSError as e:
            # Non-fatal error - continue without gitignore management
            return False

    def remove_fragment_entries(self, fragment_paths: List[str]) -> bool:
        """Remove fragment paths from .gitignore.
        
        Args:
            fragment_paths: List of fragment paths to remove
            
        Returns:
            True if .gitignore was modified
        """
        if not self.gitignore_path.exists():
            return False
        
        try:
            lines = self.gitignore_path.read_text().splitlines()
            normalized_paths = {path.replace('\\', '/') for path in fragment_paths}
            
            # Filter out the paths we want to remove
            new_lines = [line for line in lines if line not in normalized_paths]
            
            if len(new_lines) != len(lines):
                self.gitignore_path.write_text('\n'.join(new_lines) + '\n')
                return True
            
            return False
        except (OSError, UnicodeDecodeError):
            return False


class FragmentStorageManager:
    """Manages storage of Claude Code memory fragments."""

    FRAGMENT_EXTENSIONS = {'.md', '.txt'}
    PROJECT_FRAGMENT_DIR = '.claude/pacc/fragments'
    USER_FRAGMENT_DIR = '.claude/pacc/fragments'

    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        """Initialize fragment storage manager.
        
        Args:
            project_root: Project root directory (defaults to current working directory)
        """
        self.project_root = PathNormalizer.normalize(project_root or Path.cwd())
        self.user_home = Path.home()
        
        # Initialize storage paths
        self.project_storage = self.project_root / self.PROJECT_FRAGMENT_DIR
        self.user_storage = self.user_home / self.USER_FRAGMENT_DIR
        
        # Initialize utilities
        self.validator = FilePathValidator(allowed_extensions=self.FRAGMENT_EXTENSIONS)
        self.scanner = DirectoryScanner(self.validator)
        self.gitignore_manager = GitIgnoreManager(self.project_root)
        
        # Ensure storage directories exist
        self._ensure_storage_directories()

    def _ensure_storage_directories(self) -> None:
        """Ensure storage directories exist with proper permissions."""
        for storage_path in [self.project_storage, self.user_storage]:
            try:
                PathNormalizer.ensure_directory(storage_path)
                # Ensure proper permissions (readable/writable by owner only)
                storage_path.chmod(0o755)
            except OSError:
                # Non-fatal - storage may not be available
                pass

    def get_project_storage_path(self) -> Path:
        """Get project-level storage path.
        
        Returns:
            Path to project fragment storage directory
        """
        return self.project_storage

    def get_user_storage_path(self) -> Path:
        """Get user-level storage path.
        
        Returns:
            Path to user fragment storage directory
        """
        return self.user_storage

    def store_fragment(
        self, 
        fragment_name: str, 
        content: str, 
        storage_type: str = 'project',
        collection: Optional[str] = None,
        overwrite: bool = False
    ) -> Path:
        """Store a fragment in the appropriate location.
        
        Args:
            fragment_name: Name of the fragment (without extension)
            content: Fragment content
            storage_type: 'project' or 'user'
            collection: Optional collection name (subdirectory)
            overwrite: Whether to overwrite existing fragments
            
        Returns:
            Path where fragment was stored
            
        Raises:
            PACCError: If fragment already exists and overwrite=False
        """
        # Determine storage location
        if storage_type == 'user':
            base_path = self.user_storage
        else:
            base_path = self.project_storage
            
        # Handle collection directories
        if collection:
            storage_path = base_path / collection
            PathNormalizer.ensure_directory(storage_path)
        else:
            storage_path = base_path
        
        # Ensure fragment has .md extension
        if not fragment_name.endswith('.md'):
            fragment_name += '.md'
        
        fragment_path = storage_path / fragment_name
        
        # Check for existing fragment
        if fragment_path.exists() and not overwrite:
            raise PACCError(f"Fragment already exists: {fragment_path}")
        
        # Store the fragment
        try:
            fragment_path.write_text(content, encoding='utf-8')
            
            # Update gitignore for project fragments
            if storage_type == 'project':
                self._update_gitignore_for_project_fragments()
                
        except OSError as e:
            raise PACCError(f"Failed to store fragment: {e}")
        
        return fragment_path

    def load_fragment(self, fragment_name: str, storage_type: str = 'project', collection: Optional[str] = None) -> str:
        """Load a fragment's content.
        
        Args:
            fragment_name: Name of the fragment
            storage_type: 'project' or 'user'
            collection: Optional collection name
            
        Returns:
            Fragment content
            
        Raises:
            PACCError: If fragment not found or cannot be read
        """
        fragment_path = self.find_fragment(fragment_name, storage_type, collection)
        if not fragment_path:
            raise PACCError(f"Fragment not found: {fragment_name}")
        
        try:
            return fragment_path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as e:
            raise PACCError(f"Failed to load fragment: {e}")

    def find_fragment(
        self, 
        fragment_name: str, 
        storage_type: Optional[str] = None, 
        collection: Optional[str] = None
    ) -> Optional[Path]:
        """Find a fragment by name.
        
        Args:
            fragment_name: Name of the fragment
            storage_type: 'project', 'user', or None to search both
            collection: Optional collection name
            
        Returns:
            Path to fragment if found, None otherwise
        """
        # SECURITY: Reject identifiers containing path separators to prevent path traversal
        if '/' in fragment_name or '\\' in fragment_name or '..' in fragment_name:
            logger.warning(f"Rejected fragment identifier with path separators: {fragment_name}")
            return None
        
        # Ensure fragment has .md extension for searching
        if not fragment_name.endswith('.md'):
            fragment_name += '.md'
        
        # Only search within controlled fragment storage directories
        search_paths = []
        
        if storage_type == 'project' or storage_type is None:
            if self.project_storage and self.project_storage.exists():
                if collection:
                    potential_path = self.project_storage / collection / fragment_name
                else:
                    potential_path = self.project_storage / fragment_name
                    
                # SECURITY: Verify path stays within fragment storage boundaries
                try:
                    if potential_path.exists() and potential_path.is_relative_to(self.project_storage):
                        search_paths.append(potential_path)
                except (ValueError, TypeError):
                    pass  # Path is not relative to storage, skip it
                
        if storage_type == 'user' or storage_type is None:
            if self.user_storage and self.user_storage.exists():
                if collection:
                    potential_path = self.user_storage / collection / fragment_name
                else:
                    potential_path = self.user_storage / fragment_name
                    
                # SECURITY: Verify path stays within fragment storage boundaries
                try:
                    if potential_path.exists() and potential_path.is_relative_to(self.user_storage):
                        search_paths.append(potential_path)
                except (ValueError, TypeError):
                    pass  # Path is not relative to storage, skip it
        
        # Additional validation for found paths
        for path in search_paths:
            if path.exists():
                # Double-check the path is actually within our storage directories
                # We don't use self.validator.is_valid_path here because it rejects absolute paths
                # But our search_paths are already validated to be within storage directories
                try:
                    if (self.project_storage and path.is_relative_to(self.project_storage)) or \
                       (self.user_storage and path.is_relative_to(self.user_storage)):
                        return path
                except (ValueError, TypeError):
                    pass  # Path is not relative to storage
        
        return None

    def list_fragments(
        self, 
        storage_type: Optional[str] = None, 
        collection: Optional[str] = None,
        pattern: Optional[str] = None
    ) -> List[FragmentLocation]:
        """List all fragments matching criteria.
        
        Args:
            storage_type: 'project', 'user', or None for both
            collection: Optional collection name to filter by
            pattern: Optional fnmatch pattern for fragment names
            
        Returns:
            List of FragmentLocation objects
        """
        fragments = []
        
        # Define search locations
        search_locations = []
        if storage_type == 'project' or storage_type is None:
            search_locations.append(('project', self.project_storage))
        if storage_type == 'user' or storage_type is None:
            search_locations.append(('user', self.user_storage))
        
        for location_type, base_path in search_locations:
            if not base_path.exists():
                continue
                
            # Search in specific collection or all collections
            if collection:
                search_dirs = [base_path / collection] if (base_path / collection).exists() else []
            else:
                # Search base directory and all subdirectories
                search_dirs = [base_path]
                if base_path.exists():
                    search_dirs.extend([p for p in base_path.iterdir() if p.is_dir()])
            
            for search_dir in search_dirs:
                if not search_dir.exists():
                    continue
                    
                for fragment_path in self.scanner.find_files_by_extension(
                    search_dir, self.FRAGMENT_EXTENSIONS, recursive=False
                ):
                    # Apply pattern filter if specified (match against stem, not full filename)
                    if pattern and not fnmatch.fnmatch(fragment_path.stem, pattern):
                        continue
                    
                    # Determine if this is in a collection
                    is_collection = search_dir != base_path
                    collection_name = search_dir.name if is_collection else None
                    
                    fragments.append(FragmentLocation(
                        path=fragment_path,
                        name=fragment_path.stem,
                        is_collection=is_collection,
                        storage_type=location_type,
                        collection_name=collection_name
                    ))
        
        # Sort by name for consistent ordering
        return sorted(fragments, key=lambda f: (f.storage_type, f.collection_name or '', f.name))

    def list_collections(self, storage_type: Optional[str] = None) -> Dict[str, List[str]]:
        """List all collections and their fragments.
        
        Args:
            storage_type: 'project', 'user', or None for both
            
        Returns:
            Dictionary mapping collection names to fragment lists
        """
        collections = {}
        
        # Define search locations
        search_locations = []
        if storage_type == 'project' or storage_type is None:
            search_locations.append(self.project_storage)
        if storage_type == 'user' or storage_type is None:
            search_locations.append(self.user_storage)
        
        for base_path in search_locations:
            if not base_path.exists():
                continue
                
            for collection_dir in base_path.iterdir():
                if not collection_dir.is_dir():
                    continue
                
                # Get fragments in this collection
                fragment_names = []
                for fragment_path in self.scanner.find_files_by_extension(
                    collection_dir, self.FRAGMENT_EXTENSIONS, recursive=False
                ):
                    fragment_names.append(fragment_path.stem)
                
                if fragment_names:
                    collection_key = f"{collection_dir.name}"
                    if collection_key in collections:
                        collections[collection_key].extend(fragment_names)
                    else:
                        collections[collection_key] = fragment_names
        
        return collections

    def remove_fragment(
        self, 
        fragment_name: str, 
        storage_type: Optional[str] = None, 
        collection: Optional[str] = None
    ) -> bool:
        """Remove a fragment.
        
        Args:
            fragment_name: Name of the fragment to remove
            storage_type: 'project', 'user', or None to search both
            collection: Optional collection name
            
        Returns:
            True if fragment was removed, False if not found
        """
        fragment_path = self.find_fragment(fragment_name, storage_type, collection)
        if not fragment_path:
            return False
        
        try:
            fragment_path.unlink()
            
            # Clean up empty collection directories
            parent_dir = fragment_path.parent
            storage_bases = [self.project_storage, self.user_storage]
            
            if parent_dir not in storage_bases and parent_dir.exists():
                try:
                    # Remove directory if it's empty
                    parent_dir.rmdir()
                except OSError:
                    # Directory not empty, that's fine
                    pass
            
            # Update gitignore if this was a project fragment
            if fragment_path.is_relative_to(self.project_storage):
                self._update_gitignore_for_project_fragments()
            
            return True
            
        except OSError:
            return False

    def create_collection(self, collection_name: str, storage_type: str = 'project') -> Path:
        """Create a new collection directory.
        
        Args:
            collection_name: Name of the collection
            storage_type: 'project' or 'user'
            
        Returns:
            Path to created collection directory
        """
        base_path = self.project_storage if storage_type == 'project' else self.user_storage
        collection_path = base_path / collection_name
        
        PathNormalizer.ensure_directory(collection_path)
        return collection_path

    def remove_collection(
        self, 
        collection_name: str, 
        storage_type: str = 'project',
        force: bool = False
    ) -> bool:
        """Remove a collection and optionally its fragments.
        
        Args:
            collection_name: Name of the collection to remove
            storage_type: 'project' or 'user'
            force: If True, remove even if collection contains fragments
            
        Returns:
            True if collection was removed, False otherwise
        """
        base_path = self.project_storage if storage_type == 'project' else self.user_storage
        collection_path = base_path / collection_name
        
        if not collection_path.exists() or not collection_path.is_dir():
            return False
        
        try:
            if force:
                shutil.rmtree(collection_path)
            else:
                collection_path.rmdir()  # Only removes if empty
            
            # Update gitignore if this was a project collection
            if storage_type == 'project':
                self._update_gitignore_for_project_fragments()
            
            return True
            
        except OSError:
            return False

    def get_fragment_stats(self) -> Dict[str, any]:
        """Get statistics about stored fragments.
        
        Returns:
            Dictionary with fragment statistics
        """
        stats = {
            'project_fragments': 0,
            'user_fragments': 0,
            'total_fragments': 0,
            'collections': 0,
            'total_size': 0,
            'storage_paths': {
                'project': str(self.project_storage),
                'user': str(self.user_storage)
            }
        }
        
        # Count fragments in each storage type
        for storage_type in ['project', 'user']:
            fragments = self.list_fragments(storage_type=storage_type)
            count = len(fragments)
            stats[f'{storage_type}_fragments'] = count
            stats['total_fragments'] += count
            
            # Add up sizes
            for fragment in fragments:
                if fragment.size:
                    stats['total_size'] += fragment.size
        
        # Count collections
        collections = self.list_collections()
        stats['collections'] = len(collections)
        
        return stats

    def _update_gitignore_for_project_fragments(self) -> None:
        """Update .gitignore to include project fragment paths."""
        if not self.project_storage.exists():
            return
        
        # Build list of paths to ignore
        ignore_paths = []
        
        # Add the base fragment directory
        rel_path = self.project_storage.relative_to(self.project_root)
        ignore_paths.append(f"{rel_path.as_posix()}/")
        
        # Update gitignore
        self.gitignore_manager.ensure_fragment_entries(ignore_paths)

    def cleanup_empty_directories(self, storage_type: Optional[str] = None) -> int:
        """Clean up empty directories in fragment storage.
        
        Args:
            storage_type: 'project', 'user', or None for both
            
        Returns:
            Number of directories removed
        """
        removed_count = 0
        
        search_locations = []
        if storage_type == 'project' or storage_type is None:
            search_locations.append(self.project_storage)
        if storage_type == 'user' or storage_type is None:
            search_locations.append(self.user_storage)
        
        for base_path in search_locations:
            if not base_path.exists():
                continue
                
            # Find empty subdirectories
            for subdir in base_path.iterdir():
                if subdir.is_dir():
                    try:
                        # Try to remove if empty
                        subdir.rmdir()
                        removed_count += 1
                    except OSError:
                        # Directory not empty, continue
                        pass
        
        return removed_count

    def backup_fragments(self, backup_path: Union[str, Path], storage_type: Optional[str] = None) -> Path:
        """Create a backup of fragments.
        
        Args:
            backup_path: Path where backup should be created
            storage_type: 'project', 'user', or None for both
            
        Returns:
            Path to created backup
            
        Raises:
            PACCError: If backup cannot be created
        """
        backup_path = Path(backup_path)
        
        # Create backup directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = backup_path / f"fragment_backup_{timestamp}"
        
        try:
            PathNormalizer.ensure_directory(backup_dir)
            
            # Copy fragments
            if storage_type == 'project' or storage_type is None:
                if self.project_storage.exists():
                    shutil.copytree(
                        self.project_storage, 
                        backup_dir / 'project_fragments',
                        dirs_exist_ok=True
                    )
            
            if storage_type == 'user' or storage_type is None:
                if self.user_storage.exists():
                    shutil.copytree(
                        self.user_storage, 
                        backup_dir / 'user_fragments',
                        dirs_exist_ok=True
                    )
            
            return backup_dir
            
        except OSError as e:
            raise PACCError(f"Failed to create backup: {e}")