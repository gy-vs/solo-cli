"""Solo CLI 控制台 · 后端入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import config
from app.db import init_db
from app.routers import design as design_router
from app.routers import settings as settings_router
from app.routers import system as system_router
from app.routers import tasks as tasks_router
from app.services import prompt_bank, settings_store, watchdog
from app.services.scheduler import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("solo-cli")


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.ensure_dirs()
    init_db()
    cleaned = settings_store.sanitize()
    if cleaned:
        log.warning("以下设置存的是界面掩码，已清空，请在设置页重新填写：%s", ", ".join(cleaned))
    seeded = settings_store.seed_from_env()
    if seeded:
        log.info("从环境变量导入设置种子：%s", ", ".join(seeded))
    try:
        if config.prompt_file().exists():
            res = prompt_bank.import_tasks()
            log.info("题库导入：解析 %s 题，新增 %s，已存在 %s", res["parsed"], res["added"] or 0, res["skipped"])
        else:
            log.warning("题库文件不存在：%s", config.prompt_file())
    except Exception:  # noqa: BLE001
        log.exception("题库导入失败")
    await scheduler.start()
    await watchdog.start()
    log.info("=" * 60)
    log.info("Startup Success")
    log.info("Console : http://localhost:%s", config.HOST_PORT)
    log.info("API     : http://localhost:%s/api/health", config.HOST_PORT)
    log.info("Coder   : %s (mount %s)", config.CODER_ROOT_HOST, config.CODER_ROOT_MOUNT)
    log.info("巡检    : 每 %s 秒一轮，异常最多自动重跑 %s 次",
             settings_store.get_int("watchdog.interval_seconds", watchdog.INTERVAL_DEFAULT),
             settings_store.get_int("watchdog.max_retries", watchdog.MAX_RETRIES_DEFAULT))
    log.info("并发    : 最多 %s 个容器（%s 道题同时跑）",
             scheduler.max_parallel, scheduler.max_parallel // 2)
    log.info("=" * 60)
    yield
    await scheduler.stop()
    await watchdog.stop()


app = FastAPI(title="Solo CLI Console", version="1.0.0", lifespan=lifespan)
app.include_router(system_router.router)
app.include_router(settings_router.router)
app.include_router(tasks_router.router)
app.include_router(design_router.router)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("未处理异常")
    return JSONResponse(status_code=500, content={"detail": f"服务内部错误：{exc}"})
