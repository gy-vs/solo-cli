"""题库、运行、评审、上传、生命周期。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select

from app import config
from app.db import session
from app.events import bus, sse_format
from app.models import (
    ANALYSIS_RUNNING, ANALYZABLE, AVAILABLE, CLAIMED, DISCARDED, DONE, QC_RUNNING, QUEUED,
    RUN_END_STATUSES, RUNNING, REVIEWED, UPLOADED, RunEvent, Task, utc_now,
)
from app.schemas import ContinueRun, IdList, QueueMove, ReviewUpdate, task_brief, task_detail
from app.services import (
    analyzer, dockerx, gate, pipeline, prompt_bank, qa_bridge, repo, runner, scheduler, task_reset,
    uploader, settings_store,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get(db, task_id: int) -> Task:  # noqa: ANN001
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    return t


# ---------------- 题库 ----------------

@router.post("/import")
async def import_bank() -> dict:
    if not config.prompt_file().exists():
        raise HTTPException(400, f"找不到题库文件 {config.prompt_file()}")
    res = prompt_bank.import_tasks()
    bus.publish("tasks", {"type": "bank"})
    return res


@router.get("")
async def list_tasks(status: str = Query(default=""), exclude_done: bool = Query(default=False),
                     include_discarded: bool = Query(default=False)) -> dict:
    """默认不返回已废弃的题；需要时用 include_discarded 或显式 status=DISCARDED 取。"""
    with session() as db:
        q = select(Task).order_by(Task.task_no, Task.id)
        wanted = [s for s in status.split(",") if s]
        if wanted:
            q = q.where(Task.status.in_(wanted))
        elif not include_discarded:
            q = q.where(Task.status != DISCARDED)
        if exclude_done:
            q = q.where(Task.status != DONE)
        items = [task_brief(t) for t in db.execute(q).scalars()]
    return {"items": items}


# ---------------- 集合操作 ----------------
# 这些路径必须注册在 /{task_id}/… 之前：FastAPI 按注册顺序匹配，
# 先命中 /{task_id}/upload 的话 "batch" 会被当成 task_id 直接 422。

@router.get("/queue/list")
async def queue_list() -> dict:
    with session() as db:
        rows = db.execute(
            select(Task).where(Task.status.in_([QUEUED, RUNNING]))
            .order_by(Task.status.desc(), Task.priority, Task.claimed_at, Task.id)
        ).scalars().all()
        items = [task_brief(t) for t in rows]
    return {"items": items, "scheduler": scheduler.scheduler.snapshot(),
            "pipeline": pipeline.snapshot()}


@router.post("/queue/pause")
async def queue_pause(paused: bool = Query(default=True)) -> dict:
    settings_store.set_one("scheduler.paused", "1" if paused else "0")
    bus.publish("tasks", {"type": "scheduler"})
    return {"ok": True, "paused": paused,
            "message": "已暂停出队，运行中的不受影响" if paused else "已恢复出队"}


@router.post("/queue/parallel")
async def queue_parallel(value: int = Query(...)) -> dict:
    value = max(1, min(10, value))
    settings_store.set_one("scheduler.max_parallel", str(value))
    bus.publish("tasks", {"type": "scheduler"})
    return {"ok": True, "max_parallel": value}


@router.post("/batch/upload")
async def batch_upload(body: IdList) -> dict:
    results = []
    for tid in body.ids:
        res = await uploader.upload_task(tid)
        results.append({"id": tid, **res})
    return {"results": results}


@router.post("/batch/claim")
async def batch_claim(body: IdList) -> dict:
    results = []
    for tid in body.ids:
        try:
            results.append({"id": tid, **(await claim(tid))})
        except HTTPException as exc:
            results.append({"id": tid, "queued": False, "error": exc.detail})
    return {"results": results}


@router.post("/batch/qc")
async def batch_qc(body: IdList) -> dict:
    for tid in body.ids:
        asyncio.create_task(pipeline.run_qc(tid))
    return {"ok": True, "started": len(body.ids)}


@router.get("/{task_id}")
async def get_task(task_id: int) -> dict:
    with session() as db:
        return task_detail(_get(db, task_id))


# ---------------- 领取 / 门禁 / 启动 ----------------

@router.post("/{task_id}/gate")
async def gate_check(task_id: int) -> dict:
    with session() as db:
        t = _get(db, task_id)
    return gate.summarize(await gate.run_checks(t))


@router.post("/{task_id}/claim")
async def claim(task_id: int, force: bool = Query(default=False)) -> dict:
    """领取并进入队列。门禁不通过时保持 CLAIMED 并返回检查结果。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status not in (AVAILABLE, CLAIMED):
            raise HTTPException(409, f"当前状态 {t.status} 不能领取")
        t.status = CLAIMED
        t.claimed_at = t.claimed_at or utc_now()
        db.flush()
        snapshot = t
    # 一道题一个分支，开工前先落到自己的分支上；切不了就让门禁把原因报出来
    await repo.ensure_task_branch(snapshot.task_no)
    report = gate.summarize(await gate.run_checks(snapshot))
    # 同项目有题在跑不该挡住排队：进队列等着，调度器保证不会两道一起跑
    blocks = [c for c in report["checks"] if c["level"] == "block"]
    waits_repo = bool(blocks) and all(c["name"] == "repo_busy" for c in blocks)
    queued = report["passed"] or waits_repo or force
    if queued:
        with session() as db:
            t = _get(db, task_id)
            t.status = QUEUED
            t.claimed_at = utc_now()
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"queued": queued, "gate": report, "waits_repo": waits_repo}


