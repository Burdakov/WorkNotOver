from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.scenarios import _calculate_for_scenario, _extract_context, _merge_metadata
from app.db.session import SessionLocal
from app.repositories.planner_revision_repository import PlannerRevisionRepository
from app.repositories.scenario_repository import ScenarioRepository
from app.schemas.schedule_models import (
    PlannerRevisionCreateRequest,
    PlannerRevisionPublishRequest,
    PlannerRevisionPublishResponse,
    PlannerRevisionResponse,
    ScheduleItem,
)

router = APIRouter(prefix="/api/planner", tags=["planner"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _response_from_model(model) -> PlannerRevisionResponse:
    return PlannerRevisionResponse(
        revision_id=model.revision_id,
        parent_scenario_id=model.parent_scenario_id,
        version_name=model.version_name,
        planner_version_id=model.planner_version_id,
        edited_at=model.edited_at.isoformat(),
        editor=model.editor,
        item_count=len(model.items_json or []),
        metadata=model.metadata_json,
        items=[ScheduleItem(**item) for item in (model.items_json or [])],
    )


@router.post("/revisions", response_model=PlannerRevisionResponse)
def create_planner_revision(payload: PlannerRevisionCreateRequest, db: Session = Depends(get_db)) -> PlannerRevisionResponse:
    revision = PlannerRevisionRepository(db).create(
        parent_scenario_id=payload.parent_scenario_id,
        version_name=payload.version_name,
        items=[item.model_dump() for item in payload.items],
        planner_version_id=payload.planner_version_id,
        editor=payload.editor,
        metadata=payload.metadata,
    )
    return _response_from_model(revision)


@router.post("/revisions/publish", response_model=PlannerRevisionPublishResponse)
def publish_planner_revision(payload: PlannerRevisionPublishRequest, db: Session = Depends(get_db)) -> PlannerRevisionPublishResponse:
    parent = ScenarioRepository(db).get_scenario(payload.parent_scenario_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Родительский сценарий не найден.")

    revision = PlannerRevisionRepository(db).create(
        parent_scenario_id=payload.parent_scenario_id,
        version_name=payload.version_name,
        items=[item.model_dump() for item in payload.items],
        planner_version_id=payload.planner_version_id,
        editor=payload.editor,
        metadata=payload.metadata,
    )

    parent_context = _extract_context(parent.metadata_json)
    child_metadata = _merge_metadata(
        existing_metadata=parent.metadata_json,
        context=parent_context,
        patch_metadata={
            **(payload.scenario_metadata or {}),
            "scenario_source_mode": "planner",
            "planner_revision_id": revision.revision_id,
            "planner_version_id": revision.planner_version_id,
            "planner_version_name": revision.version_name,
        },
    )
    child = ScenarioRepository(db).create_scenario(
        name=payload.scenario_name.strip() if payload.scenario_name and payload.scenario_name.strip() else f"{parent.name} / {revision.version_name}",
        source_type="planner_manual_edit",
        parent_scenario_id=parent.scenario_id,
        forecast_start_date=parent.forecast_start_date,
        forecast_end_date=parent.forecast_end_date,
        metadata=child_metadata,
        status="draft",
    )
    scenario = _calculate_for_scenario(db, scenario_id=child.scenario_id, planner_revision_items=revision.items_json)

    return PlannerRevisionPublishResponse(
        revision=_response_from_model(revision),
        scenario=scenario,
    )


@router.get("/revisions", response_model=list[PlannerRevisionResponse])
def list_planner_revisions(parent_scenario_id: str, db: Session = Depends(get_db)) -> list[PlannerRevisionResponse]:
    revisions = PlannerRevisionRepository(db).list_for_scenario(parent_scenario_id)
    return [_response_from_model(revision) for revision in revisions]


@router.get("/revisions/{revision_id}", response_model=PlannerRevisionResponse)
def get_planner_revision(revision_id: str, db: Session = Depends(get_db)) -> PlannerRevisionResponse:
    revision = PlannerRevisionRepository(db).get(revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Planner revision не найден.")
    return _response_from_model(revision)
