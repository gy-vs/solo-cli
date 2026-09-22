"""题库、双跑、GSB 结论、上传、生命周期。"""

from __future__ import annotations

import asyncio
import codecs
import json
import logging
from contextlib import suppress
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select

from app import config
from app.db import session
from app.events import bus, sse_format
from app.models import (
    ANALYSIS_RUNNING, ANALYZED, AVAILABLE, CLAIMED, DISCARDED, DONE, NEEDS_ATTENTION, QC,
    QUEUED, RUN_DONE, RUN_RUNNING, RUNNING, UPLOADED, RunEvent, Task, TaskRun, utc_now,
)
from app.schemas import (
    GsbUpdate, IdList, PrecheckConfirm, QueueMove, RerunBatch, RerunRequest,
    ScreencastDeliver, ScreencastUpdate, task_brief, task_detail,
)
from app.services import (
    dockerx, gate, gsb_analyzer, gsb_factcheck, gsb_precheck, gsb_repo, gsb_uploader,
    gsb_verifier, pool, pool_bank, prompt_bank, runner, scheduler, settings_store,
    trace, watchdog,
)

log = logging.getLogger("tasks")
router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# 领取被别的设备抢先时的错误码。界面靠它区分「这题没了」和普通的领取失败：
# 前者要提示一句并立刻刷新列表，后者停在原地让人看门禁报告。
POOL_TAKEN = "POOL_TAKEN"


