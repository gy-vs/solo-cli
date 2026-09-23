"""事实核验：拿轨迹里的执行记录去对 GSB 理由，对不上的就地改掉。

和旁边两道的分工要分清。gsb_verifier 查的是确定性格式——字数、步号、行号、markdown，
正则能判的都在那边；gsb_precheck 查的是措辞读起来像不像人写的；这一道查的是**说的
是不是真的**。三者互不覆盖：「B 侧改完之后没有再跑过测试」这句话字数合规、没有步号、
读起来也完全像人话，前两道一路放行，可轨迹里明明白白摆着改完之后跑通的那条命令。

这类错的根子在分析那一步：模型拿到一份看着有问题的 diff，就顺手推断「所以它跑不
起来」「所以没验证过」，而它手上根本没有执行结果。分析那边已经把执行记录塞进 prompt
并立了红线，但红线是劝，劝不住的那部分要在这里兜住——生成和核验必须是两次独立的
调用，让同一个模型在同一次里既写又自查，它只会重复自己刚才的判断。

这一步直接改，不只报错。人要的是最终结果，不是一份「第三段第二句有问题，你自己改」
的清单——那等于把核对位置、重写、再核对一遍全丢回给人，而这三件事模型做得比人准。
改完必须留痕：哪一处原文、轨迹里的事实是什么、改成了什么，三样都记进报告，人扫一眼
就知道动过哪里，不必拿改前改后两稿去逐字对。

采信规则借 gsb_analyzer.vet_rewrite，和口语化质检共用一把尺子。改写稿过不了关就再问
一次，把过不了关的原因一并告诉模型（FIX_ROUNDS）；连着几轮都交不出能用的稿子才判
待人工——那时候留给人的至少是一份说清了「哪里不符、轨迹里是什么」的报告。

「对得上轨迹」是按侧对的，不是按两侧并集对的。说 A 的事要在 A 的轨迹里找得到，说 B
的事要在 B 的轨迹里找得到；把 B 的 removeNode 写成 A 的做法，这个词在「轨迹里」确实
有，可它不在 A 的轨迹里，这就是不符。这一类程序能逐字判的交给 gsb_attribution，判
出来的硬项不经模型点头：模型说没问题也照样算不符，改写稿里还留着也照样不采信。
程序判不了的（过程里做过的事、做法归属、侧别从上下文推断的句子）交给模型，prompt 里
给它两侧各自的过程记录和一张落点归属表，逐条对。
"""

from __future__ import annotations

import json
import logging
import re
import time

from app import config
from app.db import session
from app.events import bus
from app.models import (
    ANALYZED, FACTCHECK_CONFIRMED, FACTCHECK_ERROR, FACTCHECK_FAIL, FACTCHECK_IDLE,
    FACTCHECK_OK, FACTCHECK_PASS, FACTCHECK_RUNNING, PRECHECK_IDLE, QC, Task, utc_now,
)
from app.services import gsb_analyzer, gsb_attribution, gsb_rules, llm

log = logging.getLogger("gsb_factcheck")

# 报告里带这个标记，才说明这份结论是按侧核过的。在这之前的 PASS 只对过执行结果，
# 张冠李戴的句子照样能拿到 PASS，所以老结论一律不作数，要按新口径重核。
ATTRIBUTION_VERSION = 1

# 核验的 prompt 是一段理由加两侧执行记录，比 GSB 分析小一个量级，正常一两分钟就回。
FACTCHECK_TIMEOUT_S = 900
# 改写稿被判不能用时再问几轮。两轮足够：第一轮多半是篇幅或红项，把原因说给它就改对了；
# 连着两轮都交不出能用的稿子，多半是这段理由本身要重写，那是人该看一眼的事。
FIX_ROUNDS = 2
# 一段理由里真正与轨迹矛盾的断言通常一两处，多的三四处。给上限是防模型逐句开条目，
# 把「这句话说得不够具体」也算成事实不符。
MAX_MISMATCHES = 10


# ---------------- 本地先摘一遍可疑断言 ----------------
# 这不是独立判定：报不报、怎么改全由模型说了算，本地只把可疑的句子摘出来放进 prompt。
# 摘的是两类「说某件事没发生」的断言，因为这两类恰恰是执行记录能一票否决的——
# 记录里摆着跑通的命令，「没跑过测试」就站不住；记录里摆着完整的收尾，「戛然而止」
# 就站不住。反过来「某处实现得不全」这种对产物的判断，执行记录反驳不了，不摘。

_SENT = re.compile(r"[^。！？\n]+[。！？]?")
_SIDE_TOK = re.compile(r"(?<![A-Za-z])([AB])(?![A-Za-z])")

# 「整套都没跑过」一类。必须落在整体上：说「某条用例没核对到某个行为」是对覆盖面的
# 评价，轨迹里跑过测试并不能反驳它，不加限定这类句子会被整批误摘。
NO_RUN = re.compile(
    r"(没有|未|不曾|再没|没再|一[次条组套]都没|一[次条组套]也没)[^，。；]{0,18}"
    r"(完整(?:地)?(?:跑|运行|执行)|完整回归|全量|套件|回归的?记录"
    r"|(?:跑|运行|执行)[^，。；]{0,4}回归|测试记录|构建或测试|通过的(?:记录|检查|结果)"
    r"|再运行过|再跑|走绿|跑起来|跑过|跑绿|执行过|运行过|验证过|验证)")
# 「戛然而止」一类
NO_END = re.compile(r"戛然而止|戛然|未报错.{0,6}中断|无报错中止|直接结束|没有收尾"
                    r"|没有任何后续|未见后续|之后没有(?:任何)?(?:后续|动作)|中途放弃")
# 「跑不起来 / 编译不过」一类。这一类最危险：它断言的是一个执行结果，而只要执行记录
# 里没有对应的失败命令，这句话就是从 diff 推出来的。
CANT_RUN = re.compile(r"(?:跑|运行|启动|构建|编译|安装)不(?:起来|了|过|成功|通过)"
                      r"|无法(?:运行|启动|构建|编译|加载|导入)"
                      r"|(?:构建|编译|启动|运行|导入)(?:就)?(?:会|将|必然|直接)?(?:失败|报错|出错|中断)"
                      r"|根本跑不|压根跑不|一跑就(?:错|崩|挂)")


def _side_of(sentence: str, carry: str) -> str:
    """这句话说的是哪一侧。只提到一侧就认它，两侧都提到或都没提到就沿用上一句。

    代词句（「它」「这一侧」）本来就不带 A/B，侧别只能从上一句继承，否则整类
    断言会漏掉。猜错了不要紧：摘出来只是给模型的提示，最终归到哪一侧由它按
    原文判，prompt 里也写明了这一点。
    """
    sides = set(_SIDE_TOK.findall(sentence))
    if len(sides) == 1:
        return sides.pop()
    return "" if len(sides) > 1 else carry


def _has_passing_check(facts: dict, *, after_edit_only: bool = False) -> bool:
    return any(c.get("ok") and (c.get("after_last_edit") or not after_edit_only)
               for c in (facts or {}).get("checks") or [])


def _has_failing_check(facts: dict) -> bool:
    return any(not c.get("ok") for c in (facts or {}).get("checks") or []) \
        or bool((facts or {}).get("failures"))


def _ended_properly(facts: dict) -> bool:
    """收尾像不像跑完了。

    只看有没有留下一段像样的总结。长度门槛是为了把「好的」「已修改」这种一句话
    排除掉——那种收尾说明不了这一侧跑完没跑完。
    """
    return len((facts or {}).get("ending") or "") > 200


