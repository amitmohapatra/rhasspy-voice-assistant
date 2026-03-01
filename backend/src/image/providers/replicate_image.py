"""Replicate Image Provider - Run any image model via API."""

from __future__ import annotations

import asyncio
import time
from typing import Optional, Any

import httpx

from src.image.base import (
    ImageProvider,
    ImageSize,
    ImageStyle,
    ImageQuality,
    GenerationRequest,
    GenerationResponse,
    ImageEditRequest,
    UpscaleRequest,
)


class ReplicateImageProvider(ImageProvider):
    """Replicate image generation provider.

    Supports running any image model on Replicate's infrastructure:
    - FLUX.1 (schnell, dev, pro)
    - Stable Diffusion XL
    - Stable Diffusion 3
    - Ideogram
    - Playground v2.5
    - RealVisXL
    - And many more...

    Features:
    - Run any public or private model
    - Automatic scaling
    - Pay per prediction
    - Webhook support
    """

    provider_name = "replicate"

    BASE_URL = "https://api.replicate.com/v1"

    # Popular model versions
    MODELS = {
        # FLUX models
        "flux-schnell": "black-forest-labs/flux-schnell",
        "flux-dev": "black-forest-labs/flux-dev",
        "flux-pro": "black-forest-labs/flux-pro",

        # Stable Diffusion
        "sdxl": "stability-ai/sdxl:c221b2b8ef527988fb59bf24a8b97c4561f1c671f73bd389f866bfb27c061316",
        "sd3": "stability-ai/stable-diffusion-3",

        # Other popular models
        "ideogram": "ideogram-ai/ideogram-v2",
        "playground": "playgroundai/playground-v2.5-1024px-aesthetic",
        "realvis": "lucataco/realvisxl-v4.0:c72a68c25f8d3d8b58c99de63be75e6e6db5da61ae80cf604fc95fb0c3cc5d03",

        # Upscalers
        "esrgan": "nightmareai/real-esrgan:f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa",
        "swinir": "jingyunliang/swinir:660d922d33153019e8c263a3bba265de882e7f4f70396571bf7f1e7c89b4658",
    }

    def __init__(
        self,
        api_token: str,
        default_model: str = "flux-schnell",
        timeout: float = 300.0,
        poll_interval: float = 1.0,
    ):
        """Initialize Replicate provider.

        Args:
            api_token: Replicate API token
            default_model: Default model to use
            timeout: Maximum time to wait for prediction
            poll_interval: Time between status polls
        """
        self.api_token = api_token
        self.default_model = default_model
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate images using Replicate.

        Args:
            request: Generation request with prompt and settings

        Returns:
            GenerationResponse with generated images
        """
        start_time = time.time()
        model = request.model or self.default_model

        try:
            # Get model version
            model_version = self.MODELS.get(model, model)

            # Build input based on model type
            model_input = self._build_input(request, model)

            # Create prediction
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Determine API endpoint
                if "/" in model_version and ":" not in model_version:
                    # Official model format: owner/name
                    endpoint = f"{self.BASE_URL}/models/{model_version}/predictions"
                else:
                    # Version format: owner/name:version
                    endpoint = f"{self.BASE_URL}/predictions"
                    model_input["version"] = model_version.split(":")[-1] if ":" in model_version else None

                # Create prediction
                create_body = {"input": model_input}
                if ":" in model_version:
                    create_body["version"] = model_version.split(":")[-1]

                response = await client.post(
                    endpoint if "/" in model_version and ":" not in model_version else f"{self.BASE_URL}/predictions",
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json",
                    },
                    json=create_body,
                )
                response.raise_for_status()
                prediction = response.json()

                # Poll for completion
                prediction_id = prediction["id"]
                result = await self._wait_for_prediction(client, prediction_id)

                if result["status"] == "failed":
                    raise Exception(result.get("error", "Prediction failed"))

                # Process output
                output = result.get("output", [])
                if isinstance(output, str):
                    output = [output]

                images = [{"url": url} for url in output if url]

                elapsed_ms = (time.time() - start_time) * 1000

                return GenerationResponse(
                    images=images,
                    model=model,
                    provider=self.provider_name,
                    generation_time_ms=elapsed_ms,
                )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return GenerationResponse(
                model=model,
                provider=self.provider_name,
                generation_time_ms=elapsed_ms,
                error=str(e),
            )

    async def edit(self, request: ImageEditRequest) -> GenerationResponse:
        """Edit an image using img2img models.

        Args:
            request: Edit request with image and prompt

        Returns:
            GenerationResponse with edited images
        """
        start_time = time.time()
        model = request.model or "sdxl"

        try:
            model_version = self.MODELS.get(model, model)

            # Build input for img2img
            model_input = {
                "prompt": request.prompt,
                "image": request.image if isinstance(request.image, str) else None,
                "strength": request.strength,
            }

            if request.mask:
                model_input["mask"] = request.mask if isinstance(request.mask, str) else None

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

                # Poll for completion
                result = await self._wait_for_prediction(client, prediction["id"])

                if result["status"] == "failed":
                    raise Exception(result.get("error", "Prediction failed"))

                # Process output
                output = result.get("output", [])
                if isinstance(output, str):
                    output = [output]

                images = [{"url": url} for url in output if url]

                elapsed_ms = (time.time() - start_time) * 1000

                return GenerationResponse(
                    images=images,
                    model=model,
                    provider=self.provider_name,
                    generation_time_ms=elapsed_ms,
                )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return GenerationResponse(
                model=model,
                provider=self.provider_name,
                generation_time_ms=elapsed_ms,
                error=str(e),
            )

    async def upscale(self, request: UpscaleRequest) -> GenerationResponse:
        """Upscale an image.

        Args:
            request: Upscale request

        Returns:
            GenerationResponse with upscaled image
        """
        start_time = time.time()
        model = request.model or "esrgan"

        try:
            model_version = self.MODELS.get(model, self.MODELS["esrgan"])

            # Build input
            model_input = {
                "image": request.image if isinstance(request.image, str) else None,
                "scale": request.scale,
            }

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

                # Poll for completion
                result = await self._wait_for_prediction(client, prediction["id"])

                if result["status"] == "failed":
                    raise Exception(result.get("error", "Prediction failed"))

                # Process output
                output = result.get("output")
                if isinstance(output, list):
                    output = output[0] if output else None

                images = [{"url": output}] if output else []

                elapsed_ms = (time.time() - start_time) * 1000

                return GenerationResponse(
                    images=images,
                    model=model,
                    provider=self.provider_name,
                    generation_time_ms=elapsed_ms,
                )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return GenerationResponse(
                model=model,
                provider=self.provider_name,
                generation_time_ms=elapsed_ms,
                error=str(e),
            )

    async def _wait_for_prediction(
        self,
        client: httpx.AsyncClient,
        prediction_id: str,
    ) -> dict:
        """Wait for a prediction to complete."""
        start_time = time.time()

        while True:
            if time.time() - start_time > self.timeout:
                raise TimeoutError("Prediction timed out")

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

    def _build_input(self, request: GenerationRequest, model: str) -> dict:
        """Build model input based on model type."""
        # Base input
        model_input = {
            "prompt": request.prompt,
        }

        # Add negative prompt if supported
        if request.negative_prompt:
            model_input["negative_prompt"] = request.negative_prompt

        # Parse size
        if request.size:
            width, height = self._parse_size(request.size)
            model_input["width"] = width
            model_input["height"] = height

        # Add common parameters
        if request.seed is not None:
            model_input["seed"] = request.seed

        if request.guidance_scale:
            model_input["guidance_scale"] = request.guidance_scale

        if request.steps:
            model_input["num_inference_steps"] = request.steps

        if request.n > 1:
            model_input["num_outputs"] = request.n

        # Model-specific parameters
        if model.startswith("flux"):
            # FLUX uses different param names
            model_input["num_outputs"] = request.n
            if "aspect_ratio" not in model_input and request.size:
                model_input["aspect_ratio"] = self._get_aspect_ratio(request.size)

        return model_input

    def _parse_size(self, size: ImageSize) -> tuple[int, int]:
        """Parse ImageSize to width, height tuple."""
        size_str = size.value
        parts = size_str.split("x")
        return int(parts[0]), int(parts[1])

    def _get_aspect_ratio(self, size: ImageSize) -> str:
        """Get aspect ratio string for FLUX."""
        width, height = self._parse_size(size)
        ratio = width / height

        if abs(ratio - 1.0) < 0.1:
            return "1:1"
        elif abs(ratio - 16/9) < 0.1:
            return "16:9"
        elif abs(ratio - 9/16) < 0.1:
            return "9:16"
        elif abs(ratio - 4/3) < 0.1:
            return "4:3"
        elif abs(ratio - 3/4) < 0.1:
            return "3:4"
        else:
            return "1:1"

    def list_models(self) -> list[str]:
        """List available models."""
        return list(self.MODELS.keys())

    def get_supported_sizes(self, model: str = None) -> list[ImageSize]:
        """Get supported sizes for a model."""
        # Most models support common sizes
        return [
            ImageSize.SQUARE_512,
            ImageSize.SQUARE_1024,
            ImageSize.PORTRAIT_768_1024,
            ImageSize.PORTRAIT_1024_1792,
            ImageSize.LANDSCAPE_1024_768,
            ImageSize.LANDSCAPE_1792_1024,
        ]

    async def search_models(
        self,
        query: str = "image generation",
        limit: int = 10,
    ) -> list[dict]:
        """Search for models on Replicate.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of model info dicts
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/models",
                headers={"Authorization": f"Bearer {self.api_token}"},
                params={"query": query, "limit": limit},
            )
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])