def _get(db, task_id: int) -> Task:  # noqa: ANN001
    t = db.get(Task, task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    return t


def _runs(db, task_id: int) -> list[TaskRun]:  # noqa: ANN001
    return db.query(TaskRun).filter(TaskRun.task_id == task_id).all()


def _side(value: str) -> str:
    s = (value or "").upper()
    if s not in config.SIDES:
        raise HTTPException(400, "side 必须是 A 或 B")
    return s


# ---------------- 题库 ----------------

@router.post("/sync")
async def sync_bank() -> dict:
    """从远端题库拉最新的可领取题目。池没启用时退回本地题面文件。"""
    if not pool.enabled():
        return await import_bank()
    res = await pool_bank.refresh()
    if not res["ok"]:
        raise HTTPException(400, res["message"])
    bus.publish("tasks", {"type": "bank"})
    return res


@router.post("/import")
async def import_bank() -> dict:
    """解析本机题面文件导入。单设备模式下的题库来源，也给远端不可用时兜底。"""
    if not config.prompt_file().exists():
        raise HTTPException(400, f"找不到题库文件 {config.prompt_file()}")
    res = prompt_bank.import_tasks()
    bus.publish("tasks", {"type": "bank"})
    return {"ok": True, "message": f"解析 {res['parsed']} 题，新增 {len(res['added'])}，"
                                   f"已存在 {res['skipped']}", **res}


@router.get("")
async def list_tasks(status: str = Query(default=""), exclude_done: bool = Query(default=False),
                     include_discarded: bool = Query(default=False)) -> dict:
    """默认不返回已废弃的题；需要时用 include_discarded 或显式 status=DISCARDED 取。"""
    with session() as db:
        q = select(Task).order_by(Task.task_no, Task.id)
        wanted = [s for s in status.split(",") if s]
        if wanted:
            q = q.where(Task.status.in_(wanted))
        elif not include_discarded:
            q = q.where(Task.status != DISCARDED)
        if exclude_done:
            q = q.where(Task.status != DONE)
        tasks = db.execute(q).scalars().all()
        # 一次把所有 run 取回来按 task_id 归组，别在循环里逐题查库
        by_task: dict[int, list[TaskRun]] = {}
        for r in db.execute(select(TaskRun)).scalars():
            by_task.setdefault(r.task_id, []).append(r)
        items = [task_brief(t, by_task.get(t.id, [])) for t in tasks]
    return {"items": items}


# ---------------- 集合操作 ----------------
# 这些路径必须注册在 /{task_id}/… 之前：FastAPI 按注册顺序匹配，
# 先命中 /{task_id}/upload 的话 "batch" 会被当成 task_id 直接 422。

@router.get("/queue/list")
async def queue_list() -> dict:
    with session() as db:
        rows = db.execute(
            select(Task).where(Task.status.in_([QUEUED, RUNNING]))
            .order_by(Task.status.desc(), Task.priority, Task.claimed_at, Task.id)
        ).scalars().all()
        items = [task_brief(t, _runs(db, t.id)) for t in rows]
    return {"items": items, "scheduler": scheduler.scheduler.snapshot()}


@router.post("/queue/pause")
async def queue_pause(paused: bool = Query(default=True)) -> dict:
    settings_store.set_one("scheduler.paused", "1" if paused else "0")
    bus.publish("tasks", {"type": "scheduler"})
    return {"ok": True, "paused": paused,
            "message": "已暂停出队，运行中的不受影响" if paused else "已恢复出队"}


@router.post("/watchdog/pause")
async def watchdog_pause(paused: bool = Query(default=True)) -> dict:
    settings_store.set_one("watchdog.paused", "1" if paused else "0")
    bus.publish("tasks", {"type": "watchdog"})
    return {"ok": True, "paused": paused,
            "message": ("已暂停自动重跑与自动废弃，题目保持当前状态"
                        if paused else "已恢复自动重跑")}


@router.post("/queue/parallel")
async def queue_parallel(value: int = Query(...)) -> dict:
    value = max(1, min(12, value))
    settings_store.set_one("scheduler.max_parallel", str(value))
    bus.publish("tasks", {"type": "scheduler"})
    return {"ok": True, "max_parallel": value, "message": f"同时最多 {value} 个容器"}


@router.post("/batch/upload")
async def batch_upload(body: IdList) -> dict:
    results = []
    for tid in body.ids:
        res = await gsb_uploader.upload_task(tid)
        results.append({"id": tid, **res})
    return {"results": results}


# ---------------- 提交前质检 ----------------
# 三个发起口，按「谁在等结果」分：
#   batch/precheck        串行跑完才返回，给 app.cli —— 人在终端里守着，要的就是那份汇总
#   batch/precheck/start  立刻返回，给页面上的批量质检 —— 一百多道要跑几个小时，
#                         浏览器挂不住这么长的连接，进度改从 /api/system/status 上看
#   {task_id}/precheck    单道，跑完返回，页面和 CLI 都能用（一道一分半，等得起）
#
# 早先这几个口都被 nginx 挡着不让浏览器碰，理由是质检该等到看完录屏、准备提交那一刻
# 再跑。后来改成录屏之前先质检：措辞在录屏前改完，省一次重录。「点一下烧一次模型调用」
# 那层顾虑没消失，改由 gsb_precheck.skip_reason 兜——已经有有效结论的题根本发不出去。

@router.get("/precheck/ready")
async def precheck_ready() -> dict:
    """该做质检的题：结论已出、还没拿到有效结论。CLI 默认按这个口径挑。

    不看录屏。质检排在录屏前面，等录屏齐了才挑就回到了「措辞一改得重录」的老流程。
    """
    ids = gsb_precheck.ready_ids()
    with session() as db:
        items = [task_brief(_get(db, tid), _runs(db, tid)) for tid in ids]
    return {"ids": ids, "items": items}


@router.post("/batch/quality-gate")
async def batch_quality_gate(body: IdList) -> dict:
    """把勾中的题整条质检走一遍（事实核验 + 措辞 + 本地核验 + 平台质检），不等结果。

    和 batch/precheck/start 的分工：那个只跑措辞那一道，给「我就想改改文字」用；
    这个走完整条闸门，给积压补跑用。两者都按并发额度排队，不会一起把模型打爆。
    """
    results = []
    with session() as db:
        for tid in body.ids:
            t = db.get(Task, tid)
            if t is None:
                results.append({"id": tid, "ok": False, "message": "题目不存在"})
            elif t.status not in (ANALYZED, QC):
                results.append({"id": tid, "ok": False,
                                "message": f"状态 {t.status} 不用做提交前质检"})
            else:
                results.append({"id": tid, "task_no": t.task_no})
    return {"results": [r if "ok" in r else {**r, **watchdog.queue_gate(r["id"])}
                        for r in results]}


@router.post("/batch/factcheck")
async def batch_factcheck(body: IdList) -> dict:
    """逐道串行跑事实核验。一道失败不影响后面的，各自带原因回来。

    串行的理由和批量措辞质检一样：每道题都是一次模型调用，并发发出去只会一起撞限流。
    """
    results = []
    for tid in body.ids:
        results.append({"id": tid, **await gsb_factcheck.run_factcheck(tid)})
    return {"results": results}


@router.post("/batch/precheck")
async def batch_precheck(body: IdList) -> dict:
    """逐道串行跑质检。一道失败不影响后面的，各自带原因回来。

    串行是因为每道题都是一次模型调用，并发发出去只会一起撞限流，而这一步本来就是
    收尾动作，快十分钟慢十分钟都不影响什么。
    """
    results = []
    for tid in body.ids:
        results.append({"id": tid, **await gsb_precheck.run_precheck(tid)})
    return {"results": results}


@router.post("/batch/precheck/start")
async def batch_precheck_start(body: IdList) -> dict:
    """把勾中的题排进后台质检，不等结果。页面上的「批量质检」走这里。

    已经有有效结论、正在跑、还没有理由正文的题会被剔掉并在返回里说清是哪几道 ——
    一批二十道里挡下三道，人必须当场知道是哪三道，否则他会以为整批都发了。
    """
    return gsb_precheck.start_batch(body.ids)


@router.post("/batch/precheck/stop")
async def batch_precheck_stop() -> dict:
    """叫停后台质检。手上那道跑完才停，理由见 gsb_precheck.stop_batch。"""
    return gsb_precheck.stop_batch()


@router.post("/batch/claim")
async def batch_claim(body: IdList) -> dict:
    """界面上的「全部领取并启动」。

    走 _claim 而不是调上面那个路由函数：路由的 force 形参默认值是 `Query(default=False)`，
    那是个 FieldInfo 对象，只有经过 HTTP 请求才会被 FastAPI 解析成布尔值。在 Python 里
    直接调用它，force 拿到的就是这个对象本身，而它是真值——于是批量领取会一路强制到底，
    clone 没成、门禁全红的题照样进队列。
    """
    results = []
    for tid in body.ids:
        try:
            results.append({"id": tid, **(await _claim(tid, force=False))})
        except HTTPException as exc:
            # 被别的设备抢先时 detail 是结构化的，拆出错误码让界面能单独统计一句
            # 「N 道被其他设备领走」，混在门禁未过里报会让人以为是自己这边有问题。
            #
            # 404 在这里也归到同一类：批量领取跑到一半时题目整行消失，只可能是前一道题
            # 被抢先触发的那次重投影把它一起撤掉了，而撤掉的唯一条件就是它也被别的设备
            # 领走了（见 pool_bank.sync_tasks）。
            d = exc.detail
            structured = isinstance(d, dict)
            code = d.get("code", "") if structured else ("POOL_TAKEN" if exc.status_code == 404 else "")
            results.append({"id": tid, "queued": False, "code": code,
                            "error": d.get("message", "") if structured else str(d)})
    return {"results": results}


@router.post("/batch/rerun")
async def batch_rerun(body: RerunBatch) -> dict:
    """批量重跑。一道题失败不影响后面的，各自报各自的原因。

    逐道串行：重跑要销毁容器、把工作目录重置回初始快照、归档轨迹再退回队列，全是碰磁盘
    和 docker 的活，一起发出去只会互相抢 IO，而真正的瓶颈在后面的容器槽位上。
    """
    sides = tuple(_side(s) for s in body.sides) or config.SIDES
    results = []
    for tid in body.ids:
        with session() as db:
            if db.get(Task, tid) is None:
                results.append({"id": tid, "ok": False, "message": "题目不存在"})
                continue
            # 与单题重跑同一个口径：在跑的那一侧要先停，否则容器刚被销毁、runner 还在
            # 往这一行写收尾结果，重跑建出来的新一轮会被那份旧账盖掉。
            if any(r.status == RUN_RUNNING for r in _runs(db, tid)):
                results.append({"id": tid, "ok": False, "message": "还有容器在跑，请先停止"})
                continue
        results.append({"id": tid, **await watchdog.manual_rerun(tid, sides)})
    return {"results": results}


@router.post("/batch/advance")
async def batch_advance(body: IdList) -> dict:
    """批量发起「推产物 + 分析 + 质检」。只排队，不等任何一道跑完。

    单题也走这里，不走 /{task_id}/advance：那个是同步等到质检出结果的，一道题十几
    二十分钟，界面上点一下就得干等到请求超时。理由见 watchdog.queue_advance。
    """
    results = []
    for tid in body.ids:
        with session() as db:
            t = db.get(Task, tid)
            if t is None:
                results.append({"id": tid, "ok": False, "message": "题目不存在"})
                continue
            if t.status not in (RUN_DONE, NEEDS_ATTENTION, ANALYZED, QC):
                results.append({"id": tid, "ok": False,
                                "message": f"状态 {t.status} 不能推进"})
                continue
        results.append({"id": tid, **watchdog.queue_advance(tid)})
    return {"results": results}


@router.get("/{task_id}")
async def get_task(task_id: int) -> dict:
    with session() as db:
        return task_detail(_get(db, task_id), _runs(db, task_id))


# ---------------- 领取 / 门禁 / 启动 ----------------

@router.post("/{task_id}/gate")
async def gate_check(task_id: int) -> dict:
    with session() as db:
        t = _get(db, task_id)
    return gate.summarize(await gate.run_checks(t))


@router.post("/{task_id}/claim")
async def claim(task_id: int, force: bool = Query(default=False)) -> dict:
    """领取：校验分支、clone 两侧、跑门禁，通过就建两个 run 进队列。"""
    return await _claim(task_id, force)


async def _take_remote(task_id: int) -> None:
    """在远端把这道题占下来。占不到就抛 409，并把本机列表刷成远端的样子。

    必须发生在准备工作区之前：clone 两个分支要几十秒到几分钟，等跑完再发现题被人领走了，
    这段机器时间就白烧了，磁盘上还留着一份没人要的工作区。
    """
    with session() as db:
        t = _get(db, task_id)
        entry_id, task_no = t.pool_entry_id, t.task_no
    if not entry_id:
        return      # 纯本机题（池没启用时导入的），不存在跨设备归属

    res = await pool.claim_remote(entry_id, task_no=task_no)
    if res["ok"]:
        with session() as db:
            _get(db, task_id).claimed_by = pool.device()
        return

    taken_by = res.get("taken_by", "")
    if not taken_by:
        raise HTTPException(409, detail={"code": "POOL_UNREACHABLE", "message": res["message"]})
    # 被抢先了。顺手按远端刷一遍本机题库：这道题会从待领列表里消失，界面收到
    # bank 事件后重新拉一次就是最新的，不必让人自己去点同步。
    pool_bank.sync_tasks()
    bus.publish("tasks", {"type": "bank"})
    raise HTTPException(409, detail={"code": POOL_TAKEN, "taken_by": taken_by,
                                     "task_no": task_no, "message": res["message"]})


async def _claim(task_id: int, force: bool) -> dict:
    """领取的实际动作。进程内的调用方一律走这里，见 batch_claim 的说明。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status not in (AVAILABLE, CLAIMED):
            raise HTTPException(409, f"当前状态 {t.status} 不能领取")

    await _take_remote(task_id)

    with session() as db:
        t = _get(db, task_id)
        t.status = CLAIMED
        t.claimed_at = t.claimed_at or utc_now()
        db.flush()
        snapshot = t

    prep = await gate.prepare_workspaces(snapshot)
    with session() as db:
        t = _get(db, task_id)
        t.branch_check = {"ok": prep["ok"], "message": prep["message"],
                          "at": utc_now().isoformat()}
    if not prep["ok"] and not force:
        bus.publish("tasks", {"type": "task", "id": task_id})
        return {"queued": False, "prepare": prep, "gate": None}

    report = gate.summarize(await gate.run_checks(snapshot))
    # 强制启动只放行口径类的问题。容器起不来、或者这一侧的起点不对（没 clone 成、
    # HEAD 对不上），跑出来的东西根本不成立：docker 会拿一个空目录当工作区挂进去，
    # 模型在里面自己 git init 造一个仓库，跑完还长得像一次正常的运行。
    if force and report["hard_blocked"]:
        raise HTTPException(409, "这些是强制启动也绕不过的硬前提，先修好再领取："
                                 + "；".join(report["hard_messages"][:4]))
    queued = report["passed"] or force
    if queued:
        with session() as db:
            t = _get(db, task_id)
            # 两侧的 run 一次建齐。缺一侧调度器会跳过整道题，宁可这里就建全
            have = {r.side for r in _runs(db, task_id)}
            for side in config.SIDES:
                if side not in have:
                    db.add(TaskRun(task_id=task_id, side=side,
                                   container_name=config.TaskPaths(t.task_no, side).container_name))
            t.status = QUEUED
            t.claimed_at = utc_now()
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"queued": queued, "prepare": prep, "gate": report}


@router.post("/{task_id}/release")
async def release(task_id: int) -> dict:
    """放回题库。题在远端登记过的，先撤销那边的领取再动本机状态。

    顺序不能反：先把本机改成待领取、再去撤远端，万一撤不掉，这道题在远端还记在本机名下，
    别的设备领不了，本机却已经把它摆回待领列表 —— 界面上看是可领的，实际上谁都领不走。
    """
    with session() as db:
        t = _get(db, task_id)
        if t.status not in (CLAIMED, QUEUED):
            raise HTTPException(409, "只有未开始运行的任务可以放回题库")
        entry_id, task_no = t.pool_entry_id, t.task_no

    message = ""
    if entry_id:
        res = await pool.release_remote(entry_id, task_no=task_no)
        if not res["ok"]:
            raise HTTPException(409, f"远端没能撤销领取，题仍归本机：{res['message']}")
        message = res["message"]

    with session() as db:
        t = _get(db, task_id)
        t.status = AVAILABLE
        t.claimed_at = None
        t.claimed_by = ""
        for r in _runs(db, task_id):
            db.delete(r)
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "message": message or "已放回题库"}


@router.post("/{task_id}/discard")
async def discard(task_id: int, reason: str = Query(default="人工废弃")) -> dict:
    """标记废弃：列表默认不再显示；在跑的容器一并停掉销毁，轨迹与产物留在磁盘上。

    运行中和排队中也能直接废弃。以前要求先停容器、先放回题库，是怕误操作丢掉跑了一半
    的结果；但一道题真要放弃时，多这两步只是让它继续占着容器，而槽位是这里最紧的资源。
    """
    res = await watchdog.discard_task(task_id, reason)
    if not res["ok"]:
        raise HTTPException(404, res["message"])
    return res


@router.post("/{task_id}/restore")
async def restore(task_id: int) -> dict:
    """恢复废弃的题：回到废弃前的状态，从未跑过的回到待领取。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status != DISCARDED:
            raise HTTPException(409, "只有已废弃的题可以恢复")
        back = t.discarded_from or AVAILABLE
        if back in (RUNNING, QUEUED):   # 废弃前的运行态已不存在，退回待领取
            back = AVAILABLE
        t.status = back
        t.discarded_from = ""
        t.discarded_at = None
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "status": back, "message": f"已恢复为 {back}"}