def suspects(reason: str, facts: dict[str, dict]) -> list[dict]:
    """本地摘出的可疑断言。返回 [{"quote", "side", "why"}]。

    只在「断言」和「记录」确实对冲时才摘。说「没跑过测试」而这一侧压根没有执行
    记录，那句话是对的，摘出来只会让模型去改一句没问题的话。
    """
    out: list[dict] = []
    seen: set[str] = set()
    for para in (reason or "").split("\n"):
        carry = ""
        for raw in _SENT.findall(para):
            sent = raw.strip()
            if not sent:
                continue
            carry = side = _side_of(sent, carry)
            if not side:
                continue
            f = facts.get(side) or {}
            if not f.get("steps_total"):
                continue
            why = ""
            if NO_RUN.search(sent) and _has_passing_check(f, after_edit_only=True):
                why = "这一侧最后一次改代码之后跑过校验命令并且成功了"
            elif NO_END.search(sent) and _ended_properly(f):
                why = "这一侧最后留下了完整的收尾总结，不像中途停下"
            elif CANT_RUN.search(sent) and not _has_failing_check(f):
                why = ("执行记录里没有任何失败的命令或报错，"
                       "「跑不起来」这个结论没有执行层面的依据")
            if why and sent not in seen:
                seen.add(sent)
                out.append({"quote": sent[:200], "side": side, "why": why})
    return out[:MAX_MISMATCHES]


# ---------------- 材料 ----------------

def load_facts(task_no: str) -> dict[str, dict]:
    """取这道题两侧的执行记录。

    优先读分析当时落下的那一份。现算一遍看着更省事，但中间要是重跑过某一侧，
    算出来的就是新轨迹，拿它去判旧理由，报出来的「不符」全是假的。
    落盘那份不在（老题、或者分析是旧版本跑的）才回退到现算。
    """
    path = config.TaskPaths(task_no).analysis / "gsb_facts.json"
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(saved, dict) and any(saved.get(s) for s in config.SIDES):
                return {s: saved.get(s) or {} for s in config.SIDES}
        except (OSError, json.JSONDecodeError):
            pass
    return {s: gsb_analyzer.run_facts(gsb_analyzer._load_trace_index(task_no, s))
            for s in config.SIDES}


def load_corpora(task_no: str) -> dict[str, str]:
    """两侧各自的轨迹全文，按侧核对落点用。"""
    return gsb_attribution.load_corpora(task_no)


def load_process(task_no: str) -> dict[str, dict]:
    """两侧各自的过程：改过哪些文件、按顺序做了什么。

    判「这件事是哪一侧做的」要看过程，执行记录只有命令和结果，写临时脚本、补用例、
    对照上游实现这类事它不记。压缩口径和分析那边一致，一行一步。
    """
    out: dict[str, dict] = {}
    for s in config.SIDES:
        index = gsb_analyzer._load_trace_index(task_no, s)
        edited: list[str] = []
        for step in index.get("steps") or []:
            if step.get("tool") in gsb_analyzer.SRC_EDIT_TOOLS:
                for f in step.get("files") or []:
                    if isinstance(f, str) and f.strip() and f.strip() not in edited:
                        edited.append(f.strip())
        out[s] = {"steps": gsb_analyzer._condense_steps(index), "edited": edited[:60]}
    return out


def _facts_text(facts: dict[str, dict]) -> str:
    return "\n\n".join(f"=== {s} 侧的实际执行记录 ===\n{gsb_analyzer.facts_block(facts.get(s) or {})}"
                       for s in config.SIDES)


def _process_text(process: dict[str, dict]) -> str:
    blocks = []
    for s in config.SIDES:
        p = process.get(s) or {}
        edited = "\n".join(f"  {f}" for f in p.get("edited") or []) or "  （没有改过文件）"
        steps = "\n".join(f"  {x}" for x in p.get("steps") or []) or "  （没有轨迹）"
        blocks.append(f"=== {s} 侧的过程记录（只属于 {s} 侧）===\n"
                      f"改过的文件：\n{edited}\n按先后顺序做了什么：\n{steps}")
    return "\n\n".join(blocks)


# ---------------- prompt ----------------

