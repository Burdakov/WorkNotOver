from __future__ import annotations

import math
from datetime import datetime
from typing import Any


class RegionCalibrationReporter:
    """Builds the first deterministic calibration result for Module B.

    Full automated history matching requires repeated external OPM Flow runs.
    This reporter makes the calibration contract concrete today: every region
    receives explicit parameters, objective components and an acceptance status.
    """

    def build_parameter_set(self, regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        parameters: list[dict[str, Any]] = []
        for region in regions:
            region_id = int(region.get("region_id") or 0)
            parameters.append(
                {
                    "region_id": region_id,
                    "connection_id": region.get("connection_id") or f"region:{region_id}",
                    "producer_region_id": region.get("producer_region_id") or region_id,
                    "injector_name": region.get("injector_name"),
                    "producer_name": region.get("producer_name"),
                    "permx_multiplier": float(region.get("permeability_multiplier") or 1.0),
                    "permy_multiplier": float(region.get("permeability_multiplier") or 1.0),
                    "permz_multiplier": float(region.get("permeability_multiplier") or 1.0),
                    "transmissibility_multiplier": float(region.get("transmissibility_multiplier") or 1.0),
                    "pv_multiplier": float(region.get("pv_multiplier") or 1.0)
                    * float(region.get("pv_history_match_multiplier") or 1.0),
                    "satnum": region_id or 1,
                    "swof_shape": {
                        "swc": 0.18,
                        "sorw": 0.15,
                        "krw_end": min(1.0, max(0.05, float(region.get("corey_water_multiplier") or 1.0))),
                        "kro_end": min(1.0, max(0.05, float(region.get("corey_oil_multiplier") or 1.0))),
                        "nw": 2.0,
                        "no": 2.0,
                    },
                    "sgof_shape": {
                        "sgc": 0.0,
                        "sorg": 0.10,
                        "krg_end": 1.0,
                        "krog_end": 1.0,
                        "ng": 2.0,
                        "nog": 2.0,
                    },
                    "bounds": {
                        "permeability_multiplier": [0.05, 20.0],
                        "transmissibility_multiplier": [0.05, 20.0],
                        "pv_multiplier": [0.05, 500.0],
                        "corey_exponent": [0.5, 8.0],
                    },
                }
            )
        return parameters

    def build_report(
        self,
        *,
        run_status: str,
        region_metrics: list[dict[str, Any]],
        parameter_set: list[dict[str, Any]],
        pressure_tolerance_bar: float,
        watercut_tolerance_fraction: float,
        pressure_weight: float,
        watercut_weight: float,
        rate_weight: float,
    ) -> dict[str, Any]:
        iterations: list[dict[str, Any]] = []
        objective_terms: list[float] = []
        calibrated_count = 0

        for index, metric in enumerate(region_metrics, start=1):
            pressure_error = self._optional_abs(metric.get("pressure_error_bar"))
            watercut_error = self._optional_abs(metric.get("watercut_error"))
            liquid_fact = self._number(metric.get("current_liquid"))
            injection = self._number(metric.get("current_injection"))
            rate_proxy_error = abs(liquid_fact - injection * 0.2) / max(liquid_fact, 1.0) if liquid_fact > 0 and injection > 0 else None

            pressure_term = 0.0 if pressure_error is None else pressure_error / max(pressure_tolerance_bar, 0.001)
            watercut_term = 0.0 if watercut_error is None else watercut_error / max(watercut_tolerance_fraction, 0.001)
            rate_term = 0.0 if rate_proxy_error is None else min(10.0, rate_proxy_error)
            objective = pressure_weight * pressure_term + watercut_weight * watercut_term + rate_weight * rate_term
            objective_terms.append(objective)

            within_pressure = pressure_error is None or pressure_error <= pressure_tolerance_bar
            within_watercut = watercut_error is None or watercut_error <= watercut_tolerance_fraction
            accepted = within_pressure and within_watercut
            if accepted:
                calibrated_count += 1

            iterations.append(
                {
                    "iteration": index,
                    "region_id": metric.get("region_id"),
                    "connection_id": metric.get("connection_id"),
                    "changed_parameters": {
                        "pv_multiplier": metric.get("pv_multiplier", 1.0),
                        "permeability_multiplier": metric.get("permeability_multiplier", 1.0),
                        "transmissibility_multiplier": metric.get("transmissibility_multiplier", 1.0),
                    },
                    "objective": round(objective, 6),
                    "pressure_error_bar": pressure_error,
                    "watercut_error_fraction": watercut_error,
                    "rate_proxy_error_fraction": rate_proxy_error,
                    "accepted": accepted,
                    "status": "within_tolerance" if accepted else "outside_tolerance",
                }
            )

        region_count = len(region_metrics)
        best_objective = sum(objective_terms) / len(objective_terms) if objective_terms else 0.0
        if run_status not in {"completed", "imported"}:
            status = "diagnostic_only"
        elif region_count and calibrated_count == region_count:
            status = "calibrated"
        elif calibrated_count:
            status = "partial"
        else:
            status = "failed"

        return {
            "created_at": datetime.utcnow().isoformat(),
            "status": status,
            "run_status": run_status,
            "best_objective": round(best_objective, 6),
            "regions_within_tolerance": calibrated_count,
            "regions_total": region_count,
            "criteria": {
                "pressure_tolerance_bar": pressure_tolerance_bar,
                "watercut_tolerance_fraction": watercut_tolerance_fraction,
            },
            "objective_weights": {
                "pressure": pressure_weight,
                "watercut": watercut_weight,
                "rate": rate_weight,
            },
            "parameter_set": parameter_set,
            "iterations": iterations,
            "notes": [
                "Calibration report is deterministic and region-based.",
                "Status remains diagnostic_only until external OPM Flow output is available.",
            ]
            if run_status not in {"completed", "imported"}
            else [],
        }

    def _optional_abs(self, value: Any) -> float | None:
        number = self._nullable_number(value)
        return abs(number) if number is not None else None

    def _nullable_number(self, value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            number = float(value)
        except (TypeError, ValueError):
            return None
        if math.isnan(number) or math.isinf(number):
            return None
        return number

    def _number(self, value: Any, default: float = 0.0) -> float:
        number = self._nullable_number(value)
        return default if number is None else number
