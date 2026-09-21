"""提交前质检：把写好的 GSB 理由交给模型，判它读起来像不像一个人写的。

和 gsb_verifier 的分工要分清。那道核验查的是确定性规则——字数、步号、行号区间、
markdown、两侧材料齐不齐，凡是正则能判的都在那边；这道质检查的是措辞和句子本身，
正则判不了：「根因两边翻到的是同一处」每个字都合规，没有数字、没有步号、没有
markdown，核验一路放行，可是没有人会这么说话。所以只能让模型逐句读一遍。

判什么这件事最容易搞反，规则表开头那段基准（JUDGE_BASELINE）比规则本身更要紧。
要拦的不是「写得正式」，恰恰相反：反例里那些句子是模型为了显得像人而硬造出来的
紧缩表达，改法是换成一个工程师会自然写出的常规说法，而常规说法往往比原文更书面。
少了这段基准，模型会把「机械化」理解成「太正式」，转头往里加语气词和口语，交回来
的东西更不像评审意见。

质检结论只对当时那一段话负责，所以要连着理由正文的指纹一起存。人在界面上又改了
一稿，旧结论就不再代表这一稿，提交门禁得把它当成没质检过。指纹去掉空白再算——
只动了换行和缩进不算改内容。

这条流程不接受浏览器发起，入口只有 app.cli（见该模块头部说明）。原因不是怕误点，
而是它得在人已经看过录屏、准备整批提交的那个时刻跑：跑早了理由还会改，跑完的结论
当场就过期；摆个按钮在页面上只会让人一遍遍点它。
"""

from __future__ import annotations

import hashlib
import logging
import re
import time

from app import config
from app.db import session
from app.events import bus
from app.models import (
    ANALYZED, PRECHECK_CONFIRMED, PRECHECK_ERROR, PRECHECK_FAIL, PRECHECK_IDLE,
    PRECHECK_OK, PRECHECK_PASS, PRECHECK_RUNNING, QC, SETTLING, UPLOADABLE, Task, utc_now,
)
from app.services import gsb_analyzer, gsb_rules, llm

log = logging.getLogger("gsb_precheck")

# 质检的 prompt 只有规则表加一段几百字的正文，正常一分钟内就回。给死上限是为了
# 不让一次卡顿把整批题的质检拖成和 GSB 分析一样长。
PRECHECK_TIMEOUT_S = 600
# 一段理由里这类毛病通常两三处，多的五六处。给上限是防模型逐句开条目，
# 交回来三十条「这句可以更自然」，人一条都不会看。
MAX_ISSUES = 12


# ---------------- 判什么 ----------------

JUDGE_BASELINE = """
判的是「这句话是不是一个工程师会自然写出来的」，不是「写得正不正式」。

写得正式、用词专业、句子偏长、通篇没有「我」，这些都不算问题，一处都不要报。
要拦的是另一种东西：模型为了让文字显得像人写的，硬造出一批紧缩、别扭、不合中文
习惯的表达——动作化的动词、拟人化的思维评价、把长定语塞进主语、在半句话里用冒号
塞解释。这些句子每个字都认得，连起来却没人这么说话。

改法一律是换成常规说法，而常规说法通常比原文更书面、更平实：

  原文：题面对错误载荷写得很具体：超限时要能看出是步数还是深度
  改成：题目明确要求，超限时要能分清是步数还是深度

  原文：根因两边翻到的是同一处
  改成：两边对问题的定位是一致的

  原文：B 有一处确实比 A 想得远
  改成：B 在接口设计上比 A 更合理

三个例子的共同点：改完之后句子更长、更普通、更直白，信息一点没少。
不要反过来往口语的方向改，「说白了」「其实吧」「有点意思」这类一个都不要出现。
""".strip()

