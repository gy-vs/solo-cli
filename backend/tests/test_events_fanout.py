"""事件总线：一条连接收多路，以及运行事件那份给列表页的瘦摘要。

这两件事撑着的是界面的流畅：浏览器对同一个域只给六个并发连接，SSE 开着就不还。列表上
每张运行卡从前各连一条自己的流，几道题在跑就把额度吃光，之后所有普通请求都在排队。
现在改成公共流一条兼收两路 —— 所以「多 topic 共用一个队列」和「摘要不带 payload」都得
锁住，回退任何一个，卡顿都会原样回来。
"""

from __future__ import annotations

import asyncio

import pytest

from app.events import EventBus
from app.services import runner


def test_one_subscriber_receives_several_topics():
    bus = EventBus()

    async def go():
        got = []
        agen = bus.subscribe("tasks", "runs")
        task = asyncio.create_task(anext(agen))
        await asyncio.sleep(0)  # 让订阅先把队列挂上去

        bus.publish("tasks", {"type": "task", "id": 7})
        got.append(await task)
        bus.publish("runs", {"type": "run_event", "task_id": 7})
        got.append(await anext(agen))
        await agen.aclose()
        return got

    got = asyncio.run(go())
    assert [g["type"] for g in got] == ["task", "run_event"]


def test_unsubscribe_clears_every_topic():
    """漏一个 topic 就是漏一个队列：题目跑起来以后它会一直被喂，直到把内存吃满。"""
    bus = EventBus()

    async def go():
        agen = bus.subscribe("tasks", "runs")
        task = asyncio.create_task(anext(agen))
        await asyncio.sleep(0)
        bus.publish("runs", {"type": "run_event"})
        await task  # 收下一条，生成器就停在 yield 上，这时才关得掉
        await agen.aclose()
        return {t: len(qs) for t, qs in bus._subs.items()}

    assert asyncio.run(go()) == {"tasks": 0, "runs": 0}


def test_run_event_also_goes_out_as_a_lean_summary(tmp_db, monkeypatch):
    """详细流照旧带 payload，公共流那份必须不带 —— 单条 payload 能到 20 KB。"""
    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(runner.bus, "publish", lambda topic, data: seen.append((topic, data)))

    payload = {"type": "assistant", "message": {"content": [{"type": "text", "text": "x" * 500}]}}
    runner._record_event(7, "A", 3, "assistant", "读了一个文件", payload)

    by_topic = dict(seen)
    assert by_topic["run:7"]["payload"] == payload
    lean = by_topic["runs"]
    assert "payload" not in lean
    assert (lean["task_id"], lean["side"], lean["seq"], lean["kind"]) == (7, "A", 3, "assistant")
    assert lean["summary"] == "读了一个文件"


def test_lean_summary_stays_short(tmp_db, monkeypatch):
    """列表上只有一行的位置，摘要再长也没人看得见，但它要跟着每条事件走一遍全场订阅者。"""
    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(runner.bus, "publish", lambda topic, data: seen.append((topic, data)))

    runner._record_event(7, "B", 1, "user", "工具结果: " + "y" * 5000, {"type": "user"})

    lean = dict(seen)["runs"]
    assert len(lean["summary"]) == 300
