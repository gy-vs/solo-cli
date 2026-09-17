"""续跑轮次：路径隔离与续跑指令组装。

镜像的 entrypoint 拒绝 --resume、拒绝复用容器，还要求挂进去的轨迹目录必须是空的，
所以第 2 轮必须换容器名和换一个干净的轨迹目录；workspace 反过来必须沿用，
续跑的前提正是接着上一轮改过的代码往下做。
"""

import asyncio

from app.config import TaskPaths
from app.models import CONTINUABLE, FAILED, FINISHED, INTERRUPTED, QUEUED, RUNNING, TIMEOUT, Task


def test_first_round_paths_unchanged():
    """首轮不能带后缀，否则现有的题全都对不上原来的目录和容器。"""
    p = TaskPaths("01")
    assert p.round_suffix == ""
    assert p.container_name == "solo-cc-01"
    assert p.traces.name == "01"
    assert p.export.name == "01"


def test_later_rounds_are_isolated():
    first, second, third = TaskPaths("01"), TaskPaths("01", 2), TaskPaths("01", 3)
    assert [p.container_name for p in (second, third)] == ["solo-cc-01-r2", "solo-cc-01-r3"]
    # 轨迹目录必须是平级的兄弟目录：放成子目录的话首轮的 rglob 会把后面几轮一起扫出来
    assert second.traces.parent == first.traces.parent
    assert {second.traces.name, third.traces.name} == {"01-r2", "01-r3"}
    assert len({p.traces for p in (first, second, third)}) == 3


def test_workspace_is_shared_across_rounds():
    """续跑就是要接着上一轮改过的代码，工作区不能带轮次后缀。"""
    assert TaskPaths("01", 3).workspace == TaskPaths("01").workspace


def test_round_no_is_clamped():
    for bad in (0, -1, None):
        assert TaskPaths("01", bad).round_suffix == ""


def test_continuable_statuses():
    for st in (FINISHED, FAILED, TIMEOUT, INTERRUPTED):
        assert st in CONTINUABLE, st
    # 还在跑或还在排队的不能再排一轮，否则同一道题会有两个容器抢同一个工作区
    for st in (RUNNING, QUEUED, "AVAILABLE", "UPLOADED", "DONE"):
        assert st not in CONTINUABLE, st


def _task(**kw) -> Task:
    t = Task(task_no="01", prompt_hash="h", user_prompt="把 linkify 的 source map 补上")
    for k, v in kw.items():
        setattr(t, k, v)
    return t


def test_continue_prompt_carries_context(monkeypatch):
    """全新会话读不到上一轮对话，所以原始需求、已有改动、本轮指令都得写进 prompt。"""
    from app.services import runner

    async def fake_run(cmd, timeout=0):  # noqa: ANN001, ARG001
        out = " lib/linkify.mjs | 12 +++--\n" if "diff" in cmd else " M lib/linkify.mjs\n"
        return type("R", (), {"ok": True, "out": out, "err": ""})()

    monkeypatch.setattr(runner.dockerx, "run", fake_run)
    paths = TaskPaths("01", 2)
    monkeypatch.setattr(type(paths), "workspace", property(lambda self: _FakeWs(has_git=True)))

    t = _task(status=FAILED, error="HTTP 504 gateway timeout", continue_prompt="接着把剩下的用例补完")
    out = asyncio.run(runner.build_continue_prompt(t, paths))

    assert "第 2 轮" in out
    assert "504" in out                       # 上一轮为什么断
    assert "把 linkify 的 source map 补上" in out   # 原始需求
    assert "lib/linkify.mjs" in out           # 上一轮留下的改动
    assert "接着把剩下的用例补完" in out        # 本轮指令


def test_continue_prompt_defaults_when_blank(monkeypatch):
    from app.services import runner

    async def fake_run(cmd, timeout=0):  # noqa: ANN001, ARG001
        return type("R", (), {"ok": True, "out": "", "err": ""})()

    monkeypatch.setattr(runner.dockerx, "run", fake_run)
    paths = TaskPaths("01", 2)
    monkeypatch.setattr(type(paths), "workspace", property(lambda self: _FakeWs(has_git=False)))

    out = asyncio.run(runner.build_continue_prompt(_task(status=TIMEOUT), paths))
    assert "继续完成上面的原始需求" in out


def test_reset_purges_archived_dirs(tmp_path, monkeypatch):
    """还原要连历次归档的目录一起清掉，否则续跑几轮再还原几次会攒一堆。"""
    from app import config
    from app.services import task_reset

    traces_root = tmp_path / "轨迹"
    for name in ("01", "01-r2", "01.archived-20260101-000000",
                 "01-r2.archived-20260101-000000", "02", "02.archived-20260101-000000"):
        (traces_root / name).mkdir(parents=True)
        (traces_root / name / "x.jsonl").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path)
    monkeypatch.setattr(config, "TRACES_DIR", "轨迹")

    ok, msg = task_reset._purge_archived("01")

    assert ok, msg
    left = sorted(p.name for p in traces_root.iterdir())
    # 只清 01 自己的归档，当前轮的目录留给上一步删，别人的题一律不碰
    assert left == ["01", "01-r2", "02", "02.archived-20260101-000000"]


def test_purge_is_quiet_when_nothing_archived(tmp_path, monkeypatch):
    from app import config
    from app.services import task_reset

    (tmp_path / "轨迹" / "01").mkdir(parents=True)
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path)
    monkeypatch.setattr(config, "TRACES_DIR", "轨迹")

    ok, msg = task_reset._purge_archived("01")
    assert ok and "没有历史归档" in msg


class _FakeWs:
    """假装工作区，has_git 决定 build_continue_prompt 走不走 git 那条分支。"""

    def __init__(self, has_git: bool = True):
        self.has_git = has_git

    def __truediv__(self, other):  # noqa: ANN001, ARG002
        return _Probe(self.has_git)

    def __str__(self) -> str:
        return "/host/coder/workspace/01"


class _Probe:
    def __init__(self, ok: bool):
        self.ok = ok

    def exists(self) -> bool:
        return self.ok
