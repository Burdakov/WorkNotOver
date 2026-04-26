from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ManualInputSetModel
from app.schemas.common import ManualInputReference


class ManualInputRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, name: str, payload: dict, created_by: str | None, metadata: dict | None) -> ManualInputReference:
        item = ManualInputSetModel(
            name=name,
            status="active",
            created_by=created_by,
            payload_json=payload,
            metadata_json=metadata,
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return ManualInputReference(
            manual_input_set_id=item.manual_input_set_id,
            name=item.name,
            created_at=item.created_at.isoformat(),
            metadata=item.metadata_json,
        )

    def get_payload(self, manual_input_set_id: str) -> ManualInputSetModel | None:
        return self.session.get(ManualInputSetModel, manual_input_set_id)