@router.post("/{task_id}/fix/{action}")
async def gate_fix(task_id: int, action: str) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.status in (RUNNING, QUEUED):
            raise HTTPException(409, "运行中或排队中不能执行修复")
        task_no, repo_url, snapshot = t.task_no, t.repo_url, gsb_repo.snapshot_sha(t.env_snapshot)
        detached = t

    if action == "clone_sides":
        return await gate.prepare_workspaces(detached)
    if action == "reset_sides":
        if not snapshot:
            return {"ok": False, "message": "初始快照缺少 40 位 SHA，无法重置"}
        out = {s: await gsb_repo.reset_side(task_no, s, snapshot) for s in config.SIDES}
        return {"ok": all(r.get("ok") for r in out.values()),
                "message": "；".join(f"{s}: {r.get('message')}" for s, r in out.items())}
    if action == "archive_traces":
        out = {s: watchdog.archive_traces(task_no, s) for s in config.SIDES}
        return {"ok": all(r["ok"] for r in out.values()),
                "message": "；".join(f"{s}: {r['message']}" for s, r in out.items())}
    if action == "remove_containers":
        r = await dockerx.remove_task_containers(task_no)
        with session() as db:
            for run in _runs(db, task_id):
                run.container_exists = False
        return {"ok": r.ok, "message": r.err.strip() or "两侧容器已删除"}
    raise HTTPException(404, "未知修复动作")


