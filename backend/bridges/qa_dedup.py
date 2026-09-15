"""查重桥接：只跑 solo-qa 的查重规则 A 与规则 C。

这个文件不在 solo-cli 的进程里运行，而是挂进 `solo-qa-backend` 镜像执行
（那套依赖 pin 了 sqlalchemy/pydantic 的具体版本，跟 solo-cli 的直接混装会冲突）。
因此只用标准库 + solo-qa 自己的包，不要 import solo-cli 的任何模块。

只读口径（对应 solo-qa 的 docs/DedupPlan.md）：
- 只调 `dedup.service.run_dedup` 与 `dedup.semantic.review`，这两条路径只发 SELECT；
- 不调 `runner.run_batch` / `apply_result` / `pool_membership.sync_after_qc`
  / `lark.sync_service`，所以不写结论、不入查重池、不碰飞书；
- 关掉模型缓存，避免规则 C 的模型调用写 `qc_llm_cache`；
- 待查题目用 `MAX(id)` 之上的虚拟 row_id，只存在于内存，不落库。

唯一不可避免的写操作是查重池客户端初始化时的 `CREATE TABLE IF NOT EXISTS`
（`dedup/pool.py:ensure_schema`），表已存在时它不改结构。

协议：stdin 一个 JSON 对象，stdout 一个 JSON 对象，日志全部走 stderr。
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone

VERDICT_PASS = "pass"
VERDICT_DISCARD = "discard"
VERDICT_UNKNOWN = "unknown"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


async def run(payload: dict) -> dict:
    from sqlalchemy import func, select

    from backend import config_center
    from backend.db import dispose_engine, get_session_factory
    from backend.dedup import semantic
    from backend.dedup.service import DedupTarget, DedupUnavailable, run_dedup
    from backend.models import Submission
    from backend.states import FIELD_USER_PROMPT, SUBMITTED

    items = payload.get("items") or []
    rules = [r.upper() for r in (payload.get("rules") or ["A", "C"])]
    if not items:
        return {"ok": False, "error": "items 为空"}

    factory = get_session_factory()
    async with factory() as db:
        await config_center.refresh(db)
        # 规则 C 的模型判定默认读写 qc_llm_cache 表，这里只读所以关掉
        config_center.set_local_override("qc.llm_cache_enabled", False)
        max_id = (await db.execute(select(func.max(Submission.id)))).scalar() or 0

    # 虚拟 ID 取真实最大值之上，让在途查重把这些题当成「后提交的」
    base = int(max_id) + 1000
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for idx, it in enumerate(items):
        it["_row_id"] = base + idx

    results: dict[int, dict] = {
        it["_row_id"]: {"key": it.get("key") or str(it["_row_id"]), "rules": {}} for it in items
    }
    meta: dict = {"max_submission_id": int(max_id), "rules": rules}

    # ---------- 规则 A：字面/近字面查重，批内互查 + 历史池 ----------
    if "A" in rules:
        targets = [
            DedupTarget(
                row_id=it["_row_id"],
                repo_id=(it.get("repo_id") or "").strip(),
                seq=f"new:{it.get('key') or it['_row_id']}",
                submit_date=today,
                submitter=str(payload.get("submitter") or "solo-cli"),
                texts={FIELD_USER_PROMPT: it.get("user_prompt") or ""},
            )
            for it in items
        ]
        try:
            outcomes = await run_dedup(targets)
        except DedupUnavailable as e:
            # fail closed：查重没跑成不能当通过
            return {"ok": False, "error": f"规则 A 未完成（查重池不可用）：{e}"}
        for rid, oc in outcomes.items():
            hits = [json.loads(h.evidence_json()) for h in oc.hits if h.rule == "A"]
            results[rid]["rules"]["A"] = {
                "passed": not oc.hit_rule_a,
                "summary": oc.summary() or "查重 A 通过",
                "hits": hits,
                "top_similarity": max((h.similarity for h in oc.hits if h.rule == "A"), default=0.0),
            }

    # ---------- 规则 C：同仓库语义雷同，历史库 + 同批其他题 ----------
    if "C" in rules:
        original_load_peers = semantic.load_peers

        async def load_peers_with_batch(db, submission):
            """在库内候选之外，追加同批的其他题目。

            同一批设计出来的题目彼此也不能功能雷同，但它们都还没入库，
            `load_peers` 的 SQL 查不到，所以在这里补进去。
            批内题用负数 submission_id 标识，便于结论里区分。
            """
            peers = list(await original_load_peers(db, submission))
            repo = (submission.repo_id or "").strip()
            for pos, other in enumerate(items):
                if other["_row_id"] == submission.id:
                    continue
                if (other.get("repo_id") or "").strip() != repo:
                    continue
                text = (other.get("user_prompt") or "").strip()
                if not text:
                    continue
                peers.append(
                    semantic.Peer(
                        submission_id=-(pos + 1),
                        session_id=str(other.get("session_id") or ""),
                        round_no=1,
                        submitter_name=f"同批题 {other.get('key') or pos + 1}",
                        submitted_at=None,
                        user_prompt=text,
                        status=SUBMITTED,
                    )
                )
            return peers

        semantic.load_peers = load_peers_with_batch
        try:
            async with factory() as db:
                for it in items:
                    sub = Submission()
                    sub.id = it["_row_id"]
                    sub.repo_id = (it.get("repo_id") or "").strip()
                    sub.user_prompt = it.get("user_prompt") or ""
                    sub.session_id = str(it.get("session_id") or "")
                    sub.status = SUBMITTED
                    sub.round_no = 1
                    sub.submitter_name = str(payload.get("submitter") or "solo-cli")
                    sub.deleted_at = None
                    oc = await semantic.review(db, sub)
                    results[it["_row_id"]]["rules"]["C"] = {
                        "passed": oc.passed and not oc.skipped,
                        "skipped": oc.skipped,
                        "error": oc.error,
                        "summary": oc.summary(),
                        "detail": oc.detail(),
                        "peers_total": oc.peers_total,
                        "sent": oc.sent,
                        "task_type": oc.target_task_type,
                        "judged": oc.judged,
                    }
                    meta.setdefault("model", oc.model)
        finally:
            semantic.load_peers = original_load_peers

    # ---------- 汇总裁决：A 或 C 命中即废弃，未跑完即 unknown ----------
    out = []
    for it in items:
        r = results[it["_row_id"]]
        a, c = r["rules"].get("A"), r["rules"].get("C")
        reasons = []
        verdict = VERDICT_PASS
        if a and not a["passed"]:
            verdict = VERDICT_DISCARD
            reasons.append(a["summary"])
        if c and c.get("skipped"):
            if verdict == VERDICT_PASS:
                verdict = VERDICT_UNKNOWN
            reasons.append(c["summary"])
        elif c and not c["passed"]:
            verdict = VERDICT_DISCARD
            reasons.append(c["summary"])
        r["verdict"] = verdict
        r["passed"] = verdict == VERDICT_PASS
        r["reason"] = "；".join(reasons) or "规则 A、C 均通过"
        r["row_id"] = it["_row_id"]
        out.append(r)

    await dispose_engine()
    return {"ok": True, "meta": meta, "results": out}


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
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
