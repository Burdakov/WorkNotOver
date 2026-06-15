from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.services.opm_flow import Field2DModelService, OpmFlowSimulationService
from app.services.opm_flow.schemas import (
    CalibrationRunResponse,
    CalibrationStartRequest,
    CrmConnectivityRequest,
    CrmConnectivityResponse,
    Field2DPrepareRequest,
    Field2DPrepareResponse,
    Field2DRunFromScenarioRequest,
    Field2DRunResponse,
    OpmCaseBuildRequest,
    OpmBlackOilModelPrepareRequest,
    RegionCubeBuildRequest,
    RegionCubeBuildResponse,
    SimulationRun,
)


router = APIRouter(prefix="/api/forecast/opm-flow", tags=["module-b-opm-flow"])
_SCENARIO_CONTEXT_KEY = "scenario_context"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _service() -> OpmFlowSimulationService:
    return OpmFlowSimulationService()


def _scenario_context(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    context = metadata.get(_SCENARIO_CONTEXT_KEY)
    return context if isinstance(context, dict) else {}


def _field_2d_config(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    config = metadata.get("field_2d_config")
    return dict(config) if isinstance(config, dict) else {}


def _normalized_payload_from_context(
    db: Session,
    context: dict[str, Any],
    *,
    context_key: str,
    expected_type: str,
    required: bool = True,
) -> Any:
    reference = context.get(context_key)
    if not isinstance(reference, dict):
        if required:
            raise HTTPException(status_code=400, detail=f"Scenario has no bound dataset '{expected_type}'.")
        return None if expected_type == "pvt_properties" else []
    resolved = DatasetRepository(db).get_dataset_version(
        str(reference.get("dataset_id") or ""),
        reference.get("dataset_version_id"),
    )
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Dataset '{expected_type}' not found.")
    dataset, version = resolved
    if dataset.dataset_type != expected_type:
        raise HTTPException(status_code=400, detail=f"Expected dataset type '{expected_type}', got '{dataset.dataset_type}'.")
    payload = version.normalized_payload_json
    if payload is None:
        return [] if expected_type != "pvt_properties" else None
    if expected_type == "pvt_properties":
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Dataset 'pvt_properties' normalized payload must be an object.")
        return payload
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail=f"Dataset '{expected_type}' normalized payload must be a list.")
    return [row for row in payload if isinstance(row, dict)]


def _pvt_payload_from_context(db: Session, context: dict[str, Any], *, required: bool) -> dict[str, Any] | None:
    for key in ("pvt_properties_dataset", "pvt_dataset"):
        payload = _normalized_payload_from_context(
            db,
            context,
            context_key=key,
            expected_type="pvt_properties",
            required=False,
        )
        if isinstance(payload, dict):
            return payload
    if required:
        raise HTTPException(status_code=400, detail="Scenario has no bound dataset 'pvt_properties'.")
    return None


def _merge_field_2d_payload(
    payload: Field2DRunFromScenarioRequest,
    metadata: dict[str, Any] | None,
) -> Field2DRunFromScenarioRequest:
    data = _field_2d_config(metadata)
    data.update(payload.model_dump(exclude_unset=True))
    return Field2DRunFromScenarioRequest(**data)


def _blackoil_payload(payload: OpmBlackOilModelPrepareRequest | None) -> Field2DRunFromScenarioRequest:
    payload = payload or OpmBlackOilModelPrepareRequest(run_external_flow=False)
    data = payload.model_dump(exclude={"forecast_method", "model_radius_m"}, exclude_unset=True)
    if payload.model_radius_m is not None:
        data["influence_radius_m"] = payload.model_radius_m
    return Field2DRunFromScenarioRequest(**data)


def _payload_with_crm_options(
    payload: CrmConnectivityRequest | RegionCubeBuildRequest | None,
    *,
    run_external_flow: bool = False,
) -> Field2DRunFromScenarioRequest:
    crm = getattr(payload, "crm", {}) if payload is not None else {}
    allocation = getattr(payload, "allocation", {}) if payload is not None else {}
    options = crm if isinstance(crm, dict) else {}
    allocation_options = allocation if isinstance(allocation, dict) else {}
    metadata = {
        "min_connection_weight": options.get("min_connection_weight", 0.03),
        "allow_cross_lu": options.get("allow_cross_lu", False),
        "allow_cross_sloy": options.get("allow_cross_sloy", False),
        "allocation": allocation_options,
    }
    return Field2DRunFromScenarioRequest(
        run_external_flow=run_external_flow,
        influence_radius_m=float(options.get("radius_m") or 3000.0),
        nearest_producers_per_injector=int(options.get("max_connections_per_producer") or 4),
        region_corridor_width_m=float(allocation_options.get("corridor_width_m") or 225.0),
        well_region_radius_m=float(allocation_options.get("well_region_radius_m") or 150.0),
        metadata=metadata,
    )


def _build_field_2d_prepare_request_from_context(
    db: Session,
    scenario_id: str,
    payload: Field2DRunFromScenarioRequest,
) -> Field2DPrepareRequest:
    scenario = ScenarioRepository(db).get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    context = _scenario_context(scenario.metadata_json)
    payload = _merge_field_2d_payload(payload, scenario.metadata_json)
    return Field2DPrepareRequest(
        scenario_id=scenario.scenario_id,
        scenario_name=scenario.name,
        well_groups=_normalized_payload_from_context(
            db,
            context,
            context_key="well_groups_dataset",
            expected_type="well_groups",
        ),
        trajectories=_normalized_payload_from_context(
            db,
            context,
            context_key="well_trajectories_dataset",
            expected_type="well_trajectories",
        ),
        perforations=_normalized_payload_from_context(
            db,
            context,
            context_key="perforations_dataset",
            expected_type="perforations",
        ),
        production_history=_normalized_payload_from_context(
            db,
            context,
            context_key="production_history_dataset",
            expected_type="production_history",
        ),
        injection_history=_normalized_payload_from_context(
            db,
            context,
            context_key="injection_history_dataset",
            expected_type="injection_history",
        ),
        initial_reserves=_normalized_payload_from_context(
            db,
            context,
            context_key="niz_dataset",
            expected_type="niz",
            required=True,
        ),
        pvt_include=_pvt_payload_from_context(db, context, required=True),
        dx_m=payload.dx_m,
        dy_m=payload.dy_m,
        dz_m=payload.dz_m,
        porosity=payload.porosity,
        permeability_md=payload.permeability_md,
        formation_volume_factor=payload.formation_volume_factor,
        initial_oil_saturation=payload.initial_oil_saturation,
        initial_pressure_bar=payload.initial_pressure_bar,
        initial_water_saturation=payload.initial_water_saturation,
        initial_gas_saturation=payload.initial_gas_saturation,
        datum_depth_m=payload.datum_depth_m,
        top_depth_m=payload.top_depth_m,
        nearest_producers_per_injector=payload.nearest_producers_per_injector,
        influence_radius_m=payload.influence_radius_m,
        well_region_radius_m=payload.well_region_radius_m,
        region_corridor_width_m=payload.region_corridor_width_m,
        grid_padding_m=payload.grid_padding_m,
        max_grid_cells=payload.max_grid_cells,
        history_match_iterations=payload.history_match_iterations,
        pressure_weight=payload.pressure_weight,
        watercut_weight=payload.watercut_weight,
        rate_weight=payload.rate_weight,
        pressure_tolerance_bar=payload.pressure_tolerance_bar,
        watercut_tolerance_fraction=payload.watercut_tolerance_fraction,
        allow_generated_pvt=payload.allow_generated_pvt,
        metadata=payload.metadata,
    )


@router.post("/scenarios/{scenario_id}/field-2d/prepare", response_model=Field2DPrepareResponse)
def prepare_field_2d_model(scenario_id: str, payload: Field2DPrepareRequest) -> Field2DPrepareResponse:
    if payload.scenario_id != scenario_id:
        raise HTTPException(status_code=400, detail="scenario_id in path and payload must match.")
    try:
        return Field2DModelService().prepare(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scenarios/{scenario_id}/model/prepare", response_model=Field2DPrepareResponse)
def prepare_blackoil_model_from_context(
    scenario_id: str,
    payload: OpmBlackOilModelPrepareRequest | None = None,
    db: Session = Depends(get_db),
) -> Field2DPrepareResponse:
    request = _build_field_2d_prepare_request_from_context(db, scenario_id, _blackoil_payload(payload))
    try:
        return Field2DModelService().prepare(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scenarios/{scenario_id}/crm-connectivity", response_model=CrmConnectivityResponse)
def build_crm_connectivity(
    scenario_id: str,
    payload: CrmConnectivityRequest | None = None,
    db: Session = Depends(get_db),
) -> CrmConnectivityResponse:
    request = _build_field_2d_prepare_request_from_context(db, scenario_id, _payload_with_crm_options(payload))
    try:
        preparation = Field2DModelService().prepare(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CrmConnectivityResponse(
        scenario_id=scenario_id,
        run_id=payload.run_id if payload else None,
        connectivity=preparation.regions,
        region_cube=preparation.grid.get("region_cube", {}),
        diagnostics={
            "crm": preparation.diagnostics.get("crm", {}),
            "warnings": preparation.diagnostics.get("warnings", []),
        },
    )


@router.post("/scenarios/{scenario_id}/region-cube/build", response_model=RegionCubeBuildResponse)
def build_region_cube(
    scenario_id: str,
    payload: RegionCubeBuildRequest | None = None,
    db: Session = Depends(get_db),
) -> RegionCubeBuildResponse:
    request = _build_field_2d_prepare_request_from_context(db, scenario_id, _payload_with_crm_options(payload))
    try:
        preparation = Field2DModelService().prepare(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegionCubeBuildResponse(
        scenario_id=scenario_id,
        run_id=payload.run_id if payload else None,
        region_cube=preparation.grid.get("region_cube", {}),
        diagnostics=preparation.diagnostics,
    )


@router.post("/scenarios/{scenario_id}/calibration/start", response_model=CalibrationRunResponse)
def start_calibration(
    scenario_id: str,
    payload: CalibrationStartRequest | None = None,
    db: Session = Depends(get_db),
) -> CalibrationRunResponse:
    payload = payload or CalibrationStartRequest()
    run_options = Field2DRunFromScenarioRequest(run_external_flow=payload.run_external_flow)
    weights = payload.objective_weights if isinstance(payload.objective_weights, dict) else {}
    criteria = payload.criteria if isinstance(payload.criteria, dict) else {}
    updates: dict[str, Any] = {
        "run_external_flow": payload.run_external_flow,
        "pressure_weight": weights.get("pressure", run_options.pressure_weight),
        "watercut_weight": weights.get("watercut", run_options.watercut_weight),
        "rate_weight": weights.get("rate", run_options.rate_weight),
        "pressure_tolerance_bar": criteria.get("pressure_tolerance_bar", run_options.pressure_tolerance_bar),
        "watercut_tolerance_fraction": criteria.get("watercut_tolerance_fraction", run_options.watercut_tolerance_fraction),
    }
    run_options = run_options.model_copy(update=updates)
    request = _build_field_2d_prepare_request_from_context(db, scenario_id, run_options)
    try:
        response = Field2DModelService().run(request, run_options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    report = response.analysis.get("calibration", {})
    return CalibrationRunResponse(
        calibration_id=f"calib-{response.simulation_run.run_id[:8]}",
        scenario_id=scenario_id,
        run_id=response.simulation_run.run_id,
        status=str(report.get("status") or "unknown"),
        current_iteration=len(report.get("iterations", [])) if isinstance(report.get("iterations"), list) else 0,
        best_objective=report.get("best_objective"),
        simulation_run=response.simulation_run,
        report=report,
        artifacts=response.simulation_run.artifacts,
    )


@router.get("/scenarios/{scenario_id}/calibration/{calibration_id}", response_model=CalibrationRunResponse)
def get_calibration_status(scenario_id: str, calibration_id: str) -> CalibrationRunResponse:
    service = Field2DModelService()
    try:
        run = service.latest_run(scenario_id)
        analysis = service.load_analysis(scenario_id, run.run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Calibration result not found.") from exc
    report = analysis.get("calibration", {})
    return CalibrationRunResponse(
        calibration_id=calibration_id,
        scenario_id=scenario_id,
        run_id=run.run_id,
        status=str(report.get("status") or "unknown"),
        current_iteration=len(report.get("iterations", [])) if isinstance(report.get("iterations"), list) else 0,
        best_objective=report.get("best_objective"),
        simulation_run=run,
        report=report,
        artifacts=run.artifacts,
    )


@router.post("/scenarios/{scenario_id}/calibration/{calibration_id}/promote")
def promote_calibrated_model(
    scenario_id: str,
    calibration_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = Field2DModelService()
    try:
        run = service.latest_run(scenario_id)
        analysis = service.load_analysis(scenario_id, run.run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Calibration result not found.") from exc
    report = analysis.get("calibration", {})
    repo = ScenarioRepository(db)
    scenario = repo.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    metadata = dict(scenario.metadata_json or {})
    metadata["forecast_method"] = "opm_flow_blackoil"
    metadata["calibrated_run_id"] = run.run_id
    metadata["calibration_id"] = calibration_id
    metadata["calibration_status"] = report.get("status")
    metadata["ready_for_forecast"] = report.get("status") in {"calibrated", "partial", "diagnostic_only"}
    repo.update_scenario(scenario_id, metadata=metadata)
    return {
        "scenario_id": scenario_id,
        "calibration_id": calibration_id,
        "run_id": run.run_id,
        "status": report.get("status"),
        "ready_for_forecast": metadata["ready_for_forecast"],
    }


@router.post("/scenarios/{scenario_id}/field-2d/prepare-from-context", response_model=Field2DPrepareResponse)
def prepare_field_2d_model_from_context(
    scenario_id: str,
    payload: Field2DRunFromScenarioRequest | None = None,
    db: Session = Depends(get_db),
) -> Field2DPrepareResponse:
    payload = payload or Field2DRunFromScenarioRequest(run_external_flow=False)
    request = _build_field_2d_prepare_request_from_context(db, scenario_id, payload)
    try:
        return Field2DModelService().prepare(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scenarios/{scenario_id}/field-2d/run-from-context", response_model=Field2DRunResponse)
def run_field_2d_model_from_context(
    scenario_id: str,
    payload: Field2DRunFromScenarioRequest | None = None,
    db: Session = Depends(get_db),
) -> Field2DRunResponse:
    payload = payload or Field2DRunFromScenarioRequest()
    request = _build_field_2d_prepare_request_from_context(db, scenario_id, payload)
    try:
        return Field2DModelService().run(request, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}/field-2d/latest-analysis")
def get_latest_field_2d_analysis(scenario_id: str) -> dict[str, Any]:
    service = Field2DModelService()
    try:
        run = service.latest_run(scenario_id)
        analysis = service.load_analysis(scenario_id, run.run_id)
        return {"simulation_run": run.model_dump(mode="json"), "analysis": analysis}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Field 2D analysis not found.") from exc


@router.post("/case", response_model=SimulationRun)
def build_opm_case(payload: OpmCaseBuildRequest) -> SimulationRun:
    return _service().build_case(payload)


@router.post("/scenarios/{scenario_id}/runs/{run_id}/run", response_model=SimulationRun)
def run_opm_case(scenario_id: str, run_id: str) -> SimulationRun:
    try:
        return _service().run_case(scenario_id, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Simulation run не найден.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/scenarios/{scenario_id}/runs/{run_id}/import", response_model=SimulationRun)
def import_opm_results(scenario_id: str, run_id: str) -> SimulationRun:
    try:
        return _service().import_results(scenario_id, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Simulation run не найден.") from exc


@router.get("/scenarios/{scenario_id}/runs", response_model=list[SimulationRun])
def list_opm_runs(scenario_id: str) -> list[SimulationRun]:
    return _service().list_runs(scenario_id)


@router.get("/scenarios/{scenario_id}/runs/{run_id}", response_model=SimulationRun)
def get_opm_run(scenario_id: str, run_id: str) -> SimulationRun:
    try:
        return _service().get_run(scenario_id, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Simulation run не найден.") from exc
