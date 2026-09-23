"""模型调用层：错误分类与重试策略。

分类这件事今天是有前科的。Cursor CLI 在账号欠费时打的是「Failed to reach the Cursor
API，如果在公司代理后面请设置 HTTPS_PROXY」，一句话把人引去查网络、查 DNS、查代理，
真正的原因（未付账单）要单独去看才知道。所以这里要按关键字认出真实原因，并且分清
哪些错重试有用、哪些重试一百次也一样。
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services import llm


# ---------------- 错误分类 ----------------

@pytest.mark.parametrize("blob, want", [
    ("ActionRequiredError: You have an unpaid invoice Visit cursor.com/dashboard", "未付账单"),
    ("Error: Authentication required. Please run 'agent login' first", "无效"),
    ("Unauthorized", "无效"),
    ("Error: 401 invalid api key", "无效"),
    ("Available models: gpt-5, claude-opus-5", "模型名"),
])
def test_billing_and_auth_errors_are_not_retryable(blob, want):
    """这几类重试没有意义，重试只会把同一句报错延迟几分钟再抛一次。"""
    message, retryable = llm.classify(blob)
    assert retryable is False
    assert want in message


def test_unpaid_invoice_message_points_away_from_the_network():
    """欠费的报错必须明说和网络无关，否则又要去查一遍代理。"""
    message, _ = llm.classify("ActionRequiredError: You have an unpaid invoice")
    assert "网络" in message and "代理" in message
    assert "cursor.com/dashboard" in message


@pytest.mark.parametrize("blob", [
    "Error: 503 Service Unavailable",
    "request timed out",
    "ECONNRESET",
    "socket hang up",
    "rate limit exceeded",
    "Failed to reach the Cursor API",
    "ConnectError: [internal] aborted",
    "Stream ended without turnEnded — connection likely dropped mid-stream",
])
def test_transient_errors_are_retryable(blob):
    assert llm.classify(blob)[1] is True


def test_unknown_error_is_retryable():
    """认不出来的按可重试处理：偶发故障远多于新型永久故障。"""
    assert llm.classify("某种没见过的错")[1] is True


def test_empty_output_still_produces_a_message():
    message, _ = llm.classify("")
    assert message.strip() != ""


# ---------------- 外层信封解析 ----------------

def test_envelope_unwraps_the_result_field():
    text, sid, usage = llm._parse_envelope(
        '{"type":"result","result":"模型说的话","session_id":"s1","usage":{"input":10}}')
    assert (text, sid, usage) == ("模型说的话", "s1", {"input": 10})


def test_envelope_reads_the_last_result_from_stream_json():
    """stream-json 前面的 init / assistant 增量不能盖掉最后的 result。"""
    blob = "\n".join([
        '{"type":"system","subtype":"init"}',
        '{"type":"assistant","message":{"content":[{"type":"text","text":"半"}]}}',
        '{"type":"assistant","message":{"content":[{"type":"text","text":"句"}]}}',
        '{"type":"result","result":"正文","session_id":"s2","usage":{"output":3}}',
    ])
    text, sid, usage = llm._parse_envelope(blob)
    assert (text, sid, usage) == ("正文", "s2", {"output": 3})


def test_envelope_falls_back_to_raw_text():
    assert llm._parse_envelope("就是一段纯文本")[0] == "就是一段纯文本"


def test_envelope_refuses_to_pass_off_an_unfinished_event_stream_as_text():
    """启动即被拒时 stdout 正好是 init 加一条 user 回显，这不是正文。

    当成正文交出去，GSB 分析就会拿两行 NDJSON 去解业务 JSON，报一句「没有可解析的
    JSON」，而真正的原因（账单、Key、TLS）只在 stderr，从此看不到。
    """
    blob = "\n".join([
        '{"type":"system","subtype":"init","apiKeySource":"env","session_id":"s3"}',
        '{"type":"user","message":{"role":"user","content":[{"type":"text","text":"题目材料"}]}}',
    ])
    assert llm._parse_envelope(blob) == ("", "", {})


def test_envelope_raises_on_error_result():
    with pytest.raises(llm.LlmError):
        llm._parse_envelope('{"result":"You have an unpaid invoice","is_error":true}')


# ---------------- 重试策略 ----------------

def _stub_once(monkeypatch, outcomes):
    """把 _once 换成按脚本返回的假实现，记录调用次数。"""
    calls = {"n": 0}

    async def fake(prompt, model, timeout_s, cwd=None, purpose=""):
        calls["n"] += 1
        calls["cwd"] = cwd
        calls["purpose"] = purpose
        item = outcomes[min(calls["n"] - 1, len(outcomes) - 1)]
        if isinstance(item, Exception):
            raise item
        return item, "sid", {}

    monkeypatch.setattr(llm, "_once", fake)
    # 退避不能真睡，否则一个用例要跑十几秒。先抓住真正的 sleep 再替换，
    # 直接在 lambda 里调 asyncio.sleep 会调到替换后的自己。
    real_sleep = asyncio.sleep

    async def no_wait(*_a, **_kw):
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", no_wait)
    return calls


def test_ask_does_not_retry_billing_errors(monkeypatch):
    """欠费直接抛，不要退避重试三轮再报同一句话。"""
    calls = _stub_once(monkeypatch, [llm.LlmError("未付账单", retryable=False)])
    with pytest.raises(llm.LlmError) as e:
        asyncio.run(llm.ask("x", model="m", timeout_s=5, attempts=3))
    assert calls["n"] == 1
    assert e.value.retryable is False


def test_ask_retries_transient_errors_then_succeeds(monkeypatch):
    calls = _stub_once(monkeypatch, [llm.LlmError("504", retryable=True), "好了"])
    r = asyncio.run(llm.ask("x", model="m", timeout_s=5, attempts=3))
    assert r.text == "好了"
    assert calls["n"] == 2
    assert r.attempts == 2


def test_ask_gives_up_after_the_attempt_budget(monkeypatch):
    calls = _stub_once(monkeypatch, [llm.LlmError("504", retryable=True)])
    with pytest.raises(llm.LlmError):
        asyncio.run(llm.ask("x", model="m", timeout_s=5, attempts=3))
    assert calls["n"] == 3


def test_ask_defaults_to_two_attempts(monkeypatch):
    """CLI 自己会 resume 断流，外面再整进程重来三次会把一次分析拖到四五十分钟。"""
    calls = _stub_once(monkeypatch, [llm.LlmError("504", retryable=True)])
    with pytest.raises(llm.LlmError):
        asyncio.run(llm.ask("x", model="m", timeout_s=5))
    assert calls["n"] == 2


def test_ask_treats_empty_output_as_retryable(monkeypatch):
    calls = _stub_once(monkeypatch, ["   ", "有内容了"])
    r = asyncio.run(llm.ask("x", model="m", timeout_s=5, attempts=3))
    assert r.text == "有内容了"
    assert calls["n"] == 2


# ---------------- prompt 怎么送进 CLI ----------------

def _stub_subprocess(monkeypatch, tmp_path, stdout: str, *, returncode: int = 0,
                     stderr: str = ""):
    """拦住真正的进程创建，记下 argv 与写进 stdin 的内容。

    _once 现在按行读 stdout，不再走 communicate()，假进程必须提供同样的接口。
    """
    seen: dict = {}

    class FakeStdin:
        def __init__(self) -> None:
            self.buf = bytearray()

        def write(self, data: bytes) -> None:
            self.buf.extend(data)
            seen["stdin"] = bytes(self.buf)

        async def drain(self) -> None:
            seen["stdin"] = bytes(self.buf)

        def close(self) -> None:
            seen["stdin"] = bytes(self.buf)

    class FakeStream:
        def __init__(self, data: bytes) -> None:
            self._data = data
            self._pos = 0

        async def readline(self) -> bytes:
            if self._pos >= len(self._data):
                return b""
            nl = self._data.find(b"\n", self._pos)
            if nl < 0:
                chunk = self._data[self._pos:]
                self._pos = len(self._data)
                return chunk
            chunk = self._data[self._pos:nl + 1]
            self._pos = nl + 1
            return chunk

        async def read(self, n: int = -1) -> bytes:
            if self._pos >= len(self._data):
                return b""
            if n < 0:
                chunk = self._data[self._pos:]
                self._pos = len(self._data)
                return chunk
            chunk = self._data[self._pos:self._pos + n]
            self._pos += len(chunk)
            return chunk

    class FakeProc:
        def __init__(self) -> None:
            self.returncode = returncode
            self.pid = 999999
            self.stdin = FakeStdin()
            payload = stdout.encode("utf-8")
            if payload and not payload.endswith(b"\n"):
                payload += b"\n"
            self.stdout = FakeStream(payload)
            self.stderr = FakeStream(stderr.encode("utf-8"))

        def kill(self) -> None:
            self.returncode = -9

        async def wait(self) -> int:
            return self.returncode

    async def fake_exec(*cmd, **kw):
        seen["cmd"] = list(cmd)
        seen["stdin_mode"] = kw.get("stdin")
        seen["cwd"] = kw.get("cwd")
        seen["limit"] = kw.get("limit")
        return FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(llm, "agent_bin", lambda: "/usr/bin/agent")
    monkeypatch.setattr(llm.settings_store, "get", lambda key, *a: "k" if "api_key" in key else "")
    monkeypatch.setattr(llm, "ASK_DIR", tmp_path)
    monkeypatch.setattr(llm, "HEARTBEAT_S", 3600)
    monkeypatch.setattr(llm, "STALL_S", 3600)
    return seen


def test_prompt_goes_through_stdin_not_argv(monkeypatch, tmp_path):
    """长 prompt 当命令行参数会撞 ARG_MAX。

    GSB 分析要把两侧的 diff 和轨迹摘要一起送进去，几百 KB 是常态，
    当参数传就会报一个跟模型毫无关系的 “Argument list too long”，
    而错误信息里完全看不出是长度问题。
    """
    huge = "材料" * 200_000
    seen = _stub_subprocess(monkeypatch, tmp_path, '{"result":"好了","is_error":false}')

    text, _sid, _usage = asyncio.run(llm._once(huge, "auto", 60))

    assert text == "好了"
    assert seen["stdin"] == huge.encode("utf-8")
    assert huge not in seen["cmd"]
    # 整条命令行应当短得离谱，与 prompt 长度无关
    assert sum(len(c) for c in seen["cmd"]) < 500
    assert "--output-format" in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("--output-format") + 1] == "stream-json"
    assert "--sandbox" in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("--sandbox") + 1] == "disabled"
    assert "--stream-partial-output" in seen["cmd"]
    assert "--workspace" in seen["cmd"]
    assert seen["limit"] == llm.STREAM_LIMIT


def test_nonzero_exit_still_keeps_a_result(monkeypatch, tmp_path):
    """CLI 拿到 result 之后收尾阶段被掐掉很常见，有正文就不要整段重跑。"""
    blob = '{"type":"system","subtype":"init"}\n{"type":"result","result":"已经写完了"}'
    _stub_subprocess(monkeypatch, tmp_path, blob, returncode=1)
    text, _sid, _usage = asyncio.run(llm._once("x", "auto", 60))
    assert text == "已经写完了"


# 账单被拦时 CLI 只吐 init 加一条 user 回显，报错单独走 stderr。
_REJECTED_STDOUT = (
    '{"type":"system","subtype":"init","apiKeySource":"env","session_id":"s"}\n'
    '{"type":"user","message":{"role":"user","content":[{"type":"text","text":"题目材料"}]}}'
)
_UNPAID = ("ActionRequiredError: You have an unpaid invoice Visit "
           "[cursor.com/dashboard](https://cursor.com/dashboard) and pay your invoice.")


@pytest.mark.parametrize("returncode", [1, 0])
def test_rejected_before_generating_reports_the_real_reason(monkeypatch, tmp_path, returncode):
    """启动即被拒必须报出 stderr 里的真因，而且不许重试。

    退出码两种都要认：CLI 打完这句话有时以 1 退出，有时以 0 退出，只认非零退出码
    就会把报错丢掉，最后只剩一句「返回空内容」，还要白重试一轮。
    """
    _stub_subprocess(monkeypatch, tmp_path, _REJECTED_STDOUT,
                     returncode=returncode, stderr=_UNPAID)

    with pytest.raises(llm.LlmError) as err:
        asyncio.run(llm._once("x", "auto", 60))

    assert "未付账单" in str(err.value)
    assert err.value.retryable is False


def test_rejected_stdout_never_reaches_the_caller_as_text(monkeypatch, tmp_path):
    """这两行 NDJSON 绝不能当成模型正文往上走。

    以前会当成正文返回，GSB 分析拿它去解业务 JSON，最后报成「没有可解析的 GSB
    JSON」，一道题查半天，真正的原因（账号欠费）从头到尾没露过面。
    """
    _stub_subprocess(monkeypatch, tmp_path, _REJECTED_STDOUT, returncode=1, stderr=_UNPAID)

    with pytest.raises(llm.LlmError) as err:
        asyncio.run(llm._once("x", "auto", 60))

    assert "apiKeySource" not in str(err.value)
    assert "题目材料" not in str(err.value)


def _hanging_proc(monkeypatch, tmp_path, err_chunks: list[bytes], killed: dict):
    """假进程：吐完手里这些块就沉默，永不自行退出，只有被杀才收口。

    现场就是这样的：stderr 第一秒已经有 unpaid invoice，stdout 停在 init 加一条 user
    回显，进程却一直挂着，日志只剩一串「空闲 xxx 秒」，到五分钟才带退出码 1 结束。
    """
    class FakeStdin:
        def write(self, data: bytes) -> None: ...
        async def drain(self) -> None: ...
        def close(self) -> None: ...

    class HangingStream:
        def __init__(self, chunks: list[bytes], done: asyncio.Event) -> None:
            self._chunks = list(chunks)
            self._done = done

        async def readline(self) -> bytes:
            if self._chunks:
                return self._chunks.pop(0)
            await self._done.wait()
            return b""

        async def read(self, n: int = -1) -> bytes:
            return await self.readline()

    class HangingProc:
        def __init__(self) -> None:
            self.pid = 4242424
            self.returncode = None
            self._done = asyncio.Event()
            self.stdin = FakeStdin()
            self.stdout = HangingStream(
                [line.encode("utf-8") + b"\n" for line in _REJECTED_STDOUT.splitlines()],
                self._done)
            self.stderr = HangingStream(err_chunks, self._done)

        def kill(self) -> None:
            self.returncode = 1
            self._done.set()

        async def wait(self) -> int:
            await self._done.wait()
            return self.returncode

    async def fake_exec(*cmd, **kw):
        return HangingProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(llm, "agent_bin", lambda: "/usr/bin/agent")
    monkeypatch.setattr(llm.settings_store, "get",
                        lambda key, *a: "k" if "api_key" in key else "")
    monkeypatch.setattr(llm, "ASK_DIR", tmp_path)
    # 都设得远大于用例时长：这样能证明进程是按 stderr 主动收掉的，
    # 不是靠心跳的卡住判定兜到的。
    monkeypatch.setattr(llm, "HEARTBEAT_S", 3600)
    monkeypatch.setattr(llm, "STALL_S", 3600)
    # 别碰真进程：pid 是编的，getpgid 万一撞上活着的进程组就真杀了。
    monkeypatch.setattr(llm.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(llm.os, "killpg", lambda pgid, sig: killed.__setitem__("pg", pgid))


def test_fatal_stderr_kills_the_cli_instead_of_waiting_it_out(monkeypatch, tmp_path):
    """账单被拦时不许陪着 CLI 空转到卡住判定，那五分钟是纯等待。

    题 219 就是这么来的：23:36 起跑，stderr 第一秒就写了 unpaid invoice，界面上却一直
    显示分析中，到 23:41:57 才落 FAILED。fail-fast 没生效的话这个用例会卡到 wait_for
    超时——抛出来的是 TimeoutError 而不是 LlmError，用例直接红。
    """
    killed: dict = {}
    _hanging_proc(monkeypatch, tmp_path, [_UNPAID.encode("utf-8")], killed)

    async def run():
        # 给 _once 一个很长的自身超时，逼它只能靠 fail-fast 出来
        return await asyncio.wait_for(llm._once("x", "auto", 3600), timeout=5)

    with pytest.raises(llm.LlmError) as err:
        asyncio.run(run())

    # 判因仍走 classify，收尾路径不变
    assert "未付账单" in str(err.value)
    assert err.value.retryable is False
    # 连 CLI 派生的子进程一起收，不是只 kill 它本身
    assert killed.get("pg") == 4242424


def test_fatal_stderr_is_matched_across_chunk_boundaries(monkeypatch, tmp_path):
    """stderr 是分块读的，报错那句被切开也要认出来。

    按单块认的话，切在 "unpaid inv" / "oice" 之间就漏了，于是又回到空转五分钟。
    """
    killed: dict = {}
    blob = _UNPAID.encode("utf-8")
    _hanging_proc(monkeypatch, tmp_path, [blob[:30], blob[30:]], killed)

    async def run():
        return await asyncio.wait_for(llm._once("x", "auto", 3600), timeout=5)

    with pytest.raises(llm.LlmError) as err:
        asyncio.run(run())

    assert "未付账单" in str(err.value)
    assert killed.get("pg") == 4242424


def test_warnings_on_stderr_do_not_kill_a_healthy_run(monkeypatch, tmp_path):
    """CLI 把警告也写 stderr，写了警告照样正常出结果，不能一见 stderr 就杀。

    所以提前收进程只认高置信度的关键字：401 / 403 / forbidden 这类宽松词留到收尾时
    判因，那时已经知道有没有正文了。
    """
    warn = "\x1b[33m! sandbox preflight failed (403 landlock), continuing\x1b[0m"
    _stub_subprocess(monkeypatch, tmp_path,
                     '{"type":"result","result":"分析好了"}', stderr=warn)

    text, _sid, _usage = asyncio.run(llm._once("x", "auto", 60))

    assert text == "分析好了"


def test_result_is_returned_even_if_the_cli_never_lets_go_of_its_pipes(monkeypatch, tmp_path):
    """交完 result 就该回来，不陪 CLI 等到 timeout_s。

    题 235 补交付完整性时就是这样：42 秒拿到 result，进程却不退，派生的进程攥着管道，
    心跳判卡住按进程组杀了也等不到 EOF，一直挂到二十分钟超时才靠超时分支交差。
    这里的假进程被杀也不关管道，只有 result 之后主动收手才出得来。
    """
    killed: dict = {}
    _hanging_proc(monkeypatch, tmp_path, [], killed)
    never = asyncio.Event()

    class StuckStream:
        def __init__(self, lines: list[bytes]) -> None:
            self._lines = list(lines)

        async def readline(self) -> bytes:
            if self._lines:
                return self._lines.pop(0)
            await never.wait()
            return b""

        async def read(self, n: int = -1) -> bytes:
            return await self.readline()

    class StuckProc:
        pid = 4242424
        returncode = None
        stdin = type("S", (), {"write": lambda s, d: None, "close": lambda s: None,
                               "drain": lambda s: asyncio.sleep(0)})()

        def __init__(self) -> None:
            self.stdout = StuckStream([b'{"type":"system","subtype":"init"}\n',
                                       b'{"type":"result","result":"\xe8\xa1\xa5\xe5\xa5\xbd\xe4\xba\x86"}\n'])
            self.stderr = StuckStream([])

        def kill(self) -> None:
            self.returncode = -9

        async def wait(self) -> int:
            await never.wait()
            return 0

    async def fake_exec(*cmd, **kw):
        return StuckProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(llm, "RESULT_GRACE_S", 0.05)

    async def run():
        return await asyncio.wait_for(llm._once("x", "auto", 3600), timeout=5)

    text, _sid, _usage = asyncio.run(run())

    assert text == "补好了"
    assert killed.get("pg") == 4242424


# ---------------- 工作目录与 skill ----------------

def test_ask_defaults_to_the_empty_dir_but_honours_cwd(monkeypatch):
    """工作目录决定 CLI 能翻到什么，两种用法不能混。

    分析要的是「材料只有我给的那一份」，所以默认指向空目录；出题反过来，
    skill 必须能自己读 drafts/brief.md 与 drafts/index.md，所以要能指到工作区。
    """
    calls = _stub_once(monkeypatch, ["答案"])
    asyncio.run(llm.ask("x", model="m", timeout_s=5))
    assert calls["cwd"] is None          # 不给就用 ASK_DIR，由 _once 决定

    calls = _stub_once(monkeypatch, ["答案"])
    asyncio.run(llm.ask("x", model="m", timeout_s=5, cwd=Path("/host/coder")))
    assert calls["cwd"] == Path("/host/coder")


def test_once_runs_in_the_given_cwd(monkeypatch, tmp_path):
    """cwd 要真的落到进程上，只存不传等于没有。"""
    workdir = tmp_path / "coder"
    workdir.mkdir()
    seen = _stub_subprocess(monkeypatch, tmp_path, '{"result":"好了","is_error":false}')

    asyncio.run(llm._once("x", "auto", 60, cwd=workdir))
    assert seen["cwd"] == str(workdir)

    asyncio.run(llm._once("x", "auto", 60))
    assert seen["cwd"] == str(tmp_path)   # ASK_DIR 被 stub 指到了 tmp_path


def test_once_refuses_a_missing_cwd(monkeypatch, tmp_path):
    """工作区没挂上就别起 CLI：它会在一个空目录里跑完，skill 什么都读不到，
    却照样返回一份看着像样的结果。"""
    _stub_subprocess(monkeypatch, tmp_path, '{"result":"x","is_error":false}')
    with pytest.raises(llm.LlmError, match="工作目录不存在"):
        asyncio.run(llm._once("x", "auto", 60, cwd=tmp_path / "缺了"))


def test_ensure_skills_linked_is_idempotent(monkeypatch, tmp_path):
    """preflight 与出题都会调它，反复调不能把链接拆了重建 —— 中间那一小段
    空窗期正好撞上 CLI 启动，skill 就加载不到。"""
    src = tmp_path / "skills"
    (src / "solo-prompt").mkdir(parents=True)
    (src / "solo-prompt" / "SKILL.md").write_text("x", encoding="utf-8")
    link = tmp_path / "home" / ".cursor" / "skills"
    monkeypatch.setattr(llm.config, "SKILL_DIR_MOUNT", src)
    monkeypatch.setattr(llm.config, "SKILL_LINK", link)

    for _ in range(3):
        ok, msg = llm.ensure_skills_linked()
        assert ok, msg
        assert link.is_symlink() and link.resolve() == src.resolve()


def test_ensure_skills_linked_fails_when_the_skill_is_absent(monkeypatch, tmp_path):
    """链接建起来了但 skill 不在，等于没有出题规则。这种情况必须报错：
    CLI 对认不出的 /solo-prompt 不会失败，只会把它当普通文本，模型照字面
    猜一套规则出题，事后分不出用的是哪份口径。"""
    src = tmp_path / "skills"
    src.mkdir()
    monkeypatch.setattr(llm.config, "SKILL_DIR_MOUNT", src)
    monkeypatch.setattr(llm.config, "SKILL_LINK", tmp_path / "home" / ".cursor" / "skills")
    ok, msg = llm.ensure_skills_linked()
    assert not ok and "solo-prompt" in msg


def test_invalid_key_is_recognised_in_either_word_order():
    """CLI 两种说法都要认出来，认不出就会白重试三轮再报一串乱码。"""
    for text in ("Warning: invalid API key",
                 "The provided API key is invalid.",
                 "\x1b[33m⚠ Warning: The provided API key is invalid.\x1b[0m"):
        message, retryable = llm.classify(text)
        assert "API Key 无效" in message, text
        assert retryable is False, text


def test_terminal_colour_codes_never_reach_the_page():
    """CLI 以为自己在对着终端说话，转义码透到界面上就是一串乱码。"""
    message, _ = llm.classify("\x1b[33m⚠ 出了点别的事\x1b[0m")
    assert "\x1b" not in message and "[33m" not in message
