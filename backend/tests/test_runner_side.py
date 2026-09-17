"""运行模块：单侧执行的状态判定、网关报错识别、收尾落库、超长行切分。"""

from __future__ import annotations

import asyncio

import pytest

from app import models as m
from app.services import runner


# ---------------- 状态判定 ----------------

def test_decide_status_uses_run_constants():
    assert runner.decide_status(timed_out=True, manual_stop=False, result_event={},
                                exit_code=None, has_trace=True) == (m.RUN_TIMEOUT, False)
    assert runner.decide_status(timed_out=False, manual_stop=True, result_event={},
                                exit_code=137, has_trace=True) == (m.RUN_INTERRUPTED, False)
    assert runner.decide_status(timed_out=False, manual_stop=False,
                                result_event={"subtype": "success"}, exit_code=0,
                                has_trace=True) == (m.RUN_FINISHED, False)
    assert runner.decide_status(timed_out=False, manual_stop=False, result_event={},
                                exit_code=0, has_trace=True) == (m.RUN_FINISHED, True)
    assert runner.decide_status(timed_out=False, manual_stop=False, result_event={},
                                exit_code=None, has_trace=False) == (m.RUN_INTERRUPTED, False)
    assert runner.decide_status(timed_out=False, manual_stop=False,
                                result_event={"subtype": "error_max_turns"}, exit_code=1,
                                has_trace=True) == (m.RUN_FAILED, False)


# ---------------- 网关报错识别 ----------------

def test_gateway_errors_from_api_retry_events():
    events = [
        {"type": "system", "subtype": "api_retry", "error_status": 504},
        {"type": "system", "subtype": "api_retry", "error_status": 429},
        {"type": "system", "subtype": "init"},
    ]
    assert runner.gateway_errors(events, []) == ["504", "429"]


def test_gateway_errors_dedups():
    events = [{"type": "system", "subtype": "api_retry", "error_status": 504}] * 3
    assert runner.gateway_errors(events, []) == ["504"]


def test_gateway_errors_from_stderr_text():
    tail = ["upstream connect error", "HTTP 504 Gateway Timeout", "retrying"]
    assert runner.gateway_errors([], tail) == ["504"]


def test_gateway_errors_ignores_unrelated_numbers():
    # 「写了 5040 字节」里的 504 不是状态码，只看紧邻 HTTP/status 这类词的
    assert runner.gateway_errors([], ["wrote 5040 bytes", "exit 200"]) == []


def test_continue_round_api_is_gone():
    assert not hasattr(runner, "queue_continue")
    assert not hasattr(runner, "build_continue_prompt")
    assert not hasattr(runner, "_max_seq")


# ---------------- 超长行切分（原有行为，不许退化）----------------

class _FakeStream:
    def __init__(self, data: bytes, chunk: int = 7):
        self.data = data
        self.chunk = chunk
        self.pos = 0

    async def read(self, n: int) -> bytes:
        out = self.data[self.pos:self.pos + min(n, self.chunk)]
        self.pos += len(out)
        return out


def _collect(data: bytes, chunk: int = 7):
    async def go():
        return [(line, trunc) async for line, trunc in runner._iter_lines(_FakeStream(data, chunk))]

    return asyncio.run(go())


def test_iter_lines_splits_across_chunks():
    got = _collect(b"one\ntwo\nthree\n")
    assert [line for line, _ in got] == [b"one", b"two", b"three"]
    assert all(not t for _, t in got)


def test_iter_lines_yields_tail_without_newline():
    got = _collect(b"alpha\nbeta")
    assert [line for line, _ in got] == [b"alpha", b"beta"]


def test_iter_lines_truncates_overlong_line(monkeypatch):
    monkeypatch.setattr(runner, "MAX_LINE_BYTES", 10)
    got = _collect(b"x" * 25 + b"\nshort\n", chunk=4)
    assert got[0][1] is True
    assert len(got[0][0]) == 10
    # 超长行的余下字节要丢到行尾，下一行必须完整
    assert got[-1][0] == b"short"


# ---------------- 收尾落库 ----------------

@pytest.fixture()
def no_git(monkeypatch):
    from app.services.dockerx import CmdResult

    async def fake(*a, **k):
        return CmdResult(1, "", "not a repo")

    monkeypatch.setattr(runner.dockerx, "run", fake)


def test_finalize_writes_to_the_run_not_the_task(task_with_runs, monkeypatch, no_git):
    task_id, ids = task_with_runs
    monkeypatch.setattr(runner.trace, "find_trace_file", lambda d, since=None: None)
    monkeypatch.setattr(runner.trace, "count_traces", lambda d, since=None: 0)
    monkeypatch.setattr(runner.watchdog, "wake", lambda: None)

    asyncio.run(runner.finalize(ids["A"], exit_code=1, result_event={"subtype": "error"},
                                stderr_tail=["HTTP 504 Gateway Timeout"],
                                retry_events=[{"type": "system", "subtype": "api_retry",
                                               "error_status": 429}]))

    from app.db import session
    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        assert run.status == m.RUN_FAILED
        assert run.verdict["process"]["exit_code"] == 1
        # 事件里的 429 与 stderr 里的 504 都要收进来，watchdog 靠它判要不要重跑
        assert run.verdict["process"]["gateway_errors"] == ["429", "504"]
        assert "504" in run.error
        assert run.finished_at is not None
        # 另一侧不许被动到
        assert db.get(m.TaskRun, ids["B"]).status == m.RUN_PENDING


def test_finalize_leaves_task_status_to_watchdog(task_with_runs, monkeypatch, no_git):
    """runner 只管自己那一侧，题目级状态归 watchdog，免得两边抢着改。"""
    task_id, ids = task_with_runs
    monkeypatch.setattr(runner.trace, "find_trace_file", lambda d, since=None: None)
    monkeypatch.setattr(runner.trace, "count_traces", lambda d, since=None: 0)
    woke = []
    monkeypatch.setattr(runner.watchdog, "wake", lambda: woke.append(True))

    asyncio.run(runner.finalize(ids["A"], exit_code=0, result_event={"subtype": "success"}))

    from app.db import session
    with session() as db:
        assert db.get(m.Task, task_id).status == m.AVAILABLE
    assert woke == [True]


def test_finalize_notes_missing_trace(task_with_runs, monkeypatch, no_git):
    task_id, ids = task_with_runs
    monkeypatch.setattr(runner.trace, "find_trace_file", lambda d, since=None: None)
    monkeypatch.setattr(runner.trace, "count_traces", lambda d, since=None: 0)
    monkeypatch.setattr(runner.watchdog, "wake", lambda: None)

    asyncio.run(runner.finalize(ids["B"], exit_code=0, result_event={"subtype": "success"}))

    from app.db import session
    with session() as db:
        notes = " ".join(db.get(m.TaskRun, ids["B"]).verdict["notes"])
    assert "轨迹" in notes
