"""收尾流程跑通测试。

这条路径出过一次真事故：状态判定抽成函数后，下面拼 verdict 的地方还在用被删掉的
局部变量，finalize 直接抛 NameError，一道跑了四小时的题什么都没存下来。
纯函数单测拦不住这种，所以这里真的调一次 finalize，确认判定、轨迹、回填、事件都落了地。
"""

import json
from datetime import timedelta

import pytest

from app import config
from app.db import session
from app.models import FINISHED, INTERRUPTED, Task, utc_now
from app.services import runner

SID = "3f665232-ac02-4002-b427-3a8a608a9cbc"


@pytest.fixture
def task(tmp_path, monkeypatch):
    """一道刚跑完的题：独立的 data 目录、独立的 sqlite、工作区非 git。"""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path / "coder")
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "data" / "exports")

    from app.db import init_db
    engine_path = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", engine_path)
    import app.db as dbmod
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine(f"sqlite:///{engine_path}", future=True)
    monkeypatch.setattr(dbmod, "engine", eng)
    monkeypatch.setattr(dbmod, "SessionLocal", sessionmaker(bind=eng, expire_on_commit=False, future=True))
    init_db()

    with session() as db:
        t = Task(task_no="42", prompt_hash="h", user_prompt="写个解析器",
                 started_at=utc_now() - timedelta(minutes=5), container_name="solo-cc-42")
        db.add(t)
        db.flush()
        tid = t.id
    # 关掉后续流水线，这里只验证收尾本身
    monkeypatch.setattr(runner.settings_store, "get_bool", lambda *a, **k: False)
    return tid


def _write_trace(task_no: str) -> None:
    paths = config.TaskPaths(task_no)
    paths.traces.mkdir(parents=True, exist_ok=True)
    lines = [
        {"type": "user", "sessionId": SID, "isSidechain": False, "promptId": "p-9", "uuid": "u1",
         "timestamp": "2026-09-16T01:00:00Z", "message": {"role": "user", "content": "写个解析器"}},
        {"type": "assistant", "sessionId": SID, "uuid": "a1", "timestamp": "2026-09-16T01:00:05Z",
         "message": {"role": "assistant", "stop_reason": "end_turn",
                     "content": [{"type": "text", "text": "好了"}]}},
    ]
    (paths.traces / f"{SID}.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8")


@pytest.mark.asyncio
async def test_finalize_writes_verdict_and_trace(task):
    _write_trace("42")
    await runner.finalize(task, exit_code=0, thinking_tokens=1234,
                          result_event={"type": "result", "subtype": "success", "is_error": False,
                                        "num_turns": 7, "duration_ms": 9000, "total_cost_usd": 0.5,
                                        "session_id": SID})
    with session() as db:
        t = db.get(Task, task)
        assert t.status == FINISHED
        v = t.verdict
        assert v["protocol"]["subtype"] == "success"
        assert v["protocol"]["num_turns"] == 7
        assert v["protocol"]["thinking_tokens"] == 1234
        assert v["artifact"]["trace_found"] is True
        assert t.session_id == SID
        assert t.turn_id == "p-9"
        assert t.trace_file.endswith(".jsonl")
        assert t.finished_at is not None


@pytest.mark.asyncio
async def test_finalize_without_result_and_trace(task):
    """被杀掉又没产出：也要写下判定，不能抛异常把记录丢掉。"""
    await runner.finalize(task, exit_code=137, result_event={})
    with session() as db:
        t = db.get(Task, task)
        assert t.status == INTERRUPTED
        assert t.verdict["artifact"]["trace_found"] is False
        assert any("没有产出轨迹" in n for n in t.verdict["notes"])


@pytest.mark.asyncio
async def test_finalize_adopted_container(task):
    """重启后接管：没有 result 事件，退出码 0 且有轨迹就算跑完，并在备注里说明。"""
    _write_trace("42")
    await runner.finalize(task, exit_code=0, result_event={})
    with session() as db:
        t = db.get(Task, task)
        assert t.status == FINISHED
        assert t.verdict["protocol"]["subtype"] == ""
        assert any("接管" in n for n in t.verdict["notes"])
