"""逐次运行记录与「最近废弃」。

TaskRun 一侧只有一行，重跑时整行清空复用：上一次几点开始、跑了多久、为什么没算数，
清完就没了。人回头看一道被废掉的题，想知道的恰恰是这些——三次各跑了多久、每次
卡在哪、最后是撞了哪个上限。所以每次清空之前，以及整道题被废掉的那一刻，在
run_attempt 里记一笔。

这张表上线之前废掉的题没有记录。它们的前几次只剩磁盘上的轨迹归档（重跑前整个
目录改名成 `A.archived-时间戳`），会话 jsonl 的首尾时间戳就是那一次的起止，原因
已经无从追回，界面上照实标成旧记录。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app import config
from app.db import session
from app.models import (
    DISCARDED, RUN_FINISHED, RunAttempt, Task, TaskRun, as_utc, utc_now,
)

OUTCOME_LABEL = {
    "retry": "异常，自动重跑",
    "net_retry": "断网跑挂，重跑不计次数",
    "manual": "人工重跑",
    "discard": "重跑预算用尽，整题废弃",
    "interrupted": "整题被废弃，中途停掉",
    "finished": "正常跑完，随整题废弃",
    "failed": "没跑成，随整题废弃",
    "legacy": "被重跑（旧记录）",
}
RETRY_OUTCOMES = ("retry", "net_retry", "manual", "legacy")

KIND_LABEL = {
    "retries": "重跑次数耗尽",
    "timeouts": "超时次数耗尽",
    "prep": "重跑准备耗尽",
    "difficulty": "难度不足",
    "dedup": "查重命中",
    "manual": "人工废弃",
    "other": "其他",
}
_PREFIX = "自动废弃："


def discard_kind(reason: str) -> str:
    """按废弃理由归类。理由是各处拼好的一句话，这里认的是它们固定的那几个片段，
    历史数据也是同一套写法，所以老题一样能分出来。"""
    text = reason or ""
    if "人工废弃" in text:
        return "manual"
    if "重跑准备连续" in text:
        return "prep"
    if re.search(r"超时 \d+ 次，达到上限", text):
        return "timeouts"
    if re.search(r"已跑 \d+ 次，达到上限", text):
        return "retries"
    if "难度筛选" in text or "探路" in text:
        return "difficulty"
    if "查重" in text:
        return "dedup"
    return "other"


def clean_reason(reason: str) -> str:
    text = (reason or "").strip()
    return text[len(_PREFIX):] if text.startswith(_PREFIX) else text


# ---------------- 记账 ----------------

def record(db, run: TaskRun, outcome: str, reason: str) -> bool:  # noqa: ANN001
    """把 run 当前这一次记下来。没开跑过的不记，同一次记过的不重复记。"""
    if run.started_at is None:
        return False
    seen = db.execute(select(RunAttempt.id).where(
        RunAttempt.task_id == run.task_id, RunAttempt.side == run.side,
        RunAttempt.attempt == run.attempt, RunAttempt.started_at == run.started_at,
    )).first()
    if seen:
        return False
    db.add(RunAttempt(
        task_id=run.task_id, side=run.side, attempt=run.attempt, run_status=run.status or "",
        outcome=outcome, reason=(reason or "")[:2000],
        started_at=run.started_at, finished_at=run.finished_at or utc_now(),
    ))
    return True


def discard_outcome(run: TaskRun, stopped: bool) -> tuple[str, str]:
    """整题被废掉时，这一侧当前这一次算什么结局、附一句什么话。"""
    ab = run.abnormal or {}
    if ab.get("gave_up"):
        return "discard", ab.get("reason") or ""
    if stopped:
        return "interrupted", "整道题被废弃，这一侧跑到一半被停掉"
    if run.status == RUN_FINISHED and not ab.get("reason"):
        return "finished", "这一侧正常跑完，随整道题一起废弃"
    return "failed", ab.get("reason") or run.error or ""


# ---------------- 旧题：从轨迹归档补出前几次 ----------------

_span_cache: dict[tuple[str, int, int], tuple[datetime, datetime] | None] = {}


def _ts(line: str) -> datetime | None:
    try:
        v = json.loads(line).get("timestamp")
    except (ValueError, AttributeError):
        return None
    if not isinstance(v, str):
        return None
    try:
        return as_utc(datetime.fromisoformat(v.replace("Z", "+00:00")))
    except ValueError:
        return None


def _file_span(path: Path) -> tuple[datetime, datetime] | None:
    """一份会话 jsonl 的首尾时间戳。只读开头几十行和末尾一段，轨迹动辄几十 MB。"""
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _span_cache:
        return _span_cache[key]
    first = last = None
    with path.open("rb") as f:
        for _ in range(50):
            raw = f.readline()
            if not raw:
                break
            if (first := _ts(raw.decode("utf-8", "replace"))) is not None:
                break
        f.seek(max(0, st.st_size - 256 * 1024))
        for raw in reversed(f.read().splitlines()):
            if (last := _ts(raw.decode("utf-8", "replace"))) is not None:
                break
    span = (first, last or first) if first else None
    _span_cache[key] = span
    return span


def _archive_spans(task_no: str, side: str) -> list[tuple[datetime, datetime]]:
    traces = config.TaskPaths(task_no, side).traces
    if not traces.parent.exists():
        return []
    spans = []
    for d in sorted(traces.parent.glob(f"{side}.archived-*")):
        found = [s for f in d.rglob("*.jsonl") if (s := _file_span(f))]
        if found:
            spans.append((min(s[0] for s in found), max(s[1] for s in found)))
    return spans


def _covered(start: datetime, end: datetime, rows: list[dict]) -> bool:
    """这段时间是不是已经有一笔记录了。只认真正交叠，不留余量：自动重跑往往前一次
    刚结束半分钟就开跑下一次，留几分钟余量会把相邻的两次认成同一次。"""
    for r in rows:
        s, e = r["_start"], r["_end"] or utc_now()
        if s and (start == s or (start < e and end > s)):
            return True
    return False


# ---------------- 组装 ----------------

def _iso(dt: datetime | None) -> str | None:
    dt = as_utc(dt)
    return dt.isoformat() if dt else None


def _side_history(task: Task, run: TaskRun | None, recs: list[RunAttempt]) -> dict:
    rows = [{
        "attempt": r.attempt, "outcome": r.outcome, "run_status": r.run_status, "reason": r.reason,
        "_start": as_utc(r.started_at), "_end": as_utc(r.finished_at), "legacy": False,
    } for r in recs]
    side = run.side if run else (recs[0].side if recs else "")
    for start, end in _archive_spans(task.task_no, side) if side else []:
        if not _covered(start, end, rows):
            rows.append({"attempt": None, "outcome": "legacy", "run_status": "",
                         "reason": "本记录上线前的一次，失败原因没有留存", "_start": start,
                         "_end": end, "legacy": True})
    if run is not None and run.started_at is not None:
        start, end = as_utc(run.started_at), as_utc(run.finished_at)
        if not _covered(start, end or utc_now(), rows):
            outcome, reason = discard_outcome(run, False)
            rows.append({"attempt": run.attempt, "outcome": outcome, "run_status": run.status,
                         "reason": reason, "_start": start, "_end": end, "legacy": True})
        # 归档被清理过的老题，计数比找得到的次数多。缺的那几次照数补上占位，否则界面上
        # 「已跑 3 次」底下只列出一次，人会以为是记录写错了。有新记录的侧不补：人工重跑
        # 会把计数清零，那时计数和次数本来就不该对得上。
        if not recs:
            for _ in range(run.attempt - len(rows)):
                rows.append({"attempt": None, "outcome": "legacy", "run_status": "",
                             "reason": "轨迹归档已清理，这一次的时间与原因都无从追回",
                             "_start": None, "_end": None, "legacy": True, "_unknown": True})
    rows.sort(key=lambda r: (not r.pop("_unknown", False), r["_start"] or utc_now()))
    prev_end = None
    out = []
    for i, r in enumerate(rows, 1):
        s, e = r.pop("_start"), r.pop("_end")
        r.update({
            "seq": i,
            "outcome_label": OUTCOME_LABEL.get(r["outcome"], r["outcome"]),
            "started_at": _iso(s), "finished_at": _iso(e),
            "duration_s": int((e - s).total_seconds()) if s and e else None,
            # 上一次结束到这一次开跑之间：归档、重建工作区、再排队等槽位
            "wait_s": int((s - prev_end).total_seconds()) if s and prev_end and s > prev_end else None,
        })
        prev_end = e or prev_end
        out.append(r)
    return {
        "side": side,
        "status": run.status if run else "",
        "attempt": run.attempt if run else 0,
        "timeouts": run.timeouts if run else 0,
        "retries": sum(1 for r in out if r["outcome"] in RETRY_OUTCOMES),
        "run_s": sum(r["duration_s"] or 0 for r in out),
        "attempts": out,
    }


def _discards(task: Task) -> list[dict]:
    log = list(task.discard_log or [])
    if not log and task.discarded_at:
        log = [{"at": _iso(task.discarded_at), "reason": task.auto_error,
                "from": task.discarded_from, "legacy": True}]
    return [{**d, "reason": clean_reason(d.get("reason") or ""),
             "kind": discard_kind(d.get("reason") or ""),
             "kind_label": KIND_LABEL[discard_kind(d.get("reason") or "")]} for d in log]


def task_history(task: Task, runs: list[TaskRun], recs: list[RunAttempt]) -> dict:
    by_side = {r.side: r for r in runs}
    sides = [_side_history(task, by_side.get(s), [r for r in recs if r.side == s])
             for s in config.SIDES if s in by_side or any(r.side == s for r in recs)]
    reason = clean_reason(task.auto_error)
    kind = discard_kind(task.auto_error)
    discards = _discards(task)
    return {
        "id": task.id,
        "task_no": task.task_no,
        "question_type": task.question_type,
        "languages": task.languages,
        "run_mode": task.run_mode,
        "discarded_at": _iso(task.discarded_at),
        "discarded_from": task.discarded_from,
        "reason": reason,
        "kind": kind,
        "kind_label": KIND_LABEL[kind],
        "discard_count": len(discards),
        "discards": discards,
        "retries": sum(s["retries"] for s in sides),
        "run_s": sum(s["run_s"] for s in sides),
        "legacy": any(a["legacy"] for s in sides for a in s["attempts"]),
        "sides": sides,
    }


def recent_discarded(days: int = 7) -> dict:
    since = utc_now() - timedelta(days=max(1, days))
    with session() as db:
        tasks = list(db.execute(select(Task).where(
            Task.status == DISCARDED, Task.discarded_at >= since.replace(tzinfo=None),
        ).order_by(Task.discarded_at.desc())).scalars())
        ids = [t.id for t in tasks]
        runs = list(db.execute(select(TaskRun).where(TaskRun.task_id.in_(ids))).scalars()) if ids else []
        recs = list(db.execute(select(RunAttempt).where(RunAttempt.task_id.in_(ids))
                               .order_by(RunAttempt.started_at)).scalars()) if ids else []
    # 拼装要读轨迹归档，放到会话外面做，别拿着库连接等磁盘
    items = [task_history(t, [r for r in runs if r.task_id == t.id],
                          [r for r in recs if r.task_id == t.id]) for t in tasks]
    return {"days": days, "items": items}
