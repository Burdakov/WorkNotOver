from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.forecast import router as forecast_router
from app.api.import_api import router as import_router
from app.api.manual_inputs import router as manual_inputs_router
from app.api.planner import router as planner_router
from app.api.scenarios import router as scenarios_router
from app.api.schedule import router as schedule_router
from app.db.session import init_db

app = FastAPI(title="WorkNotOver API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(import_router)
app.include_router(manual_inputs_router)
app.include_router(schedule_router)
app.include_router(planner_router)
app.include_router(scenarios_router)
app.include_router(forecast_router)
