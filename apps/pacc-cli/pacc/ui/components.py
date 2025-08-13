"""UI components for PACC interactive interfaces."""

import sys
import os
from typing import List, Optional, Callable, Dict, Any, Union, Tuple
from dataclasses import dataclass
from pathlib import Path
import re

# Cross-platform keyboard handling
try:
    import msvcrt  # Windows
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

try:
    import termios  # Unix-like
    import tty
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False


@dataclass
class SelectableItem:
    """Represents an item that can be selected in a list."""
    
    id: str
    display_text: str
    description: Optional[str] = None
    selected: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}
    
    def toggle_selection(self) -> None:
        """Toggle selection state."""
        self.selected = not self.selected
    
    def __str__(self) -> str:
        """Return string representation."""
        return self.display_text


class KeyboardHandler:
    """Cross-platform keyboard input handler."""
    
    # Key constants
    KEY_UP = 'up'
    KEY_DOWN = 'down'
    KEY_LEFT = 'left'
    KEY_RIGHT = 'right'
    KEY_ENTER = 'enter'
    KEY_SPACE = 'space'
    KEY_ESCAPE = 'escape'
    KEY_BACKSPACE = 'backspace'
    KEY_DELETE = 'delete'
    KEY_TAB = 'tab'
    KEY_HOME = 'home'
    KEY_END = 'end'
    
    def __init__(self):
        """Initialize keyboard handler."""
        self.is_windows = os.name == 'nt'
        self._old_settings = None
    
    def __enter__(self):
        """Enter context manager - setup raw input mode."""
        if not self.is_windows and HAS_TERMIOS:
            self._old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin.fileno())
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - restore normal input mode."""
        if not self.is_windows and HAS_TERMIOS and self._old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)
    
    def get_key(self) -> Optional[str]:
        """Get a single key press.
        
        Returns:
            Key name or character, None if no input available
        """
        if self.is_windows and HAS_MSVCRT:
            return self._get_key_windows()
        elif HAS_TERMIOS:
            return self._get_key_unix()
        else:
            # Fallback to basic input
            return self._get_key_fallback()
    
    def _get_key_windows(self) -> Optional[str]:
        """Get key on Windows."""
        if not msvcrt.kbhit():
            return None
        
        ch = msvcrt.getch()
        
        # Handle special keys
        if ch == b'\x00' or ch == b'\xe0':  # Special key prefix
            ch2 = msvcrt.getch()
            key_map = {
                b'H': self.KEY_UP,
                b'P': self.KEY_DOWN,
                b'K': self.KEY_LEFT,
                b'M': self.KEY_RIGHT,
                b'G': self.KEY_HOME,
                b'O': self.KEY_END,
                b'S': self.KEY_DELETE,
            }
            return key_map.get(ch2, None)
        
        # Handle normal keys
        if ch == b'\r':
            return self.KEY_ENTER
        elif ch == b' ':
            return self.KEY_SPACE
        elif ch == b'\x1b':
            return self.KEY_ESCAPE
        elif ch == b'\x08':
            return self.KEY_BACKSPACE
        elif ch == b'\t':
            return self.KEY_TAB
        else:
            try:
                return ch.decode('utf-8')
            except UnicodeDecodeError:
                return None
    
    def _get_key_unix(self) -> Optional[str]:
        """Get key on Unix-like systems."""
        ch = sys.stdin.read(1)
        
        if ch == '\x1b':  # ESC sequence
            # Try to read more characters for arrow keys, etc.
            try:
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    key_map = {
                        'A': self.KEY_UP,
                        'B': self.KEY_DOWN,
                        'C': self.KEY_RIGHT,
                        'D': self.KEY_LEFT,
                        'H': self.KEY_HOME,
                        'F': self.KEY_END,
                    }
                    if ch3 in key_map:
                        return key_map[ch3]
                    elif ch3 == '3':  # Delete key
                        sys.stdin.read(1)  # Read the '~'
                        return self.KEY_DELETE
                return self.KEY_ESCAPE
            except:
                return self.KEY_ESCAPE
        
        # Handle normal keys
        if ch == '\r' or ch == '\n':
            return self.KEY_ENTER
        elif ch == ' ':
            return self.KEY_SPACE
        elif ch == '\x7f' or ch == '\x08':
            return self.KEY_BACKSPACE
        elif ch == '\t':
            return self.KEY_TAB
        else:
            return ch
    
    def _get_key_fallback(self) -> Optional[str]:
        """Fallback key input method."""
        try:
            return input()
        except (EOFError, KeyboardInterrupt):
            return self.KEY_ESCAPE


class SearchFilter:
    """Filters items based on search criteria."""
    
    def __init__(self, case_sensitive: bool = False):
        """Initialize search filter.
        
        Args:
            case_sensitive: Whether search should be case sensitive
        """
        self.case_sensitive = case_sensitive
        self.current_query = ""
    
    def set_query(self, query: str) -> None:
        """Set search query.
        
        Args:
            query: Search query string
        """
        self.current_query = query
    
    def filter_items(self, items: List[SelectableItem]) -> List[SelectableItem]:
        """Filter items based on current query.
        
        Args:
            items: List of items to filter
            
        Returns:
            Filtered list of items
        """
        if not self.current_query.strip():
            return items
        
        query = self.current_query if self.case_sensitive else self.current_query.lower()
        filtered = []
        
        for item in items:
            # Search in display text
            display_text = item.display_text if self.case_sensitive else item.display_text.lower()
            if query in display_text:
                filtered.append(item)
                continue
            
            # Search in description
            if item.description:
                description = item.description if self.case_sensitive else item.description.lower()
                if query in description:
                    filtered.append(item)
                    continue
            
            # Search in metadata
            for value in item.metadata.values():
                if isinstance(value, str):
                    search_value = value if self.case_sensitive else value.lower()
                    if query in search_value:
                        filtered.append(item)
                        break
        
        return filtered
    
    def fuzzy_filter_items(self, items: List[SelectableItem]) -> List[SelectableItem]:
        """Filter items using fuzzy matching.
        
        Args:
            items: List of items to filter
            
        Returns:
            Filtered list of items sorted by relevance
        """
        if not self.current_query.strip():
            return items
        
        scored_items = []
        for item in items:
            score = self._fuzzy_score(item)
            if score > 0:
                scored_items.append((score, item))
        
        # Sort by score (higher is better)
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return [item for score, item in scored_items]
    
    def _fuzzy_score(self, item: SelectableItem) -> float:
        """Calculate fuzzy matching score for an item.
        
        Args:
            item: Item to score
            
        Returns:
            Score between 0 and 1 (higher is better match)
        """
        query = self.current_query if self.case_sensitive else self.current_query.lower()
        text = item.display_text if self.case_sensitive else item.display_text.lower()
        
        # Exact match gets highest score
        if query == text:
            return 1.0
        
        # Prefix match gets high score
        if text.startswith(query):
            return 0.9
        
        # Contains match gets medium score
        if query in text:
            return 0.7
        
        # Fuzzy character matching
        query_chars = list(query)
        text_chars = list(text)
        matches = 0
        query_idx = 0
        
        for char in text_chars:
            if query_idx < len(query_chars) and char == query_chars[query_idx]:
                matches += 1
                query_idx += 1
        
        if matches == len(query_chars):
            return 0.5 * (matches / len(text))
        
        return 0.0


class PreviewPane:
    """Displays preview information for selected items."""
    
    def __init__(self, width: int = 40, height: int = 10):
        """Initialize preview pane.
        
        Args:
            width: Width of preview pane in characters
            height: Height of preview pane in lines
        """
        self.width = width
        self.height = height
    
    def render_item_preview(self, item: SelectableItem) -> str:
        """Render preview for an item.
        
        Args:
            item: Item to preview
            
        Returns:
            Formatted preview string
        """
        lines = []
        
        # Title
        lines.append(f"📄 {item.display_text}")
        lines.append("─" * min(len(item.display_text) + 3, self.width))
        
        # Description
        if item.description:
            lines.append("")
            lines.extend(self._wrap_text(item.description, self.width))
        
        # Metadata
        if item.metadata:
            lines.append("")
            lines.append("Details:")
            for key, value in item.metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    lines.append(f"  {key}: {value}")
        
        # Truncate to height
        if len(lines) > self.height:
            lines = lines[:self.height - 1]
            lines.append("...")
        
        return "\n".join(lines)
    
    def render_file_preview(self, file_path: Path, max_lines: int = 20) -> str:
        """Render preview for a file.
        
        Args:
            file_path: Path to file to preview
            max_lines: Maximum lines to show
            
        Returns:
            Formatted file preview
        """
        lines = [f"📁 {file_path.name}", "─" * min(len(file_path.name) + 3, self.width)]
        
        try:
            # File info
            stat = file_path.stat()
            lines.append(f"Size: {stat.st_size} bytes")
            lines.append(f"Path: {file_path}")
            lines.append("")
            
            # File content preview
            if file_path.is_file():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content_lines = []
                        for i, line in enumerate(f):
                            if i >= max_lines:
                                content_lines.append("...")
                                break
                            content_lines.append(line.rstrip())
                        
                        if content_lines:
                            lines.append("Content:")
                            lines.extend(content_lines)
                        
                except UnicodeDecodeError:
                    lines.append("Binary file - cannot preview")
                except OSError:
                    lines.append("Cannot read file")
            
        except OSError:
            lines.append("Cannot access file")
        
        # Truncate to height
        if len(lines) > self.height:
            lines = lines[:self.height - 1]
            lines.append("...")
        
        return "\n".join(lines)
    
    def _wrap_text(self, text: str, width: int) -> List[str]:
        """Wrap text to fit width.
        
        Args:
            text: Text to wrap
            width: Maximum width
            
        Returns:
            List of wrapped lines
        """
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= width:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines


class MultiSelectList:
    """Interactive multi-select list component."""
    
    def __init__(
        self, 
        items: List[SelectableItem],
        title: str = "Select items:",
        allow_multiple: bool = True,
        show_preview: bool = False,
        preview_width: int = 40
    ):
        """Initialize multi-select list.
        
        Args:
            items: List of selectable items
            title: Title to display
            allow_multiple: Whether multiple selection is allowed
            show_preview: Whether to show preview pane
            preview_width: Width of preview pane
        """
        self.items = items
        self.filtered_items = items.copy()
        self.title = title
        self.allow_multiple = allow_multiple
        self.show_preview = show_preview
        
        self.current_index = 0
        self.scroll_offset = 0
        self.terminal_height = 20  # Default height
        self.terminal_width = 80   # Default width
        
        self.search_filter = SearchFilter()
        self.preview_pane = PreviewPane(width=preview_width) if show_preview else None
        self.search_mode = False
        self.search_query = ""
        
        self._update_terminal_size()
    
    def _update_terminal_size(self) -> None:
        """Update terminal size information."""
        try:
            import shutil
            size = shutil.get_terminal_size()
            self.terminal_width = size.columns
            self.terminal_height = size.lines
        except:
            pass  # Use defaults
    
    def run(self) -> List[SelectableItem]:
        """Run the interactive selection interface.
        
        Returns:
            List of selected items
        """
        if not self.items:
            return []
        
        with KeyboardHandler() as kbd:
            while True:
                self._render()
                
                key = kbd.get_key()
                if key is None:
                    continue
                
                if key == KeyboardHandler.KEY_ESCAPE:
                    return []
                elif key == KeyboardHandler.KEY_ENTER:
                    if self.search_mode:
                        self._exit_search_mode()
                    else:
                        return self._get_selected_items()
                elif key == KeyboardHandler.KEY_UP:
                    if not self.search_mode:
                        self._move_up()
                elif key == KeyboardHandler.KEY_DOWN:
                    if not self.search_mode:
                        self._move_down()
                elif key == KeyboardHandler.KEY_SPACE:
                    if not self.search_mode:
                        self._toggle_current_item()
                elif key == '/':
                    self._enter_search_mode()
                elif key == KeyboardHandler.KEY_BACKSPACE:
                    if self.search_mode:
                        self._handle_search_backspace()
                elif self.search_mode and isinstance(key, str) and len(key) == 1 and key.isprintable():
                    self._handle_search_input(key)
                elif key == 'q' and not self.search_mode:
                    return []
    
    def _render(self) -> None:
        """Render the current state of the interface."""
        # Clear screen
        print('\033[2J\033[H', end='')
        
        # Render title
        print(f"\033[1m{self.title}\033[0m")
        
        # Render search bar if in search mode
        if self.search_mode:
            print(f"Search: {self.search_query}_")
        else:
            print("Use ↑/↓ to navigate, SPACE to select, ENTER to confirm, / to search, q to quit")
        
        print()
        
        # Calculate layout
        list_width = self.terminal_width
        if self.show_preview and self.preview_pane:
            list_width = self.terminal_width - self.preview_pane.width - 3
        
        available_height = self.terminal_height - 6  # Reserve space for header and footer
        
        # Render items
        if not self.filtered_items:
            print("No items found.")
            return
        
        # Adjust scroll offset
        if self.current_index < self.scroll_offset:
            self.scroll_offset = self.current_index
        elif self.current_index >= self.scroll_offset + available_height:
            self.scroll_offset = self.current_index - available_height + 1
        
        # Render visible items
        for i in range(available_height):
            item_index = self.scroll_offset + i
            if item_index >= len(self.filtered_items):
                break
            
            item = self.filtered_items[item_index]
            
            # Format item line
            marker = "●" if item.selected else "○"
            cursor = "▶" if item_index == self.current_index else " "
            
            # Truncate text to fit
            display_text = item.display_text
            max_text_width = list_width - 10  # Reserve space for markers
            if len(display_text) > max_text_width:
                display_text = display_text[:max_text_width - 3] + "..."
            
            line = f"{cursor} {marker} {display_text}"
            
            # Highlight current item
            if item_index == self.current_index:
                line = f"\033[7m{line}\033[0m"  # Reverse video
            
            print(line)
        
        # Render preview pane if enabled
        if self.show_preview and self.preview_pane and self.filtered_items:
            current_item = self.filtered_items[self.current_index]
            preview = self.preview_pane.render_item_preview(current_item)
            
            # Move cursor to top right for preview
            lines = preview.split('\n')
            for i, line in enumerate(lines):
                print(f"\033[{2 + i};{list_width + 3}H{line}")
        
        # Render status line
        selected_count = len(self._get_selected_items())
        total_count = len(self.filtered_items)
        status = f"Selected: {selected_count}, Total: {total_count}"
        print(f"\n{status}")
        
        sys.stdout.flush()
    
    def _move_up(self) -> None:
        """Move cursor up."""
        if self.current_index > 0:
            self.current_index -= 1
    
    def _move_down(self) -> None:
        """Move cursor down."""
        if self.current_index < len(self.filtered_items) - 1:
            self.current_index += 1
    
    def _toggle_current_item(self) -> None:
        """Toggle selection of current item."""
        if not self.filtered_items:
            return
        
        current_item = self.filtered_items[self.current_index]
        
        if not self.allow_multiple:
            # Single selection - deselect all others
            for item in self.items:
                item.selected = False
        
        current_item.toggle_selection()
    
    def _enter_search_mode(self) -> None:
        """Enter search mode."""
        self.search_mode = True
        self.search_query = ""
        self._update_filtered_items()
    
    def _exit_search_mode(self) -> None:
        """Exit search mode."""
        self.search_mode = False
        self.search_query = ""
        self.search_filter.set_query("")
        self._update_filtered_items()
    
    def _handle_search_input(self, char: str) -> None:
        """Handle search input character."""
        self.search_query += char
        self.search_filter.set_query(self.search_query)
        self._update_filtered_items()
        
        # Reset cursor position
        self.current_index = 0
    
    def _handle_search_backspace(self) -> None:
        """Handle backspace in search mode."""
        if self.search_query:
            self.search_query = self.search_query[:-1]
            self.search_filter.set_query(self.search_query)
            self._update_filtered_items()
            
            # Reset cursor position
            self.current_index = 0
    
    def _update_filtered_items(self) -> None:
        """Update filtered items based on search query."""
        if self.search_query:
            self.filtered_items = self.search_filter.fuzzy_filter_items(self.items)
        else:
            self.filtered_items = self.items.copy()
        
        # Ensure current index is valid
        if self.current_index >= len(self.filtered_items):
            self.current_index = max(0, len(self.filtered_items) - 1)
    
    def _get_selected_items(self) -> List[SelectableItem]:
        """Get list of currently selected items."""
        return [item for item in self.items if item.selected]