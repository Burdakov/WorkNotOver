from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException

from app.schemas.common import ColumnInfo

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "storage" / "uploads"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm"}
TEXT_EXTENSIONS = {".txt"}

HEADER_SCAN_MAX_ROWS = 50
HEADER_SCAN_MAX_COLS = 100
TABLE_SCAN_DATA_ROWS = 200
HEADER_WELL_TOKENS = ("скв", "well")
HEADER_ROW_HINTS = (
    "скв",
    "well",
    "куст",
    "brig",
    "бриг",
    "участ",
    "lu",
    "sloy",
    "слой",
    "пласт",
    "gtm",
    "гтм",
    "дата",
    "start",
    "end",
    "qн",
    "qж",
    "qг",
    "gor",
    "watercut",
    "обвод",
    "низ",
)
EMPTY_COL_STREAK_LIMIT = 3
EMPTY_ROW_STREAK_LIMIT = 3
HEADER_CONTINUATION_MAX_ROWS = 2
HEADER_PARENT_MAX_ROWS = 2


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text)


def excel_file(path: Path) -> pd.ExcelFile:
    try:
        return pd.ExcelFile(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать Excel-файл: {exc}") from exc


def _cell_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _non_empty_row_cells(raw_df: pd.DataFrame, row_index: int, col_start: int, col_end: int) -> list[str]:
    cells: list[str] = []
    for value in raw_df.iloc[row_index, col_start : col_end + 1].tolist():
        if value is None or pd.isna(value):
            continue
        text = normalize_text(value)
        if text:
            cells.append(text)
    return cells


def _row_has_content(raw_df: pd.DataFrame, row_index: int, col_start: int, col_end: int) -> bool:
    if row_index < 0 or row_index >= len(raw_df.index):
        return False
    for value in raw_df.iloc[row_index, col_start : col_end + 1].tolist():
        if _cell_text(value):
            return True
    return False


def _col_has_content(raw_df: pd.DataFrame, col_index: int, row_start: int, row_end: int) -> bool:
    if col_index < 0 or col_index >= len(raw_df.columns):
        return False
    max_row = min(row_end, len(raw_df.index) - 1)
    if max_row < row_start:
        return False
    for value in raw_df.iloc[row_start : max_row + 1, col_index].tolist():
        if _cell_text(value):
            return True
    return False


def _detect_header_row(raw_df: pd.DataFrame) -> tuple[int, int | None]:
    if raw_df.empty:
        return 0, None

    scan_df = raw_df.iloc[:HEADER_SCAN_MAX_ROWS, :HEADER_SCAN_MAX_COLS]
    best_row_index: int | None = None
    best_score = -1
    best_well_col: int | None = None
    fallback_row_index: int | None = None
    fallback_well_col: int | None = None

    for row_index, row in scan_df.iterrows():
        normalized_cells = []
        well_col: int | None = None

        for col_index, value in enumerate(row.tolist()):
            if value is None or pd.isna(value):
                continue
            cell = normalize_text(value)
            if not cell:
                continue
            normalized_cells.append(cell)
            if well_col is None and any(token in cell for token in HEADER_WELL_TOKENS):
                well_col = col_index

        if not normalized_cells or well_col is None:
            continue

        if fallback_row_index is None:
            fallback_row_index = int(row_index)
            fallback_well_col = int(well_col)

        row_score = sum(
            1
            for cell in normalized_cells
            if any(hint in cell for hint in HEADER_ROW_HINTS)
        )
        if row_score >= 2 and row_score > best_score:
            best_row_index = int(row_index)
            best_well_col = int(well_col)
            best_score = row_score

    if best_row_index is not None:
        return best_row_index, best_well_col
    if fallback_row_index is not None:
        return fallback_row_index, fallback_well_col
    return 0, None


def _detect_column_bounds(raw_df: pd.DataFrame, header_row: int, well_col: int | None) -> tuple[int, int]:
    scan_col_count = min(len(raw_df.columns), HEADER_SCAN_MAX_COLS)
    if scan_col_count == 0:
        return 0, 0

    if well_col is None:
        useful_cols = [
            col_index
            for col_index in range(scan_col_count)
            if _col_has_content(raw_df, col_index, header_row, min(header_row + TABLE_SCAN_DATA_ROWS, len(raw_df.index) - 1))
        ]
        if not useful_cols:
            return 0, max(0, scan_col_count - 1)
        return min(useful_cols), max(useful_cols)

    row_end = min(header_row + TABLE_SCAN_DATA_ROWS, len(raw_df.index) - 1)
    left = well_col
    right = well_col

    empty_streak = 0
    for col_index in range(well_col, -1, -1):
        if _col_has_content(raw_df, col_index, header_row, row_end):
            left = col_index
            empty_streak = 0
        else:
            empty_streak += 1
            if empty_streak >= EMPTY_COL_STREAK_LIMIT:
                break

    empty_streak = 0
    for col_index in range(well_col, scan_col_count):
        if _col_has_content(raw_df, col_index, header_row, row_end):
            right = col_index
            empty_streak = 0
        else:
            empty_streak += 1
            if empty_streak >= EMPTY_COL_STREAK_LIMIT:
                break

    return left, right


def _row_looks_like_data(raw_df: pd.DataFrame, row_index: int, well_col: int, col_start: int, col_end: int) -> bool:
    if row_index >= len(raw_df.index):
        return False

    well_value = raw_df.iat[row_index, well_col] if well_col < len(raw_df.columns) else None
    well_cell = normalize_text(well_value) if well_value is not None and not pd.isna(well_value) else ""
    if well_cell and not any(token in well_cell for token in HEADER_WELL_TOKENS):
        return True

    normalized_cells = _non_empty_row_cells(raw_df, row_index, col_start, col_end)
    if not normalized_cells:
        return False

    header_like_count = sum(
        1
        for cell in normalized_cells
        if any(hint in cell for hint in HEADER_ROW_HINTS)
    )
    return header_like_count == 0


def _is_value_like_text(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False

    try:
        float(normalized.replace(" ", "").replace(",", "."))
        return True
    except ValueError:
        pass

    return pd.to_datetime([text], errors="coerce", dayfirst=True).notna().any()


def _detect_header_height(raw_df: pd.DataFrame, header_row: int, well_col: int | None, col_start: int, col_end: int) -> int:
    if well_col is None:
        return 1

    header_height = 1
    for offset in range(1, HEADER_CONTINUATION_MAX_ROWS + 1):
        row_index = header_row + offset
        if row_index >= len(raw_df.index):
            break
        if not _row_has_content(raw_df, row_index, col_start, col_end):
            continue
        if _row_looks_like_data(raw_df, row_index, well_col, col_start, col_end):
            break
        header_height += 1
    return header_height


def _detect_header_top(raw_df: pd.DataFrame, header_row: int, well_col: int | None, col_start: int, col_end: int) -> int:
    top_row = header_row
    if well_col is None:
        return top_row

    for offset in range(1, HEADER_PARENT_MAX_ROWS + 1):
        row_index = header_row - offset
        if row_index < 0:
            break
        if not _row_has_content(raw_df, row_index, col_start, col_end):
            break

        cells = _non_empty_row_cells(raw_df, row_index, col_start, col_end)
        if len(cells) < 2:
            break
        value_like_count = sum(1 for cell in cells if _is_value_like_text(cell))
        if value_like_count / max(1, len(cells)) >= 0.5:
            break

        top_row = row_index

    return top_row


def _detect_last_data_row(raw_df: pd.DataFrame, data_start_row: int, col_start: int, col_end: int) -> int:
    if data_start_row >= len(raw_df.index):
        return data_start_row

    last_non_empty_row = data_start_row
    empty_streak = 0
    for row_index in range(data_start_row, len(raw_df.index)):
        if _row_has_content(raw_df, row_index, col_start, col_end):
            last_non_empty_row = row_index
            empty_streak = 0
        else:
            empty_streak += 1
            if empty_streak >= EMPTY_ROW_STREAK_LIMIT:
                break
    return last_non_empty_row


def _filled_header_matrix(header_block: pd.DataFrame) -> list[list[str]]:
    matrix = [
        [_cell_text(header_block.iat[row_offset, col_offset]) for col_offset in range(len(header_block.columns))]
        for row_offset in range(len(header_block.index))
    ]
    if not matrix:
        return matrix

    for row_offset, row in enumerate(matrix):
        current = ""
        for col_offset, cell in enumerate(row):
            if cell:
                current = cell
            elif current:
                matrix[row_offset][col_offset] = current

    col_count = len(matrix[0])
    for col_offset in range(col_count):
        current = ""
        for row_offset in range(len(matrix)):
            cell = matrix[row_offset][col_offset]
            if cell:
                current = cell
            elif current:
                matrix[row_offset][col_offset] = current

    return matrix


def _build_column_names(header_block: pd.DataFrame) -> list[str]:
    names: list[str] = []
    used_names: dict[str, int] = {}
    filled_matrix = _filled_header_matrix(header_block)

    for col_offset in range(len(header_block.columns)):
        parts: list[str] = []
        seen_normalized: set[str] = set()
        for row_offset in range(len(header_block.index)):
            text = filled_matrix[row_offset][col_offset] if filled_matrix else ""
            normalized = normalize_text(text)
            if text and normalized not in seen_normalized:
                parts.append(text)
                seen_normalized.add(normalized)

        base_name = " | ".join(parts) if parts else f"unnamed_{col_offset + 1}"
        duplicate_count = used_names.get(base_name, 0)
        used_names[base_name] = duplicate_count + 1
        if duplicate_count:
            names.append(f"{base_name}__{duplicate_count + 1}")
        else:
            names.append(base_name)

    return names


def excel_row_number(df: pd.DataFrame, index: int) -> int:
    return int(df.attrs.get("excel_data_row_offset", 2)) + int(index)


def sheet_df(path: Path, sheet_name: str | None) -> tuple[list[str], str, pd.DataFrame]:
    workbook = excel_file(path)
    sheets = workbook.sheet_names
    if not sheets:
        raise HTTPException(status_code=400, detail="В Excel нет листов.")

    selected_sheet = sheet_name or sheets[0]
    try:
        raw_df = workbook.parse(selected_sheet, header=None)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать лист '{selected_sheet}': {exc}") from exc

    if raw_df.empty:
        return sheets, selected_sheet, pd.DataFrame()

    header_row, well_col = _detect_header_row(raw_df)
    col_start, col_end = _detect_column_bounds(raw_df, header_row, well_col)
    header_height = _detect_header_height(raw_df, header_row, well_col, col_start, col_end)
    header_top = _detect_header_top(raw_df, header_row, well_col, col_start, col_end)
    header_total_height = header_height + (header_row - header_top)
    data_start_row = header_row + header_height
    last_data_row = _detect_last_data_row(raw_df, data_start_row, col_start, col_end)

    header_block = raw_df.iloc[header_top : header_row + header_height, col_start : col_end + 1].copy()
    data_block = raw_df.iloc[data_start_row : last_data_row + 1, col_start : col_end + 1].copy()
    data_block = data_block.reset_index(drop=True)
    data_block.columns = _build_column_names(header_block)
    data_block.attrs["excel_header_row"] = header_top + 1
    data_block.attrs["excel_header_height"] = header_total_height
    data_block.attrs["excel_data_row_offset"] = data_start_row + 1
    data_block.attrs["excel_table_range"] = {
        "sheet_name": selected_sheet,
        "header_row": header_top + 1,
        "header_height": header_total_height,
        "data_start_row": data_start_row + 1,
        "data_end_row": last_data_row + 1,
        "first_column_index": col_start + 1,
        "last_column_index": col_end + 1,
    }
    return sheets, selected_sheet, data_block


def text_lines(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "cp1251", "utf-8"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace").splitlines()


def text_df(path: Path) -> tuple[list[str], str, pd.DataFrame]:
    lines = text_lines(path)
    df = pd.DataFrame(
        {
            "line_number": list(range(1, len(lines) + 1)),
            "text": lines,
        }
    )
    df.attrs["excel_data_row_offset"] = 1
    return ["text"], "text", df


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
    def serialize(value: Any) -> Any:
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

    preview = df.head(limit).copy().where(pd.notnull(df.head(limit)), None)
    return [{str(column): serialize(value) for column, value in row.items()} for row in preview.to_dict(orient="records")]


def coerce_date(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (int, float)) and 20000 <= float(value) <= 80000:
        parsed = pd.to_datetime(float(value), unit="D", origin="1899-12-30", errors="coerce")
        if not pd.isna(parsed):
            return parsed.date().isoformat()
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
