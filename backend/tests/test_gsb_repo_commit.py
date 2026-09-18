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


def test_already_committed_artifact_can_still_be_pushed(cloned):
    """产物上轮就提交过、工作区已经干净时，还得能推上去。

    提交成了但推送没成、或者收尾重来一次，都会走到这儿。只看 git status 会读出零改动，
    把一次做满了活的运行判成「没有产出」，这道题就再也推不出去了。
    """
    (cloned["ws"] / "done.py").write_text("ok\n", encoding="utf-8")
    _git(cloned["ws"], "add", "-A")
    _git(cloned["ws"], "-c", f"user.name={gsb_repo.COMMIT_USER}",
         "-c", f"user.email={gsb_repo.COMMIT_EMAIL}", "commit", "-m", "solo 07 · A")

    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["repo"], "A", cloned["sha"], message="m"))

    assert r["ok"] is True, r.get("message")
    assert _git(cloned["ws"], "rev-parse", "HEAD^").lower() == cloned["sha"].lower()


def test_leftover_changes_are_folded_into_the_one_artifact_commit(cloned):
    """已经提交过又冒出新改动时要并进原提交，不能追加第二个。

    规则 G3 要的是初始快照之上恰好一个提交，多一个父提交就对不上了。
    """
    (cloned["ws"] / "done.py").write_text("ok\n", encoding="utf-8")
    _git(cloned["ws"], "add", "-A")
    _git(cloned["ws"], "-c", f"user.name={gsb_repo.COMMIT_USER}",
         "-c", f"user.email={gsb_repo.COMMIT_EMAIL}", "commit", "-m", "solo 07 · A")
    (cloned["ws"] / "late.py").write_text("late\n", encoding="utf-8")

    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["repo"], "A", cloned["sha"], message="m"))

    assert r["ok"] is True, r.get("message")
    # 并进去了就只有一个提交，父提交仍是初始快照
    assert _git(cloned["ws"], "rev-parse", "HEAD^").lower() == cloned["sha"].lower()
    assert r["changed_files"] == 2


def test_a_repo_commit_hook_cannot_block_the_archive(cloned):
    """仓库自己的提交钩子不该挡住产物存档。

    husky 之类的钩子要 npx、要装依赖，这个容器里没有也不该有；
    它们是给写代码的人用的，而这里只是把跑出来的产物存起来。
    """
    hooks = cloned["ws"] / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'npx: not found' >&2\nexit 127\n", encoding="utf-8")
    hook.chmod(0o755)
    (cloned["ws"] / "one.py").write_text("1\n", encoding="utf-8")

    r = asyncio.run(gsb_repo.commit_and_push(
        "07", cloned["repo"], "A", cloned["sha"], message="m"))

    assert r["ok"] is True, r.get("message")


# ---------------- push 失败要说人话，但不能带出 token ----------------

@pytest.mark.parametrize("err, expect", [
    ("timeout after 300s: git -C /ws -c credential.helper=!f(){ echo password=ghp_SECRET; } push",
     "超时"),
    ("! [rejected] HEAD -> B (non-fast-forward)", "领先"),
    ("remote: Permission denied\nfatal: Authentication failed for 'https://github.com/a/b'",
     "认证"),
    ("fatal: could not resolve host: github.com", "连不上"),
])
def test_push_failure_is_explained_without_leaking_the_token(err, expect):
    """网络抖一下也会走到失败分支，一律说成「检查写权限」会把人带偏。

    同时原文一个字都不能透传：超时那条 err 里拼着完整命令行，token 就在里面。
    """
    msg = gsb_repo.push_failure(gsb_repo.dockerx.CmdResult(1, "", err))
    assert expect in msg
    assert "ghp_" not in msg and "credential" not in msg


def test_an_unrecognised_push_failure_still_says_nothing_secret():
    msg = gsb_repo.push_failure(gsb_repo.dockerx.CmdResult(1, "", "password=ghp_SECRET boom"))
    assert "ghp_" not in msg
    assert msg


# ---------------- 重跑必须站在跟第一次跑一模一样的起点上 ----------------

