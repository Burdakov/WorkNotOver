from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.opm_flow.calibration import RegionCalibrationReporter
from app.services.opm_flow.crm import CrmConnectivityBuilder, RegionCubeBuilder
from app.services.opm_flow.importer import OpmResultImporter
from app.services.opm_flow.runner import OpmFlowRunner
from app.services.opm_flow.schemas import (
    Field2DPrepareRequest,
    Field2DPrepareResponse,
    Field2DRunFromScenarioRequest,
    Field2DRunResponse,
    OpmCaseManifest,
    SimulationArtifact,
    SimulationRun,
)
from app.services.opm_flow.storage import SimulationRunStore


@dataclass(frozen=True)
class _TrajectoryPoint:
    well_name: str
    md: float
    x: float
    y: float
    z: float


class Field2DModelService:
    """Single 2D OPM Flow model for all scenario wells.

    This replaces the old edge-based approach. The model has one grid,
    one layer and region corridors between nearest injector-producer pairs.
    """

    def __init__(self, *, store: SimulationRunStore | None = None, runner: OpmFlowRunner | None = None) -> None:
        self.store = store or SimulationRunStore()
        self.runner = runner or OpmFlowRunner()
        self.importer = OpmResultImporter()
        self.crm_builder = CrmConnectivityBuilder()
        self.region_cube_builder = RegionCubeBuilder()
        self.calibration_reporter = RegionCalibrationReporter()

    def prepare(self, request: Field2DPrepareRequest) -> Field2DPrepareResponse:
        if not request.pvt_include and not request.allow_generated_pvt:
            raise ValueError("Scenario-bound pvt_properties dataset is required for 2D OPM Flow model.")
        if request.pvt_include and not self._pvt_include_text(request.pvt_include) and not request.allow_generated_pvt:
            raise ValueError("Scenario-bound pvt_properties payload must contain raw OPM include text.")
        trajectory_by_well = self._group_trajectories(request.trajectories)
        group_by_well = self._well_group_lookup(request.well_groups)
        perforation_points = self._perforation_points(request.perforations, trajectory_by_well)
        wells = self._build_wells(request, trajectory_by_well, group_by_well, perforation_points)
        producers = [item for item in wells if item["well_type"] == "producer"]
        injectors = [item for item in wells if item["well_type"] == "injector"]
        grid = self._build_grid(wells, request, perforation_points)
        perforation_points = self._with_perforation_grid_indices(grid, perforation_points)
        regions, crm_diagnostics = self.crm_builder.build_regions(
            wells=wells,
            production_history=request.production_history,
            injection_history=request.injection_history,
            radius_m=request.influence_radius_m,
            max_connections_per_producer=request.nearest_producers_per_injector,
            min_connection_weight=float(request.metadata.get("min_connection_weight", 0.03)) if isinstance(request.metadata, dict) else 0.03,
            allow_cross_lu=bool(request.metadata.get("allow_cross_lu", False)) if isinstance(request.metadata, dict) else False,
            allow_cross_sloy=bool(request.metadata.get("allow_cross_sloy", False)) if isinstance(request.metadata, dict) else False,
        )
        well_regions = self._build_well_regions(wells, request, start_region_id=len(regions) + 1)
        grid_cells = self._build_grid_cells(grid, wells, regions, well_regions, request, perforation_points)
        self._apply_reserve_multipliers(grid_cells, regions, producers, request)
        self._apply_history_match_adjustments(grid_cells, regions, request)
        region_cube = self.region_cube_builder.build(grid=grid, cells=grid_cells, regions=regions)
        return Field2DPrepareResponse(
            scenario_id=request.scenario_id,
            wells=wells,
            regions=regions,
            well_regions=well_regions,
            grid={**grid, "perforation_points": perforation_points, "cells": grid_cells, "region_cube": region_cube},
            diagnostics={
                **self._diagnostics(request, wells, regions, well_regions, grid, grid_cells, perforation_points),
                "crm": crm_diagnostics,
                "region_cube": {
                    "cell_count": region_cube.get("cell_count", 0),
                    "active_cell_count": region_cube.get("active_cell_count", 0),
                    "region_count": len(region_cube.get("region_summary", [])),
                },
            },
        )

    def run(self, request: Field2DPrepareRequest, run_options: Field2DRunFromScenarioRequest) -> Field2DRunResponse:
        preparation = self.prepare(request)
        run_id, run_root = self.store.allocate_run_root(
            request.scenario_id,
            scenario_name=request.scenario_name,
            run_name="opm-flow-2d",
        )
        run = SimulationRun(
            run_id=run_id,
            scenario_id=request.scenario_id,
            forecast_method="opm_flow_blackoil",
            case_name=f"field_2d_{request.scenario_id[:8]}",
            case_root=str(run_root),
            input_dir=str(run_root / "input"),
            output_dir=str(run_root / "output"),
            normalized_dir=str(run_root / "normalized"),
            metadata={
                "run_type": "field_2d_single_model",
                "runtime_profile": "opm_flow_2d_field",
                "scenario_name": request.scenario_name,
                "field_2d_config": self._field_2d_config_snapshot(request),
                "run_external_flow": run_options.run_external_flow,
                "flow_executable": self.runner.executable,
                "flow_available": self.runner.is_available(),
            },
        )
        run.opm_case_manifest = self._build_case(run, preparation, request, run_options)
        run.artifacts = self._scan_artifacts(run)
        run.status = "case_built"
        run = self.store.save(run)

        if run_options.run_external_flow:
            run = self.runner.run(run)
        else:
            now = datetime.utcnow().isoformat()
            run.started_at = now
            run.finished_at = now
            run.status = "case_built"
            run.metadata["runner_note"] = "External OPM Flow execution skipped by request."
        run.artifacts = self._scan_artifacts(run)
        if run_options.run_external_flow:
            run.import_result = self.importer.import_results(run)
            run.artifacts = self._scan_artifacts(run)

        analysis = self._build_analysis(run, preparation, request)
        self._write_analysis(run, analysis)
        run.artifacts = self._scan_artifacts(run)
        if run_options.run_external_flow and not self.runner.is_available():
            run.status = "failed"
            run.metadata["runner_error"] = f"OPM Flow executable '{self.runner.executable}' was not found."
        run = self.store.save(run)
        return Field2DRunResponse(simulation_run=run, preparation=preparation, analysis=analysis)

    def latest_run(self, scenario_id: str) -> SimulationRun:
        runs = [
            run for run in self.store.list_for_scenario(scenario_id)
            if run.forecast_method in {"opm_flow_blackoil", "opm_flow_2d_field"} or run.metadata.get("run_type") == "field_2d_single_model"
        ]
        if not runs:
            raise FileNotFoundError(f"No 2D field run for scenario {scenario_id}")
        return runs[0]

    def load_analysis(self, scenario_id: str, run_id: str | None = None) -> dict[str, Any]:
        run = self.latest_run(scenario_id) if run_id is None else self.store.load(scenario_id, run_id)
        path = Path(run.normalized_dir) / "field_2d_analysis.json"
        if not path.exists():
            raise FileNotFoundError(path)
        return json.loads(path.read_text(encoding="utf-8"))

    def _build_case(
        self,
        run: SimulationRun,
        preparation: Field2DPrepareResponse,
        request: Field2DPrepareRequest,
        run_options: Field2DRunFromScenarioRequest,
    ) -> OpmCaseManifest:
        input_dir = Path(run.input_dir)
        include_dir = input_dir / "includes"
        include_dir.mkdir(parents=True, exist_ok=True)
        output_dir = Path(run.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        case_name = self._safe_case_name(run.case_name)
        include_files = {
            "runspec.inc": self._runspec(case_name, preparation, request),
            "grid.inc": self._grid_include(preparation, request),
            "edit.inc": self._edit_include(preparation),
            "props.inc": self._props_include(request, preparation),
            "regions.inc": self._regions_include(preparation),
            "init.inc": self._init_include(preparation),
            "schedule.inc": self._schedule_include(preparation, request),
            "summary.inc": self._summary_include(run_options.summary_vectors, preparation.wells),
        }
        include_paths: list[str] = []
        for name, text in include_files.items():
            path = include_dir / name
            path.write_text(text, encoding="utf-8")
            include_paths.append(str(path))

        deck_path = input_dir / f"{case_name}.DATA"
        deck_path.write_text(self._deck(case_name), encoding="utf-8")
        return OpmCaseManifest(
            case_name=case_name,
            deck_path=str(deck_path),
            include_files=include_paths,
            sections=["RUNSPEC", "GRID", "EDIT", "PROPS", "REGIONS", "SOLUTION", "SCHEDULE", "SUMMARY"],
            summary_vectors=run_options.summary_vectors,
            input_bindings_hash=hashlib.sha256(preparation.model_dump_json().encode("utf-8")).hexdigest(),
            deck_hash=hashlib.sha256(deck_path.read_bytes()).hexdigest(),
            validation_warnings=preparation.diagnostics.get("warnings", []),
            metadata={
                "grid": {key: preparation.grid.get(key) for key in ("nx", "ny", "nz", "dx_m", "dy_m", "dz_m")},
                "region_count": len(preparation.regions),
                "well_region_count": len(preparation.well_regions),
                "init": preparation.diagnostics.get("init"),
                "pvt_source": preparation.diagnostics.get("pvt_source"),
                "crm": preparation.diagnostics.get("crm"),
                "region_cube": preparation.diagnostics.get("region_cube"),
            },
        )

    def _build_wells(
        self,
        request: Field2DPrepareRequest,
        trajectory_by_well: dict[str, list[_TrajectoryPoint]],
        group_by_well: dict[str, dict[str, Any]],
        perforation_points: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        producer_names = {self._well_name(row) for row in request.production_history if self._well_name(row)}
        injector_names = {self._well_name(row) for row in request.injection_history if self._well_name(row)}
        perforation_centers = self._perforation_centers_from_points(perforation_points)
        names = sorted(set(trajectory_by_well) | set(perforation_centers) | producer_names | injector_names)
        wells: list[dict[str, Any]] = []
        reserve_lookup = self._reserve_lookup(request.initial_reserves)
        opm_index = 1
        for name in names:
            center = perforation_centers.get(name) or self._trajectory_center(trajectory_by_well.get(name, []))
            if center is None:
                continue
            group = group_by_well.get(name, {})
            if name in injector_names:
                well_type = "injector"
            elif name in producer_names:
                well_type = "producer"
            else:
                well_type = "producer"
            wells.append(
                {
                    "well_name": name,
                    "opm_well_name": f"W{opm_index:05d}",
                    "well_type": well_type,
                    "x": round(center[0], 3),
                    "y": round(center[1], 3),
                    "z": round(center[2], 3),
                    "lu_id": self._text(group.get("lu_id") or group.get("lu")) or "",
                    "sloy_id": self._text(group.get("sloy_id") or group.get("sloy")) or "",
                    "well_pad_id": self._text(group.get("well_pad_id") or group.get("well_pad")) or "",
                    "niz": reserve_lookup.get(name),
                }
            )
            opm_index += 1
        return wells

    def _build_grid(
        self,
        wells: list[dict[str, Any]],
        request: Field2DPrepareRequest,
        perforation_points: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not wells:
            raise ValueError("No wells with coordinates for 2D OPM model.")
        xs = [float(item["x"]) for item in wells] + [float(item["x"]) for item in perforation_points]
        ys = [float(item["y"]) for item in wells] + [float(item["y"]) for item in perforation_points]
        dx_m = float(request.dx_m)
        dy_m = float(request.dy_m)
        padding_m = max(float(request.grid_padding_m), float(request.influence_radius_m))
        min_x = math.floor((min(xs) - padding_m) / dx_m) * dx_m
        max_x = math.ceil((max(xs) + padding_m) / dx_m) * dx_m
        min_y = math.floor((min(ys) - padding_m) / dy_m) * dy_m
        max_y = math.ceil((max(ys) + padding_m) / dy_m) * dy_m
        nx = max(1, int(math.ceil((max_x - min_x) / dx_m)))
        ny = max(1, int(math.ceil((max_y - min_y) / dy_m)))
        if nx * ny > request.max_grid_cells:
            scale = math.sqrt((nx * ny) / request.max_grid_cells)
            nx = max(1, int(nx / scale))
            ny = max(1, int(ny / scale))
            dx_m = max(dx_m, (max_x - min_x) / nx)
            dy_m = max(dy_m, (max_y - min_y) / ny)
        for well in wells:
            i = min(nx, max(1, int((float(well["x"]) - min_x) / dx_m) + 1))
            j = min(ny, max(1, int((float(well["y"]) - min_y) / dy_m) + 1))
            well["grid_i"] = i
            well["grid_j"] = j
        return {
            "nx": nx,
            "ny": ny,
            "nz": 1,
            "dx_m": dx_m,
            "dy_m": dy_m,
            "dz_m": request.dz_m,
            "padding_m": padding_m,
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "cell_count": nx * ny,
        }

    def _build_well_regions(
        self,
        wells: list[dict[str, Any]],
        request: Field2DPrepareRequest,
        *,
        start_region_id: int,
    ) -> list[dict[str, Any]]:
        well_regions: list[dict[str, Any]] = []
        for offset, well in enumerate(sorted(wells, key=lambda item: item["well_name"])):
            region_id = start_region_id + offset
            well_regions.append(
                {
                    "region_id": region_id,
                    "region_name": f"WREG{region_id:04d}",
                    "region_type": "well",
                    "well_name": well["well_name"],
                    "opm_well_name": well["opm_well_name"],
                    "well_type": well["well_type"],
                    "x": well["x"],
                    "y": well["y"],
                    "radius_m": request.well_region_radius_m,
                    "permeability_multiplier": 1.0,
                    "pv_multiplier": 1.0,
                    "corey_water_multiplier": 1.0,
                    "corey_oil_multiplier": 1.0,
                    "transmissibility_multiplier": 1.0,
                    "channel_multiplier": 1.0,
                    "screen_multiplier": 1.0,
                    "flow_modifier_type": "well_region",
                }
            )
        return well_regions

    def _build_grid_cells(
        self,
        grid: dict[str, Any],
        wells: list[dict[str, Any]],
        regions: list[dict[str, Any]],
        well_regions: list[dict[str, Any]],
        request: Field2DPrepareRequest,
        perforation_points: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        well_by_name = {item["well_name"]: item for item in wells}
        well_region_by_name = {item["well_name"]: item for item in well_regions}
        perforations_by_cell = self._perforation_cell_map(grid, perforation_points)
        cells: list[dict[str, Any]] = []
        for j in range(1, int(grid["ny"]) + 1):
            for i in range(1, int(grid["nx"]) + 1):
                x = float(grid["min_x"]) + (i - 0.5) * float(grid["dx_m"])
                y = float(grid["min_y"]) + (j - 0.5) * float(grid["dy_m"])
                region = self._region_for_cell(x, y, regions, well_by_name, request.region_corridor_width_m)
                well_region = self._well_region_for_cell(x, y, well_regions)
                cell_perforations = perforations_by_cell.get((i, j), [])
                if well_region is None and cell_perforations:
                    perforation_wells = sorted({str(item["well_name"]) for item in cell_perforations})
                    well_region = next((well_region_by_name.get(name) for name in perforation_wells if well_region_by_name.get(name)), None)
                nearest_well_distance = self._nearest_well_distance(x, y, wells)
                active = bool(cell_perforations) or nearest_well_distance <= request.influence_radius_m or region is not None or well_region is not None
                region_id = int(region["region_id"]) if region else int(well_region["region_id"]) if well_region else 0
                well_region_id = int(well_region["region_id"]) if well_region else 0
                base_pv = float(grid["dx_m"]) * float(grid["dy_m"]) * float(grid["dz_m"]) * request.porosity
                cells.append(
                    {
                        "cell_id": f"{i}:{j}:1",
                        "i": i,
                        "j": j,
                        "k": 1,
                        "x": round(x, 3),
                        "y": round(y, 3),
                        "region_id": region_id,
                        "connection_region_id": int(region["region_id"]) if region else 0,
                        "connection_id": region.get("connection_id") if region else None,
                        "producer_region_id": int(region.get("producer_region_id") or 0) if region else 0,
                        "opernum": int(region.get("opernum") or region["region_id"]) if region else well_region_id,
                        "crm_weight": float(region.get("alpha") or 0.0) if region else None,
                        "dominant_injector_name": region.get("injector_name") if region else None,
                        "producer_name": region.get("producer_name") if region else None,
                        "well_region_id": well_region_id,
                        "active": active,
                        "actnum": 1 if active else 0,
                        "perforation_count": len(cell_perforations),
                        "perforation_wells": sorted({str(item["well_name"]) for item in cell_perforations}),
                        "nearest_well_distance_m": round(nearest_well_distance, 3) if nearest_well_distance < math.inf else None,
                        "pvtnum": 1,
                        "satnum": max(1, region_id),
                        "rocknum": max(1, region_id),
                        "fipnum": max(1, region_id),
                        "poro": request.porosity,
                        "permx": request.permeability_md,
                        "permy": request.permeability_md,
                        "permz": request.permeability_md * 0.1,
                        "transmissibility_multiplier": 1.0,
                        "pv": base_pv,
                        "pv_multiplier": 1.0,
                        "pressure": request.initial_pressure_bar,
                        "swat": request.initial_water_saturation,
                        "sgas": request.initial_gas_saturation,
                    }
                )
        return cells

    def _apply_reserve_multipliers(
        self,
        cells: list[dict[str, Any]],
        regions: list[dict[str, Any]],
        producers: list[dict[str, Any]],
        request: Field2DPrepareRequest,
    ) -> None:
        producer_regions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        region_by_id = {int(region["region_id"]): region for region in regions}
        for region in regions:
            producer_regions[region["producer_name"]].append(region)
        cells_by_region: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for cell in cells:
            cells_by_region[int(cell["region_id"])].append(cell)
        for producer in producers:
            niz = self._number(producer.get("niz"))
            if niz <= 0:
                continue
            target_pv = niz * request.formation_volume_factor / request.initial_oil_saturation
            target_regions = producer_regions.get(producer["well_name"], [])
            if not target_regions:
                continue
            target_pv_per_region = target_pv / len(target_regions)
            for region in target_regions:
                region_cells = cells_by_region.get(int(region["region_id"]), [])
                base_region_pv = sum(float(cell["pv"]) for cell in region_cells)
                multiplier = target_pv_per_region / base_region_pv if base_region_pv > 0 else 1.0
                multiplier = max(0.05, min(500.0, multiplier))
                region["pv_multiplier"] = round(multiplier, 6)
                for cell in region_cells:
                    cell["pv_multiplier"] = region["pv_multiplier"]
                    cell["pv"] = round(float(cell["pv"]) * region["pv_multiplier"], 3)

    def _apply_history_match_adjustments(
        self,
        cells: list[dict[str, Any]],
        regions: list[dict[str, Any]],
        request: Field2DPrepareRequest,
    ) -> None:
        production = self._history_by_well_date(request.production_history)
        injection = self._history_by_well_date(request.injection_history)
        cells_by_region: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for cell in cells:
            connection_region_id = int(cell.get("connection_region_id") or 0)
            if connection_region_id:
                cells_by_region[connection_region_id].append(cell)

        pressure_tol = max(float(request.pressure_tolerance_bar), 0.001)
        watercut_tol = max(float(request.watercut_tolerance_fraction), 0.001)
        for region in regions:
            region_id = int(region["region_id"])
            region_cells = cells_by_region.get(region_id, [])
            if not region_cells:
                region["history_match_status"] = "no_cells"
                continue

            latest_prod = self._latest_row(production.get(region["producer_name"], {}))
            latest_inj = self._latest_row(injection.get(region["injector_name"], {}))
            p_fact = self._positive_number(latest_prod.get("p_res"))
            if p_fact is None:
                p_fact = self._positive_number(latest_inj.get("p_res"))
            p_calc = self._avg(region_cells, "pressure") or request.initial_pressure_bar

            q_liq = self._number(latest_prod.get("q_liq"))
            q_water = self._number(latest_prod.get("q_water"))
            watercut_fact = q_water / q_liq if q_liq > 0 else None
            watercut_calc = self._avg(region_cells, "swat") or request.initial_water_saturation

            pressure_error = None if p_fact is None else p_fact - p_calc
            watercut_error = None if watercut_fact is None else watercut_fact - watercut_calc
            pressure_steps = 0.0 if pressure_error is None else max(-10.0, min(10.0, pressure_error / pressure_tol))
            watercut_steps = 0.0 if watercut_error is None else max(-10.0, min(10.0, watercut_error / watercut_tol))

            perm_multiplier = self._clamp(1.0 + 0.08 * request.pressure_weight * pressure_steps, 0.25, 4.0)
            pv_adjustment = self._clamp(1.0 + 0.04 * request.pressure_weight * pressure_steps, 0.25, 4.0)
            water_multiplier = self._clamp(1.0 + 0.12 * request.watercut_weight * watercut_steps, 0.25, 4.0)
            oil_multiplier = self._clamp(1.0 - 0.08 * request.watercut_weight * watercut_steps, 0.25, 4.0)
            swat_shift = 0.015 * request.watercut_weight * watercut_steps

            region["permeability_multiplier"] = round(perm_multiplier, 6)
            region["pv_history_match_multiplier"] = round(pv_adjustment, 6)
            region["corey_water_multiplier"] = round(water_multiplier, 6)
            region["corey_oil_multiplier"] = round(oil_multiplier, 6)
            region["transmissibility_multiplier"] = round(perm_multiplier, 6)
            if perm_multiplier > 1.05:
                region["flow_modifier_type"] = "channel"
                region["channel_multiplier"] = round(perm_multiplier, 6)
                region["screen_multiplier"] = 1.0
            elif perm_multiplier < 0.95:
                region["flow_modifier_type"] = "screen"
                region["channel_multiplier"] = 1.0
                region["screen_multiplier"] = round(perm_multiplier, 6)
            else:
                region["flow_modifier_type"] = "normal"
                region["channel_multiplier"] = 1.0
                region["screen_multiplier"] = 1.0

            region["p_res_fact"] = p_fact
            region["p_res_calc"] = round(p_calc, 3)
            region["pressure_error_bar"] = round(pressure_error, 3) if pressure_error is not None else None
            region["watercut_fact"] = watercut_fact
            region["watercut_calc"] = round(watercut_calc, 5)
            region["watercut_error"] = round(watercut_error, 5) if watercut_error is not None else None
            region["within_pressure_tolerance"] = pressure_error is None or abs(pressure_error) <= request.pressure_tolerance_bar
            region["within_watercut_tolerance"] = watercut_error is None or abs(watercut_error) <= request.watercut_tolerance_fraction
            region["history_match_status"] = (
                "within_tolerance"
                if region["within_pressure_tolerance"] and region["within_watercut_tolerance"]
                else "adjusted"
            )

            for cell in region_cells:
                base_permx = float(cell.get("permx") or request.permeability_md)
                cell["permx"] = round(base_permx * perm_multiplier, 3)
                cell["permy"] = round(float(cell.get("permy") or request.permeability_md) * perm_multiplier, 3)
                cell["permz"] = round(float(cell.get("permz") or request.permeability_md * 0.1) * perm_multiplier, 3)
                cell["transmissibility_multiplier"] = round(perm_multiplier, 6)
                if pressure_error is not None and abs(pressure_error) > request.pressure_tolerance_bar:
                    cell["pv_multiplier"] = round(float(cell.get("pv_multiplier") or 1.0) * pv_adjustment, 6)
                    cell["pv"] = round(float(cell.get("pv") or 0.0) * pv_adjustment, 3)
                if p_fact is not None:
                    cell["pressure"] = round(p_calc + pressure_error * min(1.0, request.pressure_weight), 3)
                cell["swat"] = round(self._clamp(float(cell.get("swat") or 0.0) + swat_shift, 0.05, 0.95), 5)

    def _build_analysis(
        self,
        run: SimulationRun,
        preparation: Field2DPrepareResponse,
        request: Field2DPrepareRequest,
    ) -> dict[str, Any]:
        production = self._history_by_well_date(request.production_history)
        injection = self._history_by_well_date(request.injection_history)
        grid_cells = self._analysis_grid_cells(preparation)
        region_metrics = self._region_metrics(preparation, production, injection, grid_cells, run)
        timeseries = self._timeseries(preparation, production, injection, region_metrics, request)
        grid_states = self._grid_states(preparation, grid_cells, region_metrics, timeseries)
        region_cube = preparation.grid.get("region_cube") or self.region_cube_builder.build(
            grid=preparation.grid,
            cells=grid_cells,
            regions=preparation.regions,
        )
        region_parameters = self.calibration_reporter.build_parameter_set(preparation.regions)
        calibration = self.calibration_reporter.build_report(
            run_status=run.status,
            region_metrics=region_metrics,
            parameter_set=region_parameters,
            pressure_tolerance_bar=request.pressure_tolerance_bar,
            watercut_tolerance_fraction=request.watercut_tolerance_fraction,
            pressure_weight=request.pressure_weight,
            watercut_weight=request.watercut_weight,
            rate_weight=request.rate_weight,
        )
        opm_outputs = self._opm_output_summary(run)
        if run.status == "case_built":
            opm_import_mode = "case_built_no_flow_run"
        elif run.status == "completed" and opm_outputs["has_binary_output"]:
            opm_import_mode = "opm_output_artifacts_present_json_summary_pending"
        elif run.status == "failed":
            opm_import_mode = "opm_failed_json_fallback_from_field_2d_case"
        else:
            opm_import_mode = "json_fallback_from_field_2d_case"
        return {
            "scenario_id": request.scenario_id,
            "run_id": run.run_id,
            "created_at": datetime.utcnow().isoformat(),
            "method": "opm_flow_blackoil",
            "runtime_profile": "opm_flow_2d_field",
            "opm_import_mode": opm_import_mode,
            "preparation": preparation.model_dump(mode="json"),
            "grid_cells": grid_cells,
            "wells": preparation.wells,
            "regions": preparation.regions,
            "well_regions": preparation.well_regions,
            "crm_connectivity": preparation.regions,
            "region_cube": region_cube,
            "region_parameters": region_parameters,
            "calibration": calibration,
            "region_metrics": region_metrics,
            "timeseries": timeseries,
            "grid_states": grid_states,
            "diagnostics": {
                **preparation.diagnostics,
                "flow_status": run.status,
                "flow_executable": self.runner.executable,
                "flow_available": self.runner.is_available(),
                "flow_return_code": run.metadata.get("flow_return_code"),
                "runner_error": run.metadata.get("runner_error"),
                "opm_outputs": opm_outputs,
                "import_result": run.import_result.model_dump(mode="json") if run.import_result else None,
            },
        }

    def _analysis_grid_cells(self, preparation: Field2DPrepareResponse) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for cell in preparation.grid.get("cells", []):
            result.append(
                {
                    **cell,
                    "pressure": round(float(cell.get("pressure") or 0.0), 3),
                    "swat": round(float(cell.get("swat") or 0.0), 5),
                    "sgas": round(float(cell.get("sgas") or 0.04), 5),
                    "permx": round(float(cell.get("permx") or 0.0), 3),
                    "source": "field_2d_prepared_state",
                }
            )
        return result

    def _region_metrics(
        self,
        preparation: Field2DPrepareResponse,
        production: dict[str, dict[str, dict[str, Any]]],
        injection: dict[str, dict[str, dict[str, Any]]],
        grid_cells: list[dict[str, Any]],
        run: SimulationRun,
    ) -> list[dict[str, Any]]:
        cells_by_region: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for cell in grid_cells:
            cells_by_region[int(cell.get("connection_region_id") or cell.get("region_id") or 0)].append(cell)
        metrics: list[dict[str, Any]] = []
        for region in preparation.regions:
            producer_history = production.get(region["producer_name"], {})
            injector_history = injection.get(region["injector_name"], {})
            latest_prod = self._latest_row(producer_history)
            latest_inj = self._latest_row(injector_history)
            region_cells = cells_by_region.get(int(region["region_id"]), [])
            p_calc = self._avg(region_cells, "pressure")
            swat = self._avg(region_cells, "swat")
            q_liq = self._number(latest_prod.get("q_liq"))
            q_water = self._number(latest_prod.get("q_water"))
            q_gas = self._number(latest_prod.get("q_gas"))
            current_injection = self._number(latest_inj.get("q_water_inj"))
            current_reservoir_fluid = q_liq + q_gas / 1000.0
            watercut = q_water / q_liq if q_liq > 0 else None
            metrics.append(
                {
                    **region,
                    "connection_id": region.get("connection_id") or f"region:{region['region_id']}",
                    "cell_count": len(region_cells),
                    "pore_volume": round(sum(float(cell.get("pv") or 0.0) for cell in region_cells), 3),
                    "p_res_fact": self._positive_number(
                        region.get("p_res_fact") if "p_res_fact" in region else latest_prod.get("p_res")
                    ),
                    "p_res_calc": region.get("p_res_calc", p_calc),
                    "pressure_error_bar": region.get("pressure_error_bar"),
                    "within_pressure_tolerance": region.get("within_pressure_tolerance"),
                    "watercut_fact": watercut,
                    "watercut_calc": region.get("watercut_calc", swat),
                    "watercut_error": region.get("watercut_error"),
                    "within_watercut_tolerance": region.get("within_watercut_tolerance"),
                    "current_injection": current_injection,
                    "current_oil": self._number(latest_prod.get("q_oil")),
                    "current_liquid": q_liq,
                    "current_gas": q_gas,
                    "current_reservoir_fluid": round(current_reservoir_fluid, 6),
                    "current_compensation": current_injection / current_reservoir_fluid if current_reservoir_fluid > 0 else None,
                    "bhp_fact": self._nullable_number(latest_prod.get("bhp")),
                    "bhp_calc": p_calc - 18.0 if p_calc is not None else None,
                    "history_match_status": region.get("history_match_status", "not_adjusted"),
                    "flow_modifier_type": region.get("flow_modifier_type", "normal"),
                    "transmissibility_multiplier": region.get("transmissibility_multiplier", 1.0),
                    "channel_multiplier": region.get("channel_multiplier", 1.0),
                    "screen_multiplier": region.get("screen_multiplier", 1.0),
                    "run_status": run.status,
                    "artifact_count": len(run.artifacts),
                }
            )
        return metrics

    def _timeseries(
        self,
        preparation: Field2DPrepareResponse,
        production: dict[str, dict[str, dict[str, Any]]],
        injection: dict[str, dict[str, dict[str, Any]]],
        region_metrics: list[dict[str, Any]],
        request: Field2DPrepareRequest,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        metric_by_pair = {(item["injector_name"], item["producer_name"]): item for item in region_metrics}
        for region in preparation.regions:
            prod_rows = production.get(region["producer_name"], {})
            inj_rows = injection.get(region["injector_name"], {})
            dates = sorted(set(prod_rows) | set(inj_rows))
            metric = metric_by_pair.get((region["injector_name"], region["producer_name"]), {})
            latest_pressure_fact = self._positive_number(metric.get("p_res_fact"))
            latest_pressure_calc = self._positive_number(metric.get("p_res_calc"))
            pressure_offset = (
                latest_pressure_calc - latest_pressure_fact
                if latest_pressure_fact is not None and latest_pressure_calc is not None
                else 0.0
            )
            for index, date in enumerate(dates):
                prod = prod_rows.get(date, {})
                inj = inj_rows.get(date, {})
                q_oil = self._number(prod.get("q_oil"))
                q_water = self._number(prod.get("q_water"))
                q_liq = self._number(prod.get("q_liq")) or q_oil + q_water
                q_gas = self._number(prod.get("q_gas"))
                rate_multiplier = self._clamp(
                    1.0
                    + request.rate_weight
                    * (float(metric.get("transmissibility_multiplier") or 1.0) - 1.0)
                    * 0.25,
                    0.5,
                    1.5,
                )
                trend = 1.0 + index * 0.001
                watercut_calc = metric.get("watercut_calc")
                if watercut_calc is None and q_liq > 0:
                    watercut_calc = q_water / q_liq
                q_liq_calc = q_liq * rate_multiplier
                q_water_calc = q_liq_calc * float(watercut_calc or 0.0)
                q_oil_calc = max(0.0, q_liq_calc - q_water_calc)
                p_res_fact = self._positive_number(prod.get("p_res"))
                if p_res_fact is not None:
                    p_res_calc = p_res_fact + pressure_offset
                elif latest_pressure_calc is not None:
                    p_res_calc = latest_pressure_calc - index * 0.15
                else:
                    p_res_calc = None
                p_res_calc = self._positive_number(p_res_calc)
                rows.append(
                    {
                        "date": date,
                        "connection_id": region.get("connection_id") or f"region:{region['region_id']}",
                        "region_id": region["region_id"],
                        "injector_name": region["injector_name"],
                        "producer_name": region["producer_name"],
                        "q_water_inj_fact": self._number(inj.get("q_water_inj")),
                        "q_water_inj_calc": self._number(inj.get("q_water_inj")) * rate_multiplier,
                        "q_oil_fact": q_oil,
                        "q_oil_calc": q_oil_calc / trend,
                        "q_water_fact": q_water,
                        "q_water_calc": q_water_calc * trend,
                        "q_liq_fact": q_liq,
                        "q_liq_calc": q_liq_calc,
                        "q_gas_fact": q_gas,
                        "q_gas_calc": q_gas * rate_multiplier,
                        "watercut_fact": q_water / q_liq if q_liq > 0 else None,
                        "watercut_calc": watercut_calc,
                        "p_res_fact": p_res_fact,
                        "p_res_calc": p_res_calc,
                        "bhp_fact": self._nullable_number(prod.get("bhp")),
                        "bhp_calc": metric.get("bhp_calc"),
                    }
        )
        return rows

    def _grid_states(
        self,
        preparation: Field2DPrepareResponse,
        grid_cells: list[dict[str, Any]],
        region_metrics: list[dict[str, Any]],
        timeseries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        cells_by_region: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for cell in grid_cells:
            region_id = int(cell.get("connection_region_id") or cell.get("region_id") or 0)
            cells_by_region[region_id].append(cell)

        metric_by_region = {int(item.get("region_id") or 0): item for item in region_metrics}
        base_by_region: dict[int, dict[str, float]] = {}
        for region in preparation.regions:
            region_id = int(region.get("region_id") or 0)
            region_cells = cells_by_region.get(region_id, [])
            metric = metric_by_region.get(region_id, {})
            base_by_region[region_id] = {
                "pressure": self._positive_number(self._avg(region_cells, "pressure"))
                or self._positive_number(metric.get("p_res_calc"))
                or self._positive_number(metric.get("p_res_fact"))
                or 220.0,
                "swat": self._avg(region_cells, "swat")
                or self._nullable_number(metric.get("watercut_calc"))
                or 0.30,
                "sgas": self._avg(region_cells, "sgas") or 0.04,
            }
        rows_by_date_region: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
        for row in timeseries:
            date = str(row.get("date") or "").strip()
            region_id = int(row.get("region_id") or 0)
            if not date or region_id <= 0:
                continue
            rows_by_date_region[date][region_id] = row

        dates = sorted(rows_by_date_region)
        if not dates:
            dates = ["initial"]

        states: list[dict[str, Any]] = []
        last_by_region: dict[int, dict[str, float]] = {region_id: values.copy() for region_id, values in base_by_region.items()}
        for step_index, date in enumerate(dates):
            region_states: list[dict[str, Any]] = []
            rows_by_region = rows_by_date_region.get(date, {})
            for region in preparation.regions:
                region_id = int(region.get("region_id") or 0)
                row = rows_by_region.get(region_id, {})
                metric = metric_by_region.get(region_id, {})
                base = last_by_region.get(region_id) or base_by_region.get(region_id, {"pressure": 220.0, "swat": 0.30, "sgas": 0.04})
                pressure = self._positive_number(row.get("p_res_calc"))
                if pressure is None:
                    pressure = self._positive_number(row.get("p_res_fact"))
                if pressure is None:
                    pressure = base.get("pressure")
                if pressure is None:
                    pressure = self._positive_number(metric.get("p_res_calc"))
                if pressure is None:
                    pressure = base["pressure"]

                swat = self._nullable_number(row.get("watercut_calc"))
                if swat is None:
                    swat = self._nullable_number(metric.get("watercut_calc"))
                if swat is None:
                    swat = base.get("swat", 0.30)
                swat = self._clamp(float(swat), 0.05, 0.95)

                q_gas = self._number(row.get("q_gas_calc"))
                q_liq = self._number(row.get("q_liq_calc"))
                gas_fraction = q_gas / max(1.0, q_gas + q_liq)
                sgas = self._clamp(base.get("sgas", 0.04) + gas_fraction * 0.08 - (swat - base.get("swat", 0.30)) * 0.20, 0.0, 0.40)
                last_by_region[region_id] = {"pressure": float(pressure), "swat": float(swat), "sgas": float(sgas)}

                region_states.append(
                    {
                        "region_id": region_id,
                        "connection_id": region.get("connection_id") or f"region:{region_id}",
                        "injector_name": region.get("injector_name"),
                        "producer_name": region.get("producer_name"),
                        "pressure": round(float(pressure), 3),
                        "swat": round(float(swat), 5),
                        "sgas": round(float(sgas), 5),
                        "source": "field_2d_timeseries_region_state",
                    }
                )

            state_count = max(1, len(region_states))
            states.append(
                {
                    "report_step": step_index,
                    "date": date,
                    "source": "field_2d_timeseries_region_state",
                    "region_states": region_states,
                    "stats": {
                        "avg_pressure": round(sum(float(item["pressure"]) for item in region_states) / state_count, 3),
                        "avg_swat": round(sum(float(item["swat"]) for item in region_states) / state_count, 5),
                        "avg_sgas": round(sum(float(item["sgas"]) for item in region_states) / state_count, 5),
                    },
                }
            )
        return states

    def _write_analysis(self, run: SimulationRun, analysis: dict[str, Any]) -> None:
        normalized_dir = Path(run.normalized_dir)
        normalized_dir.mkdir(parents=True, exist_ok=True)
        (normalized_dir / "field_2d_analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "field_2d_grid_cells.json").write_text(json.dumps(analysis["grid_cells"], ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "field_2d_region_metrics.json").write_text(json.dumps(analysis["region_metrics"], ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "field_2d_timeseries.json").write_text(json.dumps(analysis["timeseries"], ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "field_2d_grid_states.json").write_text(json.dumps(analysis["grid_states"], ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "grid_static.json").write_text(json.dumps(analysis["grid_cells"], ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "grid_dynamic.json").write_text(json.dumps(analysis["grid_states"], ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "region_cube.json").write_text(json.dumps(analysis.get("region_cube", {}), ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "crm_connectivity.json").write_text(json.dumps(analysis.get("crm_connectivity", []), ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "region_parameters_initial.json").write_text(json.dumps(analysis.get("region_parameters", []), ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "region_parameters_best.json").write_text(json.dumps(analysis.get("calibration", {}).get("parameter_set", []), ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "calibration_iterations.json").write_text(json.dumps(analysis.get("calibration", {}).get("iterations", []), ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "calibration_report.json").write_text(json.dumps(analysis.get("calibration", {}), ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "well_timeseries.json").write_text(json.dumps(self._well_timeseries(analysis["timeseries"]), ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "field_timeseries.json").write_text(json.dumps(self._field_timeseries(analysis["timeseries"]), ensure_ascii=False, indent=2), encoding="utf-8")
        (normalized_dir / "region_timeseries.json").write_text(json.dumps(analysis["timeseries"], ensure_ascii=False, indent=2), encoding="utf-8")

    def _field_timeseries(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"q_oil_calc": 0.0, "q_water_calc": 0.0, "q_liq_calc": 0.0, "q_gas_calc": 0.0, "q_water_inj_calc": 0.0})
        for row in rows:
            date = str(row.get("date") or "")[:10]
            if not date:
                continue
            bucket = grouped[date]
            for key in bucket:
                bucket[key] += self._number(row.get(key))
        return [{"date": date, **values} for date, values in sorted(grouped.items())]

    def _well_timeseries(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"q_oil_calc": 0.0, "q_water_calc": 0.0, "q_liq_calc": 0.0, "q_gas_calc": 0.0})
        for row in rows:
            date = str(row.get("date") or "")[:10]
            producer = str(row.get("producer_name") or "")
            if not date or not producer:
                continue
            bucket = grouped[(producer, date)]
            for key in bucket:
                bucket[key] += self._number(row.get(key))
        return [
            {"well_name": well_name, "date": date, **values}
            for (well_name, date), values in sorted(grouped.items())
        ]

    def _deck(self, case_name: str) -> str:
        return "\n".join(
            [
                f"-- WorkNotOver 2D field OPM Flow case: {case_name}",
                "INCLUDE",
                " 'includes/runspec.inc' /",
                "INCLUDE",
                " 'includes/grid.inc' /",
                "INCLUDE",
                " 'includes/edit.inc' /",
                "INCLUDE",
                " 'includes/props.inc' /",
                "INCLUDE",
                " 'includes/regions.inc' /",
                "INCLUDE",
                " 'includes/init.inc' /",
                "INCLUDE",
                " 'includes/schedule.inc' /",
                "INCLUDE",
                " 'includes/summary.inc' /",
                "",
            ]
        )

    def _runspec(self, case_name: str, preparation: Field2DPrepareResponse, request: Field2DPrepareRequest) -> str:
        grid = preparation.grid
        well_count = len(preparation.wells)
        max_wells = max(20, well_count + 5)
        max_connections = max(20, well_count + 5)
        max_groups = max(20, well_count + 5)
        max_group_children = max(20, well_count + 5)
        sat_table_count = self._max_cell_int(preparation, "satnum", default=1)
        pvt_table_count = self._max_cell_int(preparation, "pvtnum", default=1)
        fip_table_count = self._max_cell_int(preparation, "fipnum", default=1)
        return "\n".join(
            [
                "RUNSPEC",
                "TITLE",
                f" WorkNotOver 2D field model {case_name}",
                "/",
                "DIMENS",
                f" {grid['nx']} {grid['ny']} 1 /",
                "OIL",
                "WATER",
                "GAS",
                "METRIC",
                "TABDIMS",
                f" {sat_table_count} {pvt_table_count} 100 100 100 {fip_table_count} /",
                "START",
                f" {self._opm_date(self._first_history_date(request))} /",
                "WELLDIMS",
                f" {max_wells} {max_connections} {max_groups} {max_group_children} /",
                "",
            ]
        )

    def _grid_include(self, preparation: Field2DPrepareResponse, request: Field2DPrepareRequest) -> str:
        grid = preparation.grid
        count = int(grid["nx"]) * int(grid["ny"])
        cells = preparation.grid.get("cells", [])
        return "\n".join(
            [
                "GRID",
                "DX",
                f" {count}*{float(grid['dx_m']):.3f} /",
                "DY",
                f" {count}*{float(grid['dy_m']):.3f} /",
                "DZ",
                f" {count}*{float(grid['dz_m']):.3f} /",
                "TOPS",
                f" {count}*{float(request.top_depth_m):.3f} /",
                "PORO",
                f" {self._cell_values(cells, 'poro', 5)} /",
                "PERMX",
                f" {self._cell_values(cells, 'permx')} /",
                "PERMY",
                f" {self._cell_values(cells, 'permy')} /",
                "PERMZ",
                f" {self._cell_values(cells, 'permz')} /",
                "ACTNUM",
                f" {self._cell_values(cells, 'actnum', 0)} /",
                "",
            ]
        )

    def _edit_include(self, preparation: Field2DPrepareResponse) -> str:
        cells = preparation.grid.get("cells", [])
        return "\n".join(
            [
                "EDIT",
                "-- Region pore-volume multipliers generated by WorkNotOver Module B calibration layer",
                "MULTPV",
                f" {self._cell_values(cells, 'pv_multiplier', 6)} /",
                "-- Directional transmissibility multipliers generated by WorkNotOver Module B calibration layer",
                "MULTX",
                f" {self._cell_values(cells, 'transmissibility_multiplier', 6)} /",
                "MULTY",
                f" {self._cell_values(cells, 'transmissibility_multiplier', 6)} /",
                "MULTZ",
                f" {self._cell_values(cells, 'transmissibility_multiplier', 6)} /",
                "",
            ]
        )

    def _props_include(self, request: Field2DPrepareRequest, preparation: Field2DPrepareResponse) -> str:
        include_text = self._pvt_include_text(request.pvt_include)
        if include_text:
            first_keyword = self._first_deck_keyword(include_text)
            if first_keyword != "PROPS":
                include_text = "PROPS\n" + include_text
            additions = self._props_augmentation_blocks(include_text, preparation, request)
            return "\n".join([include_text, *additions, ""])
        if not request.allow_generated_pvt:
            raise ValueError("Scenario-bound pvt_properties include is required; generated PVT fallback is disabled.")
        cells = preparation.grid.get("cells", [])
        sat_count = max(1, max((int(cell.get("satnum") or 1) for cell in cells), default=1))
        swof_blocks = []
        sgof_blocks = []
        for _ in range(sat_count):
            swof_blocks.extend(
                [
                    " 0.18 0.000 1.000 0",
                    " 0.32 0.030 0.640 0",
                    " 0.55 0.280 0.240 0",
                    " 0.85 1.000 0.000 0 /",
                ]
            )
            sgof_blocks.extend(
                [
                    " 0.00 0.000 1.000 0",
                    " 0.04 0.010 0.820 0",
                    " 0.20 0.300 0.280 0",
                    " 0.70 1.000 0.000 0 /",
                ]
            )
        return "\n".join(
            [
                "PROPS",
                "DENSITY",
                " 820 1010 1.25 /",
                "PVTW",
                f" {float(request.initial_pressure_bar):.3f} 1.0 4.0E-5 0.45 0.0 /",
                "PVDO",
                "  1   1.18  2.8",
                " 120   1.08  3.4",
                " 260   0.98  4.2 /",
                "PVDG",
                "  1   0.0300  0.012",
                " 120   0.0060  0.018",
                " 260   0.0030  0.024 /",
                "ROCK",
                f" {float(request.initial_pressure_bar):.3f} 1.2E-5 /",
                "SWOF",
                *swof_blocks,
                "SGOF",
                *sgof_blocks,
                "",
            ]
        )

    def _regions_include(self, preparation: Field2DPrepareResponse) -> str:
        cells = preparation.grid.get("cells", [])
        return "\n".join(
            [
                "REGIONS",
                "PVTNUM",
                f" {self._cell_values(cells, 'pvtnum', 0)} /",
                "SATNUM",
                f" {self._cell_values(cells, 'satnum', 0)} /",
                "ROCKNUM",
                f" {self._cell_values(cells, 'rocknum', 0)} /",
                "FIPNUM",
                f" {self._cell_values(cells, 'fipnum', 0)} /",
                "",
            ]
        )

    def _init_include(self, preparation: Field2DPrepareResponse) -> str:
        cells = preparation.grid.get("cells", [])
        return "\n".join(
            [
                "-- INIT values generated from scenario field_2d_config",
                "SOLUTION",
                "PRESSURE",
                f" {self._cell_values(cells, 'pressure')} /",
                "SWAT",
                f" {self._cell_values(cells, 'swat', 5)} /",
                "SGAS",
                f" {self._cell_values(cells, 'sgas', 5)} /",
                "",
            ]
        )

    def _schedule_include(self, preparation: Field2DPrepareResponse, request: Field2DPrepareRequest) -> str:
        production = self._history_by_well_date(request.production_history)
        injection = self._history_by_well_date(request.injection_history)
        dates = sorted({date for rows in [*production.values(), *injection.values()] for date in rows}) or [self._first_history_date(request)]
        lines = ["SCHEDULE", "RPTRST", " BASIC=2 FREQ=1 /", "RPTSCHED", " RESTART=2 /", "WELSPECS"]
        for well in preparation.wells:
            phase = "WATER" if well["well_type"] == "injector" else "OIL"
            lines.append(f" '{well['opm_well_name']}' 'FIELD' {well['grid_i']} {well['grid_j']} 1* {phase} /")
        lines.extend(["/", "COMPDAT"])
        for well in preparation.wells:
            lines.append(f" '{well['opm_well_name']}' {well['grid_i']} {well['grid_j']} 1 1 'OPEN' 1* 0.20 /")
        lines.append("/")
        opm_name_by_well = {well["well_name"]: well["opm_well_name"] for well in preparation.wells}
        for index, date in enumerate(dates):
            if index > 0:
                lines.extend(["DATES", f" {self._opm_date(date)} /", "/"])
            prod_rows = [rows[date] for rows in production.values() if date in rows]
            inj_rows = [rows[date] for rows in injection.values() if date in rows]
            if prod_rows:
                lines.append("WCONPROD")
                for row in prod_rows:
                    well_name = self._well_name(row)
                    opm_name = opm_name_by_well.get(well_name)
                    if not opm_name:
                        continue
                    oil = max(0.1, self._number(row.get("q_oil")) / 30.0)
                    bhp = max(1.0, self._number(row.get("bhp"), 150.0))
                    lines.append(f" '{opm_name}' 'OPEN' 'ORAT' {oil:.3f} 4* {bhp:.3f} /")
                lines.append("/")
            if inj_rows:
                lines.append("WCONINJE")
                for row in inj_rows:
                    well_name = self._well_name(row)
                    opm_name = opm_name_by_well.get(well_name)
                    if not opm_name:
                        continue
                    water = max(0.1, self._number(row.get("q_water_inj")) / 30.0)
                    bhp = max(1.0, self._number(row.get("bhp"), 250.0))
                    lines.append(f" '{opm_name}' 'WATER' 'OPEN' 'RATE' {water:.3f} 1* {bhp:.3f} /")
                lines.append("/")
        lines.extend(["END", ""])
        return "\n".join(lines)

    def _summary_include(self, vectors: list[str], wells: list[dict[str, Any]]) -> str:
        vectors = [str(item).strip().upper() for item in vectors if str(item).strip()] or ["FOPR", "FWPR", "FWIR", "WOPR", "WWPR", "WBHP", "WWCT"]
        lines = ["SUMMARY"]
        for vector in vectors:
            lines.append(vector)
            if vector.startswith("W"):
                for well in wells:
                    lines.append(f" '{well['opm_well_name']}' /")
        lines.append("")
        return "\n".join(lines)

    def _scan_artifacts(self, run: SimulationRun) -> list[SimulationArtifact]:
        artifacts: list[SimulationArtifact] = []
        for directory in (Path(run.input_dir), Path(run.output_dir), Path(run.normalized_dir)):
            if not directory.exists():
                continue
            for path in directory.rglob("*"):
                if path.is_file():
                    artifacts.append(self._artifact(run.run_id, path))
        return artifacts

    def _artifact(self, run_id: str, path: Path) -> SimulationArtifact:
        suffix = path.suffix.lower().lstrip(".") or "file"
        artifact_type = {
            "data": "opm_deck",
            "inc": "opm_include",
            "egrid": "opm_egrid",
            "esmry": "opm_esmry",
            "init": "opm_init",
            "smspec": "opm_smspec",
            "unsmry": "opm_unsmry",
            "unrst": "opm_unrst",
            "prt": "opm_prt",
            "json": "normalized_json",
            "txt": "opm_log",
        }.get(suffix, "simulation_artifact")
        if re.fullmatch(r"x\d+", suffix):
            artifact_type = "opm_restart_segment"
        elif re.fullmatch(r"s\d+", suffix):
            artifact_type = "opm_summary_segment"
        return SimulationArtifact(
            artifact_id=hashlib.sha1(f"{run_id}:{path}".encode("utf-8")).hexdigest(),
            run_id=run_id,
            artifact_type=artifact_type,
            path=str(path),
            format=suffix,
            size_bytes=path.stat().st_size if path.exists() else None,
            checksum=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
            created_at=datetime.utcnow().isoformat(),
        )

    def _opm_output_summary(self, run: SimulationRun) -> dict[str, Any]:
        output_dir = Path(run.output_dir)
        files: list[dict[str, Any]] = []
        if output_dir.exists():
            for path in sorted(output_dir.glob("*")):
                if path.is_file():
                    files.append(
                        {
                            "name": path.name,
                            "extension": path.suffix.upper().lstrip(".") or "TXT",
                            "size_bytes": path.stat().st_size,
                        }
                    )
        available = {item["extension"] for item in files}
        has_restart = "UNRST" in available or any(item.startswith("X") and item[1:].isdigit() for item in available)
        has_summary = (
            "UNSMRY" in available
            or "ESMRY" in available
            or any(item.startswith("S") and item[1:].isdigit() for item in available)
        )
        artifact_families = {
            "grid": "EGRID" in available,
            "initial_state": "INIT" in available or "X0000" in available,
            "restart": has_restart,
            "summary": has_summary,
            "summary_spec": "SMSPEC" in available,
        }
        required_families = sorted(artifact_families)
        missing_families = sorted(name for name, present in artifact_families.items() if not present)
        binary_present = sorted(
            item
            for item in available
            if item in {"EGRID", "INIT", "UNRST", "UNSMRY", "ESMRY", "SMSPEC"}
            or re.fullmatch(r"[XS]\d+", item) is not None
        )
        return {
            "output_dir": str(output_dir),
            "available_extensions": sorted(available),
            "required_artifact_families": required_families,
            "missing_artifact_families": missing_families,
            "binary_present_extensions": binary_present,
            "artifact_families": artifact_families,
            "has_binary_output": all(artifact_families.values()),
            "files": files,
        }

    def _diagnostics(
        self,
        request: Field2DPrepareRequest,
        wells: list[dict[str, Any]],
        regions: list[dict[str, Any]],
        well_regions: list[dict[str, Any]],
        grid: dict[str, Any],
        grid_cells: list[dict[str, Any]],
        perforation_points: list[dict[str, Any]],
    ) -> dict[str, Any]:
        warnings: list[str] = []
        if not wells:
            warnings.append("No wells with coordinates found.")
        if not regions:
            warnings.append("No CRM injector-producer regions built.")
        if not request.pvt_include and request.allow_generated_pvt:
            warnings.append("No scenario-bound PVT include dataset; default OPM PVT/SCAL/ROCK include was generated.")
        props_augmentation = self._props_augmentation_keywords(request)
        if props_augmentation:
            warnings.append(f"Scenario PVT include missed OPM keywords {', '.join(props_augmentation)}; generated defaults were appended.")
        return {
            "well_count": len(wells),
            "producer_count": len([item for item in wells if item["well_type"] == "producer"]),
            "injector_count": len([item for item in wells if item["well_type"] == "injector"]),
            "region_count": len(regions),
            "well_region_count": len(well_regions),
            "grid_cell_count": len(grid_cells),
            "active_grid_cell_count": len([cell for cell in grid_cells if cell.get("actnum") == 1]),
            "grid": {key: grid.get(key) for key in ("nx", "ny", "nz", "dx_m", "dy_m", "dz_m", "padding_m")},
            "perforation_grid_coverage": self._perforation_grid_coverage(grid_cells, perforation_points),
            "init": {
                "initial_pressure_bar": request.initial_pressure_bar,
                "initial_water_saturation": request.initial_water_saturation,
                "initial_gas_saturation": request.initial_gas_saturation,
                "datum_depth_m": request.datum_depth_m,
                "top_depth_m": request.top_depth_m,
            },
            "adaptation": {
                "history_match_iterations": request.history_match_iterations,
                "pressure_tolerance_bar": request.pressure_tolerance_bar,
                "watercut_tolerance_fraction": request.watercut_tolerance_fraction,
                "pressure_weight": request.pressure_weight,
                "watercut_weight": request.watercut_weight,
                "rate_weight": request.rate_weight,
            },
            "geometry": {
                "influence_radius_m": request.influence_radius_m,
                "well_region_radius_m": request.well_region_radius_m,
                "region_corridor_width_m": request.region_corridor_width_m,
                "nearest_producers_per_injector": request.nearest_producers_per_injector,
            },
            "pvt_source": "scenario_pvt_include" if request.pvt_include else "generated_default",
            "props_augmentation": props_augmentation,
            "warnings": warnings,
        }

    def _perforation_grid_coverage(
        self,
        grid_cells: list[dict[str, Any]],
        perforation_points: list[dict[str, Any]],
    ) -> dict[str, Any]:
        cells_by_ij = {(int(cell["i"]), int(cell["j"])): cell for cell in grid_cells}
        total_points = len(perforation_points)
        active_points = 0
        missing_points: list[dict[str, Any]] = []
        wells: set[str] = set()
        active_wells: set[str] = set()
        for point in perforation_points:
            well_name = str(point.get("well_name") or "")
            if well_name:
                wells.add(well_name)
            i = int(point.get("grid_i") or 0)
            j = int(point.get("grid_j") or 0)
            if not i or not j:
                # grid_i/grid_j are added in _perforation_cell_map; fall back to
                # a cell search for older in-memory points.
                match = next((cell for cell in grid_cells if cell.get("perforation_count") and well_name in cell.get("perforation_wells", [])), None)
                if match:
                    i = int(match["i"])
                    j = int(match["j"])
            cell = cells_by_ij.get((i, j))
            if cell and int(cell.get("actnum") or 0) == 1:
                active_points += 1
                if well_name:
                    active_wells.add(well_name)
            else:
                missing_points.append(
                    {
                        "well_name": well_name,
                        "perforation_id": point.get("perforation_id"),
                        "point_type": point.get("point_type"),
                        "md": point.get("md"),
                        "x": point.get("x"),
                        "y": point.get("y"),
                    }
                )
        return {
            "perforation_point_count": total_points,
            "active_perforation_point_count": active_points,
            "perforation_well_count": len(wells),
            "active_perforation_well_count": len(active_wells),
            "all_perforations_in_active_cells": total_points == active_points,
            "missing_points": missing_points[:50],
        }

    def _group_trajectories(self, rows: list[dict[str, Any]]) -> dict[str, list[_TrajectoryPoint]]:
        grouped: dict[str, list[_TrajectoryPoint]] = defaultdict(list)
        for row in rows:
            well_name = self._well_name(row)
            md = self._nullable_number(row.get("md") or row.get("measured_depth") or row.get("measured_depth_m"))
            x = self._nullable_number(row.get("x"))
            y = self._nullable_number(row.get("y"))
            z = self._nullable_number(row.get("z") or row.get("tvd"))
            if not well_name or md is None or x is None or y is None:
                continue
            grouped[well_name].append(_TrajectoryPoint(well_name, md, x, y, z or 0.0))
        for points in grouped.values():
            points.sort(key=lambda item: item.md)
        return grouped

    def _well_group_lookup(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {self._well_name(row): row for row in rows if self._well_name(row)}

    def _perforation_centers(
        self,
        perforations: list[dict[str, Any]],
        trajectory_by_well: dict[str, list[_TrajectoryPoint]],
    ) -> dict[str, tuple[float, float, float]]:
        coords: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
        for row in perforations:
            well_name = self._well_name(row)
            top_md = self._nullable_number(row.get("top_md") or row.get("top") or row.get("md_top"))
            bottom_md = self._nullable_number(row.get("bottom_md") or row.get("bottom") or row.get("md_bottom"))
            if not well_name or top_md is None or bottom_md is None:
                continue
            center_md = (top_md + bottom_md) / 2.0
            xyz = self._interpolate(trajectory_by_well.get(well_name, []), center_md)
            if xyz is not None:
                coords[well_name].append(xyz)
        return {well: self._avg_xyz(items) for well, items in coords.items() if items}

    def _perforation_points(
        self,
        perforations: list[dict[str, Any]],
        trajectory_by_well: dict[str, list[_TrajectoryPoint]],
    ) -> list[dict[str, Any]]:
        points: list[dict[str, Any]] = []
        seen: set[tuple[str, str, float]] = set()
        for row_index, row in enumerate(perforations):
            well_name = self._well_name(row)
            top_md = self._nullable_number(row.get("top_md") or row.get("top") or row.get("md_top"))
            bottom_md = self._nullable_number(row.get("bottom_md") or row.get("bottom") or row.get("md_bottom"))
            explicit_x = self._nullable_number(row.get("x"))
            explicit_y = self._nullable_number(row.get("y"))
            explicit_z = self._nullable_number(row.get("z") or row.get("tvd"))
            if not well_name:
                continue
            perforation_id = str(row.get("perforation_id") or row.get("id") or f"perf:{row_index}")
            md_points: list[tuple[str, float]] = []
            if top_md is not None:
                md_points.append(("top", top_md))
            if top_md is not None and bottom_md is not None:
                md_points.append(("center", (top_md + bottom_md) / 2.0))
            elif top_md is not None or bottom_md is not None:
                md_points.append(("center", top_md if top_md is not None else float(bottom_md or 0.0)))
            if bottom_md is not None:
                md_points.append(("bottom", bottom_md))
            if not md_points and explicit_x is not None and explicit_y is not None:
                md_points.append(("center", 0.0))

            for point_type, md in md_points:
                key = (well_name, point_type, round(float(md), 6))
                if key in seen:
                    continue
                seen.add(key)
                xyz = self._interpolate(trajectory_by_well.get(well_name, []), md)
                if xyz is None and explicit_x is not None and explicit_y is not None:
                    xyz = (explicit_x, explicit_y, explicit_z or 0.0)
                if xyz is None:
                    continue
                points.append(
                    {
                        "well_name": well_name,
                        "perforation_id": perforation_id,
                        "point_type": point_type,
                        "md": round(float(md), 3),
                        "top_md": top_md,
                        "bottom_md": bottom_md,
                        "x": round(float(xyz[0]), 3),
                        "y": round(float(xyz[1]), 3),
                        "z": round(float(xyz[2]), 3),
                    }
                )
        return points

    def _perforation_centers_from_points(self, points: list[dict[str, Any]]) -> dict[str, tuple[float, float, float]]:
        coords: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
        fallback: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
        for point in points:
            well_name = str(point.get("well_name") or "")
            if not well_name:
                continue
            xyz = (float(point["x"]), float(point["y"]), float(point.get("z") or 0.0))
            fallback[well_name].append(xyz)
            if point.get("point_type") == "center":
                coords[well_name].append(xyz)
        centers: dict[str, tuple[float, float, float]] = {}
        for well in sorted(set(coords) | set(fallback)):
            items = coords.get(well) or fallback.get(well, [])
            if items:
                centers[well] = self._avg_xyz(items)
        return centers

    def _perforation_cell_map(
        self,
        grid: dict[str, Any],
        perforation_points: list[dict[str, Any]],
    ) -> dict[tuple[int, int], list[dict[str, Any]]]:
        mapped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        for point in self._with_perforation_grid_indices(grid, perforation_points):
            mapped[(int(point["grid_i"]), int(point["grid_j"]))].append(point)
        return mapped

    def _with_perforation_grid_indices(
        self,
        grid: dict[str, Any],
        perforation_points: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        nx = int(grid["nx"])
        ny = int(grid["ny"])
        min_x = float(grid["min_x"])
        min_y = float(grid["min_y"])
        dx = float(grid["dx_m"])
        dy = float(grid["dy_m"])
        indexed: list[dict[str, Any]] = []
        for point in perforation_points:
            i = min(nx, max(1, int((float(point["x"]) - min_x) / dx) + 1))
            j = min(ny, max(1, int((float(point["y"]) - min_y) / dy) + 1))
            indexed.append({**point, "grid_i": i, "grid_j": j, "grid_k": 1})
        return indexed

    def _trajectory_center(self, points: list[_TrajectoryPoint]) -> tuple[float, float, float] | None:
        if not points:
            return None
        return self._avg_xyz([(point.x, point.y, point.z) for point in points[-5:]])

    def _interpolate(self, points: list[_TrajectoryPoint], md: float) -> tuple[float, float, float] | None:
        if not points:
            return None
        if md <= points[0].md:
            point = points[0]
            return (point.x, point.y, point.z)
        if md >= points[-1].md:
            point = points[-1]
            return (point.x, point.y, point.z)
        for left, right in zip(points, points[1:]):
            if left.md <= md <= right.md:
                span = right.md - left.md
                ratio = 0.0 if span == 0 else (md - left.md) / span
                return (
                    left.x + (right.x - left.x) * ratio,
                    left.y + (right.y - left.y) * ratio,
                    left.z + (right.z - left.z) * ratio,
                )
        return None

    def _region_for_cell(
        self,
        x: float,
        y: float,
        regions: list[dict[str, Any]],
        well_by_name: dict[str, dict[str, Any]],
        corridor_width_m: float,
    ) -> dict[str, Any] | None:
        best: tuple[float, dict[str, Any]] | None = None
        for region in regions:
            injector = well_by_name.get(region["injector_name"])
            producer = well_by_name.get(region["producer_name"])
            if injector is None or producer is None:
                continue
            distance = self._point_segment_distance(x, y, float(injector["x"]), float(injector["y"]), float(producer["x"]), float(producer["y"]))
            if distance <= corridor_width_m and (best is None or distance < best[0]):
                best = (distance, region)
        return best[1] if best else None

    def _well_region_for_cell(self, x: float, y: float, well_regions: list[dict[str, Any]]) -> dict[str, Any] | None:
        best: tuple[float, dict[str, Any]] | None = None
        for region in well_regions:
            distance = math.hypot(x - float(region["x"]), y - float(region["y"]))
            if distance <= float(region["radius_m"]) and (best is None or distance < best[0]):
                best = (distance, region)
        return best[1] if best else None

    def _nearest_well_distance(self, x: float, y: float, wells: list[dict[str, Any]]) -> float:
        if not wells:
            return math.inf
        return min(math.hypot(x - float(well["x"]), y - float(well["y"])) for well in wells)

    def _reserve_lookup(self, rows: list[dict[str, Any]]) -> dict[str, float]:
        result: dict[str, float] = {}
        for row in rows:
            well = self._well_name(row)
            niz = self._nullable_number(row.get("niz") or row.get("NIZ") or row.get("reserves"))
            if well and niz is not None:
                result[well] = niz
        return result

    def _history_by_well_date(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in rows:
            well = self._well_name(row)
            date = self._date_key(row)
            if well and date:
                grouped[well][date] = row
        return grouped

    def _latest_row(self, rows_by_date: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if not rows_by_date:
            return {}
        return rows_by_date[sorted(rows_by_date)[-1]]

    def _first_history_date(self, request: Field2DPrepareRequest) -> str:
        dates = [self._date_key(row) for row in [*request.production_history, *request.injection_history]]
        dates = [date for date in dates if date]
        return min(dates) if dates else "2018-01-01"

    def _cell_values(self, cells: list[dict[str, Any]], key: str, digits: int = 3) -> str:
        if digits == 0:
            return " ".join(str(int(float(cell.get(key) or 0))) for cell in cells)
        return " ".join(f"{float(cell.get(key) or 0):.{digits}f}" for cell in cells)

    def _max_cell_int(self, preparation: Field2DPrepareResponse, key: str, *, default: int = 1) -> int:
        values: list[int] = []
        for cell in preparation.grid.get("cells", []):
            try:
                value = int(float(cell.get(key) or default))
            except (TypeError, ValueError):
                value = default
            values.append(max(default, value))
        return max(values, default=default)

    def _opm_date(self, value: str) -> str:
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        try:
            parsed = datetime.strptime(str(value)[:10], "%Y-%m-%d")
            return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"
        except ValueError:
            return "1 JAN 2018"

    def _point_segment_distance(self, px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        vx = bx - ax
        vy = by - ay
        wx = px - ax
        wy = py - ay
        segment_len2 = vx * vx + vy * vy
        if segment_len2 == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, (wx * vx + wy * vy) / segment_len2))
        projection_x = ax + t * vx
        projection_y = ay + t * vy
        return math.hypot(px - projection_x, py - projection_y)

    def _avg(self, rows: list[dict[str, Any]], key: str) -> float | None:
        values = [self._nullable_number(row.get(key)) for row in rows]
        values = [value for value in values if value is not None]
        return sum(values) / len(values) if values else None

    def _avg_xyz(self, items: list[tuple[float, float, float]]) -> tuple[float, float, float]:
        count = max(1, len(items))
        return (
            sum(item[0] for item in items) / count,
            sum(item[1] for item in items) / count,
            sum(item[2] for item in items) / count,
        )

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

    def _positive_number(self, value: Any) -> float | None:
        number = self._nullable_number(value)
        if number is None or number <= 0:
            return None
        return number

    def _number(self, value: Any, default: float = 0.0) -> float:
        number = self._nullable_number(value)
        return default if number is None else number

    def _clamp(self, value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    def _field_2d_config_snapshot(self, request: Field2DPrepareRequest) -> dict[str, Any]:
        return {
            "dx_m": request.dx_m,
            "dy_m": request.dy_m,
            "dz_m": request.dz_m,
            "porosity": request.porosity,
            "permeability_md": request.permeability_md,
            "formation_volume_factor": request.formation_volume_factor,
            "initial_oil_saturation": request.initial_oil_saturation,
            "initial_pressure_bar": request.initial_pressure_bar,
            "initial_water_saturation": request.initial_water_saturation,
            "initial_gas_saturation": request.initial_gas_saturation,
            "datum_depth_m": request.datum_depth_m,
            "top_depth_m": request.top_depth_m,
            "nearest_producers_per_injector": request.nearest_producers_per_injector,
            "influence_radius_m": request.influence_radius_m,
            "well_region_radius_m": request.well_region_radius_m,
            "region_corridor_width_m": request.region_corridor_width_m,
            "grid_padding_m": request.grid_padding_m,
            "max_grid_cells": request.max_grid_cells,
            "history_match_iterations": request.history_match_iterations,
            "pressure_weight": request.pressure_weight,
            "watercut_weight": request.watercut_weight,
            "rate_weight": request.rate_weight,
            "pressure_tolerance_bar": request.pressure_tolerance_bar,
            "watercut_tolerance_fraction": request.watercut_tolerance_fraction,
            "allow_generated_pvt": request.allow_generated_pvt,
        }

    def _date_key(self, row: dict[str, Any]) -> str:
        return str(row.get("date") or row.get("month") or row.get("period") or "")[:10]

    def _well_name(self, row: dict[str, Any]) -> str:
        return str(row.get("well_name") or row.get("well") or row.get("well_id") or row.get("producer_id") or row.get("injector_id") or "").strip().upper()

    def _text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _pvt_include_text(self, payload: dict[str, Any] | None) -> str:
        if not isinstance(payload, dict):
            return ""
        return str(payload.get("include_text") or payload.get("text") or "").strip()

    def _props_augmentation_keywords(self, request: Field2DPrepareRequest) -> list[str]:
        include_text = self._pvt_include_text(request.pvt_include)
        if not include_text:
            return []
        missing: list[str] = []
        if not self._has_deck_keyword(include_text, "PVTW"):
            missing.append("PVTW")
        if not self._has_any_deck_keyword(include_text, ["PVDO", "PVTO"]):
            missing.append("PVDO")
        if not self._has_any_deck_keyword(include_text, ["PVDG", "PVTG"]):
            missing.append("PVDG")
        if not self._has_deck_keyword(include_text, "ROCK"):
            missing.append("ROCK")
        if not self._has_deck_keyword(include_text, "SWOF"):
            missing.append("SWOF")
        if not self._has_deck_keyword(include_text, "SGOF"):
            missing.append("SGOF")
        return missing

    def _props_augmentation_blocks(
        self,
        include_text: str,
        preparation: Field2DPrepareResponse,
        request: Field2DPrepareRequest,
    ) -> list[str]:
        blocks: list[str] = []
        if not self._has_deck_keyword(include_text, "PVTW"):
            blocks.extend(
                [
                    "-- WorkNotOver generated PVTW: source include did not define water PVT",
                    "PVTW",
                    f" {float(request.initial_pressure_bar):.3f} 1.0 4.0E-5 0.45 0.0 /",
                ]
            )
        if not self._has_any_deck_keyword(include_text, ["PVDO", "PVTO"]):
            blocks.extend(
                [
                    "-- WorkNotOver generated PVDO: source include did not define oil PVT",
                    "PVDO",
                    "  1   1.18  2.8",
                    " 120   1.08  3.4",
                    " 260   0.98  4.2 /",
                ]
            )
        if not self._has_any_deck_keyword(include_text, ["PVDG", "PVTG"]):
            blocks.extend(
                [
                    "-- WorkNotOver generated PVDG: source include did not define gas PVT",
                    "PVDG",
                    "  1   0.0300  0.012",
                    " 120   0.0060  0.018",
                    " 260   0.0030  0.024 /",
                ]
            )
        if not self._has_deck_keyword(include_text, "ROCK"):
            blocks.extend(
                [
                    "-- WorkNotOver generated ROCK: source include did not define rock compressibility",
                    "ROCK",
                    f" {float(request.initial_pressure_bar):.3f} 1.2E-5 /",
                ]
            )
        missing_swof = not self._has_deck_keyword(include_text, "SWOF")
        missing_sgof = not self._has_deck_keyword(include_text, "SGOF")
        if missing_swof or missing_sgof:
            cells = preparation.grid.get("cells", [])
            sat_count = max(1, max((int(cell.get("satnum") or 1) for cell in cells), default=1))
            if missing_swof:
                blocks.extend(["-- WorkNotOver generated SWOF: source include did not define oil-water SCAL", "SWOF"])
                for _ in range(sat_count):
                    blocks.extend(
                        [
                            " 0.18 0.000 1.000 0",
                            " 0.32 0.030 0.640 0",
                            " 0.55 0.280 0.240 0",
                            " 0.85 1.000 0.000 0 /",
                        ]
                    )
            if missing_sgof:
                blocks.extend(["-- WorkNotOver generated SGOF: source include did not define gas-oil SCAL", "SGOF"])
                for _ in range(sat_count):
                    blocks.extend(
                        [
                            " 0.00 0.000 1.000 0",
                            " 0.04 0.010 0.820 0",
                            " 0.20 0.300 0.280 0",
                            " 0.70 1.000 0.000 0 /",
                        ]
                    )
        return blocks

    def _has_deck_keyword(self, text: str, keyword: str) -> bool:
        return re.search(rf"(?mi)^\s*{re.escape(keyword)}\b", text) is not None

    def _has_any_deck_keyword(self, text: str, keywords: list[str]) -> bool:
        return any(self._has_deck_keyword(text, keyword) for keyword in keywords)

    def _first_deck_keyword(self, text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            token = stripped.split()[0].strip("'\"").upper()
            return token
        return ""

    def _safe_case_name(self, value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", str(value)).strip("_")
        return (safe or "FIELD_2D")[:48].upper()
