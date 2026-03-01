"""Base classes for Image Generation providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
from uuid import UUID, uuid4


class ImageSize(str, Enum):
    """Standard image sizes."""
    SQUARE_256 = "256x256"
    SQUARE_512 = "512x512"
    SQUARE_1024 = "1024x1024"
    PORTRAIT_768_1024 = "768x1024"
    PORTRAIT_1024_1792 = "1024x1792"
    LANDSCAPE_1024_768 = "1024x768"
    LANDSCAPE_1792_1024 = "1792x1024"
    HD_1920_1080 = "1920x1080"
    ULTRA_HD_3840_2160 = "3840x2160"


class ImageStyle(str, Enum):
    """Image generation styles."""
    VIVID = "vivid"           # Hyper-real, dramatic
    NATURAL = "natural"       # More natural, less hyper-real
    ANIME = "anime"           # Anime/manga style
    PHOTOGRAPHIC = "photographic"
    DIGITAL_ART = "digital_art"
    CINEMATIC = "cinematic"
    FANTASY = "fantasy"
    PIXEL_ART = "pixel_art"
    WATERCOLOR = "watercolor"
    OIL_PAINTING = "oil_painting"


class ImageQuality(str, Enum):
    """Image quality levels."""
    STANDARD = "standard"
    HD = "hd"
    ULTRA = "ultra"


@dataclass
class GenerationRequest:
    """Request for image generation."""
    prompt: str
    negative_prompt: Optional[str] = None  # What to avoid

    # Model settings
    model: Optional[str] = None
    size: ImageSize = ImageSize.SQUARE_1024
    style: Optional[ImageStyle] = None
    quality: ImageQuality = ImageQuality.STANDARD

    # Generation parameters
    n: int = 1  # Number of images
    seed: Optional[int] = None  # For reproducibility
    guidance_scale: float = 7.5  # How closely to follow prompt
    steps: Optional[int] = None  # Inference steps (for SD)

    # Output format
    response_format: str = "url"  # "url" or "b64_json"

    # Additional options
    extra_options: dict = field(default_factory=dict)


@dataclass
class GenerationResponse:
    """Response from image generation."""
    id: UUID = field(default_factory=uuid4)

    # Generated images
    images: list[dict] = field(default_factory=list)
    # Each image: {"url": "...", "b64_json": "...", "revised_prompt": "..."}

    # Model info
    model: str = ""
    provider: str = ""

    # Usage/cost
    cost_usd: float = 0.0

    # Timing
    generation_time_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Errors
    error: Optional[str] = None


@dataclass
class ImageEditRequest:
    """Request for image editing/inpainting."""
    image: bytes | str  # Image data or URL
    prompt: str
    mask: Optional[bytes | str] = None  # Mask for inpainting

    # Model settings
    model: Optional[str] = None
    size: Optional[ImageSize] = None

    # Edit type
    edit_type: str = "inpaint"  # "inpaint", "outpaint", "variation"

    # Generation parameters
    n: int = 1
    strength: float = 0.8  # How much to change (0-1)

    # Output format
    response_format: str = "url"


@dataclass
class UpscaleRequest:
    """Request for image upscaling."""
    image: bytes | str  # Image data or URL

    # Target size
    scale: int = 2  # 2x, 4x
    target_width: Optional[int] = None
    target_height: Optional[int] = None

    # Model settings
    model: Optional[str] = None

    # Output format
    response_format: str = "url"


class ImageProvider(ABC):
    """Base class for image generation providers."""

    provider_name: str = "base"

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate images from text prompt.

        Args:
            request: Generation request with prompt and settings

        Returns:
            GenerationResponse with generated images
        """
        pass

    @abstractmethod
    async def edit(self, request: ImageEditRequest) -> GenerationResponse:
        """Edit/inpaint an existing image.

        Args:
            request: Edit request with image and prompt

        Returns:
            GenerationResponse with edited images
        """
        pass

    async def upscale(self, request: UpscaleRequest) -> GenerationResponse:
        """Upscale an image (optional - not all providers support).

        Args:
            request: Upscale request

        Returns:
            GenerationResponse with upscaled image
        """
        raise NotImplementedError(f"{self.provider_name} doesn't support upscaling")

    async def create_variation(
        self,
        image: bytes | str,
        n: int = 1,
    ) -> GenerationResponse:
        """Create variations of an existing image (optional).

        Args:
            image: Source image
            n: Number of variations

        Returns:
            GenerationResponse with variations
        """
        raise NotImplementedError(f"{self.provider_name} doesn't support variations")

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available models."""
        pass

    @abstractmethod
    def get_supported_sizes(self, model: str = None) -> list[ImageSize]:
        """Get supported image sizes for a model."""
        pass

    def estimate_cost(self, request: GenerationRequest) -> float:
        """Estimate generation cost in USD."""
        return 0.0  # Override in subclasses
