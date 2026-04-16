#!/usr/bin/env python3
"""
DocAI — Standalone demo app
Landing.ai-style two-pass document extraction.

  Pass 1 (POST /api/parse):   ABBYY OCR + VLM schema detection (concurrent)
  Pass 2 (POST /api/extract): LLM field extraction

Run:
    cd extract-app
    pip install -r requirements.txt
    uvicorn main:app --reload --port 7860
    open http://localhost:7860
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent

from dotenv import load_dotenv
load_dotenv(ROOT / ".env.local", override=True)

import httpx
try:
    import fitz  # pymupdf
    _FITZ_AVAILABLE = True
except ImportError:
    _FITZ_AVAILABLE = False

from fastapi import FastAPI, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("extract_app")

app = FastAPI(title="DocAI", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".pdf"}

MIME_MAP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "tiff": "image/tiff", "tif": "image/tiff", "bmp": "image/bmp", "webp": "image/webp",
    "pdf": "application/pdf",
}


# ── config ─────────────────────────────────────────────────────────────────────

def _cfg() -> dict:
    return {
        "base_url": os.getenv("OPENAI_COMPAT_BASE_URL", "https://qwen-test.westus3.inference.ml.azure.com/v1").rstrip("/"),
        "api_key":  os.getenv("OPENAI_COMPAT_API_KEY", ""),
        "model":    os.getenv("OPENAI_COMPAT_MODEL", "Qwen/Qwen3.5-9B"),
    }


# ── shared helpers ─────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    # Strip <think>...</think> blocks emitted by reasoning models
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw.strip())
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise


async def _llm_call(messages: list[dict], cfg: dict) -> str:
    payload = {
        "model":       cfg["model"],
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
        "messages":    messages,
    }
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(cfg["base_url"] + "/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ── Pass 1a: ABBYY OCR ────────────────────────────────────────────────────────

async def _run_abbyy(file_path: str) -> tuple[dict, str | None]:
    logger.info("Pass 1a — ABBYY OCR: %s", file_path)
    try:
        from src.inference.config import InferenceSettings
        from src.providers.ocr.abbyy import AbbyyVantageClient, AbbyyVantageAdapter

        settings = InferenceSettings()
        content = Path(file_path).read_bytes()

        async with AbbyyVantageClient.from_settings(settings) as client:
            raw_results = await client.process_document(content, Path(file_path).name)

        parsed: list = []
        plain_text_candidates: list[str] = []
        for item in raw_results:
            if isinstance(item, str):
                try:
                    decoded = json.loads(item)
                    parsed.extend(decoded if isinstance(decoded, list) else [decoded])
                except json.JSONDecodeError:
                    plain_text_candidates.append(item)
            elif isinstance(item, list):
                parsed.extend(item)
            else:
                parsed.append(item)

        plain_text = plain_text_candidates[0] if plain_text_candidates else None
        adapter = AbbyyVantageAdapter()
        abbyy = adapter.convert(parsed)
        elements = abbyy.get("elements", {})
        logger.info("ABBYY done — %d elements%s", len(elements), "  + plain-text" if plain_text else "")
        return elements, plain_text

    except Exception as e:
        logger.warning("ABBYY failed: %s", e)
        return {}, None


# ── Pass 1b: VLM schema ────────────────────────────────────────────────────────

_VLM_SCHEMA_PROMPT = """\
You are a document layout analyst. Carefully examine EVERY part of this document image.

COORDINATE SYSTEM — read carefully before writing any bbox:
  (x0=0.0, y0=0.0) = TOP-LEFT corner of the image
  (x1=1.0, y1=1.0) = BOTTOM-RIGHT corner of the image
  x values → horizontal fraction of image WIDTH  (left=0.0, right=1.0)
  y values → vertical fraction of image HEIGHT   (top=0.0, bottom=1.0)
  Example: a region in the top-right quarter has roughly x0=0.5, y0=0.0, x1=1.0, y1=0.25

BBOX RULES — tight, not padded:
  - y0 = top edge of the FIRST line of text/content in the region
  - y1 = bottom edge of the LAST line of text/content in the region
  - x0 = left edge of the actual content (not the page margin)
  - x1 = right edge of the actual content (not the full page width)
  Do NOT pad to page edges. Each bbox must hug its content.

