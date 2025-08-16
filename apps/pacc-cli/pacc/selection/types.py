"""Shared types for selection workflow to avoid circular imports."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class SelectionMode(Enum):
    """Different modes for selection workflow."""
    SINGLE_FILE = "single_file"
    MULTI_FILE = "multi_file"
    DIRECTORY = "directory"
    INTERACTIVE = "interactive"
    BATCH = "batch"


class SelectionStrategy(Enum):
    """Strategy for handling multiple selections."""
    FIRST_VALID = "first_valid"
    ALL_VALID = "all_valid"
    BEST_MATCH = "best_match"
    USER_CHOICE = "user_choice"


@dataclass
class SelectionContext:
    """Context for a selection operation."""
    
    # Core parameters
    mode: SelectionMode
    strategy: SelectionStrategy = SelectionStrategy.USER_CHOICE
    max_selections: int = 10
    allow_empty: bool = False
    
    # File filtering
    extensions: Optional[Set[str]] = None
    patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    
    # Validation settings
    strict_validation: bool = False
    auto_fix_issues: bool = True
    
    # User interaction
    interactive: bool = True
    confirm_selection: bool = True
    show_preview: bool = True
    
    # Caching and history
    use_cache: bool = True
    save_history: bool = True
    
    # Metadata and tags
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SelectionResult:
    """Result of a selection workflow operation."""
    
    success: bool
    selected_files: List[Path] = field(default_factory=list)
    validation_results: List[Any] = field(default_factory=list)  # List[ValidationResult]
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[Exception] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    user_cancelled: bool = False
    cached_result: bool = False
    
    @property
    def is_valid(self) -> bool:
        """Check if all selected files passed validation."""
        return self.success and all(
            result.is_valid for result in self.validation_results
        )
    
    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return bool(self.warnings) or any(
            result.warnings for result in self.validation_results
        )
    
    def get_all_issues(self) -> List[str]:
        """Get all error and warning messages."""
        issues = []
        
        # Add error messages
        for error in self.errors:
            issues.append(str(error))
        
        # Add warning messages
        issues.extend(self.warnings)
        
        # Add validation issues
        for result in self.validation_results:
            for issue in result.all_issues:
                issues.append(str(issue))
        
        return issues