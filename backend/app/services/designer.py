"""出题：规则在 solo-prompt skill 里，本地只做确定性编排。

整份 SOP 里真正需要判断力的只有「出一道什么题」，这一步交给 Cursor CLI 执行
`/solo-prompt`，出题口径、红线、难度档位与配比、查重与配额要求一律以那份 skill 为准。
**本文件不留第二份出题规则**：写两份必然漂移，而漂移不会报错，只会安静地出一批
不合规的题——改了 skill 却不生效，是这条流水线上最难发现的一类故障。

剩下的全是固定动作，留在本地：

    Phase 1 环境实测  →  出题时 CLI 是只读模式，起不了容器，由 dockerx 代为实测
    Phase 5 环境落地  →  一串固定的 git 与 gh 命令，输入输出都确定
    Phase 6 写题面    →  一个固定模板，字段一一对应

这样拆的收益是失败点可定位。把整份 SOP 甩给 agent 自己漫游的那版，一跑一个多小时，
中途任何一步失败都只能从几百条工具调用里翻原因；现在失败是「哪道题的哪一步崩了」，
而且一道题失败不影响同批其他题。

上游 commit 不让模型给。模型报不出一个真实存在的 40 位 SHA，它编一个出来要到 clone
那一步才炸，而那时仓库可能已经建好了。改成本地用 git ls-remote 取上游默认分支的当前
HEAD 当基线——这也正是现有题目的做法（「该 commit 是取用时的上游最新提交」）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from collections import Counter
from pathlib import Path

from app import config
from app.db import session
from app.events import bus
from app.models import (
    AVAILABLE, DESIGN_CANCELLED, DESIGN_DEDUP, DESIGN_DONE, DESIGN_FAILED, DESIGN_RUNNING,
    DISCARDED, ORIGIN_DESIGNED, DesignRun, Task, utc_now,
)
from app.services import dockerx, gsb_repo, llm, pool, prompt_bank, qa_bridge, settings_store

log = logging.getLogger("designer")

running: dict[int, asyncio.Task] = {}

STAGING_DIR = "staging"
INDEX_FILE = "index.md"
MAIN_BRANCH = "main"

# 题面模板。字段顺序与 prompt_bank 的解析顺序一致，改这里就要同步改那边的 FIELD_MAP。
DRAFT_TEMPLATE = """题号：{task_no}

对应项目

仓库：{repo_url}（本题专属，分支只有 main / A / B）
基线分支：main，落地后不再改动，快照 SHA 即此分支 HEAD
A 侧：分支 A，本地 {coder_root}/workspace/{task_no}/A，容器 /workspace，轨迹 {coder_root}/sessions/{task_no}/A/
B 侧：分支 B，本地 {coder_root}/workspace/{task_no}/B，容器 /workspace，轨迹 {coder_root}/sessions/{task_no}/B/
来源说明：{origin_note}
基底标识：{base_id}

提交参数

任务类型：{question_type}
任务难度：{difficulty}
语言/框架：{languages}
Harness：Claude Code
Harness 版本：{harness_version}
操作系统：MacOS/Linux
环境可复现等级：{repro_level}
初始环境快照：{repo_url}/commit/{snapshot}（A、B 两侧共用）
SessionID：A 侧待回填 / B 侧待回填，各取对应轨迹 jsonl 文件名的 UUID
TurnID/PromptID：A 侧待回填 / B 侧待回填，各取该侧本轮 user 消息的 promptId

以下为发送给模型的 prompt 正文，A 侧与 B 侧发送同一份，整段复制。

