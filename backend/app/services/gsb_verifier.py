"""上传前核验：红项拦住提交，黄项只提示。

拦的是平台会打回的东西，不是「写得好不好」。每一条红项都对应一条平台规则或一次
实际被打回的经历，所以宁可误报让人看一眼，也不能放过去——提交被打回的代价比
多看一眼大得多。

核验分成两半：verify 是纯函数，只看摆到面前的材料；collect 负责去库里和 git 里
把材料捞齐。分开是为了让规则本身能被直接测，不必起数据库和仓库。
"""

from __future__ import annotations

import logging
import re

from app import config
from app.db import session
from app.events import bus
from app.models import Task, TaskRun
from app.services import dockerx, gsb_repo, settings_store, trace
from app.services.gsb_analyzer import BANNED_WORDS, VERDICTS

log = logging.getLogger("gsb_verifier")

MIN_REASON_CHARS = 60
# Same 要论证两边确实等价，比直接说谁更好更费笔墨，门槛提高
MIN_SAME_REASON_CHARS = 150

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\uFE0F\u2705\u274C]")
_MD_MARK = re.compile(r"(^\s{0,3}#{1,6}\s)|(^\s{0,3}[-*+]\s)|(\*\*)|(`)", re.M)
_ABS_PATH = re.compile(r"(?<![\w.])/(?:[A-Za-z0-9_.\-\u4e00-\u9fff]+/)+")
_STEP_REF = re.compile(r"第\s*\d+\s*[步轮]|步骤\s*\d+")
# 理由里对文件的引用：带目录的路径，或者带常见扩展名的文件名
_FILE_REF = re.compile(
    r"\b(?:[\w.\-]+/)+[\w.\-]+\.\w{1,6}\b"
    r"|\b[\w\-]+\.(?:py|js|mjs|cjs|ts|tsx|jsx|go|rs|java|rb|php|c|h|cc|cpp|hpp|cs|swift|kt"
    r"|json|ya?ml|toml|ini|cfg|md|txt|sh|sql|html|css|scss|vue|svelte)\b")


def _item(name: str, level: str, message: str) -> dict:
    return {"name": name, "level": level, "message": message}


