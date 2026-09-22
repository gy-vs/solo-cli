"""改掉已提交题目理由里与轨迹矛盾的那几句话。

改的都是同一类毛病：说某一侧「没跑测试」「戛然而止」，而轨迹末尾摆着成功的测试
记录和完整收尾。成因是分析器压缩轨迹时把尾部切掉了（见 gsb_analyzer._condense_steps
的修复），不是分析得不认真，所以这里只订正事实，不动判断本身。

范围只有 reason，不含 remark。remark 写的是「这些现象我看到了但没计入判断」，说错了
不改变结论。早先有一轮连 remark 一起改过，按只管理由的口径已经用 --revert-remark
退回原样，现在库里被动过的只有理由。

替换按整句原文精确匹配，对不上就报错退出，避免在正文已经被人改过的情况下误改。
每条替换都附一句「轨迹依据」，写明订正的根据在轨迹哪里。

第 16 与第 104 题不在这里：它们的结论本身就架在被切掉的那截材料上（16 说 A 的解码器
建不出子表、整个库用不了，而 A 交付的 huffman.ts 有两级子表且与 zlib 各级别双向互通；
104 说 B 留着没过的用例，而 B 末尾类型检查与全部用例都通过），改措辞等于替一个站不住
的判断打补丁，只能重跑分析。

用法：
    python3 backend/tools/patch_gsb_false_claims.py                  # 只看 diff
    python3 backend/tools/patch_gsb_false_claims.py --apply          # 落库（先自动备份）
    python3 backend/tools/patch_gsb_false_claims.py --revert-remark  # 把 remark 退回原样
"""

from __future__ import annotations

import argparse
import difflib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "solo-cli.db"
sys.path.insert(0, str(ROOT / "backend"))

# (题号, 字段, 原文整句, 改后, 轨迹依据)
EDITS: tuple[tuple[str, str, str, str, str], ...] = (
    ("26", "reason",
     "B 的问题出在交付环节，修改完之后没有再运行完整回归。漏跑回归带来的只是尚未确认的风险，"
     "而打印出行为不一致的代码会直接影响拿到产物的使用者，综合来看 B 更好。",
     "B 的问题在于自行扩大了改动面，reduce-vars 的逃逸边界收紧并不是用户点名要的，"
     "方向虽然和普通调用一致，却会让动态引入参数附近的一些对象更难内联。这类额外改动还能单独回退，"
     "而打印出行为不一致的代码会直接影响拿到产物的使用者，综合来看 B 更好。",
     "B 最后一次改源码之后跑过完整回归：compress 用例、mocha 全量与 eslint 依次通过，"
     "「没有再运行完整回归」不成立；换上的这条不足取自 B 自己的改动范围。"),

    ("33", "reason",
     "今后修改 calc 相关代码的人要先把这几条反向的期望逐条改回来。这套用例在交付前也没有完整运行过。",
     "今后修改 calc 相关代码的人要先把这几条反向的期望逐条改回来。",
     "A 最后一次改 math-check.js 之后 lint 通过，ESM 与 CJS 两套用例都跑完且全部通过。"),
    ("33", "reason",
     "A 在报错定位粒度上更细，但这点优势建立在反复返工的推断之上，B 还有改动前后的对比运行和全量回归，"
     "所以 B 更好。",
     "A 在报错定位粒度上更细，但这点优势建立在反复返工的推断之上，"
     "而把合法写法写成必须报错的期望是眼下就存在的错误，所以 B 更好。",
     "原句拿「B 还跑了全量回归」跟 A 作对比，而 A 同样跑过，这个对比不成立。"),

    ("112-gaoyong", "reason",
     "问题是它把显示文本也提前转义，还按内容有条件地追加字段，token 形状随输入变化，"
     "最后一批源码改动后也没有成功的构建或测试记录。",
     "问题是它把显示文本也提前转义，还按内容有条件地追加字段，token 形状随输入变化，"
     "拿到这一版的人要先弄清 token 会长成什么样才敢往下改。",
     "B 最后一次改源码之后反复跑过构建与测试，末轮单元用例、规格用例、lint 与类型检查都通过。"),

    ("120-gaoyong", "reason",
     "必须重写这段识别逻辑才能修复。A 的 tests/test_getstate_setstate.py 在最后两次改动之后也没有再运行过。",
     "必须重写这段识别逻辑才能修复。A 的 docs/glossary.rst 里关于 slots 类自带状态方法会被覆盖的旧说明"
     "也没有同步，新开关上线后文档和实际行为不一致。",
     "A 最后一次改动之后跑过该测试文件，还连着几个相关模块一起跑；"
     "换上的这条不足在 A 侧轨迹里可以核到。"),
    ("120-gaoyong", "reason",
     "但 B 的新老用例一起运行过，核对的是实际运行得到的结果。综合来看，B 更好。",
     "但这两处都能在既有机制上补回来，而哈希缓存那段识别逻辑要整段重写，综合来看，B 更好。",
     "原句拿「B 跑过用例」跟 A 作对比，而 A 同样跑过，这个对比不成立。"),
)