Return ONLY valid JSON — no markdown fences, no explanation:
{
  "document_type": "<snake_case: invoice | purchase_order | bank_statement | receipt | delivery_note | contract | etc.>",
  "fields": [
    {
      "name": "<snake_case_field_name>",
      "description": "<concise description of what value this field contains>"
    }
  ],
  "has_line_items": true or false,
  "line_item_columns": ["<col1>", "<col2>", ...] or null,
  "layout_chunks": [
    {
      "type": "<header|vendor_info|buyer_info|line_items_table|totals|payment_info|notes|signature|footer|other>",
      "label": "<short human label e.g. 'Invoice header' or 'Vendor address'>",
      "fields": ["<field_name_from_fields_list>", ...],
      "text": "<key values visible in this region only, \\n for line breaks — keep brief>",
      "bbox": {"x0": <0.0-1.0>, "y0": <0.0-1.0>, "x1": <0.0-1.0>, "y1": <0.0-1.0>}
    }
  ]
}

LAYOUT CHUNK RULES:
1. Scan the document TOP TO BOTTOM. Every visible region must be covered — logos, headers,
   address blocks, tables, totals, payment info, signatures, footers, everything.
   Do NOT skip any part of the document. There must be NO uncovered area.
2. Chunks must NOT overlap — each pixel of the document belongs to exactly one chunk.
3. Adjacent regions with different semantic roles (e.g. vendor address vs buyer address)
   must be separate chunks even if they sit side by side.
4. The line items table (if present) must be its own chunk with type "line_items_table".
5. Every field in "fields" must appear in exactly one chunk's "fields" array.

FIELD RULES:
- List EVERY extractable scalar field visible in the document (one value per field).
- NEVER put individual line item rows in fields. Line item columns go in line_item_columns only.
- snake_case for all names.
"""


async def _run_vlm_schema(image_path: str, cfg: dict) -> dict:
    logger.info("Pass 1b — VLM schema: %s", cfg["model"])
    img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    suffix = Path(image_path).suffix.lower().lstrip(".")
    mime = MIME_MAP.get(suffix, "image/jpeg")

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
        {"type": "text", "text": _VLM_SCHEMA_PROMPT},
    ]}]

    raw = await _llm_call(messages, cfg)
    logger.info("VLM raw (first 600):\n%s", raw[:600])

    try:
        schema = _parse_json(raw)
    except Exception as e:
        logger.error("VLM JSON parse failed: %s", e)
        return {"document_type": "unknown", "fields": [], "has_line_items": False,
                "line_item_columns": None, "layout_chunks": []}

    # Drop line-item placeholder fields (e.g. line_item_1, row_2)
    pat = re.compile(r"^(line_item|item|row|entry)s?_?\d+", re.IGNORECASE)
    schema["fields"] = [
        f for f in schema.get("fields", [])
        if not pat.match(f["name"] if isinstance(f, dict) else f)
    ]
    logger.info(
        "VLM schema: type=%s  fields=%d  chunks=%d",
        schema.get("document_type"), len(schema.get("fields", [])), len(schema.get("layout_chunks", [])),
    )
    return schema


# ── Pass 2: LLM extraction ────────────────────────────────────────────────────

_INCLUDE_TYPES = {
    "title", "section_header", "paragraph", "key_value", "form_field",
    "list_item", "footnote", "caption", "table", "checkbox",
}
_Y_BAND = 0.01


def _build_abbyy_context(elements: dict) -> str:
    def _key(e: dict) -> tuple:
        b = e.get("bbox_normalized") or {}
        return (round(b.get("top", 0.0) / _Y_BAND) * _Y_BAND, b.get("left", 0.0))

    parts: list[str] = []
    for el in sorted((e for e in elements.values() if not e.get("skip_indexing")), key=_key):
        etype = el.get("type", "paragraph")
        if etype not in _INCLUDE_TYPES:
            continue
        content = el.get("content", "").strip()
        if not content:
            continue
        bbox = el.get("bbox_normalized") or {}
        conf = el.get("metadata", {}).get("ocr_confidence")
        conf_str = f"conf:{conf:.2f}" if conf is not None else "conf:?"
        tag = f"{el['element_id']} | x:{bbox.get('left', 0):.2f} y:{bbox.get('top', 0):.2f} | {conf_str}"
        prefix = {"title": "# ", "section_header": "## "}.get(etype, "")
        parts.append(f"[{tag}] {prefix}{content}")

    return "\n\n".join(parts)


def _build_extraction_prompt(schema: dict) -> str:
    doc_type  = schema.get("document_type", "unknown")
    fields    = schema.get("fields", [])
    has_items = schema.get("has_line_items", False)
    item_cols = schema.get("line_item_columns") or []
    chunks    = schema.get("layout_chunks", [])

    if chunks:
        chunk_lines = []
        for ch in chunks:
            line = f'  [{ch.get("type", "other")}] {ch.get("label", "")} → fields: {ch.get("fields", [])}'
            if ch.get("text", "").strip():
                indented = "\n".join(f"    {ln}" for ln in ch["text"].splitlines())
                line += f"\n{indented}"
            chunk_lines.append(line)
        doc_map = "Document layout (from visual analysis):\n" + "\n".join(chunk_lines) + "\n\n"
    else:
        doc_map = ""

    def _fname(f: dict | str) -> str:
        return f["name"] if isinstance(f, dict) else f

    field_lines = "\n".join(
        f'    "{_fname(f)}": {{"value": <value or null>, "section": "<chunk label>"}}'
        for f in fields
    )

    if has_items and item_cols:
        cols_ex = ", ".join(f'"{c}": <value>' for c in item_cols)
        items_blk = f'  "line_items": [\n    {{{cols_ex}}},\n    ...\n  ]'
    else:
        items_blk = '  "line_items": []'

    return f"""\
