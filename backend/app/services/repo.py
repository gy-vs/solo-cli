"""题目工作区的 git 分支与提交。

一个项目里一道题一个分支（默认 q01、q02…，clone 下来就带着）。做题前切到自己的分支，
上传 solo-qa 之后把这一轮的改动提交到同一个分支上——否则改动一直以未提交状态躺着，
下次还原时被 git clean 顺手清掉。还原会先把提交备份成 refs/solo-backup/*，不会真丢。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app import config
from app.services import dockerx, settings_store

log = logging.getLogger("repo")

COMMIT_USER = "solo-cli"
COMMIT_EMAIL = "solo-cli@local"
BACKUP_NS = "refs/solo-backup"
_SAFE = re.compile(r"[^A-Za-z0-9._/-]+")


def workspace(task_no: str) -> Path:
    return config.TaskPaths(task_no).workspace


def is_git(task_no: str) -> bool:
    return (workspace(task_no) / ".git").exists()


def branch_of(task_no: str) -> str:
    """题目约定的分支名。模板可在设置里改，默认 q+题号。"""
    tpl = settings_store.get("git.task_branch") or "q{no}"
    return _SAFE.sub("-", tpl.replace("{no}", task_no))


async def _git(task_no: str, *args: str, timeout: float = 60) -> dockerx.CmdResult:
    return await dockerx.run(["git", "-C", str(workspace(task_no)), *args], timeout=timeout)


async def current_branch(task_no: str) -> str:
    """当前分支名；处于游离 HEAD 时返回空串。"""
    r = await _git(task_no, "symbolic-ref", "--short", "-q", "HEAD", timeout=30)
    return r.out.strip()


async def branch_exists(task_no: str, branch: str, *, remote: bool = False) -> bool:
    ref = f"refs/remotes/origin/{branch}" if remote else f"refs/heads/{branch}"
    r = await _git(task_no, "show-ref", "--verify", "--quiet", ref, timeout=30)
    return r.ok


async def branch_state(task_no: str) -> dict:
    """做题前要落在自己的分支上，这里把判断要用的信息一次取齐。"""
    want = branch_of(task_no)
    if not is_git(task_no):
        return {"want": want, "current": "", "detached": False, "local": False, "remote": False, "git": False}
    cur = await current_branch(task_no)
    return {
        "want": want,
        "current": cur,
        "detached": not cur,
        "local": await branch_exists(task_no, want),
        "remote": await branch_exists(task_no, want, remote=True),
        "git": True,
    }


async def switch_to_task_branch(task_no: str) -> dict:
    """切到题目分支。远端有本地没有时建立跟踪分支。工作区有改动会切换失败，这是故意的。"""
    if not is_git(task_no):
        return {"ok": False, "message": "工作区不是 git 仓库"}
    st = await branch_state(task_no)
    want = st["want"]
    if st["current"] == want:
        return {"ok": True, "branch": want, "message": f"已经在分支 {want} 上"}
    if st["local"]:
        r = await _git(task_no, "checkout", want, timeout=120)
    elif st["remote"]:
        r = await _git(task_no, "checkout", "-b", want, "--track", f"origin/{want}", timeout=120)
    else:
        return {"ok": False, "branch": want,
                "message": f"本地和远端都没有分支 {want}，这道题的分支要先在仓库里建好"}
    if not r.ok:
        return {"ok": False, "branch": want, "message": (r.err or r.out).strip()[:300]}
    return {"ok": True, "branch": want, "message": f"已切到分支 {want}"}


async def ensure_task_branch(task_no: str) -> dict:
    """做题前把工作区落到这道题的分支上。

    只在工作区干净时动手：有未提交改动说明上一轮还没收尾，交给门禁报出来，
    这里悄悄切分支反而会把改动带到别的分支上。
    """
    if not is_git(task_no):
        return {"ok": False, "skipped": True, "message": "工作区不是 git 仓库"}
    st = await branch_state(task_no)
    if st["current"] == st["want"]:
        return {"ok": True, "branch": st["want"], "message": f"已经在分支 {st['want']} 上"}
    if not (st["local"] or st["remote"]):
        return {"ok": False, "skipped": True, "message": f"仓库里没有分支 {st['want']}"}
    dirty = await _git(task_no, "status", "--porcelain", "--untracked-files=all", timeout=60)
    if dirty.out.strip():
        return {"ok": False, "skipped": True, "message": "工作区有未提交改动，先还原再切分支"}
    return await switch_to_task_branch(task_no)


@dataclass
class CommitInfo:
    """提交需要的几个字段。单独拎出来，避免把 Task 对象带出数据库会话。"""

    task_no: str
    session_id: str = ""
    turn_id: str = ""
    question_type: str = ""
    env_snapshot: str = ""

    @classmethod
    def of(cls, task) -> "CommitInfo":  # noqa: ANN001
        return cls(
            task_no=task.task_no,
            session_id=task.session_id or "",
            turn_id=task.turn_id or "",
            question_type=task.question_type or "",
            env_snapshot=task.env_snapshot or "",
        )

    @property
    def message(self) -> str:
        lines = [
            f"solo {self.task_no} · {self.question_type or '未标类型'}",
            "",
            f"SessionID: {self.session_id or '-'}",
            f"TurnID: {self.turn_id or '-'}",
        ]
        if self.env_snapshot:
            lines.append(f"初始快照: {self.env_snapshot}")
        return "\n".join(lines)


async def commit_after_upload(info: CommitInfo) -> dict:
    """把工作区改动提交到题目分支。不 push，失败不影响已经成功的上传。"""
    no = info.task_no
    if not is_git(no):
        return {"ok": False, "skipped": True, "message": "工作区不是 git 仓库"}

    st = await _git(no, "status", "--porcelain", "--untracked-files=all", timeout=60)
    if not st.out.strip():
        return {"ok": True, "skipped": True, "message": "工作区没有改动，跳过提交"}

    state = await branch_state(no)
    branch, want = state["current"], state["want"]
    if state["detached"]:
        # 提交在游离 HEAD 上没有分支引用着，容易被后续操作清掉，不如直接报出来
        return {"ok": False, "message": f"工作区处于游离 HEAD，没提交。先切到分支 {want} 再上传"}
    if state["local"] and branch != want:
        return {"ok": False, "branch": branch,
                "message": f"当前在分支 {branch}，这道题应该在 {want} 上，没提交"}

    add = await _git(no, "add", "-A", timeout=120)
    if not add.ok:
        return {"ok": False, "branch": branch, "message": f"git add 失败：{add.err.strip()[:300]}"}

    # 身份用 -c 传，不写进仓库配置
    ci = await _git(no, "-c", f"user.name={COMMIT_USER}", "-c", f"user.email={COMMIT_EMAIL}",
                    "commit", "-m", info.message, timeout=120)
    if not ci.ok:
        return {"ok": False, "branch": branch, "message": f"git commit 失败：{(ci.err or ci.out).strip()[:300]}"}

    sha = await _git(no, "rev-parse", "HEAD", timeout=30)
    short = sha.out.strip()[:12]
    changed = len([x for x in st.out.splitlines() if x.strip()])
    log.info("题 %s 上传后提交 %s 到分支 %s（%s 个文件）", no, short, branch, changed)
    return {"ok": True, "branch": branch, "commit": sha.out.strip(), "short": short,
            "changed_files": changed, "message": f"已提交 {short} 到分支 {branch}（{changed} 个文件）"}


async def backup_head(task_no: str, sha: str) -> str:
    """还原前留一手：HEAD 领先快照时把它记到 refs/solo-backup/*，事后还能捞回来。"""
    head = (await _git(task_no, "rev-parse", "HEAD", timeout=30)).out.strip()
    if not head or head == sha:
        return ""
    label = (await current_branch(task_no)) or "detached"
    ref = f"{BACKUP_NS}/{label}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    r = await _git(task_no, "update-ref", ref, head, timeout=30)
    if not r.ok:
        log.warning("题 %s 备份 HEAD 失败：%s", task_no, r.err.strip())
        return ""
    log.info("题 %s 还原前把 %s 备份到 %s", task_no, head[:12], ref)
    return ref
