"""GSB 对比分析：在两份产物副本上跑 Cursor CLI，产出谁更好与理由。

运行位置是后端进程（宿主侧），与 Claude Code 容器完全隔离，不会进入被评的轨迹。

和原来的五维评分相比，这里评的不是「这一次跑得几分」，而是「同一道题的两次跑哪次更好」。
所以两侧的产物和轨迹必须同时摆在分析模型面前，工作目录设在分析目录而不是某一侧的仓库，
让它自己在 repo-A 和 repo-B 之间来回对照。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import signal
import time
from pathlib import Path

from app import config
from app.db import session
from app.events import bus
from app.models import (
    ANALYSIS_DONE, ANALYSIS_FAILED, ANALYSIS_RUNNING, ANALYZED, ANALYZING,
    NEEDS_ATTENTION, Task, TaskRun, utc_now,
)
from app.services import settings_store, trace

log = logging.getLogger("gsb_analyzer")

# 拷分析沙箱时跳过的目录：跟评审无关，还特别容易在拷贝途中变化
SANDBOX_SKIP = ("node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
                ".cache", "target", ".claude")

# 平台下拉框里的原文。库里存 A/B/Same 这种短值，上传时再换成平台的中文标签，
# 免得平台改文案就得跟着迁移历史数据
VERDICT_LABEL = {"A": "A 更好", "B": "B 更好", "Same": "Same"}
VERDICTS = tuple(VERDICT_LABEL)

# 一眼就是机器写的词。既写进 prompt 让模型别用，也给核验模块拿去查——
# 两处必须是同一份表，否则会出现「prompt 里没禁、核验却拦」的死循环。
BANNED_WORDS = (
    "首先", "其次", "最后", "综上", "总的来说", "总之", "值得注意的是", "此外", "另外",
    "不仅", "而且", "显然", "令人", "堪称", "优雅", "精妙", "丝滑", "赋能", "闭环",
    "亮点", "整体而言", "可以看出", "由此可见", "体现了", "展现了", "表现出色",
    "表现良好", "表现一般", "基本可用", "效果不错", "非常", "极其", "十分", "相当",
)

WRITING_RULES = f"""
理由的写法（reason 与 findings 里的每一条都必须遵守）：
1. 用第一人称「我」，像我自己看完两份轨迹和两份产物之后随手记下来的口语，不要书面腔。
2. 只写看到的现象和位置，位置一律用文件名、函数名、方法名、命令、报错原文来指，例如
   「A 侧 lib/dumper.js 的 writeNode 返回了对象，B 侧还是只返回字符串」。
   禁止写「第 38 步」「第 19、20 步」「步骤 12」这类步数说法，一次都不要出现。
   步号只填进 evidence 字段的 step，理由正文里不写。
3. 禁止表情符号，禁止 markdown（不要列表符号、不要标题、不要加粗、不要反引号），
   禁止比喻、排比、反问、夸张。
4. 禁止使用这些词：{"、".join(BANNED_WORDS)}。
5. 只写模型自身能力造成的差异；环境问题不写进理由。
6. 提到文件只写仓库内的相对路径，例如 lib/rules_inline.mjs。禁止出现任何绝对路径或磁盘
   目录名（以 / 开头的路径、盘符、以及 host、data、workspace、repo、分析、出题、副本、
   sandbox 这类目录名都不许写）。这些理由会原样交付给评审方，写进去等于把我本地的目录
   结构一起交出去。
7. 不许写你自己是怎么核验的：不写有没有装依赖、有没有 node_modules、能不能联网、
   跑不跑得起来，不写「产物副本」「沙箱」「我这边」「我的环境」。命令跑不了就直接依据
   代码和轨迹下结论，不要解释为什么没跑。
8. A 和 B 都要分别写，各自好在哪、差在哪，并说清是产物问题还是过程问题。
   过程问题要写清出在哪个环节、模型具体做了什么、导致了什么后果；
   产物问题要指到具体文件名、报错信息或没实现的需求点。
9. 要体现权衡。两次跑通常各有优劣，写清我在意的是哪几点、基于什么做的判断，
   不要给没来由的结论。
