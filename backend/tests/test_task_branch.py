"""领取前自动落到题目分支。

手点一次「切到题目分支」也能办，但批量领取时没人愿意点十下；
唯一不能自动的情况是工作区还有未提交改动——那会把改动带到别的分支上去。
"""

import pytest

from app import config
from app.services import dockerx, repo


async def git(ws, *args) -> str:
    r = await dockerx.run(["git", "-C", str(ws), *args], timeout=60)
    assert r.ok, f"git {' '.join(args)} 失败：{r.err or r.out}"
    return r.out.strip()


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path / "coder")
    monkeypatch.setattr(repo.settings_store, "get", lambda key, default="": "q{no}")
    d = config.TaskPaths("04").workspace
    d.mkdir(parents=True)
    return d


async def _init(d, *, branch: str = "q04") -> None:
    await git(d, "init", "-q", "-b", "main")
    (d / "README.md").write_text("初始\n", encoding="utf-8")
    await git(d, "add", "-A")
    await git(d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "snapshot")
    if branch:
        await git(d, "checkout", "-q", "-b", branch)
        await git(d, "checkout", "-q", "main")


@pytest.mark.asyncio
async def test_switches_when_clean(ws):
    await _init(ws)
    r = await repo.ensure_task_branch("04")
    assert r["ok"] and r["branch"] == "q04"
    assert await git(ws, "rev-parse", "--abbrev-ref", "HEAD") == "q04"


@pytest.mark.asyncio
async def test_keeps_hands_off_when_dirty(ws):
    await _init(ws)
    (ws / "half-done.py").write_text("x = 1\n", encoding="utf-8")

    r = await repo.ensure_task_branch("04")
    assert not r["ok"] and r["skipped"]
    assert await git(ws, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert (ws / "half-done.py").exists()


@pytest.mark.asyncio
async def test_no_branch_no_action(ws):
    await _init(ws, branch="")
    r = await repo.ensure_task_branch("04")
    assert r["skipped"] and "q04" in r["message"]
    assert await git(ws, "rev-parse", "--abbrev-ref", "HEAD") == "main"
