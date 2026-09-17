"""周期巡检：异常重跑、产物推送、自动开分析。

这是双跑流程里唯一做决策的地方。单跑时代这些判断散在 runner 收尾和流水线里，
改成双跑后两侧结束时间不定，谁都可能是最后一个——放在 runner 里就会出现 A 和 B
同时认为「该我推进了」，于是分析被起两次、容器被销毁两次。所以收归一处，
runner 跑完只负责叫一声。

周期扫描是兜底。正常情况下 runner 结束会 wake 一次，立刻扫，不必等满一轮。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app import config
from app.db import session
from app.events import bus
from app.models import (
    ANALYSIS_IDLE, ANALYZING, NEEDS_ATTENTION, QUEUED, RUN_DONE, RUN_END_STATUSES,
    RUN_FAILED, RUN_FINISHED, RUN_QUEUED, RUN_RUNNING, RunEvent, Task, TaskRun, utc_now,
)
from app.services import dockerx, gsb_repo, settings_store

log = logging.getLogger("watchdog")

INTERVAL_DEFAULT = 300
MAX_RETRIES_DEFAULT = 3

_wake = asyncio.Event()
_task: asyncio.Task | None = None
_stopping = False


def wake() -> None:
    """催一次巡检。单侧跑完后调用，不必等下一个周期到点。"""
    _wake.set()


# ---------------- 异常判定 ----------------

def abnormal_reason(run: TaskRun, container_alive: bool | None = None) -> str:
    """这一侧是不是异常。返回原因，正常返回空串。

    判的是「这次跑的过程坏了」，不是「模型做得不好」。做得不好是 GSB 要评的内容，
    过程坏了的结果没有可比性，只能重跑。网关报错尤其要抓出来：平台明确不认这类
    差异，拿它去比等于用网络波动给模型定罪。
    """
    verdict = run.verdict or {}
    process = verdict.get("process") or {}
    artifact = verdict.get("artifact") or {}
    protocol = verdict.get("protocol") or {}

    if gw := process.get("gateway_errors"):
        return f"出现网关报错 {'、'.join(str(g) for g in gw)}"
    if run.status == RUN_RUNNING and container_alive is False:
        return f"状态是运行中，但容器 {run.container_name} 已经不在了"
    if run.status not in RUN_END_STATUSES:
        return ""
    # 人主动按的停止不自动重跑。他可能是看着不对要去改配置，这时候悄悄重跑一遍
    # 既浪费算力，也会把他刚改的东西盖掉。
    if process.get("manual_stop"):
        return ""
    if run.status != RUN_FINISHED:
        return f"这一侧的结束状态是 {run.status}"
    if (code := process.get("exit_code")) not in (0, None):
        return f"容器退出码 {code}"
    subtype = protocol.get("subtype")
    if subtype and subtype != "success":
        return f"result 的 subtype 是 {subtype}"
    # 「戛然而止」：没报错，但什么都没留下。代码理解类的题可能确实不改代码，
    # 所以零改动只在同时没有轨迹或轨迹为空时才算——真跑过的痕迹比改动数更可靠。
    if not artifact.get("trace_found"):
        return "没有产出轨迹，疑似戛然而止"
    if not artifact.get("changed_files") and not (run.git_diff_stat or "").strip():
        return "工作目录零改动，疑似戛然而止"
    return ""


def can_retry(run: TaskRun, max_retries: int | None = None) -> bool:
    limit = max_retries if max_retries is not None else settings_store.get_int(
        "watchdog.max_retries", MAX_RETRIES_DEFAULT)
    return run.attempt < max(1, limit)


# ---------------- 重跑动作 ----------------

def archive_traces(task_no: str, side: str) -> dict:
    """把非空轨迹目录整体改名归档（带时间戳），腾出空目录。

    镜像的 entrypoint 会拒绝挂载非空的轨迹目录，重跑前必须腾干净。改名而不是删除：
    上一次的轨迹是判「为什么异常」的唯一材料。
    """
    tr = config.TaskPaths(task_no, side).traces
    if not tr.exists() or not any(tr.iterdir()):
        return {"ok": True, "message": "轨迹目录本就为空"}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = tr.with_name(f"{tr.name}.archived-{stamp}")
    if target.exists():
        target = tr.with_name(f"{tr.name}.archived-{stamp}-{utc_now().microsecond}")
    tr.rename(target)
    return {"ok": True, "message": f"已归档到 {target.name}"}


async def requeue_run(run_id: int, *, reason: str, reset_attempt: bool = False) -> dict:
    """把一侧退回起点重新排队。

    顺序不能变：先销毁容器（不然容器名占着起不来），再归档轨迹（镜像拒绝非空目录），
    最后 reset 工作区（拿掉上次的改动，否则产物快照的父提交对不上初始快照）。
    中间任何一步失败就停下来交给人工，硬着头皮往下走只会跑出一份没法用的结果。
    """
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return {"ok": False, "message": "这一侧的运行记录不存在"}
        task = db.get(Task, run.task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        task_id, task_no, side = task.id, task.task_no, run.side
        snapshot, name = gsb_repo.snapshot_sha(task.env_snapshot), run.container_name

    await dockerx.remove_container(name, force=True)
    arch = await asyncio.to_thread(archive_traces, task_no, side)
    if not arch["ok"]:
        return {"ok": False, "message": f"归档 {side} 侧轨迹失败：{arch['message']}"}
    if not snapshot:
        return {"ok": False, "message": "初始快照缺少 40 位 SHA，不敢 reset 工作区"}
    rst = await gsb_repo.reset_side(task_no, side, snapshot)
    if not rst.get("ok"):
        return {"ok": False, "message": f"{side} 侧回退快照失败：{rst.get('message')}"}

    with session() as db:
        run = db.get(TaskRun, run_id)
        task = db.get(Task, run.task_id) if run else None
        if run is None or task is None:
            return {"ok": False, "message": "运行记录已消失"}
        # 上一次的事件全清掉。留着的话时间线上会出现两次「启动容器」，
        # 而界面按 seq 排序，读起来像模型自己重启了一遍
        db.query(RunEvent).filter(RunEvent.task_id == task_id, RunEvent.side == side).delete()
        run.attempt = 1 if reset_attempt else run.attempt + 1
        run.status = RUN_QUEUED
        run.abnormal = {"reason": reason, "at": utc_now().isoformat(), "attempt": run.attempt}
        run.exit_code = None
        run.result = {}
        run.verdict = {}
        run.trace_summary = {}
        run.trace_file = ""
        run.git_diff_stat = ""
        run.error = ""
        run.session_id = ""
        run.turn_id = ""
        run.artifact_sha = ""
        run.artifact_url = ""
        run.container_exists = False
        run.started_at = None
        run.finished_at = None
        # 另一侧可能已经跑完在等，题级回到 QUEUED 让调度器重新成对出闸
        task.status = QUEUED
        task.finished_at = None
        task.auto_error = ""
        attempt = run.attempt
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "attempt": attempt,
            "message": f"{side} 侧已退回起点，这是第 {attempt} 次尝试（{reason}）"}


async def give_up(run_id: int, reason: str) -> None:
    """重跑用尽，转人工。"""
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return
        task = db.get(Task, run.task_id)
        run.status = RUN_FAILED if run.status not in RUN_END_STATUSES else run.status
        run.abnormal = {"reason": reason, "at": utc_now().isoformat(),
                        "attempt": run.attempt, "gave_up": True}
        if run.finished_at is None:
            run.finished_at = utc_now()
        if task is not None:
            task.status = NEEDS_ATTENTION
            task.auto_error = f"{run.side} 侧重跑 {run.attempt} 次仍异常：{reason}"[:2000]
            task_id = task.id
    bus.publish("tasks", {"type": "task", "id": task_id})


# ---------------- 配对推进 ----------------

async def _destroy_containers(task_no: str, runs: list[TaskRun]) -> None:
    """轨迹已经导出到宿主机就销毁容器；没导出成功的留着，让人工进去捞。"""
    for run in runs:
        if run.trace_file:
            await dockerx.remove_container(run.container_name, force=True)


async def push_artifacts(task_id: int) -> dict:
    """把两侧产物提交并推到各自分支，回填产物快照链接。

    失败不算模型的错，所以不计入重跑次数，题留在原状态等下一轮再试。
    """
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        task_no, repo_url = task.task_no, task.repo_url
        snapshot = gsb_repo.snapshot_sha(task.env_snapshot)
        runs = {r.side: (r.id, r.session_id, r.artifact_sha)
                for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()}

    msgs = []
    for side in config.SIDES:
        if side not in runs:
            return {"ok": False, "message": f"缺少 {side} 侧的运行记录"}
        run_id, session_id, existing = runs[side]
        if existing:
            msgs.append(f"{side}: 已有快照 {existing[:12]}")
            continue
        r = await gsb_repo.commit_and_push(
            task_no, repo_url, side, snapshot,
            message=gsb_repo.commit_message(task_no, side, session_id))
        if not r.get("ok"):
            return {"ok": False, "message": f"{side} 侧推送失败：{r.get('message')}"}
        with session() as db:
            run = db.get(TaskRun, run_id)
            if run is not None:
                run.artifact_sha = r.get("sha", "")
                run.artifact_url = r.get("url", "")
        msgs.append(f"{side}: {r.get('sha', '')[:12]}")
    return {"ok": True, "message": "；".join(msgs)}


async def advance_pair(task_id: int) -> dict:
    """两侧都正常结束之后的推进：销毁容器、推产物、开分析。"""
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        runs = db.query(TaskRun).filter(TaskRun.task_id == task_id).all()
        task_no = task.task_no
        task.status = RUN_DONE
        detached = list(runs)
    await _destroy_containers(task_no, detached)

    push = await push_artifacts(task_id)
    if not push["ok"]:
        with session() as db:
            task = db.get(Task, task_id)
            if task is not None:
                task.auto_error = push["message"][:2000]
        bus.publish("tasks", {"type": "task", "id": task_id})
        return push

    from app.services import gsb_analyzer

    return await gsb_analyzer.analyze_task(task_id)


# ---------------- 巡检主体 ----------------

def _pairs_ready() -> list[int]:
    """两侧都正常结束、还没进分析的题。"""
    with session() as db:
        out = []
        for task in db.execute(select(Task).where(Task.status.notin_(
                (ANALYZING, NEEDS_ATTENTION)))).scalars():
            if task.analysis_status != ANALYSIS_IDLE:
                continue
            runs = db.query(TaskRun).filter(TaskRun.task_id == task.id).all()
            if len(runs) != 2 or any(r.status != RUN_FINISHED for r in runs):
                continue
            if any(abnormal_reason(r) for r in runs):
                continue
            out.append(task.id)
        return out


async def _scan_abnormal() -> None:
    with session() as db:
        # 运行中的也要看：容器被 docker prune 之类的操作带走时，run 会永远停在 RUNNING
        candidates = [(r.id, r.container_name, r.status)
                      for r in db.execute(select(TaskRun).where(
                          TaskRun.status.in_((RUN_RUNNING, *RUN_END_STATUSES)))).scalars()]
    for run_id, name, status in candidates:
        alive = None
        if status == RUN_RUNNING:
            alive = await dockerx.container_state(name) == "running"
        with session() as db:
            run = db.get(TaskRun, run_id)
            if run is None:
                continue
            reason = abnormal_reason(run, alive)
            retryable = can_retry(run)
            gave_up = (run.abnormal or {}).get("gave_up")
        if not reason or gave_up:
            continue
        if retryable:
            log.info("run %s 异常（%s），重跑", run_id, reason)
            r = await requeue_run(run_id, reason=reason)
            if not r["ok"]:
                await give_up(run_id, f"{reason}；重跑准备失败：{r['message']}")
        else:
            log.warning("run %s 异常（%s）且重跑已用尽，转人工", run_id, reason)
            await give_up(run_id, reason)


async def _scan_pairs() -> None:
    for task_id in _pairs_ready():
        log.info("题 %s 两侧都跑完了，开始推产物与分析", task_id)
        r = await advance_pair(task_id)
        if not r.get("ok"):
            log.warning("题 %s 推进失败：%s", task_id, r.get("message") or r.get("error"))


async def tick() -> None:
    await _scan_abnormal()
    await _scan_pairs()


async def _loop() -> None:
    while not _stopping:
        try:
            await tick()
        except Exception:  # noqa: BLE001
            log.exception("巡检异常")
        interval = max(30, settings_store.get_int("watchdog.interval_seconds", INTERVAL_DEFAULT))
        try:
            await asyncio.wait_for(_wake.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
        _wake.clear()


async def start() -> None:
    global _task, _stopping
    _stopping = False
    _task = asyncio.create_task(_loop(), name="watchdog-loop")


async def stop() -> None:
    global _stopping
    _stopping = True
    _wake.set()
    if _task:
        _task.cancel()


# ---------------- 人工入口 ----------------

async def manual_rerun(task_id: int, sides: tuple[str, ...] = config.SIDES) -> dict:
    """人工重跑。动作与自动重跑完全一致，区别是不看 attempt 上限并把计数清零。"""
    with session() as db:
        ids = [r.id for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()
               if r.side in sides]
    if not ids:
        return {"ok": False, "message": f"没有 {'、'.join(sides)} 侧的运行记录"}
    msgs = []
    for run_id in ids:
        r = await requeue_run(run_id, reason="人工重跑", reset_attempt=True)
        if not r["ok"]:
            return r
        msgs.append(r["message"])
    return {"ok": True, "message": "；".join(msgs)}
