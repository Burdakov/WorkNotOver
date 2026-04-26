from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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


def _normalize_watercut(value: float) -> float:
    if value > 1:
        return max(0.0, min(1.0, value / 100.0))
    return max(0.0, min(1.0, value))


def _annual_percent_to_daily_factor(annual_percent: float) -> float:
    bounded = max(0.0, min(99.999999, annual_percent))
    return 1 - (1 - bounded / 100.0) ** (1 / 365.0)


def _find_curve_point_watercut(curve_points: list[dict[str, Any]], normalized_niz: float) -> float:
    if not curve_points:
        return 0.0
    ordered = sorted(
        (
            {
                "NIZ": _coerce_float(point.get("NIZ")),
                "watercut": _normalize_watercut(_coerce_float(point.get("watercut"))),
            }
            for point in curve_points
        ),
        key=lambda item: item["NIZ"],
    )
    x = max(ordered[0]["NIZ"], min(ordered[-1]["NIZ"], normalized_niz))
    for left, right in zip(ordered, ordered[1:]):
        if left["NIZ"] <= x <= right["NIZ"]:
            span = right["NIZ"] - left["NIZ"]
            if span == 0:
                return left["watercut"]
            ratio = (x - left["NIZ"]) / span
            return left["watercut"] + (right["watercut"] - left["watercut"]) * ratio
    return ordered[-1]["watercut"]


def _invert_curve_for_niz(curve_points: list[dict[str, Any]], watercut: float) -> float | None:
    if not curve_points:
        return None
    target = _normalize_watercut(watercut)
    ordered = sorted(
        (
            {
                "NIZ": _coerce_float(point.get("NIZ")),
                "watercut": _normalize_watercut(_coerce_float(point.get("watercut"))),
            }
            for point in curve_points
        ),
        key=lambda item: item["watercut"],
    )
    y = max(ordered[0]["watercut"], min(ordered[-1]["watercut"], target))
    for left, right in zip(ordered, ordered[1:]):
        if left["watercut"] <= y <= right["watercut"]:
            span = right["watercut"] - left["watercut"]
            if span == 0:
                return left["NIZ"]
            ratio = (y - left["watercut"]) / span
            return left["NIZ"] + (right["NIZ"] - left["NIZ"]) * ratio
    return ordered[-1]["NIZ"]


def _select_decline_percent(
    series: list[dict[str, Any]],
    current_day: date,
    anchor_day: date,
) -> float:
    if not series:
        return 0.0
    month_index = ((current_day.year - anchor_day.year) * 12) + (current_day.month - anchor_day.month) + 1
    lookup = {
        int(_coerce_float(item.get("month_index"), default=0)): _coerce_float(item.get("liquid_decline_factor"))
        for item in series
        if _coerce_float(item.get("month_index"), default=0) > 0
    }
    if not lookup:
        return 0.0
    if month_index in lookup:
        return lookup[month_index]
    max_key = max(lookup)
    return lookup[max_key] if month_index > max_key else lookup[min(lookup)]


@dataclass
class ForecastContext:
    start_day: date
    end_day: date
    curve_points: list[dict[str, Any]]
    base_decline: list[dict[str, Any]]
    new_wells_decline: list[dict[str, Any]]
    warnings: list[str]


