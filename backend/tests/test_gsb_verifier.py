"""上传前核验。每条红项都对应一条平台规则，放过去就是被打回。"""

from __future__ import annotations

import pytest

from app.services import gsb_verifier as gv

SNAP = "c" * 40
GOOD_REASON = (
    "A 侧 lib/dumper.js 的 writeNode 改成返回对象，writeFlowMapping 跟着改了标签透传，"
    "改完之后跑过一轮 npm test，core 那组用例全部通过。B 侧只改了 writeNode，"
    "标签在嵌套映射里丢了，锚点那条用例跑出来 tag 是 undefined，它自己也跑过测试，"
    "输出里嵌套映射那一组是失败的，但收尾的时候没有回头处理这个失败。"
    "两边的需求点我逐条对过代码，A 侧把三条约束都落到了实现里，"
    "还顺手补了一条锚点相关的用例，正好覆盖 B 侧漏掉的那个场景；"
    "B 侧漏了保留注释那一条，交出去的产物在带注释的文档上会丢信息，"
    "下游拿这份输出再解析一次就对不齐了。错误提示两边沿用的都是原来的文案，"
    "这部分看不出差别。真正让我偏向 A 的是它把失败的用例处理掉了，"
    "而 B 明知道有一组没过还是收了尾，所以我选 A。"
)


def _side(side: str, **kw):
    base = dict(session_id=f"sess-{side}", artifact_sha=side.lower() * 40,
                parent_sha=SNAP, changed_files=3, trace_count=1, human_turns=1,
                prompt="做个解析器",
                files=["lib/dumper.js", "src/a.ts", "package.json"])
    base.update(kw)
    return base


def _data(**kw):
    base = dict(verdict="A", reason=GOOD_REASON, user_prompt="做个解析器",
                env_snapshot_sha=SNAP, harness_version="2.1.197", image_version="2.1.197",
                sides={"A": _side("A"), "B": _side("B")})
    base.update(kw)
    return base


def _names(report, level="block"):
    return {i["name"] for i in report["items"] if i["level"] == level}


def test_clean_submission_passes():
    r = gv.verify(_data())
    assert r["overall"] == "ok", r["items"]


# ---------------- 理由 ----------------

def test_short_reason_is_blocked():
    assert "reason_length" in _names(gv.verify(_data(reason="A 比 B 好。")))


def test_same_verdict_needs_longer_reason():
    """Same 要论证两边确实等价，比选边更费笔墨。"""
    r = gv.verify(_data(verdict="Same", reason=GOOD_REASON[:80]))
    assert "reason_length" in _names(r)
    # 同样长度换成 A 就够了
    assert "reason_length" not in _names(gv.verify(_data(verdict="A", reason=GOOD_REASON[:80])))


def test_reason_must_mention_both_sides():
    only_a = ("A 侧 lib/dumper.js 的 writeNode 改成返回对象，我把三条约束逐条对过代码，"
              "都落到了实现里，npm test 的 core 用例 329 个全过，没有发现需求遗漏。")
    assert "reason_both_sides" in _names(gv.verify(_data(reason=only_a)))


# ---------------- AI 痕迹 ----------------
# 判的是「只有程序才数得出来的量」，不是书面语。solo-qa 的 AI 化评分里，
# 步号、工具调用次数、增删行数这些权重最高；而正式、术语密集、长句、长篇幅
# 都被它的评分提示词明确排除在扣分之外。

@pytest.mark.parametrize("bad, rule", [
    ("它在第 12 步改的", "reason_step_ref"),
    ("B 侧步骤 7 才发现", "reason_step_ref"),
    ("A 侧走了 113 次工具调用", "reason_tool_count"),
    ("交互轮次 47 才收敛", "reason_tool_count"),
    ("问题在 lib/dumper.js:120-136", "reason_file_line"),
    ("A 侧新增 1895 行", "reason_diff_stat"),
    ("B 侧耗时 46 分钟", "reason_duration"),
])
def test_machine_metrics_are_blocked(bad, rule):
    assert rule in _names(gv.verify(_data(reason=GOOD_REASON + bad)))


@pytest.mark.parametrize("ok", [
    "我看重的是 writeFlowMapping 有没有把标签透传下去",
    "两侧的实现思路存在本质差异，A 侧采用了访问者模式重构序列化链路，"
    "在架构层面更契合既有抽象，可维护性显著优于 B 侧的局部补丁式修改",
    "首先要看需求点有没有落实，其次才是实现是否优雅",
])
def test_formal_writing_is_not_an_ai_trace(ok):
    """书面语、术语、长句、单个过渡词都不该拦。

    以前这里禁「首先/其次/综上/非常」，既拦不住真正会被判回的东西，
    又把正常的书面表达判成违规，人在界面上改到第五遍也过不了。
    """
    assert _names(gv.verify(_data(reason=GOOD_REASON + ok))) == set()


