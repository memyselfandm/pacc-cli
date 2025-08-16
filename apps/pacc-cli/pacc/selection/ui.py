"""Interactive UI components for selection workflow."""

import asyncio
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
import shutil
import time

from ..validators import ValidationResult
from .types import SelectionContext


class DisplayMode(Enum):
    """Display modes for UI components."""
    MINIMAL = "minimal"
    NORMAL = "normal" 
    DETAILED = "detailed"
    DEBUG = "debug"


@dataclass
class UIConfig:
    """Configuration for UI components."""
    
    display_mode: DisplayMode = DisplayMode.NORMAL
    use_colors: bool = True
    show_file_sizes: bool = True
    show_timestamps: bool = False
    max_display_files: int = 50
    truncate_paths: bool = True
    max_path_length: int = 80
    
    # Progress settings
    show_progress_bar: bool = True
    progress_width: int = 40
    update_interval: float = 0.1
    
    # Confirmation settings
    default_yes: bool = False
    require_explicit_yes: bool = True
    show_validation_details: bool = True


class InteractiveSelector:
    """Interactive file selector with terminal UI."""
    
    def __init__(self, config: Optional[UIConfig] = None):
        """Initialize interactive selector.
        
        Args:
            config: UI configuration options
        """
        self.config = config or UIConfig()
        self.terminal_width = shutil.get_terminal_size().columns
    
    async def select_files(
        self,
        candidate_files: List[Path],
        context: SelectionContext
    ) -> List[Path]:
        """Interactive file selection interface.
        
        Args:
            candidate_files: List of files to choose from
            context: Selection context
            
        Returns:
            List of selected files
        """
        if not candidate_files:
            return []
        
        # Handle single file case
        if len(candidate_files) == 1:
            if await self._confirm_single_file(candidate_files[0]):
                return candidate_files
            return []
        
        # Handle multi-file selection
        self._print_header("File Selection", candidate_files)
        
        # Display available files
        self._display_file_list(candidate_files)
        
        # Get user selection
        if context.mode.value in ['single_file', 'interactive']:
            selected = await self._select_single(candidate_files)
        else:
            selected = await self._select_multiple(candidate_files, context)
        
        return selected
    
    async def _confirm_single_file(self, file_path: Path) -> bool:
        """Confirm selection of a single file."""
        self._print_header("Confirm Selection")
        
        # Display file info
        self._display_file_info(file_path, detailed=True)
        
        return await self._get_yes_no(
            "Select this file?",
            default=not self.config.require_explicit_yes
        )
    
    async def _select_single(self, candidate_files: List[Path]) -> List[Path]:
        """Select a single file from candidates."""
        while True:
            try:
                choice = input(f"\\nSelect file (1-{len(candidate_files)}, 'q' to quit): ").strip()
                
                if choice.lower() == 'q':
                    return []
                
                index = int(choice) - 1
                if 0 <= index < len(candidate_files):
                    selected_file = candidate_files[index]
                    
                    # Show detailed info and confirm
                    print(f"\\n{self._get_color('cyan')}Selected:{self._get_color('reset')}")
                    self._display_file_info(selected_file, detailed=True)
                    
                    if await self._get_yes_no("Confirm selection?"):
                        return [selected_file]
                    # If not confirmed, continue loop
                else:
                    print(f"{self._get_color('red')}Invalid selection. Please choose 1-{len(candidate_files)}.{self._get_color('reset')}")
                    
            except ValueError:
                print(f"{self._get_color('red')}Invalid input. Please enter a number or 'q'.{self._get_color('reset')}")
            except KeyboardInterrupt:
                print(f"\\n{self._get_color('yellow')}Selection cancelled.{self._get_color('reset')}")
                return []
    
    async def _select_multiple(
        self,
        candidate_files: List[Path], 
        context: SelectionContext
    ) -> List[Path]:
        """Select multiple files from candidates."""
        selected_indices: Set[int] = set()
        
        while True:
            try:
                print(f"\\n{self._get_color('cyan')}Multi-file selection:{self._get_color('reset')}")
                print("Enter file numbers separated by spaces (e.g., '1 3 5')")
                print("Use 'all' to select all files, 'none' to clear selection")
                print("Use 'done' to finish, 'q' to quit")
                
                if selected_indices:
                    print(f"Currently selected: {sorted(i+1 for i in selected_indices)}")
                
                choice = input("Selection: ").strip().lower()
                
                if choice == 'q':
                    return []
                elif choice == 'done':
                    if selected_indices or context.allow_empty:
                        selected_files = [candidate_files[i] for i in sorted(selected_indices)]
                        if await self._confirm_multiple_selection(selected_files):
                            return selected_files
                    else:
                        print(f"{self._get_color('yellow')}No files selected. Use 'q' to quit or select files.{self._get_color('reset')}")
                elif choice == 'all':
                    selected_indices = set(range(len(candidate_files)))
                    print(f"{self._get_color('green')}All {len(candidate_files)} files selected.{self._get_color('reset')}")
                elif choice == 'none':
                    selected_indices.clear()
                    print(f"{self._get_color('yellow')}Selection cleared.{self._get_color('reset')}")
                else:
                    # Parse file numbers
                    try:
                        numbers = [int(x) for x in choice.split()]
                        new_indices = set()
                        
                        for num in numbers:
                            if 1 <= num <= len(candidate_files):
                                new_indices.add(num - 1)
                            else:
                                print(f"{self._get_color('red')}Invalid file number: {num}{self._get_color('reset')}")
                        
                        if new_indices:
                            selected_indices.update(new_indices)
                            print(f"{self._get_color('green')}Added {len(new_indices)} files to selection.{self._get_color('reset')}")
                        
                        # Check max selections limit
                        if len(selected_indices) > context.max_selections:
                            excess = len(selected_indices) - context.max_selections
                            # Remove excess (newest selections)
                            selected_indices = set(sorted(selected_indices)[:context.max_selections])
                            print(f"{self._get_color('yellow')}Selection limited to {context.max_selections} files ({excess} removed).{self._get_color('reset')}")
                            
                    except ValueError:
                        print(f"{self._get_color('red')}Invalid input. Please enter numbers separated by spaces.{self._get_color('reset')}")
                        
            except KeyboardInterrupt:
                print(f"\\n{self._get_color('yellow')}Selection cancelled.{self._get_color('reset')}")
                return []
    
    async def _confirm_multiple_selection(self, selected_files: List[Path]) -> bool:
        """Confirm multiple file selection."""
        print(f"\\n{self._get_color('cyan')}Confirm Selection ({len(selected_files)} files):{self._get_color('reset')}")
        
        for i, file_path in enumerate(selected_files[:10]):  # Show first 10
            print(f"  {i+1:2d}. {self._format_path(file_path)}")
        
        if len(selected_files) > 10:
            print(f"  ... and {len(selected_files) - 10} more files")
        
        return await self._get_yes_no("Confirm selection?")
    
    def _print_header(self, title: str, files: Optional[List[Path]] = None) -> None:
        """Print formatted header."""
        width = min(self.terminal_width, 80)
        print("\\n" + "=" * width)
        
        if files:
            print(f"{self._get_color('bold')}{title} ({len(files)} files){self._get_color('reset')}")
        else:
            print(f"{self._get_color('bold')}{title}{self._get_color('reset')}")
        
        print("=" * width)
    
    def _display_file_list(self, files: List[Path]) -> None:
        """Display list of files with numbers."""
        max_display = min(len(files), self.config.max_display_files)
        
        for i, file_path in enumerate(files[:max_display]):
            file_info = self._get_file_info_string(file_path)
            print(f"{self._get_color('blue')}{i+1:3d}.{self._get_color('reset')} {file_info}")
        
        if len(files) > max_display:
            remaining = len(files) - max_display
            print(f"{self._get_color('yellow')}... and {remaining} more files{self._get_color('reset')}")
    
    def _display_file_info(self, file_path: Path, detailed: bool = False) -> None:
        """Display detailed information about a file."""
        print(f"  Path: {self._format_path(file_path)}")
        
        if detailed or self.config.show_file_sizes:
            try:
                stat = file_path.stat()
                size = self._format_size(stat.st_size)
                print(f"  Size: {size}")
                
                if detailed or self.config.show_timestamps:
                    mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
                    print(f"  Modified: {mtime}")
                    
            except OSError:
                print(f"  {self._get_color('red')}(File access error){self._get_color('reset')}")
    
    def _get_file_info_string(self, file_path: Path) -> str:
        """Get formatted file info string."""
        path_str = self._format_path(file_path)
        
        if self.config.show_file_sizes:
            try:
                size = file_path.stat().st_size
                size_str = self._format_size(size)
                return f"{path_str} {self._get_color('dim')}({size_str}){self._get_color('reset')}"
            except OSError:
                return f"{path_str} {self._get_color('red')}(error){self._get_color('reset')}"
        
        return path_str
    
    def _format_path(self, path: Path) -> str:
        """Format path for display."""
        path_str = str(path)
        
        if self.config.truncate_paths and len(path_str) > self.config.max_path_length:
            # Truncate from the middle
            max_len = self.config.max_path_length
            if max_len < 10:
                return path_str[:max_len]
            
            prefix_len = (max_len - 3) // 2
            suffix_len = max_len - 3 - prefix_len
            return f"{path_str[:prefix_len]}...{path_str[-suffix_len:]}"
        
        return path_str
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f}TB"
    
    async def _get_yes_no(self, prompt: str, default: Optional[bool] = None) -> bool:
        """Get yes/no input from user."""
        if default is True:
            prompt += " [Y/n]"
        elif default is False:
            prompt += " [y/N]"
        else:
            prompt += " [y/n]"
        
        while True:
            try:
                response = input(f"{prompt}: ").strip().lower()
                
                if not response and default is not None:
                    return default
                
                if response in ['y', 'yes']:
                    return True
                elif response in ['n', 'no']:
                    return False
                else:
                    print(f"{self._get_color('red')}Please enter 'y' or 'n'.{self._get_color('reset')}")
                    
            except KeyboardInterrupt:
                print(f"\\n{self._get_color('yellow')}Cancelled.{self._get_color('reset')}")
                return False
    
    def _get_color(self, color: str) -> str:
        """Get ANSI color code."""
        if not self.config.use_colors or not sys.stdout.isatty():
            return ""
        
        colors = {
            'reset': '\\033[0m',
            'bold': '\\033[1m',
            'dim': '\\033[2m',
            'red': '\\033[31m',
            'green': '\\033[32m',
            'yellow': '\\033[33m',
            'blue': '\\033[34m',
            'cyan': '\\033[36m',
        }
        
        return colors.get(color, '')


