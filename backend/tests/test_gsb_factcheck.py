"""事实核验：可疑断言的本地摘取、结论采信、自动订正、提交门禁。

模型调用全部打桩。这里守的是三件事，每一件都是真出过问题的：
- 只有「断言」和「执行记录」确实对冲时才摘，否则会去改一句本来正确的话；
- 订正稿要过同一把尺子，改坏的宁可不用；
- 订正过什么必须留痕，只换一段正文等于一次不可追溯的覆盖。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app import models as m
from app.services import gsb_factcheck as fc
from app.services import gsb_precheck as gp
from app.services.llm import LlmError, LlmResult

# 共用的一段理由。够长，不会先撞上字数下限；里面那句「没有再跑过测试」是这一节的靶子。
CLAIMED = (
    "A 侧把超限判定放在解析入口，越界时返回的错误里带着是步数超了还是深度超了，"
    "题目要求的正是这个，改完之后也重新跑了一轮用例。B 侧只回了一句解析失败，"
    "调用方拿不到可以分辨的信息，要再读一遍源码才知道是哪一种越界。"
    "更要紧的是 B 侧最后一次改完代码之后没有再跑过测试，交出去的这一版是什么状态它自己也不知道。"
    "两边对问题的定位是一致的，差别集中在错误载荷和收尾这两件事上。"
    "此外 A 侧补了针对两种越界的用例，B 侧没有，同样的输入在 B 上只能看到一句笼统的失败。"
    "综合看 A 更贴题目要求。"
)

FIXED = CLAIMED.replace(
    "更要紧的是 B 侧最后一次改完代码之后没有再跑过测试，交出去的这一版是什么状态它自己也不知道。",
    "更要紧的是 B 侧改完之后那一轮用例里仍有失败项，它没有回头处理就结束了。")


def _facts(*, ok_check=True, after_edit=True, failures=(), ending="", steps=40):
    """造一份执行记录。默认是「改完之后跑过校验并且成功」。"""
    return {
        "steps_total": steps,
        "commands_total": 6,
        "last_edit_file": "src/parser.ts",
        "checks": [{"cmd": "npm test", "ok": ok_check, "out": "所有用例通过",
                    "after_last_edit": after_edit}],
        "failures": list(failures),
        "ending": ending,
        "stop_reason": "end_turn",
    }


def _report(*, mismatches=(), rewrite="", summary="对过了"):
    return json.dumps({"verdict": "fix" if mismatches else "ok", "summary": summary,
                       "mismatches": list(mismatches), "rewrite": rewrite},
                      ensure_ascii=False)


@pytest.fixture()
def analyzed_task(tmp_db):
    """一道结论已出、还没做过任何质检的题。"""
    from app.db import session

    with session() as db:
        t = m.Task(task_no="21", prompt_hash="h", user_prompt="做个解析器", status=m.ANALYZED)
        t.gsb = {"verdict": "A", "reason": CLAIMED}
        db.add(t)
        db.flush()
        return t.id


def _task(task_id):
    from app.db import session

    with session() as db:
        return db.get(m.Task, task_id)


def _stub(monkeypatch, *, text="", error=None, facts=None, corpora=None, texts=None):
    """换掉 llm.ask、执行记录和两侧轨迹全文，并记下模型收到的 prompt。

    texts 给了就按轮次依次回，用来模拟「第一轮没改对、第二轮改对了」。
    """
    seen: list[str] = []

    async def ask(prompt, **kw):
        seen.append(prompt)
        if error is not None:
            raise error
        body = texts[min(len(seen), len(texts)) - 1] if texts else text
        return LlmResult(text=body, model="stub-model")

    monkeypatch.setattr(fc.llm, "ask", ask)
    monkeypatch.setattr(fc, "load_facts",
                        lambda task_no: facts if facts is not None
                        else {"A": _facts(), "B": _facts()})
    monkeypatch.setattr(fc, "load_corpora",
                        lambda task_no: corpora if corpora is not None else {"A": "", "B": ""})
    monkeypatch.setattr(fc, "load_process",
                        lambda task_no: {"A": {"steps": ["Edit src/map.ts"], "edited": ["src/map.ts"]},
                                         "B": {"steps": ["Edit src/index.ts"], "edited": ["src/index.ts"]}})
    return seen


# ---------------- 本地摘可疑断言 ----------------

def test_no_run_claim_is_flagged_when_the_trace_shows_a_passing_check():
    """「没再跑过测试」而轨迹里改完之后跑通了 —— 这正是这一步存在的理由。"""
    got = fc.suspects("B 侧最后一次改完代码之后没有再跑过测试。", {"B": _facts()})
    assert len(got) == 1
    assert got[0]["side"] == "B" and "跑过校验命令" in got[0]["why"]


def test_no_run_claim_is_left_alone_when_the_check_came_before_the_last_edit():
    """改之前跑通不算数，那验的是改之前的代码，这句断言站得住。"""
    assert fc.suspects("B 侧最后一次改完代码之后没有再跑过测试。",
                       {"B": _facts(after_edit=False)}) == []


def test_cant_run_claim_is_flagged_when_nothing_actually_failed():
    """「跑不起来」是从 diff 推出来的重灾区：执行记录里一条失败都没有。"""
    got = fc.suspects("B 侧改完之后项目根本跑不起来。", {"B": _facts()})
    assert len(got) == 1 and "没有执行层面的依据" in got[0]["why"]


def test_cant_run_claim_is_left_alone_when_something_really_failed():
    got = fc.suspects("B 侧改完之后项目根本跑不起来。",
                      {"B": _facts(failures=[{"what": "npm run build", "out": "TS2345"}])})
    assert got == []


def test_abrupt_stop_claim_is_flagged_when_the_run_wrapped_up():
    got = fc.suspects("B 侧戛然而止。", {"B": _facts(ending="已" + "完成全部修改。" * 40)})
    assert len(got) == 1 and "完整的收尾总结" in got[0]["why"]


def test_a_claim_about_the_artifact_is_never_flagged():
    """产物判断轨迹反驳不了，摘出来只会让模型去改一句没问题的话。"""
    assert fc.suspects("B 侧漏了保留注释那一条约束。", {"B": _facts()}) == []


def test_side_carries_over_to_pronoun_sentences():
    """代词句本来就不带 A/B，侧别只能从上一句继承，否则整类断言会漏掉。"""
    got = fc.suspects("B 侧只回了一句解析失败。它改完之后也没有再跑过测试。", {"B": _facts()})
    assert [h["side"] for h in got] == ["B"]


def test_a_side_without_any_trace_is_never_flagged():
    """没有轨迹时「没跑过测试」是对的，不该摘。"""
    assert fc.suspects("B 侧没有再跑过测试。", {"B": {"steps_total": 0}}) == []


# ---------------- prompt ----------------

def test_prompt_carries_both_execution_records_and_the_local_suspects(analyzed_task, monkeypatch):
    seen = _stub(monkeypatch, text=_report())
    asyncio.run(fc.run_factcheck(analyzed_task))
    assert "=== A 侧的实际执行记录 ===" in seen[0]
    assert "=== B 侧的实际执行记录 ===" in seen[0]
    assert "本地先摘出来的可疑断言" in seen[0]
    # 产物好坏不归这一步管，必须在 prompt 里写明，否则它会顺手报一堆代码问题；
    # 但好坏挂在哪一侧名下归它管
    assert "对产物好坏的判断本身" in seen[0]
    assert "说 A 的就要对得上 A 的轨迹" in seen[0]
    assert "=== A 侧的过程记录（只属于 A 侧）===" in seen[0]


# ---------------- 采信与订正 ----------------

def test_a_clean_reason_passes_without_touching_the_text(analyzed_task, monkeypatch):
    _stub(monkeypatch, text=_report())
    r = asyncio.run(fc.run_factcheck(analyzed_task))
    t = _task(analyzed_task)
    assert r["passed"] is True and r["applied"] is False
    assert t.factcheck_status == m.FACTCHECK_PASS
    assert t.gsb["reason"] == CLAIMED


def test_a_mismatch_gets_corrected_in_place_and_leaves_a_note(analyzed_task, monkeypatch):
    """这一步的交付是「改好的正文 + 改了哪几处」，不是一份让人自己改的清单。"""
    _stub(monkeypatch, text=_report(
        mismatches=[{"quote": "B 侧最后一次改完代码之后没有再跑过测试",
                     "side": "B", "claim": "断言 B 侧改完之后没跑过测试",
                     "fact": "执行记录里 npm test 在最后一次改代码之后跑过并且成功",
                     "fix": "改成它跑过但留了失败项没处理"}],
        rewrite=FIXED))
    r = asyncio.run(fc.run_factcheck(analyzed_task))
    t = _task(analyzed_task)
    assert r["applied"] is True and t.factcheck_status == m.FACTCHECK_PASS
    assert t.gsb["reason"] == FIXED
    # 留痕三样都在：原文、轨迹里实际是什么、改成了什么
    note = t.factcheck["notes"][0]
    assert "没有再跑过测试" in note and "npm test" in note and "已改为" in note
    # 改前那一稿留着，自动改写不能是一次不可追溯的覆盖
    assert t.factcheck["reason_before"] == CLAIMED


def test_a_rewrite_that_breaks_the_rules_is_refused_and_the_model_gets_told_why(
        analyzed_task, monkeypatch):
    """改坏的稿子宁可不用。丢掉的原因要带进下一轮，否则它会原样再交一遍。"""
    seen = _stub(monkeypatch, text=_report(
        mismatches=[{"quote": "B 侧最后一次改完代码之后没有再跑过测试",
                     "side": "B", "fact": "跑过", "fix": "改掉"}],
        rewrite="B 侧跑过测试。"))          # 删过头，够不上字数下限
    r = asyncio.run(fc.run_factcheck(analyzed_task))
    t = _task(analyzed_task)
    assert r["passed"] is False and t.factcheck_status == m.FACTCHECK_FAIL
    assert t.gsb["reason"] == CLAIMED       # 正文一个字没动
    assert len(seen) == fc.FIX_ROUNDS and "上一版改写稿没被采用" in seen[1]
    # 自动订正没成功也要把话说清楚，人照着改比自己核对轨迹快得多
    assert "轨迹里实际是" in t.factcheck["notes"][0]


def test_a_quote_that_is_not_in_the_reason_is_dropped(analyzed_task, monkeypatch):
    """模型偶尔把自己改写后的句子填进 quote，那种条目人按它回正文里找不到位置。"""
    _stub(monkeypatch, text=_report(
        mismatches=[{"quote": "这句话正文里根本没有", "side": "B", "fact": "x", "fix": "y"}]))
    r = asyncio.run(fc.run_factcheck(analyzed_task))
    assert r["passed"] is True
    assert _task(analyzed_task).factcheck["quote_dropped"] == 1


def test_a_task_without_any_trace_is_an_error_not_a_pass(analyzed_task, monkeypatch):
    """PASS 的意思是「对过了，没问题」。压根没得对时拿它当通过，题会一路走到提交。"""
    _stub(monkeypatch, text=_report(), facts={"A": {}, "B": {}})
    r = asyncio.run(fc.run_factcheck(analyzed_task))
    t = _task(analyzed_task)
    assert r["ok"] is False and t.factcheck_status == m.FACTCHECK_ERROR
    # 不算「等模型恢复」：轨迹缺了多少次重跑还是缺，看门狗放回流程只会让它每轮空转
    assert not t.factcheck.get("llm_error")


def test_a_failed_model_call_is_an_error_and_is_marked_as_one(analyzed_task, monkeypatch):
    """打上标记，看门狗才知道这道题只是在等模型，账单一通就该自己回来。"""
    _stub(monkeypatch, error=LlmError("账号有未付账单", retryable=False))
    r = asyncio.run(fc.run_factcheck(analyzed_task))
    t = _task(analyzed_task)
    assert r["ok"] is False and t.factcheck_status == m.FACTCHECK_ERROR
    assert "未付账单" in t.factcheck["error"] and t.factcheck["llm_error"] is True


# ---------------- 侧别对应 ----------------
# 7130 被打回的那一句：removeNode 只在 B 的轨迹里，正文却记到了 A 头上。这个词在
# 两侧并集里查得到，按并集查永远是通过——这一节守的就是「按侧查」。

CROSS_SENT = "size 应依据 setNode 和 removeNode 返回的插入删除结果更新，A 的实现正是这样处理的。"
CROSSED = CLAIMED.replace("综合看 A 更贴题目要求。", CROSS_SENT + "综合看 A 更贴题目要求。")
UNCROSSED = CROSSED.replace(CROSS_SENT,
                            "size 应依据 setNode 和 deleteNode 返回的插入删除结果更新，A 的实现正是这样处理的。")
CORPORA = {"A": '{"input": "function setNode() {}\\nfunction deleteNode() {}"}',
           "B": '{"input": "function setNode() {}\\nfunction removeNode() {}"}'}


def _crossed_task():
    from app.db import session

    with session() as db:
        t = m.Task(task_no="7130", prompt_hash="h7130", user_prompt="p", status=m.ANALYZED)
        t.gsb = {"verdict": "A", "reason": CROSSED}
        db.add(t)
        db.flush()
        return t.id


def test_the_model_saying_ok_does_not_let_a_cross_side_claim_through(tmp_db, monkeypatch):
    """程序按侧查出来的硬项，模型说没问题也照样算不符。"""
    tid = _crossed_task()
    seen = _stub(monkeypatch, text=_report(), corpora=CORPORA)
    r = asyncio.run(fc.run_factcheck(tid))
    t = _task(tid)
    assert r["passed"] is False and t.factcheck_status == m.FACTCHECK_FAIL
    assert t.gsb["reason"] == CROSSED
    item = t.factcheck["mismatches"][0]
    assert item["side"] == "A" and item["type"] == "侧别" and "removeNode" in item["fact"]
    assert "侧别对不上" in t.factcheck["notes"][0]
    # 两轮都把这一处点名给了模型，第二轮还把「为什么上一版不行」带上了
    assert "程序按侧逐字查出来的不符" in seen[0] and "removeNode：出现在 B 侧" in seen[0]
    assert "removeNode" in seen[1] and "上一版改写稿没被采用" in seen[1]
    assert "与轨迹不符" in fc.factcheck_block(t)


def test_swapping_in_the_sides_own_name_is_accepted(tmp_db, monkeypatch):
    """订正张冠李戴就是把名字换成那一侧自己的。deleteNode 原文里没有，但 A 的轨迹里有。"""
    tid = _crossed_task()
    _stub(monkeypatch, corpora=CORPORA, text=_report(
        mismatches=[{"quote": CROSS_SENT, "side": "A", "type": "侧别",
                     "fact": "A 的轨迹里叫 deleteNode", "fix": "换成 deleteNode"}],
        rewrite=UNCROSSED))
    r = asyncio.run(fc.run_factcheck(tid))
    t = _task(tid)
    assert r["applied"] is True and t.factcheck_status == m.FACTCHECK_PASS
    assert t.gsb["reason"] == UNCROSSED
    assert t.factcheck["attribution_version"] == fc.ATTRIBUTION_VERSION


def test_a_rewrite_that_still_crosses_sides_is_refused(tmp_db, monkeypatch):
    tid = _crossed_task()
    still = CROSSED.replace("结果更新", "结果来更新")
    seen = _stub(monkeypatch, corpora=CORPORA, texts=[
        _report(mismatches=[{"quote": CROSS_SENT, "side": "A", "fact": "x", "fix": "y"}],
                rewrite=still),
        _report(mismatches=[{"quote": CROSS_SENT, "side": "A", "fact": "x", "fix": "y"}],
                rewrite=UNCROSSED)])
    r = asyncio.run(fc.run_factcheck(tid))
    assert "仍有侧别对不上轨迹" in seen[1]
    assert r["applied"] is True and _task(tid).gsb["reason"] == UNCROSSED


def test_a_name_found_in_neither_trace_is_still_refused_in_a_rewrite(tmp_db, monkeypatch):
    tid = _crossed_task()
    made_up = CROSSED.replace("removeNode", "dropEntry")
    _stub(monkeypatch, corpora=CORPORA, text=_report(
        mismatches=[{"quote": CROSS_SENT, "side": "A", "fact": "x", "fix": "y"}],
        rewrite=made_up))
    r = asyncio.run(fc.run_factcheck(tid))
    assert r["passed"] is False
    assert "两侧轨迹里都查不到" in _task(tid).factcheck["rewrite_dropped"]


def test_an_old_pass_that_never_checked_sides_no_longer_counts(analyzed_task):
    """旧口径的 PASS 只对过执行结果，张冠李戴照样拿 PASS，不能再当放行用。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.factcheck_status = m.FACTCHECK_PASS
        t.factcheck = {"reason_digest": gp.reason_digest(CLAIMED)}
        assert fc.outdated(t) and not fc.settled(t)
        assert "旧口径" in fc.factcheck_block(t)
    assert fc.skip_reason(_task(analyzed_task)) == ""


