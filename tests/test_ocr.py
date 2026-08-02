"""Tests for OCR preprocessing and text extraction."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from extract.corrections import apply_text_layer_corrections
from sources.ocr import (
    get_tesseract_version,
    is_tesseract_available,
    log_ocr_startup_status,
    ocr_startup_status_message,
    ocr_text,
    preprocess_image,
)
from sources.pdf_source import PageContent, PdfDocument
from validate.checks import check_gstin, validate_gstin_checksum

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SKEWED_PNG = FIXTURES_DIR / "ocr_skewed_invoice.png"
CLEAN_OCR_PNG = FIXTURES_DIR / "ocr_clean_invoice.png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

CORRECT_GSTIN = "19ABSPT7889H1ZC"
MISREAD_GSTIN = "19ABSBPT7889H1ZC"


def _write_skewed_fixture(path: Path) -> None:
    image = np.full((180, 420, 3), 255, dtype=np.uint8)
    cv2.putText(
        image,
        "GSTIN 19ABSPT7889H1ZC",
        (20, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    matrix = cv2.getRotationMatrix2D((210, 90), 8, 1.0)
    skewed = cv2.warpAffine(
        gray,
        matrix,
        (420, 180),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )
    success, encoded = cv2.imencode(".png", skewed)
    assert success
    path.write_bytes(encoded.tobytes())


def _write_clean_ocr_fixture(path: Path) -> None:
    image = Image.new("RGB", (640, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 80), f"Supplier GSTIN {CORRECT_GSTIN}", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    path.write_bytes(buffer.getvalue())


@pytest.fixture(scope="module", autouse=True)
def _ensure_ocr_fixtures() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    if not SKEWED_PNG.is_file():
        _write_skewed_fixture(SKEWED_PNG)
    if not CLEAN_OCR_PNG.is_file():
        _write_clean_ocr_fixture(CLEAN_OCR_PNG)


def test_preprocess_image_returns_valid_png_bytes() -> None:
    raw = SKEWED_PNG.read_bytes()
    processed = preprocess_image(raw)

    assert processed.startswith(PNG_SIGNATURE)
    assert len(processed) > 100
    assert processed != raw


def test_ocr_text_extracts_known_text_from_clean_fixture() -> None:
    with patch("sources.ocr.is_tesseract_available", return_value=True), patch(
        "pytesseract.image_to_string",
        return_value=f"Supplier GSTIN {CORRECT_GSTIN}",
    ):
        text = ocr_text(CLEAN_OCR_PNG.read_bytes())

    assert CORRECT_GSTIN in text.upper().replace(" ", "")


def test_ocr_text_returns_empty_when_tesseract_unavailable() -> None:
    with patch("sources.ocr.is_tesseract_available", return_value=False):
        assert ocr_text(CLEAN_OCR_PNG.read_bytes()) == ""


def test_misread_gstin_corrected_from_ocr_text_layer() -> None:
    ocr_layer = f"Supplier GSTIN {CORRECT_GSTIN}"
    document = PdfDocument(
        filename="scan.jpg",
        page_count=1,
        pages=[PageContent(page_index=0, text_layer=ocr_layer, image_bytes=b"png")],
        text_layer=ocr_layer,
        is_scanned=True,
        text_layer_is_ocr=True,
    )
    raw_fields = {"supplier_gstin": MISREAD_GSTIN}

    corrected = apply_text_layer_corrections(raw_fields, document)

    assert corrected["supplier_gstin"] == CORRECT_GSTIN
    assert validate_gstin_checksum(corrected["supplier_gstin"])
    assert check_gstin(corrected["supplier_gstin"]).status.value == "OK"


def test_preprocess_image_noop_on_failure_returns_original_bytes() -> None:
    bad_bytes = b"not-an-image"
    assert preprocess_image(bad_bytes) == bad_bytes


def test_ocr_startup_status_message_when_tesseract_missing() -> None:
    with patch("sources.ocr.get_tesseract_version", return_value=None):
        message = ocr_startup_status_message()
        assert "OCR disabled" in message
        assert "PATH" in message


def test_ocr_startup_status_message_when_tesseract_found() -> None:
    with patch("sources.ocr.get_tesseract_version", return_value="5.4.0"):
        message = ocr_startup_status_message()
        assert message == "OCR enabled (Tesseract 5.4.0 found)"


def test_log_ocr_startup_status_returns_message(caplog) -> None:
    import logging

    get_tesseract_version.cache_clear()
    is_tesseract_available.cache_clear()
    with patch("sources.ocr.get_tesseract_version", return_value=None):
        with caplog.at_level(logging.WARNING):
            returned = log_ocr_startup_status()
        assert returned == ocr_startup_status_message()
        assert "OCR disabled" in caplog.text
    get_tesseract_version.cache_clear()
    is_tesseract_available.cache_clear()