{prompt_body}
"""


def _publish(run_id: int) -> None:
    bus.publish("design", {"type": "design", "id": run_id})


def _set(run_id: int, **fields) -> None:
    with session() as db:
        r = db.get(DesignRun, run_id)
        if r is None:
            return
        for k, v in fields.items():
            setattr(r, k, v)
    _publish(run_id)


def _append_log(run_id: int, line: str) -> None:
    """出题要跑一阵子，进度只能从这里看。"""
    log.info("design %s · %s", run_id, line)
    with session() as db:
        r = db.get(DesignRun, run_id)
        if r is None:
            return
        tail = (r.log or "").splitlines()[-400:]
        tail.append(line)
        r.log = "\n".join(tail)
    _publish(run_id)


def preflight() -> list[dict]:
    """出题前的条件检查，界面上直接显示缺什么。"""
    checks = []

    def add(name: str, ok: bool, msg: str) -> None:
        checks.append({"name": name, "ok": ok, "message": msg})

    add("cursor_cli", bool(llm.agent_bin()), "已安装" if llm.agent_bin() else "后端镜像里没有 agent")
    key = settings_store.get("cursor.api_key")
    add("cursor_key", bool(key), "已配置" if key else "未配置 Cursor API Key")
    # 出题规则全在 skill 里，接不上就等于没有规则，必须挡在前面
    linked, skill_msg = llm.ensure_skills_linked()
    add("skill", linked, f"{config.SKILL_NAME} 已就绪" if linked else skill_msg)
    add("gh", bool(shutil.which("gh")), "已安装" if shutil.which("gh") else "后端镜像里没有 gh，出题无法建仓库")
    add("gh_token", bool(settings_store.get("gh.token")), "已配置" if settings_store.get("gh.token") else "未配置 GitHub Token")
    brief = config.CODER_ROOT_MOUNT / config.BRIEF_FILE
    add("requirements", brief.exists(),
        "已就绪" if brief.exists() else f"工作区里没有 {config.BRIEF_FILE}，定不了本期口径")
    ok, why = qa_bridge.available()
    add("dedup", ok, "查重可用" if ok else why)
    # 池是可选的：单设备用不着它。没启用算正常状态而不是缺陷，否则整页的「就绪」
    # 会被一个有意关掉的功能拉成未就绪。只有「启用了但没配好」才算问题。
    pool_ok, pool_why = pool.available()
    snap = pool.snapshot()
    if not pool.enabled():
        add("pool", True, "未启用（单设备模式）")
    else:
        add("pool", pool_ok,
            f"{snap['repo']} · 本机 {snap['mine']} 道 / 共 {snap['total']} 道" if pool_ok else pool_why)
    return checks


def _gh_env() -> dict:
    """gh 与 git push 都靠 token，不落盘到工作区。"""
    import os

    env = dict(os.environ)
    if token := settings_store.get("gh.token"):
        env["GH_TOKEN"] = token
        env["GITHUB_TOKEN"] = token
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    return env


async def _sh(args: list[str], *, cwd: str | None = None, timeout: float = 300) -> dockerx.CmdResult:
    return await dockerx.run(args, cwd=cwd, timeout=timeout, env=_gh_env())


# ---------------- 选题（唯一用到模型的一步） ----------------

def _env_facts(caps: dict, harness_version: str) -> str:
    """把实测到的容器能力写成给 skill 看的事实清单。

    只陈述事实，不替 skill 下「所以不能出什么题」的结论——那条推论写在 skill 的
    Phase 1 里，它自己会按清单约束选题。
    """
    if not caps.get("ok"):
        return f"实测失败：{caps.get('error') or '未知原因'}。请按最保守的假设设计题目。"
    cmds = caps.get("commands") or {}
    have = sorted(c for c, ok in cmds.items() if ok)
    missing = sorted(c for c, ok in cmds.items() if not ok)
    net = caps.get("network") or {}
    reachable = [u for u, code in net.items() if code.startswith(("2", "3", "4")) and code != "000"]
    unreachable = [u for u, code in net.items() if u not in reachable]
    lines = [
        f"容器内已有命令：{'、'.join(have) or '无'}",
        f"容器内缺失命令：{'、'.join(missing) or '无'}",
        f"外网可达：{'、'.join(reachable) or '无'}",
    ]
    if unreachable:
        lines.append(f"外网不可达：{'、'.join(unreachable)}")
    lines.append(f"Harness 版本（claude --version 实测）：{harness_version or '取不到'}")
    return "\n".join(lines)


def _skill_prompt(count: int, note: str, env_facts: str) -> str:
    """调 solo-prompt skill 出题。

    这里刻意不写任何出题规则：难度档位、配比、任务类型、查重、prompt 写法全部在 skill
    里，本函数只交代两件事——哪些 Phase 由本地代码接手，以及产出用什么格式回传。
    往这段话里补规则等于在 skill 之外开第二个真相源，见模块头部说明。
    """
    return f"""/solo-prompt {count} {note.strip()}

以下是本次调用的执行边界。它不改变 skill 的任何规则，只说明哪些步骤由调用方接手。
出题口径、红线、任务类型与难度档位、难度配比、查重与配额，一律以 skill 为准。