def _remote(cloned):
    """走 file:// 而不是裸路径：git 对本地路径会拿硬链接把整个对象库搬过来，
    那是本地 clone 特有的优化。线上是 https，--single-branch 只会收到主干可达的对象，
    file:// 走的是同一条传输路径，这样测出来的才是线上的行为。"""
    return f"file://{cloned['url']}"


def _fake_previous_run(ws, url):
    """造一个「上一跑」：改文件、提交产物、推到这一侧的分支。"""
    (ws / "leak.py").write_text("上一跑写的\n", encoding="utf-8")
    _git(ws, "add", "-A")
    _git(ws, "-c", f"user.name={gsb_repo.COMMIT_USER}",
         "-c", f"user.email={gsb_repo.COMMIT_EMAIL}", "commit", "-m", "solo 07 · A")
    sha = _git(ws, "rev-parse", "HEAD")
    _git(ws, "push", "origin", "HEAD:refs/heads/A")
    return sha


def test_rebuild_leaves_no_trace_of_the_previous_run(cloned):
    """重建之后，仓库里查不到上一跑的任何东西。

    这是重跑能不能作数的前提：模型只要能从 git log --all、reflog 或者远端分支上
    看见上一跑改过什么，这一跑就不是独立的，两次跑也就没法比了。
    """
    ws = cloned["ws"]
    stray = _fake_previous_run(ws, cloned["url"])

    r = asyncio.run(gsb_repo.rebuild_side("07", _remote(cloned), "A", cloned["sha"]))
    assert r["ok"] is True, r["message"]

    assert _git(ws, "rev-parse", "HEAD").lower() == cloned["sha"].lower()
    assert _git(ws, "status", "--porcelain", "--untracked-files=all") == ""
    assert not (ws / "leak.py").exists()
    # 提交对象本身也不该在新的 .git 里 —— 只是看不见还不够，捞得出来就还是看得见
    assert stray not in _git(ws, "log", "--all", "--format=%H")
    assert subprocess.run(["git", "-C", str(ws), "cat-file", "-e", stray],
                          capture_output=True).returncode != 0
    # 悬垂对象也算：git fsck --lost-found 能把没有 ref 指着的提交捞出来
    assert "dangling commit" not in _git(ws, "fsck", "--lost-found")


def test_rebuild_also_winds_the_remote_branch_back(cloned):
    """远端分支也要退回去，否则下一次 clone 又把上一跑的产物带回来。"""
    ws = cloned["ws"]
    _fake_previous_run(ws, cloned["url"])

    r = asyncio.run(gsb_repo.rebuild_side("07", _remote(cloned), "A", cloned["sha"]))
    assert r["ok"] is True, r["message"]

    remote = _git(ws, "ls-remote", "origin", "refs/heads/A")
    assert remote.split()[0].lower() == cloned["sha"].lower()


def test_rebuild_keeps_the_previous_run_somewhere_else(cloned):
    """上一跑的产物是判「为什么异常」的材料，要留，但不能留在重跑的工作区里。"""
    ws = cloned["ws"]
    _fake_previous_run(ws, cloned["url"])

    r = asyncio.run(gsb_repo.rebuild_side("07", _remote(cloned), "A", cloned["sha"]))
    assert r["ok"] is True, r["message"]
    assert r["archived"], "上一跑没留底"

    kept = ws.with_name(r["archived"])
    assert (kept / "leak.py").exists()
    assert kept.parent == ws.parent and kept != ws


def test_rebuild_from_a_clean_side_needs_no_archive(cloned):
    """什么都没提交过的一侧直接删掉重来，不用留底，免得白占磁盘。"""
    (cloned["ws"] / "scratch.txt").write_text("没提交的草稿\n", encoding="utf-8")

    r = asyncio.run(gsb_repo.rebuild_side("07", _remote(cloned), "A", cloned["sha"]))
    assert r["ok"] is True, r["message"]
    assert not r["archived"]
    assert not (cloned["ws"] / "scratch.txt").exists()


def test_rebuild_refuses_a_snapshot_that_is_not_on_the_trunk(cloned):
    """初始快照不在主干历史里就停下来，别悄悄从别的地方开分支。"""
    r = asyncio.run(gsb_repo.rebuild_side("07", _remote(cloned), "A", "f" * 40))
    assert r["ok"] is False
    assert "主干" in r["message"]
