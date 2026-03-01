"""OpenAI Image Provider - DALL-E 3 and DALL-E 2."""

from __future__ import annotations

import time
from typing import Optional

from openai import AsyncOpenAI

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


class OpenAIImageProvider(ImageProvider):
    """OpenAI DALL-E image generation provider.

    Supports:
    - DALL-E 3: High quality, follows prompts closely
    - DALL-E 2: Faster, supports editing and variations

    Features:
    - Text-to-image generation
    - Image editing (DALL-E 2 only)
    - Image variations (DALL-E 2 only)
    - Automatic prompt revision (DALL-E 3)
    """

    provider_name = "openai"

    # Pricing per image (USD)
    PRICING = {
        "dall-e-3": {
            "1024x1024": {"standard": 0.040, "hd": 0.080},
            "1024x1792": {"standard": 0.080, "hd": 0.120},
            "1792x1024": {"standard": 0.080, "hd": 0.120},
        },
        "dall-e-2": {
            "256x256": 0.016,
            "512x512": 0.018,
            "1024x1024": 0.020,
        },
    }

    # Supported sizes by model
    SUPPORTED_SIZES = {
        "dall-e-3": [
            ImageSize.SQUARE_1024,
            ImageSize.PORTRAIT_1024_1792,
            ImageSize.LANDSCAPE_1792_1024,
        ],
        "dall-e-2": [
            ImageSize.SQUARE_256,
            ImageSize.SQUARE_512,
            ImageSize.SQUARE_1024,
        ],
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        default_model: str = "dall-e-3",
    ):
        """Initialize OpenAI image provider.

        Args:
            api_key: OpenAI API key (uses OPENAI_API_KEY env var if not provided)
            organization: OpenAI organization ID
            default_model: Default model to use
        """
        self.client = AsyncOpenAI(
            api_key=api_key,
            organization=organization,
        )
        self.default_model = default_model

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate images using DALL-E.

        Args:
            request: Generation request with prompt and settings

        Returns:
            GenerationResponse with generated images
        """
        start_time = time.time()
        model = request.model or self.default_model

        try:
            # Validate size for model
            size = request.size.value if request.size else "1024x1024"
            if request.size and request.size not in self.SUPPORTED_SIZES.get(model, []):
                # Fall back to default size for model
                size = "1024x1024"

            # Build generation params
            params = {
                "model": model,
                "prompt": request.prompt,
                "n": min(request.n, 10 if model == "dall-e-2" else 1),  # DALL-E 3 only supports n=1
                "size": size,
                "response_format": request.response_format,
            }

            # DALL-E 3 specific options
            if model == "dall-e-3":
                if request.quality:
                    params["quality"] = "hd" if request.quality == ImageQuality.HD else "standard"
                if request.style:
                    # DALL-E 3 only supports vivid and natural
                    if request.style in [ImageStyle.VIVID, ImageStyle.NATURAL]:
                        params["style"] = request.style.value

            # Generate images
            response = await self.client.images.generate(**params)

            # Process response
            images = []
            for img_data in response.data:
                img = {}
                if img_data.url:
                    img["url"] = img_data.url
                if img_data.b64_json:
                    img["b64_json"] = img_data.b64_json
                if img_data.revised_prompt:
                    img["revised_prompt"] = img_data.revised_prompt
                images.append(img)

            elapsed_ms = (time.time() - start_time) * 1000

            return GenerationResponse(
                images=images,
                model=model,
                provider=self.provider_name,
                cost_usd=self.estimate_cost(request),
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
        """Edit an image using DALL-E 2.

        Note: Only DALL-E 2 supports image editing.

        Args:
            request: Edit request with image, mask, and prompt

        Returns:
            GenerationResponse with edited images
        """
        start_time = time.time()
        model = "dall-e-2"  # Only DALL-E 2 supports editing

        try:
            # Prepare image file
            if isinstance(request.image, str):
                # URL - need to download first
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(request.image)
                    image_data = resp.content
            else:
                image_data = request.image

            # Prepare mask if provided
            mask_data = None
            if request.mask:
                if isinstance(request.mask, str):
                    import httpx
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(request.mask)
                        mask_data = resp.content
                else:
                    mask_data = request.mask

            # Build edit params
            params = {
                "model": model,
                "image": image_data,
                "prompt": request.prompt,
                "n": min(request.n, 10),
                "response_format": request.response_format,
            }

            if mask_data:
                params["mask"] = mask_data

            if request.size:
                params["size"] = request.size.value

            # Edit image
            response = await self.client.images.edit(**params)

            # Process response
            images = []
            for img_data in response.data:
                img = {}
                if img_data.url:
                    img["url"] = img_data.url
                if img_data.b64_json:
                    img["b64_json"] = img_data.b64_json
                images.append(img)

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

    async def create_variation(
        self,
        image: bytes | str,
        n: int = 1,
    ) -> GenerationResponse:
        """Create variations of an image using DALL-E 2.

        Args:
            image: Source image (bytes or URL)
            n: Number of variations

        Returns:
            GenerationResponse with variations
        """
        start_time = time.time()
        model = "dall-e-2"  # Only DALL-E 2 supports variations

        try:
            # Prepare image file
            if isinstance(image, str):
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(image)
                    image_data = resp.content
            else:
                image_data = image

            # Create variations
            response = await self.client.images.create_variation(
                model=model,
                image=image_data,
                n=min(n, 10),
            )

            # Process response
            images = []
            for img_data in response.data:
                img = {}
                if img_data.url:
                    img["url"] = img_data.url
                if img_data.b64_json:
                    img["b64_json"] = img_data.b64_json
                images.append(img)

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

    def list_models(self) -> list[str]:
        """List available DALL-E models."""
        return ["dall-e-3", "dall-e-2"]

    def get_supported_sizes(self, model: str = None) -> list[ImageSize]:
        """Get supported sizes for a model."""
        model = model or self.default_model
        return self.SUPPORTED_SIZES.get(model, self.SUPPORTED_SIZES["dall-e-3"])

    def estimate_cost(self, request: GenerationRequest) -> float:
        """Estimate generation cost in USD."""
        model = request.model or self.default_model
        size = request.size.value if request.size else "1024x1024"
        n = request.n

        if model == "dall-e-3":
            quality = "hd" if request.quality == ImageQuality.HD else "standard"
            size_prices = self.PRICING["dall-e-3"].get(size, self.PRICING["dall-e-3"]["1024x1024"])
            price_per_image = size_prices.get(quality, size_prices["standard"])
        else:
            price_per_image = self.PRICING["dall-e-2"].get(size, 0.020)

        return price_per_image * n