@router.post("/{task_id}/stop")
async def stop(task_id: int, side: str = Query(default="")) -> dict:
    """停止容器。不给 side 就把两侧都停了。"""
    with session() as db:
        _get(db, task_id)
        runs = [r for r in _runs(db, task_id)
                if not side or r.side == _side(side)]
        ids = [r.id for r in runs if r.status == RUN_RUNNING]
    if not ids:
        return {"ok": False, "message": "没有正在运行的容器"}
    out = [await runner.stop_run(rid) for rid in ids]
    return {"ok": all(r["ok"] for r in out),
            "message": "；".join(r["message"] for r in out)}


@router.post("/{task_id}/rerun")
async def rerun(task_id: int, body: RerunRequest) -> dict:
    """人工重跑。与自动重跑走同一套动作，区别是不看次数上限并把计数清零。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status == RUNNING and any(r.status == RUN_RUNNING for r in _runs(db, task_id)):
            raise HTTPException(409, "还有容器在跑，请先停止")
    sides = tuple(_side(s) for s in body.sides) or config.SIDES
    res = await watchdog.manual_rerun(task_id, sides)
    if not res["ok"]:
        raise HTTPException(400, res["message"])
    return res


# ---------------- 容器实时 ----------------

def _run_side_map(db, task_id: int) -> dict[str, TaskRun]:  # noqa: ANN001
    return {r.side: r for r in _runs(db, task_id)}


def _container_name(task: Task, side: str, run: TaskRun | None) -> str:
    """这一侧的容器名。run 上有就用它，没有就按命名规则算，好让还没建 run 的题也能查。"""
    return (run.container_name if run and run.container_name
            else config.TaskPaths(task.task_no, side).container_name)


@router.get("/{task_id}/containers")
async def task_containers(task_id: int) -> dict:
    """两侧容器此刻的真实样子：状态、退出码、资源占用、容器里的进程、最后一次出声的时刻。

    详情页上「两侧运行」里的那些数字是收尾时记下来的账，跑着的时候那份账还不存在，
    所以只能现问 docker。其中 silent_seconds（离最后一行日志过了多久）是最要紧的一个：
    事件采集一断，界面上就再没有别的东西能区分「模型还在干活」和「容器早就卡住了」。
    """
    with session() as db:
        t = _get(db, task_id)
        by_side = _run_side_map(db, task_id)
        wanted = [(s, _container_name(t, s, by_side.get(s)),
                   by_side[s].status if s in by_side else "")
                  for s in config.SIDES]

    snaps = await asyncio.gather(*(dockerx.container_snapshot(name) for _, name, _ in wanted))
    live = [name for (_, name, _), snap in zip(wanted, snaps) if snap.get("running")]
    # 日志尾行对已经退出的容器也要取：那一行的时刻就是它最后一次出声，
    # 跟退出时间一比就知道是干完活退的，还是半路没了声音。
    have = [name for (_, name, _), snap in zip(wanted, snaps) if snap.get("exists")]
    stats, tops = {}, {}
    if live:
        # stats 一次问两个（--no-stream 要采样，一个一个来要等两倍时间）
        stats = await dockerx.container_stats(live)
        tops = dict(zip(live, await asyncio.gather(*(dockerx.container_top(n) for n in live))))
    tails = dict(zip(have, await asyncio.gather(*(dockerx.last_log_line(n) for n in have))))

    # docker 用零值时间表示「还没发生」，直接给前端会算出一个两千年的时长
    def _time(v: str) -> str | None:
        return v if v and not v.startswith("0001-01-01") else None

    now = utc_now()
    items = []
    for (side, name, run_status), snap in zip(wanted, snaps):
        procs = tops.get(name) or []
        last_raw = tails.get(name) or ""
        last_ts, last_text = runner.split_log_ts(last_raw) if last_raw else (None, "")
        items.append({
            "side": side, "name": name, "run_status": run_status,
            "exists": bool(snap.get("exists")), "status": snap.get("status", ""),
            "running": bool(snap.get("running")), "exit_code": snap.get("exit_code"),
            "started_at": _time(snap.get("started_at") or ""),
            "finished_at": _time(snap.get("finished_at") or ""),
            "oom_killed": bool(snap.get("oom_killed")), "error": snap.get("error", ""),
            "image": snap.get("image", ""),
            **(stats.get(name) or {"cpu": "", "mem": "", "mem_perc": ""}),
            "processes": procs,
            # 容器里那个 claude 进程还在，就说明模型仍在工作，哪怕事件流已经不动了
            "claude_alive": any("claude" in (p.get("cmd") or "") for p in procs),
            "last_log_at": last_ts.isoformat() if last_ts else None,
            "silent_seconds": round((now - last_ts).total_seconds()) if last_ts else None,
            "last_log": last_text[:400],
        })
    return {"items": items, "at": now.isoformat()}


# 日志流的心跳间隔。容器可能几分钟不出声，中间什么都不发的话，
# 代理和浏览器都会把这条连接当成断了。
LOG_PING_SECONDS = 15


@router.get("/{task_id}/container/logs")
async def container_logs(task_id: int, side: str = Query(...),
                         tail: int = Query(default=200, ge=1, le=2000)) -> StreamingResponse:
    """把容器的原始 stdout 实时推给界面上的终端。

    走的是 `docker logs -f`，跟事件流不是一回事：事件流是解析、过滤、落库之后的结果，
    噪声事件（每个 token 一条的 thinking）被丢掉了，采集断了就什么也没有；
    这里给的是容器此刻真正在往外写的每一行，用来确认「它到底还在不在动」。
    """
    want = _side(side)
    with session() as db:
        t = _get(db, task_id)
        name = _container_name(t, want, _run_side_map(db, task_id).get(want))

    snap = await dockerx.container_snapshot(name)
    if not snap.get("exists"):
        raise HTTPException(404, f"容器 {name} 不在了（已销毁或还没启动），没有日志可看")

    async def gen():
        # 有界队列顺带做背压：容器刷得比浏览器收得快时，读日志那侧自己会等
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)

        async def pump() -> None:
            try:
                async for line in dockerx.stream_container_logs(name, tail=tail):
                    await q.put({"type": "line", "text": line})
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                await q.put({"type": "error", "message": f"读容器日志失败：{exc}"})
            await q.put({"type": "eof", "message": "日志流结束（容器已退出或被销毁）"})

        pumping = asyncio.create_task(pump())
        yield sse_format({"type": "hello", "container": name, "state": snap.get("status", ""),
                          "running": bool(snap.get("running")), "tail": tail})
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=LOG_PING_SECONDS)
                except asyncio.TimeoutError:
                    yield sse_format({"type": "ping"})
                    continue
                yield sse_format(item)
                if item["type"] == "eof":
                    break
        finally:
            pumping.cancel()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.websocket("/{task_id}/container/exec")
async def container_exec(ws: WebSocket, task_id: int, side: str = Query(default="A"),
                         rows: int = Query(default=dockerx.PTY_ROWS, ge=4, le=400),
                         cols: int = Query(default=dockerx.PTY_COLS, ge=20, le=600)) -> None:
    """页面上那个终端的另一端：容器里一个真正的 shell。

    跟隔壁 /container/logs 分工清楚：那边是 `docker logs -f` 的只读回放，只能看着
    stream-json 往下滚；这里是 `docker exec -it` 接在伪终端上的双向通道，能敲命令、
    有颜色和光标，vim、top、git log 这类认终端的程序都照常用。要确认模型此刻把工作区
    改成了什么样，只有进去用 git status 亲眼看一遍才算数。

    容器名一律由 task_id + side 推算，不接受调用方传。这个接口能在容器里执行任意命令，
    容器名一旦可以由参数指定，等于把宿主机上所有容器都对外开放了。
    """
    await ws.accept()

    async def bye(message: str) -> None:
        # 先握手再报错，不在握手阶段拒：WebSocket 握手失败浏览器只给一个
        # 「连接失败」，页面上就无从分辨是容器没了、题没跑，还是后端挂了
        with suppress(Exception):
            await ws.send_json({"type": "exit", "message": message})
            await ws.close()

    want = (side or "").upper()
    if want not in config.SIDES:
        await bye("side 必须是 A 或 B")
        return
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            await bye("任务不存在")
            return
        name = _container_name(t, want, _run_side_map(db, task_id).get(want))

    snap = await dockerx.container_snapshot(name)
    if not snap.get("exists"):
        await bye(f"容器 {name} 不在了（还没启动，或两侧跑完推完产物后已自动销毁），开不了终端")
        return
    if not snap.get("running"):
        await bye(f"容器 {name} 已经退出（{snap.get('status') or '状态未知'}）。"
                  f"停掉的容器进不去，它留下的东西请在工作区目录里翻")
        return

    try:
        term = await dockerx.pty_shell(
            name, rows=rows, cols=cols, workdir=config.CONTAINER_WORKSPACE,
            env={"TERM": "xterm-256color", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
    except Exception as exc:  # noqa: BLE001
        await bye(f"开终端失败：{exc}")
        return

    await ws.send_json({"type": "hello", "container": name, "side": want,
                        "cwd": config.CONTAINER_WORKSPACE})
    # 按块读会把一个多字节字符切成两半，攒着等下一块再拼。少了这一步，容器里的中文
    # 输出会每隔一段冒出一个替换字符，而且恰好在刷屏最快的时候最密。
    decoder = codecs.getincrementaldecoder("utf-8")("replace")

    async def to_browser() -> None:
        while (chunk := await term.read()) is not None:
            text = decoder.decode(chunk)
            if text:
                await ws.send_json({"type": "stdout", "data": text})

    async def to_container() -> None:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            kind = msg.get("type")
            if kind == "stdin":
                await term.write(str(msg.get("data") or "").encode("utf-8"))
            elif kind == "resize":
                term.resize(int(msg.get("rows") or rows), int(msg.get("cols") or cols))

    pumps = [asyncio.create_task(to_browser()), asyncio.create_task(to_container())]
    try:
        # 谁先结束都收摊：浏览器关页面（到不了 to_container 的下一轮）、
        # 容器里 exit（to_browser 读到 None）、容器被销毁，三种情况都走这里
        done, pending = await asyncio.wait(pumps, return_when=asyncio.FIRST_COMPLETED)
        for p in pending:
            p.cancel()
        for p in done:
            # 取一次异常，别让它变成没人认领的 Task 警告；浏览器断连本身不是错
            exc = p.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                log.info("容器终端 %s 结束：%r", name, exc)
    finally:
        await term.close()
        with suppress(Exception):
            await ws.send_json({"type": "exit", "message": f"终端已退出（容器 {name} 仍在运行）"})
            await ws.close()


# ---------------- 事件流 ----------------

REPLAY_LIMIT = 600      # 回放上限：一次运行可能几万条事件，全推过去浏览器会卡死


def _event_row(e: RunEvent) -> dict:
    # type 是 SSE 的分发标记，前端靠它区分事件与状态消息，缺了事件流会整段丢掉
    return {"type": "event", "seq": e.seq, "side": e.side or "A", "kind": e.kind,
            "summary": e.summary, "ts": e.ts.isoformat() if e.ts else None, "payload": e.payload}


def _load_events(db, task_id: int, limit: int, side: str = "") -> tuple[list[dict], int]:  # noqa: ANN001
    """取最后 limit 条，按 seq 升序返回，另给出总条数。"""
    where = [RunEvent.task_id == task_id]
    if side:
        where.append(RunEvent.side == side)
    total = db.execute(select(func.count()).select_from(RunEvent).where(*where)).scalar() or 0
    rows = db.execute(
        select(RunEvent).where(*where).order_by(RunEvent.seq.desc()).limit(limit)
    ).scalars().all()
    return [_event_row(e) for e in reversed(rows)], int(total)


@router.get("/{task_id}/events")
async def task_events(task_id: int, replay: bool = Query(default=True),
                      side: str = Query(default=""),
                      limit: int = Query(default=REPLAY_LIMIT, ge=1, le=5000)) -> StreamingResponse:
    want = _side(side) if side else ""
    with session() as db:
        _get(db, task_id)
        history, total = ([], 0) if not replay else _load_events(db, task_id, limit, want)

    async def gen():
        if total > len(history):
            yield sse_format({"type": "truncated", "total": total, "shown": len(history)})
        for h in history:
            yield sse_format(h)
        yield sse_format({"type": "replay_done", "count": len(history), "total": total})
        async for item in bus.subscribe(f"run:{task_id}"):
            # 只订阅一侧时，另一侧的实时事件不要混进来
            if want and item.get("side") and item["side"] != want:
                continue
            yield sse_format(item)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{task_id}/events/list")
async def task_events_list(task_id: int, side: str = Query(default=""),
                           limit: int = Query(default=1000, ge=1, le=5000)) -> dict:
    want = _side(side) if side else ""
    with session() as db:
        _get(db, task_id)
        items, total = _load_events(db, task_id, limit, want)
        return {"items": items, "total": total, "truncated": total > len(items)}


# ---------------- 轨迹 ----------------

@router.get("/{task_id}/trace")
async def download_trace(task_id: int, side: str = Query(...)) -> FileResponse:
    want = _side(side)
    with session() as db:
        _get(db, task_id)
        run = next((r for r in _runs(db, task_id) if r.side == want), None)
        path = run.trace_file if run else ""
    if not path or not Path(path).exists():
        raise HTTPException(404, f"{want} 侧的轨迹文件不存在")
    return FileResponse(path, filename=Path(path).name, media_type="application/x-ndjson")


@router.get("/{task_id}/trace-index")
async def trace_index(task_id: int, side: str = Query(...)) -> dict:
    want = _side(side)
    with session() as db:
        t = _get(db, task_id)
        paths = config.TaskPaths(t.task_no, want)
    if paths.trace_index.exists():
        import json

        try:
            return json.loads(paths.trace_index.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    tf = trace.find_trace_file(paths.traces)
    if not tf:
        raise HTTPException(404, f"{want} 侧还没有轨迹")
    summary = trace.parse_trace(tf)
    paths.analysis.mkdir(parents=True, exist_ok=True)
    trace.write_index(summary, paths.trace_index)
    return summary


# ---------------- GSB 分析与结论 ----------------

@router.post("/{task_id}/analyze")
async def analyze(task_id: int) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.analysis_status == ANALYSIS_RUNNING:
            raise HTTPException(409, "分析正在进行")
        runs = _runs(db, task_id)
        unfinished = [r.side for r in runs if r.status != "FINISHED"]
        if len(runs) != 2 or unfinished:
            raise HTTPException(409, f"两侧都跑完才能对比，{'、'.join(unfinished) or '缺少运行记录'}")
    asyncio.create_task(gsb_analyzer.analyze_task(task_id))
    return {"ok": True, "message": "GSB 对比已启动"}


@router.post("/{task_id}/advance")
async def advance(task_id: int) -> dict:
    """手动走一遍「推产物 + 开分析」。正常由巡检自动触发，这里给推送失败后重试用。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status not in (RUN_DONE, NEEDS_ATTENTION, ANALYZED, QC):
            raise HTTPException(409, f"状态 {t.status} 不能推进")
    return await watchdog.advance_pair(task_id)


