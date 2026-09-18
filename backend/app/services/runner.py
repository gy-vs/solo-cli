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
from pathlib import Path

from app import config
from app.db import session
from app.events import bus
from app.models import (
    RUN_END_STATUSES, RUN_FAILED, RUN_FINISHED, RUN_INTERRUPTED, RUN_RUNNING, RUN_TIMEOUT,
    RunEvent, Task, TaskRun, as_utc, utc_now,
)
from app.services import dockerx, gsb_repo, settings_store, trace, watchdog

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

# 容器退出后等多久再重读工作区。macOS 的 bind mount 把容器写的文件同步过来要一点时间，
# 实测容器退出到收尾最快只隔 385 毫秒，那时读到的是一片空白。
WORKSPACE_SETTLE_SECONDS = 5

# 容器退出后，留给读取协程把剩下的输出读完的时间。
#
# 两条路径的量级差着两个数量级：run_side 读的是管道里还没取走的那点数据，几秒就到底；
# attach_run 读的是 `docker logs` 从头重放的整份历史，一万行、每行都要落一次库，
# 追平要好几分钟。以前两边都是 30 秒，到点就把协程砍掉 —— 而 result 事件恰好在日志的
# 最后一行，于是接管过的运行永远「没有 result」，轮次和用量全空，状态只能靠退出码猜。
OUTPUT_DRAIN_SECONDS = 60
LOG_REPLAY_DRAIN_SECONDS = 900

# 单行上限与读取块大小。tool_result 会把整份文件连同 structuredPatch 塞进一行，
# 几百 KB 很常见，所以留足余量；真超过就截断，不能让缓冲无上限地涨。
MAX_LINE_BYTES = 8 * 1024 * 1024
READ_CHUNK_BYTES = 65536

# 网关故障的状态码。这类失败与模型能力无关，按平台规则不能作为 GSB 的判断依据，
# 只能重跑，所以要能从噪声里准确认出来。
_GATEWAY_CODES = re.compile(r"(?:http|status|code|statuscode)\D{0,10}\b(429|5\d\d)\b", re.I)


async def iter_lines(stream: asyncio.StreamReader):
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


def retry_stats(retry_events: list[dict]) -> dict:
    """CC 自己的重试进度。

    镜像里的 Claude Code 遇到网关故障会自行重试（默认十次），每次发一条
    system/api_retry，带 attempt 与 max_retries。这两个数是 watchdog 判「还在自动
    重试」还是「重试已经用尽」的唯一依据：重试期间不该介入，硬插一脚只会把一次
    本来能自己缓过来的运行打断。
    """
    attempts = [int(e.get("attempt") or 0) for e in retry_events if e.get("attempt")]
    limits = [int(e.get("max_retries") or 0) for e in retry_events if e.get("max_retries")]
    return {"count": len(retry_events),
            "attempt": max(attempts, default=0),
            "max_retries": max(limits, default=0)}


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


def _record_event(task_id: int, side: str, seq: int, kind: str, summary: str, payload: dict,
                  *, ts: datetime | None = None, publish: bool = True) -> None:
    """落一条事件。

    ts 用来按容器日志里的真实时刻记账，重建时间线时不能用「现在」——那会让一小时前
    的对话挤成同一秒。publish 关掉则只落库不推流，重放历史时用：几千条事件推到浏览器
    除了把它卡住没有别的效果，重放完让界面重新拉一次就是了。
    """
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw) > 20000:
        payload = {"truncated": True, "type": payload.get("type"), "preview": raw[:20000]}
    with session() as db:
        row = RunEvent(task_id=task_id, seq=seq, side=side, kind=kind, summary=summary[:2000],
                       payload_json=json.dumps(payload, ensure_ascii=False))
        if ts is not None:
            row.ts = ts
        db.add(row)
    if publish:
        at = (ts or utc_now()).isoformat()
        bus.publish(f"run:{task_id}", {"type": "event", "seq": seq, "side": side, "kind": kind,
                                       "summary": summary[:2000],
                                       "ts": at, "payload": payload})
        # 列表页只显示最近几行摘要，payload 对它没用却是这条流里最大的一块（单条能到
        # 20 KB）。给它单独发一份瘦的，省的不只是流量：卡片不必再各连一条自己的流。
        bus.publish("runs", {"type": "run_event", "task_id": task_id, "seq": seq, "side": side,
                             "kind": kind, "summary": summary[:300], "ts": at})


