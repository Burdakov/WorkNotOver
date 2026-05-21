from __future__ import annotations

from typing import Any

import pandas as pd

from app.schemas.common import ImportValidationReport, ValidationIssue
from app.schemas.import_models import NormalizeColumns
from app.services.importing.excel_utils import coerce_date, coerce_float, excel_row_number, normalize_text, stringify

_HINTS: dict[str, list[str]] = {
    "well": ["скв", "скваж", "well"],
    "area": ["участок", "area"],
    "lu": ["участок недр", "лу", "lu"],
    "sloy": ["слой", "пласт", "sloy"],
    "well_pad": ["куст", "wellpad", "well_pad"],
    "brigade": ["бригада", "brigade"],
    "fund_type": ["вид фонда", "тип фонда", "fund type"],
    "fund_state": ["состояние по фонду", "состояние фонда", "состояние"],
    "start_date": ["дата начала", "начало", "start"],
    "end_date": ["заверш", "оконч", "конец", "end"],
    "planned_work": ["планируемый объем работ", "планируемый объём работ", "объем работ", "объём работ", "мероприят"],
    "increment": ["qн", "прирост нефти", "дебит нефти", "oil increment"],
    "liquid_increment": ["прирост жидкости", "прирост жидк", "liquid increment"],
    "gas_increment": ["прирост газа", "дебит газа", "gas increment", "qг"],
    "gor_change": ["газовый фактор", "gor", "изменение gor"],
    "oil_rate": ["дебит нефти", "oil rate", "qн"],
    "gas_rate": ["дебит газа", "gas rate", "qг"],
    "liquid_rate": ["дебит жидкости", "liquid rate", "qж"],
    "watercut": ["обводнен", "watercut"],
    "gor": ["газовый фактор", "gor", "гф"],
    "cumulative_oil": ["накоп", "добыча нефти"],
    "cumulative_gas": ["накоп", "добыча газа"],
    "niz": ["низ", "извлекаемых запасов"],
    "gtm_type": ["тип гтм", "gtm type", "гтм"],
    "duration_days": ["длитель", "продолжительность", "duration"],
    "object_name": ["объект", "наименование объекта"],
    "object_type": ["тип объекта"],
    "commissioning_date": ["дата ввода", "ввод"],
    "capacity_oil": ["мощн", "нефть"],
    "capacity_gas": ["мощн", "газ"],
    "capacity_liquid": ["мощн", "жидк"],
    "capacity_water": ["мощн", "вода"],
    "connection_well": ["скв", "скваж"],
    "parent_object": ["родител", "parent"],
}

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "wells": ("well", "lu", "well_pad", "fund_state", "oil_rate", "liquid_rate", "watercut"),
    "niz": ("well", "lu", "well_pad", "niz"),
    "gtm": ("well", "planned_work", "start_date"),
    "infrastructure": ("object_name", "object_type"),
    "external_krs_schedule": ("brigade", "well", "start_date", "end_date", "planned_work"),
}


def _sample_column_texts(df: pd.DataFrame, column: str, limit: int = 20) -> list[str]:
    if column not in df.columns:
        return []
    series = df[column].dropna().head(limit)
    return [stringify(value) for value in series if stringify(value)]


def _looks_like_alphanumeric_well_mask(value: str) -> bool:
    return bool(value) and any(char.isalpha() for char in value) and any(char.isdigit() for char in value)


def _looks_like_numeric_well_number(value: str) -> bool:
    normalized = value.replace(" ", "").replace("-", "").replace("_", "")
    return normalized.isdigit()


def _extract_effective_well_name(row: pd.Series, primary_column: str | None) -> str:
    primary_value = stringify(row.get(primary_column)) if primary_column else ""
    if not primary_value or _looks_like_alphanumeric_well_mask(primary_value):
        return primary_value

    for column_name in row.index:
        normalized_column = normalize_text(column_name)
        if "id" not in normalized_column:
            continue
        candidate = stringify(row.get(column_name))
        if _looks_like_alphanumeric_well_mask(candidate):
            return candidate
        if "скв" not in normalized_column and "well" not in normalized_column:
            continue
        candidate = stringify(row.get(column_name))
        if _looks_like_alphanumeric_well_mask(candidate):
            return candidate

    return primary_value


