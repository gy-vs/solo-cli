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
from datetime import datetime
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


async def backup_head(task_no: str, side: str, snapshot: str) -> tuple[str, str]:
    """回退前把领先快照的 HEAD 记到 refs/solo-backup/*，事后用 git log 还能捞回来。

    reset --hard 加 clean -fdx 会把模型跑出来的东西全抹掉，先留个 ref 才敢动手。
    返回 (ref 名, 错误说明)：
    - 已经停在快照上没什么可备份，返回 ("", "")；
    - 备份成功，返回 (ref, "")；
    - 需要备份但 update-ref 失败，返回 ("", 错误说明)。
    用二元组而不是抛异常，是因为「不需要备份」和「备份失败」对调用方都是正常分支，
    不该走异常路径；单个空串又区分不开这两种情况，调用方会误以为可以放心 reset。
    """
    ws = config.TaskPaths(task_no, side).workspace
    head = (await _git(ws, "rev-parse", "HEAD", timeout=30)).out.strip()
    if not head or head.lower() == (snapshot or "").lower():
        return "", ""
    # ref 名带题号、侧别和毫秒级时间戳：秒级精度下同一秒内连续备份两次，
    # 第二次 update-ref 会直接改掉第一次的指向，前一份就真的找不回来了
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    ref = f"{BACKUP_NS}/{task_no}-{side}-{stamp}"
    r = await _git(ws, "update-ref", ref, head, timeout=30)
    if not r.ok:
        # 详细 err 只进日志：update-ref 参数里虽然没有凭据，但 git 的 stderr 一律不透传给调用方
        log.warning("题 %s %s 侧备份 HEAD 失败：%s", task_no, side, r.err.strip()[:200])
        return "", f"{side} 侧 HEAD {head[:12]} 领先初始快照，但备份 ref 写入失败"
    return ref, ""


async def reset_side(task_no: str, side: str, snapshot: str) -> dict:
    """把这一侧退回初始快照。重跑之前必须做，否则产物快照的父提交对不上。"""
    ws = config.TaskPaths(task_no, side).workspace
    if not (ws / ".git").exists():
        return {"ok": False, "backup": "", "message": f"{side} 侧不是 git 仓库"}
    if not snapshot:
        # 没有 sha 就没有回退目标，reset --hard 拿空串会退到 HEAD 等于白做，不如直接拦下
        return {"ok": False, "backup": "", "message": "初始环境快照缺少 40 位 SHA，无法回退"}
    backup, backup_err = await backup_head(task_no, side, snapshot)
    if backup_err:
        # 备份没打上就不能动手：reset --hard 加 clean -fdx 会把模型产出彻底抹掉，
        # 这时宁可停下让人手动处理，也不能拿「反正日志里记了」当理由继续
        return {"ok": False, "backup": "",
                "message": f"{backup_err}，为免丢失产物已中止回退，请先手动处理"}
    r1 = await _git(ws, "reset", "--hard", snapshot, timeout=180)
    # -x 连 .gitignore 里的东西一起清：模型跑出来的依赖目录、缓存多半正好在 ignore 里
    r2 = await _git(ws, "clean", "-fdx", timeout=180)
    if not (r1.ok and r2.ok):
        # reset / clean 的参数里只有本地路径和 sha，没有凭据，err 可以外传
        return {"ok": False, "backup": backup,
                "message": (r1.err or r2.err).strip()[:300] or "回退失败"}
    msg = f"{side} 侧已退回 {snapshot[:12]}"
    if backup:
        msg += f"，原提交备份在 {backup}"
    return {"ok": True, "backup": backup, "message": msg}


def commit_message(task_no: str, side: str, session_id: str) -> str:
    return (f"solo {task_no} · {side}\n\n"
            f"SessionID: {session_id or '-'}\n")


