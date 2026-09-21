"""提交前质检：规则摘录、结论采信、提交门禁、阶段投影。

模型调用全部打桩。这里要守住的是「不听模型自报的结论、不信它给不出原文的条目、
不采信会把理由改坏的稿子」—— 三件事都发生过，而一旦放过去，后果是人在界面上拿到一份
对不上原文的问题清单，或者一段被悄悄压短的理由。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app import models as m
from app.services import gsb_precheck as gp
from app.services.llm import LlmError, LlmResult

# 各条测试共用的一段「像人写的」理由。够长，不会先撞上字数下限
GOOD = ("A 侧把超限判定放在解析入口，越界时返回的错误里带着是步数超了还是深度超了，"
        "题目要求的正是这个。B 侧只回了一句解析失败，调用方拿不到可以分辨的信息，"
        "要再读一遍源码才知道是哪一种越界。两边对问题的定位一致，差别在错误载荷上。"
        "此外 A 侧补了针对两种越界的用例，B 侧没有。综合看 A 更贴题目要求。")


def _report(passed=True, issues=(), rewrite="", summary="读起来自然"):
    return json.dumps({"verdict": "pass" if passed else "revise", "summary": summary,
                       "issues": list(issues), "rewrite": rewrite}, ensure_ascii=False)


@pytest.fixture()
def qc_task(tmp_db):
    """一道录屏已齐、停在质检这一步的题。"""
    from app.db import session

    with session() as db:
        t = m.Task(task_no="07", prompt_hash="h", user_prompt="做个解析器", status=m.QC,
                   repo_url="https://github.com/acme/widget")
        t.gsb = {"verdict": "A", "reason": GOOD}
        t.screencast = {"A": "https://v.example/a", "B": "https://v.example/b"}
        db.add(t)
        db.flush()
        return t.id


def _task(task_id):
    from app.db import session

    with session() as db:
        return db.get(m.Task, task_id)


def _stub(monkeypatch, *, text="", error=None):
    """把 llm.ask 换掉，并记下它收到的 prompt。"""
    seen: list[str] = []

    async def ask(prompt, **kw):
        seen.append(prompt)
        if error is not None:
            raise error
        return LlmResult(text=text, model="stub-model")

    monkeypatch.setattr(gp.llm, "ask", ask)
    return seen


# ---------------- 本地摘录 ----------------

def test_hints_pick_up_action_verbs():
    got = gp.hints("根因两边翻到的是同一处。")
    assert got and got[0]["word"] == "翻到" and got[0]["kind"] == "动作化动词"


def test_hints_pick_up_anthropomorphic_praise():
    kinds = {h["kind"] for h in gp.hints("B 有一处确实比 A 想得远。")}
    assert "拟人化评价" in kinds and "含糊限定" in kinds


def test_hints_leave_normal_sentences_alone():
    """词表只收明显的。正常句子被摘一大片的话，摘出来的提示模型就不当真了。"""
    assert gp.hints("两边对问题的定位是一致的，B 在接口设计上比 A 更合理。") == []


def test_prompt_carries_local_hints(qc_task, monkeypatch):
    """本地摘出来的句子要进 prompt：一段几百字里这类词只有两三处，不点出来容易被整体读过去。"""
    prompt = gp.build_prompt("根因两边翻到的是同一处。", verdict="A", task_no="07")
    assert "翻到" in prompt and "本地先摘出来的疑似处" in prompt
    # 判断基准必须在规则前面，少了它模型会往「加口语」的方向改
    assert prompt.index("判断基准") < prompt.index("逐条规则")


# ---------------- 结论采信 ----------------

def test_normalize_drops_issues_without_a_real_quote():
    """quote 对不上原文的条目整条丢掉：人拿着它在正文里找不到，不知道该改哪一句。"""
    out = gp.normalize({"issues": [
        {"quote": "这句话正文里没有", "kind": "句子生硬", "why": "x", "suggest": "y"},
        {"quote": "两边对问题的定位一致", "kind": "句子生硬", "why": "x", "suggest": "y"},
    ]}, reason=GOOD)
    assert len(out["issues"]) == 1 and out["quote_dropped"] == 1


def test_normalize_matches_quote_ignoring_whitespace():
    reason = "A 侧写清了越界类型。\n  B 侧没有。"
    out = gp.normalize({"issues": [{"quote": "A 侧写清了越界类型。 B 侧没有。", "kind": "句子生硬"}]},
                       reason=reason)
    assert len(out["issues"]) == 1


def test_normalize_ignores_self_reported_pass_when_issues_listed():
    """模型常常一边列出三条问题一边说 pass。结论按 issues 定，不按它自报的那个字段定。"""
    out = gp.normalize({"verdict": "pass", "issues": [
        {"quote": "两边对问题的定位一致", "kind": "句子生硬"}]}, reason=GOOD)
    assert out["passed"] is False


def test_normalize_ignores_self_reported_revise_without_issues():
    """反过来也有：说 revise 却一条都举不出来，那是没话说硬凑个结论。"""
    assert gp.normalize({"verdict": "revise", "issues": []}, reason=GOOD)["passed"] is True


def test_normalize_caps_issue_count():
    raw = [{"quote": "两边对问题的定位一致", "kind": "句子生硬"} for _ in range(30)]
    assert len(gp.normalize({"issues": raw}, reason=GOOD)["issues"]) == gp.MAX_ISSUES


def test_normalize_folds_unknown_kind():
    """让模型自己起名字的话，同一种毛病会在不同题上叫出七八个名字，界面没法归类。"""
    out = gp.normalize({"issues": [
        {"quote": "两边对问题的定位一致", "kind": "读起来怪怪的"}]}, reason=GOOD)
    assert out["issues"][0]["kind"] == gp.OTHER_KIND


def test_normalize_strips_markdown_from_suggestion():
    """suggest 会被人抄进理由，所以和分析产出走同一套清洗。"""
    out = gp.normalize({"issues": [
        {"quote": "两边对问题的定位一致", "kind": "句子生硬", "suggest": "**两边定位一致**"}]},
        reason=GOOD)
    assert "**" not in out["issues"][0]["suggest"]


def test_normalize_keeps_no_rewrite_when_passed():
    out = gp.normalize({"issues": [], "rewrite": "整段重写"}, reason=GOOD)
    assert out["rewrite"] == ""


# ---------------- 整段改写稿的两道关 ----------------

def test_vet_rewrite_keeps_a_sound_draft():
    text, why = gp._vet_rewrite(GOOD + "补一句，两边的定位是一致的。", GOOD, "A")
    assert text and not why


def test_vet_rewrite_drops_a_draft_that_cut_too_deep():
    """压短是这一步要做的事，压到没有论点不是。按绝对下限判，不按占原文几成判。"""
    text, why = gp._vet_rewrite("A 更好。", GOOD, "A")
    assert text == "" and "删过头" in why


def test_vet_rewrite_keeps_a_draft_that_halves_the_length():
    """篇幅目标收到三四百之后，把一段长理由压掉一半正是合格的改法，不能再当缩水拦下。"""
    half = ("A 侧把超限判定放在解析入口，越界时返回的错误里带着是步数超了还是深度超了。"
            "B 侧只回了一句解析失败，调用方拿不到可以分辨的信息。所以 A 更好。")
    assert gp.gsb_rules.visible_chars(half) < gp.gsb_rules.visible_chars(GOOD) * 0.6
    text, why = gp._vet_rewrite(half, GOOD, "A")
    assert text and not why


def test_vet_rewrite_drops_a_draft_that_is_still_too_long():
    """只换说法不压篇幅的稿子换上去没有意义，问题只是挪了个位置。"""
    long_draft = GOOD * 4
    assert gp.gsb_rules.visible_chars(long_draft) > gp.gsb_rules.REASON_SOFT_MAX_CHARS
    text, why = gp._vet_rewrite(long_draft, GOOD, "A")
    assert text == "" and "上限" in why


def test_vet_rewrite_drops_a_draft_that_adds_a_block():
    """改写时带进对话腔这类核验红项，套进去之后核验才报红，比没有这份稿子更费事。"""
    text, why = gp._vet_rewrite(GOOD + "以上是我的分析。", GOOD, "A")
    assert text == "" and "红项" in why


def test_vet_rewrite_cleans_instead_of_dropping_what_it_can_strip():
    """步号、markdown 这些清洗剥得掉，剥完就是一份干净稿子，不必连着整份丢掉。"""
    text, why = gp._vet_rewrite(GOOD.replace("A 侧把", "在第 12 步里 A 侧把"), GOOD, "A")
    assert text and not why and "第 12 步" not in text


# ---------------- 指纹与过期 ----------------

def test_digest_ignores_whitespace_only_edits():
    assert gp.reason_digest("两边定位一致。\n B 没处理。") == gp.reason_digest("两边定位一致。B 没处理。")


def test_stale_is_true_after_reason_edited(qc_task):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, qc_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(GOOD)}
        t.gsb = {**t.gsb, "reason": GOOD + "又补了一句。"}
        assert gp.stale(t) is True


def test_stale_is_false_when_reason_untouched(qc_task):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, qc_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(GOOD)}
        assert gp.stale(t) is False


def test_stale_is_false_before_any_pass(qc_task):
    """没质检过就没有指纹，谈不上过期，那一档要说的是「还没质检」。"""
    assert gp.stale(_task(qc_task)) is False


def test_stale_also_covers_a_fail_whose_reason_got_fixed(qc_task):
    """判了待改的题被人改完理由，那一稿同样没问过模型。

    stale 不分质检走到哪一档，因为「该不该再跑一次」要的就是不分档的口径；
    提交门禁那边先判过 PRECHECK_OK 才问到这里，不受影响。
    """
    from app.db import session

    with session() as db:
        t = db.get(m.Task, qc_task)
        t.precheck_status = m.PRECHECK_FAIL
        t.precheck = {"passed": False, "reason_digest": gp.reason_digest(GOOD)}
        t.gsb = {**t.gsb, "reason": GOOD + "改了一句。"}
        assert gp.stale(t) is True
        # 门禁那句话还是「改掉并确认」，没被这一改带偏
        assert "确认" in gp.submit_block(t)


# ---------------- 阶段投影 ----------------

def test_screencast_complete_moves_task_into_qc(tmp_db):
    from app.db import session

    with session() as db:
        t = m.Task(task_no="08", prompt_hash="h", user_prompt="x", status=m.ANALYZED)
        t.screencast = {"A": "u", "B": "u"}
        db.add(t)
        db.flush()
        assert gp.sync_stage(db, t) is True and t.status == m.QC


def test_missing_screencast_sends_task_back_and_clears_verdict(tmp_db):
    """录屏被换掉通常是重录了一份。留着上一轮的「通过」会让它重录完直接可提交。"""
    from app.db import session

    with session() as db:
        t = m.Task(task_no="08", prompt_hash="h", user_prompt="x", status=m.QC)
        t.screencast = {"A": "u", "B": ""}
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True}
        db.add(t)
        db.flush()
        assert gp.sync_stage(db, t) is True
        assert t.status == m.ANALYZED
        assert t.precheck_status == m.PRECHECK_IDLE and t.precheck == {}


def test_sync_stage_leaves_uploaded_tasks_alone(tmp_db):
    from app.db import session

    with session() as db:
        t = m.Task(task_no="08", prompt_hash="h", user_prompt="x", status=m.UPLOADED)
        db.add(t)
        db.flush()
        assert gp.sync_stage(db, t) is False and t.status == m.UPLOADED


# ---------------- 提交门禁 ----------------

def test_block_before_screencast_explains_the_next_step(tmp_db):
    from app.db import session

    with session() as db:
        t = m.Task(task_no="08", prompt_hash="h", user_prompt="x", status=m.ANALYZED)
        db.add(t)
        db.flush()
        assert "录屏" in gp.submit_block(t)


def test_block_when_precheck_never_ran(qc_task):
    assert "还没做提交前质检" in gp.submit_block(_task(qc_task))


def test_block_treats_an_unmigrated_blank_status_as_unchecked(qc_task):
    """ALTER TABLE 补出来的列是空串。门禁按白名单判，空串必须落在「没质检过」那一档 ——
    否则库里所有老题一升级就全成了「质检通过」。"""
    from app.db import session

    with session() as db:
        db.get(m.Task, qc_task).precheck_status = ""
    t = _task(qc_task)
    assert gp.submittable(t) is False and "还没做" in gp.submit_block(t)


def test_sync_all_fills_blank_status_and_regroups(tmp_db):
    """开机对账：空档补成 IDLE，录屏齐了的老题从待录屏挪进质检。"""
    from app.db import session

    with session() as db:
        old = m.Task(task_no="11", prompt_hash="h", user_prompt="x", status=m.ANALYZED)
        old.screencast = {"A": "u", "B": "u"}
        old.precheck_status = ""
        db.add(old)
        db.flush()
        tid = old.id
    assert gp.sync_all() == 1
    t = _task(tid)
    assert t.status == m.QC and t.precheck_status == m.PRECHECK_IDLE


def test_block_counts_issues_when_precheck_failed(qc_task):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, qc_task)
        t.precheck_status = m.PRECHECK_FAIL
        t.precheck = {"passed": False, "issues": [{"quote": "x"}, {"quote": "y"}]}
        assert "2 处" in gp.submit_block(t)


def test_block_separates_precheck_error_from_failure(qc_task):
    """质检自己没跑成该重跑，不该让人跑去改一段没问题的话。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, qc_task)
        t.precheck_status = m.PRECHECK_ERROR
        t.precheck = {"error": "模型超时"}
        msg = gp.submit_block(t)
        assert "没跑完" in msg and "模型超时" in msg


