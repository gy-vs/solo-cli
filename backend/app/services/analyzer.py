"""Cursor CLI 五维分析：在产物副本上运行 `agent -p`，产出五维分数、第一人称描述与证据索引。

运行位置是后端进程（宿主侧），与 Claude Code 容器完全隔离，不会进入轨迹。
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
    ANALYSIS_DONE, ANALYSIS_FAILED, ANALYSIS_RUNNING, FAILED, FINISHED, INTERRUPTED, REVIEWED,
    TIMEOUT, Task, utc_now,
)
from app.services import dockerx, settings_store, trace, verifier

log = logging.getLogger("analyzer")

# 拷分析沙箱时跳过的目录：跟评审无关，还特别容易在拷贝途中变化
SANDBOX_SKIP = ("node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
                ".cache", "target", ".claude")

RUBRIC = """
五个维度，每个维度 1 到 5 的整数分。锚点：

交付完整性：看需求功能点是否完整实现、代码能不能跑、有没有宣称做了但实际没做的情况。
5 全部明示需求实现且能跑，还补了边界处理，没有虚假成功。4 主要需求全达成、能跑，只有极少细节遗漏。3 核心能跑但有明显 bug 需人工修，或有轻微虚假成功。2 主要需求未达成，代码跑不起来，或较大比例虚假成功。1 完全不可用、答非所问，或满口答应一行代码没写。

指令遵循：看是否严格遵守 prompt 里的所有显式约束（指定库、禁止项、风格、范围）。
5 全部显式与隐式约束都遵守，没有擅自做主。4 核心与绝大多数次要约束遵守，极细微格式偏差。3 遵循核心目标但漏了 1 到 2 个明确的负面约束。2 忽略关键约束（换技术栈、用了禁用库），产物需大规模重构。1 完全无视约束。

任务规划：看是否合理拆解任务、有阶段性状态追踪、遇到歧义是否求证、有没有阶段性总结。只评价计划与状态更新本身，不评价用了什么具体工具。
5 拆解清晰合理，持续更新状态，歧义会求证。4 有合理拆解和总结，偶有状态更新不及时。3 有大方向但子任务不细，总结时有时无，状态追踪明显遗漏。2 上来就盲写，无拆解，几乎无状态追踪。1 毫无步骤概念。

推理能力：看理解需求、定位根因、修复是否准确，是否有幻觉或自相矛盾；思考量与题目难度是否匹配（区分过度思考与思考不足）。
5 深刻理解意图与隐性约束，报错一次定位根因，思考聚焦不绕圈。4 方向正确，较快定位问题，偶有轻微冗余。3 理解主要任务但漏了部分条件，报错需多次尝试，思考偏发散或冗余。2 推理犹豫、选非最优解、猜答案、反复自我怀疑。1 理解完全错误、严重幻觉、思考死循环。

执行能力：看工具调用路径是否少而准，能否从报错恢复；是否重复读同一文件、反复跑同一失败命令、无意义探索、原地打转。
5 调用精准最小化，无重复读取和无效探索，合理批量。4 基本高效，少量冗余读取。3 较明显冗余（多次重复 grep/read、文件间来回横跳），最终完成。2 大量冗余或失败调用，明显低效。1 严重滥用或缺失，该读不读全靠猜，产物完全不可用。
""".strip()

WRITING_RULES = """
描述写法（五个维度的 description 与 other_issues 都必须遵守）：
1. 用第一人称「我」，像我自己看完轨迹和产物后随手记下来的口语，不要书面腔。
2. 只写看到的现象和位置，位置一律用文件名、函数名、方法名、命令、报错原文来指，例如
   「lib/dumper.js 的 writeNode 改成返回 { text, tag }」「npm test 的 core 用例 329 个全过」。
   禁止写「第 38 步」「第 19、20 步」「第 2 轮」「步骤 12」这类步数说法，一次都不要出现。
   步号只填进 evidence 字段的 step，描述正文里不写。
