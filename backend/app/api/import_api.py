from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.common import ImportValidationReport
from app.schemas.import_models import NormalizeRequest, NormalizeResponse, UploadResponse, UploadedFileItem
from app.services.importing.excel_utils import STORAGE_DIR, columns_info, preview_records, sheet_df
from app.services.importing.normalizers import (
    normalize_external_krs_schedule,
    normalize_gtm,
    normalize_infrastructure,
    normalize_wells,
    resolve_columns,
    validate_hierarchy,
)

router = APIRouter(prefix="/api", tags=["import"])

_SOURCE_KIND_MAPPING_FIELDS = {
    "wells": {
        "well",
        "area",
        "lu",
        "sloy",
        "well_pad",
        "fund_type",
        "oil_rate",
        "gas_rate",
        "liquid_rate",
        "watercut",
        "gor",
        "cumulative_oil",
        "cumulative_gas",
        "niz",
    },
    "gtm": {
        "well",
        "area",
        "lu",
        "sloy",
        "well_pad",
        "planned_work",
        "gtm_type",
        "start_date",
        "end_date",
        "duration_days",
        "increment",
        "liquid_increment",
        "gas_increment",
        "gor_change",
    },
    "infrastructure": {
        "object_name",
        "object_type",
        "commissioning_date",
        "capacity_oil",
        "capacity_gas",
        "capacity_liquid",
        "capacity_water",
        "connection_well",
        "parent_object",
        "area",
        "lu",
        "sloy",
        "well_pad",
    },
    "external_krs_schedule": {
        "brigade",
        "well",
        "area",
        "lu",
        "sloy",
        "well_pad",
        "start_date",
        "end_date",
        "planned_work",
        "increment",
        "liquid_increment",
        "gas_increment",
        "gor_change",
    },
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_column_mappings(source_kind: str, resolved_columns: dict[str, str | None]) -> dict[str, str]:
    allowed_fields = _SOURCE_KIND_MAPPING_FIELDS.get(source_kind, set())
    return {
        key: value
        for key, value in resolved_columns.items()
        if key in allowed_fields and value
    }


@router.post("/files/upload", response_model=UploadResponse)
def upload_excel(file: UploadFile = File(...), db: Session = Depends(get_db)) -> UploadResponse:
    extension = Path(file.filename or "source.xlsx").suffix.lower()
    if extension not in {".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы Excel .xlsx и .xls.")

    file_id = f"{uuid4()}{extension}"
    path = STORAGE_DIR / file_id
    with path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    sheets, selected_sheet, df = sheet_df(path, None)
    DatasetRepository(db).upsert_uploaded_file(file_id, file.filename or file_id, str(path), sheets)

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
    items = DatasetRepository(db).list_uploaded_files()
    return [
        UploadedFileItem(file_id=item.file_id, original_name=item.original_name, sheets=item.sheets_json or [])
        for item in items
    ]


@router.get("/files/{file_id}", response_model=UploadResponse)
def file_details(file_id: str, sheet_name: str | None = None, db: Session = Depends(get_db)) -> UploadResponse:
    item = next((entry for entry in DatasetRepository(db).list_uploaded_files() if entry.file_id == file_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Файл не найден.")
    path = Path(item.stored_path)
    sheets, selected_sheet, df = sheet_df(path, sheet_name)
    return UploadResponse(
        file_id=file_id,
        original_name=item.original_name,
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
def dataset_details(dataset_id: str, dataset_version_id: str | None = None, db: Session = Depends(get_db)) -> dict:
    resolved = DatasetRepository(db).get_dataset_version(dataset_id, dataset_version_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Dataset не найден.")
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


@router.post("/import/normalize", response_model=NormalizeResponse)
def normalize_dataset(payload: NormalizeRequest, db: Session = Depends(get_db)) -> NormalizeResponse:
    repo = DatasetRepository(db)
    uploaded = next((entry for entry in repo.list_uploaded_files() if entry.file_id == payload.file_id), None)
    if uploaded is None:
        raise HTTPException(status_code=404, detail="Файл не найден.")

    path = Path(uploaded.stored_path)
    _, selected_sheet, df = sheet_df(path, payload.sheet_name)
    try:
        resolved = resolve_columns(df, payload.columns, payload.source_kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    report = ImportValidationReport(
        source_kind=payload.source_kind,
        file_id=payload.file_id,
        original_name=uploaded.original_name,
        sheet_name=selected_sheet,
        column_mappings=build_column_mappings(payload.source_kind, resolved.model_dump()),
    )

    if payload.source_kind == "wells":
        normalized_payload = normalize_wells(df, resolved, report)
        validate_hierarchy(normalized_payload, report)
    elif payload.source_kind == "gtm":
        normalized_payload = normalize_gtm(df, resolved, report)
        validate_hierarchy(normalized_payload, report)
    elif payload.source_kind == "infrastructure":
        normalized_payload = normalize_infrastructure(df, resolved, report)
    elif payload.source_kind == "external_krs_schedule":
        normalized_payload = normalize_external_krs_schedule(df, resolved, report)
    else:
        raise HTTPException(status_code=400, detail="Неподдерживаемый source_kind.")

    dataset_reference = repo.create_dataset_version(
        dataset_type=payload.source_kind,
        name=payload.dataset_name or f"{payload.source_kind}:{uploaded.original_name}",
        source_format=path.suffix.lstrip("."),
        source_file_name=uploaded.original_name,
        normalized_payload=normalized_payload,
        validation_report=report.model_dump(),
        row_count=report.row_count,
        metadata={"sheet_name": selected_sheet},
    )

    if payload.source_kind == "external_krs_schedule" and isinstance(normalized_payload, dict):
        normalized_payload["dataset_reference"] = dataset_reference.model_dump()
        normalized_payload["source_format"] = path.suffix.lstrip(".")
        normalized_payload["source_file_name"] = uploaded.original_name

    return NormalizeResponse(
        dataset_reference=dataset_reference,
        validation_report=report,
        normalized_payload=normalized_payload,
    )