def test_pass_with_fresh_reason_clears_the_gate(qc_task):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, qc_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(GOOD)}
        assert gp.submit_block(t) == "" and gp.submittable(t) is True


def test_pass_goes_stale_when_reason_changes(qc_task):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, qc_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(GOOD)}
        t.gsb = {**t.gsb, "reason": GOOD + "再补一句。"}
        assert "过期" in gp.submit_block(t)


# ---------------- 跑一遍 ----------------

def test_run_precheck_records_a_pass(qc_task, monkeypatch):
    _stub(monkeypatch, text=_report(passed=True))
    r = asyncio.run(gp.run_precheck(qc_task))
    t = _task(qc_task)
    assert r["ok"] is True and r["passed"] is True
    assert t.precheck_status == m.PRECHECK_PASS
    assert t.precheck["reason_digest"] == gp.reason_digest(GOOD)
    assert t.precheck["model"] == "stub-model"


def test_run_precheck_records_issues(qc_task, monkeypatch):
    _stub(monkeypatch, text=_report(
        passed=False, summary="有一处生硬",
        issues=[{"quote": "两边对问题的定位一致", "kind": "句子生硬",
                 "why": "主谓错位", "suggest": "两边对问题的定位是一致的"}]))
    r = asyncio.run(gp.run_precheck(qc_task))
    t = _task(qc_task)
    assert r["passed"] is False and r["issues"] == 1
    assert t.precheck_status == m.PRECHECK_FAIL
    assert t.precheck["issues"][0]["suggest"] == "两边对问题的定位是一致的"


