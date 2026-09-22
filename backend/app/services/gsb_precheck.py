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

这一步不只是挑毛病，它直接改。模型交回来的是改好并收进篇幅的整段正文，校验通过就
盖掉 gsb.reason，改前那一稿存进 reason_before。改成这样是因为只给意见的代价是实打实
的：一道题挑出十条，人要逐条回正文里对位置再逐条替换，几十道题就是几百次手工替换，
而这件事模型做得比人准。把关全压在 _vet_rewrite 和 local_defects 上——稿子只要篇幅
出界、或者引入了原文没有的核验红项，就整份丢掉，宁可留着待改让人自己动手。

判的东西有两层。措辞那层只能靠模型逐句读；篇幅和词表那层程序自己就数得出来
（local_defects），不必花一次模型调用去问，而且模型对篇幅没有概念——一段六百字的
理由它逐句读完觉得句句通顺就回 pass，可篇幅恰恰是这一步要压的。两层都干净才算通过。

质检结论只对当时那一段话负责，所以要连着理由正文的指纹一起存。人在界面上又改了
一稿，旧结论就不再代表这一稿，提交门禁得把它当成没质检过。指纹去掉空白再算——
只动了换行和缩进不算改内容。自动改写走的是同一套：换正文和换指纹在同一个事务里
做完，否则中间那一瞬间是「新正文 + 旧指纹」，恰好会被 stale() 判成人又改过。

发起的口子有三个：GSB 分析跑完之后自动接上一道（watchdog.run_quality_gate 之前，
所以核验与平台质检看到的都是改过的稿子）、app.cli、以及页面上的批量质检。

「一次点击烧一次模型调用」这件事没有消失，只是换了防法：run_batch 会先把已经有
有效结论、正在跑、或者压根没有理由正文的题剔掉（skip_reasons），剩下的才真的发出去。
"""

from __future__ import annotations

import asyncio
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

    n = gsb_rules.visible_chars(reason)
    lo, hi = gsb_rules.REASON_TARGET_MIN, gsb_rules.REASON_TARGET_MAX
    cap = gsb_rules.REASON_SOFT_MAX_CHARS
    cut = (f"这一段现在 {n} 字，超了，rewrite 要收到 {lo} 到 {hi} 字，也就是去掉大约 {n - hi} 字。"
           if n > cap else
           f"这一段现在 {n} 字，rewrite 保持在 {lo} 到 {hi} 字，不要写长。")

    return f"""你在给一份双跑对比的评审理由做最后一道文字质检。这段话马上要交给评审方。
你要做两件事：把不像人写的地方挑出来，并且直接交出改好之后的整段正文。

【判断基准】
{JUDGE_BASELINE}

【逐条规则】
{TONE_RULES}
{hint_block}

【篇幅】
{cut}
这个篇幅只装得下三件事：做错了什么、导致了什么后果、对方哪里做得好。超出来的部分
一定是写了别的东西，按这个顺序删：内部机制的分步推演、与结论无关的次要缺陷、
过程叙事、两边做法相同的部分、证据的枚举明细。
文件名、函数名、标识符不能丢，那是评审的落点。

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
4. suggest 给改写后的句子，直接可以替换 quote。
5. 措辞上确实没有问题、篇幅也在范围内，才给 pass，issues 留空、rewrite 留空串。
   不要为了凑数报「可以更自然」。
6. 只要报了问题，或者篇幅超了，就必须给 rewrite：改好并收到篇幅之内的整段正文。
   rewrite 是要直接拿去替换原文的，所以它必须是一段可以照原样交付的完整理由，
   不是片段、不是说明、不带任何前后缀。

【rewrite 的硬约束】
- 结论不许变。原文判 A 更好，rewrite 也必须落在 A 更好，反之亦然。
- 不许新增原文里没有的事实。删可以，编不行。
- 不要 markdown 记号、不要步号、不要绝对路径、不要表情符号。
- 分成两到四个自然段，段之间空一行。

