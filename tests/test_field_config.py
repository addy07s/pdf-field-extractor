"""Tests for YAML field configuration loading."""

from config import load_field_configs


def test_load_default_fields() -> None:
    configs = load_field_configs()
    keys = [c.key for c in configs]
    assert keys == [
        "company_name",
        "invoice_number",
        "invoice_date",
        "supplier_gstin",
        "recipient_gstin",
        "pan",
        "description",
        "total_taxable_value",
        "cgst_amount",
        "sgst_amount",
        "igst_amount",
        "total_invoice_value",
    ]


def test_supplier_gstin_field_has_expected_validators() -> None:
    configs = load_field_configs()
    gstin = next(c for c in configs if c.key == "supplier_gstin")
    assert gstin.data_type == "string"
    assert "gstin" in gstin.validators
    assert "grounding" in gstin.validators


def test_tax_bucket_fields_default_to_number_without_grounding() -> None:
    configs = load_field_configs()
    for key in ("cgst_amount", "sgst_amount", "igst_amount"):
        field = next(c for c in configs if c.key == key)
        assert field.data_type == "number"
        assert field.validators == ["number"]
