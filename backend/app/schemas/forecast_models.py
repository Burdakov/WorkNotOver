from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import DatasetReference, ManualInputReference


class ForecastDatasetSelection(BaseModel):
    dataset_id: str
    dataset_version_id: str | None = None


class ForecastCalculateRequest(BaseModel):
    name: str
    wells: ForecastDatasetSelection
    niz: ForecastDatasetSelection
    gtm: ForecastDatasetSelection
    manual_input_set_id: str
    forecast_start_date: str | None = None
    forecast_end_date: str | None = None
    source_type: str = "uploaded_gtm"
    parent_scenario_id: str | None = None
    metadata: dict[str, Any] | None = None


class ScenarioInputBindings(BaseModel):
    well_groups: ForecastDatasetSelection | None = None
    wells: ForecastDatasetSelection | None = None
    niz: ForecastDatasetSelection | None = None
    gtm: ForecastDatasetSelection | None = None
    infrastructure: ForecastDatasetSelection | None = None
    external_krs_schedule: ForecastDatasetSelection | None = None
    well_trajectories: ForecastDatasetSelection | None = None
    perforations: ForecastDatasetSelection | None = None
    production_history: ForecastDatasetSelection | None = None
    injection_history: ForecastDatasetSelection | None = None
    manual_input_set_id: str | None = None


class ScenarioUpsertRequest(BaseModel):
    name: str
    source_type: str = "uploaded_gtm"
    parent_scenario_id: str | None = None
    forecast_start_date: str | None = None
    forecast_end_date: str | None = None
    inputs: ScenarioInputBindings = Field(default_factory=ScenarioInputBindings)
    metadata: dict[str, Any] | None = None


class ScenarioContextResponse(BaseModel):
    well_groups_dataset: DatasetReference | None = None
    wells_dataset: DatasetReference | None = None
    niz_dataset: DatasetReference | None = None
    gtm_dataset: DatasetReference | None = None
    infrastructure_dataset: DatasetReference | None = None
    external_krs_schedule_dataset: DatasetReference | None = None
    well_trajectories_dataset: DatasetReference | None = None
    perforations_dataset: DatasetReference | None = None
    production_history_dataset: DatasetReference | None = None
    injection_history_dataset: DatasetReference | None = None
    manual_input_set: ManualInputReference | None = None


class ScenarioInputNodeValidation(BaseModel):
    state: str = "empty"
    issues: list[str] = Field(default_factory=list)


class ScenarioInputValidationResponse(BaseModel):
    well_groups: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    wells: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    niz: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    gtm: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    infrastructure: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    external_krs_schedule: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    well_trajectories: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    perforations: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    production_history: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    injection_history: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    manual_input_set: ScenarioInputNodeValidation = Field(default_factory=ScenarioInputNodeValidation)
    is_forecast_ready: bool = False
    issues: list[str] = Field(default_factory=list)


class ScenarioDetailResponse(BaseModel):
    scenario: "ScenarioModelResponse"
    context: ScenarioContextResponse
    input_validation: ScenarioInputValidationResponse = Field(default_factory=ScenarioInputValidationResponse)
    production_summary: dict[str, Any] | None = None
    production_points: list[dict[str, Any]] = Field(default_factory=list)
    wells: list[dict[str, Any]] = Field(default_factory=list)
    source_payload: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    result_created_at: str | None = None


class ScenarioListItemResponse(BaseModel):
    scenario_id: str
    name: str
    source_type: str
    parent_scenario_id: str | None = None
    forecast_start_date: str | None = None
    forecast_end_date: str | None = None
    created_at: str
    status: str
    metadata: dict[str, Any] | None = None
    context: ScenarioContextResponse
    input_validation: ScenarioInputValidationResponse = Field(default_factory=ScenarioInputValidationResponse)
    latest_result_created_at: str | None = None
    production_summary: dict[str, Any] | None = None


class ScenarioRecalculateFromRevisionRequest(BaseModel):
    revision_id: str
    name: str | None = None
    metadata: dict[str, Any] | None = None


class ProductionPoint(BaseModel):
    date: str
    oil_rate: float = 0.0
    liquid_rate: float = 0.0
    gas_rate: float = 0.0
    watercut: float = 0.0
    gor: float = 0.0
    oil_increment: float = 0.0
    liquid_increment: float = 0.0
    gas_increment: float = 0.0


class WellForecastResult(BaseModel):
    well_id: str
    well_name: str
    fund_type: str | None = None
    fund_state: str | None = None
    lu_id: str | None = None
    sloy_id: str | None = None
    well_pad_id: str | None = None
    points: list[ProductionPoint] = Field(default_factory=list)
    total_oil: float = 0.0
    total_liquid: float = 0.0
    total_gas: float = 0.0


class ScenarioProductionSummary(BaseModel):
    total_oil: float = 0.0
    total_liquid: float = 0.0
    total_gas: float = 0.0
    peak_oil_rate: float = 0.0
    peak_liquid_rate: float = 0.0
    peak_gas_rate: float = 0.0
    average_gor: float = 0.0
    point_count: int = 0


class ScenarioModelResponse(BaseModel):
    scenario_id: str
    name: str
    source_type: str
    parent_scenario_id: str | None = None
    forecast_start_date: str | None = None
    forecast_end_date: str | None = None
    created_at: str
    status: str
    metadata: dict[str, Any] | None = None


class ForecastCalculateResponse(BaseModel):
    scenario: ScenarioModelResponse
    wells_dataset: DatasetReference
    niz_dataset: DatasetReference
    gtm_dataset: DatasetReference
    manual_input_set: ManualInputReference
    production_summary: ScenarioProductionSummary
    production_points: list[ProductionPoint] = Field(default_factory=list)
    wells: list[WellForecastResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


ScenarioDetailResponse.model_rebuild()
