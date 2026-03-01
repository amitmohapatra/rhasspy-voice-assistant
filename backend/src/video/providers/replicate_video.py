"""Replicate Video Provider - Run various video models."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import httpx

from src.video.base import (
    VideoProvider,
    VideoGenerationRequest,
    ImageToVideoRequest,
    VideoGenerationResponse,
    VideoFormat,
    AspectRatio,
)


class ReplicateVideoProvider(VideoProvider):
    """Replicate video generation provider.

    Supports running various video models:
    - Stable Video Diffusion
    - AnimateDiff
    - Zeroscope
    - FILM (frame interpolation)
    - And many more...

    Features:
    - Access to many open models
    - Pay per prediction
    - Custom model support
    """

    provider_name = "replicate"

    BASE_URL = "https://api.replicate.com/v1"

    # Popular video model versions
    MODELS = {
        # Stable Video Diffusion
        "svd": "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",
        "svd-xt": "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",

        # AnimateDiff
        "animatediff": "lucataco/animate-diff:beecf59c4aee8d81bf04f0381033dfa10dc16e845b4ae00d281e2fa377e48c9f",

        # Zeroscope
        "zeroscope": "anotherjesse/zeroscope-v2-xl:9f747673945c62801b13b84701c783929c0ee784e4748ec062204894dda1a351",

        # CogVideoX
        "cogvideox": "fofr/cogvideox-5b:75422fd41d64064020c4704fb90859e0bb12938abe9e6a11076ad0c2b6c50cb6",

        # Mochi 1
        "mochi": "genmoai/mochi-1-preview:1944af04d098efdb200bd098ae60fc1d3df1da22de3830abe8c36ccd8f498709",
    }

    def __init__(
        self,
        api_token: str,
        default_model: str = "svd",
        timeout: float = 600.0,
        poll_interval: float = 5.0,
    ):
        """Initialize Replicate provider.

        Args:
            api_token: Replicate API token
            default_model: Default model to use
            timeout: Max wait time for prediction
            poll_interval: Time between status polls
        """
        self.api_token = api_token
        self.default_model = default_model
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        """Generate video from text prompt."""
        start_time = time.time()
        model = request.model or self.default_model

        try:
            model_version = self.MODELS.get(model, model)

            # Build input based on model
            model_input = self._build_input(request, model)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Create prediction
                response = await client.post(
                    f"{self.BASE_URL}/predictions",
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "version": model_version.split(":")[-1] if ":" in model_version else model_version,
                        "input": model_input,
                    },
                )
                response.raise_for_status()

                prediction = response.json()
                prediction_id = prediction["id"]

                # Poll for completion
                result = await self._wait_for_prediction(client, prediction_id)

                if result["status"] == "failed":
                    raise Exception(result.get("error", "Prediction failed"))

                # Get output
                output = result.get("output")
                if isinstance(output, list):
                    video_url = output[0] if output else None
                else:
                    video_url = output

                elapsed_ms = (time.time() - start_time) * 1000

                return VideoGenerationResponse(
                    video_url=video_url,
                    duration_seconds=request.duration_seconds,
                    model=model,
                    provider=self.provider_name,
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
        """Generate video from image using SVD."""
        start_time = time.time()
        model = request.model or "svd"

        try:
            model_version = self.MODELS.get(model, self.MODELS["svd"])

            # Prepare image URL
            if isinstance(request.image, str):
                image_url = request.image
            else:
                raise NotImplementedError("Direct image upload not supported. Please provide a URL.")

            # Build input for SVD
            model_input = {
                "input_image": image_url,
                "motion_bucket_id": int(request.motion_strength * 255),  # 0-255
                "fps": request.fps,
            }

            if request.seed is not None:
                model_input["seed"] = request.seed

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Create prediction
                response = await client.post(
                    f"{self.BASE_URL}/predictions",
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "version": model_version.split(":")[-1],
                        "input": model_input,
                    },
                )
                response.raise_for_status()

                prediction = response.json()
                prediction_id = prediction["id"]

                # Poll for completion
                result = await self._wait_for_prediction(client, prediction_id)

                if result["status"] == "failed":
                    raise Exception(result.get("error", "Prediction failed"))

                # Get output
                output = result.get("output")
                if isinstance(output, list):
                    video_url = output[0] if output else None
                else:
                    video_url = output

                elapsed_ms = (time.time() - start_time) * 1000

                return VideoGenerationResponse(
                    video_url=video_url,
                    duration_seconds=request.duration_seconds,
                    fps=request.fps,
                    model=model,
                    provider=self.provider_name,
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

    def _build_input(self, request: VideoGenerationRequest, model: str) -> dict:
        """Build model input based on model type."""
        model_input = {}

        # Common parameters
        if request.prompt:
            model_input["prompt"] = request.prompt

        if request.negative_prompt:
            model_input["negative_prompt"] = request.negative_prompt

        if request.seed is not None:
            model_input["seed"] = request.seed

        if request.guidance_scale:
            model_input["guidance_scale"] = request.guidance_scale

        if request.num_inference_steps:
            model_input["num_inference_steps"] = request.num_inference_steps

        # Model-specific parameters
        if model in ["cogvideox", "mochi"]:
            model_input["num_frames"] = int(request.duration_seconds * request.fps)

        if model == "zeroscope":
            model_input["width"] = 1024
            model_input["height"] = 576
            model_input["num_frames"] = int(request.duration_seconds * request.fps)

        if model == "animatediff":
            model_input["motion_module"] = "mm_sd_v15_v2.ckpt"

        return model_input

    async def _wait_for_prediction(self, client: httpx.AsyncClient, prediction_id: str) -> dict:
        """Wait for prediction to complete."""
        start_time = time.time()

        while True:
            if time.time() - start_time > self.timeout:
                raise TimeoutError("Video generation timed out")

            response = await client.get(
                f"{self.BASE_URL}/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {self.api_token}"},
            )
            response.raise_for_status()

            prediction = response.json()
            status = prediction["status"]

            if status in ["succeeded", "failed", "canceled"]:
                return prediction

            await asyncio.sleep(self.poll_interval)

    async def get_status(self, generation_id: str) -> VideoGenerationResponse:
        """Get status of async generation."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/predictions/{generation_id}",
                headers={"Authorization": f"Bearer {self.api_token}"},
            )
            response.raise_for_status()

            prediction = response.json()
            status = prediction["status"]

            # Map status
            status_map = {
                "starting": "pending",
                "processing": "processing",
                "succeeded": "completed",
                "failed": "failed",
                "canceled": "failed",
            }

            output = prediction.get("output")
            if isinstance(output, list):
                video_url = output[0] if output else None
            else:
                video_url = output

            return VideoGenerationResponse(
                video_url=video_url,
                provider=self.provider_name,
                status=status_map.get(status, "pending"),
                progress=prediction.get("progress", 0) or 0,
                error=prediction.get("error") if status == "failed" else None,
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return list(self.MODELS.keys())

    def estimate_cost(self, request: VideoGenerationRequest) -> float:
        """Estimate generation cost in USD."""
        # Replicate charges by compute time, varies by model
        # These are rough estimates
        model = request.model or self.default_model

        costs = {
            "svd": 0.10,
            "svd-xt": 0.10,
            "animatediff": 0.05,
            "zeroscope": 0.03,
            "cogvideox": 0.15,
            "mochi": 0.20,
        }

        return costs.get(model, 0.10)
