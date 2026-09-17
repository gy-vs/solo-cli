"""一个项目同时只跑一道题。

04 和 05 用的是同一个 markdown-engine 仓库，各有自己的分支。门禁按这个口径阻断启动，
调度器按同一口径挑题：被占住的留在队列里，等前一道跑完自动进。
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db as dbmod
from app import config
from app.db import init_db, session
from app.models import AVAILABLE, CLAIMED, DONE, QUEUED, RUNNING, Task
from app.services import gate
from app.services.scheduler import Scheduler

MD = "https://github.com/gy-vs/markdown-engine/commit/43eea3062375ce2f5cba16385f1c7c7c3a361908"
CSS = "https://github.com/gy-vs/css-engine/commit/554b1a2534c6e7b0852d9ddc3da294272759ecdd"


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = tmp_path / "t.db"
    monkeypatch.setattr(config, "DB_PATH", p)
    eng = create_engine(f"sqlite:///{p}", future=True)
    monkeypatch.setattr(dbmod, "engine", eng)
    monkeypatch.setattr(dbmod, "SessionLocal", sessionmaker(bind=eng, expire_on_commit=False, future=True))
    init_db()
    return eng


def _add(no: str, snapshot: str, status: str, priority: int = 100) -> int:
    with session() as s:
        t = Task(task_no=no, prompt_hash=f"h{no}", user_prompt="p", env_snapshot=snapshot,
                 status=status, priority=priority)
        s.add(t)
        s.flush()
        return t.id


def test_running_siblings_only_count_same_repo(db):
    me = _add("04", MD, CLAIMED)
    _add("05", MD, RUNNING)
    _add("07", MD, QUEUED)      # 排队的还没占住工作区
    _add("12", MD, DONE)
    _add("09", CSS, RUNNING)    # 别的项目不相干

    assert gate.repo_siblings_running(me, "gy-vs/markdown-engine") == ["05"]


def test_quiet_when_nobody_running(db):
    me = _add("04", MD, CLAIMED)
    _add("05", MD, AVAILABLE)
    assert gate.repo_siblings_running(me, "gy-vs/markdown-engine") == []
    assert gate.repo_siblings_running(me, "") == []


def test_self_never_counted(db):
    me = _add("04", MD, RUNNING)
    assert gate.repo_siblings_running(me, "gy-vs/markdown-engine") == []


def test_scheduler_skips_project_already_running(db):
    _add("05", MD, RUNNING)
    q04 = _add("04", MD, QUEUED, priority=1)     # 排最前，但项目被 05 占着
    q09 = _add("09", CSS, QUEUED, priority=2)

    s = Scheduler()
    assert s._pick(3) == [q09]
    assert [w["task_no"] for w in s.waiting_on_repo()] == ["04"]
    assert s.waiting_on_repo()[0]["blocked_by"] == "05"

    # 05 跑完，04 立刻可以进
    with session() as sess:
        sess.get(Task, _id_of("05")).status = DONE
    assert s._pick(3) == [q04, q09]


def test_scheduler_takes_one_per_project_in_same_tick(db):
    a = _add("04", MD, QUEUED, priority=1)
    _add("05", MD, QUEUED, priority=2)           # 同项目，本轮不能一起上
    c = _add("09", CSS, QUEUED, priority=3)

    assert Scheduler()._pick(3) == [a, c]


def _id_of(no: str) -> int:
    with session() as s:
        return s.query(Task).filter(Task.task_no == no).one().id
