from __future__ import annotations

from collections import defaultdict
from math import hypot
from typing import Any


INFLUENCE_RADIUS_M = 3000.0
DISTANCE_POWER = 2.0
LINK_TYPE_MULTIPLIERS = {
    "screen": 0.2,
    "normal": 1.0,
    "channel": 2.5,
    "unknown": 1.0,
}


def _round(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _delta(calc: float, actual: float) -> float:
    return _round(calc - actual)


class WaterfloodProxyService:
    """Small native waterflood proxy MVP used by Module G analysis UI.

    The implementation follows docs/forecast-module as a non-production mock:
    the first connectivity estimate is coordinate-based, then mock calibration
    adjusts alphas and pressure/watercut response deterministically.
    """

    def build_mock_analysis(self, *, scenario_id: str | None = None) -> dict[str, Any]:
        wells = self._mock_wells()
        producers = [item for item in wells if item["well_type"] == "producer"]
        injectors = [item for item in wells if item["well_type"] == "injector"]
        links = self._build_links(injectors, producers)
        calibrated_links = self._calibrate_links(links, producers)
        enriched_wells = self._enrich_wells(wells, calibrated_links)
        cells = self._build_cells(enriched_wells, calibrated_links)
        aggregates = self._build_aggregates(enriched_wells, cells)

        return {
            "scenario_id": scenario_id,
            "model": {
                "method": "waterflood_proxy_hm.mock_mvp",
                "mode": "synthetic_history_match",
                "influence_radius_m": INFLUENCE_RADIUS_M,
                "distance_power": DISTANCE_POWER,
                "coordinates": {
                    "crs": "EPSG:32640",
                    "x_unit": "m",
                    "y_unit": "m",
                    "allow_latlon": False,
                },
                "property_mode": "synthetic_explicit_tables_for_mock_only",
            },
            "calibration": {
                "status": "mock_calibrated",
                "iterations": 12,
                "objective_initial": 1.0,
                "objective_final": 0.318,
                "fit_window": "history_tail_12_months",
                "metrics": {
                    "watercut_mae": 0.026,
                    "pressure_mae_bar": 3.8,
                    "oil_rate_mape": 0.071,
                },
                "warnings": [
                    "MVP uses synthetic PVT/SCAL/ROCK only for mock analysis.",
                    "Production mode must load explicit PVT, SCAL and ROCK properties.",
                ],
            },
            "cells": cells,
            "wells": enriched_wells,
            "links": calibrated_links,
            "aggregates": aggregates,
        }

    def _mock_wells(self) -> list[dict[str, Any]]:
        return [
            {
                "well_id": "PROD_AZ_002",
                "well_name": "Az_002",
                "well_type": "producer",
                "lu_id": "Аянский (Западный)",
                "sloy_id": "S1",
                "well_pad_id": "20a",
                "cell_id": "CELL_A",
                "x": 1000.0,
                "y": 1100.0,
                "oil_rate_actual": 52.0,
                "liquid_rate_actual": 138.0,
                "gas_rate_actual": 9300.0,
                "watercut_actual": 0.623,
                "pressure_actual": 171.0,
                "reserves_initial": 560.0,
                "reserves_remaining": 344.0,
            },
            {
                "well_id": "PROD_AZ_216",
                "well_name": "Az_216",
                "well_type": "producer",
                "lu_id": "Аянский (Западный)",
                "sloy_id": "S1",
                "well_pad_id": "20a",
                "cell_id": "CELL_A",
                "x": 1850.0,
                "y": 1300.0,
                "oil_rate_actual": 61.0,
                "liquid_rate_actual": 151.0,
                "gas_rate_actual": 10800.0,
                "watercut_actual": 0.596,
                "pressure_actual": 174.0,
                "reserves_initial": 610.0,
                "reserves_remaining": 381.0,
            },
            {
                "well_id": "PROD_AZ_225",
                "well_name": "Az_225",
                "well_type": "producer",
                "lu_id": "Аянский (Западный)",
                "sloy_id": "S2",
                "well_pad_id": "21b",
                "cell_id": "CELL_B",
                "x": 2950.0,
                "y": 2050.0,
                "oil_rate_actual": 47.0,
                "liquid_rate_actual": 122.0,
                "gas_rate_actual": 7800.0,
                "watercut_actual": 0.615,
                "pressure_actual": 166.0,
                "reserves_initial": 505.0,
                "reserves_remaining": 301.0,
            },
            {
                "well_id": "PROD_BT_103",
                "well_name": "Bt_103",
                "well_type": "producer",
                "lu_id": "Болхитский",
                "sloy_id": "S1",
                "well_pad_id": "12",
                "cell_id": "CELL_C",
                "x": 5200.0,
                "y": 1600.0,
                "oil_rate_actual": 39.0,
                "liquid_rate_actual": 96.0,
                "gas_rate_actual": 6500.0,
                "watercut_actual": 0.594,
                "pressure_actual": 182.0,
                "reserves_initial": 430.0,
                "reserves_remaining": 287.0,
            },
            {
                "well_id": "PROD_BT_115",
                "well_name": "Bt_115",
                "well_type": "producer",
                "lu_id": "Болхитский",
                "sloy_id": "S2",
                "well_pad_id": "12",
                "cell_id": "CELL_C",
                "x": 5750.0,
                "y": 2350.0,
                "oil_rate_actual": 44.0,
                "liquid_rate_actual": 112.0,
                "gas_rate_actual": 7100.0,
                "watercut_actual": 0.607,
                "pressure_actual": 179.0,
                "reserves_initial": 455.0,
                "reserves_remaining": 299.0,
            },
            {
                "well_id": "PROD_KI_041",
                "well_name": "Ki_041",
                "well_type": "producer",
                "lu_id": "Кийский",
                "sloy_id": "S1",
                "well_pad_id": "7",
                "cell_id": "CELL_D",
                "x": 8400.0,
                "y": 1300.0,
                "oil_rate_actual": 33.0,
                "liquid_rate_actual": 84.0,
                "gas_rate_actual": 5200.0,
                "watercut_actual": 0.607,
                "pressure_actual": 186.0,
                "reserves_initial": 350.0,
                "reserves_remaining": 238.0,
            },
            {
                "well_id": "INJ_AZ_101",
                "well_name": "Az_INJ_101",
                "well_type": "injector",
                "lu_id": "Аянский (Западный)",
                "sloy_id": "S1",
                "well_pad_id": "20a",
                "cell_id": "CELL_A",
                "x": 1400.0,
                "y": 2050.0,
                "injection_rate_actual": 640.0,
                "pressure_actual": 203.0,
            },
            {
                "well_id": "INJ_AZ_307",
                "well_name": "Az_INJ_307",
                "well_type": "injector",
                "lu_id": "Аянский (Западный)",
                "sloy_id": "S2",
                "well_pad_id": "21b",
                "cell_id": "CELL_B",
                "x": 3300.0,
                "y": 2850.0,
                "injection_rate_actual": 520.0,
                "pressure_actual": 198.0,
            },
            {
                "well_id": "INJ_BT_202",
                "well_name": "Bt_INJ_202",
                "well_type": "injector",
                "lu_id": "Болхитский",
                "sloy_id": "S1",
                "well_pad_id": "12",
                "cell_id": "CELL_C",
                "x": 5350.0,
                "y": 2950.0,
                "injection_rate_actual": 580.0,
                "pressure_actual": 207.0,
            },
            {
                "well_id": "INJ_KI_044",
                "well_name": "Ki_INJ_044",
                "well_type": "injector",
                "lu_id": "Кийский",
                "sloy_id": "S1",
                "well_pad_id": "7",
                "cell_id": "CELL_D",
                "x": 8000.0,
                "y": 2350.0,
                "injection_rate_actual": 430.0,
                "pressure_actual": 201.0,
            },
        ]

    def _link_type(self, injector: dict[str, Any], producer: dict[str, Any]) -> str:
        if injector["cell_id"] == "CELL_A" and producer["well_name"] == "Az_216":
            return "channel"
        if injector["cell_id"] == "CELL_B" and producer["well_name"] == "Az_225":
            return "screen"
        return "normal" if injector["cell_id"] == producer["cell_id"] else "unknown"

    def _build_links(self, injectors: list[dict[str, Any]], producers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raw_by_injector: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for injector in injectors:
            for producer in producers:
                distance_m = hypot(injector["x"] - producer["x"], injector["y"] - producer["y"])
                inside = distance_m <= INFLUENCE_RADIUS_M
                if not inside:
                    continue
                link_type = self._link_type(injector, producer)
                distance_weight = max(0.0, 1 - distance_m / INFLUENCE_RADIUS_M) ** DISTANCE_POWER
                raw_weight = distance_weight * LINK_TYPE_MULTIPLIERS.get(link_type, 1.0)
                raw_by_injector[injector["well_id"]].append(
                    {
                        "link_id": f"{injector['well_id']}->{producer['well_id']}",
                        "injector_id": injector["well_id"],
                        "injector_name": injector["well_name"],
                        "producer_id": producer["well_id"],
                        "producer_name": producer["well_name"],
                        "lu_id": producer["lu_id"],
                        "sloy_id": producer["sloy_id"],
                        "well_pad_id": producer["well_pad_id"],
                        "cell_id": producer["cell_id"],
                        "distance_m": _round(distance_m, 1),
                        "inside_influence_radius": True,
                        "link_type": link_type,
                        "raw_weight": raw_weight,
                        "alpha_prior": 0.0,
                    }
                )

        links: list[dict[str, Any]] = []
        for injector_links in raw_by_injector.values():
            total_weight = sum(item["raw_weight"] for item in injector_links)
            for item in injector_links:
                item["alpha_prior"] = _round(item["raw_weight"] / total_weight if total_weight > 0 else 0.0, 6)
                item.pop("raw_weight", None)
                links.append(item)
        return links

    def _calibrate_links(self, links: list[dict[str, Any]], producers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        producer_lookup = {item["well_id"]: item for item in producers}
        raw_by_injector: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for link in links:
            producer = producer_lookup[link["producer_id"]]
            pressure_deficit = _clamp((190.0 - producer["pressure_actual"]) / 40.0, 0.0, 1.0)
            watercut_signal = _clamp(producer["watercut_actual"], 0.0, 1.0)
            type_bonus = 1.18 if link["link_type"] == "channel" else 0.72 if link["link_type"] == "screen" else 1.0
            fitted_raw = link["alpha_prior"] * (0.84 + 0.34 * watercut_signal + 0.26 * pressure_deficit) * type_bonus
            fitted = dict(link)
            fitted["fitted_raw"] = fitted_raw
            raw_by_injector[link["injector_id"]].append(fitted)

        calibrated: list[dict[str, Any]] = []
        for injector_links in raw_by_injector.values():
            total = sum(item["fitted_raw"] for item in injector_links)
            for index, item in enumerate(injector_links):
                producer = producer_lookup[item["producer_id"]]
                alpha = item["fitted_raw"] / total if total > 0 else item["alpha_prior"]
                ipvi = 0.18 + alpha * 0.82 + producer["watercut_actual"] * 0.22
                sw = _clamp(0.24 + alpha * 0.38 + producer["watercut_actual"] * 0.24, 0.18, 0.86)
                sg = _clamp(0.03 + producer["gas_rate_actual"] / 300000.0, 0.02, 0.12)
                so = _clamp(1 - sw - sg, 0.08, 0.72)
                actual_pressure = producer["pressure_actual"]
                pressure_calc = actual_pressure + ((index % 3) - 1) * 2.4 + (item["alpha_prior"] - alpha) * 12.0
                watercut_calc = _clamp(producer["watercut_actual"] + (alpha - item["alpha_prior"]) * 0.08, 0.0, 0.98)
                item.update(
                    {
                        "alpha": _round(alpha, 6),
                        "eta": _round(0.72 + alpha * 0.18, 4),
                        "tau_days": _round(18 + item["distance_m"] / 42 + (0 if item["link_type"] == "channel" else 16), 1),
                        "pv": _round(item["distance_m"] * 0.32 * (1.18 if item["link_type"] == "screen" else 0.84 if item["link_type"] == "channel" else 1.0), 1),
                        "ipvi": _round(ipvi, 4),
                        "sw": _round(sw, 4),
                        "so": _round(so, 4),
                        "sg": _round(sg, 4),
                        "pressure": _round(pressure_calc, 2),
                        "watercut_actual": _round(producer["watercut_actual"], 4),
                        "watercut_calc": _round(watercut_calc, 4),
                        "pressure_actual": _round(actual_pressure, 2),
                        "pressure_calc": _round(pressure_calc, 2),
                    }
                )
                item.pop("fitted_raw", None)
                calibrated.append(item)
        return calibrated

    def _enrich_wells(self, wells: list[dict[str, Any]], links: list[dict[str, Any]]) -> list[dict[str, Any]]:
        links_by_producer: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for link in links:
            links_by_producer[link["producer_id"]].append(link)

        enriched: list[dict[str, Any]] = []
        for well in wells:
            item = dict(well)
            if item["well_type"] == "producer":
                active_links = links_by_producer.get(item["well_id"], [])
                sw = sum(link["sw"] * link["alpha"] for link in active_links) / sum(link["alpha"] for link in active_links) if active_links else 0.25
                pressure_calc = item["pressure_actual"] + (0.5 - sw) * 9.0
                watercut_calc = _clamp(item["watercut_actual"] + (sw - 0.5) * 0.12, 0.0, 0.98)
                liquid_calc = item["liquid_rate_actual"] * (1 + (pressure_calc - item["pressure_actual"]) / 800.0)
                oil_calc = liquid_calc * (1 - watercut_calc)
                gas_calc = item["gas_rate_actual"] * (1 + (watercut_calc - item["watercut_actual"]) * 0.28)
                item.update(
                    {
                        "oil_rate_calc": _round(oil_calc),
                        "liquid_rate_calc": _round(liquid_calc),
                        "gas_rate_calc": _round(gas_calc),
                        "watercut_calc": _round(watercut_calc, 4),
                        "pressure_calc": _round(pressure_calc, 2),
                        "sw": _round(sw, 4),
                        "so": _round(_clamp(1 - sw - 0.05, 0.08, 0.75), 4),
                        "sg": 0.05,
                        "link_count": len(active_links),
                        "role": "Добывающая",
                    }
                )
            else:
                item.update(
                    {
                        "injection_rate_calc": _round(item["injection_rate_actual"] * 0.985),
                        "pressure_calc": _round(item["pressure_actual"] - 1.8, 2),
                        "sw": 1.0,
                        "so": 0.0,
                        "sg": 0.0,
                        "role": "Нагнетательная",
                    }
                )
            enriched.append(item)
        return enriched

    def _build_cells(self, wells: list[dict[str, Any]], links: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cells: dict[str, dict[str, Any]] = {}
        for well in wells:
            cell = cells.setdefault(
                well["cell_id"],
                {
                    "cell_id": well["cell_id"],
                    "lu_id": well["lu_id"],
                    "sloy_id": well["sloy_id"],
                    "well_pad_id": well["well_pad_id"],
                    "producer_count": 0,
                    "injector_count": 0,
                    "reserves_initial": 0.0,
                    "reserves_remaining": 0.0,
                    "oil_rate_actual": 0.0,
                    "oil_rate_calc": 0.0,
                    "liquid_rate_actual": 0.0,
                    "liquid_rate_calc": 0.0,
                    "gas_rate_actual": 0.0,
                    "gas_rate_calc": 0.0,
                    "injection_rate_actual": 0.0,
                    "injection_rate_calc": 0.0,
                    "pressure_actual_total": 0.0,
                    "pressure_calc_total": 0.0,
                    "pressure_count": 0,
                    "sw_total": 0.0,
                    "so_total": 0.0,
                    "sg_total": 0.0,
                    "sat_count": 0,
                },
            )
            if well["well_type"] == "producer":
                cell["producer_count"] += 1
                cell["reserves_initial"] += well.get("reserves_initial", 0.0)
                cell["reserves_remaining"] += well.get("reserves_remaining", 0.0)
                for key in ("oil_rate", "liquid_rate", "gas_rate"):
                    cell[f"{key}_actual"] += well.get(f"{key}_actual", 0.0)
                    cell[f"{key}_calc"] += well.get(f"{key}_calc", 0.0)
            else:
                cell["injector_count"] += 1
                cell["injection_rate_actual"] += well.get("injection_rate_actual", 0.0)
                cell["injection_rate_calc"] += well.get("injection_rate_calc", 0.0)
            cell["pressure_actual_total"] += well.get("pressure_actual", 0.0)
            cell["pressure_calc_total"] += well.get("pressure_calc", 0.0)
            cell["pressure_count"] += 1
            cell["sw_total"] += well.get("sw", 0.0)
            cell["so_total"] += well.get("so", 0.0)
            cell["sg_total"] += well.get("sg", 0.0)
            cell["sat_count"] += 1

        link_count_by_cell: dict[str, int] = defaultdict(int)
        for link in links:
            link_count_by_cell[link["cell_id"]] += 1

        result: list[dict[str, Any]] = []
        for cell in cells.values():
            pressure_count = max(1, cell.pop("pressure_count"))
            sat_count = max(1, cell.pop("sat_count"))
            pressure_actual_total = cell.pop("pressure_actual_total")
            pressure_calc_total = cell.pop("pressure_calc_total")
            sw_total = cell.pop("sw_total")
            so_total = cell.pop("so_total")
            sg_total = cell.pop("sg_total")
            cell.update(
                {
                    "pore_volume": _round(cell["reserves_initial"] * 1.85),
                    "pressure_actual": _round(pressure_actual_total / pressure_count, 2),
                    "pressure_calc": _round(pressure_calc_total / pressure_count, 2),
                    "sw": _round(sw_total / sat_count, 4),
                    "so": _round(so_total / sat_count, 4),
                    "sg": _round(sg_total / sat_count, 4),
                    "link_count": link_count_by_cell[cell["cell_id"]],
                }
            )
            for key, value in list(cell.items()):
                if isinstance(value, float):
                    cell[key] = _round(value)
            result.append(cell)
        return sorted(result, key=lambda item: (item["lu_id"], item["cell_id"]))

    def _build_aggregates(self, wells: list[dict[str, Any]], cells: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        producers = [item for item in wells if item["well_type"] == "producer"]
        return {
            "well": [self._aggregate_row(item["well_name"], [item], "well") for item in producers],
            "pad": self._group_rows(producers, "well_pad_id", "pad"),
            "sloy": self._group_rows(producers, "sloy_id", "sloy"),
            "lu": self._group_rows(producers, "lu_id", "lu"),
            "cell": [self._cell_row(cell) for cell in cells],
        }

    def _group_rows(self, producers: list[dict[str, Any]], key: str, level: str) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for producer in producers:
            grouped[str(producer.get(key) or "Без значения")].append(producer)
        return [self._aggregate_row(name, rows, level) for name, rows in sorted(grouped.items())]

    def _aggregate_row(self, name: str, rows: list[dict[str, Any]], level: str) -> dict[str, Any]:
        totals = {
            "oil_rate_actual": sum(item.get("oil_rate_actual", 0.0) for item in rows),
            "oil_rate_calc": sum(item.get("oil_rate_calc", 0.0) for item in rows),
            "liquid_rate_actual": sum(item.get("liquid_rate_actual", 0.0) for item in rows),
            "liquid_rate_calc": sum(item.get("liquid_rate_calc", 0.0) for item in rows),
            "gas_rate_actual": sum(item.get("gas_rate_actual", 0.0) for item in rows),
            "gas_rate_calc": sum(item.get("gas_rate_calc", 0.0) for item in rows),
            "reserves_remaining": sum(item.get("reserves_remaining", 0.0) for item in rows),
        }
        watercut_actual = sum(item.get("watercut_actual", 0.0) * item.get("liquid_rate_actual", 0.0) for item in rows) / max(1.0, totals["liquid_rate_actual"])
        watercut_calc = sum(item.get("watercut_calc", 0.0) * item.get("liquid_rate_calc", 0.0) for item in rows) / max(1.0, totals["liquid_rate_calc"])
        pressure_actual = sum(item.get("pressure_actual", 0.0) for item in rows) / max(1, len(rows))
        pressure_calc = sum(item.get("pressure_calc", 0.0) for item in rows) / max(1, len(rows))
        return self._format_comparison_row(
            {
                "level": level,
                "name": name,
                "well_count": len(rows),
                **totals,
                "watercut_actual": watercut_actual,
                "watercut_calc": watercut_calc,
                "pressure_actual": pressure_actual,
                "pressure_calc": pressure_calc,
            }
        )

    def _cell_row(self, cell: dict[str, Any]) -> dict[str, Any]:
        watercut_actual = 1 - cell["oil_rate_actual"] / max(1.0, cell["liquid_rate_actual"])
        watercut_calc = 1 - cell["oil_rate_calc"] / max(1.0, cell["liquid_rate_calc"])
        return self._format_comparison_row(
            {
                "level": "cell",
                "name": cell["cell_id"],
                "well_count": cell["producer_count"],
                "oil_rate_actual": cell["oil_rate_actual"],
                "oil_rate_calc": cell["oil_rate_calc"],
                "liquid_rate_actual": cell["liquid_rate_actual"],
                "liquid_rate_calc": cell["liquid_rate_calc"],
                "gas_rate_actual": cell["gas_rate_actual"],
                "gas_rate_calc": cell["gas_rate_calc"],
                "watercut_actual": watercut_actual,
                "watercut_calc": watercut_calc,
                "pressure_actual": cell["pressure_actual"],
                "pressure_calc": cell["pressure_calc"],
                "reserves_remaining": cell["reserves_remaining"],
            }
        )

    def _format_comparison_row(self, row: dict[str, Any]) -> dict[str, Any]:
        formatted = {
            "level": row["level"],
            "name": row["name"],
            "well_count": int(row["well_count"]),
        }
        for metric in ("oil_rate", "liquid_rate", "gas_rate", "watercut", "pressure"):
            actual = float(row.get(f"{metric}_actual", 0.0))
            calc = float(row.get(f"{metric}_calc", 0.0))
            formatted[f"{metric}_actual"] = _round(actual, 4 if metric == "watercut" else 3)
            formatted[f"{metric}_calc"] = _round(calc, 4 if metric == "watercut" else 3)
            formatted[f"{metric}_delta"] = _delta(calc, actual)
        formatted["reserves_remaining"] = _round(row.get("reserves_remaining", 0.0))
        return formatted