TONE_RULES = """
一、直接陈述事实，不要转述和点评材料
   不写「题面对 X 写得很具体」「材料里提到」「轨迹里能看出」「从改动来看」这类对
   材料的转述，直接把事实说出来：「题目明确要求 X」「B 在 X 上没有处理」。把题面
   当成观察对象去点评它写得怎么样，是只有在读材料的程序才会有的视角。

二、动作化的动词换成常规动词
   翻到、翻出、摸到、摸清、踩到、扒出、抠出、挖出、捞出、盯上、憋着，一律换成
   定位到、找到、发现、确认、命中、触发。

三、不要拟人化地评价对方「想得怎么样」
   想得远、想得深、想得细、想得多、脑子清楚、意识到得早、心里有数，换成落到具体
   方面的判断：在接口设计上更合理、对边界情况考虑得更全、提前处理了 X。只说
   「想得远」等于没说是哪方面想得远。

四、含糊的限定要落到具体方面
   「有一处确实比 A 好」「多少有点问题」「某种程度上更稳」，要说清是哪一处、哪个
   方面、具体是什么问题。说不清就不写这一句。

五、不要在半句话里用冒号塞解释
   「这里写得很具体：超限时要能分清是步数还是深度」这种一句话两个语法主干的写法，
   拆成两句完整的话，或者用逗号接成一个自然的长句。

六、句子要有完整的主谓，不要把长定语塞进主语
   「根因两边翻到的是同一处」「需求两边对的是同一份」这类为了省字把定语硬塞进主语
   的写法，改成语序自然的完整句：「两边对问题的定位是一致的」。

七、不用比喻和意象指代问题
   分水岭、这笔账、欠的账、留了个洞、留了条缝、那层皮、软肋、命门、七寸，一律直说
   是哪一处做得不够。

八、不用随口的俚语和口头禅
   差一口气、手搓、老实得多、朴素得多、摆得乱、对得住、栽在、绕远路，换成相较差了
   一点、自己重新写了一套、做法相对保守、实现简单得多、组织比较乱、与运行时一致、
   输在、多花了哪些工夫。

九、不生造对举和省略
   「A 快、B 稳」这种没有谓语的四字对举，「不是不能，是不该」这种绕弯的否定，都改成
   把两边分别说清的完整句子。

十、不要为了像人而加口语
   这一条是上面九条的边界。不要加「说白了」「其实吧」「有点意思」「挺不错」这类语气，
   也不要刻意改成第一人称。常规、平实、把事说清楚就够了。
""".strip()

# 报出来的类别只认这十种。让模型自己起名字的话，同一种毛病会在不同题上叫出七八个
# 名字，界面上没法归类，人也看不出「这批题反复犯的是哪一条」。
KINDS: tuple[str, ...] = (
    "转述材料", "动作化动词", "拟人化评价", "含糊限定", "冒号夹注",
    "句子生硬", "比喻指代", "随口俚语", "生造省略", "刻意口语",
)
OTHER_KIND = "其他"


# ---------------- 本地先摘一遍疑似词 ----------------
# 这不是独立判定：报不报、怎么改全由模型说了算，本地只把疑似的句子摘出来放进 prompt。
# 一段五六百字的理由里这类词往往只有两三处，不点出来模型容易整体读一遍回一句「还行」。
#
# 词表只收明显的。「不太」「略」「算是」这种日常里本来就自然，收进来会把正常句子
# 摘一大片，摘得越多模型越不当真。
HINT_WORDS: tuple[tuple[str, str], ...] = (
    ("翻到", "动作化动词"), ("翻出", "动作化动词"), ("摸到", "动作化动词"),
    ("摸清", "动作化动词"), ("踩到", "动作化动词"), ("扒出", "动作化动词"),
    ("抠出", "动作化动词"), ("挖出", "动作化动词"), ("捞出", "动作化动词"),
    ("盯上", "动作化动词"),
    ("想得远", "拟人化评价"), ("想得深", "拟人化评价"), ("想得细", "拟人化评价"),
    ("想得多", "拟人化评价"), ("想得周全", "拟人化评价"), ("脑子", "拟人化评价"),
    ("心里有数", "拟人化评价"), ("意识到得早", "拟人化评价"),
    ("有一处确实", "含糊限定"), ("多少有点", "含糊限定"), ("某种程度", "含糊限定"),
    ("说不上", "含糊限定"), ("谈不上", "含糊限定"), ("算不上", "含糊限定"),
    ("写得很", "转述材料"), ("写得比较", "转述材料"), ("写得挺", "转述材料"),
    ("题面对", "转述材料"), ("材料里", "转述材料"), ("轨迹里", "转述材料"),
    ("分水岭", "比喻指代"), ("这笔账", "比喻指代"), ("那笔账", "比喻指代"),
    ("欠的账", "比喻指代"), ("留了个洞", "比喻指代"), ("留了条缝", "比喻指代"),
    ("那层皮", "比喻指代"), ("软肋", "比喻指代"), ("命门", "比喻指代"),
    ("差一口气", "随口俚语"), ("手搓", "随口俚语"), ("老实得多", "随口俚语"),
    ("朴素得多", "随口俚语"), ("摆得乱", "随口俚语"), ("对得住", "随口俚语"),
    ("栽在", "随口俚语"), ("绕远路", "随口俚语"),
    ("说白了", "刻意口语"), ("其实吧", "刻意口语"), ("有点意思", "刻意口语"),
)

