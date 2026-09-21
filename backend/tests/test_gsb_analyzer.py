"""GSB 分析：输出解析与文本清洗。

清洗这一层单独测，是因为理由会原样交付给评审方——markdown 记号、步数说法、
本机绝对路径漏出去都是实际事故，而模型时不时就会写进来。
"""

from __future__ import annotations

import asyncio
import json
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


# ---------------- 宣判式结论 ----------------
# 光靠 prompt 拦不住，它又是每道题的最后一句，漏一次整段就露怯，所以在清洗里兜死。

@pytest.mark.parametrize("text,want", [
    ("这个权重更低，判 B 更好", "这个权重更低，B 更好"),
    ("所以判 A 更好", "所以 A 更好"),
    ("综合下来判定 B 更好", "综合下来 B 更好"),
    ("这一局判给 A", "这一局 A"),
    ("两边确实等价，判 Same", "两边确实等价，Same"),
])
def test_soften_verdict_drops_the_refereeing_word(text, want):
    assert ga.soften_verdict(text) == want


@pytest.mark.parametrize("text", [
    "两侧对根因的判断一致",
    "A 把未知描述符判成整条规则无效",
    "所以 A 更好",
])
def test_soften_verdict_leaves_ordinary_uses_alone(text):
    assert ga.soften_verdict(text) == text


def test_clean_softens_the_verdict_sentence():
    assert ga._clean("这个权重更低，判 B 更好") == "这个权重更低，B 更好"


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
    # 反过来，书面语是允许的，不能在 prompt 里禁掉；要收的是篇幅、颗粒度和端着的措辞
    assert "不必为了像人而刻意堆口语" in text
    assert "只挑一到两个真正决定胜负的点展开" in text
    assert "不要用「判」字" in text


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


# ---------------- 生成时收口 ----------------
# 写作规范进 prompt 不等于模型会照做：规范收到五六百字之后，交回来的理由仍然普遍
# 一千多字，而核验里篇幅只是黄项拦不住入库。所以生成完要自查并让模型改，改完再查。

CLEAN_REASON = (
    "A 侧 lib/dumper.js 的 writeNode 改成返回对象，标签在嵌套映射里透传下去了；"
    "B 侧只改了 writeNode，锚点用例里 tag 变成 undefined。两边的约束我逐条对过，"
    "A 侧三条都落到了代码里，B 侧漏了保留注释那一条，所以选 A。"
)


def _fake_ask(replies, calls):
    """按顺序吐出 replies 里的回答，并把收到的 prompt 记进 calls。"""

    async def ask(prompt, **kw):
        calls.append(prompt)
        from app.services.llm import LlmResult

        return LlmResult(text=replies[min(len(calls) - 1, len(replies) - 1)])

    return ask


def test_polish_reason_skips_the_model_when_already_compliant(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ga.llm, "ask", _fake_ask(["不该被调用"], calls))
    text, left = asyncio.run(ga.polish_reason(CLEAN_REASON, verdict="A"))
    assert (text, left) == (CLEAN_REASON, [])
    assert calls == []


def test_polish_reason_rewrites_until_compliant(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ga.llm, "ask", _fake_ask([CLEAN_REASON], calls))
    text, left = asyncio.run(ga.polish_reason(CLEAN_REASON * 6, verdict="A"))
    assert left == []
    assert text == CLEAN_REASON
    assert len(calls) == 1


def test_polish_reason_prompt_names_the_actual_defects(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ga.llm, "ask", _fake_ask([CLEAN_REASON], calls))
    asyncio.run(ga.polish_reason(CLEAN_REASON + "真正的分水岭在测试上。", verdict="A"))
    prompt = calls[0]
    assert "分水岭" in prompt
    # 规范原文要一起给，否则模型只知道哪里错、不知道该写成什么样
    assert "只挑一到两个真正决定胜负的点展开" in prompt
    # 这一轮不给材料，必须明确禁止补新事实，否则会补出没核对过的论点
    assert "不要新增正文里没有的事实" in prompt
    assert "不要换结论" in prompt


def test_polish_reason_accepts_partial_shortening(monkeypatch):
    """超篇幅只算一条毛病，只按条数比好坏会把「一千字砍到七百字」整个丢掉。"""
    calls: list[str] = []
    half = CLEAN_REASON * 6          # 仍然超上限，但比原来短
    monkeypatch.setattr(ga.llm, "ask", _fake_ask([half, CLEAN_REASON], calls))
    text, left = asyncio.run(ga.polish_reason(CLEAN_REASON * 12, verdict="A"))
    assert left == []
    assert text == CLEAN_REASON
    # 第一轮收拢被采信了，第二轮才从更短的那一版接着改
    assert len(calls) == 2


