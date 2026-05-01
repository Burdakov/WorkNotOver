from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.manual_input_repository import ManualInputRepository
from app.schemas.import_models import ManualInputSaveRequest, ManualInputSaveResponse

router = APIRouter(prefix="/api/manual-inputs", tags=["manual-inputs"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/save", response_model=ManualInputSaveResponse)
def save_manual_inputs(payload: ManualInputSaveRequest, db: Session = Depends(get_db)) -> ManualInputSaveResponse:
    storage_payload = payload.payload.to_storage_payload()
    reference = ManualInputRepository(db).create(
        name=payload.name,
        payload=storage_payload,
        created_by=payload.created_by,
        metadata=storage_payload.get("metadata"),
    )
    return ManualInputSaveResponse(reference=reference, payload=storage_payload)


@router.get("")
def list_manual_inputs(db: Session = Depends(get_db)) -> list[dict]:
    items = ManualInputRepository(db).list_items()
    return [
        {
            "reference": {
                "manual_input_set_id": item.manual_input_set_id,
                "name": item.name,
                "created_at": item.created_at.isoformat(),
                "metadata": item.metadata_json,
            },
            "payload": item.payload_json,
        }
        for item in items
    ]


@router.get("/{manual_input_set_id}")
def get_manual_inputs(manual_input_set_id: str, db: Session = Depends(get_db)) -> dict:
    item = ManualInputRepository(db).get_payload(manual_input_set_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Набор ручных вводных не найден.")
    return {
        "reference": {
            "manual_input_set_id": item.manual_input_set_id,
            "name": item.name,
            "created_at": item.created_at.isoformat(),
            "metadata": item.metadata_json,
        },
        "payload": item.payload_json,
    }
