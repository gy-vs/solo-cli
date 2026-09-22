"""把两侧的全量材料摊到一个只读目录，交给分析那一步的 agent 自己去读。

原先材料全部拼进 prompt，于是每一样都得先过一遍预算：补丁给到 40000 字符就截断，
轨迹压成一行一步、每步 120 字、最多 140 步。压缩本身没错——一次请求装不下几 MB
的轨迹——但代价是模型看到的过程是有洞的：工具返回被切在第 120 个字符，报错的用例名
在第 400 个字符上；步数超过 140 的那批还要等距抽样，中间发生了什么根本没送进去。
拿这种材料去判"哪一侧绕了远路"，判得再认真也只是在归纳摘要，不是在读轨迹。

换个摆法就不必压缩：材料落成文件，agent 用读文件的方式按需取。--mode ask 不放开
shell，工作目录又钉在这个 evidence 目录上，它能读的就只有我们摆进去的这些，读不到
仓库本体，也读不到别的题——受控这一点和原来一样，只是不再需要提前替它决定看哪 140 步。

摆两份是有意的。steps.md 是按顺序读的全文，工具的完整入参和完整返回都在，通读一遍
就知道这一侧干了什么；trace.jsonl 是原样拷贝的轨迹，逐字核对时查它。两份加上补丁
构成 corpus()，模型交回来的每一条 evidence 都要能在里面逐字找到，找不到就是编的。
这道回查同时是一个探针：它要是压根没读文件，直接照着 prompt 里的概览编，quote 一条
都对不上，分析这一步会当场失败而不是安静地交一份看着像样的结论。
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from app import config
from app.services import trace

log = logging.getLogger("gsb_evidence")

EVIDENCE_DIR = "evidence"
# quote 短到几个字符时，随便什么材料里都能找到一段一样的，回查就失去意义了。
# 六个字符是按中文两三个词、英文一个标识符定的。
MIN_QUOTE_CHARS = 6


def root(task_no: str) -> Path:
    return config.TaskPaths(task_no).analysis / EVIDENCE_DIR


def side_dir(task_no: str, side: str) -> Path:
    return root(task_no) / side


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build(task_no: str, user_prompt: str, materials: dict[str, dict]) -> Path:
    """摆好证据目录，返回目录路径。

    每次分析都重摆一遍：重新分析往往是因为上一次跑的产物换了，留着上一轮的补丁
    会让 agent 读到一份和当前 HEAD 对不上的材料，而它无从分辨。
    """
    base = root(task_no)
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)

    _write(base / "prompt.md", user_prompt or "（题面为空）")
    for side, m in materials.items():
        d = base / side
        d.mkdir(parents=True, exist_ok=True)
        _write(d / "diff.patch", m.get("patch") or "（这一侧没有代码改动）\n")
        _write(d / "files.txt", "\n".join(m.get("files") or []) or "（没有改动文件）")
        tf = trace.find_trace_file(config.TaskPaths(task_no, side).traces)
        if tf and tf.is_file():
            shutil.copyfile(tf, d / "trace.jsonl")
            try:
                _write(d / "steps.md", trace.dump_steps(tf))
            except OSError as exc:
                log.warning("GSB %s %s 侧摊轨迹失败：%s", task_no, side, exc)
                _write(d / "steps.md", f"（轨迹读取失败：{exc}）")
        else:
            _write(d / "steps.md", "（这一侧没有轨迹文件）")

    _write(base / "README.md", _readme(materials))
    log.info("GSB %s 证据目录已摆好：%s", task_no, base)
    return base


def _readme(materials: dict[str, dict]) -> str:
    lines = ["这个目录里是两次运行的全部材料，判断只能基于这里的内容。", "",
             "prompt.md  两侧收到的题面，完全相同", ""]
    for side in sorted(materials):
        m = materials[side] or {}
        lines += [f"{side}/steps.md    {side} 侧的轨迹全文，按顺序一步一步读，"
                  f"工具的入参和返回都是完整的",
                  f"{side}/trace.jsonl {side} 侧的原始轨迹，逐字核对时查这一份",
                  f"{side}/diff.patch  {side} 侧的完整补丁，没有截断",
                  f"{side}/files.txt   {side} 侧的改动文件清单", ""]
    return "\n".join(lines)


# ---------------- 逐字回查 ----------------
# 比对前材料和 quote 都要过同一道归一化，抹掉两类不算改内容的差异。
#
# 一类是空白：转抄时改掉缩进和折行是常事。
#
# 另一类是行首记号。引一段代码注释，抄回来的是注释文字，`//` 和折行处的 `*` 不会
# 跟着抄——材料里是 `// Only functions actually exhibiting the clash are touched,
# so the\n// analysis ... is unchanged.`，交回来的是连成一句的同一段话。补丁的 +/-
# 行首标记同理，带不带全看它抄的是补丁还是文件内容。这些都不是编造，按原样比会把
# 有据的引用判成编的，所以在这里一起抹掉；只在行首生效，行内一个字不动。
# 记号可能叠着来：补丁里的注释行是 `+// ...`，两层都要吃掉，所以整组带量词。
# 每个分支都至少吃掉一个字符，不会在原地打转。
_LINE_LEAD = re.compile(r"(?m)^(?:[ \t]*(?://+|/\*+|\*+/|\*|#+|;+|[-+]+))+[ \t]*")
# 独立成段的省略号：跨行取材时用它把两段原文接起来。行内的 ...args 不是这个用法，
# 所以要求两侧是空白或首尾。
_GAP = re.compile(r"(?:(?<=\s)|^)(?:\.{3,}|…)(?=\s|$)")


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", _LINE_LEAD.sub("", text or ""))


def _appears_in(body: str, quote: str) -> bool:
    """quote 是否出自 body。body 与 quote 都要先过 _norm。

    带省略号的拆成几段依次找，且每段只在上一段之后的位置里找。分段是为了容忍
    「取两段、中间用省略号接上」这种转抄；限定顺序是因为不限顺序就等于放过「把
    两处不相干的话拼成一条证据」，而那恰恰是这道回查要拦的。
    """
    parts = [p for p in (_norm(p) for p in _GAP.split(quote)) if p]
    if not parts:
        return False
    at = 0
    for part in parts:
        i = body.find(part, at)
        if i < 0:
            return False
        at = i + len(part)
    return True


def corpus(task_no: str, side: str) -> str:
    """一侧的全部材料原文，拼成一段用于回查。

    三份都要拼上。模型引代码时抄的是 diff.patch，引过程时抄的多半是 steps.md，
    而 steps.md 里的工具返回被限额切过，超限那一段只在 trace.jsonl 里，少拼一份
    就会把一条本来有据的引用判成编的。
    """
    d = side_dir(task_no, side)
    parts: list[str] = []
    for name in ("steps.md", "diff.patch", "trace.jsonl"):
        f = d / name
        if f.is_file():
            try:
                parts.append(f.read_text(encoding="utf-8", errors="replace"))
            except OSError as exc:
                log.warning("GSB %s 读 %s 失败：%s", task_no, f, exc)
    return "\n".join(parts)


def sides_with_material(task_no: str) -> set[str]:
    """哪几侧确实有东西可引。

    一侧可能既没跑出改动也没留下轨迹（容器起来就挂了是最常见的一种）。那一侧引不出
    原文是事实，不该按「没读材料」论处，所以门槛只对有材料的侧生效。
    """
    out = set()
    for side in config.SIDES:
        d = side_dir(task_no, side)
        for name in ("steps.md", "diff.patch", "trace.jsonl"):
            f = d / name
            # 占位文件只有一行「（这一侧没有轨迹文件）」，按大小就能筛掉
            if f.is_file() and f.stat().st_size > 200:
                out.add(side)
                break
    return out


def check_quotes(task_no: str, evidence: list[dict]) -> tuple[list[dict], list[dict]]:
    """把每条 evidence 的 quote 拿回材料里对一遍，返回 (对得上的, 对不上的)。

    归一化之后仍然找不到的那种，就是它自己写出来的句子。
    """
    kept: list[dict] = []
    dropped: list[dict] = []
    bodies: dict[str, str] = {}

    def body(side: str) -> str:
        if side not in bodies:
            bodies[side] = _norm(corpus(task_no, side))
        return bodies[side]

    for e in evidence:
        if not isinstance(e, dict):
            continue
        side = str(e.get("side") or "").strip().upper()[:1]
        quote = str(e.get("quote") or "").strip()
        if side not in config.SIDES:
            dropped.append({**e, "why": f"side 不是 A 或 B：{side or '空'}"})
            continue
        if len(_norm(quote)) < MIN_QUOTE_CHARS:
            dropped.append({**e, "why": f"quote 太短，不足 {MIN_QUOTE_CHARS} 个字符"})
            continue
        if _appears_in(body(side), quote):
            kept.append(e)
            continue
        # 找不到时再看对侧。同一段话在另一侧找得到，说明引用是真的、只是 side 标错了。
        # 这和凭空编一句要修的地方不同，分开说人才不用自己再去两侧翻一遍。
        other = next(s for s in config.SIDES if s != side)
        if _appears_in(body(other), quote):
            dropped.append({**e, "why": f"这段话出自 {other} 侧的材料，side 却标成了 {side}"})
        else:
            dropped.append({**e, "why": f"这段话在 {side} 侧的轨迹和补丁里都找不到"})
    return kept, dropped
