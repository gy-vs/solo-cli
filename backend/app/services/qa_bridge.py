"""调用 solo-qa 的查重与质检。

solo-qa 的依赖 pin 了具体版本，直接装进本项目会和 fastapi/pydantic 打架，
所以走容器：把 `backend/bridges/*.py` 挂进它自己的后端镜像执行，stdin/stdout 传 JSON。
桥接脚本内部只调只读函数，不写它的库、不碰飞书，细节见脚本头部注释。
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from app import config
from app.db import session
from app.models import Task
from app.services import dockerx, settings_store

log = logging.getLogger("qa_bridge")

SCRIPT_DEDUP = "qa_dedup.py"
SCRIPT_GSB_QC = "qa_gsb_qc.py"

# 同时最多起几个质检容器。这个额度和「分析/质检并发」是两回事，必须分开：
# 那个数管的是同时在跑几个模型调用，模型在别人的机器上，开三十个只是三十条 HTTP 流；
# 而这一步每道题要起一个 solo2-backend 容器，占的是本机内存。
#
# 分不开的代价是实打实的：模型并发调到 30 之后，闸门的前两步（事实核验、措辞质检）
# 各要一两分钟，跑完就一起涌到这一步，于是三十个容器同时起。Docker Desktop 默认只
# 分到几个 G，这个镜像四百多兆、跑起来还要装 Python 运行时，撞上去就是整批 OOM，
# 而 OOM 掉的那几道会被记成「质检未完成」，看上去像是平台的问题。
#
# 四个是按「Docker 分到 8G、单个容器算 600M 峰值」估的，留了一倍余量。机器内存给得
# 多就调大，这个数和模型并发没有任何关系。
QC_PARALLEL_DEFAULT = 4
_slots: asyncio.Semaphore | None = None
_slots_limit = 0


def _gate() -> asyncio.Semaphore:
    """取容器额度的信号量，额度改了就换一个新的。

    不在模块级建：Semaphore 会绑定到创建它时的事件循环，而测试里每个用例各起一个
    循环，跨循环复用同一把会直接抛错。
    """
    global _slots, _slots_limit
    limit = max(1, settings_store.get_int("qc.max_parallel", QC_PARALLEL_DEFAULT))
    if _slots is None or _slots_limit != limit:
        _slots, _slots_limit = asyncio.Semaphore(limit), limit
    return _slots


def project_host() -> str:
    return settings_store.get("qc.project_host").rstrip("/")


def available() -> tuple[bool, str]:
    """质检是否具备执行条件。只看本地可检查的部分，远程库连通性留给实际调用。"""
    if not settings_store.get_bool("qc.enabled", True):
        return False, "质检未启用"
    root = project_host()
    if not root:
        return False, "未配置 solo-qa 项目路径"
    return True, ""


async def _run(script: str, payload: dict, *, timeout_s: int, mounts: list[str] | None = None) -> dict:
    """起一个质检容器跑桥接脚本。等额度的时间不算进超时。

    超时是给「容器起来了却不返回」用的，而排队等额度是正常的，两者混在一起会让
    队尾那几道题一进容器就被判超时 —— 而它们一秒都还没跑。
    """
    async with _gate():
        return await _run_now(script, payload, timeout_s=timeout_s, mounts=mounts)


async def _run_now(script: str, payload: dict, *, timeout_s: int,
                   mounts: list[str] | None = None) -> dict:
    root = project_host()
    image = settings_store.get("qc.image") or "solo2-backend:latest"
    cmd = [
        dockerx.docker_bin(), "run", "--rm", "-i",
        # 用宿主机上的最新源码覆盖镜像里构建时的那份快照
        "-v", f"{root}/backend:/app/backend:ro",
        "-v", f"{root}/.env:/app/.env:ro",
        "-v", f"{config.BRIDGE_DIR_HOST}:/bridge:ro",
        *(mounts or []),
        "-w", "/app", "-e", "PYTHONPATH=/app",
        "--entrypoint", "python", image, f"/bridge/{script}",
    ]
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(data), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        return {"ok": False, "error": f"{script} 超过 {timeout_s // 60} 分钟未返回"}
    text = out.decode("utf-8", "replace").strip()
    tail = err.decode("utf-8", "replace").strip()[-2000:]
    if not text:
        return {"ok": False, "error": f"{script} 无输出（exit={proc.returncode}）：{tail[-500:]}"}
    try:
        # 桥接只往 stdout 写一个 JSON，但镜像层偶尔会插警告，取最后一行兜底
        return json.loads(text if text.startswith("{") else text.splitlines()[-1])
    except json.JSONDecodeError:
        return {"ok": False, "error": f"{script} 输出不是 JSON：{text[:300]}"}


# ============================================================
# 查重：规则 A + 规则 C
# ============================================================

async def dedup(items: list[dict], *, rules: tuple[str, ...] = ("A", "C"), timeout_s: int = 900) -> dict:
    """items: [{key, user_prompt, repo_id, session_id}]。同批题目之间也会互查。"""
    ok, why = available()
    if not ok:
        return {"ok": False, "error": why}
    return await _run(SCRIPT_DEDUP, {"items": items, "rules": list(rules), "submitter": "solo-cli"},
                      timeout_s=timeout_s)


def repo_id_of(env_snapshot: str) -> str:
    """从 commit permalink 取 org/repo，与 solo-qa 的 parse_repo_id 同口径。"""
    s = (env_snapshot or "").strip()
    if "github.com/" not in s:
        return ""
    tail = s.split("github.com/", 1)[1]
    parts = [p for p in tail.split("/") if p]
    if len(parts) < 2:
        return ""
    return f"{parts[0]}/{parts[1]}"


# ============================================================
# GSB 质检：走 solo-qa 的 GSB 链路，只取结论
# ============================================================
# 早先这里调的是它的五维质检入口，传的是 score_delivery、desc_planning 那套字段。
# 那套评分连同字段一起废弃了，GSB 改成两侧对比加一个理由，字段完全不同，所以这条
# 桥接实际上早就调不通了，只是没人调用它，一直没暴露出来。

# solo-qa 的 DATA_DIR，轨迹必须挂进这个目录下才会走本地解析
QA_DATA_DIR = "/app/data"
TRACE_SUBDIR = "solo-cli-trace"


async def gsb_qc(task_id: int, *, timeout_s: int = 0) -> dict:
    """对一道题的 GSB 结论跑平台口径的质检。只读 solo-qa，不写它的库。

    要送两侧的轨迹：它的 T3 规则要在轨迹里找有没有把 GSB 的评判标准泄漏给模型，
    单送结论查不出这类问题。

    轨迹挂进它的 `DATA_DIR` 而不是随便找个路径：它的轨迹读取会先拿相对路径在
    DATA_DIR 下找本地文件，找到就直接解析，找不到才回源对象存储。挂在别处就等于
    逼它走一趟本来不需要的网络。
    """
    ok, why = available()
    if not ok:
        return {"ok": False, "error": why}

    from app.services import gsb_uploader

    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "error": "任务不存在"}
        task_no = t.task_no
    try:
        data = await gsb_uploader.build_values_for(task_id)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"装配提交字段失败：{exc}"}

    mounts: list[str] = []
    traces: dict[str, str] = {}
    for side in config.SIDES:
        paths = config.TaskPaths(task_no, side)
        local = _exported_trace(paths.export)
        if local is None:
            return {"ok": False, "error": f"{side} 侧没有导出的轨迹文件，无法质检"}
        rel = f"{TRACE_SUBDIR}-{side}"
        mounts += ["-v", f"{paths.export_host}:{QA_DATA_DIR}/{rel}:ro"]
        traces[side] = f"{rel}/{local.name}"

    payload = {
        "submission": data,
        "traces": traces,
        "submitter": "solo-cli",
        "task_no": task_no,
        # 录屏是人工环节，质检这一步必然还没录，见桥接脚本头部说明
        "defer_screencast": True,
    }
    timeout_s = timeout_s or max(120, settings_store.get_int("qc.timeout_minutes", 15) * 60)
    return await _run(SCRIPT_GSB_QC, payload, timeout_s=timeout_s, mounts=mounts)


def _exported_trace(export_dir: Path) -> Path | None:
    files = sorted(export_dir.glob("*.jsonl")) if export_dir.is_dir() else []
    return files[-1] if files else None


async def probe() -> dict:
    """设置页的连通性探测：镜像在不在、能不能连上 solo-qa 的库。"""
    ok, why = available()
    if not ok:
        return {"ok": False, "message": why}
    root = project_host()
    for p in (f"{root}/backend", f"{root}/.env"):
        # 后端在容器里，只能看挂载进来的路径，这里只检查宿主路径的拼写是否可疑
        if not p.startswith("/"):
            return {"ok": False, "message": f"路径必须是宿主机绝对路径：{p}"}
    image = settings_store.get("qc.image") or "solo2-backend:latest"
    if not await dockerx.image_present(image):
        return {"ok": False, "message": f"镜像 {image} 不存在，先在 solo-qa 项目里 docker compose build"}
    r = await dedup([{"key": "probe", "user_prompt": "连通性探测，不参与判定。", "repo_id": "", "session_id": ""}],
                    rules=("A",), timeout_s=180)
    if not r.get("ok"):
        return {"ok": False, "message": r.get("error", "查重探测失败")}
    meta = r.get("meta") or {}
    return {"ok": True, "message": f"已连上 solo-qa 库，历史提交 {meta.get('max_submission_id', 0)} 条"}
