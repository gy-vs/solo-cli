"""录屏仓库：出题端与录屏端之间唯一的交接面。

和远端题库一个思路：没有公共后端，两端都已经配着 gh token，就拿一个私有 GitHub 仓库
当信箱。布局见 docs/ScreencastAutomation.md，要点三条：

- main 只放 `events.jsonl`，一个动作一行、只追加、`merge=union`。两端每轮巡检都拉它，
  必须小；状态靠按时间戳重放折叠出来，与合并后的行序无关。
- 每道题一个孤儿分支 `rec/<设备>/<题号>`，放 `report.md`、`meta.json` 和回传的
  `A.mp4` / `B.mp4`。视频只有真要用的那一端才拉那一个分支；题提交后删分支，仓库不会
  越涨越大。
- 绝不碰作答仓库：平台规则 G2 规定作答仓库只许有 main/A/B 三个分支。

token 只在命令行上现拼（沿用 pool._authed_url），不写进 remote。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.services import pool, settings_store

log = logging.getLogger("solo-cli.rec")

MAIN_BRANCH = "main"
EVENTS_FILE = "events.jsonl"
GITATTRIBUTES = f"{EVENTS_FILE} merge=union\n"
REPORT_FILE = "report.md"
META_FILE = "meta.json"
# GitHub 单文件硬上限 100 MB，留点余量。720p 录屏一般几 MB，超了多半是录成了原始分辨率。
MAX_VIDEO_BYTES = 95 * 1024 * 1024

# 事件类型
PUBLISHED = "published"
CLAIMED = "claimed"
RELEASED = "released"
RECORDED = "recorded"
COLLECTED = "collected"
WITHDRAWN = "withdrawn"
EVENT_TYPES = (PUBLISHED, CLAIMED, RELEASED, RECORDED, COLLECTED, WITHDRAWN)

# 折叠后的条目状态
S_OPEN = "open"            # 已发布，没人认领
S_CLAIMED = "claimed"      # 有人在录
S_RECORDED = "recorded"    # 视频已回传，等出题端收
S_COLLECTED = "collected"  # 出题端已收回
S_WITHDRAWN = "withdrawn"  # 文档作废

_lock = asyncio.Lock()


# ---------------- 配置 ----------------

def enabled() -> bool:
    return settings_store.get_bool("rec.enabled", False)


def recorder_only() -> bool:
    return settings_store.get_bool("rec.recorder_only", False)


def device() -> str:
    return pool.device()


def repo_slug() -> str:
    raw = settings_store.get("rec.repo").strip()
    if not raw:
        return ""
    raw = re.sub(r"^https?://(?:[^@]+@)?github\.com/", "", raw).removesuffix(".git")
    parts = [p for p in raw.split("/") if p]
    return "/".join(parts[:2]) if len(parts) >= 2 else ""


def available() -> tuple[bool, str]:
    if not enabled():
        return False, "录屏协作没有启用（设置 → 录屏协作）"
    if not repo_slug():
        return False, "没有配置录屏仓库（设置 → 录屏协作 → 录屏仓库，填 owner/repo）"
    if not settings_store.get("gh.token"):
        return False, "没有配置 GitHub Token（设置 → 题目设计 → GitHub Token）"
    if not settings_store.get("pool.device"):
        return False, "没有配置本机标识（设置 → 跨设备题库 → 本机标识），两端靠它区分谁出的题、谁录的"
    if repo_slug() == pool.repo_slug():
        return False, "录屏仓库不能和远端题库用同一个仓库"
    return True, ""


def repo_dir() -> Path:
    return config.DATA_DIR / "rec" / "repo"


def events_path() -> Path:
    return repo_dir() / EVENTS_FILE


def scratch_dir() -> Path:
    """临时目录都落在 DATA_DIR 下：分支克隆要搬视频，放 /tmp 会在容器层里多存一份。"""
    d = config.DATA_DIR / "rec" / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def branch_of(owner: str, task_no: str) -> str:
    return f"rec/{pool._slug(owner)}/{task_no}"


def key_of(owner: str, task_no: str) -> str:
    return f"{owner}/{task_no}"


# ---------------- git ----------------

_GIT_ID = ["-c", "user.email=solo-cli@local", "-c", "user.name=solo-cli"]


async def _git(args: list[str], *, cwd: str | Path | None = None, timeout: float = 300):
    return await pool._sh(["git", *args], cwd=str(cwd) if cwd else None, timeout=timeout)


def _url() -> str:
    return pool._authed_url(repo_slug())


def _tail(r) -> str:  # noqa: ANN001
    return (r.err or r.out).strip()[:200]


async def _ensure_remote_repo(slug: str) -> tuple[bool, str]:
    r = await pool._sh(["gh", "repo", "view", slug, "--json", "visibility", "-q", ".visibility"], timeout=60)
    if r.ok:
        if r.out.strip().upper() == "PUBLIC":
            return False, f"{slug} 是公开仓库。录屏文档里有作答仓库地址和评审结论，必须用私有仓库"
        return True, ""
    rr = await pool._sh(["gh", "repo", "create", slug, "--private",
                         "--description", "internal screencast exchange"], timeout=120)
    if not rr.ok:
        return False, f"建录屏仓库 {slug} 失败：{_tail(rr)}"
    return True, f"已创建私有仓库 {slug}"


def _write_scaffold() -> None:
    d = repo_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / ".gitattributes").write_text(GITATTRIBUTES, encoding="utf-8")
    if not events_path().exists():
        events_path().write_text("", encoding="utf-8")


async def _init_local(slug: str) -> tuple[bool, str]:
    d = repo_dir()
    d.mkdir(parents=True, exist_ok=True)
    for args in (["init", "-q", "-b", MAIN_BRANCH],
                 ["remote", "add", "origin", pool._plain_url(slug)]):
        r = await _git(args, cwd=d)
        if not r.ok and "already exists" not in (r.err + r.out):
            return False, f"git {args[0]} 失败：{_tail(r)}"
    _write_scaffold()
    await _git(["add", "-A"], cwd=d)
    await _git([*_GIT_ID, "commit", "-q", "-m", "init"], cwd=d)
    r = await _git(["push", "-u", _url(), f"HEAD:{MAIN_BRANCH}"], cwd=d)
    return (True, "") if r.ok else (False, f"推送录屏仓库失败：{_tail(r)}")


async def sync() -> dict:
    """把 main 拉到本地。返回 {ok, message, stale?}。"""
    ok, why = available()
    if not ok:
        return {"ok": False, "message": why}
    async with _lock:
        return await _sync_locked()


async def _sync_locked() -> dict:
    slug = repo_slug()
    ready, msg = await _ensure_remote_repo(slug)
    if not ready:
        return {"ok": False, "message": msg}
    d = repo_dir()
    if not (d / ".git").is_dir():
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        r = await _git(["clone", "-q", "--single-branch", "-b", MAIN_BRANCH, _url(), str(d)], timeout=600)
        if r.ok:
            await _git(["remote", "set-url", "origin", pool._plain_url(slug)], cwd=d)
        else:
            shutil.rmtree(d, ignore_errors=True)
            created, why = await _init_local(slug)
            if not created:
                return {"ok": False, "message": why}
    else:
        r = await _git([*_GIT_ID, "pull", "--rebase", "-q", _url(), MAIN_BRANCH], cwd=d)
        if not r.ok:
            tail = _tail(r)
            if "find remote ref" not in tail:
                log.warning("拉取录屏仓库失败，暂用本地副本：%s", tail)
                _write_scaffold()
                return {"ok": True, "message": f"拉取失败，暂用本地副本：{tail}", "stale": True}
    _write_scaffold()
    return {"ok": True, "message": msg or "已同步"}


# ---------------- 事件 ----------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def event(kind: str, owner: str, task_no: str, **extra) -> dict:
    assert kind in EVENT_TYPES, kind
    return {"type": kind, "owner": owner, "task_no": str(task_no), "by": device(),
            "at": now_iso(), **extra}


def load_events() -> list[dict]:
    path = events_path()
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict) and raw.get("type") in EVENT_TYPES and raw.get("owner") and raw.get("task_no"):
            rows.append(raw)
    return rows


@dataclass
class Entry:
    owner: str
    task_no: str
    state: str = S_WITHDRAWN
    digest: str = ""               # 当前这一轮文档的指纹
    title: str = ""
    kind_label: str = ""
    verdict: str = ""
    repo_url: str = ""
    published_at: str = ""
    claimed_by: str = ""
    claimed_at: str = ""
    recorded_by: str = ""
    recorded_at: str = ""
    collected_at: str = ""
    history: list[dict] = field(default_factory=list)

    @property
    def key(self) -> str:
        return key_of(self.owner, self.task_no)

    @property
    def branch(self) -> str:
        return branch_of(self.owner, self.task_no)

    def as_dict(self) -> dict:
        return {"key": self.key, "owner": self.owner, "task_no": self.task_no, "state": self.state,
                "digest": self.digest, "title": self.title, "kind_label": self.kind_label,
                "verdict": self.verdict, "repo_url": self.repo_url, "branch": self.branch,
                "published_at": self.published_at, "claimed_by": self.claimed_by,
                "claimed_at": self.claimed_at, "recorded_by": self.recorded_by,
                "recorded_at": self.recorded_at, "collected_at": self.collected_at}


def fold(events: list[dict]) -> dict[str, Entry]:
    """按时间重放全部动作，得出每道题此刻的状态。

    规则只有几条，都是为了两端同时动手时结论一致：
    - 每次 published 开一轮新的，旧一轮的认领、回传一律作废 —— 理由改过的文档，
      按旧稿录的视频不能收；
    - 认领先到先得，后到的那一条不生效（发起方推完再读一遍就知道自己抢没抢到）；
    - 带 digest 的动作只对同一轮生效，防止一端拿着旧文档回传视频；
    - withdrawn 随时可以把一轮关掉。
    """
    out: dict[str, Entry] = {}
    uniq = {json.dumps(e, sort_keys=True, ensure_ascii=False): e for e in events}
    for ev in sorted(uniq.values(), key=lambda e: (str(e.get("at") or ""), str(e.get("by") or ""))):
        key = key_of(ev["owner"], ev["task_no"])
        cur = out.get(key)
        kind = ev["type"]
        if kind == PUBLISHED:
            cur = out[key] = Entry(owner=ev["owner"], task_no=str(ev["task_no"]), state=S_OPEN,
                                   digest=str(ev.get("digest") or ""), title=str(ev.get("title") or ""),
                                   kind_label=str(ev.get("kind_label") or ""),
                                   verdict=str(ev.get("verdict") or ""),
                                   repo_url=str(ev.get("repo_url") or ""),
                                   published_at=str(ev.get("at") or ""),
                                   history=list(cur.history) if cur else [])
            cur.history.append(ev)
            continue
        if cur is None:
            continue
        cur.history.append(ev)
        same_round = not ev.get("digest") or ev.get("digest") == cur.digest
        by = str(ev.get("by") or "")
        if kind == WITHDRAWN:
            cur.state = S_WITHDRAWN
        elif not same_round:
            continue
        elif kind == CLAIMED:
            if cur.state == S_OPEN:
                cur.state, cur.claimed_by, cur.claimed_at = S_CLAIMED, by, str(ev.get("at") or "")
        elif kind == RELEASED:
            if cur.state == S_CLAIMED and cur.claimed_by == by:
                cur.state, cur.claimed_by, cur.claimed_at = S_OPEN, "", ""
        elif kind == RECORDED:
            if cur.state == S_OPEN or (cur.state == S_CLAIMED and cur.claimed_by == by):
                cur.state, cur.recorded_by, cur.recorded_at = S_RECORDED, by, str(ev.get("at") or "")
                cur.claimed_by = cur.claimed_by or by
        elif kind == COLLECTED:
            if cur.state == S_RECORDED:
                cur.state, cur.collected_at = S_COLLECTED, str(ev.get("at") or "")
    return out


def entries() -> dict[str, Entry]:
    return fold(load_events())


async def append(events: list[dict], *, subject: str, attempts: int = 3) -> dict:
    """追加事件并推上去。被拒就 rebase 再推。"""
    if not events:
        return {"ok": True, "message": "没有要写的事件"}
    ok, why = available()
    if not ok:
        return {"ok": False, "message": why}
    async with _lock:
        if not (repo_dir() / ".git").is_dir():
            res = await _sync_locked()
            if not res["ok"]:
                return res
        d = repo_dir()
        with events_path().open("a", encoding="utf-8") as fp:
            for ev in events:
                fp.write(json.dumps(ev, ensure_ascii=False) + "\n")
        await _git(["add", "-A"], cwd=d)
        r = await _git([*_GIT_ID, "commit", "-q", "-m", f"{device()}: {subject}"], cwd=d)
        if not r.ok and "nothing to commit" not in (r.out + r.err):
            return {"ok": False, "message": f"提交事件失败：{_tail(r)}"}
        rr = r
        for attempt in range(1, attempts + 1):
            rr = await _git(["push", "-q", _url(), f"HEAD:{MAIN_BRANCH}"], cwd=d)
            if rr.ok:
                return {"ok": True, "message": "已同步到录屏仓库"}
            if attempt < attempts:
                await _git([*_GIT_ID, "pull", "--rebase", "-q", _url(), MAIN_BRANCH], cwd=d)
        return {"ok": False, "message": f"推送录屏仓库失败：{_tail(rr)}"}


# ---------------- 每题分支 ----------------

async def publish_branch(owner: str, task_no: str, files: dict[str, str | bytes]) -> dict:
    """把一道题的文档推成一个全新的孤儿分支（强推）。

    重新发布就是新一轮，旧一轮回传的视频按旧稿录的，一并清掉正是想要的效果。
    """
    branch = branch_of(owner, task_no)
    with tempfile.TemporaryDirectory(dir=scratch_dir(), prefix="pub-") as tmp:
        for name, body in files.items():
            p = Path(tmp) / name
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(body, bytes):
                p.write_bytes(body)
            else:
                p.write_text(body, encoding="utf-8")
        for args in (["init", "-q", "-b", "rec"], ["add", "-A"],
                     [*_GIT_ID, "commit", "-q", "-m", f"{device()}: publish {task_no}"]):
            r = await _git(args, cwd=tmp)
            if not r.ok:
                return {"ok": False, "message": f"准备分支失败：{_tail(r)}"}
        r = await _git(["push", "-q", "--force", _url(), f"HEAD:refs/heads/{branch}"], cwd=tmp, timeout=600)
        if not r.ok:
            return {"ok": False, "message": f"推送 {branch} 失败：{_tail(r)}"}
    return {"ok": True, "branch": branch}


async def _clone_branch(branch: str, dest: Path) -> tuple[bool, str]:
    r = await _git(["clone", "-q", "--depth", "1", "--single-branch", "-b", branch, _url(), str(dest)],
                   timeout=900)
    if r.ok:
        return True, ""
    tail = _tail(r)
    if "not found" in tail.lower() and "branch" in tail.lower():
        return False, f"录屏仓库里没有分支 {branch}，文档可能已被撤回"
    return False, f"拉取 {branch} 失败：{tail}"


async def read_file(owner: str, task_no: str, name: str) -> tuple[bool, str | bytes]:
    """读分支上的一个文件。文本文件返回 str。"""
    branch = branch_of(owner, task_no)
    with tempfile.TemporaryDirectory(dir=scratch_dir(), prefix="read-") as tmp:
        dest = Path(tmp) / "b"
        ok, why = await _clone_branch(branch, dest)
        if not ok:
            return False, why
        p = dest / name
        if not p.is_file():
            return False, f"{branch} 上没有 {name}"
        return True, (p.read_text(encoding="utf-8") if name.endswith((".md", ".json")) else p.read_bytes())


async def fetch_files(owner: str, task_no: str, names: list[str], into: Path) -> dict:
    """把分支上的几个文件拷到本地目录。返回 {ok, files: {name: path}, missing}。"""
    branch = branch_of(owner, task_no)
    into.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch_dir(), prefix="fetch-") as tmp:
        dest = Path(tmp) / "b"
        ok, why = await _clone_branch(branch, dest)
        if not ok:
            return {"ok": False, "message": why, "files": {}, "missing": names}
        got, missing = {}, []
        for name in names:
            src = dest / name
            if src.is_file():
                shutil.copy2(src, into / name)
                got[name] = into / name
            else:
                missing.append(name)
    return {"ok": not missing, "files": got, "missing": missing,
            "message": "" if not missing else f"{branch} 上缺 {'、'.join(missing)}"}


async def add_files(owner: str, task_no: str, files: dict[str, Path], *, subject: str) -> dict:
    """往已有分支上追加文件（录屏端回传视频）。"""
    for name, src in files.items():
        if src.stat().st_size > MAX_VIDEO_BYTES:
            mb = src.stat().st_size / 1024 / 1024
            return {"ok": False, "message": f"{name} 有 {mb:.0f} MB，超过 GitHub 单文件上限，"
                                            f"请按 720p 重新导出（一般几 MB）"}
    branch = branch_of(owner, task_no)
    with tempfile.TemporaryDirectory(dir=scratch_dir(), prefix="add-") as tmp:
        dest = Path(tmp) / "b"
        ok, why = await _clone_branch(branch, dest)
        if not ok:
            return {"ok": False, "message": why}
        for name, src in files.items():
            shutil.copy2(src, dest / name)
        await _git(["add", "-A"], cwd=dest)
        r = await _git([*_GIT_ID, "commit", "-q", "-m", f"{device()}: {subject}"], cwd=dest)
        if not r.ok and "nothing to commit" not in (r.out + r.err):
            return {"ok": False, "message": f"提交视频失败：{_tail(r)}"}
        r = await _git(["push", "-q", _url(), f"HEAD:refs/heads/{branch}"], cwd=dest, timeout=900)
        if not r.ok:
            return {"ok": False, "message": f"推送视频失败：{_tail(r)}"}
    return {"ok": True, "branch": branch}


async def delete_branch(owner: str, task_no: str) -> dict:
    branch = branch_of(owner, task_no)
    if not (repo_dir() / ".git").is_dir():
        res = await sync()
        if not res["ok"]:
            return res
    r = await _git(["push", "-q", _url(), f":refs/heads/{branch}"], cwd=repo_dir())
    if r.ok or "remote ref does not exist" in (r.err + r.out):
        return {"ok": True}
    return {"ok": False, "message": f"删除 {branch} 失败：{_tail(r)}"}