# 一份合格的改写稿：写到了两侧、落在篇幅窗口里、词表和核验都不命中
FIXED = ("A 侧把超限判定放在解析入口，越界时返回的错误里写明是步数超了还是深度超了，"
         "与题目要求一致。B 侧只返回一句解析失败，调用方无法分辨是哪一种越界，"
         "只能回到源码里再读一遍。A 侧另外补了两种越界各自的用例，B 侧没有。"
         "所以 A 更好。")


def test_run_precheck_applies_the_rewrite(qc_task, monkeypatch):
    """质检不再只报问题：改好的稿子直接盖掉理由正文，人不必逐条回正文里替换。"""
    _stub(monkeypatch, text=_report(passed=False, rewrite=FIXED,
                                    issues=[{"quote": "两边对问题的定位一致", "kind": "句子生硬"}]))
    r = asyncio.run(gp.run_precheck(qc_task))
    task = _task(qc_task)
    assert task.gsb["reason"] == FIXED
    assert r["applied"] and r["reason"] == FIXED
    # 改前那一稿要留着，否则自动改写就成了一次不可追溯的覆盖
    assert task.precheck["reason_before"] == GOOD


def test_applying_marks_it_passed_and_not_stale(qc_task, monkeypatch):
    """改写已经落上去，这一稿在规则层面就是干净的，不该再要人确认一次。
    指纹也必须跟着换，否则提交门禁会把刚改好的这一稿判成「质检之后又改过」。"""
    _stub(monkeypatch, text=_report(passed=False, rewrite=FIXED,
                                    issues=[{"quote": "两边对问题的定位一致", "kind": "句子生硬"}]))
    asyncio.run(gp.run_precheck(qc_task))
    task = _task(qc_task)
    assert task.precheck_status == m.PRECHECK_PASS
    assert not gp.stale(task)
    assert gp.submit_block(task) == ""


