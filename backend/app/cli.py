"""在对话里触发的命令行入口。管提交前质检、录屏交付与批量提交。

整条流水线现在自己跑：跑完自动分析，分析完自动过两道质检（事实核验 + 措辞），
看门狗还会把卡住的补上。留着这个入口是为了两件机器替不了的事——

1. 交付录屏。录屏在外部录完，人手上只有两个文件路径，只能他自己说出来。
   `deliver` 收下路径，把视频归档进题目目录、代传到平台，然后直接提交。
2. 兜底与查看。批量重跑某几道的质检、看一眼整批卡在哪儿、手动提交。

不 import 那些 service 自己跑，而是打后端进程的 HTTP 口。差别在界面会不会动：事件
总线是进程内的，另起一个进程写库，浏览器一个事件都收不到，人盯着列表看不见「质检
中」，只能自己刷。走 HTTP 等于让后端进程去干这件事，状态一路推到页面上。

题号就是界面上那个题号（`219`、`07-mac-air`），不是数据库 id——人记得的是题号，而
两者在这个项目里从来不相等。

用法（在宿主机仓库根目录）：

    docker compose exec backend python -m app.cli status         # 整批卡在哪儿
    docker compose exec backend python -m app.cli ready          # 还该质检哪些题
    docker compose exec backend python -m app.cli gate 219 221   # 整条质检走一遍
    docker compose exec backend python -m app.cli precheck 219   # 只跑措辞那一道
    docker compose exec backend python -m app.cli screen         # 难度筛选试算，调阈值用
    docker compose exec backend python -m app.cli screen --probe # 探路试算：另一侧本来不必跑的有哪些
    docker compose exec backend python -m app.cli scope          # 待领题的改动面预先体检一遍
    docker compose exec backend python -m app.cli deliver 219 ~/a.mp4 ~/b.mp4
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
FACTCHECK_LABEL = {
    "IDLE": "未核验", "RUNNING": "核验中", "PASS": "一致",
    "FAIL": "有出入", "CONFIRMED": "已确认", "ERROR": "没跑完",
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
    """一道题在清单里占的那一行。两道质检各占一栏。

    分两栏而不是合成一句「质检没过」：两者该做的动作完全不同，一个是回去核对轨迹，
    一个是改句子，合并之后人还得再点进去才知道是哪一种。
    """
    fact = FACTCHECK_LABEL.get(t.get("factcheck_status") or "", t.get("factcheck_status") or "—")
    tone = PRECHECK_LABEL.get(t.get("precheck_status") or "", t.get("precheck_status") or "—")
    nf, nt = t.get("factcheck_mismatches") or 0, t.get("precheck_issues") or 0
    stale = "（理由已改过，结论过期）" if t.get("precheck_stale") or t.get("factcheck_stale") else ""
    tail = t.get("factcheck_summary") or t.get("precheck_summary") or ""
    return (f"  {t['task_no']:<12} 事实 {fact:<4} {nf} 处   措辞 {tone:<4} {nt} 处{stale}"
            + (f"  {tail[:50]}" if tail else ""))


# ---------------- 子命令 ----------------

async def cmd_ready(args: argparse.Namespace) -> int:
    async with _client() as c:
        r = await c.get("/api/tasks/precheck/ready")
        r.raise_for_status()
        items = r.json()["items"]
    if not items:
        print("没有该质检的题。口径是「结论已出、还没拿到有效质检结论」，和录屏没关系 ——"
              "质检排在录屏前面，录完再改理由就得重录。")
        return 0
    print(f"该做提交前质检的题 {len(items)} 道：")
    for t in items:
        print(_line(t))
    return 0


async def cmd_gate(args: argparse.Namespace) -> int:
    """整条闸门走一遍：事实核验 + 措辞质检 + 本地核验 + 平台质检。

    正常由看门狗自动跑，这里给「刚改完理由想立刻看整条结论」和补跑积压用。
    走的是后台队列，按分析并发额度排，所以立刻返回，进度看 status。
    """
    async with _client() as c:
        items = await _tasks(c)
        if args.task_nos:
            ids, missing = _resolve(items, args.task_nos)
            if missing:
                print(f"这些题号在库里找不到：{'、'.join(missing)}", file=sys.stderr)
                if not ids:
                    return 2
        else:
            r = await c.get("/api/tasks/precheck/ready")
            r.raise_for_status()
            ids = [t["id"] for t in r.json()["items"]]
        nos = {t["id"]: t["task_no"] for t in items}
        if not ids:
            print("没有该质检的题，不用跑。")
            return 0
        print(f"要质检 {len(ids)} 道：{'、'.join(nos.get(i, str(i)) for i in ids)}")
        if args.dry_run:
            print("（--dry-run，没有真的发起）")
            return 0
        r = await c.post("/api/tasks/batch/quality-gate", json={"ids": ids})
        r.raise_for_status()
        results = r.json()["results"]

    started = [x for x in results if x.get("started")]
    print()
    for x in results:
        print(f"  题 {nos.get(x['id'], x['id'])}：{x.get('message') or ''}")
    print(f"\n已发起 {len(started)} 道，其余在队列里等额度。跑完看 "
          f"`python -m app.cli status`，界面上也会自己刷新。")
    return 0


async def cmd_screen(args: argparse.Namespace) -> int:
    """按当前阈值把跑完的题试算一遍难度筛选，只出名单。

    这条命令是调阈值用的，它自己什么都不改。跑完的题在开分析之前会被自动筛一遍，
    两侧都太轻的直接废弃 —— 而「这套阈值到底会废掉哪些」，只有在自己认得的那批题上
    算一遍才看得出来。名单里出现真题就说明线画高了。
    """
    async with _client() as c:
        r = await c.get("/api/tasks/difficulty/preview")
        r.raise_for_status()
        out = r.json()

    th = out["thresholds"]
    print(f"难度筛选：{'已开启' if out['enabled'] else '已关闭（下面只是试算）'}")
    print(f"  两侧都不到 {th['min_minutes']} 分钟，或都不到 {th['min_steps']} 步 → 废弃")
    print(f"  一侧不到 {th['low_steps']} 步时，另一侧要有 {th['low_peer_steps']} 步以上")
    print(f"  一侧在 {th['low_steps']}–{th['min_steps']} 步时，另一侧要有 {th['mid_peer_steps']} 步以上")

    items = out["items"]
    if not items:
        print("\n还没有两侧都跑完的题，算不出名单。")
        return 0
    discard = [x for x in items if x["verdict"] == "discard"]
    if args.all:
        shown = items
    else:
        shown = discard
    print(f"\n共 {len(items)} 道两侧都跑完的题，按这套阈值会废弃 {len(discard)} 道"
          + ("：" if shown else "，一道都不废。"))
    for x in shown:
        steps, mins = x["steps"], x["minutes"]
        nums = "  ".join(f"{s} {steps.get(s) if steps.get(s) is not None else '—':>3} 步 "
                         f"{mins.get(s) if mins.get(s) is not None else '—':>5} 分"
                         for s in ("A", "B"))
        mark = {"discard": "废弃", "pass": "保留", "unknown": "判不了", "skipped": "不筛"}
        print(f"  {x['task_no']:<12} {mark.get(x['verdict'], x['verdict']):<4} {nums}   "
              f"{x['status']}")
    if discard and not args.all:
        print("\n名单里出现自己认得的真题就说明线画高了，去设置页的「难度筛选」调，"
              "再跑一次这条命令。加 --all 看全部题的四个数。")
    return 0


async def cmd_screen_probe(args: argparse.Namespace) -> int:
    """探路的试算：这套阈值下，另一侧本来可以不跑的有哪些。

    和上面那条问的不是同一件事。那条问「哪些题白评了」，这条问「哪些容器白跑了」，
    所以名单里列的是另一侧的那两个数——判错的代价落在它身上。
    """
    async with _client() as c:
        r = await c.get("/api/tasks/difficulty/probe-preview")
        r.raise_for_status()
        out = r.json()

    th = out["thresholds"]
    print(f"探路：{'已开启' if out['enabled'] else '已关闭（下面只是试算）'}")
    print(f"  先跑完那一侧不到 {th['probe_steps']} 步 且 不到 {th['probe_minutes']} 分钟 → 整题废弃")
    if not out["total"]:
        print("\n还没有两侧都跑完的题，算不出名单。")
        return 0

    print(f"\n共 {out['total']} 道两侧都跑完的题，按这套阈值有 {out['hit']} 道的另一侧"
          f"本来不必跑，省下约 {out['saved_hours']} 个容器小时。")
    shown = out["items"] if args.all else [x for x in out["items"] if x["verdict"] == "discard"]
    for x in shown:
        print(f"  {x['task_no']:<12} 先跑完 {x['side']} 侧 "
              f"{x['steps'] if x['steps'] is not None else '—':>3} 步 "
              f"{x['minutes'] if x['minutes'] is not None else '—':>5} 分"
              f"   → 另一侧 {x['peer_steps'] if x['peer_steps'] is not None else '—':>3} 步 "
              f"{x['peer_minutes'] if x['peer_minutes'] is not None else '—':>5} 分   {x['status']}")
    if out["hit"]:
        print(f"\n被判掉的那些题，另一侧最多走了 {out['peer_max_steps']} 步——这个数要是逼近"
              f"自己认得的真题的水平，就说明线画高了。")
    return 0


async def cmd_scope(args: argparse.Namespace) -> int:
    """给待领的题预先体检一遍改动面，把只动一个模块的题在开跑前挑出来。

    领取时会自动补跑，但那是排在 clone 和门禁中间的，人得盯着等。趁手头没事先跑完这
    一轮，白天领题就不必等模型；改动面太窄的那几道也能提前看到，不必一道道领了才知道。
    """
    async with _client() as c:
        r = await c.post("/api/tasks/batch/scope", json={"ids": []})
        r.raise_for_status()
        out = r.json()
    print(out.get("message") or "没有要体检的题")
    if out.get("narrow"):
        print("\n被判太窄的题在题库列表上有标注，点进去看门禁里的 scope 一行，"
              "里面写着模型数出了哪几个模块。判错了就按那一行的「认了，照跑」放行。")
    return 0


async def cmd_deliver(args: argparse.Namespace) -> int:
    """交付录屏并提交：给两侧的本地视频路径，收下、代传、直接交到平台。

    这是整条流水线上最后一个人工动作。前面每一步都自己跑完了，缺的只有这两个文件，
    而它们在哪儿只有人知道。
    """
    async with _client() as c:
        items = await _tasks(c)
        ids, missing = _resolve(items, [args.task_no])
        if missing or not ids:
            print(f"题号 {args.task_no} 在库里找不到", file=sys.stderr)
            return 2
        task_id = ids[0]
        body = {"A": args.a, "B": args.b, "submit": not args.no_submit}
        r = await c.post(f"/api/tasks/{task_id}/screencast/deliver", json=body)
        if r.status_code >= 400:
            try:
                print(f"没成：{r.json().get('detail')}", file=sys.stderr)
            except ValueError:
                print(f"没成：HTTP {r.status_code} {r.text[:300]}", file=sys.stderr)
            return 1
        out = r.json()

    print(f"题 {args.task_no}：{out['message']}")
    submitted = out.get("submitted")
    if submitted and submitted.get("ok"):
        print(f"  已提交 #{submitted.get('submission_id') or ''}")
    elif args.no_submit:
        print("  （--no-submit，只收下没提交）")
    return 0 if not submitted or submitted.get("ok") else 1


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
    """质检与录屏两步的总览。顺序照流水线来：先质检，后录屏。"""
    async with _client() as c:
        items = await _tasks(c)
    checking = [t for t in items if t["status"] == "ANALYZED"]
    recording = [t for t in items if t["status"] == "QC"]
    if not checking and not recording:
        print("没有在质检或录屏这两步上的题。")
        return 0

    if checking:
        print(f"待质检 {len(checking)} 道：")
        for t in sorted(checking, key=lambda x: x["task_no"]):
            print(_line(t))
        hand = [t for t in checking
                if t.get("factcheck_status") in ("FAIL", "ERROR")
                or t.get("precheck_status") in ("FAIL", "ERROR")]
        auto = len(checking) - len(hand)
        if auto:
            print(f"  其中 {auto} 道看门狗会自己补跑，不用管。")
        for t in hand:
            why = t.get("factcheck_summary") or t.get("precheck_summary") or ""
            print(f"  题 {t['task_no']} 要人看一眼：{why[:80]}")

    if recording:
        print(f"\n待录屏 {len(recording)} 道（质检都放行了，理由不会再动）：")
        ok = [t for t in recording if not t.get("precheck_block")]
        for t in sorted(recording, key=lambda x: x["task_no"]):
            print(f"  {t['task_no']:<12} {t.get('precheck_block') or '录屏已齐，可提交'}")
        print(f"\n可以直接提交 {len(ok)} 道"
              + (f"：{'、'.join(t['task_no'] for t in ok)}" if ok else ""))
        print("录完把视频交上来：python -m app.cli deliver 题号 A.mp4 B.mp4")
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
        description="solo-cli 的对话侧命令。流水线自己会跑，这里管录屏交付与兜底。")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="质检与录屏两步的总览，含每道题卡在哪儿")
    sub.add_parser("ready", help="列出该做提交前质检的题（结论已出、还没有有效结论）")

    g = sub.add_parser("gate", help="整条质检走一遍（事实核验 + 措辞 + 核验 + 平台）")
    g.add_argument("task_nos", nargs="*", metavar="题号")
    g.add_argument("-n", "--dry-run", action="store_true", help="只看要跑哪些，不真的发起")

    q = sub.add_parser("precheck", help="只跑措辞那一道。不给题号就跑 ready 列出的全部")
    q.add_argument("task_nos", nargs="*", metavar="题号")
    q.add_argument("-n", "--dry-run", action="store_true", help="只看要跑哪些，不真的发起")

    sc = sub.add_parser("screen", help="按当前阈值试算难度筛选会废弃哪些题，什么都不改")
    sc.add_argument("-a", "--all", action="store_true", help="连保留的题也列出来，看全部四个数")
    sc.add_argument("--probe", action="store_true",
                    help="改算探路：只看先跑完那一侧，列出另一侧本来不必跑的题")

    sub.add_parser("scope", help="给待领的题预先体检改动面，提前挑出只动一个模块的题")

    d = sub.add_parser("deliver", help="交付录屏并提交：收下本机视频、代传、直接交到平台")
    d.add_argument("task_no", metavar="题号")
    d.add_argument("a", metavar="A侧视频路径")
    d.add_argument("b", metavar="B侧视频路径")
    d.add_argument("--no-submit", action="store_true", help="只收下和代传，先不提交")

    s = sub.add_parser("submit", help="批量提交。不给题号就提交全部质检放行的题")
    s.add_argument("task_nos", nargs="*", metavar="题号")
    s.add_argument("-n", "--dry-run", action="store_true", help="只看要提交哪些，不真的提交")
    return p


async def cmd_screen_or_probe(args: argparse.Namespace) -> int:
    return await (cmd_screen_probe(args) if args.probe else cmd_screen(args))


HANDLERS = {"ready": cmd_ready, "gate": cmd_gate, "precheck": cmd_precheck,
            "screen": cmd_screen_or_probe, "scope": cmd_scope, "deliver": cmd_deliver,
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
