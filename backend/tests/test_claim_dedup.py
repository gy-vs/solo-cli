"""领取前查重：撞了谁才算数、没跑成时怎么放、人略过之后记多久。

桥接（起 solo2 容器连远端库）全部打桩，这里只测拿到规则 A 的结果之后怎么用。
"""

from __future__ import annotations

import asyncio

import pytest

from app import models as m
from app.db import session
from app.routers import tasks as tasks_router
from app.schemas import ClaimBatch
from app.services import claim_dedup


def _add(no, status=m.AVAILABLE, prompt=None):
    with session() as db:
        t = m.Task(task_no=no, prompt_hash=f"h{no}", user_prompt=prompt or f"题面 {no}", status=status,
                   repo_url="https://github.com/acme/widget",
                   env_snapshot="https://github.com/acme/widget/commit/" + "c" * 40)
        db.add(t)
        db.flush()
        return t.id


def _hit(seq, sim=0.4, sid=19000):
    return {"sub_rule_label": "A-4 同义改写（等长换皮）", "similarity": sim, "peer_ref": f"#{sid}",
            "matched": {"seq": seq, "submission_id": sid}}


@pytest.fixture()
def bridge(tmp_db, monkeypatch):
    """把 solo2 这头换成桩：hits 按题 id 给规则 A 的命中，calls 记下每次送了什么。"""
    state = {"hits": {}, "calls": [], "up": True, "fail": ""}

    async def probe():
        return (True, "") if state["up"] else (False, "solo2 没有启动（容器 solo2-backend-1 exited）")

    async def dedup(items, *, rules, timeout_s):
        state["calls"].append([it["key"] for it in items])
        if state["fail"]:
            return {"ok": False, "error": state["fail"]}
        return {"ok": True, "results": [
            {"key": it["key"], "rules": {"A": {"hits": state["hits"].get(int(it["key"]), [])}}}
            for it in items]}

    monkeypatch.setattr(claim_dedup, "enabled", lambda: True)
    monkeypatch.setattr(claim_dedup, "probe", probe)
    monkeypatch.setattr(claim_dedup.qa_bridge, "dedup", dedup)
    return state


def _stub_gate(monkeypatch):
    from app.services.gate import Check

    async def prepare(task):
        return {"ok": True, "sides": {}, "message": ""}

    async def run_checks(task):
        return [Check("workspace_A", "ok", "就绪")]

    monkeypatch.setattr(tasks_router.gate, "prepare_workspaces", prepare)
    monkeypatch.setattr(tasks_router.gate, "run_checks", run_checks)


# ---------------- 撞了谁才算数 ----------------

def test_history_hit_blocks(bridge):
    tid = _add("10")
    bridge["hits"] = {tid: [_hit("s:1", sid=18001)]}
    r = asyncio.run(claim_dedup.check([tid]))["results"][tid]
    assert r["state"] == claim_dedup.HIT and "平台已提交数据 #18001" in r["reason"]


def test_a_task_already_in_flight_counts_as_the_earlier_one(bridge):
    """刚才那批重复题全撞在排队中的题上：它们还没交到平台，历史库里查不到。"""
    queued = _add("09", status=m.QUEUED)
    tid = _add("10")
    bridge["hits"] = {tid: [_hit(f"new:{queued}")]}
    r = asyncio.run(claim_dedup.check([tid]))["results"][tid]
    assert r["state"] == claim_dedup.HIT and "本机第 09 题" in r["reason"]
    assert str(queued) in bridge["calls"][0]


def test_same_batch_pair_only_blocks_the_later_one(bridge):
    """同批互查两边都会被报。两道都拦下来，一对重复题就一道也不剩了。"""
    a, b = _add("10"), _add("11")
    bridge["hits"] = {a: [_hit(f"new:{b}")], b: [_hit(f"new:{a}")]}
    res = asyncio.run(claim_dedup.check([b, a]))["results"]
    assert res[a]["state"] == claim_dedup.PASS
    assert res[b]["state"] == claim_dedup.HIT and "本机第 10 题" in res[b]["reason"]


def test_discarded_and_uploaded_tasks_are_not_local_peers(bridge):
    """已上传的在平台历史里；已废弃的不该再拦别人。"""
    _add("08", status=m.DISCARDED)
    _add("07", status=m.UPLOADED)
    tid = _add("10")
    asyncio.run(claim_dedup.check([tid]))
    assert bridge["calls"][0] == [str(tid)]


# ---------------- 缓存与略过 ----------------

def test_pass_is_reused_until_the_prompt_changes(bridge):
    tid = _add("10")
    asyncio.run(claim_dedup.check([tid]))
    asyncio.run(claim_dedup.check([tid]))
    assert len(bridge["calls"]) == 1
    with session() as db:
        db.get(m.Task, tid).prompt_hash = "changed"
    asyncio.run(claim_dedup.check([tid]))
    assert len(bridge["calls"]) == 2


