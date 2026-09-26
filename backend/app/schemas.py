"""请求体与序列化。"""

from __future__ import annotations

from datetime import timezone
from typing import Any

from pydantic import BaseModel, Field

from app.models import SETTLING, Task, TaskRun
from app.services import gsb_factcheck, gsb_precheck, gsb_repo, scope


class SettingsUpdate(BaseModel):
    values: dict[str, str]


class GsbUpdate(BaseModel):
    """人工修改 GSB 结论。字段与分析产出一致，逐个可改。"""

    verdict: str = ""
    reason: str = ""
    a_startup: dict[str, Any] | None = None
    b_startup: dict[str, Any] | None = None
    # 交付完整性：{"score": 1-5, "desc": "…"}。不传就不动
    a_delivery: dict[str, Any] | None = None
    b_delivery: dict[str, Any] | None = None
    validity: str = ""
    remark: str = ""


class ScreencastUpdate(BaseModel):
    """两侧录屏链接。只传一侧就只改一侧。"""

    A: str | None = None
    B: str | None = None


class PrecheckConfirm(BaseModel):
    """人工放行提交前质检。note 记一句为什么放行，只给自己看。"""

    note: str = ""


class ScreencastDeliver(BaseModel):
    """交付录屏：给两侧的本地视频路径，收下、代传、顺手提交。

    录屏是在外部录完的，人手上只有两个文件路径。这里收路径而不是收链接，是因为
    从路径到链接那几步（归档到题目目录、传给平台、把返回的地址填进去）每次都一样，
    没有让人分三次点的理由。

    submit 为真就接着走提交。默认为真：走到这一步，两道质检早就放行了，
    录屏是最后一个缺的参数，补上就该交出去。
    """

    A: str | None = None
    B: str | None = None
    submit: bool = True


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
    precheck = t.precheck or {}
    factcheck = t.factcheck or {}
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
        # 提交前质检。按 verify 的做法在列表里摊成几个扁平字段，详情页才给完整报告。
        # precheck_block 是能不能提交的唯一口径（空串表示能），界面上按钮灰不灰、
        # 提示写什么都照它来，免得前端自己凑一套条件，和后端回绝的理由对不上。
        "precheck_status": t.precheck_status,
        "precheck_issues": len(precheck.get("issues") or []),
        # 质检会直接改写理由正文。改过的题在列表上要看得出来，否则人翻到详情页才发现
        # 现在这段话不是分析当时那一段，而改前那一稿存在 precheck.reason_before 里。
        "precheck_applied": bool(precheck.get("applied")),
        "precheck_summary": precheck.get("summary") or precheck.get("error") or "",
        "precheck_stale": gsb_precheck.stale(t),
        # 能不能提交的唯一口径。两道质检、录屏、状态全在里面判完，空串表示能提交。
        "precheck_block": gsb_precheck.submit_block(t),
        "precheck_at": precheck.get("confirmed_at") or precheck.get("finished_at") or "",
        # 事实核验。和措辞质检摊法一致：列表给几个扁平字段，完整报告在详情页。
        # notes 是订正留痕，人扫一眼就知道动过哪几处，不必拿改前改后两稿逐字对。
        "factcheck_status": t.factcheck_status,
        "factcheck_mismatches": len(factcheck.get("mismatches") or []),
        "factcheck_applied": bool(factcheck.get("applied")),
        "factcheck_notes": factcheck.get("notes") or [],
        "factcheck_summary": factcheck.get("summary") or factcheck.get("error") or "",
        "factcheck_stale": gsb_factcheck.stale(t),
        # 事实核验没放行时给人看的那句话。理由核对过了、只是交付完整性没对上的题，
        # mismatches 是 0，照着它拼只会得出一句「0 处不符」，人看不懂卡在哪
        "factcheck_block": gsb_factcheck.factcheck_block(t) if t.status in SETTLING else "",
        "factcheck_auto_retries": int(factcheck.get("auto_retries") or 0),
        # 难度筛选结论。整份给出去而不是摊成扁平字段：里面是两侧的四个数加一句话，
        # 界面上要么不显示、要么就得把数字一起显示出来，摊开反而要在前端拼回去。
        "difficulty_screen": t.difficulty_screen,
        # 开跑前的改动面结论。只给一句话和拦不拦，模块清单留给详情页的门禁面板：
        # 列表上真正要回答的问题只有「这道题现在能不能领」。
        "scope_verdict": (t.scope or {}).get("verdict") or "",
        "scope_blocked": bool(scope.blocking(t)),
        "scope_summary": scope.summary(t.scope) if t.scope else "",
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
        "precheck": t.precheck,
        "factcheck": t.factcheck,
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
