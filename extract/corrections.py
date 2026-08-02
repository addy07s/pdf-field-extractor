"""Post-extraction corrections using exact values from the document text layer."""

from __future__ import annotations

import logging
import re
from typing import Any

from sources.pdf_source import DocumentSource
from validate.checks import is_text_layer_near_empty, validate_gstin_checksum

logger = logging.getLogger(__name__)

_SUPPLIER_GSTIN_KEY = "supplier_gstin"
_RECIPIENT_GSTIN_KEY = "recipient_gstin"
_GSTIN_KEYS = (_SUPPLIER_GSTIN_KEY, _RECIPIENT_GSTIN_KEY)
_PAN_KEY = "pan"

_GSTIN_SEARCH_PATTERN = re.compile(
    r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]",
    re.IGNORECASE,
)
_PAN_SEARCH_PATTERN = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]", re.IGNORECASE)
_PAN_FULL_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def find_valid_gstins_in_text(text_layer: str) -> list[str]:
    """Return unique checksum-valid GSTINs found in the text layer."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _GSTIN_SEARCH_PATTERN.finditer(text_layer.upper()):
        gstin = match.group(0).upper()
        if gstin in seen:
            continue
        seen.add(gstin)
        if validate_gstin_checksum(gstin):
            found.append(gstin)
    return found


def find_valid_pans_in_text(text_layer: str) -> list[str]:
    """Return unique PAN-shaped strings found in the text layer."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _PAN_SEARCH_PATTERN.finditer(text_layer.upper()):
        pan = match.group(0).upper()
        if not _PAN_FULL_PATTERN.match(pan) or pan in seen:
            continue
        seen.add(pan)
        found.append(pan)
    return found


def _normalize_field_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _choose_text_layer_value(
    field_key: str,
    ai_value: str | None,
    text_candidates: list[str],
    *,
    allow_single_candidate_replace: bool = True,
) -> str | None:
    """Apply GSTIN/PAN correction rules without fabricating values."""
    if not text_candidates or ai_value is None:
        return ai_value

    if ai_value in text_candidates:
        return ai_value

    if allow_single_candidate_replace and len(text_candidates) == 1:
        text_value = text_candidates[0]
        if ai_value != text_value:
            logger.info(
                "Corrected %s from %s to %s using document text layer",
                field_key,
                ai_value,
                text_value,
            )
            return text_value
        return ai_value

    return ai_value


def apply_text_layer_corrections(
    raw_fields: dict[str, Any],
    document: DocumentSource,
    *,
    allow_single_gstin_replace: bool = True,
) -> dict[str, Any]:
    """Prefer exact text-layer GSTIN/PAN values over misread AI proposals.

    Does nothing when the document has no usable text layer (native or OCR).
    Never fabricates: only substitutes values regex-matched in the text layer.

    With separate supplier/recipient GSTINs, a lone text-layer GSTIN may only
    auto-correct ``supplier_gstin`` — never invent a recipient GSTIN.

    When ``allow_single_gstin_replace`` is False (multi-invoice documents), a
    lone text GSTIN will not overwrite a mismatched AI supplier GSTIN — that
    value may belong to a different invoice in the same PDF.
    """
    if is_text_layer_near_empty(document.text_layer):
        return raw_fields

    corrected = dict(raw_fields)
    text_layer = document.text_layer
    text_gstins = find_valid_gstins_in_text(text_layer)

    for gstin_key in _GSTIN_KEYS:
        if gstin_key not in corrected:
            continue
        ai_gstin = _normalize_field_value(corrected.get(gstin_key))
        # Only supplier may be replaced from a single unmatched text GSTIN.
        allow_replace = (
            allow_single_gstin_replace and gstin_key == _SUPPLIER_GSTIN_KEY
        )
        corrected[gstin_key] = _choose_text_layer_value(
            gstin_key,
            ai_gstin,
            text_gstins,
            allow_single_candidate_replace=allow_replace,
        )

    if _PAN_KEY in corrected:
        text_pans = find_valid_pans_in_text(text_layer)
        ai_pan = _normalize_field_value(corrected.get(_PAN_KEY))
        corrected[_PAN_KEY] = _choose_text_layer_value(
            _PAN_KEY,
            ai_pan,
            text_pans,
        )

    return corrected
