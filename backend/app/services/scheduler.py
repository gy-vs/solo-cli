"""并发调度：槽位、队列、启动时接管残留容器。"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.db import session
from app.events import bus
from app.models import INTERRUPTED, QUEUED, RUNNING, Task, utc_now
from app.services import dockerx, runner, settings_store

log = logging.getLogger("scheduler")


class Scheduler:
    def __init__(self) -> None:
        self.running: dict[int, asyncio.Task] = {}
        self._loop_task: asyncio.Task | None = None
        self._stopping = False

    @property
    def max_parallel(self) -> int:
        return max(1, settings_store.get_int("scheduler.max_parallel", 3))

    @property
    def paused(self) -> bool:
        return settings_store.get_bool("scheduler.paused", False)

    def snapshot(self) -> dict:
        with session() as db:
            queued = db.execute(
                select(Task.id).where(Task.status == QUEUED)
            ).scalars().all()
        return {"running": len(self.running), "max_parallel": self.max_parallel,
                "running_ids": sorted(self.running), "queued": len(queued),
                "paused": self.paused}

    async def start(self) -> None:
        await self._adopt()
        self._loop_task = asyncio.create_task(self._loop(), name="scheduler-loop")

    async def stop(self) -> None:
        self._stopping = True
        if self._loop_task:
            self._loop_task.cancel()

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                await self._tick()
            except Exception:  # noqa: BLE001
                log.exception("调度循环异常")
            await asyncio.sleep(2)

    async def _tick(self) -> None:
        for tid, fut in list(self.running.items()):
            if fut.done():
                self.running.pop(tid, None)
                if fut.exception():
                    log.error("run_task(%s) 异常: %s", tid, fut.exception())
                    with session() as db:
                        t = db.get(Task, tid)
                        if t and t.status == RUNNING:
                            t.status = INTERRUPTED
                            t.finished_at = utc_now()
                            t.error = f"runner 异常: {fut.exception()}"
                    bus.publish("tasks", {"type": "task", "id": tid})
        if self.paused:
            return
        free = self.max_parallel - len(self.running)
        if free <= 0:
            return
        with session() as db:
            # priority 小的先跑，同优先级按领取时间；调队列顺序改的就是 priority
            queued = db.execute(
                select(Task).where(Task.status == QUEUED)
                .order_by(Task.priority, Task.claimed_at, Task.id).limit(free)
            ).scalars().all()
            ids = [t.id for t in queued]
        for tid in ids:
            self.running[tid] = asyncio.create_task(runner.run_task(tid), name=f"run-{tid}")

    async def _adopt(self) -> None:
        """进程重启后：状态为 RUNNING 的任务，按容器实际状态收尾。"""
        with session() as db:
            stale = db.execute(select(Task).where(Task.status == RUNNING)).scalars().all()
            items = [(t.id, t.container_name) for t in stale]
        for tid, name in items:
            state = await dockerx.container_state(name)
            if state == "running":
                log.info("接管运行中的容器 %s", name)
                self.running[tid] = asyncio.create_task(self._wait_and_finalize(tid, name))
            else:
                code = await dockerx.container_exit_code(name) if state else None
                await runner.finalize(tid, exit_code=code, result_event={}, manual_stop=(state == ""))

    async def _wait_and_finalize(self, tid: int, name: str) -> None:
        r = await dockerx.run(["docker", "wait", name], timeout=48 * 3600)
        try:
            code = int(r.out.strip())
        except ValueError:
            code = None
        await runner.finalize(tid, exit_code=code, result_event={})


scheduler = Scheduler()
