"""五维评审的交叉核验：证据能否在轨迹里定位、分数与描述是否自洽、描述是否有 AI 痕迹。

级别：block（禁止上传）/ warn（人工确认后可传）/ ok。
"""

from __future__ import annotations

import re
from typing import Any

DIMS = ("delivery", "instruction", "planning", "reasoning", "execution")
DIM_LABELS = {
    "delivery": "交付完整性",
    "instruction": "指令遵循",
    "planning": "任务规划",
    "reasoning": "推理能力",
    "execution": "执行能力",
}

# 结构词与 AI 高频词。命中即 warn，并把词高亮给人看。
AI_WORDS = (
    "首先", "其次", "再次", "最后", "综上", "综上所述", "总的来说", "总而言之", "总之", "值得注意的是",
    "值得一提", "此外", "另外", "不仅", "而且", "显然", "众所周知", "毫无疑问", "令人", "堪称", "完美地",
    "出色地", "优雅", "精妙", "丝滑", "赋能", "闭环", "抓手", "深入浅出", "一言以蔽之", "亮点", "整体而言",
    "从整体上看", "可以看出", "由此可见", "需要指出", "遗憾的是", "令人印象深刻", "展现了", "体现了",
    "表现出色", "表现良好", "表现一般", "基本可用", "效果不错", "非常", "极其", "十分", "相当",
)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\U0001F000-\U0001F2FF]")
MARKDOWN_RE = re.compile(r"(^\s*[-*•]\s+|^\s*#{1,6}\s|\*\*[^*]+\*\*|`[^`]+`|^\s*\d+\.\s+)", re.M)
_WS = re.compile(r"\s+")

# 描述会原样交付给评审方，本机目录结构不能跟着一起出去，所以按红项拦。
# 容器里的 /workspace 是题目环境的标准路径，交付信息里本来就有，只提醒改成相对路径。
ABS_PATH_RE = re.compile(r"(?<![\w.])/(?:[A-Za-z0-9_.\-\u4e00-\u9fff]+/){1,}")
HOST_DIR_WORDS = ("/host", "/data/", "/Users/", "分析/", "出题/")
CONTAINER_DIR = "/workspace"

# 对分析环境的自述：说的是我这次怎么核验的，不是被评模型的能力，写进去既没意义也显得荒唐
META_TALK_WORDS = (
    "node_modules", "产物副本", "沙箱", "我这边", "我的环境", "本地环境", "跑不起来", "跑不了",
    "无法运行", "没法运行", "不能运行", "没有装依赖", "未安装依赖", "没有安装依赖",
    "可执行文件", "没有联网", "无法联网", "不影响结论",
)


def _norm(s: str) -> str:
    return _WS.sub("", s or "").lower()


def check_text_style(text: str) -> list[dict]:
    items: list[dict] = []
    if not text or not text.strip():
        return [{"level": "block", "code": "empty", "message": "描述为空"}]
    if len(text.strip()) < 30:
        items.append({"level": "warn", "code": "too_short", "message": f"描述只有 {len(text.strip())} 字，缺少可核验的具体依据"})
    if EMOJI_RE.search(text):
        items.append({"level": "warn", "code": "emoji", "message": "包含表情符号"})
    if MARKDOWN_RE.search(text):
        items.append({"level": "warn", "code": "markdown", "message": "包含 markdown 标记（列表/标题/加粗/代码块）"})
    hits = [w for w in AI_WORDS if w in text]
    if hits:
        items.append({"level": "warn", "code": "ai_words", "message": f"包含结构词/AI 高频词：{'、'.join(hits[:6])}", "words": hits})
    found = [m.group(0) for m in ABS_PATH_RE.finditer(text)] + [w for w in HOST_DIR_WORDS if w in text]
    host = [p for p in dict.fromkeys(found) if not p.startswith(CONTAINER_DIR)]
    if host:
        items.append({"level": "block", "code": "abs_path", "words": host,
                      "message": f"出现本机路径/目录名：{'、'.join(host)[:80]}，交付前必须改成仓库内相对路径"})
    elif any(p.startswith(CONTAINER_DIR) for p in found):
        items.append({"level": "warn", "code": "container_path",
                      "message": "引用了容器内的 /workspace 绝对路径，建议写成仓库内相对路径"})
    meta = [w for w in META_TALK_WORDS if w in text]
    if meta:
        items.append({"level": "block", "code": "meta_talk", "words": meta,
                      "message": f"在讲我自己的核验环境而不是被评模型：{'、'.join(meta[:6])}，删掉这部分只留基于代码与轨迹的结论"})
    if "我" not in text:
        items.append({"level": "warn", "code": "not_first_person", "message": "没有出现第一人称「我」"})
    return items


def _find_step(steps: list[dict], no: Any) -> dict | None:
    try:
        n = int(no)
    except (TypeError, ValueError):
        return None
    for s in steps:
        if s.get("step") == n:
            return s
    return None