You are extracting structured data from a {doc_type}.

Use BOTH sources — ABBYY OCR text (below) AND VLM chunk text (layout map above):

{doc_map}Return ONLY valid JSON — no markdown fences, no explanation:
{{
  "fields": {{
{field_lines}
  }},
{items_blk}
}}

Rules:
- Extract the VALUE only, not its label  (e.g. "INV-042" not "Invoice No: INV-042")
- Numbers as numbers, not strings  (e.g. 1234.56 not "1234.56")
- Preserve original formatting for dates, codes, identifiers
- null if a field is genuinely absent — still include the field key
- section: the chunk label from the layout map that contains this field
- line_items: one object per row — include EVERY row, do not truncate
"""


async def _run_llm_extraction(schema: dict, elements: dict, cfg: dict, plain_text: str | None = None) -> dict:
    # Pick the best text source
    if plain_text and plain_text.strip():
        context = plain_text
        ctx_source = "abbyy_plain_text"
    elif elements:
        context = _build_abbyy_context(elements)
        ctx_source = "abbyy_elements"
    else:
        # Fall back to VLM chunk text (ABBYY disabled)
        chunks = schema.get("layout_chunks", [])
        context = "\n\n".join(ch.get("text", "") for ch in chunks if ch.get("text", "").strip())
        ctx_source = "vlm_chunks"

    if not context.strip():
        return {"document_type": schema.get("document_type", "unknown"),
                "fields": {}, "line_items": [], "metadata": {"error": "empty_context"}}

    logger.info("Pass 2 — LLM extraction: %d fields  %d chars  [%s]",
                len(schema.get("fields", [])), len(context), ctx_source)

    system_prompt = _build_extraction_prompt(schema)
    raw = await _llm_call(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"Document content:\n\n{context}"},
        ],
        cfg=cfg,
    )
    logger.info("LLM raw (%d chars):\n%s", len(raw), raw[:1500])

    try:
        llm_out = _parse_json(raw)
    except Exception as e:
        raise ValueError(f"LLM returned unparseable JSON: {e}. Raw: {raw[:300]}") from e

    fields_out: dict = {}
    for fname, fdata in llm_out.get("fields", {}).items():
        if isinstance(fdata, dict) and "value" in fdata:
            entry: dict = {"value": fdata["value"]}
            if fdata.get("section"):
                entry["section"] = fdata["section"]
        else:
            entry = {"value": fdata}
        fields_out[fname] = entry

    items_out = [
        {k: v for k, v in item.items() if k != "source_element_id"}
        for item in llm_out.get("line_items", [])
        if isinstance(item, dict)
    ]

    return {
        "document_type": schema.get("document_type", "unknown"),
        "fields":        fields_out,
        "line_items":    items_out,
        "metadata": {
            "model":        cfg["model"],
            "ocr_source":   ctx_source,
            "field_count":  len(fields_out),
            "item_count":   len(items_out),
        },
    }


# ── VLM field-level bbox pass ─────────────────────────────────────────────────

def _build_field_view_prompt(schema: dict) -> str:
    """Like _build_extraction_prompt but requests bbox + confidence per field from the VLM."""
    doc_type  = schema.get("document_type", "unknown")
    fields    = schema.get("fields", [])
    has_items = schema.get("has_line_items", False)
    item_cols = schema.get("line_item_columns") or []
    chunks    = schema.get("layout_chunks", [])

    # Build chunk→fields reverse map for spatial hints
    field_to_chunk: dict[str, dict] = {}
    for ch in chunks:
        for fn in ch.get("fields", []):
            field_to_chunk[fn] = ch

    if chunks:
        chunk_lines = []
        for ch in chunks:
            bb = ch.get("bbox") or {}
            region = (f"region: left={bb.get('x0',0):.2f} top={bb.get('y0',0):.2f} "
                      f"right={bb.get('x1',1):.2f} bottom={bb.get('y1',1):.2f}")
            line = (f'  [{ch.get("type","other")}] {ch.get("label","")} '
                    f'[{region}] → fields: {ch.get("fields",[])}')
            if ch.get("text", "").strip():
                indented = "\n".join(f"    {ln}" for ln in ch["text"].splitlines())
                line += f"\n{indented}"
            chunk_lines.append(line)
        doc_map = "Document layout — each chunk has a [region:] bounding box showing where it sits on the page:\n" + "\n".join(chunk_lines) + "\n\n"
    else:
        doc_map = ""

    def _fname(f: dict | str) -> str:
        return f["name"] if isinstance(f, dict) else f

    # Per-field hint: include the parent chunk's region so the VLM knows where to look
    def _field_hint(f: dict | str) -> str:
        name = _fname(f)
        ch = field_to_chunk.get(name)
        if ch and ch.get("bbox"):
            bb = ch["bbox"]
            hint = (f" /* look in region left={bb.get('x0',0):.2f} top={bb.get('y0',0):.2f} "
                    f"right={bb.get('x1',1):.2f} bottom={bb.get('y1',1):.2f} */")
        else:
            hint = ""
        return (f'    "{name}": {{"value": <value or null>, '
                f'"bbox": {{"left":<0-1>,"top":<0-1>,"right":<0-1>,"bottom":<0-1>}}, '
                f'"confidence": <0-1>, "section": "<chunk label>"}}{hint}')

    field_lines = "\n".join(_field_hint(f) for f in fields)

    if has_items and item_cols:
        cols_ex = ", ".join(
            f'"{c}": {{"value": <value>, "bbox": {{"left":<0-1>,"top":<0-1>,"right":<0-1>,"bottom":<0-1>}}, "confidence": <0-1>}}'
            for c in item_cols
        )
        items_blk = f'  "line_items": [\n    {{{cols_ex}}},\n    ...\n  ]'
    else:
        items_blk = '  "line_items": []'

    return f"""\