def test_two_delivery_cliches_are_blocked():
    """单个过渡词放过，凑够两个才是拿套话当骨架。"""
    assert _names(gv.verify(_data(reason=GOOD_REASON + "综上所述"))) == set()
    r = gv.verify(_data(reason=GOOD_REASON + "综上所述，值得注意的是两边都改了"))
    assert "reason_cliche" in _names(r)


def test_dense_numbers_are_blocked():
    dense = "A 侧改了 3 个点 12 处 7 个文件 9 个用例 5 次 2 轮 8 项 4 条 6 类 1 处。"
    assert "reason_number_density" in _names(gv.verify(_data(reason=dense * 2)))


def test_symbol_dump_is_blocked():
    dump = "A 侧动了 parseSelector、parseValue、parseAtrule、parseBlock、parseRaw、parseUrl。"
    assert "reason_symbol_dump" in _names(gv.verify(_data(reason=GOOD_REASON + dump)))


def test_terminal_output_dump_is_blocked():
    r = gv.verify(_data(reason=GOOD_REASON + "跑出来是 43 过 1 败"))
    assert "reason_terminal_dump" in _names(r)


def test_section_labels_are_blocked():
    r = gv.verify(_data(reason="【产物】" + GOOD_REASON))
    assert "reason_section_label" in _names(r)


def test_ai_self_reference_is_blocked():
    r = gv.verify(_data(reason=GOOD_REASON + "作为大语言模型我倾向 A"))
    assert "reason_self_reference" in _names(r)


def test_chat_scaffolding_is_blocked():
    r = gv.verify(_data(reason=GOOD_REASON + "希望对你有帮助"))
    assert "reason_chat_scaffold" in _names(r)


def test_hollow_reason_is_blocked():
    """通篇「各有优劣」「差不多」，删掉套话就没剩下什么。"""
    hollow = "两边各有优劣，难分高下，表现都还行，看不出差别，整体不错，基本可用，问题不大。"
    assert "reason_hollow" in _names(gv.verify(_data(verdict="Same", reason=hollow * 3)))


@pytest.mark.parametrize("bad", ["## 结论\n", "- 一条\n", "**加粗**", "`代码`"])
def test_markdown_marks_are_blocked(bad):
    assert "reason_markdown" in _names(gv.verify(_data(reason=bad + GOOD_REASON)))


def test_emoji_is_blocked():
    assert "reason_emoji" in _names(gv.verify(_data(reason=GOOD_REASON + "✅")))


def test_absolute_path_is_blocked():
    r = gv.verify(_data(reason=GOOD_REASON + "我看的是 /Users/me/repo/x.py"))
    assert "reason_abs_path" in _names(r)


def test_step_reference_is_blocked():
    assert "reason_step_ref" in _names(gv.verify(_data(reason=GOOD_REASON + "它在第 12 步改的")))


def test_unknown_file_reference_is_blocked():
    """理由里凭空出现的文件名，平台会按编造处理（规则 G6）。"""
    r = gv.verify(_data(reason=GOOD_REASON + "另外 nonexistent/ghost.ts 也被改了"))
    assert "reason_unknown_files" in _names(r)


def test_known_file_reference_passes():
    r = gv.verify(_data(reason=GOOD_REASON + "package.json 没动"))
    assert "reason_unknown_files" not in _names(r)


def test_file_check_skipped_when_no_file_list():
    """收不到文件清单时不能瞎拦，否则轨迹索引一缺就全题卡住。"""
    sides = {"A": _side("A", files=[]), "B": _side("B", files=[])}
    r = gv.verify(_data(reason=GOOD_REASON + " ghost.ts 也改了", sides=sides))
    assert "reason_unknown_files" not in _names(r)


# ---------------- 结论 ----------------

@pytest.mark.parametrize("v", ["", "A 更好", "不确定"])
def test_bad_verdict_is_blocked(v):
    assert "verdict" in _names(gv.verify(_data(verdict=v)))


# ---------------- 会话与产物 ----------------

def test_same_session_id_is_blocked():
    sides = {"A": _side("A", session_id="same"), "B": _side("B", session_id="same")}
    assert "session_same" in _names(gv.verify(_data(sides=sides)))


def test_empty_session_id_is_blocked():
    sides = {"A": _side("A", session_id=""), "B": _side("B")}
    assert "session_A" in _names(gv.verify(_data(sides=sides)))


