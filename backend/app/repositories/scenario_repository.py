from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScenarioModel, ScenarioResultModel


class ScenarioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_scenario(
        self,
        *,
        name: str,
        source_type: str,
        parent_scenario_id: str | None,
        forecast_start_date: str | None,
        forecast_end_date: str | None,
        metadata: dict[str, Any] | None,
        status: str = "draft",
    ) -> ScenarioModel:
        scenario = ScenarioModel(
            name=name,
            source_type=source_type,
            parent_scenario_id=parent_scenario_id,
            forecast_start_date=forecast_start_date,
            forecast_end_date=forecast_end_date,
            status=status,
            metadata_json=metadata,
        )
        self.session.add(scenario)
        self.session.commit()
        self.session.refresh(scenario)
        return scenario

    def update_scenario(
        self,
        scenario_id: str,
        *,
        name: str | None = None,
        source_type: str | None = None,
        forecast_start_date: str | None = None,
        forecast_end_date: str | None = None,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> ScenarioModel | None:
        scenario = self.session.get(ScenarioModel, scenario_id)
        if scenario is None:
            return None

        if name is not None:
            scenario.name = name
        if source_type is not None:
            scenario.source_type = source_type
        if forecast_start_date is not None:
            scenario.forecast_start_date = forecast_start_date
        if forecast_end_date is not None:
            scenario.forecast_end_date = forecast_end_date
        if metadata is not None:
            scenario.metadata_json = metadata
        if status is not None:
            scenario.status = status

        self.session.commit()
        self.session.refresh(scenario)
        return scenario

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
        scenario = self.create_scenario(
            name=name,
            source_type=source_type,
            parent_scenario_id=parent_scenario_id,
            forecast_start_date=forecast_start_date,
            forecast_end_date=forecast_end_date,
            metadata=metadata,
            status="calculated",
        )
        result = self.attach_result(
            scenario_id=scenario.scenario_id,
            production_summary=production_summary,
            production_points=production_points,
            well_results=well_results,
            source_payload=source_payload,
            metadata=metadata,
        )
        return scenario, result

    def attach_result(
        self,
        *,
        scenario_id: str,
        production_summary: dict[str, Any],
        production_points: list[dict[str, Any]],
        well_results: list[dict[str, Any]],
        source_payload: dict[str, Any],
        metadata: dict[str, Any] | None,
    ) -> ScenarioResultModel:
        scenario = self.session.get(ScenarioModel, scenario_id)
        if scenario is None:
            raise ValueError(f"Scenario '{scenario_id}' not found.")

        result = ScenarioResultModel(
            scenario_id=scenario_id,
            production_summary_json=production_summary,
            production_points_json=production_points,
            well_results_json=well_results,
            source_payload_json=source_payload,
            metadata_json=metadata,
        )
        scenario.status = "calculated"
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        self.session.refresh(scenario)
        return result

    def get_scenario(self, scenario_id: str) -> ScenarioModel | None:
        return self.session.get(ScenarioModel, scenario_id)

    def find_child_scenario(
        self,
        *,
        parent_scenario_id: str,
        name: str | None = None,
        metadata_key: str | None = None,
        metadata_value: Any | None = None,
    ) -> ScenarioModel | None:
        stmt = (
            select(ScenarioModel)
            .where(ScenarioModel.parent_scenario_id == parent_scenario_id)
            .order_by(ScenarioModel.created_at.desc())
        )
        for scenario in self.session.scalars(stmt):
            if name is not None and scenario.name != name:
                continue
            if metadata_key is not None:
                metadata = scenario.metadata_json or {}
                if metadata.get(metadata_key) != metadata_value:
                    continue
            return scenario
        return None

    def get_latest_result(self, scenario_id: str) -> tuple[ScenarioModel, ScenarioResultModel] | None:
        scenario = self.get_scenario(scenario_id)
        if scenario is None:
            return None
        result = self._latest_result_for_scenario(scenario_id)
        if result is None:
            return None
        return scenario, result

    def get_scenario_with_latest_result(self, scenario_id: str) -> tuple[ScenarioModel, ScenarioResultModel | None] | None:
        scenario = self.get_scenario(scenario_id)
        if scenario is None:
            return None
        return scenario, self._latest_result_for_scenario(scenario_id)

    def list_scenarios(self) -> list[tuple[ScenarioModel, ScenarioResultModel | None]]:
        stmt = select(ScenarioModel).order_by(ScenarioModel.created_at.desc())
        scenarios = list(self.session.scalars(stmt))
        return [(scenario, self._latest_result_for_scenario(scenario.scenario_id)) for scenario in scenarios]

    def _latest_result_for_scenario(self, scenario_id: str) -> ScenarioResultModel | None:
        stmt = (
            select(ScenarioResultModel)
            .where(ScenarioResultModel.scenario_id == scenario_id)
            .order_by(ScenarioResultModel.created_at.desc())
        )
        return self.session.scalars(stmt).first()
