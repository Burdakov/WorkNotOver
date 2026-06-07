from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.services.opm_flow import OpmFlowSimulationService, OpmTemplateSyntheticService
from app.services.opm_flow.drainage_1d import Drainage1DPreparationService
from app.services.opm_flow.schemas import (
    Drainage1DPrepareFromScenarioRequest,
    Drainage1DPrepareRequest,
    Drainage1DPrepareResponse,
    OpmCaseBuildRequest,
    OpmTemplateSyntheticRequest,
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


@router.post("/scenarios/{scenario_id}/drainage-1d/prepare", response_model=Drainage1DPrepareResponse)
def prepare_drainage_1d_models(scenario_id: str, payload: Drainage1DPrepareRequest) -> Drainage1DPrepareResponse:
    if payload.scenario_id != scenario_id:
        raise HTTPException(status_code=400, detail="scenario_id in path and payload must match.")
    return Drainage1DPreparationService().prepare(payload)


def _scenario_context(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    context = metadata.get(_SCENARIO_CONTEXT_KEY)
    return context if isinstance(context, dict) else {}


def _normalized_payload_from_context(
    db: Session,
    context: dict[str, Any],
    *,
    context_key: str,
    expected_type: str,
    required: bool = True,
) -> list[dict[str, Any]]:
    reference = context.get(context_key)
    if not isinstance(reference, dict):
        if required:
            raise HTTPException(status_code=400, detail=f"Scenario has no bound dataset '{expected_type}'.")
        return []
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
        return []
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail=f"Dataset '{expected_type}' normalized payload must be a list.")
    return [row for row in payload if isinstance(row, dict)]


@router.post("/scenarios/{scenario_id}/drainage-1d/prepare-from-context", response_model=Drainage1DPrepareResponse)
def prepare_drainage_1d_models_from_context(
    scenario_id: str,
    payload: Drainage1DPrepareFromScenarioRequest | None = None,
    db: Session = Depends(get_db),
) -> Drainage1DPrepareResponse:
    scenario = ScenarioRepository(db).get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    payload = payload or Drainage1DPrepareFromScenarioRequest()
    context = _scenario_context(scenario.metadata_json)
    request = Drainage1DPrepareRequest(
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
            required=False,
        ),
        influence_radius_m=payload.influence_radius_m,
        distance_kernel_power=payload.distance_kernel_power,
        grid_block_length_m=payload.grid_block_length_m,
        grid_block_width_m=payload.grid_block_width_m,
        grid_thickness_m=payload.grid_thickness_m,
        metadata=payload.metadata,
    )
    return Drainage1DPreparationService().prepare(request)


@router.post("/case", response_model=SimulationRun)
def build_opm_case(payload: OpmCaseBuildRequest) -> SimulationRun:
    return _service().build_case(payload)


@router.post("/templates/synthetic-history")
def run_template_synthetic_history(payload: OpmTemplateSyntheticRequest) -> dict:
    return OpmTemplateSyntheticService().run(payload)


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
