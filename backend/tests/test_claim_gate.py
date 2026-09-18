"""领取：强制启动能放行什么、不能放行什么。

门禁本身在 test_gate_gsb 里测，这里只测路由怎么用它的结论。
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
