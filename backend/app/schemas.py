"""请求体与序列化。"""

from __future__ import annotations

from datetime import timezone
from typing import Any

from pydantic import BaseModel, Field

from app.models import Task


class SettingsUpdate(BaseModel):
    values: dict[str, str]


class ReviewUpdate(BaseModel):
    scores: dict[str, int | None] = Field(default_factory=dict)
    descs: dict[str, str] = Field(default_factory=dict)
    other_issues: str = ""
    evidence: dict[str, list[dict[str, Any]]] | None = None
    coverage: list[dict[str, Any]] | None = None


class IdList(BaseModel):
    ids: list[int]


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


def task_brief(t: Task) -> dict:
    v = t.verdict or {}
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
        "prompt_preview": (t.user_prompt or "")[:220],
        "prompt_chars": len(t.user_prompt or ""),
        "session_id": t.session_id,
        "turn_id": t.turn_id,
        "container_name": t.container_name,
        "container_exists": t.container_exists,
        "image_tag": t.image_tag,
        "exit_code": t.exit_code,
        "meta": t.meta,
        "verdict_notes": v.get("notes") or [],
        "protocol": v.get("protocol") or {},
        "artifact": v.get("artifact") or {},
        "verify_overall": (t.verify or {}).get("overall"),
        "upload_ok": (t.upload or {}).get("ok"),
        "submission_id": (t.upload or {}).get("submission_id"),
        "error": t.error,
        "created_at": _iso(t.created_at),
        "claimed_at": _iso(t.claimed_at),
        "started_at": _iso(t.started_at),
        "finished_at": _iso(t.finished_at),
        "uploaded_at": _iso(t.uploaded_at),
        "done_at": _iso(t.done_at),
        "discarded_at": _iso(t.discarded_at),
        "discarded_from": t.discarded_from,
        "qc_status": t.qc_status,
        "qc_conclusion": (t.qc or {}).get("conclusion") or "",
        "qc_summary": (t.qc or {}).get("summary") or (t.qc or {}).get("error") or "",
        "qc_failed_count": len((t.qc or {}).get("failed_checks") or []),
        "qc_at": _iso(t.qc_at),
        "priority": t.priority,
        "origin": t.origin,
        "design_run_id": t.design_run_id,
        "auto_stage": t.auto_stage,
        "auto_error": t.auto_error,
        "dedup_verdict": (t.dedup or {}).get("verdict") or "",
        "dedup_reason": (t.dedup or {}).get("reason") or (t.dedup or {}).get("error") or "",
    }


def task_detail(t: Task) -> dict:
    d = task_brief(t)
    d.update({
        "user_prompt": t.user_prompt,
        "result": t.result,
        "verdict": t.verdict,
        "trace_summary": t.trace_summary,
        "trace_file": t.trace_file,
        "git_diff_stat": t.git_diff_stat,
        "analysis": t.analysis,
        "review": t.review,
        "verify": t.verify,
        "upload": t.upload,
        "qc": t.qc,
        "dedup": t.dedup,
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
