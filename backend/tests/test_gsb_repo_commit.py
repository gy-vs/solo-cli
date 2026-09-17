"""gsb_repo 后半部分：回退初始快照、产物提交并推送。

远端用本地裸仓库模拟，不联网。重点守两条平台规则：产物提交的父提交必须是初始快照（G3），
以及回退前领先快照的提交必须先备份、别把模型跑出来的东西直接抹掉。

题块地址统一用 github 地址：permalink 要靠它拼 org/repo；推送走 clone 时留下的 origin，
所以 origin 指向本地裸仓库也能把整条 push 链路走通。
"""

import asyncio
import subprocess

import pytest

from app import config
from app.services import gsb_repo


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture()
def cloned(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    (work / "readme.md").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init")
    sha = _git(work, "rev-parse", "HEAD")
    _git(work, "branch", "A")
    _git(work, "branch", "B")
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(work), str(bare)],
                   check=True, capture_output=True, text=True)
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path / "coder")
    monkeypatch.setattr(gsb_repo.settings_store, "get", lambda k: "")
    asyncio.run(gsb_repo.clone_side("07", str(bare), "A"))
    return {"url": str(bare), "sha": sha, "ws": config.TaskPaths("07", "A").workspace,
            "repo": "https://github.com/acme/widget"}


def test_commit_and_push_returns_permalink(cloned):
    (cloned["ws"] / "feature.py").write_text("print(1)\n", encoding="utf-8")
    r = asyncio.run(gsb_repo.commit_and_push(
        "07", "https://github.com/acme/widget", "A", cloned["sha"], message="m"))
    assert r["ok"] is True, r["message"]
    assert r["changed_files"] == 1
    assert gsb_repo.COMMIT_URL_RE.match(r["url"]), r["url"]
    assert r["url"].endswith(r["sha"])


def test_commit_and_push_writes_to_the_side_branch(cloned):
    (cloned["ws"] / "feature.py").write_text("print(1)\n", encoding="utf-8")
    asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["repo"], "A", cloned["sha"], message="m"))
    remote = _git(cloned["url"], "rev-parse", "refs/heads/A")
    local = _git(cloned["ws"], "rev-parse", "HEAD")
    assert remote == local
    # B 分支不许被动到
    assert _git(cloned["url"], "rev-parse", "refs/heads/B") == cloned["sha"]


def test_commit_and_push_refuses_empty_worktree(cloned):
    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["repo"], "A", cloned["sha"], message="m"))
    assert r["ok"] is False
    assert "没有改动" in r["message"]


def test_commit_and_push_refuses_unparseable_repo_url(cloned):
    (cloned["ws"] / "feature.py").write_text("print(1)\n", encoding="utf-8")
    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["url"], "A", cloned["sha"], message="m"))
    assert r["ok"] is False
    assert "org/repo" in r["message"]
    # 没推出去，远端 A 还停在初始快照
    assert _git(cloned["url"], "rev-parse", "refs/heads/A") == cloned["sha"]


def test_commit_and_push_refuses_foreign_origin_and_hides_url(cloned):
    """目录里的 origin 被换成别的仓库时不能推，报错里也不许回显 origin 原始地址。"""
    fake = "ghp_FAKE_TOKEN_123"
    _git(cloned["ws"], "remote", "set-url", "origin",
         f"https://x-access-token:{fake}@github.com/other/place.git")
    (cloned["ws"] / "feature.py").write_text("print(1)\n", encoding="utf-8")
    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["repo"], "A", cloned["sha"], message="m"))
    assert r["ok"] is False
    assert "other/place" in r["message"] and "acme/widget" in r["message"]
    assert fake not in r["message"]
    assert "x-access-token" not in r["message"]


def test_commit_and_push_refuses_wrong_parent(cloned):
    """已经有一个多余提交时，新提交的父提交就不是初始快照了，必须拦住（规则 G3）。"""
    (cloned["ws"] / "one.py").write_text("1\n", encoding="utf-8")
    _git(cloned["ws"], "add", "-A")
    _git(cloned["ws"], "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "stray")
    (cloned["ws"] / "two.py").write_text("2\n", encoding="utf-8")
    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["repo"], "A", cloned["sha"], message="m"))
    assert r["ok"] is False
    assert "父提交" in r["message"]
    # 被拦下就不能推出去，远端 A 必须还停在初始快照
    assert _git(cloned["url"], "rev-parse", "refs/heads/A") == cloned["sha"]


def test_reset_side_restores_snapshot_and_backs_up(cloned):
    (cloned["ws"] / "one.py").write_text("1\n", encoding="utf-8")
    _git(cloned["ws"], "add", "-A")
    _git(cloned["ws"], "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "stray")
    (cloned["ws"] / "dirt.txt").write_text("x", encoding="utf-8")
    r = asyncio.run(gsb_repo.reset_side("07", "A", cloned["sha"]))
    assert r["ok"] is True
    assert _git(cloned["ws"], "rev-parse", "HEAD") == cloned["sha"]
    assert not (cloned["ws"] / "dirt.txt").exists()
    assert r["backup"].startswith("refs/solo-backup/")
    assert _git(cloned["ws"], "rev-parse", r["backup"]) != cloned["sha"]


def test_reset_side_on_clean_snapshot_is_noop(cloned):
    r = asyncio.run(gsb_repo.reset_side("07", "A", cloned["sha"]))
    assert r["ok"] is True
    assert r["backup"] == ""


def test_commit_message_mentions_side_and_session():
    msg = gsb_repo.commit_message("07", "A", "sess-1")
    assert "07" in msg and "A" in msg and "sess-1" in msg
