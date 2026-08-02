"""Deterministic validation — grounding, checksums, arithmetic, per-field status."""

from __future__ import annotations

from typing import Any

from config.field_config import FieldConfig
from models import DocumentResult, DocumentStatus, FieldResult, FieldStatus
from sources.pdf_source import DocumentSource
from validate.checks import (
    CheckResult,
    check_arithmetic_reconciliation,
    check_date,
    check_gstin,
    check_gstin_pan_crosscheck,
    check_grounding,
    check_number,
    check_pan,
    check_tax_bucket_exclusivity,
    is_text_layer_near_empty,
    merge_check_results,
    worst_status,
)

_SUPPLIER_GSTIN_KEY = "supplier_gstin"
_PAN_KEY = "pan"
_TAXABLE_KEY = "total_taxable_value"
_CGST_KEY = "cgst_amount"
_SGST_KEY = "sgst_amount"
_IGST_KEY = "igst_amount"
_TOTAL_KEY = "total_invoice_value"
_TAX_AMOUNT_KEYS = frozenset({_CGST_KEY, _SGST_KEY, _IGST_KEY})
_AMOUNT_CROSSCHECK_KEYS = (
    _TAXABLE_KEY,
    _CGST_KEY,
    _SGST_KEY,
    _IGST_KEY,
    _TOTAL_KEY,
)


def default_missing_tax_amounts(
    raw_fields: dict[str, Any],
    field_configs: list[FieldConfig],
) -> dict[str, Any]:
    """Missing CGST/SGST/IGST buckets become 0.0 — never null."""
    configured_keys = {field.key for field in field_configs}
    updated = dict(raw_fields)
    for key in _TAX_AMOUNT_KEYS:
        if key not in configured_keys:
            continue
        value = updated.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            updated[key] = "0.0"
    return updated


def _apply_validator(
    validator_name: str,
    raw_value: Any,
    text_layer: str,
    *,
    is_scanned: bool,
    text_layer_is_ocr: bool,
) -> CheckResult:
    if validator_name == "grounding":
        return check_grounding(
            raw_value,
            text_layer,
            is_scanned=is_scanned,
            text_layer_is_ocr=text_layer_is_ocr,
        )
    if validator_name == "gstin":
        return check_gstin(raw_value)
    if validator_name == "pan":
        return check_pan(raw_value)
    if validator_name == "date":
        return check_date(raw_value)
    if validator_name == "number":
        return check_number(raw_value)
    if validator_name == "none":
        return CheckResult(status=FieldStatus.OK, value=raw_value)
    raise ValueError(f"Unknown validator: {validator_name}")


def _validate_single_field(
    raw_value: Any,
    field_config: FieldConfig,
    text_layer: str,
    *,
    is_scanned: bool,
    text_layer_is_ocr: bool,
) -> FieldResult:
    if raw_value is None:
        return FieldResult(status=FieldStatus.NOT_FOUND, reason="field not extracted")

    status = FieldStatus.OK
    reason: str | None = None
    value: Any = raw_value

    for validator_name in field_config.validators:
        check = _apply_validator(
            validator_name,
            raw_value,
            text_layer,
            is_scanned=is_scanned,
            text_layer_is_ocr=text_layer_is_ocr,
        )
        status, reason, value = merge_check_results(status, reason, value, check)

    return FieldResult(value=value, status=status, reason=reason)


def _apply_document_crosschecks(
    field_results: dict[str, FieldResult],
    raw_fields: dict[str, Any],
) -> None:
    gstin_raw = raw_fields.get(_SUPPLIER_GSTIN_KEY)
    pan_raw = raw_fields.get(_PAN_KEY)
    if gstin_raw is not None and pan_raw is not None:
        cross = check_gstin_pan_crosscheck(str(gstin_raw), str(pan_raw))
        if cross.status == FieldStatus.FAILED_VALIDATION:
            for key in (_SUPPLIER_GSTIN_KEY, _PAN_KEY):
                existing = field_results[key]
                status = worst_status(existing.status, cross.status)
                reasons = [r for r in (existing.reason, cross.reason) if r]
                field_results[key] = FieldResult(
                    value=existing.value,
                    status=status,
                    reason="; ".join(dict.fromkeys(reasons)) if reasons else cross.reason,
                )


