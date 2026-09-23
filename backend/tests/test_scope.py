"""开跑前的改动面体检：判据、缓存有效期，以及它在门禁和领取路径上的位置。"""

from __future__ import annotations

import asyncio
import json

import pytest

from app import models as m
from app.db import session
from app.services import gate, llm
from app.services import scope as sc


def _reply(modules, confidence="high", note="改动面"):
    return json.dumps({"modules": [{"path": p, "why": "非改不可"} for p in modules],
                       "confidence": confidence, "note": note}, ensure_ascii=False)
@pytest.fixture()
def task(tmp_db):
    """一道还没领取的题，题面非空。"""
    with session() as db:
        t = m.Task(task_no="07", prompt_hash="h", user_prompt="把解析和渲染两头都改了",
                   status=m.AVAILABLE, difficulty="困难", question_type="feature迭代",
                   repro_level="无外部依赖",
                   repo_url="https://github.com/acme/widget",
                   env_snapshot="https://github.com/acme/widget/commit/" + "c" * 40)
        db.add(t)
        db.flush()
        return t.id


@pytest.fixture()
def answers(monkeypatch):
    """替掉模型调用，返回一个可以逐次改写的答案槽。"""
    slot = {"text": _reply(["src/parser", "src/render"]), "calls": 0, "error": None}

    async def fake_ask(prompt, **kw):
        slot["calls"] += 1
        slot["prompt"] = prompt
        if slot["error"]:
            raise slot["error"]
        return llm.LlmResult(text=slot["text"], model="test-model")

    monkeypatch.setattr(llm, "ask", fake_ask)
    return slot
# ---------------- 判据 ----------------

def test_a_question_touching_two_modules_passes():
    r = sc.normalize({"modules": [{"path": "src/parser", "why": "x"},
                                  {"path": "src/render", "why": "y"}]}, need=2)
    assert r["verdict"] == sc.PASS
    assert r["module_count"] == 2


def test_a_question_confined_to_one_module_is_narrow():
    r = sc.normalize({"modules": [{"path": "src/parser", "why": "x"}]}, need=2)
    assert r["verdict"] == sc.NARROW
    assert "只有 1 个模块" in sc.summary(r)


def test_the_same_directory_reported_twice_counts_once():
    """模型偶尔把一个目录按两个功能点拆着报，那样数出来的宽度是假的。"""
    r = sc.normalize({"modules": [{"path": "src/parser", "why": "改词法"},
                                  {"path": "src/Parser", "why": "改语法"}]}, need=2)
    assert r["module_count"] == 1
    assert r["verdict"] == sc.NARROW


def test_the_models_own_verdict_is_ignored():
    """只数它列出来的模块。让它自己下结论，它会顺着题面的语气答。"""
    r = sc.normalize({"modules": [{"path": "src/parser", "why": "x"}],
                      "cross_module": True, "verdict": "pass"}, need=2)
    assert r["verdict"] == sc.NARROW
def test_the_threshold_comes_from_settings(monkeypatch, tmp_db):
    """把要求提到三个模块，两个模块的题就该被拦下。"""
    from app.services import settings_store
    monkeypatch.setattr(settings_store, "get_int", lambda k, d=0: 3 if k == "difficulty.min_modules" else d)
    payload = {"modules": [{"path": "a", "why": "x"}, {"path": "b", "why": "y"}]}
    assert sc.normalize(payload, need=sc.min_modules())["verdict"] == sc.NARROW


def test_asking_for_fewer_than_two_modules_turns_the_check_off(monkeypatch):
    """要求少于两个模块等于不要求，这时整道校验都不该跑，省下那次调用。"""
    from app.services import settings_store
    monkeypatch.setattr(settings_store, "get_int", lambda k, d=0: 1)
    assert not sc.enabled()


# ---------------- 跑一遍并落库 ----------------

def test_a_check_stores_the_modules_it_found(task, answers):
    r = asyncio.run(sc.check(task))
    assert r["verdict"] == sc.PASS
    with session() as db:
        stored = db.get(m.Task, task).scope
    assert [x["path"] for x in stored["modules"]] == ["src/parser", "src/render"]
    assert stored["model"] == "test-model"


def test_the_question_text_reaches_the_model(task, answers):
    asyncio.run(sc.check(task))
    assert "把解析和渲染两头都改了" in answers["prompt"]
def test_a_model_failure_does_not_block_the_question(task, answers):
    """体检自己没跑成不算这道题的错。把整批题卡在领取上，代价比放几道简单题进去大。"""
    answers["error"] = llm.LlmError("网关欠费", retryable=False)
    r = asyncio.run(sc.check(task))
    assert r["verdict"] == sc.UNKNOWN
    with session() as db:
        assert not sc.blocking(db.get(m.Task, task))


def test_unparsable_output_is_also_treated_as_unknown(task, answers):
    answers["text"] = "我觉得这道题挺难的。"
    assert asyncio.run(sc.check(task))["verdict"] == sc.UNKNOWN


def test_a_question_with_no_body_is_not_sent_to_the_model(task, answers):
    with session() as db:
        db.get(m.Task, task).user_prompt = "   "
    assert asyncio.run(sc.check(task))["verdict"] == sc.UNKNOWN
    assert answers["calls"] == 0
# ---------------- 结论的有效期 ----------------

def test_a_second_claim_reuses_the_stored_verdict(task, answers):
    """同一道题放回再领是常事，每次都问一遍模型，问的还是同一段话。"""
    asyncio.run(sc.ensure(task))
    asyncio.run(sc.ensure(task))
    assert answers["calls"] == 1


def test_rewriting_the_question_invalidates_the_verdict(task, answers):
    asyncio.run(sc.ensure(task))
    with session() as db:
        db.get(m.Task, task).user_prompt = "换了一道完全不同的题"
    asyncio.run(sc.ensure(task))
    assert answers["calls"] == 2


