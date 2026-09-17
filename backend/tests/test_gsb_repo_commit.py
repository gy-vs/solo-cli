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
    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["repo"], "A", cloned["sha"], message="m"))
    # 先确认真的推成功了：否则前置校验一旦提前失败，本地与远端双双停在初始 sha，
    # 下面的「相等」照样成立，测试就成了假阳性
    assert r["ok"] is True, r["message"]
    remote = _git(cloned["url"], "rev-parse", "refs/heads/A")
    local = _git(cloned["ws"], "rev-parse", "HEAD")
    assert remote == local
    assert local != cloned["sha"]
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
    # 被拦下就不能推出去，远端 A 必须还停在初始快照
    assert _git(cloned["url"], "rev-parse", "refs/heads/A") == cloned["sha"]


def test_commit_and_push_refuses_non_github_https_origin(cloned):
    """origin 被换成非 github 的 https 地址时必须拒绝。

    credential helper 无条件交出 token，放行就等于把 token 送给那个主机；
    而且 permalink 是按题块地址拼的 github 链接，和实际推送目标对不上。
    报错里也不许回显那个主机名。
    """
    _git(cloned["ws"], "remote", "set-url", "origin", "https://evil.example.com/x/y.git")
    (cloned["ws"] / "feature.py").write_text("print(1)\n", encoding="utf-8")
    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["repo"], "A", cloned["sha"], message="m"))
    assert r["ok"] is False
    assert "evil.example.com" not in r["message"]
    assert "acme/widget" in r["message"]
    # 没推出去也没提交：工作区改动还在，原裸仓库的 A 也没动
    assert _git(cloned["url"], "rev-parse", "refs/heads/A") == cloned["sha"]


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


def test_reset_side_aborts_when_backup_fails(cloned, monkeypatch):
    """备份 ref 写不进去时不能继续 reset：模型产出只有这一份，抹掉就没了。"""
    (cloned["ws"] / "one.py").write_text("1\n", encoding="utf-8")
    _git(cloned["ws"], "add", "-A")
    _git(cloned["ws"], "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "stray")
    stray = _git(cloned["ws"], "rev-parse", "HEAD")
    (cloned["ws"] / "dirt.txt").write_text("x", encoding="utf-8")

    real_git = gsb_repo._git

    async def failing_update_ref(ws, *args, **kw):
        if args and args[0] == "update-ref":
            return gsb_repo.dockerx.CmdResult(128, "", "fatal: cannot lock ref")
        return await real_git(ws, *args, **kw)

    monkeypatch.setattr(gsb_repo, "_git", failing_update_ref)
    r = asyncio.run(gsb_repo.reset_side("07", "A", cloned["sha"]))
    assert r["ok"] is False
    assert r["backup"] == ""
    assert "备份" in r["message"]
    # git 的 stderr 不许透传
    assert "cannot lock ref" not in r["message"]
    # reset 没执行：HEAD 和工作区里的东西都原样保留
    assert _git(cloned["ws"], "rev-parse", "HEAD") == stray
    assert (cloned["ws"] / "dirt.txt").exists()
    assert (cloned["ws"] / "one.py").exists()


def test_backup_head_keeps_both_backups_within_same_second(cloned):
    """同一秒内对同一侧连续备份两次，两份 ref 都得在，不能后一份覆盖前一份。"""
    (cloned["ws"] / "one.py").write_text("1\n", encoding="utf-8")
    _git(cloned["ws"], "add", "-A")
    _git(cloned["ws"], "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "stray")

    async def twice():
        return (await gsb_repo.backup_head("07", "A", cloned["sha"]),
                await gsb_repo.backup_head("07", "A", cloned["sha"]))

    (ref1, err1), (ref2, err2) = asyncio.run(twice())
    assert err1 == "" and err2 == ""
    assert ref1 and ref2 and ref1 != ref2
    refs = _git(cloned["ws"], "for-each-ref", "--format=%(refname)", gsb_repo.BACKUP_NS)
    assert ref1 in refs.splitlines() and ref2 in refs.splitlines()


def test_commit_message_mentions_side_and_session():
    msg = gsb_repo.commit_message("07", "A", "sess-1")
    assert "07" in msg and "A" in msg and "sess-1" in msg
