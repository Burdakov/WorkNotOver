from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.manual_input_repository import ManualInputRepository
from app.repositories.planner_revision_repository import PlannerRevisionRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.schemas.common import DatasetReference, ManualInputReference
from app.schemas.forecast_models import (
    ForecastCalculateRequest,
    ScenarioContextResponse,
    ScenarioDetailResponse,
    ScenarioInputBindings,
    ScenarioInputNodeValidation,
    ScenarioInputValidationResponse,
    ScenarioListItemResponse,
    ScenarioModelResponse,
    ScenarioRecalculateFromRevisionRequest,
    ScenarioUpsertRequest,
)
from app.schemas.schedule_models import ScheduleItem
from app.services.forecast_service import ForecastService

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])

_SCENARIO_CONTEXT_KEY = "scenario_context"
_PURE_BASE_SCENARIO_NAME = "чистая База"
_PURE_BASE_SCENARIO_ROLE = "pure_base"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _context_to_response(context: dict[str, Any] | None) -> ScenarioContextResponse:
    context = context or {}
    return ScenarioContextResponse(
        wells_dataset=DatasetReference(**context["wells_dataset"]) if context.get("wells_dataset") else None,
        niz_dataset=DatasetReference(**context["niz_dataset"]) if context.get("niz_dataset") else None,
        gtm_dataset=DatasetReference(**context["gtm_dataset"]) if context.get("gtm_dataset") else None,
        infrastructure_dataset=DatasetReference(**context["infrastructure_dataset"]) if context.get("infrastructure_dataset") else None,
        external_krs_schedule_dataset=DatasetReference(**context["external_krs_schedule_dataset"]) if context.get("external_krs_schedule_dataset") else None,
        manual_input_set=ManualInputReference(**context["manual_input_set"]) if context.get("manual_input_set") else None,
    )


