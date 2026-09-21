"""Solo CLI 控制台 · 后端入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import config
from app.db import init_db
from app.routers import design as design_router
from app.routers import host as host_router
from app.routers import settings as settings_router
from app.routers import system as system_router
from app.routers import tasks as tasks_router
from app.services import gsb_precheck, pool, pool_bank, prompt_bank, settings_store, watchdog
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
    # 题库来源二选一，不并存：池启用时远端是唯一真相源，本机题面文件只是出题的产物，
    # 再导一遍会让同一道题在本机多出一行没有远端归属、因而不受跨设备独占保护的副本。
    try:
        if pool.enabled():
            res = await pool_bank.refresh()
            if res["ok"]:
                log.info("题库同步：%s", res["message"])
            else:
                log.warning("题库同步失败，本机题目仍是上次同步的样子：%s", res["message"])
        elif config.prompt_file().exists():
            res = prompt_bank.import_tasks()
            log.info("题库导入：解析 %s 题，新增 %s，已存在 %s", res["parsed"], res["added"] or 0, res["skipped"])
        else:
            log.warning("题库文件不存在：%s", config.prompt_file())
    except Exception:  # noqa: BLE001
        log.exception("题库导入失败")
    # 结论已出的题按录屏齐不齐在「待录屏」和「质检」之间对一次账。质检这一步是后加的，
    # 不补这一次，此前录屏齐了的题会挂在待录屏栏里，提交按钮还是灰的。
    gsb_precheck.sync_all()
    await scheduler.start()
    await watchdog.start()
    log.info("=" * 60)
    log.info("Startup Success")
    log.info("Console : http://localhost:%s", config.HOST_PORT)
    log.info("API     : http://localhost:%s/api/health", config.HOST_PORT)
    log.info("Coder   : %s (mount %s)", config.CODER_ROOT_HOST, config.CODER_ROOT_MOUNT)
    snap = pool.snapshot()
    if snap["enabled"]:
        log.info("题库    : 远端 %s，本机标识 %s；共 %s 道，本机已领 %s 道、其他设备领走 %s 道",
                 snap["repo"] or "未配置", snap["device"], snap["total"],
                 snap["claimed_by_me"], snap["claimed_by_others"])
    else:
        log.info("题库    : 本地 %s（单设备模式，未启用远端题库）", config.prompt_file())
    log.info("巡检    : 每 %s 秒一轮，一侧最多跑 %s 次 / 超时 %s 次，用尽自动废弃整题%s",
             settings_store.get_int("watchdog.interval_seconds", watchdog.INTERVAL_DEFAULT),
             settings_store.get_int("watchdog.max_retries", watchdog.MAX_RETRIES_DEFAULT),
             settings_store.get_int("watchdog.max_timeouts", watchdog.MAX_TIMEOUTS_DEFAULT),
             "（自动重跑已暂停）" if settings_store.get_bool("watchdog.paused", False) else "")
    log.info("并发    : 最多 %s 个容器，按容器排队（A、B 各排各的，跑完再配对）",
             scheduler.max_parallel)
    # 页面上没有这个入口（nginx 也挡了发起路由），所以把命令印在启动日志里，
    # 免得下次想跑质检时先去翻代码找它在哪
    log.info("质检    : 提交前质检只能在这里发起 → "
             "docker compose exec backend python -m app.cli precheck")
    log.info("=" * 60)
    yield
    await scheduler.stop()
    await watchdog.stop()


app = FastAPI(title="Solo CLI Console", version="1.0.0", lifespan=lifespan)
app.include_router(system_router.router)
app.include_router(settings_router.router)
app.include_router(tasks_router.router)
app.include_router(design_router.router)
app.include_router(host_router.router)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("未处理异常")
    return JSONResponse(status_code=500, content={"detail": f"服务内部错误：{exc}"})