def test_run_precheck_keeps_the_reason_when_the_rewrite_is_unusable(qc_task, monkeypatch):
    """稿子只要会把理由改坏就整份丢掉，宁可留着待改让人自己动手。"""
    _stub(monkeypatch, text=_report(passed=False, rewrite=FIXED + "以上是我的分析。",
                                    issues=[{"quote": "两边对问题的定位一致", "kind": "句子生硬"}]))
    asyncio.run(gp.run_precheck(qc_task))
    task = _task(qc_task)
    assert task.gsb["reason"] == GOOD
    assert task.precheck_status == m.PRECHECK_FAIL
    assert "红项" in task.precheck["rewrite_dropped"]


def test_run_precheck_can_report_without_applying(qc_task, monkeypatch):
    """apply=False 留给「只想看看有什么问题」的场合，走的是同一次模型调用。"""
    _stub(monkeypatch, text=_report(passed=False, rewrite=FIXED,
                                    issues=[{"quote": "两边对问题的定位一致", "kind": "句子生硬"}]))
    r = asyncio.run(gp.run_precheck(qc_task, apply=False))
    assert _task(qc_task).gsb["reason"] == GOOD
    assert not r["applied"] and r["issues"] == 1


def test_a_reason_that_only_breaks_length_is_not_a_pass(qc_task, monkeypatch):
    """模型对篇幅没有概念，一段超长的理由它逐句读完会回 pass；而篇幅正是这一步要压的。"""
    from app.db import session

    long_reason = GOOD * 4
    assert gp.gsb_rules.visible_chars(long_reason) > gp.gsb_rules.REASON_SOFT_MAX_CHARS
    with session() as db:
        task = db.get(m.Task, qc_task)
        task.gsb = {**task.gsb, "reason": long_reason}
    _stub(monkeypatch, text=_report(passed=True, rewrite=FIXED))
    asyncio.run(gp.run_precheck(qc_task))
    task = _task(qc_task)
    assert task.gsb["reason"] == FIXED
    assert task.precheck_status == m.PRECHECK_PASS