def test_reflowing_the_question_does_not_invalidate_it(task, answers):
    """指纹去掉全部空白再算：只动了换行和缩进不算改题。"""
    asyncio.run(sc.ensure(task))
    with session() as db:
        db.get(m.Task, task).user_prompt = "把解析和渲染\n  两头都改了"
    asyncio.run(sc.ensure(task))
    assert answers["calls"] == 1


def test_a_failed_check_is_not_retried_on_every_claim(task, answers):
    """体检没跑成也算一份结论。不然模型调不通的时候这道题每次领取都要再等一次超时。"""
    answers["error"] = llm.LlmError("超时", retryable=True)
    asyncio.run(sc.ensure(task))
    answers["error"] = None
    asyncio.run(sc.ensure(task))
    assert answers["calls"] == 1


# ---------------- 人工放行 ----------------

def test_an_override_releases_a_narrow_question(task, answers):
    answers["text"] = _reply(["src/parser"])
    asyncio.run(sc.check(task))
    with session() as db:
        t = db.get(m.Task, task)
        assert sc.blocking(t)
        assert sc.override(t)
    with session() as db:
        assert not sc.blocking(db.get(m.Task, task))


def test_an_override_survives_a_recheck(task, answers):
    """放行之后再体检一遍，结论会更新，但放行的记号不该被盖掉。"""
    answers["text"] = _reply(["src/parser"])
    asyncio.run(sc.check(task))
    with session() as db:
        sc.override(db.get(m.Task, task))
    asyncio.run(sc.check(task))
    with session() as db:
        t = db.get(m.Task, task)
        assert t.scope["override"]
        assert not sc.blocking(t)
# ---------------- 门禁 ----------------

def test_the_gate_blocks_a_narrow_question_but_not_hard(task, answers):
    """拦得住但不是硬前提：判的是值不值得跑，不是能不能跑，强制启动该照走。"""
    answers["text"] = _reply(["src/parser"])
    asyncio.run(sc.check(task))
    with session() as db:
        c = gate._scope_check(db.get(m.Task, task))
    assert c.level == "block"
    assert not c.hard
    assert c.fix == "scope_override"


def test_the_gate_only_reports_on_a_question_never_checked(task, answers):
    with session() as db:
        c = gate._scope_check(db.get(m.Task, task))
    assert c.level == "warn"
    assert c.fix == "scope_check"
    assert answers["calls"] == 0
def test_the_gate_never_calls_the_model(task, answers):
    """门禁每次重新检查都会跑一遍，在这里调模型等于一次翻页烧掉十几次调用。"""
    asyncio.run(sc.check(task))
    before = answers["calls"]
    with session() as db:
        gate._scope_check(db.get(m.Task, task))
        gate._scope_check(db.get(m.Task, task))
    assert answers["calls"] == before


def test_a_stale_verdict_does_not_block(task, answers):
    """题面改过了，旧结论不代表现在这道题，不能拿它拦人。"""
    answers["text"] = _reply(["src/parser"])
    asyncio.run(sc.check(task))
    with session() as db:
        db.get(m.Task, task).user_prompt = "改成了一道跨好几层的题"
    with session() as db:
        c = gate._scope_check(db.get(m.Task, task))
    assert c.level == "warn"


# ---------------- 批量 ----------------

def test_warming_a_batch_skips_the_ones_already_checked(task, answers):
    asyncio.run(sc.check(task))
    out = asyncio.run(sc.warm([task]))
    assert out == {"checked": 0, "cached": 1, "narrow": 0}
    assert answers["calls"] == 1


def test_ready_ids_only_lists_unchecked_claimable_questions(task, answers):
    """跑起来之后再判改动面已经晚了，那时机器时间已经花出去。"""
    assert sc.ready_ids() == [task]
    asyncio.run(sc.check(task))
    assert sc.ready_ids() == []
    with session() as db:
        db.get(m.Task, task).status = m.RUNNING
        db.get(m.Task, task).scope = {}
    assert sc.ready_ids() == []


def test_a_discarded_question_is_never_written_to(task, answers):
    """废弃是人拍过板的结果，这道校验不该往一道已经结案的题上写新结论。"""
    with session() as db:
        db.get(m.Task, task).status = m.DISCARDED
    asyncio.run(sc.check(task))
    with session() as db:
        t = db.get(m.Task, task)
        assert t.scope == {}
        assert t.status == m.DISCARDED


def test_warming_a_batch_skips_questions_already_running(task, answers):
    """跑起来之后再判改动面已经晚了，废弃的更不必花这次调用。"""
    with session() as db:
        db.get(m.Task, task).status = m.DISCARDED
    assert asyncio.run(sc.warm([task])) == {"checked": 0, "cached": 0, "narrow": 0}
    assert answers["calls"] == 0


def test_a_batch_survives_one_question_blowing_up(task, answers, monkeypatch):
    """一道题体检炸了不该把整批的结果吞掉。"""
    async def boom(tid):
        raise RuntimeError("炸了")

    monkeypatch.setattr(sc, "check", boom)
    assert asyncio.run(sc.warm([task]))["checked"] == 1


# ---------------- 目录树 ----------------
def test_the_tree_is_empty_when_nothing_is_cloned(task):
    """没 clone 时照样能判，只是模型看不到真实目录。"""
    assert sc.repo_tree("07") == ""


def test_the_prompt_says_so_when_there_is_no_tree():
    with_tree = sc.build_prompt("题面", "src/\nsrc/parser/", 2)
    without = sc.build_prompt("题面", "", 2)
    assert "src/parser/" in with_tree
    assert "拿不到仓库结构" in without
