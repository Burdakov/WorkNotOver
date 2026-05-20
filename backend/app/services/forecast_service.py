from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.schemas.common import DatasetReference, ManualInputReference
from app.schemas.forecast_models import (
    ForecastCalculateRequest,
    ForecastCalculateResponse,
    ProductionPoint,
    ScenarioModelResponse,
    ScenarioProductionSummary,
    WellForecastResult,
)


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _iso(value: date) -> str:
    return value.isoformat()


def _default_forecast_end(start_day: date) -> date:
    return date(start_day.year + 1, 12, 31)


def _daterange(start_day: date, end_day: date) -> list[date]:
    current = start_day
    result: list[date] = []
    while current <= end_day:
        result.append(current)
        current += timedelta(days=1)
    return result


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _well_key(payload: dict[str, Any]) -> str:
    well_id = str(payload.get("well_id") or "").strip()
    if well_id:
        return well_id
    return str(payload.get("well_name") or "").strip()


def _normalize_watercut(value: float) -> float:
    if value > 1:
        value = value / 100.0
    return max(0.0, min(1.0, value))


def _annual_percent_to_daily_factor(annual_percent: float) -> float:
    bounded = max(0.0, min(99.999999, annual_percent))
    return 1 - (1 - bounded / 100.0) ** (1 / 365.0)


def _sort_curve_points(curve_points: list[dict[str, Any]]) -> list[dict[str, float]]:
    return sorted(
        [
            {
                "NIZ": _coerce_float(point.get("NIZ")),
                "watercut": _normalize_watercut(_coerce_float(point.get("watercut"))),
            }
            for point in curve_points
        ],
        key=lambda item: item["NIZ"],
    )


def _watercut_from_curve(curve_points: list[dict[str, Any]], remaining_share: float) -> float:
    ordered = _sort_curve_points(curve_points)
    if not ordered:
        return 0.0

    x = max(ordered[0]["NIZ"], min(ordered[-1]["NIZ"], remaining_share))
    for left, right in zip(ordered, ordered[1:]):
        if left["NIZ"] <= x <= right["NIZ"]:
            span = right["NIZ"] - left["NIZ"]
            if span == 0:
                return left["watercut"]
            ratio = (x - left["NIZ"]) / span
            return left["watercut"] + (right["watercut"] - left["watercut"]) * ratio
    return ordered[-1]["watercut"]


def _remaining_share_from_watercut(curve_points: list[dict[str, Any]], watercut: float) -> float | None:
    ordered = sorted(_sort_curve_points(curve_points), key=lambda item: item["watercut"])
    if not ordered:
        return None

    target = _normalize_watercut(watercut)
    y = max(ordered[0]["watercut"], min(ordered[-1]["watercut"], target))
    for left, right in zip(ordered, ordered[1:]):
        if left["watercut"] <= y <= right["watercut"]:
            span = right["watercut"] - left["watercut"]
            if span == 0:
                return left["NIZ"]
            ratio = (y - left["watercut"]) / span
            return left["NIZ"] + (right["NIZ"] - left["NIZ"]) * ratio
    return ordered[-1]["NIZ"]


def _month_index(current_day: date, anchor_day: date) -> int:
    return ((current_day.year - anchor_day.year) * 12) + (current_day.month - anchor_day.month) + 1


def _decline_percent(series: list[dict[str, Any]], current_day: date, anchor_day: date) -> float:
    if not series:
        return 0.0

    lookup = {
        int(_coerce_float(item.get("month_index"), 0)): _coerce_float(item.get("liquid_decline_factor"))
        for item in series
        if int(_coerce_float(item.get("month_index"), 0)) > 0
    }
    if not lookup:
        return 0.0

    current_month_index = _month_index(current_day, anchor_day)
    if current_month_index in lookup:
        return lookup[current_month_index]

    max_key = max(lookup)
    if current_month_index > max_key:
        return lookup[max_key]
    return lookup[min(lookup)]


