"""门禁：题面口径、仓库分支、两侧工作区与容器。

外部依赖（docker、git 远端）全部打桩，只测门禁自己的判断逻辑。
"""

import asyncio

import pytest

from app import models as m
from app.services import gate
from app.services.gsb_repo import BranchProbe


def test_normalize_choice_ignores_whitespace():
    assert gate.normalize_choice("0-1 代码生成", gate.QUESTION_TYPES) == "0-1代码生成"
    assert gate.normalize_choice("feature 迭代", gate.QUESTION_TYPES) == "feature迭代"
    assert gate.normalize_choice("Bug修复", gate.QUESTION_TYPES) == "Bug修复"
    assert gate.normalize_choice("随便写的", gate.QUESTION_TYPES) == ""
    assert gate.normalize_choice("", gate.QUESTION_TYPES) == ""


def test_difficulty_options_are_exactly_two():
    assert gate.DIFFICULTIES == ("困难", "地狱")


def _task(**kw):
    base = dict(task_no="07", prompt_hash="h", difficulty="困难",
                question_type="0-1 代码生成", repo_url="https://github.com/acme/widget",
                env_snapshot="https://github.com/acme/widget/commit/" + "a" * 40)
    base.update(kw)
    return m.Task(**base)


def _levels(checks):
    return {c.name: c.level for c in checks}


@pytest.fixture()
def stub(monkeypatch, tmp_path):
    async def ok_daemon():
        return True, "27.0"

    async def yes(*a, **k):
        return True

    async def version(image):
        return "2.1.197"

    async def no_container(name):
        return ""

    async def probe(url):
        return BranchProbe(True, ["A", "B", "main"], "main", "分支合规：A, B, main")

    async def verify(task_no, side, snapshot):
        return {"ok": True, "head": "a" * 40, "dirty": 0, "message": f"{side} 侧就绪"}

    async def label(image, key):
        return "cc"

    monkeypatch.setattr(gate.dockerx, "daemon_ok", ok_daemon)
    monkeypatch.setattr(gate.dockerx, "image_present", yes)
    monkeypatch.setattr(gate.dockerx, "claude_version", version)
    monkeypatch.setattr(gate.dockerx, "image_label", label)
    monkeypatch.setattr(gate.dockerx, "container_state", no_container)
    monkeypatch.setattr(gate.gsb_repo, "probe_branches", probe)
    monkeypatch.setattr(gate.gsb_repo, "verify_head", verify)
    monkeypatch.setattr(gate.settings_store, "is_configured", lambda k: True)
    monkeypatch.setattr(gate.settings_store, "get",
                        lambda k: "" if k == "gate.blacklist" else "img")
    monkeypatch.setattr(gate, "_scan_blacklist", lambda root, pats, limit=20: [])
    monkeypatch.setattr(gate.config, "CODER_ROOT_MOUNT", tmp_path)
    for side in ("A", "B"):
        (tmp_path / "workspace" / "07" / side / ".git").mkdir(parents=True)
        (tmp_path / "出题" / "轨迹" / "07" / side).mkdir(parents=True)
    return tmp_path


def test_all_green_passes(stub):
    checks = asyncio.run(gate.run_checks(_task()))
    assert gate.summarize(checks)["passed"] is True


def test_easy_difficulty_is_blocked(stub):
    checks = asyncio.run(gate.run_checks(_task(difficulty="中等")))
    assert _levels(checks)["difficulty"] == "block"


def test_unknown_question_type_is_blocked(stub):
    checks = asyncio.run(gate.run_checks(_task(question_type="瞎写的类型")))
    assert _levels(checks)["question_type"] == "block"


def test_missing_repo_url_is_blocked(stub):
    checks = asyncio.run(gate.run_checks(_task(repo_url="")))
    assert _levels(checks)["repo_url"] == "block"


def test_bad_branches_are_blocked_with_actual_list(stub, monkeypatch):
    async def probe(url):
        return BranchProbe(
            False, ["main", "dev"], "main", "分支不合规（缺少 A, B），实际分支：main, dev")

    monkeypatch.setattr(gate.gsb_repo, "probe_branches", probe)
    checks = asyncio.run(gate.run_checks(_task()))
    branch = next(c for c in checks if c.name == "branches")
    assert branch.level == "block"
    assert "dev" in branch.message


