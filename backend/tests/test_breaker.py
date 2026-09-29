"""网络熔断：断网期间不按单题的账把整队刷进废弃，恢复后接着跑。"""

from __future__ import annotations

import asyncio

import pytest

from app import models as m
from app.services import breaker, dockerx, gsb_repo
from app.services import watchdog as wd

CERT = "API Error: Unable to connect to API (UNKNOWN_CERTIFICATE_VERIFICATION_ERROR)"


def _exited():
    async def go(*a, **k):
        return "exited"
    return go


def _net_broken(ids, side="A", attempt=1, finished_at=None):
    """摆成 9 月 28 日凌晨那样：连不上模型网关，重试十次后退出码 1。"""
    from app.db import session

    with session() as db:
        r = db.get(m.TaskRun, ids[side])
        r.status = m.RUN_FAILED
        r.attempt = attempt
        r.finished_at = finished_at or m.utc_now()
        r.verdict = {"process": {"exit_code": 1, "api_error": CERT,
                                 "retries": {"attempt": 10, "max_retries": 10}},
                     "protocol": {"subtype": "success", "is_error": True},
                     "artifact": {"trace_found": True, "changed_files": 0}}


@pytest.fixture()
def budget(monkeypatch):
    monkeypatch.setattr(wd.settings_store, "get_int",
                        lambda k, d=0: {"watchdog.max_retries": 2,
                                        "watchdog.max_timeouts": 2}.get(k, d))


# ---------------- 认得出断网 ----------------

@pytest.mark.parametrize("text", [
    CERT,
    "fatal: unable to access 'https://github.com/a/b/': gnutls_handshake() failed",
    "fatal: unable to access 'https://github.com/a/b/': Could not resolve host: github.com",
    "fatal: unable to access 'https://github.com/a/b/': SSL certificate problem",
    "fatal: unable to access 'https://github.com/a/b/': Failed to connect to github.com port 443",
])
def test_connection_level_failures_count_as_network(text):
    assert breaker.network_failure(text)


@pytest.mark.parametrize("text", [
    "remote: Repository not found.\nfatal: repository 'https://github.com/a/b/' not found",
    "fatal: Authentication failed for 'https://github.com/a/b/'",
    "fatal: unable to access 'https://github.com/a/b/': The requested URL returned error: 403",
    "API Error: 529 overloaded",
    "",
])
def test_rejections_and_gateway_codes_are_not_network(text):
    """连上了被拒，网络恢复也好不了；5xx 走 CC 自己的重试那条线。"""
    assert not breaker.network_failure(text)


def test_clone_failure_no_longer_blames_the_token_for_a_dropped_connection():
    res = dockerx.CmdResult(128, "", "fatal: unable to access 'x': gnutls_handshake() failed")
    assert "Token" not in gsb_repo.clone_failure(res)
    assert gsb_repo.network_error(res)


# ---------------- 巡检 ----------------

def test_network_failure_trips_instead_of_discarding(task_with_runs, budget, monkeypatch):
    """次数已经到顶也不废弃：这一跑是断网跑挂的，不是题的问题。"""
    from app.db import session

    task_id, ids = task_with_runs
    _net_broken(ids, attempt=2)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())

    async def boom(*a, **kw):
        raise AssertionError("熔断中不该动手")

    monkeypatch.setattr(wd, "requeue_run", boom)
    monkeypatch.setattr(wd, "give_up", boom)

    stats = asyncio.run(wd._scan_abnormal())
    assert breaker.tripped()
    assert stats["held"] == 1 and stats["discarded"] == 0
    with session() as db:
        assert db.get(m.Task, task_id).status != m.DISCARDED
        assert db.get(m.TaskRun, ids["A"]).attempt == 2


def test_tripped_breaker_stops_the_scheduler(tmp_db):
    from app.services.scheduler import scheduler

    breaker.trip("测试")
    assert scheduler.paused


