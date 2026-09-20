"""请求体与序列化。"""

from __future__ import annotations

from datetime import timezone
from typing import Any

from pydantic import BaseModel, Field

from app.models import Task, TaskRun
from app.services import gsb_repo


class SettingsUpdate(BaseModel):
    values: dict[str, str]


class GsbUpdate(BaseModel):
    """人工修改 GSB 结论。字段与分析产出一致，逐个可改。"""

    verdict: str = ""
    reason: str = ""
    a_startup: dict[str, Any] | None = None
    b_startup: dict[str, Any] | None = None
    validity: str = ""
    remark: str = ""


class ScreencastUpdate(BaseModel):
    """两侧录屏链接。只传一侧就只改一侧。"""

    A: str | None = None
    B: str | None = None


class RerunRequest(BaseModel):
    """重跑哪几侧。留空表示两侧都重跑。"""

    sides: list[str] = Field(default_factory=list)


class IdList(BaseModel):
    ids: list[int]


class RerunBatch(IdList):
    """批量重跑：ids 是题，sides 留空表示每道题两侧都重跑。"""

    sides: list[str] = Field(default_factory=list)


class DesignStart(BaseModel):
    count: int = 1
    note: str = ""


class QueueMove(BaseModel):
    """队列调序：direction 为 top/up/down/bottom，或直接给 priority。"""

    direction: str = ""
    priority: int | None = None


def _iso(dt) -> str | None:  # noqa: ANN001
    """SQLite 不保存时区，统一按 UTC 补 Z，前端再转本地时间。"""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def run_brief(r: TaskRun) -> dict:
    v = r.verdict or {}
    return {
        "id": r.id,
        "side": r.side,
        "status": r.status,
        "attempt": r.attempt,
        "timeouts": r.timeouts,
        "container_name": r.container_name,
        "container_exists": r.container_exists,
        "image_tag": r.image_tag,
        "exit_code": r.exit_code,
        "session_id": r.session_id,
        "turn_id": r.turn_id,
        "trace_file": r.trace_file,
        "artifact_sha": r.artifact_sha,
        "artifact_url": r.artifact_url,
        "protocol": v.get("protocol") or {},
        "artifact": v.get("artifact") or {},
        "gateway_errors": (v.get("process") or {}).get("gateway_errors") or [],
        "notes": v.get("notes") or [],
        "abnormal": r.abnormal,
        "error": r.error,
        "started_at": _iso(r.started_at),
        "finished_at": _iso(r.finished_at),
    }


def run_detail(r: TaskRun) -> dict:
    d = run_brief(r)
    d.update({
        "result": r.result,
        "verdict": r.verdict,
        "trace_summary": r.trace_summary,
        "git_diff_stat": r.git_diff_stat,
    })
    return d


def task_brief(t: Task, runs: list[TaskRun] | None = None) -> dict:
    gsb = t.gsb or {}
    return {
        "id": t.id,
        "task_no": t.task_no,
        "status": t.status,
        "analysis_status": t.analysis_status,
        "question_type": t.question_type,
        "difficulty": t.difficulty,
        "languages": t.languages,
        "harness": t.harness,
        "harness_version": t.harness_version,
        "os_platform": t.os_platform,
        "repro_level": t.repro_level,
        "env_snapshot": t.env_snapshot,
        "repo_url": t.repo_url,
        "repo_slug": gsb_repo.repo_slug(t.repo_url),
        "branch_check": t.branch_check,
        "prompt_preview": (t.user_prompt or "")[:220],
        "prompt_chars": len(t.user_prompt or ""),
        "meta": t.meta,
        "gsb_verdict": gsb.get("verdict", ""),
        "gsb_reason_chars": len(gsb.get("reason") or ""),
        "screencast": t.screencast,
        "verify_overall": (t.verify or {}).get("overall"),
        "verify_blocked": (t.verify or {}).get("blocked") or 0,
        "upload_ok": (t.upload or {}).get("ok"),
        "submission_id": (t.upload or {}).get("submission_id"),
        "priority": t.priority,
        "origin": t.origin,
        "pool_device": t.pool_device,
        "claimed_by": t.claimed_by,
        "design_run_id": t.design_run_id,
        "auto_stage": t.auto_stage,
        "auto_error": t.auto_error,
        "dedup_verdict": (t.dedup or {}).get("verdict") or "",
        "dedup_reason": (t.dedup or {}).get("reason") or (t.dedup or {}).get("error") or "",
        "created_at": _iso(t.created_at),
        "claimed_at": _iso(t.claimed_at),
        "finished_at": _iso(t.finished_at),
        "uploaded_at": _iso(t.uploaded_at),
        "done_at": _iso(t.done_at),
        "discarded_at": _iso(t.discarded_at),
        "discarded_from": t.discarded_from,
        "runs": [run_brief(r) for r in sorted(runs or [], key=lambda x: x.side)],
    }


def task_detail(t: Task, runs: list[TaskRun] | None = None) -> dict:
    d = task_brief(t, runs)
    d.update({
        "user_prompt": t.user_prompt,
        "gsb": t.gsb,
        "analysis": t.analysis,
        "verify": t.verify,
        "upload": t.upload,
        "dedup": t.dedup,
        "runs": [run_detail(r) for r in sorted(runs or [], key=lambda x: x.side)],
    })
    return d


def design_run(r) -> dict:  # noqa: ANN001
    return {
        "id": r.id,
        "count": r.count,
        "status": r.status,
        "model": r.model,
        "note": r.note,
        "error": r.error,
        "stats": r.stats,
        "task_ids": r.task_ids,
        "log_tail": (r.log or "")[-4000:],
        "created_at": _iso(r.created_at),
        "started_at": _iso(r.started_at),
        "finished_at": _iso(r.finished_at),
    }
