"""Tests for the Gemini cloud vision provider."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import types

from config.field_config import FieldConfig
from provider.cloud import (
    CloudVisionProvider,
    build_contents,
    build_field_guidance,
    build_generate_config,
    build_response_schema,
    normalize_raw_values,
    parse_structured_response,
)
from provider.errors import ProviderError

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def sample_field_configs() -> list[FieldConfig]:
    return [
        FieldConfig(
            key="gstin",
            display_label="GSTIN",
            description="the supplier's 15-character GST identification number",
            data_type="string",
            validators=["gstin", "grounding"],
        ),
        FieldConfig(
            key="total_amount",
            display_label="Total Amount",
            description="invoice grand total payable in INR including taxes",
            data_type="number",
            validators=["number", "grounding"],
        ),
    ]


def test_build_response_schema_from_field_configs(
    sample_field_configs: list[FieldConfig],
) -> None:
    schema = build_response_schema(sample_field_configs)

    assert schema["type"] == "object"
    assert schema["required"] == ["gstin", "total_amount"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["gstin"] == {
        "type": ["string", "null"],
        "description": sample_field_configs[0].description,
    }
    assert schema["properties"]["total_amount"]["type"] == ["string", "null"]


def test_build_field_guidance_includes_all_fields(
    sample_field_configs: list[FieldConfig],
) -> None:
    guidance = build_field_guidance(sample_field_configs)

    assert "gstin (GSTIN)" in guidance
    assert "15-character GST identification number" in guidance
    assert "total_amount (Total Amount)" in guidance


def test_build_generate_config_uses_structured_json_output(
    sample_field_configs: list[FieldConfig],
) -> None:
    config = build_generate_config(sample_field_configs)

    assert config.response_mime_type == "application/json"
    assert config.response_json_schema is not None
    assert "gstin" in config.response_json_schema["properties"]


def test_build_contents_includes_image_part(
    sample_field_configs: list[FieldConfig],
) -> None:
    contents = build_contents(PNG_BYTES, sample_field_configs)

    assert len(contents) == 2
    assert isinstance(contents[0], str)
    assert isinstance(contents[1], types.Part)


def test_null_response_maps_to_none(sample_field_configs: list[FieldConfig]) -> None:
    parsed = parse_structured_response(
        json.dumps({"gstin": None, "total_amount": "1180.00"}),
        sample_field_configs,
    )

    assert parsed["gstin"] is None
    assert parsed["total_amount"] == "1180.00"


def test_empty_string_maps_to_none(sample_field_configs: list[FieldConfig]) -> None:
    parsed = normalize_raw_values(
        {"gstin": "  ", "total_amount": "500"},
        sample_field_configs,
    )

    assert parsed["gstin"] is None
    assert parsed["total_amount"] == "500"


def test_missing_tax_buckets_normalize_to_zero() -> None:
    configs = [
        FieldConfig(
            key="cgst_amount",
            display_label="CGST Amount",
            description="total CGST",
            data_type="number",
            validators=["number"],
        ),
        FieldConfig(
            key="sgst_amount",
            display_label="SGST Amount",
            description="total SGST",
            data_type="number",
            validators=["number"],
        ),
        FieldConfig(
            key="igst_amount",
            display_label="IGST Amount",
            description="total IGST",
            data_type="number",
            validators=["number"],
        ),
    ]

    parsed = normalize_raw_values(
        {"cgst_amount": None, "sgst_amount": "  ", "igst_amount": "118.00"},
        configs,
    )

    assert parsed == {
        "cgst_amount": "0.0",
        "sgst_amount": "0.0",
        "igst_amount": "118.00",
    }


def _make_mock_client(response_text: str) -> MagicMock:
    response = MagicMock()
    response.text = response_text

    mock_generate = AsyncMock(return_value=response)
    mock_models = MagicMock()
    mock_models.generate_content = mock_generate

    mock_aio = MagicMock()
    mock_aio.models = mock_models

    mock_client = MagicMock()
    mock_client.aio = mock_aio
    mock_client.generate_content = mock_generate
    return mock_client


@pytest.mark.asyncio
async def test_extract_builds_request_from_field_configs_without_network(
    sample_field_configs: list[FieldConfig],
) -> None:
    mock_client = _make_mock_client(
        json.dumps({"gstin": "29ABCDE1234F1Z5", "total_amount": "1180.00"})
    )
    provider = CloudVisionProvider(
        api_key="test-key",
        model="test-model",
        client=mock_client,
    )

    result = await provider.extract(PNG_BYTES, "", sample_field_configs)

    assert result == {"gstin": "29ABCDE1234F1Z5", "total_amount": "1180.00"}

    mock_generate = mock_client.aio.models.generate_content
    mock_generate.assert_awaited_once()
    _args, kwargs = mock_generate.await_args
    assert kwargs["model"] == "test-model"

    config: types.GenerateContentConfig = kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert set(config.response_json_schema["properties"]) == {"gstin", "total_amount"}

    contents = kwargs["contents"]
    assert isinstance(contents[0], str)
    assert "gstin (GSTIN)" in contents[0]
    assert isinstance(contents[1], types.Part)


@pytest.mark.asyncio
async def test_extract_mocked_null_field_returns_none(
    sample_field_configs: list[FieldConfig],
) -> None:
    mock_client = _make_mock_client(
        json.dumps({"gstin": None, "total_amount": "999.00"})
    )
    provider = CloudVisionProvider(
        api_key="test-key",
        model="test-model",
        client=mock_client,
    )

    result = await provider.extract(PNG_BYTES, "ignored text layer", sample_field_configs)

    assert result["gstin"] is None
    assert result["total_amount"] == "999.00"


@pytest.mark.asyncio
async def test_extract_retries_on_rate_limit(
    sample_field_configs: list[FieldConfig],
) -> None:
    from google.genai import errors as genai_errors

    success_response = MagicMock()
    success_response.text = json.dumps({"gstin": None, "total_amount": None})

    mock_generate = AsyncMock(
        side_effect=[
            genai_errors.ClientError(429, {"error": {"message": "rate limit"}}),
            success_response,
        ]
    )
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = mock_generate

    provider = CloudVisionProvider(
        api_key="test-key",
        model="test-model",
        client=mock_client,
        max_retries=3,
    )

    result = await provider.extract(PNG_BYTES, "", sample_field_configs)

    assert result == {"gstin": None, "total_amount": None}
    assert mock_generate.await_count == 2


@pytest.mark.asyncio
async def test_extract_retries_on_server_unavailable(
    sample_field_configs: list[FieldConfig],
) -> None:
    from google.genai import errors as genai_errors

    success_response = MagicMock()
    success_response.text = json.dumps({"gstin": "29ABCDE1234F1Z5", "total_amount": "100"})

    mock_generate = AsyncMock(
        side_effect=[
            genai_errors.ServerError(
                503,
                {"error": {"message": "model overloaded", "status": "UNAVAILABLE"}},
            ),
            success_response,
        ]
    )
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = mock_generate

    provider = CloudVisionProvider(
        api_key="test-key",
        model="test-model",
        client=mock_client,
        max_retries=6,
    )

    result = await provider.extract(PNG_BYTES, "", sample_field_configs)

    assert result["gstin"] == "29ABCDE1234F1Z5"
    assert mock_generate.await_count == 2


@pytest.mark.asyncio
async def test_extract_fails_only_after_retryable_errors_exhausted(
    sample_field_configs: list[FieldConfig],
) -> None:
    from google.genai import errors as genai_errors

    mock_generate = AsyncMock(
        side_effect=genai_errors.ServerError(
            503,
            {"error": {"message": "model overloaded", "status": "UNAVAILABLE"}},
        )
    )
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = mock_generate

    provider = CloudVisionProvider(
        api_key="test-key",
        model="test-model",
        client=mock_client,
        max_retries=3,
    )

    with pytest.raises(ProviderError, match="HTTP 503"):
        await provider.extract(PNG_BYTES, "", sample_field_configs)

    assert mock_generate.await_count == 3
