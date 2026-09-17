"""题目分支上的提交与还原。

约定是一个项目里一道题一个分支（q04 之类），做题前切过去，上传后把这一轮的改动提交到
同一个分支。还原会丢掉那次提交，所以必须先备份出去，否则重跑一次上一轮就找不回来了。
"""

import pytest

from app import config
from app.models import Task
from app.services import dockerx, gate, repo

SNAP = "https://github.com/gy-vs/markdown-engine/commit/{sha}"


async def git(ws, *args) -> str:
    r = await dockerx.run(["git", "-C", str(ws), *args], timeout=60)
    assert r.ok, f"git {' '.join(args)} 失败：{r.err or r.out}"
    return r.out.strip()


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """题 04 的工作区：main + q04 两个分支，当前在 q04 上，和真实 clone 出来的一致。"""
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path / "coder")
    monkeypatch.setattr(repo.settings_store, "get", lambda key, default="": "q{no}")
    d = config.TaskPaths("04").workspace
    d.mkdir(parents=True)
    return d


async def _init_repo(d, *, branch: str = "q04") -> str:
    await git(d, "init", "-q", "-b", "main")
    (d / "README.md").write_text("初始\n", encoding="utf-8")
    await git(d, "add", "-A")
    await git(d, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "snapshot")
    if branch:
        await git(d, "checkout", "-q", "-b", branch)
    return await git(d, "rev-parse", "HEAD")


def _dirty(d) -> None:
    (d / "README.md").write_text("初始\n模型补的说明\n", encoding="utf-8")
    (d / "parser.py").write_text("def parse():\n    return 1\n", encoding="utf-8")


def _info(sha: str) -> repo.CommitInfo:
    return repo.CommitInfo(task_no="04", session_id="3f665232-ac02-4002", question_type="Feature 迭代",
                           env_snapshot=SNAP.format(sha=sha))


@pytest.mark.asyncio
async def test_commit_goes_to_task_branch(ws):
    sha = await _init_repo(ws)
    _dirty(ws)

    res = await repo.commit_after_upload(_info(sha))
    assert res["ok"], res
    assert res["branch"] == "q04"
    assert res["changed_files"] == 2

    assert await git(ws, "rev-parse", "--abbrev-ref", "HEAD") == "q04"
    assert await git(ws, "status", "--porcelain") == ""
    assert "parser.py" in await git(ws, "show", "--name-only", "--format=", "q04")
    assert await git(ws, "rev-parse", "main") == sha     # 别的分支没被动


@pytest.mark.asyncio
async def test_reset_backs_up_the_delivered_commit(ws):
    sha = await _init_repo(ws)
    _dirty(ws)
    res = await repo.commit_after_upload(_info(sha))

    task = Task(task_no="04", prompt_hash="h", user_prompt="p", env_snapshot=SNAP.format(sha=sha))
    r = await gate.reset_to_snapshot(task)
    assert r["ok"], r
    assert "refs/solo-backup/q04-" in r["message"]

    assert await git(ws, "rev-parse", "HEAD") == sha
    assert await git(ws, "rev-parse", "--abbrev-ref", "HEAD") == "q04"   # 还在题目分支上
    assert not (ws / "parser.py").exists()
    # 上一轮交付的提交还能捞回来
    ref = r["message"].split("备份在 ")[1].strip()
    assert await git(ws, "rev-parse", ref) == res["commit"]


@pytest.mark.asyncio
async def test_detached_head_refuses_to_commit(ws):
    sha = await _init_repo(ws)
    await git(ws, "checkout", "-q", "--detach", sha)
    _dirty(ws)

    res = await repo.commit_after_upload(_info(sha))
    assert not res["ok"] and "游离 HEAD" in res["message"]
    assert await git(ws, "status", "--porcelain") != ""   # 改动还留着，没被吞掉


@pytest.mark.asyncio
async def test_wrong_branch_refuses_to_commit(ws):
    sha = await _init_repo(ws)
    await git(ws, "checkout", "-q", "main")
    _dirty(ws)

    res = await repo.commit_after_upload(_info(sha))
    assert not res["ok"] and "q04" in res["message"]


@pytest.mark.asyncio
async def test_commit_skips_clean_workspace(ws):
    sha = await _init_repo(ws)
    res = await repo.commit_after_upload(_info(sha))
    assert res == {"ok": True, "skipped": True, "message": "工作区没有改动，跳过提交"}


@pytest.mark.asyncio
async def test_switch_to_task_branch(ws):
    await _init_repo(ws, branch="q04")
    await git(ws, "checkout", "-q", "main")
    assert (await repo.branch_state("04"))["current"] == "main"

    r = await repo.switch_to_task_branch("04")
    assert r["ok"] and r["branch"] == "q04"
    assert await git(ws, "rev-parse", "--abbrev-ref", "HEAD") == "q04"


@pytest.mark.asyncio
async def test_missing_task_branch_is_reported(ws):
    await _init_repo(ws, branch="")
    r = await repo.switch_to_task_branch("04")
    assert not r["ok"] and "q04" in r["message"]