def test_a_wording_rewrite_that_crosses_sides_is_not_carried_forward(tmp_db, monkeypatch):
    tid = _crossed_task()
    monkeypatch.setattr(fc, "load_facts", lambda task_no: {"A": _facts(), "B": _facts()})
    monkeypatch.setattr(fc, "load_corpora", lambda task_no: CORPORA)
    from app.db import session

    good = FIXED.replace("综合看", UNCROSSED.split("综合看")[0].rsplit("。", 2)[-2] + "。综合看")
    bad = FIXED.replace("综合看", CROSS_SENT + "综合看")
    with session() as db:
        t = db.get(m.Task, tid)
        t.factcheck_status = m.FACTCHECK_PASS
        t.factcheck = {"reason_digest": gp.reason_digest(good),
                       "attribution_version": fc.ATTRIBUTION_VERSION}
        assert fc.reseal(t, good) is True
        assert fc.reseal(t, bad) is False


# ---------------- 阶段与门禁 ----------------

def test_passing_both_checks_moves_the_task_on_to_recording(analyzed_task, monkeypatch):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(CLAIMED)}
    _stub(monkeypatch, text=_report())
    asyncio.run(fc.run_factcheck(analyzed_task))
    assert _task(analyzed_task).status == m.QC


def test_a_correction_resets_the_wording_check(analyzed_task, monkeypatch):
    """订正换掉了正文，上一轮的「措辞通过」评的是改之前那一段话。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(CLAIMED)}
    _stub(monkeypatch, text=_report(
        mismatches=[{"quote": "B 侧最后一次改完代码之后没有再跑过测试",
                     "side": "B", "fact": "跑过", "fix": "改掉"}],
        rewrite=FIXED))
    asyncio.run(fc.run_factcheck(analyzed_task))
    t = _task(analyzed_task)
    assert t.precheck_status == m.PRECHECK_IDLE and t.status == m.ANALYZED


def test_the_submit_gate_names_the_factcheck_before_the_wording_check(analyzed_task):
    """两道的失败含义不同，门禁得说清卡在哪一道，人才知道该核轨迹还是改句子。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.status = m.QC
        t.screencast = {"A": "u", "B": "u"}
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(CLAIMED)}
        t.factcheck_status = m.FACTCHECK_FAIL
        t.factcheck = {"mismatches": [{"quote": "x"}, {"quote": "y"}],
                       "reason_digest": gp.reason_digest(CLAIMED)}
        assert "事实核验发现 2 处" in gp.submit_block(t)


