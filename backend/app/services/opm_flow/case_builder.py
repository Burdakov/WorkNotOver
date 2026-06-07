from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.opm_flow.schemas import OpmCaseBuildRequest, OpmCaseManifest


DEFAULT_SUMMARY_VECTORS = [
    "FOPR",
    "FOPT",
    "FWPR",
    "FWPT",
    "FGPR",
    "FGPT",
    "FWIR",
    "FWIT",
    "WOPR",
    "WWPR",
    "WGPR",
    "WLPR",
    "WBHP",
    "WWCT",
    "WGOR",
]


class OpmCaseBuilder:
    """Builds an OPM/Eclipse case skeleton from normalized scenario context.

    This first implementation intentionally creates explicit include files and a
    manifest, but leaves domain-heavy deck population behind typed extension
    points. It makes the new architecture executable without preserving the old
    decline math as the production path.
    """

    def build(self, request: OpmCaseBuildRequest, run_root: Path) -> OpmCaseManifest:
        case_name = self._case_name(request)
        input_dir = run_root / "input"
        include_dir = input_dir / "includes"
        include_dir.mkdir(parents=True, exist_ok=True)

        template_tables = request.model_config_payload.get("synthetic_template_tables")
        include_files = (
            self._synthetic_include_files(request, template_tables)
            if isinstance(template_tables, dict)
            else {
                "runspec.inc": self._runspec(request),
                "grid.inc": self._placeholder("GRID", "Grid/cell geometry must come from Module A normalized development cells."),
                "props.inc": self._placeholder("PROPS", "PVT/SCAL/ROCK properties must come from ReservoirPropertyDataset."),
                "regions.inc": self._placeholder("REGIONS", "PVTNUM/SATNUM/ROCKNUM/FIPNUM maps must come from RegionMap."),
                "solution.inc": self._placeholder("SOLUTION", "Initial pressure/saturations/equilibration must come from normalized inputs."),
                "schedule.inc": self._placeholder("SCHEDULE", "WELSPECS/COMPDAT/WCONPROD/WCONINJE must come from scenario schedule source."),
                "summary.inc": self._summary(request),
            }
        )

        include_paths: list[str] = []
        for file_name, text in include_files.items():
            path = include_dir / file_name
            path.write_text(text, encoding="utf-8")
            include_paths.append(str(path))

        deck_path = input_dir / f"{case_name}.DATA"
        deck_path.write_text(self._deck(case_name), encoding="utf-8")

        deck_hash = self._sha256(deck_path)
        bindings_hash = hashlib.sha256(
            json.dumps(request.input_bindings, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        return OpmCaseManifest(
            case_name=case_name,
            deck_path=str(deck_path),
            include_files=include_paths,
            sections=["RUNSPEC", "GRID", "PROPS", "REGIONS", "SOLUTION", "SCHEDULE", "SUMMARY"],
            summary_vectors=self._summary_vectors(request),
            input_bindings_hash=bindings_hash,
            deck_hash=deck_hash,
            validation_warnings=[] if isinstance(template_tables, dict) else [
                "Generated OPM case is a structural skeleton. Domain include population is the next implementation step."
            ],
            metadata={
                "scenario_name": request.scenario_name,
                "forecast_start_date": request.forecast_start_date,
                "forecast_end_date": request.forecast_end_date,
                "synthetic_template_deck": isinstance(template_tables, dict),
            },
        )

    def _deck(self, case_name: str) -> str:
        return "\n".join(
            [
                f"-- WorkNotOver OPM Flow case: {case_name}",
                "INCLUDE",
                " 'includes/runspec.inc' /",
                "INCLUDE",
                " 'includes/grid.inc' /",
                "INCLUDE",
                " 'includes/props.inc' /",
                "INCLUDE",
                " 'includes/regions.inc' /",
                "INCLUDE",
                " 'includes/solution.inc' /",
                "INCLUDE",
                " 'includes/schedule.inc' /",
                "INCLUDE",
                " 'includes/summary.inc' /",
                "",
            ]
        )

    def _runspec(self, request: OpmCaseBuildRequest) -> str:
        title = request.scenario_name or request.scenario_id
        return "\n".join(
            [
                "RUNSPEC",
                "TITLE",
                f" WorkNotOver scenario {title}",
                "/",
                "OIL",
                "WATER",
                "GAS",
                "METRIC",
                "",
            ]
        )

    def _summary(self, request: OpmCaseBuildRequest) -> str:
        lines = ["SUMMARY"]
        for vector in self._summary_vectors(request):
            lines.append(vector)
        lines.append("")
        return "\n".join(lines)

    def _synthetic_include_files(self, request: OpmCaseBuildRequest, tables: dict[str, Any]) -> dict[str, str]:
        cells = [self._numeric_row(item) for item in tables.get("cells", [])]
        wells = [self._numeric_row(item) for item in tables.get("wells", [])]
        production = [self._numeric_row(item) for item in tables.get("production", [])]
        injection = [self._numeric_row(item) for item in tables.get("injection", [])]
        cell_index = {str(cell.get("cell_id")): index + 1 for index, cell in enumerate(cells)}
        return {
            "runspec.inc": self._synthetic_runspec(request, cells),
            "grid.inc": self._synthetic_grid(cells),
            "props.inc": self._synthetic_props(),
            "regions.inc": self._synthetic_regions(cells),
            "solution.inc": self._synthetic_solution(cells),
            "schedule.inc": self._synthetic_schedule(request, wells, production, injection, cell_index),
            "summary.inc": self._synthetic_summary(request, wells),
        }

    def _synthetic_runspec(self, request: OpmCaseBuildRequest, cells: list[dict[str, Any]]) -> str:
        title = request.scenario_name or request.scenario_id
        start = self._opm_date(request.forecast_start_date or "2018-01-01")
        return "\n".join(
            [
                "RUNSPEC",
                "TITLE",
                f" WorkNotOver synthetic OPM case {title}",
                "/",
                "DIMENS",
                f" {max(1, len(cells))} 1 1 /",
                "OIL",
                "WATER",
                "GAS",
                "METRIC",
                "START",
                f" {start} /",
                "WELLDIMS",
                " 20 20 20 20 /",
                "",
            ]
        )

    def _synthetic_grid(self, cells: list[dict[str, Any]]) -> str:
        count = max(1, len(cells))
        dx = [max(100.0, math.sqrt(float(cell.get("area") or 1_000_000.0))) for cell in cells] or [1000.0]
        dy = dx
        dz = [max(1.0, float(cell.get("h") or 10.0)) for cell in cells] or [10.0]
        poro = [min(0.35, max(0.05, float(cell.get("phi") or 0.2))) for cell in cells] or [0.2]
        permx = [max(10.0, 60.0 + value * 800.0) for value in poro]
        permy = permx
        permz = [max(1.0, value * 0.1) for value in permx]
        return "\n".join(
            [
                "GRID",
                "DX",
                f" {self._values(dx)} /",
                "DY",
                f" {self._values(dy)} /",
                "DZ",
                f" {self._values(dz)} /",
                "TOPS",
                f" {self._values([2000.0] * count)} /",
                "PORO",
                f" {self._values(poro, 5)} /",
                "PERMX",
                f" {self._values(permx)} /",
                "PERMY",
                f" {self._values(permy)} /",
                "PERMZ",
                f" {self._values(permz)} /",
                "ACTNUM",
                f" {count}*1 /",
                "",
            ]
        )

    def _synthetic_props(self) -> str:
        return "\n".join(
            [
                "PROPS",
                "DENSITY",
                " 820 1010 1.25 /",
                "PVTW",
                " 220 1.0 4.0E-5 0.45 0.0 /",
                "PVDO",
                "  1   1.18  2.8",
                " 120   1.08  3.4",
                " 260   0.98  4.2 /",
                "PVDG",
                "  1   0.0300  0.012",
                " 120   0.0060  0.018",
                " 260   0.0030  0.024 /",
                "ROCK",
                " 220 1.2E-5 /",
                "SWOF",
                " 0.18 0.000 1.000 0",
                " 0.32 0.030 0.640 0",
                " 0.55 0.280 0.240 0",
                " 0.85 1.000 0.000 0 /",
                "SGOF",
                " 0.00 0.000 1.000 0",
                " 0.04 0.010 0.820 0",
                " 0.20 0.300 0.280 0",
                " 0.70 1.000 0.000 0 /",
                "",
            ]
        )

    def _synthetic_regions(self, cells: list[dict[str, Any]]) -> str:
        count = max(1, len(cells))
        fipnum = list(range(1, count + 1))
        return "\n".join(
            [
                "REGIONS",
                "PVTNUM",
                f" {count}*1 /",
                "SATNUM",
                f" {count}*1 /",
                "ROCKNUM",
                f" {count}*1 /",
                "FIPNUM",
                f" {self._values(fipnum, 0)} /",
                "",
            ]
        )

    def _synthetic_solution(self, cells: list[dict[str, Any]]) -> str:
        pressure = [float(cell.get("initial_pressure") or 220.0) for cell in cells] or [220.0]
        swat = [min(0.9, max(0.05, float(cell.get("sw") or 0.3))) for cell in cells] or [0.3]
        sgas = [min(0.7, max(0.0, float(cell.get("sg") or 0.04))) for cell in cells] or [0.04]
        return "\n".join(
            [
                "SOLUTION",
                "PRESSURE",
                f" {self._values(pressure)} /",
                "SWAT",
                f" {self._values(swat, 5)} /",
                "SGAS",
                f" {self._values(sgas, 5)} /",
                "",
            ]
        )

    def _synthetic_schedule(
        self,
        request: OpmCaseBuildRequest,
        wells: list[dict[str, Any]],
        production: list[dict[str, Any]],
        injection: list[dict[str, Any]],
        cell_index: dict[str, int],
    ) -> str:
        lines = ["SCHEDULE", "RPTRST", " BASIC=2 FREQ=1 /", "RPTSCHED", " RESTART=2 /", "WELSPECS"]
        for well in wells:
            phase = "WATER" if well.get("well_type") == "injector" else "OIL"
            i = cell_index.get(str(well.get("cell_id")), 1)
            lines.append(f" '{well['well_id']}' 'FIELD' {i} 1 1* {phase} /")
        lines.extend(["/", "COMPDAT"])
        for well in wells:
            i = cell_index.get(str(well.get("cell_id")), 1)
            lines.append(f" '{well['well_id']}' {i} 1 1 1 'OPEN' 1* 0.20 /")
        lines.append("/")

        production_by_date = self._rows_by_date(production)
        injection_by_date = self._rows_by_date(injection)
        dates = sorted(set(production_by_date) | set(injection_by_date))
        for index, date in enumerate(dates):
            if index > 0:
                lines.extend(["DATES", f" {self._opm_date(date)} /", "/"])
            self._append_controls(lines, production_by_date.get(date, []), injection_by_date.get(date, []))

        end_date = request.forecast_end_date
        if end_date and (not dates or end_date > dates[-1]):
            lines.extend(["DATES", f" {self._opm_date(end_date)} /", "/"])
        lines.append("END")
        lines.append("")
        return "\n".join(lines)

    def _append_controls(self, lines: list[str], production_rows: list[dict[str, Any]], injection_rows: list[dict[str, Any]]) -> None:
        if production_rows:
            lines.append("WCONPROD")
            for row in production_rows:
                well_id = self._well_id(row)
                oil = float(row.get("q_oil") or 0.0)
                bhp = float(row.get("bhp") or 150.0)
                lines.append(f" '{well_id}' 'OPEN' 'ORAT' {oil:.3f} 4* {bhp:.3f} /")
            lines.append("/")
        if injection_rows:
            lines.append("WCONINJE")
            for row in injection_rows:
                well_id = self._well_id(row)
                water = float(row.get("q_water_inj") or 0.0)
                bhp = float(row.get("bhp") or 250.0)
                lines.append(f" '{well_id}' 'WATER' 'OPEN' 'RATE' {water:.3f} 1* {bhp:.3f} /")
            lines.append("/")

    def _synthetic_summary(self, request: OpmCaseBuildRequest, wells: list[dict[str, Any]]) -> str:
        lines = ["SUMMARY"]
        field_vectors = [vector for vector in self._summary_vectors(request) if vector.startswith("F")]
        well_vectors = [vector for vector in self._summary_vectors(request) if vector.startswith("W")]
        for vector in field_vectors:
            lines.append(vector)
        for vector in well_vectors:
            lines.append(vector)
            for well in wells:
                lines.append(f" '{well['well_id']}' /")
        lines.append("")
        return "\n".join(lines)

    def _numeric_row(self, row: dict[str, Any]) -> dict[str, Any]:
        result = dict(row)
        for key, value in row.items():
            if isinstance(value, str) and value.strip():
                try:
                    result[key] = float(value)
                    if result[key].is_integer():
                        result[key] = int(result[key])
                except ValueError:
                    pass
        return result

    def _rows_by_date(self, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row.get("date") or "2018-01-01"), []).append(row)
        return grouped

    def _well_id(self, row: dict[str, Any]) -> str:
        return str(row.get("well_id") or row.get("producer_id") or row.get("injector_id") or "").strip()

    def _opm_date(self, value: str) -> str:
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        try:
            parsed = datetime.strptime(str(value)[:10], "%Y-%m-%d")
            return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"
        except ValueError:
            return "1 JAN 2018"

    def _values(self, values: list[float | int], digits: int = 3) -> str:
        if digits == 0:
            return " ".join(str(int(value)) for value in values)
        return " ".join(f"{float(value):.{digits}f}" for value in values)

    def _summary_vectors(self, request: OpmCaseBuildRequest) -> list[str]:
        configured = request.model_config_payload.get("summary_vectors")
        if isinstance(configured, list) and configured:
            return [str(item).strip().upper() for item in configured if str(item).strip()]
        return DEFAULT_SUMMARY_VECTORS

    def _placeholder(self, section: str, note: str) -> str:
        return "\n".join([section, f"-- TODO: {note}", ""])

    def _case_name(self, request: OpmCaseBuildRequest) -> str:
        source = request.case_name or request.scenario_name or request.scenario_id
        normalized = re.sub(r"[^A-Za-z0-9_]+", "_", source).strip("_")
        return normalized[:48] or f"SCENARIO_{request.scenario_id[:8]}"

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
