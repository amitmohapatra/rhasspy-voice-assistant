"""Deployment Agent - Runs in Customer's Cloud.

This agent runs alongside the main application in the customer's
cloud/VPC and handles:
1. License validation on startup
2. Periodic heartbeats to control plane
3. Usage metrics collection and reporting
4. Receiving configuration updates

The agent ensures the deployment is authorized while keeping
all customer data within their environment.

IMPORTANT: This file is deployed to customer environments.
No sensitive data is sent to the control plane - only:
- License validation requests
- Aggregated usage metrics (counts, not content)
- Health/status information
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
import json

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LicenseEntitlements:
    """What the current license allows."""
    max_users: Optional[int] = None
    max_assistants: Optional[int] = None
    max_knowledge_bases: Optional[int] = None
    max_monthly_voice_minutes: Optional[int] = None
    max_monthly_llm_tokens: Optional[int] = None
    max_storage_gb: Optional[int] = None
    features_enabled: list[str] = field(default_factory=list)

    def has_feature(self, feature: str) -> bool:
        """Check if a feature is enabled."""
        return "*" in self.features_enabled or feature in self.features_enabled


@dataclass
class UsageMetrics:
    """Collected usage metrics for reporting."""
    period_start: datetime
    period_end: datetime

    # Users
    active_users: int = 0
    total_users: int = 0

    # Resources
    assistant_count: int = 0
    knowledge_base_count: int = 0
    conversation_count: int = 0

    # Voice
    stt_minutes: float = 0.0
    tts_minutes: float = 0.0

    # LLM
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_requests: int = 0

    # Storage
    storage_bytes: int = 0
    document_count: int = 0

    # API
    api_requests: int = 0
    websocket_connections: int = 0
    websocket_minutes: float = 0.0

    # Performance
    response_times_ms: list[float] = field(default_factory=list)
    error_count: int = 0

    # Provider breakdown
    usage_by_provider: dict = field(default_factory=dict)

    def add_voice_usage(self, stt_minutes: float = 0, tts_minutes: float = 0):
        """Record voice usage."""
        self.stt_minutes += stt_minutes
        self.tts_minutes += tts_minutes

    def add_llm_usage(self, input_tokens: int, output_tokens: int, provider: str = "openai"):
        """Record LLM usage."""
        self.llm_input_tokens += input_tokens
        self.llm_output_tokens += output_tokens
        self.llm_requests += 1

        if provider not in self.usage_by_provider:
            self.usage_by_provider[provider] = {"tokens": 0, "requests": 0}
        self.usage_by_provider[provider]["tokens"] += input_tokens + output_tokens
        self.usage_by_provider[provider]["requests"] += 1

    def add_api_request(self, response_time_ms: float, is_error: bool = False):
        """Record an API request."""
        self.api_requests += 1
        self.response_times_ms.append(response_time_ms)
        if is_error:
            self.error_count += 1

    @property
    def avg_response_time_ms(self) -> Optional[float]:
        if not self.response_times_ms:
            return None
        return sum(self.response_times_ms) / len(self.response_times_ms)

    def to_report(self) -> dict:
        """Convert to usage report format."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "report_type": "hourly",
            "active_users": self.active_users,
            "total_users": self.total_users,
            "assistant_count": self.assistant_count,
            "knowledge_base_count": self.knowledge_base_count,
            "conversation_count": self.conversation_count,
            "stt_minutes": self.stt_minutes,
            "tts_minutes": self.tts_minutes,
            "llm_input_tokens": self.llm_input_tokens,
            "llm_output_tokens": self.llm_output_tokens,
            "llm_requests": self.llm_requests,
            "storage_bytes": self.storage_bytes,
            "document_count": self.document_count,
            "api_requests": self.api_requests,
            "websocket_connections": self.websocket_connections,
            "websocket_minutes": self.websocket_minutes,
            "avg_response_time_ms": self.avg_response_time_ms,
            "error_count": self.error_count,
            "usage_by_provider": self.usage_by_provider,
        }