@router.put("/{task_id}/gsb")
async def save_gsb(task_id: int, body: GsbUpdate) -> dict:
    with session() as db:
        t = _get(db, task_id)
        if t.status in (UPLOADED, DONE):
            raise HTTPException(409, "已上传的数据不可再编辑")
        gsb = dict(t.gsb)
        if body.verdict:
            if body.verdict not in gsb_analyzer.VERDICTS:
                raise HTTPException(400, f"结论必须是 {'、'.join(gsb_analyzer.VERDICTS)} 之一")
            gsb["verdict"] = body.verdict
        gsb["reason"] = body.reason.strip()
        if body.a_startup is not None:
            gsb["a_startup"] = body.a_startup
        if body.b_startup is not None:
            gsb["b_startup"] = body.b_startup
        if body.validity:
            gsb["validity"] = body.validity
        gsb["remark"] = body.remark.strip()
        t.gsb = gsb
    report = await gsb_verifier.run_verify(task_id)
    with session() as db:
        return {"verify": report, "task": task_brief(_get(db, task_id), _runs(db, task_id))}


@router.post("/{task_id}/verify")
async def verify(task_id: int) -> dict:
    with session() as db:
        _get(db, task_id)
    return await gsb_verifier.run_verify(task_id)


# ---------------- 录屏 ----------------

