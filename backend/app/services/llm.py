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
from dataclasses import dataclass, field
from pathlib import Path

from app import config
from app.services import settings_store

log = logging.getLogger("llm")

# 问答用的空目录。CLI 会把工作目录当成上下文，指到 /host/coder 这种真实工作区，
# 模型就会顺手去读题库和别的题，材料就不再是我们控制的那一份了。
ASK_DIR = Path("/tmp/solo-ask")

DEFAULT_MODEL = "claude-opus-5-thinking-high"


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
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    except OSError:
        log.exception("杀进程组失败，退回只杀 agent 本身")
    try:
        proc.kill()
    except ProcessLookupError:
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

# 这些是真·临时故障，值得再试
_RETRYABLE = re.compile(
    r"\b(429|500|502|503|504)\b|rate.?limit|timed? ?out|ECONNRESET|ETIMEDOUT|EAI_AGAIN"
    r"|socket hang up|network|temporarily", re.I)


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


def _parse_envelope(stdout: str) -> tuple[str, str, dict]:
    """--output-format json 的外层是单个对象，result 里才是模型说的话。"""
    text = (stdout or "").strip()
    if not text:
        return "", "", {}
    try:
        obj = json.loads(text.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return text, "", {}
    if not isinstance(obj, dict) or "result" not in obj:
        return text, "", {}
    if obj.get("is_error"):
        raise error_from(str(obj.get("result") or ""))
    return str(obj.get("result") or ""), str(obj.get("session_id") or ""), obj.get("usage") or {}


async def _once(prompt: str, model: str, timeout_s: int,
                cwd: Path | None = None) -> tuple[str, str, dict]:
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
    cmd = [binary, "-p", "--output-format", "json", "--mode", "ask", "--trust",
           "--model", model]
    # 单开进程组：超时要连同 CLI 派生的子进程一起收掉
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(workdir), env=env, start_new_session=True,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(prompt.encode("utf-8")), timeout=timeout_s)
    except asyncio.TimeoutError:
        kill_group(proc)
        raise LlmError(f"模型 {timeout_s // 60} 分钟没有返回", retryable=True) from None
    stdout = out.decode("utf-8", "replace")
    stderr = err.decode("utf-8", "replace")
    if proc.returncode != 0:
        # 真正的原因通常在 stderr，stdout 这时多半只有一条 init 事件
        raise error_from(stderr or stdout)
    return _parse_envelope(stdout)


async def ask(prompt: str, *, model: str = "", timeout_s: int = 0,
              attempts: int = 3, purpose: str = "", cwd: Path | None = None) -> LlmResult:
    """问一次模型，拿回文本。失败按可重试与否决定是退避重试还是直接抛。

    cwd 给 CLI 的工作目录，不给就用空的 ASK_DIR，两者的区别见模块头部说明。
    """
    model = model or settings_store.get("cursor.model") or DEFAULT_MODEL
    timeout_s = timeout_s or max(120, settings_store.get_int("cursor.timeout_minutes", 40) * 60)
    attempts = max(1, attempts)
    started = time.time()
    last: LlmError | None = None

    for attempt in range(1, attempts + 1):
        try:
            text, session_id, usage = await _once(prompt, model, timeout_s, cwd=cwd)
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
