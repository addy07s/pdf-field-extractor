"""Shared Pydantic models flowing extract → validate → output."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FieldStatus(str, Enum):
    """Per-field trust outcome assigned by deterministic validation."""

    OK = "OK"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NOT_FOUND = "NOT_FOUND"
    FAILED_VALIDATION = "FAILED_VALIDATION"


class DocumentStatus(str, Enum):
    """Aggregate outcome for a single source document."""

    OK = "OK"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class FieldResult(BaseModel):
    """Validated (or rejected) value for one configured field."""

    value: Any | None = None
    status: FieldStatus
    reason: str | None = None


class DocumentResult(BaseModel):
    """End-to-end result for one invoice document."""

    source_filename: str
    fields: dict[str, FieldResult] = Field(default_factory=dict)
    overall_status: DocumentStatus = DocumentStatus.OK
    error_message: str | None = None
