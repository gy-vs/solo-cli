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
    # evidence 不再带 step：理由里禁止出现步数说法，证据里留着这个字段
    # 等于给模型留了个照抄步号的出口
    assert got["evidence"] == [{"side": "B", "file": "x.py", "quote": ""}]


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

def _material(side: str, **over) -> dict:
    m = {"side": side, "status": "FINISHED", "num_turns": 12,
         "diff_stat": f" src/{side}.ts | 3 +++", "files": [f"M\tsrc/{side}.ts"],
         "patch": f"diff --git a/src/{side}.ts b/src/{side}.ts\n+改动{side}",
         "steps": [f"Edit 改了 src/{side}.ts"], "counts": {}}
    m.update(over)
    return m


def _task(db, **over):
    from app.models import Task

    fields = {"task_no": "07", "prompt_hash": "h", "user_prompt": "做个解析器",
              "question_type": "0-1代码生成", "difficulty": "困难"}
    fields.update(over)
    t = Task(**fields)
    db.add(t)
    db.flush()
    return t


def test_prompt_shows_both_sides_and_bans_excluded_factors(tmp_db):
    from app.db import session

    with session() as db:
        text = ga.build_prompt(_task(db), {s: _material(s) for s in ("A", "B")})

    assert "src/A.ts" in text and "src/B.ts" in text
    assert "改动A" in text and "改动B" in text
    assert "做个解析器" in text
    # 三类被排除的因素必须写进 prompt，否则模型会拿耗时差异当理由
    assert "推理时长" in text
    assert "戛然而止" in text
    assert "网络" in text
    # 不能暗示哪侧是基准
    assert "不要假设某一侧是基准" in text


def test_prompt_is_symmetric_between_sides(tmp_db):
    """两侧的段落结构必须一模一样。

    A、B 是同一个模型跑两次，差异只来自随机性。材料的措辞要是有偏差，
    模型会顺着措辞去找理由，结论就不再是对产物的判断。
    """
    from app.db import session

    with session() as db:
        text = ga.build_prompt(_task(db), {s: _material(s) for s in ("A", "B")})
    a = text.split("=== A 侧 ===")[1].split("=== B 侧 ===")[0]
    b = text.split("=== B 侧 ===")[1].split("【工作步骤】")[0]
    skeleton = lambda s: [ln.split("：")[0] for ln in s.splitlines() if "：" in ln]  # noqa: E731
    assert skeleton(a) == skeleton(b)
    assert "先跑" not in text and "基准侧" not in text


def test_prompt_carries_writing_rules_that_ban_machine_metrics(tmp_db):
    """写作规范必须进 prompt，否则模型写出来的理由会被质检判成机器写的。"""
    from app.db import session

    with session() as db:
        text = ga.build_prompt(_task(db), {s: _material(s) for s in ("A", "B")})
    assert "不写步数" in text
    assert "工具调用次数" in text
    assert "数字密度" in text
    # 反过来，书面语是允许的，不能在 prompt 里禁掉；要收的是篇幅和颗粒度
    assert "写得正式、用词专业不算机器痕迹" in text
    assert "只挑一到两个真正决定胜负的点展开" in text


def test_prompt_asks_for_startup_instructions(tmp_db):
    from app.db import session

    with session() as db:
        text = ga.build_prompt(_task(db, task_no="08"), {s: _material(s) for s in ("A", "B")})
    # 录屏要靠这份启动说明
    assert "a_startup" in text and "b_startup" in text
    assert "录屏" in text


def test_prompt_marks_missing_trace_instead_of_dropping_the_section(tmp_db):
    """没有轨迹时要写明「没有轨迹」，不能让那一段凭空消失。

    段落一旦缺失，两侧的结构就不对称了，模型会把缺失当成那一侧什么都没做。
    """
    from app.db import session

    with session() as db:
        text = ga.build_prompt(_task(db), {"A": _material("A"), "B": _material("B", steps=[])})
    assert "（没有轨迹）" in text


# ---------------- 材料采集 ----------------

def test_truncated_patch_cuts_on_file_boundaries():
    """补丁超预算要按文件切。

    直接切字符会把最后一个文件劈成半截，模型读到残缺的 hunk 会当成代码本身有问题。
    """
    blocks = [f"diff --git a/f{i}.ts b/f{i}.ts\n" + "+x\n" * 50 for i in range(10)]
    out, cut = ga._truncate_patch("".join(blocks), budget=600)
    assert cut is True
    assert out.count("diff --git") < 10
    # 切完不能留半截 hunk：最后一段必须是完整的文件块
    body = out.split("（补丁过长")[0]
    assert body.rstrip().endswith("+x")
    assert "个文件未展开" in out


def test_short_patch_is_not_truncated():
    patch = "diff --git a/a.ts b/a.ts\n+x\n"
    assert ga._truncate_patch(patch, budget=600) == (patch, False)


def test_condensed_steps_drop_step_numbers():
    """轨迹压缩后不能带步号。

    理由里禁止出现步数说法，材料里摆着步号模型就会照抄。
    """
    index = {"steps": [{"tool": "Edit", "summary": "改了 src/a.ts", "index": 38},
                       {"tool": "Bash", "summary": "npm test", "is_error": True}]}
    steps = ga._condense_steps(index)
    assert steps == ["Edit 改了 src/a.ts", "Bash [报错] npm test"]
    assert not any("38" in s for s in steps)


def test_condensed_steps_keep_every_error_when_over_limit():
    """超限抽样时报错步一个都不能丢，失败过程正是判断依据。"""
    steps = [{"tool": "Read", "summary": f"读 {i}"} for i in range(400)]
    steps += [{"tool": "Bash", "summary": f"炸了 {i}", "is_error": True} for i in range(5)]
    got = ga._condense_steps({"steps": steps})
    assert len(got) <= ga.STEP_LIMIT
    assert sum("[报错]" in s for s in got) == 5


def test_condensed_steps_keep_late_errors_that_exceed_the_budget():
    """报错集中在末尾、而且数量逼近上限时，也不能被截断切掉。

    「先抽样再截断」会在这种形状上把末尾的报错整批切没，于是一次全程失败的运行
    在材料里看起来一切正常。
    """
    steps = [{"tool": "Read", "summary": f"读 {i}"} for i in range(400)]
    steps += [{"tool": "Bash", "summary": f"炸了 {i}", "is_error": True} for i in range(300)]
    got = ga._condense_steps({"steps": steps})
    assert len(got) <= ga.STEP_LIMIT
    assert sum("[报错]" in s for s in got) == ga.STEP_LIMIT


def test_condensed_steps_preserve_original_order():
    index = {"steps": [{"tool": "Read", "summary": "一"}, {"tool": "Edit", "summary": "二"},
                       {"tool": "Bash", "summary": "三"}]}
    assert ga._condense_steps(index) == ["Read 一", "Edit 二", "Bash 三"]
