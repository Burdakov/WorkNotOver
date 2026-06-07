from __future__ import annotations

import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.common import ImportValidationReport
from app.schemas.import_models import (
    GtmWellMatchPreviewRequest,
    GtmWellMatchPreviewResponse,
    NizWellCandidateOption,
    NizWellMatchPreviewRequest,
    NizWellMatchPreviewResponse,
    NizWellMatchSuggestionRow,
    NormalizeRequest,
    NormalizeResponse,
    UploadResponse,
    UploadedFileItem,
)
from app.services.importing.excel_utils import (
    EXCEL_EXTENSIONS,
    STORAGE_DIR,
    TEXT_EXTENSIONS,
    columns_info,
    excel_row_number,
    normalize_text,
    preview_records,
    sheet_df,
    stringify,
    text_df,
    text_lines,
)
from app.services.importing.normalizers import (
    normalize_external_krs_schedule,
    normalize_gtm,
    normalize_infrastructure,
    normalize_injection_history,
    normalize_niz,
    normalize_perforations,
    normalize_perforations_text,
    normalize_production_history,
    normalize_well_groups_text,
    normalize_well_trajectories,
    normalize_well_trajectories_text,
    normalize_wells,
    resolve_columns,
    validate_hierarchy,
)

router = APIRouter(prefix="/api", tags=["module-a"])