def test_polish_reason_refuses_to_trade_too_long_for_too_short(monkeypatch):
    """太短是核验会拦的红项，太长只是黄项，不能当成等价的一条毛病换过去。"""
    calls: list[str] = []
    monkeypatch.setattr(ga.llm, "ask", _fake_ask(["A 侧和 B 侧的差别在 lib/dumper.js。"], calls))
    long = CLEAN_REASON * 6
    text, left = asyncio.run(ga.polish_reason(long, verdict="A", rounds=1))
    assert text == long
    assert left


def test_polish_reason_prompt_aims_at_the_middle_of_the_window(monkeypatch):
    """按上限要它会压到刚好擦线，瞄中位才留出余量。"""
    calls: list[str] = []
    monkeypatch.setattr(ga.llm, "ask", _fake_ask([CLEAN_REASON], calls))
    long = CLEAN_REASON * 6
    asyncio.run(ga.polish_reason(long, verdict="A"))
    aim = (ga.gsb_rules.REASON_TARGET_MIN + ga.gsb_rules.REASON_TARGET_MAX) // 2
    assert f"落在 {aim} 字左右" in calls[0]
    assert f"去掉大约 {ga.gsb_rules.visible_chars(long) - aim} 字" in calls[0]


def test_polish_reason_asks_for_a_rewrite_when_the_gap_is_large(monkeypatch):
    """按删减说它每轮只砍四分之一，要收掉将近一半就得让它重新写一段。"""
    calls: list[str] = []
    monkeypatch.setattr(ga.llm, "ask", _fake_ask([CLEAN_REASON], calls))
    asyncio.run(ga.polish_reason(CLEAN_REASON * 12, verdict="A"))
    assert "这一步不是修剪，是重写" in calls[0]
    calls.clear()
    # 只超出一点点时还是按删减说，重写反而会把已经写好的论证推翻
    asyncio.run(ga.polish_reason(CLEAN_REASON * 6, verdict="A"))
    assert "这一步不是修剪" not in calls[0]
    assert "删掉整个次要论点" in calls[0]


def test_polish_reason_keeps_the_better_version_when_a_rewrite_is_worse(monkeypatch):
    """模型偶尔把一处毛病换成两处，无条件采用就会越改越差。"""
    calls: list[str] = []
    worse = CLEAN_REASON + "## 结论\n作为大语言模型我倾向 A。"
    monkeypatch.setattr(ga.llm, "ask", _fake_ask([worse], calls))
    bad = CLEAN_REASON + "真正的分水岭在测试上。"
    text, left = asyncio.run(ga.polish_reason(bad, verdict="A"))
    assert text == bad
    assert [m for m in left if "分水岭" in m]


def test_polish_reason_survives_a_model_failure(monkeypatch):
    """改写调用失败不能让整道题的分析炸掉，原文留着、毛病回报出去。"""

    async def boom(prompt, **kw):
        from app.services.llm import LlmError

        raise LlmError("网关 504", retryable=True)

    monkeypatch.setattr(ga.llm, "ask", boom)
    bad = CLEAN_REASON + "真正的分水岭在测试上。"
    text, left = asyncio.run(ga.polish_reason(bad, verdict="A"))
    assert text == bad
    assert left


def test_polish_reason_cleans_the_rewrite_like_the_first_pass(monkeypatch):
    """改写稿也要过一遍清洗，模型在这一轮照样会写 markdown 和绝对路径。"""
    calls: list[str] = []
    dirty = "**" + CLEAN_REASON.replace("lib/dumper.js", "/workspace/lib/dumper.js") + "**"
    monkeypatch.setattr(ga.llm, "ask", _fake_ask([dirty], calls))
    text, left = asyncio.run(ga.polish_reason(CLEAN_REASON * 6, verdict="A"))
    assert "**" not in text and "/workspace" not in text
    assert "lib/dumper.js" in text
    assert left == []


def test_polish_reason_gives_up_after_the_round_limit(monkeypatch):
    """改不动就别无限打模型，剩下的毛病交出去让人看见。"""
    calls: list[str] = []
    stuck = CLEAN_REASON * 6 + "真正的分水岭在测试上。"
    monkeypatch.setattr(ga.llm, "ask", _fake_ask([stuck], calls))
    text, left = asyncio.run(ga.polish_reason(stuck, verdict="A", rounds=2))
    assert text == stuck
    assert left and len(calls) == 2