class OutputSink:
    """stream-json 的消费端：落库、推流，同时把收尾判定要用的东西攒起来。

    两条路径喂给它的是同一种行 —— run_side 直接读容器的 stdout，attach_run 从
    `docker logs` 里读。判定必须按同一套规则来（哪些算噪声、result 取哪条、网关重试
    怎么数），所以只留一份实现；从前 attach 那条路径干脆什么都不读，于是接管过的
    运行永远没有 result 事件，只能靠退出码降级判定。
    """

    def __init__(self, task_id: int, side: str, seq: int = 0) -> None:
        self.task_id = task_id
        self.side = side
        self.seq = seq
        self.result: dict = {}
        self.retry_events: list[dict] = []
        self.stderr_tail: list[str] = []
        self.thinking_tokens = 0
        self.dropped = 0
        self._last_push = 0.0

    def record(self, kind: str, summary: str, payload: dict, *,
               ts: datetime | None = None, publish: bool = True) -> None:
        self.seq += 1
        _record_event(self.task_id, self.side, self.seq, kind, summary, payload,
                      ts=ts, publish=publish)

    def feed(self, text: str, *, truncated: bool = False,
             ts: datetime | None = None, publish: bool = True) -> None:
        """吃一行 stdout。"""
        if truncated:
            self.record("stdout", f"单行输出超过 {MAX_LINE_BYTES >> 20} MB，已截断",
                        {"type": "stdout", "truncated": True, "text": text[:2000]},
                        ts=ts, publish=publish)
            return
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            self.record("stdout", text[:500], {"type": "stdout", "text": text[:2000]},
                        ts=ts, publish=publish)
            return
        kind = str(obj.get("type", "event"))
        if kind == "system" and obj.get("subtype") in NOISY_SUBTYPES:
            self.thinking_tokens = max(self.thinking_tokens, int(obj.get("estimated_tokens") or 0))
            now = time.monotonic()
            if publish and now - self._last_push >= THINKING_PUSH_INTERVAL_S:
                self._last_push = now
                # 只推流不落库，前端当成一行状态显示，不进事件列表
                bus.publish(f"run:{self.task_id}", {"type": "thinking", "side": self.side,
                                                    "tokens": self.thinking_tokens})
            return
        if kind == "system" and obj.get("subtype") == "api_retry":
            self.retry_events.append(obj)
        if self.seq >= MAX_EVENTS_PER_RUN and kind not in ("result", "lifecycle", "stderr"):
            self.dropped += 1
            return
        self.record(kind, _summarize_event(obj), obj, ts=ts, publish=publish)
        if kind == "result":
            self.result = obj

    def feed_stderr(self, text: str, *, ts: datetime | None = None, publish: bool = True) -> None:
        self.stderr_tail.append(text)
        del self.stderr_tail[:-50]
        self.record("stderr", text[:500], {"type": "stderr", "text": text[:2000]},
                    ts=ts, publish=publish)


def _publish_task(task_id: int) -> None:
    bus.publish("tasks", {"type": "task", "id": task_id})


def _set_run(run_id: int, **fields) -> None:
    with session() as db:
        r = db.get(TaskRun, run_id)
        if r is None:
            return
        for k, v in fields.items():
            setattr(r, k, v)


