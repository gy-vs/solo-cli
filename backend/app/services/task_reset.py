"""把一道题退回到开始做题之前，用于重跑。

要还原的不只是数据库状态，还有磁盘上的三处副作用：工作区被模型改过、轨迹目录
留了 jsonl、prompt.md 被回填过 SessionID。少还原一处，下次启动就会卡在门禁上，
或者把上一轮的结果混进这一轮。

每一步失败都不中断，最后把逐步结果一起返回，界面上能看到哪一步没做成。
"""

from __future__ import annotations

import logging
import shutil

from app import config
from app.db import session
from app.events import bus
from app.models import (
    ANALYSIS_IDLE, AVAILABLE, QC_IDLE, QUEUED, RUNNING, RunEvent, STAGE_IDLE, Task,
)
from app.services import dockerx, gate, prompt_bank

log = logging.getLogger("reset")

# prompt.md 里这两行的原始占位文本，回填过就要写回去
PENDING_SESSION = "待回填，取轨迹 jsonl 文件名的 UUID"
PENDING_TURN = "待回填，取本轮 user 消息的 promptId"


def _step(name: str, ok: bool, message: str = "") -> dict:
    return {"step": name, "ok": ok, "message": message}


async def reset_task(task_id: int, *, archive: bool = False) -> dict:
    """还原一道题。

    默认直接删轨迹与分析产物，不归档：归档只是把目录改名成 01.archived-<时间戳>
    留在原地，还原几次就攒一堆，续跑之后每轮还各留一个，反而要人去分辨哪个是哪个。
    要留证据就传 archive=True。
    """
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "steps": [_step("查找任务", False, "任务不存在")]}
        if t.status in (RUNNING, QUEUED):
            return {"ok": False, "blocked": True,
                    "steps": [_step("检查状态", False, "运行中或排队中，请先停止或放回题库")]}
        task_no, container, had_container = t.task_no, t.container_name, t.container_exists
        prompt_hash, backfilled = t.prompt_hash, bool(t.session_id or t.turn_id)
        rounds = max(1, t.round_no or 1)

    paths = config.TaskPaths(task_no)
    # 续跑过的题每轮一个容器、一个轨迹目录，逐轮还原，漏一轮下次启动就会撞名字
    all_paths = [config.TaskPaths(task_no, n) for n in range(1, rounds + 1)]
    steps: list[dict] = []

    # 1. 容器：残留的先销毁，否则下次启动会撞名字。续跑过的题各轮都要清
    names = {p.container_name for p in all_paths} | {container}
    removed, failed = [], []
    for name in sorted(n for n in names if n):
        if not await dockerx.container_state(name):
            continue
        r = await dockerx.remove_container(name)
        (removed if r.ok else failed).append(name if r.ok else f"{name}({r.err.strip()[:80]})")
    if failed:
        steps.append(_step("销毁容器", False, "；".join(failed)[:300]))
    elif removed:
        steps.append(_step("销毁容器", True, f"已删除 {'、'.join(removed)}"))
    else:
        steps.append(_step("销毁容器", True, "没有残留容器" if not had_container else f"容器 {container} 已不存在"))

    # 2. 工作区：回到初始快照的 commit，并清掉未跟踪文件
    with session() as db:
        t = db.get(Task, task_id)
        assert t is not None
        r = await gate.reset_to_snapshot(t)
    steps.append(_step("工作区回到初始快照", bool(r.get("ok")), str(r.get("message", ""))[:300]))

    # 3. 轨迹与分析产物：各轮逐个清，续跑过的题漏一轮就会把上一轮的结果混进下一轮
    for p in all_paths:
        tag = "轨迹目录" if p.round_no == 1 else f"第 {p.round_no} 轮轨迹目录"
        if archive:
            a = gate.archive_traces(task_no, p.round_no)
            steps.append(_step(f"归档{tag}", bool(a.get("ok")), str(a.get("message", ""))[:200]))
        else:
            ok, msg = _rmtree(p.traces)
            steps.append(_step(f"清空{tag}", ok, msg))
        ok, msg = _rmtree(p.export)
        steps.append(_step(f"删除导出的轨迹副本{p.round_suffix}", ok, msg))
    ok, msg = _rmtree(paths.analysis)
    steps.append(_step("删除分析中间产物", ok, msg))
    if not archive:
        ok, msg = _purge_archived(task_no)
        steps.append(_step("清掉历史归档的轨迹目录", ok, msg))

    # 4. prompt.md：把回填过的两行写回占位，否则重跑后新旧 SessionID 混在一起
    if backfilled:
        try:
            n = 0
            for path in (config.prompt_file(), paths.prompt_archive):
                n += prompt_bank.backfill_file(path, task_no, prompt_hash, PENDING_SESSION, PENDING_TURN)
            steps.append(_step("prompt.md 回填复位", True, f"改回 {n} 行占位"))
        except OSError as exc:
            steps.append(_step("prompt.md 回填复位", False, str(exc)[:200]))
    else:
        steps.append(_step("prompt.md 回填复位", True, "本题没有回填过"))

    # 5. 数据库：运行、分析、评审、质检的痕迹全部清掉，回到待领取
    with session() as db:
        t = db.get(Task, task_id)
        assert t is not None
        db.query(RunEvent).filter(RunEvent.task_id == task_id).delete()
        t.status = AVAILABLE
        t.session_id = t.turn_id = ""
        t.round_no = 1
        t.rounds_json = "[]"
        t.continue_prompt = ""
        t.container_name = paths.container_name
        t.container_exists = False
        t.image_tag = ""
        t.exit_code = None
        t.result_json = t.verdict_json = t.trace_summary_json = "{}"
        t.trace_file = ""
        t.git_diff_stat = ""
        t.error = ""
        t.analysis_status = ANALYSIS_IDLE
        t.analysis_json = t.review_json = t.verify_json = t.upload_json = "{}"
        t.qc_status = QC_IDLE
        t.qc_json = "{}"
        t.qc_at = None
        t.auto_stage = STAGE_IDLE
        t.auto_error = ""
        t.discarded_from = ""
        t.discarded_at = None
        t.claimed_at = t.started_at = t.finished_at = t.uploaded_at = t.done_at = None
    steps.append(_step("任务状态回到待领取", True, "运行、分析、评审、质检记录已清空"))

    bus.publish("tasks", {"type": "task", "id": task_id})
    ok = all(s["ok"] for s in steps)
    log.info("重置题 %s：%s", task_no, "全部完成" if ok else "有步骤未完成")
    return {"ok": ok, "steps": steps}


def _purge_archived(task_no: str) -> tuple[bool, str]:
    """删掉这道题以前 reset 归档下来的目录。

    归档目录形如 01.archived-20260916-101530、01-r2.archived-...，是历次还原攒下的，
    既然这次是彻底还原，一并收掉，免得越攒越多。
    """
    root = config.TaskPaths(task_no).traces.parent
    if not root.is_dir():
        return True, "轨迹根目录不存在"
    stale = sorted(root.glob(f"{task_no}.archived-*")) + sorted(root.glob(f"{task_no}-r*.archived-*"))
    if not stale:
        return True, "没有历史归档"
    failed = []
    for d in stale:
        ok, msg = _rmtree(d)
        if not ok:
            failed.append(f"{d.name}({msg})")
    if failed:
        return False, "；".join(failed)[:300]
    return True, f"已删除 {len(stale)} 个归档目录"


def _rmtree(path) -> tuple[bool, str]:  # noqa: ANN001
    if not path.exists():
        return True, "目录不存在"
    try:
        shutil.rmtree(path)
        return True, f"已删除 {path.name}"
    except OSError as exc:
        return False, str(exc)[:200]
