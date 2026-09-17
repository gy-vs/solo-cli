"""题库、双跑、GSB 结论、上传、生命周期。"""

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
    ANALYSIS_RUNNING, ANALYZED, AVAILABLE, CLAIMED, DISCARDED, DONE, NEEDS_ATTENTION,
    QUEUED, RUN_DONE, RUN_RUNNING, RUNNING, UPLOADED, RunEvent, Task, TaskRun, utc_now,
)
from app.schemas import (
    GsbUpdate, IdList, QueueMove, RerunRequest, ScreencastUpdate, task_brief, task_detail,
)
from app.services import (
    dockerx, gate, gsb_analyzer, gsb_repo, gsb_uploader, gsb_verifier, prompt_bank, runner,
    scheduler, settings_store, trace, watchdog,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get(db, task_id: int) -> Task:  # noqa: ANN001
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    return t


def _runs(db, task_id: int) -> list[TaskRun]:  # noqa: ANN001
    return db.query(TaskRun).filter(TaskRun.task_id == task_id).all()


def _side(value: str) -> str:
    s = (value or "").upper()
    if s not in config.SIDES:
        raise HTTPException(400, "side 必须是 A 或 B")
    return s


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
        tasks = db.execute(q).scalars().all()
        # 一次把所有 run 取回来按 task_id 归组，别在循环里逐题查库
        by_task: dict[int, list[TaskRun]] = {}
        for r in db.execute(select(TaskRun)).scalars():
            by_task.setdefault(r.task_id, []).append(r)
        items = [task_brief(t, by_task.get(t.id, [])) for t in tasks]
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
        items = [task_brief(t, _runs(db, t.id)) for t in rows]
    return {"items": items, "scheduler": scheduler.scheduler.snapshot()}


@router.post("/queue/pause")
async def queue_pause(paused: bool = Query(default=True)) -> dict:
    settings_store.set_one("scheduler.paused", "1" if paused else "0")
    bus.publish("tasks", {"type": "scheduler"})
    return {"ok": True, "paused": paused,
            "message": "已暂停出队，运行中的不受影响" if paused else "已恢复出队"}


@router.post("/queue/parallel")
async def queue_parallel(value: int = Query(...)) -> dict:
    value = max(2, min(12, value))
    settings_store.set_one("scheduler.max_parallel", str(value))
    bus.publish("tasks", {"type": "scheduler"})
    return {"ok": True, "max_parallel": value,
            "message": f"同时最多 {value} 个容器，也就是 {value // 2} 道题"}


@router.post("/batch/upload")
async def batch_upload(body: IdList) -> dict:
    results = []
    for tid in body.ids:
        res = await gsb_uploader.upload_task(tid)
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


@router.get("/{task_id}")
async def get_task(task_id: int) -> dict:
    with session() as db:
        return task_detail(_get(db, task_id), _runs(db, task_id))


# ---------------- 领取 / 门禁 / 启动 ----------------

@router.post("/{task_id}/gate")
async def gate_check(task_id: int) -> dict:
    with session() as db:
        t = _get(db, task_id)
    return gate.summarize(await gate.run_checks(t))


@router.post("/{task_id}/claim")
async def claim(task_id: int, force: bool = Query(default=False)) -> dict:
    """领取：校验分支、clone 两侧、跑门禁，通过就建两个 run 进队列。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status not in (AVAILABLE, CLAIMED):
            raise HTTPException(409, f"当前状态 {t.status} 不能领取")
        t.status = CLAIMED
        t.claimed_at = t.claimed_at or utc_now()
        db.flush()
        snapshot = t

    prep = await gate.prepare_workspaces(snapshot)
    with session() as db:
        t = _get(db, task_id)
        t.branch_check = {"ok": prep["ok"], "message": prep["message"],
                          "at": utc_now().isoformat()}
    if not prep["ok"] and not force:
        bus.publish("tasks", {"type": "task", "id": task_id})
        return {"queued": False, "prepare": prep, "gate": None}

    report = gate.summarize(await gate.run_checks(snapshot))
    queued = report["passed"] or force
    if queued:
        with session() as db:
            t = _get(db, task_id)
            # 两侧的 run 一次建齐。缺一侧调度器会跳过整道题，宁可这里就建全
            have = {r.side for r in _runs(db, task_id)}
            for side in config.SIDES:
                if side not in have:
                    db.add(TaskRun(task_id=task_id, side=side,
                                   container_name=config.TaskPaths(t.task_no, side).container_name))
            t.status = QUEUED
            t.claimed_at = utc_now()
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"queued": queued, "prepare": prep, "gate": report}


@router.post("/{task_id}/release")
async def release(task_id: int) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.status not in (CLAIMED, QUEUED):
            raise HTTPException(409, "只有未开始运行的任务可以放回题库")
        t.status = AVAILABLE
        t.claimed_at = None
        for r in _runs(db, task_id):
            db.delete(r)
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
        task_no = t.task_no
        had_container = any(r.container_exists for r in _runs(db, task_id))
    removed = False
    if had_container:
        removed = (await dockerx.remove_task_containers(task_no)).ok
    with session() as db:
        t = _get(db, task_id)
        t.discarded_from = t.status
        t.status = DISCARDED
        t.discarded_at = utc_now()
        for r in _runs(db, task_id):
            r.container_exists = False
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
        if back in (RUNNING, QUEUED):   # 废弃前的运行态已不存在，退回待领取
            back = AVAILABLE
        t.status = back
        t.discarded_from = ""
        t.discarded_at = None
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "status": back, "message": f"已恢复为 {back}"}


@router.post("/{task_id}/fix/{action}")
async def gate_fix(task_id: int, action: str) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.status in (RUNNING, QUEUED):
            raise HTTPException(409, "运行中或排队中不能执行修复")
        task_no, repo_url, snapshot = t.task_no, t.repo_url, gsb_repo.snapshot_sha(t.env_snapshot)
        detached = t

    if action == "clone_sides":
        return await gate.prepare_workspaces(detached)
    if action == "reset_sides":
        if not snapshot:
            return {"ok": False, "message": "初始快照缺少 40 位 SHA，无法重置"}
        out = {s: await gsb_repo.reset_side(task_no, s, snapshot) for s in config.SIDES}
        return {"ok": all(r.get("ok") for r in out.values()),
                "message": "；".join(f"{s}: {r.get('message')}" for s, r in out.items())}
    if action == "archive_traces":
        out = {s: watchdog.archive_traces(task_no, s) for s in config.SIDES}
        return {"ok": all(r["ok"] for r in out.values()),
                "message": "；".join(f"{s}: {r['message']}" for s, r in out.items())}
    if action == "remove_containers":
        r = await dockerx.remove_task_containers(task_no)
        with session() as db:
            for run in _runs(db, task_id):
                run.container_exists = False
        return {"ok": r.ok, "message": r.err.strip() or "两侧容器已删除"}
    raise HTTPException(404, "未知修复动作")


@router.post("/{task_id}/stop")
async def stop(task_id: int, side: str = Query(default="")) -> dict:
    """停止容器。不给 side 就把两侧都停了。"""
    with session() as db:
        _get(db, task_id)
        runs = [r for r in _runs(db, task_id)
                if not side or r.side == _side(side)]
        ids = [r.id for r in runs if r.status == RUN_RUNNING]
    if not ids:
        return {"ok": False, "message": "没有正在运行的容器"}
    out = [await runner.stop_run(rid) for rid in ids]
    return {"ok": all(r["ok"] for r in out),
            "message": "；".join(r["message"] for r in out)}


@router.post("/{task_id}/rerun")
async def rerun(task_id: int, body: RerunRequest) -> dict:
    """人工重跑。与自动重跑走同一套动作，区别是不看次数上限并把计数清零。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status == RUNNING and any(r.status == RUN_RUNNING for r in _runs(db, task_id)):
            raise HTTPException(409, "还有容器在跑，请先停止")
    sides = tuple(_side(s) for s in body.sides) or config.SIDES
    res = await watchdog.manual_rerun(task_id, sides)
    if not res["ok"]:
        raise HTTPException(400, res["message"])
    return res


# ---------------- 事件流 ----------------

REPLAY_LIMIT = 600      # 回放上限：一次运行可能几万条事件，全推过去浏览器会卡死


def _event_row(e: RunEvent) -> dict:
    # type 是 SSE 的分发标记，前端靠它区分事件与状态消息，缺了事件流会整段丢掉
    return {"type": "event", "seq": e.seq, "side": e.side or "A", "kind": e.kind,
            "summary": e.summary, "ts": e.ts.isoformat() if e.ts else None, "payload": e.payload}


def _load_events(db, task_id: int, limit: int, side: str = "") -> tuple[list[dict], int]:  # noqa: ANN001
    """取最后 limit 条，按 seq 升序返回，另给出总条数。"""
    where = [RunEvent.task_id == task_id]
    if side:
        where.append(RunEvent.side == side)
    total = db.execute(select(func.count()).select_from(RunEvent).where(*where)).scalar() or 0
    rows = db.execute(
        select(RunEvent).where(*where).order_by(RunEvent.seq.desc()).limit(limit)
    ).scalars().all()
    return [_event_row(e) for e in reversed(rows)], int(total)


@router.get("/{task_id}/events")
async def task_events(task_id: int, replay: bool = Query(default=True),
                      side: str = Query(default=""),
                      limit: int = Query(default=REPLAY_LIMIT, ge=1, le=5000)) -> StreamingResponse:
    want = _side(side) if side else ""
    with session() as db:
        _get(db, task_id)
        history, total = ([], 0) if not replay else _load_events(db, task_id, limit, want)

    async def gen():
        if total > len(history):
            yield sse_format({"type": "truncated", "total": total, "shown": len(history)})
        for h in history:
            yield sse_format(h)
        yield sse_format({"type": "replay_done", "count": len(history), "total": total})
        async for item in bus.subscribe(f"run:{task_id}"):
            # 只订阅一侧时，另一侧的实时事件不要混进来
            if want and item.get("side") and item["side"] != want:
                continue
            yield sse_format(item)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{task_id}/events/list")
async def task_events_list(task_id: int, side: str = Query(default=""),
                           limit: int = Query(default=1000, ge=1, le=5000)) -> dict:
    want = _side(side) if side else ""
    with session() as db:
        _get(db, task_id)
        items, total = _load_events(db, task_id, limit, want)
        return {"items": items, "total": total, "truncated": total > len(items)}


# ---------------- 轨迹 ----------------

@router.get("/{task_id}/trace")
async def download_trace(task_id: int, side: str = Query(...)) -> FileResponse:
    want = _side(side)
    with session() as db:
        _get(db, task_id)
        run = next((r for r in _runs(db, task_id) if r.side == want), None)
        path = run.trace_file if run else ""
    if not path or not Path(path).exists():
        raise HTTPException(404, f"{want} 侧的轨迹文件不存在")
    return FileResponse(path, filename=Path(path).name, media_type="application/x-ndjson")


@router.get("/{task_id}/trace-index")
async def trace_index(task_id: int, side: str = Query(...)) -> dict:
    want = _side(side)
    with session() as db:
        t = _get(db, task_id)
        paths = config.TaskPaths(t.task_no, want)
    if paths.trace_index.exists():
        import json

        try:
            return json.loads(paths.trace_index.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    tf = trace.find_trace_file(paths.traces)
    if not tf:
        raise HTTPException(404, f"{want} 侧还没有轨迹")
    summary = trace.parse_trace(tf)
    paths.analysis.mkdir(parents=True, exist_ok=True)
    trace.write_index(summary, paths.trace_index)
    return summary


# ---------------- GSB 分析与结论 ----------------

@router.post("/{task_id}/analyze")
async def analyze(task_id: int) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.analysis_status == ANALYSIS_RUNNING:
            raise HTTPException(409, "分析正在进行")
        runs = _runs(db, task_id)
        unfinished = [r.side for r in runs if r.status != "FINISHED"]
        if len(runs) != 2 or unfinished:
            raise HTTPException(409, f"两侧都跑完才能对比，{'、'.join(unfinished) or '缺少运行记录'}")
    asyncio.create_task(gsb_analyzer.analyze_task(task_id))
    return {"ok": True, "message": "GSB 对比已启动"}


@router.post("/{task_id}/advance")
async def advance(task_id: int) -> dict:
    """手动走一遍「推产物 + 开分析」。正常由巡检自动触发，这里给推送失败后重试用。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status not in (RUN_DONE, NEEDS_ATTENTION, ANALYZED):
            raise HTTPException(409, f"状态 {t.status} 不能推进")
    return await watchdog.advance_pair(task_id)


@router.put("/{task_id}/gsb")
async def save_gsb(task_id: int, body: GsbUpdate) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.status in (UPLOADED, DONE):
            raise HTTPException(409, "已上传的数据不可再编辑")
        gsb = dict(t.gsb)
        if body.verdict:
            if body.verdict not in gsb_analyzer.VERDICTS:
                raise HTTPException(400, f"结论必须是 {'、'.join(gsb_analyzer.VERDICTS)} 之一")
            gsb["verdict"] = body.verdict
        gsb["reason"] = body.reason.strip()
        if body.a_startup is not None:
            gsb["a_startup"] = body.a_startup
        if body.b_startup is not None:
            gsb["b_startup"] = body.b_startup
        if body.validity:
            gsb["validity"] = body.validity
        gsb["remark"] = body.remark.strip()
        t.gsb = gsb
    report = await gsb_verifier.run_verify(task_id)
    with session() as db:
        return {"verify": report, "task": task_brief(_get(db, task_id), _runs(db, task_id))}


@router.post("/{task_id}/verify")
async def verify(task_id: int) -> dict:
    with session() as db:
        _get(db, task_id)
    return await gsb_verifier.run_verify(task_id)


# ---------------- 录屏 ----------------

@router.put("/{task_id}/screencast")
async def save_screencast(task_id: int, body: ScreencastUpdate) -> dict:
    """填两侧录屏链接。这是上传前唯一必须人工给的东西。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status in (UPLOADED, DONE):
            raise HTTPException(409, "已上传的数据不可再编辑")
        sc = dict(t.screencast)
        for side, url in (("A", body.A), ("B", body.B)):
            if url is not None:
                sc[side] = url.strip()
        t.screencast = sc
    report = await gsb_verifier.run_verify(task_id)
    with session() as db:
        return {"verify": report, "task": task_brief(_get(db, task_id), _runs(db, task_id))}


@router.post("/{task_id}/screencast/upload")
async def upload_screencast(task_id: int, side: str = Query(...),
                            path: str = Query(...)) -> dict:
    """把本地录屏文件代传到平台，换回一个链接。"""
    want = _side(side)
    with session() as db:
        _get(db, task_id)
    res = await gsb_uploader.upload_screencast(task_id, want, Path(path))
    if not res["ok"]:
        raise HTTPException(400, res["message"])
    return res


# ---------------- 队列顺序 ----------------

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
    res = await gsb_uploader.upload_task(task_id)
    if not res.get("ok"):
        raise HTTPException(400 if not res.get("auth_error") else 401, detail=res)
    return res


# ---------------- 完成并销毁 ----------------

@router.post("/{task_id}/complete")
async def complete(task_id: int, force: bool = Query(default=False)) -> dict:
    with session() as db:
        t = _get(db, task_id)
        runs = _runs(db, task_id)
        if any(r.status == RUN_RUNNING for r in runs):
            raise HTTPException(409, "还有容器在跑，请先停止")
        if t.status not in (RUN_DONE, ANALYZED, UPLOADED, NEEDS_ATTENTION):
            raise HTTPException(409, f"状态 {t.status} 不能标记完成")
        if not force and t.status != UPLOADED:
            raise HTTPException(409, "尚未上传，若确认放弃该题请带 force=true")
        missing = [r.side for r in runs if not (r.trace_file and Path(r.trace_file).exists())]
        if missing and not force:
            raise HTTPException(409, f"{'、'.join(missing)} 侧轨迹尚未导出，销毁会丢失数据；"
                                     f"确认请带 force=true")
        task_no = t.task_no
    r = await dockerx.remove_task_containers(task_no)
    with session() as db:
        t = _get(db, task_id)
        for run in _runs(db, task_id):
            run.container_exists = False
        t.status = DONE
        t.done_at = utc_now()
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "container_removed": r.ok, "message": r.err.strip() or "两侧容器已销毁"}


@router.post("/{task_id}/destroy-container")
async def destroy_container(task_id: int) -> dict:
    """只销毁容器、不改任务状态（用于异常态清理）。"""
    with session() as db:
        t = _get(db, task_id)
        if any(r.status == RUN_RUNNING for r in _runs(db, task_id)):
            raise HTTPException(409, "还有容器在跑，请先停止")
        task_no = t.task_no
    r = await dockerx.remove_task_containers(task_no)
    with session() as db:
        for run in _runs(db, task_id):
            run.container_exists = False
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": r.ok, "message": r.err.strip() or "容器已销毁"}
