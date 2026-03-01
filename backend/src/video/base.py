"""Base classes for Video Generation providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, AsyncIterator
from uuid import UUID, uuid4


class VideoQuality(str, Enum):
    """Video quality levels."""
    LOW = "360p"
    MEDIUM = "480p"
    STANDARD = "720p"
    HD = "1080p"
    FULL_HD = "1080p"
    UHD = "4k"


class AspectRatio(str, Enum):
    """Video aspect ratios."""
    SQUARE = "1:1"
    PORTRAIT = "9:16"
    LANDSCAPE = "16:9"
    CINEMA = "21:9"
    STANDARD = "4:3"


class VideoStyle(str, Enum):
    """Video generation styles."""
    REALISTIC = "realistic"
    CINEMATIC = "cinematic"
    ANIME = "anime"
    CARTOON = "cartoon"
    ARTISTIC = "artistic"
    DOCUMENTARY = "documentary"
    COMMERCIAL = "commercial"
    MUSIC_VIDEO = "music_video"
    SLOW_MOTION = "slow_motion"
    TIMELAPSE = "timelapse"


class VideoFormat(str, Enum):
    """Video output formats."""
    MP4 = "mp4"
    WEBM = "webm"
    GIF = "gif"
    MOV = "mov"


@dataclass
class VideoGenerationRequest:
    """Request for text-to-video generation."""
    prompt: str
    negative_prompt: Optional[str] = None

    # Model settings
    model: Optional[str] = None

    # Video specs
    duration_seconds: float = 4.0  # Most models default to 4s
    fps: int = 24
    quality: VideoQuality = VideoQuality.HD
    aspect_ratio: AspectRatio = AspectRatio.LANDSCAPE

    # Style settings
    style: Optional[VideoStyle] = None
    style_strength: float = 1.0

    # Generation parameters
    seed: Optional[int] = None
    guidance_scale: float = 7.0
    num_inference_steps: Optional[int] = None

    # Output format
    output_format: VideoFormat = VideoFormat.MP4

    # Additional options
    extra_options: dict = field(default_factory=dict)


@dataclass
class ImageToVideoRequest:
    """Request for image-to-video generation."""
    image: bytes | str  # Image data or URL
    prompt: Optional[str] = None

    # Model settings
    model: Optional[str] = None

    # Video specs
    duration_seconds: float = 4.0
    fps: int = 24
    quality: VideoQuality = VideoQuality.HD

    # Motion settings
    motion_strength: float = 0.5  # 0-1, how much motion to add

    # Generation parameters
    seed: Optional[int] = None

    # Output format
    output_format: VideoFormat = VideoFormat.MP4

    # Additional options
    extra_options: dict = field(default_factory=dict)


@dataclass
class VideoExtendRequest:
    """Request for extending/continuing a video."""
    video: bytes | str  # Video data or URL
    prompt: Optional[str] = None

    # Extension settings
    extend_seconds: float = 4.0
    direction: str = "forward"  # "forward" or "backward"

    # Model settings
    model: Optional[str] = None

    # Output format
    output_format: VideoFormat = VideoFormat.MP4


@dataclass
class VideoUpscaleRequest:
    """Request for video upscaling/enhancement."""
    video: bytes | str  # Video data or URL

    # Upscale settings
    target_quality: VideoQuality = VideoQuality.UHD
    target_fps: Optional[int] = None  # Frame interpolation

    # Enhancement options
    denoise: bool = False
    stabilize: bool = False
    color_correct: bool = False

    # Model settings
    model: Optional[str] = None


@dataclass
class VideoGenerationResponse:
    """Response from video generation."""
    id: UUID = field(default_factory=uuid4)

    # Generated video
    video_url: Optional[str] = None
    video_data: Optional[bytes] = None
    thumbnail_url: Optional[str] = None

    # Video metadata
    duration_seconds: float = 0.0
    fps: int = 24
    width: int = 0
    height: int = 0
    format: VideoFormat = VideoFormat.MP4
    file_size_bytes: int = 0

    # Generation info
    model: str = ""
    provider: str = ""
    seed: Optional[int] = None

    # Usage/cost
    cost_usd: float = 0.0

    # Timing
    generation_time_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Status for async generation
    status: str = "completed"  # "pending", "processing", "completed", "failed"
    progress: float = 1.0  # 0-1

    # Errors
    error: Optional[str] = None


class VideoProvider(ABC):
    """Base class for video generation providers."""

    provider_name: str = "base"

    @abstractmethod
    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        """Generate video from text prompt.

        Args:
            request: Video generation request

        Returns:
            VideoGenerationResponse with generated video
        """
        pass

    async def image_to_video(self, request: ImageToVideoRequest) -> VideoGenerationResponse:
        """Generate video from image.

        Args:
            request: Image-to-video request

        Returns:
            VideoGenerationResponse with generated video
        """
        raise NotImplementedError(f"{self.provider_name} doesn't support image-to-video")

    async def extend_video(self, request: VideoExtendRequest) -> VideoGenerationResponse:
        """Extend/continue an existing video.

        Args:
            request: Video extension request

        Returns:
            VideoGenerationResponse with extended video
        """
        raise NotImplementedError(f"{self.provider_name} doesn't support video extension")

    async def upscale(self, request: VideoUpscaleRequest) -> VideoGenerationResponse:
        """Upscale/enhance a video.

        Args:
            request: Video upscale request

        Returns:
            VideoGenerationResponse with upscaled video
        """
        raise NotImplementedError(f"{self.provider_name} doesn't support video upscaling")

    async def get_status(self, generation_id: str) -> VideoGenerationResponse:
        """Get status of async generation.

        Args:
            generation_id: ID of the generation task

        Returns:
            VideoGenerationResponse with current status
        """
        raise NotImplementedError(f"{self.provider_name} doesn't support async status")

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available video generation models."""
        pass

    def estimate_cost(self, request: VideoGenerationRequest) -> float:
        """Estimate generation cost in USD."""
        return 0.0