【输出格式】
只输出一个 JSON 对象，不要任何前后说明，不要代码块围栏：
{{
  "verdict": "pass" 或 "revise",
  "summary": "一句话总体判断，二十到五十字",
  "issues": [
    {{"quote": "原文片段", "kind": "类别", "why": "为什么不像人写的", "suggest": "改写后的句子"}}
  ],
  "rewrite": "改好并收到篇幅之内的整段正文，没有问题时留空串"
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

    判据本身在 gsb_analyzer.vet_rewrite —— 事实核验那一步也整段换理由，两处必须
    照同一把尺子量，否则同一份稿子会在一步被放行、在另一步被拦。这里只留一个
    名字，是因为把关这件事是这个模块的职责，调用方按模块名找得到。
    """
    return gsb_analyzer.vet_rewrite(rewrite, original, verdict)


def local_defects(reason: str, verdict: str = "") -> list[str]:
    """本地规则能直接判出来的毛病。空表示这一段在规则层面是干净的。

    这一层不是给模型兜底，而是给它定调：篇幅有没有超、词表里的说法还在不在，都是
    程序数得出来的，不必花一次模型调用去问。质检的结论要把它算进去——模型说「读起来
    没问题」但这段话还有六百字、还带着「题面」「这么看下来」，那就不算通过。
    """
    return [msg for name, level, msg in gsb_rules.reason_checks(reason, verdict=verdict)
            if level == "block" or name in ("reason_too_long", "reason_wording")]


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
    #
    # 本地规则判出来的毛病也算进去。模型对篇幅没有概念，一段六百字的理由它逐句读完
    # 觉得每句都通顺，就回一个 pass；而篇幅恰恰是这一步要压的东西。
    defects = local_defects(reason, verdict)
    passed = not issues and not defects
    rewrite, why_dropped = ("", "") if passed else _vet_rewrite(
        str(obj.get("rewrite") or ""), reason, verdict)
    return {
        "passed": passed,
        "summary": _clean(obj.get("summary"))[:300],
        "issues": issues,
        "local_defects": defects,
        "quote_dropped": dropped,
        "rewrite": rewrite,
        "rewrite_dropped": why_dropped,
    }


# ---------------- 阶段投影 ----------------

def missing_screencast(task: Task) -> list[str]:
    """还缺哪几侧的录屏链接。"""
    sc = task.screencast or {}
    return [s for s in config.SIDES if not str(sc.get(s) or "").strip()]


def screencast_ready(task: Task) -> bool:
    return not missing_screencast(task)


def quality_settled(task: Task) -> bool:
    """两道质检都放行了没有。事实核验管「说的是不是真的」，措辞质检管「读起来像不像人写的」。

    两道都要过。只认措辞那一道的话，一段写得很顺、但把对方没犯的错算上去的理由
    会一路走到提交；只认事实那一道，交出去的又是一段机器味的话。
    """
    from app.services import gsb_factcheck

    return gsb_factcheck.settled(task) and task.precheck_status in PRECHECK_OK and not stale(task)


def sync_stage(db, task: Task) -> bool:  # noqa: ANN001
    """按两道质检过没过把题在 ANALYZED 和 QC 之间挪。返回有没有挪动。

    这里原先是按录屏齐不齐推的，含义正好反过来：ANALYZED 是「等录屏」，填完两条
    链接才进质检。那个顺序有个实打实的代价 —— 质检会整段改写理由，而人是对着理由
    去录屏、讲解产物的，改完就得重录一遍。录屏本身只是提交时要填的一个参数，它不
    影响质检判什么，没有理由排在质检前面。所以两步对调：分析一完就质检，质检放行
    了再去录。

    状态由质检结论推出来，而不是让某个动作各写各的。两道都过题自己就进待录屏栏，
    理由被人改过（指纹对不上）又退回待质检 —— 「谁动谁写」的做法迟早会留下一批
    质检早就过了却还挂在待质检栏的题，而人正是照着栏目决定下一步做什么。

    只在 ANALYZED 与 QC 之间动。已经上传、已完成、需人工的题不碰：那些状态下
    质检结论的新旧不再决定任何事。
    """
    if task.status == ANALYZED and quality_settled(task):
        task.status = QC
        return True
    if task.status == QC and not quality_settled(task):
        task.status = ANALYZED
        return True
    return False


def sync_all() -> int:
    """开机对账：补齐迁移出来的空档，再按质检过没过重新归位。返回挪动了几道。

    两件事都是给历史数据补的。ALTER TABLE 补出来的 precheck_status / factcheck_status
    是空串 —— 空串在界面上什么都不显示，提交门禁那边也得靠白名单才挡得住，规整成
    IDLE 省掉后面每一处的特例判断。

    归位这一次会把一批题从 QC 退回 ANALYZED，这是对的，不是回退。QC 的含义从「录屏
    齐了」换成了「两道质检都放行」，而事实核验是新加的一道，历史数据一律没跑过。
    退回去它们会被看门狗按新流程补上核验，补完自己再进来。
    """
    from app.services import gsb_factcheck

    moved, fixed = [], 0
    with session() as db:
        for task in db.query(Task).all():
            if not task.precheck_status:
                task.precheck_status = PRECHECK_IDLE
                fixed += 1
            if not task.factcheck_status:
                task.factcheck_status = gsb_factcheck.FACTCHECK_IDLE
                fixed += 1
            if task.status in SETTLING and sync_stage(db, task):
                moved.append(task.id)
    for tid in moved:
        bus.publish("tasks", {"type": "task", "id": tid})
    if fixed:
        log.info("提交前质检：补上 %d 处质检初始状态", fixed)
    if moved:
        log.info("提交前质检：%d 道题按质检过没过重新归位", len(moved))
    return len(moved)


# ---------------- 提交门禁 ----------------

def stale(task: Task) -> bool:
    """质检之后理由又改过，这份结论不再代表现在这一稿。

    不看质检走到哪一档，只看指纹对不对得上。提交门禁那边本来就先判过 PRECHECK_OK 才
    问到这里，所以对它没有影响；而「该不该再跑一次」要的正是不分档的口径 —— 判了待改
    的题也会被人改完理由，那一稿没问过模型，和放行之后又改过是同一回事。

    没记过指纹的当没改过：那是建表之后补列留下的老行，拿空指纹当「改过」会让整批老题
    一直显示结论过期。
    """
    digest = (task.precheck or {}).get("reason_digest") or ""
    return bool(digest) and digest != reason_digest((task.gsb or {}).get("reason") or "")


def submit_block(task: Task) -> str:
    """不能提交的原因。空串表示可以提交。

    这里是提交的唯一口径，界面上那个按钮灰不灰也照它算，免得前端按一套条件放行、
    后端按另一套回绝，人点下去才知道不行。

    录屏在这里判，不在状态上判。质检移到录屏前面之后，状态只表示「质检过没过」，
    而录屏仍然是提交的必填项 —— 缺了它平台会以「字段缺失」回绝，那句话得在人按
    按钮之前就说出来。
    """
    from app.services import gsb_factcheck

    if task.status not in UPLOADABLE:
        return (f"当前状态 {task.status} 不能提交，两道提交前质检都放行了才会进待录屏"
                if task.status == ANALYZED else f"当前状态 {task.status} 不能提交")
    if blocked := gsb_factcheck.factcheck_block(task):
        return blocked
    if missing := missing_screencast(task):
        return f"还缺 {'、'.join(missing)} 侧的录屏，录完贴进来就能提交"
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

def _save(task_id: int, status: str, report: dict, *, reason: str = "") -> None:
    """落库。给了 reason 就连理由正文一起换掉。

    两件事必须在同一个事务里做完：换正文、把指纹改成新正文的。分两次写的话，中间
    那一瞬间库里是「新正文 + 旧指纹」，而 stale() 正是拿这两样比的，这时候读一次就会
    判成「质检之后理由又改过」，把刚放行的题挡在提交门外。

    事实核验那一档的指纹也要一起过继，理由见 gsb_factcheck.reseal —— 它记的同样是
    「这份结论对应哪一稿」，这里换了正文不管它，等于每道题都要把事实核验再跑一遍。
    """
    from app.services import gsb_factcheck

    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return
        if reason:
            gsb = dict(task.gsb or {})
            gsb["reason"] = reason
            task.gsb = gsb
            report = {**report, "reason_digest": reason_digest(reason),
                      "reason_chars": gsb_rules.visible_chars(reason)}
            gsb_factcheck.reseal(task, reason)
        task.precheck_status = status
        task.precheck = report
        sync_stage(db, task)
    bus.publish("tasks", {"type": "task", "id": task_id})


async def run_precheck(task_id: int, *, apply: bool = True) -> dict:
    """对一道题跑质检。默认直接把改好的正文写回理由。

    以前这里只挑毛病不动文字，理由是「人下次打开看到的不是他确认过的那一段」。那个
    顾虑在流程改成分析完就自动跑之后不成立了：这时候还没有人确认过任何一稿，理由是
    上一步刚生成的，质检是它的最后一道加工，不是对人工成果的改动。而只给意见不改的
    代价是实打实的——一道题挑出十条，人要逐条回正文里对位置、逐条替换，六十道就是
    六百次手工替换，这件事模型做得比人准。

    改前的原文存进 reason_before，界面上要对比看得见。丢了这一份的话，自动改写就成了
    一次不可追溯的覆盖。

    apply=False 保留下来给「只想看看有什么问题」的场合，走的是同一次模型调用。
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
        # llm_error 标记这次失败是「模型没答上来」而不是这段理由有问题。看门狗的恢复
        # 探测按它挑要放回流程的题，见 watchdog._blocked_by_llm。
        _save(task_id, PRECHECK_ERROR, {**base, "error": str(exc)[:600], "llm_error": True,
                                        "duration_s": round(time.time() - started)})
        return {"ok": False, "message": f"质检没跑完：{exc}"}

    report = {**base, **normalize(parsed, reason=reason, verdict=verdict),
              "model": r.model, "duration_s": round(time.time() - started)}

    # 有改写稿就直接落到理由上。改完之后本地规则要重新判一遍：模型偶尔只改了被点名的
    # 那几句，篇幅或者别的说法还留着，那种稿子换上去只是把问题换了个位置，仍然算待改。
    applied, new_reason = False, ""
    if apply and report["rewrite"]:
        left = local_defects(report["rewrite"], verdict)
        if left:
            report["apply_skipped"] = "；".join(left[:2])
        else:
            applied, new_reason = True, report["rewrite"]
            report.update({
                "applied": True,
                "applied_at": utc_now().isoformat(),
                "reason_before": reason,
                "chars_before": gsb_rules.visible_chars(reason),
                "local_defects": [],
            })
    # 改写已经落上去，这一稿在规则层面是干净的，就按通过记。留在待改上等于要人再去
    # 确认一次一个已经改好的文本，而他手里并没有比这更该做的动作。
    status = PRECHECK_PASS if (report["passed"] or applied) else PRECHECK_FAIL
    _save(task_id, status, report, reason=new_reason)

    n_issues = len(report["issues"])
    if applied:
        msg = (f"质检改好了 {n_issues} 处，理由已更新为 "
               f"{gsb_rules.visible_chars(new_reason)} 字（原 {report['chars_before']} 字）")
    elif report["passed"]:
        msg = "质检通过"
    else:
        why = report.get("rewrite_dropped") or report.get("apply_skipped") or ""
        msg = f"挑出 {n_issues} 处：{report['summary']}" + (f"（改写稿没采用：{why}）" if why else "")
    log.info("题 %s 质检 %s", task_no, msg)
    return {"ok": True, "passed": status == PRECHECK_PASS, "applied": applied,
            "issues": n_issues, "summary": report["summary"], "message": msg,
            "reason": new_reason or reason, "verdict": verdict}


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
    """两道质检里还有一道没走完的题，按题号排。

    两道都要看。只问措辞那一道的话，历史数据会整批漏掉——它们的 precheck 早就是 PASS，
    而事实核验是后加的一道，一律还是 IDLE，于是这批最该核的题在 ready 列表里一个都
    不出现，而看门狗的积压扫描又明明挑得到它们，两边对不上账。

    不再看录屏。质检移到了录屏前面，等录屏齐了才跑就回到了老流程 —— 措辞一改人得
    重录一遍。

    已经通过或已经人工确认、而且理由没再改过的题不重复跑：一次质检就是一次模型调用，
    对着同一段没动过的话再问一遍，答案一样，钱白花。
    """
    from app.services import gsb_factcheck

    with session() as db:
        out = [(t.task_no, t.id) for t in db.query(Task).filter(Task.status.in_((ANALYZED, QC))).all()
               if not (skip_reason(t) and gsb_factcheck.skip_reason(t))]
        return [tid for _, tid in sorted(out)]


def submittable_ids() -> list[int]:
    """质检放行、录屏也齐了、可以直接提交的题。批量提交按它取。"""
    with session() as db:
        return [t.id for t in db.query(Task).filter(Task.status == QC).all()
                if submittable(t)]


def skip_reason(task: Task) -> str:
    """这道题为什么不用再跑一次质检。空串表示该跑。

    剔除必须在发出去之前做，不能等 run_precheck 自己回绝：页面上一次勾一百多道，
    里面多半有已经跑过的，照单发出去就是照单烧钱。ready_ids 判的是同一件事，
    只是那边自己挑题、这边按人勾的那批来判，所以口径写在这里给两边共用。
    """
    if task.status not in SETTLING:
        return f"状态 {task.status} 不用做提交前质检"
    if task.precheck_status == PRECHECK_RUNNING:
        return "质检正在跑"
    if not ((task.gsb or {}).get("reason") or "").strip():
        return "还没有理由正文，先跑 GSB 分析"
    # 判了待改的也要挡。理由一个字没改就再问一遍，模型挑出来的还是那几处，这次调用纯属
    # 白花 —— 一百多道题一个按钮发出去，这一条漏掉就是一百多次。改过理由（指纹对不上）
    # 才放行，那才是真的换了一稿。
    #
    # ERROR 不在里面：那是质检自己没跑成（模型超时、账单被拒、输出解不开），重跑正是
    # 该做的事，挡住它等于让人只能一道一道手点。
    if task.precheck_status in (PRECHECK_PASS, PRECHECK_CONFIRMED, PRECHECK_FAIL) \
            and not stale(task):
        return "已有结论，理由没再改过"
    return ""


# ---------------- 批量质检：后台串行跑 ----------------
# 页面上一次勾一百多道是常事，而一道题就是一次模型调用、一分半钟，整批下来好几个小时。
# 同步接口撑不住这么长的连接（nginx 一小时就断开，人也不会守着页面），所以这里起一个
# 后台任务：接口立刻返回，每道题跑完照常发 SSE 把那一行刷新，整批还剩多少看 job()。
#
# 串行和 batch_precheck 路由是同一个理由：并发发出去只会一起撞限流，而这一步不赶时间。

_batch: asyncio.Task | None = None


def _blank_job() -> dict:
    return {"running": False, "total": 0, "done": 0, "passed": 0, "revise": 0, "failed": 0,
            "current": "", "started_at": "", "finished_at": "", "stopping": False}


_job: dict = _blank_job()


def job() -> dict:
    """整批质检的进度。挂在 /api/system/status 上，页面每次 SSE 刷新顺带拿到，
    不必为这一个数字再开一条轮询。"""
    return dict(_job)


def batch_running() -> bool:
    return bool(_batch) and not _batch.done()


def start_batch(ids: list[int]) -> dict:
    """把勾中的题排进后台质检，立刻返回。

    同时只允许一批在跑：两批并行等于两条串行队列同时发模型调用，说好的不撞限流就没了，
    而且 job() 那份进度也说不清是谁的。
    """
    if batch_running():
        return {"ok": False, "message": f"已经有一批在质检（{_job['done']}/{_job['total']}），等它跑完或先停掉",
                "started": 0, "skipped": []}

    todo: list[tuple[int, str]] = []
    skipped: list[dict] = []
    with session() as db:
        for tid in ids:
            task = db.get(Task, tid)
            if task is None:
                skipped.append({"id": tid, "task_no": str(tid), "message": "题目不存在"})
                continue
            why = skip_reason(task)
            if why:
                skipped.append({"id": tid, "task_no": task.task_no, "message": why})
            else:
                todo.append((tid, task.task_no))

    if not todo:
        return {"ok": False, "message": "勾中的题都不用再跑质检", "started": 0, "skipped": skipped}

    _job.update(_blank_job())
    _job.update({"running": True, "total": len(todo), "started_at": utc_now().isoformat()})
    global _batch
    _batch = asyncio.create_task(_run_batch(todo), name="precheck-batch")
    log.info("批量质检开跑：%d 道（跳过 %d 道）", len(todo), len(skipped))
    return {"ok": True, "started": len(todo), "skipped": skipped,
            "message": f"已排队质检 {len(todo)} 道"
                       + (f"，跳过 {len(skipped)} 道" if skipped else "")}


def stop_batch() -> dict:
    """停在当前这道题之后。

    不打断正在跑的那一道：模型调用已经发出去了，钱已经花掉，让它写完结果比半路
    丢掉划算；而且中途取消会把题留在 RUNNING 上，下次谁也发不动它。
    """
    if not batch_running():
        return {"ok": False, "message": "现在没有在跑的批量质检"}
    _job["stopping"] = True
    return {"ok": True, "message": f"跑完手上这道就停（已完成 {_job['done']}/{_job['total']}）"}


async def _run_batch(items: list[tuple[int, str]]) -> None:
    try:
        for tid, task_no in items:
            if _job["stopping"]:
                log.info("批量质检被叫停，剩下 %d 道没跑", _job["total"] - _job["done"])
                break
            _job["current"] = task_no
            try:
                res = await run_precheck(tid)
            except Exception as exc:  # noqa: BLE001
                # 一道题炸了不能把整批带走：后面那些和它没关系，而这一道的原因
                # 已经落在 precheck_status=ERROR 上，人在列表里看得见
                log.exception("题 %s 质检抛异常：%s", task_no, exc)
                _job["failed"] += 1
            else:
                if not res.get("ok"):
                    _job["failed"] += 1
                elif res.get("passed"):
                    _job["passed"] += 1
                else:
                    _job["revise"] += 1
            _job["done"] += 1
    finally:
        _job.update({"running": False, "current": "", "stopping": False,
                     "finished_at": utc_now().isoformat()})
        log.info("批量质检收工：%d/%d 跑完 · 通过 %d · 待改 %d · 没跑成 %d",
                 _job["done"], _job["total"], _job["passed"], _job["revise"], _job["failed"])
