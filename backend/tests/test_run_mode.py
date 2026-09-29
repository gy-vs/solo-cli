"""自动配比：模式在第一个容器出闸时按当天「先 3 双、再 6 单」的循环定。"""

from __future__ import annotations

from datetime import timedelta

from app import models as m
from app.db import session
from app.services import run_mode, settings_store
from app.services.scheduler import Scheduler


def _task(db, no: str, mode: str = "auto") -> int:  # noqa: ANN001
    t = m.Task(task_no=no, prompt_hash=f"h{no}", user_prompt="做点事", status=m.QUEUED, run_mode=mode)
    db.add(t)
    db.flush()
    for side in ("A", "B"):
        db.add(m.TaskRun(task_id=t.id, side=side, container_name=f"solo-cc-{no}-{side}"))
    db.flush()
    return t.id


def _dispatch(modes: list[str]) -> list[str]:
    """按顺序建题并逐道出闸，返回每道最终定下的模式。"""
    settings_store.set_one("cc.model_b", "new/model")
    out = []
    for mode in modes:
        with session() as db:
            tid = _task(db, str(db.query(m.Task).count()), mode)
        with session() as db:
            out.append(run_mode.settle(db, tid))
    return out


def test_each_day_runs_three_dual_then_six_single(tmp_db):
    assert _dispatch(["auto"] * 12) == ["dual"] * 3 + ["single"] * 6 + ["dual"] * 3


def test_dual_side_b_gets_the_new_model_and_a_keeps_the_image_model(tmp_db):
    _dispatch(["auto"])
    with session() as db:
        assert {r.side: r.model for r in db.query(m.TaskRun)} == {"A": "", "B": "new/model"}


def test_forced_modes_count_toward_the_day(tmp_db):
    """强制双模型的题开跑也占掉循环里的双模型名额，后面的自动题不重复补。"""
    assert _dispatch(["dual", "dual", "auto", "auto", "auto"]) == \
        ["dual", "dual", "dual", "single", "single"]


def test_discarded_dual_is_refilled(tmp_db):
    _dispatch(["auto"] * 4)
    with session() as db:
        db.query(m.Task).filter(m.Task.run_mode == "dual").first().status = m.DISCARDED
    assert _dispatch(["auto"])[0] == "dual"


def test_yesterday_does_not_count(tmp_db):
    """跨天重新从三道双模型开始，昨天跑了多少双模型都不算今天的。"""
    _dispatch(["auto"] * 3)
    with session() as db:
        for t in db.query(m.Task):
            t.mode_at = t.mode_at - timedelta(days=1)
    assert _dispatch(["auto"])[0] == "dual"


def test_settle_only_once(tmp_db):
    """重跑、第二侧出闸都沿用第一次定的模式，设置改了也不换。"""
    _dispatch(["auto"])
    settings_store.set_one("cc.model_b", "other/model")
    with session() as db:
        tid = db.query(m.Task).first().id
        assert run_mode.settle(db, tid) is None
    with session() as db:
        assert db.query(m.TaskRun).filter(m.TaskRun.side == "B").one().model == "new/model"


def test_cycle_follows_the_settings(tmp_db):
    settings_store.set_one("run.cycle_dual", "1")
    settings_store.set_one("run.cycle_single", "1")
    assert _dispatch(["auto"] * 4) == ["dual", "single", "dual", "single"]


def _b(db, tid: int) -> m.TaskRun:  # noqa: ANN001
    return db.query(m.TaskRun).filter(m.TaskRun.task_id == tid, m.TaskRun.side == "B").one()


def test_switch_all_rewrites_queued_and_leaves_started_b_alone(tmp_db):
    settings_store.set_one("cc.model_b", "new/model")
    with session() as db:
        queued = _task(db, "1", "single")
        a_running = _task(db, "2", "single")
        b_running = _task(db, "3", "single")
    Scheduler()._mark_running([_run(a_running, "A"), _run(b_running, "B")])
    with session() as db:
        res = run_mode.switch_all(db, "dual", "new/model")
    assert sorted(res["changed"]) == sorted([queued, a_running]) and res["locked"] == ["3"]
    with session() as db:
        for tid in (queued, a_running):
            assert db.get(m.Task, tid).run_mode == "dual" and _b(db, tid).model == "new/model"
        assert db.get(m.Task, b_running).run_mode == "single" and _b(db, b_running).model == ""


def test_b_that_ran_once_stays_locked_after_requeue(tmp_db):
    """B 侧被看护退回重跑，前一次的轨迹是按旧模型跑的，不能再换。"""
    with session() as db:
        tid = _task(db, "1", "single")
        b = _b(db, tid)
        b.status, b.attempt = m.RUN_QUEUED, 2
    with session() as db:
        assert run_mode.switch_all(db, "dual", "new/model")["locked"] == ["1"]


def test_b_queued_for_the_first_time_is_switchable(tmp_db):
    with session() as db:
        tid = _task(db, "1", "single")
        _b(db, tid).status = m.RUN_QUEUED
    with session() as db:
        assert run_mode.switch_all(db, "dual", "new/model")["changed"] == [tid]


def test_switch_to_auto_keeps_unstarted_pending_and_assigns_started_now(tmp_db):
    settings_store.set_one("cc.model_b", "new/model")
    with session() as db:
        queued = _task(db, "1", "single")
        started = _task(db, "2", "single")
    Scheduler()._mark_running([_run(started, "A")])
    with session() as db:
        run_mode.switch_all(db, "auto", "new/model")
    with session() as db:
        assert db.get(m.Task, queued).run_mode == "auto" and db.get(m.Task, queued).mode_at is None
        # 今天第一道开跑的，按 3 双 6 单派到双模型
        assert db.get(m.Task, started).run_mode == "dual" and _b(db, started).model == "new/model"


def test_switch_back_to_single_clears_b_model(tmp_db):
    with session() as db:
        tid = _task(db, "1", "dual")
        _b(db, tid).model = "new/model"
    with session() as db:
        run_mode.switch_all(db, "single", "")
    with session() as db:
        assert db.get(m.Task, tid).run_mode == "single" and _b(db, tid).model == ""


def _run(tid: int, side: str) -> int:
    with session() as db:
        return db.query(m.TaskRun).filter(m.TaskRun.task_id == tid, m.TaskRun.side == side).one().id


def test_scheduler_settles_the_mode_before_the_container_starts(tmp_db):
    settings_store.set_one("cc.model_b", "new/model")
    with session() as db:
        tid = _task(db, "7")
        rid = db.query(m.TaskRun).filter(m.TaskRun.side == "A").one().id
    Scheduler()._mark_running([rid])
    with session() as db:
        t = db.get(m.Task, tid)
        assert t.run_mode == "dual" and t.mode_at is not None
        assert db.query(m.TaskRun).filter(m.TaskRun.side == "B").one().model == "new/model"
