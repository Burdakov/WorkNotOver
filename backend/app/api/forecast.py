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

router = APIRouter(prefix="/api/forecast", tags=["module-b"])


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
        raise HTTPException(status_code=400, detail="Normalized payload должен быть списком объектов.")

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


def _well_key(item: dict) -> str:
    well_id = str(item.get("well_id") or "").strip()
    if well_id:
        return well_id
    return str(item.get("well_name") or "").strip()


def _coerce_float(value, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_niz_lookup(payload: list[dict]) -> dict[str, float]:
    lookup: dict[str, float] = {}
    for item in payload:
        well_key = _well_key(item)
        niz_value = _coerce_float(item.get("niz"))
        if well_key and niz_value > 0:
            lookup[well_key] = niz_value
    return lookup


def _attach_niz_to_payload(payload: list[dict], niz_lookup: dict[str, float]) -> list[dict]:
    enriched: list[dict] = []
    for item in payload:
        item_copy = dict(item)
        well_key = _well_key(item_copy)
        if well_key and well_key in niz_lookup:
            item_copy["niz"] = niz_lookup[well_key]
        enriched.append(item_copy)
    return enriched


def _validate_niz_coverage(
    *,
    wells_payload: list[dict],
    gtm_payload: list[dict],
    niz_payload: list[dict],
) -> dict[str, float]:
    niz_lookup = _build_niz_lookup(niz_payload)
    if not niz_lookup:
        raise HTTPException(status_code=400, detail="Dataset NIZ не содержит валидных значений для расчета.")

    wells_keys = {_well_key(item) for item in wells_payload if _well_key(item)}
    gtm_keys = {_well_key(item) for item in gtm_payload if _well_key(item)}
    niz_keys = set(niz_lookup)

    missing_for_wells = sorted(wells_keys - niz_keys)
    if missing_for_wells:
        preview = ", ".join(missing_for_wells[:5])
        suffix = "..." if len(missing_for_wells) > 5 else ""
        raise HTTPException(
            status_code=400,
            detail=f"В wells dataset есть скважины без NIZ в scenario-bound dataset: {preview}{suffix}",
        )

    missing_for_gtm = sorted(gtm_keys - niz_keys)
    if missing_for_gtm:
        preview = ", ".join(missing_for_gtm[:5])
        suffix = "..." if len(missing_for_gtm) > 5 else ""
        raise HTTPException(
            status_code=400,
            detail=f"В GTM dataset есть скважины без NIZ в scenario-bound dataset: {preview}{suffix}",
        )

    return niz_lookup


@router.post("/calculate", response_model=ForecastCalculateResponse)
def calculate_forecast(payload: ForecastCalculateRequest, db: Session = Depends(get_db)) -> ForecastCalculateResponse:
    wells_reference, wells_payload = _resolve_dataset(
        db,
        dataset_id=payload.wells.dataset_id,
        dataset_version_id=payload.wells.dataset_version_id,
        expected_type="wells",
    )
    niz_reference, niz_payload = _resolve_dataset(
        db,
        dataset_id=payload.niz.dataset_id,
        dataset_version_id=payload.niz.dataset_version_id,
        expected_type="niz",
    )
    gtm_reference, gtm_payload = _resolve_dataset(
        db,
        dataset_id=payload.gtm.dataset_id,
        dataset_version_id=payload.gtm.dataset_version_id,
        expected_type="gtm",
    )
    manual_input_reference, manual_input_payload = _resolve_manual_inputs(db, payload.manual_input_set_id)
    niz_lookup = _validate_niz_coverage(
        wells_payload=wells_payload,
        gtm_payload=gtm_payload,
        niz_payload=niz_payload,
    )
    wells_payload = _attach_niz_to_payload(wells_payload, niz_lookup)
    gtm_payload = _attach_niz_to_payload(gtm_payload, niz_lookup)

    service = ForecastService(
        wells_reference=wells_reference,
        wells_payload=wells_payload,
        niz_reference=niz_reference,
        gtm_reference=gtm_reference,
        gtm_payload=gtm_payload,
        manual_input_reference=manual_input_reference,
        manual_input_payload=manual_input_payload,
    )
    result = service.calculate(payload)

    saved_scenario, _ = ScenarioRepository(db).create_scenario_with_result(
        name=result.scenario.name,
        source_type=result.scenario.source_type,
        parent_scenario_id=result.scenario.parent_scenario_id,
        forecast_start_date=result.scenario.forecast_start_date,
        forecast_end_date=result.scenario.forecast_end_date,
        metadata=result.scenario.metadata,
        production_summary=result.production_summary.model_dump(),
        production_points=[item.model_dump() for item in result.production_points],
        well_results=[item.model_dump() for item in result.wells],
        source_payload={
            "wells_dataset": wells_reference.model_dump(),
            "niz_dataset": niz_reference.model_dump(),
            "gtm_dataset": gtm_reference.model_dump(),
            "manual_input_set": manual_input_reference.model_dump(),
            "request": payload.model_dump(),
        },
    )

    result.scenario = ScenarioModelResponse(
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
    result.niz_dataset = niz_reference
    return result


@router.get("/scenarios")
def list_scenarios(db: Session = Depends(get_db)) -> list[dict]:
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
        for scenario, result in ScenarioRepository(db).list_scenarios()
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
