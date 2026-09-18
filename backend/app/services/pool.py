"""跨设备查重池：一个 GitHub 私有仓库里的 jsonl，多台设备共写。

要解决的问题是 solo-qa 的查重覆盖不到的那一段。它的规则 A / C 查的是**已提交到平台**
的历史数据，而两台设备各自在本地出的新题，在提交之前对彼此完全不可见 —— 这边刚出的题
和那边昨天出的题撞了，要等都交上去才被平台判重，那时两边的机器时间已经烧掉了。

所以池里存的是「已经出了但还没进平台历史」的题。载体选 GitHub 私有仓库而不是搭服务：
两台设备都是本地起的，没有公共后端，而 gh token 出题本来就要用，等于零额外设施，
还顺带拿到了版本历史和冲突合并。

池文件 append-only，并且 `.gitattributes` 里给它设了 `merge=union`：两台设备同时
各加几行时，union 合并会把两边的行都留下，不会产生需要人工解决的冲突。行内用 id 去重，
union 合出来的重复行读取时自然被折掉。

池在两个环节起作用：

- 出题前 `sync` 拉最新，再 `render_index` 把全池渲染成 `drafts/index.md`。skill 的
  Phase 3 本来就要读这个索引做功能点查重与配额统计，于是「另一台设备出过什么」这件事
  自动进入了设计阶段的语义查重，不需要额外再问一次模型。
- 落地后 `find_duplicates` 做一次确定性的字面查重兜底。设计阶段的查重是模型判断，
  它可能漏；字面这层漏不了，代价也只是几十毫秒。

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
GITATTRIBUTES = "pool.jsonl merge=union\n"
MAIN_BRANCH = "main"
INDEX_FILE = "index.md"

INDEX_HEADER = ("| 题号 | repo | 基底 | 任务类型 | 难度 | 功能点摘要 | 快照 SHA | 题面归档 |\n"
                "|---|---|---|---|---|---|---|---|\n")


def pool_dir() -> Path:
    return config.DATA_DIR / "pool"


def pool_path() -> Path:
    return pool_dir() / POOL_FILE


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
    """池里的一道题。字段取的是查重与配额统计真正要用的那些。"""

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
            created_at=str(raw.get("created_at") or ""),
            extra=raw.get("extra") if isinstance(raw.get("extra"), dict) else {},
        )


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
    r = await _sh(["git", "push", "-u", _authed_url(slug), f"HEAD:{MAIN_BRANCH}"], timeout=300)
    return (True, "") if r.ok else (False, f"推送查重池失败：{r.err.strip()[:200]}")


def _write_scaffold() -> None:
    d = pool_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / ".gitattributes").write_text(GITATTRIBUTES, encoding="utf-8")
    if not pool_path().exists():
        pool_path().write_text("", encoding="utf-8")


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
                       "pull", "--rebase", "-q", _authed_url(slug), MAIN_BRANCH], timeout=300)
        if not r.ok:
            tail = (r.err or r.out).strip()[:200]
            # 空仓库或还没有 main：本地照样能用，等第一次 add 时再推上去
            if "couldn't find remote ref" not in tail and "Couldn't find remote ref" not in tail:
                log.warning("拉取查重池失败，先用本地副本：%s", tail)
                return {"ok": True, "message": f"拉取失败，暂用本地副本：{tail}",
                        "count": len(load()), "stale": True}
    _write_scaffold()
    entries = load()
    return {"ok": True, "message": msg or f"池内 {len(entries)} 道题", "count": len(entries)}


async def push(entries_added: int) -> dict:
    """提交并推送。冲突就 rebase 后重试一次。"""
    slug = repo_slug()
    d = str(pool_dir())
    await _sh(["git", "add", "-A"], cwd=d)
    r = await _sh(["git", "-c", "user.email=solo-cli@local", "-c", "user.name=solo-cli",
                   "commit", "-q", "-m", f"{device()}: +{entries_added}"], cwd=d)
    if not r.ok and "nothing to commit" in (r.out + r.err):
        return {"ok": True, "message": "池无变化"}
    for attempt in (1, 2):
        rr = await _sh(["git", "push", "-q", _authed_url(slug), f"HEAD:{MAIN_BRANCH}"],
                       cwd=d, timeout=300)
        if rr.ok:
            return {"ok": True, "message": f"已推送 {entries_added} 道题到查重池"}
        if attempt == 1:
            log.info("推送查重池被拒，先 rebase 再试：%s", (rr.err or rr.out).strip()[:200])
            await _sh(["git", "-c", "user.email=solo-cli@local", "-c", "user.name=solo-cli",
                       "pull", "--rebase", "-q", _authed_url(slug), MAIN_BRANCH],
                      cwd=d, timeout=300)
    return {"ok": False, "message": f"推送查重池失败：{(rr.err or rr.out).strip()[:200]}"}


# ---------------- 读写 ----------------

def load() -> list[Entry]:
    """读全池。按 id 去重：merge=union 会留下重复行，这里折掉。"""
    path = pool_path()
    if not path.is_file():
        return []
    out: dict[str, Entry] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict):
            continue
        e = Entry.from_json(raw)
        if e.user_prompt:
            out.setdefault(str(raw.get("id") or e.id), e)
    return list(out.values())


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
    return len(fresh)


async def add(entries: list[Entry]) -> dict:
    """本地追加并推远端。池不可用时静默跳过，不拦出题。"""
    ok, why = available()
    if not ok:
        return {"ok": False, "message": why, "added": 0}
    n = append(entries)
    if not n:
        return {"ok": True, "message": "池里已有这些题", "added": 0}
    res = await push(n)
    return {"ok": res["ok"], "message": res["message"], "added": n}


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
    by_device: dict[str, int] = {}
    for e in entries:
        by_device[e.device or "unknown"] = by_device.get(e.device or "unknown", 0) + 1
    return {
        "enabled": enabled(), "ok": ok, "message": why,
        "repo": repo_slug(), "device": dev, "threshold": _threshold(),
        "total": len(entries), "mine": by_device.get(dev, 0), "by_device": by_device,
    }
