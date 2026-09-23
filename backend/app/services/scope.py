"""开跑之前先看这道题要动多大面：只在一个模块里打转的题，不值得开两个容器。

和 difficulty 那一道是同一件事的两头，分工要分清。那道数的是跑完之后两侧各用了多少
步、多少分钟，准——因为那是模型真花掉的工夫；可是数到的时候两个容器的两个多小时已经
烧完了，它救得下的只有后面那次分析额度。这一道站在开跑之前，看的是题面要求改动的范围，
它没有跑出来的数可依，判得没那么准，但拦下一道题省的是整整两个容器的机器时间。

为什么用「跨几个模块」当判据。回头看被跑后筛选拦下的那批题，毛病几乎都是同一个：
改动面窄。一道题只要动一个模块里的一两个函数，模型定位、改完、跑一遍验证，十几步就
收工了，两边都轻松做完，比出来的只有措辞差异。而改动面是题面自己说清楚的东西，不必
等跑完——「同时改掉解析和渲染两侧的行为」和「修一个函数的边界判断」，读题面就分得出来。

判定不信模型自报的结论，只数它列出的模块。让它回答「跨不跨模块」，它会顺着题面的语气
答；让它列出「不动它这道题就完不成」的模块并逐个说明理由，它得把话落到具体目录上，
凑不出来就只能少列。和 gsb_precheck 里「结论按 issues 定、不按模型自报的 verdict 定」
是同一个道理。

目录树有就给，没有也能判。领取时工作区已经 clone 好了，能给出真实的目录结构，模型
就能把模块落到 src/parser 这样的实际路径上；而题还在题库里没领取时没有工作区，这时
只给题面，让它按功能点归纳模块。后者当然粗一些，但它换来的是「整批题可以提前一次性
体检」——否则人只能一道一道领了才知道哪些不合格，而领取本身就要 clone 两个分支。

结论连着题面的指纹一起存。题面改过，这份结论就不再代表现在这一道题，门禁要当它没
体检过——和两道提交前质检对理由正文的做法一致。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re

from app import config
from app.db import session
from app.events import bus
from app.models import AVAILABLE, CLAIMED, DISCARDED, Task, utc_now
from app.services import gsb_analyzer, llm, settings_store

log = logging.getLogger("scope")

# 默认要求跨几个模块。和 settings_store 里的 Spec 默认值必须一字不差。
MIN_MODULES_DEFAULT = 2
# 体检的 prompt 只有题面加一份目录树，正常一两分钟就回。给死上限是不让一次卡顿把
# 领取这条同步路径拖成十几分钟——人正等着题进队列。
SCOPE_TIMEOUT_S = 420

PASS = "pass"          # 改动面够宽
NARROW = "narrow"      # 只在一个模块里打转
UNKNOWN = "unknown"    # 体检自己没跑成，不拦题
SKIPPED = "skipped"    # 这道校验被关掉了

# 目录树给多少。给全了没有用：一个中等仓库几千个文件，塞进去只会把题面淹掉，而判
# 「要动几个模块」看的是目录骨架，不是每个文件。
TREE_MAX_ENTRIES = 300
TREE_MAX_DEPTH = 3
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
              "target", ".next", ".nuxt", "vendor", "coverage", ".pytest_cache", ".idea"}


def min_modules() -> int:
    return settings_store.get_int("difficulty.min_modules", MIN_MODULES_DEFAULT)


def enabled() -> bool:
    """要求少于两个模块就等于不要求，这时整道校验都不必跑，省下那次模型调用。"""
    return min_modules() >= 2


# ---------------- 目录树 ----------------

def repo_tree(task_no: str) -> str:
    """工作区的目录骨架。没 clone 就返回空串，调用方照样能判。

    只走 A 侧：A 与 B 是同一个初始快照切出来的两个分支，目录结构一模一样，扫两遍
    没有任何新信息。

    列到文件为止但不列全部文件：每个目录只留前几个文件当样本，够模型认出这是什么
    模块就行。目录本身一个不漏——模块的边界是目录画的。
    """
    root = config.TaskPaths(task_no, config.SIDES[0]).workspace
    if not (root / ".git").exists():
        return ""
    lines: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS and not d.startswith("."))
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > TREE_MAX_DEPTH:
            dirnames[:] = []
            continue
        keep = sorted(f for f in filenames if not f.startswith("."))[:6]
        more = len(filenames) - len(keep)
        here = "/" if rel == "." else f"{rel}/"
        lines.append(f"{here}  {' '.join(keep)}" + (f"  …另有 {more} 个文件" if more > 0 else ""))
        if len(lines) >= TREE_MAX_ENTRIES:
            lines.append("…（目录过多，只列了前面这些）")
            break
    return "\n".join(lines)


# ---------------- prompt ----------------

def build_prompt(user_prompt: str, tree: str, need: int) -> str:
    tree_block = f"""
