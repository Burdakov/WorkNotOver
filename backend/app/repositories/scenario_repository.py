from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScenarioModel, ScenarioResultModel


class ScenarioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_scenario_with_result(
        self,
        *,
        name: str,
        source_type: str,
        parent_scenario_id: str | None,
        forecast_start_date: str | None,
        forecast_end_date: str | None,
        metadata: dict[str, Any] | None,
        production_summary: dict[str, Any],
        production_points: list[dict[str, Any]],
        well_results: list[dict[str, Any]],
        source_payload: dict[str, Any],
    ) -> tuple[ScenarioModel, ScenarioResultModel]:
        scenario = ScenarioModel(
            name=name,
            source_type=source_type,
            parent_scenario_id=parent_scenario_id,
            forecast_start_date=forecast_start_date,
            forecast_end_date=forecast_end_date,
            status="calculated",
            metadata_json=metadata,
        )
        self.session.add(scenario)
        self.session.flush()

        result = ScenarioResultModel(
            scenario_id=scenario.scenario_id,
            production_summary_json=production_summary,
            production_points_json=production_points,
            well_results_json=well_results,
            source_payload_json=source_payload,
            metadata_json=metadata,
        )
        self.session.add(result)
        self.session.commit()
        self.session.refresh(scenario)
        self.session.refresh(result)
        return scenario, result

    def get_latest_result(self, scenario_id: str) -> tuple[ScenarioModel, ScenarioResultModel] | None:
        scenario = self.session.get(ScenarioModel, scenario_id)
        if scenario is None:
            return None
        stmt = (
            select(ScenarioResultModel)
            .where(ScenarioResultModel.scenario_id == scenario_id)
            .order_by(ScenarioResultModel.created_at.desc())
        )
        result = self.session.scalars(stmt).first()
        if result is None:
            return None
        return scenario, result

    def list_scenarios(self) -> list[tuple[ScenarioModel, ScenarioResultModel | None]]:
        stmt = select(ScenarioModel).order_by(ScenarioModel.created_at.desc())
        scenarios = list(self.session.scalars(stmt))
        result: list[tuple[ScenarioModel, ScenarioResultModel | None]] = []
        for scenario in scenarios:
            result.append((scenario, self._latest_result_for_scenario(scenario.scenario_id)))
        return result

    def _latest_result_for_scenario(self, scenario_id: str) -> ScenarioResultModel | None:
        stmt = (
            select(ScenarioResultModel)
            .where(ScenarioResultModel.scenario_id == scenario_id)
            .order_by(ScenarioResultModel.created_at.desc())
        )
        return self.session.scalars(stmt).first()
