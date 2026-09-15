"""题目设计：用 Cursor CLI 跑 /solo-prompt，产出自动导入并查重。

一次设计的完整链路：
    起 agent 执行 solo-prompt 的 SOP → 扫描 出题/prompts 新增的题 → 导入题库
    → 对新题跑 solo-qa 的规则 A 与规则 C → 通过的留在队列，命中的直接废弃

agent 在后端容器里跑，出题要建仓库、推快照，所以容器需要：
- skill 目录（SKILL.md 与它引用的两个参考文件），只读挂载；
- 工作区 /host/coder，就是 solo-prompt 约定的「当前工作区根目录」；
- gh CLI 与 GitHub Token；token 写成 credential store 供 git push 用。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from pathlib import Path

from app import config
from app.db import session
from app.events import bus
from app.models import (
    AVAILABLE, DESIGN_CANCELLED, DESIGN_DEDUP, DESIGN_DONE, DESIGN_FAILED, DESIGN_RUNNING,
    DISCARDED, ORIGIN_DESIGNED, DesignRun, Task, utc_now,
)
from app.services import prompt_bank, qa_bridge, settings_store

log = logging.getLogger("designer")

SKILL_DIR = Path(os.getenv("SKILL_DIR_MOUNT", "/host/skills"))
SKILL_FILE = SKILL_DIR / "solo-prompt" / "SKILL.md"
running: dict[int, asyncio.Task] = {}


def _agent_bin() -> str:
    return shutil.which("agent") or shutil.which("cursor-agent") or ""


def _publish(run_id: int) -> None:
    bus.publish("design", {"type": "design", "id": run_id})


def _set(run_id: int, **fields) -> None:
    with session() as db:
        r = db.get(DesignRun, run_id)
        if r is None:
            return
        for k, v in fields.items():
            setattr(r, k, v)
    _publish(run_id)


def preflight() -> list[dict]:
    """设计前的条件检查，界面上直接显示缺什么。"""
    checks = []

    def add(name: str, ok: bool, msg: str) -> None:
        checks.append({"name": name, "ok": ok, "message": msg})

    add("cursor_cli", bool(_agent_bin()), "已安装" if _agent_bin() else "后端镜像里没有 agent")
    add("cursor_key", bool(settings_store.get("cursor.api_key")), "已配置" if settings_store.get("cursor.api_key") else "未配置 Cursor API Key")
    add("skill", SKILL_FILE.exists(), str(SKILL_FILE) if SKILL_FILE.exists() else f"未挂载 solo-prompt skill（{SKILL_FILE}）")
    add("gh", bool(shutil.which("gh")), "已安装" if shutil.which("gh") else "后端镜像里没有 gh，出题无法建仓库")
    add("gh_token", bool(settings_store.get("gh.token")), "已配置" if settings_store.get("gh.token") else "未配置 GitHub Token")
    req = config.CODER_ROOT_MOUNT / "需求文档"
    has_req = req.exists() or (config.CODER_ROOT_MOUNT / "需求文档.md").exists()
    add("requirements", has_req, "已就绪" if has_req else "工作区根目录没有需求文档，skill 会直接终止")
    ok, why = qa_bridge.available()
    add("dedup", ok, "查重可用" if ok else why)
    return checks


def _prepare_env() -> dict:
    """agent 子进程的环境。gh 与 git push 都靠 token，不落盘到工作区。"""
    env = dict(os.environ)
    env["CURSOR_API_KEY"] = settings_store.get("cursor.api_key")
    env.pop("CURSOR_MODEL", None)
    token = settings_store.get("gh.token")
    if token:
        env["GH_TOKEN"] = token
        env["GITHUB_TOKEN"] = token
        # git push 走 https，凭据从 store 读；写在 HOME 下，不进任何仓库
        home = Path(env.get("HOME", "/root"))
        try:
            cred = home / ".git-credentials"
            cred.write_text(f"https://x-access-token:{token}@github.com\n", encoding="utf-8")
            cred.chmod(0o600)
            (home / ".gitconfig").write_text(
                "[credential]\n\thelper = store\n"
                "[user]\n\tname = solo-cli\n\temail = solo-cli@local\n"
                "[init]\n\tdefaultBranch = main\n",
                encoding="utf-8",
            )
        except OSError as exc:
            log.warning("写 git 凭据失败：%s", exc)
    return env


def _instruction(count: int, note: str) -> str:
    """让 agent 读 skill 再执行。CLI 不解析 /slash，只能显式指路。"""
    tail = f" {note.strip()}" if note.strip() else ""
    return (
        f"请先用读取工具完整读取 {SKILL_FILE}，它是 solo-prompt 出题 SOP 的全文；"
        f"文件里引用的 reference.md 与 prompt-writing.md 在同目录下，需要时一并读取。"
        f"然后严格按该 SOP 执行命令：/solo-prompt {count}{tail}。"
        f"当前工作区根目录是 {config.CODER_ROOT_MOUNT}，需求文档、出题目录、workspace 都在这里。"
        f"每道题都要写进 出题/prompts/<题号>.md 并追加到 出题/题库索引.md。"
        f"全部完成后，最后一行只输出一个 JSON："
        f'{{"designed": ["题号", …], "note": "一句话说明"}}'
    )


def start(count: int, note: str = "") -> dict:
    """建一条设计记录并后台执行。同一时间只允许一条在跑（出题会改工作区）。"""
    if running:
        return {"ok": False, "error": "已有设计任务在跑，出题会改工作区，等它结束再发起"}
    count = max(1, min(20, int(count)))
    with session() as db:
        r = DesignRun(count=count, note=note.strip(), status=DESIGN_RUNNING,
                      model=settings_store.get("design.model") or settings_store.get("cursor.model"),
                      started_at=utc_now())
        db.add(r)
        db.flush()
        run_id = r.id
    task = asyncio.create_task(run_design(run_id), name=f"design-{run_id}")
    running[run_id] = task
    task.add_done_callback(lambda f: running.pop(run_id, None))
    _publish(run_id)
    return {"ok": True, "id": run_id}


def cancel(run_id: int) -> dict:
    task = running.get(run_id)
    if task is None:
        return {"ok": False, "error": "该设计任务不在运行中"}
    task.cancel()
    _set(run_id, status=DESIGN_CANCELLED, finished_at=utc_now(), error="人工取消")
    return {"ok": True}


async def run_design(run_id: int) -> None:
    with session() as db:
        r = db.get(DesignRun, run_id)
        if r is None:
            return
        count, note, model = r.count, r.note, r.model
    started = time.time()
    try:
        agent = _agent_bin()
        if not agent:
            raise RuntimeError("后端镜像里没有 Cursor CLI（agent）")
        if not settings_store.get("cursor.api_key"):
            raise RuntimeError("未配置 Cursor API Key")
        if not SKILL_FILE.exists():
            raise RuntimeError(f"未挂载 solo-prompt skill：{SKILL_FILE}")

        before = {p.name for p in prompt_bank.archive_files()}
        timeout_s = max(300, settings_store.get_int("design.timeout_minutes", 90) * 60)
        cmd = [agent, "-p", "--force", "--trust", "--model", model or "claude-opus-5-thinking-high",
               "--output-format", "json", "--workspace", str(config.CODER_ROOT_MOUNT),
               _instruction(count, note)]
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(config.CODER_ROOT_MOUNT), env=_prepare_env(),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError(f"设计超过 {timeout_s // 60} 分钟未完成")
        stdout = out.decode("utf-8", "replace")
        stderr = err.decode("utf-8", "replace")
        _set(run_id, log=(stdout[-6000:] or stderr[-6000:]))
        if proc.returncode != 0:
            raise RuntimeError(f"agent 退出码 {proc.returncode}：{(stderr or stdout).strip()[-600:]}")

        # ---- 导入新产出的题 ----
        after = [p for p in prompt_bank.archive_files() if p.name not in before]
        stats = {"agent_s": round(time.time() - started), "new_files": [p.name for p in after]}
        if not after:
            raise RuntimeError("agent 结束了，但 出题/prompts 下没有新增题目文件")
        imported = prompt_bank.import_tasks(sources=after, origin=ORIGIN_DESIGNED, design_run_id=run_id)
        stats.update({"parsed": imported["parsed"], "imported": len(imported["added"]),
                      "task_nos": imported["added"]})
        _set(run_id, status=DESIGN_DEDUP, stats_json=json.dumps(stats, ensure_ascii=False),
             task_ids_json=json.dumps(imported["added_ids"]))

        # ---- 查重：命中规则 A 或 C 直接废弃 ----
        if settings_store.get_bool("design.auto_dedup", True) and imported["added_ids"]:
            passed, discarded, err_msg = await dedup_tasks(imported["added_ids"])
            stats.update({"passed": passed, "discarded": discarded, "dedup_error": err_msg})
        _set(run_id, status=DESIGN_DONE, finished_at=utc_now(),
             stats_json=json.dumps(stats, ensure_ascii=False))
    except asyncio.CancelledError:
        _set(run_id, status=DESIGN_CANCELLED, finished_at=utc_now(), error="人工取消")
        raise
    except Exception as exc:  # noqa: BLE001
        log.exception("设计失败 run=%s", run_id)
        _set(run_id, status=DESIGN_FAILED, finished_at=utc_now(), error=str(exc)[:2000])
    finally:
        bus.publish("tasks", {"type": "tasks"})


async def dedup_tasks(task_ids: list[int]) -> tuple[int, int, str]:
    """对一批题跑规则 A+C。返回 (通过数, 废弃数, 错误说明)。"""
    with session() as db:
        rows = [db.get(Task, tid) for tid in task_ids]
        items = [
            {
                "key": str(t.id),
                "user_prompt": t.user_prompt,
                "repo_id": qa_bridge.repo_id_of(t.env_snapshot),
                "session_id": "",
            }
            for t in rows if t is not None
        ]
    if not items:
        return 0, 0, "没有可查重的题"
    r = await qa_bridge.dedup(items)
    if not r.get("ok"):
        # 查不成不能默认放行，题留在题库里但标注出来，人工决定
        for tid in task_ids:
            _mark(tid, {"ok": False, "error": r.get("error", "")}, discard=False)
        return 0, 0, r.get("error", "查重未完成")

    passed = discarded = 0
    for item in r.get("results", []):
        try:
            tid = int(item.get("key"))
        except (TypeError, ValueError):
            continue
        hit = item.get("verdict") == "discard"
        _mark(tid, item, discard=hit)
        discarded += 1 if hit else 0
        passed += 0 if hit else 1
    return passed, discarded, ""


def _mark(task_id: int, result: dict, *, discard: bool) -> None:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return
        t.dedup = result
        if discard:
            t.discarded_from = t.status if t.status != DISCARDED else AVAILABLE
            t.status = DISCARDED
            t.discarded_at = utc_now()
    bus.publish("tasks", {"type": "task", "id": task_id})