async def _refuse_to_start(run_id: int, task_id: int, side: str, why: str) -> None:
    """起点不对，这一侧不出闸。

    标成 FAILED 交给 watchdog，而不是直接转人工：它判完异常走的是完全重建，正好能把
    没 clone 成、被人动过的工作区修回来，连着几次都修不好才需要人。
    """
    log.error("run %s 的起点不对，不启动容器：%s", run_id, why)
    _set_run(run_id, status=RUN_FAILED, finished_at=utc_now(), container_exists=False,
             started_at=utc_now(), error=f"未启动：{why}"[:2000])
    _record_event(task_id, side, 1, "lifecycle", f"未启动容器：{why}",
                  {"type": "lifecycle", "side": side, "refused": True, "reason": why})
    _publish_task(task_id)
    bus.publish(f"run:{task_id}", {"type": "finished", "side": side, "status": RUN_FAILED})
    watchdog.wake()


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
        snapshot = gsb_repo.snapshot_sha(task.env_snapshot)
    paths = config.TaskPaths(task_no, side)
    image = settings_store.get("cc.image")
    api_key = settings_store.get("cc.api_key")
    timeout_s = max(60, settings_store.get_int("run.timeout_minutes", 120) * 60)

    # 出闸前再确认一次起点。门禁在领取时查过，但领取到出闸之间隔着排队的那段时间，
    # 期间目录可能被人动过、被上一次没做完的重建留在半路，clone 也可能是被强制启动
    # 绕过去的。而 docker run -v 对着一个不存在的宿主路径会默默建一个空目录挂进去，
    # 模型在空工作区里会自己 git init 从头造一个仓库接着做题，跑完的东西跟这道题毫无
    # 关系，却带着完整的轨迹和一份像模像样的产物，肉眼很难看出来。
    hv = await gsb_repo.verify_head(task_no, side, snapshot)
    if not hv["ok"]:
        await _refuse_to_start(run_id, task_id, side, hv["message"])
        return

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
    sink = OutputSink(task_id, side)
    with session() as db:
        attempt = (db.get(TaskRun, run_id).attempt if db.get(TaskRun, run_id) else 1)
    label = f"启动容器 {paths.container_name} · {image}"
    if attempt > 1:
        label = f"第 {attempt} 次尝试 · " + label
    sink.record("lifecycle", label,
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

    async def read_stdout() -> None:
        """解析出错也要把管道读到底，否则容器写 stdout 会被背压堵死。"""
        try:
            async for line, truncated in iter_lines(proc.stdout):
                text = line.decode("utf-8", "replace").strip()
                if text:
                    sink.feed(text, truncated=truncated)
        except Exception as exc:  # noqa: BLE001
            log.exception("run %s 解析 stdout 中断，转为只排空管道", run_id)
            sink.record("stderr", f"stdout 解析中断，后续过程以轨迹 jsonl 为准：{exc}",
                        {"type": "stderr", "text": repr(exc)[:2000]})
            try:
                while await proc.stdout.read(READ_CHUNK_BYTES):
                    pass
            except Exception:  # noqa: BLE001
                log.exception("run %s 排空 stdout 失败", run_id)

    async def read_stderr() -> None:
        async for line, _ in iter_lines(proc.stderr):
            text = line.decode("utf-8", "replace").rstrip()
            if text:
                sink.feed_stderr(text)

    readers = asyncio.gather(read_stdout(), read_stderr(), return_exceptions=True)
    timed_out = False
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout_s)
    except asyncio.TimeoutError:
        timed_out = True
        sink.record("lifecycle", f"超过 {timeout_s // 60} 分钟，停止容器",
                    {"type": "lifecycle", "timeout": True})
        await dockerx.stop_container(paths.container_name, grace=30)
        try:
            await asyncio.wait_for(proc.wait(), timeout=60)
        except asyncio.TimeoutError:
            proc.kill()
    try:
        results = await asyncio.wait_for(readers, timeout=OUTPUT_DRAIN_SECONDS)
    except asyncio.TimeoutError:
        results = []
        sink.record("stderr", f"容器退出后 {OUTPUT_DRAIN_SECONDS} 秒仍未读完输出，"
                              f"result 可能没采到；收尾时会去容器日志里补",
                    {"type": "stderr", "drain_timeout": True})
    for r in results:
        if isinstance(r, BaseException):
            log.error("run %s 输出读取协程异常: %r", run_id, r)

    exit_code = proc.returncode if proc.returncode is not None else await dockerx.container_exit_code(paths.container_name)
    manual = run_id in _manual_stop
    _manual_stop.discard(run_id)
    sink.record("lifecycle", f"容器退出 · exit={exit_code}",
                {"type": "lifecycle", "exit_code": exit_code, "stderr_tail": sink.stderr_tail[-10:]})

    await finalize(run_id, exit_code=exit_code, result_event=sink.result,
                   timed_out=timed_out, manual_stop=manual, stderr_tail=sink.stderr_tail,
                   retry_events=sink.retry_events, thinking_tokens=sink.thinking_tokens,
                   dropped_events=sink.dropped)


# docker logs -t 的时间戳前缀。docker 给的是 RFC3339Nano，小数位有九位，
# 而 datetime 只认到微秒，所以自己切而不用 fromisoformat。
_LOG_TS = re.compile(r"^(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d+))?Z\s?")