def test_a_blank_factcheck_status_counts_as_unchecked(analyzed_task):
    """ALTER TABLE 补出来的列是空串。黑名单会让整批老题一升级就成了「核验通过」。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.status = m.QC
        t.screencast = {"A": "u", "B": "u"}
        t.factcheck_status = ""
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(CLAIMED)}
        assert "还没做事实核验" in gp.submit_block(t)


def test_the_gate_asks_for_the_recording_once_both_checks_are_clear(analyzed_task):
    """录屏不再决定题在哪一栏，但它仍是提交的必填项，这句话得在人按按钮之前说。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.status = m.QC
        digest = gp.reason_digest(CLAIMED)
        t.factcheck_status = m.FACTCHECK_PASS
        t.factcheck = {"reason_digest": digest, "attribution_version": fc.ATTRIBUTION_VERSION}
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": digest}
        t.screencast = {"A": "u", "B": ""}
        assert "还缺 B 侧的录屏" in gp.submit_block(t)


# ---------------- 结论过继 ----------------

def test_a_wording_rewrite_carries_the_factcheck_verdict_forward(analyzed_task, monkeypatch):
    """不过继的话每道题都要核两遍，而第二遍核的是一段只换了说法的话。"""
    monkeypatch.setattr(fc, "load_facts", lambda task_no: {"A": _facts(), "B": _facts()})
    monkeypatch.setattr(fc, "load_corpora", lambda task_no: {"A": "", "B": ""})
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.factcheck_status = m.FACTCHECK_PASS
        t.factcheck = {"reason_digest": gp.reason_digest(CLAIMED),
                       "attribution_version": fc.ATTRIBUTION_VERSION}
        # 换正文和过继指纹在同一个事务里，顺序和 gsb_precheck._save 一致
        t.gsb = {**t.gsb, "reason": FIXED}
        assert fc.reseal(t, FIXED) is True
        assert not fc.stale(t)


