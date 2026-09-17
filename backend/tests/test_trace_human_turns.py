"""轨迹里的真人轮次。平台要求恰好一轮（规则 T5），数错了会误拦或误放。"""

from __future__ import annotations

import json
from pathlib import Path

from app.services import trace

SID = "3f665232-ac02-4002-b427-3a8a608a9cbc"


def _line(**kw):
    return json.dumps(kw, ensure_ascii=False) + "\n"


def _human(text: str, **kw):
    return _line(type="user", sessionId=SID, isSidechain=False, promptId="p-1",
                 message={"role": "user", "content": text}, **kw)


def _tool_result(tid: str = "t1"):
    return _line(type="user", sessionId=SID, isSidechain=False,
                 message={"role": "user", "content": [
                     {"type": "tool_result", "tool_use_id": tid, "content": "ok"}]})


def _assistant(tid: str = "t1"):
    return _line(type="assistant", sessionId=SID, message={"role": "assistant", "content": [
        {"type": "tool_use", "id": tid, "name": "Read", "input": {"file_path": "src/a.ts"}}]})


def _write(tmp_path: Path, *lines) -> Path:
    f = tmp_path / f"{SID}.jsonl"
    f.write_text("".join(lines), encoding="utf-8")
    return f


def test_single_human_turn(tmp_path):
    f = _write(tmp_path, _human("做个解析器"), _assistant(), _tool_result())
    assert trace.parse_trace(f)["human_turns"] == 1


def test_tool_results_are_not_human_turns(tmp_path):
    """type=user 的行里绝大多数是工具返回，全算上的话每道题都会被判人工介入。"""
    f = _write(tmp_path, _human("做个解析器"),
               _assistant("t1"), _tool_result("t1"),
               _assistant("t2"), _tool_result("t2"),
               _assistant("t3"), _tool_result("t3"))
    assert trace.parse_trace(f)["human_turns"] == 1


def test_second_human_turn_is_counted(tmp_path):
    f = _write(tmp_path, _human("做个解析器"), _assistant(), _tool_result(),
               _human("再加个测试"))
    assert trace.parse_trace(f)["human_turns"] == 2


def test_sidechain_user_lines_are_not_human(tmp_path):
    """子会话里的 user 行是 Task 工具派出去的子代理在自问自答，不是真人。"""
    side = _line(type="user", sessionId=SID, isSidechain=True,
                 message={"role": "user", "content": "子代理的输入"})
    f = _write(tmp_path, _human("做个解析器"), side, side, _assistant(), _tool_result())
    assert trace.parse_trace(f)["human_turns"] == 1


def test_prompt_text_is_captured_in_full(tmp_path):
    """核验要拿完整题面和题块比对（规则 G4），不能是 200 字的预览。"""
    long_prompt = "做个解析器。" + "细节要求若干。" * 200
    f = _write(tmp_path, _human(long_prompt), _assistant(), _tool_result())
    s = trace.parse_trace(f)
    assert s["prompt"] == long_prompt
    assert len(s["first_user_text"]) <= 200


def test_zero_human_turns_when_only_tool_results(tmp_path):
    f = _write(tmp_path, _assistant(), _tool_result())
    assert trace.parse_trace(f)["human_turns"] == 0