def test_same_artifact_is_blocked():
    sides = {"A": _side("A", artifact_sha="d" * 40), "B": _side("B", artifact_sha="d" * 40)}
    assert "artifact_same" in _names(gv.verify(_data(sides=sides)))


@pytest.mark.parametrize("sha", ["", "abc", "z" * 40, "c" * 39])
def test_malformed_artifact_sha_is_blocked(sha):
    sides = {"A": _side("A", artifact_sha=sha), "B": _side("B")}
    assert "artifact_A" in _names(gv.verify(_data(sides=sides)))


def test_uppercase_sha_is_accepted():
    """git 的 SHA 大小写不敏感，人工填进来的大写不该被当成格式错。"""
    sides = {"A": _side("A", artifact_sha="A" * 40), "B": _side("B")}
    assert "artifact_A" not in _names(gv.verify(_data(sides=sides)))


def test_wrong_parent_commit_is_blocked():
    """父提交不是初始快照，交上去的 diff 里就混着别人的改动（规则 G3）。"""
    sides = {"A": _side("A", parent_sha="f" * 40), "B": _side("B")}
    assert "parent_A" in _names(gv.verify(_data(sides=sides)))


# ---------------- 轨迹 ----------------

@pytest.mark.parametrize("count", [0, 2, 3])
def test_trace_count_must_be_one(count):
    sides = {"A": _side("A", trace_count=count), "B": _side("B")}
    assert "trace_count_A" in _names(gv.verify(_data(sides=sides)))


@pytest.mark.parametrize("turns", [0, 2, None])
def test_human_turns_must_be_exactly_one(turns):
    sides = {"A": _side("A"), "B": _side("B", human_turns=turns)}
    assert "human_turns_B" in _names(gv.verify(_data(sides=sides)))


def test_prompt_mismatch_between_sides_is_blocked():
    sides = {"A": _side("A", prompt="做个解析器"), "B": _side("B", prompt="做个别的东西")}
    assert "prompt_mismatch" in _names(gv.verify(_data(sides=sides)))


def test_prompt_mismatch_with_bank_is_blocked():
    sides = {"A": _side("A", prompt="改过的题面"), "B": _side("B", prompt="改过的题面")}
    assert "prompt_mismatch" in _names(gv.verify(_data(sides=sides)))


def test_whitespace_only_prompt_diff_is_fine():
    sides = {"A": _side("A", prompt="做个 解析器\n"), "B": _side("B", prompt="做个解析器")}
    assert "prompt_mismatch" not in _names(gv.verify(_data(sides=sides)))


def test_missing_side_is_blocked():
    assert "side_B" in _names(gv.verify(_data(sides={"A": _side("A")})))


# ---------------- 黄项 ----------------

def test_zero_change_is_only_a_warning():
    sides = {"A": _side("A", changed_files=0), "B": _side("B")}
    r = gv.verify(_data(sides=sides))
    assert "changed_A" in _names(r, "warn")
    assert r["overall"] == "warn"


def test_harness_version_mismatch_is_only_a_warning():
    r = gv.verify(_data(image_version="2.2.0"))
    assert "harness_version" in _names(r, "warn")
    assert r["overall"] == "warn"


def test_harness_version_ignores_the_product_name_suffix():
    """题块记的是「2.1.197 (Claude Code)」，镜像只给「2.1.197」，这不是版本对不上。"""
    r = gv.verify(_data(harness_version="2.1.197 (Claude Code)", image_version="2.1.197"))
    assert "harness_version" not in _names(r, "warn")


def test_overall_block_wins_over_warn():
    sides = {"A": _side("A", changed_files=0, session_id=""), "B": _side("B")}
    assert gv.verify(_data(sides=sides))["overall"] == "block"


# ---------------- 写法 ----------------
# 这一组平台都不管，所以只能是黄项。它们对应的是「读起来像不像一个人写的」：
# 篇幅一长颗粒度必然细到真人观察不到，几道题句式雷同就看得出是照骨架填的。

def test_long_reason_is_only_a_warning():
    r = gv.verify(_data(reason=GOOD_REASON * 6))
    assert "reason_too_long" in _names(r, "warn")
    assert r["overall"] == "warn"


@pytest.mark.parametrize("bad", ["真正的分水岭在测试上", "B 的实现差一口气",
                                 "装不上就手搓了一套", "把内部记账固化成了对外契约"])
def test_figurative_and_colloquial_wording_is_flagged(bad):
    assert "reason_wording" in _names(gv.verify(_data(reason=GOOD_REASON + bad)), "warn")


