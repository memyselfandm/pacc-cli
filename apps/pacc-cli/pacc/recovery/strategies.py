"""Recovery strategies for handling errors and failures."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
import logging

from ..errors import PACCError
from .suggestions import SuggestionEngine, FixSuggestion, RecoveryAction
from .retry import RetryManager, RetryPolicy


logger = logging.getLogger(__name__)


class RecoveryMode(Enum):
    """Recovery modes for error handling."""
    FAIL_FAST = "fail_fast"
    AUTO_RECOVER = "auto_recover"  
    INTERACTIVE = "interactive"
    BEST_EFFORT = "best_effort"


@dataclass
class RecoveryContext:
    """Context information for recovery operations."""
    
    operation: str
    error: Exception
    file_path: Optional[Path] = None
    attempt_count: int = 0
    max_attempts: int = 3
    user_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.user_data is None:
            self.user_data = {}


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""
    
    success: bool
    action_taken: Optional[RecoveryAction] = None
    fixed_error: bool = False
    retry_recommended: bool = False
    user_input_required: bool = False
    message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RecoveryStrategy(ABC):
    """Base class for error recovery strategies."""
    
    def __init__(
        self,
        suggestion_engine: Optional[SuggestionEngine] = None,
        retry_manager: Optional[RetryManager] = None
    ):
        """Initialize recovery strategy.
        
        Args:
            suggestion_engine: Engine for generating fix suggestions
            retry_manager: Manager for retry operations
        """
        self.suggestion_engine = suggestion_engine or SuggestionEngine()
        self.retry_manager = retry_manager or RetryManager()
    
    @abstractmethod
    async def recover(self, context: RecoveryContext) -> RecoveryResult:
        """Attempt to recover from error.
        
        Args:
            context: Recovery context with error information
            
        Returns:
            Recovery result
        """
        pass
    
    def can_handle(self, error: Exception) -> bool:
        """Check if strategy can handle the error type.
        
        Args:
            error: Error to check
            
        Returns:
            True if strategy can handle this error
        """
        # Default implementation - can handle any error
        return True
    
    async def _get_suggestions(self, context: RecoveryContext) -> List[FixSuggestion]:
        """Get fix suggestions for the error.
        
        Args:
            context: Recovery context
            
        Returns:
            List of fix suggestions
        """
        return await self.suggestion_engine.analyze_error(
            context.error, 
            context.file_path,
            context.operation
        )
    
    async def _attempt_auto_fix(
        self,
        suggestion: FixSuggestion,
        context: RecoveryContext
    ) -> bool:
        """Attempt to automatically apply a fix suggestion.
        
        Args:
            suggestion: Fix suggestion to apply
            context: Recovery context
            
        Returns:
            True if fix was successfully applied
        """
        try:
            if suggestion.action and suggestion.action.auto_fixable:
                logger.debug(f"Attempting auto-fix: {suggestion.action.description}")
                
                # Execute the fix action
                success = await suggestion.action.execute(context.user_data)
                
                if success:
                    logger.info(f"Auto-fix successful: {suggestion.title}")
                    return True
                else:
                    logger.warning(f"Auto-fix failed: {suggestion.title}")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error during auto-fix: {e}")
            return False


class AutoRecoveryStrategy(RecoveryStrategy):
    """Automatic recovery strategy that attempts fixes without user intervention."""
    
    def __init__(
        self,
        max_auto_fixes: int = 3,
        **kwargs
    ):
        """Initialize auto recovery strategy.
        
        Args:
            max_auto_fixes: Maximum number of auto-fixes to attempt
            **kwargs: Base class arguments
        """
        super().__init__(**kwargs)
        self.max_auto_fixes = max_auto_fixes
    
    async def recover(self, context: RecoveryContext) -> RecoveryResult:
        """Attempt automatic recovery.
        
        Args:
            context: Recovery context
            
        Returns:
            Recovery result
        """
        logger.debug(f"Starting auto-recovery for {context.operation}")
        
        # Get fix suggestions
        suggestions = await self._get_suggestions(context)
        
        if not suggestions:
            return RecoveryResult(
                success=False,
                message="No automatic fixes available"
            )
        
        # Try auto-fixable suggestions
        auto_fixable = [s for s in suggestions if s.action and s.action.auto_fixable]
        
        if not auto_fixable:
            return RecoveryResult(
                success=False,
                retry_recommended=True,
                message="Fixes available but require manual intervention"
            )
        
        # Attempt fixes in order of confidence
        auto_fixable.sort(key=lambda s: s.confidence, reverse=True)
        
        fixes_attempted = 0
        for suggestion in auto_fixable:
            if fixes_attempted >= self.max_auto_fixes:
                break
            
            logger.info(f"Attempting auto-fix: {suggestion.title}")
            
            success = await self._attempt_auto_fix(suggestion, context)
            fixes_attempted += 1
            
            if success:
                return RecoveryResult(
                    success=True,
                    action_taken=suggestion.action,
                    fixed_error=True,
                    retry_recommended=True,
                    message=f"Applied fix: {suggestion.title}"
                )
        
        # No successful fixes
        return RecoveryResult(
            success=False,
            message=f"Attempted {fixes_attempted} auto-fixes, none successful",
            metadata={'attempted_fixes': fixes_attempted}
        )


class InteractiveRecoveryStrategy(RecoveryStrategy):
    """Interactive recovery strategy that involves user in decision making."""
    
    def __init__(
        self,
        max_suggestions: int = 5,
        **kwargs
    ):
        """Initialize interactive recovery strategy.
        
        Args:
            max_suggestions: Maximum number of suggestions to show user
            **kwargs: Base class arguments
        """
        super().__init__(**kwargs)
        self.max_suggestions = max_suggestions
    
    async def recover(self, context: RecoveryContext) -> RecoveryResult:
        """Attempt interactive recovery.
        
        Args:
            context: Recovery context
            
        Returns:
            Recovery result
        """
        logger.debug(f"Starting interactive recovery for {context.operation}")
        
        # Get fix suggestions
        suggestions = await self._get_suggestions(context)
        
        if not suggestions:
            await self._show_error_details(context)
            return RecoveryResult(
                success=False,
                message="No fix suggestions available"
            )
        
        # Show suggestions to user and get choice
        choice = await self._present_suggestions(suggestions[:self.max_suggestions], context)
        
        if choice is None:
            return RecoveryResult(
                success=False,
                message="User cancelled recovery"
            )
        
        if choice == "retry":
            return RecoveryResult(
                success=False,
                retry_recommended=True,
                message="User chose to retry operation"
            )
        
        if choice == "skip":
            return RecoveryResult(
                success=True,
                message="User chose to skip and continue"
            )
        
        # Apply chosen fix
        if isinstance(choice, int) and 0 <= choice < len(suggestions):
            suggestion = suggestions[choice]
            
            if suggestion.action:
                logger.info(f"Applying user-selected fix: {suggestion.title}")
                
                if suggestion.action.auto_fixable:
                    success = await self._attempt_auto_fix(suggestion, context)
                    
                    return RecoveryResult(
                        success=success,
                        action_taken=suggestion.action,
                        fixed_error=success,
                        retry_recommended=True,
                        message=f"{'Applied' if success else 'Failed to apply'} fix: {suggestion.title}"
                    )
                else:
                    # Manual fix - show instructions
                    await self._show_manual_fix_instructions(suggestion)
                    
                    return RecoveryResult(
                        success=False,
                        user_input_required=True,
                        message=f"Manual fix required: {suggestion.title}"
                    )
            else:
                return RecoveryResult(
                    success=False,
                    message="Selected suggestion has no action"
                )
        
        return RecoveryResult(
            success=False,
            message="Invalid user choice"
        )
    
    async def _show_error_details(self, context: RecoveryContext) -> None:
        """Show detailed error information to user.
        
        Args:
            context: Recovery context
        """
        print(f"\\n{self._get_color('red')}Error in {context.operation}:{self._get_color('reset')}")
        print(f"  {type(context.error).__name__}: {context.error}")
        
        if context.file_path:
            print(f"  File: {context.file_path}")
        
        if context.attempt_count > 1:
            print(f"  Attempt: {context.attempt_count}/{context.max_attempts}")
    
    async def _present_suggestions(
        self,
        suggestions: List[FixSuggestion],
        context: RecoveryContext
    ) -> Optional[Union[int, str]]:
        """Present fix suggestions to user and get choice.
        
        Args:
            suggestions: List of fix suggestions
            context: Recovery context
            
        Returns:
            User choice (index, "retry", "skip", or None for cancel)
        """
        await self._show_error_details(context)
        
        print(f"\\n{self._get_color('cyan')}Available fixes:{self._get_color('reset')}")
        
        for i, suggestion in enumerate(suggestions):
            confidence_color = self._get_confidence_color(suggestion.confidence)
            auto_text = " (auto)" if suggestion.action and suggestion.action.auto_fixable else ""
            
            print(f"  {i+1:2d}. {confidence_color}{suggestion.title}{auto_text}{self._get_color('reset')}")
            print(f"      {suggestion.description}")
            
            if suggestion.confidence < 0.5:
                print(f"      {self._get_color('yellow')}⚠ Low confidence fix{self._get_color('reset')}")
        
        print(f"\\n{self._get_color('cyan')}Options:{self._get_color('reset')}")
        print("  r. Retry operation without changes")
        print("  s. Skip this error and continue")
        print("  q. Quit/cancel")
        
        while True:
            try:
                choice = input(f"\\nChoose an option (1-{len(suggestions)}, r, s, q): ").strip().lower()
                
                if choice == 'q':
                    return None
                elif choice == 'r':
                    return "retry"
                elif choice == 's':
                    return "skip"
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(suggestions):
                        return idx
                    else:
                        print(f"{self._get_color('red')}Invalid choice. Please choose 1-{len(suggestions)}.{self._get_color('reset')}")
                else:
                    print(f"{self._get_color('red')}Invalid choice. Please enter a number, 'r', 's', or 'q'.{self._get_color('reset')}")
                    
            except KeyboardInterrupt:
                print(f"\\n{self._get_color('yellow')}Cancelled.{self._get_color('reset')}")
                return None
    
    async def _show_manual_fix_instructions(self, suggestion: FixSuggestion) -> None:
        """Show manual fix instructions to user.
        
        Args:
            suggestion: Fix suggestion with manual instructions
        """
        print(f"\\n{self._get_color('cyan')}Manual Fix Required:{self._get_color('reset')}")
        print(f"  {suggestion.title}")
        print(f"  {suggestion.description}")
        
        if suggestion.action and suggestion.action.instructions:
            print(f"\\n{self._get_color('cyan')}Instructions:{self._get_color('reset')}")
            for i, instruction in enumerate(suggestion.action.instructions, 1):
                print(f"  {i}. {instruction}")
        
        print(f"\\n{self._get_color('yellow')}Please apply the fix manually and retry the operation.{self._get_color('reset')}")
    
    def _get_color(self, color: str) -> str:
        """Get ANSI color code.
        
        Args:
            color: Color name
            
        Returns:
            ANSI color code
        """
        import sys
        
        if not sys.stdout.isatty():
            return ""
        
        colors = {
            'reset': '\\033[0m',
            'red': '\\033[31m',
            'green': '\\033[32m',
            'yellow': '\\033[33m',
            'cyan': '\\033[36m',
            'dim': '\\033[2m',
        }
        
        return colors.get(color, '')
    
    def _get_confidence_color(self, confidence: float) -> str:
        """Get color for confidence level.
        
        Args:
            confidence: Confidence level (0.0 to 1.0)
            
        Returns:
            ANSI color code
        """
        if confidence >= 0.8:
            return self._get_color('green')
        elif confidence >= 0.5:
            return self._get_color('yellow')
        else:
            return self._get_color('red')


class HybridRecoveryStrategy(RecoveryStrategy):
    """Hybrid strategy that combines automatic and interactive recovery."""
    
    def __init__(
        self,
        auto_confidence_threshold: float = 0.8,
        max_auto_fixes: int = 2,
        **kwargs
    ):
        """Initialize hybrid recovery strategy.
        
        Args:
            auto_confidence_threshold: Minimum confidence for auto-fixes
            max_auto_fixes: Maximum number of auto-fixes to attempt
            **kwargs: Base class arguments
        """
        super().__init__(**kwargs)
        self.auto_confidence_threshold = auto_confidence_threshold
        self.max_auto_fixes = max_auto_fixes
        
        # Create sub-strategies
        self.auto_strategy = AutoRecoveryStrategy(
            max_auto_fixes=max_auto_fixes,
            suggestion_engine=self.suggestion_engine,
            retry_manager=self.retry_manager
        )
        self.interactive_strategy = InteractiveRecoveryStrategy(
            suggestion_engine=self.suggestion_engine,
            retry_manager=self.retry_manager
        )
    
    async def recover(self, context: RecoveryContext) -> RecoveryResult:
        """Attempt hybrid recovery (auto first, then interactive).
        
        Args:
            context: Recovery context
            
        Returns:
            Recovery result
        """
        logger.debug(f"Starting hybrid recovery for {context.operation}")
        
        # Get suggestions to analyze
        suggestions = await self._get_suggestions(context)
        
        if not suggestions:
            return RecoveryResult(
                success=False,
                message="No fix suggestions available"
            )
        
        # Check if we have high-confidence auto-fixable suggestions
        high_confidence_auto = [
            s for s in suggestions 
            if (s.action and s.action.auto_fixable and 
                s.confidence >= self.auto_confidence_threshold)
        ]
        
        if high_confidence_auto:
            logger.debug("Attempting automatic recovery with high-confidence fixes")
            
            # Try automatic recovery first
            auto_result = await self.auto_strategy.recover(context)
            
            if auto_result.success:
                return auto_result
            
            # Auto-recovery failed, but we tried, so mention it
            logger.debug("Automatic recovery failed, falling back to interactive")
        
        # Fall back to interactive recovery
        logger.debug("Using interactive recovery")
        interactive_result = await self.interactive_strategy.recover(context)
        
        # Add metadata about the hybrid approach
        if interactive_result.metadata is None:
            interactive_result.metadata = {}
        
        interactive_result.metadata['hybrid_strategy'] = True
        interactive_result.metadata['auto_attempted'] = len(high_confidence_auto) > 0
        
        return interactive_result


class BestEffortRecoveryStrategy(RecoveryStrategy):
    """Best effort strategy that tries to continue despite errors."""
    
    def __init__(
        self,
        skip_on_failure: bool = True,
        collect_errors: bool = True,
        **kwargs
    ):
        """Initialize best effort recovery strategy.
        
        Args:
            skip_on_failure: Whether to skip operations that fail
            collect_errors: Whether to collect errors for later reporting
            **kwargs: Base class arguments
        """
        super().__init__(**kwargs)
        self.skip_on_failure = skip_on_failure
        self.collect_errors = collect_errors
        self.collected_errors: List[tuple[RecoveryContext, Exception]] = []
    
    async def recover(self, context: RecoveryContext) -> RecoveryResult:
        """Attempt best effort recovery.
        
        Args:
            context: Recovery context
            
        Returns:
            Recovery result
        """
        logger.debug(f"Best effort recovery for {context.operation}")
        
        # Collect error if configured
        if self.collect_errors:
            self.collected_errors.append((context, context.error))
        
        # Try quick auto-fixes first
        suggestions = await self._get_suggestions(context)
        quick_fixes = [
            s for s in suggestions 
            if (s.action and s.action.auto_fixable and 
                s.confidence >= 0.9 and s.action.safe)
        ]
        
        for suggestion in quick_fixes:
            logger.debug(f"Attempting quick fix: {suggestion.title}")
            
            success = await self._attempt_auto_fix(suggestion, context)
            if success:
                return RecoveryResult(
                    success=True,
                    action_taken=suggestion.action,
                    fixed_error=True,
                    retry_recommended=True,
                    message=f"Quick fix applied: {suggestion.title}"
                )
        
        # If no quick fixes worked, decide based on skip policy
        if self.skip_on_failure:
            logger.warning(f"Skipping failed operation: {context.operation}")
            
            return RecoveryResult(
                success=True,  # "Success" means we handled it by skipping
                message=f"Skipped due to error: {type(context.error).__name__}",
                metadata={'skipped': True, 'original_error': str(context.error)}
            )
        else:
            return RecoveryResult(
                success=False,
                message=f"Best effort recovery failed: {type(context.error).__name__}"
            )
    
    def get_collected_errors(self) -> List[tuple[RecoveryContext, Exception]]:
        """Get all collected errors.
        
        Returns:
            List of (context, error) tuples
        """
        return self.collected_errors.copy()
    
    def clear_collected_errors(self) -> None:
        """Clear collected errors."""
        self.collected_errors.clear()


def create_recovery_strategy(
    mode: RecoveryMode,
    **kwargs
) -> RecoveryStrategy:
    """Create recovery strategy based on mode.
    
    Args:
        mode: Recovery mode
        **kwargs: Strategy-specific arguments
        
    Returns:
        Recovery strategy instance
    """
    if mode == RecoveryMode.AUTO_RECOVER:
        return AutoRecoveryStrategy(**kwargs)
    elif mode == RecoveryMode.INTERACTIVE:
        return InteractiveRecoveryStrategy(**kwargs)
    elif mode == RecoveryMode.BEST_EFFORT:
        return BestEffortRecoveryStrategy(**kwargs)
    elif mode == RecoveryMode.FAIL_FAST:
        # For fail-fast, we don't actually recover, just return a no-op strategy
        class FailFastStrategy(RecoveryStrategy):
            async def recover(self, context: RecoveryContext) -> RecoveryResult:
                return RecoveryResult(
                    success=False,
                    message="Fail-fast mode: no recovery attempted"
                )
        
        return FailFastStrategy(**kwargs)
    else:
        # Default to hybrid
        return HybridRecoveryStrategy(**kwargs)