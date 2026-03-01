"""Model manager - loads and holds all ML models in memory.

Models pre-loaded at startup via FastAPI lifespan:
- BGE-M3 (embeddings), BGE-reranker-v2-m3 (reranking)
- Docling (document parsing + OCR + VLM picture description)
- img2table (borderless table extraction)
- ColSmol-256M (visual page retrieval, multi-vector 128-dim) — OPTIONAL, disabled by default

Docling handles internally:
- OCR via RapidOCR + PP-OCRv5 server ONNX models (106 languages)
- Picture/chart description via VLM — two modes:
  - Local: SmolVLM-500M (default, ~1GB) via PictureDescriptionVlmOptions
  - API: Any model via PictureDescriptionApiOptions (vLLM, Ollama, OpenAI)
    Set DOCLING_VLM_USE_API=true + DOCLING_VLM_API_URL to enable.

Multi-format support:
- PDF + IMAGE: Full ML pipeline (OCR, table structure, VLM, 144 DPI)
- DOCX, PPTX, XLSX, HTML, MD: Native parsing via SimplePipeline (no ML needed)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.inference.config import InferenceSettings

logger = logging.getLogger(__name__)


class ModelManager:
    """Pre-loads all ML models at startup and holds them in memory.

    Thread-safe: uses a lock for model dict access since loading
    runs in executor threads.
    """

    def __init__(self, settings: InferenceSettings):
        self.settings = settings
        self._lock = threading.Lock()
        self._models: dict[str, Any] = {}
        self._load_times: dict[str, float] = {}
        self._loaded: dict[str, bool] = {}
        self._executor = ThreadPoolExecutor(max_workers=2)

    @property
    def all_loaded(self) -> bool:
        """Check if all required models are loaded."""
        required = {"bge_m3", "reranker", "docling", "img2table"}
        if self.settings.colsmol_enabled:
            required.add("colsmol")
        return required.issubset(
            k for k, v in self._loaded.items() if v
        )

    def get_status(self) -> dict[str, dict]:
        """Get load status for all models."""
        from src.inference.schemas import ModelStatus

        names = ["bge_m3", "reranker", "docling", "img2table"]
        if self.settings.colsmol_enabled:
            names.append("colsmol")

        status = {}
        for name in names:
            status[name] = ModelStatus(
                loaded=self._loaded.get(name, False),
                name=self._get_model_display_name(name),
                load_time_seconds=self._load_times.get(name),
            ).model_dump()
        return status

    def _get_model_display_name(self, name: str) -> str:
        names = {
            "bge_m3": self.settings.bge_m3_model,
            "reranker": self.settings.reranker_model,
            "docling": f"docling-DocumentConverter (VLM: {'API:' + self.settings.docling_vlm_api_model if self.settings.docling_vlm_use_api else self.settings.docling_vlm_model})",
            "img2table": "img2table-OpenCV",
            "colsmol": self.settings.colsmol_model,
        }
        return names.get(name, name)

    async def load_all(self) -> None:
        """Load all models at startup."""
        import asyncio

        loop = asyncio.get_running_loop()

        # Load sequentially to limit peak memory
        await loop.run_in_executor(self._executor, self._load_bge_m3)
        await loop.run_in_executor(self._executor, self._load_reranker)
        await loop.run_in_executor(self._executor, self._load_docling)
        await loop.run_in_executor(self._executor, self._load_img2table)
        if self.settings.colsmol_enabled:
            await loop.run_in_executor(self._executor, self._load_colsmol)
        else:
            logger.info("ColSmol disabled (COLSMOL_ENABLED=false) — visual page retrieval skipped")
            self._loaded["colsmol"] = False

        model_count = sum(1 for v in self._loaded.values() if v)
        if self.settings.docling_do_picture_description:
            vlm_mode = "API:" + self.settings.docling_vlm_api_model if self.settings.docling_vlm_use_api else f"local:{self.settings.docling_vlm_model}"
            vlm_info = f" + VLM {vlm_mode}"
        else:
            vlm_info = ", VLM disabled"
        logger.info("All %d models loaded (Docling: RapidOCR PP-OCRv5%s)", model_count, vlm_info)

    def _load_bge_m3(self) -> None:
        """Load BGE-M3 embedding model."""
        start = time.time()
        try:
            from FlagEmbedding import BGEM3FlagModel

            logger.info("Loading BGE-M3: %s (device: %s)",
                        self.settings.bge_m3_model, self.settings.device)

            model = BGEM3FlagModel(
                self.settings.bge_m3_model,
                use_fp16=(self.settings.device != "cpu"),
                device=self.settings.device,
            )
            with self._lock:
                self._models["bge_m3"] = model
                self._loaded["bge_m3"] = True
                self._load_times["bge_m3"] = time.time() - start
            logger.info("BGE-M3 loaded in %.1fs", self._load_times["bge_m3"])
        except Exception as e:
            logger.error("Failed to load BGE-M3: %s", e)
            self._loaded["bge_m3"] = False
            raise

    def _load_reranker(self) -> None:
        """Load BGE reranker model."""
        start = time.time()
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification

            logger.info("Loading reranker: %s", self.settings.reranker_model)

            tokenizer = AutoTokenizer.from_pretrained(self.settings.reranker_model)
            model = AutoModelForSequenceClassification.from_pretrained(
                self.settings.reranker_model
            )

            if self.settings.device != "cpu":
                model = model.to(self.settings.device)

            model.eval()
            with self._lock:
                self._models["reranker_tokenizer"] = tokenizer
                self._models["reranker_model"] = model
                self._loaded["reranker"] = True
                self._load_times["reranker"] = time.time() - start
            logger.info("Reranker loaded in %.1fs", self._load_times["reranker"])
        except Exception as e:
            logger.error("Failed to load reranker: %s", e)
            self._loaded["reranker"] = False
            raise

    def _load_docling(self) -> None:
        """Load Docling DocumentConverter with full capabilities.

        - RapidOCR backend with PP-OCRv5 server ONNX models (106 languages)
        - VLM for picture/chart description:
          - Local mode: SmolVLM-500M via PictureDescriptionVlmOptions (~1GB)
          - API mode: Any model via PictureDescriptionApiOptions (vLLM/Ollama/OpenAI)
        - Table structure (ACCURATE mode with cell matching)
        - Chart extraction, picture classification, code/formula enrichment
        - Page + picture + table image generation
        """
        start = time.time()
        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                PdfPipelineOptions,
                PictureDescriptionVlmOptions,
                TableStructureOptions,
                TableFormerMode,
                RapidOcrOptions,
            )

            # Non-PDF format options (SimplePipeline — native parsing, no ML)
            try:
                from docling.document_converter import (
                    WordFormatOption,
                    ExcelFormatOption,
                    PowerpointFormatOption,
                    ImageFormatOption,
                    HTMLFormatOption,
                    MarkdownFormatOption,
                )
                has_multi_format = True
            except ImportError:
                has_multi_format = False
                logger.warning("Multi-format options not available in this Docling version")

            logger.info("Loading Docling DocumentConverter")

            # Parse OCR languages from config (comma-separated)
            ocr_langs = [
                lang.strip()
                for lang in self.settings.ocr_languages.split(",")
                if lang.strip()
            ] or ["en"]
            logger.info("Docling OCR languages: %s", ocr_langs)

            # RapidOCR with PP-OCRv5 server models (106 languages via ONNX).
            # Downloads PP-OCRv5 ONNX models from HuggingFace on first run.
            ocr_options = self._build_rapidocr_options(RapidOcrOptions, ocr_langs)

            pipeline_options = PdfPipelineOptions()
            # Image resolution (2.0 = 144 DPI, recommended for VLM)
            pipeline_options.images_scale = self.settings.docling_images_scale
            # OCR (force_full_page_ocr is set on RapidOcrOptions, not here)
            pipeline_options.do_ocr = True
            pipeline_options.ocr_options = ocr_options
            # Table structure
            pipeline_options.do_table_structure = True
            pipeline_options.table_structure_options = TableStructureOptions(
                do_cell_matching=True,
                mode=TableFormerMode.ACCURATE,
            )
            # Image generation (for enrichment + visual retrieval)
            pipeline_options.generate_page_images = True
            pipeline_options.generate_picture_images = True
            pipeline_options.generate_table_images = True
            # Feature enrichment
            pipeline_options.do_picture_classification = self.settings.docling_do_picture_classification
            pipeline_options.do_code_enrichment = self.settings.docling_do_code_enrichment
            pipeline_options.do_formula_enrichment = self.settings.docling_do_formula_enrichment
            # Timeout
            pipeline_options.document_timeout = self.settings.docling_document_timeout

            # Chart extraction (new in Docling 2.72+)
            try:
                pipeline_options.do_chart_extraction = self.settings.docling_do_chart_extraction
            except AttributeError:
                logger.debug("do_chart_extraction not available in this Docling version")

            # VLM picture/chart description — two modes:
            # 1. API mode: calls external OpenAI-compatible endpoint (vLLM, Ollama, OpenAI)
            # 2. Local mode: loads HuggingFace VLM in-process (SmolVLM-500M default)
            if self.settings.docling_do_picture_description:
                try:
                    pipeline_options.do_picture_description = True

                    if self.settings.docling_vlm_use_api:
                        # API mode — call external VLM service
                        from docling.datamodel.pipeline_options import PictureDescriptionApiOptions
                        pipeline_options.picture_description_options = PictureDescriptionApiOptions(
                            url=self.settings.docling_vlm_api_url,
                            params=dict(
                                model=self.settings.docling_vlm_api_model,
                                max_tokens=512,
                            ),
                            headers={"Authorization": f"Bearer {self.settings.docling_vlm_api_key}"}
                            if self.settings.docling_vlm_api_key else {},
                            prompt="Describe this image in detail, including any text, charts, diagrams, or visual elements.",
                        )
                        logger.info(
                            "Docling VLM picture description via API: %s (model: %s)",
                            self.settings.docling_vlm_api_url,
                            self.settings.docling_vlm_api_model,
                        )
                    else:
                        # Local mode — load VLM in-process
                        pipeline_options.picture_description_options = PictureDescriptionVlmOptions(
                            repo_id=self.settings.docling_vlm_model,
                            prompt="Describe this image in detail, including any text, charts, diagrams, or visual elements.",
                        )
                        logger.info("Docling VLM picture description (local): %s", self.settings.docling_vlm_model)
                except Exception as e:
                    logger.warning("Failed to configure VLM picture description: %s", e)

            # Build format options — PDF and IMAGE get the full ML pipeline;
            # Office/text formats use SimplePipeline (native parsing, no ML needed).
            format_opts = {
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }

            if has_multi_format:
                # IMAGE uses the same StandardPdfPipeline as PDF — gets OCR,
                # table structure, VLM picture description, etc.
                format_opts[InputFormat.IMAGE] = ImageFormatOption(
                    pipeline_options=pipeline_options,
                )
                # Office/markup formats — native parsing via SimplePipeline
                format_opts[InputFormat.DOCX] = WordFormatOption()
                format_opts[InputFormat.PPTX] = PowerpointFormatOption()
                format_opts[InputFormat.XLSX] = ExcelFormatOption()
                format_opts[InputFormat.HTML] = HTMLFormatOption()
                format_opts[InputFormat.MD] = MarkdownFormatOption()
                logger.info(
                    "Docling multi-format enabled: PDF, IMAGE, DOCX, PPTX, XLSX, HTML, MD"
                )

            converter = DocumentConverter(format_options=format_opts)
            with self._lock:
                self._models["docling"] = converter
                self._loaded["docling"] = True
                self._load_times["docling"] = time.time() - start
            logger.info("Docling loaded in %.1fs (OCR: RapidOCR PP-OCRv5 %s)", self._load_times["docling"], ocr_langs)
        except Exception as e:
            logger.error("Failed to load Docling: %s", e)
            self._loaded["docling"] = False
            raise

    def _build_rapidocr_options(self, RapidOcrOptions, ocr_langs: list[str]):
        """Build RapidOcrOptions, using PP-OCRv5 server ONNX models if available.

        Downloads PP-OCRv5 server ONNX models from marsena/paddleocr-onnx-models
        on HuggingFace. Falls back to default RapidOCR models if download fails.
        """
        try:
            from huggingface_hub import hf_hub_download

            # PP-OCRv5 server models (highest accuracy, ONNX format)
            det_path = hf_hub_download(
                repo_id="marsena/paddleocr-onnx-models",
                filename="PP-OCRv5_server_det_infer.onnx",
            )
            rec_path = hf_hub_download(
                repo_id="marsena/paddleocr-onnx-models",
                filename="PP-OCRv5_server_rec_infer.onnx",
            )
            # Text line orientation classifier
            cls_path = hf_hub_download(
                repo_id="marsena/paddleocr-onnx-models",
                filename="PP-LCNet_x1_0_textline_ori_infer.onnx",
            )

            logger.info("Using PP-OCRv5 server ONNX models for RapidOCR")
            return RapidOcrOptions(
                lang=ocr_langs,
                det_model_path=det_path,
                rec_model_path=rec_path,
                cls_model_path=cls_path,
                force_full_page_ocr=self.settings.force_full_page_ocr,
                bitmap_area_threshold=self.settings.bitmap_area_threshold,
            )

        except Exception as e:
            logger.warning(
                "Failed to download PP-OCRv5 models, using default RapidOCR models: %s", e
            )
            return RapidOcrOptions(
                lang=ocr_langs,
                force_full_page_ocr=self.settings.force_full_page_ocr,
                bitmap_area_threshold=self.settings.bitmap_area_threshold,
            )

    def _load_img2table(self) -> None:
        """Load img2table for borderless table extraction."""
        start = time.time()
        try:
            from img2table.document import Image as Img2TableImage  # noqa: F401

            logger.info("Loading img2table (OpenCV-based)")
            # img2table doesn't need a pre-loaded model; it uses OpenCV.
            # Store a marker to confirm the import succeeded.
            with self._lock:
                self._models["img2table"] = True
                self._loaded["img2table"] = True
                self._load_times["img2table"] = time.time() - start
            logger.info("img2table loaded in %.1fs", self._load_times["img2table"])
        except Exception as e:
            logger.error("Failed to load img2table: %s", e)
            self._loaded["img2table"] = False
            raise

    def _load_colsmol(self) -> None:
        """Load ColSmol-256M for visual page retrieval."""
        start = time.time()
        try:
            import torch
            from colpali_engine.models import ColIdefics3, ColIdefics3Processor

            logger.info("Loading ColSmol: %s", self.settings.colsmol_model)

            model = ColIdefics3.from_pretrained(
                self.settings.colsmol_model,
                dtype=torch.float32,
            ).eval()

            if self.settings.device != "cpu":
                model = model.to(self.settings.device)

            processor = ColIdefics3Processor.from_pretrained(
                self.settings.colsmol_model,
            )

            with self._lock:
                self._models["colsmol_model"] = model
                self._models["colsmol_processor"] = processor
                self._loaded["colsmol"] = True
                self._load_times["colsmol"] = time.time() - start
            logger.info("ColSmol loaded in %.1fs", self._load_times["colsmol"])
        except Exception as e:
            logger.error("Failed to load ColSmol: %s", e)
            self._loaded["colsmol"] = False
            raise

    # ========================================================================
    # Accessors
    # ========================================================================

    def get_bge_m3(self):
        """Get the BGE-M3 model."""
        return self._models.get("bge_m3")

    def get_reranker(self) -> tuple:
        """Get the reranker model and tokenizer."""
        return (
            self._models.get("reranker_model"),
            self._models.get("reranker_tokenizer"),
        )

    def get_docling(self):
        """Get the Docling DocumentConverter."""
        return self._models.get("docling")

    def get_img2table_available(self) -> bool:
        """Check if img2table is available."""
        return self._loaded.get("img2table", False)

    def get_colsmol(self) -> tuple:
        """Get ColSmol model and processor."""
        return (
            self._models.get("colsmol_model"),
            self._models.get("colsmol_processor"),
        )

