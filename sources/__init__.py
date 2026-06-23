"""Document source readers."""

from sources.image_source import IMAGE_EXTENSIONS, load_image
from sources.ocr import is_tesseract_available, ocr_text, preprocess_image
from sources.pdf_source import (
    DocumentSource,
    PageContent,
    PdfDocument,
    PdfLoadError,
    load_document,
    load_pdf,
)

SUPPORTED_EXTENSIONS = frozenset({".pdf", *IMAGE_EXTENSIONS})

__all__ = [
    "DocumentSource",
    "IMAGE_EXTENSIONS",
    "PageContent",
    "PdfDocument",
    "PdfLoadError",
    "SUPPORTED_EXTENSIONS",
    "load_document",
    "load_image",
    "load_pdf",
    "is_tesseract_available",
    "ocr_text",
    "preprocess_image",
]
