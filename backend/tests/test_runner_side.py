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
        return [(line, trunc) async for line, trunc in runner.iter_lines(_FakeStream(data, chunk))]

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


# ---------------- 出闸前的起点校验 ----------------

def test_run_side_refuses_a_workspace_that_is_not_the_start_point(task_with_runs, monkeypatch):
    """起点不对就不起容器。

    docker run -v 对着一个不存在的宿主路径会默默建一个空目录挂进去，模型在空工作区里
    会自己 git init 造一个仓库接着做题，跑完带着完整轨迹和一份像模像样的产物。
    """
    from app.db import session

    task_id, ids = task_with_runs
    spawned = []

    async def verify(task_no, side, snapshot):
        return {"ok": False, "head": "", "dirty": 0, "message": f"{side} 侧还没有 clone"}

    async def spawn(*a, **k):
        spawned.append(a)
        raise AssertionError("起点不对还是把容器起起来了")

    async def present(image):
        return True

    monkeypatch.setattr(runner.dockerx, "image_present", present)
    monkeypatch.setattr(runner.gsb_repo, "verify_head", verify)
    monkeypatch.setattr(runner.settings_store, "get", lambda k: "img")
    monkeypatch.setattr(runner.settings_store, "get_int", lambda k, d=0: d)
    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", spawn)
    woke = []
    monkeypatch.setattr(runner.watchdog, "wake", lambda: woke.append(True))

    asyncio.run(runner.run_side(ids["A"]))

    assert spawned == []
    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        assert run.status == m.RUN_FAILED
        assert "还没有 clone" in run.error
        assert run.container_exists is False
        # 另一侧不归这次出闸管
        assert db.get(m.TaskRun, ids["B"]).status == m.RUN_PENDING
    # 交给巡检去判异常，它走的完全重建正好能把工作区修回来
    assert woke == [True]


def test_run_side_holds_the_queue_when_the_image_is_missing(task_with_runs, monkeypatch):
    """镜像不在本机就不出闸，也不算这一侧跑坏了。

    拉不到镜像的 docker run 三秒就退，判成 FAILED 交给巡检的话，一侧的三次重跑预算
    十几秒烧光，紧接着整道题按「达到上限」自动废弃 —— 一次镜像丢失能在几分钟里把整个
    队列废掉。所以退回排队保住 attempt，并停下出队等人补镜像。
    """
    from app.db import session

    task_id, ids = task_with_runs
    spawned = []

    async def absent(image):
        return False

    async def verify(task_no, side, snapshot):
        raise AssertionError("镜像都不在，不必再去校验起点")

    async def spawn(*a, **k):
        spawned.append(a)
        raise AssertionError("镜像不在还是把容器起起来了")

    wrote: list[tuple[str, str]] = []
    monkeypatch.setattr(runner.dockerx, "image_present", absent)
    monkeypatch.setattr(runner.gsb_repo, "verify_head", verify)
    monkeypatch.setattr(runner.settings_store, "get", lambda k: "img")
    monkeypatch.setattr(runner.settings_store, "get_int", lambda k, d=0: d)
    monkeypatch.setattr(runner.settings_store, "set_one",
                        lambda k, v: wrote.append((k, v)))
    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", spawn)

    asyncio.run(runner.run_side(ids["A"]))

    assert spawned == []
    assert wrote == [("scheduler.paused", "1")]
    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        assert run.status in m.RUN_WAITING
        assert run.attempt == 1          # 重跑预算一次都没消耗
        assert "img" in run.error
        assert run.container_exists is False


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
        assert db.get(m.Task, task_id).status == m.QUEUED
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


def test_manual_stop_survives_a_restart(task_with_runs, monkeypatch, no_git):
    """人按的停止要记在库里，不然重启之后那次停止会被当成异常，这一侧转头被重跑。

    停止接口标记的是内存集合，收尾却可能发生在另一个进程里（重启接管、巡检补记账）。
    只认内存的那份，人看到的就是「我明明停了它，它自己又跑起来了」。
    """
    from app.db import session

    _, ids = task_with_runs
    monkeypatch.setattr(runner.trace, "find_trace_file", lambda d, since=None: None)
    monkeypatch.setattr(runner.trace, "count_traces", lambda d, since=None: 0)
    monkeypatch.setattr(runner.watchdog, "wake", lambda: None)
    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        run.status = m.RUN_RUNNING
        run.stop_requested = True
    # 内存里那份标记随进程一起没了
    runner._manual_stop.clear()

    asyncio.run(runner.finalize(ids["A"], exit_code=137, result_event={}))

    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        assert run.status == m.RUN_INTERRUPTED
        assert run.verdict["process"]["manual_stop"] is True
    # 巡检据此放行，不会把人按的停止当异常重跑
    from app.services import watchdog

    with session() as db:
        assert watchdog.abnormal_reason(db.get(m.TaskRun, ids["A"])) == ""