def _score_well_column(df: pd.DataFrame, column: str, normalized_column: str, hints: list[str]) -> int:
    score = sum(1 for hint in hints if hint in normalized_column)

    if "id" in normalized_column and ("скв" in normalized_column or "well" in normalized_column):
        score += 100
    if "скважин" in normalized_column and "№" in column:
        score += 10

    if "id" in normalized_column:
        score += 100
    if "№" in column:
        score += 10
    sample_values = _sample_column_texts(df, column)
    alpha_numeric_count = sum(1 for value in sample_values if _looks_like_alphanumeric_well_mask(value))
    numeric_only_count = sum(1 for value in sample_values if _looks_like_numeric_well_number(value))

    score += alpha_numeric_count * 20
    score -= numeric_only_count * 3

    return score


def _warning(report: ImportValidationReport, message: str, row_number: int | None = None, field_name: str | None = None) -> None:
    report.warnings.append(
        ValidationIssue(level="warning", message=message, row_number=row_number, field_name=field_name)
    )


def _stable_well_id(well_name: str, row_number: int) -> str:
    raw = stringify(well_name)
    if raw:
        return " ".join(raw.split())
    return f"well_{row_number}"


def _normalize_fund_type(value: Any) -> str | None:
    raw = stringify(value)
    if not raw:
        return None
    normalized = normalize_text(raw)
    if "new wells" in normalized or "внс" in normalized or "нов" in normalized:
        return "New wells"
    if "base" in normalized or "баз" in normalized:
        return "Base"
    return raw


def _normalize_fund_state(value: Any) -> str | None:
    raw = stringify(value)
    if not raw:
        return None
    return raw


def _is_ambiguous(key: str, normalized_column: str) -> bool:
    if key in {"gas_increment", "gas_rate"} and "qж/qг" in normalized_column:
        return True
    if key == "gtm_type" and "дата" in normalized_column and "гтм" in normalized_column:
        return True
    return False


def resolve_columns(df: pd.DataFrame, provided: NormalizeColumns | None, source_kind: str) -> NormalizeColumns:
    provided = provided or NormalizeColumns()
    columns = [str(column) for column in df.columns]
    normalized_columns = {column: normalize_text(column) for column in columns}
    resolved: dict[str, str | None] = {}

    for key, hints in _HINTS.items():
        explicit = getattr(provided, key)
        if explicit:
            if explicit not in columns:
                raise ValueError(f"Колонка '{explicit}' не найдена.")
            resolved[key] = explicit
            continue

        candidates = [
            column
            for column in columns
            if any(hint in normalized_columns[column] for hint in hints) and not _is_ambiguous(key, normalized_columns[column])
        ]
        if key == "well" and candidates:
            match = max(
                candidates,
                key=lambda column: (
                    _score_well_column(df, column, normalized_columns[column], hints),
                    -columns.index(column),
                ),
            )
        else:
            match = candidates[0] if candidates else None
        resolved[key] = match

    missing = [field for field in _REQUIRED_FIELDS.get(source_kind, ()) if not resolved.get(field)]
    if missing:
        raise ValueError(f"Не удалось определить обязательные колонки: {', '.join(missing)}")
    return NormalizeColumns(**resolved)


