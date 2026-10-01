"""巡检盯防熄屏：代理不在要喊、断言掉了要让代理重建、睡过一次要记一笔。

这几条错了都不会报错，只会在某个下午屏幕一黑、机器一睡，整批题冻住半小时。
"""

import asyncio
import logging

from app.services import host_agent
from app.services import watchdog as wd


def _ok(**extra):
    return {"ok": True, "reachable": True, "message": "防熄屏生效中", "restarts": 0,
            "held": ["PreventUserIdleDisplaySleep", "PreventUserIdleSystemSleep"],
            "last_sleep": {}, "risks": [], **extra}


def test_healthy_agent_is_reported_without_rebuilding(monkeypatch):
    calls = []

    async def awake():
        return _ok()

    async def ensure():
        calls.append(1)
        return _ok()

    monkeypatch.setattr(host_agent, "awake", awake)
    monkeypatch.setattr(host_agent, "ensure_awake", ensure)
    assert asyncio.run(wd._check_awake()) == "正常"
    assert calls == []
    assert wd._awake["ok"] is True


def test_lost_assertion_triggers_rebuild_and_records_recovery(monkeypatch):
    """代理活着但断言没了：巡检得让它当场重建，而不是只记一句。"""
    calls = []

    async def awake():
        return {**_ok(), "ok": False, "message": "系统账本里缺断言", "held": []}

    async def ensure():
        calls.append(1)
        return _ok(restarts=1)

    monkeypatch.setattr(host_agent, "awake", awake)
    monkeypatch.setattr(host_agent, "ensure_awake", ensure)
    assert asyncio.run(wd._check_awake()) == "正常"
    assert calls == [1]
    assert wd._awake["restarts"] == 1


def test_failed_rebuild_stays_abnormal(monkeypatch):
    async def awake():
        return {**_ok(), "ok": False, "message": "caffeinate 不在了"}

    async def ensure():
        return {**_ok(), "ok": False, "message": "重建后仍缺 PreventUserIdleDisplaySleep"}

    monkeypatch.setattr(host_agent, "awake", awake)
    monkeypatch.setattr(host_agent, "ensure_awake", ensure)
    assert asyncio.run(wd._check_awake()) == "异常"
    assert "重建后仍缺" in wd._awake["message"]


def test_missing_agent_is_flagged_not_raised():
    """代理没起是最常见的失守方式，巡检要照常跑完并把它标出来。"""
    assert asyncio.run(wd._check_awake()) == "代理未运行"
    assert wd._awake["reachable"] is False


def test_query_crash_falls_through_to_rebuild(monkeypatch):
    """查询本身炸了不能把整轮巡检带崩，按异常处理、照样去重建。"""
    async def boom():
        raise RuntimeError("socket hung")

    async def ensure():
        return _ok(restarts=1)

    monkeypatch.setattr(host_agent, "awake", boom)
    monkeypatch.setattr(host_agent, "ensure_awake", ensure)
    assert asyncio.run(wd._check_awake()) == "正常"


def test_a_sleep_is_shouted_once(monkeypatch, caplog):
    slept = {"detected_at": "2026-10-01T19:35:44", "gap_seconds": 1544,
             "reason": "2026-10-01 19:10:15 Software Sleep pid=232"}

    async def awake():
        return _ok(last_sleep=slept)

    monkeypatch.setattr(host_agent, "awake", awake)
    with caplog.at_level(logging.ERROR, logger="watchdog"):
        asyncio.run(wd._check_awake())
        asyncio.run(wd._check_awake())
    hits = [r for r in caplog.records if "宿主机刚睡过" in r.getMessage()]
    assert len(hits) == 1
    assert "Software Sleep" in hits[0].getMessage()