你负责：Phase 0 读当期口径、Phase 3 查重与配额、Phase 3.5 批量规划、Phase 4 完整设计
（禁止项筛查、定类型与难度、难度来源、埋判定点）、Phase 6 的 prompt 正文撰写。
当前工作目录就是工作区根目录，`drafts/brief.md` 与 `drafts/index.md` 都在 `drafts/` 下，
自己读它们，不要向我索要。

你不负责，也不要尝试执行：

- Phase 1 的容器实测。本次运行是只读模式，起不了容器，实测已代为完成，结论见下方
  「环境事实」，直接按它约束题目设计。
- Phase 5 的环境落地。不要执行 git、gh、docker 任何命令，不要 clone、不要建仓库、
  不要推分支。仓库、基线快照与 A / B 分支由调用方在你给出结果之后落地。
- Phase 6 的写盘与 Phase 7 的剪贴板。不要创建或修改任何文件，题面与题库索引由调用方
  按 skill 的同一套模板渲染写入。
- 上游 commit 不要给。基线由调用方用 git ls-remote 取上游默认分支当前 HEAD，
  你报不出一个真实存在的 40 位 SHA。

环境事实（Phase 1 的替代，已实测）：
{env_facts}

产出格式：只输出一个 JSON 数组，不要任何前后说明，不要代码块围栏。每道题一个对象，
字段含义如下，取值范围与判定口径全部按 skill：

- source：A 表示基于 GitHub 开源项目切版本（skill 的来源 A），C 表示从零起空项目（来源 C）
- upstream：source 为 A 时给上游仓库 https 地址，必须真实存在、公开、且你确实了解其
  代码结构；source 为 C 时给空串
- repo_name：本题专属仓库名，按 skill Phase 5 的命名要求，同批之间不能重名
- question_type：按 skill 的任务类型取值单选
- difficulty：按 skill 的难度档位与配比单选
- languages：本题实际涉及的主要语言与框架，逗号分隔
- repro_level：按 skill 的环境可复现等级三档单选
- summary：一句话功能点摘要，用于题库索引
- origin_reason：选这个项目与这个切入点的理由，一到三句
- difficulty_basis：这道题归到该难度档的核验依据，写明命中了定义里的哪几条
- verdict_points：你埋的客观判定点，字符串数组
- prompt_body：发给模型的 prompt 正文，严格遵守 prompt-writing.md

