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
from app.services import dockerx, gsb_analyzer, gsb_repo, gsb_rules, settings_store, trace
from app.services.gsb_analyzer import VERDICTS

log = logging.getLogger("gsb_verifier")

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
# 理由里对文件的引用：带目录的路径，或者带常见扩展名的文件名
_FILE_REF = re.compile(
    r"\b(?:[\w.\-]+/)+[\w.\-]+\.\w{1,6}\b"
    r"|\b[\w\-]+\.(?:py|js|mjs|cjs|ts|tsx|jsx|go|rs|java|rb|php|c|h|cc|cpp|hpp|cs|swift|kt"
    r"|json|ya?ml|toml|ini|cfg|md|txt|sh|sql|html|css|scss|vue|svelte)\b")


def _item(name: str, level: str, message: str) -> dict:
    return {"name": name, "level": level, "message": message}


def _ver(text: str) -> str:
    """只取版本号本身。

    题块里记的是「2.1.197 (Claude Code)」，镜像实测只给「2.1.197」，直接比字符串
    会把每道题都判成版本对不上。带不带这个后缀是出题时的书写差异，不是版本差异。
    """
    m = re.search(r"\d+(?:\.\d+)+", text or "")
    return m.group(0) if m else (text or "").strip()


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
    # 只看理由文本的那些规则由 gsb_rules 统一给，分析生成时自查用的是同一个函数
    items.extend(_item(name, level, message) for name, level, message in
                 gsb_rules.reason_checks(reason, verdict=verdict,
                                         peer_openings=data.get("peer_openings") or {}))

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
    if iv and hv and _ver(iv) != _ver(hv):
        items.append(_item("harness_version", "warn",
                           f"题块记录的 Harness 版本是 {hv}，镜像实测是 {iv}，上传以实测为准"))

    levels = {i["level"] for i in items}
    overall = "block" if "block" in levels else ("warn" if "warn" in levels else "ok")
    return {"overall": overall, "items": items,
            "blocked": len([i for i in items if i["level"] == "block"]),
            "warnings": len([i for i in items if i["level"] == "warn"])}


async def _side_files(task_no: str, side: str, index: dict) -> list[str]:
    """这一侧可被理由引用的文件：轨迹里碰过的，加仓库里实际跟踪的。

    以前这里扫的是分析沙箱副本，沙箱随 agent 漫游一起取消了，改问 git。git ls-files
    只列被跟踪的文件，node_modules 这类本来就不在里面，也就不必再自己过滤一遍。
    """
    files = set()
    for step in (index.get("steps") or []):
        for f in (step.get("files") or []):
            if isinstance(f, str) and f.strip():
                files.add(f.strip().lstrip("./"))
    ws = config.TaskPaths(task_no, side).workspace
    if (ws / ".git").exists():
        r = await dockerx.run(["git", "-C", str(ws), "ls-files"], timeout=60)
        if r.ok:
            files.update(line.strip() for line in r.out.splitlines() if line.strip())
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
            "peer_openings": gsb_analyzer.peer_openings(db, task_id),
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
            "files": await _side_files(task_no, side, index),
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