class DeploymentAgent:
    """Agent that runs in customer deployments.

    Handles license validation, usage reporting, and health monitoring
    while keeping all customer data in their environment.
    """

    def __init__(
        self,
        control_plane_url: str,
        license_key: str,
        license_secret: str,
        app_version: str = "1.0.0",
        agent_version: str = "1.0.0",
        heartbeat_interval: int = 60,
        usage_report_interval: int = 3600,  # 1 hour
    ):
        self.control_plane_url = control_plane_url.rstrip("/")
        self.license_key = license_key
        self.license_secret = license_secret
        self.app_version = app_version
        self.agent_version = agent_version
        self.heartbeat_interval = heartbeat_interval
        self.usage_report_interval = usage_report_interval

        # State
        self.is_validated = False
        self.entitlements: Optional[LicenseEntitlements] = None
        self.deployment_id: Optional[str] = None
        self.deployment_name: Optional[str] = None
        self.config: dict = {}
        self.feature_flags: dict = {}

        # Metrics collection
        self._current_metrics: Optional[UsageMetrics] = None
        self._metrics_lock = asyncio.Lock()

        # Callbacks for usage collection
        self._usage_collectors: list[Callable[[], dict]] = []

        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None

        # Background tasks
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._usage_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> bool:
        """Start the agent - validate license and begin monitoring.

        Returns True if license is valid and agent started successfully.
        """
        logger.info("Starting deployment agent...")

        self._client = httpx.AsyncClient(timeout=30.0)

        # Validate license
        if not await self._validate_license():
            logger.error("License validation failed - agent not starting")
            return False

        self._running = True

        # Start metrics collection period
        await self._start_new_metrics_period()

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._usage_task = asyncio.create_task(self._usage_report_loop())

        logger.info(
            f"Deployment agent started - "
            f"deployment={self.deployment_name}"
        )

        return True

    async def stop(self):
        """Stop the agent gracefully."""
        logger.info("Stopping deployment agent...")
        self._running = False

        # Cancel background tasks
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._usage_task:
            self._usage_task.cancel()
            try:
                await self._usage_task
            except asyncio.CancelledError:
                pass

        # Send final usage report
        await self._send_usage_report()

        if self._client:
            await self._client.aclose()

        logger.info("Deployment agent stopped")

    async def _validate_license(self) -> bool:
        """Validate license with control plane."""
        try:
            response = await self._client.post(
                f"{self.control_plane_url}/api/v1/licensing/validate",
                json={
                    "license_key": self.license_key,
                    "license_secret": self.license_secret,
                    "deployment_info": {
                        "app_version": self.app_version,
                        "agent_version": self.agent_version,
                        "api_endpoint": os.getenv("API_ENDPOINT"),
                    },
                },
            )

            if response.status_code == 200:
                data = response.json()
                self.is_validated = True
                self.deployment_id = data["deployment_id"]
                self.deployment_name = data["deployment_name"]
                self.config = data.get("config", {})
                self.feature_flags = data.get("feature_flags", {})

                # Parse entitlements
                ent = data.get("entitlements", {})
                self.entitlements = LicenseEntitlements(
                    max_users=ent.get("max_users"),
                    max_assistants=ent.get("max_assistants"),
                    max_knowledge_bases=ent.get("max_knowledge_bases"),
                    max_monthly_voice_minutes=ent.get("max_monthly_voice_minutes"),
                    max_monthly_llm_tokens=ent.get("max_monthly_llm_tokens"),
                    max_storage_gb=ent.get("max_storage_gb"),
                    features_enabled=ent.get("features_enabled", []),
                )

                logger.info(f"License validated: {data.get('message')}")
                return True

            elif response.status_code == 401:
                logger.error("Invalid license credentials")
                return False

            elif response.status_code == 403:
                logger.error("License is not valid (expired or suspended)")
                return False

            else:
                logger.error(f"License validation failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to control plane: {e}")
            # In production, you might want to allow a grace period
            # for network issues with cached validation
            return False

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to control plane."""
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def _send_heartbeat(self):
        """Send a single heartbeat."""
        try:
            # Collect current metrics summary
            metrics = {}
            async with self._metrics_lock:
                if self._current_metrics:
                    metrics = {
                        "active_users": self._current_metrics.active_users,
                        "api_requests": self._current_metrics.api_requests,
                    }

            response = await self._client.post(
                f"{self.control_plane_url}/api/v1/licensing/heartbeat",
                json={
                    "license_key": self.license_key,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "healthy",
                    "app_version": self.app_version,
                    "agent_version": self.agent_version,
                    "instance_count": int(os.getenv("INSTANCE_COUNT", "1")),
                    "active_users": metrics.get("active_users", 0),
                    "metrics": metrics,
                },
            )

            if response.status_code == 200:
                data = response.json()
                # Update heartbeat interval if changed
                if "next_heartbeat_seconds" in data:
                    self.heartbeat_interval = data["next_heartbeat_seconds"]

                # Process any commands from control plane
                for command in data.get("commands", []):
                    await self._handle_command(command)

            else:
                logger.warning(f"Heartbeat rejected: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")

    async def _handle_command(self, command: dict):
        """Handle a command from the control plane."""
        cmd_type = command.get("type")

        if cmd_type == "update_config":
            self.config.update(command.get("config", {}))
            logger.info("Configuration updated from control plane")

        elif cmd_type == "update_feature_flags":
            self.feature_flags.update(command.get("flags", {}))
            logger.info("Feature flags updated from control plane")

        elif cmd_type == "force_usage_report":
            await self._send_usage_report()

        elif cmd_type == "revalidate":
            await self._validate_license()

        else:
            logger.warning(f"Unknown command type: {cmd_type}")

    async def _usage_report_loop(self):
        """Send periodic usage reports."""
        while self._running:
            try:
                await asyncio.sleep(self.usage_report_interval)
                await self._send_usage_report()
                await self._start_new_metrics_period()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Usage report error: {e}")

    async def _start_new_metrics_period(self):
        """Start a new metrics collection period."""
        async with self._metrics_lock:
            now = datetime.utcnow()
            self._current_metrics = UsageMetrics(
                period_start=now,
                period_end=now + timedelta(seconds=self.usage_report_interval),
            )

    async def _send_usage_report(self):
        """Send collected usage metrics to control plane."""
        async with self._metrics_lock:
            if not self._current_metrics:
                return

            metrics = self._current_metrics

            # Collect additional metrics from registered collectors
            for collector in self._usage_collectors:
                try:
                    additional = collector()
                    metrics.total_users = additional.get("total_users", metrics.total_users)
                    metrics.active_users = additional.get("active_users", metrics.active_users)
                    metrics.assistant_count = additional.get("assistant_count", metrics.assistant_count)
                    metrics.knowledge_base_count = additional.get("knowledge_base_count", metrics.knowledge_base_count)
                    metrics.storage_bytes = additional.get("storage_bytes", metrics.storage_bytes)
                    metrics.document_count = additional.get("document_count", metrics.document_count)
                except Exception as e:
                    logger.error(f"Usage collector error: {e}")

            # Update end time
            metrics.period_end = datetime.utcnow()

        try:
            report = metrics.to_report()
            report["license_key"] = self.license_key

            # Add checksum for integrity
            report_json = json.dumps(report, sort_keys=True, default=str)
            report["checksum"] = hashlib.sha256(report_json.encode()).hexdigest()

            response = await self._client.post(
                f"{self.control_plane_url}/api/v1/licensing/usage",
                json=report,
            )

            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"Usage report accepted - "
                    f"cost: ${data.get('calculated_cost_cents', 0) / 100:.2f}, "
                    f"overage: ${data.get('overage_cost_cents', 0) / 100:.2f}"
                )

                # Log any warnings
                for warning in data.get("warnings", []):
                    logger.warning(f"Usage warning: {warning}")

            else:
                logger.warning(f"Usage report rejected: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to send usage report: {e}")

    # =========================================================================
    # Public API for Application Integration
    # =========================================================================

    def check_feature(self, feature: str) -> bool:
        """Check if a feature is enabled in the license."""
        if not self.entitlements:
            return False
        return self.entitlements.has_feature(feature)

    def check_limit(self, limit_type: str, current_value: int) -> bool:
        """Check if a limit is exceeded.

        Returns True if within limits, False if exceeded.
        """
        if not self.entitlements:
            return False

        limits = {
            "users": self.entitlements.max_users,
            "assistants": self.entitlements.max_assistants,
            "knowledge_bases": self.entitlements.max_knowledge_bases,
        }

        max_value = limits.get(limit_type)
        if max_value is None:  # Unlimited
            return True

        return current_value < max_value

    async def record_voice_usage(self, stt_minutes: float = 0, tts_minutes: float = 0):
        """Record voice usage for this period."""
        async with self._metrics_lock:
            if self._current_metrics:
                self._current_metrics.add_voice_usage(stt_minutes, tts_minutes)

    async def record_llm_usage(
        self, input_tokens: int, output_tokens: int, provider: str = "openai"
    ):
        """Record LLM usage for this period."""
        async with self._metrics_lock:
            if self._current_metrics:
                self._current_metrics.add_llm_usage(input_tokens, output_tokens, provider)

    async def record_api_request(self, response_time_ms: float, is_error: bool = False):
        """Record an API request for this period."""
        async with self._metrics_lock:
            if self._current_metrics:
                self._current_metrics.add_api_request(response_time_ms, is_error)

    def register_usage_collector(self, collector: Callable[[], dict]):
        """Register a callback to collect additional usage metrics.

        The callback should return a dict with any of:
        - total_users, active_users
        - assistant_count, knowledge_base_count
        - storage_bytes, document_count
        """
        self._usage_collectors.append(collector)

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value pushed from control plane."""
        return self.config.get(key, default)

    def get_feature_flag(self, flag: str, default: bool = False) -> bool:
        """Get a feature flag value."""
        return self.feature_flags.get(flag, default)


