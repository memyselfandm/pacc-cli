"""Main selection workflow orchestrator that integrates all components."""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Callable
import logging

from ..core import DirectoryScanner, FileFilter, FilePathValidator
from ..validators import BaseValidator, ValidationResult
from ..errors import PACCError, ValidationError, SourceError
from .types import SelectionMode, SelectionStrategy, SelectionContext, SelectionResult
from .ui import InteractiveSelector, ConfirmationDialog, ProgressTracker
from .persistence import SelectionCache, SelectionHistory
from .filters import SelectionFilter


logger = logging.getLogger(__name__)


class SelectionWorkflow:
    """Main workflow orchestrator for file selection operations."""
    
    def __init__(
        self,
        file_validator: Optional[FilePathValidator] = None,
        cache: Optional[SelectionCache] = None,
        history: Optional[SelectionHistory] = None
    ):
        """Initialize selection workflow.
        
        Args:
            file_validator: File path validator to use
            cache: Selection cache for persistence
            history: Selection history tracker
        """
        self.file_validator = file_validator or FilePathValidator()
        self.cache = cache or SelectionCache()
        self.history = history or SelectionHistory()
        self.scanner = DirectoryScanner(self.file_validator)
        
        # UI components - will be initialized when needed
        self._selector: Optional[InteractiveSelector] = None
        self._progress: Optional[ProgressTracker] = None
        self._confirmation: Optional[ConfirmationDialog] = None
    
    async def execute_selection(
        self,
        source_paths: List[Union[str, Path]],
        context: SelectionContext
    ) -> SelectionResult:
        """Execute the complete selection workflow.
        
        Args:
            source_paths: List of paths to select from
            context: Selection context with configuration
            
        Returns:
            Selection result with chosen files and validation
        """
        result = SelectionResult(success=False)
        
        try:
            # Step 1: Check cache if enabled
            if context.cache_selections:
                cached_result = await self._check_cache(source_paths, context)
                if cached_result:
                    logger.info("Using cached selection result")
                    cached_result.cached_result = True
                    return cached_result
            
            # Step 2: Discover and filter files
            progress = self._get_progress_tracker() if context.show_progress else None
            if progress:
                await progress.start("Discovering files...")
            
            candidate_files = await self._discover_files(source_paths, context, progress)
            
            if not candidate_files and not context.allow_empty:
                result.errors.append(SourceError(
                    "No valid files found matching selection criteria"
                ))
                return result
            
            # Step 3: Apply selection strategy
            if progress:
                await progress.update("Applying selection strategy...")
            
            selected_files = await self._apply_selection_strategy(
                candidate_files, context, progress
            )
            
            if not selected_files and not context.allow_empty:
                result.user_cancelled = True
                return result
            
            # Step 4: Validate selections if requested
            validation_results = []
            if context.validate_on_select and context.validators:
                if progress:
                    await progress.update("Validating selections...")
                
                validation_results = await self._validate_selections(
                    selected_files, context, progress
                )
                
                # Handle validation errors
                if context.stop_on_validation_error:
                    invalid_results = [r for r in validation_results if not r.is_valid]
                    if invalid_results:
                        result.validation_results = validation_results
                        result.errors.append(ValidationError(
                            f"Validation failed for {len(invalid_results)} files"
                        ))
                        return result
            
            # Step 5: Confirmation if requested
            if context.confirm_selections and context.interactive_ui:
                if progress:
                    await progress.update("Waiting for confirmation...")
                
                confirmed = await self._confirm_selection(
                    selected_files, validation_results, context
                )
                
                if not confirmed:
                    result.user_cancelled = True
                    return result
            
            # Step 6: Store results and cache if enabled
            result.success = True
            result.selected_files = selected_files
            result.validation_results = validation_results
            
            if context.cache_selections:
                await self._store_cache(source_paths, context, result)
            
            if context.remember_choices:
                await self._store_history(source_paths, context, result)
            
            if progress:
                await progress.complete(f"Selected {len(selected_files)} files")
            
            logger.info(f"Selection workflow completed: {len(selected_files)} files selected")
            return result
            
        except Exception as e:
            logger.error(f"Selection workflow failed: {e}")
            result.errors.append(e)
            return result
        
        finally:
            # Clean up UI components
            if self._progress:
                await self._progress.cleanup()
    
    async def _discover_files(
        self,
        source_paths: List[Union[str, Path]],
        context: SelectionContext,
        progress: Optional[ProgressTracker] = None
    ) -> List[Path]:
        """Discover and filter candidate files from source paths."""
        all_files = []
        
        # Set up file filter based on context
        file_filter = FileFilter()
        
        if context.extensions:
            file_filter.add_extension_filter(context.extensions)
        
        if context.patterns:
            file_filter.add_pattern_filter(context.patterns)
        
        if context.size_limits:
            min_size, max_size = context.size_limits
            file_filter.add_size_filter(min_size, max_size)
        
        if context.exclude_hidden:
            file_filter.add_exclude_hidden()
        
        # Discover files from each source path
        for i, source_path in enumerate(source_paths):
            if progress:
                await progress.update(f"Scanning {source_path} ({i+1}/{len(source_paths)})")
            
            path_obj = Path(source_path)
            
            if path_obj.is_file():
                # Single file - validate and add if it passes filter
                if self.file_validator.is_valid_path(path_obj):
                    filtered = file_filter.filter_files([path_obj])
                    all_files.extend(filtered)
            
            elif path_obj.is_dir():
                # Directory - scan based on mode
                if context.mode == SelectionMode.DIRECTORY:
                    # Add the directory itself if it's valid
                    if self.file_validator.is_safe_directory(path_obj):
                        all_files.append(path_obj)
                else:
                    # Scan directory for files
                    recursive = context.mode != SelectionMode.SINGLE_FILE
                    discovered = list(self.scanner.scan_directory(
                        path_obj, recursive=recursive
                    ))
                    
                    # Apply filters
                    filtered = file_filter.filter_files(discovered)
                    all_files.extend(filtered)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for file_path in all_files:
            if file_path not in seen:
                seen.add(file_path)
                unique_files.append(file_path)
        
        logger.debug(f"Discovered {len(unique_files)} candidate files")
        return unique_files
    
    async def _apply_selection_strategy(
        self,
        candidate_files: List[Path],
        context: SelectionContext,
        progress: Optional[ProgressTracker] = None
    ) -> List[Path]:
        """Apply selection strategy to choose final files."""
        if not candidate_files:
            return []
        
        # Apply max selections limit
        if len(candidate_files) > context.max_selections:
            candidate_files = candidate_files[:context.max_selections]
        
        if context.strategy == SelectionStrategy.FIRST_VALID:
            # Return first valid file
            for file_path in candidate_files:
                if self.file_validator.is_valid_path(file_path):
                    return [file_path]
            return []
        
        elif context.strategy == SelectionStrategy.ALL_VALID:
            # Return all valid files
            valid_files = []
            for file_path in candidate_files:
                if self.file_validator.is_valid_path(file_path):
                    valid_files.append(file_path)
            return valid_files
        
        elif context.strategy == SelectionStrategy.BEST_MATCH:
            # Return best match (for now, just the first valid)
            # TODO: Implement ranking algorithm
            for file_path in candidate_files:
                if self.file_validator.is_valid_path(file_path):
                    return [file_path]
            return []
        
        elif context.strategy == SelectionStrategy.USER_CHOICE:
            # Use interactive selection if UI is enabled
            if context.interactive_ui:
                selector = self._get_interactive_selector()
                return await selector.select_files(candidate_files, context)
            else:
                # Fallback to all valid
                return await self._apply_selection_strategy(
                    candidate_files,
                    SelectionContext(**{**context.__dict__, 'strategy': SelectionStrategy.ALL_VALID}),
                    progress
                )
        
        return []
    
    async def _validate_selections(
        self,
        selected_files: List[Path],
        context: SelectionContext,
        progress: Optional[ProgressTracker] = None
    ) -> List[ValidationResult]:
        """Validate selected files using configured validators."""
        if not context.validators:
            return []
        
        all_results = []
        
        if context.background_validation and len(selected_files) > 1:
            # Use concurrent validation for better performance
            semaphore = asyncio.Semaphore(context.max_concurrent)
            
            async def validate_file(file_path: Path, validator: BaseValidator) -> ValidationResult:
                async with semaphore:
                    # Run validator in thread pool since it's CPU-bound
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        None, validator.validate_single, file_path
                    )
            
            # Create validation tasks
            tasks = []
            for file_path in selected_files:
                for validator in context.validators:
                    task = validate_file(file_path, validator)
                    tasks.append(task)
            
            # Execute with progress tracking
            if progress:
                await progress.update(f"Validating {len(selected_files)} files...")
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and handle exceptions
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Validation error: {result}")
                    # Create error result
                    error_result = ValidationResult(is_valid=False)
                    error_result.add_error(
                        "VALIDATION_EXCEPTION",
                        f"Validation failed with exception: {result}"
                    )
                    all_results.append(error_result)
                else:
                    all_results.append(result)
        
        else:
            # Sequential validation
            for i, file_path in enumerate(selected_files):
                if progress:
                    await progress.update(f"Validating file {i+1}/{len(selected_files)}")
                
                for validator in context.validators:
                    try:
                        result = validator.validate_single(file_path)
                        all_results.append(result)
                    except Exception as e:
                        logger.error(f"Validation error for {file_path}: {e}")
                        error_result = ValidationResult(
                            is_valid=False, 
                            file_path=str(file_path)
                        )
                        error_result.add_error(
                            "VALIDATION_EXCEPTION",
                            f"Validation failed: {e}"
                        )
                        all_results.append(error_result)
        
        return all_results
    
    async def _confirm_selection(
        self,
        selected_files: List[Path],
        validation_results: List[ValidationResult],
        context: SelectionContext
    ) -> bool:
        """Show confirmation dialog for selected files."""
        confirmation = self._get_confirmation_dialog()
        return await confirmation.confirm_selection(
            selected_files, validation_results, context
        )
    
    async def _check_cache(
        self,
        source_paths: List[Union[str, Path]],
        context: SelectionContext
    ) -> Optional[SelectionResult]:
        """Check if selection result is cached."""
        cache_key = self.cache.generate_key(source_paths, context)
        return await self.cache.get(cache_key)
    
    async def _store_cache(
        self,
        source_paths: List[Union[str, Path]],
        context: SelectionContext,
        result: SelectionResult
    ) -> None:
        """Store selection result in cache."""
        cache_key = self.cache.generate_key(source_paths, context)
        await self.cache.set(cache_key, result)
    
    async def _store_history(
        self,
        source_paths: List[Union[str, Path]],
        context: SelectionContext,
        result: SelectionResult
    ) -> None:
        """Store selection in history."""
        await self.history.add_selection(source_paths, context, result)
    
    def _get_interactive_selector(self) -> InteractiveSelector:
        """Get or create interactive selector."""
        if self._selector is None:
            self._selector = InteractiveSelector()
        return self._selector
    
    def _get_progress_tracker(self) -> ProgressTracker:
        """Get or create progress tracker."""
        if self._progress is None:
            self._progress = ProgressTracker()
        return self._progress
    
    def _get_confirmation_dialog(self) -> ConfirmationDialog:
        """Get or create confirmation dialog."""
        if self._confirmation is None:
            self._confirmation = ConfirmationDialog()
        return self._confirmation