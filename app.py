"""Streamlit UI — upload invoices, run extraction, download Excel + CSV."""

from __future__ import annotations

import logging
import os
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from config import load_field_configs
from models import DocumentResult, DocumentStatus
from output.formatting import display_field_value
from pipeline.batch import run_batch
from provider import CloudVisionProvider, OllamaVisionProvider
from provider.base import VisionProvider
from provider.errors import ProviderError
from sources.ocr import is_tesseract_available, log_ocr_startup_status
from ui.styles import inject_styles

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

MAX_UPLOAD_COUNT = 100
OUTPUT_DIR = Path("outputs")
DEFAULT_BATCH_CONCURRENCY = 1


def _build_provider() -> VisionProvider:
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


def _provider_label() -> str:
    provider_name = os.getenv("VISION_PROVIDER", "cloud").strip().lower()
    if provider_name == "ollama":
        model = os.getenv("OLLAMA_MODEL", "llava")
        return f"Ollama (local) — {model}"
    model = os.getenv("GEMINI_MODEL", "(model not set)")
    return f"Gemini (cloud) — {model}"


def _batch_concurrency() -> int:
    raw = os.getenv("BATCH_CONCURRENCY", str(DEFAULT_BATCH_CONCURRENCY)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_BATCH_CONCURRENCY
    return max(1, value)


def _save_uploads(uploaded_files) -> tuple[Path, list[Path]]:
    temp_dir = Path(tempfile.mkdtemp(prefix="invoice_upload_"))
    paths: list[Path] = []
    used_names: set[str] = set()

    for index, uploaded in enumerate(uploaded_files, start=1):
        filename = Path(uploaded.name).name
        if filename in used_names:
            filename = f"{index}_{filename}"
        used_names.add(filename)
        target = temp_dir / filename
        target.write_bytes(uploaded.getbuffer())
        paths.append(target)

    return temp_dir, paths


def _results_dataframe(
    results: list[DocumentResult],
    field_configs,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for document in results:
        row: dict[str, object] = {
            "Source File": document.source_filename,
            "Status": document.overall_status.value,
            "Reason": document.error_message or "",
        }
        for field_config in field_configs:
            field_result = document.fields.get(field_config.key)
            if field_result is None:
                row[field_config.display_label] = ""
            else:
                value = display_field_value(field_result)
                row[field_config.display_label] = "" if value is None else value
        rows.append(row)

    columns = (
        ["Source File", "Status", "Reason"]
        + [field.display_label for field in field_configs]
    )
    return pd.DataFrame(rows, columns=columns)


def _status_counts(results: list[DocumentResult]) -> Counter:
    return Counter(result.overall_status for result in results)


def _render_sidebar(
    *,
    provider_label: str,
    ocr_status: str,
    ocr_enabled: bool,
    batch_concurrency: int,
    field_count: int,
) -> None:
    st.sidebar.title("Settings")
    st.sidebar.caption("System status for this session")

    st.sidebar.markdown("**Vision provider**")
    st.sidebar.info(provider_label)

    st.sidebar.markdown("**OCR**")
    if ocr_enabled:
        st.sidebar.success(ocr_status)
    else:
        st.sidebar.warning(ocr_status)

    col_a, col_b = st.sidebar.columns(2)
    col_a.metric("Concurrency", batch_concurrency)
    col_b.metric("Fields", field_count)

    st.sidebar.divider()
    st.sidebar.info(
        "After processing, review any flagged rows in the Excel file. "
        "Yellow means verify manually; red means the value failed validation."
    )


def _render_summary_metrics(results: list[DocumentResult]) -> None:
    counts = _status_counts(results)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total invoices", len(results))
    c2.metric("OK", counts.get(DocumentStatus.OK, 0))
    c3.metric("Needs review", counts.get(DocumentStatus.PARTIAL, 0))
    c4.metric("Failed", counts.get(DocumentStatus.FAILED, 0))


def main() -> None:
    st.set_page_config(
        page_title="GST Invoice Field Extractor",
        page_icon="📄",
        layout="wide",
    )
    inject_styles()

    field_configs = load_field_configs()
    ocr_status = log_ocr_startup_status()

    _render_sidebar(
        provider_label=_provider_label(),
        ocr_status=ocr_status,
        ocr_enabled=is_tesseract_available(),
        batch_concurrency=_batch_concurrency(),
        field_count=len(field_configs),
    )

    st.title("GST Invoice Field Extractor")
    st.caption(
        "Upload your GST invoices and download a validated spreadsheet — "
        "no manual data entry required."
    )

    with st.expander("How it works", expanded=False):
        st.markdown(
            "1. **Upload** your invoice files (PDF or images)\n"
            "2. **Click Start processing** and wait for extraction to finish\n"
            "3. **Download** the Excel or CSV file and review any flagged cells"
        )

    st.subheader("Upload invoices")
    uploaded = st.file_uploader(
        "Choose files or drag them here",
        type=["pdf", "jpg", "jpeg", "png"],
        accept_multiple_files=True,
        help="Supported formats: PDF, JPG, PNG. Up to 100 files per batch.",
    )

    if uploaded:
        st.caption(f"{len(uploaded)} file(s) selected")
        if len(uploaded) > MAX_UPLOAD_COUNT:
            st.error(f"Maximum {MAX_UPLOAD_COUNT} files per run.")
            return

    process_clicked = st.button(
        "Start processing",
        type="primary",
        disabled=not uploaded,
    )

    if process_clicked and uploaded:
        progress_bar = st.progress(0, text="Starting batch…")
        status_text = st.empty()

        def on_progress(completed: int, total: int, filename: str) -> None:
            progress_bar.progress(
                completed / total,
                text=f"Processing {completed} of {total}: {filename}",
            )
            status_text.caption(f"Finished {filename}")

        _, document_paths = _save_uploads(uploaded)
        provider = _build_provider()

        try:
            excel_path, csv_path, results = run_batch(
                document_paths,
                field_configs,
                provider,
                OUTPUT_DIR,
                max_concurrency=_batch_concurrency(),
                progress_callback=on_progress,
            )
        except ProviderError as exc:
            st.error(f"Provider error: {exc}")
            return

        progress_bar.progress(1.0, text="Done")
        status_text.empty()
        st.success("Processing complete. Review results below and download your file.")

        st.session_state["excel_path"] = excel_path
        st.session_state["csv_path"] = csv_path
        st.session_state["results"] = results
        st.session_state["field_configs"] = field_configs

    if "results" in st.session_state:
        results: list[DocumentResult] = st.session_state["results"]
        configs = st.session_state.get("field_configs", field_configs)

        st.divider()
        st.subheader("Results")
        _render_summary_metrics(results)
        st.dataframe(
            _results_dataframe(results, configs),
            use_container_width=True,
            hide_index=True,
        )

        excel_path = Path(st.session_state["excel_path"])
        csv_path = Path(st.session_state["csv_path"])

        st.subheader("Download")
        col_excel, col_csv = st.columns(2)
        with col_excel:
            st.download_button(
                label="Download Excel",
                data=excel_path.read_bytes(),
                file_name=excel_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_csv:
            st.download_button(
                label="Download CSV",
                data=csv_path.read_bytes(),
                file_name=csv_path.name,
                mime="text/csv",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
