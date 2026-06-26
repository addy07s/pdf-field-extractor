"""Shared dependencies — provider construction and upload persistence."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import UploadFile

from provider import CloudVisionProvider, OllamaVisionProvider
from provider.base import VisionProvider


def build_provider() -> VisionProvider:
    """Select cloud or Ollama provider based on VISION_PROVIDER env flag."""
    provider_name = os.getenv("VISION_PROVIDER", "cloud").strip().lower()
    if provider_name == "ollama":
        return OllamaVisionProvider(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "llava"),
        )
    return CloudVisionProvider(
        api_key=os.getenv("GEMINI_API_KEY"),
        model=os.getenv("GEMINI_MODEL"),
    )


async def save_uploads(files: list[UploadFile]) -> tuple[Path, list[Path]]:
    """Write uploaded invoice files to a temp directory; caller must clean up."""
    temp_dir = Path(tempfile.mkdtemp(prefix="invoice_upload_"))
    paths: list[Path] = []
    used_names: set[str] = set()

    for index, uploaded in enumerate(files, start=1):
        filename = Path(uploaded.filename or f"upload_{index}").name
        if filename in used_names:
            filename = f"{index}_{filename}"
        used_names.add(filename)
        target = temp_dir / filename
        target.write_bytes(await uploaded.read())
        paths.append(target)

    return temp_dir, paths


def cleanup_temp_dir(temp_dir: Path) -> None:
    shutil.rmtree(temp_dir, ignore_errors=True)