# ---------------- 重新接管还在跑的容器 ----------------

def test_split_log_ts_handles_docker_nanoseconds():
    ts, text = runner.split_log_ts('2026-09-18T04:46:05.780650123Z {"type":"system"}')
    assert (ts.hour, ts.minute, ts.second, ts.microsecond) == (4, 46, 5, 780650)
    assert text == '{"type":"system"}'
    # 没有前缀的行原样返回，不能把正文吃掉
    assert runner.split_log_ts('{"type":"system"}') == (None, '{"type":"system"}')


class _FakeProc:
    def __init__(self, stdout: bytes, stderr: bytes = b""):
        self.stdout = _FakeStream(stdout, 64)
        self.stderr = _FakeStream(stderr, 64)
        self.returncode = 0

    def kill(self):
        pass


def test_attach_run_rebuilds_the_timeline_from_container_logs(task_with_runs, monkeypatch):
    """接管一个还在跑的容器，要把它的输出接回来，而不只是等一个退出码。

    容器是 sibling 容器，后端重启带走的只是读它 stdout 的那根管子。以前这条路径
    什么都不读，于是接管过的运行没有事件、没有 session_id、拿不到 result，界面上
    点进去一片空白，只剩一个时长在跳。
    """
    from app.db import session
    from app.services.dockerx import CmdResult

    task_id, ids = task_with_runs
    run_id = ids["A"]
    with session() as db:
        run = db.get(m.TaskRun, run_id)
        run.status = m.RUN_RUNNING
        run.started_at = m.utc_now()
        # 断点前记下的两条：它们是重放内容的一部分，留着就会重复
        db.add(m.RunEvent(task_id=task_id, side="A", seq=1, kind="lifecycle", summary="启动容器"))
        db.add(m.RunEvent(task_id=task_id, side="A", seq=2, kind="system", summary="会话初始化"))

    logs = (
        b'2026-09-18T04:46:05.780650123Z {"type":"system","subtype":"init","model":"m","cwd":"/workspace"}\n'
        b'2026-09-18T04:46:06.000000000Z {"type":"system","subtype":"thinking_tokens","estimated_tokens":120}\n'
        b'2026-09-18T04:47:00.000000000Z {"type":"assistant","message":{"content":[{"type":"text","text":"start"}]}}\n'
        b'2999-01-01T00:00:00.000000000Z {"type":"result","subtype":"success","num_turns":7,'
        b'"duration_ms":4200,"session_id":"s-1"}\n'
    )

    async def spawn(*args, **kwargs):
        assert args[:3] == ("docker", "logs", "-f")
        return _FakeProc(logs)

    async def fake_run(cmd, *a, **k):
        if "wait" in cmd:
            return CmdResult(0, "0\n", "")
        return CmdResult(1, "", "not a repo")

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(runner.dockerx, "run", fake_run)
    monkeypatch.setattr(runner.trace, "find_trace_file", lambda d, since=None: None)
    monkeypatch.setattr(runner.trace, "count_traces", lambda d, since=None: 0)
    monkeypatch.setattr(runner.watchdog, "wake", lambda: None)
    monkeypatch.setattr(runner.settings_store, "get_int", lambda k, d=0: d)
    pushed = []
    monkeypatch.setattr(runner.bus, "publish", lambda ch, p: pushed.append(p))

    asyncio.run(runner.attach_run(run_id))

    with session() as db:
        events = db.query(m.RunEvent).filter(m.RunEvent.task_id == task_id,
                                             m.RunEvent.side == "A").order_by(m.RunEvent.seq).all()
        kinds = [(e.seq, e.kind) for e in events]
        run = db.get(m.TaskRun, run_id)
        init = next(e for e in events if e.kind == "system")
        session_id, status = run.session_id, run.status
        protocol = run.verdict["protocol"]
        notes = " ".join(run.verdict["notes"])

    # 旧的两条被清掉，seq 从 1 重新编号；思考 token 仍然只推流不落库
    assert kinds == [(1, "lifecycle"), (2, "system"), (3, "assistant"),
                     (4, "result"), (5, "lifecycle")]
    assert "重新接上容器" in events[0].summary
    # 事件的时刻要用容器写那行的时间，不能是重放的此刻
    assert (init.ts.hour, init.ts.minute, init.ts.second) == (4, 46, 5)
    # result 接回来了，于是照正常路径判定，轮次与耗时都有值，不再降级
    assert status == m.RUN_FINISHED
    assert (protocol["num_turns"], protocol["duration_ms"]) == (7, 4200)
    assert session_id == "s-1"
    assert "重新接管" in notes
    # 重放阶段不推流，追平之后发 reload 让界面重新拉一次
    assert [p for p in pushed if p.get("type") == "event" and p["kind"] == "assistant"] == []
    assert any(p.get("type") == "reload" for p in pushed)


