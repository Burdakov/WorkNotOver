from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException

from app.schemas.common import ColumnInfo

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "storage" / "uploads"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text)


def excel_file(path: Path) -> pd.ExcelFile:
    try:
        return pd.ExcelFile(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать Excel-файл: {exc}") from exc


def sheet_df(path: Path, sheet_name: str | None) -> tuple[list[str], str, pd.DataFrame]:
    workbook = excel_file(path)
    sheets = workbook.sheet_names
    if not sheets:
        raise HTTPException(status_code=400, detail="В Excel нет листов.")
    active_sheet = sheet_name or sheets[0]
    try:
        df = workbook.parse(active_sheet)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать лист '{active_sheet}': {exc}") from exc
    return sheets, active_sheet, df


def column_type(series: pd.Series) -> str:
    sample = series.dropna().head(50)
    if sample.empty:
        return "empty"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    parsed = pd.to_datetime(sample, errors="coerce", dayfirst=True)
    if parsed.notna().mean() > 0.75:
        return "date"
    if sample.astype(str).nunique() < max(20, len(sample) * 0.5):
        return "categorical"
    return "text"


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
        for row in preview.to_dict(orient="records")
    ]


def coerce_date(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date().isoformat()


def coerce_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def stringify(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()
