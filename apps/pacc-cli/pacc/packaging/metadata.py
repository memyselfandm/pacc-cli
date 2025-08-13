"""Package metadata management and manifest generation."""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import hashlib
import logging

from ..core import PathNormalizer
from .formats import BasePackage, PackageFormat, PackageInfo


logger = logging.getLogger(__name__)


@dataclass
class FileMetadata:
    """Metadata for individual files in a package."""
    
    path: str
    size: int
    checksum: str
    modified: float
    permissions: Optional[str] = None
    content_type: Optional[str] = None
    
    @classmethod
    def from_path(cls, file_path: Path, base_path: Optional[Path] = None) -> 'FileMetadata':
        """Create file metadata from path.
        
        Args:
            file_path: Path to file
            base_path: Base path for relative path calculation
            
        Returns:
            File metadata instance
        """
        stat = file_path.stat()
        
        # Calculate relative path
        if base_path:
            try:
                rel_path = file_path.relative_to(base_path)
            except ValueError:
                rel_path = file_path
        else:
            rel_path = file_path
        
        # Calculate checksum
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        checksum = hasher.hexdigest()
        
        # Get permissions
        permissions = oct(stat.st_mode)[-3:]
        
        return cls(
            path=str(rel_path),
            size=stat.st_size,
            checksum=checksum,
            modified=stat.st_mtime,
            permissions=permissions
        )


@dataclass
class DependencyInfo:
    """Information about package dependencies."""
    
    name: str
    version: Optional[str] = None
    source: Optional[str] = None
    optional: bool = False
    description: Optional[str] = None


