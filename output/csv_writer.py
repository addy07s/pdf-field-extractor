"""CSV output via pandas — one row per extracted invoice."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.field_config import FieldConfig
from models import DocumentResult, FieldResult, FieldStatus
from output.formatting import (
    display_field_value,
    format_flags,
    is_document_failed,
    overall_status_display,
)


def _build_rows(
    results: list[DocumentResult],
    field_configs: list[FieldConfig],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for document in results:
        row: dict[str, object] = {
            "Source File": document.source_filename,
            "Invoice #": document.invoice_index,
        }
        document_failed = is_document_failed(document)

        for field_config in field_configs:
            field_result = document.fields.get(field_config.key)
            if field_result is None:
                field_result = FieldResult(status=FieldStatus.NOT_FOUND)

            if document_failed or field_result.status == FieldStatus.NOT_FOUND:
                row[field_config.display_label] = ""
            else:
                value = display_field_value(field_result)
                row[field_config.display_label] = "" if value is None else value

        row["Overall Status"] = overall_status_display(document)
        row["Flags"] = format_flags(document, field_configs)
        rows.append(row)

    return rows


def write_csv(
    results: list[DocumentResult],
    field_configs: list[FieldConfig],
    output_path: Path | str,
) -> Path:
    """Write validated field values to CSV with a companion Flags column."""
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    columns = (
        ["Source File", "Invoice #"]
        + [field.display_label for field in field_configs]
        + ["Overall Status", "Flags"]
    )
    rows = _build_rows(results, field_configs)
    frame = pd.DataFrame(rows, columns=columns)
    frame.to_csv(out_path, index=False)
    return out_path
