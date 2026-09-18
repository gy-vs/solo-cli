"""GSB 对比分析：在本地把两侧材料摆齐，问一次模型，拿回谁更好与理由。

原先这里是放一个 agent 进两份产物副本里自己漫游：拷仓库、装依赖、跑测试、来回读代码，
一次四十到九十分钟，失败原因散在几百次工具调用里，重试等于再赌一小时。现在换成确定性
采集：git 负责给出产物差异，轨迹索引负责给出过程，两样都是现成的、可复现的，拼进一个
prompt 问一次就够。副作用也一并没了——不再拷几百兆的副本，不再在副本里装依赖。

材料要对称。A 和 B 是同一个模型、同一份配置、同一个起点跑两次，差异只来自随机性，
所以两侧给的材料种类、顺序、截断口径必须一模一样，也不能透露哪侧是「先跑的」——
一旦有暗示，模型会顺着暗示去找理由。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path

from app import config
from app.db import session
from app.events import bus
from app.models import (
    ANALYSIS_DONE, ANALYSIS_FAILED, ANALYSIS_RUNNING, ANALYZED, ANALYZING,
    NEEDS_ATTENTION, Task, TaskRun, utc_now,
)
from app.services import dockerx, gsb_repo, gsb_rules, llm, trace

log = logging.getLogger("gsb_analyzer")

# 平台下拉框里的原文。库里存 A/B/Same 这种短值，上传时再换成平台的中文标签，
# 免得平台改文案就得跟着迁移历史数据
VERDICT_LABEL = {"A": "A 更好", "B": "B 更好", "Same": "Same"}
VERDICTS = tuple(VERDICT_LABEL)

# 单侧材料的字符预算。补丁最占地方，但它也是判断产物好坏的唯一依据，所以给得最宽；
# 超了就按文件截断并说明，而不是整段砍掉——半截补丁比没有补丁更容易让人误判。
DIFF_BUDGET = 60000
STEP_LIMIT = 220
STEP_TEXT_LIMIT = 160

# 这三类差异不反映模型能力，写进理由等于拿环境问题给模型定罪，平台也不认。
EXCLUDED_FACTORS = """
以下三类因素不许纳入判断，也不许写进 reason：
1. 推理时长。两侧的耗时差异可能来自部署与排队，快慢不代表能力。
2. 模型没有报错但戛然而止。这受部署与 harness 适配影响，不是模型自己放弃。
3. 网络工程错误，包括网络波动、请求失败、网关超时、连接重置、限流。
某一侧出现上面任何一种情况，只在 remark 字段里写一句说明，不写进 reason，
也不作为谁更好的依据。
""".strip()


# ---------------- 材料采集 ----------------

async def _git(ws: Path, *args: str, timeout: float = 120) -> str:
    r = await dockerx.run(["git", "-C", str(ws), *args], timeout=timeout)
    return r.out if r.ok else ""


def _truncate_patch(patch: str, budget: int = DIFF_BUDGET) -> tuple[str, bool]:
    """按文件截断补丁。

    直接切字符会把最后一个文件劈成半截，模型读到残缺的 hunk 会当成代码本身有问题。
    按 `diff --git` 分块，装得下就整块装，装不下就停在上一块末尾并说明还剩几个文件。
    """
    if len(patch) <= budget:
        return patch, False
    blocks = re.split(r"(?m)^(?=diff --git )", patch)
    out: list[str] = []
    used = 0
    for block in blocks:
        if used + len(block) > budget:
            break
        out.append(block)
        used += len(block)
    rest = len(blocks) - len(out)
    tail = f"\n（补丁过长，这里只给出前 {len(out)} 个文件，另有 {rest} 个文件未展开）\n"
    return "".join(out) + tail, True


async def collect_side(task_no: str, side: str, run: TaskRun, snapshot: str) -> dict:
    """把一侧的产物与过程材料取齐。全部来自 git 与轨迹索引，不跑任何模型。"""
    ws = config.TaskPaths(task_no, side).workspace
    material: dict = {"side": side, "status": run.status,
                      "num_turns": (run.verdict.get("protocol") or {}).get("num_turns")}

    if (ws / ".git").exists():
        head = (await _git(ws, "rev-parse", "HEAD", timeout=30)).strip()
        # 产物已经提交并推上分支时比 snapshot..HEAD；还没提交就比工作区
        base = snapshot if (snapshot and head and head.lower() != snapshot.lower()) else ""
        rng = [f"{base}..HEAD"] if base else []
        material["diff_stat"] = (await _git(ws, "diff", "--stat", *rng)).strip()
        material["files"] = [f for f in (await _git(ws, "diff", "--name-status", *rng)).splitlines() if f.strip()]
        patch, cut = _truncate_patch(await _git(ws, "diff", *rng, "--", "."))
        material["patch"] = patch
        material["patch_truncated"] = cut
        if not base:
            # 未提交时未跟踪的新文件不在 diff 里，单独列出来，否则新增的实现整份看不到
            untracked = [f for f in (await _git(ws, "ls-files", "--others",
                                                "--exclude-standard")).splitlines() if f.strip()]
            material["untracked"] = untracked[:50]
    else:
        material["diff_stat"] = ""
        material["files"] = []
        material["patch"] = ""

    index = _load_trace_index(task_no, side)
    material["steps"] = _condense_steps(index)
    material["counts"] = index.get("counts") or {}
    return material


def _condense_steps(index: dict) -> list[str]:
    """把轨迹索引压成一行一步。

    过程的判断依据是「做了什么、哪里错了、有没有绕圈」，所以每步只留工具名、对象和
    是否报错。步号不进这份材料——理由里禁止出现步数说法，材料里摆着它，模型就会照抄。
    """
    steps = list(index.get("steps") or [])
    if len(steps) > STEP_LIMIT:
        # 超限时先保住报错步，剩下的名额再从正常步里等距取，最后按原顺序排回去。
        # 不能「先抽样再截断」：报错如果集中在末尾，截断会把它们整批切掉，
        # 而恰恰是失败过程决定了这一侧好不好。
        keep = {i for i, s in enumerate(steps) if s.get("is_error")}
        if len(keep) > STEP_LIMIT:
            keep = set(sorted(keep)[:STEP_LIMIT])
        room = STEP_LIMIT - len(keep)
        if room > 0:
            plain = [i for i, s in enumerate(steps) if not s.get("is_error")]
            stride = max(1, len(plain) // room)
            keep.update(plain[::stride][:room])
        steps = [s for i, s in enumerate(steps) if i in keep]

    out = []
    for s in steps:
        kind = s.get("tool") or s.get("kind") or "step"
        summary = " ".join(str(s.get("summary") or "").split())[:STEP_TEXT_LIMIT]
        flag = " [报错]" if s.get("is_error") else ""
        out.append(f"{kind}{flag} {summary}".strip())
    return out


def _load_trace_index(task_no: str, side: str) -> dict:
    paths = config.TaskPaths(task_no, side)
    if paths.trace_index.exists():
        try:
            return json.loads(paths.trace_index.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    tf = trace.find_trace_file(paths.traces)
    if tf:
        summary = trace.parse_trace(tf)
        paths.analysis.mkdir(parents=True, exist_ok=True)
        trace.write_index(summary, paths.trace_index)
        return summary
    return {}


# ---------------- prompt ----------------

def build_prompt(task: Task, materials: dict[str, dict]) -> str:
    """组对比 prompt。两侧材料对称摆开，不给任何一侧多余的上下文。"""

    def block(side: str) -> str:
        m = materials.get(side) or {}
        steps = m.get("steps") or []
        step_text = "\n".join(f"  {s}" for s in steps) or "  （没有轨迹）"
        untracked = m.get("untracked") or []
        extra = ("\n未跟踪的新增文件：\n" + "\n".join(f"  {f}" for f in untracked)) if untracked else ""
        return (
            f"=== {side} 侧 ===\n"
            f"结束状态：{m.get('status')}   交互轮次：{m.get('num_turns')}\n"
            f"改动统计：\n{m.get('diff_stat') or '（无改动）'}\n"
            f"改动文件：\n" + ("\n".join(f"  {f}" for f in (m.get('files') or [])) or "  （无）") +
            f"{extra}\n"
            f"过程（按先后顺序，每行一步）：\n{step_text}\n"
            f"代码改动：\n<<<PATCH-{side}\n{m.get('patch') or '（无改动）'}\nPATCH-{side}>>>\n"
        )

    return f"""你是资深工程师，正在对比同一道题的两次自动做题过程与产物，判断哪一次更好。

