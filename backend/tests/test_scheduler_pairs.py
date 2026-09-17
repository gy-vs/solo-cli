"""调度：并发额度按容器算，A/B 必须成对出闸。"""

from __future__ import annotations

import pytest

from app import models as m
from app.services.scheduler import Scheduler


def _add_task(status=m.QUEUED, no="07", priority=0, sides=("A", "B"),
              run_status=m.RUN_PENDING):
    from app.db import session

    with session() as db:
        t = m.Task(task_no=no, prompt_hash="h" + no, status=status, priority=priority,
                   claimed_at=m.utc_now())
        db.add(t)
        db.flush()
        ids = {}
        for side in sides:
            r = m.TaskRun(task_id=t.id, side=side, status=run_status,
                          container_name=f"solo-cc-{no}-{side}")
            db.add(r)
            db.flush()
            ids[side] = r.id
        return t.id, ids


@pytest.fixture()
def sched(tmp_db, monkeypatch):
    s = Scheduler()
    monkeypatch.setattr("app.services.settings_store.get_int",
                        lambda k, d=0: 4 if k == "scheduler.max_parallel" else d)
    monkeypatch.setattr("app.services.settings_store.get_bool", lambda k, d=False: False)
    return s


def test_picks_both_sides_of_one_task(sched):
    _task, ids = _add_task()
    assert sorted(sched.pick(4)) == sorted(ids.values())


def test_waits_when_only_one_slot_left(sched):
    """一侧先跑另一侧干等，两份轨迹的起跑环境就不可比了，宁可整道题等着。"""
    _add_task()
    assert sched.pick(1) == []


def test_slots_are_counted_per_container(sched):
    _add_task(no="07")
    _add_task(no="08")
    # 4 个槽正好两道题
    assert len(sched.pick(4)) == 4
    # 3 个槽只够一道
    assert len(sched.pick(3)) == 2


def test_priority_decides_which_task_goes_first(sched):
    _t1, low = _add_task(no="07", priority=9)
    _t2, high = _add_task(no="08", priority=1)
    assert sorted(sched.pick(2)) == sorted(high.values())


def test_same_project_tasks_run_in_parallel(sched):
    """单跑时代一个项目只能跑一道，双跑时两侧目录已经分开，没有这个限制了。"""
    _add_task(no="07")
    _add_task(no="08")
    picked = sched.pick(4)
    assert len(picked) == 4


def test_skips_tasks_not_queued(sched):
    _add_task(no="07", status=m.CLAIMED)
    assert sched.pick(4) == []


def test_skips_runs_already_running(sched):
    _t, ids = _add_task(no="07", run_status=m.RUN_RUNNING)
    assert sched.pick(4) == []


def test_skips_task_missing_one_side(sched):
    """只有一侧 run 的题是数据坏了，起来只会跑出半份结果。"""
    _t, ids = _add_task(no="07", sides=("A",))
    assert sched.pick(4) == []


def test_finished_side_does_not_get_rescheduled(sched):
    from app.db import session

    _t, ids = _add_task(no="07")
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_FINISHED
    # A 已经跑完，这道题不该再整体出闸
    assert sched.pick(4) == []


def test_repo_waiting_api_is_gone(sched):
    assert not hasattr(sched, "waiting_on_repo")
    assert "repo_waiting" not in sched.snapshot()


def test_snapshot_reports_queued_runs(sched):
    _add_task(no="07")
    snap = sched.snapshot()
    assert snap["queued"] == 2
    assert snap["max_parallel"] == 4
    assert snap["running"] == 0
