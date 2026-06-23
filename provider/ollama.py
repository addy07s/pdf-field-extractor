"""Local Ollama vision provider — no API key, fully private fallback."""

from __future__ import annotations

from typing import Any

from config.field_config import FieldConfig
from provider.base import VisionProvider


class OllamaVisionProvider(VisionProvider):
    """Call a local Ollama vision model via its HTTP API."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llava") -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def extract(
        self,
        image_bytes: bytes,
        text_layer: str,
        field_configs: list[FieldConfig],
    ) -> dict[str, Any]:
        # TODO: Build JSON schema + prompt from field_configs, POST to Ollama /api/chat.
        raise NotImplementedError("Ollama vision extraction not yet implemented")