def normalize_wells(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        well_name = _extract_effective_well_name(row, columns.well)
        if not well_name:
            continue

        items.append(
            {
                "well_id": _stable_well_id(well_name, row_number),
                "well_name": well_name,
                "area": None,
                "lu_id": stringify(row.get(columns.lu)) or None,
                "sloy_id": stringify(row.get(columns.sloy)) or None,
                "well_pad_id": stringify(row.get(columns.well_pad)) or None,
                "infrastructure_object_id": None,
                "brigade": None,
                "fund_type": "Base",
                "fund_state": _normalize_fund_state(row.get(columns.fund_state)),
                "status": None,
                "current_oil_rate": coerce_float(row.get(columns.oil_rate)),
                "current_gas_rate": coerce_float(row.get(columns.gas_rate)),
                "current_liquid_rate": coerce_float(row.get(columns.liquid_rate)),
                "current_watercut": coerce_float(row.get(columns.watercut)),
                "current_gor": coerce_float(row.get(columns.gor)),
                "current_cumulative_oil": None,
                "current_cumulative_gas": None,
                "current_cumulative_liquid": None,
                "niz": None,
                "reserves_group": None,
                "metadata": {"source_row_number": row_number},
            }
        )

    report.row_count = len(items)
    return items


def normalize_niz(
    df: pd.DataFrame,
    columns: NormalizeColumns,
    report: ImportValidationReport,
    row_matches: dict[int, str] | None = None,
    manual_entries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    row_matches = row_matches or {}
    manual_entries = manual_entries or []

    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        source_well_name = stringify(row.get(columns.well))
        lu_id = stringify(row.get(columns.lu))
        well_pad_id = stringify(row.get(columns.well_pad))
        niz = coerce_float(row.get(columns.niz))
        well_name = stringify(row_matches.get(row_number)) or source_well_name

        if not source_well_name and not lu_id and not well_pad_id and niz <= 0:
            continue

        if not well_name:
            report.skipped_rows += 1
            _warning(report, "Строка NIZ пропущена: отсутствует имя скважины.", row_number=row_number, field_name="well")
            continue

        if not lu_id:
            report.skipped_rows += 1
            _warning(report, "РЎС‚СЂРѕРєР° NIZ РїСЂРѕРїСѓС‰РµРЅР°: РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ LU.", row_number=row_number, field_name="lu")
            continue

        if not well_pad_id:
            report.skipped_rows += 1
            _warning(report, "РЎС‚СЂРѕРєР° NIZ РїСЂРѕРїСѓС‰РµРЅР°: РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚ РєСѓСЃС‚.", row_number=row_number, field_name="well_pad")
            continue

        if niz <= 0:
            report.skipped_rows += 1
            _warning(report, "Строка NIZ пропущена: значение NIZ должно быть больше нуля.", row_number=row_number, field_name="niz")
            continue

        items.append(
            {
                "well_id": _stable_well_id(well_name, row_number),
                "well_name": well_name,
                "source_well_name": source_well_name,
                "lu_id": lu_id or None,
                "well_pad_id": well_pad_id or None,
                "niz": niz,
                "current_cumulative_oil": coerce_float(row.get(columns.cumulative_oil)),
                "current_cumulative_gas": coerce_float(row.get(columns.cumulative_gas)),
                "metadata": {"source_row_number": row_number},
            }
        )

    for manual_index, entry in enumerate(manual_entries, start=1):
        well_name = stringify(entry.get("well_name"))
        lu_id = stringify(entry.get("lu_id"))
        well_pad_id = stringify(entry.get("well_pad_id"))
        niz = coerce_float(entry.get("niz"))
        if not well_name or not lu_id or not well_pad_id or niz <= 0:
            continue
        items.append(
            {
                "well_id": _stable_well_id(well_name, 100000 + manual_index),
                "well_name": well_name,
                "source_well_name": well_name,
                "lu_id": lu_id or None,
                "well_pad_id": well_pad_id or None,
                "niz": niz,
                "current_cumulative_oil": coerce_float(entry.get("cumulative_oil")),
                "current_cumulative_gas": coerce_float(entry.get("cumulative_gas")),
                "metadata": {"source_row_number": None, "source": "manual"},
            }
        )

    report.row_count = len(items)
    return items


def normalize_gtm(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        well_name = _extract_effective_well_name(row, columns.well)
        planned_work = stringify(row.get(columns.planned_work))
        if not well_name and not planned_work:
            continue

        candidate_start = coerce_date(row.get(columns.start_date))
        candidate_end = coerce_date(row.get(columns.end_date)) or candidate_start
        duration_days = int(coerce_float(row.get(columns.duration_days)) or 0) or None

        items.append(
            {
                "gtm_id": f"gtm::{row_number}",
                "well_id": _stable_well_id(well_name, row_number),
                "well_name": well_name,
                "area": stringify(row.get(columns.area)) or None,
                "lu_id": stringify(row.get(columns.lu)) or None,
                "sloy_id": stringify(row.get(columns.sloy)) or None,
                "well_pad_id": stringify(row.get(columns.well_pad)) or None,
                "infrastructure_object_id": None,
                "brigade": stringify(row.get(columns.brigade)) or None,
                "gtm_type": stringify(row.get(columns.gtm_type)) or "unknown",
                "planned_work": planned_work or "unknown",
                "candidate_start_date": candidate_start,
                "candidate_end_date": candidate_end,
                "duration_days": duration_days,
                "expected_oil_increment": coerce_float(row.get(columns.increment)),
                "expected_gas_increment": coerce_float(row.get(columns.gas_increment)),
                "expected_liquid_increment": coerce_float(row.get(columns.liquid_increment)),
                "expected_watercut_change": None,
                "expected_gor_change": coerce_float(row.get(columns.gor_change)),
                "priority": None,
                "source_row_number": row_number,
                "metadata": {"source_row_number": row_number},
            }
        )

    report.row_count = len(items)
    return items


def normalize_infrastructure(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        object_name = stringify(row.get(columns.object_name))
        if not object_name:
            continue

        object_id = f"infra::{row_number}"
        objects.append(
            {
                "object_id": object_id,
                "name": object_name,
                "object_type": stringify(row.get(columns.object_type)) or "unknown",
                "commissioning_date": coerce_date(row.get(columns.commissioning_date)),
                "capacity_oil": coerce_float(row.get(columns.capacity_oil)),
                "capacity_gas": coerce_float(row.get(columns.capacity_gas)),
                "capacity_liquid": coerce_float(row.get(columns.capacity_liquid)),
                "capacity_water": coerce_float(row.get(columns.capacity_water)),
                "parent_object_id": stringify(row.get(columns.parent_object)) or None,
                "metadata": {"source_row_number": row_number},
            }
        )

        connection_well = stringify(row.get(columns.connection_well))
        if connection_well:
            connections.append(
                {
                    "connection_id": f"conn::{row_number}",
                    "well_id": _stable_well_id(connection_well, row_number),
                    "object_id": object_id,
                    "start_date": None,
                    "end_date": None,
                    "priority": None,
                    "metadata": {"source_row_number": row_number},
                }
            )

    report.row_count = len(objects)
    return {"objects": objects, "connections": connections}


def normalize_external_krs_schedule(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        brigade = stringify(row.get(columns.brigade))
        well_name = _extract_effective_well_name(row, columns.well)
        start_date = coerce_date(row.get(columns.start_date))
        end_date = coerce_date(row.get(columns.end_date))
        planned_work = stringify(row.get(columns.planned_work))

        if not any([brigade, well_name, start_date, end_date, planned_work]):
            continue

        if not brigade or not well_name or not start_date or not end_date:
            report.skipped_rows += 1
            _warning(report, "Строка внешнего графика КРС пропущена: отсутствуют обязательные поля.", row_number=row_number)
            continue

        if end_date < start_date:
            start_date, end_date = end_date, start_date

        explicit_duration = int(coerce_float(row.get(columns.duration_days)) or 0) or None
        derived_duration = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days + 1
        duration_days = explicit_duration or derived_duration

        items.append(
            {
                "schedule_item_id": f"external-krs::{row_number}",
                "scenario_id": None,
                "gtm_id": None,
                "well_id": _stable_well_id(well_name, row_number),
                "well_name": well_name,
                "brigade": brigade,
                "area": stringify(row.get(columns.area)) or None,
                "lu_id": stringify(row.get(columns.lu)) or None,
                "sloy_id": stringify(row.get(columns.sloy)) or None,
                "well_pad_id": stringify(row.get(columns.well_pad)) or None,
                "infrastructure_object_id": None,
                "planned_start_date": start_date,
                "planned_end_date": end_date,
                "duration_days": duration_days,
                "planned_work": planned_work,
                "expected_oil_increment": coerce_float(row.get(columns.increment)),
                "expected_liquid_increment": coerce_float(row.get(columns.liquid_increment)),
                "expected_gas_increment": coerce_float(row.get(columns.gas_increment)),
                "expected_gor_change": coerce_float(row.get(columns.gor_change)),
                "status": "imported",
                "metadata": {"source_row_number": row_number},
            }
        )

    report.row_count = len(items)
    return {
        "schedule": {
            "scenario_id": None,
            "name": report.original_name or "Imported external KRS schedule",
            "items": items,
            "brigade_count": len({item["brigade"] for item in items if item.get("brigade")}),
            "summary": {
                "row_count": len(items),
                "min_date": min((item["planned_start_date"] for item in items), default=None),
                "max_date": max((item["planned_end_date"] for item in items), default=None),
            },
        },
        "source_format": None,
        "source_file_name": report.original_name,
        "metadata": {"source_kind": "external_krs_schedule"},
    }


def validate_hierarchy(items: list[dict[str, Any]], report: ImportValidationReport) -> None:
    for item in items:
        row_number = None
        metadata = item.get("metadata")
        if isinstance(metadata, dict):
            row_number = metadata.get("source_row_number")

        if item.get("sloy_id") and not item.get("lu_id"):
            _warning(report, "Указан SLOY без LU.", row_number=row_number, field_name="sloy_id")
        if item.get("well_pad_id") and not item.get("lu_id"):
            _warning(report, "Указан WellPad без LU.", row_number=row_number, field_name="well_pad_id")
