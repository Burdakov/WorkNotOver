from __future__ import annotations

import re
import shutil
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / 'storage' / 'uploads'
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title='WorkNotOver API', version='1.0.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


class ColumnInfo(BaseModel):
    name: str
    type: str
    non_null: int
    nulls: int
    unique: int


class UploadedFileItem(BaseModel):
    file_id: str
    original_name: str
    sheets: list[str]


class UploadResponse(BaseModel):
    file_id: str
    original_name: str
    sheets: list[str]
    selected_sheet: str
    preview: list[dict[str, Any]]
    columns_info: list[ColumnInfo]


class ScheduleColumns(BaseModel):
    brigade: str | None = None
    area: str | None = None
    well: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    increment: str | None = None
    planned_work: str | None = None


class ScheduleParseRequest(BaseModel):
    file_id: str
    sheet_name: str | None = None
    columns: ScheduleColumns | None = None


class ScheduleItem(BaseModel):
    event_id: str
    brigade: str
    area: str = ''
    well: str
    start_date: str
    end_date: str
    increment: float | None = None
    planned_work: str = ''
    duration_days: int
    has_increment: bool
    is_ppd: bool
    source_row_number: int


class ScheduleParseResponse(BaseModel):
    file_id: str
    original_name: str
    sheet_name: str
    columns: ScheduleColumns
    items: list[ScheduleItem]
    min_date: str | None = None
    max_date: str | None = None
    skipped_rows: int = 0


class ScheduleExportRequest(BaseModel):
    version_name: str | None = None
    columns: ScheduleColumns
    items: list[ScheduleItem]


_HINTS = {
    'brigade': ['бригада', 'brigade'],
    'area': ['участок', 'area'],
    'well': ['скв', 'скваж', 'well'],
    'start_date': ['дата начала', 'начало', 'start'],
    'end_date': ['заверш', 'оконч', 'конец', 'end'],
    'increment': ['qн', 'qh', 'прирост', 'дебит'],
    'planned_work': ['планируемый объем работ', 'планируемый объём работ', 'объем работ', 'объём работ', 'мероприят'],
}


def normalize_text(value: object) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip().lower().replace('ё', 'е'))


def file_record(file_id: str) -> tuple[Path, str]:
    path = STORAGE_DIR / file_id
    if not path.exists():
        raise HTTPException(status_code=404, detail='Файл не найден.')
    meta = path.with_suffix(path.suffix + '.meta')
    original_name = meta.read_text(encoding='utf-8') if meta.exists() else path.name
    return path, original_name


def excel_file(path: Path) -> pd.ExcelFile:
    try:
        return pd.ExcelFile(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f'Не удалось прочитать Excel-файл: {exc}') from exc


def sheet_df(path: Path, sheet_name: str | None) -> tuple[list[str], str, pd.DataFrame]:
    workbook = excel_file(path)
    sheets = workbook.sheet_names
    if not sheets:
        raise HTTPException(status_code=400, detail='В Excel нет листов.')
    active_sheet = sheet_name or sheets[0]
    try:
        df = workbook.parse(active_sheet)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать лист '{active_sheet}': {exc}") from exc
    return sheets, active_sheet, df


def column_type(series: pd.Series) -> str:
    sample = series.dropna().head(50)
    if sample.empty:
        return 'empty'
    if pd.api.types.is_numeric_dtype(series):
        return 'numeric'
    parsed = pd.to_datetime(sample, errors='coerce', dayfirst=True)
    if parsed.notna().mean() > 0.75:
        return 'date'
    if sample.astype(str).nunique() < max(20, len(sample) * 0.5):
        return 'categorical'
    return 'text'


def columns_info(df: pd.DataFrame) -> list[ColumnInfo]:
    return [
        ColumnInfo(
            name=str(column),
            type=column_type(df[column]),
            non_null=int(df[column].notna().sum()),
            nulls=int(df[column].isna().sum()),
            unique=int(df[column].nunique(dropna=True)),
        )
        for column in df.columns
    ]


def preview_records(df: pd.DataFrame, limit: int = 12) -> list[dict[str, Any]]:
    def serialize_preview_value(value: Any) -> Any:
        if value is None or pd.isna(value):
            return None
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                pass
        return value

    preview = df.head(limit).copy()
    preview = preview.where(pd.notnull(preview), None)
    return [
        {str(column): serialize_preview_value(value) for column, value in row.items()}
        for row in preview.to_dict(orient='records')
    ]


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
        raise HTTPException(status_code=400, detail=f"Не удалось автоматически определить колонки: {', '.join(missing)}")
    return ScheduleColumns(**resolved)


