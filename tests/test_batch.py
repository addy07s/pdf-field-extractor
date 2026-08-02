"""Tests for the batch processing pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from config.field_config import FieldConfig, load_field_configs
from models import DocumentStatus, FieldStatus
from pipeline.batch import process_batch, run_batch
from provider.base import VisionProvider
from provider.errors import ProviderError

FIXTURE_PDF = Path("tests/fixtures/SalesBill_AME_2 1.PDF")

SMOKE_RAW = {
    "company_name": "ADITYA MULTIMEDIA AND ENTERTAINMENT",
    "invoice_number": "AME/2",
    "invoice_date": "23/04/2026",
    "supplier_gstin": "24ABMFA4190N1Z2",
    "recipient_gstin": None,
    "pan": "ABMFA4190N",
    "description": "ROYALTY INCOME",
    "total_taxable_value": "4380.00",
    "cgst_amount": "0.0",
    "sgst_amount": "0.0",
    "igst_amount": "788.40",
    "total_invoice_value": "5,168.40",
}


class _StaticProvider(VisionProvider):
    def __init__(self, raw_fields: dict[str, Any] | None = None) -> None:
        self._raw_fields = raw_fields or SMOKE_RAW
        self.call_count = 0

    async def extract(
        self,
        image_bytes: bytes,
        text_layer: str,
        field_configs: list[FieldConfig],
    ) -> dict[str, Any]:
        self.call_count += 1
        return dict(self._raw_fields)


@pytest.fixture
def field_configs() -> list[FieldConfig]:
    return load_field_configs()


def _copy_fixture(tmp_path: Path, name: str) -> Path:
    if not FIXTURE_PDF.is_file():
        pytest.skip(f"Fixture PDF not found: {FIXTURE_PDF}")
    target = tmp_path / name
    target.write_bytes(FIXTURE_PDF.read_bytes())
    return target


@pytest.mark.asyncio
async def test_batch_provider_error_isolates_failed_document(
    tmp_path: Path,
    field_configs: list[FieldConfig],
) -> None:
    paths = [
        _copy_fixture(tmp_path, "invoice_a.pdf"),
        _copy_fixture(tmp_path, "invoice_b_bad.pdf"),
        _copy_fixture(tmp_path, "invoice_c.pdf"),
    ]

    provider = _StaticProvider()
    provider.extract = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            dict(SMOKE_RAW),
            ProviderError("Gemini API error (HTTP 500): simulated failure"),
            dict(SMOKE_RAW),
        ]
    )

    results = await process_batch(paths, field_configs, provider, max_concurrency=1)

    assert len(results) == 3
    assert [r.source_filename for r in results] == [
        "invoice_a.pdf",
        "invoice_b_bad.pdf",
        "invoice_c.pdf",
    ]
    assert results[0].overall_status != DocumentStatus.FAILED
    assert results[1].overall_status == DocumentStatus.FAILED
    assert "simulated failure" in (results[1].error_message or "")
    assert results[2].overall_status != DocumentStatus.FAILED
    assert results[0].fields["supplier_gstin"].status == FieldStatus.OK
    assert results[2].fields["supplier_gstin"].status == FieldStatus.OK
    assert provider.extract.await_count == 3


@pytest.mark.asyncio
async def test_batch_corrupt_pdf_row_failed_others_succeed(
    tmp_path: Path,
    field_configs: list[FieldConfig],
) -> None:
    paths = [
        _copy_fixture(tmp_path, "good_one.pdf"),
        tmp_path / "corrupt.pdf",
        _copy_fixture(tmp_path, "good_two.pdf"),
    ]
    paths[1].write_bytes(b"not a real pdf")

    provider = _StaticProvider()
    results = await process_batch(paths, field_configs, provider, max_concurrency=5)

    assert len(results) == 3
    assert results[0].overall_status != DocumentStatus.FAILED
    assert results[1].overall_status == DocumentStatus.FAILED
    assert "Failed to load PDF" in (results[1].error_message or "")
    assert results[2].overall_status != DocumentStatus.FAILED
    assert provider.call_count == 2


@pytest.mark.asyncio
async def test_batch_respects_concurrency_limit(
    tmp_path: Path,
    field_configs: list[FieldConfig],
) -> None:
    paths = [_copy_fixture(tmp_path, f"doc_{index}.pdf") for index in range(6)]

    class ConcurrencyTrackingProvider(VisionProvider):
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0
            self._lock = asyncio.Lock()

        async def extract(
            self,
            image_bytes: bytes,
            text_layer: str,
            field_configs: list[FieldConfig],
        ) -> dict[str, Any]:
            async with self._lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.05)
            async with self._lock:
                self.active -= 1
            return dict(SMOKE_RAW)

    provider = ConcurrencyTrackingProvider()
    results = await process_batch(paths, field_configs, provider, max_concurrency=2)

    assert len(results) == 6
    assert provider.max_active <= 2


def test_run_batch_writes_timestamped_outputs(
    tmp_path: Path,
    field_configs: list[FieldConfig],
) -> None:
    if not FIXTURE_PDF.is_file():
        pytest.skip(f"Fixture PDF not found: {FIXTURE_PDF}")

    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(FIXTURE_PDF.read_bytes())
    out_dir = tmp_path / "outputs"

    excel_path, csv_path, _ = run_batch(
        [pdf_path],
        field_configs,
        _StaticProvider(),
        out_dir,
        max_concurrency=2,
    )

    assert excel_path.is_file()
    assert csv_path.is_file()
    assert excel_path.parent == out_dir
    assert csv_path.parent == out_dir
    assert excel_path.name.startswith("invoices_")
    assert csv_path.name.startswith("invoices_")