_SOURCE_KIND_MAPPING_FIELDS = {
    "wells": {
        "well",
        "lu",
        "sloy",
        "well_pad",
        "fund_state",
        "oil_rate",
        "gas_rate",
        "liquid_rate",
        "watercut",
        "gor",
    },
    "well_groups": {
        "well",
        "lu",
        "sloy",
        "well_pad",
        "object_name",
        "object_type",
        "parent_object",
        "group",
    },
    "niz": {
        "well",
        "lu",
        "well_pad",
        "niz",
        "cumulative_oil",
        "cumulative_gas",
    },
    "gtm": {
        "well",
        "lu",
        "sloy",
        "well_pad",
        "gtm_type",
        "start_date",
        "end_date",
        "increment",
        "liquid_increment",
        "gas_increment",
        "gor_change",
    },
    "infrastructure": {
        "area",
        "lu",
        "sloy",
        "well_pad",
        "object_name",
        "object_type",
        "commissioning_date",
        "capacity_oil",
        "capacity_gas",
        "capacity_liquid",
        "capacity_water",
        "connection_well",
        "parent_object",
    },
    "external_krs_schedule": {
        "brigade",
        "area",
        "lu",
        "sloy",
        "well_pad",
        "well",
        "start_date",
        "end_date",
        "planned_work",
        "increment",
        "liquid_increment",
        "gas_increment",
        "gor_change",
    },
    "well_trajectories": {
        "well",
        "md",
        "x",
        "y",
        "z",
        "trajectory_point_id",
    },
    "perforations": {
        "well",
        "lu",
        "sloy",
        "well_pad",
        "top_md",
        "bottom_md",
        "start_date",
        "end_date",
        "perforation_id",
    },
    "production_history": {
        "date",
        "well",
        "producer_id",
        "q_oil",
        "q_water",
        "q_liq",
        "q_gas",
        "oil_rate",
        "liquid_rate",
        "gas_rate",
        "bhp",
        "thp",
        "p_res",
        "wefac",
    },
    "injection_history": {
        "date",
        "well",
        "injector_id",
        "q_water_inj",
        "bhp",
        "whp",
        "thp",
        "p_res",
        "wefac",
    },
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _build_column_mappings(source_kind: str, resolved_columns: dict[str, str | None]) -> dict[str, str]:
    allowed_fields = _SOURCE_KIND_MAPPING_FIELDS.get(source_kind, set())
    return {key: value for key, value in resolved_columns.items() if key in allowed_fields and value}


_WELL_GENERIC_TOKENS = {"скв", "скважина", "скваж", "well", "id", "no", "n"}


def _well_signature(value: str) -> dict[str, str]:
    normalized = normalize_text(value)
    cleaned = re.sub(r"[^0-9a-zа-я]+", " ", normalized)
    tokens = [token for token in cleaned.split() if token and token not in _WELL_GENERIC_TOKENS]
    compact = " ".join(tokens).strip()
    digits = " ".join(re.findall(r"\d+", compact))
    letters = " ".join(re.findall(r"[a-zа-я]+", compact))
    return {"raw": value, "compact": compact, "digits": digits, "letters": letters}


def _candidate_score(source: dict[str, str], candidate: dict[str, str]) -> float:
    if not source["compact"] or not candidate["compact"]:
        return 0.0

    score = 0.0
    if source["compact"] == candidate["compact"]:
        score += 100.0
    ratio = SequenceMatcher(None, source["compact"], candidate["compact"]).ratio()
    score += ratio * 35.0

    if source["digits"] and candidate["digits"]:
        if source["digits"] == candidate["digits"]:
            score += 45.0
        elif source["digits"] in candidate["digits"] or candidate["digits"] in source["digits"]:
            score += 20.0

    if source["letters"] and candidate["letters"]:
        if source["letters"] == candidate["letters"]:
            score += 25.0
        elif source["letters"] in candidate["letters"] or candidate["letters"] in source["letters"]:
            score += 10.0

    return score


def _is_confident_well_match(source: dict[str, str], candidate: dict[str, str]) -> bool:
    source_digits = source.get("digits", "").strip()
    candidate_digits = candidate.get("digits", "").strip()
    source_letters = source.get("letters", "").strip()
    candidate_letters = candidate.get("letters", "").strip()
    if not source_digits or not candidate_digits or not source_letters or not candidate_letters:
        return False
    return source_digits == candidate_digits and source_letters == candidate_letters


def _rank_candidate_wells(source_row: dict[str, str], candidate_wells: list[dict[str, str]], limit: int = 8) -> list[NizWellCandidateOption]:
    source_signature = _well_signature(source_row["well_name"])
    source_lu = normalize_text(source_row.get("lu_id"))
    source_pad = normalize_text(source_row.get("well_pad_id"))
    ranked = []
    seen: set[tuple[str, str, str]] = set()

    same_lu_same_pad = []
    same_lu = []
    rest = []
    for candidate in candidate_wells:
        candidate_name = stringify(candidate.get("well_name"))
        candidate_lu = stringify(candidate.get("lu_id"))
        candidate_pad = stringify(candidate.get("well_pad_id"))
        identity = (candidate_name, candidate_lu, candidate_pad)
        if not candidate_name or identity in seen:
            continue
        seen.add(identity)
        bucket_item = {
            "well_name": candidate_name,
            "lu_id": candidate_lu or None,
            "well_pad_id": candidate_pad or None,
        }
        candidate_lu_norm = normalize_text(candidate_lu)
        candidate_pad_norm = normalize_text(candidate_pad)
        if source_lu and candidate_lu_norm == source_lu and source_pad and candidate_pad_norm == source_pad:
            same_lu_same_pad.append(bucket_item)
        elif source_lu and candidate_lu_norm == source_lu:
            same_lu.append(bucket_item)
        else:
            rest.append(bucket_item)

    search_space = same_lu_same_pad or same_lu or rest
    for candidate in search_space:
        score = _candidate_score(source_signature, _well_signature(candidate["well_name"]))
        if source_lu and normalize_text(candidate.get("lu_id")) == source_lu:
            score += 15.0
        if source_pad and normalize_text(candidate.get("well_pad_id")) == source_pad:
            score += 20.0
        if score <= 0:
            continue
        ranked.append((score, candidate))
    ranked.sort(key=lambda item: (-item[0], item[1]["well_name"]))
    return [NizWellCandidateOption(**item) for _, item in ranked[:limit]]


def _dedupe_candidate_wells(candidate_wells: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidate_wells:
        well_name = stringify(candidate.get("well_name"))
        lu_id = stringify(candidate.get("lu_id"))
        well_pad_id = stringify(candidate.get("well_pad_id"))
        key = (lu_id, well_pad_id, well_name)
        if not well_name or key in seen:
            continue
        seen.add(key)
        deduped.append(
            {
                "well_name": well_name,
                "lu_id": lu_id or None,
                "well_pad_id": well_pad_id or None,
            }
        )
    return deduped


def _build_well_match_rows(df, resolved_columns, candidate_wells: list[dict[str, str]]) -> list[NizWellMatchSuggestionRow]:
    rows: list[NizWellMatchSuggestionRow] = []
    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        source_well_name = stringify(row.get(resolved_columns.well))
        source_lu_id = stringify(row.get(resolved_columns.lu)) if resolved_columns.lu else ""
        source_well_pad_id = stringify(row.get(resolved_columns.well_pad)) if resolved_columns.well_pad else ""
        if not source_well_name:
            continue
        candidates = _rank_candidate_wells(
            {
                "well_name": source_well_name,
                "lu_id": source_lu_id,
                "well_pad_id": source_well_pad_id,
            },
            candidate_wells,
        )
        best_match = None
        if candidates:
            source_signature = _well_signature(source_well_name)
            top_candidate_signature = _well_signature(candidates[0].well_name)
            if _is_confident_well_match(source_signature, top_candidate_signature):
                best_match = candidates[0].well_name
        rows.append(
            NizWellMatchSuggestionRow(
                row_number=row_number,
                source_well_name=source_well_name,
                source_lu_id=source_lu_id or None,
                source_well_pad_id=source_well_pad_id or None,
                matched_well_name=best_match,
                candidates=candidates,
            )
        )
    return rows


@router.post("/files/upload", response_model=UploadResponse)
def upload_excel(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    extension = Path(file.filename or "source.xlsx").suffix.lower()
    if extension not in EXCEL_EXTENSIONS | TEXT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Supported source files: .xlsx, .xls, .xlsm, .txt.")

    file_id = f"{uuid4()}{extension}"
    stored_path = STORAGE_DIR / file_id
    with stored_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if extension in TEXT_EXTENSIONS:
        sheets, selected_sheet, df = text_df(stored_path)
    else:
        sheets, selected_sheet, df = sheet_df(stored_path, None)
    DatasetRepository(db).upsert_uploaded_file(file_id, file.filename or file_id, str(stored_path), sheets)

    return UploadResponse(
        file_id=file_id,
        original_name=file.filename or file_id,
        sheets=sheets,
        selected_sheet=selected_sheet,
        preview=preview_records(df),
        columns_info=columns_info(df),
    )


@router.get("/files", response_model=list[UploadedFileItem])
def list_files(db: Session = Depends(get_db)) -> list[UploadedFileItem]:
    return [
        UploadedFileItem(file_id=item.file_id, original_name=item.original_name, sheets=item.sheets_json or [])
        for item in DatasetRepository(db).list_uploaded_files()
    ]


@router.get("/files/{file_id}", response_model=UploadResponse)
def get_file_details(file_id: str, sheet_name: str | None = None, db: Session = Depends(get_db)) -> UploadResponse:
    uploaded = next((item for item in DatasetRepository(db).list_uploaded_files() if item.file_id == file_id), None)
    if uploaded is None:
        raise HTTPException(status_code=404, detail="Р¤Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ.")

    file_path = Path(uploaded.stored_path)
    if file_path.suffix.lower() in TEXT_EXTENSIONS:
        sheets, selected_sheet, df = text_df(file_path)
    else:
        sheets, selected_sheet, df = sheet_df(file_path, sheet_name)
    return UploadResponse(
        file_id=uploaded.file_id,
        original_name=uploaded.original_name,
        sheets=sheets,
        selected_sheet=selected_sheet,
        preview=preview_records(df),
        columns_info=columns_info(df),
    )


@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db)) -> list[dict]:
    items = DatasetRepository(db).list_datasets()
    return [
        {
            "dataset_reference": {
                "dataset_id": dataset.dataset_id,
                "dataset_version_id": version.dataset_version_id if version else None,
                "dataset_type": dataset.dataset_type,
                "name": dataset.name,
                "row_count": version.row_count if version else None,
                "created_at": dataset.created_at.isoformat(),
                "metadata": dataset.metadata_json,
            },
            "source_format": dataset.source_format,
            "source_file_name": dataset.source_file_name,
            "status": dataset.status,
            "validation_report": version.validation_report_json if version else None,
        }
        for dataset, version in items
    ]


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, dataset_version_id: str | None = None, db: Session = Depends(get_db)) -> dict:
    resolved = DatasetRepository(db).get_dataset_version(dataset_id, dataset_version_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Dataset РЅРµ РЅР°Р№РґРµРЅ.")

    dataset, version = resolved
    return {
        "dataset_reference": {
            "dataset_id": dataset.dataset_id,
            "dataset_version_id": version.dataset_version_id,
            "dataset_type": dataset.dataset_type,
            "name": dataset.name,
            "row_count": version.row_count,
            "created_at": dataset.created_at.isoformat(),
            "metadata": dataset.metadata_json,
        },
        "source_format": dataset.source_format,
        "source_file_name": dataset.source_file_name,
        "status": dataset.status,
        "validation_report": version.validation_report_json,
        "normalized_payload": version.normalized_payload_json,
    }


@router.post("/import/niz-well-matches", response_model=NizWellMatchPreviewResponse)
def preview_niz_well_matches(payload: NizWellMatchPreviewRequest, db: Session = Depends(get_db)) -> NizWellMatchPreviewResponse:
    repo = DatasetRepository(db)
    uploaded = next((item for item in repo.list_uploaded_files() if item.file_id == payload.file_id), None)
    if uploaded is None:
        raise HTTPException(status_code=404, detail="Р¤Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ.")

    file_path = Path(uploaded.stored_path)
    _, selected_sheet, df = sheet_df(file_path, payload.sheet_name)

    try:
        resolved_columns = resolve_columns(df, payload.columns, "niz")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    candidate_wells = _dedupe_candidate_wells([
        {
            "well_name": stringify(item.well_name),
            "lu_id": stringify(item.lu_id),
            "well_pad_id": stringify(item.well_pad_id),
        }
        for item in payload.candidate_wells
        if stringify(item.well_name)
    ])
    rows = _build_well_match_rows(df, resolved_columns, candidate_wells)
    return NizWellMatchPreviewResponse(rows=rows)


@router.post("/import/gtm-well-matches", response_model=GtmWellMatchPreviewResponse)
def preview_gtm_well_matches(payload: GtmWellMatchPreviewRequest, db: Session = Depends(get_db)) -> GtmWellMatchPreviewResponse:
    repo = DatasetRepository(db)
    uploaded = next((item for item in repo.list_uploaded_files() if item.file_id == payload.file_id), None)
    if uploaded is None:
        raise HTTPException(status_code=404, detail="Р¤Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ.")

    file_path = Path(uploaded.stored_path)
    _, selected_sheet, df = sheet_df(file_path, payload.sheet_name)

    try:
        resolved_columns = resolve_columns(df, payload.columns, "gtm")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    candidate_wells = _dedupe_candidate_wells([
        {
            "well_name": stringify(item.well_name),
            "lu_id": stringify(item.lu_id),
            "well_pad_id": stringify(item.well_pad_id),
        }
        for item in payload.candidate_wells
        if stringify(item.well_name)
    ])
    rows = _build_well_match_rows(df, resolved_columns, candidate_wells)
    return GtmWellMatchPreviewResponse(rows=rows)


@router.post("/import/normalize", response_model=NormalizeResponse)
def normalize_dataset(payload: NormalizeRequest, db: Session = Depends(get_db)) -> NormalizeResponse:
    repo = DatasetRepository(db)
    uploaded = next((item for item in repo.list_uploaded_files() if item.file_id == payload.file_id), None)
    if uploaded is None:
        raise HTTPException(status_code=404, detail="Р¤Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ.")

    file_path = Path(uploaded.stored_path)
    if file_path.suffix.lower() in TEXT_EXTENSIONS:
        selected_sheet = "text"
        report = ImportValidationReport(
            source_kind=payload.source_kind,
            file_id=payload.file_id,
            original_name=uploaded.original_name,
            sheet_name=selected_sheet,
            column_mappings={},
        )
        lines = text_lines(file_path)
        if payload.source_kind == "well_groups":
            normalized_payload = normalize_well_groups_text(lines, report)
        elif payload.source_kind == "well_trajectories":
            normalized_payload = normalize_well_trajectories_text(lines, report)
        elif payload.source_kind == "perforations":
            normalized_payload = normalize_perforations_text(lines, report)
        else:
            raise HTTPException(status_code=400, detail=f"Text import is not supported for source_kind '{payload.source_kind}'.")

        try:
            dataset_reference = repo.create_dataset_version(
                dataset_type=payload.source_kind,
                name=payload.dataset_name or f"{payload.source_kind}:{uploaded.original_name}",
                source_format=file_path.suffix.lstrip("."),
                source_file_name=uploaded.original_name,
                normalized_payload=normalized_payload,
                validation_report=report.model_dump(),
                row_count=report.row_count,
                metadata={"sheet_name": selected_sheet, "text_import": True},
                dataset_id=payload.dataset_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return NormalizeResponse(
            dataset_reference=dataset_reference,
            validation_report=report,
            normalized_payload=normalized_payload,
        )

    _, selected_sheet, df = sheet_df(file_path, payload.sheet_name)

    try:
        resolved_columns = resolve_columns(df, payload.columns, payload.source_kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    report = ImportValidationReport(
        source_kind=payload.source_kind,
        file_id=payload.file_id,
        original_name=uploaded.original_name,
        sheet_name=selected_sheet,
        column_mappings=_build_column_mappings(payload.source_kind, resolved_columns.model_dump()),
    )

    if payload.source_kind == "wells":
        normalized_payload = normalize_wells(df, resolved_columns, report)
        validate_hierarchy(normalized_payload, report)
    elif payload.source_kind == "well_groups":
        normalized_payload = normalize_wells(df, resolved_columns, report)
        validate_hierarchy(normalized_payload, report)
    elif payload.source_kind == "niz":
        niz_row_matches = {
            item.row_number: item.matched_well_name
            for item in payload.niz_well_matches
            if item.matched_well_name
        }
        normalized_payload = normalize_niz(
            df,
            resolved_columns,
            report,
            row_matches=niz_row_matches,
            manual_entries=[item.model_dump() for item in payload.manual_niz_entries],
        )
    elif payload.source_kind == "gtm":
        gtm_row_matches = {
            item.row_number: item.matched_well_name
            for item in payload.gtm_well_matches
            if item.matched_well_name
        }
        normalized_payload = normalize_gtm(df, resolved_columns, report, row_matches=gtm_row_matches)
        validate_hierarchy(normalized_payload, report)
    elif payload.source_kind == "infrastructure":
        normalized_payload = normalize_infrastructure(df, resolved_columns, report)
    elif payload.source_kind == "well_trajectories":
        normalized_payload = normalize_well_trajectories(df, resolved_columns, report)
    elif payload.source_kind == "perforations":
        normalized_payload = normalize_perforations(df, resolved_columns, report)
    elif payload.source_kind == "production_history":
        normalized_payload = normalize_production_history(df, resolved_columns, report)
    elif payload.source_kind == "injection_history":
        normalized_payload = normalize_injection_history(df, resolved_columns, report)
    elif payload.source_kind == "external_krs_schedule":
        normalized_payload = normalize_external_krs_schedule(df, resolved_columns, report)
    else:
        raise HTTPException(status_code=400, detail="РќРµРїРѕРґРґРµСЂР¶РёРІР°РµРјС‹Р№ source_kind.")

    try:
        dataset_reference = repo.create_dataset_version(
            dataset_type=payload.source_kind,
            name=payload.dataset_name or f"{payload.source_kind}:{uploaded.original_name}",
            source_format=file_path.suffix.lstrip("."),
            source_file_name=uploaded.original_name,
            normalized_payload=normalized_payload,
            validation_report=report.model_dump(),
            row_count=report.row_count,
            metadata={"sheet_name": selected_sheet},
            dataset_id=payload.dataset_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.source_kind == "external_krs_schedule" and isinstance(normalized_payload, dict):
        normalized_payload["dataset_reference"] = dataset_reference.model_dump()
        normalized_payload["source_format"] = file_path.suffix.lstrip(".")
        normalized_payload["source_file_name"] = uploaded.original_name

    return NormalizeResponse(
        dataset_reference=dataset_reference,
        validation_report=report,
        normalized_payload=normalized_payload,
    )

