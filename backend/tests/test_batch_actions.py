"""列表页上的批量动作：批量重跑、批量提交产物并分析。

重跑与推进本身分别在 test_watchdog 里测，这里只测「一批题」这层：一道题出问题不能带着
整批一起失败，而每道题的结果要各自带上原因回去 —— 列表页要按这些原因分类报数，
含糊成一个总数，人就没法知道该去修哪几道。
"""

from __future__ import annotations

import asyncio

import pytest

from app import models as m
from app.db import session
from app.routers import tasks as tasks_router
from app.schemas import IdList, RerunBatch


def _task(task_no: str, status: str, *, run_status: str = m.RUN_FINISHED) -> int:
    with session() as db:
        t = m.Task(task_no=task_no, prompt_hash=f"h-{task_no}", user_prompt="做点事",
                   status=status, repo_url="https://github.com/acme/widget",
                   env_snapshot="https://github.com/acme/widget/commit/" + "c" * 40)
        db.add(t)
        db.flush()
        for side in ("A", "B"):
            db.add(m.TaskRun(task_id=t.id, side=side, status=run_status,
                             container_name=f"solo-cc-{task_no}-{side}"))
        return t.id


@pytest.fixture()
def two_stuck(tmp_db):
    """两道转了需人工的题，都等着重跑。"""
    return _task("07", m.NEEDS_ATTENTION, run_status=m.RUN_TIMEOUT), \
        _task("08", m.NEEDS_ATTENTION, run_status=m.RUN_FAILED)


# ---------------- 批量重跑 ----------------

def test_batch_rerun_keeps_going_after_one_failure(two_stuck, monkeypatch):
    """一道题重跑失败，后面的照跑。

    这批题本来就是出过状况的，失败是常态；抛出去让整个请求 500 的话，人点一次批量重跑
    只知道「失败了」，既不知道哪几道跑上了，也不敢再点第二次。
    """
    first, second = two_stuck
    seen = []

    async def rerun(task_id, sides):
        seen.append((task_id, sides))
        if task_id == first:
            return {"ok": False, "message": "工作目录重置失败"}
        return {"ok": True, "message": "A、B 侧已排队重跑"}

    monkeypatch.setattr(tasks_router.watchdog, "manual_rerun", rerun)

    r = asyncio.run(tasks_router.batch_rerun(RerunBatch(ids=[first, second])))

    assert [x[0] for x in seen] == [first, second]
    assert seen[0][1] == ("A", "B"), "sides 留空就是两侧都重跑"
    assert r["results"][0] == {"id": first, "ok": False, "message": "工作目录重置失败"}
    assert r["results"][1]["ok"] is True


def test_batch_rerun_can_target_one_side(two_stuck, monkeypatch):
    seen = []

    async def rerun(task_id, sides):
        seen.append(sides)
        return {"ok": True, "message": "已排队"}

    monkeypatch.setattr(tasks_router.watchdog, "manual_rerun", rerun)
    asyncio.run(tasks_router.batch_rerun(RerunBatch(ids=list(two_stuck), sides=["b"])))
    assert seen == [("B",), ("B",)], "小写也该认，规范化交给 _side"


def test_batch_rerun_skips_a_task_still_running(tmp_db, monkeypatch):
    """还在跑的那一侧要先停。

    容器刚被销毁、runner 还在往这一行写收尾结果，此时重跑建出来的新一轮会被那份旧账
    盖掉：库里记着第二次跑，而实际跑着的是第一次留下的容器。
    """
    running = _task("09", m.RUNNING, run_status=m.RUN_RUNNING)

    async def boom(task_id, sides):
        raise AssertionError("在跑的题不该进重跑")

    monkeypatch.setattr(tasks_router.watchdog, "manual_rerun", boom)

    r = asyncio.run(tasks_router.batch_rerun(RerunBatch(ids=[running])))
    assert r["results"][0]["ok"] is False
    assert "先停止" in r["results"][0]["message"]


def test_batch_rerun_reports_a_task_that_is_gone(tmp_db):
    r = asyncio.run(tasks_router.batch_rerun(RerunBatch(ids=[4242])))
    assert r["results"] == [{"id": 4242, "ok": False, "message": "题目不存在"}]


# ---------------- 批量提交产物并分析 ----------------

def test_batch_advance_only_queues(tmp_db, monkeypatch):
    """接口只负责排队，不等任何一道跑完。

    推产物之后要跑 GSB 分析和质检，两步都在调模型，一道题十几二十分钟是常态。同步等着
    的话，批量点十道那条 HTTP 请求必然先超时，而动作已经在后台跑起来了。
    """
    ready = _task("07", m.RUN_DONE)
    stuck = _task("08", m.NEEDS_ATTENTION)
    queued = []

    def queue_advance(task_id):
        queued.append(task_id)
        # 额度只够一道，第二道排队等着
        started = len(queued) == 1
        return {"ok": True, "started": started,
                "message": "已开始推产物与分析" if started else "分析并发已满，排在第 1 位等额度"}

    monkeypatch.setattr(tasks_router.watchdog, "queue_advance", queue_advance)

    r = asyncio.run(tasks_router.batch_advance(IdList(ids=[ready, stuck])))

    assert queued == [ready, stuck], "需人工的题也能人工推进：它卡住的正是这一步"
    assert [x["started"] for x in r["results"]] == [True, False]


def test_batch_advance_refuses_a_state_that_has_nothing_to_push(tmp_db, monkeypatch):
    """还在跑、或者早就交上去的题没有产物可推，当场回绝而不是排进队列白跑一趟。"""
    running = _task("09", m.RUNNING, run_status=m.RUN_RUNNING)
    uploaded = _task("10", m.UPLOADED)

    def boom(task_id):
        raise AssertionError("不该排队")

    monkeypatch.setattr(tasks_router.watchdog, "queue_advance", boom)

    r = asyncio.run(tasks_router.batch_advance(IdList(ids=[running, uploaded])))
    assert [x["ok"] for x in r["results"]] == [False, False]
    assert all("不能推进" in x["message"] for x in r["results"])
