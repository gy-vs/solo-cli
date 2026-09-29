"""查重桥接：按 solo2 的 GSB 口径只跑查重规则 A 与规则 C。

这个文件不在 solo-cli 的进程里运行，而是挂进 solo-qa 的后端镜像执行
（那套依赖 pin 了 sqlalchemy/pydantic 的具体版本，跟 solo-cli 的直接混装会冲突）。
因此只用标准库 + solo-qa 自己的包，不要 import solo-cli 的任何模块。

必须走 GSB 这一期的口径（`backend.gsb.qc.dedup` / `backend.gsb.qc.semantic`），
不能直接调服务层：GSB 的字段在池里叫 `gsb_user_prompt`、落在自己的 `gsb_prompt_pool`，
在途与同仓库候选从 `gsb_submission` 取。以前这里传的是不带前缀的 `user_prompt`、
候选取的是上一期的 `submission` 表，比的是上一期的旧数据，本期的题一条都比不到 ——
478 就是这样查出「通过、相似度 0」，交上去被平台按规则 A 废掉。

只读口径（对应 solo-qa 的 docs/DedupPlan.md）：
- 只调 `run_dedup`、`gsb_dedup._inflight_targets`、`gsb_semantic.load_peers` 与
  `review_peers`，这几条路径只发 SELECT；
- 不调 `push` / `save_hits` / GSB 的 `runner`，所以不写结论、不入查重池、不碰飞书；
- 关掉模型缓存，避免规则 C 的模型调用写缓存表；
- 待查题目用 `MAX(gsb_submission.id)` 之上的虚拟 row_id，只存在于内存，不落库。
  取在最大值之上是为了让在途比对把它们当成「后提交的」—— 平台只判后来者。

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
    from backend.dedup import semantic as legacy_semantic
    from backend.dedup.service import DedupUnavailable, run_dedup
    from backend.gsb.models import GsbSubmission
    from backend.gsb.qc import dedup as gsb_dedup
    from backend.gsb.qc import semantic as gsb_semantic
    from backend.states import RULE_A as SERVICE_RULE_A
    from backend.states import SUBMITTED

    items = payload.get("items") or []
    rules = [r.upper() for r in (payload.get("rules") or ["A", "C"])]
    if not items:
        return {"ok": False, "error": "items 为空"}

    factory = get_session_factory()
    async with factory() as db:
        await config_center.refresh(db)
        # 规则 C 的模型判定默认读写缓存表，这里只读所以关掉
        config_center.set_local_override("qc.llm_cache_enabled", False)
        max_id = (await db.execute(select(func.max(GsbSubmission.id)))).scalar() or 0

    base = int(max_id) + 1000
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    submitter = str(payload.get("submitter") or "solo-cli")
    for idx, it in enumerate(items):
        it["_row_id"] = base + idx

    results: dict[int, dict] = {
        it["_row_id"]: {"key": it.get("key") or str(it["_row_id"]), "rules": {}} for it in items
    }
    meta: dict = {"max_submission_id": int(max_id), "rules": rules, "dataset": "gsb"}

    # ---------- 规则 A：GSB 池 + GSB 在途 + 批内互查 ----------
    if "A" in rules:
        targets = []
        for it in items:
            t = gsb_dedup.to_target(None, {
                "user_prompt": it.get("user_prompt") or "",
                "repo_id": (it.get("repo_id") or "").strip(),
                "submitted_date": today,
                "submitter_name": submitter,
            }, row_id=it["_row_id"])
            # to_target 把 seq 设成 row_id，而虚拟 row_id 出了这个进程就没意义；
            # 换成调用方的 key，批内命中的证据才能指回是哪道题
            t.seq = f"new:{it.get('key') or it['_row_id']}"
            t.texts = {k: v for k, v in t.texts.items() if v.strip()}
            targets.append(t)
        try:
            async with factory() as db:
                inflight = await gsb_dedup._inflight_targets(db, exclude_ids=set())
            meta["inflight"] = len(inflight)
            outcomes = await run_dedup(targets, inflight=inflight)
        except DedupUnavailable as e:
            # fail closed：查重没跑成不能当通过
            return {"ok": False, "error": f"规则 A 未完成（查重池不可用）：{e}"}
        for rid, oc in outcomes.items():
            a_hits = [h for h in oc.hits if h.rule == SERVICE_RULE_A]
            results[rid]["rules"]["A"] = {
                "passed": not oc.hit_rule_a,
                "summary": gsb_dedup._summary_of(oc) if oc.hit_rule_a else "查重 A 通过",
                "hits": [json.loads(h.evidence_json()) for h in a_hits],
                "top_similarity": max((h.similarity for h in a_hits), default=0.0),
            }

    # ---------- 规则 C：同仓库语义雷同，GSB 已通过/在途 + 同批其他题 ----------
    if "C" in rules:
        async with factory() as db:
            for it in items:
                sub = GsbSubmission()
                sub.id = it["_row_id"]
                sub.repo_id = (it.get("repo_id") or "").strip()
                sub.user_prompt = it.get("user_prompt") or ""
                peers = list(await gsb_semantic.load_peers(db, sub))
                # 同一批设计出来的题彼此也不能雷同，但它们都还没入库，SQL 查不到，
                # 在这里补进去。批内题用负数 submission_id 标识，便于结论里区分
                for pos, other in enumerate(items):
                    if other["_row_id"] == sub.id or (other.get("repo_id") or "").strip() != sub.repo_id:
                        continue
                    text = (other.get("user_prompt") or "").strip()
                    if not text:
                        continue
                    peers.append(legacy_semantic.Peer(
                        submission_id=-(pos + 1), session_id="", round_no=0,
                        submitter_name=f"同批题 {other.get('key') or pos + 1}",
                        submitted_at=None, user_prompt=text, status=SUBMITTED,
                    ))
                oc = await legacy_semantic.review_peers(
                    peers=peers, submission_id=sub.id, user_prompt=sub.user_prompt,
                    repo_id=sub.repo_id, session_id="",
                )
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