def _extract_context(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    context = metadata.get(_SCENARIO_CONTEXT_KEY)
    return context if isinstance(context, dict) else {}


def _is_pure_base_metadata(metadata: dict[str, Any] | None) -> bool:
    return isinstance(metadata, dict) and metadata.get("scenario_role") == _PURE_BASE_SCENARIO_ROLE


def _merge_metadata(
    *,
    existing_metadata: dict[str, Any] | None,
    context: dict[str, Any],
    patch_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(existing_metadata or {})
    if patch_metadata:
        merged.update(patch_metadata)
    merged[_SCENARIO_CONTEXT_KEY] = context
    return merged


def _resolve_dataset_reference(
    db: Session,
    selection,
    *,
    expected_type: str,
) -> DatasetReference:
    resolved = DatasetRepository(db).get_dataset_version(selection.dataset_id, selection.dataset_version_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Dataset '{expected_type}' не найден.")
    dataset, version = resolved
    if dataset.dataset_type != expected_type:
        raise HTTPException(status_code=400, detail=f"Ожидался dataset типа '{expected_type}', получен '{dataset.dataset_type}'.")
    return DatasetReference(
        dataset_id=dataset.dataset_id,
        dataset_version_id=version.dataset_version_id,
        dataset_type=dataset.dataset_type,
        name=dataset.name,
        row_count=version.row_count,
        created_at=dataset.created_at.isoformat(),
        metadata=dataset.metadata_json,
    )


def _resolve_manual_input_reference(db: Session, manual_input_set_id: str) -> ManualInputReference:
    item = ManualInputRepository(db).get_payload(manual_input_set_id)
    if item is None:
        raise HTTPException(status_code=404, detail="ManualInputSet не найден.")
    return ManualInputReference(
        manual_input_set_id=item.manual_input_set_id,
        name=item.name,
        created_at=item.created_at.isoformat(),
        metadata=item.metadata_json,
    )


def _scenario_response(scenario) -> ScenarioModelResponse:
    return ScenarioModelResponse(
        scenario_id=scenario.scenario_id,
        name=scenario.name,
        source_type=scenario.source_type,
        parent_scenario_id=scenario.parent_scenario_id,
        forecast_start_date=scenario.forecast_start_date,
        forecast_end_date=scenario.forecast_end_date,
        created_at=scenario.created_at.isoformat(),
        status=scenario.status,
        metadata=scenario.metadata_json,
    )


def _scenario_detail_payload(db: Session, scenario, result) -> ScenarioDetailResponse:
    context = _context_to_response(_extract_context(scenario.metadata_json))
    return ScenarioDetailResponse(
        scenario=_scenario_response(scenario),
        context=context,
        input_validation=_build_input_validation(db, scenario, context),
        production_summary=result.production_summary_json if result else None,
        production_points=result.production_points_json if result and result.production_points_json else [],
        wells=result.well_results_json if result and result.well_results_json else [],
        source_payload=result.source_payload_json if result else None,
        metadata=result.metadata_json if result else scenario.metadata_json,
        result_created_at=result.created_at.isoformat() if result else None,
    )


def _resolve_payload_from_reference(db: Session, reference: DatasetReference, *, expected_type: str) -> list[dict[str, Any]]:
    resolved = DatasetRepository(db).get_dataset_version(reference.dataset_id, reference.dataset_version_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Dataset '{expected_type}' не найден.")
    dataset, version = resolved
    if dataset.dataset_type != expected_type:
        raise HTTPException(status_code=400, detail=f"Ожидался dataset типа '{expected_type}', получен '{dataset.dataset_type}'.")
    payload = version.normalized_payload_json
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail=f"Normalized payload dataset '{expected_type}' должен быть списком.")
    return payload


def _resolve_manual_input_payload(db: Session, reference: ManualInputReference) -> dict[str, Any]:
    item = ManualInputRepository(db).get_payload(reference.manual_input_set_id)
    if item is None:
        raise HTTPException(status_code=404, detail="ManualInputSet не найден.")
    return dict(item.payload_json or {})


def _make_input_node_validation(state: str, *issues: str) -> ScenarioInputNodeValidation:
    return ScenarioInputNodeValidation(
        state=state,
        issues=[issue for issue in issues if issue],
    )


def _well_key_from_payload(item: dict[str, Any]) -> str:
    well_id = str(item.get("well_id") or "").strip()
    if well_id:
        return well_id
    return str(item.get("well_name") or "").strip()


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _add_node_issue(node: ScenarioInputNodeValidation, issue: str) -> None:
    if issue and issue not in node.issues:
        node.issues.append(issue)


def _mark_node_partial(node: ScenarioInputNodeValidation, issue: str) -> None:
    node.state = "partial"
    _add_node_issue(node, issue)


def _build_niz_lookup(payload: list[dict[str, Any]]) -> dict[str, float]:
    lookup: dict[str, float] = {}
    for item in payload:
        well_key = _well_key_from_payload(item)
        niz_value = _coerce_float(item.get("niz"))
        if well_key and niz_value > 0:
            lookup[well_key] = niz_value
    return lookup


def _attach_niz_to_payload(payload: list[dict[str, Any]], niz_lookup: dict[str, float]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in payload:
        item_copy = dict(item)
        well_key = _well_key_from_payload(item_copy)
        if well_key and well_key in niz_lookup:
            item_copy["niz"] = niz_lookup[well_key]
        enriched.append(item_copy)
    return enriched


def _extract_external_schedule_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    schedule = payload.get("schedule")
    if not isinstance(schedule, dict):
        return []
    items = schedule.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _build_input_validation_legacy(db: Session, scenario, context: ScenarioContextResponse) -> ScenarioInputValidationResponse:
    validation = ScenarioInputValidationResponse(
        wells=_make_input_node_validation("ready" if context.wells_dataset else "empty"),
        gtm=_make_input_node_validation("ready" if context.gtm_dataset else "empty"),
        infrastructure=_make_input_node_validation("ready" if context.infrastructure_dataset else "empty"),
        external_krs_schedule=_make_input_node_validation("ready" if context.external_krs_schedule_dataset else "empty"),
        manual_input_set=_make_input_node_validation("ready" if context.manual_input_set else "empty"),
    )

    scenario_mode = str((scenario.metadata_json or {}).get("scenario_source_mode") or "")
    requires_external = scenario_mode == "existing_krs"

    issues: list[str] = []
    if validation.wells.state != "ready":
        issues.append("Не привязан dataset wells.")
    if validation.gtm.state != "ready":
        issues.append("Не привязан dataset GTM.")
    if validation.manual_input_set.state != "ready":
        issues.append("Не привязан ManualInputSet.")
    if requires_external and validation.external_krs_schedule.state != "ready":
        issues.append("Для сценария с внешним графиком КРС должен быть привязан dataset external_krs_schedule.")

    external_items: list[dict[str, Any]] = []
    if context.external_krs_schedule_dataset is not None:
        resolved = DatasetRepository(db).get_dataset_version(
            context.external_krs_schedule_dataset.dataset_id,
            context.external_krs_schedule_dataset.dataset_version_id,
        )
        if resolved is not None:
            _, version = resolved
            external_items = _extract_external_schedule_items(version.normalized_payload_json)
        if not external_items:
            issue = "Во внешнем графике КРС нет нормализованных schedule items."
            validation.external_krs_schedule = _make_input_node_validation("partial", issue)
            issues.append(issue)

    if external_items:
        external_wells = {
            _well_key_from_payload(item)
            for item in external_items
            if _well_key_from_payload(item)
        }
        wells_payload: list[dict[str, Any]] = []
        if context.wells_dataset is not None:
            wells_payload = _resolve_payload_from_reference(db, context.wells_dataset, expected_type="wells")
        gtm_payload: list[dict[str, Any]] = []
        if context.gtm_dataset is not None:
            gtm_payload = _resolve_payload_from_reference(db, context.gtm_dataset, expected_type="gtm")

        wells_keys = {_well_key_from_payload(item) for item in wells_payload if _well_key_from_payload(item)}
        gtm_keys = {_well_key_from_payload(item) for item in gtm_payload if _well_key_from_payload(item)}

        missing_in_wells = sorted(external_wells - wells_keys)
        missing_in_gtm = sorted(external_wells - gtm_keys)

        if missing_in_wells:
            preview = ", ".join(missing_in_wells[:5])
            suffix = "..." if len(missing_in_wells) > 5 else ""
            issue = f"Во внешнем графике КРС есть скважины, отсутствующие в wells dataset: {preview}{suffix}"
            validation.wells = _make_input_node_validation("partial", issue)
            issues.append(issue)
        if missing_in_gtm:
            preview = ", ".join(missing_in_gtm[:5])
            suffix = "..." if len(missing_in_gtm) > 5 else ""
            issue = f"Во внешнем графике КРС есть скважины, отсутствующие в GTM dataset: {preview}{suffix}"
            validation.gtm = _make_input_node_validation("partial", issue)
            issues.append(issue)

    validation.issues = issues
    validation.is_forecast_ready = not issues
    return validation


def _build_input_validation(db: Session, scenario, context: ScenarioContextResponse) -> ScenarioInputValidationResponse:
    validation = ScenarioInputValidationResponse(
        wells=_make_input_node_validation("ready" if context.wells_dataset else "empty"),
        niz=_make_input_node_validation("ready" if context.niz_dataset else "empty"),
        gtm=_make_input_node_validation("ready" if context.gtm_dataset else "empty"),
        infrastructure=_make_input_node_validation("ready" if context.infrastructure_dataset else "empty"),
        external_krs_schedule=_make_input_node_validation("ready" if context.external_krs_schedule_dataset else "empty"),
        manual_input_set=_make_input_node_validation("ready" if context.manual_input_set else "empty"),
    )

    scenario_mode = str((scenario.metadata_json or {}).get("scenario_source_mode") or "")
    requires_external = scenario_mode == "existing_krs"

    issues: list[str] = []
    if validation.wells.state != "ready":
        issue = "Не привязан dataset wells."
        _add_node_issue(validation.wells, issue)
        issues.append(issue)
    if validation.niz.state != "ready":
        issue = "Не привязан dataset NIZ."
        _add_node_issue(validation.niz, issue)
        issues.append(issue)
    if validation.gtm.state != "ready":
        issue = "Не привязан dataset GTM."
        _add_node_issue(validation.gtm, issue)
        issues.append(issue)
    if validation.manual_input_set.state != "ready":
        issue = "Не привязан ManualInputSet."
        _add_node_issue(validation.manual_input_set, issue)
        issues.append(issue)
    if requires_external and validation.external_krs_schedule.state != "ready":
        issue = "Для сценария с внешним графиком КРС должен быть привязан dataset external_krs_schedule."
        _add_node_issue(validation.external_krs_schedule, issue)
        issues.append(issue)

    wells_payload: list[dict[str, Any]] = []
    gtm_payload: list[dict[str, Any]] = []
    niz_payload: list[dict[str, Any]] = []
    external_items: list[dict[str, Any]] = []

    if context.wells_dataset is not None:
        wells_payload = _resolve_payload_from_reference(db, context.wells_dataset, expected_type="wells")
    if context.gtm_dataset is not None:
        gtm_payload = _resolve_payload_from_reference(db, context.gtm_dataset, expected_type="gtm")
    if context.niz_dataset is not None:
        niz_payload = _resolve_payload_from_reference(db, context.niz_dataset, expected_type="niz")
    if context.external_krs_schedule_dataset is not None:
        resolved = DatasetRepository(db).get_dataset_version(
            context.external_krs_schedule_dataset.dataset_id,
            context.external_krs_schedule_dataset.dataset_version_id,
        )
        if resolved is not None:
            _, version = resolved
            external_items = _extract_external_schedule_items(version.normalized_payload_json)
        if not external_items:
            issue = "Во внешнем графике КРС нет нормализованных schedule items."
            _mark_node_partial(validation.external_krs_schedule, issue)
            issues.append(issue)

    if context.niz_dataset is not None and not niz_payload:
        issue = "В dataset NIZ нет нормализованных записей."
        _mark_node_partial(validation.niz, issue)
        issues.append(issue)

    if wells_payload or gtm_payload:
        wells_keys = {_well_key_from_payload(item) for item in wells_payload if _well_key_from_payload(item)}
        gtm_keys = {_well_key_from_payload(item) for item in gtm_payload if _well_key_from_payload(item)}
        niz_keys = set(_build_niz_lookup(niz_payload))

        missing_niz_for_wells = sorted(wells_keys - niz_keys)
        missing_niz_for_gtm = sorted(gtm_keys - niz_keys)

        if missing_niz_for_wells:
            preview = ", ".join(missing_niz_for_wells[:5])
            suffix = "..." if len(missing_niz_for_wells) > 5 else ""
            issue = f"В wells dataset есть скважины без NIZ в scenario-bound dataset: {preview}{suffix}"
            _mark_node_partial(validation.wells, issue)
            _mark_node_partial(validation.niz, issue)
            issues.append(issue)
        if missing_niz_for_gtm:
            preview = ", ".join(missing_niz_for_gtm[:5])
            suffix = "..." if len(missing_niz_for_gtm) > 5 else ""
            issue = f"В GTM dataset есть скважины без NIZ в scenario-bound dataset: {preview}{suffix}"
            _mark_node_partial(validation.gtm, issue)
            _mark_node_partial(validation.niz, issue)
            issues.append(issue)

    if external_items:
        external_wells = {
            _well_key_from_payload(item)
            for item in external_items
            if _well_key_from_payload(item)
        }
        wells_keys = {_well_key_from_payload(item) for item in wells_payload if _well_key_from_payload(item)}
        gtm_keys = {_well_key_from_payload(item) for item in gtm_payload if _well_key_from_payload(item)}

        missing_in_wells = sorted(external_wells - wells_keys)
        missing_in_gtm = sorted(external_wells - gtm_keys)

        if missing_in_wells:
            preview = ", ".join(missing_in_wells[:5])
            suffix = "..." if len(missing_in_wells) > 5 else ""
            issue = f"Во внешнем графике КРС есть скважины, отсутствующие в wells dataset: {preview}{suffix}"
            _mark_node_partial(validation.wells, issue)
            issues.append(issue)
        if missing_in_gtm:
            preview = ", ".join(missing_in_gtm[:5])
            suffix = "..." if len(missing_in_gtm) > 5 else ""
            issue = f"Во внешнем графике КРС есть скважины, отсутствующие в GTM dataset: {preview}{suffix}"
            _mark_node_partial(validation.gtm, issue)
            issues.append(issue)

    validation.issues = issues
    validation.is_forecast_ready = not issues
    return validation


def _ensure_pure_base_scenario(
    db: Session,
    *,
    source_scenario,
    context: dict[str, Any],
):
    repo = ScenarioRepository(db)
    existing = repo.find_child_scenario(
        parent_scenario_id=source_scenario.scenario_id,
        name=_PURE_BASE_SCENARIO_NAME,
        metadata_key="scenario_role",
        metadata_value=_PURE_BASE_SCENARIO_ROLE,
    )
    metadata = _merge_metadata(
        existing_metadata=existing.metadata_json if existing else source_scenario.metadata_json,
        context=context,
        patch_metadata={
            "scenario_role": _PURE_BASE_SCENARIO_ROLE,
            "source_scenario_id": source_scenario.scenario_id,
            "source_scenario_name": source_scenario.name,
        },
    )
    if existing is not None:
        return repo.update_scenario(
            existing.scenario_id,
            name=_PURE_BASE_SCENARIO_NAME,
            source_type=source_scenario.source_type,
            forecast_start_date=source_scenario.forecast_start_date,
            forecast_end_date=source_scenario.forecast_end_date,
            metadata=metadata,
            status="draft",
        )
    return repo.create_scenario(
        name=_PURE_BASE_SCENARIO_NAME,
        source_type=source_scenario.source_type,
        parent_scenario_id=source_scenario.scenario_id,
        forecast_start_date=source_scenario.forecast_start_date,
        forecast_end_date=source_scenario.forecast_end_date,
        metadata=metadata,
        status="draft",
    )


def _run_forecast_calculation(
    *,
    scenario,
    context: ScenarioContextResponse,
    wells_payload: list[dict[str, Any]],
    gtm_payload: list[dict[str, Any]],
    manual_input_payload: dict[str, Any],
    planner_revision_items: list[dict[str, Any]] | None = None,
    force_without_gtm: bool = False,
):
    service = ForecastService(
        wells_reference=context.wells_dataset,
        wells_payload=wells_payload,
        niz_reference=context.niz_dataset,
        gtm_reference=context.gtm_dataset,
        gtm_payload=[] if force_without_gtm else gtm_payload,
        manual_input_reference=context.manual_input_set,
        manual_input_payload=manual_input_payload,
        planner_revision_items=[] if force_without_gtm else planner_revision_items,
    )
    return service.calculate(
        ForecastCalculateRequest(
            name=scenario.name,
            wells={
                "dataset_id": context.wells_dataset.dataset_id,
                "dataset_version_id": context.wells_dataset.dataset_version_id,
            },
            niz={
                "dataset_id": context.niz_dataset.dataset_id,
                "dataset_version_id": context.niz_dataset.dataset_version_id,
            },
            gtm={
                "dataset_id": context.gtm_dataset.dataset_id,
                "dataset_version_id": context.gtm_dataset.dataset_version_id,
            },
            manual_input_set_id=context.manual_input_set.manual_input_set_id,
            forecast_start_date=scenario.forecast_start_date,
            forecast_end_date=scenario.forecast_end_date,
            source_type=scenario.source_type,
            parent_scenario_id=scenario.parent_scenario_id,
            metadata=scenario.metadata_json,
        )
    )


def _build_context_from_request(
    db: Session,
    *,
    bindings: ScenarioInputBindings,
    existing_context: dict[str, Any] | None,
) -> dict[str, Any]:
    context = dict(existing_context or {})
    if bindings.wells is not None:
        context["wells_dataset"] = _resolve_dataset_reference(db, bindings.wells, expected_type="wells").model_dump()
    if bindings.niz is not None:
        context["niz_dataset"] = _resolve_dataset_reference(db, bindings.niz, expected_type="niz").model_dump()
    if bindings.gtm is not None:
        context["gtm_dataset"] = _resolve_dataset_reference(db, bindings.gtm, expected_type="gtm").model_dump()
    if bindings.infrastructure is not None:
        context["infrastructure_dataset"] = _resolve_dataset_reference(db, bindings.infrastructure, expected_type="infrastructure").model_dump()
    if bindings.external_krs_schedule is not None:
        context["external_krs_schedule_dataset"] = _resolve_dataset_reference(
            db,
            bindings.external_krs_schedule,
            expected_type="external_krs_schedule",
        ).model_dump()
    if bindings.manual_input_set_id is not None:
        context["manual_input_set"] = _resolve_manual_input_reference(db, bindings.manual_input_set_id).model_dump()
    return context


def _calculate_for_scenario(
    db: Session,
    *,
    scenario_id: str,
    planner_revision_items: list[dict[str, Any]] | None = None,
) -> ScenarioDetailResponse:
    repo = ScenarioRepository(db)
    scenario = repo.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")

    context = _context_to_response(_extract_context(scenario.metadata_json))
    input_validation = _build_input_validation(db, scenario, context)
    if not input_validation.is_forecast_ready:
        raise HTTPException(
            status_code=400,
            detail=input_validation.issues[0] if input_validation.issues else "Сценарий недозаполнен для расчета добычи.",
        )

    wells_payload = _resolve_payload_from_reference(db, context.wells_dataset, expected_type="wells")
    gtm_payload = _resolve_payload_from_reference(db, context.gtm_dataset, expected_type="gtm")
    niz_payload = _resolve_payload_from_reference(db, context.niz_dataset, expected_type="niz")
    manual_input_payload = _resolve_manual_input_payload(db, context.manual_input_set)
    niz_lookup = _build_niz_lookup(niz_payload)
    wells_payload = _attach_niz_to_payload(wells_payload, niz_lookup)
    gtm_payload = _attach_niz_to_payload(gtm_payload, niz_lookup)

    pure_base_scenario_id: str | None = None
    is_pure_base = _is_pure_base_metadata(scenario.metadata_json)

    if is_pure_base:
        result = _run_forecast_calculation(
            scenario=scenario,
            context=context,
            wells_payload=wells_payload,
            gtm_payload=gtm_payload,
            manual_input_payload=manual_input_payload,
            force_without_gtm=True,
        )
    else:
        if gtm_payload:
            pure_base_scenario = _ensure_pure_base_scenario(
                db,
                source_scenario=scenario,
                context=context.model_dump(),
            )
            pure_base_scenario_id = pure_base_scenario.scenario_id
            pure_base_result = _run_forecast_calculation(
                scenario=pure_base_scenario,
                context=context,
                wells_payload=wells_payload,
                gtm_payload=gtm_payload,
                manual_input_payload=manual_input_payload,
                force_without_gtm=True,
            )
            repo.attach_result(
                scenario_id=pure_base_scenario.scenario_id,
                production_summary=pure_base_result.production_summary.model_dump(),
                production_points=[item.model_dump() for item in pure_base_result.production_points],
                well_results=[item.model_dump() for item in pure_base_result.wells],
                source_payload={
                    "scenario_context": context.model_dump(),
                    "planner_revision_applied": False,
                    "gtm_applied": False,
                    "scenario_role": _PURE_BASE_SCENARIO_ROLE,
                    "source_scenario_id": scenario.scenario_id,
                },
                metadata=pure_base_scenario.metadata_json,
            )

        scenario_metadata = dict(scenario.metadata_json or {})
        scenario_metadata.pop("pure_base_scenario_id", None)
        if pure_base_scenario_id:
            scenario_metadata["pure_base_scenario_id"] = pure_base_scenario_id
        scenario = repo.update_scenario(
            scenario.scenario_id,
            metadata=_merge_metadata(
                existing_metadata=scenario_metadata,
                context=context.model_dump(),
                patch_metadata=None,
            ),
        ) or scenario

        result = _run_forecast_calculation(
            scenario=scenario,
            context=context,
            wells_payload=wells_payload,
            gtm_payload=gtm_payload,
            manual_input_payload=manual_input_payload,
            planner_revision_items=planner_revision_items,
        )
    repo.attach_result(
        scenario_id=scenario_id,
        production_summary=result.production_summary.model_dump(),
        production_points=[item.model_dump() for item in result.production_points],
        well_results=[item.model_dump() for item in result.wells],
        source_payload={
            "scenario_context": context.model_dump(),
            "planner_revision_applied": bool(planner_revision_items),
            "gtm_applied": bool(gtm_payload) and not is_pure_base,
            "pure_base_scenario_id": pure_base_scenario_id,
        },
        metadata=scenario.metadata_json,
    )
    resolved = repo.get_scenario_with_latest_result(scenario_id)
    if resolved is None:
        raise HTTPException(status_code=500, detail="Не удалось прочитать рассчитанный сценарий.")
    return _scenario_detail_payload(db, *resolved)


@router.get("", response_model=list[ScenarioListItemResponse])
def list_scenarios(db: Session = Depends(get_db)) -> list[ScenarioListItemResponse]:
    items = []
    for scenario, result in ScenarioRepository(db).list_scenarios():
        context = _context_to_response(_extract_context(scenario.metadata_json))
        items.append(
            ScenarioListItemResponse(
                scenario_id=scenario.scenario_id,
                name=scenario.name,
                source_type=scenario.source_type,
                parent_scenario_id=scenario.parent_scenario_id,
                forecast_start_date=scenario.forecast_start_date,
                forecast_end_date=scenario.forecast_end_date,
                created_at=scenario.created_at.isoformat(),
                status=scenario.status,
                metadata=scenario.metadata_json,
                context=context,
                input_validation=_build_input_validation(db, scenario, context),
                latest_result_created_at=result.created_at.isoformat() if result else None,
                production_summary=result.production_summary_json if result else None,
            )
        )
    return items


@router.post("", response_model=ScenarioModelResponse)
def create_scenario(payload: ScenarioUpsertRequest, db: Session = Depends(get_db)) -> ScenarioModelResponse:
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Имя сценария обязательно.")
    context = _build_context_from_request(db, bindings=payload.inputs, existing_context=None)
    metadata = _merge_metadata(existing_metadata=None, context=context, patch_metadata=payload.metadata)
    scenario = ScenarioRepository(db).create_scenario(
        name=payload.name.strip(),
        source_type=payload.source_type,
        parent_scenario_id=payload.parent_scenario_id,
        forecast_start_date=payload.forecast_start_date,
        forecast_end_date=payload.forecast_end_date,
        metadata=metadata,
        status="draft",
    )
    return _scenario_response(scenario)


@router.put("/{scenario_id}", response_model=ScenarioModelResponse)
def update_scenario(scenario_id: str, payload: ScenarioUpsertRequest, db: Session = Depends(get_db)) -> ScenarioModelResponse:
    repo = ScenarioRepository(db)
    scenario = repo.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Имя сценария обязательно.")
    context = _build_context_from_request(db, bindings=payload.inputs, existing_context=_extract_context(scenario.metadata_json))
    metadata = _merge_metadata(existing_metadata=scenario.metadata_json, context=context, patch_metadata=payload.metadata)
    updated = repo.update_scenario(
        scenario_id,
        name=payload.name.strip(),
        source_type=payload.source_type,
        forecast_start_date=payload.forecast_start_date,
        forecast_end_date=payload.forecast_end_date,
        metadata=metadata,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")
    return _scenario_response(updated)


@router.get("/{scenario_id}", response_model=ScenarioDetailResponse)
def get_scenario(scenario_id: str, db: Session = Depends(get_db)) -> ScenarioDetailResponse:
    resolved = ScenarioRepository(db).get_scenario_with_latest_result(scenario_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Сценарий не найден.")
    return _scenario_detail_payload(db, *resolved)


@router.post("/{scenario_id}/calculate", response_model=ScenarioDetailResponse)
def calculate_scenario(scenario_id: str, db: Session = Depends(get_db)) -> ScenarioDetailResponse:
    return _calculate_for_scenario(db, scenario_id=scenario_id)


@router.post("/{scenario_id}/from-planner-revision", response_model=ScenarioDetailResponse)
def create_scenario_from_planner_revision(
    scenario_id: str,
    payload: ScenarioRecalculateFromRevisionRequest,
    db: Session = Depends(get_db),
) -> ScenarioDetailResponse:
    repo = ScenarioRepository(db)
    parent = repo.get_scenario(scenario_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Родительский сценарий не найден.")

    revision = PlannerRevisionRepository(db).get(payload.revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Planner revision не найден.")
    if revision.parent_scenario_id != scenario_id:
        raise HTTPException(status_code=400, detail="Planner revision не принадлежит активному сценарию.")

    parent_context = _extract_context(parent.metadata_json)
    child_metadata = _merge_metadata(
        existing_metadata=parent.metadata_json,
        context=parent_context,
        patch_metadata={
            **(payload.metadata or {}),
            "scenario_source_mode": "planner",
            "planner_revision_id": revision.revision_id,
            "planner_version_id": revision.planner_version_id,
            "planner_version_name": revision.version_name,
        },
    )
    child = repo.create_scenario(
        name=payload.name or f"{parent.name} / {revision.version_name}",
        source_type="planner_manual_edit",
        parent_scenario_id=parent.scenario_id,
        forecast_start_date=parent.forecast_start_date,
        forecast_end_date=parent.forecast_end_date,
        metadata=child_metadata,
        status="draft",
    )
    return _calculate_for_scenario(db, scenario_id=child.scenario_id, planner_revision_items=revision.items_json)
