"""Review workspace — native Streamlit row grid with per-row View actions (UI only)."""

from __future__ import annotations

import base64
import html
from pathlib import Path

import fitz
import streamlit as st

from config.field_config import FieldConfig
from models import DocumentResult, DocumentStatus, FieldResult, FieldStatus
from output.formatting import display_field_value, is_document_failed
from ui.styles import inject_review_workspace_styles

_ACTIVE_FILE_KEY = "active_review_file"

# Match Excel writer fills (output/excel_writer.py)
_FILL_FAILED = "#ffc7ce"
_FILL_LOW_CONFIDENCE = "#ffeb9c"
_FILL_NOT_FOUND = "#d9d9d9"
_FILL_OK = "#ffffff"

_FIELD_STATUS_COLORS = {
    FieldStatus.FAILED_VALIDATION: _FILL_FAILED,
    FieldStatus.LOW_CONFIDENCE: _FILL_LOW_CONFIDENCE,
    FieldStatus.NOT_FOUND: _FILL_NOT_FOUND,
}

_OVERALL_STATUS_COLORS = {
    DocumentStatus.FAILED: _FILL_FAILED,
    DocumentStatus.PARTIAL: _FILL_LOW_CONFIDENCE,
    DocumentStatus.OK: _FILL_OK,
}


def _grid_columns(field_configs: list[FieldConfig]) -> list[str]:
    return (
        ["Source File", "Status"]
        + [field.display_label for field in field_configs]
        + ["Reason"]
    )


def _column_weights(field_count: int) -> list[float]:
    """View button + source + status + fields + reason."""
    return [0.55, 1.4, 0.8] + [1.0] * field_count + [1.2]


def _cell_fill_color(
    document: DocumentResult,
    column: str,
    field_configs: list[FieldConfig],
) -> str:
    if column == "Source File":
        return _FILL_OK

    if column == "Status":
        return _OVERALL_STATUS_COLORS.get(document.overall_status, _FILL_OK)

    if column == "Reason":
        return _FILL_NOT_FOUND if document.error_message else _FILL_OK

    label_to_key = {fc.display_label: fc.key for fc in field_configs}
    field_key = label_to_key.get(column)
    if field_key is None:
        return _FILL_OK

    if is_document_failed(document):
        return _FILL_NOT_FOUND

    field_result = document.fields.get(field_key)
    if field_result is None:
        return _FILL_OK

    return _FIELD_STATUS_COLORS.get(field_result.status, _FILL_OK)


def _cell_display_value(
    document: DocumentResult,
    column: str,
    field_configs: list[FieldConfig],
) -> str:
    if column == "Source File":
        return document.source_filename
    if column == "Status":
        return document.overall_status.value
    if column == "Reason":
        return document.error_message or ""

    label_to_key = {fc.display_label: fc.key for fc in field_configs}
    field_key = label_to_key.get(column)
    if field_key is None:
        return ""

    field_result = document.fields.get(field_key)
    if field_result is None:
        return ""
    value = display_field_value(field_result)
    return "" if value is None else str(value)


def _render_cell(value: str, fill_color: str) -> None:
    st.markdown(
        f'<div class="review-cell" style="background-color:{fill_color};">'
        f"{html.escape(value)}</div>",
        unsafe_allow_html=True,
    )


def clear_active_review_file() -> None:
    st.session_state.pop(_ACTIVE_FILE_KEY, None)


def _get_active_review_file(valid_filenames: set[str]) -> str | None:
    active = st.session_state.get(_ACTIVE_FILE_KEY)
    if active in valid_filenames:
        return active
    if active is not None:
        clear_active_review_file()
    return None


def _render_pdf_preview(path: Path) -> None:
    doc = fitz.open(path)
    try:
        page = doc.load_page(0)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        st.image(pixmap.tobytes("png"), use_container_width=True)
        if doc.page_count > 1:
            st.caption(f"Preview: page 1 of {doc.page_count}")
    finally:
        doc.close()


def _render_pdf_iframe(path: Path) -> None:
    encoded = base64.b64encode(path.read_bytes()).decode()
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{encoded}" '
        f'width="100%" height="720" class="review-pdf-frame"></iframe>',
        unsafe_allow_html=True,
    )


