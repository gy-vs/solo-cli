"""进程内事件总线：SSE 订阅者各持一个队列。

topic 约定：
- "tasks"          任务状态变化（列表/总览刷新用）
- f"run:{task_id}" 某题的实时 stream-json 事件
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

    async def subscribe(self, topic: str) -> AsyncIterator[dict[str, Any]]:
        q: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self._subs[topic].add(q)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15)
                    yield item
                except asyncio.TimeoutError:
                    yield {"type": "ping"}
        finally:
            self._subs[topic].discard(q)


bus = EventBus()


def sse_format(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
