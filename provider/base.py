"""Abstract vision-provider interface — one swappable extraction backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from config.field_config import FieldConfig


class VisionProvider(ABC):
    """Propose raw field values from page image(s) and optional text layer.

    The model proposes values only; deterministic code assigns trust later.
    One document may contain multiple invoices — ``extract`` returns one
    raw field map per invoice.
    """

    @abstractmethod
    async def extract(
        self,
        page_images: list[bytes],
        text_layer: str,
        field_configs: list[FieldConfig],
    ) -> list[dict[str, Any]]:
        """Return one raw field map per distinct invoice found in the document.

        Args:
            page_images: Rendered page images (PNG/JPEG), in page order.
            text_layer: Extracted text from the PDF text layer (may be empty for scans).
            field_configs: Active field definitions from fields.yaml.

        Returns:
            List of mappings field key → raw proposed value (one entry per invoice).
        """
        raise NotImplementedError
