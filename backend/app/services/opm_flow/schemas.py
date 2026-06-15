from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


SimulationRunStatus = Literal["draft", "case_built", "running", "completed", "failed", "imported"]


class OpmCaseBuildRequest(BaseModel):
    scenario_id: str
    scenario_name: str | None = None
    forecast_start_date: str | None = None
    forecast_end_date: str | None = None
    case_name: str | None = None
    input_bindings: dict[str, Any] = Field(default_factory=dict)
    model_config_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpmCaseManifest(BaseModel):
    case_name: str
    deck_path: str
    include_files: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    summary_vectors: list[str] = Field(default_factory=list)
    input_bindings_hash: str | None = None
    deck_hash: str | None = None
    validation_warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationArtifact(BaseModel):
    artifact_id: str
    run_id: str
    artifact_type: str
    path: str
    format: str
    size_bytes: int | None = None
    checksum: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpmImportResult(BaseModel):
    run_id: str
    status: str = "not_imported"
    well_timeseries_path: str | None = None
    field_timeseries_path: str | None = None
    grid_static_path: str | None = None
    grid_dynamic_path: str | None = None
    region_material_balance_path: str | None = None
    rft_connections_path: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SimulationRun(BaseModel):
    run_id: str
    scenario_id: str
    forecast_method: str = "opm_flow_blackoil"
    engine: str = "opm_flow"
    engine_version: str | None = None
    status: SimulationRunStatus = "draft"
    case_name: str
    case_root: str
    input_dir: str
    output_dir: str
    normalized_dir: str
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    created_by: str | None = None
    opm_case_manifest: OpmCaseManifest | None = None
    artifacts: list[SimulationArtifact] = Field(default_factory=list)
    import_result: OpmImportResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def root_path(self) -> Path:
        return Path(self.case_root)


class Field2DPrepareRequest(BaseModel):
    scenario_id: str
    scenario_name: str | None = None
    well_groups: list[dict[str, Any]] = Field(default_factory=list)
    trajectories: list[dict[str, Any]] = Field(default_factory=list)
    perforations: list[dict[str, Any]] = Field(default_factory=list)
    production_history: list[dict[str, Any]] = Field(default_factory=list)
    injection_history: list[dict[str, Any]] = Field(default_factory=list)
    initial_reserves: list[dict[str, Any]] = Field(default_factory=list)
    pvt_include: dict[str, Any] | None = None
    dx_m: float = Field(default=150.0, gt=0)
    dy_m: float = Field(default=150.0, gt=0)
    dz_m: float = Field(default=5.0, gt=0)
    porosity: float = Field(default=0.10, gt=0, lt=1)
    permeability_md: float = Field(default=500.0, gt=0)
    formation_volume_factor: float = Field(default=1.15, gt=0)
    initial_oil_saturation: float = Field(default=0.65, gt=0, lt=1)
    initial_pressure_bar: float = Field(default=220.0, gt=0)
    initial_water_saturation: float = Field(default=0.30, ge=0, le=1)
    initial_gas_saturation: float = Field(default=0.04, ge=0, le=1)
    datum_depth_m: float = Field(default=2000.0, ge=0)
    top_depth_m: float = Field(default=2000.0, ge=0)
    nearest_producers_per_injector: int = Field(default=4, ge=1, le=20)
    influence_radius_m: float = Field(default=3000.0, gt=0)
    well_region_radius_m: float = Field(default=150.0, gt=0)
    region_corridor_width_m: float = Field(default=225.0, gt=0)
    grid_padding_m: float = Field(default=450.0, ge=0)
    max_grid_cells: int = Field(default=60000, ge=100)
    history_match_iterations: int = Field(default=8, ge=0, le=200)
    pressure_weight: float = Field(default=0.45, ge=0, le=1)
    watercut_weight: float = Field(default=0.35, ge=0, le=1)
    rate_weight: float = Field(default=0.20, ge=0, le=1)
    pressure_tolerance_bar: float = Field(default=5.0, ge=0)
    watercut_tolerance_fraction: float = Field(default=0.03, ge=0, le=1)
    allow_generated_pvt: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Field2DRunFromScenarioRequest(BaseModel):
    dx_m: float = Field(default=150.0, gt=0)
    dy_m: float = Field(default=150.0, gt=0)
    dz_m: float = Field(default=5.0, gt=0)
    porosity: float = Field(default=0.10, gt=0, lt=1)
    permeability_md: float = Field(default=500.0, gt=0)
    formation_volume_factor: float = Field(default=1.15, gt=0)
    initial_oil_saturation: float = Field(default=0.65, gt=0, lt=1)
    initial_pressure_bar: float = Field(default=220.0, gt=0)
    initial_water_saturation: float = Field(default=0.30, ge=0, le=1)
    initial_gas_saturation: float = Field(default=0.04, ge=0, le=1)
    datum_depth_m: float = Field(default=2000.0, ge=0)
    top_depth_m: float = Field(default=2000.0, ge=0)
    nearest_producers_per_injector: int = Field(default=4, ge=1, le=20)
    influence_radius_m: float = Field(default=3000.0, gt=0)
    well_region_radius_m: float = Field(default=150.0, gt=0)
    region_corridor_width_m: float = Field(default=225.0, gt=0)
    grid_padding_m: float = Field(default=450.0, ge=0)
    max_grid_cells: int = Field(default=60000, ge=100)
    history_match_iterations: int = Field(default=8, ge=0, le=200)
    pressure_weight: float = Field(default=0.45, ge=0, le=1)
    watercut_weight: float = Field(default=0.35, ge=0, le=1)
    rate_weight: float = Field(default=0.20, ge=0, le=1)
    pressure_tolerance_bar: float = Field(default=5.0, ge=0)
    watercut_tolerance_fraction: float = Field(default=0.03, ge=0, le=1)
    allow_generated_pvt: bool = False
    run_external_flow: bool = True
    summary_vectors: list[str] = Field(default_factory=lambda: ["FOPR", "FWPR", "FWIR", "WOPR", "WWPR", "WBHP", "WWCT"])
    metadata: dict[str, Any] = Field(default_factory=dict)


