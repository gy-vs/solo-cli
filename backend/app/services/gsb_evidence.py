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

def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


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

    比对前去掉全部空白：模型转抄时常把缩进和折行改掉，那不算改内容，按原样比会把
    绝大多数正确引用判成编的。反过来，去掉空白之后仍然找不到的那种，就是它自己
    写出来的句子。
    """
    kept: list[dict] = []
    dropped: list[dict] = []
    bodies: dict[str, str] = {}
    for e in evidence:
        if not isinstance(e, dict):
            continue
        side = str(e.get("side") or "").strip().upper()[:1]
        quote = str(e.get("quote") or "").strip()
        if side not in config.SIDES:
            dropped.append({**e, "why": f"side 不是 A 或 B：{side or '空'}"})
            continue
        if len(_squash(quote)) < MIN_QUOTE_CHARS:
            dropped.append({**e, "why": f"quote 太短，不足 {MIN_QUOTE_CHARS} 个字符"})
            continue
        if side not in bodies:
            bodies[side] = _squash(corpus(task_no, side))
        if _squash(quote) in bodies[side]:
            kept.append(e)
        else:
            dropped.append({**e, "why": f"这段话在 {side} 侧的轨迹和补丁里都找不到"})
    return kept, dropped
