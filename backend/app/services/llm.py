"""统一模型调用：一次问完，不让模型自己漫游。

Cursor 没有公开的 chat-completions 接口，能用的只有 CLI，所以这里仍然起 agent，
但把它压成一次纯问答：--mode ask 是只读模式，答完就返回。

和放 agent 自己漫游的区别不在于少传几个参数，而在于可预期。漫游那版一跑四十到
九十分钟，中途装依赖、跑测试、改产物副本，失败原因散在几百次工具调用里，重试一次
就是再赌一小时；这里只有一次请求，超时就是超时，报错就是报错，重试也不留副作用。

工作目录分两种，由调用方给 cwd 决定：

- 不给（默认 ASK_DIR）：一个空目录。材料全部写进 prompt，它没有东西可翻。
  GSB 分析走这条，送进去的 diff 与轨迹摘要必须是我们挑好的那一份。
- 给 coder_root：出题走这条。规则在 solo-prompt skill 里，题库索引与当期口径在
  drafts/ 下，都得让它自己读，所以工作目录必须是真实工作区。

--trust 必须给：CLI 对未信任目录一律拒绝启动，只读模式也不例外。它只表示「这个目录
可以用」，不等于放开 shell；放开 shell 的是 --force / --yolo，这里一次都不传。

--sandbox disabled 也必须给：后端跑在容器里，Landlock / bwrap 没有权限，CLI 每次
启动都会先做一次必失败的 sandbox preflight。关掉能省掉这段空转，也不改变 ask
模式本身不跑 shell 的约束。

输出用 stream-json：json 要等整轮结束才吐一行，HTTP/2 长流在 Docker 里经常被掐掉，
掐掉之后 CLI 自己静默重试、Python 再整进程重来，一次分析能拖到四五十分钟。流式
事件既能保活，也能在进程稍后崩溃时把已经到达的 result 捞出来，不必整段重跑。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import signal
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from app import config
from app.services import settings_store

log = logging.getLogger("llm")

# 问答用的空目录。CLI 会把工作目录当成上下文，指到 /host/coder 这种真实工作区，
# 模型就会顺手去读题库和别的题，材料就不再是我们控制的那一份了。
ASK_DIR = Path("/tmp/solo-ask")

DEFAULT_MODEL = "claude-opus-5-thinking-high"

# 流式输出连续这么久没有任何一行，判定卡住。ask 模式下正常生成会不断打 assistant
# 增量；json 那版 stdout 一直是空的，卡住和「还在想」从外面分不出来。
STALL_S = 300
# 心跳只是给人看进度，不影响判定。
HEARTBEAT_S = 30
# stream-json 一行就是一个事件。默认 64KB 限制会被设计题那种超长 result 打穿。
STREAM_LIMIT = 8 * 1024 * 1024
# 交完 result 之后 CLI 有时不退：它派生的进程还攥着 stdout，管道等不到 EOF，
# 按进程组杀也解不开，只能干等 timeout_s。result 已经是完整答案，给它这么久收尾，
# 过了就直接收掉。
RESULT_GRACE_S = 15


class LlmError(RuntimeError):
    """模型调用失败。

    retryable 区分「再试一次可能就好」和「再试一百次也一样」。账号欠费、Key 无效、
    模型名不存在都属于后者，这类错误重试只是把同一句报错延迟几分钟再抛一次，
    还会把失败原因埋在几轮重试日志下面。
    """

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass
class LlmResult:
    text: str
    model: str = ""
    session_id: str = ""
    usage: dict = field(default_factory=dict)
    duration_s: float = 0.0
    attempts: int = 1


def agent_bin() -> str:
    return shutil.which("agent") or shutil.which("cursor-agent") or ""


def ensure_skills_linked() -> tuple[bool, str]:
    """把挂进来的 skills 目录接到 CLI 认的位置上。返回 (是否可用, 说明)。

    CLI 只在四个固定位置找 skill（`~/.cursor/skills`、`~/.agents/skills` 及项目级的
    两个），没有「指定 skill 目录」的参数。后端跑在容器里，宿主的 skills 目录挂在
    /host/skills，不接过去 CLI 就一个 skill 都看不到，`/solo-prompt` 会被当成普通文本
    发给模型 —— 模型照着字面猜一套出题规则，看起来还真在出题，但用的不是 skill 里的
    那份口径，而这种失败不会报错，只会安静地出一批不合规的题。

    软链接可行：CLI 会跟随软链接发现 skill。本机直接跑时两个路径本来就是同一个，
    此时不动它。
    """
    src, link = config.SKILL_DIR_MOUNT, config.SKILL_LINK
    skill_md = link / config.SKILL_NAME / "SKILL.md"
    try:
        if src.resolve() != link.resolve():
            if link.is_symlink() or link.exists():
                # 已经指对了就别动：重建软链接在并发调用下会出现「刚删掉还没建上」的空窗
                if not (link.is_symlink() and link.resolve() == src.resolve()):
                    if link.is_symlink() or link.is_file():
                        link.unlink()
                    else:
                        return False, f"{link} 已是真实目录，无法链到 {src}"
            if not link.exists():
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(src, target_is_directory=True)
    except OSError as exc:
        return False, f"接 skills 目录失败：{exc}"
    if not skill_md.is_file():
        return False, f"{config.SKILL_NAME} skill 不在 {src}，出题规则无从读取"
    return True, str(skill_md)


def kill_group(proc: asyncio.subprocess.Process) -> None:
    """连 agent 自己起的子进程一起收掉。

    agent 用 start_new_session 起，进程组 ID 等于它的 PID。只杀 agent 本身的话，
    它派生出去的东西会挂到 init 上继续占 CPU。
    """
    pid = getattr(proc, "pid", None)
    if pid:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    try:
        proc.kill()
    except (ProcessLookupError, AttributeError):
        pass


# 这几类报错重试没有意义，必须原样报给人看。CLI 对计费和鉴权失败会打一句
# 「Failed to reach the Cursor API…set HTTPS_PROXY」，把人引去查网络和代理，
# 所以这里要按真正的关键字认，认出来之后换成一句说得清的话。
_FATAL_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"unpaid invoice|ActionRequiredError", re.I),
     "Cursor 账号有未付账单，模型请求被拒。这条报错和网络、代理无关，"
     "到 cursor.com/dashboard 结清，或换一个自己账号下新建的 API Key"),
    # 两种词序都要认：CLI 有时说 "invalid API key"，有时说 "The provided API key
    # is invalid"。只认前者的话后者会掉进兜底分支，把带颜色转义码的原文糊到设置页上，
    # 而且被当成可重试的，白白重试三轮。
    (re.compile(r"Authentication required|Unauthorized|401"
                r"|invalid api ?key|api ?key\b[^.\n]{0,40}\binvalid", re.I),
     "Cursor API Key 无效或已撤销，到设置页换一个"),
    (re.compile(r"Available models:", re.I),
     "模型名不被接受，到设置页换一个模型"),
    (re.compile(r"suspended|forbidden|403", re.I),
     "Cursor 账号无权调用该模型"),
)

# 这几类在 CLI 起来的头几秒就写进 stderr，但进程不会跟着退：账单被拦时它还会空转到
# 五分钟才带退出码 1 结束，日志里只剩一串「空闲 xxx 秒」，看着像在分析，其实第一秒
# 就被拒了。认出来就立刻收掉，省下的全是纯等待——这几类重试也没用，判因照旧走
# classify，收尾路径不变。
# 只认高置信度的关键字。_FATAL_PATTERNS 里 401 / 403 / forbidden 这种宽松词可能出现在
# 无关的警告行里，而 CLI 打了警告仍然正常返回正文是常态，按它们提前杀会把本来能成的
# 调用弄失败；那几个词留给收尾时判因，那时已经知道有没有正文了。
_FATAL_EARLY = re.compile(
    r"unpaid invoice|ActionRequiredError|Authentication required"
    r"|invalid api ?key|api ?key\b[^.\n]{0,40}\binvalid|Available models:", re.I)

# 这些是真·临时故障，值得再试。HTTP/2 长流在容器里被掐掉时，CLI 打的是
# ConnectError / aborted / stream ended，不进 5xx 那组关键字就会被当成「未知错误」
# ——虽然未知也是可重试，但日志里那句原文太长，这里认出来方便对照。
_RETRYABLE = re.compile(
    r"\b(429|500|502|503|504)\b|rate.?limit|timed? ?out|ECONNRESET|ETIMEDOUT|EAI_AGAIN"
    r"|socket hang up|network|temporarily|ConnectError|\[internal\] aborted"
    r"|stream ended without turnEnded|connection likely dropped", re.I)


def error_from(text: str) -> LlmError:
    """把 CLI 的输出直接包成异常。

    retryable 是仅限关键字参数，classify 的返回值不能直接展开进构造函数，
    展开出来的是 TypeError，而这条路径正是所有模型报错的必经之处。
    """
    message, retryable = classify(text)
    return LlmError(message, retryable=retryable)


# CLI 以为自己在对着终端说话，警告行带着颜色转义码。原样存进 auto_error
# 再渲染到页面上就是一串 ←[33m 之类的乱码。
_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def classify(text: str) -> tuple[str, bool]:
    """把 CLI 的输出判成 (给人看的原因, 能否重试)。"""
    blob = _ANSI.sub("", text or "").strip()
    for pattern, message in _FATAL_PATTERNS:
        if pattern.search(blob):
            return message, False
    if _RETRYABLE.search(blob):
        return blob[-400:] or "模型调用失败", True
    # 认不出来的按可重试处理：偶发故障远多于新型永久故障，
    # 而永久故障重试几次之后一样会抛出来，只是慢一点。
    return blob[-400:] or "模型调用失败，没有输出", True


def is_fatal(text: str) -> bool:
    """这句报错是不是「再试也一样」那一类。

    CLI 原文和 classify 翻出来的中文都得认：落进 auto_error 的是翻译后的那句，
    拿它再过一遍 classify 认不出任何英文关键字，于是「模型名不被接受」被当成可重试的，
    看门狗的恢复探测就永远挑不到这道题。
    """
    if not classify(text)[1]:
        return True
    return any(message in (text or "") for _, message in _FATAL_PATTERNS)


def _parse_envelope(stdout: str) -> tuple[str, str, dict]:
    """从 CLI 输出里抽出模型正文。json 和 stream-json 都认。

    stream-json 前面会铺一串 system / assistant 事件，真正的话在 type=result
    那一行的 result 字段。只看最后一行会把半截增量或空行当成正文。

    事件流里没有 result 时不能拿原文顶上。CLI 启动即被拒（账单拦截、Key 失效、
    TLS 没连上）时 stdout 正好是 init 加一条 user 回显，真正的原因只在 stderr。
    把这两行 NDJSON 当正文交出去，「启动即失败」就会冒充成功，上层拿 NDJSON 去解
    业务 JSON，最后报一句格式错误，真因再也看不到。纯文本输出仍然兜底：那是 CLI
    不按 NDJSON 说话的老行为，原文就是正文。
    """
    text = (stdout or "").strip()
    if not text:
        return "", "", {}
    last: dict | None = None
    saw_event = False
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        saw_event = True
        if "result" in obj:
            last = obj
    if last is None:
        return ("", "", {}) if saw_event else (text, "", {})
    if last.get("is_error"):
        raise error_from(str(last.get("result") or ""))
    return str(last.get("result") or ""), str(last.get("session_id") or ""), last.get("usage") or {}


def _event_kind(line: bytes) -> str:
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return "text"
    if not isinstance(obj, dict):
        return "text"
    return str(obj.get("type") or obj.get("subtype") or "event")


def _cli_cmd(binary: str, model: str, workdir: Path) -> list[str]:
    """拼 agent 命令行。参数顺序稳定，方便测试对照。"""
    return [
        binary, "-p",
        "--output-format", "stream-json",
        "--stream-partial-output",
        "--mode", "ask",
        "--trust",
        "--sandbox", "disabled",
        "--workspace", str(workdir),
        "--model", model,
    ]


async def _feed_stdin(proc: asyncio.subprocess.Process, prompt: str) -> None:
    if proc.stdin is None:
        raise LlmError("无法向 Cursor CLI 写入 prompt", retryable=False)
    data = prompt.encode("utf-8")
    try:
        proc.stdin.write(data)
        await proc.stdin.drain()
        proc.stdin.close()
    except (BrokenPipeError, ConnectionResetError) as exc:
        raise LlmError("Cursor CLI 在读完 prompt 之前退出", retryable=True) from exc


async def _read_stdout(proc: asyncio.subprocess.Process, buf: list[bytes],
                       tick: dict) -> None:
    if proc.stdout is None:
        return
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        buf.append(line)
        tick["n"] = int(tick.get("n") or 0) + 1
        tick["kind"] = _event_kind(line)
        tick["at"] = time.time()
        if tick["kind"] == "result":
            tick["result_at"] = time.time()
            log.info("%s CLI 收到 result · %d 个事件 · %.0fs",
                     tick.get("purpose") or "llm", tick["n"],
                     time.time() - float(tick.get("started") or time.time()))
            return


async def _read_stderr(proc: asyncio.subprocess.Process, buf: list[bytes],
                       fatal: dict, purpose: str = "") -> None:
    """读 stderr，认出致命报错就立刻收掉进程，不等它自己退。

    分块读进来的，报错那句话可能被切在两块之间，所以按累积的全文认，不按单块认。
    认出来之后就不再读了：判因需要的关键字已经在 buf 里，而进程刚被杀，继续读只是
    等一个不会再来的 chunk。
    """
    if proc.stderr is None:
        return
    while True:
        chunk = await proc.stderr.read(4096)
        if not chunk:
            break
        buf.append(chunk)
        if _FATAL_EARLY.search(_ANSI.sub("", _decode(buf))):
            fatal["yes"] = True
            log.error("%s CLI 报了致命错误，提前收掉进程，不等它自己退", purpose or "llm")
            kill_group(proc)
            return


async def _heartbeat(proc: asyncio.subprocess.Process, tick: dict, stalled: dict) -> None:
    """定期打进度；stdout 长时间完全没动就杀进程，让外层去重试。

    HTTP/2 被掐掉时 CLI 自己会 resume，stdout 仍可能继续有事件，这种情况不要杀。
    杀的是「进程还在、一行都不吐」——旧的 json 格式就会这样，看起来像在跑，其实
    外面什么都看不到，要等 40 分钟超时。
    """
    while True:
        await asyncio.sleep(HEARTBEAT_S)
        idle = time.time() - float(tick.get("at") or time.time())
        log.info("%s CLI 运行中 %.0fs · 事件 %d · 最近 %s · 空闲 %.0fs",
                 tick.get("purpose") or "llm",
                 time.time() - float(tick.get("started") or time.time()),
                 int(tick.get("n") or 0), tick.get("kind") or "start", idle)
        if idle >= STALL_S:
            stalled["yes"] = True
            log.warning("%s CLI %.0fs 没有新输出，判定卡住",
                        tick.get("purpose") or "llm", idle)
            kill_group(proc)
            return


def _decode(chunks: list[bytes]) -> str:
    return b"".join(chunks).decode("utf-8", "replace")


async def _once(prompt: str, model: str, timeout_s: int,
                cwd: Path | None = None, purpose: str = "") -> tuple[str, str, dict]:
    binary = agent_bin()
    if not binary:
        raise LlmError("后端镜像里没有 Cursor CLI（agent）", retryable=False)
    api_key = settings_store.get("cursor.api_key")
    if not api_key:
        raise LlmError("未配置 Cursor API Key", retryable=False)

    workdir = cwd or ASK_DIR
    if cwd is None:
        ASK_DIR.mkdir(parents=True, exist_ok=True)
    elif not workdir.is_dir():
        raise LlmError(f"工作目录不存在：{workdir}", retryable=False)
    env = dict(os.environ, CURSOR_API_KEY=api_key)
    # CURSOR_MODEL 会盖掉 --model，留着就等于设置页选的模型不起作用
    env.pop("CURSOR_MODEL", None)
    # prompt 走 stdin 而不是命令行参数：GSB 分析要把两侧的 diff 与轨迹摘要
    # 一起送进去，几百 KB 是常态，当参数传会直接撞上 ARG_MAX，
    # 报一个跟模型毫无关系的 “Argument list too long”。
    cmd = _cli_cmd(binary, model, workdir)
    # 单开进程组：超时要连同 CLI 派生的子进程一起收掉
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(workdir), env=env, start_new_session=True,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        limit=STREAM_LIMIT,
    )
    out_buf: list[bytes] = []
    err_buf: list[bytes] = []
    stalled = {"yes": False}
    fatal = {"yes": False}
    tick = {"n": 0, "kind": "start", "at": time.time(), "started": time.time(),
            "purpose": purpose or "llm"}
    log.info("%s CLI 启动 pid=%s model=%s prompt=%d 字符 timeout=%ds",
             purpose or "llm", getattr(proc, "pid", "?"), model, len(prompt), timeout_s)

    async def pump() -> None:
        await _feed_stdin(proc, prompt)
        hb = asyncio.create_task(_heartbeat(proc, tick, stalled), name="llm-heartbeat")
        rest = asyncio.gather(_read_stderr(proc, err_buf, fatal, purpose), proc.wait())
        try:
            await _read_stdout(proc, out_buf, tick)
            if not tick.get("result_at"):
                await rest
                return
            try:
                await asyncio.wait_for(asyncio.shield(rest), RESULT_GRACE_S)
            except asyncio.TimeoutError:
                log.warning("%s CLI 交完 result %ds 还没退出，直接收掉",
                            purpose or "llm", RESULT_GRACE_S)
                kill_group(proc)
        finally:
            hb.cancel()
            rest.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await hb
            with suppress(asyncio.CancelledError, Exception):
                await rest

    try:
        await asyncio.wait_for(pump(), timeout=timeout_s)
    except asyncio.TimeoutError:
        kill_group(proc)
        stdout, stderr = _decode(out_buf), _decode(err_buf)
        # 超时前已经到过 result 就别整段重跑：CLI 收尾阶段被掐掉很常见
        text, sid, usage = _parse_envelope(stdout)
        if text.strip():
            log.warning("%s CLI 超时但已经拿到结果，按成功处理", purpose or "llm")
            return text, sid, usage
        raise LlmError(f"模型 {timeout_s // 60} 分钟没有返回", retryable=True) from None

    stdout, stderr = _decode(out_buf), _decode(err_buf)
    text, sid, usage = _parse_envelope(stdout)
    if text.strip():
        if proc.returncode not in (0, None):
            log.warning("%s CLI 退出码 %s，但已经拿到结果，按成功处理",
                        purpose or "llm", proc.returncode)
        return text, sid, usage
    # 先看 fatal：进程是我们按 stderr 主动杀的，这时说「没有新输出」会把真因换成一句
    # 可重试的假话，白等一轮重试。
    if stalled["yes"] and not fatal["yes"]:
        raise LlmError(f"模型 {STALL_S // 60} 分钟没有新输出", retryable=True)
    # 没拿到正文时一律按 stderr 判因，不看退出码：CLI 被账单或鉴权拦下时会打完
    # 报错再以 0 退出，只认退出码就把这句话丢了，最后只剩一个「返回空内容」。
    if stderr.strip() or proc.returncode not in (0, None):
        # 真正的原因通常在 stderr，stdout 这时多半只有一条 init 事件。
        # 原文一并记下来：classify 会把它归成一句给人看的话，归错了（比如把账单
        # 问题说成模型名问题）就只能靠这条日志对照，否则只能靠手工复现去猜。
        log.error("%s CLI 没有正文 · 退出码 %s · stderr 原文：%s",
                  purpose or "llm", proc.returncode, _ANSI.sub("", stderr.strip())[:600])
        raise error_from(stderr or stdout)
    return text, sid, usage


async def ask(prompt: str, *, model: str = "", timeout_s: int = 0,
              attempts: int = 2, purpose: str = "", cwd: Path | None = None) -> LlmResult:
    """问一次模型，拿回文本。失败按可重试与否决定是退避重试还是直接抛。

    cwd 给 CLI 的工作目录，不给就用空的 ASK_DIR，两者的区别见模块头部说明。

    默认只重试 1 次（attempts=2）。CLI 自己已经会对 HTTP/2 断流做 checkpoint
    resume；外面再整进程重来三次，一次分析就会被拖到四五十分钟。
    """
    model = model or settings_store.get("cursor.model") or DEFAULT_MODEL
    timeout_s = timeout_s or max(120, settings_store.get_int("cursor.timeout_minutes", 40) * 60)
    attempts = max(1, attempts)
    started = time.time()
    last: LlmError | None = None

    for attempt in range(1, attempts + 1):
        try:
            text, session_id, usage = await _once(
                prompt, model, timeout_s, cwd=cwd, purpose=purpose)
        except LlmError as exc:
            last = exc
            if not exc.retryable:
                log.error("%s 模型调用失败，不重试：%s", purpose or "llm", exc)
                raise
            log.warning("%s 模型调用第 %d/%d 次失败：%s", purpose or "llm", attempt, attempts, exc)
            if attempt < attempts:
                await asyncio.sleep(min(30, 5 * attempt))
            continue
        if not text.strip():
            last = LlmError("模型返回了空内容", retryable=True)
            if attempt < attempts:
                await asyncio.sleep(min(30, 5 * attempt))
            continue
        return LlmResult(text=text, model=model, session_id=session_id, usage=usage,
                         duration_s=round(time.time() - started, 1), attempts=attempt)

    raise last or LlmError("模型调用失败", retryable=True)


# ---------------- 设置页探测 ----------------

async def probe_ping() -> dict:
    model = settings_store.get("cursor.model") or DEFAULT_MODEL
    started = time.time()
    try:
        r = await ask("Reply with exactly the single word: pong",
                      model=model, timeout_s=120, attempts=1, purpose="ping")
    except LlmError as exc:
        return {"ok": False, "message": str(exc)}
    ok = "pong" in r.text.lower()
    return {"ok": ok, "message": f"{model} · {round(time.time() - started, 1)}s · {r.text.strip()[:80]}"}


async def probe_models() -> list[str]:
    """API Key 模式下 `agent --list-models` 为空，只能从非法模型名的报错里解析。"""
    binary = agent_bin()
    api_key = settings_store.get("cursor.api_key")
    if not binary or not api_key:
        return []
    ASK_DIR.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CURSOR_API_KEY=api_key)
    env.pop("CURSOR_MODEL", None)
    proc = await asyncio.create_subprocess_exec(
        binary, "-p", "--output-format", "json", "--mode", "ask", "--trust",
        "--sandbox", "disabled",
        "--model", "__probe__", "x",
        env=env, cwd=str(ASK_DIR), start_new_session=True,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=60)
    except asyncio.TimeoutError:
        kill_group(proc)
        return []
    m = re.search(r"Available models:\s*(.+)", (out + err).decode("utf-8", "replace"))
    return [s.strip() for s in m.group(1).split(",") if s.strip()] if m else []


STATIC_MODELS = [
    "claude-opus-5-thinking-high", "claude-opus-5-thinking-xhigh", "claude-opus-5-thinking-max",
    "claude-opus-5-thinking-medium", "claude-opus-5-thinking-low",
    "claude-opus-5-high", "claude-opus-5-medium", "claude-opus-5-low",
    "claude-sonnet-5-thinking-high", "auto",
]
