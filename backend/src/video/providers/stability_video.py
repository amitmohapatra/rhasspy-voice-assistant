"""Stability AI Video Provider - Stable Video Diffusion."""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Optional

import httpx

from src.video.base import (
    VideoProvider,
    VideoGenerationRequest,
    ImageToVideoRequest,
    VideoGenerationResponse,
    VideoFormat,
)


class StabilityVideoProvider(VideoProvider):
    """Stability AI video generation provider.

    Supports:
    - Stable Video Diffusion (SVD) 1.1
    - Stable Video Diffusion XT (longer videos)

    Features:
    - Image-to-video generation
    - Motion control
    - High quality output
    - Deterministic generation with seeds
    """

    provider_name = "stability"

    BASE_URL = "https://api.stability.ai"

    # Available models
    MODELS = {
        "svd": "svd",
        "svd-xt": "svd-xt",
        "stable-video": "svd",
    }

    # Pricing (credits per generation)
    PRICING = {
        "svd": 0.20,      # ~$0.20 per video
        "svd-xt": 0.30,   # ~$0.30 per longer video
    }

    def __init__(
        self,
        api_key: str,
        default_model: str = "svd",
        timeout: float = 300.0,
        poll_interval: float = 5.0,
    ):
        """Initialize Stability AI video provider.

        Args:
            api_key: Stability AI API key
            default_model: Default model to use
            timeout: Max wait time for generation
            poll_interval: Time between status polls
        """
        self.api_key = api_key
        self.default_model = default_model
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        """Generate video from text prompt.

        Note: Stability SVD requires an input image. This method will
        first generate an image from the prompt, then animate it.
        """
        start_time = time.time()
        model = request.model or self.default_model

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Step 1: Generate an image from the prompt using Stable Diffusion
                image_response = await client.post(
                    f"{self.BASE_URL}/v2beta/stable-image/generate/core",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "image/*",
                    },
                    files={"none": ""},
                    data={
                        "prompt": request.prompt,
                        "output_format": "png",
                    },
                )
                image_response.raise_for_status()
                image_bytes = image_response.content

                # Step 2: Animate the image
                return await self._image_to_video_internal(
                    client, image_bytes, request, model, start_time
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
            # Get image bytes
            if isinstance(request.image, str):
                async with httpx.AsyncClient() as client:
                    resp = await client.get(request.image)
                    image_bytes = resp.content
            else:
                image_bytes = request.image

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                return await self._image_to_video_internal(
                    client, image_bytes, request, model, start_time
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

    async def _image_to_video_internal(
        self,
        client: httpx.AsyncClient,
        image_bytes: bytes,
        request: ImageToVideoRequest | VideoGenerationRequest,
        model: str,
        start_time: float,
    ) -> VideoGenerationResponse:
        """Internal image-to-video generation."""
        # Build request data
        data = {}

        # Motion parameters
        if hasattr(request, "motion_strength"):
            # motion_bucket_id: 1-255, higher = more motion
            data["motion_bucket_id"] = int(request.motion_strength * 127) + 1

        if hasattr(request, "seed") and request.seed is not None:
            data["seed"] = request.seed

        if hasattr(request, "guidance_scale"):
            data["cfg_scale"] = request.guidance_scale

        # Create generation
        response = await client.post(
            f"{self.BASE_URL}/v2beta/image-to-video",
            headers={
                "Authorization": f"Bearer {self.api_key}",
            },
            files={
                "image": ("image.png", image_bytes, "image/png"),
            },
            data=data,
        )
        response.raise_for_status()

        result = response.json()
        generation_id = result.get("id")

        # Poll for completion
        final_result = await self._wait_for_generation(client, generation_id)

        if final_result.get("finish_reason") == "ERROR":
            raise Exception(final_result.get("errors", ["Generation failed"]))

        # Get video
        video_bytes = final_result.get("video")
        video_b64 = base64.b64encode(video_bytes).decode() if video_bytes else None

        elapsed_ms = (time.time() - start_time) * 1000

        return VideoGenerationResponse(
            video_data=video_bytes,
            duration_seconds=4.0,  # SVD generates ~4 second videos
            fps=14 if model == "svd" else 25,  # SVD: 14fps, SVD-XT: 25fps
            model=model,
            provider=self.provider_name,
            cost_usd=self.PRICING.get(model, 0.20),
            generation_time_ms=elapsed_ms,
            seed=final_result.get("seed"),
        )

    async def _wait_for_generation(self, client: httpx.AsyncClient, generation_id: str) -> dict:
        """Wait for generation to complete."""
        start_time = time.time()

        while True:
            if time.time() - start_time > self.timeout:
                raise TimeoutError("Video generation timed out")

            response = await client.get(
                f"{self.BASE_URL}/v2beta/image-to-video/result/{generation_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "video/*",
                },
            )

            if response.status_code == 202:
                # Still processing
                await asyncio.sleep(self.poll_interval)
                continue

            if response.status_code == 200:
                # Check content type
                content_type = response.headers.get("content-type", "")

                if "video" in content_type:
                    return {
                        "video": response.content,
                        "finish_reason": "SUCCESS",
                    }
                else:
                    return response.json()

            response.raise_for_status()

    async def get_status(self, generation_id: str) -> VideoGenerationResponse:
        """Get status of async generation."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/v2beta/image-to-video/result/{generation_id}",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
            )

            if response.status_code == 202:
                return VideoGenerationResponse(
                    provider=self.provider_name,
                    status="processing",
                )

            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")

                if "video" in content_type:
                    return VideoGenerationResponse(
                        video_data=response.content,
                        provider=self.provider_name,
                        status="completed",
                    )
                else:
                    result = response.json()
                    return VideoGenerationResponse(
                        provider=self.provider_name,
                        status="completed" if result.get("finish_reason") == "SUCCESS" else "failed",
                        error=str(result.get("errors")) if result.get("finish_reason") == "ERROR" else None,
                    )

            return VideoGenerationResponse(
                provider=self.provider_name,
                status="failed",
                error=f"Unknown status code: {response.status_code}",
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return list(self.MODELS.keys())

    def estimate_cost(self, request: VideoGenerationRequest) -> float:
        """Estimate generation cost in USD."""
        model = request.model or self.default_model
        return self.PRICING.get(model, 0.20)
