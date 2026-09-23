"""GSB 对比分析：把两侧材料摆进一个只读目录，让模型读完它，拿回谁更好与理由。

这里的做法变过两次，中间那一版的教训值得记着。

最早是放一个 agent 进两份产物副本里自己漫游：拷仓库、装依赖、跑测试、来回读代码，
一次四十到九十分钟，失败原因散在几百次工具调用里，重试等于再赌一小时。于是改成
确定性采集——git 给产物差异，轨迹索引给过程，全部拼进一个 prompt 问一次就够。快是
快了，可拼进去的东西必须先过预算：补丁截到 40000 字符，轨迹压成一行一步、每步 120
字、最多 140 步。模型看到的过程因此是有洞的：工具返回被切在第 120 个字符，失败的
用例名在第 400 个字符上，步数过百的还要等距抽样。拿这种材料判「哪一侧绕了远路」，
判得再认真也只是在归纳摘要。

现在是第三版：材料落进 reports/<题号>/evidence/，工作目录钉在那儿，模型自己去读。
和最早那版漫游的区别在于它读不到仓库本体——ask 模式不放开 shell，目录里只有我们摆
进去的轨迹、补丁和题面，没有依赖可装，没有测试可跑，所以既拿回了完整材料，又没有
把四十分钟和几百兆副本一起拿回来。

配套的是 evidence 逐字回查（gsb_evidence.check_quotes）。材料从 prompt 里拿走之后，
不读文件是写不出能对上原文的引用的，所以「一条都对不上」直接判这次分析失败。这道
回查是整条链路上唯一能程序化判定编造的地方，别把它当成可选的质量提示。

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
from collections.abc import Callable
from pathlib import Path

from app import config
from app.db import session
from app.events import bus
from app.models import (
    ANALYSIS_DONE, ANALYSIS_FAILED, ANALYSIS_RUNNING, ANALYZED, ANALYZING, FACTCHECK_IDLE,
    NEEDS_ATTENTION, PRECHECK_IDLE, QC, Task, TaskRun, utc_now,
)
from app.services import dockerx, gsb_evidence, gsb_repo, gsb_rules, llm, trace

log = logging.getLogger("gsb_analyzer")

# 平台下拉框里的原文。库里存 A/B/Same 这种短值，上传时再换成平台的中文标签，
# 免得平台改文案就得跟着迁移历史数据
VERDICT_LABEL = {"A": "A 更好", "B": "B 更好", "Same": "Same"}
VERDICTS = tuple(VERDICT_LABEL)

# 补丁有两个预算，因为它有两个去处，两边的约束不是一回事。
#
# 进 prompt 的那份卡在 40000：两侧补丁加轨迹曾经到过 190KB，Opus 生成加上 HTTP/2
# 长流，容器里经常 15 分钟被掐掉再整段重跑。这是请求体的限制。
#
# 落进证据目录的那份不受这条限制 —— 它只是磁盘上的文件，供逐字回查和事后翻查。
# 给得宽是必要的：引用回查拿它当原文比对，用截断过的那份会把「引自被截掉的那个
# 文件」的正当引用判成编造。但也不能不设上限，锁文件、快照测试、误提交的构建产物
# 单个就能有几十兆。超了一律按文件边界截断并写明还剩几个，而不是整段砍掉 ——
# 半截补丁比没有补丁更容易让人误判。
DIFF_BUDGET = 40000
EVIDENCE_DIFF_BUDGET = 400000
STEP_LIMIT = 140
STEP_TEXT_LIMIT = 120
# 步骤列表里一律不带命令输出，输出统一走执行记录那一块。两处都放会把同一段文本
# 在 prompt 里计两次预算，而步骤列表要的只是「按顺序发生了什么」。
FACTS_BUDGET = 12000
# 一条命令的输出留多少。测试框架的结论行（多少过多少败、哪个用例炸了、编译错在哪）
# 基本都落在输出的头尾，中间是逐条用例的刷屏，所以掐头留尾比整段截断有用。
OUT_LIMIT = 240
CHECK_LIMIT = 24
FAILURE_LIMIT = 16
ENDING_LIMIT = 800

# 这三类差异不反映模型能力，写进理由等于拿环境问题给模型定罪，平台也不认。
EXCLUDED_FACTORS = """
以下三类因素不许纳入判断，也不许写进 reason：
1. 推理时长。两侧的耗时差异可能来自部署与排队，快慢不代表能力。
2. 模型没有报错但戛然而止。这受部署与 harness 适配影响，不是模型自己放弃。
3. 网络工程错误，包括网络波动、请求失败、网关超时、连接重置、限流。
某一侧出现上面任何一种情况，只在 remark 字段里写一句说明，不写进 reason，
也不作为谁更好的依据。
""".strip()

# 这一段单独摆出来，不混在写法要求里。它管的不是怎么写，是允不允许说——
# 违反写法要求最多是读起来像机器，违反这一条是把对方没犯的错算到它头上，
# 交上去就是一份错的评审。
#
# 之所以要写这么死：模型拿到一份看着有问题的 diff（少了个导入、类型对不上、
# 改了函数签名没改调用方），几乎必然会顺手写一句「这一侧跑不起来」。而那句话
# 它并没有依据，执行记录里明明白白写着跑通了。这类断言在已提交的数据里出现过
# 不止一次，每一次都要回头人工订正。
FACT_REDLINE = """
【红线：执行结果只能来自执行记录】
这一条违反了，整份分析作废，比结论判错还严重。

1. 关于「跑没跑起来、编译过没过、测试过没过、报了什么错」的每一句话，都必须能在
   那一侧的实际执行记录里指出是哪一条命令、哪一段输出。指不出来就不要写。
2. 不许从代码改动推断执行效果。看着少了个导入、看着类型对不上、看着签名改了调用方
   没跟着改——这些都只能说成「代码上看这里有问题」，不能说成「所以它跑不起来」
   「所以构建会失败」。一侧到底跑没跑起来，执行记录里有答案，没答案就是没有依据。
3. 不许把「执行记录里没有」说成「它没做过」以外的任何东西。没有校验命令，能写的
   只有「没有留下验证记录」；不能写成「跑不通」「有问题没发现」。
4. 执行记录里有成功的测试或构建，就不许写「没跑过测试」「没有验证」；有完整的收尾
   总结，就不许写「戛然而止」「中途放弃」。
5. 两侧都按同一把尺子量。不要因为某一侧的执行记录更详细就默认它更可靠，也不要
   因为另一侧记录少就补一句推断出来的负面结论。

【红线：说 A 的事只能出自 A 的材料，说 B 的事只能出自 B 的材料】
6. 写到某一侧的函数名、文件名、做法、过程中做过的事，都必须出自那一侧自己的材料。
   两侧思路相同、名字不同时，各写各的名字：A 叫 deleteNode 就写 deleteNode，
   不能借用 B 的 removeNode。不许把两侧的名字揉进一句、记在同一侧头上。
