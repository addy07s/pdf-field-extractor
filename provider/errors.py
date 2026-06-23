"""Provider-level errors — catchable by the pipeline for per-document FAILED rows."""

from __future__ import annotations


class ProviderError(Exception):
    """Raised when a vision provider cannot complete extraction."""
