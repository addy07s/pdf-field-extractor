"""API response models — thin wrappers over shared pipeline types."""

from __future__ import annotations

from pydantic import BaseModel, Field

from config.field_config import FieldConfig
from models import DocumentResult


class ConfigResponse(BaseModel):
    """Field layout and runtime settings for the React dashboard."""

    fields: list[FieldConfig]
    provider_label: str
    ocr_enabled: bool
    ocr_status: str
    batch_concurrency: int
    max_upload_count: int


class ExtractResponse(BaseModel):
    """Batch extraction outcome — one DocumentResult per extracted invoice.

    A single uploaded PDF may contribute multiple results (one row / invoice).
    Use ``source_filename`` + ``invoice_index`` as the stable identity when
    persisting rows to a database.
    """

    results: list[DocumentResult]
    excel_path: str = Field(description="Relative path to the generated Excel file")
    csv_path: str = Field(description="Relative path to the generated CSV file")