7. 一句话里的主语要和它说的东西在同一侧。「size 依据 removeNode 的返回值更新，
   A 正是这样处理的」这种写法，读的人会把 removeNode 记到 A 头上；说的是 B 就写明
   「B 的 removeNode」。
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
        raw_patch = await _git(ws, "diff", *rng, "--", ".")
        patch, cut = _truncate_patch(raw_patch)
        material["patch"] = patch
        material["patch_truncated"] = cut
        # 落盘那一份按更宽的预算单独截。回查拿证据目录里的原文比对，用进 prompt
        # 的那份（40000 字符）会把「引自被截掉的那个文件」的正当引用判成编造。
        material["patch_full"] = _truncate_patch(raw_patch, EVIDENCE_DIFF_BUDGET)[0]
        if not base:
            # 未提交时未跟踪的新文件不在 diff 里，单独列出来，否则新增的实现整份看不到
            untracked = [f for f in (await _git(ws, "ls-files", "--others",
                                                "--exclude-standard")).splitlines() if f.strip()]
            material["untracked"] = untracked[:50]
    else:
        material["diff_stat"] = ""
        material["files"] = []
        material["patch"] = ""
        material["patch_full"] = ""

    index = _load_trace_index(task_no, side)
    material["steps"] = _condense_steps(index)
    material["counts"] = index.get("counts") or {}
    material["facts"] = run_facts(index)
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
            # 按名额把正常步均匀铺满整段，必须把最后一步含进来。
            # 以前用 plain[::stride][:room] 取：stride 向下取整，抽出来的比名额多，
            # 再被 [:room] 一刀切，切掉的正好是收尾那一截。模型于是看不到最后的
            # 测试结果和总结，把跑完的一侧写成「戛然而止」「没跑过测试」。
            if len(plain) <= room:
                keep.update(plain)
            else:
                last = len(plain) - 1
                keep.update(plain[round(k * last / (room - 1))] if room > 1 else plain[last]
                            for k in range(room))
        steps = [s for i, s in enumerate(steps) if i in keep]

    out = []
    for s in steps:
        kind = s.get("tool") or s.get("kind") or "step"
        summary = " ".join(str(s.get("summary") or "").split())[:STEP_TEXT_LIMIT]
        flag = " [报错]" if s.get("is_error") else ""
        out.append(f"{kind}{flag} {summary}".strip())
    return out


# ---------------- 执行记录 ----------------
# 这一块是为了堵住一类反复出现的错判：模型看着代码改动，推断「这一侧编译不过」
# 「跑不起来」「没跑过测试」，而轨迹里明明摆着跑通的命令和完整的收尾总结。根子在
# 材料本身——送进 prompt 的步骤列表只有工具名和命令原文，没有任何一条命令的输出。
# 模型手上压根没有执行结果，于是只能从 diff 推，推出来的又被当成事实写进理由。
#
# 所以把「实际执行了什么、跑出了什么」单独摘成一块结构化材料。摘的是三样：
#   - 校验类命令（测试、构建、lint、直接跑脚本）连同它们的输出；
#   - 所有报错的步骤，不限于命令；
#   - 收尾那段话，用来判这一侧到底有没有跑完。
# 三样都来自轨迹，没有任何推断。轨迹里没有就是空的，空的本身也是事实——prompt 里
# 会写明「这一侧没有执行记录」，而不是留白让模型自己填。

SRC_EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SRC_PATH = re.compile(r"\.(py|js|mjs|cjs|ts|tsx|jsx|go|rs|java|rb|php|c|h|cc|cpp|swift|kt)$")
# 校验类命令：跑测试、构建、类型检查、lint，以及直接把脚本跑起来复现。
# 「直接跑脚本」必须收进来——很多题的验证方式就是 node repro.js 看输出对不对，
# 漏掉它这类题就会整批显示成「没有任何执行记录」。
VERIFY_CMD = re.compile(
    r"\b(?:npm|pnpm|yarn|npx|bun|deno)\s+(?:run\s+)?(?:test|build|lint|check|tsc|typecheck)\b"
    r"|\b(?:pytest|vitest|jest|mocha|tox|nox|rspec|phpunit|ruff|eslint|mypy|tsc|flake8)\b"
    r"|\bcargo\s+(?:test|build|check|clippy)\b|\bgo\s+(?:test|build|vet)\b"
    r"|\b(?:mvn|gradle|make|cmake|dotnet)\b|\bdotnet\s+test\b"
    r"|\bnode\s+--test\b|\bpython\d?\s+-m\s+(?:pytest|unittest)\b"
    r"|\b(?:node|python\d?|ruby|php|deno\s+run|bun\s+run)\s+[\w./-]+\.\w+", re.I)


def _clip(text: str, limit: int = OUT_LIMIT) -> str:
    """把一段输出压到 limit 以内，掐头留尾。

    测试框架的结论（多少条过、哪条炸了、编译错在哪）落在输出的开头或结尾，中间
    是逐条用例的刷屏。整段从前面截断会把「N failed」那一行切掉，而那一行恰恰是
    这块材料存在的全部理由。

    中间用单个省略号、两边留空格，这是 gsb_evidence 认的跨段标记。模型照抄这段
    输出当证据时，引用回查会按省略号把它拆成前后两截分别去原文里找；换成两个
    省略号或者不留空格，那道回查就认不出来，一条本来有据的引用会被判成编造。
    """
    body = " ".join(str(text or "").split())
    if len(body) <= limit:
        return body
    head = limit * 2 // 3
    return f"{body[:head]} … {body[-(limit - head):]}"


def run_facts(index: dict) -> dict:
    """从轨迹索引里摘出这一侧真实发生过的执行结果。不做任何推断。

    `after_last_edit` 是最有用的一项：改完代码之后还跑没跑过校验，直接决定了
    「交出去的这一版到底验证过没有」。改之前跑通不算数，那验的是改之前的代码。
    """
    steps = list(index.get("steps") or [])
    last_edit = -1
    last_edit_file = ""
    for i, s in enumerate(steps):
        if s.get("tool") in SRC_EDIT_TOOLS:
            for f in (s.get("files") or []):
                if SRC_PATH.search(str(f)):
                    last_edit, last_edit_file = i, str(f)
                    break

    checks: list[dict] = []
    failures: list[dict] = []
    commands = 0
    for i, s in enumerate(steps):
        summary = str(s.get("summary") or "")
        is_cmd = s.get("tool") == "Bash"
        if is_cmd:
            commands += 1
            cmd = " ".join(summary.lstrip("$ ").split())
            if VERIFY_CMD.search(cmd) and len(checks) < CHECK_LIMIT:
                checks.append({"cmd": cmd[:160], "ok": not s.get("is_error"),
                               "out": _clip(s.get("result")),
                               "after_last_edit": i > last_edit})
        if s.get("is_error") and len(failures) < FAILURE_LIMIT:
            what = (" ".join(summary.lstrip("$ ").split()) if is_cmd
                    else f"{s.get('tool') or s.get('kind') or 'step'} {summary}")
            failures.append({"what": what[:160], "out": _clip(s.get("result"))})

    return {
        "steps_total": len(steps),
        "commands_total": commands,
        "last_edit_file": last_edit_file,
        "checks": checks,
        "failures": failures,
        "ending": _clip(index.get("last_assistant_text"), ENDING_LIMIT),
        "stop_reason": str(index.get("stop_reason") or ""),
    }


def facts_block(facts: dict) -> str:
    """把执行记录摊成 prompt 里的一段。空的也要写出来，留白会被当成「没查到」。"""
    if not facts or not facts.get("steps_total"):
        return "（这一侧没有轨迹，执行情况无从判断，不要就此下任何结论）"

    out: list[str] = []
    checks = facts.get("checks") or []
    if checks:
        out.append("跑过的校验类命令（测试 / 构建 / 类型检查 / 直接运行）：")
        for c in checks:
            when = "最后一次改代码之后" if c.get("after_last_edit") else "最后一次改代码之前"
            out.append(f"  [{'成功' if c.get('ok') else '失败'}·{when}] {c['cmd']}")
            if c.get("out"):
                out.append(f"      输出：{c['out']}")
    else:
        out.append("跑过的校验类命令：一条都没有。"
                   "（这是「没有验证过」的唯一依据，也仅能支撑这一句，"
                   "不要据此说产物跑不起来或者编译不过。）")

    failures = facts.get("failures") or []
    if failures:
        out.append("报过错的步骤：")
        for f in failures:
            out.append(f"  {f['what']}")
            if f.get("out"):
                out.append(f"      报错：{f['out']}")
    else:
        out.append("报过错的步骤：没有。")

    if ending := facts.get("ending"):
        out.append(f"最后说的话（用它判断这一侧是不是跑完了）：{ending}")
    else:
        out.append("最后没有留下任何总结性的话。")
    if reason := facts.get("stop_reason"):
        out.append(f"结束原因：{reason}")

    text = "\n".join(out)
    return text if len(text) <= FACTS_BUDGET else text[:FACTS_BUDGET] + "\n  （执行记录过长，已截断）"


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