3. 禁止表情符号，禁止 markdown（不要列表符号、不要标题、不要加粗、不要反引号），禁止比喻、排比、反问、夸张。
4. 禁止使用这些词：首先、其次、最后、综上、总的来说、总之、值得注意的是、此外、另外、不仅、而且、显然、令人、堪称、优雅、精妙、丝滑、赋能、闭环、亮点、整体而言、可以看出、由此可见、体现了、展现了、表现出色、表现良好、表现一般、基本可用、效果不错、非常、极其、十分、相当。
5. 每条描述 2 到 6 句，80 到 300 字。分数高的维度也要写具体核对了什么，例如「我把 prompt 里的 N 条约束逐条对了产物，都能对上」，并点出对的是哪几条。
6. 只写模型自身能力造成的问题；网关超时、网络错误这类环境问题不写进描述。
7. 打分要和描述一致：描述里说了有需求没实现，交付完整性就不能给 4 分以上。
8. 提到文件只写仓库内的相对路径，例如 lib/rules_inline.mjs。禁止出现任何绝对路径或磁盘目录名
   （以 / 开头的路径、盘符、以及 host、data、workspace、repo、分析、出题、副本这类目录名都不许写）。
   这些描述会原样交付给评审方，写进去等于把我本地的目录结构一起交出去。
9. 不许写你自己这次是怎么核验的环境状况，这部分不属于对被评模型的评价：
   不写有没有装依赖、有没有 node_modules、有没有某个可执行文件、能不能联网、跑不跑得起来、
   不写「产物副本」「沙箱」「我这边」「我的环境」。
   命令跑不了就直接依据代码和轨迹下结论，不要解释为什么没跑，也不要说结论不受影响。
   verification.commands 只填真正执行成功的命令，没跑就给空数组。
10. 第一句直接写具体的东西：哪个文件、哪个函数、哪条命令、什么结果。
   不要用一句总评或表态开头，下面这些开头一律不许出现，它们一眼就是机器写的：
   「我把需求逐条对了产物。」「我照约束清单一条条核。」「推进顺序我认可。」
   「几个关键判断都做对了。」「调用路径十分紧凑。」「整体完成度不错。」
   正例开头：「lib/dumper.js 的 writeNode 现在返回 { text, tag }，writeBlockSequence 和 writeFlowMapping 也跟着改了。」
11. 只要这个维度不是 5 分，描述里必须同时出现三样东西，缺一样都会被质检打回：
   扣分点发生的具体位置（哪个文件、哪个函数、哪条命令或哪段报错原文）；
   哪里不合适（对这个维度的负面判断，不能只写「核对通过」就收尾）；
   模型具体做了什么、造成了什么客观后果。
   反例：「它把目录列了一遍就结束了」——没写在哪个文件上、也没写导致什么。
   正例：「它用 Glob 把 src 下的文件名列了一遍就去写 README，没有打开 src/parser.py 看实现，
   写出来的模块说明和代码里的函数名对不上，我按 README 的说法找不到对应函数。」
12. 满分维度也不要只写一句「没问题」，要写清核对了哪几条、在哪些文件和命令上看到的。
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


def _prepare_sandbox(paths: config.TaskPaths) -> Path:
    """把工作区拷成分析用的沙箱。

    node_modules 之类的目录既跟评审无关又特别容易踩竞态：容器可能还在写，
    copytree 走到一半源文件就没了，整次分析会因为一个 .eslintrc 失败。直接跳过。
    """
    paths.analysis.mkdir(parents=True, exist_ok=True)
    repo = paths.analysis_repo
    if repo.exists():
        shutil.rmtree(repo)
    try:
        shutil.copytree(paths.workspace, repo, symlinks=True,
                        ignore=shutil.ignore_patterns(*SANDBOX_SKIP))
    except shutil.Error as exc:
        # copytree 把逐个文件的失败收集起来最后一起抛。大目录已经跳过了，剩下的多是
        # 拷贝途中源文件消失，缺几个无关文件不该让整次分析失败。
        bad = exc.args[0] if exc.args else []
        log.warning("拷分析沙箱有 %d 个文件没拷过来，继续分析；例如 %s", len(bad), str(bad[:2])[:300])
    return repo


