"""ABBYY Vantage JSON → enriched.json v2.0 adapter.

Maps the Vantage OCR.Skill JSON output (texts / tables / pictures /
separators / checkmarks / barcodes) into the enriched.json v2.0
element format consumed by the rest of the pipeline.

Only TEXT regions are mapped from ABBYY — non-text regions (tables,
pictures) are left as placeholder elements so that Docling's layout
model and VLM can fill them in during the normal processing flow.

Element ID format:  {page_number}-{prefix}{index}
  e.g.  "1-P3"  = page 1, paragraph 3
        "2-H1"  = page 2, heading 1
        "3-F2"  = page 3, figure 2
        "4-T1"  = page 4, table 1
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Font size thresholds (Vantage reports fontSize in units of 1/10 pt)
# fontSize=220 → 22pt → heading; fontSize=140 → 14pt → body text
_HEADING_FONT_SIZE = 180   # >= this → treat as heading
_SUBHEADING_FONT_SIZE = 160  # >= this → section header

# Element type → element_id prefix (mirrors enriched.json v2.0 convention)
_PREFIX = {
    "title": "H",
    "section_header": "H",
    "paragraph": "P",
    "key_value": "K",
    "figure": "F",
    "table": "T",
    "checkbox": "X",
    "barcode": "B",
    "separator": "S",
}


def _normalize_bbox(
    position: dict[str, int],
    page_width: int,
    page_height: int,
) -> dict[str, float]:
    """Normalize pixel bbox {l,t,r,b} to 0-1 range."""
    return {
        "x0": round(position["l"] / page_width, 6),
        "y0": round(position["t"] / page_height, 6),
        "x1": round(position["r"] / page_width, 6),
        "y1": round(position["b"] / page_height, 6),
    }


def _word_confidence(lines: list[dict[str, Any]]) -> float:
    """Compute mean word-level confidence across all lines (0-1 scale)."""
    confidences: list[float] = []
    for line in lines:
        for word in line.get("words", []):
            conf = word.get("confidence")
            if conf is not None:
                confidences.append(conf / 100.0)
    if not confidences:
        return 0.0
    return round(sum(confidences) / len(confidences), 4)


def _block_text(lines: list[dict[str, Any]]) -> str:
    """Join all line texts into a single string."""
    return "\n".join(line.get("text", "") for line in lines).strip()


def _infer_element_type(lines: list[dict[str, Any]]) -> str:
    """Infer element type from typography metadata.

    Uses font size from the first line's charParams as the primary
    signal. Falls back to 'paragraph' when no font size is available.
    """
    if not lines:
        return "paragraph"

    char_params = lines[0].get("charParams", {})
    font_size = char_params.get("fontSize", 0)

    if font_size >= _HEADING_FONT_SIZE:
        return "title"
    if font_size >= _SUBHEADING_FONT_SIZE:
        return "section_header"
    return "paragraph"


def _extract_line_metadata(lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract typography metadata from the first line's charParams."""
    if not lines:
        return {}

    char_params = lines[0].get("charParams", {})
    meta: dict[str, Any] = {}

    if "fontSize" in char_params:
        # Vantage fontSize is in 1/10 pt units → convert to pt
        meta["font_size"] = char_params["fontSize"] / 10.0
    if "fontName" in char_params:
        meta["font_name"] = char_params["fontName"]
    if char_params.get("bold"):
        meta["bold"] = True
    if char_params.get("italic"):
        meta["italic"] = True
    if "lang" in char_params:
        meta["lang"] = char_params["lang"]
    if "color" in char_params:
        meta["color"] = char_params["color"]

    meta["ocr_source"] = "abbyy_vantage"
    return meta


