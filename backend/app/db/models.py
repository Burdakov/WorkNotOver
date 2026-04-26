from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid4())


class UploadedFileModel(Base):
    __tablename__ = "uploaded_files"

    file_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    original_name: Mapped[str] = mapped_column(String(512))
    stored_path: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=datetime.utcnow)
    sheets_json: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)


class DatasetModel(Base):
    __tablename__ = "datasets"

    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    dataset_type: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255))
    source_format: Mapped[str] = mapped_column(String(32))
    source_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)

    versions: Mapped[list["DatasetVersionModel"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class DatasetVersionModel(Base):
    __tablename__ = "dataset_versions"

    dataset_version_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.dataset_id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer())
    schema_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    row_count: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    stored_at: Mapped[datetime] = mapped_column(DateTime(), default=datetime.utcnow)
    storage_backend: Mapped[str] = mapped_column(String(64), default="database")
    validation_report_json: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)
    normalized_payload_json: Mapped[dict[str, object] | list[dict[str, object]] | None] = mapped_column(
        JSON(),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)

    dataset: Mapped[DatasetModel] = relationship(back_populates="versions")


class ManualInputSetModel(Base):
    __tablename__ = "manual_input_sets"

    manual_input_set_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON())
    metadata_json: Mapped[dict[str, object] | None] = mapped_column(JSON(), nullable=True)
