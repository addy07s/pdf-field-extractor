"""Tests for shared Pydantic models."""

from models import DocumentResult, DocumentStatus, FieldResult, FieldStatus


def test_field_result_defaults() -> None:
    result = FieldResult(value="ABC123", status=FieldStatus.OK)
    assert result.reason is None


def test_document_result_structure() -> None:
    doc = DocumentResult(
        source_filename="invoice.pdf",
        fields={"gstin": FieldResult(status=FieldStatus.NOT_FOUND)},
        overall_status=DocumentStatus.PARTIAL,
    )
    assert doc.source_filename == "invoice.pdf"
    assert doc.fields["gstin"].status == FieldStatus.NOT_FOUND
