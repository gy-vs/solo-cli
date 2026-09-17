"""stdout 切行：单行超过 asyncio 默认 64KiB 上限时不能把读取协程打死。

真实事故：tool_result 把整份文件连同 structuredPatch 塞进一行（150~240KB），
StreamReader.readline 抛 ValueError，事件流当场断掉，管道没人排空之后容器被背压
堵死，题一直挂到超时。
"""

import asyncio

import pytest

from app.services import runner
from app.services.runner import _iter_lines


async def _collect(payload: bytes, limit: int = 65536) -> list[tuple[bytes, bool]]:
    reader = asyncio.StreamReader(limit=limit)
    reader.feed_data(payload)
    reader.feed_eof()
    return [item async for item in _iter_lines(reader)]


def test_plain_lines():
    out = asyncio.run(_collect(b'{"a":1}\n{"b":2}\n'))
    assert out == [(b'{"a":1}', False), (b'{"b":2}', False)]


def test_last_line_without_newline():
    out = asyncio.run(_collect(b"first\nsecond"))
    assert out == [(b"first", False), (b"second", False)]


def test_long_line_survives_default_limit():
    """readline 会在这里抛 ValueError，_iter_lines 必须原样交出整行。"""
    long = b'{"x":"' + b"y" * 200_000 + b'"}'
    out = asyncio.run(_collect(long + b"\n" + b"after\n"))
    assert out == [(long, False), (b"after", False)]


def test_oversize_line_is_truncated_and_stream_continues(monkeypatch):
    """超过 MAX_LINE_BYTES 的行截断上报，被丢弃的尾巴不能污染下一行。"""
    monkeypatch.setattr(runner, "MAX_LINE_BYTES", 1000)
    out = asyncio.run(_collect(b"z" * 3000 + b"\n" + b"after\n"))
    assert out == [(b"z" * 1000, True), (b"after", False)]


def test_oversize_line_spanning_chunks(monkeypatch):
    """换行迟迟不来时也要截断，否则缓冲会一直涨；尾巴同样不能污染下一行。"""
    monkeypatch.setattr(runner, "MAX_LINE_BYTES", 1000)
    monkeypatch.setattr(runner, "READ_CHUNK_BYTES", 512)
    out = asyncio.run(_collect(b"z" * 5000 + b"\n" + b"after\n"))
    assert out == [(b"z" * 1000, True), (b"after", False)]


def test_readline_would_have_failed():
    """对照用：证明原实现在同样输入上确实会炸。"""
    async def go():
        reader = asyncio.StreamReader(limit=65536)
        reader.feed_data(b"y" * 200_000 + b"\n")
        reader.feed_eof()
        await reader.readline()

    with pytest.raises(ValueError):
        asyncio.run(go())