def build_prompt(reason: str, facts: dict[str, dict], *, verdict: str = "",
                 task_no: str = "", retry_note: str = "",
                 corpora: dict[str, str] | None = None,
                 process: dict[str, dict] | None = None) -> str:
    corpora = corpora or {}
    found = suspects(reason, facts)
    listed = "\n".join(f"  {i}. [{h['side']} 侧] 「{h['quote']}」\n     对不上的地方：{h['why']}"
                       for i, h in enumerate(found, 1))
    hint_block = (f"""
【本地先摘出来的可疑断言（执行结果类）】
下面这几句我这边按规则先摘了出来，侧别是猜的，可能猜反，你按原文自己判。
不一定都算问题，但每一条都要给出判断；漏在外面的也要报。
{listed}
""".rstrip() if found else "")

    attr = gsb_attribution.check(reason, corpora) if any(corpora.values()) else []
    hard = [h for h in attr if h["level"] == gsb_attribution.HARD]
    soft = [h for h in attr if h["level"] != gsb_attribution.HARD]
    hard_block = ("\n【程序按侧逐字查出来的不符（必须改，不许判成没问题）】\n"
                  "下面这几处是拿正文里的名字回到那一侧自己的轨迹全文里逐字查的，查不到就是查不到。"
                  "它们一定要出现在 mismatches 里，改写稿里也不许再留着：\n"
                  + "\n".join(f"  {i}. 「{h['quote']}」\n     {h['why']}"
                              for i, h in enumerate(hard, 1))) if hard else ""
    soft_block = ("\n【侧别需要你判的落点】\n"
                  "下面这几处的侧别是从上下文推断的，程序不下结论。按原文判它到底说的是哪一侧，"
                  "说的那一侧轨迹里没有就算不符；每一条都要给出判断：\n"
                  + "\n".join(f"  {i}. 「{h['quote']}」\n     {h['why']}"
                              for i, h in enumerate(soft, 1))) if soft else ""
    table_block = (f"\n【落点归属表】\n正文里每个文件名、代码符号分别在哪一侧的轨迹里出现过"
                   f"（逐字查的两侧轨迹全文）：\n{gsb_attribution.table(reason, corpora)}"
                   if any(corpora.values()) else "")
    process_block = f"\n\n{_process_text(process)}" if process else ""

    lo, hi = gsb_rules.REASON_TARGET_MIN, gsb_rules.REASON_TARGET_MAX
    retry_block = f"""
【上一版改写稿没被采用】
{retry_note}
这一轮要在改掉事实问题的同时避开上面这个毛病。
""".rstrip() if retry_note else ""

    return f"""你在核对一份双跑对比的评审理由，看它写的事实和两侧的实际运行轨迹对不对得上。
这段话马上要交给评审方，写错的事实会算到对方头上。

【你唯一的事实来源】
下面的材料全部摘自两侧各自的运行轨迹，是这两次跑真实发生过的事。A 的材料只能证明
A 做过什么，B 的材料只能证明 B 做过什么，两侧不能互相作证。
- 执行记录：判断「跑没跑起来、编译过没过、测试过没过、报了什么错」只能依据它。
- 过程记录：判断「这件事是哪一侧做的、改的是哪一侧的哪个文件」依据它。
- 落点归属表：正文里每个名字在哪一侧的轨迹里真实出现过，是程序逐字查的。
记录里没有的，就是没有依据；不要自己去推，也不要凭代码改动的样子想象运行结果。

{_facts_text(facts)}{process_block}

【待核对的正文】
题号 {task_no or '—'}，结论是 {verdict or '未给出'}。
<<<REASON
{reason}
REASON>>>
{table_block}
{hard_block}
{soft_block}
{hint_block}
{retry_block}

【核对什么】
逐句读正文，两类断言都要对。

一、侧别对应：说 A 的就要对得上 A 的轨迹，说 B 的就要对得上 B 的轨迹。
正文里挂在某一侧名下的每一件具体的事，都必须在**那一侧自己**的轨迹里找得到：
函数名、文件名、类名、用到的做法，以及过程中做过的事（写过临时脚本、补过用例、
发现并修过某个缺陷、对照过某个实现、跑了多少条测试）。命中下面任何一条就算不符：
1. 张冠李戴：把一侧的函数名、文件名、做法写到了另一侧名下。例如 removeNode 只在 B
   的轨迹里出现，正文却说「A 依据 removeNode 的返回值更新 size」——哪怕 A 确实用了
   同样的思路，它用的名字叫 deleteNode，这句话也是错的。
2. 把一侧过程中发生的事写到了另一侧名下，或者把两侧的事揉进一句、记在同一侧头上。
3. 正文里的名字或事件，两侧的轨迹里都找不到。
4. 侧别含糊：一句话只点了一侧，里面说的却是另一侧的东西，读的人会记到点名的那一侧
   头上。这也算不符，改的时候把侧别写明。
「这个名字在轨迹里确实有」不等于对上了。它得在正文说的那一侧的轨迹里有才算。

二、执行结果：跑没跑起来、构建编译过没过、测试跑没跑过、跑出了什么结果、报了什么错、
是不是中途停下了。命中下面任何一条就算不符：
5. 说某一侧没跑过测试 / 没有验证，而执行记录里它改完代码之后跑过校验命令且成功了。
6. 说某一侧戛然而止 / 中途放弃，而执行记录里它留下了完整的收尾总结。
7. 说某一侧跑不起来 / 编译不过 / 构建失败，而执行记录里没有对应的失败命令或报错。
   这一条最常见：它是从代码改动的样子推出来的，不是看出来的。
8. 说跑出了某个结果、报了某个错，而执行记录里找不到这条输出。
9. 反过来，执行记录里明明有失败的命令，正文却说这一侧验证充分。

不算不符的，一条都不要报：
- 对产物好坏的判断本身（需求点没实现、接口改坏了、边界没处理、用例写得不全）。
  这些看代码就能定，不归你管。但这个判断挂在哪一侧名下、用的名字对不对，归你管。
- 措辞生硬、篇幅、结论判给谁。那是另外两道在管的事。
- 正文说得比记录更概括。「跑过一轮验证」对应记录里的具体命令，这是正常的写法。

【改法】
只要报了不符，就必须交出改好之后的**整段**正文，直接可以替换原文：
- 张冠李戴的，按那一侧自己轨迹里的真实情况改：名字换成那一侧实际用的名字（在落点
  归属表和过程记录里查），或者把主语改回真正做这件事的那一侧。两侧都查不到的，删掉。
- 侧别含糊的，把侧别写明，例如「B 的 resolveTypeUrl 只取第一个斜杠」。
- 断言和执行记录反着的，按记录改。记录说改完跑通了，就写成跑通了，不要含糊成「验证不够」。
- 断言没有依据（推出来的），把这句话删掉或者降回它真正有依据的说法。
  例如「所以它跑不起来」，如果只是代码上看着有问题，就写成「代码上看这里会出问题」，
  不要保留任何关于运行结果的断言。
- 只动有问题的那几句，别的句子逐字保留。这一步不是重写，是订正。
- 不要新增任何原文和两侧轨迹里都没有的事实。换进来的名字必须在对应那一侧的轨迹里查得到。
- 结论不许变。原文判 A 更好，改完也必须落在 A 更好。
- 改完保持在 {lo} 到 {hi} 字。删掉一句之后短了，就把原文已经点到、但没讲透的判断依据
  补足，不要靠加新论点凑字数。
- 不要 markdown 记号、不要步号、不要绝对路径、不要表情符号。分成两到四个自然段。

【输出格式】
只输出一个 JSON 对象，不要任何前后说明，不要代码块围栏：
{{
  "verdict": "ok" 或 "fix",
  "summary": "一句话总体判断，二十到五十字",
  "mismatches": [
    {{"quote": "原文片段，逐字照抄，不要改写",
      "side": "正文把这件事记在哪一侧名下：A 或 B",
      "type": "侧别" 或 "执行结果",
      "claim": "这句话断言了什么",
      "fact": "轨迹里实际是什么：哪一侧的哪条命令、哪段输出、哪个文件里的哪个名字",
      "fix": "这一处改成了什么"}}
  ],
  "rewrite": "订正后的整段正文，没有问题时留空串"
}}
quote 必须能在正文里逐字找到，找不到的条目人没法对位置，会被丢掉。"""


# ---------------- 解析与采信 ----------------

def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def normalize(obj: dict, *, reason: str) -> dict:
    """把模型输出洗成可入库的核验报告。

    quote 对不上正文的整条丢掉。模型偶尔会把自己改写后的句子填进 quote，那种条目
    人拿着没法用：他按 quote 回正文里找位置，找不到，于是不知道动的是哪一句。
    """
    body = _squash(reason)
    items: list[dict] = []
    dropped = 0
    for raw in (obj.get("mismatches") or []):
        if not isinstance(raw, dict):
            continue
        quote = gsb_analyzer._clean(raw.get("quote"))
        if not quote or _squash(quote) not in body:
            dropped += 1
            continue
        side = str(raw.get("side") or "").upper()[:1]
        kind = gsb_analyzer._clean(raw.get("type"))
        items.append({
            "quote": quote[:300],
            "side": side if side in config.SIDES else "",
            "type": kind if kind in ("侧别", "执行结果") else "",
            "claim": gsb_analyzer._clean(raw.get("claim"))[:300],
            "fact": gsb_analyzer._clean(raw.get("fact"))[:400],
            "fix": gsb_analyzer._clean(raw.get("fix"))[:400],
        })
        if len(items) >= MAX_MISMATCHES:
            break
    return {"mismatches": items, "quote_dropped": dropped,
            "summary": gsb_analyzer._clean(obj.get("summary"))[:300]}


def merge_local(mismatches: list[dict], hard: list[dict]) -> list[dict]:
    """把程序判出的侧别硬项并进模型报的不符里。

    模型漏报的照样算数：这些是按侧逐字查出来的，不是推断。模型已经报过同一句的就
    不重复开条目，免得同一处在报告里出现两次、人以为有两处要改。
    """
    out = list(mismatches)
    for h in hard:
        q = _squash(h["quote"])
        if any(_squash(m["quote"]) in q or q in _squash(m["quote"]) for m in out):
            continue
        out.append({"quote": h["quote"], "side": h["side"], "type": "侧别",
                    "claim": f"把 {h['ref']} 记在了 {h['side'] or '未标明的一'} 侧名下"
                    if h["kind"] == gsb_attribution.CROSS else f"提到了 {h['ref']}",
                    "fact": h["why"], "fix": "", "source": "local"})
    return out[:MAX_MISMATCHES]


