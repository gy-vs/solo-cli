import json
from pathlib import Path

from app.services import trace


def _line(**kw):
    return json.dumps(kw, ensure_ascii=False) + "\n"


def make_trace(path: Path) -> None:
    sid = "3f665232-ac02-4002-b427-3a8a608a9cbc"
    lines = [
        _line(type="queue-operation", sessionId=sid),
        _line(type="user", sessionId=sid, isSidechain=False, promptId="p-1", uuid="u1", timestamp="2026-09-15T01:00:00Z",
              message={"role": "user", "content": "写一个库"}),
        _line(type="assistant", sessionId=sid, uuid="a1", timestamp="2026-09-15T01:00:05Z",
              message={"role": "assistant", "model": "auto_model/urm", "content": [
                  {"type": "text", "text": "我先看看仓库结构"},
                  {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls src/diff.ts && npm test"}},
              ]}),
        _line(type="user", sessionId=sid, uuid="u2", timestamp="2026-09-15T01:00:06Z",
              message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "1 failed, 3 passed", "is_error": True}]}),
        _line(type="assistant", sessionId=sid, uuid="a2", timestamp="2026-09-15T01:00:09Z",
              message={"role": "assistant", "stop_reason": "end_turn", "content": [
                  {"type": "tool_use", "id": "t2", "name": "Write", "input": {"file_path": "src/merge.ts", "content": "x"}},
              ]}),
        _line(type="user", sessionId=sid, uuid="u3", timestamp="2026-09-15T01:00:10Z",
              message={"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "ok"}]}),
    ]
    path.write_text("".join(lines), encoding="utf-8")


def test_parse_trace(tmp_path: Path):
    f = tmp_path / "-workspace" / "3f665232-ac02-4002-b427-3a8a608a9cbc.jsonl"
    f.parent.mkdir()
    make_trace(f)
    assert trace.find_trace_file(tmp_path) == f
    s = trace.parse_trace(f)
    assert s["session_id"] == "3f665232-ac02-4002-b427-3a8a608a9cbc"
    assert s["prompt_id"] == "p-1"
    assert s["counts"]["tool_calls"] == 2
    assert s["counts"]["tool_errors"] == 1
    tools = [x for x in s["steps"] if x["kind"] == "tool"]
    assert tools[0]["tool"] == "Bash" and "src/diff.ts" in tools[0]["files"]
    assert tools[0]["is_error"] and "1 failed" in tools[0]["result"]
    assert tools[1]["files"] == ["src/merge.ts"]


def test_find_trace_ignores_previous_round(tmp_path: Path):
    """轨迹目录按题号复用，本轮没产出时不能把上一轮的 jsonl 当成自己的。"""
    import os
    from datetime import datetime, timedelta, timezone

    old = tmp_path / "old-session.jsonl"
    make_trace(old)
    started = datetime.now(timezone.utc)
    stale = (started - timedelta(hours=3)).timestamp()
    os.utime(old, (stale, stale))

    assert trace.find_trace_file(tmp_path) == old          # 不给时间下界时仍能找到
    assert trace.find_trace_file(tmp_path, started) is None  # 本轮没写过，不采用
    assert trace.count_traces(tmp_path) == 1
    assert trace.count_traces(tmp_path, started) == 0

    fresh = tmp_path / "this-round.jsonl"
    make_trace(fresh)
    assert trace.find_trace_file(tmp_path, started) == fresh


def test_parse_trace_reads_harness_version(tmp_path: Path):
    """上传时 harness_version 必须与轨迹一致，版本要从轨迹里取。"""
    f = tmp_path / "v.jsonl"
    f.write_text(
        _line(type="user", sessionId="s1", version="2.1.246", cwd="/workspace", isSidechain=False,
              promptId="p-1", message={"role": "user", "content": "做题"}),
        encoding="utf-8",
    )
    s = trace.parse_trace(f)
    assert s["harness_version"] == "2.1.246"
    assert s["cwd"] == "/workspace"
