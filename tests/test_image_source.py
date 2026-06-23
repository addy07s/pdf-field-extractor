"""Tests for image invoice loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from sources.image_source import load_image
from sources.pdf_source import PdfLoadError, load_document

FIXTURES_DIR = Path(__file__).parent / "fixtures"
TINY_PNG = FIXTURES_DIR / "tiny_invoice.png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def tiny_png_path() -> Path:
    if not TINY_PNG.is_file():
        pytest.skip(f"Fixture image not found: {TINY_PNG}")
    return TINY_PNG


def test_load_image_returns_single_scanned_page(tiny_png_path: Path) -> None:
    doc = load_image(tiny_png_path)

    assert doc.filename == tiny_png_path.name
    assert doc.page_count == 1
    assert len(doc.pages) == 1
    assert doc.is_scanned is True
    assert doc.pages[0].image_bytes.startswith(PNG_SIGNATURE)
    assert len(doc.pages[0].image_bytes) > 0


def test_load_document_dispatches_to_image_loader(tiny_png_path: Path) -> None:
    doc = load_document(tiny_png_path)

    assert doc.page_count == 1
    assert doc.is_scanned is True


def test_load_document_rejects_unsupported_extension(tmp_path: Path) -> None:
    unsupported = tmp_path / "invoice.doc"
    unsupported.write_bytes(b"not supported")

    with pytest.raises(PdfLoadError, match="Unsupported document type"):
        load_document(unsupported)
