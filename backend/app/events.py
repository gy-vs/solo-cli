"""进程内事件总线：SSE 订阅者各持一个队列。

topic 约定：
- "tasks"          任务状态变化（列表/总览刷新用）
- "runs"           所有题的运行事件摘要，不带 payload（列表页那几行实时动静用）
- f"run:{task_id}" 某题的实时 stream-json 事件，带完整 payload

"runs" 这一路是给列表页准备的。浏览器对同一个域的并发连接只有六个，而 SSE 是长连接
不还回去：列表上每张运行卡各连一条 f"run:{id}"，三道题在跑就把额度吃掉一半，再点开
详情和终端就没有连接留给普通请求了，界面看着就是「越点越卡」。所以列表页统一从这一路
拿动静，一条连接喂所有卡片。
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, AsyncIterator


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def publish(self, topic: str, data: dict[str, Any]) -> None:
        dead = []
        for q in self._subs.get(topic, ()):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subs[topic].discard(q)

    async def subscribe(self, *topics: str) -> AsyncIterator[dict[str, Any]]:
        """订阅一个或多个 topic，共用一个队列 —— 多路合到一条 SSE 上发。"""
        q: asyncio.Queue = asyncio.Queue(maxsize=2000)
        for t in topics:
            self._subs[t].add(q)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15)
                    yield item
                except asyncio.TimeoutError:
                    yield {"type": "ping"}
        finally:
            for t in topics:
                self._subs[t].discard(q)


bus = EventBus()


def sse_format(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