def revert_remark() -> int:
    """按备份把 remark 原封不动写回去。

    早先那一轮把 remark 也订正了，后来口径收窄到只管理由。留着一半改过一半没改的
    remark 最难交代：跟平台对账时说不清哪几条动过。所以整类退回原样。
    """
    backups = sorted((ROOT / "data").glob("_gsb_backup_before_claim_fix_*.json"))
    if not backups:
        print("找不到备份，退不回去", file=sys.stderr)
        return 1
    before = json.loads(backups[-1].read_text(encoding="utf-8"))
    con = sqlite3.connect(DB)
    touched = []
    for task_no, old in before.items():
        row = con.execute("select gsb_json from task where task_no=? and status='UPLOADED'",
                          (task_no,)).fetchone()
        if row is None:
            continue
        gsb = json.loads(row[0])
        if (gsb.get("remark") or "") == (old.get("remark") or ""):
            continue
        gsb["remark"] = old.get("remark") or ""
        con.execute("update task set gsb_json=?, updated_at=datetime('now') "
                    "where task_no=? and status='UPLOADED'",
                    (json.dumps(gsb, ensure_ascii=False), task_no))
        touched.append(task_no)
    con.commit()
    con.close()
    print(f"remark 已退回原样 {len(touched)} 道：{'、'.join(touched) or '无'}（依据 {backups[-1].name}）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revert-remark", action="store_true")
    args = ap.parse_args()
    if args.revert_remark:
        return revert_remark()

    from app.services import gsb_rules

    con = sqlite3.connect(DB if args.apply else f"file:{DB}?mode=ro", uri=not args.apply)
    gsbs: dict[str, dict] = {}
    for task_no, *_ in EDITS:
        if task_no in gsbs:
            continue
        row = con.execute("select gsb_json from task where task_no=? and status='UPLOADED'",
                          (task_no,)).fetchone()
        if row is None:
            print(f"[{task_no}] 库里找不到这道已提交的题", file=sys.stderr)
            return 1
        gsbs[task_no] = json.loads(row[0])

    before = {t: dict(g) for t, g in gsbs.items()}
    for task_no, field, old, new, why in EDITS:
        text = gsbs[task_no].get(field) or ""
        if old not in text:
            print(f"[{task_no}.{field}] 对不上原文，正文可能已被改过，整个脚本不执行：\n"
                  f"  找的是：{old[:60]}…", file=sys.stderr)
            return 1
        gsbs[task_no][field] = text.replace(old, new, 1).replace("。；", "。").strip()

    for task_no in gsbs:
        for field in ("reason", "remark"):
            a = (before[task_no].get(field) or "").strip()
            b = (gsbs[task_no].get(field) or "").strip()
            if a == b:
                continue
            print(f"===== {task_no} · {field}")
            for line in difflib.unified_diff(a.split("。"), b.split("。"),
                                             lineterm="", n=1,
                                             fromfile="改前", tofile="改后"):
                print("  " + line)
            print()
        bad = [m for _, lvl, m in gsb_rules.reason_checks(
            gsbs[task_no].get("reason") or "", verdict=gsbs[task_no].get("verdict", ""))
            if lvl == "block"]
        if bad:
            print(f"  !! {task_no} 改后的理由过不了规则：{bad}", file=sys.stderr)
            return 1

    print("理由文本全部通过写作规范的红线检查。")
    for task_no, field, _, _, why in EDITS:
        print(f"  {task_no}.{field} 依据：{why}")

    if not args.apply:
        print("\n这是预览。加 --apply 才会落库。")
        return 0

    # 只备份被改的这几份 gsb_json。整库五百多兆，复制一份纯属浪费，而回滚要的就是
    # 这几个字段的原值，照着它逐条写回即可。
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = ROOT / "data" / f"_gsb_backup_before_claim_fix_{stamp}.json"
    backup.write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")
    for task_no, gsb in gsbs.items():
        con.execute("update task set gsb_json=?, updated_at=datetime('now') "
                    "where task_no=? and status='UPLOADED'",
                    (json.dumps(gsb, ensure_ascii=False), task_no))
    con.commit()
    con.close()
    print(f"\n已落库。改前正文备份在 data/{backup.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