@router.put("/{task_id}/screencast")
async def save_screencast(task_id: int, body: ScreencastUpdate) -> dict:
    """填两侧录屏链接。这是提交前唯一必须人工给的东西。

    录屏不再决定题落在哪一栏 —— 那由两道质检决定，质检放行了才轮到录屏。但它决定
    提交门禁开不开（见 gsb_precheck.submit_block），所以填完仍要过一遍阶段投影把
    状态对齐，别让某个动作各写各的。
    """
    with session() as db:
        t = _get(db, task_id)
        if t.status in (UPLOADED, DONE):
            raise HTTPException(409, "已上传的数据不可再编辑")
        sc = dict(t.screencast)
        for side, url in (("A", body.A), ("B", body.B)):
            if url is not None:
                sc[side] = url.strip()
        t.screencast = sc
        gsb_precheck.sync_stage(db, t)
    report = await gsb_verifier.run_verify(task_id)
    with session() as db:
        return {"verify": report, "task": task_brief(_get(db, task_id), _runs(db, task_id))}


@router.post("/{task_id}/screencast/upload")
async def upload_screencast(task_id: int, side: str = Query(...),
                            path: str = Query(...)) -> dict:
    """把本地录屏文件收进题目目录并代传到平台，换回一个链接。"""
    want = _side(side)
    with session() as db:
        _get(db, task_id)
    res = await gsb_uploader.upload_screencast(task_id, want, Path(path).expanduser())
    if not res["ok"]:
        raise HTTPException(400, res["message"])
    return res


