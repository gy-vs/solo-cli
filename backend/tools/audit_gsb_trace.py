"""把已提交题目的 GSB 正文逐条拿回轨迹里对一遍，找虚报。

只看轨迹这一个证据源：理由和 findings 里提到的文件、函数、命令，如果在对应那侧的
轨迹全文里搜不到，就是需要人看一眼的可疑项。轨迹是提交给平台的东西，平台质检也只
能拿它当证据，所以「轨迹里搜不到」正是会被打回的那条线。

侧别是分开的：a_findings 只许对 A 侧的轨迹成立，写进 A 却只在 B 里出现属于串侧，
和纯虚报不是一回事，所以分两类报。reason 里两侧混着写，按两侧并集判。

用法：python3 backend/tools/audit_gsb_trace.py [--status UPLOADED] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "solo-cli.db"
EXPORTS = ROOT / "data" / "exports"

# 带目录的路径，或带常见扩展名的裸文件名
FILE_REF = re.compile(
    r"(?:[\w.\-]+/)+[\w.\-]+\.\w{1,6}"
    r"|[\w\-]+\.(?:py|js|mjs|cjs|ts|tsx|jsx|go|rs|java|rb|php|c|h|cc|cpp|hpp|cs|swift|kt"
    r"|json|ya?ml|toml|ini|cfg|md|txt|sh|sql|html|css|scss|vue|svelte)\b")
# 目录引用：benchmarks/、tests/doc/ 这类不带扩展名的
DIR_REF = re.compile(r"(?:[\w.\-]+/){1,}(?=[^\w/]|$)")
# ASCII 串，后面可能跟一对括号
ASCII_RUN = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*(?:\(\))?")

# 散文里会出现、但不是代码符号的词。命中这些一律不查，宁可漏报也别把正常中文里
# 夹的英文名词报成虚报。
PROSE = {
    "a", "b", "same", "ai", "api", "apis", "cli", "id", "ids", "ok", "no", "op", "os",
    "gsb", "qa", "cc", "diff", "diffs", "git", "github", "commit", "sha", "url", "json",
    "jsonl", "yaml", "yml", "toml", "md", "readme", "license", "changelog", "todo",
    "npm", "npx", "pnpm", "yarn", "node", "nodejs", "python", "pip", "go", "rust",
    "cargo", "java", "maven", "gradle", "ruby", "php", "dotnet", "docker",
    "linux", "macos", "windows", "unix", "posix", "apfs", "utf", "ascii", "sdk",
    "js", "ts", "tsx", "jsx", "css", "scss", "html", "sql", "http", "https", "tcp",
    "jest", "mocha", "vitest", "pytest", "eslint", "prettier", "babel", "webpack",
    "vite", "rollup", "tsc", "typescript", "javascript", "zlib", "gzip", "deflate",
    "prompt", "token", "tokens", "harness", "claude", "code", "cursor", "opus",
    "true", "false", "null", "none", "nan", "inf", "int", "str", "bool", "float",
    "the", "and", "or", "not", "is", "in", "of", "to", "for", "with", "by", "on",
    "i", "it", "its", "this", "that", "we", "you", "he", "she", "they",
    "pr", "ci", "cd", "ide", "ui", "ux", "db", "sqlite", "mysql", "redis",
    "mb", "kb", "gb", "ms", "cpu", "ram", "uuid", "regex", "ast", "nfa", "dfa",
    "tz", "utc", "iso", "rfc", "bom", "eof", "eol", "crlf", "lf",
}

# 看起来像代码符号的形状：驼峰、下划线、点号连接、或写了括号
CAMEL = re.compile(r"[a-z][a-z0-9]*[A-Z]")
UPPER_SNAKE = re.compile(r"^[A-Z][A-Z0-9]*_[A-Z0-9_]+$")


def looks_like_symbol(tok: str) -> bool:
    core = tok[:-2] if tok.endswith("()") else tok
    if len(core) < 3:
        return False
    if core.lower() in PROSE:
        return False
    if tok.endswith("()"):
        return True
    if "_" in core and not core.startswith("__"):
        return True
    if CAMEL.search(core):
        return True
    if "." in core:
        # foo.bar 形式的成员访问；两段都得像标识符
        parts = core.split(".")
        return len(parts) == 2 and all(p and p[0].isalpha() for p in parts) \
            and parts[1].lower() not in PROSE
    return False


def extract(text: str) -> tuple[set[str], set[str]]:
    """返回（文件/目录引用，代码符号）。"""
    files = set(FILE_REF.findall(text))
    for d in DIR_REF.findall(text):
        d = d.strip("/")
        if d and "/" not in d and d.lower() not in PROSE and "." not in d:
            files.add(d + "/")
    masked = FILE_REF.sub(" ", text)
    syms = {t for t in ASCII_RUN.findall(masked) if looks_like_symbol(t)}
    return files, syms


def load_trace(task_no: str, side: str) -> str:
    d = EXPORTS / task_no / side
    if not d.is_dir():
        return ""
    return "\n".join(f.read_text(encoding="utf-8", errors="replace")
                     for f in sorted(d.glob("*.jsonl")))


def hit(needle: str, hay: str, hay_low: str) -> bool:
    n = needle[:-2] if needle.endswith("()") else needle
    if n in hay:
        return True
    if n.lower() in hay_low:
        return True
    if "/" in n:
        # 理由里可能按仓库根写路径，轨迹里是 /workspace 下的绝对路径或裸文件名
        tail = n.rstrip("/").rsplit("/", 1)[-1]
        if tail and (tail in hay or tail.lower() in hay_low):
            return True
    elif "." in n:
        # 「类.方法」是散文写法，代码里从不连写：分开找，两段都在才算对上
        return all(p in hay or p.lower() in hay_low for p in n.split("."))
    return False


def segment_texts(gsb: dict) -> list[tuple[str, str | None, str]]:
    out: list[tuple[str, str | None, str]] = []
    out.append(("reason", None, gsb.get("reason") or ""))
    for who in ("a", "b"):
        side = who.upper()
        f = gsb.get(f"{who}_findings") or {}
        for kind in ("good", "bad"):
            items = f.get(kind) or []
            if items:
                out.append((f"{who}_findings.{kind}", side, "\n".join(map(str, items))))
        st = gsb.get(f"{who}_startup") or {}
        chunks = list(st.get("steps") or []) + list(st.get("commands") or [])
        if st.get("note"):
            chunks.append(st["note"])
        if chunks:
            out.append((f"{who}_startup", side, "\n".join(map(str, chunks))))
    return out


SENT = re.compile(r"[^。！？\n]+[。！？]?")
SIDE_TOK = re.compile(r"(?<![A-Za-z])([AB])(?![A-Za-z])")


def diff_files(stat: str) -> set[str]:
    """从 git diff --stat 的文本里取出改动过的文件名。"""
    out = set()
    for line in (stat or "").splitlines():
        if "|" not in line:
            continue
        name = line.split("|", 1)[0].strip()
        if name and not name.startswith(("未跟踪", "改动")):
            out.add(name.lstrip("./"))
    return out


def audit_sides(gsb: dict, diffs: dict[str, set[str]]) -> list[dict]:
    """理由按句判侧：这句只说 A，句里的文件就该在 A 改过的清单里。

    抓的是把一侧干的事写到另一侧名下这种错——评审一眼就能看出来，也是最伤的一种。
    一句话里 A、B 都提到或都没提到时不判，宁可不报。
    """
    both = diffs["A"] | diffs["B"]
    found = []
    for sent in SENT.findall(gsb.get("reason") or ""):
        sides = set(SIDE_TOK.findall(sent))
        if len(sides) != 1:
            continue
        side = sides.pop()
        other = "B" if side == "A" else "A"
        files, _ = extract(sent)
        for f in sorted(files):
            f = f.rstrip("/")
            mine = any(d == f or d.endswith("/" + f) for d in diffs[side])
            theirs = any(d == f or d.endswith("/" + f) for d in diffs[other])
            # 只有对方改过、这一侧没碰过，才算归属写错；两侧都没改说明只是读过
            if theirs and not mine and any(d == f or d.endswith("/" + f) for d in both):
                found.append({"segment": "reason(按句判侧)", "kind": "file", "ref": f,
                              "issue": f"这句只说 {side}，但 {f} 只有 {other} 侧改过",
                              "sentence": sent.strip()})
    return found


def audit_task(task_no: str, gsb: dict, diffs: dict[str, set[str]] | None = None) -> dict:
    traces = {s: load_trace(task_no, s) for s in ("A", "B")}
    low = {s: t.lower() for s, t in traces.items()}
    both = traces["A"] + "\n" + traces["B"]
    both_low = low["A"] + "\n" + low["B"]

    findings: list[dict] = []
    checked = 0
    for seg, side, text in segment_texts(gsb):
        files, syms = extract(text)
        for kind, refs in (("file", files), ("symbol", syms)):
            for r in sorted(refs):
                checked += 1
                if side is None:
                    if not hit(r, both, both_low):
                        findings.append({"segment": seg, "kind": kind, "ref": r,
                                         "issue": "两侧轨迹都搜不到"})
                    continue
                if hit(r, traces[side], low[side]):
                    continue
                other = "B" if side == "A" else "A"
                if hit(r, traces[other], low[other]):
                    findings.append({"segment": seg, "kind": kind, "ref": r,
                                     "issue": f"只在 {other} 侧轨迹里出现（串侧）"})
                else:
                    findings.append({"segment": seg, "kind": kind, "ref": r,
                                     "issue": f"{side} 侧轨迹里搜不到"})
    if diffs:
        findings.extend(audit_sides(gsb, diffs))
    return {"task_no": task_no, "checked": checked, "findings": findings,
            "traces": {s: len(t) for s, t in traces.items()}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="UPLOADED")
    ap.add_argument("--task", action="append", default=[])
    ap.add_argument("--json", dest="out")
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    if args.task:
        q = ("select task_no, gsb_json from task where task_no in (%s)"
             % ",".join("?" * len(args.task)))
        rows = con.execute(q, args.task).fetchall()
    else:
        rows = con.execute("select task_no, gsb_json from task where status=?",
                           (args.status,)).fetchall()
    diffs: dict[str, dict[str, set[str]]] = {}
    for task_no, side, stat in con.execute(
            "select t.task_no, r.side, r.git_diff_stat from task t "
            "join task_run r on r.task_id = t.id"):
        diffs.setdefault(task_no, {"A": set(), "B": set()})[side] = diff_files(stat)
    con.close()

    reports = []
    for task_no, gsb_json in rows:
        try:
            gsb = json.loads(gsb_json) if gsb_json else {}
        except ValueError:
            print(f"[{task_no}] gsb_json 解析失败", file=sys.stderr)
            continue
        if not gsb:
            continue
        reports.append(audit_task(task_no, gsb, diffs.get(task_no)))

    reports.sort(key=lambda r: (-len(r["findings"]), r["task_no"]))
    total_checked = sum(r["checked"] for r in reports)
    total_bad = sum(len(r["findings"]) for r in reports)
    print(f"题目 {len(reports)} 道，核对引用 {total_checked} 处，可疑 {total_bad} 处\n")
    for r in reports:
        if not r["findings"]:
            continue
        print(f"== {r['task_no']}  (轨迹 A={r['traces']['A']} B={r['traces']['B']} 字节)")
        for f in r["findings"]:
            print(f"   [{f['kind']:6}] {f['ref']:<42} {f['segment']:<18} {f['issue']}")
        print()
    if args.out:
        Path(args.out).write_text(json.dumps(reports, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