@pytest.mark.parametrize("bad", ["A 的毛病在收尾", "A 的做法很克制", "B 的设计更讲究",
                                 "改完也没再复跑一遍", "断言的是实际运行输出",
                                 "两种情况分别建模", "B 比 A 更贴规范"])
def test_stiff_official_wording_is_flagged(bad):
    """往公文那头偏也要拦。单个词不算错，通篇摞起来就不像一个人在说话。"""
    assert "reason_wording" in _names(gv.verify(_data(reason=GOOD_REASON + bad)), "warn")


@pytest.mark.parametrize("bad", [
    "这道题的胜负就在日期解析上",
    "真正拉开差距的是测试怎么写",
    "字素切分的来源也拉开了差距",
    "这一处就能分出高下",
    "真正分开高下的是捕获语义",
    "两边的改法也分不出高下",
    "决定这次高下的是 B 动了一条注释",
])
def test_contest_framing_is_flagged(bad):
    """把两份产物说成在比赛，和「判 A 更好」是一路货。

    这几个词是写作规范自己带出来的：早先正文反复写「决定胜负的点」，模型原样搬进
    理由，一百多道里有二十几道开头都是「这道题的胜负就在……」。子串表拦不住它，
    写死「分出高下」它就写「分开高下」「分不出高下」，所以这条用正则。
    """
    assert "reason_contest_framing" in _names(gv.verify(_data(reason=GOOD_REASON + bad)), "warn")


@pytest.mark.parametrize("ok", ["选定胜出策略会把方案置空",
                                "按胜出、被覆盖、已过期、无效四种状态排序"])
def test_domain_uses_of_winning_are_not_flagged(ok):
    """业务里的「胜出策略」说的是另一回事，别一起拦掉。"""
    assert "reason_contest_framing" not in _names(gv.verify(_data(reason=GOOD_REASON + ok)), "warn")


def test_colloquial_idiom_in_the_opening_is_flagged():
    assert "reason_wording" in _names(
        gv.verify(_data(reason=GOOD_REASON + "最容易看走眼的是引用逃逸那一条")), "warn")


def test_writing_rules_do_not_seed_the_contest_words():
    """规范正文自己不能出现这些词，否则模型照抄，拦了也白拦。"""
    for word in ("胜负", "拉开差距", "看走眼"):
        assert word not in gv.gsb_rules.WRITING_RULES


def test_a_longer_phrase_that_merely_contains_a_banned_word_is_not_flagged():
    """「反复跑探针」是正常说法，不能因为里面有「复跑」就拦，否则下一轮会被改坏。"""
    ok = "它反复跑只有导入、不核对结果的探针"
    assert "reason_wording" not in _names(gv.verify(_data(reason=GOOD_REASON + ok)), "warn")
    bad = ok + "，改完作用域遍历也没再复跑"
    assert "reason_wording" in _names(gv.verify(_data(reason=GOOD_REASON + bad)), "warn")


@pytest.mark.parametrize("bad", ["所以判 A 更好", "判 B 更好", "这样看判 Same",
                                 "综合下来判定 B 更好", "这一局判给 A"])
def test_refereeing_verdict_sentence_is_flagged(bad):
    """「判 X 更好」是裁判在宣判，人给意见只会说「所以 A 更好」。"""
    assert "reason_verdict_tone" in _names(gv.verify(_data(reason=GOOD_REASON + bad)), "warn")


@pytest.mark.parametrize("ok", ["两侧对根因的判断一致", "A 把未知描述符判成整条规则无效",
                                "所以 A 更好", "这么看下来 B 更好"])
def test_normal_uses_of_the_word_are_not_flagged(ok):
    """「判断」「判成」是正常用词，别把它们一起拦掉。"""
    assert "reason_verdict_tone" not in _names(gv.verify(_data(reason=GOOD_REASON + ok)), "warn")


def test_repeated_opening_across_tasks_is_flagged():
    """同一个开场套在几道题上，单看哪道题都正常，摆在一起才露馅。"""
    reason = "这道题我比较在意两点。" + GOOD_REASON
    peers = {"87": gv.gsb_rules.opening_signature("这道题我比较在意两点。别的题这么起的头")}
    r = gv.verify(_data(reason=reason, peer_openings=peers))
    assert "reason_opening_repeat" in _names(r, "warn")


def test_distinct_openings_are_not_flagged():
    """「两侧都……」这类自然开头不该被当成套模板。"""
    peers = {"87": gv.gsb_rules.opening_signature("两侧都把校验挪进了构建器")}
    r = gv.verify(_data(reason="两侧对根因的判断一致。" + GOOD_REASON, peer_openings=peers))
    assert _names(r, "warn") == set()
