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
from app.routers import recording as recording_router
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
    # 结论已出的题按两道质检过没过在「待质检」和「待录屏」之间对一次账，顺便把
    # ALTER TABLE 补出来的空档规整成 IDLE。事实核验是后加的一道，历史数据一律没跑过，
    # 这一次会把它们从待录屏拉回待质检，交给看门狗补上。
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
    log.info("质检    : 分析完自动接两道——事实核验（拿轨迹对理由里的执行结果，"
             "不符处直接订正）与措辞质检，都放行才进待录屏；卡住的由巡检补跑")
    # 录屏是整条流水线上唯一还等人的一步，而人手上只有两个文件路径。把这条命令印在
    # 启动日志里，省得下次要交录屏时先去翻文档找它叫什么
    from app.services import rec_repo

    rec_ok, rec_why = rec_repo.available()
    if rec_ok:
        log.info("录屏    : 协作已启用，仓库 %s，本机%s；页面 http://localhost:%s/recording",
                 rec_repo.repo_slug(),
                 "只做录屏" if rec_repo.recorder_only() else "自动生成文档并收回视频",
                 config.HOST_PORT)
    else:
        log.info("录屏    : 协作未启用（%s）；手工交付 → "
                 "docker compose exec backend python -m app.cli deliver 题号 A.mp4 B.mp4", rec_why)
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
app.include_router(recording_router.router)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("未处理异常")
    return JSONResponse(status_code=500, content={"detail": f"服务内部错误：{exc}"})
