"""Gemini vision provider via the google-genai SDK."""

from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from config.field_config import FieldConfig
from provider.base import VisionProvider
from provider.errors import ProviderError

_ENV_API_KEY = "GEMINI_API_KEY"
_ENV_MODEL = "GEMINI_MODEL"

_SYSTEM_INSTRUCTION = (
    "You are extracting fields from an Indian GST tax invoice. "
    "For each requested field, return the exact value as it appears in the document, "
    "or null if it is not present or you cannot read it confidently. "
    "Exception for tax buckets: cgst_amount, sgst_amount, and igst_amount must always "
    "be numeric invoice grand totals — use 0.0 when that tax is not shown (never null). "
    "Never merge CGST/SGST/IGST into one field. Never extract per-line tax rates. "
    "Intra-state invoices use CGST+SGST with igst_amount=0.0; inter-state invoices use "
    "IGST with cgst_amount=0.0 and sgst_amount=0.0. "
    "Do NOT guess or fabricate other values. Return only the structured object."
)

_TAX_AMOUNT_KEYS = frozenset({"cgst_amount", "sgst_amount", "igst_amount"})

_MAX_RETRIES = 6
_BASE_BACKOFF_SEC = 1.0
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 503})


def build_field_guidance(field_configs: list[FieldConfig]) -> str:
    """Build per-field extraction guidance from YAML-driven configs."""
    lines = ["Extract the following fields from the attached invoice image:", ""]
    for field in field_configs:
        lines.append(f"- {field.key} ({field.display_label}): {field.description}")
    return "\n".join(lines)


def build_response_schema(field_configs: list[FieldConfig]) -> dict[str, Any]:
    """Build a JSON Schema object with one nullable string property per field key."""
    properties = {
        field.key: {
            "type": ["string", "null"],
            "description": field.description,
        }
        for field in field_configs
    }
    return {
        "type": "object",
        "properties": properties,
        "required": [field.key for field in field_configs],
        "additionalProperties": False,
    }


def build_generate_config(field_configs: list[FieldConfig]) -> types.GenerateContentConfig:
    """Build Gemini structured-output config from field configs."""
    return types.GenerateContentConfig(
        system_instruction=_SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_json_schema=build_response_schema(field_configs),
    )


def build_contents(
    image_bytes: bytes,
    field_configs: list[FieldConfig],
    *,
    mime_type: str = "image/png",
) -> list[types.Part | str]:
    """Build multimodal request contents: field guidance text + inline image."""
    return [
        build_field_guidance(field_configs),
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
    ]


def normalize_raw_values(
    parsed: dict[str, Any],
    field_configs: list[FieldConfig],
) -> dict[str, Any]:
    """Map model output to raw values; missing/blank strings become None.

    Tax bucket fields (CGST/SGST/IGST) default to ``\"0.0\"`` when missing —
    Indian GST extraction never returns null for those amounts.
    """
    normalized: dict[str, Any] = {}
    for field in field_configs:
        value = parsed.get(field.key)
        if value is None or (isinstance(value, str) and not value.strip()):
            if field.key in _TAX_AMOUNT_KEYS:
                normalized[field.key] = "0.0"
            else:
                normalized[field.key] = None
        else:
            normalized[field.key] = value
    return normalized


def parse_structured_response(
    response_text: str,
    field_configs: list[FieldConfig],
) -> dict[str, Any]:
    """Parse JSON model output into normalized raw field values."""
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Gemini returned invalid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ProviderError("Gemini response JSON must be an object")

    return normalize_raw_values(parsed, field_configs)


def _resolve_api_key(api_key: str | None) -> str:
    resolved = (api_key or os.getenv(_ENV_API_KEY, "")).strip()
    if not resolved:
        raise ProviderError(f"{_ENV_API_KEY} environment variable is not set")
    return resolved


def _resolve_model(model: str | None) -> str:
    resolved = (model or os.getenv(_ENV_MODEL, "")).strip()
    if not resolved:
        raise ProviderError(f"{_ENV_MODEL} environment variable is not set")
    return resolved


def _is_retryable(exc: genai_errors.APIError) -> bool:
    return exc.code in _RETRYABLE_STATUS_CODES


def _retry_backoff_seconds(attempt: int) -> float:
    """Exponential backoff with jitter: ~1s, 2s, 4s, 8s between attempts."""
    base_delay = _BASE_BACKOFF_SEC * (2**attempt)
    jitter = random.uniform(0, base_delay * 0.5)
    return base_delay + jitter


class CloudVisionProvider(VisionProvider):
    """Extract invoice fields using a Gemini vision model."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        client: genai.Client | None = None,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._model = _resolve_model(model)
        self._client = client
        self._max_retries = max_retries

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def extract(
        self,
        image_bytes: bytes,
        text_layer: str,
        field_configs: list[FieldConfig],
    ) -> dict[str, Any]:
        if not field_configs:
            return {}

        config = build_generate_config(field_configs)
        contents = build_contents(image_bytes, field_configs)

        try:
            response = await self._generate_with_retry(contents, config)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Gemini extraction failed: {exc}") from exc

        if not response.text:
            raise ProviderError("Gemini returned an empty response")

        return parse_structured_response(response.text, field_configs)

    async def _generate_with_retry(
        self,
        contents: list[types.Part | str],
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        client = self._get_client()
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                return await client.aio.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
            except genai_errors.APIError as exc:
                last_error = exc
                if _is_retryable(exc) and attempt < self._max_retries - 1:
                    delay = _retry_backoff_seconds(attempt)
                    await asyncio.sleep(delay)
                    continue
                raise ProviderError(
                    f"Gemini API error (HTTP {exc.code}): {exc}"
                ) from exc
            except Exception as exc:
                raise ProviderError(f"Gemini API request failed: {exc}") from exc

        raise ProviderError(f"Gemini API request failed after retries: {last_error}")