class Field2DPrepareResponse(BaseModel):
    scenario_id: str
    wells: list[dict[str, Any]] = Field(default_factory=list)
    regions: list[dict[str, Any]] = Field(default_factory=list)
    well_regions: list[dict[str, Any]] = Field(default_factory=list)
    grid: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class Field2DRunResponse(BaseModel):
    simulation_run: SimulationRun
    preparation: Field2DPrepareResponse
    analysis: dict[str, Any] = Field(default_factory=dict)


class OpmBlackOilModelPrepareRequest(Field2DRunFromScenarioRequest):
    forecast_method: str = "opm_flow_blackoil"
    model_radius_m: float | None = Field(default=None, gt=0)


class CrmConnectivityRequest(BaseModel):
    run_id: str | None = None
    history_window: dict[str, Any] = Field(default_factory=dict)
    crm: dict[str, Any] = Field(default_factory=dict)


class CrmConnectivityResponse(BaseModel):
    scenario_id: str
    run_id: str | None = None
    connectivity: list[dict[str, Any]] = Field(default_factory=list)
    region_cube: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class RegionCubeBuildRequest(BaseModel):
    run_id: str | None = None
    connectivity_result_id: str | None = None
    allocation: dict[str, Any] = Field(default_factory=dict)


class RegionCubeBuildResponse(BaseModel):
    scenario_id: str
    run_id: str | None = None
    region_cube: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class CalibrationStartRequest(BaseModel):
    run_id: str | None = None
    connectivity_result_id: str | None = None
    history_window: dict[str, Any] = Field(default_factory=dict)
    criteria: dict[str, Any] = Field(default_factory=dict)
    objective_weights: dict[str, Any] = Field(default_factory=dict)
    search: dict[str, Any] = Field(default_factory=dict)
    parameter_bounds: dict[str, Any] = Field(default_factory=dict)
    run_external_flow: bool = True


class CalibrationRunResponse(BaseModel):
    calibration_id: str
    scenario_id: str
    run_id: str
    status: str
    current_iteration: int = 0
    best_objective: float | None = None
    simulation_run: SimulationRun | None = None
    report: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[SimulationArtifact] = Field(default_factory=list)