class ProgressTracker:
    """Progress tracker for long-running operations."""
    
    def __init__(self, config: Optional[UIConfig] = None):
        """Initialize progress tracker.
        
        Args:
            config: UI configuration options
        """
        self.config = config or UIConfig()
        self.is_active = False
        self.current_message = ""
        self.start_time = 0.0
        self._update_task: Optional[asyncio.Task] = None
    
    async def start(self, message: str) -> None:
        """Start progress tracking.
        
        Args:
            message: Initial progress message
        """
        self.is_active = True
        self.current_message = message
        self.start_time = time.time()
        
        if self.config.show_progress_bar and sys.stdout.isatty():
            self._update_task = asyncio.create_task(self._update_progress_display())
        else:
            print(f"\\n{message}...")
    
    async def update(self, message: str) -> None:
        """Update progress message.
        
        Args:
            message: New progress message
        """
        if not self.is_active:
            return
        
        self.current_message = message
        
        if not self.config.show_progress_bar or not sys.stdout.isatty():
            print(f"{message}...")
    
    async def complete(self, message: str) -> None:
        """Complete progress tracking.
        
        Args:
            message: Completion message
        """
        await self.cleanup()
        
        elapsed = time.time() - self.start_time
        if elapsed > 1.0:
            print(f"\\n{message} (completed in {elapsed:.1f}s)")
        else:
            print(f"\\n{message}")
    
    async def cleanup(self) -> None:
        """Clean up progress tracking."""
        self.is_active = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            self._update_task = None
        
        # Clear progress line if using progress bar
        if self.config.show_progress_bar and sys.stdout.isatty():
            print("\\r" + " " * (self.config.progress_width + 50) + "\\r", end="")
    
    async def _update_progress_display(self) -> None:
        """Update progress bar display."""
        spinner_chars = "|/-\\\\"
        spinner_index = 0
        
        try:
            while self.is_active:
                elapsed = time.time() - self.start_time
                spinner = spinner_chars[spinner_index % len(spinner_chars)]
                
                # Create progress line
                progress_line = f"\\r{spinner} {self.current_message} ({elapsed:.1f}s)"
                
                # Truncate if too long
                max_width = shutil.get_terminal_size().columns - 5
                if len(progress_line) > max_width:
                    progress_line = progress_line[:max_width] + "..."
                
                print(progress_line, end="", flush=True)
                
                spinner_index += 1
                await asyncio.sleep(self.config.update_interval)
                
        except asyncio.CancelledError:
            pass


