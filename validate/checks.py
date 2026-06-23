"""Pure validation helpers — individually unit-tested, no side effects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from models import FieldStatus

_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)
_PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_NAMED_MONTH_DATE_PATTERN = re.compile(r"^(\d{1,2})-([A-Za-z]{3,})-(\d{2,4})$")
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d.%m.%Y",
    "%d.%m.%y",
)
_SCANNED_TEXT_THRESHOLD = 20
_ARITHMETIC_TOLERANCE = Decimal("1.00")
_CURRENCY_SYMBOLS = "₹$€£"


@dataclass(frozen=True)
class CheckResult:
    """Outcome of a single validator check."""

    status: FieldStatus
    reason: str | None = None
    value: Any | None = None


def non_whitespace_length(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def is_text_layer_near_empty(text_layer: str) -> bool:
    return non_whitespace_length(text_layer) < _SCANNED_TEXT_THRESHOLD


def normalize_for_grounding(value: Any) -> str:
    """Normalize a value for substring search in the text layer."""
    text = str(value).strip().lower()
    if _looks_numeric(text):
        text = text.replace(",", "")
    return text


def _looks_numeric(text: str) -> bool:
    stripped = text.strip()
    for symbol in _CURRENCY_SYMBOLS:
        stripped = stripped.replace(symbol, "")
    stripped = stripped.replace(",", "").replace(" ", "")
    if not stripped:
        return False
    try:
        Decimal(stripped)
        return True
    except InvalidOperation:
        return False


def normalize_text_layer(text_layer: str) -> str:
    text = text_layer.lower()
    return re.sub(r"(?<=\d),(?=\d)", "", text)


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            replace_cost = previous[j - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def _ocr_grounding_tolerance(value: str) -> int:
    length = len(value)
    if length <= 6:
        return 1
    if length <= 12:
        return 2
    return 3


def is_value_grounded_fuzzy(normalized_value: str, normalized_layer: str) -> bool:
    """Return True when value appears in OCR text within a small edit-distance tolerance."""
    if not normalized_value:
        return False
    if normalized_value in normalized_layer:
        return True

    tolerance = _ocr_grounding_tolerance(normalized_value)
    value_len = len(normalized_value)
    if value_len == 0 or len(normalized_layer) < value_len:
        return False

    for index in range(0, len(normalized_layer) - value_len + 1):
        window = normalized_layer[index : index + value_len]
        if _levenshtein_distance(normalized_value, window) <= tolerance:
            return True
    return False


def check_grounding(
    value: Any,
    text_layer: str,
    *,
    is_scanned: bool,
    text_layer_is_ocr: bool = False,
) -> CheckResult:
    if is_text_layer_near_empty(text_layer):
        return CheckResult(
            status=FieldStatus.LOW_CONFIDENCE,
            reason="scanned: cannot ground",
        )

    normalized_value = normalize_for_grounding(value)
    normalized_layer = normalize_text_layer(text_layer)
    if normalized_value and normalized_value in normalized_layer:
        return CheckResult(status=FieldStatus.OK)

    if text_layer_is_ocr and is_value_grounded_fuzzy(
        normalized_value,
        normalized_layer,
    ):
        return CheckResult(status=FieldStatus.OK)

    return CheckResult(
        status=FieldStatus.LOW_CONFIDENCE,
        reason="value not found in document text — may be computed or misread",
    )


def _gstin_char_value(char: str) -> int:
    return _GSTIN_CHARS.index(char)


def validate_gstin_checksum(gstin: str) -> bool:
    """Return True when the 15th character matches the official GSTIN checksum."""
    gstin = gstin.upper()
    if len(gstin) != 15:
        return False

    factor = 1
    total = 0
    for index in range(14):
        code_point = _gstin_char_value(gstin[index])
        addend = factor * code_point
        factor = 2 if factor == 1 else 1
        addend = (addend // 36) + (addend % 36)
        total += addend

    checksum_index = (36 - (total % 36)) % 36
    return _GSTIN_CHARS[checksum_index] == gstin[14]


def check_gstin(value: Any) -> CheckResult:
    gstin = str(value).strip().upper()
    if len(gstin) != 15 or not _GSTIN_PATTERN.match(gstin):
        return CheckResult(
            status=FieldStatus.FAILED_VALIDATION,
            reason="GSTIN checksum failed",
            value=gstin,
        )
    if not validate_gstin_checksum(gstin):
        return CheckResult(
            status=FieldStatus.FAILED_VALIDATION,
            reason="GSTIN checksum failed",
            value=gstin,
        )
    return CheckResult(status=FieldStatus.OK, value=gstin)


def check_pan(value: Any) -> CheckResult:
    pan = str(value).strip().upper()
    if not _PAN_PATTERN.match(pan):
        return CheckResult(
            status=FieldStatus.FAILED_VALIDATION,
            reason="invalid PAN structure",
            value=pan,
        )
    return CheckResult(status=FieldStatus.OK, value=pan)


def extract_pan_from_gstin(gstin: str) -> str:
    return gstin.strip().upper()[2:12]


def check_gstin_pan_crosscheck(gstin: str, pan: str) -> CheckResult:
    gstin_upper = gstin.strip().upper()
    pan_upper = pan.strip().upper()
    embedded_pan = extract_pan_from_gstin(gstin_upper)
    if embedded_pan != pan_upper:
        return CheckResult(
            status=FieldStatus.FAILED_VALIDATION,
            reason="GSTIN/PAN mismatch",
            value=None,
        )
    return CheckResult(status=FieldStatus.OK, value=None)


def _normalize_date_input(raw: str) -> str:
    """Normalize month-name dates so ``%b`` parsing accepts varied casing."""
    match = _NAMED_MONTH_DATE_PATTERN.match(raw)
    if not match:
        return raw

    day, month, year = match.groups()
    month_abbr = month[:3].title()
    return f"{day}-{month_abbr}-{year}"


def check_date(value: Any) -> CheckResult:
    raw = str(value).strip()
    candidate = _normalize_date_input(raw)
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(candidate, fmt)
            normalized = parsed.date().isoformat()
            return CheckResult(
                status=FieldStatus.OK,
                value={"original": raw, "normalized": normalized},
            )
        except ValueError:
            continue

    return CheckResult(
        status=FieldStatus.FAILED_VALIDATION,
        reason="invalid date format",
        value=raw,
    )


def parse_indian_number(value: Any) -> Decimal:
    text = str(value).strip()
    for symbol in _CURRENCY_SYMBOLS:
        text = text.replace(symbol, "")
    text = text.replace(",", "").replace(" ", "")
    if not text:
        raise InvalidOperation("empty number")
    return Decimal(text)


def check_number(value: Any) -> CheckResult:
    try:
        parsed = parse_indian_number(value)
    except (InvalidOperation, ValueError):
        return CheckResult(
            status=FieldStatus.FAILED_VALIDATION,
            reason="invalid number format",
            value=value,
        )
    return CheckResult(status=FieldStatus.OK, value=float(parsed))


def amounts_reconcile(
    taxable: Decimal | float,
    gst: Decimal | float,
    total: Decimal | float,
    *,
    tolerance: Decimal = _ARITHMETIC_TOLERANCE,
) -> bool:
    taxable_dec = Decimal(str(taxable))
    gst_dec = Decimal(str(gst))
    total_dec = Decimal(str(total))
    return abs((taxable_dec + gst_dec) - total_dec) <= tolerance


def check_arithmetic_reconciliation(
    taxable_value: Any,
    gst_value: Any,
    total_value: Any,
) -> CheckResult:
    try:
        taxable = parse_indian_number(taxable_value)
        gst = parse_indian_number(gst_value)
        total = parse_indian_number(total_value)
    except (InvalidOperation, ValueError):
        return CheckResult(status=FieldStatus.OK, value=None)

    if amounts_reconcile(taxable, gst, total):
        return CheckResult(status=FieldStatus.OK, value=None)

    return CheckResult(
        status=FieldStatus.LOW_CONFIDENCE,
        reason="amounts do not reconcile: taxable + GST ≠ total",
        value=None,
    )


def worst_status(left: FieldStatus, right: FieldStatus) -> FieldStatus:
    priority = {
        FieldStatus.OK: 0,
        FieldStatus.NOT_FOUND: 1,
        FieldStatus.LOW_CONFIDENCE: 2,
        FieldStatus.FAILED_VALIDATION: 3,
    }
    return left if priority[left] >= priority[right] else right


def merge_check_results(
    current_status: FieldStatus,
    current_reason: str | None,
    current_value: Any,
    check: CheckResult,
) -> tuple[FieldStatus, str | None, Any]:
    status = worst_status(current_status, check.status)
    reasons: list[str] = []
    if current_reason:
        reasons.append(current_reason)
    if check.reason and check.reason not in reasons:
        reasons.append(check.reason)

    value = current_value
    if check.status == FieldStatus.OK and check.value is not None:
        value = check.value

    return status, ("; ".join(reasons) if reasons else None), value
