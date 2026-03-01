"""Stability AI Image Provider - Stable Diffusion 3, SDXL, and more."""

from __future__ import annotations

import base64
import time
from typing import Optional

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


class StabilityImageProvider(ImageProvider):
    """Stability AI image generation provider.

    Supports:
    - Stable Diffusion 3 (SD3): Latest model with improved quality
    - Stable Diffusion 3 Turbo: Fast generation
    - SDXL 1.0: High resolution images
    - Stable Image Core: Optimized for speed
    - Stable Image Ultra: Highest quality

    Features:
    - Text-to-image generation
    - Image-to-image transformation
    - Inpainting/outpainting
    - Upscaling (up to 4x)
    - Negative prompts
    - Style presets
    """

    provider_name = "stability"

    BASE_URL = "https://api.stability.ai"

    # Model configurations
    MODELS = {
        "sd3": {
            "endpoint": "/v2beta/stable-image/generate/sd3",
            "max_size": 1536,
            "supports_negative": True,
        },
        "sd3-turbo": {
            "endpoint": "/v2beta/stable-image/generate/sd3",
            "max_size": 1536,
            "supports_negative": False,  # Turbo doesn't use negative prompts
        },
        "core": {
            "endpoint": "/v2beta/stable-image/generate/core",
            "max_size": 1536,
            "supports_negative": True,
        },
        "ultra": {
            "endpoint": "/v2beta/stable-image/generate/ultra",
            "max_size": 2048,
            "supports_negative": True,
        },
        "sdxl": {
            "endpoint": "/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
            "max_size": 1024,
            "supports_negative": True,
        },
    }

    # Style presets for SDXL
    STYLE_PRESETS = {
        ImageStyle.PHOTOGRAPHIC: "photographic",
        ImageStyle.DIGITAL_ART: "digital-art",
        ImageStyle.CINEMATIC: "cinematic",
        ImageStyle.FANTASY: "fantasy-art",
        ImageStyle.ANIME: "anime",
        ImageStyle.PIXEL_ART: "pixel-art",
    }

    # Pricing (credits per generation)
    PRICING = {
        "sd3": 6.5,  # $0.065 per image
        "sd3-turbo": 4.0,  # $0.04 per image
        "core": 3.0,  # $0.03 per image
        "ultra": 8.0,  # $0.08 per image
        "sdxl": 0.2,  # $0.002 per step, ~30 steps
    }

    def __init__(
        self,
        api_key: str,
        default_model: str = "sd3",
        timeout: float = 120.0,
    ):
        """Initialize Stability AI provider.

        Args:
            api_key: Stability AI API key
            default_model: Default model to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.default_model = default_model
        self.timeout = timeout

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate images using Stable Diffusion.

        Args:
            request: Generation request with prompt and settings

        Returns:
            GenerationResponse with generated images
        """
        start_time = time.time()
        model = request.model or self.default_model
        model_config = self.MODELS.get(model, self.MODELS["sd3"])

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Use appropriate API version
                if model in ["sd3", "sd3-turbo", "core", "ultra"]:
                    return await self._generate_v2(
                        client, request, model, model_config, start_time
                    )
                else:
                    return await self._generate_v1(
                        client, request, model, model_config, start_time
                    )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return GenerationResponse(
                model=model,
                provider=self.provider_name,
                generation_time_ms=elapsed_ms,
                error=str(e),
            )

    async def _generate_v2(
        self,
        client: httpx.AsyncClient,
        request: GenerationRequest,
        model: str,
        model_config: dict,
        start_time: float,
    ) -> GenerationResponse:
        """Generate using v2 API (SD3, Core, Ultra)."""
        # Build form data
        data = {
            "prompt": request.prompt,
            "output_format": "png",
        }

        # Add model-specific params
        if model == "sd3-turbo":
            data["model"] = "sd3-turbo"
        elif model == "sd3":
            data["model"] = "sd3"

        # Add negative prompt if supported
        if model_config["supports_negative"] and request.negative_prompt:
            data["negative_prompt"] = request.negative_prompt

        # Add size
        if request.size:
            width, height = self._parse_size(request.size)
            data["aspect_ratio"] = self._get_aspect_ratio(width, height)

        # Add seed for reproducibility
        if request.seed is not None:
            data["seed"] = request.seed

        # Make request
        response = await client.post(
            f"{self.BASE_URL}{model_config['endpoint']}",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "image/*",
            },
            files={"none": ""},  # Required for multipart
            data=data,
        )
        response.raise_for_status()

        # Response is raw image bytes
        image_bytes = response.content
        b64_image = base64.b64encode(image_bytes).decode()

        elapsed_ms = (time.time() - start_time) * 1000

        return GenerationResponse(
            images=[{"b64_json": b64_image}],
            model=model,
            provider=self.provider_name,
            cost_usd=self.estimate_cost(request),
            generation_time_ms=elapsed_ms,
        )

    async def _generate_v1(
        self,
        client: httpx.AsyncClient,
        request: GenerationRequest,
        model: str,
        model_config: dict,
        start_time: float,
    ) -> GenerationResponse:
        """Generate using v1 API (SDXL)."""
        # Build request body
        width, height = self._parse_size(request.size) if request.size else (1024, 1024)

        body = {
            "text_prompts": [
                {"text": request.prompt, "weight": 1.0},
            ],
            "cfg_scale": request.guidance_scale,
            "width": width,
            "height": height,
            "samples": request.n,
            "steps": request.steps or 30,
        }

        # Add negative prompt
        if request.negative_prompt:
            body["text_prompts"].append({
                "text": request.negative_prompt,
                "weight": -1.0,
            })

        # Add style preset
        if request.style and request.style in self.STYLE_PRESETS:
            body["style_preset"] = self.STYLE_PRESETS[request.style]

        # Add seed
        if request.seed is not None:
            body["seed"] = request.seed

        # Make request
        response = await client.post(
            f"{self.BASE_URL}{model_config['endpoint']}",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=body,
        )
        response.raise_for_status()

        result = response.json()

        # Process artifacts
        images = []
        for artifact in result.get("artifacts", []):
            if artifact.get("finishReason") == "SUCCESS":
                images.append({
                    "b64_json": artifact["base64"],
                    "seed": artifact.get("seed"),
                })

        elapsed_ms = (time.time() - start_time) * 1000

        return GenerationResponse(
            images=images,
            model=model,
            provider=self.provider_name,
            cost_usd=self.estimate_cost(request),
            generation_time_ms=elapsed_ms,
        )

    async def edit(self, request: ImageEditRequest) -> GenerationResponse:
        """Edit/inpaint an image.

        Args:
            request: Edit request with image and prompt

        Returns:
            GenerationResponse with edited images
        """
        start_time = time.time()

        try:
            # Prepare image
            if isinstance(request.image, str):
                async with httpx.AsyncClient() as client:
                    resp = await client.get(request.image)
                    image_bytes = resp.content
            else:
                image_bytes = request.image

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Use inpaint endpoint
                files = {
                    "image": ("image.png", image_bytes, "image/png"),
                }

                data = {
                    "prompt": request.prompt,
                    "output_format": "png",
                }

                # Add mask if provided
                if request.mask:
                    if isinstance(request.mask, str):
                        async with httpx.AsyncClient() as c:
                            resp = await c.get(request.mask)
                            mask_bytes = resp.content
                    else:
                        mask_bytes = request.mask
                    files["mask"] = ("mask.png", mask_bytes, "image/png")

                # Add strength for img2img
                if request.strength:
                    data["strength"] = request.strength

                response = await client.post(
                    f"{self.BASE_URL}/v2beta/stable-image/edit/inpaint",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "image/*",
                    },
                    files=files,
                    data=data,
                )
                response.raise_for_status()

                image_bytes = response.content
                b64_image = base64.b64encode(image_bytes).decode()

                elapsed_ms = (time.time() - start_time) * 1000

                return GenerationResponse(
                    images=[{"b64_json": b64_image}],
                    model="inpaint",
                    provider=self.provider_name,
                    generation_time_ms=elapsed_ms,
                )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return GenerationResponse(
                model="inpaint",
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

        try:
            # Prepare image
            if isinstance(request.image, str):
                async with httpx.AsyncClient() as client:
                    resp = await client.get(request.image)
                    image_bytes = resp.content
            else:
                image_bytes = request.image

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Choose upscale model based on scale factor
                if request.scale >= 4:
                    endpoint = "/v2beta/stable-image/upscale/creative"
                else:
                    endpoint = "/v2beta/stable-image/upscale/fast"

                files = {
                    "image": ("image.png", image_bytes, "image/png"),
                }

                data = {
                    "output_format": "png",
                }

                if request.target_width:
                    data["width"] = request.target_width
                if request.target_height:
                    data["height"] = request.target_height

                response = await client.post(
                    f"{self.BASE_URL}{endpoint}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "image/*",
                    },
                    files=files,
                    data=data,
                )
                response.raise_for_status()

                image_bytes = response.content
                b64_image = base64.b64encode(image_bytes).decode()

                elapsed_ms = (time.time() - start_time) * 1000

                return GenerationResponse(
                    images=[{"b64_json": b64_image}],
                    model="upscale",
                    provider=self.provider_name,
                    generation_time_ms=elapsed_ms,
                )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return GenerationResponse(
                model="upscale",
                provider=self.provider_name,
                generation_time_ms=elapsed_ms,
                error=str(e),
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return list(self.MODELS.keys())

    def get_supported_sizes(self, model: str = None) -> list[ImageSize]:
        """Get supported sizes for a model."""
        return [
            ImageSize.SQUARE_512,
            ImageSize.SQUARE_1024,
            ImageSize.PORTRAIT_768_1024,
            ImageSize.PORTRAIT_1024_1792,
            ImageSize.LANDSCAPE_1024_768,
            ImageSize.LANDSCAPE_1792_1024,
        ]

    def estimate_cost(self, request: GenerationRequest) -> float:
        """Estimate generation cost in USD."""
        model = request.model or self.default_model
        credits = self.PRICING.get(model, 6.5)
        # 1000 credits = $10, so 1 credit = $0.01
        return (credits / 100) * request.n

    def _parse_size(self, size: ImageSize) -> tuple[int, int]:
        """Parse ImageSize to width, height tuple."""
        size_str = size.value
        parts = size_str.split("x")
        return int(parts[0]), int(parts[1])

    def _get_aspect_ratio(self, width: int, height: int) -> str:
        """Get aspect ratio string for v2 API."""
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
        elif abs(ratio - 21/9) < 0.1:
            return "21:9"
        elif abs(ratio - 9/21) < 0.1:
            return "9:21"
        else:
            # Default to closest standard ratio
            return "1:1"
