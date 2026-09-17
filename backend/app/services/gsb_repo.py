"""GSB 双跑的仓库操作：分支探测、双分支 clone、回退快照、产物提交。

一道题对应一个 GitHub 仓库，仓库下有且仅有三个分支：主分支加大写的 A、B。
A 和 B 各自 clone 到 workspace/<题号>/<side>，跑完各自提交到自己的分支。
平台要求两份产物快照的父提交都是初始环境快照，所以 push 之前会先校验 HEAD^。

GitHub Token 只在拼命令的那一刻进内存：一次性命令（ls-remote）拼进 URL，
会落盘的命令（clone）走临时 credential helper，不写进 .git/config，也不进日志和报错。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from app import config
from app.services import dockerx, settings_store

log = logging.getLogger("gsb_repo")

MAIN_NAMES = ("main", "master")
COMMIT_USER = "solo-cli"
COMMIT_EMAIL = "solo-cli@local"
BACKUP_NS = "refs/solo-backup"

# 平台校验产物链接用的格式：必须是 github.com 上的 40 位完整 sha 提交页
COMMIT_URL_RE = re.compile(r"^https://github\.com/[^/\s]+/[^/\s]+/commit/[0-9a-fA-F]{40}/?$")
# 同时吃 https 与 ssh 两种写法：`github.com/org/repo(.git)` 与 `github.com:org/repo(.git)`
_SLUG_RE = re.compile(r"(?:github\.com[:/])([^/\s]+)/([^/\s]+?)(?:\.git)?/?$")
_SHA_RE = re.compile(r"/commit/([0-9a-fA-F]{40})/?$")
# 题块里仓库地址的键名不统一，中英文都认
_META_KEYS = ("仓库", "repo", "repository")


def parse_repo_url(meta: dict) -> str:
    for key in _META_KEYS:
        v = (meta or {}).get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def repo_slug(repo_url: str) -> str:
    """`org/repo`。解析不出来返回空串，调用方拿它做「是不是同一个仓库」的比较。"""
    m = _SLUG_RE.search((repo_url or "").strip())
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def commit_url(repo_url: str, sha: str) -> str:
    slug = repo_slug(repo_url)
    return f"https://github.com/{slug}/commit/{sha}" if slug and sha else ""


def snapshot_sha(env_snapshot: str) -> str:
    """从初始环境快照链接里取 sha。统一小写，后面和 rev-parse 的输出直接比。"""
    m = _SHA_RE.search(env_snapshot or "")
    return m.group(1).lower() if m else ""


def authed_url(repo_url: str, token: str) -> str:
    """把 token 拼进 https 地址。非 github https 地址（比如测试用的本地裸仓库）原样返回。"""
    url = (repo_url or "").strip()
    if not token or not url.startswith("https://github.com/"):
        return url
    return url.replace("https://", f"https://x-access-token:{token}@", 1)


def credential_args(repo_url: str) -> list[str]:
    """给 git 命令拼临时凭据参数。

    token 走 -c credential.helper 传，不进 .git/config，也就不需要事后 set-url 擦除——
    先写进去再擦掉的做法中间有个窗口，进程在那一刻被杀 token 就永久留在仓库里了。
    """
    token = _token()
    if not token or not (repo_url or "").strip().startswith("https://github.com/"):
        return []
    # helper 的值由 git 自己起 shell 执行；我们这边用 create_subprocess_exec 不经 shell，
    # 所以这里不做额外转义，否则转义字符会原样传给 git 反而把命令弄坏
    helper = f"!f() {{ echo username=x-access-token; echo password={token}; }}; f"
    return ["-c", f"credential.helper={helper}"]


def _token() -> str:
    return settings_store.get("gh.token")


@dataclass
class BranchProbe:
    ok: bool
    branches: list[str] = field(default_factory=list)
    main: str = ""
    message: str = ""


async def probe_branches(repo_url: str) -> BranchProbe:
    """远端必须恰好三个分支：主分支加 A、B（平台规则 G2）。"""
    if not repo_url:
        return BranchProbe(False, message="题块里没有仓库地址")
    r = await dockerx.run(["git", "ls-remote", "--heads", authed_url(repo_url, _token())], timeout=90)
    if not r.ok:
        # 报错里可能带着 token，整条压掉只留一句话
        return BranchProbe(False, message="读不到远端分支，检查仓库地址与 GitHub Token")
    names = sorted({line.rsplit("refs/heads/", 1)[-1].strip()
                    for line in r.out.splitlines() if "refs/heads/" in line})
    main = next((n for n in names if n in MAIN_NAMES), "")
    if not main:
        return BranchProbe(False, names, "", f"没有主分支（main 或 master），实际分支：{', '.join(names) or '无'}")
    want = {main, "A", "B"}
    if set(names) == want:
        return BranchProbe(True, names, main, f"分支合规：{', '.join(names)}")
    # 缺的和多的分开报，出题人一眼就知道该建还是该删
    missing = sorted(want - set(names))
    extra = sorted(set(names) - want)
    parts = []
    if missing:
        parts.append(f"缺少 {', '.join(missing)}")
    if extra:
        parts.append(f"多出 {', '.join(extra)}")
    return BranchProbe(False, names, main,
                       f"分支不合规（{'；'.join(parts)}），实际分支：{', '.join(names)}")


async def _git(ws: Path, *args: str, timeout: float = 60) -> dockerx.CmdResult:
    return await dockerx.run(["git", "-C", str(ws), *args], timeout=timeout)


async def clone_side(task_no: str, repo_url: str, side: str) -> dict:
    """把某一侧的分支 clone 到它自己的目录。已有干净的同源 clone 就复用。"""
    ws = config.TaskPaths(task_no, side).workspace
    if (ws / ".git").exists():
        # 目录已经在了就不重新 clone：可能是上一轮领取留下的，也可能是人手动放的。
        # 只要分支对、仓库对就接着用；对不上宁可报错让人清，别悄悄覆盖掉里面的东西。
        cur = (await _git(ws, "symbolic-ref", "--short", "-q", "HEAD", timeout=30)).out.strip()
        origin = (await _git(ws, "remote", "get-url", "origin", timeout=30)).out.strip()
        if cur == side and repo_slug(origin) == repo_slug(repo_url):
            return {"ok": True, "reused": True, "message": f"复用已有的 {side} 目录"}
        # 只回显 org/repo，不回显原始地址：config 若曾被带 token 的地址污染过，
        # 原样拼进 message 就把 token 送到调用方和前端了
        return {"ok": False, "reused": False,
                "message": f"{ws} 已存在但对不上（分支 {cur or '游离'}，"
                           f"远端 {repo_slug(origin) or '无法识别'}），先清掉再领取"}
    if ws.exists() and any(ws.iterdir()):
        # 有东西但不是 git 仓库（多半是上次 clone 被打断的残留）。git 会因为目标非空拒绝 clone，
        # 这跟分支、Token 都没关系，提前判掉免得报错把人往错误方向引
        return {"ok": False, "reused": False,
                "message": f"{ws} 已存在且非空，但不是 git 仓库，先清掉这个目录再领取"}
    ws.parent.mkdir(parents=True, exist_ok=True)
    # --single-branch：这一侧只关心自己的分支，A 目录里不该看得到 B 的提交
    # URL 用干净地址，凭据走临时 helper，clone 落盘的 origin 从头就不带 token
    r = await dockerx.run(
        ["git", *credential_args(repo_url), "clone", "--branch", side, "--single-branch",
         repo_url, str(ws)], timeout=600,
    )
    if not r.ok:
        # stderr 里可能带着 git 回显的凭据信息，不能原样返回
        return {"ok": False, "reused": False, "message": f"clone {side} 分支失败，检查分支是否存在与 Token 权限"}
    return {"ok": True, "reused": False, "message": f"已 clone {side} 分支到 {ws.name}"}


async def verify_head(task_no: str, side: str, snapshot: str) -> dict:
    """做题前这一侧必须停在初始快照上且工作区干净。"""
    ws = config.TaskPaths(task_no, side).workspace
    if not (ws / ".git").exists():
        return {"ok": False, "head": "", "dirty": 0, "message": f"{side} 侧还没有 clone"}
    head = (await _git(ws, "rev-parse", "HEAD", timeout=30)).out.strip().lower()
    # untracked 也算脏：模型产出的新文件不加这个参数就漏掉了
    st = await _git(ws, "status", "--porcelain", "--untracked-files=all", timeout=60)
    dirty = len([x for x in st.out.splitlines() if x.strip()])
    if snapshot and head != snapshot.lower():
        return {"ok": False, "head": head, "dirty": dirty,
                "message": f"{side} 侧 HEAD {head[:12]} 不是初始快照 {snapshot[:12]}"}
    if dirty:
        return {"ok": False, "head": head, "dirty": dirty,
                "message": f"{side} 侧工作区有 {dirty} 处改动，需要先回退"}
    return {"ok": True, "head": head, "dirty": 0, "message": f"{side} 侧停在初始快照且干净"}