这两次跑用的是同一个模型、同一份配置、同一个起始快照，差异只来自模型本身的随机性。
两侧没有主次之分，不要假设某一侧是基准。

【任务信息】
题号：{task.task_no}
任务类型：{task.question_type}   难度：{task.difficulty}   语言/框架：{task.languages}

【两侧收到的原始 prompt（完全相同）】
<<<PROMPT
{task.user_prompt}
PROMPT>>>

【两侧的材料】
下面给出的就是全部材料，没有别的地方可查。产物看代码改动，过程看那一行行的步骤记录。
判断需求有没有真的实现，以代码改动为准，不要凭步骤记录里的说法下结论。

{block('A')}
{block('B')}

【工作步骤】
1. 先读原始 prompt，把需求拆成可核验的功能点与约束清单。
2. 对着两侧的代码改动逐条核验，看功能点是不是真的实现了、约束有没有被破坏。
3. 再看两侧的过程，判断各自哪里顺、哪里卡、哪里绕了远路或者反复试错。
4. 逐项对比，给出哪一侧更好，或者确实等价。
5. 另外分别给出两侧产物的启动方式，要让人照着就能把项目跑起来录屏；
   材料不足以给出完整步骤时，在对应的 note 里写清缺什么。

【不许纳入判断的因素】
{EXCLUDED_FACTORS}

