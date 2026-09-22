"""定时任务：监控运行状态、监控分支进度、生成描述并质检、整合结果。

流水线只做「把题跑起来」那一段：拉题、按分支 clone 出 A 与 B 两份、起两个容器把题面
发给 Claude Code。跑起来之后的所有判断都归这里，流水线不回头看。

分成两条是因为职责的时间尺度不一样。流水线是一次性动作，发完就完；而「跑得怎么样」
要持续看：容器可能被 prune 掉、网关可能抽风、两侧结束时间差着几十分钟。把这些判断塞回
流水线就会出现 A 和 B 同时认为「该我推进了」，于是分析被起两次、容器被销毁两次。
所以收归一处，runner 跑完只负责叫一声。

四件事按顺序做，前一件的结果是后一件的前提：

1. 监控运行状态。这一侧是不是真的跑坏了。网关报错不算——CC 自带十次重试，
   重试期间不介入；重试用尽仍没跑成才动手，动作是完全回退：销毁容器、归档轨迹、
   清掉轨迹派生物与题级的分析结论、把本地目录整个删掉重新 clone、退回队列重跑这一侧。
2. 监控分支进度。A 跑完了就等 B，两侧都正常结束才推进：销毁容器、把两侧产物提交
   并推到各自分支、开 GSB 分析。
3. 生成描述并质检。分析产出结论与理由，先过本地核验（长度、AI 痕迹、证据可定位），
   再送 solo-qa 的 GSB 质检链路拿平台口径的结论。
4. 整合结果。把上面每一步的结论落到题上，异常的转人工，正常的留着等录屏与上传。

周期扫描是兜底。正常情况下 runner 结束会 wake 一次，立刻扫，不必等满一轮。
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import time
from datetime import datetime

from sqlalchemy import select

from app import config
from app.db import session
from app.events import bus
from app.models import (
    ANALYSIS_FAILED, ANALYSIS_IDLE, ANALYSIS_RUNNING, ANALYZED, ANALYZING, DISCARDED,
    FACTCHECK_IDLE, NEEDS_ATTENTION, PRECHECK_IDLE, QC, QUEUED, RUN_DONE,
    RUN_END_STATUSES, RUN_FAILED, RUN_FINISHED, RUN_INTERRUPTED, RUN_QUEUED, RUN_RUNNING,
    RUN_TIMEOUT, SCHEDULABLE, SETTLING, WATCHED, RunEvent, Task, TaskRun, as_utc, utc_now,
)
from app.services import dockerx, gsb_repo, llm, settings_store

log = logging.getLogger("watchdog")

INTERVAL_DEFAULT = 300
MAX_RETRIES_DEFAULT = 3
MAX_TIMEOUTS_DEFAULT = 2

# 「零改动」是代价最大的一条异常：它会把整侧清掉重跑。而收尾那一刻读到的零改动
# 未必作数，所以动手之前要实测复核一次。这里留常量是为了让判定和复核认的是同一句话。
ZERO_CHANGE_REASON = "工作目录零改动"

_wake = asyncio.Event()
_task: asyncio.Task | None = None
_stopping = False
# 同一道题正在推进时不许再进来。巡检和界面上那个「提交产物并分析」是两条独立入口，
# 撞在一起会各自把两侧产物推一遍：推同一个分支的两条 push 里落后的那条被远端拒掉，
# 接着它把「push 失败」写进 auto_error，盖掉另一条已经成功的事实——产物明明推上去了，
# 界面上却挂着一句让人去翻 Token 写权限的假报错。
# 用集合而不是 asyncio.Lock：要的是「挡回去」而不是「排队」，排队等完再跑一遍推送和
# 分析纯属白做；而且 Lock 会绑到创建它的事件循环上，测试里每个用例各起一个循环，
# 同一把锁跨循环复用会直接抛错。判断与写入之间没有 await，单线程事件循环里是原子的。
_advancing: set[int] = set()
# 在跑的后台推进，{task_id: task}。推进不能在巡检循环里直接 await：它要跑 GSB 分析和
# 质检，两个都在调模型，一道题十几二十分钟是常态，模型不返回时还要再乘上 llm 的重试
# 次数。占住的不只是配对这一步 —— 补记账、异常重跑跟它在同一轮 tick 里，于是跑挂的等
# 不到重跑、跑完的等不到配对，整套定时任务看上去就是停摆了，而容器照常在跑。
_advance_tasks: dict[int, asyncio.Task] = {}
# 人工点过「提交产物并分析」、还没轮到额度的题，按点击顺序排。
# 批量发起时一次能点十几道，而并发额度通常是 2，超出的必须留个凭据等着：这批题里有
# NEEDS_ATTENTION 的、有分析失败过的，配对扫描一律够不着（见 _pairs_ready），
# 当场丢掉就是悄无声息地不干活 —— 人在界面上只会看到自己点过的那批里有几道永远没动静。
_advance_wanted: list[int] = []
# 人工点过「跑质检」、还没轮到额度的题。和 _advance_wanted 分开排：那批要走推产物
# 加分析，这批只跑两道质检，一道题的耗时差着一个量级，混在一个队里会让点质检的人
# 排在几道正在做分析的题后面干等。
_gate_wanted: list[int] = []
_last_tick_at: datetime | None = None
_last_error = ""
_last_stats: dict = {}


def wake() -> None:
    """催一次巡检。单侧跑完后调用，不必等下一个周期到点。"""
    _wake.set()


def paused() -> bool:
    """异常处理是不是被人按停了。

    停的只是「动手」这一段：判定照做、异常照记，但不重跑也不废弃。模型或网关停机时
    非开不可 —— 那种时候每一侧都会跑挂，而重跑的动作是把工作区连 `.git` 一起删掉重建，
    停机半小时就能把一整批题清空并跑满次数废弃掉，而它们本来只差一次重跑。
    """
    return settings_store.get_bool("watchdog.paused", False)


def status() -> dict:
    """巡检自己的近况，供界面确认它确实在按周期跑。"""
    return {
        "interval_seconds": max(30, settings_store.get_int("watchdog.interval_seconds", INTERVAL_DEFAULT)),
        "paused": paused(),
        "max_retries": settings_store.get_int("watchdog.max_retries", MAX_RETRIES_DEFAULT),
        "max_timeouts": settings_store.get_int("watchdog.max_timeouts", MAX_TIMEOUTS_DEFAULT),
        "alive": alive(),
        "advancing": len(_advance_tasks),
        "last_tick_at": _last_tick_at.isoformat() if _last_tick_at else None,
        "last_error": _last_error,
        "last_stats": _last_stats,
    }


def _sync_task(db, task_id: int) -> None:  # noqa: ANN001
    """把题级状态对齐到两侧 run 的现状。

    局部导入：scheduler 顶层引了 runner，runner 顶层又引了本模块，写在文件头会成环。
    """
    from app.services.scheduler import sync_task_status

    sync_task_status(db, task_id)


# ---------------- 异常判定 ----------------

def _gateway_note(process: dict) -> str:
    """跑失败时补一句网关重试的情况，拼在原因后面。"""
    gw = process.get("gateway_errors") or []
    if not gw:
        return ""
    retries = process.get("retries") or {}
    note = f"；期间出现网关报错 {'、'.join(str(g) for g in gw)}"
    if attempt := retries.get("attempt"):
        note += f"，CC 已自行重试 {attempt}/{retries.get('max_retries') or '?'} 次仍未跑成"
    return note


def abnormal_reason(run: TaskRun, container_alive: bool | None = None) -> str:
    """这一侧是不是异常。返回原因，正常返回空串。

    判的是「这次跑的过程坏了」，不是「模型做得不好」。做得不好是 GSB 要评的内容，
    过程坏了的结果没有可比性，只能重跑。

    网关报错本身不再单独构成异常。镜像里的 Claude Code 自带十次重试，504 这类故障
    绝大多数在重试里就缓过来了，最后照样跑完。以前只要 stderr 里出现过状态码就重跑
    整侧，等于把一次已经成功的运行推倒重来，既白烧一小时算力，又让本来能配对的两侧
    再次错开。所以现在只看结局：跑成了就不管它中途重试过几次，没跑成才介入，
    而重试次数只作为原因说明的一部分。
    """
    verdict = run.verdict or {}
    process = verdict.get("process") or {}
    artifact = verdict.get("artifact") or {}
    protocol = verdict.get("protocol") or {}

    if run.status == RUN_RUNNING:
        # 容器被 docker prune 之类的操作带走时，run 会永远停在 RUNNING。
        #
        # started_at 为空是另一回事：调度出闸时先占住 RUNNING 状态，容器要等 runner
        # 校验完起跑点才真正拉起来，而 started_at 是在那之后才写的。这段窗口里容器
        # 本来就不存在，当成「容器没了」会把一次刚开始的运行当场判死、清掉重跑，
        # 而且每次出闸都会中一遍。
        if run.started_at is None or container_alive is not False:
            return ""
        return f"状态是运行中，但容器 {run.container_name} 已经不在了"
    if run.status not in RUN_END_STATUSES:
        return ""
    # 人主动按的停止不自动重跑。他可能是看着不对要去改配置，这时候悄悄重跑一遍
    # 既浪费算力，也会把他刚改的东西盖掉。
    if process.get("manual_stop"):
        return ""
    if run.status != RUN_FINISHED:
        return f"这一侧的结束状态是 {run.status}{_gateway_note(process)}"
    if (code := process.get("exit_code")) not in (0, None):
        return f"容器退出码 {code}{_gateway_note(process)}"
    subtype = protocol.get("subtype")
    if subtype and subtype != "success":
        return f"result 的 subtype 是 {subtype}{_gateway_note(process)}"
    # 「戛然而止」：没报错，但什么都没留下。代码理解类的题可能确实不改代码，
    # 所以零改动只在同时没有轨迹或轨迹为空时才算——真跑过的痕迹比改动数更可靠。
    if not artifact.get("trace_found"):
        return f"没有产出轨迹，疑似戛然而止{_gateway_note(process)}"
    if not artifact.get("changed_files") and not (run.git_diff_stat or "").strip():
        return f"{ZERO_CHANGE_REASON}，疑似戛然而止{_gateway_note(process)}"
    return ""


def can_retry(run: TaskRun, max_retries: int | None = None) -> bool:
    limit = max_retries if max_retries is not None else settings_store.get_int(
        "watchdog.max_retries", MAX_RETRIES_DEFAULT)
    return run.attempt < max(1, limit)


def discard_reason(run: TaskRun, max_retries: int | None = None,
                   max_timeouts: int | None = None) -> str:
    """这一侧的重跑预算用光了没有。返回废弃理由，空串表示还能再跑。

    两个上限分开数。普通异常大多在几分钟内就失败了，多试两次不心疼；超时不一样，
    一次要整整烧掉 run.timeout_minutes，连着两次就是几个小时的机器时间换一份没有的
    结果。先撞到哪个上限就按哪个废弃。
    """
    tlimit = max(1, max_timeouts if max_timeouts is not None else settings_store.get_int(
        "watchdog.max_timeouts", MAX_TIMEOUTS_DEFAULT))
    rlimit = max(1, max_retries if max_retries is not None else settings_store.get_int(
        "watchdog.max_retries", MAX_RETRIES_DEFAULT))
    if (run.timeouts or 0) >= tlimit:
        return f"{run.side} 侧超时 {run.timeouts} 次，达到上限 {tlimit}"
    if not can_retry(run, rlimit):
        return f"{run.side} 侧已跑 {run.attempt} 次，达到上限 {rlimit}"
    return ""


# ---------------- 重跑动作 ----------------

def archive_traces(task_no: str, side: str) -> dict:
    """把非空轨迹目录整体改名归档（带时间戳），腾出空目录。

    镜像的 entrypoint 会拒绝挂载非空的轨迹目录，重跑前必须腾干净。改名而不是删除：
    上一次的轨迹是判「为什么异常」的唯一材料。
    """
    tr = config.TaskPaths(task_no, side).traces
    if not tr.exists() or not any(tr.iterdir()):
        return {"ok": True, "message": "轨迹目录本就为空"}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = tr.with_name(f"{tr.name}.archived-{stamp}")
    if target.exists():
        target = tr.with_name(f"{tr.name}.archived-{stamp}-{utc_now().microsecond}")
    tr.rename(target)
    return {"ok": True, "message": f"已归档到 {target.name}"}


def clear_trace_derivatives(task_no: str, side: str) -> None:
    """删掉上一跑轨迹的派生物：导出的 jsonl 副本与轨迹索引。

    原始轨迹归档留着是为了查「为什么异常」，这两份不留：它们不是材料，是下游直接
    读的输入。质检从导出目录里按文件名排序挑 jsonl，轨迹文件名是随机的 session id，
    留着上一跑那份就有一半的概率挑错；分析则优先读轨迹索引，索引在就根本不去看新轨迹。
    两处都不会报错，只会安静地拿上一跑的过程去比这一跑的产物。
    """
    paths = config.TaskPaths(task_no, side)
    shutil.rmtree(paths.export, ignore_errors=True)
    paths.trace_index.unlink(missing_ok=True)


def clear_analysis(task: Task) -> None:
    """清掉题级的 GSB 结论与它在磁盘上的中间产物。

    结论是两侧比出来的，任一侧重跑，它依据的材料就有一半不存在了。留着有两重害处：
    界面照旧显示「已分析」，核验、质检、上传都会拿它当真，交出去的是上一跑的结论；
    而且配对扫描只挑 analysis_status 为 IDLE 的题，不复位的话两侧重跑完也不会再分析，
    题会静静卡在那里等一个永远不来的结论。
    """
    task.analysis_status = ANALYSIS_IDLE
    task.analysis = {}
    task.gsb = {}
    task.verify = {}
    task.gsb_qc = {}
    # 两道提交前质检评的都是那段已经不存在的理由，留着它们，一道重跑过的题会带着
    # 上一轮的「事实核验通过」直接可提交，而那份核验对的是上一跑的轨迹。
    task.factcheck_status = FACTCHECK_IDLE
    task.factcheck = {}
    task.precheck_status = PRECHECK_IDLE
    task.precheck = {}
    analysis_dir = config.TaskPaths(task.task_no).analysis
    # gsb_facts.json 是事实核验的材料，它对应的是上一跑的轨迹，必须跟着清掉：
    # 留着的话下一轮核验会拿上一跑的执行记录去判新理由，报出来的不符全是假的。
    for name in ("gsb_prompt.md", "gsb_raw.txt", "gsb_facts.json"):
        (analysis_dir / name).unlink(missing_ok=True)


async def requeue_run(run_id: int, *, reason: str, reset_attempt: bool = False,
                      full: bool = True) -> dict:
    """把一侧退回起点重新排队。

    顺序不能变：先销毁容器（不然容器名占着起不来），再归档轨迹（镜像拒绝非空目录，
    而那个目录挂的就是模型的会话记录，不腾干净下一跑会读到上一跑的对话），最后重建
    工作区。中间任何一步失败就停下来交给人工，硬着头皮往下走只会跑出一份没法用的结果。

    上一跑留在库里和磁盘上的东西同样要清干净：这一侧的事件与运行字段、轨迹的两份
    派生物，以及题级那份 GSB 结论，见 clear_trace_derivatives 与 clear_analysis。

    full 为真时走完全重建：分支从主干在初始快照上重新开一份，本地和远端都换掉，
    详见 gsb_repo.rebuild_side。重跑出来的这一跑必须跟第一次跑站在同一个起点上，
    不然两边就没有可比性；留下任何上一跑的痕迹——工作区的文件、`.git` 里的对象、
    远端分支上的提交、容器里的会话记录——都算污染。
    """
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return {"ok": False, "message": "这一侧的运行记录不存在"}
        task = db.get(Task, run.task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        task_id, task_no, side = task.id, task.task_no, run.side
        repo_url = task.repo_url
        snapshot, name = gsb_repo.snapshot_sha(task.env_snapshot), run.container_name

    await dockerx.remove_container(name)
    arch = await asyncio.to_thread(archive_traces, task_no, side)
    if not arch["ok"]:
        return {"ok": False, "message": f"归档 {side} 侧轨迹失败：{arch['message']}"}
    await asyncio.to_thread(clear_trace_derivatives, task_no, side)
    if not snapshot:
        return {"ok": False, "message": "初始快照缺少 40 位 SHA，不敢回退工作区"}
    if full:
        rst = await gsb_repo.rebuild_side(task_no, repo_url, side, snapshot)
    else:
        rst = await gsb_repo.reset_side(task_no, side, snapshot)
    if not rst.get("ok"):
        return {"ok": False, "message": f"{side} 侧回退失败：{rst.get('message')}"}

    with session() as db:
        run = db.get(TaskRun, run_id)
        task = db.get(Task, run.task_id) if run else None
        if run is None or task is None:
            return {"ok": False, "message": "运行记录已消失"}
        # 上一次的事件全清掉。留着的话时间线上会出现两次「启动容器」，
        # 而界面按 seq 排序，读起来像模型自己重启了一遍
        db.query(RunEvent).filter(RunEvent.task_id == task_id, RunEvent.side == side).delete()
        # 超时单独记一笔再清掉状态，不然重跑一次这笔账就没了，超时上限永远撞不到
        if run.status == RUN_TIMEOUT:
            run.timeouts = (run.timeouts or 0) + 1
        run.attempt = 1 if reset_attempt else run.attempt + 1
        if reset_attempt:
            run.timeouts = 0
        run.status = RUN_QUEUED
        run.abnormal = {"reason": reason, "at": utc_now().isoformat(), "attempt": run.attempt}
        run.exit_code = None
        run.result = {}
        run.verdict = {}
        run.trace_summary = {}
        run.trace_file = ""
        run.git_diff_stat = ""
        run.error = ""
        run.session_id = ""
        run.turn_id = ""
        run.artifact_sha = ""
        run.artifact_url = ""
        run.container_exists = False
        run.stop_requested = False
        run.started_at = None
        run.finished_at = None
        # 题回到运行阶段。到底是 QUEUED 还是 RUNNING 由两侧 run 推，不在这里硬写：
        # 另一侧很可能还在跑，硬写 QUEUED 会让界面上一道正在跑的题显示成排队。
        task.status = QUEUED
        task.finished_at = None
        task.auto_error = ""
        clear_analysis(task)
        _sync_task(db, task_id)
        # 录屏录的是这一侧的产物，产物换了那份录像就对不上了。留着它上传时仍然是一个
        # 填好了的必填项，交出去的是上一跑的录像。另一侧的录屏没受影响，不动。
        casts = task.screencast
        if side in casts:
            casts.pop(side)
            task.screencast = casts
        attempt = run.attempt
    bus.publish("tasks", {"type": "task", "id": task_id})
    how = "完全回退（清空重拉）" if rst.get("mode") == "wipe" else "回退到初始快照"
    return {"ok": True, "attempt": attempt, "mode": rst.get("mode", ""),
            "message": f"{side} 侧已{how}，这是第 {attempt} 次尝试（{reason}）"}


async def give_up(run_id: int, reason: str) -> dict:
    """这一侧的重跑预算用光了，整道题废弃。

    废的是题不是那一侧。GSB 交的是两侧对比，一侧怎么都跑不出来，另一侧跑得再好也
    交不上去；让它接着占一个容器跑满两小时，换回来的还是一份用不上的结果。所以连着
    把另一侧也收掉，槽位立刻还给队列去跑下一道题。

    以前这里是转 NEEDS_ATTENTION 等人处理，题就一直挂在那儿：不占容器，但也不出结果，
    队列里堆的到底是「在等机器」还是「在等人」分不出来。现在直接进废弃列表，人要捞
    回来按「恢复」就行，轨迹和产物都还在磁盘上。
    """
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return {"ok": False, "message": "这一侧的运行记录不存在"}
        task_id, side, attempt = run.task_id, run.side, run.attempt
        run.status = RUN_FAILED if run.status not in RUN_END_STATUSES else run.status
        run.abnormal = {"reason": reason, "at": utc_now().isoformat(),
                        "attempt": attempt, "gave_up": True}
        if run.finished_at is None:
            run.finished_at = utc_now()
    return await discard_task(task_id, f"{side} 侧第 {attempt} 次仍异常：{reason}")


async def discard_task(task_id: int, reason: str) -> dict:
    """废弃整道题：停掉还在跑的容器、销毁两侧容器、题进废弃列表。"""
    from app.services import runner

    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        if task.status == DISCARDED:
            return {"ok": True, "message": "该题已是废弃状态"}
        task_no, from_status = task.task_no, task.status
        alive = [r.id for r in db.query(TaskRun).filter(
            TaskRun.task_id == task_id, TaskRun.status == RUN_RUNNING).all()]

    # 先走停止接口再销毁：stop_run 会打上人工停止的标记，另一侧的 runner 收尾时
    # 才不会把这次停止当成又一次异常，转头再给这道已经废弃的题排一次重跑。
    for rid in alive:
        await runner.stop_run(rid)
    removed = (await dockerx.remove_task_containers(task_no)).ok

    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all():
            r.container_exists = False
            if r.status not in RUN_END_STATUSES:
                r.status = RUN_INTERRUPTED
                r.finished_at = r.finished_at or utc_now()
        task.discarded_from = from_status
        task.status = DISCARDED
        task.discarded_at = utc_now()
        task.auto_error = f"自动废弃：{reason}"[:2000]
    log.warning("题 %s 自动废弃：%s", task_no, reason)
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": True, "discarded": True, "container_removed": removed, "message": reason}


# ---------------- 配对推进 ----------------

async def _destroy_containers(task_no: str, runs: list[TaskRun]) -> None:
    """轨迹已经导出到宿主机就销毁容器；没导出成功的留着，让人工进去捞。

    删完要把台账改回去。以前只删不记，于是这些题在详情页上永远显示「容器保留 2/2」，
    而两个容器早在推进那一刻就没了。
    """
    removed = []
    for run in runs:
        if run.trace_file:
            await dockerx.remove_container(run.container_name)
            removed.append(run.id)
    if removed:
        with session() as db:
            for rid in removed:
                if (r := db.get(TaskRun, rid)) is not None:
                    r.container_exists = False


async def push_artifacts(task_id: int) -> dict:
    """把两侧产物提交并推到各自分支，回填产物快照链接。

    失败不算模型的错，所以不计入重跑次数，题留在原状态等下一轮再试。
    """
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        task_no, repo_url = task.task_no, task.repo_url
        snapshot = gsb_repo.snapshot_sha(task.env_snapshot)
        runs = {r.side: (r.id, r.session_id, r.artifact_sha)
                for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()}

    msgs = []
    for side in config.SIDES:
        if side not in runs:
            return {"ok": False, "message": f"缺少 {side} 侧的运行记录"}
        run_id, session_id, existing = runs[side]
        if existing:
            msgs.append(f"{side}: 已有快照 {existing[:12]}")
            continue
        r = await gsb_repo.commit_and_push(
            task_no, repo_url, side, snapshot,
            message=gsb_repo.commit_message(task_no, side, session_id))
        if not r.get("ok"):
            return {"ok": False, "message": f"{side} 侧推送失败：{r.get('message')}"}
        with session() as db:
            run = db.get(TaskRun, run_id)
            if run is not None:
                run.artifact_sha = r.get("sha", "")
                run.artifact_url = r.get("url", "")
        msgs.append(f"{side}: {r.get('sha', '')[:12]}")
    # 两侧都推上去了，把上一轮的失败说明擦掉。不擦的话那句话会一直挂在界面上：
    # 产物早就推成功、分析也跑完了，人看到的还是「push 失败，检查 Token 写权限」，
    # 于是跑去翻权限设置，而实际上什么都不用做。
    with session() as db:
        task = db.get(Task, task_id)
        if task is not None:
            task.auto_error = ""
    return {"ok": True, "message": "；".join(msgs)}


async def advance_pair(task_id: int) -> dict:
    """推进这道题，同一时刻只允许一个在跑，理由见 _advancing。"""
    if task_id in _advancing:
        log.info("题 %s 已经在推进了，这次调用直接挡回去", task_id)
        return {"ok": False, "message": "这道题正在推进中，等它跑完再说"}
    _advancing.add(task_id)
    try:
        return await _advance_pair(task_id)
    finally:
        _advancing.discard(task_id)


async def _advance_pair(task_id: int) -> dict:
    """两侧都正常结束之后的推进：销毁容器、推产物、写描述、质检。

    推产物必须排在分析前面：分析要拿 snapshot..HEAD 的补丁当产物材料，而这个区间
    只有在产物提交之后才存在。顺序反过来的话，两侧的补丁都会是空的。
    """
    with session() as db:
        task = db.get(Task, task_id)
        if task is None:
            return {"ok": False, "message": "题目不存在"}
        runs = db.query(TaskRun).filter(TaskRun.task_id == task_id).all()
        # 跑挂的那一侧不能提交、更不能推。推上去的是一份没跑完的东西，拿它做对比就是拿
        # 半截结果当结论；而且远端一旦有了这个提交，重跑时还得先把分支退回去。
        # 这一侧该走的是重建重跑，不是存档。自动路径上配对扫描已经挡了一道，这里再挡一次，
        # 是因为界面上那个「提交产物并分析」是直连过来的，绕得过扫描。
        if len(runs) != 2:
            return {"ok": False, "message": "这道题还没凑齐两侧"}
        blocked = sorted(r.side for r in runs
                         if r.status != RUN_FINISHED or abnormal_reason(r))
        if blocked:
            return {"ok": False,
                    "message": f"{'、'.join(blocked)} 侧没有正常跑完，不能提交产物；"
                               f"先重跑这一侧，两侧都正常了再推进"}
        task_no = task.task_no
        task.status = RUN_DONE
        detached = list(runs)
    await _destroy_containers(task_no, detached)

    push = await push_artifacts(task_id)
    if not push["ok"]:
        with session() as db:
            task = db.get(Task, task_id)
            if task is not None:
                task.auto_error = push["message"][:2000]
        bus.publish("tasks", {"type": "task", "id": task_id})
        return push

    from app.services import gsb_analyzer

    analyzed = await gsb_analyzer.analyze_task(task_id)
    if not analyzed.get("ok"):
        return analyzed
    # 质检失败不推翻已经写好的结论：理由还在，人改几句就能再过一遍，
    # 没必要把整次分析作废重跑
    qc = await run_quality_gate(task_id)
    return {**analyzed, "qc": qc}


async def run_quality_gate(task_id: int) -> dict:
    """事实核验 + 措辞质检 + 本地核验 + solo-qa 的 GSB 质检。

    四道拦的东西各不相同，一道都不能省：
    - 事实核验：理由里关于执行结果的话和轨迹对不对得上。会调模型，对不上的直接订正。
    - 措辞质检：读起来像不像一个人写的，篇幅压到规范之内。会调模型，直接改写正文。
    - 本地核验：确定性的东西（长度、AI 痕迹、证据能不能定位、两侧材料齐不齐），
      快且不花钱。
    - solo-qa 质检：平台自己的口径，慢但结论权威。

    顺序是定死的，前两道尤其不能换。两道都会整段换掉理由正文，而事实必须先定下来：
    先把话说对，再把话说顺。反过来的话，措辞那一版打磨的是一段事实还错着的话，
    事实核验接着又把它改一遍，前一次的打磨白做，而且改完的那一段没人再看措辞。

    后两道也必须排在前两道之后：它们读到的必须是最终要提交的那一段，否则核验过了
    也说明不了提交的那一份合规。

    前两道没跑成都不挡后面。模型欠费或者超时的时候把整条闸门停掉，等于一道题都过不去；
    过不了的那一档会留在 ERROR 上，看门狗看到账单恢复会自己回来补。
    """
    from app.services import gsb_factcheck, gsb_precheck, gsb_verifier, qa_bridge

    fact = await gsb_factcheck.run_factcheck(task_id)
    if not fact.get("ok"):
        log.warning("题 %d 事实核验没跑成，继续走措辞质检：%s", task_id, fact.get("message", ""))
    elif fact.get("applied"):
        log.info("题 %d 事实核验订正了 %d 处后进入措辞质检", task_id, fact.get("mismatches", 0))

    pre = await gsb_precheck.run_precheck(task_id)
    if not pre.get("ok"):
        log.warning("题 %d 措辞质检没跑成，继续走核验：%s", task_id, pre.get("message", ""))

    report = await gsb_verifier.run_verify(task_id)
    if report.get("overall") == "block":
        blocked = [i["message"] for i in report.get("items", []) if i["level"] == "block"]
        with session() as db:
            task = db.get(Task, task_id)
            if task is not None:
                task.auto_error = ("本地核验有红项，未送质检：" + "；".join(blocked[:4]))[:2000]
        bus.publish("tasks", {"type": "task", "id": task_id})
        return {"ok": False, "stage": "verify", "blocked": blocked}

    qc = await qa_bridge.gsb_qc(task_id)
    with session() as db:
        task = db.get(Task, task_id)
        if task is not None:
            task.gsb_qc = qc
            task.auto_error = _qc_note(qc)[:2000]
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {**qc, "precheck": pre, "factcheck": fact}


def _qc_note(qc: dict) -> str:
    """把质检结论折成一句给人看的话。通过时返回空串，清掉上一轮的报错。

    INCOMPLETE 单独一档：它是平台侧没跑成（查重池连不上、GitHub Token 缺失、
    轨迹取不到），不是这道题有问题。混进「被打回」里会让人跑去改理由，
    而实际上该做的是过会儿再跑一次。
    """
    if not qc.get("ok"):
        return f"质检未完成：{qc.get('error', '')}"
    if qc.get("passed"):
        return ""
    summary = qc.get("summary", "")
    if qc.get("incomplete"):
        return f"质检未跑完，稍后重跑：{summary}"
    rule = qc.get("hit_rule_label") or qc.get("hit_rule") or ""
    head = f"质检{'废弃' if qc.get('conclusion') == 'DISCARD' else '打回'}"
    return f"{head}（{rule}）：{summary}" if rule else f"{head}：{summary}"


# ---------------- 巡检主体 ----------------
# 三步扫描的先后不能换：
# 1. 先收养孤儿，把「容器早就退了、账还没记」的 run 补成结束状态，否则它在后面两步
#    里都还是 RUNNING，既判不了异常也配不了对，会一直卡着占着调度槽位。
# 2. 再处理异常。异常处理会把坏掉的那一侧退回队列，于是它在配对扫描里就不再满足
#    「两侧都 FINISHED」，不会被当成可以推进的题。
# 3. 最后扫配对。反过来先扫配对的话，一侧刚被判异常、另一侧正常结束时，
#    会拿着一份坏材料去开分析。

def _pairs_ready() -> list[int]:
    """两侧都正常结束、还没进分析的题。"""
    with session() as db:
        out = []
        for task in db.execute(select(Task).where(Task.status.notin_(
                (ANALYZING, NEEDS_ATTENTION, DISCARDED)))).scalars():
            if task.analysis_status != ANALYSIS_IDLE:
                continue
            runs = db.query(TaskRun).filter(TaskRun.task_id == task.id).all()
            if len(runs) != 2 or any(r.status != RUN_FINISHED for r in runs):
                continue
            if any(abnormal_reason(r) for r in runs):
                continue
            out.append(task.id)
        return out


async def _scan_orphans() -> int:
    """收养没人送终的 run：状态还是 RUNNING，容器却已经退出了。返回补记账的条数。

    正常情况下是 runner 的协程守到容器结束再收尾。但协程自己可能先死——进程重启、
    任务被取消、或者 runner 里抛了没接住的异常——这时容器还在跑，跑完也没人记账，
    这一侧就永远停在 RUNNING：调度器的槽位一直被占着，配对扫描也永远等不到它结束。

    关键是**先收尾、再判异常**。容器退出码为 0、轨迹也落盘了，说明这是一次跑完的运行，
    只是没人记账；直接按「容器不见了」判异常会把一次成功的运行整个清掉重跑。所以这里
    只补记账，让它进入正常的结束状态，好不好留给下一轮 _scan_abnormal 按同一套标准判。
    """
    # 局部导入：runner 在模块级就 import 了 watchdog，写在文件头会成环
    from app.services import runner
    from app.services.scheduler import scheduler

    adopted = 0
    with session() as db:
        stale = [(r.id, r.container_name) for r in db.execute(
            select(TaskRun).where(TaskRun.status == RUN_RUNNING)).scalars()]
    for run_id, name in stale:
        if run_id in scheduler.running:
            continue  # 还有协程守着，不插手
        state = await dockerx.container_state(name)
        if state == "running":
            continue
        code = await dockerx.container_exit_code(name) if state else None
        log.warning("run %s 的容器 %s 已是 %s 但没人收尾，补记账",
                    run_id, name, state or "不存在")
        # 容器没了只说明容器没了，不等于人按了停止。当成人工停止会让下面的
        # 异常扫描直接放行，这一侧就永远卡在非 FINISHED 上，配对也永远凑不齐。
        await runner.finalize(run_id, exit_code=code, result_event={},
                              container_gone=(state == ""))
        adopted += 1
    return adopted


async def _recount_output(run_id: int) -> bool:
    """重新实测这一侧的产出。确实有东西就把结论补正回库里，返回 True。

    收尾读到的零改动有两种假法：产物已经 commit（工作区自然干净），
    或者容器刚退、文件还没同步过来。等到巡检这一刻，两者都已经不成立了。
    """
    from app.services import runner

    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return False
        task = db.get(Task, run.task_id)
        if task is None:
            return False
        ws = config.TaskPaths(task.task_no, run.side).workspace
        base_sha = gsb_repo.snapshot_sha(task.env_snapshot)
    changed, stat = await runner.workspace_output(ws, base_sha)
    if not changed and not stat:
        return False
    log.info("run %s 复核后确认有产出（%s 个文件），撤销「零改动」判定", run_id, changed)
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return False
        verdict = dict(run.verdict or {})
        artifact = dict(verdict.get("artifact") or {})
        artifact["changed_files"] = changed
        verdict["artifact"] = artifact
        run.verdict = verdict
        run.git_diff_stat = stat[:8000]
    _clear_abnormal(run_id)
    return True


def _hold_abnormal(run_id: int, reason: str, recorded: dict) -> bool:
    """暂停期间只记一笔异常，不动手。返回是否记了新的一笔。

    记而不动是为了留下停机期间到底哪几侧跑挂了：暂停一解除，这些侧会照常被重跑，
    界面上也能提前看见等着处理的是哪些。attempt 不加，这一笔不算一次重跑。
    """
    if recorded.get("held") and recorded.get("reason") == reason:
        return False
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return False
        run.abnormal = {**recorded, "reason": reason, "at": utc_now().isoformat(),
                        "attempt": run.attempt, "held": True}
        task_id = run.task_id
    bus.publish("tasks", {"type": "task", "id": task_id})
    return True


def _clear_abnormal(run_id: int) -> None:
    """抹掉这一侧已经不成立的异常记录，并看看题能不能放回流程。"""
    with session() as db:
        run = db.get(TaskRun, run_id)
        if run is None:
            return
        run.abnormal = {}
        task_id = run.task_id
    _revive_if_cleared(task_id)
    bus.publish("tasks", {"type": "task", "id": task_id})


def _revive_if_cleared(task_id: int) -> None:
    """撤销误判之后，把题从「需人工」放回流程。

    配对扫描不看 NEEDS_ATTENTION 的题 —— 那本是对的，人没处理完就不该自动往下走。
    但判成需人工的如果是我们自己，撤销之后就必须把门再打开，否则这道题谁也不动它：
    异常已经不成立了，配对扫描又够不着，它会一直停在那儿，看上去就是看护彻底失灵。
    只在两侧都正常结束、且都没有其它异常时才放回去，其余情形仍然留给人。
    """
    with session() as db:
        task = db.get(Task, task_id)
        if task is None or task.status != NEEDS_ATTENTION:
            return
        runs = db.query(TaskRun).filter(TaskRun.task_id == task_id).all()
        if len(runs) != 2 or any(r.status != RUN_FINISHED for r in runs):
            return
        if any(abnormal_reason(r) for r in runs):
            return
        log.info("题 %s 的异常判定已撤销，放回流程", task.task_no)
        task.status = RUN_DONE
        task.auto_error = ""


async def _scan_abnormal() -> dict:
    # 两个上限先读出来。settings_store 每次取值都要开一个新会话，放进下面的
    # with session() 里就是在已有事务中再开一条连接；SQLite 的库文件在 Docker Desktop
    # 的 bind mount 上，第二条连接跑 PRAGMA journal_mode=WAL 会直接抛 disk I/O error，
    # 于是整轮巡检当场中断——异常不处理、配对不推进，而日志里只有一条看不懂的磁盘报错。
    max_retries = settings_store.get_int("watchdog.max_retries", MAX_RETRIES_DEFAULT)
    max_timeouts = settings_store.get_int("watchdog.max_timeouts", MAX_TIMEOUTS_DEFAULT)
    held_only = paused()
    stats = {"requeued": 0, "discarded": 0, "held": 0}
    with session() as db:
        # 只看还在流程里的题。已经分析完、交上去或废弃的题，它们的 run 每轮都判一遍
        # 也只会得出「没异常」，白扫几百行。
        # 运行中的 run 也要看：容器被 docker prune 之类的操作带走时，它会永远停在 RUNNING。
        candidates = [(r.id, r.container_name, r.status)
                      for r in db.execute(select(TaskRun).join(Task, Task.id == TaskRun.task_id)
                                          .where(Task.status.in_(WATCHED),
                                                 TaskRun.status.in_((RUN_RUNNING, *RUN_END_STATUSES)))
                                          ).scalars()]
    from app.services.scheduler import scheduler

    for run_id, name, status in candidates:
        alive = None
        if status == RUN_RUNNING:
            # 有协程守着的不插手，跟 _scan_orphans 同一条分工线。守着的那个协程正等
            # 容器结束，容器一退它就收尾；而这里看到的「容器不在 running」十有八九就是
            # 那半秒钟的窗口。抢在它前面判，等于把一次刚跑完、甚至跑了一两个小时的运行
            # 当成异常清掉重跑，人只会看到题莫名其妙从头开始。
            # 没人守着的那些由 _scan_orphans 先补成结束状态，下一轮再按结束状态判。
            if run_id in scheduler.running:
                continue
            alive = await dockerx.container_state(name) == "running"
        with session() as db:
            run = db.get(TaskRun, run_id)
            if run is None:
                continue
            reason = abnormal_reason(run, alive)
            over_budget = discard_reason(run, max_retries, max_timeouts)
            recorded = dict(run.abnormal or {})
        if not reason:
            # 判过异常、现在又不成立了：要么是我们判错撤销了，要么是人把环境修好了。
            # 记录留着不清，这一侧会一直挂着一条过期的异常。
            if recorded:
                _clear_abnormal(run_id)
            continue
        if recorded.get("gave_up"):
            continue
        if held_only:
            # 模型或网关停机时开的那个开关。判定照做、异常照记，但一步都不动手：
            # 重跑会把这一侧连 .git 一起删掉重建，停机期间每一侧都会跑挂，真让它跑起来
            # 就是把一整批题清空、再跑满次数废弃掉，而它们缺的只是一次能连上模型的重跑。
            if _hold_abnormal(run_id, reason, recorded):
                log.warning("run %s 异常（%s），异常处理已暂停，只记一笔不动手", run_id, reason)
            stats["held"] += 1
            continue
        if reason.startswith(ZERO_CHANGE_REASON) and await _recount_output(run_id):
            # 收尾那一刻读到的零改动未必作数，详见 runner.workspace_output
            continue
        if over_budget:
            log.warning("run %s 异常（%s），%s，废弃整题", run_id, reason, over_budget)
            await give_up(run_id, f"{reason}（{over_budget}）")
            stats["discarded"] += 1
            continue
        log.info("run %s 异常（%s），重跑", run_id, reason)
        r = await requeue_run(run_id, reason=reason)
        if r["ok"]:
            stats["requeued"] += 1
            continue
        # 重跑准备失败不是这道题的错，是 clone、回退这类环境动作没做成，多半下一轮
        # 就好了，所以不占重跑次数。但也不能无限试下去：连着失败到重跑上限那么多次，
        # 说明环境是真坏了，按废弃处理，别让它每五分钟空转一次。
        fails = int(recorded.get("prep_failures") or 0) + 1
        if fails >= max(1, max_retries):
            await give_up(run_id, f"{reason}；重跑准备连续 {fails} 次失败：{r['message']}")
            stats["discarded"] += 1
            continue
        log.warning("run %s 重跑准备第 %s 次失败：%s，下一轮再试", run_id, fails, r["message"])
        with session() as db:
            run = db.get(TaskRun, run_id)
            if run is not None:
                run.abnormal = {**recorded, "reason": reason, "at": utc_now().isoformat(),
                                "attempt": run.attempt, "prep_failures": fails,
                                "prep_error": r["message"]}
    return stats


def _settle_finished() -> int:
    """两侧都正常跑完的题，从「运行中」挪到「两侧跑完」。返回挪了几道。

    题级状态是从两侧 run 推出来的，而两侧都结束时推不出值（见 derive_task_status），
    于是在这一步之前，只有 advance_pair 会把题写成 RUN_DONE —— 而它排在分析并发额度
    后面。额度就是设置里那个「分析/质检并发」（默认 2），一道题的分析加质检十几二十
    分钟是常态，跑完的题一多，后面那些只能在队里等额度。等的这一路上，题级状态没人
    动过：容器早就 Exited、产物也齐了，界面上却一直是「运行中」。

    而巡检每轮都看见它们，只是既开不了推进（没额度）、又不管题级状态，于是看上去像是
    连看门狗都刷不过来。所以状态不跟着额度走：两侧一正常结束就落 RUN_DONE，推进照旧
    排队等额度，界面上显示的是「等提交产物与分析」—— 它确实在等的就是这个。

    题级 finished_at 也在这里补。整条正常路径上从没人写过它，而列表按它排序、今日统计
    也数它，于是跑完的题一律排在最后、当天产出永远是 0。取两侧较晚的那个结束时刻，
    而不是此刻：巡检可能隔了几分钟甚至跨了一次重启才扫到。
    """
    moved: list[int] = []
    with session() as db:
        for task in db.execute(select(Task).where(Task.status.in_(SCHEDULABLE))).scalars():
            runs = db.query(TaskRun).filter(TaskRun.task_id == task.id).all()
            if len(runs) != 2 or any(r.status != RUN_FINISHED for r in runs):
                continue
            if any(abnormal_reason(r) for r in runs):
                continue  # 异常扫描会把它退回重跑，别让它先顶着「跑完了」的名义
            task.status = RUN_DONE
            task.finished_at = task.finished_at or max(
                (as_utc(r.finished_at) for r in runs if r.finished_at), default=utc_now())
            log.info("题 %s 两侧都正常跑完，转两侧跑完，等额度推进", task.task_no)
            moved.append(task.id)
    for tid in moved:
        bus.publish("tasks", {"type": "task", "id": tid})
    return len(moved)


def _settle_stopped() -> int:
    """人按了停止、两侧都停下来的题，从「运行中」挪到「需人工」。返回挪了几道。

    题级状态是从两侧 run 推出来的：有一侧在跑就是 RUNNING，有一侧在等就是 QUEUED，
    两侧都结束了就推不出来，交给巡检。而巡检对人工停止的态度是「不碰」——这本是对的，
    人停下来多半是要去改配置，悄悄重跑会盖掉他刚改的东西。但「不碰」只管住了这一侧
    的 run，没人来收题级状态：异常扫描放行、配对扫描又只认两侧 FINISHED，于是两个容器
    早就 Exited 了，题还挂着「运行中」，界面上连「废弃」都点不了（那个按钮在运行中不亮）。

    所以这一步专收这种题：两侧都结束、都不算异常、又不是都正常跑完 —— 按前面那几步
    的排除法，剩下的只能是被人停掉的。转到「需人工」，详情页上会亮出「重跑 X 侧」与
    「废弃」，人自己决定下一步。真异常的题不归这里管，异常扫描那步已经重跑、废弃
    或挂起了它们。
    """
    moved: list[int] = []
    with session() as db:
        for task in db.execute(select(Task).where(Task.status.in_(SCHEDULABLE))).scalars():
            runs = db.query(TaskRun).filter(TaskRun.task_id == task.id).all()
            if len(runs) != 2 or any(r.status not in RUN_END_STATUSES for r in runs):
                continue
            if all(r.status == RUN_FINISHED for r in runs):
                continue  # 两侧都正常跑完，_settle_finished 已经收过了
            if any(abnormal_reason(r) for r in runs):
                continue  # 真异常，异常扫描已经处理过或正挂起等着
            stopped = sorted(r.side for r in runs if r.status != RUN_FINISHED)
            task.status = NEEDS_ATTENTION
            task.finished_at = task.finished_at or utc_now()
            task.auto_error = (f"{'、'.join(stopped)} 侧被人工停止，两侧容器都已结束；"
                               f"重跑{'这一侧' if len(stopped) == 1 else '两侧'}或废弃整题")
            log.info("题 %s 两侧都已停下（%s 侧为人工停止），转需人工",
                     task.task_no, "、".join(stopped))
            moved.append(task.id)
    for tid in moved:
        bus.publish("tasks", {"type": "task", "id": tid})
    return len(moved)


async def _reconcile_containers() -> int:
    """校正容器台账：库里写着「保留中」而容器其实已经不在了的，改回去。返回改了几条。

    container_exists 是各处动作各自写的，而销毁容器的路径不止一条：推进成功后自动销毁、
    人工点销毁、废弃整题、`docker prune`、机器重启后 Docker 自己清。漏写任何一处，
    详情页就会一直显示「容器保留 2/2」——而人正是看着这个数字决定要不要进容器里捞东西。
    一次 `docker ps` 就能把全部台账对齐，比在每个动作里各写一遍可靠。
    """
    alive = {c["name"] for c in await dockerx.list_task_containers()}
    fixed = 0
    with session() as db:
        for run in db.execute(select(TaskRun).where(TaskRun.container_exists.is_(True))).scalars():
            if run.container_name and run.container_name not in alive:
                run.container_exists = False
                fixed += 1
    if fixed:
        log.info("容器台账校正：%s 条记录的容器其实已经不在了", fixed)
    return fixed


def _reap_advances() -> None:
    """把跑完的后台推进从台账上划掉，顺带把没接住的异常记一笔。

    不记的话这种异常就彻底无声：create_task 出来的任务谁也不 await 它，抛了什么
    只留在 Task 对象里，而那个对象下一刻就被丢掉了。
    """
    for task_id, job in list(_advance_tasks.items()):
        if not job.done():
            continue
        _advance_tasks.pop(task_id, None)
        if job.cancelled():
            continue
        if exc := job.exception():
            log.error("题 %s 推进异常：%s: %s", task_id, type(exc).__name__, exc)


async def _advance_one(task_id: int) -> None:
    r = await advance_pair(task_id)
    if not r.get("ok"):
        log.warning("题 %s 推进失败：%s", task_id, r.get("message") or r.get("error"))


def _advance_slots() -> int:
    """还能再开几个后台推进。额度就是设置里那个「分析/质检并发」。

    推产物之后的每一步都在调模型，所以这个数就是同时在跑的模型调用数。兜底值要和
    settings_store 里的 Spec 默认值一致，不然「设置页显示 30、实际按 2 跑」这种账
    没人对得出来。
    """
    limit = max(1, settings_store.get_int("auto.max_parallel", 30))
    return max(0, limit - len(_advance_tasks))


def _advancing_now(task_id: int) -> bool:
    """这道题此刻是不是已经在推进。

    create_task 排到事件循环里才真正开跑，在那之前题的状态还是原样，扫描照样会挑中它；
    所以占位看的是 _advance_tasks 而不是题的状态，不能等 advance_pair 自己去 _advancing。
    """
    return task_id in _advance_tasks or task_id in _advancing


def _start_advance(task_id: int) -> None:
    """占一个额度把推进跑起来。额度与重复由调用方先判。"""
    _advance_tasks[task_id] = asyncio.create_task(
        _advance_one(task_id), name=f"advance-{task_id}")


# ---------------- 质检积压 ----------------
# 分析跑完自动接一道质检，这条路走通了就不会有积压。会有积压是因为质检也在调模型：
# 账单被拒、网关抽风、后端重启，任何一次没跑成，题就停在「待质检」上，而它已经过了
# 配对扫描那一关（analysis_status 是 DONE），后面没有任何一步会再碰它。
#
# 这一步专收这种题：结论已经有了、两道质检还没都放行的，一律重新排进闸门。判「该不该
# 再跑」用的是两个模块自己的 skip_reason，所以不会对着一段没改过的话反复烧调用。

def _quality_backlog() -> list[int]:
    """结论已出、两道质检还没都走完的题，按题号排。

    口径借 gsb_precheck.ready_ids，不在这里另写一套：CLI 和页面上那个 ready 列表用的
    是同一个函数，两处各判一套的话，人看到「该质检 12 道」而巡检自己捡了 15 道，
    对不上账的时候没人说得清哪边是对的。
    """
    from app.services import gsb_precheck

    return gsb_precheck.ready_ids()


async def _gate_one(task_id: int) -> None:
    r = await run_quality_gate(task_id)
    if not r.get("ok"):
        log.info("题 %s 补跑质检没有全过：%s", task_id, r.get("error") or r.get("summary") or "")


def _start_gate(task_id: int) -> None:
    """补跑质检也占推进额度。两者都在调模型，分开算额度等于把并发悄悄翻倍。"""
    _advance_tasks[task_id] = asyncio.create_task(
        _gate_one(task_id), name=f"gate-{task_id}")


async def _scan_quality_backlog() -> int:
    """把卡在待质检的题重新排进闸门。返回这一轮新起了几个。

    排在配对之后：新跑完的题该优先拿到结论，补跑的这批已经等了一轮，再等一轮无妨。
    人工排的队又比扫描自己捡的优先，和配对那边同一个道理。
    """
    started = 0
    while _gate_wanted and _advance_slots():
        task_id = _gate_wanted.pop(0)
        if _advancing_now(task_id):
            continue
        log.info("题 %s 是人工点的质检，开始跑事实核验与措辞质检", task_id)
        _start_gate(task_id)
        started += 1
    for task_id in _quality_backlog():
        if not _advance_slots():
            break
        if _advancing_now(task_id) or task_id in _gate_wanted:
            continue
        log.info("题 %s 结论已出但质检没走完，补跑事实核验与措辞质检", task_id)
        _start_gate(task_id)
        started += 1
    return started


def queue_gate(task_id: int) -> dict:
    """把一道题排进后台质检，不等它跑完。

    和 queue_advance 同一个理由：两道质检都在调模型，一道题几分钟，批量点十道那条
    HTTP 请求必然先超时，而动作已经在后台跑起来了 —— 人看到的是一个失败，回头再点
    一遍，于是同一道题被质检两遍。
    """
    _reap_advances()
    if _advancing_now(task_id):
        return {"ok": True, "started": False, "message": "这道题正在跑质检"}
    if task_id in _gate_wanted:
        return {"ok": True, "started": False,
                "message": f"已在质检队列里等额度，第 {_gate_wanted.index(task_id) + 1} 位"}
    if _advance_slots():
        _start_gate(task_id)
        return {"ok": True, "started": True, "message": "已开始跑事实核验与措辞质检"}
    _gate_wanted.append(task_id)
    wake()
    return {"ok": True, "started": False,
            "message": f"分析并发已满，排在第 {len(_gate_wanted)} 位等额度"}


# ---------------- 模型恢复探测 ----------------
# 账单被拒不是偶发故障，它会一直拒到人去结账为止，而这期间每一次分析、每一次质检都
# 会失败一次并把题留在 FAILED / ERROR 上。等账结清了，这批题没有任何机制会自己回来：
# 分析失败的靠人换 Key 才触发 retry_failed_analyses，质检 ERROR 的连这个都没有。
#
# 所以这里主动探一下。探测本身也是一次模型调用，不能每轮都探：没有积压时一次都不探，
# 有积压时按 PROBE_GAP_S 节流。探通了就把两类都放回流程，剩下的交给上面两步扫描。

PROBE_GAP_S = 600
_last_probe_at = 0.0
_llm_ok = True


# 明确不是模型问题的失败。这一步重试多少次结果都一样，放回流程只会让它下一轮再报
# 同样的错，从此每轮空转。目前只有一种：这道题压根没有轨迹可核。
_NOT_LLM_ERROR = re.compile(r"没有轨迹|无法核验|轨迹文件缺失")


def _llm_stalled(report: dict) -> bool:
    """这一档是不是「模型没答上来」，而不是这道题本身有问题。

    两道质检失败时会打 llm_error 标记，有标记就只认标记。

    没有标记的是建这个标记之前留下的老行，只能看报错文本 —— 而这里用的是排除法，
    不是白名单。白名单那版漏掉了一多半：CLI 被账单拦下时打的是「Failed to reach the
    Cursor API. If you are behind a corporate proxy...」，一个关键词都不沾，26 道
    ERROR 里有 16 道就这么永远卡着。CLI 的报错措辞是它自己的事，穷举不完。

    两个方向的代价不对等，所以默认按「是模型问题」算：误判成模型问题，代价是白跑一次
    质检；误判成任务问题，代价是这道题再也没人管。
    """
    if not report.get("error"):
        return False
    if "llm_error" in report:
        return bool(report["llm_error"])
    return not _NOT_LLM_ERROR.search(str(report.get("error") or ""))


def _blocked_by_llm() -> tuple[int, int]:
    """因为模型调不通而卡住的题有多少。返回 (分析失败的, 质检没跑完的)。

    只认「模型不通」这一类原因。分析失败的原因五花八门（轨迹缺失、输出解不开、
    结论认不出来），拿那些题去触发探测等于每十分钟白烧一次调用，而它们重跑多少次
    都是同样的结果。
    """
    analyses = qc = 0
    with session() as db:
        for task in db.execute(select(Task).where(
                Task.analysis_status == ANALYSIS_FAILED)).scalars():
            if llm.classify(task.auto_error or "")[1] is False:
                analyses += 1  # 不可重试 = 账单 / 鉴权 / 模型名，正是要等恢复的那类
        for task in db.execute(select(Task).where(Task.status.in_(SETTLING))).scalars():
            if _llm_stalled(task.factcheck or {}) or _llm_stalled(task.precheck or {}):
                qc += 1
    return analyses, qc


def _release_llm_blocked() -> int:
    """把因为模型不通而卡住的题放回流程。返回放回了几道。

    质检那两档只复位成 IDLE，不在这里直接跑：跑不跑、跑几道要走额度，
    那是 _scan_quality_backlog 的事。这里只负责把门打开。
    """
    freed = len(retry_failed_analyses())
    with session() as db:
        for task in db.execute(select(Task).where(Task.status.in_(SETTLING))).scalars():
            touched = False
            if _llm_stalled(task.factcheck or {}):
                task.factcheck_status, task.factcheck, touched = FACTCHECK_IDLE, {}, True
            if _llm_stalled(task.precheck or {}):
                task.precheck_status, task.precheck, touched = PRECHECK_IDLE, {}, True
            if touched:
                task.auto_error = ""
                freed += 1
    return freed


async def _scan_llm_recovery() -> int:
    """模型恢复了就把卡住的题全放回流程。返回放回了几道。"""
    global _last_probe_at, _llm_ok
    analyses, qc = _blocked_by_llm()
    if not (analyses or qc):
        _llm_ok = True
        return 0
    now = time.time()
    if now - _last_probe_at < PROBE_GAP_S:
        return 0
    _last_probe_at = now
    probe = await llm.probe_ping()
    if not probe.get("ok"):
        if _llm_ok:
            log.warning("模型仍然调不通（%s），%s 道分析、%s 道质检等着恢复",
                        probe.get("message", "")[:200], analyses, qc)
        _llm_ok = False
        return 0
    _llm_ok = True
    freed = _release_llm_blocked()
    if freed:
        log.info("模型恢复调用（%s），把 %s 道卡住的题放回流程", probe.get("message", ""), freed)
        wake()
    return freed


async def _scan_pairs() -> int:
    """把该推进的题交给后台，不等它跑完。返回这一轮新起了几个。

    人工排的队先走：那是人在界面上点过的，而扫描自己捡到的题等一轮无妨。额度占满时
    两边剩下的都留到下一轮 —— 扫描那批的状态没变，照样挑得到；人工那批在队列里等着。
    """
    _reap_advances()
    started = 0
    while _advance_wanted and _advance_slots():
        task_id = _advance_wanted.pop(0)
        if _advancing_now(task_id):
            continue
        log.info("题 %s 是人工点的推进，开始推产物、写描述、质检", task_id)
        _start_advance(task_id)
        started += 1
    for task_id in _pairs_ready():
        if not _advance_slots():
            break
        if _advancing_now(task_id) or task_id in _advance_wanted:
            continue
        log.info("题 %s 两侧都跑完了，交给后台推产物、写描述、质检", task_id)
        _start_advance(task_id)
        started += 1
    return started


async def tick() -> dict:
    """跑一轮定时任务。三步的先后都不能换，理由见上面那段注释。"""
    adopted = await _scan_orphans()
    stats = await _scan_abnormal()
    # 收题级状态的两步都排在异常扫描之后：它们靠「这一侧不算异常」这个结论做排除，
    # 抢在前面会把一道马上要被退回重跑的题先说成跑完了。
    # 也都排在配对之前：推进是按额度慢慢来的，状态不能跟着它一起等。
    stats["run_done"] = _settle_finished()
    stats["settled"] = _settle_stopped()
    # 探测排在推进前面：账单刚恢复时，这一步会把上一轮卡住的题放回流程，
    # 紧接着的两步扫描当轮就能把它们排上，不必再等一个周期。
    stats["freed"] = await _scan_llm_recovery()
    advanced = await _scan_pairs()
    # 补跑质检排在配对之后，共用同一份额度：新跑完的题该优先拿到结论
    stats["gated"] = await _scan_quality_backlog()
    # 台账校正放最后：上面几步可能刚销毁过容器，这时对齐一次正好
    fixed = await _reconcile_containers()
    return {"adopted": adopted, **stats, "advanced": advanced, "container_fixed": fixed}


def alive() -> bool:
    return bool(_task) and not _task.done()


def ensure_alive() -> bool:
    """循环没了就地重启。返回是否做了重启。

    巡检停摆不会立刻显形：容器照常跑，只是跑坏的没人重跑、跑完的没人配对，题一道道
    沉进队列底下，要等到发现「怎么一晚上什么都没出来」才知道。所以由调度那一侧每轮
    看一眼，两个循环互相盯着。
    """
    global _task
    if _stopping or alive():
        return False
    exc = _task.exception() if _task and not _task.cancelled() else None
    log.error("巡检循环已停止（%s），就地重启", exc or "被取消")
    _task = asyncio.create_task(_loop(), name="watchdog-loop")
    return True


async def _loop() -> None:
    global _last_tick_at, _last_error, _last_stats
    while not _stopping:
        began = utc_now()
        try:
            stats = await tick()
            _last_tick_at, _last_error, _last_stats = utc_now(), "", stats
            # 每轮都留一行。巡检绝大多数时候什么都不做，一声不吭的话，「它到底还在不在
            # 按周期跑」就完全无从判断 —— 出了问题只能靠猜。
            log.info("巡检 · 补记账 %s · 重跑 %s · 废弃 %s · 挂起 %s · 转待分析 %s · 转人工 %s"
                     " · 恢复放回 %s · 起推进 %s · 补质检 %s（在跑 %s） · 耗时 %.1fs",
                     stats["adopted"], stats["requeued"], stats["discarded"], stats["held"],
                     stats["run_done"], stats["settled"], stats["freed"], stats["advanced"],
                     stats["gated"], len(_advance_tasks),
                     (utc_now() - began).total_seconds())
        except asyncio.CancelledError:
            raise
        except BaseException as exc:  # noqa: BLE001
            # 见 scheduler._loop 的同款注释：只接 Exception 会让循环无声退出
            _last_error = f"{type(exc).__name__}: {exc}"
            log.exception("巡检异常")
        interval = max(30, settings_store.get_int("watchdog.interval_seconds", INTERVAL_DEFAULT))
        try:
            await asyncio.wait_for(_wake.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
        _wake.clear()


def reset_stale_analyses() -> list[str]:
    """把上一个进程留下的「分析中」复位，返回被复位的题号。

    analysis_status 记的是一个进程内的协程在不在跑，而协程随进程一起没了，库里那个
    RUNNING 还留着。配对扫描只挑 IDLE 的题，于是这些题谁也不会再碰：界面上永远显示
    分析中，人只能挨个去点重新分析。产物都在分支上了，重跑一次分析没有副作用。
    """
    out: list[str] = []
    with session() as db:
        for task in db.execute(select(Task).where(
                Task.analysis_status == ANALYSIS_RUNNING)).scalars():
            task.analysis_status = ANALYSIS_IDLE
            if task.status == ANALYZING:
                task.status = RUN_DONE
            task.auto_error = ""
            out.append(task.task_no)
    return out


async def start() -> None:
    global _task, _stopping
    _stopping = False
    if stale := reset_stale_analyses():
        log.warning("上次进程留下 %s 道题卡在分析中，已复位重排：%s", len(stale), "、".join(stale))
    _task = asyncio.create_task(_loop(), name="watchdog-loop")


async def stop() -> None:
    global _stopping
    _stopping = True
    _wake.set()
    for job in _advance_tasks.values():
        job.cancel()
    _advance_tasks.clear()
    _advance_wanted.clear()
    _gate_wanted.clear()
    if _task:
        _task.cancel()


# ---------------- 人工入口 ----------------

def retry_failed_analyses() -> list[str]:
    """把分析失败的题放回流程，返回被放回的题号。

    分析挂掉多半挂在凭据上，人换完 Key 就该自己接着跑。只挑两侧都正常结束的题：
    产物都在分支上了，缺的只是那份对比结论，重来一次没有副作用。
    """
    out: list[str] = []
    with session() as db:
        for task in db.execute(select(Task).where(
                Task.analysis_status == ANALYSIS_FAILED)).scalars():
            runs = db.query(TaskRun).filter(TaskRun.task_id == task.id).all()
            if len(runs) != 2 or any(r.status != RUN_FINISHED for r in runs):
                continue
            if any(abnormal_reason(r) for r in runs):
                continue
            task.analysis_status = ANALYSIS_IDLE
            task.auto_error = ""
            if task.status == NEEDS_ATTENTION:
                task.status = RUN_DONE
            out.append(task.task_no)
    if out:
        log.info("凭据已更新，把分析失败的题 %s 放回流程", "、".join(out))
        wake()
    return out


def queue_advance(task_id: int) -> dict:
    """把一道题排进后台推进（推产物 + 分析 + 质检），不等它跑完。

    列表页上那个「提交产物并分析」走这里而不是 advance_pair：推产物之后要跑 GSB 分析
    和质检，两步都在调模型，一道题十几二十分钟是常态。同步等着的话，批量点十道那条
    HTTP 请求必然先超时，而动作已经在后台跑起来了 —— 人看到的是一个失败，回头再点一遍，
    于是同一道题的产物被推两遍（advance_pair 的 _advancing 能挡住，但界面上说不清）。

    返回的 started 区分「已经开跑」和「在队列里等额度」，界面要照原话说给人听：
    后者看上去什么都没发生，不说清楚就会被当成没点动。
    """
    _reap_advances()
    if _advancing_now(task_id):
        return {"ok": True, "started": False, "message": "这道题正在推进中"}
    if task_id in _advance_wanted:
        return {"ok": True, "started": False,
                "message": f"已在推进队列里等额度，第 {_advance_wanted.index(task_id) + 1} 位"}
    if _advance_slots():
        _start_advance(task_id)
        return {"ok": True, "started": True, "message": "已开始推产物与分析"}
    _advance_wanted.append(task_id)
    # 催一次巡检：额度是随推进结束腾出来的，而巡检默认五分钟一轮，不催的话队首那道题
    # 可能在额度早就空了的情况下还干等着。
    wake()
    return {"ok": True, "started": False,
            "message": f"分析并发已满，排在第 {len(_advance_wanted)} 位等额度"}


async def manual_rerun(task_id: int, sides: tuple[str, ...] = config.SIDES) -> dict:
    """人工重跑。动作与自动重跑完全一致，区别是不看 attempt 上限并把计数清零。"""
    with session() as db:
        ids = [r.id for r in db.query(TaskRun).filter(TaskRun.task_id == task_id).all()
               if r.side in sides]
    if not ids:
        return {"ok": False, "message": f"没有 {'、'.join(sides)} 侧的运行记录"}
    msgs = []
    for run_id in ids:
        r = await requeue_run(run_id, reason="人工重跑", reset_attempt=True)
        if not r["ok"]:
            return r
        msgs.append(r["message"])
    return {"ok": True, "message": "；".join(msgs)}
