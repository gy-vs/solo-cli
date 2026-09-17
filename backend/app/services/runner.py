"""单侧容器执行：docker run -i … print < prompt，逐行采集 stream-json，结束后三层判定。

一道题会有两个这样的运行（A 与 B），各自一个容器、一份工作区、一份轨迹。本模块
只关心「一次跑」，不知道自己是对照组还是实验组，也不负责题目级状态——两侧谁先结束
是随机的，让先结束的那一侧去改题级状态会互相覆盖，那件事统一由 watchdog 做。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import time
from datetime import datetime, timezone

from app import config
from app.db import session
from app.events import bus
from app.models import (
    RUN_END_STATUSES, RUN_FAILED, RUN_FINISHED, RUN_INTERRUPTED, RUN_RUNNING, RUN_TIMEOUT,
    RunEvent, Task, TaskRun, utc_now,
)
from app.services import dockerx, settings_store, trace, watchdog

log = logging.getLogger("runner")

# 人工停止标记（按 run.id）：runner 结束时据此把状态定为 INTERRUPTED 而不是 FAILED，
# 也让 watchdog 知道这不是异常，不要自动重跑
_manual_stop: set[int] = set()

# 纯心跳类事件：一次运行能刷出几万条「思考 token +1」，落库和推流都毫无意义，
# 只在内存里累计总量，按秒节流推一条进度。
NOISY_SUBTYPES = frozenset({"thinking_tokens"})
THINKING_PUSH_INTERVAL_S = 2.0
# 单侧落库上限。防的是以后出现别的高频事件把库和浏览器一起拖死；
# 超过之后只留生命周期、结束事件与 stderr。
MAX_EVENTS_PER_RUN = 8000

# 单行上限与读取块大小。tool_result 会把整份文件连同 structuredPatch 塞进一行，
# 几百 KB 很常见，所以留足余量；真超过就截断，不能让缓冲无上限地涨。
MAX_LINE_BYTES = 8 * 1024 * 1024
READ_CHUNK_BYTES = 65536

# 网关故障的状态码。这类失败与模型能力无关，按平台规则不能作为 GSB 的判断依据，
# 只能重跑，所以要能从噪声里准确认出来。
_GATEWAY_CODES = re.compile(r"(?:http|status|code|statuscode)\D{0,10}\b(429|5\d\d)\b", re.I)


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


def gateway_errors(retry_events: list[dict], stderr_tail: list[str]) -> list[str]:
    """从重试事件与 stderr 里挑出网关状态码，按出现顺序去重。

    stderr 只认紧跟在 http/status/code 后面的数字。日志里「wrote 5040 bytes」这种
    裸数字不少，不加限定会把它当成 504，白白触发一次重跑。
    """
    codes: list[str] = []
    for e in retry_events:
        code = str(e.get("error_status") or "").strip()
        if code and code not in codes:
            codes.append(code)
    for line in stderr_tail:
        for m in _GATEWAY_CODES.finditer(line or ""):
            if m.group(1) not in codes:
                codes.append(m.group(1))
    return codes


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


def _record_event(task_id: int, side: str, seq: int, kind: str, summary: str, payload: dict) -> None:
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) > 20000:
        payload = {"truncated": True, "type": payload.get("type"), "preview": raw[:20000]}
    with session() as db:
        db.add(RunEvent(task_id=task_id, seq=seq, side=side, kind=kind, summary=summary[:2000],
                        payload_json=json.dumps(payload, ensure_ascii=False)))
    bus.publish(f"run:{task_id}", {"type": "event", "seq": seq, "side": side, "kind": kind,
                                   "summary": summary[:2000], "ts": _now_iso(), "payload": payload})


def _publish_task(task_id: int) -> None:
    bus.publish("tasks", {"type": "task", "id": task_id})


def _set_run(run_id: int, **fields) -> None:
    with session() as db:
        r = db.get(TaskRun, run_id)
        if r is None:
            return
        for k, v in fields.items():
            setattr(r, k, v)


async def run_side(run_id: int) -> None:
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return
        task = db.get(Task, run.task_id)
        if task is None:
            return
        task_id, side, task_no = task.id, run.side, task.task_no
        prompt = task.user_prompt or ""
    paths = config.TaskPaths(task_no, side)
    image = settings_store.get("cc.image")
    api_key = settings_store.get("cc.api_key")
    timeout_s = max(60, settings_store.get_int("run.timeout_minutes", 120) * 60)

    paths.traces.mkdir(parents=True, exist_ok=True)
    _set_run(run_id, status=RUN_RUNNING, started_at=utc_now(), container_exists=True,
             image_tag=image, container_name=paths.container_name, error="",
             exit_code=None, result_json="{}", finished_at=None)
    _publish_task(task_id)

    cmd = [
        "docker", "run", "-i",
        "--name", paths.container_name,
        "--label", f"{config.CONTAINER_LABEL}={task_no}",
        "--label", f"{config.CONTAINER_LABEL}.side={side}",
        "-e", f"apikey={api_key}",
        "-v", f"{paths.workspace_host}:{config.CONTAINER_WORKSPACE}",
        "-v", f"{paths.traces_host}:{config.CONTAINER_PROJECTS}",
        "--memory", settings_store.get("cc.memory") or "4g",
        "--cpus", settings_store.get("cc.cpus") or "2",
        image, "print",
    ]
    # 每一侧的事件从 1 开始独立编号，重跑前 watchdog 会清掉这一侧的旧事件，
    # 界面上 A、B 两栏各是一条干净的时间线
    seq = 1
    with session() as db:
        attempt = (db.get(TaskRun, run_id).attempt if db.get(TaskRun, run_id) else 1)
    label = f"启动容器 {paths.container_name} · {image}"
    if attempt > 1:
        label = f"第 {attempt} 次尝试 · " + label
    _record_event(task_id, side, seq, "lifecycle", label,
                  {"type": "lifecycle", "image": image, "container": paths.container_name,
                   "side": side, "attempt": attempt, "prompt_preview": prompt[:2000]})

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
    retry_events: list[dict] = []
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
                _record_event(task_id, side, seq, "stdout", f"单行输出超过 {MAX_LINE_BYTES >> 20} MB，已截断",
                              {"type": "stdout", "truncated": True, "text": text[:2000]})
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                seq += 1
                _record_event(task_id, side, seq, "stdout", text[:500], {"type": "stdout", "text": text[:2000]})
                continue
            kind = str(obj.get("type", "event"))
            if kind == "system" and obj.get("subtype") in NOISY_SUBTYPES:
                thinking_tokens = max(thinking_tokens, int(obj.get("estimated_tokens") or 0))
                now = time.monotonic()
                if now - last_push >= THINKING_PUSH_INTERVAL_S:
                    last_push = now
                    # 只推流不落库，前端当成一行状态显示，不进事件列表
                    bus.publish(f"run:{task_id}", {"type": "thinking", "side": side,
                                                   "tokens": thinking_tokens})
                continue
            if kind == "system" and obj.get("subtype") == "api_retry":
                retry_events.append(obj)
            if seq >= MAX_EVENTS_PER_RUN and kind not in ("result", "lifecycle", "stderr"):
                dropped += 1
                continue
            seq += 1
            _record_event(task_id, side, seq, kind, _summarize_event(obj), obj)
            if kind == "result":
                result_event = obj

    async def read_stdout() -> None:
        """解析出错也要把管道读到底，否则容器写 stdout 会被背压堵死。"""
        nonlocal seq
        try:
            await pump_stdout()
        except Exception as exc:  # noqa: BLE001
            log.exception("run %s 解析 stdout 中断，转为只排空管道", run_id)
            seq += 1
            _record_event(task_id, side, seq, "stderr", f"stdout 解析中断，后续过程以轨迹 jsonl 为准：{exc}",
                          {"type": "stderr", "text": repr(exc)[:2000]})
            try:
                while await proc.stdout.read(READ_CHUNK_BYTES):
                    pass
            except Exception:  # noqa: BLE001
                log.exception("run %s 排空 stdout 失败", run_id)

    async def read_stderr() -> None:
        nonlocal seq
        async for line, _ in _iter_lines(proc.stderr):
            text = line.decode("utf-8", "replace").rstrip()
            if text:
                stderr_tail.append(text)
                del stderr_tail[:-50]
                seq += 1
                _record_event(task_id, side, seq, "stderr", text[:500], {"type": "stderr", "text": text[:2000]})

    readers = asyncio.gather(read_stdout(), read_stderr(), return_exceptions=True)
    timed_out = False
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        timed_out = True
        seq += 1
        _record_event(task_id, side, seq, "lifecycle", f"超过 {timeout_s // 60} 分钟，停止容器",
                      {"type": "lifecycle", "timeout": True})
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
            log.error("run %s 输出读取协程异常: %r", run_id, r)

    exit_code = proc.returncode if proc.returncode is not None else await dockerx.container_exit_code(paths.container_name)
    manual = run_id in _manual_stop
    _manual_stop.discard(run_id)
    seq += 1
    _record_event(task_id, side, seq, "lifecycle", f"容器退出 · exit={exit_code}",
                  {"type": "lifecycle", "exit_code": exit_code, "stderr_tail": stderr_tail[-10:]})

    await finalize(run_id, exit_code=exit_code, result_event=result_event,
                   timed_out=timed_out, manual_stop=manual, stderr_tail=stderr_tail,
                   retry_events=retry_events, thinking_tokens=thinking_tokens,
                   dropped_events=dropped)


def decide_status(*, timed_out: bool, manual_stop: bool, result_event: dict,
                  exit_code: int | None, has_trace: bool) -> tuple[str, bool]:
    """结束状态判定。第二个返回值表示这是不是「重启后接管」的收尾。

    正常路径靠 stdout 上的 result 事件定性。但后端重启后接管的容器读不到 stdout，
    result 永远是空的；这时退出码 0 且这一侧写出了轨迹就按正常结束算，
    否则一小时跑完的题会被判成失败。
    """
    adopted_ok = not result_event and exit_code == 0 and has_trace
    if timed_out:
        return RUN_TIMEOUT, False
    if manual_stop:
        return RUN_INTERRUPTED, False
    subtype = result_event.get("subtype", "")
    if result_event and subtype == "success" and not result_event.get("is_error") and exit_code in (0, None):
        return RUN_FINISHED, False
    if adopted_ok:
        return RUN_FINISHED, True
    if not result_event and (exit_code in (137, 143) or exit_code is None):
        return RUN_INTERRUPTED, False
    return RUN_FAILED, False


async def finalize(run_id: int, *, exit_code: int | None, result_event: dict,
                   timed_out: bool = False, manual_stop: bool = False,
                   stderr_tail: list[str] | None = None,
                   retry_events: list[dict] | None = None,
                   thinking_tokens: int = 0, dropped_events: int = 0) -> None:
    """三层判定 + 轨迹解析 + 导出，结果全部落在这一侧的 TaskRun 上。

    可被「接管残留容器」和 watchdog 复用。题目级状态与后续动作（推送产物、开分析、
    重跑）一概不在这里决定，只在最后叫一声 watchdog 让它自己判断。
    """
    stderr_tail = stderr_tail or []
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return
        task = db.get(Task, run.task_id)
        if task is None:
            return
        task_id, side, task_no = task.id, run.side, task.task_no
        since, attempt = run.started_at, run.attempt
    paths = config.TaskPaths(task_no, side)
    ws = paths.workspace

    # ---- 产物层：轨迹 ----
    # 只认这次跑之后写过的 jsonl：轨迹目录按侧复用，重跑时旧文件还在里面
    trace_file = trace.find_trace_file(paths.traces, since)
    summary = trace.parse_trace(trace_file) if trace_file else {}
    trace_count = trace.count_traces(paths.traces, since)
    export_path = ""
    if trace_file:
        paths.export.mkdir(parents=True, exist_ok=True)
        target = paths.export / trace_file.name
        shutil.copy2(trace_file, target)
        export_path = str(target)
        paths.analysis.mkdir(parents=True, exist_ok=True)
        trace.write_index(summary, paths.trace_index)

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
    gw = gateway_errors(retry_events or [], stderr_tail)

    notes = []
    if not trace_file:
        stale = trace.count_traces(paths.traces)
        notes.append("这次跑没有产出轨迹 jsonl" + (f"（目录里有 {stale} 份更早的，未采用）" if stale else ""))
    if trace_count > 1:
        notes.append(f"轨迹目录有 {trace_count} 份 jsonl，已取最大的一份；上传前需人工确认（规则 T4）")
    if trace_file and changed_files == 0 and not diff_stat:
        notes.append("工作目录无任何改动，疑似未产出")
    rs = result_event.get("session_id", "")
    if rs and summary.get("session_id") and rs != summary.get("session_id"):
        notes.append(f"result.session_id({rs[:8]}) 与轨迹 sessionId({summary.get('session_id', '')[:8]}) 不一致")
    if dropped_events:
        notes.append(f"事件超过 {MAX_EVENTS_PER_RUN} 条，丢弃了 {dropped_events} 条中间事件；完整过程以轨迹 jsonl 为准")
    if adopted_ok:
        notes.append("后端重启后接管的容器，没有 result 事件；状态按退出码 0 与这一侧的轨迹判定，轮次与用量为空")
    if gw:
        notes.append(f"出现网关报错 {'、'.join(gw)}，按平台规则不作为 GSB 判断依据")
    if attempt > 1:
        notes.append(f"这是第 {attempt} 次尝试，之前的异常已重跑")
    if stderr_tail:
        notes.append("stderr: " + " / ".join(stderr_tail[-3:])[:300])

    verdict = {
        "process": {"exit_code": exit_code, "timed_out": timed_out, "manual_stop": manual_stop,
                    "gateway_errors": gw, "attempt": attempt},
        "protocol": {"subtype": result_event.get("subtype", ""), "is_error": bool(result_event.get("is_error")),
                     "num_turns": result_event.get("num_turns"),
                     "duration_ms": result_event.get("duration_ms"), "cost_usd": result_event.get("total_cost_usd"),
                     "usage": result_event.get("usage"), "thinking_tokens": thinking_tokens or None},
        "artifact": {"trace_found": bool(trace_file), "trace_count": trace_count,
                     "tool_calls": (summary.get("counts") or {}).get("tool_calls"),
                     "tool_errors": (summary.get("counts") or {}).get("tool_errors"),
                     "human_turns": summary.get("human_turns"),
                     "changed_files": changed_files},
        "notes": notes,
        "status": status,
    }

    session_id = (summary.get("file_session") or summary.get("session_id") or rs or "")
    turn_id = summary.get("prompt_id", "")
    light = {k: v for k, v in summary.items() if k != "steps"}
    light["steps_count"] = len(summary.get("steps") or [])

    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return
        run.status = status
        run.finished_at = utc_now()
        run.container_exists = True
        run.exit_code = exit_code
        run.result = result_event
        run.verdict = verdict
        run.trace_summary = light
        run.trace_file = export_path
        run.git_diff_stat = diff_stat[:8000]
        if session_id:
            run.session_id = session_id
        if turn_id:
            run.turn_id = turn_id
        if not result_event and stderr_tail:
            run.error = "\n".join(stderr_tail[-5:])[:2000]
        elif gw:
            run.error = f"网关报错 {'、'.join(gw)}"

    _publish_task(task_id)
    bus.publish(f"run:{task_id}", {"type": "finished", "side": side, "status": status})

    # 两侧都结束才有下一步。谁结束得晚由 watchdog 自己看，这里只负责叫它别等下一个周期
    if status in RUN_END_STATUSES:
        watchdog.wake()


async def stop_run(run_id: int) -> dict:
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None or run.status != RUN_RUNNING:
            return {"ok": False, "message": "这一侧不在运行中"}
        name = run.container_name
    _manual_stop.add(run_id)
    r = await dockerx.stop_container(name, grace=30)
    return {"ok": r.ok, "message": r.err.strip() or "已发送停止"}
