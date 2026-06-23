"""Tests for PyMuPDF PDF loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from sources.pdf_source import PdfLoadError, load_pdf

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DIGITAL_PDF = FIXTURES_DIR / "digital_invoice.pdf"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def digital_pdf_path() -> Path:
    if not DIGITAL_PDF.is_file():
        pytest.skip(f"Place a digital sample PDF at {DIGITAL_PDF}")
    return DIGITAL_PDF


def test_load_digital_pdf_text_and_images(digital_pdf_path: Path) -> None:
    doc = load_pdf(digital_pdf_path)

    assert doc.page_count >= 1
    assert len(doc.pages) == doc.page_count
    assert doc.filename == digital_pdf_path.name
    assert _non_whitespace_len(doc.text_layer) > 0
    assert doc.is_scanned is False

    for page in doc.pages:
        assert page.page_index >= 0
        assert len(page.text_layer) > 0
        assert page.image_bytes.startswith(PNG_SIGNATURE)
        assert len(page.image_bytes) > 100


def test_concatenated_text_layer_matches_pages(digital_pdf_path: Path) -> None:
    doc = load_pdf(digital_pdf_path)
    joined = "\n\n".join(p.text_layer for p in doc.pages)
    assert doc.text_layer == joined


def test_corrupt_pdf_raises_pdf_load_error(tmp_path: Path) -> None:
    bad_pdf = tmp_path / "corrupt.pdf"
    bad_pdf.write_bytes(b"not a real pdf")

    with pytest.raises(PdfLoadError, match="Failed to load PDF"):
        load_pdf(bad_pdf)


def _non_whitespace_len(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())