_SENT = re.compile(r"[。；\n]")


def hints(reason: str) -> list[dict]:
    """本地摘出的疑似句。返回 [{"quote": 整句, "word": 命中词, "kind": 类别}]。"""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for chunk in _SENT.split(reason or ""):
        line = chunk.strip()
        if not line:
            continue
        for word, kind in HINT_WORDS:
            if word in line and (line, word) not in seen:
                seen.add((line, word))
                out.append({"quote": line[:120], "word": word, "kind": kind})
    return out


# ---------------- prompt ----------------

def build_prompt(reason: str, *, verdict: str = "", task_no: str = "") -> str:
    found = hints(reason)
    listed = "\n".join(f"   「{h['word']}」在这一句里：{h['quote']}" for h in found[:12])
    hint_block = (f"""
【本地先摘出来的疑似处】
下面这几句我这边按词表先摘了出来，不一定都算问题，你自己判断；漏在外面的也要报。
{listed}
""".rstrip() if found else "")

    return f"""你在给一份双跑对比的评审理由做最后一道文字质检。这段话马上要交给评审方，
需要你判断它读起来像不像一个人写的，把不像的地方逐句挑出来并给出改法。

【判断基准】
{JUDGE_BASELINE}

【逐条规则】
{TONE_RULES}
{hint_block}

【待检正文】
题号 {task_no or '—'}，结论是 {verdict or '未给出'}。
<<<REASON
{reason}
REASON>>>

【怎么报】
1. 一处一条，quote 必须是上面正文里的原文片段，逐字照抄，不要改写、不要合并两处。
   报不出原文片段的就不要报——人要拿它去正文里对位置。
2. kind 只能从这十个里选：{'、'.join(KINDS)}。
3. why 用一句话说清它为什么读起来不像人写的，不要复述规则编号。
4. suggest 给改写后的句子，直接可以替换 quote，长度相近或更长都行，别压缩掉信息。
5. 通篇确实没有这类问题就给 pass，issues 留空数组，不要为了凑数报「可以更自然」。
6. 报了问题就必须给 rewrite：整段改写后的正文，只改被点出来的那几句，其余原样保留，
   结论和事实一个字都不许变，篇幅和原文相当。没有问题时 rewrite 留空串。

【输出格式】
只输出一个 JSON 对象，不要任何前后说明，不要代码块围栏：
{{
  "verdict": "pass" 或 "revise",
  "summary": "一句话总体判断，二十到五十字",
  "issues": [
    {{"quote": "原文片段", "kind": "类别", "why": "为什么不像人写的", "suggest": "改写后的句子"}}
  ],
  "rewrite": "整段改写后的正文，没有问题时留空串"
}}"""


# ---------------- 解析与采信 ----------------

def _clean(text) -> str:
    """把模型给的文字洗成能直接落库的样子。

    suggest 和 rewrite 都可能被人一键套进理由里，所以要和分析产出走同一套清洗：
    markdown 记号、绝对路径、步号、机器指标，一个都不能带进去。
    """
    out = gsb_analyzer.strip_markdown(str(text or "").strip())
    out = gsb_analyzer.strip_paths(out)
    return gsb_analyzer.strip_machine_metrics(gsb_analyzer.strip_steps(out))


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def reason_digest(reason: str) -> str:
    """理由正文的指纹。只动了换行和缩进不算改内容，所以先去掉全部空白。"""
    return hashlib.sha256(_squash(reason).encode("utf-8")).hexdigest()[:16]