def test_attach_run_keeps_old_events_when_logs_are_unreadable(task_with_runs, monkeypatch):
    """日志一行都读不到就什么都不清。断点前那几条是这一侧仅剩的记录，宁可留着。"""
    from app.db import session
    from app.services.dockerx import CmdResult

    task_id, ids = task_with_runs
    run_id = ids["A"]
    with session() as db:
        run = db.get(m.TaskRun, run_id)
        run.status = m.RUN_RUNNING
        run.started_at = m.utc_now()
        db.add(m.RunEvent(task_id=task_id, side="A", seq=1, kind="lifecycle", summary="启动容器"))

    async def spawn(*args, **kwargs):
        return _FakeProc(b"")

    async def fake_run(cmd, *a, **k):
        if "wait" in cmd:
            return CmdResult(0, "137\n", "")
        return CmdResult(1, "", "not a repo")

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(runner.dockerx, "run", fake_run)
    monkeypatch.setattr(runner.trace, "find_trace_file", lambda d, since=None: None)
    monkeypatch.setattr(runner.trace, "count_traces", lambda d, since=None: 0)
    monkeypatch.setattr(runner.watchdog, "wake", lambda: None)
    monkeypatch.setattr(runner.settings_store, "get_int", lambda k, d=0: d)
    monkeypatch.setattr(runner.bus, "publish", lambda ch, p: None)

    asyncio.run(runner.attach_run(run_id))

    with session() as db:
        events = db.query(m.RunEvent).filter(m.RunEvent.task_id == task_id,
                                             m.RunEvent.side == "A").order_by(m.RunEvent.seq).all()
    assert events[0].summary == "启动容器"
    assert any("容器退出" in e.summary for e in events)


# ---------------- 有没有产出，要跟起跑点比 ----------------

def _git_stub(monkeypatch, *, dirty: bool, committed: bool):
    """假 git：dirty 控制有没有未提交改动，committed 控制相对起跑点有没有提交。"""
    from app.services.dockerx import CmdResult

    async def fake(cmd, *a, **k):
        argv = " ".join(cmd)
        if "status" in argv:
            return CmdResult(0, " M src/a.ts\n" if dirty else "", "")
        if "--name-only" in argv:
            return CmdResult(0, "src/a.ts\nsrc/b.ts\n" if committed else "", "")
        if ".." in argv:  # diff --stat base..HEAD
            return CmdResult(0, " src/a.ts | 3 +-\n" if committed else "", "")
        if "diff" in argv:
            return CmdResult(0, " src/a.ts | 3 +-\n" if dirty else "", "")
        return CmdResult(0, "", "")

    monkeypatch.setattr(runner.dockerx, "run", fake)


def _finalize_ok(ids, monkeypatch, tmp_path):
    monkeypatch.setattr(runner.trace, "find_trace_file", lambda d, since=None: tmp_path / "t.jsonl")
    monkeypatch.setattr(runner.trace, "count_traces", lambda d, since=None: 1)
    monkeypatch.setattr(runner.trace, "parse_trace", lambda f: {})
    monkeypatch.setattr(runner.trace, "write_index", lambda *a, **k: None)
    monkeypatch.setattr(runner.shutil, "copy2", lambda *a, **k: None)
    monkeypatch.setattr(runner.watchdog, "wake", lambda: None)
    monkeypatch.setattr(runner.config.TaskPaths, "workspace",
                        property(lambda self: tmp_path))
    (tmp_path / ".git").mkdir(exist_ok=True)
    asyncio.run(runner.finalize(ids["A"], exit_code=0, result_event={"subtype": "success"}))


def test_committed_work_still_counts_as_output(task_with_runs, monkeypatch, tmp_path):
    """产物被 commit 之后工作区就干净了，不能因此判成「什么都没做」。

    推进流程推产物时就会 commit。一旦这一侧需要重新收尾（重启接管、巡检补记账），
    只看 git status 会读出零改动，把一次做满了活的运行判成戛然而止、清掉重跑。
    """
    from app.db import session

    _, ids = task_with_runs
    _git_stub(monkeypatch, dirty=False, committed=True)
    _finalize_ok(ids, monkeypatch, tmp_path)

    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        assert run.verdict["artifact"]["changed_files"] == 2
        assert "起跑点" in run.git_diff_stat


def test_truly_empty_run_is_still_reported_as_empty(task_with_runs, monkeypatch, tmp_path):
    """真的什么都没干，还是要如实报零改动，否则异常判定就瞎了。"""
    from app.db import session

    _, ids = task_with_runs
    _git_stub(monkeypatch, dirty=False, committed=False)
    _finalize_ok(ids, monkeypatch, tmp_path)

    with session() as db:
        run = db.get(m.TaskRun, ids["A"])
        assert run.verdict["artifact"]["changed_files"] == 0
        assert not run.git_diff_stat.strip()