def coerce_date(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors='coerce', dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def coerce_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def stringify(value: object) -> str:
    if value is None or pd.isna(value):
        return ''
    return str(value).strip()


@app.get('/api/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/api/files/upload', response_model=UploadResponse)
def upload_excel(file: UploadFile = File(...)) -> UploadResponse:
    extension = Path(file.filename or 'schedule.xlsx').suffix.lower()
    if extension not in {'.xlsx', '.xls'}:
        raise HTTPException(status_code=400, detail='Поддерживаются только файлы Excel .xlsx и .xls.')

    file_id = f'{uuid4()}{extension}'
    path = STORAGE_DIR / file_id
    with path.open('wb') as buffer:
        shutil.copyfileobj(file.file, buffer)
    path.with_suffix(path.suffix + '.meta').write_text(file.filename or file_id, encoding='utf-8')

    sheets, selected_sheet, df = sheet_df(path, None)
    payload = UploadResponse(
        file_id=file_id,
        original_name=file.filename or file_id,
        sheets=sheets,
        selected_sheet=selected_sheet,
        preview=preview_records(df),
        columns_info=columns_info(df),
    )
    return JSONResponse(content=jsonable_encoder(payload.model_dump()))


@app.get('/api/files', response_model=list[UploadedFileItem])
def list_files() -> list[UploadedFileItem]:
    items: list[UploadedFileItem] = []
    for path in sorted(STORAGE_DIR.glob('*.xls*'), key=lambda item: item.stat().st_mtime, reverse=True):
        if path.name.endswith('.meta'):
            continue
        try:
            workbook = excel_file(path)
            sheets = workbook.sheet_names
        except HTTPException:
            sheets = []
        meta = path.with_suffix(path.suffix + '.meta')
        original_name = meta.read_text(encoding='utf-8') if meta.exists() else path.name
        items.append(UploadedFileItem(file_id=path.name, original_name=original_name, sheets=sheets))
    return items


@app.get('/api/files/{file_id}', response_model=UploadResponse)
def file_details(file_id: str, sheet_name: str | None = None) -> UploadResponse:
    path, original_name = file_record(file_id)
    sheets, selected_sheet, df = sheet_df(path, sheet_name)
    payload = UploadResponse(
        file_id=file_id,
        original_name=original_name,
        sheets=sheets,
        selected_sheet=selected_sheet,
        preview=preview_records(df),
        columns_info=columns_info(df),
    )
    return JSONResponse(content=jsonable_encoder(payload.model_dump()))


@app.post('/api/schedule/parse', response_model=ScheduleParseResponse)
def parse_schedule(payload: ScheduleParseRequest) -> ScheduleParseResponse:
    path, original_name = file_record(payload.file_id)
    _, selected_sheet, df = sheet_df(path, payload.sheet_name)
    resolved = resolve_columns(df, payload.columns)

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
        is_ppd = 'ппд' in normalized_work
        has_increment = increment is not None and increment > 0

        items.append(
            ScheduleItem(
                event_id=f'evt-{index + 2}',
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

    min_date = min((item.start_date for item in items), default=None)
    max_date = max((item.end_date for item in items), default=None)

    return ScheduleParseResponse(
        file_id=payload.file_id,
        original_name=original_name,
        sheet_name=selected_sheet,
        columns=resolved,
        items=items,
        min_date=min_date,
        max_date=max_date,
        skipped_rows=skipped_rows,
    )


@app.post('/api/schedule/export')
def export_schedule(payload: ScheduleExportRequest) -> StreamingResponse:
    rows = [
        {
            payload.columns.brigade or 'Бригада': item.brigade,
            payload.columns.area or 'Участок': item.area,
            payload.columns.well or 'Скв.': item.well,
            payload.columns.start_date or 'Дата начала (план)': item.start_date,
            payload.columns.end_date or 'Заверш рем (план)': item.end_date,
            payload.columns.increment or 'Qн, тн/сут': item.increment if item.increment is not None else 0,
            payload.columns.planned_work or 'Планируемый объем работ': item.planned_work,
        }
        for item in payload.items
    ]

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name='KRS Schedule')

    filename = re.sub(r'[^A-Za-z0-9А-Яа-я._-]+', '_', (payload.version_name or 'krs_schedule').strip()) + '.xlsx'
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