class ConfirmationDialog:
    """Confirmation dialog for selection results."""
    
    def __init__(self, config: Optional[UIConfig] = None):
        """Initialize confirmation dialog.
        
        Args:
            config: UI configuration options
        """
        self.config = config or UIConfig()
    
    async def confirm_selection(
        self,
        selected_files: List[Path],
        validation_results: List[ValidationResult],
        context: SelectionContext
    ) -> bool:
        """Show confirmation dialog for selection.
        
        Args:
            selected_files: Files that were selected
            validation_results: Validation results for the files
            context: Selection context
            
        Returns:
            True if user confirms, False otherwise
        """
        print(f"\\n{'='*60}")
        print(f"{self._get_color('bold')}Selection Summary{self._get_color('reset')}")
        print(f"{'='*60}")
        
        # Show selected files
        print(f"\\n{self._get_color('cyan')}Selected Files ({len(selected_files)}):{self._get_color('reset')}")
        for i, file_path in enumerate(selected_files[:10]):
            print(f"  {i+1:2d}. {file_path}")
        
        if len(selected_files) > 10:
            print(f"  ... and {len(selected_files) - 10} more files")
        
        # Show validation summary if available
        if validation_results:
            await self._show_validation_summary(validation_results)
        
        # Get confirmation
        return await self._get_confirmation()
    
    async def _show_validation_summary(
        self,
        validation_results: List[ValidationResult]
    ) -> None:
        """Show validation summary."""
        valid_count = sum(1 for r in validation_results if r.is_valid)
        total_count = len(validation_results)
        
        print(f"\\n{self._get_color('cyan')}Validation Results:{self._get_color('reset')}")
        
        if valid_count == total_count:
            print(f"  {self._get_color('green')}✓ All {total_count} validations passed{self._get_color('reset')}")
        else:
            failed_count = total_count - valid_count
            print(f"  {self._get_color('green')}✓ {valid_count} validations passed{self._get_color('reset')}")
            print(f"  {self._get_color('red')}✗ {failed_count} validations failed{self._get_color('reset')}")
        
        # Show detailed issues if requested
        if self.config.show_validation_details:
            await self._show_validation_details(validation_results)
    
    async def _show_validation_details(
        self,
        validation_results: List[ValidationResult]
    ) -> None:
        """Show detailed validation results."""
        error_count = 0
        warning_count = 0
        
        for result in validation_results:
            if result.errors:
                error_count += len(result.errors)
            if result.warnings:
                warning_count += len(result.warnings)
        
        if error_count == 0 and warning_count == 0:
            return
        
        print(f"\\n{self._get_color('yellow')}Validation Details:{self._get_color('reset')}")
        
        # Show first few errors/warnings
        shown_errors = 0
        shown_warnings = 0
        max_show = 5
        
        for result in validation_results:
            if shown_errors >= max_show and shown_warnings >= max_show:
                break
            
            for error in result.errors:
                if shown_errors >= max_show:
                    break
                print(f"  {self._get_color('red')}✗ {error}{self._get_color('reset')}")
                shown_errors += 1
            
            for warning in result.warnings:
                if shown_warnings >= max_show:
                    break
                print(f"  {self._get_color('yellow')}⚠ {warning}{self._get_color('reset')}")
                shown_warnings += 1
        
        if error_count > shown_errors or warning_count > shown_warnings:
            remaining = (error_count - shown_errors) + (warning_count - shown_warnings)
            print(f"  ... and {remaining} more issues")
    
    async def _get_confirmation(self) -> bool:
        """Get user confirmation."""
        while True:
            try:
                default_prompt = " [Y/n]" if self.config.default_yes else " [y/N]"
                response = input(f"\\nProceed with selection?{default_prompt}: ").strip().lower()
                
                if not response:
                    return self.config.default_yes
                
                if response in ['y', 'yes']:
                    return True
                elif response in ['n', 'no']:
                    return False
                else:
                    print(f"{self._get_color('red')}Please enter 'y' or 'n'.{self._get_color('reset')}")
                    
            except KeyboardInterrupt:
                print(f"\\n{self._get_color('yellow')}Cancelled.{self._get_color('reset')}")
                return False
    
    def _get_color(self, color: str) -> str:
        """Get ANSI color code."""
        if not self.config.use_colors or not sys.stdout.isatty():
            return ""
        
        colors = {
            'reset': '\\033[0m',
            'bold': '\\033[1m',
            'red': '\\033[31m',
            'green': '\\033[32m',
            'yellow': '\\033[33m',
            'cyan': '\\033[36m',
        }
        
        return colors.get(color, '')