def _vet_rewrite(rewrite: str, original: str, verdict: str) -> tuple[str, str]:
    """决定这份整段改写稿要不要留。返回 (采信的稿子, 丢弃原因)。

    留一手是必须的：这段稿子会被人一键套进理由，而模型「顺手」把一千字压成两百字、
    或者改写时带进一条 markdown 列表，都出现过。套进去之后核验才报红，人得再回头
    重写一遍，比没有这份稿子更费事。

    两道关：篇幅不能明显缩水（信息被删掉了），也不能引入原文没有的核验红项。
    """
    text = _clean(rewrite)
    if not text:
        return "", ""
    n, m = gsb_rules.visible_chars(text), gsb_rules.visible_chars(original)
    if m and n < m * 0.6:
        return "", f"改写稿只有 {n} 字，原文 {m} 字，缩水太多，多半删掉了论点"
    before = {name for name, level, _ in gsb_rules.reason_checks(original, verdict=verdict)
              if level == "block"}
    after = [msg for name, level, msg in gsb_rules.reason_checks(text, verdict=verdict)
             if level == "block" and name not in before]
    if after:
        return "", f"改写稿引入了原文没有的红项：{'；'.join(after[:2])}"
    return text, ""


def normalize(obj: dict, *, reason: str, verdict: str = "") -> dict:
    """把模型输出洗成可入库的质检报告。

    quote 必须能在正文里对上位置，对不上的整条丢掉。模型偶尔会把自己改写后的句子
    填进 quote，那种条目人拿着没法用：他在界面上按 quote 去正文里找，找不到，于是
    不知道该改哪一句，只能整段重写。
    """
    body = _squash(reason)
    issues: list[dict] = []
    dropped = 0
    for raw in (obj.get("issues") or []):
        if not isinstance(raw, dict):
            continue
        quote = _clean(raw.get("quote"))
        if not quote or _squash(quote) not in body:
            dropped += 1
            continue
        kind = str(raw.get("kind") or "").strip()
        issues.append({
            "quote": quote[:200],
            "kind": kind if kind in KINDS else OTHER_KIND,
            "why": _clean(raw.get("why"))[:200],
            "suggest": _clean(raw.get("suggest"))[:400],
        })
        if len(issues) >= MAX_ISSUES:
            break

    # 结论按 issues 定，不按模型自报的 verdict 定：它常常一边列出三条问题一边说
    # pass。反过来也有——说 revise 却一条都举不出来，那种就是没话说硬凑个结论。
    passed = not issues
    rewrite, why_dropped = ("", "") if passed else _vet_rewrite(
        str(obj.get("rewrite") or ""), reason, verdict)
    return {
        "passed": passed,
        "summary": _clean(obj.get("summary"))[:300],
        "issues": issues,
        "quote_dropped": dropped,
        "rewrite": rewrite,
        "rewrite_dropped": why_dropped,
    }


# ---------------- 阶段投影 ----------------

def screencast_ready(task: Task) -> bool:
    sc = task.screencast or {}
    return all(str(sc.get(s) or "").strip() for s in config.SIDES)


def sync_stage(db, task: Task) -> bool:  # noqa: ANN001
    """按录屏齐不齐把题在 ANALYZED 和 QC 之间挪。返回有没有挪动。

    质检这一步的入口条件就是「录屏录完了」，所以状态由录屏链接推出来，而不是让
    某个动作各写各的。填完两条链接题自己就进质检栏，链接被清掉又退回待录屏——
    以前那种「谁动谁写」的做法在这里会留下一批录屏齐了却还挂在待录屏栏的题，
    而人正是照着栏目决定下一步做什么。

    只在 ANALYZED 与 QC 之间动。已经上传、已完成、需人工的题不碰：那些状态下录屏
    链接的有无不再决定任何事。
    """
    if task.status == ANALYZED and screencast_ready(task):
        task.status = QC
        return True
    if task.status == QC and not screencast_ready(task):
        task.status = ANALYZED
        # 退回待录屏就把质检结论一起清掉。录屏链接被换掉通常是重录了一份，
        # 这时留着上一轮的「通过」会让它在重新录完之后直接可提交，等于跳过质检。
        task.precheck_status = PRECHECK_IDLE
        task.precheck = {}
        return True
    return False


