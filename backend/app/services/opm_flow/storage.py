from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.services.opm_flow.schemas import SimulationRun


DEFAULT_SIMULATION_ROOT = Path("storage") / "simulation_runs"


class SimulationRunStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_SIMULATION_ROOT

    def allocate_run_root(self, scenario_id: str) -> tuple[str, Path]:
        run_id = str(uuid4())
        run_root = self.root / scenario_id / run_id
        for child in ("input", "output", "normalized", "reports"):
            (run_root / child).mkdir(parents=True, exist_ok=True)
        return run_id, run_root

    def save(self, run: SimulationRun) -> SimulationRun:
        path = self._manifest_path(run)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(run.model_dump_json(indent=2), encoding="utf-8")
        return run

    def load(self, scenario_id: str, run_id: str) -> SimulationRun:
        path = self.root / scenario_id / run_id / "run_manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return SimulationRun.model_validate(data)

    def list_for_scenario(self, scenario_id: str) -> list[SimulationRun]:
        scenario_root = self.root / scenario_id
        if not scenario_root.exists():
            return []
        runs: list[SimulationRun] = []
        for manifest in scenario_root.glob("*/run_manifest.json"):
            data = json.loads(manifest.read_text(encoding="utf-8"))
            runs.append(SimulationRun.model_validate(data))
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def _manifest_path(self, run: SimulationRun) -> Path:
        return Path(run.case_root) / "run_manifest.json"
