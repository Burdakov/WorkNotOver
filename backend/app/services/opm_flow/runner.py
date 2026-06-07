from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from app.services.opm_flow.schemas import SimulationRun


class OpmFlowRunner:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or os.getenv("OPM_FLOW_EXECUTABLE") or "flow"

    def is_available(self) -> bool:
        return shutil.which(self.executable) is not None

    def run(self, simulation_run: SimulationRun) -> SimulationRun:
        if simulation_run.opm_case_manifest is None:
            raise ValueError("OPM case manifest is required before running OPM Flow.")
        if not self.is_available():
            simulation_run.status = "failed"
            simulation_run.finished_at = datetime.utcnow().isoformat()
            simulation_run.metadata["runner_error"] = f"OPM Flow executable '{self.executable}' was not found."
            return simulation_run

        output_dir = Path(simulation_run.output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = output_dir / "stdout.txt"
        stderr_path = output_dir / "stderr.txt"
        deck_path = Path(simulation_run.opm_case_manifest.deck_path).resolve()

        simulation_run.status = "running"
        simulation_run.started_at = datetime.utcnow().isoformat()
        simulation_run.metadata["flow_executable"] = self.executable
        simulation_run.metadata["flow_deck_path"] = str(deck_path)
        try:
            with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
                completed = subprocess.run(
                    [self.executable, str(deck_path)],
                    cwd=output_dir,
                    stdout=stdout,
                    stderr=stderr,
                    check=False,
                )
        except OSError as exc:
            simulation_run.finished_at = datetime.utcnow().isoformat()
            simulation_run.status = "failed"
            simulation_run.metadata["runner_error"] = str(exc)
            simulation_run.metadata["stdout_path"] = str(stdout_path)
            simulation_run.metadata["stderr_path"] = str(stderr_path)
            return simulation_run

        simulation_run.finished_at = datetime.utcnow().isoformat()
        simulation_run.status = "completed" if completed.returncode == 0 else "failed"
        simulation_run.metadata["flow_return_code"] = completed.returncode
        simulation_run.metadata["stdout_path"] = str(stdout_path)
        simulation_run.metadata["stderr_path"] = str(stderr_path)
        self._collect_output_files(deck_path, output_dir)
        return simulation_run

    def _collect_output_files(self, deck_path: Path, output_dir: Path) -> None:
        case_prefix = deck_path.with_suffix("").name.upper()
        source_dir = deck_path.parent
        output_suffixes = {
            ".DBG",
            ".EGRID",
            ".ESMRY",
            ".INIT",
            ".PRT",
            ".RFT",
            ".SMSPEC",
            ".UNRST",
            ".UNSMRY",
        }
        for path in source_dir.glob(f"{case_prefix}.*"):
            suffix = path.suffix.upper()
            if suffix in output_suffixes or suffix.startswith(".X") or suffix.startswith(".S"):
                target = output_dir / path.name
                if path.resolve() != target.resolve():
                    shutil.copy2(path, target)