DELIVERY_OUTPUT = (
    f'  "a_delivery": {{"score": 1 到 5 的整数, "desc": "A 侧交付完整性描述，'
    f'{gsb_rules.DELIVERY_TARGET_MIN} 到 {gsb_rules.DELIVERY_TARGET_MAX} 字，只写 A"}},\n'
    f'  "b_delivery": {{"score": 1 到 5 的整数, "desc": "B 侧交付完整性描述，只写 B"}},'
)


def delivery_section() -> str:
    """交付完整性那一段要求。分析、补问、事实核验三处给模型的是同一段话。"""
    return f"""【交付完整性评分】
除了对比结论，还要给两侧各打一个交付完整性分（1 到 5 的整数），并各写一段描述。
这一项是给每一侧单独打的绝对分，和上面「谁更好」的对比是两件事。评分表：
{gsb_rules.DELIVERY_RUBRIC}

{gsb_rules.DELIVERY_WRITING_RULES}"""


def build_prompt(task: Task, materials: dict[str, dict]) -> str:
    """组对比 prompt。两侧材料对称摆开，不给任何一侧多余的上下文。

    材料随 prompt 一起送进去，不靠模型自己去读文件。这一条是有意选的：送进去的
    东西一定在上下文里，而「让它自己读」是在赌它愿意读 —— 赌输了拿回来的是一份照着
    概览编的结论，形状和真读过的一模一样。压缩的代价用摘出来的执行记录抵掉：
    步骤摘要只说做了什么，命令到底跑出了什么由 facts_block 单独给，而那一块恰恰是
    从 diff 推不出来、又必须准的部分。

    压缩本身是请求体逼出来的：两侧补丁加轨迹曾经到过 190KB，Opus 生成叠上 HTTP/2
    长流，容器里经常十几分钟被掐掉再整段重跑。压缩之前的原样落在证据目录里，
    引用回查拿它当底本（见 gsb_evidence）。
    """

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
            f"实际执行记录（摘自轨迹，是执行结果的唯一依据）：\n"
            + "\n".join(f"  {line}" for line in facts_block(m.get('facts') or {}).splitlines()) + "\n"
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
下面给出的就是全部材料，没有别的地方可查。每一侧给四样东西，各有各的用途，不要串用：
- 代码改动：判断产物好坏的依据。需求点实现了没有、接口改没改坏、边界处理得全不全，
  都看它。
- 实际执行记录：判断执行结果的唯一依据。跑没跑起来、编译过没过、测试过没过、
  报了什么错，只看它，它没写的就是没有依据。
- 步骤记录：看过程走向的，哪里顺、哪里卡、哪里反复试错。它只说做了什么，不说结果，
  所以不要拿它当结论。
- 改动统计与文件清单：看改动规模和落点的。

{block('A')}
{block('B')}

{FACT_REDLINE}

【工作步骤】
1. 先读原始 prompt，把需求拆成可核验的功能点与约束清单。
2. 对着两侧的代码改动逐条核验，看功能点是不是真的实现了、约束有没有被破坏。
3. 再读两侧的实际执行记录，确认各自到底跑过什么、跑出了什么结果。要写进理由的
   每一句执行结果，都要能在这份记录里指出是哪一条。
4. 再看两侧的过程，判断各自哪里顺、哪里卡、哪里绕了远路或者反复试错。
5. 逐项对比，给出哪一侧更好，或者确实等价。核验做得细是对的，但写的时候只挑
   一到两个真正影响结论的点展开，别把核验清单原样交出去。
6. 另外分别给出两侧产物的启动方式，要让人照着就能把项目跑起来录屏；
   材料不足以给出完整步骤时，在对应的 note 里写清缺什么。
7. 最后按下面的评分表，分别给 A、B 打交付完整性分并写描述。先定分再写描述，写完回头
   对一遍：分数、描述、reason 里说这一侧的话，三者讲的必须是同一件事。

【结论必须有据】
理由里写到的每一处事实，都要能在上面那些文件里找到出处。想不起来在哪读到的，
就回去翻一遍再写；翻不到的，那一句不要写。宁可少写一个论点，也不要写一句
查不到出处的话。

【不许纳入判断的因素】
{EXCLUDED_FACTORS}

【写法要求】
{gsb_rules.WRITING_RULES}

{delivery_section()}

【输出格式】
只输出一个 JSON 对象，不要任何前后说明，不要代码块围栏。结构如下（字段名必须完全一致）：
{{
  "verdict": "A" 或 "B" 或 "Same",
  "reason": "对比理由正文，{gsb_rules.REASON_TARGET_MIN} 到 {gsb_rules.REASON_TARGET_MAX} 字，A 和 B 都要写到",
  "a_findings": {{"good": ["…"], "bad": ["…"]}},
  "b_findings": {{"good": ["…"], "bad": ["…"]}},
  "a_startup": {{"steps": ["…"], "commands": ["…"], "note": "给不出完整步骤时写原因，否则空串"}},
  "b_startup": {{"steps": ["…"], "commands": ["…"], "note": ""}},
{DELIVERY_OUTPUT}
  "evidence": [{{"side": "A", "file": "src/x.ts", "quote": "从上面材料里逐字复制的原文片段"}}],
  "remark": "被排除的那三类情况如果出现就写在这里，否则空串"
}}

evidence 这一项会被程序拿回原文里逐字核对，所以它的要求和别的字段不一样：

- quote 必须是你从上面那几块材料（代码改动、执行记录、步骤记录）里逐字复制的一段
  原文，不要转述、不要概括、不要把几处拼成一句。换行和缩进对不上没关系，字要对得上。
- 引用被截断过的那种输出时，中间用一个省略号接起来，前后各留一个空格。
- 对不上原文的会被整条丢掉；丢到一条不剩，这次分析判定失败重来。
- 每一侧至少给两条，并且要覆盖你在理由里真正用来支撑结论的那几个点。
- side 必须是 A 或 B，file 填这段原文所在的那个文件的路径。
- 不要填步号。
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


def extract_object(text: str, key: str, what: str) -> dict:
    """从模型最终文本里提取含 key 的 JSON 对象：容忍前置说明、代码围栏、结尾少括号。

    按 key 认而不是取第一个对象：模型经常先吐一个小对象当示例或说明，取第一个
    就会拿到那个壳子。
    """
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
            if isinstance(obj, dict) and key in obj:
                return obj
    raise ValueError(f"输出中没有可解析的{what}：{last_err}")


def extract_json(text: str) -> dict:
    return extract_object(text, "verdict", "GSB JSON")


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


_VERDICT_WORD = re.compile(r"判(?:定|为|给)?\s*(?=(?:[AB](?![A-Za-z0-9_])|[Ss]ame\b))")