def _scope_rank(config: dict[str, Any], lu_id: str | None, sloy_id: str | None) -> int:
    config_lu = config.get("lu_id")
    config_sloy = config.get("sloy_id")

    if config_sloy:
        if config_sloy == sloy_id and (not config_lu or config_lu == lu_id):
            return 3
        return 0
    if config_lu:
        return 2 if config_lu == lu_id else 0
    return 1


def _select_scoped_config(configs: list[dict[str, Any]], lu_id: str | None, sloy_id: str | None) -> dict[str, Any] | None:
    best_config: dict[str, Any] | None = None
    best_rank = -1
    for config in configs:
        rank = _scope_rank(config, lu_id, sloy_id)
        if rank > best_rank:
            best_rank = rank
            best_config = config
    return best_config if best_rank > 0 else None


@dataclass
class ForecastContext:
    start_day: date
    end_day: date
    displacement_configs: list[dict[str, Any]]
    decline_configs: list[dict[str, Any]]
    warnings: list[str]


class ForecastService:
    def __init__(
        self,
        *,
        wells_reference: DatasetReference,
        wells_payload: list[dict[str, Any]],
        niz_reference: DatasetReference,
        gtm_reference: DatasetReference,
        gtm_payload: list[dict[str, Any]],
        manual_input_reference: ManualInputReference,
        manual_input_payload: dict[str, Any],
        planner_revision_items: list[dict[str, Any]] | None = None,
    ) -> None:
        self.wells_reference = wells_reference
        self.wells_payload = wells_payload
        self.niz_reference = niz_reference
        self.gtm_reference = gtm_reference
        self.gtm_payload = gtm_payload
        self.manual_input_reference = manual_input_reference
        self.manual_input_payload = manual_input_payload
        self.planner_revision_items = planner_revision_items or []

    def calculate(self, payload: ForecastCalculateRequest) -> ForecastCalculateResponse:
        start_day = _parse_iso_date(payload.forecast_start_date) or date.today()
        end_day = _parse_iso_date(payload.forecast_end_date) or _default_forecast_end(start_day)
        warnings: list[str] = []

        displacement_configs = self._extract_config_list("displacement_configs", "displacement_config")
        decline_configs = self._extract_config_list("decline_configs", "decline_config")

        if not displacement_configs:
            warnings.append("Не задана характеристика вытеснения. Обводненность будет взята из фактической, если она есть.")
        if not decline_configs:
            warnings.append("Не задан DeclineConfig. Снижение жидкости будет равно нулю.")

        context = ForecastContext(
            start_day=start_day,
            end_day=end_day,
            displacement_configs=displacement_configs,
            decline_configs=decline_configs,
            warnings=warnings,
        )

        prepared_gtm_payload = self._apply_planner_revision(self.gtm_payload, self.planner_revision_items)
        prepared_wells_payload = self._build_forecast_wells(prepared_gtm_payload, warnings)

        events_by_well: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in prepared_gtm_payload:
            well_id = _well_key(event)
            if well_id:
                events_by_well[well_id].append(event)
        for event_list in events_by_well.values():
            event_list.sort(key=lambda item: str(item.get("candidate_start_date") or ""))

        daily_aggregate: dict[str, dict[str, float]] = {}
        well_results: list[WellForecastResult] = []

        for well in prepared_wells_payload:
            well_result = self._calculate_well(well, events_by_well.get(_well_key(well), []), context)
            well_results.append(well_result)
            for point in well_result.points:
                bucket = daily_aggregate.setdefault(
                    point.date,
                    {
                        "oil_rate": 0.0,
                        "liquid_rate": 0.0,
                        "gas_rate": 0.0,
                        "oil_increment": 0.0,
                        "liquid_increment": 0.0,
                        "gas_increment": 0.0,
                        "watercut_weighted": 0.0,
                        "gor_weighted": 0.0,
                    },
                )
                bucket["oil_rate"] += point.oil_rate
                bucket["liquid_rate"] += point.liquid_rate
                bucket["gas_rate"] += point.gas_rate
                bucket["oil_increment"] += point.oil_increment
                bucket["liquid_increment"] += point.liquid_increment
                bucket["gas_increment"] += point.gas_increment
                bucket["watercut_weighted"] += point.watercut * point.liquid_rate
                bucket["gor_weighted"] += point.gor * point.oil_rate

        production_points: list[ProductionPoint] = []
        total_oil = total_liquid = total_gas = 0.0
        peak_oil = peak_liquid = peak_gas = 0.0
        gor_sum = 0.0
        gor_weight_count = 0

        for current_day in _daterange(start_day, end_day):
            bucket = daily_aggregate.get(_iso(current_day), {})
            oil_rate = float(bucket.get("oil_rate", 0.0))
            liquid_rate = float(bucket.get("liquid_rate", 0.0))
            gas_rate = float(bucket.get("gas_rate", 0.0))
            watercut = bucket.get("watercut_weighted", 0.0) / liquid_rate if liquid_rate > 0 else 0.0
            gor = bucket.get("gor_weighted", 0.0) / oil_rate if oil_rate > 0 else 0.0

            point = ProductionPoint(
                date=_iso(current_day),
                oil_rate=round(oil_rate, 6),
                liquid_rate=round(liquid_rate, 6),
                gas_rate=round(gas_rate, 6),
                watercut=round(watercut, 6),
                gor=round(gor, 6),
                oil_increment=round(float(bucket.get("oil_increment", 0.0)), 6),
                liquid_increment=round(float(bucket.get("liquid_increment", 0.0)), 6),
                gas_increment=round(float(bucket.get("gas_increment", 0.0)), 6),
            )
            production_points.append(point)

            total_oil += point.oil_rate
            total_liquid += point.liquid_rate
            total_gas += point.gas_rate
            peak_oil = max(peak_oil, point.oil_rate)
            peak_liquid = max(peak_liquid, point.liquid_rate)
            peak_gas = max(peak_gas, point.gas_rate)
            if point.gor > 0:
                gor_sum += point.gor
                gor_weight_count += 1

        summary = ScenarioProductionSummary(
            total_oil=round(total_oil, 6),
            total_liquid=round(total_liquid, 6),
            total_gas=round(total_gas, 6),
            peak_oil_rate=round(peak_oil, 6),
            peak_liquid_rate=round(peak_liquid, 6),
            peak_gas_rate=round(peak_gas, 6),
            average_gor=round(gor_sum / gor_weight_count, 6) if gor_weight_count else 0.0,
            point_count=len(production_points),
        )

        return ForecastCalculateResponse(
            scenario=ScenarioModelResponse(
                scenario_id="",
                name=payload.name,
                source_type=payload.source_type,
                parent_scenario_id=payload.parent_scenario_id,
                forecast_start_date=_iso(start_day),
                forecast_end_date=_iso(end_day),
                created_at="",
                status="calculated",
                metadata=payload.metadata,
            ),
            wells_dataset=self.wells_reference,
            niz_dataset=self.niz_reference,
            gtm_dataset=self.gtm_reference,
            manual_input_set=self.manual_input_reference,
            production_summary=summary,
            production_points=production_points,
            wells=well_results,
            warnings=warnings,
        )

    def _apply_planner_revision(
        self,
        gtm_payload: list[dict[str, Any]],
        revision_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not revision_items:
            return [dict(item) for item in gtm_payload]

        revision_lookup: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in revision_items:
            well_name = str(item.get("well") or item.get("well_name") or "").strip()
            planned_work = str(item.get("planned_work") or "").strip()
            if well_name and planned_work:
                revision_lookup[(well_name, planned_work)].append(item)

        revised_events: list[dict[str, Any]] = []
        for event in gtm_payload:
            revised = dict(event)
            key = (str(event.get("well_name") or "").strip(), str(event.get("planned_work") or "").strip())
            planned_items = revision_lookup.get(key) or []
            if planned_items:
                planner_item = planned_items.pop(0)
                start_date = str(planner_item.get("start_date") or planner_item.get("planned_start_date") or "") or revised.get("candidate_start_date")
                end_date = str(planner_item.get("end_date") or planner_item.get("planned_end_date") or "") or revised.get("candidate_end_date")
                revised["candidate_start_date"] = start_date
                revised["candidate_end_date"] = end_date
                revised["duration_days"] = int(_coerce_float(planner_item.get("duration_days"), _coerce_float(revised.get("duration_days"))))
                revised.setdefault("metadata", {})
                if isinstance(revised["metadata"], dict):
                    revised["metadata"]["planner_revision_event_id"] = planner_item.get("event_id")
            revised_events.append(revised)
        return revised_events

    def _extract_config_list(self, plural_key: str, legacy_key: str) -> list[dict[str, Any]]:
        value = self.manual_input_payload.get(plural_key)
        if value is None:
            value = self.manual_input_payload.get(legacy_key)
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
        return []

    def _build_forecast_wells(
        self,
        gtm_payload: list[dict[str, Any]],
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        prepared_wells: list[dict[str, Any]] = []
        seen_keys: set[str] = set()

        for well in self.wells_payload:
            well_copy = dict(well)
            key = _well_key(well_copy)
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            prepared_wells.append(well_copy)

        synthesized_count = 0
        for event in gtm_payload:
            key = _well_key(event)
            if not key or key in seen_keys:
                continue

            seen_keys.add(key)
            synthesized_count += 1
            prepared_wells.append(
                {
                    "well_id": str(event.get("well_id") or key).strip(),
                    "well_name": str(event.get("well_name") or key).strip(),
                    "area": event.get("area"),
                    "lu_id": event.get("lu_id"),
                    "sloy_id": event.get("sloy_id"),
                    "well_pad_id": event.get("well_pad_id"),
                    "fund_type": "New wells",
                    "current_oil_rate": 0.0,
                    "current_liquid_rate": 0.0,
                    "current_gas_rate": 0.0,
                    "current_watercut": 0.0,
                    "current_gor": 0.0,
                    "current_cumulative_oil": _coerce_float(event.get("current_cumulative_oil")),
                    "current_cumulative_gas": _coerce_float(event.get("current_cumulative_gas")),
                    "niz": _coerce_float(event.get("niz")),
                    "metadata": {
                        "synthetic_well_state": True,
                        "synthetic_source": "gtm_only",
                    },
                }
            )

        if synthesized_count:
            warnings.append(
                f"В wells dataset отсутствовали {synthesized_count} скважин из GTM. "
                "Они были синтезированы как New wells для расчета Module B."
            )

        return prepared_wells

    def _calculate_well(
        self,
        well: dict[str, Any],
        events: list[dict[str, Any]],
        context: ForecastContext,
    ) -> WellForecastResult:
        well_id = _well_key(well)
        well_name = str(well.get("well_name") or well_id)
        fund_type = str(well.get("fund_type") or "Base")
        lu_id = well.get("lu_id")
        sloy_id = well.get("sloy_id")

        displacement_config = _select_scoped_config(context.displacement_configs, lu_id, sloy_id)
        decline_config = _select_scoped_config(context.decline_configs, lu_id, sloy_id)

        curve_points = list((displacement_config or {}).get("curve_points") or [])
        base_decline = list((decline_config or {}).get("base_monthly_decline_values") or [])
        new_wells_decline = list((decline_config or {}).get("new_wells_monthly_decline_values") or [])

        current_liquid = max(_coerce_float(well.get("current_liquid_rate")), 0.0)
        current_oil = max(_coerce_float(well.get("current_oil_rate")), 0.0)
        current_gas = max(_coerce_float(well.get("current_gas_rate")), 0.0)
        current_gor = max(_coerce_float(well.get("current_gor")), 0.0)
        current_watercut = _normalize_watercut(_coerce_float(well.get("current_watercut")))
        cumulative_oil = max(_coerce_float(well.get("current_cumulative_oil")), 0.0)
        niz = max(_coerce_float(well.get("niz")), 0.0)

        if current_gor <= 0 and current_oil > 0 and current_gas > 0:
            current_gor = current_gas / current_oil

        if curve_points and current_watercut > 0:
            remaining_share = _remaining_share_from_watercut(curve_points, current_watercut)
        elif niz > 0:
            remaining_share = max(0.0, min(1.0, (niz - cumulative_oil) / niz))
        else:
            remaining_share = 1.0
        if remaining_share is None:
            remaining_share = 1.0

        current_watercut = _watercut_from_curve(curve_points, remaining_share) if curve_points else current_watercut
        if current_oil <= 0 and current_liquid > 0:
            current_oil = current_liquid * (1 - current_watercut)
        if current_gor <= 0 and current_oil > 0 and current_gas > 0:
            current_gor = current_gas / current_oil

        active_liquid = current_liquid if fund_type == "Base" else 0.0
        active_gor = current_gor
        gas_floor = current_gas if fund_type == "Base" else 0.0
        decline_anchor = context.start_day
        startup_day: date | None = None

        events_by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            event_day = _parse_iso_date(event.get("candidate_start_date"))
            if event_day is not None:
                events_by_day[event_day].append(event)

        points: list[ProductionPoint] = []
        total_oil = total_liquid = total_gas = 0.0

        for current_day in _daterange(context.start_day, context.end_day):
            day_liquid_increment = 0.0
            day_gas_increment = 0.0

            if fund_type == "Base" and current_day > context.start_day and active_liquid > 0:
                annual_decline_percent = _decline_percent(base_decline, current_day, decline_anchor)
                active_liquid *= 1 - _annual_percent_to_daily_factor(annual_decline_percent)
            elif fund_type != "Base" and startup_day is not None and current_day > startup_day and active_liquid > 0:
                annual_decline_percent = _decline_percent(new_wells_decline, current_day, startup_day)
                active_liquid *= 1 - _annual_percent_to_daily_factor(annual_decline_percent)

            for event in events_by_day.get(current_day, []):
                expected_liquid_increment = _coerce_float(event.get("expected_liquid_increment"))
                expected_gas_increment = _coerce_float(event.get("expected_gas_increment"))
                expected_gor_change = _coerce_float(event.get("expected_gor_change"))

                active_liquid = max(active_liquid + expected_liquid_increment, 0.0)
                gas_floor = max(gas_floor + expected_gas_increment, 0.0)
                active_gor = max(active_gor + expected_gor_change, 0.0)
                day_liquid_increment += expected_liquid_increment
                day_gas_increment += expected_gas_increment

                if fund_type != "Base" and startup_day is None:
                    startup_day = current_day

            watercut = _watercut_from_curve(curve_points, remaining_share) if curve_points else current_watercut
            oil_rate = max(active_liquid * (1 - watercut), 0.0)
            gas_rate = gas_floor
            if active_gor > 0 and oil_rate > 0:
                gas_rate = max(gas_rate, oil_rate * active_gor)
            gor = gas_rate / oil_rate if oil_rate > 0 else active_gor

            day_oil_increment = max(day_liquid_increment * (1 - watercut), 0.0)

            point = ProductionPoint(
                date=_iso(current_day),
                oil_rate=round(oil_rate, 6),
                liquid_rate=round(active_liquid, 6),
                gas_rate=round(gas_rate, 6),
                watercut=round(watercut, 6),
                gor=round(gor, 6),
                oil_increment=round(day_oil_increment, 6),
                liquid_increment=round(day_liquid_increment, 6),
                gas_increment=round(day_gas_increment, 6),
            )
            points.append(point)

            total_oil += point.oil_rate
            total_liquid += point.liquid_rate
            total_gas += point.gas_rate

            if niz > 0:
                cumulative_oil += point.oil_rate
                remaining_share = max(0.0, min(1.0, (niz - cumulative_oil) / niz))

        return WellForecastResult(
            well_id=well_id,
            well_name=well_name,
            fund_type=fund_type,
            lu_id=lu_id,
            sloy_id=sloy_id,
            well_pad_id=well.get("well_pad_id"),
            points=points,
            total_oil=round(total_oil, 6),
            total_liquid=round(total_liquid, 6),
            total_gas=round(total_gas, 6),
        )