def vet(rewrite: str, original: str, verdict: str,
        corpora: dict[str, str]) -> tuple[str, str]:
    """事实核验这一步的改写稿采信。在通用那把尺子上多两条：

    - 换进来的名字只要在任一侧的轨迹里查得到，就不算编造。订正张冠李戴，往往就是把
      removeNode 换成 A 自己的 deleteNode，而通用尺子拦的正是「原文没有的符号」，
      不放开这一条，串侧的句子就只能删不能改。
    - 改完之后按侧再查一遍，还有硬项就不采信。换对了名字却把主语换错，是同一种错。
    """
    fixed, why = gsb_analyzer.vet_rewrite(
        rewrite, original, verdict,
        grounded=(lambda t: gsb_attribution.grounded(t, corpora)) if any(corpora.values()) else None)
    if not fixed:
        return "", why
    if left := gsb_attribution.hard(fixed, corpora):
        return "", ("改写稿里仍有侧别对不上轨迹的地方：" +
                    "；".join(f"「{h['quote'][:60]}」{h['why']}" for h in left[:3]))
    return fixed, ""


def notes_for(mismatches: list[dict], reason: str, *, applied: bool = True) -> list[str]:
    """把每一处订正折成一句人话，放进报告里给人看。

    这是这一步对外交付的东西之一。只给一段改好的正文，人没法知道动过哪里，
    要么全信，要么拿改前改后两稿逐字对——两个都不是他该干的活。所以每一处都写清
    三样：原文哪一句、轨迹里其实是什么、改成了什么。

    附上段落序号而不是字符位置：人是在界面上读这段话的，「第二段」他找得到，
    「第 418 个字符」他找不到。
    """
    paras = [p for p in (reason or "").split("\n") if p.strip()]
    out: list[str] = []
    for i, m in enumerate(mismatches, 1):
        loc = next((f"第 {j} 段" for j, p in enumerate(paras, 1)
                    if _squash(m["quote"]) in _squash(p)), "正文")
        side = f"{m['side']} 侧" if m.get("side") else "未标明侧别"
        kind = "侧别对不上" if m.get("type") == "侧别" else "与轨迹不符"
        if applied:
            tail = f"已改为：{m.get('fix') or '见订正后的正文'}"
        else:
            tail = (f"建议改为：{m['fix']}" if m.get("fix")
                    else "需要按那一侧自己的轨迹改掉，或者把侧别写明")
        out.append(f"第 {i} 处（{loc}，{side}）：原文「{m['quote']}」{kind}。"
                   f"轨迹里实际是：{m['fact']}。{tail}")
    return out


# ---------------- 交付完整性 ----------------
# 和理由走同一道核验、同一份事实来源，但单独问一次：理由那份 prompt 是按「两侧对比」
# 调出来的，把单侧打分的核对塞进去，两类判断会互相串味。理由先核、交付完整性后核，
# 后者拿的是核过的那一稿理由——「满分却在理由里写了交付问题」要对着定稿去判。
#
# 这里核的是两件事：描述里的事实对不对得上这一侧的轨迹，分数和描述、和理由对不对得上。
# 代码本身写得好不好这一步看不到，不归它管；但过程记录能直接反驳的（说某个文件没改，
# 过程里明明改过）照样算不符。

DELIVERY_TYPES = ("执行结果", "侧别", "虚假成功", "分数")


def delivery_sides(gsb: dict) -> list[str]:
    """有交付完整性可核的侧。老题没有这对字段，整段跳过。"""
    return [s for s in config.SIDES
            if str(((gsb or {}).get(f"{s.lower()}_delivery") or {}).get("desc") or "").strip()]


def _delivery(gsb: dict, side: str) -> dict:
    return dict((gsb or {}).get(f"{side.lower()}_delivery") or {})


def delivery_suspects(desc: str, side: str, facts: dict[str, dict]) -> list[dict]:
    """描述里和执行记录对冲的断言。借理由那套摘法，句首补上侧别让它认得出是哪一侧。"""
    prefix = f"{side} 侧："
    return [{**h, "quote": h["quote"].removeprefix(prefix)}
            for h in suspects(prefix + (desc or ""), {side: facts.get(side) or {}})]


def build_delivery_prompt(gsb: dict, facts: dict[str, dict], *, sides: list[str],
                          task_no: str = "", corpora: dict[str, str] | None = None,
                          process: dict[str, dict] | None = None, retry_note: str = "") -> str:
    corpora = corpora or {}
    blocks = []
    for s in sides:
        d = _delivery(gsb, s)
        desc = str(d.get("desc") or "")
        local = [h for h in gsb_attribution.side_check(desc, s, corpora)]
        hard = [h for h in local if h["level"] == gsb_attribution.HARD]
        soft = [h for h in local if h["level"] != gsb_attribution.HARD]
        sus = delivery_suspects(desc, s, facts)
        extra = ""
        if hard:
            extra += ("\n  程序按侧逐字查出来的不符（必须改，不许判成没问题）：\n"
                      + "\n".join(f"    「{h['quote']}」{h['why']}" for h in hard))
        if soft:
            extra += ("\n  需要你判的落点：\n"
                      + "\n".join(f"    「{h['quote']}」{h['why']}" for h in soft))
        if sus:
            extra += ("\n  本地先摘出来的可疑断言（执行结果类，不一定都算问题，每条都要给判断）：\n"
                      + "\n".join(f"    「{h['quote']}」对不上的地方：{h['why']}" for h in sus))
        blocks.append(f"=== {s} 侧：{d.get('score')} 分 ===\n<<<DELIVERY-{s}\n{desc}\nDELIVERY-{s}>>>{extra}")

    process_block = f"\n\n{_process_text(process)}" if process else ""
    retry_block = f"""
【上一版订正稿没被采用】
{retry_note}
这一轮要在改掉事实问题的同时避开上面这个毛病。
""".rstrip() if retry_note else ""
    fields = ",\n".join(
        f'  "{s}": {{"verdict": "ok" 或 "fix", "problems": [{{"quote": "描述原文片段，逐字照抄；'
        f'分数问题可以留空串", "type": "{"」或「".join(DELIVERY_TYPES)}", "claim": "描述或分数断言了什么", '
        f'"fact": "轨迹里实际是什么：哪条命令、哪段输出、改过哪个文件、理由里哪句话"}}], '
        f'"score": 订正后的分数（没有问题时照填原分）, "desc": "订正后的整段描述，没有问题时留空串"}}'
        for s in sides)

    return f"""你在核对一份双跑对比里的交付完整性评分与描述，看它们和各自那一侧的实际运行轨迹对不对得上。
这两个字段马上要随对比结论一起交给评审方，打错的分、写错的事实会算到对方头上。

【你唯一的事实来源】
下面的材料全部摘自两侧各自的运行轨迹。A 的材料只能证明 A 做过什么，B 的材料只能证明
B 做过什么，两侧不能互相作证。记录里没有的，就是没有依据；不要自己去推，也不要凭想象
补运行结果。

{_facts_text(facts)}{process_block}

【已经核对过的对比理由】
这段已经对过轨迹，只当参照，不要核它也不要改它。它是判「满分合不合理」的依据之一。
<<<REASON
{gsb.get('reason') or ''}
REASON>>>

【待核对的交付完整性】
题号 {task_no or '—'}。
{chr(10).join(blocks)}
{retry_block}

【评分表】
{gsb_rules.DELIVERY_RUBRIC}

【核对什么】
一、描述里的事实
1. 描述只说它自己那一侧。里面的文件名、函数名、做过的事，都必须在这一侧自己的轨迹里
   找得到；只在另一侧出现、或者两侧都找不到的，算不符。
2. 执行结果：说这一侧没跑过测试、没有验证，而它改完代码之后跑过校验且成功了；说它跑
   不起来、编译不过，而执行记录里没有对应的失败命令；说跑出了某个结果、报了某个错，而
   执行记录里找不到这条输出——都算不符。
3. 虚假成功：描述说「宣称改了 X、实际没改」，要对照这一侧的改过的文件和最后说的话；
   反过来，这一侧收尾时宣称改过的文件在改过的文件清单里找不到，描述却没写、分数也没
   因此扣，同样算不符。
二、分数
4. 分数要落在评分表对应的档位上：描述写到的缺陷有多重，分数就是多少，打了 4 分却写
   「非常完整」、打了 3 分却写「小瑕疵」都算不符。
5. 满分时，上面那段理由和描述里都不能有这一侧没实现某个需求、跑不起来、宣称改了实际
   没改这类交付问题；理由里写着，就不能给满分。
6. 4 分必须写清扣在哪里；3 分、2 分要让人读出缺陷的严重程度。
不算不符的，一条都不要报：对代码本身写得好不好的判断（这一步看不到代码），除非过程
记录直接反驳它；措辞生硬、篇幅，那是另一道在管的事。

【改法】
- 只要报了不符，就交出这一侧订正后的 score 和整段 desc，直接可以替换原文。
- 按轨迹改事实，按事实定分数：描述里的事实订正之后，分数要跟着重新落档，缺口有多大
  就打多少分。
- 只动有问题的那几句，别的句子逐字保留。
- 不要新增原文和这一侧轨迹里都没有的事实；换进来的名字必须在这一侧的轨迹里查得到。
- 写法照下面这份要求：
{gsb_rules.DELIVERY_WRITING_RULES}

【输出格式】
只输出一个 JSON 对象，不要任何前后说明，不要代码块围栏，只包含上面列出的那几侧：
{{
{fields}
}}"""