def soften_verdict(text: str) -> str:
    """把「判 A 更好」里的「判」字去掉，剩下「所以 A 更好」这种人会说的话。

    这一条本可以只靠 prompt，实测靠不住：模型要么留着「判」，要么为了换说法把整段
    写长，超了篇幅又被改写那一轮丢弃，来回四轮还停在原地。而它恰恰是每道题的最后
    一句，漏一次就整段露怯，所以在这里兜死。

    只删「判」不补别的词：「这个权重更低，判 B 更好」删完就是「这个权重更低，B 更好」，
    读起来是通的；补个「所以」反而会和前面已有的「所以」撞上。前面是汉字时留一个
    空格，「综合下来判定 B」才不会挤成「综合下来B」。
    """
    if not text:
        return text

    def cut(m: re.Match) -> str:
        prev = text[m.start() - 1] if m.start() else ""
        return " " if "\u4e00" <= prev <= "\u9fff" else ""

    return _VERDICT_WORD.sub(cut, text)


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
    return soften_verdict(strip_machine_metrics(strip_steps(strip_markdown(text))))


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


def delivery_of(obj, repos: dict[str, Path] | None = None) -> dict:
    """一侧的交付完整性。分数认不出来留 None，不猜——猜出来的分会带着描述一起交出去。"""
    d = obj if isinstance(obj, dict) else {}
    return {"score": gsb_rules.parse_score(d.get("score")),
            "desc": _clean(d.get("desc") or d.get("description"), repos)}


def delivery_complete(gsb: dict) -> bool:
    """两侧的评分和描述都有了没有。"""
    return all(gsb_rules.parse_score((gsb.get(k) or {}).get("score")) is not None
               and str((gsb.get(k) or {}).get("desc") or "").strip()
               for k in ("a_delivery", "b_delivery"))


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
        "a_delivery": delivery_of(obj.get("a_delivery"), repos),
        "b_delivery": delivery_of(obj.get("b_delivery"), repos),
        "evidence": [
            {"side": str(e.get("side") or "").upper()[:1],
             "file": _clean(e.get("file"), repos),
             # quote 一个字都不洗。_clean 那套是给交付出去的正文准备的，套在 quote 上
             # 只会把它改坏：去 markdown 记号会吃掉代码里的反引号和 /** */，去绝对路径
             # 会把「Write /tmp/stubs/pytest/__init__.py」洗成「Write __init__.py」，
             # 洗完的句子回材料里必然找不到，回查于是把有据的引用判成编造。它唯一的
             # 用途就是逐字比对，又不随理由上传，留着原文没有外泄的问题。
             "quote": str(e.get("quote") or "").strip()}
            for e in (obj.get("evidence") or []) if isinstance(e, dict)
        ][:24],
        "remark": _clean(obj.get("remark"), repos),
    }


# ---------------- 生成时收口 ----------------
# 写作规范进 prompt 并不等于模型会照做。规范改成五六百字之后，交回来的理由仍然
# 普遍是一千多字，而核验里篇幅只是黄项，拦不住入库，结果每批题都得人工回头重写
# 一遍。所以在这里加一道自查：用 gsb_rules 那份表挑出毛病，把毛病原样念给模型让
# 它改，改完再查。规则只有一份，因此不会出现「自查放过、核验却拦」。
#
# 这一轮不给材料，只给正文。要的是收篇幅、换措辞、换开场，不是重新判断；给了材料
# 模型就会去补新论点，补出来的东西没有经过第一轮的核对。
REASON_FIX_ROUNDS = 4
# 改写的 prompt 只有一两千字，正常一分钟内就回。给死上限是为了不让一次卡顿把
# 整道题的分析拖到和主调用一样长。
REASON_FIX_TIMEOUT_S = 600


def _reason_score(text: str, *, verdict: str, peer_openings: dict | None
                  ) -> tuple[list[str], tuple[int, int, int]]:
    """返回 (毛病清单, 用来比好坏的分数)。分数越小越好，按先后逐项比。

    三项都有用，少一项就会误判：

    - 红项条数排最前。红项是平台会打回的东西，黄项只是读起来像不像人写的。不分
      轻重的话，一段「太短」会被当成和「太长」等价，于是模型回一句二十几个字的
      话也算改好了，而太短恰恰是核验会拦的那一档。
    - 黄项条数其次。
    - 最后记离篇幅窗口还差多少字。超篇幅只算一条黄项，一千字砍到七百字在条数上毫无
      变化，只按条数比就会把这次真实的进展整个丢掉，改三轮也原地不动。
      两头都要记：篇幅窗口抬到三百五到四百五之后，写短了也成了一档要改的毛病，
      只记超出的那头会让「二百字补到三百字」同样显示成没有进展。
    """
    found = gsb_rules.reason_checks(text, verdict=verdict, peer_openings=peer_openings)
    blocks = sum(1 for _, level, _ in found if level == "block")
    n = gsb_rules.visible_chars(text)
    off = max(0, n - gsb_rules.REASON_SOFT_MAX_CHARS, gsb_rules.REASON_SOFT_MIN_CHARS - n)
    return [m for _, _, m in found], (blocks, len(found) - blocks, off)


def build_reason_fix_prompt(reason: str, defects: list[str]) -> str:
    """把毛病念给模型，让它改这一段。

    篇幅超了就把要砍掉多少字算出来一起给。只说「超过上限」它往往只削掉一两句，
    给出确切的字数缺口才会真的去掉一整个次要论点。

    没超限也要说，而且这一档更容易翻车。贴着上限的那批余量只有几个字，不给预算
    它就只管换说法，562 字换完成 588 字，措辞那条修掉了、超篇幅那条冒出来，分数
    没变好，整版被丢弃，四轮下来原文一个字没动。

    缺口按窗口中位算，不按上限算。照上限要它会压到刚好擦线，实测一段九百多字的
    改三轮仍停在六百三十字，离上限只差十几个字；瞄中位留出余量，略微收不够也还
    落在区间里。

    差得太多时改口说「重写」。按删减说，它每轮只肯砍掉四分之一左右——一千零四十五
    字的那段三轮下来还有七百八十字。要收掉将近一半就不是修剪，得让它照着一两个
    决定胜负的点重新写一段。
    """
    listed = "\n".join(f"{i}. {d}" for i, d in enumerate(defects, 1))
    n = gsb_rules.visible_chars(reason)
    aim = (gsb_rules.REASON_TARGET_MIN + gsb_rules.REASON_TARGET_MAX) // 2
    if n < gsb_rules.REASON_SOFT_MIN_CHARS:
        # 写短了。补字这件事比删字危险得多：模型手上已经没有材料了，让它「写长一点」
        # 它就会去编执行结果。所以把补什么说死——补的是原文已经点到、但只说了半句
        # 的那些判断依据，不是新的论点。
        listed += (f"\n\n这一段现在 {n} 字，太短了，要补到 {gsb_rules.REASON_TARGET_MIN} 到 "
                   f"{gsb_rules.REASON_TARGET_MAX} 字，落在 {aim} 字左右最好。"
                   f"补的只能是原文里已经点到、但没讲透的那部分：某一侧具体差在哪个文件的"
                   f"哪个地方、这个问题会造成什么后果、为什么这一点压过了另一侧的长处。"
                   f"不要补新的论点，更不要补原文里没有的执行结果——"
                   f"跑没跑通、测试过没过，原文没写的就是没有依据，一个字都不要加。")
    elif n <= gsb_rules.REASON_SOFT_MAX_CHARS:
        # 没超限也要把预算说出来。不说它就只管换说法，一段 562 字的换完就是 588 字，
        # 措辞那条警告是修掉了，超篇幅那条又冒出来，分数没变好，整版被丢弃——四轮
        # 下来原文一个字没动。这批题本来就贴着上限，余量只有几个字。
        listed += (f"\n\n这一段现在 {n} 字，改完不要超过 {gsb_rules.REASON_TARGET_MAX} 字，"
                   f"落在 {aim} 字左右最好。换说法的时候顺手把最弱的那个论点删掉，"
                   f"别一边改措辞一边把篇幅撑上去。")
    else:
        listed += (f"\n\n这一段现在 {n} 字，要收到 {gsb_rules.REASON_TARGET_MIN} 到 "
                   f"{gsb_rules.REASON_TARGET_MAX} 字，最好落在 {aim} 字左右，也就是去掉大约 "
                   f"{n - aim} 字。")
        # 阈值挂在上限上，不挂在中位上。挂中位的写法在旧窗口里（中位 525、上限 570）
        # 恰好等于上限的一点四倍，留出五百多到七百多这一段「删减」带；篇幅窗口收到
        # 三到四百之后，中位掉到 350，一点五倍是 525，和 500 的上限几乎贴在一起，
        # 删减带只剩二十几个字，等于凡是超限一律按重写走 —— 而超出几十字的那种，
        # 重写会把已经写好的论证整个推翻，换回来的往往是一段更泛的话。
        if n > gsb_rules.REASON_SOFT_MAX_CHARS * 1.4:
            listed += ("这一步不是修剪，是重写：先定下哪一到两个点真正影响了结论，"
                       "只把这一两个点讲透，其余的最多各一句带过，剩下的整段不要。"
                       "在原文上逐句删改收不到这个篇幅。")
        else:
            listed += "删掉整个次要论点，不要靠压缩句子硬凑。"
    return f"""下面这段是一份双跑对比的评审理由，它违反了写作规范，需要你改写。

【当前正文】
<<<REASON
{reason}
REASON>>>

【必须改掉的地方】
{listed}

【写法要求】
{gsb_rules.WRITING_RULES}

【改写约束】
1. 只在现有正文的事实范围内删减和改写。不要新增正文里没有的事实，不要换结论，
   哪一侧更好必须和现在一致。
2. 篇幅超了就砍内容，不要靠压缩句子硬凑：只留一到两个真正影响结论的点展开，其余的
   最多一句带过，够不上的一句都不写。
3. 开头句式被指出雷同时，换一个按这道题自己的矛盾来起头的写法，不要只改几个字。
4. 只输出改写后的正文。不要 JSON，不要代码块围栏，不要任何说明或前言。"""