@router.post("/{task_id}/release")
async def release(task_id: int) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.status not in (CLAIMED, QUEUED):
            raise HTTPException(409, "只有未开始运行的任务可以放回题库")
        t.status = AVAILABLE
        t.claimed_at = None
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True}


@router.post("/{task_id}/discard")
async def discard(task_id: int) -> dict:
    """标记废弃：列表默认不再显示；残留容器一并销毁，轨迹与产物保留在磁盘上。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status == RUNNING:
            raise HTTPException(409, "运行中不能废弃，请先停止容器")
        if t.status == QUEUED:
            raise HTTPException(409, "排队中不能废弃，请先放回题库")
        if t.status == DISCARDED:
            return {"ok": True, "message": "该题已是废弃状态"}
        task_no, had_container = t.task_no, t.container_exists
    removed = False
    if had_container:
        removed = (await dockerx.remove_task_containers(task_no)).ok
    with session() as db:
        t = _get(db, task_id)
        t.discarded_from = t.status
        t.status = DISCARDED
        t.discarded_at = utc_now()
        t.container_exists = False
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "container_removed": removed,
            "message": "已废弃" + ("，容器已销毁" if removed else "")}


@router.post("/{task_id}/restore")
async def restore(task_id: int) -> dict:
    """恢复废弃的题：回到废弃前的状态，从未跑过的回到待领取。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status != DISCARDED:
            raise HTTPException(409, "只有已废弃的题可以恢复")
        back = t.discarded_from or AVAILABLE
        if back in (RUNNING, QUEUED):   # 废弃前的运行态已不存在，退回结束态判定
            back = t.verdict.get("status") or AVAILABLE
        t.status = back
        t.discarded_from = ""
        t.discarded_at = None
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "status": back, "message": f"已恢复为 {back}"}


@router.post("/{task_id}/reset")
async def reset(task_id: int, keep_traces: bool = Query(default=False)) -> dict:
    """恢复到做题前：容器、工作区、轨迹、prompt.md 回填、评审与质检记录全部还原。

    默认把轨迹与分析产物直接删掉；要留一份改名归档的证据就传 keep_traces=true。
    """
    r = await task_reset.reset_task(task_id, archive=keep_traces)
    if r.get("blocked"):
        raise HTTPException(409, r["steps"][0]["message"])
    return r


@router.post("/{task_id}/fix/{action}")
async def gate_fix(task_id: int, action: str) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.status in (RUNNING, QUEUED):
            raise HTTPException(409, "运行中/排队中不能执行修复")
    if action == "reset_snapshot":
        return await gate.reset_to_snapshot(t)
    if action == "archive_traces":
        return gate.archive_traces(t.task_no)
    if action == "switch_branch":
        return await repo.switch_to_task_branch(t.task_no)
    if action == "remove_container":
        r = await dockerx.remove_container(t.container_name)
        with session() as db:
            _get(db, task_id).container_exists = False
        return {"ok": r.ok, "message": r.err.strip() or "容器已删除"}
    raise HTTPException(404, "未知修复动作")


