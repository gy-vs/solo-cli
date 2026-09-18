"""SQLite + 同步 SQLAlchemy。

单机单人工具，写入量很小，用同步 Session 配合短事务足够；
asyncio 侧直接调用（SQLite 本地文件，毫秒级），不引入 aiosqlite 的复杂度。
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.models import Base

config.ensure_dirs()
engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
    future=True,
)


@event.listens_for(engine, "connect")
def _pragmas(dbapi_conn, _record) -> None:  # noqa: ANN001
    cur = dbapi_conn.cursor()
    # NORMAL 下提交不 fsync，Docker Desktop 的 bind mount 在容器重建时会把还没落盘的
    # 提交丢掉——设置改完一重启就回退，任务状态同样会丢。写入量很小，换成 FULL。
    cur.execute("PRAGMA synchronous=FULL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()
    # journal_mode 不在这里设：它是写在库文件头上的库级属性，不是连接级的，
    # 每建一条连接就改一次既没必要，还会在别的连接占着库时静默失败。见 _set_journal_mode。


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    set_journal_mode()
    Base.metadata.create_all(engine)
    _ensure_columns()


def set_journal_mode(mode: str = "DELETE") -> str:
    """把日志模式定在 DELETE，不用 WAL。返回实际生效的模式。

    WAL 的提交先落到 -wal 文件，要等一次 checkpoint 才并回主库。而库文件在
    Docker Desktop 的 bind mount 上，容器一重建，还没 checkpoint 的那批提交就跟着
    没了：界面上刚改的设置自己回退、任务状态退回上一个样子，data 目录里那几个
    .corrupt 也是这么来的。实际踩到过一次——「暂停出队」点了、接口也返回成功，
    重启之后队列照旧把容器发出去。

    DELETE 模式每次提交直接改主库文件再删掉回滚日志，不依赖 checkpoint 的时机。
    代价是读写不能并发，但这是单机单人的工具，写入量很小。
    """
    import logging

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        # 走裸连接：PRAGMA journal_mode 在事务里改不动，SQLite 会直接拒绝
        actual = str(cur.execute(f"PRAGMA journal_mode={mode}").fetchone()[0])
        cur.close()
    finally:
        raw.close()
    if actual.lower() != mode.lower():
        logging.getLogger("db").warning(
            "日志模式仍是 %s，切到 %s 没成功（多半有别的连接占着库），"
            "容器重建时可能丢掉最近的提交", actual, mode)
    return actual


def _ensure_columns() -> None:
    """最小迁移：模型新增的列用 ALTER TABLE 补上。

    单机工具不引入 Alembic；新增列必须 nullable 或可给出 DDL 默认值，
    否则 SQLite 的 ADD COLUMN 会拒绝。
    """
    from sqlalchemy import text
    from sqlalchemy.schema import CreateColumn

    with engine.begin() as conn:
        for table in Base.metadata.tables.values():
            rows = conn.execute(text(f"PRAGMA table_info('{table.name}')")).all()
            if not rows:
                continue
            existing = {r[1] for r in rows}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = str(CreateColumn(col).compile(engine))
                if not col.nullable and "DEFAULT" not in ddl.upper():
                    literal = "0" if str(col.type).upper().startswith(("INT", "BOOL", "FLOAT")) else "''"
                    ddl += f" DEFAULT {literal}"
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {ddl}"))
                log_migration(table.name, col.name)


def log_migration(table: str, column: str) -> None:
    import logging

    logging.getLogger("db").info("迁移：%s 新增列 %s", table, column)


@contextmanager
def session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Iterator[Session]:
    """FastAPI 依赖。"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
