"""难度筛选：判据、指标口径，以及它在推进链上的位置。"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from app import models as m
from app.services import difficulty as df
from app.services import watchdog as wd

TH = {"min_minutes": 30, "min_steps": 40, "low_steps": 30,
      "low_peer_steps": 80, "mid_peer_steps": 60}


def _judge(a_steps, b_steps, a_min=90, b_min=90, th=None):
    return df.judge({"A": a_steps, "B": b_steps}, {"A": a_min, "B": b_min}, th or TH)


# ---------------- 判据 ----------------

def test_a_pair_that_both_finished_fast_is_discarded():
    """两侧都在半小时内收工，说明题面对两边都没构成难度。"""
    verdict, reason = _judge(120, 140, a_min=21, b_min=28)
    assert verdict == df.DISCARD
    assert "30 分钟" in reason


def test_one_slow_side_keeps_the_pair():
    """只有两侧都低才废弃。一侧快一侧慢，恰恰说明题难住了一边。"""
    assert _judge(120, 140, a_min=12, b_min=95)[0] == df.PASS


def test_a_pair_that_both_took_few_steps_is_discarded():
    verdict, reason = _judge(31, 38)
    assert verdict == df.DISCARD
    assert "40 步" in reason


def test_a_very_light_side_needs_a_really_heavy_peer():
    """一侧才二十几步时，另一侧得确实吃力，否则那点落差只是风格差异。"""
    assert _judge(25, 75)[0] == df.DISCARD
    assert _judge(25, 80)[0] == df.PASS


def test_a_mildly_light_side_needs_a_moderately_heavy_peer():
    """一侧三十几步时门槛低一档：另一侧 60 步就够。"""
    assert _judge(35, 55)[0] == df.DISCARD
    assert _judge(35, 60)[0] == df.PASS


def test_the_light_side_may_be_either_of_the_two():
    """判据认的是两侧里低的那个，不是固定 A 或固定 B。"""
    assert _judge(75, 25)[0] == df.DISCARD
    assert _judge(80, 25)[0] == df.PASS


def test_two_heavy_sides_pass():
    assert _judge(62, 91)[0] == df.PASS


def test_thresholds_are_read_as_bounds_not_as_an_if_order():
    """两个陪跑门槛是设置项，人完全可能把低的那档调得反而更高。

    按 if 先后次序兜的写法在那种配置下会静静地漏判：一侧 25 步、另一侧 65 步的题，
    第一条按 low_peer=50 放行，而人的本意是「这么低的一侧要求更严」。
    """
    th = {**TH, "low_peer_steps": 50, "mid_peer_steps": 70}
    assert _judge(25, 65, th=th)[0] == df.PASS     # 低档线 50，65 过得去
    assert _judge(35, 65, th=th)[0] == df.DISCARD  # 中档线 70，65 不够


def test_a_missing_metric_lets_the_task_through():
    """「一步没调」和「还不知道」是两件事，拿不准就往下走。

    误放一道简单题只是白花一次分析额度；误废一道真题，两个容器跑掉的两个多小时连同
    这道题一起没了。两个方向的代价不对等。
    """
    verdict, reason = _judge(None, 120, a_min=15, b_min=18)
    assert verdict == df.UNKNOWN
    assert "A" in reason
    assert df.judge({"A": 10, "B": 12}, {"A": None, "B": 5}, TH)[0] == df.UNKNOWN


# ---------------- 指标从哪儿读 ----------------

def _run(side="A", *, steps=None, minutes=None, duration_ms=None):
    r = m.TaskRun(task_id=1, side=side, status=m.RUN_FINISHED,
                  container_name=f"solo-cc-07-{side}")
    r.verdict = {"artifact": {"tool_calls": steps} if steps is not None else {},
                 "protocol": {"duration_ms": duration_ms} if duration_ms else {}}
    if minutes is not None:
        r.started_at = m.utc_now() - timedelta(minutes=minutes)
        r.finished_at = m.utc_now()
    return r


def test_steps_come_from_the_same_field_the_list_shows():
    """界面上那个「N 步」就是 tool_calls。一把尺子量到底，否则人对不上账。"""
    assert df.steps_of(_run(steps=47)) == 47


def test_steps_are_unknown_rather_than_zero_when_the_field_is_missing():
    assert df.steps_of(_run()) is None
    assert df.steps_of(_run(steps=0)) == 0


def test_duration_prefers_the_two_timestamps():
    """两个时间戳相减是界面上显示的容器用时，CLI 自报的 duration_ms 比它短几分钟。"""
    run = _run(minutes=73, duration_ms=60_000)
    assert 72.5 < df.minutes_of(run) < 73.5


def test_duration_falls_back_to_what_the_cli_reported():
    assert df.minutes_of(_run(duration_ms=90 * 60_000)) == 90


def test_duration_is_unknown_when_neither_source_has_it():
    assert df.minutes_of(_run()) is None


# ---------------- 在推进链上的位置 ----------------

def _both_finished(ids, *, a_steps, b_steps, a_min, b_min):
    """把两侧摆成正常跑完的样子，带上指定的步数与用时。"""
    from app.db import session

    plan = {"A": (a_steps, a_min), "B": (b_steps, b_min)}
    with session() as db:
        for side, rid in ids.items():
            steps, minutes = plan[side]
            run = db.get(m.TaskRun, rid)
            run.status = m.RUN_FINISHED
            run.session_id = f"sess-{side}"
            run.trace_file = f"/x/{side}.jsonl"
            run.git_diff_stat = "src/a.ts | 3 +-"
            run.started_at = m.utc_now() - timedelta(minutes=minutes)
            run.finished_at = m.utc_now()
            run.verdict = {"process": {"exit_code": 0, "gateway_errors": []},
                           "protocol": {"subtype": "success"},
                           "artifact": {"trace_found": True, "changed_files": 3,
                                        "tool_calls": steps}}


@pytest.fixture()
def no_push(monkeypatch):
    """把推产物换成哨兵。被筛掉的题一次 git 推送都不该发生。"""
    pushed = []

    async def push(task_id):
        pushed.append(task_id)
        return {"ok": False, "message": "测试里不推"}

    async def remove(name):
        return True

    monkeypatch.setattr(wd, "push_artifacts", push)
    monkeypatch.setattr(wd.dockerx, "remove_container", remove)
    return pushed


@pytest.fixture()
def stub_rerun(monkeypatch, tmp_path):
    """重跑要动容器和 git，测试里全部换成空动作。"""
    async def remove(name):
        return True

    async def rebuild(task_no, repo_url, side, snapshot):
        return {"ok": True, "message": f"{side} 已重建"}

    monkeypatch.setattr(wd.dockerx, "remove_container", remove)
    monkeypatch.setattr(wd.gsb_repo, "rebuild_side", rebuild)
    monkeypatch.setattr(wd.config, "CODER_ROOT_MOUNT", tmp_path)
    monkeypatch.setattr(wd.config, "EXPORT_DIR", tmp_path / "exports")


def test_an_easy_pair_is_discarded_before_anything_is_spent(task_with_runs, no_push):
    """筛选排在推产物之前：它判废弃的题，后面每一步都是纯支出。"""
    from app.db import session

    task_id, ids = task_with_runs
    _both_finished(ids, a_steps=18, b_steps=22, a_min=11, b_min=14)

    r = asyncio.run(wd.advance_pair(task_id))

    assert r.get("discarded") is True
    assert no_push == [], "被筛掉的题不该推产物"
    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.DISCARDED
        assert "难度筛选未通过" in task.auto_error
        # 结论要留痕：事后被问起凭什么把它废了，凭据只有这四个数和当时的阈值
        report = task.difficulty_screen
        assert report["verdict"] == df.DISCARD
        assert report["steps"] == {"A": 18, "B": 22}
        assert report["thresholds"]["min_steps"] == 40


def test_a_hard_pair_goes_on_to_push_and_analysis(task_with_runs, no_push):
    from app.db import session

    task_id, ids = task_with_runs
    _both_finished(ids, a_steps=64, b_steps=132, a_min=55, b_min=118)

    asyncio.run(wd.advance_pair(task_id))

    assert no_push == [task_id]
    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.RUN_DONE
        assert task.difficulty_screen["verdict"] == df.PASS


def test_turning_the_screen_off_sends_everything_to_analysis(task_with_runs, no_push):
    from app.db import session
    from app.services import settings_store

    task_id, ids = task_with_runs
    _both_finished(ids, a_steps=9, b_steps=11, a_min=6, b_min=8)
    settings_store.set_one("difficulty.screen", "0")

    asyncio.run(wd.advance_pair(task_id))

    assert no_push == [task_id]
    with session() as db:
        assert db.get(m.Task, task_id).status == m.RUN_DONE


def test_restoring_a_screened_out_task_stops_it_being_screened_again(task_with_runs, no_push):
    """恢复就是人在说「这道题我还是要评」。

    不打这个记号的话，巡检下一轮拿同一套阈值再算一遍，四个数一个没变，结论当然还是
    废弃 —— 人按恢复只会看见题一闪又回到废弃列表，而他没做错任何事。
    """
    from app.db import session

    from app.routers import tasks as api

    task_id, ids = task_with_runs
    _both_finished(ids, a_steps=18, b_steps=22, a_min=11, b_min=14)
    asyncio.run(wd.advance_pair(task_id))

    out = asyncio.run(api.restore(task_id))
    assert "难度筛选不再拦它" in out["message"]

    # 再推进一次：这一回筛选放行，题照常往下走
    asyncio.run(wd.advance_pair(task_id))
    assert no_push == [task_id]
    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.RUN_DONE
        assert task.difficulty_screen["verdict"] == df.SKIPPED
        assert task.difficulty_screen["override"] is True


def test_restoring_a_task_discarded_for_other_reasons_stays_screenable(task_with_runs,
                                                                      stub_rerun):
    """重跑用尽而废弃的题压根没被筛过，恢复之后照样要走一遍难度筛选。

    对这种题也打放行记号，等于给这一步开了个绕行口：跑挂重跑几次的题往往正是那些
    又简单又不稳的题。
    """
    from app.db import session

    from app.routers import tasks as api

    task_id, ids = task_with_runs
    asyncio.run(wd.give_up(ids["A"], "网关 504 连着三次"))
    asyncio.run(api.restore(task_id))

    with session() as db:
        assert db.get(m.Task, task_id).difficulty_screen == {}


def test_a_rerun_drops_the_previous_metrics_but_keeps_the_release(task_with_runs,
                                                                 stub_rerun):
    """那四个数是上一跑的步数与用时，重跑之后不再是这道题的现状。

    人工放行那一笔要留：它是对这道题的决定，不随某一次跑作废。
    """
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        db.get(m.Task, task_id).difficulty_screen = {
            "verdict": df.DISCARD, "steps": {"A": 18, "B": 22}, "override": True,
            "override_at": "2026-01-01T00:00:00+00:00"}

    asyncio.run(wd.requeue_run(ids["A"], reason="超时"))

    with session() as db:
        report = db.get(m.Task, task_id).difficulty_screen
        assert report == {"override": True, "override_at": "2026-01-01T00:00:00+00:00"}


# ---------------- 试算 ----------------

def test_preview_reports_every_pair_without_touching_them(task_with_runs, no_push):
    """调阈值只能靠在自己认得的那批题上算一遍看名单，所以试算什么都不能改。"""
    from app.db import session

    task_id, ids = task_with_runs
    _both_finished(ids, a_steps=18, b_steps=22, a_min=11, b_min=14)

    items = df.preview()
    assert [x["task_no"] for x in items] == ["07"]
    assert items[0]["verdict"] == df.DISCARD
    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status != m.DISCARDED
        assert task.difficulty_screen == {}, "试算不许落库"


def test_preview_leaves_out_pairs_that_did_not_finish(task_with_runs):
    """跑挂的那一侧步数天然就低，算进名单只会凭空多出一批「会被废弃」的题。

    它们一道也不会真的走到筛选那一步：那条路上只有两侧都正常收尾才判难度，没跑成的
    归重跑和次数上限管。库里这个差别不小——有两条运行记录的 118 道里，两侧都正常跑完
    的只有 76 道。
    """
    from app.db import session

    _, ids = task_with_runs
    _both_finished(ids, a_steps=18, b_steps=22, a_min=11, b_min=14)
    with session() as db:
        db.get(m.TaskRun, ids["B"]).status = m.RUN_TIMEOUT
    assert df.preview() == []


# ---------------- 探路：先跑完那一侧就够判了 ----------------

def _one_finished(ids, *, side, steps, minutes, peer=m.RUN_PENDING):
    """把一侧摆成正常跑完的样子，另一侧留在队列里等槽位。"""
    from app.db import session

    with session() as db:
        for s, rid in ids.items():
            run = db.get(m.TaskRun, rid)
            if s != side:
                run.status = peer
                continue
            run.status = m.RUN_FINISHED
            run.session_id = f"sess-{s}"
            run.trace_file = f"/x/{s}.jsonl"
            run.git_diff_stat = "src/a.ts | 3 +-"
            run.started_at = m.utc_now() - timedelta(minutes=minutes)
            run.finished_at = m.utc_now()
            run.verdict = {"process": {"exit_code": 0, "gateway_errors": []},
                           "protocol": {"subtype": "success"},
                           "artifact": {"trace_found": True, "changed_files": 3,
                                        "tool_calls": steps}}


def scheduler_queue():
    from app.services.scheduler import scheduler
    return scheduler.queue()


PROBE_TH = {"probe_steps": 40, "probe_minutes": 30}


def test_a_fast_and_light_first_side_stops_the_pair():
    assert df.probe_judge(18, 11, PROBE_TH)[0] == df.DISCARD


def test_both_numbers_must_be_low_to_stop_it():
    """手上只有一侧的信息，所以收紧成「且」：二十步啃了两小时的题未必简单。"""
    assert df.probe_judge(18, 95, PROBE_TH)[0] == df.PASS
    assert df.probe_judge(120, 11, PROBE_TH)[0] == df.PASS


def test_a_missing_metric_holds_instead_of_counting_as_zero():
    assert df.probe_judge(None, 11, PROBE_TH)[0] == df.PROBE_HOLD
    assert df.probe_judge(18, None, PROBE_TH)[0] == df.PROBE_HOLD


def test_the_probe_discards_the_whole_task_before_the_peer_starts(task_with_runs, no_push):
    """另一侧还在等槽位，这时候废掉整题省下的是它完整的一次运行。"""
    from app.db import session

    task_id, ids = task_with_runs
    _one_finished(ids, side="A", steps=18, minutes=11)

    assert asyncio.run(wd._scan_probe()) == 1
    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.DISCARDED
        assert "探路未通过" in task.auto_error
        report = task.difficulty_screen["probe"]
        assert report["side"] == "A" and report["steps"] == 18


def test_the_probe_keeps_quiet_when_the_peer_is_already_running(task_with_runs, no_push):
    """那台容器的时间已经花下去了，这时废掉整题却要中断一次正在进行的运行。"""
    from app.db import session

    task_id, ids = task_with_runs
    _one_finished(ids, side="A", steps=25, minutes=11, peer=m.RUN_RUNNING)

    assert asyncio.run(wd._scan_probe()) == 0
    with session() as db:
        assert db.get(m.Task, task_id).status != m.DISCARDED


HARD_TH = {**PROBE_TH, "hard_steps": 20}


def test_below_the_hard_floor_only_steps_count():
    """6 步耗了 30.3 分钟的那道题：用时撑长了，步数已经说明它没构成难度。"""
    assert df.probe_judge(6, 30.3, HARD_TH)[0] == df.DISCARD
    assert df.probe_judge(6, None, HARD_TH)[0] == df.DISCARD
    assert df.probe_judge(20, 95, HARD_TH)[0] == df.PASS


def test_the_hard_floor_can_be_turned_off():
    assert df.probe_judge(6, 30.3, {**PROBE_TH, "hard_steps": 0})[0] == df.PASS


def test_the_hard_floor_discards_even_while_the_peer_runs(task_with_runs, no_push):
    """另一侧跑下去也必然被筛掉，停掉它才是省。"""
    from app.db import session

    task_id, ids = task_with_runs
    _one_finished(ids, side="A", steps=6, minutes=31, peer=m.RUN_RUNNING)

    assert asyncio.run(wd._scan_probe()) == 1
    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.DISCARDED
        assert "硬下限" in task.auto_error


def test_the_post_run_screen_also_applies_the_hard_floor():
    verdict, reason = df.judge({"A": 6, "B": 150}, {"A": 31, "B": 100}, {**TH, "hard_steps": 20})
    assert verdict == df.DISCARD and "硬下限" in reason


def test_the_probe_lets_a_heavy_first_side_through(task_with_runs, no_push):
    from app.db import session

    task_id, ids = task_with_runs
    _one_finished(ids, side="A", steps=120, minutes=95)

    assert asyncio.run(wd._scan_probe()) == 0
    with session() as db:
        assert db.get(m.Task, task_id).difficulty_screen["probe"]["verdict"] == df.PASS


def test_the_scheduler_holds_the_peer_until_the_probe_passes(task_with_runs):
    """判据长在调度里才省得下东西：巡检五分钟一轮，另一侧早出闸了。"""
    from app.db import session

    task_id, ids = task_with_runs
    _one_finished(ids, side="A", steps=18, minutes=11)
    assert scheduler_queue() == []

    with session() as db:
        assert df.probe_order(db, [task_id]) == ({ids["B"]}, set())


def test_a_freshly_claimed_task_still_gets_one_side_out(task_with_runs):
    """两侧都在等的题：一侧占首发，另一侧降到队尾。

    首发那个不能也降级，否则整道题一起沉底，探路无从开始；真扣住另一侧的话，
    队列只有这一道题时机器就闲着了。
    """
    assert [(q["side"], q["deferred"]) for q in scheduler_queue()] == [("A", False), ("B", True)]


def test_the_peer_queues_behind_everyone_while_the_first_side_is_running(task_with_runs):
    """还不知道这道题轻不轻，所以让别的题先走；但队列空下来它照样出闸。"""
    from app.db import session

    _, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_RUNNING
    assert [(q["side"], q["deferred"]) for q in scheduler_queue()] == [("B", True)]


def test_the_peer_queues_behind_everyone_while_the_first_side_is_being_retried(task_with_runs):
    """跑挂的那一侧还要重跑，这道题轻不轻仍然没答案，同样只降级不拦。"""
    from app.db import session

    _, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_FAILED
    assert [(q["side"], q["deferred"]) for q in scheduler_queue()] == [("B", True)]


def test_other_questions_get_the_slot_before_a_deferred_peer(tmp_db):
    """降级的实际效果：两道题都在等时，先各放一侧，两个第二侧排在它们后面。"""
    from app.db import session

    with session() as db:
        for no in ("07", "08"):
            t = m.Task(task_no=no, prompt_hash=f"h{no}", user_prompt="做点事", status=m.QUEUED,
                       repo_url="https://github.com/acme/widget",
                       env_snapshot="https://github.com/acme/widget/commit/" + "c" * 40)
            db.add(t)
            db.flush()
            for side in ("A", "B"):
                db.add(m.TaskRun(task_id=t.id, side=side, container_name=f"solo-cc-{no}-{side}"))

    assert [(q["task_no"], q["side"]) for q in scheduler_queue()] == [
        ("07", "A"), ("08", "A"), ("07", "B"), ("08", "B")]


def test_a_peer_is_really_held_once_the_first_side_came_out_light(task_with_runs):
    """判出太轻就不是降级了：这道题下一轮巡检就要废掉，另一侧一次都不该起。"""
    _, ids = task_with_runs
    _one_finished(ids, side="A", steps=18, minutes=11)
    assert scheduler_queue() == []


def test_a_requeued_side_goes_out_after_its_peer_finished_heavy(task_with_runs):
    """人手动重跑一侧时，另一侧早就跑完了，判它够重就放行。"""
    from app.db import session

    _, ids = task_with_runs
    _one_finished(ids, side="B", steps=120, minutes=95)
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_QUEUED
    assert [q["side"] for q in scheduler_queue()] == ["A"]


def test_the_scheduler_releases_the_peer_when_the_first_side_was_heavy(task_with_runs):
    _, ids = task_with_runs
    _one_finished(ids, side="A", steps=120, minutes=95)
    assert [q["side"] for q in scheduler_queue()] == ["B"]


def test_both_sides_go_out_together_when_probing_is_off(task_with_runs, monkeypatch):
    """关掉探路就是两侧照旧同时出闸，一道过滤都不做。"""
    monkeypatch.setattr(df, "probe_enabled", lambda: False)
    assert len(scheduler_queue()) == 2


def test_a_released_task_is_not_held_again(task_with_runs):
    """人在废弃列表里按过恢复，就是替这道题拍过板了，探路不该再把它扣住。"""
    from app.db import session

    task_id, ids = task_with_runs
    _one_finished(ids, side="A", steps=18, minutes=11)
    with session() as db:
        task = db.get(m.Task, task_id)
        task.difficulty_screen = {"verdict": df.DISCARD}
        assert df.override(task)
    assert [q["side"] for q in scheduler_queue()] == ["B"]


def test_probe_preview_counts_the_machine_time_it_would_save(task_with_runs):
    """问的不是「会废掉哪些题」，是「另一侧本来可以不跑的有哪些」。"""
    _, ids = task_with_runs
    _both_finished(ids, a_steps=18, b_steps=22, a_min=11, b_min=14)
    items = df.probe_preview()
    assert len(items) == 1
    assert items[0]["verdict"] == df.DISCARD
    assert items[0]["peer_steps"] in (18, 22)
