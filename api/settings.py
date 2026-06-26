"""API runtime settings — mirrors Streamlit app env handling."""

from __future__ import annotations

import os
from pathlib import Path

MAX_UPLOAD_COUNT = 100
OUTPUT_DIR = Path("outputs")
DEFAULT_BATCH_CONCURRENCY = 1
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"


def batch_concurrency() -> int:
    raw = os.getenv("BATCH_CONCURRENCY", str(DEFAULT_BATCH_CONCURRENCY)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_BATCH_CONCURRENCY
    return max(1, value)


def cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).strip()
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def provider_label() -> str:
    provider_name = os.getenv("VISION_PROVIDER", "cloud").strip().lower()
    if provider_name == "ollama":
        model = os.getenv("OLLAMA_MODEL", "llava")
        return f"Ollama (local) — {model}"
    model = os.getenv("GEMINI_MODEL", "(model not set)")
    return f"Gemini (cloud) — {model}"
