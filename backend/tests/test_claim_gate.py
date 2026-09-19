"""领取：强制启动能放行什么、不能放行什么，以及跨设备抢占的收尾。

门禁本身在 test_gate_gsb 里测，归属仲裁在 test_pool_claims 里测，这里只测路由怎么用
它们的结论。
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app import models as m
from app.db import session
from app.routers import tasks as tasks_router


@pytest.fixture()
def one_task(tmp_db):
    with session() as db:
        t = m.Task(task_no="42", prompt_hash="h", user_prompt="做点事",
                   repo_url="https://github.com/acme/widget",
                   env_snapshot="https://github.com/acme/widget/commit/" + "c" * 40)
        db.add(t)
        db.flush()
        return t.id


def _stub_gate(monkeypatch, *, prepared: bool, checks: list):
    async def prepare(task):
        return {"ok": prepared, "sides": {}, "message": "A: 结果；B: 结果"}

    async def run_checks(task):
        return checks

    monkeypatch.setattr(tasks_router.gate, "prepare_workspaces", prepare)
    monkeypatch.setattr(tasks_router.gate, "run_checks", run_checks)


def test_force_cannot_skip_a_side_that_never_cloned(one_task, monkeypatch):
    """这是 09 那次事故：clone 失败了还被入队，A 侧容器挂着空目录跑了起来。"""
    from app.services.gate import Check

    _stub_gate(monkeypatch, prepared=False, checks=[
        Check("workspace_A", "block", "A 侧还没 clone 到 …", fix="clone_sides", hard=True),
        Check("workspace_B", "ok", "B 侧停在初始快照且干净"),
    ])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(tasks_router._claim(one_task, force=True))
    assert exc.value.status_code == 409
    assert "A 侧还没 clone" in exc.value.detail

    with session() as db:
        t = db.get(m.Task, one_task)
        assert t.status == m.CLAIMED          # 停在已领取，没进队列
        assert db.query(m.TaskRun).count() == 0


def test_force_still_passes_spec_blocks(one_task, monkeypatch):
    """难度、任务类型这类是交不上去而不是跑不起来，强制启动照旧放行。"""
    from app.services.gate import Check

    _stub_gate(monkeypatch, prepared=True, checks=[
        Check("difficulty", "block", "难度「中等」不收"),
        Check("workspace_A", "ok", "A 侧停在初始快照且干净"),
        Check("workspace_B", "ok", "B 侧停在初始快照且干净"),
    ])

    r = asyncio.run(tasks_router._claim(one_task, force=True))
    assert r["queued"] is True
    with session() as db:
        t = db.get(m.Task, one_task)
        assert t.status == m.QUEUED
        assert {r.side for r in db.query(m.TaskRun).all()} == {"A", "B"}


def test_clone_failure_stops_before_the_gate(one_task, monkeypatch):
    from app.services.gate import Check

    _stub_gate(monkeypatch, prepared=False, checks=[Check("workspace_A", "ok", "就绪")])

    r = asyncio.run(tasks_router._claim(one_task, force=False))
    assert r["queued"] is False
    assert r["gate"] is None
    with session() as db:
        assert db.get(m.Task, one_task).branch_check["ok"] is False


def test_batch_claim_never_forces(one_task, monkeypatch):
    """「全部领取并启动」以前是直接调路由函数的，force 拿到的是 Query 对象——它是真值，
    于是整批题都被强制领取。09 就是这么在 clone 失败的情况下跑起来的。"""
    from app.schemas import IdList
    from app.services.gate import Check

    _stub_gate(monkeypatch, prepared=False, checks=[
        Check("workspace_A", "block", "A 侧还没 clone 到 …", fix="clone_sides", hard=True),
    ])

    r = asyncio.run(tasks_router.batch_claim(IdList(ids=[one_task])))
    assert r["results"][0]["queued"] is False
    with session() as db:
        assert db.get(m.Task, one_task).status == m.CLAIMED
        assert db.query(m.TaskRun).count() == 0


# ---------------- 跨设备抢占 ----------------

@pytest.fixture()
def pooled_task(one_task):
    """给这道题挂上远端条目 id，让它走跨设备独占那条路。"""
    with session() as db:
        db.get(m.Task, one_task).pool_entry_id = "air:01:abc123"
    return one_task


def _stub_pool(monkeypatch, result: dict, *, synced: list | None = None):
    async def claim_remote(entry_id, *, task_no=""):
        return result

    def sync_tasks():
        (synced if synced is not None else []).append(True)
        return {"added": [], "removed": [], "adopted": [], "skipped": [], "total": 0, "claimed": 0}

    monkeypatch.setattr(tasks_router.pool, "claim_remote", claim_remote)
    monkeypatch.setattr(tasks_router.pool_bank, "sync_tasks", sync_tasks)


def test_a_question_another_device_holds_is_refused_before_any_cloning(pooled_task, monkeypatch):
    """被抢先时要在 clone 之前就停下。

    准备工作区要几十秒到几分钟，跑完再发现题没了，这段机器时间就白烧了，磁盘上还留着
    一份没人要的工作区。所以 gate 这里被换成会炸的桩：真调到它就说明顺序错了。
    """
    async def boom(task):
        raise AssertionError("被别的设备领走的题不该走到准备工作区")

    monkeypatch.setattr(tasks_router.gate, "prepare_workspaces", boom)
    _stub_pool(monkeypatch, {"ok": False, "taken_by": "air", "message": "这道题已被「air」领取"})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(tasks_router._claim(pooled_task, force=False))

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == tasks_router.POOL_TAKEN
    assert exc.value.detail["taken_by"] == "air"
    with session() as db:
        assert db.get(m.Task, pooled_task).status == m.AVAILABLE   # 没被改成已领取


def test_losing_the_race_refreshes_the_local_bank(pooled_task, monkeypatch):
    """抢输了要顺手按远端刷一遍本机题库。

    不刷的话那张卡片还留在页面上，人会反复点同一道已经没了的题，每点一次都要跟远端
    往返一轮。
    """
    synced: list = []
    _stub_pool(monkeypatch, {"ok": False, "taken_by": "air", "message": "已被领取"}, synced=synced)

    with pytest.raises(HTTPException):
        asyncio.run(tasks_router._claim(pooled_task, force=False))
    assert synced, "被抢先后没有重新投影本机题库"


def test_batch_claim_counts_a_vanished_task_as_taken(pooled_task, monkeypatch):
    """批量领取跑到一半时题目整行消失，只可能是它也被别的设备领走了。

    归到「门禁未过」里会让人去查本机环境，而本机什么毛病都没有。
    """
    from app.schemas import IdList

    async def claim_remote(entry_id, *, task_no=""):
        with session() as db:
            db.delete(db.get(m.Task, pooled_task))     # 模拟重投影把它撤掉
        return {"ok": False, "taken_by": "air", "message": "已被领取"}

    monkeypatch.setattr(tasks_router.pool, "claim_remote", claim_remote)
    monkeypatch.setattr(tasks_router.pool_bank, "sync_tasks", lambda: {
        "added": [], "removed": [], "adopted": [], "skipped": [], "total": 0, "claimed": 0})

    # 同一个 id 领两次：第一次把它删掉，第二次就只剩 404 这一个线索
    r = asyncio.run(tasks_router.batch_claim(IdList(ids=[pooled_task, pooled_task])))
    assert [x["code"] for x in r["results"]] == [tasks_router.POOL_TAKEN, tasks_router.POOL_TAKEN]


def test_an_unreachable_remote_is_not_reported_as_taken(pooled_task, monkeypatch):
    """连不上远端和被人领走是两回事。

    混成一个提示，人会以为题真的没了而去出新题，实际上只是网断了 —— 那道题还在等着。
    """
    _stub_pool(monkeypatch, {"ok": False, "message": "连不上远端题库"})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(tasks_router._claim(pooled_task, force=False))
    assert exc.value.detail["code"] == "POOL_UNREACHABLE"


def test_winning_the_race_records_who_holds_it(pooled_task, monkeypatch):
    from app.services.gate import Check

    _stub_gate(monkeypatch, prepared=True, checks=[Check("workspace_A", "ok", "就绪")])
    _stub_pool(monkeypatch, {"ok": True, "message": "已在远端登记领取"})
    monkeypatch.setattr(tasks_router.pool, "device", lambda: "mac")

    r = asyncio.run(tasks_router._claim(pooled_task, force=False))
    assert r["queued"] is True
    with session() as db:
        assert db.get(m.Task, pooled_task).claimed_by == "mac"


def test_a_purely_local_task_never_asks_the_remote(one_task, monkeypatch):
    """池没启用时导入的题没有远端条目 id，领取不该为它跑一趟网络。"""
    from app.services.gate import Check

    async def boom(entry_id, *, task_no=""):
        raise AssertionError("没有远端条目的题不该去远端占位")

    _stub_gate(monkeypatch, prepared=True, checks=[Check("workspace_A", "ok", "就绪")])
    monkeypatch.setattr(tasks_router.pool, "claim_remote", boom)

    assert asyncio.run(tasks_router._claim(one_task, force=False))["queued"] is True
