"""Package format definitions and implementations."""

import hashlib
import json
import tarfile
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, BinaryIO
import tempfile
import shutil
import logging

from ..core import PathNormalizer
from ..errors import PACCError


logger = logging.getLogger(__name__)


class PackageFormat(Enum):
    """Supported package formats."""
    SINGLE_FILE = "single_file"
    MULTI_FILE = "multi_file"
    ZIP_ARCHIVE = "zip_archive"
    TAR_ARCHIVE = "tar_archive"
    TAR_GZ_ARCHIVE = "tar_gz_archive"
    CUSTOM = "custom"


@dataclass
class PackageInfo:
    """Information about a package."""
    
    format: PackageFormat
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    created_at: Optional[str] = None
    size_bytes: int = 0
    file_count: int = 0
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BasePackage(ABC):
    """Base class for all package formats."""
    
    def __init__(self, path: Union[str, Path], info: Optional[PackageInfo] = None):
        """Initialize base package.
        
        Args:
            path: Path to package file or directory
            info: Package information
        """
        self.path = Path(path)
        self.info = info or PackageInfo(
            format=self.get_format(),
            name=self.path.stem
        )
    
    @abstractmethod
    def get_format(self) -> PackageFormat:
        """Get package format."""
        pass
    
    @abstractmethod
    def extract_to(self, destination: Union[str, Path]) -> Path:
        """Extract package contents to destination.
        
        Args:
            destination: Destination directory
            
        Returns:
            Path to extracted contents
        """
        pass
    
    @abstractmethod
    def list_contents(self) -> List[str]:
        """List contents of package.
        
        Returns:
            List of file paths in package
        """
        pass
    
    @abstractmethod
    def get_file_content(self, file_path: str) -> bytes:
        """Get content of specific file in package.
        
        Args:
            file_path: Path to file within package
            
        Returns:
            File content as bytes
        """
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate package integrity.
        
        Returns:
            True if package is valid
        """
        pass
    
    def get_size(self) -> int:
        """Get package size in bytes.
        
        Returns:
            Package size in bytes
        """
        try:
            if self.path.is_file():
                return self.path.stat().st_size
            elif self.path.is_dir():
                total_size = 0
                for file_path in self.path.rglob('*'):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                return total_size
            return 0
        except OSError:
            return 0
    
    def calculate_checksum(self, algorithm: str = "sha256") -> str:
        """Calculate package checksum.
        
        Args:
            algorithm: Hash algorithm to use
            
        Returns:
            Hexadecimal checksum string
        """
        hasher = hashlib.new(algorithm)
        
        if self.path.is_file():
            # Single file checksum
            with open(self.path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
        elif self.path.is_dir():
            # Directory checksum (all files sorted by path)
            file_paths = sorted(self.path.rglob('*'))
            for file_path in file_paths:
                if file_path.is_file():
                    # Include relative path in hash
                    rel_path = file_path.relative_to(self.path)
                    hasher.update(str(rel_path).encode())
                    
                    # Include file content in hash
                    with open(file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(8192), b""):
                            hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def update_info(self) -> None:
        """Update package info with current state."""
        self.info.size_bytes = self.get_size()
        self.info.file_count = len(self.list_contents())
        self.info.checksum = self.calculate_checksum()


class SingleFilePackage(BasePackage):
    """Package containing a single file."""
    
    def get_format(self) -> PackageFormat:
        """Get package format."""
        return PackageFormat.SINGLE_FILE
    
    def extract_to(self, destination: Union[str, Path]) -> Path:
        """Extract file to destination.
        
        Args:
            destination: Destination directory
            
        Returns:
            Path to extracted file
        """
        dest_path = Path(destination)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        target_file = dest_path / self.path.name
        
        if self.path.is_file():
            shutil.copy2(self.path, target_file)
            logger.debug(f"Extracted single file to {target_file}")
            return target_file
        else:
            raise PACCError(f"Source file does not exist: {self.path}")
    
    def list_contents(self) -> List[str]:
        """List contents (just the single file).
        
        Returns:
            List containing the single file name
        """
        if self.path.exists():
            return [self.path.name]
        return []
    
    def get_file_content(self, file_path: str) -> bytes:
        """Get file content.
        
        Args:
            file_path: Should match the file name
            
        Returns:
            File content as bytes
        """
        if file_path == self.path.name and self.path.is_file():
            with open(self.path, 'rb') as f:
                return f.read()
        else:
            raise PACCError(f"File not found in package: {file_path}")
    
    def validate(self) -> bool:
        """Validate package (check if file exists and is readable).
        
        Returns:
            True if valid
        """
        try:
            return self.path.is_file() and self.path.stat().st_size > 0
        except OSError:
            return False


class MultiFilePackage(BasePackage):
    """Package containing multiple files in a directory."""
    
    def get_format(self) -> PackageFormat:
        """Get package format."""
        return PackageFormat.MULTI_FILE
    
    def extract_to(self, destination: Union[str, Path]) -> Path:
        """Extract directory contents to destination.
        
        Args:
            destination: Destination directory
            
        Returns:
            Path to extracted directory
        """
        dest_path = Path(destination)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        target_dir = dest_path / self.path.name
        
        if self.path.is_dir():
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(self.path, target_dir)
            logger.debug(f"Extracted multi-file package to {target_dir}")
            return target_dir
        else:
            raise PACCError(f"Source directory does not exist: {self.path}")
    
    def list_contents(self) -> List[str]:
        """List all files in directory.
        
        Returns:
            List of relative file paths
        """
        if not self.path.is_dir():
            return []
        
        contents = []
        for file_path in self.path.rglob('*'):
            if file_path.is_file():
                rel_path = file_path.relative_to(self.path)
                contents.append(str(rel_path))
        
        return sorted(contents)
    
    def get_file_content(self, file_path: str) -> bytes:
        """Get content of specific file.
        
        Args:
            file_path: Relative path to file within package
            
        Returns:
            File content as bytes
        """
        full_path = self.path / file_path
        
        if full_path.is_file() and full_path.is_relative_to(self.path):
            with open(full_path, 'rb') as f:
                return f.read()
        else:
            raise PACCError(f"File not found in package: {file_path}")
    
    def validate(self) -> bool:
        """Validate package (check if directory exists and contains files).
        
        Returns:
            True if valid
        """
        try:
            if not self.path.is_dir():
                return False
            
            # Check if directory contains at least one file
            for item in self.path.rglob('*'):
                if item.is_file():
                    return True
            
            return False  # Empty directory
        except OSError:
            return False


class ArchivePackage(BasePackage):
    """Base class for archive-based packages (ZIP, TAR, etc.)."""
    
    def __init__(self, path: Union[str, Path], info: Optional[PackageInfo] = None):
        """Initialize archive package.
        
        Args:
            path: Path to archive file
            info: Package information
        """
        super().__init__(path, info)
        self._temp_dir: Optional[Path] = None
    
    def __del__(self):
        """Clean up temporary directory."""
        self._cleanup_temp()
    
    def _cleanup_temp(self) -> None:
        """Clean up temporary extraction directory."""
        if self._temp_dir and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir)
                self._temp_dir = None
            except OSError as e:
                logger.warning(f"Failed to clean up temp directory {self._temp_dir}: {e}")
    
    def _get_temp_dir(self) -> Path:
        """Get or create temporary extraction directory.
        
        Returns:
            Path to temporary directory
        """
        if self._temp_dir is None or not self._temp_dir.exists():
            self._temp_dir = Path(tempfile.mkdtemp(prefix="pacc_"))
        return self._temp_dir
    
    @abstractmethod
    def _extract_archive(self, destination: Path) -> None:
        """Extract archive to destination (implementation specific).
        
        Args:
            destination: Destination directory
        """
        pass
    
    @abstractmethod
    def _list_archive_contents(self) -> List[str]:
        """List archive contents (implementation specific).
        
        Returns:
            List of file paths in archive
        """
        pass
    
    @abstractmethod
    def _get_archive_file_content(self, file_path: str) -> bytes:
        """Get file content from archive (implementation specific).
        
        Args:
            file_path: Path to file within archive
            
        Returns:
            File content as bytes
        """
        pass
    
    def extract_to(self, destination: Union[str, Path]) -> Path:
        """Extract archive to destination.
        
        Args:
            destination: Destination directory
            
        Returns:
            Path to extracted contents
        """
        dest_path = Path(destination)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        target_dir = dest_path / self.path.stem
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir()
        
        self._extract_archive(target_dir)
        logger.debug(f"Extracted archive to {target_dir}")
        return target_dir
    
    def list_contents(self) -> List[str]:
        """List archive contents.
        
        Returns:
            List of file paths in archive
        """
        try:
            return self._list_archive_contents()
        except Exception as e:
            logger.error(f"Failed to list archive contents: {e}")
            return []
    
    def get_file_content(self, file_path: str) -> bytes:
        """Get file content from archive.
        
        Args:
            file_path: Path to file within archive
            
        Returns:
            File content as bytes
        """
        return self._get_archive_file_content(file_path)
    
    def validate(self) -> bool:
        """Validate archive integrity.
        
        Returns:
            True if archive is valid
        """
        try:
            # Try to list contents - if this works, archive is likely valid
            contents = self.list_contents()
            return len(contents) > 0
        except Exception:
            return False


class ZipPackage(ArchivePackage):
    """ZIP archive package."""
    
    def get_format(self) -> PackageFormat:
        """Get package format."""
        return PackageFormat.ZIP_ARCHIVE
    
    def _extract_archive(self, destination: Path) -> None:
        """Extract ZIP archive to destination.
        
        Args:
            destination: Destination directory
        """
        with zipfile.ZipFile(self.path, 'r') as zip_file:
            # Security: validate file paths to prevent zip slip
            for member in zip_file.namelist():
                if os.path.isabs(member) or ".." in member:
                    raise PACCError(f"Unsafe path in ZIP archive: {member}")
            
            zip_file.extractall(destination)
    
    def _list_archive_contents(self) -> List[str]:
        """List ZIP archive contents.
        
        Returns:
            List of file paths in archive
        """
        with zipfile.ZipFile(self.path, 'r') as zip_file:
            return [name for name in zip_file.namelist() if not name.endswith('/')]
    
    def _get_archive_file_content(self, file_path: str) -> bytes:
        """Get file content from ZIP archive.
        
        Args:
            file_path: Path to file within archive
            
        Returns:
            File content as bytes
        """
        with zipfile.ZipFile(self.path, 'r') as zip_file:
            try:
                return zip_file.read(file_path)
            except KeyError:
                raise PACCError(f"File not found in ZIP archive: {file_path}")
    
    def validate(self) -> bool:
        """Validate ZIP archive.
        
        Returns:
            True if ZIP is valid
        """
        try:
            with zipfile.ZipFile(self.path, 'r') as zip_file:
                # Test the archive
                bad_file = zip_file.testzip()
                return bad_file is None
        except (zipfile.BadZipFile, OSError):
            return False


class TarPackage(ArchivePackage):
    """TAR archive package (including compressed variants)."""
    
    def __init__(
        self,
        path: Union[str, Path],
        compression: Optional[str] = None,
        info: Optional[PackageInfo] = None
    ):
        """Initialize TAR package.
        
        Args:
            path: Path to archive file
            compression: Compression type ('gz', 'bz2', 'xz', or None)
            info: Package information
        """
        super().__init__(path, info)
        self.compression = compression
        
        # Determine format based on compression
        if compression == 'gz':
            self.info.format = PackageFormat.TAR_GZ_ARCHIVE
        else:
            self.info.format = PackageFormat.TAR_ARCHIVE
    
    def get_format(self) -> PackageFormat:
        """Get package format."""
        return self.info.format
    
    def _get_tar_mode(self) -> str:
        """Get TAR file mode string.
        
        Returns:
            Mode string for tarfile.open()
        """
        if self.compression == 'gz':
            return 'r:gz'
        elif self.compression == 'bz2':
            return 'r:bz2'
        elif self.compression == 'xz':
            return 'r:xz'
        else:
            return 'r'
    
    def _extract_archive(self, destination: Path) -> None:
        """Extract TAR archive to destination.
        
        Args:
            destination: Destination directory
        """
        with tarfile.open(self.path, self._get_tar_mode()) as tar_file:
            # Security: validate file paths to prevent tar slip
            for member in tar_file.getmembers():
                if os.path.isabs(member.name) or ".." in member.name:
                    raise PACCError(f"Unsafe path in TAR archive: {member.name}")
            
            tar_file.extractall(destination)
    
    def _list_archive_contents(self) -> List[str]:
        """List TAR archive contents.
        
        Returns:
            List of file paths in archive
        """
        with tarfile.open(self.path, self._get_tar_mode()) as tar_file:
            return [member.name for member in tar_file.getmembers() if member.isfile()]
    
    def _get_archive_file_content(self, file_path: str) -> bytes:
        """Get file content from TAR archive.
        
        Args:
            file_path: Path to file within archive
            
        Returns:
            File content as bytes
        """
        with tarfile.open(self.path, self._get_tar_mode()) as tar_file:
            try:
                member = tar_file.getmember(file_path)
                file_obj = tar_file.extractfile(member)
                if file_obj is None:
                    raise PACCError(f"Cannot extract file from TAR archive: {file_path}")
                return file_obj.read()
            except KeyError:
                raise PACCError(f"File not found in TAR archive: {file_path}")
    
    def validate(self) -> bool:
        """Validate TAR archive.
        
        Returns:
            True if TAR is valid
        """
        try:
            with tarfile.open(self.path, self._get_tar_mode()) as tar_file:
                # Try to list contents - if this works, archive is likely valid
                tar_file.getnames()
                return True
        except (tarfile.TarError, OSError):
            return False


def create_package(
    path: Union[str, Path],
    format_hint: Optional[PackageFormat] = None
) -> BasePackage:
    """Create appropriate package instance based on path and format.
    
    Args:
        path: Path to package file or directory
        format_hint: Optional format hint
        
    Returns:
        Package instance
    """
    path_obj = Path(path)
    
    # Determine format if not provided
    if format_hint is None:
        if path_obj.is_file():
            suffix = path_obj.suffix.lower()
            if suffix == '.zip':
                format_hint = PackageFormat.ZIP_ARCHIVE
            elif suffix in ['.tar', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz']:
                if suffix in ['.tar.gz', '.tgz']:
                    format_hint = PackageFormat.TAR_GZ_ARCHIVE
                else:
                    format_hint = PackageFormat.TAR_ARCHIVE
            else:
                format_hint = PackageFormat.SINGLE_FILE
        elif path_obj.is_dir():
            format_hint = PackageFormat.MULTI_FILE
        else:
            raise PACCError(f"Cannot determine format for path: {path}")
    
    # Create appropriate package instance
    if format_hint == PackageFormat.SINGLE_FILE:
        return SingleFilePackage(path)
    elif format_hint == PackageFormat.MULTI_FILE:
        return MultiFilePackage(path)
    elif format_hint == PackageFormat.ZIP_ARCHIVE:
        return ZipPackage(path)
    elif format_hint in [PackageFormat.TAR_ARCHIVE, PackageFormat.TAR_GZ_ARCHIVE]:
        compression = 'gz' if format_hint == PackageFormat.TAR_GZ_ARCHIVE else None
        return TarPackage(path, compression=compression)
    else:
        raise PACCError(f"Unsupported package format: {format_hint}")


# Import os for security checks
import os