def _amount_fields_ready_for_crosscheck(
    field_results: dict[str, FieldResult],
) -> bool:
    for key in _AMOUNT_CROSSCHECK_KEYS:
        result = field_results.get(key)
        if result is None or result.status == FieldStatus.NOT_FOUND:
            return False
        if result.status == FieldStatus.FAILED_VALIDATION:
            return False
    return True


def _flag_amount_fields(
    field_results: dict[str, FieldResult],
    keys: tuple[str, ...],
    check: CheckResult,
) -> None:
    for key in keys:
        existing = field_results[key]
        status = worst_status(existing.status, check.status)
        reasons = [r for r in (existing.reason, check.reason) if r]
        field_results[key] = FieldResult(
            value=existing.value,
            status=status,
            reason="; ".join(dict.fromkeys(reasons)) if reasons else check.reason,
        )


def _apply_tax_and_arithmetic_checks(
    field_results: dict[str, FieldResult],
    raw_fields: dict[str, Any],
) -> None:
    taxable_raw = raw_fields.get(_TAXABLE_KEY)
    cgst_raw = raw_fields.get(_CGST_KEY)
    sgst_raw = raw_fields.get(_SGST_KEY)
    igst_raw = raw_fields.get(_IGST_KEY)
    total_raw = raw_fields.get(_TOTAL_KEY)
    if any(
        value is None
        for value in (taxable_raw, cgst_raw, sgst_raw, igst_raw, total_raw)
    ):
        return

    if not _amount_fields_ready_for_crosscheck(field_results):
        return

    exclusivity = check_tax_bucket_exclusivity(cgst_raw, sgst_raw, igst_raw)
    if exclusivity.status == FieldStatus.FAILED_VALIDATION:
        _flag_amount_fields(
            field_results,
            (_CGST_KEY, _SGST_KEY, _IGST_KEY),
            exclusivity,
        )
        return

    arithmetic = check_arithmetic_reconciliation(
        taxable_raw,
        cgst_raw,
        sgst_raw,
        igst_raw,
        total_raw,
    )
    if arithmetic.status == FieldStatus.LOW_CONFIDENCE:
        _flag_amount_fields(field_results, _AMOUNT_CROSSCHECK_KEYS, arithmetic)


def _compute_overall_status(field_results: dict[str, FieldResult]) -> DocumentStatus:
    if not field_results:
        return DocumentStatus.FAILED
    if all(result.status == FieldStatus.OK for result in field_results.values()):
        return DocumentStatus.OK
    return DocumentStatus.PARTIAL


def validate_fields(
    source_filename: str,
    raw_fields: dict[str, Any],
    field_configs: list[FieldConfig],
    text_layer: str,
    *,
    is_scanned: bool | None = None,
    text_layer_is_ocr: bool = False,
    invoice_index: int = 1,
) -> DocumentResult:
    """Validate raw extracted values and assign per-field trust status."""
    scanned = (
        is_text_layer_near_empty(text_layer)
        if is_scanned is None
        else is_scanned
    )

    raw_fields = default_missing_tax_amounts(raw_fields, field_configs)

    field_results: dict[str, FieldResult] = {}
    for field_config in field_configs:
        raw_value = raw_fields.get(field_config.key)
        field_results[field_config.key] = _validate_single_field(
            raw_value,
            field_config,
            text_layer,
            is_scanned=scanned,
            text_layer_is_ocr=text_layer_is_ocr,
        )

    _apply_document_crosschecks(field_results, raw_fields)
    _apply_tax_and_arithmetic_checks(field_results, raw_fields)

    return DocumentResult(
        source_filename=source_filename,
        invoice_index=invoice_index,
        fields=field_results,
        overall_status=_compute_overall_status(field_results),
    )


def validate_document(
    source_filename: str,
    raw_fields: dict[str, Any],
    field_configs: list[FieldConfig],
    document: DocumentSource,
    *,
    invoice_index: int = 1,
) -> DocumentResult:
    """Validate raw fields using text layer and scan heuristic from a loaded document."""
    return validate_fields(
        source_filename,
        raw_fields,
        field_configs,
        document.text_layer,
        is_scanned=document.is_scanned,
        text_layer_is_ocr=document.text_layer_is_ocr,
        invoice_index=invoice_index,
    )
