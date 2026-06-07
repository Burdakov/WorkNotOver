from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.services.opm_flow.case_builder import OpmCaseBuilder
from app.services.opm_flow.importer import OpmResultImporter
from app.services.opm_flow.runner import OpmFlowRunner
from app.services.opm_flow.schemas import OpmCaseBuildRequest, SimulationArtifact, SimulationRun
from app.services.opm_flow.storage import SimulationRunStore


class OpmFlowSimulationService:
    def __init__(
        self,
        *,
        store: SimulationRunStore | None = None,
        case_builder: OpmCaseBuilder | None = None,
        runner: OpmFlowRunner | None = None,
        importer: OpmResultImporter | None = None,
    ) -> None:
        self.store = store or SimulationRunStore()
        self.case_builder = case_builder or OpmCaseBuilder()
        self.runner = runner or OpmFlowRunner()
        self.importer = importer or OpmResultImporter()

    def build_case(self, request: OpmCaseBuildRequest) -> SimulationRun:
        run_id, run_root = self.store.allocate_run_root(request.scenario_id)
        case_name = request.case_name or request.scenario_name or f"scenario_{request.scenario_id[:8]}"
        run = SimulationRun(
            run_id=run_id,
            scenario_id=request.scenario_id,
            case_name=case_name,
            case_root=str(run_root),
            input_dir=str(run_root / "input"),
            output_dir=str(run_root / "output"),
            normalized_dir=str(run_root / "normalized"),
            metadata={"case_build_only": True},
        )
        run.opm_case_manifest = self.case_builder.build(request, run_root)
        run.artifacts = self._case_artifacts(run)
        run.status = "case_built"
        return self.store.save(run)

    def run_case(self, scenario_id: str, run_id: str) -> SimulationRun:
        run = self.store.load(scenario_id, run_id)
        run = self.runner.run(run)
        run.artifacts = self._scan_artifacts(run)
        return self.store.save(run)

    def import_results(self, scenario_id: str, run_id: str) -> SimulationRun:
        run = self.store.load(scenario_id, run_id)
        run.import_result = self.importer.import_results(run)
        if run.import_result.status == "import_ready":
            run.status = "imported"
        elif run.import_result.status == "failed":
            run.status = "failed"
        run.artifacts = self._scan_artifacts(run)
        return self.store.save(run)

    def get_run(self, scenario_id: str, run_id: str) -> SimulationRun:
        return self.store.load(scenario_id, run_id)

    def list_runs(self, scenario_id: str) -> list[SimulationRun]:
        return self.store.list_for_scenario(scenario_id)

    def _case_artifacts(self, run: SimulationRun) -> list[SimulationArtifact]:
        if run.opm_case_manifest is None:
            return []
        paths = [Path(run.opm_case_manifest.deck_path)] + [Path(item) for item in run.opm_case_manifest.include_files]
        return [self._artifact(run.run_id, path, "opm_deck" if path.suffix.upper() == ".DATA" else "opm_include") for path in paths]

    def _scan_artifacts(self, run: SimulationRun) -> list[SimulationArtifact]:
        artifacts = self._case_artifacts(run)
        output_map = {
            ".EGRID": "opm_egrid",
            ".GRID": "opm_egrid",
            ".INIT": "opm_init",
            ".SMSPEC": "opm_smspec",
            ".UNSMRY": "opm_unsmry",
            ".UNRST": "opm_unrst",
            ".RFT": "opm_rft",
            ".PRT": "opm_prt",
            ".LOG": "opm_log",
            ".TXT": "opm_log",
        }
        for directory in (Path(run.output_dir), Path(run.normalized_dir)):
            if not directory.exists():
                continue
            for path in directory.glob("*"):
                if not path.is_file():
                    continue
                artifact_type = output_map.get(path.suffix.upper(), "normalized_parquet" if path.suffix == ".parquet" else "import_report")
                artifacts.append(self._artifact(run.run_id, path, artifact_type))
        return artifacts

    def _artifact(self, run_id: str, path: Path, artifact_type: str) -> SimulationArtifact:
        return SimulationArtifact(
            artifact_id=str(uuid4()),
            run_id=run_id,
            artifact_type=artifact_type,
            path=str(path),
            format=path.suffix.lower().lstrip(".") or "file",
            size_bytes=path.stat().st_size if path.exists() else None,
            checksum=self._sha256(path) if path.exists() else None,
            created_at=datetime.utcnow().isoformat(),
        )

    def _sha256(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
