"""还原时把 prompt.md 里回填过的两行改回占位。

漏了这步，重跑之后文件里留着上一轮的 SessionID，交付的时候分不清是哪一轮。
"""

from app.services.prompt_bank import backfill_file, parse_file
from app.services.task_reset import PENDING_SESSION, PENDING_TURN

TEMPLATE = """题号：07

提交参数
任务类型：0-1 代码生成
初始环境快照：https://github.com/a/b/commit/{sha}
SessionID：{sid}
TurnID/PromptID：{tid}

以下为发送给模型的 prompt 正文，整段复制。

给这个库加一个解析器。
"""


def _write(tmp_path, sid: str, tid: str):
    p = tmp_path / "prompt.md"
    p.write_text(TEMPLATE.format(sha="a" * 40, sid=sid, tid=tid), encoding="utf-8")
    return p


def test_backfill_then_reset_restores_placeholder(tmp_path):
    path = _write(tmp_path, "待回填，取轨迹 jsonl 文件名的 UUID", "待回填，取本轮 user 消息的 promptId")
    task = parse_file(path)[0]

    assert backfill_file(path, "07", task.prompt_hash, "sess-111", "turn-222") == 2
    after = parse_file(path)[0]
    assert after.fields["session_id"] == "sess-111"
    assert after.fields["turn_id"] == "turn-222"
    # 正文不能被动到，否则 prompt_hash 变了就再也定位不到这道题
    assert after.prompt_hash == task.prompt_hash

    assert backfill_file(path, "07", task.prompt_hash, PENDING_SESSION, PENDING_TURN) == 2
    reset = parse_file(path)[0]
    assert reset.fields["session_id"] == PENDING_SESSION
    assert reset.fields["turn_id"] == PENDING_TURN
    assert "sess-111" not in path.read_text(encoding="utf-8")
    assert reset.prompt_hash == task.prompt_hash


def test_reset_only_touches_matching_task(tmp_path):
    """同一个文件里多道题，还原一道不能碰到另一道。"""
    path = tmp_path / "prompt.md"
    block = TEMPLATE.format(sha="b" * 40, sid="sess-A", tid="turn-A")
    path.write_text(block + "\n" + block.replace("题号：07", "题号：08").replace("加一个解析器", "加一个格式化器"),
                    encoding="utf-8")
    seven, eight = parse_file(path)

    backfill_file(path, "07", seven.prompt_hash, PENDING_SESSION, PENDING_TURN)
    a, b = parse_file(path)
    assert a.fields["session_id"] == PENDING_SESSION
    assert b.fields["session_id"] == "sess-A"
    assert b.prompt_hash == eight.prompt_hash