【仓库目录结构】
这是这道题的初始代码，模块要落到下面真实存在的目录上，不要编造路径。
{tree}
""".rstrip() if tree else """
【仓库目录结构】
这次拿不到仓库结构。按题面描述的功能点归纳模块，path 写你认为它在工程里对应的
那一块的名字（例如「命令行参数解析」「任务调度」），不要凭空编造具体目录路径。
""".rstrip()

    return f"""你在给一道众测题做开跑前的体检。只判一件事：这道题要求的改动落在几个模块上。

这个判断有实际后果。这批题是拿来比两个模型谁做得更好的，一道题如果只需要动一个模块
里的一两个函数，两边都能十几步做完，比出来的只有措辞差异，而跑一道题要两个容器各两
个多小时。所以只在一个模块里打转的题会被拦下来不跑。

【什么算一个模块】
模块是仓库里能独立成章的一块代码：一个顶层源码目录、一个包、一个服务、一层（解析层、
存储层、传输层）。判断标准是「改它要不要换一套上下文」——解析器和渲染器是两个模块，
同一个目录下的两个文件不是，同一个类的两个方法更不是。
测试文件、文档、配置不单独算模块：改了实现顺带改它的测试，那仍然是一个模块。

【只算必须改的，不算要读的】
任何一道题动手前都要读一圈别处的代码，那些不算。只列「不动它这道题就完不成」的模块，
每一个都要说清为什么非改不可。宁可少列也不要凑数——凑出来的模块会让一道本该拦下的
简单题混进去跑掉四个多小时的机器时间，而漏列一个模块只是让一道题多等一次人工确认。

【题面】
<<<PROMPT
{user_prompt.strip()[:20000]}
PROMPT>>>
{tree_block}

【怎么报】
1. modules 一条一个模块，path 写目录或模块名，why 用一句话说清不动它为什么完不成。
2. confidence 说你对这份判断有多大把握：题面把要改的东西说得很具体就是 high；
   只说了要达成什么效果、得靠猜实现落在哪里就是 low。
3. note 一句话概括这道题的改动面，二十到五十字。
4. 不要输出 markdown 记号，不要代码块围栏。

只输出一个 JSON 对象：
{{
  "modules": [{{"path": "src/parser", "why": "词法规则在这里，不改它新语法认不出来"}}],
  "confidence": "high" 或 "medium" 或 "low",
  "note": "一句话概括改动面"
}}

