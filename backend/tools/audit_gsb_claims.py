"""核验 GSB 正文里那些「某侧没有跑过测试/构建」「某侧戛然而止」的断言。

这两类断言的共同点是：它们说的是轨迹里**没有**某件事，而这恰恰是轨迹本身能一票
否决的。只要轨迹末尾摆着成功的测试记录或完整的收尾总结，断言就站不住，交上去等
于把对方没犯的错算到它头上。

会写错的根子在分析器：轨迹步骤超过 STEP_LIMIT 就压缩，等距抽样时 stride 取整后
配 [:room] 会把尾部整段切掉，模型于是看不到收尾。所以这里顺手把「这一侧当时被压
掉了多少尾部步骤」一起算出来，方便对着看。

报出来的每条都要人看一眼再定性：句子归到哪一侧是按「这句里只提到 A 还是只提到 B」
猜的，代词句从上一句继承，遇上「A 的用例没跑过，所以 B 更好」这种一句话里主语和
结论各指一侧的写法就会猜反。宁可让人多看一眼，也不能因为猜不准就整类漏掉。

用法：python3 backend/tools/audit_gsb_claims.py [--status UPLOADED]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "solo-cli.db"
EXPORTS = ROOT / "data" / "exports"

STEP_LIMIT = 140  # 与 gsb_analyzer.STEP_LIMIT 保持一致

SRC_EDIT = ("Edit", "Write", "MultiEdit", "NotebookEdit")
TEST_CMD = re.compile(r"\b(npm|pnpm|yarn|npx)\s+(run\s+)?(test|build|lint)"
                      r"|\b(pytest|vitest|jest|mocha|tox|cargo\s+test|go\s+test|tsc|mvn|gradle)\b"
                      r"|node\s+--test|python\s+-m\s+(pytest|unittest)")
SRC_PATH = re.compile(r"\.(py|js|mjs|cjs|ts|tsx|jsx|go|rs|java|rb|php|c|h|cc|cpp|swift|kt)$")

SENT = re.compile(r"[^。！？\n]+[。！？]?")
SIDE_TOK = re.compile(r"(?<![A-Za-z])([AB])(?![A-Za-z])")
# 「整个套件没跑过」一类断言。必须落在整体上：说「某条用例没核对到某个行为」是对
# 覆盖面的评价，轨迹里跑过测试并不能反驳它，早先不加限定，这类句子会被整批误报。
NO_RUN = re.compile(r"(没有|未|不曾|再没|没再|一[次条组套]都没|一[次条组套]也没)[^，。；]{0,18}"
                    r"(完整(?:地)?(?:跑|运行|执行)|完整回归|全量|套件"
                    r"|回归的?记录|(?:跑|运行|执行)[^，。；]{0,4}回归"
                    r"|测试记录|构建或测试|通过的(?:记录|检查|结果)|再运行过|再跑"
                    r"|走绿|跑起来|跑过|跑绿|执行过|运行过)")
# 「戛然而止」一类断言
NO_END = re.compile(r"(戛然而止|戛然|未报错.{0,6}中断|无报错中止|直接结束|没有收尾"
                    r"|没有任何后续|未见后续|之后没有(?:任何)?(?:后续|动作))")
# 收尾总结的样子
DONE = re.compile(r"(全部完成|修复完成|实现完成|完成了|总结一下|所有测试通过|全部验证通过"
                  r"|检查通过|已完成|complete|Summary|## )")


def walk(task_no: str, side: str) -> list[dict]:
    """把一侧轨迹摊成工具调用序列，附上 assistant 的正文。"""
    files = sorted((EXPORTS / task_no / side).glob("*.jsonl"))
    if not files:
        return []
    seq: list[dict] = []
    by: dict[str, dict] = {}
    for raw in files[0].read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        if obj.get("type") == "assistant":
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    step = {"kind": "tool", "tool": b.get("name", ""),
                            "input": b.get("input") or {}, "is_error": False, "text": ""}
                    seq.append(step)
                    by[str(b.get("id"))] = step
                elif b.get("type") == "text" and str(b.get("text", "")).strip():
                    seq.append({"kind": "text", "tool": "", "input": {},
                                "is_error": False, "text": str(b["text"]).strip()})
        elif obj.get("type") == "user":
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    step = by.get(str(b.get("tool_use_id")))
                    if step is not None:
                        step["is_error"] = bool(b.get("is_error"))
    return seq


def dropped_tail(seq: list[dict]) -> int:
    """按 gsb_analyzer 的压缩规则，算出当时被切掉的尾部步数。"""
    if len(seq) <= STEP_LIMIT:
        return 0
    err = [i for i, s in enumerate(seq) if s["is_error"]]
    plain = [i for i, s in enumerate(seq) if not s["is_error"]]
    room = STEP_LIMIT - len(err)
    sel = plain[::max(1, len(plain) // room)][:room] if room > 0 else []
    kept = sel + err
    return len(seq) - 1 - max(kept) if kept else len(seq)


def evidence(seq: list[dict]) -> dict:
    """这一侧到底有没有「改完之后跑通过」和「像样的收尾」。"""
    last_edit = -1
    for i, s in enumerate(seq):
        if s["tool"] in SRC_EDIT and SRC_PATH.search(str(s["input"].get("file_path", ""))):
            last_edit = i
    passed = []
    for s in seq[last_edit + 1:]:
        cmd = str(s["input"].get("command", "")) if s["tool"] == "Bash" else ""
        if cmd and not s["is_error"] and TEST_CMD.search(cmd):
            passed.append(" ".join(cmd.split())[:110])
    tail_text = next((s["text"] for s in reversed(seq) if s["kind"] == "text"), "")
    return {"last_edit": last_edit, "passed_after_edit": passed,
            "tail_text": tail_text,
            "tail_is_summary": bool(DONE.search(tail_text)) and len(tail_text) > 300,
            "steps": len(seq), "dropped_tail": dropped_tail(seq)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="UPLOADED")
    # 默认只查 reason。remark 写的都是「这些现象我没计入判断」，说错了不改变结论，
    # 混在一起报会把真正影响判断的那几条淹掉。要看就显式加这个开关。
    ap.add_argument("--with-remark", action="store_true")
    args = ap.parse_args()
    fields = ("reason", "remark") if args.with_remark else ("reason",)
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute("select task_no, gsb_json from task where status=?",
                       (args.status,)).fetchall()
    con.close()

    hits = []
    for task_no, gsb_json in rows:
        try:
            gsb = json.loads(gsb_json) if gsb_json else {}
        except ValueError:
            continue
        if not gsb:
            continue
        ev = {}
        for field in fields:
            # 「它」「这一侧」这类代词句不带 A/B，侧别按段落从上一句继承，否则会漏掉
            # 一整类断言——112 那条「最后一批源码改动后也没有成功的构建或测试记录」
            # 就是拿代词指代的。换段清空，免得跨段串到另一侧。
            for para in (gsb.get(field) or "").split("\n"):
                carry = ""
                for sent in SENT.findall(para):
                    sides = set(SIDE_TOK.findall(sent))
                    if len(sides) == 1:
                        carry = sides.pop()
                    elif len(sides) > 1:
                        carry = ""
                    side = carry
                    kinds = []
                    if NO_RUN.search(sent):
                        kinds.append("no_run")
                    if NO_END.search(sent):
                        kinds.append("no_end")
                    if not kinds or not side:
                        continue
                    if side not in ev:
                        ev[side] = evidence(walk(task_no, side))
                    e = ev[side]
                    if not e["steps"]:
                        continue
                    if "no_end" in kinds and e["tail_is_summary"]:
                        hits.append((task_no, side, field, "no_end", sent.strip(), e))
                    elif "no_run" in kinds and e["passed_after_edit"]:
                        hits.append((task_no, side, field, "no_run", sent.strip(), e))

    label = {"no_run": "断言「没跑过」，但轨迹里改完之后跑通了",
             "no_end": "断言「戛然而止」，但轨迹末尾是完整收尾总结"}
    print(f"已提交 {len(rows)} 道题，与轨迹矛盾的断言 {len(hits)} 条\n")
    for task_no, side, field, kind, sent, e in hits:
        print(f"== {task_no} / {side} 侧 / {field}  —— {label[kind]}")
        print(f"   断言：{sent}")
        print(f"   轨迹：{e['steps']} 步，分析时被压掉尾部 {e['dropped_tail']} 步")
        if kind == "no_run":
            for c in e["passed_after_edit"][-3:]:
                print(f"   改完之后跑通的命令：{c}")
        print(f"   轨迹末尾原文：{' '.join(e['tail_text'].split())[:150]}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