【写法要求】
{gsb_rules.WRITING_RULES}

【输出格式】
只输出一个 JSON 对象，不要任何前后说明，不要代码块围栏。结构如下（字段名必须完全一致）：
{{
  "verdict": "A" 或 "B" 或 "Same",
  "reason": "对比理由正文，至少 200 字，A 和 B 都要写到",
  "a_findings": {{"good": ["…"], "bad": ["…"]}},
  "b_findings": {{"good": ["…"], "bad": ["…"]}},
  "a_startup": {{"steps": ["…"], "commands": ["…"], "note": "给不出完整步骤时写原因，否则空串"}},
  "b_startup": {{"steps": ["…"], "commands": ["…"], "note": ""}},
  "evidence": [{{"side": "A", "file": "src/x.ts", "quote": "代码或过程记录里的原文片段"}}],
  "remark": "被排除的那三类情况如果出现就写在这里，否则空串"
}}
evidence 里的 side 必须是 A 或 B，file 必须是那一侧真实出现过的路径，
quote 必须是材料里的原文片段（可截断）。evidence 不要填步号。
"""


# ---------------- 输出清洗 ----------------

def _repair_truncated(text: str) -> str:
    """给被截断的 JSON 补上缺的闭合符号。

    按未闭合的括号栈逆序补，不能先补齐所有 ] 再补所有 }：数组里的对象被截断时
    （…"evidence": [{"side": "B"），顺序补出来是 ]}} ，括号交叉照样解析不了。
    """
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in text:
        if esc:
            esc = False
        elif ch == "\\" and in_str:
            esc = True
        elif ch == '"':
            in_str = not in_str
        elif in_str:
            continue
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack and stack[-1] == ("{" if ch == "}" else "["):
            stack.pop()
    out = text + ('"' if in_str else "")
    # 截断点常落在逗号或键名后面，留着它们补完还是非法的
    out = re.sub(r"[,:]\s*$", "", out.rstrip())
    return out + "".join("}" if ch == "{" else "]" for ch in reversed(stack))


def extract_json(text: str) -> dict:
    """从模型最终文本里提取 JSON：容忍前置说明、代码围栏、以及结尾少括号。"""
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    decoder = json.JSONDecoder()
    last_err: Exception | None = None
    for m in re.finditer(r"\{", text):
        start = m.start()
        for candidate in (text[start:], _repair_truncated(text[start:])):
            try:
                obj, _ = decoder.raw_decode(candidate, 0)
            except json.JSONDecodeError as exc:
                last_err = exc
                continue
            if isinstance(obj, dict) and "verdict" in obj:
                return obj
    raise ValueError(f"输出中没有可解析的 GSB JSON：{last_err}")


_ABS_PATH = re.compile(r"(?<![\w.])/(?:[A-Za-z0-9_.\-\u4e00-\u9fff]+/)+[A-Za-z0-9_.\-\u4e00-\u9fff]*")
_HERE = "仓库根目录"


def strip_paths(text: str, repos: dict[str, Path] | None = None) -> str:
    """把理由里的绝对路径压成仓库内相对路径。

    模型偶尔不听话，把工作区的绝对路径写进理由，而理由会原样交付给评审方，
    等于把本机目录结构一并交出去。

    只有工作区这几个前缀能剥成相对路径（剥完正好是仓库内路径），别的绝对路径
    整条压掉：末段像文件就留文件名，像目录就换成一句话，不给任何目录名留出口。
    """
    if not text:
        return text
    # /workspace 是容器里的仓库根，和本地工作区一样剥成相对路径
    roots = [str(p).rstrip("/") for p in (repos or {}).values()]
    roots.append("/workspace")
    # 长的先剥：父目录也在列表里时，先剥短的会留下一截前缀
    for root in sorted(roots, key=len, reverse=True):
        if root and root != "/":
            text = text.replace(root + "/", "").replace(root, _HERE)

    def squash(m: re.Match) -> str:
        parts = [p for p in m.group(0).split("/") if p]
        return parts[-1] if parts and "." in parts[-1] else _HERE

    return _ABS_PATH.sub(squash, text)


_SPACE_BEFORE_PUNCT = re.compile(r"\s+([，。、；：）])")


def strip_steps(text: str) -> str:
    """去掉理由里的步数说法。

    这是 AI 化评分里权重最高的一类物证，模型偶尔还是会写，留着就是机器在报行号。
    连着的「在」「于」一起吃掉，否则会剩下「它在追到报错」这种断句。
    """
    if not text:
        return text
    out = gsb_rules.STEP_REF.sub("", text)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = _SPACE_BEFORE_PUNCT.sub(r"\1", out)
    out = re.sub(r"([，。、；])\s*\1+", r"\1", out)
    return out.strip(" ，、")


def strip_machine_metrics(text: str) -> str:
    """去掉只有程序数得出来的量：工具调用计数、增删行数、耗时、file:line 的行号。

    行号单独处理：文件名本身是正常引用，要留；钉在后面的 :120-136 才是机器味，
    所以只剥行号，不动文件名。
    """
    if not text:
        return text
    out = gsb_rules.FILE_LINE.sub(lambda m: m.group(0).split(":")[0].split("：")[0], text)
    for pattern in (gsb_rules.TOOL_COUNT, gsb_rules.DIFF_STAT, gsb_rules.DURATION,
                    gsb_rules.TERMINAL_DUMP):
        out = pattern.sub("", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = _SPACE_BEFORE_PUNCT.sub(r"\1", out)
    return re.sub(r"([，。、；])\s*\1+", r"\1", out).strip(" ，、")


def strip_markdown(text: str) -> str:
    """扒掉 markdown 记号与固定分栏，保留文字本身。"""
    if not text:
        return text
    out = gsb_rules.MD_HEADING.sub("", text)
    out = gsb_rules.MD_HR.sub("", out)
    out = gsb_rules.MD_BULLET.sub("", out)
    out = gsb_rules.MD_BOLD.sub(r"\1", out)
    out = gsb_rules.MD_CODE.sub(r"\1", out)
    out = re.sub(r"(?m)^\s*>\s*", "", out)
    out = gsb_rules.EMOJI.sub("", out)
    # 【产物】【过程】这类栏目标签：平台的理由框是纯文本，摆出来就是模板
    out = re.sub(r"【([^】\n]{1,12})】", r"\1", out)
    return out.strip()


def _clean(value, repos: dict[str, Path] | None = None) -> str:
    text = strip_paths(str(value or "").strip(), repos)
    return strip_machine_metrics(strip_steps(strip_markdown(text)))


def _clean_list(items, repos, limit: int = 20) -> list[str]:
    if not isinstance(items, list):
        return []
    return [c for c in (_clean(i, repos) for i in items if isinstance(i, (str, int, float))) if c][:limit]


def _findings(obj, repos) -> dict:
    d = obj if isinstance(obj, dict) else {}
    return {"good": _clean_list(d.get("good"), repos), "bad": _clean_list(d.get("bad"), repos)}


def _startup(obj, repos) -> dict:
    d = obj if isinstance(obj, dict) else {}
    return {"steps": _clean_list(d.get("steps"), repos),
            # 命令里的路径与数字不清洗：清洗会把命令改坏，人照着敲就跑不起来
            "commands": [str(c).strip() for c in (d.get("commands") or [])
                         if isinstance(c, str) and c.strip()][:20],
            "note": _clean(d.get("note"), repos)}


def normalize(obj: dict, repos: dict[str, Path] | None = None) -> dict:
    """把模型的原始输出洗成可入库的结论。

    verdict 认不出来时留空，不猜一个。猜出来的结论会带着「已分析」的样子直接进上传
    环节，比空着更难发现。
    """
    raw = str(obj.get("verdict") or "").strip()
    verdict = ""
    for v in VERDICTS:
        if raw.upper() == v.upper() or raw == VERDICT_LABEL[v]:
            verdict = v
            break
    return {
        "verdict": verdict,
        "reason": _clean(obj.get("reason"), repos),
        "a_findings": _findings(obj.get("a_findings"), repos),
        "b_findings": _findings(obj.get("b_findings"), repos),
        "a_startup": _startup(obj.get("a_startup"), repos),
        "b_startup": _startup(obj.get("b_startup"), repos),
        "evidence": [
            {"side": str(e.get("side") or "").upper()[:1],
             "file": _clean(e.get("file"), repos),
             "quote": _clean(e.get("quote"), repos)}
            for e in (obj.get("evidence") or []) if isinstance(e, dict)
        ][:24],
        "remark": _clean(obj.get("remark"), repos),
    }


# ---------------- 主流程 ----------------

async def analyze_task(task_id: int) -> dict:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "error": "任务不存在"}
        runs = {r.side: r for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()}
        if set(runs) != set(config.SIDES):
            return {"ok": False, "error": f"两侧的运行记录不全，只有 {sorted(runs) or '空'}"}
        t.analysis_status = ANALYSIS_RUNNING
        t.status = ANALYZING
        t.auto_error = ""
        db.flush()
        task_no = t.task_no
        snapshot = gsb_repo.snapshot_sha(t.env_snapshot)
    bus.publish("tasks", {"type": "task", "id": task_id})

    started = time.time()
    analysis_dir = config.TaskPaths(task_no).analysis
    try:
        with session() as db:
            t = db.get(Task, task_id)
            assert t is not None
            runs = {r.side: r for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()}
            materials = {s: await collect_side(task_no, s, runs[s], snapshot) for s in config.SIDES}
            prompt_text = build_prompt(t, materials)

        analysis_dir.mkdir(parents=True, exist_ok=True)
        (analysis_dir / "gsb_prompt.md").write_text(prompt_text, encoding="utf-8")

        result = await llm.ask(prompt_text, purpose=f"GSB {task_no}")
        (analysis_dir / "gsb_raw.txt").write_text(result.text, encoding="utf-8")

        parsed = extract_json(result.text)
        workspaces = {s: config.TaskPaths(task_no, s).workspace for s in config.SIDES}
        gsb = normalize(parsed, workspaces)
        if not gsb["verdict"]:
            raise RuntimeError(f"分析没给出可识别的结论，原始值：{str(parsed.get('verdict'))[:80]}")

        with session() as db:
            t = db.get(Task, task_id)
            assert t is not None
            t.analysis = {
                "model": result.model,
                "agent_session": result.session_id,
                "usage": result.usage,
                "attempts": result.attempts,
                "duration_s": round(time.time() - started),
                "finished_at": utc_now().isoformat(),
                "raw": parsed,
            }
            t.gsb = gsb
            t.analysis_status = ANALYSIS_DONE
            t.status = ANALYZED
            db.flush()

        from app.services import gsb_verifier

        await gsb_verifier.run_verify(task_id)
        bus.publish("tasks", {"type": "task", "id": task_id})
        return {"ok": True, "verdict": gsb["verdict"]}
    except Exception as exc:  # noqa: BLE001
        log.exception("GSB 分析失败 %s", task_no)
        with session() as db:
            t = db.get(Task, task_id)
            if t is not None:
                t.analysis_status = ANALYSIS_FAILED
                t.status = NEEDS_ATTENTION
                t.auto_error = f"GSB 分析失败：{exc}"[:2000]
        bus.publish("tasks", {"type": "task", "id": task_id})
        return {"ok": False, "error": str(exc)}
