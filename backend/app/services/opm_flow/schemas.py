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


class OpmTemplateSyntheticRequest(BaseModel):
    scenario_id: str = "template-synthetic"
    scenario_name: str | None = None
    case_name: str = "data_templates_opm_synthetic"
    forecast_start_date: str = "2018-01-01"
    forecast_end_date: str = "2018-03-01"
    history_match_iterations: int = Field(default=12, ge=1, le=200)
    influence_radius_m: float = Field(default=3000.0, gt=0)
    pressure_weight: float = Field(default=0.45, ge=0, le=1)
    watercut_weight: float = Field(default=0.35, ge=0, le=1)
    rate_weight: float = Field(default=0.2, ge=0, le=1)
    summary_vectors: list[str] = Field(default_factory=lambda: ["FOPR", "FWPR", "FGPR", "WOPR", "WWPR", "WBHP", "WWCT"])
    run_external_flow: bool = True
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


class ContactInterval(BaseModel):
    contact_id: str
    well_name: str
    lu_id: str | None = None
    sloy_id: str | None = None
    well_pad_id: str | None = None
    top_md: float
    bottom_md: float
    center_md: float
    top_x: float | None = None
    top_y: float | None = None
    top_z: float | None = None
    bottom_x: float | None = None
    bottom_y: float | None = None
    bottom_z: float | None = None
    center_x: float | None = None
    center_y: float | None = None
    center_z: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Drainage1DConnection(BaseModel):
    connection_id: str
    scenario_id: str
    injector_name: str
    producer_name: str
    distance_m: float
    inside_influence_radius: bool
    active: bool = True
    alpha_prior: float = 0.0
    alpha: float = 0.0
    eta: float = 1.0
    tau_days: float = 0.0
    pv: float = 0.0
    link_type: str = "unknown"
    prior_source: str = "distance_3000m"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Drainage1DModelSpec(BaseModel):
    model_id: str
    model_name: str
    connection_id: str
    injector_name: str
    producer_name: str
    nx: int
    ny: int = 1
    nz: int = 1
    dx_m: float = 50.0
    dy_m: float = 50.0
    dz_m: float = 5.0
    length_m: float
    pore_volume: float
    allocated_ooip: float | None = None
    opm_case_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Drainage1DPrepareRequest(BaseModel):
    scenario_id: str
    scenario_name: str | None = None
    well_groups: list[dict[str, Any]] = Field(default_factory=list)
    trajectories: list[dict[str, Any]] = Field(default_factory=list)
    perforations: list[dict[str, Any]] = Field(default_factory=list)
    production_history: list[dict[str, Any]] = Field(default_factory=list)
    injection_history: list[dict[str, Any]] = Field(default_factory=list)
    initial_reserves: list[dict[str, Any]] = Field(default_factory=list)
    pore_volumes: list[dict[str, Any]] = Field(default_factory=list)
    influence_radius_m: float = Field(default=3000.0, gt=0)
    distance_kernel_power: float = Field(default=2.0, gt=0)
    grid_block_length_m: float = Field(default=50.0, gt=0)
    grid_block_width_m: float = Field(default=50.0, gt=0)
    grid_thickness_m: float = Field(default=5.0, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Drainage1DPrepareFromScenarioRequest(BaseModel):
    influence_radius_m: float = Field(default=3000.0, gt=0)
    distance_kernel_power: float = Field(default=2.0, gt=0)
    grid_block_length_m: float = Field(default=50.0, gt=0)
    grid_block_width_m: float = Field(default=50.0, gt=0)
    grid_thickness_m: float = Field(default=5.0, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Drainage1DPrepareResponse(BaseModel):
    scenario_id: str
    contact_intervals: list[ContactInterval] = Field(default_factory=list)
    connections: list[Drainage1DConnection] = Field(default_factory=list)
    model_specs: list[Drainage1DModelSpec] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


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
