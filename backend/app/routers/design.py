"""题目设计：调 Cursor CLI 跑 /solo-prompt，产出自动导入并查重。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.db import session
from app.events import bus, sse_format
from app.models import DesignRun, Task
from app.schemas import DesignStart, IdList, design_run, task_brief
from app.services import designer, settings_store

router = APIRouter(prefix="/api/design", tags=["design"])


@router.get("/preflight")
async def preflight() -> dict:
    checks = designer.preflight()
    return {"checks": checks, "ready": all(c["ok"] for c in checks),
            "default_count": settings_store.get_int("design.count", 5),
            "auto_dedup": settings_store.get_bool("design.auto_dedup", True)}


@router.post("/start")
async def start(body: DesignStart) -> dict:
    blocking = [c for c in designer.preflight() if not c["ok"] and c["name"] in ("cursor_cli", "cursor_key", "skill", "requirements")]
    if blocking:
        raise HTTPException(409, "缺少必要条件：" + "；".join(f"{c['name']} {c['message']}" for c in blocking))
    res = designer.start(body.count, body.note)
    if not res.get("ok"):
        raise HTTPException(409, res.get("error", "无法启动"))
    return res


@router.get("")
async def list_runs(limit: int = 20) -> dict:
    with session() as db:
        rows = db.execute(select(DesignRun).order_by(DesignRun.id.desc()).limit(limit)).scalars().all()
        return {"items": [design_run(r) for r in rows], "running": sorted(designer.running)}


@router.get("/events")
async def events() -> StreamingResponse:
    async def gen():
        async for payload in bus.subscribe("design"):
            yield sse_format(payload)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/dedup")
async def dedup(body: IdList) -> dict:
    """对指定题目重跑规则 A+C。用于查重失败后重试。"""
    if not body.ids:
        raise HTTPException(400, "没有指定题目")
    passed, discarded, err = await designer.dedup_tasks(body.ids)
    if err:
        raise HTTPException(502, err)
    return {"ok": True, "passed": passed, "discarded": discarded}


@router.get("/{run_id}")
async def get_run(run_id: int) -> dict:
    with session() as db:
        r = db.get(DesignRun, run_id)
        if r is None:
            raise HTTPException(404, "设计任务不存在")
        d = design_run(r)
        ids = r.task_ids
        d["tasks"] = [task_brief(t) for t in
                      db.execute(select(Task).where(Task.id.in_(ids or [-1]))).scalars()]
    return d


@router.post("/{run_id}/cancel")
async def cancel(run_id: int) -> dict:
    res = designer.cancel(run_id)
    if not res.get("ok"):
        raise HTTPException(409, res.get("error", "无法取消"))
    return res