def _build_prompt(task: Task, trace_index_path: Path, repo: Path, trace_file: str) -> str:
    return f"""你是资深工程师，正在复核一次 Claude Code 自动做题的过程与产物，然后按五个维度打分并写描述。

【任务信息】
题号：{task.task_no}
任务类型：{task.question_type}   难度：{task.difficulty}   语言/框架：{task.languages}

【发给模型的原始 prompt】
<<<PROMPT
{task.user_prompt}
PROMPT>>>

【可用材料】
1. 当前工作目录就是模型完成后的代码，是一份可随意改动的副本。
   优先靠读代码核验需求是否真的实现。装依赖、跑测试、跑构建这些能跑就跑，跑不起来就完全依据代码与轨迹判断，
   不要把「我这边跑不起来」写进任何描述字段。引用文件一律用相对这个目录的路径。
2. 轨迹步骤索引（JSON）：{trace_index_path}
   steps[] 里每一步有 step 序号、kind（tool 或 text）、tool 名、summary（命令/文件/说明）、files、result（工具返回摘要）、is_error。
   step 序号只填进 evidence 字段，描述正文里不要提步数。
3. 原始轨迹 jsonl（需要看细节时再读，可能很大）：{trace_file or '（无）'}

【工作步骤】
1. 先读 prompt，把需求拆成可核验的功能点与约束清单。
2. 读轨迹步骤索引，理解模型做了什么、顺序如何、哪里出错、哪里重复。
3. 在当前目录逐条核验功能点与约束：读代码，能跑就跑测试或构建，记录真正跑成功的命令与结果。
4. 按下面的评分锚点打分，按写法要求写描述，每条描述都要点到具体的文件名或函数名。

【评分锚点】
{RUBRIC}

【写法要求】
{WRITING_RULES}

【输出格式】
只输出一个 JSON 对象，不要任何前后说明，不要代码块围栏。结构如下（字段名必须完全一致）：
{{
  "delivery":    {{"score": 1-5, "description": "…", "evidence": [{{"step": 12, "file": "src/x.ts", "quote": "轨迹里出现过的原话片段"}}]}},
  "instruction": {{"score": 1-5, "description": "…", "evidence": [...]}},
  "planning":    {{"score": 1-5, "description": "…", "evidence": [...]}},
  "reasoning":   {{"score": 1-5, "description": "…", "evidence": [...]}},
  "execution":   {{"score": 1-5, "description": "…", "evidence": [...]}},
  "other_issues": "未被五维覆盖的其他问题，没有就写空字符串",
  "requirement_coverage": [{{"point": "需求点", "status": "done|partial|missing", "evidence": "文件/测试/现象"}}],
  "verification": {{"commands": ["你实际跑过的命令"], "summary": "跑的结果，含通过/失败数"}}
}}
evidence 里的 step 必须是索引里真实存在的序号，file 必须是轨迹里出现过的路径，quote 必须是 summary 或 result 里的原文片段（可截断）。没有合适证据的维度 evidence 给空数组，但描述里仍要写出具体位置。
"""


def _extract_json(text: str) -> dict:
    """从 agent 最终文本里提取 JSON：容忍前置说明、代码围栏、以及结尾少括号。"""
    text = re.sub(r"```(?:json)?", "", text).strip()
    decoder = json.JSONDecoder()
    last_err: Exception | None = None
    for m in re.finditer(r"\{", text):
        start = m.start()
        try:
            obj, _ = decoder.raw_decode(text, start)
            if isinstance(obj, dict) and "delivery" in obj:
                return obj
        except json.JSONDecodeError as exc:
            last_err = exc
            # 结尾截断：补齐缺失的 ] / }
            candidate = text[start:].rstrip()
            for _ in range(4):
                opens = candidate.count("{") - candidate.count("}")
                opens_arr = candidate.count("[") - candidate.count("]")
                if opens <= 0 and opens_arr <= 0:
                    break
                candidate += "]" * max(0, opens_arr) + "}" * max(0, opens)
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict) and "delivery" in obj:
                        return obj
                except json.JSONDecodeError as exc2:
                    last_err = exc2
    raise ValueError(f"输出中没有可解析的五维 JSON：{last_err}")