def _chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def _norm_prompt(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def verify(data: dict) -> dict:
    """按平台规则核验。data 的形状见 collect 的返回值。"""
    items: list[dict] = []
    reason = data.get("reason") or ""
    verdict = data.get("verdict") or ""
    sides: dict = data.get("sides") or {}

    # ---- 结论与理由 ----
    if verdict not in VERDICTS:
        items.append(_item("verdict", "block", f"结论「{verdict or '空'}」不是 A、B、Same 之一"))
    n = _chars(reason)
    floor = MIN_SAME_REASON_CHARS if verdict == "Same" else MIN_REASON_CHARS
    if n < floor:
        extra = "，Same 要论证两边确实等价，比选边更费笔墨" if verdict == "Same" else ""
        items.append(_item("reason_length", "block",
                           f"理由去掉空白只有 {n} 字，不足 {floor} 字{extra}"))
    if not re.search(r"\bA\b|A\s*侧", reason) or not re.search(r"\bB\b|B\s*侧", reason):
        items.append(_item("reason_both_sides", "block", "理由里没有分别写到 A 和 B 两侧"))

    if hits := [w for w in BANNED_WORDS if w in reason]:
        items.append(_item("reason_banned_words", "block",
                           f"理由里有禁用词：{'、'.join(hits[:8])}"))
    if _MD_MARK.search(reason):
        items.append(_item("reason_markdown", "block",
                           "理由里有 markdown 记号（标题、列表符号、加粗或反引号），平台的理由框不渲染"))
    if _EMOJI.search(reason):
        items.append(_item("reason_emoji", "block", "理由里有表情符号"))
    if m := _ABS_PATH.search(reason):
        items.append(_item("reason_abs_path", "block",
                           f"理由里有绝对路径（{m.group(0)[:40]}），会把本机目录结构一起交出去"))
    if m := _STEP_REF.search(reason):
        items.append(_item("reason_step_ref", "block",
                           f"理由里有步数说法（{m.group(0)}），位置该用文件名和函数名来指"))

    # ---- 理由提到的文件必须真实存在（G6）----
    known = set()
    for s in sides.values():
        known |= {str(f) for f in (s.get("files") or [])}
    if known:
        refs = {r for r in _FILE_REF.findall(reason)}
        missing = sorted(r for r in refs
                         if not any(k == r or k.endswith("/" + r) or r.endswith("/" + k)
                                    for k in known))
        if missing:
            items.append(_item("reason_unknown_files", "block",
                               f"理由提到的文件在两侧的轨迹和产物里都找不到：{'、'.join(missing[:6])}"))

    # ---- 两侧的硬性材料 ----
    for side in config.SIDES:
        s = sides.get(side)
        if not s:
            items.append(_item(f"side_{side}", "block", f"缺少 {side} 侧的材料"))
            continue
        if not s.get("session_id"):
            items.append(_item(f"session_{side}", "block", f"{side} 侧没有 SessionID"))
        sha = (s.get("artifact_sha") or "").lower()
        if not _SHA40.match(sha):
            items.append(_item(f"artifact_{side}", "block",
                               f"{side} 侧的产物快照不是 40 位 SHA：{sha or '空'}"))
        elif (parent := (s.get("parent_sha") or "").lower()) and parent != data.get("env_snapshot_sha"):
            # 父提交必须是初始快照，否则交上去的 diff 里混着别人的改动（规则 G3）
            items.append(_item(f"parent_{side}", "block",
                               f"{side} 侧产物快照的父提交是 {parent[:12]}，不是初始快照 "
                               f"{(data.get('env_snapshot_sha') or '')[:12]}"))
        tc = s.get("trace_count")
        if tc != 1:
            items.append(_item(f"trace_count_{side}", "block",
                               f"{side} 侧有 {tc} 份轨迹 jsonl，平台只收一份（规则 T4）"))
        ht = s.get("human_turns")
        if ht != 1:
            items.append(_item(f"human_turns_{side}", "block",
                               f"{side} 侧轨迹里真人输入有 {ht} 轮，必须恰好一轮（规则 T5）"))
        if not s.get("changed_files"):
            items.append(_item(f"changed_{side}", "warn", f"{side} 侧工作目录零改动"))

    # ---- 两侧之间的关系 ----
    a, b = sides.get("A") or {}, sides.get("B") or {}
    if a.get("session_id") and a.get("session_id") == b.get("session_id"):
        items.append(_item("session_same", "block",
                           "两侧的 SessionID 相同，说明交的是同一次跑（规则 G9）"))
    if a.get("artifact_sha") and a.get("artifact_sha") == b.get("artifact_sha"):
        items.append(_item("artifact_same", "block", "两侧的产物快照相同，说明交的是同一份代码"))
    # 两侧必须收到一模一样的题面，否则比的不是同一道题（规则 G4）
    pa, pb = _norm_prompt(a.get("prompt")), _norm_prompt(b.get("prompt"))
    want = _norm_prompt(data.get("user_prompt"))
    if pa and pb and pa != pb:
        items.append(_item("prompt_mismatch", "block", "两侧轨迹里的 prompt 不一致（规则 G4）"))
    elif want and pa and pa != want:
        items.append(_item("prompt_mismatch", "block",
                           "轨迹里的 prompt 与题块记录的不一致（规则 G4）"))

    # ---- 提示项 ----
    iv, hv = data.get("image_version"), data.get("harness_version")
    if iv and hv and iv != hv:
        items.append(_item("harness_version", "warn",
                           f"题块记录的 Harness 版本是 {hv}，镜像实测是 {iv}，上传以实测为准"))

    levels = {i["level"] for i in items}
    overall = "block" if "block" in levels else ("warn" if "warn" in levels else "ok")
    return {"overall": overall, "items": items,
            "blocked": len([i for i in items if i["level"] == "block"]),
            "warnings": len([i for i in items if i["level"] == "warn"])}


_SCAN_SKIP = {".git", "node_modules", ".venv", "__pycache__"}


def _side_files(task_no: str, side: str, index: dict) -> list[str]:
    """这一侧可被理由引用的文件：轨迹里碰过的，加产物副本里实际存在的。"""
    files = set()
    for step in (index.get("steps") or []):
        for f in (step.get("files") or []):
            if isinstance(f, str) and f.strip():
                files.add(f.strip().lstrip("./"))
    repo = config.TaskPaths(task_no, side).analysis_repo
    if repo.is_dir():
        for p in repo.rglob("*"):
            if p.is_file() and not any(part in _SCAN_SKIP for part in p.parts):
                files.add(str(p.relative_to(repo)))
    return sorted(files)


async def collect(task_id: int) -> dict:
    """把核验要看的材料捞齐。"""
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {}
        runs = {r.side: r for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()}
        gsb = task.gsb
        data = {
            "verdict": gsb.get("verdict", ""),
            "reason": gsb.get("reason", ""),
            "user_prompt": task.user_prompt,
            "env_snapshot_sha": gsb_repo.snapshot_sha(task.env_snapshot),
            "harness_version": task.harness_version,
            "sides": {},
        }
        task_no = task.task_no
        side_meta = {s: {"session_id": r.session_id, "artifact_sha": r.artifact_sha,
                         "changed_files": (r.verdict.get("artifact") or {}).get("changed_files"),
                         "trace_summary": r.trace_summary}
                     for s, r in runs.items()}

    for side, meta in side_meta.items():
        paths = config.TaskPaths(task_no, side)
        index = {}
        if paths.trace_index.exists():
            try:
                import json

                index = json.loads(paths.trace_index.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                index = {}
        summary = meta["trace_summary"] or {}
        parent = ""
        if meta["artifact_sha"]:
            r = await dockerx.run(["git", "-C", str(paths.workspace), "rev-parse",
                                   f"{meta['artifact_sha']}^"], timeout=30)
            parent = r.out.strip().lower() if r.ok else ""
        data["sides"][side] = {
            "session_id": meta["session_id"],
            "artifact_sha": meta["artifact_sha"],
            "parent_sha": parent,
            "changed_files": meta["changed_files"],
            "trace_count": trace.count_traces(paths.traces) if paths.traces.exists() else 0,
            "human_turns": summary.get("human_turns", index.get("human_turns")),
            "prompt": summary.get("prompt") or index.get("prompt") or "",
            "files": _side_files(task_no, side, index),
        }

    image = settings_store.get("cc.image")
    data["image_version"] = await dockerx.claude_version(image) if image else ""
    return data


async def run_verify(task_id: int) -> dict:
    data = await collect(task_id)
    if not data:
        return {}
    report = verify(data)
    with session() as db:
        task = db.get(Task, task_id)
        if task is not None:
            task.verify = report
    bus.publish("tasks", {"type": "task", "id": task_id})
    return report
