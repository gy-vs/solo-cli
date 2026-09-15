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


async def reset_task(task_id: int, *, archive: bool = True) -> dict:
    """还原一道题。archive=True 时轨迹与产物先归档再清空，False 直接删。"""
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "steps": [_step("查找任务", False, "任务不存在")]}
        if t.status in (RUNNING, QUEUED):
            return {"ok": False, "blocked": True,
                    "steps": [_step("检查状态", False, "运行中或排队中，请先停止或放回题库")]}
        task_no, container, had_container = t.task_no, t.container_name, t.container_exists
        prompt_hash, backfilled = t.prompt_hash, bool(t.session_id or t.turn_id)

    paths = config.TaskPaths(task_no)
    steps: list[dict] = []

    # 1. 容器：残留的先销毁，否则下次启动会撞名字
    if had_container:
        r = await dockerx.remove_container(container)
        steps.append(_step("销毁容器", r.ok, r.err.strip()[:200] or f"已删除 {container}"))
    else:
        steps.append(_step("销毁容器", True, "没有残留容器"))

    # 2. 工作区：回到初始快照的 commit，并清掉未跟踪文件
    with session() as db:
        t = db.get(Task, task_id)
        assert t is not None
        r = await gate.reset_to_snapshot(t)
    steps.append(_step("工作区回到初始快照", bool(r.get("ok")), str(r.get("message", ""))[:300]))

    # 3. 轨迹与分析产物：默认归档保底，不直接毁掉证据
    if archive:
        a = gate.archive_traces(task_no)
        steps.append(_step("归档轨迹目录", bool(a.get("ok")), str(a.get("message", ""))[:200]))
    else:
        ok, msg = _rmtree(paths.traces)
        steps.append(_step("清空轨迹目录", ok, msg))
    for label, d in (("导出的轨迹副本", paths.export), ("分析中间产物", paths.analysis)):
        ok, msg = _rmtree(d)
        steps.append(_step(f"删除{label}", ok, msg))

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


def _rmtree(path) -> tuple[bool, str]:  # noqa: ANN001
    if not path.exists():
        return True, "目录不存在"
    try:
        shutil.rmtree(path)
        return True, f"已删除 {path.name}"
    except OSError as exc:
        return False, str(exc)[:200]
