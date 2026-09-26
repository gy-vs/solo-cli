"""录屏录制处理：出题端看文档生成与回收进度，录屏端认领、看文档、回传视频。"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app import config
from app.services import rec_repo, recording

router = APIRouter(prefix="/api/rec", tags=["recording"])


class KeyBody(BaseModel):
    key: str


def _raise(res: dict, code: int = 409) -> dict:
    if not res.get("ok"):
        raise HTTPException(code, res.get("message") or "操作失败")
    return res


@router.get("")
async def overview() -> dict:
    return recording.overview()


@router.post("/sync")
async def sync() -> dict:
    """立即同步一次。出题端顺带跑一遍巡检（收视频、撤回、排生成），不等下一轮。"""
    if recording.producer_active():
        stats = await recording.scan()
        if stats.get("error"):
            raise HTTPException(409, stats["error"])
        return {"ok": True, "stats": stats}
    return _raise(await rec_repo.sync())


@router.post("/tasks/{task_id}/generate")
async def generate(task_id: int) -> dict:
    return _raise(recording.start_generate(task_id, force=True))


@router.post("/tasks/{task_id}/withdraw")
async def withdraw(task_id: int) -> dict:
    return _raise(await recording.withdraw_task(task_id))


@router.get("/tasks/{task_id}/report", response_class=PlainTextResponse)
async def local_report(task_id: int) -> str:
    """出题端看本机生成的文档（不必去仓库拉）。"""
    from app.db import session
    from app.models import Task

    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            raise HTTPException(404, "题目不存在")
        no = task.task_no
    path = config.TaskPaths(no).analysis / "screencast-report.md"
    if not path.is_file():
        raise HTTPException(404, "这道题还没有生成录屏文档")
    return path.read_text(encoding="utf-8")


@router.post("/claim")
async def claim(body: KeyBody) -> dict:
    return _raise(await recording.claim(body.key))


@router.get("/report")
async def report(key: str) -> dict:
    return _raise(await recording.report(key), 404)


@router.post("/release")
async def release(body: KeyBody) -> dict:
    return _raise(await recording.release(body.key))


@router.post("/videos")
async def videos(key: str = Form(...),
                 a: UploadFile | None = File(default=None), b: UploadFile | None = File(default=None),
                 a_path: str = Form(default=""), b_path: str = Form(default="")) -> dict:
    """回传两侧视频。浏览器直传文件，或者给后端能读到的路径（宿主机代理录在 reports/ 下的那份）。"""
    with tempfile.TemporaryDirectory(dir=rec_repo.scratch_dir(), prefix="form-") as tmp:
        files: dict[str, Path] = {}
        for side, up, path in (("A", a, a_path), ("B", b, b_path)):
            if up is not None and up.filename:
                dst = Path(tmp) / f"{side}{Path(up.filename).suffix.lower() or '.mp4'}"
                with dst.open("wb") as fp:
                    shutil.copyfileobj(up.file, fp)
                files[side] = dst
            elif path.strip():
                files[side] = Path(path.strip()).expanduser()
        return _raise(await recording.submit_videos(key, files), 400)
