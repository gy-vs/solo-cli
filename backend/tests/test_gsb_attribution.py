"""侧别对应：说 A 的要对得上 A 的轨迹，说 B 的要对得上 B 的轨迹。

每一条用例都来自真实的理由正文。报出来的是 7130 那种被平台打回的串侧；放过去的
是扫全部已提交题目时查出来的误报——那些句子侧别写得清楚，只是规则读偏了。
"""

from __future__ import annotations

from app.services import gsb_analyzer
from app.services import gsb_attribution as ga
from app.services import gsb_verifier

A_TRACE = '{"input": "function setNode() {}\\nfunction deleteNode() {}\\nsrc/map.ts"}'
B_TRACE = ('{"input": "class PersistentMap {}\\nfunction setNode() {}\\n'
           'function removeNode() {}\\nsrc/index.ts"}')
BOTH = {"A": A_TRACE, "B": B_TRACE}


def _hard(text, corpora=BOTH):
    return [(h["ref"], h["side"], h["kind"]) for h in ga.hard(text, corpora)]


def _all(text, corpora=BOTH):
    return [(h["ref"], h["side"], h["kind"], h["level"]) for h in ga.check(text, corpora)]


# ---------------- 该报的 ----------------

def test_the_7130_sentence_is_a_cross_side_hard_fail():
    text = ("B 的 PersistentMap 在 size 计算上存在错误。存储可空值的调用方都会遇到这一问题。"
            "size 应依据 setNode 和 removeNode 返回的插入删除结果更新，A 的实现正是这样处理的。")
    assert _hard(text) == [("removeNode", "A", ga.CROSS)]


def test_being_found_in_the_union_is_not_enough():
    """按并集查这句话永远是通过：removeNode 确实在「轨迹里」，只是不在 A 的轨迹里。"""
    text = "A 在删除时调用 removeNode，并按返回值调整 size。"
    assert ga.grounded("removeNode", BOTH)
    assert _hard(text) == [("removeNode", "A", ga.CROSS)]


def test_a_name_in_neither_trace_is_a_hard_fail_whatever_the_side():
    assert _hard("B 用 dropEntry 清理过期条目。") == [("dropEntry", "B", ga.MISSING)]


def test_a_similar_longer_name_on_the_claimed_side_does_not_count():
    """A 的轨迹里有 removeNodes 不等于有 removeNode，子串一放宽串侧就查不出来了。"""
    corpora = {"A": "removeNodes()", "B": "removeNode()"}
    assert _hard("A 调用 removeNode 做清理。", corpora) == [("removeNode", "A", ga.CROSS)]


def test_names_glued_to_chinese_are_still_extracted():
    """中文和英文之间常常不空格，而 \\b 在「依据removeNode更新」里一个边界都找不到。"""
    assert _hard("A 依据removeNode的返回值更新计数。") == [("removeNode", "A", ga.CROSS)]


def test_json_escapes_in_the_trace_do_not_hide_a_name():
    """jsonl 里「\\nremoveNode」前一个字符是 n，不抹掉转义就按标识符边界找不到。"""
    assert ga.found_in("removeNode", ga._JSON_ESC.sub(" ", B_TRACE))
    assert _hard("B 调用 removeNode 做清理。") == []


def test_a_path_matches_by_its_file_name():
    """正文按仓库根写路径，轨迹里是容器里的绝对路径。"""
    assert _hard("A 把逻辑放进了 src/map.ts。") == []
    assert _hard("A 把逻辑放进了 lib/index.ts。") == [("lib/index.ts", "A", ga.CROSS)]


def test_a_same_ambiguous_sentence_as_7130_is_reported():
    """和 7130 同一个句式：前半句说的是 B，后半句点的却是 A，读的人会记到 A 头上。"""
    text = ("B 同样有两处缺陷。removeNode 只处理了叶子节点，中间节点会残留，"
            "A 采用 deleteNode 的处理更正确；")
    assert _hard(text) == [("removeNode", "A", ga.CROSS)]


# ---------------- 不该报的 ----------------

def test_each_side_named_explicitly_passes():
    assert _hard("A 的 deleteNode 和 B 的 removeNode 都按返回值更新 size。") == []
    assert _hard("A 的 deleteNode 比 B 的 removeNode 多处理了一种边界。") == []


def test_a_semicolon_ends_the_reach_of_the_side_named_after_it():
    """「……；A 的同类验证只停留在临时脚本里」里的 A 管不到分号前面。"""
    text = "B 完成了这一项。removeNode 在 finally 中关闭内层迭代器；A 的同类验证只停留在临时脚本里。"
    assert _hard(text) == []


def test_the_side_being_compared_against_is_not_the_subject():
    """「结构比 B 更清晰」里 B 是比较对象，说的是 A。"""
    text = "A 也有优于 B 的地方。防过期的守卫单独抽成 deleteNode，结构比 B 更清晰。"
    assert _all(text) == []


def test_compared_against_side_and_named_side_being_the_same_is_only_inferred():
    text = "removeNode 只回放服务端返回的稳定路径，比 A 更符合要求，A 没有这层区分。"
    assert _hard(text) == []


def test_a_verdict_clause_does_not_claim_the_sentence():
    """「因此 A 更好」说的是判给谁，不是这句话在描述 A 的实现。"""
    assert _hard("协议上的优势不足以弥补 removeNode 残留节点的问题，因此 A 更好。") == []


def test_an_absence_claim_is_left_to_the_model():
    """「没有 collect_ignore」本来就不该在轨迹里找得到。"""
    got = _all("B 的 conftest 中也没有 collect_ignore。")
    assert got and all(level == ga.SOFT for *_, level in got)


def test_a_side_without_any_trace_is_never_a_hard_fail():
    """没有轨迹是缺材料，不是轨迹里没这回事。"""
    assert _hard("A 调用 removeNode 做清理。", {"A": "", "B": B_TRACE}) == []


def test_inherited_side_is_only_inferred():
    text = "A 的删除路径更完整。它在 removeNode 之后还会回收空桶。"
    got = _all(text)
    assert got == [("removeNode", "A", ga.CROSS, ga.SOFT)]


def test_prose_english_is_not_a_code_reference():
    assert ga.refs_in("两侧都用 TypeScript 写，A 的 NaN 处理和 GitHub 上的讨论一致。") == []


# ---------------- 接到别的环节 ----------------

def test_vet_rewrite_accepts_a_name_that_is_grounded_in_the_traces():
    original = "A 依据 removeNode 更新 size。" * 8
    rewrite = original.replace("removeNode", "deleteNode")
    assert gsb_analyzer.vet_rewrite(rewrite, original, "A")[0] == ""
    fixed, _ = gsb_analyzer.vet_rewrite(rewrite, original, "A",
                                        grounded=lambda t: ga.grounded(t, BOTH))
    assert fixed == rewrite


def test_the_local_verifier_blocks_on_a_cross_side_claim():
    items = gsb_verifier.verify({
        "verdict": "A", "reason": "x",
        "attribution": ga.hard("A 调用 removeNode 做清理。", BOTH),
        "sides": {},
    })["items"]
    assert any(i["name"] == "reason_side_mismatch" and i["level"] == "block" for i in items)