# 规则拦得住篇幅和措辞，拦不住颗粒度。原本就写在上限以内的那批因此一次都没被
# 重写过，读起来仍然是每个点都交代一句的核对清单——查得出毛病的反而都被收拾干净了，
# 没毛病的原样留着，一份文档里两种笔法。点名强制时用这条当由头让它重写。
GRANULARITY_DEFECT = (
    "这一段是按核对清单写的：两侧的每个点都交代一句，颗粒度细到真人评审观察不到。"
    "重写成只讲一到两个真正影响结论的点，把它们讲透，其余的最多一句带过，"
    f"够不上的一句都不写，收到 {gsb_rules.REASON_TARGET_MIN} 到 "
    f"{gsb_rules.REASON_TARGET_MAX} 字。"
)


async def polish_reason(reason: str, *, verdict: str, peer_openings: dict | None = None,
                        repos: dict[str, Path] | None = None, purpose: str = "",
                        rounds: int = REASON_FIX_ROUNDS,
                        forced: bool = False) -> tuple[str, list[str]]:
    """把理由改到符合写作规范。返回 (最终正文, 还没修掉的毛病)。

    只在确有改善时才采信改写稿。模型偶尔会把一处毛病换成两处，无条件采用就会
    越改越差；改不动就把原文留着，剩下的毛病回报给调用方记录下来，让人能看见，
    而不是静悄悄地交一段不合规的话。好坏的比法见 _reason_score。

    forced 用来重写那些查不出毛病、但笔法还停在核对清单上的。这时基准分要故意
    记差一档，否则原文是满分，任何改写都「没有变好」，四轮全被丢弃，等于没跑。
    记差一档之后，只有改完自身挑不出毛病的那一版才会被采信。

    另外每一版都要查落点。这几轮只给正文不给材料，模型手里没有 diff 也没有轨迹，
    它写下的任何一个新文件名都无从查证，而正文是要原样交给评审的。基准取最初那一
    稿而不是上一版：上一版已经过了这道关，它的落点本来就能追到第一轮核对过的材料，
    拿它当基准等于允许落点一轮一轮往外漂。
    """
    text = reason
    origin = reason
    defects, score = _reason_score(text, verdict=verdict, peer_openings=peer_openings)
    if not defects and forced:
        defects, score = [GRANULARITY_DEFECT], (0, 1, 0)
    if not defects:
        return text, []

    for rnd in range(1, rounds + 1):
        log.info("%s 理由不合规 %d 处（%d 字），第 %d 轮改写：%s",
                 purpose or "GSB", len(defects), gsb_rules.visible_chars(text),
                 rnd, "；".join(defects)[:200])
        try:
            r = await llm.ask(build_reason_fix_prompt(text, defects),
                              purpose=f"{purpose} 理由改写", attempts=1,
                              timeout_s=REASON_FIX_TIMEOUT_S)
        except llm.LlmError as exc:
            log.warning("%s 理由改写调用失败，保留上一版：%s", purpose or "GSB", exc)
            break
        fixed = _clean(r.text, repos)
        if not fixed:
            log.warning("%s 理由改写返回空，保留上一版", purpose or "GSB")
            break
        if invented := gsb_rules.invented_tokens(fixed, origin):
            log.warning("%s 第 %d 轮改写冒出了原文没有的落点（%s），丢弃这一版",
                        purpose or "GSB", rnd, "、".join(invented[:4]))
            continue
        left, new_score = _reason_score(fixed, verdict=verdict, peer_openings=peer_openings)
        if new_score >= score:
            log.warning("%s 第 %d 轮改写没有变好（%s %d 字 → %s %d 字），丢弃这一版",
                        purpose or "GSB", rnd, score, gsb_rules.visible_chars(text),
                        new_score, gsb_rules.visible_chars(fixed))
            continue
        text, defects, score = fixed, left, new_score
        if not defects:
            log.info("%s 理由第 %d 轮改写后合规，%d 字",
                     purpose or "GSB", rnd, gsb_rules.visible_chars(text))
            return text, []
    return text, defects


def vet_rewrite(rewrite: str, original: str, verdict: str,
                repos: dict[str, Path] | None = None,
                grounded: Callable[[str], bool] | None = None) -> tuple[str, str]:
    """决定一份整段改写稿要不要留。返回 (采信的稿子, 丢弃原因)，两者必有一个是空的。

    事实核验和口语化质检都会整段换掉理由，而它们都是自动落库、不等人点头的。所以
    「什么样的稿子能用」必须只有一份判据：两处各写一套的话，一份稿子在这一步被放行、
    换到那一步又被拦，人看到的是同一段话时好时坏，而两处的日志都说自己是对的。

    四道关：
    - 篇幅落在规范的窗口里。下限防删过头，上限防它只换说法不压篇幅。
    - 不能引入原文没有的核验红项。原文本来就有的不算它的账——那是上一步留下的，
      在这里拦住只会让这一步永远交不出稿子。
    - 不能冒出原文没有的文件名或代码符号。这一关是这里唯一防编造的手段：改写这几轮
      手里只有正文，没有题面、没有 diff、也没有轨迹，本意是让它没有素材去补新论点，
      但换句话说，它凭空写下的任何一个文件名都无从查证，而稿子采信之后就直接盖掉
      理由正文，那个文件名会原样交到评审手里。
    - 两侧都还在。结论翻没翻程序判不了，但一份只剩单侧的稿子必然是删过头了，
      而这恰好是 reason_both_sides 这条红项管的事，第二条已经覆盖。

    grounded 是给手上有轨迹的那一步留的口子（事实核验）：新冒出来的名字在轨迹里查得
    到就不算编。订正张冠李戴本来就要把 B 的名字换成 A 自己的名字，不放这个口子，
    那种句子就只能删、不能改。
    """
    text = _clean(rewrite, repos)
    if not text:
        return "", ""
    n = gsb_rules.visible_chars(text)
    floor = (gsb_rules.MIN_SAME_REASON_CHARS if verdict == "Same"
             else gsb_rules.MIN_REASON_CHARS)
    if n < floor:
        return "", f"改写稿只有 {n} 字，不足 {floor} 字，删过头了"
    if n > gsb_rules.REASON_SOFT_MAX_CHARS:
        return "", (f"改写稿 {n} 字，仍然超过 {gsb_rules.REASON_SOFT_MAX_CHARS} 字的上限，"
                    f"只换了说法没有压篇幅")
    before = {name for name, level, _ in gsb_rules.reason_checks(original, verdict=verdict)
              if level == "block"}
    after = [msg for name, level, msg in gsb_rules.reason_checks(text, verdict=verdict)
             if level == "block" and name not in before]
    if after:
        return "", f"改写稿引入了原文没有的红项：{'；'.join(after[:2])}"
    invented = gsb_rules.invented_tokens(text, original)
    if grounded is not None:
        invented = [t for t in invented if not grounded(t)]
        if invented:
            return "", (f"改写稿里冒出了两侧轨迹里都查不到的文件名或符号：{'、'.join(invented[:4])}")
    elif invented:
        return "", (f"改写稿里冒出了原文没有的文件名或符号：{'、'.join(invented[:4])}，"
                    f"这一步看不到材料，编出来的落点无从查证")
    return text, ""


