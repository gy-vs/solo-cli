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
