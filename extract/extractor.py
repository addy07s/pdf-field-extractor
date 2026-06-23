"""Build schema + prompt from YAML, call vision provider, return raw proposals."""

from __future__ import annotations

from typing import Any

from config.field_config import FieldConfig
from provider.base import VisionProvider
from sources.pdf_source import DocumentSource


async def extract_raw_fields(
    document: DocumentSource,
    field_configs: list[FieldConfig],
    provider: VisionProvider,
) -> dict[str, Any]:
    """Propose field values for a document using the configured vision provider.

    TODO:
      - Merge text layers across pages for grounding context.
      - Build JSON schema and system prompt from field_configs.
      - Call provider per page (or primary page) and merge proposals.
    """
    raise NotImplementedError("Field extraction not yet implemented")