def sync_all() -> int:
    """开机对账：补齐迁移出来的空档，再按录屏齐不齐重新归位。返回挪动了几道。

    两件事都是给历史数据补的。质检这一步是后加的，此前录屏齐了的题一律停在 ANALYZED，
    不补这一次它们会挂在待录屏栏里（录屏明明齐了），提交按钮还是灰的，人看不出为什么。
    而 ALTER TABLE 补出来的 precheck_status 是空串 —— 空串在界面上什么都不显示，
    提交门禁那边也得靠白名单才挡得住，规整成 IDLE 省掉后面每一处的特例判断。
    """
    moved, fixed = [], 0
    with session() as db:
        for task in db.query(Task).all():
            if not task.precheck_status:
                task.precheck_status = PRECHECK_IDLE
                fixed += 1
            if task.status in SETTLING and sync_stage(db, task):
                moved.append(task.id)
    for tid in moved:
        bus.publish("tasks", {"type": "task", "id": tid})
    if fixed:
        log.info("提交前质检：%d 道题补上质检初始状态", fixed)
    if moved:
        log.info("提交前质检：%d 道题按录屏齐不齐重新归位", len(moved))
    return len(moved)


# ---------------- 提交门禁 ----------------

def stale(task: Task) -> bool:
    """质检之后理由又改过。"""
    if task.precheck_status not in PRECHECK_OK:
        return False
    digest = (task.precheck or {}).get("reason_digest") or ""
    return bool(digest) and digest != reason_digest((task.gsb or {}).get("reason") or "")


def submit_block(task: Task) -> str:
    """不能提交的原因。空串表示可以提交。

    这里是提交的唯一口径，界面上那个按钮灰不灰也照它算，免得前端按一套条件放行、
    后端按另一套回绝，人点下去才知道不行。
    """
    if task.status not in UPLOADABLE:
        return (f"当前状态 {task.status} 不能提交，两侧录屏链接齐了才会进质检"
                if task.status == ANALYZED else f"当前状态 {task.status} 不能提交")
    report = task.precheck or {}
    status = task.precheck_status
    # 白名单：只有明确放行的两档算过，其余一律挡下。写成「排除掉几个坏档」的黑名单会
    # 在一个地方漏出去 —— 建表之后补的列，老行拿到的是空串（ADD COLUMN 给不出 Python
    # 侧的默认值），而空串不等于任何一个坏档，于是整批老题被当成质检通过。
    if status not in PRECHECK_OK:
        if status == PRECHECK_RUNNING:
            return "提交前质检正在跑，等它出结果"
        if status == PRECHECK_ERROR:
            return f"提交前质检没跑完（{report.get('error', '原因不明')}），重跑或人工确认后再提交"
        if status == PRECHECK_FAIL:
            n = len(report.get("issues") or [])
            return f"质检挑出 {n} 处机械化表达，改掉并确认后才能提交"
        return "还没做提交前质检"
    if stale(task):
        return "质检之后理由又改过，这份结论已经过期，重跑质检或人工确认"
    return ""


def submittable(task: Task) -> bool:
    return not submit_block(task)


# ---------------- 跑一遍 ----------------

def _save(task_id: int, status: str, report: dict) -> None:
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return
        task.precheck_status = status
        task.precheck = report
        sync_stage(db, task)
    bus.publish("tasks", {"type": "task", "id": task_id})