@router.post("/{task_id}/stop")
async def stop(task_id: int) -> dict:
    return await runner.stop_task(task_id)


@router.post("/{task_id}/continue")
async def continue_run(task_id: int, body: ContinueRun) -> dict:
    """续跑一轮：首轮 504 或报错后，带着新指令接着上一轮的改动往下做。"""
    with session() as db:
        _get(db, task_id)
    res = await runner.queue_continue(task_id, body.prompt)
    if not res.get("ok"):
        raise HTTPException(400, res.get("message", "无法续跑"))
    return res


# ---------------- 事件流 ----------------

REPLAY_LIMIT = 600      # 回放上限：一次运行可能几万条事件，全推过去浏览器会卡死


def _event_row(e: RunEvent) -> dict:
    # type 是 SSE 的分发标记，前端靠它区分事件与状态消息，缺了事件流会整段丢掉
    return {"type": "event", "seq": e.seq, "round_no": max(1, e.round_no or 1), "kind": e.kind,
            "summary": e.summary, "ts": e.ts.isoformat() if e.ts else None, "payload": e.payload}


def _load_events(db, task_id: int, limit: int) -> tuple[list[dict], int]:  # noqa: ANN001
    """取最后 limit 条，按 seq 升序返回，另给出总条数。"""
    total = db.execute(
        select(func.count()).select_from(RunEvent).where(RunEvent.task_id == task_id)
    ).scalar() or 0
    rows = db.execute(
        select(RunEvent).where(RunEvent.task_id == task_id).order_by(RunEvent.seq.desc()).limit(limit)
    ).scalars().all()
    return [_event_row(e) for e in reversed(rows)], int(total)


@router.get("/{task_id}/events")
async def task_events(task_id: int, replay: bool = Query(default=True),
                      limit: int = Query(default=REPLAY_LIMIT, ge=1, le=5000)) -> StreamingResponse:
    with session() as db:
        _get(db, task_id)
        history, total = ([], 0) if not replay else _load_events(db, task_id, limit)

    async def gen():
        if total > len(history):
            yield sse_format({"type": "truncated", "total": total, "shown": len(history)})
        for h in history:
            yield sse_format(h)
        yield sse_format({"type": "replay_done", "count": len(history), "total": total})
        async for item in bus.subscribe(f"run:{task_id}"):
            yield sse_format(item)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{task_id}/events/list")
async def task_events_list(task_id: int, limit: int = Query(default=1000, ge=1, le=5000)) -> dict:
    with session() as db:
        _get(db, task_id)
        items, total = _load_events(db, task_id, limit)
        return {"items": items, "total": total, "truncated": total > len(items)}


# ---------------- 轨迹 ----------------

@router.get("/{task_id}/trace")
async def download_trace(task_id: int) -> FileResponse:
    with session() as db:
        t = _get(db, task_id)
        path = t.trace_file
    if not path or not Path(path).exists():
        raise HTTPException(404, "轨迹文件不存在")
    return FileResponse(path, filename=Path(path).name, media_type="application/x-ndjson")


@router.get("/{task_id}/trace-index")
async def trace_index(task_id: int) -> dict:
    with session() as db:
        t = _get(db, task_id)
        paths = config.TaskPaths(t.task_no)
    return analyzer._load_trace_index(paths)  # noqa: SLF001


# ---------------- 分析 / 评审 ----------------

@router.post("/{task_id}/analyze")
async def analyze(task_id: int) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.status not in ANALYZABLE:
            raise HTTPException(409, f"状态 {t.status} 不能分析（需运行结束）")
        if t.analysis_status == ANALYSIS_RUNNING:
            raise HTTPException(409, "分析正在进行")
    asyncio.create_task(analyzer.analyze_task(task_id))
    return {"ok": True, "message": "分析已启动"}


@router.put("/{task_id}/review")
async def save_review(task_id: int, body: ReviewUpdate) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.status in (UPLOADED, DONE):
            raise HTTPException(409, "已上传的数据不可再编辑")
        review = t.review or {}
        review["scores"] = {k: v for k, v in body.scores.items()}
        review["descs"] = {k: (v or "").strip() for k, v in body.descs.items()}
        review["other_issues"] = body.other_issues.strip()
        if body.evidence is not None:
            review["evidence"] = body.evidence
        if body.coverage is not None:
            review["coverage"] = body.coverage
        t.review = review
    report = analyzer.run_verify(task_id)
    with session() as db:
        return {"verify": report, "task": task_brief(_get(db, task_id))}


