"""跨设备题库：一个 GitHub 私有仓库，多台设备共写，同时充当查重池与可领取题库。

最初它只解决查重覆盖不到的那一段。solo-qa 的规则 A / C 查的是**已提交到平台**的历史
数据，而两台设备各自在本地出的新题，在提交之前对彼此完全不可见 —— 这边刚出的题和那边
昨天出的题撞了，要等都交上去才被平台判重，那时两边的机器时间已经烧掉了。

后来题库来源也收到了这里：池条目带上题面全文（`draft`）之后，一条池记录就足以在另一台
设备上还原出一道可领取的题，于是「谁出的题谁独占」这个旧限制没有了理由。现在池承担两件事：

- **查重**：出题前把全池投影成 `drafts/index.md` 给 skill 读，落地后再做一次字面兜底。
- **题库与领取**：`pool.jsonl` 是所有设备可见的题目全集，`claims.jsonl` 记谁领了哪道题。

载体选 GitHub 私有仓库而不是搭服务：两台设备都是本地起的，没有公共后端，而 gh token
出题本来就要用，等于零额外设施，还顺带拿到了版本历史和冲突合并。

两个 jsonl 都是 append-only，并且 `.gitattributes` 里给它们设了 `merge=union`：两台
设备同时各加几行时，union 合并会把两边的行都留下，不会产生需要人工解决的冲突。

union 也决定了读取侧的写法 —— 合并结果里必然有重复行，而且**行序不保证**。所以凡是
「多行折成一个结论」的地方，规则都必须与行序无关：

- `load()` 同 id 折叠时取字段更全的那行，而不是先出现的那行；
- `owners()` 把领取记录按时间戳排序后重放，先 claim 的赢。

两条规则都只依赖行的内容，因此两台设备读同一份文件必然得出同一个结论，不需要中心仲裁。

池目录放在 `DATA_DIR/pool`，不在 coder_root 下 —— 那边整个是出题资料，而 workspace
子目录会挂进容器，池文件绝不能出现在容器可见范围内（skill 红线 9）。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from app import config
from app.services import dockerx, settings_store

log = logging.getLogger("pool")

POOL_FILE = "pool.jsonl"
CLAIMS_FILE = "claims.jsonl"
DRAFTS_DIR = "prompts"
GITATTRIBUTES = f"{POOL_FILE} merge=union\n{CLAIMS_FILE} merge=union\n"
MAIN_BRANCH = "main"
INDEX_FILE = "index.md"

# 领取记录的两种动作。释放只认领取者本人发的，见 owners()。
ACTION_CLAIM = "claim"
ACTION_RELEASE = "release"

INDEX_HEADER = ("| 题号 | repo | 基底 | 任务类型 | 难度 | 功能点摘要 | 快照 SHA | 题面归档 |\n"
                "|---|---|---|---|---|---|---|---|\n")


def pool_dir() -> Path:
    return config.DATA_DIR / "pool"


def pool_path() -> Path:
    return pool_dir() / POOL_FILE


def claims_path() -> Path:
    return pool_dir() / CLAIMS_FILE


def enabled() -> bool:
    return settings_store.get_bool("pool.enabled", False)


def device() -> str:
    """本机在池里的标识。

    回退到 hostname 只是为了别让调用方拿到空串：后端跑在容器里，hostname 是容器 ID，
    每次 `compose up --build` 都会换一个。池条目的 id 带设备名，标识一变，同一道题就会
    以新 id 再入池一次，而另一台设备会把它看成一台新设备出的新题。所以这个值必须人工
    配死，available() 会把没配的情况挡在外面。
    """
    return settings_store.get("pool.device") or socket.gethostname() or "unknown"


_SLUG_BAD = re.compile(r"[^a-z0-9]+")


def _slug(name: str) -> str:
    """设备名压成只剩小写字母数字与连字符。

    这个值会拼进本机题号，而题号又会拼成容器名（`solo-cc-<题号>-<侧>`）和工作区目录名。
    Docker 容器名只认 `[a-zA-Z0-9_.-]`，设备名里一个空格或中文就能让整道题起不来容器，
    而报错要等到出闸那一刻才出现。
    """
    return _SLUG_BAD.sub("-", (name or "").strip().lower()).strip("-") or "unknown"


def local_task_no(entry: "Entry") -> str:
    """池条目在本机的题号。

    本机出的题保持原题号，别的设备的题后缀上设备名。两台设备各自从 01 开始编号，不区分
    就会撞在一起：题号是工作区目录名和容器名的一部分，撞号意味着两道题共用一个工作区。
    """
    return entry.task_no if entry.device == device() else f"{entry.task_no}-{_slug(entry.device)}"


def available() -> tuple[bool, str]:
    """池是否具备使用条件。只看本地可判断的部分，连通性留给实际调用。"""
    if not enabled():
        return False, "跨设备查重池未启用"
    if not settings_store.get("pool.repo"):
        return False, "未配置查重池仓库"
    if not settings_store.get("pool.device"):
        return False, "未配置本机标识，两台设备必须各填一个不同的值"
    if not settings_store.get("gh.token"):
        return False, "未配置 GitHub Token，无法读写查重池"
    return True, ""


# ---------------- 池条目 ----------------

@dataclass
class Entry:
    """池里的一道题。字段既要够查重与配额统计用，也要够在另一台设备上还原成可领取的题。"""

    task_no: str = ""
    device: str = ""
    repo_name: str = ""
    repo_id: str = ""          # 题目仓库 org/repo，与 qa_bridge.repo_id_of 同口径
    base_id: str = ""          # 基底：上游仓库@commit 或「自行设计」，查重与配额按它分组
    question_type: str = ""
    difficulty: str = ""
    summary: str = ""
    snapshot: str = ""
    user_prompt: str = ""
    # 完整题面 Markdown（render_draft 的产物）。查重只要正文，但领题要的远不止：
    # 仓库地址、初始快照、语言、Harness 版本、可复现等级全在题面的字段区里，缺了它
    # 另一台设备拿到的就只是一段没有出处的文字，clone 不了分支也提交不了。
    draft: str = ""
    created_at: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        """跨设备唯一。题号在两台设备上会撞，所以必须带设备名，再加正文哈希。

        正文哈希进 id 是为了让「同一道题改了题面」成为新的一行而不是覆盖：池是
        append-only 的，改题后两行都在，查重按最像的那行判，不会因为覆盖丢掉历史。
        """
        return f"{self.device}:{self.task_no}:{self.prompt_sha[:12]}"

    @property
    def prompt_sha(self) -> str:
        return hashlib.sha256(self.user_prompt.strip().encode("utf-8")).hexdigest()

    def to_json(self) -> dict:
        return {
            "id": self.id, "task_no": self.task_no, "device": self.device,
            "repo_name": self.repo_name, "repo_id": self.repo_id, "base_id": self.base_id,
            "question_type": self.question_type, "difficulty": self.difficulty,
            "summary": self.summary, "snapshot": self.snapshot,
            "prompt_sha256": self.prompt_sha, "user_prompt": self.user_prompt,
            **({"draft": self.draft} if self.draft else {}),
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
            **({"extra": self.extra} if self.extra else {}),
        }

    @classmethod
    def from_json(cls, raw: dict) -> "Entry":
        return cls(
            task_no=str(raw.get("task_no") or ""), device=str(raw.get("device") or ""),
            repo_name=str(raw.get("repo_name") or ""), repo_id=str(raw.get("repo_id") or ""),
            base_id=str(raw.get("base_id") or ""),
            question_type=str(raw.get("question_type") or ""),
            difficulty=str(raw.get("difficulty") or ""),
            summary=str(raw.get("summary") or ""), snapshot=str(raw.get("snapshot") or ""),
            user_prompt=str(raw.get("user_prompt") or ""),
            draft=str(raw.get("draft") or ""),
            created_at=str(raw.get("created_at") or ""),
            extra=raw.get("extra") if isinstance(raw.get("extra"), dict) else {},
        )


@dataclass
class Claim:
    """一条领取记录。claims.jsonl 里一行一条，只追加不修改。

    记的是动作而不是状态：状态要改行，而两台设备同时改同一行就是 union 合不掉的冲突。
    动作只追加，谁先谁后由 `at` 决定，重放一遍就得到当前归属，见 owners()。
    """

    entry_id: str = ""
    device: str = ""
    action: str = ACTION_CLAIM
    at: str = ""
    task_no: str = ""      # 冗余一份，直接翻 claims.jsonl 时不用回查池

    def to_json(self) -> dict:
        return {"entry_id": self.entry_id, "device": self.device, "action": self.action,
                "at": self.at or datetime.now(timezone.utc).isoformat(),
                "task_no": self.task_no}

    @classmethod
    def from_json(cls, raw: dict) -> "Claim":
        return cls(entry_id=str(raw.get("entry_id") or ""), device=str(raw.get("device") or ""),
                   action=str(raw.get("action") or ACTION_CLAIM),
                   at=str(raw.get("at") or ""), task_no=str(raw.get("task_no") or ""))


# ---------------- git 同步 ----------------

def _git_env() -> dict:
    env = dict(os.environ)
    if token := settings_store.get("gh.token"):
        env["GH_TOKEN"] = token
        env["GITHUB_TOKEN"] = token
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    return env


async def _sh(args: list[str], *, cwd: str | None = None, timeout: float = 180) -> dockerx.CmdResult:
    return await dockerx.run(args, cwd=cwd, timeout=timeout, env=_git_env())


def repo_slug() -> str:
    """把设置里的仓库值统一成 owner/repo。"""
    raw = settings_store.get("pool.repo").strip()
    if not raw:
        return ""
    raw = re.sub(r"^https?://(?:[^@]+@)?github\.com/", "", raw).removesuffix(".git")
    parts = [p for p in raw.split("/") if p]
    return "/".join(parts[:2]) if len(parts) >= 2 else ""


def _authed_url(slug: str) -> str:
    """带 token 的 URL，只在命令行上出现一次。

    不写进 `.git/config` 的 remote：那等于把 token 落盘到一个会被随手打包、
    随手 cat 的文件里。remote 存不带凭据的地址，每次 fetch / push 现拼。
    """
    token = settings_store.get("gh.token")
    return f"https://x-access-token:{token}@github.com/{slug}.git" if token else _plain_url(slug)


def _plain_url(slug: str) -> str:
    return f"https://github.com/{slug}.git"


async def _ensure_remote_repo(slug: str) -> tuple[bool, str]:
    """仓库不存在就建一个 private 的。"""
    r = await _sh(["gh", "repo", "view", slug, "--json", "visibility", "-q", ".visibility"], timeout=60)
    if r.ok:
        if r.out.strip().upper() == "PUBLIC":
            return False, f"{slug} 是公开仓库，池里存题面全文，必须用私有仓库"
        return True, ""
    rr = await _sh(["gh", "repo", "create", slug, "--private",
                    "--description", "internal dedup index"], timeout=120)
    if not rr.ok:
        return False, f"建查重池仓库 {slug} 失败：{(rr.err or rr.out).strip()[:200]}"
    return True, f"已创建私有仓库 {slug}"


async def _init_local(slug: str) -> tuple[bool, str]:
    """本地建库并推出第一个提交。远端是空仓库时走这条。"""
    d = pool_dir()
    d.mkdir(parents=True, exist_ok=True)
    for args in (["git", "init", "-q", "-b", MAIN_BRANCH],
                 ["git", "remote", "add", "origin", _plain_url(slug)]):
        r = await _sh(args, cwd=str(d))
        if not r.ok and "already exists" not in (r.err + r.out):
            return False, f"{' '.join(args[:2])} 失败：{r.err.strip()[:200]}"
    _write_scaffold()
    await _sh(["git", "add", "-A"], cwd=str(d))
    await _sh(["git", "-c", "user.email=solo-cli@local", "-c", "user.name=solo-cli",
               "commit", "-q", "-m", "init"], cwd=str(d))
    r = await _sh(["git", "push", "-u", _authed_url(slug), f"HEAD:{MAIN_BRANCH}"],
                  cwd=str(d), timeout=300)
    return (True, "") if r.ok else (False, f"推送题库失败：{r.err.strip()[:200]}")


def _write_scaffold() -> None:
    d = pool_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / ".gitattributes").write_text(GITATTRIBUTES, encoding="utf-8")
    for path in (pool_path(), claims_path()):
        if not path.exists():
            path.write_text("", encoding="utf-8")


async def sync() -> dict:
    """把远端池拉到本地。返回 {ok, message, count}。"""
    ok, why = available()
    if not ok:
        return {"ok": False, "message": why, "count": 0}
    slug = repo_slug()
    if not slug:
        return {"ok": False, "message": "查重池仓库格式不对，应为 owner/repo", "count": 0}

    ready, msg = await _ensure_remote_repo(slug)
    if not ready:
        return {"ok": False, "message": msg, "count": 0}

    d = pool_dir()
    if not (d / ".git").is_dir():
        d.parent.mkdir(parents=True, exist_ok=True)
        r = await _sh(["git", "clone", "-q", _authed_url(slug), str(d)], timeout=600)
        if r.ok:
            await _sh(["git", "remote", "set-url", "origin", _plain_url(slug)], cwd=str(d))
            _write_scaffold()
        else:
            # 远端是空仓库时 clone 会成功但没有分支；真失败才走本地初始化
            created, why2 = await _init_local(slug)
            if not created:
                return {"ok": False, "message": why2, "count": 0}
    else:
        r = await _sh(["git", "-c", "user.email=solo-cli@local", "-c", "user.name=solo-cli",
                       "pull", "--rebase", "-q", _authed_url(slug), MAIN_BRANCH],
                      cwd=str(d), timeout=300)
        if not r.ok:
            tail = (r.err or r.out).strip()[:200]
            # 空仓库或还没有 main：本地照样能用，等第一次 add 时再推上去
            if "couldn't find remote ref" not in tail and "Couldn't find remote ref" not in tail:
                # 拿本地副本顶上只在查重时说得通（无非是漏查一批）。领取不行：归属就记在
                # claims.jsonl 里，读的是陈旧副本就等于没问过远端，独占直接失效。
                # 所以这里必须把 stale 报出去，由调用方决定能不能接受。
                log.warning("拉取远端题库失败，本地副本可能已过期：%s", tail)
                return {"ok": True, "message": f"拉取失败，暂用本地副本：{tail}",
                        "count": len(load()), "stale": True}
    _write_scaffold()
    entries = load()
    return {"ok": True, "message": msg or f"池内 {len(entries)} 道题", "count": len(entries)}


async def commit_push(subject: str, *, done: str, attempts: int = 3) -> dict:
    """提交并推送本地池目录。被拒就 rebase 后重试。

    重试次数从 2 提到 3：领取会在用户点一下的瞬间推一行上去，两台设备同时点时必然有一方
    被拒，而 rebase 之后还可能撞上第三方的推送。多试一轮的代价是几百毫秒，推不上去的代价
    是这次领取要整个回滚。
    """
    slug = repo_slug()
    d = str(pool_dir())
    await _sh(["git", "add", "-A"], cwd=d)
    r = await _sh(["git", "-c", "user.email=solo-cli@local", "-c", "user.name=solo-cli",
                   "commit", "-q", "-m", f"{device()}: {subject}"], cwd=d)
    if not r.ok and "nothing to commit" in (r.out + r.err):
        return {"ok": True, "message": "远端题库无变化"}
    rr = r
    for attempt in range(1, attempts + 1):
        rr = await _sh(["git", "push", "-q", _authed_url(slug), f"HEAD:{MAIN_BRANCH}"],
                       cwd=d, timeout=300)
        if rr.ok:
            return {"ok": True, "message": done}
        if attempt < attempts:
            log.info("推送题库被拒，先 rebase 再试：%s", (rr.err or rr.out).strip()[:200])
            await _sh(["git", "-c", "user.email=solo-cli@local", "-c", "user.name=solo-cli",
                       "pull", "--rebase", "-q", _authed_url(slug), MAIN_BRANCH],
                      cwd=d, timeout=300)
    return {"ok": False, "message": f"推送题库失败：{(rr.err or rr.out).strip()[:200]}"}


async def push(entries_added: int) -> dict:
    """推一批新题。"""
    return await commit_push(f"+{entries_added}",
                             done=f"已推送 {entries_added} 道题到远端题库")


# ---------------- 读写 ----------------

def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            rows.append(raw)
    return rows


def load() -> list[Entry]:
    """读全池。按 id 去重：merge=union 会留下重复行，这里折掉。

    同 id 时保留题面全文更完整的那行，而不是先出现的那行。补 draft 是把整行重写一遍
    追加进去的（见 backfill_drafts），补之前那行还在，两行 id 相同；而 union 合并后的
    行序不保证，取「先出现的」会让补进去的题面在一部分设备上永远读不到。
    """
    out: dict[str, Entry] = {}
    for raw in _read_jsonl(pool_path()):
        e = Entry.from_json(raw)
        if not e.user_prompt:
            continue
        key = str(raw.get("id") or e.id)
        old = out.get(key)
        if old is None or (not old.draft and e.draft):
            out[key] = e
    return list(out.values())


def load_claims() -> list[Claim]:
    """读全部领取记录。这里不折叠：归属要靠按时间重放全部动作才能算出来。"""
    return [c for c in (Claim.from_json(r) for r in _read_jsonl(claims_path()))
            if c.entry_id and c.device]


def owners() -> dict[str, str]:
    """每道题当前归谁，{entry_id: device}。没被领的题不出现在结果里。

    仲裁只看文件内容，不看谁先 push：union 合并后两台设备手上的 claims.jsonl 内容一致
    但行序未必一致，所以先按 `(at, device, action)` 排序再重放 —— 排序键不含行号，
    两边必然算出同一个归属。

    重放规则是「先 claim 的赢」：无主时 claim 生效，有主时后来的 claim 一律忽略；
    release 只有领取者本人发的才作数，否则一台设备就能把另一台正在做的题抢过来。

    时间戳撞上的概率极低（ISO 到微秒），真撞了就按设备名字典序，仍然是确定的。
    """
    by_entry: dict[str, list[Claim]] = {}
    for c in load_claims():
        by_entry.setdefault(c.entry_id, []).append(c)
    out: dict[str, str] = {}
    for entry_id, rows in by_entry.items():
        rows.sort(key=lambda c: (c.at, c.device, c.action))
        holder = ""
        for c in rows:
            if c.action == ACTION_CLAIM and not holder:
                holder = c.device
            elif c.action == ACTION_RELEASE and c.device == holder:
                holder = ""
        if holder:
            out[entry_id] = holder
    return out


def append_claim(claim: Claim) -> None:
    _write_scaffold()
    with claims_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(claim.to_json(), ensure_ascii=False) + "\n")


def drop_claim(claim: Claim) -> None:
    """把本地那一行领取记录抹掉。

    只在「写了但没推上去」时用：远端不知道这次领取，本地留着它会让本机以为自己占着题，
    而另一台设备照领不误 —— 这正是回写机制要防的重复领取，方向反了而已。
    """
    path = claims_path()
    if not path.is_file():
        return
    target = json.dumps(claim.to_json(), ensure_ascii=False)
    kept = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip() != target]
    path.write_text("".join(ln + "\n" for ln in kept if ln.strip()), encoding="utf-8")


def draft_path(entry: Entry) -> Path:
    """题面在仓库里的镜像位置。按设备分目录，两台设备的 01 题不会写到同一个文件上。"""
    return pool_dir() / DRAFTS_DIR / _slug(entry.device) / f"{entry.task_no}.md"


def write_draft_mirror(entries: list[Entry]) -> int:
    """把题面另存一份 Markdown 到仓库里。

    真相源是 `pool.jsonl` 里的 `draft` 字段，这些 .md 纯粹是给人看的：在 GitHub 上点开
    就能读一道题，不必把一行几千字的 JSON 拷出来格式化。所以这里写失败不影响任何流程。
    """
    n = 0
    for e in entries:
        if not e.draft:
            continue
        path = draft_path(e)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(e.draft, encoding="utf-8")
        n += 1
    return n


def append(entries: list[Entry]) -> int:
    """追加到本地池文件，已在池里的跳过。返回实际写入行数。"""
    if not entries:
        return 0
    _write_scaffold()
    known = {e.id for e in load()}
    fresh = [e for e in entries if e.id not in known]
    if not fresh:
        return 0
    with pool_path().open("a", encoding="utf-8") as fh:
        for e in fresh:
            fh.write(json.dumps(e.to_json(), ensure_ascii=False) + "\n")
    write_draft_mirror(fresh)
    return len(fresh)


async def add(entries: list[Entry]) -> dict:
    """本地追加并推远端。池不可用时静默跳过，不拦出题。"""
    ok, why = available()
    if not ok:
        return {"ok": False, "message": why, "added": 0}
    n = append(entries)
    if not n:
        return {"ok": True, "message": "远端题库里已有这些题", "added": 0}
    res = await push(n)
    return {"ok": res["ok"], "message": res["message"], "added": n}


# ---------------- 领取（跨设备独占） ----------------

async def claim_remote(entry_id: str, *, task_no: str = "") -> dict:
    """在远端把一道题占下来。返回 {ok, taken_by, message}。

    git 没有 compare-and-swap，独占是靠「推上去 + 推完再核对」两步凑出来的：

    1. 先 `sync` 拉最新，已经有主就直接拒，省掉一次没必要的 push；
    2. 写一行 claim 并推。被拒说明期间有人推过东西，`commit_push` 会 rebase 后重试；
    3. 推成功也**还不算领到** —— `merge=union` 会把两台设备的 claim 都留下，谁赢由
       `owners()` 按时间戳判，而不是由谁先 push 判。所以推完必须再拉一次重新核对。

    第 3 步是这套机制里唯一不能省的：少了它，两台设备会各自看到自己 push 成功，然后
    双双开始做同一道题，而远端文件里明明白白写着只有一个赢家。

    池没启用（单设备）时直接放行 —— 这时候不存在第二台设备，独占无从谈起。
    """
    ok, why = available()
    if not ok:
        return {"ok": True, "skipped": True, "message": why}

    synced = await sync()
    if not synced["ok"] or synced.get("stale"):
        # stale 是「拉失败了，手上这份是旧的」。查重时旧副本还能顶一顶，领取不行：
        # 归属就记在远端，读旧副本等于没问过，两台设备会双双认为这题没人领。
        return {"ok": False,
                "message": f"连不上远端题库，无法确认这道题没被别人领走：{synced['message']}"}

    me = device()
    held = owners().get(entry_id, "")
    if held and held != me:
        return {"ok": False, "taken_by": held, "message": f"这道题已被「{held}」领取"}
    if held == me:
        return {"ok": True, "already": True, "message": "本机已领取过这道题"}

    claim = Claim(entry_id=entry_id, device=me, action=ACTION_CLAIM,
                  at=datetime.now(timezone.utc).isoformat(), task_no=task_no)
    append_claim(claim)
    pushed = await commit_push(f"claim {task_no or entry_id}", done="已在远端登记领取")
    if not pushed["ok"]:
        drop_claim(claim)
        return {"ok": False, "message": f"领取没能同步到远端，已撤销：{pushed['message']}"}

    await sync()
    winner = owners().get(entry_id, "")
    if winner and winner != me:
        return {"ok": False, "taken_by": winner,
                "message": f"这道题几乎同时被「{winner}」领走了，对方在先"}
    return {"ok": True, "message": "已在远端登记领取"}


async def release_remote(entry_id: str, *, task_no: str = "") -> dict:
    """把领取还回去，让别的设备能领。只有领取者本人发的释放才作数。"""
    ok, why = available()
    if not ok:
        return {"ok": True, "skipped": True, "message": why}
    await sync()
    me = device()
    held = owners().get(entry_id, "")
    if not held:
        return {"ok": True, "message": "远端本来就没有这道题的领取记录"}
    if held != me:
        return {"ok": False, "message": f"这道题在远端登记给「{held}」，本机放不了"}
    append_claim(Claim(entry_id=entry_id, device=me, action=ACTION_RELEASE,
                       at=datetime.now(timezone.utc).isoformat(), task_no=task_no))
    return await commit_push(f"release {task_no or entry_id}", done="已在远端撤销领取")


# ---------------- 题库索引投影 ----------------

def render_index() -> str:
    """把全池渲染成 skill 认的题库索引表格。

    skill 的 Phase 3 读 `drafts/index.md` 做功能点查重与按基底的配额统计，所以只要把
    另一台设备的题也渲染进这张表，跨设备语义查重就由设计阶段顺带完成了，不必再单独
    跑一轮模型判断。

    本机的题同样来自池（落地时写进去的），所以这里是整表重建而不是追加 —— 索引由池
    投影出来，池是唯一真相源，避免两边各记一份又对不上。
    """
    rows = []
    for e in sorted(load(), key=lambda x: (x.device != device(), x.task_no)):
        # 别的设备出的题标出来：题号在两台设备上各自编号，不标会看成本机的题
        no = e.task_no if e.device == device() else f"{e.task_no}@{e.device}"
        archive = f"{config.PROMPTS_ARCHIVE_DIR}/{e.task_no}.md" if e.device == device() else "（另一台设备）"
        rows.append(f"| {no} | {e.repo_name} | {e.base_id} | {e.question_type} "
                    f"| {e.difficulty} | {e.summary} | {e.snapshot} | {archive} |\n")
    return INDEX_HEADER + "".join(rows)


def write_index() -> dict:
    """把投影写进 drafts/index.md，给 skill 读。"""
    entries = load()
    if not entries:
        return {"ok": True, "message": "池为空，索引未改动", "count": 0}
    path = config.CODER_ROOT_MOUNT / config.PROMPTS_ARCHIVE_DIR / INDEX_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_index(), encoding="utf-8")
    mine = sum(1 for e in entries if e.device == device())
    return {"ok": True, "count": len(entries),
            "message": f"题库索引已按池重建：本机 {mine} 道、其他设备 {len(entries) - mine} 道"}


# ---------------- 字面查重 ----------------

_NON_WORD = re.compile(r"[\s\W_]+", re.UNICODE)


def normalize(text: str) -> str:
    """归一化：只留字母数字与汉字，统一小写。

    查的是「同一道题换了措辞」，所以标点、换行、空格一律不参与比较。
    """
    return _NON_WORD.sub("", (text or "").lower())


def similarity(a: str, b: str, *, floor: float = 0.0) -> float:
    """两段题面的相似度，0 到 1。

    floor 是「低于这个值就不关心具体是多少」，用来提前退出。quick_ratio 只比字符频次，
    是真实 ratio 的**上界**且快得多，上界都到不了 floor 时真实值一定也到不了，直接返回
    0 —— 池上千条时省掉的是几十秒。

    注意这里返回的是 0 而不是 quick_ratio 本身：上界比真实值大，把它当相似度报出去会
    让本来不相似的题被判成重复。调用方只拿它跟阈值比，所以「确定低于 floor」用 0 表达
    最安全。
    """
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    m = SequenceMatcher(None, na, nb, autojunk=False)
    if floor and m.quick_ratio() < floor:
        return 0.0
    return m.ratio()


def find_duplicates(items: list[dict], *, threshold: float = 0.0) -> dict[str, dict]:
    """字面查重。items: [{key, user_prompt, repo_id?, base_id?}]，返回命中的 key。

    这是设计阶段模型查重之后的确定性兜底。同时比两个方向：

    - 与池里的题比（含另一台设备的）
    - 同批候选之间互比 —— 一次要 10 道题，模型自己批内撞车是常事

    同基底会让相似度天然偏高（背景段落往往雷同），所以命中时把基底一并报出来，
    人能一眼看出是真撞了还是同项目的不同功能点。
    """
    thr = threshold or _threshold()
    pooled = load()
    hits: dict[str, dict] = {}
    for idx, it in enumerate(items):
        key = str(it.get("key") or idx)
        text = str(it.get("user_prompt") or "")
        if not text.strip():
            continue
        best: tuple[float, str, str] = (0.0, "", "")
        for e in pooled:
            score = similarity(text, e.user_prompt, floor=thr)
            if score > best[0]:
                best = (score, f"池内 {e.task_no}@{e.device}（{e.base_id or '基底未记'}）", e.summary)
        for jdx, other in enumerate(items):
            if jdx == idx:
                continue
            score = similarity(text, str(other.get("user_prompt") or ""), floor=thr)
            if score > best[0]:
                best = (score, f"同批 {other.get('key') or jdx}", str(other.get("summary") or ""))
        if best[0] >= thr:
            hits[key] = {"similarity": round(best[0], 4), "against": best[1],
                         "summary": best[2],
                         "reason": f"题面与{best[1]}字面相似度 {best[0]:.0%}，超过阈值 {thr:.0%}"}
    return hits


DEFAULT_THRESHOLD = 0.45


def _threshold() -> float:
    try:
        v = float(settings_store.get("pool.similarity") or DEFAULT_THRESHOLD)
    except ValueError:
        return DEFAULT_THRESHOLD
    return v if 0 < v <= 1 else DEFAULT_THRESHOLD


# ---------------- 首次导入本机既有题 ----------------

def parse_index() -> dict[str, dict]:
    """读现有 `drafts/index.md`，按题号取出各列。

    题面里没有「功能点摘要」这个字段 —— 它只存在于索引表，是出题时单独写进去的。
    而摘要恰恰是功能点查重的依据，用题面里的「来源说明」顶替不行：那段话是模板化的
    （「上游 X，选定 commit Y，选择理由…」），几十道题之间高度雷同，拿它查重等于没查。
    所以既有的索引必须当成数据源读回来，而不是重新生成一遍。
    """
    path = config.CODER_ROOT_MOUNT / config.PROMPTS_ARCHIVE_DIR / INDEX_FILE
    if not path.is_file():
        return {}
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 7 or cols[0] in ("题号", "---") or set(cols[0]) <= {"-"}:
            continue
        # 题号列可能带设备后缀（投影写回来的），只认本机那部分
        no = cols[0].split("@", 1)[0]
        out[no] = {"repo_name": cols[1], "base_id": cols[2], "question_type": cols[3],
                   "difficulty": cols[4], "summary": cols[5], "snapshot": cols[6]}
    return out


def local_draft_text(task_no: str) -> str:
    """本机归档的整份题面。池里的 draft 字段就是它。"""
    path = config.CODER_ROOT_MOUNT / config.PROMPTS_ARCHIVE_DIR / f"{task_no}.md"
    try:
        return path.read_text(encoding="utf-8") if path.is_file() else ""
    except OSError:
        return ""


async def backfill_drafts() -> dict:
    """给池里本机那些还没有题面全文的老条目补上 draft。

    题面全文是后加的字段，在那之前入池的题只有 prompt 正文，另一台设备拿到它还原不出
    仓库地址和初始快照，也就领不了。补的办法是把整行重写一遍追加进去：池 append-only，
    同 id 的新旧两行都在，`load()` 按「题面更全者优先」折叠，于是补过的那份胜出。
    """
    ok, why = available()
    if not ok:
        return {"ok": False, "message": why, "filled": 0}
    synced = await sync()
    if not synced["ok"]:
        return {"ok": False, "message": synced["message"], "filled": 0}

    me = device()
    filled = [
        Entry(**{**e.__dict__, "draft": text})
        for e in load()
        if e.device == me and not e.draft and (text := local_draft_text(e.task_no))
    ]
    if not filled:
        return {"ok": True, "message": "本机入池的题都带着题面全文，无需补", "filled": 0}

    _write_scaffold()
    with pool_path().open("a", encoding="utf-8") as fh:
        for e in filled:
            fh.write(json.dumps(e.to_json(), ensure_ascii=False) + "\n")
    write_draft_mirror(filled)
    res = await commit_push(f"backfill {len(filled)}",
                            done=f"已给 {len(filled)} 道老题补上题面全文")
    return {"ok": res["ok"], "message": res["message"], "filled": len(filled)}


def bootstrap_entries() -> list[Entry]:
    """把本机题库里已有的题转成池条目。

    第一次启用池时用：池是空的，而本机已经出了几十道题，不导进去就等于告诉另一台设备
    「这边还没出过题」，它会重出一遍。

    字段以既有索引为准、题面补齐：索引里的摘要与基底是出题当时写下的，比从题面反推的
    准。索引缺这道题时才退回题面解析，此时基底取来源说明里的上游与 commit，取不到就
    留空 —— 宁可让配额统计少一个分组，也不要编一个基底出来。
    """
    from app.services import gsb_repo, prompt_bank

    dev = device()
    indexed = parse_index()
    out: list[Entry] = []
    for p in prompt_bank.parse_sources():
        meta = p.meta or {}
        row = indexed.get(p.task_no, {})
        snapshot = gsb_repo.first_url(p.fields.get("env_snapshot", ""))
        repo_url = gsb_repo.parse_repo_url(meta)
        out.append(Entry(
            task_no=p.task_no, device=dev,
            repo_name=row.get("repo_name") or (repo_url.rstrip("/").split("/")[-1] if repo_url else ""),
            repo_id=_repo_id(snapshot or repo_url),
            base_id=row.get("base_id") or _base_id_from(meta),
            question_type=row.get("question_type") or p.fields.get("question_type", ""),
            difficulty=row.get("difficulty") or p.fields.get("difficulty", ""),
            summary=row.get("summary") or "",
            snapshot=row.get("snapshot") or _sha_of(snapshot),
            user_prompt=p.user_prompt,
            draft=local_draft_text(p.task_no),
        ))
    return out


def _repo_id(url: str) -> str:
    s = (url or "").strip()
    if "github.com/" not in s:
        return ""
    parts = [x for x in s.split("github.com/", 1)[1].split("/") if x]
    return "/".join(parts[:2]) if len(parts) >= 2 else ""


def _base_id_from(meta: dict) -> str:
    """来源说明里带上游地址与 commit 时拼成 slug@sha，否则按自行设计。"""
    note = meta.get("来源说明") or ""
    m = re.search(r"github\.com/([^/\s]+)/([^/\s,，）)]+)", note)
    sha = re.search(r"\b([0-9a-f]{40})\b", note)
    if m:
        return f"{m.group(1)}/{m.group(2).removesuffix('.git')}@{sha.group(1) if sha else ''}"
    return "自行设计" if "自行设计" in note else ""


def _sha_of(url: str) -> str:
    m = re.search(r"\b([0-9a-f]{40})\b", url or "")
    return m.group(1) if m else ""


async def bootstrap() -> dict:
    """把本机既有题一次性导入池。已在池里的会被 append 自己跳过。"""
    ok, why = available()
    if not ok:
        return {"ok": False, "message": why, "added": 0}
    synced = await sync()
    if not synced["ok"]:
        return {"ok": False, "message": synced["message"], "added": 0}
    return await add(bootstrap_entries())


def snapshot() -> dict:
    """给界面看的池状态。"""
    ok, why = available()
    entries = load() if ok else []
    dev = device()
    held = owners() if ok else {}
    by_device: dict[str, int] = {}
    for e in entries:
        by_device[e.device or "unknown"] = by_device.get(e.device or "unknown", 0) + 1
    claimed_by_me = sum(1 for d in held.values() if d == dev)
    return {
        "enabled": enabled(), "ok": ok, "message": why,
        "repo": repo_slug(), "device": dev, "threshold": _threshold(),
        "total": len(entries), "mine": by_device.get(dev, 0), "by_device": by_device,
        # 领取是跨设备口径：claimed 是全局已被领走的题数，unclaimed 才是这台机器还能领的
        "claimed": len(held), "claimed_by_me": claimed_by_me,
        "claimed_by_others": len(held) - claimed_by_me,
        "unclaimed": sum(1 for e in entries if e.id not in held),
        "draftless": sum(1 for e in entries if not e.draft),
    }
