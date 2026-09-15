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
SCRIPT_QC = "qa_qc.py"

# solo-qa 的五维字段名 → 本项目的维度键
DIM_MAP = {
    "delivery": "score_delivery",
    "instruction": "score_instruction",
    "planning": "score_planning",
    "reasoning": "score_reasoning",
    "execution": "score_execution",
}
DESC_MAP = {k: f"desc_{k}" for k in DIM_MAP}


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
    root = project_host()
    image = settings_store.get("qc.image") or "solo-qa-backend:latest"
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
# 质检：完整链路，只取结论
# ============================================================

def build_submission(t: Task) -> tuple[dict, list[str]]:
    """把一条任务装成 solo-qa 的提交字段。返回 (payload, 缺失字段说明)。"""
    review = t.review or {}
    scores = review.get("scores") or {}
    descs = review.get("descs") or {}
    summary = t.trace_summary or {}

    data = {
        "question_type": t.question_type,
        "difficulty": t.difficulty,
        "languages": t.languages,
        "harness": t.harness or "Claude Code",
        # 表单版本必须和轨迹里的一致，否则质检的交叉校验直接打回；
        # 轨迹解析拿到版本时以它为准，镜像实测值只作兜底
        "harness_version": summary.get("harness_version") or t.harness_version,
        "os_platform": t.os_platform,
        "repro_level": t.repro_level,
        "env_snapshot": t.env_snapshot,
        "user_prompt": t.user_prompt,
        "session_id": t.session_id,
        "turn_id": t.turn_id,
        "other_issues": review.get("other_issues") or "",
    }
    for dim, field in DIM_MAP.items():
        data[field] = scores.get(dim)
    for dim, field in DESC_MAP.items():
        data[field] = (descs.get(dim) or "").strip()

    missing = [k for k, v in data.items() if k != "other_issues" and (v is None or v == "")]
    return data, missing


async def qc_task(task_id: int) -> dict:
    """对一条任务跑质检。只读 solo-qa，不写它的库。"""
    ok, why = available()
    if not ok:
        return {"ok": False, "error": why}
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "error": "任务不存在"}
        data, missing = build_submission(t)
        task_no, trace_file = t.task_no, t.trace_file
    if missing:
        return {"ok": False, "error": "字段不全，先完成五维评审：" + "、".join(missing)}
    if not trace_file or not Path(trace_file).exists():
        return {"ok": False, "error": "没有导出的轨迹文件，无法质检"}

    paths = config.TaskPaths(task_no)
    name = Path(trace_file).name
    size = Path(trace_file).stat().st_size
    mounts = ["-v", f"{paths.export_host}:/trace:ro"]
    timeout_s = max(120, settings_store.get_int("qc.timeout_minutes", 15) * 60)
    payload = {
        "submission": data,
        "trace_path": f"/trace/{name}",
        "trace_name": name,
        "trace_size": size,
        "submitter": "solo-cli",
        "task_no": task_no,
        "round_no": 1,
    }
    return await _run(SCRIPT_QC, payload, timeout_s=timeout_s, mounts=mounts)


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
    image = settings_store.get("qc.image") or "solo-qa-backend:latest"
    if not await dockerx.image_present(image):
        return {"ok": False, "message": f"镜像 {image} 不存在，先在 solo-qa 项目里 docker compose build"}
    r = await dedup([{"key": "probe", "user_prompt": "连通性探测，不参与判定。", "repo_id": "", "session_id": ""}],
                    rules=("A",), timeout_s=180)
    if not r.get("ok"):
        return {"ok": False, "message": r.get("error", "查重探测失败")}
    meta = r.get("meta") or {}
    return {"ok": True, "message": f"已连上 solo-qa 库，历史提交 {meta.get('max_submission_id', 0)} 条"}
