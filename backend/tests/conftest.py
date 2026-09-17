"""测试公共设施。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """把 db 模块的 engine 换成临时库。

    不 reload app.db：别的模块都是 `from app.db import session` 拿到的函数对象，
    reload 之后它们手上还是旧引用，改了也不生效。而 session() 内部对
    SessionLocal 是模块级查找，替掉模块属性就能让所有调用方一起用上临时库。
    """
    from app import db as db_mod
    from app.models import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr(db_mod, "engine", engine)
    monkeypatch.setattr(db_mod, "SessionLocal", local)
    return engine


@pytest.fixture()
def task_with_runs(tmp_db):
    """一道题加它的 A、B 两个 run，返回 (task_id, {side: run_id})。"""
    from app.db import session
    from app.models import Task, TaskRun

    with session() as db:
        t = Task(task_no="07", prompt_hash="h", user_prompt="做点事",
                 repo_url="https://github.com/acme/widget",
                 env_snapshot="https://github.com/acme/widget/commit/" + "c" * 40)
        db.add(t)
        db.flush()
        ids = {}
        for side in ("A", "B"):
            r = TaskRun(task_id=t.id, side=side,
                        container_name=f"solo-cc-07-{side}")
            db.add(r)
            db.flush()
            ids[side] = r.id
        return t.id, ids
