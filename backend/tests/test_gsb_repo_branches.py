"""gsb_repo 前半部分：地址解析、远端分支探测、双分支 clone、做题前状态校验。

远端用本地裸仓库模拟，不联网；token 相关验证纯函数行为，以及 config / 报错里不留痕迹。
"""

import asyncio
import subprocess

import pytest

from app import config
from app.services import gsb_repo


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True,
                   capture_output=True, text=True)


@pytest.fixture()
def origin(tmp_path, monkeypatch):
    """造一个本地裸仓库当远端，带 main/A/B 三个分支，都指向同一个初始提交。"""
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    (work / "readme.md").write_text("hello\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init")
    sha = subprocess.run(["git", "-C", str(work), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    _git(work, "branch", "A")
    _git(work, "branch", "B")
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "--bare", str(work), str(bare)],
                   check=True, capture_output=True, text=True)
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path / "coder")
    monkeypatch.setattr(config, "CODER_ROOT_HOST", str(tmp_path / "coder"))
    monkeypatch.setattr(gsb_repo.settings_store, "get", lambda k: "")
    return {"url": str(bare), "sha": sha}


def test_repo_slug_and_commit_url():
    url = "https://github.com/acme/widget.git"
    assert gsb_repo.repo_slug(url) == "acme/widget"
    sha = "a" * 40
    assert gsb_repo.commit_url(url, sha) == f"https://github.com/acme/widget/commit/{sha}"
    assert gsb_repo.COMMIT_URL_RE.match(gsb_repo.commit_url(url, sha))


def test_repo_slug_handles_ssh_and_trailing_slash():
    assert gsb_repo.repo_slug("git@github.com:acme/widget.git") == "acme/widget"
    assert gsb_repo.repo_slug("https://github.com/acme/widget/") == "acme/widget"
    assert gsb_repo.repo_slug("not-a-url") == ""


def test_parse_repo_url_from_meta():
    assert gsb_repo.parse_repo_url({"仓库": "https://github.com/acme/widget"}) == \
        "https://github.com/acme/widget"
    assert gsb_repo.parse_repo_url({}) == ""


def test_parse_repo_url_drops_trailing_note():
    """题面里地址后面跟着括号说明，连说明一起存会让 clone 与同项目判定一起失效。"""
    meta = {"仓库": "https://github.com/acme/widget（本题专属，分支只有 main / A / B）"}
    assert gsb_repo.parse_repo_url(meta) == "https://github.com/acme/widget"
    assert gsb_repo.repo_slug(gsb_repo.parse_repo_url(meta)) == "acme/widget"


def test_parse_repo_url_keeps_non_url_value():
    """本地裸仓库路径没有 scheme，按原值留着。"""
    assert gsb_repo.parse_repo_url({"仓库": "/tmp/bare/widget.git"}) == "/tmp/bare/widget.git"


def test_first_url_cleans_snapshot_link():
    """快照链接后面也跟着括号说明，脏着存会让 snapshot_sha 认不出 SHA。"""
    sha = "f" * 40
    raw = f"https://github.com/acme/widget/commit/{sha}（A、B 两侧共用）"
    assert gsb_repo.first_url(raw) == f"https://github.com/acme/widget/commit/{sha}"
    assert gsb_repo.snapshot_sha(gsb_repo.first_url(raw)) == sha


def test_snapshot_sha():
    sha = "b" * 40
    assert gsb_repo.snapshot_sha(f"https://github.com/a/b/commit/{sha}") == sha
    assert gsb_repo.snapshot_sha("https://github.com/a/b/commit/short") == ""


def test_authed_url_injects_token():
    got = gsb_repo.authed_url("https://github.com/acme/widget", "tok")
    assert got == "https://x-access-token:tok@github.com/acme/widget"
    # 没 token 就原样返回，本地路径也不许被改坏
    assert gsb_repo.authed_url("/tmp/origin.git", "tok") == "/tmp/origin.git"


