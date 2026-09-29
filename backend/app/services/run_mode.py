"""运行模式配比：每天开跑的题按「先 N 道双模型、再 M 道单模型」循环，默认 3 + 6。

模式在一道题的第一个容器出闸时才定，而不是领取时：队列很长时，今天领的题可能明天才跑，
按领取算的话今天实际跑的比例和配出来的对不上。按自动配比领取的题入队时标成 auto，
调度器出闸那一刻按当天已开跑的题数决定它落在循环的哪个位置。

手动强制单/双模型的题照样计入当天的循环：配比管的是当天实际跑了什么。
废弃的不算：难度筛选和人工废弃都发生在跑完之后，双模型的题被废得多，交上去的比例就会
跌破下限，把它们剔掉再数，缺口由后面开跑的题补上。

「当天」按东八区算，和总览上今日统计是同一个日界线。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app import config
from app.models import DISCARDED, RUN_PENDING, SCHEDULABLE, Task, TaskRun, utc_now
from app.services import settings_store

log = logging.getLogger("run_mode")

MODE_AUTO = "auto"
MODES = (MODE_AUTO, config.RUN_MODE_SINGLE, config.RUN_MODE_DUAL)
FIXED = (config.RUN_MODE_SINGLE, config.RUN_MODE_DUAL)

_CST = timezone(timedelta(hours=8))


def cycle() -> tuple[int, int]:
    """一轮里先跑几道双模型、再跑几道单模型。"""
    dual = max(0, settings_store.get_int("run.cycle_dual", 3))
    single = max(0, settings_store.get_int("run.cycle_single", 6))
    if dual + single == 0:
        return 0, 1
    return dual, single


def _today(dt: datetime | None, today) -> bool:  # noqa: ANN001
    if dt is None:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_CST).date() == today


def today_counts(db) -> tuple[int, int]:  # noqa: ANN001
    """当天开跑且没废弃的题数，以及其中双模型的题数。"""
    today = datetime.now(_CST).date()
    rows = db.query(Task.mode_at, Task.run_mode).filter(
        Task.mode_at.isnot(None), Task.status != DISCARDED, Task.run_mode.in_(FIXED)).all()
    live = [mode for at, mode in rows if _today(at, today)]
    return len(live), sum(1 for m in live if m == config.RUN_MODE_DUAL)


def next_mode(db) -> str:  # noqa: ANN001
    """下一道开跑的自动配比题该用哪种模式。

    按数量而不是按序号取模：第 k 轮结束时双模型应当已有 k 轮 × N 道，缺多少就先补多少。
    这样中间插进来的强制单/双模型、被废弃的双模型题都会被后面的题自然抹平。
    """
    dual_n, single_n = cycle()
    total, dual = today_counts(db)
    rounds = total // (dual_n + single_n) + 1       # 这一道落在第几轮
    return config.RUN_MODE_DUAL if dual < dual_n * rounds else config.RUN_MODE_SINGLE


def settle(db, task_id: int) -> str | None:  # noqa: ANN001
    """题的第一个容器出闸时调用：把模式定死，auto 的按当天循环派。返回刚定下的模式。

    已经定过的题（mode_at 非空）什么都不做：重跑、第二侧出闸都沿用第一次定的。
    调用方负责提交；同一轮里连着出闸好几道时，每道之后要 flush，下一道才数得到它。
    """
    task = db.get(Task, task_id)
    if task is None or task.mode_at is not None:
        return None
    mode = task.run_mode
    if mode == MODE_AUTO:
        mode = next_mode(db)
        model = settings_store.get("cc.model_b").strip() if mode == config.RUN_MODE_DUAL else ""
        if mode == config.RUN_MODE_DUAL and not model:
            # 领取时已经拦过，走到这里只能是之后有人把设置清空了。照单模型跑，但要留痕
            log.error("题 %s 按配比该跑双模型，但 B 侧模型名为空，改按单模型跑", task.task_no)
            mode = config.RUN_MODE_SINGLE
        for r in db.query(TaskRun).filter(TaskRun.task_id == task_id):
            r.model = model if r.side == "B" else ""
        task.run_mode = mode
        log.info("题 %s 开跑，按当天配比派为%s", task.task_no,
                 "双模型" if mode == config.RUN_MODE_DUAL else "单模型")
    elif mode not in FIXED:
        mode = task.run_mode = config.RUN_MODE_SINGLE
    task.mode_at = utc_now()
    db.flush()
    return mode


def switchable(task: Task, runs: list[TaskRun]) -> bool:
    """这道题还能不能改模式：只看 B 侧有没有真正起过容器。

    两种模式下 A 侧都用镜像自带模型，差别全在 B 侧的模型名上，所以 A 在跑、甚至跑完都不妨碍。
    B 侧只要起过一次就不行，哪怕后来被退回重跑（attempt > 1）：前一次的轨迹是按旧模型跑的。
    """
    if task.status not in SCHEDULABLE:
        return False
    b = next((r for r in runs if r.side == "B"), None)
    return b is not None and b.status == RUN_PENDING and b.attempt <= 1 and b.started_at is None


def switch(db, task: Task, runs: list[TaskRun], mode: str, model_b: str) -> str:  # noqa: ANN001
    """把一道可切换的题改成 mode，返回改完后的 run_mode。调用方先用 switchable 判过。

    还没开跑的题直接换标签，auto 照旧等出闸时再定。已经开跑（A 侧出过闸）的题 settle 不会
    再来，选 auto 就得当场按当天循环派一个：先把自己标成 auto，统计里就不会把它算进去。
    """
    if task.mode_at is not None and mode == MODE_AUTO:
        task.run_mode = MODE_AUTO
        db.flush()
        mode = next_mode(db)
        if mode == config.RUN_MODE_DUAL and not model_b:
            mode = config.RUN_MODE_SINGLE
    for r in runs:
        r.model = model_b if mode == config.RUN_MODE_DUAL and r.side == "B" else ""
    task.run_mode = mode
    db.flush()
    return mode


def switch_all(db, mode: str, model_b: str) -> dict:  # noqa: ANN001
    """把队列里所有还能切换的题统一改成 mode。

    必须在事件循环里同步做完、中间不能 await：调度器出闸（标 RUNNING + settle）也是同步的，
    两边不交错，才不会出现判的时候 B 还在排队、改完它已经按旧模型起了容器。
    """
    tasks = db.query(Task).filter(Task.status.in_(SCHEDULABLE)).order_by(Task.priority, Task.claimed_at).all()
    by_task: dict[int, list[TaskRun]] = {}
    for r in db.query(TaskRun).filter(TaskRun.task_id.in_([t.id for t in tasks] or [-1])):
        by_task.setdefault(r.task_id, []).append(r)
    changed: list[int] = []
    locked: list[str] = []
    same = 0
    for t in tasks:
        runs = by_task.get(t.id, [])
        if not switchable(t, runs):
            locked.append(t.task_no)
            continue
        before = (t.run_mode, next((r.model for r in runs if r.side == "B"), ""))
        switch(db, t, runs, mode, model_b)
        if (t.run_mode, next((r.model for r in runs if r.side == "B"), "")) == before:
            same += 1
        else:
            changed.append(t.id)
            log.info("题 %s 运行模式 %s → %s", t.task_no, before[0], t.run_mode)
    return {"changed": changed, "same": same, "locked": locked}


def quota(db) -> dict:  # noqa: ANN001
    total, dual = today_counts(db)
    dual_n, single_n = cycle()
    return {"date": datetime.now(_CST).date().isoformat(), "total": total, "dual": dual,
            "cycle": [dual_n, single_n], "next": next_mode(db)}