10. 第一句直接写具体的东西：哪个文件、哪个函数、哪条命令、什么结果。不要用总评开头。
11. 选 Same 也要写得一样详细，写清哪些点确实等价、哪些点各有优劣相互抵消。
    一句话的 Same 不合格。
""".strip()

# 这三类差异不反映模型能力，写进理由等于拿环境问题给模型定罪，平台也不认。
# 出现了只往 remark 里记一句，重跑的判断由 watchdog 负责。
EXCLUDED_FACTORS = """
以下三类因素不许纳入判断，也不许写进 reason：
1. 推理时长。两侧的耗时差异可能来自部署与排队，快慢不代表能力。
   要评效率只能看交互轮次和输出篇幅，不能看秒数。
2. 模型没有报错但戛然而止。这受部署与 harness 适配影响，不是模型自己放弃。
3. 网络工程错误，包括网络波动、请求失败、网关超时、连接重置。
如果某一侧出现了上面任何一种情况，只在 remark 字段里写一句说明，不写进 reason，
也不作为谁更好的依据。
""".strip()


def _agent_bin() -> str | None:
    return shutil.which("agent") or shutil.which("cursor-agent")


def _kill_group(proc: asyncio.subprocess.Process) -> None:
    """连 agent 自己起的子进程一起收掉。

    agent 是用 start_new_session 起的，进程组 ID 等于它的 PID。杀整组才能带走它
    用 Bash 工具跑起来的东西，否则那些进程会挂到 init 上继续占 CPU。
    """
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    except OSError:
        log.exception("杀进程组失败，退回只杀 agent 本身")
    try:
        proc.kill()
    except ProcessLookupError:
        pass


def prepare_sandboxes(task_no: str) -> dict[str, Path]:
    """把两侧工作区各拷一份到分析目录，返回 {side: 副本路径}。

    node_modules 之类的目录既跟评审无关又特别容易踩竞态：容器可能还在写，
    copytree 走到一半源文件就没了，整次分析会因为一个 .eslintrc 失败。直接跳过。
    """
    out: dict[str, Path] = {}
    for side in config.SIDES:
        paths = config.TaskPaths(task_no, side)
        paths.analysis.mkdir(parents=True, exist_ok=True)
        repo = paths.analysis_repo
        if repo.exists():
            shutil.rmtree(repo)
        try:
            shutil.copytree(paths.workspace, repo, symlinks=True,
                            ignore=shutil.ignore_patterns(*SANDBOX_SKIP))
        except shutil.Error as exc:
            bad = exc.args[0] if exc.args else []
            log.warning("拷 %s 侧沙箱有 %d 个文件没拷过来，继续分析；例如 %s",
                        side, len(bad), str(bad[:2])[:300])
        out[side] = repo
    return out


def build_prompt(task: Task, runs: dict[str, TaskRun], repos: dict[str, Path]) -> str:
    """组对比 prompt。两侧的材料对称摆开，不给任何一侧多余的上下文。

    A 和 B 是同一个模型、同一份配置跑两次，差异只来自随机性。所以不能透露哪侧是
    「原来的」「新的」，也不能只描述一侧的判定结果——分析模型会顺着暗示去找理由。
    """
    def side_block(side: str) -> str:
        run = runs[side]
        paths = config.TaskPaths(task.task_no, side)
        return (
            f"{side} 侧：\n"
            f"  产物副本目录：{repos[side].name}\n"
            f"  轨迹步骤索引：{paths.trace_index}\n"
            f"  原始轨迹 jsonl（要看细节时再读，可能很大）：{run.trace_file or '（无）'}\n"
            f"  结束状态：{run.status}   交互轮次：{(run.verdict.get('protocol') or {}).get('num_turns')}\n"
            f"  改动文件数：{(run.verdict.get('artifact') or {}).get('changed_files')}\n"
            f"  git diff --stat：\n{(run.git_diff_stat or '（空）')[:1500]}\n"
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
当前工作目录下有 {repos['A'].name} 和 {repos['B'].name} 两个产物副本，都可以随意改动。
优先靠读代码核验需求是否真的实现。装依赖、跑测试、跑构建这些能跑就跑，跑不起来就完全
依据代码与轨迹判断，不要把「我这边跑不起来」写进任何字段。引用文件一律用相对各自副本根
目录的路径，不要带副本目录名。

{side_block('A')}
{side_block('B')}

轨迹索引的 steps[] 里每一步有 step 序号、kind（tool 或 text）、tool 名、summary（命令或
文件或说明）、files、result（工具返回摘要）、is_error。step 序号只填进 evidence 字段，
理由正文里不要提步数。

【工作步骤】
1. 先读 prompt，把需求拆成可核验的功能点与约束清单。
2. 分别读两侧的轨迹索引，理解各自做了什么、哪里出错、哪里重复。
3. 在两个副本里逐条核验功能点与约束：读代码，能跑就跑测试或构建。
4. 逐项对比，判断哪一侧更好，或者确实等价。
5. 另外分别给出两侧产物的启动方式，要让人照着就能把项目跑起来录屏。
   跑不起来就在 note 里写清卡在哪。

【不许纳入判断的因素】
{EXCLUDED_FACTORS}

【写法要求】
{WRITING_RULES}

【输出格式】
只输出一个 JSON 对象，不要任何前后说明，不要代码块围栏。结构如下（字段名必须完全一致）：
{{
  "verdict": "A" 或 "B" 或 "Same",
  "reason": "对比理由正文，至少 200 字，A 和 B 都要写到",
  "a_findings": {{"good": ["…"], "bad": ["…"]}},
  "b_findings": {{"good": ["…"], "bad": ["…"]}},
  "a_startup": {{"steps": ["…"], "commands": ["…"], "note": "跑不起来时写原因，否则空串"}},
  "b_startup": {{"steps": ["…"], "commands": ["…"], "note": ""}},
  "evidence": [{{"side": "A", "step": 12, "file": "src/x.ts", "quote": "轨迹或产物里的原文片段"}}],
  "remark": "被排除的那三类情况如果出现就写在这里，否则空串"
}}
evidence 里的 side 必须是 A 或 B，step 必须是那一侧索引里真实存在的序号，
file 必须是那一侧出现过的路径，quote 必须是原文片段（可截断）。
"""


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
    """从 agent 最终文本里提取 JSON：容忍前置说明、代码围栏、以及结尾少括号。"""
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

    模型偶尔不听话，把产物副本的绝对路径写进理由，而理由会原样交付给评审方，
    等于把本机目录结构一并交出去。

    只有产物副本这几个前缀能剥成相对路径（剥完正好是仓库内路径），别的绝对路径
    整条压掉：末段像文件就留文件名，像目录就换成一句话，不给任何目录名留出口。
    """
    if not text:
        return text
    # /workspace 是容器里的仓库根，和产物副本一样剥成相对路径
    roots = [str(p).rstrip("/") for p in (repos or {}).values()]
    roots.append("/workspace")
    # 长的先剥：repo-A 的父目录也在列表里时，先剥短的会留下一截 repo-A/ 前缀
    for root in sorted(roots, key=len, reverse=True):
        if root and root != "/":
            text = text.replace(root + "/", "").replace(root, _HERE)

    def squash(m: re.Match) -> str:
        parts = [p for p in m.group(0).split("/") if p]
        return parts[-1] if parts and "." in parts[-1] else _HERE

    return _ABS_PATH.sub(squash, text)


# 「第 38 步」「第 19、20 步」「第 48 到 51 步」「步骤 12」。位置该用文件名和函数名来指，
# 步号只属于 evidence 字段；连着的「在」「于」一起吃掉，否则会剩下「它在追到报错」这种断句。
_STEP_REF = re.compile(
    r"[在于]?\s*第\s*\d+\s*(?:[、,，和及]\s*\d+\s*|(?:到|至|-|~)\s*\d+\s*)*[步轮]\s*(?:里|中|上|时|的时候)?"
    r"|[在于]?\s*步骤\s*\d+(?:\s*[、,，和及到至-]\s*\d+)*\s*(?:里|中|上|时|的时候)?"
)
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([，。、；：）])")


def strip_steps(text: str) -> str:
    """去掉理由里的步数说法。模型偶尔还是会写，留着读起来就是机器在报行号。"""
    if not text:
        return text
    out = _STEP_REF.sub("", text)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = _SPACE_BEFORE_PUNCT.sub(r"\1", out)
    out = re.sub(r"([，。、；])\s*\1+", r"\1", out)
    return out.strip(" ，、")


# 行首的标题井号与列表符号、成对的加粗与反引号。平台的理由框是纯文本，
# markdown 记号在那里不渲染，原样显示出来一眼就是机器抄的模板。
_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
_MD_BULLET = re.compile(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+", re.M)
_MD_BOLD = re.compile(r"\*{1,3}([^*\n]+?)\*{1,3}")
_MD_CODE = re.compile(r"`{1,3}([^`\n]+?)`{1,3}")


def strip_markdown(text: str) -> str:
    """扒掉 markdown 记号，保留文字本身。"""
    if not text:
        return text
    out = _MD_HEADING.sub("", text)
    out = _MD_BULLET.sub("", out)
    out = _MD_BOLD.sub(r"\1", out)
    out = _MD_CODE.sub(r"\1", out)
    out = re.sub(r"^\s*>\s*", "", out, flags=re.M)
    return out.strip()


def _clean(value, repos: dict[str, Path] | None = None) -> str:
    return strip_steps(strip_markdown(strip_paths(str(value or "").strip(), repos)))


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
            # 命令里的路径不清洗：清洗会把命令改坏，人照着敲就跑不起来
            "commands": [str(c).strip() for c in (d.get("commands") or [])
                         if isinstance(c, str) and c.strip()][:20],
            "note": _clean(d.get("note"), repos)}


def normalize(obj: dict, repos: dict[str, Path] | None = None) -> dict:
    """把 agent 的原始输出洗成可入库的结论。

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
             "step": e.get("step"),
             "file": _clean(e.get("file"), repos),
             "quote": _clean(e.get("quote"), repos)}
            for e in (obj.get("evidence") or []) if isinstance(e, dict)
        ][:24],
        "remark": _clean(obj.get("remark"), repos),
    }