def normalize_delivery(obj, desc: str) -> dict:
    """一侧的核对结论。quote 对不上描述原文的整条丢掉，分数类问题允许不带 quote。"""
    d = obj if isinstance(obj, dict) else {}
    body = _squash(desc)
    items: list[dict] = []
    dropped = 0
    for raw in (d.get("problems") or []):
        if not isinstance(raw, dict):
            continue
        kind = gsb_analyzer._clean(raw.get("type"))
        quote = gsb_analyzer._clean(raw.get("quote"))
        if quote and _squash(quote) not in body:
            dropped += 1
            continue
        if not quote and kind != "分数":
            dropped += 1
            continue
        items.append({"quote": quote[:300], "type": kind if kind in DELIVERY_TYPES else "",
                      "claim": gsb_analyzer._clean(raw.get("claim"))[:300],
                      "fact": gsb_analyzer._clean(raw.get("fact"))[:400]})
        if len(items) >= MAX_MISMATCHES:
            break
    return {"problems": items, "quote_dropped": dropped,
            "score": d.get("score"), "desc": str(d.get("desc") or "")}


def merge_local_delivery(problems: list[dict], hard: list[dict]) -> list[dict]:
    """把程序按侧查出的硬项并进来。模型漏报的照样算数，理由和 merge_local 相同。"""
    out = list(problems)
    for h in hard:
        q = _squash(h["quote"])
        if any(m["quote"] and (_squash(m["quote"]) in q or q in _squash(m["quote"])) for m in out):
            continue
        out.append({"quote": h["quote"], "type": "侧别", "claim": f"提到了 {h['ref']}",
                    "fact": h["why"], "source": "local"})
    return out[:MAX_MISMATCHES]


def vet_delivery(new: dict, old: dict, *, side: str, gsb: dict,
                 corpora: dict[str, str]) -> tuple[dict | None, str]:
    """交付完整性订正稿的采信。返回 (采信的 {score, desc}, 丢弃原因)。

    四道关，和理由那边同一个思路：
    - 分数必须是 1 到 5 的整数；
    - 不能引入原来没有的红项（分数与描述对不上、照抄理由、写到另一侧、机器指标这些）；
    - 换进来的文件名、符号要在这一侧自己的轨迹里查得到；
    - 改完按侧再查一遍，还有硬项就不采信。
    """
    fixed = gsb_analyzer.delivery_of({"score": new.get("score"),
                                      "desc": new.get("desc") or old.get("desc")})
    if fixed["score"] is None:
        return None, f"订正稿的分数不是 1 到 5 的整数（{new.get('score')!r}）"
    if not fixed["desc"]:
        return None, "订正稿没有给出描述"
    kw = {"side": side, "reason": gsb.get("reason") or "",
          "bad_findings": (gsb.get(f"{side.lower()}_findings") or {}).get("bad")}
    before = {name for name, level, _ in gsb_rules.delivery_checks(old, **kw) if level == "block"}
    after = [msg for name, level, msg in gsb_rules.delivery_checks(fixed, **kw)
             if level == "block" and name not in before]
    if after:
        return None, f"订正稿引入了原来没有的红项：{'；'.join(after[:2])}"
    body = corpora.get(side) or ""
    invented = [t for t in gsb_rules.invented_tokens(fixed["desc"], str(old.get("desc") or ""))
                if not (body and gsb_attribution.found_in(t, body))]
    if invented:
        return None, f"订正稿里冒出了 {side} 侧轨迹里查不到的文件名或符号：{'、'.join(invented[:4])}"
    if left := gsb_attribution.side_hard(fixed["desc"], side, corpora):
        return None, ("订正稿里仍有对不上这一侧轨迹的落点：" +
                      "；".join(f"{h['ref']}（{h['why']}）" for h in left[:3]))
    return fixed, ""


def delivery_notes(side: str, problems: list[dict], before: dict, after: dict | None) -> list[str]:
    """交付完整性每一处订正折成一句人话，和理由那边的 notes 同一个写法。"""
    out = []
    for m in problems:
        where = f"原文「{m['quote']}」" if m.get("quote") else f"{before.get('score')} 分这个打分"
        out.append(f"{side} 侧交付完整性：{where}{'与轨迹不符' if m.get('type') != '分数' else '和描述或理由对不上'}。"
                   f"轨迹里实际是：{m.get('fact') or '见订正后的描述'}。")
    if after is not None:
        if after.get("score") != before.get("score"):
            out.append(f"{side} 侧交付完整性评分由 {before.get('score')} 分改为 {after.get('score')} 分")
        out.append(f"{side} 侧交付完整性描述已按轨迹订正")
    return out


