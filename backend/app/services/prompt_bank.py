"""prompt.md 题库：解析、增量导入、回填。

文件格式（实测）：
    题号：01
    <空行>
    对应项目
    仓库：https://…
    …
    提交参数
    任务类型：0-1 代码生成
    …
    SessionID：待回填，取轨迹 jsonl 文件名的 UUID
    TurnID/PromptID：待回填，取本轮 user 消息的 promptId
    <空行>
    以下为发送给模型的 prompt 正文，整段复制。
    <空行>
    <正文…直到下一个「题号：」或文件末尾>

回填只改 SessionID / TurnID 两行的值，其余字节不动。
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app import config
from app.db import session
from app.models import AVAILABLE, ORIGIN_BANK, Task

BODY_MARKER = "以下为发送给模型的 prompt 正文，整段复制。"
_TASK_LINE = re.compile(r"^题号[：:]\s*(\S+)\s*$")
_KV_LINE = re.compile(r"^([^：:]{1,40})[：:]\s*(.*)$")

# prompt.md 键 → Task 字段
FIELD_MAP = {
    "任务类型": "question_type",
    "任务难度": "difficulty",
    "语言/框架": "languages",
    "Harness": "harness",
    "Harness 版本": "harness_version",
    "Harness版本": "harness_version",
    "操作系统": "os_platform",
    "环境可复现等级": "repro_level",
    "初始环境快照": "env_snapshot",
    "SessionID": "session_id",
    "TurnID/PromptID": "turn_id",
}
META_KEYS = ("仓库", "本地路径", "容器工作目录", "轨迹目录", "来源说明")


@dataclass
class ParsedTask:
    task_no: str
    fields: dict[str, str] = field(default_factory=dict)
    meta: dict[str, str] = field(default_factory=dict)
    user_prompt: str = ""
    line_start: int = 0   # 题块起止行号（0-based，含头不含尾）
    line_end: int = 0

    @property
    def prompt_hash(self) -> str:
        return hashlib.sha256(self.user_prompt.strip().encode("utf-8")).hexdigest()


def split_blocks(lines: list[str]) -> list[tuple[int, int]]:
    starts = [i for i, line in enumerate(lines) if _TASK_LINE.match(line.rstrip("\n"))]
    blocks = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        blocks.append((start, end))
    return blocks


def parse_block(lines: list[str], start: int, end: int) -> ParsedTask:
    head = lines[start].rstrip("\n")
    m = _TASK_LINE.match(head)
    task = ParsedTask(task_no=m.group(1) if m else "", line_start=start, line_end=end)
    body_at = None
    for i in range(start + 1, end):
        text = lines[i].rstrip("\n")
        if text.strip() == BODY_MARKER:
            body_at = i
            break
        kv = _KV_LINE.match(text)
        if not kv:
            continue
        key, value = kv.group(1).strip(), kv.group(2).strip()
        if key in META_KEYS:
            task.meta[key] = value
        elif key in FIELD_MAP:
            task.fields[FIELD_MAP[key]] = value
    if body_at is not None:
        body = "".join(lines[body_at + 1:end])
        task.user_prompt = body.strip("\n").rstrip() + "\n" if body.strip() else ""
        task.user_prompt = task.user_prompt.strip()
    return task


def parse_text(text: str) -> list[ParsedTask]:
    lines = text.splitlines(keepends=True)
    return [parse_block(lines, s, e) for s, e in split_blocks(lines)]


def parse_file(path: Path | None = None) -> list[ParsedTask]:
    path = path or config.prompt_file()
    if not path.exists():
        return []
    return parse_text(path.read_text(encoding="utf-8"))


def _pending_value(v: str) -> bool:
    return (not v) or v.startswith("待回填")


def archive_files() -> list[Path]:
    """出题/prompts/ 下的单题归档。/solo-prompt 批量出题时每题一个文件。"""
    d = config.CODER_ROOT_MOUNT / config.PROMPTS_ARCHIVE_DIR
    return sorted(d.glob("*.md")) if d.exists() else []


def parse_sources(extra: list[Path] | None = None) -> list[ParsedTask]:
    """根目录 prompt.md + 归档目录。同题以先出现的为准（根目录优先）。"""
    seen: set[tuple[str, str]] = set()
    out: list[ParsedTask] = []
    for path in [config.prompt_file(), *(extra if extra is not None else archive_files())]:
        for p in parse_file(path):
            if not (p.task_no and p.user_prompt):
                continue
            key = (p.task_no, p.prompt_hash)
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    return out


def import_tasks(*, sources: list[Path] | None = None, origin: str = ORIGIN_BANK,
                 design_run_id: int = 0) -> dict:
    """增量导入：唯一键 task_no + prompt 正文哈希。返回统计（含新建任务 id）。"""
    parsed = parse_sources(sources)
    added, added_ids, skipped = [], [], 0
    with session() as db:
        existing = {
            (t.task_no, t.prompt_hash) for t in db.execute(select(Task)).scalars()
        }
        for p in parsed:
            key = (p.task_no, p.prompt_hash)
            if key in existing:
                skipped += 1
                continue
            t = Task(task_no=p.task_no, prompt_hash=p.prompt_hash, status=AVAILABLE,
                     user_prompt=p.user_prompt, origin=origin, design_run_id=design_run_id)
            t.meta = p.meta
            for fk, fv in p.fields.items():
                if fk in ("session_id", "turn_id") and _pending_value(fv):
                    continue
                setattr(t, fk, fv)
            t.container_name = config.TaskPaths(p.task_no).container_name
            db.add(t)
            db.flush()
            added.append(p.task_no)
            added_ids.append(t.id)
    return {"parsed": len(parsed), "added": added, "added_ids": added_ids, "skipped": skipped}


def _rewrite_block(lines: list[str], start: int, end: int, session_id: str, turn_id: str) -> tuple[list[str], int]:
    changed = 0
    for i in range(start, end):
        text = lines[i]
        stripped = text.rstrip("\r\n")
        eol = text[len(stripped):]
        kv = _KV_LINE.match(stripped)
        if not kv:
            continue
        key = kv.group(1).strip()
        sep_idx = stripped.find("：") if "：" in stripped else stripped.find(":")
        prefix = stripped[: sep_idx + 1]
        if key == "SessionID" and session_id:
            lines[i] = f"{prefix}{session_id}{eol}"
            changed += 1
        elif key == "TurnID/PromptID" and turn_id:
            lines[i] = f"{prefix}{turn_id}{eol}"
            changed += 1
    return lines, changed


def backfill_file(path: Path, task_no: str, prompt_hash: str, session_id: str, turn_id: str) -> int:
    """在单个文件中定位题块（题号 + 正文哈希双重匹配）并回填。返回修改行数。"""
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    total = 0
    for s, e in split_blocks(lines):
        p = parse_block(lines, s, e)
        if p.task_no != task_no or p.prompt_hash != prompt_hash:
            continue
        lines, changed = _rewrite_block(lines, s, e, session_id, turn_id)
        total += changed
    if total:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, path.with_name(f"{path.name}.bak.{stamp}"))
        path.write_text("".join(lines), encoding="utf-8")
    return total


def backfill(task: Task) -> dict:
    """回填 prompt.md 与 出题/prompts/NN.md。"""
    paths = config.TaskPaths(task.task_no)
    results = {}
    for label, path in (("prompt.md", config.prompt_file()), ("archive", paths.prompt_archive)):
        try:
            results[label] = backfill_file(path, task.task_no, task.prompt_hash, task.session_id, task.turn_id)
        except OSError as exc:
            results[label] = f"error: {exc}"
    return results
