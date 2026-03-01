"""AWS Bedrock Image Provider - Titan Image Generator and Stable Diffusion."""

from __future__ import annotations

import base64
import json
import time
from typing import Optional

import boto3
from botocore.config import Config

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


class BedrockImageProvider(ImageProvider):
    """AWS Bedrock image generation provider.

    Supports:
    - Amazon Titan Image Generator G1 v2
    - Amazon Titan Image Generator G1 v1
    - Stability AI SDXL 1.0 (via Bedrock)

    Features:
    - Enterprise-grade security
    - VPC integration
    - No data logging by default
    - Regional availability
    """

    provider_name = "bedrock"

    # Model IDs
    MODELS = {
        "titan-image-v2": "amazon.titan-image-generator-v2:0",
        "titan-image-v1": "amazon.titan-image-generator-v1",
        "titan-image": "amazon.titan-image-generator-v2:0",  # Default alias
        "sdxl": "stability.stable-diffusion-xl-v1",
    }

    # Pricing per image (approximate)
    PRICING = {
        "titan-image-v2": {
            "512x512": 0.008,
            "1024x1024": 0.012,
        },
        "sdxl": {
            "512x512": 0.018,
            "1024x1024": 0.036,
        },
    }

    def __init__(
        self,
        region_name: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        profile_name: Optional[str] = None,
        default_model: str = "titan-image",
    ):
        """Initialize AWS Bedrock image provider.

        Args:
            region_name: AWS region
            aws_access_key_id: AWS access key (uses env/config if not provided)
            aws_secret_access_key: AWS secret key
            aws_session_token: AWS session token (for temporary credentials)
            profile_name: AWS profile name
            default_model: Default model to use
        """
        self.region_name = region_name
        self.default_model = default_model

        # Build session kwargs
        session_kwargs = {}
        if profile_name:
            session_kwargs["profile_name"] = profile_name

        # Create session
        session = boto3.Session(**session_kwargs)

        # Build client kwargs
        client_kwargs = {
            "region_name": region_name,
            "config": Config(
                retries={"max_attempts": 3, "mode": "adaptive"}
            ),
        }

        if aws_access_key_id and aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = aws_access_key_id
            client_kwargs["aws_secret_access_key"] = aws_secret_access_key
            if aws_session_token:
                client_kwargs["aws_session_token"] = aws_session_token

        # Create Bedrock runtime client
        self.client = session.client("bedrock-runtime", **client_kwargs)

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate images using Bedrock.

        Args:
            request: Generation request with prompt and settings

        Returns:
            GenerationResponse with generated images
        """
        start_time = time.time()
        model = request.model or self.default_model
        model_id = self.MODELS.get(model, self.MODELS["titan-image"])

        try:
            # Route to appropriate handler
            if "titan" in model_id:
                return await self._generate_titan(request, model_id, start_time)
            else:
                return await self._generate_sdxl(request, model_id, start_time)

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return GenerationResponse(
                model=model,
                provider=self.provider_name,
                generation_time_ms=elapsed_ms,
                error=str(e),
            )

    async def _generate_titan(
        self,
        request: GenerationRequest,
        model_id: str,
        start_time: float,
    ) -> GenerationResponse:
        """Generate using Titan Image Generator."""
        # Parse size
        width, height = self._parse_size(request.size) if request.size else (1024, 1024)

        # Build request body
        body = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {
                "text": request.prompt,
            },
            "imageGenerationConfig": {
                "numberOfImages": min(request.n, 5),  # Titan max is 5
                "width": width,
                "height": height,
                "quality": "premium" if request.quality == ImageQuality.HD else "standard",
            },
        }

        # Add negative prompt
        if request.negative_prompt:
            body["textToImageParams"]["negativeText"] = request.negative_prompt

        # Add seed
        if request.seed is not None:
            body["imageGenerationConfig"]["seed"] = request.seed

        # Add CFG scale
        if request.guidance_scale:
            body["imageGenerationConfig"]["cfgScale"] = request.guidance_scale

        # Invoke model (sync call, run in thread for async)
        import asyncio
        loop = asyncio.get_event_loop()

        response = await loop.run_in_executor(
            None,
            lambda: self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
        )

        # Parse response
        result = json.loads(response["body"].read())

        # Extract images
        images = []
        for img in result.get("images", []):
            images.append({"b64_json": img})

        elapsed_ms = (time.time() - start_time) * 1000

        return GenerationResponse(
            images=images,
            model=request.model or self.default_model,
            provider=self.provider_name,
            cost_usd=self.estimate_cost(request),
            generation_time_ms=elapsed_ms,
        )

    async def _generate_sdxl(
        self,
        request: GenerationRequest,
        model_id: str,
        start_time: float,
    ) -> GenerationResponse:
        """Generate using Stable Diffusion XL on Bedrock."""
        # Parse size
        width, height = self._parse_size(request.size) if request.size else (1024, 1024)

        # Build request body
        body = {
            "text_prompts": [
                {"text": request.prompt, "weight": 1.0},
            ],
            "cfg_scale": request.guidance_scale or 7.0,
            "width": width,
            "height": height,
            "samples": min(request.n, 5),
            "steps": request.steps or 50,
        }

        # Add negative prompt
        if request.negative_prompt:
            body["text_prompts"].append({
                "text": request.negative_prompt,
                "weight": -1.0,
            })

        # Add seed
        if request.seed is not None:
            body["seed"] = request.seed

        # Add style preset
        if request.style:
            style_map = {
                ImageStyle.PHOTOGRAPHIC: "photographic",
                ImageStyle.DIGITAL_ART: "digital-art",
                ImageStyle.CINEMATIC: "cinematic",
                ImageStyle.FANTASY: "fantasy-art",
                ImageStyle.ANIME: "anime",
            }
            if request.style in style_map:
                body["style_preset"] = style_map[request.style]

        # Invoke model
        import asyncio
        loop = asyncio.get_event_loop()

        response = await loop.run_in_executor(
            None,
            lambda: self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
        )

        # Parse response
        result = json.loads(response["body"].read())

        # Extract images
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
            model=request.model or self.default_model,
            provider=self.provider_name,
            cost_usd=self.estimate_cost(request),
            generation_time_ms=elapsed_ms,
        )

    async def edit(self, request: ImageEditRequest) -> GenerationResponse:
        """Edit/inpaint an image using Titan.

        Args:
            request: Edit request with image and prompt

        Returns:
            GenerationResponse with edited images
        """
        start_time = time.time()
        model_id = self.MODELS["titan-image"]

        try:
            # Prepare image
            if isinstance(request.image, str):
                # URL - need to download
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(request.image)
                    image_bytes = resp.content
            else:
                image_bytes = request.image

            image_b64 = base64.b64encode(image_bytes).decode()

            # Build request body
            if request.mask:
                # Inpainting
                task_type = "INPAINTING"

                if isinstance(request.mask, str):
                    import httpx
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(request.mask)
                        mask_bytes = resp.content
                else:
                    mask_bytes = request.mask

                mask_b64 = base64.b64encode(mask_bytes).decode()

                body = {
                    "taskType": task_type,
                    "inPaintingParams": {
                        "text": request.prompt,
                        "image": image_b64,
                        "maskImage": mask_b64,
                    },
                    "imageGenerationConfig": {
                        "numberOfImages": request.n,
                    },
                }
            else:
                # Image variation / outpainting
                task_type = "IMAGE_VARIATION"

                body = {
                    "taskType": task_type,
                    "imageVariationParams": {
                        "text": request.prompt,
                        "images": [image_b64],
                        "similarityStrength": 1.0 - request.strength,  # Invert for Titan
                    },
                    "imageGenerationConfig": {
                        "numberOfImages": request.n,
                    },
                }

            # Invoke model
            import asyncio
            loop = asyncio.get_event_loop()

            response = await loop.run_in_executor(
                None,
                lambda: self.client.invoke_model(
                    modelId=model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json",
                )
            )

            # Parse response
            result = json.loads(response["body"].read())

            # Extract images
            images = []
            for img in result.get("images", []):
                images.append({"b64_json": img})

            elapsed_ms = (time.time() - start_time) * 1000

            return GenerationResponse(
                images=images,
                model="titan-image",
                provider=self.provider_name,
                generation_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return GenerationResponse(
                model="titan-image",
                provider=self.provider_name,
                generation_time_ms=elapsed_ms,
                error=str(e),
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return list(self.MODELS.keys())

    def get_supported_sizes(self, model: str = None) -> list[ImageSize]:
        """Get supported sizes for a model."""
        model = model or self.default_model
        model_id = self.MODELS.get(model, "")

        if "titan" in model_id:
            # Titan supports many sizes in 64px increments
            return [
                ImageSize.SQUARE_512,
                ImageSize.SQUARE_1024,
                ImageSize.PORTRAIT_768_1024,
                ImageSize.LANDSCAPE_1024_768,
            ]
        else:
            # SDXL sizes
            return [
                ImageSize.SQUARE_512,
                ImageSize.SQUARE_1024,
                ImageSize.PORTRAIT_768_1024,
                ImageSize.LANDSCAPE_1024_768,
            ]

    def estimate_cost(self, request: GenerationRequest) -> float:
        """Estimate generation cost in USD."""
        model = request.model or self.default_model
        size = request.size.value if request.size else "1024x1024"
        n = request.n

        model_prices = self.PRICING.get(model, self.PRICING.get("titan-image-v2", {}))
        price_per_image = model_prices.get(size, model_prices.get("1024x1024", 0.012))

        return price_per_image * n

    def _parse_size(self, size: ImageSize) -> tuple[int, int]:
        """Parse ImageSize to width, height tuple."""
        size_str = size.value
        parts = size_str.split("x")
        return int(parts[0]), int(parts[1])
