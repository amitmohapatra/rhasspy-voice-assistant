"""Production-ready server configuration with HTTP/2 support.

Uses Hypercorn for HTTP/2 support with proper async configuration.
Falls back to uvicorn for development mode.

Features:
- HTTP/2 support (via Hypercorn with h2 protocol)
- Graceful shutdown
- Worker process management
- SSL/TLS configuration
- Access logging
- Prometheus metrics endpoint
"""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import TYPE_CHECKING

from src.core.config import settings

if TYPE_CHECKING:
    from hypercorn.config import Config


def get_hypercorn_config() -> "Config":
    """Create Hypercorn configuration for HTTP/2 server."""
    from hypercorn.config import Config

    config = Config()

    # Bind configuration
    config.bind = [f"{settings.server_host}:{settings.server_port}"]

    # Workers
    config.workers = settings.server_workers

    # Timeouts
    config.keep_alive_timeout = settings.keepalive_timeout
    config.graceful_timeout = 30

    # HTTP/2 settings
    if settings.http2_enabled:
        config.h2_max_concurrent_streams = 128
        config.h2_max_header_list_size = 16384
        config.h2_max_inbound_frame_size = 16384

    # SSL/TLS for HTTP/2 (required for h2 with browsers)
    if settings.ssl_certfile and settings.ssl_keyfile:
        config.certfile = settings.ssl_certfile
        config.keyfile = settings.ssl_keyfile
        # ALPN protocols for HTTP/2
        config.alpn_protocols = ["h2", "http/1.1"]

    # Access log
    config.accesslog = "-" if settings.access_log else None
    config.errorlog = "-"

    # Logging
    config.loglevel = "DEBUG" if settings.debug else "INFO"

    # Application
    config.application_path = "src.main:app"

    return config


async def run_hypercorn_server() -> None:
    """Run the Hypercorn server with HTTP/2 support."""
    from hypercorn.asyncio import serve

    config = get_hypercorn_config()

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig: int, frame) -> None:
        print(f"\nReceived signal {sig}, initiating graceful shutdown...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"Starting Hypercorn server on {settings.server_host}:{settings.server_port}")
    print(f"HTTP/2 enabled: {settings.http2_enabled}")
    print(f"Workers: {settings.server_workers}")

    if settings.ssl_certfile:
        print(f"SSL enabled with cert: {settings.ssl_certfile}")
    else:
        print("SSL disabled (HTTP/2 will work with h2c for non-browser clients)")

    # Import app here to avoid circular imports
    from src.main import app

    await serve(
        app,
        config,
        shutdown_trigger=shutdown_event.wait,
    )


def run_uvicorn_server() -> None:
    """Run uvicorn server (development mode, no HTTP/2)."""
    import uvicorn

    print("Starting uvicorn server (development mode)")
    print(f"HTTP/2: Not available with uvicorn (use Hypercorn for HTTP/2)")

    uvicorn.run(
        "src.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.server_workers,
        log_level="debug" if settings.debug else "info",
        access_log=settings.access_log,
    )


def main() -> None:
    """Main entry point for server.

    Uses Hypercorn in production for HTTP/2, uvicorn in development.
    """
    # Check if HTTP/2 is requested
    if settings.http2_enabled and not settings.is_development:
        try:
            import hypercorn  # noqa: F401

            print("Hypercorn available, starting with HTTP/2 support")
            asyncio.run(run_hypercorn_server())
        except ImportError:
            print("Warning: Hypercorn not installed, falling back to uvicorn")
            print("Install with: pip install hypercorn[h2]")
            run_uvicorn_server()
    else:
        run_uvicorn_server()


if __name__ == "__main__":
    main()
