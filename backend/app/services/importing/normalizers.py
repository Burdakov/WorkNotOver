from __future__ import annotations

import re
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
    "date": ["date", "дата"],
    "producer_id": ["producer"],
    "injector_id": ["injector"],
    "q_oil": ["q_oil", "oil", "дебит нефти"],
    "q_water": ["q_water", "water", "дебит воды"],
    "q_liq": ["q_liq", "liquid", "дебит жидкости"],
    "q_gas": ["q_gas", "gas", "дебит газа"],
    "q_water_inj": ["inj", "water injection", "закачка воды"],
    "bhp": ["bhp", "рзаб"],
    "thp": ["thp"],
    "whp": ["whp", "wellhead"],
    "p_res": ["p_res", "рпл"],
    "wefac": ["кэкспл", "wefac"],
    "md": ["md", "measured depth"],
    "top_md": ["top md"],
    "bottom_md": ["bottom md"],
    "x": ["x"],
    "y": ["y"],
    "z": ["z", "tvd"],
    "trajectory_point_id": ["trajectory", "point id"],
    "perforation_id": ["perforation", "perf"],
}

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "wells": ("well", "lu", "well_pad", "fund_state", "oil_rate", "liquid_rate", "watercut"),
    "well_groups": ("well", "well_pad"),
    "niz": ("well", "lu", "well_pad", "niz"),
    "gtm": ("well", "lu", "sloy", "well_pad", "gtm_type", "start_date", "end_date", "increment", "liquid_increment"),
    "infrastructure": ("object_name", "object_type"),
    "external_krs_schedule": ("brigade", "well", "start_date", "end_date", "planned_work"),
    "well_trajectories": ("well", "md", "x", "y", "z"),
    "perforations": ("well", "top_md", "bottom_md"),
    "production_history": ("date", "well", "q_oil"),
    "injection_history": ("date", "well", "q_water_inj"),
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


def _upper_text(value: Any) -> str:
    return stringify(value).upper()


def _upper_or_none(value: Any) -> str | None:
    text = _upper_text(value)
    return text or None


def _upper_well_name(value: Any) -> str:
    return _upper_text(value)


