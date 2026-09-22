"""质检容器的并发额度。

这一步和「分析/质检并发」占的不是同一种资源：那个数管同时发几个模型调用，模型在
别人的机器上；这一步每道题要起一个 solo-qa 容器，占的是本机内存。模型并发调到 30
之后，闸门前两步跑完会一起涌到这一步，不分开就是三十个容器同时起，而 Docker Desktop
只分到几个 G —— 撞上去是整批 OOM，而 OOM 掉的那几道会被记成「质检未完成」，
看上去像平台的问题。
"""

from __future__ import annotations

import asyncio

import pytest

from app.services import qa_bridge as qb


@pytest.fixture(autouse=True)
def _reset_gate(monkeypatch):
    """每个用例各起一个事件循环，信号量不能跨循环复用。"""
    monkeypatch.setattr(qb, "_slots", None)
    monkeypatch.setattr(qb, "_slots_limit", 0)


def _spy(limit: int, calls: int):
    """记录同时在跑的容器峰值。"""
    peak = {"now": 0, "max": 0}

    async def fake_run_now(script, payload, *, timeout_s, mounts=None):
        peak["now"] += 1
        peak["max"] = max(peak["max"], peak["now"])
        await asyncio.sleep(0)          # 让出一次，给别的协程机会挤进来
        peak["now"] -= 1
        return {"ok": True}

    async def go():
        await asyncio.gather(*(qb._run("x.py", {}, timeout_s=60) for _ in range(calls)))

    return fake_run_now, go, peak


def test_container_fanout_is_capped(monkeypatch):
    monkeypatch.setattr(qb.settings_store, "get_int", lambda k, d=0: 4)
    fake, go, peak = _spy(4, 30)
    monkeypatch.setattr(qb, "_run_now", fake)
    asyncio.run(go())
    assert peak["max"] <= 4


def test_the_cap_is_independent_of_the_model_concurrency(monkeypatch):
    """模型并发 30 不该把容器也带成 30，两个数各调各的。"""
    monkeypatch.setattr(qb.settings_store, "get_int",
                        lambda k, d=0: 30 if k == "auto.max_parallel" else 2)
    fake, go, peak = _spy(2, 20)
    monkeypatch.setattr(qb, "_run_now", fake)
    asyncio.run(go())
    assert peak["max"] <= 2


def test_raising_the_setting_takes_effect_without_a_restart(monkeypatch):
    """额度改了要换一把新的信号量，否则设置页改完得重启才生效。"""
    monkeypatch.setattr(qb.settings_store, "get_int", lambda k, d=0: 2)
    assert qb._gate()._value == 2
    monkeypatch.setattr(qb.settings_store, "get_int", lambda k, d=0: 8)
    assert qb._gate()._value == 8


def test_queueing_does_not_eat_into_the_timeout(monkeypatch):
    """超时是给「容器起来了却不返回」用的。排队等额度算进去，队尾那几道一进容器
    就被判超时 —— 而它们一秒都还没跑。"""
    monkeypatch.setattr(qb.settings_store, "get_int", lambda k, d=0: 1)
    seen: list[int] = []

    async def fake_run_now(script, payload, *, timeout_s, mounts=None):
        seen.append(timeout_s)
        await asyncio.sleep(0.01)
        return {"ok": True}

    monkeypatch.setattr(qb, "_run_now", fake_run_now)

    async def go():
        await asyncio.gather(*(qb._run("x.py", {}, timeout_s=900) for _ in range(3)))

    asyncio.run(go())
    # 三道都串着跑，但每一道拿到的超时都是完整的 900 秒
    assert seen == [900, 900, 900]