def test_run_precheck_marks_error_when_model_fails(qc_task, monkeypatch):
    _stub(monkeypatch, error=LlmError("模型十分钟没有返回", retryable=True))
    r = asyncio.run(gp.run_precheck(qc_task))
    t = _task(qc_task)
    assert r["ok"] is False
    assert t.precheck_status == m.PRECHECK_ERROR and "十分钟" in t.precheck["error"]
    assert t.gsb["reason"] == GOOD


def test_run_precheck_marks_error_on_unparsable_output(qc_task, monkeypatch):
    _stub(monkeypatch, text="我觉得写得挺好的，没什么要改的。")
    assert asyncio.run(gp.run_precheck(qc_task))["ok"] is False
    assert _task(qc_task).precheck_status == m.PRECHECK_ERROR


def test_run_precheck_refuses_without_a_reason(tmp_db):
    from app.db import session

    with session() as db:
        t = m.Task(task_no="09", prompt_hash="h", user_prompt="x", status=m.QC)
        db.add(t)
        db.flush()
        tid = t.id
    r = asyncio.run(gp.run_precheck(tid))
    assert r["ok"] is False and "GSB 分析" in r["message"]


def test_run_precheck_refuses_on_a_running_task(tmp_db):
    from app.db import session

    with session() as db:
        t = m.Task(task_no="09", prompt_hash="h", user_prompt="x", status=m.RUNNING)
        db.add(t)
        db.flush()
        tid = t.id
    assert asyncio.run(gp.run_precheck(tid))["ok"] is False


