"""巡检：异常判定、重跑准备、配对推进。"""

from __future__ import annotations

import asyncio

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


def test_gateway_error_is_abnormal():
    r = _run(verdict={"process": {"gateway_errors": ["504"]},
                      "protocol": {"subtype": "success"},
                      "artifact": {"trace_found": True, "changed_files": 3}})
    assert "504" in wd.abnormal_reason(r)


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
    r = _run(status=m.RUN_RUNNING, verdict={})
    assert "已经不在了" in wd.abnormal_reason(r, container_alive=False)


def test_running_with_live_container_is_fine():
    r = _run(status=m.RUN_RUNNING, verdict={})
    assert wd.abnormal_reason(r, container_alive=True) == ""


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
    tr = tmp_path / "出题" / "轨迹" / "07" / "A"
    tr.mkdir(parents=True)
    (tr / "a.jsonl").write_text("{}", encoding="utf-8")

    assert wd.archive_traces("07", "A")["ok"] is True
    # 原目录整体改名走了，下次跑之前 runner 会重新建一个空的
    assert not tr.exists()
    archived = list((tmp_path / "出题" / "轨迹" / "07").glob("A.archived-*"))
    assert len(archived) == 1
    # 归档是改名不是删除：上一次的轨迹是判「为什么异常」的唯一材料
    assert (archived[0] / "a.jsonl").exists()


def test_archive_traces_noop_when_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(wd.config, "CODER_ROOT_MOUNT", tmp_path)
    (tmp_path / "出题" / "轨迹" / "07" / "A").mkdir(parents=True)
    assert wd.archive_traces("07", "A")["ok"] is True


# ---------------- 重跑准备 ----------------

@pytest.fixture()
def stub_side_effects(monkeypatch, tmp_path):
    calls = {"removed": [], "reset": []}

    async def remove(name, force=False):
        calls["removed"].append(name)
        return True

    async def reset(task_no, side, snapshot):
        calls["reset"].append(side)
        return {"ok": True, "message": f"{side} 已退回"}

    monkeypatch.setattr(wd.dockerx, "remove_container", remove)
    monkeypatch.setattr(wd.gsb_repo, "reset_side", reset)
    monkeypatch.setattr(wd.config, "CODER_ROOT_MOUNT", tmp_path)
    return calls


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


def test_requeue_removes_container_then_resets(task_with_runs, stub_side_effects):
    task_id, ids = task_with_runs
    asyncio.run(wd.requeue_run(ids["B"], reason="超时"))
    assert stub_side_effects["removed"] == ["solo-cc-07-B"]
    assert stub_side_effects["reset"] == ["B"]


def test_requeue_stops_if_reset_fails(task_with_runs, stub_side_effects, monkeypatch):
    """reset 失败还往下走，会拿上一次的改动当起点，产物快照的父提交就对不上了。"""
    from app.db import session

    async def bad_reset(task_no, side, snapshot):
        return {"ok": False, "message": "本地有冲突"}

    monkeypatch.setattr(wd.gsb_repo, "reset_side", bad_reset)
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


def test_give_up_flags_task_for_human(task_with_runs):
    from app.db import session

    task_id, ids = task_with_runs
    asyncio.run(wd.give_up(ids["A"], "网关 504 连着三次"))
    with session() as db:
        task = db.get(m.Task, task_id)
        assert task.status == m.NEEDS_ATTENTION
        assert "504" in task.auto_error
        assert db.get(m.TaskRun, ids["A"]).abnormal["gave_up"] is True


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


def test_pairs_ready_skips_abnormal_side(task_with_runs):
    from app.db import session

    task_id, ids = task_with_runs
    _finish_both(ids)
    with session() as db:
        run = db.get(m.TaskRun, ids["B"])
        run.verdict = {"process": {"gateway_errors": ["504"]},
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


def test_push_failure_does_not_count_as_retry(task_with_runs, monkeypatch):
    """推送失败是我这边的事，不是模型的事，不能吃掉重跑次数。"""
    from app.db import session

    task_id, ids = task_with_runs
    _finish_both(ids)

    async def push(task_no, repo_url, side, snapshot, *, message):
        return {"ok": False, "message": "远端拒绝"}

    async def remove(name, force=False):
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

    async def remove(name, force=False):
        removed.append(name)
        return True

    async def push(task_no, repo_url, side, snapshot, *, message):
        return {"ok": False, "message": "先不推"}

    monkeypatch.setattr(wd.dockerx, "remove_container", remove)
    monkeypatch.setattr(wd.gsb_repo, "commit_and_push", push)
    asyncio.run(wd.advance_pair(task_id))
    assert removed == ["solo-cc-07-B"]
