"""Retry mechanisms with exponential backoff and policy management."""

import asyncio
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
import logging

from ..errors import PACCError


logger = logging.getLogger(__name__)


class RetryCondition(Enum):
    """Conditions for when to retry operations."""
    ALWAYS = "always"
    ON_FAILURE = "on_failure"
    ON_SPECIFIC_ERRORS = "on_specific_errors"
    NEVER = "never"


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    
    attempt_number: int
    delay: float
    error: Optional[Exception] = None
    success: bool = False
    timestamp: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class RetryResult:
    """Result of retry operations."""
    
    success: bool
    final_result: Any = None
    total_attempts: int = 0
    total_delay: float = 0.0
    attempts: List[RetryAttempt] = None
    final_error: Optional[Exception] = None
    
    def __post_init__(self):
        if self.attempts is None:
            self.attempts = []


class BackoffStrategy(ABC):
    """Base class for backoff strategies."""
    
    @abstractmethod
    def calculate_delay(self, attempt: int, base_delay: float) -> float:
        """Calculate delay for given attempt.
        
        Args:
            attempt: Attempt number (1-based)
            base_delay: Base delay in seconds
            
        Returns:
            Delay in seconds
        """
        pass


class ExponentialBackoff(BackoffStrategy):
    """Exponential backoff with optional jitter."""
    
    def __init__(
        self,
        multiplier: float = 2.0,
        max_delay: float = 300.0,
        jitter: bool = True,
        jitter_range: float = 0.1
    ):
        """Initialize exponential backoff.
        
        Args:
            multiplier: Backoff multiplier
            max_delay: Maximum delay in seconds
            jitter: Whether to add random jitter
            jitter_range: Jitter range as fraction of delay
        """
        self.multiplier = multiplier
        self.max_delay = max_delay
        self.jitter = jitter
        self.jitter_range = jitter_range
    
    def calculate_delay(self, attempt: int, base_delay: float) -> float:
        """Calculate exponential backoff delay."""
        # Calculate exponential delay
        delay = base_delay * (self.multiplier ** (attempt - 1))
        
        # Apply maximum delay limit
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            jitter_amount = delay * self.jitter_range
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay + jitter)
        
        return delay


class LinearBackoff(BackoffStrategy):
    """Linear backoff strategy."""
    
    def __init__(self, increment: float = 1.0, max_delay: float = 60.0):
        """Initialize linear backoff.
        
        Args:
            increment: Delay increment per attempt
            max_delay: Maximum delay in seconds
        """
        self.increment = increment
        self.max_delay = max_delay
    
    def calculate_delay(self, attempt: int, base_delay: float) -> float:
        """Calculate linear backoff delay."""
        delay = base_delay + (self.increment * (attempt - 1))
        return min(delay, self.max_delay)


class FixedBackoff(BackoffStrategy):
    """Fixed delay backoff strategy."""
    
    def __init__(self, fixed_delay: float = 1.0):
        """Initialize fixed backoff.
        
        Args:
            fixed_delay: Fixed delay in seconds
        """
        self.fixed_delay = fixed_delay
    
    def calculate_delay(self, attempt: int, base_delay: float) -> float:
        """Return fixed delay."""
        return self.fixed_delay


