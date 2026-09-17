"""Claude Code 轨迹 jsonl 解析：SessionID、PromptID、步骤索引。

步骤索引供 Cursor 分析引用与后端交叉核验：
    steps[i] = {step, ts, kind: tool|text, tool, summary, files[], result, is_error, uuid}
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models import as_utc

_FILE_TOKEN = re.compile(r"(?<![\w/])((?:\.{0,2}/)?[\w.\-]+(?:/[\w.\-]+)*\.[A-Za-z0-9]{1,8})(?![\w/])")


def find_trace_file(traces_dir: Path, since: datetime | None = None) -> Path | None:
    """找本轮的轨迹。

    轨迹目录按题号复用，重跑时上一轮的 jsonl 还躺在里面。给了 since 就只认
    这个时间之后写过的文件，否则一次没产出轨迹的运行会把旧 session 当成自己的
    回填进 prompt.md。放宽 60 秒，容忍容器与宿主的时钟偏差。
    """
    if not traces_dir.exists():
        return None
    files = [p for p in traces_dir.rglob("*.jsonl") if p.is_file()]
    if since is not None:
        floor = as_utc(since).timestamp() - 60
        files = [p for p in files if p.stat().st_mtime >= floor]
    if not files:
        return None
    # 一题一份；若有多份取最大（最完整）的那份，并在 summary 中标记
    files.sort(key=lambda p: (p.stat().st_size, p.stat().st_mtime), reverse=True)
    return files[0]


def count_traces(traces_dir: Path, since: datetime | None = None) -> int:
    if not traces_dir.exists():
        return 0
    files = [p for p in traces_dir.rglob("*.jsonl") if p.is_file()]
    if since is not None:
        floor = as_utc(since).timestamp() - 60
        files = [p for p in files if p.stat().st_mtime >= floor]
    return len(files)


def _text_of(content: Any, limit: int = 400) -> str:
    if isinstance(content, str):
        return content[:limit]
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif block.get("type") == "tool_result":
                    parts.append(_text_of(block.get("content"), limit))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts).strip()[:limit]
    return ""


def _files_from_input(name: str, inp: dict) -> list[str]:
    files: list[str] = []
    for key in ("file_path", "path", "notebook_path"):
        v = inp.get(key)
        if isinstance(v, str) and v:
            files.append(v)
    if name == "Bash":
        cmd = str(inp.get("command", ""))
        files.extend(m for m in _FILE_TOKEN.findall(cmd) if not m.startswith("http"))
    return list(dict.fromkeys(files))[:12]


def _tool_summary(name: str, inp: dict) -> str:
    if name == "Bash":
        return f"$ {str(inp.get('command', ''))[:200]}"
    if name in ("Read", "Write", "Edit", "MultiEdit", "NotebookEdit"):
        return f"{name} {inp.get('file_path') or inp.get('notebook_path') or ''}"
    if name in ("Glob", "Grep"):
        return f"{name} {inp.get('pattern', '')} {inp.get('path', '') or ''}".strip()
    if name in ("Task", "Agent"):
        return f"{name} {str(inp.get('description') or inp.get('prompt', ''))[:120]}"
    return f"{name} {json.dumps(inp, ensure_ascii=False)[:160]}"


def parse_trace(path: Path) -> dict:
    session_id = ""
    prompt_id = ""
    first_user_text = ""
    prompt_text = ""
    steps: list[dict] = []
    by_tool_use: dict[str, dict] = {}
    # human_turns 是真人真正说话的轮数。平台要求恰好一轮（规则 T5）：多一轮说明
    # 中途人工介入指导过，这次跑就不能代表模型自己的水平。type=user 的行里绝大多数
    # 是工具返回，必须把它们排除掉才数得准。
    counts = {"user": 0, "assistant": 0, "tool_calls": 0, "tool_errors": 0, "lines": 0}
    human_turns = 0
    first_ts = last_ts = ""
    last_assistant_text = ""
    stop_reason = ""
    model = ""
    harness_version = ""
    cwd = ""

    with path.open("r", encoding="utf-8", errors="replace") as fp:
        for raw in fp:
            raw = raw.strip()
            if not raw:
                continue
            counts["lines"] += 1
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not session_id and obj.get("sessionId"):
                session_id = str(obj["sessionId"])
            # 上传时 harness_version 必须与轨迹一致，否则质检的交叉校验会打回
            if not harness_version and obj.get("version"):
                harness_version = str(obj["version"])
            if not cwd and obj.get("cwd"):
                cwd = str(obj["cwd"])
            ts = obj.get("timestamp") or ""
            if ts:
                first_ts = first_ts or ts
                last_ts = ts
            typ = obj.get("type")
            msg = obj.get("message") or {}
            content = msg.get("content")
            if typ == "user":
                counts["user"] += 1
                is_tool_result = isinstance(content, list) and any(
                    isinstance(b, dict) and b.get("type") == "tool_result" for b in content
                )
                if is_tool_result:
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            step = by_tool_use.get(str(b.get("tool_use_id")))
                            if step is not None:
                                step["result"] = _text_of(b.get("content"), 300)
                                step["is_error"] = bool(b.get("is_error"))
                                if step["is_error"]:
                                    counts["tool_errors"] += 1
                elif not obj.get("isSidechain"):
                    # 子会话（isSidechain）里的 user 行是 Task 工具派出去的子代理在自问自答，
                    # 不是真人；算进去的话用了 Task 工具的题全都会被判成多轮人工介入
                    human_turns += 1
                    if not prompt_id and obj.get("promptId"):
                        prompt_id = str(obj["promptId"])
                    if not first_user_text:
                        first_user_text = _text_of(content, 200)
                    if not prompt_text:
                        prompt_text = _text_of(content, 100000)
            elif typ == "assistant":
                counts["assistant"] += 1
                model = msg.get("model") or model
                stop_reason = msg.get("stop_reason") or stop_reason
                if isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "tool_use":
                            counts["tool_calls"] += 1
                            name = str(b.get("name", ""))
                            inp = b.get("input") or {}
                            step = {
                                "step": len(steps) + 1,
                                "ts": ts,
                                "kind": "tool",
                                "tool": name,
                                "summary": _tool_summary(name, inp if isinstance(inp, dict) else {}),
                                "files": _files_from_input(name, inp if isinstance(inp, dict) else {}),
                                "result": "",
                                "is_error": False,
                                "uuid": obj.get("uuid", ""),
                            }
                            steps.append(step)
                            by_tool_use[str(b.get("id"))] = step
                        elif b.get("type") == "text" and str(b.get("text", "")).strip():
                            text = str(b["text"]).strip()
                            last_assistant_text = text
                            steps.append({
                                "step": len(steps) + 1,
                                "ts": ts,
                                "kind": "text",
                                "tool": "",
                                "summary": text[:300],
                                "files": [],
                                "result": "",
                                "is_error": False,
                                "uuid": obj.get("uuid", ""),
                            })

    if not session_id:
        session_id = path.stem
    return {
        "file": str(path),
        "file_session": path.stem,
        "session_id": session_id,
        "prompt_id": prompt_id,
        "first_user_text": first_user_text,
        # 完整的题面，核验要拿它和题块比对（规则 G4）
        "prompt": prompt_text,
        "human_turns": human_turns,
        "model": model,
        "harness_version": harness_version,
        "cwd": cwd,
        "counts": counts,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "stop_reason": stop_reason,
        "last_assistant_text": last_assistant_text[:2000],
        "steps": steps,
    }


def write_index(summary: dict, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
