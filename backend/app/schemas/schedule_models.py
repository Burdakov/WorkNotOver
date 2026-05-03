from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.schemas.common import DatasetReference


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


class ImportedScheduleOpenRequest(BaseModel):
    dataset_id: str
    dataset_version_id: str | None = None


class ImportedScheduleOpenResponse(BaseModel):
    dataset_reference: DatasetReference
    version_name: str
    source_file_name: str | None = None
    source_format: str | None = None
    items: list[ScheduleItem]
    min_date: str | None = None
    max_date: str | None = None
    brigade_count: int = 0
    skipped_rows: int = 0


class GenericRowPayload(BaseModel):
    data: dict[str, Any]


class PlannerRevisionCreateRequest(BaseModel):
    parent_scenario_id: str
    version_name: str
    items: list[ScheduleItem]
    planner_version_id: str | None = None
    editor: str | None = None
    metadata: dict[str, Any] | None = None


class PlannerRevisionResponse(BaseModel):
    revision_id: str
    parent_scenario_id: str
    version_name: str
    planner_version_id: str | None = None
    edited_at: str
    editor: str | None = None
    item_count: int = 0
    metadata: dict[str, Any] | None = None
    items: list[ScheduleItem]
