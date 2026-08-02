"""Unit tests for individual validation checks."""

from __future__ import annotations

from decimal import Decimal

import pytest

from models import FieldStatus
from validate.checks import (
    amounts_reconcile,
    check_arithmetic_reconciliation,
    check_date,
    check_gstin,
    check_gstin_pan_crosscheck,
    check_grounding,
    check_number,
    check_pan,
    check_tax_bucket_exclusivity,
    parse_indian_number,
    validate_gstin_checksum,
)

SMOKE_GSTIN = "24ABMFA4190N1Z2"
SMOKE_PAN = "ABMFA4190N"
SMOKE_DATE = "23/04/2026"
SMOKE_TAXABLE = "4380.00"
SMOKE_GST = "788.40"
SMOKE_TOTAL = "5,168.40"


def test_validate_gstin_checksum_smoke_value_is_valid() -> None:
    assert validate_gstin_checksum(SMOKE_GSTIN) is True


def test_check_gstin_smoke_value_passes() -> None:
    result = check_gstin(SMOKE_GSTIN)
    assert result.status == FieldStatus.OK
    assert result.value == SMOKE_GSTIN


def test_check_gstin_bad_checksum_fails() -> None:
    bad = "24ABMFA4190N1Z0"
    result = check_gstin(bad)
    assert result.status == FieldStatus.FAILED_VALIDATION
    assert result.reason == "GSTIN checksum failed"


def test_check_pan_smoke_value_passes() -> None:
    result = check_pan(SMOKE_PAN)
    assert result.status == FieldStatus.OK
    assert result.value == SMOKE_PAN


def test_check_pan_malformed_fails() -> None:
    result = check_pan("ABMF4190N")
    assert result.status == FieldStatus.FAILED_VALIDATION
    assert result.reason == "invalid PAN structure"


def test_gstin_pan_crosscheck_smoke_values_match() -> None:
    result = check_gstin_pan_crosscheck(SMOKE_GSTIN, SMOKE_PAN)
    assert result.status == FieldStatus.OK


def test_gstin_pan_crosscheck_mismatch_fails() -> None:
    result = check_gstin_pan_crosscheck(SMOKE_GSTIN, "ZZZZZ9999Z")
    assert result.status == FieldStatus.FAILED_VALIDATION
    assert result.reason == "GSTIN/PAN mismatch"


def test_check_date_smoke_value_normalizes_to_iso() -> None:
    result = check_date(SMOKE_DATE)
    assert result.status == FieldStatus.OK
    assert result.value == {
        "original": SMOKE_DATE,
        "normalized": "2026-04-23",
    }


@pytest.mark.parametrize(
    ("raw", "expected_iso"),
    [
        ("31-Mar-26", "2026-03-31"),
        ("2-Mar-26", "2026-03-02"),
        ("1-Sep-2025", "2025-09-01"),
        ("23/04/2025", "2025-04-23"),
        ("2025-12-10", "2025-12-10"),
        ("31/03/2026", "2026-03-31"),
    ],
)
def test_check_date_accepts_common_indian_invoice_formats(
    raw: str,
    expected_iso: str,
) -> None:
    result = check_date(raw)
    assert result.status == FieldStatus.OK
    assert result.value == {"original": raw, "normalized": expected_iso}


def test_check_date_invalid_format_fails() -> None:
    result = check_date("not-a-date")
    assert result.status == FieldStatus.FAILED_VALIDATION


def test_parse_indian_number_strips_commas() -> None:
    assert parse_indian_number(SMOKE_TOTAL) == Decimal("5168.40")


def test_check_number_smoke_total_parses() -> None:
    result = check_number(SMOKE_TOTAL)
    assert result.status == FieldStatus.OK
    assert result.value == 5168.40


def test_check_number_invalid_fails() -> None:
    result = check_number("abc")
    assert result.status == FieldStatus.FAILED_VALIDATION


def test_amounts_reconcile_smoke_values() -> None:
    assert amounts_reconcile(
        parse_indian_number(SMOKE_TAXABLE),
        Decimal("0"),
        Decimal("0"),
        parse_indian_number(SMOKE_GST),
        parse_indian_number(SMOKE_TOTAL),
    )


def test_arithmetic_reconciliation_smoke_values_ok() -> None:
    result = check_arithmetic_reconciliation(
        SMOKE_TAXABLE,
        "0.0",
        "0.0",
        SMOKE_GST,
        SMOKE_TOTAL,
    )
    assert result.status == FieldStatus.OK


def test_arithmetic_reconciliation_mismatch_low_confidence() -> None:
    result = check_arithmetic_reconciliation(
        "1000.00",
        "0.0",
        "0.0",
        "100.00",
        "5000.00",
    )
    assert result.status == FieldStatus.LOW_CONFIDENCE
    assert "do not reconcile" in (result.reason or "")


def test_tax_bucket_exclusivity_allows_igst_only() -> None:
    result = check_tax_bucket_exclusivity("0.0", "0.0", "788.40")
    assert result.status == FieldStatus.OK


def test_tax_bucket_exclusivity_allows_cgst_sgst_only() -> None:
    result = check_tax_bucket_exclusivity("394.20", "394.20", "0.0")
    assert result.status == FieldStatus.OK


def test_tax_bucket_exclusivity_rejects_mixed_buckets() -> None:
    result = check_tax_bucket_exclusivity("394.20", "394.20", "100.00")
    assert result.status == FieldStatus.FAILED_VALIDATION
    assert "invalid tax mix" in (result.reason or "")


def test_grounding_found_in_text_layer() -> None:
    text = "GSTIN 24ABMFA4190N1Z2 and total 5,168.40"
    result = check_grounding(SMOKE_GSTIN, text, is_scanned=False)
    assert result.status == FieldStatus.OK


def test_grounding_missing_value_low_confidence() -> None:
    text = "this invoice text layer is long enough to avoid the scanned heuristic"
    result = check_grounding("99ZZZZ9999Z9", text, is_scanned=False)
    assert result.status == FieldStatus.LOW_CONFIDENCE
    assert "not found in document text" in (result.reason or "")


def test_grounding_scanned_document_low_confidence() -> None:
    result = check_grounding(SMOKE_GSTIN, "", is_scanned=True)
    assert result.status == FieldStatus.LOW_CONFIDENCE
    assert result.reason == "scanned: cannot ground"


def test_grounding_ocr_text_layer_uses_fuzzy_match() -> None:
    gstin = "19ABSPT7889H1ZC"
    garbled_layer = "supplier gstin 19ab5pt7889h1zc"
    result = check_grounding(
        gstin,
        garbled_layer,
        is_scanned=True,
        text_layer_is_ocr=True,
    )
    assert result.status == FieldStatus.OK
