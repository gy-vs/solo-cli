"""健康检查、总览状态、连通性探测、全局事件流。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app import config
from app.db import session
from app.events import bus, sse_format
from app.models import ALL_STATUSES, Task
from app.services import analyzer, designer, dockerx, pipeline, qa_bridge, settings_store, uploader
from app.services.scheduler import scheduler

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "solo-cli-backend"}


@router.get("/system/status")
async def system_status() -> dict:
    docker_ok, docker_msg = await dockerx.daemon_ok()
    image = settings_store.get("cc.image")
    image_ok = await dockerx.image_present(image) if docker_ok else False
    with session() as db:
        counts = {s: 0 for s in ALL_STATUSES}
        for status, n in db.execute(select(Task.status, func.count()).group_by(Task.status)):
            counts[status] = n
        cst = timezone(timedelta(hours=8))
        today = datetime.now(cst).date()

        def _is_today(dt) -> bool:  # noqa: ANN001
            if dt is None:
                return False
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(cst).date() == today

        rows = db.execute(select(Task.finished_at, Task.uploaded_at)).all()
        finished_today = sum(1 for f, _ in rows if _is_today(f))
        uploaded_today = sum(1 for _, u in rows if _is_today(u))
        today = today.isoformat()
    containers = await dockerx.list_task_containers() if docker_ok else []
    qc_ok, qc_why = qa_bridge.available()
    return {
        "docker": {"ok": docker_ok, "message": docker_msg},
        "image": {"name": image, "present": image_ok},
        "scheduler": scheduler.snapshot(),
        "pipeline": {
            **pipeline.snapshot(),
            "destroy": settings_store.get_bool("auto.destroy_on_finish", True),
            "analyze": settings_store.get_bool("auto.analyze", True),
            "qc": settings_store.get_bool("auto.qc", True),
        },
        "qc": {"ok": qc_ok, "message": qc_why or "已启用", "image": settings_store.get("qc.image")},
        "design": {"running": sorted(designer.running)},
        "counts": counts,
        "totals": {"finished": finished_today, "uploaded": uploaded_today, "date": today},
        "containers": containers,
        "configured": {
            "cc.api_key": settings_store.is_configured("cc.api_key"),
            "qa.session_cookie": settings_store.is_configured("qa.session_cookie"),
            "qa.csrf_token": settings_store.is_configured("qa.csrf_token"),
            "cursor.api_key": settings_store.is_configured("cursor.api_key"),
        },
        "paths": {"coder_root_host": config.CODER_ROOT_HOST, "coder_root_mount": str(config.CODER_ROOT_MOUNT),
                  "prompt_file": str(config.prompt_file()), "prompt_exists": config.prompt_file().exists()},
    }


@router.post("/system/probe/{target}")
async def probe(target: str) -> dict:
    if target == "qa":
        return await uploader.probe_identity()
    if target == "gateway":
        return await uploader.probe_gateway()
    if target == "cursor":
        return await analyzer.probe_ping()
    if target == "qc":
        return await qa_bridge.probe()
    if target == "docker":
        ok, msg = await dockerx.daemon_ok()
        if ok:
            image = settings_store.get("cc.image")
            present = await dockerx.image_present(image)
            version = await dockerx.claude_version(image) if present else ""
            return {"ok": present, "message": f"Docker {msg} · 镜像{'就绪 CLI ' + version if present else '缺失：' + image}"}
        return {"ok": False, "message": msg}
    raise HTTPException(404, "未知探测目标")


@router.get("/events")
async def global_events() -> StreamingResponse:
    async def gen():
        yield sse_format({"type": "hello"})
        async for item in bus.subscribe("tasks"):
            yield sse_format(item)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
