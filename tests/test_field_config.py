"""Tests for YAML field configuration loading."""

from config import load_field_configs


def test_load_default_fields() -> None:
    configs = load_field_configs()
    keys = [c.key for c in configs]
    assert keys == [
        "company_name",
        "invoice_number",
        "invoice_date",
        "gstin",
        "pan",
        "description",
        "taxable_amount",
        "gst_amount",
        "total_amount",
    ]


def test_gstin_field_has_expected_validators() -> None:
    configs = load_field_configs()
    gstin = next(c for c in configs if c.key == "gstin")
    assert gstin.data_type == "string"
    assert "gstin" in gstin.validators
    assert "grounding" in gstin.validators
