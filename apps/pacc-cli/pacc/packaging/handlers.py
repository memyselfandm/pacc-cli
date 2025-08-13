"""Package handlers for managing different package types."""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

from ..core import DirectoryScanner, FilePathValidator
from ..errors import PACCError
from .formats import BasePackage, PackageFormat, create_package
from .converters import PackageConverter, ConversionResult


logger = logging.getLogger(__name__)


class PackageHandler(ABC):
    """Base class for package handlers."""
    
    def __init__(self, validator: Optional[FilePathValidator] = None):
        """Initialize package handler.
        
        Args:
            validator: File path validator
        """
        self.validator = validator or FilePathValidator()
    
    @abstractmethod
    def get_supported_formats(self) -> List[PackageFormat]:
        """Get supported package formats.
        
        Returns:
            List of supported formats
        """
        pass
    
    @abstractmethod
    async def install_package(
        self,
        package: BasePackage,
        destination: Union[str, Path],
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Install package to destination.
        
        Args:
            package: Package to install
            destination: Installation destination
            options: Installation options
            
        Returns:
            True if installation succeeded
        """
        pass
    
    @abstractmethod
    async def uninstall_package(
        self,
        package_info: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Uninstall previously installed package.
        
        Args:
            package_info: Information about installed package
            options: Uninstallation options
            
        Returns:
            True if uninstallation succeeded
        """
        pass
    
    def can_handle(self, package_format: PackageFormat) -> bool:
        """Check if handler can handle the package format.
        
        Args:
            package_format: Package format to check
            
        Returns:
            True if format is supported
        """
        return package_format in self.get_supported_formats()


class FilePackageHandler(PackageHandler):
    """Handler for file-based packages (single and multi-file)."""
    
    def get_supported_formats(self) -> List[PackageFormat]:
        """Get supported formats."""
        return [
            PackageFormat.SINGLE_FILE,
            PackageFormat.MULTI_FILE
        ]
    
    async def install_package(
        self,
        package: BasePackage,
        destination: Union[str, Path],
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Install file package.
        
        Args:
            package: Package to install
            destination: Installation destination
            options: Installation options
            
        Returns:
            True if installation succeeded
        """
        options = options or {}
        dest_path = Path(destination)
        
        try:
            # Validate package
            if not package.validate():
                logger.error(f"Package validation failed: {package.path}")
                return False
            
            # Check destination safety
            if not self.validator.is_safe_directory(dest_path.parent):
                logger.error(f"Unsafe destination directory: {dest_path.parent}")
                return False
            
            # Extract package
            extracted_path = package.extract_to(dest_path.parent)
            
            # Handle overwrite options
            overwrite = options.get('overwrite', False)
            if dest_path.exists() and not overwrite:
                logger.error(f"Destination exists and overwrite=False: {dest_path}")
                return False
            
            # Move to final destination if needed
            if extracted_path != dest_path:
                if dest_path.exists():
                    if dest_path.is_dir():
                        import shutil
                        shutil.rmtree(dest_path)
                    else:
                        dest_path.unlink()
                
                extracted_path.rename(dest_path)
            
            logger.info(f"Installed file package to {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to install file package: {e}")
            return False
    
    async def uninstall_package(
        self,
        package_info: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Uninstall file package.
        
        Args:
            package_info: Package installation information
            options: Uninstallation options
            
        Returns:
            True if uninstallation succeeded
        """
        try:
            install_path = Path(package_info['install_path'])
            
            if not install_path.exists():
                logger.warning(f"Package not found for uninstall: {install_path}")
                return True  # Already gone
            
            # Remove installed files
            if install_path.is_file():
                install_path.unlink()
            elif install_path.is_dir():
                import shutil
                shutil.rmtree(install_path)
            
            logger.info(f"Uninstalled file package from {install_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to uninstall file package: {e}")
            return False


class ArchivePackageHandler(PackageHandler):
    """Handler for archive-based packages (ZIP, TAR, etc.)."""
    
    def __init__(self, validator: Optional[FilePathValidator] = None):
        """Initialize archive package handler."""
        super().__init__(validator)
        self.converter = PackageConverter()
    
    def get_supported_formats(self) -> List[PackageFormat]:
        """Get supported formats."""
        return [
            PackageFormat.ZIP_ARCHIVE,
            PackageFormat.TAR_ARCHIVE,
            PackageFormat.TAR_GZ_ARCHIVE
        ]
    
    async def install_package(
        self,
        package: BasePackage,
        destination: Union[str, Path],
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Install archive package.
        
        Args:
            package: Package to install
            destination: Installation destination
            options: Installation options
            
        Returns:
            True if installation succeeded
        """
        options = options or {}
        dest_path = Path(destination)
        
        try:
            # Validate package
            if not package.validate():
                logger.error(f"Archive validation failed: {package.path}")
                return False
            
            # Check destination safety
            if not self.validator.is_safe_directory(dest_path.parent):
                logger.error(f"Unsafe destination directory: {dest_path.parent}")
                return False
            
            # Handle format conversion if requested
            target_format = options.get('convert_to')
            if target_format and target_format != package.get_format():
                logger.debug(f"Converting archive format to {target_format}")
                
                # Create temporary converted package
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=self._get_format_extension(target_format), delete=False) as tmp_file:
                    tmp_path = Path(tmp_file.name)
                
                try:
                    result = self.converter.convert_file(
                        package.path, target_format, tmp_path, options.get('conversion_options')
                    )
                    
                    if not result.success:
                        logger.error(f"Format conversion failed: {result.error_message}")
                        return False
                    
                    # Use converted package
                    package = create_package(tmp_path, target_format)
                    
                finally:
                    # Clean up temp file when done
                    import atexit
                    atexit.register(lambda: tmp_path.unlink(missing_ok=True))
            
            # Extract package
            extracted_path = package.extract_to(dest_path.parent)
            
            # Handle overwrite options
            overwrite = options.get('overwrite', False)
            if dest_path.exists() and not overwrite:
                logger.error(f"Destination exists and overwrite=False: {dest_path}")
                return False
            
            # Move to final destination if needed
            if extracted_path != dest_path:
                if dest_path.exists():
                    import shutil
                    if dest_path.is_dir():
                        shutil.rmtree(dest_path)
                    else:
                        dest_path.unlink()
                
                extracted_path.rename(dest_path)
            
            logger.info(f"Installed archive package to {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to install archive package: {e}")
            return False
    
    async def uninstall_package(
        self,
        package_info: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Uninstall archive package.
        
        Args:
            package_info: Package installation information
            options: Uninstallation options
            
        Returns:
            True if uninstallation succeeded
        """
        try:
            install_path = Path(package_info['install_path'])
            
            if not install_path.exists():
                logger.warning(f"Package not found for uninstall: {install_path}")
                return True  # Already gone
            
            # Remove installed files/directories
            if install_path.is_file():
                install_path.unlink()
            elif install_path.is_dir():
                import shutil
                shutil.rmtree(install_path)
            
            logger.info(f"Uninstalled archive package from {install_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to uninstall archive package: {e}")
            return False
    
    def _get_format_extension(self, format: PackageFormat) -> str:
        """Get file extension for package format."""
        format_extensions = {
            PackageFormat.ZIP_ARCHIVE: '.zip',
            PackageFormat.TAR_ARCHIVE: '.tar',
            PackageFormat.TAR_GZ_ARCHIVE: '.tar.gz',
        }
        return format_extensions.get(format, '.pkg')


class UniversalPackageHandler(PackageHandler):
    """Universal package handler that delegates to specialized handlers."""
    
    def __init__(self, validator: Optional[FilePathValidator] = None):
        """Initialize universal package handler."""
        super().__init__(validator)
        
        # Initialize specialized handlers
        self.file_handler = FilePackageHandler(validator)
        self.archive_handler = ArchivePackageHandler(validator)
        
        # Map formats to handlers
        self.format_handlers = {}
        
        for format in self.file_handler.get_supported_formats():
            self.format_handlers[format] = self.file_handler
        
        for format in self.archive_handler.get_supported_formats():
            self.format_handlers[format] = self.archive_handler
    
    def get_supported_formats(self) -> List[PackageFormat]:
        """Get all supported formats."""
        return list(self.format_handlers.keys())
    
    async def install_package(
        self,
        package: BasePackage,
        destination: Union[str, Path],
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Install package using appropriate handler.
        
        Args:
            package: Package to install
            destination: Installation destination
            options: Installation options
            
        Returns:
            True if installation succeeded
        """
        package_format = package.get_format()
        
        if package_format not in self.format_handlers:
            logger.error(f"Unsupported package format: {package_format}")
            return False
        
        handler = self.format_handlers[package_format]
        return await handler.install_package(package, destination, options)
    
    async def uninstall_package(
        self,
        package_info: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Uninstall package using appropriate handler.
        
        Args:
            package_info: Package installation information
            options: Uninstallation options
            
        Returns:
            True if uninstallation succeeded
        """
        package_format = PackageFormat(package_info.get('format', 'unknown'))
        
        if package_format not in self.format_handlers:
            logger.error(f"Unsupported package format for uninstall: {package_format}")
            return False
        
        handler = self.format_handlers[package_format]
        return await handler.uninstall_package(package_info, options)
    
    async def install_from_path(
        self,
        source_path: Union[str, Path],
        destination: Union[str, Path],
        format_hint: Optional[PackageFormat] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Install package from path.
        
        Args:
            source_path: Path to package
            destination: Installation destination
            format_hint: Optional format hint
            options: Installation options
            
        Returns:
            True if installation succeeded
        """
        try:
            package = create_package(source_path, format_hint)
            return await self.install_package(package, destination, options)
        except Exception as e:
            logger.error(f"Failed to install package from {source_path}: {e}")
            return False
    
    async def batch_install(
        self,
        packages: List[tuple[Union[str, Path], Union[str, Path]]],
        options: Optional[Dict[str, Any]] = None
    ) -> List[bool]:
        """Install multiple packages.
        
        Args:
            packages: List of (source_path, destination) tuples
            options: Installation options
            
        Returns:
            List of success flags
        """
        results = []
        
        # Process packages concurrently with semaphore
        max_concurrent = options.get('max_concurrent', 5) if options else 5
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def install_single(source_path: Union[str, Path], destination: Union[str, Path]) -> bool:
            async with semaphore:
                return await self.install_from_path(source_path, destination, options=options)
        
        # Create tasks for all installations
        tasks = [
            install_single(source_path, destination)
            for source_path, destination in packages
        ]
        
        # Execute with progress logging
        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            
            if completed % 10 == 0 or completed == len(packages):
                logger.info(f"Batch install progress: {completed}/{len(packages)}")
        
        successful = sum(results)
        logger.info(f"Batch install completed: {successful}/{len(packages)} successful")
        
        return results
    
    def get_handler_for_format(self, package_format: PackageFormat) -> Optional[PackageHandler]:
        """Get handler for specific format.
        
        Args:
            package_format: Package format
            
        Returns:
            Handler instance or None if not supported
        """
        return self.format_handlers.get(package_format)