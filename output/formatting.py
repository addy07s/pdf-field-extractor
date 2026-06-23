"""Shared display-value and flag formatting for output writers."""

from __future__ import annotations

from typing import Any

from config.field_config import FieldConfig
from models import DocumentResult, DocumentStatus, FieldResult, FieldStatus


def display_field_value(field_result: FieldResult) -> Any | None:
    """Return the cleaned value to write in output cells."""
    if field_result.status == FieldStatus.NOT_FOUND:
        return None

    value = field_result.value
    if value is None:
        return None

    if isinstance(value, dict) and "normalized" in value:
        return value["normalized"]

    return value


def format_flags(
    document: DocumentResult,
    field_configs: list[FieldConfig],
) -> str:
    """Build CSV Flags column text for non-OK fields."""
    if document.overall_status == DocumentStatus.FAILED and document.error_message:
        parts = [f"document: FAILED ({document.error_message})"]
    else:
        parts = []

    for field_config in field_configs:
        field_result = document.fields.get(field_config.key)
        if field_result is None or field_result.status == FieldStatus.OK:
            continue
        reason = f" ({field_result.reason})" if field_result.reason else ""
        parts.append(f"{field_config.key}: {field_result.status.value}{reason}")

    return "; ".join(parts)


def overall_status_display(document: DocumentResult) -> str:
    """Format document-level status for output columns."""
    if document.overall_status == DocumentStatus.FAILED and document.error_message:
        return f"FAILED: {document.error_message}"
    return document.overall_status.value


def is_document_failed(document: DocumentResult) -> bool:
    return document.overall_status == DocumentStatus.FAILED