def check_evidence(evidence: list[dict], steps: list[dict]) -> tuple[list[dict], int, int]:
    items: list[dict] = []
    total = hit = 0
    all_files = {f for s in steps for f in (s.get("files") or [])}
    all_text = _norm(" ".join(f"{s.get('summary', '')} {s.get('result', '')}" for s in steps))
    for ev in evidence or []:
        if not isinstance(ev, dict):
            continue
        total += 1
        ok = True
        step = _find_step(steps, ev.get("step")) if ev.get("step") not in (None, "", 0) else None
        if ev.get("step") not in (None, "", 0) and step is None:
            ok = False
            items.append({"level": "warn", "code": "step_missing", "message": f"证据引用的第 {ev.get('step')} 步在轨迹中不存在"})
        file = str(ev.get("file") or "").strip()
        if file:
            in_step = step is not None and any(file in f or f.endswith(file) for f in (step.get("files") or []))
            in_any = any(file in f or f.endswith(file) for f in all_files) or _norm(file) in all_text
            if not (in_step or in_any):
                ok = False
                items.append({"level": "warn", "code": "file_missing", "message": f"证据文件 {file} 未在轨迹中出现"})
        quote = str(ev.get("quote") or "").strip()
        if quote:
            q = _norm(quote)[:80]
            hay = _norm(f"{step.get('summary', '')} {step.get('result', '')}") if step else all_text
            if q and q not in hay and q not in all_text:
                ok = False
                items.append({"level": "warn", "code": "quote_missing", "message": f"引文「{quote[:40]}…」无法在轨迹中定位"})
        hit += 1 if ok else 0
    return items, total, hit


def verify(review: dict, trace_index: dict) -> dict:
    """review = {scores:{dim:int}, descs:{dim:str}, evidence:{dim:[...]}, other_issues:str, coverage:[...]}"""
    steps = (trace_index or {}).get("steps") or []
    scores = review.get("scores") or {}
    descs = review.get("descs") or {}
    evidence = review.get("evidence") or {}
    coverage = review.get("coverage") or []

    items: list[dict] = []
    ev_total = ev_hit = 0
    for dim in DIMS:
        label = DIM_LABELS[dim]
        score = scores.get(dim)
        if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
            items.append({"dim": dim, "level": "block", "code": "score_invalid", "message": f"{label}分数必须是 1–5 的整数"})
        for it in check_text_style(str(descs.get(dim) or "")):
            items.append({"dim": dim, **it})
        ev_items, t, h = check_evidence(evidence.get(dim) or [], steps)
        ev_total += t
        ev_hit += h
        for it in ev_items:
            items.append({"dim": dim, **it})
        if steps and not (evidence.get(dim) or []):
            items.append({"dim": dim, "level": "warn", "code": "no_evidence", "message": f"{label}没有引用任何轨迹步骤作为证据"})

    # 描述雷同
    texts = [_norm(str(descs.get(d) or "")) for d in DIMS]
    for i in range(len(DIMS)):
        for j in range(i + 1, len(DIMS)):
            if texts[i] and texts[i] == texts[j]:
                items.append({"dim": DIMS[j], "level": "block", "code": "duplicate_desc",
                              "message": f"{DIM_LABELS[DIMS[i]]}与{DIM_LABELS[DIMS[j]]}的描述完全相同"})

    # 分数 vs 需求覆盖
    missing = [c for c in coverage if isinstance(c, dict) and str(c.get("status", "")).lower() in ("missing", "partial")]
    d_score = scores.get("delivery")
    if isinstance(d_score, int) and coverage:
        if d_score >= 4 and any(str(c.get("status", "")).lower() == "missing" for c in coverage):
            items.append({"dim": "delivery", "level": "block", "code": "score_coverage_conflict",
                          "message": f"交付完整性打了 {d_score} 分，但需求覆盖表里有 {len(missing)} 项未实现/部分实现"})
        if d_score <= 2 and not missing:
            items.append({"dim": "delivery", "level": "warn", "code": "score_coverage_conflict",
                          "message": f"交付完整性只打了 {d_score} 分，但需求覆盖表全部标为已实现，请核对"})

    other = str(review.get("other_issues") or "")
    if other.strip():
        for it in check_text_style(other):
            if it["code"] != "too_short" and it["code"] != "not_first_person":
                items.append({"dim": "other", **it})

    levels = {i["level"] for i in items}
    overall = "block" if "block" in levels else ("warn" if "warn" in levels else "pass")
    return {
        "overall": overall,
        "blocks": len([i for i in items if i["level"] == "block"]),
        "warns": len([i for i in items if i["level"] == "warn"]),
        "evidence_total": ev_total,
        "evidence_hit": ev_hit,
        "evidence_hit_rate": (round(ev_hit / ev_total, 2) if ev_total else None),
        "items": items,
    }
