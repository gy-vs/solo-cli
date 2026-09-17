"""GSB 分析：输出解析与文本清洗。

清洗这一层单独测，是因为理由会原样交付给评审方——markdown 记号、步数说法、
本机绝对路径漏出去都是实际事故，而模型时不时就会写进来。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services import gsb_analyzer as ga


# ---------------- 结论取值 ----------------

def test_verdict_labels_match_platform_options():
    assert ga.VERDICT_LABEL == {"A": "A 更好", "B": "B 更好", "Same": "Same"}


@pytest.mark.parametrize("raw,want", [
    ("A", "A"), ("b", "B"), ("Same", "Same"), ("SAME", "Same"),
    ("A 更好", "A"), ("B 更好", "B"),
])
def test_normalize_accepts_both_short_and_label(raw, want):
    assert ga.normalize({"verdict": raw})["verdict"] == want


def test_normalize_leaves_unknown_verdict_empty():
    # 猜一个结论会带着「已分析」的样子直接进上传，比空着更难发现
    assert ga.normalize({"verdict": "A 和 B 差不多吧"})["verdict"] == ""
    assert ga.normalize({})["verdict"] == ""


# ---------------- markdown ----------------

def test_strip_markdown_removes_headings_and_bullets():
    text = "## 对比结论\n- A 侧改了 src/a.ts\n* B 侧没改\n1. 还有一点"
    got = ga.strip_markdown(text)
    assert "#" not in got
    assert "- " not in got
    assert "A 侧改了 src/a.ts" in got
    assert "还有一点" in got


def test_strip_markdown_unwraps_bold_and_code():
    got = ga.strip_markdown("A 侧的 **writeNode** 返回了 `{ text, tag }`")
    assert got == "A 侧的 writeNode 返回了 { text, tag }"


def test_strip_markdown_keeps_plain_text_intact():
    text = "A 侧 lib/dumper.js 的 writeNode 改成返回对象，B 侧还是字符串。"
    assert ga.strip_markdown(text) == text


# ---------------- 步数说法 ----------------

@pytest.mark.parametrize("text", [
    "它在第 38 步追到报错",
    "它在第 19、20 步反复读同一个文件",
    "它在第 48 到 51 步原地打转",
    "它在步骤 12 改了配置",
])
def test_strip_steps_removes_step_references(text):
    got = ga.strip_steps(text)
    assert "步" not in got or "步骤" not in got
    assert "38" not in got and "12" not in got or "追到报错" in got or "改了配置" in got


def test_strip_steps_keeps_sentence_readable():
    assert ga.strip_steps("它在第 38 步追到了 parse 的报错") == "它追到了 parse 的报错"


def test_strip_steps_does_not_eat_ordinary_numbers():
    text = "A 侧的 npm test 有 329 个用例全过"
    assert ga.strip_steps(text) == text


# ---------------- 绝对路径 ----------------

def test_strip_paths_makes_sandbox_paths_relative():
    repos = {"A": Path("/data/分析/07/repo-A"), "B": Path("/data/分析/07/repo-B")}
    got = ga.strip_paths("A 侧改了 /data/分析/07/repo-A/src/x.ts", repos)
    assert got == "A 侧改了 src/x.ts"


def test_strip_paths_squashes_other_absolute_paths():
    got = ga.strip_paths("我看了 /Users/someone/secret/notes.md 和 /etc/nginx/conf.d/", {})
    assert "/Users" not in got
    assert "/etc" not in got
    assert "notes.md" in got


def test_strip_paths_handles_container_workspace():
    assert ga.strip_paths("改的是 /workspace/src/main.py", {}) == "改的是 src/main.py"


def test_strip_paths_strips_longest_root_first():
    """副本目录和它的父目录都在列表里时，先剥短的会留下一截 repo-A/ 前缀。"""
    repos = {"A": Path("/x/07/repo-A"), "B": Path("/x/07")}
    assert ga.strip_paths("见 /x/07/repo-A/src/a.ts", repos) == "见 src/a.ts"


# ---------------- 组合清洗 ----------------

def test_normalize_cleans_reason_through_all_three():
    obj = {"verdict": "A",
           "reason": "## 结论\n- 它在第 12 步改了 /workspace/src/a.ts 里的 **parse**"}
    reason = ga.normalize(obj, {})["reason"]
    assert "#" not in reason and "*" not in reason
    assert "第 12 步" not in reason
    assert "/workspace" not in reason
    assert "src/a.ts" in reason and "parse" in reason


def test_normalize_keeps_startup_commands_verbatim():
    """命令要照着能敲，清洗会把路径改坏。"""
    obj = {"verdict": "Same",
           "a_startup": {"steps": ["先装依赖"], "commands": ["cd /workspace && npm run dev"], "note": ""}}
    got = ga.normalize(obj, {})
    assert got["a_startup"]["commands"] == ["cd /workspace && npm run dev"]
    assert got["a_startup"]["steps"] == ["先装依赖"]


def test_normalize_survives_garbage_field_types():
    obj = {"verdict": "A", "reason": None, "a_findings": "不是字典",
           "b_startup": ["不是字典"], "evidence": ["不是字典", {"side": "b", "file": "x.py"}]}
    got = ga.normalize(obj, {})
    assert got["a_findings"] == {"good": [], "bad": []}
    assert got["b_startup"]["steps"] == []
    assert got["evidence"] == [{"side": "B", "step": None, "file": "x.py", "quote": ""}]


# ---------------- JSON 提取 ----------------

def test_extract_json_from_fenced_block():
    text = '说明在此\n```json\n{"verdict": "A", "reason": "因为"}\n```\n'
    assert ga.extract_json(text)["verdict"] == "A"


def test_extract_json_repairs_truncated_tail():
    text = '{"verdict": "B", "reason": "被截断了", "evidence": [{"side": "B"'
    assert ga.extract_json(text)["verdict"] == "B"


def test_extract_json_skips_leading_unrelated_object():
    text = '{"note": "先来一个不相关的对象"}\n{"verdict": "Same", "reason": "等价"}'
    assert ga.extract_json(text)["verdict"] == "Same"


def test_extract_json_raises_without_verdict():
    with pytest.raises(ValueError):
        ga.extract_json('{"delivery": {"score": 4}}')


# ---------------- prompt ----------------

def test_prompt_shows_both_sides_and_bans_excluded_factors(tmp_db):
    from app.db import session
    from app.models import Task, TaskRun

    with session() as db:
        t = Task(task_no="07", prompt_hash="h", user_prompt="做个解析器",
                 question_type="0-1代码生成", difficulty="困难")
        db.add(t)
        db.flush()
        runs = {}
        for side in ("A", "B"):
            r = TaskRun(task_id=t.id, side=side, trace_file=f"/x/{side}.jsonl",
                        git_diff_stat=f"{side} 侧改了 3 个文件")
            db.add(r)
            db.flush()
            runs[side] = r
        text = ga.build_prompt(t, runs, {"A": Path("/x/repo-A"), "B": Path("/x/repo-B")})

    assert "repo-A" in text and "repo-B" in text
    assert "A 侧改了 3 个文件" in text and "B 侧改了 3 个文件" in text
    assert "做个解析器" in text
    # 三类被排除的因素必须写进 prompt，否则模型会拿耗时差异当理由
    assert "推理时长" in text
    assert "戛然而止" in text
    assert "网络" in text
    # 不能暗示哪侧是基准
    assert "基准" in text and "不要假设某一侧是基准" in text


def test_prompt_asks_for_startup_instructions(tmp_db):
    from app.db import session
    from app.models import Task, TaskRun

    with session() as db:
        t = Task(task_no="08", prompt_hash="h", user_prompt="x")
        db.add(t)
        db.flush()
        runs = {s: TaskRun(task_id=t.id, side=s) for s in ("A", "B")}
        text = ga.build_prompt(t, runs, {"A": Path("/x/repo-A"), "B": Path("/x/repo-B")})
    # 录屏要靠这份启动说明
    assert "a_startup" in text and "b_startup" in text
    assert "录屏" in text