async def check_delivery(gsb: dict, facts: dict[str, dict], *, task_no: str,
                         corpora: dict[str, str], process: dict[str, dict],
                         apply: bool = True) -> dict:
    """核两侧交付完整性。返回 {status, sides, notes, fixed, model}。

    status：skipped（老题没有这对字段）、ok（都对得上）、fixed（订正过并采信）、
    fail（报了不符却交不出能用的订正稿）。模型没答上来直接抛 LlmError / ValueError，
    由调用方记成 ERROR——那和「核过了、有问题」是两回事。
    """
    sides = delivery_sides(gsb)
    if not sides:
        return {"status": "skipped", "sides": {}, "notes": [], "fixed": {}}
    cur = dict(gsb)
    result: dict[str, dict] = {}
    pending = list(sides)
    retry: list[str] = []
    model = ""
    for rnd in range(1, FIX_ROUNDS + 1):
        r = await llm.ask(
            build_delivery_prompt(cur, facts, sides=pending, task_no=task_no, corpora=corpora,
                                  process=process, retry_note="；".join(retry)),
            purpose=f"交付完整性核验 {task_no}", attempts=1, timeout_s=FACTCHECK_TIMEOUT_S)
        model = r.model
        parsed = gsb_analyzer.extract_object(r.text, pending[0], "交付完整性核验 JSON")
        retry = []
        for s in list(pending):
            old = _delivery(cur, s)
            item = normalize_delivery(parsed.get(s), str(old.get("desc") or ""))
            item["problems"] = merge_local_delivery(
                item["problems"], gsb_attribution.side_hard(str(old.get("desc") or ""), s, corpora))
            entry = {"score": old.get("score"), "problems": item["problems"],
                     "quote_dropped": item["quote_dropped"], "rounds": rnd}
            if not item["problems"]:
                result[s] = {**entry, "status": "ok"}
                pending.remove(s)
                continue
            if not apply:
                result[s] = {**entry, "status": "fail",
                             "notes": delivery_notes(s, item["problems"], old, None)}
                pending.remove(s)
                continue
            fixed, why = vet_delivery(item, old, side=s, gsb=cur, corpora=corpora)
            if fixed:
                result[s] = {**entry, "status": "fixed", "before": old, "after": fixed,
                             "notes": delivery_notes(s, item["problems"], old, fixed)}
                cur[f"{s.lower()}_delivery"] = fixed
                pending.remove(s)
                continue
            why = why or "上一版没有交出可用的订正稿"
            result[s] = {**entry, "status": "fail", "rewrite_dropped": why,
                         "notes": delivery_notes(s, item["problems"], old, None)}
            retry.append(f"{s} 侧：{why}")
            log.warning("题 %s %s 侧交付完整性第 %d 轮订正稿没采用：%s", task_no, s, rnd, why)
        if not pending:
            break

    states = {v["status"] for v in result.values()}
    status = "fail" if "fail" in states else ("fixed" if "fixed" in states else "ok")
    return {"status": status, "sides": result, "model": model,
            "notes": [n for s in sides for n in (result.get(s) or {}).get("notes") or []],
            "fixed": {f"{s.lower()}_delivery": result[s]["after"]
                      for s in sides if (result.get(s) or {}).get("status") == "fixed"}}


# ---------------- 落库 ----------------

def _save(task_id: int, status: str, report: dict, *, reason: str = "",
          delivery: dict | None = None) -> None:
    """落库。给了 reason 就连理由正文一起换掉。

    换正文和换指纹必须在同一个事务里：分两次写的话，中间那一瞬间库里是「新正文 +
    旧指纹」，而 gsb_precheck.stale() 正是拿这两样比的，这时候读一次就会判成
    「质检之后理由又改过」，把刚订正好的题挡在提交门外。

    改了正文就把口语化质检的结论一并清掉。这一步排在它前面，正常不会撞上；但人工
    重跑事实核验是允许的，那时候上一轮的「措辞通过」评的是改之前那一段话。

    delivery 给了就把订正过的那一侧交付完整性一起换掉，同样在这个事务里连指纹一起记。
    """
    from app.services import gsb_precheck

    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return
        gsb = dict(task.gsb or {})
        if reason:
            gsb["reason"] = reason
            report = {**report, "reason_digest": gsb_precheck.reason_digest(reason),
                      "reason_chars": gsb_rules.visible_chars(reason)}
        if delivery:
            gsb.update(delivery)
        if reason or delivery:
            task.gsb = gsb
            task.precheck_status = PRECHECK_IDLE
            task.precheck = {}
        report = {**report, "delivery_digest": gsb_precheck.delivery_digest(gsb)}
        task.factcheck_status = status
        task.factcheck = report
        gsb_precheck.sync_stage(db, task)
    bus.publish("tasks", {"type": "task", "id": task_id})


# ---------------- 跑一遍 ----------------

async def run_factcheck(task_id: int, *, apply: bool = True) -> dict:
    """对一道题跑事实核验。默认直接把订正好的正文写回理由。

    apply=False 留给「只想看看有没有说错」的场合，走的是同一次模型调用。
    """
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        if task.factcheck_status == FACTCHECK_RUNNING:
            return {"ok": False, "message": "这道题的事实核验正在跑"}
        if task.status not in (ANALYZED, QC):
            return {"ok": False, "message": f"状态 {task.status} 不用做事实核验"}
        gsb = task.gsb or {}
        reason = gsb.get("reason") or ""
        verdict, task_no = gsb.get("verdict") or "", task.task_no
        if not reason.strip():
            return {"ok": False, "message": "还没有理由正文，先跑 GSB 分析"}
        gsb = dict(gsb)
        prev_status, prev = task.factcheck_status, dict(task.factcheck or {})
        task.factcheck_status = FACTCHECK_RUNNING
        task.factcheck = {"started_at": utc_now().isoformat()}
    bus.publish("tasks", {"type": "task", "id": task_id})

    started = time.time()
    from app.services import gsb_precheck

    facts = load_facts(task_no)
    corpora = load_corpora(task_no)
    process = load_process(task_no)
    attribution = gsb_attribution.check(reason, corpora)
    hard = [h for h in attribution if h["level"] == gsb_attribution.HARD]
    base = {"reason_digest": gsb_precheck.reason_digest(reason),
            "reason_chars": gsb_rules.visible_chars(reason),
            "local_suspects": suspects(reason, facts) + [
                {"quote": h["quote"], "side": h["side"],
                 "why": ("[必须改] " if h["level"] == gsb_attribution.HARD else "[待判] ") + h["why"]}
                for h in attribution],
            "attribution": attribution,
            "attribution_version": ATTRIBUTION_VERSION,
            "attribution_sides": [s for s in config.SIDES if corpora.get(s)],
            "finished_at": utc_now().isoformat()}
    if not any((facts.get(s) or {}).get("steps_total") for s in config.SIDES):
        # 两侧都没有轨迹就核不了。判 ERROR 而不是 PASS：PASS 的意思是「对过了，没问题」，
        # 而这里是「压根没对」，拿它当通过会让一道无从核验的题一路走到提交。
        #
        # 不带 llm_error：轨迹缺了多少次重跑都还是缺，而看门狗的恢复探测正是按这个
        # 标记挑「等模型恢复」的题。混进去的话，账单一通它就被放回流程，下一轮再报
        # 同样的错，从此每轮空转一次。
        _save(task_id, FACTCHECK_ERROR,
              {**base, "error": "两侧都没有轨迹执行记录，无法核验",
               "duration_s": round(time.time() - started)})
        return {"ok": False, "message": "两侧都没有轨迹执行记录，无法核验"}

    # 理由没动、只是交付完整性变了（人改过那对字段，或者老题刚补上）的时候，理由那一段
    # 沿用上一次的结论，只核交付完整性。理由和交付完整性都没变的重跑照常整段重核——
    # 人点「重跑」要的就是再核一遍。
    if (prev.get("reason_digest") == base["reason_digest"] and _reason_settled(prev_status, prev)
            and (prev.get("delivery_digest") or "") != gsb_precheck.delivery_digest(gsb)):
        keep = {k: prev[k] for k in ("mismatches", "notes", "summary", "model", "applied",
                                     "applied_at", "reason_before", "chars_before",
                                     "confirmed_at", "confirmed_note") if k in prev}
        outcome = {"status": FACTCHECK_PASS, "new_reason": "",
                   "report": {**base, **keep, "mismatches": prev.get("mismatches") or [],
                              "reason_reused": True},
                   "result": {"ok": True, "passed": True, "applied": False, "mismatches": 0,
                              "notes": [], "summary": prev.get("summary", ""),
                              "message": "理由没变，事实核验沿用上一次的结论", "reason": reason}}
    else:
        outcome = await _check_reason(reason, facts, verdict=verdict, task_no=task_no,
                                      corpora=corpora, process=process, hard=hard, base=base,
                                      apply=apply, started=started)
    report, result = outcome["report"], outcome["result"]
    if outcome["status"] == FACTCHECK_ERROR:
        _save(task_id, FACTCHECK_ERROR, report)
        return result
    report["reason_status"] = outcome["status"]
    final_reason = outcome["new_reason"] or reason

    try:
        delivery = await check_delivery({**gsb, "reason": final_reason}, facts, task_no=task_no,
                                        corpora=corpora, process=process, apply=apply)
    except (llm.LlmError, ValueError) as exc:
        log.warning("题 %s 交付完整性核验没跑完：%s", task_no, exc)
        # 理由那一段的订正照样落库：它已经过了采信，丢掉等于白核一遍。状态记 ERROR 并带
        # llm_error，看门狗等模型恢复后会回来补；那时理由没变，只会重核交付完整性。
        _save(task_id, FACTCHECK_ERROR,
              {**report, "error": f"交付完整性核验没跑完：{exc}"[:600], "llm_error": True,
               "duration_s": round(time.time() - started)},
              reason=outcome["new_reason"])
        return {**result, "ok": False, "passed": False,
                "message": f"交付完整性核验没跑完：{exc}"}

    report["delivery"] = {k: v for k, v in delivery.items() if k != "fixed"}
    report["duration_s"] = round(time.time() - started)
    status = outcome["status"]
    if delivery["status"] == "fail":
        status = FACTCHECK_FAIL
    _save(task_id, status, report, reason=outcome["new_reason"], delivery=delivery["fixed"])

    if delivery["status"] == "skipped":
        return result
    msg = {"ok": "交付完整性与轨迹一致",
           "fixed": "交付完整性订正了 " + "、".join(
               s for s, v in delivery["sides"].items() if v["status"] == "fixed") + " 侧",
           "fail": "交付完整性有与轨迹不符的地方没能自动订正，报告里写明了是哪几处"}[delivery["status"]]
    log.info("题 %s %s", task_no, msg)
    return {**result, "passed": status == FACTCHECK_PASS,
            "applied": result.get("applied") or delivery["status"] == "fixed",
            "notes": (result.get("notes") or []) + delivery["notes"],
            "delivery": report["delivery"],
            "message": f"{result['message']}；{msg}"}