def split_log_ts(raw: str) -> tuple[datetime | None, str]:
    """把 `docker logs -t` 的时间戳前缀切下来，返回 (容器写这行的时刻, 正文)。"""
    m = _LOG_TS.match(raw)
    if not m:
        return None, raw
    y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))
    micro = int((m.group(7) or "")[:6].ljust(6, "0")) if m.group(7) else 0
    try:
        ts = datetime(y, mo, d, h, mi, s, micro, tzinfo=timezone.utc)
    except ValueError:
        return None, raw[m.end():]
    return ts, raw[m.end():]


async def attach_run(run_id: int) -> None:
    """重新接上一个还在跑、但已经没人读它输出的容器，跑完照常收尾。

    用在后端重启和 runner 协程自己炸了之后。题目容器是 sibling 容器，起它的那个
    docker 客户端进程没了，它照样跑完，可 stdout 那根管子断在了那一刻：从此没有事件、
    没有 session_id，连 result 事件都收不到，收尾只能靠退出码降级判定，轮次和用量一律
    为空。界面上的表现就是点进去一片空白，只剩一个按 started_at 算出来的时长在跳。

    容器的输出并没有丢，`docker logs` 能把它从启动到现在的每一行都给回来。所以这里
    不再只是 `docker wait` 等一个退出码，而是把日志从头接回来：先按容器日志里的真实
    时刻重建这一侧的时间线，再跟着后续输出继续记，就当没断过。

    重建前会清掉这一侧已有的事件。断点之前那几条是重放内容的一部分，留着就会重复；
    而重放用的是容器自己的时间戳，落库顺序与 seq 都跟正常跑一致。
    """
    attach_at = utc_now()
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None or run.status != RUN_RUNNING:
            return
        task = db.get(Task, run.task_id)
        if task is None:
            return
        task_id, side, name = task.id, run.side, run.container_name
        attempt, started = run.attempt, as_utc(run.started_at)

    log.info("重新接上容器 %s 的输出（run %s）", name, run_id)
    proc = await asyncio.create_subprocess_exec(
        "docker", "logs", "-f", "-t", name,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout and proc.stderr
    sink = OutputSink(task_id, side)
    state = {"wiped": False, "live": False}

    def before_first_line() -> None:
        """确认真读到日志了，再动已有的事件。读不到就什么都不清，界面至少还剩断点前那几条。"""
        if state["wiped"]:
            return
        state["wiped"] = True
        with session() as db:
            db.query(RunEvent).filter(RunEvent.task_id == task_id, RunEvent.side == side).delete()
        sink.seq = 0
        sink.record("lifecycle", f"第 {attempt} 次尝试 · 重新接上容器 {name}（时间线按容器日志重建）",
                    {"type": "lifecycle", "container": name, "side": side,
                     "attempt": attempt, "reattached": True},
                    ts=started, publish=False)

    async def pump(stream: asyncio.StreamReader, is_stderr: bool) -> None:
        async for line, truncated in iter_lines(stream):
            ts, text = split_log_ts(line.decode("utf-8", "replace").rstrip())
            text = text.strip()
            if not text:
                continue
            before_first_line()
            # 重放阶段只落库。几千条历史事件推到浏览器除了把它卡住没有别的效果，
            # 追平之后发一次 reload，让界面重新拉一遍这条完整的时间线。
            live = ts is None or ts >= attach_at
            if live and not state["live"]:
                state["live"] = True
                bus.publish(f"run:{task_id}", {"type": "reload", "side": side})
            if is_stderr:
                sink.feed_stderr(text, ts=ts, publish=live)
            else:
                sink.feed(text, truncated=truncated, ts=ts, publish=live)

    async def read(stream: asyncio.StreamReader, is_stderr: bool) -> None:
        try:
            await pump(stream, is_stderr)
        except Exception as exc:  # noqa: BLE001
            log.exception("run %s 读 docker logs 中断（stderr=%s）", run_id, is_stderr)
            sink.record("stderr", f"接管期间读日志中断，后续过程以轨迹 jsonl 为准：{exc}",
                        {"type": "stderr", "text": repr(exc)[:2000]})

    readers = asyncio.gather(read(proc.stdout, False), read(proc.stderr, True),
                             return_exceptions=True)
    # 超时这条路径一样要管：漏了它，接管过的那一侧会一直跑下去，没有上限。
    limit = max(1, settings_store.get_int("run.timeout_minutes", 120)) * 60
    elapsed = (utc_now() - started).total_seconds() if started else 0.0
    remain = max(60.0, limit - elapsed)
    timed_out = False
    waited = None
    try:
        waited = await asyncio.wait_for(
            dockerx.run(["docker", "wait", name], timeout=limit + 300), remain)
    except asyncio.TimeoutError:
        timed_out = True
        log.warning("接管的容器 %s 已跑满 %s 分钟，停止并按超时收尾", name, limit // 60)
        sink.record("lifecycle", f"超过 {limit // 60} 分钟，停止容器",
                    {"type": "lifecycle", "timeout": True})
        await dockerx.stop_container(name, grace=30)

    try:
        await asyncio.wait_for(readers, timeout=LOG_REPLAY_DRAIN_SECONDS)
    except asyncio.TimeoutError:
        # 重放没追平就被砍，时间线会缺后半段。如实记一条，别让人以为容器只跑了那么多
        log.warning("run %s 的日志重放 %s 秒还没读完，中断读取", run_id, LOG_REPLAY_DRAIN_SECONDS)
        readers.cancel()
        sink.record("stderr", f"容器日志重放超过 {LOG_REPLAY_DRAIN_SECONDS // 60} 分钟仍未读完，"
                              f"事件流可能缺后半段；完整过程以轨迹 jsonl 为准",
                    {"type": "stderr", "replay_timeout": True})
    if proc.returncode is None:
        proc.kill()

    exit_code = None
    if waited is not None:
        try:
            exit_code = int(waited.out.strip())
        except ValueError:
            exit_code = None
    if exit_code is None:
        exit_code = await dockerx.container_exit_code(name)
    manual = run_id in _manual_stop
    _manual_stop.discard(run_id)
    sink.record("lifecycle", f"容器退出 · exit={exit_code}",
                {"type": "lifecycle", "exit_code": exit_code, "stderr_tail": sink.stderr_tail[-10:]})
    # 时间线是重建出来的，界面手里那份多半只剩断点前的几条，让它重新拉一次
    bus.publish(f"run:{task_id}", {"type": "reload", "side": side})

    await finalize(run_id, exit_code=exit_code, result_event=sink.result,
                   timed_out=timed_out, manual_stop=manual, stderr_tail=sink.stderr_tail,
                   retry_events=sink.retry_events, thinking_tokens=sink.thinking_tokens,
                   dropped_events=sink.dropped, reattached=True)


async def workspace_output(ws: Path, base_sha: str = "", *,
                           settle: bool = False) -> tuple[int, str]:
    """实测这一侧到底产出了什么，返回 (改动文件数, diff 摘要)。

    「零改动」会被判成戛然而止、整侧清掉重跑，是全流程代价最大的一个结论，
    所以下这个结论之前要把两种会读空的情况都排掉：

    一是产物已经被 commit —— 推进流程推产物时就会做。这时 `git status` 干干净净，
    可活是实实在在干了的，所以工作区干净就回头跟起跑点比。

    二是文件系统还没同步过来。容器退出到这里最快只隔几百毫秒，而 macOS 上的
    bind mount 要把容器写的文件同步到宿主再给到本容器，这点时间不够，
    读出来就是一片空白。`settle` 打开时会等一下重读 —— 只在「有轨迹却读不到改动」
    这种自相矛盾的情况下等，正常路径不多花一秒。
    """
    if not (ws / ".git").exists():
        return 0, ""

    async def measure() -> tuple[int, str]:
        st = await dockerx.run(
            ["git", "-C", str(ws), "status", "--porcelain", "--untracked-files=all"], timeout=60)
        n = len([l for l in st.out.splitlines() if l.strip()])
        ds = await dockerx.run(["git", "-C", str(ws), "diff", "--stat"], timeout=60)
        stat = (ds.out.strip() + (f"\n未跟踪/改动文件合计 {n}" if n else "")).strip()
        if n or stat:
            return n, stat
        if not base_sha:
            return 0, ""
        committed = await dockerx.run(
            ["git", "-C", str(ws), "diff", "--stat", f"{base_sha}..HEAD"], timeout=60)
        if not (committed.ok and committed.out.strip()):
            return 0, ""
        names = await dockerx.run(
            ["git", "-C", str(ws), "diff", "--name-only", f"{base_sha}..HEAD"], timeout=60)
        return (len([l for l in names.out.splitlines() if l.strip()]),
                (committed.out.strip() + "\n（已提交，相对起跑点统计）").strip())

    changed, stat = await measure()
    if changed or stat or not settle:
        return changed, stat
    await asyncio.sleep(WORKSPACE_SETTLE_SECONDS)
    return await measure()


def decide_status(*, timed_out: bool, manual_stop: bool, result_event: dict,
                  exit_code: int | None, has_trace: bool,
                  container_gone: bool = False,
                  container_running: bool = False) -> tuple[str, bool]:
    """结束状态判定。第二个返回值表示这是不是「没有 result，只能靠退出码」的收尾。

    正常路径靠 stdout 上的 result 事件定性。采集断过的运行读不到它（收尾时会先去
    容器日志里捞一遍，见 finalize），捞不回来时退出码 0 且这一侧写出了轨迹就按正常
    结束算，否则一小时跑完的题会被判成失败。

    这条降级路径必须要求容器**确实已经退出**。docker 对没退出的容器，
    `.State.ExitCode` 一律给 0（见 dockerx._EXITED_STATES），拿它当退出码的话，
    一个还在干活的容器会被判成「正常结束 · 退出码 0」，题就此收尾，界面上再也看不到
    它其实还在跑。container_exit_code 已经把假 0 挡住了，这里再挡一次：
    容器还在 running 就不许走这条路。

    `container_gone` 与 `manual_stop` 必须分开。前者是「容器找不着了」这个观察，
    后者是「人按了停止」这个事实，只有停止接口能置上。曾经把前者直接当后者用，
    后果是一次跑完的运行被标成人工中断，而 watchdog 对人工中断的态度是「不碰」——
    于是这一侧既不是 FINISHED（配对永远凑不齐），又不算异常（没人来重跑），
    题目就此永久卡死，日志里还一个字都看不到。
    容器被销毁的正当理由很多（advance_pair 推进成功后就会主动销毁），
    所以容器没了不说明这次跑得好不好，轨迹才说明。
    """
    adopted_ok = not result_event and exit_code == 0 and has_trace and not container_running
    if timed_out:
        return RUN_TIMEOUT, False
    if manual_stop:
        return RUN_INTERRUPTED, False
    subtype = result_event.get("subtype", "")
    if result_event and subtype == "success" and not result_event.get("is_error") and exit_code in (0, None):
        return RUN_FINISHED, False
    if adopted_ok:
        return RUN_FINISHED, True
    if container_gone and has_trace and not result_event:
        # 退出码无从查起了，但轨迹是这一侧真跑过的证据，按跑完算
        return RUN_FINISHED, True
    if not result_event and (exit_code in (137, 143) or exit_code is None):
        return RUN_INTERRUPTED, False
    return RUN_FAILED, False


async def finalize(run_id: int, *, exit_code: int | None, result_event: dict,
                   timed_out: bool = False, manual_stop: bool = False,
                   container_gone: bool = False,
                   stderr_tail: list[str] | None = None,
                   retry_events: list[dict] | None = None,
                   thinking_tokens: int = 0, dropped_events: int = 0,
                   reattached: bool = False) -> None:
    """三层判定 + 轨迹解析 + 导出，结果全部落在这一侧的 TaskRun 上。

    可被「接管残留容器」和 watchdog 复用。题目级状态与后续动作（推送产物、开分析、
    重跑）一概不在这里决定，只在最后叫一声 watchdog 让它自己判断。

    已经收过尾的 run 不再改写。收尾的入口有三个（协程守到容器结束、重启后接管、
    巡检补记账），它们可能先后看到同一次运行，而后到的那个手里的信息只会更少
    —— 容器早没了，退出码和 result 都取不到，重算一遍只会把先前正确的结论
    换成一个更差的。
    """
    stderr_tail = stderr_tail or []
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return
        if run.status in RUN_END_STATUSES:
            log.info("run %s 已是 %s，跳过重复收尾", run_id, run.status)
            return
        task = db.get(Task, run.task_id)
        if task is None:
            return
        task_id, side, task_no = task.id, run.side, task.task_no
        since, attempt = run.started_at, run.attempt
        base_sha = gsb_repo.snapshot_sha(task.env_snapshot)
        # 库里记着的人工停止同样作数：按停止的那个进程可能已经不在了，见 TaskRun.stop_requested
        manual_stop = manual_stop or bool(run.stop_requested)
    paths = config.TaskPaths(task_no, side)
    ws = paths.workspace

    # ---- 容器层：现问一次 docker，别只信调用方递过来的那两个数 ----
    # 收尾的入口有三个（协程守着、重启后接管、巡检补记账），后两条手里往往什么都没有：
    # result 是空的、退出码是 inspect 读来的。而容器的每一行输出 docker 都还留着，
    # 所以这里回头去日志尾部把 result 捞一遍 —— 捞回来了，轮次、耗时、用量、subtype
    # 就都是实测值，不必再靠退出码去猜这一侧跑得怎么样。
    snap = await dockerx.container_snapshot(paths.container_name)
    if not snap.get("exists"):
        container_gone = True
    if exit_code is None and snap.get("exit_code") is not None:
        exit_code = snap["exit_code"]
    if snap.get("running") and exit_code is not None:
        # 容器还在跑，手里这个退出码不可能是它的，宁可没有也别拿它去判「正常结束」
        log.warning("run %s 收尾时容器 %s 仍在运行，丢弃退出码 %s",
                    run_id, paths.container_name, exit_code)
        exit_code = None
    result_recovered = False
    if not result_event and snap.get("exists"):
        result_event = await dockerx.tail_result_event(paths.container_name)
        result_recovered = bool(result_event)
        if result_recovered:
            log.info("run %s 的 result 事件是从容器日志尾部补回来的（subtype=%s）",
                     run_id, result_event.get("subtype"))

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
    changed_files, diff_stat = await workspace_output(ws, base_sha, settle=trace_file is not None)

    # ---- 状态判定 ----
    status, adopted_ok = decide_status(timed_out=timed_out, manual_stop=manual_stop,
                                       result_event=result_event, exit_code=exit_code,
                                       has_trace=trace_file is not None,
                                       container_gone=container_gone,
                                       container_running=bool(snap.get("running")))
    gw = gateway_errors(retry_events or [], stderr_tail)
    retries = retry_stats(retry_events or [])

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
    if reattached:
        notes.append("这一侧中途被重新接管（后端重启），事件流按容器日志重建")
    if result_recovered:
        notes.append("事件采集中途断过，这一侧的 result 是收尾时从容器日志尾部补回来的；"
                     "轮次与用量以它为准，事件流可能不完整，完整过程看轨迹 jsonl")
    if adopted_ok:
        notes.append(f"没有采到 result 事件，容器日志尾部也没找到；状态是按退出码 {exit_code} "
                     f"与这一侧的轨迹判定的，轮次与用量取不到")
    if snap.get("oom_killed"):
        notes.append("容器被 OOM 杀掉过，内存额度可能不够")
    if snap.get("running"):
        notes.append(f"收尾时容器 {paths.container_name} 竟然还在运行，退出码按取不到处理")
    if gw:
        note = f"出现网关报错 {'、'.join(gw)}，按平台规则不作为 GSB 判断依据"
        if retries["attempt"]:
            note += f"；CC 自行重试了 {retries['attempt']}/{retries['max_retries'] or '?'} 次"
            note += "，最终跑完了" if status == RUN_FINISHED else "，仍未跑成"
        notes.append(note)
    if attempt > 1:
        notes.append(f"这是第 {attempt} 次尝试，之前的异常已重跑")
    if stderr_tail:
        notes.append("stderr: " + " / ".join(stderr_tail[-3:])[:300])

    verdict = {
        "process": {"exit_code": exit_code, "timed_out": timed_out, "manual_stop": manual_stop,
                    "gateway_errors": gw, "attempt": attempt, "retries": retries,
                    # 这一侧的 result 是采到的还是收尾时从日志补回来的，排查时要分得清
                    "result_recovered": result_recovered,
                    "container_status": snap.get("status", ""),
                    "oom_killed": bool(snap.get("oom_killed"))},
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
        # 按刚才问到的实况写，别一律写 True：容器可能已经被 prune 或人工删掉了，
        # 写死之后详情页会一直显示「容器保留」，而那个数字是人决定要不要进容器捞东西的依据
        run.container_exists = bool(snap.get("exists"))
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
        # 内存集合只够本进程用，见 TaskRun.stop_requested
        run.stop_requested = True
    _manual_stop.add(run_id)
    r = await dockerx.stop_container(name, grace=30)
    return {"ok": r.ok, "message": r.err.strip() or "已发送停止"}
