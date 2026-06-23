"""Image source reader — normalize invoice photos to PNG for the vision model."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from sources.ocr import enrich_scanned_content
from sources.pdf_source import PageContent, PdfDocument, PdfLoadError

IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})


def load_image(path: Path | str) -> PdfDocument:
    """Load a single-page image invoice with OCR enrichment when available.

    ``is_scanned`` remains True (OCR text is lower trust than native PDF text).
    When Tesseract is installed, ``text_layer`` is populated from OCR so grounding
    and GSTIN/PAN correction can run on image invoices.
    """
    image_path = Path(path)
    if not image_path.is_file():
        raise PdfLoadError(f"Image not found: {image_path}")

    try:
        with Image.open(image_path) as image:
            png_buffer = io.BytesIO()
            image.convert("RGB").save(png_buffer, format="PNG")
            raw_image_bytes = png_buffer.getvalue()
    except Exception as exc:
        raise PdfLoadError(f"Failed to load image {image_path.name}: {exc}") from exc

    image_bytes, text_layer, text_layer_is_ocr = enrich_scanned_content(raw_image_bytes)
    page = PageContent(
        page_index=0,
        text_layer=text_layer,
        image_bytes=image_bytes,
    )
    return PdfDocument(
        filename=image_path.name,
        page_count=1,
        pages=[page],
        text_layer=text_layer,
        is_scanned=True,
        text_layer_is_ocr=text_layer_is_ocr,
    )