判定点只放进 verdict_points，**不要写进 prompt_body**（skill Phase 4.4：判定点不写进
题面，否则复制 prompt 时会把答案一起发给模型）。
"""


def _parse_candidates(text: str) -> list[dict]:
    """从模型输出里取出候选数组。"""
    cleaned = re.sub(r"```(?:json)?", "", text or "").strip()
    decoder = json.JSONDecoder()
    for m in re.finditer(r"\[", cleaned):
        try:
            obj, _ = decoder.raw_decode(cleaned[m.start():], 0)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return [c for c in obj if isinstance(c, dict)]
    raise ValueError("模型没有给出可解析的候选题目数组")


_REPO_NAME_OK = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
# 暴露出题语义的仓库名，红线里明确禁止
_REPO_NAME_BAD = re.compile(r"\b(q\d|task|case|test|demo|exam|quiz|bench|eval)\b|^q\d")


def validate_candidate(c: dict) -> str:
    """候选题目的硬性检查。返回空串表示通过。"""
    name = str(c.get("repo_name") or "").strip()
    if not _REPO_NAME_OK.match(name):
        return f"仓库名 {name!r} 不合法，应为小写字母数字加连字符"
    if _REPO_NAME_BAD.search(name):
        return f"仓库名 {name!r} 暴露了出题语义"
    if str(c.get("difficulty") or "").strip() not in ("困难", "地狱"):
        return f"难度 {c.get('difficulty')!r} 不收，只要困难或地狱"
    if len(str(c.get("prompt_body") or "").strip()) < 200:
        return "prompt 正文太短，撑不起困难档"
    if str(c.get("source") or "").upper() == "A" and not str(c.get("upstream") or "").startswith("https://github.com/"):
        return f"上游地址 {c.get('upstream')!r} 不是 GitHub https 地址"
    return ""


# ---------------- 环境落地（Phase 5，全部确定性） ----------------

async def resolve_upstream_head(upstream: str) -> tuple[str, str]:
    """取上游默认分支的当前 HEAD 当基线。返回 (sha, 错误说明)。"""
    r = await _sh(["git", "ls-remote", "--symref", upstream, "HEAD"], timeout=120)
    if not r.ok:
        return "", f"读不到上游 {upstream}，检查地址是否正确、仓库是否公开"
    sha = ""
    for line in r.out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == "HEAD" and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
            sha = parts[0]
    return (sha, "") if sha else ("", f"{upstream} 没有解析出 HEAD 的 40 位 SHA")


async def land_repo(task_no: str, c: dict, owner: str) -> dict:
    """把一道题的仓库建起来：main 冻结在基线，A、B 从 main 切出。

    第二步的断开上游不能省：clone 会把上游全部分支的对象带下来，`refs/remotes/origin/*`
    留在本地就等于把基线之后的上游提交一起交给模型，Bug 修复题的答案会直接暴露。
    """
    staging = config.CODER_ROOT_MOUNT / STAGING_DIR / task_no
    if staging.exists():
        await asyncio.to_thread(shutil.rmtree, staging)
    staging.parent.mkdir(parents=True, exist_ok=True)

    upstream = str(c.get("upstream") or "").strip()
    sha, err = await resolve_upstream_head(upstream)
    if err:
        return {"ok": False, "message": err}

    r = await _sh(["git", "clone", "--no-tags", upstream, str(staging)], timeout=900)
    if not r.ok:
        return {"ok": False, "message": f"clone 上游失败：{r.err.strip()[:300]}"}
    steps = [
        ["git", "checkout", "-B", MAIN_BRANCH, sha],
        ["git", "remote", "remove", "origin"],
    ]
    for args in steps:
        rr = await _sh(args, cwd=str(staging), timeout=300)
        if not rr.ok:
            return {"ok": False, "message": f"{' '.join(args[:3])} 失败：{rr.err.strip()[:300]}"}

    # 删掉除 main 以外的本地分支，再把不可达对象清干净
    br = await _sh(["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"],
                   cwd=str(staging), timeout=120)
    for name in [b.strip() for b in br.out.splitlines() if b.strip() and b.strip() != MAIN_BRANCH]:
        await _sh(["git", "branch", "-D", name], cwd=str(staging), timeout=120)
    await _sh(["git", "reflog", "expire", "--expire=now", "--all"], cwd=str(staging), timeout=300)
    await _sh(["git", "gc", "--prune=now"], cwd=str(staging), timeout=900)

    repo_name = str(c["repo_name"]).strip()
    rr = await _sh(["gh", "repo", "create", repo_name, "--public", "--source=.",
                    "--remote=origin", "--push"], cwd=str(staging), timeout=900)
    if not rr.ok:
        return {"ok": False, "message": f"建仓库 {repo_name} 失败：{(rr.err or rr.out).strip()[:300]}"}
    for args in (["git", "branch", "A"], ["git", "branch", "B"],
                 ["git", "push", "-u", "origin", "A", "B"]):
        rr = await _sh(args, cwd=str(staging), timeout=600)
        if not rr.ok:
            return {"ok": False, "message": f"{' '.join(args[:3])} 失败：{rr.err.strip()[:300]}"}

    repo_url = f"https://github.com/{owner}/{repo_name}"
    # 分支必须恰好三个，且 main 的 HEAD 就是基线：这两条平台会卡（规则 G2 / G3），
    # 等提交被打回才发现就白跑了两个容器
    probe = await gsb_repo.probe_branches(repo_url)
    if not probe.ok:
        return {"ok": False, "message": f"仓库建好了但分支不合规：{probe.message}"}
    return {"ok": True, "repo_url": repo_url, "snapshot": sha,
            "message": f"{repo_name} 已落地，基线 {sha[:12]}"}


# ---------------- 写题面（Phase 6，固定模板） ----------------

def next_task_no(taken: set[str]) -> str:
    n = 1
    while f"{n:02d}" in taken:
        n += 1
    return f"{n:02d}"


def render_draft(task_no: str, c: dict, repo_url: str, snapshot: str,
                 harness_version: str) -> str:
    upstream = str(c.get("upstream") or "").strip()
    reason = str(c.get("origin_reason") or "").strip()
    if upstream:
        origin_note = f"上游 {upstream} ，选定 commit {snapshot}。选择理由：{reason}"
        base_id = f"{gsb_repo.repo_slug(upstream)}@{snapshot}"
    else:
        origin_note = f"自行设计。{reason}"
        base_id = "自行设计"
    return DRAFT_TEMPLATE.format(
        task_no=task_no, repo_url=repo_url, coder_root=config.CODER_ROOT_HOST,
        origin_note=origin_note, base_id=base_id,
        question_type=str(c.get("question_type") or "").strip(),
        difficulty=str(c.get("difficulty") or "").strip(),
        languages=str(c.get("languages") or "").strip(),
        harness_version=harness_version or "待回填",
        repro_level=str(c.get("repro_level") or "").strip(),
        snapshot=snapshot,
        prompt_body=str(c.get("prompt_body") or "").strip(),
    )


def append_index(task_no: str, c: dict, base_id: str, snapshot: str) -> None:
    """题库索引。文件不在就连表头一起写。"""
    path = config.CODER_ROOT_MOUNT / config.PROMPTS_ARCHIVE_DIR / INDEX_FILE
    header = ("| 题号 | repo | 基底 | 任务类型 | 难度 | 功能点摘要 | 快照 SHA | 题面归档 |\n"
              "|---|---|---|---|---|---|---|---|\n")
    row = (f"| {task_no} | {c.get('repo_name', '')} | {base_id} | {c.get('question_type', '')} "
           f"| {c.get('difficulty', '')} | {c.get('summary', '')} | {snapshot} "
           f"| {config.PROMPTS_ARCHIVE_DIR}/{task_no}.md |\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(header + row, encoding="utf-8")
        return
    text = path.read_text(encoding="utf-8")
    path.write_text(text.rstrip("\n") + "\n" + row, encoding="utf-8")


# ---------------- 编排 ----------------

def start(count: int, note: str = "") -> dict:
    """建一条设计记录并后台执行。同一时间只允许一条在跑（出题会改工作区）。"""
    if running:
        return {"ok": False, "error": "已有出题任务在跑，等它结束再发起"}
    count = max(1, min(20, int(count)))
    # 先把模型名取出来。settings_store 每次取值都要开新会话，写在下面的 with session()
    # 里就是在已有事务中再开一条连接，SQLite 在 bind mount 上会抛 disk I/O error。
    model = settings_store.get("design.model") or settings_store.get("cursor.model")
    with session() as db:
        r = DesignRun(count=count, note=note.strip(), status=DESIGN_RUNNING,
                      model=model, started_at=utc_now())
        db.add(r)
        db.flush()
        run_id = r.id
    task = asyncio.create_task(run_design(run_id), name=f"design-{run_id}")
    running[run_id] = task
    task.add_done_callback(lambda f: running.pop(run_id, None))
    _publish(run_id)
    return {"ok": True, "id": run_id}


def cancel(run_id: int) -> dict:
    task = running.get(run_id)
    if task is None:
        return {"ok": False, "error": "该出题任务不在运行中"}
    task.cancel()
    _set(run_id, status=DESIGN_CANCELLED, finished_at=utc_now(), error="人工取消")
    return {"ok": True}


async def _gh_owner() -> str:
    r = await _sh(["gh", "api", "user", "--jq", ".login"], timeout=120)
    return r.out.strip() if r.ok else ""


async def run_design(run_id: int) -> None:
    with session() as db:
        r = db.get(DesignRun, run_id)
        if r is None:
            return
        count, note, model = r.count, r.note, r.model
    try:
        if not shutil.which("gh"):
            raise RuntimeError("后端镜像里没有 gh，出题无法建仓库")
        if not settings_store.get("gh.token"):
            raise RuntimeError("未配置 GitHub Token")
        brief_path = config.CODER_ROOT_MOUNT / config.BRIEF_FILE
        if not brief_path.exists():
            raise RuntimeError(f"工作区里没有 {config.BRIEF_FILE}，定不了本期口径")
        owner = await _gh_owner()
        if not owner:
            raise RuntimeError("gh 取不到当前用户，检查 GitHub Token 权限")

        # skill 是出题规则的唯一来源，接不上就必须停：CLI 找不到 skill 时不会报错，
        # 只会把 /solo-prompt 当普通文本，模型照字面猜一套规则出题，事后无从分辨。
        linked, skill_msg = llm.ensure_skills_linked()
        if not linked:
            raise RuntimeError(skill_msg)

        image = settings_store.get("cc.image")
        _append_log(run_id, "实测容器能力（代 skill 的 Phase 1）")
        caps = await dockerx.image_capabilities(image)
        harness_version = await dockerx.claude_version(image)
        if not caps.get("ok"):
            _append_log(run_id, f"容器能力实测失败 · {caps.get('error', '')[:200]}")

        # 跨设备查重池：先拉最新，再把全池投影成题库索引。skill 的 Phase 3 读那个索引
        # 做功能点查重与配额统计，于是另一台设备出过的题自动进入设计阶段的语义查重。
        pool_ready, pool_why = pool.available()
        if pool_ready:
            synced = await pool.sync()
            _append_log(run_id, f"查重池 · {synced['message']}")
            pool_ready = synced["ok"]
            if pool_ready:
                _append_log(run_id, f"查重池 · {pool.write_index()['message']}")
        else:
            _append_log(run_id, f"查重池未参与 · {pool_why}")

        _append_log(run_id, f"调 /solo-prompt 设计 {count} 道题（规则取自 {skill_msg}）")
        planned = await llm.ask(
            _skill_prompt(count, note, _env_facts(caps, harness_version)),
            model=model, purpose=f"design-{run_id}",
            # 工作目录必须是工作区：skill 要自己读 drafts/brief.md 与 drafts/index.md
            cwd=config.CODER_ROOT_MOUNT,
            timeout_s=max(600, settings_store.get_int("design.timeout_minutes", 90) * 60))
        candidates = _parse_candidates(planned.text)
        _append_log(run_id, f"拿到 {len(candidates)} 道候选")
        taken = {p.stem for p in prompt_bank.archive_files()}
        written: list[Path] = []
        failures: list[str] = []
        designed: list[dict] = []
        pooled: list[pool.Entry] = []

        # 字面查重兜底。设计阶段那层是模型读索引判功能点，它会漏；这一层是确定性的，
        # 拦的是「同一道题换了措辞」以及模型在同一批里自己撞车。放在落地之前：
        # 一旦 land_repo 跑过，GitHub 上就多了一个建完又用不上的仓库。
        dup = pool.find_duplicates(
            [{"key": str(i), "user_prompt": c.get("prompt_body", ""),
              "summary": c.get("summary", "")} for i, c in enumerate(candidates[:count])]
        ) if pool_ready else {}

        for idx, c in enumerate(candidates[:count]):
            why = validate_candidate(c)
            if why:
                failures.append(f"{c.get('repo_name', '?')}：{why}")
                _append_log(run_id, f"候选被拒 · {failures[-1]}")
                continue
            if hit := dup.get(str(idx)):
                failures.append(f"{c.get('repo_name', '?')}：{hit['reason']}")
                _append_log(run_id, f"候选查重命中 · {failures[-1]}")
                continue
            task_no = next_task_no(taken)
            _append_log(run_id, f"题 {task_no} · 落地仓库 {c.get('repo_name')}")
            landed = await land_repo(task_no, c, owner)
            if not landed["ok"]:
                failures.append(f"{task_no}：{landed['message']}")
                _append_log(run_id, f"题 {task_no} 落地失败 · {landed['message']}")
                continue
            taken.add(task_no)
            text = render_draft(task_no, c, landed["repo_url"], landed["snapshot"], harness_version)
            path = config.CODER_ROOT_MOUNT / config.PROMPTS_ARCHIVE_DIR / f"{task_no}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            base_id = (f"{gsb_repo.repo_slug(c.get('upstream', ''))}@{landed['snapshot']}"
                       if c.get("upstream") else "自行设计")
            append_index(task_no, c, base_id, landed["snapshot"])
            written.append(path)
            _append_log(run_id, f"题 {task_no} 已写入 · {landed['message']}")
            # 判定点按 skill Phase 4.4 不能进题面，但必须报告给人，否则验收时无从定位
            _append_log(run_id, f"题 {task_no} · 难度 {c.get('difficulty', '?')}"
                                f"：{str(c.get('difficulty_basis') or '未给依据')[:300]}")
            for i, point in enumerate(c.get("verdict_points") or [], 1):
                _append_log(run_id, f"题 {task_no} · 判定点 {i}：{str(point)[:300]}")
            designed.append({"task_no": task_no, "difficulty": c.get("difficulty", ""),
                             "difficulty_basis": c.get("difficulty_basis", ""),
                             "verdict_points": c.get("verdict_points") or []})
            pooled.append(pool.Entry(
                task_no=task_no, device=pool.device(), repo_name=str(c.get("repo_name") or ""),
                repo_id=f"{owner}/{c.get('repo_name')}", base_id=base_id,
                question_type=str(c.get("question_type") or ""),
                difficulty=str(c.get("difficulty") or ""),
                summary=str(c.get("summary") or ""), snapshot=landed["snapshot"],
                user_prompt=str(c.get("prompt_body") or "").strip(),
            ))

        # 推池：让另一台设备下次出题时能查到这一批。放在导入题库之前，
        # 因为查重失败也不该影响已经落地的题，而池落后一批就等于那边会重出。
        if pool_ready and pooled:
            res = await pool.add(pooled)
            _append_log(run_id, f"查重池 · {res['message']}")

        stats = {"planned": len(candidates), "landed": len(written),
                 "new_files": [p.name for p in written], "failures": failures,
                 "difficulty": dict(Counter(d["difficulty"] for d in designed)),
                 "designed": designed, "pooled": len(pooled)}
        if not written:
            raise RuntimeError("没有一道题落地成功：" + "；".join(failures[:5]))

        imported = prompt_bank.import_tasks(sources=written, origin=ORIGIN_DESIGNED,
                                            design_run_id=run_id)
        stats.update({"parsed": imported["parsed"], "imported": len(imported["added"]),
                      "task_nos": imported["added"]})
        _set(run_id, status=DESIGN_DEDUP, stats_json=json.dumps(stats, ensure_ascii=False),
             task_ids_json=json.dumps(imported["added_ids"]))

        if settings_store.get_bool("design.auto_dedup", True) and imported["added_ids"]:
            _append_log(run_id, "查重（规则 A + C）")
            passed, discarded, err_msg = await dedup_tasks(imported["added_ids"])
            stats.update({"passed": passed, "discarded": discarded, "dedup_error": err_msg})
        _set(run_id, status=DESIGN_DONE, finished_at=utc_now(),
             stats_json=json.dumps(stats, ensure_ascii=False))
        _append_log(run_id, f"完成 · 落地 {len(written)} 道")
    except asyncio.CancelledError:
        _set(run_id, status=DESIGN_CANCELLED, finished_at=utc_now(), error="人工取消")
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("出题失败 run=%s", run_id)
        _set(run_id, status=DESIGN_FAILED, finished_at=utc_now(), error=str(exc)[:2000])
    finally:
        bus.publish("tasks", {"type": "tasks"})


# ---------------- 查重 ----------------

async def dedup_tasks(task_ids: list[int]) -> tuple[int, int, str]:
    """对一批题跑规则 A+C。返回 (通过数, 废弃数, 错误说明)。"""
    with session() as db:
        rows = [db.get(Task, tid) for tid in task_ids]
        items = [
            {
                "key": str(t.id),
                "user_prompt": t.user_prompt,
                "repo_id": qa_bridge.repo_id_of(t.env_snapshot),
                "session_id": "",
            }
            for t in rows if t is not None
        ]
    if not items:
        return 0, 0, "没有可查重的题"
    r = await qa_bridge.dedup(items)
    if not r.get("ok"):
        # 查不成不能默认放行，题留在题库里但标注出来，人工决定
        for tid in task_ids:
            _mark(tid, {"ok": False, "error": r.get("error", "")}, discard=False)
        return 0, 0, r.get("error", "查重未完成")

    passed = discarded = 0
    for item in r.get("results", []):
        try:
            tid = int(item.get("key"))
        except (TypeError, ValueError):
            continue
        hit = item.get("verdict") == "discard"
        _mark(tid, item, discard=hit)
        discarded += 1 if hit else 0
        passed += 0 if hit else 1
    return passed, discarded, ""


def _mark(task_id: int, result: dict, *, discard: bool) -> None:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        t.dedup = result
        if discard:
            t.discarded_from = t.status if t.status != DISCARDED else AVAILABLE
            t.status = DISCARDED
            t.discarded_at = utc_now()
    bus.publish("tasks", {"type": "task", "id": task_id})
