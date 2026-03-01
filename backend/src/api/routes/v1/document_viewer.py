"""Document Viewer API — enriched JSON + page image rendering.

Provides endpoints for the Agentic Docs viewer to display
parsed document structure with bounding box overlays.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from src.api.deps import DbSession, CurrentUser
from src.core.storage import get_storage_backend
from src.models.knowledge_base import Document
from src.services.knowledge_base_service import KnowledgeBaseService

logger = logging.getLogger(__name__)
router = APIRouter()

# Image file extensions that can be returned directly
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif"}
PDF_EXTENSIONS = {".pdf"}


def _bboxes_need_correction(parsed: dict) -> bool:
    """Detect if bboxes are in Docling BOTTOMLEFT origin and need y-flip.

    Docling BOTTOMLEFT: t > b, so y0 (stored as t) > y1 (stored as b).
    TOPLEFT (already converted): y0 <= y1.
    """
    for element in parsed.get("elements", []):
        bbox = element.get("bbox")
        if not bbox:
            continue
        y0 = bbox.get("y0", 0)
        y1 = bbox.get("y1", 0)
        if y0 == 0 and y1 == 0:
            continue
        # If y0 > y1, bboxes are in BOTTOMLEFT origin and need flipping
        return y0 > y1
    return False


def _extract_page_dimensions_pymupdf(file_bytes: bytes) -> dict[str, dict]:
    """Extract page dimensions from a PDF using PyMuPDF."""
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        dims = {}
        for i in range(len(doc)):
            page = doc[i]
            rect = page.rect
            dims[str(i + 1)] = {"width": float(rect.width), "height": float(rect.height)}
        doc.close()
        return dims
    except Exception:
        return {}


def _correct_bboxes_with_pymupdf(parsed: dict, file_bytes: bytes, page_dims: dict) -> dict:
    """Correct Docling bboxes using PyMuPDF word-level positions.

    Docling bboxes use bottom-left origin and report only ~50% of
    the actual text height (captures ascent, misses descent).
    This function:
    1. Flips y-axis from bottom-left to top-left origin
    2. Uses PyMuPDF word bboxes to correct the bottom edge
    """
    if not page_dims:
        return parsed

    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        # Fall back to simple y-flip without height correction
        return _flip_bboxes_simple(parsed, page_dims)

    # Pre-extract PyMuPDF words per page: {page_num: [(x0,y0,x1,y1,text), ...]}
    words_by_page: dict[int, list] = {}
    for i in range(len(doc)):
        page = doc[i]
        # get_text("words") returns (x0, y0, x1, y1, text, block, line, word)
        words_by_page[i + 1] = [
            (w[0], w[1], w[2], w[3]) for w in page.get_text("words")
        ]
    doc.close()

    for element in parsed.get("elements", []):
        bbox = element.get("bbox")
        if not bbox:
            continue

        page_num = int(bbox.get("page", element.get("page_number", 1)))
        page_num_str = str(page_num)
        dims = page_dims.get(page_num_str)
        if not dims:
            continue

        page_h = dims["height"]
        if page_h <= 0:
            continue

        x0 = bbox.get("x0", 0)
        y0 = bbox.get("y0", 0)
        x1 = bbox.get("x1", 0)
        y1 = bbox.get("y1", 0)

        # Flip y-axis: top-left y = page_height - bottom-left y
        ny0 = page_h - y0
        ny1 = page_h - y1
        if ny0 > ny1:
            ny0, ny1 = ny1, ny0
        if x0 > x1:
            x0, x1 = x1, x0

        # Correct bbox using PyMuPDF words on this page
        page_words = words_by_page.get(page_num, [])
        if page_words:
            # Find words whose top edge is near Docling's top edge
            # and whose x-range overlaps
            tolerance_y = max(5.0, (ny1 - ny0) * 0.3)
            matched_bottom = ny1
            for wx0, wy0, wx1, wy1 in page_words:
                # Word overlaps horizontally?
                if wx1 <= x0 or wx0 >= x1:
                    continue
                # Word's top edge near our top edge?
                if abs(wy0 - ny0) <= tolerance_y:
                    matched_bottom = max(matched_bottom, wy1)

            ny1 = matched_bottom

        element["bbox"] = {
            "x0": round(x0, 2),
            "y0": round(max(0, ny0), 2),
            "x1": round(x1, 2),
            "y1": round(min(page_h, ny1), 2),
            "page": page_num,
        }

    return parsed


def _flip_bboxes_simple(parsed: dict, page_dims: dict) -> dict:
    """Fallback: flip y-axis without PyMuPDF height correction."""
    for element in parsed.get("elements", []):
        bbox = element.get("bbox")
        if not bbox:
            continue

        page_num = str(bbox.get("page", element.get("page_number", 1)))
        dims = page_dims.get(page_num)
        if not dims:
            continue

        page_h = dims["height"]
        if page_h <= 0:
            continue

        x0 = bbox.get("x0", 0)
        y0 = bbox.get("y0", 0)
        x1 = bbox.get("x1", 0)
        y1 = bbox.get("y1", 0)

        ny0 = page_h - y0
        ny1 = page_h - y1
        if ny0 > ny1:
            ny0, ny1 = ny1, ny0
        if x0 > x1:
            x0, x1 = x1, x0

        element["bbox"] = {
            "x0": round(x0, 2),
            "y0": round(ny0, 2),
            "x1": round(x1, 2),
            "y1": round(ny1, 2),
            "page": int(page_num),
        }

    return parsed


@router.get("/{document_id}/parsed")
async def get_document_parsed(
    document_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Return the enriched JSON for the document viewer."""
    service = KnowledgeBaseService(db)
    document = await service.get_document(document_id)

    # Ownership check
    if document.uploaded_by and document.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own files",
        )

    empty_result = {
        "document_id": str(document.id),
        "filename": document.filename,
        "page_count": document.page_count or 1,
        "page_dimensions": {},
        "elements": [],
        "tables": [],
        "images": [],
        "metadata": {},
    }

    if not document.structured_json_path:
        return empty_result

    storage = get_storage_backend()
    try:
        data = await storage.get(document.structured_json_path)
        parsed = json.loads(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return empty_result

    # Populate page_dimensions from PyMuPDF if empty (Docling may not set them)
    page_dims = parsed.get("page_dimensions") or {}
    file_bytes = None
    is_pdf = (document.file_type or "").lower() in PDF_EXTENSIONS

    if not page_dims and is_pdf:
        try:
            file_bytes = await storage.get(document.file_path)
            page_dims = _extract_page_dimensions_pymupdf(file_bytes)
            parsed["page_dimensions"] = page_dims
        except Exception:
            pass

    # Correct bboxes if they're still in Docling BOTTOMLEFT origin.
    # New documents (processed with to_top_left_origin) have y0 <= y1.
    # Old documents (raw BOTTOMLEFT) have y0 > y1 and need correction.
    needs_correction = _bboxes_need_correction(parsed)

    if needs_correction and page_dims:
        if is_pdf:
            if file_bytes is None:
                try:
                    file_bytes = await storage.get(document.file_path)
                except Exception:
                    pass
            if file_bytes:
                parsed = _correct_bboxes_with_pymupdf(parsed, file_bytes, page_dims)
            else:
                parsed = _flip_bboxes_simple(parsed, page_dims)
        else:
            parsed = _flip_bboxes_simple(parsed, page_dims)

    return parsed


@router.get("/{document_id}/pages/{page_num}/image")
async def get_document_page_image(
    document_id: UUID,
    page_num: int,
    db: DbSession,
    current_user: CurrentUser,
    dpi: int = Query(150, ge=72, le=300),
) -> Response:
    """Return a rendered page image as PNG.

    - PDFs: rendered via PyMuPDF at specified DPI
    - Images: returned directly
    - Other: 404
    """
    service = KnowledgeBaseService(db)
    document = await service.get_document(document_id)

    # Ownership check
    if document.uploaded_by and document.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own files",
        )

    storage = get_storage_backend()
    file_ext = (document.file_type or "").lower()

    if file_ext in PDF_EXTENSIONS:
        # Render PDF page with PyMuPDF
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="PyMuPDF not installed — cannot render PDF pages",
            )

        file_bytes = await storage.get(document.file_path)
        try:
            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to open PDF: {e}",
            )

        if page_num < 1 or page_num > len(pdf_doc):
            pdf_doc.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Page {page_num} not found (document has {len(pdf_doc)} pages)",
            )

        page = pdf_doc[page_num - 1]
        pix = page.get_pixmap(dpi=dpi)
        png_bytes = pix.tobytes("png")
        pdf_doc.close()

        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    elif file_ext in IMAGE_EXTENSIONS:
        # Return original image directly (it IS the single page)
        if page_num != 1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image files only have 1 page",
            )

        file_bytes = await storage.get(document.file_path)
        media_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
        }.get(file_ext, "image/png")

        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page images not available for file type: {file_ext}",
        )


