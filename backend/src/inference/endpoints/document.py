"""Document processing endpoint - Docling parsing with element enrichment.

Docling handles OCR (RapidOCR PP-OCRv5) and image/chart description (PP-DocBee VLM)
internally. Post-processing enrichment is limited to img2table for borderless tables.

enriched.json v2.0:
- Elements keyed by page-index IDs (e.g., "9-T1", "10-P3")
- Normalized bboxes (0-1 range)
- Charspan from ProvenanceItem
- Quality scores from ConversionResult
- Hierarchy (parent/children refs)
- skip_indexing for non-content elements
- Table cells with row_section, fillable
- PictureMeta with description, classification, caption
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import tempfile
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from docling_core.types.doc import (
    TextItem,
    SectionHeaderItem,
    ListItem,
    TableItem,
    PictureItem,
)

# Types available in docling-core >=2.15 (we require >=2.60)
try:
    from docling_core.types.doc import TitleItem
except ImportError:
    TitleItem = None
try:
    from docling_core.types.doc import CodeItem
except ImportError:
    CodeItem = None
try:
    from docling_core.types.doc import FormulaItem
except ImportError:
    FormulaItem = None
try:
    from docling_core.types.doc import KeyValueItem
except ImportError:
    KeyValueItem = None
try:
    from docling_core.types.doc import FormItem
except ImportError:
    FormItem = None

# Newer types (docling-core >=2.40+)
try:
    from docling_core.types.doc.labels import DocItemLabel
except ImportError:
    DocItemLabel = None

from src.inference.schemas import ProcessedDocumentResponse

logger = logging.getLogger(__name__)
router = APIRouter()

# Element ID prefix map
_LABEL_PREFIX = {
    "paragraph": "P",
    "text": "P",
    "title": "H",
    "section_header": "H",
    "heading": "H",
    "table": "T",
    "figure": "F",
    "chart": "F",
    "image": "F",
    "equation": "E",
    "code": "C",
    "key_value": "K",
    "form_field": "K",
    "checkbox": "X",
    "list_item": "LI",
    "caption": "N",
    "footnote": "N",
    "reference": "N",
    "handwritten": "HW",
    "grading_scale": "GS",
    "document_index": "DI",
    "page_header": "PH",
    "page_footer": "PF",
}

# Element types that should be skipped during RAG indexing
_SKIP_INDEXING_TYPES = {"page_header", "page_footer", "document_index"}


def _generate_element_id(
    page: int, label: str, counters: dict[str, dict[str, int]]
) -> str:
    """Generate a page-index element ID like '9-T1', '10-P3'."""
    prefix = _LABEL_PREFIX.get(label, "P")
    page_key = str(page)
    if page_key not in counters:
        counters[page_key] = {}
    page_counters = counters[page_key]
    count = page_counters.get(prefix, 0) + 1
    page_counters[prefix] = count
    return f"{page}-{prefix}{count}"


def _normalize_bbox(
    bbox_dict: dict, page_width: float, page_height: float
) -> dict | None:
    """Normalize absolute-pixel bbox to 0-1 range."""
    if not bbox_dict or page_width <= 0 or page_height <= 0:
        return None
    return {
        "left": round(bbox_dict.get("x0", 0) / page_width, 6),
        "top": round(bbox_dict.get("y0", 0) / page_height, 6),
        "right": round(bbox_dict.get("x1", 0) / page_width, 6),
        "bottom": round(bbox_dict.get("y1", 0) / page_height, 6),
    }


@router.post("/process-document", response_model=ProcessedDocumentResponse)
async def process_document(
    request: Request,
    file: UploadFile = File(...),
) -> ProcessedDocumentResponse:
    """Process a document using Docling."""
    model_manager = request.app.state.model_manager
    converter = model_manager.get_docling()

    if converter is None:
        raise HTTPException(status_code=503, detail="Docling converter not loaded")

    content = await file.read()
    filename = file.filename or "document"
    suffix = Path(filename).suffix

    # Write to temp file for Docling
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        loop = asyncio.get_event_loop()

        def _process():
            result = converter.convert(temp_path)
            doc = result.document

            raw_count = 0
            skipped_count = 0
            skipped_types = {}
            converted_types = {}
            # v2: elements keyed by element_id
            elements = {}
            tables = {}
            images = {}

            # Extract page dimensions first (needed for bbox normalization)
            page_dimensions = {}
            if hasattr(doc, "pages") and doc.pages:
                for page_no, page_obj in doc.pages.items():
                    size = getattr(page_obj, "size", None)
                    if size:
                        w = getattr(size, "width", 0) or 0
                        h = getattr(size, "height", 0) or 0
                    else:
                        w = getattr(page_obj, "width", 0) or 0
                        h = getattr(page_obj, "height", 0) or 0
                    if w and h:
                        page_dimensions[str(page_no)] = {
                            "width": float(w),
                            "height": float(h),
                        }

            # Extract quality scores from ConversionResult
            quality = _extract_quality(result)

            # Extract conversion status and timings
            conversion_status = "unknown"
            if hasattr(result, "status"):
                s = result.status
                conversion_status = s.value if hasattr(s, "value") else str(s)

            timings = {}
            if hasattr(result, "timings") and result.timings:
                t = result.timings
                for attr in dir(t):
                    if not attr.startswith("_"):
                        val = getattr(t, attr, None)
                        if isinstance(val, (int, float)):
                            timings[attr] = val

            # Element ID counters per page
            id_counters: dict[str, dict[str, int]] = {}

            # Track heading hierarchy for section context
            heading_stack: list[dict] = []

            # iterate_items() returns (item, level) tuples
            for item, level in doc.iterate_items():
                raw_count += 1
                tn = type(item).__name__
                element = _convert_item_v2(
                    item, doc, level, page_dimensions,
                    id_counters, heading_stack,
                )
                if element:
                    eid = element["element_id"]
                    elements[eid] = element
                    et = element.get("type")
                    converted_types[et] = converted_types.get(et, 0) + 1
                    if et == "table":
                        tables[eid] = element
                    elif et in ("figure", "chart"):
                        images[eid] = element
                else:
                    skipped_count += 1
                    skipped_types[tn] = skipped_types.get(tn, 0) + 1

            logger.info(
                "Docling: %s — raw=%d, converted=%d (%s), skipped=%d (%s)",
                filename, raw_count, len(elements), converted_types,
                skipped_count, skipped_types,
            )

            # Fallback: if iterate_items produced no elements, use export_to_markdown
            md_text = ""
            if not elements:
                try:
                    md_text = doc.export_to_markdown()
                except Exception:
                    pass

                if md_text.strip():
                    logger.info(
                        "No elements from iterate_items, using markdown fallback (%d chars)",
                        len(md_text),
                    )
                    fallback_id = "1-P1"
                    elements = {
                        fallback_id: {
                            "element_id": fallback_id,
                            "type": "paragraph",
                            "label": "paragraph",
                            "content": md_text,
                            "page_number": 1,
                            "bbox": None,
                            "bbox_normalized": None,
                            "metadata": {},
                        }
                    }

            # Enrich elements (img2table for borderless tables only)
            elements = _enrich_elements_v2(elements, model_manager)

            # Build text from enriched elements
            text_parts = []
            for eid, element in elements.items():
                etype = element.get("type", "paragraph")
                elem_content = element.get("content", "")

                if element.get("skip_indexing"):
                    continue

                if etype in ("figure", "chart"):
                    if elem_content:
                        text_parts.append(f"[{etype.title()}: {elem_content}]")
                elif etype == "equation":
                    if elem_content:
                        text_parts.append(f"[Equation: {elem_content}]")
                elif etype == "checkbox":
                    checked = element.get("metadata", {}).get("checked", False)
                    mark = "[x]" if checked else "[ ]"
                    text_parts.append(f"{mark} {elem_content}")
                elif etype == "footnote":
                    if elem_content:
                        text_parts.append(f"[Footnote: {elem_content}]")
                elif elem_content:
                    text_parts.append(elem_content)

            # Last-resort fallback
            if not text_parts and md_text.strip():
                text_parts = [md_text]

            # Page count
            page_count = 1
            if hasattr(doc, "pages") and doc.pages:
                page_count = len(doc.pages)
            elif elements:
                page_count = max(
                    (e.get("page_number", 1) for e in elements.values()),
                    default=1,
                )

            # Per-page quality
            pages_quality = {}
            if quality.get("page_scores"):
                pages_quality = quality.pop("page_scores")

            metadata = {}
            if hasattr(doc, "name"):
                metadata["title"] = doc.name

            return {
                "version": "2.0",
                "text": "\n\n".join(text_parts),
                "elements": elements,
                "tables": tables,
                "images": images,
                "page_count": page_count,
                "page_dimensions": page_dimensions,
                "pages": pages_quality,
                "quality": quality,
                "conversion_status": conversion_status,
                "timings": timings,
                "metadata": metadata,
            }

        result = await loop.run_in_executor(None, _process)
        return ProcessedDocumentResponse(**result)

    finally:
        os.unlink(temp_path)


def _extract_quality(result) -> dict:
    """Extract quality/confidence scores from ConversionResult."""
    quality = {}
    try:
        conf = getattr(result, "confidence", None)
        if conf is None:
            return quality
        for attr in (
            "layout_score", "ocr_score", "table_score",
            "parse_score", "mean_grade", "low_grade",
        ):
            val = getattr(conf, attr, None)
            if val is not None:
                quality[attr] = float(val) if isinstance(val, (int, float)) else val

        # Per-page confidence
        page_scores = {}
        pages_attr = getattr(conf, "pages", None)
        if pages_attr and isinstance(pages_attr, dict):
            for pg, pg_conf in pages_attr.items():
                pg_data = {}
                for attr in ("layout_score", "ocr_score", "table_score"):
                    val = getattr(pg_conf, attr, None)
                    if val is not None:
                        pg_data[attr] = float(val)
                if pg_data:
                    page_scores[str(pg)] = pg_data
        if page_scores:
            quality["page_scores"] = page_scores
    except Exception:
        pass
    return quality


def _get_item_label(item) -> str | None:
    """Get the DocItemLabel string from an item, if available."""
    if DocItemLabel is None:
        return None
    label = getattr(item, "label", None)
    if label is None:
        return None
    # DocItemLabel enum → string value
    if hasattr(label, "value"):
        return label.value
    return str(label)


def _extract_charspan(item) -> list[int] | None:
    """Extract character span from ProvenanceItem.charspan."""
    try:
        if hasattr(item, "prov") and item.prov:
            prov = item.prov[0] if isinstance(item.prov, list) else item.prov
            charspan = getattr(prov, "charspan", None)
            if charspan is not None:
                # charspan is typically a tuple/list of (start, end)
                if hasattr(charspan, "__iter__"):
                    cs = list(charspan)
                    if len(cs) == 2:
                        return [int(cs[0]), int(cs[1])]
                elif isinstance(charspan, (int, float)):
                    return [int(charspan), int(charspan)]
    except Exception:
        pass
    return None


def _extract_hierarchy(item, doc) -> dict:
    """Extract parent/children references from DocItem."""
    hierarchy = {}
    try:
        # Parent reference
        parent = getattr(item, "parent", None)
        if parent is not None:
            parent_ref = getattr(parent, "cref", None) or getattr(parent, "$ref", None)
            if parent_ref:
                hierarchy["parent"] = str(parent_ref)

        # Children references
        children = getattr(item, "children", None)
        if children:
            child_refs = []
            for child in children:
                child_ref = getattr(child, "cref", None) or getattr(child, "$ref", None)
                if child_ref:
                    child_refs.append(str(child_ref))
            if child_refs:
                hierarchy["children"] = child_refs
    except Exception:
        pass
    return hierarchy


def _convert_item_v2(
    item,
    doc,
    level: int,
    page_dimensions: dict,
    id_counters: dict,
    heading_stack: list,
) -> dict | None:
    """Convert a Docling document item to a v2.0 dict.

    v2.0 additions over v1:
    - element_id (page-index based)
    - label (raw DocItemLabel)
    - bbox_normalized (0-1 range)
    - charspan
    - confidence
    - hierarchy (parent/children)
    - skip_indexing
    - headings (section ancestry)
    """
    try:
        content = ""
        etype = "paragraph"
        metadata = {}
        page_number = 0
        bbox_dict = None
        page_height = 0
        page_width = 0

        # ---- Extract provenance FIRST (page_number, page dims, element bbox) ----
        if hasattr(item, "prov") and item.prov:
            prov = item.prov[0] if isinstance(item.prov, list) else item.prov
            if hasattr(prov, "page_no"):
                page_number = prov.page_no or 0
            if hasattr(prov, "bbox"):
                bb = prov.bbox
                if bb:
                    if hasattr(doc, "pages") and doc.pages:
                        page_key = prov.page_no if hasattr(prov, "page_no") else page_number
                        page_obj = doc.pages.get(page_key)
                        if page_obj:
                            size = getattr(page_obj, "size", None)
                            if size:
                                page_height = getattr(size, "height", 0) or 0
                                page_width = getattr(size, "width", 0) or 0

                    if page_height and hasattr(bb, "to_top_left_origin"):
                        bbox_tl = bb.to_top_left_origin(page_height=page_height)
                        bbox_dict = {
                            "x0": bbox_tl.l,
                            "y0": bbox_tl.t,
                            "x1": bbox_tl.r,
                            "y1": bbox_tl.b,
                            "page": page_number,
                        }
                    else:
                        bbox_dict = {
                            "x0": getattr(bb, "l", 0),
                            "y0": getattr(bb, "t", 0),
                            "x1": getattr(bb, "r", 0),
                            "y1": getattr(bb, "b", 0),
                            "page": page_number,
                        }

        # Get page dims for normalization
        pg_dims = page_dimensions.get(str(page_number))
        pg_w = pg_dims["width"] if pg_dims else page_width
        pg_h = pg_dims["height"] if pg_dims else page_height

        # Get label string
        raw_label = _get_item_label(item)

        # Extract charspan
        charspan = _extract_charspan(item)

        # Extract hierarchy
        hierarchy = _extract_hierarchy(item, doc)

        # --- Specific TextItem subclasses (check before TextItem) ---

        if isinstance(item, SectionHeaderItem):
            etype = "section_header"
            content = item.text or ""
            metadata["level"] = item.level
            # Update heading stack
            while heading_stack and heading_stack[-1].get("level", 0) >= (item.level or 1):
                heading_stack.pop()
            heading_stack.append({"text": content, "level": item.level or 1})

        elif isinstance(item, ListItem):
            etype = "list_item"
            content = item.text or ""
            if item.marker:
                metadata["marker"] = item.marker

        elif TitleItem and isinstance(item, TitleItem):
            etype = "title"
            content = item.text or ""
            metadata["level"] = 1
            heading_stack.clear()
            heading_stack.append({"text": content, "level": 0})

        elif CodeItem and isinstance(item, CodeItem):
            etype = "code"
            content = item.text or ""
            if hasattr(item, "code_language") and item.code_language:
                metadata["language"] = str(item.code_language)

        elif FormulaItem and isinstance(item, FormulaItem):
            etype = "equation"
            content = item.text or ""

        # --- Floating item types ---

        elif isinstance(item, TableItem):
            etype = "table"
            try:
                content = item.export_to_markdown(doc=doc)
            except Exception:
                content = ""
            try:
                metadata["table_html"] = item.export_to_html(doc=doc)
            except Exception:
                pass
            if hasattr(item, "data") and item.data:
                metadata["num_rows"] = getattr(item.data, "num_rows", 0)
                metadata["num_cols"] = getattr(item.data, "num_cols", 0)
                # Extract table cell structure with normalized bboxes
                table_cells_data = getattr(item.data, "table_cells", None)
                if table_cells_data:
                    cells_list = []
                    for tc in table_cells_data:
                        cell_entry = {
                            "value": getattr(tc, "text", "") or "",
                            "row": getattr(tc, "start_row_offset_idx", 0),
                            "row_end": getattr(tc, "end_row_offset_idx", 0),
                            "col": getattr(tc, "start_col_offset_idx", 0),
                            "col_end": getattr(tc, "end_col_offset_idx", 0),
                            "column_header": getattr(tc, "column_header", False),
                            "row_header": getattr(tc, "row_header", False),
                            "row_span": getattr(tc, "row_span", 1),
                            "col_span": getattr(tc, "col_span", 1),
                        }
                        # v2: row_section and fillable
                        row_section = getattr(tc, "row_section", None)
                        if row_section is not None:
                            cell_entry["row_section"] = str(row_section.value) if hasattr(row_section, "value") else str(row_section)
                        fillable = getattr(tc, "fillable", None)
                        if fillable is not None:
                            cell_entry["fillable"] = bool(fillable)

                        tc_bbox = getattr(tc, "bbox", None)
                        if tc_bbox:
                            if page_height and hasattr(tc_bbox, "to_top_left_origin"):
                                tc_tl = tc_bbox.to_top_left_origin(page_height=page_height)
                                abs_bbox = {
                                    "x0": tc_tl.l, "y0": tc_tl.t,
                                    "x1": tc_tl.r, "y1": tc_tl.b,
                                    "page": page_number,
                                }
                            else:
                                abs_bbox = {
                                    "x0": getattr(tc_bbox, "l", 0),
                                    "y0": getattr(tc_bbox, "t", 0),
                                    "x1": getattr(tc_bbox, "r", 0),
                                    "y1": getattr(tc_bbox, "b", 0),
                                    "page": page_number,
                                }
                            cell_entry["bbox"] = abs_bbox
                            norm = _normalize_bbox(abs_bbox, pg_w, pg_h)
                            if norm:
                                cell_entry["bbox_normalized"] = norm

                        cells_list.append(cell_entry)
                    if cells_list:
                        metadata["table_cells"] = cells_list
            image_b64 = _extract_image_bytes(item, doc)
            if image_b64:
                metadata["image_b64"] = image_b64

        elif isinstance(item, PictureItem):
            if raw_label and raw_label.lower() == "chart":
                etype = "chart"
            else:
                etype = "figure"

            # Extract VL description from Docling annotations (PP-DocBee)
            vl_description = ""
            description_source = None
            if hasattr(item, "annotations") and item.annotations:
                for ann in item.annotations:
                    ann_text = getattr(ann, "text", "") or ""
                    if not ann_text:
                        ann_text = getattr(ann, "generated_text", "") or ""
                    if ann_text.strip():
                        vl_description = ann_text.strip()
                        description_source = "vlm"
                        break

            if vl_description:
                content = vl_description
                try:
                    caption = item.caption_text(doc) or ""
                    if caption:
                        metadata["caption"] = caption
                except Exception:
                    pass
            else:
                try:
                    content = item.caption_text(doc) or ""
                    description_source = "caption" if content else None
                except Exception:
                    content = ""

            if description_source:
                metadata["description_source"] = description_source

            # Picture classification metadata
            if hasattr(item, "classification") and item.classification:
                cls_val = item.classification
                if hasattr(cls_val, "value"):
                    metadata["classification"] = str(cls_val.value)
                elif hasattr(cls_val, "label"):
                    metadata["classification"] = str(cls_val.label)
                else:
                    metadata["classification"] = str(cls_val)

            image_b64 = _extract_image_bytes(item, doc)
            if image_b64:
                metadata["image_b64"] = image_b64

        elif KeyValueItem and isinstance(item, KeyValueItem):
            etype = "key_value"
            content, kv_cells = _extract_graph_data(item)
            if kv_cells:
                metadata["kv_cells"] = kv_cells

        elif FormItem and isinstance(item, FormItem):
            etype = "form_field"
            content, form_cells = _extract_graph_data(item)
            if form_cells:
                metadata["form_cells"] = form_cells

        # --- Label-based types ---

        elif raw_label and isinstance(item, TextItem):
            label_lower = raw_label.lower().replace("-", "_").replace(" ", "_")

            if label_lower == "caption":
                etype = "caption"
                content = item.text or ""
            elif label_lower == "footnote":
                etype = "footnote"
                content = item.text or ""
            elif label_lower == "page_header":
                etype = "page_header"
                content = item.text or ""
            elif label_lower == "page_footer":
                etype = "page_footer"
                content = item.text or ""
            elif label_lower == "reference":
                etype = "reference"
                content = item.text or ""
            elif label_lower == "document_index":
                etype = "document_index"
                content = item.text or ""
            elif label_lower == "checkbox_selected":
                etype = "checkbox"
                content = item.text or ""
                metadata["checked"] = True
            elif label_lower == "checkbox_unselected":
                etype = "checkbox"
                content = item.text or ""
                metadata["checked"] = False
            elif label_lower == "handwritten_text":
                etype = "handwritten"
                content = item.text or ""
                metadata["handwriting_detected"] = True
            elif label_lower == "grading_scale":
                etype = "grading_scale"
                content = item.text or ""
            else:
                etype = "paragraph"
                content = item.text or ""

        # --- Generic TextItem (catch-all) ---

        elif isinstance(item, TextItem):
            etype = "paragraph"
            content = item.text or ""

        # --- Unknown type fallback ---
        else:
            if hasattr(item, "text"):
                content = item.text or ""
            elif hasattr(item, "export_to_markdown"):
                try:
                    content = item.export_to_markdown(doc=doc)
                except Exception:
                    content = ""

        # Skip empty text-like elements (keep tables/figures/charts even with empty content)
        skip_if_empty = {
            "text", "paragraph", "list_item", "key_value", "form_field",
            "caption", "footnote", "page_header", "page_footer",
            "reference", "document_index", "handwritten", "grading_scale",
        }
        if not content and etype in skip_if_empty:
            return None

        # Generate element ID
        element_id = _generate_element_id(page_number, etype, id_counters)

        # Normalize bbox
        bbox_normalized = None
        if bbox_dict and pg_w > 0 and pg_h > 0:
            bbox_normalized = _normalize_bbox(bbox_dict, pg_w, pg_h)

        # Determine skip_indexing
        skip_indexing = etype in _SKIP_INDEXING_TYPES

        # Build headings list (section ancestry)
        headings = [h["text"] for h in heading_stack] if heading_stack else []

        result = {
            "element_id": element_id,
            "type": etype,
            "label": raw_label or etype,
            "content": content,
            "page_number": page_number,
            "bbox": bbox_dict,
            "bbox_normalized": bbox_normalized,
            "metadata": metadata,
        }

        if charspan:
            result["charspan"] = charspan
        if hierarchy:
            result["hierarchy"] = hierarchy
        if skip_indexing:
            result["skip_indexing"] = True
        if headings:
            result["headings"] = headings

        return result

    except Exception as e:
        logger.debug("Failed to convert Docling item %s: %s", type(item).__name__, e)
        return None


def _extract_graph_data(item) -> tuple[str, list[dict]]:
    """Extract text + structured cell data from KeyValueItem/FormItem graph cells."""
    if not hasattr(item, "graph") or not item.graph:
        return "", []
    parts = []
    cells = []
    for cell in item.graph.cells:
        cell_text = getattr(cell, "text", "") or ""
        cell_label = getattr(cell, "label", None)
        label_str = ""
        if cell_label:
            label_str = cell_label.value if hasattr(cell_label, "value") else str(cell_label)
        if cell_text.strip():
            parts.append(cell_text.strip())
        cells.append({
            "text": cell_text.strip(),
            "role": label_str,
            "cell_id": getattr(cell, "cell_id", None),
        })
    return " | ".join(parts), cells


def _extract_image_bytes(item, doc=None) -> str | None:
    """Extract image bytes from a Docling FloatingItem as base64."""
    try:
        pil_image = None

        if doc and hasattr(item, "get_image"):
            try:
                pil_image = item.get_image(doc=doc)
            except Exception:
                pass

        if pil_image is None and hasattr(item, "image") and item.image is not None:
            img_obj = item.image
            if hasattr(img_obj, "pil_image") and img_obj.pil_image is not None:
                pil_image = img_obj.pil_image

        if pil_image is None and hasattr(item, "get_image"):
            try:
                pil_image = item.get_image()
            except Exception:
                pass

        if pil_image is None:
            return None

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

    except Exception as e:
        logger.debug("Failed to extract image bytes: %s", e)
        return None


def _enrich_elements_v2(
    elements: dict[str, dict], model_manager
) -> dict[str, dict]:
    """Enrich table elements with img2table for borderless cell-level structure.

    Runs synchronously — caller must wrap in run_in_executor.
    """
    img2table_available = model_manager.get_img2table_available()
    if not img2table_available:
        return elements

    for eid, element in elements.items():
        etype = element.get("type", "paragraph")
        metadata = element.get("metadata", {})

        if etype == "table" and metadata.get("image_b64"):
            if "table_cells" in metadata:
                continue

            try:
                img_bytes = base64.b64decode(metadata["image_b64"])

                from img2table.document import Image as Img2TableImage

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    f.write(img_bytes)
                    temp_path = f.name

                try:
                    img_doc = Img2TableImage(src=temp_path)
                    extracted_tables = img_doc.extract_tables()
                finally:
                    os.unlink(temp_path)

                if extracted_tables:
                    table_cells = []
                    for table in extracted_tables:
                        for cell in table.content.values():
                            cell_entry = {
                                "value": str(cell.value) if cell.value else "",
                            }
                            cell_bbox = getattr(cell, "bbox", None)
                            if cell_bbox:
                                cell_entry["bbox"] = {
                                    "x0": getattr(cell_bbox, "x1", 0),
                                    "y0": getattr(cell_bbox, "y1", 0),
                                    "x1": getattr(cell_bbox, "x2", 0),
                                    "y1": getattr(cell_bbox, "y2", 0),
                                    "page": element.get("page_number", 0),
                                }
                            table_cells.append(cell_entry)
                    if table_cells:
                        metadata["table_cells"] = table_cells

            except Exception as e:
                logger.debug("img2table extraction failed: %s", e)

    return elements
