"""宿主机代理客户端。

后端在容器里，既起不了宿主机上的项目，也拿不到 macOS 的屏幕录制权限，这两件事全部
转交给跑在宿主机上的 host-agent（见仓库根的 host-agent/ 目录）。这里只负责：读口令、
发请求、把宿主路径和容器内挂载路径对上。
"""

from __future__ import annotations

import logging

import httpx

from app import config

log = logging.getLogger("host-agent")

TOKEN_FILE = config.DATA_DIR / "host-agent" / "token"
NOT_RUNNING = "宿主机代理没在跑。到仓库的 host-agent 目录双击「启动宿主机代理.command」，那个窗口留着别关"


def token() -> str:
    try:
        return TOKEN_FILE.read_text("utf-8").strip()
    except OSError:
        return ""


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=config.HOST_AGENT_URL, timeout=40,
                             headers={"X-Agent-Token": token()})


async def _call(method: str, path: str, **kw) -> dict:
    try:
        async with _client() as c:
            r = await c.request(method, path, **kw)
    except httpx.HTTPError as e:
        log.info("宿主机代理不可达：%s", e)
        return {"ok": False, "reachable": False, "message": NOT_RUNNING}
    try:
        body = r.json()
    except ValueError:
        return {"ok": False, "reachable": True, "message": f"代理返回了非 JSON（HTTP {r.status_code}）"}
    if r.status_code == 401:
        body["message"] = "口令对不上，重启一次宿主机代理让它和后端重新对齐"
    body.setdefault("ok", r.is_success)
    body["reachable"] = True
    return body


async def health() -> dict:
    """代理在不在、ffmpeg 有没有、能录哪几块屏。界面靠它决定按钮是否可点。"""
    res = await _call("GET", "/health")
    res.setdefault("screens", [])
    res.setdefault("recordings", [])
    return res


async def start_project(task_no: str, side: str, commands: list[str]) -> dict:
    paths = config.TaskPaths(task_no, side)
    return await _call("POST", "/project/start", json={
        "task_no": task_no, "side": side,
        "cwd": paths.workspace_host, "commands": commands,
    })


async def project_status(task_no: str, side: str) -> dict:
    return await _call("GET", f"/project/status?key={task_no}/{side}")


async def start_record(task_no: str, side: str, screen: int) -> dict:
    """录屏文件落在 reports/<题号>/ 下，那个目录本来就是这道题的产物归档地。"""
    out_host = f"{config.CODER_ROOT_HOST}/{config.ANALYSIS_DIR}/{task_no}"
    return await _call("POST", "/record/start", json={
        "task_no": task_no, "side": side, "out_dir": out_host, "screen": screen,
    })


async def stop_record(task_no: str, side: str) -> dict:
    res = await _call("POST", "/record/stop", json={"task_no": task_no, "side": side})
    # 代理给的是宿主路径，上传接口读文件用的是容器内的挂载路径，这里换一次
    if res.get("ok") and res.get("file"):
        res["host_file"] = res["file"]
        res["file"] = to_mount(res["file"])
    return res


def to_mount(host_path: str) -> str:
    """宿主路径 → 后端容器里看得到的路径。不在 CODER_ROOT 下的原样返回。"""
    root = config.CODER_ROOT_HOST.rstrip("/")
    if host_path == root or host_path.startswith(root + "/"):
        return str(config.CODER_ROOT_MOUNT) + host_path[len(root):]
    return host_path
