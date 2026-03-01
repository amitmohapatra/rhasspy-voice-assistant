"""Image Generation Module - Support for multiple image generation providers.

Supported Providers:
- OpenAI (DALL-E 3, DALL-E 2)
- Stability AI (Stable Diffusion 3, SDXL)
- Replicate (Various models)
- Midjourney (via API)
- AWS Bedrock (Titan Image, Stable Diffusion)

Features:
- Text-to-image generation
- Image-to-image transformation
- Image editing/inpainting
- Upscaling
- Style transfer
"""

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
from src.image.providers.openai_image import OpenAIImageProvider
from src.image.providers.stability_image import StabilityImageProvider
from src.image.providers.replicate_image import ReplicateImageProvider
from src.image.providers.bedrock_image import BedrockImageProvider


# Provider registry
PROVIDERS = {
    "openai": OpenAIImageProvider,
    "dalle": OpenAIImageProvider,
    "stability": StabilityImageProvider,
    "stable_diffusion": StabilityImageProvider,
    "replicate": ReplicateImageProvider,
    "bedrock": BedrockImageProvider,
    "aws_bedrock": BedrockImageProvider,
}


def get_provider(provider_name: str, **kwargs) -> ImageProvider:
    """Get an image provider instance by name."""
    provider_name = provider_name.lower().replace("-", "_")

    if provider_name not in PROVIDERS:
        available = ", ".join(sorted(PROVIDERS.keys()))
        raise ValueError(f"Unknown provider: {provider_name}. Available: {available}")

    return PROVIDERS[provider_name](**kwargs)


__all__ = [
    # Base classes
    "ImageProvider",
    "ImageSize",
    "ImageStyle",
    "ImageQuality",
    "GenerationRequest",
    "GenerationResponse",
    "ImageEditRequest",
    "UpscaleRequest",
    # Providers
    "OpenAIImageProvider",
    "StabilityImageProvider",
    "ReplicateImageProvider",
    "BedrockImageProvider",
    # Registry
    "PROVIDERS",
    "get_provider",
]