def test_run_precheck_promotes_analyzed_task_with_screencast(tmp_db, monkeypatch):
    """录屏早就齐了、状态还挂在待录屏的老题，质检完顺手归位到质检栏。"""
    from app.db import session

    with session() as db:
        t = m.Task(task_no="09", prompt_hash="h", user_prompt="x", status=m.ANALYZED)
        t.gsb = {"verdict": "A", "reason": GOOD}
        t.screencast = {"A": "u", "B": "u"}
        db.add(t)
        db.flush()
        tid = t.id
    _stub(monkeypatch, text=_report(passed=True))
    asyncio.run(gp.run_precheck(tid))
    assert _task(tid).status == m.QC


# ---------------- 人工确认 ----------------

def test_confirm_clears_the_gate_after_a_fix(qc_task, monkeypatch):
    """模型挑出来的十条里总有两三条是它读偏了，人看一眼直接放行是正常操作。"""
    _stub(monkeypatch, text=_report(passed=False,
                                    issues=[{"quote": "两边对问题的定位一致", "kind": "句子生硬"}]))
    asyncio.run(gp.run_precheck(qc_task))
    r = gp.confirm(qc_task, note="第二条是它读偏了")
    t = _task(qc_task)
    assert r["ok"] is True and r["submittable"] is True
    assert t.precheck_status == m.PRECHECK_CONFIRMED
    assert t.precheck["confirmed_from"] == m.PRECHECK_FAIL
    assert t.precheck["confirmed_note"] == "第二条是它读偏了"
    assert gp.submit_block(t) == ""


def test_confirm_takes_the_digest_of_the_edited_reason(qc_task, monkeypatch):
    """确认的是人改完之后那一稿，不是质检当时读到的那一段，否则一确认就立刻「已过期」。"""
    from app.db import session

    _stub(monkeypatch, text=_report(passed=False,
                                    issues=[{"quote": "两边对问题的定位一致", "kind": "句子生硬"}]))
    asyncio.run(gp.run_precheck(qc_task))
    fixed = GOOD.replace("两边对问题的定位一致", "两边对问题的定位是一致的")
    with session() as db:
        t = db.get(m.Task, qc_task)
        t.gsb = {**t.gsb, "reason": fixed}
    gp.confirm(qc_task)
    t = _task(qc_task)
    assert t.precheck["reason_digest"] == gp.reason_digest(fixed)
    assert gp.stale(t) is False


def test_confirm_refuses_when_precheck_never_ran(qc_task):
    """没跑过质检就能确认的话，这道门等于不存在。"""
    r = gp.confirm(qc_task)
    assert r["ok"] is False and "还没做过" in r["message"]


def test_confirm_refuses_while_precheck_is_running(qc_task):
    from app.db import session

    with session() as db:
        db.get(m.Task, qc_task).precheck_status = m.PRECHECK_RUNNING
    assert gp.confirm(qc_task)["ok"] is False


# ---------------- 挑题 ----------------

def test_ready_skips_tasks_without_screencast(tmp_db):
    from app.db import session

    with session() as db:
        t = m.Task(task_no="10", prompt_hash="h", user_prompt="x", status=m.ANALYZED)
        t.gsb = {"verdict": "A", "reason": GOOD}
        db.add(t)
        db.flush()
    assert gp.ready_ids() == []


