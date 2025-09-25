"""Collection Manager for Claude Code memory fragment collections.

This module provides comprehensive collection management including metadata parsing,
selective installation, versioning, dependencies, and atomic operations.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

from ..errors.exceptions import PACCError
from ..validators.fragment_validator import FragmentValidator
from .installation_manager import FragmentInstallationManager
from .storage_manager import FragmentStorageManager
from .version_tracker import FragmentVersionTracker

logger = logging.getLogger(__name__)


@dataclass
class CollectionMetadata:
    """Metadata for a fragment collection."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    tags: List[str] = field(default_factory=list)
    category: str = ""
    dependencies: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    optional_files: List[str] = field(default_factory=list)
    install_order: List[str] = field(default_factory=list)
    checksum: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    source_url: Optional[str] = None
    git_commit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "category": self.category,
            "dependencies": self.dependencies,
            "files": self.files,
            "optional_files": self.optional_files,
            "install_order": self.install_order,
            "checksum": self.checksum,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_url": self.source_url,
            "git_commit": self.git_commit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CollectionMetadata":
        """Create from dictionary representation."""
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            tags=data.get("tags", []),
            category=data.get("category", ""),
            dependencies=data.get("dependencies", []),
            files=data.get("files", []),
            optional_files=data.get("optional_files", []),
            install_order=data.get("install_order", []),
            checksum=data.get("checksum"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            source_url=data.get("source_url"),
            git_commit=data.get("git_commit"),
        )


@dataclass
class CollectionInstallOptions:
    """Options for collection installation."""

    selected_files: Optional[List[str]] = None
    include_optional: bool = False
    force_overwrite: bool = False
    storage_type: str = "project"
    verify_integrity: bool = True
    resolve_dependencies: bool = True
    dry_run: bool = False


@dataclass
class CollectionInstallResult:
    """Result of collection installation."""

    success: bool
    collection_name: str
    installed_files: List[str] = field(default_factory=list)
    skipped_files: List[str] = field(default_factory=list)
    failed_files: List[str] = field(default_factory=list)
    dependencies_resolved: List[str] = field(default_factory=list)
    integrity_verified: bool = False
    error_message: str = ""
    warnings: List[str] = field(default_factory=list)
    changes_made: List[str] = field(default_factory=list)


@dataclass
class CollectionUpdateInfo:
    """Information about collection updates."""

    collection_name: str
    current_version: str
    available_version: str
    has_update: bool
    changed_files: List[str] = field(default_factory=list)
    new_files: List[str] = field(default_factory=list)
    removed_files: List[str] = field(default_factory=list)
    dependency_changes: Dict[str, Any] = field(default_factory=dict)
    breaking_changes: bool = False


