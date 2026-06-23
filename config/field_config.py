"""Load and validate field definitions from config/fields.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

DEFAULT_FIELDS_PATH = Path(__file__).resolve().parent / "fields.yaml"

DataType = Literal["string", "date", "number"]
ValidatorName = Literal[
    "gstin",
    "pan",
    "date",
    "grounding",
    "number",
    "none",
]


class FieldConfig(BaseModel):
    """One configurable invoice field."""

    key: str
    display_label: str
    description: str
    data_type: DataType
    validators: list[ValidatorName] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def key_must_be_snake_case(cls, value: str) -> str:
        if not value or not value.replace("_", "").isalnum():
            raise ValueError(f"Invalid field key: {value!r}")
        return value


class FieldsConfig(BaseModel):
    """Root container matching fields.yaml structure."""

    fields: list[FieldConfig]


def load_field_configs(path: Path | str | None = None) -> list[FieldConfig]:
    """Read fields.yaml and return a list of typed FieldConfig objects."""
    config_path = Path(path) if path is not None else DEFAULT_FIELDS_PATH
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    parsed = FieldsConfig.model_validate(raw)
    return parsed.fields
