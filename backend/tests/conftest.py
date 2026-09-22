"""测试公共设施。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# 会改动本机状态的 docker 子命令。测试里的题号是固定的 07、08，而本机上很可能
# 正好有一个同名容器在跑真活：一次 remove_task_containers 就能把它连同还没导出的
# 轨迹一起删掉。只读的 inspect、ps 照常放行，那些是查询。
_DESTRUCTIVE = {"rm", "stop", "kill", "run", "start", "restart"}


@pytest.fixture(autouse=True)
def no_container_side_effects(monkeypatch):
    """兜住所有会动到真容器的命令，测试跑不出本机的副作用。"""
    from app.services import dockerx

    real = dockerx.run

    async def guarded(args, **kw):
        if list(args[:1]) == ["docker"] and len(args) > 1 and args[1] in _DESTRUCTIVE:
            return dockerx.CmdResult(0, "", "")
        return await real(args, **kw)

    monkeypatch.setattr(dockerx, "run", guarded)


@pytest.fixture(autouse=True)
def tmp_coder_root(tmp_path, monkeypatch):
    """把工作区根目录指到临时目录，和 no_container_side_effects 是同一类保护。

    CODER_ROOT 默认落在 `/Users/gaoyong/solo-coder-0908`，那是真人的工作区。凡是
    会写盘的代码路径（归档录屏、落分析材料、写轨迹索引）在测试里都会往那儿写 ——
    本机上没有这个目录就抛 PermissionError，有这个目录则更糟：测试会把题号 07、08
    的真实产物覆盖掉。

    TaskPaths 的每个属性都是现取模块全局，所以换掉属性就能让全部调用方一起改道，
    不必逐个 fixture 去传路径。
    """
    from app import config

    monkeypatch.setattr(config, "CODER_ROOT_MOUNT", tmp_path / "coder")
    monkeypatch.setattr(config, "CODER_ROOT_HOST", str(tmp_path / "coder"))
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path / "exports")


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
    from app.models import QUEUED, Task, TaskRun

    with session() as db:
        # 有 run 的题一定已经领取过了。留默认的 AVAILABLE 会让巡检扫不到它 ——
        # 那一步只看还在流程里的题，见 models.WATCHED。
        t = Task(task_no="07", prompt_hash="h", user_prompt="做点事", status=QUEUED,
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
