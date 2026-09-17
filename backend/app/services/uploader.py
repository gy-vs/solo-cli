"""solo-qa 两步上传：form-schema → /submissions/upload → /submissions。"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx

from app.db import session
from app.events import bus
from app.models import UPLOADED, Task, utc_now
from app.services import dockerx, repo, settings_store
from app.services.verifier import DIMS

log = logging.getLogger("uploader")
API = "/api/v1"


def _client() -> httpx.AsyncClient:
    base = settings_store.get("qa.base_url").rstrip("/")
    cookie = settings_store.get("qa.session_cookie")
    csrf = settings_store.get("qa.csrf_token")
    if not (base and cookie and csrf):
        raise RuntimeError("solo-qa 身份未配置完整（地址 / solo_qa_session / solo_qa_csrf）")
    return httpx.AsyncClient(
        base_url=base,
        cookies={"solo_qa_session": cookie, "solo_qa_csrf": csrf},
        headers={"X-CSRF-Token": csrf, "User-Agent": "solo-cli/1.0", "Accept": "application/json"},
        timeout=httpx.Timeout(120, connect=20),
        follow_redirects=False,
    )


async def probe_identity() -> dict:
    try:
        async with _client() as c:
            r = await c.get(f"{API}/auth/me")
    except RuntimeError as exc:
        return {"ok": False, "message": str(exc)}
    except httpx.HTTPError as exc:
        return {"ok": False, "message": f"请求失败：{exc}"}
    if r.status_code == 200:
        u = r.json()
        return {"ok": True, "message": f"已登录：{u.get('real_name') or u.get('username')}（{u.get('role', '')}）"}
    return {"ok": False, "message": f"HTTP {r.status_code}：{r.text[:200]}"}


async def probe_gateway() -> dict:
    key = settings_store.get("cc.api_key")
    if not key:
        return {"ok": False, "message": "未配置网关 Key"}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://llm.jzxhnh.com/v1/models", headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError as exc:
        return {"ok": False, "message": f"无法连接网关：{exc}"}
    if r.status_code in (200, 404, 405):
        return {"ok": True, "message": f"网关可达，Key 已被接受（HTTP {r.status_code}）"}
    if r.status_code in (401, 403):
        return {"ok": False, "message": f"网关拒绝该 Key（HTTP {r.status_code}）"}
    return {"ok": False, "message": f"网关返回 HTTP {r.status_code}"}


async def build_payload(t: Task) -> dict:
    review = t.review or {}
    scores, descs = review.get("scores") or {}, review.get("descs") or {}
    version = t.harness_version
    if t.image_tag:
        real = await dockerx.claude_version(t.image_tag)
        if real:
            version = real
    data = {
        "question_type": t.question_type,
        "difficulty": t.difficulty,
        "languages": t.languages,
        "harness": t.harness or "Claude Code",
        "harness_version": version,
        "os_platform": t.os_platform,
        "repro_level": t.repro_level,
        "env_snapshot": t.env_snapshot,
        "user_prompt": t.user_prompt,
        "session_id": t.session_id,
        "turn_id": t.turn_id,
        "other_issues": review.get("other_issues") or "",
    }
    for dim in DIMS:
        data[f"score_{dim}"] = scores.get(dim)
        data[f"desc_{dim}"] = descs.get(dim) or ""
    return data


def _missing_fields(data: dict) -> list[str]:
    required = [k for k in data if k != "other_issues"]
    return [k for k in required if data.get(k) in (None, "")]


async def upload_task(task_id: int) -> dict:
    with session() as db:
        t = db.get(Task, task_id)
        if t is None:
            return {"ok": False, "message": "任务不存在"}
        if t.status not in ("REVIEWED",):
            return {"ok": False, "message": f"当前状态 {t.status} 不允许上传，需先完成评审且核验无红项"}
        if (t.verify or {}).get("overall") == "block":
            return {"ok": False, "message": "核验存在红项，先处理后再上传"}
        if not t.trace_file or not Path(t.trace_file).exists():
            return {"ok": False, "message": "轨迹文件缺失，无法上传"}
        data = await build_payload(t)
        trace_path = Path(t.trace_file)
        task_no = t.task_no
    missing = _missing_fields(data)
    if missing:
        return {"ok": False, "message": f"字段缺失：{', '.join(missing)}", "fields": missing}

    record: dict = {"started_at": utc_now().isoformat(), "steps": []}
    try:
        async with _client() as c:
            me = await c.get(f"{API}/auth/me")
            if me.status_code != 200:
                return _fail(task_id, record, f"身份失效（HTTP {me.status_code}），请到设置页更新 Cookie", auth=True)
            record["steps"].append("auth/me ok")

            fs = await c.get(f"{API}/submissions/form-schema")
            if fs.status_code != 200:
                return _fail(task_id, record, f"获取表单指纹失败 HTTP {fs.status_code}: {fs.text[:200]}")
            fingerprint = fs.json().get("fingerprint", "")
            record["steps"].append(f"form-schema fingerprint={fingerprint}")

            with trace_path.open("rb") as fp:
                up = await c.post(f"{API}/submissions/upload",
                                  files={"file": (trace_path.name, fp, "application/jsonl")})
            if up.status_code != 200:
                return _fail(task_id, record, f"轨迹上传失败 HTTP {up.status_code}: {up.text[:300]}")
            ref = up.json()
            record["steps"].append(f"upload ok path={ref.get('path')}")
            data["trace_file"] = [{"name": ref.get("name"), "path": ref.get("path"), "size": ref.get("size")}]

            body_json = {"data": data, "schema_fingerprint": fingerprint}
            resp = await c.post(f"{API}/submissions", json=body_json)
            if resp.status_code == 503:
                # 轨迹落盘/COS 暂不可用：等 3 秒重试一次
                record["steps"].append("503, retry once")
                await asyncio.sleep(3)
                resp = await c.post(f"{API}/submissions", json=body_json)
            record["status_code"] = resp.status_code
            try:
                body = resp.json()
            except ValueError:
                body = {"detail": resp.text[:500]}
            record["response"] = body
            if resp.status_code == 201:
                info = None
                with session() as db:
                    t = db.get(Task, task_id)
                    if t is not None:
                        t.status = UPLOADED
                        t.uploaded_at = utc_now()
                        record["ok"] = True
                        record["submission_id"] = body.get("id")
                        t.upload = record
                        info = repo.CommitInfo.of(t)
                bus.publish("tasks", {"type": "task", "id": task_id})
                log.info("题 %s 上传成功 id=%s", task_no, body.get("id"))
                commit = await _commit_code(task_id, record, info)
                return {"ok": True, "message": body.get("message") or "提交成功", "submission_id": body.get("id"),
                        "status": body.get("status"), "round_no": body.get("round_no"), "commit": commit}
            if resp.status_code == 422:
                errors = body.get("errors") or []
                fields = {e.get("field"): e.get("message") for e in errors if isinstance(e, dict)}
                return _fail(task_id, record, body.get("detail") or "校验未通过", fields=fields)
            if resp.status_code in (401, 403):
                return _fail(task_id, record, f"HTTP {resp.status_code}：{body.get('detail', '')}", auth=True)
            return _fail(task_id, record, f"HTTP {resp.status_code}：{str(body.get('detail', body))[:300]}")
    except RuntimeError as exc:
        return _fail(task_id, record, str(exc), auth=True)
    except httpx.HTTPError as exc:
        return _fail(task_id, record, f"请求失败：{exc}")


async def _commit_code(task_id: int, record: dict, info: "repo.CommitInfo | None") -> dict:
    """上传成功后固化工作区产物。提交失败只记一笔，不把成功的上传判为失败。"""
    if info is None:
        return {"ok": False, "skipped": True, "message": "任务已不存在，跳过提交"}
    if not settings_store.get_bool("git.commit_on_upload"):
        return {"ok": False, "skipped": True, "message": "已关闭上传后提交"}
    try:
        res = await repo.commit_after_upload(info)
    except Exception as exc:  # noqa: BLE001
        log.exception("题 %s 上传后提交异常", info.task_no)
        res = {"ok": False, "message": f"提交异常：{exc}"}
    if not res.get("ok") and not res.get("skipped"):
        log.warning("题 %s 上传后提交失败：%s", info.task_no, res.get("message"))
    record["commit"] = res
    with session() as db:
        t = db.get(Task, task_id)
        if t is not None:
            t.upload = dict(record)
    bus.publish("tasks", {"type": "task", "id": task_id})
    return res


def _fail(task_id: int, record: dict, message: str, *, fields: dict | None = None, auth: bool = False) -> dict:
    record["ok"] = False
    record["message"] = message
    if fields:
        record["fields"] = fields
    with session() as db:
        t = db.get(Task, task_id)
        if t is not None:
            t.upload = record
    bus.publish("tasks", {"type": "task", "id": task_id})
    return {"ok": False, "message": message, "fields": fields or {}, "auth_error": auth}
