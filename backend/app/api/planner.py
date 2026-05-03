from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.planner_revision_repository import PlannerRevisionRepository
from app.schemas.schedule_models import PlannerRevisionCreateRequest, PlannerRevisionResponse, ScheduleItem

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


@router.get("/revisions/{revision_id}", response_model=PlannerRevisionResponse)
def get_planner_revision(revision_id: str, db: Session = Depends(get_db)) -> PlannerRevisionResponse:
    revision = PlannerRevisionRepository(db).get(revision_id)
    if revision is None:
        raise HTTPException(status_code=404, detail="Planner revision не найден.")
    return _response_from_model(revision)