def _findings_defects(a: dict, b: dict) -> list[str]:
    return (gsb_rules.findings_checks(a, label="a_findings.")
            + gsb_rules.findings_checks(b, label="b_findings."))


def _findings_text(a: dict, b: dict) -> str:
    """把两侧条目拼成一段，只用来比对落点。"""
    return "\n".join(str(t) for d in (a, b) for kind in ("good", "bad")
                     for t in ((d or {}).get(kind) or []))


def build_findings_fix_prompt(a: dict, b: dict, defects: list[str]) -> str:
    """把 findings 的毛病念给模型，让它逐条改写。"""
    listed = "\n".join(f"{i}. {d}" for i, d in enumerate(defects, 1))
    current = json.dumps({"a_findings": a, "b_findings": b}, ensure_ascii=False, indent=1)
    return f"""下面是一份双跑对比里两侧的长处与不足清单，其中若干条违反了写作规范，需要你改写。

【当前内容】
{current}

【必须改掉的地方】
{listed}

【写法要求】
{gsb_rules.WRITING_RULES}

【改写约束】
1. 条目的数量与顺序都不要变，只改写文字。每条仍然只说这一侧的一件事。
2. 只在现有内容的事实范围内改写，不要新增原本没有的事实，不要把一条拆成两条或
   把两条并成一条。
3. 文件名、函数名、命令、报错原文照留，这是定位问题的正常方式，只是不要带行号。
4. 只输出一个 JSON 对象，结构与上面完全一致（顶层只有 a_findings 与 b_findings，
   各自只有 good 与 bad 两个字符串数组）。不要代码块围栏，不要任何说明。"""


async def polish_findings(a: dict, b: dict, *, repos: dict[str, Path] | None = None,
                          purpose: str = "", rounds: int = REASON_FIX_ROUNDS
                          ) -> tuple[dict, dict, list[str]]:
    """把两侧 findings 改到符合写作规范。返回 (a, b, 还没修掉的毛病)。

    两侧一起改，一次调用就够：分开改要两次，而两侧的措辞本来就该统一。
    采信规则和理由那边一样，只在毛病确实减少时才换，改不动就留着并回报；落点也
    照理由那边查，这一轮同样看不到材料，多出来的文件名一律是编的。
    """
    origin = _findings_text(a, b)
    defects = _findings_defects(a, b)
    if not defects:
        return a, b, []

    for rnd in range(1, rounds + 1):
        log.info("%s findings 不合规 %d 处，第 %d 轮改写：%s",
                 purpose or "GSB", len(defects), rnd, "；".join(defects)[:200])
        try:
            r = await llm.ask(build_findings_fix_prompt(a, b, defects),
                              purpose=f"{purpose} findings 改写", attempts=1,
                              timeout_s=REASON_FIX_TIMEOUT_S)
            obj = extract_object(r.text, "a_findings", "findings JSON")
        except (llm.LlmError, ValueError) as exc:
            log.warning("%s findings 改写失败，保留上一版：%s", purpose or "GSB", exc)
            break
        fixed_a = _findings(obj.get("a_findings"), repos)
        fixed_b = _findings(obj.get("b_findings"), repos)
        # 条目数变了说明它没按约束改，拆条并条会让 findings 和证据对不上
        if [len(fixed_a[k]) for k in ("good", "bad")] != [len(a[k]) for k in ("good", "bad")] \
                or [len(fixed_b[k]) for k in ("good", "bad")] != [len(b[k]) for k in ("good", "bad")]:
            log.warning("%s 第 %d 轮改写改动了条目数量，丢弃这一版", purpose or "GSB", rnd)
            continue
        if invented := gsb_rules.invented_tokens(_findings_text(fixed_a, fixed_b), origin):
            log.warning("%s 第 %d 轮 findings 改写冒出了原文没有的落点（%s），丢弃这一版",
                        purpose or "GSB", rnd, "、".join(invented[:4]))
            continue
        left = _findings_defects(fixed_a, fixed_b)
        if len(left) >= len(defects):
            log.warning("%s 第 %d 轮 findings 改写没有减少毛病（%d → %d），丢弃这一版",
                        purpose or "GSB", rnd, len(defects), len(left))
            continue
        a, b, defects = fixed_a, fixed_b, left
        if not defects:
            log.info("%s findings 第 %d 轮改写后合规", purpose or "GSB", rnd)
            return a, b, []
    return a, b, defects


# ---------------- 交付完整性：自查改写与补问 ----------------

def delivery_defects(gsb: dict) -> dict[str, list[str]]:
    """两侧交付完整性各自还有哪些毛病。判的是写好之后的理由和不足清单，所以要放在
    理由与 findings 都改完之后再调。"""
    return {s: gsb_rules.delivery_defects(
                gsb.get(f"{s.lower()}_delivery") or {}, side=s, reason=gsb.get("reason") or "",
                bad_findings=(gsb.get(f"{s.lower()}_findings") or {}).get("bad"))
            for s in config.SIDES}


def build_delivery_fix_prompt(gsb: dict, defects: dict[str, list[str]]) -> str:
    """把两侧交付完整性的毛病念给模型。

    这一轮同样不给材料，只给已经核过的理由和两侧长处与不足清单当事实底本。分数和
    描述对不上时哪个错改哪个，但改分数的依据也只能是这份底本里已经写着的事实。
    """
    current = json.dumps({"a_delivery": gsb.get("a_delivery"), "b_delivery": gsb.get("b_delivery")},
                         ensure_ascii=False, indent=1)
    listed = "\n".join(f"{s} 侧：\n" + "\n".join(f"  {i}. {d}" for i, d in enumerate(ds, 1))
                       for s, ds in defects.items() if ds)
    basis = json.dumps({"a_findings": gsb.get("a_findings"), "b_findings": gsb.get("b_findings")},
                       ensure_ascii=False, indent=1)
    return f"""下面是一份双跑对比里两侧的交付完整性评分与描述，其中有地方违反了规范，需要你改。

【当前内容】
{current}

【必须改掉的地方】
{listed}

【事实底本：已经核对过的对比理由与两侧长处和不足】
<<<REASON
{gsb.get('reason') or ''}
REASON>>>
{basis}

{delivery_section()}

【改写约束】
1. 只在上面事实底本和当前描述的事实范围内改，不要新增任何原本没有的事实、文件名或函数名。
2. 分数和描述对不上时，看事实底本：底本里写着这一侧有交付缺陷，就降分并把扣分点写清；
   底本里这一侧没有交付缺陷，就把描述里无据的缺陷说法删掉。
3. 没被点名的那一侧原样交回，分数和描述一个字都不要动。
4. 只输出一个 JSON 对象，顶层只有 a_delivery 与 b_delivery，各自只有 score（整数）和
   desc（字符串）。不要代码块围栏，不要任何说明。"""


