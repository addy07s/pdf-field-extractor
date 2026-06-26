"""HTTP routes for invoice extraction and configuration."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.deps import build_provider, cleanup_temp_dir, save_uploads
from api.schemas import ConfigResponse, ExtractResponse
from api.settings import ALLOWED_EXTENSIONS, MAX_UPLOAD_COUNT, OUTPUT_DIR, batch_concurrency, provider_label
from config import load_field_configs
from pipeline.batch import run_batch
from provider.errors import ProviderError
from sources.ocr import is_tesseract_available, log_ocr_startup_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/config", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    """Return field layout from fields.yaml and current runtime settings."""
    return ConfigResponse(
        fields=load_field_configs(),
        provider_label=provider_label(),
        ocr_enabled=is_tesseract_available(),
        ocr_status=log_ocr_startup_status(),
        batch_concurrency=batch_concurrency(),
        max_upload_count=MAX_UPLOAD_COUNT,
    )


@router.post("/extract", response_model=ExtractResponse)
async def extract_invoices(
    files: list[UploadFile] = File(..., description="Invoice PDFs or images"),
) -> ExtractResponse:
    """Accept a batch of invoices, run extraction, and return validated field results."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    if len(files) > MAX_UPLOAD_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_UPLOAD_COUNT} files per batch.",
        )

    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported file type: {upload.filename!r}. "
                    f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                ),
            )

    field_configs = load_field_configs()
    temp_dir, document_paths = await save_uploads(files)
    provider = build_provider()

    try:
        # run_batch uses asyncio.run(); execute in a worker thread so we do not
        # nest event loops inside FastAPI/uvicorn's running loop.
        excel_path, csv_path, results = await asyncio.to_thread(
            run_batch,
            document_paths,
            field_configs,
            provider,
            OUTPUT_DIR,
            max_concurrency=batch_concurrency(),
            progress_callback=None,
        )
    except ProviderError as exc:
        logger.exception("Provider error during batch extraction")
        raise HTTPException(status_code=502, detail=f"Provider error: {exc}") from exc
    finally:
        cleanup_temp_dir(temp_dir)

    return ExtractResponse(
        results=results,
        excel_path=str(excel_path),
        csv_path=str(csv_path),
    )
