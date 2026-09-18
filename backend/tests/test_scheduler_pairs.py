"""调度：额度和排队的单位都是容器，一个空槽放一个 run。"""

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


def test_picks_both_sides_when_slots_allow(sched):
    _task, ids = _add_task()
    assert sorted(sched.pick(4)) == sorted(ids.values())


def test_one_free_slot_sends_one_side_out(sched):
    """槽位不够两个也要发。

    这是改动的核心：以前整道题会一起等第二个槽，于是只剩一个空槽时队头把整条队列
    堵死，那个槽谁也用不上。现在 A 先走，B 留在队列里等下一个槽，两侧跑完再配对。
    """
    _task, ids = _add_task()
    assert sched.pick(1) == [ids["A"]]


def test_slots_are_counted_per_container(sched):
    _add_task(no="07")
    _add_task(no="08")
    assert len(sched.pick(4)) == 4
    # 3 个槽就发 3 个容器，不会因为凑不齐一道题而空着
    assert len(sched.pick(3)) == 3


def test_priority_decides_which_task_goes_first(sched):
    _t1, low = _add_task(no="07", priority=9)
    _t2, high = _add_task(no="08", priority=1)
    assert sorted(sched.pick(2)) == sorted(high.values())


def test_a_goes_before_b_within_a_task(sched):
    _t, ids = _add_task(no="07")
    assert sched.pick(2) == [ids["A"], ids["B"]]


def test_skips_tasks_not_claimed_yet(sched):
    _add_task(no="07", status=m.CLAIMED)
    assert sched.pick(4) == []


def test_skips_runs_already_running(sched):
    _t, _ids = _add_task(no="07", run_status=m.RUN_RUNNING)
    assert sched.pick(4) == []


def test_skips_task_missing_one_side(sched):
    """只有一侧 run 的题是数据坏了，起来只会跑出半份结果。"""
    _t, _ids = _add_task(no="07", sides=("A",))
    assert sched.pick(4) == []


def test_finished_side_does_not_get_rescheduled(sched):
    """跑完的那一侧不能再被起一遍，但另一侧该走还是要走。"""
    from app.db import session

    _t, ids = _add_task(no="07")
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_FINISHED
        db.get(m.TaskRun, ids["B"]).status = m.RUN_QUEUED

    assert sched.pick(4) == [ids["B"]]


def test_side_requeued_while_the_other_still_runs_goes_out_alone(sched):
    """另一侧还在跑的时候重跑这一侧，也不必等它。"""
    from app.db import session

    _t, ids = _add_task(no="07")
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_RUNNING
        db.get(m.TaskRun, ids["B"]).status = m.RUN_QUEUED

    assert sched.pick(4) == [ids["B"]]


def test_running_task_still_feeds_the_queue(sched):
    """题级是 RUNNING 时，排队的那一侧照样要能出闸。

    这是队列停摆的原形：A 出闸把题带成 RUNNING，B 随后被退回队列，而候选集只认
    QUEUED 的题，于是 B 再也排不上，题看上去在跑、实际半死不活地挂着。
    """
    from app.db import session

    tid, ids = _add_task(no="07")
    with session() as db:
        db.get(m.Task, tid).status = m.RUNNING
        db.get(m.TaskRun, ids["A"]).status = m.RUN_RUNNING
        db.get(m.TaskRun, ids["B"]).status = m.RUN_QUEUED

    assert sched.pick(4) == [ids["B"]]


def test_head_of_queue_never_blocks_the_rest(sched):
    """队头那道题占不满槽位时，后面的照样往前走。"""
    from app.db import session

    _t1, first = _add_task(no="07", priority=1)
    _t2, second = _add_task(no="08", priority=2)
    with session() as db:
        db.get(m.TaskRun, first["A"]).status = m.RUN_RUNNING   # 07 只剩 B 在等

    # 三个槽：07-B 一个，剩下两个给 08 的两侧，一个都不浪费
    assert sched.pick(3) == [first["B"], second["A"], second["B"]]


def test_snapshot_reports_queue_in_containers(sched):
    _add_task(no="07")
    snap = sched.snapshot()
    assert snap["queued"] == 2            # 两个容器在等，不是一道题
    assert snap["queued_tasks"] == 1
    assert snap["max_parallel"] == 4
    assert snap["free"] == 4
    assert snap["running"] == 0
    assert [q["side"] for q in snap["queue"]] == ["A", "B"]


def test_repo_waiting_api_is_gone(sched):
    assert not hasattr(sched, "waiting_on_repo")
    assert "repo_waiting" not in sched.snapshot()
