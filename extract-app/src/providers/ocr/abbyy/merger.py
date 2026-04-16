"""Spatial merger: overlays ABBYY OCR text onto Docling layout elements.

Docling owns:
  - Reading order, hierarchy, element types, headings context
  - Non-text content (table cell structure, VLM image descriptions)

ABBYY owns:
  - Text content (superior OCR accuracy)
  - Typography metadata: font_size, bold, italic, lang, color
  - Per-word confidence scores

The merger matches each Docling text element to the ABBYY text block
with the highest spatial overlap (IoU) on the same page, then replaces
the element's content with ABBYY text and injects typography metadata.

Non-text Docling elements (table, figure, chart, equation, code,
checkbox) are never touched — they stay with Docling/VLM as-is.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Docling element types that carry human-readable text → ABBYY replaces
_TEXT_TYPES = {
    "paragraph",
    "section_header",
    "title",
    "key_value",
    "form_field",
    "list_item",
    "footnote",
    "caption",
    "reference",
    "page_header",
    "page_footer",
    "handwritten_text",
}

# Minimum IoU for pass-1 (strict 1-to-1 matching)
_IOU_THRESHOLD = 0.25
# Minimum IoA for pass-2 fallback: fraction of the Docling element's area
# that must be covered by an ABBYY block for it to inherit that block's text.
_IOA_THRESHOLD = 0.5


def _intersection(a: dict[str, float], b: dict[str, float]) -> float:
    """Return intersection area of two bboxes (x0,y0,x1,y1). 0 if no overlap."""
    ix0 = max(a["x0"], b["x0"])
    iy0 = max(a["y0"], b["y0"])
    ix1 = min(a["x1"], b["x1"])
    iy1 = min(a["y1"], b["y1"])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    return (ix1 - ix0) * (iy1 - iy0)


def _iou(a: dict[str, float], b: dict[str, float]) -> float:
    """Intersection over Union for two pixel-coordinate bboxes."""
    inter = _intersection(a, b)
    if inter == 0.0:
        return 0.0
    area_a = max((a["x1"] - a["x0"]) * (a["y1"] - a["y0"]), 1e-6)
    area_b = max((b["x1"] - b["x0"]) * (b["y1"] - b["y0"]), 1e-6)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _ioa(docling_bbox: dict[str, float], abbyy_bbox: dict[str, float]) -> float:
    """Intersection over Area of the Docling element.

    High when the Docling element is mostly *inside* the ABBYY block,
    even if the ABBYY block is much larger (e.g. covers a full row).
    """
    inter = _intersection(docling_bbox, abbyy_bbox)
    if inter == 0.0:
        return 0.0
    area_docling = max(
        (docling_bbox["x1"] - docling_bbox["x0"])
        * (docling_bbox["y1"] - docling_bbox["y0"]),
        1e-6,
    )
    return inter / area_docling


def _build_abbyy_index(
    abbyy_elements: dict[str, Any],
) -> dict[int, list[dict[str, Any]]]:
    """Build a per-page spatial index of ABBYY text elements.

    Returns:
        {page_number: [element, ...]}  — only text-type elements.
    """
    index: dict[int, list[dict[str, Any]]] = {}
    for el in abbyy_elements.values():
        if el.get("type") not in _TEXT_TYPES:
            continue
        bbox = el.get("bbox")
        if not bbox:
            continue
        page = el.get("page_number", 1)
        index.setdefault(page, []).append(el)
    return index


def _extract_overlapping_lines(
    docling_bbox: dict[str, float],
    abbyy_block: dict[str, Any],
) -> str:
    """Return only the ABBYY lines whose y-range overlaps the Docling element.

    Falls back to the full block content when no line-level data is available
    or when no lines match (which would indicate a bbox misalignment).
    """
    abbyy_lines: list[dict[str, Any]] = abbyy_block.get("metadata", {}).get("abbyy_lines", [])
    if not abbyy_lines:
        return abbyy_block.get("content", "").strip()

    doc_y0 = docling_bbox["y0"]
    doc_y1 = docling_bbox["y1"]

    matched: list[str] = []
    for line in abbyy_lines:
        pos = line.get("position", {})
        line_y0 = pos.get("t", 0)
        line_y1 = pos.get("b", 0)
        # Overlap: line's y-range intersects with Docling element's y-range
        if line_y1 > doc_y0 and line_y0 < doc_y1:
            text = line.get("text", "").strip()
            if text:
                matched.append(text)

    if matched:
        return "\n".join(matched)
    # Fallback: no lines matched — return full block to avoid empty content
    return abbyy_block.get("content", "").strip()


class AbbyyDoclingMerger:
    """Merges ABBYY OCR text into Docling layout elements.

    Usage:
        merger = AbbyyDoclingMerger()
        enriched_elements = merger.merge(docling_elements, abbyy_data)
    """

    def merge(
        self,
        docling_elements: dict[str, Any],
        abbyy_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Overlay ABBYY text onto matching Docling text elements.

        Args:
            docling_elements: enriched.json v2.0 elements dict from Docling.
            abbyy_data:       Output of AbbyyVantageAdapter.convert().

        Returns:
            Enriched elements dict with ABBYY text + metadata injected
            into text elements, non-text elements unchanged.
        """
        abbyy_elements = abbyy_data.get("elements", {})
        if not abbyy_elements:
            logger.warning("ABBYY produced no elements — keeping Docling OCR text")
            return docling_elements

        abbyy_index = _build_abbyy_index(abbyy_elements)
        matched = 0
        unmatched = 0

        # Build scored pairs (docling_id, abbyy_element, iou) across all pages,
        # then do greedy 1-to-1 assignment: highest-IoU pairs win first.
        # This prevents the same ABBYY block from being claimed by multiple
        # Docling elements (which produced duplicate content in earlier runs).
        scored: list[tuple[float, str, dict[str, Any]]] = []

        for eid, element in docling_elements.items():
            el_type = element.get("type", "")
            if el_type not in _TEXT_TYPES:
                continue
            bbox = element.get("bbox")
            if not bbox or not all(k in bbox for k in ("x0", "y0", "x1", "y1")):
                continue
            page = element.get("page_number", 1)
            for candidate in abbyy_index.get(page, []):
                cand_bbox = candidate.get("bbox", {})
                if not cand_bbox:
                    continue
                score = _iou(bbox, cand_bbox)
                if score >= _IOU_THRESHOLD:
                    scored.append((score, eid, candidate))

        # Sort descending by IoU so best matches are assigned first
        scored.sort(key=lambda t: t[0], reverse=True)

        claimed_abbyy: set[int] = set()   # id() of already-assigned ABBYY blocks
        claimed_docling: set[str] = set() # element IDs already filled

        for score, eid, candidate in scored:
            if eid in claimed_docling:
                continue
            cand_id = id(candidate)
            if cand_id in claimed_abbyy:
                continue

            element = docling_elements[eid]
            abbyy_content = _extract_overlapping_lines(element.get("bbox", {}), candidate)
            if abbyy_content:
                element["content"] = abbyy_content

            existing_meta = element.setdefault("metadata", {})
            abbyy_meta = candidate.get("metadata", {})
            for key in (
                "font_size", "font_name", "bold", "italic",
                "lang", "color", "ocr_confidence", "ocr_source",
            ):
                if key in abbyy_meta:
                    existing_meta[key] = abbyy_meta[key]

            existing_meta["abbyy_iou"] = round(score, 4)
            claimed_abbyy.add(cand_id)
            claimed_docling.add(eid)
            matched += 1

        # ------------------------------------------------------------------
        # Pass 2 — IoA fallback for still-unmatched elements.
        #
        # A Docling element that sat *inside* a large ABBYY block (e.g. a
        # full-row block covering "Terms: …  Freight: …") had low IoU and
        # was skipped in pass 1.  Here we allow it to inherit text from any
        # ABBYY block that covers ≥ _IOA_THRESHOLD of its own area.
        # ABBYY blocks are NOT exclusively claimed in this pass — multiple
        # Docling elements may share the same large block.
        # ------------------------------------------------------------------
        ioa_matched = 0
        all_abbyy_blocks: list[dict[str, Any]] = [
            el for page_els in abbyy_index.values() for el in page_els
        ]

        for eid, element in docling_elements.items():
            if eid in claimed_docling:
                continue
            el_type = element.get("type", "")
            if el_type not in _TEXT_TYPES:
                continue
            bbox = element.get("bbox")
            if not bbox or not all(k in bbox for k in ("x0", "y0", "x1", "y1")):
                continue
            page = element.get("page_number", 1)

            best_ioa = 0.0
            best_block: dict[str, Any] | None = None
            for block in abbyy_index.get(page, []):
                cand_bbox = block.get("bbox", {})
                if not cand_bbox:
                    continue
                score = _ioa(bbox, cand_bbox)
                if score > best_ioa:
                    best_ioa = score
                    best_block = block

            if best_block and best_ioa >= _IOA_THRESHOLD:
                abbyy_content = _extract_overlapping_lines(bbox, best_block)
                if abbyy_content:
                    element["content"] = abbyy_content
                existing_meta = element.setdefault("metadata", {})
                abbyy_meta = best_block.get("metadata", {})
                for key in (
                    "font_size", "font_name", "bold", "italic",
                    "lang", "color", "ocr_confidence", "ocr_source",
                ):
                    if key in abbyy_meta:
                        existing_meta[key] = abbyy_meta[key]
                existing_meta["abbyy_ioa"] = round(best_ioa, 4)
                claimed_docling.add(eid)
                ioa_matched += 1
            else:
                unmatched += 1
                logger.debug("No ABBYY match for element %s (best IoA=%.3f)", eid, best_ioa)

        logger.info(
            "ABBYY merge: %d IoU matched, %d IoA fallback, %d unmatched",
            matched,
            ioa_matched,
            unmatched,
        )
        return docling_elements
