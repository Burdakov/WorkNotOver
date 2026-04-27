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
    gtm: ForecastDatasetSelection
    manual_input_set_id: str
    forecast_start_date: str | None = None
    forecast_end_date: str | None = None
    source_type: str = "uploaded_gtm"
    parent_scenario_id: str | None = None
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
    gtm_dataset: DatasetReference
    manual_input_set: ManualInputReference
    production_summary: ScenarioProductionSummary
    production_points: list[ProductionPoint] = Field(default_factory=list)
    wells: list[WellForecastResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
