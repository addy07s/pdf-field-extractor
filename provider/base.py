"""Abstract vision-provider interface — one swappable extraction backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from config.field_config import FieldConfig


class VisionProvider(ABC):
    """Propose raw field values from a page image and optional text layer.

  The model proposes values only; deterministic code assigns trust later.
  """

    @abstractmethod
    async def extract(
        self,
        image_bytes: bytes,
        text_layer: str,
        field_configs: list[FieldConfig],
    ) -> dict[str, Any]:
        """Return proposed raw values keyed by field ``key``.

        Args:
            image_bytes: Rendered page image (PNG/JPEG) for the vision model.
            text_layer: Extracted text from the PDF text layer (may be empty for scans).
            field_configs: Active field definitions from fields.yaml.

        Returns:
            Mapping of field key → raw proposed value (type depends on data_type).
        """
        raise NotImplementedError