@router.post("/{task_id}/screencast/deliver")
async def deliver_screencast(task_id: int, body: ScreencastDeliver) -> dict:
    """交付录屏并提交：给两侧的本地视频路径，收下、代传、直接交到平台。

    整条流水线到这里只剩一个人工动作。分侧调接口再调一次提交也能做到同样的事，
    但那是把三步机械操作留给人，而这三步之间没有任何需要人判断的地方。

    提交被门禁挡住不算失败：录屏确实收下了，挡的是别的（质检没过、状态不对），
    那句话原样带回去，人看一眼就知道还差什么。
    """
    with session() as db:
        t = _get(db, task_id)
        if t.status in (UPLOADED, DONE):
            raise HTTPException(409, "已上传的数据不可再编辑")
    if not (body.A or body.B):
        raise HTTPException(400, "至少要给一侧的录屏文件路径")
    res = await gsb_uploader.deliver_screencasts(
        task_id, {"A": body.A, "B": body.B}, submit=body.submit)
    if not res["ok"]:
        raise HTTPException(400, res["message"])
    with session() as db:
        return {**res, "task": task_brief(_get(db, task_id), _runs(db, task_id))}


# ---------------- 提交前质检：单题与人工确认 ----------------
# 两道分开发起。合成一个「跑质检」按钮看着省事，但它们的失败含义不一样：事实核验
# 报的是说错了，措辞质检报的是说得生硬，人重跑哪一道取决于他刚改了什么。

