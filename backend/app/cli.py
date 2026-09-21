"""在对话里触发的命令行入口。目前只管提交前质检与随后的批量提交。

这个模块存在的理由只有一个：发起质检不能放在页面上。它要在人已经看过录屏、准备整批
提交的那一刻跑——跑早了理由还会改，结论当场就过期；而一个点一下就烧掉一次模型调用的
按钮，摆在页面上迟早会被点。所以发起的口子只留在这里，nginx 那边把
`/api/tasks/*/precheck` 与 `/api/tasks/batch/precheck` 一并挡掉，浏览器根本到不了。

不 import 那些 service 自己跑，而是打后端进程的 HTTP 口。差别在界面会不会动：事件
总线是进程内的，另起一个进程写库，浏览器一个事件都收不到，人盯着列表看不见「质检
中」，只能自己刷。走 HTTP 等于让后端进程去干这件事，状态一路推到页面上。

题号就是界面上那个题号（`219`、`07-mac-air`），不是数据库 id——人记得的是题号，而
两者在这个项目里从来不相等。

用法（在宿主机仓库根目录）：

    docker compose exec backend python -m app.cli ready          # 该质检哪些题
    docker compose exec backend python -m app.cli precheck       # 全部跑一遍
    docker compose exec backend python -m app.cli precheck 219 221
    docker compose exec backend python -m app.cli status         # 质检栏总览
    docker compose exec backend python -m app.cli submit         # 批量提交放行的
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx

# 容器内直接找本进程的 uvicorn。给个环境变量是为了在本机裸跑后端时也能用，
# 不是为了让它指到别的机器上。
BASE = os.environ.get("SOLO_CLI_API", "http://localhost:8000")

# 质检一道题按 600s 算，批量十几道就是几小时；提交要传两份轨迹，也可能很慢。
# 这条命令是人在对话里盯着看的，等多久都比中途被客户端掐断好，所以不设上限。
TIMEOUT = httpx.Timeout(None, connect=10)

PRECHECK_LABEL = {
    "IDLE": "未质检", "RUNNING": "质检中", "PASS": "通过",
    "FAIL": "待改", "CONFIRMED": "已确认", "ERROR": "没跑完",
}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE, timeout=TIMEOUT)


async def _tasks(c: httpx.AsyncClient) -> list[dict]:
    r = await c.get("/api/tasks", params={"include_discarded": "true"})
    r.raise_for_status()
    return r.json()["items"]


def _resolve(items: list[dict], wanted: list[str]) -> tuple[list[int], list[str]]:
    """题号列表转 id。返回 (命中的 id, 没找到的题号)。

    顺序按用户给的来，不按题号排：他念的顺序通常就是他关心的顺序。
    """
    by_no = {str(t["task_no"]): t["id"] for t in items}
    ids, missing = [], []
    for raw in wanted:
        no = raw.strip().lstrip("#")
        if no in by_no:
            ids.append(by_no[no])
        else:
            missing.append(raw)
    return ids, missing


def _line(t: dict) -> str:
    """一道题在清单里占的那一行。"""
    status = PRECHECK_LABEL.get(t.get("precheck_status") or "", t.get("precheck_status") or "—")
    n = t.get("precheck_issues") or 0
    tail = t.get("precheck_summary") or ""
    stale = "（理由已改过，结论过期）" if t.get("precheck_stale") else ""
    return (f"  {t['task_no']:<12} {status:<6} {n} 处{stale}"
            + (f"  {tail[:60]}" if tail else ""))


# ---------------- 子命令 ----------------

async def cmd_ready(args: argparse.Namespace) -> int:
    async with _client() as c:
        r = await c.get("/api/tasks/precheck/ready")
        r.raise_for_status()
        items = r.json()["items"]
    if not items:
        print("没有该质检的题。口径是「两侧录屏链接齐了、还没拿到有效质检结论」。")
        return 0
    print(f"该做提交前质检的题 {len(items)} 道：")
    for t in items:
        print(_line(t))
    return 0


async def cmd_precheck(args: argparse.Namespace) -> int:
    async with _client() as c:
        if args.task_nos:
            items = await _tasks(c)
            ids, missing = _resolve(items, args.task_nos)
            if missing:
                print(f"这些题号在库里找不到：{'、'.join(missing)}", file=sys.stderr)
                if not ids:
                    return 2
            nos = {t["id"]: t["task_no"] for t in items}
        else:
            r = await c.get("/api/tasks/precheck/ready")
            r.raise_for_status()
            ready = r.json()["items"]
            ids = [t["id"] for t in ready]
            nos = {t["id"]: t["task_no"] for t in ready}
            if not ids:
                print("没有该质检的题，不用跑。")
                return 0

        print(f"要质检 {len(ids)} 道：{'、'.join(nos.get(i, str(i)) for i in ids)}")
        if args.dry_run:
            print("（--dry-run，没有真的发起）")
            return 0

        r = await c.post("/api/tasks/batch/precheck", json={"ids": ids})
        r.raise_for_status()
        results = r.json()["results"]

    passed = [x for x in results if x.get("passed")]
    revise = [x for x in results if x.get("ok") and not x.get("passed")]
    failed = [x for x in results if not x.get("ok")]
    print()
    for x in results:
        no = nos.get(x["id"], x["id"])
        print(f"  题 {no}：{x.get('message') or ''}")
    print(f"\n汇总：{len(passed)} 道通过，{len(revise)} 道要人工改，{len(failed)} 道没跑完")
    if revise:
        print("要人工改的题在界面「质检」栏里逐条看 issues，改完点「确认放行」才能提交。")
    return 0


async def cmd_status(args: argparse.Namespace) -> int:
    async with _client() as c:
        items = await _tasks(c)
    qc = [t for t in items if t["status"] == "QC"]
    waiting = [t for t in items if t["status"] == "ANALYZED"]
    if not qc and not waiting:
        print("没有在录屏或质检这两步上的题。")
        return 0
    if waiting:
        print(f"还在等录屏 {len(waiting)} 道：{'、'.join(t['task_no'] for t in waiting)}")
    if qc:
        print(f"\n质检栏 {len(qc)} 道：")
        for t in sorted(qc, key=lambda x: x["task_no"]):
            print(_line(t))
        ok = [t for t in qc if not t.get("precheck_block")]
        blocked = [t for t in qc if t.get("precheck_block")]
        print(f"\n可以直接提交 {len(ok)} 道"
              + (f"：{'、'.join(t['task_no'] for t in ok)}" if ok else ""))
        for t in blocked:
            print(f"  题 {t['task_no']} 提交被挡：{t['precheck_block']}")
    return 0


async def cmd_submit(args: argparse.Namespace) -> int:
    async with _client() as c:
        items = await _tasks(c)
        if args.task_nos:
            ids, missing = _resolve(items, args.task_nos)
            if missing:
                print(f"这些题号在库里找不到：{'、'.join(missing)}", file=sys.stderr)
        else:
            ids = [t["id"] for t in items if t["status"] == "QC" and not t.get("precheck_block")]
        nos = {t["id"]: t["task_no"] for t in items}
        if not ids:
            print("没有质检放行、可以提交的题。先跑 precheck，或者在界面上确认放行。")
            return 0
        print(f"要提交 {len(ids)} 道：{'、'.join(nos.get(i, str(i)) for i in ids)}")
        if args.dry_run:
            print("（--dry-run，没有真的提交）")
            return 0
        r = await c.post("/api/tasks/batch/upload", json={"ids": ids})
        r.raise_for_status()
        results = r.json()["results"]

    ok = [x for x in results if x.get("ok")]
    print()
    for x in results:
        no = nos.get(x["id"], x["id"])
        mark = f"#{x.get('submission_id')}" if x.get("ok") else "没成"
        print(f"  题 {no}：{mark} {x.get('message') or ''}")
    print(f"\n汇总：{len(ok)} 道提交成功，{len(results) - len(ok)} 道没成")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="solo-cli 的对话侧命令。提交前质检只能从这里发起，页面上没有入口。")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ready", help="列出该做提交前质检的题（录屏已齐、还没有有效结论）")

    q = sub.add_parser("precheck", help="跑提交前质检。不给题号就跑 ready 列出的全部")
    q.add_argument("task_nos", nargs="*", metavar="题号")
    q.add_argument("-n", "--dry-run", action="store_true", help="只看要跑哪些，不真的发起")

    sub.add_parser("status", help="录屏与质检两步的总览，含每道题为什么不能提交")

    s = sub.add_parser("submit", help="批量提交。不给题号就提交全部质检放行的题")
    s.add_argument("task_nos", nargs="*", metavar="题号")
    s.add_argument("-n", "--dry-run", action="store_true", help="只看要提交哪些，不真的提交")
    return p


HANDLERS = {"ready": cmd_ready, "precheck": cmd_precheck,
            "status": cmd_status, "submit": cmd_submit}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(HANDLERS[args.cmd](args))
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            body = exc.response.json()
            detail = body.get("detail") if isinstance(body, dict) else ""
            if isinstance(detail, dict):
                detail = detail.get("message") or str(detail)
        except ValueError:
            detail = exc.response.text[:300]
        print(f"后端回绝：HTTP {exc.response.status_code} {detail}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"连不上后端 {BASE}：{exc}\n"
              f"这条命令要在后端容器里跑：docker compose exec backend python -m app.cli …",
              file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n中断。已经跑完的那几道题结论已经落库，重跑不会重复花钱。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
