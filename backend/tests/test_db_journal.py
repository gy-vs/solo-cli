"""库的日志模式：必须是 DELETE，不能是 WAL。

WAL 的提交要等一次 checkpoint 才并回主库，而库文件在 Docker Desktop 的 bind mount 上，
容器一重建那批提交就跟着没了 —— 实际表现是改完的设置自己回退（「暂停出队」点了、
接口也返回成功，重启之后队列照旧发容器）。
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, text


@pytest.fixture()
def wal_engine(tmp_path, monkeypatch):
    """一个已经是 WAL 的库，并挂上连接级 pragma，模拟老库被打开的样子。"""
    from app import db as db_mod

    engine = create_engine(f"sqlite:///{tmp_path / 'j.db'}",
                           connect_args={"check_same_thread": False})
    with engine.connect() as c:
        c.exec_driver_sql("PRAGMA journal_mode=WAL")
    event.listen(engine, "connect", db_mod._pragmas)
    monkeypatch.setattr(db_mod, "engine", engine)
    return engine


def test_switches_an_existing_wal_db_to_delete(wal_engine):
    from app import db as db_mod

    assert db_mod.set_journal_mode() == "delete"
    with wal_engine.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar() == "delete"


def test_new_connections_do_not_switch_back_to_wal(wal_engine):
    """journal_mode 是库级属性，连接级 pragma 不许再碰它，否则每条新连接都会改回去。"""
    from app import db as db_mod

    db_mod.set_journal_mode()
    for _ in range(3):
        with wal_engine.connect() as c:      # 每次都会跑一遍 _pragmas
            c.execute(text("select 1"))
    with wal_engine.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar() == "delete"
        # 提交仍然要 fsync，bind mount 上这个不能省
        assert c.execute(text("PRAGMA synchronous")).scalar() == 2
