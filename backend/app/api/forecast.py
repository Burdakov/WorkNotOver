from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.manual_input_repository import ManualInputRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.schemas.common import DatasetReference, ManualInputReference
from app.schemas.forecast_models import ForecastCalculateRequest, ForecastCalculateResponse, ScenarioModelResponse
from app.services.forecast_service import ForecastService

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _resolve_dataset(
    db: Session,
    *,
    dataset_id: str,
    dataset_version_id: str | None,
    expected_type: str,
) -> tuple[DatasetReference, list[dict]]:
    resolved = DatasetRepository(db).get_dataset_version(dataset_id, dataset_version_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Dataset не найден.")
    dataset, version = resolved
    if dataset.dataset_type != expected_type:
        raise HTTPException(
            status_code=400,
            detail=f"Ожидался dataset типа '{expected_type}', получен '{dataset.dataset_type}'.",
        )
    payload = version.normalized_payload_json
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="Normalized payload dataset должен быть списком объектов.")
    reference = DatasetReference(
        dataset_id=dataset.dataset_id,
        dataset_version_id=version.dataset_version_id,
        dataset_type=dataset.dataset_type,
        name=dataset.name,
        row_count=version.row_count,
        created_at=dataset.created_at.isoformat(),
        metadata=dataset.metadata_json,
    )
    return reference, payload


def _resolve_manual_inputs(db: Session, manual_input_set_id: str) -> tuple[ManualInputReference, dict]:
    item = ManualInputRepository(db).get_payload(manual_input_set_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Набор ручных вводных не найден.")
    return (
        ManualInputReference(
            manual_input_set_id=item.manual_input_set_id,
            name=item.name,
            created_at=item.created_at.isoformat(),
            metadata=item.metadata_json,
        ),
        dict(item.payload_json or {}),
    )


@router.post("/calculate", response_model=ForecastCalculateResponse)
def calculate_forecast(payload: ForecastCalculateRequest, db: Session = Depends(get_db)) -> ForecastCalculateResponse:
    wells_reference, wells_payload = _resolve_dataset(
        db,
        dataset_id=payload.wells.dataset_id,
        dataset_version_id=payload.wells.dataset_version_id,
        expected_type="wells",
    )
    gtm_reference, gtm_payload = _resolve_dataset(
        db,
        dataset_id=payload.gtm.dataset_id,
        dataset_version_id=payload.gtm.dataset_version_id,
        expected_type="gtm",
    )
    manual_input_reference, manual_input_payload = _resolve_manual_inputs(db, payload.manual_input_set_id)

    service = ForecastService(
        wells_reference=wells_reference,
        wells_payload=wells_payload,
        gtm_reference=gtm_reference,
        gtm_payload=gtm_payload,
        manual_input_reference=manual_input_reference,
        manual_input_payload=manual_input_payload,
    )
    response = service.calculate(payload)

    scenario_repo = ScenarioRepository(db)
    saved_scenario, _ = scenario_repo.create_scenario_with_result(
        name=response.scenario.name,
        source_type=response.scenario.source_type,
        parent_scenario_id=response.scenario.parent_scenario_id,
        forecast_start_date=response.scenario.forecast_start_date,
        forecast_end_date=response.scenario.forecast_end_date,
        metadata=response.scenario.metadata,
        production_summary=response.production_summary.model_dump(),
        production_points=[point.model_dump() for point in response.production_points],
        well_results=[item.model_dump() for item in response.wells],
        source_payload={
            "wells_dataset": wells_reference.model_dump(),
            "gtm_dataset": gtm_reference.model_dump(),
            "manual_input_set": manual_input_reference.model_dump(),
            "request": payload.model_dump(),
        },
    )

    response.scenario = ScenarioModelResponse(
        scenario_id=saved_scenario.scenario_id,
        name=saved_scenario.name,
        source_type=saved_scenario.source_type,
        parent_scenario_id=saved_scenario.parent_scenario_id,
        forecast_start_date=saved_scenario.forecast_start_date,
        forecast_end_date=saved_scenario.forecast_end_date,
        created_at=saved_scenario.created_at.isoformat(),
        status=saved_scenario.status,
        metadata=saved_scenario.metadata_json,
    )
    return response


@router.get("/scenarios")
def list_scenarios(db: Session = Depends(get_db)) -> list[dict]:
    items = ScenarioRepository(db).list_scenarios()
    return [
        {
            "scenario_id": scenario.scenario_id,
            "name": scenario.name,
            "source_type": scenario.source_type,
            "parent_scenario_id": scenario.parent_scenario_id,
            "forecast_start_date": scenario.forecast_start_date,
            "forecast_end_date": scenario.forecast_end_date,
            "created_at": scenario.created_at.isoformat(),
            "status": scenario.status,
            "metadata": scenario.metadata_json,
            "latest_result_created_at": result.created_at.isoformat() if result else None,
            "production_summary": result.production_summary_json if result else None,
        }
        for scenario, result in items
    ]


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, db: Session = Depends(get_db)) -> dict:
    resolved = ScenarioRepository(db).get_latest_result(scenario_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")
    scenario, result = resolved
    return {
        "scenario": {
            "scenario_id": scenario.scenario_id,
            "name": scenario.name,
            "source_type": scenario.source_type,
            "parent_scenario_id": scenario.parent_scenario_id,
            "forecast_start_date": scenario.forecast_start_date,
            "forecast_end_date": scenario.forecast_end_date,
            "created_at": scenario.created_at.isoformat(),
            "status": scenario.status,
            "metadata": scenario.metadata_json,
        },
        "production_summary": result.production_summary_json,
        "production_points": result.production_points_json,
        "wells": result.well_results_json,
        "source_payload": result.source_payload_json,
        "metadata": result.metadata_json,
        "result_created_at": result.created_at.isoformat(),
    }
