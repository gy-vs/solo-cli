"""并发调度：槽位按容器算，A/B 成对出闸，启动时接管残留容器。

额度的单位是容器而不是题：一道题要占两个容器，按题算额度会让实际并发翻倍，
机器上一下起八个容器直接把内存吃满。
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.db import session
from app.events import bus
from app.models import (
    QUEUED, RUN_INTERRUPTED, RUN_QUEUED, RUN_RUNNING, RUNNING, Task, TaskRun, as_utc, utc_now,
)
from app.services import dockerx, runner, settings_store

log = logging.getLogger("scheduler")


class Scheduler:
    def __init__(self) -> None:
        self.running: dict[int, asyncio.Task] = {}   # run_id -> 协程
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
                select(TaskRun.id).join(Task, Task.id == TaskRun.task_id)
                .where(Task.status == QUEUED, TaskRun.status.in_((RUN_QUEUED, "PENDING")))
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
        for rid, fut in list(self.running.items()):
            if fut.done():
                self.running.pop(rid, None)
                if fut.exception():
                    log.error("run_side(%s) 异常: %s", rid, fut.exception())
                    await self._after_crash(rid, fut.exception())
        if self.paused:
            return
        free = self.max_parallel - len(self.running)
        if free <= 0:
            return
        picked = self.pick(free)
        if not picked:
            return
        self._mark_running(picked)
        for rid in picked:
            self._readopted.discard(rid)
            self.running[rid] = asyncio.create_task(runner.run_side(rid), name=f"run-{rid}")

    async def _after_crash(self, run_id: int, exc: BaseException | None) -> None:
        """runner 协程自己炸了，这时候还不能判定这一侧结束了。

        容器很可能还在跑。直接标 INTERRUPTED 会留下「状态说结束了、容器还在干活」
        的孤儿：槽位被放开，调度器接着起新题，实际并发就超了额度。所以先看容器，
        还活着就重新接管，只有确认容器没了才收尾。
        """
        with session() as db:
            run = db.get(TaskRun, run_id)
            if run is None or run.status != RUN_RUNNING:
                return
            name, task_id = run.container_name, run.task_id
        if run_id not in self._readopted and await dockerx.container_state(name) == "running":
            log.warning("run %s 的 runner 异常但容器 %s 还在跑，重新接管", run_id, name)
            self._readopted.add(run_id)
            self.running[run_id] = asyncio.create_task(self._wait_and_finalize(run_id, name))
            return
        with session() as db:
            run = db.get(TaskRun, run_id)
            if run and run.status == RUN_RUNNING:
                run.status = RUN_INTERRUPTED
                run.finished_at = utc_now()
                run.error = f"runner 异常: {exc}"
        bus.publish("tasks", {"type": "task", "id": task_id})

    def pick(self, free: int) -> list[int]:
        """挑这轮可以启动的 run。同一道题的两侧必须一起出闸。

        A 和 B 是同一道题在同一起点上的两次独立运行，对比的前提是环境尽量一致。
        一侧先跑、另一侧排在半小时后，机器负载和网关状况都变了，跑出来的差异说不清
        是模型的还是环境的。槽位不够两个就整道题继续等。
        """
        with session() as db:
            # priority 小的先跑，同优先级按领取时间；调队列顺序改的就是 priority
            tasks = db.execute(
                select(Task).where(Task.status == QUEUED)
                .order_by(Task.priority, Task.claimed_at, Task.id)
            ).scalars().all()
            picked: list[int] = []
            for t in tasks:
                if free - len(picked) < 2:
                    break
                runs = db.execute(select(TaskRun).where(TaskRun.task_id == t.id)
                                  .order_by(TaskRun.side)).scalars().all()
                # 两侧齐备、且都还没动过，才算这道题可以起
                if len(runs) != 2 or any(r.status not in (RUN_QUEUED, "PENDING") for r in runs):
                    continue
                picked.extend(r.id for r in runs)
            return picked

    def _mark_running(self, run_ids: list[int]) -> None:
        """出闸前先占住状态。

        runner 自己也会把 run 标成 RUNNING，但那是在起容器之后。中间这一小段里
        pick 会把同一批 run 再挑一遍，于是同一侧被起两次、容器名冲突。
        """
        with session() as db:
            for rid in run_ids:
                run = db.get(TaskRun, rid)
                if run is None:
                    continue
                run.status = RUN_RUNNING
                task = db.get(Task, run.task_id)
                if task is not None and task.status == QUEUED:
                    task.status = RUNNING
        for tid in {t for t in self._task_ids(run_ids)}:
            bus.publish("tasks", {"type": "task", "id": tid})

    def _task_ids(self, run_ids: list[int]) -> list[int]:
        with session() as db:
            return [r.task_id for r in
                    db.execute(select(TaskRun).where(TaskRun.id.in_(run_ids))).scalars()]

    async def _adopt(self) -> None:
        """进程重启后：状态为 RUNNING 的 run，按容器实际状态收尾。"""
        with session() as db:
            stale = db.execute(select(TaskRun).where(TaskRun.status == RUN_RUNNING)).scalars().all()
            items = [(r.id, r.container_name) for r in stale]
        for rid, name in items:
            state = await dockerx.container_state(name)
            if state == "running":
                log.info("接管运行中的容器 %s", name)
                self.running[rid] = asyncio.create_task(self._wait_and_finalize(rid, name))
            else:
                code = await dockerx.container_exit_code(name) if state else None
                await runner.finalize(rid, exit_code=code, result_event={},
                                      manual_stop=(state == ""))

    async def _wait_and_finalize(self, run_id: int, name: str) -> None:
        """等接管的容器结束。超时一样要管：这条路径漏了超时，这一侧会一直跑下去。"""
        limit = max(1, settings_store.get_int("run.timeout_minutes", 120)) * 60
        with session() as db:
            run = db.get(TaskRun, run_id)
            started = as_utc(run.started_at) if run else None
        elapsed = (utc_now() - started).total_seconds() if started else 0.0
        remain = max(60.0, limit - elapsed)
        try:
            r = await asyncio.wait_for(dockerx.run(["docker", "wait", name], timeout=limit + 300), remain)
        except asyncio.TimeoutError:
            log.warning("接管的容器 %s 超过 %s 分钟，停止并按超时收尾", name, limit // 60)
            await dockerx.run(["docker", "stop", "-t", "10", name], timeout=120)
            await runner.finalize(run_id, exit_code=None, result_event={}, timed_out=True)
            return
        try:
            code = int(r.out.strip())
        except ValueError:
            code = None
        await runner.finalize(run_id, exit_code=code, result_event={})


scheduler = Scheduler()
