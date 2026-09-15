"""运行结束后的自动流水线：销毁容器 → 五维分析 → 质检。

每一步都能单独关掉（设置页的「自动流水线」组），关掉的那步留给人工点。
分析与质检都在调模型，用同一个信号量限流，避免十道题同时结束时把网关打爆。

失败不阻塞后续题目：某一步出错就把原因写进 `auto_error` 停在那一步，
任务仍留在列表里等人处理，不会回滚已经拿到的结果。
"""

from __future__ import annotations

import asyncio
import logging

from app.db import session
from app.events import bus
from sqlalchemy import select

from app.models import (
    ANALYSIS_DONE, ANALYSIS_IDLE, ANALYSIS_RUNNING, ANALYZABLE, QC_IDLE, QC_DONE, QC_FAILED, QC_RUNNING,
    RUN_END_STATUSES, STAGE_ANALYZE, STAGE_DESTROY, STAGE_DONE, STAGE_IDLE, STAGE_QC,
    Task, utc_now,
)
from app.services import dockerx, qa_bridge, settings_store

log = logging.getLogger("pipeline")

_sem: asyncio.Semaphore | None = None
_sem_size = 0
running: set[int] = set()


def _semaphore() -> asyncio.Semaphore:
    """并发数改了就换一个信号量。已在里面的任务按旧额度跑完，不打断。"""
    global _sem, _sem_size
    size = max(1, settings_store.get_int("auto.max_parallel", 2))
    if _sem is None or size != _sem_size:
        _sem, _sem_size = asyncio.Semaphore(size), size
    return _sem


def _set(task_id: int, **fields) -> None:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        for k, v in fields.items():
            setattr(t, k, v)
    bus.publish("tasks", {"type": "task", "id": task_id})


def _note(task_id: int, msg: str) -> None:
    """流水线的提示逐条累加，后一步不要把前一步的原因抹掉。"""
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        old = [s for s in (t.auto_error or "").split(" / ") if s]
        if msg not in old:
            old.append(msg)
        t.auto_error = " / ".join(old)[:1000]
    bus.publish("tasks", {"type": "task", "id": task_id})


def snapshot() -> dict:
    return {"running": sorted(running), "max_parallel": max(1, settings_store.get_int("auto.max_parallel", 2))}


def spawn(task_id: int) -> None:
    """运行结束后由 runner 调用。不 await，失败只记日志。"""
    if task_id in running:
        return
    task = asyncio.create_task(run_for(task_id), name=f"pipeline-{task_id}")
    task.add_done_callback(lambda f: f.exception() and log.error("流水线 %s 异常: %s", task_id, f.exception()))


async def run_for(task_id: int) -> None:
    if task_id in running:
        return
    running.add(task_id)
    try:
        _set(task_id, auto_error="")
        async with _semaphore():
            await _destroy(task_id)
            ok = await _analyze(task_id)
            if ok:
                await _qc(task_id)
        _set(task_id, auto_stage=STAGE_DONE)
    finally:
        running.discard(task_id)


async def _destroy(task_id: int) -> None:
    """轨迹已经导出到宿主机才销毁。没导出成功就留着容器，人工还能进去捞。"""
    if not settings_store.get_bool("auto.destroy_on_finish", True):
        return
    with session() as db:
        t = db.get(Task, task_id)
        if t is None or not t.container_exists:
            return
        name, trace_file = t.container_name, t.trace_file
    if not trace_file:
        _note(task_id, "本轮没导出轨迹，容器先留着等人工处理")
        return
    _set(task_id, auto_stage=STAGE_DESTROY)
    r = await dockerx.remove_container(name)
    if r.ok:
        _set(task_id, container_exists=False)
    else:
        _note(task_id, f"销毁容器失败：{r.err.strip()[:300]}")


async def _analyze(task_id: int) -> bool:
    """返回是否具备进入质检的条件。"""
    from app.services import analyzer  # 延迟导入：analyzer 会反向用到本模块的开关

    if not settings_store.get_bool("auto.analyze", True):
        return False
    with session() as db:
        t = db.get(Task, task_id)
        if t is None or t.status not in ANALYZABLE:
            return False
        if t.analysis_status == ANALYSIS_DONE:
            return True
        has_trace = bool(t.trace_file)
        changed = (t.verdict.get("artifact") or {}).get("changed_files") or 0
    # 没轨迹就没有可分析的过程，模型只会对着空气打分，白烧一次额度
    if not has_trace:
        _note(task_id, "本轮没有轨迹，跳过自动分析")
        return False
    if not changed:
        _note(task_id, "工作目录没有任何改动，分析结果仅供参考")
    _set(task_id, auto_stage=STAGE_ANALYZE)
    try:
        r = await analyzer.analyze_task(task_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("自动分析失败 %s", task_id)
        _note(task_id, f"自动分析失败：{exc}")
        return False
    if not r.get("ok"):
        _note(task_id, f"自动分析失败：{r.get('error', '')[:500]}")
        return False
    return True


async def _qc(task_id: int) -> None:
    if not settings_store.get_bool("auto.qc", True):
        return
    ok, why = qa_bridge.available()
    if not ok:
        _note(task_id, f"跳过质检：{why}")
        return
    await run_qc(task_id)


async def run_qc(task_id: int) -> dict:
    """单独跑质检，手动触发也走这里。"""
    _set(task_id, auto_stage=STAGE_QC, qc_status=QC_RUNNING)
    try:
        r = await qa_bridge.qc_task(task_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("质检异常 %s", task_id)
        r = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    if r.get("ok"):
        _set(task_id, qc_status=QC_DONE, qc_json=Task._dump(r), qc_at=utc_now())
    else:
        _set(task_id, qc_status=QC_FAILED, qc_json=Task._dump(r), qc_at=utc_now())
        _note(task_id, f"质检未完成：{r.get('error', '')[:500]}")
    bus.publish("tasks", {"type": "task", "id": task_id})
    return r


def reset_qc(task_id: int) -> None:
    _set(task_id, qc_status=QC_IDLE, qc_json="{}", qc_at=None)


def resume_stale() -> list[int]:
    """启动时自愈：分析/质检是进程内的活，后端一重启就没了，但状态还留在库里。

    不复位的话任务会永远显示「分析中」，既不推进也不给重试入口。
    这里把中断的状态清回空档，再把没走完的题重新排进流水线。
    """
    with session() as db:
        rows = db.execute(select(Task).where(Task.status.in_(RUN_END_STATUSES))).scalars().all()
        stale: list[int] = []
        for t in rows:
            interrupted = t.analysis_status == ANALYSIS_RUNNING or t.qc_status == QC_RUNNING
            if interrupted:
                if t.analysis_status == ANALYSIS_RUNNING:
                    t.analysis_status = ANALYSIS_IDLE
                if t.qc_status == QC_RUNNING:
                    t.qc_status = QC_IDLE
                t.auto_stage = STAGE_IDLE
            # 停在中途的阶段也要接着跑完
            if interrupted or (t.auto_stage or "") not in (STAGE_DONE, STAGE_IDLE, ""):
                t.auto_stage = STAGE_IDLE
                stale.append(t.id)
    for tid in stale:
        _note(tid, "上一次流水线被后端重启打断，已自动重新接续")
        spawn(tid)
    return stale


def should_autorun(status: str) -> bool:
    return status in RUN_END_STATUSES and (
        settings_store.get_bool("auto.destroy_on_finish", True)
        or settings_store.get_bool("auto.analyze", True)
    )