_ABS_PATH = re.compile(r"(?<![\w.])/(?:[A-Za-z0-9_.\-\u4e00-\u9fff]+/)+[A-Za-z0-9_.\-\u4e00-\u9fff]*")
_HERE = "仓库根目录"


def _strip_paths(text: str, repo: Path | str = "") -> str:
    """把描述里的绝对路径压成仓库内相对路径。

    模型偶尔不听话，把产物副本的绝对路径写进描述，而描述会原样交付给评审方，
    等于把本机目录结构一并交出去。

    只有产物副本这一个前缀能剥成相对路径（剥完正好是仓库内路径），别的绝对路径
    整条压掉：末段像文件就留文件名，像目录就换成一句话，不给任何目录名留出口。
    """
    if not text:
        return text
    # /workspace 是容器里的仓库根，和产物副本一样剥成相对路径
    for root in (str(repo).rstrip("/"), "/workspace"):
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


def _strip_steps(text: str) -> str:
    """去掉描述里的步数说法。模型偶尔还是会写，留着读起来就是机器在报行号。"""
    if not text:
        return text
    out = _STEP_REF.sub("", text)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = _SPACE_BEFORE_PUNCT.sub(r"\1", out)
    out = re.sub(r"([，。、；])\s*\1+", r"\1", out)
    return out.strip(" ，、")


def _normalize(obj: dict, repo: Path | str = "") -> dict:
    out: dict = {"scores": {}, "descs": {}, "evidence": {}, "other_issues": "", "coverage": [], "verification": {}}
    clean = lambda s: _strip_steps(_strip_paths(str(s or "").strip(), repo))  # noqa: E731
    for dim in verifier.DIMS:
        d = obj.get(dim) or {}
        score = d.get("score")
        try:
            score = int(score)
        except (TypeError, ValueError):
            score = None
        out["scores"][dim] = score
        out["descs"][dim] = clean(d.get("description"))
        ev = d.get("evidence") or []
        out["evidence"][dim] = [_clean_dict(e, ("file", "quote"), clean) for e in ev if isinstance(e, dict)][:12]
    out["other_issues"] = clean(obj.get("other_issues"))
    cov = obj.get("requirement_coverage") or []
    out["coverage"] = [_clean_dict(c, ("point", "evidence"), clean) for c in cov if isinstance(c, dict)][:40]
    ver = dict(obj.get("verification") or {})
    if isinstance(ver.get("commands"), list):
        ver["commands"] = [clean(c) for c in ver["commands"] if isinstance(c, str)]
    if isinstance(ver.get("summary"), str):
        ver["summary"] = clean(ver["summary"])
    out["verification"] = ver
    return out


def _clean_dict(d: dict, keys: tuple[str, ...], clean) -> dict:
    out = dict(d)
    for k in keys:
        if isinstance(out.get(k), str):
            out[k] = clean(out[k])
    return out


