from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.common import DatasetReference
from app.schemas.schedule_models import (
    ImportedScheduleOpenRequest,
    ImportedScheduleOpenResponse,
    ScheduleColumns,
    ScheduleExportRequest,
    ScheduleItem,
    ScheduleParseRequest,
    ScheduleParseResponse,
)
from app.services.importing.excel_utils import coerce_date, coerce_float, normalize_text, sheet_df, stringify

router = APIRouter(prefix="/api/schedule", tags=["schedule"])

_HINTS = {
    "brigade": ["бригада", "brigade"],
    "area": ["участок", "area"],
    "well": ["скв", "скваж", "well"],
    "start_date": ["дата начала", "начало", "start"],
    "end_date": ["заверш", "оконч", "конец", "end"],
    "increment": ["qн", "qh", "прирост", "дебит"],
    "planned_work": ["планируемый объем работ", "планируемый объём работ", "объем работ", "объём работ", "мероприят"],
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def resolve_columns(df: pd.DataFrame, provided: ScheduleColumns | None) -> ScheduleColumns:
    provided = provided or ScheduleColumns()
    columns = [str(column) for column in df.columns]
    normalized = {column: normalize_text(column) for column in columns}
    resolved: dict[str, str | None] = {}

    for key, hints in _HINTS.items():
        explicit = getattr(provided, key)
        if explicit:
            if explicit not in columns:
                raise HTTPException(status_code=400, detail=f"Колонка '{explicit}' не найдена.")
            resolved[key] = explicit
            continue
        match = next((column for column in columns if any(hint in normalized[column] for hint in hints)), None)
        resolved[key] = match

    missing = [key for key, value in resolved.items() if not value]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось автоматически определить колонки: {', '.join(missing)}",
        )
    return ScheduleColumns(**resolved)


def parse_schedule_rows(df: pd.DataFrame, resolved: ScheduleColumns) -> tuple[list[ScheduleItem], int]:
    items: list[ScheduleItem] = []
    skipped_rows = 0

    for index, row in df.iterrows():
        brigade = stringify(row.get(resolved.brigade))
        area = stringify(row.get(resolved.area))
        well = stringify(row.get(resolved.well))
        start_date = coerce_date(row.get(resolved.start_date))
        end_date = coerce_date(row.get(resolved.end_date))
        increment = coerce_float(row.get(resolved.increment))
        planned_work = stringify(row.get(resolved.planned_work))

        if not any([brigade, area, well, start_date, end_date, increment is not None, planned_work]):
            continue
        if not brigade or not well or not start_date or not end_date:
            skipped_rows += 1
            continue
        if end_date < start_date:
            start_date, end_date = end_date, start_date

        duration_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1
        normalized_work = normalize_text(planned_work)
        is_ppd = "ппд" in normalized_work
        has_increment = increment is not None and increment > 0

        items.append(
            ScheduleItem(
                event_id=f"evt-{index + 2}",
                brigade=brigade,
                area=area,
                well=well,
                start_date=start_date,
                end_date=end_date,
                increment=increment,
                planned_work=planned_work,
                duration_days=duration_days,
                has_increment=has_increment,
                is_ppd=is_ppd,
                source_row_number=index + 2,
            )
        )

    return items, skipped_rows


def build_schedule_item_from_imported_row(row: dict[str, object]) -> ScheduleItem:
    start_date = stringify(row.get("planned_start_date"))
    end_date = stringify(row.get("planned_end_date"))
    increment = coerce_float(row.get("expected_oil_increment"))
    planned_work = stringify(row.get("planned_work"))
    normalized_work = normalize_text(planned_work)

    duration_days = 0
    if start_date and end_date:
        duration_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1
    else:
        duration_days = int(row.get("duration_days") or 0)

    source_row_number = 0
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        source_row_number = int(metadata.get("source_row_number") or 0)

    return ScheduleItem(
        event_id=stringify(row.get("schedule_item_id")) or stringify(row.get("gtm_id")) or "imported-event",
        brigade=stringify(row.get("brigade")),
        area=stringify(row.get("area")),
        well=stringify(row.get("well_name")) or stringify(row.get("well_id")),
        start_date=start_date,
        end_date=end_date,
        increment=increment,
        planned_work=planned_work,
        duration_days=duration_days,
        has_increment=increment is not None and increment > 0,
        is_ppd="ппд" in normalized_work,
        source_row_number=source_row_number,
    )