@router.post("/{task_id}/verify")
async def verify(task_id: int) -> dict:
    with session() as db:
        _get(db, task_id)
    return analyzer.run_verify(task_id)


# ---------------- 质检（solo-qa 链路，只取结论） ----------------

@router.post("/{task_id}/qc")
async def run_qc(task_id: int) -> dict:
    ok, why = qa_bridge.available()
    if not ok:
        raise HTTPException(409, why)
    with session() as db:
        t = _get(db, task_id)
        if t.qc_status == QC_RUNNING:
            raise HTTPException(409, "质检正在进行")
        _, missing = qa_bridge.build_submission(t)
        if missing:
            raise HTTPException(409, "字段不全，先完成五维评审：" + "、".join(missing))
    asyncio.create_task(pipeline.run_qc(task_id))
    return {"ok": True, "message": "质检已启动"}


@router.post("/{task_id}/pipeline")
async def rerun_pipeline(task_id: int) -> dict:
    """手动重跑自动流水线（销毁容器 → 分析 → 质检）。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status not in RUN_END_STATUSES | {REVIEWED}:
            raise HTTPException(409, f"状态 {t.status} 不能跑流水线")
    pipeline.spawn(task_id)
    return {"ok": True, "message": "流水线已启动"}


@router.post("/{task_id}/queue/move")
async def queue_move(task_id: int, body: QueueMove) -> dict:
    """调整排队顺序。priority 越小越先出队，同值按领取时间。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status != QUEUED:
            raise HTTPException(409, "只有排队中的题可以调整顺序")
        others = db.execute(
            select(Task).where(Task.status == QUEUED, Task.id != task_id)
        ).scalars().all()
        lo = min([o.priority for o in others], default=0)
        hi = max([o.priority for o in others], default=0)
        if body.priority is not None:
            t.priority = int(body.priority)
        elif body.direction == "top":
            t.priority = lo - 1
        elif body.direction == "bottom":
            t.priority = hi + 1
        elif body.direction == "up":
            t.priority -= 1
        elif body.direction == "down":
            t.priority += 1
        else:
            raise HTTPException(400, "direction 需为 top/up/down/bottom")
        new_priority = t.priority
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "priority": new_priority}


# ---------------- 上传 ----------------

@router.post("/{task_id}/upload")
async def upload(task_id: int) -> dict:
    res = await uploader.upload_task(task_id)
    if not res.get("ok"):
        raise HTTPException(400 if not res.get("auth_error") else 401, detail=res)
    return res


# ---------------- 完成并销毁 ----------------

@router.post("/{task_id}/complete")
async def complete(task_id: int, force: bool = Query(default=False)) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.status == RUNNING:
            raise HTTPException(409, "运行中不能销毁，请先停止")
        if t.status not in (RUN_END_STATUSES | {REVIEWED, UPLOADED}):
            raise HTTPException(409, f"状态 {t.status} 不能标记完成")
        if not force and t.status != UPLOADED:
            raise HTTPException(409, "尚未上传，若确认放弃该题请带 force=true")
        trace_ok = bool(t.trace_file and Path(t.trace_file).exists())
        if not trace_ok and not force:
            raise HTTPException(409, "轨迹尚未导出，销毁会丢失数据；确认请带 force=true")
        task_no = t.task_no
    # 续跑过的题每轮一个容器，按标签一起收掉，别把前几轮落下
    r = await dockerx.remove_task_containers(task_no)
    with session() as db:
        t = _get(db, task_id)
        t.container_exists = False
        t.status = DONE
        t.done_at = utc_now()
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "container_removed": r.ok, "message": r.err.strip() or "容器已销毁"}


@router.post("/{task_id}/destroy-container")
async def destroy_container(task_id: int) -> dict:
    """只销毁容器、不改任务状态（用于异常态清理）。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status == RUNNING:
            raise HTTPException(409, "运行中不能销毁，请先停止")
        task_no = t.task_no
    r = await dockerx.remove_task_containers(task_no)
    with session() as db:
        _get(db, task_id).container_exists = False
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": r.ok, "message": r.err.strip() or "容器已销毁"}
