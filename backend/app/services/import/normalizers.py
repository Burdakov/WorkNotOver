from __future__ import annotations

from typing import Any

import pandas as pd

from app.schemas.common import ImportValidationReport, ValidationIssue
from app.schemas.import_models import NormalizeColumns
from app.services.import.excel_utils import coerce_date, coerce_float, normalize_text, stringify

_HINTS: dict[str, list[str]] = {
    "well": ["скв", "скваж", "well"],
    "area": ["участок", "area"],
    "lu": ["лу", "lu", "участок недр"],
    "sloy": ["слой", "пласт", "sloy"],
    "well_pad": ["куст", "wellpad", "well_pad"],
    "brigade": ["бригада", "brigade"],
    "start_date": ["дата начала", "начало", "start"],
    "end_date": ["заверш", "оконч", "конец", "end"],
    "planned_work": ["планируемый объем работ", "планируемый объём работ", "объем работ", "объём работ", "мероприят"],
    "increment": ["qн", "qh", "прирост нефти", "нефть"],
    "gas_increment": ["газ", "qг", "qg", "прирост газа"],
    "gor_change": ["газовый фактор", "gor"],
    "oil_rate": ["дебит нефти", "oil rate", "qн"],
    "gas_rate": ["дебит газа", "gas rate", "qг", "qg"],
    "liquid_rate": ["дебит жидкости", "liquid rate", "qж"],
    "watercut": ["обводнен", "watercut"],
    "gor": ["газовый фактор", "gor"],
    "cumulative_oil": ["накоплен", "добыча нефти"],
    "cumulative_gas": ["накоплен", "добыча газа"],
    "niz": ["низ", "извлекаемых запасов"],
    "gtm_type": ["гтм", "gtm type", "тип гтм"],
    "duration_days": ["длитель", "duration"],
    "object_name": ["объект", "наименование объекта"],
    "object_type": ["тип объекта"],
    "commissioning_date": ["ввод", "дата ввода"],
    "capacity_oil": ["мощн", "нефть"],
    "capacity_gas": ["мощн", "газ"],
    "capacity_liquid": ["мощн", "жидк"],
    "capacity_water": ["мощн", "вода"],
    "connection_well": ["скв", "скваж"],
    "parent_object": ["родител", "parent"],
}


def resolve_columns(df: pd.DataFrame, provided: NormalizeColumns | None, source_kind: str) -> NormalizeColumns:
    provided = provided or NormalizeColumns()
    columns = [str(column) for column in df.columns]
    normalized = {column: normalize_text(column) for column in columns}
    resolved: dict[str, str | None] = {}

    required_map = {
        "wells": ["well", "oil_rate", "liquid_rate"],
        "gtm": ["well", "planned_work"],
        "infrastructure": ["object_name", "object_type"],
    }

    for key, hints in _HINTS.items():
        explicit = getattr(provided, key)
        if explicit:
            if explicit not in columns:
                raise ValueError(f"Колонка '{explicit}' не найдена.")
            resolved[key] = explicit
            continue
        match = next((column for column in columns if all(part in normalized[column] for part in hints[:1])), None)
        if match is None:
            match = next((column for column in columns if any(hint in normalized[column] for hint in hints)), None)
        resolved[key] = match

    missing = [key for key in required_map.get(source_kind, []) if not resolved.get(key)]
    if missing:
        raise ValueError(f"Не удалось автоматически определить обязательные колонки: {', '.join(missing)}")
    return NormalizeColumns(**resolved)


def normalize_wells(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        well_name = stringify(row.get(columns.well))
        if not well_name:
            continue
        items.append(
            {
                "well_id": f"well-{index + 2}",
                "well_name": well_name,
                "area": stringify(row.get(columns.area)),
                "lu_id": stringify(row.get(columns.lu)) or None,
                "sloy_id": stringify(row.get(columns.sloy)) or None,
                "well_pad_id": stringify(row.get(columns.well_pad)) or None,
                "infrastructure_object_id": None,
                "brigade": stringify(row.get(columns.brigade)) or None,
                "fund_type": None,
                "status": None,
                "current_oil_rate": coerce_float(row.get(columns.oil_rate)),
                "current_gas_rate": coerce_float(row.get(columns.gas_rate)),
                "current_liquid_rate": coerce_float(row.get(columns.liquid_rate)),
                "current_watercut": coerce_float(row.get(columns.watercut)),
                "current_gor": coerce_float(row.get(columns.gor)),
                "current_cumulative_oil": coerce_float(row.get(columns.cumulative_oil)),
                "current_cumulative_gas": coerce_float(row.get(columns.cumulative_gas)),
                "current_cumulative_liquid": None,
                "niz": coerce_float(row.get(columns.niz)),
                "reserves_group": None,
                "launch_date": None,
                "metadata": {"source_row_number": index + 2},
            }
        )
    report.row_count = len(items)
    return items


def normalize_gtm(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        well_name = stringify(row.get(columns.well))
        planned_work = stringify(row.get(columns.planned_work))
        if not well_name and not planned_work:
            continue
        items.append(
            {
                "gtm_id": f"gtm-{index + 2}",
                "well_id": f"well-ref-{normalize_text(well_name) or index + 2}",
                "well_name": well_name,
                "area": stringify(row.get(columns.area)),
                "lu_id": stringify(row.get(columns.lu)) or None,
                "sloy_id": stringify(row.get(columns.sloy)) or None,
                "well_pad_id": stringify(row.get(columns.well_pad)) or None,
                "infrastructure_object_id": None,
                "brigade": stringify(row.get(columns.brigade)) or None,
                "gtm_type": stringify(row.get(columns.gtm_type)) or "unknown",
                "planned_work": planned_work,
                "candidate_start_date": coerce_date(row.get(columns.start_date)),
                "candidate_end_date": coerce_date(row.get(columns.end_date)),
                "duration_days": int(coerce_float(row.get(columns.duration_days)) or 0) or None,
                "expected_oil_increment": coerce_float(row.get(columns.increment)),
                "expected_gas_increment": coerce_float(row.get(columns.gas_increment)),
                "expected_liquid_increment": None,
                "expected_watercut_change": None,
                "expected_gor_change": coerce_float(row.get(columns.gor_change)),
                "priority": None,
                "source_row_number": index + 2,
                "metadata": None,
            }
        )
    report.row_count = len(items)
    return items


def normalize_infrastructure(df: pd.DataFrame, columns: NormalizeColumns, report: ImportValidationReport) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    connections: list[dict[str, Any]] = []

    for index, row in df.iterrows():
        object_name = stringify(row.get(columns.object_name))
        if not object_name:
            continue
        object_id = f"infra-{index + 2}"
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
                "metadata": {"source_row_number": index + 2},
            }
        )
        well_name = stringify(row.get(columns.connection_well))
        if well_name:
            connections.append(
                {
                    "connection_id": f"conn-{index + 2}",
                    "well_id": f"well-ref-{normalize_text(well_name)}",
                    "object_id": object_id,
                    "start_date": None,
                    "end_date": None,
                    "priority": None,
                    "metadata": None,
                }
            )

    report.row_count = len(objects)
    return {"objects": objects, "connections": connections}


def validate_hierarchy(items: list[dict[str, Any]], report: ImportValidationReport) -> None:
    for item in items:
        if item.get("sloy_id") and not item.get("lu_id"):
            report.warnings.append(
                ValidationIssue(
                    level="warning",
                    message="Указан SLOY без LU; иерархия может быть неполной.",
                    row_number=item.get("metadata", {}).get("source_row_number"),
                    field_name="sloy_id",
                )
            )
