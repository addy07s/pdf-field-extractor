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
    "You are extracting fields from Indian GST tax invoice document(s). "
    "A single uploaded PDF or image set may contain one invoice or many separate "
    "invoices (for example distinct invoice numbers, dates, supplier headers, or "
    "page breaks). Scan every attached page carefully and identify each distinct "
    "invoice. Return one structured object per invoice inside the top-level "
    "`invoices` array — if the document has N invoices, `invoices` must contain "
    "exactly N objects (never merge multiple invoices into one object). "
    "For each invoice object and each requested field, return the exact value as "
    "it appears on that invoice, or null if it is not present or you cannot read "
    "it confidently. "
    "Exception for tax buckets: cgst_amount, sgst_amount, and igst_amount must always "
    "be numeric invoice grand totals — use 0.0 when that tax is not shown (never null). "
    "Never merge CGST/SGST/IGST into one field. Never extract per-line tax rates. "
    "Intra-state invoices use CGST+SGST with igst_amount=0.0; inter-state invoices use "
    "IGST with cgst_amount=0.0 and sgst_amount=0.0. "
    "For every invoice, total_taxable_value + cgst_amount + sgst_amount + igst_amount "
    "must equal total_invoice_value. "
    "Do NOT guess or fabricate other values. Return only the structured object with "
    "an `invoices` array."
)

_TAX_AMOUNT_KEYS = frozenset({"cgst_amount", "sgst_amount", "igst_amount"})

_MAX_RETRIES = 6
_BASE_BACKOFF_SEC = 1.0
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 503})
_MAX_PAGES_PER_REQUEST = 30


def build_invoice_item_schema(field_configs: list[FieldConfig]) -> dict[str, Any]:
    """Build the per-invoice JSON Schema object (field keys → nullable string)."""
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


def build_field_guidance(field_configs: list[FieldConfig]) -> str:
    """Build per-field extraction guidance from YAML-driven configs."""
    lines = [
        "Scan every attached page and extract EVERY distinct Indian GST invoice.",
        "Return JSON shaped as {\"invoices\": [ /* one object per invoice */ ]}.",
        "If there is only one invoice, still return a one-element invoices array.",
        "Do not combine separate invoices. Fields to extract for each invoice:",
        "",
    ]
    for field in field_configs:
        lines.append(f"- {field.key} ({field.display_label}): {field.description}")
    return "\n".join(lines)


def build_response_schema(field_configs: list[FieldConfig]) -> dict[str, Any]:
    """Build wrapper JSON Schema: ``{ invoices: [ InvoiceData, ... ] }``."""
    invoice_schema = build_invoice_item_schema(field_configs)
    return {
        "type": "object",
        "properties": {
            "invoices": {
                "type": "array",
                "description": (
                    "One entry per distinct invoice found in the document. "
                    "Length must equal the number of invoices (1 or more)."
                ),
                "items": invoice_schema,
                "minItems": 1,
            }
        },
        "required": ["invoices"],
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
    page_images: list[bytes],
    field_configs: list[FieldConfig],
    *,
    mime_type: str = "image/png",
) -> list[types.Part | str]:
    """Build multimodal request: field guidance + one inline image per page."""
    if not page_images:
        raise ProviderError("At least one page image is required for extraction")

    contents: list[types.Part | str] = [build_field_guidance(field_configs)]
    for index, image_bytes in enumerate(page_images, start=1):
        contents.append(f"Page {index} of {len(page_images)}:")
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
    return contents


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


def _looks_like_flat_invoice(parsed: dict[str, Any], field_configs: list[FieldConfig]) -> bool:
    """True when the object looks like a single invoice field map (legacy shape)."""
    if "invoices" in parsed:
        return False
    field_keys = {field.key for field in field_configs}
    return bool(field_keys.intersection(parsed.keys()))


def parse_structured_response(
    response_text: str,
    field_configs: list[FieldConfig],
) -> list[dict[str, Any]]:
    """Parse JSON model output into a list of normalized invoice field maps."""
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Gemini returned invalid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ProviderError("Gemini response JSON must be an object")

    if "invoices" in parsed:
        invoices = parsed["invoices"]
        if not isinstance(invoices, list):
            raise ProviderError("Gemini response `invoices` must be an array")
        if not invoices:
            raise ProviderError("Gemini returned an empty `invoices` array")
        normalized_invoices: list[dict[str, Any]] = []
        for index, item in enumerate(invoices, start=1):
            if not isinstance(item, dict):
                raise ProviderError(
                    f"Gemini invoice object at index {index} must be an object"
                )
            normalized_invoices.append(normalize_raw_values(item, field_configs))
        return normalized_invoices

    # Backward compatibility: flat single-invoice object.
    if _looks_like_flat_invoice(parsed, field_configs):
        return [normalize_raw_values(parsed, field_configs)]

    raise ProviderError(
        "Gemini response must include an `invoices` array "
        "(or a flat single-invoice field object)"
    )


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
        max_pages: int = _MAX_PAGES_PER_REQUEST,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._model = _resolve_model(model)
        self._client = client
        self._max_retries = max_retries
        self._max_pages = max_pages

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def extract(
        self,
        page_images: list[bytes],
        text_layer: str,
        field_configs: list[FieldConfig],
    ) -> list[dict[str, Any]]:
        if not field_configs:
            return []
        if not page_images:
            raise ProviderError("At least one page image is required for extraction")

        images = page_images
        if len(images) > self._max_pages:
            images = images[: self._max_pages]

        config = build_generate_config(field_configs)
        contents = build_contents(images, field_configs)

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