async def run_precheck(task_id: int) -> dict:
    """对一道题跑提交前质检。只碰 precheck 那几个字段，理由本身一个字都不改。

    不自动套用改写稿：改哪几句、要不要照它改，是人看完 issues 才能定的事。质检自动
    改文字的话，人下次打开看到的理由已经不是他确认过的那一段，而差异藏在一段五六百
    字的话里，翻不出来。
    """
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        if task.precheck_status == PRECHECK_RUNNING:
            return {"ok": False, "message": "这道题的质检正在跑"}
        if task.status not in (ANALYZED, QC):
            return {"ok": False, "message": f"状态 {task.status} 不用做提交前质检"}
        gsb = task.gsb or {}
        reason, verdict, task_no = gsb.get("reason") or "", gsb.get("verdict") or "", task.task_no
        if not reason.strip():
            return {"ok": False, "message": "还没有理由正文，先跑 GSB 分析"}
        task.precheck_status = PRECHECK_RUNNING
        task.precheck = {"started_at": utc_now().isoformat()}
    bus.publish("tasks", {"type": "task", "id": task_id})

    started = time.time()
    base = {"reason_digest": reason_digest(reason), "reason_chars": gsb_rules.visible_chars(reason),
            "finished_at": utc_now().isoformat()}
    try:
        r = await llm.ask(build_prompt(reason, verdict=verdict, task_no=task_no),
                          purpose=f"质检 {task_no}", attempts=1, timeout_s=PRECHECK_TIMEOUT_S)
        parsed = gsb_analyzer.extract_object(r.text, "issues", "质检 JSON")
    except (llm.LlmError, ValueError) as exc:
        log.warning("题 %s 提交前质检没跑完：%s", task_no, exc)
        _save(task_id, PRECHECK_ERROR, {**base, "error": str(exc)[:600],
                                        "duration_s": round(time.time() - started)})
        return {"ok": False, "message": f"质检没跑完：{exc}"}

    report = {**base, **normalize(parsed, reason=reason, verdict=verdict),
              "model": r.model, "duration_s": round(time.time() - started)}
    status = PRECHECK_PASS if report["passed"] else PRECHECK_FAIL
    _save(task_id, status, report)
    log.info("题 %s 提交前质检 %s，%d 处、%ds", task_no,
             "通过" if report["passed"] else "有问题", len(report["issues"]), report["duration_s"])
    return {"ok": True, "passed": report["passed"], "issues": len(report["issues"]),
            "summary": report["summary"],
            "message": ("质检通过" if report["passed"]
                        else f"挑出 {len(report['issues'])} 处：{report['summary']}")}


def confirm(task_id: int, note: str = "") -> dict:
    """人工确认：理由已经按质检意见改过，可以提交了。

    这是整条流程里唯一允许在界面上做的动作。质检本身由对话发起，改理由和拍这个板
    只有人能做——模型挑出来的十条里总有两三条是它自己读偏了，逐条辩论不如让人看一眼
    直接放行，而放行这件事必须留痕：确认时把当时的理由指纹记下来，之后再改又会变回
    「结论已过期」。
    """
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        if task.precheck_status == PRECHECK_IDLE:
            return {"ok": False, "message": "这道题还没做过提交前质检，没有可确认的结论"}
        if task.precheck_status == PRECHECK_RUNNING:
            return {"ok": False, "message": "质检正在跑，等它出结果再确认"}
        reason = (task.gsb or {}).get("reason") or ""
        report = dict(task.precheck or {})
        report.update({
            "confirmed_at": utc_now().isoformat(),
            "confirmed_from": task.precheck_status,
            "confirmed_note": (note or "").strip()[:500],
            # 指纹换成此刻这一稿：确认的是人改完之后的话，不是质检当时看到的那一段
            "reason_digest": reason_digest(reason),
        })
        task.precheck = report
        task.precheck_status = PRECHECK_CONFIRMED
        sync_stage(db, task)
        blocked = submit_block(task)
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "message": "已确认，可以提交" if not blocked else f"已确认，但{blocked}",
            "submittable": not blocked}


# ---------------- 该质检哪些题 ----------------

def ready_ids() -> list[int]:
    """录屏已齐、还没拿到有效质检结论的题，按题号排。

    口径只认「录屏齐了」这一件事，因为质检要在人看过录屏、准备整批提交的时候跑。
    已经通过或已经人工确认、而且理由没再改过的题不重复跑：一次质检就是一次模型调用，
    对着同一段没动过的话再问一遍，答案一样，钱白花。
    """
    with session() as db:
        out = []
        for task in db.query(Task).filter(Task.status.in_((ANALYZED, QC))).all():
            if not screencast_ready(task) or not (task.gsb or {}).get("reason"):
                continue
            if task.precheck_status == PRECHECK_RUNNING:
                continue
            if task.precheck_status in PRECHECK_OK and not stale(task):
                continue
            out.append((task.task_no, task.id))
        return [tid for _, tid in sorted(out)]


def submittable_ids() -> list[int]:
    """质检放行、可以直接提交的题。批量提交按它取。"""
    with session() as db:
        return [t.id for t in db.query(Task).filter(Task.status == QC).all()
                if submittable(t)]