def _parse_number_token(value: Any) -> float | None:
    raw = stringify(value).replace(",", ".")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _source_lines_from_text_df(df: pd.DataFrame) -> list[str]:
    if "text" not in df.columns:
        return []
    return [stringify(value) for value in df["text"].tolist()]


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
    seen_keys: set[tuple[str, str, str]] = set()

    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        well_name = _upper_well_name(_extract_effective_well_name(row, columns.well))
        if not well_name:
            continue
        lu_id = _upper_or_none(row.get(columns.lu))
        sloy_id = _upper_or_none(row.get(columns.sloy))
        well_pad_id = _upper_or_none(row.get(columns.well_pad))
        dedupe_key = (lu_id or "", well_pad_id or "", well_name)
        if dedupe_key in seen_keys:
            report.skipped_rows += 1
            _warning(
                report,
                "Строка wells пропущена: дублирующаяся скважина в пределах LU/куста.",
                row_number=row_number,
                field_name="well",
            )
            continue
        seen_keys.add(dedupe_key)

        items.append(
            {
                "well_id": _stable_well_id(well_name, row_number),
                "well_name": well_name,
                "area": None,
                "lu_id": lu_id,
                "sloy_id": sloy_id,
                "well_pad_id": well_pad_id,
                "infrastructure_object_id": None,
                "brigade": None,
                "fund_type": "Base",
                "fund_state": _upper_or_none(_normalize_fund_state(row.get(columns.fund_state))),
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
    seen_keys: set[tuple[str, str, str]] = set()

    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        source_well_name = _upper_well_name(row.get(columns.well))
        lu_id = _upper_text(row.get(columns.lu))
        well_pad_id = _upper_text(row.get(columns.well_pad))
        niz = coerce_float(row.get(columns.niz))
        well_name = _upper_well_name(row_matches.get(row_number)) or source_well_name

        if not source_well_name and not lu_id and not well_pad_id and (niz or 0.0) <= 0:
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

        if (niz or 0.0) <= 0:
            report.skipped_rows += 1
            _warning(report, "Строка NIZ пропущена: значение NIZ должно быть больше нуля.", row_number=row_number, field_name="niz")
            continue

        dedupe_key = (lu_id, well_pad_id, well_name)
        if dedupe_key in seen_keys:
            report.skipped_rows += 1
            _warning(
                report,
                "Строка NIZ пропущена: дублирующаяся скважина в пределах LU/куста после сопоставления.",
                row_number=row_number,
                field_name="well",
            )
            continue
        seen_keys.add(dedupe_key)

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
        well_name = _upper_well_name(entry.get("well_name"))
        lu_id = _upper_text(entry.get("lu_id"))
        well_pad_id = _upper_text(entry.get("well_pad_id"))
        niz = coerce_float(entry.get("niz"))
        if not well_name or not lu_id or not well_pad_id or (niz or 0.0) <= 0:
            continue
        dedupe_key = (lu_id, well_pad_id, well_name)
        if dedupe_key in seen_keys:
            _warning(
                report,
                "Ручная строка NIZ пропущена: для этой скважины значение уже существует.",
                field_name="well",
            )
            continue
        seen_keys.add(dedupe_key)
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


def normalize_gtm(
    df: pd.DataFrame,
    columns: NormalizeColumns,
    report: ImportValidationReport,
    row_matches: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    row_matches = row_matches or {}

    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        source_well_name = _upper_well_name(_extract_effective_well_name(row, columns.well))
        well_name = _upper_well_name(row_matches.get(row_number)) or source_well_name
        planned_work = stringify(row.get(columns.planned_work))
        if not source_well_name and not planned_work:
            continue

        candidate_start = coerce_date(row.get(columns.start_date))
        candidate_end = coerce_date(row.get(columns.end_date)) or candidate_start
        duration_days = int(coerce_float(row.get(columns.duration_days)) or 0) or None

        items.append(
            {
                "gtm_id": f"gtm::{row_number}",
                "well_id": _stable_well_id(well_name, row_number),
                "well_name": well_name,
                "area": _upper_or_none(row.get(columns.area)),
                "lu_id": _upper_or_none(row.get(columns.lu)),
                "sloy_id": _upper_or_none(row.get(columns.sloy)),
                "well_pad_id": _upper_or_none(row.get(columns.well_pad)),
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
                "metadata": {
                    "source_row_number": row_number,
                    "source_well_name": source_well_name,
                    "matched_existing_well": bool(row_matches.get(row_number)),
                    "fund_type_hint": "Base" if row_matches.get(row_number) else "New wells",
                },
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
        well_name = _upper_well_name(_extract_effective_well_name(row, columns.well))
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


def normalize_well_trajectories(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        well_name = _upper_well_name(_extract_effective_well_name(row, columns.well))
        md = coerce_float(row.get(columns.md))
        x = coerce_float(row.get(columns.x))
        y = coerce_float(row.get(columns.y))
        z = coerce_float(row.get(columns.z))
        if not any([well_name, md, x, y, z]):
            continue
        if not well_name or md <= 0:
            report.skipped_rows += 1
            _warning(report, "Trajectory row skipped: missing well or measured depth.", row_number=row_number)
            continue
        items.append(
            {
                "trajectory_point_id": stringify(row.get(columns.trajectory_point_id)) or f"trajectory::{row_number}",
                "well_id": _stable_well_id(well_name, row_number),
                "well_name": well_name,
                "md": md,
                "x": x,
                "y": y,
                "z": z,
                "metadata": {"source_row_number": row_number},
            }
        )
    report.row_count = len(items)
    return items


def normalize_perforations(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        well_name = _upper_well_name(_extract_effective_well_name(row, columns.well))
        top_md = coerce_float(row.get(columns.top_md))
        bottom_md = coerce_float(row.get(columns.bottom_md))
        if not any([well_name, top_md, bottom_md]):
            continue
        if not well_name or top_md <= 0 or bottom_md <= 0:
            report.skipped_rows += 1
            _warning(report, "Perforation row skipped: missing well/top_md/bottom_md.", row_number=row_number)
            continue
        if bottom_md < top_md:
            top_md, bottom_md = bottom_md, top_md
        items.append(
            {
                "perforation_id": stringify(row.get(columns.perforation_id)) or f"perforation::{row_number}",
                "well_id": _stable_well_id(well_name, row_number),
                "well_name": well_name,
                "lu_id": _upper_or_none(row.get(columns.lu)),
                "sloy_id": _upper_or_none(row.get(columns.sloy)),
                "well_pad_id": _upper_or_none(row.get(columns.well_pad)),
                "top_md": top_md,
                "bottom_md": bottom_md,
                "start_date": coerce_date(row.get(columns.start_date)),
                "end_date": coerce_date(row.get(columns.end_date)),
                "metadata": {"source_row_number": row_number},
            }
        )
    report.row_count = len(items)
    return items


def normalize_production_history(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        well_column = columns.well or columns.producer_id
        well_name = _upper_well_name(_extract_effective_well_name(row, well_column))
        date = coerce_date(row.get(columns.date))
        q_oil = coerce_float(row.get(columns.q_oil or columns.oil_rate)) or 0.0
        q_liq = coerce_float(row.get(columns.q_liq or columns.liquid_rate)) or 0.0
        q_water = coerce_float(row.get(columns.q_water)) or 0.0
        if q_water == 0 and q_liq > 0:
            q_water = max(0.0, q_liq - q_oil)
        if not well_name and not date and q_oil <= 0 and q_water <= 0 and q_liq <= 0:
            continue
        if not well_name or not date:
            report.skipped_rows += 1
            _warning(report, "Production history row skipped: missing producer/date.", row_number=row_number)
            continue
        if q_oil <= 0 and q_water <= 0 and q_liq <= 0:
            continue
        items.append(
            {
                "date": date,
                "producer_id": _stable_well_id(well_name, row_number),
                "well_id": _stable_well_id(well_name, row_number),
                "well_name": well_name,
                "q_oil": q_oil,
                "q_water": q_water,
                "q_liq": q_liq or q_oil + q_water,
                "q_gas": coerce_float(row.get(columns.q_gas or columns.gas_rate)),
                "bhp": coerce_float(row.get(columns.bhp)),
                "thp": coerce_float(row.get(columns.thp)),
                "p_res": coerce_float(row.get(columns.p_res)),
                "wefac": coerce_float(row.get(columns.wefac)),
                "metadata": {"source_row_number": row_number, "units": {"rates": "m3/month", "pressure": "bar"}},
            }
        )
    report.row_count = len(items)
    return items


def normalize_injection_history(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        row_number = excel_row_number(df, index)
        well_column = columns.well or columns.injector_id
        well_name = _upper_well_name(_extract_effective_well_name(row, well_column))
        date = coerce_date(row.get(columns.date))
        q_water_inj = coerce_float(row.get(columns.q_water_inj)) or 0.0
        if not well_name and not date and q_water_inj <= 0:
            continue
        if not well_name or not date:
            report.skipped_rows += 1
            _warning(report, "Injection history row skipped: missing injector/date.", row_number=row_number)
            continue
        if q_water_inj <= 0:
            continue
        items.append(
            {
                "date": date,
                "injector_id": _stable_well_id(well_name, row_number),
                "well_id": _stable_well_id(well_name, row_number),
                "well_name": well_name,
                "q_water_inj": q_water_inj,
                "bhp": coerce_float(row.get(columns.bhp)),
                "whp": coerce_float(row.get(columns.whp)),
                "thp": coerce_float(row.get(columns.thp)),
                "p_res": coerce_float(row.get(columns.p_res)),
                "wefac": coerce_float(row.get(columns.wefac)),
                "metadata": {"source_row_number": row_number, "units": {"rates": "m3/month", "pressure": "bar"}},
            }
        )
    report.row_count = len(items)
    return items


def _strip_text_comment(line: str) -> str:
    if "--" in line:
        line = line.split("--", 1)[0]
    return line.strip()


def normalize_well_groups_text(lines: list[str], report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for line_number, line in enumerate(lines, start=1):
        cleaned = _strip_text_comment(line)
        if not cleaned or cleaned.startswith("-"):
            continue
        tokens = cleaned.split()
        if len(tokens) < 3 or tokens[0].upper() != "GROUP":
            continue

        well_name = _upper_well_name(tokens[-1])
        hierarchy = [_upper_text(token) for token in tokens[1:-1] if stringify(token)]
        if not well_name or not hierarchy:
            report.skipped_rows += 1
            _warning(report, "GRUP row skipped: expected GROUP <hierarchy> <well>.", row_number=line_number)
            continue

        well_pad_id = hierarchy[-1]
        sloy_id = hierarchy[-2] if len(hierarchy) >= 2 else None
        lu_id = hierarchy[-3] if len(hierarchy) >= 3 else None
        infrastructure_path = hierarchy[:-3] if len(hierarchy) >= 4 else []
        infrastructure_object_id = infrastructure_path[-1] if infrastructure_path else None
        key = (lu_id or "", well_pad_id or "", well_name)
        if key in seen:
            report.skipped_rows += 1
            _warning(report, "GRUP row skipped: duplicate LU/pad/well mapping.", row_number=line_number)
            continue
        seen.add(key)
        items.append(
            {
                "well_id": _stable_well_id(well_name, line_number),
                "well_name": well_name,
                "lu_id": lu_id,
                "sloy_id": sloy_id,
                "well_pad_id": well_pad_id,
                "infrastructure_object_id": infrastructure_object_id,
                "group_path": hierarchy,
                "metadata": {
                    "source_row_number": line_number,
                    "source_format": "GRUP",
                    "infrastructure_path": infrastructure_path,
                },
            }
        )
    report.row_count = len(items)
    return items


def normalize_well_trajectories_text(lines: list[str], report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current_well = ""
    point_index_by_well: dict[str, int] = {}
    for line_number, line in enumerate(lines, start=1):
        cleaned = _strip_text_comment(line)
        if not cleaned or cleaned.startswith("-"):
            continue
        tokens = cleaned.split()
        if not tokens:
            continue
        if tokens[0].upper() == "WELLTRACK":
            current_well = _upper_well_name(tokens[1]) if len(tokens) >= 2 else ""
            point_index_by_well.setdefault(current_well, 0)
            continue
        if not current_well:
            continue
        if len(tokens) < 4:
            report.skipped_rows += 1
            _warning(report, "TRAJ row skipped: expected X Y Z MD.", row_number=line_number)
            continue
        x = _parse_number_token(tokens[0])
        y = _parse_number_token(tokens[1])
        z = _parse_number_token(tokens[2])
        md = _parse_number_token(tokens[3])
        if x is None or y is None or z is None or md is None:
            report.skipped_rows += 1
            _warning(report, "TRAJ row skipped: non-numeric X/Y/Z/MD.", row_number=line_number)
            continue
        point_index_by_well[current_well] += 1
        point_index = point_index_by_well[current_well]
        items.append(
            {
                "trajectory_point_id": f"trajectory::{current_well}::{point_index}",
                "well_id": _stable_well_id(current_well, line_number),
                "well_name": current_well,
                "x": x,
                "y": y,
                "z": z,
                "md": md,
                "metadata": {
                    "source_row_number": line_number,
                    "source_format": "TRAJ",
                    "column_order": "X,Y,Z,MD",
                },
            }
        )
    report.row_count = len(items)
    return items


def normalize_perforations_text(lines: list[str], report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str, float, float, float | None, float | None, float | None, str | None]] = set()
    for line_number, line in enumerate(lines, start=1):
        cleaned = _strip_text_comment(line)
        if not cleaned or cleaned.startswith("-"):
            continue
        tokens = cleaned.split()
        if len(tokens) < 9:
            continue
        if tokens[2].upper() != "PERF":
            continue

        well_name = _upper_well_name(tokens[0])
        start_date = coerce_date(tokens[1])
        top_md = _parse_number_token(tokens[3])
        bottom_md = _parse_number_token(tokens[4])
        diameter = _parse_number_token(tokens[5])
        skin = _parse_number_token(tokens[6])
        multiplier = _parse_number_token(tokens[7])
        flow_direction = _upper_or_none(tokens[8])
        if not well_name or top_md is None or bottom_md is None:
            report.skipped_rows += 1
            _warning(report, "PERF row skipped: missing well/top_md/bottom_md.", row_number=line_number)
            continue
        if bottom_md < top_md:
            top_md, bottom_md = bottom_md, top_md
        key = (well_name, start_date or "", top_md, bottom_md, diameter, skin, multiplier, flow_direction)
        if key in seen:
            report.skipped_rows += 1
            _warning(report, "PERF row skipped: exact duplicate interval.", row_number=line_number)
            continue
        seen.add(key)
        items.append(
            {
                "perforation_id": f"perforation::{well_name}::{line_number}",
                "well_id": _stable_well_id(well_name, line_number),
                "well_name": well_name,
                "lu_id": None,
                "sloy_id": None,
                "well_pad_id": None,
                "top_md": top_md,
                "bottom_md": bottom_md,
                "start_date": start_date,
                "end_date": None,
                "diameter": diameter,
                "skin": skin,
                "multiplier": multiplier,
                "flow_direction": flow_direction,
                "metadata": {
                    "source_row_number": line_number,
                    "source_format": "PERF",
                    "units": {"md": "m", "diameter": "m"},
                },
            }
        )
    report.row_count = len(items)
    return items


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