async def polish_delivery(gsb: dict, *, repos: dict[str, Path] | None = None,
                          purpose: str = "", rounds: int = REASON_FIX_ROUNDS
                          ) -> tuple[dict, dict, dict[str, list[str]]]:
    """把两侧交付完整性改到符合规范。返回 (a_delivery, b_delivery, 每侧还没修掉的毛病)。

    按侧采信：一侧改好了、另一侧改坏了的时候只收改好的那一侧，两侧捆在一起要么全收
    要么全丢，会让已经改好的那一侧跟着被丢掉。落点照 findings 那边查，这一轮看不到
    材料，多出来的文件名一律是编的。
    """
    cur = dict(gsb)
    origin = "\n".join([gsb.get("reason") or "", _findings_text(gsb.get("a_findings") or {},
                                                                 gsb.get("b_findings") or {}),
                        *(str((gsb.get(k) or {}).get("desc") or "") for k in ("a_delivery", "b_delivery"))])
    defects = delivery_defects(cur)
    for rnd in range(1, rounds + 1):
        if not any(defects.values()):
            break
        log.info("%s 交付完整性不合规，第 %d 轮改写：%s", purpose or "GSB", rnd,
                 "；".join(d for ds in defects.values() for d in ds)[:200])
        try:
            r = await llm.ask(build_delivery_fix_prompt(cur, defects),
                              purpose=f"{purpose} 交付完整性改写", attempts=1,
                              timeout_s=REASON_FIX_TIMEOUT_S)
            obj = extract_object(r.text, "a_delivery", "交付完整性 JSON")
        except (llm.LlmError, ValueError) as exc:
            log.warning("%s 交付完整性改写失败，保留上一版：%s", purpose or "GSB", exc)
            break
        for s in config.SIDES:
            key = f"{s.lower()}_delivery"
            if not defects[s]:
                continue
            fixed = delivery_of(obj.get(key), repos)
            if invented := gsb_rules.invented_tokens(fixed["desc"], origin):
                log.warning("%s 第 %d 轮 %s 侧交付完整性改写冒出了原文没有的落点（%s），丢弃",
                            purpose or "GSB", rnd, s, "、".join(invented[:4]))
                continue
            trial = {**cur, key: fixed}
            left = delivery_defects(trial)[s]
            if len(left) >= len(defects[s]):
                log.warning("%s 第 %d 轮 %s 侧交付完整性改写没有减少毛病（%d → %d），丢弃",
                            purpose or "GSB", rnd, s, len(defects[s]), len(left))
                continue
            cur[key] = fixed
            defects[s] = left
    return cur.get("a_delivery") or {}, cur.get("b_delivery") or {}, defects


def build_delivery_ask_prompt(prompt_text: str, gsb: dict) -> str:
    """补问交付完整性。材料原样再给一遍，外加已经定稿的结论，只要这两个字段。

    结论要一起给：交付完整性和理由必须讲同一件事，不给它看理由，它会重新判一遍，
    判出来的分数和已经写好的理由很可能对不上。
    """
    done = json.dumps({"verdict": gsb.get("verdict"), "reason": gsb.get("reason"),
                       "a_findings": gsb.get("a_findings"), "b_findings": gsb.get("b_findings")},
                      ensure_ascii=False, indent=1)
    return f"""{prompt_text}

【已经定稿的对比结论】
下面这份对比结论已经写好并核对过，不要改它。你这一次只补两侧的交付完整性评分和描述，
分数与描述要和这份结论里说各侧的话对得上。
{done}

【这一次的输出格式】
只输出一个 JSON 对象，不要任何前后说明，不要代码块围栏：
{{
{DELIVERY_OUTPUT.rstrip(',')}
}}"""


async def ask_delivery(prompt_text: str, gsb: dict, *, repos: dict[str, Path] | None = None,
                       purpose: str = "") -> dict:
    """分析那一次没给全交付完整性时补问一次。返回补好的 {a_delivery, b_delivery}。

    只补缺的那一侧：已经给了的那一侧是和理由同一次生成的，比补问出来的更可信。
    """
    r = await llm.ask(build_delivery_ask_prompt(prompt_text, gsb),
                      purpose=f"{purpose} 交付完整性", attempts=2)
    obj = extract_object(r.text, "a_delivery", "交付完整性 JSON")
    out = {}
    for key in ("a_delivery", "b_delivery"):
        have = gsb.get(key) or {}
        if gsb_rules.parse_score(have.get("score")) is not None and str(have.get("desc") or "").strip():
            out[key] = have
        else:
            out[key] = delivery_of(obj.get(key), repos)
    return out


async def fill_delivery(gsb: dict, prompt_text: str, *, repos: dict[str, Path] | None = None,
                        purpose: str = "") -> tuple[dict, dict[str, list[str]]]:
    """补齐并收口两侧交付完整性。返回 (补好的 gsb, 每侧还没修掉的毛病)。

    补问之后仍然缺字段就让这次分析失败：平台把这两对字段设成了必填，缺一个交上去
    就是字段缺失，而且那时候已经没人会回头看它为什么是空的。
    """
    if not delivery_complete(gsb):
        gsb = {**gsb, **await ask_delivery(prompt_text, gsb, repos=repos, purpose=purpose)}
    if not delivery_complete(gsb):
        raise RuntimeError("分析没给出两侧完整的交付完整性评分与描述，补问一次后仍然缺")
    a, b, left = await polish_delivery(gsb, repos=repos, purpose=purpose)
    return {**gsb, "a_delivery": a, "b_delivery": b}, left


