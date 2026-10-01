"""逐次运行记录与「最近废弃」。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from app import config
from app import models as m
from app.services import attempt_log
from app.services import watchdog as wd

# 「最近」按此刻往回数，起点钉死的话这批用例过几天就全落到窗口外面去了
T0 = (datetime.now(timezone.utc) - timedelta(days=1)).replace(minute=0, second=0, microsecond=0)


@pytest.fixture()
def stubbed(monkeypatch):
    async def ok(*_a, **_kw):
        return {"ok": True, "mode": "reset", "message": "已重建"}

    async def removed(*_a, **_kw):
        return True

    monkeypatch.setattr(wd.dockerx, "remove_container", removed)
    monkeypatch.setattr(wd.gsb_repo, "reset_side", ok)
    monkeypatch.setattr(wd.gsb_repo, "rebuild_side", ok)


def _ran(run_id: int, start: datetime, minutes: int, status: str = m.RUN_FAILED) -> None:
    from app.db import session

    with session() as db:
        r = db.get(m.TaskRun, run_id)
        r.status, r.started_at = status, start
        r.finished_at = start + timedelta(minutes=minutes)


def _item(task_id: int) -> dict:
    return next(i for i in attempt_log.recent_discarded(7)["items"] if i["id"] == task_id)


def test_three_runs_then_discard_are_all_listed(task_with_runs, stubbed):
    """跑了三次被废掉的一侧，三次各自的起止、耗时、间隔和原因都要在。"""
    task_id, ids = task_with_runs
    _ran(ids["A"], T0, 30)
    asyncio.run(wd.requeue_run(ids["A"], reason="退出码 1"))
    _ran(ids["A"], T0 + timedelta(minutes=40), 20, m.RUN_TIMEOUT)
    asyncio.run(wd.requeue_run(ids["A"], reason="跑超时"))
    _ran(ids["A"], T0 + timedelta(minutes=65), 10)
    asyncio.run(wd.give_up(ids["A"], "退出码 1（A 侧已跑 3 次，达到上限 3）"))

    item = _item(task_id)
    assert item["kind"] == "retries" and item["discard_count"] == 1
    a = next(s for s in item["sides"] if s["side"] == "A")
    assert [x["outcome"] for x in a["attempts"]] == ["retry", "retry", "discard"]
    assert [x["reason"] for x in a["attempts"]][:2] == ["退出码 1", "跑超时"]
    assert [x["duration_s"] for x in a["attempts"]] == [1800, 1200, 600]
    assert [x["wait_s"] for x in a["attempts"]] == [None, 600, 300]
    assert [x["run_status"] for x in a["attempts"]] == [m.RUN_FAILED, m.RUN_TIMEOUT, m.RUN_FAILED]
    assert a["retries"] == 2 and not item["legacy"]


def test_side_never_started_has_no_attempts(task_with_runs, stubbed):
    task_id, ids = task_with_runs
    _ran(ids["A"], T0, 30)
    asyncio.run(wd.give_up(ids["A"], "退出码 1"))
    b = next(s for s in _item(task_id)["sides"] if s["side"] == "B")
    assert b["attempts"] == []


def test_restore_then_discard_again_counts_twice(task_with_runs, stubbed):
    """恢复后再废，废弃次数要累加；恢复时的人工重跑不能把废弃那次再记一遍。"""
    from app.db import session

    task_id, ids = task_with_runs
    _ran(ids["A"], T0, 30)
    asyncio.run(wd.give_up(ids["A"], "退出码 1（A 侧已跑 1 次，达到上限 1）"))
    asyncio.run(wd.revive_discarded(task_id))
    with session() as db:
        assert db.get(m.Task, task_id).status != m.DISCARDED
    _ran(ids["A"], T0 + timedelta(hours=1), 15)
    asyncio.run(wd.give_up(ids["A"], "跑超时（A 侧超时 2 次，达到上限 2）"))

    item = _item(task_id)
    assert item["discard_count"] == 2
    assert [d["kind"] for d in item["discards"]] == ["retries", "timeouts"]
    a = next(s for s in item["sides"] if s["side"] == "A")
    assert [x["outcome"] for x in a["attempts"]] == ["discard", "discard"]


def test_other_side_stopped_midway_is_marked_interrupted(task_with_runs, stubbed, monkeypatch):
    from app.services import runner

    task_id, ids = task_with_runs
    _ran(ids["A"], T0, 30)
    _ran(ids["B"], T0, 0, m.RUN_RUNNING)

    async def stop_run(_rid):
        return {"ok": True, "message": ""}

    monkeypatch.setattr(runner, "stop_run", stop_run)
    asyncio.run(wd.give_up(ids["A"], "退出码 1"))
    b = next(s for s in _item(task_id)["sides"] if s["side"] == "B")
    assert [x["outcome"] for x in b["attempts"]] == ["interrupted"]


@pytest.mark.parametrize("reason, kind", [
    ("A 侧第 3 次仍异常：退出码 1（A 侧已跑 3 次，达到上限 3）", "retries"),
    ("B 侧第 2 次仍异常：结束状态是 TIMEOUT（B 侧超时 2 次，达到上限 2）", "timeouts"),
    ("A 侧第 1 次仍异常：零改动；重跑准备连续 3 次失败：GitHub 连不上", "prep"),
    ("难度筛选未通过：两侧都只跑了 12 步", "difficulty"),
    ("探路未通过：A 侧 8 步", "difficulty"),
    ("领取查重（GSB 口径）规则 A 查重命中", "dedup"),
    ("自动废弃：人工废弃", "manual"),
    ("别的什么", "other"),
])
def test_discard_kind(reason, kind):
    assert attempt_log.discard_kind(reason) == kind


def test_old_task_gets_earlier_runs_from_trace_archives(task_with_runs):
    """记录上线前废掉的题：前几次从轨迹归档的首尾时间戳补出来，标成旧记录。"""
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        r = db.get(m.TaskRun, ids["A"])
        r.status, r.attempt = m.RUN_FAILED, 3
        r.started_at, r.finished_at = T0 + timedelta(hours=3), T0 + timedelta(hours=4)
        r.abnormal = {"reason": "退出码 1", "gave_up": True}
        t = db.get(m.Task, task_id)
        t.status, t.discarded_at = m.DISCARDED, T0 + timedelta(hours=4)
        t.auto_error = "自动废弃：A 侧第 3 次仍异常：退出码 1（A 侧已跑 3 次，达到上限 3）"
    root = config.TaskPaths("07", "A").traces.parent
    for i, stamp in enumerate(("20261001-013000", "20261001-024500")):
        d = root / f"A.archived-{stamp}" / "-workspace"
        d.mkdir(parents=True)
        s = T0 + timedelta(hours=i, minutes=1)
        lines = [{"type": "summary"}, {"timestamp": s.isoformat().replace("+00:00", "Z")},
                 {"timestamp": (s + timedelta(minutes=25)).isoformat().replace("+00:00", "Z")}]
        (d / "x.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")

    item = _item(task_id)
    assert item["legacy"] and item["discard_count"] == 1
    a = next(s for s in item["sides"] if s["side"] == "A")
    assert [x["outcome"] for x in a["attempts"]] == ["legacy", "legacy", "discard"]
    assert [x["duration_s"] for x in a["attempts"]] == [1500, 1500, 3600]


def test_old_task_without_archives_pads_missing_runs(task_with_runs):
    """归档也清掉了的老题，按计数补占位，不能让「已跑 2 次」底下只列一次。"""
    from app.db import session

    task_id, ids = task_with_runs
    with session() as db:
        r = db.get(m.TaskRun, ids["A"])
        r.status, r.attempt = m.RUN_TIMEOUT, 2
        r.started_at, r.finished_at = T0, T0 + timedelta(hours=2)
        t = db.get(m.Task, task_id)
        t.status, t.discarded_at = m.DISCARDED, T0 + timedelta(hours=2)
    a = next(s for s in _item(task_id)["sides"] if s["side"] == "A")
    assert len(a["attempts"]) == 2
    assert a["attempts"][0]["started_at"] is None and a["attempts"][1]["duration_s"] == 7200


def test_recent_route_is_registered_before_task_id_routes():
    """/{task_id} 先注册的话 discarded 会被当成题号，接口直接 422。"""
    from app.routers.tasks import router

    paths = [r.path for r in router.routes]
    assert paths.index("/api/tasks/discarded/recent") < paths.index("/api/tasks/{task_id}")
