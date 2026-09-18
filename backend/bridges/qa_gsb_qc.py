"""GSB 质检桥接：按平台口径给一道题的 GSB 结论做质检，只取结论不落库。

这个文件不在 solo-cli 的进程里运行，而是挂进 solo-qa 的后端镜像执行
（那套依赖 pin 了 sqlalchemy/pydantic 的具体版本，跟 solo-cli 直接混装会冲突）。
因此只用标准库 + solo-qa 自己的包，不要 import solo-cli 的任何模块。

走的是它的 `gsb.qc.runner.evaluate_one` —— 跟平台自动质检同一个函数，
而不是把规则在这边重抄一遍。抄一遍的写法上次已经失败过：五维质检那套字段
废弃后，这条桥接跟着变成死代码，而谁都没发现，因为它自成一套。

只读口径：
- 只调 `evaluate_one`，它按注释约定不改任何数据库状态；
- 不调 `apply_result` / `run_batch` / `pool_membership.sync_after_qc`
  / `lark.sync_service`，所以不写结论、不入查重池、不碰飞书；
- 关掉模型缓存，避免理由质检的模型调用写 `qc_llm_cache`；
- `trace_store.save_digest` 打成空操作 —— 轨迹摘要是链路里唯一的写库点，
  而它写的是 `submission_id` 这个在库里并不存在的虚拟 ID；
- 待检数据用 `MAX(id)` 之上的虚拟 row_id，只存在于内存，不落库。

轨迹不走对象存储：`trace_storage.local_file` 会先拿相对路径在 `DATA_DIR`
下找，找到就本地解析。调用方把两侧轨迹挂进容器的 `/app/data` 里，传相对
路径即可，全程不发网络请求。

录屏（规则 G8）默认声明为「稍后人工补」：本项目的录屏是人工环节，质检时
两侧必然为空，而 G8 在第一道闸就会短路返回，后面的 AI 痕迹检测一条都跑不到
—— 那恰恰是这条桥接唯一想要的东西。所以把 G8 摘掉并在输出里明说它被跳过了，
不是给它编一个假链接糊弄过去。

协议：stdin 一个 JSON 对象，stdout 一个 JSON 对象，日志全部走 stderr。
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _check_dict(c, rule_label) -> dict:
    """GsbCheck → 可序列化字典。规则标识同时带上中文标签，省得调用方再查表。"""
    return {
        "check_key": c.check_key,
        "check_name": c.check_name,
        "passed": bool(c.passed),
        "category": c.category,
        "rule": c.rule,
        "rule_label": rule_label(c.rule) if c.rule else "",
        "side": c.side,
        "summary": c.summary,
        "detail": c.detail,
        "evidence": c.evidence or {},
    }


def _build_submission(values: dict, *, row_id: int, submitter: str):
    """用表单字段拼一条只存在于内存里的 GsbSubmission。

    走 `normalize_payload` + `apply_payload` 而不是逐个 setattr：枚举值的
    全角折半、长文本的 strip 都在归一化里，绕过去就会出现「界面上选的明明是
    这个选项、质检却判成非法值」，而那正是归一化当初要修的问题。
    """
    from backend.gsb.models import GsbSubmission
    from backend.gsb.services import submission_service as svc
    from backend.gsb.validators import normalize_payload
    from backend.states import SUBMITTED

    data = normalize_payload(dict(values))

    sub = GsbSubmission()
    sub.id = row_id
    sub.user_id = 0
    sub.submitter_name = str(values.get("submitter_name") or submitter)
    sub.leader_name = ""
    sub.status = SUBMITTED
    sub.current_version = 1
    sub.schema_stale = 0
    sub.deleted_at = None
    sub.extra_json = ""
    sub.repo_id = ""
    now = datetime.now(timezone.utc)
    sub.submitted_at = now
    sub.submitted_date = now.strftime("%Y-%m-%d")
    sub.created_at = now

    svc.apply_payload(sub, data)
    return sub


async def run(payload: dict) -> dict:
    from backend import config_center
    from backend.db import dispose_engine, get_session_factory
    from backend.gsb.qc import rules_local, runner, trace_store
    from backend.gsb.states import gsb_rule_label
    from sqlalchemy import func, select

    from backend.gsb.models import GsbSubmission

    values = payload.get("submission") or {}
    if not values:
        return {"ok": False, "error": "submission 为空"}
    traces = payload.get("traces") or {}
    submitter = str(payload.get("submitter") or "solo-cli")
    defer_screencast = bool(payload.get("defer_screencast", True))

    # 轨迹按 DATA_DIR 下的相对路径挂进来，refs 的结构与上传接口登记的一致
    for side in ("A", "B"):
        rel = str(traces.get(side) or "").strip()
        if not rel:
            return {"ok": False, "error": f"{side} 侧未提供轨迹文件路径"}
        values[f"{side.lower()}_trace_file"] = [
            {"name": rel.rsplit("/", 1)[-1], "path": rel, "size": 0}
        ]

    from backend.gsb.services import submission_service as svc

    deferred: list[str] = []
    original_save = trace_store.save_digest
    original_screencast = rules_local.check_screencast

    async def save_digest_noop(*a, **kw) -> None:
        return None

    trace_store.save_digest = save_digest_noop
    if defer_screencast:
        rules_local.check_screencast = lambda _data: []
        deferred.append("G8 运行录屏（人工环节，质检时尚未录制）")

    factory = get_session_factory()
    try:
        async with factory() as db:
            await config_center.refresh(db)
            # 理由质检与题目规则的模型调用默认读写 qc_llm_cache，这里只读所以关掉
            config_center.set_local_override("qc.llm_cache_enabled", False)
            max_id = (await db.execute(select(func.max(GsbSubmission.id)))).scalar() or 0

            row_id = int(max_id) + 1000
            sub = _build_submission(values, row_id=row_id, submitter=submitter)
            data = svc.to_detail_dict(sub)
            result = await runner.evaluate_one(sub, data, db=db, skip_llm=False)
    finally:
        trace_store.save_digest = original_save
        rules_local.check_screencast = original_screencast
        await dispose_engine()

    checks = [_check_dict(c, gsb_rule_label) for c in result.checks]
    failures = [c for c in checks if not c["passed"]]

    return {
        "ok": True,
        "conclusion": result.conclusion,
        # INCOMPLETE 是平台侧没跑成（池不可用、Token 缺失、轨迹取不到），
        # 既不是通过也不是不通过，调用方要当「待重跑」而不是「被打回」。
        "passed": result.conclusion == runner.CONCLUSION_PASS,
        "incomplete": result.conclusion == runner.CONCLUSION_INCOMPLETE,
        "hit_rule": result.hit_rule,
        "hit_rule_label": gsb_rule_label(result.hit_rule) if result.hit_rule else "",
        "summary": result.summary,
        "error": result.error,
        "confidence": result.confidence,
        "needs_review": bool(result.needs_review),
        "risk_flag": result.risk_flag,
        "risk_note": result.risk_note,
        "git_state": result.git_state,
        "git_note": result.git_note,
        "failures": failures,
        "checks": checks,
        "deferred": deferred,
        "meta": {
            "row_id": row_id,
            "max_submission_id": int(max_id),
            "hard_ms": result.hard_ms,
            "llm_ms": result.llm_ms,
            "task_no": payload.get("task_no"),
        },
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"stdin 不是合法 JSON：{e}"}, ensure_ascii=False))
        return 2
    try:
        result = asyncio.run(run(payload))
    except Exception as e:  # noqa: BLE001
        log(traceback.format_exc())
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
