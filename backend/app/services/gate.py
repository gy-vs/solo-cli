"""启动前门禁：泄漏扫描与环境校验。任一 block 级检查不通过则拒绝启动。"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import asdict, dataclass

from app import config
from app.models import Task
from app.services import dockerx, settings_store

_SHA_RE = re.compile(r"/commit/([0-9a-fA-F]{40})/?$")
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "target"}


@dataclass
class Check:
    name: str
    level: str          # ok / warn / block
    message: str
    fix: str = ""       # 可用的修复动作标识


def snapshot_sha(env_snapshot: str) -> str:
    m = _SHA_RE.search(env_snapshot or "")
    return m.group(1).lower() if m else ""


def _scan_blacklist(root: str, patterns: list[str], limit: int = 20) -> list[str]:
    hits: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in list(dirnames) + filenames:
            for pat in patterns:
                if fnmatch.fnmatch(name, pat):
                    rel = os.path.relpath(os.path.join(dirpath, name), root)
                    hits.append(rel)
                    break
            if len(hits) >= limit:
                return hits
    return hits


async def run_checks(task: Task) -> list[Check]:
    paths = config.TaskPaths(task.task_no)
    checks: list[Check] = []

    # 1. 配置
    if settings_store.is_configured("cc.api_key"):
        checks.append(Check("cc.api_key", "ok", "网关 Key 已配置"))
    else:
        checks.append(Check("cc.api_key", "block", "未配置网关 Key，请到设置页填写"))

    image = settings_store.get("cc.image")
    ok, msg = await dockerx.daemon_ok()
    if not ok:
        checks.append(Check("docker", "block", f"Docker 不可用：{msg}"))
        return checks
    checks.append(Check("docker", "ok", f"Docker {msg}"))
    if await dockerx.image_present(image):
        version = await dockerx.claude_version(image)
        note = f"镜像 {image} 就绪，CLI {version or '未知'}"
        level = "ok"
        if version and task.harness_version and version != task.harness_version:
            level = "warn"
            note += f"；prompt.md 记录的 Harness 版本为 {task.harness_version}，上传时将以实测值为准"
        checks.append(Check("image", level, note))
        mode = await dockerx.image_label(image, "org.benzhi.claude.task-mode")
        if not mode:
            checks.append(Check("image_label", "warn", "镜像缺少 org.benzhi.claude.task-mode 标签，可能不是本项目的 CC 任务镜像"))
    else:
        checks.append(Check("image", "block", f"本机不存在镜像 {image}，请先 docker pull 或在设置页更换"))

    # 2. 容器名占用
    state = await dockerx.container_state(paths.container_name)
    if state:
        checks.append(Check("container", "block", f"容器 {paths.container_name} 已存在（{state}），需先销毁", fix="remove_container"))
    else:
        checks.append(Check("container", "ok", f"容器名 {paths.container_name} 可用"))

    # 3. 工作目录与快照
    ws = paths.workspace
    if not ws.is_dir():
        checks.append(Check("workspace", "block", f"工作目录不存在：{ws}（需先 clone 初始快照到该目录）"))
    elif not (ws / ".git").exists():
        checks.append(Check("workspace", "block", f"{ws} 不是 git 仓库，无法校验初始快照"))
    else:
        head = await dockerx.run(["git", "-C", str(ws), "rev-parse", "HEAD"], timeout=20)
        head_sha = head.out.strip().lower()
        want = snapshot_sha(task.env_snapshot)
        if not want:
            checks.append(Check("snapshot", "warn", "初始环境快照不是 40 位 SHA 的 commit 链接，无法比对 HEAD"))
        elif head_sha == want:
            checks.append(Check("snapshot", "ok", f"HEAD == 快照 {want[:12]}"))
        else:
            checks.append(Check("snapshot", "block", f"HEAD {head_sha[:12]} ≠ 快照 {want[:12]}", fix="reset_snapshot"))

        st = await dockerx.run(["git", "-C", str(ws), "status", "--porcelain", "--untracked-files=all"], timeout=30)
        dirty = [line for line in st.out.splitlines() if line.strip()]
        if dirty:
            checks.append(Check("clean", "block", f"工作区有 {len(dirty)} 处改动/未跟踪文件，例如 {dirty[0].strip()}", fix="reset_snapshot"))
        else:
            checks.append(Check("clean", "ok", "工作区干净（不含忽略文件）"))

        ig = await dockerx.run(["git", "-C", str(ws), "status", "--porcelain", "--ignored=matching", "--untracked-files=no"], timeout=30)
        ignored = [line[3:] for line in ig.out.splitlines() if line.startswith("!!")]
        if ignored:
            checks.append(Check("ignored", "warn", f"存在 {len(ignored)} 个被忽略的文件/目录（如 {ignored[0]}），与初始快照不完全一致；重置到快照会一并清除", fix="reset_snapshot"))

        patterns = [p.strip() for p in settings_store.get("gate.blacklist").split(",") if p.strip()]
        hits = _scan_blacklist(str(ws), patterns)
        if hits:
            checks.append(Check("leak", "block", f"发现可能泄漏的文件：{', '.join(hits[:5])}"))
        else:
            checks.append(Check("leak", "ok", "未发现黑名单文件"))

    # 4. 轨迹目录必须为空
    tr = paths.traces
    if tr.exists() and any(tr.iterdir()):
        checks.append(Check("traces", "block", f"轨迹目录非空：{tr}（一题只允许一份轨迹，请先归档清空）", fix="archive_traces"))
    else:
        checks.append(Check("traces", "ok", "轨迹目录为空"))

    return checks


def summarize(checks: list[Check]) -> dict:
    blocked = [c for c in checks if c.level == "block"]
    return {
        "passed": not blocked,
        "blocked": len(blocked),
        "warnings": len([c for c in checks if c.level == "warn"]),
        "checks": [asdict(c) for c in checks],
    }


async def reset_to_snapshot(task: Task) -> dict:
    """git clean -fdx && git reset --hard <sha>。破坏性操作，由界面二次确认后调用。"""
    ws = config.TaskPaths(task.task_no).workspace
    sha = snapshot_sha(task.env_snapshot)
    if not sha:
        return {"ok": False, "message": "初始环境快照缺少 40 位 SHA，无法重置"}
    r1 = await dockerx.run(["git", "-C", str(ws), "clean", "-fdx"], timeout=120)
    r2 = await dockerx.run(["git", "-C", str(ws), "reset", "--hard", sha], timeout=120)
    ok = r1.ok and r2.ok
    return {"ok": ok, "message": (r2.out or r2.err or r1.err).strip()}


def archive_traces(task: Task) -> dict:
    """把非空轨迹目录整体改名归档（带时间戳），腾出空目录。"""
    from datetime import datetime

    tr = config.TaskPaths(task.task_no).traces
    if not tr.exists() or not any(tr.iterdir()):
        return {"ok": True, "message": "轨迹目录本就为空"}
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = tr.with_name(f"{tr.name}.archived-{stamp}")
    tr.rename(target)
    return {"ok": True, "message": f"已归档到 {target}"}
