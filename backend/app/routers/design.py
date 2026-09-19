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
from app.services import designer, pool, pool_bank, settings_store

router = APIRouter(prefix="/api/design", tags=["design"])


@router.get("/preflight")
async def preflight() -> dict:
    checks = designer.preflight()
    return {"checks": checks, "ready": all(c["ok"] for c in checks),
            "default_count": settings_store.get_int("design.count", 5),
            "auto_dedup": settings_store.get_bool("design.auto_dedup", True)}


@router.post("/start")
async def start(body: DesignStart) -> dict:
    # 少了这几样出题必然失败：模型调不通、建不了仓库、或者读不到本期口径。
    # 查重不在列，它失败只是把题留着等人工判，不影响出题本身。
    blocking = [c for c in designer.preflight()
                if not c["ok"] and c["name"] in ("cursor_cli", "cursor_key", "gh", "gh_token", "requirements")]
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


# ---------------- 跨设备题库 ----------------

@router.get("/pool")
async def pool_status() -> dict:
    return pool.snapshot()


@router.post("/pool/sync")
async def pool_sync() -> dict:
    """拉一次远端池，并把题库索引按池重建。出题时会自动做，这里是手动触发。"""
    res = await pool.sync()
    if not res["ok"]:
        raise HTTPException(409, res["message"])
    return {**res, "index": pool.write_index(), "pool": pool.snapshot()}


@router.post("/pool/bootstrap")
async def pool_bootstrap() -> dict:
    """把本机已有的题一次性推上远端题库。第一次启用时用。

    幂等：已经在上面的题会被跳过，重复点不会写重复行。推完顺带投影一次，让本机的题
    立刻带上远端条目 id —— 没有它的题领取时绕过跨设备独占，另一台设备照样能领。
    """
    res = await pool.bootstrap()
    if not res["ok"]:
        raise HTTPException(409, res["message"])
    linked = pool_bank.sync_tasks()
    return {**res, "linked": len(linked["adopted"]), "pool": pool.snapshot()}


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
