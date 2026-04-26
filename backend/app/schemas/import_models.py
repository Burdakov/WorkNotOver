from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.common import ColumnInfo, DatasetReference, ImportValidationReport, ManualInputReference


class UploadedFileItem(BaseModel):
    file_id: str
    original_name: str
    sheets: list[str]


class UploadResponse(BaseModel):
    file_id: str
    original_name: str
    sheets: list[str]
    selected_sheet: str
    preview: list[dict[str, Any]]
    columns_info: list[ColumnInfo]


class NormalizeColumns(BaseModel):
    well: str | None = None
    area: str | None = None
    lu: str | None = None
    sloy: str | None = None
    well_pad: str | None = None
    brigade: str | None = None
    fund_type: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    planned_work: str | None = None
    increment: str | None = None
    liquid_increment: str | None = None
    gas_increment: str | None = None
    gor_change: str | None = None
    oil_rate: str | None = None
    gas_rate: str | None = None
    liquid_rate: str | None = None
    watercut: str | None = None
    gor: str | None = None
    cumulative_oil: str | None = None
    cumulative_gas: str | None = None
    niz: str | None = None
    gtm_type: str | None = None
    duration_days: str | None = None
    object_name: str | None = None
    object_type: str | None = None
    commissioning_date: str | None = None
    capacity_oil: str | None = None
    capacity_gas: str | None = None
    capacity_liquid: str | None = None
    capacity_water: str | None = None
    connection_well: str | None = None
    parent_object: str | None = None


class NormalizeRequest(BaseModel):
    file_id: str
    source_kind: str
    sheet_name: str | None = None
    columns: NormalizeColumns | None = None
    dataset_name: str | None = None


class NormalizeResponse(BaseModel):
    dataset_reference: DatasetReference
    validation_report: ImportValidationReport
    normalized_payload: dict[str, Any] | list[dict[str, Any]]


class ManualInputPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    displacement_config: dict[str, Any] | None = None
    decline_config: dict[str, Any] | None = None
    brigade_availability_config: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("brigade_availability_config", "brigade_availability"),
    )
    brigade_capacity_by_lu_config: dict[str, Any] | None = None
    failure_coefficient_config: dict[str, Any] | None = None
    krs_resource_config: dict[str, Any] | None = None
    economics_config: dict[str, Any] | None = None
    optimizer_config: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class ManualInputSaveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    payload: ManualInputPayload | None = None
    created_by: str | None = None
    displacement_config: dict[str, Any] | None = None
    decline_config: dict[str, Any] | None = None
    brigade_availability_config: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("brigade_availability_config", "brigade_availability"),
    )
    brigade_capacity_by_lu_config: dict[str, Any] | None = None
    failure_coefficient_config: dict[str, Any] | None = None
    krs_resource_config: dict[str, Any] | None = None
    economics_config: dict[str, Any] | None = None
    optimizer_config: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    def normalized_payload(self) -> ManualInputPayload:
        if self.payload is not None:
            return self.payload
        return ManualInputPayload(
            displacement_config=self.displacement_config,
            decline_config=self.decline_config,
            brigade_availability_config=self.brigade_availability_config,
            brigade_capacity_by_lu_config=self.brigade_capacity_by_lu_config,
            failure_coefficient_config=self.failure_coefficient_config,
            krs_resource_config=self.krs_resource_config,
            economics_config=self.economics_config,
            optimizer_config=self.optimizer_config,
            metadata=self.metadata,
        )


class ManualInputSaveResponse(BaseModel):
    reference: ManualInputReference
    payload: ManualInputPayload
