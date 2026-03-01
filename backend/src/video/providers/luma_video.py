"""Luma AI Video Provider - Dream Machine."""

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


class LumaVideoProvider(VideoProvider):
    """Luma AI Dream Machine video generation provider.

    Features:
    - High-quality cinematic video generation
    - Fast generation times (~2 minutes for 5s)
    - Image-to-video support
    - Video extension
    - Excellent motion and physics
    - Camera motion control
    """

    provider_name = "luma"

    BASE_URL = "https://api.lumalabs.ai/dream-machine/v1"

    # Available models
    MODELS = {
        "ray-2": "ray-2",  # Latest model
        "ray-1": "ray-1",
    }

    # Pricing (credits per generation)
    PRICING = {
        "ray-2": 0.40,  # ~$0.40 per 5s video
        "ray-1": 0.30,
    }

    def __init__(
        self,
        api_key: str,
        default_model: str = "ray-2",
        timeout: float = 600.0,
        poll_interval: float = 5.0,
    ):
        """Initialize Luma AI provider.

        Args:
            api_key: Luma AI API key
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
                    AspectRatio.CINEMA: "21:9",
                }
                ratio = ratio_map.get(request.aspect_ratio, "16:9")

                # Build request
                body = {
                    "prompt": request.prompt,
                    "aspect_ratio": ratio,
                    "model": self.MODELS.get(model, model),
                }

                if request.extra_options.get("loop"):
                    body["loop"] = True

                # Create generation
                response = await client.post(
                    f"{self.BASE_URL}/generations",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()

                generation = response.json()
                generation_id = generation.get("id")

                # Poll for completion
                result = await self._wait_for_generation(client, generation_id)

                if result.get("state") == "failed":
                    raise Exception(result.get("failure_reason", "Generation failed"))

                # Get video info
                video = result.get("video", {})
                video_url = video.get("url")

                elapsed_ms = (time.time() - start_time) * 1000

                return VideoGenerationResponse(
                    video_url=video_url,
                    thumbnail_url=result.get("thumbnail", {}).get("url"),
                    duration_seconds=5.0,  # Luma generates 5s videos
                    model=model,
                    provider=self.provider_name,
                    cost_usd=self.PRICING.get(model, 0.40),
                    generation_time_ms=elapsed_ms,
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
                # Prepare keyframes
                if isinstance(request.image, str):
                    image_url = request.image
                else:
                    # Would need to upload image
                    raise NotImplementedError("Direct image upload not supported. Please provide a URL.")

                # Build request with keyframe
                body = {
                    "prompt": request.prompt or "",
                    "model": self.MODELS.get(model, model),
                    "keyframes": {
                        "frame0": {
                            "type": "image",
                            "url": image_url,
                        }
                    },
                }

                # Create generation
                response = await client.post(
                    f"{self.BASE_URL}/generations",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()

                generation = response.json()
                generation_id = generation.get("id")

                # Poll for completion
                result = await self._wait_for_generation(client, generation_id)

                if result.get("state") == "failed":
                    raise Exception(result.get("failure_reason", "Generation failed"))

                # Get video info
                video = result.get("video", {})
                video_url = video.get("url")

                elapsed_ms = (time.time() - start_time) * 1000

                return VideoGenerationResponse(
                    video_url=video_url,
                    thumbnail_url=result.get("thumbnail", {}).get("url"),
                    duration_seconds=5.0,
                    model=model,
                    provider=self.provider_name,
                    cost_usd=self.PRICING.get(model, 0.40),
                    generation_time_ms=elapsed_ms,
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

    async def extend_video(self, request: VideoExtendRequest) -> VideoGenerationResponse:
        """Extend an existing video."""
        start_time = time.time()
        model = request.model or self.default_model

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Get video URL
                if isinstance(request.video, str):
                    video_url = request.video
                else:
                    raise NotImplementedError("Direct video upload not supported. Please provide a URL.")

                # Build request with video keyframe
                keyframe_type = "frame0" if request.direction == "forward" else "frame1"

                body = {
                    "prompt": request.prompt or "",
                    "model": self.MODELS.get(model, model),
                    "keyframes": {
                        keyframe_type: {
                            "type": "generation",
                            "id": video_url,  # Reference to previous generation
                        }
                    },
                }

                # Create generation
                response = await client.post(
                    f"{self.BASE_URL}/generations",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()

                generation = response.json()
                generation_id = generation.get("id")

                # Poll for completion
                result = await self._wait_for_generation(client, generation_id)

                if result.get("state") == "failed":
                    raise Exception(result.get("failure_reason", "Extension failed"))

                # Get video info
                video = result.get("video", {})
                video_url = video.get("url")

                elapsed_ms = (time.time() - start_time) * 1000

                return VideoGenerationResponse(
                    video_url=video_url,
                    duration_seconds=5.0,
                    model=model,
                    provider=self.provider_name,
                    cost_usd=self.PRICING.get(model, 0.40),
                    generation_time_ms=elapsed_ms,
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

    async def _wait_for_generation(self, client: httpx.AsyncClient, generation_id: str) -> dict:
        """Wait for generation to complete."""
        start_time = time.time()

        while True:
            if time.time() - start_time > self.timeout:
                raise TimeoutError("Video generation timed out")

            response = await client.get(
                f"{self.BASE_URL}/generations/{generation_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()

            generation = response.json()
            state = generation.get("state")

            if state in ["completed", "failed"]:
                return generation

            await asyncio.sleep(self.poll_interval)

    async def get_status(self, generation_id: str) -> VideoGenerationResponse:
        """Get status of async generation."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/generations/{generation_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()

            generation = response.json()
            state = generation.get("state", "pending")

            # Map state
            status_map = {
                "queued": "pending",
                "dreaming": "processing",
                "completed": "completed",
                "failed": "failed",
            }

            video = generation.get("video", {})
            video_url = video.get("url")

            return VideoGenerationResponse(
                video_url=video_url,
                thumbnail_url=generation.get("thumbnail", {}).get("url"),
                model=generation.get("model", ""),
                provider=self.provider_name,
                status=status_map.get(state, "pending"),
                error=generation.get("failure_reason") if state == "failed" else None,
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return list(self.MODELS.keys())

    def estimate_cost(self, request: VideoGenerationRequest) -> float:
        """Estimate generation cost in USD."""
        model = request.model or self.default_model
        return self.PRICING.get(model, 0.40)