class AbbyyVantageAdapter:
    """Converts ABBYY Vantage OCR output into enriched.json v2.0 elements.

    Only text blocks are fully populated — pictures and formal tables
    are emitted as typed placeholders so the Docling/VLM layer can
    enrich them as part of the normal pipeline.

    Usage:
        adapter = AbbyyVantageAdapter()
        elements = adapter.convert(vantage_results)
        # elements is a dict keyed by element_id, same shape as
        # enriched.json v2.0 "elements" field.
    """

    def convert(
        self,
        vantage_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Convert Vantage result list to enriched.json v2.0 format.

        Args:
            vantage_results: List returned by AbbyyVantageClient.process_document().
                             Typically one item (the OCR.Skill JSON output).

        Returns:
            Dict with keys: elements, page_count, page_dimensions,
            quality, metadata — ready to merge into enriched.json v2.0.
        """
        if not vantage_results:
            return self._empty_result()

        # Vantage returns a list; the OCR skill output is the first item.
        # Handle all wrapping variants that can arrive from _download_results:
        #   [[{...}]]  — response.json() returned a list, appended as-is
        #   [{...}]    — already the correct format
        #   "{...}"    — double-encoded string (rare, some content-type paths)
        import json as _json
        raw = vantage_results[0] if isinstance(vantage_results, list) else vantage_results
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        if isinstance(raw, str):
            try:
                raw = _json.loads(raw)
                if isinstance(raw, list):
                    raw = raw[0] if raw else {}
            except Exception:
                logger.warning("ABBYY adapter: could not parse raw result string — returning empty")
                return self._empty_result()
        if not isinstance(raw, dict):
            logger.warning("ABBYY adapter: unexpected result type %s — returning empty", type(raw))
            return self._empty_result()
        pages = raw.get("layout", {}).get("pages", [])

        elements: dict[str, Any] = {}
        page_dimensions: dict[str, dict[str, float]] = {}
        page_quality: dict[str, dict[str, Any]] = {}

        reading_order = 0

        for page_idx, page in enumerate(pages):
            page_number = page_idx + 1
            page_width = page.get("width", 1)
            page_height = page.get("height", 1)

            page_dimensions[str(page_number)] = {
                "width": float(page_width),
                "height": float(page_height),
            }

            # Per-element type counters for ID generation
            counters: dict[str, int] = {}

            # ---- TEXT BLOCKS ----------------------------------------
            for text_block in page.get("texts", []):
                lines = text_block.get("lines", [])
                if not lines:
                    continue

                element_type = _infer_element_type(lines)
                prefix = _PREFIX[element_type]
                counters[prefix] = counters.get(prefix, 0) + 1
                element_id = f"{page_number}-{prefix}{counters[prefix]}"

                content = _block_text(lines)
                if not content:
                    continue

                position = text_block.get("position", {})
                bbox_norm = _normalize_bbox(position, page_width, page_height)
                confidence = _word_confidence(lines)
                metadata = _extract_line_metadata(lines)
                metadata["ocr_confidence"] = confidence
                metadata["abbyy_lines"] = [
                    {
                        "text": line.get("text", ""),
                        "position": line.get("position", {}),
                    }
                    for line in lines
                    if line.get("text", "").strip()
                ]

                reading_order += 1
                elements[element_id] = {
                    "element_id": element_id,
                    "type": element_type,
                    "label": element_type,
                    "content": content,
                    "page_number": page_number,
                    "reading_order": reading_order,
                    "bbox": {
                        "x0": position.get("l", 0),
                        "y0": position.get("t", 0),
                        "x1": position.get("r", 0),
                        "y1": position.get("b", 0),
                        "page": page_number,
                    },
                    "bbox_normalized": bbox_norm,
                    "charspan": [],   # populated by downstream pipeline
                    "hierarchy": {"parent": None, "children": []},
                    "headings": [],   # populated by downstream pipeline
                    "skip_indexing": False,
                    "metadata": metadata,
                }

            # ---- PICTURES (placeholders for VLM) --------------------
            for pic in page.get("pictures", []):
                prefix = _PREFIX["figure"]
                counters[prefix] = counters.get(prefix, 0) + 1
                element_id = f"{page_number}-{prefix}{counters[prefix]}"

                position = pic.get("position", {})
                bbox_norm = _normalize_bbox(position, page_width, page_height)

                reading_order += 1
                elements[element_id] = {
                    "element_id": element_id,
                    "type": "figure",
                    "label": "figure",
                    "content": "",   # VLM will populate this
                    "page_number": page_number,
                    "reading_order": reading_order,
                    "bbox": {
                        "x0": position.get("l", 0),
                        "y0": position.get("t", 0),
                        "x1": position.get("r", 0),
                        "y1": position.get("b", 0),
                        "page": page_number,
                    },
                    "bbox_normalized": bbox_norm,
                    "charspan": [],
                    "hierarchy": {"parent": None, "children": []},
                    "headings": [],
                    "skip_indexing": False,
                    "metadata": {
                        "ocr_source": "abbyy_vantage",
                        "vlm_pending": True,   # signal for VLM enrichment
                        "confidence": pic.get("confidence", 0) / 100.0,
                    },
                }

            # ---- FORMAL TABLES (placeholders for VLM/TableFormer) ---
            for table in page.get("tables", []):
                prefix = _PREFIX["table"]
                counters[prefix] = counters.get(prefix, 0) + 1
                element_id = f"{page_number}-{prefix}{counters[prefix]}"

                position = table.get("position", {})
                bbox_norm = _normalize_bbox(position, page_width, page_height)

                reading_order += 1
                elements[element_id] = {
                    "element_id": element_id,
                    "type": "table",
                    "label": "table",
                    "content": "",   # VLM will populate this
                    "page_number": page_number,
                    "reading_order": reading_order,
                    "bbox": {
                        "x0": position.get("l", 0),
                        "y0": position.get("t", 0),
                        "x1": position.get("r", 0),
                        "y1": position.get("b", 0),
                        "page": page_number,
                    },
                    "bbox_normalized": bbox_norm,
                    "charspan": [],
                    "hierarchy": {"parent": None, "children": []},
                    "headings": [],
                    "skip_indexing": False,
                    "metadata": {
                        "ocr_source": "abbyy_vantage",
                        "vlm_pending": True,
                    },
                }

            # ---- CHECKMARKS -----------------------------------------
            for chk in page.get("checkmarks", []):
                prefix = _PREFIX["checkbox"]
                counters[prefix] = counters.get(prefix, 0) + 1
                element_id = f"{page_number}-{prefix}{counters[prefix]}"

                position = chk.get("position", {})
                bbox_norm = _normalize_bbox(position, page_width, page_height)
                checked = chk.get("value", "").lower() in ("checked", "true", "yes")

                reading_order += 1
                elements[element_id] = {
                    "element_id": element_id,
                    "type": "checkbox",
                    "label": "checkbox",
                    "content": "[x]" if checked else "[ ]",
                    "page_number": page_number,
                    "reading_order": reading_order,
                    "bbox": {
                        "x0": position.get("l", 0),
                        "y0": position.get("t", 0),
                        "x1": position.get("r", 0),
                        "y1": position.get("b", 0),
                        "page": page_number,
                    },
                    "bbox_normalized": bbox_norm,
                    "charspan": [],
                    "hierarchy": {"parent": None, "children": []},
                    "headings": [],
                    "skip_indexing": False,
                    "metadata": {
                        "checked": checked,
                        "ocr_source": "abbyy_vantage",
                        "confidence": chk.get("confidence", 0) / 100.0,
                    },
                }

            # ---- PAGE QUALITY ---------------------------------------
            # Use mean word confidence across all text blocks as proxy
            all_confs = [
                el["metadata"].get("ocr_confidence", 0.0)
                for el in elements.values()
                if el["page_number"] == page_number
                and el["metadata"].get("ocr_source") == "abbyy_vantage"
                and "ocr_confidence" in el.get("metadata", {})
            ]
            mean_conf = round(sum(all_confs) / len(all_confs), 4) if all_confs else 0.0
            page_quality[str(page_number)] = {
                "ocr_confidence": mean_conf,
                "ocr_source": "abbyy_vantage",
            }

        return {
            "elements": elements,
            "page_count": len(pages),
            "page_dimensions": page_dimensions,
            "page_quality": page_quality,
            "metadata": {
                "producer": raw.get("producer", "ABBYY Vantage OCR.Skill"),
                "version": raw.get("version", ""),
                "languages": raw.get("languages", []),
                "ocr_source": "abbyy_vantage",
            },
        }

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "elements": {},
            "page_count": 0,
            "page_dimensions": {},
            "page_quality": {},
            "metadata": {"ocr_source": "abbyy_vantage"},
        }