def _require_evidence(task_no: str, kept: list[dict], dropped: list[dict],
                      analysis_dir: Path) -> None:
    """回查结果不达标就让这次分析失败。

    判的是「它给的依据是不是真的」。evidence 是这段理由里唯一能逐字核对的部分，
    材料原文就在证据目录里摆着，一条引用都对不上，说明它没有照着材料写，而是照着
    自己的印象编了一份读起来像样的结论。这种结果必须当场失败，不能落库：它带着
    完整的 verdict 和理由，界面上和一份有据的分析长得一模一样，人分不出来。

    一侧有材料却一条都引不出来，同样不放过。那一侧的判断没有可核对的依据，
    而 GSB 交的是两侧对比，单侧没依据整个结论就站不住。

    丢掉几条不算失败。模型转抄时偶尔会顺手改两个字，那是引用不规范，不是编造；
    这种只记进留痕，让人能翻。
    """
    (analysis_dir / "gsb_evidence_check.json").write_text(
        json.dumps({"kept": kept, "dropped": dropped}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    if dropped:
        log.warning("GSB %s 有 %d 条引用在材料里找不到原文：%s", task_no, len(dropped),
                    "；".join(str(d.get("quote"))[:40] for d in dropped[:3]))
    if not kept:
        raise RuntimeError(
            f"分析给出的 {len(dropped)} 条引用没有一条能在材料原文里找到，"
            f"这份结论没有可核对的依据")
    have = gsb_evidence.sides_with_material(task_no)
    cited = {str(e.get("side") or "").upper()[:1] for e in kept}
    if missing := sorted(have - cited):
        raise RuntimeError(
            f"{'、'.join(missing)} 侧有材料，但分析没给出一条能对上原文的引用，"
            f"这一侧的判断没有依据")


def peer_openings(db, task_id: int) -> dict[str, str]:
    """别的已分析题目的开头句式，用来发现几道题套同一个开场。

    已分析的题本来就不多，全取出来也就几十条，不值得为此加索引或缓存。
    """
    return {other.task_no: gsb_rules.opening_signature((other.gsb or {}).get("reason", ""))
            for other in db.query(Task).filter(Task.id != task_id,
                                               Task.analysis_status == ANALYSIS_DONE).all()}


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
        # 重新分析会整段换掉理由，两道提交前质检的结论对新的这一段都不再成立。
        # 留着它们，一道重新分析过的题会带着旧的「质检通过」直接可提交 —— 事实核验
        # 那一档尤其不能留，它对的是上一稿理由，而理由马上要被整段换掉。
        t.factcheck_status = FACTCHECK_IDLE
        t.factcheck = {}
        t.precheck_status = PRECHECK_IDLE
        t.precheck = {}
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
            evidence_dir = gsb_evidence.build(task_no, t.user_prompt, materials)

        analysis_dir.mkdir(parents=True, exist_ok=True)
        (analysis_dir / "gsb_prompt.md").write_text(prompt_text, encoding="utf-8")
        # 执行记录单独落一份。事实核验那一步要拿它去对理由里的断言，而它必须和分析
        # 当时看到的是同一份 —— 现算一遍的话，中间要是重跑过一侧，核验就在拿新轨迹
        # 判旧理由，报出来的「不符」全是假的。
        (analysis_dir / "gsb_facts.json").write_text(
            json.dumps({s: materials[s].get("facts") or {} for s in config.SIDES},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        log.info("GSB %s prompt %d 字符，材料副本在 %s，开始调用模型",
                 task_no, len(prompt_text), evidence_dir)

        # 工作目录仍然用空的 ASK_DIR，不指向证据目录：材料是随 prompt 一起送进去的，
        # 判断该基于哪一份必须由我们决定，而不是看模型愿不愿意去读文件。证据目录
        # 只作原文留底，供下面的逐字回查和事后翻查用。
        result = await llm.ask(prompt_text, purpose=f"GSB {task_no}", attempts=2)
        (analysis_dir / "gsb_raw.txt").write_text(result.text, encoding="utf-8")

        parsed = extract_json(result.text)
        parsed["evidence"], dropped = gsb_evidence.check_quotes(
            task_no, parsed.get("evidence") or [])
        _require_evidence(task_no, parsed["evidence"], dropped, analysis_dir)

        workspaces = {s: config.TaskPaths(task_no, s).workspace for s in config.SIDES}
        gsb = normalize(parsed, workspaces)
        if not gsb["verdict"]:
            raise RuntimeError(f"分析没给出可识别的结论，原始值：{str(parsed.get('verdict'))[:80]}")

        with session() as db:
            peers = peer_openings(db, task_id)
        gsb["reason"], left = await polish_reason(
            gsb["reason"], verdict=gsb["verdict"], peer_openings=peers,
            repos=workspaces, purpose=f"GSB {task_no}")
        gsb["a_findings"], gsb["b_findings"], findings_left = await polish_findings(
            gsb["a_findings"], gsb["b_findings"],
            repos=workspaces, purpose=f"GSB {task_no}")
        # 交付完整性放在理由和 findings 改完之后收口：「满分却在理由里写了交付问题」
        # 要拿定稿的理由去判，拿改之前那一稿判，改完可能又对不上了。
        gsb, delivery_left = await fill_delivery(gsb, prompt_text, repos=workspaces,
                                                 purpose=f"GSB {task_no}")

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
                # 改写之后还剩的毛病要留痕。留空说明生成时已经收干净，非空就是
                # 改了两轮还没改动的地方，界面上的核验会用同一份规则再报一次
                "reason_defects": left,
                "findings_defects": findings_left,
                "delivery_defects": delivery_left,
                # 回查丢掉的引用。留空说明每一条都在材料里对上了原文，非空就是
                # 它转抄时改了字，界面上能翻出来是哪几句
                "evidence_dropped": dropped,
                "raw": parsed,
            }
            t.gsb = gsb
            t.analysis_status = ANALYSIS_DONE
            t.status = ANALYZED
            # 重新分析的题录屏可能早就录完了，那它该直接落回质检栏而不是待录屏栏。
            # gsb_precheck 反过来要用这个模块的 JSON 提取和清洗，所以在这里延迟导入，
            # 和下面的 gsb_verifier 一样。
            from app.services import gsb_precheck

            gsb_precheck.sync_stage(db, t)
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


async def backfill_delivery(task_id: int) -> dict:
    """给交付完整性字段上线之前就分析完的题补上这两对字段，不重跑整次分析。

    材料照分析那样重新取齐、prompt 照原样组，再附上已经定稿的结论只问这两个字段——
    重跑整次分析会把已经过了两道质检的理由整段换掉。补完不动理由，所以理由那一档的
    质检结论不作废；两道质检记着的交付完整性指纹对不上，会自己把这道题放回质检队列，
    交付完整性那部分在那里过一遍轨迹核对和措辞质检。
    """
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "message": "任务不存在"}
        if t.status not in (ANALYZED, QC):
            return {"ok": False, "message": f"状态 {t.status} 不能补交付完整性"}
        gsb = dict(t.gsb or {})
        if not str(gsb.get("reason") or "").strip():
            return {"ok": False, "message": "还没有理由正文，先跑 GSB 分析"}
        runs = {r.side: r for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()}
        if set(runs) != set(config.SIDES):
            return {"ok": False, "message": f"两侧的运行记录不全，只有 {sorted(runs) or '空'}"}
        task_no = t.task_no
        snapshot = gsb_repo.snapshot_sha(t.env_snapshot)
        materials = {s: await collect_side(task_no, s, runs[s], snapshot) for s in config.SIDES}
        prompt_text = build_prompt(t, materials)

    workspaces = {s: config.TaskPaths(task_no, s).workspace for s in config.SIDES}
    try:
        filled, left = await fill_delivery(gsb, prompt_text, repos=workspaces,
                                           purpose=f"GSB {task_no}")
    except (llm.LlmError, ValueError, RuntimeError) as exc:
        log.warning("题 %s 补交付完整性失败：%s", task_no, exc)
        return {"ok": False, "message": f"补交付完整性失败：{exc}"}

    from app.services import gsb_precheck

    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "message": "任务不存在"}
        cur = dict(t.gsb or {})
        cur["a_delivery"], cur["b_delivery"] = filled["a_delivery"], filled["b_delivery"]
        t.gsb = cur
        # 两道质检的结论只对理由负过责，交付完整性从没被核过。把交付指纹显式记成空串，
        # 它们就和刚补上的这一对对不上，自己回到质检队列；理由指纹不动，理由那一段沿用。
        for attr in ("factcheck", "precheck"):
            report = dict(getattr(t, attr) or {})
            if report.get("reason_digest"):
                report["delivery_digest"] = ""
                setattr(t, attr, report)
        analysis = dict(t.analysis or {})
        analysis["delivery_defects"] = left
        analysis["delivery_backfilled_at"] = utc_now().isoformat()
        t.analysis = analysis
        gsb_precheck.sync_stage(db, t)

    from app.services import gsb_verifier

    await gsb_verifier.run_verify(task_id)
    bus.publish("tasks", {"type": "task", "id": task_id})
    a, b = filled["a_delivery"], filled["b_delivery"]
    return {"ok": True, "message": f"已补上交付完整性：A {a['score']} 分，B {b['score']} 分",
            "a_delivery": a, "b_delivery": b}
