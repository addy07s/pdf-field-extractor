"""Tests for shared Pydantic models."""

from models import DocumentResult, DocumentStatus, FieldResult, FieldStatus


def test_field_result_defaults() -> None:
    result = FieldResult(value="ABC123", status=FieldStatus.OK)
    assert result.reason is None


def test_document_result_structure() -> None:
    doc = DocumentResult(
        source_filename="invoice.pdf",
        invoice_index=2,
        fields={"supplier_gstin": FieldResult(status=FieldStatus.NOT_FOUND)},
        overall_status=DocumentStatus.PARTIAL,
    )
    assert doc.source_filename == "invoice.pdf"
    assert doc.invoice_index == 2
    assert doc.fields["supplier_gstin"].status == FieldStatus.NOT_FOUND


def test_document_result_defaults_invoice_index_to_one() -> None:
    doc = DocumentResult(
        source_filename="invoice.pdf",
        fields={},
        overall_status=DocumentStatus.OK,
    )
    assert doc.invoice_index == 1