def test_hit_is_not_cached_so_the_next_claim_asks_again(bridge):
    tid = _add("10")
    bridge["hits"] = {tid: [_hit("s:1")]}
    asyncio.run(claim_dedup.check([tid]))
    asyncio.run(claim_dedup.check([tid]))
    assert len(bridge["calls"]) == 2


# ---------------- 领取路由 ----------------

def test_claim_stops_before_taking_the_task_when_it_hits(bridge, monkeypatch):
    _stub_gate(monkeypatch)
    tid = _add("10")
    bridge["hits"] = {tid: [_hit("s:1")]}
    r = asyncio.run(tasks_router._claim(tid, force=False))
    assert r["queued"] is False and r["dedup"]["state"] == claim_dedup.HIT
    with session() as db:
        assert db.get(m.Task, tid).status == m.AVAILABLE      # 没占、没 clone


def test_skip_after_a_hit_claims_and_remembers_the_decision(bridge, monkeypatch):
    _stub_gate(monkeypatch)
    tid = _add("10")
    bridge["hits"] = {tid: [_hit("s:1")]}
    r = asyncio.run(tasks_router._claim(tid, force=False, skip_dedup=True, skip_reason="人工看过不是重复"))
    assert r["queued"] is True
    with session() as db:
        t = db.get(m.Task, tid)
        assert t.dedup["state"] == claim_dedup.SKIPPED and t.dedup["reason"] == "人工看过不是重复"
    assert bridge["calls"] == []


def test_solo2_down_asks_first_and_then_does_not_block(bridge, monkeypatch):
    """solo2 没起：先告诉人，不替人拒；人确认后照常领。"""
    _stub_gate(monkeypatch)
    tid = _add("10")
    bridge["up"] = False
    r = asyncio.run(tasks_router._claim(tid, force=False))
    assert r["queued"] is False and r["dedup"]["state"] == "unavailable"
    assert "solo2 没有启动" in r["dedup"]["reason"]
    with session() as db:
        assert db.get(m.Task, tid).status == m.AVAILABLE
    assert asyncio.run(tasks_router._claim(tid, force=False, skip_dedup=True))["queued"] is True


def test_bridge_error_is_treated_like_solo2_down(bridge, monkeypatch):
    _stub_gate(monkeypatch)
    tid = _add("10")
    bridge["fail"] = "规则 A 未完成（查重池不可用）"
    r = asyncio.run(tasks_router._claim(tid, force=False))
    assert r["dedup"]["state"] == "unavailable" and "查重池不可用" in r["dedup"]["reason"]


def test_force_from_the_gate_does_not_dedup_again(bridge, monkeypatch):
    _stub_gate(monkeypatch)
    tid = _add("10")
    asyncio.run(tasks_router._claim(tid, force=True))
    assert bridge["calls"] == []


def test_batch_checks_once_and_leaves_hits_untouched(bridge, monkeypatch):
    _stub_gate(monkeypatch)
    a, b = _add("10"), _add("11")
    bridge["hits"] = {b: [_hit(f"new:{a}")]}
    r = asyncio.run(tasks_router.batch_claim(ClaimBatch(ids=[a, b])))
    by = {x["id"]: x for x in r["results"]}
    assert by[a]["queued"] is True
    assert by[b]["code"] == "DEDUP_HIT" and "本机第 10 题" in by[b]["error"]
    assert len(bridge["calls"]) == 1
    with session() as db:
        assert db.get(m.Task, b).status == m.AVAILABLE


def test_batch_with_solo2_down_touches_nothing_until_confirmed(bridge, monkeypatch):
    _stub_gate(monkeypatch)
    a = _add("10")
    bridge["up"] = False
    r = asyncio.run(tasks_router.batch_claim(ClaimBatch(ids=[a])))
    assert r["results"] == [] and "solo2 没有启动" in r["dedup_unavailable"]
    with session() as db:
        assert db.get(m.Task, a).status == m.AVAILABLE
    r = asyncio.run(tasks_router.batch_claim(ClaimBatch(ids=[a], skip_dedup=True, skip_reason="solo2 没起")))
    assert r["results"][0]["queued"] is True


def test_gate_shows_the_dedup_conclusion_without_running_it(bridge):
    from app.services import gate

    tid = _add("10")
    with session() as db:
        assert gate._dedup_check(db.get(m.Task, tid)).level == "warn"
    asyncio.run(claim_dedup.check([tid]))
    with session() as db:
        c = gate._dedup_check(db.get(m.Task, tid))
    assert c.level == "ok" and len(bridge["calls"]) == 1
