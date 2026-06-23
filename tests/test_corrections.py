"""Tests for post-extraction text-layer corrections."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from extract.corrections import apply_text_layer_corrections
from sources.pdf_source import PageContent, PdfDocument
from validate.checks import check_gstin, validate_gstin_checksum

CORRECT_GSTIN = "19ABSPT7889H1ZC"
MISREAD_GSTIN = "19ABSBPT7889H1ZC"
CORRECT_PAN = "ABSPT7889H"


@dataclass(frozen=True)
class _FakeDocument:
    filename: str
    page_count: int
    pages: list[PageContent]
    text_layer: str
    is_scanned: bool


def _digital_document(text_layer: str) -> PdfDocument:
    return _FakeDocument(  # type: ignore[return-value]
        filename="invoice.pdf",
        page_count=1,
        pages=[PageContent(page_index=0, text_layer=text_layer, image_bytes=b"png")],
        text_layer=text_layer,
        is_scanned=False,
    )


def _scanned_document() -> PdfDocument:
    return _FakeDocument(  # type: ignore[return-value]
        filename="scan.jpg",
        page_count=1,
        pages=[PageContent(page_index=0, text_layer="", image_bytes=b"png")],
        text_layer="",
        is_scanned=True,
    )


def test_misread_gstin_is_corrected_from_text_layer() -> None:
    text_layer = f"Supplier GSTIN No.: {CORRECT_GSTIN}"
    raw_fields = {"gstin": MISREAD_GSTIN, "pan": CORRECT_PAN}
    document = _digital_document(text_layer)

    corrected = apply_text_layer_corrections(raw_fields, document)

    assert corrected["gstin"] == CORRECT_GSTIN
    assert validate_gstin_checksum(corrected["gstin"])
    assert check_gstin(corrected["gstin"]).status.value == "OK"


def test_correct_gstin_left_unchanged() -> None:
    text_layer = f"GSTIN {CORRECT_GSTIN}"
    raw_fields = {"gstin": CORRECT_GSTIN}

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
    )

    assert corrected["gstin"] == CORRECT_GSTIN


def test_scanned_document_leaves_ai_gstin_untouched() -> None:
    raw_fields = {"gstin": MISREAD_GSTIN, "pan": CORRECT_PAN}

    corrected = apply_text_layer_corrections(raw_fields, _scanned_document())

    assert corrected["gstin"] == MISREAD_GSTIN
    assert corrected["pan"] == CORRECT_PAN


def test_multiple_text_gstins_keeps_ai_when_it_matches_one() -> None:
    supplier = CORRECT_GSTIN
    recipient = "24ABMFA4190N1Z2"
    text_layer = f"Supplier GSTIN: {supplier}\nRecipient GSTIN: {recipient}"
    raw_fields = {"gstin": supplier}

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
    )

    assert corrected["gstin"] == supplier


def test_multiple_text_gstins_leaves_ai_when_it_matches_neither() -> None:
    supplier = CORRECT_GSTIN
    recipient = "24ABMFA4190N1Z2"
    text_layer = f"Supplier GSTIN: {supplier}\nRecipient GSTIN: {recipient}"
    wrong_ai = MISREAD_GSTIN
    raw_fields = {"gstin": wrong_ai}

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
    )

    assert corrected["gstin"] == wrong_ai


def test_pan_corrected_from_text_layer_when_single_match() -> None:
    text_layer = f"PAN {CORRECT_PAN} GSTIN {CORRECT_GSTIN}"
    raw_fields = {"pan": "ABSPT7889X", "gstin": CORRECT_GSTIN}

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
    )

    assert corrected["pan"] == CORRECT_PAN
