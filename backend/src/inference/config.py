"""Inference service configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class InferenceSettings(BaseSettings):
    """Settings for the inference service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    workers: int = Field(default=1)

    # Device
    device: str = Field(default="cpu")  # cpu, cuda, mps

    # BGE-M3 settings
    bge_m3_model: str = Field(default="BAAI/bge-m3")
    bge_m3_use_onnx: bool = Field(default=True)
    bge_m3_batch_size: int = Field(default=4)  # Small batches to limit peak memory on CPU
    bge_m3_max_length: int = Field(default=1024)  # Chunks are typically <500 tokens

    # Reranker settings
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3")
    reranker_batch_size: int = Field(default=16)

    # OCR language configuration
    # RapidOCR + PP-OCRv5 server models (106 languages via ONNX).
    # PP-OCRv5 language codes: en, ch, hi (Hindi), ar (Arabic), ta (Tamil),
    # te (Telugu), ja (Japanese), ko (Korean), ru (Russian), fr, de, es, etc.
    # Full list: https://www.paddleocr.ai/latest/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html
    ocr_languages: str = Field(
        default="en,ch,hi,ar,ta,te,ja,korean,ru,fr,de,es,it,pt",
        description="Comma-separated PaddleOCR language codes for RapidOCR PP-OCRv5",
    )
    # Force OCR on every page (needed for scanned docs with missing/garbled text layers)
    force_full_page_ocr: bool = Field(default=False)
    # Minimum bitmap area (fraction of page) to trigger OCR.
    # Default 0.05 catches tiny decorative borders; 0.08 reduces noise while
    # still OCR-ing real bitmap text blocks.
    bitmap_area_threshold: float = Field(default=0.08)

    # Image resolution scale for Docling page rendering.
    # 1.0 = 72 DPI (fast), 2.0 = 144 DPI (recommended when VLM is enabled).
    docling_images_scale: float = Field(default=1.0)

    # Docling pipeline features
    docling_do_chart_extraction: bool = Field(default=True)
    docling_do_picture_classification: bool = Field(default=True)
    docling_do_picture_description: bool = Field(default=True)
    docling_vlm_model: str = Field(
        default="HuggingFaceTB/SmolVLM-500M-Instruct",
        description="HuggingFace repo_id for the local VLM used by Docling to describe images/charts",
    )
    docling_do_code_enrichment: bool = Field(default=True)
    docling_do_formula_enrichment: bool = Field(default=True)
    docling_document_timeout: int = Field(default=120)

    # VLM API mode — set docling_vlm_use_api=true to call an external
    # OpenAI-compatible API (vLLM, Ollama, OpenAI, etc.) instead of loading
    # a local VLM. This frees ~1GB RAM and lets you use larger models
    # like Qwen2.5-VL-72B on a GPU server.
    docling_vlm_use_api: bool = Field(
        default=False,
        description="Use external API for VLM instead of local model",
    )
    docling_vlm_api_url: str = Field(
        default="http://localhost:8080/v1",
        description="OpenAI-compatible API base URL (vLLM, Ollama, etc.)",
    )
    docling_vlm_api_key: str = Field(
        default="",
        description="API key for the VLM API (leave empty for local vLLM/Ollama)",
    )
    docling_vlm_api_model: str = Field(
        default="Qwen/Qwen2.5-VL-7B-Instruct",
        description="Model name to send in API requests",
    )

    # ColSmol-256M for visual page retrieval
    colsmol_enabled: bool = Field(
        default=False,
        description="Enable ColSmol visual page retrieval (requires ~500MB extra RAM)",
    )
    colsmol_model: str = Field(
        default="vidore/colsmol-256m",
        description="ColSmol model for visual page retrieval (multi-vector, 128-dim patches)",
    )
    colsmol_batch_size: int = Field(default=2)  # Pages per batch (large images)

    # Logging
    log_level: str = Field(default="INFO")


inference_settings = InferenceSettings()
