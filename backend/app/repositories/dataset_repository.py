from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DatasetModel, DatasetVersionModel, UploadedFileModel
from app.schemas.common import DatasetReference


class DatasetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_uploaded_file(self, file_id: str, original_name: str, stored_path: str, sheets: list[str]) -> UploadedFileModel:
        uploaded = self.session.get(UploadedFileModel, file_id)
        if uploaded is None:
            uploaded = UploadedFileModel(
                file_id=file_id,
                original_name=original_name,
                stored_path=stored_path,
                sheets_json=sheets,
            )
            self.session.add(uploaded)
        else:
            uploaded.original_name = original_name
            uploaded.stored_path = stored_path
            uploaded.sheets_json = sheets
        self.session.commit()
        self.session.refresh(uploaded)
        return uploaded

    def list_uploaded_files(self) -> list[UploadedFileModel]:
        stmt = select(UploadedFileModel).order_by(UploadedFileModel.created_at.desc())
        return list(self.session.scalars(stmt))

    def list_datasets(self) -> list[tuple[DatasetModel, DatasetVersionModel | None]]:
        stmt = select(DatasetModel).order_by(DatasetModel.created_at.desc())
        datasets = list(self.session.scalars(stmt))
        return [(dataset, self._get_active_version(dataset.dataset_id)) for dataset in datasets]

    def get_dataset_version(
        self,
        dataset_id: str,
        dataset_version_id: str | None = None,
    ) -> tuple[DatasetModel, DatasetVersionModel] | None:
        dataset = self.session.get(DatasetModel, dataset_id)
        if dataset is None:
            return None

        if dataset_version_id:
            version = self.session.get(DatasetVersionModel, dataset_version_id)
            if version is None or version.dataset_id != dataset_id:
                return None
            return dataset, version

        version = self._get_active_version(dataset_id)
        if version is None:
            return None
        return dataset, version

    def create_dataset_version(
        self,
        *,
        dataset_type: str,
        name: str,
        source_format: str,
        source_file_name: str | None,
        normalized_payload: dict[str, Any] | list[dict[str, Any]],
        validation_report: dict[str, Any],
        row_count: int,
        metadata: dict[str, Any] | None = None,
        dataset_id: str | None = None,
    ) -> DatasetReference:
        dataset = self.session.get(DatasetModel, dataset_id) if dataset_id else None
        if dataset is None:
            dataset = DatasetModel(
                dataset_type=dataset_type,
                name=name,
                source_format=source_format,
                source_file_name=source_file_name,
                status="active",
                metadata_json=metadata,
            )
            self.session.add(dataset)
            self.session.flush()
            version_number = 1
        else:
            if dataset.dataset_type != dataset_type:
                raise ValueError(f"Dataset '{dataset.dataset_id}' has type '{dataset.dataset_type}', expected '{dataset_type}'.")
            dataset.name = name
            dataset.source_format = source_format
            dataset.source_file_name = source_file_name
            dataset.status = "active"
            dataset.metadata_json = metadata
            version_number = self._next_version_number(dataset.dataset_id)
            active_version = self._get_active_version(dataset.dataset_id)
            if active_version is not None:
                active_version.is_active = False

        version = DatasetVersionModel(
            dataset_id=dataset.dataset_id,
            version_number=version_number,
            schema_version="1.0",
            row_count=row_count,
            stored_at=datetime.utcnow(),
            storage_backend="database",
            validation_report_json=validation_report,
            normalized_payload_json=normalized_payload,
            is_active=True,
            metadata_json=metadata,
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(dataset)
        self.session.refresh(version)

        return DatasetReference(
            dataset_id=dataset.dataset_id,
            dataset_version_id=version.dataset_version_id,
            dataset_type=dataset.dataset_type,
            name=dataset.name,
            row_count=version.row_count,
            created_at=dataset.created_at.isoformat(),
            metadata=dataset.metadata_json,
        )

    def _get_active_version(self, dataset_id: str) -> DatasetVersionModel | None:
        stmt = (
            select(DatasetVersionModel)
            .where(DatasetVersionModel.dataset_id == dataset_id)
            .where(DatasetVersionModel.is_active.is_(True))
            .order_by(DatasetVersionModel.version_number.desc(), DatasetVersionModel.stored_at.desc())
        )
        return self.session.scalars(stmt).first()

    def _next_version_number(self, dataset_id: str) -> int:
        stmt = (
            select(DatasetVersionModel.version_number)
            .where(DatasetVersionModel.dataset_id == dataset_id)
            .order_by(DatasetVersionModel.version_number.desc())
        )
        latest = self.session.scalars(stmt).first()
        return (latest or 0) + 1