def test_credential_args_only_for_github_https_with_token(monkeypatch):
    monkeypatch.setattr(gsb_repo, "_token", lambda: "ghp_FAKE_TOKEN_123")
    args = gsb_repo.credential_args("https://github.com/acme/widget")
    assert len(args) == 2
    assert args[0] == "-c"
    assert args[1].startswith("credential.helper=")
    assert "ghp_FAKE_TOKEN_123" in args[1]
    assert "x-access-token" in args[1]
    # 本地路径 / ssh 地址不走 https 凭据，helper 传进去只会让 git 报警
    assert gsb_repo.credential_args("/tmp/origin.git") == []
    assert gsb_repo.credential_args("git@github.com:acme/widget.git") == []
    monkeypatch.setattr(gsb_repo, "_token", lambda: "")
    assert gsb_repo.credential_args("https://github.com/acme/widget") == []


def test_probe_branches_accepts_exactly_three(origin):
    probe = asyncio.run(gsb_repo.probe_branches(origin["url"]))
    assert probe.ok is True
    assert probe.main == "main"
    assert sorted(probe.branches) == ["A", "B", "main"]


def test_probe_branches_rejects_missing_side(origin, tmp_path):
    subprocess.run(["git", "-C", origin["url"], "branch", "-D", "B"],
                   check=True, capture_output=True, text=True)
    probe = asyncio.run(gsb_repo.probe_branches(origin["url"]))
    assert probe.ok is False
    assert "B" in probe.message


def test_probe_branches_rejects_extra_branch(origin):
    subprocess.run(["git", "-C", origin["url"], "branch", "feature-x"],
                   check=True, capture_output=True, text=True)
    probe = asyncio.run(gsb_repo.probe_branches(origin["url"]))
    assert probe.ok is False
    assert "feature-x" in probe.message


def test_clone_side_puts_each_branch_in_its_own_dir(origin):
    for side in ("A", "B"):
        r = asyncio.run(gsb_repo.clone_side("07", origin["url"], side))
        assert r["ok"] is True, r["message"]
    for side in ("A", "B"):
        ws = config.TaskPaths("07", side).workspace
        assert (ws / ".git").exists()
        cur = subprocess.run(["git", "-C", str(ws), "symbolic-ref", "--short", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
        assert cur == side


def test_clone_side_reuses_existing_clean_clone(origin):
    asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    again = asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    assert again["ok"] is True
    assert again["reused"] is True


def test_clone_side_never_writes_token_into_git_config(origin, monkeypatch):
    fake = "ghp_FAKE_TOKEN_123"
    monkeypatch.setattr(gsb_repo, "_token", lambda: fake)
    r = asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    assert r["ok"] is True, r["message"]
    ws = config.TaskPaths("07", "A").workspace
    cfg = (ws / ".git" / "config").read_text(encoding="utf-8")
    # 本地路径下 credential_args 返回空列表，这里守住的是「clone 之后 config 里没有任何凭据痕迹」
    assert fake not in cfg
    assert "x-access-token" not in cfg


def test_clone_side_mismatch_message_hides_origin_url(origin):
    fake = "ghp_FAKE_TOKEN_123"
    asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    ws = config.TaskPaths("07", "A").workspace
    # 模拟被历史操作污染过的 config：origin 带着 token
    _git(ws, "remote", "set-url", "origin",
         f"https://x-access-token:{fake}@github.com/acme/widget.git")
    r = asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    assert r["ok"] is False
    assert fake not in r["message"]
    assert "x-access-token" not in r["message"]
    assert "acme/widget" in r["message"]


def test_clone_side_reports_nonempty_dir_without_git(origin):
    ws = config.TaskPaths("07", "A").workspace
    ws.mkdir(parents=True)
    (ws / "leftover.txt").write_text("x", encoding="utf-8")
    r = asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    assert r["ok"] is False
    assert str(ws) in r["message"]
    assert "Token" not in r["message"]


def test_verify_head_matches_snapshot(origin):
    asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    r = asyncio.run(gsb_repo.verify_head("07", "A", origin["sha"]))
    assert r["ok"] is True
    assert r["dirty"] == 0


def test_verify_head_reports_dirty_worktree(origin):
    asyncio.run(gsb_repo.clone_side("07", origin["url"], "A"))
    ws = config.TaskPaths("07", "A").workspace
    (ws / "scratch.txt").write_text("x", encoding="utf-8")
    r = asyncio.run(gsb_repo.verify_head("07", "A", origin["sha"]))
    assert r["ok"] is False
    assert r["dirty"] == 1
