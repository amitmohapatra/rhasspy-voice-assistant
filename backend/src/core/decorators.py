"""Reusable decorators for consistent behavior across the codebase.

This module provides decorators that eliminate code duplication and ensure
consistent error handling, timing, and logging patterns.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

import structlog

from src.core.exceptions import LLMError, ProviderError

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def handle_provider_errors(
    provider_name: str,
    operation: str = "operation",
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Decorator for consistent error handling across providers.

    Wraps async functions with standardized error handling that converts
    exceptions to provider-specific errors with proper logging.

    Args:
        provider_name: Name of the provider (e.g., 'openai', 'anthropic')
        operation: Type of operation (e.g., 'completion', 'embedding', 'streaming')

    Example:
        @handle_provider_errors("openai", "completion")
        async def complete(self, request: CompletionRequest) -> CompletionResponse:
            # ... implementation
    """
    def decorator(
        func: Callable[P, Coroutine[Any, Any, T]]
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except LLMError:
                # Re-raise LLMErrors as-is
                raise
            except ProviderError:
                # Re-raise ProviderErrors as-is
                raise
            except Exception as e:
                # Extract model from kwargs or args
                model = kwargs.get("model", "unknown")
                if hasattr(args[0], "model"):
                    model = getattr(args[0], "model", model)
                elif len(args) > 1 and hasattr(args[1], "model"):
                    model = args[1].model

                logger.error(
                    f"{provider_name}_{operation}_failed",
                    provider=provider_name,
                    operation=operation,
                    model=model,
                    error=str(e),
                    error_type=type(e).__name__,
                )

                raise LLMError(
                    message=f"{provider_name} {operation} failed: {str(e)}",
                    provider=provider_name,
                    details={"model": model, "error": str(e), "error_type": type(e).__name__},
                ) from e

        return wrapper
    return decorator


def measure_execution_time(
    operation_name: str | None = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Decorator to measure and log execution time of async functions.

    Args:
        operation_name: Optional name for the operation in logs.
                       If not provided, uses the function name.

    Example:
        @measure_execution_time("image_generation")
        async def generate_image(self, request):
            # ... implementation
    """
    def decorator(
        func: Callable[P, Coroutine[Any, Any, T]]
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        op_name = operation_name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.perf_counter()

            try:
                result = await func(*args, **kwargs)

                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(
                    f"{op_name}_completed",
                    operation=op_name,
                    duration_ms=round(elapsed_ms, 2),
                )

                # If result has a timing field, set it
                if hasattr(result, "generation_time_ms"):
                    result.generation_time_ms = elapsed_ms
                elif hasattr(result, "elapsed_ms"):
                    result.elapsed_ms = elapsed_ms

                return result

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(
                    f"{op_name}_failed",
                    operation=op_name,
                    duration_ms=round(elapsed_ms, 2),
                    error=str(e),
                )
                raise

        return wrapper
    return decorator


def retry_on_failure(
    max_retries: int = 3,
    delay_seconds: float = 1.0,
    exponential_backoff: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Decorator for automatic retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay_seconds: Initial delay between retries
        exponential_backoff: Whether to use exponential backoff
        retryable_exceptions: Tuple of exception types to retry on

    Example:
        @retry_on_failure(max_retries=3, retryable_exceptions=(RateLimitError,))
        async def call_api(self, request):
            # ... implementation
    """
    def decorator(
        func: Callable[P, Coroutine[Any, Any, T]]
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import asyncio

            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        delay = delay_seconds * (2 ** attempt if exponential_backoff else 1)
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay_seconds=delay,
                            error=str(e),
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "max_retries_exceeded",
                            function=func.__name__,
                            max_retries=max_retries,
                            error=str(e),
                        )

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry logic")

        return wrapper
    return decorator


def cache_result(
    ttl_seconds: int = 300,
    key_func: Callable[..., str] | None = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Decorator for caching async function results with TTL.

    Simple in-memory cache with time-based expiration.

    Args:
        ttl_seconds: Time to live for cached results
        key_func: Optional function to generate cache key from arguments

    Example:
        @cache_result(ttl_seconds=600)
        async def get_model_info(self, model_id: str):
            # ... implementation
    """
    cache: dict[str, tuple[float, Any]] = {}

    def decorator(
        func: Callable[P, Coroutine[Any, Any, T]]
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Default: use function name and string representation of args
                cache_key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"

            current_time = time.time()

            # Check cache
            if cache_key in cache:
                cached_time, cached_result = cache[cache_key]
                if current_time - cached_time < ttl_seconds:
                    return cached_result

            # Call function and cache result
            result = await func(*args, **kwargs)
            cache[cache_key] = (current_time, result)

            # Clean up expired entries periodically
            if len(cache) > 1000:
                expired_keys = [
                    k for k, (t, _) in cache.items()
                    if current_time - t >= ttl_seconds
                ]
                for k in expired_keys:
                    del cache[k]

            return result

        # Add method to clear cache
        wrapper.clear_cache = lambda: cache.clear()  # type: ignore
        return wrapper

    return decorator


def validate_request(
    validator_func: Callable[[Any], None] | None = None,
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    """Decorator for request validation before execution.

    Args:
        validator_func: Optional custom validation function

    Example:
        @validate_request(lambda req: validate_completion_request(req))
        async def complete(self, request: CompletionRequest):
            # ... implementation
    """
    def decorator(
        func: Callable[P, Coroutine[Any, Any, T]]
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Find request argument (usually first positional arg after self)
            request = None
            if len(args) > 1:
                request = args[1]
            elif "request" in kwargs:
                request = kwargs["request"]

            if request and validator_func:
                validator_func(request)

            return await func(*args, **kwargs)

        return wrapper
    return decorator
