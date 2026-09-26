"""录屏协作的编排：待录屏 → 生成文档 → 发布 → 录屏端认领、回传 → 收回 → 可上传。

两端共用这一个模块，按角色走不同的分支：

出题端（默认）
  巡检每轮调 kick()，后台跑一次 scan()：
  1. 拉录屏仓库 main，折叠出每道题此刻的状态；
  2. 本机的题录好了（recorded）就把视频拉回来，走现有 upload_screencast 收进题目目录、
     代传平台、写链接，写 collected；阶段投影随即把题推到 READY；
  3. 本机的题离开待录屏（废弃、提交、理由被改退回待质检）就写 withdrawn，文档作废；
     已提交或废弃的顺手删掉分支；
  4. 按额度给待录屏、还没有有效文档的题起生成任务。

录屏端（rec.recorder_only）
  不跑 scan 的 2～4 步，只在页面上认领、看文档、回传视频。出题端自己也能在页面上认领
  自己的题来录，两种角色的差别只在自动化开不开。

题上的 recording 字段记本机视角的进度：
  {"state": generating|failed|published|collected|withdrawn, "digest", "stage", "note",
   "fails", "error", "rounds", "model", "published_at", "collected_at", "branch_deleted"}
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app import config
from app.db import session
from app.events import bus
from app.models import DISCARDED, DONE, QC, READY, UPLOADED, Task, as_utc, utc_now
from app.services import gsb_precheck, gsb_uploader, rec_repo, rec_report, settings_store

log = logging.getLogger("solo-cli.rec")

GENERATING = "generating"
GEN_FAILED = "failed"
PUBLISHED = "published"
COLLECTED = "collected"
WITHDRAWN = "withdrawn"

GEN_AUTO_RETRIES = 2          # 自动生成失败后再试几次
GEN_RETRY_GAP_S = 1800        # 两次自动重试之间至少隔多久
COLLECT_RETRY_GAP_S = 300     # 收视频失败（多半是平台代传失败）之后隔多久再试
FINAL = frozenset({UPLOADED, DONE, DISCARDED})

_gen_jobs: dict[int, asyncio.Task] = {}
_collect_jobs: dict[int, asyncio.Task] = {}
_scan_task: asyncio.Task | None = None
_last_scan: dict = {}


# ---------------- 口径 ----------------

def max_parallel() -> int:
    return max(1, settings_store.get_int("rec.max_parallel", 2))


def auto_generate() -> bool:
    return settings_store.get_bool("rec.auto_generate", True)


def producer_active() -> bool:
    ok, _ = rec_repo.available()
    return ok and not rec_repo.recorder_only()


def current_digest(task: Task) -> str:
    """这一稿理由的指纹。文档里的「预期看到什么」是照着理由写的，理由一改文档就得重写。"""
    return gsb_precheck.reason_digest((task.gsb or {}).get("reason") or "")


def _age(stamp: str) -> float:
    """距 stamp 多少秒。没记时间当作很久以前：重启时清掉的失败时刻不该再卡冷却期。"""
    try:
        return (utc_now() - as_utc(datetime.fromisoformat(stamp))).total_seconds()
    except (TypeError, ValueError):
        return float("inf")


def needs_generation(task: Task) -> str:
    """这道题该不该（重新）生成文档。返回原因，空串表示不用。"""
    if task.status != QC or not gsb_precheck.missing_screencast(task):
        return ""
    if task.id in _gen_jobs:
        return ""
    rec = task.recording or {}
    if rec.get("wanted"):
        return "手动排队，等生成额度"
    state = rec.get("state")
    same = rec.get("digest") == current_digest(task)
    if state in (PUBLISHED, COLLECTED) and same:
        return ""
    if state == GEN_FAILED and same:
        if int(rec.get("fails") or 0) > GEN_AUTO_RETRIES:
            return ""
        if _age(rec.get("failed_at") or "") < GEN_RETRY_GAP_S:
            return ""
        return "上次生成失败，自动重试"
    if state in (PUBLISHED, COLLECTED, GEN_FAILED):
        return "理由改过，文档要照新稿重写"
    return "进了待录屏，还没有录屏文档"


def _update(task_id: int, **fields) -> dict:
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {}
        rec = {**(task.recording or {}), **fields}
        task.recording = rec
    bus.publish("tasks", {"type": "task", "id": task_id})
    return rec


# ---------------- 生成与发布 ----------------

def start_generate(task_id: int, *, force: bool = False) -> dict:
    """起一个生成任务。force 跳过额度（人在页面上点的）。"""
    if task_id in _gen_jobs:
        return {"ok": False, "message": "这道题的文档正在生成"}
    ok, why = rec_repo.available()
    if not ok:
        return {"ok": False, "message": why}
    if missing := rec_report.preflight():
        return {"ok": False, "message": "；".join(missing)}
    if not force and len(_gen_jobs) >= max_parallel():
        return {"ok": False, "message": f"已有 {len(_gen_jobs)} 道在生成，额度 {max_parallel()}"}
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        if task.status != QC:
            return {"ok": False, "message": f"只有待录屏的题能生成录屏文档（当前 {task.status}）"}
    _update(task_id, state=GENERATING, stage="queued", note="排队", error="", wanted=False,
            started_at=utc_now().isoformat())
    job = asyncio.create_task(_generate(task_id), name=f"rec-gen-{task_id}")
    _gen_jobs[task_id] = job
    job.add_done_callback(lambda _: _gen_jobs.pop(task_id, None))
    return {"ok": True, "message": "已开始生成录屏文档"}


def queue_generate(task_ids: list[int]) -> list[dict]:
    """批量生成：额度内的当场开跑，其余打上手动排队标记，由巡检按额度接着起。

    不像单题那样跳过额度：一次勾几十道全部同时调模型，账单和限流都扛不住。
    手动排队不受「自动生成」开关、失败冷却、文档已是最新这几条限制 —— 人点了就是要重写。
    """
    ok, why = rec_repo.available()
    if not ok:
        return [{"id": tid, "ok": False, "message": why} for tid in task_ids]
    results = []
    for tid in task_ids:
        with session() as db:
            task = db.get(Task, tid)
            if task is None:
                results.append({"id": tid, "ok": False, "message": "题目不存在"})
                continue
            if task.status != QC:
                results.append({"id": tid, "ok": False, "task_no": task.task_no,
                                "message": f"只有待录屏的题能生成（当前 {task.status}）"})
                continue
            no = task.task_no
        if tid in _gen_jobs:
            results.append({"id": tid, "ok": True, "task_no": no, "message": "已在生成"})
            continue
        if len(_gen_jobs) < max_parallel():
            res = start_generate(tid)
            results.append({"id": tid, "task_no": no, **res})
            continue
        _update(tid, wanted=True, note="手动排队")
        results.append({"id": tid, "ok": True, "task_no": no, "message": "额度已满，排队等巡检接着跑"})
    return results


async def batch(action: str, keys: list) -> list[dict]:
    """逐条跑同一个动作。认领、放回、撤回都要推仓库，串行跑，避免自己和自己抢推送。"""
    out = []
    for k in keys:
        if action == "withdraw":
            res = await withdraw_task(int(k))
        elif action == "claim":
            res = await claim(str(k))
            res = {"ok": res["ok"], "message": "已认领" if res["ok"] else res["message"]}
        elif action == "release":
            res = await release(str(k))
        else:
            res = {"ok": False, "message": f"不认识的动作 {action}"}
        out.append({"key": k, **res})
    return out


async def _generate(task_id: int) -> None:
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return
        task_no, digest = task.task_no, current_digest(task)
        gsb, repo_url = dict(task.gsb or {}), (task.repo_url or "").rstrip("/")
        title = f"{task.question_type or ''} · {task.difficulty or ''}".strip(" ·")

    def progress(stage: str, note: str) -> None:
        _update(task_id, stage=stage, note=note)

    owner = rec_repo.device()
    try:
        report = await rec_report.generate(task_no, progress=progress)
        md = rec_report.render(report.fragment, task_no=task_no, owner=owner, digest=digest)
        local = config.TaskPaths(task_no).analysis / "screencast-report.md"
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(md, encoding="utf-8")
        kind_label = str(report.material.get("kind_label") or "")
        meta = {"task_no": task_no, "owner": owner, "digest": digest, "repo_url": repo_url,
                "title": title, "kind_label": kind_label, "verdict": gsb.get("verdict") or "",
                "generated_at": utc_now().isoformat(), "model": report.model, "rounds": report.rounds}
        progress("publish", "推到录屏仓库")
        pub = await rec_repo.publish_branch(owner, task_no, {
            rec_repo.REPORT_FILE: md,
            rec_repo.META_FILE: json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        })
        if not pub["ok"]:
            raise rec_report.ReportError(pub["message"])
        ev = rec_repo.event(rec_repo.PUBLISHED, owner, task_no, digest=digest, title=title,
                            kind_label=kind_label, verdict=meta["verdict"], repo_url=repo_url)
        res = await rec_repo.append([ev], subject=f"publish {task_no}")
        if not res["ok"]:
            raise rec_report.ReportError(res["message"])
    except Exception as exc:  # noqa: BLE001
        with session() as db:
            task = db.get(Task, task_id)
            fails = int(((task.recording if task else {}) or {}).get("fails") or 0) + 1
        log.warning("录屏文档 %s 生成失败（第 %d 次）：%s", task_no, fails, exc)
        _update(task_id, state=GEN_FAILED, stage="", note="", fails=fails,
                failed_at=utc_now().isoformat(), error=str(exc)[:800], digest=digest)
        return
    log.info("录屏文档 %s 已发布（%d 稿通过校验）", task_no, report.rounds)
    _update(task_id, state=PUBLISHED, stage="", note="", digest=digest, fails=0, error="",
            rounds=report.rounds, model=report.model, kind_label=kind_label,
            published_at=utc_now().isoformat(), branch_deleted=False,
            collect_error="", collected_at="")


# ---------------- 收回视频 ----------------

def _start_collect(task_id: int, entry: rec_repo.Entry) -> None:
    if task_id in _collect_jobs:
        return
    job = asyncio.create_task(_collect(task_id, entry), name=f"rec-collect-{task_id}")
    _collect_jobs[task_id] = job
    job.add_done_callback(lambda _: _collect_jobs.pop(task_id, None))


def _video_names(entry: rec_repo.Entry) -> dict[str, str]:
    for ev in reversed(entry.history):
        if ev.get("type") == rec_repo.RECORDED and ev.get("digest") in ("", None, entry.digest):
            files = ev.get("files") or {}
            if all(files.get(s) for s in config.SIDES):
                return {s: str(files[s]) for s in config.SIDES}
    return {s: f"{s}.mp4" for s in config.SIDES}


async def _collect(task_id: int, entry: rec_repo.Entry) -> None:
    names = _video_names(entry)
    with tempfile.TemporaryDirectory(dir=rec_repo.scratch_dir(), prefix="collect-") as tmp:
        got = await rec_repo.fetch_files(entry.owner, entry.task_no, list(names.values()), Path(tmp))
        if not got["ok"]:
            _update(task_id, collect_error=got["message"], collect_failed_at=utc_now().isoformat())
            return
        for side, name in names.items():
            res = await gsb_uploader.upload_screencast(task_id, side, Path(tmp) / name)
            if not res["ok"]:
                _update(task_id, collect_error=f"{side} 侧：{res['message']}",
                        collect_failed_at=utc_now().isoformat())
                return
    ev = rec_repo.event(rec_repo.COLLECTED, entry.owner, entry.task_no, digest=entry.digest)
    await rec_repo.append([ev], subject=f"collect {entry.task_no}")
    _update(task_id, state=COLLECTED, collected_at=utc_now().isoformat(), collect_error="",
            recorded_by=entry.recorded_by)
    log.info("录屏 %s 已收回（%s 录制），两侧已代传平台", entry.task_no, entry.recorded_by)


# ---------------- 巡检 ----------------

def kick() -> bool:
    """巡检每轮调一次。上一轮还没跑完就跳过：拉仓库、代传视频都可能慢。"""
    global _scan_task
    if not producer_active():
        return False
    if _scan_task is not None and not _scan_task.done():
        return False
    _scan_task = asyncio.create_task(_scan_safe(), name="rec-scan")
    return True


async def _scan_safe() -> None:
    try:
        await scan()
    except Exception:  # noqa: BLE001
        log.exception("录屏协作巡检失败")


async def scan() -> dict:
    stats = {"generated": 0, "collected": 0, "withdrawn": 0, "cleaned": 0, "at": utc_now().isoformat()}
    res = await rec_repo.sync()
    if not res["ok"]:
        stats["error"] = res["message"]
        _last_scan.clear()
        _last_scan.update(stats)
        return stats
    me = rec_repo.device()
    mine = {e.task_no: e for e in rec_repo.entries().values() if e.owner == me}

    withdraw: list[dict] = []
    cleanup: list[tuple[int, str]] = []
    with session() as db:
        tasks = {t.task_no: t for t in db.execute(
            select(Task).where(Task.task_no.in_(list(mine)) | (Task.status == QC))).scalars()}
        for no, entry in mine.items():
            task = tasks.get(no)
            rec = (task.recording if task else {}) or {}
            live = entry.state in (rec_repo.S_OPEN, rec_repo.S_CLAIMED, rec_repo.S_RECORDED)
            if task is None or task.status in FINAL:
                if live:
                    withdraw.append(rec_repo.event(rec_repo.WITHDRAWN, me, no, reason="题已提交或废弃"))
                # 本机库里没有的题不删：可能是换过库，分支上的视频是唯一一份
                if task is not None and not rec.get("branch_deleted"):
                    cleanup.append((task.id, no))
                continue
            stale = entry.digest != current_digest(task)
            if live and (task.status not in (QC, READY) or stale
                         or (task.status == READY and entry.state != rec_repo.S_RECORDED)):
                why = "理由改过" if stale else f"题已离开待录屏（{task.status}）"
                withdraw.append(rec_repo.event(rec_repo.WITHDRAWN, me, no, reason=why))
                continue
            if entry.state == rec_repo.S_RECORDED and task.status == QC and not stale:
                if task.id in _collect_jobs:
                    continue
                if rec.get("collect_error") and _age(rec.get("collect_failed_at") or "") < COLLECT_RETRY_GAP_S:
                    continue
                _start_collect(task.id, entry)
                stats["collected"] += 1
        # 人手动排的排前面，而且不看自动生成开关
        wanted = sorted((t for t in tasks.values() if needs_generation(t)),
                        key=lambda t: (not (t.recording or {}).get("wanted"), t.task_no))
        wanted_ids = [(t.id, bool((t.recording or {}).get("wanted"))) for t in wanted]

    if withdraw:
        r = await rec_repo.append(withdraw, subject=f"withdraw {len(withdraw)}")
        if r["ok"]:
            stats["withdrawn"] = len(withdraw)
            for ev in withdraw:
                with session() as db:
                    t = db.execute(select(Task).where(Task.task_no == ev["task_no"])).scalar_one_or_none()
                    if t is not None and (t.recording or {}).get("state") in (PUBLISHED, GENERATING):
                        rec = {**t.recording, "state": WITHDRAWN, "withdrawn_at": utc_now().isoformat(),
                               "note": ev.get("reason", "")}
                        t.recording = rec
    for task_id, no in cleanup:
        r = await rec_repo.delete_branch(me, no)
        if r["ok"]:
            stats["cleaned"] += 1
            _update(task_id, branch_deleted=True)

    for tid, manual in wanted_ids:
        if len(_gen_jobs) >= max_parallel():
            break
        if not (manual or auto_generate()):
            continue
        if start_generate(tid)["ok"]:
            stats["generated"] += 1
    _last_scan.clear()
    _last_scan.update(stats)
    if any(stats[k] for k in ("generated", "collected", "withdrawn", "cleaned")):
        log.info("录屏协作：起生成 %d，收视频 %d，撤回 %d，清分支 %d",
                 stats["generated"], stats["collected"], stats["withdrawn"], stats["cleaned"])
    return stats


def reset_stale_generating() -> int:
    """开机时把上次进程留下的 generating 改成失败，交给巡检重新排。"""
    n = 0
    with session() as db:
        for task in db.execute(select(Task).where(Task.recording_json.like('%"generating"%'))).scalars():
            rec = task.recording or {}
            if rec.get("state") == GENERATING:
                task.recording = {**rec, "state": GEN_FAILED, "error": "后端重启，生成中断",
                                  "failed_at": "", "stage": "", "note": ""}
                n += 1
    return n


# ---------------- 录屏端动作 ----------------

def inbox_dir(owner: str, task_no: str) -> Path:
    return config.DATA_DIR / "rec" / "inbox" / rec_repo.pool._slug(owner) / str(task_no)


def _find(key: str) -> rec_repo.Entry | None:
    return rec_repo.entries().get(key)


async def claim(key: str) -> dict:
    """认领一道题并拉回文档。先写先得：推完再读一遍，看是不是自己抢到了。"""
    res = await rec_repo.sync()
    if not res["ok"]:
        return {"ok": False, "message": res["message"]}
    entry = _find(key)
    if entry is None:
        return {"ok": False, "message": "录屏仓库里没有这道题"}
    me = rec_repo.device()
    if entry.state == rec_repo.S_CLAIMED and entry.claimed_by == me:
        return await report(key)
    if entry.state != rec_repo.S_OPEN:
        who = f"（{entry.claimed_by} 在录）" if entry.claimed_by else ""
        return {"ok": False, "message": f"这道题现在不能认领：{entry.state}{who}"}
    ev = rec_repo.event(rec_repo.CLAIMED, entry.owner, entry.task_no, digest=entry.digest)
    r = await rec_repo.append([ev], subject=f"claim {entry.task_no}")
    if not r["ok"]:
        return {"ok": False, "message": r["message"]}
    await rec_repo.sync()
    entry = _find(key)
    if entry is None or entry.claimed_by != me:
        who = entry.claimed_by if entry else "别人"
        return {"ok": False, "message": f"晚了一步，{who} 先认领了这道题"}
    return await report(key)


async def report(key: str) -> dict:
    entry = _find(key)
    if entry is None:
        return {"ok": False, "message": "录屏仓库里没有这道题"}
    cache = inbox_dir(entry.owner, entry.task_no)
    path, stamp = cache / rec_repo.REPORT_FILE, cache / ".digest"
    if not (path.is_file() and stamp.is_file() and stamp.read_text().strip() == entry.digest):
        ok, body = await rec_repo.read_file(entry.owner, entry.task_no, rec_repo.REPORT_FILE)
        if not ok:
            return {"ok": False, "message": str(body)}
        cache.mkdir(parents=True, exist_ok=True)
        path.write_text(str(body), encoding="utf-8")
        stamp.write_text(entry.digest)
    return {"ok": True, "entry": entry.as_dict(), "markdown": path.read_text(encoding="utf-8")}


async def release(key: str) -> dict:
    entry = _find(key)
    if entry is None or entry.state != rec_repo.S_CLAIMED or entry.claimed_by != rec_repo.device():
        return {"ok": False, "message": "这道题不在你名下"}
    ev = rec_repo.event(rec_repo.RELEASED, entry.owner, entry.task_no, digest=entry.digest)
    r = await rec_repo.append([ev], subject=f"release {entry.task_no}")
    return {"ok": r["ok"], "message": "已放回队列" if r["ok"] else r["message"]}


async def submit_videos(key: str, files: dict[str, Path]) -> dict:
    """回传两侧视频。两侧都要给：只传一侧，出题端收回去也提交不了。"""
    missing = [s for s in config.SIDES if s not in files]
    if missing:
        return {"ok": False, "message": f"还缺 {'、'.join(missing)} 侧的视频"}
    for side, src in files.items():
        if not src.is_file():
            return {"ok": False, "message": f"{side} 侧文件不存在：{src}"}
        if src.suffix.lower() not in gsb_uploader.VIDEO_SUFFIXES:
            return {"ok": False, "message": f"{side} 侧 {src.name} 不像视频文件"}
    await rec_repo.sync()
    entry = _find(key)
    me = rec_repo.device()
    if entry is None:
        return {"ok": False, "message": "录屏仓库里没有这道题"}
    if entry.state == rec_repo.S_WITHDRAWN:
        return {"ok": False, "message": "这份文档已被出题端撤回（理由改过或题已提交），视频不用传了"}
    if entry.state == rec_repo.S_CLAIMED and entry.claimed_by != me:
        return {"ok": False, "message": f"这道题由 {entry.claimed_by} 在录"}
    if entry.state not in (rec_repo.S_OPEN, rec_repo.S_CLAIMED):
        return {"ok": False, "message": f"这道题已经回传过了（{entry.state}）"}
    names = {s: f"{s}{files[s].suffix.lower()}" for s in config.SIDES}
    with tempfile.TemporaryDirectory(dir=rec_repo.scratch_dir(), prefix="up-") as tmp:
        staged = {}
        for side, src in files.items():
            dst = Path(tmp) / names[side]
            shutil.copy2(src, dst)
            staged[names[side]] = dst
        r = await rec_repo.add_files(entry.owner, entry.task_no, staged, subject=f"record {entry.task_no}")
    if not r["ok"]:
        return {"ok": False, "message": r["message"]}
    ev = rec_repo.event(rec_repo.RECORDED, entry.owner, entry.task_no, digest=entry.digest, files=names)
    r = await rec_repo.append([ev], subject=f"recorded {entry.task_no}")
    if not r["ok"]:
        return {"ok": False, "message": r["message"]}
    return {"ok": True, "message": f"已回传，{entry.owner} 那边下一轮巡检会自动收回"}


async def withdraw_task(task_id: int) -> dict:
    """出题端手动撤回（比如想改理由再录）。"""
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        no = task.task_no
    me = rec_repo.device()
    entry = rec_repo.entries().get(rec_repo.key_of(me, no))
    if entry is None or entry.state in (rec_repo.S_WITHDRAWN, rec_repo.S_COLLECTED):
        return {"ok": False, "message": "这道题没有在录屏队列里"}
    r = await rec_repo.append([rec_repo.event(rec_repo.WITHDRAWN, me, no, reason="出题端手动撤回")],
                              subject=f"withdraw {no}")
    if r["ok"]:
        _update(task_id, state=WITHDRAWN, withdrawn_at=utc_now().isoformat(), note="手动撤回")
    return {"ok": r["ok"], "message": "已撤回" if r["ok"] else r["message"]}


# ---------------- 概览 ----------------

def overview() -> dict:
    ok, why = rec_repo.available()
    me = rec_repo.device() if ok else ""
    ents = rec_repo.entries() if ok else {}
    with session() as db:
        by_no = {t.task_no: t for t in db.execute(
            select(Task).where(Task.status.in_((QC, READY)) | Task.recording_json.not_in(("{}", "")))).scalars()}
        local = []
        for t in sorted(by_no.values(), key=lambda x: x.task_no):
            if t.status not in (QC, READY) and not (t.recording or {}).get("state"):
                continue
            if t.status in FINAL:
                continue
            entry = ents.get(rec_repo.key_of(me, t.task_no)) if me else None
            local.append({
                "id": t.id, "task_no": t.task_no, "status": t.status,
                "question_type": t.question_type, "difficulty": t.difficulty,
                "verdict": (t.gsb or {}).get("verdict") or "",
                "recording": t.recording or {},
                "generating": t.id in _gen_jobs, "collecting": t.id in _collect_jobs,
                "screencast": t.screencast or {},
                "submit_block": gsb_precheck.submit_block(t),
                "entry": entry.as_dict() if entry else None,
                "need": needs_generation(t),
            })
    queue = []
    for e in sorted(ents.values(), key=lambda x: x.published_at, reverse=True):
        if e.state == rec_repo.S_WITHDRAWN:
            continue
        queue.append({**e.as_dict(), "mine": e.owner == me, "claimed_by_me": e.claimed_by == me,
                      "recorded_by_me": e.recorded_by == me})
    return {
        "available": ok, "message": why, "device": me,
        "role": "recorder" if rec_repo.recorder_only() else "producer",
        "repo": rec_repo.repo_slug(), "auto_generate": auto_generate(),
        "max_parallel": max_parallel(), "generating": len(_gen_jobs),
        "skill_missing": rec_report.preflight(),
        "last_scan": dict(_last_scan), "local": local, "queue": queue,
        "now": time.time(),
    }