def _load_trace_index(paths: config.TaskPaths) -> dict:
    idx = paths.analysis / "trace_index.json"
    if idx.exists():
        try:
            return json.loads(idx.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    tf = trace.find_trace_file(paths.traces)
    if tf:
        summary = trace.parse_trace(tf)
        trace.write_index(summary, idx)
        return summary
    return {}


def run_verify(task_id: int) -> dict:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {}
        paths = config.TaskPaths(t.task_no)
        report = verifier.verify(t.review, _load_trace_index(paths))
        t.verify = report
        complete = all(isinstance(t.review.get("scores", {}).get(d), int) and (t.review.get("descs", {}).get(d) or "").strip()
                       for d in verifier.DIMS)
        # 状态只在「运行结束态 ↔ REVIEWED」之间切换；已上传/已完成的不动
        if t.status in (FINISHED, FAILED, TIMEOUT, INTERRUPTED, REVIEWED):
            if complete and report.get("overall") != "block":
                t.status = REVIEWED
            elif t.status == REVIEWED:
                t.status = t.verdict.get("status") or FINISHED
        db.flush()
    bus.publish("tasks", {"type": "task", "id": task_id})
    return report


async def analyze_task(task_id: int) -> dict:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "error": "任务不存在"}
        t.analysis_status = ANALYSIS_RUNNING
        t.error = ""
        db.flush()
        task_no = t.task_no
    bus.publish("tasks", {"type": "task", "id": task_id})

    started = time.time()
    try:
        agent = _agent_bin()
        if not agent:
            raise RuntimeError("未找到 Cursor CLI（agent），请检查后端镜像")
        api_key = settings_store.get("cursor.api_key")
        if not api_key:
            raise RuntimeError("未配置 Cursor API Key")
        model = settings_store.get("cursor.model") or "claude-opus-5-thinking-high"
        timeout_s = max(120, settings_store.get_int("cursor.timeout_minutes", 40) * 60)

        paths = config.TaskPaths(task_no)
        with session() as db:
            t = db.get(Task, task_id)
            assert t is not None
            trace_index = _load_trace_index(paths)
            repo = await asyncio.to_thread(_prepare_sandbox, paths)
            prompt_text = _build_prompt(t, paths.analysis / "trace_index.json", repo, t.trace_file)
        prompt_path = paths.analysis / "analysis_prompt.md"
        prompt_path.write_text(prompt_text, encoding="utf-8")

        env = dict(os.environ)
        env["CURSOR_API_KEY"] = api_key
        env.pop("CURSOR_MODEL", None)
        instruction = (f"请先用读取工具完整读取 {prompt_path} 这个文件，然后严格按其中的步骤与输出格式完成任务。"
                       f"最终回复只包含一个 JSON 对象。")
        cmd = [agent, "-p", "--force", "--trust", "--model", model, "--output-format", "json",
               "--workspace", str(repo), instruction]
        # 自己一个进程组：agent 带 --force --trust，会拿 Bash 工具跑基准测试之类的东西。
        # 真实事故：它写的 benchmark 死循环，占满一核跑了十几分钟，agent 干等它结束；
        # 只 kill agent 的话那个子进程会挂到 init 上继续烧 CPU，所以超时要杀整组。
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(repo), env=env, start_new_session=True,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            _kill_group(proc)
            raise RuntimeError(f"Cursor 分析超过 {timeout_s // 60} 分钟未完成")
        stdout = out.decode("utf-8", "replace")
        stderr = err.decode("utf-8", "replace")
        (paths.analysis / "agent_stdout.json").write_text(stdout, encoding="utf-8")
        if stderr.strip():
            (paths.analysis / "agent_stderr.log").write_text(stderr, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"agent 退出码 {proc.returncode}: {(stderr or stdout).strip()[:600]}")

        # --output-format json：单个对象，result 为最终文本
        result_text = stdout
        try:
            wrapper = json.loads(stdout.strip().splitlines()[-1])
            if isinstance(wrapper, dict) and "result" in wrapper:
                if wrapper.get("is_error"):
                    raise RuntimeError(f"agent 返回错误：{str(wrapper.get('result'))[:600]}")
                result_text = str(wrapper.get("result") or "")
                agent_session = wrapper.get("session_id", "")
                usage = wrapper.get("usage") or {}
            else:
                agent_session, usage = "", {}
        except (json.JSONDecodeError, IndexError):
            agent_session, usage = "", {}
        parsed = _extract_json(result_text)
        review = _normalize(parsed, repo)

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
            t.review = review
            t.analysis_status = ANALYSIS_DONE
            db.flush()
        run_verify(task_id)
        bus.publish("tasks", {"type": "task", "id": task_id})
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        log.exception("分析失败 %s", task_no)
        with session() as db:
            t = db.get(Task, task_id)
            if t is not None:
                t.analysis_status = ANALYSIS_FAILED
                t.error = f"分析失败：{exc}"[:2000]
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
