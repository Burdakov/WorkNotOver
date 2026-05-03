from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PlannerScheduleRevisionModel


class PlannerRevisionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        parent_scenario_id: str,
        version_name: str,
        items: list[dict[str, Any]],
        planner_version_id: str | None = None,
        editor: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PlannerScheduleRevisionModel:
        revision = PlannerScheduleRevisionModel(
            parent_scenario_id=parent_scenario_id,
            planner_version_id=planner_version_id,
            version_name=version_name,
            editor=editor,
            items_json=items,
            metadata_json=metadata,
        )
        self.session.add(revision)
        self.session.commit()
        self.session.refresh(revision)
        return revision

    def get(self, revision_id: str) -> PlannerScheduleRevisionModel | None:
        return self.session.get(PlannerScheduleRevisionModel, revision_id)

    def list_for_scenario(self, parent_scenario_id: str) -> list[PlannerScheduleRevisionModel]:
        stmt = (
            select(PlannerScheduleRevisionModel)
            .where(PlannerScheduleRevisionModel.parent_scenario_id == parent_scenario_id)
            .order_by(PlannerScheduleRevisionModel.edited_at.desc())
        )
        return list(self.session.scalars(stmt))
