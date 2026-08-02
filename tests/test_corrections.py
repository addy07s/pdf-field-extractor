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


def test_misread_supplier_gstin_is_corrected_from_text_layer() -> None:
    text_layer = f"Supplier GSTIN No.: {CORRECT_GSTIN}"
    raw_fields = {"supplier_gstin": MISREAD_GSTIN, "pan": CORRECT_PAN}
    document = _digital_document(text_layer)

    corrected = apply_text_layer_corrections(raw_fields, document)

    assert corrected["supplier_gstin"] == CORRECT_GSTIN
    assert validate_gstin_checksum(corrected["supplier_gstin"])
    assert check_gstin(corrected["supplier_gstin"]).status.value == "OK"


def test_correct_supplier_gstin_left_unchanged() -> None:
    text_layer = f"GSTIN {CORRECT_GSTIN}"
    raw_fields = {"supplier_gstin": CORRECT_GSTIN}

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
    )

    assert corrected["supplier_gstin"] == CORRECT_GSTIN


def test_scanned_document_leaves_ai_gstin_untouched() -> None:
    raw_fields = {
        "supplier_gstin": MISREAD_GSTIN,
        "recipient_gstin": None,
        "pan": CORRECT_PAN,
    }

    corrected = apply_text_layer_corrections(raw_fields, _scanned_document())

    assert corrected["supplier_gstin"] == MISREAD_GSTIN
    assert corrected["pan"] == CORRECT_PAN


def test_multiple_text_gstins_keeps_ai_when_it_matches_one() -> None:
    supplier = CORRECT_GSTIN
    recipient = "24ABMFA4190N1Z2"
    text_layer = f"Supplier GSTIN: {supplier}\nRecipient GSTIN: {recipient}"
    raw_fields = {"supplier_gstin": supplier, "recipient_gstin": recipient}

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
    )

    assert corrected["supplier_gstin"] == supplier
    assert corrected["recipient_gstin"] == recipient


def test_multiple_text_gstins_leaves_ai_when_it_matches_neither() -> None:
    supplier = CORRECT_GSTIN
    recipient = "24ABMFA4190N1Z2"
    text_layer = f"Supplier GSTIN: {supplier}\nRecipient GSTIN: {recipient}"
    wrong_ai = MISREAD_GSTIN
    raw_fields = {"supplier_gstin": wrong_ai}

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
    )

    assert corrected["supplier_gstin"] == wrong_ai


def test_single_text_gstin_does_not_fabricate_recipient() -> None:
    text_layer = f"Supplier GSTIN No.: {CORRECT_GSTIN}"
    raw_fields = {
        "supplier_gstin": MISREAD_GSTIN,
        "recipient_gstin": None,
    }

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
    )

    assert corrected["supplier_gstin"] == CORRECT_GSTIN
    assert corrected["recipient_gstin"] is None


def test_recipient_misread_not_replaced_by_unrelated_single_gstin() -> None:
    """A lone text GSTIN may correct supplier only — not recipient."""
    text_layer = f"Supplier GSTIN: {CORRECT_GSTIN}"
    raw_fields = {
        "supplier_gstin": CORRECT_GSTIN,
        "recipient_gstin": MISREAD_GSTIN,
    }

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
    )

    assert corrected["recipient_gstin"] == MISREAD_GSTIN


def test_multi_invoice_disables_single_gstin_replace() -> None:
    text_layer = f"Supplier GSTIN No.: {CORRECT_GSTIN}"
    raw_fields = {"supplier_gstin": MISREAD_GSTIN}

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
        allow_single_gstin_replace=False,
    )

    assert corrected["supplier_gstin"] == MISREAD_GSTIN


def test_pan_corrected_from_text_layer_when_single_match() -> None:
    text_layer = f"PAN {CORRECT_PAN} GSTIN {CORRECT_GSTIN}"
    raw_fields = {"pan": "ABSPT7889X", "supplier_gstin": CORRECT_GSTIN}

    corrected = apply_text_layer_corrections(
        raw_fields,
        _digital_document(text_layer),
    )

    assert corrected["pan"] == CORRECT_PAN