def test_short_snapshot_is_blocked(stub):
    checks = asyncio.run(gate.run_checks(
        _task(env_snapshot="https://github.com/a/b/commit/abc")))
    assert _levels(checks)["snapshot"] == "block"


def test_both_sides_are_checked_independently(stub, monkeypatch):
    async def verify(task_no, side, snapshot):
        ok = side == "A"
        return {"ok": ok, "head": "a" * 40, "dirty": 0 if ok else 3,
                "message": f"{side} 侧工作区有 3 处改动"}

    monkeypatch.setattr(gate.gsb_repo, "verify_head", verify)
    levels = _levels(asyncio.run(gate.run_checks(_task())))
    assert levels["workspace_A"] == "ok"
    assert levels["workspace_B"] == "block"


def test_nonempty_trace_dir_is_blocked(stub):
    (stub / "出题" / "轨迹" / "07" / "B" / "stale.jsonl").write_text("{}", encoding="utf-8")
    levels = _levels(asyncio.run(gate.run_checks(_task())))
    assert levels["traces_A"] == "ok"
    assert levels["traces_B"] == "block"


def test_existing_container_is_blocked(stub, monkeypatch):
    async def state(name):
        return "exited" if name.endswith("-A") else ""

    monkeypatch.setattr(gate.dockerx, "container_state", state)
    levels = _levels(asyncio.run(gate.run_checks(_task())))
    assert levels["container_A"] == "block"
    assert levels["container_B"] == "ok"


def test_missing_workspace_is_blocked_with_fix_action(stub):
    import shutil

    shutil.rmtree(stub / "workspace" / "07" / "B")
    checks = asyncio.run(gate.run_checks(_task()))
    b = next(c for c in checks if c.name == "workspace_B")
    assert b.level == "block"
    assert b.fix == "clone_sides"


def test_leak_scan_runs_per_side(stub, monkeypatch):
    monkeypatch.setattr(gate, "_scan_blacklist",
                        lambda root, pats, limit=20: ["CLAUDE.md"] if root.endswith("A") else [])
    levels = _levels(asyncio.run(gate.run_checks(_task())))
    assert levels["leak_A"] == "block"
    assert levels["leak_B"] == "ok"


def test_repo_busy_check_is_gone(stub):
    names = {c.name for c in asyncio.run(gate.run_checks(_task()))}
    assert "repo_busy" not in names


def test_prepare_workspaces_clones_both_sides(stub, monkeypatch):
    calls = []

    async def clone(task_no, repo_url, side):
        calls.append(side)
        return {"ok": True, "reused": False, "message": f"已 clone {side}"}

    monkeypatch.setattr(gate.gsb_repo, "clone_side", clone)
    r = asyncio.run(gate.prepare_workspaces(_task()))
    assert r["ok"] is True
    assert calls == ["A", "B"]


def test_prepare_workspaces_stops_on_bad_branches(stub, monkeypatch):
    called = []

    async def probe(url):
        return BranchProbe(False, ["main"], "main", "缺少 A, B")

    async def clone(task_no, repo_url, side):
        called.append(side)
        return {"ok": True, "reused": False, "message": ""}

    monkeypatch.setattr(gate.gsb_repo, "probe_branches", probe)
    monkeypatch.setattr(gate.gsb_repo, "clone_side", clone)
    r = asyncio.run(gate.prepare_workspaces(_task()))
    assert r["ok"] is False
    # 分支不合规就不该去 clone，clone 失败的报错会盖住真正的原因
    assert called == []


def test_prepare_workspaces_fails_if_one_side_fails(stub, monkeypatch):
    async def clone(task_no, repo_url, side):
        ok = side == "A"
        return {"ok": ok, "reused": False, "message": f"{side} 侧结果"}

    monkeypatch.setattr(gate.gsb_repo, "clone_side", clone)
    r = asyncio.run(gate.prepare_workspaces(_task()))
    assert r["ok"] is False
    assert "B 侧结果" in r["message"]