class RetryPolicy:
    """Policy defining retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        backoff_strategy: Optional[BackoffStrategy] = None,
        retry_condition: RetryCondition = RetryCondition.ON_FAILURE,
        retryable_errors: Optional[List[type]] = None,
        stop_on_success: bool = True,
        timeout: Optional[float] = None
    ):
        """Initialize retry policy.
        
        Args:
            max_attempts: Maximum number of attempts
            base_delay: Base delay between attempts
            backoff_strategy: Strategy for calculating delays
            retry_condition: When to retry operations
            retryable_errors: Specific error types that trigger retry
            stop_on_success: Whether to stop retrying on success
            timeout: Total timeout for all attempts
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.backoff_strategy = backoff_strategy or ExponentialBackoff()
        self.retry_condition = retry_condition
        self.retryable_errors = retryable_errors or []
        self.stop_on_success = stop_on_success
        self.timeout = timeout
    
    def should_retry(self, attempt: int, error: Optional[Exception] = None) -> bool:
        """Check if operation should be retried.
        
        Args:
            attempt: Current attempt number
            error: Error that occurred (if any)
            
        Returns:
            True if operation should be retried
        """
        # Check attempt limit
        if attempt >= self.max_attempts:
            return False
        
        # Check retry condition
        if self.retry_condition == RetryCondition.NEVER:
            return False
        
        if self.retry_condition == RetryCondition.ALWAYS:
            return True
        
        if self.retry_condition == RetryCondition.ON_FAILURE:
            return error is not None
        
        if self.retry_condition == RetryCondition.ON_SPECIFIC_ERRORS:
            if error is None:
                return False
            
            return any(isinstance(error, err_type) for err_type in self.retryable_errors)
        
        return False
    
    def get_delay(self, attempt: int) -> float:
        """Get delay for given attempt.
        
        Args:
            attempt: Attempt number
            
        Returns:
            Delay in seconds
        """
        return self.backoff_strategy.calculate_delay(attempt, self.base_delay)


