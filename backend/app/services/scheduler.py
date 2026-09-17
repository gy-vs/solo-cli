"""并发调度：槽位、队列、启动时接管残留容器。"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.db import session
from app.events import bus
from app.models import INTERRUPTED, QUEUED, RUNNING, Task, as_utc, utc_now
from app.services import dockerx, qa_bridge, runner, settings_store

log = logging.getLogger("scheduler")


class Scheduler:
    def __init__(self) -> None:
        self.running: dict[int, asyncio.Task] = {}
        self._loop_task: asyncio.Task | None = None
        self._stopping = False
        self._readopted: set[int] = set()  # 因 runner 异常重新接管过的，不再重复接管

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
        waiting = self.waiting_on_repo()
        return {"running": len(self.running), "max_parallel": self.max_parallel,
                "running_ids": sorted(self.running), "queued": len(queued),
                "paused": self.paused, "repo_waiting": waiting}

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
                    await self._after_crash(tid, fut.exception())
                    bus.publish("tasks", {"type": "task", "id": tid})
        if self.paused:
            return
        free = self.max_parallel - len(self.running)
        if free <= 0:
            return
        for tid in self._pick(free):
            self._readopted.discard(tid)
            self.running[tid] = asyncio.create_task(runner.run_task(tid), name=f"run-{tid}")

    async def _after_crash(self, tid: int, exc: BaseException | None) -> None:
        """runner 协程自己炸了，这时候还不能判定这道题结束了。

        容器很可能还在跑。直接标 INTERRUPTED 会留下「状态说结束了、容器还在干活」
        的孤儿：槽位被放开，调度器接着起新题，实际并发就超了额度。所以先看容器，
        还活着就重新接管，只有确认容器没了才收尾。
        """
        with session() as db:
            t = db.get(Task, tid)
            if t is None or t.status != RUNNING:
                return
            name = t.container_name
        if tid not in self._readopted and await dockerx.container_state(name) == "running":
            log.warning("题 %s 的 runner 异常但容器 %s 还在跑，重新接管", tid, name)
            self._readopted.add(tid)
            self.running[tid] = asyncio.create_task(self._wait_and_finalize(tid, name))
            return
        with session() as db:
            t = db.get(Task, tid)
            if t and t.status == RUNNING:
                t.status = INTERRUPTED
                t.finished_at = utc_now()
                t.error = f"runner 异常: {exc}"

    def _pick(self, free: int) -> list[int]:
        """挑出这轮可以启动的题：一个项目同时只跑一道，被占住的留在队列里等。"""
        with session() as db:
            busy_repos = {
                qa_bridge.repo_id_of(t.env_snapshot)
                for t in db.execute(select(Task).where(Task.status == RUNNING)).scalars()
            }
            busy_repos.discard("")
            # priority 小的先跑，同优先级按领取时间；调队列顺序改的就是 priority
            queued = db.execute(
                select(Task).where(Task.status == QUEUED)
                .order_by(Task.priority, Task.claimed_at, Task.id)
            ).scalars().all()
            picked: list[int] = []
            for t in queued:
                rid = qa_bridge.repo_id_of(t.env_snapshot)
                if rid and rid in busy_repos:
                    continue
                if rid:
                    busy_repos.add(rid)
                picked.append(t.id)
                if len(picked) >= free:
                    break
            return picked

    def waiting_on_repo(self) -> list[dict]:
        """排在队列里但因为同项目有题在跑而起不来的，界面要能解释清楚。"""
        with session() as db:
            running = {}
            for t in db.execute(select(Task).where(Task.status == RUNNING)).scalars():
                rid = qa_bridge.repo_id_of(t.env_snapshot)
                if rid:
                    running.setdefault(rid, t.task_no)
            out = []
            for t in db.execute(select(Task).where(Task.status == QUEUED)
                                .order_by(Task.priority, Task.claimed_at, Task.id)).scalars():
                rid = qa_bridge.repo_id_of(t.env_snapshot)
                if rid in running:
                    out.append({"id": t.id, "task_no": t.task_no, "repo_id": rid,
                                "blocked_by": running[rid]})
            return out

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
        """等接管的容器结束。超时一样要管：这条路径漏了超时，题会一直跑下去。"""
        limit = max(1, settings_store.get_int("run.timeout_minutes", 120)) * 60
        with session() as db:
            t = db.get(Task, tid)
            started = as_utc(t.started_at) if t else None
        elapsed = (utc_now() - started).total_seconds() if started else 0.0
        remain = max(60.0, limit - elapsed)
        try:
            r = await asyncio.wait_for(dockerx.run(["docker", "wait", name], timeout=limit + 300), remain)
        except asyncio.TimeoutError:
            log.warning("接管的容器 %s 超过 %s 分钟，停止并按超时收尾", name, limit // 60)
            await dockerx.run(["docker", "stop", "-t", "10", name], timeout=120)
            await runner.finalize(tid, exit_code=None, result_event={}, timed_out=True)
            return
        try:
            code = int(r.out.strip())
        except ValueError:
            code = None
        await runner.finalize(tid, exit_code=code, result_event={})


scheduler = Scheduler()