def test_after_recovery_the_held_side_reruns_without_spending_an_attempt(
        task_with_runs, budget, monkeypatch):
    """断网期间挂的侧，放开后不计次数重跑，也不会再拿它把闸拉回去。"""
    from app.db import session

    _task_id, ids = task_with_runs
    _net_broken(ids, attempt=2)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())
    calls = []

    async def requeue(run_id, *, reason, reset_attempt=False, count=True):
        calls.append(count)
        return {"ok": True}

    monkeypatch.setattr(wd, "requeue_run", requeue)
    asyncio.run(wd._scan_abnormal())
    assert breaker.tripped()

    breaker.reset()
    asyncio.run(wd._scan_abnormal())
    assert not breaker.tripped()
    assert calls == [False]
    with session() as db:
        assert db.get(m.TaskRun, ids["A"]).abnormal["net_retries"] == 1


def test_a_side_that_keeps_losing_the_network_falls_back_to_the_normal_budget(
        task_with_runs, budget, monkeypatch):
    from app.db import session

    task_id, ids = task_with_runs
    _net_broken(ids, attempt=2)
    with session() as db:
        db.get(m.TaskRun, ids["A"]).abnormal = {"net_retries": wd.NET_RETRIES_MAX}
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())
    monkeypatch.setattr(wd.dockerx, "remove_task_containers",
                        lambda *_a: asyncio.sleep(0, dockerx.CmdResult(0, "", "")))

    asyncio.run(wd._scan_abnormal())
    assert not breaker.tripped()
    with session() as db:
        assert db.get(m.Task, task_id).status == m.DISCARDED


def test_clone_lost_to_the_network_trips_and_does_not_count_toward_discard(
        task_with_runs, budget, monkeypatch):
    """凌晨那一波的第二步：重跑准备 clone 不下来，连败两次就废弃了。"""
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        r = db.get(m.TaskRun, ids["A"])
        r.status = m.RUN_FAILED
        r.verdict = {"process": {"exit_code": 1}, "protocol": {}, "artifact": {}}
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())

    async def failing(run_id, *, reason, reset_attempt=False):
        return {"ok": False, "network": True, "message": "A 侧重新 clone 主干失败：TLS 被掐断"}

    monkeypatch.setattr(wd, "requeue_run", failing)
    for _ in range(3):
        asyncio.run(wd._scan_abnormal())
        breaker.reset()

    with session() as db:
        assert db.get(m.Task, task_id).status != m.DISCARDED
        run = db.get(m.TaskRun, ids["A"])
        assert not run.abnormal.get("prep_failures")
        assert run.abnormal["net_prep_failures"] == 3


def test_probe_needs_both_gateway_and_github(monkeypatch):
    import httpx

    async def api_url():
        return "https://llm.example.com"

    monkeypatch.setattr(breaker, "_api_url", api_url)

    def handler(request):
        if request.url.host == "llm.example.com":
            raise httpx.ConnectError("certificate verify failed")
        return httpx.Response(200)

    real = httpx.AsyncClient
    monkeypatch.setattr(breaker.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    ok, msg = asyncio.run(breaker.probe())
    assert not ok and "模型网关" in msg


# ---------------- 恢复 ----------------

def test_revive_reruns_only_the_broken_side(task_with_runs, monkeypatch):
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        t = db.get(m.Task, task_id)
        t.status, t.discarded_from = m.DISCARDED, m.RUNNING
        a = db.get(m.TaskRun, ids["A"])
        a.status = m.RUN_FAILED
        a.abnormal = {"reason": "x", "gave_up": True}
        b = db.get(m.TaskRun, ids["B"])
        b.status = m.RUN_FINISHED
        b.git_diff_stat = "a | 1 +"
        b.verdict = {"process": {"exit_code": 0}, "protocol": {"subtype": "success"},
                     "artifact": {"trace_found": True, "changed_files": 1}}
    seen = []

    async def rerun(tid, sides):
        seen.append(sides)
        with session() as db:
            db.get(m.Task, tid).status = m.QUEUED
        return {"ok": True, "message": "ok"}

    monkeypatch.setattr(wd, "manual_rerun", rerun)
    res = asyncio.run(wd.revive_discarded(task_id))
    assert res["ok"] and seen == [("A",)]
    with session() as db:
        t = db.get(m.Task, task_id)
        assert t.status == m.QUEUED and t.discarded_from == "" and t.discarded_at is None
        assert db.get(m.TaskRun, ids["A"]).abnormal == {}