@router.get("/{document_id}/pages")
async def get_document_pages(
    document_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Return page metadata: page count and dimensions per page."""
    service = KnowledgeBaseService(db)
    document = await service.get_document(document_id)

    # Ownership check
    if document.uploaded_by and document.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own files",
        )

    page_dimensions = {}
    storage = get_storage_backend()

    if document.structured_json_path:
        try:
            data = await storage.get(document.structured_json_path)
            parsed = json.loads(data)
            page_dimensions = parsed.get("page_dimensions", {})
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # Fall back to PyMuPDF if Docling didn't provide page dimensions
    if not page_dimensions and (document.file_type or "").lower() in PDF_EXTENSIONS:
        try:
            file_bytes = await storage.get(document.file_path)
            page_dimensions = _extract_page_dimensions_pymupdf(file_bytes)
        except Exception:
            pass

    return {
        "page_count": document.page_count or 1,
        "page_dimensions": page_dimensions,
    }


def _convert_v1_to_v2(parsed: dict) -> dict:
    """Convert v1 enriched.json (flat arrays) to v2 (dict keyed by element_id)."""
    if parsed.get("version") == "2.0":
        return parsed

    elements_list = parsed.get("elements", [])
    if isinstance(elements_list, dict):
        return parsed  # Already v2 format

    # Generate element IDs for v1 elements
    counters: dict[str, dict[str, int]] = {}
    _PREFIX = {
        "paragraph": "P", "text": "P", "title": "H", "section_header": "H",
        "heading": "H", "table": "T", "figure": "F", "chart": "F", "image": "F",
        "equation": "E", "code": "C", "key_value": "K", "form_field": "K",
        "checkbox": "X", "list_item": "LI", "caption": "N", "footnote": "N",
        "reference": "N", "handwritten": "HW", "grading_scale": "GS",
        "document_index": "DI", "page_header": "PH", "page_footer": "PF",
    }
    _SKIP = {"page_header", "page_footer", "document_index"}

    elements_dict = {}
    tables_dict = {}
    images_dict = {}

    for el in elements_list:
        etype = el.get("element_type", "paragraph")
        page = el.get("page_number", 0)
        prefix = _PREFIX.get(etype, "P")
        page_key = str(page)
        if page_key not in counters:
            counters[page_key] = {}
        count = counters[page_key].get(prefix, 0) + 1
        counters[page_key][prefix] = count
        eid = f"{page}-{prefix}{count}"

        v2_el = {
            "element_id": eid,
            "type": etype,
            "label": etype,
            "content": el.get("content", ""),
            "page_number": page,
            "bbox": el.get("bbox"),
            "bbox_normalized": None,
            "metadata": el.get("metadata", {}),
        }
        if etype in _SKIP:
            v2_el["skip_indexing"] = True

        elements_dict[eid] = v2_el
        if etype == "table":
            tables_dict[eid] = v2_el
        elif etype in ("figure", "chart", "image"):
            images_dict[eid] = v2_el

    result = dict(parsed)
    result["version"] = "2.0"
    result["elements"] = elements_dict
    result["tables"] = tables_dict
    result["images"] = images_dict
    result.setdefault("pages", {})
    result.setdefault("quality", {})
    result.setdefault("conversion_status", "unknown")
    result.setdefault("timings", {})
    return result


@router.get("/{document_id}/enriched")
async def get_document_enriched(
    document_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Return enriched.json in v2.0 format (auto-converts v1 on-the-fly)."""
    service = KnowledgeBaseService(db)
    document = await service.get_document(document_id)

    if document.uploaded_by and document.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own files",
        )

    if not document.structured_json_path:
        return {"version": "2.0", "elements": {}, "tables": {}, "images": {}}

    storage = get_storage_backend()
    try:
        data = await storage.get(document.structured_json_path)
        parsed = json.loads(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": "2.0", "elements": {}, "tables": {}, "images": {}}

    # Convert v1 → v2 on the fly
    return _convert_v1_to_v2(parsed)


@router.get("/{document_id}/markdown")
async def get_document_markdown(
    document_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    """Reconstruct markdown from enriched.json elements."""
    service = KnowledgeBaseService(db)
    document = await service.get_document(document_id)

    if document.uploaded_by and document.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own files",
        )

    if not document.structured_json_path:
        return Response(content="", media_type="text/markdown")

    storage = get_storage_backend()
    try:
        data = await storage.get(document.structured_json_path)
        parsed = json.loads(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return Response(content="", media_type="text/markdown")

    # Ensure v2 format
    parsed = _convert_v1_to_v2(parsed)

    # Reconstruct markdown from elements
    md_parts = []
    elements = parsed.get("elements", {})
    if isinstance(elements, dict):
        elem_list = list(elements.values())
    else:
        elem_list = elements

    for el in elem_list:
        etype = el.get("type") or el.get("element_type", "paragraph")
        content = el.get("content", "")
        meta = el.get("metadata", {})

        if el.get("skip_indexing"):
            continue
        if not content.strip():
            continue

        if etype == "title":
            md_parts.append(f"# {content}")
        elif etype == "section_header":
            level = meta.get("level", 2)
            prefix = "#" * min(max(level, 1), 6)
            md_parts.append(f"{prefix} {content}")
        elif etype == "table":
            md_parts.append(content)
        elif etype == "code":
            lang = meta.get("language", "")
            md_parts.append(f"```{lang}\n{content}\n```")
        elif etype == "equation":
            md_parts.append(f"$$\n{content}\n$$")
        elif etype in ("figure", "chart", "image"):
            caption = meta.get("caption", "") or meta.get("original_caption", "")
            desc = content
            if desc:
                md_parts.append(f"*[{etype.title()}: {desc}]*")
            if caption:
                md_parts.append(f"*{caption}*")
        elif etype == "list_item":
            marker = meta.get("marker", "-")
            md_parts.append(f"{marker} {content}")
        elif etype == "checkbox":
            checked = meta.get("checked", False)
            mark = "x" if checked else " "
            md_parts.append(f"- [{mark}] {content}")
        elif etype == "footnote":
            md_parts.append(f"[^]: {content}")
        elif etype == "caption":
            md_parts.append(f"*{content}*")
        else:
            md_parts.append(content)

    markdown = "\n\n".join(md_parts)

    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'inline; filename="{document.filename}.md"'},
    )