class RetryManager:
    """Manager for retry operations."""
    
    def __init__(self, default_policy: Optional[RetryPolicy] = None):
        """Initialize retry manager.
        
        Args:
            default_policy: Default retry policy
        """
        self.default_policy = default_policy or RetryPolicy()
    
    async def retry_async(
        self,
        func: Callable,
        *args,
        policy: Optional[RetryPolicy] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> RetryResult:
        """Retry an async function with exponential backoff.
        
        Args:
            func: Async function to retry
            *args: Function arguments
            policy: Retry policy (uses default if None)
            context: Optional context for logging
            **kwargs: Function keyword arguments
            
        Returns:
            Retry result
        """
        retry_policy = policy or self.default_policy
        context = context or {}
        
        result = RetryResult(success=False)
        start_time = time.time()
        
        for attempt in range(1, retry_policy.max_attempts + 1):
            attempt_start = time.time()
            
            try:
                logger.debug(f"Retry attempt {attempt}/{retry_policy.max_attempts}")
                
                # Execute function
                if asyncio.iscoroutinefunction(func):
                    final_result = await func(*args, **kwargs)
                else:
                    final_result = func(*args, **kwargs)
                
                # Success!
                attempt_info = RetryAttempt(
                    attempt_number=attempt,
                    delay=0.0,
                    success=True,
                    timestamp=attempt_start
                )
                result.attempts.append(attempt_info)
                
                result.success = True
                result.final_result = final_result
                result.total_attempts = attempt
                
                logger.debug(f"Operation succeeded on attempt {attempt}")
                break
                
            except Exception as e:
                # Calculate delay for next attempt
                delay = retry_policy.get_delay(attempt) if attempt < retry_policy.max_attempts else 0.0
                
                attempt_info = RetryAttempt(
                    attempt_number=attempt,
                    delay=delay,
                    error=e,
                    success=False,
                    timestamp=attempt_start
                )
                result.attempts.append(attempt_info)
                result.final_error = e
                
                logger.debug(f"Attempt {attempt} failed: {type(e).__name__}: {e}")
                
                # Check if we should retry
                if not retry_policy.should_retry(attempt, e):
                    logger.debug(f"Not retrying: {retry_policy.retry_condition}")
                    break
                
                # Check timeout
                if retry_policy.timeout:
                    elapsed = time.time() - start_time
                    if elapsed + delay > retry_policy.timeout:
                        logger.debug("Timeout reached, stopping retries")
                        break
                
                # Wait before next attempt
                if delay > 0 and attempt < retry_policy.max_attempts:
                    logger.debug(f"Waiting {delay:.2f}s before next attempt")
                    await asyncio.sleep(delay)
                    result.total_delay += delay
        
        result.total_attempts = len(result.attempts)
        
        if result.success:
            logger.info(f"Operation succeeded after {result.total_attempts} attempts")
        else:
            logger.warning(f"Operation failed after {result.total_attempts} attempts")
        
        return result
    
    def retry_sync(
        self,
        func: Callable,
        *args,
        policy: Optional[RetryPolicy] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> RetryResult:
        """Retry a synchronous function.
        
        Args:
            func: Function to retry
            *args: Function arguments
            policy: Retry policy (uses default if None)
            context: Optional context for logging
            **kwargs: Function keyword arguments
            
        Returns:
            Retry result
        """
        retry_policy = policy or self.default_policy
        context = context or {}
        
        result = RetryResult(success=False)
        start_time = time.time()
        
        for attempt in range(1, retry_policy.max_attempts + 1):
            attempt_start = time.time()
            
            try:
                logger.debug(f"Retry attempt {attempt}/{retry_policy.max_attempts}")
                
                # Execute function
                final_result = func(*args, **kwargs)
                
                # Success!
                attempt_info = RetryAttempt(
                    attempt_number=attempt,
                    delay=0.0,
                    success=True,
                    timestamp=attempt_start
                )
                result.attempts.append(attempt_info)
                
                result.success = True
                result.final_result = final_result
                result.total_attempts = attempt
                
                logger.debug(f"Operation succeeded on attempt {attempt}")
                break
                
            except Exception as e:
                # Calculate delay for next attempt
                delay = retry_policy.get_delay(attempt) if attempt < retry_policy.max_attempts else 0.0
                
                attempt_info = RetryAttempt(
                    attempt_number=attempt,
                    delay=delay,
                    error=e,
                    success=False,
                    timestamp=attempt_start
                )
                result.attempts.append(attempt_info)
                result.final_error = e
                
                logger.debug(f"Attempt {attempt} failed: {type(e).__name__}: {e}")
                
                # Check if we should retry
                if not retry_policy.should_retry(attempt, e):
                    logger.debug(f"Not retrying: {retry_policy.retry_condition}")
                    break
                
                # Check timeout
                if retry_policy.timeout:
                    elapsed = time.time() - start_time
                    if elapsed + delay > retry_policy.timeout:
                        logger.debug("Timeout reached, stopping retries")
                        break
                
                # Wait before next attempt
                if delay > 0 and attempt < retry_policy.max_attempts:
                    logger.debug(f"Waiting {delay:.2f}s before next attempt")
                    time.sleep(delay)
                    result.total_delay += delay
        
        result.total_attempts = len(result.attempts)
        
        if result.success:
            logger.info(f"Operation succeeded after {result.total_attempts} attempts")
        else:
            logger.warning(f"Operation failed after {result.total_attempts} attempts")
        
        return result
    
    async def retry_with_circuit_breaker(
        self,
        func: Callable,
        *args,
        policy: Optional[RetryPolicy] = None,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        **kwargs
    ) -> RetryResult:
        """Retry with circuit breaker pattern.
        
        Args:
            func: Function to retry
            *args: Function arguments
            policy: Retry policy
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before trying again
            **kwargs: Function keyword arguments
            
        Returns:
            Retry result
        """
        # Simple circuit breaker implementation
        circuit_state = getattr(func, '_circuit_state', 'closed')
        failure_count = getattr(func, '_failure_count', 0)
        last_failure_time = getattr(func, '_last_failure_time', 0)
        
        current_time = time.time()
        
        # Check circuit state
        if circuit_state == 'open':
            if current_time - last_failure_time >= recovery_timeout:
                # Try to close circuit
                circuit_state = 'half_open'
                func._circuit_state = circuit_state
                logger.debug("Circuit breaker: half-open state")
            else:
                # Circuit still open
                logger.warning("Circuit breaker: operation blocked (circuit open)")
                return RetryResult(
                    success=False,
                    final_error=PACCError("Circuit breaker is open")
                )
        
        # Attempt operation
        result = await self.retry_async(func, *args, policy=policy, **kwargs)
        
        # Update circuit state based on result
        if result.success:
            # Reset circuit breaker on success
            func._circuit_state = 'closed'
            func._failure_count = 0
            logger.debug("Circuit breaker: closed (success)")
        else:
            # Increment failure count
            failure_count += 1
            func._failure_count = failure_count
            func._last_failure_time = current_time
            
            if failure_count >= failure_threshold:
                # Open circuit
                func._circuit_state = 'open'
                logger.warning(f"Circuit breaker: opened after {failure_count} failures")
            else:
                func._circuit_state = 'closed'
        
        return result


# Predefined retry policies for common use cases

RETRY_POLICIES = {
    'default': RetryPolicy(
        max_attempts=3,
        base_delay=1.0,
        backoff_strategy=ExponentialBackoff()
    ),
    
    'aggressive': RetryPolicy(
        max_attempts=5,
        base_delay=0.5,
        backoff_strategy=ExponentialBackoff(multiplier=1.5)
    ),
    
    'conservative': RetryPolicy(
        max_attempts=2,
        base_delay=2.0,
        backoff_strategy=LinearBackoff(increment=1.0)
    ),
    
    'network': RetryPolicy(
        max_attempts=5,
        base_delay=1.0,
        backoff_strategy=ExponentialBackoff(max_delay=30.0),
        timeout=120.0,
        retryable_errors=[ConnectionError, TimeoutError]
    ),
    
    'file_operations': RetryPolicy(
        max_attempts=3,
        base_delay=0.1,
        backoff_strategy=ExponentialBackoff(multiplier=2.0, max_delay=5.0),
        retryable_errors=[FileNotFoundError, PermissionError, OSError]
    ),
    
    'validation': RetryPolicy(
        max_attempts=1,  # Usually no point retrying validation
        retry_condition=RetryCondition.NEVER
    ),
    
    'no_retry': RetryPolicy(
        max_attempts=1,
        retry_condition=RetryCondition.NEVER
    )
}


def get_retry_policy(name: str) -> RetryPolicy:
    """Get predefined retry policy by name.
    
    Args:
        name: Policy name
        
    Returns:
        Retry policy instance
    """
    if name not in RETRY_POLICIES:
        logger.warning(f"Unknown retry policy '{name}', using default")
        name = 'default'
    
    return RETRY_POLICIES[name]


class RetryDecorator:
    """Decorator for adding retry behavior to functions."""
    
    def __init__(
        self,
        policy: Optional[Union[str, RetryPolicy]] = None,
        manager: Optional[RetryManager] = None
    ):
        """Initialize retry decorator.
        
        Args:
            policy: Retry policy name or instance
            manager: Retry manager instance
        """
        if isinstance(policy, str):
            self.policy = get_retry_policy(policy)
        else:
            self.policy = policy or RetryPolicy()
        
        self.manager = manager or RetryManager()
    
    def __call__(self, func: Callable) -> Callable:
        """Decorate function with retry behavior."""
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                result = await self.manager.retry_async(
                    func, *args, policy=self.policy, **kwargs
                )
                
                if result.success:
                    return result.final_result
                else:
                    raise result.final_error or PACCError("Retry failed")
            
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                result = self.manager.retry_sync(
                    func, *args, policy=self.policy, **kwargs
                )
                
                if result.success:
                    return result.final_result
                else:
                    raise result.final_error or PACCError("Retry failed")
            
            return sync_wrapper


# Convenient decorator functions
def retry(policy: Union[str, RetryPolicy] = 'default'):
    """Decorator for adding retry behavior with specified policy."""
    return RetryDecorator(policy)


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0):
    """Simple retry decorator for common use cases."""
    policy = RetryPolicy(
        max_attempts=max_attempts,
        base_delay=delay,
        backoff_strategy=ExponentialBackoff()
    )
    return RetryDecorator(policy)