def _reason_settled(status: str, report: dict) -> bool:
    """上一次的结论里，理由那一段算不算放行。人工确认的一律算；按侧核对之前的旧口径不算。"""
    if status == FACTCHECK_CONFIRMED:
        return True
    return ((report.get("reason_status") or status) == FACTCHECK_PASS
            and int(report.get("attribution_version") or 0) >= ATTRIBUTION_VERSION)


async def _check_reason(reason: str, facts: dict[str, dict], *, verdict: str, task_no: str,
                        corpora: dict[str, str], process: dict[str, dict], hard: list[dict],
                        base: dict, apply: bool, started: float) -> dict:
    """核理由那一段。返回 {status, report, new_reason, result}，不落库——交付完整性还要
    接着核，两段的结论合成一个状态一起写。"""
    report: dict = {}
    text = reason
    retry_note = ""
    for rnd in range(1, FIX_ROUNDS + 1):
        try:
            r = await llm.ask(
                build_prompt(text, facts, verdict=verdict, task_no=task_no,
                             retry_note=retry_note, corpora=corpora, process=process),
                purpose=f"事实核验 {task_no}", attempts=1, timeout_s=FACTCHECK_TIMEOUT_S)
            parsed = gsb_analyzer.extract_object(r.text, "mismatches", "事实核验 JSON")
        except (llm.LlmError, ValueError) as exc:
            log.warning("题 %s 事实核验没跑完：%s", task_no, exc)
            # llm_error 标记这次失败是「模型没答上来」，而不是这道题本身有问题。
            # 看门狗的恢复探测按它挑要放回流程的题：账单被拒、超时、输出解不开都该
            # 等模型好了再来一次，而轨迹缺失那种再试一百次也是同样的结果。
            return {"status": FACTCHECK_ERROR, "new_reason": "",
                    "report": {**base, "error": str(exc)[:600], "llm_error": True,
                               "duration_s": round(time.time() - started)},
                    "result": {"ok": False, "message": f"事实核验没跑完：{exc}"}}

        report = {**base, **normalize(parsed, reason=text), "model": r.model,
                  "rounds": rnd, "duration_s": round(time.time() - started)}
        # 模型说没问题不作数：按侧逐字查出来的硬项照样记为不符，不改掉就过不了
        report["mismatches"] = merge_local(report["mismatches"], hard)
        if not report["mismatches"]:
            break
        if not apply:
            break
        fixed, why = vet(str(parsed.get("rewrite") or ""), text, verdict, corpora)
        if fixed:
            report["notes"] = notes_for(report["mismatches"], text)
            report.update({"applied": True, "applied_at": utc_now().isoformat(),
                           "reason_before": text,
                           "chars_before": gsb_rules.visible_chars(text)})
            n = len(report["mismatches"])
            log.info("题 %s 事实核验订正了 %d 处：%s", task_no, n,
                     "；".join(report["notes"])[:300])
            return {"status": FACTCHECK_PASS, "new_reason": fixed, "report": report,
                    "result": {"ok": True, "passed": True, "applied": True, "mismatches": n,
                               "notes": report["notes"], "summary": report["summary"],
                               "message": f"事实核验订正了 {n} 处与轨迹不符的描述，理由已更新",
                               "reason": fixed}}
        retry_note = why or "上一版没有交出可用的改写稿"
        if not why and hard:
            retry_note += ("，而程序按侧查出的那几处不符还在正文里："
                           + "；".join(f"「{h['quote'][:60]}」{h['why']}" for h in hard[:3])
                           + "。这几处必须改，给出整段订正稿")
        report["rewrite_dropped"] = retry_note
        log.warning("题 %s 事实核验第 %d 轮改写稿没采用：%s", task_no, rnd, retry_note)

    if not report.get("mismatches"):
        log.info("题 %s 事实核验通过，理由与轨迹一致", task_no)
        return {"status": FACTCHECK_PASS, "new_reason": "", "report": report,
                "result": {"ok": True, "passed": True, "applied": False, "mismatches": 0,
                           "notes": [], "summary": report.get("summary", ""),
                           "message": "事实核验通过，理由与轨迹一致", "reason": text}}

    # 报出了不符、却几轮都交不出能用的订正稿。留给人，但把话说清楚：哪一处、
    # 轨迹里是什么。人照着改比自己从头核对轨迹快得多。
    report["notes"] = notes_for(report["mismatches"], text, applied=False)
    n = len(report["mismatches"])
    log.warning("题 %s 事实核验挑出 %d 处但没能自动订正", task_no, n)
    return {"status": FACTCHECK_FAIL, "new_reason": "", "report": report,
            "result": {"ok": True, "passed": False, "applied": False, "mismatches": n,
                       "notes": report["notes"], "summary": report.get("summary", ""),
                       "message": f"挑出 {n} 处与轨迹不符，自动订正没成功（{report.get('rewrite_dropped', '')}），"
                                  f"报告里写明了是哪几处",
                       "reason": text}}


