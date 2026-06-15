from __future__ import annotations

import math
from datetime import date
from importlib import metadata
from collections import defaultdict
from typing import Any


class CrmConnectivityBuilder:
    """Builds injector-producer connectivity for the OPM-first Module B path.

    The production contract names pywaterflood as the preferred CRM engine. The
    runtime keeps that dependency optional: when the package is unavailable, a
    deterministic distance/history prior is used and reported in diagnostics.
    """

    def build_regions(
        self,
        *,
        wells: list[dict[str, Any]],
        production_history: list[dict[str, Any]],
        injection_history: list[dict[str, Any]],
        radius_m: float,
        max_connections_per_producer: int,
        min_connection_weight: float = 0.03,
        allow_cross_lu: bool = False,
        allow_cross_sloy: bool = False,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        producers = [item for item in wells if item.get("well_type") == "producer"]
        injectors = [item for item in wells if item.get("well_type") == "injector"]
        production = self._history_by_well_date(production_history)
        injection = self._history_by_well_date(injection_history)
        pywaterflood_available = self._pywaterflood_available()
        crm_fit = self._fit_pywaterflood(
            producers=producers,
            injectors=injectors,
            production=production,
            injection=injection,
        )

        regions: list[dict[str, Any]] = []
        filtered_connections: list[dict[str, Any]] = []
        fallback_connections: list[dict[str, Any]] = []
        unconnected_producers: list[str] = []
        producer_region_id_by_name = {
            str(producer.get("well_name") or ""): index + 1
            for index, producer in enumerate(sorted(producers, key=lambda item: str(item.get("well_name") or "")))
        }

        region_id = 1
        for producer in sorted(producers, key=lambda item: str(item.get("well_name") or "")):
            candidates: list[dict[str, Any]] = []
            for injector in injectors:
                distance = self._distance(injector, producer)
                if distance <= 0 or distance > radius_m:
                    continue
                if not allow_cross_lu and self._text(injector.get("lu_id")) and self._text(producer.get("lu_id")):
                    if self._text(injector.get("lu_id")) != self._text(producer.get("lu_id")):
                        filtered_connections.append(self._filter_record(injector, producer, distance, "cross_lu"))
                        continue
                if not allow_cross_sloy and self._text(injector.get("sloy_id")) and self._text(producer.get("sloy_id")):
                    if self._text(injector.get("sloy_id")) != self._text(producer.get("sloy_id")):
                        filtered_connections.append(self._filter_record(injector, producer, distance, "cross_sloy"))
                        continue
                candidates.append(
                    {
                        "injector": injector,
                        "producer": producer,
                        "distance_m": distance,
                        "score": self._connection_score(
                            injector=injector,
                            producer=producer,
                            distance_m=distance,
                            radius_m=radius_m,
                            production=production,
                            injection=injection,
                            crm_fit=crm_fit,
                        ),
                        "crm_raw_gain": self._crm_gain(crm_fit, injector, producer),
                        "crm_tau_days": self._crm_tau(crm_fit, injector, producer),
                    }
                )

            candidates.sort(key=lambda item: (-float(item["score"]), float(item["distance_m"])))
            selected = [item for item in candidates[:max(1, max_connections_per_producer)] if float(item["score"]) > 0]
            total_score = sum(float(item["score"]) for item in selected)
            weighted = [
                {**item, "alpha": float(item["score"]) / total_score}
                for item in selected
                if total_score > 0
            ]
            filtered_low_weight = [item for item in weighted if float(item["alpha"]) < min_connection_weight]
            weighted = [item for item in weighted if float(item["alpha"]) >= min_connection_weight]

            if not weighted and selected:
                nearest = min(selected, key=lambda item: float(item["distance_m"]))
                weighted = [{**nearest, "alpha": 1.0}]
                fallback_connections.append(
                    {
                        "producer_name": producer.get("well_name"),
                        "injector_name": nearest["injector"].get("well_name"),
                        "reason": "all_crm_weights_below_threshold",
                    }
                )
            if not weighted:
                unconnected_producers.append(str(producer.get("well_name") or ""))
                continue

            for item in weighted:
                injector = item["injector"]
                producer_region_id = producer_region_id_by_name.get(str(producer.get("well_name") or ""), region_id)
                distance = float(item["distance_m"])
                alpha = float(item["alpha"])
                raw_gain = self._number(item.get("crm_raw_gain"))
                tau_days = self._number(item.get("crm_tau_days"), max(7.0, min(730.0, distance / 15.0)))
                regions.append(
                    {
                        "connection_id": f"{injector['well_name']}:{producer['well_name']}",
                        "region_id": region_id,
                        "producer_region_id": producer_region_id,
                        "opernum": region_id,
                        "region_name": f"R{region_id:04d}",
                        "injector_name": injector["well_name"],
                        "producer_name": producer["well_name"],
                        "injector_opm_name": injector["opm_well_name"],
                        "producer_opm_name": producer["opm_well_name"],
                        "distance_m": round(distance, 3),
                        "alpha": round(alpha, 6),
                        "alpha_prior": round(alpha, 6),
                        "tau_days": round(max(0.001, tau_days), 3),
                        "crm_source": "pywaterflood.crm.CRM.fit"
                        if crm_fit.get("status") == "fit"
                        else "distance_history_fallback",
                        "crm_quality": {
                            "engine": "pywaterflood" if crm_fit.get("status") == "fit" else "distance_history_fallback",
                            "fit_status": crm_fit.get("status"),
                            "fit_message": crm_fit.get("message"),
                            "raw_gain": round(raw_gain, 14),
                            "score": round(float(item["score"]), 14),
                            "normalized_weight": round(alpha, 6),
                            "tau_days": round(max(0.001, tau_days), 3),
                            "producer_rmse": self._crm_rmse(crm_fit, producer),
                            "low_weight_filtered": len(filtered_low_weight),
                        },
                        "permeability_multiplier": 1.0,
                        "pv_multiplier": 1.0,
                        "corey_water_multiplier": 1.0,
                        "corey_oil_multiplier": 1.0,
                        "transmissibility_multiplier": 1.0,
                        "channel_multiplier": 1.0,
                        "screen_multiplier": 1.0,
                        "flow_modifier_type": "normal",
                        "target_p_res_source": "production_history.p_res",
                    }
                )
                region_id += 1

        diagnostics = {
            "engine": "pywaterflood" if pywaterflood_available else "distance_history_fallback",
            "pywaterflood_available": pywaterflood_available,
            "pywaterflood_version": self._pywaterflood_version() if pywaterflood_available else None,
            "pywaterflood_fit": {
                key: value
                for key, value in crm_fit.items()
                if key
                in {
                    "status",
                    "message",
                    "model_class",
                    "constraints",
                    "tau_selection",
                    "time_count",
                    "producer_count",
                    "injector_count",
                    "producer_order",
                    "injector_order",
                    "rmse_by_producer",
                }
            },
            "radius_m": radius_m,
            "max_connections_per_producer": max_connections_per_producer,
            "min_connection_weight": min_connection_weight,
            "allow_cross_lu": allow_cross_lu,
            "allow_cross_sloy": allow_cross_sloy,
            "producer_count": len(producers),
            "injector_count": len(injectors),
            "connection_count": len(regions),
            "unconnected_producers": [item for item in unconnected_producers if item],
            "fallback_connections": fallback_connections[:100],
            "filtered_connections": filtered_connections[:100],
        }
        return regions, diagnostics

    def _connection_score(
        self,
        *,
        injector: dict[str, Any],
        producer: dict[str, Any],
        distance_m: float,
        radius_m: float,
        production: dict[str, dict[str, dict[str, Any]]],
        injection: dict[str, dict[str, dict[str, Any]]],
        crm_fit: dict[str, Any] | None = None,
    ) -> float:
        crm_gain = self._crm_gain(crm_fit, injector, producer)
        if crm_fit and crm_fit.get("status") == "fit":
            return max(0.0, crm_gain or 0.0)

        distance_ratio = max(distance_m / max(radius_m, 1.0), 0.001)
        distance_score = 1.0 / (distance_ratio * distance_ratio)
        layer_score = 1.0
        if self._text(injector.get("sloy_id")) and self._text(producer.get("sloy_id")):
            layer_score = 1.35 if self._text(injector.get("sloy_id")) == self._text(producer.get("sloy_id")) else 0.65

        producer_name = str(producer.get("well_name") or "")
        injector_name = str(injector.get("well_name") or "")
        prod_rows = production.get(producer_name, {})
        inj_rows = injection.get(injector_name, {})
        dates = sorted(set(prod_rows) & set(inj_rows))
        corr = 0.0
        if len(dates) >= 3:
            inj_values = [self._number(inj_rows[date].get("q_water_inj")) for date in dates]
            water_values = [self._number(prod_rows[date].get("q_water")) for date in dates]
            liquid_values = [self._number(prod_rows[date].get("q_liq")) for date in dates]
            corr = max(self._correlation(inj_values, water_values), self._correlation(inj_values, liquid_values), 0.0)

        inj_total = sum(self._number(row.get("q_water_inj")) for row in inj_rows.values())
        prod_total = sum(self._number(row.get("q_liq")) or self._number(row.get("q_oil")) + self._number(row.get("q_water")) for row in prod_rows.values())
        history_scale = math.sqrt(max(inj_total, 0.0) + 1.0) * math.sqrt(max(prod_total, 0.0) + 1.0)
        history_score = 1.0 + min(3.0, history_scale / 10000.0) + max(0.0, corr)
        return max(0.0, distance_score * layer_score * history_score)

    def _history_by_well_date(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in rows:
            well = self._well_name(row)
            date = str(row.get("date") or row.get("month") or row.get("period") or "")[:10]
            if well and date:
                grouped[well][date] = row
        return grouped

    def _filter_record(self, injector: dict[str, Any], producer: dict[str, Any], distance: float, reason: str) -> dict[str, Any]:
        return {
            "injector_name": injector.get("well_name"),
            "producer_name": producer.get("well_name"),
            "distance_m": round(distance, 3),
            "reason": reason,
        }

    def _pywaterflood_available(self) -> bool:
        try:
            __import__("pywaterflood")
        except Exception:
            return False
        return True

    def _pywaterflood_version(self) -> str | None:
        try:
            return metadata.version("pywaterflood")
        except Exception:
            return None

    def _fit_pywaterflood(
        self,
        *,
        producers: list[dict[str, Any]],
        injectors: list[dict[str, Any]],
        production: dict[str, dict[str, dict[str, Any]]],
        injection: dict[str, dict[str, dict[str, Any]]],
    ) -> dict[str, Any]:
        if not producers or not injectors:
            return {"status": "skipped", "message": "no_producers_or_injectors"}
        try:
            import numpy as np
            from pywaterflood import CRM
        except Exception as exc:
            return {"status": "unavailable", "message": str(exc)}

        producer_names = [str(item.get("well_name") or "") for item in sorted(producers, key=lambda row: str(row.get("well_name") or ""))]
        injector_names = [str(item.get("well_name") or "") for item in sorted(injectors, key=lambda row: str(row.get("well_name") or ""))]
        dates = sorted(
            {
                day
                for well in [*producer_names, *injector_names]
                for day in [*production.get(well, {}).keys(), *injection.get(well, {}).keys()]
                if day
            }
        )
        if len(dates) < 3:
            return {
                "status": "insufficient_history",
                "message": "pywaterflood CRM requires at least three aligned history dates",
                "producer_order": producer_names,
                "injector_order": injector_names,
                "time_count": len(dates),
            }

        start = self._parse_date(dates[0])
        time = []
        for index, day in enumerate(dates):
            parsed = self._parse_date(day)
            time.append(float((parsed - start).days if start and parsed else index))
        time_array = np.asarray(time, dtype=float)
        production_matrix = np.asarray(
            [
                [
                    self._liquid_rate(production.get(producer, {}).get(day, {}))
                    for producer in producer_names
                ]
                for day in dates
            ],
            dtype=float,
        )
        injection_matrix = np.asarray(
            [
                [
                    self._number(injection.get(injector, {}).get(day, {}).get("q_water_inj"))
                    for injector in injector_names
                ]
                for day in dates
            ],
            dtype=float,
        )
        if not np.any(production_matrix > 0) or not np.any(injection_matrix > 0):
            return {
                "status": "insufficient_rates",
                "message": "production or injection matrix has no positive rates",
                "producer_order": producer_names,
                "injector_order": injector_names,
                "time_count": len(dates),
            }

        try:
            model = CRM(primary=True, tau_selection="per-pair", constraints="up-to one")
            model.fit(
                production_matrix,
                injection_matrix,
                time_array,
                num_cores=1,
                options={"maxiter": 250},
            )
            prediction = model.predict()
            residual = production_matrix - prediction
            rmse = np.sqrt(np.mean(np.square(residual), axis=0))
            return {
                "status": "fit",
                "message": "ok",
                "model_class": "pywaterflood.crm.CRM",
                "constraints": "up-to one",
                "tau_selection": "per-pair",
                "producer_order": producer_names,
                "injector_order": injector_names,
                "producer_index": {name: index for index, name in enumerate(producer_names)},
                "injector_index": {name: index for index, name in enumerate(injector_names)},
                "time_count": len(dates),
                "producer_count": len(producer_names),
                "injector_count": len(injector_names),
                "gains": model.gains,
                "tau": model.tau,
                "rmse_by_producer": {
                    name: round(float(rmse[index]), 6)
                    for index, name in enumerate(producer_names)
                },
            }
        except Exception as exc:
            return {
                "status": "fit_failed",
                "message": str(exc),
                "producer_order": producer_names,
                "injector_order": injector_names,
                "time_count": len(dates),
            }

    def _crm_gain(self, crm_fit: dict[str, Any] | None, injector: dict[str, Any], producer: dict[str, Any]) -> float | None:
        if not crm_fit or crm_fit.get("status") != "fit":
            return None
        gains = crm_fit.get("gains")
        injector_index = crm_fit.get("injector_index", {}).get(str(injector.get("well_name") or ""))
        producer_index = crm_fit.get("producer_index", {}).get(str(producer.get("well_name") or ""))
        if gains is None or injector_index is None or producer_index is None:
            return None
        try:
            return max(0.0, float(gains[injector_index, producer_index]))
        except Exception:
            return None

    def _crm_tau(self, crm_fit: dict[str, Any] | None, injector: dict[str, Any], producer: dict[str, Any]) -> float | None:
        if not crm_fit or crm_fit.get("status") != "fit":
            return None
        tau = crm_fit.get("tau")
        injector_index = crm_fit.get("injector_index", {}).get(str(injector.get("well_name") or ""))
        producer_index = crm_fit.get("producer_index", {}).get(str(producer.get("well_name") or ""))
        if tau is None or injector_index is None or producer_index is None:
            return None
        try:
            if getattr(tau, "ndim", 0) == 1:
                return max(0.001, float(tau[producer_index]))
            return max(0.001, float(tau[injector_index, producer_index]))
        except Exception:
            return None

    def _crm_rmse(self, crm_fit: dict[str, Any] | None, producer: dict[str, Any]) -> float | None:
        if not crm_fit or crm_fit.get("status") != "fit":
            return None
        value = crm_fit.get("rmse_by_producer", {}).get(str(producer.get("well_name") or ""))
        return None if value is None else round(float(value), 6)

    def _liquid_rate(self, row: dict[str, Any]) -> float:
        q_liq = self._number(row.get("q_liq"))
        if q_liq > 0:
            return q_liq
        return self._number(row.get("q_oil")) + self._number(row.get("q_water"))

    def _parse_date(self, value: str) -> date | None:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def _correlation(self, left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or len(left) < 2:
            return 0.0
        left_mean = sum(left) / len(left)
        right_mean = sum(right) / len(right)
        numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
        left_den = math.sqrt(sum((x - left_mean) ** 2 for x in left))
        right_den = math.sqrt(sum((y - right_mean) ** 2 for y in right))
        if left_den == 0 or right_den == 0:
            return 0.0
        return numerator / (left_den * right_den)

    def _distance(self, left: dict[str, Any], right: dict[str, Any]) -> float:
        return math.hypot(float(left["x"]) - float(right["x"]), float(left["y"]) - float(right["y"]))

    def _well_name(self, row: dict[str, Any]) -> str:
        return str(row.get("well_name") or row.get("well") or row.get("well_id") or row.get("producer_id") or row.get("injector_id") or "").strip().upper()

    def _text(self, value: Any) -> str:
        return str(value or "").strip()

    def _number(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            number = float(value)
        except (TypeError, ValueError):
            return default
        if math.isnan(number) or math.isinf(number):
            return default
        return number


class RegionCubeBuilder:
    def build(self, *, grid: dict[str, Any], cells: list[dict[str, Any]], regions: list[dict[str, Any]]) -> dict[str, Any]:
        region_by_id = {int(region.get("region_id") or 0): region for region in regions}
        arrays = {
            "opernum": [],
            "fipnum": [],
            "satnum": [],
            "rocknum": [],
            "pvtnum": [],
            "actnum": [],
        }
        rows: list[dict[str, Any]] = []
        active_by_region: dict[int, int] = defaultdict(int)
        pv_by_region: dict[int, float] = defaultdict(float)

        for cell in cells:
            region_id = int(cell.get("connection_region_id") or cell.get("region_id") or 0)
            region = region_by_id.get(region_id, {})
            opernum = int(region.get("opernum") or region_id or cell.get("well_region_id") or 0)
            actnum = int(cell.get("actnum") or 0)
            fipnum = int(cell.get("fipnum") or max(1, opernum))
            satnum = int(cell.get("satnum") or max(1, opernum))
            rocknum = int(cell.get("rocknum") or max(1, opernum))
            pvtnum = int(cell.get("pvtnum") or 1)
            arrays["opernum"].append(opernum)
            arrays["fipnum"].append(fipnum)
            arrays["satnum"].append(satnum)
            arrays["rocknum"].append(rocknum)
            arrays["pvtnum"].append(pvtnum)
            arrays["actnum"].append(actnum)
            if actnum:
                active_by_region[opernum] += 1
                pv_by_region[opernum] += float(cell.get("pv") or 0.0)
            rows.append(
                {
                    "cell_id": cell.get("cell_id"),
                    "i": cell.get("i"),
                    "j": cell.get("j"),
                    "k": cell.get("k", 1),
                    "opernum": opernum,
                    "producer_region_id": region.get("producer_region_id"),
                    "connection_region_id": region_id,
                    "connection_id": region.get("connection_id"),
                    "crm_weight": region.get("alpha"),
                    "dominant_injector_name": region.get("injector_name"),
                    "producer_name": region.get("producer_name"),
                    "fipnum": fipnum,
                    "satnum": satnum,
                    "rocknum": rocknum,
                    "pvtnum": pvtnum,
                    "actnum": actnum,
                    "pv": cell.get("pv"),
                }
            )

        return {
            "nx": int(grid.get("nx") or 0),
            "ny": int(grid.get("ny") or 0),
            "nz": int(grid.get("nz") or 1),
            "cell_count": len(cells),
            "active_cell_count": sum(arrays["actnum"]),
            "arrays": arrays,
            "cells": rows,
            "region_summary": [
                {
                    "opernum": region_id,
                    "active_cell_count": count,
                    "pore_volume": round(pv_by_region.get(region_id, 0.0), 3),
                }
                for region_id, count in sorted(active_by_region.items())
            ],
        }
