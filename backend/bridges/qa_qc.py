"""质检桥接：把一条本地提交送进 solo-qa 的质检链路，只取结论不落任何库。

和 `qa_dedup.py` 一样跑在 `solo-qa-backend` 镜像里，只用标准库 + solo-qa 自己的包。

切入点选 `qc.runner.evaluate_one()`：它跑完 S1 → P1 → 本地规则 → 查重 A/B/C →
轨迹 T 组 → 描述 D/E/F → 裁决，但**不写任何状态**（状态落地在 `apply_result()`，
飞书同步在 `run_batch()` 尾部，两者都不调用）。区间内确认没有 commit / add / flush。

三处默认会碰库或写库的依赖按 solo-qa 自己的 `scripts/qc_lark_table.py` 的做法替换：
- `trace.store.build_digest` → 读本地轨迹文件（原实现读本地暂存或 COS）
- `trace.store.save_digest`  → 空操作（原实现写 trace_digest 表）
- `rules_session.load_session_rounds` → 用入参给的轮次（本条不在库里，查不到）
另外关掉 `qc.llm_cache_enabled`，避免描述质检写 qc_llm_cache。
db 传真实 session 供规则 C 与描述质检读库，退出前 rollback。

协议：stdin 一个 JSON 对象，stdout 一个 JSON 对象，日志全部走 stderr。
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _check_json(c) -> dict:
    return {
        "key": c.check_key,
        "name": c.check_name,
        "passed": bool(c.passed),
        "summary": c.summary or "",
        "detail": c.detail or "",
        "evidence": c.evidence or {},
    }


async def run(payload: dict) -> dict:
    from sqlalchemy import func, select

    from backend import config_center
    from backend.db import dispose_engine, get_session_factory
    from backend.models import Submission
    from backend.qc import rules_session, runner
    from backend.qc.trace import reader, store
    from backend.dedup.service import DedupOutcome, DedupTarget, DedupUnavailable, run_dedup
    from backend.services import submission_service
    from backend.states import SUBMITTED
    from backend.validators import normalize_payload

    data = payload.get("submission") or {}
    if not data:
        return {"ok": False, "error": "submission 为空"}
    trace_path = str(payload.get("trace_path") or "").strip()
    trace_name = str(payload.get("trace_name") or "").strip() or (
        Path(trace_path).name if trace_path else ""
    )

    factory = get_session_factory()
    async with factory() as db:
        await config_center.refresh(db)
        max_id = (await db.execute(select(func.max(Submission.id)))).scalar() or 0
    row_id = int(max_id) + 1000

    # ---------- 进程内替换：轨迹来源 / 摘要落库 / 同题轮次 ----------
    async def build_digest_local(submission):
        if not trace_path:
            return None, "未上传轨迹文件"
        p = Path(trace_path)
        if not p.exists():
            raise store.TraceUnavailable(f"轨迹文件不存在：{trace_path}")
        try:
            digest = await asyncio.to_thread(reader.parse_path, p)
        except reader.TraceFormatError as e:
            return None, str(e)
        except Exception as e:  # noqa: BLE001
            raise store.TraceUnavailable(f"轨迹解析异常：{type(e).__name__}: {e}") from e
        if not digest.file_name:
            digest.file_name = trace_name
        if not digest.format_ok:
            return digest, f"「{trace_name}」不是 Claude Code 或 Codex CLI 的轨迹文件"
        return digest, ""

    async def save_digest_noop(*a, **k):
        return None

    holder: dict = {}

    async def load_session_rounds_local(db, user_id, session_id):
        """同题轮次。solo-cli 一题只跑一轮，本条自己就是首轮。"""
        sub = holder.get("sub")
        return [sub] if sub is not None and session_id else []

    store.build_digest = build_digest_local
    store.save_digest = save_digest_noop
    rules_session.load_session_rounds = load_session_rounds_local
    config_center.set_local_override("qc.llm_cache_enabled", False)
    if config_center.get_int("qc.llm_timeout_seconds") < 300:
        config_center.set_local_override("qc.llm_timeout_seconds", 300)
    if config_center.get_int("dedup.c.max_tokens") < 8192:
        config_center.set_local_override("dedup.c.max_tokens", 8192)

    # ---------- 组装一个不入 session 的 Submission ----------
    payload_data = normalize_payload(dict(data))
    payload_data.setdefault("x_iteration", int(payload.get("round_no") or 1))

    now = datetime.now(timezone.utc)
    sub = Submission()
    sub.id = row_id
    sub.user_id = int(payload.get("user_id") or 0)
    sub.submitter_name = str(payload.get("submitter") or "solo-cli")
    sub.status = SUBMITTED
    sub.round_no = int(payload.get("round_no") or 1)
    sub.current_version = 1
    sub.schema_stale = 0
    sub.deleted_at = None
    sub.submitted_at = now
    sub.submitted_date = (now.astimezone(timezone.utc)).strftime("%Y-%m-%d")
    sub.qc_conclusion = None
    sub.qc_summary = None
    sub.qc_hit_rule = ""
    sub.qc_confidence = 0
    sub.qc_needs_review = 0
    sub.qc_risk_flag = ""
    sub.qc_risk_note = ""
    sub.lark_record_id = ""
    sub.lark_sync_status = ""
    sub.extra_json = None
    sub.created_at = None
    sub.qc_finished_at = None
    sub.lark_synced_at = None
    submission_service.apply_payload(sub, payload_data)
    # 轨迹文件引用：path 留空，实际内容由上面的 build_digest 替换件从本地读
    sub.trace_file_json = json.dumps(
        [{"name": trace_name or "trace.jsonl", "path": "", "size": int(payload.get("trace_size") or 0)}],
        ensure_ascii=False,
    )
    holder["sub"] = sub

    # ---------- 查重 A/B（质检链路的必经步骤） ----------
    dedup_ok = True
    dedup_error = ""
    try:
        from backend.states import DEDUP_FIELDS, SCORE_DIMENSIONS

        target = DedupTarget(
            row_id=row_id,
            repo_id=sub.repo_id or "",
            seq=f"solo-cli:{payload.get('task_no') or row_id}",
            submit_date=sub.submitted_date or "",
            submitter=sub.submitter_name or "",
            texts={f: getattr(sub, f, "") or "" for f in DEDUP_FIELDS},
            scores={
                desc_field: int(getattr(sub, score_key, 0) or 0)
                for score_key, _, desc_field in SCORE_DIMENSIONS
            },
        )
        outcome = (await run_dedup([target]))[row_id]
    except DedupUnavailable as e:
        dedup_ok = False
        dedup_error = str(e)
        outcome = DedupOutcome(row_id=row_id)
    except Exception as e:  # noqa: BLE001
        dedup_ok = False
        dedup_error = f"{type(e).__name__}: {e}"
        outcome = DedupOutcome(row_id=row_id)

    # ---------- 正式质检 ----------
    async with factory() as db:
        try:
            result = await runner.evaluate_one(
                sub,
                outcome,
                dedup_ok=dedup_ok,
                llm_semaphore=None,
                db=db,
                skip_llm=bool(payload.get("skip_llm")),
            )
        finally:
            await db.rollback()

    await dispose_engine()

    checks = [_check_json(c) for c in result.checks]
    return {
        "ok": True,
        "row_id": row_id,
        "conclusion": result.conclusion,
        "to_status": result.to_status,
        "hit_rule": result.hit_rule,
        "summary": result.summary,
        "confidence": int(result.confidence or 0),
        "needs_review": bool(result.needs_review),
        "risk_flag": result.risk_flag or "",
        "risk_note": result.risk_note or "",
        "error": result.error or "",
        "hard_ms": int(result.hard_ms or 0),
        "llm_ms": int(result.llm_ms or 0),
        "dedup": {
            "ok": dedup_ok,
            "error": dedup_error,
            "summary": outcome.summary() if outcome.hits else "",
            "hit_rule_a": outcome.hit_rule_a,
            "hit_rule_b": outcome.hit_rule_b,
        },
        "checks": checks,
        "failed_checks": [c for c in checks if not c["passed"]],
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"stdin 不是合法 JSON：{e}"}, ensure_ascii=False))
        return 2
    try:
        result = asyncio.run(run(payload))
    except Exception as e:  # noqa: BLE001
        log(traceback.format_exc())
        tb = traceback.extract_tb(e.__traceback__)
        where = f"{Path(tb[-1].filename).name}:{tb[-1].lineno}" if tb else "?"
        result = {"ok": False, "error": f"{type(e).__name__}: {e} @ {where}"}
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
