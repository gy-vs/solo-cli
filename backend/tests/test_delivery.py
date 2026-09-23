"""交付完整性：分数与描述的对应、照抄与串侧、生成补问、事实核验、措辞质检、上传字段。

模型调用全部打桩。这里守的是 brief 里那几条硬要求：满分不许带缺陷、4 分要写清扣分点、
3 分及以下要读得出缺陷多重、分数和描述不能打架、描述不能整段照抄理由。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.services import gsb_analyzer, gsb_attribution, gsb_factcheck, gsb_precheck, gsb_rules, gsb_uploader
from app.services.llm import LlmResult

REASON = ("A 侧把超限判定放在解析入口，越界时返回的错误里带着是步数超了还是深度超了，"
          "题目要求的正是这个。B 侧只回了一句解析失败，调用方拿不到可以分辨的信息，"
          "要再读一遍源码才知道是哪一种越界。此外 A 侧补了针对两种越界的用例，B 侧没有。")

A4 = ("src/parser.ts 按题目要求实现了越界判定和最大深度限制，测试也覆盖了这两处；"
      "扣分在深度超限时仍返回笼统的解析失败，没有处理题目要求的错误类型区分。")
B3 = ("src/parser.ts 只实现了越界判定，最大深度限制没有实现，深度超限的输入"
      "会被当成合法结构继续解析，题目要求的核心约束缺失了一半。")
A5 = ("src/parser.ts 覆盖了题目列出的越界判定、最大深度限制和错误类型区分三项要求，"
      "对应用例全部通过，交付物可以直接使用，没有遗漏。")


def _names(delivery, side="A", reason=REASON, bad=None):
    return {n for n, _, _ in gsb_rules.delivery_checks(delivery, side=side, reason=reason, bad_findings=bad)}


def _stub(monkeypatch, replies):
    seen: list[str] = []

    async def ask(prompt, **kw):
        seen.append(prompt)
        return LlmResult(text=replies[min(len(seen) - 1, len(replies) - 1)], model="stub-model")

    monkeypatch.setattr(gsb_analyzer.llm, "ask", ask)
    return seen


# ---------------- 分数与描述 ----------------

@pytest.mark.parametrize("value,want", [(4, 4), ("4", 4), ("3 分", 3), (5.0, 5), (0, None),
                                        (6, None), ("四", None), (True, None), (None, None), (4.5, None)])
def test_parse_score_only_takes_one_to_five(value, want):
    assert gsb_rules.parse_score(value) == want


def test_well_formed_pairs_pass():
    assert _names({"score": 4, "desc": A4}) == set()
    assert _names({"score": 3, "desc": B3}, side="B") == set()
    assert _names({"score": 5, "desc": A5}) == set()


def test_four_described_as_perfect_is_a_mismatch():
    assert "delivery_score_mismatch" in _names({"score": 4, "desc": A4 + "整体非常完整。"})


def test_five_with_a_defect_is_a_mismatch():
    got = _names({"score": 5, "desc": A5.replace("没有遗漏", "错误类型区分有遗漏")})
    assert "delivery_score_mismatch" in got


def test_negated_defect_word_does_not_count():
    """「没有遗漏」是满分描述的正常说法，不能当成缺陷。"""
    assert "delivery_score_mismatch" not in _names({"score": 5, "desc": A5})


def test_four_without_a_deduction_point_is_blocked():
    desc = "src/parser.ts 按题目要求实现了越界判定和最大深度限制，测试也覆盖了这两处，交付物可以直接使用。"
    assert "delivery_no_deduction" in _names({"score": 4, "desc": desc})


def test_four_cannot_carry_a_severe_defect():
    assert "delivery_score_mismatch" in _names({"score": 4, "desc": A4 + "而且项目无法运行。"})


def test_three_cannot_be_described_as_a_minor_flaw():
    assert "delivery_score_mismatch" in _names({"score": 3, "desc": B3 + "整体只是小瑕疵。"}, side="B")


def test_full_marks_conflicting_with_the_reason_is_blocked():
    reason = REASON + "B 侧没有实现最大深度限制。"
    got = _names({"score": 5, "desc": A5}, side="B", reason=reason)
    assert "delivery_reason_conflict" in got


def test_full_marks_conflict_ignores_the_other_side():
    reason = REASON + "B 侧没有实现最大深度限制。"
    assert "delivery_reason_conflict" not in _names({"score": 5, "desc": A5}, side="A", reason=reason)


def test_full_marks_conflicting_with_bad_findings_is_blocked():
    got = _names({"score": 5, "desc": A5}, bad=["深度超限的错误类型没有处理"])
    assert "delivery_reason_conflict" in got


def test_mentioning_the_other_side_is_blocked():
    assert "delivery_other_side" in _names({"score": 4, "desc": A4 + "比 B 更贴题。"})


def test_copying_a_whole_reason_sentence_is_blocked():
    desc = A4 + "B 侧只回了一句解析失败，调用方拿不到可以分辨的信息。"
    assert "delivery_copied" in _names({"score": 4, "desc": desc})
    assert gsb_rules.copied_from(A4, REASON) == ""


def test_short_and_missing_fields_are_blocked():
    assert "delivery_too_short" in _names({"score": 4, "desc": "有遗漏。"})
    assert "delivery_score" in _names({"score": "七", "desc": A4})
    assert "delivery_desc" in _names({"score": 4, "desc": ""})


# ---------------- 生成：归一与补问 ----------------

def test_normalize_carries_delivery():
    gsb = gsb_analyzer.normalize({"verdict": "A", "reason": REASON,
                                  "a_delivery": {"score": "4", "desc": A4},
                                  "b_delivery": {"score": 9, "desc": B3}})
    assert gsb["a_delivery"] == {"score": 4, "desc": A4}
    assert gsb["b_delivery"]["score"] is None
    assert gsb_analyzer.delivery_complete(gsb) is False
    assert gsb_analyzer.delivery_complete({**gsb, "b_delivery": {"score": 3, "desc": B3}}) is True


def test_fill_delivery_only_asks_for_the_missing_side(monkeypatch):
    seen = _stub(monkeypatch, [json.dumps({"a_delivery": {"score": 2, "desc": "不该被采用"},
                                           "b_delivery": {"score": 3, "desc": B3}}, ensure_ascii=False)])
    gsb = {"verdict": "A", "reason": REASON, "a_delivery": {"score": 4, "desc": A4}}
    out, left = asyncio.run(gsb_analyzer.fill_delivery(gsb, "材料", purpose="t"))
    assert out["a_delivery"] == {"score": 4, "desc": A4}
    assert out["b_delivery"] == {"score": 3, "desc": B3}
    assert left == {"A": [], "B": []}
    assert len(seen) == 1


def test_fill_delivery_fails_when_still_missing(monkeypatch):
    _stub(monkeypatch, [json.dumps({"a_delivery": {"score": 4, "desc": A4}}, ensure_ascii=False)])
    with pytest.raises(RuntimeError, match="交付完整性"):
        asyncio.run(gsb_analyzer.fill_delivery({"reason": REASON}, "材料", purpose="t"))


def test_polish_rejects_a_fix_that_invents_a_file(monkeypatch):
    bad = {"a_delivery": {"score": 4, "desc": A4 + "整体非常完整。"}}
    invented = {"a_delivery": {"score": 4, "desc": A4.replace("src/parser.ts", "src/depth_guard.ts")}}
    _stub(monkeypatch, [json.dumps(invented, ensure_ascii=False)])
    gsb = {"reason": REASON, **bad, "b_delivery": {"score": 3, "desc": B3}}
    a, b, left = asyncio.run(gsb_analyzer.polish_delivery(gsb, purpose="t", rounds=1))
    assert a == bad["a_delivery"] and left["A"]


def test_polish_accepts_a_fix_that_clears_the_defect(monkeypatch):
    _stub(monkeypatch, [json.dumps({"a_delivery": {"score": 4, "desc": A4}}, ensure_ascii=False)])
    gsb = {"reason": REASON, "a_delivery": {"score": 4, "desc": A4 + "整体非常完整。"},
           "b_delivery": {"score": 3, "desc": B3}}
    a, b, left = asyncio.run(gsb_analyzer.polish_delivery(gsb, purpose="t", rounds=1))
    assert a == {"score": 4, "desc": A4} and not left["A"]


# ---------------- 事实核验 ----------------

CORPORA = {"A": "edit src/parser.ts\nnpm test passed", "B": "edit src/parser.ts src/depth.ts"}
GSB = {"verdict": "A", "reason": REASON,
       "a_delivery": {"score": 4, "desc": A4}, "b_delivery": {"score": 3, "desc": B3}}


def _check(apply=True, gsb=GSB):
    return asyncio.run(gsb_factcheck.check_delivery(gsb, {}, task_no="t", corpora=CORPORA,
                                                    process={}, apply=apply))


def test_factcheck_skips_tasks_without_delivery():
    assert _check(gsb={"reason": REASON})["status"] == "skipped"


def test_factcheck_ok_when_both_sides_hold(monkeypatch):
    _stub(monkeypatch, [json.dumps({"A": {"verdict": "ok", "problems": []},
                                    "B": {"verdict": "ok", "problems": []}})])
    r = _check()
    assert r["status"] == "ok" and r["fixed"] == {}


def test_factcheck_applies_a_score_fix(monkeypatch):
    new = B3.replace("src/parser.ts 只实现了越界判定", "src/parser.ts 实现了越界判定")
    _stub(monkeypatch, [json.dumps({
        "A": {"verdict": "fix", "problems": [{"quote": "测试也覆盖了这两处", "type": "执行结果",
                                               "claim": "测试覆盖", "fact": "轨迹里没有跑测试"}],
              "score": 3, "desc": new},
        "B": {"verdict": "ok", "problems": []}}, ensure_ascii=False)])
    r = _check()
    assert r["status"] == "fixed"
    assert r["fixed"]["a_delivery"] == {"score": 3, "desc": new}
    assert any("由 4 分改为 3 分" in n for n in r["notes"])


def test_factcheck_counts_a_cross_side_reference_the_model_missed(monkeypatch):
    """A 的描述里写了只在 B 轨迹里出现的文件，模型说没问题也照样算数。"""
    gsb = {**GSB, "a_delivery": {"score": 4, "desc": A4.replace("src/parser.ts", "src/depth.ts")}}
    _stub(monkeypatch, [json.dumps({"A": {"verdict": "ok", "problems": []},
                                    "B": {"verdict": "ok", "problems": []}})])
    r = _check(apply=False, gsb=gsb)
    assert r["status"] == "fail"
    assert r["sides"]["A"]["problems"][0]["type"] == "侧别"


def test_factcheck_rejects_a_fix_that_contradicts_its_score(monkeypatch):
    _stub(monkeypatch, [json.dumps({
        "A": {"verdict": "fix", "problems": [{"quote": "测试也覆盖了这两处", "type": "执行结果",
                                               "claim": "c", "fact": "f"}],
              "score": 4, "desc": A4 + "整体非常完整。"},
        "B": {"verdict": "ok", "problems": []}}, ensure_ascii=False)])
    r = _check()
    assert r["status"] == "fail" and "红项" in r["sides"]["A"]["rewrite_dropped"]


# ---------------- 措辞质检 ----------------

def _precheck(monkeypatch, reply, gsb=GSB):
    monkeypatch.setattr(gsb_attribution, "load_corpora", lambda task_no: CORPORA)
    _stub(monkeypatch, [json.dumps(reply, ensure_ascii=False)])
    return asyncio.run(gsb_precheck.precheck_delivery(gsb, task_no="t"))


def test_precheck_rewrite_keeps_the_score(monkeypatch):
    new = A4.replace("笼统的解析失败", "统一的解析失败")
    r = _precheck(monkeypatch, {"A": {"verdict": "revise",
                                      "issues": [{"quote": "笼统的解析失败", "kind": "句子生硬"}],
                                      "rewrite": new},
                                "B": {"verdict": "pass", "issues": []}})
    assert r["status"] == "fixed"
    assert r["fixed"] == {"a_delivery": {"score": 4, "desc": new}}


def test_precheck_drops_a_rewrite_that_breaks_the_score(monkeypatch):
    r = _precheck(monkeypatch, {"A": {"verdict": "revise",
                                      "issues": [{"quote": "笼统的解析失败", "kind": "句子生硬"}],
                                      "rewrite": A4 + "整体非常完整。"},
                                "B": {"verdict": "pass", "issues": []}})
    assert r["status"] == "fail" and r["fixed"] == {}


def test_delivery_digest_marks_old_reports_stale_only_when_tracked():
    assert gsb_precheck.delivery_digest({"reason": REASON}) == ""
    assert gsb_precheck.delivery_stale({}, GSB) is False
    assert gsb_precheck.delivery_stale({"delivery_digest": ""}, GSB) is True
    assert gsb_precheck.delivery_stale({"delivery_digest": gsb_precheck.delivery_digest(GSB)}, GSB) is False


# ---------------- 上传字段 ----------------

def test_resolve_fields_maps_labels_and_score_types():
    schema = {"fields": [
        {"field_key": "f_as", "label": "A 交付完整性评分", "field_type": "select",
         "options": [{"label": "3分", "value": "o3"}, {"label": "4分", "value": "o4"}]},
        {"field_key": "f_ad", "label": "A 交付完整性描述", "field_type": "textarea"},
        {"field_key": "b_score_delivery", "label": "B 交付完整性评分", "field_type": "number"},
        {"field_key": "gsb_reason", "label": "GSB 理由"},
    ]}
    values = {"a_score_delivery": 4, "a_desc_delivery": A4, "b_score_delivery": 3,
              "b_desc_delivery": B3, "gsb_reason": REASON}
    out = gsb_uploader.resolve_fields(schema, values)
    assert out["f_as"] == "o4"
    assert out["f_ad"] == A4
    assert out["b_score_delivery"] == 3
    assert out["gsb_reason"] == REASON
