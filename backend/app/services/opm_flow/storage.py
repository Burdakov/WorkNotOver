from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.services.opm_flow.schemas import SimulationRun


DEFAULT_SIMULATION_ROOT = Path("storage") / "simulation_runs"


class SimulationRunStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_SIMULATION_ROOT

    def allocate_run_root(
        self,
        scenario_id: str,
        *,
        scenario_name: str | None = None,
        run_name: str | None = None,
    ) -> tuple[str, Path]:
        run_id = str(uuid4())
        scenario_folder = self._safe_folder_name(self._repair_mojibake(scenario_name or scenario_id))
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        run_folder = self._safe_folder_name(run_name or "opm-flow-2d")
        run_root = self.root / scenario_folder / f"{timestamp}_{run_folder}_{run_id[:8]}"
        for child in ("input", "output", "normalized", "reports"):
            (run_root / child).mkdir(parents=True, exist_ok=True)
        return run_id, run_root

    def save(self, run: SimulationRun) -> SimulationRun:
        path = self._manifest_path(run)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self._canonical_manifest_data(run.model_dump(mode="json"), path)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return SimulationRun.model_validate(data)

    def load(self, scenario_id: str, run_id: str) -> SimulationRun:
        path = self.root / scenario_id / run_id / "run_manifest.json"
        if not path.exists():
            path = self._find_manifest(scenario_id, run_id)
        return self._load_manifest(path)

    def list_for_scenario(self, scenario_id: str) -> list[SimulationRun]:
        if not self.root.exists():
            return []
        runs: list[SimulationRun] = []
        for manifest in self.root.glob("*/*/run_manifest.json"):
            run = self._load_manifest(manifest)
            if run.scenario_id == scenario_id:
                runs.append(run)
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def _manifest_path(self, run: SimulationRun) -> Path:
        return Path(run.case_root) / "run_manifest.json"

    def _find_manifest(self, scenario_id: str, run_id: str) -> Path:
        if self.root.exists():
            for manifest in self.root.glob("*/*/run_manifest.json"):
                data = json.loads(manifest.read_text(encoding="utf-8"))
                if data.get("scenario_id") == scenario_id and data.get("run_id") == run_id:
                    return manifest
        raise FileNotFoundError(self.root / scenario_id / run_id / "run_manifest.json")

    def _load_manifest(self, path: Path) -> SimulationRun:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SimulationRun.model_validate(self._canonical_manifest_data(data, path))

    def _canonical_manifest_data(self, data: dict, manifest_path: Path) -> dict:
        run_root = manifest_path.parent
        canonical_root = self._path_text(run_root)
        old_root = str(data.get("case_root") or "").replace("\\", "/")
        old_roots = [item for item in [old_root, self._repair_mojibake(old_root)] if item]

        def rewrite(value):
            if isinstance(value, str):
                text = self._repair_mojibake(value).replace("\\", "/")
                for candidate in old_roots:
                    if text == candidate:
                        return canonical_root
                    if text.startswith(f"{candidate}/"):
                        return f"{canonical_root}{text[len(candidate):]}"
                    app_candidate = f"/app/{candidate}"
                    if text == app_candidate:
                        return f"/app/{canonical_root}"
                    if text.startswith(f"{app_candidate}/"):
                        return f"/app/{canonical_root}{text[len(app_candidate):]}"
                return text
            if isinstance(value, list):
                return [rewrite(item) for item in value]
            if isinstance(value, dict):
                return {key: rewrite(item) for key, item in value.items()}
            return value

        data = rewrite(data)
        data["case_root"] = canonical_root
        data["input_dir"] = self._path_text(run_root / "input")
        data["output_dir"] = self._path_text(run_root / "output")
        data["normalized_dir"] = self._path_text(run_root / "normalized")
        return data

    def _path_text(self, path: Path) -> str:
        return path.as_posix()

    def _safe_folder_name(self, value: str) -> str:
        text = str(value or "").strip().lower()
        text = re.sub(r"[^\w.-]+", "-", text, flags=re.UNICODE).strip("-_.")
        text = re.sub(r"-{2,}", "-", text)
        return (text or "scenario")[:96]

    def _repair_mojibake(self, value: str) -> str:
        text = str(value or "")
        for source_encoding in ("cp1251", "latin1", "cp1252"):
            try:
                repaired = text.encode(source_encoding).decode("utf-8")
            except UnicodeError:
                continue
            if self._mojibake_score(repaired) < self._mojibake_score(text):
                return repaired
        return text

    def _mojibake_score(self, value: str) -> int:
        return sum(value.count(marker) for marker in ("Р", "С", "Ð", "Ñ", "Ѓ", "�"))