You are extracting structured data from a {doc_type}. You have the document image AND OCR text.

COORDINATE SYSTEM — read carefully before writing any bbox:
  (left=0.0, top=0.0) = TOP-LEFT corner of the image
  (right=1.0, bottom=1.0) = BOTTOM-RIGHT corner of the image
  left/right → horizontal fraction of image WIDTH   (left edge=0.0, right edge=1.0)
  top/bottom → vertical fraction of image HEIGHT    (top edge=0.0, bottom edge=1.0)
  Example: a value in the top-right quarter is roughly left=0.5 top=0.0 right=1.0 bottom=0.25

BBOX RULES — tight around the VALUE text only:
  - top    = top edge of the value text (not the field label)
  - bottom = bottom edge of the value text
  - left   = left edge of the value text
  - right  = right edge of the value text
  Do NOT include the field label in the bbox. Do NOT pad to page edges.
  Each chunk's [region:] tag tells you where to look — the value bbox must fall inside that region.

{doc_map}Return ONLY valid JSON — no markdown fences, no explanation:
{{
  "fields": {{
{field_lines}
  }},
{items_blk}
}}

Rules:
- Extract the VALUE only, not its label  (e.g. "INV-042" not "Invoice No: INV-042")
- Numbers as numbers, not strings  (e.g. 1234.56 not "1234.56")
- Preserve original formatting for dates, codes, identifiers
- null if a field is genuinely absent — still include the field key
- Use the /* look in region */ comment as your search window for each field
- line_items: one object per row — include EVERY row, do not truncate
"""


async def _run_vlm_field_bboxes(image_b64: str, schema: dict, context: str, cfg: dict) -> list[dict]:
    """Send image + OCR context + schema to VLM; returns fields with values AND bboxes."""
    prompt = _build_field_view_prompt(schema)
    logger.info("VLM field bbox pass — doc_type=%s  fields=%d  ctx_chars=%d",
                schema.get("document_type"), len(schema.get("fields", [])), len(context))

    if "," in image_b64:
        header, raw_b64 = image_b64.split(",", 1)
        mime = header.split(":")[1].split(";")[0] if ":" in header else "image/jpeg"
    else:
        raw_b64 = image_b64
        mime = "image/jpeg"

    # Combine prompt + OCR context into a single text part
    full_text = prompt + (f"\n\nDocument content:\n\n{context}" if context.strip() else "")

    messages = [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{raw_b64}"}},
        {"type": "text", "text": full_text},
    ]}]

    def _norm_bb(bb: dict) -> dict:
        return {
            "left":   max(0.0, min(1.0, float(bb.get("left",   0)))),
            "top":    max(0.0, min(1.0, float(bb.get("top",    0)))),
            "right":  max(0.0, min(1.0, float(bb.get("right",  1)))),
            "bottom": max(0.0, min(1.0, float(bb.get("bottom", 1)))),
        }

    try:
        raw    = await _llm_call(messages, cfg)
        parsed = _parse_json(raw)
        result = []

        # Scalar fields — response is a dict: {field_name: {value, bbox, confidence, section}}
        fields_out = parsed.get("fields", {})
        if isinstance(fields_out, dict):
            for fname, fdata in fields_out.items():
                if isinstance(fdata, dict):
                    bb = fdata.get("bbox", {})
                    val = fdata.get("value")
                    result.append({
                        "name":         fname,
                        "value":        str(val) if val is not None else "",
                        "bbox":         _norm_bb(bb),
                        "confidence":   float(fdata.get("confidence", 0.8)),
                        "line_item_id": -1,
                    })

        # Line items — each row is a dict of col → {value, bbox, confidence}
        for row_idx, row in enumerate(parsed.get("line_items", [])):
            if not isinstance(row, dict):
                continue
            for col, cell in row.items():
                if isinstance(cell, dict):
                    bb = cell.get("bbox", {})
                    val = cell.get("value")
                    result.append({
                        "name":         col,
                        "value":        str(val) if val is not None else "",
                        "bbox":         _norm_bb(bb),
                        "confidence":   float(cell.get("confidence", 0.8)),
                        "line_item_id": row_idx,
                    })

        logger.info("VLM field bbox: %d fields + line-item cells returned", len(result))
        return result
    except Exception as e:
        logger.warning("VLM field bbox pass failed (returning empty): %s", e)
        return []


# ── API models ─────────────────────────────────────────────────────────────────

class ParseResponse(BaseModel):
    elements:         dict[str, Any]
    abbyy_plain_text: str | None
    vlm_schema:       dict[str, Any]
    image_b64:        str   # data URL — echoed back for the viewer
    timings:          dict[str, float]  # pass1_ms

class ExtractRequest(BaseModel):
    elements:         dict[str, Any]       = Field(default_factory=dict)
    abbyy_plain_text: str | None           = None
    vlm_schema:       dict[str, Any]

class ExtractResponse(BaseModel):
    document_type: str
    fields:        dict[str, Any]
    line_items:    list[dict[str, Any]]
    metadata:      dict[str, Any]

class FieldViewRequest(BaseModel):
    elements:         dict[str, Any] = Field(default_factory=dict)
    abbyy_plain_text: str | None     = None
    vlm_schema:       dict[str, Any]
    image_b64:        str  # data URL — needed for VLM vision call

class FieldViewResponse(BaseModel):
    document_type: str
    fields:        dict[str, Any]
    line_items:    list[dict[str, Any]]
    metadata:      dict[str, Any]
    field_bboxes:  list[dict[str, Any]]

class PdfPagesResponse(BaseModel):
    page_count: int
    pages:      list[dict[str, Any]]


DIVA_API_URL = "https://diva-staging-endpoint-a0cyajgccrfpe6ef.a03.azurefd.net/api/v1/extract"
DIVA_API_KEY = os.getenv("DIVA_API_KEY", "")


class DivaCompareRequest(BaseModel):
    image_b64: str  # full data URL: data:image/jpeg;base64,...


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/config")
async def get_config():
    """Serve non-sensitive frontend config (API keys for GPT/Gemini comparison)."""
    return {
        "gpt_endpoint":   os.getenv("GPT_ENDPOINT", ""),
        "gpt_api_key":    os.getenv("GPT_API_KEY", ""),
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "gemini_model":   os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
    }


@app.post("/api/pdf-pages", response_model=PdfPagesResponse)
async def pdf_pages(file: UploadFile):
    """Render PDF thumbnails for page selection."""
    if not _FITZ_AVAILABLE:
        raise HTTPException(status_code=501, detail="pymupdf not installed — run: pip install pymupdf")
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for i, page in enumerate(doc):
            mat = fitz.Matrix(0.3, 0.3)
            pix = page.get_pixmap(matrix=mat)
            thumb_b64 = base64.b64encode(pix.tobytes("jpeg")).decode()
            pages.append({"page_num": i + 1, "thumbnail": f"data:image/jpeg;base64,{thumb_b64}"})
        doc.close()
        logger.info("PDF pages: rendered %d thumbnails", len(pages))
        return PdfPagesResponse(page_count=len(pages), pages=pages)
    except Exception as e:
        logger.error("PDF thumbnail rendering failed: %s", e, exc_info=True)
        raise HTTPException(status_code=422, detail=f"Could not render PDF: {e}")


@app.post("/api/parse", response_model=ParseResponse)
async def parse_document(file: UploadFile, page: int = Query(default=1, ge=1)):
    """Pass 1: ABBYY OCR + VLM schema detection (concurrent)."""
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    suffix = Path(file.filename or "doc.jpg").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {suffix}")

    # PDF → render the requested page to PNG
    if suffix == ".pdf":
        if not _FITZ_AVAILABLE:
            raise HTTPException(status_code=501, detail="pymupdf not installed — run: pip install pymupdf")
        try:
            doc = fitz.open(stream=image_bytes, filetype="pdf")
            if page > len(doc):
                raise HTTPException(status_code=422, detail=f"Page {page} exceeds PDF length ({len(doc)})")
            pdf_page = doc[page - 1]
            mat = fitz.Matrix(150 / 72, 150 / 72)  # 150 DPI
            pix = pdf_page.get_pixmap(matrix=mat)
            image_bytes = pix.tobytes("png")
            doc.close()
            suffix = ".png"
            logger.info("PDF page %d rendered to PNG (%d bytes)", page, len(image_bytes))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not render PDF page {page}: {e}")

    cfg       = _cfg()
    use_abbyy = os.getenv("ABBYY_ENABLED", "false").lower() == "true"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(image_bytes)
        tmp_path = f.name

    t0 = time.perf_counter()
    try:
        if use_abbyy:
            (elements, plain_text), vlm_schema = await asyncio.gather(
                _run_abbyy(tmp_path),
                _run_vlm_schema(tmp_path, cfg),
            )
            elements = elements or {}
        else:
            logger.warning("ABBYY disabled — VLM schema only; LLM will use VLM chunk text")
            vlm_schema = await _run_vlm_schema(tmp_path, cfg)
            elements   = {}
            plain_text = None
    finally:
        os.unlink(tmp_path)
    pass1_ms = round((time.perf_counter() - t0) * 1000)

    mime      = MIME_MAP.get(suffix.lstrip("."), "image/jpeg")
    image_b64 = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"

    return ParseResponse(
        elements=elements,
        abbyy_plain_text=plain_text,
        vlm_schema=vlm_schema,
        image_b64=image_b64,
        timings={"pass1_ms": pass1_ms},
    )


@app.post("/api/extract", response_model=ExtractResponse)
async def extract_fields(body: ExtractRequest):
    """Pass 2: LLM field extraction using the (optionally edited) schema."""
    cfg = _cfg()
    t0  = time.perf_counter()
    try:
        result = await _run_llm_extraction(
            schema=body.vlm_schema,
            elements=body.elements,
            cfg=cfg,
            plain_text=body.abbyy_plain_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Extraction failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")

    result["metadata"]["pass2_ms"] = round((time.perf_counter() - t0) * 1000)
    return ExtractResponse(**result)


@app.post("/api/extract-field-view", response_model=FieldViewResponse)
async def extract_field_view(body: FieldViewRequest):
    """VLM-only field extraction — same context as /api/extract but sent to VLM with bbox output."""
    cfg = _cfg()
    t0  = time.perf_counter()

    # Build OCR context exactly the same way _run_llm_extraction does
    schema = body.vlm_schema
    if body.abbyy_plain_text and body.abbyy_plain_text.strip():
        context    = body.abbyy_plain_text
        ctx_source = "abbyy_plain_text"
    elif body.elements:
        context    = _build_abbyy_context(body.elements)
        ctx_source = "abbyy_elements"
    else:
        chunks     = schema.get("layout_chunks", [])
        context    = "\n\n".join(ch.get("text", "") for ch in chunks if ch.get("text", "").strip())
        ctx_source = "vlm_chunks"

    logger.info("Field view pass — %d fields  %d chars  [%s]",
                len(schema.get("fields", [])), len(context), ctx_source)

    try:
        field_bboxes = await _run_vlm_field_bboxes(
            image_b64=body.image_b64,
            schema=schema,
            context=context,
            cfg=cfg,
        )
    except Exception as e:
        logger.error("Field bbox pass failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Field bbox pass failed: {e}")

    bbox_ms = round((time.perf_counter() - t0) * 1000)

    # Build the fields/line_items response from the flat bbox list
    fields_out: dict = {}
    line_items_out: list = []
    row_buffers: dict[int, dict] = {}

    for fb in field_bboxes:
        lid = fb.get("line_item_id", -1)
        if lid == -1:
            fields_out[fb["name"]] = {
                "value":      fb["value"],
                "bbox":       fb["bbox"],
                "confidence": fb["confidence"],
            }
        else:
            if lid not in row_buffers:
                row_buffers[lid] = {}
            row_buffers[lid][fb["name"]] = {
                "value":      fb["value"],
                "bbox":       fb["bbox"],
                "confidence": fb["confidence"],
            }

    for i in sorted(row_buffers):
        line_items_out.append(row_buffers[i])

    return FieldViewResponse(
        document_type=schema.get("document_type", "unknown"),
        fields=fields_out,
        line_items=line_items_out,
        metadata={
            "model":       cfg["model"],
            "ocr_source":  ctx_source,
            "field_count": len(fields_out),
            "item_count":  len(line_items_out),
            "bbox_ms":     bbox_ms,
        },
        field_bboxes=field_bboxes,
    )


@app.post("/api/compare-diva")
async def compare_with_diva(body: DivaCompareRequest):
    """Call DIVA API with the same image and return its response for side-by-side comparison."""
    logger.info("Calling DIVA API (%s)", DIVA_API_URL)
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                DIVA_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Ocp-Apim-Subscription-Key": DIVA_API_KEY,
                },
                json={"file": body.image_b64, "autodetect": True, "debug": True},
            )
            resp.raise_for_status()
        logger.info("DIVA response: %d chars", len(resp.text))
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("DIVA API error %s: %s", e.response.status_code, e.response.text[:300])
        raise HTTPException(
            status_code=502,
            detail=f"DIVA API returned {e.response.status_code}: {e.response.text[:200]}",
        )
    except Exception as e:
        logger.error("DIVA API failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"DIVA API failed: {e}")
