"""Batch pipeline — bounded async concurrency, per-document error isolation."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from config.field_config import FieldConfig
from models import DocumentResult, DocumentStatus, FieldResult, FieldStatus
from output.csv_writer import write_csv
from output.excel_writer import write_excel
from provider.base import VisionProvider
from provider.errors import ProviderError
from sources.pdf_source import PdfLoadError, load_document
from extract.corrections import apply_text_layer_corrections
from validate.validator import validate_document

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


def _failed_document_result(
    source_filename: str,
    field_configs: list[FieldConfig],
    error_message: str,
    *,
    invoice_index: int = 1,
) -> DocumentResult:
    return DocumentResult(
        source_filename=source_filename,
        invoice_index=invoice_index,
        fields={
            cfg.key: FieldResult(
                status=FieldStatus.NOT_FOUND,
                reason="processing failed",
            )
            for cfg in field_configs
        },
        overall_status=DocumentStatus.FAILED,
        error_message=error_message,
    )


def _validate_invoices(
    source_filename: str,
    raw_invoices: list[dict[str, Any]],
    field_configs: list[FieldConfig],
    document,
) -> list[DocumentResult]:
    """Apply corrections + validation to each extracted invoice independently."""
    multi_invoice = len(raw_invoices) > 1
    results: list[DocumentResult] = []
    for index, raw_fields in enumerate(raw_invoices, start=1):
        corrected = apply_text_layer_corrections(
            raw_fields,
            document,
            allow_single_gstin_replace=not multi_invoice,
        )
        results.append(
            validate_document(
                source_filename,
                corrected,
                field_configs,
                document,
                invoice_index=index,
            )
        )
    return results


async def process_document(
    file_path: Path,
    field_configs: list[FieldConfig],
    provider: VisionProvider,
) -> list[DocumentResult]:
    """Process one PDF/image through load → extract → validate.

    Returns one ``DocumentResult`` per distinct invoice found in the file.
    All pages are sent to the vision model (subject to provider page limits).
    """
    try:
        document = load_document(file_path)
        page_images = [page.image_bytes for page in document.pages]
        if document.page_count > 1:
            logger.info(
                "%s has %d pages; sending all pages for multi-invoice extraction",
                file_path.name,
                document.page_count,
            )

        raw_invoices = await provider.extract(
            page_images,
            document.text_layer,
            field_configs,
        )
        if not raw_invoices:
            raise ProviderError("Provider returned no invoices")

        return _validate_invoices(
            file_path.name,
            raw_invoices,
            field_configs,
            document,
        )
    except (PdfLoadError, ProviderError) as exc:
        logger.exception("Document failed (%s): %s", file_path.name, exc)
        return [_failed_document_result(file_path.name, field_configs, str(exc))]
    except Exception as exc:  # noqa: BLE001 — per-doc isolation
        logger.exception("Unexpected error processing %s", file_path.name)
        return [_failed_document_result(file_path.name, field_configs, str(exc))]


async def process_batch(
    pdf_paths: list[Path | str],
    field_configs: list[FieldConfig],
    provider: VisionProvider,
    *,
    max_concurrency: int = 5,
    progress_callback: ProgressCallback | None = None,
) -> list[DocumentResult]:
    """Process many PDFs with bounded concurrency and per-document isolation.

    Each path yields one or more ``DocumentResult`` rows (one per invoice), in
    file order. Failures still produce a single FAILED row for that file.

    Keep ``max_concurrency`` modest (3–5 on Gemini Flash) to reduce 503 overload
    errors when Google's model is under heavy load; higher values fan out more
    simultaneous requests and can worsen transient UNAVAILABLE responses.
    """
    paths = [Path(p) for p in pdf_paths]
    total = len(paths)
    if total == 0:
        return []

    semaphore = asyncio.Semaphore(max_concurrency)
    progress_lock = asyncio.Lock()
    completed_count = 0

    async def _run(path: Path) -> list[DocumentResult]:
        nonlocal completed_count
        async with semaphore:
            logger.info("Starting %s", path.name)
            results = await process_document(path, field_configs, provider)

        async with progress_lock:
            completed_count += 1
            if progress_callback is not None:
                progress_callback(completed_count, total, path.name)

        statuses = ",".join(r.overall_status.value for r in results)
        logger.info(
            "Finished %s -> %d invoice(s) [%s]",
            path.name,
            len(results),
            statuses,
        )
        return results

    nested = await asyncio.gather(*[_run(path) for path in paths])
    flattened: list[DocumentResult] = []
    for group in nested:
        flattened.extend(group)
    return flattened


def run_batch(
    pdf_paths: list[Path | str],
    field_configs: list[FieldConfig],
    provider: VisionProvider,
    out_dir: Path | str,
    *,
    max_concurrency: int = 5,
    progress_callback: ProgressCallback | None = None,
) -> tuple[Path, Path, list[DocumentResult]]:
    """Run ``process_batch`` and write timestamped Excel + CSV outputs to ``out_dir``."""
    results = asyncio.run(
        process_batch(
            pdf_paths,
            field_configs,
            provider,
            max_concurrency=max_concurrency,
            progress_callback=progress_callback,
        )
    )

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = write_excel(
        results,
        field_configs,
        output_dir / f"invoices_{timestamp}.xlsx",
    )
    csv_path = write_csv(
        results,
        field_configs,
        output_dir / f"invoices_{timestamp}.csv",
    )
    return excel_path, csv_path, results
