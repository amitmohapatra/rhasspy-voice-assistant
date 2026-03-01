"""Reusable HTTP Client utilities for API providers.

This module provides a standardized HTTP client that eliminates
duplicated HTTP request handling across different providers.

Features:
- Shared connection pools for efficiency
- HTTP/2 support when available
- Automatic retry with exponential backoff
- Timeout configuration
- Connection pool management
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Optional

import httpx
import structlog

from src.core.config import settings
from src.core.exceptions import ProviderError

logger = structlog.get_logger(__name__)


# =============================================================================
# Global Connection Pool Manager
# =============================================================================


class ConnectionPoolManager:
    """Manages shared HTTP connection pools with HTTP/2 support.

    Singleton pattern ensures efficient connection reuse across the application.
    """

    _instance: Optional["ConnectionPoolManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "ConnectionPoolManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._pools: dict[str, httpx.AsyncClient] = {}
        self._default_pool: Optional[httpx.AsyncClient] = None
        self._initialized = True

    @property
    def default_limits(self) -> httpx.Limits:
        """Get default connection limits from settings."""
        return httpx.Limits(
            max_connections=settings.http_client_pool_size,
            max_keepalive_connections=settings.http_client_pool_maxsize,
            keepalive_expiry=settings.keepalive_timeout,
        )

    @property
    def default_timeout(self) -> httpx.Timeout:
        """Get default timeout configuration."""
        return httpx.Timeout(
            connect=5.0,
            read=settings.http_client_timeout,
            write=10.0,
            pool=5.0,
        )

    async def get_pool(
        self,
        name: str = "default",
        base_url: Optional[str] = None,
        http2: bool = True,
        **kwargs,
    ) -> httpx.AsyncClient:
        """Get or create a named connection pool.

        Args:
            name: Pool identifier
            base_url: Optional base URL for all requests
            http2: Enable HTTP/2 support
            **kwargs: Additional httpx.AsyncClient arguments

        Returns:
            Configured AsyncClient with connection pooling
        """
        async with self._lock:
            if name not in self._pools or self._pools[name].is_closed:
                client_kwargs = {
                    "limits": self.default_limits,
                    "timeout": self.default_timeout,
                    "http2": http2,
                    "follow_redirects": True,
                    "headers": {
                        "Accept-Encoding": "gzip, deflate, br",
                        "User-Agent": f"AIPlat/{settings.version}",
                    },
                }
                if base_url:
                    client_kwargs["base_url"] = base_url
                client_kwargs.update(kwargs)

                self._pools[name] = httpx.AsyncClient(**client_kwargs)
                logger.debug("connection_pool_created", name=name, http2=http2)

            return self._pools[name]

    async def close_all(self) -> None:
        """Close all connection pools."""
        async with self._lock:
            for name, pool in self._pools.items():
                if not pool.is_closed:
                    await pool.aclose()
                    logger.debug("connection_pool_closed", name=name)
            self._pools.clear()

    @asynccontextmanager
    async def batch_context(self, concurrency: int = 10):
        """Context manager for batched HTTP operations with semaphore.

        Args:
            concurrency: Maximum concurrent requests

        Yields:
            Tuple of (client, semaphore)
        """
        pool = await self.get_pool()
        semaphore = asyncio.Semaphore(concurrency)
        yield pool, semaphore


# Global pool manager singleton
pool_manager = ConnectionPoolManager()


async def close_http_clients() -> None:
    """Close all HTTP clients on application shutdown."""
    await pool_manager.close_all()


class AsyncHTTPClient:
    """Async HTTP client with standardized error handling and retries.

    This class provides a reusable HTTP client that handles common patterns
    like authentication, retries, timeouts, and error handling.

    Now uses shared connection pools for better efficiency and HTTP/2 support.

    Example:
        client = AsyncHTTPClient(
            base_url="https://api.example.com",
            api_key="your-key",
            provider_name="example",
        )

        result = await client.post("/endpoint", json={"data": "value"})
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        provider_name: str = "http",
        default_timeout: float = 60.0,
        max_retries: int = 3,
        auth_header: str = "Authorization",
        auth_prefix: str = "Bearer",
        extra_headers: dict[str, str] | None = None,
        use_connection_pool: bool = True,
        http2: bool = True,
    ):
        """Initialize the HTTP client.

        Args:
            base_url: Base URL for API requests
            api_key: API key for authentication
            provider_name: Name of the provider (for error messages)
            default_timeout: Default timeout in seconds
            max_retries: Maximum number of retry attempts
            auth_header: Header name for authentication
            auth_prefix: Prefix for auth token (e.g., "Bearer", "Api-Key")
            extra_headers: Additional headers to include in all requests
            use_connection_pool: Use shared connection pool (recommended)
            http2: Enable HTTP/2 support
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.provider_name = provider_name
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.auth_header = auth_header
        self.auth_prefix = auth_prefix
        self.extra_headers = extra_headers or {}
        self.use_connection_pool = use_connection_pool
        self.http2 = http2
        self._client: Optional[httpx.AsyncClient] = None

    def _build_headers(
        self,
        content_type: str = "application/json",
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build headers for a request."""
        headers = {
            "Content-Type": content_type,
            **self.extra_headers,
        }

        if self.api_key:
            if self.auth_prefix:
                headers[self.auth_header] = f"{self.auth_prefix} {self.api_key}"
            else:
                headers[self.auth_header] = self.api_key

        if extra_headers:
            headers.update(extra_headers)

        return headers

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict[str, Any] | None = None,
        data: Any = None,
        files: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        retries: int | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with retries and error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint (will be appended to base_url)
            json: JSON body to send
            data: Raw data to send
            files: Files to upload
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout (uses default if not specified)
            retries: Number of retries (uses default if not specified)

        Returns:
            Parsed JSON response

        Raises:
            ProviderError: If the request fails after all retries
        """
        url = f"{self.base_url}{endpoint}"
        timeout_val = timeout or self.default_timeout
        max_retries = retries if retries is not None else self.max_retries

        # Determine content type based on what we're sending
        content_type = "application/json"
        if files:
            content_type = ""  # Let httpx set it for multipart

        request_headers = self._build_headers(
            content_type=content_type,
            extra_headers=headers,
        )

        # Remove Content-Type for file uploads
        if files and "Content-Type" in request_headers:
            del request_headers["Content-Type"]

        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                # Use shared connection pool or create temporary client
                if self.use_connection_pool:
                    client = await pool_manager.get_pool(
                        name=self.provider_name,
                        base_url=None,  # Use full URL
                        http2=self.http2,
                    )
                    response = await client.request(
                        method=method,
                        url=url,
                        json=json,
                        data=data,
                        files=files,
                        params=params,
                        headers=request_headers,
                        timeout=timeout_val,
                    )
                else:
                    async with httpx.AsyncClient(http2=self.http2) as client:
                        response = await client.request(
                            method=method,
                            url=url,
                            json=json,
                            data=data,
                            files=files,
                            params=params,
                            headers=request_headers,
                            timeout=timeout_val,
                        )

                    # Check for rate limiting
                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After", "5")
                        wait_time = float(retry_after) if retry_after.isdigit() else 5.0
                        if attempt < max_retries:
                            logger.warning(
                                "rate_limited",
                                provider=self.provider_name,
                                retry_after=wait_time,
                                attempt=attempt + 1,
                            )
                            await asyncio.sleep(wait_time)
                            continue

                    response.raise_for_status()

                    # Handle empty responses
                    if response.status_code == 204 or not response.content:
                        return {}

                    return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                error_detail = ""
                try:
                    error_body = e.response.json()
                    error_detail = error_body.get("error", {}).get("message", str(error_body))
                except Exception:
                    error_detail = e.response.text[:500] if e.response.text else str(e)

                logger.error(
                    "http_error",
                    provider=self.provider_name,
                    status_code=e.response.status_code,
                    error=error_detail,
                    url=url,
                )

                # Don't retry client errors (4xx) except rate limits
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    raise ProviderError(
                        message=f"{self.provider_name} API error: {error_detail}",
                        provider=self.provider_name,
                        details={
                            "status_code": e.response.status_code,
                            "error": error_detail,
                        },
                    ) from e

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "request_timeout",
                    provider=self.provider_name,
                    timeout=timeout_val,
                    attempt=attempt + 1,
                )

            except Exception as e:
                last_error = e
                logger.error(
                    "request_failed",
                    provider=self.provider_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )

            # Wait before retry
            if attempt < max_retries:
                wait_time = min(2 ** attempt, 30)  # Exponential backoff, max 30s
                await asyncio.sleep(wait_time)

        # All retries exhausted
        raise ProviderError(
            message=f"{self.provider_name} request failed after {max_retries + 1} attempts",
            provider=self.provider_name,
            details={"last_error": str(last_error)},
        )

    async def get(
        self,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a GET request."""
        return await self.request("GET", endpoint, **kwargs)

    async def post(
        self,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a POST request."""
        return await self.request("POST", endpoint, **kwargs)

    async def put(
        self,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a PUT request."""
        return await self.request("PUT", endpoint, **kwargs)

    async def patch(
        self,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a PATCH request."""
        return await self.request("PATCH", endpoint, **kwargs)

    async def delete(
        self,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make a DELETE request."""
        return await self.request("DELETE", endpoint, **kwargs)


async def download_file(
    url: str,
    timeout: float = 60.0,
) -> bytes:
    """Download a file from a URL.

    Args:
        url: URL to download from
        timeout: Request timeout

    Returns:
        File contents as bytes
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content


async def download_file_to_path(
    url: str,
    path: str,
    timeout: float = 120.0,
) -> None:
    """Download a file from a URL and save it to a path.

    Args:
        url: URL to download from
        path: Local path to save the file
        timeout: Request timeout
    """
    content = await download_file(url, timeout)
    with open(path, "wb") as f:
        f.write(content)