class ForecastService:
    def __init__(
        self,
        *,
        wells_reference: DatasetReference,
        wells_payload: list[dict[str, Any]],
        gtm_reference: DatasetReference,
        gtm_payload: list[dict[str, Any]],
        manual_input_reference: ManualInputReference,
        manual_input_payload: dict[str, Any],
    ) -> None:
        self.wells_reference = wells_reference
        self.wells_payload = wells_payload
        self.gtm_reference = gtm_reference
        self.gtm_payload = gtm_payload
        self.manual_input_reference = manual_input_reference
        self.manual_input_payload = manual_input_payload

    def calculate(self, payload: ForecastCalculateRequest) -> ForecastCalculateResponse:
        start_day = _parse_iso_date(payload.forecast_start_date) or date.today()
        end_day = _parse_iso_date(payload.forecast_end_date) or _default_forecast_end(start_day)
        warnings: list[str] = []

        displacement_config = self.manual_input_payload.get("displacement_config") or {}
        decline_config = self.manual_input_payload.get("decline_config") or {}
        curve_points = list(displacement_config.get("curve_points") or [])
        base_decline = list(decline_config.get("base_monthly_decline_values") or [])
        new_wells_decline = list(decline_config.get("new_wells_monthly_decline_values") or [])

        if not curve_points:
            warnings.append("Не задана характеристика вытеснения; обводненность будет считаться как 0.")
        if not base_decline:
            warnings.append("Не задан ряд снижения жидкости для Base; будет использовано нулевое падение.")
        if not new_wells_decline:
            warnings.append("Не задан ряд снижения жидкости для New wells; будет использовано нулевое падение.")

        context = ForecastContext(
            start_day=start_day,
            end_day=end_day,
            curve_points=curve_points,
            base_decline=base_decline,
            new_wells_decline=new_wells_decline,
            warnings=warnings,
        )

        events_by_well: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in self.gtm_payload:
            well_key = str(event.get("well_name") or event.get("well_id") or "").strip()
            if well_key:
                events_by_well[well_key].append(event)
        for event_list in events_by_well.values():
            event_list.sort(key=lambda item: item.get("candidate_start_date") or "")

        daily_aggregate: dict[str, dict[str, float]] = {}
        well_results: list[WellForecastResult] = []

        for well in self.wells_payload:
            result = self._calculate_well(well, events_by_well.get(str(well.get("well_name") or "").strip(), []), context)
            well_results.append(result)
            for point in result.points:
                bucket = daily_aggregate.setdefault(
                    point.date,
                    {
                        "oil_rate": 0.0,
                        "liquid_rate": 0.0,
                        "gas_rate": 0.0,
                        "watercut_weighted": 0.0,
                        "gor_weighted": 0.0,
                        "liquid_increment": 0.0,
                        "oil_increment": 0.0,
                        "gas_increment": 0.0,
                    },
                )
                bucket["oil_rate"] += point.oil_rate
                bucket["liquid_rate"] += point.liquid_rate
                bucket["gas_rate"] += point.gas_rate
                bucket["liquid_increment"] += point.liquid_increment
                bucket["oil_increment"] += point.oil_increment
                bucket["gas_increment"] += point.gas_increment
                bucket["watercut_weighted"] += point.watercut * point.liquid_rate
                bucket["gor_weighted"] += point.gor * point.oil_rate

        production_points: list[ProductionPoint] = []
        total_oil = total_liquid = total_gas = 0.0
        peak_oil = peak_liquid = peak_gas = 0.0
        gor_sum = 0.0
        gor_count = 0

        for current_day in _daterange(start_day, end_day):
            bucket = daily_aggregate.get(_iso(current_day), {})
            liquid_rate = float(bucket.get("liquid_rate", 0.0))
            oil_rate = float(bucket.get("oil_rate", 0.0))
            gas_rate = float(bucket.get("gas_rate", 0.0))
            watercut = (bucket.get("watercut_weighted", 0.0) / liquid_rate) if liquid_rate > 0 else 0.0
            gor = (bucket.get("gor_weighted", 0.0) / oil_rate) if oil_rate > 0 else 0.0
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
                gor_count += 1

        summary = ScenarioProductionSummary(
            total_oil=round(total_oil, 6),
            total_liquid=round(total_liquid, 6),
            total_gas=round(total_gas, 6),
            peak_oil_rate=round(peak_oil, 6),
            peak_liquid_rate=round(peak_liquid, 6),
            peak_gas_rate=round(peak_gas, 6),
            average_gor=round(gor_sum / gor_count, 6) if gor_count else 0.0,
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
            gtm_dataset=self.gtm_reference,
            manual_input_set=self.manual_input_reference,
            production_summary=summary,
            production_points=production_points,
            wells=well_results,
            warnings=warnings,
        )

    def _calculate_well(
        self,
        well: dict[str, Any],
        events: list[dict[str, Any]],
        context: ForecastContext,
    ) -> WellForecastResult:
        well_id = str(well.get("well_id") or "")
        well_name = str(well.get("well_name") or well_id)
        fund_type = str(well.get("fund_type") or "Base")
        current_liquid = _coerce_float(well.get("current_liquid_rate"))
        current_oil = _coerce_float(well.get("current_oil_rate"))
        current_gas = _coerce_float(well.get("current_gas_rate"))
        current_gor = _coerce_float(well.get("current_gor"))
        niz = _coerce_float(well.get("niz"))
        cumulative_oil = _coerce_float(well.get("current_cumulative_oil"))
        current_watercut = _coerce_float(well.get("current_watercut"))

        if current_gor <= 0 and current_oil > 0 and current_gas > 0:
            current_gor = current_gas / current_oil

        normalized_remaining_niz = None
        if current_watercut > 0 and context.curve_points:
            normalized_remaining_niz = _invert_curve_for_niz(context.curve_points, current_watercut)
        if normalized_remaining_niz is None and niz > 0:
            normalized_remaining_niz = max(0.0, min(1.0, (niz - cumulative_oil) / niz))
        if normalized_remaining_niz is None:
            normalized_remaining_niz = 1.0

        watercut = _find_curve_point_watercut(context.curve_points, normalized_remaining_niz) if context.curve_points else _normalize_watercut(current_watercut)
        if current_oil <= 0 and current_liquid > 0:
            current_oil = current_liquid * (1 - watercut)
        if current_gor <= 0 and current_oil > 0 and current_gas > 0:
            current_gor = current_gas / current_oil

        event_index = 0
        active_liquid = current_liquid if fund_type == "Base" else 0.0
        active_gor = current_gor
        active_gas_direct = current_gas if fund_type == "Base" else 0.0
        anchor_day = context.start_day

        points: list[ProductionPoint] = []
        total_oil = total_liquid = total_gas = 0.0

        for current_day in _daterange(context.start_day, context.end_day):
            day_liquid_increment = 0.0
            day_oil_increment = 0.0
            day_gas_increment = 0.0

            while event_index < len(events):
                event_day = _parse_iso_date(events[event_index].get("candidate_start_date"))
                if event_day is None or event_day != current_day:
                    break
                expected_liquid_increment = _coerce_float(events[event_index].get("expected_liquid_increment"))
                expected_gas_increment = _coerce_float(events[event_index].get("expected_gas_increment"))
                expected_gor_change = _coerce_float(events[event_index].get("expected_gor_change"))
                active_liquid += expected_liquid_increment
                active_gas_direct += expected_gas_increment
                active_gor += expected_gor_change
                if fund_type == "New wells" and anchor_day == context.start_day and current_day >= context.start_day:
                    anchor_day = current_day
                day_liquid_increment += expected_liquid_increment
                day_gas_increment += expected_gas_increment
                event_index += 1

            decline_series = context.base_decline if fund_type == "Base" else context.new_wells_decline
            annual_decline_percent = _select_decline_percent(decline_series, current_day, anchor_day)
            daily_factor = _annual_percent_to_daily_factor(annual_decline_percent)
            if current_day > anchor_day or fund_type == "Base":
                active_liquid *= 1 - daily_factor

            if niz > 0:
                normalized_remaining_niz = max(0.0, normalized_remaining_niz - (max(active_liquid * (1 - watercut), 0.0) / max(niz, 1e-9)))
                normalized_remaining_niz = max(0.0, min(1.0, normalized_remaining_niz))
            watercut = _find_curve_point_watercut(context.curve_points, normalized_remaining_niz) if context.curve_points else watercut
            oil_rate = max(active_liquid * (1 - watercut), 0.0)
            gas_rate = max(active_gas_direct, 0.0)
            if active_gor > 0 and oil_rate > 0:
                gas_rate = max(gas_rate, oil_rate * active_gor)
            gor = (gas_rate / oil_rate) if oil_rate > 0 else active_gor
            day_oil_increment = max(day_liquid_increment * (1 - watercut), 0.0)

            point = ProductionPoint(
                date=_iso(current_day),
                oil_rate=round(oil_rate, 6),
                liquid_rate=round(max(active_liquid, 0.0), 6),
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
            cumulative_oil += point.oil_rate

        return WellForecastResult(
            well_id=well_id,
            well_name=well_name,
            fund_type=fund_type,
            lu_id=well.get("lu_id"),
            sloy_id=well.get("sloy_id"),
            points=points,
            total_oil=round(total_oil, 6),
            total_liquid=round(total_liquid, 6),
            total_gas=round(total_gas, 6),
        )
