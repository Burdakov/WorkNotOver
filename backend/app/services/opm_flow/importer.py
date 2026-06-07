from __future__ import annotations

from pathlib import Path

from app.services.opm_flow.schemas import OpmImportResult, SimulationRun


class OpmResultImporter:
    """Imports OPM/Eclipse artifacts into normalized WorkNotOver outputs.

    The implementation is deliberately dependency-light. When res2df/opm.io is
    installed, this class is the integration point for reading UNSMRY, EGRID,
    INIT, UNRST, RFT and PRT artifacts into parquet/JSON tables.
    """

    def import_results(self, simulation_run: SimulationRun) -> OpmImportResult:
        output_dir = Path(simulation_run.output_dir)
        normalized_dir = Path(simulation_run.normalized_dir)
        normalized_dir.mkdir(parents=True, exist_ok=True)

        warnings: list[str] = []
        if not output_dir.exists():
            return OpmImportResult(
                run_id=simulation_run.run_id,
                status="failed",
                errors=[f"Output directory does not exist: {output_dir}"],
            )

        available = {path.suffix.upper().lstrip(".") for path in output_dir.glob("*") if path.is_file()}
        required_any = {"UNSMRY", "SMSPEC", "UNRST", "EGRID", "INIT"}
        missing = sorted(required_any - available)
        if missing:
            warnings.append(
                "OPM output artifacts are incomplete or not generated yet: " + ", ".join(missing)
            )

        report_path = normalized_dir / "import_report.json"
        result = OpmImportResult(
            run_id=simulation_run.run_id,
            status="pending_external_importer" if missing else "import_ready",
            warnings=warnings,
            metadata={
                "available_extensions": sorted(available),
                "expected_importer": "res2df/opm.io",
            },
        )
        report_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result