顺带说明：这道题现在的要求是至少跨 {need} 个模块。这个数字不该影响你怎么数——
你照实列，够不够由程序判。"""


# ---------------- 解析与判定 ----------------

def _clean(text) -> str:
    return gsb_analyzer.strip_markdown(str(text or "").strip())


def prompt_digest(user_prompt: str) -> str:
    """题面指纹。去掉全部空白再算：只动了换行和缩进不算改题。"""
    body = re.sub(r"\s+", "", user_prompt or "")
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def normalize(obj: dict, *, need: int) -> dict:
    """把模型输出洗成可入库的体检报告。

    判定只数模块条数，不看模型有没有说这道题「够跨」。同一个 path 报两遍算一个——
    模型偶尔会把一个目录按两个功能点拆开报，那样数出来的宽度是假的。
    """
    modules: list[dict] = []
    seen: set[str] = set()
    for raw in (obj.get("modules") or []):
        if not isinstance(raw, dict):
            continue
        path = _clean(raw.get("path"))[:120].strip("/ ")
        if not path or path.casefold() in seen:
            continue
        seen.add(path.casefold())
        modules.append({"path": path, "why": _clean(raw.get("why"))[:200]})
        if len(modules) >= 12:
            break
    confidence = str(obj.get("confidence") or "").strip().lower()
    return {
        "verdict": PASS if len(modules) >= need else NARROW,
        "modules": modules,
        "module_count": len(modules),
        "need": need,
        "confidence": confidence if confidence in ("high", "medium", "low") else "medium",
        "note": _clean(obj.get("note"))[:300],
    }


def summary(report: dict) -> str:
    """一句话结论，门禁和题卡都显示它。"""
    verdict = report.get("verdict")
    if verdict == SKIPPED:
        return "跨模块校验已关闭"
    if verdict == UNKNOWN:
        return f"改动面没体检成（{report.get('error', '原因不明')}），不拦这道题"
    names = "、".join(m["path"] for m in (report.get("modules") or [])[:4]) or "没数出模块"
    n, need = report.get("module_count", 0), report.get("need", MIN_MODULES_DEFAULT)
    low = "，而且题面说得含糊、这份判断把握不大" if report.get("confidence") == "low" else ""
    if verdict == PASS:
        return f"改动面跨 {n} 个模块（{names}），达到 {need} 个的要求{low}"
    return (f"改动面只有 {n} 个模块（{names}），不到要求的 {need} 个，"
            f"两边都会很快做完，比不出高下{low}")


# ---------------- 结论的有效期 ----------------

def stale(task: Task) -> bool:
    """体检之后题面又改过，这份结论不再代表现在这道题。

    没记过指纹的当没改过：那是建表之后补列留下的老行。
    """
    digest = (task.scope or {}).get("prompt_digest") or ""
    return bool(digest) and digest != prompt_digest(task.user_prompt or "")


def settled(task: Task) -> bool:
    """有一份还作数的结论没有。UNKNOWN 也算——那次体检自己没跑成，重跑多半还是不成，
    不能让一道题因为模型调不通就永远领不了。"""
    return bool((task.scope or {}).get("verdict")) and not stale(task)


def blocking(task: Task) -> str:
    """这道题因为改动面太窄而不该开跑的理由。空串表示可以跑。

    只有 NARROW 才拦。没体检过、体检没跑成、人工放行过的，一律放行——这道校验是拿来
    省机器时间的，不是拿来卡人的，它自己出问题不该让整批题领不了。
    """
    report = task.scope or {}
    if report.get("override") or stale(task):
        return ""
    if report.get("verdict") != NARROW:
        return ""
    return summary(report)


def override(task: Task, note: str = "") -> bool:
    """人工放行：这道题的改动面我认了，照跑。返回有没有真的改动。

    在打开的会话里直接改传进来的 task，由调用方提交。模型判「窄」判错的时候，人手里
    得有一个不必去改题面、也不必关掉整道校验的出口。
    """
    report = dict(task.scope or {})
    if not report or report.get("override"):
        return False
    report.update({"override": True, "override_at": utc_now().isoformat(),
                   "override_note": (note or "").strip()[:300]})
    task.scope = report
    return True


# ---------------- 跑一遍 ----------------

def _save(task_id: int, report: dict) -> None:
    """结论落到题上。已经废弃的题一个字都不写。

    废弃是人拍过板的结果——不管是他自己按的，还是跑后筛选判的而他没有捞回来。这道
    校验是给还要跑的题用的，往一道已经结案的题上写新结论，只会让废弃列表里冒出一行
    谁也没要求过的判断，而那道题本来就不会再跑。
    """
    with session() as db:
        task = db.get(Task, task_id)
        if task is None or task.status == DISCARDED:
            return
        keep = {k: v for k, v in (task.scope or {}).items()
                if k in ("override", "override_at", "override_note")}
        task.scope = {**report, **keep}
    bus.publish("tasks", {"type": "task", "id": task_id})


async def check(task_id: int) -> dict:
    """给一道题做一次改动面体检，结论落库。

    体检没跑成不算这道题的错，落 UNKNOWN 放行：模型欠费或超时的时候把整批题卡在领取
    上，代价远大于放几道简单题进去跑。
    """
    if not enabled():
        return {"ok": True, "verdict": SKIPPED, "reason": "跨模块校验已关闭"}
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "verdict": UNKNOWN, "reason": "题目不存在"}
        task_no, user_prompt = task.task_no, task.user_prompt or ""
    if not user_prompt.strip():
        return {"ok": False, "verdict": UNKNOWN, "reason": "这道题没有题面正文，判不了改动面"}

    need = min_modules()
    tree = repo_tree(task_no)
    base = {"ok": True, "prompt_digest": prompt_digest(user_prompt),
            "has_tree": bool(tree), "checked_at": utc_now().isoformat()}
    try:
        r = await llm.ask(build_prompt(user_prompt, tree, need),
                          purpose=f"改动面 {task_no}", attempts=1, timeout_s=SCOPE_TIMEOUT_S)
        parsed = gsb_analyzer.extract_object(r.text, "modules", "改动面 JSON")
    except (llm.LlmError, ValueError) as exc:
        log.warning("题 %s 的改动面没体检成：%s", task_no, exc)
        report = {**base, "verdict": UNKNOWN, "error": str(exc)[:600], "llm_error": True}
        _save(task_id, report)
        return {**report, "ok": False, "reason": summary(report)}

    report = {**base, **normalize(parsed, need=need), "model": r.model}
    _save(task_id, report)
    line = summary(report)
    log.info("题 %s 改动面体检：%s", task_no, line)
    return {**report, "reason": line}


async def ensure(task_id: int) -> dict:
    """领取路径上用：已经有作数的结论就直接用，没有才花一次调用。

    题面没改过就不重体检。一道题被领取、放回、再领取是常事，每次都问一遍模型，问的
    还是同一段话，答案一样，钱白花。
    """
    if not enabled():
        return {"ok": True, "verdict": SKIPPED, "cached": True}
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "verdict": UNKNOWN, "reason": "题目不存在"}
        if settled(task):
            return {**task.scope, "ok": True, "cached": True}
    return {**await check(task_id), "cached": False}


async def warm(task_ids: list[int], concurrency: int = 4) -> dict:
    """给一批题把体检结论备齐，缺哪道跑哪道。批量领取和提前体检都走它。

    限并发而不是一把撒出去：这些调用打的是同一个网关，跟正在跑的分析、质检抢同一份
    额度，十几个并发上去只会一起撞限流，然后一起退避重试，总耗时反倒更长。
    """
    if not enabled():
        return {"checked": 0, "cached": 0, "narrow": 0}
    todo: list[int] = []
    cached = 0
    with session() as db:
        for tid in task_ids:
            task = db.get(Task, tid)
            if task is None or not (task.user_prompt or "").strip():
                continue
            # 只体检还没开跑的题。已经跑起来的判它也来不及了，废弃的更是人已经结过案
            # 的，白花一次调用还要在那道题上写一行没人要的结论。
            if task.status not in (AVAILABLE, CLAIMED):
                continue
            if settled(task):
                cached += 1
            else:
                todo.append(tid)

    sem = asyncio.Semaphore(max(1, concurrency))

    async def one(tid: int) -> dict:
        async with sem:
            return await check(tid)

    done = await asyncio.gather(*(one(t) for t in todo), return_exceptions=True)
    narrow = sum(1 for r in done if isinstance(r, dict) and r.get("verdict") == NARROW)
    return {"checked": len(todo), "cached": cached, "narrow": narrow}


# ---------------- 该体检哪些题 ----------------

def ready_ids() -> list[int]:
    """还没体检过改动面的待领题，按题号排。

    只挑还没领取的：跑起来之后再判改动面已经晚了，那时候机器时间已经花出去，而跑完
    之后有 difficulty 那道更准的关口接着。
    """
    if not enabled():
        return []
    with session() as db:
        out = [(t.task_no, t.id) for t in db.query(Task).filter(
            Task.status.in_((AVAILABLE, CLAIMED))).all()
            if (t.user_prompt or "").strip() and not settled(t)]
    return [tid for _, tid in sorted(out)]