async def commit_and_push(task_no: str, repo_url: str, side: str, snapshot: str,
                          *, message: str) -> dict:
    """提交这一侧的产物并推到同名分支，返回产物快照 permalink。

    push 之前校验父提交等于初始快照：平台规则 G3 卡这个，等提交被打回才发现就晚了。
    """
    ws = config.TaskPaths(task_no, side).workspace
    if not (ws / ".git").exists():
        return {"ok": False, "message": f"{side} 侧不是 git 仓库"}
    slug = repo_slug(repo_url)
    if not slug:
        return {"ok": False, "message": f"仓库地址解析不出 org/repo：{repo_url}"}
    # 推送走 origin 而不是题块地址：clone 时 origin 就是从题块地址来的，两者本该一致；
    # 这里再比一次，防止目录被人换过远端后把产物推去别处。
    # 判定按「origin 是不是 https」而不是「能不能解析出 slug」分岔：credential helper
    # 不看目标主机、无条件交出 token，所以任何 https 目标都必须是题块那个 github 仓库——
    # 非 github 的 https 地址 slug 为空串、另一个 github 仓库 slug 不等，两种都在这里被拒。
    # 非 https 的 origin（本地路径、ssh）不走 http 凭据通道，git 根本不会调 helper，
    # token 漏不出去，放行；测试用本地裸仓库当远端走的就是这条路。
    # 只回显 org/repo，不回显 origin 原始地址，config 若被带 token 的地址污染过也不会外漏
    origin = (await _git(ws, "remote", "get-url", "origin", timeout=30)).out.strip()
    if origin.startswith("https://"):
        origin_slug = repo_slug(origin)
        if origin_slug != slug:
            return {"ok": False,
                    "message": f"{side} 侧的 origin（{origin_slug or '无法识别'}）"
                               f"与题块仓库 {slug} 对不上，不能推送"}

    st = await _git(ws, "status", "--porcelain", "--untracked-files=all", timeout=60)
    changed = len([x for x in st.out.splitlines() if x.strip()])
    if not changed:
        return {"ok": False, "message": f"{side} 侧工作区没有改动，这一跑没有产出，不能当作产物提交"}

    # add / commit 的参数里没有凭据，stderr 可以带给调用方帮人定位问题
    add = await _git(ws, "add", "-A", timeout=180)
    if not add.ok:
        return {"ok": False, "message": f"git add 失败：{add.err.strip()[:300]}"}
    ci = await _git(ws, "-c", f"user.name={COMMIT_USER}", "-c", f"user.email={COMMIT_EMAIL}",
                    "commit", "-m", message, timeout=180)
    if not ci.ok:
        return {"ok": False, "message": f"git commit 失败：{(ci.err or ci.out).strip()[:300]}"}

    head = (await _git(ws, "rev-parse", "HEAD", timeout=30)).out.strip()
    parent = (await _git(ws, "rev-parse", "HEAD^", timeout=30)).out.strip()
    if parent.lower() != (snapshot or "").lower():
        return {"ok": False,
                "message": f"{side} 侧产物的父提交是 {parent[:12]}，不是初始快照 {snapshot[:12]}；"
                           f"平台规则 G3 会打回，需要先回退这一侧再重跑"}

    # 凭据走临时 credential helper，不用带 token 的 URL——push 失败时 git 会把命令行
    # 回显进 stderr，URL 里的 token 就跟着漏出去了。-c 必须放在 push 之前，放后面
    # git 会把它当成 push 的参数。目标写 origin：上面已经核对过它和题块仓库是同一个，
    # 而测试里的 origin 是本地裸仓库，这样不用联网也能走通整条 push 链路
    push = await dockerx.run(
        ["git", "-C", str(ws), *credential_args(repo_url), "push", "origin",
         f"HEAD:refs/heads/{side}"], timeout=300,
    )
    if not push.ok:
        # 超时分支的 err 里拼着完整命令行，而 helper 参数里就有 token：一律不透传
        return {"ok": False, "message": f"{side} 侧 push 失败，检查 Token 的 repo 写权限"}

    url = commit_url(repo_url, head)
    log.info("题 %s %s 侧产物 %s 已推到分支 %s（%d 个文件）", task_no, side, head[:12], side, changed)
    return {"ok": True, "sha": head, "url": url, "changed_files": changed,
            "message": f"{side} 侧已提交 {head[:12]} 并推到分支 {side}（{changed} 个文件）"}