@router.post("/{task_id}/factcheck")
async def factcheck(task_id: int) -> dict:
    """对一道题跑事实核验：拿轨迹里的执行记录去对理由，不符处直接订正。"""
    with session() as db:
        _get(db, task_id)
    res = await gsb_factcheck.run_factcheck(task_id)
    if not res.get("ok"):
        raise HTTPException(409, res["message"])
    return res


@router.post("/{task_id}/factcheck/confirm")
async def factcheck_confirm(task_id: int, body: PrecheckConfirm) -> dict:
    """人工放行事实核验。模型报的不符里总有它自己读偏的，人看一眼直接放行。"""
    with session() as db:
        _get(db, task_id)
    res = gsb_factcheck.confirm(task_id, body.note)
    if not res["ok"]:
        raise HTTPException(409, res["message"])
    with session() as db:
        return {**res, "task": task_brief(_get(db, task_id), _runs(db, task_id))}


@router.post("/{task_id}/precheck")
async def precheck(task_id: int) -> dict:
    """对一道题跑措辞质检，跑完才返回（一道一分半，页面上转个圈等得起）。"""
    with session() as db:
        _get(db, task_id)
    res = await gsb_precheck.run_precheck(task_id)
    if not res.get("ok"):
        raise HTTPException(409, res["message"])
    return res


@router.post("/{task_id}/precheck/confirm")
async def precheck_confirm(task_id: int, body: PrecheckConfirm) -> dict:
    """人工放行质检。这是这条流程里唯一允许在界面上做的动作，理由见 gsb_precheck.confirm。"""
    with session() as db:
        _get(db, task_id)
    res = gsb_precheck.confirm(task_id, body.note)
    if not res["ok"]:
        raise HTTPException(409, res["message"])
    with session() as db:
        return {**res, "task": task_brief(_get(db, task_id), _runs(db, task_id))}


@router.post("/{task_id}/quality-gate")
async def quality_gate(task_id: int) -> dict:
    """把两道质检连着本地核验、平台质检整条走一遍。

    正常由巡检自动跑，这里给「改完理由想立刻看整条结论」用。顺序和自动路径完全
    一致（见 watchdog.run_quality_gate），不另起一套，否则手动跑出来的结论和
    自动跑出来的会不一样，而两者都说自己是对的。
    """
    with session() as db:
        t = _get(db, task_id)
        if t.status not in (ANALYZED, QC):
            raise HTTPException(409, f"状态 {t.status} 不用做提交前质检")
    return await watchdog.run_quality_gate(task_id)


# ---------------- 队列顺序 ----------------

@router.post("/{task_id}/queue/move")
async def queue_move(task_id: int, body: QueueMove) -> dict:
    """调整排队顺序。priority 越小越先出队，同值按领取时间。"""
    with session() as db:
        t = _get(db, task_id)
        if t.status != QUEUED:
            raise HTTPException(409, "只有排队中的题可以调整顺序")
        others = db.execute(
            select(Task).where(Task.status == QUEUED, Task.id != task_id)
        ).scalars().all()
        lo = min([o.priority for o in others], default=0)
        hi = max([o.priority for o in others], default=0)
        if body.priority is not None:
            t.priority = int(body.priority)
        elif body.direction == "top":
            t.priority = lo - 1
        elif body.direction == "bottom":
            t.priority = hi + 1
        elif body.direction == "up":
            t.priority -= 1
        elif body.direction == "down":
            t.priority += 1
        else:
            raise HTTPException(400, "direction 需为 top/up/down/bottom")
        new_priority = t.priority
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "priority": new_priority}


# ---------------- 上传 ----------------

@router.post("/{task_id}/upload")
async def upload(task_id: int) -> dict:
    res = await gsb_uploader.upload_task(task_id)
    if not res.get("ok"):
        raise HTTPException(400 if not res.get("auth_error") else 401, detail=res)
    return res


# ---------------- 完成并销毁 ----------------

@router.post("/{task_id}/complete")
async def complete(task_id: int, force: bool = Query(default=False)) -> dict:
    with session() as db:
        t = _get(db, task_id)
        runs = _runs(db, task_id)
        if any(r.status == RUN_RUNNING for r in runs):
            raise HTTPException(409, "还有容器在跑，请先停止")
        if t.status not in (RUN_DONE, ANALYZED, QC, UPLOADED, NEEDS_ATTENTION):
            raise HTTPException(409, f"状态 {t.status} 不能标记完成")
        if not force and t.status != UPLOADED:
            raise HTTPException(409, "尚未上传，若确认放弃该题请带 force=true")
        missing = [r.side for r in runs if not (r.trace_file and Path(r.trace_file).exists())]
        if missing and not force:
            raise HTTPException(409, f"{'、'.join(missing)} 侧轨迹尚未导出，销毁会丢失数据；"
                                     f"确认请带 force=true")
        task_no = t.task_no
    r = await dockerx.remove_task_containers(task_no)
    with session() as db:
        t = _get(db, task_id)
        for run in _runs(db, task_id):
            run.container_exists = False
        t.status = DONE
        t.done_at = utc_now()
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "container_removed": r.ok, "message": r.err.strip() or "两侧容器已销毁"}


@router.post("/{task_id}/destroy-container")
async def destroy_container(task_id: int) -> dict:
    """只销毁容器、不改任务状态（用于异常态清理）。"""
    with session() as db:
        t = _get(db, task_id)
        if any(r.status == RUN_RUNNING for r in _runs(db, task_id)):
            raise HTTPException(409, "还有容器在跑，请先停止")
        task_no = t.task_no
    r = await dockerx.remove_task_containers(task_no)
    with session() as db:
        for run in _runs(db, task_id):
            run.container_exists = False
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": r.ok, "message": r.err.strip() or "容器已销毁"}
