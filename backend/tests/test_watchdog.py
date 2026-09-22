"""巡检：异常判定、重跑准备、配对推进。"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from app import models as m
from app.services import watchdog as wd


def _run(**kw):
    verdict = kw.pop("verdict", None)
    base = dict(task_id=1, side="A", status=m.RUN_FINISHED, attempt=1,
                container_name="solo-cc-07-A", git_diff_stat="src/a.ts | 3 +-")
    base.update(kw)
    r = m.TaskRun(**base)
    r.verdict = verdict if verdict is not None else {
        "process": {"exit_code": 0, "gateway_errors": []},
        "protocol": {"subtype": "success"},
        "artifact": {"trace_found": True, "changed_files": 3},
    }
    return r


# ---------------- 异常判定 ----------------

def test_clean_finished_run_is_not_abnormal():
    assert wd.abnormal_reason(_run()) == ""


def test_gateway_error_alone_is_not_abnormal():
    """CC 自带十次重试，中途报过 504 但最终跑完的，不该重跑。

    以前只要 stderr 里出现过状态码就把整侧推倒重来，等于把一次已经成功的运行作废，
    白烧一个多小时，还让本来能配对的两侧再次错开。
    """
    r = _run(verdict={"process": {"gateway_errors": ["504"],
                                  "retries": {"attempt": 3, "max_retries": 10}},
                      "protocol": {"subtype": "success"},
                      "artifact": {"trace_found": True, "changed_files": 3}})
    assert wd.abnormal_reason(r) == ""


def test_failed_run_reports_exhausted_gateway_retries():
    """重试用尽仍没跑成才介入，原因里要说清重试到了第几次。"""
    r = _run(status=m.RUN_FAILED,
             verdict={"process": {"gateway_errors": ["504"],
                                  "retries": {"attempt": 10, "max_retries": 10}},
                      "protocol": {}, "artifact": {}})
    reason = wd.abnormal_reason(r)
    assert "504" in reason and "10/10" in reason


def test_nonzero_exit_code_is_abnormal():
    r = _run(verdict={"process": {"exit_code": 1}, "protocol": {"subtype": "success"},
                      "artifact": {"trace_found": True, "changed_files": 2}})
    assert "退出码 1" in wd.abnormal_reason(r)


def test_non_success_subtype_is_abnormal():
    r = _run(verdict={"process": {"exit_code": 0}, "protocol": {"subtype": "error_max_turns"},
                      "artifact": {"trace_found": True, "changed_files": 2}})
    assert "error_max_turns" in wd.abnormal_reason(r)


@pytest.mark.parametrize("status", [m.RUN_FAILED, m.RUN_TIMEOUT, m.RUN_INTERRUPTED])
def test_bad_end_status_is_abnormal(status):
    assert wd.abnormal_reason(_run(status=status)) != ""


def test_manual_stop_is_not_retried():
    """人主动按的停止不自动重跑，否则会盖掉他停下来要改的东西。"""
    r = _run(status=m.RUN_INTERRUPTED,
             verdict={"process": {"manual_stop": True}, "protocol": {}, "artifact": {}})
    assert wd.abnormal_reason(r) == ""


def test_missing_trace_is_abnormal():
    r = _run(verdict={"process": {"exit_code": 0}, "protocol": {"subtype": "success"},
                      "artifact": {"trace_found": False, "changed_files": 5}})
    assert "轨迹" in wd.abnormal_reason(r)


def test_zero_change_with_trace_is_abnormal():
    r = _run(git_diff_stat="",
             verdict={"process": {"exit_code": 0}, "protocol": {"subtype": "success"},
                      "artifact": {"trace_found": True, "changed_files": 0}})
    assert "零改动" in wd.abnormal_reason(r)


def test_zero_change_count_but_diff_present_is_ok():
    """接管路径下 changed_files 拿不到，但 diff 有内容就说明确实干了活。"""
    r = _run(git_diff_stat="src/a.ts | 9 +++",
             verdict={"process": {"exit_code": 0}, "protocol": {"subtype": "success"},
                      "artifact": {"trace_found": True, "changed_files": 0}})
    assert wd.abnormal_reason(r) == ""


def test_running_with_dead_container_is_abnormal():
    r = _run(status=m.RUN_RUNNING, verdict={}, started_at=m.utc_now())
    assert "已经不在了" in wd.abnormal_reason(r, container_alive=False)


def test_running_with_live_container_is_fine():
    r = _run(status=m.RUN_RUNNING, verdict={}, started_at=m.utc_now())
    assert wd.abnormal_reason(r, container_alive=True) == ""


def test_just_dispatched_run_is_not_judged_by_a_missing_container():
    """出闸到容器拉起来之间有一段窗口，那会儿容器本来就不存在。

    调度先占住 RUNNING 状态，runner 校验完起跑点才真正 docker run，started_at 是在
    那之后才写的。不认这个窗口的话，每一次出闸都会被当场判成「容器没了」清掉重跑。
    """
    r = _run(status=m.RUN_RUNNING, verdict={}, started_at=None)
    assert wd.abnormal_reason(r, container_alive=False) == ""


def test_pending_run_is_not_abnormal():
    assert wd.abnormal_reason(_run(status=m.RUN_PENDING, verdict={})) == ""


# ---------------- 重跑次数 ----------------

def test_can_retry_respects_limit():
    assert wd.can_retry(_run(attempt=1), 3) is True
    assert wd.can_retry(_run(attempt=2), 3) is True
    assert wd.can_retry(_run(attempt=3), 3) is False
    assert wd.can_retry(_run(attempt=4), 3) is False


# ---------------- 轨迹归档 ----------------

def test_archive_traces_renames_nonempty_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(wd.config, "CODER_ROOT_MOUNT", tmp_path)
    tr = tmp_path / wd.config.TRACES_DIR / "07" / "A"
    tr.mkdir(parents=True)
    (tr / "a.jsonl").write_text("{}", encoding="utf-8")

    assert wd.archive_traces("07", "A")["ok"] is True
    # 原目录整体改名走了，下次跑之前 runner 会重新建一个空的
    assert not tr.exists()
    archived = list((tmp_path / wd.config.TRACES_DIR / "07").glob("A.archived-*"))
    assert len(archived) == 1
    # 归档是改名不是删除：上一次的轨迹是判「为什么异常」的唯一材料
    assert (archived[0] / "a.jsonl").exists()


def test_archive_traces_noop_when_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(wd.config, "CODER_ROOT_MOUNT", tmp_path)
    (tmp_path / wd.config.TRACES_DIR / "07" / "A").mkdir(parents=True)
    assert wd.archive_traces("07", "A")["ok"] is True


# ---------------- 重跑准备 ----------------

@pytest.fixture()
def stub_side_effects(monkeypatch, tmp_path):
    calls = {"removed": [], "reset": [], "wiped": []}

    async def remove(name):
        calls["removed"].append(name)
        return True

    async def reset(task_no, side, snapshot):
        calls["reset"].append(side)
        return {"ok": True, "mode": "reset", "message": f"{side} 已退回"}

    async def rebuild(task_no, repo_url, side, snapshot):
        calls["wiped"].append(side)
        return {"ok": True, "archived": "", "message": f"{side} 已从主干重建"}

    monkeypatch.setattr(wd.dockerx, "remove_container", remove)
    monkeypatch.setattr(wd.gsb_repo, "reset_side", reset)
    monkeypatch.setattr(wd.gsb_repo, "rebuild_side", rebuild)
    monkeypatch.setattr(wd.config, "CODER_ROOT_MOUNT", tmp_path)
    monkeypatch.setattr(wd.config, "EXPORT_DIR", tmp_path / "exports")
    return calls


def _lay_out_last_run(task_no: str = "07") -> dict:
    """铺一份上一跑留下的东西：两侧的导出轨迹与索引，加题级的分析中间产物。"""
    made = {}
    for side in ("A", "B"):
        paths = wd.config.TaskPaths(task_no, side)
        paths.export.mkdir(parents=True, exist_ok=True)
        jsonl = paths.export / f"{side.lower()}-old.jsonl"
        jsonl.write_text("{}", encoding="utf-8")
        paths.analysis.mkdir(parents=True, exist_ok=True)
        paths.trace_index.write_text('{"steps": []}', encoding="utf-8")
        made[side] = (jsonl, paths.trace_index)
    analysis = wd.config.TaskPaths(task_no).analysis
    (analysis / "gsb_prompt.md").write_text("上一跑的 prompt", encoding="utf-8")
    (analysis / "gsb_raw.txt").write_text("上一跑的原始输出", encoding="utf-8")
    made["dir"] = analysis
    return made


def test_requeue_clears_previous_result_and_events(task_with_runs, stub_side_effects):
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        run.status = m.RUN_FAILED
        run.exit_code = 1
        run.trace_file = "/x/a.jsonl"
        run.session_id = "sess-a"
        run.artifact_sha = "a" * 40
        run.error = "炸了"
        db.add(m.RunEvent(task_id=task_id, seq=1, side="A", kind="lifecycle", summary="启动"))
        db.add(m.RunEvent(task_id=task_id, seq=1, side="B", kind="lifecycle", summary="启动"))

    r = asyncio.run(wd.requeue_run(ids["A"], reason="网关 504"))
    assert r["ok"] is True
    assert r["attempt"] == 2

    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        assert run.status == m.RUN_QUEUED
        assert run.attempt == 2
        assert run.exit_code is None
        assert run.trace_file == "" and run.session_id == "" and run.error == ""
        assert run.artifact_sha == ""
        assert run.abnormal["reason"] == "网关 504"
        # 题级退回排队，让调度器重新成对出闸
        assert db.get(m.Task, task_id).status == m.QUEUED
        # 只清这一侧的事件，另一侧的时间线不能动
        assert db.query(m.RunEvent).filter(m.RunEvent.side == "A").count() == 0
        assert db.query(m.RunEvent).filter(m.RunEvent.side == "B").count() == 1


def test_requeue_clears_exported_trace_and_index(task_with_runs, stub_side_effects):
    """导出的 jsonl 和轨迹索引都是下游直接读的，留着会让质检和分析用上一跑的过程。"""
    _, ids = task_with_runs
    made = _lay_out_last_run()

    assert asyncio.run(wd.requeue_run(ids["A"], reason="超时"))["ok"] is True

    jsonl_a, index_a = made["A"]
    assert not jsonl_a.exists()
    assert not index_a.exists()
    # 另一侧没重跑，它的材料一个都不能动
    jsonl_b, index_b = made["B"]
    assert jsonl_b.exists() and index_b.exists()


def test_requeue_clears_analysis_conclusion(task_with_runs, stub_side_effects):
    """结论是两侧比出来的，一侧重跑它就作废了；不清的话上传交出去的是上一跑的结论。"""
    from app.db import session

    task_id, ids = task_with_runs
    made = _lay_out_last_run()
    with session() as db:
        t = db.get(m.Task, task_id)
        t.analysis_status = m.ANALYSIS_DONE
        t.analysis = {"model": "x", "raw": {"verdict": "A"}}
        t.gsb = {"verdict": "A", "reason": "上一跑的理由"}
        t.verify = {"overall": "pass"}
        t.gsb_qc = {"ok": True, "passed": True}

    asyncio.run(wd.requeue_run(ids["B"], reason="人工重跑"))

    with session() as db:
        t = db.get(m.Task, task_id)
        assert t.analysis_status == m.ANALYSIS_IDLE
        assert t.analysis == {} and t.gsb == {} and t.verify == {} and t.gsb_qc == {}
    assert not (made["dir"] / "gsb_prompt.md").exists()
    assert not (made["dir"] / "gsb_raw.txt").exists()


def test_requeue_drops_only_the_rerun_sides_screencast(task_with_runs, stub_side_effects):
    """录的是那一侧的产物，重跑之后得重录；另一侧的录屏还作数。"""
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        db.get(m.Task, task_id).screencast = {"A": "https://v/a.mp4", "B": "https://v/b.mp4"}

    asyncio.run(wd.requeue_run(ids["A"], reason="超时"))

    with session() as db:
        assert db.get(m.Task, task_id).screencast == {"B": "https://v/b.mp4"}


def test_requeue_lets_the_pair_be_analyzed_again(task_with_runs, stub_side_effects):
    """配对扫描只挑 analysis_status 为 IDLE 的题。不复位，两侧重跑完也等不来分析。"""
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        db.get(m.Task, task_id).analysis_status = m.ANALYSIS_DONE

    asyncio.run(wd.requeue_run(ids["A"], reason="超时"))
    with session() as db:
        for run_id in ids.values():
            run = db.get(m.TaskRun, run_id)
            run.status = m.RUN_FINISHED
            run.verdict = _run().verdict

    assert wd._pairs_ready() == [task_id]


def test_requeue_removes_container_then_rebuilds(task_with_runs, stub_side_effects):
    """默认走完全重建：销毁容器，再把这一侧从主干在初始快照上重新开一份。"""
    task_id, ids = task_with_runs
    asyncio.run(wd.requeue_run(ids["B"], reason="超时"))
    assert stub_side_effects["removed"] == ["solo-cc-07-B"]
    assert stub_side_effects["wiped"] == ["B"]
    assert stub_side_effects["reset"] == []


def test_requeue_can_fall_back_to_plain_reset(task_with_runs, stub_side_effects):
    _, ids = task_with_runs
    asyncio.run(wd.requeue_run(ids["B"], reason="超时", full=False))
    assert stub_side_effects["reset"] == ["B"]
    assert stub_side_effects["wiped"] == []


def test_requeue_stops_if_rollback_fails(task_with_runs, stub_side_effects, monkeypatch):
    """回退失败还往下走，会拿上一次的改动当起点，产物快照的父提交就对不上了。"""
    from app.db import session

    async def bad_rebuild(task_no, repo_url, side, snapshot):
        return {"ok": False, "message": "本地有冲突"}

    monkeypatch.setattr(wd.gsb_repo, "rebuild_side", bad_rebuild)
    task_id, ids = task_with_runs
    r = asyncio.run(wd.requeue_run(ids["A"], reason="超时"))
    assert r["ok"] is False
    assert "本地有冲突" in r["message"]
    with session() as db:
        assert db.get(m.TaskRun, ids["A"]).status == m.RUN_PENDING


def test_manual_rerun_resets_attempt(task_with_runs, stub_side_effects):
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).attempt = 3
        db.get(m.TaskRun, ids["B"]).attempt = 3

    r = asyncio.run(wd.manual_rerun(task_id))
    assert r["ok"] is True
    with session() as db:
        assert db.get(m.TaskRun, ids["A"]).attempt == 1
        assert db.get(m.TaskRun, ids["B"]).attempt == 1


def test_manual_rerun_one_side_only(task_with_runs, stub_side_effects):
    from app.db import session

    task_id, ids = task_with_runs
    asyncio.run(wd.manual_rerun(task_id, sides=("B",)))
    with session() as db:
        assert db.get(m.TaskRun, ids["B"]).status == m.RUN_QUEUED
        assert db.get(m.TaskRun, ids["A"]).status == m.RUN_PENDING


def test_give_up_discards_the_whole_task(task_with_runs, stub_side_effects):
    """一侧修不好，整道题就废弃：另一侧再跑也交不出去，不能让它继续占容器。"""
    from app.db import session

    task_id, ids = task_with_runs
    asyncio.run(wd.give_up(ids["A"], "网关 504 连着三次"))
    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.DISCARDED
        assert task.discarded_from == m.QUEUED      # 恢复时按它回退
        assert "504" in task.auto_error
        assert db.get(m.TaskRun, ids["A"]).abnormal["gave_up"] is True


def test_discard_stops_the_other_side_still_running(task_with_runs, stub_side_effects,
                                                    monkeypatch):
    """废弃时另一侧可能还在跑，容器要停掉，槽位立刻还给队列。"""
    from app.db import session
    from app.services import runner

    task_id, ids = task_with_runs
    stopped = []
    with session() as db:
        db.get(m.TaskRun, ids["B"]).status = m.RUN_RUNNING

    async def stop_run(rid):
        stopped.append(rid)
        return {"ok": True, "message": ""}

    monkeypatch.setattr(runner, "stop_run", stop_run)
    asyncio.run(wd.discard_task(task_id, "超时两次"))

    assert stopped == [ids["B"]]
    with session() as db:
        assert db.get(m.Task, task_id).status == m.DISCARDED
        assert db.get(m.TaskRun, ids["B"]).status == m.RUN_INTERRUPTED


# ---------------- 重跑预算 ----------------

def test_retry_budget_allows_reruns_until_the_limit():
    assert wd.discard_reason(_run(attempt=1), 3, 2) == ""
    assert wd.discard_reason(_run(attempt=2), 3, 2) == ""
    assert "上限 3" in wd.discard_reason(_run(attempt=3), 3, 2)


def test_timeouts_have_their_own_lower_limit():
    """超时一次就烧掉一整个运行超时，容忍次数比普通重跑低。"""
    assert wd.discard_reason(_run(attempt=1, timeouts=1), 3, 2) == ""
    assert "超时 2 次" in wd.discard_reason(_run(attempt=1, timeouts=2), 3, 2)


def test_requeue_counts_the_timeout_before_clearing_it(task_with_runs, stub_side_effects):
    """超时得在重跑前记一笔，不然状态一清这笔账就没了，上限永远撞不到。"""
    from app.db import session

    _task_id, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_TIMEOUT

    asyncio.run(wd.requeue_run(ids["A"], reason="超时"))
    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        assert run.timeouts == 1
        assert run.attempt == 2
        assert run.status == m.RUN_QUEUED


def test_manual_rerun_clears_the_timeout_tally(task_with_runs, stub_side_effects):
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).timeouts = 2

    asyncio.run(wd.manual_rerun(task_id, sides=("A",)))
    with session() as db:
        assert db.get(m.TaskRun, ids["A"]).timeouts == 0


def _broken_run(ids, side="A", **fields):
    """把一侧摆成「跑挂了」的样子。"""
    from app.db import session

    with session() as db:
        r = db.get(m.TaskRun, ids[side])
        r.status = m.RUN_FAILED
        r.verdict = {"process": {"exit_code": 1}, "protocol": {}, "artifact": {}}
        for k, v in fields.items():
            setattr(r, k, v)


def test_scan_discards_the_task_once_reruns_run_out(task_with_runs, stub_side_effects,
                                                    monkeypatch):
    from app.db import session

    task_id, ids = task_with_runs
    _broken_run(ids, attempt=3)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())
    monkeypatch.setattr(wd.settings_store, "get_int",
                        lambda k, d=0: {"watchdog.max_retries": 3, "watchdog.max_timeouts": 2}.get(k, d))

    asyncio.run(wd._scan_abnormal())
    with session() as db:
        assert db.get(m.Task, task_id).status == m.DISCARDED


def test_scan_discards_the_task_after_two_timeouts(task_with_runs, stub_side_effects,
                                                   monkeypatch):
    """次数还有富余，但超时已经两次 —— 先撞到哪个上限就按哪个废弃。"""
    from app.db import session

    task_id, ids = task_with_runs
    _broken_run(ids, attempt=1, timeouts=2)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())
    monkeypatch.setattr(wd.settings_store, "get_int",
                        lambda k, d=0: {"watchdog.max_retries": 3, "watchdog.max_timeouts": 2}.get(k, d))

    asyncio.run(wd._scan_abnormal())
    with session() as db:
        assert db.get(m.Task, task_id).status == m.DISCARDED
        assert "超时 2 次" in db.get(m.Task, task_id).auto_error


def test_failed_rerun_prep_waits_for_the_next_round(task_with_runs, monkeypatch):
    """重跑没准备成是环境的事，不占重跑次数，题也不该当场废弃。"""
    from app.db import session

    task_id, ids = task_with_runs
    _broken_run(ids, attempt=1)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())

    async def failing(run_id, *, reason, reset_attempt=False):
        return {"ok": False, "message": "GitHub 连不上"}

    monkeypatch.setattr(wd, "requeue_run", failing)
    asyncio.run(wd._scan_abnormal())

    with session() as db:
        assert db.get(m.Task, task_id).status == m.QUEUED
        assert db.get(m.TaskRun, ids["A"]).abnormal["prep_failures"] == 1


def test_rerun_prep_failing_over_and_over_does_discard(task_with_runs, monkeypatch):
    """但环境一直坏着也不能每五分钟空转一次，攒够次数照样废弃。"""
    from app.db import session

    task_id, ids = task_with_runs
    _broken_run(ids, attempt=1)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())

    async def failing(run_id, *, reason, reset_attempt=False):
        return {"ok": False, "message": "GitHub 连不上"}

    monkeypatch.setattr(wd, "requeue_run", failing)
    for _ in range(3):
        asyncio.run(wd._scan_abnormal())

    with session() as db:
        assert db.get(m.Task, task_id).status == m.DISCARDED


def test_scan_leaves_runs_that_still_have_a_coroutine_watching(task_with_runs, monkeypatch):
    """有协程守着的 run 不判异常，哪怕这一刻容器已经不在 running 了。

    守着的协程正等容器结束，容器一退它就收尾 —— 这里看到的「容器没了」多半就是那
    半秒钟的窗口。抢在它前面判，会把一次刚跑完、甚至跑满两小时的运行清掉重跑。
    """
    from app.db import session
    from app.services.scheduler import scheduler

    _task_id, ids = task_with_runs
    with session() as db:
        r = db.get(m.TaskRun, ids["A"])
        r.status = m.RUN_RUNNING
        r.started_at = m.utc_now()

    async def boom(*a, **kw):
        raise AssertionError("有协程守着，不该来碰它")

    monkeypatch.setattr(wd, "requeue_run", boom)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())
    monkeypatch.setitem(scheduler.running, ids["A"], object())
    try:
        asyncio.run(wd._scan_abnormal())
    finally:
        scheduler.running.pop(ids["A"], None)

    with session() as db:
        assert db.get(m.TaskRun, ids["A"]).status == m.RUN_RUNNING


# ---------------- 暂停异常处理 ----------------

def _pause_watchdog(monkeypatch, on: bool = True) -> None:
    monkeypatch.setattr(wd.settings_store, "get_bool",
                        lambda k, d=False: on if k == "watchdog.paused" else d)


def test_paused_watchdog_neither_reruns_nor_discards(task_with_runs, monkeypatch):
    """模型停机时开的开关：跑挂的题停在原地，一个动作都不做。

    重跑的动作是把这一侧连 .git 一起删掉重建。停机期间每一侧都会跑挂，照常重跑就是
    把一整批题清空，再跑满次数整题废弃 —— 而它们缺的只是一次能连上模型的重跑。
    """
    from app.db import session

    task_id, ids = task_with_runs
    _broken_run(ids, attempt=3)   # 次数已经到顶，不暂停的话这一轮就该废弃整题
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())
    _pause_watchdog(monkeypatch)

    async def boom(*a, **kw):
        raise AssertionError("异常处理已暂停，不该动手")

    monkeypatch.setattr(wd, "requeue_run", boom)
    monkeypatch.setattr(wd, "give_up", boom)

    stats = asyncio.run(wd._scan_abnormal())
    assert stats == {"requeued": 0, "discarded": 0, "held": 1}
    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status != m.DISCARDED
        run = db.get(m.TaskRun, ids["A"])
        # 状态、次数、产出记录一律不动，环境也就没人碰
        assert run.status == m.RUN_FAILED
        assert run.attempt == 3
        assert run.abnormal["held"] is True
        assert run.abnormal["reason"]


def test_paused_watchdog_still_records_why(task_with_runs, monkeypatch):
    """记一笔是为了让人看见停机期间到底哪几侧跑挂了，开关一关就照常重跑。"""
    from app.db import session

    _task_id, ids = task_with_runs
    _broken_run(ids, attempt=1)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())
    _pause_watchdog(monkeypatch)
    asyncio.run(wd._scan_abnormal())

    with session() as db:
        held = dict(db.get(m.TaskRun, ids["A"]).abnormal)
    assert held["held"] is True
    assert held["attempt"] == 1, "挂起不算一次重跑"

    # 同一个原因不反复改写：巡检每五分钟一轮，改一次就推一条事件出去
    asyncio.run(wd._scan_abnormal())
    with session() as db:
        assert dict(db.get(m.TaskRun, ids["A"]).abnormal)["at"] == held["at"]


def test_unpausing_picks_the_held_side_back_up(task_with_runs, stub_side_effects, monkeypatch):
    """开关一关，挂起的那一侧照常走完全回退重跑，挂起的记录被这一跑的记录顶掉。"""
    from app.db import session

    _task_id, ids = task_with_runs
    _broken_run(ids, attempt=1)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())
    _pause_watchdog(monkeypatch)
    asyncio.run(wd._scan_abnormal())

    _pause_watchdog(monkeypatch, on=False)
    stats = asyncio.run(wd._scan_abnormal())
    assert stats["requeued"] == 1
    assert stats["held"] == 0
    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        assert run.status == m.RUN_QUEUED
        assert run.attempt == 2
        assert "held" not in run.abnormal
    assert stub_side_effects["wiped"] == ["A"]


def test_manual_rerun_works_while_paused(task_with_runs, stub_side_effects, monkeypatch):
    """暂停只挡自动动作。人明确点的重跑照做，不然停机期间什么都动不了。"""
    from app.db import session

    task_id, ids = task_with_runs
    _pause_watchdog(monkeypatch)
    assert asyncio.run(wd.manual_rerun(task_id, sides=("A",)))["ok"] is True
    with session() as db:
        assert db.get(m.TaskRun, ids["A"]).status == m.RUN_QUEUED


def test_scan_ignores_tasks_already_out_of_the_pipeline(task_with_runs, monkeypatch):
    """已经上传或废弃的题不再每轮扫一遍，它们的 run 怎么样都不必再管。"""
    from app.db import session

    task_id, ids = task_with_runs
    _broken_run(ids, attempt=1)
    with session() as db:
        db.get(m.Task, task_id).status = m.UPLOADED
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())

    async def boom(*a, **kw):
        raise AssertionError("不该来碰这道题")

    monkeypatch.setattr(wd, "requeue_run", boom)
    asyncio.run(wd._scan_abnormal())


# ---------------- 配对推进 ----------------

def _finish_both(ids):
    from app.db import session

    with session() as db:
        for side, rid in ids.items():
            run = db.get(m.TaskRun, rid)
            run.status = m.RUN_FINISHED
            run.session_id = f"sess-{side}"
            run.trace_file = f"/x/{side}.jsonl"
            run.git_diff_stat = "src/a.ts | 3 +-"
            run.verdict = {"process": {"exit_code": 0, "gateway_errors": []},
                           "protocol": {"subtype": "success"},
                           "artifact": {"trace_found": True, "changed_files": 3}}


def test_pairs_ready_needs_both_sides_finished(task_with_runs):
    from app.db import session

    task_id, ids = task_with_runs
    assert wd._pairs_ready() == []
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_FINISHED
    assert wd._pairs_ready() == []
    _finish_both(ids)
    assert wd._pairs_ready() == [task_id]


@pytest.fixture()
def clean_advances():
    """后台推进的台账是模块级的，用例之间必须擦干净。"""
    wd._advance_tasks.clear()
    wd._advance_wanted.clear()
    yield
    for job in wd._advance_tasks.values():
        job.cancel()
    wd._advance_tasks.clear()
    wd._advance_wanted.clear()


def _ready_task(task_no: str) -> int:
    """再造一道两侧都正常跑完、等着推进的题。"""
    from app.db import session

    with session() as db:
        t = m.Task(task_no=task_no, prompt_hash=f"h-{task_no}", user_prompt="做点事",
                   status=m.QUEUED, repo_url="https://github.com/acme/widget",
                   env_snapshot="https://github.com/acme/widget/commit/" + "c" * 40)
        db.add(t)
        db.flush()
        task_id = t.id
        ids = {}
        for side in ("A", "B"):
            r = m.TaskRun(task_id=task_id, side=side,
                          container_name=f"solo-cc-{task_no}-{side}")
            db.add(r)
            db.flush()
            ids[side] = r.id
    _finish_both(ids)
    return task_id


def test_scan_pairs_hands_the_advance_to_the_background(task_with_runs, monkeypatch,
                                                        clean_advances):
    """推进不能在巡检循环里等它跑完。

    推进要跑 GSB 分析和质检，两个都在调模型，一道题十几二十分钟是常态，模型不返回时
    还要按 llm 的重试次数再乘一遍。而补记账、异常重跑跟配对在同一轮 tick 里，等它就
    等于整套定时任务停摆：容器照常跑，跑挂的没人重跑，跑完的也没人配对。
    """
    task_id, ids = task_with_runs
    _finish_both(ids)

    async def main():
        gate = asyncio.Event()

        async def slow(tid):
            await gate.wait()
            return {"ok": True}

        monkeypatch.setattr(wd, "advance_pair", slow)
        # 推进还卡在模型上，这一轮扫描必须已经回来了
        assert await asyncio.wait_for(wd._scan_pairs(), timeout=2) == 1
        assert task_id in wd._advance_tasks
        gate.set()
        await wd._advance_tasks[task_id]

    asyncio.run(main())


def test_scan_pairs_stops_at_the_concurrency_limit(task_with_runs, monkeypatch,
                                                   clean_advances):
    """并发额度就是设置里那个「分析/质检并发」，两步都在调模型，开太多互相拖慢。"""
    from app.services import settings_store

    task_id, ids = task_with_runs
    _finish_both(ids)
    _ready_task("08")
    settings_store.set_one("auto.max_parallel", "1")
    assert len(wd._pairs_ready()) == 2

    async def main():
        gate = asyncio.Event()

        async def slow(tid):
            await gate.wait()
            return {"ok": True}

        monkeypatch.setattr(wd, "advance_pair", slow)
        # 包一层超时：推进一旦变回在扫描里直接 await，这里会卡到天荒地老而不是报错
        assert await asyncio.wait_for(wd._scan_pairs(), timeout=2) == 1
        # 额度占满，第二道留到下一轮：它的状态没变，扫描照样挑得到
        assert await asyncio.wait_for(wd._scan_pairs(), timeout=2) == 0
        assert len(wd._advance_tasks) == 1
        gate.set()
        for job in list(wd._advance_tasks.values()):
            await job

    asyncio.run(main())


def test_queue_advance_starts_once_and_reports_the_second_click(task_with_runs, monkeypatch,
                                                               clean_advances):
    """同一道题点两次只跑一次，第二次照原话告诉人它已经在推进了。

    推同一个分支的两条 push 里落后的那条会被远端拒掉，接着它把「push 失败」写进
    auto_error，盖掉另一条已经成功的事实 —— 产物明明推上去了，界面上却挂着一句假报错。
    """
    task_id, ids = task_with_runs
    _finish_both(ids)

    async def main():
        gate = asyncio.Event()
        started = []

        async def slow(tid):
            started.append(tid)
            await gate.wait()
            return {"ok": True}

        monkeypatch.setattr(wd, "advance_pair", slow)

        first = wd.queue_advance(task_id)
        assert first["started"] is True
        await asyncio.sleep(0.01)

        second = wd.queue_advance(task_id)
        assert second["started"] is False
        assert "正在推进" in second["message"]
        assert started == [task_id]

        gate.set()
        for job in list(wd._advance_tasks.values()):
            await job

    asyncio.run(main())


def test_manual_advance_goes_in_before_the_ones_the_scan_found(task_with_runs, monkeypatch,
                                                               clean_advances):
    """额度满了，人工点的那道要留在队列里等，而且比扫描自己捡到的先走。

    当场丢掉是最坏的做法：人工点的这批里有需人工、有分析失败过的题，配对扫描一律够不着，
    于是那几道永远没动静，人只会觉得按钮点了没反应。
    """
    from app.services import settings_store

    task_id, ids = task_with_runs          # 07：扫描能挑到的那道
    other = _ready_task("08")              # 08：人工点的那道
    settings_store.set_one("auto.max_parallel", "1")

    async def main():
        gate = asyncio.Event()
        started = []

        async def slow(tid):
            started.append(tid)
            await gate.wait()
            return {"ok": True}

        monkeypatch.setattr(wd, "advance_pair", slow)
        # 拿一个不相干的 job 占满那唯一的额度，好让人工点的那道只能排队
        hold = asyncio.create_task(gate.wait())
        wd._advance_tasks[-1] = hold

        queued = wd.queue_advance(other)
        assert queued["started"] is False
        assert "等额度" in queued["message"]
        assert wd._advance_wanted == [other]
        # 额度还是满的，这一轮谁都起不来，但队列得留着
        assert await asyncio.wait_for(wd._scan_pairs(), timeout=2) == 0
        assert wd._advance_wanted == [other]

        wd._advance_tasks.pop(-1)
        assert await asyncio.wait_for(wd._scan_pairs(), timeout=2) == 1
        await asyncio.sleep(0.01)
        assert started == [other], "人工排的队该先走，扫描捡到的 07 再等一轮"
        assert wd._advance_wanted == []

        gate.set()
        for job in list(wd._advance_tasks.values()):
            await job
        await hold

    asyncio.run(main())


def test_a_stale_analysis_is_reset_so_the_pair_can_be_picked_up(task_with_runs):
    """进程没了，库里那个「分析中」还留着。

    analysis_status 记的是一个协程在不在跑，而协程随进程一起没了。配对扫描只挑 IDLE
    的题，不复位就谁也不会再碰它：界面上永远显示分析中，人只能挨个去点重新分析。
    """
    from app.db import session

    task_id, ids = task_with_runs
    _finish_both(ids)
    with session() as db:
        t = db.get(m.Task, task_id)
        t.status = m.ANALYZING
        t.analysis_status = m.ANALYSIS_RUNNING

    assert wd._pairs_ready() == []          # 卡住的时候扫描够不着它
    assert wd.reset_stale_analyses() == ["07"]
    assert wd._pairs_ready() == [task_id]


# ---------------- 收养孤儿 ----------------

@pytest.fixture()
def stub_container(monkeypatch):
    """让 watchdog 看到一个指定状态的容器，并记录有没有去收尾。"""
    seen = {"finalized": []}
    state = {"value": "exited", "code": 0}

    async def container_state(name):
        return state["value"]

    async def container_exit_code(name):
        return state["code"]

    async def finalize(run_id, **kw):
        seen["finalized"].append((run_id, kw))

    monkeypatch.setattr(wd.dockerx, "container_state", container_state)
    monkeypatch.setattr(wd.dockerx, "container_exit_code", container_exit_code)
    from app.services import runner

    monkeypatch.setattr(runner, "finalize", finalize)
    return seen, state


def test_orphan_run_with_exited_container_is_finalized(task_with_runs, stub_container):
    """容器跑完退出了、协程却没了的 run，要补记账而不是判异常。

    这一侧退出码是 0、轨迹也落盘了，是一次跑完的运行，只是没人记账。按「容器不见了」
    判异常会把它整个清掉重跑，一个多小时的结果就白跑了。
    """
    from app.db import session

    seen, _ = stub_container
    _, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_RUNNING
    asyncio.run(wd._scan_orphans())
    assert [r for r, _ in seen["finalized"]] == [ids["A"]]
    assert seen["finalized"][0][1]["exit_code"] == 0
    assert seen["finalized"][0][1]["container_gone"] is False


def test_orphan_scan_leaves_live_containers_alone(task_with_runs, stub_container):
    from app.db import session

    seen, state = stub_container
    state["value"] = "running"
    _, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_RUNNING
    asyncio.run(wd._scan_orphans())
    assert seen["finalized"] == []


def test_orphan_scan_reports_a_vanished_container_as_such(task_with_runs, stub_container):
    """容器连记录都没了，如实报「容器没了」，不要替人认下「我按的停止」。

    认成人工停止的话，abnormal_reason 会直接放行（人工停止不自动重跑），
    而这一侧又不是 FINISHED，配对扫描也不管 —— 题目就此永久卡死。
    """
    from app.db import session

    seen, state = stub_container
    state["value"] = ""
    _, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_RUNNING
    asyncio.run(wd._scan_orphans())
    assert seen["finalized"][0][1]["container_gone"] is True
    assert "manual_stop" not in seen["finalized"][0][1]


def test_orphan_scan_skips_runs_the_scheduler_still_watches(task_with_runs, stub_container,
                                                            monkeypatch):
    """还有协程守着的不插手，否则会和 runner 抢着收尾，记两遍账。"""
    from app.db import session
    from app.services.scheduler import scheduler

    seen, _ = stub_container
    _, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_RUNNING
    monkeypatch.setitem(scheduler.running, ids["A"], object())
    asyncio.run(wd._scan_orphans())
    assert seen["finalized"] == []


def test_scan_abnormal_never_opens_a_nested_session(task_with_runs, monkeypatch):
    """巡检里不许在已开的会话中再开一条连接。

    settings_store 每次取值都会自己开会话。以前 can_retry 就是在 with session() 里被
    调用的，于是每轮巡检都要在已有事务中新建连接，而库文件在 Docker Desktop 的
    bind mount 上，第二条连接跑 PRAGMA journal_mode=WAL 会抛 disk I/O error。
    结果是定时任务每 5 分钟静静地挂一次：异常不处理、配对不推进，线上整整一小时
    没有推进任何一道题，日志里只有一条看不懂的磁盘报错。
    """
    from contextlib import contextmanager

    from app import db as db_mod
    from app.services import settings_store

    real = db_mod.session
    depth = {"now": 0, "max": 0}

    @contextmanager
    def counting_session():
        depth["now"] += 1
        depth["max"] = max(depth["max"], depth["now"])
        try:
            with real() as s:
                yield s
        finally:
            depth["now"] -= 1

    monkeypatch.setattr(wd, "session", counting_session)
    monkeypatch.setattr(settings_store, "session", counting_session)

    _, ids = task_with_runs
    _finish_both(ids)
    asyncio.run(wd._scan_abnormal())
    assert depth["max"] == 1, f"巡检里出现了嵌套会话，最深 {depth['max']} 层"


def test_pairs_ready_skips_abnormal_side(task_with_runs):
    from app.db import session

    task_id, ids = task_with_runs
    _finish_both(ids)
    with session() as db:
        run = db.get(m.TaskRun, ids["B"])
        run.verdict = {"process": {"exit_code": 1},
                       "protocol": {"subtype": "success"},
                       "artifact": {"trace_found": True, "changed_files": 1}}
    assert wd._pairs_ready() == []


def test_pairs_ready_skips_already_analyzed(task_with_runs):
    from app.db import session

    task_id, ids = task_with_runs
    _finish_both(ids)
    with session() as db:
        db.get(m.Task, task_id).analysis_status = m.ANALYSIS_DONE
    assert wd._pairs_ready() == []


def test_push_artifacts_fills_snapshot_for_both_sides(task_with_runs, monkeypatch):
    from app.db import session

    task_id, ids = task_with_runs
    _finish_both(ids)
    seen = []

    async def push(task_no, repo_url, side, snapshot, *, message):
        seen.append((side, message))
        return {"ok": True, "sha": side.lower() * 40,
                "url": f"https://github.com/acme/widget/commit/{side.lower() * 40}"}

    monkeypatch.setattr(wd.gsb_repo, "commit_and_push", push)
    r = asyncio.run(wd.push_artifacts(task_id))
    assert r["ok"] is True
    assert [s for s, _ in seen] == ["A", "B"]
    # 提交信息里要带 SessionID，平台核对产物与轨迹靠它
    assert "sess-A" in seen[0][1]
    with session() as db:
        assert db.get(m.TaskRun, ids["A"]).artifact_sha == "a" * 40
        assert db.get(m.TaskRun, ids["B"]).artifact_url.endswith("b" * 40)


def test_push_artifacts_skips_sides_already_pushed(task_with_runs, monkeypatch):
    from app.db import session

    task_id, ids = task_with_runs
    _finish_both(ids)
    with session() as db:
        db.get(m.TaskRun, ids["A"]).artifact_sha = "a" * 40
    seen = []

    async def push(task_no, repo_url, side, snapshot, *, message):
        seen.append(side)
        return {"ok": True, "sha": "b" * 40, "url": "u"}

    monkeypatch.setattr(wd.gsb_repo, "commit_and_push", push)
    asyncio.run(wd.push_artifacts(task_id))
    assert seen == ["B"]


def test_push_artifacts_clears_stale_failure_note(task_with_runs, monkeypatch):
    """上一轮失败留下的那句话，推成功之后要擦掉。

    不擦的话产物早就推上去了、分析也跑完了，界面上还挂着「push 失败，检查 Token
    写权限」，人只会跑去翻权限设置，而实际上什么都不用做。
    """
    from app.db import session

    task_id, ids = task_with_runs
    _finish_both(ids)
    with session() as db:
        db.get(m.Task, task_id).auto_error = "B 侧推送失败：原因不明，检查网络与 Token 的 repo 写权限"

    async def push(task_no, repo_url, side, snapshot, *, message):
        return {"ok": True, "sha": side.lower() * 40, "url": "u"}

    monkeypatch.setattr(wd.gsb_repo, "commit_and_push", push)
    assert asyncio.run(wd.push_artifacts(task_id))["ok"] is True
    with session() as db:
        assert db.get(m.Task, task_id).auto_error == ""


def test_advance_pair_rejects_reentry_while_running(task_with_runs, monkeypatch):
    """巡检和界面上那个「提交产物并分析」撞在一起时，后来的那个要被挡回去。

    不挡的话两边各推一遍产物：推同一个分支的两条 push 里落后的那条被远端拒掉，
    接着它把「push 失败」写进 auto_error，盖掉另一条已经成功的事实。
    """
    task_id, ids = task_with_runs
    _finish_both(ids)
    calls = []
    second = {}

    async def push(tid):
        # 第一次推送还没回来时插一次调用，模拟人正好在这几秒里点了按钮
        calls.append(tid)
        second.update(await wd.advance_pair(tid))
        return {"ok": False, "message": "先不往下走"}

    async def remove(name):
        return True

    monkeypatch.setattr(wd, "push_artifacts", push)
    monkeypatch.setattr(wd.dockerx, "remove_container", remove)
    asyncio.run(wd.advance_pair(task_id))

    assert calls == [task_id]        # 推送只跑了一遍，没有第二次推同一个分支
    assert second["ok"] is False
    assert "正在推进" in second["message"]
    # 挡回去之后标记要清掉，否则这道题以后再也推不动
    assert task_id not in wd._advancing


def test_push_failure_does_not_count_as_retry(task_with_runs, monkeypatch):
    """推送失败是我这边的事，不是模型的事，不能吃掉重跑次数。"""
    from app.db import session

    task_id, ids = task_with_runs
    _finish_both(ids)

    async def push(task_no, repo_url, side, snapshot, *, message):
        return {"ok": False, "message": "远端拒绝"}

    async def remove(name):
        return True

    monkeypatch.setattr(wd.gsb_repo, "commit_and_push", push)
    monkeypatch.setattr(wd.dockerx, "remove_container", remove)
    r = asyncio.run(wd.advance_pair(task_id))
    assert r["ok"] is False
    with session() as db:
        assert db.get(m.TaskRun, ids["A"]).attempt == 1
        assert "远端拒绝" in db.get(m.Task, task_id).auto_error
        # 停在 RUN_DONE 等下一轮再试，不是转人工
        assert db.get(m.Task, task_id).status == m.RUN_DONE


def test_advance_pair_keeps_container_when_trace_missing(task_with_runs, monkeypatch):
    """轨迹没导出成功就留着容器，让人工进去捞，别把唯一的材料删了。"""
    from app.db import session

    task_id, ids = task_with_runs
    _finish_both(ids)
    with session() as db:
        db.get(m.TaskRun, ids["A"]).trace_file = ""
    removed = []

    async def remove(name):
        removed.append(name)
        return True

    async def push(task_no, repo_url, side, snapshot, *, message):
        return {"ok": False, "message": "先不推"}

    monkeypatch.setattr(wd.dockerx, "remove_container", remove)
    monkeypatch.setattr(wd.gsb_repo, "commit_and_push", push)
    asyncio.run(wd.advance_pair(task_id))
    assert removed == ["solo-cc-07-B"]


# ---------------- 质检结论折成给人看的一句话 ----------------

def test_qc_note_is_empty_when_passed():
    """通过时要把上一轮的报错清掉，不能留着旧结论误导人。"""
    assert wd._qc_note({"ok": True, "passed": True, "summary": "全部通过"}) == ""


def test_qc_note_separates_platform_failure_from_rejection():
    """质检压根没跑成，和这道题被打回，是两件事。"""
    note = wd._qc_note({"ok": False, "error": "查重池连不上"})
    assert "质检未完成" in note and "查重池连不上" in note


def test_incomplete_conclusion_tells_people_to_rerun_not_to_fix():
    """INCOMPLETE 是平台侧没跑完，让人去改理由就是白费工。"""
    note = wd._qc_note({
        "ok": True, "passed": False, "incomplete": True,
        "conclusion": "INCOMPLETE", "summary": "分支与起跑点未能核验",
    })
    assert "重跑" in note
    assert "打回" not in note and "废弃" not in note


def test_qc_note_carries_the_rule_that_was_hit():
    note = wd._qc_note({
        "ok": True, "passed": False, "conclusion": "REJECT",
        "hit_rule": "T4", "hit_rule_label": "轨迹规则 T4 · 上传了多份轨迹文件",
        "summary": "A 侧传了 2 个文件",
    })
    assert "打回" in note and "T4" in note and "A 侧传了 2 个文件" in note


def test_discard_and_reject_are_worded_differently():
    """废弃是这条数据作废，打回是改完再交，两者的下一步动作不同。"""
    common = {"ok": True, "passed": False, "summary": "题面与已有数据重复"}
    discard = wd._qc_note({**common, "conclusion": "DISCARD"})
    reject = wd._qc_note({**common, "conclusion": "REJECT"})
    assert "废弃" in discard
    assert "打回" in reject


# ---------------- 容器没了 ≠ 人按了停止 ----------------

def test_vanished_container_with_trace_counts_as_finished():
    """advance_pair 推进成功后会主动销毁容器，容器没了不代表这次跑坏了。"""
    from app.services import runner

    status, adopted = runner.decide_status(
        timed_out=False, manual_stop=False, result_event={},
        exit_code=None, has_trace=True, container_gone=True)
    assert status == m.RUN_FINISHED
    assert adopted is True


def test_vanished_container_without_trace_is_still_interrupted():
    """没轨迹就没有跑过的证据，这种才是真的断了。"""
    from app.services import runner

    status, _ = runner.decide_status(
        timed_out=False, manual_stop=False, result_event={},
        exit_code=None, has_trace=False, container_gone=True)
    assert status == m.RUN_INTERRUPTED


def test_explicit_stop_still_wins_over_trace():
    """人按的停止是事实不是推断，有轨迹也照样算中断。"""
    from app.services import runner

    status, _ = runner.decide_status(
        timed_out=False, manual_stop=True, result_event={},
        exit_code=None, has_trace=True, container_gone=True)
    assert status == m.RUN_INTERRUPTED


def test_vanished_container_does_not_get_the_manual_stop_pass():
    """这是那次死锁的回归测试。

    容器没了被记成 manual_stop 时，abnormal_reason 会直接放行（人工停止不自动重跑），
    而这一侧又不是 FINISHED，配对扫描同样不管它 —— 两边都不接手，题目永久卡死。
    """
    run = m.TaskRun(side="A", status=m.RUN_INTERRUPTED, attempt=1,
                    container_name="solo-cc-07-A")
    run.verdict = {"process": {"manual_stop": False, "exit_code": None}}
    assert wd.abnormal_reason(run) != ""


# ---------------- 「零改动」下手前要复核 ----------------

def _exited(*_a, **_kw):
    async def go(*a, **k):
        return "exited"
    return go


def _zero_change_run(ids, side="A"):
    from app.db import session

    with session() as db:
        r = db.get(m.TaskRun, ids[side])
        r.status = m.RUN_FINISHED
        r.git_diff_stat = ""
        r.verdict = {"process": {"exit_code": 0}, "protocol": {"subtype": "success"},
                     "artifact": {"trace_found": True, "changed_files": 0}}


def test_zero_change_is_rechecked_before_a_rerun(task_with_runs, monkeypatch):
    """收尾读到的零改动可能是假的，清掉重跑之前要实测一次。

    两种假法：产物已 commit（工作区自然干净），或容器刚退、文件还没同步过来。
    不复核就会把一次做满了活的运行整个清掉重跑。
    """
    from app.db import session

    _, ids = task_with_runs
    _zero_change_run(ids)
    requeued = []

    async def measure(ws, base_sha="", *, settle=False):
        return 7, "src/a.ts | 3 +-"

    async def requeue(run_id, *, reason, reset_attempt=False):
        requeued.append(run_id)
        return {"ok": True, "message": ""}

    from app.services import runner
    monkeypatch.setattr(runner, "workspace_output", measure)
    monkeypatch.setattr(wd, "requeue_run", requeue)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())

    asyncio.run(wd._scan_abnormal())

    assert requeued == []
    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        assert run.verdict["artifact"]["changed_files"] == 7
        assert run.git_diff_stat == "src/a.ts | 3 +-"


def test_really_empty_run_still_gets_requeued(task_with_runs, monkeypatch):
    """复核确认真的什么都没有，该重跑还是要重跑。"""
    _, ids = task_with_runs
    _zero_change_run(ids)
    requeued = []

    async def measure(ws, base_sha="", *, settle=False):
        return 0, ""

    async def requeue(run_id, *, reason, reset_attempt=False):
        requeued.append(run_id)
        return {"ok": True, "message": ""}

    from app.services import runner
    monkeypatch.setattr(runner, "workspace_output", measure)
    monkeypatch.setattr(wd, "requeue_run", requeue)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())

    asyncio.run(wd._scan_abnormal())
    assert requeued == [ids["A"]]


def test_revoked_misjudgement_puts_the_task_back_in_the_flow(task_with_runs, monkeypatch):
    """异常是我们自己判错的，撤销之后要把题从「需人工」放回去。

    配对扫描够不着 NEEDS_ATTENTION 的题。撤销了判定却不开门，这道题就谁也不碰了：
    异常已经不成立，配对又轮不到它，看上去就是看护彻底失灵。
    """
    from app.db import session

    task_id, ids = task_with_runs
    _zero_change_run(ids)
    with session() as db:
        db.get(m.TaskRun, ids["B"]).status = m.RUN_FINISHED
        db.get(m.TaskRun, ids["B"]).verdict = {
            "process": {"exit_code": 0}, "protocol": {"subtype": "success"},
            "artifact": {"trace_found": True, "changed_files": 4}}
        db.get(m.TaskRun, ids["B"]).git_diff_stat = "src/b.ts | 1 +"
        db.get(m.Task, task_id).status = m.NEEDS_ATTENTION
        db.get(m.Task, task_id).auto_error = "工作目录零改动，疑似戛然而止"

    async def measure(ws, base_sha="", *, settle=False):
        return 6, "src/a.ts | 3 +-"

    from app.services import runner
    monkeypatch.setattr(runner, "workspace_output", measure)
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())

    asyncio.run(wd._scan_abnormal())

    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.RUN_DONE
        assert task.auto_error == ""


def test_other_reasons_for_attention_are_left_to_people(task_with_runs, monkeypatch):
    """另一侧还有真异常时不能放回去，那不是误判。"""
    from app.db import session

    task_id, ids = task_with_runs
    _zero_change_run(ids)
    with session() as db:
        db.get(m.TaskRun, ids["B"]).status = m.RUN_FAILED
        db.get(m.TaskRun, ids["B"]).verdict = {"process": {"exit_code": 1}}
        db.get(m.Task, task_id).status = m.NEEDS_ATTENTION

    async def measure(ws, base_sha="", *, settle=False):
        return 6, "src/a.ts | 3 +-"

    from app.services import runner
    monkeypatch.setattr(runner, "workspace_output", measure)
    monkeypatch.setattr(wd, "requeue_run", _noop_requeue())
    monkeypatch.setattr(wd.dockerx, "container_state", _exited())

    asyncio.run(wd._scan_abnormal())

    with session() as db:
        assert db.get(m.Task, task_id).status == m.NEEDS_ATTENTION


def _noop_requeue():
    async def go(run_id, *, reason, reset_attempt=False):
        return {"ok": True, "message": ""}
    return go


def _stopped_by_hand(db, run_id: int) -> None:
    r = db.get(m.TaskRun, run_id)
    r.status = m.RUN_INTERRUPTED
    r.exit_code = 143
    r.verdict = {"process": {"exit_code": 143, "manual_stop": True}, "protocol": {}, "artifact": {}}


def test_a_pair_waiting_for_the_analysis_quota_stops_showing_as_running(task_with_runs,
                                                                       clean_advances):
    """两侧都正常跑完、只是在排队等分析额度的题，不能还挂着「运行中」。

    题级状态推不出「两侧都结束」这一种，而写 RUN_DONE 的只有 advance_pair，它排在额度
    后面。额度默认 2、一道题的分析加质检十几二十分钟，跑完的题一多后面就得排队；排队
    这一路上容器早已 Exited、产物也齐了，界面上却一直是「运行中」，看上去像是连巡检都
    刷不过来。所以状态不跟着额度走，推进照旧排队。
    """
    from app.db import session
    from app.services import settings_store

    task_id, ids = task_with_runs
    _finish_both(ids)
    ended = m.utc_now()
    with session() as db:
        db.get(m.Task, task_id).status = m.RUNNING
        db.get(m.TaskRun, ids["A"]).finished_at = ended - timedelta(minutes=14)
        db.get(m.TaskRun, ids["B"]).finished_at = ended
    settings_store.set_one("auto.max_parallel", "1")

    async def main():
        gate = asyncio.Event()
        wd._advance_tasks[-1] = asyncio.create_task(gate.wait())  # 唯一那个额度占满
        try:
            return await wd.tick()
        finally:
            gate.set()

    stats = asyncio.run(main())
    assert stats["run_done"] == 1
    assert stats["advanced"] == 0

    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.RUN_DONE
        # 结束时刻取两侧较晚的那个，不是扫到它的此刻：列表按它排序、今日产出也数它
        assert m.as_utc(task.finished_at) == ended
    # 换了状态不等于放过了它：额度一空照样该推进
    assert wd._pairs_ready() == [task_id]


def test_a_task_stopped_by_hand_leaves_running_and_waits_for_people(task_with_runs):
    """人按了停止、两侧容器都 Exited 了，题不能还挂着「运行中」。

    题级状态从两侧 run 推：两侧都结束就推不出来，交给巡检。巡检对人工停止的 run 是
    「不碰」，异常扫描放行、配对扫描又只认两侧 FINISHED —— 两头都不管，题就永远停在
    RUNNING，界面上连「废弃」都点不了。这一步把它转成「需人工」，让人自己决定重跑还是废弃。
    """
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        for side in ("A", "B"):
            _stopped_by_hand(db, ids[side])
        db.get(m.Task, task_id).status = m.RUNNING

    assert asyncio.run(wd.tick())["settled"] == 1

    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.NEEDS_ATTENTION
        assert "A、B 侧被人工停止" in task.auto_error
        assert task.finished_at is not None


def test_one_side_stopped_by_hand_after_the_other_finished_also_waits_for_people(task_with_runs):
    """A 正常跑完、B 被人停掉：配对凑不齐，也不算异常，同样得转人工并点名 B 侧。"""
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        a = db.get(m.TaskRun, ids["A"])
        a.status = m.RUN_FINISHED
        a.git_diff_stat = "src/a.ts | 3 +-"
        a.verdict = {"process": {"exit_code": 0}, "protocol": {"subtype": "success"},
                     "artifact": {"trace_found": True, "changed_files": 3}}
        _stopped_by_hand(db, ids["B"])
        db.get(m.Task, task_id).status = m.RUNNING

    assert wd._settle_stopped() == 1

    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.NEEDS_ATTENTION
        assert task.auto_error.startswith("B 侧被人工停止")
        assert "重跑这一侧" in task.auto_error


def test_settling_stopped_tasks_does_not_touch_tasks_still_in_flight(task_with_runs):
    """一侧还在跑、或一侧是真异常等着重跑的题，都不是这一步该碰的。"""
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        _stopped_by_hand(db, ids["A"])
        db.get(m.TaskRun, ids["B"]).status = m.RUN_RUNNING
        db.get(m.Task, task_id).status = m.RUNNING
    assert wd._settle_stopped() == 0

    with session() as db:
        b = db.get(m.TaskRun, ids["B"])
        b.status = m.RUN_FAILED
        b.verdict = {"process": {"exit_code": 1}, "protocol": {}, "artifact": {}}
    assert wd._settle_stopped() == 0

    with session() as db:
        assert db.get(m.Task, task_id).status == m.RUNNING


def test_settling_ignores_tasks_that_have_left_the_running_phase(task_with_runs):
    """废弃时也会把没跑完的 run 标成 INTERRUPTED，但那道题已经不在运行阶段，不能被拽回「需人工」。"""
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        for side in ("A", "B"):
            _stopped_by_hand(db, ids[side])
        db.get(m.Task, task_id).status = m.DISCARDED

    assert wd._settle_stopped() == 0
    with session() as db:
        assert db.get(m.Task, task_id).status == m.DISCARDED


def test_stale_abnormal_record_is_cleared_once_it_no_longer_holds(task_with_runs, monkeypatch):
    """异常不成立了就要把记录抹掉，否则题永远出不了「需人工」。

    这一侧的 changed_files 已经被复核补正，abnormal_reason 早就返回空了，
    但 run 上还挂着上一轮那条过期的异常。不清掉的话，扫描每轮都直接跳过它，
    而配对扫描又不看「需人工」的题 —— 两头都够不着，这道题就死在那儿了。
    """
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        for side in ("A", "B"):
            r = db.get(m.TaskRun, ids[side])
            r.status = m.RUN_FINISHED
            r.git_diff_stat = "src/x.ts | 2 +-"
            r.verdict = {"process": {"exit_code": 0}, "protocol": {"subtype": "success"},
                         "artifact": {"trace_found": True, "changed_files": 5}}
        db.get(m.TaskRun, ids["A"]).abnormal = {"reason": "工作目录零改动，疑似戛然而止",
                                                "attempt": 1}
        db.get(m.Task, task_id).status = m.NEEDS_ATTENTION
        db.get(m.Task, task_id).auto_error = "A 侧重跑 1 次仍异常"

    monkeypatch.setattr(wd.dockerx, "container_state", _exited())
    asyncio.run(wd._scan_abnormal())

    with session() as db:
        assert db.get(m.TaskRun, ids["A"]).abnormal == {}
        task = db.get(m.Task, task_id)
        assert task.status == m.RUN_DONE
        assert task.auto_error == ""


def test_a_new_key_puts_failed_analyses_back_in_the_flow(task_with_runs):
    """换 Key 是「凭据修好了」的动作，挂在凭据上的分析该自己接着跑。

    不这么做，人换完 Key 还得回头挨个点一遍重新分析 —— 而这正是这条流水线想省掉的事。
    """
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        for side in ("A", "B"):
            r = db.get(m.TaskRun, ids[side])
            r.status = m.RUN_FINISHED
            r.git_diff_stat = "src/x.ts | 2 +-"
            r.verdict = {"process": {"exit_code": 0}, "protocol": {"subtype": "success"},
                         "artifact": {"trace_found": True, "changed_files": 5}}
        t = db.get(m.Task, task_id)
        t.status, t.analysis_status = m.NEEDS_ATTENTION, m.ANALYSIS_FAILED
        t.auto_error = "GSB 分析失败：Cursor API Key 无效或已撤销"

    assert wd.retry_failed_analyses() == ["07"]

    with session() as db:
        t = db.get(m.Task, task_id)
        assert t.status == m.RUN_DONE
        assert t.analysis_status == m.ANALYSIS_IDLE
        assert t.auto_error == ""


def test_a_new_key_does_not_revive_a_half_finished_task(task_with_runs):
    """一侧还没跑完的题不能因为换了 Key 就被拖进分析。"""
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_FINISHED
        db.get(m.TaskRun, ids["B"]).status = m.RUN_FAILED
        db.get(m.Task, task_id).analysis_status = m.ANALYSIS_FAILED
        db.get(m.Task, task_id).status = m.NEEDS_ATTENTION

    assert wd.retry_failed_analyses() == []
    with session() as db:
        assert db.get(m.Task, task_id).status == m.NEEDS_ATTENTION


def test_a_broken_side_never_gets_its_work_pushed(task_with_runs, monkeypatch):
    """跑挂的那一侧不能提交产物，界面上那个直连的按钮也不行。

    推上去的是一份没跑完的东西，拿它做对比就是拿半截结果当结论；远端一旦有了这个提交，
    重跑时还得先把分支退回去。这一侧该走的是重建重跑。
    """
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        db.get(m.TaskRun, ids["A"]).status = m.RUN_FINISHED
        db.get(m.TaskRun, ids["A"]).verdict = {
            "process": {"exit_code": 0}, "protocol": {"subtype": "success"},
            "artifact": {"trace_found": True, "changed_files": 3}}
        db.get(m.TaskRun, ids["A"]).git_diff_stat = "src/a.ts | 3 +-"
        db.get(m.TaskRun, ids["B"]).status = m.RUN_INTERRUPTED

    pushed = []
    monkeypatch.setattr(wd, "push_artifacts", lambda tid: pushed.append(tid))

    r = asyncio.run(wd.advance_pair(task_id))

    assert r["ok"] is False
    assert "B 侧" in r["message"]
    assert pushed == []


def test_a_side_flagged_abnormal_is_blocked_too(task_with_runs, monkeypatch):
    """状态是 FINISHED 但被判过异常的，同样不能推。"""
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        for side in ("A", "B"):
            r = db.get(m.TaskRun, ids[side])
            r.status = m.RUN_FINISHED
            r.git_diff_stat = "src/x.ts | 1 +"
            r.verdict = {"process": {"exit_code": 0}, "protocol": {"subtype": "success"},
                         "artifact": {"trace_found": True, "changed_files": 2}}
        # 轨迹都没落盘，abnormal_reason 会认出来
        db.get(m.TaskRun, ids["A"]).verdict = {
            "process": {"exit_code": 0}, "protocol": {"subtype": "success"},
            "artifact": {"trace_found": False, "changed_files": 2}}

    pushed = []
    monkeypatch.setattr(wd, "push_artifacts", lambda tid: pushed.append(tid))

    r = asyncio.run(wd.advance_pair(task_id))
    assert r["ok"] is False
    assert "A 侧" in r["message"]
    assert pushed == []


# ---------------- 质检闸门的次序 ----------------

def test_quality_gate_checks_facts_then_wording_then_verifies(tmp_db, monkeypatch):
    """两道质检都会整段换掉理由，所以都必须排在核验与平台质检之前，而且事实在前。

    事实必须先定下来：先把话说对，再把话说顺。反过来的话，措辞那一版打磨的是一段
    事实还错着的话，事实核验接着又把它改一遍，前一次打磨白做，改完也没人再看措辞。

    后两道排在最后，是因为它们读到的必须是最终要提交的那一段 —— 读的要是改之前那一稿，
    核验过了也说明不了提交的那一份合规。
    """
    from app.db import session
    from app.services import gsb_factcheck, gsb_precheck, gsb_verifier, qa_bridge

    with session() as db:
        t = m.Task(task_no="07", prompt_hash="h", user_prompt="p", status=m.ANALYZED)
        t.gsb = {"verdict": "A", "reason": "A 侧改对了，B 侧没有。"}
        db.add(t)
        db.flush()
        tid = t.id

    order: list[str] = []

    async def fake_factcheck(task_id, **kw):
        order.append("factcheck")
        return {"ok": True, "applied": True, "mismatches": 1}

    async def fake_precheck(task_id, **kw):
        order.append("precheck")
        return {"ok": True, "applied": True}

    async def fake_verify(task_id):
        order.append("verify")
        return {"overall": "ok", "items": []}

    async def fake_qc(task_id):
        order.append("qc")
        return {"ok": True, "passed": True, "summary": ""}

    monkeypatch.setattr(gsb_factcheck, "run_factcheck", fake_factcheck)
    monkeypatch.setattr(gsb_precheck, "run_precheck", fake_precheck)
    monkeypatch.setattr(gsb_verifier, "run_verify", fake_verify)
    monkeypatch.setattr(qa_bridge, "gsb_qc", fake_qc)

    out = asyncio.run(wd.run_quality_gate(tid))
    assert order == ["factcheck", "precheck", "verify", "qc"]
    assert out["precheck"]["applied"] and out["factcheck"]["applied"]


@pytest.mark.parametrize("dead", ["factcheck", "precheck"])
def test_quality_gate_goes_on_when_a_model_backed_check_fails(tmp_db, monkeypatch, dead):
    """前两道都在调模型。欠费或超时的时候把整条闸门停掉，等于一道题都过不去。

    过不了的那一档会留在 ERROR 上，看门狗看到账单恢复会自己回来补，所以这里放行
    并不会让一道没核过的题溜到提交 —— 提交门禁那边照样认 ERROR。
    """
    from app.db import session
    from app.services import gsb_factcheck, gsb_precheck, gsb_verifier, qa_bridge

    with session() as db:
        t = m.Task(task_no="07", prompt_hash="h", user_prompt="p", status=m.ANALYZED)
        t.gsb = {"verdict": "A", "reason": "A 侧改对了，B 侧没有。"}
        db.add(t)
        db.flush()
        tid = t.id

    reached = []

    async def dead_check(task_id, **kw):
        return {"ok": False, "message": "模型请求被拒"}

    async def live_check(task_id, **kw):
        reached.append("alive")
        return {"ok": True}

    async def fake_verify(task_id):
        reached.append("verify")
        return {"overall": "ok", "items": []}

    async def fake_qc(task_id):
        reached.append("qc")
        return {"ok": True, "passed": True, "summary": ""}

    monkeypatch.setattr(gsb_factcheck, "run_factcheck",
                        dead_check if dead == "factcheck" else live_check)
    monkeypatch.setattr(gsb_precheck, "run_precheck",
                        dead_check if dead == "precheck" else live_check)
    monkeypatch.setattr(gsb_verifier, "run_verify", fake_verify)
    monkeypatch.setattr(qa_bridge, "gsb_qc", fake_qc)

    asyncio.run(wd.run_quality_gate(tid))
    assert reached == ["alive", "verify", "qc"]


# ---------------- 质检积压与模型恢复 ----------------
# 分析跑完自动接一道质检，这条路走通了就不会有积压。会有积压是因为质检也在调模型：
# 账单被拒、网关抽风、后端重启，任何一次没跑成，题就停在待质检上，而它已经过了配对
# 扫描那一关（analysis_status 是 DONE），后面没有任何一步会再碰它。

def _settled_task(db, task_no="30", *, status=m.ANALYZED, **over):
    t = m.Task(task_no=task_no, prompt_hash="h", user_prompt="p", status=status)
    t.gsb = {"verdict": "A", "reason": "A 侧改对了，B 侧没有。"}
    for k, v in over.items():
        setattr(t, k, v)
    db.add(t)
    db.flush()
    return t


def test_backlog_picks_up_a_task_whose_quality_gate_never_finished(tmp_db):
    from app.db import session

    with session() as db:
        tid = _settled_task(db).id
    assert wd._quality_backlog() == [tid]


def test_backlog_leaves_a_task_whose_checks_both_settled(tmp_db):
    """两道都有有效结论就别再排了：一道题一次调用，对着没动过的话再问一遍是白花。"""
    from app.db import session
    from app.services import gsb_precheck

    with session() as db:
        t = _settled_task(db)
        digest = gsb_precheck.reason_digest(t.gsb["reason"])
        t.factcheck_status = m.FACTCHECK_PASS
        t.factcheck = {"reason_digest": digest}
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": digest}
    assert wd._quality_backlog() == []


def test_backlog_picks_up_a_check_that_errored_out(tmp_db):
    """ERROR 是这道检查自己没跑成，重跑正是该做的事。"""
    from app.db import session
    from app.services import gsb_precheck

    with session() as db:
        t = _settled_task(db)
        digest = gsb_precheck.reason_digest(t.gsb["reason"])
        t.factcheck_status = m.FACTCHECK_ERROR
        t.factcheck = {"error": "账号有未付账单", "reason_digest": digest}
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": digest}
        tid = t.id
    assert wd._quality_backlog() == [tid]


def test_backlog_picks_up_legacy_data_that_only_ever_had_the_wording_check(tmp_db):
    """历史数据的 precheck 早就是 PASS，而事实核验是后加的一道，一律还是 IDLE。

    只问措辞那一道的话，这批最该核的题会整批漏掉，而 ready 列表和积压扫描还会各说
    各的数 —— 两处必须是同一个口径。
    """
    from app.db import session
    from app.services import gsb_precheck

    with session() as db:
        t = _settled_task(db, "35")
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True,
                      "reason_digest": gsb_precheck.reason_digest(t.gsb["reason"])}
        t.factcheck_status = m.FACTCHECK_IDLE
        tid = t.id
    assert wd._quality_backlog() == [tid]
    assert gsb_precheck.ready_ids() == [tid]


def test_recovery_probes_nothing_when_no_task_is_blocked_on_the_model(tmp_db, monkeypatch):
    """探测本身也是一次模型调用。没有积压时一次都不该探。"""
    probes = []

    async def probe():
        probes.append(1)
        return {"ok": True, "message": "pong"}

    monkeypatch.setattr(wd.llm, "probe_ping", probe)
    monkeypatch.setattr(wd, "_last_probe_at", 0.0)
    assert asyncio.run(wd._scan_llm_recovery()) == 0
    assert probes == []


def test_recovery_puts_billing_blocked_tasks_back_once_the_model_answers(tmp_db, monkeypatch):
    """账单结清之后这批题没有任何机制会自己回来，所以要主动探一下。"""
    from app.db import session

    with session() as db:
        stuck = _settled_task(db, "31")
        stuck.factcheck_status = m.FACTCHECK_ERROR
        stuck.factcheck = {"error": "Cursor 账号有未付账单", "llm_error": True}
        stuck.auto_error = "质检没跑完"
        tid = stuck.id

    async def probe():
        return {"ok": True, "message": "claude-opus-5 · 1.2s · pong"}

    monkeypatch.setattr(wd.llm, "probe_ping", probe)
    monkeypatch.setattr(wd, "_last_probe_at", 0.0)
    assert asyncio.run(wd._scan_llm_recovery()) == 1
    from app.db import session as s2

    with s2() as db:
        t = db.get(m.Task, tid)
        assert t.factcheck_status == m.FACTCHECK_IDLE and t.auto_error == ""
    # 门一打开，积压扫描当轮就能挑到它
    assert wd._quality_backlog() == [tid]


def test_recovery_keeps_waiting_while_the_model_still_refuses(tmp_db, monkeypatch):
    from app.db import session

    with session() as db:
        stuck = _settled_task(db, "32")
        stuck.factcheck_status = m.FACTCHECK_ERROR
        stuck.factcheck = {"error": "Cursor 账号有未付账单", "llm_error": True}
        tid = stuck.id

    async def probe():
        return {"ok": False, "message": "Cursor 账号有未付账单"}

    monkeypatch.setattr(wd.llm, "probe_ping", probe)
    monkeypatch.setattr(wd, "_last_probe_at", 0.0)
    assert asyncio.run(wd._scan_llm_recovery()) == 0
    from app.db import session as s2

    with s2() as db:
        assert db.get(m.Task, tid).factcheck_status == m.FACTCHECK_ERROR


def test_recovery_throttles_repeated_probes(tmp_db, monkeypatch):
    """五分钟一轮巡检，每轮都探等于白烧调用。刚探过就跳过。"""
    import time

    from app.db import session

    with session() as db:
        stuck = _settled_task(db, "33")
        stuck.factcheck_status = m.FACTCHECK_ERROR
        stuck.factcheck = {"error": "Cursor 账号有未付账单", "llm_error": True}

    probes = []

    async def probe():
        probes.append(1)
        return {"ok": True, "message": "pong"}

    monkeypatch.setattr(wd.llm, "probe_ping", probe)
    monkeypatch.setattr(wd, "_last_probe_at", time.time())
    assert asyncio.run(wd._scan_llm_recovery()) == 0
    assert probes == []


def test_recovery_leaves_a_check_that_failed_for_a_reason_the_model_cannot_fix(
        tmp_db, monkeypatch):
    """轨迹缺了多少次重跑还是缺。放回流程只会让它下一轮再报同样的错，从此每轮空转。"""
    from app.db import session

    with session() as db:
        t = _settled_task(db, "36")
        t.factcheck_status = m.FACTCHECK_ERROR
        t.factcheck = {"error": "两侧都没有轨迹执行记录，无法核验"}
        tid = t.id

    probes = []

    async def probe():
        probes.append(1)
        return {"ok": True, "message": "pong"}

    monkeypatch.setattr(wd.llm, "probe_ping", probe)
    monkeypatch.setattr(wd, "_last_probe_at", 0.0)
    # 这道题压根不算「等模型恢复」，所以连探测都不该发起
    assert asyncio.run(wd._scan_llm_recovery()) == 0
    assert probes == []
    from app.db import session as s2

    with s2() as db:
        assert db.get(m.Task, tid).factcheck_status == m.FACTCHECK_ERROR


def test_recovery_still_rescues_rows_written_before_the_llm_error_flag(tmp_db, monkeypatch):
    """标记是后加的。账单那阵子攒下的 ERROR 行拿不到它，一条都不放回去等于白做。"""
    from app.db import session

    with session() as db:
        t = _settled_task(db, "37")
        t.precheck_status = m.PRECHECK_ERROR
        t.precheck = {"error": "Cursor 账号有未付账单，模型请求被拒"}
        tid = t.id

    async def probe():
        return {"ok": True, "message": "pong"}

    monkeypatch.setattr(wd.llm, "probe_ping", probe)
    monkeypatch.setattr(wd, "_last_probe_at", 0.0)
    assert asyncio.run(wd._scan_llm_recovery()) == 1
    from app.db import session as s2

    with s2() as db:
        assert db.get(m.Task, tid).precheck_status == m.PRECHECK_IDLE


def test_recovery_ignores_an_analysis_that_failed_for_a_non_model_reason(tmp_db, monkeypatch):
    """分析失败的原因五花八门。拿「轨迹缺失」那种去触发探测，等于每十分钟白烧一次。"""
    from app.db import session

    with session() as db:
        t = _settled_task(db, "34", status=m.NEEDS_ATTENTION)
        t.analysis_status = m.ANALYSIS_FAILED
        t.auto_error = "GSB 分析失败：两侧的运行记录不全"

    probes = []

    async def probe():
        probes.append(1)
        return {"ok": True, "message": "pong"}

    monkeypatch.setattr(wd.llm, "probe_ping", probe)
    monkeypatch.setattr(wd, "_last_probe_at", 0.0)
    assert asyncio.run(wd._scan_llm_recovery()) == 0
    assert probes == []
