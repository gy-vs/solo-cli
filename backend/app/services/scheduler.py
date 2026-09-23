"""并发调度：槽位按容器算，一个空槽放一个 run，谁排到谁先出闸。

额度的单位是容器而不是题。一道题要占两个容器，按题算额度会让实际并发翻倍，
机器上一下起八个容器直接把内存吃满。

排队的单位同样是容器。A 与 B 各排各的队，谁排到谁先跑，跑完的结果在库里等着对方，
两侧都齐了再由巡检去配对分析 —— 这跟「必须两个一起出闸」是两回事，后者会让整条
队列被队头那道凑不齐两个空槽的题堵死，而空出来的那个槽谁也用不上。
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import datetime

from sqlalchemy import select

from app import config
from app.db import session
from app.events import bus
from app.models import (
    RUN_INTERRUPTED, RUN_QUEUED, RUN_RUNNING, RUN_WAITING, SCHEDULABLE, Task, TaskRun,
    as_utc, derive_task_status, utc_now,
)
from app.services import difficulty, dockerx, runner, settings_store

log = logging.getLogger("scheduler")

TICK_SECONDS = 2
# 没有任何动作时多久打一行队列心跳。既是「调度还活着」的证据，也是事后回溯
# 「那会儿到底谁在跑、谁在等」的唯一记录 —— 出闸是瞬时事件，不写下来就查不到了。
HEARTBEAT_SECONDS = 60


class Scheduler:
    def __init__(self) -> None:
        self.running: dict[int, asyncio.Task] = {}   # run_id -> 协程
        self._loop_task: asyncio.Task | None = None
        self._stopping = False
        self._readopted: set[int] = set()  # 因 runner 异常重新接管过的，不再重复接管
        self.last_tick_at: datetime | None = None
        self.last_error = ""
        self._last_beat = 0.0

    @property
    def max_parallel(self) -> int:
        return max(1, settings_store.get_int("scheduler.max_parallel", 3))

    @property
    def paused(self) -> bool:
        return settings_store.get_bool("scheduler.paused", False)

    # ---------------- 队列视图 ----------------

    def queue(self) -> list[dict]:
        """完整排队序列，已按出闸先后排好。第 n 项就是第 n 个拿到槽位的容器。"""
        with session() as db:
            return self._waiting(db)

    def _waiting(self, db) -> list[dict]:  # noqa: ANN001
        """在等槽位的 run，按 (题优先级, 领取时间, 题 id, 侧) 排序。

        题级状态取 SCHEDULABLE 而不只是 QUEUED，理由见该常量的注释。
        两侧记录不齐的题跳过：缺一侧说明数据坏了，发出去也只会跑出半份结果，
        而巡检那边永远等不到配对。

        开着探路时还要再动一道队形（见 difficulty 末尾那一节）。先跑完那一侧已经判出
        太轻的题，另一侧直接不放——那道题下一轮巡检就要废掉。其余「还不知道轻不轻」的
        第二侧不拦，只降一档排到队尾：别的题的首侧先走，轮完了还有空槽它照样出闸。

        这道排序必须长在这里而不是交给巡检。巡检默认五分钟一轮，调度两秒一轮，等巡检
        判出来，另一侧早就跑起来了。
        """
        rows = db.execute(
            select(TaskRun.id, TaskRun.task_id, TaskRun.side, TaskRun.status, TaskRun.attempt,
                   Task.task_no, Task.priority, Task.claimed_at)
            .join(Task, Task.id == TaskRun.task_id)
            .where(Task.status.in_(SCHEDULABLE))
            .order_by(Task.priority, Task.claimed_at, Task.id, TaskRun.side)
        ).all()
        sides = Counter(r.task_id for r in rows)
        ready = [r for r in rows
                 if r.status in RUN_WAITING and sides[r.task_id] == len(config.SIDES)]
        held, deferred = difficulty.probe_order(db, sorted({r.task_id for r in ready}))
        out = [{"run_id": r.id, "task_id": r.task_id, "task_no": r.task_no, "side": r.side,
                "attempt": r.attempt, "requeued": r.status == RUN_QUEUED,
                "deferred": r.id in deferred}
               for r in ready if r.id not in held]
        # 稳定排序，降级的整体挪到队尾，各自内部仍按上面那个优先级顺序
        out.sort(key=lambda q: q["deferred"])
        return out

    def _running_view(self) -> list[dict]:
        with session() as db:
            rows = db.execute(
                select(TaskRun.id, TaskRun.side, TaskRun.attempt, TaskRun.started_at, Task.task_no)
                .join(Task, Task.id == TaskRun.task_id)
                .where(TaskRun.id.in_(list(self.running) or [-1]))
                .order_by(TaskRun.started_at)
            ).all()
        now = utc_now()
        return [{"run_id": r.id, "task_no": r.task_no, "side": r.side, "attempt": r.attempt,
                 "minutes": round(((now - s).total_seconds() / 60) if (s := as_utc(r.started_at)) else 0)}
                for r in rows]

    def snapshot(self) -> dict:
        queue = self.queue()
        beat = as_utc(self.last_tick_at)
        return {
            "running": len(self.running),
            "max_parallel": self.max_parallel,
            "free": max(0, self.max_parallel - len(self.running)),
            "running_ids": sorted(self.running),
            "running_runs": self._running_view(),
            # queued 一直是「还要等几个容器」，改成按 run 计数后这个数才和槽位同一个单位
            "queued": len(queue),
            "queued_tasks": len({q["task_id"] for q in queue}),
            "queue": queue[:200],
            "paused": self.paused,
            "alive": self.alive,
            "last_tick_at": beat.isoformat() if beat else None,
            "last_error": self.last_error,
        }

    # ---------------- 生命周期 ----------------

    @property
    def alive(self) -> bool:
        return bool(self._loop_task) and not self._loop_task.done()

    async def start(self) -> None:
        await self._adopt()
        self._stopping = False
        self._loop_task = asyncio.create_task(self._loop(), name="scheduler-loop")

    async def stop(self) -> None:
        self._stopping = True
        if self._loop_task:
            self._loop_task.cancel()

    def ensure_alive(self) -> bool:
        """循环没了就地重启。返回是否做了重启。

        调度停摆是这套东西最贵的故障：机器空着、题在队列里排一整夜，而日志里一个字
        都没有。循环本身已经兜住了所有异常，这里防的是它被取消掉这种兜不住的情况。
        """
        if self._stopping or self.alive:
            return False
        exc = self._loop_task.exception() if self._loop_task and not self._loop_task.cancelled() else None
        log.error("调度循环已停止（%s），就地重启", exc or "被取消")
        self._loop_task = asyncio.create_task(self._loop(), name="scheduler-loop")
        return True

    async def _loop(self) -> None:
        while not self._stopping:
            try:
                await self._tick()
                self.last_tick_at = utc_now()
                self.last_error = ""
            except asyncio.CancelledError:
                raise
            except BaseException as exc:  # noqa: BLE001
                # 这里必须是 BaseException。以前只接 Exception，任何逃出来的
                # BaseException 都会让循环无声退出，表现就是队列从某一刻起再也不动，
                # 而日志里干干净净什么都没有。
                self.last_error = f"{type(exc).__name__}: {exc}"
                log.exception("调度循环异常")
            await asyncio.sleep(TICK_SECONDS)

    # ---------------- 出闸 ----------------

    async def _tick(self) -> None:
        for rid, fut in list(self.running.items()):
            if fut.done():
                self.running.pop(rid, None)
                if fut.exception():
                    log.error("run_side(%s) 异常: %s", rid, fut.exception())
                    await self._after_crash(rid, fut.exception())
        self._watch_watchdog()
        self._reconcile()
        if self.paused:
            # 暂停期间照样要打心跳。心跳是「调度还活着」的唯一证据，而暂停恰恰是最需要
            # 这个证据的时候 —— 队列不动到底是因为按了暂停，还是循环已经停摆，
            # 光看「没有日志」分不出来。
            self._heartbeat()
            return
        free = self.max_parallel - len(self.running)
        picked = self.pick(free)
        if picked:
            names = self._names(picked)
            self._mark_running(picked)
            for rid in picked:
                self._readopted.discard(rid)
                self.running[rid] = asyncio.create_task(runner.run_side(rid), name=f"run-{rid}")
            log.info("出闸 %s · 占用 %s/%s · 队列还剩 %s", "、".join(names),
                     len(self.running), self.max_parallel, len(self.queue()))
        self._heartbeat()

    def _names(self, run_ids: list[int]) -> list[str]:
        with session() as db:
            rows = db.execute(
                select(Task.task_no, TaskRun.side).join(Task, Task.id == TaskRun.task_id)
                .where(TaskRun.id.in_(run_ids))).all()
        return [f"{no}-{side}" for no, side in rows]

    def _heartbeat(self) -> None:
        now = asyncio.get_running_loop().time()
        if now - self._last_beat < HEARTBEAT_SECONDS:
            return
        self._last_beat = now
        run = self._running_view()
        queue = self.queue()
        log.info("队列 · 在跑 %s/%s [%s] · 等 %s 个容器 [%s]%s",
                 len(run), self.max_parallel,
                 "、".join(f"{r['task_no']}-{r['side']}({r['minutes']}m)" for r in run) or "空",
                 len(queue), "、".join(f"{q['task_no']}-{q['side']}" for q in queue[:6]) or "空",
                 "（已暂停出队）" if self.paused else "")

    def _reconcile(self) -> None:
        """把题级状态对齐到两侧 run 的现状，两秒一轮。

        写题级状态的地方有好几处（出闸、收尾、重跑、废弃），哪一处写歪了都会让题
        显示成另一回事。与其要求每一处都写对，不如在这里统一拨回来 —— 状态本来就是
        从两侧 run 推得出来的，没有独立的真相。
        """
        changed: list[int] = []
        with session() as db:
            tasks = db.execute(select(Task).where(Task.status.in_(SCHEDULABLE))).scalars().all()
            by_task: dict[int, list[TaskRun]] = {}
            for r in db.execute(select(TaskRun).where(
                    TaskRun.task_id.in_([t.id for t in tasks] or [-1]))).scalars():
                by_task.setdefault(r.task_id, []).append(r)
            for t in tasks:
                want = derive_task_status(by_task.get(t.id, []))
                if want and want != t.status:
                    log.info("题 %s 状态 %s → %s（按两侧 run 推）", t.task_no, t.status, want)
                    t.status = want
                    changed.append(t.id)
        for tid in changed:
            bus.publish("tasks", {"type": "task", "id": tid})

    def _watch_watchdog(self) -> None:
        """顺手看一眼巡检还在不在。两个循环互相盯着，谁停了对方负责拉起来。"""
        from app.services import watchdog

        watchdog.ensure_alive()

    def pick(self, free: int) -> list[int]:
        """挑这轮出闸的 run：排队序列的前 free 个，不看它们属于哪道题。

        以前这里是「同一道题的两侧必须一起出闸」，理由是两侧环境要一致。实际跑下来
        这个约束换不到一致性 —— 一道题两个容器本来就要跑一两个小时，同时开始不等于
        同时结束，环境该变照样变 —— 却换来了队头阻塞：只剩一个空槽时，队头那道等着
        两个槽的题会把整条队列挡住，空槽谁也用不上，机器就那么闲着。
        """
        if free <= 0:
            return []
        with session() as db:
            return [q["run_id"] for q in self._waiting(db)[:free]]

    def _mark_running(self, run_ids: list[int]) -> None:
        """出闸前先占住状态。

        runner 自己也会把 run 标成 RUNNING，但那是在起容器之后。中间这一小段里
        pick 会把同一批 run 再挑一遍，于是同一侧被起两次、容器名冲突。
        """
        task_ids: set[int] = set()
        with session() as db:
            for rid in run_ids:
                run = db.get(TaskRun, rid)
                if run is None:
                    continue
                run.status = RUN_RUNNING
                task_ids.add(run.task_id)
            for tid in task_ids:
                sync_task_status(db, tid)
        for tid in task_ids:
            bus.publish("tasks", {"type": "task", "id": tid})

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
            self.running[run_id] = asyncio.create_task(
                runner.attach_run(run_id), name=f"attach-{run_id}")
            return
        with session() as db:
            run = db.get(TaskRun, run_id)
            if run and run.status == RUN_RUNNING:
                run.status = RUN_INTERRUPTED
                run.finished_at = utc_now()
                run.error = f"runner 异常: {exc}"
            sync_task_status(db, task_id)
        bus.publish("tasks", {"type": "task", "id": task_id})

    # ---------------- 重启接管 ----------------

    async def _adopt(self) -> None:
        """进程重启后：状态为 RUNNING 的 run，还活着的接回输出，已经退了的按实际状态收尾。

        接回输出而不是只等一个退出码，见 runner.attach_run —— 容器是 sibling 容器，
        进程重启带走的只是读它 stdout 的那根管子，日志还在。
        """
        with session() as db:
            stale = db.execute(select(TaskRun).where(TaskRun.status == RUN_RUNNING)).scalars().all()
            items = [(r.id, r.container_name) for r in stale]
        for rid, name in items:
            state = await dockerx.container_state(name)
            if state == "running":
                log.info("接管运行中的容器 %s", name)
                self.running[rid] = asyncio.create_task(
                    runner.attach_run(rid), name=f"attach-{rid}")
            else:
                code = await dockerx.container_exit_code(name) if state else None
                await runner.finalize(rid, exit_code=code, result_event={},
                                      container_gone=(state == ""))


def sync_task_status(db, task_id: int) -> str | None:  # noqa: ANN001
    """把题级状态对齐到两侧 run 的现状。调用方负责所在事务的提交。

    只在题处于运行阶段时改写。已经进到分析、上传或废弃的题，状态由那边的流程说了算，
    这里插一脚会把它们拽回 QUEUED。
    """
    task = db.get(Task, task_id)
    if task is None or task.status not in SCHEDULABLE:
        return None
    runs = db.query(TaskRun).filter(TaskRun.task_id == task_id).all()
    want = derive_task_status(runs)
    if want and want != task.status:
        task.status = want
    return want


scheduler = Scheduler()
