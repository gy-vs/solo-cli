"""容器执行：docker run -i … print < prompt，逐行采集 stream-json，结束后三层判定。"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from datetime import datetime, timezone

from app import config
from app.db import session
from app.events import bus
from app.models import (
    CONTINUABLE, FAILED, FINISHED, INTERRUPTED, QUEUED, RUN_END_STATUSES, RUNNING, STAGE_IDLE, TIMEOUT,
    RunEvent, Task, utc_now,
)
from app.services import dockerx, prompt_bank, settings_store, trace

log = logging.getLogger("runner")

# 人工停止标记：runner 结束时据此把状态定为 INTERRUPTED 而不是 FAILED
_manual_stop: set[int] = set()

# 纯心跳类事件：一次运行能刷出几万条「思考 token +1」，落库和推流都毫无意义，
# 只在内存里累计总量，按秒节流推一条进度。
NOISY_SUBTYPES = frozenset({"thinking_tokens"})
THINKING_PUSH_INTERVAL_S = 2.0
# 单题落库上限。防的是以后出现别的高频事件把库和浏览器一起拖死；
# 超过之后只留生命周期、结束事件与 stderr。
MAX_EVENTS_PER_TASK = 8000

# 单行上限与读取块大小。tool_result 会把整份文件连同 structuredPatch 塞进一行，
# 几百 KB 很常见，所以留足余量；真超过就截断，不能让缓冲无上限地涨。
MAX_LINE_BYTES = 8 * 1024 * 1024
READ_CHUNK_BYTES = 65536


async def _iter_lines(stream: asyncio.StreamReader):
    """按块读、自己切行，第二个返回值表示这行是否因超长被截断。

    不能用 StreamReader.readline：它的上限是 create_subprocess_exec 的 limit（默认
    64KiB），单行超过就抛 ValueError 把读取协程打死。协程一死管道没人排空，容器写
    stdout 被背压堵住，题就卡在原地不动，一直挂到超时。
    """
    buf = bytearray()
    dropping = False  # 当前行已超限，余下的字节丢到换行为止
    while True:
        chunk = await stream.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        buf += chunk
        while (nl := buf.find(b"\n")) >= 0:
            line = bytes(buf[:nl])
            del buf[:nl + 1]
            if dropping:
                dropping = False
                continue
            if len(line) > MAX_LINE_BYTES:
                yield line[:MAX_LINE_BYTES], True
            else:
                yield line, False
        if dropping:
            buf.clear()
        elif len(buf) > MAX_LINE_BYTES:
            # 还没见到换行就已经超限，先把读到的交出去，剩下的丢到行尾
            yield bytes(buf[:MAX_LINE_BYTES]), True
            buf.clear()
            dropping = True
    if buf and not dropping:
        yield bytes(buf), False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summarize_event(obj: dict) -> str:
    typ = obj.get("type", "")
    if typ == "system":
        sub = obj.get("subtype", "")
        if sub == "init":
            return f"会话初始化 · model={obj.get('model', '')} · cwd={obj.get('cwd', '')}"
        if sub == "api_retry":
            return (f"API 重试 {obj.get('attempt')}/{obj.get('max_retries')} · HTTP {obj.get('error_status')} "
                    f"{obj.get('error', '')}")
        return f"system/{sub} " + json.dumps({k: v for k, v in obj.items() if k not in ('type', 'subtype', 'uuid', 'session_id')}, ensure_ascii=False)[:200]
    if typ == "assistant":
        parts = []
        for b in (obj.get("message") or {}).get("content", []) or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                inp = b.get("input") or {}
                target = inp.get("file_path") or inp.get("command") or inp.get("pattern") or ""
                parts.append(f"{b.get('name')} {str(target)[:120]}".strip())
            elif b.get("type") == "text" and str(b.get("text", "")).strip():
                parts.append(str(b["text"]).strip()[:160])
        return " | ".join(parts) or "assistant"
    if typ == "user":
        for b in (obj.get("message") or {}).get("content", []) or []:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                prefix = "工具报错: " if b.get("is_error") else "工具结果: "
                return prefix + trace._text_of(b.get("content"), 160)
        return "user"
    if typ == "result":
        return (f"结束 · {obj.get('subtype')} · turns={obj.get('num_turns')} · "
                f"{round((obj.get('duration_ms') or 0) / 1000)}s · cost=${obj.get('total_cost_usd', 0):.3f}")
    return typ or "event"


def _record_event(task_id: int, seq: int, kind: str, summary: str, payload: dict, round_no: int = 1) -> None:
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) > 20000:
        payload = {"truncated": True, "type": payload.get("type"), "preview": raw[:20000]}
    with session() as db:
        db.add(RunEvent(task_id=task_id, seq=seq, round_no=round_no, kind=kind, summary=summary[:2000],
                        payload_json=json.dumps(payload, ensure_ascii=False)))
    bus.publish(f"run:{task_id}", {"type": "event", "seq": seq, "round_no": round_no, "kind": kind,
                                   "summary": summary[:2000], "ts": _now_iso(), "payload": payload})


def _max_seq(task_id: int) -> int:
    """续跑的事件要接在已有时间线后面，不能从 1 重新开始撞上上一轮的 seq。"""
    from sqlalchemy import func, select

    with session() as db:
        return int(db.execute(select(func.max(RunEvent.seq)).where(RunEvent.task_id == task_id)).scalar() or 0)


async def build_continue_prompt(task: Task, paths: config.TaskPaths) -> str:
    """组装续跑指令。

    镜像不支持 --resume，所以每一轮都是全新会话，模型看不到上一轮的对话。但
    workspace 是挂载的宿主目录，上一轮改的代码都还在，所以把「原始需求 + 上一轮
    留下的改动 + 这一轮要做什么」讲清楚，模型就能接着做而不是从头重来。
    """
    ws = paths.workspace
    diff_stat = ""
    changed: list[str] = []
    if (ws / ".git").exists():
        ds = await dockerx.run(["git", "-C", str(ws), "diff", "--stat"], timeout=60)
        diff_stat = ds.out.strip()
        st = await dockerx.run(["git", "-C", str(ws), "status", "--porcelain", "--untracked-files=all"], timeout=60)
        changed = [line.strip() for line in st.out.splitlines() if line.strip()][:50]

    # 这些列可能是 ALTER TABLE 补出来的 NULL，取值一律兜一层
    why = (task.error or "").strip() or (task.verdict.get("protocol") or {}).get("subtype") or task.status
    progress = diff_stat or "（git diff 为空）"
    if changed:
        progress += "\n未提交/未跟踪的文件：\n" + "\n".join(changed)

    return (
        f"【续跑说明】这是同一道题的第 {paths.round_no} 轮。上一轮没有正常跑完，"
        f"原因：{str(why)[:300]}。\n"
        f"你是一个全新的会话，读不到上一轮的对话记录，但上一轮对 {config.CONTAINER_WORKSPACE} "
        f"的代码改动都还在。请先用 git status、git diff 等工具确认当前进度，"
        f"在已有改动的基础上继续，不要从头重做、也不要把已完成的部分推翻重写。\n\n"
        f"【本题原始需求】\n{task.user_prompt or ''}\n\n"
        f"【上一轮已经留下的改动】\n{progress}\n\n"
        f"【本轮要求】\n{(task.continue_prompt or '').strip() or '继续完成上面的原始需求。'}\n"
    )


def _publish_task(task_id: int) -> None:
    bus.publish("tasks", {"type": "task", "id": task_id})


def _set(task_id: int, **fields) -> Task | None:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return None
        for k, v in fields.items():
            setattr(t, k, v)
        db.flush()
        return t


async def run_task(task_id: int) -> None:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        task_no, round_no = t.task_no, max(1, t.round_no or 1)
        paths = config.TaskPaths(task_no, round_no)
        prompt = t.user_prompt if round_no <= 1 else await build_continue_prompt(t, paths)
    image = settings_store.get("cc.image")
    api_key = settings_store.get("cc.api_key")
    timeout_s = max(60, settings_store.get_int("run.timeout_minutes", 120) * 60)

    paths.traces.mkdir(parents=True, exist_ok=True)
    _set(task_id, status=RUNNING, started_at=utc_now(), container_exists=True, image_tag=image,
         container_name=paths.container_name, error="", exit_code=None, result_json="{}")
    _publish_task(task_id)

    cmd = [
        "docker", "run", "-i",
        "--name", paths.container_name,
        "--label", f"{config.CONTAINER_LABEL}={task_no}",
        "-e", f"apikey={api_key}",
        "-v", f"{paths.workspace_host}:{config.CONTAINER_WORKSPACE}",
        "-v", f"{paths.traces_host}:{config.CONTAINER_PROJECTS}",
        "--memory", settings_store.get("cc.memory") or "4g",
        "--cpus", settings_store.get("cc.cpus") or "2",
        image, "print",
    ]
    # 续跑的事件接在上一轮后面，界面上就是一条连续的时间线
    seq = _max_seq(task_id) if round_no > 1 else 0
    seq += 1
    label = f"启动容器 {paths.container_name} · {image}"
    if round_no > 1:
        label = f"第 {round_no} 轮续跑 · " + label
    _record_event(task_id, seq, "lifecycle", label,
                  {"type": "lifecycle", "image": image, "container": paths.container_name,
                   "round_no": round_no, "prompt_preview": prompt[:2000]}, round_no)

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdin and proc.stdout and proc.stderr
    try:
        proc.stdin.write(prompt.encode("utf-8"))
        await proc.stdin.drain()
        proc.stdin.close()
    except (BrokenPipeError, ConnectionResetError) as exc:
        log.warning("stdin 写入失败: %s", exc)

    result_event: dict = {}
    stderr_tail: list[str] = []
    thinking_tokens = 0
    dropped = 0
    last_push = 0.0

    async def pump_stdout() -> None:
        nonlocal seq, result_event, thinking_tokens, dropped, last_push
        async for line, truncated in _iter_lines(proc.stdout):
            text = line.decode("utf-8", "replace").strip()
            if not text:
                continue
            if truncated:
                seq += 1
                _record_event(task_id, seq, "stdout", f"单行输出超过 {MAX_LINE_BYTES >> 20} MB，已截断",
                              {"type": "stdout", "truncated": True, "text": text[:2000]}, round_no)
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                seq += 1
                _record_event(task_id, seq, "stdout", text[:500], {"type": "stdout", "text": text[:2000]}, round_no)
                continue
            kind = str(obj.get("type", "event"))
            if kind == "system" and obj.get("subtype") in NOISY_SUBTYPES:
                thinking_tokens = max(thinking_tokens, int(obj.get("estimated_tokens") or 0))
                now = time.monotonic()
                if now - last_push >= THINKING_PUSH_INTERVAL_S:
                    last_push = now
                    # 只推流不落库，前端当成一行状态显示，不进事件列表
                    bus.publish(f"run:{task_id}", {"type": "thinking", "tokens": thinking_tokens})
                continue
            if seq >= MAX_EVENTS_PER_TASK and kind not in ("result", "lifecycle", "stderr"):
                dropped += 1
                continue
            seq += 1
            _record_event(task_id, seq, kind, _summarize_event(obj), obj, round_no)
            if kind == "result":
                result_event = obj

    async def read_stdout() -> None:
        """解析出错也要把管道读到底，否则容器写 stdout 会被背压堵死。"""
        nonlocal seq
        try:
            await pump_stdout()
        except Exception as exc:  # noqa: BLE001
            log.exception("题 %s 解析 stdout 中断，转为只排空管道", task_id)
            seq += 1
            _record_event(task_id, seq, "stderr", f"stdout 解析中断，后续过程以轨迹 jsonl 为准：{exc}",
                          {"type": "stderr", "text": repr(exc)[:2000]}, round_no)
            try:
                while await proc.stdout.read(READ_CHUNK_BYTES):
                    pass
            except Exception:  # noqa: BLE001
                log.exception("题 %s 排空 stdout 失败", task_id)

    async def read_stderr() -> None:
        nonlocal seq
        async for line, _ in _iter_lines(proc.stderr):
            text = line.decode("utf-8", "replace").rstrip()
            if text:
                stderr_tail.append(text)
                del stderr_tail[:-50]
                seq += 1
                _record_event(task_id, seq, "stderr", text[:500], {"type": "stderr", "text": text[:2000]}, round_no)

    readers = asyncio.gather(read_stdout(), read_stderr(), return_exceptions=True)
    timed_out = False
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        timed_out = True
        seq += 1
        _record_event(task_id, seq, "lifecycle", f"超过 {timeout_s // 60} 分钟，停止容器",
                      {"type": "lifecycle", "timeout": True}, round_no)
        await dockerx.stop_container(paths.container_name, grace=30)
        try:
            await asyncio.wait_for(proc.wait(), timeout=60)
        except asyncio.TimeoutError:
            proc.kill()
    try:
        results = await asyncio.wait_for(readers, timeout=30)
    except asyncio.TimeoutError:
        results = []
    for r in results:
        if isinstance(r, BaseException):
            log.error("题 %s 输出读取协程异常: %r", task_id, r)

    exit_code = proc.returncode if proc.returncode is not None else await dockerx.container_exit_code(paths.container_name)
    manual = task_id in _manual_stop
    _manual_stop.discard(task_id)
    seq += 1
    _record_event(task_id, seq, "lifecycle", f"容器退出 · exit={exit_code}",
                  {"type": "lifecycle", "exit_code": exit_code, "stderr_tail": stderr_tail[-10:]}, round_no)

    await finalize(task_id, exit_code=exit_code, result_event=result_event,
                   timed_out=timed_out, manual_stop=manual, stderr_tail=stderr_tail,
                   thinking_tokens=thinking_tokens, dropped_events=dropped)


def decide_status(*, timed_out: bool, manual_stop: bool, result_event: dict,
                  exit_code: int | None, has_trace: bool) -> tuple[str, bool]:
    """结束状态判定。第二个返回值表示这是不是「重启后接管」的收尾。

    正常路径靠 stdout 上的 result 事件定性。但后端重启后接管的容器读不到 stdout，
    result 永远是空的；这时退出码 0 且本轮写出了轨迹就按正常结束算，
    否则一小时跑完的题会被判成失败。
    """
    adopted_ok = not result_event and exit_code == 0 and has_trace
    if timed_out:
        return TIMEOUT, False
    if manual_stop:
        return INTERRUPTED, False
    subtype = result_event.get("subtype", "")
    if result_event and subtype == "success" and not result_event.get("is_error") and exit_code in (0, None):
        return FINISHED, False
    if adopted_ok:
        return FINISHED, True
    if not result_event and (exit_code in (137, 143) or exit_code is None):
        return INTERRUPTED, False
    return FAILED, False


async def finalize(task_id: int, *, exit_code: int | None, result_event: dict,
                   timed_out: bool = False, manual_stop: bool = False,
                   stderr_tail: list[str] | None = None,
                   thinking_tokens: int = 0, dropped_events: int = 0) -> None:
    """三层判定 + 轨迹解析 + 导出 + 回填。可被「接管残留容器」复用。"""
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        task_no, since = t.task_no, t.started_at
        round_no = max(1, t.round_no or 1)
    paths = config.TaskPaths(task_no, round_no)
    ws = paths.workspace

    # ---- 产物层：轨迹 ----
    # 只认本轮写过的 jsonl：轨迹目录按题号复用，重跑时旧文件还在里面
    trace_file = trace.find_trace_file(paths.traces, since)
    summary = trace.parse_trace(trace_file) if trace_file else {}
    trace_count = trace.count_traces(paths.traces, since)
    export_path = ""
    if trace_file:
        paths.export.mkdir(parents=True, exist_ok=True)
        target = paths.export / trace_file.name
        shutil.copy2(trace_file, target)
        export_path = str(target)
        trace.write_index(summary, paths.analysis / "trace_index.json")

    # ---- 产物层：git ----
    diff_stat = ""
    changed_files = 0
    if (ws / ".git").exists():
        st = await dockerx.run(["git", "-C", str(ws), "status", "--porcelain", "--untracked-files=all"], timeout=60)
        changed_files = len([l for l in st.out.splitlines() if l.strip()])
        ds = await dockerx.run(["git", "-C", str(ws), "diff", "--stat"], timeout=60)
        diff_stat = (ds.out.strip() + (f"\n未跟踪/改动文件合计 {changed_files}" if changed_files else "")).strip()

    # ---- 状态判定 ----
    status, adopted_ok = decide_status(timed_out=timed_out, manual_stop=manual_stop,
                                       result_event=result_event, exit_code=exit_code,
                                       has_trace=trace_file is not None)

    notes = []
    if not trace_file:
        stale = trace.count_traces(paths.traces)
        notes.append("本轮没有产出轨迹 jsonl" + (f"（目录里有 {stale} 份更早的，未采用）" if stale else ""))
    if trace_count > 1:
        notes.append(f"轨迹目录有 {trace_count} 份 jsonl，已取最大的一份；上传前需人工确认（规则 T4）")
    if trace_file and changed_files == 0 and not diff_stat:
        notes.append("工作目录无任何改动，疑似未产出")
    rs = result_event.get("session_id", "")
    if rs and summary.get("session_id") and rs != summary.get("session_id"):
        notes.append(f"result.session_id({rs[:8]}) 与轨迹 sessionId({summary.get('session_id', '')[:8]}) 不一致")
    if dropped_events:
        notes.append(f"事件超过 {MAX_EVENTS_PER_TASK} 条，丢弃了 {dropped_events} 条中间事件；完整过程以轨迹 jsonl 为准")
    if adopted_ok:
        notes.append("后端重启后接管的容器，没有 result 事件；状态按退出码 0 与本轮轨迹判定，轮次与用量为空")
    if stderr_tail:
        notes.append("stderr: " + " / ".join(stderr_tail[-3:])[:300])
    if round_no > 1:
        notes.append(f"这是第 {round_no} 轮续跑，每轮一份独立轨迹（各轮目录 {config.TRACES_DIR}/{task_no}[-rN]）；"
                     f"上传只能交一份，需人工确认用哪一轮")

    verdict = {
        "process": {"exit_code": exit_code, "timed_out": timed_out, "manual_stop": manual_stop},
        "protocol": {"subtype": result_event.get("subtype", ""), "is_error": bool(result_event.get("is_error")),
                     "num_turns": result_event.get("num_turns"),
                     "duration_ms": result_event.get("duration_ms"), "cost_usd": result_event.get("total_cost_usd"),
                     "usage": result_event.get("usage"), "thinking_tokens": thinking_tokens or None},
        "artifact": {"trace_found": bool(trace_file), "trace_count": trace_count,
                     "tool_calls": (summary.get("counts") or {}).get("tool_calls"),
                     "tool_errors": (summary.get("counts") or {}).get("tool_errors"),
                     "changed_files": changed_files},
        "notes": notes,
        "status": status,
    }

    session_id = (summary.get("file_session") or summary.get("session_id") or rs or "")
    turn_id = summary.get("prompt_id", "")
    light = {k: v for k, v in summary.items() if k != "steps"}
    light["steps_count"] = len(summary.get("steps") or [])

    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        t.status = status
        t.finished_at = utc_now()
        t.exit_code = exit_code
        t.result = result_event
        t.verdict = verdict
        t.trace_summary = light
        t.trace_file = export_path
        t.git_diff_stat = diff_stat[:8000]
        if session_id:
            t.session_id = session_id
        if turn_id:
            t.turn_id = turn_id
        if not result_event and stderr_tail:
            t.error = "\n".join(stderr_tail[-5:])[:2000]
        # 每轮留一条痕：哪一轮、什么指令、跑出什么结果、轨迹在哪
        history = [r for r in t.rounds if r.get("round_no") != round_no]
        history.append({
            "round_no": round_no,
            "status": status,
            "exit_code": exit_code,
            "container": paths.container_name,
            "trace_file": export_path,
            "session_id": session_id,
            "changed_files": changed_files,
            "prompt": (t.user_prompt if round_no <= 1 else t.continue_prompt)[:2000],
            "finished_at": utc_now().isoformat(),
        })
        t.rounds = sorted(history, key=lambda r: r.get("round_no") or 0)
        t.continue_prompt = ""
        db.flush()
        should_backfill = bool(session_id and turn_id)
        snapshot = t

    if should_backfill:
        try:
            res = prompt_bank.backfill(snapshot)
            log.info("回填 %s: %s", task_no, res)
        except Exception as exc:  # noqa: BLE001
            log.exception("回填失败")
            _set(task_id, error=f"回填 prompt.md 失败: {exc}")
    _publish_task(task_id)
    bus.publish(f"run:{task_id}", {"type": "finished", "status": status})

    # 结束后不再等人点：销毁容器、五维分析、质检由流水线接手（各步可在设置里关）
    from app.services import pipeline

    if status in RUN_END_STATUSES:
        pipeline.spawn(task_id)


async def stop_task(task_id: int) -> dict:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None or t.status != RUNNING:
            return {"ok": False, "message": "任务不在运行中"}
        name = t.container_name
    _manual_stop.add(task_id)
    r = await dockerx.stop_container(name, grace=30)
    return {"ok": r.ok, "message": r.err.strip() or "已发送停止"}


async def queue_continue(task_id: int, prompt: str) -> dict:
    """把一道跑完或跑挂的题排进下一轮续跑。

    首轮 504、报错、超时之后，workspace 里往往已经有一半改动，整题重跑等于白扔。
    这里只递增轮次并记下这轮要做什么，出队仍然走调度器，照样受并发额度和
    「一个项目同时只跑一道」的约束。
    """
    prompt = (prompt or "").strip()
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "message": "任务不存在"}
        if t.status not in CONTINUABLE:
            return {"ok": False, "message": f"当前状态 {t.status} 不能续跑，只有跑完或中断的题可以"}
        task_no = t.task_no
        nxt = max(1, t.round_no or 1) + 1

    paths = config.TaskPaths(task_no, nxt)
    if not paths.workspace.is_dir():
        return {"ok": False, "message": f"工作目录不存在：{paths.workspace}"}
    state = await dockerx.container_state(paths.container_name)
    if state:
        return {"ok": False, "message": f"容器 {paths.container_name} 已存在（{state}），需先销毁再续跑"}
    # 镜像要求挂进去的轨迹目录必须是空的，非空会在 entrypoint 直接拒绝启动
    if paths.traces.exists() and any(paths.traces.iterdir()):
        return {"ok": False, "message": f"第 {nxt} 轮的轨迹目录非空：{paths.traces}，请先归档"}

    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "message": "任务不存在"}
        t.round_no = nxt
        t.continue_prompt = prompt
        t.status = QUEUED
        t.container_name = paths.container_name
        t.container_exists = False
        t.error = ""
        t.exit_code = None
        t.auto_stage = STAGE_IDLE
        t.auto_error = ""
        t.finished_at = None
    _publish_task(task_id)
    return {"ok": True, "round_no": nxt, "container": paths.container_name,
            "message": f"已排入第 {nxt} 轮续跑，等调度器出队"}
