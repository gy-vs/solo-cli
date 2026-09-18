from __future__ import annotations

from fastapi import APIRouter

from app.schemas import SettingsUpdate
from app.services import llm, settings_store, watchdog

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings() -> dict:
    return {"items": settings_store.all_for_ui()}


@router.put("")
async def put_settings(body: SettingsUpdate) -> dict:
    written = settings_store.set_many(body.values)
    # 换 Key 是个明确的「我把凭据修好了」的动作。分析挂在凭据上的题这时该自己接着跑，
    # 否则人换完 Key 还得回头挨个点一遍重新分析，而这正是这条流水线想省掉的事。
    revived = watchdog.retry_failed_analyses() if "cursor.api_key" in written else []
    return {"written": written, "items": settings_store.all_for_ui(), "revived": revived}


@router.get("/models")
async def list_models() -> dict:
    models = await llm.probe_models()
    source = "live"
    if not models:
        models, source = llm.STATIC_MODELS, "static"
    current = settings_store.get("cursor.model")
    if current and current not in models:
        models = [current, *models]
    return {"models": models, "source": source, "current": current}