# Global agent instance
_agent: Optional[DeploymentAgent] = None


def get_agent() -> Optional[DeploymentAgent]:
    """Get the global agent instance."""
    return _agent


async def initialize_agent(
    control_plane_url: str = None,
    license_key: str = None,
    license_secret: str = None,
) -> DeploymentAgent:
    """Initialize and start the global deployment agent."""
    global _agent

    control_plane_url = control_plane_url or os.getenv(
        "CONTROL_PLANE_URL", "https://api.rhasspy.io"
    )
    license_key = license_key or os.getenv("LICENSE_KEY")
    license_secret = license_secret or os.getenv("LICENSE_SECRET")

    if not license_key or not license_secret:
        raise ValueError(
            "LICENSE_KEY and LICENSE_SECRET environment variables are required"
        )

    _agent = DeploymentAgent(
        control_plane_url=control_plane_url,
        license_key=license_key,
        license_secret=license_secret,
        app_version=os.getenv("APP_VERSION", "1.0.0"),
        agent_version="1.0.0",
    )

    success = await _agent.start()
    if not success:
        raise RuntimeError("Failed to start deployment agent - license invalid")

    return _agent


async def shutdown_agent():
    """Shutdown the global deployment agent."""
    global _agent
    if _agent:
        await _agent.stop()
        _agent = None


# FastAPI middleware for automatic request tracking
class DeploymentAgentMiddleware:
    """FastAPI middleware to automatically track API requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = datetime.utcnow()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Calculate response time
                response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                is_error = message.get("status", 200) >= 400

                # Record with agent
                agent = get_agent()
                if agent:
                    await agent.record_api_request(response_time, is_error)

            await send(message)

        await self.app(scope, receive, send_wrapper)
