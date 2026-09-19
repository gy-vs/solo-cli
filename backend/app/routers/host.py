"""宿主机动作：在本机把项目跑起来、录 720p 屏。

这些活后端自己干不了——容器里没有 macOS 的屏幕录制权限，在挂载目录上执行命令用的
也是容器自己的 Node/Python。所以本路由只做一件事：查出这道题这一侧该在哪个目录跑
哪些命令，转给宿主机代理执行。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app import config
from app.db import session
from app.models import Task
from app.services import host_agent, project_probe

router = APIRouter(prefix="/api/host", tags=["host"])


def _task(task_id: int) -> tuple[str, dict]:
    """题号与 GSB 结论。取完就脱离会话，免得后面 await 期间还占着连接。"""
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            raise HTTPException(404, "任务不存在")
        return t.task_no, t.gsb


def _side(value: str) -> str:
    s = (value or "").upper()
    if s not in config.SIDES:
        raise HTTPException(400, "side 必须是 A 或 B")
    return s


@router.get("/health")
async def health() -> dict:
    return await host_agent.health()


@router.get("/tasks/{task_id}/plan")
async def record_plan(task_id: int, side: str = Query(...)) -> dict:
    """这一侧是个什么项目、录屏该怎么录。不经过宿主机代理，后端自己看挂载目录就够。"""
    want = _side(side)
    task_no, gsb = _task(task_id)
    startup = gsb.get("a_startup" if want == "A" else "b_startup") or {}
    plan = project_probe.record_plan(task_no, want, [str(c) for c in (startup.get("commands") or [])])
    plan["note"] = startup.get("note", "")
    return plan


@router.post("/tasks/{task_id}/start")
async def start_project(task_id: int, side: str = Query(...)) -> dict:
    """照 GSB 给的启动说明把这一侧跑起来。装依赖的命令代理会自动执行，其余的留给人敲。"""
    want = _side(side)
    task_no, gsb = _task(task_id)
    startup = gsb.get("a_startup" if want == "A" else "b_startup") or {}
    commands = [c for c in (startup.get("commands") or []) if str(c).strip()]
    res = await host_agent.start_project(task_no, want, commands)
    res["note"] = startup.get("note", "")
    res["steps"] = startup.get("steps", [])
    if not res.get("ok"):
        raise HTTPException(400, res.get("message") or "启动失败")
    return res


@router.get("/tasks/{task_id}/status")
async def project_status(task_id: int, side: str = Query(...)) -> dict:
    """这一侧的终端还在不在，跑出来的东西监听了哪些端口。"""
    return await host_agent.project_status(_task(task_id)[0], _side(side))


@router.post("/tasks/{task_id}/record/start")
async def record_start(task_id: int, side: str = Query(...), screen: int = Query(default=0)) -> dict:
    res = await host_agent.start_record(_task(task_id)[0], _side(side), screen)
    if not res.get("ok"):
        raise HTTPException(400, res.get("message") or "录屏启动失败")
    return res


@router.post("/tasks/{task_id}/record/stop")
async def record_stop(task_id: int, side: str = Query(...)) -> dict:
    """停录并交出文件路径。给的是后端可见的挂载路径，能直接喂给录屏上传接口。"""
    res = await host_agent.stop_record(_task(task_id)[0], _side(side))
    if not res.get("ok"):
        raise HTTPException(400, res.get("message") or "停止录屏失败")
    return res
