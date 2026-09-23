"""侧别对应：理由里挂在某一侧名下的落点，必须在那一侧自己的轨迹里找得到。

事实核验原先只对执行结果（跑没跑、测没测、构建过没过），对「这个函数、这个文件、
这种做法是哪一侧的」从来不查。于是出现过这样一句：「size 应依据 setNode 和
removeNode 返回的插入删除结果更新，A 的实现正是这样处理的」——removeNode 只在 B 的
轨迹里出现，A 叫 deleteNode。这句话里的每个词在「两侧轨迹的并集」里都找得到，所以
按并集查永远是通过，而平台的锚点核验是按侧查的，一查就打回。

按并集查等于没查。这里的口径只有一条：说 A 的就拿 A 的轨迹对，说 B 的就拿 B 的
轨迹对。只在对侧出现的叫串侧，两侧都没有的叫无据，两种都不许放行。

判侧分两档，因为中文正文里侧别不总是写在同一句里：
- 确定：落点所在的分句里、它前面就点了某一侧（「B 的 removeNode」），或者落点所在的
  那一段只有一侧当主语（「size 依据 removeNode 更新，A 的实现正是这样处理的」）。
  读的人、平台的锚点核验都会把它记在这一侧名下，串侧直接判不通过。
- 推断：这一段没点侧别、侧别从上文继承的，或者只点了一个比较对象（「结构比 B 更
  清晰」）。这一档程序不下结论，交给模型逐条判，但每一条它都必须给出判断。
「段」按句号和分号切：分号前后是两件事，「……；A 的同类验证只停留在临时脚本里」
里的 A 管不到分号前面。逗号不切，逗号接起来的「……，A 的实现正是这样处理的」
读的人就是会把前半句算到 A 头上，7130 正是这样被打回的。
无据不看侧别：两侧轨迹里都搜不到的名字，归到哪一侧都是编的。

底本只用轨迹文件本身，不掺 diff。平台核验拿的是交上去的那份轨迹，轨迹里对不上的，
diff 里有也救不回来；而代码改动本来就以 Edit / Write 的入参留在轨迹里了。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from app import config
from app.services import gsb_evidence, gsb_rules, trace

log = logging.getLogger("gsb_attribution")

HARD, SOFT = "hard", "soft"
CROSS, MISSING = "cross", "missing"

_SEG = re.compile(r"[^。！？；;\n]+[。！？；;]?")
_CLAUSE = re.compile(r"[^，,：:]+[，,：:]?")
_SIDE_TOK = re.compile(r"(?<![A-Za-z0-9_])([AB])(?![A-Za-z0-9_])")
# 比较对象。「A 优于 B」「结构比 B 更清晰」「像 B 那样」里的 B 不是这句话在说的那一侧。
_OBJ_BEFORE = re.compile(r"(?:比|不如|优于|胜于|胜过|强于|弱于|好于|逊于|差于|高于|低于|多于|少于"
                         r"|相比|相较|较|像|对比)\s*$")
_OBJ_AFTER = re.compile(r"^\s*(?:侧)?\s*(?:相比|比起来|那样|一样|类似)")
_POSSESSIVE = re.compile(r"^\s*(?:侧)?\s*的")
# 结论句里的 A/B（「因此 A 更好」「结论取 A」）说的是判给谁，不是这句话在描述谁的实现。
_VERDICT_BEFORE = re.compile(r"(?:结论|判给|取|倾向|偏向|选)\s*$")
_VERDICT_AFTER = re.compile(r"^\s*(?:侧)?\s*(?:更好|更优|胜出|占优|更胜一筹|略好|略优)")
# 说「没有 X」「X 未同步修改」的，是在断言 X 不在那里。这种话轨迹里本来就找不到 X，
# 找不到也不说明它是编的；它对不对只能读代码判，交给模型。
_NEG_BEFORE = re.compile(r"(?:没有|没|未|无|缺少|缺失|缺|不存在|并无|漏了|漏掉|不含|不带)[^，,。；;]{0,6}$")
_NEG_AFTER = re.compile(r"^[^，,。；;]{0,4}(?:没有|没|未|不存在|缺失|缺)")

_ID = r"[A-Za-z_$][A-Za-z0-9_$]*"
# 中文和英文之间常常不空格，而 Python 的 \w 认中文，\b 在「依据removeNode返回」里
# 一个边界都找不到。所以边界一律手写成 ASCII 字符类。
_NB_L = r"(?<![A-Za-z0-9_$./\-])"
_NB_R = r"(?![A-Za-z0-9_$\-])"
REF = re.compile(
    _NB_L + r"(?:"
    r"(?:[A-Za-z0-9_.\-]+/)+[A-Za-z0-9_.\-]*[A-Za-z0-9_]"          # 带目录的路径
    rf"|[A-Za-z0-9_\-]+\.(?:{gsb_rules.CODE_EXT})(?![A-Za-z0-9_])"  # 带扩展名的文件名
    rf"|{_ID}(?:\.{_ID})*(?:\(\))?"                                  # 标识符、成员访问、调用
    r")" + _NB_R)

# 正文里会出现、但不是代码落点的英文。宁可漏报也不能把正常夹在中文里的名词报成编造：
# 这里判出来的是硬项，报错一次就挡一道题的提交。
PROSE = {
    "same", "api", "apis", "cli", "gsb", "diff", "git", "github", "gitlab", "readme",
    "typescript", "javascript", "nodejs", "node.js", "vue.js", "next.js", "nuxt.js",
    "deno.land", "fastapi", "graphql", "postgresql", "mongodb", "mysql", "sqlite",
    "webassembly", "websocket", "websockets", "pypi", "npm", "pnpm", "yarn", "vitest",
    "pytest", "eslint", "prettier", "webpack", "vite", "rollup", "esbuild", "tsc",
    "http", "https", "json", "jsonl", "yaml", "toml", "utf", "ascii", "unicode",
    "claude", "cursor", "opus", "sonnet", "harness", "token", "tokens", "prompt",
    "fuzz", "fuzzing", "lint", "linter", "todo", "fixme", "e.g", "i.e", "etc",
    "nan", "infinity", "iframe", "ipv4", "ipv6", "oauth", "jwt", "uuid",
}
_CAMEL = re.compile(r"[a-z0-9][A-Z]")
_PASCAL2 = re.compile(r"^[A-Z][a-z0-9]+[A-Z]")
_UPPER_SNAKE = re.compile(r"^[A-Z][A-Z0-9]*_[A-Z0-9_]+$")


def _is_ref(tok: str) -> bool:
    """这个词是不是一个代码落点。只收形状上明确是代码的写法。"""
    core = tok[:-2] if tok.endswith("()") else tok
    if len(core) < 3 or core.lower() in PROSE:
        return False
    if "/" in core:
        return any(c.isalpha() for c in core)
    if re.fullmatch(rf"[A-Za-z0-9_\-]+\.(?:{gsb_rules.CODE_EXT})", core):
        return True
    if tok.endswith("()"):
        return True
    if "." in core:
        parts = core.split(".")
        return all(re.fullmatch(_ID, p) for p in parts) and parts[-1].lower() not in PROSE
    if "_" in core.strip("_$") or _UPPER_SNAKE.match(core):
        return True
    return bool(_CAMEL.search(core) or _PASCAL2.match(core))


def refs_in(text: str) -> list[tuple[str, int]]:
    """正文里的落点与它们的位置。"""
    return [(m.group(0), m.start()) for m in REF.finditer(text or "") if _is_ref(m.group(0))]


# ---------------- 底本 ----------------

# jsonl 里的换行、引号是转义过的：「\nremoveNode」在原文里前一个字符是 n，
# 按标识符边界找就会漏。抹成空格再找。
_JSON_ESC = re.compile(r"\\(?:[ntrbf\"\\/]|u[0-9a-fA-F]{4})")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        log.warning("读轨迹 %s 失败：%s", path, exc)
        return ""


def corpus(task_no: str, side: str) -> str:
    """一侧的轨迹全文。

    优先取导出目录里的那份，那是交给平台的原件，平台的锚点核验拿的就是它。
    导出目录没有（还没走到导出）就取证据目录里分析当时拷的那份，再没有才取容器
    轨迹目录——那里重跑过的话可能已经换成了新一轮。
    """
    paths = config.TaskPaths(task_no, side)
    parts: list[str] = []
    try:
        if paths.export.is_dir():
            parts = [_read(f) for f in sorted(paths.export.glob("*.jsonl"))]
        if not any(parts):
            d = gsb_evidence.side_dir(task_no, side)
            parts = [_read(d / n) for n in ("trace.jsonl", "steps.md") if (d / n).is_file()]
        if not any(parts):
            tf = trace.find_trace_file(paths.traces)
            parts = [_read(tf)] if tf else []
    except OSError as exc:
        log.warning("取 %s %s 侧轨迹失败：%s", task_no, side, exc)
    return _JSON_ESC.sub(" ", "\n".join(parts))


def corpora_from_files(files: dict[str, Path]) -> dict[str, str]:
    """直接拿指定的轨迹文件当底本。上传前用：核的必须是马上要交出去的那两份。"""
    return {s: _JSON_ESC.sub(" ", _read(p)) if p and p.is_file() else ""
            for s, p in files.items()}


def load_corpora(task_no: str) -> dict[str, str]:
    return {s: corpus(task_no, s) for s in config.SIDES}


def _pattern(needle: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9_$])" + re.escape(needle) + r"(?![A-Za-z0-9_$])")


def found_in(ref: str, body: str) -> bool:
    """落点在这份轨迹里有没有。

    按标识符边界找，不按子串：A 的轨迹里有 removeNodes 不等于有 removeNode，
    子串一放宽，串侧这一类就又查不出来了。
    """
    if not body:
        return False
    n = ref[:-2] if ref.endswith("()") else ref
    if _pattern(n).search(body):
        return True
    if "/" in n:
        # 正文按仓库根写路径，轨迹里是容器里的绝对路径，按末段找
        tail = n.rstrip("/").rsplit("/", 1)[-1]
        return bool(tail) and _pattern(tail).search(body) is not None
    if "." in n and not re.search(rf"\.(?:{gsb_rules.CODE_EXT})$", n):
        # 「类.方法」是正文写法，代码里未必连写；两段都要在
        return all(_pattern(p).search(body) for p in n.split("."))
    return False


# ---------------- 判侧 ----------------

def _other(side: str) -> str:
    return next(s for s in config.SIDES if s != side)


def _marks(text: str) -> list[tuple[str, int, bool, bool]]:
    """点到的侧别：(侧, 位置, 是不是主语, 能不能认领紧跟在后面的落点)。

    主语能认领；比较对象不能——「A 比 B 多了 flush()」里 flush() 是 A 的。唯一的
    例外是比较对象带了「的」：「比 B 的 removeNode 更稳」里 removeNode 就是 B 的。
    """
    out = []
    for m in _SIDE_TOK.finditer(text):
        before, after = text[:m.start()], text[m.end():]
        if _VERDICT_BEFORE.search(before) or _VERDICT_AFTER.match(after):
            continue
        subj = not (_OBJ_BEFORE.search(before) or _OBJ_AFTER.match(after))
        out.append((m.group(1), m.start(), subj, subj or bool(_POSSESSIVE.match(after))))
    return out


def _negated(clause: str, pos: int, ref: str) -> bool:
    return bool(_NEG_BEFORE.search(clause[:pos]) or _NEG_AFTER.match(clause[pos + len(ref):]))


def attributions(reason: str) -> list[dict]:
    """把正文里每个落点归到一侧。返回 [{ref, side, sure, sentence}]，side 可能为空。

    归属按从近到远三层找，找到就停：
    1. 同一个逗号分句里、落点前面最近点到的那一侧（「B 的 removeNode」「比 B 的
       removeNode」都归 B）。确定。
    2. 这一段（句号、分号之间）只有一侧当主语，归它。确定。
    3. 这一段只点了比较对象，归另一侧；什么都没点，沿用上文。推断。

    继承只在自然段内：换段通常就换了话题，上一段末尾说的 B 不该带进下一段开头。
    """
    out: list[dict] = []
    for para in (reason or "").split("\n"):
        carry = ""
        for raw in _SEG.findall(para):
            seg = raw.strip()
            if not seg:
                continue
            marks = _marks(seg)
            subj = {s for s, _, is_subj, _ in marks if is_subj}
            objs = {s for s, _, is_subj, _ in marks if not is_subj}
            if len(subj) == 1 and subj == objs:
                # 「locate.ts ……比 A 更符合要求，A 没有这层区分」：前半句的主语显然
                # 不是被拿来比的那个 A，后半句才轮到 A。整段归哪一侧说不准，只算推断。
                seg_side, seg_sure = _other(next(iter(objs))), False
            elif len(subj) == 1:
                seg_side, seg_sure = next(iter(subj)), True
            elif not subj and len(objs) == 1:
                seg_side, seg_sure = _other(next(iter(objs))), False
            elif not marks:
                seg_side, seg_sure = carry, False
            else:
                seg_side, seg_sure = "", False
            for c_raw in _CLAUSE.finditer(seg):
                clause, base = c_raw.group(0), c_raw.start()
                cm = _marks(clause)
                for r, pos in refs_in(clause):
                    before = [s for s, p, _, owns in cm if p < pos and owns]
                    if before:
                        side, sure = before[-1], True
                    elif seg_side:
                        side, sure = seg_side, seg_sure
                    else:
                        # 两侧都当了主语，落点前面又没有点侧别：按段里离它最近的
                        # 那一次点名归，只算推断
                        at = base + pos
                        prior = [s for s, p, _, _ in marks if p < at]
                        side = prior[-1] if prior else (marks[0][0] if marks else carry)
                        sure = False
                    out.append({"ref": r, "side": side, "sure": sure, "sentence": seg,
                                "negated": _negated(clause, pos, r)})
            subj_seq = [s for s, _, is_subj, _ in marks if is_subj]
            if subj_seq:
                carry = subj_seq[-1]
            elif seg_side:
                carry = seg_side
    return out


def check(reason: str, corpora: dict[str, str]) -> list[dict]:
    """逐个落点拿回它所属那一侧的轨迹里对。返回对不上的条目。

    每条是 {quote, side, ref, kind, level, why}：
    - kind=cross 串侧：只在对侧的轨迹里有；
    - kind=missing 无据：两侧的轨迹里都没有；
    - level=hard 程序认定不通过，soft 交给模型判。

    某一侧压根没有轨迹时，不拿它当「这一侧没有这个名字」的证据：没有轨迹是缺材料，
    不是轨迹里没这回事，那种情况只报给模型，不当硬项。
    """
    have = {s: bool(corpora.get(s)) for s in config.SIDES}
    if not any(have.values()):
        return []
    out: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for a in attributions(reason):
        ref, side = a["ref"], a["side"]
        hits = {s for s in config.SIDES if found_in(ref, corpora.get(s) or "")}
        if side and side in hits:
            continue
        if not side and hits:
            continue
        if not hits:
            kind = MISSING
            level = HARD if all(have.values()) else SOFT
            why = (f"{ref} 在 A、B 两侧的轨迹里都搜不到" if all(have.values())
                   else f"{ref} 在现有的轨迹里搜不到（有一侧没有轨迹，无法完全确认）")
        else:
            other = next(iter(hits))
            kind = CROSS
            if not have.get(side):
                level = SOFT
                why = f"{side} 侧没有轨迹，{ref} 只在 {other} 侧的轨迹里出现"
            else:
                level = HARD if a["sure"] else SOFT
                why = (f"这句写的是 {side} 侧，但 {ref} 只在 {other} 侧的轨迹里出现，"
                       f"{side} 侧的轨迹里没有")
                if not a["sure"]:
                    why += "（侧别是从上下文推断的，按原文确认）"
        if a.get("negated") and level == HARD:
            level = SOFT
            why += "（这句说的是它不存在或没改，按代码确认说法对不对）"
        key = (a["sentence"], ref, kind)
        if key in seen:
            continue
        seen.add(key)
        out.append({"quote": a["sentence"][:200], "side": side, "ref": ref,
                    "kind": kind, "level": level, "why": why})
    return out


def hard(reason: str, corpora: dict[str, str]) -> list[dict]:
    return [h for h in check(reason, corpora) if h["level"] == HARD]


def side_check(text: str, side: str, corpora: dict[str, str]) -> list[dict]:
    """一侧自己的文字（交付完整性描述）里的落点，逐个拿回这一侧的轨迹里对。

    描述整段都只说这一侧，不点侧别，所以不走 attributions 那套判侧：每个落点一律
    记在这一侧名下。这一侧没有轨迹时一条都不报，理由和 check 一样——缺材料不是
    轨迹里没这回事。说「没有 X」「X 未改」的照样降成软项交给模型。
    """
    body = corpora.get(side) or ""
    if not body:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for raw in _SEG.findall(text or ""):
        seg = raw.strip()
        for c_raw in _CLAUSE.finditer(seg):
            clause = c_raw.group(0)
            for ref, pos in refs_in(clause):
                if ref in seen or found_in(ref, body):
                    continue
                seen.add(ref)
                other = next((s for s in config.SIDES if s != side
                              and found_in(ref, corpora.get(s) or "")), "")
                kind = CROSS if other else MISSING
                why = (f"{ref} 只在 {other} 侧的轨迹里出现，{side} 侧的轨迹里没有" if other
                       else f"{ref} 在 {side} 侧的轨迹里搜不到")
                level = HARD
                if _negated(clause, pos, ref):
                    level = SOFT
                    why += "（这句说的是它不存在或没改，按代码确认说法对不对）"
                out.append({"quote": seg[:200], "side": side, "ref": ref,
                            "kind": kind, "level": level, "why": why})
    return out


def side_hard(text: str, side: str, corpora: dict[str, str]) -> list[dict]:
    return [h for h in side_check(text, side, corpora) if h["level"] == HARD]


def table(reason: str, corpora: dict[str, str]) -> str:
    """落点归属表：正文里每个落点分别在哪一侧的轨迹里出现过。给模型对照用。"""
    rows: list[str] = []
    done: set[str] = set()
    for a in attributions(reason):
        ref = a["ref"]
        if ref in done:
            continue
        done.add(ref)
        hits = [s for s in config.SIDES if found_in(ref, corpora.get(s) or "")]
        where = "、".join(f"{s} 侧" for s in hits) if hits else "两侧都没有"
        rows.append(f"  {ref}：出现在 {where}")
    return "\n".join(rows) or "  （正文里没有文件名或代码符号）"


def grounded(token: str, corpora: dict[str, str]) -> bool:
    """这个落点在任一侧的轨迹里有没有。改写稿换进来的名字过这一关才不算编造。"""
    return any(found_in(token, corpora.get(s) or "") for s in config.SIDES)
