"""PyMuPDF source reader — text layer for grounding, page images for the model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from sources.ocr import enrich_scanned_content

RENDER_DPI = 200
_SCANNED_TEXT_THRESHOLD = 20
_PAGE_SEPARATOR = "\n\n"


class PdfLoadError(Exception):
    """Raised when a PDF cannot be opened, parsed, or rendered."""


@dataclass(frozen=True)
class PageContent:
    """Content extracted from a single PDF page."""

    page_index: int
    text_layer: str
    image_bytes: bytes


@dataclass(frozen=True)
class PdfDocument:
    """Normalized content from a PDF file."""

    filename: str
    page_count: int
    pages: list[PageContent]
    text_layer: str
    is_scanned: bool
    text_layer_is_ocr: bool = False


# Backward-compatible alias used by extract / validate modules.
DocumentSource = PdfDocument


def _non_whitespace_length(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def _is_scanned(pages_text: list[str]) -> bool:
    total = sum(_non_whitespace_length(t) for t in pages_text)
    return total < _SCANNED_TEXT_THRESHOLD


def _render_page_png(page: fitz.Page, zoom: float) -> bytes:
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    return pixmap.tobytes("png")


def load_pdf(path: Path | str) -> PdfDocument:
    """Load a PDF and return per-page images plus text layers for grounding.

    Rasterizes each page at ~200 DPI for vision-model input. No OCR is performed;
    the extracted text layer is used only for downstream grounding validation.

    Raises:
        PdfLoadError: If the file is missing, corrupt, or cannot be rendered.
    """
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise PdfLoadError(f"PDF not found: {pdf_path}")

    doc: fitz.Document | None = None
    try:
        doc = fitz.open(pdf_path)
        zoom = RENDER_DPI / 72.0
        pages: list[PageContent] = []

        for page_index in range(doc.page_count):
            try:
                page = doc.load_page(page_index)
                text_layer = page.get_text("text") or ""
                image_bytes = _render_page_png(page, zoom)
            except Exception as exc:  # noqa: BLE001 — wrap per-page render failures
                raise PdfLoadError(
                    f"Failed to read page {page_index + 1} of {pdf_path.name}: {exc}"
                ) from exc

            pages.append(
                PageContent(
                    page_index=page_index,
                    text_layer=text_layer,
                    image_bytes=image_bytes,
                )
            )

        page_texts = [p.text_layer for p in pages]
        concatenated = _PAGE_SEPARATOR.join(page_texts)
        is_scanned = _is_scanned(page_texts)

        if is_scanned:
            enriched_pages: list[PageContent] = []
            ocr_texts: list[str] = []
            any_ocr = False
            for page in pages:
                image_bytes, text_layer, text_layer_is_ocr = enrich_scanned_content(
                    page.image_bytes,
                    page.text_layer,
                )
                if text_layer_is_ocr:
                    any_ocr = True
                ocr_texts.append(text_layer)
                enriched_pages.append(
                    PageContent(
                        page_index=page.page_index,
                        text_layer=text_layer,
                        image_bytes=image_bytes,
                    )
                )
            pages = enriched_pages
            concatenated = _PAGE_SEPARATOR.join(ocr_texts)
            return PdfDocument(
                filename=pdf_path.name,
                page_count=len(pages),
                pages=pages,
                text_layer=concatenated,
                is_scanned=True,
                text_layer_is_ocr=any_ocr,
            )

        return PdfDocument(
            filename=pdf_path.name,
            page_count=len(pages),
            pages=pages,
            text_layer=concatenated,
            is_scanned=False,
            text_layer_is_ocr=False,
        )
    except PdfLoadError:
        raise
    except Exception as exc:
        raise PdfLoadError(f"Failed to load PDF {pdf_path.name}: {exc}") from exc
    finally:
        if doc is not None:
            doc.close()


def load_document(path: Path | str) -> PdfDocument:
    """Load a PDF or image invoice as a normalized document source."""
    from sources.image_source import IMAGE_EXTENSIONS, load_image

    document_path = Path(path)
    suffix = document_path.suffix.lower()

    if suffix == ".pdf":
        return load_pdf(document_path)
    if suffix in IMAGE_EXTENSIONS:
        return load_image(document_path)

    raise PdfLoadError(
        f"Unsupported document type: {document_path.suffix or '(none)'}"
    )