def test_ready_includes_a_task_waiting_for_precheck(qc_task):
    assert gp.ready_ids() == [qc_task]


def test_ready_skips_a_fresh_pass(qc_task):
    """同一段没动过的话再问一遍，答案一样，那次模型调用是白花的。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, qc_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(GOOD)}
    assert gp.ready_ids() == []


def test_ready_picks_up_a_stale_pass(qc_task):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, qc_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(GOOD)}
        t.gsb = {**t.gsb, "reason": GOOD + "补一句。"}
    assert gp.ready_ids() == [qc_task]


def test_submittable_ids_only_lists_cleared_tasks(qc_task):
    from app.db import session

    assert gp.submittable_ids() == []
    with session() as db:
        t = db.get(m.Task, qc_task)
        t.precheck_status = m.PRECHECK_CONFIRMED
        t.precheck = {"reason_digest": gp.reason_digest(GOOD)}
    assert gp.submittable_ids() == [qc_task]


# ---------------- 批量质检 ----------------
# 页面上一次勾一百多道，一道就是一次模型调用。这一节守的是「发出去之前先剔干净」——
# 漏一道就是白烧一次调用，而人是看不出来的：结果长得和上一次一模一样。

@pytest.fixture()
def screencast_task(tmp_db):
    """一道结论已出、还没录屏的题。质检现在赶在录屏之前跑，这就是那时候的样子。"""
    from app.db import session

    with session() as db:
        t = m.Task(task_no="12", prompt_hash="h", user_prompt="x", status=m.ANALYZED)
        t.gsb = {"verdict": "A", "reason": GOOD}
        db.add(t)
        db.flush()
        return t.id


def test_skip_reason_lets_an_unchecked_task_through(screencast_task):
    """没录屏不是跳过的理由：质检要的是理由正文，跟录屏没关系。"""
    assert gp.skip_reason(_task(screencast_task)) == ""


def test_skip_reason_turns_down_a_fresh_pass(screencast_task):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, screencast_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(GOOD)}
    assert "没再改过" in gp.skip_reason(_task(screencast_task))


def test_skip_reason_lets_a_stale_pass_back_in(screencast_task):
    """理由在质检之后又改过，那份结论不代表现在这一稿，该重跑。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, screencast_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(GOOD)}
        t.gsb = {**t.gsb, "reason": GOOD + "补一句。"}
    assert gp.skip_reason(_task(screencast_task)) == ""


def test_skip_reason_turns_down_an_unfixed_fail(screencast_task):
    """判了待改、理由却一个字没改，再问一遍挑出来的还是那几处。

    一百多道题一个按钮发出去，这一条漏掉就是一百多次白花的调用，而人看不出来——
    结果和上一次长得一模一样。
    """
    from app.db import session

    with session() as db:
        t = db.get(m.Task, screencast_task)
        t.precheck_status = m.PRECHECK_FAIL
        t.precheck = {"passed": False, "reason_digest": gp.reason_digest(GOOD)}
    assert "没再改过" in gp.skip_reason(_task(screencast_task))