def confirm(task_id: int, note: str = "") -> dict:
    """人工放行事实核验。

    留这个口子的理由和口语化质检那边一样：模型报的不符里总有它自己读偏的，
    逐条辩论不如让人看一眼直接放行。放行要留痕，并且把当时的理由指纹记下来。
    """
    from app.services import gsb_precheck

    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        if task.factcheck_status == FACTCHECK_IDLE:
            return {"ok": False, "message": "这道题还没做过事实核验，没有可确认的结论"}
        if task.factcheck_status == FACTCHECK_RUNNING:
            return {"ok": False, "message": "事实核验正在跑，等它出结果再确认"}
        reason = (task.gsb or {}).get("reason") or ""
        report = dict(task.factcheck or {})
        report.update({
            "confirmed_at": utc_now().isoformat(),
            "confirmed_from": task.factcheck_status,
            "confirmed_note": (note or "").strip()[:500],
            "reason_digest": gsb_precheck.reason_digest(reason),
            "delivery_digest": gsb_precheck.delivery_digest(task.gsb or {}),
        })
        task.factcheck = report
        task.factcheck_status = FACTCHECK_CONFIRMED
        gsb_precheck.sync_stage(db, task)
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "message": "已确认事实核验结论"}


def reseal(task: Task, new_reason: str, new_gsb: dict | None = None) -> bool:
    """措辞质检整段换掉理由之后，把事实核验的结论过继到新的这一稿上。返回过继了没有。

    不过继的话每道题都要核两遍。顺序是事实在前、措辞在后，而措辞那一步会整段改写，
    改完指纹就对不上，题当场退回待质检、再排一次事实核验 —— 而那一次核的是一段只
    换了说法的话，结论必然和上一次一样。一百多道题就是一百多次白花的调用。

    过继不是无条件放行。措辞改写的约束是「不许新增原文里没有的事实」，但约束是劝，
    劝不住的那部分要有人接住，所以这里拿本地那两把确定性的尺子在新文本上再量一遍：
    执行结果（suspects）和侧别对应（gsb_attribution.hard）。措辞改写最容易出的侧别
    问题是把「B 的 removeNode」和「A 的 setNode」并成一句、只留一个主语，名字一个
    没改，归属却变了。量不出新的矛盾才过继，量得出就留着让它过期，重核一遍。
    这一遍不花模型调用，只是几条正则。

    只有已经放行、并且按侧核过的结论才谈得上过继。判了待人工、没跑成的、还是旧口径
    的，本来就该重跑。

    new_gsb 给了就是交付完整性描述也被措辞质检改过，两侧描述按同样两把尺子各量一遍，
    交付指纹一起过继。过继之前事实核验必须真核过这一版之前的交付完整性（指纹对得上），
    否则就是在给一对从没核过的字段盖章。
    """
    from app.services import gsb_precheck

    if task.factcheck_status not in FACTCHECK_OK or outdated(task):
        return False
    report = dict(task.factcheck or {})
    if gsb_precheck.delivery_stale(report, task.gsb or {}):
        return False
    facts, corpora = load_facts(task.task_no), load_corpora(task.task_no)
    if suspects(new_reason, facts):
        return False
    if gsb_attribution.hard(new_reason, corpora):
        return False
    gsb = new_gsb if new_gsb is not None else (task.gsb or {})
    if new_gsb is not None:
        for s in delivery_sides(new_gsb):
            desc = str(_delivery(new_gsb, s).get("desc") or "")
            if delivery_suspects(desc, s, facts) or gsb_attribution.side_hard(desc, s, corpora):
                return False

    report.update({"reason_digest": gsb_precheck.reason_digest(new_reason),
                   "delivery_digest": gsb_precheck.delivery_digest(gsb),
                   "resealed_at": utc_now().isoformat(),
                   "resealed_by": "措辞质检改写"})
    task.factcheck = report
    return True


def stale(task: Task) -> bool:
    """核验之后理由又改过，这份结论不再代表现在这一稿。口径与 gsb_precheck.stale 相同。"""
    from app.services import gsb_precheck

    digest = (task.factcheck or {}).get("reason_digest") or ""
    return (bool(digest) and digest != gsb_precheck.reason_digest((task.gsb or {}).get("reason") or "")) \
        or gsb_precheck.delivery_stale(task.factcheck or {}, task.gsb or {})


def outdated(task: Task) -> bool:
    """这份 PASS 是不是按侧核对之前的旧口径给的。

    旧口径只对执行结果，张冠李戴的句子照样拿 PASS，这种结论不能再当放行用。
    人工确认的不算：那是人看过之后自己拍板的。
    """
    return (task.factcheck_status == FACTCHECK_PASS
            and int((task.factcheck or {}).get("attribution_version") or 0) < ATTRIBUTION_VERSION)


def settled(task: Task) -> bool:
    """事实核验这一档过了没有。提交门禁与阶段推进都照它算。"""
    return task.factcheck_status in FACTCHECK_OK and not stale(task) and not outdated(task)


def factcheck_block(task: Task) -> str:
    """事实核验这一档挡不挡提交。空串表示不挡。

    和 gsb_precheck.submit_block 里那段措辞质检的判法一样，用白名单而不是黑名单：
    建表之后补的列，老行拿到的是空串，空串不等于任何一个坏档，用黑名单会让整批
    老题被当成核验通过。
    """
    if task.factcheck_status in FACTCHECK_OK:
        if stale(task):
            return "事实核验之后理由又改过，这份结论已经过期，重跑核验或人工确认"
        if outdated(task):
            return "这份事实核验是旧口径，没有按 A、B 两侧分别对照轨迹，重跑事实核验"
        return ""
    if task.factcheck_status == FACTCHECK_RUNNING:
        return "事实核验正在跑，等它出结果"
    if task.factcheck_status == FACTCHECK_ERROR:
        why = (task.factcheck or {}).get("error", "原因不明")
        return f"事实核验没跑完（{why}），重跑或人工确认后再提交"
    if task.factcheck_status == FACTCHECK_FAIL:
        report = task.factcheck or {}
        n = len(report.get("mismatches") or [])
        failed = [s for s, v in ((report.get("delivery") or {}).get("sides") or {}).items()
                  if v.get("status") == "fail"]
        if failed and (report.get("reason_status") or FACTCHECK_FAIL) != FACTCHECK_FAIL:
            return (f"事实核验发现 {'、'.join(failed)} 侧交付完整性与轨迹不符且没能自动订正，"
                    f"改完并确认后才能提交")
        return f"事实核验发现 {n} 处描述与轨迹不符且没能自动订正，改完并确认后才能提交"
    return "还没做事实核验"


def skip_reason(task: Task) -> str:
    """这道题为什么不用再跑一次事实核验。空串表示该跑。

    剔除要在发出去之前做：批量一次勾一百多道，里面多半有已经核过的，照单发出去
    就是照单烧钱。口径写在这里给批量入口和看门狗共用。
    """
    if task.status not in (ANALYZED, QC):
        return f"状态 {task.status} 不用做事实核验"
    if task.factcheck_status == FACTCHECK_RUNNING:
        return "事实核验正在跑"
    if not ((task.gsb or {}).get("reason") or "").strip():
        return "还没有理由正文，先跑 GSB 分析"
    # ERROR 不在里面：那是核验自己没跑成（模型超时、账单被拒、输出解不开），重跑正是
    # 该做的事。FAIL 要挡——理由一个字没改就再问一遍，模型挑出来的还是那几处。
    if task.factcheck_status in (FACTCHECK_PASS, FACTCHECK_CONFIRMED, FACTCHECK_FAIL) \
            and not stale(task) and not outdated(task):
        return "已有结论，理由没再改过"
    return ""
