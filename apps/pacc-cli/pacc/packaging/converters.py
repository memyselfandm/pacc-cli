"""Format converters for transforming between package formats."""

import json
import tarfile
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import tempfile
import shutil
import logging

from ..core import PathNormalizer
from ..errors import PACCError
from .formats import (
    BasePackage, PackageFormat, PackageInfo,
    SingleFilePackage, MultiFilePackage, ZipPackage, TarPackage,
    create_package
)


logger = logging.getLogger(__name__)


class ConversionResult:
    """Result of a package conversion operation."""
    
    def __init__(
        self,
        success: bool,
        output_path: Optional[Path] = None,
        source_format: Optional[PackageFormat] = None,
        target_format: Optional[PackageFormat] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize conversion result.
        
        Args:
            success: Whether conversion succeeded
            output_path: Path to converted package
            source_format: Original package format
            target_format: Target package format
            error_message: Error message if conversion failed
            metadata: Additional metadata about conversion
        """
        self.success = success
        self.output_path = output_path
        self.source_format = source_format
        self.target_format = target_format
        self.error_message = error_message
        self.metadata = metadata or {}
    
    def __str__(self) -> str:
        """String representation of conversion result."""
        if self.success:
            return f"Conversion successful: {self.source_format} -> {self.target_format}"
        else:
            return f"Conversion failed: {self.error_message}"


class BaseConverter(ABC):
    """Base class for package format converters."""
    
    def __init__(self, preserve_metadata: bool = True):
        """Initialize converter.
        
        Args:
            preserve_metadata: Whether to preserve package metadata
        """
        self.preserve_metadata = preserve_metadata
    
    @abstractmethod
    def get_supported_conversions(self) -> List[tuple[PackageFormat, PackageFormat]]:
        """Get list of supported conversion pairs.
        
        Returns:
            List of (source_format, target_format) tuples
        """
        pass
    
    @abstractmethod
    def convert(
        self,
        source_package: BasePackage,
        target_format: PackageFormat,
        output_path: Union[str, Path],
        options: Optional[Dict[str, Any]] = None
    ) -> ConversionResult:
        """Convert package to target format.
        
        Args:
            source_package: Source package to convert
            target_format: Target format
            output_path: Output path for converted package
            options: Conversion options
            
        Returns:
            Conversion result
        """
        pass
    
    def can_convert(
        self,
        source_format: PackageFormat,
        target_format: PackageFormat
    ) -> bool:
        """Check if conversion is supported.
        
        Args:
            source_format: Source package format
            target_format: Target package format
            
        Returns:
            True if conversion is supported
        """
        supported = self.get_supported_conversions()
        return (source_format, target_format) in supported
    
    def _preserve_package_info(
        self,
        source_package: BasePackage,
        target_package: BasePackage
    ) -> None:
        """Preserve package info during conversion.
        
        Args:
            source_package: Source package
            target_package: Target package
        """
        if not self.preserve_metadata:
            return
        
        # Copy relevant info fields
        target_package.info.name = source_package.info.name
        target_package.info.version = source_package.info.version
        target_package.info.description = source_package.info.description
        target_package.info.author = source_package.info.author
        target_package.info.created_at = source_package.info.created_at
        target_package.info.metadata.update(source_package.info.metadata)
        
        # Update computed fields
        target_package.update_info()


class UniversalConverter(BaseConverter):
    """Universal converter that can handle any format conversion."""
    
    def get_supported_conversions(self) -> List[tuple[PackageFormat, PackageFormat]]:
        """Get all possible conversion pairs."""
        formats = [
            PackageFormat.SINGLE_FILE,
            PackageFormat.MULTI_FILE,
            PackageFormat.ZIP_ARCHIVE,
            PackageFormat.TAR_ARCHIVE,
            PackageFormat.TAR_GZ_ARCHIVE
        ]
        
        conversions = []
        for source in formats:
            for target in formats:
                if source != target:
                    conversions.append((source, target))
        
        return conversions
    
    def convert(
        self,
        source_package: BasePackage,
        target_format: PackageFormat,
        output_path: Union[str, Path],
        options: Optional[Dict[str, Any]] = None
    ) -> ConversionResult:
        """Convert package using universal approach (extract -> repackage).
        
        Args:
            source_package: Source package to convert
            target_format: Target format
            output_path: Output path for converted package
            options: Conversion options
            
        Returns:
            Conversion result
        """
        options = options or {}
        output_path = Path(output_path)
        
        try:
            # Create temporary directory for extraction
            with tempfile.TemporaryDirectory(prefix="pacc_convert_") as temp_dir:
                temp_path = Path(temp_dir)
                
                # Step 1: Extract source package
                logger.debug(f"Extracting {source_package.path} to {temp_path}")
                extracted_path = source_package.extract_to(temp_path)
                
                # Step 2: Create target package from extracted content
                logger.debug(f"Creating {target_format} package at {output_path}")
                
                if target_format == PackageFormat.SINGLE_FILE:
                    result = self._convert_to_single_file(
                        extracted_path, output_path, source_package, options
                    )
                elif target_format == PackageFormat.MULTI_FILE:
                    result = self._convert_to_multi_file(
                        extracted_path, output_path, source_package, options
                    )
                elif target_format == PackageFormat.ZIP_ARCHIVE:
                    result = self._convert_to_zip(
                        extracted_path, output_path, source_package, options
                    )
                elif target_format in [PackageFormat.TAR_ARCHIVE, PackageFormat.TAR_GZ_ARCHIVE]:
                    compression = 'gz' if target_format == PackageFormat.TAR_GZ_ARCHIVE else None
                    result = self._convert_to_tar(
                        extracted_path, output_path, source_package, compression, options
                    )
                else:
                    return ConversionResult(
                        success=False,
                        source_format=source_package.get_format(),
                        target_format=target_format,
                        error_message=f"Unsupported target format: {target_format}"
                    )
                
                return result
                
        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            return ConversionResult(
                success=False,
                source_format=source_package.get_format(),
                target_format=target_format,
                error_message=str(e)
            )
    
    def _convert_to_single_file(
        self,
        source_path: Path,
        output_path: Path,
        source_package: BasePackage,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert to single file format."""
        # Find the main file to use
        if source_path.is_file():
            main_file = source_path
        elif source_path.is_dir():
            # Look for main file based on options or heuristics
            main_file_name = options.get('main_file')
            if main_file_name:
                main_file = source_path / main_file_name
                if not main_file.exists():
                    return ConversionResult(
                        success=False,
                        source_format=source_package.get_format(),
                        target_format=PackageFormat.SINGLE_FILE,
                        error_message=f"Specified main file not found: {main_file_name}"
                    )
            else:
                # Use heuristics to find main file
                candidates = list(source_path.rglob('*'))
                files = [f for f in candidates if f.is_file()]
                
                if not files:
                    return ConversionResult(
                        success=False,
                        source_format=source_package.get_format(),
                        target_format=PackageFormat.SINGLE_FILE,
                        error_message="No files found to convert to single file"
                    )
                elif len(files) == 1:
                    main_file = files[0]
                else:
                    # Multiple files - pick the largest or first alphabetically
                    if options.get('pick_largest', True):
                        main_file = max(files, key=lambda f: f.stat().st_size)
                    else:
                        main_file = sorted(files, key=lambda f: f.name)[0]
        else:
            return ConversionResult(
                success=False,
                source_format=source_package.get_format(),
                target_format=PackageFormat.SINGLE_FILE,
                error_message=f"Invalid source path: {source_path}"
            )
        
        # Copy the main file to output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(main_file, output_path)
        
        # Create and configure target package
        target_package = SingleFilePackage(output_path)
        self._preserve_package_info(source_package, target_package)
        
        return ConversionResult(
            success=True,
            output_path=output_path,
            source_format=source_package.get_format(),
            target_format=PackageFormat.SINGLE_FILE,
            metadata={'main_file': str(main_file.name)}
        )
    
    def _convert_to_multi_file(
        self,
        source_path: Path,
        output_path: Path,
        source_package: BasePackage,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert to multi-file format."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if source_path.is_file():
            # Single file -> create directory with that file
            output_path.mkdir(exist_ok=True)
            target_file = output_path / source_path.name
            shutil.copy2(source_path, target_file)
        elif source_path.is_dir():
            # Directory -> copy entire directory
            if output_path.exists():
                shutil.rmtree(output_path)
            shutil.copytree(source_path, output_path)
        else:
            return ConversionResult(
                success=False,
                source_format=source_package.get_format(),
                target_format=PackageFormat.MULTI_FILE,
                error_message=f"Invalid source path: {source_path}"
            )
        
        # Create and configure target package
        target_package = MultiFilePackage(output_path)
        self._preserve_package_info(source_package, target_package)
        
        return ConversionResult(
            success=True,
            output_path=output_path,
            source_format=source_package.get_format(),
            target_format=PackageFormat.MULTI_FILE
        )
    
    def _convert_to_zip(
        self,
        source_path: Path,
        output_path: Path,
        source_package: BasePackage,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert to ZIP archive format."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        compression = options.get('compression', zipfile.ZIP_DEFLATED)
        compress_level = options.get('compress_level', 6)
        
        with zipfile.ZipFile(output_path, 'w', compression=compression, compresslevel=compress_level) as zip_file:
            if source_path.is_file():
                # Single file
                zip_file.write(source_path, source_path.name)
            elif source_path.is_dir():
                # Directory tree
                for file_path in source_path.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(source_path)
                        zip_file.write(file_path, arcname)
            else:
                return ConversionResult(
                    success=False,
                    source_format=source_package.get_format(),
                    target_format=PackageFormat.ZIP_ARCHIVE,
                    error_message=f"Invalid source path: {source_path}"
                )
        
        # Create and configure target package
        target_package = ZipPackage(output_path)
        self._preserve_package_info(source_package, target_package)
        
        return ConversionResult(
            success=True,
            output_path=output_path,
            source_format=source_package.get_format(),
            target_format=PackageFormat.ZIP_ARCHIVE
        )
    
    def _convert_to_tar(
        self,
        source_path: Path,
        output_path: Path,
        source_package: BasePackage,
        compression: Optional[str],
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert to TAR archive format."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine TAR mode
        if compression == 'gz':
            mode = 'w:gz'
            target_format = PackageFormat.TAR_GZ_ARCHIVE
        elif compression == 'bz2':
            mode = 'w:bz2'
            target_format = PackageFormat.TAR_ARCHIVE
        elif compression == 'xz':
            mode = 'w:xz'
            target_format = PackageFormat.TAR_ARCHIVE
        else:
            mode = 'w'
            target_format = PackageFormat.TAR_ARCHIVE
        
        with tarfile.open(output_path, mode) as tar_file:
            if source_path.is_file():
                # Single file
                tar_file.add(source_path, arcname=source_path.name)
            elif source_path.is_dir():
                # Directory tree
                for file_path in source_path.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(source_path)
                        tar_file.add(file_path, arcname=arcname)
            else:
                return ConversionResult(
                    success=False,
                    source_format=source_package.get_format(),
                    target_format=target_format,
                    error_message=f"Invalid source path: {source_path}"
                )
        
        # Create and configure target package
        target_package = TarPackage(output_path, compression=compression)
        self._preserve_package_info(source_package, target_package)
        
        return ConversionResult(
            success=True,
            output_path=output_path,
            source_format=source_package.get_format(),
            target_format=target_format
        )


class SpecializedConverter(BaseConverter):
    """Specialized converter for specific format pairs with optimizations."""
    
    def __init__(self, preserve_metadata: bool = True):
        """Initialize specialized converter."""
        super().__init__(preserve_metadata)
        
        # Define optimized conversion paths
        self._specialized_conversions = {
            (PackageFormat.SINGLE_FILE, PackageFormat.ZIP_ARCHIVE): self._single_to_zip,
            (PackageFormat.SINGLE_FILE, PackageFormat.TAR_ARCHIVE): self._single_to_tar,
            (PackageFormat.SINGLE_FILE, PackageFormat.TAR_GZ_ARCHIVE): self._single_to_tar_gz,
            (PackageFormat.MULTI_FILE, PackageFormat.ZIP_ARCHIVE): self._multi_to_zip,
            (PackageFormat.MULTI_FILE, PackageFormat.TAR_ARCHIVE): self._multi_to_tar,
            (PackageFormat.MULTI_FILE, PackageFormat.TAR_GZ_ARCHIVE): self._multi_to_tar_gz,
            (PackageFormat.ZIP_ARCHIVE, PackageFormat.TAR_ARCHIVE): self._zip_to_tar,
            (PackageFormat.ZIP_ARCHIVE, PackageFormat.TAR_GZ_ARCHIVE): self._zip_to_tar_gz,
            (PackageFormat.TAR_ARCHIVE, PackageFormat.ZIP_ARCHIVE): self._tar_to_zip,
            (PackageFormat.TAR_GZ_ARCHIVE, PackageFormat.ZIP_ARCHIVE): self._tar_to_zip,
        }
    
    def get_supported_conversions(self) -> List[tuple[PackageFormat, PackageFormat]]:
        """Get specialized conversion pairs."""
        return list(self._specialized_conversions.keys())
    
    def convert(
        self,
        source_package: BasePackage,
        target_format: PackageFormat,
        output_path: Union[str, Path],
        options: Optional[Dict[str, Any]] = None
    ) -> ConversionResult:
        """Convert using specialized optimization if available."""
        conversion_key = (source_package.get_format(), target_format)
        
        if conversion_key in self._specialized_conversions:
            converter_func = self._specialized_conversions[conversion_key]
            return converter_func(source_package, Path(output_path), options or {})
        else:
            return ConversionResult(
                success=False,
                source_format=source_package.get_format(),
                target_format=target_format,
                error_message=f"Specialized conversion not available for {conversion_key}"
            )
    
    def _single_to_zip(
        self,
        source_package: SingleFilePackage,
        output_path: Path,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert single file to ZIP (optimized)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        compression = options.get('compression', zipfile.ZIP_DEFLATED)
        
        with zipfile.ZipFile(output_path, 'w', compression=compression) as zip_file:
            zip_file.write(source_package.path, source_package.path.name)
        
        target_package = ZipPackage(output_path)
        self._preserve_package_info(source_package, target_package)
        
        return ConversionResult(
            success=True,
            output_path=output_path,
            source_format=PackageFormat.SINGLE_FILE,
            target_format=PackageFormat.ZIP_ARCHIVE
        )
    
    def _single_to_tar(
        self,
        source_package: SingleFilePackage,
        output_path: Path,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert single file to TAR (optimized)."""
        return self._single_to_tar_common(source_package, output_path, options, None)
    
    def _single_to_tar_gz(
        self,
        source_package: SingleFilePackage,
        output_path: Path,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert single file to TAR.GZ (optimized)."""
        return self._single_to_tar_common(source_package, output_path, options, 'gz')
    
    def _single_to_tar_common(
        self,
        source_package: SingleFilePackage,
        output_path: Path,
        options: Dict[str, Any],
        compression: Optional[str]
    ) -> ConversionResult:
        """Common implementation for single file to TAR conversion."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = f'w:{compression}' if compression else 'w'
        target_format = PackageFormat.TAR_GZ_ARCHIVE if compression == 'gz' else PackageFormat.TAR_ARCHIVE
        
        with tarfile.open(output_path, mode) as tar_file:
            tar_file.add(source_package.path, arcname=source_package.path.name)
        
        target_package = TarPackage(output_path, compression=compression)
        self._preserve_package_info(source_package, target_package)
        
        return ConversionResult(
            success=True,
            output_path=output_path,
            source_format=PackageFormat.SINGLE_FILE,
            target_format=target_format
        )
    
    def _multi_to_zip(
        self,
        source_package: MultiFilePackage,
        output_path: Path,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert multi-file to ZIP (optimized)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        compression = options.get('compression', zipfile.ZIP_DEFLATED)
        
        with zipfile.ZipFile(output_path, 'w', compression=compression) as zip_file:
            for file_path in source_package.path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_package.path)
                    zip_file.write(file_path, arcname)
        
        target_package = ZipPackage(output_path)
        self._preserve_package_info(source_package, target_package)
        
        return ConversionResult(
            success=True,
            output_path=output_path,
            source_format=PackageFormat.MULTI_FILE,
            target_format=PackageFormat.ZIP_ARCHIVE
        )
    
    def _multi_to_tar(
        self,
        source_package: MultiFilePackage,
        output_path: Path,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert multi-file to TAR (optimized)."""
        return self._multi_to_tar_common(source_package, output_path, options, None)
    
    def _multi_to_tar_gz(
        self,
        source_package: MultiFilePackage,
        output_path: Path,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert multi-file to TAR.GZ (optimized)."""
        return self._multi_to_tar_common(source_package, output_path, options, 'gz')
    
    def _multi_to_tar_common(
        self,
        source_package: MultiFilePackage,
        output_path: Path,
        options: Dict[str, Any],
        compression: Optional[str]
    ) -> ConversionResult:
        """Common implementation for multi-file to TAR conversion."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = f'w:{compression}' if compression else 'w'
        target_format = PackageFormat.TAR_GZ_ARCHIVE if compression == 'gz' else PackageFormat.TAR_ARCHIVE
        
        with tarfile.open(output_path, mode) as tar_file:
            for file_path in source_package.path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_package.path)
                    tar_file.add(file_path, arcname=arcname)
        
        target_package = TarPackage(output_path, compression=compression)
        self._preserve_package_info(source_package, target_package)
        
        return ConversionResult(
            success=True,
            output_path=output_path,
            source_format=PackageFormat.MULTI_FILE,
            target_format=target_format
        )
    
    def _zip_to_tar(
        self,
        source_package: ZipPackage,
        output_path: Path,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert ZIP to TAR (optimized)."""
        return self._archive_to_archive(
            source_package, output_path, options, PackageFormat.TAR_ARCHIVE, None
        )
    
    def _zip_to_tar_gz(
        self,
        source_package: ZipPackage,
        output_path: Path,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert ZIP to TAR.GZ (optimized)."""
        return self._archive_to_archive(
            source_package, output_path, options, PackageFormat.TAR_GZ_ARCHIVE, 'gz'
        )
    
    def _tar_to_zip(
        self,
        source_package: TarPackage,
        output_path: Path,
        options: Dict[str, Any]
    ) -> ConversionResult:
        """Convert TAR to ZIP (optimized)."""
        return self._archive_to_archive(
            source_package, output_path, options, PackageFormat.ZIP_ARCHIVE, None
        )
    
    def _archive_to_archive(
        self,
        source_package: BasePackage,
        output_path: Path,
        options: Dict[str, Any],
        target_format: PackageFormat,
        compression: Optional[str]
    ) -> ConversionResult:
        """Optimized archive-to-archive conversion without full extraction."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if target_format == PackageFormat.ZIP_ARCHIVE:
                zip_compression = options.get('compression', zipfile.ZIP_DEFLATED)
                
                with zipfile.ZipFile(output_path, 'w', compression=zip_compression) as zip_file:
                    for file_path in source_package.list_contents():
                        file_data = source_package.get_file_content(file_path)
                        zip_file.writestr(file_path, file_data)
                
                target_package = ZipPackage(output_path)
                
            elif target_format in [PackageFormat.TAR_ARCHIVE, PackageFormat.TAR_GZ_ARCHIVE]:
                mode = f'w:{compression}' if compression else 'w'
                
                with tarfile.open(output_path, mode) as tar_file:
                    for file_path in source_package.list_contents():
                        file_data = source_package.get_file_content(file_path)
                        
                        # Create tarinfo
                        tarinfo = tarfile.TarInfo(name=file_path)
                        tarinfo.size = len(file_data)
                        
                        # Add file to tar
                        tar_file.addfile(tarinfo, fileobj=io.BytesIO(file_data))
                
                target_package = TarPackage(output_path, compression=compression)
            
            else:
                return ConversionResult(
                    success=False,
                    source_format=source_package.get_format(),
                    target_format=target_format,
                    error_message=f"Unsupported target format: {target_format}"
                )
            
            self._preserve_package_info(source_package, target_package)
            
            return ConversionResult(
                success=True,
                output_path=output_path,
                source_format=source_package.get_format(),
                target_format=target_format
            )
            
        except Exception as e:
            return ConversionResult(
                success=False,
                source_format=source_package.get_format(),
                target_format=target_format,
                error_message=str(e)
            )


class FormatConverter:
    """High-level format converter that chooses the best conversion strategy."""
    
    def __init__(self, prefer_specialized: bool = True):
        """Initialize format converter.
        
        Args:
            prefer_specialized: Whether to prefer specialized converters
        """
        self.prefer_specialized = prefer_specialized
        self.specialized_converter = SpecializedConverter()
        self.universal_converter = UniversalConverter()
    
    def convert(
        self,
        source_path: Union[str, Path],
        target_format: PackageFormat,
        output_path: Union[str, Path],
        source_format: Optional[PackageFormat] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> ConversionResult:
        """Convert package to target format.
        
        Args:
            source_path: Path to source package
            target_format: Target format
            output_path: Output path for converted package
            source_format: Source format hint (auto-detected if None)
            options: Conversion options
            
        Returns:
            Conversion result
        """
        try:
            # Create source package
            source_package = create_package(source_path, source_format)
            
            # If no conversion needed, just copy/link
            if source_package.get_format() == target_format:
                return self._copy_package(source_package, Path(output_path))
            
            # Try specialized converter first if preferred
            if self.prefer_specialized:
                if self.specialized_converter.can_convert(
                    source_package.get_format(), target_format
                ):
                    logger.debug("Using specialized converter")
                    return self.specialized_converter.convert(
                        source_package, target_format, output_path, options
                    )
            
            # Fall back to universal converter
            logger.debug("Using universal converter")
            return self.universal_converter.convert(
                source_package, target_format, output_path, options
            )
            
        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            return ConversionResult(
                success=False,
                error_message=str(e)
            )
    
    def _copy_package(self, source_package: BasePackage, output_path: Path) -> ConversionResult:
        """Copy package when no conversion is needed."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if source_package.path.is_file():
            shutil.copy2(source_package.path, output_path)
        elif source_package.path.is_dir():
            if output_path.exists():
                shutil.rmtree(output_path)
            shutil.copytree(source_package.path, output_path)
        else:
            return ConversionResult(
                success=False,
                error_message=f"Invalid source package path: {source_package.path}"
            )
        
        return ConversionResult(
            success=True,
            output_path=output_path,
            source_format=source_package.get_format(),
            target_format=source_package.get_format(),
            metadata={'operation': 'copy'}
        )
    
    def get_supported_conversions(self) -> List[tuple[PackageFormat, PackageFormat]]:
        """Get all supported conversions.
        
        Returns:
            List of (source_format, target_format) tuples
        """
        # Combine specialized and universal converter capabilities
        specialized = set(self.specialized_converter.get_supported_conversions())
        universal = set(self.universal_converter.get_supported_conversions())
        
        return list(specialized.union(universal))


class PackageConverter:
    """Main package converter interface."""
    
    def __init__(self):
        """Initialize package converter."""
        self.format_converter = FormatConverter()
    
    def convert_file(
        self,
        source_path: Union[str, Path],
        target_format: PackageFormat,
        output_path: Union[str, Path],
        options: Optional[Dict[str, Any]] = None
    ) -> ConversionResult:
        """Convert a single package file.
        
        Args:
            source_path: Path to source package
            target_format: Target format
            output_path: Output path
            options: Conversion options
            
        Returns:
            Conversion result
        """
        return self.format_converter.convert(
            source_path, target_format, output_path, options=options
        )
    
    def convert_batch(
        self,
        conversions: List[tuple[Union[str, Path], PackageFormat, Union[str, Path]]],
        options: Optional[Dict[str, Any]] = None
    ) -> List[ConversionResult]:
        """Convert multiple packages.
        
        Args:
            conversions: List of (source_path, target_format, output_path) tuples
            options: Conversion options
            
        Returns:
            List of conversion results
        """
        results = []
        
        for source_path, target_format, output_path in conversions:
            result = self.convert_file(source_path, target_format, output_path, options)
            results.append(result)
            
            # Log progress
            if result.success:
                logger.info(f"Converted {source_path} -> {output_path}")
            else:
                logger.error(f"Failed to convert {source_path}: {result.error_message}")
        
        return results
    
    def get_conversion_options(self, target_format: PackageFormat) -> Dict[str, Any]:
        """Get available options for target format.
        
        Args:
            target_format: Target package format
            
        Returns:
            Dictionary of available options
        """
        if target_format == PackageFormat.ZIP_ARCHIVE:
            return {
                'compression': {
                    'type': 'choice',
                    'choices': ['stored', 'deflated', 'bzip2', 'lzma'],
                    'default': 'deflated',
                    'description': 'Compression method'
                },
                'compress_level': {
                    'type': 'int',
                    'min': 0,
                    'max': 9,
                    'default': 6,
                    'description': 'Compression level (0-9)'
                }
            }
        elif target_format in [PackageFormat.TAR_ARCHIVE, PackageFormat.TAR_GZ_ARCHIVE]:
            return {
                'compression': {
                    'type': 'choice',
                    'choices': [None, 'gz', 'bz2', 'xz'],
                    'default': 'gz' if target_format == PackageFormat.TAR_GZ_ARCHIVE else None,
                    'description': 'Compression method'
                }
            }
        elif target_format == PackageFormat.SINGLE_FILE:
            return {
                'main_file': {
                    'type': 'str',
                    'default': None,
                    'description': 'Specific file to extract (if multiple files)'
                },
                'pick_largest': {
                    'type': 'bool',
                    'default': True,
                    'description': 'Pick largest file if multiple candidates'
                }
            }
        else:
            return {}


# Import io for BytesIO
import io