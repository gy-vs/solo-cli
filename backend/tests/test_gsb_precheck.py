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


def test_vet_rewrite_drops_a_shrunken_draft():
    """模型「顺手」把一千字压成两百字发生过。套进去之后论点没了，人得整段重写。"""
    text, why = gp._vet_rewrite("A 更好。", GOOD, "A")
    assert text == "" and "缩水" in why


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
    """没放行的题谈不上过期，那一档要说的是「还没质检」。"""
    assert gp.stale(_task(qc_task)) is False


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


def test_run_precheck_never_touches_the_reason(qc_task, monkeypatch):
    """质检只报问题、不改文字：自动改的话，人下次打开看到的已经不是他确认过的那一段，
    而差异藏在几百字里翻不出来。"""
    _stub(monkeypatch, text=_report(passed=False, rewrite="整段换掉的稿子" * 40,
                                    issues=[{"quote": "两边对问题的定位一致", "kind": "句子生硬"}]))
    asyncio.run(gp.run_precheck(qc_task))
    assert _task(qc_task).gsb["reason"] == GOOD


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
