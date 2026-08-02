"""Integration tests for the validation orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.field_config import load_field_configs
from models import FieldStatus
from sources.pdf_source import load_document
from validate.validator import validate_fields

SMOKE_RAW = {
    "company_name": "ADITYA MULTIMEDIA AND ENTERTAINMENT",
    "invoice_number": "AME/2",
    "invoice_date": "23/04/2026",
    "supplier_gstin": "24ABMFA4190N1Z2",
    "recipient_gstin": "19ABSPT7889H1ZC",
    "pan": "ABMFA4190N",
    "description": "ROYALTY INCOME {9984} JIOSaavn Royalty payment for Nov 2025 to Dec 2025 (FY 2025-26).",
    "total_taxable_value": "4380.00",
    "cgst_amount": "0.0",
    "sgst_amount": "0.0",
    "igst_amount": "788.40",
    "total_invoice_value": "5,168.40",
}

FIXTURE_PDF = Path("tests/fixtures/SalesBill_AME_2 1.PDF")


SMOKE_TEXT_LAYER = """
ADITYA MULTIMEDIA AND ENTERTAINMENT
Invoice No. AME/2
Date: 23/04/2026
GSTIN No.: 24ABMFA4190N1Z2
Recipient GSTIN: 19ABSPT7889H1ZC
PAN ABMFA4190N
ROYALTY INCOME {9984} JIOSaavn Royalty payment for Nov 2025 to Dec 2025 (FY 2025-26).
Taxable 4380.00
IGST 788.40
Total 5,168.40
"""


@pytest.fixture
def field_configs():
    return load_field_configs()


@pytest.fixture
def fixture_text_layer() -> str:
    if not FIXTURE_PDF.is_file():
        pytest.skip(f"Fixture PDF not found: {FIXTURE_PDF}")
    return load_document(FIXTURE_PDF).text_layer


def test_smoke_values_happy_path(field_configs) -> None:
    result = validate_fields(
        "SalesBill_AME_2 1.PDF",
        SMOKE_RAW,
        field_configs,
        SMOKE_TEXT_LAYER,
        is_scanned=False,
    )

    assert result.overall_status.value == "OK"
    assert result.fields["supplier_gstin"].status == FieldStatus.OK
    assert result.fields["pan"].status == FieldStatus.OK
    assert result.fields["invoice_date"].value == {
        "original": "23/04/2026",
        "normalized": "2026-04-23",
    }
    assert result.fields["total_taxable_value"].value == 4380.0
    assert result.fields["cgst_amount"].value == 0.0
    assert result.fields["sgst_amount"].value == 0.0
    assert result.fields["igst_amount"].value == 788.4
    assert result.fields["total_invoice_value"].value == 5168.4
    assert result.fields["total_taxable_value"].status == FieldStatus.OK
    assert result.fields["igst_amount"].status == FieldStatus.OK
    assert result.fields["total_invoice_value"].status == FieldStatus.OK


def test_smoke_values_against_fixture_pdf_text(field_configs, fixture_text_layer: str) -> None:
    result = validate_fields(
        "SalesBill_AME_2 1.PDF",
        SMOKE_RAW,
        field_configs,
        fixture_text_layer,
        is_scanned=False,
    )

    assert result.fields["supplier_gstin"].status == FieldStatus.OK
    assert result.fields["pan"].status == FieldStatus.OK
    assert result.fields["total_taxable_value"].status == FieldStatus.OK
    assert result.fields["igst_amount"].status == FieldStatus.OK
    assert result.fields["total_taxable_value"].value == 4380.0
    assert result.fields["igst_amount"].value == 788.4


def test_smoke_corrupted_gstin_transposition_fails_checksum(field_configs) -> None:
    """Smoke invoice with transposed GSTIN chars must fail checksum validation."""
    raw = dict(SMOKE_RAW)
    raw["supplier_gstin"] = "24ABFMA4190N1Z2"

    result = validate_fields(
        "SalesBill_AME_2 1.PDF",
        raw,
        field_configs,
        SMOKE_TEXT_LAYER,
        is_scanned=False,
    )

    assert result.fields["supplier_gstin"].status == FieldStatus.FAILED_VALIDATION
    assert "GSTIN checksum failed" in (result.fields["supplier_gstin"].reason or "")


def test_smoke_broken_reconciliation_flags_all_amounts(field_configs) -> None:
    """Wrong grand total must flag taxable + tax buckets + invoice total."""
    raw = dict(SMOKE_RAW)
    raw["total_invoice_value"] = "9999.99"

    result = validate_fields(
        "SalesBill_AME_2 1.PDF",
        raw,
        field_configs,
        SMOKE_TEXT_LAYER,
        is_scanned=False,
    )

    for key in (
        "total_taxable_value",
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "total_invoice_value",
    ):
        assert result.fields[key].status == FieldStatus.LOW_CONFIDENCE
        assert "do not reconcile" in (result.fields[key].reason or "")


def test_cgst_sgst_with_igst_fails_exclusivity(field_configs) -> None:
    raw = dict(SMOKE_RAW)
    raw["cgst_amount"] = "394.20"
    raw["sgst_amount"] = "394.20"
    raw["igst_amount"] = "788.40"
    raw["total_invoice_value"] = "5,168.40"

    result = validate_fields(
        "SalesBill_AME_2 1.PDF",
        raw,
        field_configs,
        SMOKE_TEXT_LAYER,
        is_scanned=False,
    )

    for key in ("cgst_amount", "sgst_amount", "igst_amount"):
        assert result.fields[key].status == FieldStatus.FAILED_VALIDATION
        assert "invalid tax mix" in (result.fields[key].reason or "")


def test_missing_tax_buckets_default_to_zero(field_configs) -> None:
    raw = dict(SMOKE_RAW)
    raw["cgst_amount"] = None
    raw["sgst_amount"] = None
    raw["igst_amount"] = "788.40"

    result = validate_fields(
        "SalesBill_AME_2 1.PDF",
        raw,
        field_configs,
        SMOKE_TEXT_LAYER,
        is_scanned=False,
    )

    assert result.fields["cgst_amount"].status == FieldStatus.OK
    assert result.fields["cgst_amount"].value == 0.0
    assert result.fields["sgst_amount"].status == FieldStatus.OK
    assert result.fields["sgst_amount"].value == 0.0
    assert result.fields["igst_amount"].value == 788.4


def test_smoke_gstin_pan_mismatch_flags_both_fields(field_configs) -> None:
    """Supplier GSTIN with a wrong PAN must flag both fields on cross-check."""
    raw = dict(SMOKE_RAW)
    raw["supplier_gstin"] = "24ABMFA4190N1Z2"
    raw["pan"] = "ZZZZZ9999Z"

    result = validate_fields(
        "SalesBill_AME_2 1.PDF",
        raw,
        field_configs,
        SMOKE_TEXT_LAYER,
        is_scanned=False,
    )

    assert result.fields["supplier_gstin"].status == FieldStatus.FAILED_VALIDATION
    assert result.fields["pan"].status == FieldStatus.FAILED_VALIDATION
    assert "GSTIN/PAN mismatch" in (result.fields["supplier_gstin"].reason or "")
    assert "GSTIN/PAN mismatch" in (result.fields["pan"].reason or "")


def test_none_field_is_not_found(field_configs) -> None:
    raw = dict(SMOKE_RAW)
    raw["supplier_gstin"] = None

    result = validate_fields(
        "invoice.pdf",
        raw,
        field_configs,
        "some text",
        is_scanned=False,
    )

    assert result.fields["supplier_gstin"].status == FieldStatus.NOT_FOUND
    assert result.fields["supplier_gstin"].reason == "field not extracted"


def test_ungroundable_value_gets_low_confidence(field_configs) -> None:
    raw = dict(SMOKE_RAW)
    raw["company_name"] = "TOTALLY DIFFERENT COMPANY LTD"

    result = validate_fields(
        "invoice.pdf",
        raw,
        field_configs,
        "unrelated invoice text",
        is_scanned=False,
    )

    assert result.fields["company_name"].status == FieldStatus.LOW_CONFIDENCE
    assert "not found in document text" in (result.fields["company_name"].reason or "")