def test_skip_reason_lets_a_fixed_fail_back_in(screencast_task):
    """按意见改完了，这一稿还没问过模型，该再跑一次。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, screencast_task)
        t.precheck_status = m.PRECHECK_FAIL
        t.precheck = {"passed": False, "reason_digest": gp.reason_digest(GOOD)}
        t.gsb = {**t.gsb, "reason": GOOD.replace("两边对问题的定位一致", "两边对问题的定位是一致的")}
    assert gp.skip_reason(_task(screencast_task)) == ""


def test_skip_reason_always_lets_an_error_retry(screencast_task):
    """ERROR 是质检自己没跑成（账单被拒、模型超时），重跑正是该做的事。"""
    from app.db import session

    with session() as db:
        t = db.get(m.Task, screencast_task)
        t.precheck_status = m.PRECHECK_ERROR
        t.precheck = {"error": "账号有未付账单", "reason_digest": gp.reason_digest(GOOD)}
    assert gp.skip_reason(_task(screencast_task)) == ""


def test_skip_reason_turns_down_a_task_still_running(screencast_task):
    from app.db import session

    with session() as db:
        db.get(m.Task, screencast_task).precheck_status = m.PRECHECK_RUNNING
    assert "正在跑" in gp.skip_reason(_task(screencast_task))


def test_skip_reason_turns_down_a_task_without_a_reason(tmp_db):
    from app.db import session

    with session() as db:
        t = m.Task(task_no="13", prompt_hash="h", user_prompt="x", status=m.ANALYZED)
        db.add(t)
        db.flush()
        tid = t.id
    assert "理由正文" in gp.skip_reason(_task(tid))


def test_start_batch_reports_what_it_refused_to_send(screencast_task, monkeypatch):
    """一批里挡下几道，人必须当场知道是哪几道 —— 否则他以为整批都发了，
    回头对不上数才发现。"""
    from app.db import session

    with session() as db:
        done = m.Task(task_no="14", prompt_hash="h", user_prompt="x", status=m.ANALYZED)
        done.gsb = {"verdict": "A", "reason": GOOD}
        done.precheck_status = m.PRECHECK_PASS
        done.precheck = {"passed": True, "reason_digest": gp.reason_digest(GOOD)}
        db.add(done)
        db.flush()
        done_id = done.id

    _stub(monkeypatch, text=_report(passed=True))

    async def go():
        res = gp.start_batch([screencast_task, done_id])
        await gp._batch
        return res

    res = asyncio.run(go())
    assert res["started"] == 1
    assert [s["task_no"] for s in res["skipped"]] == ["14"]
    # 挡下的那道一次调用都没花：结论还是原来那份
    assert _task(done_id).precheck["passed"] is True
    assert _task(screencast_task).precheck_status == m.PRECHECK_PASS


def test_start_batch_refuses_when_nothing_is_worth_running(screencast_task):
    from app.db import session

    with session() as db:
        t = db.get(m.Task, screencast_task)
        t.precheck_status = m.PRECHECK_PASS
        t.precheck = {"passed": True, "reason_digest": gp.reason_digest(GOOD)}
    res = gp.start_batch([screencast_task])
    assert res["ok"] is False and res["started"] == 0
    assert gp.batch_running() is False


def test_batch_keeps_going_after_one_task_blows_up(screencast_task, monkeypatch):
    """一道炸了不能把整批带走：后面那些和它没关系。"""
    from app.db import session

    with session() as db:
        second = m.Task(task_no="15", prompt_hash="h", user_prompt="x", status=m.ANALYZED)
        second.gsb = {"verdict": "A", "reason": GOOD}
        db.add(second)
        db.flush()
        second_id = second.id

    calls: list[str] = []

    async def ask(prompt, **kw):
        calls.append(kw.get("purpose", ""))
        if len(calls) == 1:
            raise LlmError("第一道超时了", retryable=True)
        return LlmResult(text=_report(passed=True), model="stub-model")

    monkeypatch.setattr(gp.llm, "ask", ask)

    async def go():
        gp.start_batch([screencast_task, second_id])
        await gp._batch

    asyncio.run(go())
    assert len(calls) == 2
    assert gp.job()["failed"] == 1 and gp.job()["passed"] == 1
    assert _task(screencast_task).precheck_status == m.PRECHECK_ERROR
    assert _task(second_id).precheck_status == m.PRECHECK_PASS


def test_job_tallies_the_batch_and_clears_running(screencast_task, monkeypatch):
    _stub(monkeypatch, text=_report(passed=False,
                                    issues=[{"quote": "两边对问题的定位一致", "kind": "句子生硬"}]))

    async def go():
        gp.start_batch([screencast_task])
        await gp._batch

    asyncio.run(go())
    job = gp.job()
    assert job["running"] is False and job["done"] == 1 and job["total"] == 1
    assert job["revise"] == 1 and job["passed"] == 0
    assert job["current"] == "" and job["finished_at"]
