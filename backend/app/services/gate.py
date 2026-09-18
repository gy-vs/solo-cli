"""启动前门禁：题面口径、仓库分支、两侧工作区与容器的校验。

任一 block 级检查不通过就拒绝启动。双跑的检查项按 side 成对出现（workspace_A 与
workspace_B 这样），因为 A 和 B 是两次完全独立的运行，一侧就绪不代表另一侧也就绪。

题面口径（难度、任务类型）在这里就挡住，是因为跑完了才发现不符合平台收题范围，
两个容器的算力就白花了。
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import asdict, dataclass

from app import config
from app.models import Task
from app.services import dockerx, gsb_repo, settings_store
# 快照 sha 的解析归仓库模块管，这里只是用；保留 gate.snapshot_sha 这个名字给现有调用方
from app.services.gsb_repo import snapshot_sha  # noqa: F401

_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "target"}

# 平台的选项原值。注意「0-1代码生成」「feature迭代」中间没有空格，
# 而题块里习惯写成有空格的，所以比对前要先归一化
QUESTION_TYPES = ("0-1代码生成", "feature迭代", "Bug修复", "代码理解",
                  "代码重构", "工程化", "代码测试")
# 本期只收这两档，简单与中等一律打回（平台规则 G1）
DIFFICULTIES = ("困难", "地狱")
REPRO_LEVELS = ("无外部依赖", "有外部依赖，未容器化", "已容器化，可一键起环境")

_WS = re.compile(r"\s+")


@dataclass
class Check:
    name: str
    level: str          # ok / warn / block
    message: str
    fix: str = ""       # 可用的修复动作标识
    # 硬前提：强制启动也绕不过去。分两类，跑不起来的（Docker、镜像、Key、容器名被占）
    # 和起点不对的（没 clone、HEAD 对不上、轨迹目录非空）。它们跟难度、任务类型那种
    # 口径问题不是一回事：口径不对是交不上去，人明知故犯地先跑着还有意义；这两类是
    # 跑出来的东西根本不成立——容器起不来，或者模型在一个空目录里自己造一个仓库，
    # 跑完还长得像一次正常的运行。
    hard: bool = False


def normalize_choice(value: str, options: tuple[str, ...]) -> str:
    """把题块里写的值对到平台选项上。

    去掉全部空白、忽略大小写再比对，匹配上返回平台侧的原值。题块里的写法跟着
    出题速查表走，是「Feature 迭代」「0-1 代码生成」这种带空格且首字母大写的，
    平台选项则是「feature迭代」；差在书写而不是语义，不放宽的话整道题会卡在门禁上。
    匹配不上返回空串让门禁报出来，不做模糊猜测——猜错了会以一个合法但错误的分类提交上去。
    """
    want = _WS.sub("", value or "").casefold()
    if not want:
        return ""
    for o in options:
        if _WS.sub("", o).casefold() == want:
            return o
    return ""


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
    checks: list[Check] = []

    # 1. 配置与镜像
    if settings_store.is_configured("cc.api_key"):
        checks.append(Check("cc.api_key", "ok", "网关 Key 已配置"))
    else:
        checks.append(Check("cc.api_key", "block", "未配置网关 Key，请到设置页填写", hard=True))

    image = settings_store.get("cc.image")
    ok, msg = await dockerx.daemon_ok()
    if not ok:
        checks.append(Check("docker", "block", f"Docker 不可用：{msg}", hard=True))
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
            checks.append(Check("image_label", "warn",
                                "镜像缺少 org.benzhi.claude.task-mode 标签，可能不是本项目的 CC 任务镜像"))
    else:
        checks.append(Check("image", "block", f"本机不存在镜像 {image}，请先 docker pull 或在设置页更换",
                            hard=True))

    # 2. 题面必须符合平台口径，不然两个容器跑完也交不上去
    if normalize_choice(task.difficulty, DIFFICULTIES):
        checks.append(Check("difficulty", "ok", f"难度 {task.difficulty}"))
    else:
        checks.append(Check("difficulty", "block",
                            f"难度「{task.difficulty or '空'}」不收，本期只收困难与地狱（规则 G1）"))
    qt = normalize_choice(task.question_type, QUESTION_TYPES)
    if qt:
        checks.append(Check("question_type", "ok", f"任务类型 {qt}"))
    else:
        checks.append(Check("question_type", "block",
                            f"任务类型「{task.question_type or '空'}」不在平台选项里，"
                            f"可选：{'、'.join(QUESTION_TYPES)}"))
    if normalize_choice(task.repro_level, REPRO_LEVELS):
        checks.append(Check("repro_level", "ok", f"可复现等级 {task.repro_level}"))
    else:
        checks.append(Check("repro_level", "warn",
                            f"可复现等级「{task.repro_level or '空'}」不在平台选项里，上传前需要改题块"))

    # 3. 仓库与分支
    if not task.repo_url:
        checks.append(Check("repo_url", "block", "题块里没有仓库地址（「仓库：」那一行）", hard=True))
        return checks
    checks.append(Check("repo_url", "ok",
                        f"仓库 {gsb_repo.repo_slug(task.repo_url) or task.repo_url}"))
    probe = await gsb_repo.probe_branches(task.repo_url)
    checks.append(Check("branches", "ok" if probe.ok else "block", probe.message))

    snapshot = snapshot_sha(task.env_snapshot)
    if snapshot:
        checks.append(Check("snapshot", "ok", f"初始快照 {snapshot[:12]}"))
    else:
        checks.append(Check("snapshot", "block",
                            "初始环境快照不是 40 位 SHA 的 commit 链接，两边都没法对起跑点",
                            hard=True))

    # 4. 两侧各自的工作目录、轨迹目录、容器名
    patterns = [p.strip() for p in settings_store.get("gate.blacklist").split(",") if p.strip()]
    for side in config.SIDES:
        paths = config.TaskPaths(task.task_no, side)
        ws = paths.workspace
        if not (ws / ".git").exists():
            checks.append(Check(f"workspace_{side}", "block",
                                f"{side} 侧还没 clone 到 {ws}", fix="clone_sides", hard=True))
        else:
            hv = await gsb_repo.verify_head(task.task_no, side, snapshot)
            checks.append(Check(f"workspace_{side}", "ok" if hv["ok"] else "block",
                                hv["message"], fix="" if hv["ok"] else "reset_sides",
                                hard=not hv["ok"]))
            hits = _scan_blacklist(str(ws), patterns)
            checks.append(Check(f"leak_{side}", "block" if hits else "ok",
                                f"{side} 侧发现可能泄漏的文件：{', '.join(hits[:5])}" if hits
                                else f"{side} 侧未发现黑名单文件"))

        tr = paths.traces
        if tr.exists() and any(tr.iterdir()):
            checks.append(Check(f"traces_{side}", "block",
                                f"{side} 侧轨迹目录非空：{tr}（一次跑只能有一份轨迹）",
                                fix="archive_traces", hard=True))
        else:
            checks.append(Check(f"traces_{side}", "ok", f"{side} 侧轨迹目录为空"))

        state = await dockerx.container_state(paths.container_name)
        if state:
            checks.append(Check(f"container_{side}", "block",
                                f"容器 {paths.container_name} 已存在（{state}）",
                                fix="remove_containers", hard=True))
        else:
            checks.append(Check(f"container_{side}", "ok", f"容器名 {paths.container_name} 可用"))

    return checks


async def prepare_workspaces(task: Task) -> dict:
    """领题时把 A、B 两个分支各 clone 一份。

    先验分支再 clone：分支不合规时 clone 一定失败，让 git 的报错盖住「仓库分支不对」
    这个真正的原因，只会让人去查 Token 和网络。
    """
    probe = await gsb_repo.probe_branches(task.repo_url)
    if not probe.ok:
        return {"ok": False, "sides": {}, "message": probe.message}
    sides: dict[str, dict] = {}
    for side in config.SIDES:
        sides[side] = await gsb_repo.clone_side(task.task_no, task.repo_url, side)
    ok = all(r["ok"] for r in sides.values())
    msg = "；".join(f"{s}: {r['message']}" for s, r in sides.items())
    return {"ok": ok, "sides": sides, "message": msg}


def summarize(checks: list[Check]) -> dict:
    blocked = [c for c in checks if c.level == "block"]
    hard = [c for c in blocked if c.hard]
    return {
        "passed": not blocked,
        "blocked": len(blocked),
        # 强制启动能放行的只是剩下那些；这几条得先修好，没有别的路
        "hard_blocked": [c.name for c in hard],
        "hard_messages": [c.message for c in hard],
        "warnings": len([c for c in checks if c.level == "warn"]),
        "checks": [asdict(c) for c in checks],
    }