def render_document_preview(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png"}:
        st.image(path.read_bytes(), use_container_width=True)
        return

    if suffix == ".pdf":
        try:
            _render_pdf_preview(path)
        except Exception:
            _render_pdf_iframe(path)
        return

    st.warning(f"Preview not supported for {path.suffix} files.")


def _render_flag_details(document: DocumentResult, field_configs: list[FieldConfig]) -> None:
    flagged = [
        (fc.display_label, fr.reason)
        for fc in field_configs
        if (fr := document.fields.get(fc.key)) is not None
        and fr.status != FieldStatus.OK
        and fr.reason
    ]
    if not flagged:
        return
    with st.expander("Validation notes for this invoice", expanded=False):
        for label, reason in flagged:
            st.markdown(f"**{label}:** {reason}")


def _render_preview_panel(
    active_file: str,
    results: list[DocumentResult],
    field_configs: list[FieldConfig],
    document_paths: dict[str, Path],
) -> None:
    with st.container(border=True):
        header_left, header_right = st.columns([5, 1])
        with header_left:
            st.markdown(f"**Previewing:** {active_file}")
        with header_right:
            if st.button("❌ Close Preview", key="close_review_preview", use_container_width=True):
                clear_active_review_file()
                st.rerun()

        preview_path = document_paths.get(active_file)
        if preview_path is None or not preview_path.is_file():
            st.info("Original file is not available for preview in this session.")
            return

        render_document_preview(preview_path)
        document = next(doc for doc in results if doc.source_filename == active_file)
        _render_flag_details(document, field_configs)


def _render_preview_slot(
    active_file: str | None,
    results: list[DocumentResult],
    field_configs: list[FieldConfig],
    document_paths: dict[str, Path],
) -> None:
    """Stable preview area — reserved space reduces layout jump when toggling rows."""
    if active_file:
        _render_preview_panel(active_file, results, field_configs, document_paths)
    else:
        st.markdown(
            '<div class="preview-panel-empty">'
            "Click <strong>View</strong> on any row below to open a document preview here."
            "</div>",
            unsafe_allow_html=True,
        )


def _render_grid_header(columns: list[str], weights: list[float]) -> None:
    header_cols = st.columns(weights)
    labels = ["View", *columns]
    for col_widget, label in zip(header_cols, labels):
        with col_widget:
            st.markdown(f'<div class="review-header-cell">{html.escape(label)}</div>', unsafe_allow_html=True)


def _render_result_row(
    document: DocumentResult,
    columns: list[str],
    field_configs: list[FieldConfig],
    weights: list[float],
    *,
    is_active: bool,
) -> None:
    with st.container(border=is_active):
        row_cols = st.columns(weights)
        with row_cols[0]:
            if st.button(
                "👁️ View",
                key=f"view_{document.source_filename}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state[_ACTIVE_FILE_KEY] = document.source_filename
                st.rerun()

        for col_widget, column in zip(row_cols[1:], columns):
            with col_widget:
                _render_cell(
                    _cell_display_value(document, column, field_configs),
                    _cell_fill_color(document, column, field_configs),
                )


def render_review_workspace(
    results: list[DocumentResult],
    field_configs: list[FieldConfig],
    document_paths: dict[str, Path],
) -> None:
    """Interactive row-by-row review grid with native View buttons."""
    inject_review_workspace_styles()

    valid_filenames = {doc.source_filename for doc in results}
    active_file = _get_active_review_file(valid_filenames)
    columns = _grid_columns(field_configs)
    weights = _column_weights(len(field_configs))

    _render_preview_slot(active_file, results, field_configs, document_paths)

    st.markdown("##### Extraction results")
    st.caption(
        "Red = failed validation · Amber = needs review · Grey = not found · "
        "White = OK. Colors match the Excel export."
    )

    with st.container(border=True):
        _render_grid_header(columns, weights)
        st.divider()
        for document in results:
            _render_result_row(
                document,
                columns,
                field_configs,
                weights,
                is_active=active_file == document.source_filename,
            )
