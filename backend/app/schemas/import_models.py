from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

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
    fund_state: str | None = None
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


class NizWellMatchInput(BaseModel):
    row_number: int
    matched_well_name: str | None = None


class GtmWellMatchInput(BaseModel):
    row_number: int
    matched_well_name: str | None = None


class NizWellCandidateInput(BaseModel):
    well_name: str
    lu_id: str | None = None
    well_pad_id: str | None = None


class ManualNizEntryInput(BaseModel):
    well_name: str
    lu_id: str | None = None
    well_pad_id: str | None = None
    niz: float | None = None
    cumulative_oil: float | None = None
    cumulative_gas: float | None = None


class NormalizeRequest(BaseModel):
    file_id: str
    source_kind: str
    sheet_name: str | None = None
    columns: NormalizeColumns | None = None
    dataset_name: str | None = None
    dataset_id: str | None = None
    niz_well_matches: list[NizWellMatchInput] = Field(default_factory=list)
    gtm_well_matches: list[GtmWellMatchInput] = Field(default_factory=list)
    manual_niz_entries: list[ManualNizEntryInput] = Field(default_factory=list)


class NormalizeResponse(BaseModel):
    dataset_reference: DatasetReference
    validation_report: ImportValidationReport
    normalized_payload: dict[str, Any] | list[dict[str, Any]]


class NizWellMatchPreviewRequest(BaseModel):
    file_id: str
    sheet_name: str | None = None
    columns: NormalizeColumns | None = None
    candidate_wells: list[NizWellCandidateInput] = Field(default_factory=list)


class NizWellCandidateOption(BaseModel):
    well_name: str
    lu_id: str | None = None
    well_pad_id: str | None = None


class NizWellMatchSuggestionRow(BaseModel):
    row_number: int
    source_well_name: str
    source_lu_id: str | None = None
    source_well_pad_id: str | None = None
    matched_well_name: str | None = None
    candidates: list[NizWellCandidateOption] = Field(default_factory=list)


class NizWellMatchPreviewResponse(BaseModel):
    rows: list[NizWellMatchSuggestionRow] = Field(default_factory=list)


class GtmWellMatchPreviewRequest(BaseModel):
    file_id: str
    sheet_name: str | None = None
    columns: NormalizeColumns | None = None
    candidate_wells: list[NizWellCandidateInput] = Field(default_factory=list)


class GtmWellMatchPreviewResponse(BaseModel):
    rows: list[NizWellMatchSuggestionRow] = Field(default_factory=list)


class DisplacementCurvePointInput(BaseModel):
    NIZ: float
    watercut: float


class DisplacementConfigInput(BaseModel):
    config_id: str | None = None
    lu_id: str | None = None
    sloy_id: str | None = None
    curve_points: list[DisplacementCurvePointInput] = Field(default_factory=list)
    watercut_unit: str = "percent"
    notes: str | None = None


class MonthlyDeclinePointInput(BaseModel):
    month_index: int
    liquid_decline_factor: float


class DeclineConfigInput(BaseModel):
    config_id: str | None = None
    lu_id: str | None = None
    sloy_id: str | None = None
    base_monthly_decline_values: list[MonthlyDeclinePointInput] = Field(default_factory=list)
    new_wells_monthly_decline_values: list[MonthlyDeclinePointInput] = Field(default_factory=list)
    notes: str | None = None


class ManualInputPayload(BaseModel):
    displacement_config: DisplacementConfigInput | list[DisplacementConfigInput] | None = None
    decline_config: DeclineConfigInput | list[DeclineConfigInput] | None = None
    brigade_availability_config: dict[str, Any] | None = None
    brigade_capacity_by_lu_config: dict[str, Any] | None = None
    failure_coefficient_config: dict[str, Any] | None = None
    krs_resource_config: dict[str, Any] | None = None
    economics_config: dict[str, Any] | None = None
    optimizer_config: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    @staticmethod
    def _ensure_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    def to_storage_payload(self) -> dict[str, Any]:
        displacement_configs = [
            item.model_dump()
            for item in self._ensure_list(self.displacement_config)
            if isinstance(item, DisplacementConfigInput)
        ]
        decline_configs = [
            item.model_dump()
            for item in self._ensure_list(self.decline_config)
            if isinstance(item, DeclineConfigInput)
        ]
        return {
            "displacement_configs": displacement_configs,
            "decline_configs": decline_configs,
            "brigade_availability_config": self.brigade_availability_config,
            "brigade_capacity_by_lu_config": self.brigade_capacity_by_lu_config,
            "failure_coefficient_config": self.failure_coefficient_config,
            "krs_resource_config": self.krs_resource_config,
            "economics_config": self.economics_config,
            "optimizer_config": self.optimizer_config,
            "metadata": self.metadata,
        }


class ManualInputSaveRequest(BaseModel):
    name: str
    payload: ManualInputPayload
    created_by: str | None = None


class ManualInputSaveResponse(BaseModel):
    reference: ManualInputReference
    payload: dict[str, Any]
