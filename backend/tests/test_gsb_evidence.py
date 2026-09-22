"""证据目录与逐字回查。

这一层要守住的事只有一件：理由里的每一句都能在材料原文里找到出处。所以用例分两组，
一组盯着「材料摊得够不够全」，一组盯着「对不上原文的引用会不会被放过」。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import config
from app.services import gsb_evidence, trace


def _line(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False) + "\n"


LONG_OUTPUT = ("FAIL src/parser.test.ts > 解析嵌套括号\n" + "堆栈第 x 行\n" * 200
               + "AssertionError: 期望 3 个 token，实际 0 个\n")


def _trace_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join([
        _line(type="user", sessionId="s-1", version="2.1.246", isSidechain=False,
              promptId="p-1", message={"role": "user", "content": "修好解析器"}),
        _line(type="assistant", sessionId="s-1",
              message={"role": "assistant", "model": "opus", "content": [
                  {"type": "text", "text": "先跑一遍测试看看现状"},
                  {"type": "tool_use", "id": "t1", "name": "Bash",
                   "input": {"command": "npm test -- src/parser.test.ts"}}]}),
        _line(type="user", sessionId="s-1",
              message={"role": "user", "content": [
                  {"type": "tool_result", "tool_use_id": "t1",
                   "content": LONG_OUTPUT, "is_error": True}]}),
    ]), encoding="utf-8")
    return path


@pytest.fixture()
def coder_root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path)
    return tmp_path


def _materials() -> dict[str, dict]:
    return {s: {"side": s, "status": "FINISHED", "num_turns": 3,
                "diff_stat": f" src/{s}.ts | 3 +++", "files": [f"M\tsrc/{s}.ts"],
                "patch": f"diff --git a/src/{s}.ts b/src/{s}.ts\n+const limit = 3\n"}
            for s in ("A", "B")}


# ---------------- 摊开轨迹 ----------------

def test_dump_steps_keeps_the_whole_tool_output(tmp_path: Path):
    """工具返回要完整留下，这正是压缩那版看不到的东西。

    索引里每步的返回只留 300 字符，一次失败的测试跑下来，断言原文在第 400 个字符上，
    读索引的人只知道「跑了测试」。判断两侧谁真的定位到了问题，靠的就是这一段。
    """
    f = _trace_file(tmp_path / "s-1.jsonl")
    assert len(trace.parse_trace(f)["steps"][1]["result"]) <= 300

    dumped = trace.dump_steps(f)
    assert "AssertionError: 期望 3 个 token，实际 0 个" in dumped
    assert "npm test -- src/parser.test.ts" in dumped
    assert len(dumped) > 2000


def test_dump_steps_marks_failed_steps_and_keeps_order(tmp_path: Path):
    dumped = trace.dump_steps(_trace_file(tmp_path / "s-1.jsonl"))
    assert "← 这一步报错了" in dumped
    assert dumped.index("真人输入") < dumped.index("模型发言") < dumped.index("调用 Bash")


def test_dump_steps_flags_what_it_had_to_clip(tmp_path: Path):
    """单步超限要写明还剩多少、去哪看，不能悄悄切掉。

    悄悄切掉的后果是模型把半截返回当成全部，据此判断「这次跑没有报错」。
    """
    dumped = trace.dump_steps(_trace_file(tmp_path / "s-1.jsonl"), limit=100)
    assert "完整内容在 trace.jsonl 里" in dumped


# ---------------- 摆目录 ----------------

def test_build_lays_out_both_sides(coder_root: Path):
    _trace_file(config.TaskPaths("07", "A").traces / "s-a.jsonl")
    _trace_file(config.TaskPaths("07", "B").traces / "s-b.jsonl")

    base = gsb_evidence.build("07", "修好解析器", _materials())

    assert (base / "prompt.md").read_text(encoding="utf-8") == "修好解析器"
    for side in ("A", "B"):
        for name in ("steps.md", "trace.jsonl", "diff.patch", "files.txt"):
            assert (base / side / name).is_file(), f"{side}/{name} 没摆出来"
        assert "AssertionError" in (base / side / "steps.md").read_text(encoding="utf-8")
    assert "README.md" in "\n".join(p.name for p in base.iterdir())


def test_build_clears_the_previous_round(coder_root: Path):
    """重新分析要把上一轮的材料清干净。

    留着旧补丁，agent 会读到一份和当前产物对不上的材料，而它无从分辨。
    """
    base = gsb_evidence.build("07", "题面", _materials())
    stale = base / "A" / "diff.patch"
    stale.write_text("这是上一轮的补丁", encoding="utf-8")

    gsb_evidence.build("07", "题面", _materials())
    assert "上一轮" not in stale.read_text(encoding="utf-8")


def test_build_marks_a_side_without_trace(coder_root: Path):
    """一侧没轨迹要写明，不能让那个文件缺失——缺失和「没有轨迹」是两回事。"""
    _trace_file(config.TaskPaths("07", "A").traces / "s-a.jsonl")
    base = gsb_evidence.build("07", "题面", _materials())
    assert "没有轨迹文件" in (base / "B" / "steps.md").read_text(encoding="utf-8")


# ---------------- 逐字回查 ----------------

def test_quotes_found_in_the_material_are_kept(coder_root: Path):
    _trace_file(config.TaskPaths("07", "A").traces / "s-a.jsonl")
    gsb_evidence.build("07", "题面", _materials())

    kept, dropped = gsb_evidence.check_quotes("07", [
        {"side": "A", "file": "src/parser.test.ts",
         "quote": "AssertionError: 期望 3 个 token，实际 0 个"},
        {"side": "A", "file": "src/A.ts", "quote": "+const limit = 3"},
    ])
    assert len(kept) == 2 and not dropped


def test_quotes_that_are_not_in_the_material_are_dropped(coder_root: Path):
    """编出来的引用必须被拦下，这是整条链路上唯一能程序化判定编造的地方。"""
    _trace_file(config.TaskPaths("07", "A").traces / "s-a.jsonl")
    gsb_evidence.build("07", "题面", _materials())

    kept, dropped = gsb_evidence.check_quotes("07", [
        {"side": "A", "file": "src/ghost.ts", "quote": "throw new Error('从没出现过')"},
    ])
    assert not kept
    assert len(dropped) == 1 and "找不到" in dropped[0]["why"]


def test_quote_matching_ignores_whitespace(coder_root: Path):
    """转抄时改了缩进和折行不算编造，按原样比会把绝大多数正确引用判错。"""
    _trace_file(config.TaskPaths("07", "A").traces / "s-a.jsonl")
    gsb_evidence.build("07", "题面", _materials())

    kept, _ = gsb_evidence.check_quotes("07", [
        {"side": "A", "file": "x", "quote": "npm test --\n   src/parser.test.ts"},
    ])
    assert len(kept) == 1


def test_short_quotes_are_dropped(coder_root: Path):
    """几个字符的引用在任何材料里都能找到，放行等于这道回查形同虚设。"""
    _trace_file(config.TaskPaths("07", "A").traces / "s-a.jsonl")
    gsb_evidence.build("07", "题面", _materials())

    kept, dropped = gsb_evidence.check_quotes("07", [{"side": "A", "file": "x", "quote": "npm"}])
    assert not kept and "太短" in dropped[0]["why"]


def test_quotes_are_matched_against_their_own_side(coder_root: Path):
    """A 的原文不能给 B 当证据，否则两侧材料就串了。"""
    _trace_file(config.TaskPaths("07", "A").traces / "s-a.jsonl")
    gsb_evidence.build("07", "题面",
                       {"A": _materials()["A"],
                        "B": {**_materials()["B"], "patch": "diff --git a/b b/b\n+别的东西\n"}})

    kept, dropped = gsb_evidence.check_quotes("07", [
        {"side": "B", "file": "x", "quote": "AssertionError: 期望 3 个 token，实际 0 个"},
    ])
    assert not kept and dropped


def test_sides_with_material_skips_an_empty_side(coder_root: Path):
    """一侧既没改动也没轨迹时，引不出原文是事实，不该按「没读材料」论处。"""
    _trace_file(config.TaskPaths("07", "A").traces / "s-a.jsonl")
    gsb_evidence.build("07", "题面",
                       {"A": _materials()["A"], "B": {"side": "B", "files": [], "patch": ""}})
    assert gsb_evidence.sides_with_material("07") == {"A"}


# ---------------- 门槛 ----------------
# 这道门槛真正判的不是「证据够不够多」，而是「它到底有没有去读材料」。材料已经从
# prompt 里拿走了，不读文件是写不出能对上原文的引用的。

def _both_sides(coder_root: Path) -> Path:
    _trace_file(config.TaskPaths("07", "A").traces / "s-a.jsonl")
    _trace_file(config.TaskPaths("07", "B").traces / "s-b.jsonl")
    gsb_evidence.build("07", "题面", _materials())
    return config.TaskPaths("07").analysis


def test_require_evidence_fails_when_nothing_matches(coder_root: Path):
    """一条都对不上，基本可以断定它照着概览编了一份读起来像样的结论。

    这种结果必须当场失败：它带着完整的 verdict 和理由，界面上和一份真读过的分析
    长得一模一样，落库之后人分不出来。
    """
    from app.services import gsb_analyzer as ga

    d = _both_sides(coder_root)
    dropped = [{"side": "A", "quote": "编的一句", "why": "找不到"}]
    with pytest.raises(RuntimeError, match="没有真的去读"):
        ga._require_evidence("07", [], dropped, d)


def test_require_evidence_fails_when_a_side_has_no_citation(coder_root: Path):
    """两侧都有材料时，缺一侧的引用就等于那一侧的判断没有依据。"""
    from app.services import gsb_analyzer as ga

    d = _both_sides(coder_root)
    kept = [{"side": "A", "quote": "+const limit = 3"}]
    with pytest.raises(RuntimeError, match="B 侧有材料"):
        ga._require_evidence("07", kept, [], d)


def test_require_evidence_passes_and_leaves_a_record(coder_root: Path):
    """丢掉几条不算失败，但要留痕——那是转抄不规范，人得能翻出来是哪几句。"""
    from app.services import gsb_analyzer as ga

    d = _both_sides(coder_root)
    kept = [{"side": "A", "quote": "+const limit = 3"},
            {"side": "B", "quote": "+const limit = 3"}]
    dropped = [{"side": "A", "quote": "改了两个字的引用", "why": "找不到"}]
    ga._require_evidence("07", kept, dropped, d)

    record = json.loads((d / "gsb_evidence_check.json").read_text(encoding="utf-8"))
    assert len(record["kept"]) == 2 and len(record["dropped"]) == 1


def test_require_evidence_tolerates_a_side_without_material(coder_root: Path):
    """一侧压根没跑出东西时，只引另一侧是对的，不该因此判失败。"""
    from app.services import gsb_analyzer as ga

    _trace_file(config.TaskPaths("07", "A").traces / "s-a.jsonl")
    gsb_evidence.build("07", "题面",
                       {"A": _materials()["A"], "B": {"side": "B", "files": [], "patch": ""}})
    d = config.TaskPaths("07").analysis
    ga._require_evidence("07", [{"side": "A", "quote": "+const limit = 3"}], [], d)
