import json
from pathlib import Path

from app.services import trace, verifier


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


def test_verify_flags(tmp_path: Path):
    f = tmp_path / "t.jsonl"
    make_trace(f)
    idx = trace.parse_trace(f)
    good = "我把 prompt 里的四条约束逐条对了产物，第 2 步跑 npm test 时有 1 个用例失败，模型在第 4 步改了 src/merge.ts 之后没有再跑测试就结束了。"
    review = {
        "scores": {d: 4 for d in verifier.DIMS},
        "descs": {d: good for d in verifier.DIMS},
        "evidence": {"delivery": [{"step": 2, "file": "src/diff.ts", "quote": "1 failed, 3 passed"}],
                     "instruction": [{"step": 99}], "planning": [], "reasoning": [], "execution": []},
        "other_issues": "",
        "coverage": [{"point": "Myers", "status": "missing"}],
    }
    rep = verifier.verify(review, idx)
    codes = {(i.get("dim"), i["code"]) for i in rep["items"]}
    assert ("instruction", "step_missing") in codes
    assert ("delivery", "score_coverage_conflict") in codes
    assert rep["overall"] == "block"            # 分数与覆盖冲突 + 描述雷同
    assert rep["evidence_hit"] == 1 and rep["evidence_total"] == 2

    review["descs"] = {d: good + f"这是第{n}条。" for n, d in enumerate(verifier.DIMS)}
    review["descs"]["delivery"] = "首先，模型表现出色 ✅ **完美**"
    review["coverage"] = [{"point": "Myers", "status": "done"}]
    rep2 = verifier.verify(review, idx)
    delivery_codes = {i["code"] for i in rep2["items"] if i.get("dim") == "delivery"}
    assert {"ai_words", "emoji", "markdown", "not_first_person", "too_short"} <= delivery_codes
    assert rep2["overall"] == "warn"
