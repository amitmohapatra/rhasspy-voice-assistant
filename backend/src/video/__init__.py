"""Video Generation Module - Text-to-video and image-to-video providers.

Supported Providers:
- Runway (Gen-3 Alpha)
- Luma AI (Dream Machine)
- Pika Labs
- Stability AI (Stable Video Diffusion)
- Replicate (Various models)

Features:
- Text-to-video generation
- Image-to-video animation
- Video extension/continuation
- Video upscaling
- Style control
- Motion control
"""

from src.video.base import (
    # Enums
    VideoQuality,
    AspectRatio,
    VideoStyle,
    VideoFormat,
    # Request/Response
    VideoGenerationRequest,
    ImageToVideoRequest,
    VideoExtendRequest,
    VideoUpscaleRequest,
    VideoGenerationResponse,
    # Base class
    VideoProvider,
)
from src.video.providers.runway_video import RunwayVideoProvider
from src.video.providers.luma_video import LumaVideoProvider
from src.video.providers.replicate_video import ReplicateVideoProvider
from src.video.providers.stability_video import StabilityVideoProvider


# Provider registry
PROVIDERS = {
    "runway": RunwayVideoProvider,
    "runway_gen3": RunwayVideoProvider,
    "luma": LumaVideoProvider,
    "luma_ai": LumaVideoProvider,
    "dream_machine": LumaVideoProvider,
    "replicate": ReplicateVideoProvider,
    "stability": StabilityVideoProvider,
    "stable_video": StabilityVideoProvider,
}


def get_provider(provider_name: str, **kwargs) -> VideoProvider:
    """Get a video provider instance by name."""
    provider_name = provider_name.lower().replace("-", "_")

    if provider_name not in PROVIDERS:
        available = ", ".join(sorted(PROVIDERS.keys()))
        raise ValueError(f"Unknown provider: {provider_name}. Available: {available}")

    return PROVIDERS[provider_name](**kwargs)


__all__ = [
    # Enums
    "VideoQuality",
    "AspectRatio",
    "VideoStyle",
    "VideoFormat",
    # Request/Response
    "VideoGenerationRequest",
    "ImageToVideoRequest",
    "VideoExtendRequest",
    "VideoUpscaleRequest",
    "VideoGenerationResponse",
    # Base class
    "VideoProvider",
    # Providers
    "RunwayVideoProvider",
    "LumaVideoProvider",
    "ReplicateVideoProvider",
    "StabilityVideoProvider",
    # Registry
    "PROVIDERS",
    "get_provider",
]