@router.post("/parse", response_model=ScheduleParseResponse)
def parse_schedule(payload: ScheduleParseRequest, db: Session = Depends(get_db)) -> ScheduleParseResponse:
    uploaded = next((entry for entry in DatasetRepository(db).list_uploaded_files() if entry.file_id == payload.file_id), None)
    if uploaded is None:
        raise HTTPException(status_code=404, detail="Файл не найден.")

    path = Path(uploaded.stored_path)
    _, selected_sheet, df = sheet_df(path, payload.sheet_name)
    resolved = resolve_columns(df, payload.columns)
    items, skipped_rows = parse_schedule_rows(df, resolved)

    return ScheduleParseResponse(
        file_id=payload.file_id,
        original_name=uploaded.original_name,
        sheet_name=selected_sheet,
        columns=resolved,
        items=items,
        min_date=min((item.start_date for item in items), default=None),
        max_date=max((item.end_date for item in items), default=None),
        skipped_rows=skipped_rows,
    )


@router.post("/open-imported", response_model=ImportedScheduleOpenResponse)
def open_imported_schedule(payload: ImportedScheduleOpenRequest, db: Session = Depends(get_db)) -> ImportedScheduleOpenResponse:
    resolved = DatasetRepository(db).get_dataset_version(payload.dataset_id, payload.dataset_version_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Импортированный график КРС не найден.")

    dataset, version = resolved
    if dataset.dataset_type != "external_krs_schedule":
        raise HTTPException(status_code=400, detail="Указанный dataset не является внешним графиком КРС.")

    payload_json = version.normalized_payload_json
    if not isinstance(payload_json, dict):
        raise HTTPException(status_code=400, detail="Нормализованный payload графика КРС поврежден.")

    schedule = payload_json.get("schedule")
    if not isinstance(schedule, dict):
        raise HTTPException(status_code=400, detail="В dataset отсутствует planner-friendly schedule payload.")

    schedule_rows = schedule.get("items")
    if not isinstance(schedule_rows, list):
        raise HTTPException(status_code=400, detail="В dataset отсутствует список мероприятий графика КРС.")

    items = [build_schedule_item_from_imported_row(row) for row in schedule_rows if isinstance(row, dict)]

    return ImportedScheduleOpenResponse(
        dataset_reference=DatasetReference(
            dataset_id=dataset.dataset_id,
            dataset_version_id=version.dataset_version_id,
            dataset_type=dataset.dataset_type,
            name=dataset.name,
            row_count=version.row_count,
            created_at=dataset.created_at.isoformat(),
            metadata=dataset.metadata_json,
        ),
        version_name=stringify(schedule.get("name")) or dataset.name,
        source_file_name=dataset.source_file_name,
        source_format=dataset.source_format,
        items=items,
        min_date=min((item.start_date for item in items), default=None),
        max_date=max((item.end_date for item in items), default=None),
        brigade_count=int(schedule.get("brigade_count") or 0),
        skipped_rows=0,
    )


@router.post("/export")
def export_schedule(payload: ScheduleExportRequest) -> StreamingResponse:
    rows = [
        {
            payload.columns.brigade or "Бригада": item.brigade,
            payload.columns.area or "Участок": item.area,
            payload.columns.well or "Скв.": item.well,
            payload.columns.start_date or "Дата начала (план)": item.start_date,
            payload.columns.end_date or "Заверш рем (план)": item.end_date,
            payload.columns.increment or "Qн, тн/сут": item.increment if item.increment is not None else 0,
            payload.columns.planned_work or "Планируемый объем работ": item.planned_work,
        }
        for item in payload.items
    ]

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="KRS Schedule")

    filename = re.sub(r"[^A-Za-z0-9А-Яа-я._-]+", "_", (payload.version_name or "krs_schedule").strip()) + ".xlsx"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
