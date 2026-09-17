from pathlib import Path

from app.services import prompt_bank

SAMPLE = """题号：01

对应项目

仓库：https://github.com/gy-vs/merge-conflict-lab
本地路径：/Users/x/workspace/01
来源说明：自行设计。

提交参数

任务类型：0-1 代码生成
任务难度：困难
语言/框架：TypeScript, Node.js, Vitest
Harness：Claude Code
Harness 版本：2.1.197
操作系统：MacOS/Linux
环境可复现等级：无外部依赖
初始环境快照：https://github.com/gy-vs/merge-conflict-lab/commit/909033995d94343ccbd98de4945b4135f29fb16d
SessionID：待回填，取轨迹 jsonl 文件名的 UUID
TurnID/PromptID：待回填，取本轮 user 消息的 promptId

以下为发送给模型的 prompt 正文，整段复制。

我要做一个三方合并的内核库。

第二段：hunk 头用标准格式。

题号：02

提交参数

任务类型：Bug修复
任务难度：中等
语言/框架：Python
Harness：Claude Code
Harness 版本：2.1.197
操作系统：MacOS/Linux
环境可复现等级：无外部依赖
初始环境快照：https://github.com/a/b/commit/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
SessionID：
TurnID/PromptID：

以下为发送给模型的 prompt 正文，整段复制。

修一下这个 bug。
"""


def test_parse_multi():
    tasks = prompt_bank.parse_text(SAMPLE)
    assert [t.task_no for t in tasks] == ["01", "02"]
    t1, t2 = tasks
    assert t1.fields["question_type"] == "0-1 代码生成"
    assert t1.fields["harness_version"] == "2.1.197"
    assert t1.meta["仓库"].startswith("https://github.com")
    assert t1.user_prompt.startswith("我要做一个三方合并的内核库。")
    assert "第二段：hunk 头用标准格式。" in t1.user_prompt
    assert "题号" not in t1.user_prompt
    assert t2.user_prompt == "修一下这个 bug。"
    # SessionID / TurnID 不再入库：双跑时两侧各有自己的会话号，题级放不下
    assert "session_id" not in t1.fields and "turn_id" not in t1.fields


def test_import_picks_up_repo_url(tmp_db, tmp_path, monkeypatch):
    """双跑要按分支 clone 两份，仓库地址必须在导入时就拿到。"""
    from app.db import session
    from app.models import Task

    f = tmp_path / "prompt.md"
    f.write_text(SAMPLE, encoding="utf-8")
    monkeypatch.setattr(prompt_bank.config, "prompt_file", lambda: f)
    monkeypatch.setattr(prompt_bank, "archive_files", lambda: [])

    res = prompt_bank.import_tasks()
    assert res["parsed"] == 2
    with session() as db:
        t1 = db.query(Task).filter(Task.task_no == "01").one()
        assert t1.repo_url == "https://github.com/gy-vs/merge-conflict-lab"
        # 第二题题块里没写仓库，留空让门禁去拦，不要瞎猜
        assert db.query(Task).filter(Task.task_no == "02").one().repo_url == ""
