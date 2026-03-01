"""Runway Video Provider - Gen-3 Alpha and Gen-2."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx

from src.video.base import (
    VideoProvider,
    VideoGenerationRequest,
    ImageToVideoRequest,
    VideoExtendRequest,
    VideoGenerationResponse,
    VideoFormat,
    AspectRatio,
)


class RunwayVideoProvider(VideoProvider):
    """Runway video generation provider.

    Supports:
    - Gen-3 Alpha: Latest model with best quality
    - Gen-3 Alpha Turbo: Faster generation
    - Gen-2: Previous generation model

    Features:
    - Text-to-video generation
    - Image-to-video animation
    - Video extension
    - Motion brush control
    - Camera motion control
    """

    provider_name = "runway"

    BASE_URL = "https://api.runwayml.com/v1"

    # Available models
    MODELS = {
        "gen3a_turbo": "gen3a_turbo",
        "gen3a": "gen3a",
        "gen2": "gen2",
    }

    # Pricing per second (approximate)
    PRICING = {
        "gen3a_turbo": 0.05,  # $0.05/second
        "gen3a": 0.10,        # $0.10/second
        "gen2": 0.05,         # $0.05/second
    }

    def __init__(
        self,
        api_key: str,
        default_model: str = "gen3a_turbo",
        timeout: float = 600.0,
        poll_interval: float = 5.0,
    ):
        """Initialize Runway provider.

        Args:
            api_key: Runway API key
            default_model: Default model to use
            timeout: Max wait time for generation
            poll_interval: Time between status polls
        """
        self.api_key = api_key
        self.default_model = default_model
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        """Generate video from text prompt."""
        start_time = time.time()
        model = request.model or self.default_model

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Map aspect ratio
                ratio_map = {
                    AspectRatio.LANDSCAPE: "16:9",
                    AspectRatio.PORTRAIT: "9:16",
                    AspectRatio.SQUARE: "1:1",
                }
                ratio = ratio_map.get(request.aspect_ratio, "16:9")

                # Build request
                body = {
                    "model": self.MODELS.get(model, model),
                    "promptText": request.prompt,
                    "ratio": ratio,
                    "duration": int(request.duration_seconds),
                }

                if request.seed is not None:
                    body["seed"] = request.seed

                # Add style options
                if request.extra_options:
                    body.update(request.extra_options)

                # Create task
                response = await client.post(
                    f"{self.BASE_URL}/image_to_video",  # Runway uses same endpoint
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "X-Runway-Version": "2024-11-06",
                    },
                    json=body,
                )
                response.raise_for_status()

                task = response.json()
                task_id = task.get("id")

                # Poll for completion
                result = await self._wait_for_task(client, task_id)

                if result.get("status") == "FAILED":
                    raise Exception(result.get("failure", "Generation failed"))

                # Get output
                output = result.get("output", [])
                video_url = output[0] if output else None

                elapsed_ms = (time.time() - start_time) * 1000

                return VideoGenerationResponse(
                    video_url=video_url,
                    duration_seconds=request.duration_seconds,
                    model=model,
                    provider=self.provider_name,
                    cost_usd=self.estimate_cost(request),
                    generation_time_ms=elapsed_ms,
                    seed=result.get("seed"),
                )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return VideoGenerationResponse(
                model=model,
                provider=self.provider_name,
                generation_time_ms=elapsed_ms,
                status="failed",
                error=str(e),
            )

    async def image_to_video(self, request: ImageToVideoRequest) -> VideoGenerationResponse:
        """Generate video from image."""
        start_time = time.time()
        model = request.model or self.default_model

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Prepare image
                if isinstance(request.image, str):
                    image_url = request.image
                else:
                    # Upload image first
                    image_url = await self._upload_image(client, request.image)

                # Build request
                body = {
                    "model": self.MODELS.get(model, model),
                    "promptImage": image_url,
                    "duration": int(request.duration_seconds),
                }

                if request.prompt:
                    body["promptText"] = request.prompt

                if request.seed is not None:
                    body["seed"] = request.seed

                # Create task
                response = await client.post(
                    f"{self.BASE_URL}/image_to_video",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "X-Runway-Version": "2024-11-06",
                    },
                    json=body,
                )
                response.raise_for_status()

                task = response.json()
                task_id = task.get("id")

                # Poll for completion
                result = await self._wait_for_task(client, task_id)

                if result.get("status") == "FAILED":
                    raise Exception(result.get("failure", "Generation failed"))

                # Get output
                output = result.get("output", [])
                video_url = output[0] if output else None

                elapsed_ms = (time.time() - start_time) * 1000

                return VideoGenerationResponse(
                    video_url=video_url,
                    duration_seconds=request.duration_seconds,
                    model=model,
                    provider=self.provider_name,
                    generation_time_ms=elapsed_ms,
                    seed=result.get("seed"),
                )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return VideoGenerationResponse(
                model=model,
                provider=self.provider_name,
                generation_time_ms=elapsed_ms,
                status="failed",
                error=str(e),
            )

    async def _wait_for_task(self, client: httpx.AsyncClient, task_id: str) -> dict:
        """Wait for a task to complete."""
        start_time = time.time()

        while True:
            if time.time() - start_time > self.timeout:
                raise TimeoutError("Video generation timed out")

            response = await client.get(
                f"{self.BASE_URL}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()

            task = response.json()
            status = task.get("status")

            if status in ["SUCCEEDED", "FAILED"]:
                return task

            await asyncio.sleep(self.poll_interval)

    async def _upload_image(self, client: httpx.AsyncClient, image_data: bytes) -> str:
        """Upload an image and return the URL."""
        # This would use Runway's asset upload API
        # For now, raise not implemented
        raise NotImplementedError("Direct image upload not implemented. Please provide a URL.")

    async def get_status(self, generation_id: str) -> VideoGenerationResponse:
        """Get status of async generation."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/tasks/{generation_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()

            task = response.json()
            status = task.get("status", "PENDING")

            # Map status
            status_map = {
                "PENDING": "pending",
                "RUNNING": "processing",
                "SUCCEEDED": "completed",
                "FAILED": "failed",
            }

            output = task.get("output", [])
            video_url = output[0] if output else None

            return VideoGenerationResponse(
                video_url=video_url,
                model=task.get("model", ""),
                provider=self.provider_name,
                status=status_map.get(status, "pending"),
                progress=task.get("progress", 0),
                error=task.get("failure") if status == "FAILED" else None,
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return list(self.MODELS.keys())

    def estimate_cost(self, request: VideoGenerationRequest) -> float:
        """Estimate generation cost in USD."""
        model = request.model or self.default_model
        price_per_second = self.PRICING.get(model, 0.05)
        return request.duration_seconds * price_per_second