def test_a_rewrite_that_reintroduces_a_contradiction_is_not_carried_forward(
        analyzed_task, monkeypatch):
    """过继不是无条件放行：本地那把尺子在新文本上再量一遍，量得出就让它过期。"""
    monkeypatch.setattr(fc, "load_facts", lambda task_no: {"A": _facts(), "B": _facts()})
    broken = CLAIMED.replace("交出去的这一版是什么状态它自己也不知道。",
                             "B 侧改完之后根本跑不起来。")
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.factcheck_status = m.FACTCHECK_PASS
        t.factcheck = {"reason_digest": gp.reason_digest(CLAIMED)}
        assert fc.reseal(t, broken) is False


def test_an_unsettled_factcheck_is_never_carried_forward(analyzed_task, monkeypatch):
    monkeypatch.setattr(fc, "load_facts", lambda task_no: {"A": _facts(), "B": _facts()})
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.factcheck_status = m.FACTCHECK_FAIL
        assert fc.reseal(t, FIXED) is False


# ---------------- 挑题 ----------------

def test_skip_reason_lets_an_unchecked_task_through(analyzed_task):
    assert fc.skip_reason(_task(analyzed_task)) == ""


def test_skip_reason_turns_down_a_fresh_pass(analyzed_task):
    """同一段没动过的话再核一遍，答案一样，那次调用是白花的。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.factcheck_status = m.FACTCHECK_PASS
        t.factcheck = {"reason_digest": gp.reason_digest(CLAIMED),
                       "attribution_version": fc.ATTRIBUTION_VERSION}
    assert "没再改过" in fc.skip_reason(_task(analyzed_task))


def test_skip_reason_lets_a_stale_pass_back_in(analyzed_task):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.factcheck_status = m.FACTCHECK_PASS
        t.factcheck = {"reason_digest": gp.reason_digest(CLAIMED)}
        t.gsb = {**t.gsb, "reason": CLAIMED + "补一句。"}
    assert fc.skip_reason(_task(analyzed_task)) == ""


def test_skip_reason_always_lets_an_error_retry(analyzed_task):
    """ERROR 是核验自己没跑成（账单被拒、模型超时），重跑正是该做的事。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, analyzed_task)
        t.factcheck_status = m.FACTCHECK_ERROR
        t.factcheck = {"error": "账号有未付账单", "reason_digest": gp.reason_digest(CLAIMED)}
    assert fc.skip_reason(_task(analyzed_task)) == ""