@dataclass
class PackageMetadata:
    """Comprehensive package metadata."""
    
    # Basic information
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    author: Optional[str] = None
    email: Optional[str] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    
    # Package details
    format: Optional[PackageFormat] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    size_bytes: int = 0
    file_count: int = 0
    checksum: Optional[str] = None
    
    # Content information
    files: List[FileMetadata] = field(default_factory=list)
    dependencies: List[DependencyInfo] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    
    # Installation information
    install_path: Optional[str] = None
    install_time: Optional[str] = None
    installed_by: Optional[str] = None
    
    # Custom metadata
    custom: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_package(cls, package: BasePackage) -> 'PackageMetadata':
        """Create metadata from package.
        
        Args:
            package: Package to extract metadata from
            
        Returns:
            Package metadata instance
        """
        metadata = cls(
            name=package.info.name,
            version=package.info.version or "1.0.0",
            description=package.info.description,
            author=package.info.author,
            format=package.get_format(),
            created_at=package.info.created_at or datetime.now().isoformat(),
            size_bytes=package.get_size(),
            checksum=package.calculate_checksum()
        )
        
        # Add file information
        try:
            contents = package.list_contents()
            metadata.file_count = len(contents)
            
            # Create file metadata for each file
            if package.path.is_dir():
                base_path = package.path
                for content_path in contents:
                    full_path = package.path / content_path
                    if full_path.exists() and full_path.is_file():
                        file_meta = FileMetadata.from_path(full_path, base_path)
                        metadata.files.append(file_meta)
            elif package.path.is_file():
                file_meta = FileMetadata.from_path(package.path)
                metadata.files.append(file_meta)
                
        except Exception as e:
            logger.warning(f"Failed to extract file metadata: {e}")
        
        return metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary.
        
        Returns:
            Dictionary representation
        """
        data = asdict(self)
        
        # Convert enums to strings
        if self.format:
            data['format'] = self.format.value
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PackageMetadata':
        """Create metadata from dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            Package metadata instance
        """
        # Handle format enum
        if 'format' in data and isinstance(data['format'], str):
            try:
                data['format'] = PackageFormat(data['format'])
            except ValueError:
                data['format'] = None
        
        # Convert file metadata
        if 'files' in data:
            files = []
            for file_data in data['files']:
                if isinstance(file_data, dict):
                    files.append(FileMetadata(**file_data))
                else:
                    files.append(file_data)
            data['files'] = files
        
        # Convert dependency info
        if 'dependencies' in data:
            deps = []
            for dep_data in data['dependencies']:
                if isinstance(dep_data, dict):
                    deps.append(DependencyInfo(**dep_data))
                else:
                    deps.append(dep_data)
            data['dependencies'] = deps
        
        return cls(**data)
    
    def save_to_file(self, file_path: Union[str, Path]) -> None:
        """Save metadata to JSON file.
        
        Args:
            file_path: Path to save metadata file
        """
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved package metadata to {path}")
    
    @classmethod
    def load_from_file(cls, file_path: Union[str, Path]) -> 'PackageMetadata':
        """Load metadata from JSON file.
        
        Args:
            file_path: Path to metadata file
            
        Returns:
            Package metadata instance
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    def add_dependency(
        self,
        name: str,
        version: Optional[str] = None,
        source: Optional[str] = None,
        optional: bool = False,
        description: Optional[str] = None
    ) -> None:
        """Add dependency to metadata.
        
        Args:
            name: Dependency name
            version: Dependency version
            source: Dependency source
            optional: Whether dependency is optional
            description: Dependency description
        """
        dep = DependencyInfo(
            name=name,
            version=version,
            source=source,
            optional=optional,
            description=description
        )
        self.dependencies.append(dep)
    
    def add_tag(self, tag: str) -> None:
        """Add tag to metadata.
        
        Args:
            tag: Tag to add
        """
        if tag not in self.tags:
            self.tags.append(tag)
    
    def add_category(self, category: str) -> None:
        """Add category to metadata.
        
        Args:
            category: Category to add
        """
        if category not in self.categories:
            self.categories.append(category)
    
    def update_install_info(
        self,
        install_path: Union[str, Path],
        installed_by: Optional[str] = None
    ) -> None:
        """Update installation information.
        
        Args:
            install_path: Path where package was installed
            installed_by: Who/what installed the package
        """
        self.install_path = str(install_path)
        self.install_time = datetime.now().isoformat()
        self.installed_by = installed_by or "pacc"
        self.updated_at = self.install_time
    
    def verify_integrity(self, package: BasePackage) -> bool:
        """Verify package integrity against metadata.
        
        Args:
            package: Package to verify
            
        Returns:
            True if package matches metadata
        """
        try:
            # Check basic properties
            if self.size_bytes != package.get_size():
                logger.warning("Package size mismatch")
                return False
            
            if self.checksum != package.calculate_checksum():
                logger.warning("Package checksum mismatch")
                return False
            
            # Check file count
            contents = package.list_contents()
            if self.file_count != len(contents):
                logger.warning("File count mismatch")
                return False
            
            # Verify individual files if possible
            if package.path.is_dir():
                for file_meta in self.files:
                    file_path = package.path / file_meta.path
                    if not file_path.exists():
                        logger.warning(f"Missing file: {file_meta.path}")
                        return False
                    
                    # Check file size
                    if file_path.stat().st_size != file_meta.size:
                        logger.warning(f"File size mismatch: {file_meta.path}")
                        return False
                    
                    # Check file checksum
                    hasher = hashlib.sha256()
                    with open(file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            hasher.update(chunk)
                    
                    if hasher.hexdigest() != file_meta.checksum:
                        logger.warning(f"File checksum mismatch: {file_meta.path}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Integrity verification failed: {e}")
            return False


class ManifestGenerator:
    """Generator for package manifests and metadata."""
    
    def __init__(self, include_checksums: bool = True, include_permissions: bool = True):
        """Initialize manifest generator.
        
        Args:
            include_checksums: Whether to include file checksums
            include_permissions: Whether to include file permissions
        """
        self.include_checksums = include_checksums
        self.include_permissions = include_permissions
    
    def generate_manifest(
        self,
        package: BasePackage,
        output_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Generate package manifest.
        
        Args:
            package: Package to generate manifest for
            output_path: Optional path to save manifest
            
        Returns:
            Manifest dictionary
        """
        metadata = PackageMetadata.from_package(package)
        
        # Create manifest structure
        manifest = {
            'manifest_version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'generator': 'pacc-manifest-generator',
            'package': metadata.to_dict()
        }
        
        # Add file listing with details
        file_listing = []
        for file_meta in metadata.files:
            file_info = {
                'path': file_meta.path,
                'size': file_meta.size,
                'modified': file_meta.modified
            }
            
            if self.include_checksums:
                file_info['checksum'] = file_meta.checksum
            
            if self.include_permissions and file_meta.permissions:
                file_info['permissions'] = file_meta.permissions
            
            if file_meta.content_type:
                file_info['content_type'] = file_meta.content_type
            
            file_listing.append(file_info)
        
        manifest['files'] = file_listing
        
        # Save manifest if output path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Generated manifest: {output_file}")
        
        return manifest
    
    def generate_dependency_manifest(
        self,
        packages: List[BasePackage],
        output_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """Generate dependency manifest for multiple packages.
        
        Args:
            packages: List of packages
            output_path: Optional path to save manifest
            
        Returns:
            Dependency manifest dictionary
        """
        manifest = {
            'manifest_version': '1.0',
            'type': 'dependency_manifest',
            'generated_at': datetime.now().isoformat(),
            'generator': 'pacc-manifest-generator',
            'package_count': len(packages),
            'packages': []
        }
        
        total_size = 0
        
        for package in packages:
            metadata = PackageMetadata.from_package(package)
            
            package_info = {
                'name': metadata.name,
                'version': metadata.version,
                'format': metadata.format.value if metadata.format else None,
                'size_bytes': metadata.size_bytes,
                'file_count': metadata.file_count,
                'checksum': metadata.checksum,
                'path': str(package.path)
            }
            
            if metadata.dependencies:
                package_info['dependencies'] = [
                    {
                        'name': dep.name,
                        'version': dep.version,
                        'optional': dep.optional
                    }
                    for dep in metadata.dependencies
                ]
            
            manifest['packages'].append(package_info)
            total_size += metadata.size_bytes
        
        manifest['total_size_bytes'] = total_size
        
        # Save manifest if output path provided
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Generated dependency manifest: {output_file}")
        
        return manifest
    
    def validate_manifest(self, manifest_path: Union[str, Path]) -> tuple[bool, List[str]]:
        """Validate manifest file.
        
        Args:
            manifest_path: Path to manifest file
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            
            # Check required fields
            required_fields = ['manifest_version', 'generated_at', 'package']
            for field in required_fields:
                if field not in manifest:
                    errors.append(f"Missing required field: {field}")
            
            # Validate manifest version
            if manifest.get('manifest_version') not in ['1.0']:
                errors.append(f"Unsupported manifest version: {manifest.get('manifest_version')}")
            
            # Validate package information
            package_info = manifest.get('package', {})
            if not package_info.get('name'):
                errors.append("Package name is required")
            
            if not package_info.get('version'):
                errors.append("Package version is required")
            
            # Validate file listing
            files = manifest.get('files', [])
            for i, file_info in enumerate(files):
                if not file_info.get('path'):
                    errors.append(f"File {i}: missing path")
                
                if 'size' in file_info and not isinstance(file_info['size'], int):
                    errors.append(f"File {i}: invalid size type")
                
                if 'checksum' in file_info and not isinstance(file_info['checksum'], str):
                    errors.append(f"File {i}: invalid checksum type")
            
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")
        except Exception as e:
            errors.append(f"Validation error: {e}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def compare_manifests(
        self,
        manifest1_path: Union[str, Path],
        manifest2_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """Compare two manifests.
        
        Args:
            manifest1_path: Path to first manifest
            manifest2_path: Path to second manifest
            
        Returns:
            Comparison result dictionary
        """
        try:
            with open(manifest1_path, 'r') as f:
                manifest1 = json.load(f)
            
            with open(manifest2_path, 'r') as f:
                manifest2 = json.load(f)
            
            comparison = {
                'identical': False,
                'differences': [],
                'added_files': [],
                'removed_files': [],
                'modified_files': []
            }
            
            # Compare basic package info
            pkg1 = manifest1.get('package', {})
            pkg2 = manifest2.get('package', {})
            
            for field in ['name', 'version', 'size_bytes', 'file_count', 'checksum']:
                if pkg1.get(field) != pkg2.get(field):
                    comparison['differences'].append({
                        'field': f'package.{field}',
                        'value1': pkg1.get(field),
                        'value2': pkg2.get(field)
                    })
            
            # Compare file listings
            files1 = {f['path']: f for f in manifest1.get('files', [])}
            files2 = {f['path']: f for f in manifest2.get('files', [])}
            
            # Find added/removed files
            all_paths = set(files1.keys()) | set(files2.keys())
            
            for path in all_paths:
                if path in files1 and path not in files2:
                    comparison['removed_files'].append(path)
                elif path not in files1 and path in files2:
                    comparison['added_files'].append(path)
                elif path in files1 and path in files2:
                    # Compare file attributes
                    f1, f2 = files1[path], files2[path]
                    if f1.get('checksum') != f2.get('checksum') or f1.get('size') != f2.get('size'):
                        comparison['modified_files'].append({
                            'path': path,
                            'size1': f1.get('size'),
                            'size2': f2.get('size'),
                            'checksum1': f1.get('checksum'),
                            'checksum2': f2.get('checksum')
                        })
            
            # Check if manifests are identical
            comparison['identical'] = (
                len(comparison['differences']) == 0 and
                len(comparison['added_files']) == 0 and
                len(comparison['removed_files']) == 0 and
                len(comparison['modified_files']) == 0
            )
            
            return comparison
            
        except Exception as e:
            return {
                'error': str(e),
                'identical': False
            }