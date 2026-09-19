"""远端题库 → 本机题目表。

池启用后，可领取的题目全集在 `pool.jsonl` 里，本机 SQLite 的 `task` 表只是它的一份
投影加上本机的做题进度。两边的分工是固定的：

    远端只回答「这道题归谁」，本机只回答「这道题做到哪一步」。

所以同步是单向的 —— 远端多了题就在本机建一行 AVAILABLE，远端被别人领走了就把本机那行
待领的删掉。已经领到手的题（CLAIMED 及以后）不受同步影响：那时本机有工作区、有容器、
有轨迹，删掉一行数据库记录并不能把这些收回去，反而会让它们变成没人认领的垃圾。

题号要在这里改写。两台设备各自从 01 开始编号，而题号会拼成工作区目录名和容器名
（`workspace/<题号>/<侧>`、`solo-cc-<题号>-<侧>`），照搬过来两道不同的题会共用一个
工作区。别的设备的题一律加设备后缀，题面里的题号与路径也跟着改，免得界面上显示的题号
和题面里写的对不上。
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import select

from app import config
from app.models import AVAILABLE, ORIGIN_POOL, Task
from app.db import session
from app.services import gsb_repo, pool, prompt_bank

log = logging.getLogger("pool-bank")

# 同步不会碰的状态：已经动过手的题。AVAILABLE 之外的每一个状态背后都有本机产物。
UNTOUCHED = frozenset({AVAILABLE})


def localize_draft(text: str, orig_no: str, local_no: str) -> str:
    """把别的设备的题面改写成本机口径：题号换成本机题号，工作区路径换成本机路径。

    只改题号行和那几个路径片段，正文一个字不动 —— 正文里出现 `01` 这样的数字太常见，
    全文替换会把题目内容一起改了。
    """
    if orig_no == local_no and str(config.CODER_ROOT_HOST) in text:
        return text
    out = re.sub(rf"^题号[：:]\s*{re.escape(orig_no)}\s*$", f"题号：{local_no}",
                 text, count=1, flags=re.MULTILINE)
    # 路径形如 `<对方的 coder_root>/workspace/01/A`，coder_root 与题号都要换成本机的
    for sub in (config.WORKSPACE_DIR, config.TRACES_DIR):
        out = re.sub(rf"\S*/{sub}/{re.escape(orig_no)}/([AB])",
                     rf"{config.CODER_ROOT_HOST}/{sub}/{local_no}/\1", out)
    return out


def archive_draft(local_no: str, text: str) -> None:
    """把题面落到本机归档目录，人工核对时能直接打开。

    带设备后缀的文件名不是纯数字，`prompt_bank.archive_files()` 扫不到它，所以这些文件
    不会被本地导入那条路径当成本机题再解析一遍 —— 归属只认远端那一份。
    """
    path = config.CODER_ROOT_MOUNT / config.PROMPTS_ARCHIVE_DIR / f"{local_no}.md"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        log.warning("题面归档失败 %s：%s", path, exc)


def _fill(task: Task, parsed: prompt_bank.ParsedTask, entry: pool.Entry) -> None:
    task.meta = parsed.meta
    for key, value in parsed.fields.items():
        setattr(task, key, value)
    task.user_prompt = parsed.user_prompt
    # 与 prompt_bank.import_tasks 同口径：快照链接后面跟着括号说明，而这个值要拿去比对
    # HEAD、还会原样提交；仓库地址则是双跑 clone 两个分支的依据
    task.env_snapshot = gsb_repo.first_url(task.env_snapshot)
    task.repo_url = gsb_repo.parse_repo_url(parsed.meta)
    task.pool_entry_id = entry.id
    task.pool_device = entry.device
    task.origin = ORIGIN_POOL


def sync_tasks() -> dict:
    """按远端题库刷新本机可领取的题。返回 {added, removed, adopted, skipped}。"""
    entries = pool.load()
    held = pool.owners()
    me = pool.device()

    added: list[str] = []
    removed: list[str] = []
    adopted: list[str] = []
    skipped: list[str] = []

    with session() as db:
        existing = {(t.task_no, t.prompt_hash): t
                    for t in db.execute(select(Task)).scalars()}
        for entry in entries:
            local_no = pool.local_task_no(entry)
            if not entry.draft:
                # 只有 prompt 正文、没有题面的老条目。缺仓库地址和初始快照，clone 不了
                # 两个分支，建成待领取的题只会在领取那一步才失败。
                skipped.append(local_no)
                continue
            parsed = next((p for p in prompt_bank.parse_text(entry.draft) if p.user_prompt), None)
            if parsed is None:
                skipped.append(local_no)
                continue

            task = existing.get((local_no, parsed.prompt_hash))
            owner = held.get(entry.id, "")
            if owner and owner != me:
                # 别的设备领走了。本机只是挂在待领列表里的，从列表上撤掉；已经动过手的
                # 留着 —— 那说明两边抢在了一起，本机的工作区和容器还得让人处理。
                if task is not None and task.status in UNTOUCHED:
                    db.delete(task)
                    removed.append(local_no)
                continue

            text = localize_draft(entry.draft, parsed.task_no, local_no)
            if task is None:
                task = Task(task_no=local_no, prompt_hash=parsed.prompt_hash, status=AVAILABLE)
                _fill(task, parsed, entry)
                task.claimed_by = owner
                db.add(task)
                archive_draft(local_no, text)
                added.append(local_no)
                continue

            # 已有的题只补关联字段。题面与状态不覆盖：本机可能已经在做了。
            if not task.pool_entry_id:
                task.pool_entry_id = entry.id
                task.pool_device = entry.device
                adopted.append(local_no)
            task.claimed_by = owner

    if skipped:
        log.info("远端题库有 %s 道题缺题面全文，暂不可领：%s", len(skipped), "、".join(skipped[:8]))
    return {"added": added, "removed": removed, "adopted": adopted, "skipped": skipped,
            "total": len(entries), "claimed": len(held)}


async def refresh() -> dict:
    """拉远端题库再投影一次。界面上那个「同步题库」按钮走这里。"""
    ok, why = pool.available()
    if not ok:
        return {"ok": False, "message": why, "added": [], "removed": [], "skipped": []}
    synced = await pool.sync()
    if not synced["ok"]:
        return {"ok": False, "message": synced["message"], "added": [], "removed": [], "skipped": []}
    # 拉失败但有本地副本时照常投影：看得到题总比题库空着强，只是这一轮的归属可能是旧的。
    # 真要领取时 claim_remote 会自己再拉一次，拉不到就不让领，不会靠这份旧副本放行。
    stale = " · 注意：这次没拉到远端，下面是上次同步的副本" if synced.get("stale") else ""

    # 题面全文是后加的字段，早于它入池的本机题在别的设备上领不了。每次同步顺带补一次：
    # 补过就没有可补的了，代价只是遍历几十条记录。
    filled = 0
    if any(e.device == pool.device() and not e.draft for e in pool.load()):
        back = await pool.backfill_drafts()
        filled = back["filled"]
        log.info("补题面全文 · %s", back["message"])

    res = sync_tasks()
    parts = [f"远端 {res['total']} 道，已被领取 {res['claimed']} 道"]
    if filled:
        parts.append(f"补齐 {filled} 道老题的题面")
    if res["added"]:
        parts.append(f"新增 {len(res['added'])} 道")
    if res["removed"]:
        parts.append(f"移除已被他人领取 {len(res['removed'])} 道")
    if res["adopted"]:
        parts.append(f"关联本机已有 {len(res['adopted'])} 道")
    if res["skipped"]:
        parts.append(f"{len(res['skipped'])} 道缺题面全文不可领")
    return {"ok": True, "message": "；".join(parts) + stale, "stale": bool(synced.get("stale")), **res}
