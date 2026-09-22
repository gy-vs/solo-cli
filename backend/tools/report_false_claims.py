"""生成已提交题目的数据订正文档。

一道题一节，按「平台上现在是什么 → 改成了什么 → 凭轨迹哪一处认定原文是错的」排，
因为这份文档是拿去跟平台对账的：对方看到的是提交时那一版，要先认出是哪一条，才谈
得上换成哪一条。

轨迹依据不在这里另写一份，直接取 patch_gsb_false_claims 里那份。同一个判断在两处
各写一遍，迟早会走样成两种说法。

用法：python3 backend/tools/report_false_claims.py > docs/已提交题目数据订正.md
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "solo-cli.db"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from patch_gsb_false_claims import EDITS  # noqa: E402

BACKUPS = sorted((ROOT / "data").glob("_gsb_backup_before_claim_fix_*.json"))

VERDICT = {"A": "A 更好", "B": "B 更好", "Same": "Same"}

# 这两道不是措辞错，结论本身架在被压掉的那截材料上，所以没有改文字。
NEEDS_RERUN = {
    "16": (
        "理由认定 A 的解码器不能用（主表只有十位宽、十一位符号的前缀没建出子表），"
        "并据此判 B 更好。但 A 交付的 src/huffman.ts 里 PRIMARY_BITS 之外有完整的两级子表构造，"
        "A 自己的收尾自述也写着 huffman.ts 是两级解码表；末轮 tsc 干净、全部用例通过，"
        "其中包含 zlib 各压缩级别、多种分布与窗口边界的双向互通。"
        "理由里另一句「benchmarks 下的脚本一次都没执行过」同样不成立，"
        "A 跑过 tradeoff 与 realistic 两个基准并拿到了体积比与吞吐数字。"
    ),
    "104-gaoyong": (
        "理由认定 B 留着一条没解决的失败用例、之后没有通过的记录，并据此判 A 更好。"
        "但 B 末尾类型检查通过，全部用例通过，收尾自述也是完成交付。"
        "「解码器实现不在补丁里」这半句成立（源文件当时还未被跟踪，补丁按预算截断了），"
        "失败用例那半句不成立。"
    ),
}

# 已订正的那十一道，错的都是次要的一句，判断另有立足点（代码里一处能核到的缺陷），
# 所以换掉那句话结论不动。这两道相反，下面三栏把「错的那句就是立足点」摆开来看。
FALSE_SENTENCE = {
    "16": "「这一缺陷在交付前始终没有修复，也没有一次完整通过的测试记录」"
          "与「benchmarks 下的脚本一次都没执行过」。",
    "104-gaoyong": "「它记录的最后一次运行仍有用例没过……之后没有通过的记录」。",
}

VERDICT_SENTENCE = {
    "16": "「但解码器在最常见的那档码长上失效，整个库就用不了，综合来看 B 更好」"
          "——B 胜出全靠这一条。",
    "104-gaoyong": "「B 则是一条尚未解决的失败用例，加上一份无法查看的实现。所以 A 更好」"
                   "——A 胜出全靠这一条。",
}

WHAT_REMAINS = {
    "16": "同一段理由自己写着 A 在跳转边界语义、分块写入的流式入口和 gzip 头兼容上比 B 做得好，"
          "而记在 B 名下的是过程绕远。去掉两句不成立的指控，剩下的材料指向的是 A，"
          "结论很可能要翻过来。",
    "104-gaoyong": "B 只剩「实现不在补丁里」，而这是材料截断造成的，不是模型的毛病；"
                   "A 那两处缺陷（位翻转用例写成空操作、窗口左移后重扫起点用了旧坐标）是实打实的。"
                   "两边对比因此可能变成 B 更好或者持平。",
}


def load_before() -> dict[str, dict]:
    if not BACKUPS:
        return {}
    return json.loads(BACKUPS[-1].read_text(encoding="utf-8"))


def quote(text: str) -> str:
    """当引用块排版。空正文要显式写出来，不能留一片空白让人以为是漏了。"""
    text = (text or "").strip()
    if not text:
        return "> （空）"
    return "\n".join("> " + line if line.strip() else ">" for line in text.split("\n"))


def main() -> int:
    before = load_before()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

    evidence: dict[str, list[str]] = {}
    for task_no, field, _, _, why in EDITS:
        evidence.setdefault(task_no, [])
        if why not in evidence[task_no]:
            evidence[task_no].append(why)

    order = sorted(set(list(evidence) + list(NEEDS_RERUN)),
                   key=lambda t: int(t.split("-")[0]))

    print("# 已提交题目的数据订正")
    print()
    print("把已提交的题目逐条拿回轨迹里核过一遍之后，这些题的 GSB 理由里有与轨迹矛盾的断言。")
    print("矛盾集中在一类说法上：称某一侧「没跑测试」或「戛然而止」，而那一侧的轨迹末尾"
          "摆着成功的测试记录和完整收尾总结。")
    print()
    print("只收已提交状态、且问题出在理由里的题目。理由是提交给平台的判断正文，"
          "写错就是错报；与它一同提交的备注字段写的是「这些现象我看到了但没计入判断」，"
          "不在这份文档的范围内，库里也没有改动过。")
    print()
    print("成因是分析器喂给模型的材料被截断。轨迹步骤超过上限就压缩，"
          "而等距抽样那步会把尾部整段切掉，模型因此看不到收尾；"
          "压缩后的步骤又只带命令与是否报错、不带命令输出，"
          "测试跑出来是绿还是红，材料里本就分辨不出。截断已修，回归测试锁住了收尾步不许再被切掉。")
    print()
    print("下面分两类，区别在于错的那句话是不是判断的立足点。")
    print()
    print("第一类，错的是次要的一句，判断另有立足点——代码里一处能独立核到的缺陷，"
          "所以换掉那句话结论不动，正文已订正，每道题都给出改前改后两版。")
    print()
    print("第二类，错的那句就是判断的立足点，删掉它结论也就没了支撑。"
          "这类题**没有改后版本**，不是漏抄：改一句话要么得换结论，"
          "要么得另编一条理由，两样都不能由人在文本上替模型定，只能拿修好的材料重跑分析。"
          "这类题的小节里列了三栏——错的那句、判断落在哪一句、删掉之后还剩什么——便于复核。")
    print()

    fixed = [t for t in order if t not in NEEDS_RERUN]
    print(f"理由已订正 {len(fixed)} 道：{'、'.join(fixed)}")
    print()
    print(f"理由待重跑 {len(NEEDS_RERUN)} 道：{'、'.join(t for t in order if t in NEEDS_RERUN)}")
    print()

    for task_no in order:
        row = con.execute(
            "select user_prompt, gsb_json, upload_json, uploaded_at, question_type, "
            "difficulty, languages, repo_url from task where task_no=?", (task_no,)).fetchone()
        prompt, gsb_json, upload_json, uploaded_at, qtype, diff, langs, repo = row
        gsb = json.loads(gsb_json)
        up = json.loads(upload_json) if upload_json else {}
        old = before.get(task_no, gsb)
        rerun = task_no in NEEDS_RERUN

        print("---")
        print()
        print(f"## {task_no}　平台提交 ID {up.get('submission_id', '—')}")
        print()
        print(f"- 结论：{VERDICT.get(gsb.get('verdict', ''), gsb.get('verdict', ''))}")
        print(f"- 上传时间：{uploaded_at}")
        print(f"- 题目类型：{qtype}　难度：{diff}　语言：{langs}")
        print(f"- 仓库：{repo}")
        print(f"- 处理：{'未改动，需重跑分析' if rerun else '正文已订正'}")
        print()

        print("### prompt 原文")
        print()
        print(quote(prompt))
        print()

        if rerun:
            print("### 提交的理由（未改动）")
            print()
            print(quote(gsb.get("reason")))
            print()
            # 这里必须显式写一句「没有改后版本」。留空会被当成漏抄，读的人会回头找
            # 数据，而不是去看下一节讲的原因。
            print("### 理由　改后")
            print()
            print("> （没有改后版本。这道题不是某句话写错，错的那句正是判断的立足点，"
                  "换掉它就等于换结论，只能重跑分析。原因见下。）")
            print()
            print("### 为什么判断站不住")
            print()
            print(NEEDS_RERUN[task_no])
            print()
            print(f"错的那句：{FALSE_SENTENCE[task_no]}")
            print()
            print(f"判断落在哪一句：{VERDICT_SENTENCE[task_no]}")
            print()
            print(f"删掉错的那句之后剩下什么：{WHAT_REMAINS[task_no]}")
            print()
            continue

        print("### 理由　改前（平台上现在是这一版）")
        print()
        print(quote(old.get("reason")))
        print()
        print("### 理由　改后")
        print()
        print(quote(gsb.get("reason")))
        print()

        print("### 轨迹依据")
        print()
        for why in evidence.get(task_no, []):
            print(f"- {why}")
        print()

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