def _load_trace_index(task_no: str, side: str) -> dict:
    paths = config.TaskPaths(task_no, side)
    if paths.trace_index.exists():
        try:
            return json.loads(paths.trace_index.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    tf = trace.find_trace_file(paths.traces)
    if tf:
        summary = trace.parse_trace(tf)
        paths.analysis.mkdir(parents=True, exist_ok=True)
        trace.write_index(summary, paths.trace_index)
        return summary
    return {}


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
    bus.publish("tasks", {"type": "task", "id": task_id})

    started = time.time()
    analysis_dir = config.TaskPaths(task_no).analysis
    try:
        agent = _agent_bin()
        if not agent:
            raise RuntimeError("未找到 Cursor CLI（agent），请检查后端镜像")
        api_key = settings_store.get("cursor.api_key")
        if not api_key:
            raise RuntimeError("未配置 Cursor API Key")
        model = settings_store.get("cursor.model") or "claude-opus-5-thinking-high"
        timeout_s = max(120, settings_store.get_int("cursor.timeout_minutes", 40) * 60)

        for side in config.SIDES:
            _load_trace_index(task_no, side)
        repos = await asyncio.to_thread(prepare_sandboxes, task_no)
        with session() as db:
            t = db.get(Task, task_id)
            assert t is not None
            runs = {r.side: r for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()}
            prompt_text = build_prompt(t, runs, repos)
        prompt_path = analysis_dir / "gsb_prompt.md"
        prompt_path.write_text(prompt_text, encoding="utf-8")

        env = dict(os.environ)
        env["CURSOR_API_KEY"] = api_key
        env.pop("CURSOR_MODEL", None)
        instruction = (f"请先用读取工具完整读取 {prompt_path} 这个文件，然后严格按其中的步骤与输出格式完成任务。"
                       f"最终回复只包含一个 JSON 对象。")
        # 工作目录是分析目录而不是某一侧的副本：对比要在两个副本之间来回读，
        # 把 workspace 定在其中一侧会让另一侧变成「外面的目录」，读起来处处受限
        cmd = [agent, "-p", "--force", "--trust", "--model", model, "--output-format", "json",
               "--workspace", str(analysis_dir), instruction]
        # 自己一个进程组：agent 带 --force --trust，会拿 Bash 工具跑测试之类的东西。
        # 只 kill agent 的话那些子进程会挂到 init 上继续烧 CPU，所以超时要杀整组。
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(analysis_dir), env=env, start_new_session=True,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            _kill_group(proc)
            raise RuntimeError(f"GSB 分析超过 {timeout_s // 60} 分钟未完成")
        stdout = out.decode("utf-8", "replace")
        stderr = err.decode("utf-8", "replace")
        (analysis_dir / "agent_stdout.json").write_text(stdout, encoding="utf-8")
        if stderr.strip():
            (analysis_dir / "agent_stderr.log").write_text(stderr, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"agent 退出码 {proc.returncode}: {(stderr or stdout).strip()[:600]}")

        # --output-format json：单个对象，result 为最终文本
        result_text = stdout
        agent_session, usage = "", {}
        try:
            wrapper = json.loads(stdout.strip().splitlines()[-1])
            if isinstance(wrapper, dict) and "result" in wrapper:
                if wrapper.get("is_error"):
                    raise RuntimeError(f"agent 返回错误：{str(wrapper.get('result'))[:600]}")
                result_text = str(wrapper.get("result") or "")
                agent_session = wrapper.get("session_id", "")
                usage = wrapper.get("usage") or {}
        except (json.JSONDecodeError, IndexError):
            pass
        parsed = extract_json(result_text)
        gsb = normalize(parsed, repos)
        if not gsb["verdict"]:
            raise RuntimeError(f"分析没给出可识别的结论，原始值：{str(parsed.get('verdict'))[:80]}")

        with session() as db:
            t = db.get(Task, task_id)
            assert t is not None
            t.analysis = {
                "model": model,
                "agent_session": agent_session,
                "usage": usage,
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


async def probe_models() -> list[str]:
    """API Key 模式下 `agent models` 为空，只能从非法模型名的报错里解析列表。"""
    agent = _agent_bin()
    api_key = settings_store.get("cursor.api_key")
    if not agent or not api_key:
        return []
    env = dict(os.environ, CURSOR_API_KEY=api_key)
    for _ in range(3):
        proc = await asyncio.create_subprocess_exec(
            agent, "-p", "--trust", "--output-format", "json", "--model", "__probe__", "x",
            env=env, stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd="/tmp",
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=60)
        except asyncio.TimeoutError:
            proc.kill()
            continue
        text = (out + err).decode("utf-8", "replace")
        m = re.search(r"Available models:\s*(.+)", text)
        if m and m.group(1).strip():
            return [s.strip() for s in m.group(1).split(",") if s.strip()]
        await asyncio.sleep(2)
    return []


async def probe_ping() -> dict:
    agent = _agent_bin()
    api_key = settings_store.get("cursor.api_key")
    model = settings_store.get("cursor.model")
    if not agent:
        return {"ok": False, "message": "后端未安装 Cursor CLI"}
    if not api_key:
        return {"ok": False, "message": "未配置 Cursor API Key"}
    env = dict(os.environ, CURSOR_API_KEY=api_key)
    started = time.time()
    proc = await asyncio.create_subprocess_exec(
        agent, "-p", "--trust", "--output-format", "json", "--model", model,
        "Reply with exactly the single word: pong",
        env=env, stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd="/tmp",
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=120)
    except asyncio.TimeoutError:
        proc.kill()
        return {"ok": False, "message": "120 秒无响应"}
    text = out.decode("utf-8", "replace")
    try:
        obj = json.loads(text.strip().splitlines()[-1])
        ok = not obj.get("is_error") and "pong" in str(obj.get("result", "")).lower()
        return {"ok": ok, "message": f"{model} · {round(time.time() - started, 1)}s · {str(obj.get('result'))[:80]}"}
    except (json.JSONDecodeError, IndexError):
        return {"ok": False, "message": (err.decode('utf-8', 'replace') or text).strip()[:300]}


STATIC_MODELS = [
    "claude-opus-5-thinking-high", "claude-opus-5-thinking-xhigh", "claude-opus-5-thinking-max",
    "claude-opus-5-thinking-medium", "claude-opus-5-thinking-low",
    "claude-opus-5-high", "claude-opus-5-medium", "claude-opus-5-low",
    "claude-sonnet-5-thinking-high", "auto",
]
