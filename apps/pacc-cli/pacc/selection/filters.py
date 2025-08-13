"""Advanced filtering components for selection workflow."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
import fnmatch
import stat
import time

from ..validators import ValidationResult


class FilterOperator(Enum):
    """Logical operators for combining filters."""
    AND = "and"
    OR = "or"
    NOT = "not"


class SortCriteria(Enum):
    """Criteria for sorting filtered results."""
    NAME = "name"
    SIZE = "size"
    MODIFIED = "modified"
    CREATED = "created"
    EXTENSION = "extension"
    PATH_DEPTH = "path_depth"
    VALIDATION_SCORE = "validation_score"


@dataclass
class FilterResult:
    """Result of applying a filter."""
    
    passed: bool
    score: float = 0.0  # Relevance score for ranking
    metadata: Dict[str, Any] = None
    reason: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseFilter(ABC):
    """Base class for file filters."""
    
    def __init__(self, weight: float = 1.0, required: bool = True):
        """Initialize base filter.
        
        Args:
            weight: Weight for scoring when combining filters
            required: Whether this filter must pass for file to be included
        """
        self.weight = weight
        self.required = required
    
    @abstractmethod
    def apply(self, file_path: Path, context: Dict[str, Any] = None) -> FilterResult:
        """Apply filter to a file path.
        
        Args:
            file_path: Path to filter
            context: Optional context information
            
        Returns:
            Filter result
        """
        pass
    
    def __call__(self, file_path: Path, context: Dict[str, Any] = None) -> FilterResult:
        """Make filter callable."""
        return self.apply(file_path, context)


class ExtensionFilter(BaseFilter):
    """Filter files by extension."""
    
    def __init__(
        self,
        extensions: Set[str],
        case_sensitive: bool = False,
        **kwargs
    ):
        """Initialize extension filter.
        
        Args:
            extensions: Set of allowed extensions (with or without dots)
            case_sensitive: Whether to match case sensitively
            **kwargs: Base filter arguments
        """
        super().__init__(**kwargs)
        
        # Normalize extensions
        self.extensions = set()
        for ext in extensions:
            ext = ext if ext.startswith('.') else f'.{ext}'
            self.extensions.add(ext.lower() if not case_sensitive else ext)
        
        self.case_sensitive = case_sensitive
    
    def apply(self, file_path: Path, context: Dict[str, Any] = None) -> FilterResult:
        """Apply extension filter."""
        file_ext = file_path.suffix
        if not self.case_sensitive:
            file_ext = file_ext.lower()
        
        passed = file_ext in self.extensions
        score = 1.0 if passed else 0.0
        
        return FilterResult(
            passed=passed,
            score=score,
            metadata={'extension': file_ext},
            reason=f"Extension '{file_ext}' {'matches' if passed else 'does not match'} allowed extensions"
        )


class PatternFilter(BaseFilter):
    """Filter files by name patterns."""
    
    def __init__(
        self,
        patterns: List[str],
        pattern_type: str = "glob",  # "glob" or "regex"
        **kwargs
    ):
        """Initialize pattern filter.
        
        Args:
            patterns: List of patterns to match
            pattern_type: Type of patterns ("glob" or "regex")
            **kwargs: Base filter arguments
        """
        super().__init__(**kwargs)
        self.patterns = patterns
        self.pattern_type = pattern_type
        
        # Compile regex patterns if needed
        if pattern_type == "regex":
            self.compiled_patterns = []
            for pattern in patterns:
                try:
                    self.compiled_patterns.append(re.compile(pattern))
                except re.error as e:
                    raise ValueError(f"Invalid regex pattern '{pattern}': {e}")
        else:
            self.compiled_patterns = None
    
    def apply(self, file_path: Path, context: Dict[str, Any] = None) -> FilterResult:
        """Apply pattern filter."""
        filename = file_path.name
        
        if self.pattern_type == "regex":
            for pattern in self.compiled_patterns:
                if pattern.search(filename):
                    return FilterResult(
                        passed=True,
                        score=1.0,
                        metadata={'matched_pattern': pattern.pattern},
                        reason=f"Filename matches regex pattern '{pattern.pattern}'"
                    )
        else:
            for pattern in self.patterns:
                if fnmatch.fnmatch(filename, pattern):
                    return FilterResult(
                        passed=True,
                        score=1.0,
                        metadata={'matched_pattern': pattern},
                        reason=f"Filename matches glob pattern '{pattern}'"
                    )
        
        return FilterResult(
            passed=False,
            score=0.0,
            reason=f"Filename does not match any {self.pattern_type} patterns"
        )


class SizeFilter(BaseFilter):
    """Filter files by size."""
    
    def __init__(
        self,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        **kwargs
    ):
        """Initialize size filter.
        
        Args:
            min_size: Minimum file size in bytes
            max_size: Maximum file size in bytes
            **kwargs: Base filter arguments
        """
        super().__init__(**kwargs)
        self.min_size = min_size
        self.max_size = max_size
    
    def apply(self, file_path: Path, context: Dict[str, Any] = None) -> FilterResult:
        """Apply size filter."""
        try:
            file_size = file_path.stat().st_size
            
            passed = True
            reasons = []
            
            if self.min_size is not None and file_size < self.min_size:
                passed = False
                reasons.append(f"size {file_size} < minimum {self.min_size}")
            
            if self.max_size is not None and file_size > self.max_size:
                passed = False
                reasons.append(f"size {file_size} > maximum {self.max_size}")
            
            # Calculate score based on how well size fits within range
            score = 1.0 if passed else 0.0
            if passed and self.min_size is not None and self.max_size is not None:
                # Score based on position within range
                range_size = self.max_size - self.min_size
                if range_size > 0:
                    position = (file_size - self.min_size) / range_size
                    # Score is higher for files in the middle of the range
                    score = 1.0 - abs(position - 0.5) * 2
            
            return FilterResult(
                passed=passed,
                score=score,
                metadata={'file_size': file_size},
                reason=' and '.join(reasons) if reasons else f"Size {file_size} is within limits"
            )
            
        except OSError as e:
            return FilterResult(
                passed=False,
                score=0.0,
                reason=f"Cannot access file size: {e}"
            )


class ModificationTimeFilter(BaseFilter):
    """Filter files by modification time."""
    
    def __init__(
        self,
        after: Optional[float] = None,
        before: Optional[float] = None,
        **kwargs
    ):
        """Initialize modification time filter.
        
        Args:
            after: Files modified after this timestamp
            before: Files modified before this timestamp
            **kwargs: Base filter arguments
        """
        super().__init__(**kwargs)
        self.after = after
        self.before = before
    
    def apply(self, file_path: Path, context: Dict[str, Any] = None) -> FilterResult:
        """Apply modification time filter."""
        try:
            mtime = file_path.stat().st_mtime
            
            passed = True
            reasons = []
            
            if self.after is not None and mtime < self.after:
                passed = False
                reasons.append(f"modified {time.ctime(mtime)} before {time.ctime(self.after)}")
            
            if self.before is not None and mtime > self.before:
                passed = False
                reasons.append(f"modified {time.ctime(mtime)} after {time.ctime(self.before)}")
            
            # Score based on recency (more recent = higher score)
            score = 1.0 if passed else 0.0
            if passed:
                now = time.time()
                # Files modified within last day get highest score
                age_days = (now - mtime) / (24 * 3600)
                if age_days < 1:
                    score = 1.0
                elif age_days < 7:
                    score = 0.8
                elif age_days < 30:
                    score = 0.6
                else:
                    score = 0.4
            
            return FilterResult(
                passed=passed,
                score=score,
                metadata={'modification_time': mtime},
                reason=' and '.join(reasons) if reasons else f"Modified {time.ctime(mtime)}"
            )
            
        except OSError as e:
            return FilterResult(
                passed=False,
                score=0.0,
                reason=f"Cannot access modification time: {e}"
            )


class PathDepthFilter(BaseFilter):
    """Filter files by path depth."""
    
    def __init__(
        self,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
        base_path: Optional[Path] = None,
        **kwargs
    ):
        """Initialize path depth filter.
        
        Args:
            min_depth: Minimum path depth
            max_depth: Maximum path depth
            base_path: Base path for depth calculation
            **kwargs: Base filter arguments
        """
        super().__init__(**kwargs)
        self.min_depth = min_depth
        self.max_depth = max_depth
        self.base_path = base_path
    
    def apply(self, file_path: Path, context: Dict[str, Any] = None) -> FilterResult:
        """Apply path depth filter."""
        # Calculate depth relative to base path or absolute
        if self.base_path:
            try:
                relative_path = file_path.relative_to(self.base_path)
                depth = len(relative_path.parts) - 1  # Exclude filename
            except ValueError:
                # Path is not relative to base_path
                depth = len(file_path.parts) - 1
        else:
            depth = len(file_path.parts) - 1
        
        passed = True
        reasons = []
        
        if self.min_depth is not None and depth < self.min_depth:
            passed = False
            reasons.append(f"depth {depth} < minimum {self.min_depth}")
        
        if self.max_depth is not None and depth > self.max_depth:
            passed = False
            reasons.append(f"depth {depth} > maximum {self.max_depth}")
        
        # Score based on preferred depth (shallower is often better)
        score = 1.0 if passed else 0.0
        if passed:
            # Prefer files closer to the surface
            score = max(0.1, 1.0 - (depth * 0.1))
        
        return FilterResult(
            passed=passed,
            score=score,
            metadata={'path_depth': depth},
            reason=' and '.join(reasons) if reasons else f"Path depth {depth}"
        )


class ValidationScoreFilter(BaseFilter):
    """Filter files based on validation results."""
    
    def __init__(
        self,
        min_score: float = 0.0,
        require_valid: bool = True,
        **kwargs
    ):
        """Initialize validation score filter.
        
        Args:
            min_score: Minimum validation score (0.0 to 1.0)
            require_valid: Whether file must pass validation
            **kwargs: Base filter arguments
        """
        super().__init__(**kwargs)
        self.min_score = min_score
        self.require_valid = require_valid
    
    def apply(self, file_path: Path, context: Dict[str, Any] = None) -> FilterResult:
        """Apply validation score filter."""
        if context is None:
            context = {}
        
        validation_results = context.get('validation_results', [])
        
        # Find validation result for this file
        file_result = None
        for result in validation_results:
            if result.file_path and Path(result.file_path) == file_path:
                file_result = result
                break
        
        if file_result is None:
            # No validation result available
            if self.require_valid:
                return FilterResult(
                    passed=False,
                    score=0.0,
                    reason="No validation result available"
                )
            else:
                return FilterResult(
                    passed=True,
                    score=0.5,  # Neutral score
                    reason="No validation result available"
                )
        
        # Calculate validation score
        validation_score = self._calculate_validation_score(file_result)
        
        passed = validation_score >= self.min_score
        if self.require_valid:
            passed = passed and file_result.is_valid
        
        return FilterResult(
            passed=passed,
            score=validation_score,
            metadata={
                'validation_score': validation_score,
                'is_valid': file_result.is_valid,
                'error_count': len(file_result.errors),
                'warning_count': len(file_result.warnings)
            },
            reason=f"Validation score {validation_score:.2f}, valid: {file_result.is_valid}"
        )
    
    def _calculate_validation_score(self, result: ValidationResult) -> float:
        """Calculate validation score from result."""
        if result.is_valid and not result.warnings:
            return 1.0
        
        # Start with base score
        score = 0.8 if result.is_valid else 0.2
        
        # Penalize errors and warnings
        error_penalty = len(result.errors) * 0.3
        warning_penalty = len(result.warnings) * 0.1
        
        score -= (error_penalty + warning_penalty)
        
        return max(0.0, min(1.0, score))


class SelectionFilter:
    """Main filter manager that combines multiple filters."""
    
    def __init__(self, operator: FilterOperator = FilterOperator.AND):
        """Initialize selection filter.
        
        Args:
            operator: How to combine multiple filters
        """
        self.operator = operator
        self.filters: List[BaseFilter] = []
    
    def add_filter(self, filter_instance: BaseFilter) -> 'SelectionFilter':
        """Add a filter to the selection.
        
        Args:
            filter_instance: Filter to add
            
        Returns:
            Self for method chaining
        """
        self.filters.append(filter_instance)
        return self
    
    def add_extension_filter(self, extensions: Set[str], **kwargs) -> 'SelectionFilter':
        """Add extension filter.
        
        Args:
            extensions: Set of allowed extensions
            **kwargs: Filter arguments
            
        Returns:
            Self for method chaining
        """
        return self.add_filter(ExtensionFilter(extensions, **kwargs))
    
    def add_pattern_filter(self, patterns: List[str], **kwargs) -> 'SelectionFilter':
        """Add pattern filter.
        
        Args:
            patterns: List of patterns to match
            **kwargs: Filter arguments
            
        Returns:
            Self for method chaining
        """
        return self.add_filter(PatternFilter(patterns, **kwargs))
    
    def add_size_filter(
        self,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        **kwargs
    ) -> 'SelectionFilter':
        """Add size filter.
        
        Args:
            min_size: Minimum file size
            max_size: Maximum file size
            **kwargs: Filter arguments
            
        Returns:
            Self for method chaining
        """
        return self.add_filter(SizeFilter(min_size, max_size, **kwargs))
    
    def add_modification_filter(
        self,
        after: Optional[float] = None,
        before: Optional[float] = None,
        **kwargs
    ) -> 'SelectionFilter':
        """Add modification time filter.
        
        Args:
            after: Files modified after timestamp
            before: Files modified before timestamp
            **kwargs: Filter arguments
            
        Returns:
            Self for method chaining
        """
        return self.add_filter(ModificationTimeFilter(after, before, **kwargs))
    
    def add_depth_filter(
        self,
        min_depth: Optional[int] = None,
        max_depth: Optional[int] = None,
        base_path: Optional[Path] = None,
        **kwargs
    ) -> 'SelectionFilter':
        """Add path depth filter.
        
        Args:
            min_depth: Minimum path depth
            max_depth: Maximum path depth
            base_path: Base path for depth calculation
            **kwargs: Filter arguments
            
        Returns:
            Self for method chaining
        """
        return self.add_filter(PathDepthFilter(min_depth, max_depth, base_path, **kwargs))
    
    def add_validation_filter(
        self,
        min_score: float = 0.0,
        require_valid: bool = True,
        **kwargs
    ) -> 'SelectionFilter':
        """Add validation score filter.
        
        Args:
            min_score: Minimum validation score
            require_valid: Whether validation must pass
            **kwargs: Filter arguments
            
        Returns:
            Self for method chaining
        """
        return self.add_filter(ValidationScoreFilter(min_score, require_valid, **kwargs))
    
    def apply(
        self,
        files: List[Path],
        context: Dict[str, Any] = None
    ) -> List[tuple[Path, float]]:
        """Apply all filters to file list.
        
        Args:
            files: List of files to filter
            context: Optional context information
            
        Returns:
            List of (file_path, score) tuples for files that pass
        """
        if not self.filters:
            # No filters, return all files with neutral score
            return [(f, 0.5) for f in files]
        
        results = []
        
        for file_path in files:
            # Apply all filters
            filter_results = []
            for filter_instance in self.filters:
                result = filter_instance.apply(file_path, context)
                filter_results.append(result)
            
            # Combine results based on operator
            combined_result = self._combine_results(filter_results)
            
            if combined_result.passed:
                results.append((file_path, combined_result.score))
        
        return results
    
    def filter_and_sort(
        self,
        files: List[Path],
        sort_by: SortCriteria = SortCriteria.NAME,
        reverse: bool = False,
        context: Dict[str, Any] = None
    ) -> List[Path]:
        """Filter files and sort by criteria.
        
        Args:
            files: List of files to filter and sort
            sort_by: Sorting criteria
            reverse: Whether to reverse sort order
            context: Optional context information
            
        Returns:
            Filtered and sorted list of files
        """
        # Apply filters
        filtered_results = self.apply(files, context)
        
        if not filtered_results:
            return []
        
        # Sort by criteria
        if sort_by == SortCriteria.NAME:
            key_func = lambda x: x[0].name.lower()
        elif sort_by == SortCriteria.SIZE:
            key_func = lambda x: self._get_file_size(x[0])
        elif sort_by == SortCriteria.MODIFIED:
            key_func = lambda x: self._get_mtime(x[0])
        elif sort_by == SortCriteria.CREATED:
            key_func = lambda x: self._get_ctime(x[0])
        elif sort_by == SortCriteria.EXTENSION:
            key_func = lambda x: x[0].suffix.lower()
        elif sort_by == SortCriteria.PATH_DEPTH:
            key_func = lambda x: len(x[0].parts)
        elif sort_by == SortCriteria.VALIDATION_SCORE:
            key_func = lambda x: x[1]  # Use filter score
        else:
            key_func = lambda x: x[0].name.lower()
        
        try:
            sorted_results = sorted(filtered_results, key=key_func, reverse=reverse)
            return [path for path, score in sorted_results]
        except (OSError, TypeError):
            # Fallback to name sorting if other criteria fail
            sorted_results = sorted(filtered_results, key=lambda x: x[0].name.lower(), reverse=reverse)
            return [path for path, score in sorted_results]
    
    def _combine_results(self, results: List[FilterResult]) -> FilterResult:
        """Combine filter results based on operator."""
        if not results:
            return FilterResult(passed=False, score=0.0)
        
        if self.operator == FilterOperator.AND:
            # All filters must pass
            passed = all(r.passed for r in results)
            
            # Average score of passing filters, 0 if any fail
            if passed:
                score = sum(r.score * self.filters[i].weight for i, r in enumerate(results))
                total_weight = sum(f.weight for f in self.filters)
                score = score / total_weight if total_weight > 0 else 0.0
            else:
                score = 0.0
            
            return FilterResult(passed=passed, score=score)
        
        elif self.operator == FilterOperator.OR:
            # At least one filter must pass
            passed = any(r.passed for r in results)
            
            # Maximum score of all filters
            score = max(r.score for r in results) if results else 0.0
            
            return FilterResult(passed=passed, score=score)
        
        elif self.operator == FilterOperator.NOT:
            # Invert the result of the first filter
            if results:
                first_result = results[0]
                return FilterResult(
                    passed=not first_result.passed,
                    score=1.0 - first_result.score
                )
            
            return FilterResult(passed=False, score=0.0)
        
        else:
            # Default to AND behavior
            return self._combine_results(results)
    
    def _get_file_size(self, path: Path) -> int:
        """Get file size safely."""
        try:
            return path.stat().st_size
        except OSError:
            return 0
    
    def _get_mtime(self, path: Path) -> float:
        """Get modification time safely."""
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0
    
    def _get_ctime(self, path: Path) -> float:
        """Get creation time safely."""
        try:
            return path.stat().st_ctime
        except OSError:
            return 0.0
    
    def clear_filters(self) -> 'SelectionFilter':
        """Clear all filters.
        
        Returns:
            Self for method chaining
        """
        self.filters.clear()
        return self


class MultiCriteriaFilter:
    """Advanced filter that supports multiple criteria and ranking."""
    
    def __init__(self):
        """Initialize multi-criteria filter."""
        self.filter_groups: List[tuple[SelectionFilter, float]] = []  # (filter, weight)
    
    def add_filter_group(
        self,
        filter_group: SelectionFilter,
        weight: float = 1.0
    ) -> 'MultiCriteriaFilter':
        """Add a filter group with weight.
        
        Args:
            filter_group: Selection filter to add
            weight: Weight for this filter group
            
        Returns:
            Self for method chaining
        """
        self.filter_groups.append((filter_group, weight))
        return self
    
    def apply(
        self,
        files: List[Path],
        context: Dict[str, Any] = None
    ) -> List[tuple[Path, float]]:
        """Apply all filter groups and combine scores.
        
        Args:
            files: List of files to filter
            context: Optional context information
            
        Returns:
            List of (file_path, combined_score) tuples
        """
        if not self.filter_groups:
            return [(f, 0.5) for f in files]
        
        # Collect results from all filter groups
        all_results: Dict[Path, List[tuple[float, float]]] = {}  # path -> [(score, weight), ...]
        
        for filter_group, group_weight in self.filter_groups:
            group_results = filter_group.apply(files, context)
            
            for file_path, score in group_results:
                if file_path not in all_results:
                    all_results[file_path] = []
                all_results[file_path].append((score, group_weight))
        
        # Combine scores using weighted average
        final_results = []
        for file_path, scores_weights in all_results.items():
            total_score = sum(score * weight for score, weight in scores_weights)
            total_weight = sum(weight for score, weight in scores_weights)
            
            if total_weight > 0:
                final_score = total_score / total_weight
                final_results.append((file_path, final_score))
        
        # Sort by score (highest first)
        final_results.sort(key=lambda x: x[1], reverse=True)
        
        return final_results
    
    def get_top_matches(
        self,
        files: List[Path],
        limit: int = 10,
        min_score: float = 0.1,
        context: Dict[str, Any] = None
    ) -> List[Path]:
        """Get top matching files.
        
        Args:
            files: List of files to filter
            limit: Maximum number of results
            min_score: Minimum score threshold
            context: Optional context information
            
        Returns:
            List of top matching files
        """
        results = self.apply(files, context)
        
        # Filter by minimum score
        filtered_results = [
            (path, score) for path, score in results
            if score >= min_score
        ]
        
        # Apply limit
        limited_results = filtered_results[:limit]
        
        return [path for path, score in limited_results]