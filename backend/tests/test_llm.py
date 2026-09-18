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


def test_envelope_reads_the_last_line_only():
    """stream 残留的前置事件不能被当成正文。"""
    blob = '{"type":"system","subtype":"init"}\n{"type":"result","result":"正文"}'
    assert llm._parse_envelope(blob)[0] == "正文"


def test_envelope_falls_back_to_raw_text():
    assert llm._parse_envelope("就是一段纯文本")[0] == "就是一段纯文本"


def test_envelope_raises_on_error_result():
    with pytest.raises(llm.LlmError):
        llm._parse_envelope('{"result":"You have an unpaid invoice","is_error":true}')


# ---------------- 重试策略 ----------------

def _stub_once(monkeypatch, outcomes):
    """把 _once 换成按脚本返回的假实现，记录调用次数。"""
    calls = {"n": 0}

    async def fake(prompt, model, timeout_s, cwd=None):
        calls["n"] += 1
        calls["cwd"] = cwd
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


def test_ask_treats_empty_output_as_retryable(monkeypatch):
    calls = _stub_once(monkeypatch, ["   ", "有内容了"])
    r = asyncio.run(llm.ask("x", model="m", timeout_s=5, attempts=3))
    assert r.text == "有内容了"
    assert calls["n"] == 2


# ---------------- prompt 怎么送进 CLI ----------------

def _stub_subprocess(monkeypatch, tmp_path, stdout: str):
    """拦住真正的进程创建，记下 argv 与写进 stdin 的内容。"""
    seen: dict = {}

    class FakeProc:
        returncode = 0

        async def communicate(self, data=None):
            seen["stdin"] = data
            return stdout.encode("utf-8"), b""

    async def fake_exec(*cmd, **kw):
        seen["cmd"] = list(cmd)
        seen["stdin_mode"] = kw.get("stdin")
        seen["cwd"] = kw.get("cwd")
        return FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(llm, "agent_bin", lambda: "/usr/bin/agent")
    monkeypatch.setattr(llm.settings_store, "get", lambda key, *a: "k" if "api_key" in key else "")
    monkeypatch.setattr(llm, "ASK_DIR", tmp_path)
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
    assert sum(len(c) for c in seen["cmd"]) < 200


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
