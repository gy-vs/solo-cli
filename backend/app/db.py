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
    cur.execute("PRAGMA journal_mode=WAL")
    # NORMAL 下提交不 fsync，Docker Desktop 的 bind mount 在容器重建时会把还没落盘的
    # 提交丢掉——设置改完一重启就回退，任务状态同样会丢。写入量很小，换成 FULL。
    cur.execute("PRAGMA synchronous=FULL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)
    _ensure_columns()


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
