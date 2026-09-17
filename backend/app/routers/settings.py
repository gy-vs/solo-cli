from __future__ import annotations

from fastapi import APIRouter

from app.schemas import SettingsUpdate
from app.services import gsb_analyzer, settings_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings() -> dict:
    return {"items": settings_store.all_for_ui()}


@router.put("")
async def put_settings(body: SettingsUpdate) -> dict:
    written = settings_store.set_many(body.values)
    return {"written": written, "items": settings_store.all_for_ui()}


@router.get("/models")
async def list_models() -> dict:
    models = await gsb_analyzer.probe_models()
    source = "live"
    if not models:
        models, source = gsb_analyzer.STATIC_MODELS, "static"
    current = settings_store.get("cursor.model")
    if current and current not in models:
        models = [current, *models]
    return {"models": models, "source": source, "current": current}