class CollectionMetadataParser:
    """Parser for collection metadata from pacc.json and frontmatter."""

    def __init__(self):
        """Initialize metadata parser."""
        self.validator = FragmentValidator()

    def parse_collection_metadata(self, collection_path: Path) -> Optional[CollectionMetadata]:
        """Parse collection metadata from pacc.json or frontmatter.

        Args:
            collection_path: Path to collection directory

        Returns:
            CollectionMetadata object or None if parsing failed
        """
        # Try pacc.json first (preferred)
        pacc_json = collection_path / "pacc.json"
        if pacc_json.exists():
            try:
                return self._parse_pacc_json(pacc_json, collection_path)
            except Exception as e:
                logger.warning(f"Failed to parse pacc.json in {collection_path}: {e}")

        # Fall back to README.md or first .md file with frontmatter
        return self._parse_frontmatter_metadata(collection_path)

    def _parse_pacc_json(self, pacc_json: Path, collection_path: Path) -> CollectionMetadata:
        """Parse metadata from pacc.json file."""
        with open(pacc_json, encoding="utf-8") as f:
            data = json.load(f)

        # Extract collection-specific data
        collection_data = data.get("collection", {})

        # Get file list from directory
        md_files = [f.stem for f in collection_path.glob("*.md")]

        metadata = CollectionMetadata.from_dict(
            {
                "name": collection_data.get("name", collection_path.name),
                "version": collection_data.get("version", "1.0.0"),
                "description": collection_data.get("description", ""),
                "author": collection_data.get("author", ""),
                "tags": collection_data.get("tags", []),
                "category": collection_data.get("category", ""),
                "dependencies": collection_data.get("dependencies", []),
                "files": collection_data.get("files", md_files),
                "optional_files": collection_data.get("optional_files", []),
                "install_order": collection_data.get("install_order", []),
                "source_url": collection_data.get("source_url"),
                "git_commit": collection_data.get("git_commit"),
            }
        )

        # Calculate checksum
        metadata.checksum = self._calculate_collection_checksum(collection_path, metadata.files)

        # Set timestamps
        stat = collection_path.stat()
        metadata.updated_at = datetime.fromtimestamp(stat.st_mtime).isoformat()

        return metadata

    def _parse_frontmatter_metadata(self, collection_path: Path) -> Optional[CollectionMetadata]:
        """Parse metadata from README.md or first fragment's frontmatter."""
        # Look for README.md first
        readme_path = collection_path / "README.md"
        if readme_path.exists():
            metadata = self._extract_frontmatter_metadata(readme_path)
            if metadata:
                metadata.name = collection_path.name
                return metadata

        # Fall back to first .md file
        for md_file in collection_path.glob("*.md"):
            metadata = self._extract_frontmatter_metadata(md_file)
            if metadata:
                metadata.name = collection_path.name
                return metadata

        # Create minimal metadata if none found
        md_files = [f.stem for f in collection_path.glob("*.md")]
        return CollectionMetadata(
            name=collection_path.name,
            version="1.0.0",
            files=md_files,
            checksum=self._calculate_collection_checksum(collection_path, md_files),
        )

    def _extract_frontmatter_metadata(self, file_path: Path) -> Optional[CollectionMetadata]:
        """Extract metadata from YAML frontmatter."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                return None

            parts = content.split("---", 2)
            if len(parts) < 3:
                return None

            frontmatter = yaml.safe_load(parts[1])
            if not isinstance(frontmatter, dict):
                return None

            # Extract collection metadata
            collection_data = frontmatter.get("collection", frontmatter)

            return CollectionMetadata.from_dict(
                {
                    "name": collection_data.get("name", ""),
                    "version": collection_data.get("version", "1.0.0"),
                    "description": collection_data.get("description", ""),
                    "author": collection_data.get("author", ""),
                    "tags": collection_data.get("tags", []),
                    "category": collection_data.get("category", ""),
                    "dependencies": collection_data.get("dependencies", []),
                    "files": collection_data.get("files", []),
                    "optional_files": collection_data.get("optional_files", []),
                    "install_order": collection_data.get("install_order", []),
                }
            )

        except Exception as e:
            logger.debug(f"Could not parse frontmatter from {file_path}: {e}")
            return None

    def _calculate_collection_checksum(self, collection_path: Path, files: List[str]) -> str:
        """Calculate checksum for collection integrity verification."""
        hasher = hashlib.sha256()

        # Sort files for consistent hashing
        for file_name in sorted(files):
            file_path = collection_path / f"{file_name}.md"
            if file_path.exists():
                hasher.update(file_path.read_bytes())

        return hasher.hexdigest()[:16]  # Short checksum


class CollectionDependencyResolver:
    """Resolves dependencies between collections."""

    def __init__(self, storage_manager: FragmentStorageManager):
        """Initialize dependency resolver."""
        self.storage_manager = storage_manager

    def resolve_dependencies(self, metadata: CollectionMetadata) -> List[str]:
        """Resolve collection dependencies.

        Args:
            metadata: Collection metadata with dependencies

        Returns:
            List of collection names that need to be installed first

        Raises:
            PACCError: If circular dependencies detected
        """
        if not metadata.dependencies:
            return []

        resolved = []
        visited = set()
        visiting = set()

        def _resolve_recursive(collection_name: str) -> None:
            if collection_name in visiting:
                raise PACCError(f"Circular dependency detected involving: {collection_name}")

            if collection_name in visited:
                return

            visiting.add(collection_name)

            # Check if collection is already installed
            collections = self.storage_manager.list_collections()
            if collection_name not in collections:
                # Collection needs to be installed
                if collection_name not in resolved:
                    resolved.append(collection_name)

            visiting.remove(collection_name)
            visited.add(collection_name)

        # Resolve each dependency
        for dep in metadata.dependencies:
            _resolve_recursive(dep)

        return resolved

    def check_dependency_conflicts(self, collections: List[CollectionMetadata]) -> List[str]:
        """Check for dependency conflicts between collections.

        Args:
            collections: List of collections to check

        Returns:
            List of conflict descriptions
        """
        conflicts = []

        # Build dependency graph
        deps = {}
        for collection in collections:
            deps[collection.name] = collection.dependencies

        # Check for version conflicts (simplified - just name conflicts for now)
        all_deps = set()
        for collection_deps in deps.values():
            all_deps.update(collection_deps)

        # Check if any required dependency is missing
        available_collections = {c.name for c in collections}
        for dep in all_deps:
            if dep not in available_collections:
                conflicts.append(f"Missing dependency: {dep}")

        return conflicts


class FragmentCollectionManager:
    """Manages fragment collections with advanced features."""

    def __init__(self, project_root: Optional[Union[str, Path]] = None):
        """Initialize collection manager."""
        self.project_root = Path(project_root or Path.cwd()).resolve()

        # Initialize component managers
        self.storage_manager = FragmentStorageManager(project_root=self.project_root)
        self.installation_manager = FragmentInstallationManager(project_root=self.project_root)
        self.metadata_parser = CollectionMetadataParser()
        self.dependency_resolver = CollectionDependencyResolver(self.storage_manager)
        self.validator = FragmentValidator()
        self.version_tracker = FragmentVersionTracker(self.project_root)

        logger.info(f"Collection manager initialized for project: {self.project_root}")

    def discover_collections(
        self, search_paths: List[Path]
    ) -> List[Tuple[Path, CollectionMetadata]]:
        """Discover collections in specified paths.

        Args:
            search_paths: Paths to search for collections

        Returns:
            List of (collection_path, metadata) tuples
        """
        collections = []

        for search_path in search_paths:
            if not search_path.exists():
                continue

            # Look for collection directories
            for item in search_path.iterdir():
                if not item.is_dir():
                    continue

                # Check if directory has multiple .md files (collection indicator)
                md_files = list(item.glob("*.md"))
                if len(md_files) >= 2:
                    metadata = self.metadata_parser.parse_collection_metadata(item)
                    if metadata:
                        collections.append((item, metadata))

        return collections

    def install_collection(
        self, collection_path: Path, options: CollectionInstallOptions
    ) -> CollectionInstallResult:
        """Install a collection with selective file support.

        Args:
            collection_path: Path to collection directory
            options: Installation options

        Returns:
            CollectionInstallResult with operation details
        """
        result = CollectionInstallResult(success=False, collection_name=collection_path.name)

        try:
            # Parse collection metadata
            metadata = self.metadata_parser.parse_collection_metadata(collection_path)
            if not metadata:
                result.error_message = "Could not parse collection metadata"
                return result

            result.collection_name = metadata.name

            # Resolve dependencies if requested
            if options.resolve_dependencies:
                missing_deps = self.dependency_resolver.resolve_dependencies(metadata)
                if missing_deps:
                    result.dependencies_resolved = missing_deps
                    result.warnings.append(f"Missing dependencies: {', '.join(missing_deps)}")

            # Determine files to install
            files_to_install = self._select_files_for_installation(
                collection_path, metadata, options
            )

            if not files_to_install:
                result.success = True
                result.warnings.append("No files selected for installation")
                return result

            # Verify integrity if requested
            if options.verify_integrity:
                if self._verify_collection_integrity(collection_path, metadata):
                    result.integrity_verified = True
                else:
                    if not options.force_overwrite:
                        result.error_message = "Collection integrity check failed"
                        return result
                    result.warnings.append(
                        "Collection integrity check failed, proceeding with force"
                    )

            # Perform installation (atomic operation)
            if options.dry_run:
                result = self._perform_dry_run_collection_install(
                    result, collection_path, files_to_install, options
                )
            else:
                result = self._perform_actual_collection_install(
                    result, collection_path, metadata, files_to_install, options
                )

            return result

        except Exception as e:
            logger.error(f"Collection installation failed: {e}")
            result.error_message = str(e)
            return result

    def _select_files_for_installation(
        self, collection_path: Path, metadata: CollectionMetadata, options: CollectionInstallOptions
    ) -> List[str]:
        """Select files for installation based on options."""
        available_files = [f.stem for f in collection_path.glob("*.md")]

        # Start with explicitly selected files or all files
        if options.selected_files:
            files_to_install = [f for f in options.selected_files if f in available_files]
        else:
            files_to_install = metadata.files if metadata.files else available_files

        # Add optional files if requested
        if options.include_optional and metadata.optional_files:
            files_to_install.extend(
                [
                    f
                    for f in metadata.optional_files
                    if f in available_files and f not in files_to_install
                ]
            )

        return files_to_install

    def _verify_collection_integrity(
        self, collection_path: Path, metadata: CollectionMetadata
    ) -> bool:
        """Verify collection integrity using checksum."""
        if not metadata.checksum:
            return True  # No checksum to verify

        current_checksum = self.metadata_parser._calculate_collection_checksum(
            collection_path, metadata.files
        )

        return current_checksum == metadata.checksum

    def _perform_dry_run_collection_install(
        self,
        result: CollectionInstallResult,
        collection_path: Path,
        files_to_install: List[str],
        options: CollectionInstallOptions,
    ) -> CollectionInstallResult:
        """Perform dry-run collection installation."""
        result.success = True

        for file_name in files_to_install:
            file_path = collection_path / f"{file_name}.md"
            if file_path.exists():
                # Check if would overwrite existing
                existing = self.storage_manager.find_fragment(
                    file_name, options.storage_type, collection_path.name
                )
                if existing and not options.force_overwrite:
                    result.skipped_files.append(file_name)
                    result.changes_made.append(f"Would skip existing: {file_name}")
                else:
                    result.installed_files.append(file_name)
                    result.changes_made.append(f"Would install: {file_name}")
            else:
                result.failed_files.append(file_name)
                result.changes_made.append(f"Would fail (missing): {file_name}")

        return result

    def _perform_actual_collection_install(
        self,
        result: CollectionInstallResult,
        collection_path: Path,
        metadata: CollectionMetadata,
        files_to_install: List[str],
        options: CollectionInstallOptions,
    ) -> CollectionInstallResult:
        """Perform actual collection installation with atomic operations."""
        backup_state = None

        try:
            # Create backup for rollback
            backup_state = self._create_collection_backup(
                collection_path.name, options.storage_type
            )

            # Install files in order (if specified)
            install_order = metadata.install_order if metadata.install_order else files_to_install

            for file_name in install_order:
                if file_name not in files_to_install:
                    continue

                file_path = collection_path / f"{file_name}.md"
                if not file_path.exists():
                    result.failed_files.append(file_name)
                    result.warnings.append(f"File not found: {file_name}")
                    continue

                try:
                    # Install individual fragment
                    content = file_path.read_text(encoding="utf-8")
                    stored_path = self.storage_manager.store_fragment(
                        fragment_name=file_name,
                        content=content,
                        storage_type=options.storage_type,
                        collection=collection_path.name,
                        overwrite=options.force_overwrite,
                    )

                    result.installed_files.append(file_name)
                    result.changes_made.append(f"Installed: {file_name}")

                    # Track version if source URL available
                    if metadata.source_url:
                        self.version_tracker.track_installation(
                            file_name, metadata.source_url, "collection", file_path
                        )

                except PACCError as e:
                    if "already exists" in str(e) and not options.force_overwrite:
                        result.skipped_files.append(file_name)
                        result.changes_made.append(f"Skipped existing: {file_name}")
                    else:
                        result.failed_files.append(file_name)
                        result.warnings.append(f"Failed to install {file_name}: {e}")

            # Update collection tracking
            self._track_collection_installation(metadata, options.storage_type)

            result.success = True
            logger.info(
                f"Collection installed: {metadata.name} ({len(result.installed_files)} files)"
            )

        except Exception as e:
            logger.error(f"Collection installation failed, performing rollback: {e}")

            # Rollback on failure
            if backup_state:
                try:
                    self._rollback_collection_installation(backup_state)
                    result.changes_made.append("Rolled back changes due to installation failure")
                except Exception as rollback_error:
                    result.warnings.append(f"Rollback failed: {rollback_error}")

            result.error_message = str(e)
            result.success = False

        return result

    def _create_collection_backup(self, collection_name: str, storage_type: str) -> Dict[str, Any]:
        """Create backup state for atomic rollback."""
        backup_state = {
            "collection_name": collection_name,
            "storage_type": storage_type,
            "existing_fragments": [],
            "pacc_json_backup": None,
        }

        # Backup existing fragments in collection
        existing_fragments = self.storage_manager.list_fragments(
            storage_type=storage_type, collection=collection_name
        )

        for fragment in existing_fragments:
            backup_state["existing_fragments"].append(
                {
                    "name": fragment.name,
                    "content": self.storage_manager.load_fragment(
                        fragment.name, storage_type, collection_name
                    ),
                }
            )

        # Backup pacc.json
        pacc_json_path = self.project_root / "pacc.json"
        if pacc_json_path.exists():
            backup_state["pacc_json_backup"] = pacc_json_path.read_text(encoding="utf-8")

        return backup_state

    def _rollback_collection_installation(self, backup_state: Dict[str, Any]) -> None:
        """Rollback collection installation."""
        collection_name = backup_state["collection_name"]
        storage_type = backup_state["storage_type"]

        # Remove any newly installed fragments
        current_fragments = self.storage_manager.list_fragments(
            storage_type=storage_type, collection=collection_name
        )

        for fragment in current_fragments:
            self.storage_manager.remove_fragment(fragment.name, storage_type, collection_name)

        # Restore original fragments
        for fragment_backup in backup_state["existing_fragments"]:
            self.storage_manager.store_fragment(
                fragment_name=fragment_backup["name"],
                content=fragment_backup["content"],
                storage_type=storage_type,
                collection=collection_name,
                overwrite=True,
            )

        # Restore pacc.json
        if backup_state["pacc_json_backup"]:
            pacc_json_path = self.project_root / "pacc.json"
            pacc_json_path.write_text(backup_state["pacc_json_backup"], encoding="utf-8")

    def _track_collection_installation(
        self, metadata: CollectionMetadata, storage_type: str
    ) -> None:
        """Track collection installation in pacc.json."""
        pacc_json_path = self.project_root / "pacc.json"

        # Load or create pacc.json
        if pacc_json_path.exists():
            try:
                config = json.loads(pacc_json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                config = {}
        else:
            config = {}

        # Ensure collections section exists
        if "collections" not in config:
            config["collections"] = {}

        # Add collection entry
        config["collections"][metadata.name] = {
            "version": metadata.version,
            "description": metadata.description,
            "author": metadata.author,
            "tags": metadata.tags,
            "category": metadata.category,
            "dependencies": metadata.dependencies,
            "files": metadata.files,
            "storage_type": storage_type,
            "installed_at": datetime.now().isoformat(),
            "source_url": metadata.source_url,
            "checksum": metadata.checksum,
        }

        # Write updated config
        pacc_json_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    def update_collection(
        self, collection_name: str, source_path: Path, options: CollectionInstallOptions
    ) -> CollectionInstallResult:
        """Update an existing collection with partial update support.

        Args:
            collection_name: Name of collection to update
            source_path: Path to new collection version
            options: Update options

        Returns:
            CollectionInstallResult with update details
        """
        result = CollectionInstallResult(success=False, collection_name=collection_name)

        try:
            # Get current collection info
            current_collections = self.storage_manager.list_collections(options.storage_type)
            if collection_name not in current_collections:
                result.error_message = f"Collection '{collection_name}' not found"
                return result

            # Parse new metadata
            new_metadata = self.metadata_parser.parse_collection_metadata(source_path)
            if not new_metadata:
                result.error_message = "Could not parse new collection metadata"
                return result

            # Determine what files changed
            update_info = self._analyze_collection_update(
                collection_name, new_metadata, options.storage_type
            )

            if not update_info.has_update:
                result.success = True
                result.warnings.append("Collection is already up to date")
                return result

            # Perform selective update based on changed files
            files_to_update = (
                options.selected_files or update_info.changed_files + update_info.new_files
            )

            # Create new install options for update
            update_options = CollectionInstallOptions(
                selected_files=files_to_update,
                include_optional=options.include_optional,
                force_overwrite=True,  # Updates should overwrite
                storage_type=options.storage_type,
                verify_integrity=options.verify_integrity,
                resolve_dependencies=options.resolve_dependencies,
                dry_run=options.dry_run,
            )

            # Install updates
            result = self.install_collection(source_path, update_options)
            result.changes_made.extend(
                [
                    f"Updated from version {update_info.current_version} to {update_info.available_version}"
                ]
            )

            return result

        except Exception as e:
            logger.error(f"Collection update failed: {e}")
            result.error_message = str(e)
            return result

    def _analyze_collection_update(
        self, collection_name: str, new_metadata: CollectionMetadata, storage_type: str
    ) -> CollectionUpdateInfo:
        """Analyze collection for updates."""
        # Load current collection metadata from pacc.json
        pacc_json_path = self.project_root / "pacc.json"
        current_metadata = None

        if pacc_json_path.exists():
            try:
                config = json.loads(pacc_json_path.read_text(encoding="utf-8"))
                if "collections" in config and collection_name in config["collections"]:
                    current_data = config["collections"][collection_name]
                    current_metadata = CollectionMetadata.from_dict(current_data)
            except Exception:
                pass

        update_info = CollectionUpdateInfo(
            collection_name=collection_name,
            current_version=current_metadata.version if current_metadata else "unknown",
            available_version=new_metadata.version,
            has_update=False,
        )

        if not current_metadata:
            # New installation
            update_info.has_update = True
            update_info.new_files = new_metadata.files
            return update_info

        # Compare versions
        if new_metadata.version != current_metadata.version:
            update_info.has_update = True

        # Compare files
        current_files = set(current_metadata.files)
        new_files = set(new_metadata.files)

        update_info.changed_files = list(new_files.intersection(current_files))
        update_info.new_files = list(new_files - current_files)
        update_info.removed_files = list(current_files - new_files)

        # Compare dependencies
        if current_metadata.dependencies != new_metadata.dependencies:
            update_info.dependency_changes = {
                "added": list(set(new_metadata.dependencies) - set(current_metadata.dependencies)),
                "removed": list(
                    set(current_metadata.dependencies) - set(new_metadata.dependencies)
                ),
            }
            update_info.has_update = True

        # Simple breaking change detection (major version bump)
        try:
            current_major = int(current_metadata.version.split(".")[0])
            new_major = int(new_metadata.version.split(".")[0])
            update_info.breaking_changes = new_major > current_major
        except (ValueError, IndexError):
            pass

        return update_info

    def remove_collection(
        self, collection_name: str, storage_type: str = "project", remove_dependencies: bool = False
    ) -> bool:
        """Remove a collection and optionally its dependencies.

        Args:
            collection_name: Name of collection to remove
            storage_type: Storage type to remove from
            remove_dependencies: Whether to remove unused dependencies

        Returns:
            True if collection was removed successfully
        """
        try:
            # Remove fragments in collection
            success = self.storage_manager.remove_collection(
                collection_name, storage_type, force=True
            )

            if success:
                # Remove from pacc.json tracking
                self._untrack_collection_installation(collection_name)

                # Remove unused dependencies if requested
                if remove_dependencies:
                    self._remove_unused_dependencies(collection_name, storage_type)

                logger.info(f"Collection removed: {collection_name}")

            return success

        except Exception as e:
            logger.error(f"Failed to remove collection {collection_name}: {e}")
            return False

    def _untrack_collection_installation(self, collection_name: str) -> None:
        """Remove collection from pacc.json tracking."""
        pacc_json_path = self.project_root / "pacc.json"

        if not pacc_json_path.exists():
            return

        try:
            config = json.loads(pacc_json_path.read_text(encoding="utf-8"))

            if "collections" in config and collection_name in config["collections"]:
                del config["collections"][collection_name]

                # Clean up empty collections section
                if not config["collections"]:
                    del config["collections"]

                pacc_json_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not update pacc.json during collection removal: {e}")

    def _remove_unused_dependencies(self, removed_collection: str, storage_type: str) -> None:
        """Remove dependencies that are no longer needed."""
        # This is a simplified implementation
        # In practice, you'd want to check all remaining collections for dependency usage
        logger.debug(f"Dependency cleanup for {removed_collection} not yet implemented")

    def list_collections_with_metadata(
        self, storage_type: Optional[str] = None
    ) -> List[Tuple[str, CollectionMetadata]]:
        """List collections with their metadata.

        Args:
            storage_type: Storage type to filter by

        Returns:
            List of (collection_name, metadata) tuples
        """
        collections_with_metadata = []

        # Get collections from pacc.json
        pacc_json_path = self.project_root / "pacc.json"
        if pacc_json_path.exists():
            try:
                config = json.loads(pacc_json_path.read_text(encoding="utf-8"))
                collections_config = config.get("collections", {})

                for name, data in collections_config.items():
                    if storage_type and data.get("storage_type") != storage_type:
                        continue

                    metadata = CollectionMetadata.from_dict(data)
                    collections_with_metadata.append((name, metadata))

            except Exception as e:
                logger.warning(f"Could not read collections from pacc.json: {e}")

        return collections_with_metadata

    def get_collection_status(self, collection_name: str) -> Dict[str, Any]:
        """Get detailed status information for a collection.

        Args:
            collection_name: Name of collection to check

        Returns:
            Dictionary with collection status details
        """
        status = {
            "name": collection_name,
            "installed": False,
            "storage_type": None,
            "version": None,
            "files_count": 0,
            "missing_files": [],
            "extra_files": [],
            "integrity_valid": False,
            "dependencies_satisfied": True,
            "last_updated": None,
        }

        # Check if collection is tracked in pacc.json
        pacc_json_path = self.project_root / "pacc.json"
        if pacc_json_path.exists():
            try:
                config = json.loads(pacc_json_path.read_text(encoding="utf-8"))
                collections = config.get("collections", {})

                if collection_name in collections:
                    collection_data = collections[collection_name]
                    status.update(
                        {
                            "installed": True,
                            "storage_type": collection_data.get("storage_type"),
                            "version": collection_data.get("version"),
                            "last_updated": collection_data.get("installed_at"),
                        }
                    )

                    # Check file consistency
                    expected_files = collection_data.get("files", [])
                    storage_type = collection_data.get("storage_type", "project")

                    # Get actual files
                    actual_fragments = self.storage_manager.list_fragments(
                        storage_type=storage_type, collection=collection_name
                    )
                    actual_files = {f.name for f in actual_fragments}
                    expected_files_set = set(expected_files)

                    status["files_count"] = len(actual_files)
                    status["missing_files"] = list(expected_files_set - actual_files)
                    status["extra_files"] = list(actual_files - expected_files_set)

                    # Check integrity (simplified)
                    status["integrity_valid"] = len(status["missing_files"]) == 0

            except Exception as e:
                logger.warning(f"Could not check collection status: {e}")

        return status
