"""领取前查重：用 solo2 的规则 A 看这道题是不是和已有的题撞了。

比的是三拨题：平台上已提交的历史、本机已经领了在做的题、同一批里排在前面的题。
本机在做的题一定要带上：它们还没交到平台，历史库里查不到，而同一个模板套到不同仓库
上出的题，恰恰就是在这一段撞的——两道都跑完了才发现，四个容器的机器时间就白花了。

同批互查时两边都会被标成命中，这里只认「撞了排在前面的那道」：先领的留下，后领的
才算重复，不然一对重复题会一起被拦下，一道也不剩。

桥接是拿 solo2 的镜像和源码起一个一次性容器、直连远端库，不经过 solo2 的服务，所以
solo2 起没起不影响查重。查重没跑成（远端库连不上、桥接报错）不替人拿主意：告诉人
一声，人确认了就照常领，不拦。命中了也不自动废弃，人可以略过——规则 A 按字面比，模板相近但做的事不同的题
它也会报。
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.db import session
from app.models import (
    ANALYZED, ANALYZING, CLAIMED, NEEDS_ATTENTION, QC, QUEUED, READY, RUN_DONE, RUNNING,
    Task, as_utc, utc_now,
)
from app.services import qa_bridge, settings_store

log = logging.getLogger("claim_dedup")

STAGE = "claim"
FRESH_S = 1800          # 通过的结论管多久。平台历史一直在长，放太久就不作数了
IN_FLIGHT = (CLAIMED, QUEUED, RUNNING, RUN_DONE, ANALYZING, ANALYZED, QC, READY, NEEDS_ATTENTION)

PASS, HIT, SKIPPED = "pass", "hit", "skipped"
DATASET = "gsb"


def enabled() -> bool:
    return settings_store.get_bool("claim.dedup", True)


def _age(stamp: str) -> float:
    try:
        return (utc_now() - as_utc(datetime.fromisoformat(stamp))).total_seconds()
    except (TypeError, ValueError):
        return float("inf")


def cached(task: Task) -> dict | None:
    """这道题还作数的领取查重结论：人工略过的一直作数，通过的管 FRESH_S，题面改了都作废。"""
    d = task.dedup or {}
    if d.get("stage") != STAGE or d.get("prompt_hash") != task.prompt_hash:
        return None
    if d.get("state") == SKIPPED:
        return d
    # 没带 dataset 的是桥接改口径之前比的上一期旧池，那种「通过」不作数
    if d.get("state") == PASS and d.get("dataset") == DATASET and _age(d.get("checked_at") or "") < FRESH_S:
        return d
    return None


def _peer_label(h: dict, local: dict[str, Task]) -> tuple[str, int | None]:
    """命中对象的说法，以及它若是本机题时的 id。"""
    seq = str((h.get("matched") or {}).get("seq") or "")
    if seq.startswith("new:") and (t := local.get(seq[4:])) is not None:
        return f"本机第 {t.task_no} 题", t.id
    sid = (h.get("matched") or {}).get("submission_id")
    return (f"平台已提交数据 #{sid}" if sid else str(h.get("peer_ref") or "平台已提交数据")), None


async def check(task_ids: list[int]) -> dict:
    """给这批题跑领取查重，结论写回每道题。返回 {ok, error, results: {id: 结论}}。

    已有作数结论的题不再查。ok=False 表示查重没跑成，results 里只有缓存命中的那些。
    """
    with session() as db:
        rows = [t for tid in dict.fromkeys(task_ids) if (t := db.get(Task, tid)) is not None]
        results = {t.id: c for t in rows if (c := cached(t))}
        todo = sorted((t for t in rows if t.id not in results), key=lambda t: t.id)
        if not todo:
            return {"ok": True, "error": "", "results": results}
        want = {t.id for t in todo}
        peers = [t for t in db.query(Task).filter(Task.status.in_(IN_FLIGHT)).all() if t.id not in want]
        local = {str(t.id): t for t in [*peers, *todo]}
        order = {t.id: i for i, t in enumerate(todo)}
        items = [{"key": str(t.id), "user_prompt": t.user_prompt or "",
                  "repo_id": qa_bridge.repo_id_of(t.env_snapshot), "session_id": ""}
                 for t in [*peers, *todo] if (t.user_prompt or "").strip()]
        hashes = {t.id: t.prompt_hash for t in todo}
        nos = {t.id: t.task_no for t in todo}

    r = await qa_bridge.dedup(items, rules=("A",), timeout_s=300)
    if not r.get("ok"):
        return {"ok": False, "error": f"solo2 查重没跑成：{r.get('error') or '未知错误'}", "results": results}

    by_key = {it.get("key"): it for it in r.get("results") or []}
    now = utc_now().isoformat()
    for tid in order:
        a = ((by_key.get(str(tid)) or {}).get("rules") or {}).get("A") or {}
        hits = []
        for h in a.get("hits") or []:
            label, other = _peer_label(h, local)
            # 同批里排在它后面的题不算：那一对由后面那道来背
            if other is not None and other in order and order[other] >= order[tid]:
                continue
            hits.append({"peer": label, "similarity": round(float(h.get("similarity") or 0), 4),
                         "rule": h.get("sub_rule_label") or h.get("sub_rule") or "规则 A"})
        hits.sort(key=lambda x: -x["similarity"])
        state = HIT if hits else PASS
        reason = (f"规则 A 查重命中：与{hits[0]['peer']}重复（{hits[0]['rule']}，相似度 {hits[0]['similarity']:.1%}）"
                  + (f"，另有 {len(hits) - 1} 处" if len(hits) > 1 else "")) if hits else "规则 A 查重通过"
        results[tid] = {"stage": STAGE, "state": state, "verdict": "discard" if hits else "pass",
                        "passed": not hits, "reason": reason, "hits": hits[:5],
                        "prompt_hash": hashes[tid], "checked_at": now, "dataset": DATASET}
    with session() as db:
        for tid in order:
            if (t := db.get(Task, tid)) is not None:
                t.dedup = results[tid]
    hit = [nos[t] for t in order if results[t]["state"] == HIT]
    log.info("领取查重 %d 道，命中 %d 道%s", len(order), len(hit), f"：{'、'.join(hit)}" if hit else "")
    return {"ok": True, "error": "", "results": results}


def skip(task_id: int, note: str) -> dict:
    """人工略过查重，按当前题面记下。题面改了这个决定就不作数。"""
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {}
        prev = (t.dedup or {}) if (t.dedup or {}).get("stage") == STAGE else {}
        t.dedup = {**prev, "stage": STAGE, "state": SKIPPED, "verdict": "pass", "passed": True,
                   "reason": note, "prompt_hash": t.prompt_hash, "skipped_at": utc_now().isoformat(),
                   "checked_at": prev.get("checked_at") or ""}
        return t.dedup
