from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DatasetReference(BaseModel):
    dataset_id: str
    dataset_version_id: str
    dataset_type: str
    name: str | None = None
    row_count: int | None = None
    created_at: str | None = None
    metadata: dict[str, Any] | None = None


class ManualInputReference(BaseModel):
    manual_input_set_id: str
    name: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] | None = None


class ValidationIssue(BaseModel):
    level: str = Field(description="warning | error")
    message: str
    row_number: int | None = None
    field_name: str | None = None


class ImportValidationReport(BaseModel):
    source_kind: str
    file_id: str | None = None
    original_name: str | None = None
    sheet_name: str | None = None
    column_mappings: dict[str, str] = Field(default_factory=dict)
    skipped_rows: int = 0
    warnings: list[ValidationIssue] = Field(default_factory=list)
    errors: list[ValidationIssue] = Field(default_factory=list)
    row_count: int = 0


class ColumnInfo(BaseModel):
    name: str
    type: str
    non_null: int
    nulls: int
    unique: int