# ---------------- 人工确认 ----------------

def test_confirm_clears_the_factcheck_gate(analyzed_task, monkeypatch):
    """模型报的出入里总有它自己读偏的，人对着轨迹看一眼直接放行是正常操作。"""
    _stub(monkeypatch, text=_report(
        mismatches=[{"quote": "B 侧最后一次改完代码之后没有再跑过测试",
                     "side": "B", "fact": "跑过", "fix": "改掉"}],
        rewrite="太短了。"))
    asyncio.run(fc.run_factcheck(analyzed_task))
    assert fc.confirm(analyzed_task, note="第一处是它读偏了")["ok"] is True
    t = _task(analyzed_task)
    assert t.factcheck_status == m.FACTCHECK_CONFIRMED and fc.settled(t)


def test_confirm_refuses_a_task_that_was_never_checked(analyzed_task):
    assert fc.confirm(analyzed_task)["ok"] is False


# ---------------- 重新分析要把两道都清掉 ----------------

def test_reanalysis_drops_both_check_verdicts(tmp_db, monkeypatch):
    """重新分析会整段换掉理由，两道结论评的都是那段已经不存在的话。

    事实核验那一档尤其不能留：它对的是上一稿理由，而理由马上要被整段换掉，
    留着就是让一道重新分析过的题带着旧的「与轨迹一致」直接可提交。
    """
    import time

    from app.db import session
    from app.services import gsb_analyzer

    with session() as db:
        t = m.Task(task_no="40", prompt_hash="h", user_prompt="p", status=m.QC)
        t.gsb = {"verdict": "A", "reason": CLAIMED}
        t.factcheck_status = m.FACTCHECK_PASS
        t.factcheck = {"reason_digest": gp.reason_digest(CLAIMED)}
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(CLAIMED)}
        db.add(t)
        db.flush()
        tid = t.id
        for side in ("A", "B"):
            db.add(m.TaskRun(task_id=tid, side=side, status=m.RUN_FINISHED))
        db.flush()

    # 分析在拿到材料之前就该把两档清掉，所以让它停在采集那一步再看库里的样子
    async def boom(*a, **kw):
        raise RuntimeError("停在这里就够了")

    monkeypatch.setattr(gsb_analyzer, "collect_side", boom)
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    asyncio.run(gsb_analyzer.analyze_task(tid))

    t = _task(tid)
    assert t.factcheck_status == m.FACTCHECK_IDLE and t.factcheck == {}
    assert t.precheck_status == m.PRECHECK_IDLE and t.precheck == {}
