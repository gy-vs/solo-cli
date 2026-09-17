"""GSB 双跑改造后的数据模型约束。

一道题固定两条 TaskRun（A/B），单跑时代挂在 Task 上的容器、会话、结果字段全部下沉到
TaskRun；Task 只留题面与流程状态，以及 GSB 结论、录屏、分支校验这些题级信息。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models as m


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    m.Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_task_run_unique_per_side(db):
    t = m.Task(task_no="07", prompt_hash="h")
    db.add(t)
    db.flush()
    db.add(m.TaskRun(task_id=t.id, side="A"))
    db.add(m.TaskRun(task_id=t.id, side="B"))
    db.flush()
    db.add(m.TaskRun(task_id=t.id, side="A"))
    with pytest.raises(Exception):
        db.flush()


def test_task_run_defaults(db):
    t = m.Task(task_no="07", prompt_hash="h")
    db.add(t)
    db.flush()
    r = m.TaskRun(task_id=t.id, side="A")
    db.add(r)
    db.flush()
    assert r.status == m.RUN_PENDING
    assert r.attempt == 1
    assert r.artifact_sha == "" and r.artifact_url == ""
    assert r.verdict == {} and r.abnormal == {}


def test_task_run_json_roundtrip(db):
    t = m.Task(task_no="07", prompt_hash="h")
    db.add(t)
    db.flush()
    r = m.TaskRun(task_id=t.id, side="B")
    db.add(r)
    r.verdict = {"process": {"exit_code": 0}}
    r.abnormal = {"reason": "没有产出轨迹", "at": "2026-09-17T00:00:00Z"}
    db.flush()
    assert r.verdict["process"]["exit_code"] == 0
    assert r.abnormal["reason"] == "没有产出轨迹"


def test_task_gsb_fields(db):
    t = m.Task(task_no="07", prompt_hash="h")
    db.add(t)
    t.gsb = {"verdict": "A", "reason": "x"}
    t.screencast = {"A": "https://a", "B": "https://b"}
    t.branch_check = {"ok": True, "branches": ["main", "A", "B"]}
    db.flush()
    assert t.gsb["verdict"] == "A"
    assert t.screencast["B"] == "https://b"
    assert t.branch_check["branches"] == ["main", "A", "B"]


def test_run_event_has_side_not_round(db):
    e = m.RunEvent(task_id=1, seq=1, side="B", kind="system", summary="x")
    db.add(e)
    db.flush()
    assert e.side == "B"
    assert not hasattr(e, "round_no")


def test_dropped_task_columns_are_gone():
    dropped = {"session_id", "turn_id", "round_no", "rounds_json", "continue_prompt",
               "container_name", "container_exists", "image_tag", "exit_code",
               "result_json", "verdict_json", "trace_summary_json", "trace_file",
               "git_diff_stat", "review_json", "qc_status", "qc_json", "qc_at"}
    assert dropped & set(m.Task.__table__.columns.keys()) == set()


def test_task_statuses_cover_gsb_flow():
    for s in (m.RUN_DONE, m.ANALYZING, m.ANALYZED, m.NEEDS_ATTENTION):
        assert s in m.ALL_STATUSES