def test_findings_checks_flag_machine_metrics_per_item():
    got = ga.gsb_rules.findings_checks(
        {"good": ["按规范补了严格类型"], "bad": ["它在第 12 步才发现 lib/a.js:30-40 的问题"]},
        label="a_findings.")
    assert any("a_findings.bad[0]" in m and "步数" in m for m in got)
    assert any("行号" in m for m in got)
    assert not any("good[0]" in m for m in got)


def test_findings_do_not_inherit_the_number_density_line():
    """那条线按五六百字的成段散文校准，套到短句上会逼人删掉该写的数字。"""
    dense = {"good": ["改了 2 处 3 项 4 条 5 个 6 次"], "bad": ["漏了 7 条 8 项 9 处"]}
    assert not any("数字" in m for m in ga.gsb_rules.findings_checks(dense))


def test_findings_hollow_wording_is_counted_over_the_whole_block():
    hollow = {"good": ["表现良好", "基本可用"], "bad": ["各有优劣", "看不出差别"]}
    assert any("空话" in m for m in ga.gsb_rules.findings_checks(hollow))


def test_findings_checks_skip_rules_that_only_fit_the_reason():
    """篇幅、是否写到两侧、开头句式对一条条短句不适用。"""
    got = ga.gsb_rules.findings_checks({"good": ["透传了标签"], "bad": []})
    assert got == []


def test_polish_findings_rewrites_until_compliant(monkeypatch):
    calls: list[str] = []
    fixed = {"a_findings": {"good": ["标签在嵌套映射里透传下去了"], "bad": []},
             "b_findings": {"good": [], "bad": ["锚点用例里标签变成了 undefined"]}}
    monkeypatch.setattr(ga.llm, "ask", _fake_ask([json.dumps(fixed, ensure_ascii=False)], calls))
    a = {"good": ["它在第 12 步透传了标签"], "bad": []}
    b = {"good": [], "bad": ["lib/dumper.js:30-40 的标签丢了"]}
    got_a, got_b, left = asyncio.run(ga.polish_findings(a, b))
    assert left == []
    assert got_a == fixed["a_findings"] and got_b == fixed["b_findings"]
    assert len(calls) == 1


def test_polish_findings_rejects_a_rewrite_that_changes_item_counts(monkeypatch):
    """拆条并条会让 findings 和 evidence 对不上。"""
    calls: list[str] = []
    merged = {"a_findings": {"good": ["透传了标签", "多出来的一条"], "bad": []},
              "b_findings": {"good": [], "bad": ["标签丢了"]}}
    monkeypatch.setattr(ga.llm, "ask", _fake_ask([json.dumps(merged, ensure_ascii=False)], calls))
    a = {"good": ["它在第 12 步透传了标签"], "bad": []}
    b = {"good": [], "bad": ["标签丢了"]}
    got_a, _, left = asyncio.run(ga.polish_findings(a, b, rounds=1))
    assert got_a == a
    assert left


def test_polish_findings_skips_the_model_when_already_compliant(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ga.llm, "ask", _fake_ask(["不该被调用"], calls))
    a = {"good": ["透传了标签"], "bad": []}
    b = {"good": [], "bad": ["标签丢了"]}
    assert asyncio.run(ga.polish_findings(a, b)) == (a, b, [])
    assert calls == []


def test_polish_findings_survives_unparsable_output(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(ga.llm, "ask", _fake_ask(["我改好了，见上文"], calls))
    a = {"good": ["它在第 12 步透传了标签"], "bad": []}
    b = {"good": [], "bad": ["标签丢了"]}
    got_a, got_b, left = asyncio.run(ga.polish_findings(a, b))
    assert (got_a, got_b) == (a, b)
    assert left


def test_extract_object_skips_a_leading_example_shell():
    """模型常先吐一个说明用的小对象，取第一个就会拿到那个壳子。"""
    text = '{"note": "下面是结果"}\n{"a_findings": {"good": [], "bad": []}, "b_findings": {}}'
    assert "a_findings" in ga.extract_object(text, "a_findings", "findings JSON")


def test_peer_openings_excludes_self_and_unanalyzed(tmp_db):
    from app.db import session
    from app.models import ANALYSIS_DONE, Task

    with session() as db:
        me = _task(db, task_no="07")
        done = _task(db, task_no="08", prompt_hash="h8")
        done.analysis_status = ANALYSIS_DONE
        done.gsb = {"reason": "两侧对根因的判断一致。" + CLEAN_REASON}
        pending = _task(db, task_no="09", prompt_hash="h9")
        pending.gsb = {"reason": "这道题我比较在意两点。" + CLEAN_REASON}
        db.flush()
        got = ga.peer_openings(db, me.id)
    assert set(got) == {"08"}
    assert got["08"] == ga.gsb_rules.opening_signature("两侧对根因的判断一致。")
