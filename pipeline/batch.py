"""Batch pipeline — bounded async concurrency, per-document error isolation."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from config.field_config import FieldConfig, load_field_configs
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
) -> DocumentResult:
    return DocumentResult(
        source_filename=source_filename,
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


async def process_document(
    file_path: Path,
    field_configs: list[FieldConfig],
    provider: VisionProvider,
) -> DocumentResult:
    """Process one PDF through load → extract → validate.

    Multi-page limitation: only page 1 is sent to the vision model. Most GST
    invoices are single-page; multi-page support (merge or per-page extraction)
    is not implemented yet — see TODO below.

    TODO: When ``page_count > 1``, decide whether to merge pages, iterate, or
    flag the document for review instead of silently using page 1 only.
    """
    try:
        document = load_document(file_path)
        if document.page_count > 1:
            logger.warning(
                "%s has %d pages; extracting page 1 only (multi-page not yet supported)",
                file_path.name,
                document.page_count,
            )

        first_page = document.pages[0]
        raw_fields = await provider.extract(
            first_page.image_bytes,
            document.text_layer,
            field_configs,
        )
        raw_fields = apply_text_layer_corrections(raw_fields, document)
        return validate_document(
            file_path.name,
            raw_fields,
            field_configs,
            document,
        )
    except (PdfLoadError, ProviderError) as exc:
        logger.exception("Document failed (%s): %s", file_path.name, exc)
        return _failed_document_result(file_path.name, field_configs, str(exc))
    except Exception as exc:  # noqa: BLE001 — per-doc isolation; N in = N rows out
        logger.exception("Unexpected error processing %s", file_path.name)
        return _failed_document_result(file_path.name, field_configs, str(exc))


async def process_batch(
    pdf_paths: list[Path | str],
    field_configs: list[FieldConfig],
    provider: VisionProvider,
    *,
    max_concurrency: int = 5,
    progress_callback: ProgressCallback | None = None,
) -> list[DocumentResult]:
    """Process many PDFs with bounded concurrency and per-document isolation.

    Each path yields exactly one ``DocumentResult`` in the same order as
    ``pdf_paths``, whether processing succeeded or failed.

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

    async def _run(path: Path) -> DocumentResult:
        nonlocal completed_count
        async with semaphore:
            logger.info("Starting %s", path.name)
            result = await process_document(path, field_configs, provider)

        async with progress_lock:
            completed_count += 1
            if progress_callback is not None:
                progress_callback(completed_count, total, path.name)

        logger.info(
            "Finished %s -> %s",
            path.name,
            result.overall_status.value,
        )
        return result

    return list(await asyncio.gather(*[_run(path) for path in paths]))


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
